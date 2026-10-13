// Real artifact stores, cache generation, guild capture and dirty-state polling.
// The writer retains owned SQL and commit receipts; tests decide when each commits.
#include "guild/artifact.c"
#include "guild/assocs.h"
#include "sql/sql_player.h"
#include "kingdom/kingdom_internal.h"
#include <cassert>
#include <cstdarg>
#include <new>
#include <set>
#include <chrono>
#include <limits>
#include <mutex>

extern "C" time_t time(time_t *out)
{
	constexpr time_t now = 1792000000;
	if (out)
		*out = now;
	return now;
}
float get_property(const char *name, double fallback)
{
	return std::string(name) == "artifact.wars.modifier" ? .25f : fallback;
}
P_char find_player_by_pid(int)
{
	return nullptr;
}
P_obj unequip_char(P_char, int, bool)
{
	std::abort();
}
void obj_to_room(P_obj, int)
{
	std::abort();
}
void obj_from_char(P_obj)
{
	std::abort();
}
void nevent_periodic_mark_failure(const char *)
{
	std::abort();
}
void nevent_periodic_retry_after(unsigned long long, const char *)
{
	std::abort();
}
void nevent_periodic_continue_after(unsigned long long)
{
	std::abort();
}
int fill_word(char *)
{
	return 0;
}
// PARSER_BODY

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
	sql_work work = {};
};
static std::vector<job> jobs;
static bool accepting = true;
static size_t cache_writes = 0, cache_invalidations = 0;
static std::function<void(bool, const sql_rows &)> cache_read;
index_data indexes[1] = {};
P_index obj_index = indexes;
char guild_default_titles[ASC_NUM_RANKS][ASC_MAX_STR_RANK] = {};
extern P_Guild guild_list;
kingdom_config kingdom_cfg;

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
bool sql_queue_work_at(persistence_query_site, sql_work work)
{
	if (!accepting)
	{
		errno = ESHUTDOWN;
		return false;
	}
	jobs.push_back({ {}, {}, std::move(work) });
	return true;
}
bool sql_queue_work_at(persistence_query_site, sql_work work,
		       std::shared_ptr<sql_write_receipt> receipt)
{
	if (!accepting)
	{
		errno = ESHUTDOWN;
		return false;
	}
	jobs.push_back({ {}, std::move(receipt), std::move(work) });
	return true;
}
bool sql_queue_at(persistence_query_site, const char *, ...)
{
	return true;
}
char *coins_to_string(int, int, int, int, const char *)
{
	static char text[] = "fixture coins";
	return text;
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
static job *executing = nullptr;
unsigned int sql_execute(MYSQL *connection, const std::string &statement)
{
	if (connection)
		return mysql_real_query(connection, statement.data(), statement.size()) ?
			       mysql_errno(connection) :
			       0;
	assert(executing);
	executing->sql.push_back(statement);
	return 0;
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

// The optional database leg uses the same owned production snapshots. Writer
// scheduling/receipts remain controlled; each job's SQL runs in a real transaction.
static MYSQL *payment_db = nullptr;
static size_t database_next_job = 0;
static void query(const char *statement)
{
	if (sql_execute(payment_db, statement))
	{
		fprintf(stderr, "payment SQL failed: %s\n", mysql_error(payment_db));
		std::abort();
	}
}
static void open_disposable_database()
{
	assert(getenv("TEST_DB_HOST") && getenv("DB_NAME"));
	assert(std::string(getenv("TEST_DB_HOST")) == "127.0.0.1" &&
	       std::string(getenv("DB_HOST")) == "127.0.0.1" &&
	       std::string(getenv("DB_NAME")) == "duris_test" &&
	       std::string(getenv("DB_PORT")) == getenv("TEST_DB_PORT"));
	payment_db = mysql_init(nullptr);
	assert(mysql_real_connect(payment_db, getenv("DB_HOST"), getenv("DB_USER"),
				  getenv("DB_PASSWD"), getenv("DB_NAME"),
				  std::stoul(getenv("DB_PORT")), nullptr, 0));
}
static void saved_payment(long coins, long prestige, long paid, long mineral = 0, long wood = 0)
{
	if (!payment_db)
		return;
	query("SELECT platinum*1000+gold*100+silver*10+copper,prestige,construction,"
	      "upkeep_paid_through,res_mineral,res_wood FROM guilds g "
	      "JOIN kingdom_realms k ON k.assoc_id=g.id WHERE g.id=7");
	MYSQL_RES *result = mysql_store_result(payment_db);
	assert(result);
	MYSQL_ROW row = mysql_fetch_row(result);
	assert(row && std::stol(row[0]) == coins && std::stol(row[1]) == prestige &&
	       std::stol(row[2]) == 20 && std::stol(row[3]) == paid &&
	       std::stol(row[4]) == mineral && std::stol(row[5]) == wood);
	mysql_free_result(result);
}
static void finish(size_t index, bool ok = true)
{
	assert(jobs.at(index).receipt);
	if (payment_db)
	{
		// Preserve writer order, including intervening realm-only jobs.
		for (; database_next_job <= index; ++database_next_job)
		{
			const bool fail = database_next_job == index && !ok;
			if (fail)
				query("CREATE TRIGGER refuse_payment BEFORE UPDATE ON kingdom_realms "
				      "FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='fixture rollback'");
			query("START TRANSACTION");
			auto &j = jobs.at(database_next_job);
			unsigned int error = 0;
			if (j.work)
				error = j.work(payment_db);
			else
				for (const auto &statement : j.sql)
					if ((error = sql_execute(payment_db, statement)))
						break;
			assert(fail ? error == 1644 : error == 0);
			query(error ? "ROLLBACK" : "COMMIT");
			if (fail)
				query("DROP TRIGGER refuse_payment");
		}
	}
	jobs[index].receipt->ok = ok;
	jobs[index].receipt->error_code = ok ? 0 : EIO;
	jobs[index].receipt->finished.store(true, std::memory_order_release);
}
static bool contains(job &j, const std::string &text)
{
	if (j.work && j.sql.empty())
	{
		executing = &j;
		assert(j.work(nullptr) == 0);
		executing = nullptr;
	}
	for (const auto &s : j.sql)
		if (s.find(text) != std::string::npos)
			return true;
	return false;
}

static void payment_cases(Guild *guild)
{
	jobs.clear();
	kingdom_cfg.enabled = true;
	kingdom_realm realm;
	realm.assoc_id = 7;
	realm.realm_id = 1;
	realm.hall_vnum = 100;
	realm.highest_claim = 1;
	realm.upkeep_paid_through = 2000000000;
	kingdom_realms.emplace(7, realm);
	auto &paid = kingdom_realms.at(7);
	if (payment_db)
	{
		query("INSERT INTO kingdom_realms (assoc_id,realm_id,hall_vnum,highest_claim,upkeep_paid_through) "
		      "VALUES(7,1,100,1,2000000000)");
	}
	assert(guild->add_copper(1000));
	assert(guild->save()); // an older pre-payment capture
	assert(guild->sub_copper(125));
	paid.upkeep_paid_through += 3600;
	paid.dirty = true;
	assert(kingdom_persist_payment(guild, paid));
	assert(paid.payment_pending); // admission alone cannot settle the payment
	assert(guild_save_pulse(false) == 1);
	finish(0);
	assert(paid.payment_pending && guild_save_pulse(false) == 1);
	saved_payment(1000, 70, 2000000000);

	assert(contains(jobs[1], ", 70, 20, 0, 8, 7, 5,"));
	assert(contains(jobs[1], "INSERT INTO kingdom_realms") && contains(jobs[1], "2000003600"));
	paid.resources[KRES_MINERAL] = 5;
	paid.dirty = true;
	guild->add_prestige(10); // later reward must keep the unpaid realm paired
	assert(jobs.size() == 3 && contains(jobs[2], ", 80, 20, 0, 8, 7, 5,"));
	assert(contains(jobs[2], "INSERT INTO kingdom_realms"));
	finish(1);
	assert(guild_save_pulse(false) == 1 && paid.payment_pending);
	saved_payment(875, 70, 2000003600);
	finish(2, false);
	assert(guild_save_pulse(false) == 1 && paid.payment_pending && paid.dirty);
	saved_payment(875, 70, 2000003600); // the later reward and resources both rolled back
	const auto held_jobs = jobs.size();
	kingdom_db_flush_dirty();
	assert(jobs.size() == held_jobs); // no realm-only publication after paired failure
	paid.resources[KRES_MINERAL] = 9;
	accepting = false;
	guild->set_prestige(90);
	assert(guild_save_pulse(false) == 1 && paid.payment_pending);
	accepting = true;
	guild_save_pulse(true);
	assert(jobs.size() == held_jobs + 1);
	assert(contains(jobs.back(), ", 90, 20, 0, 8, 7, 5,")); // no second debit
	assert(contains(jobs.back(), "(7,1,100,1,9,0,0,0,2000003600"));
	// A later resource change remains dirty when the earlier pair commits.
	paid.resources[KRES_WOOD] = 7;
	paid.dirty = true;
	finish(jobs.size() - 1);
	assert(guild_save_pulse(false) == 0 && !paid.payment_pending && paid.dirty);
	saved_payment(875, 90, 2000003600, 9);
	kingdom_db_flush_dirty();
	assert(contains(jobs.back(), "(7,1,100,1,9,7,0,0,2000003600"));
	assert(!contains(jobs.back(), "insert into guilds"));
	assert(!paid.dirty);
	assert(guild->sub_copper(25));
	paid.upkeep_paid_through += 3600;
	paid.dirty = true;
	assert(kingdom_persist_payment(guild, paid));
	const auto second_payment = jobs.size() - 1;
	// A member-deletion transaction uses the same public composition seam.
	job member_deletion = { {},
				{},
				kingdom_guild_save_work(7, sql_save_guild_statements(guild)) };
	assert(contains(member_deletion, "insert into guilds") &&
	       contains(member_deletion, "INSERT INTO kingdom_realms"));
	accepting = false;
	guild->set_prestige(91);
	finish(second_payment);
	saved_payment(850, 90, 2000007200, 9, 7);
	assert(guild_save_pulse(false) == 1 && paid.payment_pending);
	accepting = true;
	guild_save_pulse(true);
	assert(contains(jobs.back(), ", 91, 20, 0, 8, 5, 0,"));
	assert(contains(jobs.back(), "2000007200"));
	finish(jobs.size() - 1);
	assert(guild_save_pulse(false) == 0 && !paid.payment_pending);
	saved_payment(850, 91, 2000007200, 9, 7);
	// A supported deployment without the optional roster still commits the pair.
	if (payment_db)
		query("DROP TABLE kingdom_garrison");
	fail_allocation = true;
	assert(!kingdom_persist_payment(guild, paid));
	assert(guild_save_pulse(false) == 1 && paid.payment_pending);
	guild_save_pulse(true);
	const auto old_receipt = jobs.back().receipt;
	// Removing a realm removes its pending state; old ACK cannot settle a new one.
	kingdom_realms.erase(7);
	kingdom_realms.emplace(7, realm);
	auto &replacement = kingdom_realms.at(7);
	assert(!replacement.payment_pending);
	assert(kingdom_persist_payment(guild, replacement));
	finish(jobs.size() - 2);
	assert(guild_save_pulse(false) == 1 && replacement.payment_pending);
	finish(jobs.size() - 1);
	assert(guild_save_pulse(false) == 0 && !replacement.payment_pending);
	saved_payment(850, 91, 2000000000);
	puts("PASS kingdom payment admission/commit boundary, later rewards, rollback and fresh paired retries, late realm changes and recreation");
}

static void artifact_ordering_cases()
{
	artifact_rows.clear();
	artifact_binds.clear();
	jobs.clear();
	database_next_job = 0;
	const time_t now = time(nullptr);
	artifact_update_sql(900, true, ARTIFACT_ON_PC, 42, now + 8000, ARTIFACT_MAJOR);
	artifact_bind_store(900, 42, 0);
	artifact_feed_set_timer(900, now + 8100);
	// Transfer and soul change capture the timer already fed in memory.
	artifact_update_sql(900, true, ARTIFACT_ON_PC, 77, artifact_rows.at(900).timer,
			    ARTIFACT_MAJOR);
	artifact_bind_store(900, 77, 33);
	artifact_feed_set_timer(900, artifact_rows.at(900).timer + 100);
	char_data staff = {};
	staff.player.level = FORGER;
	char extend[] = "add 900 1";
	arti_timer_sql(&staff, extend);
	assert(artifact_rows.at(900).timer == now + 8260);
	artifact_update_sql(901, true, ARTIFACT_ON_PC, 77, now + 10000, ARTIFACT_MAJOR);
	event_artifact_wars_sql(nullptr, nullptr, nullptr, nullptr);
	// One excess major artifact burns one quarter of each remaining timer.
	assert(artifact_rows.at(900).timer == now + 6195);
	assert(artifact_rows.at(901).timer == now + 7500);
	artifact_feed_set_timer(900, artifact_rows.at(900).timer + 100);
	obj_data object = {};
	object.R_num = 0;
	object.extra_flags = ITEM_ARTIFACT;
	assert(remove_owned_artifact_sql(&object, 77));
	assert(artifact_rows.at(900).locType == ARTIFACT_ONCORPSE &&
	       artifact_rows.at(900).location == 77);
	assert(artifact_rows.at(900).timer == now + 6295 && artifact_binds.at(900).owner_pid == -1);
	artifact_update_sql(900, true, ARTIFACT_ON_PC, 88, artifact_rows.at(900).timer,
			    ARTIFACT_MAJOR);
	artifact_bind_store(900, 88, 0);
	artifact_feed_set_timer(900, artifact_rows.at(900).timer + 100);
	artifact_update_sql(900, true, ARTIFACT_ON_PC, 88, now - 1, ARTIFACT_MAJOR);
	assert(artifact_expired(artifact_rows.at(900)));
	assert(remove_owned_artifact_sql(&object, 0));
	assert(!artifact_expired(artifact_rows.at(900)) && !artifact_rows.at(900).owned);
	char number[] = "900";
	arti_clear_sql(&staff, number);
	assert(artifact_rows.at(900).removed);
	artifact_update_sql(900, true, ARTIFACT_ON_PC, 99, now + 9000, ARTIFACT_MAJOR);
	artifact_bind_store(900, 99, 55);
	for (size_t i = 0; i < jobs.size(); ++i)
		finish(i);
	assert(artifact_save_pulse(false) == 0 && artifact_rows.at(900).location == 99);
	if (payment_db)
	{
		artifact_rows.clear();
		artifact_binds.clear();
		for (const char *statement : { ARTIFACT_ROWS_QUERY, ARTIFACT_BINDS_QUERY })
		{
			query(statement);
			MYSQL_RES *result = mysql_store_result(payment_db);
			assert(result);
			while (MYSQL_ROW row = mysql_fetch_row(result))
				artifact_row_read(row);
			mysql_free_result(result);
		}
	}
	assert(artifact_rows.at(900).owned && !artifact_rows.at(900).removed &&
	       artifact_rows.at(900).locType == ARTIFACT_ON_PC &&
	       artifact_rows.at(900).location == 99 && artifact_rows.at(900).timer == now + 9000);
	assert(artifact_binds.at(900).owner_pid == 99 && artifact_binds.at(900).timer == 55);
	assert(artifact_rows.at(901).timer == now + 7500);
	if (payment_db)
	{
		query("SELECT COUNT(*) FROM artifacts a LEFT JOIN artifact_bind b ON b.vnum=a.vnum "
		      "LEFT JOIN artifact_domain_state d ON d.vnum=a.vnum WHERE a.vnum IN(900,901) AND "
		      "(d.vnum IS NULL OR d.owned<>(a.owned='Y') OR d.loc_type<>a.locType OR "
		      "d.location<>a.location OR d.timer_epoch<>UNIX_TIMESTAMP(a.timer) OR "
		      "d.artifact_type<>a.type OR d.bind_owner_pid<>COALESCE(b.owner_pid,0) OR "
		      "d.bind_timer_epoch<>COALESCE(b.timer,0))");
		MYSQL_RES *result = mysql_store_result(payment_db);
		assert(result);
		MYSQL_ROW row = mysql_fetch_row(result);
		assert(row && std::string(row[0]) == "0");
		mysql_free_result(result);
		puts("PASS artifact SQL drain, actual boot-row reload and mirror agreement");
	}
	puts("PASS artifact feed/transfer/soul/extension/wars/corpse/expiry/removal/recreation ordering");
}

int main(int argc, char **argv)
{
	if (argc == 2)
	{
		assert(std::string(argv[1]) == "--mysql");
		open_disposable_database();
		char name[] = "Snapshot fixture";
		auto *guild = new Guild(name, RACEWAR_GOOD, 7, 70, 20, 0, 0);
		guild_list = guild;
		payment_cases(guild);
		indexes[0].virtual_number = 900;
		artifact_ordering_cases();
		mysql_close(payment_db);
		return 0;
	}
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
	payment_cases(guild);
	artifact_ordering_cases();
}
