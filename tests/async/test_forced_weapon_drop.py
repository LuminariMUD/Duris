#!/usr/bin/env python3
"""Exercise the in-memory fumble and disarm drop."""

from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, SRC, extract_function, rel


makefile = (SRC / "Makefile").read_text(encoding="utf-8")
fight = (SRC / "fight.c").read_text(encoding="utf-8")
specs = (SRC / "specs.object.c").read_text(encoding="utf-8")

assert "item/forced_weapon_drop.o" in makefile
fumble = fight[fight.index("if (sic == 1") : fight.index("if (IS_GRAPPLED", fight.index("if (sic == 1"))]
critical = extract_function("fight.c", "bool critical_disarm(P_char ch, P_char victim)")
gauntlets = extract_function("specs.object.c", "int fumblegaunts(P_obj obj, P_char ch, int cmd")
for body in (fumble, critical, gauntlets):
    assert "forced_weapon_drop(" in body
assert "obj_to_room(weap" not in fumble
assert "obj_to_room(obj, victim->in_room)" not in critical
assert "obj_to_room(weap" not in gauntlets


harness = r'''
#include "core/utils.h"
#include "item/forced_weapon_drop.h"
#include "persistence/persistence_checkpoint.h"
#include "redis/redis_floor_runtime.h"

#include <cassert>
#include <cstdlib>
#include <string>
#include <vector>

room_data rooms[2] = {};
P_room world = rooms;
extern const int top_of_world = 1;

[[noreturn]] int panic_corruption_int(const char *, const char *, ...)
{
    std::abort();
}

static int floor_calls = 0;
static int dirty_calls = 0;
static int act_calls = 0;
static std::vector<std::string> recorded_messages;

P_obj unequip_char(P_char actor, int slot, bool)
{
    assert(actor && slot >= 0 && slot < MAX_WEAR);
    P_obj object = actor->equipment[slot];
    assert(object);
    actor->equipment[slot] = nullptr;
    object->loc_p = LOC_NOWHERE;
    object->loc.wearing = nullptr;
    return object;
}

void obj_to_room(P_obj object, int room)
{
    assert(object && OBJ_NOWHERE(object));
    object->loc_p = LOC_ROOM;
    object->loc.room = room;
}

void act(const char *message, int, P_char, P_obj, void *, int)
{
    ++act_calls;
    recorded_messages.emplace_back(message ? message : "");
}

int char_light(P_char)
{
    return 0;
}

int room_light(int, int)
{
    return 0;
}

void redis_log_floor_drop(P_obj, int)
{
    ++floor_calls;
}

void mark_player_dirty_components(int, player_component_mask_t)
{
    ++dirty_calls;
}

static pc_only_data player = {};
static char_data actor = {};
static obj_data weapon = {};

static void reset(bool actor_is_npc = false)
{
    floor_calls = 0;
    dirty_calls = 0;
    act_calls = 0;
    recorded_messages.clear();
    rooms[0] = {};
    rooms[1] = {};
    rooms[0].number = 100;
    rooms[1].number = 200;
    player = {};
    player.pid = 42;
    actor = {};
    actor.only.pc = &player;
    actor.in_room = 0;
    actor.player.level = 20;
    if (actor_is_npc)
        SET_BIT(actor.specials.act, ACT_ISNPC);
    weapon = {};
    weapon.obj_uid = 9001;
    weapon.type = ITEM_WEAPON;
    weapon.loc_p = LOC_WORN;
    weapon.loc.wearing = &actor;
    actor.equipment[WIELD] = &weapon;
}

int main()
{
    // Memory is the authority: a player's fumbled weapon lands on the floor at once,
    // and the player's next save no longer holds it.
    reset();
    assert(forced_weapon_drop(&actor, &weapon, forced_weapon_drop_cause::combat_fumble) ==
           forced_weapon_drop_result::dropped);
    assert(OBJ_ROOM(&weapon) && weapon.loc.room == 0 && !actor.equipment[WIELD]);
    assert(floor_calls == 1 && dirty_calls == 1 && act_calls == 2);

    // A disarm announces nothing itself; the caller does.
    reset();
    assert(forced_weapon_drop(&actor, &weapon, forced_weapon_drop_cause::critical_disarm) ==
           forced_weapon_drop_result::dropped);
    assert(OBJ_ROOM(&weapon) && act_calls == 0);

    // A mobile's weapon drops too; it has no save to mark.
    reset(true);
    assert(forced_weapon_drop(&actor, &weapon, forced_weapon_drop_cause::combat_fumble) ==
           forced_weapon_drop_result::dropped);
    assert(OBJ_ROOM(&weapon) && floor_calls == 0 && dirty_calls == 0);

    // A weapon the actor is not wielding, or an actor nowhere, is refused.
    reset();
    obj_data other = {};
    assert(forced_weapon_drop(&actor, &other, forced_weapon_drop_cause::combat_fumble) ==
           forced_weapon_drop_result::rejected);
    reset();
    actor.in_room = NOWHERE;
    assert(forced_weapon_drop(&actor, &weapon, forced_weapon_drop_cause::combat_fumble) ==
           forced_weapon_drop_result::rejected);
    assert(OBJ_WORN_BY(&weapon, &actor) && floor_calls == 0);
    return 0;
}
'''


with tempfile.TemporaryDirectory(prefix="duris-forced-weapon-drop-") as directory:
    test_source = Path(directory) / "forced_weapon_drop.cpp"
    binary = Path(directory) / "forced_weapon_drop"
    test_source.write_text(harness, encoding="utf-8")
    subprocess.run(
        [
            "g++",
            "-std=c++20",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-fsanitize=address,undefined",
            "-fno-omit-frame-pointer",
            "-ffunction-sections",
            "-fdata-sections",
            "-Isrc",
            str(test_source),
            rel("item/forced_weapon_drop.c"),
            "-Wl,--gc-sections",
            "-o",
            str(binary),
        ],
        cwd=ROOT,
        check=True,
    )
    subprocess.run([str(binary)], check=True, timeout=5)

print("forced weapon drop regressions passed")
