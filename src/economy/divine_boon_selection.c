#include "economy/divine_boon_selection.h"

#include "combat/justice.h"
#include "core/prototypes.h"
#include "core/utils.h"
#include "world/db.h"
#include "world/map.h"
#include "world/world_quest_policy.h"

#include <algorithm>
#include <new>
#include <set>

extern P_room world;
extern zone_data *zone_table;
extern int top_of_world;
extern int top_of_zone_table;
extern const int guild_locations[][CLASS_COUNT + 1];

namespace
{
// Bounded adventure pool from areas/zon and areas/wld.
// Membership is only permission to validate, never proof of live eligibility.
constexpr int reviewed_zones[] = { 18,	20,  40,  55,  109, 114, 148, 190,
				   241, 358, 750, 886, 969, 974, 985 };
constexpr ulong forbidden_rooms = ROOM_LOCKER | ROOM_PRIVATE | ROOM_ARENA | ROOM_GUILD | ROOM_JAIL |
				  ROOM_ATRIUM;

struct encounter
{
	int room;
	int level;
};
struct candidate
{
	int number;
	int index;
	std::vector<encounter> encounters;
};
std::vector<candidate> catalogue;
std::array<std::vector<int>, 2> paths;

bool ordinary_room(int room, unsigned side)
{
	if (!world || !zone_table || room < 0 || room > top_of_world || side > 1)
		return false;
	const auto &entry = world[room];
	if (entry.zone > top_of_zone_table || entry.funct ||
	    IS_SET(entry.room_flags, forbidden_rooms) ||
	    IS_SET(zone_table[entry.zone].flags, ZONE_CLOSED | ZONE_PRIVATE))
		return false;
	const int town = zone_table[entry.zone].hometown;
	if (town < 0 || town > LAST_HOME)
		return false;
	if (town && IS_SET(hometowns[town - 1].flags,
			   (side ? JUSTICE_GOODHOME : JUSTICE_EVILHOME) | JUSTICE_UNDEADHOME))
		return false;
	switch (entry.sector_type)
	{
	case SECT_MOUNTAIN:
	case SECT_WATER_NOSWIM:
	case SECT_NO_GROUND:
	case SECT_UNDERWATER:
	case SECT_UNDERWATER_GR:
	case SECT_FIREPLANE:
	case SECT_OCEAN:
	case SECT_UNDRWLD_NOSWIM:
	case SECT_UNDRWLD_NOGROUND:
	case SECT_AIR_PLANE:
	case SECT_WATER_PLANE:
	case SECT_EARTH_PLANE:
	case SECT_ETHEREAL:
	case SECT_ASTRAL:
	case SECT_UNDRWLD_MOUNTAIN:
	case SECT_UNDRWLD_LIQMITH:
	case SECT_CASTLE_WALL:
	case SECT_NEG_PLANE:
	case SECT_PLANE_OF_AVERNUS:
	case SECT_LAVA:
		return false;
	default:
		return true;
	}
}

bool ordinary_exit(int room, int direction, unsigned side)
{
	const auto *exit = world[room].dir_option[direction];
	return exit && !IS_SET(exit->exit_info, EX_SECRET | EX_LOCKED | EX_BLOCKED | EX_WALLED) &&
	       ordinary_room(exit->to_room, side);
}

bool live_zone(const candidate &zone)
{
	if (!zone_table || zone.index < 0 || zone.index > top_of_zone_table)
		return false;
	const auto &current = zone_table[zone.index];
	return current.number == zone.number && current.reset_mode > 0 &&
	       !IS_SET(current.flags,
		       ZONE_TOWN | ZONE_SAFE | ZONE_MAP | ZONE_CLOSED | ZONE_PRIVATE) &&
	       current.hometown == 0;
}

bool path_valid(int room, unsigned side)
{
	if (side > 1 || paths[side].size() != static_cast<size_t>(top_of_world) + 1)
		return false;
	// A saved predecessor chain is acyclic; the bound also contains corruption.
	for (size_t left = paths[side].size(); left; --left)
	{
		if (!ordinary_room(room, side) || paths[side][room] < 0)
			return false;
		const int previous = paths[side][room];
		if (previous == room)
		{
			const int home = zone_table[world[room].zone].hometown;
			return home > 0 && IS_SET(hometowns[home - 1].flags,
						  side ? JUSTICE_EVILHOME : JUSTICE_GOODHOME);
		}
		bool connected = false;
		for (int direction = 0; direction < NUM_EXITS; ++direction)
			if (world[previous].dir_option[direction] &&
			    world[previous].dir_option[direction]->to_room == room &&
			    ordinary_exit(previous, direction, side))
				connected = true;
		if (!connected)
			return false;
		room = previous;
	}
	return false;
}

void refresh_paths()
{
	for (unsigned side = 0; side < paths.size(); ++side)
	{
		auto &previous = paths[side];
		previous.assign(static_cast<size_t>(top_of_world) + 1, -1);
		std::vector<int> queue;
		for (int town = 1; town <= LAST_HOME; ++town)
		{
			const int room = real_room(guild_locations[town][0]);
			if (!ordinary_room(room, side))
				continue;
			const int home = zone_table[world[room].zone].hometown;
			if (!home || !IS_SET(hometowns[home - 1].flags,
					     side ? JUSTICE_EVILHOME : JUSTICE_GOODHOME))
				continue;
			if (previous[room] < 0)
			{
				previous[room] = room;
				queue.push_back(room);
			}
		}
		for (size_t next = 0; next < queue.size(); ++next)
			for (int direction = 0; direction < NUM_EXITS; ++direction)
			{
				const int room = queue[next];
				if (!ordinary_exit(room, direction, side))
					continue;
				const int destination = world[room].dir_option[direction]->to_room;
				if (previous[destination] < 0)
				{
					previous[destination] = room;
					queue.push_back(destination);
				}
			}
	}
}

double suitable_level(const candidate &zone, unsigned side)
{
	if (!live_zone(zone))
		return 0;
	std::set<int> rooms;
	double total = 0;
	unsigned count = 0;
	for (const auto &mob : zone.encounters)
		if (mob.room >= 0 && mob.room <= top_of_world &&
		    world[mob.room].zone == zone.index &&
		    !IS_SET(world[mob.room].room_flags, ROOM_SAFE | ROOM_NO_MOB) &&
		    !IS_SURFACE_MAP(mob.room) && !IS_UD_MAP(mob.room) && path_valid(mob.room, side))
		{
			rooms.insert(mob.room);
			total += mob.level;
			++count;
		}
	return rooms.size() >= 3 && count >= 5 ? total / count : 0;
}

bool assigned(const divine_boon_state &state, int zone, unsigned side, int64_t now)
{
	return std::any_of(state.slots.begin(), state.slots.end(), [&](const auto &slot)
			   { return divine_boon_active(slot, now) && slot.zones[side] == zone; });
}

unsigned bracket(double level)
{
	return level <= 20 ? 0 : level <= 35 ? 1 : level <= 50 ? 2 : 3;
}
}

