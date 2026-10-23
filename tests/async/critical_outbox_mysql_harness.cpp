#include "persistence/critical_outbox.h"
#include "world/epic_command.h"

#include <algorithm>
#include <array>
#include <cassert>
#include <atomic>
#include <cerrno>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <mysql.h>
#include <openssl/sha.h>
#include <future>
#include <mutex>
#include <string>
#include <thread>

static MYSQL *database_connection = nullptr;
static MYSQL *worker_connection = nullptr;
static std::atomic<bool> pool_available = true;
static std::atomic<bool> fail_counts = false, fail_audit = false, fail_observation = false;
static std::atomic<bool> disconnect_counts = false;
static std::atomic<bool> lose_commit_ack = false;
static std::atomic<unsigned int> audits = 0, fetches = 0, observations = 0, replacements = 0;
static std::mutex query_mutex;
static std::string counts_sql;

static MYSQL *connect_database()
{
	MYSQL *connection = mysql_init(nullptr);
	assert(connection);
	const char *port = getenv("DB_PORT");
	assert(mysql_real_connect(
		connection, getenv("DB_HOST"), getenv("DB_USER"), getenv("DB_PASSWD"),
		getenv("CRITICAL_TEST_DB_NAME"),
		static_cast<unsigned int>(strtoul(port ? port : "3306", nullptr, 10)), nullptr, 0));
	return connection;
}

extern "C" int __real_mysql_real_query(MYSQL *, const char *, unsigned long);
extern "C" int __wrap_mysql_real_query(MYSQL *connection, const char *sql, unsigned long length)
{
	const std::string query(sql, length);
	bool fail = false;
	if (query == "COMMIT" && lose_commit_ack.exchange(false))
	{
		assert(__real_mysql_real_query(connection, sql, length) == 0);
		MYSQL *killer = connect_database();
		const std::string kill = "KILL " + std::to_string(mysql_thread_id(connection));
		assert(__real_mysql_real_query(killer, kill.data(), kill.size()) == 0);
		mysql_close(killer);
		// The durable commit happened, but its caller sees a lost connection.
		return __real_mysql_real_query(connection, "SELECT 1", 8);
	}
	if (query.find("SELECT (SELECT COUNT(*) FROM critical_outbox") == 0)
	{
		{
			std::lock_guard<std::mutex> lock(query_mutex);
			counts_sql = query;
		}
		fail = fail_counts;
		if (disconnect_counts.exchange(false))
		{
			MYSQL *killer = connect_database();
			const std::string kill =
				"KILL " + std::to_string(mysql_thread_id(connection));
			assert(__real_mysql_real_query(killer, kill.data(), kill.size()) == 0);
			mysql_close(killer);
		}
	}
	else if (query.find("/* critical_outbox_audit */") == 0)
	{
		++audits;
		fail = fail_audit;
	}
	else if (query.find("SELECT EXISTS(SELECT 1 FROM critical_outbox") == 0)
	{
		++observations;
		fail = fail_observation;
	}
	else if (query.find("SELECT outbox_id,operation_id,destination") == 0)
		++fetches;
	// A genuine server SQL error leaves the connection usable. Connection-loss
	// coverage above actually kills the connection and exercises replacement.
	if (fail)
	{
		static const char invalid[] = "SELECT * FROM outbox_deliberately_missing_table";
		return __real_mysql_real_query(connection, invalid, sizeof(invalid) - 1);
	}
	return __real_mysql_real_query(connection, sql, length);
}

extern "C" MYSQL *sql_pool_acquire(void)
{
	return pool_available ? worker_connection : nullptr;
}
extern "C" MYSQL *sql_pool_replace_connection(MYSQL *)
{
	mysql_close(worker_connection);
	worker_connection = connect_database();
	++replacements;
	return worker_connection;
}

static void execute(const char *sql)
{
	const int result = mysql_real_query(database_connection, sql, strlen(sql));
	if (result != 0)
		fprintf(stderr, "critical outbox query failed: %s\n",
			mysql_error(database_connection));
	assert(result == 0);
}

static unsigned long long scalar(const char *sql)
{
	execute(sql);
	MYSQL_RES *result = mysql_store_result(database_connection);
	assert(result);
	MYSQL_ROW row = mysql_fetch_row(result);
	assert(row && row[0]);
	const unsigned long long value = strtoull(row[0], nullptr, 10);
	mysql_free_result(result);
	return value;
}

