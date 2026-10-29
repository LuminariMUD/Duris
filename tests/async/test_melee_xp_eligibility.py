#!/usr/bin/env python3
"""Exercise periodic melee XP through the production combat loop."""

from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, HARNESS_STUBS, extract_function


HARNESS = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "core/utility.h"
#include "core/files.h"
#include "world/db.h"
#include "world/weather.h"
#include "magic/spells.h"
#include "combat/grapple.h"
#include "item/item_actions.h"
#include "net/comm.h"
#include <cassert>
#include <cmath>
#include <cstdio>
#include <set>

#define MAX_ATTACKS 256
room_data rooms[2]{};
P_room world = rooms;
time_info_data time_info{};
P_char combat_list = nullptr, combat_next_ch = nullptr;
int pulse = 0;
int awards = 0, attacks_made = 0, spell = 0;
bool item_busy = false, battlemage = false;
bool affected_by_spell(P_char, int type) {
    return type == spell || (battlemage && type == SPELL_BATTLEMAGE);
}
bool item_action_active(P_char) { return item_busy; }
bool IS_OUTDOORS(int) { return false; }
bool SanityCheck(P_char ch, const char *) { return IS_ALIVE(ch) && ch->in_room != NOWHERE; }
void stop_fighting(P_char ch) { ch->specials.fighting = nullptr; }
void extract_char(P_char) { assert(false); }
int gain_exp(P_char ch, P_char victim, int amount, int type) {
    assert(IS_PC(ch) && IS_NPC(victim) && type == EXP_MELEE && amount > 0);
    ++awards;
    return amount;
}
void startPvP(P_char, bool) {}
P_char misfire_check(P_char, P_char target, int) { return target; }
void affect_from_char(P_char, int) {}
void send_to_char(const char *, P_char) {}
void act(const char *, int, P_char, P_obj, void *, int) {}
int get_property(const char *, int fallback) { return fallback; }
float get_property(const char *, double fallback) { return fallback; }
int number(int low, int) { return low; }
int calculate_attacks(P_char, int slots[]) { slots[0] = PRIMARY_WEAPON; return 1; }
bool notch_skill(P_char, int, float) { return false; }
int GET_CHAR_SKILL_P(P_char, int) { return 0; }
int GET_CLASS(P_char ch, unsigned int cls) { return ch->player.m_class & cls; }
int IS_MORPH(P_char) { return false; }
bool is_dragoon_mounted(P_char) { return false; }
bool has_innate(P_char, int) { return false; }
bool frightening_presence(P_char, P_char) { return false; }
void set_short_affected_by(P_char, int, int) {}
int is_char_in_room(P_char ch, int room) { return ch->in_room == room; }
bool monk_superhit(P_char, P_char, int *) { assert(false); return false; }
int pv_common(P_char, P_char, const P_obj, int *) { ++attacks_made; return 0; }
void MobCombat(P_char) {}
void appear(P_char, bool) {}
'''

CASES = r'''
int main() {
    char_data attacker{}, player{};
    npc_only_data npc{};
    pc_only_data pc{};
    attacker.only.npc = &npc;
    player.only.pc = &pc;
    combat_list = &attacker;
    rooms[0].room_flags = ROOM_INDOORS;
    auto reset = [&] {
        attacker.specials = {};
        player.specials = {};
        attacker.specials.act = ACT_ISNPC;
        attacker.specials.position = player.specials.position = STAT_NORMAL;
        attacker.specials.fighting = &player;
        player.specials.fighting = &attacker;
        attacker.player.level = player.player.level = 20;
        attacker.in_room = player.in_room = 0;
        attacker.specials.combat_tics = 5;
        attacker.specials.base_combat_round = PULSE_VIOLENCE;
        item_busy = battlemage = false;
        spell = awards = attacks_made = 0;
        pulse = PULSE_VIOLENCE;
    };
    reset();
    perform_violence();
    assert(awards == 1 && attacks_made == 0);
    assert(attacker.specials.combat_tics == 4);
    ++pulse;
    perform_violence();
    assert(awards == 1);

    // Fight validity is checked even while an attack timer is counting down.
    reset();
    player.specials.position = STAT_DEAD;
    perform_violence();
    assert(awards == 0);
    reset();
    player.in_room = 1;
    perform_violence();
    assert(awards == 0 && !IS_FIGHTING(&attacker) && !IS_FIGHTING(&player));

    // Attack-blocking states cannot produce periodic XP on either timer path.
    for (int ticks : {0, 5}) {
        for (int state = 0; state < 7; ++state) {
            reset();
            attacker.specials.combat_tics = ticks;
            switch (state) {
            case 0: spell = TAG_GRAPPLE; break;
            case 1: spell = SKILL_BEARHUG; break;
            case 2: attacker.specials.affected_by2 = AFF2_MAJOR_PARALYSIS; break;
            case 3: attacker.specials.affected_by2 = AFF2_MINOR_PARALYSIS; break;
            case 4: attacker.specials.affected_by2 = AFF2_CASTING; break;
            case 5: item_busy = true; break;
            case 6: attacker.specials.affected_by5 = AFF5_NOT_OFFENSIVE; break;
            }
            perform_violence();
            assert(awards == 0 && attacks_made == 0);
        }
        reset();
        attacker.specials.combat_tics = ticks;
        attacker.specials.affected_by2 = AFF2_CASTING;
        battlemage = true;
        perform_violence();
        assert(awards == 1);
        assert(attacks_made == (ticks == 0 ? 1 : 0));
    }
    // Ordinary combat retains one reward per fixed pulse, independent of rounds.
    reset();
    for (pulse = 1; pulse <= 4 * PULSE_VIOLENCE; ++pulse) perform_violence();
    assert(awards == 4 && attacks_made > 0);
}
'''


def main() -> None:
    directory = ROOT / "bin" / "tests"
    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="melee-xp-", dir=directory) as temporary:
        program = Path(temporary) / "harness.cpp"
        binary = Path(temporary) / "harness"
        program.write_text(HARNESS + extract_function("utility.c", "bool FightingCheck(") +
                           extract_function("fight.c", "void perform_violence(") + CASES)
        subprocess.run([
            "g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-Isrc", "-I/usr/include/mysql",
            "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-fno-pie", "-no-pie",
            str(program), str(HARNESS_STUBS), "-o", str(binary),
        ], cwd=ROOT, check=True)
        subprocess.run([str(binary)], check=True, timeout=10)
    print("periodic melee XP eligibility passed")


if __name__ == "__main__":
    main()
