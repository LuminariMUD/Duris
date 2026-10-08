/****************************************************************************
 *
 *  File: currency_transaction.h                                Part of Duris
 *  Usage: currency transaction interface and health
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef DURIS_ECONOMY_CURRENCY_TRANSACTION_H
#define DURIS_ECONOMY_CURRENCY_TRANSACTION_H

#include "persistence/critical_command.h"
#include "economy/currency_command.h"
#include "core/structs.h"

#include <cstddef>
#include <cstdint>

// The size callers keep their completion context within.
constexpr size_t CURRENCY_PENDING_CONTEXT_MAX_BYTES = 64;

// Money lives in memory. A transaction changes the character's wallet, and the bank of
// every online character of its account and side, at once, then calls its completion
// before returning: committed, or refused with ENOSPC when a balance would go below zero
// (the submit still returns true). The save writes the wallet; a bank change is queued on
// the one writer as a delta, after the player's save when the bank gains and before it
// when the bank loses, so a crash can lose money but never pay it twice.
using currency_completion_fn = void (*)(P_char character, bool committed,
					const currency_command_result &result,
					unsigned int error_code, const uint8_t *context,
					size_t context_size);

struct currency_transaction_health
{
	uint64_t submitted;
	uint64_t committed;
	uint64_t rejected;
	uint64_t bank_deltas;
};

bool currency_transaction_submit(P_char character, const currency_vector &wallet_delta,
				 const currency_vector &bank_delta, currency_reason_type reason,
				 int64_t reason_id, critical_source_site source_site,
				 critical_deadline_class deadline_class,
				 currency_completion_fn completion, const void *context,
				 size_t context_size);
bool currency_transaction_submit_identified(
	P_char character, const critical_operation_id &operation_id,
	const currency_vector &wallet_delta, const currency_vector &bank_delta,
	currency_reason_type reason, int64_t reason_id, critical_source_site source_site,
	critical_deadline_class deadline_class, currency_completion_fn completion,
	const void *context, size_t context_size);
// Prepare a locker payment without applying it. A durable receipt stores this exact
// command before submit_prepared applies it.
bool currency_transaction_prepare_identify(P_char character, int64_t cost,
					   critical_command *command);
bool currency_transaction_submit_prepared(P_char character, const critical_command &command,
					  currency_completion_fn completion, const void *context,
					  size_t context_size);
bool currency_transaction_submit_wallet_value(P_char character, int64_t value_delta,
					      currency_reason_type reason, int64_t reason_id,
					      critical_source_site source_site,
					      critical_deadline_class deadline_class,
					      currency_completion_fn completion,
					      const void *context, size_t context_size);
bool currency_transaction_submit_bank_reward(P_char character, int64_t value,
					     currency_reason_type reason, int64_t reason_id,
					     critical_source_site source_site,
					     critical_deadline_class deadline_class,
					     currency_completion_fn completion, const void *context,
					     size_t context_size);
bool currency_transaction_submit_bank_payment(P_char character, int64_t value,
					      currency_reason_type reason, int64_t reason_id,
					      critical_source_site source_site,
					      critical_deadline_class deadline_class,
					      currency_completion_fn completion,
					      const void *context, size_t context_size);
// Queue the character's save now, before whatever the money it gave up moves into is
// saved: when money leaves one saved owner for another, the one it leaves goes first.
void currency_transaction_save_first(P_char character);
currency_transaction_health currency_transaction_health_copy(void);
void currency_transaction_reset_for_tests(void);

#endif
