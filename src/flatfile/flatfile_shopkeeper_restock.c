#include "flatfile/flatfile_shopkeeper_restore.h"
#include "flatfile/flatfile_shopkeeper_materialize.h"
#include "flatfile/flatfile_shopkeeper_ownership.h"
#include "economy/shopkeeper_restock.h"
#include "player/player_snapshot_capture.h"
#include "core/prototypes.h"
#include "core/utils.h"
#include "world/world_singletons.h"

extern P_index mob_index;
extern struct shop_data *shop_index;

bool flatfile_shopkeeper_restock(const std::string &root,
				 std::vector<flatfile_shopkeeper_record> *records,
				 const std::vector<flatfile_materialized_shopkeeper> &staged,
				 std::string *error)
{
	struct refill
	{
		size_t index;
		std::vector<P_obj> stock;
	};
	std::vector<refill> refills;
	std::vector<flatfile_shopkeeper_record> updates;
	std::vector<uint64_t> new_uids;
	for (size_t index = 0; index < records->size(); ++index)
	{
		const auto &record = (*records)[index];
		P_char fresh = nullptr;
		int matches = 0;
		for (P_char keeper : live_shopkeepers(static_cast<int>(record.shop_id)))
			if (keeper != staged[index].character &&
			    mob_index[GET_RNUM(keeper)].virtual_number == record.mob_vnum &&
			    (shop_index[record.shop_id].shop_is_roaming ||
			     keeper->in_room == staged[index].room_rnum))
			{
				fresh = keeper;
				++matches;
			}
		if (matches != 1)
			continue;
		auto stock = shopkeeper_reboot_stock(
			fresh->carrying, staged[index].character->carrying, record.shop_id);
		if (stock.empty())
			continue;
		if (record.revision == UINT64_MAX)
			return false;
		auto updated = record;
		++updated.revision;
		updated.saved_at = time(nullptr);
		for (P_obj item : stock)
		{
			std::vector<player_item_snapshot> tree;
			if (player_item_snapshot_tree_capture(item, &tree, nullptr) !=
			    player_snapshot_capture_result::ok)
				return false;
			const auto offset = updated.items.size();
			for (auto &child : tree)
			{
				if (child.parent_index != PLAYER_SNAPSHOT_NO_PARENT)
					child.parent_index += static_cast<int32_t>(offset);
				new_uids.push_back(child.object_uid);
				updated.items.push_back(std::move(child));
			}
		}
		updates.push_back(std::move(updated));
		refills.push_back({ index, std::move(stock) });
	}
	if (updates.empty())
		return true;
	{
		flatfile_authority_lock lock;
		if (!lock.acquire(root, error))
			return false;
		flatfile_authority_after_image catalog;
		if (flatfile_shopkeeper_prepare_restock(root, lock, updates, &catalog, error) !=
		    flatfile_shopkeeper_result::ok)
			return false;
		std::vector<flatfile_item_ownership_record> existing;
		if (flatfile_item_repository_load_uids_locked(root, lock, new_uids, &existing,
							      error) !=
			    flatfile_item_repository_result::ok ||
		    !existing.empty())
			return false;
		std::vector<flatfile_item_claim> claims;
		for (size_t index = 0; index < updates.size(); ++index)
		{
			const auto source = refills[index].index;
			const auto &record = (*records)[source];
			const auto owner = flatfile_shopkeeper_item_owner(record.shop_id);
			uint64_t revision = 0;
			std::vector<flatfile_item_ownership_record> held;
			std::vector<player_load_item_identity> identities;
			if (flatfile_item_repository_load_owner_locked(root, lock, owner, &revision,
								       &held, error) !=
				    flatfile_item_repository_result::ok ||
			    revision != staged[source].owner_revision ||
			    flatfile_shopkeeper_reconcile_item_ownership(record, revision, held,
									 &identities) !=
				    flatfile_shopkeeper_ownership_result::ok)
				return false;
			claims.push_back({ owner, &updates[index].items, {} });
		}
		flatfile_authority_operation custody;
		std::vector<flatfile_item_claim_audit> audits;
		if (flatfile_item_repository_prepare_claim(root, lock, &claims, &custody, &audits,
							   error) !=
		    flatfile_item_repository_result::ok)
			return false;
		for (const auto &claim : claims)
			if (!claim.outcome.left_out.empty())
				return false;
		flatfile_authority_operation shops;
		shops.filename = std::move(catalog.filename);
		shops.bytes = std::move(catalog.bytes);
		if (flatfile_authority_transaction_commit_operations(root, lock, { custody, shops },
								     error) !=
		    flatfile_authority_transaction_result::ok)
			return false;
	}
	for (size_t index = 0; index < updates.size(); ++index)
	{
		const auto source = refills[index].index;
		(*records)[source] = std::move(updates[index]);
		for (P_obj item : refills[index].stock)
		{
			obj_from_char(item);
			obj_to_char(item, staged[source].character);
		}
		if (!flatfile_shopkeeper_publish_ownership(root, (*records)[source], error))
			return false;
	}
	return true;
}
