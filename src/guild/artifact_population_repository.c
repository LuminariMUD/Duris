#include "guild/artifact_population_repository.h"

#ifndef __NO_MYSQL__
#include <charconv>
#include <cerrno>
#include <cstring>
#include <memory>
#include <new>
#include <string>

namespace
{
template <typename T> bool number(const char *text, T *value)
{
	*value = 0;
	if (!text)
		return true;
	const char *end = text + strlen(text);
	const auto parsed = std::from_chars(text, end, *value);
	return parsed.ec == std::errc{} && parsed.ptr == end;
}
} // namespace

unsigned int artifact_population_read_sql_page(MYSQL *connection, artifact_payload_domain domain,
					       uint64_t after_row_id,
					       artifact_population_sql_page *page)
{
	if (!connection || !page)
		return EINVAL;
	const char *table = nullptr, *owner = nullptr, *context = "0", *quantity = "i.quantity";
	const char *owner_id = "0", *owner_context = "0", *metadata = "";
	item_owner_type payload_owner_type = item_owner_type::unknown;
	switch (domain)
	{
	case artifact_payload_domain::player:
		table = "player_items";
		owner = "pid";
		owner_id = "i.pid";
		payload_owner_type = item_owner_type::player;
		break;
	case artifact_payload_domain::pet:
		table = "player_pet_items";
		owner = "pet_id";
		quantity = "1";
		owner_id = "pp.pet_uid";
		owner_context = "pp.owner_pid";
		metadata = " LEFT JOIN player_pets pp ON pp.id=i.pet_id";
		payload_owner_type = item_owner_type::pet;
		break;
	case artifact_payload_domain::locker:
		table = "locker_items";
		owner = "locker_id";
		context = "COALESCE(i.chest_id,0)";
		owner_id = "i.locker_id";
		owner_context = "COALESCE(i.chest_id,public_chest.id,0)";
		metadata =
			" LEFT JOIN private_chests public_chest ON "
			"public_chest.locker_id=i.locker_id AND i.chest_id IS NULL AND public_chest.is_public=1";
		payload_owner_type = item_owner_type::locker;
		break;
	case artifact_payload_domain::account_locker:
		table = "account_locker_items";
		owner = "chest_id";
		break;
	case artifact_payload_domain::corpse:
		table = "corpse_items";
		owner = "corpse_id";
		owner_id = "IF(pd.pid>0 AND c.save_id BETWEEN 1 AND 4294967295,"
			   "((CAST(pd.pid AS UNSIGNED)<<32)|CAST(c.save_id AS UNSIGNED)),0)";
		metadata = " LEFT JOIN corpses c ON c.id=i.corpse_id "
			   "LEFT JOIN player_data pd ON LOWER(pd.name)=LOWER(c.player_name)";
		payload_owner_type = item_owner_type::corpse;
		break;
	case artifact_payload_domain::room:
		table = "saved_items";
		owner = "room_vnum";
		owner_id = "i.room_vnum";
		payload_owner_type = item_owner_type::room;
		break;
	case artifact_payload_domain::shopkeeper:
		table = "shopkeeper_items";
		owner = "shopkeeper_id";
		owner_id = "(CAST(sk.shop_id AS UNSIGNED)+1)";
		metadata = " LEFT JOIN shopkeepers sk ON sk.id=i.shopkeeper_id";
		payload_owner_type = item_owner_type::shopkeeper;
		break;
	case artifact_payload_domain::siege:
		table = "siege_items";
		owner = "room_vnum";
		break;
	default:
		return EINVAL;
	}
	try
	{
		const std::string owner_field = owner;
		const std::string parent_context =
			domain == artifact_payload_domain::locker ?
				" OR (p.chest_id IS NOT NULL AND i.chest_id IS NOT NULL AND p.chest_id<>i.chest_id)" :
				"";
		const std::string sql =
			"SELECT i.id,i.obj_uid,i.container_id,p.obj_uid,i." + owner_field + "," +
			context + ",i.vnum,i.extra_flags," + quantity +
			",(i.container_id IS NOT NULL AND (p.id IS NULL OR p.obj_uid IS NULL OR p.obj_uid=0)),"
			"(p.id IS NOT NULL AND (NOT (p." +
			owner_field + " <=> i." + owner_field + ")" + parent_context +
			")),own.item_uid,own.root_item_uid,own.parent_item_uid,own.owner_type,"
			"own.owner_id,own.owner_context_id,own.item_revision,own.vnum,own.state,"
			"rev.revision," +
			owner_id + "," + owner_context + " FROM " + table + " i" + metadata +
			" LEFT JOIN " + table +
			" p ON p.id=i.container_id LEFT JOIN item_current_owner own ON "
			"own.item_uid=i.obj_uid LEFT JOIN item_owner_revision rev ON "
			"rev.owner_type=own.owner_type AND rev.owner_id=own.owner_id AND "
			"rev.owner_context_id=own.owner_context_id WHERE i.id>" +
			std::to_string(after_row_id) + " ORDER BY i.id LIMIT " +
			std::to_string(ARTIFACT_POPULATION_SQL_PAGE_SIZE + 1);
		if (mysql_real_query(connection, sql.data(), sql.size()))
			return mysql_errno(connection);
		std::unique_ptr<MYSQL_RES, decltype(&mysql_free_result)> result(
			mysql_store_result(connection), mysql_free_result);
		if (!result)
			return mysql_errno(connection) ? mysql_errno(connection) : EIO;
		artifact_population_sql_page staged;
		staged.next_row_id = after_row_id;
		staged.complete = mysql_num_rows(result.get()) <= ARTIFACT_POPULATION_SQL_PAGE_SIZE;
		while (MYSQL_ROW row = mysql_fetch_row(result.get()))
		{
			uint64_t row_id = 0;
			if (!number(row[0], &row_id) || row_id <= staged.next_row_id)
				return EINVAL;
			if (staged.rows.size() == ARTIFACT_POPULATION_SQL_PAGE_SIZE)
				break;
			artifact_payload_projection item = {};
			item.domain = domain;
			item.row_id = row_id;
			item.payload_owner.type = payload_owner_type;
			unsigned int missing = 0, disagreement = 0, owner_type = 0, state = 0;
			if (!number(row[1], &item.item_uid) ||
			    !number(row[2], &item.parent_row_id) ||
			    !number(row[3], &item.parent_item_uid) ||
			    !number(row[4], &item.owner_reference) ||
			    !number(row[5], &item.owner_context) || !number(row[6], &item.vnum) ||
			    !number(row[7], &item.extra_flags) || !number(row[8], &item.quantity) ||
			    !number(row[9], &missing) || !number(row[10], &disagreement) ||
			    !number(row[11], &item.custody.item_uid) ||
			    !number(row[12], &item.custody.root_item_uid) ||
			    !number(row[13], &item.custody.parent_item_uid) ||
			    !number(row[14], &owner_type) || owner_type > UINT8_MAX ||
			    !number(row[15], &item.custody.owner.id) ||
			    !number(row[16], &item.custody.owner.context_id) ||
			    !number(row[17], &item.custody.item_revision) ||
			    !number(row[18], &item.custody.vnum) || !number(row[19], &state) ||
			    state > UINT8_MAX || !number(row[20], &item.custody.owner_revision) ||
			    !number(row[21], &item.payload_owner.id) ||
			    !number(row[22], &item.payload_owner.context_id))
				return EINVAL;
			// Legacy pets without a UID carry their player's custody, as the
			// actual player load path does. Missing pet metadata stays unknown.
			if (domain == artifact_payload_domain::pet && !item.payload_owner.id &&
			    item.payload_owner.context_id)
				item.payload_owner = { item_owner_type::player,
						       item.payload_owner.context_id, 0 };
			item.parent_missing = missing;
			item.extra_flags_present = row[7] != nullptr;
			item.parent_owner_disagrees = disagreement;
			item.custody_found = row[11] != nullptr;
			item.custody.owner.type = static_cast<item_owner_type>(owner_type);
			item.custody.state = static_cast<item_custody_state>(state);
			staged.next_row_id = item.row_id;
			staged.rows.push_back(item);
		}
		if (mysql_errno(connection))
			return mysql_errno(connection);
		*page = std::move(staged);
		return 0;
	}
	catch (const std::bad_alloc &)
	{
		return ENOMEM;
	}
}
#endif
