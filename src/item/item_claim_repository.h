#ifndef ITEM_CLAIM_REPOSITORY_H
#define ITEM_CLAIM_REPOSITORY_H

#include "item/item_claim.h"

#include <mysql/mysql.h>

/*
 * Make item_current_owner name `owner` for every item the owner holds in memory.
 * `items` lists parents before their contents, as a snapshot does. Runs inside the
 * caller's transaction:
 *   - no row: insert one;
 *   - a row naming this owner: correct its placement if it moved;
 *   - a row naming anyone else: take it, and write an item_owner_audit row;
 *   - a row naming an auction, shopkeeper or the collector: leave the item and its
 *     contents out of the save and report it in outcome->dupes.
 * Returns 0, or the MySQL error code of the statement that failed.
 */
unsigned int claim_items(MYSQL *connection, const item_owner_identity &owner,
			 const std::vector<player_item_snapshot> &items,
			 item_claim_outcome *outcome);

#endif
