#!/usr/bin/env python3
"""Execute complete flee, exit validation, parsing and movement dispatch.

The final room transition and unrelated combat/affect systems are fixtures.
The real movement dispatcher executes specials once; refusals, redirection and
extraction are tested under ASan/UBSan, alongside exact probability boundaries.
"""

from pathlib import Path
import os
import subprocess
import tempfile

from _paths import ROOT, HARNESS_STUBS, extract_function, source


PRELUDE = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "magic/spells.h"
#include "net/comm.h"
#include "world/events.h"
#include "world/db.h"
#include "cmd/interp.h"
#include "combat/grapple.h"
#include "combat/forced_movement.h"
#include "telemetry/telemetry_runtime.h"
#include <cassert>
#include <cstdio>
#include <cstring>
#include <random>
#include <string>

static char_data runner{}, opponent{}, mount{};
static pc_only_data pc{};
static npc_only_data npc{};
static room_data rooms[NUM_EXITS + 2]{};
static room_direction_data exits[NUM_EXITS]{};
static index_data indices[1]{};
P_room world = rooms;
extern const int top_of_world = NUM_EXITS + 1;
P_index obj_index = indices, mob_index = indices;
static zone_data zones[1]{};
zone_data *zone_table = zones;
P_char character_list;
uint64_t character_removal_generation;
P_nevent current_nevent;
static bool completing_water_crossing(P_char, int) { return false; }
static int skill, roll, escape_roll, random_exit, training, moves, special_calls, special_mode;
static bool notch, random_rolls, trapped, woods, flying_mount, entrapment;
static std::mt19937 generator(187);
static std::string output;
const char *dirs[] = {"north", "east", "south", "west", "up", "down", "northwest", "southwest", "northeast", "southeast"};
const char *fill_words[] = {"in", "from", "with", "the", "on", "at", "to", "\n"};

