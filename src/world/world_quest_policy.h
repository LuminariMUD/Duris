/****************************************************************************
 *
 *  File: world_quest_policy.h                                  Part of Duris
 *  Usage: world quest policy interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef DURIS_WORLD_QUEST_POLICY_H
#define DURIS_WORLD_QUEST_POLICY_H

#include <vector>
#include <unordered_map>

#include "core/structs.h"
#include "world/world_quest.h"

// Describes a route under the supplied player facts. It is not, by itself, a
// verdict that an accepted assignment is invalidated by the world.
enum class world_quest_route_status
{
	available,
	unavailable,
	unproven,
};

// Build and reuse only within one command. Room IDs are rnums; the result has
// no live pointers. Reverse links prove a directed return journey.
struct world_quest_route_context
{
	struct room
	{
		int map_entrance = NOWHERE;
		bool returns_to_origin = false;
		std::vector<int> incoming;
	};
	std::unordered_map<int, room> rooms;
	size_t work = 0;
	bool exhausted = false;
	bool uncertain = false;
};

world_quest_route_context world_quest_policy_routes(P_char ch, int origin_vnum, int accepted_level);
world_quest_route_status world_quest_policy_route(const world_quest_route_context &context,
						  int room);
int world_quest_policy_map_room(const world_quest_route_context &context, int room);

struct world_quest_target
{
	int zone = -1;
	int mob_vnum = -1;
	int type = 0;
	int usable_count = 0;
	int map_room = NOWHERE;
};

quest_creation_failure world_quest_policy_select_target(P_char ch, int origin_vnum,
							int accepted_level,
							world_quest_target &target,
							int required_type = 0, int needed = 0);

struct world_quest_target_check
{
	world_quest_target_status status = world_quest_target_status::unproven;
	int map_room = NOWHERE;
	size_t work = 0;
};

world_quest_target_check world_quest_policy_check_target(P_char ch, int origin_vnum,
							 int accepted_level, int zone_number,
							 int mob_vnum, int type, int needed);

bool world_quest_policy_bootstrap();
// Reuse the boot probe for Divine encounter checks, without quest reward rules.
// Unknown, staff-level, shop and non-combat prototypes return -1.
int world_quest_policy_combat_level(int mob_rnum);
bool world_quest_policy_zone_is_invalid(int zone_number);
void world_quest_policy_zone_list(P_char ch, std::vector<int> &valid_zones);
int world_quest_policy_select_zone(int accepted_level, const std::vector<int> &valid_zones);
int world_quest_policy_random_item(int zone_number);
int world_quest_policy_random_quest_item(int zone_number, int quest_level);

#endif // DURIS_WORLD_QUEST_POLICY_H
