#include "telemetry/telemetry_outage_private.h"

#include <array>
#include <atomic>
#include <cassert>
#include <cerrno>
#include <csignal>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <string>
#include <vector>

#include <fcntl.h>
#include <openssl/sha.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <unistd.h>

std::atomic<bool> fail_write{ false };
std::atomic<bool> fail_rename{ false };
std::atomic<unsigned int> fail_fsync_call{ 0U };
std::atomic<bool> fail_registration_fsync{ false };
extern "C" ssize_t __real_write(int, const void *, size_t);
extern "C" int __real_fsync(int);
extern "C" int __real_renameat(int, const char *, int, const char *);
extern "C" ssize_t __wrap_write(int fd, const void *data, size_t count)
{
	if (fail_write.load())
	{
		errno = ENOSPC;
		return -1;
	}
	return __real_write(fd, data, count);
}
extern "C" int __wrap_fsync(int fd)
{
	struct stat status
	{
	};
	if (fail_registration_fsync.load() && fstat(fd, &status) == 0 && S_ISREG(status.st_mode) &&
	    status.st_size == 464)
	{
		errno = ENOSPC;
		return -1;
	}
	const auto remaining = fail_fsync_call.load();
	if (remaining != 0U && fail_fsync_call.fetch_sub(1U) == 1U)
	{
		errno = ENOSPC;
		return -1;
	}
	return __real_fsync(fd);
}
extern "C" int __wrap_renameat(int source, const char *from, int destination, const char *to)
{
	if (fail_rename.load())
	{
		errno = EIO;
		return -1;
	}
	return __real_renameat(source, from, destination, to);
}

