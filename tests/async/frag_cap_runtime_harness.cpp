// Include the actual runtime to drive its writer seam and retry deadline without
// adding a gameplay clock command or a production-only testing interface.
#include "combat/frag_cap_runtime.c"
#include "flatfile/flatfile_store.h"

#include <cassert>
#include <filesystem>
#include <iostream>

namespace
{
std::string test_root;
persistence_job_write_fn queued_read;
bool refuse_read = false;
std::vector<std::string> announcements;
constexpr int64_t start = INT64_C(1800000000000000);

void write(const frag_cap_state &state)
{
	flatfile_authority_lock lock;
	assert(lock.acquire(test_root, nullptr));
	std::vector<flatfile_authority_operation> operations;
	assert(frag_cap_flatfile_prepare(test_root, lock, state, &operations) ==
	       frag_cap_store_result::ok);
	assert(flatfile_authority_transaction_commit_operations(test_root, lock, operations,
								nullptr) ==
	       flatfile_authority_transaction_result::ok);
}

void complete()
{
	assert(queued_read);
	auto work = std::move(queued_read);
	work();
	frag_cap_runtime_pulse();
}

void refresh()
{
	frag_cap_runtime_refresh();
	frag_cap_runtime_pulse();
	complete();
}
}

enum persistence_mode persistence_mode_get(void)
{
	return PERSISTENCE_MODE_FLATFILE_PRIMARY;
}
const char *persistence_mode_flatfile_root(void)
{
	return test_root.c_str();
}
void logit(const char *, const char *, ...) {}
void send_to_all(const char *text)
{
	announcements.emplace_back(text);
}
bool redis_invalidate_fraglist(void)
{
	return true;
}
player_save_submit_result persistence_writer_submit(persistence_job_kind kind, uint64_t owner,
						    size_t bytes, persistence_job_write_fn work)
{
	assert(kind == persistence_job_kind::frag_cap && owner == 1 && bytes == FRAG_CAP_MAX_BYTES);
	if (refuse_read)
		return player_save_submit_result::unavailable;
	assert(!queued_read);
	queued_read = std::move(work);
	return player_save_submit_result::accepted;
}

int main(int argc, char **argv)
{
	assert(argc == 2);
	test_root = argv[1];
	std::filesystem::create_directories(test_root + "/domains");
	for (const auto &path : { test_root, test_root + "/domains" })
		std::filesystem::permissions(path, std::filesystem::perms::owner_all,
					     std::filesystem::perm_options::replace);
	assert(frag_cap_runtime_boot(start));
	assert(frag_cap_runtime_state()->level == 31);
	assert(announcements.empty());
	auto state = *frag_cap_runtime_state();
	const frag_cap_award partial = { frag_cap_side::good, 5 };
	assert(frag_cap_apply(&state, start, start, &partial, 1));
	write(state);
	frag_cap_runtime_refresh();
	frag_cap_runtime_pulse();
	frag_cap_runtime_refresh(); // Coalesced while the earlier read is in flight.
	assert(frag_cap_runtime_state()->earned == (std::array<uint64_t, 2>{}));
	complete();
	assert(frag_cap_runtime_state()->earned[0] == 5);
	complete(); // The request made during the read was preserved.
	assert(frag_cap_runtime_status(1, start).find("Good 0.05 / Evil 0.00") !=
	       std::string::npos);
	assert(frag_cap_runtime_status(2, start).find("Good 0.05 / Evil 0.00") !=
	       std::string::npos);
	assert(frag_cap_runtime_status(1, start).find("3d 0h 0m 0s") != std::string::npos);
	const auto confirmed = state;
	auto older = state;
	older.revision = 1;
	older.earned = {};
	write(older);
	refresh();
	assert(*frag_cap_runtime_state() == confirmed);
	write(confirmed);

	refuse_read = true;
	frag_cap_runtime_refresh();
	frag_cap_runtime_pulse();
	assert(!queued_read && *frag_cap_runtime_state() == confirmed);
	assert(frag_cap_runtime_status(1, start).find("last confirmed state") != std::string::npos);
	refuse_read = false;
	retry_at = {};
	frag_cap_runtime_pulse();
	complete();
	assert(frag_cap_runtime_status(1, start).find("last confirmed state") == std::string::npos);
	// A failed observation preserves confirmed credit and reports stale status.
	assert(flatfile_atomic_write(test_root + "/domains", "frag-cap.state", { 'b', 'a', 'd' },
				     nullptr));
	refresh();
	assert(*frag_cap_runtime_state() == confirmed);
	assert(frag_cap_runtime_status(1, start).find("last confirmed state") != std::string::npos);
	write(confirmed);
	retry_at = {}; // Exercise recovery without a five-second test sleep.
	frag_cap_runtime_pulse();
	complete();
	assert(frag_cap_runtime_status(1, start).find("last confirmed state") == std::string::npos);
	assert(announcements.empty());

	const frag_cap_award remainder = { frag_cap_side::good, 15 };
	assert(frag_cap_apply(&state, start + FRAG_CAP_HOUR, start + FRAG_CAP_HOUR, &remainder, 1));
	write(state);
	refresh();
	refresh();
	assert(announcements.empty()); // Provisional scores never announce a secured winner.
	assert(frag_cap_flatfile_tick(test_root, start + 72 * FRAG_CAP_HOUR) ==
	       frag_cap_store_result::ok);
	refresh();
	refresh();
	assert(announcements.size() == 1 &&
	       announcements[0].find("Good cap: 32. Evil cap: 31") != std::string::npos);
	assert(frag_cap_runtime_status(1, start + 72 * FRAG_CAP_HOUR).find("Your normal cap: 32") !=
	       std::string::npos);
	assert(frag_cap_runtime_status(2, start + 72 * FRAG_CAP_HOUR).find("Your normal cap: 31") !=
	       std::string::npos);
	assert(frag_cap_flatfile_tick(test_root, start + 216 * FRAG_CAP_HOUR) ==
	       frag_cap_store_result::ok);
	assert(frag_cap_runtime_boot(start + 216 * FRAG_CAP_HOUR));
	assert(frag_cap_runtime_state()->level == 34 && announcements.size() == 1);
	assert(flatfile_atomic_write(test_root + "/domains", "frag-cap.state", { 'b', 'a', 'd' },
				     nullptr));
	assert(!frag_cap_runtime_boot(start + 216 * FRAG_CAP_HOUR));
	std::cout
		<< "PASS cap publication: coalesced reads, viewer isolation, older revisions, failed reads, boot recovery and one announcement\n";
}