int number(int low, int high) {
    assert(low <= high);
    if (low == 1 && high == 100) return random_rolls ? std::uniform_int_distribution<>(1,100)(generator) : roll;
    if (low == 0 && high == 100) return escape_roll;
    if (low == 0 && high < NUM_EXITS) return random_exit % (high + 1);
    return low;
}
int BOUNDED(int low, int value, int high) { return value < low ? low : value > high ? high : value; }
int GET_CHAR_SKILL_P(P_char, int type) { return type == SKILL_CONTROL_FLEE ? skill : 0; }
int GET_CLASS(P_char ch, uint cls) { return (ch->player.m_class & cls) != 0; }
int GET_SECONDARY_CLASS(P_char, uint) { return false; }
bool notch_skill(P_char, int type, float) {
    if (type != SKILL_CONTROL_FLEE) return false;
    ++training;
    if (notch && skill < 100) ++skill;
    return notch;
}
int get_property(const char *, int fallback) { return fallback; }
P_char get_linked_char(P_char, ush_int) { return flying_mount ? &mount : nullptr; }
P_char get_linking_char(P_char, ush_int) { return nullptr; }
bool check_castle_walls(int, int) { return false; }
int is_ice(P_char, int) { return false; }
bool has_innate(P_char, int) { return false; }
int grapple_flee_check(P_char) { return trapped; }
int grapple_check_entrapment(P_char) { return entrapment; }
bool check_crippling_strike(P_char) { return false; }
void send_to_char(const char *message, P_char) { output += message; }
void act(const char *, int, P_char, P_obj, void *, int) {}
void CharWait(P_char, int) {}
int NumAttackers(P_char) { return 0; }
int exitnumb_to_cmd(int dir) { return dir + 1; }
bool grease_check(P_char) { return false; }
bool special(P_char ch, int, char *) {
    ++special_calls;
    if (special_mode == 2) ch->in_room = NUM_EXITS + 1;
    if (special_mode == 3) { ++character_removal_generation; character_list = nullptr; delete ch; }
    return special_mode != 0;
}
int do_simple_move_skipping_procs(P_char ch, int dir, unsigned int flags) {
    assert(flags == (MVFLG_DRAG_FOLLOWERS | MVFLG_FLEE));
    ++moves; ch->in_room = EXIT(ch, dir)->to_room; return true;
}
room_affect *get_spell_from_room(P_room, int) { static room_affect af{}; return woods ? &af : nullptr; }
void stop_fighting(P_char ch) { ch->specials.fighting = nullptr; }
void set_fighting(P_char ch, P_char other) { ch->specials.fighting = other; }
void StopAllAttackers(P_char ch) { stop_fighting(ch); }
void StartRegen(P_char, regen_resource) {}
void disarm_char_nevents(P_char, event_func_type) {}
nevent_schedule_result add_event(event_func, int, P_char, P_char, P_obj, int, const void *, int) { return {}; }
void event_mob_mundane(P_char, P_char, P_obj, void *) {}
telemetry_capture_result telemetry_runtime_game_encounter_leave(P_char, telemetry_encounter_outcome) { return {}; }
bool affected_by_spell(P_char ch, int type) {
    for (auto *af = ch->affected; af; af = af->next) if (af->type == type) return true;
    return false;
}
affected_type *affect_to_char(P_char ch, affected_type *af) {
    auto *copy = new affected_type(*af); copy->next = ch->affected; ch->affected = copy;
    ch->specials.affected_by |= af->bitvector; return copy;
}
'''


def production():
    return "#define DRAGONSLAYER_VNUM 80569\n" + "\n".join(
        extract_function(file, signature) for file, signature in [
            ("utility.c", "int strn_cmp("),
            ("utility.c", "int char_in_list(const P_char ch)"),
            ("interp.c", "int search_block("),
            ("interp.c", "int fill_word("),
            ("interp.c", "char *one_argument("),
            ("utility.c", "int dir_from_keyword("),
            ("actmove.c", "static int can_enter_room_internal("),
            ("actmove.c", "int can_enter_room("),
            ("actmove.c", "static P_char movement_special_actor("),
            ("actmove.c", "int do_simple_move("),
            ("actoff.c", "bool bad_flee_dir("),
            ("actoff.c", "static bool restore_equipment_sneak_after_flee("),
            ("actoff.c", "void do_flee("),
        ])


DRIVER = r'''
static void clear() {
    while (runner.affected) { auto *af = runner.affected; runner.affected = af->next; delete af; }
}
static void reset(int count = 2) {
    clear(); runner = {}; opponent = {}; mount = {};
    for (auto &room : rooms) room = {};
    for (int dir = 0; dir < count; ++dir) {
        exits[dir] = {}; exits[dir].to_room = dir + 1;
        rooms[0].dir_option[dir] = &exits[dir];
    }
    runner.only.pc = &pc; runner.player.m_class = CLASS_ROGUE; runner.player.level = 56;
    runner.curr_stats.Int = 100;
    SET_POS(&runner, POS_STANDING + STAT_NORMAL); GET_VITALITY(&runner) = 100;
    character_list = &runner;
    skill = 100; roll = 1; escape_roll = random_exit = training = moves = special_calls = special_mode = 0;
    notch = random_rolls = trapped = woods = flying_mount = entrapment = false;
    output.clear();
}
static void flee(const char *argument = "east", P_char ch = &runner) {
    char command[MAX_INPUT_LENGTH]; std::strcpy(command, argument);
    do_flee(ch, command, CMD_FLEE);
}
static bool lost_control() { return output.find("lose control") != std::string::npos; }
static void probabilities() {
    for (int trained : {45, 60, 80, 90, 100}) for (bool learns : {false, true}) {
        int controlled = 0;
        for (int boundary = 1; boundary <= 100; ++boundary) {
            reset(); skill = trained; notch = learns; roll = boundary;
            flee();
            assert(training == 1 && moves == 1);
            bool expected = boundary <= trained * MAX_CHANCE_TO_CONTROL_FLEE / 100;
            assert(lost_control() == !expected);
            assert(runner.in_room == (expected ? 2 : 1));
            controlled += !lost_control();
        }
        assert(controlled == trained * MAX_CHANCE_TO_CONTROL_FLEE / 100);
    }
    int controlled = 0, fallback_coincidences = 0, escaped = 0;
    for (int i = 0; i < 10000; ++i) {
        reset(); random_rolls = true; random_exit = i % 2;
        runner.specials.fighting = &opponent; escape_roll = i % 101;
        flee(); controlled += !lost_control(); escaped += runner.in_room != 0;
        fallback_coincidences += lost_control() && runner.in_room == 2;
    }
    assert(controlled >= 9400 && controlled <= 9600);
    printf("seed=187 n=10000 controlled=%d fallback-to-requested=%d escaped=%d\n",
           controlled, fallback_coincidences, escaped);
}
static void exits_and_arguments() {
    for (const char *arg : {"east", "e", "EAST", "  e  ", "e\t"}) {
        reset(); flee(arg); assert(runner.in_room == 2);
    }
    for (const char *arg : {"nowhere", "east west", "east x"}) {
        reset(); flee(arg); assert(runner.in_room == 0 && moves == 0 && training == 0);
        assert(output.find("Choose one") != std::string::npos);
    }
    for (const char *arg : {"northwest", "nw", "ne", "se", "sw"}) {
        reset(NUM_EXITS); char token[32]; std::strcpy(token, arg);
        int dir = dir_from_keyword(token); flee(arg); assert(runner.in_room == dir + 1);
    }
    reset(0); flee(""); assert(moves == 0 && output.find("safe exit") != std::string::npos);
    reset(1); flee("east"); assert(moves == 0 && training == 0);
    for (int flag : {EX_CLOSED, EX_BLOCKED, EX_SECRET}) {
        reset(); exits[1].exit_info = flag; flee(); assert(moves == 0 && training == 0);
    }
    reset(); exits[1].exit_info = EX_CLOSED; runner.specials.affected_by2 |= AFF2_PASSDOOR;
    flee(); assert(runner.in_room == 2);
    reset(); rooms[2].chance_fall = 10; flee(); assert(moves == 0);
    reset(); rooms[2].sector_type = SECT_NO_GROUND; flee(); assert(moves == 0);
    reset(); rooms[2].sector_type = SECT_NO_GROUND; flying_mount = true;
    mount.specials.affected_by |= AFF_FLY; flee(); assert(runner.in_room == 2);
    reset(); rooms[2].sector_type = SECT_WATER_NOSWIM; flee(); assert(moves == 0);
    reset(); rooms[2].sector_type = SECT_WATER_NOSWIM; rooms[0].current_speed = 1;
    flee(); assert(runner.in_room == 2);
    // Non-rogues, untrained rogues and no-argument flee retain random selection.
    reset(); runner.player.m_class = CLASS_WARRIOR; flee(); assert(runner.in_room == 1 && !training);
    reset(); skill = 0; flee(); assert(runner.in_room == 1 && !training);
    reset(); flee(""); assert(runner.in_room == 1 && !training);
    reset(); runner.specials.act |= ACT_ISNPC; runner.only.npc = &npc;
    flee(); assert(runner.in_room == 1 && !training);
}
static void escape_and_specials() {
    // Direction control and the existing 0..100 escape roll are independent.
    for (int count : {1, 2, 4, NUM_EXITS}) {
        int threshold = MIN_CHANCE_TO_FLEE + MIN(3, count - 1) * (MAX_CHANCE_TO_FLEE - MIN_CHANCE_TO_FLEE) / 3;
        for (int boundary : {threshold - 1, threshold}) {
            reset(count); runner.specials.fighting = &opponent; escape_roll = boundary;
            flee("north"); assert(!lost_control());
            assert((runner.in_room != 0) == (boundary < threshold));
            assert((output.find("couldn't escape") != std::string::npos) == (boundary >= threshold));
        }
    }
    reset(); trapped = true; flee(); assert(!moves);
    reset(); flying_mount = entrapment = true;
    runner.specials.fighting = &opponent;
    mount.specials.fighting = &opponent;
    flee();
    assert(!moves && runner.in_room == 0);
    assert(runner.specials.fighting == &opponent && mount.specials.fighting == &opponent);
    reset(); woods = true; flee(); assert(!moves);
    reset(); special_mode = 1; flee(); assert(!moves && special_calls == 1);
    assert(output.find("couldn't escape") != std::string::npos);
    reset(); special_mode = 2; flee(); assert(!moves && special_calls == 1);
    assert(output.find("You flee eastward") == std::string::npos);
    assert(output.find("unexpected turn") != std::string::npos);
    // A special may free the mover; no post-movement dereference is allowed.
    reset(); auto *temporary = new char_data(runner); character_list = temporary;
    special_mode = 3; flee("east", temporary); assert(special_calls == 1 && !character_list);
    reset(); obj_data boots{}; boots.bitvector = AFF_SNEAK; runner.equipment[WEAR_FEET] = &boots;
    runner.specials.affected_by |= AFF_SNEAK;
    flee(); assert(IS_AFFECTED(&runner, AFF_SNEAK));
    assert(GET_VITALITY(&runner) == 95 && IS_AFFECTED(&runner, AFF_AWARE));
}
int main() {
    probabilities(); exits_and_arguments(); escape_and_specials(); clear();
    puts("Control Flee runtime regressions passed");
}
'''


def main():
    build = Path(os.environ.get("BIN_ROOT", ROOT / "bin")) / "tests"
    build.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="control-flee-", dir=build) as directory:
        cpp, binary = Path(directory) / "harness.cpp", Path(directory) / "harness"
        cpp.write_text(PRELUDE + production() + DRIVER)
        subprocess.run([
            "g++", "-std=c++20", "-g", "-Wall", "-Wextra", "-Werror",
            "-Wno-unused-parameter", "-fsanitize=address,undefined",
            "-fno-omit-frame-pointer", "-fno-pie", "-no-pie",
            "-ffunction-sections", "-fdata-sections", "-Wl,--gc-sections",
            "-I" + str(ROOT / "src"), str(cpp), str(source("combat/forced_movement.c")), str(HARNESS_STUBS), "-o", str(binary),
        ], check=True)
        subprocess.run([str(binary)], check=True, env={**os.environ,
            "ASAN_OPTIONS": "detect_leaks=1:halt_on_error=1",
            "UBSAN_OPTIONS": "halt_on_error=1:print_stacktrace=1"})


if __name__ == "__main__":
    main()
