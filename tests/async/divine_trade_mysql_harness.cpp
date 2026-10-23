#include "economy/divine_trade_repository.h"
#include "player/player_snapshot_codec.h"
#include "player/player_snapshot_repository.h"
#include <openssl/sha.h>
#include "persistence/critical_command_repository.h"
#include "ships/ships.h"
#include "persistence/maintenance_repository.c"

#include <algorithm>
#include <cstdlib>
#include <iostream>
#include <string>

namespace
{
void require(bool ok, const std::string &message)
{
	if (!ok)
	{
		std::cerr << "FAILED: " << message << '\n';
		std::exit(1);
	}
}
std::string environment(const char *name)
{
	const char *value = std::getenv(name);
	require(value && *value, std::string("missing fixture environment ") + name);
	return value;
}
void execute(MYSQL *db, const std::string &sql)
{
	require(mysql_real_query(db, sql.data(), sql.size()) == 0,
		std::string("synthetic query failed: ") + mysql_error(db));
}
std::string scalar(MYSQL *db, const std::string &sql)
{
	execute(db, sql);
	MYSQL_RES *rows = mysql_store_result(db);
	MYSQL_ROW row = rows ? mysql_fetch_row(rows) : nullptr;
	require(row && row[0], "missing synthetic scalar");
	const std::string result = row[0];
	mysql_free_result(rows);
	return result;
}
}

