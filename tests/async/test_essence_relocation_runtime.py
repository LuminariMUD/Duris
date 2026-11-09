#!/usr/bin/env python3
"""Exercise Essence relocation cancellation with production movement/link code.

Room departure, entry guards/insertion/cancellation, riding transport, walking
departure/recovery, teleport_to, forced single/pair moves and link teardown are
production code. The entry tail (display, hazards and aggro), allocator and
unrelated services are fixtures. Walking models the real two placement passes;
source checks ensure only those calls opt out of relocation cancellation.
"""

import re
import subprocess
import tempfile
from pathlib import Path

from _paths import ROOT, extract_function, source
from _source_contract import function_body


PRELUDE = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "core/mm.h"
#include "cmd/interp.h"
#include "magic/spells.h"
#include "combat/training_dummy.h"
#include "combat/forced_movement.h"
#include "item/item_actions.h"
#include "world/db.h"
#include "net/gmcp.h"
#include "net/comm.h"
#include "abilities/abilities.h"
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <algorithm>

static room_data rooms[4];
P_room world = rooms;
P_index mob_index = nullptr;
extern const int top_of_world = 3;
static zone_data zones[1];
zone_data *zone_table = zones;
static room_direction_data north;
const int rev_dir[] = {2, 3, 0, 1, 5, 4, 9, 8, 7, 6};
uint64_t character_removal_generation = 0;
static char_data caster, recipient, third;
P_char character_list = nullptr;
static P_char terminal_departure_override = nullptr;
static P_char denied_entry = nullptr, hooked = nullptr;
enum class Hook { none, veto, seal, redirect, remove };
static Hook leave_hook;
static int essence_messages;
static bool redirect_arrival;
static mm_ds link_pool;
mm_ds *dead_link_pool = nullptr;
link_description link_types[LNK_MAX + 1];

mm_ds *mm_create(const char *, size_t size, size_t, unsigned) {
    link_pool.size = size; return &link_pool;
}
void *_mm_get(mm_ds *pool, const char *, int) { return std::calloc(1, pool->size); }
void mm_release(mm_ds *, void *link) { std::free(link); }
void affect_remove(P_char, affected_type *) { assert(false); }
void wear_off_message(P_char, affected_type *) { assert(false); }
void logit(const char *, const char *, ...) {}
void wizlog(int, const char *, ...) {}
int panic_corruption_int(const char *, const char *, ...) { std::abort(); }
void act(const char *, int, P_char, P_obj, void *, int) { ++essence_messages; }
void send_to_char(const char *, P_char) {}
bool training_dummy_can_leave_room(P_char) { return true; }
bool training_dummy_can_enter_room(P_char ch) { return ch != denied_entry; }
void event_conjure_water(P_char, P_char, P_obj, void *) {}
void event_water_crossing(P_char, P_char, P_obj, void *) {}
void disarm_char_nevents(P_char, event_func_type) {}
void item_actions_character_leaving(P_char) {}
void gmcp_mark_room_dirty(int) {}
void DelCharFromZone(P_char) {}
void StopCasting(P_char) {}
int char_light(P_char) { return 0; }
int room_light(int, int) { return 0; }
void make_bloodstain(P_char) {}
int real_room0(int vnum) { assert(vnum >= 100 && vnum < 104); return vnum - 100; }
bool check_castle_walls(int, int) { return false; }
int check_wall(int, int) { return false; }
int number(int low, int) { return low; }
int dice(int, int) { return 1; }
const Rolls live_rolls = {dice, number};
int char_in_list(const P_char ch) {
    for (P_char current = character_list; current; current = current->next)
        if (current == ch) return true;
    return false;
}
P_char find_character_by_runtime_id(uint64_t id) {
    for (P_char ch = character_list; ch; ch = ch->next)
        if (ch->runtime_id == id) return ch;
    return nullptr;
}
void extract_char(P_char ch) { clear_all_links(ch); ch->in_room = NOWHERE; }

