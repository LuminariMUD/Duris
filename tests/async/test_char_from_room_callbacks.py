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
static int cleanup_calls, hook_calls, begin_calls, end_calls, shopkeeper_calls;
static P_char terminal_departure_override = nullptr, dummy_override = nullptr;
static bool dummy_guard;
enum Scenario { ordinary, handled, veto, redirected, nested_dummy_redirect, detached, removed, freed,
                reused, killed, already_dead, unrelated_removal, extraction_returned };
static Scenario scenario;

bool training_dummy_can_leave_room(P_char ch) { return !dummy_guard || dummy_override == ch; }
void training_dummy_begin_removal(P_char ch) { ++begin_calls; if (dummy_guard) dummy_override = ch; }
void training_dummy_end_removal(P_char ch) { ++end_calls; if (dummy_override == ch) dummy_override = nullptr; }
void shopkeeper_mob_extracted(P_char) { ++shopkeeper_calls; }
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
    ++hook_calls;
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
    case nested_dummy_redirect:
        // A nested extraction can clear the training-dummy removal override.
        if (scenario == nested_dummy_redirect) { ++character_removal_generation; dummy_override = nullptr; }
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

static void run_extraction(Scenario selected, bool npc)
{
    rooms[0] = {};
    rooms[1] = {};
    rooms[0].number = 100;
    rooms[1].number = 200;
    rooms[0].funct = room_hook;
    // A redirected character must not run a second room hook during teardown.
    rooms[1].funct = room_hook;
    auto *ch = new char_data{};
    ch->runtime_id = 1;
    ch->in_room = 0;
    ch->specials.act = npc ? ACT_ISNPC : 0;
    ch->specials.was_in_room = 777;
    ch->points.hit = ch->points.max_hit = 100;
    SET_POS(ch, selected == already_dead ? STAT_DEAD : STAT_NORMAL + POS_STANDING);
    character_list = rooms[0].people = ch;
    cleanup_calls = hook_calls = begin_calls = end_calls = shopkeeper_calls = 0;
    terminal_departure_override = dummy_override = nullptr;
    dummy_guard = selected == nested_dummy_redirect;
    scenario = selected;
    character_removal_generation = std::numeric_limits<uint64_t>::max();
    extraction_unlink_fixture(ch);

    const bool retried = selected == veto || selected == redirected ||
                         selected == nested_dummy_redirect || selected == killed;
    assert(begin_calls == (retried ? 2 : 1) && end_calls == 1 && hook_calls == 1);
    assert(dummy_override == nullptr);
    assert(terminal_departure_override == nullptr);
    if (selected == reused)
    {
        // Same-address replacement belongs to the hook, not this extraction.
        assert(ch->runtime_id == 2 && ch->in_room == 0);
        assert(rooms[0].people == ch && character_list == ch);
        assert(shopkeeper_calls == 0);
        delete ch;
    }
    else if (selected == freed)
    {
        // Real delete happened in the hook: ASan verifies no later dereference.
        assert(character_list == nullptr && rooms[0].people == nullptr);
        assert(shopkeeper_calls == 0);
    }
    else if (selected == removed)
    {
        // The callback already extracted the original; do not extract it twice.
        assert(character_list == nullptr && rooms[0].people == nullptr);
        assert(shopkeeper_calls == 0);
        delete ch;
    }
    else
    {
        assert(character_list == nullptr && ch->in_room == NOWHERE);
        assert(rooms[0].people == nullptr && rooms[1].people == nullptr);
        assert(ch->next_in_room == nullptr);
        assert(shopkeeper_calls == (npc ? 1 : 0));
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
    for (bool npc : {false, true})
        for (Scenario selected : {ordinary, handled, veto, redirected, nested_dummy_redirect,
                                  detached, removed, freed, reused, killed, already_dead,
                                  unrelated_removal, extraction_returned})
            run_extraction(selected, npc);
    char_from_room(nullptr);
    char_data detached_character{};
    detached_character.in_room = NOWHERE;
    char_from_room(&detached_character);
    std::puts("Room departure and terminal extraction: 50 PC/NPC callback cases passed");
}
'''

build_root = Path(os.environ.get("BIN_ROOT", ROOT / "bin")) / "tests"
build_root.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="char-from-room-", dir=build_root) as directory:
    harness = Path(directory) / "harness.cpp"
    binary = Path(directory) / "harness"
    extraction = extract_function("handler.c", "void extract_char(P_char ch)")
    start = extraction.index("\tconst uint64_t room_removal_before =")
    end = extraction.index("\tSET_POS(ch, GET_POS(ch) + STAT_DEAD);", start)
    # Exercise the real extraction teardown and global-list unlink, with unrelated
    # equipment, network and persistence services outside the focused fixture.
    unlink = "void extraction_unlink_fixture(P_char ch) {\nP_char k;\n" + extraction[start:end] + "\n}"
    harness.write_text("\n".join((
        PRELUDE,
        extract_function("utility.c", "int char_in_list(const P_char ch)"),
        "void char_from_room(P_char ch)\n" + function_body(
            source("handler.c").read_text(encoding="utf-8"),
            r"void\s+char_from_room\s*\(\s*P_char\s+ch\s*\)",
        ),
        unlink,
        DRIVER,
    )), encoding="utf-8")
    subprocess.run([
        "g++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
        "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-fno-pie", "-no-pie",
        f"-I{ROOT / 'src'}", str(harness), "-o", str(binary),
    ], cwd=ROOT, check=True)
    subprocess.run([str(binary)], cwd=ROOT, check=True)
