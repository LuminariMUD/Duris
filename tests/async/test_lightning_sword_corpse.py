#!/usr/bin/env python3
"""Lightning sword destroys only the corpse its own kill made.

Compile the production lightning_sword and its corpse finder with a die() fixture
that either files a fresh corpse (as make_corpse does) or makes none (arena players,
training dummies, reincarnation). An unrelated corpse already in the room must
survive the second case with its contents.
"""

from pathlib import Path
import os
import subprocess
import tempfile

from _paths import ROOT, HARNESS_STUBS, extract_function


PRELUDE = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "cmd/interp.h"
#include "magic/spells.h"
#include "net/comm.h"
#include "world/specs.prototypes.h"
#include <cassert>
#include <cstdio>

static room_data rooms[1]{};
P_room world = rooms;
int top_of_world = 0;
static index_data indexes[1]{};
P_index obj_index = indexes;
static char_data killer, victim;
static obj_data sword, old_corpse, old_item, new_corpse, new_item;
static bool die_makes_corpse;
static int extracted, chain_lightnings;

int number(int low, int) { return low; }
int dice(int count, int) { return count * 1000; }
int STAT_INDEX(int) { return 0; }
const str_app_type str_app[] = {{}};
void act(const char *, int, P_char, P_obj, void *, int) {}
void logit(const char *, const char *, ...) {}
void spell_haste(int, P_char, char *, int, P_char, P_obj) {}
void spell_chain_lightning(int, P_char, char *, int, P_char, P_obj) { ++chain_lightnings; }

static void put_in_room(P_obj o)
{
    o->loc_p = LOC_ROOM;
    o->loc.room = 0;
    o->next_content = world[0].contents;
    world[0].contents = o;
}
void obj_to_room(P_obj o, int) { put_in_room(o); }
void obj_from_obj(P_obj o)
{
    o->loc.inside->contains = o->next_content;
    o->next_content = nullptr;
}
void extract_obj(P_obj o, int)
{
    ++extracted;
    P_obj *link = &world[0].contents;
    while (*link != o) link = &(*link)->next_content;
    *link = o->next_content;
}
void die(P_char ch, P_char)
{
    ch->specials.position = STAT_DEAD;
    if (die_makes_corpse) put_in_room(&new_corpse);
}
'''

DRIVER = r'''
static void corpse_with_item(P_obj corpse, P_obj item)
{
    *corpse = obj_data{};
    *item = obj_data{};
    corpse->type = ITEM_CORPSE;
    corpse->short_description = (char *) "a corpse";
    item->loc_p = LOC_INSIDE;
    item->loc.inside = corpse;
    corpse->contains = item;
}

static void reset(bool makes_corpse)
{
    world[0] = room_data{};
    killer = char_data{};
    victim = char_data{};
    for (P_char ch : {&killer, &victim}) {
        ch->in_room = 0;
        ch->specials.position = POS_STANDING + STAT_NORMAL;
        ch->player.level = 50;
        ch->specials.damage_mod = 1.0;
        SET_BIT(ch->specials.act, ACT_ISNPC);
    }
    killer.specials.fighting = &victim;
    GET_HIT(&victim) = 1;
    sword = obj_data{};
    sword.loc_p = LOC_WORN;
    sword.loc.wearing = &killer;
    sword.value[1] = 1;
    sword.value[2] = 1;
    killer.equipment[WIELD] = &sword;
    corpse_with_item(&old_corpse, &old_item);
    corpse_with_item(&new_corpse, &new_item);
    put_in_room(&old_corpse);
    die_makes_corpse = makes_corpse;
    extracted = chain_lightnings = 0;
}

static bool in_room(P_obj o)
{
    for (P_obj it = world[0].contents; it; it = it->next_content)
        if (it == o) return true;
    return false;
}

int main()
{
    // The kill makes no corpse: the bystander's corpse and its item stay put.
    reset(false);
    lightning_sword(&sword, &killer, CMD_MELEE_HIT, (char *) &victim);
    assert(extracted == 0);
    assert(in_room(&old_corpse) && old_corpse.contains == &old_item);

    // The kill makes a corpse: only that one is emptied and destroyed.
    reset(true);
    assert(lightning_sword(&sword, &killer, CMD_MELEE_HIT, (char *) &victim));
    assert(extracted == 1 && !in_room(&new_corpse) && in_room(&new_item));
    assert(in_room(&old_corpse) && old_corpse.contains == &old_item);
    assert(chain_lightnings == 1);
    puts("lightning sword corpse regressions passed");
}
'''


def main():
    production = "\n".join([
        extract_function("specs/specs.object.c", "P_char melee_proc_target("),
        extract_function("specs/specs.undermountain.c", "static P_obj first_corpse_in_room(int room)"),
        extract_function("specs/specs.undermountain.c",
                         "int lightning_sword(P_obj obj, P_char ch, int cmd, char *arg)"),
    ])
    build = ROOT / "bin/tests"
    build.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="lightning-sword-", dir=build) as directory:
        cpp, binary = Path(directory) / "harness.cpp", Path(directory) / "harness"
        cpp.write_text(PRELUDE + production + DRIVER)
        subprocess.run([
            "g++", "-std=c++20", "-g", "-Wall", "-Wextra", "-Werror",
            "-Wno-unused-parameter", "-fsanitize=address,undefined",
            "-fno-omit-frame-pointer", "-fno-pie", "-no-pie",
            "-ffunction-sections", "-fdata-sections", "-I" + str(ROOT / "src"),
            str(cpp), str(HARNESS_STUBS), "-Wl,--gc-sections", "-o", str(binary),
        ], check=True)
        subprocess.run([str(binary)], check=True, env={**os.environ,
            "ASAN_OPTIONS": "detect_leaks=0:halt_on_error=1",
            "UBSAN_OPTIONS": "halt_on_error=1:print_stacktrace=1"})


if __name__ == "__main__":
    main()
