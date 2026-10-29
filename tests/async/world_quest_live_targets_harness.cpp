#include "core/prototypes.h"
#include "core/utils.h"
#include "world/world_quest_policy.h"
#include "world/world_quest_policy_math.h"
#include "world/map.h"
#include "world/weather.h"
#include "combat/justice.h"
#include "persistence/persistence_checkpoint.h"
#include "economy/currency_transaction.h"
#include "world/zone_story_quest_runtime.h"
#include "cmd/interp.h"
#include "world/specs.prototypes.h"

#include <cassert>
#include <cstring>
#include <deque>
#include <iostream>
#include <memory>
#include <set>
#include <string>
#include <vector>

room_data rooms[7]{};
P_room world = rooms;
zone_data zones[3]{};
zone_data *zone_table = zones;
int top_of_world = 6, top_of_zone_table = 2;
index_data mobiles[70]{}, objects[6]{};
P_index mob_index = mobiles, obj_index = objects;
int top_of_mobt = 2, top_of_objt = 5;
int number_of_quests = 0;
quest_data quest_index[1]{};
shop_data shops[1]{};
shop_data *shop_index = shops;
int number_of_shops = 1;
hometown_data hometowns[LAST_HOME]{};
time_info_data time_info{};
const char *month_name[] = { "Moon" };
P_char character_list = nullptr;

std::deque<room_direction_data> exits;
std::vector<reset_com> commands;
std::vector<std::unique_ptr<char_data>> live;
std::deque<npc_only_data> npc_state;
char_data player{};
pc_only_data pc{};
std::set<int> fresh;
std::vector<int> history_reads;
std::string mode;
int level, preferred_type, probe_reads = 0, object_reads = 0, dirty_marks = 0;
int shown_map = NOWHERE, map_calls = 0;
std::string feedback;
void run_payment(P_char, int origin, int fee, bool committed);
void run_map_payment(P_char, int fee);

int unknown_room(int, P_char, int, char *)
{
	std::abort();
}
int unknown_object(P_obj, P_char, int, char *)
{
	std::abort();
}
int real_zone(const int vnum)
{
	for (int zone = 0; zone <= top_of_zone_table; ++zone)
		if (zones[zone].number == vnum)
			return zone;
	return -1;
}

int inn(int, P_char, int, char *)
{
	std::abort();
}
int ship_shop_proc(int, P_char, int, char *)
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
int shop_keeper(P_char, P_char, int, char *)
{
	std::abort();
}
int singleton_shop_id(P_char)
{
	return 0;
}
void logit(const char *, const char *, ...) {}
bool has_innate(P_char, int)
{
	return false;
}
bool IS_TWILIGHT_ROOM(int room)
{
	assert(room >= 0 && room <= top_of_world);
	return false;
}
bool IS_OUTDOORS(int room)
{
	assert(room >= 0 && room <= top_of_world);
	return false;
}
P_char get_linked_char(P_char, int)
{
	return nullptr;
}
bool affected_by_spell(P_char, int)
{
	return false;
}
bool affected_by_spell_flagged(P_char, int, uint)
{
	return false;
}
affected_type *get_spell_from_char(P_char, int, void *, int)
{
	return nullptr;
}
bool AdjacentInRoom(P_char, P_char)
{
	return true;
}
bool aggressive_to_race(P_char, P_char)
{
	return false;
}
bool aggressive_to_class(P_char, P_char)
{
	return false;
}
bool is_aggr_to(P_char, P_char)
{
	std::abort();
}
int CheckFor_remember(P_char, P_char)
{
	return false;
}
int IS_MORPH(P_char)
{
	return 0;
}
int GET_CLASS(P_char ch, uint cls)
{
	return (ch->player.m_class & cls) != 0;
}
int BOUNDED(int low, int value, int high)
{
	return std::max(low, std::min(value, high));
}
int share_limit = 0;

float get_property(const char *name, double fallback)
{
	return !strcmp(name, "world.quest.share.max") ? share_limit : static_cast<float>(fallback);
}
int get_property(const char *, int fallback)
{
	return fallback;
}
int difficulty_scale_world_quest_kills(int kills)
{
	return kills;
}
void send_to_char(const char *text, P_char)
{
	feedback += text;
}
void gmcp_quest_status(P_char) {}
void gmcp_quest_status(P_char, world_quest_target_status) {}
void gmcp_quest_map(P_char) {}
void show_map_at(P_char, int room)
{
	shown_map = room;
	++map_calls;
}
void ADD_MONEY(P_char ch, int value)
{
	GET_COPPER(ch) += value;
}
int daily_remaining = 1, wallet_debits = 0, reward_claims = 0, history_writes = 0;
bool currency_transaction_submit_wallet_value(P_char ch, int64_t value, currency_reason_type,
					      int64_t, critical_source_site,
					      critical_deadline_class,
					      currency_completion_fn callback, const void *context,
					      size_t size)
{
	GET_COPPER(ch) += value;
	wallet_debits += value < 0;
	callback(ch, true, {}, 0, static_cast<const uint8_t *>(context), size);
	return true;
}
P_char command_giver = nullptr, command_recipient = nullptr;
bool consent = true;

