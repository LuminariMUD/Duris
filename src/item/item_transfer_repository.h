#ifndef ITEM_TRANSFER_REPOSITORY_H
#define ITEM_TRANSFER_REPOSITORY_H

#include "item/item_transfer_command.h"

#include <mysql/mysql.h>

bool item_transfer_repository_execute(MYSQL *connection, const critical_command &command,
				      item_transfer_result *result, unsigned int *result_code,
				      bool *mutation_applied);
// Compound commands may use one inbox operation for consecutive transfer
// segments. The offset keeps their item-ledger event indexes disjoint.
bool item_transfer_repository_execute_at_offset(MYSQL *connection, const critical_command &command,
						uint16_t event_index_base,
						item_transfer_result *result,
						unsigned int *result_code, bool *mutation_applied);
bool item_transfer_repository_destroy_owners(MYSQL *connection, const item_owner_identity *owners,
					     size_t owner_count);
// Retire selected container/item roots while preserving their contents with the
// current owner.  The caller owns the enclosing SQL transaction and its physical
// projection changes; this function advances authoritative custody and ledger rows.
bool item_transfer_repository_revoke_roots_preserving_children(MYSQL *connection,
							       const uint64_t *item_uids,
							       size_t item_count);

#endif
