#!/usr/bin/env python3
"""Saved prepared spells obey the current circle, including after a rebalance."""

from pathlib import Path
import re
import subprocess
import tempfile

from _paths import ROOT, HARNESS_STUBS, extract_function, source


registration = source("skills.c").read_text().split(
    'SPELL_CREATE_MSG("freedom of movement",', 1)[1].split("SKILL_CREATE(", 1)[0]
classes = re.findall(r"SPELL_ADD\((CLASS_\w+), (\d+)\)", registration)
assert len(classes) == 6 and all(circle == "11" for _, circle in classes)

prelude = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "magic/spells.h"
#include "classes/necromancy.h"
#include <cassert>
#include <cstdio>

Skill skills[MAX_SKILLS];
int numSkills;
char class_innates[LAST_INNATE + 2][CLASS_COUNT][5];
unsigned int class_innates_at_all[LAST_INNATE + 2];
char racial_innates[LAST_INNATE + 1][LAST_RACE + 1];
float get_property(const char *, double fallback) { return fallback; }
'''
production = "\n".join(extract_function(file, signature) for file, signature in (
    ("utility.c", "int BOUNDED(int a, int b, int c)"),
    ("utility.c", "int flag2idx(int flag)"),
    ("utility.c", "int GET_CLASS(P_char ch, uint m_class)"),
    ("utility.c", "int GET_PRIME_CLASS(P_char ch, uint m_class)"),
    ("utility.c", "int GET_SECONDARY_CLASS(P_char ch, uint m_class)"),
    ("utility.c", "ClassSkillInfo SKILL_DATA_ALL(P_char ch, int skill)"),
    ("memorize.c", "int get_max_circle(P_char ch)"),
    ("memorize.c", "int get_spell_circle(P_char ch, int spl)"),
    ("memorize.c", "void *has_memorized(P_char ch, int spell)"),
    ("memorize.c", "int knows_spell(P_char ch, int spell)"),
    ("skills.c", "void SPEC_SPELL_ADD("),
    ("skills.c", "void SPELL_ADD("),
    ("skills.c", "void SPEC_SKILL_ADD("),
    ("skills.c", "void SKILL_ADD("),
    ("affects.c", "struct affected_type *get_spell_from_char("),
    ("innates.c", "static int innate_char_race("),
    ("innates.c", "static int innate_unlock_level("),
    ("innates.c", "bool has_innate("),
))

# Replay the current registration statements, including all spec overrides, through
# the real registration functions. Expected circles below are independent of input.
grants = []
clean = re.sub(r"/\*.*?\*/|//[^\n]*", "", source("skills.c").read_text(), flags=re.S)
for block in re.split(r"\b(?:SPELL|SKILL)_CREATE(?:_MSG|_WITH_MESSAGES)?\(", clean)[1:]:
    match = re.match(r'"[^"]+",\s*((?:SPELL|SKILL)_\w+)', block)
    if not match:
        continue
    statements = re.findall(r"^\s*((?:SPEC_)?(?:SPELL|SKILL)_ADD\([^;]+;)", block, re.M)
    if not any("CLASS_CLERIC" in line for line in statements) and match[1] != "SPELL_VITAL_INTERCESSION":
        continue
    grants.append(f"numSkills = {match[1]}; skills[numSkills].targets = TAR_SPELL;\n" + "\n".join(statements))

cleric_driver = r'''
    REGISTER_CLERIC
    const int restored[][2] = {
        {SPELL_CAUSE_LIGHT, 1}, {SPELL_CAUSE_SERIOUS, 2}, {SPELL_CAUSE_CRITICAL, 3},
        {SPELL_EARTHQUAKE, 3}, {SPELL_DISPEL_EVIL, 3}, {SPELL_DISPEL_GOOD, 3},
        {SPELL_DESTROY_UNDEAD, 5}, {SPELL_HARM, 6}, {SPELL_FLAMESTRIKE, 6},
        {SPELL_HOLY_WORD, 9}, {SPELL_UNHOLY_WORD, 9}, {SPELL_FULL_HARM, 10},
        {SPELL_TAINT, 10}, {SPELL_NEG_ENERGY_BARRIER, 6},
        {SPELL_MIRACLE, 8}, {SPELL_TRUE_SEEING, 10}, {SPELL_DIVINE_WARDING, 11}
    };
    char_data cleric{};
    cleric.player.m_class = CLASS_CLERIC;
    cleric.player.race = RACE_HUMAN;
    affected_type saved{};
    saved.type = TAG_MEMORIZE;
    cleric.affected = &saved;
    const int levels[] = {25,26,29,30,31,35,36,40,41,45,46,50,51,56};
    for (int spec : {0, SPEC_HEALER, SPEC_HOLYMAN, SPEC_ZEALOT}) {
        cleric.player.spec = spec;
        for (int level : levels) {
            cleric.player.level = level;
            for (const auto &entry : restored) {
                assert(get_spell_circle(&cleric, entry[0]) == entry[1]);
                saved.modifier = entry[0];
                for (int flags : {0u, MEMTYPE_FULL}) {
                    saved.flags = flags;
                    assert(bool(knows_spell(&cleric, entry[0])) == (level >= 5 * (entry[1] - 1) + 1));
                }
            }
            saved.modifier = SPELL_VITAL_INTERCESSION;
            for (int flags : {0u, MEMTYPE_FULL}) {
                saved.flags = flags;
                assert(get_spell_circle(&cleric, SPELL_VITAL_INTERCESSION) == MAX_CIRCLE + 1);
                assert(!knows_spell(&cleric, SPELL_VITAL_INTERCESSION));
            }
            saved.modifier = SPELL_HOLY_INTERCESSION;
            for (int flags : {0u, MEMTYPE_FULL}) {
                saved.flags = flags;
                assert(get_spell_circle(&cleric, SPELL_HOLY_INTERCESSION) == MAX_CIRCLE + 1);
                assert(!knows_spell(&cleric, SPELL_HOLY_INTERCESSION));
            }
            assert(SKILL_DATA_ALL(&cleric, SKILL_KICK).maxlearn[spec] == (spec == SPEC_ZEALOT ? 90 : 40));
        }
    }
    // A fighter/Cleric still receives the lawful secondary spell circle (+1).
    cleric.player.spec = 0;
    cleric.player.m_class = CLASS_WARRIOR;
    cleric.player.secondary_class = CLASS_CLERIC;
    cleric.player.level = 56;
    assert(get_spell_circle(&cleric, SPELL_MIRACLE) == 9);
    saved.modifier = SPELL_VITAL_INTERCESSION;
    saved.flags = MEMTYPE_FULL;
    assert(!knows_spell(&cleric, SPELL_VITAL_INTERCESSION));
    cleric.affected = nullptr;
    puts("Cleric source grants: all restored offense, progression boundaries, saved full/pending spells, specs and multiclass passed");
