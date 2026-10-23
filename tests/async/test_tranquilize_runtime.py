#!/usr/bin/env python3
"""Tranquilize stops incoming attacks even when its target is not fighting back."""
from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, extract_function

harness = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "net/comm.h"
#include <cassert>
#include <cstdio>

static room_data rooms[1] = {};
P_room world = rooms;
static int memory_clears = 0;
static P_char slept = nullptr;

void stop_fighting(P_char ch) {
    assert(GET_OPPONENT(ch));
    ch->specials.fighting = nullptr;
}
void clearMemory(P_char) { ++memory_clears; }
void act(const char *, int, P_char, P_obj, void *, int) {}
void do_sleep(P_char ch, char *, int) { slept = ch; }
''' + extract_function("actwiz.c", "void tranquilize(P_char ch, P_char victim)") + r'''
int main() {
    char_data staff{}, target{}, attacker{}, second_attacker{}, unrelated{}, other{};
    staff.player.level = OVERLORD;
    target.player.level = 30;
    target.in_room = 0;
    rooms[0].people = &target;
    target.next_in_room = &attacker;
    attacker.next_in_room = &second_attacker;
    second_attacker.next_in_room = &unrelated;
    unrelated.next_in_room = &other;

    // A missed same-room throw engages its victim before the thrower has an opponent.
    attacker.specials.fighting = &target;
    second_attacker.specials.fighting = &target;
    unrelated.specials.fighting = &other;
    tranquilize(&staff, &target);
    assert(!attacker.specials.fighting && !second_attacker.specials.fighting);
    assert(!target.specials.fighting);
    assert(unrelated.specials.fighting == &other);
    assert(memory_clears == 2 && slept == &target);

    // Mutual combat and additional incoming attackers must all stop too.
    target.specials.fighting = &attacker;
    attacker.specials.fighting = &target;
    second_attacker.specials.fighting = &target;
    memory_clears = 0;
    slept = nullptr;
    tranquilize(&staff, &target);
    assert(!target.specials.fighting && !attacker.specials.fighting);
    assert(!second_attacker.specials.fighting);
    assert(unrelated.specials.fighting == &other);
    assert(memory_clears == 3 && slept == &target);

    // The existing level restriction still refuses a non-staff lower-level caller.
    staff.player.level = 20;
    attacker.specials.fighting = &target;
    memory_clears = 0;
    slept = nullptr;
    tranquilize(&staff, &target);
    assert(attacker.specials.fighting == &target);
    assert(memory_clears == 0 && slept == nullptr);
    tranquilize(&staff, nullptr);
    puts("tranquilize clears one-sided and mutual combat without disturbing other fights");
}
'''

with tempfile.TemporaryDirectory(prefix="duris-tranquilize-") as directory:
    work = Path(directory)
    source, binary = work / "test.cpp", work / "test"
    source.write_text(harness)
    subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-Isrc",
                    str(source), "-o", str(binary)], cwd=ROOT, check=True)
    subprocess.run([str(binary)], cwd=work, check=True)

