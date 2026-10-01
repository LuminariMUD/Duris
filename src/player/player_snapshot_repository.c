#include "player/player_snapshot_repository.h"

#include "core/defines.h"
#include "economy/collector_eligibility.h"
#include "economy/collector_repository.h"
#include "item/item_claim_repository.h"
#include "persistence/persistence_observability.h"
#include "player/player_snapshot_codec.h"
#include "sql/item_extra_descr_codec.h"
#include "sql/sql_pool.h"

#include <mysql/mysql.h>

#include <array>
#include <algorithm>
#include <cerrno>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <functional>
#include <limits>
#include <sstream>
#include <string>
#include <strings.h>
#include <unordered_set>
#include <unordered_map>
#include <vector>

namespace
{
struct query_result
{
	bool ok;
	unsigned int error_code;
};

query_result
canonicalize_snapshot_extra_description(const player_item_extra_description_snapshot &description,
					std::string *keyword_out, std::string *description_out)
{
	if (!keyword_out || !description_out)
		return { false, EINVAL };
	if (description.spellbook != (description.keyword == "SPELLBOOK"))
		return { false, EINVAL };
	if (description.spellbook && !description.description.empty() &&
	    !description.spell_ids.empty())
		return { false, EINVAL };

	*keyword_out = description.keyword;
	*description_out = description.description;
	if (!description.spellbook)
	{
		if (!description.spell_ids.empty())
			return { false, EINVAL };
		return { true, 0 };
	}

	std::array<char, (MAX_SKILLS + 1) / 8 + 1> spell_bits = {};
	if (!description.description.empty())
	{
		if (sql_decode_stored_spellbook("SPELLBOOK", description.description.c_str(),
						spell_bits.data(), spell_bits.size()) !=
		    sql_spellbook_decode_status::decoded)
			return { false, EINVAL };
	}
	else
	{
		std::array<bool, MAX_SKILLS> seen = {};
		for (int32_t spell : description.spell_ids)
		{
			if (spell < 0 || spell >= MAX_SKILLS || seen[spell])
				return { false, EINVAL };
			seen[spell] = true;
			const size_t byte = static_cast<size_t>(spell) / 8;
			spell_bits[byte] =
				static_cast<char>(static_cast<unsigned char>(spell_bits[byte]) |
						  static_cast<unsigned char>(1U << (spell % 8)));
		}
	}

	const char marker[] = { 3, 1, 3, 0 };
	char *db_keyword = nullptr;
	char *db_description = nullptr;
	if (!sql_encode_item_extra_descr(marker, spell_bits.data(), &db_keyword, &db_description))
		return { false, ENOMEM };
	if (!db_keyword || !db_description)
	{
		std::free(db_keyword);
		std::free(db_description);
		return { false, ENOMEM };
	}
	*keyword_out = db_keyword;
	*description_out = db_description;
	std::free(db_keyword);
	std::free(db_description);
	return { true, 0 };
}

query_result execute(MYSQL *connection, const std::string &sql)
{
	const uint64_t started = persistence_observability_now_usec();
	const int rc = mysql_real_query(connection, sql.data(), sql.size());
	const uint64_t finished = persistence_observability_now_usec();
	const unsigned int error_code = rc ? mysql_errno(connection) : 0;
	persistence_query_record(PERSISTENCE_QUERY_SITE,
				 PERSISTENCE_QUERY_CONTEXT_PLAYER_SAVE_WORKER,
				 persistence_statement_kind_from_sql(sql.c_str()),
				 finished - started, rc == 0, error_code,
				 rc ? mysql_sqlstate(connection) : "00000");
	return { rc == 0, error_code };
}

bool retryable_error(unsigned int error_code)
{
	return error_code == 1040 || error_code == 1205 || error_code == 1213 ||
	       error_code == 2002 || error_code == 2003 || error_code == 2006 || error_code == 2013;
}

bool connection_error(unsigned int error_code)
{
	return error_code == 2002 || error_code == 2003 || error_code == 2006 || error_code == 2013;
}

player_save_apply_result failure(unsigned int error_code)
{
	return { retryable_error(error_code) ? player_save_apply_outcome::retryable_failure :
					       player_save_apply_outcome::terminal_failure,
		 0, error_code };
}

std::string escape(MYSQL *connection, const std::string &value)
{
	std::string escaped(value.size() * 2 + 1, '\0');
	const unsigned long size =
		mysql_real_escape_string(connection, escaped.data(), value.data(), value.size());
	escaped.resize(size);
	return escaped;
}

std::string quote(MYSQL *connection, const std::string &value)
{
	return "'" + escape(connection, value) + "'";
}

uint64_t integer_value(const player_snapshot_integer &row)
{
	return row.is_unsigned ? row.unsigned_value : static_cast<uint64_t>(row.signed_value);
}

const char *status_column(player_status_field field)
{
	static constexpr std::array<const char *, 61> columns = {
		"m_class",
		"secondary_class",
		"spec",
		"race",
		"racewar",
		"level",
		"sex",
		"weight",
		"height",
		"size",
		"hometown",
		"birthplace",
		"orig_birthplace",
		"birth_time",
		"played_time",
		"base_str",
		"base_dex",
		"base_agi",
		"base_con",
		"base_pow",
		"base_int",
		"base_wis",
		"base_cha",
		"base_kar",
		"base_luk",
		"mana",
		"base_mana",
		"hit_diff",
		"base_hit",
		"vitality",
		"base_vitality",
		"spells_memmed_extra",
		"copper",
		"silver",
		"gold",
		"platinum",
		"exp",
		"epics",
		"epic_skill_points",
		"skillpoints",
		"spell_bind_used",
		"act",
		"act2",
		"act3",
		"vote",
		"alignment",
		"prestige",
		"assoc_id",
		"guild_status",
		"time_left_guild",
		"nb_left_guild",
		"time_unspecced",
		"frags",
		"oldfrags",
		"numb_deaths",
		"echo_toggle",
		"prompt",
		"wiz_invis",
		"wimpy",
		"aggressive",
		"highest_level",
	};
	static constexpr std::array<const char *, 2> tail = { "screen_length", "last_ip" };
	const size_t index = static_cast<size_t>(field);
	if (index < columns.size())
		return columns[index];
	return index - columns.size() < tail.size() ? tail[index - columns.size()] : nullptr;
}

const char *status_string_column(player_status_string_field field)
{
	static constexpr std::array<const char *, 7> columns = {
		"name", "short_descr", "long_descr", "description", "title", "poof_in", "poof_out",
	};
	const size_t index = static_cast<size_t>(field);
	return index < columns.size() ? columns[index] : nullptr;
}

bool status_time_field(player_status_field field)
{
	return field == player_status_field::birth_time ||
	       field == player_status_field::time_left_guild ||
	       field == player_status_field::time_unspecialized;
}

query_result apply_status(MYSQL *connection, const player_snapshot &snapshot)
{
	std::ostringstream sql;
	sql << "UPDATE player_data SET last_room=" << snapshot.room_vnum << ",last_save=NOW()";
	sql << ",output_preferences=" << quote(connection, snapshot.output_preferences);
	// The wallet, epic points and frags are memory's, and the save writes them.
	for (const player_snapshot_integer &row : snapshot.status_integers)
	{
		const char *column = status_column(row.field);
		if (!column)
			return { false, EINVAL };
		sql << ',' << column << '=';
		if (status_time_field(row.field))
			sql << "FROM_UNIXTIME(NULLIF(" << integer_value(row) << ",0))";
		else if (row.is_unsigned)
			sql << row.unsigned_value;
		else
			sql << row.signed_value;
	}
	for (const player_snapshot_string &row : snapshot.status_strings)
	{
		const char *column = status_string_column(row.field);
		if (!column || row.field == player_status_string_field::name)
			continue;
		sql << ',' << column << '=' << quote(connection, row.value);
	}
	for (size_t index = 0; index < snapshot.conditions.size(); ++index)
		sql << ",condition_" << index << '=' << snapshot.conditions[index];
	static constexpr std::array<const char *, 14> quest_columns = {
		"quest_active",	  "quest_mob_vnum",    "quest_type",	      "quest_accomplished",
		"quest_started",  "quest_zone_number", "quest_giver",	      "quest_level",
		"quest_receiver", "quest_shares_left", "quest_kill_how_many", "quest_kill_original",
		"quest_map_room", "quest_map_bought",
	};
	for (size_t index = 0; index < snapshot.quest_values.size(); ++index)
		sql << ',' << quest_columns[index] << '=' << snapshot.quest_values[index];
	sql << " WHERE pid=" << snapshot.pid;
	return execute(connection, sql.str());
}

template <typename Row, typename Append>
query_result replace_rows(MYSQL *connection, int pid, const char *table, const char *columns,
			  const std::vector<Row> &rows, Append append)
{
	query_result result = execute(connection, "DELETE FROM " + std::string(table) +
							  " WHERE pid=" + std::to_string(pid));
	if (!result.ok || rows.empty())
		return result;
	std::ostringstream sql;
	sql << "INSERT INTO " << table << " (pid," << columns << ") VALUES ";
	for (size_t index = 0; index < rows.size(); ++index)
	{
		if (index)
			sql << ',';
		sql << '(' << pid << ',';
		append(sql, rows[index]);
		sql << ')';
	}
	return execute(connection, sql.str());
}

query_result apply_replacement_rows(MYSQL *connection, const player_snapshot &snapshot)
{
	query_result result = { true, 0 };
	if (snapshot.components & PLAYER_COMPONENT_LANGUAGES)
		result = replace_rows(connection, snapshot.pid, "player_languages",
				      "tongue_id,proficiency", snapshot.languages,
				      [](auto &sql, const auto &row)
				      { sql << row.index << ',' << row.value; });
	if (result.ok && (snapshot.components & PLAYER_COMPONENT_INTRODUCTIONS))
		result = replace_rows(connection, snapshot.pid, "player_intros",
				      "intro_index,intro_pid,intro_time", snapshot.introductions,
				      [](auto &sql, const auto &row) {
					      sql << row.index << ',' << row.value
						  << ",FROM_UNIXTIME(NULLIF(" << row.auxiliary
						  << ",0))";
				      });
	if (result.ok && (snapshot.components & PLAYER_COMPONENT_TIMERS))
		result = replace_rows(
			connection, snapshot.pid, "player_timers", "timer_id,timer_value",
			snapshot.timers, [](auto &sql, const auto &row)
			{ sql << row.index << ",FROM_UNIXTIME(NULLIF(" << row.value << ",0))"; });
	if (result.ok && (snapshot.components & PLAYER_COMPONENT_UNDEAD_SLOTS))
		result = replace_rows(connection, snapshot.pid, "player_undead_slots",
				      "circle,slots", snapshot.undead_slots,
				      [](auto &sql, const auto &row)
				      { sql << row.index << ',' << row.value; });
	if (result.ok && (snapshot.components & PLAYER_COMPONENT_FORGED_ITEMS))
		result = replace_rows(connection, snapshot.pid, "player_forged_items",
				      "forge_index,item_vnum", snapshot.forged_items,
				      [](auto &sql, const auto &row)
				      { sql << row.index << ',' << row.value; });
	if (result.ok && (snapshot.components & PLAYER_COMPONENT_GRANTED_COMMANDS))
	{
		result = execute(connection, "DELETE FROM player_granted_cmds WHERE pid=" +
						     std::to_string(snapshot.pid));
		if (result.ok && !snapshot.granted_commands.empty())
		{
			std::ostringstream sql;
			sql << "INSERT INTO player_granted_cmds (pid,cmd_num) VALUES ";
			for (size_t index = 0; index < snapshot.granted_commands.size(); ++index)
				sql << (index ? "," : "") << '(' << snapshot.pid << ','
				    << snapshot.granted_commands[index] << ')';
			result = execute(connection, sql.str());
		}
	}
	return result;
}

query_result apply_skills(MYSQL *connection, const player_snapshot &snapshot)
{
	return replace_rows(connection, snapshot.pid, "player_skills", "skill_id,learned,taught",
			    snapshot.skills,
			    [](auto &sql, const auto &row)
			    {
				    sql << row.skill_id << ','
					<< static_cast<unsigned int>(row.learned) << ','
					<< static_cast<unsigned int>(row.taught);
			    });
}

query_result apply_affects(MYSQL *connection, const player_snapshot &snapshot)
{
	query_result result = execute(connection, "DELETE FROM player_affects WHERE pid=" +
							  std::to_string(snapshot.pid));
	if (!result.ok || snapshot.affects.empty())
		return result;
	std::ostringstream sql;
	sql << "INSERT INTO player_affects (pid,type,duration,flags,modifier,location,level,"
	       "bitvector1,bitvector2,bitvector3,bitvector4,bitvector5,custom_msg_char,"
	       "custom_msg_room) VALUES ";
	for (size_t index = 0; index < snapshot.affects.size(); ++index)
	{
		const auto &row = snapshot.affects[index];
		sql << (index ? "," : "") << '(' << snapshot.pid << ',' << row.type << ','
		    << row.duration << ',' << row.flags << ',' << row.modifier << ','
		    << static_cast<unsigned int>(row.location) << ',' << row.level;
		for (uint64_t bitvector : row.bitvectors)
			sql << ',' << bitvector;
		sql << ','
		    << (row.wear_off_character.empty() ? "NULL" :
							 quote(connection, row.wear_off_character))
		    << ','
		    << (row.wear_off_room.empty() ? "NULL" : quote(connection, row.wear_off_room))
		    << ')';
	}
	return execute(connection, sql.str());
}

std::string optional_item_string(MYSQL *connection, const player_item_snapshot &row, uint8_t mask,
				 const std::string &value)
{
	return row.string_mask & mask ? quote(connection, value) : "NULL";
}

// The tables an item graph is written to: a player's, a pet's, a corpse's or a saved
// room item's.
struct item_tables
{
	const char *items;
	const char *owner_columns;
	bool equip_slot;
	bool quantity;
	bool condition;
	const char *affects;
	const char *descriptions;
};

constexpr item_tables player_item_tables = {
	"player_items", "pid", true, true, true, "player_item_affects", "player_item_extra_descr"
};
constexpr item_tables pet_item_tables = {
	"player_pet_items",	      "pet_id", true, false, true, "player_pet_item_affects",
	"player_pet_item_extra_descr"
};
constexpr item_tables corpse_item_tables = {
	"corpse_items",		  "corpse_id", false, true, true, "corpse_item_affects",
	"corpse_item_extra_descr"
};
constexpr item_tables locker_item_tables = {
	"locker_items",	       "locker_id,chest_id",	 false, true, true,
	"locker_item_affects", "locker_item_extra_descr"
};
constexpr item_tables shopkeeper_item_tables = {
	"shopkeeper_items",	      "shopkeeper_id", true, true, false, "shopkeeper_item_affects",
	"shopkeeper_item_extra_descr"
};
constexpr item_tables saved_item_tables = {
	"saved_items",	      "item_key,room_vnum",    false, true, false,
	"saved_item_affects", "saved_item_extra_descr"
};

// `owner_values` fills the table's owner columns.
query_result insert_item_rows(MYSQL *connection, const std::vector<player_item_snapshot> &items,
			      const std::string &owner_values, const item_tables &tables)
{
	std::vector<unsigned long long> ids;
	ids.reserve(items.size());
	for (size_t index = 0; index < items.size(); ++index)
	{
		const player_item_snapshot &row = items[index];
		if (row.parent_index >= static_cast<int32_t>(index) || row.parent_index < -1)
			return { false, EINVAL };
		const std::string container =
			row.parent_index < 0 ? "NULL" : std::to_string(ids[row.parent_index]);
		std::ostringstream sql;
		sql << "INSERT INTO " << tables.items << " (" << tables.owner_columns << ",vnum,"
		    << (tables.equip_slot ? "equip_slot," : "") << "container_id,"
		    << (tables.quantity ? "quantity," : "")
		    << "weight,cost,timer,extra_flags,wear_flags,item_type,value0,value1,value2,"
		       "value3,value4,value5,value6,value7,name,short_descr,description,action_descr,"
		       "bitvector1,bitvector2,bitvector3,bitvector4,bitvector5,item_material,obj_uid"
		    << (tables.condition ? ",item_condition" : "") << ") VALUES (" << owner_values
		    << ',' << row.vnum;
		if (tables.equip_slot)
			sql << ',' << row.equipment_slot;
		sql << ',' << container;
		if (tables.quantity)
			sql << ",1";
		sql << ',' << row.weight << ',' << row.cost << ',' << row.timers[0] << ','
		    << row.extra_flags << ',' << row.wear_flags << ','
		    << static_cast<int>(row.type);
		for (int32_t value : row.values)
			sql << ',' << value;
		sql << ',' << optional_item_string(connection, row, 1, row.name) << ','
		    << optional_item_string(connection, row, 4, row.short_description) << ','
		    << optional_item_string(connection, row, 2, row.description) << ','
		    << optional_item_string(connection, row, 8, row.action_description);
		for (uint64_t bitvector : row.bitvectors)
			sql << ',' << bitvector;
		sql << ',' << static_cast<int>(row.material) << ',' << row.object_uid;
		if (tables.condition)
			sql << ',' << row.condition;
		sql << ')';
		query_result result = execute(connection, sql.str());
		if (!result.ok)
			return result;
		const unsigned long long item_id = mysql_insert_id(connection);
		if (!item_id)
			return { false, EIO };
		ids.push_back(item_id);

		std::unordered_set<uint64_t> affect_keys;
		std::unordered_set<std::string> description_keys;
		for (const auto &affect : row.affects)
		{
			if (!affect[0] && !affect[1])
				continue;
			const uint64_t key =
				(static_cast<uint64_t>(static_cast<uint16_t>(affect[0])) << 32) |
				static_cast<uint32_t>(affect[1]);
			if (!affect_keys.insert(key).second)
				continue;
			result = execute(connection,
					 "INSERT INTO " + std::string(tables.affects) +
						 " (item_id,location,modifier) VALUES (" +
						 std::to_string(item_id) + "," +
						 std::to_string(affect[0]) + "," +
						 std::to_string(affect[1]) + ")");
			if (!result.ok)
				return result;
		}
		for (const auto &description : row.extra_descriptions)
		{
			if (description.keyword.empty())
			{
				if (description.spellbook || !description.spell_ids.empty())
					return { false, EINVAL };
				continue;
			}
			std::string encoded_keyword;
			std::string encoded_description;
			const query_result canonical = canonicalize_snapshot_extra_description(
				description, &encoded_keyword, &encoded_description);
			if (!canonical.ok)
				return canonical;
			std::string description_key = encoded_keyword;
			description_key.push_back('\0');
			description_key += encoded_description;
			if (!description_keys.insert(std::move(description_key)).second)
				continue;
			result = execute(connection,
					 "INSERT INTO " + std::string(tables.descriptions) +
						 " (item_id,keyword,description) VALUES (" +
						 std::to_string(item_id) + "," +
						 quote(connection, encoded_keyword) + "," +
						 quote(connection, encoded_description) + ")");
			if (!result.ok)
				return result;
		}
	}
	return { true, 0 };
}

struct claimed_graph
{
	item_owner_identity owner;
	item_claim_outcome outcome;
};

query_result claim_graph(MYSQL *connection, const item_owner_identity &owner,
			 const std::vector<player_item_snapshot> &items,
			 std::vector<claimed_graph> *claims,
			 std::vector<player_item_snapshot> *written)
{
	claimed_graph claim;
	claim.owner = owner;
	const unsigned int failed = claim_items(connection, owner, items, &claim.outcome);
	if (failed)
		return { false, failed };
	*written = item_claim_written_items(items, claim.outcome.left_out);
	if (claims && !claim.outcome.dupes.empty())
		claims->push_back(std::move(claim));
	return { true, 0 };
}

query_result apply_items(MYSQL *connection, const player_snapshot &snapshot,
			 std::vector<claimed_graph> *claims)
{
	const item_owner_identity owner = { item_owner_type::player,
					    static_cast<uint64_t>(snapshot.pid), 0 };
	std::vector<player_item_snapshot> written;
	query_result result = claim_graph(connection, owner, snapshot.items, claims, &written);
	if (!result.ok)
		return result;
	// A save carries the whole item graph: the pipeline marks equipment and inventory together.
	result = execute(connection,
			 "DELETE FROM player_items WHERE pid=" + std::to_string(snapshot.pid));
	if (!result.ok)
		return result;
	return insert_item_rows(connection, written, std::to_string(snapshot.pid),
				player_item_tables);
}

query_result pet_has_live_custody(MYSQL *connection, int pid, uint64_t pet_uid, bool *has_custody)
{
	if (!has_custody)
		return { false, EINVAL };
	*has_custody = false;
	if (!pet_uid)
		return { true, 0 };
	const std::string sql =
		"SELECT 1 FROM item_current_owner WHERE owner_type=" +
		std::to_string(static_cast<unsigned>(item_owner_type::pet)) +
		" AND owner_id=" + std::to_string(pet_uid) +
		" AND owner_context_id=" + std::to_string(pid) + " AND state IN (" +
		std::to_string(static_cast<unsigned>(item_custody_state::active)) + "," +
		std::to_string(static_cast<unsigned>(item_custody_state::quarantined)) +
		") LIMIT 1";
	query_result result = execute(connection, sql);
	if (!result.ok)
		return result;
	MYSQL_RES *rows = mysql_store_result(connection);
	if (!rows)
		return { false, mysql_errno(connection) };
	MYSQL_ROW row = mysql_fetch_row(rows);
	*has_custody = row != nullptr;
	mysql_free_result(rows);
	return { true, 0 };
}

query_result apply_pets(MYSQL *connection, const player_snapshot &snapshot,
			std::vector<claimed_graph> *claims)
{
	query_result result = { true, 0 };
	std::unordered_set<uint64_t> retained;
	std::unordered_set<uint64_t> pet_uids;
	for (const player_pet_snapshot &pet : snapshot.pets)
	{
		if (pet.pet_uid && !pet_uids.insert(pet.pet_uid).second)
			return { false, EINVAL };
		if (pet.hold_reason == pet_hold_reason::custody_pending)
		{
			bool has_custody = false;
			result = pet_has_live_custody(connection, snapshot.pid, pet.pet_uid,
						      &has_custody);
			if (!result.ok)
				return result;
			if (!has_custody)
				continue;
		}
		uint64_t pet_id = 0;
		if (pet.pet_uid)
		{
			// The pet is whoever holds it in memory; its row follows it.
			result = execute(connection, "SELECT id FROM player_pets WHERE pet_uid=" +
							     std::to_string(pet.pet_uid) +
							     " FOR UPDATE");
			if (!result.ok)
				return result;
			MYSQL_RES *rows = mysql_store_result(connection);
			if (!rows)
				return { false, mysql_errno(connection) };
			MYSQL_ROW row = mysql_fetch_row(rows);
			if (row && row[0])
				pet_id = std::strtoull(row[0], nullptr, 10);
			mysql_free_result(rows);
		}
		// A pet's items belong to the pet; a legacy pet without a UID keeps its
		// items under its owner.
		const item_owner_identity owner =
			pet.pet_uid ? item_owner_identity{ item_owner_type::pet, pet.pet_uid,
							   static_cast<uint64_t>(snapshot.pid) } :
				      item_owner_identity{ item_owner_type::player,
							   static_cast<uint64_t>(snapshot.pid), 0 };
		std::vector<player_item_snapshot> written;
		result = claim_graph(connection, owner, pet.items, claims, &written);
		if (!result.ok)
			return result;
		std::ostringstream sql;
		if (pet_id)
			sql << "UPDATE player_pets SET owner_pid=" << snapshot.pid
			    << ",mob_vnum=" << pet.mob_vnum << ",pet_order=" << pet.order
			    << ",hit=" << pet.hit << ",max_hit=" << pet.max_hit
			    << ",mana=" << pet.mana << ",max_mana=" << pet.max_mana
			    << ",vitality=" << pet.vitality << ",max_vitality=" << pet.max_vitality
			    << ",charm_duration=" << pet.charm_duration
			    << ",room_vnum=" << pet.room_vnum << ",saved_at=NOW(),restore_state="
			    << quote(connection, pet.restore_state)
			    << ",hold_reason=" << static_cast<uint32_t>(pet.hold_reason)
			    << " WHERE id=" << pet_id;
		else
		{
			sql << "INSERT INTO player_pets (owner_pid,mob_vnum,pet_order,hit,"
			       "max_hit,mana,max_mana,vitality,max_vitality,charm_duration,room_vnum,"
			       "saved_at,restore_state,hold_reason";
			if (pet.pet_uid)
				sql << ",pet_uid";
			sql << ") VALUES (" << snapshot.pid << ',' << pet.mob_vnum << ','
			    << pet.order << ',' << pet.hit << ',' << pet.max_hit << ',' << pet.mana
			    << ',' << pet.max_mana << ',' << pet.vitality << ',' << pet.max_vitality
			    << ',' << pet.charm_duration << ',' << pet.room_vnum << ",NOW(),"
			    << quote(connection, pet.restore_state) << ','
			    << static_cast<uint32_t>(pet.hold_reason);
			if (pet.pet_uid)
				sql << ',' << pet.pet_uid;
			sql << ')';
		}
		result = execute(connection, sql.str());
		if (!result.ok)
			return result;
		if (!pet_id)
			pet_id = mysql_insert_id(connection);
		if (!pet_id ||
		    pet_id > static_cast<unsigned long long>(std::numeric_limits<int>::max()))
			return { false, EIO };
		retained.insert(pet_id);
		result = execute(connection, "DELETE FROM player_pet_items WHERE pet_id=" +
						     std::to_string(pet_id));
		if (!result.ok)
			return result;
		result = insert_item_rows(connection, written, std::to_string(pet_id),
					  pet_item_tables);
		if (!result.ok)
			return result;
	}
	std::string missing = "owner_pid=" + std::to_string(snapshot.pid);
	if (!retained.empty())
	{
		missing += " AND id NOT IN (";
		for (uint64_t id : retained)
			missing += std::to_string(id) + ',';
		missing.back() = ')';
	}
	const std::string custody =
		"EXISTS (SELECT 1 FROM item_current_owner own WHERE own.owner_type=" +
		std::to_string(static_cast<unsigned>(item_owner_type::pet)) +
		" AND own.owner_id=player_pets.pet_uid AND own.owner_context_id=" +
		std::to_string(snapshot.pid) + " AND own.state IN (" +
		std::to_string(static_cast<unsigned>(item_custody_state::active)) + "," +
		std::to_string(static_cast<unsigned>(item_custody_state::quarantined)) + "))";
	result = execute(connection, "UPDATE player_pets SET hold_reason=" +
					     std::to_string(static_cast<uint32_t>(
						     pet_hold_reason::custody_pending)) +
					     ",room_vnum=" + std::to_string(snapshot.room_vnum) +
					     " WHERE " + missing + " AND " + custody);
	if (!result.ok)
		return result;
	return execute(connection,
		       "DELETE FROM player_pets WHERE " + missing + " AND NOT " + custody);
}

query_result apply_shapes(MYSQL *connection, const player_snapshot &snapshot)
{
	return replace_rows(connection, snapshot.pid, "player_shapechanges",
			    "mob_vnum,times_researched,last_researched,last_shapechanged",
			    snapshot.shapes,
			    [](auto &sql, const auto &row)
			    {
				    sql << row.mob_vnum << ',' << row.times_researched
					<< ",FROM_UNIXTIME(NULLIF(" << row.last_researched
					<< ",0)),FROM_UNIXTIME(NULLIF(" << row.last_shapechanged
					<< ",0))";
			    });
}

query_result apply_trophies(MYSQL *connection, const player_snapshot &snapshot)
{
	query_result result = execute(connection, "DELETE FROM zone_trophy WHERE pid=" +
							  std::to_string(snapshot.pid));
	if (!result.ok || snapshot.trophies.empty())
		return result;
	std::ostringstream sql;
	sql << "INSERT INTO zone_trophy (pid,zone_number,exp) VALUES ";
	for (size_t index = 0; index < snapshot.trophies.size(); ++index)
		sql << (index ? "," : "") << '(' << snapshot.pid << ','
		    << snapshot.trophies[index].zone_number << ','
		    << snapshot.trophies[index].experience << ')';
	return execute(connection, sql.str());
}

query_result apply_components(MYSQL *connection, const player_snapshot &snapshot,
			      std::vector<claimed_graph> *claims)
{
	query_result result = { true, 0 };
	if (snapshot.components & PLAYER_COMPONENT_STATUS)
		result = apply_status(connection, snapshot);
	if (result.ok)
		result = apply_replacement_rows(connection, snapshot);
	if (result.ok && (snapshot.components & PLAYER_COMPONENT_SKILLS))
		result = apply_skills(connection, snapshot);
	if (result.ok && (snapshot.components & PLAYER_COMPONENT_AFFECTS))
		result = apply_affects(connection, snapshot);
	if (result.ok &&
	    (snapshot.components & (PLAYER_COMPONENT_EQUIPMENT | PLAYER_COMPONENT_INVENTORY)))
		result = apply_items(connection, snapshot, claims);
	if (result.ok && (snapshot.components & PLAYER_COMPONENT_PETS))
		result = apply_pets(connection, snapshot, claims);
	if (result.ok && (snapshot.components & PLAYER_COMPONENT_SHAPECHANGES))
		result = apply_shapes(connection, snapshot);
	if (result.ok && (snapshot.components & PLAYER_COMPONENT_TROPHIES))
		result = apply_trophies(connection, snapshot);
	return result;
}

// A character with no player_data row yet gets one (*created). The rest of the save fills
// it in.
query_result ensure_player_row(MYSQL *connection, const player_snapshot &snapshot, bool *created)
{
	*created = false;
	query_result result =
		execute(connection, "SELECT save_revision FROM player_data WHERE pid=" +
					    std::to_string(snapshot.pid) + " FOR UPDATE");
	if (!result.ok)
		return result;
	MYSQL_RES *rows = mysql_store_result(connection);
	if (!rows)
		return { false, mysql_errno(connection) };
	const bool present = mysql_fetch_row(rows) != nullptr;
	mysql_free_result(rows);
	if (present)
		return { true, 0 };
	const auto name = std::find_if(snapshot.status_strings.begin(),
				       snapshot.status_strings.end(),
				       [](const player_snapshot_string &row)
				       { return row.field == player_status_string_field::name; });
	if (name == snapshot.status_strings.end() || name->value.empty())
		return { false, ENOENT };
	*created = true;
	return execute(connection, "INSERT INTO player_data (pid,name) VALUES (" +
					   std::to_string(snapshot.pid) + "," +
					   quote(connection, name->value) + ")");
}

// A new character's opening balances, from the row its first save has just written: the
// accounting ledgers start from them.
query_result insert_opening_baselines(MYSQL *connection, int pid)
{
	const std::string from = " FROM player_data WHERE pid=" + std::to_string(pid);
	query_result result = execute(
		connection, "INSERT IGNORE INTO currency_wallet_baseline(pid,opening_copper,"
			    "opening_silver,opening_gold,opening_platinum,opening_revision) "
			    "SELECT pid,copper,silver,gold,platinum,0" +
				    from);
	if (result.ok)
		result =
			execute(connection, "INSERT IGNORE INTO epic_balance_baseline(pid,"
					    "opening_balance,opening_revision) SELECT pid,epics,0" +
						    from);
	if (result.ok)
		result = execute(connection, "INSERT IGNORE INTO combat_frag_baseline(pid,"
					     "opening_frags,opening_revision) SELECT pid,frags,0" +
						     from);
	return result;
}

player_save_apply_result apply_snapshot(MYSQL *connection, const player_snapshot &snapshot)
{
	if (!connection || snapshot.pid <= 0 || !snapshot.revision || !snapshot.components ||
	    (snapshot.components & ~PLAYER_CHECKPOINT_COMPONENT_ALL))
		return { player_save_apply_outcome::terminal_failure, 0, EINVAL };
	if (snapshot.schema_version != PLAYER_SNAPSHOT_SCHEMA_VERSION)
		return { player_save_apply_outcome::terminal_failure, 0, ENOTSUP };

	query_result query = execute(connection, "START TRANSACTION");
	if (!query.ok)
		return failure(query.error_code);
	std::vector<claimed_graph> claims;
	bool created = false;
	query = ensure_player_row(connection, snapshot, &created);
	if (query.ok)
		query = apply_components(connection, snapshot, &claims);
	if (query.ok && created)
		query = insert_opening_baselines(connection, snapshot.pid);
	if (query.ok)
		query = execute(connection, "UPDATE player_data SET save_revision=" +
						    std::to_string(snapshot.revision) +
						    " WHERE pid=" + std::to_string(snapshot.pid));
	if (!query.ok)
	{
		if (!connection_error(query.error_code))
			execute(connection, "ROLLBACK");
		return failure(query.error_code);
	}
	query = execute(connection, "COMMIT");
	if (!query.ok)
	{
		// A lost connection may or may not have committed. The save is a full
		// replacement, so writing it again is always safe.
		if (!connection_error(query.error_code))
			execute(connection, "ROLLBACK");
		return { connection_error(query.error_code) ?
				 player_save_apply_outcome::ambiguous_commit :
				 failure(query.error_code).outcome,
			 0, query.error_code };
	}
	for (const claimed_graph &claim : claims)
		item_claim_log_dupes("save_left_out", claim.owner, claim.outcome);
	return { player_save_apply_outcome::applied, snapshot.revision, 0 };
}

// Reads one unsigned value; *found is false when the query returns no row.
query_result read_value(MYSQL *connection, const std::string &sql, bool *found, uint64_t *value)
{
	*found = false;
	query_result result = execute(connection, sql);
	if (!result.ok)
		return result;
	MYSQL_RES *rows = mysql_store_result(connection);
	if (!rows)
		return { false, mysql_errno(connection) ? mysql_errno(connection) : EIO };
	if (MYSQL_ROW row = mysql_fetch_row(rows))
	{
		char *end = nullptr;
		*value = row[0] ? std::strtoull(row[0], &end, 10) : 0;
		*found = row[0] && end && !*end && !mysql_fetch_row(rows);
		if (!*found)
		{
			mysql_free_result(rows);
			return { false, EILSEQ };
		}
	}
	mysql_free_result(rows);
	return { true, 0 };
}

// Record the player's death and the corpse's eligible items as collector candidates. A
// refusal (a full catalog, a death recorded differently) leaves the corpse saved without,
// and is set in refused.
query_result enroll_collector_death(MYSQL *connection, const collector_death_snapshot &death,
				    const std::vector<player_item_snapshot> &items,
				    unsigned int *refused)
{
	std::vector<uint64_t> eligible;
	try
	{
		for (const player_item_snapshot &item : items)
			if (collector_death_item_snapshot_eligible(item))
				eligible.push_back(item.object_uid);
	}
	catch (const std::bad_alloc &)
	{
		return { false, ENOMEM };
	}
	std::sort(eligible.begin(), eligible.end());
	if (!collector_repository_enroll_death(connection, death, eligible, refused))
		return { false, errno ? static_cast<unsigned int>(errno) : EIO };
	return { true, 0 };
}

query_result write_corpse(MYSQL *connection, const corpse_snapshot &corpse,
			  std::vector<claimed_graph> *claims, unsigned int *collector_refused)
{
	bool found = false;
	uint64_t catalog_revision = 0;
	query_result result = read_value(
		connection,
		"SELECT catalog_revision FROM corpse_catalog_state WHERE state_id=1 FOR UPDATE",
		&found, &catalog_revision);
	if (!result.ok)
		return result;
	if (!found || !catalog_revision || catalog_revision == UINT64_MAX)
		return { false, EILSEQ };
	const std::string key = "player_name=" + quote(connection, corpse.player_name) +
				" AND save_id=" + std::to_string(corpse.save_id);
	uint64_t corpse_revision = 0;
	result = read_value(connection,
			    "SELECT corpse_revision FROM corpses WHERE " + key + " FOR UPDATE",
			    &found, &corpse_revision);
	if (!result.ok)
		return result;
	if (!found && corpse.remove)
		return { true, 0 };
	// The corpse's items, affects and descriptions go with its row.
	if (found && !(result = execute(connection, "DELETE FROM corpses WHERE " + key)).ok)
		return result;
	if (!corpse.remove)
	{
		std::ostringstream sql;
		sql << "INSERT INTO corpses (player_name,save_id,corpse_revision,room_vnum,"
		       "short_descr,description,name,weight,value0,value1,value2,value3,value4,"
		       "value5,value7) VALUES ("
		    << quote(connection, corpse.player_name) << ',' << corpse.save_id << ','
		    << (found ? corpse_revision + 1 : 1) << ',' << corpse.room_vnum << ','
		    << quote(connection, corpse.short_description) << ','
		    << quote(connection, corpse.description) << ','
		    << quote(connection, corpse.keywords) << ',' << corpse.weight;
		for (size_t index : { 0, 1, 2, 3, 4, 5, 7 })
			sql << ',' << corpse.values[index];
		sql << ')';
		if (!(result = execute(connection, sql.str())).ok)
			return result;
		const unsigned long long corpse_id = mysql_insert_id(connection);
		if (!corpse_id)
			return { false, EIO };
		std::vector<player_item_snapshot> written;
		if (!(result =
			      claim_graph(connection, corpse.owner, corpse.items, claims, &written))
			     .ok ||
		    !(result = insert_item_rows(connection, written, std::to_string(corpse_id),
						corpse_item_tables))
			     .ok)
			return result;
		if (!critical_operation_id_is_zero(corpse.collector_death.operation_id) &&
		    !(result = enroll_collector_death(connection, corpse.collector_death, written,
						      collector_refused))
			     .ok)
			return result;
	}
	result = execute(connection, "UPDATE corpse_catalog_state SET catalog_revision=" +
					     std::to_string(catalog_revision + 1) +
					     " WHERE state_id=1 AND catalog_revision=" +
					     std::to_string(catalog_revision));
	if (result.ok && mysql_affected_rows(connection) != 1)
		return { false, EILSEQ };
	return result;
}

// Run one corpse, saved-item or locker chest write in its own transaction, then log
// what the claims left out.
template <typename Write> player_save_apply_result apply_owner_write(MYSQL *connection, Write write)
{
	query_result query = execute(connection, "START TRANSACTION");
	if (!query.ok)
		return failure(query.error_code);
	std::vector<claimed_graph> claims;
	query = write(&claims);
	if (!query.ok)
	{
		if (!connection_error(query.error_code))
			execute(connection, "ROLLBACK");
		return failure(query.error_code);
	}
	query = execute(connection, "COMMIT");
	if (!query.ok)
	{
		// The write is a full replacement, so writing it again is safe.
		if (!connection_error(query.error_code))
			execute(connection, "ROLLBACK");
		return { connection_error(query.error_code) ?
				 player_save_apply_outcome::ambiguous_commit :
				 failure(query.error_code).outcome,
			 0, query.error_code };
	}
	for (const claimed_graph &claim : claims)
		item_claim_log_dupes("save_left_out", claim.owner, claim.outcome);
	return { player_save_apply_outcome::applied, 0, 0 };
}

player_save_apply_result apply_corpse(MYSQL *connection, const corpse_snapshot &corpse)
{
	if (!connection || corpse.owner.type != item_owner_type::corpse || !corpse.owner.id ||
	    corpse.save_id <= 0 || corpse.player_name.empty())
		return { player_save_apply_outcome::terminal_failure, 0, EINVAL };
	unsigned int collector_refused = 0;
	player_save_apply_result result = apply_owner_write(
		connection, [&](std::vector<claimed_graph> *claims)
		{ return write_corpse(connection, corpse, claims, &collector_refused); });
	// A corpse saved without its death says why.
	if (result.outcome == player_save_apply_outcome::applied)
		result.error_code = collector_refused;
	return result;
}

query_result write_saved_item(MYSQL *connection, const saved_item_snapshot &item,
			      std::vector<claimed_graph> *claims)
{
	const std::string key = quote(connection, item.item_key);
	query_result result = execute(connection, "DELETE FROM saved_items WHERE item_key=" + key);
	if (!result.ok || item.remove)
		return result;
	std::vector<player_item_snapshot> written;
	if (!(result = claim_graph(connection, item.owner, item.items, claims, &written)).ok)
		return result;
	return insert_item_rows(connection, written, key + "," + std::to_string(item.room_vnum),
				saved_item_tables);
}

player_save_apply_result apply_saved_item(MYSQL *connection, const saved_item_snapshot &item)
{
	if (!connection || item.owner.type != item_owner_type::room || item.item_key.empty() ||
	    (!item.remove && item.items.empty()))
		return { player_save_apply_outcome::terminal_failure, 0, EINVAL };
	return apply_owner_write(connection, [&](std::vector<claimed_graph> *claims)
				 { return write_saved_item(connection, item, claims); });
}

player_save_apply_result apply_shopkeeper(MYSQL *connection, const flatfile_shopkeeper_record &shop)
{
	if (!connection || !shop.mob_vnum)
		return { player_save_apply_outcome::terminal_failure, 0, EINVAL };
	return apply_owner_write(
		connection,
		[&](std::vector<claimed_graph> *)
		{
			const std::string shop_id = std::to_string(shop.shop_id);
			query_result result = execute(
				connection, "DELETE FROM shopkeepers WHERE shop_id=" + shop_id);
			if (result.ok)
				result = execute(
					connection,
					"INSERT INTO shopkeepers (shop_id,mob_vnum,room_vnum,"
					"save_time) VALUES (" +
						shop_id + "," + std::to_string(shop.mob_vnum) +
						"," + std::to_string(shop.room_vnum) +
						",FROM_UNIXTIME(NULLIF(" +
						std::to_string(shop.saved_at) + ",0)))");
			if (!result.ok)
				return result;
			const std::string keeper = std::to_string(mysql_insert_id(connection));
			for (const flatfile_shopkeeper_affect_record &affect : shop.affects)
			{
				std::ostringstream sql;
				sql << "INSERT INTO shopkeeper_affects (shopkeeper_id,type,duration,"
				       "modifier,location,bitvector1,bitvector2,bitvector3,bitvector4,"
				       "bitvector5) VALUES ("
				    << keeper << ',' << affect.type << ',' << affect.duration << ','
				    << affect.modifier << ',' << affect.location;
				for (uint64_t bitvector : affect.bitvectors)
					sql << ',' << bitvector;
				sql << ')';
				if (!(result = execute(connection, sql.str())).ok)
					return result;
			}
			return insert_item_rows(connection, shop.items, keeper,
						shopkeeper_item_tables);
		});
}

player_save_apply_result apply_locker_chest(MYSQL *connection, const locker_chest_snapshot &chest)
{
	if (!connection || chest.locker_id <= 0 || chest.chest_id <= 0)
		return { player_save_apply_outcome::terminal_failure, 0, EINVAL };
	const item_owner_identity owner = { item_owner_type::locker,
					    static_cast<uint64_t>(chest.locker_id),
					    static_cast<uint64_t>(chest.chest_id) };
	const std::string keys =
		std::to_string(chest.locker_id) + "," + std::to_string(chest.chest_id);
	return apply_owner_write(
		connection,
		[&](std::vector<claimed_graph> *claims)
		{
			query_result result =
				execute(connection,
					"DELETE FROM locker_items WHERE locker_id=" +
						std::to_string(chest.locker_id) +
						" AND chest_id=" + std::to_string(chest.chest_id));
			std::vector<player_item_snapshot> written;
			if (result.ok)
				result = claim_graph(connection, owner, chest.items, claims,
						     &written);
			return result.ok ? insert_item_rows(connection, written, keys,
							    locker_item_tables) :
					   result;
		});
}

// The locker's row and its public chest, created for a new locker.
query_result find_locker(MYSQL *connection, const locker_snapshot &locker, uint64_t *locker_id,
			 uint64_t *public_id)
{
	const std::string name = quote(connection, locker.locker_name);
	bool found = false;
	query_result result = read_value(
		connection, "SELECT id FROM lockers WHERE locker_name=" + name, &found, locker_id);
	if (result.ok && !found)
	{
		const std::string owner_pid =
			locker.owner_name.empty() ?
				"NULL" :
				"(SELECT pid FROM player_data WHERE LOWER(name)=LOWER(" +
					quote(connection, locker.owner_name) + ") LIMIT 1)";
		result = execute(
			connection,
			"INSERT INTO lockers (locker_name,owner_pid,owner_assoc_id,racewar,race) "
			"VALUES (" +
				name + ',' + owner_pid + ',' +
				(locker.owner_assoc_id > 0 ? std::to_string(locker.owner_assoc_id) :
							     "NULL") +
				',' + std::to_string(locker.racewar) + ',' +
				std::to_string(locker.race) + ')');
		*locker_id = result.ok ? mysql_insert_id(connection) : 0;
	}
	if (!result.ok)
		return result;
	if (!*locker_id)
		return { false, EIO };
	const std::string id = std::to_string(*locker_id);
	result = read_value(connection,
			    "SELECT id FROM private_chests WHERE locker_id=" + id +
				    " AND is_public=1 ORDER BY id LIMIT 1",
			    &found, public_id);
	if (result.ok && !found)
	{
		result = execute(
			connection,
			"INSERT INTO private_chests (locker_id,chest_name,is_public) VALUES (" +
				id + ",'public',1)");
		*public_id = result.ok ? mysql_insert_id(connection) : 0;
	}
	if (result.ok && !*public_id)
		return { false, EIO };
	return result;
}

player_save_apply_result apply_locker(MYSQL *connection, const locker_snapshot &locker)
{
	if (!connection || locker.locker_name.empty())
		return { player_save_apply_outcome::terminal_failure, 0, EINVAL };
	return apply_owner_write(
		connection,
		[&](std::vector<claimed_graph> *claims)
		{
			uint64_t locker_id = 0, public_id = 0;
			query_result result =
				find_locker(connection, locker, &locker_id, &public_id);
			const std::string keys =
				std::to_string(locker_id) + "," + std::to_string(public_id);
			// Rows written before public chests existed have no chest_id.
			if (result.ok)
				result = execute(connection,
						 "DELETE FROM locker_items WHERE locker_id=" +
							 std::to_string(locker_id) +
							 " AND (chest_id IS NULL OR chest_id=" +
							 std::to_string(public_id) + ")");
			std::vector<player_item_snapshot> written;
			if (result.ok)
				result = claim_graph(connection,
						     { item_owner_type::locker, locker_id,
						       public_id },
						     locker.items, claims, &written);
			return result.ok ? insert_item_rows(connection, written, keys,
							    locker_item_tables) :
					   result;
		});
}

player_save_apply_result apply_log_entry(MYSQL *connection, const log_entry_snapshot &entry)
{
	if (!connection || entry.kind.empty())
		return { player_save_apply_outcome::terminal_failure, 0, EINVAL };
	const query_result result = execute(
		connection,
		"INSERT INTO log_entries (date,kind,ip_address,pid,player_name,zone_number,"
		"room_vnum,message) VALUES (FROM_UNIXTIME(" +
			std::to_string(entry.logged_at) + ")," + quote(connection, entry.kind) +
			',' + quote(connection, entry.ip_address) + ',' +
			std::to_string(entry.pid) + ',' + quote(connection, entry.player_name) +
			',' + std::to_string(entry.zone_number) + ',' +
			std::to_string(entry.room_vnum) + ',' + quote(connection, entry.message) +
			')');
	if (!result.ok)
		return failure(result.error_code);
	return { player_save_apply_outcome::applied, 0, 0 };
}

player_save_apply_result apply_sql_work(MYSQL *connection, const sql_work &work)
{
	query_result query = execute(connection, "START TRANSACTION");
	if (!query.ok)
		return failure(query.error_code);
	if (const unsigned int error_code = work(connection))
	{
		if (!connection_error(error_code))
			execute(connection, "ROLLBACK");
		return failure(error_code);
	}
	query = execute(connection, "COMMIT");
	if (query.ok)
		return { player_save_apply_outcome::applied, 0, 0 };
	if (connection_error(query.error_code))
		return { player_save_apply_outcome::terminal_failure, 0, query.error_code };
	execute(connection, "ROLLBACK");
	return failure(query.error_code);
}

player_save_apply_result apply_bank_delta(MYSQL *connection, const bank_delta_snapshot &bank)
{
	if (!connection || bank.account_name.empty())
		return { player_save_apply_outcome::terminal_failure, 0, EINVAL };
	static constexpr std::array<const char *, 4> columns = { "bank_copper", "bank_silver",
								 "bank_gold", "bank_platinum" };
	std::ostringstream sql;
	sql << "INSERT INTO account_banks (account_name,racewar,bank_copper,bank_silver,bank_gold,"
	       "bank_platinum) VALUES ("
	    << quote(connection, bank.account_name) << ',' << bank.racewar;
	for (int64_t amount : bank.delta)
		sql << ',' << std::max<int64_t>(amount, 0);
	sql << ") ON DUPLICATE KEY UPDATE bank_revision=bank_revision+1";
	// The columns are unsigned: a debit subtracts, so one the row cannot cover fails.
	for (size_t index = 0; index < columns.size(); ++index)
		if (bank.delta[index] > 0)
			sql << ',' << columns[index] << '=' << columns[index] << '+'
			    << bank.delta[index];
		else if (bank.delta[index] < 0)
			sql << ',' << columns[index] << '=' << columns[index] << '-'
			    << -bank.delta[index];
	// A delta written twice pays twice. In a transaction, a connection lost before
	// the commit leaves nothing written, so the retry is safe; a commit whose outcome
	// is unknown is reported instead of retried.
	return apply_sql_work(connection, [&](MYSQL *transaction)
			      { return execute(transaction, sql.str()).error_code; });
}

template <typename Apply> player_save_apply_result apply_with_pool(Apply apply)
{
	MYSQL *connection = sql_pool_acquire();
	if (!connection)
		return { player_save_apply_outcome::retryable_failure, 0, ETIMEDOUT };
	const player_save_apply_result applied = apply(connection);
	if (applied.outcome == player_save_apply_outcome::ambiguous_commit ||
	    connection_error(applied.error_code))
	{
		MYSQL *replacement = sql_pool_replace_connection(connection);
		if (!replacement)
		{
			sql_pool_release(connection);
			return applied;
		}
		connection = replacement;
	}
	sql_pool_release(connection);
	return applied;
}
} // namespace