'''.replace("REGISTER_CLERIC", "\n".join(grants))

expected_auras = {
    "HEALING": {("CLASS_PALADIN", "30", "0")},
    "PROTECTION": {
        ("CLASS_PALADIN", "1", "0"),
        ("CLASS_CLERIC", "1", "SPEC_HOLYMAN"),
        ("CLASS_CLERIC", "1", "SPEC_ZEALOT"),
        ("CLASS_ANTIPALADIN", "1", "0"),
    },
    "SPELL_PROTECTION": {
        ("CLASS_CLERIC", "1", "SPEC_HOLYMAN"),
        ("CLASS_CLERIC", "1", "SPEC_HEALER"),
    },
}
innate_source = source("innates.c").read_text()
for aura, expected in expected_auras.items():
    innate = f"INNATE_AURA_{aura}"
    actual = set(re.findall(
        rf"^\s*ADD_CLASS_INNATE\({innate}, (CLASS_\w+), (\d+), (\w+)\);",
        innate_source, re.M))
    assert actual == expected, (innate, actual)
    for cls, level, spec in sorted(actual):
        cleric_driver += f"class_innates[{innate}][flag2idx({cls}) - 1][{spec}] = {level};\n"
        cleric_driver += f"class_innates_at_all[{innate}] |= {cls};\n"
cleric_driver += r'''
    cleric.player.secondary_class = 0;
    cleric.player.m_class = CLASS_CLERIC;
    for (int spec : {0, SPEC_HEALER, SPEC_HOLYMAN, SPEC_ZEALOT}) {
        cleric.player.spec = spec;
        cleric.player.level = 30;
        assert(!has_innate(&cleric, INNATE_AURA_HEALING));
        assert(has_innate(&cleric, INNATE_AURA_PROTECTION) ==
               (spec == SPEC_HOLYMAN || spec == SPEC_ZEALOT));
        assert(has_innate(&cleric, INNATE_AURA_SPELL_PROTECTION) ==
               (spec == SPEC_HOLYMAN || spec == SPEC_HEALER));
    }
    cleric.player.spec = 0;
    cleric.player.m_class = CLASS_PALADIN;
    cleric.player.level = 29;
    assert(!has_innate(&cleric, INNATE_AURA_HEALING));
    cleric.player.level = 30;
    assert(has_innate(&cleric, INNATE_AURA_HEALING));
    puts("Cleric protection auras and Paladin level-30 Improved Healing entitlement passed");
