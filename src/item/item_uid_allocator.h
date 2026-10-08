/****************************************************************************
 *
 *  File: item_uid_allocator.h                                  Part of Duris
 *  Usage: item uid allocator interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef ITEM_UID_ALLOCATOR_H
#define ITEM_UID_ALLOCATOR_H

#include <cstdint>

#include <mysql/mysql.h>

constexpr uint64_t ITEM_UID_BOOT_RESERVATION = UINT64_C(1000000);

bool item_uid_allocator_reserve(MYSQL *connection, uint64_t count);
uint64_t item_uid_allocator_next(void);
void item_uid_allocator_reset_for_tests(void);

#endif
