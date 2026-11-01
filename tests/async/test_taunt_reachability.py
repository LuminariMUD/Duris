#!/usr/bin/env python3
"""Run the taunt command against real single-file formations.

The handler, target parser, adjacency predicate and affect lookup are production
code. Rolls, affect publication and combat services are deterministic fixtures.
"""

from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, extract_function


PRELUDE = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "magic/spells.h"
#include "net/comm.h"
#include <algorithm>
#include <cassert>
#include <cstdio>
#include <cstring>
#include <initializer_list>
#include <string>

static room_data room{};
P_room world = &room;
static char_data taunter{}, mob{}, tank{};
static affected_type taunt{};
static int rolls, saves, notches, applied, removed, stopped, engaged;
static int actor_wait, victim_wait, skill_roll;
static bool resisted;
static std::string feedback;

bool SanityCheck(P_char ch, const char *) { return ch != nullptr; }
int GET_CHAR_SKILL_P(P_char, int skill) { assert(skill == SKILL_TAUNT); return 100; }
int get_property(const char *, int fallback) { return fallback; }
bool notch_skill(P_char, int, float) { ++notches; return false; }
int number(int low, int high) {
    assert(low == 1 && high == 100);
    ++rolls;
    return skill_roll;
}
bool NewSaves(P_char ch, int type, int) {
    assert(ch == &mob && type == SAVING_FEAR);
    ++saves;
    return resisted;
}
int BOUNDED(int low, int value, int high) { return std::clamp(value, low, high); }
bool ac_can_see(P_char, P_char, bool) { return true; }
char *one_argument(const char *arg, char *out) {
    std::strcpy(out, arg);
    return out + std::strlen(out);
}
P_char get_char_room_vis(P_char ch, const char *name) {
    for (P_char target = world[ch->in_room].people; target; target = target->next_in_room)
        if (!std::strcmp(target->player.name, name)) return target;
    return nullptr;
}
void do_action(P_char, char *, int) { assert(false); }
void send_to_char(const char *text, P_char) { feedback += text; }
void act(const char *text, int, P_char, P_obj, void *, int flags) {
    if (flags == TO_CHAR) feedback += text;
}
void CharWait(P_char ch, int delay) {
    if (ch == &mob) victim_wait += delay;
    else { assert(ch == &taunter); actor_wait += delay; }
}
void affect_to_char_with_messages(P_char ch, affected_type *af, const char *, const char *) {
    assert(ch == &mob && !ch->affected);
    taunt = *af;
    ch->affected = &taunt;
    ++applied;
}
void affect_from_char(P_char ch, int type) {
    assert(ch == &mob && type == SKILL_TAUNT);
    ch->affected = nullptr;
    ++removed;
}
void stop_fighting(P_char ch) {
    assert(ch == &mob);
    GET_OPPONENT(ch) = nullptr;
    ++stopped;
}
void engage(P_char ch, P_char target) {
    assert(ch == &mob && target == &taunter);
    GET_OPPONENT(ch) = target;
    if (!IS_FIGHTING(target)) GET_OPPONENT(target) = ch;
    ++engaged;
}
'''

DRIVER = r'''
static void reset(std::initializer_list<P_char> formation, bool narrow = true) {
    room = {}; taunter = {}; mob = {}; tank = {}; taunt = {};
    room.number = 40010;
    room.room_flags = narrow ? ROOM_SINGLE_FILE : 0;
    taunter.player.name = const_cast<char *>("Taunter");
    mob.player.name = const_cast<char *>("Mob");
    tank.player.name = const_cast<char *>("Tank");
    SET_BIT(mob.specials.act, ACT_ISNPC);
    P_char *next = &room.people;
    for (P_char ch : formation) {
        ch->in_room = 0;
        ch->player.level = 50;
        SET_POS(ch, POS_STANDING + STAT_NORMAL);
        *next = ch;
        next = &ch->next_in_room;
    }
    mob.specials.fighting = &tank;
    tank.specials.fighting = &mob;
    rolls = saves = notches = applied = removed = stopped = engaged = 0;
    actor_wait = victim_wait = 0;
    skill_roll = 1;
    resisted = false;
    feedback.clear();
}

