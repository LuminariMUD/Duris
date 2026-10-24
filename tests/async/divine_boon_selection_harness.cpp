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
reset_com high_resets[6] = {};
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
int obj_zone_id(P_obj)
{
	return stone_zone;
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
	zones[4].number = 999; // Unknown content, even if it looks like a valid dungeon.
	for (auto &zone : zones)
		zone.reset_mode = 2;
	for (int i = 0; i < 5; ++i)
	{
		low_resets[i] = { 'M', false, i % 2, 5, 2 + i % 3, 100 };
		high_resets[i] = { 'M', false, 2 + i % 2, 5, 5 + i % 3, 100 };
	}
	low_resets[5].command = high_resets[5].command = 'S';
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
	}
	exits[0].exit_info = EX_CLOSED; // An ordinary door can be opened.
	assert(divine_boon_zone_eligible(18, 0));
	exits[0].exit_info = 0;
	for (int sector : { SECT_OCEAN, SECT_NO_GROUND, SECT_UNDERWATER, SECT_FIREPLANE })
	{
		rooms[3].sector_type = sector;
		assert(!divine_boon_zone_eligible(18, 0));
	}
	rooms[3].sector_type = SECT_FIELD;
	rooms[0].room_flags = ROOM_SAFE; // A safe hometown may lead to normal encounters.
	assert(divine_boon_zone_eligible(18, 0));

	divine_boon_state state;
	assert(divine_boon_set_mode(&state, divine_boon_mode::draining, 0));
	assert(divine_boon_set_mode(&state, divine_boon_mode::divine, 0));
	std::array<divine_boon_population, 2> population = {};
	population[0].active_accounts = population[0].brackets[0] = 1;
	population[1].active_accounts = population[1].brackets[2] = 1;
	divine_boon_slot choice;
	assert(divine_boon_select(state, 3600, population, &choice));
	assert(choice.category == divine_boon_category::experience);
	assert(choice.zones[0] == 18 && choice.zones[1] == 20);
	assert(divine_boon_rotate(&state, 3600, &choice));
	assert(!divine_boon_select(state, 7200, population, &choice)); // No same-side reuse.

	assert(divine_boon_replace(&state, 0, 7200));
	assert(divine_boon_select(state, 10800, population, &choice)); // Thin pool relaxes history.
	assert(choice.zones[0] == 18 && choice.zones[1] == 20);
	population[1] = {};
	assert(divine_boon_select(state, 10800, population, &choice));
	assert(choice.zones[0] == 18 && choice.zones[1] == -1);
	levels[2] = levels[3] = 18;
	assert(divine_boon_selection_bootstrap());
	assert(divine_boon_select(state, 10800, population, &choice));
	assert(choice.zones[0] ==
	       20); // Prefer an unvisited safe alternative before relaxing history.
	levels[2] = 38;
	levels[3] = 42;
	assert(divine_boon_selection_bootstrap());
	population[0] = {};
	assert(!divine_boon_select(state, 10800, population, &choice));
	state.paused = true;
	assert(!divine_boon_select(state, 10800, population, &choice));
	state.paused = false;
	population[0].active_accounts = population[0].brackets[0] = 1;
	{
		divine_boon_state pending;
		assert(divine_boon_set_mode(&pending, divine_boon_mode::draining, 0));
		assert(divine_boon_set_mode(&pending, divine_boon_mode::divine, 0));
		divine_boon_slot active;
		active.category = divine_boon_category::experience;
		active.zones = { 20, -1 };
		assert(divine_boon_rotate(&pending, 3600, &active));
		reset_com alternative[6] = {};
		for (int i = 0; i < 5; ++i)
			alternative[i] = { 'M', false, 2 + i % 2, 5, 8 + i % 3, 100 };
		alternative[5].command = 'S';
		zones[4].number = 40;
		zones[4].cmd = alternative;
		zones[3].flags = ZONE_CLOSED;
		assert(divine_boon_selection_bootstrap());
		auto balanced = population;
		balanced[0].brackets[2] = 1;
		random_value = 600000;
		assert(divine_boon_select(pending, 7200, balanced, &choice));
		assert(choice.zones[0] == 18); // Invalid high objective must not serve bracket 0.
		random_value = 0;
		zones[4].number = 999;
		zones[4].cmd = high_resets;
		zones[3].flags = 0;
		levels[2] = levels[3] = 18;
		assert(divine_boon_selection_bootstrap());
		assert(divine_boon_select(pending, 9 * 3600, population, &choice));
		assert(choice.zones[0] == 18); // Expired zone 20 awaits core reconciliation.
		levels[2] = 38;
		levels[3] = 42;
		assert(divine_boon_selection_bootstrap());
	}
	{
		for (int i = 0; i < 5; ++i)
			low_resets[i].arg1 = 0;
		low_resets[5] = {
			'M', false, 1, 5, 8, 100
		}; // Other prototype moved outside the zone.
		low_resets[6].command = 'S';
		assert(divine_boon_selection_bootstrap());
		assert(!divine_boon_zone_eligible(18, 0));
		low_resets[5].arg3 = 4;
		assert(divine_boon_selection_bootstrap());
		assert(divine_boon_zone_eligible(18, 0));
		for (int i = 0; i < 5; ++i)
			low_resets[i].arg1 = i % 2;
		low_resets[5].command = 'S';
	}
	low_resets[0].arg1 = 99; // Unknown profiles fail closed on catalogue rebuild.
	assert(divine_boon_selection_bootstrap());
	assert(!divine_boon_select(state, 10800, population, &choice));

	// Exercise the actual game-thread tick at the existing writer boundary.
	std::array<divine_boon_population, 2> opposing = {};
	opposing[0].active_accounts = opposing[1].active_accounts = 1;
	opposing[0].brackets[0] = opposing[1].brackets[0] = 1;
	opposing[0].pvp_accounts = 1;
	assert(!divine_boon_select(state, 10800, opposing, &choice));
	opposing[1].pvp_accounts = 1;
	assert(divine_boon_select(state, 10800, opposing, &choice) &&
	       choice.category == divine_boon_category::pvp);
	auto pvp_state = state;
	assert(divine_boon_rotate(&pvp_state, 10800, &choice));
	assert(!divine_boon_select(pvp_state, 14400, opposing, &choice)); // One global PvP slot.

	// Publication itself remains the real writer runtime's separate proof.
	low_resets[0].arg1 = 0;
	auto reset_hour = [&]
	{
		assert(divine_boon_selection_bootstrap());
		authority = {};
		assert(divine_boon_set_mode(&authority, divine_boon_mode::draining, 0));
		assert(divine_boon_set_mode(&authority, divine_boon_mode::divine, 0));
		current_population = {};
		current_population[0].active_accounts = current_population[0].brackets[0] = 1;
		queue_calls = random_calls = 0;
		queue_accepts = write_pending = false;
	};
	auto publish = [&]
	{
		assert(write_pending);
		authority = queued;
		write_pending = false;
	};
	reset_hour();
	divine_boon_selection_pulse(3599);
	assert(queue_calls == 0 && random_calls == 0);
	divine_boon_selection_pulse(3600);
	assert(queue_calls == 1 && queued.slots[0].id == 1 && !authority.slots[0].id);
	const auto first_choice = queued;
	const auto choices = random_calls;
	divine_boon_selection_pulse(3601);
	assert(queue_calls == 2 && random_calls == choices && queued == first_choice);
	queue_accepts = true;
	divine_boon_selection_pulse(3602);
	assert(queue_calls == 3 && write_pending && !authority.slots[0].id);
	divine_boon_selection_pulse(3603);
	assert(queue_calls == 3);
	publish();
	divine_boon_selection_pulse(3604);
	assert(queue_calls == 3);
	assert(divine_boon_reward_zone_eligible(18, 0));
	exits[0].exit_info = EX_BLOCKED;
	for (unsigned hit = 0; hit < 10000; ++hit)
		assert(divine_boon_reward_zone_eligible(18, 0)); // A bounded cached lookup.
	divine_boon_selection_pulse(3605);
	assert(!divine_boon_reward_zone_eligible(18, 0));
	exits[0].exit_info = 0;
	divine_boon_selection_pulse(3606);
	assert(divine_boon_reward_zone_eligible(18, 0));
	assert(!divine_boon_reward_zone_eligible(18, 2));
	divine_boon_selection_pulse(10800); // Forward jump skips opportunities without RNG.
	assert(random_calls == choices && queued.last_opportunity == 10800);
	publish();
	divine_boon_selection_pulse(32400);
	assert(random_calls == choices && !queued.slots[0].id);
	assert(queued.history.size() == 1 && queued.history[0].zone == 18);
	publish();

	reset_hour();
	divine_boon_selection_pulse(3600);
	const auto before_skip = random_calls;
	divine_boon_selection_pulse(7200); // Queue refused until the choice's hour passed.
	assert(random_calls == before_skip && queued.last_opportunity == 7200 &&
	       !queued.slots[0].id);
	queue_accepts = true;
	divine_boon_selection_pulse(7201);
	publish();
	assert(divine_boon_set_paused(&authority, true, 7201));
	divine_boon_selection_pulse(10800);
	assert(random_calls == before_skip && !queued.slots[0].id);
	publish();

	reset_hour();
	divine_boon_selection_pulse(3600);
	zones[2].flags = ZONE_TOWN; // Changed after selection, before writer admission.
	const auto before_invalid = random_calls;
	divine_boon_selection_pulse(3601);
	assert(random_calls == before_invalid && !queued.slots[0].id);
	zones[2].flags = 0;
	// A cached metadata row alone cannot advertise an epic. Require the real
	// functional, payable stone at its reset location and an ordinary side path.
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
	rooms[3].contents = &stone;
	object_list = &stone;
	// The live stone remains eligible after looting its defeated carrier.
	rooms[3].contents = nullptr;
	assert(divine_boon_epic_zone_eligible(18, 0));
	stone_zone = 3;
	assert(!divine_boon_epic_zone_eligible(18, 0));
	stone_zone = 2;
	assert(divine_boon_epic_zone_eligible(18, 0));
	stone.extra2_flags = 0;
	assert(!divine_boon_epic_zone_eligible(18, 0));
	stone.extra2_flags = ITEM2_MAGIC;
	epic_metadata[0].epic_payout = 0;
	assert(!divine_boon_epic_zone_eligible(18, 0));
	epic_metadata[0].epic_payout = 100;
	zones[2].flags = ZONE_TOWN;
	assert(!divine_boon_epic_zone_eligible(18, 0));
	zones[2].flags = 0;
	divine_boon_state epic_state;
	assert(divine_boon_set_mode(&epic_state, divine_boon_mode::draining, 0));
	assert(divine_boon_set_mode(&epic_state, divine_boon_mode::divine, 0));
	std::array<divine_boon_population, 2> epic_population = {};
	epic_population[0].active_accounts = epic_population[0].brackets[0] = 1;
	assert(divine_boon_select(epic_state, 3600, epic_population, &choice));
	assert(choice.category == divine_boon_category::experience); // Crowd requires two accounts.
	epic_population[0].active_accounts = epic_population[0].brackets[0] = 2;
	assert(divine_boon_select(epic_state, 3600, epic_population, &choice));
	assert(choice.category == divine_boon_category::epic && choice.zones[0] == 18);
	divine_boon_slot route;
	route.category = divine_boon_category::cargo;
	route.source_port = route.cargo_commodity = route.contraband_commodity = 0;
	route.destination_port = 1;
	zones[2].flags = 0;
	zones[2].hometown = 0;
	zones[2].reset_mode = 2;
	rooms[3].funct = rooms[4].funct = ship_shop_proc;
	exits[0].exit_info = exits[2].exit_info = exits[3].exit_info = 0;
	rooms[3].room_flags = rooms[4].room_flags = 0;
	rooms[3].sector_type = rooms[4].sector_type = SECT_FIELD;
	room_direction_data water_exits[2] = {};
	water_exits[0].to_room = 9;
	water_exits[1].to_room = 8;
	rooms[8].dir_option[5] = &water_exits[0];
	rooms[9].dir_option[5] = &water_exits[1];
	rooms[8].sector_type = rooms[9].sector_type = SECT_OCEAN;
	const int searches = water_searches;
	for (int i = 0; i < 100; ++i)
		assert(divine_boon_cargo_eligible(route));
	assert(water_searches == searches);
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

	// A zero-player server may generate cargo and then correctly record empty
	// hourly opportunities while cargo remains active. No RNG from staff status.
	zones[2].flags = 0; // Restore valid water-port access for the cargo-only fixture.
	reset_hour();
	current_population = {};
	divine_boon_selection_pulse(3600);
	assert(queued.slots[0].category == divine_boon_category::cargo);
	queue_accepts = true;
	divine_boon_selection_pulse(3601);
	publish();
	divine_boon_selection_pulse(3602);
	const unsigned after_grant_rng = random_calls;
	divine_boon_selection_pulse(7200);
	publish();
	divine_boon_selection_pulse(7201);
	assert(random_calls == after_grant_rng);
	char_data staff = {};
	staff.player.level = IMMORTAL;
	diagnostic_output.clear();
	divine_boon_selection_status(&staff);
	assert(diagnostic_output.find("last_hour=7200 outcome=no-eligible-category") !=
	       std::string::npos);
	assert(diagnostic_output.find("side=good active=0") != std::string::npos);
	assert(diagnostic_output.find("side=evil active=0") != std::string::npos);
	assert(diagnostic_output.find("cargo_routes=0") != std::string::npos);
	assert(diagnostic_output.find("recent hour=3600 outcome=generated") != std::string::npos);
	const auto before_status_rng = random_calls;
	divine_boon_selection_status(&staff);
	assert(random_calls == before_status_rng);
	reset_hour();
	diagnostic_output.clear();
	divine_boon_selection_status(&staff);
	assert(diagnostic_output.find("history=empty") != std::string::npos);
	std::cout << "Divine candidate paths, flags, account brackets and thin pools passed\n";
}
