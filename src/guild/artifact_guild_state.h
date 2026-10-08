/****************************************************************************
 *
 *  File: artifact_guild_state.h                                Part of Duris
 *  Usage: artifact guild state interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef ARTIFACT_GUILD_STATE_H
#define ARTIFACT_GUILD_STATE_H

#include "guild/artifact_guild_command.h"
#include "core/structs.h"

enum class artifact_guild_capture_status : uint8_t
{
	ready,
	no_effect,
	unavailable,
};

bool artifact_guild_state_hydrate(void);
artifact_guild_capture_status
artifact_guild_state_capture(P_char character, int epics, int epic_type,
			     const critical_operation_id &parent_operation_id,
			     artifact_guild_payload *payload);
void artifact_guild_state_publish(const artifact_guild_result &result,
				  const artifact_guild_payload &payload);
bool artifact_guild_state_ready(void);
void artifact_guild_state_reset_for_tests(void);

#endif
