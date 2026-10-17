#include "guild/artifact_population_repository.h"

#ifndef __NO_MYSQL__
#include "guild/artifact_identity.h"
#include "core/defines.h"
#include "economy/collector_codec.h"
#include "economy/auction_command.h"
#include "item/legacy_object_identity.h"
#include "player/player_snapshot_codec.h"

#include <algorithm>
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
			"public_chest.locker_id=i.locker_id AND i.chest_id IS NULL AND public_chest.is_public=1"
			" LEFT JOIN private_chests parent_public_chest ON "
			"parent_public_chest.locker_id=p.locker_id AND p.chest_id IS NULL AND parent_public_chest.is_public=1";
		payload_owner_type = item_owner_type::locker;
		break;
	case artifact_payload_domain::account_locker:
		table = "account_locker_items";
		owner = "chest_id";
		break;
	case artifact_payload_domain::corpse:
		table = "corpse_items";
		owner = "corpse_id";
		owner_id =
			"IF(c.value3 BETWEEN 1 AND 4294967295 AND c.save_id BETWEEN 1 AND 4294967295,"
			"((CAST(c.value3 AS UNSIGNED)<<32)|CAST(c.save_id AS UNSIGNED)),0)";
		metadata = " LEFT JOIN corpses c ON c.id=i.corpse_id";
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
				" OR (COALESCE(p.chest_id,parent_public_chest.id,0)<>COALESCE(i.chest_id,public_chest.id,0))" :
			domain == artifact_payload_domain::room ?
				" OR (NOT (p.item_key <=> i.item_key))" :
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
			owner_id + "," + owner_context +
			",EXISTS(SELECT 1 FROM item_ownership_quarantine q WHERE q.repaired_at IS NULL AND "
			"((i.obj_uid<>0 AND q.item_uid=i.obj_uid) OR "
			"(COALESCE(i.obj_uid,0)=0 AND q.item_uid=0 AND q.source_table='" +
			table + "' AND q.source_row_id=i.id))) FROM " + table + " i LEFT JOIN " +
			table + " p ON p.id=i.container_id" + metadata +
			" LEFT JOIN item_current_owner own ON "
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
			unsigned int missing = 0, disagreement = 0, owner_type = 0, state = 0,
				     quarantined = 0;
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
			    !number(row[22], &item.payload_owner.context_id) ||
			    !number(row[23], &quarantined))
				return EINVAL;
			// Legacy pets without a UID carry their player's custody, as the
			// actual player load path does. Missing pet metadata stays unknown.
			if (domain == artifact_payload_domain::pet && !item.payload_owner.id &&
			    item.payload_owner.context_id)
				item.payload_owner = { item_owner_type::player,
						       item.payload_owner.context_id, 0 };
			item.source_quarantined = quarantined;
			item.parent_missing = missing;
			item.extra_flags_present = row[7] != nullptr;
			item.parent_owner_disagrees = disagreement;
			item.custody_examined = true;
			item.custody_found = row[11] != nullptr;
			item.custody_owner_revision_found = row[20] != nullptr;
			item.custody.owner.type = static_cast<item_owner_type>(owner_type);
			item.custody.state = static_cast<item_custody_state>(state);
			staged.next_row_id = item.row_id;
			staged.rows.push_back(item);
			++staged.source_rows;
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

