#!/usr/bin/env python3
"""Exercise combat startup callbacks and the hit continuation from the Nov 3 core.

Production set_fighting/engage, the hit startup block, and melee_damage startup
and retaliation blocks run under sanitizers. Dragon/innate effects are fixtures
that kill, extract, replace, relocate, or disarm a participant synchronously.
"""
from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, HARNESS_STUBS, extract_function

hit = extract_function('fight.c', 'bool hit(')
start = hit.index('\tif (!IS_FIGHTING(ch))')
end = hit.index('\n\t/* The blind and eyeless', start)
hit_start = hit[start:end]
melee = ''.join(extract_function('fight.c', signature) for signature in (
    'int skin_spell_deduct(', 'float iceflow_armor_melee_share(',
    'float negative_feedback_barrier_melee_share(', 'int melee_damage('))
start = melee.index('\tif (!IS_FIGHTING(ch)')
end = melee.index('\n\tdragonfist = FALSE;', start)
melee_start = melee[start:end]
start = melee.index('\tif (dam <= 5 || (flags & PHSDAM_NOSHIELDS))')
end = melee.index('\n\t// If they actually took damage', start)
retaliation = melee[start:end]

PRELUDE = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "combat/attack_continuation.h"
#include "combat/damage.h"
#include "combat/training_dummy.h"
#include "economy/collector_presence.h"
#include "net/comm.h"
#include "net/gmcp.h"
#include "telemetry/telemetry_runtime.h"
#include "classes/dreadlord.h"
#include "magic/spells.h"
#include "item/objmisc.h"
#include <cassert>
#include <cstdio>
#include <cstdlib>

enum class effect { none, kill_actor, kill_target, kill_both, extract_actor, extract_target,
                    replace_actor, replace_target, move_actor, move_target, move_height,
                    drop_weapon, replace_weapon };
enum class callback { dragon, anti_evil, decrepify, wrath, dismount };
static char_data actor{}, target{}, mount{};
static pc_only_data actor_pc{}, target_pc{};
static npc_only_data actor_npc{}, target_npc{};
static room_data rooms[3]{};
static index_data profiles[2]{};
static obj_data weapon{};
static bool actor_listed, target_listed, mounted;
static effect change;
static callback trigger;
static int dragons, anti_evils, decrepifies, wraths, dismounts, retaliations;
P_char combat_list;
P_room world = rooms;
P_index mob_index = profiles;
P_obj object_list;

