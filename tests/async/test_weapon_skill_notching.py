#!/usr/bin/env python3
"""Exercise weapon classification and real combat notching under ASan/UBSan.

The complete pv_common and notch_skill functions run together. Only unrelated
combat effects and services are stubbed; skill gains and their eligibility checks
use production code. Every weapon type is checked with and without the 2h flag.
"""
import re
import subprocess
import tempfile
from pathlib import Path

from _paths import ROOT, HARNESS_STUBS, extract_function, source


cpp = r'''
#include "abilities/abilities.h"
#include "core/prototypes.h"
#include "core/utils.h"
#include "classes/epic_skills.h"
#include "combat/grapple.h"
#include "cmd/interp.h"
#include "item/objmisc.h"
#include "magic/spells.h"
#include <cassert>
#include <cstdio>

static room_data rooms[1]{};
P_room world = rooms;
static index_data indexes[1]{};
P_index obj_index = indexes;
P_index mob_index = indexes;
Skill skills[MAX_SKILLS]{};
epic_teacher_skill epic_teachers[1]{};
static bool lowest_roll, defended;
static int defense_checks, hits, notch_messages, timers;

int number(int lo, int hi) { return lowest_roll ? lo : hi; }
int dice(int count, int sides) { return lowest_roll ? count : count * sides; }
const Rolls live_rolls = {dice, number};
int get_property(const char *, int fallback) { return fallback; }
bool chaos_mud_enabled() { return false; }
int GET_CHAR_SKILL_P(P_char ch, int skill) { return ch->only.pc->skills[skill].learned; }
bool SanityCheck(P_char, const char *) { return true; }
bool ac_can_see(P_char, P_char, bool) { return true; }
bool affect_timer(P_char, int, int tag) {
    assert(tag == TAG_PHYS_SKILL_NOTCH);
    ++timers;
    return true;
}
void send_to_char(const char *, P_char) { ++notch_messages; }
bool mangleSucceed(P_char, P_char, P_obj) { return false; }
int parrySucceed(P_char, P_char, P_obj) { return false; }
bool divine_blessing_parry(P_char, P_char) { return false; }
int blockSucceed(P_char, P_char, P_obj) { return false; }
int dodgeSucceed(P_char, P_char, P_obj) { ++defense_checks; return defended; }
int leapSucceed(P_char, P_char) { return false; }
int MonkRiposte(P_char, P_char, P_obj) { return false; }
bool hit(P_char, P_char, P_obj, int *) { ++hits; return true; }
void armlock_check(P_char, P_char) {}
int blindfighting_defense_threshold(P_char) { return 0; }
int devotion_zealot_bonus(int) { return 0; }
int zealot_regain_threshold(int) { return 0; }
int memorize_last_spell(P_char) { return 0; }
const char *get_god_name(P_char) { return "test god"; }
int is_char_in_room(P_char, int) { return true; }
int double_strike_threshold(P_char) { return 0; }
void double_strike(P_char, P_char, P_obj) { assert(false); }
'''
cpp += re.search(
    r"int proccing_slots\[\] = \{.*?\};", source("fight.c").read_text(), re.S
).group(0) + "\n"
for file, signature in (
    ("fight.c", "int required_weapon_skill(P_obj wpn)"),
    ("objmisc.c", "int getWeaponDamType(const int weaptype)"),
    ("guild.c", "static int learning_extra_notch_roll("),
    ("guild.c", "bool notch_skill(P_char ch, int skill, float chance)"),
    ("fight.c", "int pv_common(P_char ch, P_char opponent, const P_obj wpn, int *damAccumulator)"),
):
    cpp += extract_function(file, signature) + "\n"

