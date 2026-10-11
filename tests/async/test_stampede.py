#!/usr/bin/env python3
"""Execute stampede with its real stun/cooldown logic and controlled combat/RNG."""

import re
import subprocess
import tempfile
from pathlib import Path

from _paths import ROOT, extract_function, source


PRELUDE = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "cmd/interp.h"
#include "net/comm.h"
#include "magic/spells.h"
#include <cassert>
#include <cstring>
#include <string>

room_data rooms[2]{};
P_room world = rooms;
P_char character_list;
command_info cmd_info[MAX_CMD_LIST];
static P_char caster, target, bystander, tank;
static bool front = true, target_front = true, innate = true, save = false, miss = false;
static bool with_bystander = false, move_bystander = false, move_caster = false;
static int attacks, appearances, stop_calls, hit_roll = 1, auto_roll = 1;
static std::string output;
bool SanityCheck(P_char ch, const char *) { return ch != nullptr; }
bool has_innate(P_char ch, int id) {
    assert(id == INNATE_STAMPEDE);
    return ch == caster && innate;
}
int on_front_line(P_char ch) {
    if (ch == caster) return front;
    if (ch == target) return target_front;
    return true;
}
bool ac_can_see(P_char, P_char, bool) { return true; }
bool should_area_hit(P_char, P_char victim) {
    return victim == target || (with_bystander && victim == bystander);
}
int STAT_INDEX(int) { return 10; }
int number(int low, int high) {
    if (low == 1 && high == 100) return miss ? 100 : hit_roll;
    if (low == 0 && high == 9) return auto_roll;
    return low;
}
int dice(int, int) { return 50; }
bool NewSaves(P_char, int, int) { return save; }
void send_to_char(const char *text, P_char) { output += text; }
void act(const char *, int, P_char, P_obj, void *, int) {}
void appear(P_char, bool) { ++appearances; }
void CharWait(P_char, int) {}
void stop_fighting(P_char ch) { ++stop_calls; GET_OPPONENT(ch) = nullptr; }
// Stampede may only call this for idle targets, so it never replays
// combat-opening hooks (such as DragonCombat) on an existing fight. Its
// callbacks can move people, as a dragon's roar can make players flee.
void set_fighting(P_char ch, P_char opponent) {
    assert(!IS_FIGHTING(ch));
    ++attacks;
    GET_OPPONENT(ch) = opponent;
    if (move_bystander) bystander->in_room = 1;
    if (move_caster) caster->in_room = 1;
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
    ch->specials.position = STAT_NORMAL + POS_STANDING;
    ch->in_room = 0;
}
'''

DRIVER = r'''
// Both public routes must pass the interpreter's combat gate while fighting.
static void check_combat_gate() {
    REGISTRATIONS
    P_char ch = caster;
    for (int cmd : {CMD_STAMPEDE, CMD_INNATE}) {
        assert(cmd_info[cmd].command_pointer);
        assert(!(COMBAT_GATE));
    }
}