bool player_snapshot_repository_write_pets(MYSQL *connection, const player_snapshot &snapshot)
{
	if (!connection || snapshot.pid <= 0)
		return false;
	std::vector<claimed_graph> claims;
	if (!apply_pets(connection, snapshot, &claims).ok)
		return false;
	for (const claimed_graph &claim : claims)
		item_claim_log_dupes("save_left_out", claim.owner, claim.outcome);
	return true;
}

player_save_apply_result player_snapshot_repository_apply(MYSQL *connection,
							  const player_snapshot &snapshot)
{
	return apply_snapshot(connection, snapshot);
}

player_save_apply_result player_snapshot_repository_apply_from_pool(const player_snapshot &snapshot,
								    void * /*context*/)
{
	return apply_with_pool([&](MYSQL *connection)
			       { return apply_snapshot(connection, snapshot); });
}

player_save_apply_result corpse_snapshot_repository_apply(MYSQL *connection,
							  const corpse_snapshot &corpse)
{
	return apply_corpse(connection, corpse);
}

player_save_apply_result corpse_snapshot_repository_apply_from_pool(const corpse_snapshot &corpse)
{
	return apply_with_pool([&](MYSQL *connection) { return apply_corpse(connection, corpse); });
}

player_save_apply_result
shopkeeper_snapshot_repository_apply(MYSQL *connection, const flatfile_shopkeeper_record &shop)
{
	return apply_shopkeeper(connection, shop);
}