bool divine_boon_selection_bootstrap()
try
{
	catalogue.clear();
	if (!world || !zone_table || top_of_world < 0 || top_of_zone_table < 0)
		return false;
	for (int number : reviewed_zones)
	{
		const int index = real_zone0(number);
		candidate zone{ number, index, {} };
		if (!live_zone(zone) || !zone_table[index].cmd)
			continue;
		std::set<int> prototypes;
		for (auto *reset = zone_table[index].cmd; reset->command != 'S'; ++reset)
		{
			if (reset->command != 'M' || reset->arg2 <= 0 || reset->arg4 < 50)
				continue;
			const int level = world_quest_policy_combat_level(reset->arg1);
			if (level < 5)
				continue;
			prototypes.insert(reset->arg1);
			zone.encounters.push_back({ reset->arg3, level });
		}
		if (prototypes.size() >= 2)
			catalogue.push_back(std::move(zone));
	}
	refresh_paths();
	return true;
}
catch (const std::bad_alloc &)
{
	catalogue.clear();
	paths = {};
	return false;
}

bool divine_boon_zone_eligible(int zone_number, unsigned side)
{
	for (const auto &zone : catalogue)
		if (zone.number == zone_number)
			return suitable_level(zone, side) > 0;
	return false;
}

bool divine_boon_select(const divine_boon_state &state, int64_t now,
			const std::array<divine_boon_population, 2> &population,
			divine_boon_slot *choice)
try
{
	if (!choice || state.mode != divine_boon_mode::divine || state.paused ||
	    !divine_boon_state_valid(state) || top_of_world < 0)
		return false;
	refresh_paths();
	divine_boon_slot selected;
	selected.category = divine_boon_category::experience;
	for (unsigned side = 0; side < population.size(); ++side)
	{
		if (!population[side].active_accounts)
			continue;
		std::array<unsigned, 4> served = {};
		for (const auto &slot : state.slots)
			if (divine_boon_active(slot, now))
				for (const auto &zone : catalogue)
					if (zone.number == slot.zones[side])
						++served[bracket(suitable_level(zone, side))];
		for (unsigned relaxed = 0; relaxed < 2 && selected.zones[side] < 0; ++relaxed)
		{
			double total = 0;
			for (const auto &zone : catalogue)
			{
				if (assigned(state, zone.number, side, now))
					continue;
				if (!relaxed &&
				    std::any_of(
					    state.history.begin(), state.history.end(),
					    [&](const auto &old)
					    {
						    return old.side == side &&
							   old.zone == zone.number &&
							   now < old.expired_at +
									   DIVINE_BOON_REPEAT_WINDOW;
					    }))
					continue;
				const double level = suitable_level(zone, side);
				if (level <= 0)
					continue;
				// Accounts, rather than their levels, supply bracket weight. An
				// isolated high-level alt cannot outweigh a populated low bracket.
				const unsigned band = bracket(level);
				const double weight =
					static_cast<double>(population[side].brackets[band]) /
					(1 + served[band]);
				if (weight <= 0)
					continue;
				total += weight;
				if (number(0, 1000000) / 1000001.0 < weight / total)
					selected.zones[side] = zone.number;
			}
		}
	}
	if (selected.zones[0] < 0 && selected.zones[1] < 0)
		return false;
	// Epic/trade/PvP choices join this selector with their actual payout paths.
	// Until then, do not advertise a category that cannot yet deliver its benefit.
	*choice = selected;
	return true;
}
catch (const std::bad_alloc &)
{
	return false;
}
