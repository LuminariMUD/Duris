#!/usr/bin/env python3
"""Run damage callers against damage that really releases the dead participant."""
from pathlib import Path
import subprocess
import tempfile
from _paths import ROOT, extract_function

fixture = r'''
#include "abilities/abilities.h"
#include "core/prototypes.h"
#include "core/utils.h"
#include "combat/damage.h"
#include "combat/grapple.h"
#include "item/objmisc.h"
#include "magic/spells.h"
#include "net/comm.h"
#include <cassert>
#include <cstdio>
#include <cstring>
#include <set>
#include <string>
static room_data rooms[2]{};
P_room world = rooms;
const int top_of_world = 1;
int STAT_INDEX(int stat) { return stat; }
int BOUNDED(int low, int value, int high) { return value < low ? low : value > high ? high : value; }
int get_property(const char *, int fallback) { return fallback; }
float get_property(const char *, double fallback) { return fallback; }
static std::set<P_char> live;
static int damage_calls, waits, notches, follow_ups;
static P_char kill_on_hit, kill_with_hit; // Released by the next damage call.
int number(int low, int) { return low; }
int dice(int count, int size) { return count * size; }
const Rolls live_rolls = {dice, number};

static char_data *person(int skill_room = 1) {
    auto ch = new char_data{};
    ch->specials.position = POS_STANDING + STAT_NORMAL;
    ch->in_room = skill_room;
    ch->player.level = 50;
    ch->player.race = RACE_HUMAN;
    live.insert(ch);
    ch->next_in_room = world[skill_room].people;
    world[skill_room].people = ch;
    return ch;
}
static void release(P_char ch) {
    for (P_char *link = &world[ch->in_room].people; *link; link = &(*link)->next_in_room)
        if (*link == ch) { *link = ch->next_in_room; break; }
    live.erase(ch);
    delete ch;
}
static void clear_room() {
    while (world[1].people) release(world[1].people);
    damage_calls = waits = notches = follow_ups = 0;
    kill_on_hit = kill_with_hit = nullptr;
}
static int hit(P_char ch, P_char victim) {
    assert(live.count(ch) && live.count(victim));
    ++damage_calls;
    const bool dead = victim == kill_on_hit, attacker = ch == kill_with_hit;
    if (dead) release(victim);
    if (attacker && !(dead && ch == victim)) release(ch);
    if (dead) kill_on_hit = nullptr;
    if (attacker) kill_with_hit = nullptr;
    return dead && attacker ? DAM_BOTHDEAD : dead ? DAM_VICTDEAD : attacker ? DAM_CHARDEAD : DAM_NONEDEAD;
}
int spell_damage(P_char ch, P_char victim, double, int, uint, damage_messages *, int *) { return hit(ch, victim); }
int melee_damage(P_char ch, P_char victim, double, int, damage_messages *, int *) { return hit(ch, victim); }
bool damage(P_char ch, P_char victim, double, int) { return hit(ch, victim) != DAM_NONEDEAD; }
void CharWait(P_char ch, int) { assert(live.count(ch)); ++waits; }
bool notch_skill(P_char ch, int, float) { assert(live.count(ch)); ++notches; return false; }
void act(const char *, int, P_char ch, P_obj, void *vict, int) {
    assert(live.count(ch));
    assert(!vict || live.count(static_cast<P_char>(vict)));
}
void send_to_char(const char *, P_char ch) { assert(live.count(ch)); }
void send_to_room(const char *, int) {}
nevent_schedule_result add_event(event_func, int, P_char ch, P_char vict, P_obj, int, const void *, int) {
    assert(live.count(ch) && live.count(vict)); ++follow_ups; return {};
}
void affect_to_char_with_messages(P_char ch, affected_type *, const char *, const char *) { assert(live.count(ch)); }
bool NewSaves(P_char ch, int, int) { assert(live.count(ch)); return true; }
bool StatSave(P_char ch, int, int) { assert(live.count(ch)); return false; }
bool resists_spell(P_char, P_char) { return false; }
int STATS(P_char, int) { return 100; }
int GET_CHAR_SKILL_P(P_char, int) { return 100; }
void affect_from_char(P_char, int) {}
void unlink_char(P_char, P_char, int) {}
affected_type *affect_to_char(P_char, affected_type *) { return nullptr; }
int char_in_list(P_char ch) { return live.count(ch); }
int CanDoFightMove(P_char ch, P_char vict) { assert(live.count(ch) && live.count(vict)); return true; }
bool affected_by_spell(P_char ch, int type) { assert(live.count(ch)); return type == TAG_GRAPPLE || type == SKILL_BEARHUG; }
void Stun(P_char, P_char, int, bool) {}
void do_flee(P_char, char *, int) {}
void obj_from_char(P_obj) {}
P_obj unequip_char(P_char, int, bool) { return nullptr; }
void extract_obj(P_obj, int) {}
void obj_to_room(P_obj, int) {}
P_obj create_money(int, int, int, int) { return nullptr; }
int real_room(int) { return 1; }
void char_from_room(P_char) {}
bool char_to_room(P_char, int, int) { return true; }
void die(P_char, P_char) {}
int is_char_in_room(P_char ch, int) { return live.count(ch); }
static int roll_for_strike;
static int crippling_strike_roll(const Rolls &) { return roll_for_strike; }
static int crippling_strike_deaf_duration(const Rolls &) { return 1; }
static int crippling_strike_best_vitality(const Rolls &) { return 0; }
static int crippling_strike_second_vitality(const Rolls &) { return 0; }
static int crippling_strike_best_damage(const Rolls &) { return 1; }
static int crippling_strike_second_damage(const Rolls &) { return 1; }
static int crippling_strike_third_damage(const Rolls &) { return 1; }
static int crippling_strike_fourth_damage(const Rolls &) { return 1; }
static int bearhug_rest() { return 1; }
static int bearhug_interval() { return 1; }
static int bearhug_damage_roll(const Rolls &) { return 1; }
static int bearhug_base_damage(P_char, int) { return 1; }
static int sticks_to_snakes_count(const Rolls &, int) { return 2; }
static int sticks_to_snakes_cap() { return 8; }
static int sticks_to_snakes_bite(const Rolls &, int) { return 1; }
static int transfer_wellness_healing(const Rolls &, int, P_char) { return 10; }
void do_point(P_char, P_char) {}
void wizlog(int, const char *, ...) {}
int GET_CLASS(P_char, uint) { return 0; }
static int transfer_wellness_cost(int to) { return to; }
int find_dam_type(const char *) { return 0; }
''' + '\n'.join(extract_function(path, sig) for path, sig in [
    ('classes/psionics.c', 'void spell_detonate2('),
    ('magic/smagic.c', 'void spell_transfer_wellness('),
    ('magic/magic.c', 'void spell_sticks_to_snakes('),
    ('combat/grapple.c', 'void event_bearhug('),
    ('cmd/actoff.c', 'bool check_crippling_strike('),
]) + r'''
static void detonate() {
    for (bool attacker_dies : {false, true}) {
        auto caster = person(), victim = person();
        (attacker_dies ? kill_with_hit : kill_on_hit) = attacker_dies ? caster : victim;
        spell_detonate2(50, caster, nullptr, 0, victim, nullptr);
        assert(damage_calls == 1);
        assert(waits == !attacker_dies); // The surviving caster still pays the lag.
        clear_room();
    }
}
static void bearhug() {
    for (bool attacker_dies : {false, true}) {
        auto hugger = person(), victim = person();
        (attacker_dies ? kill_with_hit : kill_on_hit) = attacker_dies ? hugger : victim;
        event_bearhug(hugger, victim, nullptr, nullptr);
        assert(damage_calls == 1 && follow_ups == 0);
        assert(notches == !attacker_dies);
        clear_room();
    }
}
static void crippling_strike() {
    for (int roll : {0, 30, 50, 70}) { // Reaches each damaging branch.
        for (bool stander_dies : {true, false}) {
            roll_for_strike = roll;
            auto stander = person(), striker = person(), tank = person();
            stander->specials.fighting = tank;
            striker->specials.fighting = stander;
            tank->specials.fighting = striker;
            if (stander_dies) kill_on_hit = stander; else kill_with_hit = striker;
            assert(check_crippling_strike(stander));
            assert(damage_calls == 1);
            clear_room();
        }
    }
}
static void transfer_wellness() {
    auto caster = person(), bystander = person(), target = person();
    caster->points.hit = 2;
    target->points.hit = 1; target->points.max_hit = 100;
    bystander->points.hit = bystander->points.max_hit = 100;
    kill_on_hit = target; // First in the room, so the blast must step past it.
    spell_transfer_wellness(50, caster, nullptr, 0, target, nullptr);
    assert(damage_calls == 2);
    clear_room();
}
static void sticks() {
    auto caster = person(), target = person();
    kill_with_hit = caster; // A deflected bite: no later snake may use the dead caster.
    spell_sticks_to_snakes(50, caster, nullptr, 0, target, nullptr);
    assert(damage_calls == 1);
    clear_room();
    caster = person(); target = person();
    kill_on_hit = target;
    spell_sticks_to_snakes(50, caster, nullptr, 0, target, nullptr);
    assert(damage_calls == 1);
    clear_room();
}
int main() {
    detonate();
    bearhug();
    crippling_strike();
    transfer_wellness();
    sticks();
    std::printf("PASS damage result lifetime\n");
}
'''

out = ROOT / 'bin/tests'
out.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix='damage-results-', dir=out) as temporary:
    cpp, binary = Path(temporary) / 'test.cpp', Path(temporary) / 'test'
    cpp.write_text(fixture)
    subprocess.run(['g++', '-std=c++20', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                    '-g', '-Isrc', str(cpp), '-o', str(binary)], cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True, timeout=30)
