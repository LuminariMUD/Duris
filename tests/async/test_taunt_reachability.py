#!/usr/bin/env python3
"""Run the taunt command against real single-file formations.

The handler, target parser, adjacency predicate and affect lookup are production
code. Rolls, affect publication and combat services are deterministic fixtures.
"""

from pathlib import Path
import re
import subprocess
import tempfile

from _paths import ROOT, extract_function


PRELUDE = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "magic/spells.h"
#include "net/comm.h"
#include "core/mm.h"
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
static mm_ds link_pool{};
mm_ds *dead_link_pool = &link_pool;
link_description link_types[LNK_MAX + 1]{};
void *_mm_get(mm_ds *, const char *, int) { return new char_link_data{}; }
void mm_release(mm_ds *, void *value) { delete static_cast<char_link_data *>(value); }
mm_ds *mm_create(const char *, size_t, size_t, unsigned) { return &link_pool; }
void logit(const char *, const char *, ...) {}
void wear_off_message(P_char, affected_type *) {}
void unlink_char_affect(P_char, affected_type *);

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
affected_type *affect_to_char(P_char ch, affected_type *af) {
    assert(ch == &mob && !ch->affected);
    taunt = *af;
    ch->affected = &taunt;
    ++applied;
    return ch->affected;
}
void affect_remove(P_char ch, affected_type *af) {
    assert(ch == &mob && af == ch->affected);
    ch->affected = nullptr;
    if (IS_SET(af->flags, AFFTYPE_LINKED_CH)) unlink_char_affect(ch, af);
    ++removed;
}
void affect_from_char(P_char ch, int type) {
    assert(ch->affected && ch->affected->type == type);
    affect_remove(ch, ch->affected);
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
    clear_all_links(&taunter); clear_all_links(&mob); clear_all_links(&tank);
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
    affected_type af{};
    af.type = SKILL_TAUNT;
    af.context = issuer;
    af.duration = 17;
    linked_affect_to_char(&mob, &af, issuer, LNK_TAUNT);
    applied = 0;
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
    initialize_taunt_link();
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

    // Character removal on either end and normal expiry unlink both lists.
    for (P_char departing : {&taunter, &mob}) {
        reset({&tank, &mob, &taunter});
        invoke();
        assert(taunter.linked && mob.linking);
        clear_all_links(departing);
        assert(!mob.affected && !mob.linking && !taunter.linked);
        // Reusing the issuer's address must not redirect later target selection.
        taunter = {};
        assert(ParseTarget(&mob, const_cast<char *>("Tank")) == &tank);
    }
    reset({&tank, &mob, &taunter});
    invoke();
    affect_from_char(&mob, SKILL_TAUNT);
    assert(!mob.linking && !taunter.linked);
    reset({&tank, &mob, &taunter});
    existing_taunt(&tank);
    invoke(); // Retargeting replaces the old link as well as its affect.
    assert(!tank.linked && taunter.linked && mob.linking);
    clear_all_links(&tank); // An unrelated issuer cannot remove this taunt.
    assert(mob.affected && mob.affected->context == &taunter);
    clear_all_links(&taunter);
    assert(!mob.affected && !mob.linking);

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
link_functions = [extract_function("affects.c", signature) for signature in (
    "void define_link(", "struct char_link_data *link_char_with_affect(",
    "P_char get_linked_char(", "P_char get_linking_char(", "void dispose_link(", "void internal_unlink_char(",
    "void unlink_char(", "void unlink_char_affect(P_char ch, struct affected_type *af)",
    "void clear_links(P_char ch, ush_int type)", "void clear_all_links(",
    "void linked_affect_to_char(",
)]
functions = link_functions + functions
registration = re.search(r'define_link\(LNK_TAUNT,.*?;',
                         extract_function("affects.c", "void initialize_links()"), re.S)
assert registration
functions.append("void initialize_taunt_link() { " + registration[0] + " }")
# Both ordinary extraction and direct character release must clear linked affects
# while the issuer is still intact, before strings/PC data or the character pool.
free = extract_function("db.c", "void free_char(")
assert free.index("clear_all_links(ch);") < free.index("str_free(ch->player.title)")
assert "clear_all_links(ch);" in extract_function("handler.c", "void extract_char(")

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
