#!/usr/bin/env python3
"""Exercise the real pet-link break and extraction follower path under sanitizers."""

import subprocess

from _paths import ROOT, HARNESS_STUBS, extract_function


harness = r"""
#include "core/prototypes.h"
#include "core/utils.h"
#include "net/comm.h"
#include "classes/necromancy.h"
#include "persistence/persistence_checkpoint.h"
#include "redis/redis_floor_runtime.h"
#include <cassert>
#include <cstdlib>
#include <set>
#include <vector>

room_data rooms[2] = {};
P_room world = rooms;
index_data mob_indexes[1] = {};
P_index mob_index = mob_indexes;
link_description link_types[LNK_MAX + 1] = {};
static int dirty_calls, fights, deaths, scheduled;
static bool hostile;
static std::vector<uint64_t> floor_uids;

void charm_broken(char_link_data *);
void __free(void *pointer, const char *, int) { std::free(pointer); }
void dispose_link(char_link_data *link) { assert(!link->affect); std::free(link); }
void wear_off_message(P_char, affected_type *) { std::abort(); }
bool group_remove_member(P_char) { std::abort(); }
void act(const char *, int, P_char, P_obj, void *, int) {}
void schedule_pet_death(P_char, int) { ++scheduled; }
void die(P_char, P_char) { ++deaths; }
int CheckFor_remember(P_char, P_char) { return hostile; }
void MobStartFight(P_char pet, P_char)
{
    assert(!pet->carrying);
    for (P_obj object : pet->equipment) assert(!object);
    ++fights;
}
void mark_player_dirty_components(int pid, player_component_mask_t mask)
{
    assert(pid == 42 && (mask & PLAYER_COMPONENT_PETS));
    ++dirty_calls;
}
void redis_log_floor_drop(P_obj object, int room_vnum)
{
    assert(OBJ_ROOM(object) && world[object->loc.room].number == room_vnum);
    floor_uids.push_back(object->obj_uid);
}
P_obj unequip_char(P_char pet, int slot, bool)
{
    P_obj object = pet->equipment[slot]; assert(object);
    pet->equipment[slot] = nullptr;
    object->loc_p = LOC_NOWHERE;
    object->loc.wearing = nullptr;
    return object;
}
void obj_to_char(P_obj object, P_char actor)
{
    object->loc_p = LOC_CARRIED;
    object->loc.carrying = actor;
    object->next_content = actor->carrying;
    actor->carrying = object;
}
void obj_from_char(P_obj object)
{
    assert(OBJ_CARRIED(object));
    P_char actor = object->loc.carrying;
    P_obj *at = &actor->carrying;
    while (*at && *at != object) at = &(*at)->next_content;
    assert(*at == object);
    *at = object->next_content;
    object->next_content = nullptr;
    object->loc_p = LOC_NOWHERE;
    object->loc.carrying = nullptr;
}
void obj_to_room(P_obj object, int room)
{
    assert(OBJ_NOWHERE(object));
    if (object->type == ITEM_MONEY) { delete object; return; } // merged coin pile
    object->loc_p = LOC_ROOM;
    object->loc.room = room;
    object->next_content = world[room].contents;
    world[room].contents = object;
}
"""

for file, signature in (
    ("affects.c", "P_char get_linked_char(P_char ch, ush_int type)"),
    ("affects.c", "void internal_unlink_char(P_char ch, struct char_link_data *cld,"),
    ("affects.c", "void unlink_char(P_char ch, P_char target, ush_int type)"),
    ("affects.c", "void clear_links(P_char ch, ush_int type)"),
    ("sparser.c", "void stop_follower(P_char ch)"),
    ("sparser.c", "void die_follower(P_char ch)"),
    ("handler.c", "void unequip_all(P_char ch)"),
    ("necromancy.c", "void charm_broken(struct char_link_data *cld)"),
):
    harness += "\n" + extract_function(file, signature) + "\n"