P_char ParseTarget(P_char, char *name)
{
	return !strcmp(name, "bartender") ? command_giver :
	       !strcmp(name, "friend")	  ? command_recipient :
					    nullptr;
}
bool is_linked_to(P_char, P_char, ush_int type)
{
	return type == LNK_CONSENT && consent;
}
void mobsay(P_char, const char *text)
{
	feedback += text;
}
void act(const char *text, int, P_char, P_obj, void *, int)
{
	feedback += text;
}
void do_yell(P_char, char *, int)
{
	std::abort();
}
char *coin_stringv(int, int)
{
	static char text[] = "coins";
	return text;
}
int difficulty_scale_world_quest_fee(int fee)
{
	return fee;
}
void quest_full_reward(P_char, P_char, int)
{
	++reward_claims;
}
namespace zone_story_quest_runtime
{
zone_story_quest_feature::service *service()
{
	return nullptr;
}
std::string render_daily(P_char, bool, std::string *)
{
	std::abort();
}
}

void sql_world_quest_finished(P_char, P_obj)
{
	++history_writes;
}
int sql_world_quest_can_do_another(P_char)
{
	return daily_remaining;
}
void mark_player_dirty_components(int, player_component_mask_t component)
{
	assert(component == PLAYER_COMPONENT_STATUS);
	++dirty_marks;
}
int number(int low, int high)
{
	return low == 1 && high == 2 ? preferred_type : low;
}
int real_room(int vnum)
{
	for (int room = 0; room <= top_of_world; ++room)
		if (world[room].number == vnum)
			return room;
	return NOWHERE;
}
int real_room0(const int)
{
	std::abort();
}
int real_zone0(const int)
{
	std::abort();
}

int real_mobile(int vnum)
{
	for (int rnum = 0; rnum <= top_of_mobt; ++rnum)
		if (mobiles[rnum].virtual_number == vnum)
			return rnum;
	return -1;
}
int real_object(int vnum)
{
	for (int rnum = 0; rnum <= top_of_objt; ++rnum)
		if (objects[rnum].virtual_number == vnum)
			return rnum;
	return -1;
}
int get_map_room(int zone)
{
	return zone == 1 && mode == "mapless" ? NOWHERE : 6; // Deliberately wrong first marker.
}
int itemvalue(P_obj object)
{
	return object->value[0];
}
P_obj read_object(int nr, int type)
{
	++object_reads;
	int rnum = type == VIRTUAL ? real_object(nr) : nr;
	if (rnum < 0 || (mode == "no_reward" && rnum >= 3))
		return nullptr;
	auto object = new obj_data{};
	object->R_num = rnum;
	object->type = ITEM_ARMOR;
	object->wear_flags = ITEM_TAKE;
	object->name = const_cast<char *>("fixture reward");
	object->value[0] = 40 + 10 * (rnum % 3);
	return object;
}
void extract_obj(P_obj object, int)
{
	delete object;
}
P_char read_mobile_probe(int nr, int type)
{
	const int rnum = type == VIRTUAL ? real_mobile(nr) : nr;
	assert(rnum >= 0);
	++probe_reads;
	auto mob = new char_data{};
	mob->only.npc = new npc_only_data{};
	mob->only.npc->R_num = rnum;
	mob->specials.act = ACT_ISNPC;
	mob->player.level = mode == "no_level_window" && rnum == 2 ? 60 : level;
	mob->player.race = RACE_HUMAN;
	GET_MAX_HIT(mob) = GET_HIT(mob) = 100;
	GET_EXP(mob) = 100;
	SET_POS(mob, STAT_NORMAL + POS_STANDING);
	mob->in_room = NOWHERE;
	++mobiles[rnum].number;
	return mob;
}
void extract_char(P_char mob)
{
	--mobiles[GET_RNUM(mob)].number;
	delete mob->only.npc;
	delete mob;
}
int sql_world_quest_done_already(P_char, int vnum)
{
	assert(std::find(history_reads.begin(), history_reads.end(), vnum) == history_reads.end());
	history_reads.push_back(vnum);
	if (mode == "history_error")
		return -1;
	return fresh.count(vnum) ? 0 : 1;
}
void edge(int from, int dir, int to)
{
	room_direction_data value{};
	value.to_room = to;
	value.key = -1;
	exits.push_back(value);
	world[from].dir_option[dir] = &exits.back();
}
void two_way(int from, int dir, int to, int reverse)
{
	edge(from, dir, to);
	edge(to, reverse, from);
}
void move(P_char mob, int room)
{
	if (mob->in_room >= 0)
	{
		P_char *link = &world[mob->in_room].people;
		while (*link && *link != mob)
			link = &(*link)->next_in_room;
		assert(*link == mob);
		*link = mob->next_in_room;
	}
	mob->in_room = room;
	mob->next_in_room = room >= 0 ? world[room].people : nullptr;
	if (room >= 0)
		world[room].people = mob;
}
P_char spawn(int rnum, int birthplace, int room)
{
	live.push_back(std::make_unique<char_data>());
	auto mob = live.back().get();
	npc_state.emplace_back();
	mob->only.npc = &npc_state.back();
	mob->only.npc->R_num = rnum;
	mob->specials.act = ACT_ISNPC;
	mob->player.level = level;
	mob->player.race = RACE_HUMAN;
	GET_MAX_HIT(mob) = GET_HIT(mob) = 100;
	GET_EXP(mob) = 100;
	SET_POS(mob, STAT_NORMAL + POS_STANDING);
	GET_BIRTHPLACE(mob) = world[birthplace].number;
	mob->in_room = NOWHERE;
	mob->next = character_list;
	character_list = mob;
	move(mob, room);
	++mobiles[rnum].number;
	return mob;
}

