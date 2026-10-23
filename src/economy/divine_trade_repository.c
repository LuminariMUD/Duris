#include "economy/divine_trade_repository.h"
#include "player/player_snapshot_repository.h"

#include <cerrno>
#include <charconv>
#include <cstring>
#include <limits>
#include <string>
#include <string_view>

#ifndef __NO_MYSQL__
namespace
{
bool execute(MYSQL *connection, const std::string &sql)
{
	return mysql_real_query(connection, sql.data(), sql.size()) == 0;
}

bool number(const char *text, uint64_t *value)
{
	if (!text || !*text)
		return false;
	const char *end = text + strlen(text);
	const auto parsed = std::from_chars(text, end, *value);
	return parsed.ec == std::errc{} && parsed.ptr == end;
}

std::string hex(const std::vector<uint8_t> &bytes)
{
	constexpr char digits[] = "0123456789abcdef";
	std::string result;
	result.reserve(bytes.size() * 2);
	for (uint8_t byte : bytes)
	{
		result.push_back(digits[byte >> 4]);
		result.push_back(digits[byte & 15]);
	}
	return result;
}

bool read_book(MYSQL *connection, uint64_t account, uint64_t boon, divine_trade_book *book)
{
	if (!execute(connection, "SELECT snapshot FROM divine_trade_state WHERE account_key=" +
					 std::to_string(account) +
					 " AND boon_id=" + std::to_string(boon) + " FOR UPDATE"))
		return false;
	MYSQL_RES *rows = mysql_store_result(connection);
	if (!rows)
		return false;
	MYSQL_ROW row = mysql_fetch_row(rows);
	bool valid = true;
	divine_trade_book loaded;
	if (row)
	{
		const auto *lengths = mysql_fetch_lengths(rows);
		valid = lengths && row[0] && lengths[0] <= CRITICAL_COMMAND_MAX_PAYLOAD_BYTES &&
			divine_trade_book_decode(
				std::vector<uint8_t>(reinterpret_cast<const uint8_t *>(row[0]),
						     reinterpret_cast<const uint8_t *>(row[0]) +
							     lengths[0]),
				&loaded) &&
			loaded.account == account && loaded.boon_id == boon;
	}
	mysql_free_result(rows);
	if (!valid)
	{
		errno = EILSEQ;
		return false;
	}
	*book = std::move(loaded);
	return true;
}
bool ship_preimage_matches(MYSQL *connection, const divine_trade_payload &p)
{
	const auto matches = [&](const std::string &query)
	{
		if (!execute(connection, query))
			return false;
		MYSQL_RES *rows = mysql_store_result(connection);
		if (!rows)
		{
			if (!mysql_errno(connection))
				errno = EIO;
			return false;
		}
		const bool same = mysql_num_rows(rows) == 1;
		mysql_free_result(rows);
		if (!same)
			errno = ESTALE;
		return same;
	};
	for (const auto &slot : p.slots_before)
	{
		std::string query =
			"SELECT 1 FROM ship_slots WHERE ship_id=" + std::to_string(p.ship_id) +
			" AND slot_index=" + std::to_string(slot.slot_index) +
			" AND slot_type=" + std::to_string(slot.slot_type) +
			" AND item_index=" + std::to_string(slot.item_index) +
			" AND position=" + std::to_string(slot.position) +
			" AND timer=" + std::to_string(slot.timer);
		for (size_t i = 0; i < slot.values.size(); ++i)
			query += " AND val" + std::to_string(i) + "=" +
				 std::to_string(slot.values[i]);
		if (!matches(query + " FOR UPDATE"))
		{
			if (errno != ESTALE || slot != flatfile_ship_empty_slot(slot.slot_index) ||
			    !matches("SELECT 1 FROM ships WHERE id=" + std::to_string(p.ship_id) +
				     " AND NOT EXISTS(SELECT 1 FROM ship_slots WHERE ship_id=" +
				     std::to_string(p.ship_id) + " AND slot_index=" +
				     std::to_string(slot.slot_index) + ") FOR UPDATE"))
				return false;
		}
	}
	const auto &crew = p.crew_before;
	std::string query = "SELECT 1 FROM ship_crew WHERE ship_id=" + std::to_string(p.ship_id);
	constexpr const char *fields[] = { "crew_index", "sail_skill", "guns_skill", "rpar_skill",
					   "sail_chief", "guns_chief", "rpar_chief" };
	const int32_t values[] = { crew.crew_index,	  crew.sail_skill_milli,
				   crew.guns_skill_milli, crew.repair_skill_milli,
				   crew.sail_chief,	  crew.guns_chief,
				   crew.repair_chief };
	for (size_t i = 0; i < std::size(values); ++i)
		query += std::string(" AND ") + fields[i] + "=" + std::to_string(values[i]);
	if (matches(query + " FOR UPDATE"))
		return true;
	return errno == ESTALE && crew == flatfile_ship_crew_record{} &&
	       matches("SELECT 1 FROM ships WHERE id=" + std::to_string(p.ship_id) +
		       " AND NOT EXISTS(SELECT 1 FROM ship_crew WHERE ship_id=" +
		       std::to_string(p.ship_id) + ") FOR UPDATE");
}
}