static unsigned long long next_reads()
{
	execute("SHOW SESSION STATUS LIKE 'Handler_read_next'");
	MYSQL_RES *result = mysql_store_result(database_connection);
	assert(result);
	MYSQL_ROW row = mysql_fetch_row(result);
	assert(row && row[1]);
	const auto value = strtoull(row[1], nullptr, 10);
	mysql_free_result(result);
	return value;
}

static void clear_rows()
{
	execute("DELETE d FROM critical_outbox_delivery_dedupe d JOIN critical_outbox o ON "
		"o.outbox_id=d.outbox_id WHERE o.operation_id IN "
		"(UNHEX('00000000000000000000000000000001'),"
		"UNHEX('00000000000000000000000000000002'),"
		"UNHEX('00000000000000000000000000000003'))");
	execute("DELETE FROM critical_outbox WHERE operation_id IN "
		"(UNHEX('00000000000000000000000000000001'),"
		"UNHEX('00000000000000000000000000000002'),"
		"UNHEX('00000000000000000000000000000003'))");
	execute("DELETE FROM critical_operation_inbox WHERE operation_id IN "
		"(UNHEX('00000000000000000000000000000001'),"
		"UNHEX('00000000000000000000000000000002'),"
		"UNHEX('00000000000000000000000000000003'))");
	execute("DELETE FROM critical_test_state");
}

static void insert_record(unsigned int suffix)
{
	const char digit = static_cast<char>('0' + suffix);
	char sql[2048] = {};
	snprintf(
		sql, sizeof(sql),
		"INSERT INTO critical_operation_inbox(operation_id,command_hash,keys_hash,"
		"command_type,schema_version,payload_version,status,result_payload,committed_at) "
		"VALUES(UNHEX('0000000000000000000000000000000%c'),UNHEX(REPEAT('11',32)),"
		"UNHEX(REPEAT('22',32)),1,1,1,1,'',CURRENT_TIMESTAMP(6));"
		"INSERT INTO critical_outbox(operation_id,event_index,destination,event_type,"
		"payload_version,payload) VALUES(UNHEX('0000000000000000000000000000000%c'),0,1,1,1,"
		"UNHEX(REPEAT('33',16)))",
		digit, digit);
	const char *separator = strchr(sql, ';');
	assert(separator);
	std::string first(sql, static_cast<size_t>(separator - sql));
	execute(first.c_str());
	execute(separator + 1);
}

struct delivery_state
{
	unsigned int calls;
	bool retry_first;
	bool terminal;
	bool deferred = false;
};
static std::atomic<bool> block_delivery = false, delivery_entered = false;
static std::atomic<bool> publication_queued = false, publication_ready = false;
static bool needs_publication = false;
static bool duplicate_delivery = false;
static std::thread::id game_thread;
static std::chrono::steady_clock::time_point publication_not_before;

static void publish()
{
	assert(std::this_thread::get_id() == game_thread);
	if (publication_queued && !publication_ready &&
	    std::chrono::steady_clock::now() >= publication_not_before)
	{
		publication_ready = true;
		critical_outbox_resume();
	}
}

static critical_outbox_delivery_result deliver(const critical_outbox_record &record, void *raw)
{
	auto &state = *static_cast<delivery_state *>(raw);
	assert(record.outbox_id &&
	       ((record.destination == 1 && record.event_type == 1 && record.payload_version == 1) ||
		(record.destination == 7 && record.event_type == 2 &&
		 record.payload_version == 3)) &&
	       record.payload.size() == 16 && record.operation_id.bytes[15] >= 1 &&
	       record.operation_id.bytes[15] <= 3);
	++state.calls;
	delivery_entered = true;
	while (block_delivery)
		std::this_thread::sleep_for(std::chrono::milliseconds(1));
	if (needs_publication && !publication_ready)
	{
		publication_queued = true;
		return critical_outbox_delivery_result::publication_pending;
	}
	if (state.deferred)
		return critical_outbox_delivery_result::publication_pending;
	if (state.terminal)
		return critical_outbox_delivery_result::terminal_failure;
	if (state.retry_first && state.calls == 1)
		return critical_outbox_delivery_result::retryable_failure;
	if (duplicate_delivery)
		return critical_outbox_delivery_result::already_delivered;
	return critical_outbox_delivery_result::delivered;
}

