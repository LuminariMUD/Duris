#!/usr/bin/env python3
"""Exercise critical surprise attacks across destructive nested hits."""

from pathlib import Path
import os
import subprocess
import tempfile

from _paths import ROOT, extract_function, source


fight = source("fight.c").read_text()
start = fight.index("\tif (sic == -1 && (notch_skill(ch, SKILL_CRITICAL_ATTACK,")
end = fight.index("\n\tif (has_innate(ch, INNATE_BATTLE_FRENZY)", start)
critical_branch = fight[start:end]

PRELUDE = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "combat/attack_continuation.h"
#include "combat/damage.h"
#include "magic/spells.h"
#include "net/comm.h"
#include <cassert>
#include <cstdio>
#include <cstdlib>

enum class mutation { none, kill_actor, kill_target, extract_actor, extract_target,
                      replace_actor, replace_target, move_actor, move_target,
                      move_height, drop_weapon, replace_weapon };
static mutation change;
static char_data actor{}, target{};
static pc_only_data actor_pc{}, target_pc{};
static npc_only_data actor_npc{}, target_npc{};
static obj_data primary{}, secondary{};
static index_data profiles[2]{};
static bool actor_listed, target_listed;
static P_obj expected_nested_weapon;
P_index mob_index = profiles;
P_obj object_list;
attack_hit_type attack_hit_text[11]{};

[[noreturn]] int panic_corruption_int(const char *, const char *, ...) { std::abort(); }
P_char find_character_by_runtime_id(uint64_t id) {
    if (actor_listed && id == actor.runtime_id) return &actor;
    if (target_listed && id == target.runtime_id) return &target;
    return nullptr;
}
int number(int low, int high) { return low == 0 && high == 3 ? 3 : low; }
bool affected_by_spell(P_char, int) { return false; }
void affect_from_char(P_char, int) {}
bool critical_disarm(P_char, P_char) { assert(false); return false; }
void act(const char *, int, P_char ch, P_obj, void *victim, int) {
    assert(IS_ALIVE(ch));
    assert(!victim || IS_ALIVE(static_cast<P_char>(victim)));
}
bool notch_skill(P_char, int skill, float) { return skill == SKILL_CRITICAL_ATTACK; }
int GET_CHAR_SKILL_P(P_char, int) { return 0; }
int get_property(const char *, int fallback) { return fallback; }

static void mutate() {
    switch (change) {
    case mutation::none: break;
    case mutation::kill_actor:
        SET_POS(&actor, POS_STANDING + STAT_DEAD); actor.only.pc = nullptr; break;
    case mutation::kill_target:
        SET_POS(&target, POS_STANDING + STAT_DEAD); target.only.pc = nullptr; break;
    case mutation::extract_actor: actor_listed = false; actor.only.pc = nullptr; break;
    case mutation::extract_target: target_listed = false; target.only.pc = nullptr; break;
    case mutation::replace_actor: ++actor.runtime_id; break;
    case mutation::replace_target: ++target.runtime_id; break;
    case mutation::move_actor: ++actor.in_room; break;
    case mutation::move_target: ++target.in_room; break;
    case mutation::move_height: ++target.specials.z_cord; break;
    case mutation::drop_weapon: actor.equipment[PRIMARY_WEAPON] = nullptr; break;
    case mutation::replace_weapon: ++primary.obj_uid; break;
    }
}
bool hit(P_char ch, P_char victim, P_obj weapon, int *) {
    assert(ch == &actor && victim == &target && weapon == expected_nested_weapon);
    mutate();
    return false;
}
'''

WRAPPER = r'''
static bool run_critical_branch(P_char ch, P_char victim, P_obj weapon) {
    const int sic = -1;
    const int msg = MSG_SLASH;
CRITICAL_BRANCH
    // This is the downstream lookup that faulted in the core. Without the
    // continuation check it dereferences released NPC storage after inner hit().
    (void)tutorial_mobile_mechanics_race(victim);
    return true;
}

static void reset(mutation effect, bool npc_actor, bool npc_target) {
    actor = {}; target = {}; primary = {}; secondary = {};
    actor.only.pc = &actor_pc; target.only.pc = &target_pc;
    if (npc_actor) { actor.specials.act = ACT_ISNPC; actor.only.npc = &actor_npc; }
    if (npc_target) { target.specials.act = ACT_ISNPC; target.only.npc = &target_npc; }
    actor.runtime_id = 10; target.runtime_id = 20;
    actor.in_room = target.in_room = 1;
    actor.player.race = target.player.race = RACE_HUMAN;
    SET_POS(&actor, POS_STANDING + STAT_NORMAL);
    SET_POS(&target, POS_STANDING + STAT_NORMAL);
    actor_npc.R_num = 0; target_npc.R_num = 1;
    profiles[0].virtual_number = profiles[1].virtual_number = 1000;
    primary.obj_uid = 100; secondary.obj_uid = 200;
    primary.next = &secondary; object_list = &primary;
    actor.equipment[PRIMARY_WEAPON] = &primary;
    actor.equipment[SECONDARY_WEAPON] = &secondary;
    expected_nested_weapon = &secondary;
    actor_listed = target_listed = true;
    change = effect;
}

int main() {
    for (bool npc_actor : {false, true}) for (bool npc_target : {false, true}) {
        for (auto effect : {mutation::none, mutation::kill_actor, mutation::kill_target,
                            mutation::extract_actor, mutation::extract_target,
                            mutation::replace_actor, mutation::replace_target,
                            mutation::move_actor, mutation::move_target,
                            mutation::move_height, mutation::drop_weapon,
                            mutation::replace_weapon}) {
            reset(effect, npc_actor, npc_target);
            assert(run_critical_branch(&actor, &target, &primary) ==
                   (effect == mutation::none));
        }
    }
    // The second core was the same nested hit with both attacks unarmed.
    reset(mutation::kill_target, true, true);
    actor.equipment[PRIMARY_WEAPON] = nullptr;
    actor.equipment[SECONDARY_WEAPON] = nullptr;
    expected_nested_weapon = nullptr;
    assert(!run_critical_branch(&actor, &target, nullptr));
    puts("critical surprise attack continuation checks passed");
}
'''.replace("CRITICAL_BRANCH", critical_branch)

production = "\n".join([
    extract_function("specs.ailvio.c", "int tutorial_mobile_mechanics_race("),
    extract_function("fight.c", "bool critical_attack("),
])

directory = ROOT / "bin/tests"
directory.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="critical-attack-", dir=directory) as temporary:
    cpp = Path(temporary) / "critical.cpp"
    binary = Path(temporary) / "critical"
    cpp.write_text(PRELUDE + production + WRAPPER)
    subprocess.run([
        "g++", "-std=c++20", "-g", "-Og", "-Isrc",
        "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-fno-pie", "-no-pie",
        str(cpp), str(ROOT / "src/combat/attack_continuation.c"), "-o", str(binary),
    ], cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True, timeout=30,
                   env={**os.environ, "ASAN_OPTIONS": "detect_leaks=0"})
