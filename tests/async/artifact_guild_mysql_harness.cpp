#include "guild/artifact_guild_command.h"
#include "guild/artifact_guild_transaction.h"
#include "redis/redis_report_cache.h"
#include <cstdarg>
#include <vector>
#include "persistence/critical_command_repository.h"

#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <iostream>
#include <mysql.h>
#include <string>

static std::vector<std::string> diagnostics;
static size_t invalidations = 0;
void logit(const char *, const char *format, ...)
{
	char line[2048];
	va_list args;
	va_start(args, format);
	vsnprintf(line, sizeof(line), format, args);
	va_end(args);
	diagnostics.emplace_back(line);
}
bool persistence_log_submit(const char *record)
{
	diagnostics.emplace_back(record);
	return true;
}
bool redis_invalidate_artifact_cache()
{
	++invalidations;
	return true;
}
void critical_outbox_resume() {}

namespace
{
constexpr int32_t ARTIFACT_VNUM = 2147483001;
constexpr uint32_t GUILD_ID = 4294000201U;
constexpr uint32_t ACTOR_PID = 2147000202U;
constexpr int64_t OPENING_TIMER = 2000000000;

void execute(MYSQL *db, const std::string &sql)
{
	if (mysql_real_query(db, sql.data(), sql.size()) != 0)
	{
		std::cerr << mysql_error(db) << "\nSQL: " << sql << '\n';
		std::abort();
	}
}

uint64_t scalar(MYSQL *db, const std::string &sql)
{
	execute(db, sql);
	MYSQL_RES *result = mysql_store_result(db);
	assert(result);
	MYSQL_ROW row = mysql_fetch_row(result);
	assert(row && row[0]);
	const uint64_t value = strtoull(row[0], nullptr, 10);
	mysql_free_result(result);
	return value;
}

std::string hex_id(const critical_operation_id &id)
{
	char output[CRITICAL_COMMAND_ID_HEX_SIZE] = {};
	assert(critical_operation_id_to_hex(id, output, sizeof(output)));
	return output;
}

void insert_parent(MYSQL *db, const critical_operation_id &id)
{
	execute(db,
		"INSERT INTO critical_operation_inbox(operation_id,command_hash,keys_hash,"
		"command_type,schema_version,payload_version,status,result_payload,committed_at) "
		"VALUES(UNHEX('" +
			hex_id(id) + "'),REPEAT(CHAR(1),32),REPEAT(CHAR(2),32),2,1,1,1,'',NOW(6))");
}

void cleanup(MYSQL *db)
{
	execute(db, "DELETE FROM critical_outbox WHERE operation_id IN (SELECT operation_id FROM "
		    "artifact_guild_outcome WHERE actor_pid=" +
			    std::to_string(ACTOR_PID) + ")");
	execute(db, "DELETE FROM guild_outcome_ledger WHERE guild_id=" + std::to_string(GUILD_ID));
	execute(db,
		"DELETE FROM artifact_delta_ledger WHERE vnum=" + std::to_string(ARTIFACT_VNUM));
	execute(db, "DELETE FROM artifact_guild_outcome_delta WHERE vnum=" +
			    std::to_string(ARTIFACT_VNUM));
	execute(db,
		"DELETE FROM artifact_guild_outcome WHERE actor_pid=" + std::to_string(ACTOR_PID));
	execute(db,
		"DELETE FROM critical_operation_inbox WHERE created_at>=@artifact_harness_started "
		"AND command_type IN (2,9)");
	execute(db,
		"DELETE FROM artifact_domain_baseline WHERE vnum=" + std::to_string(ARTIFACT_VNUM));
	execute(db,
		"DELETE FROM artifact_domain_state WHERE vnum=" + std::to_string(ARTIFACT_VNUM));
	execute(db, "DELETE FROM artifact_bind WHERE vnum=" + std::to_string(ARTIFACT_VNUM));
	execute(db, "DELETE FROM artifacts WHERE vnum=" + std::to_string(ARTIFACT_VNUM));
	execute(db, "DELETE FROM guilds WHERE id=" + std::to_string(GUILD_ID));
}
} // namespace

