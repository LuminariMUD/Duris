/****************************************************************************
 *
 *  File: item_movement_transaction.h                           Part of Duris
 *  Usage: item movement transaction interface and health
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef ITEM_MOVEMENT_TRANSACTION_H
#define ITEM_MOVEMENT_TRANSACTION_H

#include "persistence/critical_command_coordinator.h"
#include "item/item_transfer_command.h"
#include "core/structs.h"

#include <cstddef>
#include <cstdint>
#include <functional>

enum class item_creation_prepare_result
{
	more,
	ready,
	failed
};
// Each invocation creates at most one detached root. Captures must own their
// data and must not retain a character pointer across pulses.
using item_creation_prepare_fn = std::function<item_creation_prepare_result(P_char, P_obj *)>;
using item_creation_grant_completion_fn = void (*)(P_char actor, uint64_t item_uid, bool committed,
						   unsigned int error_code);
bool item_creation_grant_defer(P_char actor, item_creation_prepare_fn prepare);
void item_creation_grant_prepare_pulse(void);

constexpr size_t ITEM_MOVEMENT_PENDING_MAX = 1024;
constexpr size_t ITEM_MOVEMENT_CONTEXT_MAX_BYTES = 128;
// A starter kit's roots are held in the same bounded queue as every other grant, so
// admission must never promise more roots than one transfer can carry.
constexpr size_t ITEM_CREATION_GRANT_MAX_ROOTS =
	ITEM_MOVEMENT_PENDING_MAX < ITEM_TRANSFER_MAX_ITEMS ? ITEM_MOVEMENT_PENDING_MAX :
							      ITEM_TRANSFER_MAX_ITEMS;
static_assert(ITEM_CREATION_GRANT_MAX_ROOTS <= ITEM_TRANSFER_MAX_ITEMS);

using item_movement_completion_fn = void (*)(P_char actor, bool committed,
					     const item_transfer_result &result,
					     unsigned int error_code, const uint8_t *context,
					     size_t context_size);
struct item_movement_health
{
	uint64_t pending;
	uint64_t retained_offline;
	uint64_t submitted;
	uint64_t committed;
	uint64_t rejected;
	uint64_t submission_failures;
	uint64_t stale_publications;
};

bool item_creation_grant_submit_to_player(P_char actor, P_obj object, P_char recipient,
					  P_obj target_container = NULL);
/* As above, but invoke `completion` only after the ownership authority has
 * published the detached object to the recipient (or has terminally rejected
 * the grant). The callback context is copied into the bounded transaction
 * state and must not contain live pointers. */
bool item_creation_grant_submit_to_player_with_completion(P_char actor, P_obj object,
							  P_char recipient,
							  item_movement_completion_fn completion,
							  const void *context, size_t context_size,
							  P_obj target_container = NULL);
// Reports only the final outcome: committed means the durable grant was also
// published into the requested live inventory/container. The callback runs
// after the grant queue releases this request, so it may submit a successor.
bool item_creation_grant_submit_to_player_with_completion(
	P_char actor, P_obj object, P_char recipient, P_obj target_container,
	item_creation_grant_completion_fn completion);
// Admit all detached roots before starting any ownership operation. A refused
// batch leaves every object with the caller; an accepted batch owns every root.
bool item_creation_grant_submit_batch_to_player_before_entry(P_char actor, P_obj const *objects,
							     size_t count, P_char recipient);
bool item_creation_grant_submit_to_room(P_char actor, P_obj object, int room);
bool item_creation_grant_mark_blocking(P_char actor);
bool item_creation_grant_blocks_commands(P_char actor);
// Orderly maintenance must not quiesce between the roots of an accepted kit.
bool item_creation_grant_batches_pending(void);
// A disconnected pre-entry character cannot finish unsubmitted kit roots.
void item_creation_grant_cancel_batch_before_entry(P_char actor);
void item_movement_transaction_handle_completions(const critical_completion *completions,
						  size_t count);
void item_movement_transaction_player_ready(P_char actor);
bool item_movement_transaction_player_busy(P_char actor);
item_movement_health item_movement_transaction_health_copy(void);
void item_movement_transaction_reset_for_tests(void);

#endif
