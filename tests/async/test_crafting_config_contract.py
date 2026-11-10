#!/usr/bin/env python3
"""Crafting balance must be boot-loaded from a documented config."""
from _paths import SRC
from pathlib import Path
from contract_text import contains
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
source = (SRC / "crafting.c").read_text()
header = (SRC / "crafting.h").read_text()
comm = (SRC / "comm.c").read_text()
config = root / "lib/crafting.cfg"
config_text = config.read_text()
assert config.exists(), "missing lib/crafting.cfg"
assert contains(source, 'fopen("lib/crafting.cfg", "r")')
assert contains(source, "crafting.level.gate.multiplier")
assert contains(source, "crafting.material.quantity.multiplier")
assert contains(source, "crafting.experience.per.ival")
assert "crafting.experience.per.ival=1000" in config_text
assert "Commands accept either form" in config_text
assert contains(source, "i + 1, recipes[i]")
assert contains(source, "selected = recipes[choice2 - 1]")
assert contains(source, "objVnum = recipes[objVnum - 1]")
assert contains(source, "crafting.recipe.max.player.level")
assert contains(source, "crafting.recipe.examine.materials")
assert "crafting.recipe.max.player.level=56" in config_text
assert "crafting.recipe.examine.materials=1" in config_text
assert contains(source, "Discipline consumables")
assert contains(source, "is_salvageable(item)")
assert contains(source, "crafting.salvage.scientific.tools.vnum")
assert contains(header, "int crafting_scientific_tools_vnum(void);")
assert contains(header, "int crafting_level_gate_multiplier(void);")
assert contains(comm, "boot_crafting_system();")
print("crafting config contract passed")

# A valid int score can still overflow score+4 before material decomposition.
# Execute the production plan, controlling only its score/material endpoints.
HARNESS = r'''
#include "economy/crafting.c"
#include <cassert>
#include <climits>
#include <limits>
#include <cstring>
static int score;
static int xp_calls, requested_xp;
int gain_exp(P_char, P_char, int amount, int type) {
    assert(type == EXP_BOON);
    ++xp_calls;
    requested_xp = amount;
    return std::max(1, amount); // The production API has this minimum too.
}
int itemvalue(P_obj) { return score; }
int get_matstart(P_obj) { return 400015; }
int main() {
    obj_data object{};
    char_data player{};
    struct test_case { int value, high, low; };
    for (const test_case test : {test_case{1, 1, 0}, {4, 1, 3}, {5, 1, 4}, {6, 2, 0}, {9, 2, 3}, {10, 2, 4},
                                 {INT_MAX - 1, 429496730, 0}, {INT_MAX, 429496730, 1}}) {
        score = test.value;
        crafting_experience_per_item_value = score < 100 ? 1000 : 0;
        crafting_plan plan{};
        assert(crafting_build_plan(&object, &plan));
        assert(plan.item_value == score && plan.high_material_count == test.high &&
               plan.low_material_count == test.low);
        assert(plan.low_material_vnum == 400015 && plan.high_material_vnum == 400019);
        assert(plan.experience == (score < 100 ? score * 1000 : 0));
        const auto original = plan;
        xp_calls = requested_xp = 0;
        crafting_award_experience(&player, plan);
        assert(xp_calls == (plan.experience > 0 ? 1 : 0));
        if (xp_calls) assert(requested_xp == plan.experience);
        assert(!std::memcmp(&plan, &original, sizeof(plan)));
    }
    crafting_experience_per_item_value = 1000;
    score = INT_MAX / 1000;
    crafting_plan valid{};
    assert(crafting_build_plan(&object, &valid) && valid.experience == 2147483000);
    ++score;
    auto unchanged = valid;
    assert(!crafting_build_plan(&object, &valid));
    assert(!std::memcmp(&valid, &unchanged, sizeof(valid)));
    score = 5;
    for (double scale : {0., -1., std::numeric_limits<double>::infinity(),
                          std::numeric_limits<double>::quiet_NaN(), 1e100}) {
        crafting_material_quantity_multiplier = scale;
        assert(!crafting_build_plan(&object, &valid));
        assert(!std::memcmp(&valid, &unchanged, sizeof(valid)));
    }
    crafting_material_quantity_multiplier = 1e-300;
    assert(crafting_build_plan(&object, &valid) && valid.high_material_count == 1 && valid.low_material_count == 1);
    crafting_material_quantity_multiplier = 1.00000001;
    score = 1;
    assert(crafting_build_plan(&object, &valid) && valid.high_material_count == 2 && valid.low_material_count == 0);
    int high = 11, low = 22;
    assert(!item_value_material_quantities(5, INT_MAX, high, low) && high == 11 && low == 22);
    assert(item_value_material_quantities(1, INT_MAX, high, low) && high == INT_MAX && low == 0);
    assert(item_value_material_quantities(5, .99999999, high, low) && high == 1 && low == 4);
    assert(item_value_material_quantities(5, 1.00000001, high, low) && high == 2 && low == 5);
    assert(item_value_material_quantities(5, .25, high, low) && high == 1 && low == 1);
    assert(item_value_material_quantities(121, 2.2, high, low) && high == 55 && low == 0);
    score = 0;
    crafting_plan plan{};
    assert(!crafting_build_plan(&object, &plan));
}
'''
(root / "bin/tests").mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="craft-plan-bounds-", dir=root / "bin/tests") as tmp:
    cpp, binary = Path(tmp) / "test.cpp", Path(tmp) / "test"
    cpp.write_text(HARNESS)
    subprocess.run(["g++", "-std=c++20", "-g", "-O1", "-Isrc", "-I/usr/include/mysql", "-ffunction-sections",
                    "-fdata-sections", "-Wl,--gc-sections", "-fsanitize=address,undefined,float-cast-overflow",
                    "-fno-sanitize-recover=all", "-fno-pie", "-no-pie", str(cpp), "src/item/item_value.c", "-o", str(binary)],
                   cwd=root, check=True)
    subprocess.run([str(binary)], check=True)
print("native crafting plan: quantity/XP boundaries and disabled XP awards passed")
