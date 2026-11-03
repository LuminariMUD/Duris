// Engine doubles shared by the key-gate reset harnesses. Each harness includes
// this, then the Python runner inserts the production reset/timer functions.
// Doubles cover allocation, placement, RNG and unrelated engine services only.
#pragma once
#include <algorithm>
#include <cassert>
#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <memory>
#include <string>
#include <vector>
#include "core/defines.h"

constexpr int NOWHERE = -1, MAX_STRING_LENGTH = 8192, LOG_STATUS = 0, LOG_DEBUG = 1, LOG_MOB = 2,
	      LOG_OBJ = 3, LOG_FILE = 4, REAL = 0, DIFFICULTY_ZONE_REPOP = 0, PULSES_IN_TICK = 300;
struct Character;
struct Object;
using P_char = Character *;
using P_obj = Object *;
struct Object
{
	int R_num;
	unsigned long wear_flags = 0;
	int in_room = NOWHERE;
	P_obj in_obj = nullptr, contains = nullptr, next_content = nullptr;
};
struct Character
{
	int rnum = -1, in_room = NOWHERE, birthplace = 0;
	bool npc = true, alive = true, morph = false;
	P_char next = nullptr, next_in_room = nullptr;
	P_obj carrying = nullptr;
	P_obj equipment[CUR_MAX_WEAR + 1] = {};
};
struct Descriptor
{
	int connected = 0;
	P_char character = nullptr;
	Descriptor *next = nullptr;
};
using P_desc = Descriptor *;
struct room_direction_data
{
	int to_room, key;
	unsigned long exit_info;
};
struct Room
{
	int number, zone;
	P_char people = nullptr;
	P_obj contents = nullptr;
	room_direction_data *dir_option[NUM_EXITS] = {};
};
struct Index
{
	int virtual_number, number = 0, limit = 0;
	bool take = true;
};
struct Reset
{
	char command;
	int if_flag, arg1, arg2, arg3, arg4, arg5, arg6, arg7;
};
struct Zone
{
	int number = 0, lifespan = 5, lifespan_min = 5, lifespan_max = 5, age = 0, reset_mode = 1;
	const char *filename = "fixture", *name = "fixture";
	std::vector<Reset> cmd;
};
std::vector<Room> world;
std::vector<Index> mob_index, obj_index;
Zone zone_table[2];
std::vector<std::unique_ptr<Character>> characters;
std::vector<std::unique_ptr<Object>> objects;
std::vector<std::unique_ptr<room_direction_data>> exits;
P_char character_list = nullptr;
P_desc descriptor_list = nullptr;
int top_of_world = -1, fail_object = -1, births = 0, reschedules = 0;
const int rev_dir[NUM_EXITS] = { 2, 3, 0, 1, 5, 4 };
const char *equipment_types[CUR_MAX_WEAR + 1] = {};
struct Event
{
	unsigned long long due_tick, sequence;
	int element;
};
Event *current_nevent = nullptr;
unsigned long long ne_event_tick = 0;
int pulse = 0;

#define IS_NPC(ch) ((ch)->npc)
#define IS_MORPH(ch) ((ch)->npc && (ch)->morph)
#define IS_ALIVE(ch) ((ch) && (ch)->alive)
#define IS_SHOPKEEPER(ch) (false)
#define GET_RNUM(ch) ((ch)->rnum)
#define GET_BIRTHPLACE(ch) ((ch)->birthplace)
#define OBJ_VNUM(obj) (obj_index[(obj)->R_num].virtual_number)
#define IS_ARTIFACT(obj) (false)
#define ITEM_LOAD_CHECK(obj, value, chance) ((chance) == 100)
#define REMOVE_BIT(var, bit) ((var) &= ~(bit))
#define SET_BIT(var, bit) ((var) |= (bit))
#define IS_SET(var, bit) ((var) & (bit))
#define MAX(a, b) ((a) > (b) ? (a) : (b))

int number(int low, int)
{
	return low;
}
int get_property(const char *, int value)
{
	return value;
}
void logit(int, const char *, ...) {}
double difficulty_multiplier(int)
{
	return 1.0;
}
int difficulty_scale_int(int value, double)
{
	return value;
}
bool room_has_shopkeeper(int, int)
{
	return false;
}
int configured_shopkeeper_for_room(int, int)
{
	return -1;
}
bool is_replicated_shop(int)
{
	return false;
}
bool live_shopkeeper_for_identity(int)
{
	return false;
}
void bind_shopkeeper(P_char, int) {}
void apply_zone_modifier(P_char) {}
void enhance_on_npc_item_reset_skipped(P_char, P_obj) {}
int itemvalue(P_obj)
{
	return 0;
}
bool zone_reset_trace_enabled()
{
	return false;
}
void no_reset_zone_reset(int)
{
	assert(false);
}
template <class... Args> void add_event(Args...)
{
	++reschedules;
}

