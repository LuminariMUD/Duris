/****************************************************************************
 *
 *  File: combat_outcome_command.c                              Part of Duris
 *  Usage: encodes and decodes combat outcome commands
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#include "combat/combat_outcome_command.h"
#include "economy/divine_boon_delivery.h"

#include <algorithm>
#include <bit>
#include <cmath>
#include <limits>
#include <cstring>
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

template <size_t N> bool bounded(const std::array<char, N> &value)
{
	return memchr(value.data(), '\0', value.size()) != nullptr;
}

template <size_t N>
void append_string(std::vector<uint8_t> *output, const std::array<char, N> &value)
{
	const size_t size = strnlen(value.data(), value.size());
	append_le<uint16_t>(output, static_cast<uint16_t>(size));
	output->insert(output->end(), value.data(), value.data() + size);
}

template <size_t N>
bool read_string(const uint8_t **cursor, const uint8_t *end, std::array<char, N> *value)
{
	uint16_t size = 0;
	if (!read_le(cursor, end, &size) || size >= N || static_cast<size_t>(end - *cursor) < size)
		return false;
	value->fill('\0');
	memcpy(value->data(), *cursor, size);
	*cursor += size;
	return true;
}

void append_text(std::vector<uint8_t> *output, const std::string &value)
{
	append_le<uint32_t>(output, static_cast<uint32_t>(value.size()));
	output->insert(output->end(), value.begin(), value.end());
}

bool read_text(const uint8_t **cursor, const uint8_t *end, size_t maximum, std::string *value)
{
	uint32_t size = 0;
	if (!read_le(cursor, end, &size) || size > maximum ||
	    static_cast<size_t>(end - *cursor) < size || memchr(*cursor, '\0', size))
		return false;
	value->assign(reinterpret_cast<const char *>(*cursor), size);
	*cursor += size;
	return true;
}

bool valid(const combat_outcome_payload &payload)
{
	if (!payload.victim_pid || !payload.participant_count ||
	    payload.participant_count > payload.participants.size() || !bounded(payload.room_name))
		return false;
	const auto victim = std::find_if(payload.participants.begin(),
					 payload.participants.begin() + payload.participant_count,
					 [&](const auto &entry)
					 { return entry.pid == payload.victim_pid; });
	if (victim == payload.participants.begin() + payload.participant_count)
		return false;
	bool prepared = false;
	for (size_t index = 0; index < payload.participant_count; ++index)
	{
		const auto &entry = payload.participants[index];
		if (!entry.pid || entry.role == combat_participant_role::unknown ||
		    entry.role > combat_participant_role::victim_group ||
		    !bounded(entry.account_name) || !bounded(entry.description) ||
		    entry.equipment.size() > COMBAT_OUTCOME_EQUIPMENT_MAX_BYTES ||
		    entry.log.size() > COMBAT_OUTCOME_LOG_MAX_BYTES ||
		    entry.equipment.find('\0') != std::string::npos ||
		    entry.log.find('\0') != std::string::npos ||
		    (entry.webinfo_at_capture != combat_webinfo::unknown &&
		     entry.webinfo_at_capture != combat_webinfo::off &&
		     entry.webinfo_at_capture != combat_webinfo::on) ||
		    (entry.webinfo_at_capture == combat_webinfo::off &&
		     (!entry.equipment.empty() || !entry.log.empty())) ||
		    ((entry.wallet_delta_copper != 0) && !entry.account_name[0]))
			return false;
		if (entry.flags & COMBAT_PARTICIPANT_DIVINE_EPIC)
		{
			if (!entry.epic_boon_id || !std::isfinite(entry.epic_base) ||
			    entry.epic_base <= 0 || entry.epic_delta <= 0 ||
			    entry.epic_delta > std::numeric_limits<int>::max() ||
			    entry.frag_delta <= 0 || entry.pid == payload.victim_pid ||
			    !(entry.flags & COMBAT_PARTICIPANT_IN_ROOM) ||
			    !((entry.racewar == 1 && victim->racewar == 2) ||
			      (entry.racewar == 2 && victim->racewar == 1)) ||
			    (entry.epic_spill_blood != 0 && entry.epic_spill_blood != 500) ||
			    ((entry.epic_spill_blood != 0) !=
			     ((entry.flags & COMBAT_PARTICIPANT_SPILL_BLOOD) != 0)))
				return false;
			prepared = true;
		}
		else if (entry.epic_boon_id || entry.epic_base != 0 || entry.epic_spill_blood)
			return false;
		for (size_t other = 0; other < index; ++other)
			if (payload.participants[other].pid == entry.pid)
				return false;
	}
	if ((!payload.artifact_intents && !payload.artifact_deliveries.empty()) ||
	    (payload.artifact_intents && !prepared) ||
	    payload.artifact_deliveries.size() > payload.participant_count)
		return false;
	std::array<uint32_t, COMBAT_OUTCOME_MAX_PARTICIPANTS> actors{};
	for (size_t i = 0; i < payload.artifact_deliveries.size(); ++i)
	{
		artifact_guild_payload effect{};
		const auto &child = payload.artifact_deliveries[i];
		if (child.payload_version != ARTIFACT_GUILD_PREPARED_PAYLOAD_VERSION ||
		    !artifact_guild_command_decode_payload(child, &effect) ||
		    std::find(actors.begin(), actors.begin() + i, effect.actor_pid) !=
			    actors.begin() + i ||
		    std::none_of(payload.participants.begin(),
				 payload.participants.begin() + payload.participant_count,
				 [&](const auto &entry) {
					 return entry.pid == effect.actor_pid &&
						(entry.flags & COMBAT_PARTICIPANT_DIVINE_EPIC);
				 }))
			return false;
		actors[i] = effect.actor_pid;
	}
	return prepared ? payload.prepared_at > 0 : payload.prepared_at == 0;
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

bool combat_outcome_command_encode_payload(const combat_outcome_payload &payload,
					   std::vector<uint8_t> *encoded)
{
	if (!encoded || !valid(payload))
		return false;
	encoded->clear();
	append_le<uint32_t>(encoded, payload.victim_pid);
	append_le<int32_t>(encoded, payload.room_vnum);
	append_string(encoded, payload.room_name);
	append_le<uint16_t>(encoded, payload.participant_count);
	for (size_t index = 0; index < payload.participant_count; ++index)
	{
		const auto &entry = payload.participants[index];
		append_le<uint32_t>(encoded, entry.pid);
		append_le<uint8_t>(encoded, static_cast<uint8_t>(entry.role));
		append_le<uint8_t>(encoded, entry.flags);
		append_le<uint16_t>(encoded, entry.level);
		append_le<uint8_t>(encoded, entry.racewar);
		append_le<int64_t>(encoded, entry.frag_delta);
		append_le<int64_t>(encoded, entry.epic_delta);
		append_le<int64_t>(encoded, entry.wallet_delta_copper);
		append_le<uint64_t>(encoded, entry.expected_frag_revision);
		append_le<uint64_t>(encoded, entry.expected_epic_revision);
		append_le<uint64_t>(encoded, entry.expected_wallet_revision);
		append_le<uint64_t>(encoded, entry.expected_bank_revision);
		append_string(encoded, entry.account_name);
		append_string(encoded, entry.description);
	}
	append_le<uint32_t>(encoded, payload.killer_allies);
	for (size_t index = 0; index < payload.participant_count; ++index)
	{
		append_text(encoded, payload.participants[index].equipment);
		append_text(encoded, payload.participants[index].log);
	}
	// Append the v4 consent bytes after the v3 snapshots. 255 is unknown on wire;
	// SQL uses NULL for that state, never this byte or the enum's ordinal.
	for (size_t index = 0; index < payload.participant_count; ++index)
		append_le<uint8_t>(
			encoded,
			payload.participants[index].webinfo_at_capture == combat_webinfo::unknown ?
				255 :
			payload.participants[index].webinfo_at_capture == combat_webinfo::on ? 1 :
											       0);
	if (payload.prepared_at)
	{
		append_le<int64_t>(encoded, payload.prepared_at);
		for (size_t index = 0; index < payload.participant_count; ++index)
		{
			const auto &entry = payload.participants[index];
			append_le<uint64_t>(encoded, entry.epic_boon_id);
			append_le<uint64_t>(encoded, std::bit_cast<uint64_t>(entry.epic_base));
			append_le<int32_t>(encoded, entry.epic_spill_blood);
		}
	}
	if (payload.artifact_intents)
	{
		append_le<uint16_t>(encoded, payload.artifact_deliveries.size());
		for (const auto &child : payload.artifact_deliveries)
		{
			std::vector<uint8_t> bytes;
			if (critical_command_encode(child, &bytes) !=
				    critical_command_codec_result::ok ||
			    bytes.size() > 2048)
				return false;
			append_le<uint16_t>(encoded, bytes.size());
			encoded->insert(encoded->end(), bytes.begin(), bytes.end());
		}
	}
	return encoded->size() <= CRITICAL_COMMAND_MAX_PAYLOAD_BYTES;
}

bool combat_outcome_command_decode_payload(const critical_command &command,
					   combat_outcome_payload *payload)
{
	if (!payload || command.type != critical_command_type::combat_outcome ||
	    command.payload_version < 1 ||
	    command.payload_version > COMBAT_OUTCOME_PAYLOAD_VERSION ||
	    command.payload.size() > CRITICAL_COMMAND_MAX_PAYLOAD_BYTES)
		return false;
	*payload = {};
	const uint8_t *cursor = command.payload.data();
	const uint8_t *end = cursor + command.payload.size();
	if (!read_le(&cursor, end, &payload->victim_pid) ||
	    !read_le(&cursor, end, &payload->room_vnum) ||
	    !read_string(&cursor, end, &payload->room_name) ||
	    !read_le(&cursor, end, &payload->participant_count) ||
	    payload->participant_count > payload->participants.size())
		return false;
	for (size_t index = 0; index < payload->participant_count; ++index)
	{
		auto &entry = payload->participants[index];
		uint8_t role = 0;
		if (!read_le(&cursor, end, &entry.pid) || !read_le(&cursor, end, &role) ||
		    !read_le(&cursor, end, &entry.flags) || !read_le(&cursor, end, &entry.level) ||
		    !read_le(&cursor, end, &entry.racewar) ||
		    !read_le(&cursor, end, &entry.frag_delta) ||
		    !read_le(&cursor, end, &entry.epic_delta) ||
		    !read_le(&cursor, end, &entry.wallet_delta_copper) ||
		    !read_le(&cursor, end, &entry.expected_frag_revision) ||
		    !read_le(&cursor, end, &entry.expected_epic_revision) ||
		    !read_le(&cursor, end, &entry.expected_wallet_revision) ||
		    !read_le(&cursor, end, &entry.expected_bank_revision) ||
		    !read_string(&cursor, end, &entry.account_name) ||
		    !read_string(&cursor, end, &entry.description))
			return false;
		entry.role = static_cast<combat_participant_role>(role);
	}
	// Version 1 payloads remain decodable, with an unknown ally count.
	if (command.payload_version >= 2 && !read_le(&cursor, end, &payload->killer_allies))
		return false;
	// Versions 1 and 2 did not capture presentation snapshots.
	if (command.payload_version >= 3)
		for (size_t index = 0; index < payload->participant_count; ++index)
			if (!read_text(&cursor, end, COMBAT_OUTCOME_EQUIPMENT_MAX_BYTES,
				       &payload->participants[index].equipment) ||
			    !read_text(&cursor, end, COMBAT_OUTCOME_LOG_MAX_BYTES,
				       &payload->participants[index].log))
				return false;
	if (command.payload_version >= 4)
		for (size_t index = 0; index < payload->participant_count; ++index)
		{
			uint8_t consent;
			if (!read_le(&cursor, end, &consent) ||
			    (consent != 0 && consent != 1 && consent != 255))
				return false;
			payload->participants[index].webinfo_at_capture =
				consent == 255 ? combat_webinfo::unknown :
				consent == 1   ? combat_webinfo::on :
						 combat_webinfo::off;
		}
	if (command.payload_version >= 5)
	{
		if (!read_le(&cursor, end, &payload->prepared_at))
			return false;
		for (size_t index = 0; index < payload->participant_count; ++index)
		{
			auto &entry = payload->participants[index];
			uint64_t base = 0;
			if (!read_le(&cursor, end, &entry.epic_boon_id) ||
			    !read_le(&cursor, end, &base) ||
			    !read_le(&cursor, end, &entry.epic_spill_blood))
				return false;
			entry.epic_base = std::bit_cast<double>(base);
		}
	}
	if (command.payload_version >= 6)
	{
		payload->artifact_intents = true;
		uint16_t count = 0;
		if (!read_le(&cursor, end, &count) || count > payload->participant_count)
			return false;
		for (size_t i = 0; i < count; ++i)
		{
			uint16_t size = 0;
			critical_command child;
			if (!read_le(&cursor, end, &size) || size > 2048 ||
			    static_cast<size_t>(end - cursor) < size ||
			    critical_command_decode(cursor, size, &child) !=
				    critical_command_codec_result::ok)
				return false;
			cursor += size;
			payload->artifact_deliveries.push_back(std::move(child));
		}
	}
	if (cursor != end || !valid(*payload))
		return false;
	critical_command expected = {};
	if (!combat_outcome_command_build(&expected, command.operation_id, *payload))
		return false;
	return expected.keys.size() == command.keys.size() &&
	       std::equal(expected.keys.begin(), expected.keys.end(), command.keys.begin(),
			  critical_entity_key_equal) &&
	       expected.expected_revisions.size() == command.expected_revisions.size() &&
	       std::equal(expected.expected_revisions.begin(), expected.expected_revisions.end(),
			  command.expected_revisions.begin(),
			  [](const auto &left, const auto &right) {
				  return critical_entity_key_equal(left.key, right.key) &&
					 left.revision == right.revision;
			  });
}

namespace
{
constexpr std::array<uint8_t, 8> prepared_result_magic = { 'D', 'B', 'C', 'O', 'M', 'B', '0', '5' };
constexpr size_t prepared_entry_size = 129;
constexpr size_t prepared_header_size = 32;

bool valid_delivery(const combat_outcome_result &result,
		    const combat_outcome_participant_result &row)
{
	if (!row.epic_delivery_flags)
		return !row.epic_delivery_previous && !row.epic_delivery_delta &&
		       !row.epic_boon_id && row.epic_base == 0 && !row.epic_spill_blood;
	return row.pid && result.victim_pid && result.prepared_at > 0 &&
	       (row.epic_delivery_flags & COMBAT_PARTICIPANT_DIVINE_EPIC) &&
	       !(row.epic_delivery_flags &
		 ~(COMBAT_PARTICIPANT_DIVINE_EPIC | COMBAT_PARTICIPANT_SPILL_BLOOD)) &&
	       row.epic_revision > row.epic_delivery_previous && row.epic_delivery_delta > 0 &&
	       row.epic_delivery_delta <= std::numeric_limits<int>::max() && row.epic_boon_id &&
	       std::isfinite(row.epic_base) && row.epic_base > 0 &&
	       (row.epic_spill_blood == 0 || row.epic_spill_blood == 500) &&
	       ((row.epic_spill_blood != 0) ==
		((row.epic_delivery_flags & COMBAT_PARTICIPANT_SPILL_BLOOD) != 0));
}
}

bool combat_outcome_command_encode_result(const combat_outcome_result &result,
					  std::array<uint8_t, COMBAT_OUTCOME_RESULT_BYTES> *encoded)
{
	if (!encoded || result.participant_count > result.participants.size())
		return false;
	static_assert(prepared_header_size +
			      COMBAT_OUTCOME_MAX_PARTICIPANTS * prepared_entry_size <=
		      COMBAT_OUTCOME_RESULT_BYTES);
	const bool prepared = result.prepared_at != 0;
	const size_t header = prepared ? prepared_header_size : 10;
	const size_t stride = prepared ? prepared_entry_size : 92;
	encoded->fill(0);
	if (prepared)
	{
		std::copy(prepared_result_magic.begin(), prepared_result_magic.end(),
			  encoded->begin());
		put_u64(encoded->data() + 8, result.event_id);
		for (size_t byte = 0; byte < 4; ++byte)
			(*encoded)[16 + byte] =
				static_cast<uint8_t>(result.victim_pid >> (byte * 8));
		put_u64(encoded->data() + 20, static_cast<uint64_t>(result.prepared_at));
		(*encoded)[30] = result.artifact_intents ? 1 : 0;
	}
	else
		put_u64(encoded->data(), result.event_id);
	const size_t count_offset = prepared ? 28 : 8;
	(*encoded)[count_offset] = static_cast<uint8_t>(result.participant_count);
	(*encoded)[count_offset + 1] = static_cast<uint8_t>(result.participant_count >> 8);
	for (size_t index = 0; index < result.participant_count; ++index)
	{
		const auto &entry = result.participants[index];
		if (!valid_delivery(result, entry))
			return false;
		uint8_t *row = encoded->data() + header + index * stride;
		for (size_t byte = 0; byte < 4; ++byte)
			row[byte] = static_cast<uint8_t>(entry.pid >> (byte * 8));
		put_u64(row + 4, static_cast<uint64_t>(entry.frags));
		put_u64(row + 12, static_cast<uint64_t>(entry.epics));
		put_u64(row + 20, static_cast<uint64_t>(entry.wallet_value));
		for (size_t denomination = 0; denomination < entry.bank.amount.size();
		     ++denomination)
			put_u64(row + 28 + denomination * 8,
				static_cast<uint64_t>(entry.bank.amount[denomination]));
		put_u64(row + 60, entry.frag_revision);
		put_u64(row + 68, entry.epic_revision);
		put_u64(row + 76, entry.wallet_revision);
		put_u64(row + 84, entry.bank_revision);
		if (prepared)
		{
			put_u64(row + 92, entry.epic_delivery_previous);
			put_u64(row + 100, static_cast<uint64_t>(entry.epic_delivery_delta));
			put_u64(row + 108, entry.epic_boon_id);
			put_u64(row + 116, std::bit_cast<uint64_t>(entry.epic_base));
			for (size_t byte = 0; byte < 4; ++byte)
				row[124 + byte] =
					static_cast<uint8_t>(entry.epic_spill_blood >> (byte * 8));
			row[128] = entry.epic_delivery_flags;
		}
	}
	return true;
}

bool combat_outcome_command_decode_result(const uint8_t *encoded, size_t size,
					  combat_outcome_result *result)
{
	if (!encoded || !result ||
	    (size != COMBAT_OUTCOME_RESULT_BYTES && size != COMBAT_OUTCOME_LEGACY_RESULT_BYTES))
		return false;
	const bool prepared =
		size == COMBAT_OUTCOME_RESULT_BYTES &&
		std::equal(prepared_result_magic.begin(), prepared_result_magic.end(), encoded);
	if (!prepared && size == COMBAT_OUTCOME_RESULT_BYTES &&
	    !std::all_of(encoded + COMBAT_OUTCOME_LEGACY_RESULT_BYTES, encoded + size,
			 [](uint8_t byte) { return byte == 0; }))
		return false;
	*result = {};
	result->event_id = get_u64(encoded + (prepared ? 8 : 0));
	const size_t count_offset = prepared ? 28 : 8;
	result->participant_count = encoded[count_offset] |
				    static_cast<uint16_t>(encoded[count_offset + 1]) << 8;
	if (result->participant_count > result->participants.size())
		return false;
	if (prepared)
	{
		for (size_t byte = 0; byte < 4; ++byte)
			result->victim_pid |= static_cast<uint32_t>(encoded[16 + byte])
					      << (byte * 8);
		result->prepared_at = static_cast<int64_t>(get_u64(encoded + 20));
		result->artifact_intents = encoded[30] == 1;
		if (encoded[30] > 1 || encoded[31])
			return false;
	}
	const size_t header = prepared ? prepared_header_size : 10;
	const size_t stride = prepared ? prepared_entry_size : 92;
	for (size_t index = 0; index < result->participant_count; ++index)
	{
		const uint8_t *row = encoded + header + index * stride;
		auto &entry = result->participants[index];
		for (size_t byte = 0; byte < 4; ++byte)
			entry.pid |= static_cast<uint32_t>(row[byte]) << (byte * 8);
		if (!entry.pid)
			return false;
		entry.frags = static_cast<int64_t>(get_u64(row + 4));
		entry.epics = static_cast<int64_t>(get_u64(row + 12));
		entry.wallet_value = static_cast<int64_t>(get_u64(row + 20));
		for (size_t denomination = 0; denomination < entry.bank.amount.size();
		     ++denomination)
			entry.bank.amount[denomination] =
				static_cast<int64_t>(get_u64(row + 28 + denomination * 8));
		entry.frag_revision = get_u64(row + 60);
		entry.epic_revision = get_u64(row + 68);
		entry.wallet_revision = get_u64(row + 76);
		entry.bank_revision = get_u64(row + 84);
		if (prepared)
		{
			entry.epic_delivery_previous = get_u64(row + 92);
			entry.epic_delivery_delta = static_cast<int64_t>(get_u64(row + 100));
			entry.epic_boon_id = get_u64(row + 108);
			entry.epic_base = std::bit_cast<double>(get_u64(row + 116));
			uint32_t spill = 0;
			for (size_t byte = 0; byte < 4; ++byte)
				spill |= static_cast<uint32_t>(row[124 + byte]) << (byte * 8);
			entry.epic_spill_blood = static_cast<int32_t>(spill);
			entry.epic_delivery_flags = row[128];
			if (!valid_delivery(*result, entry))
				return false;
		}
	}
	return !prepared || std::all_of(encoded + header + result->participant_count * stride,
					encoded + size, [](uint8_t byte) { return byte == 0; });
}

bool combat_outcome_command_build(critical_command *command, critical_operation_id operation_id,
				  const combat_outcome_payload &payload)
{
	if (!command || !valid(payload))
		return false;
	*command = { .schema_version = CRITICAL_COMMAND_SCHEMA_VERSION,
		     .operation_id = operation_id,
		     .type = critical_command_type::combat_outcome,
		     .payload_version = static_cast<uint16_t>(payload.artifact_intents ? 6 :
							      payload.prepared_at      ? 5 :
											 4),
		     .source_site = critical_source_site::combat,
		     .deadline_class = critical_deadline_class::terminal,
		     .accepted_at_usec = 0,
		     .keys = {},
		     .expected_revisions = {},
		     .payload = {} };
	for (size_t index = 0; index < payload.participant_count; ++index)
	{
		const auto &entry = payload.participants[index];
		const critical_entity_key player = { critical_entity_type::player, entry.pid };
		command->keys.push_back(player);
		command->expected_revisions.push_back({ player, entry.expected_frag_revision });
		if (entry.wallet_delta_copper)
		{
			critical_entity_key account = {};
			if (!currency_account_key(entry.account_name.data(), entry.racewar,
						  &account))
				return false;
			const auto existing = std::find_if(
				command->keys.begin(), command->keys.end(), [&](const auto &key)
				{ return critical_entity_key_equal(key, account); });
			if (existing == command->keys.end())
			{
				command->keys.push_back(account);
				command->expected_revisions.push_back(
					{ account, entry.expected_bank_revision });
			}
		}
	}
	for (const auto &child : payload.artifact_deliveries)
	{
		if (!artifact_guild_command_valid_delivery(child, operation_id))
			return false;
		for (const auto &key : child.keys)
			if (std::none_of(command->keys.begin(), command->keys.end(),
					 [&](const auto &prior)
					 { return critical_entity_key_equal(prior, key); }))
				command->keys.push_back(key);
	}
	if (!combat_outcome_command_encode_payload(payload, &command->payload))
		return false;
	std::sort(command->keys.begin(), command->keys.end(), critical_entity_key_less);
	std::sort(command->expected_revisions.begin(), command->expected_revisions.end(),
		  [](const auto &left, const auto &right)
		  { return critical_entity_key_less(left.key, right.key); });
	return command->keys.size() <= CRITICAL_COMMAND_MAX_KEYS;
}

bool divine_epic_delivery_from_combat(const critical_operation_id &operation,
				      const combat_outcome_result &result, size_t index,
				      divine_epic_delivery *delivery)
{
	if (!delivery || index >= result.participant_count ||
	    !valid_delivery(result, result.participants[index]))
		return false;
	const auto &row = result.participants[index];
	if (!(row.epic_delivery_flags & COMBAT_PARTICIPANT_DIVINE_EPIC))
		return false;
	divine_epic_delivery decoded = { operation,
					 row.pid,
					 result.victim_pid,
					 row.epic_revision,
					 row.epic_delivery_previous,
					 row.epic_boon_id,
					 row.epic_delivery_delta,
					 result.prepared_at,
					 row.epic_base,
					 row.epic_spill_blood };
	decoded.artifact_intents = result.artifact_intents;
	if (!divine_epic_delivery_valid(decoded))
		return false;
	*delivery = decoded;
	return true;
}
