/****************************************************************************
 *
 *  File: collector_codec.c                                     Part of Duris
 *  Usage: encodes and decodes collector catalog records
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#include "economy/collector_codec.h"

#include <algorithm>
#include <cstring>
#include <new>
#include <type_traits>
#include <utility>

namespace collector
{
namespace
{
template <typename T>
bool put(std::array<uint8_t, encoded_record_bytes> *output, size_t *offset, T value)
{
	if (!output || !offset || *offset > output->size() || output->size() - *offset < sizeof(T))
		return false;
	using unsigned_type = std::make_unsigned_t<T>;
	const unsigned_type bits = static_cast<unsigned_type>(value);
	for (size_t byte = 0; byte < sizeof(T); ++byte)
		(*output)[(*offset)++] = static_cast<uint8_t>(bits >> (byte * 8));
	return true;
}

struct reader
{
	const uint8_t *cursor;
	const uint8_t *end;

	template <typename T> bool get(T *value)
	{
		if (!value || !cursor || !end || end - cursor < static_cast<ptrdiff_t>(sizeof(T)))
			return false;
		using unsigned_type = std::make_unsigned_t<T>;
		unsigned_type bits = 0;
		for (size_t byte = 0; byte < sizeof(T); ++byte)
			bits |= static_cast<unsigned_type>(cursor[byte]) << (byte * 8);
		cursor += sizeof(T);
		*value = static_cast<T>(bits);
		return true;
	}
};

int hexadecimal(unsigned char value)
{
	if (value >= '0' && value <= '9')
		return value - '0';
	if (value >= 'a' && value <= 'f')
		return value - 'a' + 10;
	return -1;
}

bool put_operation(std::array<uint8_t, encoded_record_bytes> *output, size_t *offset,
		   const death_operation_id &operation)
{
	for (size_t byte = 0; byte < 16; ++byte)
	{
		const int high = hexadecimal(operation[byte * 2]);
		const int low = hexadecimal(operation[byte * 2 + 1]);
		if (high < 0 || low < 0 || !put<uint8_t>(output, offset, (high << 4) | low))
			return false;
	}
	return true;
}

bool get_operation(reader *input, death_operation_id *operation)
{
	if (!input || !operation)
		return false;
	constexpr char hexadecimal_digits[] = "0123456789abcdef";
	for (size_t byte = 0; byte < 16; ++byte)
	{
		uint8_t value = 0;
		if (!input->get(&value))
			return false;
		(*operation)[byte * 2] = hexadecimal_digits[value >> 4];
		(*operation)[byte * 2 + 1] = hexadecimal_digits[value & 0xf];
	}
	(*operation)[death_operation_hex_size] = '\0';
	return true;
}

bool listings_are_canonical(const std::vector<record> &records, uint64_t next_listing)
{
	if (!next_listing)
		return false;
	for (size_t index = 0; index < records.size(); ++index)
		if (records[index].listing >= next_listing ||
		    (index && records[index - 1].listing >= records[index].listing))
			return false;
	return true;
}
}

bool valid_catalog(const catalog &value)
{
	return value.records.size() <= catalog_max_records &&
	       listings_are_canonical(value.records, value.next_listing) &&
	       std::all_of(value.records.begin(), value.records.end(), valid_record);
}

codec_result record_encode(const record &entry, std::array<uint8_t, encoded_record_bytes> *encoded)
{
	if (!encoded)
		return codec_result::invalid;
	if (entry.version != record_version)
		return codec_result::unsupported_version;
	if (!valid_record(entry))
		return codec_result::invalid;
	std::array<uint8_t, encoded_record_bytes> candidate = {};
	size_t offset = 0;
	if (!put(&candidate, &offset, entry.version) || !put(&candidate, &offset, entry.listing) ||
	    !put_operation(&candidate, &offset, entry.death_operation) ||
	    !put(&candidate, &offset, entry.beneficiary) || !put(&candidate, &offset, entry.uid) ||
	    !put(&candidate, &offset, entry.death_time) ||
	    !put(&candidate, &offset, entry.collect_at) ||
	    !put(&candidate, &offset, entry.sale_at) ||
	    !put(&candidate, &offset, entry.available_at) ||
	    !put(&candidate, &offset, entry.expires_at) ||
	    !put<uint8_t>(&candidate, &offset, entry.holding_paused ? 1 : 0) ||
	    !put(&candidate, &offset, entry.paused_at) ||
	    !put(&candidate, &offset, entry.revision) ||
	    !put(&candidate, &offset, entry.item_revision) ||
	    !put(&candidate, &offset, entry.price_value) ||
	    !put<uint8_t>(&candidate, &offset, entry.policy.enabled ? 1 : 0) ||
	    !put(&candidate, &offset, entry.policy.collection_delay) ||
	    !put(&candidate, &offset, entry.policy.sale_delay) ||
	    !put(&candidate, &offset, entry.policy.holding_duration) ||
	    !put(&candidate, &offset, entry.policy.price_percent) ||
	    !put(&candidate, &offset, entry.policy.minimum_value) ||
	    !put<uint8_t>(&candidate, &offset, static_cast<uint8_t>(entry.status)) ||
	    !put<uint8_t>(&candidate, &offset, static_cast<uint8_t>(entry.closed_reason)) ||
	    offset != candidate.size())
		return codec_result::invalid;
	*encoded = candidate;
	return codec_result::ok;
}

codec_result record_decode(const uint8_t *encoded, size_t size, record *entry)
{
	if (!entry)
		return codec_result::invalid;
	if (!encoded || size != encoded_record_bytes)
		return codec_result::malformed;
	reader input{ encoded, encoded + size };
	record candidate;
	uint8_t paused = 0, enabled = 0, status = 0, closed_reason = 0;
	if (!input.get(&candidate.version))
		return codec_result::malformed;
	if (candidate.version != record_version)
		return codec_result::unsupported_version;
	if (!input.get(&candidate.listing) || !get_operation(&input, &candidate.death_operation) ||
	    !input.get(&candidate.beneficiary) || !input.get(&candidate.uid) ||
	    !input.get(&candidate.death_time) || !input.get(&candidate.collect_at) ||
	    !input.get(&candidate.sale_at) || !input.get(&candidate.available_at) ||
	    !input.get(&candidate.expires_at) || !input.get(&paused) || paused > 1 ||
	    !input.get(&candidate.paused_at) || !input.get(&candidate.revision) ||
	    !input.get(&candidate.item_revision) || !input.get(&candidate.price_value) ||
	    !input.get(&enabled) || enabled > 1 || !input.get(&candidate.policy.collection_delay) ||
	    !input.get(&candidate.policy.sale_delay) ||
	    !input.get(&candidate.policy.holding_duration) ||
	    !input.get(&candidate.policy.price_percent) ||
	    !input.get(&candidate.policy.minimum_value) || !input.get(&status) ||
	    !input.get(&closed_reason) || input.cursor != input.end)
		return codec_result::malformed;
	candidate.holding_paused = paused != 0;
	candidate.policy.enabled = enabled != 0;
	candidate.status = static_cast<state>(status);
	candidate.closed_reason = static_cast<reason>(closed_reason);
	if (!valid_record(candidate))
		return codec_result::invalid;
	*entry = candidate;
	return codec_result::ok;
}
}