namespace
{
unsigned int attach_blob_custody(MYSQL *connection, std::vector<artifact_payload_projection> *items)
{
	std::string uids;
	for (auto &item : *items)
	{
		item.custody_examined = true;
		item.custody_found = item.custody_owner_revision_found = false;
		item.custody = {};
		if (item.item_uid)
		{
			if (!uids.empty())
				uids += " UNION ";
			uids += "SELECT " + std::to_string(item.item_uid) + " AS item_uid";
		}
	}
	if (uids.empty())
		return 0;
	const std::string sql =
		"SELECT ids.item_uid,own.root_item_uid,own.parent_item_uid,own.owner_type,"
		"own.owner_id,own.owner_context_id,own.item_revision,own.vnum,own.state,rev.revision,"
		"EXISTS(SELECT 1 FROM item_ownership_quarantine q WHERE q.item_uid=ids.item_uid AND q.repaired_at IS NULL),own.item_uid "
		"FROM (" +
		uids +
		") ids LEFT JOIN item_current_owner own ON own.item_uid=ids.item_uid "
		"LEFT JOIN item_owner_revision rev ON "
		"rev.owner_type=own.owner_type AND rev.owner_id=own.owner_id AND "
		"rev.owner_context_id=own.owner_context_id";
	if (mysql_real_query(connection, sql.data(), sql.size()))
		return mysql_errno(connection);
	std::unique_ptr<MYSQL_RES, decltype(&mysql_free_result)> result(
		mysql_store_result(connection), mysql_free_result);
	if (!result)
		return mysql_errno(connection) ? mysql_errno(connection) : EIO;
	while (MYSQL_ROW row = mysql_fetch_row(result.get()))
	{
		item_ownership_runtime_entry custody = {};
		unsigned int owner_type = 0, state = 0, quarantined = 0;
		if (!number(row[0], &custody.item_uid) || !number(row[1], &custody.root_item_uid) ||
		    !number(row[2], &custody.parent_item_uid) || !number(row[3], &owner_type) ||
		    owner_type > UINT8_MAX || !number(row[4], &custody.owner.id) ||
		    !number(row[5], &custody.owner.context_id) ||
		    !number(row[6], &custody.item_revision) || !number(row[7], &custody.vnum) ||
		    !number(row[8], &state) || state > UINT8_MAX ||
		    !number(row[9], &custody.owner_revision) || !number(row[10], &quarantined))
			return EINVAL;
		custody.owner.type = static_cast<item_owner_type>(owner_type);
		custody.state = static_cast<item_custody_state>(state);
		for (auto &item : *items)
			if (item.item_uid == custody.item_uid)
			{
				item.custody_found = row[11] != nullptr;
				item.custody_owner_revision_found = row[9] != nullptr;
				item.custody = item.custody_found ? custody :
								    item_ownership_runtime_entry{};
				item.source_quarantined = item.source_quarantined || quarantined;
			}
	}
	return mysql_errno(connection);
}
} // namespace

