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
#include "magic/spells.h"
#include "sql/sql.h"
#include "world/db.h"
#include "world/map.h"
#include "world/specs.prototypes.h"
#include "world/world_singletons.h"
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

struct quest_work
{
	size_t work = 0;
	bool exhausted = false;
};

bool quest_spend_work(quest_work &context, size_t amount = 1)
{
	if (context.exhausted || amount > WORLD_QUEST_MAX_TARGET_WORK - context.work)
	{
		context.exhausted = true;
		return false;
	}
	context.work += amount;
	return true;
}

struct quest_zone_geography
{
	world_quest_region region;
	std::vector<int> entrances;
};

std::vector<quest_zone_geography> quest_geography;
std::vector<int> quest_underdark;

bool quest_valid_room(int room)
{
	return room >= 0 && room <= top_of_world && world[room].zone <= top_of_zone_table;
}

world_quest_region quest_map_region(int room)
{
	if (!quest_valid_room(room) || !IS_MAP_ROOM(room))
		return {};
	if (IS_SURFACE_MAP(room))
		return { world[room].continent > 0 && world[room].continent <= NUM_CONTINENTS ?
				 world[room].continent :
				 0,
			 0 };
	if (IS_UD_MAP(room))
		return { 0, quest_underdark[room] };
	return {};
}

// Geography uses authored adjacency only. No player facts, movement predicates,
// reverse-route proof, scripts, flags, terrain or request work budget participate.
void build_geography()
{
	quest_geography.assign(top_of_zone_table + 1, {});
	quest_underdark.assign(top_of_world + 1, 0);
	std::vector<int> parent(top_of_world + 1);
	for (int room = 0; room <= top_of_world; ++room)
		parent[room] = room;
	auto root = [&](int room)
	{
		while (parent[room] != room)
		{
			parent[room] = parent[parent[room]];
			room = parent[room];
		}
		return room;
	};
	for (int room = 0; room <= top_of_world; ++room)
		if (quest_valid_room(room) && IS_MAP_ROOM(room) && IS_UD_MAP(room))
			for (const auto *edge : world[room].dir_option)
				if (edge && quest_valid_room(edge->to_room) &&
				    IS_MAP_ROOM(edge->to_room) && IS_UD_MAP(edge->to_room))
				{
					const int first = root(room), second = root(edge->to_room);
					parent[std::max(first, second)] = std::min(first, second);
				}
	for (int room = 0; room <= top_of_world; ++room)
		if (quest_valid_room(room) && IS_MAP_ROOM(room) && IS_UD_MAP(room))
			quest_underdark[room] = root(room) + 1;

	std::vector<std::vector<int>> neighbors(top_of_zone_table + 1);
	for (int room = 0; room <= top_of_world; ++room)
	{
		if (!quest_valid_room(room))
			continue;
		for (const auto *edge : world[room].dir_option)
		{
			if (!edge || !quest_valid_room(edge->to_room))
				continue;
			const int to = edge->to_room;
			const int from_zone = world[room].zone, to_zone = world[to].zone;
			if (!IS_MAP_ROOM(room) && IS_MAP_ROOM(to))
				quest_geography[from_zone].entrances.push_back(to);
			else if (IS_MAP_ROOM(room) && !IS_MAP_ROOM(to))
				quest_geography[to_zone].entrances.push_back(room);
			else if (!IS_MAP_ROOM(room) && !IS_MAP_ROOM(to) && from_zone != to_zone)
			{
				neighbors[from_zone].push_back(to_zone);
				neighbors[to_zone].push_back(from_zone);
			}
		}
	}
	for (auto &entry : quest_geography)
	{
		std::sort(entry.entrances.begin(), entry.entrances.end());
		entry.entrances.erase(std::unique(entry.entrances.begin(), entry.entrances.end()),
				      entry.entrances.end());
	}
	// Resolve each family at its nearest authored zone boundary. This admits a
	// town's adjacent connector without flooding all connected interior areas.
	// Tied boundaries in different regions stay ambiguous rather than expanding
	// the local contract. Surface and Underdark never compete with each other.
	for (int zone = 0; zone <= top_of_zone_table; ++zone)
		for (bool underdark : { false, true })
		{
			std::vector<bool> seen(top_of_zone_table + 1, false);
			std::vector<int> frontier{ zone };
			seen[zone] = true;
			while (!frontier.empty())
			{
				std::unordered_set<int> regions;
				std::vector<int> next;
				for (int current : frontier)
				{
					for (int entrance : quest_geography[current].entrances)
					{
						const auto region = quest_map_region(entrance);
						const int identity = underdark ? region.underdark :
										 region.surface;
						if (identity > 0)
							regions.insert(identity);
					}
					for (int neighbor : neighbors[current])
						if (!seen[neighbor])
						{
							seen[neighbor] = true;
							next.push_back(neighbor);
						}
				}
				if (!regions.empty())
				{
					if (regions.size() == 1)
					{
						auto &region = quest_geography[zone].region;
						(underdark ? region.underdark : region.surface) =
							*regions.begin();
					}
					else
						quest_geography[zone].region.uncertain = true;
					break;
				}
				frontier = std::move(next);
			}
		}
}

