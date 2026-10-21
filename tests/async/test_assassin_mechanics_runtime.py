#!/usr/bin/env python3
"""Run complete Awareness/backstab functions with real affect list operations.

Damage delivery, unrelated combat guards and stat recalculation are fixtures.
The checked-in properties, stat indexing, RNG boundaries, both weapon slots and
the recent-stab timer are exercised under ASan/UBSan.
"""

from pathlib import Path
import json
import os
import subprocess
import tempfile

from _paths import ROOT, HARNESS_STUBS, extract_function


PRELUDE = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "core/mm.h"
#include "magic/spells.h"
#include "world/events.h"
#include "world/db.h"
#include "net/comm.h"
#include "cmd/interp.h"
#include "combat/damage.h"
#include "combat/guard.h"
#include "item/objmisc.h"
#include <cassert>
#include <cstdio>
#include <cstring>
#include <string>
#include <unordered_map>
#include <vector>

static char_data attacker{}, defender{};
static int trained, stab_skill, critical_skill, fallback_hits, training_calls;
static bool upper_roll, kill_on_hit, leave_on_hit;
static std::vector<int> delivered_damage;
static mm_ds pool{};
mm_ds *dead_affect_pool = &pool;
static index_data objects[1]{};
index_data *obj_index = objects;
Skill skills[MAX_SKILLS]{};
static room_data rooms[3]{};
P_room world = rooms;