int main() {
    char_data player{}, victim{}, other{}, opponent{};
    caster = &player; target = &victim; bystander = &other; tank = &opponent;
    character_list = caster;
    caster->next = target; target->next = bystander; bystander->next = tank;
    caster->next_in_room = target; target->next_in_room = bystander;
    bystander->next_in_room = tank;
    rooms[0].people = caster;
    for (auto *ch : {caster, target, bystander, tank}) {
        ch->player.level = 30;
        GET_RACE(ch) = RACE_CENTAUR;
        ch->specials.position = STAT_NORMAL + POS_STANDING;
    }

    GET_OPPONENT(caster) = tank;
    check_combat_gate();
    GET_OPPONENT(caster) = nullptr;

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

    // A full stun breaks the engaged target's fight; stampede neither pulls
    // it onto the caster nor calls set_fighting to restore it.
    GET_OPPONENT(target) = tank;
    do_stampede(caster, nullptr, 0);
    assert(IS_AFFECTED2(target, AFF2_STUNNED));
    assert(stop_calls == 1 && attacks == 0 && !GET_OPPONENT(target));
    assert(caster->affected->type == TAG_INNATE_TIMER);
    assert(caster->affected->location == INNATE_STAMPEDE);
    assert(caster->affected->duration == 60 * WAIT_SEC);
    assert(caster->affected->modifier == 1);
    do_stampede(caster, nullptr, 0);
    assert(appearances == 1 && attacks == 0);
    assert(output.find("too winded") != std::string::npos);

    // Expiration allows another attempt. A miss or a resisted stun leaves
    // an engaged target on its existing opponent.
    for (bool avoid : {true, false}) {
        clear(caster); clear(target);
        GET_OPPONENT(target) = tank;
        miss = avoid; save = true;
        do_stampede(caster, nullptr, 0);
        assert(!IS_AFFECTED2(target, AFF2_STUNNED));
        assert(GET_OPPONENT(target) == tank && attacks == 0);
    }

    // Engaged and idle targets use the same hit threshold (40 here); only
    // the idle target starts fighting the caster.
    for (bool engaged : {true, false}) {
        clear(caster); clear(target);
        GET_OPPONENT(target) = engaged ? tank : nullptr;
        miss = false; save = false; hit_roll = 40;
        do_stampede(caster, nullptr, 0);
        assert(IS_AFFECTED2(target, AFF2_STUNNED));
        assert(GET_OPPONENT(target) == (engaged ? nullptr : caster));
    }
    assert(attacks == 1);

    // A back-ranked target dodges whether or not the automatic hit rolls.
    for (int roll : {0, 1}) {
        clear(caster); clear(target);
        GET_OPPONENT(target) = nullptr;
        target_front = false; auto_roll = roll;
        do_stampede(caster, nullptr, 0);
        assert(!IS_AFFECTED2(target, AFF2_STUNNED));
        assert(GET_POS(target) == POS_STANDING);
        GET_OPPONENT(target) = nullptr;
    }
    target_front = true; auto_roll = 1;

    // Combat callbacks that move a later candidate out of the room, or move
    // the caster, stop stampede from reaching anyone outside the room.
    with_bystander = true;
    for (bool caster_leaves : {false, true}) {
        clear(caster); clear(target); clear(bystander);
        GET_OPPONENT(target) = nullptr; GET_OPPONENT(bystander) = nullptr;
        move_bystander = !caster_leaves; move_caster = caster_leaves;
        do_stampede(caster, nullptr, 0);
        assert(IS_AFFECTED2(target, AFF2_STUNNED));
        assert(!IS_AFFECTED2(bystander, AFF2_STUNNED));
        assert(GET_POS(bystander) == POS_STANDING && !GET_OPPONENT(bystander));
    }
    clear(caster); clear(target); clear(bystander);
}
'''

innates = source("innates.c").read_text()
interp = source("interp.c").read_text()
assert '"stampede", do_stampede' in innates
assert "do_stampede(" not in source("mobact.c").read_text()

gate = "(IS_FIGHTING(ch) && !cmd_info[cmd].in_battle)"
assert gate in interp
macros = "\n".join(
    re.search(r"#define %s\(.*?\n\t}\n" % name, interp, re.S).group(0) for name in ("CMD_N", "CMD_Y")
)
registrations = "\n".join(
    re.search(r"^\s*CMD_\w+\(%s,.*$" % cmd, interp, re.M).group(0) for cmd in ("CMD_STAMPEDE", "CMD_INNATE")
)

production = "\n".join([
    macros,
    "void do_innate(P_char, char *, int) {}",
    extract_function("utility.c", "int BOUNDED("),
    extract_function("utility.c", "int char_in_list("),
    extract_function("innates.c", "bool check_innate_time("),
    extract_function("affects.c", "void Stun("),
    extract_function("actnew.c", "void do_stampede("),
])
driver = DRIVER.replace("REGISTRATIONS", registrations).replace("COMBAT_GATE", gate)
with tempfile.TemporaryDirectory(prefix="duris-stampede-") as directory:
    generated = Path(directory) / "stampede.cpp"
    binary = Path(directory) / "stampede"
    generated.write_text(PRELUDE + production + driver)
    subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
                    "-fsanitize=address,undefined", "-I" + str(ROOT / "src"),
                    str(generated), "-o", str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
print("Stampede commands, eligibility, cooldown, engaged combat, back rank and room changes passed.")
