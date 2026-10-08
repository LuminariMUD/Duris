/****************************************************************************
 *
 *  File: shop_trade_transaction.h                              Part of Duris
 *  Usage: shop trade transaction interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef SHOP_TRADE_TRANSACTION_H
#define SHOP_TRADE_TRANSACTION_H

#include "persistence/critical_command_coordinator.h"
#include "economy/shop_trade_command.h"
#include "core/structs.h"

#include <cstddef>

constexpr size_t SHOP_TRADE_PENDING_MAX = 128;

using shop_trade_completion_fn = void (*)(P_char character, bool committed,
					  const shop_trade_result &result, unsigned int error_code,
					  const shop_trade_payload &payload);

bool shop_trade_transaction_submit(P_char character, const shop_trade_payload &payload,
				   shop_trade_completion_fn completion);
void shop_trade_transaction_handle_completions(const critical_completion *completions,
					       size_t count);
void shop_trade_transaction_player_ready(P_char character);
bool shop_trade_transaction_player_busy(P_char character);
void shop_trade_transaction_reset_for_tests(void);

#endif