int number(int low, int high) { assert(low <= high); return upper_roll ? high : low; }
int BOUNDED(int low, int value, int high) { return value < low ? low : value > high ? high : value; }
int GET_CHAR_SKILL_P(P_char ch, int skill) {
    if (skill == SKILL_AWARENESS) return ch == &defender ? trained : 0;
    if (skill == SKILL_BACKSTAB) return ch == &attacker ? stab_skill : 0;
    if (skill == SKILL_CRITICAL_STAB) return ch == &attacker ? critical_skill : 0;
    return 0;
}
int GET_CLASS(P_char ch, uint cls) { return (ch->player.m_class & cls) != 0; }
bool notch_skill(P_char, int, float) { ++training_calls; return false; }
void CharWait(P_char, int) {}
void balance_affects(P_char) {}
void gmcp_char_affects(P_char) {}
int char_light(P_char) { return 0; }
int room_light(int, int) { return 0; }
void unlink_char_affect(P_char, affected_type *) { assert(false); }
void unlink_char_obj_affect(P_char, affected_type *) { assert(false); }
void event_web_spray(P_char, P_char, P_obj, void *) {}
void disarm_char_nevents(P_char, event_func_type) {}
void event_short_affect(P_char, P_char, P_obj, void *) {}
nevent_handle nevent_handle_from_event(P_nevent) { return {}; }
nevent_cancel_result nevent_cancel(nevent_handle) { return nevent_cancel_result::canceled; }
nevent_schedule_result add_event(event_func, int, P_char, P_char, P_obj, int, const void *, int) { return {}; }
void *_mm_get(mm_ds *, const char *, int) { return new affected_type{}; }
void mm_release(mm_ds *, void *p) { delete static_cast<affected_type *>(p); }
mm_ds *mm_create(const char *, size_t, size_t, unsigned) { return &pool; }
void all_affects(P_char ch, int add) {
    for (auto *af = ch->affected; af; af = af->next) {
        if (add) ch->specials.affected_by |= af->bitvector;
        else ch->specials.affected_by &= ~af->bitvector;
    }
}
int melee_damage(P_char, P_char victim, double dam, int, damage_messages *, int *) {
    delivered_damage.push_back(static_cast<int>(dam));
    if (kill_on_hit) SET_POS(victim, POS_PRONE + STAT_DEAD);
    if (leave_on_hit) attacker.in_room = 2;
    return kill_on_hit ? DAM_VICTDEAD : DAM_NONEDEAD;
}
int is_char_in_room(const P_char ch, int room) { return IS_ALIVE(ch) && ch->in_room == room; }
int char_in_list(const P_char ch) { return IS_ALIVE(ch); }
bool SanityCheck(P_char, const char *) { return true; }
bool can_hit_target(P_char, P_char) { return true; }
P_char guard_check(P_char, P_char victim) { return victim; }
int get_takedown_size(P_char) { return SIZE_MEDIUM; }
bool should_not_kill(P_char, P_char) { return false; }
int CanDoFightMove(P_char, P_char) { return true; }
P_char misfire_check(P_char, P_char victim, int) { return victim; }
bool ac_can_see(P_char, P_char, bool) { return true; }
bool has_innate(P_char, int) { return false; }
int on_front_line(P_char) { return true; }
void set_fighting(P_char, P_char) {}
void stop_fighting(P_char) {}
void guardian_spirits_messages(P_char, P_char) {}
bool hit(P_char, P_char, P_obj, int *) { ++fallback_hits; return false; }
void poison_lifeleak(int, P_char, char *, int, P_char, affected_type *) { assert(false); }
'''


def production():
    properties = {}
    for line in (ROOT / "lib/duris.properties").read_text().splitlines():
        if line.startswith(("backstab.", "skill.notch.offensive=")):
            key, value = line.split("=", 1)
            properties[key] = float(value)
    code = "static const std::unordered_map<std::string, double> properties = {\n"
    code += ",\n".join("{" + json.dumps(key) + "," + str(value) + "}"
                      for key, value in properties.items()) + "};\n"
    code += '''float get_property(const char *key, double fallback) {
        auto found = properties.find(key);
        return found == properties.end() ? fallback : found->second;
    }
    int get_property(const char *key, int fallback) {
        return static_cast<int>(get_property(key, static_cast<double>(fallback)));
    }\n'''
    code += "\n".join(extract_function(file, signature) for file, signature in [
        ("utility.c", "int STAT_INDEX(int v)\n{\n\t"),
        ("affects.c", "bool affected_by_spell("),
        ("affects.c", "struct affected_type *get_spell_from_char("),
        ("affects.c", "struct affected_type *affect_to_char("),
        ("affects.c", "void affect_remove("),
        ("affects.c", "void affect_from_char("),
        ("affects.c", "void set_short_affected_by("),
        ("new_skills.c", "void do_awareness("),
        ("actoff.c", "bool single_stab("),
        ("actoff.c", "bool backstab(P_char ch, P_char victim)"),
    ])
    return code


DRIVER = r'''
static void clear(P_char ch) { while (ch->affected) affect_remove(ch, ch->affected); }
static void reset() {
    clear(&attacker); clear(&defender);
    attacker = {}; defender = {};
    for (auto *ch : {&attacker, &defender}) {
        SET_POS(ch, POS_STANDING + STAT_NORMAL);
        ch->in_room = 1;
        ch->player.level = 56;
        ch->curr_stats.Int = ch->curr_stats.Dex = ch->curr_stats.Str = 100;
        ch->curr_stats.Agi = ch->curr_stats.Luk = 100;
    }
    attacker.player.m_class = CLASS_ROGUE;
    attacker.player.spec = SPEC_ASSASSIN;
    attacker.points.damroll = 100;
    trained = 80; stab_skill = 100; critical_skill = 0;
    upper_roll = kill_on_hit = leave_on_hit = false;
    fallback_hits = training_calls = 0;
    delivered_damage.clear();
}
static void add_affect(int type, unsigned long bits = 0) {
    affected_type af{}; af.type = type; af.bitvector = bits;
    affect_to_char(&defender, &af);
}
static obj_data weapon() {
    obj_data obj{};
    obj.type = ITEM_WEAPON; obj.value[0] = WEAPON_DAGGER;
    obj.value[1] = 4; obj.value[2] = 6;
    obj.value[3] = WEAPONTYPE_PIERCE;
    return obj;
}
static void awareness() {
    reset();
    const int skills[] = {1, 45, 60, 70, 74, 75, 80, 100};
    // INT/DEX 100 and level 56 give base 39, then skill scales before division.
    const int low[] = {0, 11, 15, 18, 19, 19, 20, 26};
    const int high[] = {0, 23, 31, 36, 38, 39, 41, 52};
    for (int i = 0; i < 8; ++i) for (bool upper : {false, true}) {
        trained = skills[i]; upper_roll = upper;
        do_awareness(&defender, nullptr, 0);
        auto *af = get_spell_from_char(&defender, SKILL_AWARENESS);
        assert(af && !af->next);
        assert(af->modifier == (upper ? high[i] : low[i]));
        assert(af->duration == (upper ? 1 + 7 * trained / 75 : 1));
        assert(IS_AFFECTED(&defender, AFF_SKILL_AWARE));
        assert(!IS_AFFECTED(&defender, AFF_AWARE));
    }
    reset(); trained = 0;
    do_awareness(&defender, nullptr, 0); assert(!defender.affected);
    trained = 80; defender.curr_stats.Int = 50;
    do_awareness(&defender, nullptr, 0);
    assert(defender.affected->duration == 0);
    affect_remove(&defender, defender.affected);
    assert(!IS_AFFECTED(&defender, AFF_SKILL_AWARE));
    reset(); add_affect(SKILL_AWARENESS, AFF_AWARE);
    do_awareness(&defender, nullptr, 0);
    do_awareness(&defender, nullptr, 0);
    assert(defender.affected && defender.affected->next && !defender.affected->next->next);
    assert(IS_AFFECTED(&defender, AFF_AWARE) && IS_AFFECTED(&defender, AFF_SKILL_AWARE));
    affect_remove(&defender, defender.affected);
    assert(IS_AFFECTED(&defender, AFF_AWARE) && !IS_AFFECTED(&defender, AFF_SKILL_AWARE));
}
static int stab(int race, int aware, bool critical = false, bool recent = false,
                bool knocked_out = false, int ward = 0, bool high = false, int intelligence = 100) {
    reset(); attacker.player.race = race;
    defender.curr_stats.Int = intelligence;
    if (aware & 1) add_affect(SKILL_AWARENESS, AFF_AWARE);
    if (aware & 2) do_awareness(&defender, nullptr, 0);
    if (recent) add_affect(SKILL_BACKSTAB);
    if (knocked_out) defender.specials.affected_by |= AFF_KNOCKED_OUT;
    if (ward) add_affect(ward);
    critical_skill = critical ? 100 : 0;
    upper_roll = high;
    auto obj = weapon();
    assert(!single_stab(&attacker, &defender, &obj));
    assert(delivered_damage.size() == 1);
    if (ward) assert(!affected_by_spell(&defender, ward));
    return delivered_damage[0];
}
static void mitigation() {
    int normal = stab(RACE_HUMAN, 0);
    int critical = stab(RACE_HUMAN, 0, true);
    assert(critical == int(normal + normal * properties.at("backstab.CriticalStab.Multiplier")));
    for (int race : {RACE_HUMAN, RACE_MOUNTAIN, RACE_DUERGAR}) {
        for (int aware = 0; aware < 4; ++aware) {
            const bool mitigates = aware != 0;
            assert(stab(race, aware) == (mitigates ? int(normal * .6) : normal));
            assert(stab(race, aware, true) == critical);
            assert(stab(race, aware, false, true) == int(normal * .25));
            assert(stab(race, aware, true, true) == int(int(normal * .25) * 1.3));
            assert(stab(race, aware, false, false, true) == MAX(80, normal));
        }
    }
    for (int ward : {SPELL_STONE_SKIN, SPELL_DRAKESCALE_AEGIS, SPELL_SHADOW_SHIELD,
                     SPELL_BIOFEEDBACK, SPELL_VINES}) {
        assert(stab(RACE_HUMAN, 3, false, false, false, ward) == 1);
        assert(stab(RACE_HUMAN, 3, true, false, false, ward) == 1);
    }
    // Awareness still needs to win its INT/opportunity check.
    for (int aware : {1, 2, 3}) {
        assert(stab(RACE_HUMAN, aware, false, false, false, 0, true, 40) ==
               stab(RACE_HUMAN, 0, false, false, false, 0, true, 40));
    }
    printf("matched stab: normal=%d aware=%d critical=%d recent-critical=%d\n", normal,
           stab(RACE_HUMAN, 1), critical, stab(RACE_HUMAN, 1, true, true));
}
static void callers() {
    reset();
    auto first = weapon(), second = weapon();
    attacker.equipment[WIELD] = &first;
    attacker.equipment[SECONDARY_WEAPON] = &second;
    assert(backstab(&attacker, &defender));
    assert(delivered_damage.size() == 2 && delivered_damage[0] == delivered_damage[1]);
    assert(affected_by_spell(&defender, SKILL_BACKSTAB));
    reset(); do_awareness(&defender, nullptr, 0);
    attacker.equipment[WIELD] = &first; attacker.equipment[SECONDARY_WEAPON] = &second;
    assert(backstab(&attacker, &defender));
    assert(delivered_damage.size() == 2 && delivered_damage[0] == 40 && delivered_damage[1] == 40);
    reset(); attacker.equipment[WIELD] = &first;
    attacker.equipment[SECONDARY_WEAPON] = &second;
    upper_roll = true;
    assert(backstab(&attacker, &defender));
    assert(delivered_damage.empty() && fallback_hits == 2);
    reset(); attacker.equipment[WIELD] = &first; kill_on_hit = true;
    assert(backstab(&attacker, &defender)); assert(delivered_damage.size() == 1);
    reset(); attacker.equipment[WIELD] = &first; leave_on_hit = true;
    assert(backstab(&attacker, &defender)); assert(delivered_damage.size() == 1);
}
int main() {
    awareness(); mitigation(); callers(); reset();
    puts("Assassin Awareness/backstab native regressions passed");
}
'''


def main():
    build = ROOT / "bin/tests"
    build.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="assassin-mechanics-", dir=build) as directory:
        cpp, binary = Path(directory) / "harness.cpp", Path(directory) / "harness"
        cpp.write_text(PRELUDE + production() + DRIVER)
        subprocess.run([
            "g++", "-std=c++20", "-g", "-Wall", "-Wextra", "-Werror",
            "-Wno-unused-parameter", "-ftrivial-auto-var-init=pattern",
            "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-fno-pie", "-no-pie",
            "-ffunction-sections", "-fdata-sections", "-I" + str(ROOT / "src"),
            str(cpp), str(HARNESS_STUBS), "-Wl,--gc-sections", "-o", str(binary),
        ], check=True)
        subprocess.run([str(binary)], check=True, env={**os.environ,
            "ASAN_OPTIONS": "detect_leaks=1:halt_on_error=1",
            "UBSAN_OPTIONS": "halt_on_error=1:print_stacktrace=1"})


if __name__ == "__main__":
    main()
