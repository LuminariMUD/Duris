#!/usr/bin/env python3
"""Execute the production takedown_check() against Freedom of Movement.

Freedom of Movement trims takedown chances for the whole spell, the way
Guardian Spirits does, instead of blocking one attempt and then being used up.
The harness compiles the real takedown_check() and stubs only the dice, skills
and messages it calls.  The backstab reduction lives in a much larger function,
so it is pinned at source level instead.
"""

from pathlib import Path
import re
import subprocess
import tempfile

from _paths import ROOT, HARNESS_STUBS, extract_function, source
from _source_contract import function_bodies


ACTOFF = source("actoff.c").read_text(encoding="utf-8")
TAKEDOWN_DEFINES = re.search(
    r"#define TAKEDOWN_DEFAULT.*?#define TAKEDOWN_PENALTY -2\n", ACTOFF, re.S
).group(0)
BOUNDED = extract_function("utility.c", "int BOUNDED(int a, int b, int c)")
TAKEDOWN_CHECK = extract_function(
    "actoff.c",
    "float takedown_check(P_char ch, P_char victim, float chance, int skill, ulong applicable)",
)

PRELUDE = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "combat/grapple.h"
#include "magic/spells.h"
#include "net/comm.h"

#include <cmath>
#include <cstdio>
#include <cstdlib>
''' + TAKEDOWN_DEFINES + r'''
static bool freedom, guardian;

bool affected_by_spell(P_char, int spell)
{
    return (spell == SPELL_FREEDOM_OF_MOVEMENT && freedom) ||
           (spell == SPELL_GUARDIAN_SPIRITS && guardian);
}

// A takedown must neither spend the spell nor be turned away outright.
bool check_freedom_of_movement(P_char, bool) { std::abort(); }
void affect_from_char(P_char, int) { std::abort(); }
void show_failed_takedown_messages(P_char, P_char, int, int) { std::abort(); }

float get_property(const char *, double fallback) { return (float)fallback; }
int number(int, int high) { return high; }
int on_front_line(P_char) { return 1; }
int GET_CHAR_SKILL_P(P_char, int) { return 0; }
bool notch_skill(P_char, int, float) { return false; }
struct affected_type *get_spell_from_char(P_char, int, void *, int) { return nullptr; }
void guardian_spirits_messages(P_char, P_char) {}
int get_property(const char *, int fallback) { return fallback; }
void set_short_affected_by(P_char, int, int) {}
void CharWait(P_char, int) {}
bool hit(P_char, P_char, P_obj, int *) { std::abort(); }

static room_data rooms[1]{};
P_room world = rooms;
''' + BOUNDED

DRIVER = r'''
static void require_chance(const char *name, float actual, float expected)
{
    if (std::fabs(actual - expected) > 0.001f)
    {
        std::fprintf(stderr, "%s: expected %.3f, got %.3f\n", name, expected, actual);
        std::exit(1);
    }
}

static float attempt(char_data &basher, char_data &victim, bool has_freedom, bool has_guardian)
{
    freedom = has_freedom;
    guardian = has_guardian;
    return takedown_check(&basher, &victim, 50.0f, SKILL_BASH, 0);
}

int main()
{
    char_data basher{}, victim{};
    SET_POS(&basher, POS_STANDING + STAT_NORMAL);
    SET_POS(&victim, POS_STANDING + STAT_NORMAL);

    require_chance("no-protection", attempt(basher, victim, false, false), 50.0f);
    require_chance("freedom-of-movement", attempt(basher, victim, true, false), 40.0f);
    require_chance("guardian-spirits", attempt(basher, victim, false, true), 37.5f);
    require_chance("both-stack", attempt(basher, victim, true, true), 30.0f);

    // A much higher level basher used to strip the spell; now it just meets the same 20%.
    basher.player.level = 56;
    victim.player.level = 30;
    require_chance("high-level-basher", attempt(basher, victim, true, false), 40.0f);

    std::puts("Freedom of Movement takedown runtime regressions passed");
    return 0;
}
'''


with tempfile.TemporaryDirectory(prefix="duris-fom-takedown-") as directory:
    temporary = Path(directory)
    harness = temporary / "harness.cpp"
    binary = temporary / "harness"
    harness.write_text("\n".join((PRELUDE, TAKEDOWN_CHECK, DRIVER)), encoding="utf-8")
    subprocess.run(
        [
            "g++",
            "-std=c++20",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-Wno-unused-parameter",
            "-fsanitize=address,undefined",
            "-ffunction-sections",
            "-fdata-sections",
            f"-I{ROOT / 'src'}",
            str(harness),
            "-Wl,--gc-sections",
            str(HARNESS_STUBS),
            "-o",
            str(binary),
        ],
        cwd=ROOT,
        check=True,
    )
    subprocess.run([str(binary)], cwd=ROOT, check=True)


# Backstab: the same spell cuts the stab chance by 30% for its duration.
backstab = function_bodies(ACTOFF, r"\bbool\s+backstab\s*\(\s*P_char\s+ch\s*,\s*P_char\s+victim\s*\)")
assert len(backstab) == 1, "backstab() definition not found"
assert re.search(
    r"affected_by_spell\(\s*victim\s*,\s*SPELL_FREEDOM_OF_MOVEMENT\s*\)\s*\)\s*\{\s*"
    r"percent_chance\s*=\s*\(int\)\(\s*percent_chance\s*\*\s*"
    r'get_property\(\s*"spell\.FreedomOfMovement\.backstab"\s*,\s*0\.700\s*\)\s*\)\s*;',
    backstab[0],
), "backstab() must scale percent_chance by the Freedom of Movement backstab property"
assert "check_freedom_of_movement" not in backstab[0]

properties = (ROOT / "lib/duris.properties").read_text(encoding="utf-8")
assert "\nspell.FreedomOfMovement.takedown=0.800\n" in properties
assert "\nspell.FreedomOfMovement.backstab=0.700\n" in properties

print("Freedom of Movement takedown and backstab regressions passed")
