#include "cmd/interp.h"
#include "economy/boon.h"
#include "economy/divine_boon_runtime.h"
#include "economy/divine_boon_selection.h"
#include "core/prototypes.h"
#include "core/utility.h"
#include "core/utils.h"
#include "ships/ships.h"
#include <cassert>
#include <cstdarg>
#include <ctime>
#include <iostream>
#include <string>
using namespace std;

// NATIVE_ANSI_FUNCTIONS

zone_data zones[2] = {};
zone_data *zone_table = zones;
int top_of_zone_table = 1;
const PortData ports[NUM_PORTS] = { { 1, "&+CSource&n", 0 }, { 2, "&+YDestination&n", 0 } };
static divine_boon_state authority, queued;
static bool available = true, pending = false, admit = true, eligible = true;
static unsigned writes = 0, forces = 0, audits = 0;
static string output;
const divine_boon_state *divine_boon_runtime_state()
{
	return available ? &authority : nullptr;
}
bool divine_boon_runtime_pending()
{
	return pending;
}
bool divine_boon_runtime_queue(const divine_boon_state &next)
{
	++writes;
	if (!admit)
		return false;
	queued = next;
	pending = true;
	return true;
}
bool divine_boon_zone_eligible(int zone, unsigned side)
{
	return eligible && side < 2 && zone == zones[side].number;
}
bool divine_boon_epic_zone_eligible(int zone, unsigned side)
{
	return divine_boon_zone_eligible(zone, side);
}
bool divine_boon_cargo_eligible(const divine_boon_slot &)
{
	return eligible;
}
void divine_boon_selection_status(P_char) {}
void divine_boon_selection_pulse(int64_t)
{
	++forces;
}
void wizlog(int, const char *, ...)
{
	++audits;
}
void send_to_char(const char *message, P_char)
{
	output += message;
}
void send_to_char_f(P_char, const char *format, ...)
{
	char buffer[4096];
	va_list args;
	va_start(args, format);
	vsnprintf(buffer, sizeof(buffer), format, args);
	va_end(args);
	output += buffer;
}
char *one_argument(const char *argument, char *word)
{
	while (*argument == ' ')
		++argument;
	while (*argument && *argument != ' ')
		*word++ = tolower(*argument++);
	*word = 0;
	while (*argument == ' ')
		++argument;
	return const_cast<char *>(argument);
}
static string invoke(P_char ch, const char *argument, bool staff = false)
{
	output.clear();
	char buffer[256];
	snprintf(buffer, sizeof(buffer), "%s", argument);
	if (staff)
		do_divineboon(ch, buffer, 0);
	else
		do_divine_boon(ch, buffer, 0);
	for (size_t pos = 0; pos < output.size();)
	{
		const auto end = output.find("\r\n", pos);
		assert(end != string::npos);
		assert(strip_ansi(output.substr(pos, end - pos).c_str()).size() <= 80);
		pos = end + 2;
	}
	return output;
}
int main()
{
	const int64_t now = time(nullptr), hour = now - now % DIVINE_BOON_HOUR;
	assert(divine_boon_set_mode(&authority, divine_boon_mode::draining, now));
	assert(divine_boon_set_mode(&authority, divine_boon_mode::divine, now));
	authority.last_opportunity = hour - 4 * DIVINE_BOON_HOUR;
	zones[0].number = 18;
	zones[1].number = 20;
	zones[0].name = const_cast<char *>("&+RNative coloured dungeon&n");
	string long_name = "&+G" + string(100, 'x') + "&n";
	zones[1].name = long_name.data();
	divine_boon_slot exp;
	exp.category = divine_boon_category::experience;
	exp.zones = { 18, 20 };
	assert(divine_boon_rotate(&authority, hour - 3 * DIVINE_BOON_HOUR, &exp));
	divine_boon_slot epic = exp;
	epic.category = divine_boon_category::epic;
	epic.zones = { 21, 22 };
	assert(divine_boon_rotate(&authority, hour - 2 * DIVINE_BOON_HOUR, &epic));
	divine_boon_slot cargo;
	cargo.category = divine_boon_category::cargo;
	cargo.source_port = cargo.cargo_commodity = cargo.contraband_commodity = 0;
	cargo.destination_port = 1;
	assert(divine_boon_rotate(&authority, hour - DIVINE_BOON_HOUR, &cargo));
	divine_boon_slot pvp;
	pvp.category = divine_boon_category::pvp;
	assert(divine_boon_rotate(&authority, hour, &pvp));
	char_data player = {};
	player.player.level = 10;
	player.player.racewar = RACEWAR_GOOD;
	player.player.name = const_cast<char *>("Tester");
	auto shown = invoke(&player, "");
	assert(shown.starts_with(
		"The Gods of Duris have given you and your allies the following boons:\r\n"));
	assert(shown.find("&+RNative coloured dungeon&n") != string::npos);
	assert(shown.find("Good defeats qualifying Evil") != string::npos);
	assert(shown.find("&+CSource&n") != string::npos &&
	       shown.find("&+YDestination&n") != string::npos);
	assert(shown.find("200% total base") != string::npos &&
	       shown.find("50% base") != string::npos &&
	       shown.find("25% base sale") != string::npos);
	assert(shown.find("Epic stone") == string::npos); // Invalid target is never advertised.
	player.player.racewar = RACEWAR_EVIL;
	shown = invoke(&player, "list");
	assert(shown.find("Evil defeats qualifying Good") != string::npos &&
	       shown.find("&+Gxxx") != string::npos);
	player.player.racewar = RACEWAR_NEUTRAL;
	shown = invoke(&player, "");
	assert(shown.find("PvP") == string::npos && shown.find("Zone EXP") == string::npos &&
	       shown.find("Cargo & contraband") != string::npos);
	eligible = false;
	shown = invoke(&player, "");
	assert(shown.find("no active boons") != string::npos);
	eligible = true;
	available = false;
	assert(invoke(&player, "").find("initializing") != string::npos);
	available = true;
	assert(invoke(&player, "shop").find("Usage") != string::npos);
	assert(invoke(&player, "pause", true).empty() && !writes);
	player.player.level = IMMORTAL;
	eligible = false;
	shown = invoke(&player, "status", true);
	assert(shown.find("Native coloured dungeon") != string::npos);
	eligible = true;

	shown = invoke(&player, "pause", true);
	assert(pending && !authority.paused && queued.paused && writes == 1 && audits == 1);
	invoke(&player, "pause", true);
	assert(writes == 1);
	authority = queued;
	pending = false;
	assert(invoke(&player, "list").find("paused") != string::npos);
	invoke(&player, "resume", true);
	assert(pending && authority.paused && !queued.paused);
	authority = queued;
	pending = false;
	invoke(&player, "replace 1", true);
	assert(pending && authority.slots[0].id && !queued.slots[0].id &&
	       queued.recent.size() == 1);
	authority = queued;
	pending = false;
	assert(invoke(&player, "history", true).find("Native coloured dungeon") != string::npos);
	const auto previous = authority;
	invoke(&player, "replace -1", true);
	invoke(&player, "replace 9", true);
	invoke(&player, "replace 2 junk", true);
	assert(authority == previous && !pending);
	invoke(&player, "force", true);
	assert(forces == 1 && authority == previous);
	admit = false;
	invoke(&player, "pause", true);
	assert(!pending && authority == previous);
	assert(invoke(&player, "status", true).find("revision=") != string::npos);
	std::cout
		<< "Divine commands: native ANSI/80 columns, sides, invalid targets, automatic benefits, durable staff controls and history passed\n";
}
