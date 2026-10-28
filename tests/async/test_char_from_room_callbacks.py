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
#include <algorithm>
#include <vector>

static room_data rooms[2];
P_room world = rooms;
P_char character_list = nullptr;
uint64_t character_removal_generation = 0;
static int cleanup_calls, hook_calls, begin_calls, end_calls, shopkeeper_calls;
static P_char terminal_departure_override = nullptr, dummy_override = nullptr;
static bool dummy_guard;
static int follower_cleanup_calls, group_cleanup_calls, link_cleanup_calls;
static int combat_cleanup_calls, event_cleanup_calls;
static char_data peer, incoming_follower;
static follow_type outgoing_follow, incoming_follow;
static char_link_data outgoing_guard, incoming_guard;
static group_list recreated_group;
static nevent_data recreated_event;
static index_data object_indices[1], mob_indices[1];
P_index obj_index = object_indices, mob_index = mob_indices;
static obj_data initial_carried, initial_equipped, initial_linked;
static obj_data callback_carried, callback_extra_carried, callback_equipped, callback_linked;
static std::vector<P_obj> extracted_items;
static bool transient_items;

P_char combat_list = nullptr;
P_char combat_next_ch = nullptr;
enum Scenario { ordinary, handled, veto, redirected, nested_dummy_redirect, detached, removed, freed,
                reused, killed, already_dead, unrelated_removal, extraction_returned,
                recreated_same_room, recreated_redirected, recreated_detached,
                recreated_dead, incoming_combat_only,
                inventory_same_room, inventory_redirected, inventory_detached };
static Scenario scenario;

bool training_dummy_can_leave_room(P_char ch) { return !dummy_guard || dummy_override == ch; }
void training_dummy_begin_removal(P_char ch) { ++begin_calls; if (dummy_guard) dummy_override = ch; }
void training_dummy_end_removal(P_char ch) { ++end_calls; if (dummy_override == ch) dummy_override = nullptr; }
void shopkeeper_mob_extracted(P_char) { ++shopkeeper_calls; }
void logit(const char *, const char *, ...) { assert(false); }
int panic_corruption_int(const char *, const char *, ...) { std::abort(); }
void event_conjure_water(P_char, P_char, P_obj, void *) {}
void event_water_crossing(P_char, P_char, P_obj, void *) {}
void disarm_char_nevents(P_char ch, event_func_type func)
{
    ++cleanup_calls;
    if (!func) { ++event_cleanup_calls; ch->nevents = ch->nevents_tail = nullptr; }
}
void die_follower(P_char ch)
{
    ++follower_cleanup_calls;
    if (ch->following) ch->following->followers = nullptr;
    ch->following = nullptr;
    if (ch->followers) ch->followers->follower->following = nullptr;
    ch->followers = nullptr;
}
bool group_remove_member(P_char ch)
{
    ++group_cleanup_calls;
    ch->group = nullptr;
    return true;
}
void clear_all_links(P_char ch)
{
    ++link_cleanup_calls;
    if (ch->linking) ch->linking->linked->linked = nullptr;
    if (ch->linked) ch->linked->linking->linking = nullptr;
    ch->linking = ch->linked = nullptr;
}
void stop_fighting(P_char ch)
{
    // Ordinary combat teardown requires a living character placed in a room.
    assert(IS_ALIVE(ch) && ch->in_room != NOWHERE);
    ++combat_cleanup_calls;
    P_char *cursor = &combat_list;
    while (*cursor && *cursor != ch) cursor = &(*cursor)->specials.next_fighting;
    assert(*cursor == ch);
    *cursor = ch->specials.next_fighting;
    if (combat_next_ch == ch) combat_next_ch = ch->specials.next_fighting;
    ch->specials.next_fighting = nullptr;
    GET_OPPONENT(ch) = nullptr;
}
void item_actions_character_leaving(P_char) { ++cleanup_calls; }
void gmcp_mark_room_dirty(int) { ++cleanup_calls; }
void DelCharFromZone(P_char) { ++cleanup_calls; }
void StopCasting(P_char) { ++cleanup_calls; }
int char_light(P_char) { ++cleanup_calls; return 0; }
int room_light(int, int) { ++cleanup_calls; return 0; }
void make_bloodstain(P_char) { ++cleanup_calls; }

int shop_keeper(P_char, P_char, int, char *) { return 0; }

