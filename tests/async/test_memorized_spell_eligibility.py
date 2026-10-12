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
#include <cassert>
#include <cstdio>

Skill skills[MAX_SKILLS];
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
))
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
