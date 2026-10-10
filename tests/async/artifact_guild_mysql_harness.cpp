#include "guild/artifact_guild_command.h"
#include "persistence/critical_command_repository.h"

#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <iostream>
#include <mysql.h>
#include <string>

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

	critical_operation_id parent = {};
	assert(critical_operation_id_generate(&parent));
	insert_parent(db, parent);
	artifact_guild_payload payload = {};
	payload.parent_operation_id = parent;
	payload.actor_pid = ACTOR_PID;
	payload.guild_id = GUILD_ID;
	payload.prestige_delta = 5;
	payload.construction_delta = 1;
	payload.artifact_count = 1;
	payload.artifacts[0] = { ARTIFACT_VNUM,
				 ARTIFACT_DELTA_FEED,
				 0,
				 OPENING_TIMER,
				 OPENING_TIMER + 3600,
				 static_cast<int32_t>(ACTOR_PID),
				 static_cast<int32_t>(ACTOR_PID),
				 0,
				 0 };
	critical_operation_id child = {};
	assert(critical_operation_id_derive(parent, 0x41475431, ACTOR_PID, &child));
	critical_command command = {};
	assert(artifact_guild_command_build(&command, child, payload));
	command.accepted_at_usec = 1;
	const critical_apply_result applied = critical_command_repository_apply(db, command);
	assert(applied.outcome == critical_apply_outcome::applied);
	assert(scalar(db, "SELECT timer_epoch FROM artifact_domain_state WHERE vnum=" +
				  std::to_string(ARTIFACT_VNUM)) == OPENING_TIMER + 3600);
	assert(scalar(db, "SELECT prestige FROM guilds WHERE id=" + std::to_string(GUILD_ID)) ==
	       100);
	assert(scalar(db, "SELECT construction FROM guilds WHERE id=" + std::to_string(GUILD_ID)) ==
	       11);
	assert(scalar(db, "SELECT COUNT(*) FROM artifact_delta_ledger WHERE vnum=" +
				  std::to_string(ARTIFACT_VNUM)) == 1);
	assert(scalar(db, "SELECT COUNT(*) FROM guild_outcome_ledger WHERE guild_id=" +
				  std::to_string(GUILD_ID)) == 1);
	const critical_apply_result replay = critical_command_repository_apply(db, command);
	assert(replay.outcome == critical_apply_outcome::already_applied);

	critical_operation_id stale_parent = {};
	assert(critical_operation_id_generate(&stale_parent));
	insert_parent(db, stale_parent);
	payload.parent_operation_id = stale_parent;
	critical_operation_id stale_child = {};
	assert(critical_operation_id_derive(stale_parent, 0x41475431, ACTOR_PID, &stale_child));
	critical_command stale = {};
	assert(artifact_guild_command_build(&stale, stale_child, payload));
	stale.accepted_at_usec = 2;
	const critical_apply_result rejected = critical_command_repository_apply(db, stale);
	assert(rejected.outcome == critical_apply_outcome::terminal_failure);
	assert(rejected.error_code == ESTALE);
	assert(scalar(db, "SELECT COUNT(*) FROM artifact_guild_outcome WHERE actor_pid=" +
				  std::to_string(ACTOR_PID)) == 1);

	// Another ledgered transaction advanced the artifact's revision without changing its
	// timer or soul: a feed captured from those still applies, on top of that revision.
	execute(db, "UPDATE artifact_domain_state SET revision=revision+5 WHERE vnum=" +
			    std::to_string(ARTIFACT_VNUM));
	critical_operation_id later_parent = {};
	assert(critical_operation_id_generate(&later_parent));
	insert_parent(db, later_parent);
	payload.parent_operation_id = later_parent;
	payload.expected_guild_revision = 1;
	payload.artifacts[0].expected_timer = OPENING_TIMER + 3600;
	payload.artifacts[0].timer = OPENING_TIMER + 7200;
	critical_operation_id later_child = {};
	assert(critical_operation_id_derive(later_parent, 0x41475431, ACTOR_PID, &later_child));
	critical_command later = {};
	assert(artifact_guild_command_build(&later, later_child, payload));
	later.accepted_at_usec = 3;
	assert(critical_command_repository_apply(db, later).outcome ==
	       critical_apply_outcome::applied);
	assert(scalar(db, "SELECT timer_epoch FROM artifact_domain_state WHERE vnum=" +
				  std::to_string(ARTIFACT_VNUM)) == OPENING_TIMER + 7200);
	assert(scalar(db, "SELECT revision FROM artifact_domain_state WHERE vnum=" +
				  std::to_string(ARTIFACT_VNUM)) == 7);

	cleanup(db);
	mysql_close(db);
	std::cout
		<< "artifact/guild atomic threshold apply, replay, stale rejection, revision advance, and ledgers passed\n";
}
