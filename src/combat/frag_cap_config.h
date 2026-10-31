/****************************************************************************
 *
 *  File: frag_cap_config.h                                     Part of Duris
 *  Usage: frag cap configuration types and interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef DURIS_FRAG_CAP_CONFIG_H
#define DURIS_FRAG_CAP_CONFIG_H

#include "combat/frag_cap.h"

struct frag_cap_config
{
	int cap_floor_level;
	int legacy_maximum_level;
	int round_hours;
	int hardcore_levels_beyond_cap;
};

void boot_frag_cap_config(void);
const struct frag_cap_config *frag_cap_config_get(void);
int frag_cap_config_hardcore_level_cap(int normal_cap);

frag_cap_policy frag_cap_config_policy(void);

#endif
