// Real artifact stores, cache generation, guild capture and dirty-state polling.
// The writer retains owned SQL and commit receipts; tests decide when each commits.
#include "guild/artifact.c"
#include "guild/assocs.h"
#include "sql/sql_player.h"
#include <cassert>
#include <cstdarg>
#include <new>
#include <set>
#include <chrono>
#include <limits>
#include <mutex>

static bool fail_allocation = false;
void *operator new(size_t size)
{
	if (fail_allocation)
	{
		fail_allocation = false;
		throw std::bad_alloc();
	}
	if (void *p = malloc(size))
		return p;
	throw std::bad_alloc();
}
void operator delete(void *p) noexcept
{
	free(p);
}
void operator delete(void *p, size_t) noexcept
{
	free(p);
}

struct job
{
	std::vector<std::string> sql;
	std::shared_ptr<sql_write_receipt> receipt;
};
static std::vector<job> jobs;
static bool accepting = true;
static size_t cache_writes = 0, cache_invalidations = 0;
static std::function<void(bool, const sql_rows &)> cache_read;
index_data indexes[1] = {};
P_index obj_index = indexes;
char guild_default_titles[ASC_NUM_RANKS][ASC_MAX_STR_RANK] = {};
extern P_Guild guild_list;

std::string sql_format(const char *format, ...)
{
	char out[4096];
	va_list args;
	va_start(args, format);
	vsnprintf(out, sizeof(out), format, args);
	va_end(args);
	return out;
}
void send_to_char_f(P_char, const char *, ...) {}
std::string escape_str(const char *value)
{
	return value;
}
int sql_get_player_pid(const char *)
{
	return 42;
}
char *get_player_name_from_pid(int)
{
	return nullptr;
}
bool sql_queue_statements_at(persistence_query_site, std::vector<std::string> sql,
			     std::shared_ptr<sql_write_receipt> receipt)
{
	if (!accepting)
	{
		errno = ESHUTDOWN;
		return false;
	}
	jobs.push_back({ std::move(sql), std::move(receipt) });
	return true;
}
bool sql_queue_statements_at(persistence_query_site site, std::vector<std::string> sql)
{
	return sql_queue_statements_at(site, std::move(sql), {});
}
bool sql_read_at(persistence_query_site, std::string,
		 std::function<void(bool, const sql_rows &)> done)
{
	cache_read = std::move(done);
	return true;
}
static std::function<void(bool, const sql_rows &)> sync_done;
static P_char sync_staff = nullptr;
static bool staff_online = true;
P_char find_character_by_runtime_id(uint64_t id)
{
	return staff_online && sync_staff && sync_staff->runtime_id == id ? sync_staff : nullptr;
}
bool sql_read_work_at(persistence_query_site, sql_read_work_fn,
		      std::function<void(bool, const sql_rows &)> done)
{
	sync_done = std::move(done);
	return true;
}
bool sql_read_work_for_at(persistence_query_site, P_char ch, sql_read_work_fn,
			  std::function<void(P_char, const sql_rows &)> done)
{
	sync_done = [ch, done](bool ok, const sql_rows &rows)
	{
		if (ok && staff_online)
			done(ch, rows);
	};
	return true;
}
unsigned int sql_execute(MYSQL *, const std::string &)
{
	std::abort();
}
unsigned int sql_select(MYSQL *, const std::string &, sql_rows *)
{
	std::abort();
}

bool redis_report_cache_enabled()
{
	return true;
}
bool redis_invalidate_artifact_cache()
{
	++cache_invalidations;
	return true;
}
void redis_cache_artifact_list(int, bool, const char *)
{
	++cache_writes;
}
P_obj read_object(int vnum, int)
{
	assert(vnum == 900);
	auto *obj = new obj_data{};
	obj->extra_flags = ITEM_ARTIFACT;
	obj->R_num = 0;
	return obj;
}
void extract_obj(P_obj obj, int)
{
	delete obj;
}

static std::vector<std::string> diagnostic_records;
bool persistence_log_submit(const char *text)
{
	diagnostic_records.emplace_back(text);
	return true;
}
// PERSISTENCE_REPORTER

