// Include the actual runtime to drive its writer seam and retry deadline without
// adding a gameplay clock command or a production-only testing interface.
#include "combat/frag_cap_runtime.c"

#include <cassert>
#include <filesystem>
#include <iostream>

namespace
{
// The frag_cap row, held in memory behind the SQL repository interface.
frag_cap_state stored;
bool row_exists = false;
frag_cap_store_result load_result = frag_cap_store_result::ok;
persistence_job_write_fn queued_read;
bool refuse_read = false;
std::vector<std::string> announcements;
constexpr int64_t start = INT64_C(1800000000000000);

void write(const frag_cap_state &state)
{
	stored = state;
	row_exists = true;
	load_result = frag_cap_store_result::ok;
}

void corrupt()
{
	load_result = frag_cap_store_result::invalid;
}

void tick(int64_t now)
{
	auto settled = stored;
	assert(frag_cap_settle(&settled, now));
	write(settled);
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

MYSQL *DB = nullptr;
extern "C"
{
	int STDCALL mysql_query(MYSQL *, const char *)
	{
		return 0;
	}
	unsigned int STDCALL mysql_errno(MYSQL *)
	{
		return 0;
	}
	MYSQL *sql_pool_acquire(void)
	{
		return reinterpret_cast<MYSQL *>(&stored);
	}
	MYSQL *sql_pool_replace_connection(MYSQL *connection)
	{
		return connection;
	}
	void sql_pool_release(MYSQL *) {}
}
frag_cap_store_result frag_cap_sql_load(MYSQL *, frag_cap_state *state, bool)
{
	if (load_result != frag_cap_store_result::ok)
		return load_result;
	if (!row_exists)
		return frag_cap_store_result::not_found;
	*state = stored;
	return frag_cap_store_result::ok;
}
frag_cap_store_result frag_cap_sql_save(MYSQL *, const frag_cap_state &state)
{
	write(state);
	return frag_cap_store_result::ok;
}
frag_cap_store_result frag_cap_sql_adopt(MYSQL *connection, int legacy_floor, int, int64_t now,
					 frag_cap_state *state, const frag_cap_policy &policy)
{
	const auto loaded = frag_cap_sql_load(connection, state, true);
	if (loaded != frag_cap_store_result::not_found)
		return loaded;
	assert(frag_cap_adopt(state, legacy_floor, 0, now, policy));
	write(*state);
	return frag_cap_store_result::ok;
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

int main()
{
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
	corrupt();
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
	tick(start + 72 * FRAG_CAP_HOUR);
	refresh();
	refresh();
	assert(announcements.size() == 1 &&
	       announcements[0].find("Good cap: 32. Evil cap: 31") != std::string::npos);
	assert(frag_cap_runtime_status(1, start + 72 * FRAG_CAP_HOUR).find("Your normal cap: 32") !=
	       std::string::npos);
	assert(frag_cap_runtime_status(2, start + 72 * FRAG_CAP_HOUR).find("Your normal cap: 31") !=
	       std::string::npos);
	tick(start + 216 * FRAG_CAP_HOUR);
	assert(frag_cap_runtime_boot(start + 216 * FRAG_CAP_HOUR));
	assert(frag_cap_runtime_state()->level == 34 && announcements.size() == 1);
	corrupt();
	assert(!frag_cap_runtime_boot(start + 216 * FRAG_CAP_HOUR));
	std::cout
		<< "PASS cap publication: coalesced reads, viewer isolation, older revisions, failed reads, boot recovery and one announcement\n";
}
