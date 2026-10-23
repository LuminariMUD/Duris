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
	invalid,
};

artifact_guild_capture_status
artifact_guild_state_capture(P_char character, int epics, int epic_type,
			     const critical_operation_id &parent_operation_id,
			     artifact_guild_payload *payload);
artifact_guild_capture_status
artifact_guild_state_prepare_delivery(P_char character, int epics, int epic_type,
				      const critical_operation_id &parent,
				      critical_command *command);

// Prepared delivery IDs are saved in the same snapshot as their effects.
bool artifact_guild_state_apply_delivery(const critical_operation_id &operation,
					 const artifact_guild_payload &payload,
					 artifact_guild_payload *published);
bool artifact_apply_delivery(const critical_operation_id &operation,
			     const artifact_guild_delta &delta, int64_t feeding_cap,
			     bool *newly_applied);
void artifact_forget_delivery(int vnum, const critical_operation_id &operation);
// At most eight entities per game-thread cleanup slice.
void artifact_delivery_markers(int32_t *cursor, critical_operation_id *after,
			       artifact_guild_delivery_ids *ids);
void artifact_guild_state_guild_markers(uint32_t *cursor, critical_operation_id *after,
					artifact_guild_delivery_ids *ids);
// Call only after the native delivery ACK is confirmed durable.
void artifact_guild_state_forget_delivery(const critical_operation_id &operation,
					  const artifact_guild_payload &payload);

// Immediate live application; never use this for history replay.
void artifact_guild_state_apply(P_char character, const artifact_guild_payload &payload);

#endif
