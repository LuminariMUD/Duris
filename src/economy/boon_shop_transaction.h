/****************************************************************************
 *
 *  File: boon_shop_transaction.h                               Part of Duris
 *  Usage: boon shop transaction interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef BOON_SHOP_TRANSACTION_H
#define BOON_SHOP_TRANSACTION_H

#include "economy/boon_shop_command.h"
#include "persistence/critical_command_coordinator.h"
#include "core/structs.h"

bool boon_shop_transaction_submit(P_char character, uint8_t stat_index);
void boon_shop_transaction_handle_completions(const critical_completion *completions, size_t count);
void boon_shop_transaction_reset_for_tests(void);

#endif
