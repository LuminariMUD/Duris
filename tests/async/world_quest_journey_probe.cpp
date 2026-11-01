
#include "core/prototypes.h"
#include "core/utils.h"
#include "world/world_quest_policy.h"
#include "world/world_quest_policy_math.h"
#include "persistence/persistence_checkpoint.h"
#include <cstdio>
#include <cassert>
#include <vector>
#include <unistd.h>
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
#include "world/specs.prototypes.h"
#include "combat/forced_movement.h"
#include "sql/sql.h"
#include "sql/sql_async.h"
#include "item/item_movement_transaction.h"
#ifdef __NO_MYSQL__
#include "flatfile/flatfile_world_quest_history.h"
#endif
#include <cjson/cJSON.h>
#include <algorithm>
#include <chrono>
#include <unordered_map>
#include <unordered_set>
#include <map>
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
	int quest_gameplay_fixture_zone = -1;
	int quest_gameplay_fixture_vnum = 0;
	int quest_gameplay_fixture_selected = 0;
	int quest_gameplay_fixture_suggested = 0;
	int quest_gameplay_reward_quota = 0;
	int quest_gameplay_bonus_successes = -1;
	int quest_gameplay_bonus_rolls = 0;
	int quest_gameplay_fail_reward_at = 0;
	int quest_gameplay_reward_calls = 0;
	void *quest_gameplay_passive_mobile = nullptr;
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
	input = fopen("quest-reward-control.txt", "r");
	quest_gameplay_reward_quota = 0;
	quest_gameplay_bonus_successes = -1;
	quest_gameplay_bonus_rolls = 0;
	quest_gameplay_fail_reward_at = 0;
	quest_gameplay_reward_calls = 0;
	if (input)
	{
		const int fields = fscanf(input, "%d %d %d", &quest_gameplay_reward_quota,
					  &quest_gameplay_bonus_successes,
					  &quest_gameplay_fail_reward_at);
		assert(fields == 2 || fields == 3);
		fclose(input);
	}
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
			assert(q.quest_active && q.quest_type == FIND_AND_KILL &&
			       q.quest_kill_original > 1);
			q.quest_kill_how_many = 1;
		}
		if (action == 3)
			q.quest_origin_room = 0;
		if (action == 4)
			quest_journey_invalidate(ch);
		if (action == 7)
			for (auto *edge : world[ch->in_room].dir_option)
				if (edge)
					edge->exit_info |= EX_LOCKED;
		if (action == 8)
			ADD_MONEY(ch, 1000);
		if (action == 6)
		{
			const int allowance = sql_world_quest_can_do_another(ch);
			assert(allowance > 0);
			const int64_t yesterday = (time(nullptr) / 86400) * 86400 - 1;
			for (int n = 0; n < allowance; ++n)
			{
#ifdef __NO_MYSQL__
				std::string error;
				assert(flatfile_world_quest_record(
					       getenv("FLATFILE_STATE_DIR"), GET_PID(ch),
					       2147483000 + n, GET_LEVEL(ch), yesterday,
					       &error) == flatfile_world_quest_result::ok);
#else
				assert(sql_queue(
					"INSERT INTO world_quest_accomplished "
					"(pid,timestamp,quest_giver,player_name,player_level,quest_target,reward_vnum,reward_desc) "
					"VALUES (%d,FROM_UNIXTIME(%lld),%d,'Taverek',%d,%d,0,'')",
					GET_PID(ch), static_cast<long long>(yesterday),
					q.quest_giver, GET_LEVEL(ch), 2147483000 + n));
#endif
			}
#ifdef __NO_MYSQL__
			FILE *ready = fopen("quest-history-ready.txt", "w");
			assert(ready);
			fputs("ready", ready);
			fclose(ready);
#else
			// Equivalent to a SELECT executed before midnight whose rows are
			// published to today's game thread. Only this disposable SQL writer
			// session's clock is changed, then restored before the marker read.
			assert(sql_queue("SET timestamp = %lld",
					 static_cast<long long>(yesterday)));
			sql_world_quest_history_load(ch);
			assert(sql_queue("SET timestamp = 0"));
			assert(sql_read("SELECT 1",
					[](bool ok, const sql_rows &)
					{
						assert(ok);
						FILE *ready = fopen("quest-history-ready.txt", "w");
						assert(ready);
						fputs("ready", ready);
						fclose(ready);
					}));
#endif
		}
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
static std::vector<uint64_t> completion_rewards;
extern "C" void quest_gameplay_history(P_char ch, const void *raw_rewards)
{
	assert(ch && IS_PC(ch));
	const auto *rewards = static_cast<const std::vector<P_obj> *>(raw_rewards);
	completion_rewards.clear();
	for (P_obj reward : *rewards)
		if (reward)
			completion_rewards.push_back(reward->obj_uid);
	FILE *record = fopen("quest-reward-uids.txt", "w");
	assert(record);
	for (uint64_t uid : completion_rewards)
		fprintf(record, "%llu\n", static_cast<unsigned long long>(uid));
	fclose(record);
	P_obj reward = rewards->empty() ? nullptr : rewards->front();
	++completion_calls;
	completion_remaining = sql_world_quest_can_do_another(ch);
	completion_level = GET_LEVEL(ch);
	completion_target = ch->only.pc->quest_mob_vnum;
	completion_reward = reward ? reward->obj_uid : 0;
	completion_reward_vnum = reward ? OBJ_VNUM(reward) : 0;
}