static void give_item(P_char ch, P_obj object)
{
    object->loc_p = LOC_CARRIED;
    object->loc.carrying = ch;
    object->next_content = ch->carrying;
    ch->carrying = object;
}
static void wear_item(P_char ch, P_obj object)
{
    assert(!ch->equipment[0]);
    object->loc_p = LOC_WORN;
    object->loc.wearing = ch;
    ch->equipment[0] = object;
}
void obj_from_char(P_obj object)
{
    assert(OBJ_CARRIED(object) && object->loc.carrying);
    P_obj *cursor = &object->loc.carrying->carrying;
    while (*cursor && *cursor != object) cursor = &(*cursor)->next_content;
    assert(*cursor == object);
    *cursor = object->next_content;
    object->next_content = nullptr;
    object->loc_p = LOC_NOWHERE;
    object->loc.carrying = nullptr;
}
P_obj unequip_char(P_char ch, int slot, bool)
{
    P_obj object = ch->equipment[slot];
    assert(object && OBJ_WORN_BY(object, ch));
    ch->equipment[slot] = nullptr;
    object->loc_p = LOC_NOWHERE;
    object->loc.wearing = nullptr;
    return object;
}
void obj_to_room(P_obj object, int room)
{
    assert(OBJ_NOWHERE(object) && room >= 0 && room <= 1);
    object->loc_p = LOC_ROOM;
    object->loc.room = room;
    object->next_content = rooms[room].contents;
    rooms[room].contents = object;
}
void extract_obj(P_obj object, int)
{
    assert(std::find(extracted_items.begin(), extracted_items.end(), object) == extracted_items.end());
    if (OBJ_CARRIED(object)) obj_from_char(object);
    else if (OBJ_WORN(object)) {
        P_char owner = object->loc.wearing;
        for (int slot = 0; slot < MAX_WEAR; ++slot)
            if (owner->equipment[slot] == object) { unequip_char(owner, slot, false); break; }
    }
    assert(OBJ_NOWHERE(object));
    if (object->hitched_to) remove_linked_object(object);
    extracted_items.push_back(object);
}

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
    case recreated_same_room:
    case recreated_redirected:
    case recreated_detached:
    case recreated_dead:
    case incoming_combat_only:
        // These are the relationship effects of supported room actions such as
        // transfer followed by follow, guard or an attack. Services are fixtures.
        peer.specials.fighting = ch;
        combat_list = &peer;
        combat_next_ch = ch;
        if (scenario == incoming_combat_only) {
            combat_next_ch = &peer;
            return false;
        }
        outgoing_follow = {}; incoming_follow = {};
        outgoing_follow.follower = ch;
        peer.followers = &outgoing_follow;
        ch->following = &peer;
        incoming_follow.follower = &incoming_follower;
        ch->followers = &incoming_follow;
        incoming_follower.following = ch;
        outgoing_guard = {}; incoming_guard = {};
        outgoing_guard.linking = ch; outgoing_guard.linked = &peer;
        incoming_guard.linking = &peer; incoming_guard.linked = ch;
        ch->linking = peer.linked = &outgoing_guard;
        ch->linked = peer.linking = &incoming_guard;
        ch->group = &recreated_group;
        ch->nevents = ch->nevents_tail = &recreated_event;
        ch->specials.fighting = &peer;
        ch->specials.next_fighting = &peer;
        combat_list = ch;
        if (scenario == recreated_dead) SET_POS(ch, STAT_DEAD);
        if (scenario == recreated_redirected) {
            rooms[0].people = nullptr; rooms[1].people = ch; ch->in_room = 1;
        } else if (scenario == recreated_detached) {
            rooms[0].people = nullptr; ch->in_room = NOWHERE;
        }
        return false;
    case inventory_same_room:
    case inventory_redirected:
    case inventory_detached:
        // Studio GIVE/EQUIP and attachment actions can repopulate ownership after
        // the original extraction inventory pass. Keep the real object fields.
        give_item(ch, &callback_carried);
        give_item(ch, &callback_extra_carried);
        wear_item(ch, &callback_equipped);
        add_linked_object(ch, &callback_linked, LINKED_FOLLOWING);
        if (scenario == inventory_redirected) {
            rooms[0].people = nullptr; rooms[1].people = ch; ch->in_room = 1;
        } else if (scenario == inventory_detached) {
            rooms[0].people = nullptr; ch->in_room = NOWHERE;
        }
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
    follower_cleanup_calls = group_cleanup_calls = link_cleanup_calls = 0;
    combat_cleanup_calls = event_cleanup_calls = 0;
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
    assert(follower_cleanup_calls == 0 && group_cleanup_calls == 0 && link_cleanup_calls == 0);
    assert(combat_cleanup_calls == 0 && event_cleanup_calls == 0);
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


