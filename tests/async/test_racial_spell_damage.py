#!/usr/bin/env python3
"""Match racial spell properties to all twelve production damage types.

The real property initializer and racial modifier predicate run together.
Distinct factors expose adjacent-slot lookups; neutral defaults, Earth, invalid
types and race bounds are covered without changing spell balance or combat rules.
"""

from pathlib import Path
import os
import subprocess
import tempfile

from _paths import ROOT, extract_function, source


fight = source("fight.c").read_text()
names_start = fight.index("const char *spldam_types[")
type_names = fight[names_start:fight.index(";", names_start) + 1]
common = source("common.c").read_text()
race_start = common.index("const struct race_names race_names_table[LAST_RACE + 2] =")
race_names = common[race_start:common.index("\n};", race_start) + 3]
mods = source("dam_mods.c").read_text()
race_lookup = mods.index("const int casterRace = tutorial_mobile_mechanics_race(caster);")
start = mods.rfind("MAKE_DAM_MOD_PRED()", 0, race_lookup)
opening = mods.index("{", start)
depth, end = 1, opening + 1
while depth:
    depth += (mods[end] == "{") - (mods[end] == "}")
    end += 1
predicate = "dam_mod_predicate racial_modifier = " + mods[start:end] + ";\n"

PRELUDE = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "combat/damage.h"
#include "combat/dam_mods.h"
#include <cassert>
#include <cmath>
#include <cstdio>
#include <limits>
#include <map>
#include <string>

static std::map<std::string, float> properties;
float racial_spldam_offensive_factor[LAST_RACE + 1][LAST_SPLDAM_TYPE];
float racial_spldam_defensive_factor[LAST_RACE + 1][LAST_SPLDAM_TYPE];
float get_property(const char *name, double fallback) {
    auto found = properties.find(name);
    return found == properties.end() ? fallback : found->second;
}
// Tutorial identity dispatch is exercised by test_issue213_tutorial_combat.py.
int tutorial_mobile_mechanics_race(P_char ch) { return GET_RACE(ch); }
'''

DRIVER = r'''
struct damage_case { int type; const char *name; };
static const damage_case cases[] = {
    {SPLDAM_GENERIC, "generic"}, {SPLDAM_FIRE, "fire"}, {SPLDAM_COLD, "cold"},
    {SPLDAM_LIGHTNING, "lightning"}, {SPLDAM_GAS, "gas"}, {SPLDAM_ACID, "acid"},
    {SPLDAM_NEGATIVE, "negative"}, {SPLDAM_HOLY, "holy"}, {SPLDAM_PSI, "psionic"},
    {SPLDAM_SPIRIT, "spiritual"}, {SPLDAM_SOUND, "sound"}, {SPLDAM_EARTH, "earth"},
};
static char_data caster{}, victim{};
static void check(int type, double expected, dam_mod_type expected_type = dam_mod_type::More) {
    damage_mod result{dam_mod_type::None, 0};
    racial_modifier(&caster, &victim, 200, type, 0, &result, nullptr);
    if (result.type != expected_type || std::abs(result.mod - expected) > .000001) {
        std::fprintf(stderr, "damage type %d: modifier %.6f, expected %.6f\n",
                     type, result.mod, expected);
        std::abort();
    }
}
int main() {
    static_assert(sizeof(cases) / sizeof(cases[0]) == LAST_SPLDAM_TYPE);
    int ordinal = 0;
    for (const auto &entry : cases) {
        ++ordinal;
        // Binary fractions keep exact, distinct expectations for every property slot.
        properties[std::string("damage.spellTypeMod.offensive.racial.Human.") + entry.name]
            = 1 + ordinal / 16.f;
        properties[std::string("damage.spellTypeMod.defensive.racial.Orc.") + entry.name]
            = .5f + ordinal / 32.f;
    }
    const std::string last_race = race_names_table[LAST_RACE].no_spaces;
    properties["damage.spellTypeMod.offensive.racial." + last_race + ".earth"] = 1.5f;
    properties["damage.spellTypeMod.defensive.racial." + last_race + ".earth"] = .75f;
    update_racial_dam_factors();
    ordinal = 0;
    for (const auto &entry : cases) {
        ++ordinal;
        const double offense = ordinal / 16.0;
        const double defense = -.5 + ordinal / 32.0;
        caster.player.race = RACE_HUMAN; victim.player.race = RACE_NONE;
        check(entry.type, offense);
        caster.player.race = RACE_NONE; victim.player.race = RACE_ORC;
        check(entry.type, defense);
        caster.player.race = RACE_HUMAN; victim.player.race = RACE_ORC;
        check(entry.type, offense + defense); // retain the existing combination rule
        caster.player.race = victim.player.race = RACE_BARBARIAN;
        check(entry.type, 0); // an unconfigured race still defaults to neutral
    }
    caster.player.race = victim.player.race = LAST_RACE;
    check(SPLDAM_EARTH, .25);
    caster.player.race = RACE_HUMAN; victim.player.race = RACE_ORC;
    for (int type : {std::numeric_limits<int>::min(), -1, 0, LAST_SPLDAM_TYPE + 1,
                     std::numeric_limits<int>::max()})
        check(type, 0, dam_mod_type::None);
    for (int race : {RACE_NONE, LAST_RACE + 1}) {
        caster.player.race = race; victim.player.race = RACE_ORC;
        check(SPLDAM_COLD, -.5 + 3 / 32.0);
        caster.player.race = RACE_HUMAN; victim.player.race = race;
        check(SPLDAM_COLD, 3 / 16.0);
        caster.player.race = victim.player.race = race;
        check(SPLDAM_COLD, 0, dam_mod_type::None);
    }
    std::puts("PASS racial spell properties: all 12 types, offense/defense, neutral defaults, Earth and bounds");
}
'''

production = race_names + type_names + extract_function("fight.c", "void update_racial_dam_factors(")
out = ROOT / "bin/tests"
out.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="racial-spell-", dir=out) as temporary:
    cpp, binary = Path(temporary) / "test.cpp", Path(temporary) / "test"
    cpp.write_text(PRELUDE + production + predicate + DRIVER)
    subprocess.run([
        "g++", "-std=c++20", "-g", "-Wall", "-Wextra", "-Werror", "-Isrc",
        "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-fno-pie", "-no-pie",
        str(cpp), "-o", str(binary),
    ], cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True, timeout=30,
                   env={**os.environ, "ASAN_OPTIONS": "detect_leaks=0",
                        "UBSAN_OPTIONS": "halt_on_error=1:print_stacktrace=1"})
