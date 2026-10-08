/****************************************************************************
 *
 *  File: collector_presence.h                                  Part of Duris
 *  Usage: collector presence interface and health
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef DURIS_COLLECTOR_PRESENCE_H
#define DURIS_COLLECTOR_PRESENCE_H

#include "core/structs.h"

#include <cstddef>
#include <cstdint>

struct collector_presence_health
{
	bool initialized = false;
	bool desired = false;
	size_t registered_rooms = 0;
	size_t active_rooms = 0;
	size_t live_collectors = 0;
	uint64_t reconciliations = 0;
	uint64_t spawned = 0;
	uint64_t removed = 0;
	uint64_t duplicates_removed = 0;
	uint64_t off_registry_removed = 0;
	uint64_t spawn_failures = 0;
	uint64_t prototype_conflicts = 0;
};

// Installs the dedicated collector prototype procedure after boot_db() has
// loaded and assigned the world's mobile index. The game-thread reconciliation
// below owns every live instance of that prototype.
bool collector_presence_init(void);
void collector_presence_pulse(void);
void collector_presence_shutdown(void);

// Runtime guards used by commands and hostile gameplay paths. A service room is
// active only when it contains exactly one reconciled collector.
bool collector_presence_is_npc(P_char character);
bool collector_presence_room_active(int room_rnum);
collector_presence_health collector_presence_health_copy(void);

#endif
