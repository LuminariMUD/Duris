// Production reset/timer functions are inserted by the Python runner.
// Doubles cover allocation, placement, RNG and unrelated engine services only.
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
	P_obj next_content = nullptr;
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
	room_direction_data *dir_option[NUM_EXITS] = {};
};
struct Index
{
	int virtual_number, number = 0, limit = 0;
};
struct Reset
{
	char command;
	int if_flag, arg1, arg2, arg3, arg4, arg5, arg6, arg7;
};
struct Zone
{
	int number = 24, lifespan = 5, lifespan_min = 5, lifespan_max = 5, age = 0, reset_mode = 1;
	const char *filename = "castle", *name = "castle";
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
void add_index(std::vector<Index> &indexes, int vnum)
{
	indexes.push_back({ vnum });
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
	auto result = item.get();
	++obj_index[rnum].number;
	objects.push_back(std::move(item));
	return result;
}
void detach(P_obj item)
{
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
		if (row.command == 'D')
			row.arg1 = real_room(row.arg1);
	}
}

// PRODUCTION

struct Gate
{
	int key, mob, home, near, direction, far, slot;
};
const Gate gates[] = {
	{ 2405, 2406, 2427, 2414, 5, 2415, 18 }, { 2418, 2415, 2439, 2427, 4, 2428, 0 },
	{ 2422, 2418, 2452, 2446, 3, 2448, 0 },	 { 2425, 2419, 2456, 2460, 4, 2461, 18 },
	{ 2436, 2433, 2481, 2471, 0, 2479, 0 },	 { 2437, 2420, 2477, 2480, 0, 2488, 4 },
	{ 2438, 2428, 2493, 2480, 2, 2498, 18 }
};
// FIXTURE