int main()
{
	require(environment("ENVIRONMENT") == "test", "disposable test environment required");
	MYSQL *db = mysql_init(nullptr);
	const auto host = environment("DB_HOST"), user = environment("DB_USER"),
		   password = environment("DB_PASSWD"), name = environment("DB_NAME");
	require(mysql_real_connect(db, host.c_str(), user.c_str(), password.c_str(), name.c_str(),
				   std::stoul(environment("DB_PORT")), nullptr, 0),
		"disposable database connection failed");
	const std::string triggers[] = { "BEFORE INSERT ON critical_operation_inbox",
					 "BEFORE UPDATE ON player_data",
					 "BEFORE INSERT ON ship_slots",
					 "BEFORE UPDATE ON ship_crew",
					 "BEFORE INSERT ON ship_cargo_market_mods",
					 "BEFORE INSERT ON ship_cargo_prices",
					 "BEFORE INSERT ON divine_trade_state",
					 "BEFORE UPDATE ON divine_trade_state",
					 "BEFORE UPDATE ON critical_operation_inbox",
					 "BEFORE INSERT ON critical_outbox" };
	for (unsigned scenario = 0; scenario < std::size(triggers); ++scenario)
	{
		const bool contraband = scenario % 2;
		const bool zero_sale = scenario == 9;
		const int slot_type = contraband ? SLOT_CONTRABAND : SLOT_CARGO;
		const auto goods = contraband ? divine_trade_goods::contraband :
						divine_trade_goods::cargo;
		const std::string market_type = contraband ? "CONTRABAND" : "CARGO";
		const uint32_t pid = 41 + scenario, ship_id = 101 + scenario;
		const std::string player = "Trader" + std::to_string(scenario);
		const std::string account_name = "trade_case_" + std::to_string(scenario);
		execute(db, "INSERT INTO accounts(account_name) VALUES('" + account_name + "')");
		execute(db,
			"INSERT INTO player_data(pid,name,account_name,copper,silver,gold,platinum,wallet_revision) VALUES(" +
				std::to_string(pid) + ",'" + player + "','" + account_name +
				"',11,12,13,14,7)");
		execute(db, "INSERT INTO ships(id,owner_name,ship_name,ship_class) VALUES(" +
				    std::to_string(ship_id) + ",'" + player +
				    "','Trade fixture',0)");
		execute(db,
			"INSERT INTO ship_slots(ship_id,slot_index,slot_type,item_index,position,timer,val0,val1,val2,val3,val4) VALUES(" +
				std::to_string(ship_id) + ",3," + std::to_string(slot_type) +
				",2," + std::to_string(SLOT_HOLD) + ",0,9,900,-1,-1,-1)");
		execute(db,
			"INSERT INTO ship_crew(ship_id,crew_index,sail_skill,guns_skill,rpar_skill,sail_chief,guns_chief,rpar_chief) VALUES(" +
				std::to_string(ship_id) + ",0,0,0,0,0,0,0)");
		execute(db,
			"INSERT INTO ship_cargo_market_mods(type,port_id,cargo_type,modifier) VALUES('" +
				market_type + "',2,2,1),('" + market_type +
				"',4,2,1) ON DUPLICATE KEY UPDATE modifier=1");
		execute(db,
			"INSERT INTO ship_cargo_prices(type,port_id,cargo_type,price) VALUES('" +
				market_type + "',2,2,100),('" + market_type +
				"',4,2,120) ON DUPLICATE KEY UPDATE price=VALUES(price)");
		uint64_t generation = 0;
		require(divine_trade_sql_generation(db, &generation, false),
			"restore trade generation");
		critical_entity_key account;
		require(currency_account_key(account_name.c_str(), 0, &account),
			"canonical account");
		critical_operation_id buy_id{}, sell_id{};
		require(critical_operation_id_generate(&buy_id) &&
				critical_operation_id_generate(&sell_id),
			"trade identities");
		divine_boon_slot boon;
		boon.id = 17;
		boon.category = divine_boon_category::cargo;
		boon.starts_at = 100;
		boon.expires_at = 14500;
		boon.source_port = boon.cargo_commodity = boon.contraband_commodity = 2;
		boon.destination_port = 4;
		divine_trade_purchase buy;
		buy.operation = buy_id;
		buy.goods = goods;
		buy.account = account.id;
		buy.ship_id = ship_id;
		buy.full_hold = 10;
		buy.slot = 3;
		buy.source_port = 2;
		buy.at = 101;
		buy.quantity = 1;
		buy.paid = 100;
		buy.slot_quantity_before = 9;
		buy.slot_basis_before = 900;
		divine_trade_payload purchase;
		purchase.pid = purchase.ship_owner_pid = pid;
		purchase.ship_id = ship_id;
		purchase.generation = generation;
		purchase.wallet_revision = 7;
		purchase.admitted_at = 101;
		purchase.payment = -100;
		purchase.wallet_after.amount = { 1, 3, 3, 15 };
		purchase.slots_after.push_back(
			{ 3, slot_type, 2, SLOT_HOLD, 0, { 10, 1000, -1, -1, -1 } });
		purchase.slots_before.push_back(
			{ 3, slot_type, 2, SLOT_HOLD, 0, { 9, 900, -1, -1, -1 } });
		purchase.market_after.push_back({ 2, 2, goods, 1.03f, 100 });
		require(divine_trade_prepare_purchase({}, boon, buy, &purchase.book_after),
			"prepare purchase provenance");
		critical_command command;
		require(divine_trade_command_build(&command, buy_id, purchase),
			"prepare purchase command");
		if (!scenario)
		{
			execute(db, "START TRANSACTION");
			execute(db, "DELETE FROM ship_slots WHERE slot_index=3 AND ship_id=" +
					    std::to_string(ship_id));
			execute(db,
				"DELETE FROM ship_crew WHERE ship_id=" + std::to_string(ship_id));
			auto implicit = purchase;
			implicit.slots_before = { flatfile_ship_empty_slot(3) };
			implicit.slots_after[0].values[0] = 1;
			implicit.slots_after[0].values[1] = 100;
			critical_command implicit_command;
			require(divine_trade_command_build(&implicit_command, buy_id, implicit),
				"implicit empty command");
			divine_trade_result implicit_result;
			unsigned int implicit_error = 0;
			bool implicit_mutated = false;
			require(divine_trade_sql_execute(db, implicit_command, &implicit_result,
							 &implicit_error, &implicit_mutated) &&
					!implicit_error && implicit_mutated,
				"native empty slot/crew materialization was refused");
			execute(db, "ROLLBACK");
		}
		for (int changed_field = 0; changed_field < 2; ++changed_field)
		{
			const std::string change =
				changed_field ?
					"UPDATE ship_crew SET sail_chief=1 WHERE ship_id=" +
						std::to_string(ship_id) :
					"UPDATE ship_slots SET val0=8,val1=800 WHERE slot_index=3 AND ship_id=" +
						std::to_string(ship_id);
			execute(db, change);
			critical_operation_id stale_id;
			require(critical_operation_id_generate(&stale_id),
				"stale ship operation id");
			auto stale = purchase;
			stale.book_after.lots.back().purchase = stale_id;
			critical_command stale_command;
			require(divine_trade_command_build(&stale_command, stale_id, stale),
				"stale ship capture");
			require(critical_command_repository_apply(db, stale_command).error_code ==
						ESTALE &&
					scalar(db,
					       "SELECT wallet_revision FROM player_data WHERE pid=" +
						       std::to_string(pid)) == "7",
				"delayed trade changed wallet despite a stale ship");
			if (changed_field)
			{
				require(scalar(db,
					       "SELECT sail_chief FROM ship_crew WHERE ship_id=" +
						       std::to_string(ship_id)) == "1",
					"stale trade reverted chief");
				execute(db, "UPDATE ship_crew SET sail_chief=0 WHERE ship_id=" +
						    std::to_string(ship_id));
			}
			else
			{
				require(scalar(db,
					       "SELECT val0 FROM ship_slots WHERE slot_index=3 AND ship_id=" +
						       std::to_string(ship_id)) == "8",
					"stale trade resurrected cargo");
				execute(db,
					"UPDATE ship_slots SET val0=9,val1=900 WHERE slot_index=3 AND ship_id=" +
						std::to_string(ship_id));
			}
		}
		const auto fail = [&]
		{
			const auto body =
				scenario == 7 ?
					" FOR EACH ROW BEGIN IF OLD.account_key=0 AND OLD.boon_id=0 THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='divine trade fault'; END IF; END" :
					" FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='divine trade fault'";
			execute(db,
				"CREATE TRIGGER divine_trade_fault " + triggers[scenario] + body);
			const auto market_before = scalar(
				db,
				"SELECT GROUP_CONCAT(CONCAT(type,':',port_id,':',cargo_type,':',modifier) ORDER BY port_id,cargo_type,modifier SEPARATOR ';') FROM ship_cargo_market_mods");
			const auto prices_before = scalar(
				db,
				"SELECT GROUP_CONCAT(CONCAT(type,':',port_id,':',cargo_type,':',price) ORDER BY port_id,cargo_type,price SEPARATOR ';') FROM ship_cargo_prices");
			const auto generation_before = scalar(
				db,
				"SELECT revision FROM divine_trade_state WHERE account_key=0 AND boon_id=0");
			const auto result = critical_command_repository_apply(db, command);
			require(result.outcome != critical_apply_outcome::applied &&
					result.outcome != critical_apply_outcome::already_applied,
				"fault did not reject the transaction at boundary " +
					std::to_string(scenario));
			execute(db, "DROP TRIGGER divine_trade_fault");
			require(market_before ==
						scalar(db,
						       "SELECT GROUP_CONCAT(CONCAT(type,':',port_id,':',cargo_type,':',modifier) ORDER BY port_id,cargo_type,modifier SEPARATOR ';') FROM ship_cargo_market_mods") &&
					prices_before ==
						scalar(db,
						       "SELECT GROUP_CONCAT(CONCAT(type,':',port_id,':',cargo_type,':',price) ORDER BY port_id,cargo_type,price SEPARATOR ';') FROM ship_cargo_prices") &&
					generation_before ==
						scalar(db,
						       "SELECT revision FROM divine_trade_state WHERE account_key=0 AND boon_id=0"),
				"rejected trade changed market cells/prices or the generation");
		};
		const auto wallet = [&]
		{
			return scalar(
				db,
				"SELECT CONCAT(copper,':',silver,':',gold,':',platinum,':',wallet_revision) FROM player_data WHERE pid=" +
					std::to_string(pid));
		};
		const auto quantity = [&]
		{
			return scalar(
				db,
				"SELECT CONCAT(slot_type,':',val0) FROM ship_slots WHERE ship_id=" +
					std::to_string(ship_id) + " AND slot_index=3");
		};
		fail();
		require(wallet() == "11:12:13:14:7" &&
				quantity() == std::to_string(slot_type) + ":9" &&
				scalar(db,
				       "SELECT COUNT(*) FROM divine_trade_state WHERE account_key=" +
					       std::to_string(account.id)) == "0",
			"rejected purchase left financial effects");
		auto result = critical_command_repository_apply(db, command);
		require(result.outcome == critical_apply_outcome::applied,
			"purchase did not commit after fault removal");
		require(scalar(db,
			       "SELECT COUNT(*) FROM critical_outbox WHERE destination=12 AND event_type=1 AND payload_version=3") !=
				"0",
			"trade outbox result version does not match its delivery handler");
		require(critical_command_repository_apply(db, command).outcome ==
					critical_apply_outcome::already_applied &&
				wallet() == "1:3:3:15:8" &&
				quantity() == std::to_string(slot_type) + ":10",
			"purchase retry lost/duplicated money or cargo");
		auto conflict = purchase;
		conflict.wallet_after.amount[0]++;
		critical_command changed;
		require(divine_trade_command_build(&changed, buy_id, conflict),
			"conflicting retry payload");
		require(critical_command_repository_apply(db, changed).outcome ==
				critical_apply_outcome::terminal_failure,
			"operation identity accepted altered financial payload");
		std::vector<divine_trade_book> books;
		require(divine_trade_sql_books(db, 17, &books), "restore purchase books");
		const auto found = std::find_if(books.begin(), books.end(), [&](const auto &book)
						{ return book.account == account.id; });
		require(found != books.end() && *found == purchase.book_after,
			"paid purchase provenance did not restore");
		divine_trade_removal remove;
		remove.goods = goods;
		remove.account = account.id;
		remove.ship_id = ship_id;
		remove.slot = 3;
		remove.source_port = 2;
		remove.destination_port = 4;
		remove.at = 200;
		remove.slot_quantity_before = remove.quantity = 10;
		remove.slot_basis_before = 1000;
		divine_trade_payload sale;
		sale.action = divine_trade_action::sale;
		sale.pid = sale.ship_owner_pid = pid;
		sale.ship_id = ship_id;
		sale.generation = generation + 1;
		sale.book_revision = 1;
		sale.wallet_revision = 8;
		sale.admitted_at = 200;
		sale.payment = zero_sale ? 0 : 1230;
		sale.wallet_after.amount = zero_sale ? std::array<int64_t, 4>{ 1, 3, 3, 15 } :
						       std::array<int64_t, 4>{ 1, 6, 5, 16 };
		sale.slots_after.push_back({ 3, SLOT_EMPTY, -1, -1, 0, { -1, -1, -1, -1, -1 } });
		sale.slots_before = purchase.slots_after;
		sale.crew_before = purchase.crew_after;
		sale.market_after.push_back(
			{ 4, 2, goods, zero_sale ? 0.0f : .95f, zero_sale ? 0 : 120 });
		sale.crew_after.sail_skill_milli = zero_sale ? 0 : 1500;
		divine_trade_consumption consumed;
		require(divine_trade_prepare_removal(*found, boon, remove, &sale.book_after,
						     &consumed) &&
				consumed.qualifying_quantity == 1,
			"merged sale qualified pre-stocked cargo");
		sale.qualifying_quantity = consumed.qualifying_quantity;
		sale.has_cargo_effect = !contraband && !zero_sale;
		sale.cargo_effect.type = PLAYER_TRADE_CARGO_AFFECT;
		sale.cargo_effect.duration = -1;
		sale.cargo_effect.modifier = 10005;

		require(divine_trade_command_build(&command, sell_id, sale),
			"prepare sale command");
		// Cargo loaded after preparation must survive a delayed full-slot sale.
		execute(db,
			"UPDATE ship_slots SET val0=11,val1=1100 WHERE slot_index=3 AND ship_id=" +
				std::to_string(ship_id));
		critical_operation_id delayed_sale;
		require(critical_operation_id_generate(&delayed_sale), "delayed sale identity");
		critical_command delayed;
		require(divine_trade_command_build(&delayed, delayed_sale, sale),
			"delayed sale command");
		require(critical_command_repository_apply(db, delayed).error_code == ESTALE &&
				scalar(db,
				       "SELECT val0 FROM ship_slots WHERE slot_index=3 AND ship_id=" +
					       std::to_string(ship_id)) == "11" &&
				scalar(db, "SELECT wallet_revision FROM player_data WHERE pid=" +
						   std::to_string(pid)) == "8",
			"delayed sale consumed newly loaded cargo or changed money");
		execute(db,
			"UPDATE ship_slots SET val0=10,val1=1000 WHERE slot_index=3 AND ship_id=" +
				std::to_string(ship_id));

		fail();
		require(wallet() == "1:3:3:15:8" && quantity() == std::to_string(slot_type) + ":10",
			"rejected sale left partial financial effects");
		require(critical_command_repository_apply(db, command).outcome ==
					critical_apply_outcome::applied &&
				critical_command_repository_apply(db, command).outcome ==
					critical_apply_outcome::already_applied &&
				wallet() == (zero_sale ? "1:3:3:15:9" : "1:6:5:16:9") &&
				quantity() == "0:-1",
			"sale lost/duplicated money or restored cargo");
		require(scalar(db, "SELECT COUNT(*) FROM ship_cargo_market_mods WHERE type='" +
					   market_type + "' AND port_id=4 AND cargo_type=2") ==
					"1" &&
				scalar(db, "SELECT COUNT(*) FROM ship_cargo_prices WHERE type='" +
						   market_type +
						   "' AND port_id=4 AND cargo_type=2") == "1",
			"trade left duplicate logical market cells");
		require(divine_trade_sql_generation(db, &generation, false) &&
				scalar(db, "SELECT sail_skill FROM ship_crew WHERE ship_id=" +
						   std::to_string(ship_id)) ==
					(zero_sale ? "0" : "1500"),
			"sale generation or prepared crew state missing");
		if (sale.has_cargo_effect)
			require(scalar(db, "SELECT modifier FROM player_affects WHERE pid=" +
						   std::to_string(pid) + " AND type=2110") ==
					"10005",
				"financial sale omitted its cargo achievement");
		player_snapshot captured{};
		captured.schema_version = PLAYER_SNAPSHOT_SCHEMA_VERSION;
		captured.pid = pid;
		captured.revision = 100;
		captured.components = PLAYER_COMPONENT_STATUS | PLAYER_COMPONENT_AFFECTS;
		captured.encoded_size_bound = 8192;
		captured.wallet_revision = 9;
		captured.pending_trade.operation = sell_id.bytes;
		captured.pending_trade.payment = sale.payment;
		captured.pending_trade.wallet_revision = 8;
		captured.pending_trade.has_cargo_effect = sale.has_cargo_effect;
		captured.pending_trade.cargo_effect = sale.cargo_effect;
		std::vector<uint8_t> encoded_command;
		require(critical_command_encode(command, &encoded_command) ==
				critical_command_codec_result::ok,
			"encode captured trade identity");
		SHA256(encoded_command.data(), encoded_command.size(),
		       captured.pending_trade.command_hash.data());
		for (unsigned coin = 0; coin < 4; ++coin)
			captured.status_integers.push_back(
				{ static_cast<player_status_field>(
					  static_cast<unsigned>(player_status_field::copper) + coin),
				  coin ? purchase.wallet_after.amount[coin] : 21, 0, false });
		captured.status_integers.push_back({ player_status_field::level, 51, 0, false });
		const std::string merged = zero_sale ? "21:3:3:15:10" : "21:6:5:16:10";
		const auto captured_result = player_snapshot_repository_apply(db, captured);
		require(captured_result.outcome == player_save_apply_outcome::applied &&
				wallet() == merged,
			"pending logout capture failed: outcome=" +
				std::to_string(static_cast<unsigned>(captured_result.outcome)) +
				" error=" + std::to_string(captured_result.error_code) + " field=" +
				captured_result.failed_field.data() + " wallet=" + wallet());
		require(player_snapshot_repository_apply(db, captured).outcome ==
					player_save_apply_outcome::applied &&
				wallet() == merged,
			"snapshot retry paid trade twice");
		require(scalar(db, "SELECT level FROM player_data WHERE pid=" +
					   std::to_string(pid)) == "51",
			"trade fence lost ordinary status");
		if (sale.has_cargo_effect)
			require(scalar(db, "SELECT modifier FROM player_affects WHERE pid=" +
						   std::to_string(pid) + " AND type=2110") ==
					"10005",
				"pending affect capture erased cargo achievement");
		auto corrupt = captured;
		corrupt.pending_trade.command_hash[0] ^= 1;
		require(player_snapshot_repository_apply(db, corrupt).outcome ==
					player_save_apply_outcome::terminal_failure &&
				wallet() == merged,
			"mismatched pending receipt accepted");
		// Absent and durably rejected trades do not pay a captured purse.
		auto unpaid = captured;
		require(player_snapshot_settle_trade(&unpaid, true) ==
				player_snapshot_codec_result::ok,
			"prepare current purse fixture");
		unpaid.pending_trade = captured.pending_trade;
		critical_operation_id absent;
		require(critical_operation_id_generate(&absent), "missing receipt id");
		unpaid.pending_trade.operation = absent.bytes;
		require(player_snapshot_repository_apply(db, unpaid).outcome ==
					player_save_apply_outcome::applied &&
				wallet() == merged,
			"absent trade paid a capture");
		critical_command rejected;
		auto stale_sale = sale;
		require(divine_trade_command_build(&rejected, absent, stale_sale),
			"build stale rejected trade");
		require(critical_command_repository_apply(db, rejected).error_code == ESTALE,
			"stale trade did not retain rejection");
		encoded_command.clear();
		require(critical_command_encode(rejected, &encoded_command) ==
				critical_command_codec_result::ok,
			"encode rejected trade");
		SHA256(encoded_command.data(), encoded_command.size(),
		       unpaid.pending_trade.command_hash.data());
		require(player_snapshot_repository_apply(db, unpaid).outcome ==
					player_save_apply_outcome::applied &&
				wallet() == merged,
			"rejected trade paid a capture");
		require(divine_trade_sql_books(db, 17, &books), "restore spent account allowances");
		const auto spent = std::find_if(books.begin(), books.end(), [&](const auto &book)
						{ return book.account == account.id; });
		require(spent != books.end() && spent->lots.empty() && spent->consumed == 1 &&
				spent->first_full_hold == 10,
			"sale lost its shared spent allowance");
	}
	// Execute the real maintenance producer against the settled market. A
	// restored legacy capture has generation zero and must not erase trade 20.
	maintenance_request request{};
	request.work_id = 10001;
	request.job_id = maintenance_job_id::cargo_market;
	request.row_budget = 100;
	request.time_budget_usec = 5000000;
	request.deadline_usec = persistence_observability_now_usec() + 5000000;
	request.value_count = 3 + 10 * 10 * 4;
	request.values[0] = 1700000000;
	request.values[1] = request.values[2] = 1;
	for (size_t offset = 3; offset < request.value_count; offset += 4)
	{
		request.values[offset] = 100;
		request.values[offset + 1] = 200;
		request.values[offset + 2] = 1100000;
		request.values[offset + 3] = 1200000;
	}
	const auto old_maintenance = execute_cargo_market(db, request);
	const auto old_market = scalar(
		db,
		"SELECT ROUND(modifier*100) FROM ship_cargo_market_mods WHERE type='CARGO' AND port_id=4 AND cargo_type=2");
	require(old_maintenance.outcome == maintenance_outcome::complete &&
			std::stod(old_market) == 95,
		"restored maintenance: outcome=" +
			std::to_string(static_cast<int>(old_maintenance.outcome)) + " error=" +
			std::to_string(old_maintenance.error_code) + " modifier=" + old_market);
	request.work_id++;
	request.values[request.value_count++] = 20;
	const auto current_maintenance = execute_cargo_market(db, request);
	const auto current_market = scalar(
		db,
		"SELECT ROUND(modifier*100) FROM ship_cargo_market_mods WHERE type='CARGO' AND port_id=4 AND cargo_type=2");
	require(current_maintenance.outcome == maintenance_outcome::complete &&
			std::stod(current_market) == 110,
		"current maintenance: outcome=" +
			std::to_string(static_cast<int>(current_maintenance.outcome)) +
			" error=" + std::to_string(current_maintenance.error_code) +
			" modifier=" + current_market);
	mysql_close(db);
	std::cout
		<< "PASS: SQL Divine purchase/sale receipts and rollback at ten financial boundaries\n";
}