unsigned int artifact_population_read_sql_blob_page(MYSQL *connection,
						    artifact_payload_domain domain,
						    uint64_t after_row_id,
						    artifact_population_sql_page *page)
{
	if (!connection || !page)
		return EINVAL;
	try
	{
		// Each query projects the same bounded raw shape. Indexed binding UIDs
		// override auction template UIDs, exactly as the actual claim path does.
		std::string fields, source, key = "i.id";
		size_t max_bytes = ITEM_TRANSFER_ITEM_BLOB_MAX_BYTES;
		switch (domain)
		{
		case artifact_payload_domain::auction:
			max_bytes = AUCTION_BLOB_MAX_BYTES;
			key = "((CAST(i.auction_id AS UNSIGNED)<<16)|i.slot)";
			fields =
				key +
				",i.auction_id,i.slot,i.item_uid,i.vnum,1,"
				"IF(i.claimed_at IS NULL,0,2),IF(i.claimed_at IS NULL,6,1),"
				"IF(i.claimed_at IS NULL,i.auction_id,COALESCE(i.claim_pid,0)),"
				"COALESCE(i.claim_operation_id,a.listing_operation_id),(a.id IS NULL OR a.custody_state<>1 OR "
				"a.quantity<>(SELECT COUNT(*) FROM auction_item_custody c WHERE c.auction_id=i.auction_id) OR "
				"EXISTS(SELECT 1 FROM auction_reconciliation_quarantine q WHERE q.auction_id=i.auction_id AND q.repaired_at IS NULL)),"
				"OCTET_LENGTH(i.obj_blob),LEFT(i.obj_blob,32769),NULL,0,0,"
				"i.claim_pid,i.claim_operation_id,i.claimed_at,a.listing_operation_id";
			source = "auction_item_custody i LEFT JOIN auctions a ON a.id=i.auction_id";
			break;
		case artifact_payload_domain::auction_legacy:
			max_bytes = AUCTION_BLOB_MAX_BYTES;
			fields =
				"i.id,i.id,0,0,i.obj_vnum,i.quantity,"
				"IF(i.status=1 AND NOT EXISTS(SELECT 1 FROM auction_item_custody c WHERE c.auction_id=i.id),0,2),"
				"6,i.id,i.listing_operation_id,(i.custody_state<>1 OR "
				"i.quantity<>(SELECT COUNT(*) FROM auction_item_custody c WHERE c.auction_id=i.id) OR "
				"EXISTS(SELECT 1 FROM auction_reconciliation_quarantine q WHERE q.auction_id=i.id AND q.repaired_at IS NULL) OR "
				"EXISTS(SELECT 1 FROM item_ownership_quarantine q WHERE q.item_uid=0 AND q.source_table='auctions' AND q.source_row_id=i.id AND q.repaired_at IS NULL)),"
				"OCTET_LENGTH(i.obj_blob_str),LEFT(i.obj_blob_str,32769),NULL,0,0,i.custody_state";
			source = "auctions i";
			break;
		case artifact_payload_domain::auction_pickup:
			max_bytes = AUCTION_BLOB_MAX_BYTES;
			fields = "i.id,i.pid,0,0,0,i.quantity,IF(i.retrieved=0,0,2),1,i.pid,"
				 "NULL,EXISTS(SELECT 1 FROM item_ownership_quarantine q WHERE "
				 "q.item_uid=0 AND q.source_table='auction_item_pickups' AND "
				 "q.source_row_id=i.id AND q.repaired_at IS NULL),"
				 "OCTET_LENGTH(i.obj_blob_str),LEFT(i.obj_blob_str,32769),NULL,0,0";
			source = "auction_item_pickups i";
			break;
		case artifact_payload_domain::collector:
			key = "i.listing_id";
			fields =
				"i.listing_id,i.beneficiary_pid,i.listing_id,i.item_uid,0,1,"
				"IF(i.status IN (2,3),0,2),10,i.listing_id,i.death_operation_id,"
				"EXISTS(SELECT 1 FROM collector_reconciliation_quarantine q WHERE q.listing_id=i.listing_id AND q.repaired_at IS NULL),"
				"OCTET_LENGTH(i.item_blob),LEFT(i.item_blob,131073),i.record_blob,i.beneficiary_pid,i.status,i.listing_revision,i.item_revision";
			source = "collector_listings i";
			break;
		case artifact_payload_domain::embedded:
			key = "i.item_uid";
			fields =
				"i.item_uid,0,i.item_uid,i.item_uid,i.vnum,1,2,0,0,NULL,0,"
				"OCTET_LENGTH(i.coin_payload),LEFT(i.coin_payload,131073),NULL,0,0";
			source = "item_current_owner i";
			break;
		default:
			return EINVAL;
		}
		std::string predicate = key + ">" + std::to_string(after_row_id), order = key;
		if (domain == artifact_payload_domain::auction)
		{
			const auto auction = std::to_string(after_row_id >> 16);
			predicate = "(i.auction_id>" + auction + " OR (i.auction_id=" + auction +
				    " AND i.slot>" + std::to_string(after_row_id & 65535) + "))";
			order = "i.auction_id,i.slot";
		}
		const std::string sql = "SELECT " + fields + " FROM " + source + " WHERE " +
					predicate +
					(domain == artifact_payload_domain::embedded ?
						 " AND OCTET_LENGTH(i.coin_payload)>0" :
						 "") +
					" ORDER BY " + order + " LIMIT " +
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
		size_t count = 0;
		while (MYSQL_ROW row = mysql_fetch_row(result.get()))
		{
			const auto *lengths = mysql_fetch_lengths(result.get());
			artifact_payload_projection item = {};
			item.domain = domain;
			uint64_t indexed_uid = 0, blob_size = 0, beneficiary = 0, status = 0;
			unsigned int role = 0, owner_type = 0, quarantined = 0;
			int32_t indexed_vnum = 0;
			if (!lengths || !number(row[0], &item.row_id) ||
			    item.row_id <= staged.next_row_id)
				return EINVAL;
			if (count++ == ARTIFACT_POPULATION_SQL_PAGE_SIZE)
				break;
			if (!number(row[1], &item.owner_reference) ||
			    !number(row[2], &item.owner_context) || !number(row[3], &indexed_uid) ||
			    !number(row[4], &indexed_vnum) || !number(row[5], &item.quantity) ||
			    !number(row[6], &role) || role > 2 || !number(row[7], &owner_type) ||
			    owner_type > UINT8_MAX || !number(row[8], &item.payload_owner.id) ||
			    !number(row[10], &quarantined) || !number(row[11], &blob_size) ||
			    blob_size > max_bytes || lengths[12] != blob_size ||
			    !number(row[14], &beneficiary) || !number(row[15], &status))
				return EINVAL;
			const auto valid_operation = [&](size_t column)
			{
				critical_operation_id operation;
				if (!row[column] || lengths[column] != operation.bytes.size())
					return false;
				memcpy(operation.bytes.data(), row[column], operation.bytes.size());
				return !critical_operation_id_is_zero(operation);
			};
			if (domain == artifact_payload_domain::auction_legacy)
			{
				unsigned int custody_state = 0;
				if (!number(row[16], &custody_state) ||
				    (custody_state == 1 && (!item.quantity || !valid_operation(9))))
					return EINVAL;
			}

			if (domain == artifact_payload_domain::auction)
			{
				uint64_t claimant = 0;
				// Reservation sets the PID first; completion writes operation/time together.
				if ((!quarantined && !row[19]) ||
				    (row[19] && !valid_operation(19)) ||
				    (row[18] != nullptr) != (row[17] != nullptr) ||
				    (row[18] && !row[16]) ||
				    (row[16] && (!number(row[16], &claimant) || !claimant)) ||
				    (row[17] && lengths[17] != item.source_operation.bytes.size()))
					return EINVAL;
			}

			staged.next_row_id = item.row_id;
			++staged.source_rows;
			item.role = static_cast<artifact_payload_role>(role);
			item.payload_owner.type = static_cast<item_owner_type>(owner_type);
			item.source_quarantined = quarantined;
			if (row[9])
			{
				if (!valid_operation(9))
					return EINVAL;
				memcpy(item.source_operation.bytes.data(), row[9], lengths[9]);
			}
			if (domain == artifact_payload_domain::collector)
			{
				collector::record record;
				critical_operation_id operation;
				uint64_t listing_revision = 0, item_revision = 0;
				if (!row[13] ||
				    collector::record_decode(
					    reinterpret_cast<const uint8_t *>(row[13]), lengths[13],
					    &record) != collector::codec_result::ok ||
				    !critical_operation_id_from_hex(record.death_operation.data(),
								    &operation) ||
				    record.listing != item.row_id || record.uid != indexed_uid ||
				    record.beneficiary != beneficiary ||
				    !number(row[16], &listing_revision) ||
				    !number(row[17], &item_revision) ||
				    record.revision != listing_revision ||
				    record.item_revision != item_revision ||
				    static_cast<unsigned>(record.status) != status ||
				    !critical_operation_id_equal(operation,
								 item.source_operation) ||
				    (!blob_size && item.role == artifact_payload_role::stored))
					return EINVAL;
				// Candidate/terminal metadata without bytes is not a payload.
				if (!blob_size)
					continue;
			}
			if (!row[12] || !blob_size)
				return EINVAL;
			if (domain == artifact_payload_domain::auction ||
			    domain == artifact_payload_domain::auction_legacy ||
			    domain == artifact_payload_domain::auction_pickup)
			{
				legacy_object_identity identity;
				if (!legacy_object_identity_read(
					    reinterpret_cast<const uint8_t *>(row[12]), lengths[12],
					    &identity) ||
				    (indexed_vnum && indexed_vnum != identity.vnum) ||
				    (domain == artifact_payload_domain::auction && !indexed_uid))
					return EINVAL;
				item.item_uid = domain == artifact_payload_domain::auction ?
							indexed_uid :
							identity.item_uid;
				item.vnum = identity.vnum;
				item.extra_flags = identity.extra_flags;
				item.extra_flags_present = identity.extra_flags_present;
			}
			else
			{
				std::vector<player_item_snapshot> decoded;
				const auto parsed = player_item_snapshot_list_decode(
					reinterpret_cast<const uint8_t *>(row[12]), lengths[12],
					&decoded);
				if (parsed != player_snapshot_codec_result::ok)
					return parsed == player_snapshot_codec_result::
								       allocation_failure ?
						       ENOMEM :
						       EINVAL;
				if (decoded.size() != 1 || decoded[0].object_uid != indexed_uid ||
				    (indexed_vnum && decoded[0].vnum != indexed_vnum))
					return EINVAL;
				if (domain == artifact_payload_domain::collector &&
				    decoded[0].equipment_slot != 0)
					return EINVAL;
				if (domain == artifact_payload_domain::embedded &&
				    (decoded[0].type != ITEM_MONEY ||
				     std::any_of(decoded[0].values.begin(),
						 decoded[0].values.begin() + 4,
						 [](int32_t value) { return value < 0; })))
					return EINVAL;
				item.item_uid = decoded[0].object_uid;
				item.vnum = decoded[0].vnum;
				item.extra_flags = decoded[0].extra_flags;
				item.extra_flags_present = true;
			}
			staged.rows.push_back(item);
		}
		if (mysql_errno(connection))
			return mysql_errno(connection);
		// Release the buffered source before the bounded custody lookup.
		result.reset();
		if (const auto failed = attach_blob_custody(connection, &staged.rows))
			return failed;
		*page = std::move(staged);
		return 0;
	}
	catch (const std::bad_alloc &)
	{
		return ENOMEM;
	}
}

