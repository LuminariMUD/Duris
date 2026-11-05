#!/usr/bin/env python3
"""Exercise dissonance's real handler with crowded rooms and per-target dispatch."""
from pathlib import Path
import subprocess
import tempfile
from _paths import ROOT, extract_function

fixture = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "magic/spells.h"
#include "net/comm.h"
#include <cassert>
#include <cstdio>
#include <cstring>
static room_data room{};
P_room world = &room;
static char_data caster{}, master{}, targets[64]{};
static int checked, rolls, freed, scheduled, stopped, lagged, pet_roll = 308;
static bool eligible = true, allied;
int GET_CHAR_SKILL_P(P_char, int) { return 60; }
bool should_area_hit(P_char, P_char) { ++checked; return eligible; }
bool grouped(P_char, P_char) { return allied; }
P_char get_linked_char(P_char ch, ush_int) { return IS_NPC(ch) ? &master : nullptr; }
void clear_all_links(P_char) { ++freed; }
void stop_singing(P_char ch) { ++stopped; ch->specials.affected_by3 &= ~AFF3_SINGING; }
void CharWait(P_char, int delay) { assert(delay == PULSE_VIOLENCE); ++lagged; }
void act(const char *, int, P_char, P_obj, void *, int) {}
int number(int low, int high) {
    ++rolls;
    assert((low == 0 && high == 50) || (low == 1 && high == 2000));
    return low == 0 ? 0 : pet_roll;
}
nevent_schedule_result add_event(event_func, int delay, P_char, P_char, P_obj, int, const void *, int) {
    assert(delay == 90 * WAIT_SEC); ++scheduled; return {};
}
void event_pet_death(P_char, P_char, P_obj, void *) {}
''' + '\n'.join(extract_function('bard.c', signature) for signature in [
    'static int song_dissonance_power(',
    'static int song_dissonance_disharmonist_bonus(',
    'static int song_dissonance_target_lag(',
    'static int song_dissonance_pet_death_delay(',
    'void bard_dissonance(int /*l*/',
]) + r'''
static void setup(bool disharmonist) {
    caster.player.level = 50;
    caster.player.m_class = CLASS_BARD;
    caster.player.spec = disharmonist ? SPEC_DISHARMONIST : 0;
    caster.curr_stats.Cha = caster.curr_stats.Luk = 100;
    caster.specials.position = POS_STANDING | STAT_NORMAL;
    caster.specials.affected_by3 = AFF3_SINGING;
    for (int i = 0; i < 64; ++i) {
        targets[i] = {};
        targets[i].specials.position = POS_STANDING | STAT_NORMAL;
        targets[i].specials.act = ACT_ISNPC;
        targets[i].next_in_room = i == 63 ? nullptr : &targets[i + 1];
    }
    room.people = targets;
    checked = rolls = freed = scheduled = stopped = lagged = 0;
}
int main(int argc, char **argv) {
    assert(argc == 2);
    if (!std::strcmp(argv[1], "overflow")) {
        setup(true);
        // The old inner loop multiplies by 2.2 until float-to-int conversion overflows.
        bard_dissonance(50, &caster, targets, SONG_DISSONANCE);
    } else {
        for (bool disharmonist : {false, true}) {
            for (int threshold : {139, 140, 307, 308}) {
                setup(disharmonist);
                pet_roll = threshold;
                // Verses, echoes and riffs all dispatch once per target.
                for (auto &target : targets)
                    bard_dissonance(50, &caster, &target, SONG_DISSONANCE);
                const bool success = threshold < (disharmonist ? 308 : 140);
                assert(checked == 64 && rolls == 64);
                assert(freed == (success ? 64 : 0) && scheduled == freed);
            }
            // A single target call cannot stop a different singer in the room.
            setup(disharmonist);
            targets[1].specials.act = 0;
            targets[1].specials.affected_by3 = AFF3_SINGING;
            bard_dissonance(50, &caster, targets, SONG_DISSONANCE);
            assert(!stopped && !lagged && IS_AFFECTED3(&targets[1], AFF3_SINGING));
            bard_dissonance(50, &caster, &targets[1], SONG_DISSONANCE);
            assert(stopped == 1 && lagged == 1 && !IS_AFFECTED3(&targets[1], AFF3_SINGING));
        }
        // Refused targets and a stopped caster make no contest or pet rolls.
        for (int refusal = 0; refusal < 4; ++refusal) {
            setup(true);
            eligible = refusal != 0;
            allied = refusal == 1;
            if (refusal == 2) targets[0].player.level = 60, targets[0].specials.act = 0;
            if (refusal == 3) caster.specials.affected_by3 = 0;
            bard_dissonance(50, &caster, targets, SONG_DISSONANCE);
            assert(!rolls && !freed && !scheduled && !stopped && !lagged);
        }
    }
    std::printf("PASS dissonance: %s\n", argv[1]);
}
'''

out = ROOT / 'bin/tests'
out.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix='dissonance-', dir=out) as temporary:
    cpp, binary = Path(temporary) / 'test.cpp', Path(temporary) / 'test'
    cpp.write_text(fixture)
    subprocess.run(['g++', '-std=c++20', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined,float-cast-overflow', '-fno-sanitize-recover=all',
                    '-g', '-Isrc', str(cpp), '-o', str(binary)], cwd=ROOT, check=True)
    results = [subprocess.run([str(binary), case], timeout=30).returncode
               for case in ('overflow', 'targets')]
    assert not any(results), results