template <typename Predicate> static void wait_until(Predicate predicate)
{
	const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(10);
	while (!predicate())
	{
		assert(std::chrono::steady_clock::now() < deadline);
		std::this_thread::sleep_for(std::chrono::milliseconds(10));
	}
}

static void audit_fixtures()
{
	clear_rows();
	auto id = [](unsigned int suffix)
	{ return "UNHEX(LPAD(HEX(" + std::to_string(200000 + suffix) + "),32,'0'))"; };
	auto receipt = [&](const std::string &operation, unsigned int type, int expected,
			   unsigned int code = 0)
	{
		execute(("INSERT INTO critical_operation_inbox(operation_id,command_hash,keys_hash,"
			 "command_type,schema_version,payload_version,status,result_code,result_payload,"
			 "created_at,committed_at,expected_outbox_events) VALUES(" +
			 operation + ",UNHEX(REPEAT('11',32)),UNHEX(REPEAT('22',32))," +
			 std::to_string(type) + ",1,1,1," + std::to_string(code) +
			 ",'','2020-01-01','2020-01-01'," +
			 (expected < 0 ? "NULL" : std::to_string(expected)) + ")")
				.c_str());
	};
	auto event = [&](unsigned int operation, unsigned int index)
	{
		execute(("INSERT INTO critical_outbox(operation_id,event_index,destination,event_type,"
			 "payload_version,payload,status) VALUES(" +
			 id(operation) + "," + std::to_string(index) +
			 ",1,1,1,UNHEX(REPEAT('33',16)),1)")
				.c_str());
	};
	receipt(id(1), 13, -1); // Proven historical audit omission.
	execute(("INSERT INTO session_audit_outcome(operation_id,pid,event_type,occurred_at) VALUES(" +
		 id(1) + ",105,1,'2020-01-01')")
			.c_str());
	receipt(id(2), 13, -1); // Type alone is not proof: no typed receipt.
	receipt(id(3), 7, 0); // Successful zero-effect result.
	receipt(id(4), 7, -1, EINVAL); // Historical rejection has no publication.
	receipt(id(5), 12, 1); // A recovered stone receipt still expects its event.
	receipt(id(6), 5, 3);
	event(6, 0);
	event(6, 2); // Partial multi-event loss.
	receipt(id(7), 5, 2);
	event(7, 0);
	event(7, 2); // Correct count, wrong indexes.
	receipt(id(8), 7, 0);
	event(8, 0); // Unexpected event for known zero.
	receipt(id(9), 11, -1);
	execute(("INSERT INTO boon_reward_outcome(operation_id,pid,`option`,event_value,entry_count) VALUES(" +
		 id(9) + ",104,0,0,0)")
			.c_str()); // Even zero-match legacy boons expected one event.
	receipt(id(10), 5, -1);
	event(10, 0); // Unknown historical multi-event set stays unknown.
	receipt(id(11), 7, -1); // Unproven historical no-op is also unknown.
	receipt(id(16), 12, -1);
	execute(("INSERT INTO zone_touch_outcome(operation_id,zone_number,toucher_pid,boot_time,"
		 "touched_at,group_size,epic_value,alignment_delta) VALUES(" +
		 id(16) + ",1,100,1,2,1,1,0)")
			.c_str()); // Missing event from an old typed mutation.
	receipt(id(18), 12, -1); // Recovery without provable history is never a zero exemption.
	for (unsigned int parent : { 12U, 21U })
	{
		receipt(id(parent), 8, -1);
		event(parent, 0);
		execute(("INSERT INTO combat_outcome(operation_id,pkill_event_id,victim_pid,room_vnum,"
			 "participant_count) VALUES(" +
			 id(parent) + "," + std::to_string(parent) + ",20,1," +
			 (parent == 12 ? "2" : "1") + ")")
				.c_str());
	}
	receipt(id(22), 7, -1);
	execute(("INSERT INTO auction_ledger(operation_id,event_type,auction_id,auction_revision) VALUES(" +
		 id(22) + ",1,1,1)")
			.c_str());
	receipt(id(23), 9, -1);
	execute(("INSERT INTO artifact_guild_outcome(operation_id,parent_operation_id,actor_pid) VALUES(" +
		 id(23) + "," + id(12) + ",100)")
			.c_str());
	receipt(id(24), 18, -1);
	execute(("INSERT INTO collector_ledger(operation_id,listing_id,action,catalog_revision,listing_revision,"
		 "item_uid,source_site) VALUES(" +
		 id(24) + ",1,5,1,1,1,2)")
			.c_str());
	auto combat_child = [&](unsigned int parent, unsigned int index, unsigned int pid,
				bool divine, bool impostor)
	{
		// Writer contract: first 16 bytes of SHA256(parent || domain || LE16(index)).
		// C++ hashing independently checks the audit's SQL identity calculation.
		std::array<uint8_t, 19> input = {};
		for (unsigned int byte = 0; byte < 4; ++byte)
			input[15 - byte] = static_cast<uint8_t>((200000 + parent) >> (8 * byte));
		input[16] = 1;
		input[17] = static_cast<uint8_t>(index);
		std::array<uint8_t, SHA256_DIGEST_LENGTH> digest = {};
		SHA256(input.data(), input.size(), digest.data());
		std::array<uint8_t, 16> child = {};
		std::copy_n(digest.begin(), child.size(), child.begin());
		if (impostor)
			child[0] ^= 1; // Same hashes/ledger shape, wrong derived identity.
		auto hex = [](const uint8_t *bytes, size_t length)
		{
			static const char DIGITS[] = "0123456789abcdef";
			std::string value;
			for (size_t i = 0; i < length; ++i)
			{
				value += DIGITS[bytes[i] >> 4];
				value += DIGITS[bytes[i] & 15];
			}
			return value;
		};
		const std::string operation = "UNHEX('" + hex(child.data(), child.size()) + "')";
		receipt(operation, 2, -1);
		SHA256(child.data(), child.size(), digest.data());
		const auto hash = "UNHEX('" + hex(digest.data(), digest.size()) + "')";
		execute(("UPDATE critical_operation_inbox SET command_hash=" + hash +
			 ",keys_hash=" + hash +
			 ",durable_revision=1 WHERE operation_id=" + operation)
				.c_str());
		execute(("INSERT INTO combat_outcome_participant(operation_id,participant_index,pid,role,flags,"
			 "frag_delta,epic_delta,wallet_delta_copper,frag_after,frag_revision,epic_revision,"
			 "wallet_revision,bank_revision) VALUES(" +
			 id(parent) + "," + std::to_string(index) + "," + std::to_string(pid) +
			 ",1," + (divine ? "8" : "0") + ",0,50,0,0,0,1,0,0)")
				.c_str());
		execute(("INSERT INTO epic_ledger(operation_id,pid,delta,balance_after,epic_revision,reason_type,"
			 "reason_id,source_site) VALUES(" +
			 operation + "," + std::to_string(pid) + ",50,150,1," +
			 std::to_string(
				 static_cast<uint16_t>(divine ? epic_reason_type::divine_pvp_award :
								epic_reason_type::pvp_award)) +
			 ",20," +
			 std::to_string(static_cast<uint16_t>(critical_source_site::combat)) + ")")
				.c_str());
	};
	combat_child(12, 0, 100, false, false);
	combat_child(12, 1, 101, false, true);
	combat_child(21, 0, 102, true, false);
	delivery_state state = {};
	assert(critical_outbox_init(deliver, &state));
	wait_until([] { return critical_outbox_health_copy().audit_available; });
	const auto result = critical_outbox_health_copy();
	assert(result.outbox_expectation_mismatches == 10);
	assert(result.unknown_outbox_expectations == 4);
	assert(result.committed_without_outbox == 3);
	critical_outbox_shutdown();
	// This database is owned solely by the disposable wrapper. Respect all FKs.
	for (const char *table :
	     { "combat_outcome_participant", "combat_outcome", "epic_ledger",
	       "session_audit_outcome", "boon_reward_outcome", "zone_touch_outcome",
	       "auction_ledger", "artifact_guild_outcome", "collector_ledger",
	       "critical_outbox_delivery_dedupe", "critical_outbox", "critical_operation_inbox" })
		execute(("DELETE FROM " + std::string(table)).c_str());
	puts("outbox historical proof, unknown coverage and exact/partial/unexpected event audit passed");
}

