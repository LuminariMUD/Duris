/****************************************************************************
 *
 *  File: artifact_guild_command.c                              Part of Duris
 *  Usage: encodes and decodes artifact guild commands
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#include "guild/artifact_guild_command.h"

#include <algorithm>
#include <limits>

namespace
{
template <typename T> void append_le(std::vector<uint8_t> *output, T value)
{
	for (size_t byte = 0; byte < sizeof(T); ++byte)
		output->push_back(static_cast<uint8_t>(static_cast<uint64_t>(value) >> (byte * 8)));
}

template <typename T> bool read_le(const uint8_t **cursor, const uint8_t *end, T *value)
{
	if (!cursor || !*cursor || !value || static_cast<size_t>(end - *cursor) < sizeof(T))
		return false;
	uint64_t decoded = 0;
	for (size_t byte = 0; byte < sizeof(T); ++byte)
		decoded |= static_cast<uint64_t>((*cursor)[byte]) << (byte * 8);
	*cursor += sizeof(T);
	*value = static_cast<T>(decoded);
	return true;
}

bool valid(const artifact_guild_payload &payload, bool legacy, bool prepared)
{
	if (critical_operation_id_is_zero(payload.parent_operation_id) || !payload.actor_pid ||
	    payload.artifact_count > payload.artifacts.size() ||
	    (!payload.guild_id && !payload.artifact_count) ||
	    (!payload.guild_id &&
	     (payload.prestige_delta || payload.construction_delta || payload.prestige_before ||
	      payload.prestige_after || payload.construction_before || payload.construction_after)))
		return false;
	if (!legacy &&
	    (payload.prestige_delta < 0 || payload.construction_delta < 0 ||
	     static_cast<uint64_t>(payload.prestige_delta) > UINT64_MAX - payload.prestige_before ||
	     static_cast<uint64_t>(payload.construction_delta) >
		     UINT64_MAX - payload.construction_before ||
	     payload.prestige_after != payload.prestige_before + payload.prestige_delta ||
	     payload.construction_after !=
		     payload.construction_before + payload.construction_delta))
		return false;
	if (prepared &&
	    ((payload.guild_id && (!payload.construction_notch ||
				   critical_operation_id_is_zero(payload.guild_identity))) ||
	     (payload.artifact_count && payload.feeding_cap <= 0)))
		return false;
	if (prepared && payload.guild_id &&
	    payload.prestige_after / payload.construction_notch -
			    payload.prestige_before / payload.construction_notch !=
		    static_cast<uint64_t>(payload.construction_delta))
		return false;
	for (size_t index = 0; index < payload.artifact_count; ++index)
	{
		const auto &entry = payload.artifacts[index];
		if (entry.vnum <= 0 ||
		    !(entry.flags & (ARTIFACT_DELTA_FEED | ARTIFACT_DELTA_BIND)) ||
		    (entry.flags & ~(ARTIFACT_DELTA_FEED | ARTIFACT_DELTA_BIND)) ||
		    entry.timer < 0 || entry.bind_timer < 0)
			return false;
		if (!legacy && (entry.flags != ARTIFACT_DELTA_FEED || entry.timer_before < 0 ||
				entry.bind_owner_before != entry.bind_owner_pid ||
				entry.bind_timer_before != entry.bind_timer))
			return false;
		if (prepared)
		{
			if (!entry.canonical_item_uid ||
			    (entry.feed_seconds > 0 &&
			     entry.timer_before > INT64_MAX - entry.feed_seconds))
				return false;
			const int64_t target = std::clamp<int64_t>(
				entry.timer_before + entry.feed_seconds, 0, payload.feeding_cap);
			if (target != entry.timer)
				return false;
		}
		for (size_t other = 0; other < index; ++other)
			if (payload.artifacts[other].vnum == entry.vnum ||
			    (prepared && payload.artifacts[other].canonical_item_uid ==
						 entry.canonical_item_uid))
				return false;
	}
	return true;
}

void set_keys(critical_command *command, const artifact_guild_payload &payload, bool prepared)
{
	command->keys.push_back({ critical_entity_type::player, payload.actor_pid });
	if (payload.guild_id)
		command->keys.push_back({ critical_entity_type::guild, payload.guild_id });
	for (size_t index = 0; index < payload.artifact_count; ++index)
	{
		command->keys.push_back({ critical_entity_type::artifact,
					  static_cast<uint64_t>(payload.artifacts[index].vnum) });
		if (prepared)
			command->keys.push_back({ critical_entity_type::item,
						  payload.artifacts[index].canonical_item_uid });
	}
	std::sort(command->keys.begin(), command->keys.end(), critical_entity_key_less);
}

void put_u64(uint8_t *output, uint64_t value)
{
	for (size_t byte = 0; byte < 8; ++byte)
		output[byte] = static_cast<uint8_t>(value >> (byte * 8));
}

uint64_t get_u64(const uint8_t *input)
{
	uint64_t value = 0;
	for (size_t byte = 0; byte < 8; ++byte)
		value |= static_cast<uint64_t>(input[byte]) << (byte * 8);
	return value;
}
} // namespace

bool artifact_guild_payload_valid(const artifact_guild_payload &payload)
{
	return valid(payload, false, false);
}

static bool encode_payload(const artifact_guild_payload &payload, std::vector<uint8_t> *encoded,
			   bool prepared)
{
	if (!encoded || !valid(payload, false, prepared))
		return false;
	encoded->clear();
	encoded->insert(encoded->end(), payload.parent_operation_id.bytes.begin(),
			payload.parent_operation_id.bytes.end());
	append_le<uint32_t>(encoded, payload.actor_pid);
	append_le<uint32_t>(encoded, payload.guild_id);
	append_le<int64_t>(encoded, payload.prestige_delta);
	append_le<int64_t>(encoded, payload.construction_delta);
	append_le<uint64_t>(encoded, payload.prestige_before);
	append_le<uint64_t>(encoded, payload.prestige_after);
	append_le<uint64_t>(encoded, payload.construction_before);
	append_le<uint64_t>(encoded, payload.construction_after);
	if (prepared)
	{
		append_le<int64_t>(encoded, payload.feeding_cap);
		append_le<uint64_t>(encoded, payload.construction_notch);
		encoded->insert(encoded->end(), payload.guild_identity.bytes.begin(),
				payload.guild_identity.bytes.end());
	}
	append_le<uint16_t>(encoded, payload.artifact_count);
	for (size_t index = 0; index < payload.artifact_count; ++index)
	{
		const auto &entry = payload.artifacts[index];
		append_le<int32_t>(encoded, entry.vnum);
		append_le<uint8_t>(encoded, entry.flags);
		append_le<int64_t>(encoded, entry.timer_before);
		append_le<int64_t>(encoded, entry.timer);
		append_le<int32_t>(encoded, entry.bind_owner_before);
		append_le<int32_t>(encoded, entry.bind_owner_pid);
		append_le<int64_t>(encoded, entry.bind_timer_before);
		append_le<int64_t>(encoded, entry.bind_timer);
		if (prepared)
		{
			if (!entry.canonical_item_uid)
				return false;
			append_le<uint64_t>(encoded, entry.canonical_item_uid);
			append_le<int32_t>(encoded, entry.feed_seconds);
		}
	}
	return encoded->size() <= CRITICAL_COMMAND_MAX_PAYLOAD_BYTES;
}

bool artifact_guild_command_encode_payload(const artifact_guild_payload &payload,
					   std::vector<uint8_t> *encoded)
{
	return encode_payload(payload, encoded, false);
}

bool artifact_guild_command_decode_payload(const critical_command &command,
					   artifact_guild_payload *payload)
{
	const bool legacy = command.payload_version == 1;
	const bool prepared = command.payload_version == ARTIFACT_GUILD_PREPARED_PAYLOAD_VERSION;
	if (!payload || command.type != critical_command_type::artifact ||
	    (!legacy && !prepared && command.payload_version != ARTIFACT_GUILD_PAYLOAD_VERSION) ||
	    command.payload.size() < CRITICAL_COMMAND_ID_BYTES)
		return false;
	*payload = {};
	const uint8_t *cursor = command.payload.data();
	const uint8_t *end = cursor + command.payload.size();
	std::copy_n(cursor, payload->parent_operation_id.bytes.size(),
		    payload->parent_operation_id.bytes.begin());
	cursor += payload->parent_operation_id.bytes.size();
	uint64_t guild_revision = 0;
	if (!read_le(&cursor, end, &payload->actor_pid) ||
	    !read_le(&cursor, end, &payload->guild_id) ||
	    (legacy && !read_le(&cursor, end, &guild_revision)) ||
	    !read_le(&cursor, end, &payload->prestige_delta) ||
	    !read_le(&cursor, end, &payload->construction_delta))
		return false;
	if (!legacy && (!read_le(&cursor, end, &payload->prestige_before) ||
			!read_le(&cursor, end, &payload->prestige_after) ||
			!read_le(&cursor, end, &payload->construction_before) ||
			!read_le(&cursor, end, &payload->construction_after)))
		return false;
	if (prepared && (!read_le(&cursor, end, &payload->feeding_cap) ||
			 !read_le(&cursor, end, &payload->construction_notch)))
		return false;
	if (prepared)
	{
		if (static_cast<size_t>(end - cursor) < payload->guild_identity.bytes.size())
			return false;
		std::copy_n(cursor, payload->guild_identity.bytes.size(),
			    payload->guild_identity.bytes.begin());
		cursor += payload->guild_identity.bytes.size();
	}
	if (!read_le(&cursor, end, &payload->artifact_count) ||
	    payload->artifact_count > payload->artifacts.size())
		return false;
	critical_command expected = {};
	if (legacy && payload->guild_id)
		expected.expected_revisions.push_back(
			{ { critical_entity_type::guild, payload->guild_id }, guild_revision });
	for (size_t index = 0; index < payload->artifact_count; ++index)
	{
		auto &entry = payload->artifacts[index];
		uint64_t revision = 0;
		if (!read_le(&cursor, end, &entry.vnum) || !read_le(&cursor, end, &entry.flags) ||
		    (legacy && !read_le(&cursor, end, &revision)) ||
		    !read_le(&cursor, end, &entry.timer_before) ||
		    !read_le(&cursor, end, &entry.timer) ||
		    !read_le(&cursor, end, &entry.bind_owner_before) ||
		    !read_le(&cursor, end, &entry.bind_owner_pid) ||
		    !read_le(&cursor, end, &entry.bind_timer_before) ||
		    !read_le(&cursor, end, &entry.bind_timer) ||
		    (prepared && (!read_le(&cursor, end, &entry.canonical_item_uid) ||
				  !read_le(&cursor, end, &entry.feed_seconds))))
			return false;
		if (legacy)
			expected.expected_revisions.push_back(
				{ { critical_entity_type::artifact,
				    static_cast<uint64_t>(entry.vnum) },
				  revision });
	}
	if (cursor != end || !valid(*payload, legacy, prepared))
		return false;
	set_keys(&expected, *payload, prepared);
	std::sort(expected.expected_revisions.begin(), expected.expected_revisions.end(),
		  [](const auto &a, const auto &b)
		  { return critical_entity_key_less(a.key, b.key); });
	return expected.keys.size() == command.keys.size() &&
	       std::equal(expected.keys.begin(), expected.keys.end(), command.keys.begin(),
			  critical_entity_key_equal) &&
	       expected.expected_revisions.size() == command.expected_revisions.size() &&
	       std::equal(expected.expected_revisions.begin(), expected.expected_revisions.end(),
			  command.expected_revisions.begin(),
			  [](const auto &a, const auto &b) {
				  return critical_entity_key_equal(a.key, b.key) &&
					 a.revision == b.revision;
			  });
}

bool artifact_guild_command_encode_result(const artifact_guild_result &result,
					  std::array<uint8_t, ARTIFACT_GUILD_RESULT_BYTES> *encoded)
{
	constexpr size_t HEADER = 30;
	constexpr size_t ENTRY = 36;
	if (!encoded || result.artifact_count > result.artifacts.size() ||
	    HEADER + result.artifact_count * ENTRY > encoded->size())
		return false;
	encoded->fill(0);
	for (size_t byte = 0; byte < 4; ++byte)
		(*encoded)[byte] = static_cast<uint8_t>(result.guild_id >> (byte * 8));
	put_u64(encoded->data() + 4, result.prestige);
	put_u64(encoded->data() + 12, result.construction);
	put_u64(encoded->data() + 20, result.guild_revision);
	(*encoded)[28] = static_cast<uint8_t>(result.artifact_count);
	(*encoded)[29] = static_cast<uint8_t>(result.artifact_count >> 8);
	for (size_t index = 0; index < result.artifact_count; ++index)
	{
		uint8_t *row = encoded->data() + HEADER + index * ENTRY;
		const auto &entry = result.artifacts[index];
		for (size_t byte = 0; byte < 4; ++byte)
			row[byte] = static_cast<uint8_t>(entry.vnum >> (byte * 8));
		put_u64(row + 4, static_cast<uint64_t>(entry.timer));
		for (size_t byte = 0; byte < 4; ++byte)
			row[12 + byte] = static_cast<uint8_t>(entry.bind_owner_pid >> (byte * 8));
		put_u64(row + 16, static_cast<uint64_t>(entry.bind_timer));
		put_u64(row + 24, entry.revision);
	}
	return true;
}

bool artifact_guild_command_decode_result(const uint8_t *encoded, size_t size,
					  artifact_guild_result *result)
{
	constexpr size_t HEADER = 30;
	constexpr size_t ENTRY = 36;
	if (!encoded || !result || size != ARTIFACT_GUILD_RESULT_BYTES)
		return false;
	*result = {};
	for (size_t byte = 0; byte < 4; ++byte)
		result->guild_id |= static_cast<uint32_t>(encoded[byte]) << (byte * 8);
	result->prestige = get_u64(encoded + 4);
	result->construction = get_u64(encoded + 12);
	result->guild_revision = get_u64(encoded + 20);
	result->artifact_count = encoded[28] | static_cast<uint16_t>(encoded[29]) << 8;
	if (result->artifact_count > result->artifacts.size())
		return false;
	for (size_t index = 0; index < result->artifact_count; ++index)
	{
		const uint8_t *row = encoded + HEADER + index * ENTRY;
		auto &entry = result->artifacts[index];
		for (size_t byte = 0; byte < 4; ++byte)
			entry.vnum |= static_cast<int32_t>(static_cast<uint32_t>(row[byte])
							   << (byte * 8));
		entry.timer = static_cast<int64_t>(get_u64(row + 4));
		for (size_t byte = 0; byte < 4; ++byte)
			entry.bind_owner_pid |= static_cast<int32_t>(
				static_cast<uint32_t>(row[12 + byte]) << (byte * 8));
		entry.bind_timer = static_cast<int64_t>(get_u64(row + 16));
		entry.revision = get_u64(row + 24);
	}
	return true;
}

bool artifact_guild_command_build(critical_command *command, critical_operation_id operation_id,
				  const artifact_guild_payload &payload)
{
	if (!command || !valid(payload, false, false))
		return false;
	*command = { .schema_version = CRITICAL_COMMAND_SCHEMA_VERSION,
		     .operation_id = operation_id,
		     .type = critical_command_type::artifact,
		     .payload_version = ARTIFACT_GUILD_PAYLOAD_VERSION,
		     .source_site = critical_source_site::combat,
		     .deadline_class = critical_deadline_class::background,
		     .accepted_at_usec = 0,
		     .keys = {},
		     .expected_revisions = {},
		     .payload = {} };
	set_keys(command, payload, false);
	return command->keys.size() <= CRITICAL_COMMAND_MAX_KEYS &&
	       artifact_guild_command_encode_payload(payload, &command->payload);
}

bool artifact_guild_command_build_prepared(critical_command *command,
					   const critical_operation_id &operation_id,
					   const artifact_guild_payload &payload)
{
	if (!command)
		return false;
	critical_command prepared;
	if (!artifact_guild_command_build(&prepared, operation_id, payload) ||
	    !encode_payload(payload, &prepared.payload, true))
		return false;
	prepared.payload_version = ARTIFACT_GUILD_PREPARED_PAYLOAD_VERSION;
	prepared.keys.clear();
	set_keys(&prepared, payload, true);
	*command = std::move(prepared);
	return true;
}

bool artifact_guild_command_valid_delivery(const critical_command &command,
					   const critical_operation_id &parent)
{
	artifact_guild_payload payload{};
	critical_operation_id expected{};
	return command.payload_version == ARTIFACT_GUILD_PREPARED_PAYLOAD_VERSION &&
	       artifact_guild_command_decode_payload(command, &payload) &&
	       payload.parent_operation_id.bytes == parent.bytes &&
	       critical_operation_id_derive(parent, ARTIFACT_GUILD_DERIVATION_DOMAIN,
					    payload.actor_pid, &expected) &&
	       expected.bytes == command.operation_id.bytes;
}
