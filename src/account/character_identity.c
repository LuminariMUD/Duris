/****************************************************************************
 *
 *  File: character_identity.c                                  Part of Duris
 *  Usage: runtime character ids and lookup
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#include "core/prototypes.h"

#include <unordered_map>

extern P_char character_list;

static uint64_t next_runtime_id = 0;
static std::unordered_map<uint64_t, P_char> live_characters;

uint64_t allocate_character_runtime_id()
{
	const uint64_t runtime_id = ++next_runtime_id;

	if (!runtime_id)
		panic_corruption("character", "process-local character identity exhausted");
	return runtime_id;
}

P_char find_character_by_runtime_id(uint64_t runtime_id)
{
	const auto found = live_characters.find(runtime_id);

	return found == live_characters.end() ? NULL : found->second;
}

void character_list_add(P_char character)
{
	if (character->runtime_id)
		live_characters[character->runtime_id] = character;
	character->next = character_list;
	character_list = character;
}

void forget_live_character(P_char character)
{
	live_characters.erase(character->runtime_id);
}
