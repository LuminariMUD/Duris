/****************************************************************************
 *
 *  File: collector_codec.h                                     Part of Duris
 *  Usage: collector codec interface and catalog type
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef DURIS_COLLECTOR_CODEC_H
#define DURIS_COLLECTOR_CODEC_H

#include "economy/collector_policy.h"

#include <array>
#include <cstddef>
#include <cstdint>
#include <vector>

namespace collector
{
// V1 is a fixed-width little-endian metadata format. Object payloads remain the
// transaction layer's responsibility and are deliberately not embedded here.
constexpr size_t encoded_record_bytes = 154;
constexpr uint32_t catalog_max_records = 262144;

struct catalog
{
	uint64_t revision = 0;
	uint64_t next_listing = 1;
	std::vector<record> records;
};

enum class codec_result : uint8_t
{
	ok = 0,
	invalid,
	malformed,
	unsupported_version,
	too_many_records,
	allocation_failure,
};

bool valid_catalog(const catalog &value);
codec_result record_encode(const record &entry, std::array<uint8_t, encoded_record_bytes> *encoded);
codec_result record_decode(const uint8_t *encoded, size_t size, record *entry);
}

#endif
