/****************************************************************************
 *
 *  File: persistence_mode.h                                    Part of Duris
 *  Usage: persistence mode type and interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef PERSISTENCE_MODE_H
#define PERSISTENCE_MODE_H

#include <stdbool.h>
#include <stddef.h>

bool persistence_mode_configure(char *error, size_t error_size);
const char *persistence_mode_name(void);

#endif