P_char carrier(const Gate &gate)
{
	for (auto &mob : characters)
		if (mob->npc && mob->rnum == real_mobile(gate.mob))
			return mob.get();
	return nullptr;
}
P_obj key_on(P_char mob, int key)
{
	for (auto item : mob->equipment)
		if (item && OBJ_VNUM(item) == key)
			return item;
	for (auto item = mob->carrying; item; item = item->next_content)
		if (OBJ_VNUM(item) == key)
			return item;
	return nullptr;
}
room_direction_data *door(int room, int direction)
{
	return world[real_room(room)].dir_option[direction];
}
void check_pair(const Gate &gate, bool locked)
{
	for (auto exit :
	     { door(gate.near, gate.direction), door(gate.far, rev_dir[gate.direction]) })
	{
		assert(IS_SET(exit->exit_info, EX_ISDOOR) && IS_SET(exit->exit_info, EX_CLOSED));
		assert(IS_SET(exit->exit_info, EX_PICKPROOF));
		assert(!!IS_SET(exit->exit_info, EX_LOCKED) == locked);
		assert(!!IS_SET(exit->exit_info, EX_SECRET) == (locked && gate.key == 2436));
	}
}
void held_sequence(const Gate &gate)
{
	// A live off-carrier copy suppresses E/G on the newly spawned carrier.
	auto held = read_object_for_creation(real_object(gate.key), REAL);
	reset_zone(1, 0);
	auto mob = carrier(gate);
	assert(mob && !key_on(mob, gate.key));
	assert(obj_index[real_object(gate.key)].number == 1);
	const bool initially_unlocked =
		!IS_SET(door(gate.near, gate.direction)->exit_info, EX_LOCKED);
	// Model successful consumption; actual commands/dirty saves run in the socket journey.
	extract_obj(held);
	const int prior_births = births;
	const auto prior_objects = objects.size();
	std::vector<P_obj> prior_object_ids;
	for (const auto &item : objects)
		prior_object_ids.push_back(item.get());
	for (int repeat = 0; repeat < 3; ++repeat)
	{
		reset_zone(1, 0);
		assert(carrier(gate) == mob && !key_on(mob, gate.key));
		assert(obj_index[real_object(gate.key)].number == 0);
		assert(births == prior_births && objects.size() == prior_objects);
		for (size_t i = 0; i < objects.size(); ++i)
			assert(objects[i].get() == prior_object_ids[i]);
		check_pair(gate, false);
	}
	assert(initially_unlocked);
	extract_char(mob);
	reset_zone(1, 0);
	assert(key_on(carrier(gate), gate.key));
	check_pair(gate, true);
}
void controls()
{
	reset_zone(1, 2);
	for (const auto &gate : gates)
	{
		assert(key_on(carrier(gate), gate.key));
		check_pair(gate, true);
	}
	assert(OBJ_VNUM(carrier(gates[5])->equipment[4]) == 2437);
	assert(OBJ_VNUM(carrier(gates[5])->equipment[HOLD]) != 2437);
	const auto count = objects.size();
	const auto born = births;
	reset_zone(1, 0);
	assert(objects.size() == count && births == born);
	for (const auto &gate : gates)
		check_pair(gate, true);
	for (const auto &gate : gates)
	{
		const auto case_count = objects.size();
		const auto case_births = births;
		auto mob = carrier(gate);
		auto item = key_on(mob, gate.key);
		detach(item); // held/corpse/container copies all remain live but off the carrier
		reset_zone(1, 0);
		check_pair(gate, false);
		assert(objects.size() == case_count && births == case_births);
		obj_to_char(item, mob);
		reset_zone(1, 0);
		check_pair(gate, true); // inventory counts as well as its authored equipment slot
		char_to_room(mob, real_room(5760), -2);
		reset_zone(1, 0);
		check_pair(gate, false);
		char_to_room(mob, real_room(gate.home), -2);
		reset_zone(1, 0);
		check_pair(gate, true);
		extract_char(mob);
		fail_object = gate.key;
		reset_zone(1, 0);
		check_pair(gate, false);
		assert(carrier(gate) && !key_on(carrier(gate), gate.key));
		fail_object = -1;
		extract_char(carrier(gate));
		reset_zone(1, 0);
		check_pair(gate, true);
	}
}
P_char player(int room)
{
	auto ch = std::make_unique<Character>();
	ch->npc = false;
	ch->next = character_list;
	character_list = ch.get();
	characters.push_back(std::move(ch));
	char_to_room(character_list, real_room(room), -2);
	return character_list;
}
void occupancy()
{
	reset_zone(1, 0);
	auto pc = player(2415);
	Descriptor descriptor{ 0, pc, nullptr };
	descriptor_list = &descriptor;
	int zone = 1;
	zone_table[zone].age = zone_table[zone].lifespan;
	const int born = births;
	event_reset_zone(nullptr, nullptr, nullptr, &zone);
	assert(zone_table[zone].age == 6 && births == born && reschedules == 1);
	for (const auto &gate : gates)
		check_pair(gate, true);
	descriptor_list = nullptr; // linkdead body still in the zone
	event_reset_zone(nullptr, nullptr, nullptr, &zone);
	assert(zone_table[zone].age == 0 && births == born && reschedules == 2);
	for (const auto &gate : gates)
		check_pair(gate, false);
	assert(!IS_SET(door(2401, 0)->exit_info, EX_LOCKED));
	assert(!IS_SET(door(2402, 2)->exit_info, EX_LOCKED));
	descriptor_list = &descriptor;
	reset_zone(1, 0); // staff zreset ok bypasses the timer admission
	for (const auto &gate : gates)
		check_pair(gate, false);
	char_to_room(pc, real_room(5760), -2);
	zone_table[zone].age = zone_table[zone].lifespan;
	event_reset_zone(nullptr, nullptr, nullptr, &zone);
	assert(zone_table[zone].age == 0);
	for (const auto &gate : gates)
		check_pair(gate, true);
	assert(IS_SET(door(2402, 2)->exit_info, EX_LOCKED));
	// A morphed player's visible body is an NPC; the original PC is in limbo.
	char_to_room(pc, real_room(2415), -2);
	pc->npc = pc->morph = true;
	descriptor_list = nullptr;
	zone_table[zone].age = zone_table[zone].lifespan;
	event_reset_zone(nullptr, nullptr, nullptr, &zone);
	for (const auto &gate : gates)
		check_pair(gate, false);
	assert(!IS_SET(door(2402, 2)->exit_info, EX_LOCKED));
	pc->npc = pc->morph = false;
	char_from_room(pc); // NOWHERE does not count as castle occupancy
	reset_zone(1, 0);
	for (const auto &gate : gates)
		check_pair(gate, true);
	descriptor_list = nullptr;
}
void boundaries()
{
	// Scope uses zone number, not its array index.
	zone_table[1].number = 25;
	auto held = read_object_for_creation(real_object(gates[0].key), REAL);
	reset_zone(1, 0);
	check_pair(gates[0], true);
	zone_table[1].number = 24;
	reset_zone(1, 0);
	check_pair(gates[0], false);
	assert(IS_SET(door(2401, 0)->exit_info, EX_LOCKED));
	assert(!IS_SET(door(2403, 0)->exit_info, EX_LOCKED)); // unrelated closed-only door
	extract_obj(held);
	// An unexpected reverse exit must not be silently changed.
	auto reverse = door(gates[0].far, rev_dir[gates[0].direction]);
	const int target = reverse->to_room;
	reverse->to_room = real_room(5760);
	reset_zone(1, 0);
	assert(IS_SET(door(gates[0].near, gates[0].direction)->exit_info, EX_LOCKED));
	assert(IS_SET(reverse->exit_info, EX_LOCKED));
	reverse->to_room = target;
	reset_zone(1, 0);
	check_pair(gates[0], false);
	// The unrelated consumable bookcase key neither supplies a door nor gets replaced.
	auto bookcase_key = read_object_for_creation(real_object(2434), REAL);
	obj_to_char(bookcase_key, carrier(gates[0]));
	const auto count = objects.size();
	reset_zone(1, 0);
	check_pair(gates[0], false);
	assert(key_on(carrier(gates[0]), 2434) == bookcase_key && objects.size() == count);
}
int main(int argc, char **argv)
{
	assert(argc == 2);
	load_fixture();
	const std::string scenario = argv[1];
	if (scenario == "controls")
		controls();
	else if (scenario == "occupancy")
		occupancy();
	else if (scenario == "boundaries")
		boundaries();
	else
	{
		const int key = std::atoi(argv[1]);
		bool found = false;
		for (const auto &gate : gates)
			if (gate.key == key)
			{
				held_sequence(gate);
				found = true;
			}
		assert(found);
	}
}