player_save_apply_result
shopkeeper_snapshot_repository_apply_from_pool(const flatfile_shopkeeper_record &shop)
{
	return apply_with_pool([&](MYSQL *connection)
			       { return apply_shopkeeper(connection, shop); });
}

player_save_apply_result saved_item_snapshot_repository_apply(MYSQL *connection,
							      const saved_item_snapshot &item)
{
	return apply_saved_item(connection, item);
}

player_save_apply_result
saved_item_snapshot_repository_apply_from_pool(const saved_item_snapshot &item)
{
	return apply_with_pool([&](MYSQL *connection)
			       { return apply_saved_item(connection, item); });
}

player_save_apply_result locker_chest_snapshot_repository_apply(MYSQL *connection,
								const locker_chest_snapshot &chest)
{
	return apply_locker_chest(connection, chest);
}

player_save_apply_result
locker_chest_snapshot_repository_apply_from_pool(const locker_chest_snapshot &chest)
{
	return apply_with_pool([&](MYSQL *connection)
			       { return apply_locker_chest(connection, chest); });
}

player_save_apply_result locker_snapshot_repository_apply(MYSQL *connection,
							  const locker_snapshot &locker)
{
	return apply_locker(connection, locker);
}

player_save_apply_result locker_snapshot_repository_apply_from_pool(const locker_snapshot &locker)
{
	return apply_with_pool([&](MYSQL *connection) { return apply_locker(connection, locker); });
}