bool divine_trade_sql_generation(MYSQL *connection, uint64_t *generation, bool for_update)
{
	if (!connection || !generation ||
	    !execute(
		    connection,
		    std::string(
			    "SELECT revision,OCTET_LENGTH(snapshot) FROM divine_trade_state WHERE account_key=0 AND boon_id=0") +
			    (for_update ? " FOR UPDATE" : "")))
		return false;
	MYSQL_RES *rows = mysql_store_result(connection);
	MYSQL_ROW row = rows ? mysql_fetch_row(rows) : nullptr;
	uint64_t value = 0;
	const bool valid = row && number(row[0], &value) && row[1] &&
			   std::string_view(row[1]) == "0";
	if (rows)
		mysql_free_result(rows);
	if (!valid)
	{
		errno = EILSEQ;
		return false;
	}
	*generation = value;
	return true;
}

bool divine_trade_sql_execute(MYSQL *connection, const critical_command &command,
			      divine_trade_result *result, unsigned int *result_code, bool *mutated)
{
	divine_trade_payload p;
	if (!connection || !result || !result_code || !mutated ||
	    !divine_trade_command_decode(command, &p))
	{
		errno = EINVAL;
		return false;
	}
	*result = { p.pid,
		    p.ship_id,
		    p.generation + 1,
		    p.wallet_revision + 1,
		    p.book_after.revision,
		    p.payment,
		    p.qualifying_quantity };
	*result_code = 0;
	*mutated = false;
	if (command.payload_version < 3)
	{
		*result_code = EPROTONOSUPPORT;
		return true; // Existing receipts are resolved before this executor.
	}
	uint64_t generation = 0;
	if (!divine_trade_sql_generation(connection, &generation, true))
		return false;
	divine_trade_book before;
	if (!read_book(connection, p.book_after.account, p.book_after.boon_id, &before))
		return false;
	if (generation != p.generation || !divine_trade_book_transition_valid(before, p))
	{
		*result_code = ESTALE;
		return true;
	}
	if (!execute(connection, "SELECT account_name,wallet_revision FROM player_data WHERE pid=" +
					 std::to_string(p.pid) + " FOR UPDATE"))
		return false;
	MYSQL_RES *rows = mysql_store_result(connection);
	MYSQL_ROW row = rows ? mysql_fetch_row(rows) : nullptr;
	critical_entity_key account;
	uint64_t wallet_revision = 0;
	bool valid = row && row[0] && currency_account_key(row[0], 0, &account) &&
		     account.id == p.book_after.account && number(row[1], &wallet_revision) &&
		     wallet_revision <= p.wallet_revision;
	if (rows)
		mysql_free_result(rows);
	if (!rows)
		return false;
	if (!valid)
	{
		*result_code = ESTALE;
		return true;
	}
	if (!execute(connection,
		     "SELECT p.pid FROM ships s JOIN player_data p ON p.name=s.owner_name "
		     "WHERE s.id=" +
			     std::to_string(p.ship_id) + " FOR UPDATE"))
		return false;
	rows = mysql_store_result(connection);
	row = rows ? mysql_fetch_row(rows) : nullptr;
	uint64_t owner = 0;
	valid = row && number(row[0], &owner) && owner == p.ship_owner_pid;
	if (rows)
		mysql_free_result(rows);
	if (!rows)
		return false;
	if (!valid)
	{
		*result_code = ESTALE;
		return true;
	}
	errno = 0;
	if (!ship_preimage_matches(connection, p))
	{
		if (errno != ESTALE)
			return false;
		*result_code = ESTALE;
		return true;
	}
	std::string wallet =
		"UPDATE player_data SET wallet_revision=" + std::to_string(p.wallet_revision + 1);
	constexpr const char *coins[] = { "copper", "silver", "gold", "platinum" };
	for (size_t i = 0; i < p.wallet_after.amount.size(); ++i)
		wallet += std::string(",") + coins[i] + "=" +
			  std::to_string(p.wallet_after.amount[i]);
	if (!execute(connection, wallet + " WHERE pid=" + std::to_string(p.pid)))
		return false;
	if (p.has_cargo_effect &&
	    !player_snapshot_repository_write_cargo_effect(connection, p.pid, p.cargo_effect))
		return false;
	for (const auto &slot : p.slots_after)
	{
		std::string values =
			std::to_string(p.ship_id) + "," + std::to_string(slot.slot_index) + "," +
			std::to_string(slot.slot_type) + "," + std::to_string(slot.item_index) +
			"," + std::to_string(slot.position) + "," + std::to_string(slot.timer);
		for (int32_t value : slot.values)
			values += "," + std::to_string(value);
		if (!execute(
			    connection,
			    "INSERT INTO ship_slots(ship_id,slot_index,slot_type,item_index,position,timer,val0,val1,val2,val3,val4) VALUES(" +
				    values +
				    ") ON DUPLICATE KEY UPDATE slot_type=VALUES(slot_type),item_index=VALUES(item_index),position=VALUES(position),timer=VALUES(timer),val0=VALUES(val0),val1=VALUES(val1),val2=VALUES(val2),val3=VALUES(val3),val4=VALUES(val4)"))
			return false;
	}
	const auto &crew = p.crew_after;
	std::string crew_values = std::to_string(p.ship_id);
	for (int32_t value :
	     { crew.crew_index, crew.sail_skill_milli, crew.guns_skill_milli,
	       crew.repair_skill_milli, crew.sail_chief, crew.guns_chief, crew.repair_chief })
		crew_values += "," + std::to_string(value);
	if (!execute(
		    connection,
		    "INSERT INTO ship_crew(ship_id,crew_index,sail_skill,guns_skill,rpar_skill,sail_chief,guns_chief,rpar_chief) VALUES(" +
			    crew_values +
			    ") ON DUPLICATE KEY UPDATE crew_index=VALUES(crew_index),sail_skill=VALUES(sail_skill),guns_skill=VALUES(guns_skill),rpar_skill=VALUES(rpar_skill),sail_chief=VALUES(sail_chief),guns_chief=VALUES(guns_chief),rpar_chief=VALUES(rpar_chief)"))
		return false;
	for (const auto &cell : p.market_after)
	{
		const std::string key =
			std::string("'") +
			(cell.goods == divine_trade_goods::cargo ? "CARGO" : "CONTRABAND") + "'," +
			std::to_string(cell.port) + "," + std::to_string(cell.commodity);
		char modifier[32];
		const auto formatted = std::to_chars(modifier, modifier + sizeof(modifier),
						     cell.modifier, std::chars_format::general,
						     std::numeric_limits<float>::max_digits10);
		// Legacy market indexes are non-unique; replace this logical cell in
		// the same financial transaction, including any old duplicate rows.
		const std::string where =
			std::string(" WHERE type='") +
			(cell.goods == divine_trade_goods::cargo ? "CARGO" : "CONTRABAND") +
			"' AND port_id=" + std::to_string(cell.port) +
			" AND cargo_type=" + std::to_string(cell.commodity);
		if (formatted.ec != std::errc{} ||
		    !execute(connection, "DELETE FROM ship_cargo_market_mods" + where) ||
		    !execute(connection, "DELETE FROM ship_cargo_prices" + where) ||
		    !execute(
			    connection,
			    "INSERT INTO ship_cargo_market_mods(type,port_id,cargo_type,modifier) VALUES(" +
				    key + "," + std::string(modifier, formatted.ptr) + ")") ||
		    !execute(connection,
			     "INSERT INTO ship_cargo_prices(type,port_id,cargo_type,price) VALUES(" +
				     key + "," + std::to_string(cell.price) + ")"))
			return false;
	}
	std::vector<uint8_t> snapshot;
	if (!divine_trade_book_encode(p.book_after, &snapshot))
	{
		errno = EILSEQ;
		return false;
	}
	if (!execute(
		    connection,
		    "INSERT INTO divine_trade_state(account_key,boon_id,revision,snapshot) VALUES(" +
			    std::to_string(p.book_after.account) + "," +
			    std::to_string(p.book_after.boon_id) + "," +
			    std::to_string(p.book_after.revision) + ",UNHEX('" + hex(snapshot) +
			    "')) ON DUPLICATE KEY UPDATE revision=VALUES(revision),snapshot=VALUES(snapshot)") ||
	    !execute(connection,
		     "UPDATE divine_trade_state SET revision=" + std::to_string(p.generation + 1) +
			     " WHERE account_key=0 AND boon_id=0"))
		return false;
	*mutated = true;
	return true;
}

