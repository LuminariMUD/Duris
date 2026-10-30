#include "cmd/interp.h"
#include "economy/boon.h"
#include "economy/divine_boon_runtime.h"
#include "economy/divine_boon_selection.h"
#include "core/prototypes.h"
#include "core/utility.h"
#include "core/utils.h"
#include "ships/ships.h"
#include <cassert>
#include <map>
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
static bool capturing_echo = false;
static string all_echoes;
static map<P_char, string> recipient_echoes;
P_desc descriptor_list = nullptr;
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
int32_t divine_boon_shared_target_zone(const divine_boon_slot &slot)
{
	if (slot.category != divine_boon_category::experience &&
	    slot.category != divine_boon_category::epic)
		return -1;
	for (int zone : slot.zones)
		if (zone >= 0 && divine_boon_zone_eligible(zone, 0) &&
		    divine_boon_zone_eligible(zone, 1))
			return zone;
	for (int zone : slot.zones)
		if (zone >= 0 &&
		    (divine_boon_zone_eligible(zone, 0) || divine_boon_zone_eligible(zone, 1)))
			return zone;
	return divine_boon_target_zone(slot);
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
void send_to_char(const char *message, P_char ch)
{
	if (capturing_echo)
		recipient_echoes[ch] += message;
	else
		output += message;
}
void send_to_all(const char *message)
{
	all_echoes += message;
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
		"&+YThe Gods of Duris have given you and your allies the following boons:&n\r\n"));
	assert(shown.find("&+G[1] 200% Experience&n") != string::npos);
	assert(shown.find("&+C[3] +25% Cargo & Contraband&n") != string::npos);
	assert(shown.find("&+R[4] +50% PvP Epic Points&n") != string::npos);
	assert(shown.find("&+RNative coloured dungeon&n") != string::npos);
	assert(shown.find("Frags against Evil racewar") != string::npos);
	assert(shown.find("&+CSource&n") != string::npos &&
	       shown.find("&+YDestination&n") != string::npos);
	assert(shown.find("From:") == string::npos && shown.find("To:") == string::npos);
	assert(shown.find("Next hourly opportunity:") == string::npos);
	assert(shown.find("&+YNext Divine Boon opportunity in ") != string::npos);
	assert(shown.find("base sale") == string::npos);
	assert(shown.find("&+M[2]") == string::npos); // Invalid epic target is hidden.
	// A single cargo boon occupies one aligned table row, not three separate lines.
	const size_t cargo_at = shown.find("&+C[3]");
	assert(cargo_at != string::npos);
	const size_t cargo_start = shown.rfind("\r\n", cargo_at) + 2;
	const size_t cargo_end = shown.find("\r\n", cargo_at);
	const string cargo_line =
		strip_ansi(shown.substr(cargo_start, cargo_end - cargo_start).c_str());
	assert(cargo_line.size() == 79);
	assert(cargo_line.substr(2, 4) == "[3] ");
	assert(cargo_line.find("Source -> Destination", 35) != string::npos);
	assert(cargo_line.substr(69, 10).find("h ") != string::npos);
	// A valid epic target is magenta; zone colouring remains its original ANSI.
	const int original_zone = zones[0].number;
	zones[0].number = 21;
	shown = invoke(&player, "");
	assert(shown.find("&+M[2] +50% Epic Points&n") != string::npos);
	assert(shown.find("&+RNative coloured dungeon&n") != string::npos);
	player.player.racewar = RACEWAR_EVIL;
	const auto evil_epic = invoke(&player, "list");
	assert(evil_epic.find("&+M[2] +50% Epic Points&n") != string::npos);
	assert(evil_epic.find("&+RNative coloured dungeon&n") != string::npos);
	player.player.racewar = RACEWAR_GOOD;
	// Truncated real targets retain an explicit identity within the same row width.
	char *original_name = zones[0].name;
	for (const auto &[id, name] :
	     { std::pair{ 27, "&+MZalkapfaan, City of the Headless Horde&n" },
	       std::pair{ 1398, "&+CThe Para-Elemental Plane of Smoke&n" } })
	{
		zones[0].number = authority.slots[1].zones[0] = id;
		zones[0].name = const_cast<char *>(name);
		shown = invoke(&player, "");
		const auto at = shown.find("&+M[2]");
		const auto start = shown.rfind("\r\n", at) + 2;
		const auto end = shown.find("\r\n", at);
		const string row = strip_ansi(shown.substr(start, end - start).c_str());
		assert(row.size() == 79);
		assert(row.substr(35, 32).ends_with("... [" + std::to_string(id) + "]"));
		assert(shown.find(string(name).substr(0, 3)) != string::npos);
	}
	zones[0].name = original_name;
	authority.slots[1].zones[0] = 21;
	zones[0].number = original_zone;
	player.player.racewar = RACEWAR_EVIL;
	shown = invoke(&player, "list");
	assert(shown.find("Frags against Good racewar") != string::npos &&
	       shown.find("&+RNative coloured dungeon&n") != string::npos);
	assert(shown.find("&+Gxxx") == string::npos); // Legacy Good target is shared.
	player.player.racewar = RACEWAR_NEUTRAL;
	shown = invoke(&player, "");
	assert(shown.find("PvP Epic Points") == string::npos &&
	       shown.find("200% Experience") == string::npos &&
	       shown.find("+25% Cargo & Contraband") != string::npos);
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
	// Experience and Epic announcements disclose the same hotspot to both sides;
	// saved one-sided objectives are also announced globally.
	char_data good = {}, evil = {}, neutral = {};
	good.player.racewar = RACEWAR_GOOD;
	evil.player.racewar = RACEWAR_EVIL;
	neutral.player.racewar = RACEWAR_NEUTRAL;
	descriptor_data gd = {}, ed = {}, nd = {};
	gd.character = &good;
	ed.character = &evil;
	nd.character = &neutral;
	gd.connected = ed.connected = nd.connected = CON_PLAYING;
	gd.next = &ed;
	ed.next = &nd;
	descriptor_list = &gd;
	capturing_echo = true;
	std::array<divine_boon_slot, DIVINE_BOON_SLOTS> before = {}, after = {};
	exp.id = 101;
	exp.starts_at = hour;
	exp.expires_at = hour + 8 * DIVINE_BOON_HOUR;
	after[0] = exp;
	divine_boon_announce_changes(before, after, now);
	assert(all_echoes.find("&+G200% Base Experience&n") != string::npos);
	assert(all_echoes.find("&+RNative coloured dungeon&n") != string::npos);
	assert(recipient_echoes.empty());
	const auto one = all_echoes;
	divine_boon_announce_changes(after, after, now);
	assert(all_echoes == one); // Unchanged snapshot never re-announces.

	before = after;
	cargo.id = 102;
	cargo.starts_at = hour;
	cargo.expires_at = hour + 4 * DIVINE_BOON_HOUR;
	after[1] = cargo;
	divine_boon_announce_changes(before, after, now);
	assert(all_echoes.find("&+C+25% Cargo & Contraband&n") != string::npos);
	assert(all_echoes.find("&+CSource&n") != string::npos);
	assert(all_echoes.find("&+YDestination&n") != string::npos);
	before = after;
	after[1] = {};
	const auto grant_echo = all_echoes;
	divine_boon_announce_changes(before, after, now);
	assert(all_echoes == grant_echo); // Manual replacement is not expiry.
	divine_boon_announce_changes(before, after, cargo.expires_at);
	assert(all_echoes.find("has expired") != string::npos);
	before = after;
	pvp.id = 103;
	pvp.starts_at = hour;
	pvp.expires_at = hour + 4 * DIVINE_BOON_HOUR;
	after[2] = pvp;
	divine_boon_announce_changes(before, after, now);
	assert(all_echoes.find("&+R+50% PvP Epic Points&n") != string::npos);
	before = after;
	epic.id = 104;
	epic.zones = { 18, -1 };
	epic.starts_at = hour;
	epic.expires_at = hour + 8 * DIVINE_BOON_HOUR;
	after[3] = epic;
	divine_boon_announce_changes(before, after, now);
	assert(all_echoes.find("&+M+50% Epic Points&n") != string::npos);
	assert(all_echoes.find("&+RNative coloured dungeon&n") != string::npos);
	before = after;
	after[0] = {};
	divine_boon_announce_changes(before, after, exp.expires_at);
	assert(all_echoes.find("have withdrawn") != string::npos);
	capturing_echo = false;
	descriptor_list = nullptr;
	std::cout
		<< "Divine commands: native ANSI/80 columns, shared faction targets, global world echoes, durable staff controls and history passed\n";
}
