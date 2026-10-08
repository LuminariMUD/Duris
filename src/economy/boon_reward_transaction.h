/****************************************************************************
 *
 *  File: boon_reward_transaction.h                             Part of Duris
 *  Usage: boon reward transaction interface and health
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef BOON_REWARD_TRANSACTION_H
#define BOON_REWARD_TRANSACTION_H

#include "economy/boon_reward_command.h"
#include "persistence/critical_command_coordinator.h"
#include "persistence/critical_outbox.h"
#include "core/structs.h"

constexpr size_t BOON_REWARD_PENDING_MAX = 1024;

struct boon_reward_health
{
	uint64_t submitted;
	uint64_t committed;
	uint64_t rejected;
	uint64_t submission_failures;
	uint64_t pending;
	uint64_t max_results;
	uint64_t oldest_age_msec;
};

bool boon_reward_transaction_submit(P_char character, P_char victim, double data, int option);
void boon_reward_transaction_handle_completions(const critical_completion *completions,
						size_t count);
void boon_reward_transaction_player_ready(P_char character);
critical_outbox_delivery_result
boon_reward_transaction_outbox_delivery(const critical_outbox_record &record, void *context);
boon_reward_health boon_reward_transaction_health_copy(void);
void boon_reward_transaction_reset_for_tests(void);

#endif
