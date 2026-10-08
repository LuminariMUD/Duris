/****************************************************************************
 *
 *  File: creation_availability_config.h                        Part of Duris
 *  Usage: creation availability configuration interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef CREATION_AVAILABILITY_CONFIG_H
#define CREATION_AVAILABILITY_CONFIG_H

#include <stdbool.h>

void boot_creation_availability_config(void);
bool creation_class_enabled(int class_id);
bool creation_class_normally_available(int race_id, int class_id);
bool creation_race_enabled(int race_id);
bool creation_all_races_enabled(void);
bool creation_all_classes_enabled(void);
int creation_class_align(int race_id, int class_id);

#endif
