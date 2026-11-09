#!/usr/bin/env python3
"""Run the real Dragon Roar against room lists that fleeing really rewrites."""
from pathlib import Path
import subprocess
import tempfile
from _paths import ROOT, extract_function, source

fixture = r'''
#include "abilities/abilities.h"
#include "core/prototypes.h"
#include "core/utils.h"
#include "magic/spells.h"
#include "net/comm.h"
#include "net/gmcp.h"
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <functional>
#include <map>
#include <set>
#include <vector>

P_char character_list;
static room_data rooms[4]{};
P_room world = rooms;
const int top_of_world = 3;
int number(int low, int) { return low; }
int dice(int count, int size) { return count * size; }
const Rolls live_rolls = {dice, number};
int BOUNDED(int low, int value, int high) { return value < low ? low : value > high ? high : value; }
int get_property(const char *, int fallback) { return fallback; }
float get_property(const char *, double fallback) { return fallback; }

static std::set<P_char> live;
static std::map<P_char, std::set<int>> effects;
static std::vector<P_char> fled;
static std::map<P_char, std::vector<P_char>> dragged_along;
static std::set<P_char> fearless;
static std::function<void(P_char)> during_flee;
static int flee_room; // Where a flee ends up; 0 means the exits are blocked.
static P_char hunter, mount;

static void enter(P_char ch, int room) {
    ch->in_room = room;
    ch->next_in_room = world[room].people;
    world[room].people = ch;
}
static void leave(P_char ch) {
    for (P_char *link = &world[ch->in_room].people; *link; link = &(*link)->next_in_room)
        if (*link == ch) { *link = ch->next_in_room; break; }
    ch->in_room = NOWHERE;
    ch->next_in_room = nullptr;
}
static void move(P_char ch, int room) { leave(ch); enter(ch, room); }
static P_char person(int room) {
    auto ch = new char_data{};
    ch->specials.position = POS_STANDING + STAT_NORMAL;
    ch->player.level = 50;
    ch->player.race = RACE_HUMAN;
    ch->runtime_id = allocate_character_runtime_id();
    character_list_add(ch);
    enter(ch, room);
    live.insert(ch);
    return ch;
}
static void release(P_char ch) {
    leave(ch);
    forget_live_character(ch);
    for (P_char *link = &character_list; *link; link = &(*link)->next)
        if (*link == ch) { *link = ch->next; break; }
    live.erase(ch);
    delete ch;
}

// The flee boundary: only the real list surgery of leaving one room and entering another.
void do_flee(P_char ch, char *, int) {
    assert(live.count(ch) && ch->in_room == 1); // A room-local roar only scares this room.
    fled.push_back(ch);
    if (flee_room) {
        const auto party = dragged_along[ch];
        move(ch, flee_room);
        for (P_char companion : party) move(companion, flee_room);
    }
    if (during_flee) during_flee(ch);
}

void panic_corruption(const char *, const char *, ...) { abort(); }
bool SanityCheck(P_char, const char *) { return true; }
int GET_CHAR_SKILL_P(P_char ch, int) { assert(live.count(ch)); return 100; }
int GET_CLASS(P_char ch, uint cls) { assert(live.count(ch)); return (ch->player.m_class & cls) != 0; }
bool has_dragoon_mount(P_char) { return true; }
bool is_dragoon_mounted(P_char) { return true; }
P_char get_dragoon_mount(P_char) { return mount; }
int get_next_dragoon_circle(P_char) { return 1; }
bool affected_by_spell(P_char ch, int type) { assert(live.count(ch)); return effects[ch].count(type); }
affected_type *affect_to_char(P_char ch, affected_type *af) {
    assert(live.count(ch));
    effects[ch].insert(af->type);
    return nullptr;
}
void update_pos(P_char ch) { assert(live.count(ch)); }
void appear(P_char ch, bool) { assert(live.count(ch)); }
void send_to_char(const char *, P_char ch) { assert(live.count(ch)); }
void act(const char *, int, P_char ch, P_obj, void *vict, int) {
    assert(live.count(ch));
    assert(!vict || live.count(static_cast<P_char>(vict)));
}
bool fear_check(P_char ch, bool) { assert(live.count(ch)); return fearless.count(ch); }
bool notch_skill(P_char ch, int, float) { assert(live.count(ch)); return false; }
void DelayCommune(P_char ch, int) { assert(live.count(ch)); }
void set_short_affected_by(P_char ch, int, int) { assert(live.count(ch)); }
void CharWait(P_char ch, int) { assert(live.count(ch)); }
''' + '\n'.join(extract_function(path, signature) for path, signature in [
    ('guild/group.c', 'bool is_in_dragoon_group('),
    ('cmd/actoff.c', 'static int dragoon_power('),
    ('cmd/actoff.c', 'static int dragon_roar_hit_points('),
    ('cmd/actoff.c', 'static int dragon_roar_bonus('),
    ('cmd/actoff.c', 'static int dragon_roar_duration('),
    ('cmd/actoff.c', 'static int dragon_roar_threshold('),
    ('cmd/actoff.c', 'static int dragon_roar_empower('),
    ('cmd/actoff.c', 'static int dragon_roar_penalty('),
    ('cmd/actoff.c', 'static int dragon_roar_rest('),
    ('cmd/actoff.c', 'static int dragon_roar_lag('),
    ('cmd/actoff.c', 'static int dragon_roar_flee_roll('),
    ('cmd/actoff.c', 'static int dragon_roar_flee_threshold('),
    ('cmd/actoff.c', 'static int dragon_roar_flee_level('),
    ('cmd/actoff.c', 'void do_dragon_roar('),
]) + r'''
using people = std::vector<P_char>;

// Targets come first in the room list, so a flee runs before the roar reaches anyone else.
static people scene(int targets, bool is_hunter = true) {
    mount = person(1);
    hunter = person(1);
    hunter->player.m_class = CLASS_DRAGOON;
    hunter->player.spec = is_hunter ? SPEC_DRAGON_HUNTER : 0;
    hunter->specials.undead_spell_slots[1] = 3;
    people list(targets);
    for (int i = targets - 1; i >= 0; --i) list[i] = person(1);
    return list;
}
static void roar() { do_dragon_roar(hunter, nullptr, 0); }
static bool shaken(P_char ch) { return effects[ch].count(SONG_COWARDICE); }
static bool rallied(P_char ch) { return effects[ch].count(SKILL_WAR_CRY); }
// The loop ran to the end of the original room and the roar was paid for once.
static void assert_finished() {
    assert(rallied(hunter) && rallied(mount));
    assert(hunter->specials.undead_spell_slots[1] == 2);
}
static void clear_scene() {
    for (int room = 1; room <= top_of_world; ++room)
        while (world[room].people) release(world[room].people);
    effects.clear(); fled.clear(); dragged_along.clear(); fearless.clear();
    during_flee = nullptr;
    flee_room = 0;
    hunter = mount = nullptr;
}

static void flee_into_occupied_room() {
    auto targets = scene(2);
    auto stranger = person(2);
    flee_room = 2;
    roar();
    assert(fled == (people{targets[0], targets[1]}));
    assert(shaken(targets[0]) && shaken(targets[1]));
    assert(!shaken(stranger) && stranger->in_room == 2);
    assert_finished();
    clear_scene();
}
static void flee_into_empty_room() { // Used to end the roar early, so the group lost War Cry.
    auto targets = scene(3);
    flee_room = 2;
    roar();
    assert(fled == (people{targets[0], targets[1], targets[2]}));
    assert_finished();
    clear_scene();
}
static void flee_with_exits_blocked() {
    auto targets = scene(2);
    roar();
    assert(fled == (people{targets[0], targets[1]}));
    assert(targets[0]->in_room == 1 && targets[1]->in_room == 1);
    assert_finished();
    clear_scene();
}
static void remote_groupmate_is_not_rallied() {
    auto targets = scene(1);
    auto ally = person(2);
    group_list member{ally, nullptr};
    hunter->group = &member;
    flee_room = 2;
    roar();
    assert(!rallied(ally) && !shaken(ally) && fled == people{targets[0]});
    assert_finished();
    clear_scene();
}
static void companion_leaves_with_the_fleer() { // The saved next person is gone too.
    auto targets = scene(3);
    dragged_along[targets[0]] = {targets[1]};
    flee_room = 2;
    roar();
    assert(fled == (people{targets[0], targets[2]}));
    assert(!shaken(targets[1]) && targets[1]->in_room == 2);
    assert(shaken(targets[2]));
    assert_finished();
    clear_scene();
}
static void exclusions_do_not_flee() {
    auto targets = scene(4);
    group_list member{targets[0], nullptr};
    hunter->group = &member;
    SET_BIT(targets[1]->specials.affected_by4, AFF4_NOFEAR);
    SET_BIT(targets[2]->specials.act, ACT_ELITE);
    fearless.insert(targets[3]);
    flee_room = 2;
    roar();
    assert(fled.empty());
    assert(rallied(targets[0]) && !shaken(targets[0]));
    assert(shaken(targets[1]) && shaken(targets[2]) && shaken(targets[3]));
    assert_finished();
    clear_scene();
}
static void only_hunters_scare() {
    auto targets = scene(2, false);
    flee_room = 2;
    roar();
    assert(fled.empty() && shaken(targets[0]) && shaken(targets[1]));
    assert_finished();
    clear_scene();
}
static void hook_removes_next_target() {
    auto targets = scene(3);
    during_flee = [&](P_char ch) { if (ch == targets[0]) release(targets[1]); };
    flee_room = 2;
    roar();
    assert(fled == (people{targets[0], targets[2]}));
    assert_finished();
    clear_scene();
}
static void hook_relocates_next_target() {
    auto targets = scene(3);
    during_flee = [&](P_char ch) { if (ch == targets[0]) move(targets[1], 3); };
    flee_room = 2;
    roar();
    assert(fled == (people{targets[0], targets[2]}));
    assert(!shaken(targets[1]) && targets[1]->in_room == 3);
    assert_finished();
    clear_scene();
}
static void hook_removes_fleer() {
    auto targets = scene(2);
    during_flee = [&](P_char ch) { if (ch == targets[0]) release(ch); };
    roar();
    assert(fled.size() == 2 && fled[1] == targets[1]);
    assert_finished();
    clear_scene();
}
static void hook_leaves_next_target_dead() {
    auto targets = scene(3);
    during_flee = [&](P_char ch) {
        if (ch == targets[0]) SET_POS(targets[1], POS_PRONE + STAT_DEAD);
    };
    roar();
    assert(fled == (people{targets[0], targets[2]}) && !shaken(targets[1]));
    assert_finished();
    clear_scene();
}
static void hook_removes_roarer() {
    auto targets = scene(2);
    during_flee = [&](P_char) { release(hunter); };
    roar(); // Sanitizers and the boundaries reject any later use of the released roarer.
    assert(fled == people{targets[0]} && !shaken(targets[1]));
    clear_scene();
}
static void hook_leaves_roarer_dead() {
    auto targets = scene(2);
    during_flee = [&](P_char) { SET_POS(hunter, POS_PRONE + STAT_DEAD); };
    roar();
    assert(fled == people{targets[0]} && !shaken(targets[1]));
    assert(hunter->specials.undead_spell_slots[1] == 3);
    clear_scene();
}
static void roarer_dragged_out_still_finishes_the_room() {
    auto targets = scene(2);
    dragged_along[targets[0]] = {hunter};
    flee_room = 2;
    roar();
    assert(fled == (people{targets[0], targets[1]}));
    assert(hunter->in_room == 2 && !rallied(hunter) && rallied(mount));
    assert(hunter->specials.undead_spell_slots[1] == 2);
    clear_scene();
}
int main() {
    flee_into_occupied_room();
    flee_into_empty_room();
    flee_with_exits_blocked();
    remote_groupmate_is_not_rallied();
    companion_leaves_with_the_fleer();
    exclusions_do_not_flee();
    only_hunters_scare();
    hook_removes_next_target();
    hook_relocates_next_target();
    hook_removes_fleer();
    hook_leaves_next_target_dead();
    hook_removes_roarer();
    hook_leaves_roarer_dead();
    roarer_dragged_out_still_finishes_the_room();
    std::printf("PASS dragon roar room targets\n");
}
'''

out = ROOT / 'bin/tests'
out.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix='dragon-roar-', dir=out) as temporary:
    cpp, binary = Path(temporary) / 'test.cpp', Path(temporary) / 'test'
    cpp.write_text(fixture)
    subprocess.run(['g++', '-std=c++20', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                    '-g', '-Isrc', str(cpp), str(source('character_identity.c')), '-o', str(binary)],
                   cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True, timeout=30)
