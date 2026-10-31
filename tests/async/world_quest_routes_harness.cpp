// Exercise the production geographic catalog directly; real assignment/refresh
// coverage lives in world_quest_live_targets_harness.cpp.
#include "../../src/world/world_quest_policy.c"
#include <cassert>
#include <cstring>
#include <deque>
#include <iostream>

P_room world = nullptr;
zone_data zones[10]{};
zone_data *zone_table = zones;
int top_of_world = 0, top_of_zone_table = 9;
std::vector<room_data> rooms;
std::deque<room_direction_data> exits;

void edge(int from, int direction, int to)
{
	room_direction_data entry{};
	entry.to_room = to;
	entry.exit_info = EX_LOCKED | EX_SECRET | EX_BLOCKED | EX_WALLED;
	exits.push_back(entry);
	rooms[from].dir_option[direction] = &exits.back();
}

void fixture(size_t count = 14)
{
	rooms.assign(count, {});
	exits.clear();
	world = rooms.data();
	top_of_world = static_cast<int>(count) - 1;
	for (auto &zone : zones)
		zone = {};
	for (int room = 0; room <= top_of_world; ++room)
	{
		world[room].number = 500100 + room;
		world[room].zone = 3;
		world[room].continent = CONT_EC;
	}
	const int numbers[] = { 1734, 74339,  54000,  602263, 813720, 813721, 2000,
				3000, 500001, 700002, 4000,   5000,   2001,   55000 };
	const int zone_ids[] = { 0, 1, 2, 3, 4, 4, 5, 6, 3, 4, 7, 8, 5, 9 };
	for (int room = 0; room < 14; ++room)
	{
		world[room].number = numbers[room];
		world[room].zone = zone_ids[room];
	}
	zones[3].flags = zones[4].flags = ZONE_MAP;
	world[8].continent = CONT_GC;
	edge(3, DIR_WEST, 0); // Incoming-only attachment also conveys geography.
	edge(0, DIR_DOWN, 4);
	edge(1, DIR_EAST, 3);
	edge(1, DIR_DOWN, 2);
	edge(2, DIR_DOWN, 4); // Bloodstone's adjacent interior connector.
	edge(2, DIR_NORTH, 13);
	edge(13, DIR_NORTH, 8); // A farther boundary cannot replace the direct one.
	edge(4, DIR_NORTH, 5); // One-way, locked map adjacency defines one component.
	edge(6, DIR_NORTH, 3);
	edge(7, DIR_NORTH, 5);
	edge(10, DIR_NORTH, 8);
	edge(11, DIR_NORTH, 9);
}

void verify()
{
	const auto before = rooms;
	const auto before_exits = exits;
	build_geography();
	assert(!memcmp(before.data(), rooms.data(), rooms.size() * sizeof(room_data)));
	for (size_t index = 0; index < exits.size(); ++index)
		assert(!memcmp(&before_exits[index], &exits[index], sizeof(room_direction_data)));
	for (int origin : { 0, 1 })
	{
		const auto region = quest_region_for_room(origin);
		assert(region.surface == CONT_EC && region.underdark > 0);
		assert(region.underdark == quest_region_for_room(5).underdark);
		assert(quest_local_match(origin, 6));
		assert(quest_local_match(origin, 7));
		assert(quest_local_match(origin, 12)); // No ordinary path to this reset room.
		assert(!quest_local_match(origin, 10));
		assert(!quest_local_match(origin, 11));
	}
	assert(!quest_local_match(NOWHERE, 6));
}

int main()
{
	fixture();
	verify();
	edge(7, DIR_EAST, 11); // Interior bridges cannot join Underdark map components.
	verify();
	edge(0, DIR_NORTH, 8); // Ambiguous surface, independently known Underdark.
	build_geography();
	assert(quest_region_for_room(0).surface == 0);
	assert(quest_region_for_room(0).uncertain);
	assert(quest_local_match(0, 7) && !quest_local_match(0, 6));
	fixture(65536 + 8); // No old route-size budget participates.
	verify();
	std::cout
		<< "both local regions, nearest boundaries, one-way geography, disconnected rooms, "
		   "remote rejection, ambiguity, non-mutation and large-world geography passed\n";
}
