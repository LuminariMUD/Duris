/****************************************************************************
 *
 *  File: item_claim_repository.h                               Part of Duris
 *  Usage: SQL item claim repository interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

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
 *   - a destroyed row: leave the item and its contents out of the save and report
 *     it in outcome->dupes.
 * Returns 0, or the MySQL error code of the statement that failed.
 */
unsigned int claim_items(MYSQL *connection, const item_owner_identity &owner,
			 const std::vector<player_item_snapshot> &items,
			 item_claim_outcome *outcome);

// Make item_current_owner name `holder` for one item a transfer takes from memory:
// a missing row is inserted, another owner's row is taken with an item_owner_audit
// row, and a stale placement is corrected. `parent_uid` null keeps the recorded
// parent. A destroyed row is never revived: *refused is set instead. *revision is the item's revision afterwards.
// Returns 0, or the MySQL error code of the statement that failed.
unsigned int claim_transfer_item(MYSQL *connection, const item_owner_identity &holder,
				 uint64_t item_uid, uint64_t root_uid, const uint64_t *parent_uid,
				 int32_t vnum, uint64_t *revision, bool *refused);

// Delete every active row naming a player as the holder of an item that is in no
// payload row at all (player_items, player_pet_items, locker_items, corpse_items,
// saved_items, whoever's). For boot, when no character is in memory: such a row is an
// item the player no longer holds (dropped and then extracted, eaten, decayed), which
// no save ever releases. A row whose item an older copy elsewhere still carries stays:
// it makes that copy load as a stale one (a crash after a hand-over leaves the giver's
// copy). A row an auction's custody row, an artifact_domain_state row or another row
// (its contents) still references is kept for the foreign keys; the pass repeats until
// it deletes nothing, so a container goes after its contents. *deleted counts the rows.
// Returns 0, or the MySQL error code of the statement that failed.
unsigned int reap_unheld_player_items(MYSQL *connection, uint64_t *deleted);

#endif