extern "C" void quest_gameplay_reward_pause()
{
	if (access("quest-reward-pause", F_OK) != 0)
		return;
	FILE *ready = fopen("quest-reward-ready", "w");
	assert(ready);
	fputs("committed\n", ready);
	fclose(ready);
	while (access("quest-reward-pause", F_OK) == 0)
		usleep(100000);
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

// Navigation belongs to this disposable journey, not quest eligibility.
// This searches ordinary authored exits from the actor's current room and then
// lets real movement commands establish whether the selected fixture is walkable.
struct journey_navigation
{
	std::unordered_map<int, std::vector<int>> rooms;
	size_t work = 0;
};

static journey_navigation navigation_routes(P_char ch)
{
	journey_navigation result;
	const auto passive =
		reinterpret_cast<bool (*)(mob_proc_type)>(quest_gameplay_passive_mobile);
	assert(passive);
	std::unordered_map<int, bool> checked;
	auto ordinary_room = [&](int room)
	{
		if (const auto found = checked.find(room); found != checked.end())
			return found->second;
		const auto &entry = world[room];
		bool ordinary = !entry.affected &&
				(!entry.funct || entry.funct == inn ||
				 entry.funct == crew_shop_proc || entry.funct == ship_shop_proc);
		for (P_char person = entry.people; person && ordinary;
		     person = person->next_in_room)
			if (IS_NPC(person))
				for (mob_proc_type proc : { mob_index[GET_RNUM(person)].func.mob,
							    mob_index[GET_RNUM(person)].qst_func })
				{
					if (proc == shop_keeper)
					{
						const int shop = singleton_shop_id(person);
						if (shop < 0 || shop >= number_of_shops)
						{
							ordinary = false;
							continue;
						}
						proc = shop_index[shop].func;
					}
					ordinary = ordinary && (!proc || proc == world_quest ||
								proc == quester || passive(proc));
				}
		for (P_obj object = entry.contents; object && ordinary;
		     object = object->next_content)
			if (object->R_num >= 0)
			{
				const auto proc = obj_index[object->R_num].func.obj;
				ordinary = !proc || proc == board || proc == artifact_hide ||
					   proc == ring_of_regeneration || proc == tracks ||
					   proc == blood_stains;
			}
		checked[room] = ordinary;
		return ordinary;
	};
	result.rooms.try_emplace(ch->in_room);
	std::vector<int> queue{ ch->in_room };
	bool boat = false;
	for (P_obj object = ch->carrying; object; object = object->next_content)
		boat = boat || object->type == ITEM_BOAT;
	for (P_obj object : ch->equipment)
		boat = boat || (object && object->type == ITEM_BOAT);
	for (size_t next = 0; next < queue.size(); ++next)
		for (int direction = 0; direction < NUM_EXITS; ++direction)
		{
			const auto *edge = world[queue[next]].dir_option[direction];
			++result.work;
			if (!edge || edge->to_room < 0 || edge->to_room > top_of_world ||
			    IS_SET(edge->exit_info,
				   EX_LOCKED | EX_SECRET | EX_BLOCKED | EX_WALLED | EX_SPIKED))
				continue;
			const int to = edge->to_room;
			if (!ordinary_room(queue[next]) || !ordinary_room(to) ||
			    check_wall(queue[next], direction))
				continue;
			if (check_castle_walls(queue[next], to) ||
			    map_entry_barrier(ch, queue[next], to) != forced_block::none)
				continue;
			const auto &room = world[to];
			switch (room.sector_type)
			{
			case SECT_OCEAN:
			case SECT_FIREPLANE:
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
				continue;
			default:
				break;
			}
			if (IS_SET(zone_table[room.zone].flags, ZONE_CLOSED | ZONE_PRIVATE) ||
			    IS_SET(room.room_flags, ROOM_PRIVATE | ROOM_LOCKER | ROOM_GUILD |
							    ROOM_JAIL | ROOM_ATRIUM | ROOM_ARENA) ||
			    room.chance_fall || room.current_speed ||
			    ((room.sector_type == SECT_NO_GROUND ||
			      room.sector_type == SECT_UNDRWLD_NOGROUND) &&
			     !IS_AFFECTED(ch, AFF_FLY)) ||
			    ((room.sector_type == SECT_WATER_NOSWIM ||
			      room.sector_type == SECT_UNDRWLD_NOSWIM) &&
			     !boat && !IS_AFFECTED(ch, AFF_FLY)) ||
			    ((IS_SET(room.room_flags, ROOM_UNDERWATER) ||
			      room.sector_type == SECT_UNDERWATER ||
			      room.sector_type == SECT_UNDERWATER_GR) &&
			     !IS_AFFECTED(ch, AFF_WATERBREATH)))
				continue;
			auto [found, inserted] = result.rooms.try_emplace(to);
			found->second.push_back(queue[next]);
			if (inserted)
				queue.push_back(to);
		}
	return result;
}

// Explicit disposable setup: restore routine target inputs to authored reset
// positions and stop wandering. Do not change levels, stats, counts or provenance.
extern "C" void quest_gameplay_prepare_mobiles(P_char ch, const void *source_lookup)
{
	using lookup_type = const void *(*)(P_char);
	const auto source = reinterpret_cast<lookup_type>(const_cast<void *>(source_lookup));
	const auto &quest = *ch->only.pc;
	for (P_char mob = character_list; mob; mob = mob->next)
	{
		if (!IS_NPC(mob) || !IS_ALIVE(mob) || !source(mob))
			continue;
		const int birthplace = real_room(GET_BIRTHPLACE(mob));
		if (birthplace < 0 || birthplace > top_of_world)
			continue;
		if (quest.quest_active ? GET_VNUM(mob) != quest.quest_mob_vnum :
		    quest_gameplay_kind == FIND_AND_KILL ?
					 GET_LEVEL(mob) < quest_gameplay_level - 4 ||
						 GET_LEVEL(mob) > quest_gameplay_level + 5 :
					 mob_index[GET_RNUM(mob)].number != 1)
			continue;
		SET_BIT(mob->specials.act, ACT_SENTINEL);
		if (mob->in_room != birthplace)
		{
			if (mob->in_room >= 0)
				char_from_room(mob);
			char_to_room(mob, birthplace, 0);
		}
	}
}

// Pick an otherwise eligible, not previously completed fixture whose routine
// instances and birthplaces lie on ordinary outward/return paths. Only the
// debugger's gameplay sampling uses this; production eligibility stays broader.
extern "C" void quest_gameplay_choose_fixture(P_char ch, const void *source_lookup)
{
	using lookup_type = const void *(*)(P_char);
	const auto source = reinterpret_cast<lookup_type>(const_cast<void *>(source_lookup));
	quest_gameplay_fixture_zone = -1;
	quest_gameplay_fixture_vnum = 0;
	quest_gameplay_fixture_selected = quest_gameplay_fixture_suggested = 0;
	if (ch->only.pc->quest_active)
		return;
	const auto navigation = navigation_routes(ch);
	std::unordered_set<int> returns{ ch->in_room };
	std::vector<int> queue{ ch->in_room };
	for (size_t next = 0; next < queue.size(); ++next)
		for (int from : navigation.rooms.at(queue[next]))
			if (returns.insert(from).second)
				queue.push_back(from);
	std::unordered_map<int, std::vector<int>> outgoing;
	for (const auto &[to, incoming] : navigation.rooms)
		for (int from : incoming)
			outgoing[from].push_back(to);
	std::unordered_map<int, int> distances{ { ch->in_room, 0 } };
	queue = { ch->in_room };
	for (size_t next = 0; next < queue.size(); ++next)
		for (int to : outgoing[queue[next]])
			if (distances.emplace(to, distances.at(queue[next]) + 1).second)
				queue.push_back(to);
	std::map<std::pair<int, int>, int> candidates;
	for (P_char mob = character_list; mob; mob = mob->next)
		if (IS_NPC(mob) && IS_ALIVE(mob) && returns.count(mob->in_room) && source(mob) &&
		    !IS_SET(world[mob->in_room].room_flags, ROOM_SAFE | ROOM_ARENA | ROOM_GUILD) &&
		    !IS_SET(zone_table[world[mob->in_room].zone].flags, ZONE_SAFE) &&
		    (quest_gameplay_kind != FIND_AND_KILL ||
		     (GET_LEVEL(mob) >= quest_gameplay_level - 4 &&
		      GET_LEVEL(mob) <= quest_gameplay_level + 5)) &&
		    (quest_gameplay_kind != FIND_AND_ASK ||
		     (mob_index[GET_RNUM(mob)].number == 1 &&
		      (GET_LEVEL(mob) < quest_gameplay_level - 4 ||
		       GET_LEVEL(mob) > quest_gameplay_level + 5))))
			candidates[{ distances.at(mob->in_room), GET_VNUM(mob) }] =
				zone_table[world[mob->in_room].zone].number;
	std::unordered_set<int> checked;
	for (const auto &[key, zone] : candidates)
	{
		const int vnum = key.second;
		if (!checked.insert(vnum).second || sql_world_quest_done_already(ch, vnum) != 0)
			continue;
		bool walkable = true;
		for (P_char mob = character_list; mob; mob = mob->next)
			if (IS_NPC(mob) && GET_VNUM(mob) == vnum && source(mob) &&
			    mob->in_room >= 0 && mob->in_room <= top_of_world &&
			    zone_table[world[mob->in_room].zone].number == zone &&
			    (!returns.count(mob->in_room) ||
			     !returns.count(real_room(GET_BIRTHPLACE(mob)))))
				walkable = false;
		const int needed =
			quest_gameplay_kind == FIND_AND_ASK ? 1 :
			quest_gameplay_reward_quota > 0	    ? quest_gameplay_reward_quota + 1 :
			quest_gameplay_level == 29	    ? 3 :
							      2;
		if (!walkable ||
		    world_quest_policy_check_target(ch, quest_gameplay_origin, quest_gameplay_level,
						    zone, vnum, quest_gameplay_kind, needed)
				    .status != world_quest_target_status::valid)
			continue;
		quest_gameplay_fixture_zone = real_zone(zone);
		quest_gameplay_fixture_vnum = vnum;
		return;
	}
	assert(false && "no eligible ordinary-travel gameplay fixture");
}

extern "C" void quest_gameplay_plan(P_char ch, const void *source_lookup, const char *request)
{
	assert(ch && IS_PC(ch));
	using lookup_type = const void *(*)(P_char);
	const auto source = reinterpret_cast<lookup_type>(const_cast<void *>(source_lookup));
	auto &q = *ch->only.pc;
	if (q.quest_active && q.quest_type == FIND_AND_KILL && !q.quest_accomplished &&
	    !q.quest_kill_how_many && quest_gameplay_reward_quota > 0)
	{
		q.quest_kill_original = quest_gameplay_reward_quota;
		mark_player_dirty_components(GET_PID(ch), PLAYER_COMPONENT_STATUS);
	}
	static unsigned sequence = 0;
	static int last_target = 0;
	if (q.quest_active)
		last_target = q.quest_mob_vnum;
	cJSON *root = cJSON_CreateObject();
	cJSON_AddStringToObject(root, "request", request);
	number(root, "sequence", ++sequence);
	number(root, "pid", getpid());
	number(root, "actor_level", GET_LEVEL(ch));
	number(root, "profile_level", quest_gameplay_level);
	number(root, "profile_kind", quest_gameplay_kind);
	number(root, "fixture_vnum", quest_gameplay_fixture_vnum);
	number(root, "fixture_zone",
	       quest_gameplay_fixture_zone >= 0 ? zone_table[quest_gameplay_fixture_zone].number :
						  -1);
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
	char_data completion_view = *ch;
	completion_view.player.level = completion_level;
	number(root, "completion_remaining_at_level",
	       completion_level > 0 ? sql_world_quest_can_do_another(&completion_view) : -1);
	number(root, "completion_target", completion_target);
	cJSON_AddStringToObject(root, "reward_uid", std::to_string(completion_reward).c_str());
	number(root, "reward_vnum", completion_reward_vnum);
	cJSON *reward_uids = cJSON_AddArrayToObject(root, "reward_uids");
	for (uint64_t uid : completion_rewards)
		cJSON_AddItemToArray(reward_uids, cJSON_CreateString(std::to_string(uid).c_str()));

	number(root, "active", q.quest_active);
	number(root, "accomplished", q.quest_accomplished);
	number(root, "due", q.quest_replacement_due);
	number(root, "accepted_level", q.quest_level);
	number(root, "type", q.quest_type);
	number(root, "mob", q.quest_mob_vnum);
	number(root, "zone", q.quest_zone_number);
	number(root, "kills", q.quest_kill_how_many);
	number(root, "quota", q.quest_kill_original);
	number(root, "frozen_item_count", q.quest_reward_item_count);
	number(root, "bonus_rolls", quest_gameplay_bonus_rolls);
	number(root, "reward_calls", quest_gameplay_reward_calls);
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
	if (FILE *ready = fopen("quest-history-ready.txt", "r"))
	{
		fclose(ready);
		number(root, "retained_history", sql_world_quest_done_already(ch, 2147483000));
#ifdef __NO_MYSQL__
		int yesterday_count = 0;
		std::string error;
		assert(flatfile_world_quest_count_day(getenv("FLATFILE_STATE_DIR"), GET_PID(ch), 50,
						      (time(nullptr) / 86400) * 86400 - 1,
						      &yesterday_count,
						      &error) == flatfile_world_quest_result::ok);
		number(root, "yesterday_history", yesterday_count);
#endif
	}
	cJSON_AddStringToObject(root, "month", strip_ansi(month_name[time_info.month]).c_str());
	cJSON *items = cJSON_AddArrayToObject(root, "items");
	for (P_obj object = ch->carrying; object; object = object->next_content)
		inventory_item(items, object);
	for (P_obj object : ch->equipment)
		if (object)
			inventory_item(items, object);

	const int origin = q.quest_active ? q.quest_origin_room : quest_gameplay_origin;
	number(root, "route_origin", origin);
	const auto start = std::chrono::steady_clock::now();
	const auto routes = navigation_routes(ch);
	number(root, "route_work", routes.work);
	number(root, "route_rooms", routes.rooms.size());
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
	const bool seeking_target = q.quest_active && !q.quest_accomplished;
	if (seeking_target)
		for (P_char mob = character_list; mob; mob = mob->next)
		{
			if (!IS_NPC(mob) || !IS_ALIVE(mob) || mob->in_room < 0 ||
			    mob->in_room > top_of_world || GET_VNUM(mob) != q.quest_mob_vnum ||
			    zone_table[world[mob->in_room].zone].number != q.quest_zone_number ||
			    GET_HIT(mob) <= 0 || mob->following || GET_MASTER(mob) ||
			    IS_AFFECTED(mob, AFF_CHARM) || !source(mob) ||

			    !ac_can_see_from(ch, mob, mob->in_room))
				continue;
			targets[mob->in_room].push_back(mob);
			if (q.quest_type == FIND_AND_ASK)
				number(root, "target_level", GET_LEVEL(mob));
		}
	std::unordered_map<int, std::vector<int>> outgoing;
	for (const auto &[to, incoming] : routes.rooms)
		for (int from : incoming)
			outgoing[from].push_back(to);
	std::unordered_map<int, int> previous{ { ch->in_room, NOWHERE } };
	std::vector<int> queue{ ch->in_room };
	int destination = NOWHERE;
	for (size_t next = 0; next < queue.size(); ++next)
	{
		const int room = queue[next];
		if (seeking_target ? targets.count(room) : room == real_room(origin))
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
		if (seeking_target)
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
			const auto origin_region = world_quest_policy_region(giver->in_room);
			number(entry, "surface_region", origin_region.surface);
			number(entry, "underdark_region", origin_region.underdark);
			int underdark = 0, surface = 0;
			for (int room = 0; room <= top_of_world; ++room)
				if (IS_MAP_ROOM(room))
				{
					const auto region = world_quest_policy_region(room);
					underdark += region.underdark > 0 &&
						     region.underdark == origin_region.underdark;
					surface += region.surface > 0 &&
						   region.surface == origin_region.surface;
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
				    (level >= 30 ||
				     (origin_region.surface > 0 &&
				      origin_region.surface ==
					      world_quest_policy_region(mob->in_room).surface) ||
				     (origin_region.underdark > 0 &&
				      origin_region.underdark ==
					      world_quest_policy_region(mob->in_room).underdark)))
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
			if (!origin_region.surface && !origin_region.underdark)
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