static int room_hook(int, P_char ch, int cmd, char *) {
    assert(cmd == CMD_FROMROOM);
    if (ch != hooked) return false;
    const Hook selected = leave_hook;
    leave_hook = Hook::none;
    if (selected == Hook::veto) return ROOM_PROC_LEAVE_VETO;
    if (selected == Hook::seal) north.exit_info = EX_CLOSED | EX_LOCKED | EX_PICKPROOF;
    if (selected == Hook::redirect) {
        char_from_room(ch);
        assert(char_to_room(ch, 3, -2));
    }
    if (selected == Hook::remove) {
        char_from_room(ch);
        clear_all_links(ch);
        SET_POS(ch, STAT_DEAD);
    }
    return false;
}
'''

DRIVER = r'''
static void place_fixture(P_char ch, int room) {
    ch->in_room = room;
    ch->specials.was_in_room = rooms[room].number;
    ch->next_in_room = rooms[room].people;
    rooms[room].people = ch;
}

static void reset() {
    for (P_char ch : {&caster, &recipient, &third}) clear_all_links(ch);
    caster = {}; recipient = {}; third = {};
    for (auto &room : rooms) room = {};
    for (int i = 0; i < 4; ++i) {
        rooms[i].number = 100 + i;
        rooms[i].funct = room_hook;
        rooms[i].sector_type = SECT_FIELD;
    }
    north = {}; north.to_room = 1;
    rooms[0].dir_option[DIR_NORTH] = &north;
    caster.next = &recipient; recipient.next = &third; character_list = &caster;
    uint64_t id = 0;
    for (P_char ch : {&caster, &recipient, &third}) {
        ch->runtime_id = ++id;
        ch->player.level = 50;
        ch->points.hit = ch->points.max_hit = 100;
        SET_POS(ch, STAT_NORMAL + POS_STANDING);
        place_fixture(ch, 0);
    }
    denied_entry = hooked = nullptr; leave_hook = Hook::none; redirect_arrival = false;
    link_char(&caster, &recipient, LNK_ESSENCE_OF_WOLF);
    essence_messages = 0;
}

static void linked(bool expected) {
    assert(bool(get_linked_char(&caster, LNK_ESSENCE_OF_WOLF)) == expected);
    assert(bool(get_linking_char(&recipient, LNK_ESSENCE_OF_WOLF)) == expected);
    assert(bonus_attacks(&recipient) == (expected ? 2 : 0));
}

static bool walk(P_char ch, int destination) {
    const int source = ch->in_room;
    north.to_room = destination;
    rooms[source].dir_option[DIR_NORTH] = &north;
    check_room_links(ch, source, destination);
    if (!leave_walking_group(ch, destination, DIR_NORTH)) return false;
    if (!char_to_room(ch, destination, -2, true)) return false;
    char_from_room(ch); // The production visibility pass precedes final placement.
    ch->specials.was_in_room = rooms[source].number;
    return char_to_room(ch, destination, DIR_NORTH, true);
}

