#!/usr/bin/env python3
"""Exercise dissonance's real handler with crowded rooms and per-target dispatch."""
from pathlib import Path
import subprocess
import tempfile
from _paths import ROOT, extract_function

fixture = r'''
#include "core/prototypes.h"
#include "abilities/abilities.h"
#include <map>
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
static std::map<P_char,int> immunity;
static int interrupted, interrupt_roll = 1;
bool affected_by_spell(P_char ch,int spell) { return spell == SONG_DISSONANCE && immunity.count(ch); }
void set_short_affected_by(P_char ch,int spell,int delay) {
    assert(spell == SONG_DISSONANCE && delay == 25*WAIT_SEC); immunity[ch] = delay;
}
void interrupt_spellcasting(P_char ch) { ++interrupted; REMOVE_BIT(ch->specials.affected_by2,AFF2_CASTING); }
void send_to_char(const char *,P_char) {}
int GET_CHAR_SKILL_P(P_char, int) { return 60; }
int BOUNDED(int low,int value,int high) { return MIN(high,MAX(low,value)); }
bool should_area_hit(P_char, P_char) { ++checked; return eligible; }
bool grouped(P_char, P_char) { return allied; }
P_char get_linked_char(P_char ch, ush_int) { return IS_NPC(ch) ? &master : nullptr; }
void clear_all_links(P_char) { ++freed; }
void stop_singing(P_char ch) { ++stopped; ch->specials.affected_by3 &= ~AFF3_SINGING; }
void CharWait(P_char, int delay) { assert(delay == PULSE_VIOLENCE); ++lagged; }
void act(const char *, int, P_char, P_obj, void *, int) {}
int number(int low, int high) {
    ++rolls;
    if (low == 1 && high == 4000) return interrupt_roll;
    assert((low == 0 && high == 50) || (low == 1 && high == 2000));
    return low == 0 ? 0 : pet_roll;
}
int dice(int count,int sides) { return count*sides; }
const Rolls live_rolls = {dice,number};
nevent_schedule_result add_event(event_func, int delay, P_char, P_char, P_obj, int, const void *, int) {
    assert(delay == 90 * WAIT_SEC); ++scheduled; return {};
}
void event_pet_death(P_char, P_char, P_obj, void *) {}
''' + '\n'.join(extract_function('bard.c', signature) for signature in [
    'bool player_bard(',
    'static int disharmonist_proc_roll(',
    'static int disharmonist_song_chance(',
    'static int song_dissonance_interrupt_chance(',
    'static int song_dissonance_interrupt_immunity(',
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
    checked = rolls = freed = scheduled = stopped = lagged = interrupted = 0;
    immunity.clear();
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
        // An echo reaches targets in the song's room after the bard has walked away.
        setup(false);
        pet_roll = 1;
        caster.in_room = 1;
        bard_dissonance(50, &caster, targets, SONG_DISSONANCE);
        assert(freed == 1 && scheduled == 1);
        // A pet whose master stayed elsewhere keeps its link.
        setup(false);
        pet_roll = 1;
        master.in_room = 1;
        bard_dissonance(50, &caster, targets, SONG_DISSONANCE);
        assert(!freed && !scheduled);
        master.in_room = 0;
        caster.in_room = 0;
        pet_roll = 308;
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
        // The opposed interrupt remains between 5 and 25%, with per-target immunity.
        setup(true); eligible = true; allied = false; caster.player.level = 51;
        targets[0].specials.act = targets[1].specials.act = 0;
        targets[0].specials.affected_by2 = targets[1].specials.affected_by2 = AFF2_CASTING;
        targets[0].curr_stats.Int = 511;
        assert(song_dissonance_interrupt_chance(&caster,&targets[0]) == 200);
        caster.curr_stats.Cha = 511;
        assert(song_dissonance_interrupt_chance(&caster,&targets[1]) == 1000);
        caster.curr_stats.Cha = 100;
        interrupt_roll = 201;
        bard_dissonance(51,&caster,&targets[0],SONG_DISSONANCE);
        assert(!interrupted && !lagged && immunity.empty());
        interrupt_roll = 200;
        targets[0].specials.affected_by3 = AFF3_SINGING;
        bard_dissonance(51,&caster,&targets[0],SONG_DISSONANCE);
        assert(interrupted == 1 && !lagged && immunity.size() == 1);
        assert(IS_AFFECTED3(&targets[0],AFF3_SINGING)); // No older singing-contest lag.
        targets[0].specials.affected_by3 = 0;
        targets[0].specials.affected_by2 = AFF2_CASTING;
        bard_dissonance(51,&caster,&targets[0],SONG_DISSONANCE);
        assert(interrupted == 1); // Cannot chain-interrupt this victim.
        bard_dissonance(51,&caster,&targets[1],SONG_DISSONANCE);
        assert(interrupted == 2 && immunity.size() == 2); // Independent enemy.
        for (int refusal = 0; refusal < 3; ++refusal) {
            setup(true); caster.player.level = refusal == 0 ? 50 : 56;
            if (refusal == 1) caster.specials.act = ACT_ISNPC;
            if (refusal == 2) caster.player.spec = SPEC_MINSTREL;
            targets[0].specials.act = 0; targets[0].specials.affected_by2 = AFF2_CASTING;
            bard_dissonance(56,&caster,&targets[0],SONG_DISSONANCE);
            assert(!interrupted && !lagged && immunity.empty());
            caster.specials.act = 0;
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