cpp += r'''
static void check_notching(P_obj weapon, int skill) {
    char_data attacker{}, opponent{};
    pc_only_data pc{}, opponent_pc{};
    attacker.only.pc = &pc;
    opponent.only.pc = &opponent_pc;
    attacker.specials.position = opponent.specials.position = STAT_NORMAL + POS_STANDING;
    attacker.player.level = opponent.player.level = 50;
    attacker.player.m_class = CLASS_WARRIOR;
    attacker.specials.fighting = &opponent;
    opponent.specials.fighting = &attacker;
    attacker.in_room = opponent.in_room = 0;
    skills[skill].name = "test weapon skill";
    skills[skill].targets = TAR_PHYS;

    // A gain skips automatic defenses; a missed roll, cap or safe room does not.
    enum Scenario { GAIN, MISSED_ROLL, AT_CAP, SAFE_ROOM };
    for (Scenario scenario : {GAIN, MISSED_ROLL, AT_CAP, SAFE_ROOM}) {
        pc.skills[skill].learned = scenario == AT_CAP ? 100 : 40;
        pc.skills[skill].taught = 100;
        rooms[0].room_flags = scenario == SAFE_ROOM ? ROOM_SAFE : 0;
        lowest_roll = scenario != MISSED_ROLL;
        defended = true;
        defense_checks = hits = notch_messages = timers = 0;
        const int before = pc.skills[skill].learned;
        const bool gains = skill != 0 && scenario == GAIN;
        const int result = pv_common(&attacker, &opponent, weapon, nullptr);
        assert(result == gains);
        assert(pc.skills[skill].learned == before + gains);
        assert(pc.skills[skill].taught == 100);
        assert(notch_messages == gains && timers == gains);
        assert(hits == gains && defense_checks == !gains);
        // In particular, nunchucks must never train the flaying skill instead.
        for (int other = 1; other < MAX_SKILLS; ++other)
            if (other != skill) assert(pc.skills[other].learned == 0);
    }

    // Missing a notch still permits an ordinary hit if the defenses fail.
    rooms[0].room_flags = 0;
    pc.skills[skill].learned = 40;
    lowest_roll = false;
    defended = false;
    defense_checks = hits = notch_messages = timers = 0;
    assert(pv_common(&attacker, &opponent, weapon, nullptr));
    assert(pc.skills[skill].learned == 40);
    assert(hits == 1 && defense_checks == 1 && notch_messages == 0 && timers == 0);
}

int main() {
    struct WeaponCase { int type, one_handed, two_handed; };
    const WeaponCase cases[] = {
        {WEAPON_AXE, SKILL_1H_SLASHING, SKILL_2H_SLASHING},
        {WEAPON_DAGGER, SKILL_1H_PIERCING, 0},
        {WEAPON_FLAIL, SKILL_1H_FLAYING, SKILL_2H_FLAYING},
        {WEAPON_HAMMER, SKILL_1H_BLUDGEON, SKILL_2H_BLUDGEON},
        {WEAPON_LONGSWORD, SKILL_1H_SLASHING, SKILL_2H_SLASHING},
        {WEAPON_MACE, SKILL_1H_BLUDGEON, SKILL_2H_BLUDGEON},
        {WEAPON_SPIKED_MACE, SKILL_1H_BLUDGEON, SKILL_2H_BLUDGEON},
        {WEAPON_POLEARM, SKILL_1H_SLASHING, SKILL_REACH_WEAPONS},
        {WEAPON_SHORTSWORD, SKILL_1H_SLASHING, SKILL_2H_SLASHING},
        {WEAPON_CLUB, SKILL_1H_BLUDGEON, SKILL_2H_BLUDGEON},
        {WEAPON_SPIKED_CLUB, SKILL_1H_BLUDGEON, SKILL_2H_BLUDGEON},
        {WEAPON_STAFF, SKILL_1H_BLUDGEON, SKILL_2H_BLUDGEON},
        {WEAPON_2HANDSWORD, SKILL_1H_SLASHING, SKILL_2H_SLASHING},
        {WEAPON_WHIP, SKILL_1H_FLAYING, SKILL_2H_FLAYING},
        {WEAPON_SPEAR, SKILL_1H_PIERCING, SKILL_REACH_WEAPONS},
        {WEAPON_LANCE, SKILL_1H_BLUDGEON, SKILL_2H_BLUDGEON},
        {WEAPON_SICKLE, SKILL_1H_SLASHING, SKILL_2H_SLASHING},
        {WEAPON_TRIDENT, SKILL_1H_PIERCING, SKILL_REACH_WEAPONS},
        {WEAPON_HORN, SKILL_1H_PIERCING, 0},
        {WEAPON_NUMCHUCKS, SKILL_1H_BLUDGEON, SKILL_2H_BLUDGEON},
    };
    for (const auto &entry : cases) {
        for (bool two_handed : {false, true}) {
            obj_data weapon{};
            weapon.type = ITEM_WEAPON;
            weapon.value[0] = entry.type;
            weapon.short_description = const_cast<char *>("test weapon");
            weapon.extra_flags = two_handed ? ITEM_TWOHANDS : 0;
            const int skill = two_handed ? entry.two_handed : entry.one_handed;
            assert(required_weapon_skill(&weapon) == skill);
            if (entry.type == WEAPON_NUMCHUCKS) {
                assert(IS_BLUDGEON(&weapon) && !IS_FLAYING(&weapon));
                assert(getWeaponDamType(entry.type) == WEAPONTYPE_BLUDGEON);
            }
            check_notching(&weapon, skill);
        }
    }
    assert(required_weapon_skill(nullptr) == SKILL_UNARMED_DAMAGE);
    check_notching(nullptr, SKILL_UNARMED_DAMAGE);
    obj_data non_weapon{};
    non_weapon.type = ITEM_ARMOR;
    assert(required_weapon_skill(&non_weapon) == 0);
    check_notching(&non_weapon, 0);
    std::puts("PASS weapon skill notching: all 40 weapon/handedness combinations, "
              "unarmed and non-weapons; actual skill gains, caps, safe rooms and defenses");
}
'''

build_root = ROOT / "bin/tests"
build_root.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="weapon-skill-notching-", dir=build_root) as tmp:
    path, binary = Path(tmp) / "harness.cpp", Path(tmp) / "harness"
    path.write_text(cpp)
    subprocess.run(
        ["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-ffunction-sections",
         "-fdata-sections", "-Wl,--gc-sections", "-fsanitize=address,undefined",
         "-fno-sanitize-recover=all", "-fno-omit-frame-pointer", "-no-pie", "-Isrc",
         str(path), str(HARNESS_STUBS), "-o", str(binary)],
        cwd=ROOT, check=True,
    )
    subprocess.run([str(binary)], cwd=ROOT, check=True, timeout=30)
