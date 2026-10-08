/****************************************************************************
 *
 *  File: chaos_config.h                                        Part of Duris
 *  Usage: chaos configuration interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef CHAOS_CONFIG_H
#define CHAOS_CONFIG_H

#include <stdbool.h>

/* CHAOS_MUD is enabled only by the exact .env value TRUE. */
bool chaos_mud_enabled(void);

/* CHAOS_EQ_PROFILE accepts standard (default) or enhanceable. */
bool chaos_eq_use_enhanceable_profile(void);

/* New-character Chaos starter grants.  Every accessor also requires CHAOS_MUD. */
bool chaos_starter_bonuses_enabled(void);
bool chaos_starter_frigate_enabled(void);
bool chaos_starter_epic_skills_enabled(void);
bool chaos_starter_epic_points_enabled(void);
bool chaos_starter_bank_platinum_enabled(void);
bool chaos_starter_materials_enabled(void);

/* Local integration-test commands require an explicit, exact opt-in. */
bool chaos_test_commands_enabled(void);

#endif
