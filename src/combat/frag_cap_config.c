/****************************************************************************
 *
 *  File: frag_cap_config.c                                     Part of Duris
 *  Usage: loads the frag cap configuration from properties
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
#include "core/config.h"
#include "combat/frag_cap_config.h"

#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static const struct frag_cap_config defaults = { 25, 30, 56, 3, 5, 10, 2 };

static struct frag_cap_config active;
static bool config_initialized;

static void reset_to_defaults(void)
{
	active = defaults;
	config_initialized = true;
}

static bool parse_long_value(const char *text, long *result)
{
	char *end;
	long value;
	errno = 0;
	value = strtol(text, &end, 10);
	if (errno || end == text || *end != '\0')
		return false;
	*result = value;
	return true;
}

static void set_int(const char *key, const char *value, int *field, int low, int high)
{
	long parsed;
	if (!parse_long_value(value, &parsed) || parsed < low || parsed > high)
	{
		logit(LOG_STATUS, "Invalid frag-cap config value %s=%s; retaining default.", key,
		      value);
		return;
	}
	*field = (int)parsed;
}

static void apply_value(const char *key, const char *value)
{
#define INT_KEY(name, field, low, high)                        \
	if (!strcmp(key, name))                                \
	{                                                      \
		set_int(key, value, &active.field, low, high); \
		return;                                        \
	}

	INT_KEY("cap.floor.level", cap_floor_level, 1, MAXLVLMORTAL)
	INT_KEY("cap.reset.level", cap_reset_level, 1, MAXLVLMORTAL)
	INT_KEY("cap.maximum.level", cap_maximum_level, 1, MAXLVLMORTAL)
	INT_KEY("timer.unlock.days", unlock_timer_days, 0, 3650)
	INT_KEY("unlock.victim.levels.below.open", unlock_victim_levels_below, 0, MAXLVLMORTAL)
	INT_KEY("unlock.minimum.frag.points", unlock_minimum_frag_points, 1, 100)
	INT_KEY("hardcore.levels.beyond.cap", hardcore_levels_beyond_cap, 0, 56)

#undef INT_KEY
	logit(LOG_STATUS, "Unknown frag-cap config key: %s", key);
}

void boot_frag_cap_config(void)
{
	FILE *fp;
	char line[256], key[128], value[128];

	reset_to_defaults();
	fp = fopen("lib/frag_cap.cfg", "r");
	if (!fp)
	{
		logit(LOG_STATUS, "Frag-cap config unavailable; using compiled defaults.");
		return;
	}

	while (fgets(line, sizeof(line), fp))
	{
		if (line[0] == '#' || line[0] == '\n')
			continue;
		if (sscanf(line, " %127[^=]= %127s", key, value) != 2)
		{
			logit(LOG_STATUS, "Ignoring malformed frag-cap config line: %s", line);
			continue;
		}
		apply_value(key, value);
	}
	fclose(fp);

	if (active.cap_floor_level > active.cap_reset_level ||
	    active.cap_reset_level > active.cap_maximum_level)
	{
		logit(LOG_STATUS, "Invalid frag-cap level ordering; restoring level defaults.");
		active.cap_floor_level = defaults.cap_floor_level;
		active.cap_reset_level = defaults.cap_reset_level;
		active.cap_maximum_level = defaults.cap_maximum_level;
	}

	logit(LOG_STATUS,
	      "Loaded frag-cap config: floor %d, reset %d, ceiling %d, unlock timer %d days, unlock victim at most %d levels below the open cap, minimum individual frag gain %d points, hardcore allowance %d.",
	      active.cap_floor_level, active.cap_reset_level, active.cap_maximum_level,
	      active.unlock_timer_days, active.unlock_victim_levels_below,
	      active.unlock_minimum_frag_points, active.hardcore_levels_beyond_cap);
}

const struct frag_cap_config *frag_cap_config_get(void)
{
	if (!config_initialized)
		reset_to_defaults();
	return &active;
}

int frag_cap_config_reset_level(void)
{
	return frag_cap_config_get()->cap_reset_level;
}

int frag_cap_config_hardcore_level_cap(int normal_cap)
{
	int level_cap = normal_cap + frag_cap_config_get()->hardcore_levels_beyond_cap;
	return (level_cap > MAXLVLMORTAL) ? MAXLVLMORTAL : level_cap;
}
