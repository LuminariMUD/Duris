/****************************************************************************
 *
 *  File: zone_touch_transaction.h                              Part of Duris
 *  Usage: zone touch transaction interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef ZONE_TOUCH_TRANSACTION_H
#define ZONE_TOUCH_TRANSACTION_H

#include "persistence/critical_command_coordinator.h"
#include "persistence/critical_outbox.h"
#include "world/zone_touch_command.h"

constexpr size_t ZONE_TOUCH_PENDING_MAX = 64;

struct char_data;
bool zone_touch_transaction_busy(uint64_t stone_uid, uint32_t zone_number);
void zone_touch_transaction_player_ready(char_data *character);

bool zone_touch_transaction_submit(const zone_touch_payload &payload);
void zone_touch_transaction_handle_completions(const critical_completion *completions,
					       size_t count);
critical_outbox_delivery_result
zone_touch_transaction_outbox_delivery(const critical_outbox_record &record, void *context);
void zone_touch_transaction_reset_for_tests(void);

#endif
