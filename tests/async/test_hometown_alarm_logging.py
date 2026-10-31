#!/usr/bin/env python3
"""Hometown alarms record the actual trigger, including a pet's master."""

from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, HARNESS_STUBS, extract_function


program = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "combat/justice.h"

#include <cassert>
#include <cstdarg>
#include <cstdio>
#include <string>
#include <vector>

room_data rooms[1]{};
P_room world = rooms;
zone_data zones[1]{};
zone_data *zone_table = zones;
index_data mobs[1]{};
P_index mob_index = mobs;
hometown_data hometowns[LAST_HOME]{};
const char *town_name_list[] = {"Nowhere", "Tharnadia", "Ixarkon", "Arachdrathos"};

static std::vector<int> rolls;
static std::vector<std::string> logs, echoes;
static bool alarms_enabled = true;

int number(int low, int high) {
    assert(!rolls.empty());
    int value = rolls.front();
    rolls.erase(rolls.begin());
    assert(value >= low && value <= high);
    return value;
}
int get_property(const char *, int) { return alarms_enabled; }
int real_room(int) { return -1; } // The roaming NPC was not born in this hometown.
int IS_MORPH(P_char) { return false; }
int GET_CLASS(P_char, uint) { return 0; }
int justice_send_guards(int, P_char, int) { return false; }
void justice_hometown_echo(int town, const char *text) {
    assert(town == zones[0].hometown);
    echoes.emplace_back(text);
}
void logit(const char *filename, const char *format, ...) {
    assert(std::string(filename) == LOG_STATUS);
    char text[4096];
    va_list args;
    va_start(args, format);
    vsnprintf(text, sizeof(text), format, args);
    va_end(args);
    logs.emplace_back(text);
}
'''
program += extract_function("common.c", "const struct race_names race_names_table[LAST_RACE + 2] = {") + ";\n"
program += extract_function("affects.c", "P_char get_linked_char(P_char ch, ush_int type)")
program += "\n" + extract_function("training_dummy.c", "bool training_dummy_is(P_char ch)")
program += "\n" + extract_function("justice.c", "void justice_action_invader(P_char ch)")
program += r'''

static void run(P_char ch, std::initializer_list<int> draws) {
    rolls = draws;
    logs.clear();
    echoes.clear();
    zones[0].last_raid = 0;
    justice_action_invader(ch);
    assert(rolls.empty());
    assert(logs.size() == echoes.size());
}

int main() {
    rooms[0].number = 132504;
    zones[0].hometown = HOME_THARN;
    hometowns[HOME_THARN - 1].flags = JUSTICE_GOODHOME;
    hometowns[HOME_ARACHDRATHOS - 1].flags = JUSTICE_EVILHOME;
    mobs[0].virtual_number = 1234;

    char demon_name[] = "a summoned demon", player_name[] = "Raider";
    char master_name[] = "FriendlyOwner";
    char_data pet{}, owner{}, player{};
    npc_only_data npc{};
    pet.player.name = demon_name;
    pet.player.race = RACE_DEMON;
    pet.specials.act = ACT_ISNPC;
    pet.only.npc = &npc;
    owner.player.name = master_name;
    owner.player.racewar = RACEWAR_GOOD;
    char_link_data link{};
    link.type = LNK_PET;
    link.linked = &owner;
    pet.linking = &link;

    // All four existing good-town message rolls log once, with pet attribution.
    for (int variant = 1; variant <= 4; ++variant) {
        run(&pet, {1, 0, variant});
        assert(logs.size() == 1);
        assert(logs[0] == "HOMETOWN ALARM: town=Tharnadia room=132504 trigger=a summoned demon npc_vnum=1234 race=Demon master=FriendlyOwner");
        assert(echoes[0] == (variant == 1 || variant == 4 ?
            "&+RAlarm bells sound, &+rsignalling an invasion!&n" :
            "&+LMilitia forces muster to bolster the town's defenses against the &=Lrinvaders!!!&n"));
    }

    // Unowned NPCs remain identifiable without inventing a master.
    pet.linking = nullptr;
    run(&pet, {1, 0, 1});
    assert(logs[0].ends_with("race=Demon master=none"));

    // Players never access NPC-only prototype data, in either town alignment.
    player.player.name = player_name;
    player.player.race = RACE_DROW;
    player.player.racewar = RACEWAR_EVIL;
    run(&player, {1, 0, 1});
    assert(logs[0] == "HOMETOWN ALARM: town=Tharnadia room=132504 trigger=Raider npc_vnum=-1 race=Drow Elf master=none");
    zones[0].hometown = HOME_ARACHDRATHOS;
    player.player.race = RACE_HUMAN;
    player.player.racewar = RACEWAR_GOOD;
    run(&player, {1, 0});
    assert(logs[0] == "HOMETOWN ALARM: town=Arachdrathos room=132504 trigger=Raider npc_vnum=-1 race=Human master=none");
    assert(echoes[0] == "&+yHorns begin to &+Ybellow &+yand drums &+cthunder&n &+yto the &+Rcall to arms!&n");

    // No audit noise when the random check misses, alarms are disabled,
    // or the character is exempt from the hometown's invader response.
    run(&player, {1, 1});
    assert(logs.empty());
    alarms_enabled = false;
    run(&player, {1, 0});
    assert(logs.empty());
    alarms_enabled = true;
    zones[0].hometown = HOME_THARN;
    run(&player, {}); // Friendly player.
    assert(logs.empty());
    player.player.racewar = RACEWAR_EVIL;
    player.player.level = MAXLVLMORTAL + 1;
    run(&player, {}); // Trusted player.
    assert(logs.empty());
    npc.training_dummy = true;
    run(&pet, {});
    assert(logs.empty());
    npc.training_dummy = false;
    pet.specials.affected_by = AFF_BOUND;
    run(&pet, {});
    assert(logs.empty());
    zones[0].hometown = 0;
    run(&pet, {});
    assert(logs.empty());
}
'''

directory = ROOT / "bin/tests"
directory.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="hometown-alarm-", dir=directory) as temporary:
    path = Path(temporary)
    source = path / "harness.cpp"
    binary = path / "harness"
    source.write_text(program)
    subprocess.run(
        ["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-Isrc",
         "-fsanitize=address,undefined", "-fno-pie", "-no-pie",
         str(source), str(HARNESS_STUBS), "-o", str(binary)],
        cwd=ROOT, check=True,
    )
    subprocess.run([str(binary)], check=True, timeout=10)

print("hometown alarms log their trigger and master only when an alarm is emitted")
