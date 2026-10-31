
#include "core/prototypes.h"
#include "core/utils.h"
#include "world/world_quest_policy.h"
#include "world/world_quest_policy_math.h"
#include "persistence/persistence_checkpoint.h"
#include <cstdio>
#include <cassert>
#include <vector>
extern P_room world;
extern zone_data *zone_table;
extern int top_of_world;
extern "C" void quest_journey_checkpoint(P_char ch, const char *label)
{
	assert(ch && IS_PC(ch));
	const auto &q = *ch->only.pc;
	FILE *out = fopen("quest-journey.tsv", "a");
	if (!out)
		return;
	fprintf(out, "%s\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%lld\t%d\t%d\t%d\t%d\t%d\t%d\t%lld\t%lld\n",
		label, q.quest_active, q.quest_replacement_due, q.quest_origin_room, q.quest_level,
		q.quest_type, q.quest_mob_vnum, q.quest_zone_number,
		static_cast<long long>(q.quest_started), q.quest_receiver, q.quest_shares_left,
		q.quest_kill_how_many, q.quest_kill_original, q.quest_map_room, q.quest_map_bought,
		static_cast<long long>(GET_MONEY(ch)), static_cast<long long>(ch->points.curr_exp));
	fclose(out);
}
extern "C" void quest_journey_invalidate(P_char ch)
{
	quest_journey_checkpoint(ch, "before-invalidation");
	std::vector<int> eligible;
	world_quest_policy_zone_list(ch, eligible);
	for (int zone : eligible)
		zone_table[zone].flags |= ZONE_CLOSED;
}

#include "world/handler.h"
#include "world/map.h"
#include "world/world_singletons.h"
#include "sql/sql.h"
#include "item/item_movement_transaction.h"
#ifdef __NO_MYSQL__
#include "flatfile/flatfile_world_quest_history.h"
#endif
#include <cjson/cJSON.h>
#include <algorithm>
#include <chrono>
#include <unordered_map>
#include <string>
#include <unistd.h>
#include <dlfcn.h>
extern P_char character_list;
extern P_index mob_index;
extern P_index obj_index;
extern int top_of_mobt;
extern long new_exp_table[];
extern shop_data *shop_index;
extern int number_of_shops;
extern time_info_data time_info;
extern const char *month_name[];
extern const char *dirs[];

extern "C"
{
	int quest_gameplay_kind = 0;
	int quest_gameplay_stage = 0;
	int quest_gameplay_level = 11;
	int quest_gameplay_origin = 16633;
}
extern "C" void quest_gameplay_read_control()
{
	FILE *input = fopen("quest-gameplay-control.txt", "r");
	if (!input)
		return;
	quest_gameplay_origin = 16633;
	const int read = fscanf(input, "%d %d %d %d", &quest_gameplay_level, &quest_gameplay_kind,
				&quest_gameplay_stage, &quest_gameplay_origin);
	fclose(input);
	assert(read == 3 || read == 4);
}
extern "C" void quest_gameplay_setup(P_char ch)
{
	assert(ch && IS_PC(ch));
	quest_gameplay_read_control();
	ch->player.level = quest_gameplay_level;
	bool placing = quest_gameplay_stage == 1 && quest_gameplay_origin != 16633;
	if (quest_gameplay_stage == 4)
	{
		// Explicit disposable-fixture setup only. Gameplay/state transitions
		// after this point run through the normal command/payment handlers.
		FILE *input = fopen("quest-reported-setup.txt", "r");
		if (!input)
			return;
		int action = 0;
		assert(fscanf(input, "%d", &action) == 1);
		fclose(input);
		assert(remove("quest-reported-setup.txt") == 0);
		placing = action == 0;
		auto &q = *ch->only.pc;
		if (action == 1 || action == 2)
			q.quest_started = time(nullptr) - 25 * 3600;
		if (action == 2)
		{
			assert(q.quest_active && q.quest_type == FIND_AND_KILL);
			q.quest_kill_how_many = 1;
		}
		if (action == 3)
			q.quest_origin_room = 0;
		if (action == 4)
			quest_journey_invalidate(ch);
		mark_player_dirty_components(GET_PID(ch), PLAYER_COMPONENT_STATUS);
	}
	if (placing)
	{
		char_from_room(ch);
		char_to_room(ch, real_room(quest_gameplay_origin), 0);
		if (GET_MONEY(ch) < 10000000)
			ADD_MONEY(ch, 10000000 - GET_MONEY(ch));
	}
}