player_save_apply_result log_entry_repository_apply(MYSQL *connection,
						    const log_entry_snapshot &entry)
{
	return apply_log_entry(connection, entry);
}

player_save_apply_result log_entry_repository_apply_from_pool(const log_entry_snapshot &entry)
{
	return apply_with_pool([&](MYSQL *connection)
			       { return apply_log_entry(connection, entry); });
}

player_save_apply_result sql_work_repository_apply(MYSQL *connection, const sql_work &work)
{
	if (!connection || !work)
		return { player_save_apply_outcome::terminal_failure, 0, EINVAL };
	return apply_sql_work(connection, work);
}

player_save_apply_result sql_work_repository_apply_from_pool(const sql_work &work)
{
	if (!work)
		return { player_save_apply_outcome::terminal_failure, 0, EINVAL };
	return apply_with_pool([&](MYSQL *connection) { return apply_sql_work(connection, work); });
}

player_save_apply_result bank_delta_repository_apply(MYSQL *connection,
						     const bank_delta_snapshot &bank)
{
	return apply_bank_delta(connection, bank);
}

player_save_apply_result bank_delta_repository_apply_from_pool(const bank_delta_snapshot &bank)
{
	return apply_with_pool([&](MYSQL *connection)
			       { return apply_bank_delta(connection, bank); });
}