namespace
{
using result = telemetry_outage_result;
using phase = telemetry_outage_phase;
namespace fs = std::filesystem;

struct fixture
{
	fs::path path;
	fixture()
	{
		char directory[] = "/tmp/duris-telemetry-outage-XXXXXX";
		assert(mkdtemp(directory) != nullptr);
		path = directory;
	}
	~fixture() { fs::remove_all(path); }
};

telemetry_outage_observation registration(std::uint64_t incarnation = 1U)
{
	telemetry_outage_observation value{};
	value.producer = { 9100U, incarnation };
	value.environment_id = 20U;
	value.season_id = 30U;
	value.registered_monotonic_usec = value.observed_monotonic_usec = 100U;
	value.registered_utc_usec = value.observed_utc_usec = 1000;
	return value;
}

telemetry_outage_observation sampled(std::uint64_t incarnation = 1U)
{
	auto value = registration(incarnation);
	value.observed_monotonic_usec = 400U;
	value.observed_utc_usec = TELEMETRY_UTC_UNKNOWN;
	value.record_kind_mask = (1U << 1U) | (1U << 6U);
	value.health.admitted_detail = 8U;
	value.health.last_admitted_record_seq = 12U;
	value.health.applied_records = 4U;
	value.health.last_committed_record_seq = 6U;
	value.health.queue_depth = 4U;
	value.unattempted_records = 4U;
	value.health.dropped_detail = 3U;
	return value;
}

std::vector<unsigned char> bytes(const fs::path &file)
{
	std::ifstream input(file, std::ios::binary);
	assert(input.good());
	return { std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>() };
}

void replace(const fs::path &file, const std::vector<unsigned char> &data)
{
	std::ofstream output(file, std::ios::binary | std::ios::trunc);
	assert(output.good());
	output.write(reinterpret_cast<const char *>(data.data()),
		     static_cast<std::streamsize>(data.size()));
	output.close();
	assert(chmod(file.c_str(), 0600) == 0);
}

void word(std::vector<unsigned char> &data, std::size_t offset, std::uint64_t value)
{
	for (unsigned int index = 0; index < 8U; ++index)
		data[offset + index] = static_cast<unsigned char>(value >> (56U - index * 8U));
}

void checksum(std::vector<unsigned char> &data)
{
	assert(SHA256(data.data(), data.size() - SHA256_DIGEST_LENGTH,
		      data.data() + data.size() - SHA256_DIGEST_LENGTH) != nullptr);
}

void terminate_cleanly(telemetry_outage_journal &journal, std::uint64_t incarnation = 1U)
{
	auto value = registration(incarnation);
	value.observed_monotonic_usec = 500U;
	value.phase = phase::clean_drained;
	assert(telemetry_outage_checkpoint(&journal, value) == result::ready);
	telemetry_outage_close(&journal);
}

void lifecycle()
{
	fixture f;
	telemetry_outage_journal journal{};
	assert(telemetry_outage_open(&journal, f.path.c_str(), registration()) == result::ready);
	assert(journal.count == 1U && journal.generation == 1U);
	const auto original = bytes(f.path / "outages.ledger");
	assert(telemetry_outage_read(&journal, f.path.c_str()) == result::invalid);
	assert(journal.directory_fd >= 0); // A mistaken double-open must not release ownership.
	telemetry_outage_journal rival{};
	assert(telemetry_outage_open(&rival, f.path.c_str(), registration(2)) ==
	       result::owned_elsewhere);
	const auto child = fork();
	assert(child >= 0);
	if (child == 0)
	{
		telemetry_outage_journal process_rival{};
		assert(telemetry_outage_open(&process_rival, f.path.c_str(), registration(2)) ==
		       result::owned_elsewhere);
		_exit(0);
	}
	int status = 0;
	assert(waitpid(child, &status, 0) == child && WIFEXITED(status) &&
	       WEXITSTATUS(status) == 0);
	auto value = sampled();
	assert(telemetry_outage_terminal_phase(value) == phase::abandoned);
	assert(telemetry_outage_checkpoint(&journal, value) == result::ready);
	const auto observed = bytes(f.path / "outages.ledger");
	auto invalid = value;
	invalid.health.admitted_detail = 7U;
	assert(telemetry_outage_checkpoint(&journal, invalid) == result::invalid);
	invalid = value;
	invalid.season_id = 99U;
	assert(telemetry_outage_checkpoint(&journal, invalid) == result::invalid);
	assert(bytes(f.path / "outages.ledger") == observed);
	value.phase = phase::abandoned;
	assert(telemetry_outage_checkpoint(&journal, value) == result::ready);
	assert(telemetry_outage_checkpoint(&journal, value) == result::invalid);
	telemetry_outage_close(&journal);
	assert(telemetry_outage_open(&journal, f.path.c_str(), registration()) == result::invalid);
	assert(telemetry_outage_open(&journal, f.path.c_str(), registration(2)) == result::ready);
	assert(journal.observations[0].phase == phase::abandoned);
	terminate_cleanly(journal, 2);
	assert(telemetry_outage_read(&journal, f.path.c_str()) == result::ready);
	assert(journal.count == 2U && journal.observations[1].phase == phase::clean_drained);
	telemetry_outage_close(&journal);
	assert(original.size() == 384U);
	std::puts("outage lifecycle, immutable scopes and monotonic counters passed");
}

void unsafe_storage()
{
	fixture f;
	telemetry_outage_journal journal{};
	assert(telemetry_outage_open(&journal, "relative", registration()) == result::invalid);
	assert(chmod(f.path.c_str(), 0755) == 0);
	assert(telemetry_outage_open(&journal, f.path.c_str(), registration()) ==
	       result::unsafe_storage);
	assert(chmod(f.path.c_str(), 0700) == 0);
	const auto alias = f.path / "alias";
	fs::create_directory_symlink(f.path, alias);
	assert(telemetry_outage_open(&journal, alias.c_str(), registration()) != result::ready);
	assert(telemetry_outage_open(&journal, (alias.string() + "/").c_str(), registration()) !=
	       result::ready);
	fs::remove(alias);
	fs::create_symlink("outages.ledger", f.path / "outages.owner");
	assert(telemetry_outage_open(&journal, f.path.c_str(), registration()) != result::ready);
	fs::remove(f.path / "outages.owner");
	assert(telemetry_outage_open(&journal, f.path.c_str(), registration()) == result::ready);
	telemetry_outage_close(&journal);
	assert(chmod((f.path / "outages.ledger").c_str(), 0644) == 0);
	assert(telemetry_outage_read(&journal, f.path.c_str()) == result::unsafe_storage);
	assert(chmod((f.path / "outages.ledger").c_str(), 0600) == 0);
	fs::create_hard_link(f.path / "outages.ledger", f.path / "duplicate");
	assert(telemetry_outage_read(&journal, f.path.c_str()) == result::unsafe_storage);
	fs::remove(f.path / "duplicate");
	fs::rename(f.path / "outages.ledger", f.path / "original");
	fs::create_symlink("original", f.path / "outages.ledger");
	assert(telemetry_outage_read(&journal, f.path.c_str()) != result::ready);
	std::puts("outage protected paths, ownership, symlinks and hard links passed");
}

void corruption()
{
	fixture f;
	telemetry_outage_journal journal{};
	assert(telemetry_outage_open(&journal, f.path.c_str(), registration()) == result::ready);
	telemetry_outage_close(&journal);
	const auto original = bytes(f.path / "outages.ledger");
	for (const auto size : { std::size_t{ 0U }, std::size_t{ 63U }, original.size() - 1U,
				 original.size() + 1U, TELEMETRY_OUTAGE_MAX_BYTES + 1U })
	{
		auto altered = original;
		altered.resize(size);
		replace(f.path / "outages.ledger", altered);
		assert(telemetry_outage_read(&journal, f.path.c_str()) == result::corrupt);
		assert(bytes(f.path / "outages.ledger") == altered);
	}
	auto altered = original;
	altered[42] ^= 1U;
	replace(f.path / "outages.ledger", altered);
	assert(telemetry_outage_read(&journal, f.path.c_str()) == result::corrupt);
	for (const auto field : { 8U, 9U, 24U, 27U, 32U })
	{
		altered = original;
		word(altered, 32U + field * 8U, UINT64_MAX);
		checksum(altered);
		replace(f.path / "outages.ledger", altered);
		assert(telemetry_outage_read(&journal, f.path.c_str()) == result::corrupt);
	}
	std::puts("outage checksum, truncation, size and semantic corruption passed");
}

void publication_faults()
{
	for (unsigned int fault = 0U; fault < 4U; ++fault)
	{
		fixture f;
		telemetry_outage_journal journal{};
		assert(telemetry_outage_open(&journal, f.path.c_str(), registration()) ==
		       result::ready);
		const auto original = bytes(f.path / "outages.ledger");
		fail_write = fault == 0U;
		fail_rename = fault == 1U;
		fail_fsync_call = fault >= 2U ? fault - 1U : 0U;
		assert(telemetry_outage_checkpoint(&journal, sampled()) == result::io_failure);
		assert(journal.error_code == (fault == 1U ? EIO : ENOSPC));
		assert(journal.observations[0].health.admitted_detail == 0U);
		fail_write = fail_rename = false;
		fail_fsync_call = 0U;
		// A failure before the rename leaves no staging file and the next sample
		// retries in place. A failed rename leaves the whole frame and poisons
		// the journal until a fresh open validates it.
		if (fault == 1U)
		{
			assert(fs::exists(f.path / "outages.pending"));
			assert(telemetry_outage_checkpoint(&journal, sampled()) == result::invalid);
			assert(bytes(f.path / "outages.ledger") == original);
		}
		else
		{
			assert(!fs::exists(f.path / "outages.pending"));
			assert(telemetry_outage_checkpoint(&journal, sampled()) == result::ready);
		}
		telemetry_outage_close(&journal);
		assert(telemetry_outage_read(&journal, f.path.c_str()) == result::ready);
		assert(journal.generation == 2U &&
		       journal.observations[0].health.admitted_detail == 8U);
		assert(!fs::exists(f.path / "outages.pending"));
		telemetry_outage_close(&journal);
		const auto recovered = bytes(f.path / "outages.ledger");
		assert(telemetry_outage_read(&journal, f.path.c_str()) == result::ready);
		assert(journal.generation == 2U && bytes(f.path / "outages.ledger") == recovered);
		telemetry_outage_close(&journal);
	}
	std::puts(
		"outage disk-full, fsync, interrupted publication and idempotent recovery passed");
}

void interrupted_publication()
{
	// What a crash or a full disk leaves between the create and the rename: an
	// empty, a short or a torn pending file. None of them is a whole frame, so an
	// open removes it and the ledger stands; the directory is otherwise untouched.
	fixture f;
	telemetry_outage_journal journal{};
	assert(telemetry_outage_open(&journal, f.path.c_str(), registration()) == result::ready);
	assert(telemetry_outage_checkpoint(&journal, sampled()) == result::ready);
	telemetry_outage_close(&journal);
	const auto original = bytes(f.path / "outages.ledger");
	auto torn = original;
	torn[original.size() - 5U] ^= 1U;
	for (const auto &pending :
	     { std::vector<unsigned char>{}, std::vector<unsigned char>(100U, 7U),
	       std::vector<unsigned char>(original.begin(), original.begin() + 200), torn })
	{
		replace(f.path / "outages.pending", pending);
		assert(telemetry_outage_read(&journal, f.path.c_str()) == result::ready);
		assert(journal.generation == 2U && journal.count == 1U);
		assert(!fs::exists(f.path / "outages.pending"));
		assert(bytes(f.path / "outages.ledger") == original);
		telemetry_outage_close(&journal);
	}
	replace(f.path / "outages.pending", {});
	assert(telemetry_outage_open(&journal, f.path.c_str(), registration(2)) == result::ready);
	assert(journal.count == 2U && journal.generation == 3U);
	assert(journal.observations[0].phase == phase::unknown_tail);
	assert(!fs::exists(f.path / "outages.pending"));
	telemetry_outage_close(&journal);
	std::puts("outage interrupted publication is removed and the ledger stands passed");
}

void changed_storage()
{
	for (unsigned int change = 0U; change < 3U; ++change)
	{
		fixture f;
		telemetry_outage_journal journal{};
		assert(telemetry_outage_open(&journal, f.path.c_str(), registration()) ==
		       result::ready);
		const auto original = bytes(f.path / "outages.ledger");
		if (change == 0U)
			assert(chmod(f.path.c_str(), 0755) == 0);
		else if (change == 1U)
			fs::remove(f.path / "outages.owner");
		else
			assert(chmod((f.path / "outages.ledger").c_str(), 0644) == 0);
		assert(telemetry_outage_checkpoint(&journal, sampled()) == result::unsafe_storage);
		assert(bytes(f.path / "outages.ledger") == original &&
		       !fs::exists(f.path / "outages.pending"));
		telemetry_outage_close(&journal);
	}
	std::puts("outage changed permissions or replaced ownership refuse mutation passed");
}

void pending_chain()
{
	fixture f;
	telemetry_outage_journal journal{};
	assert(telemetry_outage_open(&journal, f.path.c_str(), registration()) == result::ready);
	assert(telemetry_outage_checkpoint(&journal, sampled()) == result::ready);
	telemetry_outage_close(&journal);
	const auto original = bytes(f.path / "outages.ledger");
	for (const auto field : { 0U, 2U, 4U, 6U, 10U, 12U, 19U })
	{
		auto pending = original;
		word(pending, 8U, 3U);
		word(pending, 32U + field * 8U, field < 6U ? 999U : 0U);
		checksum(pending);
		replace(f.path / "outages.pending", pending);
		assert(telemetry_outage_read(&journal, f.path.c_str()) == result::corrupt);
		assert(bytes(f.path / "outages.ledger") == original);
		assert(bytes(f.path / "outages.pending") == pending);
	}
	fs::remove(f.path / "outages.pending");
	assert(telemetry_outage_open(&journal, f.path.c_str(), registration(2)) == result::ready);
	assert(journal.observations[0].observed_monotonic_usec == 400U);
	assert(journal.observations[0].phase == phase::unknown_tail);
	terminate_cleanly(journal, 2);
	const auto historical = bytes(f.path / "outages.ledger");
	auto pending = historical;
	word(pending, 8U, 5U);
	word(pending, 32U + 10U * 8U, 9U);
	checksum(pending);
	replace(f.path / "outages.pending", pending);
	assert(telemetry_outage_read(&journal, f.path.c_str()) == result::corrupt);
	assert(bytes(f.path / "outages.ledger") == historical);
	std::puts("outage pending chain refuses altered identities and rewritten history passed");
}

telemetry_quota_binding quota_binding()
{
	return { 678214U, 1U, 20U, 30U, 8U, 2U, 10U };
}

constexpr telemetry_utc_usec QUOTA_UTC = 1'728'000'000'000'000LL;
constexpr telemetry_utc_usec DAY = 86'400'000'000LL;

void quota_accounting()
{
	fixture f;
	telemetry_outage_journal j{};
	const auto b = quota_binding();
	assert(telemetry_outage_read(&j, f.path.c_str()) == result::ready);
	assert(telemetry_outage_quota_check(&j, b) == result::invalid);
	assert(j.error_code == ENODATA);
	assert(telemetry_outage_quota_reserve(&j, b, QUOTA_UTC, 1U, 0U) == result::invalid);
	assert(telemetry_outage_quota_initialize(&j, b, QUOTA_UTC) == result::ready);
	assert(j.count == 0U && j.quota.day == QUOTA_UTC / DAY);
	assert(fs::file_size(f.path / "outages.owner") == 48U);
	assert((fcntl(j.directory_fd, F_GETFD) & FD_CLOEXEC) != 0);
	assert((fcntl(j.ownership_fd, F_GETFD) & FD_CLOEXEC) != 0);
	assert(telemetry_outage_quota_initialize(&j, b, QUOTA_UTC) == result::invalid);
	assert(telemetry_outage_quota_reserve(&j, b, QUOTA_UTC, 5U, 1U) == result::ready);
	assert(telemetry_outage_quota_reserve(&j, b, QUOTA_UTC, 2U, 1U) ==
	       result::ready); // Retried attempts are charged again.
	assert(telemetry_outage_quota_reserve(&j, b, QUOTA_UTC, 1U, 0U) == result::ready);
	const auto full = bytes(f.path / "outages.ledger");
	assert(j.quota.normal_reserved == 8U && j.quota.health_reserved == 2U);
	assert(telemetry_outage_quota_reserve(&j, b, QUOTA_UTC, 1U, 0U) == result::invalid);
	assert(j.error_code == EDQUOT);
	assert(telemetry_outage_quota_reserve(&j, b, QUOTA_UTC, 0U, 1U) == result::invalid);
	assert(telemetry_outage_quota_reserve(&j, b, QUOTA_UTC - DAY, 1U, 0U) == result::invalid);
	assert(j.error_code == ERANGE);
	assert(telemetry_outage_quota_reserve(&j, b, TELEMETRY_UTC_UNKNOWN, 1U, 0U) ==
	       result::invalid);
	assert(telemetry_outage_quota_reserve(&j, b, QUOTA_UTC, UINT32_MAX, UINT32_MAX) ==
	       result::invalid);
	auto wrong = b;
	++wrong.sender_id;
	assert(telemetry_outage_quota_check(&j, wrong) == result::invalid);
	assert(j.error_code == EINVAL);
	assert(bytes(f.path / "outages.ledger") == full);
	telemetry_outage_journal rival{};
	assert(telemetry_outage_read(&rival, f.path.c_str()) == result::owned_elsewhere);
	telemetry_outage_close(&j);
	assert(telemetry_outage_open(&j, f.path.c_str(), registration()) == result::ready);
	assert(j.quota.normal_reserved == 8U && j.quota.health_reserved == 2U);
	assert(telemetry_outage_quota_reserve(&j, b, QUOTA_UTC + DAY, 2U, 0U) == result::ready);
	assert(j.quota.normal_reserved == 2U && j.quota.health_reserved == 0U);
	const auto recovery_generation = j.generation;
	const auto before = bytes(f.path / "outages.ledger");
	assert(telemetry_outage_quota_exhaust_day(&j, b, QUOTA_UTC + DAY) == result::ready);
	assert(bytes(f.path / ("outages.ledger.recovery." + std::to_string(recovery_generation))) ==
	       before);
	assert(telemetry_outage_quota_reserve(&j, b, QUOTA_UTC + DAY, 1U, 0U) == result::invalid);
	assert(telemetry_outage_quota_reserve(&j, b, QUOTA_UTC + DAY, 0U, 1U) == result::invalid);
	telemetry_outage_close(&j);
	auto bad_registration = registration(2U);
	++bad_registration.environment_id;
	assert(telemetry_outage_open(&j, f.path.c_str(), bad_registration) == result::invalid);
	std::puts(
		"quota initialization, retry charging, limits, clock and restore recovery passed");
}

void quota_publication_faults()
{
	const auto b = quota_binding();
	for (unsigned int step = 0U; step < 5U; ++step)
	{
		fixture f;
		telemetry_outage_journal j{};
		assert(telemetry_outage_read(&j, f.path.c_str()) == result::ready);
		assert(telemetry_outage_quota_initialize(&j, b, QUOTA_UTC) == result::ready);
		if (step == 0U)
			fail_write.store(true);
		else if (step == 4U)
			fail_rename.store(true);
		else
			fail_fsync_call.store(step);
		assert(telemetry_outage_quota_reserve(&j, b, QUOTA_UTC, 3U, 0U) ==
		       result::io_failure);
		assert(j.quota_poisoned);
		assert(telemetry_outage_quota_reserve(&j, b, QUOTA_UTC, 1U, 0U) == result::corrupt);
		fail_write.store(false);
		fail_rename.store(false);
		fail_fsync_call.store(0U);
		telemetry_outage_close(&j);
		assert(telemetry_outage_read(&j, f.path.c_str()) == result::ready);
		assert(j.quota.normal_reserved == (step <= 1U ? 0U : 3U));
		assert(telemetry_outage_quota_reserve(&j, b, QUOTA_UTC, 1U, 0U) == result::ready);
		telemetry_outage_close(&j);
	}
	std::puts("quota write, file/owner/directory fsync and rename failures passed");
}

void quota_rollback()
{
	const auto b = quota_binding();
	fixture f;
	telemetry_outage_journal j{};
	assert(telemetry_outage_read(&j, f.path.c_str()) == result::ready);
	assert(telemetry_outage_quota_initialize(&j, b, QUOTA_UTC) == result::ready);
	assert(telemetry_outage_quota_reserve(&j, b, QUOTA_UTC, 2U, 0U) == result::ready);
	const auto previous = bytes(f.path / "outages.ledger");
	const auto previous_marker = bytes(f.path / "outages.owner");
	assert(telemetry_outage_quota_reserve(&j, b, QUOTA_UTC, 2U, 0U) == result::ready);
	const auto latest = bytes(f.path / "outages.ledger");
	telemetry_outage_close(&j);
	replace(f.path / "outages.ledger", previous);
	assert(telemetry_outage_read(&j, f.path.c_str()) ==
	       result::corrupt); // Partial backup rollback.
	replace(f.path / "outages.ledger", latest);
	auto conflict = latest;
	word(conflict, 96U, 0U); // Same generation, lower normal count, valid frame checksum.
	checksum(conflict);
	replace(f.path / "outages.ledger", conflict);
	assert(telemetry_outage_read(&j, f.path.c_str()) == result::corrupt);
	replace(f.path / "outages.ledger", latest);
	auto pending = latest;
	word(pending, 8U, j.generation + 1U);
	word(pending, 96U, 1U);
	checksum(pending);
	replace(f.path / "outages.pending", pending);
	assert(telemetry_outage_read(&j, f.path.c_str()) == result::corrupt);
	assert(bytes(f.path / "outages.pending") == pending);
	fs::remove(f.path / "outages.pending");
	replace(f.path / "outages.ledger", previous);
	replace(f.path / "outages.owner",
		previous_marker); // Full rollback is inherently undetectable.
	assert(telemetry_outage_read(&j, f.path.c_str()) == result::ready);
	assert(telemetry_outage_quota_exhaust_day(&j, b, QUOTA_UTC) == result::ready);
	assert(telemetry_outage_quota_reserve(&j, b, QUOTA_UTC, 1U, 0U) == result::invalid);
	telemetry_outage_close(&j);
	std::puts(
		"quota partial/same-generation/pending rollback refusal and full-restore exhaustion passed");
}

void quota_rotation()
{
	fixture f;
	telemetry_outage_journal j{};
	const auto b = quota_binding();
	assert(telemetry_outage_read(&j, f.path.c_str()) == result::ready);
	assert(telemetry_outage_quota_initialize(&j, b, QUOTA_UTC) == result::ready);
	telemetry_outage_close(&j);
	for (std::uint64_t incarnation = 1U; incarnation <= TELEMETRY_OUTAGE_MAX_PRODUCERS;
	     ++incarnation)
	{
		assert(telemetry_outage_open(&j, f.path.c_str(), registration(incarnation)) ==
		       result::ready);
		if (incarnation == 1U)
			assert(telemetry_outage_quota_reserve(&j, b, QUOTA_UTC, 5U, 1U) ==
			       result::ready);
		terminate_cleanly(j, incarnation);
	}
	fail_fsync_call.store(4U); // Pending registration after durable archive, before rename.
	assert(telemetry_outage_open(&j, f.path.c_str(), registration(257U)) == result::io_failure);
	fail_fsync_call.store(0U);
	assert(telemetry_outage_read(&j, f.path.c_str()) == result::ready);
	assert(j.count == 1U && j.observations[0].producer.process_id == 257U);
	assert(j.quota.normal_reserved == 5U && j.quota.health_reserved == 1U);
	telemetry_outage_close(&j);
	assert(telemetry_outage_open(&j, f.path.c_str(), registration(258U)) == result::ready);
	assert(j.count == 2U && j.quota.normal_reserved == 5U);
	telemetry_outage_close(&j);
	std::puts(
		"quota survives producer archive rotation and interrupted next registration passed");
}

void quota_rotation_retry()
{
	fixture f;
	telemetry_outage_journal j{};
	const auto b = quota_binding();
	assert(telemetry_outage_read(&j, f.path.c_str()) == result::ready);
	assert(telemetry_outage_quota_initialize(&j, b, QUOTA_UTC) == result::ready);
	telemetry_outage_close(&j);
	for (std::size_t index = 1U; index <= TELEMETRY_OUTAGE_MAX_PRODUCERS; ++index)
	{
		assert(telemetry_outage_open(&j, f.path.c_str(), registration(index)) ==
		       result::ready);
		if (index == 1U)
			assert(telemetry_outage_quota_reserve(&j, b, QUOTA_UTC, 5U, 1U) ==
			       result::ready);
		telemetry_outage_close(&j);
	}
	std::vector<unsigned char> terminal;
	for (std::uint64_t attempt = 0U; attempt < 4U; ++attempt)
	{
		auto next = registration(300U + attempt);
		next.registered_utc_usec = next.observed_utc_usec = 2000 + attempt;
		fail_registration_fsync = true;
		assert(telemetry_outage_open(&j, f.path.c_str(), next) == result::io_failure);
		fail_registration_fsync = false;
		assert(!fs::exists(f.path / "outages.pending"));
		if (attempt == 0U)
			terminal = bytes(f.path / "outages.ledger");
		assert(bytes(f.path / "outages.ledger") == terminal);
		std::size_t archives = 0U;
		for (const auto &entry : fs::directory_iterator(f.path))
			archives += entry.path().filename().string().rfind("outages.ledger.", 0) ==
				    0;
		assert(archives == 1U);
	}
	assert(telemetry_outage_open(&j, f.path.c_str(), registration(400U)) == result::ready);
	assert(j.count == 1U && j.quota.normal_reserved == 5U && j.quota.health_reserved == 1U);
	telemetry_outage_close(&j);
	std::puts(
		"quota rotation reuses one terminal archive across failed fresh registrations passed");
}

void quota_season_rollover()
{
	for (const auto total : { 9U, 10U })
	{
		auto b = quota_binding();
		b.total_limit = total;
		auto next = b;
		++next.season_id;
		for (unsigned int fault = 0U; fault <= 7U; ++fault)
		{
			fixture f;
			telemetry_outage_journal j{};
			assert(telemetry_outage_open(&j, f.path.c_str(), registration()) ==
			       result::ready);
			assert(telemetry_outage_checkpoint(&j, sampled()) == result::ready);
			assert(telemetry_outage_quota_initialize(&j, b, QUOTA_UTC) ==
			       result::ready);
			assert(telemetry_outage_quota_reserve(&j, b, QUOTA_UTC, 2U, 1U) ==
			       result::ready);
			const auto original = bytes(f.path / "outages.ledger");
			const auto generation = j.generation;
			for (unsigned int field = 0U; field < 7U; ++field)
			{
				auto wrong = next;
				if (field == 0U)
					++wrong.project_id;
				if (field == 1U)
					++wrong.sender_id;
				if (field == 2U)
					++wrong.environment_id;
				if (field == 3U)
					--wrong.total_limit;
				if (field == 4U)
					--wrong.normal_limit;
				if (field == 5U)
					--wrong.health_limit;
				if (field == 6U)
					wrong.season_id = 0U;
				assert(telemetry_outage_quota_rollover(&j, wrong, QUOTA_UTC) ==
				       result::invalid);
			}
			assert(telemetry_outage_quota_rollover(&j, next, QUOTA_UTC - DAY) ==
			       result::invalid);
			assert(j.error_code == ERANGE);
			assert(telemetry_outage_quota_rollover(&j, next, TELEMETRY_UTC_UNKNOWN) ==
			       result::invalid);
			assert(bytes(f.path / "outages.ledger") == original);
			fail_write = fault == 0U;
			fail_fsync_call = fault >= 1U && fault <= 5U ? fault : 0U;
			fail_rename = fault == 6U;
			assert(telemetry_outage_quota_rollover(&j, next, QUOTA_UTC) ==
			       (fault == 7U ? result::ready : result::io_failure));
			fail_write = fail_rename = false;
			fail_fsync_call = 0U;
			telemetry_outage_close(&j);
			assert(telemetry_outage_read(&j, f.path.c_str()) == result::ready);
			if (fault <= 3U)
			{
				assert(j.quota.binding.season_id == b.season_id);
				assert(j.quota.normal_reserved == 2U &&
				       j.quota.health_reserved == 1U);
				assert(telemetry_outage_quota_rollover(&j, next, QUOTA_UTC) ==
				       result::ready);
			}
			assert(j.quota.binding.season_id == next.season_id);
			assert(j.count == 1U && j.observations[0].season_id == b.season_id);
			assert(j.observations[0].observed_monotonic_usec == 400U);
			assert(j.quota.normal_reserved == 8U &&
			       j.quota.health_reserved == total - 8U);
			assert(bytes(f.path / ("outages.ledger.recovery." +
					       std::to_string(generation))) == original);
			assert(telemetry_outage_quota_reserve(&j, next, QUOTA_UTC, 1U, 0U) ==
			       result::invalid);
			assert(j.error_code == EDQUOT);
			assert(telemetry_outage_quota_reserve(&j, next, QUOTA_UTC, 0U, 1U) ==
			       result::invalid);
			const auto exhausted = bytes(f.path / "outages.ledger");
			const auto owner = bytes(f.path / "outages.owner");
			const auto exhausted_generation = j.generation;
			const auto files = std::distance(fs::directory_iterator(f.path),
							 fs::directory_iterator{});
			fail_fsync_call = 1U;
			assert(telemetry_outage_quota_rollover(&j, next, QUOTA_UTC) ==
			       result::io_failure);
			fail_fsync_call = 0U;
			for (unsigned int retry = 0U; retry < 3U; ++retry)
			{
				assert(telemetry_outage_quota_rollover(&j, next, QUOTA_UTC) ==
				       result::ready);
				assert(telemetry_outage_quota_exhaust_day(&j, next, QUOTA_UTC) ==
				       result::ready);
				assert(j.generation == exhausted_generation && j.error_code == 0U);
				assert(bytes(f.path / "outages.ledger") == exhausted);
				assert(bytes(f.path / "outages.owner") == owner);
				assert(std::distance(fs::directory_iterator(f.path),
						     fs::directory_iterator{}) == files);
			}
			assert(telemetry_outage_quota_reserve(&j, next, QUOTA_UTC + DAY, 1U, 0U) ==
			       result::ready);
			assert(j.quota.normal_reserved == 1U && j.quota.health_reserved == 0U);
			telemetry_outage_close(&j);
			assert(telemetry_outage_open(&j, f.path.c_str(), registration(2U)) ==
			       result::invalid);
			auto new_scope = registration(2U);
			new_scope.season_id = next.season_id;
			assert(telemetry_outage_open(&j, f.path.c_str(), new_scope) ==
			       result::ready);
			assert(j.count == 2U && j.observations[0].phase == phase::unknown_tail);
			telemetry_outage_close(&j);
		}
	}
	// A whole pending frame cannot change season while leaving usable quota,
	// even if its owner witness and checksum agree.
	fixture f;
	telemetry_outage_journal j{};
	const auto b = quota_binding();
	assert(telemetry_outage_read(&j, f.path.c_str()) == result::ready);
	assert(telemetry_outage_quota_initialize(&j, b, QUOTA_UTC) == result::ready);
	fail_rename = true;
	assert(telemetry_outage_quota_reserve(&j, b, QUOTA_UTC, 1U, 0U) == result::io_failure);
	fail_rename = false;
	telemetry_outage_close(&j);
	auto pending = bytes(f.path / "outages.pending");
	word(pending, 32U + 3U * 8U, b.season_id + 1U);
	checksum(pending);
	replace(f.path / "outages.pending", pending);
	auto owner = bytes(f.path / "outages.owner");
	std::copy(pending.end() - SHA256_DIGEST_LENGTH, pending.end(), owner.begin() + 16U);
	replace(f.path / "outages.owner", owner);
	assert(telemetry_outage_read(&j, f.path.c_str()) == result::corrupt);
	assert(fs::exists(f.path / "outages.pending"));
	std::puts(
		"quota season rollover preserves history, exhausts today and recovers every publication fault passed");
}

void wait_success(pid_t child)
{
	int status = 0;
	assert(waitpid(child, &status, 0) == child);
	assert(WIFEXITED(status) && WEXITSTATUS(status) == 0);
}

void abrupt_kill()
{
	fixture f;
	int pipe_fds[2];
	assert(pipe(pipe_fds) == 0);
	const auto child = fork();
	assert(child >= 0);
	if (child == 0)
	{
		close(pipe_fds[0]);
		telemetry_outage_journal journal{};
		assert(telemetry_outage_open(&journal, f.path.c_str(), registration()) ==
		       result::ready);
		auto value = sampled();
		value.inflight_records = 2U;
		value.unattempted_records = 2U;
		value.health.inflight_active = 1U;
		value.health.inflight_first_record_seq = 8U;
		value.health.inflight_last_record_seq = 9U;
		value.health.ambiguous_commits = 1U;
		value.health.last_failure_class = telemetry_failure_class::commit_ambiguous;
		assert(telemetry_outage_terminal_phase(value) == phase::unknown_tail);
		assert(telemetry_outage_checkpoint(&journal, value) == result::ready);
		assert(write(pipe_fds[1], "!", 1) == 1);
		for (;;)
			pause();
	}
	close(pipe_fds[1]);
	char signal = 0;
	assert(read(pipe_fds[0], &signal, 1) == 1);
	close(pipe_fds[0]);
	assert(kill(child, SIGKILL) == 0);
	int status = 0;
	assert(waitpid(child, &status, 0) == child && WIFSIGNALED(status));
	telemetry_outage_journal journal{};
	assert(telemetry_outage_open(&journal, f.path.c_str(), registration(2)) == result::ready);
	assert(journal.count == 2U && journal.observations[0].phase == phase::unknown_tail);
	const auto &before_kill = journal.observations[0];
	assert(before_kill.observed_monotonic_usec == 400U);
	assert(before_kill.observed_utc_usec == TELEMETRY_UTC_UNKNOWN);
	assert(before_kill.inflight_records == 2U && before_kill.unattempted_records == 2U);
	assert(before_kill.health.ambiguous_commits == 1U);
	terminate_cleanly(journal, 2);
	std::puts(
		"outage real SIGKILL retains ambiguous last sample without a crash boundary passed");
}

void process_exec(const char *executable)
{
	fixture f;
	const auto child = fork();
	assert(child >= 0);
	if (child == 0)
	{
		telemetry_outage_journal journal{};
		assert(telemetry_outage_open(&journal, f.path.c_str(), registration()) ==
		       result::ready);
		assert(telemetry_outage_checkpoint(&journal, sampled()) == result::ready);
		// Do not close: successful replacement proves O_CLOEXEC drops ownership.
		execl(executable, executable, "--after-exec", f.path.c_str(), nullptr);
		_exit(1);
	}
	wait_success(child);
	telemetry_outage_journal journal{};
	assert(telemetry_outage_read(&journal, f.path.c_str()) == result::ready);
	assert(journal.count == 2U && journal.observations[0].phase == phase::unknown_tail);
	assert(journal.observations[1].phase == phase::clean_drained);
	telemetry_outage_close(&journal);
	std::puts("outage real process exec, restart and descriptor ownership passed");
}

void rotation()
{
	fixture f;
	telemetry_outage_journal journal{};
	for (std::size_t index = 0U; index < TELEMETRY_OUTAGE_MAX_PRODUCERS; ++index)
	{
		assert(telemetry_outage_open(&journal, f.path.c_str(), registration(index + 1U)) ==
		       result::ready);
		// The last lifetime ends without a terminal sample, like a kill.
		if (index + 1U < TELEMETRY_OUTAGE_MAX_PRODUCERS)
			terminate_cleanly(journal, index + 1U);
		else
			telemetry_outage_close(&journal);
	}
	const auto full = bytes(f.path / "outages.ledger");
	assert(full.size() ==
	       64U + TELEMETRY_OUTAGE_MAX_PRODUCERS * TELEMETRY_OUTAGE_DISK_WORDS * 8U);
	// Lifetime 257 keeps the full chain as an archive, with the killed producer
	// closed as an unknown tail, and starts a new chain with itself.
	assert(telemetry_outage_open(&journal, f.path.c_str(), registration(257)) == result::ready);
	assert(journal.count == 1U && journal.generation == 1U && journal.current == 0U);
	terminate_cleanly(journal, 257);
	assert(fs::file_size(f.path / "outages.ledger") == 384U);
	const auto archive = f.path / "outages.ledger.1000.512";
	assert(fs::exists(archive) && fs::file_size(archive) == full.size());
	std::size_t files = 0U;
	for (const auto &entry : fs::directory_iterator(f.path))
		files += entry.path().filename().string().rfind("outages.ledger.", 0) == 0 ? 1U :
											     0U;
	assert(files == 1U);
	assert(telemetry_outage_read(&journal, f.path.c_str()) == result::ready);
	assert(journal.count == 1U && journal.generation == 2U &&
	       journal.observations[0].phase == phase::clean_drained);
	telemetry_outage_close(&journal);
	fixture g;
	fs::copy_file(archive, g.path / "outages.ledger");
	assert(chmod((g.path / "outages.ledger").c_str(), 0600) == 0);
	assert(telemetry_outage_read(&journal, g.path.c_str()) == result::ready);
	assert(journal.count == TELEMETRY_OUTAGE_MAX_PRODUCERS && journal.generation == 512U);
	assert(journal.observations[TELEMETRY_OUTAGE_MAX_PRODUCERS - 1U].phase ==
	       phase::unknown_tail);
	assert(journal.observations[0].phase == phase::clean_drained);
	telemetry_outage_close(&journal);
	std::puts("outage full producer table is archived and the chain starts again passed");
}
} // namespace