template <typename T> void append(std::vector<uint8_t> &bytes, T value)
{
	for (size_t i = 0; i < sizeof(T); ++i)
		bytes.push_back(static_cast<uint8_t>(static_cast<uint64_t>(value) >> (i * 8)));
}
std::string hex_bytes(const uint8_t *bytes, size_t size)
{
	const char *digits = "0123456789abcdef";
	std::string out;
	for (size_t i = 0; i < size; ++i)
	{
		out += digits[bytes[i] >> 4];
		out += digits[bytes[i] & 15];
	}
	return out;
}
// The former wire layout, used only to qualify existing receipts. No legacy
// gameplay implementation is linked into the new repository.
critical_command legacy_command(critical_command command, const artifact_guild_payload &p)
{
	command.payload_version = 1;
	auto &bytes = command.payload;
	bytes.assign(p.parent_operation_id.bytes.begin(), p.parent_operation_id.bytes.end());
	append(bytes, p.actor_pid);
	append(bytes, p.guild_id);
	append<uint64_t>(bytes, 0);
	append(bytes, p.prestige_delta);
	append(bytes, p.construction_delta);
	append(bytes, p.artifact_count);
	if (p.guild_id)
		command.expected_revisions.push_back(
			{ { critical_entity_type::guild, p.guild_id }, 0 });
	for (size_t i = 0; i < p.artifact_count; ++i)
	{
		const auto &a = p.artifacts[i];
		append(bytes, a.vnum);
		append(bytes, a.flags);
		append<uint64_t>(bytes, 0);
		append(bytes, a.timer_before);
		append(bytes, a.timer);
		append(bytes, a.bind_owner_before);
		append(bytes, a.bind_owner_pid);
		append(bytes, a.bind_timer_before);
		append(bytes, a.bind_timer);
		command.expected_revisions.push_back(
			{ { critical_entity_type::artifact, static_cast<uint64_t>(a.vnum) }, 0 });
	}
	assert(critical_command_normalize(&command));
	return command;
}

