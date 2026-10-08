/****************************************************************************
 *
 *  File: epic_task_catalog.h                                   Part of Duris
 *  Usage: epic task catalog interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef EPIC_TASK_CATALOG_H
#define EPIC_TASK_CATALOG_H

#include "persistence/gameplay_read_state.h"

#include <cstddef>
#include <cstdint>

constexpr size_t EPIC_TASK_CATALOG_MAX = 1024;

enum class epic_task_catalog_status : uint8_t
{
	unavailable,
	ready,
};

bool epic_task_catalog_publish(const int32_t *zone_numbers, size_t count);
bool epic_task_catalog_refresh(void);
int epic_task_catalog_select(const gameplay_read_state *state);
size_t epic_task_catalog_size(void);
bool epic_task_catalog_ready(void);
void epic_task_catalog_reset_for_tests(void);

#endif