static void run_recreated_relationships(Scenario selected, bool npc)
{
    rooms[0] = {}; rooms[1] = {}; peer = {}; incoming_follower = {};
    rooms[0].number = 100; rooms[1].number = 200;
    rooms[0].funct = rooms[1].funct = room_hook;
    peer.in_room = 1;
    SET_POS((&peer), STAT_NORMAL + POS_STANDING);
    auto *ch = new char_data{};
    ch->runtime_id = 1; ch->in_room = 0;
    ch->specials.act = npc ? ACT_ISNPC : 0;
    SET_POS(ch, STAT_NORMAL + POS_STANDING);
    character_list = rooms[0].people = ch;
    hook_calls = cleanup_calls = begin_calls = end_calls = shopkeeper_calls = 0;
    follower_cleanup_calls = group_cleanup_calls = link_cleanup_calls = 0;
    combat_cleanup_calls = event_cleanup_calls = 0;
    combat_list = combat_next_ch = nullptr;
    terminal_departure_override = dummy_override = nullptr;
    dummy_guard = false; scenario = selected;
    character_removal_generation = 0;
    extraction_unlink_fixture(ch);
    assert(character_list == nullptr && ch->in_room == NOWHERE);
    assert(rooms[0].people == nullptr && rooms[1].people == nullptr);
    assert(hook_calls == 1 && end_calls == 1);
    assert(ch->following == nullptr && ch->followers == nullptr);
    assert(peer.followers == nullptr && incoming_follower.following == nullptr);
    assert(ch->linking == nullptr && ch->linked == nullptr);
    assert(peer.linking == nullptr && peer.linked == nullptr);
    assert(ch->group == nullptr && ch->nevents == nullptr && ch->nevents_tail == nullptr);
    assert(ch->specials.fighting == nullptr && peer.specials.fighting == nullptr);
    assert(combat_list == nullptr && combat_next_ch == nullptr);
    const bool full = selected != incoming_combat_only;
    assert(follower_cleanup_calls == (full ? 1 : 0));
    assert(group_cleanup_calls == (full ? 1 : 0));
    assert(link_cleanup_calls == (full ? 1 : 0));
    assert(event_cleanup_calls == (full ? 1 : 0));
    assert(combat_cleanup_calls == 1);
    delete ch;
}


static void assert_item_cleanup(P_obj object, bool extracted, int room)
{
    assert(!OBJ_CARRIED(object) && !OBJ_WORN(object) && !object->hitched_to);
    const bool was_extracted = std::find(extracted_items.begin(), extracted_items.end(), object) != extracted_items.end();
    assert(was_extracted == extracted);
    if (extracted) assert(OBJ_NOWHERE(object) && object->loc.carrying == nullptr);
    else {
        assert(OBJ_ROOM(object) && object->loc.room == room);
        bool found = false;
        for (P_obj current = rooms[room].contents; current; current = current->next_content)
            if (current == object) found = true;
        assert(found);
    }
}