static void existing_taunt(P_char issuer) {
    taunt.type = SKILL_TAUNT;
    taunt.context = issuer;
    taunt.duration = 17;
    mob.affected = &taunt;
}

static void invoke() { do_taunt(&taunter, const_cast<char *>("Mob"), 0); }

static void assert_ineffective(P_char issuer = nullptr) {
    assert(mob.specials.fighting == &tank && tank.specials.fighting == &mob);
    assert(!taunter.specials.fighting);
    assert(!applied && !removed && !stopped && !engaged && !victim_wait);
    if (issuer) {
        assert(mob.affected == &taunt && taunt.context == issuer && taunt.duration == 17);
    } else {
        assert(!mob.affected);
        // A rejected taunt must not redirect later targeting to its issuer.
        assert(ParseTarget(&mob, const_cast<char *>("Tank")) == &tank);
    }
}

static void blocked_cases() {
    for (bool reverse : {false, true}) {
        for (P_char issuer : {static_cast<P_char>(nullptr), &taunter, &tank}) {
            if (reverse) reset({&taunter, &tank, &mob});
            else reset({&mob, &tank, &taunter});
            assert(AdjacentInRoom(&mob, &tank) && !AdjacentInRoom(&mob, &taunter));
            if (issuer) existing_taunt(issuer);
            invoke();
            assert_ineffective(issuer);
            assert(!rolls && !saves && !notches && !actor_wait);
            assert(feedback.find("can't reach you") != std::string::npos);
        }
    }
}

static void reachable_cases() {
    for (bool reverse : {false, true}) {
        if (reverse) reset({&taunter, &mob, &tank});
        else reset({&tank, &mob, &taunter});
        assert(AdjacentInRoom(&mob, &tank) && AdjacentInRoom(&mob, &taunter));
        invoke();
        assert(mob.affected == &taunt && taunt.context == &taunter && taunt.duration > 0);
        assert(applied == 1 && stopped == 1 && engaged == 1 && !removed);
        assert(mob.specials.fighting == &taunter && tank.specials.fighting == &mob);
        assert(victim_wait == WAIT_SEC * 2 && actor_wait == PULSE_VIOLENCE);
        assert(ParseTarget(&mob, const_cast<char *>("Tank")) == &taunter);
    }
}

int main() {
    blocked_cases();
    reachable_cases();

    // Room-wide taunting still works in an ordinary room.
    reset({&mob, &tank, &taunter}, false);
    assert(!AdjacentInRoom(&mob, &taunter));
    invoke();
    assert(applied == 1 && mob.specials.fighting == &taunter);

    reset({&tank, &mob, &taunter});
    resisted = true;
    invoke();
    assert_ineffective();
    assert(saves == 1 && actor_wait == PULSE_VIOLENCE);

    reset({&tank, &mob, &taunter});
    skill_roll = 100;
    invoke();
    assert_ineffective();
    assert(rolls == 1 && !saves && actor_wait == PULSE_VIOLENCE);

    // Reachable repeat taunts retain the existing duration extension.
    reset({&tank, &mob, &taunter});
    existing_taunt(&taunter);
    mob.specials.fighting = &taunter;
    invoke();
    assert(taunt.context == &taunter && taunt.duration > 17);
    assert(!applied && !removed && !stopped && !engaged && victim_wait == WAIT_SEC * 2);

    std::puts("taunt reachability: blocked and adjacent formations, existing affects, ordinary rooms, saves and failures passed");
}
'''

functions = [
    extract_function("affects.c", "struct affected_type *get_spell_from_char("),
    extract_function("affects.c", "bool affected_by_spell("),
    extract_function("fight.c", "bool AdjacentInRoom("),
    extract_function("actoff.c", "P_char ParseTarget("),
    extract_function("actoff.c", "void do_taunt("),
]

build = ROOT / "bin/tests"
build.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="taunt-reachability-", dir=build) as directory:
    harness = Path(directory) / "harness.cpp"
    binary = Path(directory) / "harness"
    harness.write_text("\n".join((PRELUDE, *functions, DRIVER)), encoding="utf-8")
    subprocess.run([
        "g++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
        "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-fno-pie", "-no-pie",
        f"-I{ROOT / 'src'}", str(harness), "-o", str(binary),
    ], cwd=ROOT, check=True)
    subprocess.run([str(binary)], cwd=ROOT, check=True)
