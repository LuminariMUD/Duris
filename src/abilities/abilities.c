/****************************************************************************
 *
 *  File: abilities.c                                           Part of Duris
 *  Usage: shared ability rolls, fact formatting and the facts table
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-11-04
 *
 ****************************************************************************/

#include "abilities/abilities.h"
#include "core/prototypes.h"
#include "magic/spells.h"

#include <algorithm>
#include <cstdio>

// dice() raises a count or size below 1 to 1; number() accepts its bounds in either order.
static int lowest_dice(int count, int /*sides*/)
{
	return std::max(count, 1);
}

static int highest_dice(int count, int sides)
{
	return std::max(count, 1) * std::max(sides, 1);
}

static int lowest_number(int from, int to)
{
	return std::min(from, to);
}

static int highest_number(int from, int to)
{
	return std::max(from, to);
}

const Rolls live_rolls = { dice, number };
const Rolls lowest_rolls = { lowest_dice, lowest_number };
const Rolls highest_rolls = { highest_dice, highest_number };

std::string fact(const std::string &label, const std::string &text)
{
	return "  " + label + ": " + text + "\n";
}

std::string show(Range range)
{
	if (range.low == range.high)
		return std::to_string(range.low);
	return std::to_string(range.low) + "-" + std::to_string(range.high);
}

std::string seconds(int pulses)
{
	if (pulses == WAIT_SEC)
		return "1 second";
	char text[32];
	snprintf(text, sizeof(text), "%g seconds", pulses / static_cast<double>(WAIT_SEC));
	return text;
}

// Affect durations count ticks, one game hour each. An affect lasts into the tick it
// expires on, hence "about".
std::string game_hours(int ticks)
{
	char text[64];
	snprintf(text, sizeof(text), "%d game hour%s (about %g minutes)", ticks,
		 ticks == 1 ? "" : "s", ticks * SECS_PER_MUD_HOUR / 60.0);
	return text;
}

AbilityFacts ability_facts(int skill)
{
	switch (skill)
	{
	case SKILL_BASH:
		return bash_facts;
	case SPELL_FIREBALL:
		return fireball_facts;
	default:
		return nullptr;
	}
}