harness += r"""
struct fixture
{
    char_data owner{}, pet{};
    pc_only_data pc{};
    npc_only_data npc{};
    obj_data worn{}, bag{}, child{};
    fixture(bool following = true, int link_type = LNK_PET)
    {
        rooms[0] = {}; rooms[1] = {}; rooms[0].number = 100; rooms[1].number = 200;
        dirty_calls = fights = deaths = scheduled = 0; hostile = false; floor_uids.clear();
        owner.only.pc = &pc; pc.pid = 42; GET_HIT(&owner) = 100;
        pet.only.npc = &npc; pet.specials.act = ACT_ISNPC;
        pet.in_room = 1; owner.in_room = 1;
        mob_indexes[0].virtual_number = 139132;
        worn.type = ITEM_ARMOR; worn.obj_uid = 9001; worn.loc_p = LOC_WORN;
        worn.loc.wearing = &pet; worn.extra_flags = ITEM_NODROP;
        pet.equipment[WEAR_BODY] = &worn;
        bag.type = ITEM_CONTAINER; bag.obj_uid = 9002; bag.loc_p = LOC_CARRIED;
        bag.loc.carrying = &pet; bag.extra2_flags = ITEM2_SOULBIND; pet.carrying = &bag;
        child.type = ITEM_ARMOR; child.obj_uid = 9003; child.loc_p = LOC_INSIDE;
        child.loc.inside = &bag; bag.contains = &child;
        auto *link = static_cast<char_link_data *>(std::calloc(1, sizeof(char_link_data)));
        link->type = link_type; link->linking = &pet; link->linked = &owner;
        pet.linking = owner.linked = link;
        link_types[link_type].break_func.ch = charm_broken;
        if (following)
        {
            pet.following = &owner;
            owner.followers = static_cast<follow_type *>(std::calloc(1, sizeof(follow_type)));
            owner.followers->follower = &pet;
        }
    }
    void assert_dropped()
    {
        assert(!pet.carrying && !pet.equipment[WEAR_BODY]);
        assert(OBJ_ROOM(&worn) && worn.loc.room == 1);
        assert(OBJ_ROOM(&bag) && bag.loc.room == 1);
        assert(bag.contains == &child && OBJ_INSIDE(&child) && child.loc.inside == &bag);
        assert((std::set<uint64_t>(floor_uids.begin(), floor_uids.end()) == std::set<uint64_t>{9001, 9002}));
        assert(dirty_calls == 1 && !pet.following && !owner.followers);
        assert(!pet.linking && !owner.linked && !deaths);
    }
};

int main()
{
    { fixture f; hostile = true; clear_links(&f.pet, LNK_PET); f.assert_dropped(); assert(fights == 1); }
    // Extracting a still-controlled high-VNUM NPC reaches the same callback before
    // extract_char's generic equipment/inventory cleanup can delete anything.
    { fixture f; die_follower(&f.pet); f.assert_dropped(); assert(!fights); }
    { fixture f(false); clear_links(&f.pet, LNK_PET); f.assert_dropped(); }
    { fixture f; f.owner.in_room = 0; clear_links(&f.pet, LNK_PET); f.assert_dropped(); }
    { fixture f; f.pet.durable_pet_uid = 123; clear_links(&f.pet, LNK_PET); f.assert_dropped(); }
    { fixture f; mob_indexes[0].virtual_number = 1201; clear_links(&f.pet, LNK_PET); f.assert_dropped(); assert(scheduled == 1); }
    { fixture f; auto *coins = new obj_data{}; coins->type = ITEM_MONEY; coins->obj_uid = 9004;
      obj_to_char(coins, &f.pet); clear_links(&f.pet, LNK_PET); f.assert_dropped(); }
    { fixture f; f.pet.in_room = NOWHERE; clear_links(&f.pet, LNK_PET);
      assert(f.pet.carrying == &f.bag && f.pet.equipment[WEAR_BODY] == &f.worn && floor_uids.empty() && !dirty_calls); }
    { fixture f; f.owner.specials.act = ACT_ISNPC; clear_links(&f.pet, LNK_PET);
      assert(f.pet.carrying == &f.bag && f.pet.equipment[WEAR_BODY] == &f.worn && floor_uids.empty() && !dirty_calls); }
    { fixture f; f.pet.specials.act = 0; f.pet.only.pc = &f.pc; clear_links(&f.pet, LNK_PET);
      assert(f.pet.carrying == &f.bag && f.pet.equipment[WEAR_BODY] == &f.worn && floor_uids.empty() && !dirty_calls); }
    { fixture f(true, LNK_DRAGOON_MOUNT); clear_links(&f.pet, LNK_DRAGOON_MOUNT);
      assert(f.pet.carrying == &f.bag && f.pet.equipment[WEAR_BODY] == &f.worn && floor_uids.empty() && !dirty_calls); }
}
"""

extract = extract_function("handler.c", "void extract_char(P_char ch)")
assert extract.index("die_follower(ch)") < extract.index("/* clear equipment_list */")

build = ROOT / "bin/tests/pet-control-drop"
build.mkdir(parents=True, exist_ok=True)
source = build / "regression.cpp"
binary = build / "regression"
source.write_text(harness)
subprocess.run([
    "g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-Isrc",
    "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
    str(source), str(HARNESS_STUBS), "-o", str(binary),
], cwd=ROOT, check=True)
subprocess.run([str(binary)], check=True, timeout=10)
print("pet control-break floor drops, nested contents, extraction, aggression and exclusions passed")
