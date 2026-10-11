#!/usr/bin/env python3
"""Execute stampede with its real stun/cooldown logic and controlled combat/RNG."""

import subprocess
import tempfile
from pathlib import Path

from _paths import ROOT, extract_function, source


PRELUDE = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "net/comm.h"
#include "magic/spells.h"
#include <cassert>
#include <cstring>
#include <string>

room_data rooms[2]{};
P_room world = rooms;
P_char character_list;
static P_char caster, target, tank;
static bool front = true, innate = true, save = false, miss = false;
static int attacks, appearances, stop_calls, hit_roll = 1;
static std::string output;
bool SanityCheck(P_char ch, const char *) { return ch != nullptr; }
bool has_innate(P_char ch, int id) {
    assert(id == INNATE_STAMPEDE);
    return ch == caster && innate;
}
int on_front_line(P_char ch) { return ch != caster || front; }
bool ac_can_see(P_char, P_char, bool) { return true; }
bool should_area_hit(P_char, P_char victim) { return victim == target; }
int STAT_INDEX(int) { return 10; }
int number(int low, int high) {
    if (low == 1 && high == 100) return miss ? 100 : hit_roll;
    if (low == 0 && high == 9) return 1;
    return low;
}
int dice(int, int) { return 50; }
bool NewSaves(P_char, int, int) { return save; }
void send_to_char(const char *text, P_char) { output += text; }
void act(const char *, int, P_char, P_obj, void *, int) {}
void appear(P_char, bool) { ++appearances; }
void CharWait(P_char, int) {}
void stop_fighting(P_char ch) { ++stop_calls; GET_OPPONENT(ch) = nullptr; }
void set_fighting(P_char ch, P_char opponent) {
    assert(!IS_FIGHTING(ch));
    ++attacks;
    GET_OPPONENT(ch) = opponent;
}
int get_property(const char *key, int fallback) {
    if (std::strcmp(key, "innate.timer.secs.stampede") == 0) assert(fallback == 60);
    return fallback;
}
int get_innate_property(int, const char *, int fallback) { return fallback; }
bool affected_by_spell(P_char ch, int type) {
    for (auto *af = ch->affected; af; af = af->next)
        if (af->type == type) return true;
    return false;
}
affected_type *affect_to_char(P_char ch, affected_type *af) {
    auto *copy = new affected_type(*af);
    copy->next = ch->affected;
    ch->affected = copy;
    ch->specials.affected_by2 |= copy->bitvector2;
    return copy;
}
static void clear(P_char ch) {
    while (ch->affected) {
        auto *af = ch->affected;
        ch->affected = af->next;
        delete af;
    }
    ch->specials.affected_by2 = 0;
}
'''

DRIVER = r'''
int main() {
    char_data player{}, victim{}, opponent{};
    caster = &player; target = &victim; tank = &opponent;
    character_list = caster;
    caster->next = target; target->next = tank;
    caster->next_in_room = target; target->next_in_room = tank;
    rooms[0].people = caster;
    for (auto *ch : {caster, target, tank}) {
        ch->player.level = 30;
        GET_RACE(ch) = RACE_CENTAUR;
        ch->specials.position = STAT_NORMAL + POS_STANDING;
    }

    // Rejected NPCs (including pets/charmies), missing innate and bad footing,
    // room width or rank must not spend the timer or reveal the actor.
    for (int blocked = 0; blocked < 5; ++blocked) {
        if (blocked == 0) caster->specials.act |= ACT_ISNPC;
        if (blocked == 1) innate = false;
        if (blocked == 2) rooms[0].sector_type = SECT_UNDERWATER;
        if (blocked == 3) rooms[0].room_flags |= ROOM_SINGLE_FILE;
        if (blocked == 4) front = false;
        do_stampede(caster, nullptr, 0);
        assert(!caster->affected && !attacks && !appearances);
        caster->specials.act = 0; innate = true; front = true;
        rooms[0].sector_type = SECT_INSIDE; rooms[0].room_flags = 0;
    }

    // Successful full stun breaks combat, then restores the prior tank.
    GET_OPPONENT(target) = tank;
    do_stampede(caster, nullptr, 0);
    assert(IS_AFFECTED2(target, AFF2_STUNNED));
    assert(stop_calls == 1 && attacks == 1 && GET_OPPONENT(target) == tank);
    assert(caster->affected->type == TAG_INNATE_TIMER);
    assert(caster->affected->location == INNATE_STAMPEDE);
    assert(caster->affected->duration == 60 * WAIT_SEC);
    assert(caster->affected->modifier == 1);
    do_stampede(caster, nullptr, 0);
    assert(appearances == 1 && attacks == 1);
    assert(output.find("too winded") != std::string::npos);

    // Expiration allows another attempt. A miss or a resisted stun must not
    // call set_fighting on an engaged target or steal its existing opponent.
    for (bool avoid : {true, false}) {
        clear(caster); clear(target);
        miss = avoid; save = true;
        do_stampede(caster, nullptr, 0);
        assert(!IS_AFFECTED2(target, AFF2_STUNNED));
        assert(GET_OPPONENT(target) == tank && attacks == 1);
    }

    // Engaged and idle targets use the same hit threshold (40 here).
    for (bool engaged : {true, false}) {
        clear(caster); clear(target);
        GET_OPPONENT(target) = engaged ? tank : nullptr;
        miss = false; save = false; hit_roll = 40;
        do_stampede(caster, nullptr, 0);
        assert(IS_AFFECTED2(target, AFF2_STUNNED));
        assert(GET_OPPONENT(target) == (engaged ? tank : caster));
    }
    clear(caster); clear(target);
}
'''

assert '"stampede", do_stampede' in source("innates.c").read_text()
assert "CMD_STAMPEDE, STAT_NORMAL + POS_STANDING, do_stampede" in source("interp.c").read_text()
assert "do_stampede(" not in source("mobact.c").read_text()

production = "\n".join([
    extract_function("utility.c", "int BOUNDED("),
    extract_function("utility.c", "int char_in_list("),
    extract_function("innates.c", "bool check_innate_time("),
    extract_function("affects.c", "void Stun("),
    extract_function("actnew.c", "void do_stampede("),
])
with tempfile.TemporaryDirectory(prefix="duris-stampede-") as directory:
    generated = Path(directory) / "stampede.cpp"
    binary = Path(directory) / "stampede"
    generated.write_text(PRELUDE + production + DRIVER)
    subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
                    "-fsanitize=address,undefined", "-I" + str(ROOT / "src"),
                    str(generated), "-o", str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
print("Stampede eligibility, cooldown, engaged hits and combat target preservation passed.")