static int completion_remaining = -1, completion_level = 0, completion_target = 0;
static int completion_calls = 0;
static uint64_t completion_reward = 0;
static int completion_reward_vnum = 0;
extern "C" void quest_gameplay_history(P_char ch, P_obj reward)
{
	assert(ch && IS_PC(ch));
	++completion_calls;
	completion_remaining = sql_world_quest_can_do_another(ch);
	completion_level = GET_LEVEL(ch);
	completion_target = ch->only.pc->quest_mob_vnum;
	completion_reward = reward ? reward->obj_uid : 0;
	completion_reward_vnum = reward ? OBJ_VNUM(reward) : 0;
}

static void number(cJSON *object, const char *key, long long value)
{
	cJSON_AddNumberToObject(object, key, static_cast<double>(value));
}

// Debugger-only provenance lookup uses the owning private routine_source;
// no policy copy, public engine test API or live pointers survive this call.
static const char *procedure_name(const void *function)
{
	Dl_info info{};
	return function && dladdr(function, &info) && info.dli_sname ? info.dli_sname :
	       function						     ? "unknown-symbol" :
								       "none";
}

static cJSON *room_diagnostic(int room, P_char viewer)
{
	cJSON *data = cJSON_CreateObject();
	number(data, "room", world[room].number);
	number(data, "single_file", IS_SET(world[room].room_flags, ROOM_SINGLE_FILE));
	number(data, "affected", world[room].affected != nullptr);
	number(data, "current", world[room].current_speed);
	number(data, "fall", world[room].chance_fall);
	number(data, "sector", world[room].sector_type);
	cJSON *exits = cJSON_AddArrayToObject(data, "exits");
	for (int direction = 0; direction < NUM_EXITS; ++direction)
		if (const auto *edge = world[room].dir_option[direction])
		{
			cJSON *entry = cJSON_CreateObject();
			number(entry, "direction", direction);
			number(entry, "to", world[edge->to_room].number);
			number(entry, "flags", edge->exit_info);
			cJSON_AddItemToArray(exits, entry);
		}
	cJSON_AddStringToObject(data, "flags", std::to_string(world[room].room_flags).c_str());
	cJSON_AddStringToObject(data, "procedure",
				procedure_name(reinterpret_cast<const void *>(world[room].funct)));
	cJSON *people = cJSON_AddArrayToObject(data, "people");
	for (P_char person = world[room].people; person; person = person->next_in_room)
	{
		cJSON *entry = cJSON_CreateObject();
		number(entry, "self", person == viewer);
		number(entry, "npc", IS_NPC(person));
		if (IS_NPC(person))
		{
			number(entry, "vnum", GET_VNUM(person));
			cJSON_AddStringToObject(entry, "primary",
						procedure_name(reinterpret_cast<const void *>(
							mob_index[GET_RNUM(person)].func.mob)));
			cJSON_AddStringToObject(entry, "secondary",
						procedure_name(reinterpret_cast<const void *>(
							mob_index[GET_RNUM(person)].qst_func)));
			const int shop = singleton_shop_id(person);
			if (shop >= 0 && shop < number_of_shops)
				cJSON_AddStringToObject(
					entry, "shop",
					procedure_name(reinterpret_cast<const void *>(
						shop_index[shop].func)));
		}
		cJSON_AddItemToArray(people, entry);
	}
	cJSON *objects = cJSON_AddArrayToObject(data, "objects");
	for (P_obj object = world[room].contents; object; object = object->next_content)
	{
		cJSON *entry = cJSON_CreateObject();
		number(entry, "vnum", OBJ_VNUM(object));
		cJSON_AddStringToObject(entry, "procedure",
					procedure_name(reinterpret_cast<const void *>(
						obj_index[object->R_num].func.obj)));
		cJSON_AddItemToArray(objects, entry);
	}
	return data;
}