static void run_inventory_cleanup(Scenario selected, bool npc, bool saved, int policy = 0)
{
    rooms[0] = {}; rooms[1] = {};
    rooms[0].number = 100; rooms[1].number = 200;
    rooms[0].funct = rooms[1].funct = room_hook;
    object_indices[0] = {}; mob_indices[0] = {};
    object_indices[0].virtual_number = 123;
    mob_indices[0].virtual_number = policy == 3 ? 100005 : policy == 4 ? 150001 : 50;
    if (policy == 2) mob_indices[0].func.mob = shop_keeper;
    transient_items = policy == 1;
    for (P_obj object : {&initial_carried, &initial_equipped, &initial_linked,
                         &callback_carried, &callback_extra_carried, &callback_equipped, &callback_linked}) {
        *object = {};
        object->loc_p = LOC_NOWHERE;
        if (transient_items) object->extra_flags |= ITEM_TRANSIENT;
    }
    extracted_items.clear();
    npc_only_data npc_data{};
    auto *ch = new char_data{};
    ch->runtime_id = 1; ch->in_room = 0;
    ch->specials.act = npc ? ACT_ISNPC : 0;
    if (npc) ch->only.npc = &npc_data;
    if (saved) ch->runtime_flags |= CHAR_RFLAG_TERMINAL_ITEMS_SAVED;
    SET_POS(ch, STAT_NORMAL + POS_STANDING);
    character_list = rooms[0].people = ch;
    give_item(ch, &initial_carried);
    wear_item(ch, &initial_equipped);
    add_linked_object(ch, &initial_linked, LINKED_FOLLOWING);
    hook_calls = cleanup_calls = begin_calls = end_calls = shopkeeper_calls = 0;
    terminal_departure_override = dummy_override = nullptr;
    combat_list = combat_next_ch = nullptr;
    dummy_guard = false; scenario = selected;
    character_removal_generation = 0;
    extraction_unlink_fixture(ch);
    assert(character_list == nullptr && ch->in_room == NOWHERE);
    assert(rooms[0].people == nullptr && rooms[1].people == nullptr);
    assert(hook_calls == 1 && end_calls == 1);
    assert(!ch->carrying && !ch->lobj);
    for (P_obj object : ch->equipment) assert(!object);
    assert(!initial_linked.hitched_to && !callback_linked.hitched_to);
    const bool saved_pc = saved && !npc;
    const bool carried_policy = saved_pc || transient_items || policy == 2 || (npc && policy == 3);
    const bool equipped_policy = saved_pc || transient_items || policy == 2 || (npc && (policy == 3 || policy == 4));
    assert_item_cleanup(&initial_carried, carried_policy, 0);
    assert_item_cleanup(&initial_equipped, equipped_policy, 0);
    const bool detached_actor = selected != inventory_redirected;
    assert_item_cleanup(&callback_carried, detached_actor || carried_policy, 1);
    assert_item_cleanup(&callback_extra_carried, detached_actor || carried_policy, 1);
    assert_item_cleanup(&callback_equipped, detached_actor || equipped_policy, 1);
    delete ch;
    // Surviving room and linked objects can now be examined after actor deletion.
    assert(!initial_linked.hitched_to && !callback_linked.hitched_to);
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
    for (bool npc : {false, true})
        for (Scenario selected : {recreated_same_room, recreated_redirected,
                                  recreated_detached, recreated_dead, incoming_combat_only})
            run_recreated_relationships(selected, npc);
    for (bool npc : {false, true})
        for (bool saved : {false, true})
            for (Scenario selected : {inventory_same_room, inventory_redirected, inventory_detached})
                run_inventory_cleanup(selected, npc, saved);
    run_inventory_cleanup(inventory_redirected, false, false, 1); // transient items
    run_inventory_cleanup(inventory_redirected, true, false, 2); // shopkeeper items
    run_inventory_cleanup(inventory_redirected, true, false, 3); // summoned-mob carrying
    run_inventory_cleanup(inventory_redirected, true, false, 4); // random-mob equipment
    char_from_room(nullptr);
    char_data detached_character{};
    detached_character.in_room = NOWHERE;
    char_from_room(&detached_character);
    std::puts("Room departure and terminal extraction: callback lifetime, relationships and item ownership cases passed");
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
    # network and persistence services outside the focused fixture.
    unlink = ("void extraction_unlink_fixture(P_char ch) {\nP_char k;\n"
              "const bool terminal_items_saved = IS_PC(ch) && IS_SET(ch->runtime_flags, CHAR_RFLAG_TERMINAL_ITEMS_SAVED);\n"
              "remove_all_linked_objects(ch);\nextract_char_items(ch, terminal_items_saved);\n"
              + extraction[start:end] + "\n}")
    harness.write_text("\n".join((
        PRELUDE,
        extract_function("utility.c", "int char_in_list(const P_char ch)"),
        "void char_from_room(P_char ch)\n" + function_body(
            source("handler.c").read_text(encoding="utf-8"),
            r"void\s+char_from_room\s*\(\s*P_char\s+ch\s*\)",
        ),
        extract_function("fight.c", "void StopAllAttackers(P_char ch)"),
        extract_function("fight.c", "static void unlink_fighting(P_char ch)"),
        extract_function("fight.c", "void stop_fighting_for_extraction(P_char ch)"),
        extract_function("linked_objects.c", "LINKED_OBJECTS::LINKED_OBJECTS("),
        extract_function("linked_objects.c", "LINKED_OBJECTS::~LINKED_OBJECTS()"),
        extract_function("linked_objects.c", "void remove_linked_object("),
        extract_function("linked_objects.c", "void remove_all_linked_objects("),
        extract_function("linked_objects.c", "void add_linked_object("),
        extract_function("handler.c", "static void extract_char_items("),
        unlink,
        DRIVER,
    )), encoding="utf-8")
    subprocess.run([
        "g++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
        "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-fno-pie", "-no-pie",
        f"-I{ROOT / 'src'}", str(harness), "-o", str(binary),
    ], cwd=ROOT, check=True)
    subprocess.run([str(binary)], cwd=ROOT, check=True)