static void require_live(P_char ch) {
    assert(ch && IS_ALIVE(ch));
    assert(ch->only.pc);
    assert((ch == &actor && actor_listed) || (ch == &target && target_listed));
}
P_char find_character_by_runtime_id(uint64_t id) {
    if (actor_listed && actor.runtime_id == id) return &actor;
    if (target_listed && target.runtime_id == id) return &target;
    return nullptr;
}
static void mutate() {
    switch (change) {
    case effect::none: break;
    case effect::kill_actor:
    case effect::kill_both:
        SET_POS(&actor, POS_STANDING + STAT_DEAD); actor.only.pc = nullptr;
        if (change != effect::kill_both) break;
        [[fallthrough]];
    case effect::kill_target:
        SET_POS(&target, POS_STANDING + STAT_DEAD); target.only.pc = nullptr; break;
    case effect::extract_actor: actor_listed = false; actor.only.pc = nullptr; break;
    case effect::extract_target: target_listed = false; target.only.pc = nullptr; break;
    case effect::replace_actor: ++actor.runtime_id; break;
    case effect::replace_target: ++target.runtime_id; break;
    case effect::move_actor: ++actor.in_room; break;
    case effect::move_target: ++target.in_room; break;
    case effect::move_height: ++target.specials.z_cord; break;
    case effect::drop_weapon: actor.equipment[PRIMARY_WEAPON] = nullptr; break;
    case effect::replace_weapon: ++weapon.obj_uid; break;
    }
}
[[noreturn]] int panic_corruption_int(const char *, const char *, ...) { std::abort(); }
bool collector_presence_is_npc(P_char) { return false; }
bool training_dummy_is(P_char) { return false; }
bool training_dummy_target_allowed(P_char, P_char) { return true; }
void training_dummy_retarget_nonpet(P_char, P_char) { std::abort(); }
bool SanityCheck(P_char ch, const char *) { require_live(ch); return true; }
bool can_hit_target(P_char, P_char) { return true; }
bool AdjacentInRoom(P_char, P_char) { return true; }
P_char PickTarget(P_char) { std::abort(); }
int on_front_line(P_char) { return true; }
int IS_MORPH(P_char) { return false; }
int GET_CLASS(P_char, uint) { return false; }
int number(int, int high) { return high; }
bool affected_by_spell(P_char, int) { return false; }
void affect_from_char(P_char, int) { std::abort(); }
affected_type *get_spell_from_char(P_char, int, void *, int) { return nullptr; }
void appear(P_char, bool) {}
void stop_meditation(P_char) { std::abort(); }
void show_string(P_desc, const char *) { std::abort(); }
void send_to_char(const char *, P_char) {}
void act(const char *, int, P_char, P_obj, void *, int) {}
void logit(const char *, const char *, ...) { std::abort(); }
void event_water_crossing(P_char, P_char, P_obj, void *) {}
void disarm_char_nevents(P_char, event_func) {}
void update_group_vitals(P_char) {}
void gmcp_char_vitals(P_char) {}
void gmcp_combat_target(P_char, P_char) {}
void gmcp_mark_room_dirty(int) {}
void telemetry_combat_context_changed(P_char) {}
telemetry_capture_result telemetry_runtime_game_encounter_begin(P_char, telemetry_encounter_mode) { return {}; }
void stop_memorizing(P_char, memorization_stop_reason) {}
void stop_fighting(P_char ch) { ch->specials.fighting = nullptr; }
bool DragonCombat(P_char ch, int) {
    require_live(ch); ++dragons;
    if (trigger == callback::dragon) mutate();
    return true;
}
void remember(P_char ch, P_char victim) { require_live(ch); require_live(victim); }
bool ac_can_see(P_char, P_char, bool) { return true; }
void do_wake(P_char, char *, int) { std::abort(); }
P_char get_linked_char(P_char ch, ush_int type) {
    return type == LNK_RIDING && ch == &actor && mounted ? &mount : nullptr;
}
bool is_flight_passenger(P_char) { return false; }
void stop_riding(P_char) { ++dismounts; mounted = false; if (trigger == callback::dismount) mutate(); }
bool has_innate(P_char ch, int innate) {
    require_live(ch);
    return (innate == INNATE_ANTI_EVIL && trigger == callback::anti_evil) ||
           (innate == INNATE_DECREPIFY && trigger == callback::decrepify);
}
int GET_CHAR_SKILL_P(P_char ch, int skill) {
    require_live(ch);
    return skill == SKILL_DREAD_WRATH ? 100 : 0;
}
void do_innate_anti_evil(P_char ch, P_char victim) {
    require_live(ch); require_live(victim); ++anti_evils; mutate();
}
void do_innate_decrepify(P_char ch, P_char victim) {
    require_live(ch); require_live(victim); ++decrepifies; mutate();
}
void do_dread_wrath(P_char ch, P_char victim) {
    require_live(ch); require_live(victim); ++wraths;
    if (trigger == callback::wrath) mutate();
}
static int retaliation_result;
int attack_back(P_char, P_char, int) { ++retaliations; return retaliation_result; }
'''

PRODUCTION = '\n'.join((
    extract_function('specs.ailvio.c', 'int tutorial_mobile_mechanics_race('),
    extract_function('fight.c', 'void set_fighting(P_char ch, P_char vict)'),
    extract_function('fight.c', 'void engage('),
))
WRAPPERS = r'''
static bool hit_startup(P_char ch, P_char victim, P_obj weapon) {
    (void)weapon;
HIT_START
    require_live(ch); require_live(victim);
    // This lookup is the crash site in core.2026.11.03-11.12.01.
    (void)tutorial_mobile_mechanics_race(victim);
    return true;
}
static int melee_startup(P_char ch, P_char victim, int flags = 0) {
MELEE_START
    require_live(ch); require_live(victim);
    return 99; // reached the original strike's damage calculation
}
static int melee_retaliation(P_char ch, P_char victim, double dam, int flags) {
    const int result = DAM_NONEDEAD;
RETALIATION
    return 99; // reached the shield branch
}
'''.replace('HIT_START', hit_start).replace('MELEE_START', melee_start).replace('RETALIATION', retaliation)

DRIVER = r'''
static void reset(effect mutation, callback where, bool pc_actor = false, bool pc_target = false) {
    actor = {}; target = {}; actor_pc = {}; target_pc = {};
    actor_npc = {}; target_npc = {}; weapon = {};
    actor.only.pc = &actor_pc; target.only.pc = &target_pc;
    if (!pc_actor) { actor.specials.act = ACT_ISNPC; actor.only.npc = &actor_npc; }
    if (!pc_target) { target.specials.act = ACT_ISNPC; target.only.npc = &target_npc; }
    actor.player.race = RACE_DRAGON; target.player.race = RACE_W_ELEMENTAL;
    target.specials.alignment = -1000;
    actor_npc.R_num = 0; target_npc.R_num = 1;
    profiles[0].virtual_number = 3818; profiles[1].virtual_number = 1000;
    actor.runtime_id = 10; target.runtime_id = 20;
    actor.in_room = target.in_room = 1;
    SET_POS(&actor, POS_STANDING + STAT_NORMAL);
    SET_POS(&target, POS_STANDING + STAT_NORMAL);
    actor_listed = target_listed = true;
    weapon.obj_uid = 30; object_list = &weapon;
    actor.equipment[PRIMARY_WEAPON] = &weapon;
    combat_list = nullptr; mounted = where == callback::dismount;
    change = mutation; trigger = where;
    dragons = anti_evils = decrepifies = wraths = dismounts = retaliations = 0;
}
int main() {
    for (auto where : {callback::dragon, callback::anti_evil, callback::decrepify,
                       callback::wrath, callback::dismount}) {
        for (auto mutation : {effect::none, effect::kill_actor, effect::kill_target,
                              effect::kill_both, effect::extract_actor, effect::extract_target,
                              effect::replace_actor, effect::replace_target, effect::move_actor,
                              effect::move_target, effect::move_height, effect::drop_weapon,
                              effect::replace_weapon}) {
            reset(mutation, where);
            assert(hit_startup(&actor, &target, &weapon) == (mutation == effect::none));
            assert(dragons == 1);
            if (where != callback::wrath && mutation != effect::none &&
                mutation != effect::drop_weapon && mutation != effect::replace_weapon)
                assert(wraths == 0);
        }
    }
    // Reproduce the unarmed dragon -> sleeping elemental attack in the core.
    reset(effect::kill_target, callback::dragon);
    SET_POS(&target, POS_PRONE + STAT_SLEEPING);
    actor.equipment[PRIMARY_WEAPON] = nullptr;
    assert(!hit_startup(&actor, &target, nullptr));
    assert(target.only.npc == nullptr && wraths == 0);
    // Players also participate in synchronous innate callbacks.
    for (bool pc_actor : {false, true}) for (bool pc_target : {false, true}) {
        reset(effect::kill_target, callback::anti_evil, pc_actor, pc_target);
        assert(!hit_startup(&actor, &target, nullptr));
        assert(anti_evils == 1 && wraths == 0);
    }
    for (auto mutation : {effect::none, effect::kill_actor, effect::kill_target, effect::kill_both,
                          effect::extract_actor, effect::extract_target, effect::replace_actor, effect::replace_target,
                          effect::move_actor, effect::move_target, effect::move_height}) {
        reset(mutation, callback::dragon);
        const int expected = mutation == effect::none ? 99 :
            (mutation == effect::kill_actor || mutation == effect::extract_actor ||
             mutation == effect::replace_actor) ? DAM_CHARDEAD :
            (mutation == effect::kill_target || mutation == effect::extract_target ||
             mutation == effect::replace_target) ? DAM_VICTDEAD :
            mutation == effect::kill_both ? DAM_BOTHDEAD : DAM_NONEDEAD;
        assert(melee_startup(&actor, &target) == expected);
        reset(mutation, callback::dragon);
        engage(&actor, &target);
        assert(target.specials.fighting == (mutation == effect::none ? &actor : nullptr));
    }
    for (int result : {DAM_NONEDEAD, DAM_CHARDEAD, DAM_VICTDEAD, DAM_BOTHDEAD}) {
        reset(effect::none, callback::dragon); retaliation_result = result;
        assert(melee_retaliation(&actor, &target, 4, 0) == result && retaliations == 1);
        retaliations = 0;
        assert(melee_retaliation(&actor, &target, 40, PHSDAM_NOSHIELDS) == result && retaliations == 1);
        retaliations = 0;
        assert(melee_retaliation(&actor, &target, 4, PHSDAM_NOENGAGE) == DAM_NONEDEAD && !retaliations);
    }
    reset(effect::none, callback::dragon);
    SET_POS(&target, STAT_DEAD); target.only.npc = nullptr;
    set_fighting(&actor, &target); engage(&actor, &target);
    assert(!dragons && !actor.specials.fighting);
    set_fighting(nullptr, &target);
    puts("combat startup: lethal callbacks, extraction/reuse, movement, disarm, normal attacks and retaliation results passed");
}
'''

build = ROOT / 'bin/tests'
build.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix='combat-start-', dir=build) as temporary:
    cpp, binary = Path(temporary) / 'harness.cpp', Path(temporary) / 'harness'
    cpp.write_text(PRELUDE + PRODUCTION + WRAPPERS + DRIVER)
    subprocess.run(['g++', '-std=c++20', '-g', '-Og', '-Wall', '-Wextra', '-Werror',
                    '-Isrc', '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                    '-fno-pie', '-no-pie', str(cpp),
                    str(ROOT / 'src/combat/attack_continuation.c'), str(HARNESS_STUBS),
                    '-o', str(binary)], cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True, timeout=30)