int main(int argc, char **argv)
{
	assert(argc == 4);
	level = std::stoi(argv[1]);
	mode = argv[2];
	preferred_type = std::string(argv[3]) == "ask" ? FIND_AND_ASK : FIND_AND_KILL;
	fresh.insert(preferred_type == FIND_AND_ASK ? 1003 : 1002);
	const bool budget_case = mode == "history_cap" || mode == "history_cap_zones" ||
				 mode == "last_history" || mode == "last_history_zones" ||
				 mode == "probe_cap" || mode == "probe_cap_zones" ||
				 mode == "last_probe";
	const int prototype_count = mode == "probe_cap_zones" || mode == "last_history_zones" ? 32 :
												64;
	if (budget_case)
	{
		top_of_mobt = prototype_count;
		fresh.clear();
		if (mode == "probe_cap" || mode == "probe_cap_zones" || mode == "last_probe")
			for (int rnum = 0; rnum < prototype_count; ++rnum)
				fresh.insert(1002 + rnum);
		else if (mode == "history_cap_zones")
			fresh.insert(1003);
		else
			fresh.insert(mode == "history_cap" ? 1034 : 1033);
	}
	const int room_numbers[] = { 1000, 1001, 1099, 2000, 2099, 500001, 500002 };
	for (int room = 0; room <= top_of_world; ++room)
	{
		rooms[room].number = room_numbers[room];
		rooms[room].zone = room < 3 ? 0 : room < 5 ? 1 : 2;
		rooms[room].sector_type = SECT_FIELD;
		rooms[room].light = 1;
		rooms[room].continent = room == 6 ? CONT_EC : room == 5 ? CONT_GC : 0;
	}
	zones[0].number = 10;
	zones[0].real_bottom = 0;
	zones[0].real_top = 2;
	zones[1].number = 20;
	zones[1].real_bottom = 3;
	zones[1].real_top = 4;
	zones[2].number = 500;
	zones[2].real_bottom = 5;
	zones[2].real_top = 6;
	zones[2].flags = ZONE_MAP;
	zones[0].reset_mode = zones[1].reset_mode = 2;
	if (mode == "no_reset")
		zones[0].reset_mode = 0;
	const int mob_numbers[] = { 1002, 1003, 2001 };
	for (int rnum = 0; rnum < 3; ++rnum)
		mobiles[rnum].virtual_number = mob_numbers[rnum];
	if (budget_case)
	{
		for (int rnum = 0; rnum < prototype_count; ++rnum)
			mobiles[rnum].virtual_number = 1002 + rnum;
		mobiles[prototype_count].virtual_number = 2001;
	}
	for (int rnum = 0; rnum < 6; ++rnum)
		objects[rnum].virtual_number = (rnum < 3 ? 1005 : 2005) + rnum % 3;
	two_way(0, DIR_EAST, 5, DIR_WEST);
	two_way(5, DIR_EAST, 3, DIR_WEST);
	edge(4, DIR_WEST, 3); // A distribution room with no ordinary inbound route.
	if (mode == "foreign")
	{
		rooms[5].dir_option[DIR_EAST] = rooms[3].dir_option[DIR_WEST] = nullptr;
		two_way(5, DIR_EAST, 6, DIR_WEST);
		two_way(6, DIR_EAST, 3, DIR_WEST);
	}
	if (mode == "mapless")
	{
		rooms[5].dir_option[DIR_EAST] = rooms[3].dir_option[DIR_WEST] = nullptr;
		two_way(0, DIR_NORTH, 1, DIR_SOUTH);
		two_way(1, DIR_EAST, 3, DIR_WEST);
	}
	if (mode == "no_return")
		rooms[3].dir_option[DIR_WEST] = nullptr;
	commands = { { 'M', false, 0, 6, 3, 100 },
		     { 'M', false, 0, 6, 4, 100 },
		     { 'M', false, 1, 1, 3, 100 } };
	if (mode == "rare")
		commands[2].arg4 = 1;
	if (mode == "conditional")
		commands[2].if_flag = true;
	if (mode == "staging_release")
		commands[2].arg3 = 4;
	if (mode == "mixed")
		commands.push_back({ 'M', false, 1, 1, 3, 1 });
	if (mode == "random")
		commands.push_back({ 'Y', false, 1, 1, 3, 100 });
	if (mode == "follower")
		commands.push_back({ 'F', false, 1, 1, 3, 100 });
	if (mode == "mount")
		commands.push_back({ 'R', false, 1, 1, 3, 100 });
	if (mode == "cross_zone_retry")
	{
		two_way(0, DIR_NORTH, 1, DIR_SOUTH);
		commands.push_back({ 'M', false, 0, 8, 1, 100 });
	}
	if (budget_case)
	{
		commands.clear();
		two_way(0, DIR_NORTH, 1, DIR_SOUTH);
		for (int rnum = 0; rnum < prototype_count; ++rnum)
		{
			const int room = mode == "history_cap_zones" ? (rnum % 2 ? 3 : 1) :
					 mode == "last_history_zones" && rnum < 31 ? 1 :
										     3;
			commands.push_back({ 'M', false, rnum, 4, room, 100 });
			if (mode == "probe_cap_zones")
				commands.push_back({ 'M', false, rnum, 4, 1, 100 });
		}
	}
	commands.push_back({ 'S', false, 0, 0, 0, 0 });
	zones[0].cmd = commands.data();
	player.only.pc = &pc;
	pc.pid = 42;
	player.player.level = level;
	player.player.race = RACE_HUMAN;
	player.player.racewar = RACEWAR_GOOD;
	SET_POS(&player, STAT_NORMAL + POS_STANDING);
	player.in_room = 0;
	rooms[0].people = &player;
	character_list = &player;
	std::vector<P_char> ordinary;
	if (budget_case)
	{
		for (int rnum = 0; rnum < prototype_count; ++rnum)
		{
			const int room = mode == "history_cap_zones" ? (rnum % 2 ? 3 : 1) :
					 mode == "last_history_zones" && rnum < 31 ? 1 :
										     3;
			for (int n = 0; n < 2; ++n)
			{
				auto mob = spawn(rnum, room, room);
				if (mode == "probe_cap" || (mode == "last_probe" && rnum < 31))
					mob->specials.affected_by |= AFF_INVISIBLE;
				if (mode == "probe_cap_zones")
					spawn(rnum, 1, 1)->specials.affected_by |= AFF_INVISIBLE;
			}
		}
	}
	else if (mode != "zero")
	{
		for (int n = 0; n < (mode == "quota" ? 4 : mode == "one_usable" ? 1 : 2); ++n)
			ordinary.push_back(spawn(0, 3, mode == "unroomed" ? NOWHERE : 3));
		for (int n = 0; n < (mode == "quota" ? 2 : mode == "one_usable" ? 5 : 4); ++n)
			spawn(0, 4, 4);
		spawn(1, mode == "staging_release" ? 4 : 3, 3);
		if (mode == "cross_zone_retry")
			for (int n = 0; n < 2; ++n)
				spawn(0, 1, 1)->specials.affected_by |= AFF_INVISIBLE;
	}
	for (int rnum = 0; rnum <= top_of_mobt; ++rnum)
		mobiles[rnum].desc2 = const_cast<char *>("a fixture target");

	assert(world_quest_policy_bootstrap());
	const int boot_probes = probe_reads;
	const int boot_objects = object_reads;
	assert(boot_probes == top_of_mobt + 1);
	assert(zones[0].avg_mob_level == level);
	assert(zones[1].avg_mob_level == (mode == "no_level_window" ? 60 : level));
	for (auto &owned : live)
	{
		auto mob = owned.get();
		if (!budget_case && GET_RNUM(mob) == 0 && mob->in_room == 3)
		{
			if (mode == "protected")
				mob->specials.act |= ACT_IGNORE;
			if (mode == "noexp")
				GET_EXP(mob) = 0;
			if (mode == "summoned")
				mob->only.npc->summoned_instance = true;
			if (mode == "summon_kind")
				mob->only.npc->summon_kind = 1;
			if (mode == "charmed")
				mob->specials.affected_by |= AFF_CHARM;
			if (mode == "following")
				mob->following = &player;
		}
		if (!budget_case && GET_RNUM(mob) == 1)
		{
			if (mode == "moved")
				move(mob, 0);
			if (mode == "unspeaking")
				mob->player.race = RACE_ANIMAL;
			if (mode == "invisible")
				mob->specials.affected_by |= AFF_INVISIBLE;
			if (mode == "hidden")
				mob->specials.affected_by |= AFF_HIDE;
			if (mode == "aggressive")
				mob->only.npc->aggro_flags = AGGR_ALL;
			if (mode == "sleeping")
				SET_POS(mob, STAT_SLEEPING + POS_PRONE);
		}
	}
	if (mode == "safe")
		rooms[3].room_flags |= ROOM_SAFE;
	if (mode == "silent")
		rooms[3].room_flags |= ROOM_SILENT;
	obj_data hide_artifact{}, regeneration_ring{};
	if (mode == "gear")
	{
		hide_artifact.R_num = 0;
		regeneration_ring.R_num = 1;
		objects[0].func.obj = artifact_hide;
		objects[1].func.obj = ring_of_regeneration;
		player.carrying = &hide_artifact;
		hide_artifact.next_content = &regeneration_ring;
	}
	if (mode == "validate")
	{
		using status = world_quest_target_status;
		const int vnum = preferred_type == FIND_AND_KILL ? 1002 : 1003;
		auto check = [&](status expected_status, int needed = 1, int origin = 1000)
		{
			const auto before_actor = player;
			const auto before_pc = pc;
			const std::vector<room_data> before_rooms(world, world + top_of_world + 1);
			const auto actual = world_quest_policy_check_target(
				&player, origin, level, 20, vnum, preferred_type, needed);
			if (actual.status != expected_status)
				std::cerr << "expected status " << static_cast<int>(expected_status)
					  << " got " << static_cast<int>(actual.status) << '\n';
			assert(actual.status == expected_status);
			assert(actual.work <= WORLD_QUEST_MAX_ROUTE_WORK);
			assert(!memcmp(&before_actor, &player, sizeof(player)));
			assert(!memcmp(&before_pc, &pc, sizeof(pc)));
			assert(!memcmp(before_rooms.data(), world,
				       before_rooms.size() * sizeof(room_data)));
			assert(history_reads.empty() && dirty_marks == 0);
			assert(probe_reads == boot_probes && object_reads == boot_objects);
			return actual;
		};
		assert(check(status::valid).map_room == 5);
		check(status::needs_origin, 1, 0);
		check(status::unavailable, 1, 999999);
		move(&player, 2);
		check(status::valid); // The accepted origin survives ordinary player travel.
		move(&player, 0);
		player.specials.affected_by |= AFF_BLIND;
		check(status::blocked);
		player.specials.affected_by &= ~AFF_BLIND;
		SET_POS(&player, STAT_SLEEPING | POS_PRONE);
		check(status::blocked);
		SET_POS(&player, STAT_NORMAL | POS_STANDING);
		hide_artifact.R_num = 0;
		objects[0].func.obj = unknown_object;
		player.carrying = &hide_artifact;
		check(status::unproven);
		player.carrying = nullptr;
		objects[0].func.obj = nullptr;
		rooms[3].funct = unknown_room;
		check(status::unproven);
		rooms[3].funct = nullptr;
		// An unrelated unknown branch cannot conceal a definitive final lock.
		two_way(0, DIR_NORTH, 1, DIR_SOUTH);
		rooms[1].funct = unknown_room;
		rooms[5].dir_option[DIR_EAST]->exit_info |= EX_LOCKED;
		check(status::unavailable);
		rooms[5].dir_option[DIR_EAST]->exit_info &= ~EX_LOCKED;
		check(status::valid);
		rooms[1].funct = nullptr;
		rooms[3].dir_option[DIR_WEST]->exit_info |= EX_LOCKED;
		check(status::unavailable); // A return path is required independently.
		rooms[3].dir_option[DIR_WEST]->exit_info &= ~EX_LOCKED;
		const int sector = rooms[3].sector_type;
		rooms[3].sector_type = SECT_NO_GROUND;
		if (level >= 30)
		{
			check(status::blocked); // Removing one's own flight is not a world invalidation.
			player.specials.affected_by |= AFF_FLY;
			check(status::valid);
			player.specials.affected_by &= ~AFF_FLY;
		}
		else
			check(status::unavailable); // Gear cannot extend an accepted 11-29 contract.
		rooms[3].sector_type = sector;
		if (preferred_type == FIND_AND_KILL)
		{
			check(status::valid,
			      2); // Remaining work, without the new-quest minus-one rule.
			check(status::unavailable, 3);
			move(ordinary[0], 2);
			check(status::valid, 1);
			check(status::unavailable, 2);
			move(ordinary[1], 2);
			check(status::unavailable);
			move(ordinary[0], 3);
			move(ordinary[1], 3);
			rooms[3].room_flags |= ROOM_SAFE;
			check(status::unavailable);
			rooms[3].room_flags &= ~ROOM_SAFE;
			for (auto mob : ordinary)
				mob->specials.affected_by |= AFF_CHARM;
			check(status::blocked);
			for (auto mob : ordinary)
				mob->specials.affected_by &= ~AFF_CHARM;
		}
		else
		{
			player.specials.affected_by2 |= AFF2_SILENCED;
			check(status::blocked);
			player.specials.affected_by2 &= ~AFF2_SILENCED;
			mobiles[1].qst_func = world_quest;
			check(status::unproven); // Known travel-safe does not mean ASK-safe.
			mobiles[1].qst_func = nullptr;
			P_char ask = live.back().get();
			move(ask, 2);
			check(status::unavailable);
			move(ask, 3);
			ask->specials.affected_by |= AFF_INVISIBLE;
			check(level < 31 ? status::unavailable : status::blocked);
			ask->specials.affected_by &= ~AFF_INVISIBLE;
			rooms[3].room_flags |= ROOM_SILENT;
			check(status::unavailable);
			rooms[3].room_flags &= ~ROOM_SILENT;
		}
		// Same accepted-target API, not just the raw route helper, fails
		// unproven when its shared traversal exceeds the room bound.
		std::vector<room_data> oversized(WORLD_QUEST_MAX_ROUTE_ROOMS + 8);
		std::copy(std::begin(rooms), std::end(rooms), oversized.begin());
		world = oversized.data();
		top_of_world = static_cast<int>(oversized.size()) - 1;
		for (int room = 7; room <= top_of_world; ++room)
		{
			world[room].number = 500000 + room;
			world[room].continent = CONT_GC;
			edge(room == 7 ? 5 : room - 1, DIR_NORTH, room);
			edge(room, DIR_SOUTH, room == 7 ? 5 : room - 1);
		}
		check(status::unproven);
		world = rooms;
		top_of_world = 6;

		// Exercise the durable transition, not only its policy verdict.
		pc.quest_active = 1;
		pc.quest_type = preferred_type;
		pc.quest_mob_vnum = vnum;
		pc.quest_zone_number = 20;
		pc.quest_level = level;
		pc.quest_origin_room = 1000;
		pc.quest_giver = 9000;
		pc.quest_kill_original = preferred_type == FIND_AND_KILL ? 4 : 0;
		pc.quest_kill_how_many = preferred_type == FIND_AND_KILL ? 3 : 0;
		pc.quest_receiver = 999;
		pc.quest_shares_left = 2;
		pc.quest_map_bought = 1;
		pc.quest_map_room = 500001;
		pc.quest_started = 12345;
		dirty_marks = 0;
		const auto accepted = pc;
		// The oversized graph's added branch is no longer part of this world.
		rooms[5].dir_option[DIR_NORTH] = nullptr;
		assert(world_quest_refresh(&player) == status::valid);
		assert(!memcmp(&pc, &accepted, sizeof(pc)) && dirty_marks == 0);
		pc.quest_origin_room = 0;
		pc.quest_map_room = 0;
		assert(world_quest_refresh(&player) == status::needs_origin);
		assert(!pc.quest_replacement_due && !pc.quest_origin_room);
		assert(world_quest_refresh(&player, 1000) == status::valid);
		assert(pc.quest_origin_room == 1000 && pc.quest_map_room == 500001);
		dirty_marks = 0;
		for (auto &mob : live)
			if (GET_VNUM(mob.get()) == vnum && mob->in_room == 3)
				move(mob.get(), 2);
		assert(world_quest_refresh(&player) == status::unavailable);
		assert(pc.quest_active == 0 && pc.quest_replacement_due == 1 && dirty_marks == 1);
		assert(pc.quest_level == accepted.quest_level &&
		       pc.quest_type == accepted.quest_type);
		assert(pc.quest_kill_original == accepted.quest_kill_original &&
		       pc.quest_kill_how_many == accepted.quest_kill_how_many);
		assert(pc.quest_map_bought == 1 && pc.quest_map_room == 0 &&
		       pc.quest_shares_left == 2 && pc.quest_receiver == 999 &&
		       pc.quest_started == 12345 && pc.quest_origin_room == 1000);
		assert(history_reads.empty());
		const auto due = pc;
		assert(world_quest_refresh(&player) == status::unavailable);
		assert(!memcmp(&pc, &due, sizeof(pc)) && dirty_marks == 1);
		auto giver = spawn(2, 0, 0);
		fresh.clear();
		history_reads.clear();
		assert(!world_quest_replace(&player, giver));
		assert(!memcmp(&pc, &due, sizeof(pc)));
		// The original work can be restored without charging or replaying XP.
		for (auto &mob : live)
			if (GET_VNUM(mob.get()) == vnum && mob->in_room == 2)
				move(mob.get(), 3);
		fresh.insert(vnum);
		history_reads.clear();
		assert(world_quest_replace(&player, giver));
		assert(pc.quest_active == 1 && pc.quest_replacement_due == 0);
		assert(pc.quest_type == accepted.quest_type &&
		       pc.quest_level == accepted.quest_level);
		assert(pc.quest_kill_original == accepted.quest_kill_original &&
		       pc.quest_kill_how_many == accepted.quest_kill_how_many);
		assert(pc.quest_map_bought == 1 && pc.quest_map_room == 500001 &&
		       pc.quest_shares_left == 2 && pc.quest_receiver == 999 &&
		       pc.quest_started == 12345);
		const auto replaced = pc;
		assert(!world_quest_replace(&player, giver));
		assert(!memcmp(&pc, &replaced, sizeof(pc)));
		// Finished legacy work remains claimable even without its final target.
		pc.quest_accomplished = 1;
		pc.quest_origin_room = 0;
		pc.quest_mob_vnum = 999999;
		history_reads.clear();
		dirty_marks = 0;
		const auto complete = pc;
		assert(world_quest_refresh(&player) == status::valid);
		assert(!memcmp(&pc, &complete, sizeof(pc)) && dirty_marks == 0 &&
		       history_reads.empty());

		// Complete production bartender commands: parsing, payment, recovery
		// ordering, free cancellation and the normal voluntary abandon.
		command_giver = giver;
		auto ask = [&](const char *what)
		{
			history_reads.clear();
			feedback.clear();
			std::string argument = std::string("bartender ") + what;
			assert(world_quest(giver, &player, CMD_ASK, argument.data()) != FALSE);
		};
		pc = accepted;
		daily_remaining = 0;
		wallet_debits = reward_claims = history_writes = 0;
		GET_COPPER(&player) = 10000;
		rooms[5].dir_option[DIR_EAST]->exit_info |= EX_LOCKED;
		ask("quest");
		assert(!pc.quest_active && pc.quest_replacement_due && GET_MONEY(&player) == 10000);
		const auto waiting = pc;
		ask("quest");
		assert(!memcmp(&pc, &waiting, sizeof(pc)));
		ask("map");
		assert(GET_MONEY(&player) == 10000 && wallet_debits == 0 && history_writes == 0);
		rooms[5].dir_option[DIR_EAST]->exit_info &= ~EX_LOCKED;
		player.player.level = 10;
		ask("quest"); // Continuation precedes new-purchase level and allowance gates.
		assert(pc.quest_active && !pc.quest_replacement_due && GET_MONEY(&player) == 10000);
		assert(pc.quest_level == level && pc.quest_type == preferred_type &&
		       pc.quest_kill_original == accepted.quest_kill_original &&
		       pc.quest_kill_how_many == accepted.quest_kill_how_many &&
		       pc.quest_shares_left == 2 && pc.quest_map_bought == 1);
		assert(wallet_debits == 0 && reward_claims == 0 && history_writes == 0);
		player.player.level = level;
		daily_remaining = 1;
		pc.quest_map_bought = 0;
		map_calls = 0;
		ask("map");
		assert(pc.quest_map_bought == 1 && GET_MONEY(&player) == 10000 - 10 * level &&
		       wallet_debits == 1 && map_calls == 1);
		const int paid_wallet = GET_MONEY(&player);
		pc.quest_map_bought = 0;
		player.specials.affected_by |= AFF_BLIND;
		ask("map");
		assert(pc.quest_active && !pc.quest_replacement_due && !pc.quest_map_bought &&
		       GET_MONEY(&player) == paid_wallet && wallet_debits == 1);
		player.specials.affected_by &= ~AFF_BLIND;
		rooms[5].dir_option[DIR_EAST]->exit_info |= EX_LOCKED;
		ask("abandon confirm");
		assert(!pc.quest_active && !pc.quest_replacement_due &&
		       GET_MONEY(&player) == paid_wallet && history_writes == 0 &&
		       wallet_debits == 1);
		rooms[5].dir_option[DIR_EAST]->exit_info &= ~EX_LOCKED;
		pc = accepted;
		pc.quest_accomplished = 1;
		pc.quest_mob_vnum = 999999;
		pc.quest_giver = GET_VNUM(giver);
		daily_remaining = 0;
		player.player.level = 10;
		ask("quest");
		assert(reward_claims == 1 && wallet_debits == 1 && history_writes == 0);
		player.player.level = level;
		daily_remaining = 1;
		if (preferred_type == FIND_AND_KILL)
		{
			pc = accepted;
			GET_COPPER(&player) = 10000;
			ask("abandon confirm");
			assert(!pc.quest_active && GET_MONEY(&player) < 10000 &&
			       history_writes == 1);
		}
		// Recipient proof cannot overwrite an existing replacement entitlement.
		pc = accepted;
		pc.quest_receiver = GET_PID(&player);
		char_data recipient{};
		pc_only_data recipient_state{};
		recipient.only.pc = &recipient_state;
		recipient_state.pid = 88;
		recipient.player.level = level;
		recipient.player.race = RACE_HUMAN;
		recipient.player.racewar = RACEWAR_GOOD;
		SET_POS(&recipient, STAT_NORMAL | POS_STANDING);
		recipient.in_room = NOWHERE;
		move(&recipient, 0);
		recipient.next = character_list;
		character_list = &recipient;
		command_recipient = &recipient;
		share_limit = 2;
		std::string sharing = "share friend";
		recipient.specials.affected_by |= AFF_BLIND;
		history_reads.clear();
		do_quest(&player, sharing.data(), 0);
		assert(!recipient_state.quest_active && pc.quest_shares_left == 2);
		recipient.specials.affected_by &= ~AFF_BLIND;
		recipient_state.quest_replacement_due = 1;
		history_reads.clear();
		do_quest(&player, sharing.data(), 0);
		assert(recipient_state.quest_replacement_due == 1 &&
		       !recipient_state.quest_active && pc.quest_shares_left == 2);
		recipient_state.quest_replacement_due = 0;
		history_reads.clear();
		do_quest(&player, sharing.data(), 0);
		assert(recipient_state.quest_active && recipient_state.quest_origin_room == 1000 &&
		       recipient_state.quest_level == pc.quest_level &&
		       recipient_state.quest_kill_original == pc.quest_kill_original &&
		       recipient_state.quest_kill_how_many == pc.quest_kill_how_many &&
		       recipient_state.quest_map_room == 500001 &&
		       !recipient_state.quest_map_bought &&
		       !recipient_state.quest_replacement_due && pc.quest_shares_left == 1);
		share_limit = 0;
		std::cout << "accepted target checks " << level << ' ' << argv[3] << ": passed\n";
		return 0;
	}

	const bool expected = level >= 11 &&
			      (mode == "normal" || mode == "gear" || mode == "quota" ||
			       mode == "cross_zone_retry" || mode == "last_history" ||
			       mode == "last_history_zones" || mode == "last_probe" ||
			       (mode == "foreign" && level >= 30) ||
			       (mode == "mapless" && level >= 41)) &&
			      !(preferred_type == FIND_AND_ASK && level >= 50);
	pc.quest_mob_vnum = 777;
	pc.quest_kill_how_many = 2;
	pc.quest_kill_original = 4;
	pc.quest_map_bought = 1;
	pc.quest_replacement_due = 1;
	std::vector<unsigned char> before(sizeof(pc));
	std::memcpy(before.data(), &pc, sizeof(pc));
	quest_creation_failure failure = QUEST_CREATION_NO_FAILURE;
	const bool created = createQuestForGiverVnum(&player, 9000, 1000, &failure);
	assert(created == expected);
	assert(player.in_room == 0 && probe_reads == boot_probes && object_reads == boot_objects);
	assert(history_reads.size() <= WORLD_QUEST_MAX_HISTORY_CHECKS);
	if (budget_case)
		assert(history_reads.size() == WORLD_QUEST_MAX_HISTORY_CHECKS);
	if (created)
	{
		assert(failure == QUEST_CREATION_NO_FAILURE && pc.quest_active == 1);
		assert(pc.quest_zone_number == 20 && pc.quest_origin_room == 1000);
		assert(pc.quest_type == preferred_type);
		const int expected_vnum = mode == "last_history" || mode == "last_history_zones" ||
							  mode == "last_probe" ?
						  1033 :
					  preferred_type == FIND_AND_ASK ? 1003 :
									   1002;
		assert(pc.quest_mob_vnum == expected_vnum);
		assert(pc.quest_kill_original == (preferred_type == FIND_AND_ASK ? 0 :
						  mode == "quota"		 ? 3 :
										   1));
		assert(pc.quest_map_room == (mode == "mapless" ? 0 :
					     mode == "foreign" ? 500002 :
								 500001));
		assert(pc.quest_map_bought == 0 && pc.quest_replacement_due == 0 &&
		       dirty_marks == 1);
		if (mode == "cross_zone_retry")
			assert((history_reads == std::vector<int>{ 1002 }));
	}
	else
	{
		assert(failure != QUEST_CREATION_NO_FAILURE && dirty_marks == 0);
		assert(std::memcmp(before.data(), &pc, sizeof(pc)) == 0);
	}
	if (mode == "foreign" && level == 29)
	{
		player.player.level = 30;
		history_reads.clear();
		world_quest_target accepted_target;
		assert(world_quest_policy_select_target(&player, 1000, 29, accepted_target) ==
		       QUEST_CREATION_NO_ELIGIBLE_TARGET);
		assert(player.player.level == 30);
		player.player.level = 29;
	}
	// Repeat through the actual payment continuation. The wallet debit has
	// already committed when this callback runs; unsuccessful selection must
	// return exactly its fee without consuming progress/history.
	resetQuest(&player);
	dirty_marks = 0;
	history_reads.clear();
	feedback.clear();
	GET_COPPER(&player) = 500;
	move(&player, 2); // Customer moved after the request origin was captured.
	run_payment(&player, 1000, 100, true);
	assert(player.in_room == 2);
	move(&player, 0);
	assert((pc.quest_active == 1) == expected);
	assert(GET_MONEY(&player) == (expected ? 500 : 600));
	assert(probe_reads == boot_probes && object_reads == boot_objects);
	assert(history_reads.size() <= WORLD_QUEST_MAX_HISTORY_CHECKS);
	if (budget_case)
		assert(history_reads.size() == WORLD_QUEST_MAX_HISTORY_CHECKS);
	if (!expected && level >= 11 && level <= 29)
	{
		assert(feedback.find("local task") != std::string::npos);
		assert(feedback.find("colleagues around the world") == std::string::npos);
		assert(feedback.find("\\r") == std::string::npos);
	}
	if (expected)
	{
		const int verified_map = pc.quest_map_room;
		GET_COPPER(&player) -= 10;
		run_map_payment(&player, 10);
		assert(pc.quest_map_room == verified_map);
		if (verified_map)
		{
			assert(pc.quest_map_bought == 1 && GET_MONEY(&player) == 490);
			assert(map_calls == 1 && world[shown_map].number == verified_map);
		}
		else
			assert(pc.quest_map_bought == 0 && GET_MONEY(&player) == 500 &&
			       map_calls == 0);
	}
	if (mode == "normal" && expected)
	{
		// The shared selector uses the accepted level without modifying the
		// player's current level. This is the recovery consumer's boundary.
		if (level == 11)
		{
			player.player.level = 30;
			history_reads.clear();
			world_quest_target target;
			assert(world_quest_policy_select_target(&player, 1000, 11, target) ==
			       QUEST_CREATION_NO_FAILURE);
			assert(player.player.level == 30 && target.mob_vnum == pc.quest_mob_vnum);
			player.player.level = 11;
		}
		resetQuest(&player);
		history_reads.clear();
		dirty_marks = 0;
		auto giver = spawn(2, 0, 0);
		assert(createQuest(&player, giver, &failure) && pc.quest_origin_room == 1000);
		std::memcpy(before.data(), &pc, sizeof(pc));
		move(giver, 3);
		assert(!createQuest(&player, giver, &failure) &&
		       failure == QUEST_CREATION_INVALID_ACTOR);
		assert(std::memcmp(before.data(), &pc, sizeof(pc)) == 0);
	}
	resetQuest(&player);
	history_reads.clear();
	dirty_marks = 0;
	GET_COPPER(&player) = 500;
	run_payment(&player, 999999, 100, true);
	assert(!pc.quest_active && !pc.quest_origin_room && GET_MONEY(&player) == 600);
	assert(history_reads.empty() && dirty_marks == 0);
	GET_COPPER(&player) = 600;
	run_payment(&player, 1000, 100, false);
	assert(!pc.quest_active && GET_MONEY(&player) == 600 && history_reads.empty());
	std::cout << "live quest " << level << ' ' << mode << ' ' << argv[3] << ": passed\n";
}
