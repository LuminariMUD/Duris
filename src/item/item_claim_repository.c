/****************************************************************************
 *
 *  File: item_claim_repository.c                               Part of Duris
 *  Usage: SQL item ownership claims and the reaping of unheld items
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#include "item/item_claim_repository.h"

#include "persistence/persistence_observability.h"

#include <algorithm>
#include <cerrno>
#include <cstdlib>
#include <set>
#include <sstream>
#include <string>
#include <unordered_map>

namespace
{
// Rows read per SELECT ... IN (...).
constexpr size_t CLAIM_LOOKUP_BATCH = 500;

struct current_row
{
	item_owner_identity owner;
	uint64_t root_item_uid;
	uint64_t parent_item_uid;
	int32_t vnum;
	unsigned int state;
};

unsigned int execute(MYSQL *connection, const std::string &sql)
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
	return rc ? (error_code ? error_code : EIO) : 0;
}

bool parse_u64(const char *text, uint64_t *value)
{
	if (!text || !*text)
		return false;
	char *end = nullptr;
	errno = 0;
	const unsigned long long parsed = std::strtoull(text, &end, 10);
	if (errno || !end || *end)
		return false;
	*value = static_cast<uint64_t>(parsed);
	return true;
}

std::string owner_values(const item_owner_identity &owner)
{
	return std::to_string(static_cast<unsigned>(owner.type)) + ',' + std::to_string(owner.id) +
	       ',' + std::to_string(owner.context_id);
}

bool same_owner(const item_owner_identity &left, const item_owner_identity &right)
{
	return left.type == right.type && left.id == right.id &&
	       left.context_id == right.context_id;
}

unsigned int load_current_rows(MYSQL *connection, const std::vector<player_item_snapshot> &items,
			       std::unordered_map<uint64_t, current_row> *rows)
{
	for (size_t start = 0; start < items.size(); start += CLAIM_LOOKUP_BATCH)
	{
		std::ostringstream sql;
		sql << "SELECT item_uid,owner_type,owner_id,owner_context_id,root_item_uid,"
		       "COALESCE(parent_item_uid,0),vnum,state FROM item_current_owner WHERE "
		       "item_uid IN (";
		bool any = false;
		for (size_t index = start;
		     index < items.size() && index < start + CLAIM_LOOKUP_BATCH; ++index)
			if (items[index].object_uid)
			{
				sql << (any ? "," : "") << items[index].object_uid;
				any = true;
			}
		if (!any)
			continue;
		sql << ") FOR UPDATE";
		if (const unsigned int failed = execute(connection, sql.str()))
			return failed;
		MYSQL_RES *result = mysql_store_result(connection);
		if (!result)
			return mysql_errno(connection) ? mysql_errno(connection) : EIO;
		while (MYSQL_ROW row = mysql_fetch_row(result))
		{
			uint64_t uid = 0, type = 0, id = 0, context = 0, root = 0, parent = 0,
				 vnum = 0, state = 0;
			if (!parse_u64(row[0], &uid) || !parse_u64(row[1], &type) ||
			    !parse_u64(row[2], &id) || !parse_u64(row[3], &context) ||
			    !parse_u64(row[4], &root) || !parse_u64(row[5], &parent) || !row[6] ||
			    !parse_u64(row[7], &state))
			{
				mysql_free_result(result);
				return EILSEQ;
			}
			vnum = static_cast<uint64_t>(std::strtoll(row[6], nullptr, 10));
			(*rows)[uid] = { { static_cast<item_owner_type>(type), id, context },
					 root,
					 parent,
					 static_cast<int32_t>(vnum),
					 static_cast<unsigned int>(state) };
		}
		mysql_free_result(result);
	}
	return 0;
}
} // namespace

unsigned int claim_items(MYSQL *connection, const item_owner_identity &owner,
			 const std::vector<player_item_snapshot> &items,
			 item_claim_outcome *outcome, bool rent_keys)
{
	if (!connection || !outcome || (rent_keys && owner.type != item_owner_type::player))
		return EINVAL;
	*outcome = {};
	if (items.empty())
		return 0;
	std::unordered_map<uint64_t, current_row> rows;
	if (const unsigned int failed = load_current_rows(connection, items, &rows))
		return failed;

	const item_owner_identity destruction = { item_owner_type::destruction, 0, 0 };
	std::vector<uint64_t> roots(items.size(), 0);
	std::ostringstream audit;
	size_t audits = 0;
	bool changed = false;
	bool disposed = false;
	std::set<std::string> losers;
	for (size_t index = 0; index < items.size(); ++index)
	{
		const player_item_snapshot &item = items[index];
		const bool rent_key = rent_keys &&
				      item_claim_is_norent_key(item.type, item.extra_flags);
		if (rent_key && !item.object_uid)
			return EINVAL;
		const bool nested = item.parent_index >= 0 &&
				    static_cast<size_t>(item.parent_index) < index;
		const player_item_snapshot *parent = nested ? &items[item.parent_index] : nullptr;
		const uint64_t parent_uid = parent ? parent->object_uid : 0;
		roots[index] = parent && roots[item.parent_index] ? roots[item.parent_index] :
								    item.object_uid;
		if (!item.object_uid)
			continue;
		const auto found = rows.find(item.object_uid);
		if (parent_uid && outcome->left_out.count(parent_uid))
		{
			// Its container is left out, so it is too.
			outcome->left_out.insert(item.object_uid);
			const auto holder = rows.find(parent_uid);
			outcome->dupes.push_back({ item.object_uid, item.vnum,
						   found != rows.end()	? found->second.owner :
						   holder != rows.end() ? holder->second.owner :
									  owner });
			continue;
		}
		if (found != rows.end() &&
		    item_claim_leaves_out(static_cast<item_custody_state>(found->second.state)))
		{
			outcome->left_out.insert(item.object_uid);
			if (!rent_key)
				outcome->dupes.push_back(
					{ item.object_uid, item.vnum, found->second.owner });
			continue;
		}
		const item_owner_identity &target = rent_key ? destruction : owner;
		const auto state = rent_key ? item_custody_state::destroyed :
					      item_custody_state::active;
		const std::string state_sql = std::to_string(static_cast<unsigned>(state));
		const uint64_t target_root = rent_key ? item.object_uid : roots[index];
		const uint64_t target_parent = rent_key ? 0 : parent_uid;
		const std::string parent_sql = target_parent ? std::to_string(target_parent) :
							       "NULL";
		if (rent_key)
			outcome->left_out.insert(item.object_uid);
		if (found == rows.end())
		{
			if (const unsigned int failed = execute(
				    connection,
				    "INSERT INTO item_current_owner (item_uid,root_item_uid,"
				    "parent_item_uid,owner_type,owner_id,owner_context_id,"
				    "item_revision,vnum,state) VALUES (" +
					    std::to_string(item.object_uid) + ',' +
					    std::to_string(target_root) + ',' + parent_sql + ',' +
					    owner_values(target) + ",1," +
					    std::to_string(item.vnum) + ',' + state_sql + ')'))
				return failed;
			if (rent_key)
			{
				disposed = true;
				audit << (audits++ ? "," : "") << '(' << item.object_uid << ','
				      << item.vnum << ',' << owner_values(owner) << ','
				      << owner_values(target) << ')';
			}
			++outcome->inserted;
			changed = true;
			continue;
		}
		const current_row &current = found->second;
		const bool owned = same_owner(current.owner, target);
		if (owned && current.root_item_uid == target_root &&
		    current.parent_item_uid == target_parent && current.vnum == item.vnum &&
		    current.state == static_cast<unsigned>(state))
			continue;
		if (const unsigned int failed = execute(
			    connection,
			    "UPDATE item_current_owner SET owner_type=" +
				    std::to_string(static_cast<unsigned>(target.type)) +
				    ",owner_id=" + std::to_string(target.id) +
				    ",owner_context_id=" + std::to_string(target.context_id) +
				    ",root_item_uid=" + std::to_string(target_root) +
				    ",parent_item_uid=" + parent_sql +
				    ",vnum=" + std::to_string(item.vnum) + ",state=" + state_sql +
				    ",item_revision=item_revision+1 WHERE item_uid=" +
				    std::to_string(item.object_uid)))
			return failed;
		changed = true;
		disposed = disposed || rent_key;
		if (owned)
			continue;
		if (!same_owner(current.owner, owner))
			losers.insert(owner_values(current.owner));
		++outcome->claimed;
		audit << (audits++ ? "," : "") << '(' << item.object_uid << ',' << item.vnum << ','
		      << owner_values(current.owner) << ',' << owner_values(target) << ')';
	}
	if (audits)
		if (const unsigned int failed =
			    execute(connection,
				    "INSERT INTO item_owner_audit (item_uid,vnum,old_owner_type,"
				    "old_owner_id,old_owner_context_id,new_owner_type,"
				    "new_owner_id,new_owner_context_id) VALUES " +
					    audit.str()))
			return failed;
	// The holdings of the claimer and of every owner that lost an item changed.
	if (changed)
		if (const unsigned int failed = execute(
			    connection, "INSERT INTO item_owner_revision (owner_type,owner_id,"
					"owner_context_id,revision) VALUES (" +
						owner_values(owner) +
						",1) ON DUPLICATE KEY UPDATE revision=revision+1"))
			return failed;
	for (const std::string &loser : losers)
		if (const unsigned int failed = execute(
			    connection, "UPDATE item_owner_revision SET revision=revision+1 WHERE "
					"(owner_type,owner_id,owner_context_id)=(" +
						loser + ")"))
			return failed;
	if (disposed)
		if (const unsigned int failed = execute(
			    connection,
			    "INSERT INTO item_owner_revision (owner_type,owner_id,owner_context_id,revision) VALUES (" +
				    owner_values(destruction) +
				    ",1) ON DUPLICATE KEY UPDATE revision=revision+1"))
			return failed;
	return 0;
}

unsigned int reap_unheld_player_items(MYSQL *connection, uint64_t *deleted,
				      const std::vector<uint64_t> *retained)
{
	if (!connection || !deleted)
		return EINVAL;
	*deleted = 0;
	// The self-join, not a subquery on the same table: MySQL refuses the latter in a
	// DELETE.
	std::string sql =
		"DELETE own FROM item_current_owner own "
		"LEFT JOIN item_current_owner child ON child.parent_item_uid=own.item_uid "
		"LEFT JOIN auction_item_custody auction ON auction.item_uid=own.item_uid "
		"LEFT JOIN artifact_domain_state artifact ON artifact.canonical_item_uid=own.item_uid "
		"WHERE own.owner_type=" +
		std::to_string(static_cast<unsigned>(item_owner_type::player)) +
		" AND own.owner_context_id=0 AND own.state=" +
		std::to_string(static_cast<unsigned>(item_custody_state::active)) +
		" AND child.item_uid IS NULL AND auction.item_uid IS NULL AND artifact.vnum IS NULL";
	// Any owner's payload: a load skips a copy whose row names someone else, so while
	// an older copy is stored anywhere, the row is what keeps it out.
	for (const char *payload :
	     { "player_items", "player_pet_items", "locker_items", "corpse_items", "saved_items" })
		sql += std::string(" AND NOT EXISTS (SELECT 1 FROM ") + payload +
		       " payload WHERE payload.obj_uid=own.item_uid)";
	if (retained && !retained->empty())
	{
		if (!std::is_sorted(retained->begin(), retained->end()))
			return EINVAL;
		std::string select = sql;
		select.replace(0, sizeof("DELETE own") - 1, "SELECT own.item_uid");
		for (;;)
		{
			const uint64_t before = *deleted;
			uint64_t cursor = 0;
			for (;;)
			{
				if (const auto failed = execute(
					    connection, select + " AND own.item_uid>" +
								std::to_string(cursor) +
								" ORDER BY own.item_uid LIMIT 256"))
					return failed;
				MYSQL_RES *page = mysql_store_result(connection);
				if (!page)
					return mysql_errno(connection) ? mysql_errno(connection) :
									 EIO;
				std::string eligible;
				bool valid = true, found = false;
				while (MYSQL_ROW row = mysql_fetch_row(page))
				{
					uint64_t uid = 0;
					if (!parse_u64(row[0], &uid) || uid <= cursor)
					{
						valid = false;
						break;
					}
					cursor = uid;
					found = true;
					if (!std::binary_search(retained->begin(), retained->end(),
								uid))
					{
						if (!eligible.empty())
							eligible += ',';
						eligible += std::to_string(uid);
					}
				}
				const auto error = mysql_errno(connection);
				mysql_free_result(page);
				if (!valid || error)
					return error ? error : EINVAL;
				if (!found)
					break;
				if (!eligible.empty())
				{
					// Recheck every original stale-row condition at deletion.
					if (const auto failed = execute(
						    connection, sql + " AND own.item_uid IN (" +
									eligible + ')'))
						return failed;
					*deleted += mysql_affected_rows(connection);
				}
			}
			if (*deleted == before)
				return 0;
		}
	}
	for (;;)
	{
		if (const unsigned int failed = execute(connection, sql))
			return failed;
		const my_ulonglong affected = mysql_affected_rows(connection);
		if (!affected)
			return 0;
		*deleted += affected;
	}
}

unsigned int claim_transfer_item(MYSQL *connection, const item_owner_identity &holder,
				 uint64_t item_uid, uint64_t root_uid, const uint64_t *parent_uid,
				 int32_t vnum, uint64_t *revision, bool *refused)
{
	if (!connection || !item_uid || !revision || !refused)
		return EINVAL;
	*revision = 0;
	*refused = false;
	const std::string uid = std::to_string(item_uid);
	if (const unsigned int failed =
		    execute(connection, "SELECT owner_type,owner_id,owner_context_id,root_item_uid,"
					"COALESCE(parent_item_uid,0),item_revision,vnum,state FROM "
					"item_current_owner WHERE item_uid=" +
						uid + " FOR UPDATE"))
		return failed;
	MYSQL_RES *result = mysql_store_result(connection);
	if (!result)
		return mysql_errno(connection) ? mysql_errno(connection) : EIO;
	MYSQL_ROW row = mysql_fetch_row(result);
	uint64_t type = 0, id = 0, context = 0, root = 0, parent = 0, stored_revision = 0,
		 state = 0;
	int32_t stored_vnum = 0;
	const bool found = row != nullptr;
	const bool parsed = !found ||
			    (parse_u64(row[0], &type) && parse_u64(row[1], &id) &&
			     parse_u64(row[2], &context) && parse_u64(row[3], &root) &&
			     parse_u64(row[4], &parent) && parse_u64(row[5], &stored_revision) &&
			     row[6] && parse_u64(row[7], &state));
	if (found && row[6])
		stored_vnum = static_cast<int32_t>(std::strtol(row[6], nullptr, 10));
	mysql_free_result(result);
	if (!parsed)
		return EILSEQ;
	const uint64_t wanted_parent = parent_uid ? *parent_uid : parent;
	const std::string parent_sql = wanted_parent ? std::to_string(wanted_parent) : "NULL";
	const int32_t wanted_vnum = vnum ? vnum : stored_vnum;
	const std::string active =
		std::to_string(static_cast<unsigned>(item_custody_state::active));
	if (!found)
	{
		*revision = 1;
		return execute(connection,
			       "INSERT INTO item_current_owner (item_uid,root_item_uid,"
			       "parent_item_uid,owner_type,owner_id,owner_context_id,item_revision,"
			       "vnum,state) VALUES (" +
				       uid + ',' + std::to_string(root_uid) + ',' + parent_sql +
				       ',' + owner_values(holder) + ",1," +
				       std::to_string(wanted_vnum) + ',' + active + ')');
	}
	const item_owner_identity current = { static_cast<item_owner_type>(type), id, context };
	if (item_claim_leaves_out(static_cast<item_custody_state>(state)))
	{
		*refused = true;
		return 0;
	}
	const bool owned = same_owner(current, holder);
	*revision = stored_revision;
	if (owned && root == root_uid && parent == wanted_parent && stored_vnum == wanted_vnum &&
	    state == static_cast<uint64_t>(item_custody_state::active))
		return 0;
	if (stored_revision == UINT64_MAX)
		return ERANGE;
	if (const unsigned int failed =
		    execute(connection,
			    "UPDATE item_current_owner SET owner_type=" +
				    std::to_string(static_cast<unsigned>(holder.type)) +
				    ",owner_id=" + std::to_string(holder.id) +
				    ",owner_context_id=" + std::to_string(holder.context_id) +
				    ",root_item_uid=" + std::to_string(root_uid) +
				    ",parent_item_uid=" + parent_sql +
				    ",vnum=" + std::to_string(wanted_vnum) + ",state=" + active +
				    ",item_revision=item_revision+1 WHERE item_uid=" + uid))
		return failed;
	*revision = stored_revision + 1;
	if (owned)
		return 0;
	return execute(connection, "INSERT INTO item_owner_audit (item_uid,vnum,old_owner_type,"
				   "old_owner_id,old_owner_context_id,new_owner_type,new_owner_id,"
				   "new_owner_context_id) VALUES (" +
					   uid + ',' + std::to_string(wanted_vnum) + ',' +
					   owner_values(current) + ',' + owner_values(holder) +
					   ')');
}
