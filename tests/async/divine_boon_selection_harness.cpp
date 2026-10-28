#include "economy/divine_boon_selection.h"
#include "economy/divine_boon_runtime.h"
#include "combat/justice.h"
#include "core/prototypes.h"
#include "world/db.h"
#include "sql/sql.h"
#include "world/epic.h"
#include "ships/ships.h"
#include "world/graph.h"

#include <cassert>
#include <chrono>
#include <cstdarg>
#include <cstdio>
#include <string>
#include <iostream>

namespace
{
room_data rooms[11] = {};
zone_data zones[5] = {};
room_direction_data exits[11] = {};
reset_com low_resets[7] = {};
reset_com high_resets[7] = {};
int levels[] = { 16, 18, 38, 42 };
int random_value = 0;
divine_boon_state authority, queued;
std::array<divine_boon_population, 2> current_population = {};
bool queue_accepts = false, write_pending = false;
unsigned random_calls = 0, queue_calls = 0;
}
P_room world = rooms;
zone_data *zone_table = zones;
int top_of_world = 10;
int top_of_zone_table = 4;
hometown_data hometowns[LAST_HOME] = {};
extern const int guild_locations[LAST_HOME + 1][CLASS_COUNT + 1] = { {}, { 132500 }, { 36329 } };

std::vector<zone_info> epic_metadata;
index_data stone_index[1] = {};
P_index obj_index = nullptr;
P_obj object_list = nullptr;
int stone_zone = 2;
unsigned stone_location_lookups = 0;
int obj_zone_id(P_obj obj)
{
	++stone_location_lookups;
	return obj->value[2] == 20 ? 3 : stone_zone;
}
int top_of_objt = -1;
const std::vector<zone_info> &sql_zones()
{
	return epic_metadata;
}
bool get_zone_info(int number, zone_info *info)
{
	for (const auto &entry : epic_metadata)
		if (entry.number == number)
		{
			*info = entry;
			return true;
		}
	return false;
}
bool epic_zone_done_now(int)
{
	return false;
}
int epic_stone(P_obj, P_char, int, char *)
{
	return false;
}

int real_room(const int number)
{
	for (int i = 0; i <= top_of_world; ++i)
		if (world[i].number == number)
			return i;
	return -1;
}
int real_zone0(const int number)
{
	for (int i = 0; i <= top_of_zone_table; ++i)
		if (zone_table[i].number == number)
			return i;
	return -1;
}
int world_quest_policy_combat_level(int mob)
{
	return mob >= 0 && mob < 4 ? levels[mob] : -1;
}
bool world_quest_policy_zone_is_invalid(int zone)
{
	return zone == 999; // Explicitly denied content, even if it looks like a valid dungeon.
}
int number(int low, int high)
{
	++random_calls;
	return random_value ? std::min(random_value, high) : low;
}
int inn(int, P_char, int, char *)
{
	return false;
}
int unsafe_room(int, P_char, int, char *)
{
	return false;
}
void logit(const char *, const char *, ...) {}
std::string diagnostic_output;
void send_to_char_f(P_char, const char *format, ...)
{
	char line[512];
	va_list args;
	va_start(args, format);
	vsnprintf(line, sizeof(line), format, args);
	va_end(args);
	diagnostic_output += line;
}

const divine_boon_state *divine_boon_runtime_state()
{
	return &authority;
}
bool divine_boon_runtime_pending()
{
	return write_pending;
}
bool divine_boon_runtime_queue(const divine_boon_state &next)
{
	++queue_calls;
	queued = next;
	write_pending = queue_accepts;
	return queue_accepts;
}
std::array<divine_boon_population, 2> divine_boon_activity_population()
{
	return current_population;
}

const PortData ports[NUM_PORTS] = { { 103, "Source", 108 }, { 104, "Destination", 109 } };
bool water_connected = true;
int water_searches = 0;
bool valid_ship_edge(int, int)
{
	return true;
}
bool dijkstra(int from, int to, valid_edge_func *edge, std::vector<int> &path)
{
	assert(((from == 8 && to == 9) || (from == 9 && to == 8)) && edge == valid_ship_edge);
	++water_searches;
	path = { 5 };
	return water_connected;
}