static void inventory_item(cJSON *items, P_obj object)
{
	cJSON *entry = cJSON_CreateObject();
	cJSON_AddStringToObject(entry, "uid", std::to_string(object->obj_uid).c_str());
	number(entry, "vnum", OBJ_VNUM(object));
	cJSON_AddStringToObject(entry, "name", object->name);
	cJSON_AddItemToArray(items, entry);
	for (P_obj child = object->contains; child; child = child->next_content)
		inventory_item(items, child);
}

extern "C" void quest_gameplay_plan(P_char ch, const void *source_lookup)
{
	assert(ch && IS_PC(ch));
	using lookup_type = const void *(*)(P_char);
	const auto source = reinterpret_cast<lookup_type>(const_cast<void *>(source_lookup));
	const auto &q = *ch->only.pc;
	static unsigned sequence = 0;
	static int last_target = 0;
	if (q.quest_active)
		last_target = q.quest_mob_vnum;
	cJSON *root = cJSON_CreateObject();
	number(root, "sequence", ++sequence);
	number(root, "pid", getpid());
	number(root, "actor_level", GET_LEVEL(ch));
	number(root, "profile_level", quest_gameplay_level);
	number(root, "profile_kind", quest_gameplay_kind);
	number(root, "history_target", last_target);
	number(root, "items_busy", item_movement_transaction_player_busy(ch));

	number(root, "room", world[ch->in_room].number);
	number(root, "hp", GET_HIT(ch));
	number(root, "max_hp", GET_MAX_HIT(ch));
	number(root, "moves", GET_VITALITY(ch));
	number(root, "max_moves", GET_MAX_VITALITY(ch));
	number(root, "position", GET_POS(ch));
	number(root, "fighting", IS_FIGHTING(ch));
	number(root, "primary_weapon",
	       ch->equipment[PRIMARY_WEAPON] ? OBJ_VNUM(ch->equipment[PRIMARY_WEAPON]) : 0);
	number(root, "secondary_weapon",
	       ch->equipment[SECONDARY_WEAPON] ? OBJ_VNUM(ch->equipment[SECONDARY_WEAPON]) : 0);
	if (GET_OPPONENT(ch) && IS_NPC(GET_OPPONENT(ch)))
	{
		number(root, "opponent", GET_VNUM(GET_OPPONENT(ch)));
		number(root, "opponent_hp", GET_HIT(GET_OPPONENT(ch)));
	}

	number(root, "wallet", GET_MONEY(ch));
	number(root, "xp", ch->points.curr_exp);
	long long progress_xp = ch->points.curr_exp;
	for (int entered_level = 1; entered_level <= GET_LEVEL(ch); ++entered_level)
		progress_xp += new_exp_table[entered_level];
	number(root, "progress_xp", progress_xp);
	number(root, "completion_remaining", completion_remaining);
	number(root, "completion_calls", completion_calls);
	number(root, "player_id", GET_PID(ch));
#ifdef __NO_MYSQL__
	int stored_history = 0;
	std::string history_error;
	const auto history_result = flatfile_world_quest_count_day(getenv("FLATFILE_STATE_DIR"),
								   GET_PID(ch), 50, time(nullptr),
								   &stored_history, &history_error);
	assert(history_result == flatfile_world_quest_result::ok ||
	       history_result == flatfile_world_quest_result::not_found);
	number(root, "stored_history", stored_history);
#endif

	number(root, "completion_level", completion_level);
	number(root, "completion_target", completion_target);
	cJSON_AddStringToObject(root, "reward_uid", std::to_string(completion_reward).c_str());
	number(root, "reward_vnum", completion_reward_vnum);

	number(root, "active", q.quest_active);
	number(root, "due", q.quest_replacement_due);
	number(root, "accepted_level", q.quest_level);
	number(root, "type", q.quest_type);
	number(root, "mob", q.quest_mob_vnum);
	number(root, "zone", q.quest_zone_number);
	number(root, "kills", q.quest_kill_how_many);
	number(root, "quota", q.quest_kill_original);
	number(root, "map_bought", q.quest_map_bought);
	number(root, "map_room", q.quest_map_room);
	number(root, "origin", q.quest_origin_room);
	number(root, "giver", q.quest_giver);
	number(root, "receiver", q.quest_receiver);
	number(root, "shares", q.quest_shares_left);
	number(root, "started", q.quest_started);

	number(root, "remaining", sql_world_quest_can_do_another(ch));
	number(root, "history_done",
	       last_target ? sql_world_quest_done_already(ch, last_target) : 0);
	cJSON_AddStringToObject(root, "month", strip_ansi(month_name[time_info.month]).c_str());
	cJSON *items = cJSON_AddArrayToObject(root, "items");
	for (P_obj object = ch->carrying; object; object = object->next_content)
		inventory_item(items, object);
	for (P_obj object : ch->equipment)
		if (object)
			inventory_item(items, object);

	const int origin = q.quest_active ? q.quest_origin_room : quest_gameplay_origin;
	number(root, "route_origin", origin);
	const int level = q.quest_active ? q.quest_level : quest_gameplay_level;
	const auto start = std::chrono::steady_clock::now();
	const auto routes = world_quest_policy_routes(ch, origin, level);
	number(root, "route_work", routes.work);
	number(root, "route_rooms", routes.rooms.size());
	number(root, "route_exhausted", routes.exhausted);
	number(root, "route_uncertain", routes.uncertain);
	number(root, "route_us",
	       std::chrono::duration_cast<std::chrono::microseconds>(
		       std::chrono::steady_clock::now() - start)
		       .count());

	if (routes.rooms.empty())
	{
		cJSON_AddItemToObject(root, "current_room_details",
				      room_diagnostic(ch->in_room, ch));
		if (real_room(origin) >= 0)
			cJSON_AddItemToObject(root, "origin_details",
					      room_diagnostic(real_room(origin), ch));
	}

	std::unordered_map<int, std::vector<P_char>> targets;
	if (q.quest_active)
		for (P_char mob = character_list; mob; mob = mob->next)
		{
			if (!IS_NPC(mob) || !IS_ALIVE(mob) || mob->in_room < 0 ||
			    mob->in_room > top_of_world || GET_VNUM(mob) != q.quest_mob_vnum ||
			    zone_table[world[mob->in_room].zone].number != q.quest_zone_number ||
			    GET_HIT(mob) <= 0 || mob->following || GET_MASTER(mob) ||
			    IS_AFFECTED(mob, AFF_CHARM) || !source(mob) ||
			    world_quest_policy_route(routes, real_room(GET_BIRTHPLACE(mob))) !=
				    world_quest_route_status::available ||
			    world_quest_policy_route(routes, mob->in_room) !=
				    world_quest_route_status::available ||
			    !ac_can_see_from(ch, mob, mob->in_room))
				continue;
			targets[mob->in_room].push_back(mob);
		}
	std::unordered_map<int, std::vector<int>> outgoing;
	for (const auto &[to, room] : routes.rooms)
		if (room.returns_to_origin)
			for (int from : room.incoming)
				if (routes.rooms.at(from).returns_to_origin)
					outgoing[from].push_back(to);
	std::unordered_map<int, int> previous{ { ch->in_room, NOWHERE } };
	std::vector<int> queue{ ch->in_room };
	int destination = NOWHERE;
	for (size_t next = 0; next < queue.size(); ++next)
	{
		const int room = queue[next];
		if (q.quest_active ? targets.count(room) : room == real_room(origin))
		{
			destination = room;
			break;
		}
		for (int to : outgoing[room])
			if (previous.emplace(to, room).second)
				queue.push_back(to);
	}
	cJSON *path = cJSON_AddArrayToObject(root, "path");
	if (destination != NOWHERE)
	{
		std::vector<int> reversed;
		for (int room = destination; room != ch->in_room; room = previous.at(room))
			reversed.push_back(room);
		std::reverse(reversed.begin(), reversed.end());
		int from = ch->in_room;
		for (int to : reversed)
		{
			int direction = 0;
			while (direction < NUM_EXITS &&
			       (!world[from].dir_option[direction] ||
				world[from].dir_option[direction]->to_room != to))
				++direction;
			assert(direction < NUM_EXITS);
			cJSON *step = cJSON_CreateObject();
			cJSON_AddStringToObject(step, "direction", dirs[direction]);
			number(step, "from", world[from].number);
			number(step, "to", world[to].number);
			number(step, "closed",
			       IS_SET(world[from].dir_option[direction]->exit_info, EX_CLOSED) !=
				       0);
			number(step, "crawl", world[to].sector_type == SECT_UNDRWLD_LOWCEIL);
			cJSON_AddItemToArray(path, step);
			from = to;
		}
		number(root, "destination", world[destination].number);
		if (q.quest_active)
		{
			P_char mob = targets.at(destination).front();
			number(root, "birthplace", GET_BIRTHPLACE(mob));
			char selector[MAX_INPUT_LENGTH]{};
			if (destination == ch->in_room &&
			    get_char_room_target(ch, mob, selector, sizeof(selector)))
				cJSON_AddStringToObject(root, "selector", selector);
		}
	}
	if (destination == NOWHERE)
	{
		cJSON *boundary = cJSON_AddArrayToObject(root, "unproved_boundary");
		std::vector<int> inspected;
		for (const auto &[room, info] : routes.rooms)
		{
			(void)info;
			for (const auto *exit : world[room].dir_option)
				if (exit && exit->to_room >= 0 && exit->to_room <= top_of_world &&
				    !routes.rooms.count(exit->to_room) && inspected.size() < 32 &&
				    std::find(inspected.begin(), inspected.end(), exit->to_room) ==
					    inspected.end())
				{
					inspected.push_back(exit->to_room);
					cJSON_AddItemToArray(boundary,
							     room_diagnostic(exit->to_room, ch));
				}
		}
	}
	char *text = cJSON_PrintUnformatted(root);
	FILE *out = fopen("quest-gameplay.json.tmp", "w");
	assert(out);
	fputs(text, out);
	fclose(out);
	assert(rename("quest-gameplay.json.tmp", "quest-gameplay.json") == 0);
	cJSON_free(text);
	cJSON_Delete(root);
}

