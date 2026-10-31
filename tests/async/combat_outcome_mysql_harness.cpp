#include "combat/frag_cap_repository.h"
#include "combat_intent_recovery_checks.h"
#include <chrono>
#include "combat/combat_outcome_command.h"
#include "persistence/critical_command_repository.h"
#include "world/epic_command.h"

#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <mysql.h>
#include <string>
#include <fstream>
#include <filesystem>
#include <iterator>

static bool lose_commit_ack = false, commit_ack_lost = false;
extern "C" int __real_mysql_real_query(MYSQL *, const char *, unsigned long);
extern "C" unsigned int __real_mysql_errno(MYSQL *);
extern "C" int __wrap_mysql_real_query(MYSQL *db, const char *sql, unsigned long length)
{
	const int result = __real_mysql_real_query(db, sql, length);
	if (!result && lose_commit_ack && length == 6 && !memcmp(sql, "COMMIT", 6))
	{
		lose_commit_ack = false;
		commit_ack_lost = true;
		return 1;
	}
	return result;
}
extern "C" unsigned int __wrap_mysql_errno(MYSQL *db)
{
	return commit_ack_lost ? 2013 : __real_mysql_errno(db);
}

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

std::string text_value(MYSQL *db, const std::string &sql)
{
	execute(db, sql);
	MYSQL_RES *result = mysql_store_result(db);
	assert(result);
	MYSQL_ROW row = mysql_fetch_row(result);
	assert(row && row[0]);
	const std::string value(row[0], mysql_fetch_lengths(result)[0]);
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
	entry.webinfo_at_capture = combat_webinfo::on;
	entry.role = role;
	entry.flags = COMBAT_PARTICIPANT_IN_ROOM;
	entry.level = 50;
	entry.racewar = 1;
	snprintf(entry.account_name.data(), entry.account_name.size(), "%s", ACCOUNT);
	snprintf(entry.description.data(), entry.description.size(), "%s",
		 role == combat_participant_role::killer ? "[50 &+RWarrior&n] Killer (Human)" :
							   "[50 Cleric] Victim (Orc)");
	entry.equipment = "<wielded> a warrior's &+Rsword&n\\edge\n";
	entry.log = "You hit the victim's shield.\r\n&+RThe victim falls.&n\r\n";
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
	const int64_t cap_start = std::chrono::duration_cast<std::chrono::microseconds>(
					  std::chrono::system_clock::now().time_since_epoch())
					  .count();
	execute(db, "UPDATE level_cap SET snapshot=NULL,level=30,level_good=0,level_evil=0");
	execute(db, "START TRANSACTION");
	frag_cap_state cap;
	assert(frag_cap_sql_adopt(db, 25, 56, cap_start, &cap) == frag_cap_store_result::ok);
	execute(db, "COMMIT");
	if (getenv("PVP_FULL_GROUP_ONLY"))
	{
		assert(std::string(getenv("ENVIRONMENT")) == "test");
		constexpr uint32_t first_pid = 4293000000U;
		execute(db, "INSERT INTO accounts(account_name) VALUES('" + std::string(ACCOUNT) +
				    "')");
		combat_outcome_payload full{};
		full.victim_pid = first_pid + 20;
		full.killer_allies = 20;
		full.room_vnum = 22800;
		full.prepared_at = 150;
		strcpy(full.room_name.data(), "Full racewar groups");
		full.participant_count = 40;
		for (size_t i = 0; i < 40; ++i)
		{
			const auto pid = first_pid + i;
			execute(db,
				"INSERT INTO player_data(pid,name,account_name,racewar) VALUES(" +
					std::to_string(pid) + ",'Group" + std::to_string(i) +
					"','" + ACCOUNT + "'," + (i < 20 ? "1" : "2") + ")");
			auto &entry = full.participants[i];
			entry = participant(pid, i < 20 ? combat_participant_role::killer_group :
							  combat_participant_role::victim_group);
			entry.racewar = i < 20 ? 1 : 2;
			entry.equipment.assign(COMBAT_OUTCOME_EQUIPMENT_MAX_BYTES, 'e');
			entry.log.assign(COMBAT_OUTCOME_LOG_MAX_BYTES, 'l');
			if (i < 20)
			{
				entry.flags |= COMBAT_PARTICIPANT_DIVINE_EPIC;
				entry.frag_delta = 5;
				entry.epic_delta = 150;
				entry.epic_boon_id = 7;
				entry.epic_base = 100;
			}
		}
		critical_operation_id id{};
		assert(critical_operation_id_generate(&id));
		critical_command command;
		assert(combat_outcome_command_build(&command, id, full));
		command.accepted_at_usec = cap_start;
		execute(db,
			"CREATE TRIGGER reject_full_group BEFORE INSERT ON combat_outcome_participant FOR EACH ROW "
			"BEGIN IF NEW.pid=" +
				std::to_string(first_pid + 39) +
				" THEN SIGNAL SQLSTATE '40001' SET MYSQL_ERRNO=1213,MESSAGE_TEXT='fixture'; END IF; END");
		assert(critical_command_repository_apply(db, command).outcome ==
		       critical_apply_outcome::retryable_failure);
		assert(scalar(db, "SELECT COUNT(*) FROM combat_outcome WHERE victim_pid=" +
					  std::to_string(full.victim_pid)) == 0);
		assert(scalar(db, "SELECT SUM(epic_revision) FROM player_data WHERE pid BETWEEN " +
					  std::to_string(first_pid) + " AND " +
					  std::to_string(first_pid + 39)) == 0);
		execute(db, "DROP TRIGGER reject_full_group");
		const auto first = critical_command_repository_apply(db, command);
		combat_outcome_result result{};
		assert(first.outcome == critical_apply_outcome::applied &&
		       first.result_size == 8192);
		assert(combat_outcome_command_decode_result(first.result_payload.data(),
							    first.result_size, &result));
		assert(result.participant_count == 40 &&
		       result.participants[39].pid == first_pid + 39);
		assert(result.participants[19].epic_delivery_delta == 150);
		const auto event =
			scalar(db, "SELECT pkill_event_id FROM combat_outcome WHERE victim_pid=" +
					   std::to_string(full.victim_pid));
		assert(scalar(db, "SELECT COUNT(*) FROM pkill_info WHERE event_id=" +
					  std::to_string(event)) == 40);
		assert(scalar(db, "SELECT MIN(OCTET_LENGTH(log)) FROM pkill_info WHERE event_id=" +
					  std::to_string(event)) == COMBAT_OUTCOME_LOG_MAX_BYTES);
		const auto replay = critical_command_repository_apply(db, command);
		assert(replay.outcome == critical_apply_outcome::already_applied &&
		       replay.result_size == first.result_size &&
		       replay.result_payload == first.result_payload);
		mysql_close(db);
		std::cout
			<< "full 20/20 SQL outcome: complete snapshots, rollback/retry and exact replay passed\n";
		return 0;
	}
	if (const char *directory = getenv("PVP_CAPTURE_COMMAND_DIR"))
	{
		// This mode is used only on the disposable schema created by the wrapper.
		assert(std::string(getenv("ENVIRONMENT")) == "test");
		execute(db, "SET time_zone='+00:00'");
		execute(db, "INSERT INTO accounts(account_name) VALUES('privacy-fixture')");
		execute(db,
			"INSERT INTO player_data(pid,name,account_name,racewar,act2) VALUES"
			"(100,'Alice','privacy-fixture',1,134217728),(101,'Bob','privacy-fixture',2,134217728)");
		std::ofstream ids(std::filesystem::path(directory) / "events.json");
		ids << '[';
		for (int battle = 0; battle < 5; ++battle)
		{
			std::ifstream file(std::filesystem::path(directory) /
						   (std::to_string(battle) + ".command"),
					   std::ios::binary);
			assert(file.good());
			std::vector<uint8_t> bytes((std::istreambuf_iterator<char>(file)), {});
			critical_command captured{};
			assert(critical_command_decode(bytes.data(), bytes.size(), &captured) ==
			       critical_command_codec_result::ok);
			const auto written = critical_command_repository_apply(db, captured);
			assert(written.outcome == critical_apply_outcome::applied);
			assert(critical_command_repository_apply(db, captured).outcome ==
			       critical_apply_outcome::already_applied);
			const auto event = scalar(db, "SELECT MAX(id) FROM pkill_event");
			if (battle)
				ids << ',';
			ids << event;
			assert(scalar(db, "SELECT COUNT(*) FROM pkill_info WHERE event_id=" +
						  std::to_string(event)) == 2);
			assert(scalar(db, "SELECT COUNT(*) FROM pkill_info WHERE event_id=" +
						  std::to_string(event) +
						  " AND log LIKE '%PRIVATE_HANDOFF_MARKER%'") == 0);
		}
		ids << ']';
		ids.close();
		assert(ids.good());
		mysql_close(db);
		std::cout
			<< "five real capture/codec/repository handoff events written and replayed\n";
		return 0;
	}

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
	payload.killer_allies = 5;
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
	payload.participants[1].webinfo_at_capture = combat_webinfo::off;
	payload.participants[1].equipment.clear();
	payload.participants[1].log.clear();

	critical_operation_id id = {};
	assert(critical_operation_id_generate(&id));
	critical_command command = {};
	assert(combat_outcome_command_build(&command, id, payload));
	command.accepted_at_usec = 1;
	const critical_apply_result applied = critical_command_repository_apply(db, command);
	assert(applied.outcome == critical_apply_outcome::applied);
	const auto event_id =
		scalar(db, "SELECT pkill_event_id FROM combat_outcome WHERE victim_pid=" +
				   std::to_string(VICTIM_PID));
	const std::string snapshot_where =
		" FROM pkill_info WHERE event_id=" + std::to_string(event_id) +
		" AND pid=" + std::to_string(KILLER_PID);
	assert(text_value(db, "SELECT player_description" + snapshot_where) ==
	       payload.participants[0].description.data());
	assert(text_value(db, "SELECT equip" + snapshot_where) ==
	       payload.participants[0].equipment);
	assert(text_value(db, "SELECT log" + snapshot_where) == payload.participants[0].log);
	assert(scalar(db, "SELECT webinfo_at_capture" + snapshot_where) == 1);
	assert(scalar(db,
		      "SELECT COUNT(*) FROM pkill_info WHERE event_id=" + std::to_string(event_id) +
			      " AND pid=" + std::to_string(VICTIM_PID) +
			      " AND webinfo_at_capture=0 AND equip='' AND log=''") == 1);
	execute(db, "UPDATE player_data SET act2=0 WHERE pid=" + std::to_string(KILLER_PID));
	assert(scalar(db, "SELECT webinfo_at_capture" + snapshot_where) == 1);
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
	assert(scalar(db, "SELECT COUNT(*) FROM pkill_info WHERE event_id=" +
				  std::to_string(event_id)) == 2);
	assert(text_value(db, "SELECT log" + snapshot_where) == payload.participants[0].log);

	// A failure after the first participant must roll back the whole snapshot/event.
	execute(db,
		"CREATE TRIGGER reject_combat_fixture BEFORE INSERT ON pkill_info FOR EACH ROW "
		"BEGIN IF NEW.log='reject_fixture' THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='fixture'; END IF; END");
	auto failed_payload = payload;
	failed_payload.participants[1].webinfo_at_capture = combat_webinfo::on;
	failed_payload.participants[1].log = "reject_fixture";
	critical_operation_id failed_id = {};
	assert(critical_operation_id_generate(&failed_id));
	critical_command failed_command = {};
	assert(combat_outcome_command_build(&failed_command, failed_id, failed_payload));
	failed_command.accepted_at_usec = 2;
	assert(critical_command_repository_apply(db, failed_command).outcome !=
	       critical_apply_outcome::applied);
	assert(scalar(db, "SELECT COUNT(*) FROM combat_outcome WHERE victim_pid=" + victim) == 1);
	assert(scalar(db, "SELECT COUNT(*) FROM pkill_info WHERE pid=" + killer) == 1);
	execute(db, "DROP TRIGGER reject_combat_fixture");
	// The identical command can succeed on retry after a transient storage failure.
	assert(critical_command_repository_apply(db, failed_command).outcome ==
	       critical_apply_outcome::applied);
	assert(critical_command_repository_apply(db, failed_command).outcome ==
	       critical_apply_outcome::already_applied);
	// A second outcome is not fenced by the first: its ledger rows continue from the
	// first's, whatever the saves wrote in between.
	execute(db, "UPDATE player_data SET frags=900 WHERE pid=" + killer);
	critical_operation_id second_id = {};
	assert(critical_operation_id_generate(&second_id));
	critical_command second = {};
	for (size_t index = 0; index < payload.participant_count; ++index)
	{
		payload.participants[index].webinfo_at_capture = combat_webinfo::on;
		payload.participants[index].equipment.assign(COMBAT_OUTCOME_EQUIPMENT_MAX_BYTES,
							     '\'');
		payload.participants[index].log.assign(COMBAT_OUTCOME_LOG_MAX_BYTES, '\\');
	}
	assert(combat_outcome_command_build(&second, second_id, payload));
	second.accepted_at_usec = 2;
	assert(critical_command_repository_apply(db, second).outcome ==
	       critical_apply_outcome::applied);
	assert(scalar(db, "SELECT COUNT(*) FROM combat_outcome WHERE victim_pid=" + victim) == 3);
	assert(scalar(db,
		      "SELECT COUNT(*) FROM combat_outcome WHERE killer_allies=5 AND victim_pid=" +
			      victim) == 3);
	assert(scalar(db, "SELECT frags_after FROM combat_frag_ledger WHERE pid=" + killer +
				  " AND frag_revision=2") == 400);
	assert(scalar(db, "SELECT balance_after FROM epic_ledger WHERE pid=" + killer +
				  " AND epic_revision=2") == 1100);
	assert(scalar(db, "SELECT frags FROM player_data WHERE pid=" + killer) == 900);
	const std::string latest_snapshot =
		" FROM pkill_info WHERE pid=" + killer + " ORDER BY id DESC LIMIT 1";
	assert(text_value(db, "SELECT equip" + latest_snapshot) ==
	       payload.participants[0].equipment);
	assert(text_value(db, "SELECT log" + latest_snapshot) == payload.participants[0].log);
	assert(critical_command_repository_apply(db, second).outcome ==
	       critical_apply_outcome::already_applied);

	// A v3 replay retains original text but cannot invent historical consent.
	auto legacy = second;
	assert(critical_operation_id_generate(&legacy.operation_id));
	legacy.payload_version = 3;
	legacy.payload.resize(legacy.payload.size() - payload.participant_count);
	assert(critical_command_repository_apply(db, legacy).outcome ==
	       critical_apply_outcome::applied);
	assert(scalar(db, "SELECT webinfo_at_capture IS NULL" + latest_snapshot) == 1);
	assert(text_value(db, "SELECT log" + latest_snapshot) == payload.participants[0].log);
	assert(critical_command_repository_apply(db, legacy).outcome ==
	       critical_apply_outcome::already_applied);
	// Prepared Divine epics are sequenced on the locked recipient row. The
	// player balance is credited later at its status/watermark checkpoint.
	auto prepared = payload;
	prepared.prepared_at = 150;
	for (auto &entry : prepared.participants)
	{
		entry.equipment.clear();
		entry.log.clear();
		entry.webinfo_at_capture = combat_webinfo::off;
		entry.wallet_delta_copper = 0;
	}
	prepared.participants[0].flags = COMBAT_PARTICIPANT_IN_ROOM |
					 COMBAT_PARTICIPANT_DIVINE_EPIC;
	prepared.participants[0].frag_delta = 100;
	prepared.participants[0].epic_delta = 150;
	prepared.participants[0].epic_boon_id = 7;
	prepared.participants[0].epic_base = 100;
	prepared.participants[1].racewar = 2;
	prepared.participants[1].epic_delta = 0;
	const auto before_revision =
		scalar(db, "SELECT epic_revision FROM player_data WHERE pid=" + killer);
	const auto before_balance = scalar(db, "SELECT epics FROM player_data WHERE pid=" + killer);
	auto write_prepared = [&]
	{
		critical_operation_id id = {};
		assert(critical_operation_id_generate(&id));
		critical_command cmd;
		assert(combat_outcome_command_build(&cmd, id, prepared));
		cmd.accepted_at_usec = 3;
		return cmd;
	};
	const auto first_prepared = write_prepared();
	const auto first_written = critical_command_repository_apply(db, first_prepared);
	assert(first_written.outcome == critical_apply_outcome::applied);
	combat_outcome_result prepared_result;
	assert(combat_outcome_command_decode_result(first_written.result_payload.data(),
						    first_written.result_size, &prepared_result));
	assert(prepared_result.participants[0].epic_revision == before_revision + 1);
	assert(prepared_result.participants[0].epic_delivery_previous == 0);
	assert(prepared_result.participants[0].epic_delivery_delta == 150);
	assert(critical_command_repository_apply(db, first_prepared).outcome ==
	       critical_apply_outcome::already_applied);
	const auto second_written = critical_command_repository_apply(db, write_prepared());
	assert(second_written.outcome == critical_apply_outcome::applied);
	assert(combat_outcome_command_decode_result(second_written.result_payload.data(),
						    second_written.result_size, &prepared_result));
	assert(prepared_result.participants[0].epic_revision == before_revision + 2 &&
	       prepared_result.participants[0].epic_delivery_previous == before_revision + 1);
	assert(scalar(db, "SELECT epics FROM player_data WHERE pid=" + killer) == before_balance);
	execute(db,
		"CREATE TRIGGER reject_divine_ledger BEFORE INSERT ON epic_ledger FOR EACH ROW "
		"BEGIN IF NEW.reason_type=" +
			std::to_string(static_cast<uint16_t>(epic_reason_type::divine_pvp_award)) +
			" THEN SIGNAL SQLSTATE '40001' SET MYSQL_ERRNO=1213,MESSAGE_TEXT='fixture'; END IF; END");
	const auto failed_prepared = write_prepared();
	assert(critical_command_repository_apply(db, failed_prepared).outcome ==
	       critical_apply_outcome::retryable_failure);
	assert(scalar(db, "SELECT epic_revision FROM player_data WHERE pid=" + killer) ==
	       before_revision + 2);
	execute(db, "DROP TRIGGER reject_divine_ledger");
	const auto retried_prepared = critical_command_repository_apply(db, failed_prepared);
	assert(retried_prepared.outcome == critical_apply_outcome::applied);
	assert(combat_outcome_command_decode_result(retried_prepared.result_payload.data(),
						    retried_prepared.result_size,
						    &prepared_result));
	assert(prepared_result.participants[0].epic_revision == before_revision + 3 &&
	       prepared_result.participants[0].epic_delivery_previous == before_revision + 2);
	assert(scalar(db,
		      "SELECT COUNT(*) FROM critical_operation_inbox WHERE command_type=2 "
		      "AND (expected_outbox_events IS NULL OR expected_outbox_events<>0)") == 0);
	assert(scalar(db,
		      "SELECT COUNT(*) FROM critical_operation_inbox WHERE command_type=8 "
		      "AND result_code=0 AND (expected_outbox_events IS NULL OR expected_outbox_events<>1)") ==
	       0);

	// Exercise real cap failure after ordinary ledgers have been prepared.
	auto credit = payload;
	credit.participants[0].frag_delta = 5;
	credit.participants[1].frag_delta = -5;
	for (size_t index = 0; index < credit.participant_count; ++index)
	{
		credit.participants[index].epic_delta = 0;
		credit.participants[index].wallet_delta_copper = 0;
	}
	const uint64_t ledger_before =
		scalar(db, "SELECT COUNT(*) FROM combat_frag_ledger WHERE pid=" + killer);
	for (int pass = 0; pass < 4; ++pass)
	{
		critical_operation_id credit_id;
		assert(critical_operation_id_generate(&credit_id));
		critical_command contribution;
		assert(combat_outcome_command_build(&contribution, credit_id, credit));
		contribution.accepted_at_usec = cap_start;
		if (!pass)
		{
			execute(db,
				"CREATE TRIGGER reject_cap_fixture BEFORE UPDATE ON level_cap FOR EACH ROW "
				"SIGNAL SQLSTATE '40001' SET MYSQL_ERRNO=1213,MESSAGE_TEXT='fixture'");
			assert(critical_command_repository_apply(db, contribution).outcome ==
			       critical_apply_outcome::retryable_failure);
			assert(scalar(db, "SELECT COUNT(*) FROM combat_frag_ledger WHERE pid=" +
						  killer) == ledger_before);
			assert(frag_cap_sql_load(db, &cap) == frag_cap_store_result::ok &&
			       cap.earned == (std::array<uint64_t, 2>{}) && cap.level == 31);
			execute(db, "DROP TRIGGER reject_cap_fixture");
		}
		if (!pass)
		{
			const auto snapshot = text_value(db, "SELECT HEX(snapshot) FROM level_cap");
			check_combat_intent_recovery(
				contribution, [&](const auto &cmd)
				{ return critical_command_repository_apply(db, cmd); },
				[&] { execute(db, "UPDATE level_cap SET snapshot=UNHEX('00')"); },
				[&] {
					execute(db, "UPDATE level_cap SET snapshot=UNHEX('" +
							    snapshot + "')");
				});
		}
		else
			assert(critical_command_repository_apply(db, contribution).outcome ==
			       critical_apply_outcome::applied);
		assert(frag_cap_sql_load(db, &cap) == frag_cap_store_result::ok);
		assert(cap.level == 31 && cap.earned[0] == static_cast<uint64_t>((pass + 1) * 5));
		const auto confirmed = cap;
		assert(critical_command_repository_apply(db, contribution).outcome ==
		       critical_apply_outcome::already_applied);
		assert(frag_cap_sql_load(db, &cap) == frag_cap_store_result::ok &&
		       cap == confirmed);
	}
	critical_operation_id ambiguous_id;
	assert(critical_operation_id_generate(&ambiguous_id));
	critical_command ambiguous;
	assert(combat_outcome_command_build(&ambiguous, ambiguous_id, credit));
	ambiguous.accepted_at_usec = cap_start;
	lose_commit_ack = true;
	const auto unknown = critical_command_repository_apply(db, ambiguous);
	assert(commit_ack_lost && unknown.outcome == critical_apply_outcome::ambiguous_commit);
	commit_ack_lost = false;
	assert(frag_cap_sql_load(db, &cap) == frag_cap_store_result::ok && cap.earned[0] == 25);
	const auto committed_cap = cap;
	assert(critical_command_repository_apply(db, ambiguous).outcome ==
	       critical_apply_outcome::already_applied);
	assert(frag_cap_sql_load(db, &cap) == frag_cap_store_result::ok && cap == committed_cap);
	std::cout
		<< "lost COMMIT acknowledgement: receipt recovery preserves exactly-once faction credit\n";
	MYSQL *blocker = mysql_init(nullptr);
	assert(blocker &&
	       mysql_real_connect(blocker, getenv("DB_HOST"), getenv("DB_USER"),
				  getenv("DB_PASSWD"), getenv("DB_NAME"), port, nullptr, 0));
	execute(db, "SET SESSION innodb_lock_wait_timeout=1");
	for (const auto &lock_sql :
	     { "SELECT pid FROM player_data WHERE pid=" + killer + " FOR UPDATE",
	       "SELECT pid FROM combat_frag_ledger WHERE pid=" + killer +
		       " AND frag_revision=(SELECT frag_revision FROM player_data WHERE pid=" +
		       killer + ") FOR UPDATE",
	       "SELECT pid FROM epic_ledger WHERE pid=" + killer +
		       " AND epic_revision=(SELECT epic_revision FROM player_data WHERE pid=" +
		       killer + ") FOR UPDATE" })
	{
		critical_operation_id locked_id;
		assert(critical_operation_id_generate(&locked_id));
		critical_command locked;
		assert(combat_outcome_command_build(&locked, locked_id, credit));
		locked.accepted_at_usec = cap_start;
		execute(blocker, "START TRANSACTION");
		execute(blocker, lock_sql);
		MYSQL_RES *rows = mysql_store_result(blocker);
		assert(rows && mysql_num_rows(rows) >= 1);
		mysql_free_result(rows);
		const auto before = scalar(db, "SELECT COUNT(*) FROM critical_operation_inbox");
		const auto timed_out = critical_command_repository_apply(db, locked);
		assert(timed_out.outcome == critical_apply_outcome::retryable_failure &&
		       timed_out.error_code == 1205);
		assert(scalar(db, "SELECT COUNT(*) FROM critical_operation_inbox") == before);
		execute(blocker, "ROLLBACK");
		assert(critical_command_repository_apply(db, locked).outcome ==
		       critical_apply_outcome::applied);
		assert(critical_command_repository_apply(db, locked).outcome ==
		       critical_apply_outcome::already_applied);
	}
	mysql_close(blocker);
	std::cout
		<< "enqueue crash, corrupt-cap repair, and player/frag/epic lock-timeout recovery passed\n";
	cleanup(db);
	mysql_close(db);
	std::cout
		<< "combat outcome snapshots, size limits, rollback/retry, replay, and ledgers passed\n";
}
