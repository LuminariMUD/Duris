#ifndef DUPE_LOG_H
#define DUPE_LOG_H

#include "item/item_transfer_command.h"

#include <cstdint>

// logs/log/dupes: one line per item a save left out or a load skipped, naming the
// owner that lost it and the owner that has it. Safe to call from any thread.
constexpr const char *DUPE_LOG_PATH = "logs/log/dupes";

const char *item_owner_type_label(item_owner_type type);
void dupe_log_item(const char *event, uint64_t item_uid, int32_t vnum,
		   const item_owner_identity &lost_by, const item_owner_identity &held_by);
// logs/log/item_claims: the flat-file backend's record of a save taking an item from
// another owner (MariaDB writes item_owner_audit rows instead).
constexpr const char *ITEM_CLAIM_LOG_PATH = "logs/log/item_claims";
void item_claim_log_item(uint64_t item_uid, int32_t vnum, const item_owner_identity &old_owner,
			 const item_owner_identity &new_owner);
// Redirect the log for a test; null restores DUPE_LOG_PATH.
void dupe_log_set_path_for_tests(const char *path);

#endif
