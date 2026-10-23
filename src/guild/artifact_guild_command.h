/****************************************************************************
 *
 *  File: artifact_guild_command.h                              Part of Duris
 *  Usage: artifact guild payload, delta, and result types
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef ARTIFACT_GUILD_COMMAND_H
#define ARTIFACT_GUILD_COMMAND_H

#include "guild/artifact_guild_delivery_ids.h"
#include "persistence/critical_command.h"

#include <array>
#include <cstdint>

constexpr uint16_t ARTIFACT_GUILD_PAYLOAD_VERSION = 2;

// A delivery intent must co-commit with its primary prepared award.
constexpr uint16_t ARTIFACT_GUILD_PREPARED_PAYLOAD_VERSION = 3;
constexpr uint32_t ARTIFACT_GUILD_DERIVATION_DOMAIN = 0x41475431;
constexpr size_t ARTIFACT_GUILD_MAX_ARTIFACTS = 15;
constexpr size_t ARTIFACT_GUILD_RESULT_BYTES = 576;
constexpr uint8_t ARTIFACT_DELTA_FEED = 1 << 0;
constexpr uint8_t ARTIFACT_DELTA_BIND = 1 << 1;

struct artifact_guild_delta
{
	int32_t vnum;
	uint8_t flags;
	int64_t timer_before;
	int64_t timer;
	int32_t bind_owner_before;
	int32_t bind_owner_pid;
	int64_t bind_timer_before;
	int64_t bind_timer;
	uint64_t canonical_item_uid = 0;
	int32_t feed_seconds = 0;
};

struct artifact_guild_payload
{
	critical_operation_id parent_operation_id;
	uint32_t actor_pid;
	uint32_t guild_id;
	uint64_t prestige_before;
	uint64_t prestige_after;
	uint64_t construction_before;
	uint64_t construction_after;
	int64_t prestige_delta;
	int64_t construction_delta;
	uint16_t artifact_count;
	std::array<artifact_guild_delta, ARTIFACT_GUILD_MAX_ARTIFACTS> artifacts;
	int64_t feeding_cap = 0;
	uint64_t construction_notch = 0;
	critical_operation_id guild_identity = {};
};

struct artifact_guild_result_entry
{
	int32_t vnum;
	int64_t timer;
	int32_t bind_owner_pid;
	int64_t bind_timer;
	uint64_t revision;
};

struct artifact_guild_result
{
	uint32_t guild_id;
	uint64_t prestige;
	uint64_t construction;
	uint64_t guild_revision;
	uint16_t artifact_count;
	std::array<artifact_guild_result_entry, ARTIFACT_GUILD_MAX_ARTIFACTS> artifacts;
};

// Current payloads describe completed live rewards; before-values are history, not SQL fences.
bool artifact_guild_payload_valid(const artifact_guild_payload &payload);
bool artifact_guild_command_encode_payload(const artifact_guild_payload &payload,
					   std::vector<uint8_t> *encoded);
bool artifact_guild_command_decode_payload(const critical_command &command,
					   artifact_guild_payload *payload);
bool artifact_guild_command_encode_result(const artifact_guild_result &result,
					  std::array<uint8_t, ARTIFACT_GUILD_RESULT_BYTES> *encoded);
bool artifact_guild_command_decode_result(const uint8_t *encoded, size_t size,
					  artifact_guild_result *result);
bool artifact_guild_command_build(critical_command *command, critical_operation_id operation_id,
				  const artifact_guild_payload &payload);

bool artifact_guild_command_valid_delivery(const critical_command &command,
					   const critical_operation_id &parent);

bool artifact_guild_command_build_prepared(critical_command *command,
					   const critical_operation_id &operation_id,
					   const artifact_guild_payload &payload);

#endif
