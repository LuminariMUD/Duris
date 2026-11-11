#!/usr/bin/env python3
"""Check the Nax classroom/reset and execute its ordinary spell teaching gates."""

from pathlib import Path
import re
import subprocess
import tempfile

from _paths import ROOT, HARNESS_STUBS, extract_function, source


def record(path, vnum):
    matches = re.findall(
        rf"^#{vnum}\n(.*?)(?=^#|\Z)", (ROOT / path).read_text(), re.M | re.S
    )
    assert len(matches) == 1, (path, vnum, len(matches))
    return matches[0]


landing = record("areas/wld/nax.wld", 37941)
classroom = record("areas/wld/nax.wld", 37945)
assert "D3\n~\n~\n0 0 37945\n" in landing
assert "D1\n~\n~\n0 0 37941\n" in classroom
assert re.sub(r"&\+.|&[nN]", "", classroom.split("~", 1)[0]) == "Chamber of Shifting Images"
assert classroom.split("~", 2)[2].lstrip().startswith("377 ")
zone = (ROOT / "areas/zon/nax.zon").read_text()
assert zone.splitlines()[2].split()[0] == "37945"
resets = [line.split("*", 1)[0].split() for line in zone.splitlines() if line.startswith("M ")]
assert [row for row in resets if row[2] == "37766"] == [
    ["M", "0", "37766", "1", "37945", "100", "0", "0", "0"]
]
fields = record("areas/mob/nax.mob", 37766).split("~", 4)
stats = fields[4].strip().splitlines()
flags = [int(value) for value in stats[0].split()[:-1]]
race = stats[1].split()
level = int(stats[2].split()[0])
assert len(flags) == 9 and not any(flags[1:]), "trainer must have no aggression or hidden affects"
assert race == ["TF", "14", "4194304", "0", "-1"] and level == 56

