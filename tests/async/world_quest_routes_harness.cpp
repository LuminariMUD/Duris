#include "core/utils.h"
#include "world/map.h"
#include "world/world_quest_policy.h"
#include "world/world_quest_policy_math.h"
#include "combat/justice.h"

#include <cassert>
#include <cstring>
#include <deque>
#include <iostream>
#include <vector>

P_room world = nullptr;
zone_data zones[3]{};
zone_data *zone_table = zones;
int top_of_world = 0, top_of_zone_table = 2;
index_data mobiles[1]{}, objects[1]{};
P_index mob_index = mobiles, obj_index = objects;
int top_of_mobt = 0, top_of_objt = 0;
shop_data shops[1]{};
shop_data *shop_index = shops;
int number_of_shops = 1;
hometown_data hometowns[LAST_HOME]{};

// Procedures are compared by identity and must never execute during a proof.
int inn(int, P_char, int, char *)
{
	std::abort();
}
int ship_shop_proc(int, P_char, int, char *)
{
	std::abort();
}
int world_quest(P_char, P_char, int, char *)
{
	std::abort();
}
int shop_keeper(P_char, P_char, int, char *)
{
	std::abort();
}
int quester(P_char, P_char, int, char *)
{
	std::abort();
}
int board(P_obj, P_char, int, char *)
{
	std::abort();
}
int artifact_hide(P_obj, P_char, int, char *)
{
	std::abort();
}
int ring_of_regeneration(P_obj, P_char, int, char *)
{
	std::abort();
}
int singleton_shop_id(P_char)
{
	return 0;
}
int unknown_room(int, P_char, int, char *)
{
	std::abort();
}
int unknown_mobile(P_char, P_char, int, char *)
{
	std::abort();
}
int unknown_object(P_obj, P_char, int, char *)
{
	std::abort();
}

std::vector<room_data> rooms;
std::deque<room_direction_data> exits;
char_data player{};
pc_only_data pc{};

void edge(int from, int direction, int to, int flags = 0, int key = -1)
{
	room_direction_data entry{};
	entry.to_room = to;
	entry.exit_info = flags;
	entry.key = key;
	entry.keyword = const_cast<char *>("gate");
	exits.push_back(entry);
	rooms[from].dir_option[direction] = &exits.back();
}

void two_way(int from, int direction, int to, int reverse)
{
	edge(from, direction, to);
	edge(to, reverse, from);
}

int real_room(int vnum)
{
	for (int room = 0; room <= top_of_world; ++room)
		if (world[room].number == vnum)
			return room;
	return NOWHERE;
}

void fixture(size_t count = 8)
{
	rooms.assign(count, {});
	exits.clear();
	world = rooms.data();
	top_of_world = static_cast<int>(rooms.size()) - 1;
	for (int room = 0; room <= top_of_world; ++room)
	{
		rooms[room].number = 1000 + room;
		rooms[room].sector_type = SECT_FIELD;
	}
	for (auto &zone : zones)
		zone = {};
	zones[1].flags = ZONE_MAP;
	for (int room : { 1, 3, 4, 5 })
	{
		rooms[room].zone = 1;
		rooms[room].number = 500000 + room;
		rooms[room].continent = room == 4 ? CONT_EC : CONT_GC;
		rooms[room].map_section = 64;
	}
	rooms[0].number = 16633;
	rooms[2].zone = 2;
	player = {};
	pc = {};
	player.only.pc = &pc;
	player.player.level = 11;
	player.player.racewar = RACEWAR_GOOD;
	player.in_room = 7; // The accepted origin is independent of later location.
	mobiles[0] = {};
	objects[0] = {};
	shops[0] = {};
	for (auto &home : hometowns)
		home = {};
	two_way(0, DIR_EAST, 1, DIR_WEST);
	two_way(1, DIR_EAST, 3, DIR_WEST);
	two_way(3, DIR_EAST, 2, DIR_WEST);
}

world_quest_route_context routes(int level = 11)
{
	const auto before_world = rooms;
	const auto before_exits = exits;
	std::vector<unsigned char> actor(sizeof(player)), status(sizeof(pc));
	std::memcpy(actor.data(), &player, sizeof(player));
	std::memcpy(status.data(), &pc, sizeof(pc));
	auto result = world_quest_policy_routes(&player, 16633, level);
	assert(std::memcmp(actor.data(), &player, sizeof(player)) == 0);
	assert(std::memcmp(status.data(), &pc, sizeof(pc)) == 0);
	assert(std::memcmp(before_world.data(), rooms.data(), rooms.size() * sizeof(room_data)) ==
	       0);
	for (size_t i = 0; i < exits.size(); ++i)
		assert(std::memcmp(&before_exits[i], &exits[i], sizeof(room_direction_data)) == 0);
	assert(result.work <= WORLD_QUEST_MAX_ROUTE_WORK);
	return result;
}