int ship_shop_proc(int, P_char, int, char *)
{
	return false;
}
int cargo_sell_price(int, bool)
{
	return 100;
}
int contra_sell_price(int)
{
	return 100;
}
int cargo_buy_price(int, int, bool)
{
	return 120;
}
int contra_buy_price(int, int)
{
	return 120;
}

int main()
{
	for (int room = 0; room <= top_of_world; ++room)
	{
		rooms[room].number = 100 + room;
		rooms[room].zone = room < 2 ? room : room < 5 ? 2 : room < 8 ? 3 : 4;
	}
	rooms[0].number = 132500;
	rooms[1].number = 36329;
	zones[0].number = 1325;
	zones[1].number = 363;
	zones[0].flags = zones[1].flags = ZONE_TOWN;
	zones[0].hometown = 1;
	zones[1].hometown = 2;
	hometowns[0].flags = JUSTICE_GOODHOME;
	hometowns[1].flags = JUSTICE_EVILHOME;
	zones[2].number = 18;
	zones[3].number = 20;
	zones[4].number = 999; // Denied by the world-quest zone vetting.
	for (auto &zone : zones)
		zone.reset_mode = 2;
	for (int i = 0; i < 5; ++i)
	{
		low_resets[i] = { 'M', false, i % 2, 5, 2 + i % 3, 100 };
		high_resets[i] = { 'M', false, 2 + i % 2, 5, 5 + i % 3, 100 };
	}
	low_resets[5].command = high_resets[5].command = high_resets[6].command = 'S';
	zones[2].cmd = low_resets;
	zones[3].cmd = high_resets;
	zones[4].cmd = high_resets;
	const int from[] = { 0, 1, 2, 3, 0, 5, 6, 0, 8, 9, 1 };
	const int to[] = { 2, 2, 3, 4, 5, 6, 7, 8, 9, 10, 5 };
	for (int i = 0; i < 11; ++i)
	{
		exits[i].to_room = to[i];
		const int direction = (i == 4 || i == 10) ? 1 : i == 7 ? 2 : 0;
		rooms[from[i]].dir_option[direction] = &exits[i];
	}
	assert(divine_boon_selection_bootstrap());
	assert(divine_boon_zone_eligible(18, 0) && divine_boon_zone_eligible(18, 1));
	assert(divine_boon_zone_eligible(20, 0));
	rooms[0].funct = inn; // The real hometown spawn can be an ordinary inn.
	assert(divine_boon_zone_eligible(18, 0));
	rooms[0].funct = nullptr;
	assert(!divine_boon_zone_eligible(999, 0));
	assert(!divine_boon_zone_eligible(18, 2));
	rooms[0].funct = inn; // Tharn's ordinary spawn uses the movement-safe inn.
	assert(divine_boon_selection_bootstrap());
	assert(divine_boon_zone_eligible(18, 0));
	rooms[0].funct = unsafe_room;
	assert(!divine_boon_zone_eligible(18, 0));
	rooms[0].funct = nullptr;
	assert(divine_boon_selection_bootstrap());
	for (int flag : { ZONE_TOWN, ZONE_SAFE, ZONE_MAP, ZONE_CLOSED, ZONE_PRIVATE })
	{
		zones[2].flags = flag;
		assert(!divine_boon_zone_eligible(18, 0)); // Town with hometown index zero.
	}
	zones[2].flags = 0;
	zones[2].hometown = 1;
	assert(!divine_boon_zone_eligible(18, 0));
	zones[2].hometown = 0;
	zones[2].reset_mode = 0;
	assert(!divine_boon_zone_eligible(18, 0));
	zones[2].reset_mode = 2;
	for (ulong flag : { ROOM_LOCKER, ROOM_PRIVATE, ROOM_ARENA, ROOM_GUILD, ROOM_JAIL,
			    ROOM_ATRIUM, ROOM_SAFE, ROOM_NO_MOB })
	{
		rooms[3].room_flags = flag;
		assert(!divine_boon_zone_eligible(18, 0));
	}
	rooms[3].room_flags = 0;
	for (int flag : { EX_SECRET, EX_LOCKED, EX_BLOCKED, EX_WALLED })
	{
		exits[0].exit_info = flag;
		assert(!divine_boon_zone_eligible(18, 0));
		assert(divine_boon_zone_eligible(18, 1));
		divine_boon_slot legacy_target;
		legacy_target.category = divine_boon_category::experience;
		legacy_target.zones = { 18, 20 };
		assert(divine_boon_zone_eligible(20, 0) &&
		       divine_boon_zone_eligible(20, 1));
		assert(divine_boon_shared_target_zone(legacy_target) == 20);
	}
	exits[0].exit_info = EX_CLOSED; // An ordinary door can be opened.
	assert(divine_boon_zone_eligible(18, 0));
	divine_boon_slot old;
	old.category = divine_boon_category::experience;
	old.zones = { 18, 20 };
	assert(divine_boon_shared_target_zone(old) == 18);
	old.zones = { 999, 18 };
	assert(divine_boon_shared_target_zone(old) == 18);
	exits[0].exit_info = 0;
	for (int sector : { SECT_OCEAN, SECT_NO_GROUND, SECT_UNDERWATER, SECT_FIREPLANE })
	{
		rooms[3].sector_type = sector;
		assert(!divine_boon_zone_eligible(18, 0));
	}
	rooms[3].sector_type = SECT_FIELD;
	rooms[0].room_flags = ROOM_SAFE; // A safe hometown may lead to normal encounters.
	assert(divine_boon_zone_eligible(18, 0));


	// Experience objectives are one globally shared zone, even if only one
	// racewar side is online or the sides play at very different levels.
	divine_boon_state state;
	assert(divine_boon_set_mode(&state, divine_boon_mode::draining, 0));
	assert(divine_boon_set_mode(&state, divine_boon_mode::divine, 0));
	std::array<divine_boon_population, 2> population = {};
	population[0].levels = { 17 };
	population[1].levels = { 40 };
	std::vector<divine_boon_slot> picks;
	assert(divine_boon_select(state, 3600, population, &picks));
	assert(picks.size() == 1);
	assert(picks[0].category == divine_boon_category::experience);
	assert(picks[0].zones[0] == 18 && picks[0].zones[1] == 18);
	assert(divine_boon_rotate(&state, 3600, picks.data(), picks.size()));
	assert(divine_boon_target_zone(state.slots[0]) == 18);

	// A legacy persisted two-target objective is normalized for live display
	// and awards without rewriting its snapshot, ID or expiry timestamp.
	divine_boon_state legacy;
	assert(divine_boon_set_mode(&legacy, divine_boon_mode::draining, 0));
	assert(divine_boon_set_mode(&legacy, divine_boon_mode::divine, 0));
	divine_boon_slot old;
	old.category = divine_boon_category::experience;
	old.zones = { 18, 20 };
	assert(divine_boon_rotate(&legacy, 3600, &old));
	assert(divine_boon_target_zone(legacy.slots[0]) == 18);
	std::vector<uint8_t> bytes;
	assert(divine_boon_state_encode(legacy, &bytes));
	divine_boon_state recovered;
	assert(divine_boon_state_decode(bytes, &recovered) && recovered == legacy);

	// A closed Good approach must never make a newly selected hotspot
	// faction-specific, even though older saved boons remain shared.
	exits[0].exit_info = EX_BLOCKED;
	assert(divine_boon_zone_eligible(18, 1));
	assert(!divine_boon_zone_eligible(18, 0));
	divine_boon_state fresh;
	assert(divine_boon_set_mode(&fresh, divine_boon_mode::draining, 0));
	assert(divine_boon_set_mode(&fresh, divine_boon_mode::divine, 0));
	divine_boon_select(fresh, 3600, population, &picks);
	for (const auto &choice : picks)
		if (choice.category == divine_boon_category::experience)
			assert(choice.zones[0] == choice.zones[1] &&
			       choice.zones[0] != 18);
	exits[0].exit_info = 0;
	population[0] = {};
	population[1].levels = { 40 };
	assert(divine_boon_select(fresh, 3600, population, &picks));
	assert(picks[0].category == divine_boon_category::experience);
	assert(picks[0].zones[0] == 20 && picks[0].zones[1] == 20);

	// A real payable, reachable Epic stone is mandatory: metadata alone is
	// insufficient. The same zone must work from both hometowns.
	zone_info metadata = {};
	metadata.number = 18;
	metadata.epic_payout = 100;
	metadata.suggested_group_size = 100;
	metadata.stonecount = 1;
	metadata.epic_type = EPIC_ZONE_TYPE_SMALL;
	epic_metadata.push_back(metadata);
	obj_index = stone_index;
	top_of_objt = 0;
	stone_index[0].func.obj = epic_stone;
	stone_index[0].virtual_number = EPIC_SMALL_STONE;
	low_resets[5] = { 'O', false, 0, 1, 3, 100 };
	low_resets[6].command = 'S';
	assert(divine_boon_selection_bootstrap());
	assert(!divine_boon_epic_zone_eligible(18, 0));
	obj_data stone = {};
	stone.R_num = 0;
	stone.obj_uid = 123;
	stone.extra2_flags = ITEM2_MAGIC;
	stone.value[0] = stone.value[1] = 100;
	stone.value[2] = 18;
	object_list = &stone;
	assert(divine_boon_epic_zone_eligible(18, 0));
	assert(divine_boon_epic_zone_eligible(18, 1));
	stone.extra2_flags = 0;
	assert(!divine_boon_epic_zone_eligible(18, 0));
	stone.extra2_flags = ITEM2_MAGIC;
	stone_zone = 3;
	assert(!divine_boon_epic_zone_eligible(18, 1));
	stone_zone = 2;

	// One Epic objective is allowed on a quiet server, not three idle ones.
	std::array<divine_boon_population, 2> quiet_players = {};
	assert(divine_boon_select(fresh, 3600, quiet_players, &picks));
	assert(picks.size() == 1 && picks[0].category == divine_boon_category::epic);
	assert(picks[0].zones == (std::array<int32_t, 2>{ 18, 18 }));
	assert(divine_boon_rotate(&fresh, 3600, picks.data(), picks.size()));
	assert(!divine_boon_select(fresh, 7200, quiet_players, &picks));

	// Two eligible Epic zones can coexist with one new Experience objective
	// in a single hour, but the same zone is never picked for both rewards.
	metadata.number = 20;
	metadata.epic_payout = 900;
	epic_metadata.push_back(metadata);
	high_resets[5] = { 'O', false, 0, 1, 6, 100 };
	high_resets[6].command = 'S';
	obj_data high_stone = stone;
	high_stone.obj_uid = 124;
	high_stone.value[2] = 20;
	stone.next = &high_stone;
	assert(divine_boon_selection_bootstrap());
	std::array<divine_boon_population, 2> online = {};
	online[0].levels = { 17 };
	assert(divine_boon_select(fresh, 7200, online, &picks));
	// Zone 18 is already occupied by the waiting Epic objective, so the
	// next Epic may use the other zone. Any new selected objectives still have shared IDs.
	for (const auto &choice : picks)
		assert(choice.zones[0] == choice.zones[1]);

	// Protect the stone-index lookup cost when the world contains many objects:
	// the two sides must reuse the same live-stone inventory snapshot.
	{
		std::vector<obj_data> ordinary(38935);
		for (size_t index = 0; index < ordinary.size(); ++index)
		{
			ordinary[index].R_num = -1;
			ordinary[index].next = index + 1 < ordinary.size() ?
							 &ordinary[index + 1] : &stone;
		}
		object_list = ordinary.data();
		const auto started = std::chrono::steady_clock::now();
		for (int run = 0; run < 20; ++run)
		{
			stone_location_lookups = 0;
			assert(divine_boon_select(fresh, 7200, online, &picks));
			assert(stone_location_lookups == 2);
		}
		const auto elapsed = std::chrono::duration<double, std::micro>(
			std::chrono::steady_clock::now() - started);
		std::cout << "38937 objects, two shared Epic zones: selection mean_us="
			  << elapsed.count() / 20 << std::endl;
		object_list = &stone;
	}

	// Rotation enforces dedicated capacities even if callers supply more than
	// one candidate per type. No saved-state format migration is required.
	divine_boon_state full;
	assert(divine_boon_set_mode(&full, divine_boon_mode::draining, 0));
	assert(divine_boon_set_mode(&full, divine_boon_mode::divine, 0));
	for (int index = 0; index < 3; ++index)
	{
		divine_boon_slot exp;
		exp.category = divine_boon_category::experience;
		exp.zones = { 100 + index, 100 + index };
		assert(divine_boon_rotate(&full, (index + 1) * 3600, &exp));
	}
	for (int index = 0; index < 3; ++index)
	{
		divine_boon_slot epic;
		epic.category = divine_boon_category::epic;
		epic.zones = { 200 + index, 200 + index };
		assert(divine_boon_rotate(&full, (index + 4) * 3600, &epic));
	}
	divine_boon_slot overflow[2];
	overflow[0].category = divine_boon_category::experience;
	overflow[0].zones = { 888, 888 };
	overflow[1].category = divine_boon_category::epic;
	overflow[1].zones = { 889, 889 };
	const auto capped = full;
	assert(!divine_boon_rotate(&full, 7 * 3600, overflow, 2));
	assert(full == capped);
	assert(std::count_if(full.slots.begin(), full.slots.end(), [](const auto &slot)
				    { return slot.category == divine_boon_category::experience; }) == 3);
	assert(std::count_if(full.slots.begin(), full.slots.end(), [](const auto &slot)
				    { return slot.category == divine_boon_category::epic; }) == 3);
	bytes.clear();
	assert(divine_boon_state_encode(full, &bytes));
	assert(divine_boon_state_decode(bytes, &recovered) && recovered == full);

	// PvP remains conditioned on distinct opposing active accounts.
	std::array<divine_boon_population, 2> opposing = {};
	opposing[0].pvp_accounts = 1;
	assert(!divine_boon_select(full, 7 * 3600, opposing, &picks));
	opposing[1].pvp_accounts = 1;
	assert(divine_boon_select(full, 7 * 3600, opposing, &picks));
	assert(picks.size() == 1 && picks[0].category == divine_boon_category::pvp);
	assert(divine_boon_rotate(&full, 8 * 3600, picks.data(), picks.size()));
	assert(!divine_boon_select(full, 8 * 3600, opposing, &picks));

	// Cargo remains independent of player activity and requires a real
	// profitable, navigable route with suitable port shops.
	divine_boon_slot route;
	route.category = divine_boon_category::cargo;
	route.source_port = route.cargo_commodity = route.contraband_commodity = 0;
	route.destination_port = 1;
	rooms[3].funct = rooms[4].funct = ship_shop_proc;
	rooms[3].room_flags = rooms[4].room_flags = 0;
	rooms[3].sector_type = rooms[4].sector_type = SECT_FIELD;
	room_direction_data water_exits[2] = {};
	water_exits[0].to_room = 9;
	water_exits[1].to_room = 8;
	rooms[8].dir_option[5] = &water_exits[0];
	rooms[9].dir_option[5] = &water_exits[1];
	rooms[8].sector_type = rooms[9].sector_type = SECT_OCEAN;
	assert(divine_boon_selection_bootstrap());
	assert(divine_boon_cargo_eligible(route));
	const int water_before = water_searches;
	for (int i = 0; i < 100; ++i)
		assert(divine_boon_cargo_eligible(route));
	assert(water_searches == water_before); // A cached navigation proof.
	water_exits[0].exit_info = EX_CLOSED | EX_LOCKED;
	assert(!divine_boon_cargo_eligible(route));
	water_exits[0].exit_info = 0;
	water_connected = false;
	assert(divine_boon_selection_bootstrap());
	assert(!divine_boon_cargo_eligible(route));
	water_connected = true;
	assert(divine_boon_selection_bootstrap());
	route.destination_port = 0;
	assert(!divine_boon_cargo_eligible(route));
	route.destination_port = 1;
	route.cargo_commodity = 1;
	assert(!divine_boon_cargo_eligible(route));
	route.cargo_commodity = 0;
	rooms[4].funct = nullptr;
	assert(!divine_boon_cargo_eligible(route));
	rooms[4].funct = ship_shop_proc;
	zones[2].flags = ZONE_CLOSED;
	assert(!divine_boon_cargo_eligible(route));
	zones[2].flags = 0;
	assert(divine_boon_selection_bootstrap());
	assert(divine_boon_select(full, 8 * 3600, quiet_players, &picks));
	assert(picks.size() == 1 && picks[0].category == divine_boon_category::cargo);
	assert(divine_boon_rotate(&full, 9 * 3600, picks.data(), picks.size()));
	assert(std::count_if(full.slots.begin(), full.slots.end(), [](const auto &slot)
				    { return slot.category == divine_boon_category::cargo; }) == 1);

	// Real game-thread tick must preserve the original prepared choice while
	// a writer is refusing admission, then publish exactly once.
	assert(divine_boon_set_mode(&authority, divine_boon_mode::draining, 0));
	assert(divine_boon_set_mode(&authority, divine_boon_mode::divine, 0));
	current_population = {};
	current_population[0].levels = { 17 };
	queue_calls = random_calls = 0;
	queue_accepts = write_pending = false;
	divine_boon_selection_pulse(3599);
	assert(queue_calls == 0 && random_calls == 0);
	divine_boon_selection_pulse(3600);
	assert(queue_calls == 1 && !authority.slots[0].id);
	const auto chosen = queued;
	const auto random_before = random_calls;
	divine_boon_selection_pulse(3601);
	assert(queue_calls == 2 && random_calls == random_before && queued == chosen);
	queue_accepts = true;
	divine_boon_selection_pulse(3602);
	assert(write_pending && queue_calls == 3 && queued == chosen);
	authority = queued;
	write_pending = false;
	divine_boon_selection_pulse(3603);
	assert(queue_calls == 3);
	int exp_zone = -1;
	for (const auto &slot : authority.slots)
		if (slot.category == divine_boon_category::experience)
			exp_zone = divine_boon_target_zone(slot);
	assert(exp_zone >= 0);
	assert(divine_boon_reward_zone_eligible(exp_zone, 0));
	assert(divine_boon_reward_zone_eligible(exp_zone, 1));
	for (int index = 0; index < 10000; ++index)
		assert(divine_boon_reward_zone_eligible(exp_zone, 1));
	// The cached award remains shared when only one side's route closes.
	exits[0].exit_info = EX_BLOCKED;
	divine_boon_selection_pulse(3604);
	assert(divine_boon_reward_zone_eligible(exp_zone, 0) ==
	       divine_boon_reward_zone_eligible(exp_zone, 1));
	exits[0].exit_info = 0;

	// A refused hour is not replayed after the wall clock advances.
	queue_accepts = false;
	divine_boon_selection_pulse(7200);
	const unsigned prior_rng = random_calls;
	divine_boon_selection_pulse(10800); // 7200 remained refused.
	assert(random_calls == prior_rng && queued.last_opportunity == 10800);
	queue_accepts = true;
	divine_boon_selection_pulse(10801);
	assert(write_pending);
	authority = queued;
	write_pending = false;
	// A paused hour does not invent an alternative objective.
	assert(divine_boon_set_paused(&authority, true, 10801));
	divine_boon_selection_pulse(14400);
	assert(write_pending);
	authority = queued;
	write_pending = false;

	char_data staff = {};
	staff.player.level = IMMORTAL;
	diagnostic_output.clear();
	divine_boon_selection_status(&staff);
	assert(diagnostic_output.find("divine_diag") != std::string::npos);
	std::cout << "Divine selection: shared zones, 3+3 reserved pools, unchanged cargo/PvP gating, durable rotation and cached rewards passed\n";
}