// GUILD_SQL_CAPTURE

static void finish(size_t index, bool ok = true)
{
	assert(jobs.at(index).receipt);
	jobs[index].receipt->ok = ok;
	jobs[index].receipt->error_code = ok ? 0 : EIO;
	jobs[index].receipt->finished.store(true, std::memory_order_release);
}
static bool contains(const job &j, const std::string &text)
{
	for (const auto &s : j.sql)
		if (s.find(text) != std::string::npos)
			return true;
	return false;
}

int main()
{
	indexes[0].virtual_number = 900;
	artifact_rows[900] = { true, ARTIFACT_ON_PC, 42, 1000, ARTIFACT_MAJOR };
	artifact_binds[900] = { 42, 0 };
	arti_redis_cache(ARTIFACT_MAJOR, true);
	assert(cache_read);
	artifact_feed_set_timer(900, 1600);
	assert(artifact_rows.at(900).timer == 1600 && artifact_save_pulse(false) == 1);
	assert(contains(jobs[0], "NULLIF(1600, 0)"));
	cache_read(true, {});
	assert(cache_writes == 0); // earlier in-flight read was invalidated
	arti_redis_cache(ARTIFACT_MAJOR, true);
	cache_read(true, {});
	assert(cache_writes == 1);
	artifact_row_store(900, { true, ARTIFACT_ON_PC, 77, 1600, ARTIFACT_MAJOR });
	artifact_bind_store(900, 77, 17);
	assert(jobs.size() == 3);
	finish(0); // old feed committed; current row and soul captures remain dirty
	assert(artifact_save_pulse(false) == 2);
	finish(1);
	finish(2, false);
	assert(artifact_save_pulse(false) == 1);
	accepting = false;
	artifact_bind_store(900, 88, 18);
	assert(artifact_binds.at(900).owner_pid == 88 && artifact_save_pulse(true) == 1);
	// A list read after failed admission still sees old SQL. A later retry must
	// invalidate that in-flight read even though live memory has not changed again.
	arti_redis_cache(ARTIFACT_MAJOR, true);
	accepting = true;
	artifact_save_pulse(true);
	cache_read(true, {});
	assert(cache_writes == 1);
	assert(jobs.size() == 4 && contains(jobs.back(), "VALUES(900,88,18)"));
	finish(3);
	assert(artifact_save_pulse(false) == 0);
	assert(artifact_rows.at(900).location == 77 && artifact_rows.at(900).timer == 1600);
	puts("PASS ordered artifact/soul captures; old ACK cannot clean a newer capture; retry saves current state");

	// Failure while constructing SQL retains the current row and its dirty bit.
	const auto count = jobs.size();
	fail_allocation = true;
	artifact_feed_set_timer(900, 1700);
	assert(!fail_allocation && jobs.size() == count && artifact_save_pulse(false) == 1);
	artifact_save_pulse(true);
	assert(jobs.size() == count + 1 && contains(jobs.back(), "NULLIF(1700, 0)"));
	finish(count);
	assert(artifact_save_pulse(false) == 0);

	// Drive the actual staff clear procedure, including refusal and later retry.
	char_data god = {};
	pc_only_data pc = {};
	god.only.pc = &pc;
	god.player.level = FORGER;
	char number[] = "900";
	accepting = false;
	arti_clear_sql(&god, number);
	int64_t timer = 0, bind = 0;
	int32_t owner = 0;
	assert(!artifact_feed_state(900, &timer, &owner, &bind));
	assert(artifact_save_pulse(false) == 1);
	accepting = true;
	artifact_save_pulse(true);
	const auto deletion = jobs.size() - 1;
	assert(contains(jobs.back(), "DELETE FROM artifact_domain_state WHERE vnum=900"));
	// Recreate before deletion ACK: that ACK belongs to the removed generation.
	artifact_row_store(900, { true, ARTIFACT_ON_PC, 99, 1900, ARTIFACT_MAJOR });
	finish(deletion);
	assert(artifact_save_pulse(false) == 1 && artifact_rows.at(900).location == 99);
	finish(jobs.size() - 1);
	assert(artifact_save_pulse(false) == 0);
	arti_clear_sql(&god, number);
	finish(jobs.size() - 1);
	assert(artifact_save_pulse(false) == 0 && !artifact_rows.count(900));
	puts("PASS allocation failure, actual clear/retry, deletion ACK and recreation");

	// The all-souls write shares one receipt, but a later binding owns a new one.
	artifact_rows.clear();
	artifact_binds.clear();
	jobs.clear();
	artifact_binds[900] = { 42, 10 };
	artifact_binds[901] = { 43, 11 };
	assert(artifact_binds_reset(-1));
	assert(jobs.size() == 1 && artifact_save_pulse(false) == 2);
	assert(contains(jobs[0], "UPDATE artifact_bind SET owner_pid=-1,timer=0"));
	artifact_bind_store(900, 77, 20);
	finish(0);
	assert(artifact_save_pulse(false) == 1);
	assert(artifact_binds.at(900).owner_pid == 77 && artifact_binds.at(901).owner_pid == -1);
	finish(1);
	assert(artifact_save_pulse(false) == 0);
	accepting = false;
	assert(!artifact_binds_reset(-1));
	assert(artifact_save_pulse(false) == 2);
	accepting = true;
	artifact_bind_store(900, 88, 30);
	artifact_save_pulse(true);
	assert(jobs.size() == 4 && contains(jobs[2], "VALUES(900,88,30)") &&
	       contains(jobs[3], "VALUES(901,-1,0)"));
	finish(2);
	finish(3);
	assert(artifact_save_pulse(false) == 0);
	fail_allocation = true;
	assert(!artifact_binds_reset(-1));
	assert(!fail_allocation && artifact_save_pulse(false) == 2);
	artifact_save_pulse(true);
	assert(jobs.size() == 6);
	finish(4);
	finish(5);
	assert(artifact_save_pulse(false) == 0);
	puts("PASS shared soul-reset receipt, later binding, admission and allocation recovery");

	// Failed low-number rows must not starve higher-number rows indefinitely.
	artifact_rows.clear();
	artifact_binds.clear();
	jobs.clear();
	accepting = false;
	for (int i = 1; i <= 12; ++i)
		artifact_row_store(i, { true, ARTIFACT_ON_PC, i, 1000, 1 });
	accepting = true;
	for (int pass = 0; pass < 3; ++pass)
	{
		const size_t before = jobs.size();
		artifact_save_pulse(true);
		assert(jobs.size() == before + 4);
		for (size_t i = before; i < jobs.size(); ++i)
			finish(i, false);
		assert(artifact_save_pulse(false) == 12);
	}
	std::set<int> tried;
	for (const auto &j : jobs)
	{
		const auto pos = j.sql[0].find("VALUES(");
		assert(pos != std::string::npos);
		tried.insert(atoi(j.sql[0].c_str() + pos + 7));
	}
	assert(tried.size() == 12);
	artifact_rows.clear();
	jobs.clear();
	puts("PASS bounded round-robin snapshot retry without starvation");

	// Administrative SQL sync must not hydrate over a later feed/transfer, and
	// its state publication must not depend on the staff connection staying up.
	artifact_rows[900] = { true, ARTIFACT_ON_PC, 42, 1000, ARTIFACT_MAJOR };
	artifact_binds[900] = { 42, 9 };
	pc.pid = 42;
	god.runtime_id = 42;
	sync_staff = &god;
	const sql_rows old_sync = { sql_row{ { "1", "1" } },
				    sql_row{ { "a", "900", "Y", "3", "42", "1000", "1" } },
				    sql_row{ { "b", "900", "42", "9" } } };
	arti_syncdb_sql(&god);
	assert(sync_done);
	artifact_row_store(900, { true, ARTIFACT_ON_PC, 99, 2000, ARTIFACT_MAJOR });
	artifact_bind_store(900, 99, 20);
	finish(0);
	finish(1);
	assert(artifact_save_pulse(false) == 0);
	sync_done(true, old_sync);
	assert(artifact_rows.at(900).timer == 2000 && artifact_rows.at(900).location == 99);
	assert(artifact_binds.at(900).owner_pid == 99 && artifact_save_pulse(false) == 2);
	artifact_save_pulse(true);
	assert(jobs.size() == 4);
	finish(2);
	finish(3);
	assert(artifact_save_pulse(false) == 0);
	const sql_rows fresh_sync = { sql_row{ { "1", "1" } },
				      sql_row{ { "a", "900", "Y", "3", "42", "2000", "1" } },
				      sql_row{ { "b", "900", "42", "21" } } };
	arti_syncdb_sql(&god);
	staff_online = false;
	sync_done(true, fresh_sync);
	assert(artifact_rows.at(900).location == 42 && artifact_rows.at(900).timer == 2000);
	assert(artifact_binds.at(900).owner_pid == 42);
	staff_online = true;
	// A failed current snapshot must drain before SQL can be a repair input.
	accepting = false;
	artifact_feed_set_timer(900, 2100);
	sync_done = {};
	arti_syncdb_sql(&god);
	assert(sync_done);
	sync_done(true, fresh_sync);
	assert(artifact_rows.at(900).timer == 2100 && artifact_save_pulse(false) == 2);
	accepting = true;
	artifact_save_pulse(true);
	finish(jobs.size() - 2);
	finish(jobs.size() - 1);
	assert(artifact_save_pulse(false) == 0);
	arti_syncdb_sql(&god);
	assert(sync_done);
	arti_clear_sql(&god, number);
	finish(jobs.size() - 1);
	artifact_save_pulse(false);
	assert(!artifact_rows.count(900));
	sync_done(true, fresh_sync);
	assert(!artifact_rows.count(900));
	artifact_rows.clear();
	artifact_binds.clear();
	jobs.clear();
	puts("PASS administrative sync: newer state and deletion survive; disconnect does not discard publication; unsaved input retained");

	char name[] = "Snapshot fixture";
	auto *guild = new Guild(name, RACEWAR_GOOD, 7, 100, 11, 0, 0);
	guild_list = guild;
	assert(guild->save());
	assert(contains(jobs.back(), "prestige=VALUES(prestige)") &&
	       contains(jobs.back(), "construction=VALUES(construction)"));
	assert(guild_save_pulse(false) == 1);
	guild->sub_prestige(50);
	guild->set_construction(20);
	assert(jobs.size() == 2);
	finish(0);
	assert(guild_save_pulse(false) == 1);
	finish(1, false);
	assert(guild_save_pulse(false) == 1);
	accepting = false;
	guild->set_prestige(70);
	assert(guild->get_prestige() == 70 && guild_save_pulse(true) == 1);
	accepting = true;
	guild_save_pulse(true);
	assert(contains(jobs.back(), "'Snapshot fixture'") && contains(jobs.back(), ", 70, 20,"));
	finish(jobs.size() - 1);
	assert(guild_save_pulse(false) == 0);
	fail_allocation = true;
	assert(!guild->save());
	assert(guild_save_pulse(false) == 1);
	guild_save_pulse(true);
	finish(jobs.size() - 1);
	assert(guild_save_pulse(false) == 0);
	const auto recorded = [](const std::string &text)
	{
		return std::any_of(diagnostic_records.begin(), diagnostic_records.end(),
				   [&text](const auto &record)
				   { return record.find(text) != std::string::npos; });
	};
	assert(recorded(
		"domain=artifact_snapshot/admission_failed/soul action=writer_stopped outcome=alert detail=vnum=900 error=" +
		std::to_string(ESHUTDOWN)));
	assert(recorded(
		"domain=guild_snapshot/admission_failed action=allocation_failure outcome=alert detail=guild_id=7 error=" +
		std::to_string(ENOMEM)));
	puts("PASS real guild capture, spending/settings, current-state retry and exact-capture ACK; snapshot diagnostics survive the real reporter");
}
