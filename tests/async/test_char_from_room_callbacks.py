#!/usr/bin/env python3
"""Run production room departure bookkeeping against callback lifetime changes."""

import os
import subprocess
import tempfile
from pathlib import Path

from _paths import ROOT, extract_function, source
from _source_contract import function_body


PRELUDE = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "cmd/interp.h"
#include "combat/training_dummy.h"
#include "item/item_actions.h"
#include "net/gmcp.h"
#include "world/db.h"
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <initializer_list>
#include <limits>
#include <new>

static room_data rooms[2];
P_room world = rooms;
P_char character_list = nullptr;
uint64_t character_removal_generation = 0;
static int cleanup_calls;
enum Scenario { ordinary, handled, veto, redirected, detached, removed, freed,
                reused, killed, already_dead, unrelated_removal, extraction_returned };
static Scenario scenario;

bool training_dummy_can_leave_room(P_char) { return true; }
void logit(const char *, const char *, ...) { assert(false); }
int panic_corruption_int(const char *, const char *, ...) { std::abort(); }
void event_conjure_water(P_char, P_char, P_obj, void *) {}
void event_water_crossing(P_char, P_char, P_obj, void *) {}
void disarm_char_nevents(P_char, event_func_type) { ++cleanup_calls; }
void item_actions_character_leaving(P_char) { ++cleanup_calls; }
void gmcp_mark_room_dirty(int) { ++cleanup_calls; }
void DelCharFromZone(P_char) { ++cleanup_calls; }
void StopCasting(P_char) { ++cleanup_calls; }
int char_light(P_char) { ++cleanup_calls; return 0; }
int room_light(int, int) { ++cleanup_calls; return 0; }
void make_bloodstain(P_char) { ++cleanup_calls; }

static int room_hook(int room, P_char ch, int cmd, char *)
{
    assert(room == 0 && cmd == CMD_FROMROOM);
    switch (scenario)
    {
    case ordinary:
    case already_dead:
        return false;
    case handled:
        return true; // Legacy handled events are not an explicit leave veto.
    case veto:
        return ROOM_PROC_LEAVE_VETO;
    case redirected:
        rooms[0].people = nullptr;
        rooms[1].people = ch;
        ch->in_room = 1;
        return false;
    case detached:
        rooms[0].people = nullptr;
        ch->in_room = NOWHERE;
        return false;
    case removed:
    case freed:
        ++character_removal_generation;
        character_list = rooms[0].people = nullptr;
        if (scenario == freed)
            delete ch;
        return false;
    case reused:
        ++character_removal_generation;
        ch->~char_data();
        new (ch) char_data{};
        ch->runtime_id = 2;
        ch->in_room = 0;
        SET_POS(ch, STAT_NORMAL + POS_STANDING);
        return false;
    case killed:
        SET_POS(ch, STAT_DEAD);
        return false;
    case unrelated_removal:
        ++character_removal_generation;
        ch->next = nullptr;
        return false;
    case extraction_returned:
        ++character_removal_generation; // Removal entry may return without removing.
        return false;
    }
    std::abort();
}
'''

DRIVER = r'''
static void run(Scenario selected, bool npc)
{
    rooms[0] = {};
    rooms[1] = {};
    rooms[0].number = 100;
    rooms[1].number = 200;
    rooms[0].funct = room_hook;
    auto *ch = new char_data{};
    char_data other{};
    ch->runtime_id = 1;
    ch->in_room = 0;
    ch->specials.act = npc ? ACT_ISNPC : 0;
    ch->specials.was_in_room = 777;
    ch->points.hit = ch->points.max_hit = 100;
    SET_POS(ch, selected == already_dead ? STAT_DEAD : STAT_NORMAL + POS_STANDING);
    ch->next = &other;
    character_list = rooms[0].people = ch;
    cleanup_calls = 0;
    scenario = selected;
    character_removal_generation = std::numeric_limits<uint64_t>::max();
    char_from_room(ch);

    const bool completed = selected == ordinary || selected == handled ||
                           selected == already_dead || selected == unrelated_removal ||
                           selected == extraction_returned;
    assert((cleanup_calls > 0) == completed);
    if (selected != freed)
    {
        if (completed)
        {
            assert(ch->in_room == NOWHERE);
            assert(ch->specials.was_in_room == 100);
            assert(ch->next_in_room == nullptr);
            assert(rooms[0].people == nullptr);
        }
        else if (selected == redirected)
        {
            assert(ch->in_room == 1 && rooms[1].people == ch);
            assert(ch->specials.was_in_room == 777);
        }
        else if (selected == detached)
        {
            assert(ch->in_room == NOWHERE && rooms[0].people == nullptr);
            assert(ch->specials.was_in_room == 777);
        }
        else if (selected == reused)
        {
            assert(ch->runtime_id == 2 && ch->in_room == 0);
            assert(rooms[0].people == ch);
        }
        else if (selected != removed)
        {
            assert(ch->in_room == 0 && rooms[0].people == ch);
            assert(ch->specials.was_in_room == 777);
        }
        delete ch;
    }
    character_list = rooms[0].people = rooms[1].people = nullptr;
}

int main()
{
    for (bool npc : {false, true})
        for (Scenario selected : {ordinary, handled, veto, redirected, detached,
                                  removed, freed, reused, killed, already_dead,
                                  unrelated_removal, extraction_returned})
            run(selected, npc);
    char_from_room(nullptr);
    char_data detached_character{};
    detached_character.in_room = NOWHERE;
    char_from_room(&detached_character);
    std::puts("char_from_room callbacks: 24 PC/NPC lifetime and redirect cases passed");
}
'''

build_root = Path(os.environ.get("BIN_ROOT", ROOT / "bin")) / "tests"
build_root.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="char-from-room-", dir=build_root) as directory:
    harness = Path(directory) / "harness.cpp"
    binary = Path(directory) / "harness"
    harness.write_text("\n".join((
        PRELUDE,
        extract_function("utility.c", "int char_in_list(const P_char ch)"),
        "void char_from_room(P_char ch)\n" + function_body(
            source("handler.c").read_text(encoding="utf-8"),
            r"void\s+char_from_room\s*\(\s*P_char\s+ch\s*\)",
        ),
        DRIVER,
    )), encoding="utf-8")
    subprocess.run([
        "g++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
        "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-fno-pie", "-no-pie",
        f"-I{ROOT / 'src'}", str(harness), "-o", str(binary),
    ], cwd=ROOT, check=True)
    subprocess.run([str(binary)], cwd=ROOT, check=True)
