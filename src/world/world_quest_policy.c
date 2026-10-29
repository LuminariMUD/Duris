/****************************************************************************
 *
 *  File: world_quest_policy.c                                  Part of Duris
 *  Usage: world quest policy: zones, mob and reward profiles, intervals
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
#include "core/utils.h"
#include "combat/forced_movement.h"
#include "combat/justice.h"
#include "combat/trap.h"
#include "economy/tradeskill.h"
#include "item/objmisc.h"
#include "magic/spells.h"
#include "sql/sql.h"
#include "world/db.h"
#include "world/map.h"
#include "world/specs.prototypes.h"
#include "world/world_singletons.h"
#include "ships/ships.h"
#include "world/world_quest_policy.h"
#include "world/world_quest_policy_math.h"

#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <exception>
#include <cstdio>
#include <map>
#include <string>
#include <unordered_set>
#include <vector>

extern P_index mob_index;
extern P_index obj_index;
extern P_room world;
extern struct zone_data *zone_table;
extern int top_of_mobt;
extern int top_of_objt;
extern int top_of_zone_table;
extern int top_of_world;
extern int number_of_quests;
extern int number_of_shops;
extern shop_data *shop_index;
extern P_char character_list;
extern struct quest_data quest_index[];

extern int get_map_room(int zone_id);

namespace
{
constexpr int WORLD_QUEST_MAX_ZONE_NUMBER = 4000;

bool quest_spend_work(world_quest_route_context &context, size_t amount = 1)
{
	if (context.exhausted || amount > WORLD_QUEST_MAX_ROUTE_WORK - context.work)
	{
		context.exhausted = true;
		return false;
	}
	context.work += amount;
	return true;
}

enum class quest_route_mode
{
	current,
	capable,
	potential,
};

struct quest_route_builder
{
	using rooms = std::unordered_map<int, world_quest_route_context::room>;
	struct room_check
	{
		world_quest_route_status status = world_quest_route_status::unavailable;
		size_t objects = 0;
		unsigned trapped_directions = 0;
	};
	P_char ch;
	int level;
	quest_route_mode mode;
	world_quest_route_context &context;
	std::unordered_map<int, room_check> checked;
	std::unordered_map<int, int> geography;
	bool flight = false, boat = false, waterbreath = false;
	int local_region = 0;
	quest_route_builder(P_char actor, int accepted_level, quest_route_mode route_mode,
			    world_quest_route_context &request)
		: ch(actor)
		, level(accepted_level)
		, mode(route_mode)
		, context(request)
	{
	}

	bool spend(size_t amount = 1) { return quest_spend_work(context, amount); }

	bool valid_room(int room) const
	{
		return room >= 0 && room <= top_of_world && world[room].zone <= top_of_zone_table;
	}

	void unknown() { context.uncertain = true; }

	bool ordinary_mobile_proc(P_char mob, mob_proc_type proc)
	{
		// This classifies travel/door commands, not ASK. quester explicitly
		// handles ASK/TELL/GIVE only, and world_quest handles ASK only.
		if (proc == shop_keeper)
		{
			const size_t lookup_work = mob->only.npc->shopkeeper_shop_id < 0 ?
							   static_cast<size_t>(number_of_shops) :
							   1;
			if (!spend(lookup_work))
				return false;
			const int shop = singleton_shop_id(mob);
			if (shop < 0 || shop >= number_of_shops)
				return false;
			proc = shop_index[shop].func;
		}
		return !proc || proc == world_quest || proc == quester;
	}

	bool ordinary_object_proc(obj_proc_type proc) const
	{
		// board explicitly handles writing/reading/look/examine/removal only.
		// The hide artifact handles SAY; the regeneration ring handles RUB
		// and periodic ticks. Neither consumes travel, door or ASK commands.
		return !proc || proc == board || proc == artifact_hide ||
		       proc == ring_of_regeneration;
	}

	bool ordinary_space(int room) const
	{
		if (!valid_room(room))
			return false;
		const auto &entry = world[room];
		const auto &zone = zone_table[entry.zone];
		if (IS_SET(zone.flags, ZONE_CLOSED | ZONE_PRIVATE) ||
		    IS_SET(entry.room_flags, ROOM_LOCKER | ROOM_PRIVATE | ROOM_ARENA | ROOM_GUILD |
						     ROOM_JAIL | ROOM_ATRIUM))
			return false;
		if (zone.hometown < 0 || zone.hometown > LAST_HOME ||
		    (mode == quest_route_mode::current && zone.hometown &&
		     PC_NOTWELCOME(ch, zone.hometown)))
			return false;
		if ((IS_SET(entry.room_flags, ROOM_UNDERWATER) && !waterbreath) ||
		    ((entry.sector_type == SECT_UNDERWATER ||
		      entry.sector_type == SECT_UNDERWATER_GR) &&
		     !waterbreath) ||
		    ((entry.sector_type == SECT_NO_GROUND ||
		      entry.sector_type == SECT_UNDRWLD_NOGROUND) &&
		     !flight) ||
		    ((entry.sector_type == SECT_WATER_NOSWIM ||
		      entry.sector_type == SECT_UNDRWLD_NOSWIM) &&
		     !boat && !flight))
			return false;
		switch (entry.sector_type)
		{
		case SECT_FIREPLANE:
		case SECT_OCEAN:
		case SECT_AIR_PLANE:
		case SECT_WATER_PLANE:
		case SECT_EARTH_PLANE:
		case SECT_ETHEREAL:
		case SECT_ASTRAL:
		case SECT_UNDRWLD_LIQMITH:
		case SECT_NEG_PLANE:
		case SECT_PLANE_OF_AVERNUS:
		case SECT_LAVA:
		case SECT_CASTLE_WALL:
			return false;
		case SECT_UNDRWLD_LOWCEIL:
			// can_enter_room permits an ordinary kneel/crawl here. No actor
			// posture is changed while proving that the route is usable.
			return true;
		default:
			break;
		}
		return true;
	}

	room_check inspect_room(int room)
	{
		room_check result;
		if (!ordinary_space(room))
			return result;
		const auto &entry = world[room];
		result.status = world_quest_route_status::unproven;
		// inn and ship_shop_proc explicitly ignore movement, door commands and
		// arrival/departure hooks. Other procedures require a source audit.
		if (mode != quest_route_mode::potential &&
		    ((entry.funct && entry.funct != inn && entry.funct != ship_shop_proc) ||
		     entry.chance_fall || entry.current_speed || entry.affected))
			return result;
		for (P_char person = entry.people; person; person = person->next_in_room)
		{
			if (!spend())
				return result;
			if (person == ch)
				continue;
			// Occupied single-file movement can depend on list order, combat,
			// crawling and a retry. Do not pretend the graph alone proves it.
			if (mode != quest_route_mode::potential &&
			    IS_SET(entry.room_flags, ROOM_SINGLE_FILE))
				return result;
			if (!IS_NPC(person))
				continue;
			const int rnum = GET_RNUM(person);
			if (mode != quest_route_mode::potential &&
			    (rnum < 0 || rnum > top_of_mobt ||
			     !ordinary_mobile_proc(person, mob_index[rnum].func.mob) ||
			     !ordinary_mobile_proc(person, mob_index[rnum].qst_func)))
				return result;
		}
		for (P_obj object = entry.contents; object; object = object->next_content)
		{
			if (!spend())
				return result;
			++result.objects;
			if (mode != quest_route_mode::potential && object->R_num >= 0 &&
			    object->R_num <= top_of_objt &&
			    !ordinary_object_proc(obj_index[object->R_num].func.obj))
				return result;
			for (int direction = 0; direction < NUM_EXITS; ++direction)
				if (movement_trap_trigger(object, direction))
					result.trapped_directions |= 1u << direction;
		}
		result.status = world_quest_route_status::available;
		return result;
	}

	const room_check &room(int rnum)
	{
		const auto found = checked.find(rnum);
		if (found != checked.end())
			return found->second;
		if (checked.size() >= WORLD_QUEST_MAX_ROUTE_ROOMS)
			context.exhausted = true;
		return checked
			.emplace(rnum, context.exhausted ?
					       room_check{ world_quest_route_status::unproven } :
					       inspect_room(rnum))
			.first->second;
	}

	bool connection(int from, int direction)
	{
		if (!spend() || !valid_room(from))
			return false;
		const auto *edge = world[from].dir_option[direction];
		if (!edge || !valid_room(edge->to_room) ||
		    IS_SET(edge->exit_info, EX_SECRET | EX_BLOCKED | EX_WALLED | EX_LOCKED) ||
		    (IS_SET(edge->exit_info, EX_CLOSED) &&
		     (!IS_SET(edge->exit_info, EX_ISDOOR) || IS_SET(edge->exit_info, EX_SPIKED))) ||
		    check_castle_walls(from, edge->to_room) ||
		    map_entry_barrier(ch, from, edge->to_room) != forced_block::none)
			return false;
		return ordinary_space(from) && ordinary_space(edge->to_room);
	}

	bool exit(int from, int direction)
	{
		if (!connection(from, direction))
			return false;
		const auto *edge = world[from].dir_option[direction];
		const auto &source = room(from);
		const auto &target = room(edge->to_room);
		if (source.status == world_quest_route_status::unproven ||
		    target.status == world_quest_route_status::unproven)
			unknown();
		if (source.status != world_quest_route_status::available ||
		    target.status != world_quest_route_status::available ||
		    (source.trapped_directions & (1u << direction)))
			return false;
		// check_wall is read-only; charge its bounded object walk to this same
		// request rather than introducing a second wall implementation.
		return spend(source.objects) && !check_wall(from, direction);
	}

	void expand(int origin, rooms &visited, bool underdark_only)
	{
		visited.try_emplace(origin);
		std::vector<int> queue{ origin };
		for (size_t next = 0; next < queue.size() && !context.exhausted; ++next)
		{
			const int from = queue[next];
			for (int direction = 0; direction < NUM_EXITS; ++direction)
			{
				if (!(underdark_only ? connection(from, direction) :
						       exit(from, direction)))
					continue;
				const int to = world[from].dir_option[direction]->to_room;
				if (underdark_only ? !IS_UD_MAP(to) || !IS_MAP_ROOM(to) :
						     level <= WORLD_QUEST_LOCAL_MAX_LEVEL &&
							     region(to) != local_region)
					continue;
				if (visited.size() >= WORLD_QUEST_MAX_ROUTE_ROOMS &&
				    !visited.count(to))
				{
					context.exhausted = true;
					return;
				}
				auto [found, inserted] = visited.try_emplace(to);
				if (inserted)
				{
					found->second.map_entrance =
						IS_MAP_ROOM(from) && !IS_MAP_ROOM(to) ?
							from :
							visited.at(from).map_entrance;
					queue.push_back(to);
				}
				found->second.incoming.push_back(from);
			}
		}
	}

	void mark_returns(int origin, rooms &visited)
	{
		visited.at(origin).returns_to_origin = true;
		std::vector<int> queue{ origin };
		for (size_t next = 0; next < queue.size() && !context.exhausted; ++next)
			for (int from : visited.at(queue[next]).incoming)
			{
				if (!spend())
					return;
				auto &entry = visited.at(from);
				if (!entry.returns_to_origin)
				{
					entry.returns_to_origin = true;
					queue.push_back(from);
				}
			}
	}

	int region(int origin)
	{
		if (!valid_room(origin))
			return 0;
		if (IS_SURFACE_MAP(origin) && IS_MAP_ROOM(origin))
			return world[origin].continent > 0 &&
					       world[origin].continent <= NUM_CONTINENTS ?
				       world[origin].continent :
				       0;
		if (const auto found = geography.find(origin); found != geography.end())
			return found->second;
		if (IS_UD_MAP(origin) && IS_MAP_ROOM(origin))
		{
			rooms component;
			expand(origin, component, true);
			mark_returns(origin, component);
			// Only the directed map component containing this origin shares its
			// identity. An interior cannot merge disconnected Underdark maps.
			for (const auto &[rnum, entry] : component)
				if (entry.returns_to_origin)
					geography[rnum] = -origin - 1;
			return context.exhausted ? 0 : geography[origin];
		}
		if (IS_MAP_ROOM(origin))
			return 0;
		std::unordered_set<int> seen{ origin };
		std::vector<int> queue{ origin };
		int resolved = 0;
		bool conflicting = false;
		for (size_t next = 0; next < queue.size() && !context.exhausted; ++next)
		{
			for (int direction = 0; direction < NUM_EXITS; ++direction)
			{
				if (!connection(queue[next], direction))
					continue;
				const int to = world[queue[next]].dir_option[direction]->to_room;
				const auto cached = geography.find(to);
				if (IS_MAP_ROOM(to) || cached != geography.end())
				{
					const int boundary = cached != geography.end() ?
								     cached->second :
								     region(to);
					if (!boundary || (resolved && resolved != boundary))
						conflicting = true;
					else
						resolved = boundary;
				}
				else if (seen.insert(to).second)
				{
					if (seen.size() > WORLD_QUEST_MAX_ROUTE_ROOMS)
					{
						context.exhausted = true;
						break;
					}
					queue.push_back(to);
				}
			}
		}
		if (conflicting || context.exhausted)
			resolved = 0;
		if (resolved)
			for (int rnum : queue)
				geography[rnum] = resolved;
		else
			geography[origin] = 0;
		return resolved;
	}

	void build(int origin)
	{
		if (level > WORLD_QUEST_LOCAL_MAX_LEVEL)
		{
			flight = mode != quest_route_mode::current || IS_AFFECTED(ch, AFF_FLY);
			waterbreath = mode != quest_route_mode::current ||
				      IS_AFFECTED(ch, AFF_WATERBREATH);
			boat = mode != quest_route_mode::current;
			for (int slot = 0; slot < MAX_WEAR; ++slot)
				boat = boat || (ch->equipment[slot] &&
						ch->equipment[slot]->type == ITEM_BOAT);
		}
		// Inventory/equipment procedures intercept commands before room exits.
		for (P_obj object = ch->carrying; object; object = object->next_content)
		{
			if (!spend())
				return;
			if (level > WORLD_QUEST_LOCAL_MAX_LEVEL && object->type == ITEM_BOAT)
				boat = true;
			if (mode != quest_route_mode::potential && object->R_num >= 0 &&
			    object->R_num <= top_of_objt &&
			    !ordinary_object_proc(obj_index[object->R_num].func.obj))
			{
				unknown();
				return;
			}
		}
		for (int slot = 0; slot < MAX_WEAR; ++slot)
			if (mode != quest_route_mode::potential && ch->equipment[slot] &&
			    ch->equipment[slot]->R_num >= 0 &&
			    ch->equipment[slot]->R_num <= top_of_objt &&
			    !ordinary_object_proc(obj_index[ch->equipment[slot]->R_num].func.obj))
			{
				unknown();
				return;
			}
		if (level <= WORLD_QUEST_LOCAL_MAX_LEVEL)
		{
			local_region = region(origin);
			if (!local_region)
			{
				unknown();
				return;
			}
		}
		if (room(origin).status != world_quest_route_status::available)
		{
			if (room(origin).status == world_quest_route_status::unproven)
				unknown();
			return;
		}
		expand(origin, context.rooms, false);
		mark_returns(origin, context.rooms);
		if (level <= WORLD_QUEST_LOCAL_MAX_LEVEL && !IS_MAP_ROOM(origin))
		{
			// Geography considers potential ordinary connections through a town,
			// so an unknown shop in a side street cannot erase a proved region.
			// At least one map boundary must also have an actual proved route.
			const bool reached_map = std::any_of(context.rooms.begin(),
							     context.rooms.end(),
							     [](const auto &entry)
							     { return IS_MAP_ROOM(entry.first); });
			if (!reached_map)
			{
				context.rooms.clear();
				unknown();
			}
		}
	}
};

world_quest_route_context quest_build_routes(P_char ch, int origin_vnum, int level,
					     quest_route_mode mode, size_t work = 0)
{
	world_quest_route_context context;
	context.work = work;
	if (!ch || IS_NPC(ch) || !world || !zone_table || level < WORLD_QUEST_MIN_LEVEL ||
	    level >= TOTALLVLS)
	{
		context.uncertain = true;
		return context;
	}
	const int origin = origin_vnum > 0 ? real_room(origin_vnum) : NOWHERE;
	if (origin < 0 || origin > top_of_world)
	{
		context.uncertain = true;
		return context;
	}
	quest_route_builder builder(ch, level, mode, context);
	builder.build(origin);
	return context;
}

constexpr int WORLD_QUEST_EXPLICIT_DENY_ZONES[] = {
	0,
	292,
	914,
	536,
};

struct quest_mob_profile
{
	int rnum = -1;
	int vnum = -1;
	int level = -1;
	bool can_speak = false;
	bool invisible = false;
	bool hidden = false;
	bool combat_eligible = false;
};

struct quest_reward_profile
{
	int vnum = -1;
	int ivalue = 0;
};

struct quest_routine_source
{
	const quest_mob_profile *profile = nullptr;
	int room = NOWHERE;
	bool ordinary = false;
	bool conditional = false;
};

// The NPC's birthplace is its reset room VNUM. A mixed source at the same
// birthplace cannot identify an instance's provenance and stays ineligible.
std::unordered_map<int, std::unordered_map<int, quest_routine_source>> quest_sources;

struct zone_interval
{
	int bottom = 0;
	int top = 0;
	int zone = -1;
};

struct quest_zone_profile
{
	int number = -1;
	int runtime_average_level = -1;
	int64_t mob_level_sum = 0;
	int64_t mob_level_count = 0;
	double average_level = -1.0;
	int map_room = -1;
	std::vector<quest_mob_profile> mobs;
	std::vector<quest_reward_profile> rewards;
	std::vector<int> reward_vnums;
	std::array<std::vector<int>, TOTALLVLS> reward_vnums_by_level;
	std::array<int, TOTALLVLS> reward_count{};
	std::array<double, TOTALLVLS> reward_average{};
	std::array<double, TOTALLVLS> zone_score{};
};

std::vector<quest_zone_profile> quest_zones;
std::vector<zone_interval> quest_intervals;
bool quest_catalog_ready = false;
bool quest_catalog_failed = false;
bool quest_catalog_building = false;

struct mobile_probe_guard
{
	P_char value;
	~mobile_probe_guard()
	{
		if (value)
			extract_char(value);
	}
};

struct object_probe_guard
{
	P_obj value;
	~object_probe_guard()
	{
		if (value)
			extract_obj(value, FALSE);
	}
};

bool explicit_deny(int zone_number)
{
	for (const int denied : WORLD_QUEST_EXPLICIT_DENY_ZONES)
	{
		if (zone_number == denied)
			return true;
	}
	return false;
}

bool normal_zone(int zone_index)
{
	if (!zone_table || zone_index < 0 || zone_index > top_of_zone_table)
		return false;
	const int zone_number = zone_table[zone_index].number;
	return zone_number >= 0 && zone_number < WORLD_QUEST_MAX_ZONE_NUMBER;
}

bool valid_room_interval(int zone_index)
{
	if (!normal_zone(zone_index))
		return false;
	const zone_data &zone = zone_table[zone_index];
	return zone.real_bottom != NOWHERE && zone.real_top != NOWHERE && zone.real_bottom >= 0 &&
	       zone.real_top >= zone.real_bottom && zone.real_top <= top_of_world;
}

int zone_for_vnum(int vnum)
{
	if (quest_intervals.empty())
		return -1;
	const auto found = std::upper_bound(quest_intervals.begin(), quest_intervals.end(), vnum,
					    [](int value, const zone_interval &interval)
					    { return value < interval.bottom; });
	if (found == quest_intervals.begin())
		return -1;
	const auto candidate = found - 1;
	return vnum <= candidate->top ? candidate->zone : -1;
}

bool source_eligible_reward(P_obj obj)
{
	if (!obj)
		return false;
	if (IS_SET(obj->extra_flags, ITEM_NORENT) || IS_SET(obj->str_mask, STRUNG_KEYS) ||
	    !IS_SET(obj->wear_flags, ITEM_TAKE) || IS_SET(obj->extra_flags, ITEM_TRANSIENT))
		return false;
	if (obj->type != ITEM_WAND && obj->type != ITEM_STAFF && obj->type != ITEM_ARMOR &&
	    obj->type != ITEM_WORN && obj->type != ITEM_BOOK && obj->type != ITEM_QUIVER &&
	    obj->type != ITEM_INSTRUMENT && obj->type != ITEM_SPELLBOOK &&
	    obj->type != ITEM_TOTEM && obj->type != ITEM_SHIELD && obj->type != ITEM_FIREWEAPON &&
	    obj->type != ITEM_WEAPON && obj->type != ITEM_POTION)
		return false;
	if (IS_SET(obj->bitvector, AFF_STONE_SKIN) || IS_SET(obj->bitvector, AFF_HIDE) ||
	    IS_SET(obj->bitvector, AFF_SNEAK) || IS_SET(obj->bitvector, AFF_FLY) ||
	    IS_SET(obj->bitvector4, AFF4_NOFEAR) || IS_SET(obj->bitvector2, AFF2_AIR_AURA) ||
	    IS_SET(obj->bitvector2, AFF2_EARTH_AURA) ||
	    IS_SET(obj->bitvector3, AFF3_INERTIAL_BARRIER) ||
	    IS_SET(obj->bitvector3, AFF3_REDUCE) || IS_SET(obj->bitvector2, AFF2_GLOBE) ||
	    IS_SET(obj->bitvector, AFF_HASTE) || IS_SET(obj->bitvector, AFF_DETECT_INVISIBLE) ||
	    IS_SET(obj->bitvector4, AFF4_DETECT_ILLUSION))
		return false;
	if (IS_NOSHOW(obj) || GET_OBJ_WEIGHT(obj) > 99 || IS_ARTIFACT(obj) ||
	    isname("_noquest_", obj->name) || IS_OBJ_STAT2(obj, ITEM2_QUESTITEM))
		return false;
	return true;
}

struct reward_withholding
{
	size_t quest_items = 0;
	size_t top_value = 0;
};

// Every item a hand-built quest pays out or asks players to hand in. Bartender rewards
// never include these, whether or not a builder flagged them ITEM2_QUESTITEM.
std::unordered_set<int> collect_quest_item_vnums()
{
	std::unordered_set<int> vnums;
	for (int quest = 0; quest < number_of_quests; ++quest)
	{
		for (const quest_complete_data *complete = quest_index[quest].quest_complete;
		     complete; complete = complete->next)
		{
			for (const goal_data *goal = complete->receive; goal; goal = goal->next)
			{
				if (goal->goal_type == QUEST_GOAL_ITEM)
					vnums.insert(goal->number);
			}
			for (const goal_data *goal = complete->give; goal; goal = goal->next)
			{
				if (goal->goal_type == QUEST_GOAL_ITEM)
					vnums.insert(goal->number);
			}
		}
	}
	return vnums;
}

void build_intervals()
{
	quest_intervals.clear();
	quest_intervals.reserve(static_cast<size_t>(top_of_zone_table + 1));
	for (int zone = 0; zone <= top_of_zone_table; ++zone)
	{
		if (!valid_room_interval(zone))
			continue;
		quest_intervals.push_back({
			world[zone_table[zone].real_bottom].number,
			world[zone_table[zone].real_top].number,
			zone,
		});
	}
	std::sort(quest_intervals.begin(), quest_intervals.end(),
		  [](const zone_interval &left, const zone_interval &right)
		  {
			  if (left.bottom != right.bottom)
				  return left.bottom < right.bottom;
			  return left.top < right.top;
		  });
}

void load_mobile_profiles()
{
	for (int rnum = 0; rnum <= top_of_mobt; ++rnum)
	{
		const int zone = zone_for_vnum(mob_index[rnum].virtual_number);
		if (zone < 0)
			continue;

		mobile_probe_guard probe{ read_mobile_probe(mob_index[rnum].virtual_number,
							    VIRTUAL) };
		if (!probe.value)
			continue;

		quest_mob_profile profile;
		profile.rnum = rnum;
		profile.vnum = mob_index[rnum].virtual_number;
		profile.level = GET_LEVEL(probe.value);
		profile.combat_eligible = profile.level > 0 && profile.level < MAXLVL &&
					  GET_MAX_HIT(probe.value) > 1 &&
					  GET_EXP(probe.value) > 0 && !IS_SHOPKEEPER(probe.value) &&
					  !IS_SET(probe.value->specials.act,
						  ACT_TEACHER | ACT_GUILD_GOLEM | ACT_IGNORE);
		profile.can_speak = CAN_SPEAK(probe.value);
		profile.invisible = IS_AFFECTED(probe.value, AFF_INVISIBLE) ||
				    IS_AFFECTED2(probe.value, AFF2_CONCEALMENT) ||
				    IS_AFFECTED3(probe.value, AFF3_ECTOPLASMIC_FORM);
		profile.hidden = IS_AFFECTED(probe.value, AFF_HIDE);
		quest_zones[zone].mobs.push_back(profile);
		++quest_zones[zone].mob_level_count;
		quest_zones[zone].mob_level_sum += profile.level;
		quest_zones[zone].average_level =
			static_cast<double>(quest_zones[zone].mob_level_sum) /
			static_cast<double>(quest_zones[zone].mob_level_count);
	}
}

const quest_mob_profile *cached_mob_profile(int rnum)
{
	if (rnum < 0 || rnum > top_of_mobt)
		return nullptr;
	const int zone = zone_for_vnum(mob_index[rnum].virtual_number);
	if (zone < 0)
		return nullptr;
	for (const auto &profile : quest_zones[zone].mobs)
		if (profile.rnum == rnum)
			return &profile;
	return nullptr;
}

void load_routine_sources()
{
	quest_sources.clear();
	std::unordered_set<int> random_rooms;
	for (int zone = 0; zone <= top_of_zone_table; ++zone)
		for (const reset_com *cmd = zone_table[zone].cmd; cmd && cmd->command != 'S'; ++cmd)
		{
			if (cmd->arg3 < 0 || cmd->arg3 > top_of_world)
				continue;
			if (cmd->command == 'Y')
			{
				// A random-table load at the same birthplace makes instance
				// provenance ambiguous without evaluating or rolling the table.
				random_rooms.insert(cmd->arg3);
				continue;
			}
			if (cmd->command != 'M' && cmd->command != 'F' && cmd->command != 'R')
				continue;
			const auto *profile = cached_mob_profile(cmd->arg1);
			if (!profile)
				continue;
			auto &source = quest_sources[cmd->arg1][world[cmd->arg3].number];
			source.profile = profile;
			source.room = cmd->arg3;
			const bool ordinary = cmd->command == 'M' &&
					      zone_table[zone].reset_mode > 0 && !cmd->if_flag &&
					      cmd->arg2 > 0 && cmd->arg4 == 100;
			source.ordinary = source.ordinary || ordinary;
			source.conditional = source.conditional || !ordinary;
		}
	for (auto &[rnum, placements] : quest_sources)
	{
		(void)rnum;
		for (auto &[birthplace, source] : placements)
		{
			(void)birthplace;
			if (random_rooms.count(source.room))
				source.conditional = true;
		}
	}
}

const quest_routine_source *routine_source(P_char mob)
{
	const auto prototype = quest_sources.find(GET_RNUM(mob));
	if (prototype == quest_sources.end())
		return nullptr;
	const auto source = prototype->second.find(GET_BIRTHPLACE(mob));
	if (source == prototype->second.end() || !source->second.ordinary ||
	    source->second.conditional)
		return nullptr;
	return &source->second;
}

void load_reward_profiles(reward_withholding &withheld)
{
	const std::unordered_set<int> quest_items = collect_quest_item_vnums();
	for (int rnum = 0; rnum <= top_of_objt; ++rnum)
	{
		const int zone = zone_for_vnum(obj_index[rnum].virtual_number);
		if (zone < 0)
			continue;

		object_probe_guard probe{ read_object(obj_index[rnum].virtual_number, VIRTUAL) };
		if (!probe.value)
			continue;
		if (!source_eligible_reward(probe.value))
			continue;
		if (quest_items.count(obj_index[rnum].virtual_number))
		{
			++withheld.quest_items;
			continue;
		}
		quest_reward_profile profile;
		profile.vnum = obj_index[rnum].virtual_number;
		profile.ivalue = itemvalue(probe.value);
		quest_zones[zone].rewards.push_back(profile);
	}

	// A zone's most valuable items are earned in the zone, not bought from a bartender.
	// They are withheld before the per-level lists and zone scores are built, so both
	// describe only what a quest can actually pay.
	const int withheld_percent = BOUNDED(
		0,
		static_cast<int>(get_property("world.quest.reward.top.withheld.percent", 20.000)),
		100);
	for (quest_zone_profile &zone : quest_zones)
	{
		std::vector<int> values;
		values.reserve(zone.rewards.size());
		for (const quest_reward_profile &reward : zone.rewards)
			values.push_back(reward.ivalue);
		const int ceiling = world_quest_reward_value_ceiling(values, withheld_percent);

		std::vector<quest_reward_profile> offered;
		offered.reserve(zone.rewards.size());
		for (const quest_reward_profile &reward : zone.rewards)
		{
			if (reward.ivalue >= ceiling)
			{
				++withheld.top_value;
				continue;
			}
			offered.push_back(reward);
			zone.reward_vnums.push_back(reward.vnum);
		}
		zone.rewards.swap(offered);

		for (const quest_reward_profile &reward : zone.rewards)
		{
			for (int level = 1; level < TOTALLVLS; ++level)
			{
				if (!world_quest_item_passes_floor(level, reward.ivalue))
					continue;
				zone.reward_vnums_by_level[level].push_back(reward.vnum);
				zone.reward_count[level]++;
				zone.reward_average[level] += reward.ivalue;
			}
		}
		for (int level = 1; level < TOTALLVLS; ++level)
		{
			if (zone.reward_count[level] > 0)
				zone.reward_average[level] /= zone.reward_count[level];
		}
	}
}

void load_zone_scores()
{
	for (quest_zone_profile &zone : quest_zones)
		for (int level = 1; level < TOTALLVLS; ++level)
			zone.zone_score[level] = world_quest_zone_raw_score(
				level, zone.average_level, zone.reward_average[level],
				zone.reward_count[level]);
}

bool static_zone_eligibility(int zone, int level)
{
	if (zone < 0 || zone > top_of_zone_table || !normal_zone(zone))
		return false;
	const quest_zone_profile &profile = quest_zones[zone];
	if (explicit_deny(profile.number) || IS_SET(zone_table[zone].flags, ZONE_TOWN) ||
	    zone_table[zone].hometown != 0 || profile.runtime_average_level < 0)
		return false;
	if (level < WORLD_QUEST_MIN_LEVEL || level >= TOTALLVLS)
		return false;
	if (!world_quest_zone_level_window_accepts(level, profile.runtime_average_level))
		return false;
	if (profile.map_room < 0 && level < WORLD_QUEST_MAPLESS_MIN_LEVEL)
		return false;
	return profile.reward_count[level] > 0;
}

struct quest_target_request
{
	P_char actor;
	int level;
	world_quest_route_context routes;
	std::map<int, std::map<int, std::vector<P_char>>> mobs;
	std::unordered_map<int, size_t> population;
	int probes = WORLD_QUEST_MAX_TARGET_PROBES;
	int history_checks = WORLD_QUEST_MAX_HISTORY_CHECKS;
	std::unordered_map<int, int> history;
	std::map<int, std::vector<int>> tried;

	quest_target_request(P_char ch, int origin, int accepted_level, int accepted_target = 0)
		: actor(ch)
		, level(accepted_level)
		, routes(accepted_target ? world_quest_route_context{} :
					   world_quest_policy_routes(ch, origin, accepted_level))
	{
		if (routes.exhausted || (!accepted_target && routes.rooms.empty()))
			return;
		for (P_char mob = character_list; mob; mob = mob->next)
		{
			if (!quest_spend_work(routes))
				break;
			if (mob->in_room >= 0 && mob->in_room <= top_of_world)
				++population[mob->in_room];
			const bool match = accepted_target ?
						   IS_NPC(mob) && IS_ALIVE(mob) &&
							   mob->in_room >= 0 &&
							   mob->in_room <= top_of_world &&
							   GET_RNUM(mob) >= 0 &&
							   GET_RNUM(mob) <= top_of_mobt &&
							   GET_VNUM(mob) == accepted_target :
						   common(mob);
			if (match)
				mobs[world[mob->in_room].zone][GET_RNUM(mob)].push_back(mob);
		}
		if (routes.exhausted)
			mobs.clear();
	}

	bool controlled(P_char mob) const
	{
		return mob->following || GET_MASTER(mob) || mob->only.npc->summoned_instance ||
		       mob->only.npc->summon_kind != 0 || IS_AFFECTED(mob, AFF_CHARM) ||
		       affected_by_spell(mob, TAG_CONJURED_PET);
	}

	bool ordinary_instance(P_char mob) const
	{
		if (!IS_NPC(mob) || !IS_ALIVE(mob) || mob->in_room < 0 ||
		    mob->in_room > top_of_world || GET_RNUM(mob) < 0 ||
		    GET_RNUM(mob) > top_of_mobt || GET_HIT(mob) <= 0)
			return false;
		const auto *source = routine_source(mob);
		return source && source->room >= 0 && source->room <= top_of_world &&
		       world[source->room].number == GET_BIRTHPLACE(mob) &&
		       world[source->room].zone == world[mob->in_room].zone &&
		       source->profile->vnum == GET_VNUM(mob) &&
		       static_zone_eligibility(world[mob->in_room].zone, level) &&
		       source->profile->level >= level - 4 && source->profile->level <= level + 5 &&
		       GET_LEVEL(mob) >= level - 4 && GET_LEVEL(mob) <= level + 5;
	}

	bool reachable(P_char mob) const
	{
		return world_quest_policy_route(routes, routine_source(mob)->room) ==
			       world_quest_route_status::available &&
		       world_quest_policy_route(routes, mob->in_room) ==
			       world_quest_route_status::available;
	}

	bool common(P_char mob) const
	{
		return ordinary_instance(mob) && !controlled(mob) && reachable(mob);
	}

	bool actor_can_ask() const
	{
		return CAN_SPEAK(actor) && !IS_AFFECTED(actor, AFF_WRAITHFORM) &&
		       !IS_AFFECTED2(actor, AFF2_SILENCED) &&
		       !IS_SET(actor->specials.act, PLR_SILENCE) &&
		       !affected_by_spell_flagged(actor, SKILL_THROAT_CRUSH, AFFTYPE_CUSTOM1);
	}

	bool ask_handler(P_char mob, mob_proc_type proc)
	{
		if (!proc)
			return true;
		if (proc != shop_keeper)
			return false;
		const size_t lookup_work = mob->only.npc->shopkeeper_shop_id < 0 ?
						   static_cast<size_t>(number_of_shops) :
						   1;
		if (!quest_spend_work(routes, lookup_work))
			return false;
		const int shop = singleton_shop_id(mob);
		// Travel-safe quest handlers may consume ASK before do_ask reaches
		// quest_ask. A shop with no delegate explicitly ignores ASK.
		return shop >= 0 && shop < number_of_shops && !shop_index[shop].func;
	}

	bool world_type_eligible(P_char mob, int type)
	{
		const auto &profile = *routine_source(mob)->profile;
		const int room = mob->in_room;
		if (mob->specials.z_cord != 0)
			return false;
		if (type == FIND_AND_KILL)
			return profile.combat_eligible && GET_MAX_HIT(mob) > 1 &&
			       GET_EXP(mob) > 0 && !IS_SHOPKEEPER(mob) &&
			       !IS_SET(mob->specials.act,
				       ACT_TEACHER | ACT_GUILD_GOLEM | ACT_IGNORE) &&
			       !IS_SET(world[room].room_flags, ROOM_SAFE) &&
			       !IS_SET(zone_table[world[room].zone].flags, ZONE_SAFE);
		if (mob_index[GET_RNUM(mob)].number != 1 || !profile.can_speak ||
		    profile.level >= MAXLVL || !CAN_SPEAK(mob) || !IS_AWAKE(mob) ||
		    IS_AFFECTED2(mob, AFF2_SILENCED) ||
		    IS_SET(world[room].room_flags, ROOM_SILENT | ROOM_UNDERWATER) ||
		    IS_SET(zone_table[world[room].zone].flags, ZONE_SILENT) ||
		    world[room].sector_type == SECT_UNDERWATER ||
		    world[room].sector_type == SECT_UNDERWATER_GR)
			return false;
		if (level < 31 && (profile.invisible || profile.hidden ||
				   IS_AFFECTED(mob, AFF_INVISIBLE | AFF_HIDE) ||
				   IS_AFFECTED2(mob, AFF2_CONCEALMENT) ||
				   IS_AFFECTED3(mob, AFF3_ECTOPLASMIC_FORM)))
			return false;
		return true;
	}

	bool handlers_eligible(P_char mob)
	{
		return ask_handler(mob, mob_index[GET_RNUM(mob)].func.mob) &&
		       ask_handler(mob, mob_index[GET_RNUM(mob)].qst_func);
	}

	bool type_eligible(P_char mob, int type)
	{
		return world_type_eligible(mob, type) &&
		       (type != FIND_AND_ASK || (actor_can_ask() && handlers_eligible(mob)));
	}

	int suggest(int zone, int type, int minimum)
	{
		std::vector<int> candidates;
		const auto &excluded = tried[zone];
		for (const auto &[rnum, instances] : mobs.at(zone))
		{
			if (!quest_spend_work(routes))
				break;
			const int vnum = mob_index[rnum].virtual_number;
			if (std::find(excluded.begin(), excluded.end(), vnum) != excluded.end())
				continue;
			const auto completed = history.find(vnum);
			if ((completed != history.end() && completed->second > 0) ||
			    (completed == history.end() && history_checks <= 0))
				continue;
			int count = 0;
			for (P_char mob : instances)
			{
				if (!quest_spend_work(routes))
					break;
				if (common(mob) && type_eligible(mob, type))
					++count;
			}
			if ((type == FIND_AND_KILL && count >= minimum) ||
			    (type == FIND_AND_ASK && count == 1))
				candidates.push_back(vnum);
		}
		if (routes.exhausted || candidates.empty())
			return -1;
		return candidates[number(0, static_cast<int>(candidates.size()) - 1)];
	}

	bool validate(int zone, int vnum, int type, world_quest_target &target, int minimum)
	{
		if (probes <= 0)
			return false;
		--probes;
		const int rnum = real_mobile(vnum);
		const auto prototype = mobs.at(zone).find(rnum);
		if (prototype == mobs.at(zone).end())
			return false;
		world_quest_target checked;
		checked.zone = zone;
		checked.mob_vnum = vnum;
		checked.type = type;
		for (P_char mob : prototype->second)
		{
			if (!quest_spend_work(routes))
				break;
			if (!common(mob) || !type_eligible(mob, type))
				continue;
			// Bound the lighting/aura walks in the existing visibility
			// predicate as well as this request's one live-character scan.
			if (!quest_spend_work(routes, 8 * (population.at(mob->in_room) + 1)))
				break;
			if (!ac_can_see_from(actor, mob, mob->in_room))
				continue;
			if (type == FIND_AND_ASK && aggressive_to_at(mob, actor, mob->in_room))
				continue;
			if (checked.usable_count++ == 0)
				checked.map_room =
					world_quest_policy_map_room(routes, mob->in_room);
		}
		if (routes.exhausted || (type == FIND_AND_KILL ? checked.usable_count < minimum :
								 checked.usable_count != 1))
			return false;
		target = checked;
		return true;
	}
};

} // namespace

world_quest_target_check world_quest_policy_check_target(P_char ch, int origin_vnum,
							 int accepted_level, int zone_number,
							 int mob_vnum, int type, int needed)
{
	using status = world_quest_target_status;
	world_quest_target_check result;
	if (!ch || IS_NPC(ch) || !world_quest_policy_bootstrap() ||
	    accepted_level < WORLD_QUEST_MIN_LEVEL || accepted_level >= TOTALLVLS ||
	    (type != FIND_AND_ASK && type != FIND_AND_KILL) || needed < 1)
		return result;
	const int zone = real_zone(zone_number);
	if (zone < 0 || !static_zone_eligibility(zone, accepted_level) || real_mobile(mob_vnum) < 0)
	{
		result.status = status::unavailable;
		return result;
	}

	quest_target_request request(ch, origin_vnum, accepted_level, mob_vnum);
	auto finish = [&](status value)
	{
		result.status = value;
		result.work = request.routes.work;
		return result;
	};
	if (request.routes.exhausted)
		return finish(status::unproven);
	struct candidate
	{
		P_char mob;
		status interaction;
	};
	std::vector<candidate> candidates;
	const auto found = request.mobs.find(zone);
	if (found != request.mobs.end())
		for (const auto &[rnum, instances] : found->second)
		{
			(void)rnum;
			for (P_char mob : instances)
			{
				if (!quest_spend_work(request.routes))
					return finish(status::unproven);
				if (!request.ordinary_instance(mob) ||
				    !request.world_type_eligible(mob, type))
					continue;
				status interaction = status::valid;
				if (request.controlled(mob) ||
				    (type == FIND_AND_ASK && !request.actor_can_ask()))
					interaction = status::blocked;
				else if (type == FIND_AND_ASK && !request.handlers_eligible(mob))
					interaction = status::unproven;
				else
				{
					if (!quest_spend_work(
						    request.routes,
						    8 * (request.population.at(mob->in_room) + 1)))
						return finish(status::unproven);
					if (!ac_can_see_from(ch, mob, mob->in_room))
						interaction = status::blocked;
					else if (type == FIND_AND_ASK &&
						 aggressive_to_at(mob, ch, mob->in_room))
						// Aggression can depend on memory, faction or random
						// player protection. It cannot alone authorize a reroll.
						interaction = status::unproven;
				}
				candidates.push_back({ mob, interaction });
			}
		}
	if (request.routes.exhausted)
		return finish(status::unproven);
	if (static_cast<int>(candidates.size()) < needed)
		return finish(status::unavailable);
	if (origin_vnum <= 0)
		return finish(status::needs_origin);
	if (real_room(origin_vnum) < 0)
		return finish(status::unavailable);

	const size_t scan_work = request.routes.work;
	for (quest_route_mode mode :
	     { quest_route_mode::current, quest_route_mode::capable, quest_route_mode::potential })
	{
		request.routes = quest_build_routes(
			ch, origin_vnum, accepted_level, mode,
			mode == quest_route_mode::current ? scan_work : request.routes.work);
		if (request.routes.exhausted)
			return finish(status::unproven);
		int valid = 0, blocked = 0, uncertain = 0, possible = 0;
		for (const auto &candidate : candidates)
		{
			if (!quest_spend_work(request.routes))
				return finish(status::unproven);
			if (!request.reachable(candidate.mob))
				continue;
			++possible;
			if (candidate.interaction == status::valid)
			{
				if (valid++ == 0 && mode == quest_route_mode::current)
					result.map_room = world_quest_policy_map_room(
						request.routes, candidate.mob->in_room);
			}
			else if (candidate.interaction == status::blocked)
				++blocked;
			else
				++uncertain;
		}
		if (mode == quest_route_mode::current && valid >= needed)
			return finish(status::valid);
		if (mode != quest_route_mode::potential)
		{
			if (valid + blocked >= needed)
				return finish(status::blocked);
			if (valid + blocked + uncertain >= needed)
				return finish(status::unproven);
		}
		else if (!request.routes.uncertain && possible < needed)
			return finish(status::unavailable);
	}
	return finish(status::unproven);
}

world_quest_route_context world_quest_policy_routes(P_char ch, int origin_vnum, int accepted_level)
{
	return quest_build_routes(ch, origin_vnum, accepted_level, quest_route_mode::current);
}

world_quest_route_status world_quest_policy_route(const world_quest_route_context &context,
						  int room)
{
	if (context.exhausted)
		return world_quest_route_status::unproven;
	const auto found = context.rooms.find(room);
	if (found != context.rooms.end() && found->second.returns_to_origin)
		return world_quest_route_status::available;
	return context.uncertain ? world_quest_route_status::unproven :
				   world_quest_route_status::unavailable;
}

int world_quest_policy_map_room(const world_quest_route_context &context, int room)
{
	if (world_quest_policy_route(context, room) != world_quest_route_status::available)
		return NOWHERE;
	return context.rooms.at(room).map_entrance;
}

bool world_quest_policy_bootstrap()
{
	if (quest_catalog_ready || quest_catalog_failed)
		return quest_catalog_ready;
	if (quest_catalog_building || !zone_table || !world || !mob_index || !obj_index ||
	    top_of_zone_table < 0 || top_of_mobt < 0 || top_of_objt < 0)
		return false;

	quest_catalog_building = true;
	const auto started = std::chrono::steady_clock::now();
	try
	{
		quest_zones.clear();
		quest_zones.resize(static_cast<size_t>(top_of_zone_table + 1));
		for (int zone = 0; zone <= top_of_zone_table; ++zone)
			quest_zones[zone].number = zone_table[zone].number;
		build_intervals();
		load_mobile_profiles();
		for (quest_zone_profile &zone : quest_zones)
		{
			if (zone.mob_level_count > 0)
			{
				zone.average_level = static_cast<double>(zone.mob_level_sum) /
						     static_cast<double>(zone.mob_level_count);
				zone.runtime_average_level = world_quest_truncated_average_level(
					zone.mob_level_sum, zone.mob_level_count);
			}
			if (zone.runtime_average_level >= 0)
				zone_table[&zone - quest_zones.data()].avg_mob_level =
					zone.runtime_average_level;
			else if (normal_zone(static_cast<int>(&zone - quest_zones.data())))
				zone_table[&zone - quest_zones.data()].avg_mob_level = -1;
		}
		for (int zone = 0; zone <= top_of_zone_table; ++zone)
		{
			if (!valid_room_interval(zone))
				continue;
			quest_zones[zone].map_room = get_map_room(zone);
		}
		reward_withholding withheld;
		load_reward_profiles(withheld);
		load_zone_scores();
		load_routine_sources();
		quest_catalog_ready = true;
		const auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(
			std::chrono::steady_clock::now() - started);
		size_t mob_profiles = 0;
		size_t reward_profiles = 0;
		int mapless_zones = 0;
		for (const quest_zone_profile &zone : quest_zones)
		{
			mob_profiles += zone.mobs.size();
			reward_profiles += zone.rewards.size();
			if (zone.map_room < 0)
				++mapless_zones;
		}
		logit(LOG_STATUS,
		      "World quest catalog ready: zones=%d mobile_profiles=%zu reward_profiles=%zu "
		      "mapless_zones=%d elapsed_ms=%lld withheld_quest_items=%zu "
		      "withheld_top_value=%zu",
		      top_of_zone_table + 1, mob_profiles, reward_profiles, mapless_zones,
		      static_cast<long long>(elapsed.count()), withheld.quest_items,
		      withheld.top_value);
		fprintf(stderr,
			"World quest catalog ready: zones=%d mobile_profiles=%zu reward_profiles=%zu "
			"mapless_zones=%d elapsed_ms=%lld withheld_quest_items=%zu "
			"withheld_top_value=%zu\n",
			top_of_zone_table + 1, mob_profiles, reward_profiles, mapless_zones,
			static_cast<long long>(elapsed.count()), withheld.quest_items,
			withheld.top_value);
	}
	catch (const std::exception &error)
	{
		quest_zones.clear();
		quest_intervals.clear();
		quest_sources.clear();
		quest_catalog_failed = true;
		logit(LOG_EXIT, "World quest catalog failed closed: %s", error.what());
		fprintf(stderr, "World quest catalog failed closed: %s\n", error.what());
	}
	quest_catalog_building = false;
	return quest_catalog_ready;
}

int world_quest_policy_combat_level(int mob_rnum)
{
	if (!quest_catalog_ready)
		return -1;
	const auto *profile = cached_mob_profile(mob_rnum);
	return profile && profile->combat_eligible ? profile->level : -1;
}

bool world_quest_policy_zone_is_invalid(int zone_number)
{
	if (!world_quest_policy_bootstrap())
		return true;
	for (int zone = 0; zone <= top_of_zone_table; ++zone)
	{
		if (quest_zones[zone].number != zone_number)
			continue;
		return !normal_zone(zone) || explicit_deny(zone_number) ||
		       IS_SET(zone_table[zone].flags, ZONE_TOWN) ||
		       zone_table[zone].hometown != 0 ||
		       quest_zones[zone].runtime_average_level < 0;
	}
	return true;
}

void world_quest_policy_zone_list(P_char ch, std::vector<int> &valid_zones)
{
	valid_zones.clear();
	if (!world_quest_policy_bootstrap() || !ch)
		return;
	for (int zone = 0; zone <= top_of_zone_table; ++zone)
	{
		if (static_zone_eligibility(zone, GET_LEVEL(ch)))
			valid_zones.push_back(zone);
	}
}

int world_quest_policy_select_zone(int level, const std::vector<int> &valid_zones)
{
	if (valid_zones.empty() || !world_quest_policy_bootstrap())
		return -1;
	if (level < 1 || level >= TOTALLVLS)
		return -1;
	double total = 0.0;
	for (const int zone : valid_zones)
	{
		if (zone < 0 || zone > top_of_zone_table)
			continue;
		const quest_zone_profile &profile = quest_zones[zone];
		total += profile.zone_score[level];
	}
	if (total <= 0.0)
		return -1;

	double roll = static_cast<double>(number(1, 1000000)) / 1000000.0 * total;
	for (const int zone : valid_zones)
	{
		if (zone < 0 || zone > top_of_zone_table)
			continue;
		const quest_zone_profile &profile = quest_zones[zone];
		const double weight = profile.zone_score[level];
		if (weight <= 0.0)
			continue;
		if (roll <= weight)
			return zone;
		roll -= weight;
	}
	return valid_zones.back();
}

quest_creation_failure world_quest_policy_select_target(P_char ch, int origin_vnum,
							int accepted_level,
							world_quest_target &target,
							int required_type, int needed)
{
	target = {};
	if (!ch || IS_NPC(ch) || origin_vnum <= 0 || real_room(origin_vnum) == NOWHERE ||
	    (required_type && required_type != FIND_AND_KILL && required_type != FIND_AND_ASK) ||
	    needed < 0)
		return QUEST_CREATION_INVALID_ACTOR;
	if (!world_quest_policy_bootstrap())
		return QUEST_CREATION_NO_ELIGIBLE_ZONE;
	bool eligible_zone = false;
	for (int zone = 0; zone <= top_of_zone_table; ++zone)
		eligible_zone = eligible_zone || static_zone_eligibility(zone, accepted_level);
	if (!eligible_zone)
		return QUEST_CREATION_NO_ELIGIBLE_ZONE;

	quest_target_request request(ch, origin_vnum, accepted_level);
	std::vector<int> remaining_zones;
	for (const auto &[zone, mobs] : request.mobs)
	{
		(void)mobs;
		remaining_zones.push_back(zone);
	}
	while (!remaining_zones.empty() && request.probes > 0 && !request.routes.exhausted)
	{
		const int zone = world_quest_policy_select_zone(accepted_level, remaining_zones);
		if (zone < 0)
			break;
		remaining_zones.erase(
			std::find(remaining_zones.begin(), remaining_zones.end(), zone));
		const int first_type = required_type	   ? required_type :
				       accepted_level > 49 ? FIND_AND_KILL :
							     number(1, 2);
		const int type_attempts = required_type || accepted_level > 49 ? 1 : 2;
		for (int attempt = 0; attempt < type_attempts; ++attempt)
		{
			const int type = attempt == 0 ?
						 first_type :
						 (first_type == FIND_AND_KILL ? FIND_AND_ASK :
										FIND_AND_KILL);
			while (request.probes > 0 && !request.routes.exhausted)
			{
				const int minimum = needed > 0		  ? needed :
						    type == FIND_AND_KILL ? 2 :
									    1;
				const int vnum = request.suggest(zone, type, minimum);
				if (vnum <= 0)
					break;
				request.tried[zone].push_back(vnum);
				auto completed = request.history.find(vnum);
				if (completed == request.history.end())
				{
					--request.history_checks;
					const int done = sql_world_quest_done_already(ch, vnum);
					if (done < 0)
						return QUEST_CREATION_NO_ELIGIBLE_TARGET;
					completed = request.history.emplace(vnum, done).first;
				}
				if (completed->second > 0)
					continue;
				// Do the real live check after the history read, immediately
				// before publishing the assignment. No prototype probe or
				// movement/interaction command is run on this path.
				if (request.validate(zone, vnum, type, target, minimum))
					return QUEST_CREATION_NO_FAILURE;
			}
		}
	}
	return QUEST_CREATION_NO_ELIGIBLE_TARGET;
}

int world_quest_policy_random_item(int zone_number)
{
	if (!world_quest_policy_bootstrap() || zone_number < 0 || zone_number > top_of_zone_table)
		return -1;
	const std::vector<int> &items = quest_zones[zone_number].reward_vnums;
	if (items.empty())
		return -1;
	return items[number(0, static_cast<int>(items.size()) - 1)];
}

int world_quest_policy_random_quest_item(int zone_number, int quest_level)
{
	if (!world_quest_policy_bootstrap() || zone_number < 0 || zone_number > top_of_zone_table ||
	    quest_level <= 0 || quest_level >= TOTALLVLS)
		return -1;
	const std::vector<int> &items = quest_zones[zone_number].reward_vnums_by_level[quest_level];
	if (items.empty())
		return -1;
	return items[number(0, static_cast<int>(items.size()) - 1)];
}
