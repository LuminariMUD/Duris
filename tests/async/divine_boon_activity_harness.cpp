#include "economy/divine_boon_activity.h"
#include "core/utils.h"

#include <cassert>
#include <iostream>

// MORPH_POLICY

P_desc descriptor_list = nullptr;
namespace
{
char_data bodies[3] = {};
pc_only_data players[3] = {};
descriptor_data descriptors[3] = {};
acct_entry accounts[3] = {};
std::string account_names[3];
bool present[3] = { true, true, true };
P_char morph_body = nullptr;

divine_boon_actor actor(uint32_t pid, const char *account, uint8_t side, uint16_t level)
{
	return { pid, account, side, level, true };
}

void played(divine_boon_activity_history &history, const divine_boon_actor &who, int64_t start)
{
	for (int offset : { 0, 60, 120, 180, 300 })
		assert(history.observe(who, start + offset));
}

void windows_and_accounts()
{
	divine_boon_activity_history history;
	auto good = actor(1, "Alice", 0, 20);
	auto evil = actor(2, "Bob", 1, 35);
	assert(history.population({ good, evil }, 0)[0].active_accounts == 0);
	assert(!history.observe(good, -1));
	for (int now = 0; now < 60; ++now)
		assert(history.observe(good, now));
	assert(history.population({ good }, 59)[0].pvp_accounts == 0);
	for (int now : { 60, 120, 180, 299 })
		assert(history.observe(good, now));
	assert(history.population({ good }, 299)[0].pvp_accounts == 0);
	assert(history.observe(good, 300));
	played(history, evil, 0);
	auto population = history.population({ good, evil }, 300);
	assert(population[0].active_accounts == 1 && population[1].active_accounts == 1);
	assert(population[0].pvp_accounts == 1 && population[1].pvp_accounts == 1);
	assert(population[0].brackets[0] == 1 && population[1].brackets[1] == 1);
	auto alt = actor(3, "ALICE", 0, 51);
	assert(history.observe(alt, 301));
	population = history.population({ good, alt, evil, alt }, 301);
	assert(population[0].active_accounts == 1 && population[0].brackets[3] == 1);
	assert(population[0].pvp_accounts == 1); // Account history follows its active alts.
	assert(history.population({ alt }, 301)[0].pvp_accounts == 1); // Earlier alt logged out.
	alt.eligible = false;
	population = history.population({ good, alt }, 301);
	assert(population[0].active_accounts == 1 && population[0].brackets[0] == 1);
	assert(history.population({ good }, 1199)[0].active_accounts == 1);
	assert(history.population({ good }, 1200)[0].active_accounts == 1);
	assert(history.population({ good }, 1201)[0].active_accounts == 0);
	assert(history.observe(good, 1201));
	assert(history.population({ good }, 1201)[0].pvp_accounts == 1);
	assert(history.observe(good, 4801)); // A full hour erases old qualification.
	assert(history.population({ good }, 4801)[0].pvp_accounts == 0);
	assert(history.population({}, 4801)[0].active_accounts == 0);
	assert(!history.observe(good, 4799));
	good.account = "new-owner";
	assert(history.population({ good }, 4801)[0].active_accounts == 0);
}

void sides_and_brackets()
{
	divine_boon_activity_history history;
	std::vector<divine_boon_actor> current;
	for (int level : { 1, 20, 21, 35, 36, 50, 51, 56 })
	{
		auto who = actor(static_cast<uint32_t>(level),
				 ("account" + std::to_string(level)).c_str(), 0, level);
		played(history, who, 0);
		current.push_back(who);
	}
	const auto population = history.population(current, 300);
	assert(population[0].active_accounts == 8 && population[0].pvp_accounts == 8);
	for (unsigned count : population[0].brackets)
		assert(count == 2);
	auto evil_alt = actor(200, "ACCOUNT1", 1, 30);
	played(history, evil_alt, 0);
	current.push_back(evil_alt);
	const auto overlap = history.population(current, 300);
	assert(overlap[0].active_accounts == 8 && overlap[1].active_accounts == 1);
	assert(overlap[0].pvp_accounts == 7 && overlap[1].pvp_accounts == 1);
	// Distinct accounts, even behind the same host, remain independent.
	auto opposing = actor(201, "opposing", 1, 30);
	played(history, opposing, 0);
	current.push_back(opposing);
	assert(history.population(current, 300)[1].pvp_accounts == 2);
	current[0].eligible = false;
	assert(history.population(current, 300)[1].pvp_accounts == 2);
	assert(history.population(current, -1)[0].active_accounts == 0);
	divine_boon_activity_history only_alts;
	auto one_good = actor(1, "same-account", 0, 20);
	auto one_evil = actor(2, "SAME-ACCOUNT", 1, 30);
	played(only_alts, one_good, 0);
	played(only_alts, one_evil, 5);
	const auto alone = only_alts.population({ one_good, one_evil }, 305);
	assert(alone[0].pvp_accounts == 0 && alone[1].pvp_accounts == 1);
}

void setup_game()
{
	morph_body = nullptr;
	static uint32_t next_pid = 1000;
	for (size_t index = 0; index < 3; ++index)
	{
		bodies[index] = {};
		players[index] = {};
		descriptors[index] = {};
		accounts[index] = {};
		present[index] = true;
		bodies[index].runtime_id = index + 1;
		bodies[index].only.pc = &players[index];
		players[index].pid = ++next_pid;
		bodies[index].player.level = 30;
		bodies[index].player.racewar = RACEWAR_GOOD;
		bodies[index].in_room = 5;
		bodies[index].desc = &descriptors[index];
		descriptors[index].character = &bodies[index];
		descriptors[index].connected = CON_PLAYING;
		descriptors[index].account = &accounts[index];
		account_names[index] = "activity-" + std::to_string(next_pid);
		accounts[index].acct_name = account_names[index].data();
		descriptors[index].next = index < 2 ? &descriptors[index + 1] : nullptr;
	}
	descriptor_list = &descriptors[0];
}

void real_input_boundary()
{
	setup_game();
	for (int spam = 0; spam < 10; ++spam)
		divine_boon_activity_end(divine_boon_activity_begin(&bodies[0]));
	assert(divine_boon_activity_population()[0].active_accounts == 0);
	// An automatically awarded combat tick has no playing-input capture.
	GET_EXP(&bodies[1]) += 100;
	assert(divine_boon_activity_population()[0].active_accounts == 0);
	auto input = divine_boon_activity_begin(&bodies[0]);
	GET_EXP(&bodies[1]) += 100; // A force-like effect on somebody else is not their input.
	divine_boon_activity_end(input);
	assert(divine_boon_activity_population()[0].active_accounts == 0);
	input = divine_boon_activity_begin(&bodies[0]);
	++bodies[0].in_room;
	divine_boon_activity_end(input);
	assert(divine_boon_activity_population()[0].active_accounts == 1);
	descriptors[0].showstr_count = 1;
	assert(divine_boon_activity_population()[0].active_accounts == 1);
	assert(!divine_boon_activity_begin(&bodies[0]).runtime_id);
	descriptors[0].showstr_count = 0;
	char *editing = nullptr;
	descriptors[0].str = &editing;
	assert(divine_boon_activity_population()[0].active_accounts == 1);
	assert(!divine_boon_activity_begin(&bodies[0]).runtime_id);
	descriptors[0].str = nullptr;
	SET_BIT(bodies[0].specials.act, PLR_AFK);
	assert(divine_boon_activity_population()[0].active_accounts == 0);
	REMOVE_BIT(bodies[0].specials.act, PLR_AFK);
	assert(divine_boon_activity_population()[0].active_accounts == 1);
	bodies[0].desc = nullptr;
	assert(divine_boon_activity_population()[0].active_accounts == 0);
	setup_game();
	input = divine_boon_activity_begin(&bodies[0]);
	SET_BIT(bodies[0].specials.affected_by2, AFF2_CASTING);
	divine_boon_activity_end(input);
	assert(divine_boon_activity_population()[0].active_accounts == 1);
	setup_game();
	bodies[0].player.level = MAXLVLMORTAL + 1;
	assert(!divine_boon_activity_begin(&bodies[0]).runtime_id);
	bodies[0].player.level = 30;
	acct_chars staff = {};
	staff.racewar = ACCT_IMMORTAL;
	accounts[0].acct_character_list = &staff;
	assert(!divine_boon_activity_begin(&bodies[0]).runtime_id);
	accounts[0].acct_character_list = nullptr;
	bodies[0].player.racewar = RACEWAR_NEUTRAL;
	assert(!divine_boon_activity_begin(&bodies[0]).runtime_id);
	bodies[0].player.racewar = RACEWAR_GOOD;
	input = divine_boon_activity_begin(&bodies[0]);
	present[0] = false; // Quit/extraction before the post-dispatch observation.
	divine_boon_activity_end(input);
	assert(divine_boon_activity_population()[0].active_accounts == 0);
}

void container_input()
{
	setup_game();
	obj_data source = {}, target = {}, nested = {}, item = {};
	bodies[0].carrying = &source;
	source.next_content = &target;
	source.contains = &nested;
	nested.contains = &item;
	IS_CARRYING_N(&bodies[0]) = 2;
	auto input = divine_boon_activity_begin(&bodies[0]);
	divine_boon_activity_end(input); // Inspecting unchanged contents creates no evidence.
	assert(divine_boon_activity_population()[0].active_accounts == 0);
	input = divine_boon_activity_begin(&bodies[0]);
	nested.contains = nullptr;
	target.contains = &item; // The resulting tree of empty source target.
	divine_boon_activity_end(input);
	assert(IS_CARRYING_N(&bodies[0]) == 2);
	assert(divine_boon_activity_population()[0].active_accounts == 1);
	bodies[0].carrying = nullptr;
}

void morphed_player()
{
	setup_game();
	char_data body = {};
	npc_only_data npc = {};
	body.only.npc = &npc;
	npc.orig_char = &bodies[0];
	body.runtime_id = 4;
	body.specials.act = ACT_ISNPC;
	body.desc = &descriptors[0];
	descriptors[0].character = &body;
	morph_body = &body;
	const auto input = divine_boon_activity_begin(&body);
	assert(input.runtime_id == 4 && input.pid == static_cast<uint32_t>(players[0].pid));
	++body.in_room;
	divine_boon_activity_end(input);
	assert(divine_boon_activity_population()[0].active_accounts == 1);
	npc.orig_char = nullptr;
	assert(!divine_boon_activity_begin(&body).runtime_id);
	morph_body = nullptr;
	descriptors[0].character = nullptr;
}
}

P_char find_character_by_runtime_id(uint64_t id)
{
	if (morph_body && morph_body->runtime_id == id)
		return morph_body;
	for (size_t index = 0; index < 3; ++index)
		if (present[index] && bodies[index].runtime_id == id)
			return &bodies[index];
	return nullptr;
}

int main()
{
	windows_and_accounts();
	sides_and_brackets();
	real_input_boundary();
	container_input();
	morphed_player();
	std::cout
		<< "Divine activity: 60/15/5-minute windows, accounts, brackets, real input and exclusions passed\n";
}
