/****************************************************************************
 *
 *  File: zone_touch_command.h                                  Part of Duris
 *  Usage: zone touch command payload and award types
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef ZONE_TOUCH_COMMAND_H
#define ZONE_TOUCH_COMMAND_H

#include "persistence/critical_command.h"
#include "guild/artifact_guild_command.h"

#include <array>

constexpr uint16_t ZONE_TOUCH_PAYLOAD_VERSION = 2;
constexpr size_t ZONE_TOUCH_MAX_PARTICIPANTS = 15;
constexpr size_t ZONE_TOUCH_LEGACY_RESULT_BYTES = 88;
constexpr size_t ZONE_TOUCH_V2_RESULT_BYTES = 512;
constexpr size_t ZONE_TOUCH_RESULT_BYTES = 1024;

struct zone_touch_award
{
	int32_t amount = 0;
	int32_t errand = 0;
	uint8_t flags = 0; // blessing=1, outstanding task penalty=2
	uint64_t boon_id = 0;
	double base = 0;
};

struct zone_touch_payload
{
	uint32_t zone_number;
	uint32_t toucher_pid;
	int32_t boot_time;
	int32_t touched_at;
	uint16_t group_size;
	std::array<uint32_t, ZONE_TOUCH_MAX_PARTICIPANTS> participant_pids;
	int32_t epic_value;
	int16_t alignment_delta;
	uint8_t reset_requested;
	uint64_t stone_uid = 0; // zero identifies legacy metadata-only commands
	int32_t stone_level = 0;
	uint8_t record_zone = 1;
	std::array<zone_touch_award, ZONE_TOUCH_MAX_PARTICIPANTS> awards = {};
	bool prepared_delivery = false; // v3: saved recipient checkpoint owns payment
	bool artifact_intents = false; // v4: immutable entity effects co-commit with the award
	std::vector<critical_command> artifact_deliveries;
};

struct zone_touch_result : zone_touch_payload
{
	zone_touch_result(const zone_touch_payload &payload = {})
		: zone_touch_payload(payload)
	{
	}
	std::array<int64_t, ZONE_TOUCH_MAX_PARTICIPANTS> balances = {};
	std::array<uint64_t, ZONE_TOUCH_MAX_PARTICIPANTS> revisions = {};
	std::array<uint64_t, ZONE_TOUCH_MAX_PARTICIPANTS> previous = {};
	critical_operation_id parent_operation = {};
	bool recovered_claim = false;
};

struct divine_epic_delivery;
bool divine_epic_delivery_from_zone(const critical_operation_id &operation,
				    const zone_touch_result &result, size_t index,
				    divine_epic_delivery *delivery);

bool zone_touch_award_command(const critical_command &parent, size_t index,
			      critical_command *award);

bool zone_touch_command_build(critical_command *command, critical_operation_id operation_id,
			      const zone_touch_payload &payload);
bool zone_touch_command_decode_payload(const critical_command &command,
				       zone_touch_payload *payload);
bool zone_touch_command_encode_result(const zone_touch_result &result,
				      std::array<uint8_t, ZONE_TOUCH_RESULT_BYTES> *encoded);
bool zone_touch_command_decode_result(const uint8_t *encoded, size_t size,
				      zone_touch_result *result);

#endif
