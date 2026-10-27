/****************************************************************************
 *
 *  File: combat_outcome_command.h                              Part of Duris
 *  Usage: combat outcome payload, participant, and result types
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef COMBAT_OUTCOME_COMMAND_H
#define COMBAT_OUTCOME_COMMAND_H

#include "persistence/critical_command.h"
#include "economy/currency_command.h"
#include "guild/artifact_guild_command.h"

#include <array>
#include <cstdint>
#include <string>

constexpr uint16_t COMBAT_OUTCOME_PAYLOAD_VERSION = 6;
// Capture both configured full racewar groups in the same atomic outcome.
constexpr size_t COMBAT_OUTCOME_MAX_PARTICIPANTS = 40;
constexpr size_t COMBAT_OUTCOME_LEGACY_MAX_PARTICIPANTS = 15;
constexpr size_t COMBAT_OUTCOME_ROOM_NAME_MAX_BYTES = 96;
constexpr size_t COMBAT_OUTCOME_DESCRIPTION_MAX_BYTES = 255;
constexpr size_t COMBAT_OUTCOME_EQUIPMENT_MAX_BYTES = 65535;
constexpr size_t COMBAT_OUTCOME_LOG_MAX_BYTES = 99999;
constexpr size_t COMBAT_OUTCOME_LEGACY_RESULT_BYTES = 1536;
constexpr size_t COMBAT_OUTCOME_PREPARED_RESULT_BYTES = 2048;
constexpr size_t COMBAT_OUTCOME_RESULT_BYTES = 8192;
// Every participant can retain the legacy snapshots without losing the outcome
// when a full group has long logs. The coordinator still enforces its byte budget.
static_assert(COMBAT_OUTCOME_MAX_PARTICIPANTS * (COMBAT_OUTCOME_EQUIPMENT_MAX_BYTES +
						 COMBAT_OUTCOME_LOG_MAX_BYTES + 512) +
		      128 <=
	      CRITICAL_COMMAND_MAX_PAYLOAD_BYTES);

enum class combat_participant_role : uint8_t
{
	unknown = 0,
	killer,
	killer_group,
	victim,
	victim_group,
};

enum combat_participant_flag : uint8_t
{
	COMBAT_PARTICIPANT_IN_ROOM = UINT8_C(1) << 0,
	COMBAT_PARTICIPANT_LEADER = UINT8_C(1) << 1,
	COMBAT_PARTICIPANT_SPILL_BLOOD = UINT8_C(1) << 2,
	COMBAT_PARTICIPANT_DIVINE_EPIC = UINT8_C(1) << 3,
};

enum class combat_webinfo : int8_t
{
	unknown = -1,
	off = 0,
	on = 1,
};

struct combat_outcome_participant
{
	uint32_t pid;
	combat_participant_role role;
	uint8_t flags;
	uint16_t level;
	uint8_t racewar;
	int64_t frag_delta;
	int64_t epic_delta;
	int64_t wallet_delta_copper;
	uint64_t expected_frag_revision;
	uint64_t expected_epic_revision;
	uint64_t expected_wallet_revision;
	uint64_t expected_bank_revision;
	std::array<char, CURRENCY_ACCOUNT_NAME_MAX_BYTES + 1> account_name;
	std::array<char, COMBAT_OUTCOME_DESCRIPTION_MAX_BYTES + 1> description;
	combat_webinfo webinfo_at_capture = combat_webinfo::unknown;
	std::string equipment;
	std::string log;
	uint64_t epic_boon_id = 0;
	double epic_base = 0;
	int32_t epic_spill_blood = 0;
};

struct combat_outcome_payload
{
	uint32_t victim_pid;
	// Same-side mortals in the killer's room; 0 means unknown or no frag award.
	uint32_t killer_allies;
	int32_t room_vnum;
	int64_t gameplay_read_occurred_at;
	uint64_t gameplay_read_token;
	std::array<char, COMBAT_OUTCOME_ROOM_NAME_MAX_BYTES + 1> room_name;
	uint16_t participant_count;
	std::array<combat_outcome_participant, COMBAT_OUTCOME_MAX_PARTICIPANTS> participants;
	int64_t prepared_at = 0;
	bool artifact_intents = false;
	std::vector<critical_command> artifact_deliveries;
};

struct combat_outcome_participant_result
{
	uint32_t pid;
	int64_t frags;
	int64_t epics;
	int64_t wallet_value;
	currency_vector bank;
	uint64_t frag_revision;
	uint64_t epic_revision;
	uint64_t wallet_revision;
	uint64_t bank_revision;
	uint64_t epic_delivery_previous = 0;
	int64_t epic_delivery_delta = 0;
	uint64_t epic_boon_id = 0;
	double epic_base = 0;
	int32_t epic_spill_blood = 0;
	uint8_t epic_delivery_flags = 0;
};

struct combat_outcome_result
{
	uint64_t event_id;
	uint16_t participant_count;
	std::array<combat_outcome_participant_result, COMBAT_OUTCOME_MAX_PARTICIPANTS> participants;
	uint32_t victim_pid = 0;
	int64_t prepared_at = 0;
	bool artifact_intents = false;
};

inline size_t combat_outcome_result_size(const combat_outcome_result &result)
{
	if (result.participant_count > COMBAT_OUTCOME_LEGACY_MAX_PARTICIPANTS)
		return COMBAT_OUTCOME_RESULT_BYTES;
	return result.prepared_at ? COMBAT_OUTCOME_PREPARED_RESULT_BYTES :
				    COMBAT_OUTCOME_LEGACY_RESULT_BYTES;
}

bool combat_outcome_command_encode_payload(const combat_outcome_payload &payload,
					   std::vector<uint8_t> *encoded);
bool combat_outcome_command_decode_payload(const critical_command &command,
					   combat_outcome_payload *payload);
bool combat_outcome_command_encode_result(const combat_outcome_result &result,
					  std::array<uint8_t, COMBAT_OUTCOME_RESULT_BYTES> *encoded);
bool combat_outcome_command_decode_result(const uint8_t *encoded, size_t size,
					  combat_outcome_result *result);
bool combat_outcome_command_build(critical_command *command, critical_operation_id operation_id,
				  const combat_outcome_payload &payload);

#endif
