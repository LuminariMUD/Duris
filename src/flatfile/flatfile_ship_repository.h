/****************************************************************************
 *
 *  File: flatfile_ship_repository.h                            Part of Duris
 *  Usage: flat-file ship repository types and interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef DURIS_FLATFILE_SHIP_REPOSITORY_H
#define DURIS_FLATFILE_SHIP_REPOSITORY_H

#include <array>
#include <cstdint>
#include <string>
#include <vector>

struct flatfile_ship_slot_record
{
	uint8_t slot_index = 0;
	int32_t slot_type = 0;
	int32_t item_index = 0;
	int32_t position = 0;
	int32_t timer = 0;
	std::array<int32_t, 5> values = {};
	bool operator==(const flatfile_ship_slot_record &) const = default;
};

// Missing legacy slot rows materialize through ShipSlot::clear() in both loaders.
inline flatfile_ship_slot_record flatfile_ship_empty_slot(uint8_t index)
{
	return { index, 0, -1, -1, 0, { -1, -1, -1, -1, -1 } };
}

struct flatfile_ship_crew_record
{
	int32_t crew_index = 0;
	int32_t sail_skill_milli = 0;
	int32_t guns_skill_milli = 0;
	int32_t repair_skill_milli = 0;
	int32_t sail_chief = 0;
	int32_t guns_chief = 0;
	int32_t repair_chief = 0;
	bool operator==(const flatfile_ship_crew_record &) const = default;
};

#endif
