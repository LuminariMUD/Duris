#include "combat/combat_outcome_command.h"
#include "persistence/critical_command_repository.h"

#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <mysql.h>
#include <string>

namespace
{
constexpr uint32_t KILLER_PID = 4294000101U;
constexpr uint32_t VICTIM_PID = 4294000102U;
constexpr const char *ACCOUNT = "combat-harness-account";

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

void cleanup(MYSQL *db)
{
	execute(db, "DELETE FROM critical_outbox WHERE operation_id IN (SELECT operation_id FROM "
		    "combat_outcome WHERE victim_pid=" +
			    std::to_string(VICTIM_PID) + ")");
	execute(db, "DELETE FROM epic_ledger WHERE pid=" + std::to_string(KILLER_PID) +
			    " AND reason_id=" + std::to_string(VICTIM_PID));
	execute(db, "DELETE FROM currency_ledger WHERE pid=" + std::to_string(KILLER_PID) +
			    " AND reason_id=" + std::to_string(VICTIM_PID));
	execute(db, "DELETE FROM combat_frag_ledger WHERE pid IN (" + std::to_string(KILLER_PID) +
			    "," + std::to_string(VICTIM_PID) + ")");
	execute(db, "DELETE FROM combat_outcome_participant WHERE pid IN (" +
			    std::to_string(KILLER_PID) + "," + std::to_string(VICTIM_PID) + ")");
	execute(db,
		"DELETE p FROM pkill_info p LEFT JOIN combat_outcome c ON c.pkill_event_id=p.event_id "
		"WHERE p.pid IN (" +
			std::to_string(KILLER_PID) + "," + std::to_string(VICTIM_PID) + ")");
	execute(db,
		"DELETE e FROM pkill_event e LEFT JOIN combat_outcome c ON c.pkill_event_id=e.id "
		"WHERE c.victim_pid=" +
			std::to_string(VICTIM_PID));
	execute(db, "DELETE FROM combat_outcome WHERE victim_pid=" + std::to_string(VICTIM_PID));
	execute(db, "DELETE FROM critical_operation_inbox WHERE command_type IN (2,3,8) AND "
		    "created_at >= @combat_harness_started");
	execute(db, "DELETE FROM combat_frag_baseline WHERE pid IN (" + std::to_string(KILLER_PID) +
			    "," + std::to_string(VICTIM_PID) + ")");
	execute(db, "DELETE FROM epic_balance_baseline WHERE pid IN (" +
			    std::to_string(KILLER_PID) + "," + std::to_string(VICTIM_PID) + ")");
	execute(db, "DELETE FROM currency_wallet_baseline WHERE pid=" + std::to_string(KILLER_PID));
	execute(db,
		std::string("DELETE FROM currency_bank_baseline WHERE bank_id IN (SELECT id FROM "
			    "account_banks WHERE account_name='") +
			ACCOUNT + "')");
	execute(db, "DELETE FROM progress WHERE pid IN (" + std::to_string(KILLER_PID) + "," +
			    std::to_string(VICTIM_PID) + ")");
	execute(db, "DELETE FROM frag_leaderboard WHERE pid IN (" + std::to_string(KILLER_PID) +
			    "," + std::to_string(VICTIM_PID) + ")");
	execute(db, "DELETE FROM player_data WHERE pid IN (" + std::to_string(KILLER_PID) + "," +
			    std::to_string(VICTIM_PID) + ")");
	execute(db, "DELETE FROM account_banks WHERE account_name='" + std::string(ACCOUNT) + "'");
	execute(db, "DELETE FROM accounts WHERE account_name IN ('" + std::string(ACCOUNT) +
			    "','combat-victim-account')");
}

combat_outcome_participant participant(uint32_t pid, combat_participant_role role)
{
	combat_outcome_participant entry = {};
	entry.pid = pid;
	entry.role = role;
	entry.flags = COMBAT_PARTICIPANT_IN_ROOM;
	entry.level = 50;
	entry.racewar = 1;
	snprintf(entry.account_name.data(), entry.account_name.size(), "%s", ACCOUNT);
	snprintf(entry.description.data(), entry.description.size(), "%s",
		 role == combat_participant_role::killer ? "Killer" : "Victim");
	return entry;
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
	execute(db, "SET @combat_harness_started=CURRENT_TIMESTAMP(6)");
	cleanup(db);
	execute(db, "INSERT INTO accounts(account_name) VALUES('" + std::string(ACCOUNT) +
			    "'),('combat-victim-account')");
	execute(db, "INSERT INTO account_banks(account_name,racewar) VALUES('" +
			    std::string(ACCOUNT) + "',1)");
	execute(db, "INSERT INTO player_data(pid,name,account_name,racewar,frags,epics,copper,"
		    "silver,gold,platinum) VALUES(" +
			    std::to_string(KILLER_PID) + ",'CombatKiller','" + ACCOUNT +
			    "',1,200,100,5,0,0,0),(" + std::to_string(VICTIM_PID) +
			    ",'CombatVictim','combat-victim-account',2,300,0,0,0,0,0)");
	execute(db, "INSERT INTO frag_leaderboard(pid,account_name,char_name,total_frags,racewar) "
		    "VALUES(" +
			    std::to_string(KILLER_PID) + ",'" + ACCOUNT +
			    "','CombatKiller',200,1),(" + std::to_string(VICTIM_PID) +
			    ",'combat-victim-account','CombatVictim',300,2)");

	combat_outcome_payload payload = {};
	payload.victim_pid = VICTIM_PID;
	payload.room_vnum = 1234;
	snprintf(payload.room_name.data(), payload.room_name.size(), "%s", "Combat Harness Room");
	payload.participant_count = 2;
	payload.participants[0] = participant(KILLER_PID, combat_participant_role::killer);
	payload.participants[0].frag_delta = 100;
	payload.participants[0].epic_delta = 500;
	payload.participants[0].wallet_delta_copper = 10000;
	payload.participants[1] = participant(VICTIM_PID, combat_participant_role::victim);
	payload.participants[1].racewar = 2;
	payload.participants[1].account_name.fill('\0');
	snprintf(payload.participants[1].account_name.data(),
		 payload.participants[1].account_name.size(), "%s", "combat-victim-account");
	payload.participants[1].frag_delta = -100;

	critical_operation_id id = {};
	assert(critical_operation_id_generate(&id));
	critical_command command = {};
	assert(combat_outcome_command_build(&command, id, payload));
	command.accepted_at_usec = 1;
	const critical_apply_result applied = critical_command_repository_apply(db, command);
	assert(applied.outcome == critical_apply_outcome::applied);
	// Frags, epic points and blood money are memory's: the submit changed them and the
	// players' saves write them. The outcome leaves the balances alone and records the
	// kill, the frag and epic ledgers (continued from their last rows) and the leaderboard.
	const auto killer = std::to_string(KILLER_PID), victim = std::to_string(VICTIM_PID);
	assert(scalar(db, "SELECT frags FROM player_data WHERE pid=" + killer) == 200);
	assert(scalar(db, "SELECT epics FROM player_data WHERE pid=" + killer) == 100);
	assert(scalar(db, "SELECT copper FROM player_data WHERE pid=" + killer) == 5);
	assert(scalar(db, "SELECT frag_revision FROM player_data WHERE pid=" + killer) == 1);
	assert(scalar(db, "SELECT COUNT(*) FROM combat_outcome_participant WHERE operation_id IN "
			  "(SELECT operation_id FROM combat_outcome WHERE victim_pid=" +
				  victim + ")") == 2);
	assert(scalar(db, "SELECT frags_after FROM combat_frag_ledger WHERE pid=" + killer) == 300);
	assert(scalar(db, "SELECT frags_after FROM combat_frag_ledger WHERE pid=" + victim) == 200);
	assert(scalar(db, "SELECT total_frags FROM frag_leaderboard WHERE pid=" + killer) == 300);
	assert(scalar(db, "SELECT balance_after FROM epic_ledger WHERE pid=" + killer +
				  " AND reason_id=" + victim) == 600);
	assert(scalar(db, "SELECT COUNT(*) FROM currency_ledger WHERE pid=" + killer) == 0);

	const critical_apply_result replay = critical_command_repository_apply(db, command);
	assert(replay.outcome == critical_apply_outcome::already_applied);
	// A second outcome is not fenced by the first: its ledger rows continue from the
	// first's, whatever the saves wrote in between.
	execute(db, "UPDATE player_data SET frags=900 WHERE pid=" + killer);
	critical_operation_id second_id = {};
	assert(critical_operation_id_generate(&second_id));
	critical_command second = {};
	assert(combat_outcome_command_build(&second, second_id, payload));
	second.accepted_at_usec = 2;
	assert(critical_command_repository_apply(db, second).outcome ==
	       critical_apply_outcome::applied);
	assert(scalar(db, "SELECT COUNT(*) FROM combat_outcome WHERE victim_pid=" + victim) == 2);
	assert(scalar(db, "SELECT frags_after FROM combat_frag_ledger WHERE pid=" + killer +
				  " AND frag_revision=2") == 400);
	assert(scalar(db, "SELECT balance_after FROM epic_ledger WHERE pid=" + killer +
				  " AND epic_revision=2") == 1100);
	assert(scalar(db, "SELECT frags FROM player_data WHERE pid=" + killer) == 900);

	cleanup(db);
	mysql_close(db);
	std::cout
		<< "combat outcome apply, replay, ledgers across saves, and the untouched balances passed\n";
}
