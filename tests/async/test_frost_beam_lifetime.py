#!/usr/bin/env python3
"""Execute Frost Beam across damage that extracts either participant.

The spell and racial lookup are production code. Damage and saving throws are
controlled boundaries so every death outcome and nonlethal effect is exercised.
"""

from pathlib import Path
import os
import subprocess
import tempfile

from _paths import ROOT, extract_function


PRELUDE = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "combat/damage.h"
#include "magic/spells.h"
#include "net/comm.h"
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>

static index_data profiles[1]{};
P_index mob_index = profiles;
static int deaths, damage_branch, saves, effects, message_count, stopped, merciful, damage_calls;
static bool save_success;
static uint damage_flags;

[[noreturn]] int panic_corruption_int(const char *, const char *, ...) { std::abort(); }
void logit(const char *, const char *, ...) {}
int number(int lo, int hi) { return lo == 0 && hi == 99 ? (damage_branch == 2 ? 99 : 0) : lo; }
void act(const char *, int, P_char ch, P_obj, void *target, int) {
    assert(IS_ALIVE(ch));
    assert(!target || IS_ALIVE(static_cast<P_char>(target)));
    ++message_count;
}
void send_to_char(const char *, P_char ch) { assert(IS_ALIVE(ch)); ++message_count; }
void stop_fighting(P_char ch) { assert(IS_ALIVE(ch)); ++stopped; }
void StopMercifulAttackers(P_char ch) { assert(IS_ALIVE(ch)); ++merciful; }
affected_type *affect_to_char(P_char ch, affected_type *af) {
    assert(IS_ALIVE(ch));
    assert(af->type == SPELL_MINOR_PARALYSIS && af->flags == AFFTYPE_SHORT);
    assert(af->duration == static_cast<int>(56 * WAIT_SEC * 0.75));
    assert(af->bitvector2 == AFF2_MINOR_PARALYSIS);
    ++effects;
    return af;
}
static void extract(P_char ch) {
    SET_POS(ch, POS_STANDING + STAT_DEAD);
    ch->in_room = NOWHERE;
    // free_char releases the substorage now and the outer character later.
    if (IS_NPC(ch)) ch->only.npc = nullptr;
    else ch->only.pc = nullptr;
}
int spell_damage(P_char ch, P_char victim, double dam, int type, uint flags,
                 damage_messages *, int *) {
    assert(IS_ALIVE(ch) && IS_ALIVE(victim));
    assert(dam == 56 * 14 + 10 && type == SPLDAM_COLD);
    ++damage_calls;
    damage_flags = flags;
    if (deaths & 1) extract(victim);
    if (deaths & 2) extract(ch);
    return deaths == 3 ? DAM_BOTHDEAD : deaths == 2 ? DAM_CHARDEAD :
           deaths == 1 ? DAM_VICTDEAD : DAM_NONEDEAD;
}
'''

SAVE = r'''
bool NewSaves(P_char ch, int type, int mod) {
    assert(type == SAVING_PARA && mod == 0);
    // The real save checks racial innates. This is where the core faulted
    // when the spell continued with an extracted NPC's null only.npc pointer.
    volatile int race = tutorial_mobile_mechanics_race(ch);
    (void)race;
    assert(IS_ALIVE(ch));
    ++saves;
    return save_success;
}
'''

CASES = r'''
static void run(bool npc_actor, bool npc_target, bool fighting) {
    char_data actor{}, target{};
    pc_only_data actor_pc{}, target_pc{};
    npc_only_data actor_npc{}, target_npc{};
    actor.only.pc = &actor_pc; target.only.pc = &target_pc;
    if (npc_actor) { actor.specials.act = ACT_ISNPC; actor.only.npc = &actor_npc; }
    if (npc_target) { target.specials.act = ACT_ISNPC; target.only.npc = &target_npc; }
    actor.player.level = 56;
    actor.player.m_class = CLASS_ETHERMANCER;
    actor.player.spec = damage_branch == 0 ? SPEC_FROSTMAGUS : 3;
    actor.player.race = target.player.race = RACE_HUMAN;
    profiles[0].virtual_number = 9308;
    actor.in_room = target.in_room = 1;
    SET_POS(&actor, POS_STANDING + STAT_NORMAL);
    SET_POS(&target, POS_STANDING + STAT_NORMAL);
    if (fighting) target.specials.fighting = &actor;
    saves = effects = message_count = stopped = merciful = damage_calls = 0;
    spell_frost_beam(56, &actor, nullptr, SPELL_TYPE_SPELL, &target, nullptr);
    assert(damage_calls == 1);
    assert(damage_flags == (damage_branch == 2 ? 0u : SPLDAM_NOSHRUG));
    if (deaths) {
        assert(saves == 0 && effects == 0 && message_count == 3);
        assert(stopped == 0 && merciful == 0);
    } else {
        assert(saves == 1 && effects == !save_success);
        assert(message_count == (save_success ? 3 : 5));
        assert(stopped == (!save_success && fighting));
        assert(merciful == !save_success);
    }
}

int main() {
    for (damage_branch = 0; damage_branch < 3; ++damage_branch)
        for (deaths = 0; deaths < 4; ++deaths)
            for (bool npc_actor : {false, true})
                for (bool npc_target : {true, false})
                    for (bool fighting : {false, true})
                        for (bool saved : {false, true}) {
                            save_success = saved;
                            run(npc_actor, npc_target, fighting);
                        }
    puts("Frost Beam lifetime: 192 death/survival, damage-branch, save and combat cases passed");
}
'''

production = extract_function("specs.ailvio.c", "int tutorial_mobile_mechanics_race(")
production += SAVE + extract_function("ethermancer.c", "void spell_frost_beam(")
directory = ROOT / "bin/tests"
directory.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="frost-beam-", dir=directory) as temporary:
    cpp = Path(temporary) / "frost_beam.cpp"
    binary = Path(temporary) / "frost_beam"
    cpp.write_text(PRELUDE + production + CASES)
    subprocess.run([
        "g++", "-std=c++20", "-g", "-Og", "-Wall", "-Wextra", "-Werror", "-Isrc",
        "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-fno-pie", "-no-pie",
        str(cpp), "-o", str(binary),
    ], cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True, timeout=30,
                   env={**os.environ, "ASAN_OPTIONS": "detect_leaks=0",
                        "UBSAN_OPTIONS": "halt_on_error=1:print_stacktrace=1"})