unsigned int sql_execute(MYSQL *connection, const std::string &statement)
{
	if (const unsigned int error_code = execute(connection, statement).error_code)
		return error_code;
	// A statement that returns rows must still be drained.
	if (MYSQL_RES *result = mysql_store_result(connection))
		mysql_free_result(result);
	return mysql_errno(connection);
}

unsigned int sql_select(MYSQL *connection, const std::string &query, sql_rows *rows)
{
	if (const unsigned int error_code = execute(connection, query).error_code)
		return error_code;
	MYSQL_RES *result = mysql_store_result(connection);
	if (!result)
		return mysql_errno(connection);
	const unsigned int width = mysql_num_fields(result);
	try
	{
		rows->reserve(rows->size() + mysql_num_rows(result));
		while (MYSQL_ROW row = mysql_fetch_row(result))
		{
			const unsigned long *lengths = mysql_fetch_lengths(result);
			sql_row copied;
			copied.fields.reserve(width);
			for (unsigned int index = 0; index < width; ++index)
				if (row[index])
					copied.fields.emplace_back(std::in_place, row[index],
								   lengths[index]);
				else
					copied.fields.emplace_back();
			rows->push_back(std::move(copied));
		}
	}
	catch (const std::bad_alloc &)
	{
		mysql_free_result(result);
		return ENOMEM;
	}
	mysql_free_result(result);
	return 0;
}