void available(int level = 11)
{
	const auto result = routes(level);
	assert(world_quest_policy_route(result, 2) == world_quest_route_status::available);
	assert(world_quest_policy_map_room(result, 2) == 3);
}

void unavailable(int level = 11)
{
	const auto result = routes(level);
	assert(world_quest_policy_route(result, 2) != world_quest_route_status::available);
	assert(world_quest_policy_map_room(result, 2) == NOWHERE);
}

int main()
{
	fixture();
	available(11);
	available(29);
	unavailable(10);
	// Foreign transit is excluded even when both map tiles share map_section.
	rooms[3].continent = CONT_EC;
	unavailable(11);
	unavailable(29);
	available(30);
	available(40);
	available(41);
	available(49);
	available(50);
	fixture();
	rooms[0].dir_option[DIR_EAST] = nullptr;
	two_way(7, DIR_EAST, 1, DIR_NORTH);
	unavailable(30); // Another origin's access is not the accepted origin's route.
	fixture();
	two_way(0, DIR_NORTH, 5, DIR_SOUTH);
	available(); // Multiple entrances in the same region are unambiguous.
	rooms[5].continent = CONT_EC;
	assert(world_quest_policy_route(routes(), 2) == world_quest_route_status::unproven);
	fixture();
	rooms[1].continent = 0;
	unavailable();
	// A real directed return may use a different entrance/path.
	fixture();
	rooms[3].dir_option[DIR_WEST] = nullptr;
	unavailable();
	two_way(3, DIR_NORTH, 6, DIR_SOUTH);
	edge(6, DIR_WEST, 1);
	available();
	fixture();
	for (int flags : { EX_LOCKED, EX_SECRET, EX_BLOCKED, EX_WALLED,
			   EX_CLOSED | EX_ISDOOR | EX_SPIKED, EX_CLOSED })
	{
		rooms[3].dir_option[DIR_EAST]->exit_info = flags;
		unavailable();
	}
	rooms[3].dir_option[DIR_EAST]->exit_info = EX_CLOSED | EX_ISDOOR;
	rooms[3].dir_option[DIR_EAST]->key = 20; // Currently unlocked: opening needs no key.
	available();
	const auto prior = routes();
	rooms[3].dir_option[DIR_EAST]->exit_info |= EX_LOCKED;
	unavailable(); // A new command observes a newly locked door.
	assert(world_quest_policy_route(prior, 2) == world_quest_route_status::available);
	fixture();
	rooms[3].sector_type = SECT_MOUNTAIN;
	player.specials.affected_by |= AFF_FLY;
	unavailable(30);
	rooms[3].sector_type = SECT_UNDRWLD_MOUNTAIN;
	unavailable(30);
	rooms[3].sector_type = SECT_FIELD;
	rooms[2].sector_type = SECT_MOUNTAIN; // Ordinary mountain and map/zone transition.
	available();
	fixture();
	rooms[3].dir_option[DIR_EAST] = nullptr;
	two_way(3, DIR_EAST, 6, DIR_WEST);
	two_way(6, DIR_EAST, 2, DIR_WEST);
	rooms[2].sector_type = SECT_UNDRWLD_LOWCEIL;
	available(); // An ordinary zone passage can be crawled through.
	fixture();
	for (int room : { 1, 3 })
	{
		rooms[room].number = 700000 + room;
		rooms[room].continent = 0;
	}
	available();
	two_way(0, DIR_NORTH, 5, DIR_SOUTH); // Underdark versus surface is conflicting.
	unavailable();
	available(30);
	rooms[5].number = 700005; // A disconnected Underdark map is also distinct.
	rooms[5].continent = 0;
	unavailable();
	fixture();
	for (ulong flags : { ROOM_PRIVATE, ROOM_GUILD, ROOM_LOCKER, ROOM_JAIL, ROOM_ATRIUM })
	{
		rooms[2].room_flags = flags;
		unavailable();
	}
	fixture();
	zones[2].flags = ZONE_CLOSED;
	unavailable();
	zones[2].flags = ZONE_PRIVATE;
	unavailable();
	fixture();
	zones[2].hometown = 1;
	hometowns[0].flags = JUSTICE_EVILHOME;
	unavailable();
	player.player.racewar = RACEWAR_EVIL;
	available();
	fixture();
	rooms[2].sector_type = SECT_WATER_NOSWIM;
	unavailable(30);
	obj_data boat{};
	boat.type = ITEM_BOAT;
	player.carrying = &boat;
	available(30);
	unavailable(29);
	rooms[2].sector_type = SECT_NO_GROUND;
	unavailable(30);
	player.specials.affected_by |= AFF_FLY;
	available(30);
	unavailable(29);
	rooms[2].sector_type = SECT_UNDRWLD_NOGROUND;
	available(30);
	unavailable(29);
	player.specials.affected_by &= ~AFF_FLY;
	unavailable(30);
	rooms[2].sector_type = SECT_UNDERWATER;
	unavailable(30);
	player.specials.affected_by |= AFF_WATERBREATH;
	available(30);
	fixture();
	// An unknown side-street script cannot erase a proved local route. Its
	// potential ordinary exits still participate in geography ambiguity checks.
	rooms[6].funct = unknown_room;
	two_way(0, DIR_NORTH, 6, DIR_SOUTH);
	available();
	edge(6, DIR_EAST, 4);
	unavailable();
	fixture();
	rooms[2].funct = unknown_room;
	assert(world_quest_policy_route(routes(), 2) == world_quest_route_status::unproven);
	rooms[2].funct = inn;
	available();
	rooms[2].funct = ship_shop_proc;
	available();
	fixture();
	char_data npc{};
	npc_only_data npc_data{};
	npc.only.npc = &npc_data;
	npc.specials.act = ACT_ISNPC | ACT_SPEC;
	npc.in_room = 0;
	rooms[0].people = &npc;
	mobiles[0].func.mob = world_quest;
	available();
	mobiles[0].qst_func = quester;
	available();
	mobiles[0].qst_func = nullptr;
	mobiles[0].func.mob = shop_keeper;
	available();
	shops[0].func = world_quest; // Woodseer's real bartender uses this delegate.
	available();
	shops[0].func = unknown_mobile;
	unavailable(); // A shop's secondary procedure must be classified too.
	shops[0].func = nullptr;
	mobiles[0].func.mob = unknown_mobile;
	unavailable();
	fixture();
	obj_data obstacle{};
	obstacle.R_num = 0;
	rooms[3].contents = &obstacle;
	objects[0].virtual_number = 753;
	obstacle.value[1] = DIR_EAST;
	unavailable();
	objects[0].virtual_number = 100;
	obstacle.trap_charge = 1;
	obstacle.trap_eff = BIT_1 | (BIT_4 << DIR_EAST);
	unavailable();
	assert(obstacle.trap_charge == 1);
	obstacle.trap_charge = 0;
	available();
	// Non-direction trap flags must not block diagonal exits. Movement only
	// checks trap direction bits from north through down.
	for (int direction = DIR_NORTHWEST; direction < NUM_EXITS; ++direction)
	{
		rooms[3].dir_option[DIR_EAST] = nullptr;
		edge(3, direction, 2);
		obstacle.trap_charge = 1;
		obstacle.trap_eff = BIT_1 | (BIT_4 << DIR_EAST) | BIT_10 | BIT_11 | BIT_12;
		available();
		assert(obstacle.trap_charge == 1);
		rooms[3].dir_option[direction] = nullptr;
	}
	edge(3, DIR_EAST, 2);
	unavailable(); // The actual east trigger still blocks the east route.
	obstacle.trap_charge = 0;
	objects[0].func.obj = unknown_object;
	unavailable();
	objects[0].func.obj = board;
	available();
	fixture();
	obj_data held{};
	held.R_num = 0;
	player.carrying = &held;
	objects[0].func.obj = unknown_object;
	assert(world_quest_policy_route(routes(), 2) == world_quest_route_status::unproven);
	player.carrying = nullptr;
	player.equipment[0] = &held;
	assert(world_quest_policy_route(routes(), 2) == world_quest_route_status::unproven);
	objects[0].func.obj = artifact_hide;
	available();
	objects[0].func.obj = ring_of_regeneration;
	available();
	// The bound covers an oversized, otherwise legal graph; exhaustion is
	// unproven rather than a cancellation-worthy impossibility verdict.
	fixture(WORLD_QUEST_MAX_ROUTE_ROOMS + 4);
	for (int room = 0; room <= top_of_world; ++room)
	{
		rooms[room].zone = 1;
		rooms[room].number = 500000 + room;
		rooms[room].continent = CONT_GC;
		for (auto &exit : rooms[room].dir_option)
			exit = nullptr;
		if (room)
			two_way(room - 1, DIR_EAST, room, DIR_WEST);
	}
	rooms[0].number = 16633;
	rooms[0].zone = 0;
	const auto oversized = routes();
	assert(oversized.exhausted);
	assert(world_quest_policy_route(oversized, 2) == world_quest_route_status::unproven);
	std::cout
		<< "bartender route geometry, directed returns, barriers, capabilities, scripts, traps and bounds passed\n";
}