#include "world/specs.prototypes.h"
#include "combat/justice.h"

extern "C" void quest_world_audit(P_char ch)
{
	assert(ch && IS_PC(ch));
	cJSON *root = cJSON_CreateObject();
	number(root, "race", GET_RACE(ch));
	number(root, "racewar", GET_RACEWAR(ch));
	cJSON *origins = cJSON_AddArrayToObject(root, "origins");
	for (P_char giver = character_list; giver; giver = giver->next)
	{
		if (!IS_NPC(giver) || giver->in_room < 0 || giver->in_room > top_of_world)
			continue;
		const int shop = singleton_shop_id(giver);
		if (mob_index[GET_RNUM(giver)].func.mob != world_quest &&
		    mob_index[GET_RNUM(giver)].qst_func != world_quest &&
		    (shop < 0 || shop >= number_of_shops || shop_index[shop].func != world_quest))
			continue;
		const int home = zone_table[world[giver->in_room].zone].hometown;
		const bool reported = GET_VNUM(giver) == 1709 || GET_VNUM(giver) == 74060 ||
				      GET_VNUM(giver) == 132555;
		if ((!reported && home < 1) || home > LAST_HOME ||
		    (home > 0 && PC_NOTWELCOME(ch, home)))
			continue;
		for (int level : { 11, 29, 30 })
		{
			cJSON *entry = cJSON_CreateObject();
			number(entry, "origin", world[giver->in_room].number);
			number(entry, "giver", GET_VNUM(giver));
			number(entry, "home", home);
			number(entry, "level", level);
			const auto routes =
				world_quest_policy_routes(ch, world[giver->in_room].number, level);
			number(entry, "rooms", routes.rooms.size());
			number(entry, "work", routes.work);
			number(entry, "exhausted", routes.exhausted);
			number(entry, "uncertain", routes.uncertain);
			int underdark = 0, surface = 0;
			for (const auto &[room, info] : routes.rooms)
				if (info.returns_to_origin && IS_MAP_ROOM(room))
				{
					underdark += IS_UD_MAP(room);
					surface += IS_SURFACE_MAP(room);
				}
			number(entry, "underdark_map_rooms", underdark);
			number(entry, "surface_map_rooms", surface);
			char_data profile = *ch;
			profile.player.level = level;
			std::vector<int> zones;
			world_quest_policy_zone_list(&profile, zones);
			int live_level_zone = 0;
			for (P_char mob = character_list; mob; mob = mob->next)
				if (IS_NPC(mob) && mob->in_room >= 0 &&
				    mob->in_room <= top_of_world && GET_LEVEL(mob) >= level - 4 &&
				    GET_LEVEL(mob) <= level + 5 &&
				    std::find(zones.begin(), zones.end(),
					      world[mob->in_room].zone) != zones.end() &&
				    world_quest_policy_route(routes, mob->in_room) ==
					    world_quest_route_status::available)
					++live_level_zone;
			number(entry, "live_level_zone", live_level_zone);

			world_quest_target target;
			const auto failure = world_quest_policy_select_target(
				ch, world[giver->in_room].number, level, target);
			number(entry, "failure", failure);
			number(entry, "target", target.mob_vnum);
			number(entry, "type", target.type);
			number(entry, "usable", target.usable_count);
			if (target.zone >= 0)
				number(entry, "zone", zone_table[target.zone].number);
			if (routes.rooms.empty())
				cJSON_AddItemToObject(entry, "origin_details",
						      room_diagnostic(giver->in_room, ch));
			cJSON_AddItemToArray(origins, entry);
		}
	}
	cJSON *named = cJSON_AddArrayToObject(root, "named");
	for (int vnum : { 23501, 6610, 19830, 4405, 82718, 97038, 97039, 97051 })
	{
		cJSON *entry = cJSON_CreateObject();
		number(entry, "vnum", vnum);
		const int prototype = real_mobile(vnum);
		assert(prototype >= 0 && prototype <= top_of_mobt);
		number(entry, "global", mob_index[prototype].number);
		cJSON *instances = cJSON_AddArrayToObject(entry, "instances");
		std::vector<int> checked_zones;
		for (P_char mob = character_list; mob; mob = mob->next)
		{
			if (!IS_NPC(mob) || GET_VNUM(mob) != vnum || mob->in_room < 0 ||
			    mob->in_room > top_of_world)
				continue;
			cJSON *instance = cJSON_CreateObject();
			number(instance, "room", world[mob->in_room].number);
			number(instance, "zone", zone_table[world[mob->in_room].zone].number);
			number(instance, "birthplace", GET_BIRTHPLACE(mob));
			number(instance, "level", GET_LEVEL(mob));
			cJSON_AddItemToArray(instances, instance);
			const int zone_number = zone_table[world[mob->in_room].zone].number;
			if (std::find(checked_zones.begin(), checked_zones.end(), zone_number) !=
			    checked_zones.end())
				continue;
			checked_zones.push_back(zone_number);
			cJSON *levels = cJSON_AddArrayToObject(instance, "levels");
			// Check every possible new quest level, rather than infer eligibility
			// from a prototype interval or a sampled successful assignment.
			for (int level = WORLD_QUEST_MIN_LEVEL; level < TOTALLVLS; ++level)
			{
				const auto kill = world_quest_policy_check_target(
					ch, 16633, level,
					zone_table[world[mob->in_room].zone].number, vnum,
					FIND_AND_KILL, 2);
				world_quest_target_check ask;
				if (level < 50)
					ask = world_quest_policy_check_target(
						ch, 16633, level,
						zone_table[world[mob->in_room].zone].number, vnum,
						FIND_AND_ASK, 1);
				if (kill.status != world_quest_target_status::unavailable ||
				    (level < 50 &&
				     ask.status != world_quest_target_status::unavailable))
				{
					cJSON *result = cJSON_CreateObject();
					number(result, "level", level);
					number(result, "kill", static_cast<int>(kill.status));
					if (level < 50)
						number(result, "ask", static_cast<int>(ask.status));
					cJSON_AddItemToArray(levels, result);
				}
			}
		}
		cJSON_AddItemToArray(named, entry);
	}
	char *text = cJSON_PrintUnformatted(root);
	FILE *out = fopen("quest-world-audit.json.tmp", "w");
	assert(out);
	fputs(text, out);
	fclose(out);
	assert(rename("quest-world-audit.json.tmp", "quest-world-audit.json") == 0);
	cJSON_free(text);
	cJSON_Delete(root);
}