'''
driver = r'''
int main() {
    const int spell = SPELL_FREEDOM_OF_MOVEMENT;
    skills[spell].targets = TAR_SPELL;
    const int classes[] = { CLASSES };
    for (int cls : classes) {
        auto &data = skills[spell].m_class[flag2idx(cls) - 1];
        for (int spec = 0; spec <= MAX_SPEC; ++spec) {
            data.rlevel[spec] = 11;
            data.maxlearn[spec] = 100;
        }
        char_data ch{};
        P_char caster = &ch;
        ch.player.m_class = cls;
        ch.player.race = RACE_HUMAN;
        affected_type saved{};
        saved.type = TAG_MEMORIZE;
        saved.modifier = spell;
        ch.affected = &saved;
        for (int level = 46; level <= 50; ++level) {
            ch.player.level = level;
            // A full slot restored from a pre-upgrade save must no longer cast.
            saved.flags = MEMTYPE_FULL;
            assert(has_memorized(&ch, spell));
            assert(knows_spell(&ch, spell) == 0);
            // Nor can changing pending/full state during rest bypass eligibility.
            saved.flags = 0;
            assert(knows_spell(&ch, spell) == 0);
            saved.flags = MEMTYPE_FULL;
            assert(knows_spell(&ch, spell) == 0);
        }
        ch.player.level = 51;
        assert(knows_spell(caster, spell) == (USES_SPELL_SLOTS(caster) ? 11 : -1));
        saved.flags = 0;
        assert(knows_spell(&ch, spell) == 11);
        // Existing level-appropriate prepared spells still take the prepared path.
        data.rlevel[0] = 10;
        ch.player.level = 46;
        saved.flags = MEMTYPE_FULL;
        assert(knows_spell(caster, spell) == (USES_SPELL_SLOTS(caster) ? 10 : -1));
        data.rlevel[0] = 11;
        ch.player.level = MINLVLIMMORTAL;
        assert(knows_spell(&ch, spell) == TRUE);
    }
    puts("Saved spell eligibility: levels 46-50 reject, level 51 accepts, across six classes");
}
'''.replace("CLASSES", ", ".join(cls for cls, _ in classes))
driver = driver.replace('    puts("Saved spell eligibility:', cleric_driver + '\n    puts("Saved spell eligibility:')

# The real cast path must reject a zero result before handling the prepared (-1) path.
casting = source("sparser.c").read_text()
assert "if (!(circle = knows_spell(ch, spl)))" in casting

build = ROOT / "bin/tests"
build.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="memorized-eligibility-", dir=build) as directory:
    cpp, binary = Path(directory) / "harness.cpp", Path(directory) / "harness"
    cpp.write_text(prelude + production + driver)
    subprocess.run([
        "g++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
        "-fsanitize=address,undefined", "-fno-pie", "-no-pie",
        "-I" + str(ROOT / "src"), str(cpp), str(HARNESS_STUBS), "-o", str(binary),
    ], check=True, timeout=120)
    subprocess.run([str(binary)], check=True, timeout=120)
