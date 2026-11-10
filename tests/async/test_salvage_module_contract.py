#!/usr/bin/env python3
from _paths import SRC
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
salvage = (SRC / "salvage.c").read_text()
actobj = (SRC / "actobj.c").read_text()
makefile = (SRC / "Makefile").read_text()

for symbol in ("is_salvageable", "salvage_examine_item", "do_salvage"):
    assert symbol in salvage, symbol
eligibility = salvage[salvage.index("bool is_salvageable") : salvage.index("void salvage_examine_item")]
assert "GET_ITEM_TYPE(temp) == ITEM_CORPSE" in eligibility
assert "void do_salvage(" not in actobj
assert "bool is_salvageable(" not in actobj
assert "salvage.o" in makefile
print("salvage module contract passed")

import subprocess
import tempfile
from _paths import extract_function

HARNESS = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "magic/spells.h"
#include <cassert>
#include <climits>
#include <cfloat>
#include <initializer_list>
int GET_CHAR_SKILL_P(P_char, int skill) { assert(skill == SKILL_SALVAGE); return 100; }
// FUNCTIONS
int main() {
    char_data player{};
    player.curr_stats.Luk = 100; player.player.level = 56;
    assert(salvage_recipe_score(&player) == 312);
    assert(salvage_recipe_score(&player, INT_MAX) == 312LL * INT_MAX);
    for (int luck : {-1, 0, 60, 100, 500, 700})
    for (double scale : {.1, .5, 1., 1.5, 2., 500.}) {
        const int original = static_cast<int>(luck * scale);
        const int checked = salvage_essence_luck(luck, scale);
        for (int roll = 1; roll <= 500; ++roll) assert((roll < original) == (roll < checked));
    }
    for (double scale : {0., .000001, .5, .99999999, 1., 1.00000001, 2.}) {
        const int original = static_cast<int>(1000000. * scale);
        const int checked = salvage_essence_chance(scale);
        for (int roll : {1, 499999, 500000, 999999, 1000000}) assert((roll <= original) == (roll <= checked));
    }
    assert(salvage_essence_luck(INT_MAX, DBL_MAX) == 501);
    assert(salvage_essence_luck(INT_MAX, 1e-300) == 0);
    assert(salvage_essence_chance(DBL_MAX) == 1000000);
}
'''
functions = "\n".join(extract_function("salvage.c", signature) for signature in (
    "static int64_t salvage_recipe_score(", "static int salvage_essence_luck(", "static int salvage_essence_chance("))
(ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="salvage-bounds-", dir=ROOT / "bin/tests") as tmp:
    cpp, binary = Path(tmp) / "test.cpp", Path(tmp) / "test"
    cpp.write_text(HARNESS.replace("// FUNCTIONS", functions))
    subprocess.run(["g++", "-std=c++20", "-g", "-O1", "-Isrc", "-fsanitize=address,undefined,float-cast-overflow",
                    "-fno-sanitize-recover=all", "-fno-pie", "-no-pie", str(cpp), "-o", str(binary)], cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True)
print("native salvage recipe/probability boundaries and ordinary roll parity passed")