world_quest_region quest_region_for_room(int room)
{
	if (!quest_valid_room(room))
		return {};
	return IS_MAP_ROOM(room) ? quest_map_region(room) :
				   quest_geography[world[room].zone].region;
}

bool quest_local_match(int origin, int destination)
{
	const auto first = quest_region_for_room(origin);
	const auto second = quest_region_for_room(destination);
	return (first.surface > 0 && first.surface == second.surface) ||
	       (first.underdark > 0 && first.underdark == second.underdark);
}

bool quest_target_location(int room)
{
	if (!quest_valid_room(room))
		return false;
	return !IS_SET(zone_table[world[room].zone].flags, ZONE_CLOSED | ZONE_PRIVATE) &&
	       !IS_SET(world[room].room_flags, ROOM_LOCKER | ROOM_PRIVATE | ROOM_ARENA |
						       ROOM_GUILD | ROOM_JAIL | ROOM_ATRIUM);
}

// Audited Bloodstone ambient ticks. Each ignores nonzero commands (apart
// from periodic registration) and only speaks or performs cosmetic actions.
// They neither gate ordinary travel/doors nor intercept ASK.
bool passive_quest_mobile_proc(mob_proc_type proc)
{
	return proc == bs_boss || proc == bs_citizen || proc == bs_comwoman || proc == bs_brat ||
	       proc == bs_holyman || proc == bs_merchant || proc == bs_wino || proc == bs_watcher ||
	       proc == bs_guard || proc == bs_squire || proc == bs_peddler || proc == bs_timid ||
	       proc == bs_shady || proc == bs_sinister || proc == bs_menacing ||
	       proc == bs_executioner || proc == bs_baron || proc == bs_sparrow ||
	       proc == bs_squirrel || proc == bs_crow || proc == bs_mountainman ||
	       proc == bs_salesman || proc == bs_nomad || proc == bs_insane ||
	       proc == bs_homeless || proc == bs_servant || proc == bs_gnoll ||
	       proc == bs_griffon || proc == bs_boar || proc == bs_cub || proc == bs_stirge;
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

enum quest_rejection
{
	rejected_instance,
	rejected_source,
	rejected_zone,
	rejected_location,
	rejected_controlled,
	rejected_nonlocal,
	rejected_altitude,
	rejected_kill_rules,
	rejected_ask_population,
	rejected_ask_speech_level,
	rejected_ask_environment,
	rejected_ask_hidden,
	rejected_sleeping,
	rejected_silenced,
	rejected_actor_speech,
	rejected_room_handler,
	rejected_actor_object_handler,
	rejected_room_object_handler,
	rejected_mobile_handler,
	rejected_visibility,
	rejected_aggression,
	rejected_supply,
	rejected_completed,
	rejected_history_limit,
	quest_rejection_count,
};

constexpr const char *quest_rejection_names[] = {
	"invalid_instance",
	"reset_source",
	"zone",
	"location",
	"controlled",
	"nonlocal",
	"altitude",
	"kill_rules",
	"ask_population",
	"ask_speech_level",
	"ask_environment",
	"ask_hidden",
	"sleeping",
	"silenced",
	"actor_speech",
	"room_handler",
	"actor_object_handler",
	"room_object_handler",
	"mobile_handler",
	"visibility",
	"aggression",
	"supply",
	"completed",
	"history_limit",
};
static_assert(std::size(quest_rejection_names) == quest_rejection_count);

struct quest_target_request
{
	P_char actor;
	int level;
	quest_work work;
	int origin_room;
	std::map<int, std::map<int, std::vector<P_char>>> mobs;
	std::unordered_map<int, size_t> population;
	int probes = WORLD_QUEST_MAX_TARGET_PROBES;
	int history_checks = WORLD_QUEST_MAX_HISTORY_CHECKS;
	std::unordered_map<int, int> history;
	std::map<int, std::vector<int>> tried;
	// Predicate failures can count the same instance on multiple passes. Keep
	// fixed-size counters and one example per reason; never log inside the scan.
	std::array<size_t, quest_rejection_count> rejected{};
	std::array<int, quest_rejection_count> examples{};
	size_t scanned = 0;
	int zones_tried = 0;
	int last_target = 0;
	const char *history_state = "not_checked";

	bool reject(quest_rejection reason, int example = 0)
	{
		if (rejected[reason]++ == 0)
			examples[reason] = example;
		return false;
	}

	quest_target_request(P_char ch, int origin, int accepted_level, int accepted_target = 0)
		: actor(ch)
		, level(accepted_level)
		, origin_room(origin > 0 ? real_room(origin) : NOWHERE)
	{
		for (P_char mob = character_list; mob; mob = mob->next)
		{
			if (!quest_spend_work(work))
				break;
			++scanned;
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
		if (work.exhausted)
			mobs.clear();
	}

	bool controlled(P_char mob) const
	{
		return mob->following || GET_MASTER(mob) || mob->only.npc->summoned_instance ||
		       mob->only.npc->summon_kind != 0 || IS_AFFECTED(mob, AFF_CHARM) ||
		       affected_by_spell(mob, TAG_CONJURED_PET);
	}

	bool ordinary_instance(P_char mob)
	{
		if (!IS_NPC(mob) || !IS_ALIVE(mob) || mob->in_room < 0 ||
		    mob->in_room > top_of_world || GET_RNUM(mob) < 0 ||
		    GET_RNUM(mob) > top_of_mobt || GET_HIT(mob) <= 0)
			return reject(rejected_instance);
		const auto *source = routine_source(mob);
		if (!source || source->room < 0 || source->room > top_of_world ||
		    world[source->room].number != GET_BIRTHPLACE(mob) ||
		    world[source->room].zone != world[mob->in_room].zone ||
		    source->profile->vnum != GET_VNUM(mob))
			return reject(rejected_source, GET_VNUM(mob));
		if (!static_zone_eligibility(world[mob->in_room].zone, level))
			return reject(rejected_zone, zone_table[world[mob->in_room].zone].number);
		if (!quest_target_location(mob->in_room))
			return reject(rejected_location, world[mob->in_room].number);
		return true;
	}

	bool local(P_char mob) const
	{
		return level > WORLD_QUEST_LOCAL_MAX_LEVEL ||
		       quest_local_match(origin_room, mob->in_room);
	}

	int map_room(P_char mob) const
	{
		const auto &entrances = quest_geography[world[mob->in_room].zone].entrances;
		for (int entrance : entrances)
			if (level > WORLD_QUEST_LOCAL_MAX_LEVEL ||
			    quest_local_match(origin_room, entrance))
				return entrance;
		return NOWHERE;
	}

	bool common(P_char mob)
	{
		if (!ordinary_instance(mob))
			return false;
		if (controlled(mob))
			return reject(rejected_controlled, GET_VNUM(mob));
		if (!local(mob))
			return reject(rejected_nonlocal, GET_VNUM(mob));
		return true;
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
		if (!proc || passive_quest_mobile_proc(proc))
			return true;
		if (proc != shop_keeper)
			return false;
		const size_t lookup_work = mob->only.npc->shopkeeper_shop_id < 0 ?
						   static_cast<size_t>(number_of_shops) :
						   1;
		if (!quest_spend_work(work, lookup_work))
			return false;
		const int shop = singleton_shop_id(mob);
		// Travel-safe quest handlers may consume ASK before do_ask reaches
		// quest_ask. Only an absent or audited passive shop delegate ignores it.
		return shop >= 0 && shop < number_of_shops &&
		       (!shop_index[shop].func || passive_quest_mobile_proc(shop_index[shop].func));
	}

	bool world_type_eligible(P_char mob, int type)
	{
		const auto &profile = *routine_source(mob)->profile;
		const int room = mob->in_room;
		if (mob->specials.z_cord != 0)
			return reject(rejected_altitude, GET_VNUM(mob));
		if (type == FIND_AND_KILL)
		{
			const bool eligible =
				profile.level >= level - 4 && profile.level <= level + 5 &&
				GET_LEVEL(mob) >= level - 4 && GET_LEVEL(mob) <= level + 5 &&
				profile.combat_eligible && GET_MAX_HIT(mob) > 1 &&
				GET_EXP(mob) > 0 && !IS_SHOPKEEPER(mob) &&
				!IS_SET(mob->specials.act,
					ACT_TEACHER | ACT_GUILD_GOLEM | ACT_IGNORE) &&
				!IS_SET(world[room].room_flags, ROOM_SAFE) &&
				!IS_SET(zone_table[world[room].zone].flags, ZONE_SAFE);
			return eligible || reject(rejected_kill_rules, GET_VNUM(mob));
		}
		if (mob_index[GET_RNUM(mob)].number != 1)
			return reject(rejected_ask_population, GET_VNUM(mob));
		if (!profile.can_speak || profile.level >= MAXLVL || GET_LEVEL(mob) >= MAXLVL ||
		    !CAN_SPEAK(mob))
			return reject(rejected_ask_speech_level, GET_VNUM(mob));
		if (IS_SET(world[room].room_flags, ROOM_SILENT | ROOM_UNDERWATER) ||
		    IS_SET(zone_table[world[room].zone].flags, ZONE_SILENT) ||
		    world[room].sector_type == SECT_UNDERWATER ||
		    world[room].sector_type == SECT_UNDERWATER_GR)
			return reject(rejected_ask_environment, world[room].number);
		if (level < 31 && (profile.invisible || profile.hidden ||
				   IS_AFFECTED(mob, AFF_INVISIBLE | AFF_HIDE) ||
				   IS_AFFECTED2(mob, AFF2_CONCEALMENT) ||
				   IS_AFFECTED3(mob, AFF3_ECTOPLASMIC_FORM)))
			return reject(rejected_ask_hidden, GET_VNUM(mob));
		return true;
	}

	bool handlers_eligible(P_char mob)
	{
		// special() offers ASK to the whole interaction scene before do_ask.
		// Audit that scene without executing scripts or proving a travel route.
		const auto &room = world[mob->in_room];
		if (room.funct && room.funct != inn && room.funct != ship_shop_proc &&
		    room.funct != crew_shop_proc)
			return reject(rejected_room_handler, room.number);
		auto object_handler = [&](P_obj object, quest_rejection reason)
		{
			if (!object)
				return true;
			if (!quest_spend_work(work))
				return false;
			if (object->R_num < 0)
				return true;
			if (object->R_num > top_of_objt)
				return reject(reason, -1);
			const auto proc = obj_index[object->R_num].func.obj;
			// set_proc delegates only to master/random set bonuses; both ignore ASK.
			if (!proc || proc == board || proc == artifact_hide ||
			    proc == ring_of_regeneration || proc == tracks ||
			    proc == blood_stains || proc == set_proc)
				return true;
			return reject(reason, obj_index[object->R_num].virtual_number);
		};
		for (P_obj object = actor->carrying; object; object = object->next_content)
			if (!object_handler(object, rejected_actor_object_handler))
				return false;
		for (P_obj object : actor->equipment)
			if (!object_handler(object, rejected_actor_object_handler))
				return false;
		for (P_obj object = room.contents; object; object = object->next_content)
			if (!object_handler(object, rejected_room_object_handler))
				return false;
		for (P_char person = room.people; person; person = person->next_in_room)
		{
			if (!quest_spend_work(work))
				return false;
			if (person == actor || !IS_NPC(person) || !IS_ALIVE(person) ||
			    !IS_AWAKE(person))
				continue;
			const int rnum = GET_RNUM(person);
			if (rnum < 0 || rnum > top_of_mobt ||
			    !ask_handler(person, mob_index[rnum].func.mob) ||
			    !ask_handler(person, mob_index[rnum].qst_func))
				return work.exhausted ? false :
							reject(rejected_mobile_handler,
							       rnum >= 0 && rnum <= top_of_mobt ?
								       GET_VNUM(person) :
								       -1);
		}
		return true;
	}

	bool type_eligible(P_char mob, int type)
	{
		if (!world_type_eligible(mob, type))
			return false;
		if (type != FIND_AND_ASK)
			return true;
		if (!IS_AWAKE(mob))
			return reject(rejected_sleeping, GET_VNUM(mob));
		if (IS_AFFECTED2(mob, AFF2_SILENCED))
			return reject(rejected_silenced, GET_VNUM(mob));
		if (!actor_can_ask())
			return reject(rejected_actor_speech);
		return handlers_eligible(mob);
	}

	int suggest(int zone, int type, int minimum)
	{
		std::vector<int> candidates;
		const auto &excluded = tried[zone];
		for (const auto &[rnum, instances] : mobs.at(zone))
		{
			if (!quest_spend_work(work))
				break;
			const int vnum = mob_index[rnum].virtual_number;
			if (std::find(excluded.begin(), excluded.end(), vnum) != excluded.end())
				continue;
			const auto completed = history.find(vnum);
			if (completed != history.end() && completed->second > 0)
				continue;
			if (completed == history.end() && history_checks <= 0)
			{
				reject(rejected_history_limit, vnum);
				continue;
			}
			int count = 0;
			for (P_char mob : instances)
			{
				if (!quest_spend_work(work))
					break;
				if (common(mob) && type_eligible(mob, type))
					++count;
			}
			if ((type == FIND_AND_KILL && count >= minimum) ||
			    (type == FIND_AND_ASK && count == 1))
				candidates.push_back(vnum);
			else
				reject(rejected_supply, vnum);
		}
		if (work.exhausted || candidates.empty())
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
			if (!quest_spend_work(work))
				break;
			if (!common(mob) || !type_eligible(mob, type))
				continue;
			// Bound the lighting/aura walks in the existing visibility
			// predicate as well as this request's one live-character scan.
			if (!quest_spend_work(work, 8 * (population.at(mob->in_room) + 1)))
				break;
			if (!ac_can_see_from(actor, mob, mob->in_room))
			{
				reject(rejected_visibility, vnum);
				continue;
			}
			if (type == FIND_AND_ASK && aggressive_to_at(mob, actor, mob->in_room))
			{
				reject(rejected_aggression, vnum);
				continue;
			}
			if (checked.usable_count++ == 0)
				checked.map_room = map_room(mob);
		}
		if (work.exhausted || (type == FIND_AND_KILL ? checked.usable_count < minimum :
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
		result.work = request.work.work;
		return result;
	};
	if (request.work.exhausted)
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
				if (!quest_spend_work(request.work))
					return finish(status::unproven);
				if (!request.ordinary_instance(mob) ||
				    !request.world_type_eligible(mob, type))
					continue;
				status interaction = status::valid;
				if (request.controlled(mob) ||
				    (type == FIND_AND_ASK &&
				     (!request.actor_can_ask() || !IS_AWAKE(mob) ||
				      IS_AFFECTED2(mob, AFF2_SILENCED))))
					interaction = status::blocked;
				else if (type == FIND_AND_ASK && !request.handlers_eligible(mob))
					interaction = status::unproven;
				else
				{
					if (!quest_spend_work(
						    request.work,
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
	if (request.work.exhausted)
		return finish(status::unproven);
	if (static_cast<int>(candidates.size()) < needed)
		return finish(status::unavailable);
	if (origin_vnum <= 0)
		return finish(status::needs_origin);
	if (real_room(origin_vnum) < 0)
		return finish(status::unavailable);

	const auto region = quest_region_for_room(request.origin_room);
	if (accepted_level <= WORLD_QUEST_LOCAL_MAX_LEVEL && !region.surface && !region.underdark)
		return finish(status::unproven);
	int valid = 0, blocked = 0, uncertain = 0;
	for (const auto &candidate : candidates)
	{
		if (!request.local(candidate.mob))
		{
			const auto destination = quest_region_for_room(candidate.mob->in_room);
			if (region.uncertain || destination.uncertain ||
			    (!destination.surface && !destination.underdark))
				++uncertain;
			continue;
		}
		if (candidate.interaction == status::valid)
		{
			if (valid++ == 0)
				result.map_room = request.map_room(candidate.mob);
		}
		else if (candidate.interaction == status::blocked)
			++blocked;
		else
			++uncertain;
	}
	if (valid >= needed)
		return finish(status::valid);
	if (valid + blocked >= needed)
		return finish(status::blocked);
	if (valid + blocked + uncertain >= needed)
		return finish(status::unproven);
	return finish(status::unavailable);
}

world_quest_region world_quest_policy_region(int room)
{
	return world_quest_policy_bootstrap() ? quest_region_for_room(room) : world_quest_region{};
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
		build_geography();
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
	auto failed = [&](quest_creation_failure failure, const char *reason,
			  const quest_target_request *request = nullptr)
	{
		if (ch && IS_PC(ch) && ch->only.pc->quest_replacement_due)
		{
			std::string rejections;
			if (request)
				for (size_t index = 0; index < quest_rejection_count; ++index)
					if (request->rejected[index])
					{
						char entry[128];
						snprintf(entry, sizeof(entry),
							 "%s%s=%zu(example=%d)",
							 rejections.empty() ? "" : ",",
							 quest_rejection_names[index],
							 request->rejected[index],
							 request->examples[index]);
						rejections += entry;
					}
			const auto region = request ? quest_region_for_room(request->origin_room) :
						      world_quest_region{};
			logit(LOG_STATUS,
			      "World quest replacement failed: pid=%d stage=selection reason=%s "
			      "current_level=%d accepted_level=%d selection_level=%d "
			      "type=%d needed=%d old_target=%d "
			      "origin=%d surface=%d underdark=%d uncertain=%d scanned=%zu "
			      "candidate_zones=%zu zones_tried=%d last_target=%d history=%s "
			      "probes_left=%d history_checks_left=%d work=%zu work_exhausted=%d "
			      "rejections={%s}",
			      GET_PID(ch), reason, GET_LEVEL(ch), ch->only.pc->quest_level,
			      accepted_level, required_type, needed, ch->only.pc->quest_mob_vnum,
			      origin_vnum, region.surface, region.underdark, region.uncertain,
			      request ? request->scanned : size_t{ 0 },
			      request ? request->mobs.size() : size_t{ 0 },
			      request ? request->zones_tried : 0,
			      request ? request->last_target : 0,
			      request ? request->history_state : "not_checked",
			      request ? request->probes : WORLD_QUEST_MAX_TARGET_PROBES,
			      request ? request->history_checks : WORLD_QUEST_MAX_HISTORY_CHECKS,
			      request ? request->work.work : size_t{ 0 },
			      request && request->work.exhausted, rejections.c_str());
		}
		return failure;
	};
	if (!ch || IS_NPC(ch) || origin_vnum <= 0 || real_room(origin_vnum) == NOWHERE ||
	    (required_type && required_type != FIND_AND_KILL && required_type != FIND_AND_ASK) ||
	    needed < 0)
		return failed(QUEST_CREATION_INVALID_ACTOR, "invalid_request");
	if (!world_quest_policy_bootstrap())
		return failed(QUEST_CREATION_NO_ELIGIBLE_ZONE, "catalog_unavailable");
	bool eligible_zone = false;
	for (int zone = 0; zone <= top_of_zone_table; ++zone)
		eligible_zone = eligible_zone || static_zone_eligibility(zone, accepted_level);
	if (!eligible_zone)
		return failed(QUEST_CREATION_NO_ELIGIBLE_ZONE, "no_eligible_zone");

	quest_target_request request(ch, origin_vnum, accepted_level);
	std::vector<int> remaining_zones;
	for (const auto &[zone, mobs] : request.mobs)
	{
		(void)mobs;
		remaining_zones.push_back(zone);
	}
	while (!remaining_zones.empty() && request.probes > 0 && !request.work.exhausted)
	{
		const int zone = world_quest_policy_select_zone(accepted_level, remaining_zones);
		if (zone < 0)
			break;
		++request.zones_tried;
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
			while (request.probes > 0 && !request.work.exhausted)
			{
				const int minimum = needed > 0		  ? needed :
						    type == FIND_AND_KILL ? 2 :
									    1;
				const int vnum = request.suggest(zone, type, minimum);
				if (vnum <= 0)
					break;
				request.last_target = vnum;
				request.tried[zone].push_back(vnum);
				auto completed = request.history.find(vnum);
				if (completed == request.history.end())
				{
					--request.history_checks;
					const int done = sql_world_quest_done_already(ch, vnum);
					if (done < 0)
					{
						request.history_state = "unavailable";
						return failed(QUEST_CREATION_NO_ELIGIBLE_TARGET,
							      "history_unavailable", &request);
					}
					request.history_state = "ready";
					completed = request.history.emplace(vnum, done).first;
				}
				if (completed->second > 0)
				{
					request.reject(rejected_completed, vnum);
					continue;
				}
				// Do the real live check after the history read, immediately
				// before publishing the assignment. No prototype probe or
				// movement/interaction command is run on this path.
				if (request.validate(zone, vnum, type, target, minimum))
					return QUEST_CREATION_NO_FAILURE;
			}
		}
	}
	const char *reason = request.work.exhausted		      ? "work_budget_exhausted" :
			     request.probes <= 0		      ? "probe_budget_exhausted" :
			     request.rejected[rejected_history_limit] ? "history_budget_exhausted" :
									"no_eligible_target";
	return failed(QUEST_CREATION_NO_ELIGIBLE_TARGET, reason, &request);
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
