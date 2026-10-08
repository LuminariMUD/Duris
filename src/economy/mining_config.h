/****************************************************************************
 *
 *  File: mining_config.h                                       Part of Duris
 *  Usage: mining configuration interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef _MINING_CONFIG_H_
#define _MINING_CONFIG_H_

/* Boot-time configuration for mine placement and rewards. */
void mining_config_boot(void);
int mining_config_region_value(int region, const char *field, int fallback);
int mining_config_gem_vnum(int mine_quality);

#endif
