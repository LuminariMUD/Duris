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

// Affect durations count ticks, one game hour each; -1 never wears off. affect_update()
// takes one off on each of the owner's ticks and removes the affect on the tick after it
// reaches 0, so an affect set to `ticks` lasts more than `ticks` and up to `ticks + 1`
// game hours.
std::string game_hours(int ticks)
{
	if (ticks == -1)
		return "permanent";
	const double minutes = PULSES_IN_TICK / static_cast<double>(WAIT_SEC) / 60.0;
	char text[96];
	if (ticks == 0)
		snprintf(text, sizeof(text), "up to 1 game hour (up to %.10g minutes)", minutes);
	else
		snprintf(text, sizeof(text), "%d-%d game hours (%.10g-%.10g minutes)", ticks,
			 ticks + 1, ticks * minutes, (ticks + 1) * minutes);
	return text;
}

// A real-time span for longer waits: "12 minutes", "1 minute 15 seconds".
std::string real_time(int pulses)
{
	const int total = pulses / WAIT_SEC;
	if (total < 60)
		return seconds(pulses);
	const int minutes = total / 60, rest = total % 60;
	std::string text = std::to_string(minutes) + (minutes == 1 ? " minute" : " minutes");
	if (rest)
		text += " " + std::to_string(rest) + (rest == 1 ? " second" : " seconds");
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

AbilityFacts innate_facts(int innate)
{
	switch (innate)
	{
	case INNATE_REFLECTION:
		return reflection_innate_facts;
	default:
		return nullptr;
	}
}