bool divine_trade_sql_books(MYSQL *connection, uint64_t boon_id,
			    std::vector<divine_trade_book> *books)
{
	if (!connection || !boon_id || !books ||
	    !execute(connection,
		     "SELECT account_key,snapshot FROM divine_trade_state WHERE boon_id=" +
			     std::to_string(boon_id) + " AND account_key>0 ORDER BY account_key"))
		return false;
	MYSQL_RES *rows = mysql_store_result(connection);
	if (!rows)
		return false;
	std::vector<divine_trade_book> restored;
	bool valid = true;
	while (MYSQL_ROW row = mysql_fetch_row(rows))
	{
		const auto *lengths = mysql_fetch_lengths(rows);
		uint64_t account = 0;
		divine_trade_book book;
		if (!number(row[0], &account) || !row[1] || !lengths ||
		    lengths[1] > CRITICAL_COMMAND_MAX_PAYLOAD_BYTES ||
		    !divine_trade_book_decode(
			    std::vector<uint8_t>(reinterpret_cast<const uint8_t *>(row[1]),
						 reinterpret_cast<const uint8_t *>(row[1]) +
							 lengths[1]),
			    &book) ||
		    book.account != account || book.boon_id != boon_id)
		{
			valid = false;
			break;
		}
		restored.push_back(std::move(book));
	}
	mysql_free_result(rows);
	if (valid)
		*books = std::move(restored);
	else
		errno = EILSEQ;
	return valid;
}
#endif

#ifdef __NO_MYSQL__
bool divine_trade_sql_generation(MYSQL *, uint64_t *, bool)
{
	errno = ENOTSUP;
	return false;
}
bool divine_trade_sql_execute(MYSQL *, const critical_command &, divine_trade_result *,
			      unsigned int *, bool *)
{
	errno = ENOTSUP;
	return false;
}
bool divine_trade_sql_books(MYSQL *, uint64_t, std::vector<divine_trade_book> *)
{
	errno = ENOTSUP;
	return false;
}
#endif