int main() {
    define_link(LNK_ESSENCE_OF_WOLF, "ESSENCE", essence_broken, LNKFLG_ROOM | LNKFLG_EXCLUSIVE);
    define_link(LNK_RIDING, "RIDING", nullptr, LNKFLG_EXCLUSIVE);
    define_link(LNK_GUARDING, "GUARDING", nullptr, LNKFLG_ROOM);
    define_link(LNK_CONSENT, "CONSENT", nullptr, LNKFLG_EXCLUSIVE);

    // Both endpoints retain the first step and reunion, and lose the second step away.
    for (P_char mover : {&caster, &recipient}) {
        reset(); linked(true);
        assert(walk(mover, 1)); linked(true);
        assert(walk(mover, 0)); linked(true);
        assert(walk(mover, 1)); linked(true);
        assert(walk(mover, 2)); linked(false);
    }
    // Followers can reunite after staggered walking, just as before.
    reset(); assert(walk(&recipient, 1)); assert(walk(&caster, 1)); linked(true);

    // The dir argument is not a travel classification: all legacy callers cancel.
    for (P_char mover : {&caster, &recipient})
        for (int direction : {-2, -1, DIR_NORTH}) {
            reset();
            char_from_room(mover); linked(true); // Temporary NOWHERE isn't separation.
            assert(char_to_room(mover, 1, direction)); linked(false);
            assert(essence_messages == 2);
            assert(walk(mover, 0)); linked(false); // Reunion never recreates a broken link.
        }
    for (P_char mover : {&caster, &recipient}) for (int destination : {1, 3}) {
        reset(); teleport_to(mover, destination, 0); linked(false);
        assert(mover->in_room == destination);
    }
    reset(); teleport_to(&recipient, NOWHERE, 0); linked(true);

    // Single and pair forced movement both use the default cancellation boundary.
    for (P_char mover : {&caster, &recipient}) {
        reset();
        assert(move_forced(&third, mover, DIR_NORTH, [] {}).status == forced_move_status::arrived);
        linked(false);
    }
    reset();
    assert(move_forced_pair(&caster, &recipient, DIR_NORTH, [] {}).status == forced_move_status::arrived);
    assert(caster.in_room == 1 && recipient.in_room == 1); linked(false);
    reset(); teleport_to(&recipient, 3, 0); teleport_to(&caster, 3, 0); linked(false);

    // Rider and mount placements inherit only the current placement's exemption.
    for (bool essence_on_mount : {false, true}) for (bool ordinary : {false, true}) {
        reset();
        P_char mover = essence_on_mount ? &third : &recipient;
        P_char companion = essence_on_mount ? &recipient : &third;
        link_char(mover, companion, LNK_RIDING);
        if (ordinary) assert(walk(mover, 1));
        else teleport_to(mover, 1, 0);
        assert(mover->in_room == 1 && companion->in_room == 1);
        assert(GET_MOUNT(mover) == companion);
        linked(ordinary);
    }

    // Cancellation does not touch unrelated room-scoped or exclusive links.
    reset();
    link_char(&recipient, &third, LNK_GUARDING);
    link_char(&third, &recipient, LNK_GUARDING);
    link_char(&recipient, &third, LNK_CONSENT);
    teleport_to(&recipient, 3, 0); linked(false);
    assert(get_linked_char(&recipient, LNK_GUARDING) == &third);
    assert(get_linking_char(&recipient, LNK_GUARDING) == &third);
    assert(get_linked_char(&recipient, LNK_CONSENT) == &third);

    // A recipient can also lend Essence onward: relocating them ends both links.
    reset(); link_char(&recipient, &third, LNK_ESSENCE_OF_WOLF);
    teleport_to(&recipient, 1, 0); linked(false);
    assert(!get_linked_char(&recipient, LNK_ESSENCE_OF_WOLF));
    assert(!get_linking_char(&third, LNK_ESSENCE_OF_WOLF));
    assert(bonus_attacks(&third) == 0);

    // No room change, refused insertion, departure veto and source recovery retain it.
    reset(); assert(!char_to_room(&recipient, 1, -2)); linked(true);
    reset(); denied_entry = &recipient;
    char_from_room(&recipient); assert(!char_to_room(&recipient, 1, -2)); linked(true);
    denied_entry = nullptr; assert(char_to_room(&recipient, 0, -2)); linked(true);
    reset(); char_from_room(&recipient); assert(char_to_room(&recipient, 0, -2)); linked(true);
    for (Hook hook : {Hook::veto, Hook::seal}) {
        reset(); hooked = &recipient; leave_hook = hook;
        assert(move_forced(&third, &recipient, DIR_NORTH, [] {}).status != forced_move_status::arrived);
        assert(recipient.in_room == 0); linked(true);
    }
    // An ordinary departure can be redirected by a nonordinary nested transfer.
    for (Hook hook : {Hook::redirect, Hook::remove}) {
        reset(); hooked = &recipient; leave_hook = hook;
        assert(!walk(&recipient, 1)); linked(false);
        assert(recipient.in_room == (hook == Hook::redirect ? 3 : NOWHERE));
    }
    reset(); redirect_arrival = true;
    assert(!walk(&recipient, 1)); assert(recipient.in_room == 3); linked(false);
    // Mounted failed walking restores detached survivors without canceling Essence.
    reset(); link_char(&recipient, &third, LNK_RIDING);
    hooked = &third; leave_hook = Hook::veto;
    assert(!walk(&recipient, 1));
    assert(recipient.in_room == 0 && third.in_room == 0); linked(true);

    for (P_char ch : {&caster, &recipient, &third}) clear_all_links(ch);
    std::puts("Essence relocation: walking, teleport, forced/pair, riding, veto/recovery, redirect and link isolation passed");
}
'''


entry = extract_function("handler.c", "bool char_to_room(P_char ch, int room, int dir, bool")
# Keep every guard, the real room-list insertion and the cancellation in order.
# Display/hazard/aggro processing is outside this focused boundary fixture.
entry = entry[:entry.index("\n\tif ((was_in_arena !=")]
entry += r'''
    if (!move_riding_companions(ch, room, dir, ordinary_movement)) return false;
    if (redirect_arrival && ch == &recipient) {
        redirect_arrival = false;
        char_from_room(ch);
        assert(char_to_room(ch, 3, -2));
        return false;
    }
    return true;
}
'''

functions = [extract_function(file, signature) for file, signature in (
    ("smagic.c", "void essence_broken("),
    ("affects.c", "void define_link("),
    ("affects.c", "struct char_link_data *link_char_with_affect("),
    ("affects.c", "struct char_link_data *link_char("),
    ("affects.c", "P_char get_linked_char("),
    ("affects.c", "P_char get_linking_char("),
    ("affects.c", "void dispose_link("),
    ("affects.c", "void internal_unlink_char("),
    ("affects.c", "void unlink_char("),
    ("affects.c", "void clear_links(P_char ch, ush_int type)"),
    ("affects.c", "void clear_all_links("),
    ("affects.c", "void check_room_links("),
)]
functions += ["void char_from_room(P_char ch)\n" + function_body(
    source("handler.c").read_text(encoding="utf-8"), r"void\s+char_from_room\s*\(\s*P_char\s+ch\s*\)"),
    extract_function("handler.c", "static bool move_riding_companions(")]
functions += [entry, extract_function("handler.c", "bool char_to_room(P_char ch, int room, int dir)"),
              extract_function("actmove.c", "static bool walking_door_allows("),
              extract_function("actmove.c", "static bool leave_walking_group("),
              extract_function("magic.c", "void teleport_to(")]
functions += [extract_function("fight.c", f"int {name}(") for name in (
    "essence_of_wolf_attacks", "essence_of_wolf_attack_cap", "essence_of_wolf_offhand_roll")]
attacks = extract_function("fight.c", "int calculate_attacks(")
bonus = attacks[attacks.index("\tif (get_linking_char(ch, LNK_ESSENCE_OF_WOLF))"):]
bonus = bonus[:bonus.index("\n\t// This is a reaver-only")]
functions += ["int bonus_attacks(P_char ch) { int attacks = 0;\n#define ADD_ATTACK(slot) ++attacks\n"
              + bonus + "\n#undef ADD_ATTACK\nreturn attacks; }"]

# Keep the production routing tied to the executable boundary cases above.
walking = extract_function("actmove.c", "int do_simple_move_skipping_procs(")
assert "check_room_links(ch, was_in, new_room);" in walking
assert re.findall(r"char_to_room\(ch, new_room, ([^)]*)\)", walking) == [
    "-2, true", "exitnumb, true"]
assert "char_to_room(current, source, -2, true)" in extract_function(
    "actmove.c", "static bool leave_walking_group(")

build_root = ROOT / "bin/tests"
build_root.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="essence-relocation-", dir=build_root) as directory:
    harness, binary = Path(directory) / "harness.cpp", Path(directory) / "harness"
    harness.write_text(PRELUDE + "\n".join(functions) + DRIVER, encoding="utf-8")
    subprocess.run([
        "g++", "-std=c++20", "-g", "-fsanitize=address,undefined",
        "-fno-sanitize-recover=undefined", "-fno-omit-frame-pointer", "-fno-pie", "-no-pie",
        "-ffunction-sections", "-fdata-sections", f"-I{ROOT / 'src'}", str(harness),
        str(ROOT / "src/combat/forced_movement.c"), "-Wl,--gc-sections", "-o", str(binary),
    ], cwd=ROOT, check=True)
    subprocess.run([str(binary)], cwd=ROOT, check=True)
