/****************************************************************************
 *
 *  File: flatfile_shopkeeper_repository.h                      Part of Duris
 *  Usage: flat-file shopkeeper repository types and interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef DURIS_FLATFILE_SHOPKEEPER_REPOSITORY_H
#define DURIS_FLATFILE_SHOPKEEPER_REPOSITORY_H

#include "player/player_snapshot.h"

#include <array>
#include <cstdint>
#include <string>
#include <vector>

struct flatfile_shopkeeper_affect_record
{
	int32_t type = 0;
	int32_t duration = 0;
	int32_t modifier = 0;
	int32_t location = 0;
	std::array<uint64_t, 5> bitvectors = {};
};

struct flatfile_shopkeeper_record
{
	uint32_t shop_id = 0;
	int32_t mob_vnum = 0;
	int32_t room_vnum = 0;
	int64_t saved_at = 0;
	uint64_t revision = 0;
	std::vector<flatfile_shopkeeper_affect_record> affects;
	std::vector<player_item_snapshot> items;
};

#endif