prelude = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "magic/spells.h"
#include <cassert>
#include <cstdio>
#include <set>
Skill skills[MAX_SKILLS];
int numSkills;
room_data rooms[1]{};
P_room world = rooms;
float get_property(const char *, double fallback) { return fallback; }
bool ac_can_see(P_char, P_char, bool) { return true; }
bool is_linked_to(P_char, P_char, ush_int) { return false; }
P_obj find_gh_library_book_obj(P_char) { return nullptr; }
void send_to_char(const char *, P_char) {}
void mobsay(P_char, const char *) {}
void logit(const char *, const char *, ...) {}
'''
production = "\n".join(extract_function(file, signature) for file, signature in (
    ("utility.c", "int BOUNDED(int a, int b, int c)"),
    ("utility.c", "int flag2idx(int flag)"),
    ("utility.c", "int GET_CLASS(P_char ch, uint m_class)"),
    ("utility.c", "int GET_PRIME_CLASS(P_char ch, uint m_class)"),
    ("utility.c", "int GET_SECONDARY_CLASS(P_char ch, uint m_class)"),
    ("utility.c", "ClassSkillInfo SKILL_DATA_ALL(P_char ch, int skill)"),
    ("utility.c", "int GET_LVL_FOR_SKILL(P_char ch, int skill)"),
    ("memorize.c", "int IS_CASTER(P_char ch)"),
    ("memorize.c", "int IS_SEMI_CASTER(P_char ch)"),
    ("memorize.c", "int get_max_circle(P_char ch)"),
    ("memorize.c", "int get_spell_circle(P_char ch, int spl)"),
    ("memorize.c", "void *has_memorized(P_char ch, int spell)"),
    ("memorize.c", "int knows_spell(P_char ch, int spell)"),
    ("skills.c", "void SPEC_SPELL_ADD("),
    ("skills.c", "void SPELL_ADD("),
    ("guild.c", "P_char FindTeacher(P_char ch)"),
    ("guild.c", "bool is_spec_spell(P_char teacher, int skl)"),
    ("guild.c", "int IsTaughtHere(P_char ch, int skl)"),
))

# Replay real class/circle registrations; callbacks are outside the teaching gate.
clean = re.sub(r"/\*.*?\*/|//[^\n]*", "", source("skills.c").read_text(), flags=re.S)
grants = []
for block in re.split(r"\b(?:SPELL|SKILL)_CREATE(?:_MSG|2|_WITH_MESSAGES)?\(", clean)[1:]:
    match = re.match(r'"[^"]+",\s*(SPELL_\w+)', block)
    if not match:
        continue
    statements = re.findall(r"^\s*((?:SPEC_)?SPELL_ADD\([^;]+;)", block, re.M)
    if not any("CLASS_ILLUSIONIST" in statement for statement in statements):
        continue
    grants.append(f"numSkills = {match[1]}; skills[numSkills].targets = TAR_SPELL;\n" + "\n".join(statements))

driver = r'''
int main() {
    REGISTER_SPELLS
    char_data teacher{}, pupil{};
    pc_only_data pc{};
    teacher.specials.act = TRAINER_ACT;
    teacher.player.m_class = TRAINER_CLASS;
    teacher.player.level = TRAINER_LEVEL;
    teacher.player.race = RACE_TIEFLING;
    assert(IS_NPC(&teacher) && IS_SET(teacher.specials.act, ACT_TEACHER));
    assert(IS_SET(teacher.specials.act, ACT_SENTINEL));
    assert(!IS_SET(teacher.specials.act, ACT_HUNTER | ACT_SPEC_TEACHER));
    assert(teacher.player.m_class == CLASS_ILLUSIONIST);
    pupil.player.m_class = CLASS_ILLUSIONIST;
    pupil.player.race = RACE_TIEFLING;
    pupil.player.level = 56;
    pupil.only.pc = &pc;
    rooms[0].people = &teacher;
    assert(FindTeacher(&pupil) == &teacher);
    int count = 0;
    std::set<int> circles;
    for (int spell = FIRST_SPELL; spell <= LAST_SPELL; ++spell) {
        int circle = skills[spell].m_class[flag2idx(CLASS_ILLUSIONIST) - 1].rlevel[0];
        if (circle <= 0 || circle > MAX_CIRCLE) continue;
        assert(knows_spell(&teacher, spell) == circle);
        assert(IsTaughtHere(&pupil, spell));
        circles.insert(circle);
        ++count;
    }
    assert(count >= 40 && circles.size() == MAX_CIRCLE);
    for (int spell : {SPELL_CONTINUAL_LIGHT, SPELL_DARKNESS, SPELL_SHADOW_MONSTER}) {
        assert(knows_spell(&teacher, spell));
        assert(IsTaughtHere(&pupil, spell));
        teacher.player.m_class = CLASS_SORCERER;
        assert(!IsTaughtHere(&pupil, spell));
        teacher.player.m_class = CLASS_ILLUSIONIST;
    }
    printf("Nax Illusionist teacher: %d ordinary spells across %zu circles passed\n", count, circles.size());
}
'''.replace("REGISTER_SPELLS", "\n".join(grants)).replace("TRAINER_ACT", str(flags[0]))
driver = driver.replace("TRAINER_CLASS", race[2]).replace("TRAINER_LEVEL", str(level))

build = ROOT / "bin/tests"
build.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="nax-illusionist-", dir=build) as directory:
    cpp, binary = Path(directory) / "harness.cpp", Path(directory) / "harness"
    cpp.write_text(prelude + production + driver)
    subprocess.run([
        "g++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
        "-fsanitize=address,undefined", "-fno-pie", "-no-pie",
        "-I" + str(ROOT / "src"), str(cpp), str(HARNESS_STUBS), "-o", str(binary),
    ], check=True, timeout=120)
    subprocess.run([str(binary)], check=True, timeout=10)
print("Nax classroom exits, zone limit, stationary nonaggressive Tiefling trainer and reset passed")
