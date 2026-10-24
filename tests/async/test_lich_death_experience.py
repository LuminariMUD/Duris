#!/usr/bin/env python3
"""Execute the death-policy block, retaining lich's fractional residual XP."""

from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, extract_function


HELPER = extract_function("combat/fight.c", "static long lich_death_residual_experience(")
DIE = extract_function("combat/fight.c", "void die(P_char ch, P_char killer)")

# The death path must use the shared production helper and keep ordinary death
# policy in the non-lich branch.
assert "GET_EXP(ch) = lich_death_residual_experience(tmp, GET_LEVEL(ch));" in DIE
assert "else\n\t\t{\n\t\t\tloss = gain_exp(ch, NULL, 0, EXP_DEATH);" in DIE
assert "new_exp_table[GET_LEVEL(ch)] / new_exp_table[GET_LEVEL(ch) + 1]" not in DIE
assert "static_cast<double>(new_exp_table[level])" in HELPER
assert "static_cast<double>(new_exp_table[level + 1])" in HELPER
POLICY = DIE[DIE.index("\t/* count xp loss for victim and apply */"):]
POLICY = POLICY[:POLICY.index("\n\t/*", 5)]
CUTOFF = extract_function("world/limits.c", "int death_exp_loss_level_threshold(")
# The initialized/returned loss is still the one passed to the actual corpse.
assert "int loss = 0, i;" in DIE
assert "corpse = make_corpse(ch, loss);" in DIE

HARNESS = f"""
#include <cassert>
#include <cstring>
#include <initializer_list>
#include "core/prototypes.h"
#include "core/utils.h"

long new_exp_table[TOTALLVLS] = {{}};
room_data rooms[1]{{}};
P_room world = rooms;
int configured_cutoff = -1, ordinary_calls = 0;
int get_property(const char *key, int fallback) {{
    assert(!std::strcmp(key, "exp.goodieDeathExpLossLevelThreshold"));
    return configured_cutoff < 0 ? fallback : configured_cutoff;
}}
void lose_level(P_char ch) {{ --ch->player.level; }}
int gain_exp(P_char, P_char, int, int) {{ ++ordinary_calls; return -150; }}
void debug(const char *, ...) {{}}

{HELPER}
{CUTOFF}
int death_loss(P_char ch) {{
    int loss = 0;
    {POLICY}
    return loss;
}}

int main()
{{
    for (auto &xp : new_exp_table) xp = 10000;
    new_exp_table[30] = 20000;
    new_exp_table[31] = 40000;
    for (int side : {{RACEWAR_GOOD, RACEWAR_EVIL, 0, 3}}) {{
        for (int level : {{1, 2, 29, 30, 31}}) {{
            char_data ch{{}};
            ch.player.race = RACE_LICH;
            ch.player.racewar = side;
            ch.player.level = level;
            ch.points.curr_exp = 4000;
            const int residual = level < 30 ? 4000 :
                lich_death_residual_experience(4000, level - 1);
            const int loss = death_loss(&ch);
            assert(ch.player.level == (level < 30 ? level : level - 1));
            assert(GET_EXP(&ch) == residual);
            assert(loss == (level < 30 ? 0 : -(4000 + new_exp_table[level - 1] - residual)));
        }}
    }}
    assert(ordinary_calls == 0);
    char_data ch{{}};
    ch.player.race = RACE_LICH;
    ch.player.level = 30;
    rooms[0].room_flags = ROOM_ARENA;
    assert(death_loss(&ch) == 0 && ch.player.level == 30);
    rooms[0].room_flags = 0;
    ch.player.level = MINLVLIMMORTAL;
    assert(death_loss(&ch) == 0 && ch.player.level == MINLVLIMMORTAL);
    ch.player.level = 24;
    configured_cutoff = 25;
    assert(death_loss(&ch) == 0 && ch.player.level == 24);
    ch.player.level = 25;
    ch.points.curr_exp = 4000;
    assert(death_loss(&ch) < 0 && ch.player.level == 24);
    configured_cutoff = -1;
    ch.player.race = RACE_OGRE;
    ch.player.level = 29;
    assert(death_loss(&ch) == 0 && ordinary_calls == 0);
    ch.player.level = 30;
    assert(death_loss(&ch) == -150 && ordinary_calls == 1);

    // Increasing thresholds must retain the fractional ratio instead of
    // truncating it to zero before the residual is scaled.
    new_exp_table[50] = 20000000L;
    new_exp_table[51] = 40000000L;
    assert(lich_death_residual_experience(10000000L, 50) == 5000000L);

    // Equal thresholds are unchanged by the corrected division.
    new_exp_table[50] = 24000000L;
    new_exp_table[51] = 24000000L;
    assert(lich_death_residual_experience(1234567L, 50) == 1234567L);

    // Preserve the existing minimum-one policy for zero and sub-unit results.
    new_exp_table[50] = 1L;
    new_exp_table[51] = 2L;
    assert(lich_death_residual_experience(0L, 50) == 1L);
    assert(lich_death_residual_experience(1L, 50) == 1L);
    return 0;
}}
"""

directory = ROOT / "bin/tests"
directory.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="lich-death-", dir=directory) as temporary:
    root = Path(temporary)
    harness = root / "lich_death.cpp"
    binary = root / "lich_death"
    harness.write_text(HARNESS, encoding="utf-8")
    subprocess.run(
        ["g++", "-std=c++20", "-Wall", "-Wextra", "-Wpedantic", "-Werror",
         "-fsanitize=address,undefined", "-fno-pie", "-no-pie", "-Isrc",
         str(harness), "-o", str(binary)],
        check=True, cwd=ROOT,
    )
    subprocess.run([str(binary)], check=True)

print("lich death proportional residual experience regression passed")
