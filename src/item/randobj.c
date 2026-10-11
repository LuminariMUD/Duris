/****************************************************************************
 *
 *  File: randobj.c                                             Part of Duris
 *  Usage: randobj, the staff command that makes random items, mobs and zones
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
#include "core/structs.h"
#include "net/comm.h"
#include "world/db.h"
#include "cmd/interp.h"
#include "core/utils.h"
#include "economy/tradeskill.h"
#include "item/random_equipment.h"
#include "world/vnum.obj.h"
#include <string>

extern P_index obj_index;

void create_zone(int theme, int map_room1, int map_room2, int level_range, int rooms);

extern flagDef wear_bits[];

static void usage(P_char ch, const char *syntax)
{
	send_to_char_f(ch, "Syntax: randobj %s\r\n", syntax);
}

static bool has_arguments(const char *arguments)
{
	if (!arguments)
		return false;
	while (isspace(static_cast<unsigned char>(*arguments)))
		arguments++;
	return *arguments != '\0';
}

// lohrr_chop keeps every word: one_argument would silently discard "with", "at", etc.
static bool read_number(char *&arguments, int &value, int minimum, int maximum)
{
	if (!has_arguments(arguments))
		return true;
	char word[MAX_INPUT_LENGTH];
	arguments = lohrr_chop(arguments, word);
	if (!*word)
		return false;
	int parsed = 0;
	for (const char *p = word; *p; p++)
	{
		if (*p < '0' || *p > '9')
			return false;
		parsed = parsed * 10 + (*p - '0');
		// Checking each digit also rejects arbitrarily large integers without overflow.
		if (parsed > maximum)
			return false;
	}
	if (parsed < minimum)
		return false;
	value = parsed;
	return true;
}

static bool read_options(char *arguments, int *level, int minimum_level, int &count,
			 int maximum_count)
{
	return (!level || read_number(arguments, *level, minimum_level, 62)) &&
	       read_number(arguments, count, 1, maximum_count) && !has_arguments(arguments);
}

static std::string slot_word(const char *name)
{
	std::string word = strip_ansi(name);
	for (char &c : word)
		c = c == ' ' ? '-' : tolower(static_cast<unsigned char>(c));
	return word;
}

static std::string wear_word(int bit)
{
	const char *name = wear_bits[bit].flagShort;
	if (!strncmp(name, "WEAR_", 5))
		name += 5;
	return slot_word(name);
}

static bool resolve_slots(const char *word, int *slots, int &count)
{
	count = 0;
	if (!strcmp(word, "any"))
		return true;
	for (int bit = 0; wear_bits[bit].flagShort; bit++)
		if (wear_word(bit) == word)
		{
			for (int i = 0; i < MAX_SLOT; i++)
				if (static_cast<unsigned>(slot_data[i].wear_bit) == (1U << bit))
					slots[count++] = i;
			return count != 0;
		}
	for (int i = 0; i < MAX_SLOT; i++)
		if (slot_word(slot_data[i].m_name) == word)
			slots[count++] = i;
	return count != 0;
}

static void list_slots(P_char ch)
{
	send_to_char("Equipment slots (or 'any' for the usual weighted choice):\r\n", ch);
	for (int bit = 0; wear_bits[bit].flagShort; bit++)
	{
		std::string nouns;
		for (int i = 0; i < MAX_SLOT; i++)
			if (static_cast<unsigned>(slot_data[i].wear_bit) == (1U << bit))
				nouns += " " + slot_word(slot_data[i].m_name);
		if (!nouns.empty())
			send_to_char_f(ch, "%s:%s\r\n", wear_word(bit).c_str(), nouns.c_str());
	}
}

static bool give_item(P_char ch, P_obj obj, int level, bool multiple)
{
	if (!obj)
	{
		send_to_char("Failed to create item; stopped.\r\n", ch);
		return false;
	}
	obj_to_char(obj, ch);
	if (multiple)
	{
		if (level)
			send_to_char_f(ch, "%s (level %d)\r\n", obj->short_description, level);
		else
			send_to_char_f(ch, "%s\r\n", obj->short_description);
	}
	return true;
}

static void randobj_eq(P_char ch, char *arguments)
{
	const char *syntax = "eq [slot] [level] [count] | eq list";
	char word[MAX_INPUT_LENGTH];
	char *after = lohrr_chop(arguments, word);
	if (!strcmp(word, "list"))
	{
		if (has_arguments(after))
			return usage(ch, syntax);
		return list_slots(ch);
	}
	int slots[MAX_SLOT], slot_count = 0;
	if (*word && !is_number(word))
	{
		if (!resolve_slots(word, slots, slot_count))
			return usage(ch, syntax);
		arguments = after;
	}
	int level = GET_LEVEL(ch), count = 1;
	if (!read_options(arguments, &level, 1, count, 50))
		return usage(ch, syntax);
	for (int i = 0; i < count; i++)
	{
		int slot = slot_count ? slots[slot_count == 1 ? 0 : number(0, slot_count - 1)] : -1;
		P_obj obj = create_random_eq(ch, level, level, slot, -1);
		if (!give_item(ch, obj, level, count > 1))
			return;
		if (count == 1)
		{
			char argument[] = "o";
			do_stat(ch, argument, CMD_STAT, obj);
		}
	}
	if (count > 1)
		send_to_char_f(ch, "Created %d equipment items.\r\n", count);
}

static void randobj_piece(P_char ch, char *arguments)
{
	int level = GET_LEVEL(ch), count = 1;
	if (!read_options(arguments, &level, 1, count, 50))
		return usage(ch, "piece [level] [count]");
	for (int i = 0; i < count; i++)
		if (!give_item(ch, create_material(ch, level, level), level, count > 1))
			return;
	if (count > 1)
		send_to_char_f(ch, "Created %d materials.\r\n", count);
}

static void randobj_stone(P_char ch, char *arguments)
{
	int count = 1;
	if (!read_options(arguments, nullptr, 0, count, 50))
		return usage(ch, "stone [count]");
	for (int i = 0; i < count; i++)
		if (!give_item(ch, create_stones(), 0, count > 1))
			return;
	if (count > 1)
		send_to_char_f(ch, "Created %d stones.\r\n", count);
}

static void randobj_recipe(P_char ch, char *arguments)
{
	int count = 1;
	if (!read_options(arguments, nullptr, 0, count, 50))
		return usage(ch, "recipe [count]");
	int created = 0;
	for (int i = 0; i < count; i++)
	{
		P_obj obj = random_zone_item(ch);
		if (!obj)
			return send_to_char("Failed creating random zone item; stopped.\r\n", ch);
		int vnum = obj_index[obj->R_num].virtual_number;
		if (vnum == VOBJ_RANDOM_ARMOR || vnum == VOBJ_RANDOM_THRUSTED ||
		    vnum == VOBJ_RANDOM_WEAPON)
		{
			act("Created random object: $q.  Deleting it.", FALSE, ch, obj, NULL,
			    TO_CHAR);
			extract_obj(obj);
			continue;
		}
		if (create_recipe(ch, obj))
		{
			created++;
			if (count > 1)
				send_to_char_f(ch, "Recipe for %s\r\n", obj->short_description);
		}
		extract_obj(obj);
	}
	if (count > 1)
		send_to_char_f(ch, "Created %d recipes.\r\n", created);
}

static void randobj_mob(P_char ch, char *arguments)
{
	int level = 0, count = 1;
	if (!read_options(arguments, &level, 0, count, 10) || level > 61)
		return usage(ch, "mob [level] [count] (level 0-61; 0 chooses automatically)");
	for (int i = 0; i < count; i++)
	{
		P_char mob = create_random_mob(-1, level);
		if (!mob)
			return send_to_char("Failed to create mob; stopped.\r\n", ch);
		send_to_char_f(ch, "Created mob: %s (level %d)\r\n", GET_NAME(mob), GET_LEVEL(mob));
	}
	if (count > 1)
		send_to_char_f(ch, "Created %d mobs.\r\n", count);
}

static void randobj_encrust(P_char ch, char *arguments)
{
	int count = 10;
	if (!read_options(arguments, nullptr, 0, count, 50))
		return usage(ch, "encrust [count]");
	for (int i = 0; i < count; i++)
	{
		P_obj obj = random_zone_item(ch);
		if (!obj)
			return send_to_char("Failed to create item; stopped.\r\n", ch);
		obj->affected[2].location = APPLY_MOVE_REG;
		describe_encrusted_enhanced(obj);
		send_to_char_f(ch, "%s\r\n", obj->short_description);
		extract_obj(obj);
	}
	if (count > 1)
		send_to_char_f(ch, "Created %d sample encrusted names.\r\n", count);
}

void do_randobj(P_char ch, char *arguments, int /*val*/)
{
	if (!IS_TRUSTED(ch))
		return send_to_char("Bad mortal or mob.. bad!.\r\n", ch);
	char command[MAX_INPUT_LENGTH];
	arguments = lohrr_chop(arguments, command);
	if (!strcmp(command, "eq"))
		return randobj_eq(ch, arguments);
	if (!strcmp(command, "piece"))
		return randobj_piece(ch, arguments);
	if (!strcmp(command, "stone"))
		return randobj_stone(ch, arguments);
	if (!strcmp(command, "recipe"))
		return randobj_recipe(ch, arguments);
	if (!strcmp(command, "mob"))
		return randobj_mob(ch, arguments);
	if (!strcmp(command, "encrust"))
		return randobj_encrust(ch, arguments);
	if (!has_arguments(arguments))
	{
		if (!strcmp(command, "remove"))
		{
			reset_lab(0);
			reset_lab(1);
			reset_lab(2);
			return wizlog(56, "Reset map random");
		}
		if (!strcmp(command, "map"))
		{
			create_lab(0);
			create_lab(1);
			create_lab(2);
			return wizlog(56, "Created map random");
		}
		if (!strcmp(command, "zone"))
			return create_zone(number(0, 2), 999, 999, 999, 999);
	}
	send_to_char(
		"Syntax: randobj eq [slot] [level] [count] | eq list\r\n"
		"               piece [level] [count] | stone [count] | recipe [count]\r\n"
		"               mob [level] [count] | encrust [count] | zone | map | remove\r\n"
		"Levels: 1-62 (mob: 0 for automatic). Counts: 1-50 (mobs: 1-10).\r\n"
		"Defaults: any slot, your level, count 1; mob level 0, encrust count 10.\r\n",
		ch);
}
