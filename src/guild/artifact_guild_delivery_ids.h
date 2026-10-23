#ifndef ARTIFACT_GUILD_DELIVERY_IDS_H
#define ARTIFACT_GUILD_DELIVERY_IDS_H

#include "persistence/critical_command.h"

#include <algorithm>
#include <string>
#include <vector>

constexpr size_t ARTIFACT_GUILD_PENDING_MAX = 256;
using artifact_guild_delivery_ids = std::vector<std::array<uint8_t, CRITICAL_COMMAND_ID_BYTES>>;

// Existing catalogs predate incarnation IDs. A new guild receives a random ID
// in found_asc(), so reusing a deleted guild number cannot inherit its effects.
inline critical_operation_id artifact_guild_legacy_identity(uint32_t guild_id)
{
	critical_operation_id id{};
	id.bytes[0] = 'L';
	id.bytes[1] = 'G';
	id.bytes[2] = 'L';
	id.bytes[3] = 'D';
	for (size_t i = 0; i < sizeof(guild_id); ++i)
		id.bytes[12 + i] = static_cast<uint8_t>(guild_id >> (i * 8));
	return id;
}

inline bool artifact_guild_delivery_ids_valid(const artifact_guild_delivery_ids &ids)
{
	return ids.size() <= ARTIFACT_GUILD_PENDING_MAX && std::is_sorted(ids.begin(), ids.end()) &&
	       std::adjacent_find(ids.begin(), ids.end()) == ids.end() &&
	       (ids.empty() || std::any_of(ids.front().begin(), ids.front().end(),
					   [](uint8_t byte) { return byte != 0; }));
}

inline std::string artifact_guild_delivery_ids_hex(const artifact_guild_delivery_ids &ids)
{
	static constexpr char digits[] = "0123456789abcdef";
	std::string encoded;
	encoded.reserve(ids.size() * CRITICAL_COMMAND_ID_BYTES * 2);
	for (const auto &id : ids)
		for (uint8_t byte : id)
		{
			encoded += digits[byte >> 4];
			encoded += digits[byte & 15];
		}
	return encoded;
}

inline bool artifact_guild_delivery_ids_read_hex(const char *text, artifact_guild_delivery_ids *ids)
{
	if (!ids)
		return false;
	artifact_guild_delivery_ids decoded;
	const std::string encoded = text ? text : "";
	constexpr size_t width = CRITICAL_COMMAND_ID_BYTES * 2;
	if (encoded.size() % width || encoded.size() / width > ARTIFACT_GUILD_PENDING_MAX)
		return false;
	decoded.resize(encoded.size() / width);
	for (size_t i = 0; i < encoded.size(); ++i)
	{
		const char c = encoded[i];
		const int value = c >= '0' && c <= '9' ? c - '0' :
				  c >= 'a' && c <= 'f' ? c - 'a' + 10 :
				  c >= 'A' && c <= 'F' ? c - 'A' + 10 :
							 -1;
		if (value < 0)
			return false;
		auto &byte = decoded[i / width][(i % width) / 2];
		byte = static_cast<uint8_t>((byte << 4) | value);
	}
	if (!artifact_guild_delivery_ids_valid(decoded))
		return false;
	*ids = std::move(decoded);
	return true;
}

#endif