unsigned int
artifact_population_read_sql_payloads(MYSQL *connection,
				      std::vector<artifact_payload_projection> *items,
				      const std::vector<artifact_payload_projection> *additional)
{
	if (!connection || !items)
		return EINVAL;
	if (additional && additional->size() > ARTIFACT_IDENTITY_MAX_RECORDS)
		return E2BIG;
	if ((connection->server_status & SERVER_STATUS_IN_TRANS) ||
	    !(connection->server_status & SERVER_STATUS_AUTOCOMMIT))
		return EBUSY;
	const char isolation[] = "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ";
	const char begin[] = "START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY";
	if (mysql_real_query(connection, isolation, sizeof(isolation) - 1) ||
	    mysql_real_query(connection, begin, sizeof(begin) - 1))
		return mysql_errno(connection);
	unsigned int failed = 0;
	size_t source_rows = 0;
	std::vector<artifact_payload_projection> staged;
	try
	{
		if (additional)
		{
			staged = *additional;
			source_rows = staged.size();
			for (size_t first = 0; first < staged.size();
			     first += ARTIFACT_POPULATION_SQL_PAGE_SIZE)
			{
				const size_t last = std::min(
					staged.size(), first + ARTIFACT_POPULATION_SQL_PAGE_SIZE);
				std::vector<artifact_payload_projection> batch(
					staged.begin() + first, staged.begin() + last);
				if ((failed = attach_blob_custody(connection, &batch)))
					break;
				std::copy(batch.begin(), batch.end(), staged.begin() + first);
			}
		}
		const artifact_payload_domain sources[] = {
			artifact_payload_domain::player,
			artifact_payload_domain::pet,
			artifact_payload_domain::locker,
			artifact_payload_domain::account_locker,
			artifact_payload_domain::corpse,
			artifact_payload_domain::room,
			artifact_payload_domain::shopkeeper,
			artifact_payload_domain::siege,
			artifact_payload_domain::auction,
			artifact_payload_domain::auction_legacy,
			artifact_payload_domain::auction_pickup,
			artifact_payload_domain::collector,
			artifact_payload_domain::embedded,
		};
		for (const auto domain : sources)
		{
			if (failed)
				break;
			uint64_t cursor = 0;
			do
			{
				artifact_population_sql_page page;
				failed = domain <= artifact_payload_domain::siege ?
						 artifact_population_read_sql_page(
							 connection, domain, cursor, &page) :
						 artifact_population_read_sql_blob_page(
							 connection, domain, cursor, &page);
				if (failed)
					break;
				if (page.source_rows > ARTIFACT_IDENTITY_MAX_RECORDS - source_rows)
				{
					failed = E2BIG;
					break;
				}
				source_rows += page.source_rows;
				staged.insert(staged.end(), page.rows.begin(), page.rows.end());
				if (page.complete)
					break;
				if (page.next_row_id <= cursor)
				{
					failed = EINVAL;
					break;
				}
				cursor = page.next_row_id;
			} while (true);
			if (failed)
				break;
		}
	}
	catch (const std::bad_alloc &)
	{
		failed = ENOMEM;
	}
	if (failed)
	{
		mysql_rollback(connection);
		return failed;
	}
	if (mysql_commit(connection))
	{
		failed = mysql_errno(connection);
		mysql_rollback(connection);
		return failed ? failed : EIO;
	}
	*items = std::move(staged);
	return 0;
}
#endif
