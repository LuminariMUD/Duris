#include "economy/divine_boon_selection.h"
#include "economy/divine_boon_runtime.h"

#include "combat/justice.h"
#include "core/prototypes.h"
#include "core/utils.h"
#include "world/db.h"
#include "world/map.h"
#include "world/epic.h"
#include "world/zone_touch_command.h"
#include "world/specs.prototypes.h"
#include "item/objmisc.h"
#include "sql/sql.h"
#include "ships/ships.h"
#include "world/graph.h"
#include <map>
#include "world/world_quest_policy.h"

#include <algorithm>
#include <cmath>
#include <deque>
#include <new>
#include <optional>
#include <set>

extern P_room world;
extern zone_data *zone_table;
extern int top_of_world;
extern P_index obj_index;
extern P_obj object_list;
extern int top_of_objt;
extern int top_of_zone_table;
extern const int guild_locations[][CLASS_COUNT + 1];
int inn(int, P_char, int, char *);

namespace
{
constexpr ulong forbidden_rooms = ROOM_LOCKER | ROOM_PRIVATE | ROOM_ARENA | ROOM_GUILD | ROOM_JAIL |
				  ROOM_ATRIUM;

struct encounter
{
	int room;
	int level;
	int prototype;
};
struct candidate
{
	int number;
	int index;
	std::vector<encounter> encounters;
	bool experience = false;
	std::vector<int> stone_rooms;
};
std::vector<candidate> catalogue;
std::array<std::array<std::vector<int>, NUM_PORTS>, NUM_PORTS> cargo_paths;
std::array<std::vector<int>, 2> paths;
std::optional<divine_boon_state> prepared_hour;
// Ring of the last eight durably published hourly decisions (current boot only).
constexpr size_t diagnostic_limit = 8;
std::deque<divine_boon_selection_diagnostic> diagnostic_history;
std::optional<divine_boon_selection_diagnostic> prepared_diagnostic;
std::optional<divine_boon_selection_diagnostic> submitted_diagnostic;

void confirm_diagnostic(const divine_boon_state &state, bool pending)
{
	if (!submitted_diagnostic || pending)
		return;
	if (state.revision == submitted_diagnostic->committed_revision &&
	    state.last_opportunity == submitted_diagnostic->hour)
	{
		if (diagnostic_history.size() == diagnostic_limit)
			diagnostic_history.pop_front();
		try
		{
			diagnostic_history.push_back(*submitted_diagnostic);
		}
		catch (const std::bad_alloc &)
		{
			// Read-only diagnostics must never interrupt game commands.
		}
	}
	// Never report a refused, superseded or failed write as committed.
	if (state.revision >= submitted_diagnostic->committed_revision)
		submitted_diagnostic.reset();
}
std::array<std::array<int32_t, DIVINE_BOON_SLOTS>, 2> reward_zones = {};
uint64_t reward_revision = 0;
int64_t reward_checked_at = -1;

bool ordinary_room(int room, unsigned side)
{
	if (!world || !zone_table || room < 0 || room > top_of_world || side > 1)
		return false;
	const auto &entry = world[room];
	if (entry.zone > top_of_zone_table ||
	    (entry.funct && entry.funct != inn && entry.funct != ship_shop_proc) ||
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
	std::set<int> prototypes;
	double total = 0;
	unsigned count = 0;
	for (const auto &mob : zone.encounters)
		if (mob.room >= 0 && mob.room <= top_of_world &&
		    world[mob.room].zone == zone.index &&
		    !IS_SET(world[mob.room].room_flags, ROOM_SAFE | ROOM_NO_MOB) &&
		    !IS_SURFACE_MAP(mob.room) && !IS_UD_MAP(mob.room) && path_valid(mob.room, side))
		{
			rooms.insert(mob.room);
			prototypes.insert(mob.prototype);
			total += mob.level;
			++count;
		}
	return rooms.size() >= 3 && prototypes.size() >= 2 && count >= 5 ? total / count : 0;
}

bool epic_target(const candidate &zone, unsigned side)
{
	zone_info metadata;
	if (!live_zone(zone) || !get_zone_info(zone.number, &metadata) ||
	    metadata.epic_payout <= 0 || metadata.suggested_group_size <= 0 ||
	    metadata.stonecount <= 0 || metadata.epic_type < EPIC_ZONE_TYPE_SMALL ||
	    metadata.epic_type > EPIC_ZONE_TYPE_MONOLITH || epic_zone_done_now(zone.number))
		return false;
	auto stone = [&](P_obj obj)
	{
		return obj && obj_index && obj->R_num >= 0 && obj->R_num <= top_of_objt &&
		       obj_index[obj->R_num].func.obj == epic_stone && obj->obj_uid &&
		       OBJ_MAGIC(obj) && obj->value[0] > 0 && obj->value[1] > 0 &&
		       obj->value[2] == zone.number;
	};
	const bool reachable = std::any_of(zone.stone_rooms.begin(), zone.stone_rooms.end(),
					   [&](int room)
					   {
						   return room >= 0 && room <= top_of_world &&
							  world[room].zone == zone.index &&
							  !IS_SET(world[room].room_flags,
								  ROOM_SAFE | ROOM_NO_MOB) &&
							  path_valid(room, side);
					   });
	if (!reachable)
		return false;
	// A defeated carrier leaves the same stone in a corpse, then the player
	// takes it. Follow the existing container/carrier location; do not withdraw
	// the bonus precisely when the group completes that legitimate stone.
	for (P_obj obj = object_list; obj; obj = obj->next)
		if (stone(obj) && obj_zone_id(obj) == zone.index)
			return true;
	return false;
}

unsigned encounter_group(const candidate &zone)
{
	// The historical SQL value 100 is a payout divisor, not party guidance.
	// Use the actual reset encounter: one active account per concurrent NPC in
	// the most crowded room, rejecting encounters beyond the supported group.
	std::map<int, unsigned> rooms;
	unsigned group = 1;
	for (const auto &mob : zone.encounters)
		group = std::max(group, ++rooms[mob.room]);
	return group;
}

bool assigned(const divine_boon_state &state, int zone, unsigned side, int64_t now)
{
	return std::any_of(state.slots.begin(), state.slots.end(), [&](const auto &slot)
			   { return divine_boon_active(slot, now) && slot.zones[side] == zone; });
}

std::string category_list(unsigned categories)
{
	constexpr const char *names[] = { "none", "experience", "epic", "cargo", "pvp" };
	std::string text;
	for (unsigned category = 1; category < std::size(names); ++category)
		if (categories & (1u << category))
			text += (text.empty() ? "" : "+") + std::string(names[category]);
	return text.empty() ? "none" : text;
}

// Same side and zone ended within the repeat window.
bool repeated(const divine_boon_state &state, int zone, unsigned side, int64_t now)
{
	return std::any_of(state.history.begin(), state.history.end(),
			   [&](const auto &old)
			   {
				   return old.side == side && old.zone == zone &&
					  now < old.expired_at + DIVINE_BOON_REPEAT_WINDOW;
			   });
}
}

bool divine_boon_selection_bootstrap()
try
{
	catalogue.clear();
	cargo_paths = {};
	prepared_hour.reset();
	prepared_diagnostic.reset();
	submitted_diagnostic.reset();
	diagnostic_history.clear();
	reward_revision = 0;
	reward_checked_at = -1;
	if (!world || !zone_table || top_of_world < 0 || top_of_zone_table < 0)
		return false;
#ifdef __NO_MYSQL__
	sql_load_zones();
#endif
	for (int index = 0; index <= top_of_zone_table; ++index)
	{
		// Exp uses the bartender-quest vetting (normal zone, not a town, not
		// explicitly denied, valid average level). Epics need their live stone.
		const int number = zone_table[index].number;
		candidate zone{ number, index, {}, !world_quest_policy_zone_is_invalid(number), {} };
		if (!live_zone(zone) || !zone_table[index].cmd)
			continue;
		int mob_room = -1;
		for (auto *reset = zone_table[index].cmd; reset->command != 'S'; ++reset)
		{
			if (reset->command == 'M')
				mob_room = reset->arg3;
			if (obj_index && reset->arg1 >= 0 && reset->arg1 <= top_of_objt &&
			    reset->arg4 >= 50 &&
			    (reset->command == 'O' || reset->command == 'G' ||
			     reset->command == 'E') &&
			    obj_index[reset->arg1].func.obj == epic_stone)
				zone.stone_rooms.push_back(reset->command == 'O' ? reset->arg3 :
										   mob_room);
			if (reset->command != 'M' || reset->arg2 <= 0 || reset->arg4 < 50)
				continue;
			const int level = world_quest_policy_combat_level(reset->arg1);
			if (level < 5)
				continue;
			zone.encounters.push_back({ reset->arg3, level, reset->arg1 });
		}
		if (zone.encounters.size() >= 5)
			catalogue.push_back(std::move(zone));
	}
	// The native shortest-path search belongs to boot, never player commands.
	for (int source = 0; source < NUM_PORTS; ++source)
		for (int destination = 0; destination < NUM_PORTS; ++destination)
		{
			if (source == destination)
				continue;
			const int from = real_room(ports[source].ocean_map_room);
			const int to = real_room(ports[destination].ocean_map_room);
			if (from < 0 || to < 0 || from >= top_of_world || to >= top_of_world)
				continue;
			if (!dijkstra(from, to, valid_ship_edge, cargo_paths[source][destination]))
				cargo_paths[source][destination].clear();
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
			return zone.experience && suitable_level(zone, side) > 0;
	return false;
}

bool divine_boon_epic_zone_eligible(int zone_number, unsigned side)
{
	for (const auto &zone : catalogue)
		if (zone.number == zone_number)
			return suitable_level(zone, side) > 0 && epic_target(zone, side);
	return false;
}

bool divine_boon_reward_zone_eligible(int zone_number, unsigned side)
{
	const auto *state = divine_boon_runtime_state();
	return state && state->revision == reward_revision && side < reward_zones.size() &&
	       zone_number >= 0 &&
	       std::find(reward_zones[side].begin(), reward_zones[side].end(), zone_number) !=
		       reward_zones[side].end();
}

bool divine_boon_cargo_eligible(const divine_boon_slot &slot)
{
	if (slot.category != divine_boon_category::cargo || slot.source_port < 0 ||
	    slot.source_port >= NUM_PORTS || slot.destination_port < 0 ||
	    slot.destination_port >= NUM_PORTS || slot.source_port == slot.destination_port ||
	    slot.cargo_commodity != slot.source_port ||
	    slot.contraband_commodity != slot.source_port)
		return false;
	const int source = real_room(ports[slot.source_port].loc_room),
		  destination = real_room(ports[slot.destination_port].loc_room);
	if (source < 0 || source > top_of_world || destination < 0 || destination > top_of_world ||
	    world[source].funct != ship_shop_proc || world[destination].funct != ship_shop_proc)
		return false;

	bool land = false;
	for (unsigned side = 0; side < 2; ++side)
		land |= path_valid(source, side) && path_valid(destination, side);
	if (!land)
		return false;
	const int from = real_room(ports[slot.source_port].ocean_map_room),
		  to = real_room(ports[slot.destination_port].ocean_map_room);
	if (from < 0 || to < 0 || from > top_of_world || to > top_of_world)
		return false;
	int room = from;
	for (int direction : cargo_paths[slot.source_port][slot.destination_port])
	{
		// Revalidate the cached route without graph-search scratch marks.
		// These are the same navigation restrictions as VALID_SHIP_EDGE.
		if (direction < 0 || direction >= NUM_EXITS || !world[room].dir_option[direction] ||
		    TOROOM(room, direction) < 0 || TOROOM(room, direction) > top_of_world ||
		    IS_SECRET(room, direction) || IS_LOCKED(room, direction) ||
		    IS_BLOCKED(room, direction) ||
		    !(TO_OCEAN(room, direction) || TO_DOCKABLE(room, direction) ||
		      TO_NOSWIM(room, direction)))
			return false;
		room = TOROOM(room, direction);
	}
	return room == to;
}

bool divine_boon_select(const divine_boon_state &published, int64_t now,
			const std::array<divine_boon_population, 2> &population,
			std::vector<divine_boon_slot> *choices,
			divine_boon_selection_diagnostic *diagnostic)
try
{
	if (!choices || published.mode != divine_boon_mode::divine || published.paused ||
	    !divine_boon_state_valid(published) || top_of_world < 0)
		return false;
	choices->clear();
	auto state = published;
	divine_boon_reconcile(&state, now); // Newly expired objectives join repeat history.
	refresh_paths();
	if (diagnostic)
		diagnostic->population = population;
	unsigned zone_boons = 0;
	bool has_cargo = false, has_pvp = false;
	for (const auto &slot : state.slots)
		if (divine_boon_active(slot, now))
		{
			has_cargo |= slot.category == divine_boon_category::cargo;
			has_pvp |= slot.category == divine_boon_category::pvp;
			zone_boons += slot.category == divine_boon_category::experience ||
				      slot.category == divine_boon_category::epic;
		}

	if (zone_boons < DIVINE_BOON_ZONE_SLOTS)
	{
		// The in-game epic zone list order: lowest payout first.
		std::vector<std::pair<int, size_t>> ranked;
		for (size_t index = 0; index < catalogue.size(); ++index)
			if (zone_info info;
			    get_zone_info(catalogue[index].number, &info) && info.epic_type > 0)
				ranked.push_back({ info.epic_payout, index });
		std::ranges::stable_sort(ranked, {}, &std::pair<int, size_t>::first);

		std::array<divine_boon_slot, 2> pick;
		pick[0].category = divine_boon_category::experience;
		pick[1].category = divine_boon_category::epic;
		for (unsigned side = 0; side < population.size(); ++side)
		{
			// Path walks and stone scans happen once per side, not per pass.
			std::vector<double> fit(catalogue.size());
			for (size_t index = 0; index < catalogue.size(); ++index)
				fit[index] = suitable_level(catalogue[index], side);
			auto open = [&](size_t index, bool relaxed)
			{
				const int zone = catalogue[index].number;
				return fit[index] > 0 && !assigned(state, zone, side, now) &&
				       (relaxed || !repeated(state, zone, side, now));
			};
			const auto &levels = population[side].levels;

			// Exp: a zone around one online player's level (-5..+3), widening by
			// up to 10 more each way; never a zone far outside their range.
			if (!levels.empty())
			{
				const int level =
					levels[number(0, static_cast<int>(levels.size()) - 1)];
				for (int spread = 0; spread <= 10 && pick[0].zones[side] < 0;
				     spread += 5)
					for (unsigned relaxed = 0;
					     relaxed < 2 && pick[0].zones[side] < 0; ++relaxed)
					{
						unsigned count = 0;
						for (size_t index = 0; index < catalogue.size();
						     ++index)
							if (catalogue[index].experience &&
							    open(index, relaxed) &&
							    fit[index] >= level - 5 - spread &&
							    fit[index] <= level + 3 + spread &&
							    number(1, ++count) == 1)
								pick[0].zones[side] =
									catalogue[index].number;
						if (diagnostic && count)
							diagnostic->experience_candidates[side] =
								count;
					}
			}

			// Epic: a window over the payout-ranked list, centred by the side's
			// average online level (top half under 30, bottom half above, the
			// bottom quarter from 50). Nobody online: any zone, so one awaits login.
			std::vector<bool> live(ranked.size());
			for (size_t rank = 0; rank < ranked.size(); ++rank)
			{
				const auto &zone = catalogue[ranked[rank].second];
				live[rank] = fit[ranked[rank].second] > 0 &&
					     encounter_group(zone) <= ZONE_TOUCH_MAX_PARTICIPANTS &&
					     epic_target(zone, side);
			}
			double centre = 0;
			for (uint16_t level : levels)
				centre += level;
			if (!levels.empty())
				centre = std::clamp((centre / levels.size() - 10) / 40, 0.0, 1.0);
			for (double reach = 0.25; reach < 1.1 && pick[1].zones[side] < 0;
			     reach += 0.1)
				for (unsigned relaxed = 0; relaxed < 2 && pick[1].zones[side] < 0;
				     ++relaxed)
				{
					double total = 0;
					unsigned count = 0;
					for (size_t rank = 0; rank < ranked.size(); ++rank)
					{
						if (!live[rank] ||
						    !open(ranked[rank].second, relaxed))
							continue;
						const double position =
							ranked.size() > 1 ?
								double(rank) / (ranked.size() - 1) :
								0;
						const double weight =
							levels.empty() ?
								1 :
								1 - std::abs(position - centre) /
										reach;
						if (weight <= 0)
							continue;
						++count;
						total += weight;
						if (number(0, 1000000) / 1000001.0 < weight / total)
							pick[1].zones[side] =
								catalogue[ranked[rank].second]
									.number;
					}
					if (diagnostic && count)
						diagnostic->epic_candidates[side] = count;
				}
		}
		divine_boon_slot selected;
		unsigned total = 0;
		for (const auto &candidate : pick)
			if (candidate.zones[0] >= 0 || candidate.zones[1] >= 0)
			{
				const unsigned weight =
					candidate.category == divine_boon_category::experience ?
						35 :
						30;
				total += weight;
				if (number(1, total) <= static_cast<int>(weight))
					selected = candidate;
			}
		if (total)
			choices->push_back(selected);
	}

	const bool pvp = population[0].pvp_accounts && population[1].pvp_accounts && !has_pvp;
	if (diagnostic)
		diagnostic->pvp_eligible = pvp;
	if (pvp)
	{
		choices->emplace_back();
		choices->back().category = divine_boon_category::pvp;
	}

	if (!has_cargo)
	{
		// Validate each water route once per selection pass; the second scan only
		// chooses among these proved routes and relaxes the shared-side preference.
		std::vector<divine_boon_slot> routes;
		bool shared_route = false;
		for (int source = 0; source < NUM_PORTS; ++source)
			for (int destination = 0; destination < NUM_PORTS; ++destination)
			{
				divine_boon_slot route;
				route.category = divine_boon_category::cargo;
				route.source_port = route.cargo_commodity =
					route.contraband_commodity = source;
				route.destination_port = destination;
				if (!divine_boon_cargo_eligible(route) ||
				    cargo_sell_price(source) <= 0 ||
				    contra_sell_price(source) <= 0 ||
				    cargo_buy_price(destination, source) <=
					    cargo_sell_price(source) ||
				    contra_buy_price(destination, source) <=
					    contra_sell_price(source))
					continue;
				const int from = real_room(ports[source].loc_room),
					  to = real_room(ports[destination].loc_room);
				shared_route |= path_valid(from, 0) && path_valid(to, 0) &&
						path_valid(from, 1) && path_valid(to, 1);
				routes.push_back(route);
			}
		divine_boon_slot route;
		unsigned count = 0;
		for (const auto &candidate : routes)
		{
			const int from = real_room(ports[candidate.source_port].loc_room),
				  to = real_room(ports[candidate.destination_port].loc_room);
			if (shared_route && !(path_valid(from, 0) && path_valid(to, 0) &&
					      path_valid(from, 1) && path_valid(to, 1)))
				continue;
			if (number(1, ++count) == 1)
				route = candidate;
		}
		if (diagnostic)
			diagnostic->cargo_routes = count;
		if (count)
			choices->push_back(route);
	}

	if (diagnostic)
		diagnostic->sampled = true;
	return !choices->empty();
}
catch (const std::bad_alloc &)
{
	return false;
}

void divine_boon_selection_status(P_char ch)
{
	if (!ch || IS_NPC(ch) || !IS_TRUSTED(ch))
		return;
	refresh_paths();
	for (unsigned side = 0; side < 2; ++side)
	{
		unsigned exp = 0, epic = 0;
		for (const auto &zone : catalogue)
			if (suitable_level(zone, side) > 0)
			{
				exp += zone.experience;
				if (zone.experience)
					send_to_char_f(ch, "divine_exp side=%s zone=%d\r\n",
						       side ? "evil" : "good", zone.number);
				if (epic_target(zone, side))
				{
					++epic;
					send_to_char_f(ch,
						       "divine_target side=%s zone=%d group=%u\r\n",
						       side ? "evil" : "good", zone.number,
						       encounter_group(zone));
				}
			}
		send_to_char_f(ch, "divine_targets side=%s experience=%u epic=%u\r\n",
			       side ? "evil" : "good", exp, epic);
	}
	unsigned routes = 0, shared = 0;
	int first_source = -1, first_destination = -1;
	for (int source = 0; source < NUM_PORTS; ++source)
		for (int destination = 0; destination < NUM_PORTS; ++destination)
		{
			divine_boon_slot route;
			route.category = divine_boon_category::cargo;
			route.source_port = route.cargo_commodity = route.contraband_commodity =
				source;
			route.destination_port = destination;
			if (!divine_boon_cargo_eligible(route) || cargo_sell_price(source) <= 0 ||
			    contra_sell_price(source) <= 0 ||
			    cargo_buy_price(destination, source) <= cargo_sell_price(source) ||
			    contra_buy_price(destination, source) <= contra_sell_price(source))
				continue;
			++routes;
			const int from = real_room(ports[source].loc_room),
				  to = real_room(ports[destination].loc_room);
			shared += path_valid(from, 0) && path_valid(to, 0) && path_valid(from, 1) &&
				  path_valid(to, 1);
			if (first_source < 0)
			{
				first_source = source;
				first_destination = destination;
			}
		}
	send_to_char_f(ch,
		       "divine_routes count=%u shared=%u first_source=%d first_destination=%d\r\n",
		       routes, shared, first_source, first_destination);

	const auto *published = divine_boon_runtime_state();
	if (published)
		confirm_diagnostic(*published, divine_boon_runtime_pending());
	if (diagnostic_history.empty())
		send_to_char_f(ch, "divine_diag history=empty scope=current-boot\r\n");
	else
	{
		const auto &latest = diagnostic_history.back();
		send_to_char_f(
			ch, "divine_diag last_hour=%lld outcome=%s categories=%s revision=%llu\r\n",
			static_cast<long long>(latest.hour), latest.reason,
			category_list(latest.categories).c_str(),
			static_cast<unsigned long long>(latest.committed_revision));
		for (unsigned side = 0; side < latest.population.size(); ++side)
		{
			const auto &p = latest.population[side];
			send_to_char_f(ch,
				       "divine_diag side=%s active=%u online=%zu "
				       "levels=1-20:%u,21-35:%u,36-50:%u,51+:%u\r\n",
				       side ? "evil" : "good", p.active_accounts, p.levels.size(),
				       p.brackets[0], p.brackets[1], p.brackets[2], p.brackets[3]);
			send_to_char_f(
				ch,
				"divine_diag side=%s pvp=%u exp_candidates=%u epic_candidates=%u\r\n",
				side ? "evil" : "good", p.pvp_accounts,
				latest.experience_candidates[side], latest.epic_candidates[side]);
		}
		send_to_char_f(ch, "divine_diag sampled=%s pvp_eligible=%s cargo_routes=%u\r\n",
			       latest.sampled ? "yes" : "no", latest.pvp_eligible ? "yes" : "no",
			       latest.cargo_routes);
		for (const auto &item : diagnostic_history)
			send_to_char_f(ch,
				       "divine_diag recent hour=%lld outcome=%s categories=%s\r\n",
				       static_cast<long long>(item.hour), item.reason,
				       category_list(item.categories).c_str());
	}
	if (submitted_diagnostic)
		send_to_char_f(ch, "divine_diag hour=%lld status=pending-durable-write\r\n",
			       static_cast<long long>(submitted_diagnostic->hour));
	else if (prepared_diagnostic)
		send_to_char_f(ch, "divine_diag hour=%lld status=queue-refused\r\n",
			       static_cast<long long>(prepared_diagnostic->hour));
}

void divine_boon_selection_pulse(int64_t now)
try
{
	const auto *state = divine_boon_runtime_state();
	if (!state || state->mode != divine_boon_mode::divine || now < 0)
	{
		reward_revision = 0;
		return;
	}
	// Path validation allocates and walks world exits. Refresh at most once per
	// second (and after publication), never from a per-hit reward calculation.
	if (reward_revision != state->revision || reward_checked_at != now)
	{
		for (auto &side : reward_zones)
			side.fill(-1);
		for (size_t index = 0; index < state->slots.size(); ++index)
		{
			const auto &slot = state->slots[index];
			if (slot.category != divine_boon_category::experience ||
			    !divine_boon_active(slot, now))
				continue;
			for (unsigned side = 0; side < reward_zones.size(); ++side)
				if (slot.zones[side] >= 0 &&
				    divine_boon_zone_eligible(slot.zones[side], side))
					reward_zones[side][index] = slot.zones[side];
		}
		reward_revision = state->revision;
		reward_checked_at = now;
	}
	confirm_diagnostic(*state, divine_boon_runtime_pending());
	if (divine_boon_runtime_pending())
		return;
	const int64_t hour = now - now % DIVINE_BOON_HOUR;
	if (prepared_hour && prepared_hour->revision != state->revision + 1)
	{
		prepared_hour.reset(); // A staff mutation superseded this unsubmitted choice.
		prepared_diagnostic.reset();
	}
	if (hour <= state->last_opportunity)
		return;
	if (!prepared_hour || hour > prepared_hour->last_opportunity)
	{
		auto next = *state;
		std::vector<divine_boon_slot> choices;
		divine_boon_selection_diagnostic report;
		report.hour = hour;
		// A refused queue retains the exact choice for this hour. Once the hour
		// has passed, skip it and consume the present opportunity without RNG.
		if (prepared_hour || hour - state->last_opportunity != DIVINE_BOON_HOUR)
			report.reason = "missed-hour";
		else if (state->paused)
			report.reason = "paused";
		else
		{
			auto candidates = *state;
			divine_boon_reconcile(&candidates,
					      now); // Include just-expired repeat history.
			if (std::any_of(candidates.slots.begin(), candidates.slots.end(),
					[](const auto &slot) { return !slot.id; }))
			{
				const bool selected = divine_boon_select(
					candidates, now, divine_boon_activity_population(),
					&choices, &report);
				report.reason = selected       ? "generated" :
						report.sampled ? "no-eligible-category" :
								 "selector-unavailable";
			}
			else
				report.reason = "slots-full";
		}
		if (!divine_boon_rotate(&next, now, choices.data(), choices.size()))
			return;
		for (const auto &choice : choices)
			report.categories |= 1u << static_cast<unsigned>(choice.category);
		prepared_diagnostic = report;
		prepared_hour = std::move(next);
	}
	// New objectives carry IDs from the published next_id onward. Drop any whose
	// target became invalid before admission, keeping the rest; never reroll.
	std::vector<divine_boon_slot> valid;
	bool invalidated = false;
	for (const auto &slot : prepared_hour->slots)
	{
		if (!slot.id || slot.id < state->next_id)
			continue;
		bool targets_valid = slot.category != divine_boon_category::cargo ||
				     divine_boon_cargo_eligible(slot);
		for (unsigned side = 0; side < slot.zones.size(); ++side)
			if (slot.zones[side] >= 0 &&
			    !(slot.category == divine_boon_category::epic ?
				      divine_boon_epic_zone_eligible(slot.zones[side], side) :
				      divine_boon_zone_eligible(slot.zones[side], side)))
				targets_valid = false;
		if (!targets_valid)
		{
			invalidated = true;
			continue;
		}
		auto choice = slot;
		choice.id = 0;
		choice.starts_at = choice.expires_at = 0;
		valid.push_back(choice);
	}
	if (invalidated)
	{
		auto kept = *state;
		if (!divine_boon_rotate(&kept, now, valid.data(), valid.size()))
			return;
		prepared_hour = std::move(kept);
		if (prepared_diagnostic)
		{
			prepared_diagnostic->reason = "target-invalidated";
			prepared_diagnostic->categories = 0;
			for (const auto &choice : valid)
				prepared_diagnostic->categories |=
					1u << static_cast<unsigned>(choice.category);
		}
	}
	if (divine_boon_runtime_queue(*prepared_hour))
	{
		if (prepared_diagnostic)
		{
			prepared_diagnostic->committed_revision = prepared_hour->revision;
			submitted_diagnostic = *prepared_diagnostic;
		}
		prepared_diagnostic.reset();
		prepared_hour.reset();
	}
}
catch (const std::bad_alloc &)
{
	// No durable admission happened; published state remains the authority.
	logit(LOG_STATUS, "Divine Boon selection deferred: insufficient memory.");
}