int main()
{
	MYSQL *db = mysql_init(nullptr);
	assert(db);
	const char *port_text = getenv("DB_PORT");
	const unsigned int port = port_text ? static_cast<unsigned int>(atoi(port_text)) : 3306;
	assert(mysql_real_connect(db, getenv("DB_HOST"), getenv("DB_USER"), getenv("DB_PASSWD"),
				  getenv("DB_NAME"), port, nullptr, 0));
	execute(db, "SET @artifact_harness_started=CURRENT_TIMESTAMP(6)");
	cleanup(db);
	execute(db, "INSERT INTO artifacts(vnum,owned,locType,location,timer,type,lastUpdate) "
		    "VALUES(" +
			    std::to_string(ARTIFACT_VNUM) + ",'Y',3," + std::to_string(ACTOR_PID) +
			    ",FROM_UNIXTIME(" + std::to_string(OPENING_TIMER) + "),1,NOW())");
	execute(db, "INSERT INTO artifact_bind(vnum,owner_pid,timer) VALUES(" +
			    std::to_string(ARTIFACT_VNUM) + "," + std::to_string(ACTOR_PID) +
			    ",0)");
	execute(db, "INSERT INTO artifact_domain_state(vnum,owned,loc_type,location,timer_epoch,"
		    "artifact_type,bind_owner_pid,bind_timer_epoch) VALUES(" +
			    std::to_string(ARTIFACT_VNUM) + ",1,3," + std::to_string(ACTOR_PID) +
			    "," + std::to_string(OPENING_TIMER) + ",1," +
			    std::to_string(ACTOR_PID) + ",0)");
	execute(db, "INSERT INTO artifact_domain_baseline(vnum,opening_timer_epoch,"
		    "opening_bind_owner_pid,opening_bind_timer_epoch,opening_revision) VALUES(" +
			    std::to_string(ARTIFACT_VNUM) + "," + std::to_string(OPENING_TIMER) +
			    "," + std::to_string(ACTOR_PID) + ",0,0)");
	execute(db, "INSERT INTO guilds(id,name,prestige,construction) VALUES(" +
			    std::to_string(GUILD_ID) + ",'Artifact Harness',95,10)");

	// Repository evidence only: these are already-applied capture facts. SQL is
	// deliberately newer (transfer, soul change, spending and staff adjustment).
	execute(db, "UPDATE artifacts SET location=77,timer=FROM_UNIXTIME(2000020000) WHERE vnum=" +
			    std::to_string(ARTIFACT_VNUM));
	execute(db, "UPDATE artifact_bind SET owner_pid=77,timer=17 WHERE vnum=" +
			    std::to_string(ARTIFACT_VNUM));
	execute(db,
		"UPDATE artifact_domain_state SET location=77,timer_epoch=2000020000,bind_owner_pid=77,bind_timer_epoch=17,revision=700 WHERE vnum=" +
			std::to_string(ARTIFACT_VNUM));
	execute(db, "UPDATE guilds SET prestige=65,construction=8,outcome_revision=90 WHERE id=" +
			    std::to_string(GUILD_ID));
	auto current_state = [&]()
	{
		assert(scalar(db, "SELECT UNIX_TIMESTAMP(timer) FROM artifacts WHERE vnum=" +
					  std::to_string(ARTIFACT_VNUM)) == 2000020000);
		assert(scalar(db, "SELECT location FROM artifacts WHERE vnum=" +
					  std::to_string(ARTIFACT_VNUM)) == 77);
		assert(scalar(db, "SELECT owner_pid FROM artifact_bind WHERE vnum=" +
					  std::to_string(ARTIFACT_VNUM)) == 77);
		assert(scalar(db, "SELECT timer_epoch FROM artifact_domain_state WHERE vnum=" +
					  std::to_string(ARTIFACT_VNUM)) == 2000020000);
		assert(scalar(db, "SELECT revision FROM artifact_domain_state WHERE vnum=" +
					  std::to_string(ARTIFACT_VNUM)) == 700);
		assert(scalar(db, "SELECT prestige FROM guilds WHERE id=" +
					  std::to_string(GUILD_ID)) == 65);
		assert(scalar(db, "SELECT construction FROM guilds WHERE id=" +
					  std::to_string(GUILD_ID)) == 8);
		assert(scalar(db, "SELECT outcome_revision FROM guilds WHERE id=" +
					  std::to_string(GUILD_ID)) == 90);
	};
	uint64_t sequence = 1;
	auto build = [&](artifact_guild_payload &payload, bool parent_exists = true)
	{
		assert(critical_operation_id_generate(&payload.parent_operation_id));
		if (parent_exists)
			insert_parent(db, payload.parent_operation_id);
		critical_operation_id child = {};
		assert(critical_operation_id_derive(payload.parent_operation_id, 0x41475431,
						    ACTOR_PID, &child));
		critical_command command = {};
		assert(artifact_guild_command_build(&command, child, payload));
		command.accepted_at_usec = sequence++;
		return command;
	};
	auto apply = [&](const critical_command &command)
	{
		auto result = critical_command_repository_apply(db, command);
		assert(result.outcome == critical_apply_outcome::applied);
		assert(result.result_size == ARTIFACT_GUILD_RESULT_BYTES);
		return result;
	};
	auto reject = [&](const critical_command &command, unsigned int error, const char *reason)
	{
		diagnostics.clear();
		auto result = critical_command_repository_apply(db, command);
		assert(result.outcome == critical_apply_outcome::terminal_failure &&
		       result.error_code == error);
		bool named = false;
		for (const auto &line : diagnostics)
			if (line.find(std::string("reason=") + reason) != std::string::npos)
				named = true;
		assert(named);
	};
	artifact_guild_payload payload = {};
	payload.actor_pid = ACTOR_PID;
	payload.guild_id = GUILD_ID;
	payload.artifact_count = 1;
	std::vector<critical_command> burst;
	for (int i = 0; i < 3; ++i)
	{
		payload.prestige_before = 85 + i * 10;
		payload.prestige_after = 95 + i * 10;
		payload.prestige_delta = 10;
		payload.construction_before = i > 1 ? 1 : 0;
		payload.construction_after = i > 0 ? 1 : 0;
		payload.construction_delta =
			payload.construction_after - payload.construction_before;
		payload.artifacts[0] = { ARTIFACT_VNUM,
					 ARTIFACT_DELTA_FEED,
					 OPENING_TIMER + i * 3600,
					 OPENING_TIMER + (i + 1) * 3600,
					 static_cast<int32_t>(ACTOR_PID),
					 static_cast<int32_t>(ACTOR_PID),
					 0,
					 0 };
		burst.push_back(build(payload));
	}
	for (const auto &command : burst)
	{
		apply(command);
		current_state();
	}
	assert(scalar(db, "SELECT SUM(timer_delta) FROM artifact_delta_ledger WHERE vnum=" +
				  std::to_string(ARTIFACT_VNUM)) == 10800);
	assert(scalar(db, "SELECT SUM(prestige_delta) FROM guild_outcome_ledger WHERE guild_id=" +
				  std::to_string(GUILD_ID)) == 30);
	assert(scalar(db,
		      "SELECT SUM(construction_delta) FROM guild_outcome_ledger WHERE guild_id=" +
			      std::to_string(GUILD_ID)) == 1);
	assert(scalar(db, "SELECT MAX(revision) FROM artifact_delta_ledger WHERE vnum=" +
				  std::to_string(ARTIFACT_VNUM)) == 3);
	for (const auto &command : burst)
		assert(critical_command_repository_apply(db, command).outcome ==
		       critical_apply_outcome::already_applied);
	current_state();
	assert(scalar(db, "SELECT COUNT(*) FROM artifact_guild_outcome WHERE actor_pid=" +
				  std::to_string(ACTOR_PID)) == 3);
	std::cout
		<< "PASS captured burst history, construction threshold, immutable replay; newer gameplay snapshots unchanged\n";
	auto reconcile = []()
	{
		return std::system(
			"migrations/reconcile_artifact_guild_outcomes.sh > bin/tests/artifact-reconcile.log");
	};
	assert(reconcile() == 0); // timer wars/spending differ from reward history legitimately
	execute(db, "UPDATE artifact_domain_state SET timer_epoch=timer_epoch+1 WHERE vnum=" +
			    std::to_string(ARTIFACT_VNUM));
	assert(reconcile() != 0);
	execute(db, "UPDATE artifact_domain_state SET timer_epoch=timer_epoch-1 WHERE vnum=" +
			    std::to_string(ARTIFACT_VNUM));
	execute(db,
		"CREATE TEMPORARY TABLE mirror_copy AS SELECT * FROM artifact_domain_state WHERE vnum=" +
			std::to_string(ARTIFACT_VNUM));
	execute(db,
		"DELETE FROM artifact_domain_state WHERE vnum=" + std::to_string(ARTIFACT_VNUM));
	assert(reconcile() != 0);
	execute(db, "INSERT INTO artifact_domain_state SELECT * FROM mirror_copy");
	execute(db, "CREATE TEMPORARY TABLE legacy_copy AS SELECT * FROM artifacts WHERE vnum=" +
			    std::to_string(ARTIFACT_VNUM));
	execute(db, "DELETE FROM artifacts WHERE vnum=" + std::to_string(ARTIFACT_VNUM));
	assert(reconcile() != 0);
	execute(db, "INSERT INTO artifacts SELECT * FROM legacy_copy");
	assert(reconcile() == 0);
	std::cout
		<< "PASS reconciliation: real mirror/missing-row defects detected; independent reward history accepted\n";

	payload.guild_id = 0;
	payload.prestige_before = payload.prestige_after = 0;
	payload.construction_before = payload.construction_after = 0;
	payload.prestige_delta = payload.construction_delta = 0;
	payload.artifacts[0].timer_before = payload.artifacts[0].timer = OPENING_TIMER + 864000;
	auto capped = build(payload);
	apply(capped);
	current_state();
	assert(scalar(db,
		      "SELECT timer_delta FROM artifact_delta_ledger WHERE operation_id=UNHEX('" +
			      hex_id(capped.operation_id) + "')") == 0);
	auto conflict = capped;
	payload.artifacts[0].timer++;
	assert(artifact_guild_command_build(&conflict, capped.operation_id, payload));
	conflict.accepted_at_usec = capped.accepted_at_usec;
	reject(conflict, EEXIST, "identity_conflict");
	auto duplicate_parent = conflict;
	assert(critical_operation_id_generate(&duplicate_parent.operation_id));
	reject(duplicate_parent, 1062, "identity_conflict");
	auto malformed = capped;
	malformed.payload.pop_back();
	reject(malformed, EINVAL, "malformed_payload");
	auto missing = build(payload, false);
	reject(missing, ENOENT, "missing_parent");
	assert(scalar(db,
		      "SELECT COUNT(*) FROM critical_operation_inbox WHERE operation_id=UNHEX('" +
			      hex_id(missing.operation_id) + "')") == 0);
	std::cout
		<< "PASS capped no-op, identity conflicts, malformed payload and missing-parent diagnostics\n";

	auto old = legacy_command(build(payload), payload);
	artifact_guild_payload decoded = {};
	assert(artifact_guild_command_decode_payload(old, &decoded));
	reject(old, EPROTONOSUPPORT, "legacy_uncommitted");
	// Seed the exact v1 inbox/result/outbox receipt using its historical hashes.
	std::vector<uint8_t> encoded, keys;
	assert(critical_command_encode(old, &encoded) == critical_command_codec_result::ok);
	for (const auto &key : old.keys)
	{
		append<uint8_t>(keys, static_cast<uint8_t>(key.type));
		append(keys, key.id);
	}
	artifact_guild_result old_result = {};
	old_result.artifact_count = 1;
	old_result.artifacts[0] = { ARTIFACT_VNUM, payload.artifacts[0].timer,
				    static_cast<int32_t>(ACTOR_PID), 0, 100 };
	std::array<uint8_t, ARTIFACT_GUILD_RESULT_BYTES> result_bytes;
	assert(artifact_guild_command_encode_result(old_result, &result_bytes));
	const auto operation = hex_id(old.operation_id);
	execute(db,
		"INSERT INTO critical_operation_inbox(operation_id,command_hash,keys_hash,command_type,schema_version,payload_version,status,durable_revision,result_payload) "
		"VALUES(UNHEX('" +
			operation + "'),UNHEX(SHA2(UNHEX('" +
			hex_bytes(encoded.data(), encoded.size()) +
			"'),256)),"
			"UNHEX(SHA2(UNHEX('" +
			hex_bytes(keys.data(), keys.size()) + "'),256)),9,1,1,1,100,UNHEX('" +
			hex_bytes(result_bytes.data(), result_bytes.size()) + "'))");
	execute(db,
		"INSERT INTO critical_outbox(operation_id,event_index,destination,event_type,payload_version,payload) VALUES(UNHEX('" +
			operation + "'),0,7,1,1,UNHEX('" +
			hex_bytes(result_bytes.data(), result_bytes.size()) + "'))");
	auto replay = critical_command_repository_apply(db, old);
	assert(replay.outcome == critical_apply_outcome::already_applied &&
	       replay.durable_revision == 100);
	assert(replay.result_size == result_bytes.size() &&
	       std::equal(result_bytes.begin(), result_bytes.end(), replay.result_payload.begin()));
	current_state();
	critical_outbox_record record = {};
	execute(db, "SELECT outbox_id,payload FROM critical_outbox WHERE operation_id=UNHEX('" +
			    operation + "')");
	MYSQL_RES *outbox = mysql_store_result(db);
	assert(outbox);
	MYSQL_ROW stored = mysql_fetch_row(outbox);
	assert(stored);
	auto lengths = mysql_fetch_lengths(outbox);
	record.outbox_id = strtoull(stored[0], nullptr, 10);
	record.operation_id = old.operation_id;
	record.destination = 7;
	record.event_type = 1;
	record.payload_version = 1;
	record.payload.assign(reinterpret_cast<uint8_t *>(stored[1]),
			      reinterpret_cast<uint8_t *>(stored[1]) + lengths[1]);
	mysql_free_result(outbox);
	assert(artifact_guild_transaction_outbox_delivery(record, nullptr) ==
	       critical_outbox_delivery_result::retryable_failure);
	artifact_guild_transaction_publish_outbox();
	artifact_guild_transaction_publish_outbox();
	assert(invalidations == 1);
	assert(artifact_guild_transaction_outbox_delivery(record, nullptr) ==
	       critical_outbox_delivery_result::delivered);
	current_state();
	execute(db, "DELETE FROM critical_outbox WHERE operation_id=UNHEX('" + operation + "')");
	std::cout << "PASS committed v1 receipt and old pending outbox; no state reapplication\n";

	// History records captures even if subsequent gameplay removed the entity.
	execute(db,
		"DELETE FROM artifact_domain_state WHERE vnum=" + std::to_string(ARTIFACT_VNUM));
	execute(db, "DELETE FROM artifacts WHERE vnum=" + std::to_string(ARTIFACT_VNUM));
	apply(build(payload));
	assert(scalar(db, "SELECT COUNT(*) FROM artifacts WHERE vnum=" +
				  std::to_string(ARTIFACT_VNUM)) == 0);
	assert(scalar(db, "SELECT COUNT(*) FROM artifact_domain_state WHERE vnum=" +
				  std::to_string(ARTIFACT_VNUM)) == 0);
	std::cout << "PASS history after removal does not recreate artifact state\n";
	cleanup(db);
	mysql_close(db);
}
