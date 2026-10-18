#!/usr/bin/env python3
"""Execute production Freedom of Movement duration and protection checks.

Freedom of Movement lasts about 70% as long as Guardian Spirits' player
duration at the same level, and blocking an effect never consumes it.  The
harness compiles the real spell_freedom_of_movement(), spell_guardian_spirits()
and check_freedom_of_movement(), and pins the dice to their lowest and highest
rolls to compare the two spells' durations directly.
"""

from pathlib import Path
import re
import subprocess
import tempfile

from _paths import ROOT, HARNESS_STUBS, extract_function, source


FREEDOM_CHECK = extract_function("magic.c", "bool check_freedom_of_movement(P_char ch)")
FREEDOM_SPELL = extract_function("magic.c", "void spell_freedom_of_movement(int level")
GUARDIAN_SPELL = extract_function("smagic.c", "void spell_guardian_spirits(int level")

PRELUDE = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "magic/spells.h"
#include "net/comm.h"

#include <algorithm>
#include <cstdio>
#include <cstdlib>

static bool high_roll;      // number() returns its highest value instead of its lowest
static bool has_freedom;    // affected_by_spell(SPELL_FREEDOM_OF_MOVEMENT)
static int applied_type, applied_duration, freedom_removals;

int number(int low, int high) { return high_roll ? high : low; }
void act(const char *, int, P_char, P_obj, void *, int) {}
void send_to_char(const char *, P_char) {}
int GET_CLASS(P_char, uint) { return 1; } // a shaman, so guardian spirits casts

bool affected_by_spell(P_char, int spell)
{
    return spell == SPELL_FREEDOM_OF_MOVEMENT && has_freedom;
}

affected_type *affect_to_char(P_char, affected_type *af)
{
    applied_type = af->type;
    applied_duration = af->duration;
    return af;
}

void affect_from_char(P_char, int spell)
{
    if (spell == SPELL_FREEDOM_OF_MOVEMENT)
        ++freedom_removals;
}
'''

DRIVER = r'''
static void require(bool ok, const char *name, const char *what)
{
    if (!ok)
    {
        std::fprintf(stderr, "%s: %s\n", name, what);
        std::exit(1);
    }
}

static int cast(bool guardian, int level, bool high)
{
    static char_data caster{};
    SET_POS(&caster, POS_STANDING + STAT_NORMAL);
    high_roll = high;
    has_freedom = false;
    applied_type = applied_duration = 0;
    if (guardian)
        spell_guardian_spirits(level, &caster, nullptr, 0, &caster, nullptr);
    else
        spell_freedom_of_movement(level, &caster, nullptr, 0, &caster, nullptr);
    require(applied_type == (guardian ? SPELL_GUARDIAN_SPIRITS : SPELL_FREEDOM_OF_MOVEMENT),
            "cast", "spell applied no affect");
    return applied_duration;
}

int main()
{
    // {level, lowest roll, highest roll}, about 70% of guardian spirits with a floor of 3.
    const int expected[][3] = { { 56, 16, 19 }, { 51, 14, 17 }, { 40, 11, 14 },
                                { 30, 7, 10 },  { 10, 3, 3 },   { 1, 3, 3 } };
    for (const auto &row : expected)
    {
        int level = row[0];
        int low = cast(false, level, false), high = cast(false, level, true);
        if (low != row[1] || high != row[2])
        {
            std::fprintf(stderr, "level %d: expected %d-%d, got %d-%d\n", level, row[1],
                         row[2], low, high);
            return 1;
        }
        // Same roll, same level: 70% of guardian spirits, never below 3.
        int guardian_low = cast(true, level, false), guardian_high = cast(true, level, true);
        require(low == std::max(3, guardian_low * 7 / 10), "low roll",
                "duration drifted from 70% of guardian spirits");
        require(high == std::max(3, guardian_high * 7 / 10), "high roll",
                "duration drifted from 70% of guardian spirits");
    }

    // The duration follows the spell level, so potions and scrolls use their own level.
    char_data low_level_drinker{};
    low_level_drinker.player.level = 1;
    high_roll = false;
    has_freedom = false;
    spell_freedom_of_movement(56, &low_level_drinker, nullptr, 0, &low_level_drinker, nullptr);
    require(applied_duration == 16, "item level", "duration ignored the spell level");

    // Recasting while protected does nothing.
    has_freedom = true;
    applied_type = 0;
    spell_freedom_of_movement(56, &low_level_drinker, nullptr, 0, &low_level_drinker, nullptr);
    require(applied_type == 0, "recast", "stacked a second affect");

    // Blocking an effect reports protection and never spends the spell.
    freedom_removals = 0;
    for (int blocked = 0; blocked < 10; ++blocked)
        require(check_freedom_of_movement(&low_level_drinker), "protected", "check failed");
    require(freedom_removals == 0, "protected", "blocking an effect consumed the spell");
    has_freedom = false;
    require(!check_freedom_of_movement(&low_level_drinker), "unprotected", "check passed");

    std::puts("Freedom of Movement duration runtime regressions passed");
    return 0;
}
'''


with tempfile.TemporaryDirectory(prefix="duris-fom-duration-") as directory:
    temporary = Path(directory)
    harness = temporary / "harness.cpp"
    binary = temporary / "harness"
    harness.write_text(
        "\n".join((PRELUDE, FREEDOM_CHECK, FREEDOM_SPELL, GUARDIAN_SPELL, DRIVER)),
        encoding="utf-8",
    )
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


# No caller may ask the check to spend the spell, and the helper takes no such flag.
callers = []
for path in sorted((ROOT / "src").rglob("*.c")):
    text = path.read_text(encoding="latin-1")
    callers += re.findall(r"check_freedom_of_movement\(([^()]*)\)", text)
assert len(callers) >= 15, f"expected the existing callers, found {len(callers)}"
assert all("," not in args for args in callers), "check_freedom_of_movement takes one argument"
assert "bool check_freedom_of_movement(P_char ch);" in source("prototypes.h").read_text(
    encoding="utf-8"
)

print("Freedom of Movement duration and protection regressions passed")
