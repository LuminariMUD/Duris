#!/usr/bin/env python3
"""Crafting balance must be boot-loaded from a documented config."""
from _paths import SRC
from pathlib import Path
from contract_text import contains
import subprocess
import tempfile
import shutil

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
#include <array>
static int score;
static int xp_calls, requested_xp;
static int config_diagnostics;
void logit(const char *, const char *, ...) { ++config_diagnostics; }
int real_object(int vnum) { return vnum > 0 && vnum != 999999 ? 0 : -1; }
bool is_salvageable(P_obj) { return true; }
int gain_exp(P_char, P_char, int amount, int type) {
    assert(type == EXP_BOON);
    ++xp_calls;
    requested_xp = amount;
    return std::max(1, amount); // The production API has this minimum too.
}
int itemvalue(P_obj) { return score; }
int get_matstart(P_obj) { return 400015; }
static void config_text(const std::string &text) {
    FILE *file = std::fopen("lib/crafting.cfg", "w");
    assert(file && std::fwrite(text.data(), 1, text.size(), file) == text.size());
    assert(!std::fclose(file));
    config_diagnostics = 0;
    load_crafting_config();
}
static void config_cases() {
    load_crafting_config(); // The fixture starts with the actual shipped file.
    assert(crafting_level_gate == 3 && crafting_recipe_max_player_level == MAXLVLMORTAL);
    assert(crafting_experience_per_item_value == 1000 && crafting_material_quantity_multiplier == 1);
    assert(crafting_craft_enabled && crafting_forge_enabled && crafting_recipe_display_vnums && crafting_recipe_examine_materials);
    config_text("crafting.level.gate.multiplier=3junk\ncrafting.recipe.max.player.level=999\n"
                "crafting.experience.per.ival=2147483648\ncrafting.material.quantity.multiplier=inf\n"
                "crafting.craft.enabled=2\ncrafting.forge.enabled=broken\ncrafting.recipe.display.vnums=-1\n"
                "crafting.recipe.examine.materials=\ncrafting.craft.essence.vnum=0\ncrafting.craft.tool.vnum=-1\n"
                "crafting.forge.essence.vnum=999999999999999999999999\ncrafting.forge.tool.vnum=12junk\n"
                "crafting.salvage.scientific.tools.vnum=0\ncrafting.salvage.scientific.tools.prevent.breakage=2\n"
                "crafting.salvage.scientific.tools.recipe.roll.divisor=0\n"
                "crafting.salvage.scientific.tools.recipe.player.multiplier=-1\n"
                "crafting.salvage.essence.luck.multiplier=nan\ncrafting.salvage.essence.chance.multiplier=-1\n=123\n");
    assert(config_diagnostics == 18);
    assert(crafting_level_gate == 3 && crafting_experience_per_item_value == 1000 && crafting_material_quantity_multiplier == 1);
    assert(crafting_recipe_max_player_level == MAXLVLMORTAL && crafting_craft_enabled && crafting_forge_enabled);
    assert(crafting_recipe_display_vnums && crafting_recipe_examine_materials);
    assert(crafting_craft_essence_vnum == VOBJ_CRAFTING_ESSENCE && crafting_craft_tool_vnum == VOBJ_CRAFTING_TOOLS);
    assert(crafting_forge_essence_vnum == VOBJ_FORGING_ESSENCE && crafting_forge_tool_vnum == VOBJ_FORGING_FLUX);
    assert(crafting_scientific_tools_vnum_value == VOBJ_EPIC_LANTAN_TOOLS && crafting_scientific_tools_prevent_breakage_value);
    assert(crafting_scientific_tools_recipe_roll_divisor_value == 15 && crafting_scientific_tools_recipe_player_multiplier_value == 2);
    assert(crafting_salvage_essence_luck_multiplier_value == 1 && crafting_salvage_essence_chance_multiplier_value == 1);
    config_text("crafting.level.gate.multiplier=5\ncrafting.recipe.max.player.level=40\n"
                "crafting.experience.per.ival=123\ncrafting.material.quantity.multiplier=.5\n"
                "crafting.craft.enabled=0\ncrafting.forge.enabled=0\ncrafting.recipe.display.vnums=0\n"
                "crafting.recipe.examine.materials=0\ncrafting.craft.essence.vnum=900001\ncrafting.craft.tool.vnum=900002\n"
                "crafting.forge.essence.vnum=900003\ncrafting.forge.tool.vnum=900004\n"
                "crafting.salvage.scientific.tools.vnum=900005\ncrafting.salvage.scientific.tools.prevent.breakage=0\n"
                "crafting.salvage.scientific.tools.recipe.roll.divisor=7\n"
                "crafting.salvage.scientific.tools.recipe.player.multiplier=3\n"
                "crafting.salvage.essence.luck.multiplier=2.5\ncrafting.salvage.essence.chance.multiplier=0\n");
    assert(config_diagnostics == 0 && crafting_level_gate == 5 && crafting_recipe_max_player_level == 40);
    assert(crafting_experience_per_item_value == 123 && crafting_material_quantity_multiplier == .5);
    assert(!crafting_craft_enabled && !crafting_forge_enabled && !crafting_recipe_display_vnums && !crafting_recipe_examine_materials);
    assert(crafting_craft_essence_vnum == 900001 && crafting_craft_tool_vnum == 900002);
    assert(crafting_forge_essence_vnum == 900003 && crafting_forge_tool_vnum == 900004);
    assert(crafting_scientific_tools_vnum_value == 900005 && !crafting_scientific_tools_prevent_breakage_value);
    assert(crafting_scientific_tools_recipe_roll_divisor_value == 7 && crafting_scientific_tools_recipe_player_multiplier_value == 3);
    assert(crafting_salvage_essence_luck_multiplier_value == 2.5 && crafting_salvage_essence_chance_multiplier_value == 0);
    config_text("crafting.experience.per.ival=0\ncrafting.experience.per.ival=oops\n"
                "crafting.material.quantity.multiplier=1.25\ncrafting.material.quantity.multiplier=1e9999\n");
    assert(crafting_experience_per_item_value == 0 && crafting_material_quantity_multiplier == 1.25 && config_diagnostics == 2);
    config_text("crafting.experience.per.ival=0" + std::string(600, ' ') + "junk\ncrafting.level.gate.multiplier=4\n");
    assert(crafting_experience_per_item_value == 1000 && crafting_level_gate == 4 && config_diagnostics == 1);
    config_text("crafting.experience.per.ival=2000");
    assert(crafting_experience_per_item_value == 2000);
    config_text("crafting.craft.tool.vnum=999999\n");
    assert(crafting_craft_tool_vnum == VOBJ_CRAFTING_TOOLS && config_diagnostics == 1);
    config_text("crafting.level.gate.multiplier=2147483647\ncrafting.experience.per.ival=0\n"
                "crafting.salvage.scientific.tools.recipe.player.multiplier=2147483647\n"
                "crafting.salvage.essence.luck.multiplier=1e300\ncrafting.salvage.essence.chance.multiplier=1e300\n");
    char_data player{}; player.player.level = 56;
    assert(crafting_value_limit(&player) == 56LL * INT_MAX);
    obj_data object{}; score = INT_MAX;
    assert(crafting_recipe_target_is_available(&object));
    assert(crafting_scientific_tools_recipe_player_multiplier_value == INT_MAX);
    assert(crafting_salvage_essence_luck_multiplier_value == 1e300 && crafting_salvage_essence_chance_multiplier_value == 1e300);
    config_text("");
}
int main() {
    config_cases();
    const int recipes[] = {2, 700001, INT_MAX};
    const auto original_recipes = std::array{2, 700001, INT_MAX};
    assert(crafting_select_recipe(recipes, 3, 1) == 2);
    assert(crafting_select_recipe(recipes, 3, 2) == 2); // Stable vnum wins over list number.
    assert(crafting_select_recipe(recipes, 3, 3) == INT_MAX);
    assert(crafting_select_recipe(recipes, 3, 700001) == 700001);
    assert(crafting_select_recipe(recipes, 3, INT_MAX) == INT_MAX);
    for (int choice : {INT_MIN, -1, 0, 4, 700002}) assert(crafting_select_recipe(recipes, 3, choice) == 0);
    assert(crafting_select_recipe(recipes, 0, 1) == 0);
    const int invalid_recipes[] = {0, -1};
    assert(crafting_select_recipe(invalid_recipes, 2, 1) == 0);
    assert(crafting_select_recipe(invalid_recipes, 2, 2) == 0);
    for (const char *text : {"", "1junk", "1.0", "2147483648", "99999999999999999999999"}) {
        int choice = 0;
        assert(!config_parse_int(text, choice));
        assert(crafting_select_recipe(recipes, 3, choice) == 0);
    }
    assert(!std::memcmp(recipes, original_recipes.data(), sizeof(recipes)));
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
    score = 0;
    crafting_plan plan{};
    assert(!crafting_build_plan(&object, &plan));
}
'''
(root / "bin/tests").mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="craft-plan-bounds-", dir=root / "bin/tests") as tmp:
    cpp, binary = Path(tmp) / "test.cpp", Path(tmp) / "test"
    cpp.write_text(HARNESS)
    (Path(tmp) / "lib").mkdir()
    shutil.copyfile(config, Path(tmp) / "lib/crafting.cfg")
    subprocess.run(["g++", "-std=c++20", "-g", "-O1", "-Isrc", "-I/usr/include/mysql", "-ffunction-sections",
                    "-fdata-sections", "-Wl,--gc-sections", "-fsanitize=address,undefined,float-cast-overflow",
                    "-fno-sanitize-recover=all", "-fno-pie", "-no-pie", str(cpp), "src/item/item_value.c", "-o", str(binary)],
                   cwd=root, check=True)
    subprocess.run([str(binary)], cwd=tmp, check=True)
print("native crafting plan: quantity/XP boundaries and disabled XP awards passed")