int real_room(int vnum)
{
	for (size_t i = 0; i < world.size(); ++i)
		if (world[i].number == vnum)
			return static_cast<int>(i);
	return -1;
}
int index_of(const std::vector<Index> &indexes, int vnum)
{
	for (size_t i = 0; i < indexes.size(); ++i)
		if (indexes[i].virtual_number == vnum)
			return static_cast<int>(i);
	return -1;
}
int real_mobile(int vnum)
{
	return index_of(mob_index, vnum);
}
int real_object(int vnum)
{
	return index_of(obj_index, vnum);
}
void add_index(std::vector<Index> &indexes, int vnum, bool take = true)
{
	indexes.push_back({ vnum, 0, 0, take });
}
void add_room(int vnum, int zone)
{
	world.push_back({ vnum, zone });
	top_of_world = static_cast<int>(world.size()) - 1;
}
void add_exit(int room, int direction, int target, int key, int flags)
{
	if (real_room(target) < 0)
		return;
	auto exit = std::make_unique<room_direction_data>();
	*exit = { real_room(target), key, (flags & 3) ? EX_ISDOOR : 0 };
	if ((flags & 3) == 3)
		exit->exit_info |= EX_PICKPROOF;
	world[real_room(room)].dir_option[direction] = exit.get();
	exits.push_back(std::move(exit));
}
void char_from_room(P_char mob)
{
	if (mob->in_room == NOWHERE)
		return;
	auto *link = &world[mob->in_room].people;
	while (*link && *link != mob)
		link = &(*link)->next_in_room;
	assert(*link == mob);
	*link = mob->next_in_room;
	mob->in_room = NOWHERE;
}
void char_to_room(P_char mob, int room, int)
{
	char_from_room(mob);
	mob->in_room = room;
	mob->next_in_room = world[room].people;
	world[room].people = mob;
}
P_char read_mobile(int rnum, int)
{
	auto mob = std::make_unique<Character>();
	mob->rnum = rnum;
	mob->next = character_list;
	character_list = mob.get();
	++mob_index[rnum].number;
	++births;
	characters.push_back(std::move(mob));
	return character_list;
}
P_obj read_object_for_creation(int rnum, int)
{
	if (obj_index[rnum].virtual_number == fail_object)
	{
		errno = ENOMEM;
		return nullptr;
	}
	auto item = std::make_unique<Object>();
	item->R_num = rnum;
	item->wear_flags = obj_index[rnum].take ? ITEM_TAKE : 0;
	auto result = item.get();
	++obj_index[rnum].number;
	objects.push_back(std::move(item));
	return result;
}
void unlink(P_obj *link, P_obj item)
{
	while (*link && *link != item)
		link = &(*link)->next_content;
	if (*link)
		*link = item->next_content;
}
void detach(P_obj item)
{
	if (item->in_room != NOWHERE)
		unlink(&world[item->in_room].contents, item);
	if (item->in_obj)
		unlink(&item->in_obj->contains, item);
	item->in_room = NOWHERE;
	item->in_obj = nullptr;
	for (auto &ch : characters)
	{
		for (auto &equipped : ch->equipment)
			if (equipped == item)
				equipped = nullptr;
		auto *link = &ch->carrying;
		while (*link && *link != item)
			link = &(*link)->next_content;
		if (*link)
			*link = item->next_content;
	}
	item->next_content = nullptr;
}
void extract_obj(P_obj item)
{
	while (item->contains)
		extract_obj(item->contains);
	detach(item);
	--obj_index[item->R_num].number;
	auto found = std::find_if(objects.begin(), objects.end(),
				  [item](auto &o) { return o.get() == item; });
	assert(found != objects.end());
	objects.erase(found);
}
void obj_to_char(P_obj item, P_char mob)
{
	detach(item);
	item->next_content = mob->carrying;
	mob->carrying = item;
}
void obj_to_room(P_obj item, int room)
{
	detach(item);
	item->in_room = room;
	item->next_content = world[room].contents;
	world[room].contents = item;
}
void obj_to_obj(P_obj item, P_obj container)
{
	detach(item);
	item->in_obj = container;
	item->next_content = container->contains;
	container->contains = item;
}
bool obj_can_nest(P_obj, P_obj)
{
	return true;
}
P_obj get_obj_in_list_num(int rnum, P_obj list)
{
	for (; list; list = list->next_content)
		if (list->R_num == rnum)
			return list;
	return nullptr;
}
// Like the engine's object_list, search newest objects first.
P_obj get_obj_num(int rnum)
{
	for (auto item = objects.rbegin(); item != objects.rend(); ++item)
		if ((*item)->R_num == rnum)
			return item->get();
	return nullptr;
}
P_obj unequip_char(P_char mob, int slot)
{
	auto item = mob->equipment[slot];
	mob->equipment[slot] = nullptr;
	return item;
}
void equip_char(P_char mob, P_obj item, int slot, int)
{
	detach(item);
	mob->equipment[slot] = item;
}
void extract_char(P_char mob)
{
	while (mob->carrying)
		extract_obj(mob->carrying);
	for (auto &item : mob->equipment)
		if (item)
			extract_obj(item);
	char_from_room(mob);
	auto *link = &character_list;
	while (*link != mob)
		link = &(*link)->next;
	*link = mob->next;
	--mob_index[mob->rnum].number;
	auto found = std::find_if(characters.begin(), characters.end(),
				  [mob](auto &c) { return c.get() == mob; });
	characters.erase(found);
}
void renumber_commands()
{
	for (auto &row : zone_table[1].cmd)
	{
		if (row.command == 'M')
		{
			row.arg1 = real_mobile(row.arg1);
			row.arg3 = real_room(row.arg3);
		}
		if (row.command == 'G' || row.command == 'E')
			row.arg1 = real_object(row.arg1);
		if (row.command == 'O')
		{
			row.arg1 = real_object(row.arg1);
			row.arg3 = real_room(row.arg3);
		}
		if (row.command == 'P')
		{
			row.arg1 = real_object(row.arg1);
			row.arg3 = real_object(row.arg3);
		}
		if (row.command == 'D')
			row.arg1 = real_room(row.arg1);
	}
}