int main()
{
	assert(mysql_library_init(0, nullptr, nullptr) == 0);
	database_connection = connect_database();
	worker_connection = connect_database();
	game_thread = std::this_thread::get_id();
	assert(!critical_outbox_drain(0));
	// The wrapper owns an isolated database with ordinary production-shaped tables.
	clear_rows();

	insert_record(1);
	delivery_state state = {};
	assert(critical_outbox_init(deliver, &state));
	// Startup health is zero before the first poll; only a new worker observation
	// can establish emptiness after the committed record is delivered.
	assert(!critical_outbox_health_copy().counts_available);
	assert(critical_outbox_drain(1000));
	wait_until([&] { return critical_outbox_health_copy().delivered == 1; });
	critical_outbox_shutdown();
	assert(scalar("SELECT COUNT(*) FROM critical_outbox WHERE status=1 AND operation_id="
		      "UNHEX('00000000000000000000000000000001')") == 1);
	assert(scalar("SELECT COUNT(*) FROM critical_outbox_delivery_dedupe d JOIN "
		      "critical_outbox o ON o.outbox_id=d.outbox_id WHERE o.operation_id="
		      "UNHEX('00000000000000000000000000000001')") == 1);

	clear_rows();
	insert_record(1);
	state = { .calls = 0, .retry_first = false, .terminal = false, .deferred = true };
	assert(critical_outbox_init(deliver, &state));
	wait_until(
		[&] {
			return critical_outbox_health_copy().fetched >
			       CRITICAL_OUTBOX_MAX_ATTEMPTS + 1;
		});
	critical_outbox_shutdown();
	assert(scalar("SELECT COUNT(*) FROM critical_outbox WHERE status=0 AND attempt_count=0 AND operation_id=UNHEX('00000000000000000000000000000001')") ==
	       1);
	state.deferred = false;
	assert(critical_outbox_init(deliver, &state));
	wait_until([&] { return critical_outbox_health_copy().delivered == 1; });
	critical_outbox_shutdown();
	assert(scalar("SELECT COUNT(*) FROM critical_outbox WHERE status=1 AND attempt_count=0 AND operation_id=UNHEX('00000000000000000000000000000001')") ==
	       1);

	clear_rows();
	insert_record(1);
	execute("UPDATE critical_operation_inbox SET command_type=9,payload_version=3");
	execute("UPDATE critical_outbox SET destination=7,event_type=2,payload_version=3");
	execute("CREATE TRIGGER refuse_effect_ack BEFORE UPDATE ON critical_operation_inbox FOR EACH ROW BEGIN IF NEW.result_code=1 THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='effect ACK fixture'; END IF; END");
	state = {};
	assert(critical_outbox_init(deliver, &state));
	wait_until([&] { return critical_outbox_health_copy().db_failures > 0; });
	critical_outbox_shutdown();
	assert(scalar("SELECT status FROM critical_outbox") == 0);
	assert(scalar("SELECT result_code FROM critical_operation_inbox") == 0);
	assert(scalar("SELECT COUNT(*) FROM critical_outbox_delivery_dedupe") == 0);
	execute("DROP TRIGGER refuse_effect_ack");
	assert(critical_outbox_init(deliver, &state));
	wait_until([&] { return critical_outbox_health_copy().delivered == 1; });
	critical_outbox_shutdown();
	assert(scalar("SELECT status FROM critical_outbox") == 1);
	assert(scalar("SELECT result_code FROM critical_operation_inbox") == 1);

	clear_rows();
	insert_record(2);
	state = { .calls = 0, .retry_first = true, .terminal = false };
	assert(critical_outbox_init(deliver, &state));
	wait_until([&] { return critical_outbox_health_copy().retries == 1; });
	critical_outbox_shutdown();
	execute("UPDATE critical_outbox SET next_attempt_at=CURRENT_TIMESTAMP(6) WHERE "
		"operation_id=UNHEX('00000000000000000000000000000002')");
	state.retry_first = false;
	assert(critical_outbox_init(deliver, &state));
	wait_until([&] { return critical_outbox_health_copy().delivered == 1; });
	critical_outbox_shutdown();
	assert(state.calls == 2);
	assert(scalar("SELECT COUNT(*) FROM critical_outbox WHERE status=1 AND attempt_count=1 "
		      "AND operation_id=UNHEX('00000000000000000000000000000002')") == 1);

	clear_rows();
	insert_record(3);
	state = { .calls = 0, .retry_first = false, .terminal = true };
	assert(critical_outbox_init(deliver, &state));
	wait_until([&] { return critical_outbox_health_copy().terminal_failures == 1; });
	critical_outbox_shutdown();
	assert(scalar("SELECT COUNT(*) FROM critical_outbox WHERE status=2 AND operation_id="
		      "UNHEX('00000000000000000000000000000003')") == 1);
	puts("outbox delivery, fresh startup drain, retry/restart and terminal failure passed");
	clear_rows();
	insert_record(1);
	state = {};
	lose_commit_ack = true;
	assert(critical_outbox_init(deliver, &state));
	assert(critical_outbox_drain(1000));
	critical_outbox_shutdown();
	assert(state.calls == 1);
	assert(scalar("SELECT COUNT(*) FROM critical_outbox_delivery_dedupe") == 1);
	clear_rows();
	insert_record(2);
	state = {};
	duplicate_delivery = true;
	assert(critical_outbox_init(deliver, &state));
	assert(critical_outbox_drain(1000));
	assert(critical_outbox_health_copy().duplicates == 1);
	critical_outbox_shutdown();
	duplicate_delivery = false;
	puts("outbox ambiguous commit reconciliation and duplicate callback passed");

	clear_rows();
	state = {};
	assert(critical_outbox_init(deliver, &state));
	assert(critical_outbox_drain(1000));
	wait_until([] { return critical_outbox_health_copy().counts_available; });
	// A new commit after an observed zero must not reuse that old observation.
	insert_record(1);
	execute("UPDATE critical_outbox SET next_attempt_at=TIMESTAMPADD(HOUR,1,CURRENT_TIMESTAMP(6))");
	assert(!critical_outbox_drain(80));
	wait_until([] { return critical_outbox_health_copy().pending == 1; });
	critical_outbox_quiesce();
	assert(!critical_outbox_health_copy().accepting);
	// Preserve a last-good positive count when diagnostics fail, but let delivery
	// and the independent empty check complete.
	fail_counts = true;
	execute("UPDATE critical_outbox SET next_attempt_at=CURRENT_TIMESTAMP(6)");
	assert(critical_outbox_drain(1000));
	wait_until([] { return critical_outbox_health_copy().counts_stale; });
	assert(critical_outbox_health_copy().pending == 1);
	fail_counts = false;
	critical_outbox_resume();
	wait_until([] { return !critical_outbox_health_copy().counts_stale; });
	assert(critical_outbox_health_copy().pending == 0);
	assert(critical_outbox_health_copy().accepting);
	// SQL failure and pool outage cannot reuse an earlier successful drain.
	fail_observation = true;
	assert(!critical_outbox_drain(80));
	fail_observation = false;
	pool_available = false;
	assert(!critical_outbox_drain(80));
	pool_available = true;
	assert(critical_outbox_drain(1000));
	const unsigned int replaced_before = replacements;
	disconnect_counts = true;
	critical_outbox_resume();
	wait_until([&] { return replacements > replaced_before; });
	assert(critical_outbox_drain(1000));
	critical_outbox_shutdown();
	assert(!critical_outbox_drain(0));

	clear_rows();
	insert_record(1);
	state = {};
	block_delivery = true;
	delivery_entered = false;
	assert(critical_outbox_init(deliver, &state));
	wait_until([] { return delivery_entered.load(); });
	auto in_flight = std::async(std::launch::async, [] { return critical_outbox_drain(1000); });
	assert(in_flight.wait_for(std::chrono::milliseconds(50)) == std::future_status::timeout);
	block_delivery = false;
	assert(in_flight.get());
	critical_outbox_shutdown();
	clear_rows();
	insert_record(1);
	execute("UPDATE critical_outbox SET next_attempt_at=TIMESTAMPADD(HOUR,1,CURRENT_TIMESTAMP(6))");
	assert(critical_outbox_init(deliver, &state));
	auto stopping = std::async(std::launch::async, [] { return critical_outbox_drain(1000); });
	assert(stopping.wait_for(std::chrono::milliseconds(30)) == std::future_status::timeout);
	critical_outbox_shutdown();
	assert(!stopping.get());

	clear_rows();
	insert_record(2);
	state = {};
	needs_publication = true;
	publication_queued = publication_ready = false;
	// A read finishing after the old two-second retry must still acknowledge
	// within the caller's three seconds, without consuming eight attempts.
	publication_not_before = std::chrono::steady_clock::now() + std::chrono::milliseconds(2300);
	assert(critical_outbox_init(deliver, &state, publish));
	assert(critical_outbox_drain(3000));
	assert(publication_ready && state.calls > CRITICAL_OUTBOX_MAX_ATTEMPTS);
	assert(critical_outbox_health_copy().retries == 0 &&
	       critical_outbox_health_copy().terminal_failures == 0);
	assert(scalar("SELECT attempt_count FROM critical_outbox") == 0);
	critical_outbox_shutdown();
	needs_publication = false;
	puts("outbox commit/in-flight/future-retry/failure drains and game-thread publication passed");

	// Compare actual operational SQL row work before/after retained history.
	clear_rows();
	insert_record(1);
	insert_record(2);
	insert_record(3);
	execute("UPDATE critical_outbox SET next_attempt_at=TIMESTAMPADD(HOUR,1,CURRENT_TIMESTAMP(6))");
	execute("UPDATE critical_outbox SET status=2 WHERE operation_id=UNHEX('00000000000000000000000000000002')");
	execute("DELETE FROM critical_outbox WHERE operation_id=UNHEX('00000000000000000000000000000003')");
	execute("UPDATE critical_operation_inbox SET status=0 WHERE operation_id=UNHEX('00000000000000000000000000000003')");
	assert(critical_outbox_init(deliver, &state));
	wait_until([] { return critical_outbox_health_copy().counts_available; });
	auto mixed = critical_outbox_health_copy();
	assert(mixed.pending == 1 && mixed.dead_letter == 1 && mixed.incomplete_inbox == 1);
	critical_outbox_shutdown();
	std::string operational;
	{
		std::lock_guard<std::mutex> lock(query_mutex);
		operational = counts_sql;
	}
	auto row_work = [&]
	{
		const auto before = next_reads();
		execute(operational.c_str());
		MYSQL_RES *result = mysql_store_result(database_connection);
		assert(result);
		MYSQL_ROW row = mysql_fetch_row(result);
		assert(row && strtoull(row[0], nullptr, 10) == 1 &&
		       strtoull(row[1], nullptr, 10) == 1 && strtoull(row[3], nullptr, 10) == 1);
		mysql_free_result(result);
		return next_reads() - before;
	};
	const auto before_history = row_work();
	std::string digits =
		"(SELECT 0 n UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4 UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8 UNION ALL SELECT 9)";
	std::string numbers = "SELECT 1000+a.n+10*b.n+100*c.n+1000*d.n+10000*e.n n FROM " + digits +
			      " a CROSS JOIN " + digits + " b CROSS JOIN " + digits +
			      " c CROSS JOIN " + digits + " d CROSS JOIN " + digits + " e";
	execute(("INSERT INTO critical_operation_inbox(operation_id,command_hash,keys_hash,command_type,schema_version,payload_version,status,result_payload,committed_at) SELECT UNHEX(LPAD(HEX(n),32,'0')),UNHEX(REPEAT('11',32)),UNHEX(REPEAT('22',32)),1,1,1,1,'',CURRENT_TIMESTAMP(6) FROM (" +
		 numbers + ") numbers")
			.c_str());
	execute("INSERT INTO critical_outbox(operation_id,event_index,destination,event_type,payload_version,payload,status) SELECT operation_id,0,1,1,1,UNHEX(REPEAT('33',16)),1 FROM critical_operation_inbox WHERE operation_id>=UNHEX('000000000000000000000000000003e8')");
	assert(row_work() == before_history);
	assert(before_history < 20);
	execute(("EXPLAIN FORMAT=JSON " + operational).c_str());
	MYSQL_RES *plan_result = mysql_store_result(database_connection);
	assert(plan_result);
	MYSQL_ROW plan_row = mysql_fetch_row(plan_result);
	assert(plan_row && plan_row[0]);
	const std::string plan = plan_row[0];
	assert(plan.find("\"access_type\": \"ALL\"") == std::string::npos);
	assert(plan.find("\"access_type\": \"index\"") == std::string::npos);
	mysql_free_result(plan_result);
	// A large *active* backlog is counted exactly and remains ineligible for fetch.
	execute("UPDATE critical_outbox SET status=0,next_attempt_at=TIMESTAMPADD(HOUR,1,CURRENT_TIMESTAMP(6)) WHERE operation_id>=UNHEX('000000000000000000000000000003e8') LIMIT 10000");
	assert(critical_outbox_init(deliver, &state));
	wait_until([] { return critical_outbox_health_copy().counts_available; });
	assert(critical_outbox_health_copy().pending == 10001);
	assert(!critical_outbox_drain(80));
	critical_outbox_shutdown();
	execute("DELETE FROM critical_outbox WHERE operation_id>=UNHEX('000000000000000000000000000003e8')");
	execute("DELETE FROM critical_operation_inbox WHERE operation_id>=UNHEX('000000000000000000000000000003e8')");
	printf("outbox mixed counters and 100k delivered-history scaling passed (%llu indexed next reads)\n",
	       before_history);
	audit_fixtures();

	// One real minute proves the production deadline; do not add a test-only
	// scheduler/configuration surface to the worker.
	clear_rows();
	state = {};
	const unsigned int audits_before = audits;
	assert(critical_outbox_init(deliver, &state));
	wait_until(
		[&] {
			return audits > audits_before &&
			       critical_outbox_health_copy().audit_available;
		});
	const auto first_audit = std::chrono::steady_clock::now();
	const unsigned int fetches_before = fetches;
	fail_audit = true;
	insert_record(1);
	assert(critical_outbox_drain(1000));
	for (unsigned int i = 0; i < 10; ++i)
	{
		critical_outbox_resume();
		std::this_thread::sleep_for(std::chrono::milliseconds(10));
	}
	assert(audits == audits_before + 1);
	assert(fetches > fetches_before);
	puts("checking independent 60-second audit deadline and failure backoff...");
	fflush(stdout);
	while (audits == audits_before + 1)
	{
		assert(std::chrono::steady_clock::now() - first_audit < std::chrono::seconds(63));
		std::this_thread::sleep_for(std::chrono::milliseconds(20));
	}
	assert(std::chrono::steady_clock::now() - first_audit >= std::chrono::milliseconds(59500));
	wait_until([] { return critical_outbox_health_copy().audit_stale; });
	assert(critical_outbox_health_copy().audit_available);
	assert(critical_outbox_health_copy().committed_without_outbox == 0);
	assert(critical_outbox_health_copy().audit_age_msec >= 59500);
	fail_audit = false;
	critical_outbox_resume();
	std::this_thread::sleep_for(std::chrono::milliseconds(800));
	assert(audits == audits_before + 2); // No catch-up burst after a failed attempt/resume.
	insert_record(2);
	assert(critical_outbox_drain(1000));
	critical_outbox_shutdown();
	puts("outbox independent audit cadence, stale last-good values and continued delivery passed");
	clear_rows();
	insert_record(1);
	state = {};
	fail_counts = fail_audit = true;
	const unsigned int unavailable_audits = audits;
	assert(critical_outbox_init(deliver, &state));
	assert(critical_outbox_drain(1000));
	wait_until([&] { return audits > unavailable_audits; });
	assert(!critical_outbox_health_copy().counts_available);
	assert(!critical_outbox_health_copy().audit_available);
	std::this_thread::sleep_for(std::chrono::milliseconds(800));
	assert(audits == unavailable_audits + 1);
	critical_outbox_shutdown();
	fail_counts = fail_audit = false;
	puts("outbox unavailable diagnostics do not block delivery or retry audits rapidly");

	clear_rows();
	mysql_close(worker_connection);
	mysql_close(database_connection);
	database_connection = nullptr;
	return 0;
}
