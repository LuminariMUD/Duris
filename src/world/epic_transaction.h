/****************************************************************************
 *
 *  File: epic_transaction.h                                    Part of Duris
 *  Usage: epic transaction interface and health
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef EPIC_TRANSACTION_H
#define EPIC_TRANSACTION_H

#include "persistence/critical_command_coordinator.h"
#include "world/epic_command.h"
#include "core/structs.h"

#include <cstddef>
#include <cstdint>

// The size callers keep their completion context within.
constexpr size_t EPIC_PENDING_CONTEXT_MAX_BYTES = 256;

// Epic points live in memory: a submit changes the balance at once and calls its
// completion before returning (refused with ENOSPC when a purchase needs more than the
// balance). The save writes the balance; the command only adds an epic ledger row.
using epic_completion_fn = void (*)(P_char character, bool committed,
				    const epic_command_result &result, unsigned int error_code,
				    const uint8_t *context, size_t context_size);

struct epic_transaction_health
{
	uint64_t submitted;
	uint64_t committed;
	uint64_t rejected;
	// Ledger rows the coordinator would not queue.
	uint64_t submission_failures;
};

bool epic_transaction_submit(P_char character, int64_t delta, epic_reason_type reason,
			     int64_t reason_id, uint16_t flags, critical_source_site source_site,
			     critical_deadline_class deadline_class, epic_completion_fn completion,
			     const void *context, size_t context_size);
bool epic_transaction_submit_identified(P_char character, const critical_operation_id &operation_id,
					int64_t delta, epic_reason_type reason, int64_t reason_id,
					uint16_t flags, critical_source_site source_site,
					critical_deadline_class deadline_class,
					epic_completion_fn completion, const void *context,
					size_t context_size);
epic_transaction_health epic_transaction_health_copy(void);
void epic_transaction_reset_for_tests(void);

#endif