int main(int argc, char **argv)
{
	if (argc == 3 && std::strcmp(argv[1], "--make-fixture") == 0)
	{
		telemetry_outage_journal journal{};
		assert(telemetry_outage_open(&journal, argv[2], registration()) == result::ready);
		assert(telemetry_outage_checkpoint(&journal, sampled()) == result::ready);
		telemetry_outage_close(&journal);
		assert(telemetry_outage_open(&journal, argv[2], registration(2)) == result::ready);
		terminate_cleanly(journal, 2);
		return 0;
	}
	if (argc == 3 && std::strcmp(argv[1], "--hold-fixture") == 0)
	{
		telemetry_outage_journal journal{};
		assert(telemetry_outage_open(&journal, argv[2], registration()) == result::ready);
		std::puts("held");
		std::fflush(stdout);
		for (;;)
			pause();
	}
	if (argc == 3 && std::strcmp(argv[1], "--after-exec") == 0)
	{
		telemetry_outage_journal journal{};
		assert(telemetry_outage_open(&journal, argv[2], registration(2)) == result::ready);
		terminate_cleanly(journal, 2);
		return 0;
	}
	lifecycle();
	unsafe_storage();
	corruption();
	publication_faults();
	interrupted_publication();
	changed_storage();
	pending_chain();
	abrupt_kill();
	process_exec(argv[0]);
	rotation();
	quota_accounting();
	quota_publication_faults();
	quota_rollback();
	quota_rotation();
	quota_rotation_retry();
	quota_season_rollover();
	std::puts("telemetry durable outage evidence qualification passed");
}
