/****************************************************************************
 *
 *  File: telemetry_outage.c                                    Part of Duris
 *  Usage: the telemetry outage ledger: frames, journal, and recovery
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#include "telemetry/telemetry_outage_private.h"

#include <algorithm>
#include <bit>
#include <cerrno>
#include <cstdio>
#include <cstring>
#include <limits>
#include <new>
#include <vector>

#include <fcntl.h>
#include <openssl/sha.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <unistd.h>

namespace
{
	constexpr const char *LEDGER = "outages.ledger";
	constexpr const char *PENDING = "outages.pending";
	constexpr const char *LOCK = "outages.owner";
	constexpr unsigned char MAGIC[] = { 'D', 'M', 'S', 'T', 'L', 'J', '0', '1' };
	constexpr unsigned char QUOTA_MAGIC[] = { 'D', 'M', 'S', 'T', 'L', 'J', '0', '2' };
	constexpr unsigned char POSTHOG_MAGIC[] = { 'D', 'M', 'S', 'T', 'L', 'J', '0', '3' };
	constexpr unsigned char MARKER_MAGIC[] = { 'D', 'M', 'S', 'Q', 'W', '0', '0', '1' };
	using words = std::array<std::uint64_t, TELEMETRY_OUTAGE_POSTHOG_WORDS>;
	constexpr std::uint64_t KNOWN_KINDS = (std::uint64_t{ 1U } << 9U) - 2U;
	words encode(const telemetry_outage_observation &value);

	struct file_guard
	{
		int fd;
		~file_guard()
		{
			if (fd >= 0)
				close(fd);
		}
	};

	telemetry_outage_result failure(telemetry_outage_journal & journal,
					telemetry_outage_result result, int error)
	{
		journal.error_code = static_cast<std::uint32_t>(error);
		return result;
	}

	bool same_producer(telemetry_producer_id left, telemetry_producer_id right)
	{
		return left.boot_id == right.boot_id && left.process_id == right.process_id;
	}

	bool clean(const telemetry_outage_observation &value)
	{
		const auto &h = value.health;
		if (h.admitted_detail >= UINT64_MAX - h.admitted_control ||
		    h.applied_records >= UINT64_MAX - h.duplicate_records)
			return false;
		const auto accepted = h.admitted_detail + h.admitted_control;
		const auto acknowledged = h.applied_records + h.duplicate_records;
		return acknowledged < UINT64_MAX - h.stale_checkpoint_records &&
		       accepted == acknowledged + h.stale_checkpoint_records &&
		       h.queue_depth == 0U && value.inflight_records == 0U &&
		       h.invalid_records == 0U && h.conflict_records == 0U &&
		       h.quarantined_records == 0U;
	}

	bool valid(const telemetry_outage_observation &value)
	{
		const auto phase = static_cast<std::uint8_t>(value.phase);
		const auto &h = value.health;
		return telemetry_producer_id_is_valid(value.producer) &&
		       value.environment_id != 0U && value.season_id != 0U &&
		       value.observed_monotonic_usec >= value.registered_monotonic_usec &&
		       phase >= 1U && phase <= 4U &&
		       (value.record_kind_mask & ~KNOWN_KINDS) == 0U &&
		       (h.last_failure_record_kind_mask & ~KNOWN_KINDS) == 0U &&
		       static_cast<std::uint8_t>(h.last_failure_class) <=
			       static_cast<std::uint8_t>(
				       telemetry_failure_class::permanent_repository) &&
		       h.last_committed_record_seq <= h.last_admitted_record_seq &&
		       h.last_consumed_record_seq <= h.last_admitted_record_seq &&
		       h.queue_depth <= TELEMETRY_QUEUE_CAPACITY_PROPOSAL &&
		       value.inflight_records <= TELEMETRY_BATCH_MAX_RECORDS_PROPOSAL &&
		       value.unattempted_records <= h.queue_depth &&
		       value.inflight_records + value.unattempted_records == h.queue_depth &&
		       h.inflight_active <= 1U &&
		       (h.inflight_active != 0U) == (value.inflight_records != 0U) &&
		       (h.inflight_active == 0U ||
			(h.inflight_first_record_seq != 0U &&
			 h.inflight_last_record_seq >= h.inflight_first_record_seq &&
			 h.inflight_last_record_seq <= h.last_admitted_record_seq)) &&
		       (value.phase != telemetry_outage_phase::clean_drained || clean(value)) &&
		       (value.phase != telemetry_outage_phase::abandoned ||
			(value.inflight_records == 0U && value.unattempted_records != 0U));
	}

	bool registration_is_empty(const telemetry_outage_observation &value)
	{
		if (!valid(value) || value.phase != telemetry_outage_phase::running ||
		    value.observed_monotonic_usec != value.registered_monotonic_usec ||
		    value.observed_utc_usec != value.registered_utc_usec ||
		    value.record_kind_mask != 0U)
			return false;
		const auto fields = encode(value);
		return std::all_of(fields.begin() + 10U, fields.begin() + 40U,
				   [](auto field) { return field == 0U; }) &&
		       fields[41] == 0U && fields[42] == 0U;
	}

	bool extends(const telemetry_outage_observation &previous,
		     const telemetry_outage_observation &next)
	{
		const auto left = encode(previous);
		const auto right = encode(next);
		if (previous.phase != telemetry_outage_phase::running)
			return left == right;
		if (!std::equal(left.begin(), left.begin() + 6U, right.begin()) ||
		    right[6] < left[6] || (right[9] & left[9]) != left[9])
			return false;
		for (const auto field : { 10U, 11U, 12U, 13U, 14U, 15U, 16U, 17U, 18U, 19U, 20U,
					  21U, 28U, 29U, 30U, 31U, 39U, 41U, 42U })
			if (right[field] < left[field])
				return false;
		return true;
	}

	words encode(const telemetry_outage_observation &v)
	{
		const auto &h = v.health;
		return { v.producer.boot_id,
			 v.producer.process_id,
			 v.environment_id,
			 v.season_id,
			 v.registered_monotonic_usec,
			 std::bit_cast<std::uint64_t>(v.registered_utc_usec),
			 v.observed_monotonic_usec,
			 std::bit_cast<std::uint64_t>(v.observed_utc_usec),
			 static_cast<std::uint64_t>(v.phase),
			 v.record_kind_mask,
			 h.admitted_detail,
			 h.admitted_control,
			 h.last_admitted_record_seq,
			 h.applied_records,
			 h.duplicate_records,
			 h.stale_checkpoint_records,
			 h.quarantined_records,
			 h.invalid_records,
			 h.conflict_records,
			 h.dropped_detail,
			 h.dropped_control,
			 h.last_committed_record_seq,
			 h.inflight_first_record_seq,
			 h.inflight_last_record_seq,
			 v.inflight_records,
			 v.unattempted_records,
			 h.queue_depth,
			 h.inflight_active,
			 h.retryable_failures,
			 h.ambiguous_commits,
			 h.sequence_gap_count,
			 h.unclosed_tail_count,
			 static_cast<std::uint64_t>(h.last_failure_class),
			 h.last_error_code,
			 h.last_failure_first_record_seq,
			 h.last_failure_last_record_seq,
			 h.last_failure_record_kind_mask,
			 h.last_success_monotonic_usec,
			 h.last_failure_monotonic_usec,
			 h.circuit_open_count,
			 h.backend == telemetry_storage_backend::posthog ? 3U : 0U,
			 h.last_consumed_record_seq,
			 h.consumed_records };
	}

	bool decode(const words &w, telemetry_outage_observation &v)
	{
		if (w[8] > UINT8_MAX || w[24] > UINT32_MAX || w[25] > UINT32_MAX || w[27] > 1U ||
		    w[32] > static_cast<std::uint64_t>(
				    telemetry_failure_class::permanent_repository) ||
		    w[33] > UINT32_MAX)
			return false;
		v = {};
		v.producer = { w[0], w[1] };
		v.environment_id = w[2];
		v.season_id = w[3];
		v.registered_monotonic_usec = w[4];
		v.registered_utc_usec = std::bit_cast<std::int64_t>(w[5]);
		v.observed_monotonic_usec = w[6];
		v.observed_utc_usec = std::bit_cast<std::int64_t>(w[7]);
		v.phase = static_cast<telemetry_outage_phase>(w[8]);
		v.record_kind_mask = w[9];
		auto &h = v.health;
		h.producer = v.producer;
		h.schema_version = TELEMETRY_SCHEMA_VERSION;
		h.backend = telemetry_storage_backend::sql;
		h.admitted_detail = w[10];
		h.admitted_control = w[11];
		h.last_admitted_record_seq = w[12];
		h.applied_records = w[13];
		h.duplicate_records = w[14];
		h.stale_checkpoint_records = w[15];
		h.quarantined_records = w[16];
		h.invalid_records = w[17];
		h.conflict_records = w[18];
		h.dropped_detail = w[19];
		h.dropped_control = w[20];
		h.last_committed_record_seq = w[21];
		h.inflight_first_record_seq = w[22];
		h.inflight_last_record_seq = w[23];
		v.inflight_records = static_cast<std::uint32_t>(w[24]);
		v.unattempted_records = static_cast<std::uint32_t>(w[25]);
		h.queue_depth = w[26];
		h.inflight_active = static_cast<std::uint8_t>(w[27]);
		h.retryable_failures = w[28];
		h.ambiguous_commits = w[29];
		h.sequence_gap_count = w[30];
		h.unclosed_tail_count = w[31];
		h.last_failure_class = static_cast<telemetry_failure_class>(w[32]);
		h.last_error_code = static_cast<std::uint32_t>(w[33]);
		h.last_failure_first_record_seq = w[34];
		h.last_failure_last_record_seq = w[35];
		h.last_failure_record_kind_mask = w[36];
		h.last_success_monotonic_usec = w[37];
		h.last_failure_monotonic_usec = w[38];
		h.circuit_open_count = w[39];
		if (w[40] != 0U && w[40] != 3U)
			return false;
		if (w[40] == 3U)
			h.backend = telemetry_storage_backend::posthog;
		h.last_consumed_record_seq = w[41];
		h.consumed_records = w[42];
		return valid(v);
	}

	void append_word(std::vector<unsigned char> & data, std::uint64_t value)
	{
		for (unsigned int shift = 64U; shift != 0U; shift -= 8U)
			data.push_back(static_cast<unsigned char>(value >> (shift - 8U)));
	}

	std::uint64_t read_word(const unsigned char *data)
	{
		std::uint64_t value = 0U;
		for (unsigned int index = 0U; index < 8U; ++index)
			value = (value << 8U) | data[index];
		return value;
	}

	using quota_words = std::array<std::uint64_t, TELEMETRY_OUTAGE_QUOTA_WORDS>;

	bool binding_valid(const telemetry_quota_binding &b)
	{
		return b.project_id != 0U && b.sender_id != 0U && b.environment_id != 0U &&
		       b.season_id != 0U && b.total_limit > 0U && b.total_limit <= 20'000U &&
		       b.normal_limit <= b.total_limit && b.health_limit <= 100U &&
		       b.health_limit <= b.total_limit &&
		       (b.normal_limit != 0U || b.health_limit != 0U);
	}

	quota_words encode_quota(const telemetry_quota_state &q)
	{
		const auto &b = q.binding;
		return { b.project_id,	    b.sender_id,
			 b.environment_id,  b.season_id,
			 b.normal_limit,    b.health_limit,
			 b.total_limit,	    std::bit_cast<std::uint64_t>(q.day),
			 q.normal_reserved, q.health_reserved };
	}

	bool decode_quota(const quota_words &w, telemetry_quota_state &q)
	{
		if (w[4] > 20'000U || w[5] > 100U || w[6] > 20'000U || w[8] > 20'000U ||
		    w[9] > 100U)
			return false;
		q.binding = { w[0],
			      w[1],
			      w[2],
			      w[3],
			      static_cast<std::uint32_t>(w[4]),
			      static_cast<std::uint32_t>(w[5]),
			      static_cast<std::uint32_t>(w[6]) };
		q.day = std::bit_cast<std::int64_t>(w[7]);
		q.normal_reserved = static_cast<std::uint32_t>(w[8]);
		q.health_reserved = static_cast<std::uint32_t>(w[9]);
		return binding_valid(q.binding) && q.day >= -719162 && q.day <= 2932896 &&
		       q.normal_reserved <= q.binding.normal_limit &&
		       q.health_reserved <= q.binding.health_limit &&
		       q.normal_reserved + q.health_reserved <= q.binding.total_limit;
	}

	bool quota_extends(const telemetry_quota_state &previous, const telemetry_quota_state &next)
	{
		const auto left = encode_quota(previous);
		const auto right = encode_quota(next);
		return std::equal(left.begin(), left.begin() + 7U, right.begin()) &&
		       next.day >= previous.day &&
		       (next.day > previous.day ||
			(next.normal_reserved >= previous.normal_reserved &&
			 next.health_reserved >= previous.health_reserved));
	}

	bool marker_matches(const std::array<unsigned char, 48U> &marker,
			    const telemetry_outage_journal &j)
	{
		return std::memcmp(marker.data(), MARKER_MAGIC, sizeof(MARKER_MAGIC)) == 0 &&
		       read_word(marker.data() + 8U) == j.generation &&
		       std::memcmp(marker.data() + 16U, j.digest.data(), j.digest.size()) == 0;
	}

	bool write_marker(telemetry_outage_journal & j, std::uint64_t generation,
			  const unsigned char *digest)
	{
		std::vector<unsigned char> marker(std::begin(MARKER_MAGIC), std::end(MARKER_MAGIC));
		append_word(marker, generation);
		marker.insert(marker.end(), digest, digest + SHA256_DIGEST_LENGTH);
		std::size_t offset = 0U;
		while (offset < marker.size())
		{
			const auto written = pwrite(j.ownership_fd, marker.data() + offset,
						    marker.size() - offset,
						    static_cast<off_t>(offset));
			if (written < 0 && errno == EINTR)
				continue;
			if (written <= 0)
			{
				if (written == 0)
					errno = EIO;
				return false;
			}
			offset += static_cast<std::size_t>(written);
		}
		return fsync(j.ownership_fd) == 0;
	}

	bool safe_file(int fd, struct stat &status)
	{
		return fstat(fd, &status) == 0 && S_ISREG(status.st_mode) &&
		       status.st_uid == geteuid() && (status.st_mode & 07777U) == 0600U &&
		       status.st_nlink == 1U;
	}

	/* A frame that is not whole, short or with a digest that does not match, is an
 * interrupted write and reports ENODATA; a whole frame whose content does not
 * decode reports EBADMSG. */
	telemetry_outage_result load(telemetry_outage_journal & j, const char *name, bool &present)
	{
		present = false;
		const int fd = openat(j.directory_fd, name, O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
		if (fd < 0)
			return errno == ENOENT ?
				       telemetry_outage_result::ready :
				       failure(j, telemetry_outage_result::io_failure, errno);
		present = true;
		file_guard guard{ fd };
		struct stat status{};
		if (!safe_file(fd, status))
		{
			return failure(j, telemetry_outage_result::unsafe_storage, EPERM);
		}
		if (status.st_size < 64 ||
		    static_cast<std::uint64_t>(status.st_size) > TELEMETRY_OUTAGE_MAX_BYTES)
		{
			return failure(j, telemetry_outage_result::corrupt, ENODATA);
		}
		std::vector<unsigned char> data(static_cast<std::size_t>(status.st_size));
		std::size_t offset = 0U;
		while (offset < data.size())
		{
			const auto received = read(fd, data.data() + offset, data.size() - offset);
			if (received < 0 && errno == EINTR)
				continue;
			if (received <= 0)
			{
				const int error = received == 0 ? EBADMSG : errno;
				return failure(j, telemetry_outage_result::io_failure, error);
			}
			offset += static_cast<std::size_t>(received);
		}
		unsigned char digest[SHA256_DIGEST_LENGTH]{};
		if (SHA256(data.data(), data.size() - sizeof(digest), digest) == nullptr)
			return failure(j, telemetry_outage_result::io_failure, EIO);
		const bool posthog_frame =
			std::memcmp(data.data(), POSTHOG_MAGIC, sizeof(POSTHOG_MAGIC)) == 0;
		const bool quota_frame =
			std::memcmp(data.data(), QUOTA_MAGIC, sizeof(QUOTA_MAGIC)) == 0 ||
			(posthog_frame &&
			 read_word(data.data() + 24U) == TELEMETRY_OUTAGE_QUOTA_WORDS);
		const auto disk_words = posthog_frame ? TELEMETRY_OUTAGE_POSTHOG_WORDS :
							TELEMETRY_OUTAGE_DISK_WORDS;
		if ((!quota_frame && !posthog_frame &&
		     std::memcmp(data.data(), MAGIC, sizeof(MAGIC)) != 0) ||
		    std::memcmp(data.data() + data.size() - sizeof(digest), digest,
				sizeof(digest)) != 0)
			return failure(j, telemetry_outage_result::corrupt, ENODATA);
		const auto generation = read_word(data.data() + 8U);
		const auto count = read_word(data.data() + 16U);
		const auto extra = quota_frame ? TELEMETRY_OUTAGE_QUOTA_WORDS : 0U;
		if (generation == 0U || (!quota_frame && count == 0U) ||
		    count > TELEMETRY_OUTAGE_MAX_PRODUCERS ||
		    read_word(data.data() + 24U) != extra ||
		    data.size() != 64U + extra * 8U + count * disk_words * 8U)
			return failure(j, telemetry_outage_result::corrupt, EBADMSG);
		j.quota = {};
		if (quota_frame)
		{
			quota_words fields{};
			for (std::size_t index = 0U; index < fields.size(); ++index)
				fields[index] = read_word(data.data() + 32U + index * 8U);
			if (!decode_quota(fields, j.quota))
				return failure(j, telemetry_outage_result::corrupt, EBADMSG);
		}
		for (std::size_t index = 0U; index < count; ++index)
		{
			words fields{};
			for (std::size_t field = 0U; field < disk_words; ++field)
				fields[field] = read_word(data.data() + 32U + extra * 8U +
							  (index * disk_words + field) * 8U);
			if (!decode(fields, j.observations[index]) ||
			    (index + 1U < count &&
			     j.observations[index].phase == telemetry_outage_phase::running))
				return failure(j, telemetry_outage_result::corrupt, EBADMSG);
			for (std::size_t previous = 0U; previous < index; ++previous)
				if (same_producer(j.observations[index].producer,
						  j.observations[previous].producer))
					return failure(j, telemetry_outage_result::corrupt,
						       EBADMSG);
		}
		j.generation = generation;
		j.count = static_cast<std::size_t>(count);
		std::copy(std::begin(digest), std::end(digest), j.digest.begin());
		return telemetry_outage_result::ready;
	}

	std::vector<unsigned char> frame(const telemetry_outage_journal &j,
					 std::uint64_t generation)
	{
		const bool quota = j.quota.binding.project_id != 0U;
		const bool posthog = std::any_of(j.observations.begin(),
						 j.observations.begin() + j.count,
						 [](const auto &observation)
						 {
							 return observation.health.backend ==
								telemetry_storage_backend::posthog;
						 });
		const auto disk_words = posthog ? TELEMETRY_OUTAGE_POSTHOG_WORDS :
						  TELEMETRY_OUTAGE_DISK_WORDS;
		const auto *magic = posthog ? POSTHOG_MAGIC : quota ? QUOTA_MAGIC : MAGIC;
		std::vector<unsigned char> data(magic, magic + sizeof(MAGIC));
		data.reserve(64U + (quota ? TELEMETRY_OUTAGE_QUOTA_WORDS * 8U : 0U) +
			     j.count * disk_words * 8U);
		append_word(data, generation);
		append_word(data, j.count);
		append_word(data, quota ? TELEMETRY_OUTAGE_QUOTA_WORDS : 0U);
		if (quota)
			for (const auto value : encode_quota(j.quota))
				append_word(data, value);
		for (std::size_t index = 0U; index < j.count; ++index)
		{
			const auto fields = encode(j.observations[index]);
			for (std::size_t field = 0U; field < disk_words; ++field)
				append_word(data, fields[field]);
		}
		unsigned char digest[SHA256_DIGEST_LENGTH]{};
		if (SHA256(data.data(), data.size(), digest) == nullptr)
			throw std::bad_alloc();
		data.insert(data.end(), std::begin(digest), std::end(digest));
		return data;
	}

	telemetry_outage_result write_new(telemetry_outage_journal & j, const char *name,
					  const std::vector<unsigned char> &data)
	{
		const int fd = openat(j.directory_fd, name,
				      O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC | O_NOFOLLOW, 0600);
		if (fd < 0)
			return failure(j, telemetry_outage_result::io_failure, errno);
		int error = 0;
		std::size_t offset = 0U;
		while (error == 0 && offset < data.size())
		{
			const auto written = write(fd, data.data() + offset, data.size() - offset);
			if (written < 0 && errno == EINTR)
				continue;
			if (written <= 0)
				error = written == 0 ? EIO : errno;
			else
				offset += static_cast<std::size_t>(written);
		}
		if (error == 0 && fsync(fd) != 0)
			error = errno;
		if (close(fd) != 0 && error == 0)
			error = errno;
		if (error != 0)
		{
			(void)unlinkat(j.directory_fd, name, 0);
			return failure(j, telemetry_outage_result::io_failure, error);
		}
		return telemetry_outage_result::ready;
	}

	telemetry_outage_result persist(telemetry_outage_journal & j)
	{
		struct stat directory = {};
		struct stat owner = {};
		struct stat linked_owner = {};
		struct stat ledger = {};
		if (fstat(j.directory_fd, &directory) != 0 || directory.st_uid != geteuid() ||
		    (directory.st_mode & 07777U) != 0700U || !safe_file(j.ownership_fd, owner) ||
		    (owner.st_size != 0 && owner.st_size != 48) ||
		    fstatat(j.directory_fd, LOCK, &linked_owner, AT_SYMLINK_NOFOLLOW) != 0 ||
		    linked_owner.st_dev != owner.st_dev || linked_owner.st_ino != owner.st_ino)
			return failure(j, telemetry_outage_result::unsafe_storage, EPERM);
		if (fstatat(j.directory_fd, LEDGER, &ledger, AT_SYMLINK_NOFOLLOW) == 0)
		{
			if (!S_ISREG(ledger.st_mode) || ledger.st_uid != geteuid() ||
			    (ledger.st_mode & 07777U) != 0600U || ledger.st_nlink != 1U)
				return failure(j, telemetry_outage_result::unsafe_storage, EPERM);
		}
		else if (errno != ENOENT || j.generation != 0U)
			return failure(j, telemetry_outage_result::unsafe_storage, errno);
		if (j.quota_poisoned)
			return failure(j, telemetry_outage_result::corrupt, EBADMSG);
		if (j.quota_marker && owner.st_size != 48)
			return failure(j, telemetry_outage_result::corrupt, EBADMSG);
		if (j.quota.binding.project_id != 0U && owner.st_size != 0)
		{
			std::array<unsigned char, 48U> marker{};
			if (pread(j.ownership_fd, marker.data(), marker.size(), 0) !=
				    static_cast<ssize_t>(marker.size()) ||
			    !marker_matches(marker, j))
				return failure(j, telemetry_outage_result::corrupt, EBADMSG);
		}
		if (j.generation == UINT64_MAX)
			return failure(j, telemetry_outage_result::io_failure, EOVERFLOW);
		const auto data = frame(j, j.generation + 1U);
		const auto written = write_new(j, PENDING, data);
		if (written != telemetry_outage_result::ready)
			return written;
		const auto *digest = data.data() + data.size() - SHA256_DIGEST_LENGTH;
		if (j.quota.binding.project_id != 0U && !write_marker(j, j.generation + 1U, digest))
			return failure(j, telemetry_outage_result::io_failure,
				       errno != 0 ? errno : EIO);
		if (renameat(j.directory_fd, PENDING, j.directory_fd, LEDGER) != 0 ||
		    fsync(j.directory_fd) != 0)
			return failure(j, telemetry_outage_result::io_failure, errno);
		++j.generation;
		j.quota_marker = j.quota.binding.project_id != 0U;
		std::copy(digest, digest + SHA256_DIGEST_LENGTH, j.digest.begin());
		j.error_code = 0U;
		return telemetry_outage_result::ready;
	}

	telemetry_outage_result preserve_frame(telemetry_outage_journal & j, const char *name)
	{
		telemetry_outage_journal existing{};
		existing.directory_fd = j.directory_fd;
		bool present = false;
		const auto loaded = load(existing, name, present);
		if (loaded != telemetry_outage_result::ready)
			return failure(j, loaded, static_cast<int>(existing.error_code));
		if (present)
			return existing.generation == j.generation && existing.digest == j.digest ?
				       telemetry_outage_result::ready :
				       failure(j, telemetry_outage_result::unsafe_storage, EEXIST);
		const auto written = write_new(j, name, frame(j, j.generation));
		if (written != telemetry_outage_result::ready)
			return written;
		return fsync(j.directory_fd) == 0 ?
			       telemetry_outage_result::ready :
			       failure(j, telemetry_outage_result::io_failure, errno);
	}

	/* A full ledger is published once more, with its last running phase closed by
 * the caller, then kept as outages.ledger.<registered utc>.<generation>; the
 * chain starts again with the new registration as its only entry. */
	telemetry_outage_result archive(telemetry_outage_journal & j,
					const telemetry_outage_observation &registration)
	{
		const auto published = persist(j);
		if (published != telemetry_outage_result::ready)
			return published;
		std::array<char, 80U> name{};
		const auto stamp =
			registration.registered_utc_usec != TELEMETRY_UTC_UNKNOWN ?
				registration.registered_utc_usec :
				static_cast<std::int64_t>(registration.registered_monotonic_usec);
		std::snprintf(name.data(), name.size(), "%s.%lld.%llu", LEDGER,
			      static_cast<long long>(stamp),
			      static_cast<unsigned long long>(j.generation));
		struct stat existing{};
		if (fstatat(j.directory_fd, name.data(), &existing, AT_SYMLINK_NOFOLLOW) == 0)
			return failure(j, telemetry_outage_result::unsafe_storage, EEXIST);
		if (errno != ENOENT)
			return failure(j, telemetry_outage_result::io_failure, errno);
		if (j.quota.binding.project_id != 0U)
		{
			const auto preserved = preserve_frame(j, name.data());
			if (preserved != telemetry_outage_result::ready)
				return preserved;
		}
		else
		{
			if (renameat(j.directory_fd, LEDGER, j.directory_fd, name.data()) != 0 ||
			    fsync(j.directory_fd) != 0)
				return failure(j, telemetry_outage_result::io_failure, errno);
			j.generation = 0U;
		}
		j.count = 0U;
		return telemetry_outage_result::ready;
	}

	bool archived_rotation(telemetry_outage_journal & j, const telemetry_outage_journal &staged)
	{
		if (j.quota.binding.project_id == 0U || j.count != TELEMETRY_OUTAGE_MAX_PRODUCERS ||
		    staged.count != 1U || !registration_is_empty(staged.observations[0]))
			return false;
		const auto &registration = staged.observations[0];
		for (const auto &observation : j.observations)
			if (observation.phase == telemetry_outage_phase::running ||
			    same_producer(observation.producer, registration.producer))
				return false;
		std::array<char, 80U> name{};
		const auto stamp =
			registration.registered_utc_usec != TELEMETRY_UTC_UNKNOWN ?
				registration.registered_utc_usec :
				static_cast<std::int64_t>(registration.registered_monotonic_usec);
		std::snprintf(name.data(), name.size(), "%s.%lld.%llu", LEDGER,
			      static_cast<long long>(stamp),
			      static_cast<unsigned long long>(j.generation));
		telemetry_outage_journal archived{};
		archived.directory_fd = j.directory_fd;
		bool present = false;
		return load(archived, name.data(), present) == telemetry_outage_result::ready &&
		       present && archived.generation == j.generation &&
		       archived.digest == j.digest;
	}

	telemetry_outage_result acquire(telemetry_outage_journal & j, const char *directory)
	{
		if (!directory || directory[0] != '/' || j.directory_fd >= 0 || j.ownership_fd >= 0)
			return failure(j, telemetry_outage_result::invalid, EINVAL);
		std::array<char, 4096U> path{};
		auto length = strnlen(directory, path.size());
		if (length == path.size())
			return failure(j, telemetry_outage_result::invalid, ENAMETOOLONG);
		std::memcpy(path.data(), directory, length);
		// A trailing slash otherwise makes O_NOFOLLOW follow a directory symlink.
		while (length > 1U && path[length - 1U] == '/')
			path[--length] = '\0';
		j.directory_fd = open(path.data(), O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW);
		if (j.directory_fd < 0)
			return failure(j, telemetry_outage_result::io_failure, errno);
		struct stat status{};
		if (fstat(j.directory_fd, &status) != 0 || !S_ISDIR(status.st_mode) ||
		    status.st_uid != geteuid() || (status.st_mode & 07777U) != 0700U)
			return failure(j, telemetry_outage_result::unsafe_storage, EPERM);
		j.ownership_fd = openat(j.directory_fd, LOCK,
					O_RDWR | O_CREAT | O_CLOEXEC | O_NOFOLLOW, 0600);
		if (j.ownership_fd < 0)
			return failure(j, telemetry_outage_result::io_failure, errno);
		if (!safe_file(j.ownership_fd, status) ||
		    (status.st_size != 0 && status.st_size != 48))
			return failure(j, telemetry_outage_result::unsafe_storage, EPERM);
		if (flock(j.ownership_fd, LOCK_EX | LOCK_NB) != 0)
			return failure(j, telemetry_outage_result::owned_elsewhere, errno);
		const bool has_marker = status.st_size == 48;
		j.quota_marker = has_marker;
		std::array<unsigned char, 48U> marker{};
		if (has_marker &&
		    (pread(j.ownership_fd, marker.data(), marker.size(), 0) !=
			     static_cast<ssize_t>(marker.size()) ||
		     std::memcmp(marker.data(), MARKER_MAGIC, sizeof(MARKER_MAGIC)) != 0))
			return failure(j, telemetry_outage_result::corrupt, EBADMSG);
		j.count = 0U;
		j.generation = 0U;
		j.current = TELEMETRY_OUTAGE_MAX_PRODUCERS;
		j.quota = {};
		j.digest.fill(0U);
		j.quota_poisoned = false;
		bool present = false;
		auto result = load(j, LEDGER, present);
		if (result != telemetry_outage_result::ready)
			return result;
		telemetry_outage_journal staged{};
		staged.directory_fd = j.directory_fd;
		bool pending = false;
		result = load(staged, PENDING, pending);
		/* The marker independently detects restoring only the ledger, including
	 * a same-generation replacement. A whole pending frame may match it. */
		if ((j.quota.binding.project_id != 0U && !has_marker) ||
		    (has_marker && !marker_matches(marker, j) &&
		     !(pending && result == telemetry_outage_result::ready &&
		       marker_matches(marker, staged))))
			return failure(j, telemetry_outage_result::corrupt, EBADMSG);
		if (result == telemetry_outage_result::corrupt && staged.error_code == ENODATA)
		{
			// An interrupted write left a pending file that is not a whole frame. It
			// never became the ledger and holds nothing the ledger lacks: remove it.
			if ((unlinkat(j.directory_fd, PENDING, 0) != 0 && errno != ENOENT) ||
			    fsync(j.directory_fd) != 0)
				return failure(j, telemetry_outage_result::io_failure, errno);
			result = telemetry_outage_result::ready;
			pending = false;
		}
		if (result != telemetry_outage_result::ready)
			return failure(j, result, static_cast<int>(staged.error_code));
		if (pending)
		{
			const bool rotation = archived_rotation(j, staged);
			// A whole pending publication may only extend this exact chain; one that
			// decodes but does not is kept and refuses admission.
			if (j.generation == UINT64_MAX || staged.generation != j.generation + 1U ||
			    (!rotation && (staged.count < j.count || staged.count > j.count + 1U)))
				return failure(j, telemetry_outage_result::corrupt, EBADMSG);
			if (j.quota.binding.project_id != 0U &&
			    !quota_extends(j.quota, staged.quota))
				return failure(j, telemetry_outage_result::corrupt, EBADMSG);
			for (std::size_t index = 0U; !rotation && index < j.count; ++index)
			{
				if (!extends(j.observations[index], staged.observations[index]))
					return failure(j, telemetry_outage_result::corrupt,
						       EBADMSG);
				if (staged.count > j.count &&
				    j.observations[index].phase == telemetry_outage_phase::running)
				{
					auto expected = j.observations[index];
					expected.phase = telemetry_outage_phase::unknown_tail;
					if (encode(expected) != encode(staged.observations[index]))
						return failure(j, telemetry_outage_result::corrupt,
							       EBADMSG);
				}
			}
			if (staged.count > j.count &&
			    !registration_is_empty(staged.observations[j.count]))
				return failure(j, telemetry_outage_result::corrupt, EBADMSG);
			const int pending_fd =
				openat(j.directory_fd, PENDING, O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
			if (pending_fd < 0)
				return failure(j, telemetry_outage_result::io_failure, errno);
			file_guard pending_guard{ pending_fd };
			if (!safe_file(pending_fd, status))
				return failure(j, telemetry_outage_result::unsafe_storage, EPERM);
			if (staged.quota.binding.project_id != 0U &&
			    !write_marker(j, staged.generation, staged.digest.data()))
				return failure(j, telemetry_outage_result::io_failure, errno);
			if (fsync(pending_fd) != 0 ||
			    renameat(j.directory_fd, PENDING, j.directory_fd, LEDGER) != 0 ||
			    fsync(j.directory_fd) != 0)
				return failure(j, telemetry_outage_result::io_failure, errno);
			j.generation = staged.generation;
			j.count = staged.count;
			j.observations = staged.observations;
			j.quota = staged.quota;
			j.digest = staged.digest;
			j.quota_marker = staged.quota.binding.project_id != 0U;
		}
		j.error_code = 0U;
		return telemetry_outage_result::ready;
	}
} // namespace

telemetry_outage_phase
telemetry_outage_terminal_phase(const telemetry_outage_observation &observation) noexcept
{
	if (clean(observation))
		return telemetry_outage_phase::clean_drained;
	if (observation.inflight_records == 0U && observation.unattempted_records != 0U)
		return telemetry_outage_phase::abandoned;
	return telemetry_outage_phase::unknown_tail;
}

void telemetry_outage_close(telemetry_outage_journal *journal) noexcept
{
	if (!journal)
		return;
	if (journal->ownership_fd >= 0)
		close(journal->ownership_fd);
	if (journal->directory_fd >= 0)
		close(journal->directory_fd);
	journal->ownership_fd = -1;
	journal->directory_fd = -1;
	journal->current = TELEMETRY_OUTAGE_MAX_PRODUCERS;
}

telemetry_outage_result telemetry_outage_read(telemetry_outage_journal *journal,
					      const char *directory) noexcept
{
	if (!journal || journal->directory_fd >= 0 || journal->ownership_fd >= 0)
		return telemetry_outage_result::invalid;
	telemetry_outage_result result;
	try
	{
		result = acquire(*journal, directory);
	}
	catch(...)
	{
		result = failure(*journal, telemetry_outage_result::io_failure, ENOMEM);
	}
	if (result != telemetry_outage_result::ready)
		telemetry_outage_close(journal);
	return result;
}

telemetry_outage_result
telemetry_outage_open(telemetry_outage_journal *journal, const char *directory,
		      const telemetry_outage_observation &registration) noexcept
{
	if (!journal || !registration_is_empty(registration))
		return telemetry_outage_result::invalid;
	auto result = telemetry_outage_read(journal, directory);
	if (result != telemetry_outage_result::ready)
		return result;
	if (journal->quota.binding.project_id != 0U &&
	    (registration.environment_id != journal->quota.binding.environment_id ||
	     registration.season_id != journal->quota.binding.season_id))
	{
		result = failure(*journal, telemetry_outage_result::invalid, EINVAL);
		telemetry_outage_close(journal);
		return result;
	}
	try
	{
		for (std::size_t index = 0U; index < journal->count; ++index)
		{
			if (same_producer(registration.producer,
					  journal->observations[index].producer))
			{
				result =
					failure(*journal, telemetry_outage_result::invalid, EEXIST);
				telemetry_outage_close(journal);
				return result;
			}
			if (journal->observations[index].phase == telemetry_outage_phase::running)
				journal->observations[index].phase =
					telemetry_outage_phase::unknown_tail;
		}
		result = journal->count == TELEMETRY_OUTAGE_MAX_PRODUCERS ?
				 archive(*journal, registration) :
				 telemetry_outage_result::ready;
		if (result == telemetry_outage_result::ready)
		{
			journal->current = journal->count++;
			journal->observations[journal->current] = registration;
			result = persist(*journal);
		}
	}
	catch(...)
	{
		result = failure(*journal, telemetry_outage_result::io_failure, ENOMEM);
	}
	if (result != telemetry_outage_result::ready)
		telemetry_outage_close(journal);
	return result;
}

telemetry_outage_result
telemetry_outage_checkpoint(telemetry_outage_journal *journal,
			    const telemetry_outage_observation &observation) noexcept
{
	if (!journal || journal->directory_fd < 0 || journal->ownership_fd < 0 ||
	    journal->current >= journal->count || !valid(observation))
		return telemetry_outage_result::invalid;
	const auto previous = journal->observations[journal->current];
	if (!extends(previous, observation) || previous.phase != telemetry_outage_phase::running)
		return failure(*journal, telemetry_outage_result::invalid, EINVAL);
	telemetry_outage_result result;
	try
	{
		journal->observations[journal->current] = observation;
		result = persist(*journal);
	}
	catch(...)
	{
		result = failure(*journal, telemetry_outage_result::io_failure, ENOMEM);
	}
	if (result != telemetry_outage_result::ready)
	{
		journal->observations[journal->current] = previous;
		// A failure before the rename left nothing behind; the next sample
		// retries. A pending file still present was written whole and may or
		// may not have been published: reopen and validate before any further
		// mutation, since a retry from this generation could overwrite it.
		struct stat staged{};
		if (fstatat(journal->directory_fd, PENDING, &staged, AT_SYMLINK_NOFOLLOW) == 0)
			journal->current = TELEMETRY_OUTAGE_MAX_PRODUCERS;
	}
	return result;
}

namespace
{
	bool utc_day(telemetry_utc_usec utc, std::int64_t &day)
	{
		if (utc < -62'135'596'800'000'000LL || utc > 253'402'300'799'999'999LL)
			return false;
		constexpr std::int64_t span = 86'400'000'000LL;
		day = utc / span - (utc % span < 0 ? 1 : 0);
		return true;
	}

	telemetry_outage_result publish_quota(telemetry_outage_journal & j,
					      const telemetry_quota_state &next) noexcept
	{
		telemetry_outage_result result;
		try
		{
			j.quota = next;
			result = persist(j);
		}
		catch(...)
		{
			result = failure(j, telemetry_outage_result::io_failure, ENOMEM);
		}
		/* An unsuccessful durable reservation never authorizes HTTP. Stop this
	 * owner rather than guessing which publication reached stable storage. */
		if (result != telemetry_outage_result::ready)
			j.quota_poisoned = true;
		return result;
	}
} // namespace

telemetry_outage_result
telemetry_outage_quota_check(telemetry_outage_journal *journal,
			     const telemetry_quota_binding &binding) noexcept
{
	if (!journal || journal->directory_fd < 0 || journal->ownership_fd < 0 ||
	    !binding_valid(binding))
		return telemetry_outage_result::invalid;
	if (journal->quota_poisoned)
		return failure(*journal, telemetry_outage_result::corrupt, EBADMSG);
	if (journal->quota.binding.project_id == 0U)
		return failure(*journal, telemetry_outage_result::invalid, ENODATA);
	auto expected = journal->quota;
	expected.binding = binding;
	if (encode_quota(expected) != encode_quota(journal->quota))
		return failure(*journal, telemetry_outage_result::invalid, EINVAL);
	return telemetry_outage_result::ready;
}

telemetry_outage_result telemetry_outage_quota_initialize(telemetry_outage_journal *journal,
							  const telemetry_quota_binding &binding,
							  telemetry_utc_usec utc) noexcept
{
	std::int64_t day = 0;
	if (!journal || journal->directory_fd < 0 || journal->ownership_fd < 0 ||
	    !binding_valid(binding) || !utc_day(utc, day))
		return telemetry_outage_result::invalid;
	if (journal->quota.binding.project_id != 0U)
		return failure(*journal, telemetry_outage_result::invalid, EEXIST);
	for (std::size_t index = 0U; index < journal->count; ++index)
		if (journal->observations[index].environment_id != binding.environment_id ||
		    journal->observations[index].season_id != binding.season_id)
			return failure(*journal, telemetry_outage_result::invalid, EINVAL);
	return publish_quota(*journal, { binding, day, 0U, 0U });
}

telemetry_outage_result telemetry_outage_quota_reserve(telemetry_outage_journal *journal,
						       const telemetry_quota_binding &binding,
						       telemetry_utc_usec utc, std::uint32_t normal,
						       std::uint32_t health) noexcept
{
	const auto checked = telemetry_outage_quota_check(journal, binding);
	if (checked != telemetry_outage_result::ready)
		return checked;
	std::int64_t day = 0;
	if (!utc_day(utc, day) || normal > 64U || health > 64U || normal + health == 0U ||
	    normal + health > 64U)
		return failure(*journal, telemetry_outage_result::invalid, EINVAL);
	if (day < journal->quota.day)
		return failure(*journal, telemetry_outage_result::invalid, ERANGE);
	auto next = journal->quota;
	if (day > next.day)
	{
		next.day = day;
		next.normal_reserved = next.health_reserved = 0U;
	}
	if (normal > binding.normal_limit - next.normal_reserved ||
	    health > binding.health_limit - next.health_reserved ||
	    normal + health > binding.total_limit - next.normal_reserved - next.health_reserved)
		return failure(*journal, telemetry_outage_result::invalid, EDQUOT);
	next.normal_reserved += normal;
	next.health_reserved += health;
	return publish_quota(*journal, next);
}

telemetry_outage_result telemetry_outage_quota_exhaust_day(telemetry_outage_journal *journal,
							   const telemetry_quota_binding &binding,
							   telemetry_utc_usec utc) noexcept
{
	const auto checked = telemetry_outage_quota_check(journal, binding);
	if (checked != telemetry_outage_result::ready)
		return checked;
	std::int64_t day = 0;
	if (!utc_day(utc, day))
		return failure(*journal, telemetry_outage_result::invalid, EINVAL);
	if (day < journal->quota.day)
		return failure(*journal, telemetry_outage_result::invalid, ERANGE);
	auto next = journal->quota;
	if (day > next.day)
		next.normal_reserved = next.health_reserved = 0U;
	next.day = day;
	next.normal_reserved =
		std::min(binding.normal_limit, binding.total_limit - next.health_reserved);
	next.health_reserved =
		std::min(binding.health_limit, binding.total_limit - next.normal_reserved);
	try
	{
		std::array<char, 80U> name{};
		std::snprintf(name.data(), name.size(), "%s.recovery.%llu", LEDGER,
			      static_cast<unsigned long long>(journal->generation));
		const auto preserved = preserve_frame(*journal, name.data());
		if (preserved != telemetry_outage_result::ready)
			return preserved;
	}
	catch(...)
	{
		return failure(*journal, telemetry_outage_result::io_failure, ENOMEM);
	}
	return publish_quota(*journal, next);
}
