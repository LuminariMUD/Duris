#!/usr/bin/env python3
"""Verify neutral racial activation, unchanged class values, and damage composition."""
from pathlib import Path
import re
import subprocess
import tempfile

from _paths import ROOT, extract_function, source


CLASS_OUTPUT = {
    "None": 1.0, "Warrior": 1.15, "Ranger": 1.05, "Psionicist": .85,
    "Paladin": 1.0, "Anti-Paladin": 1.0, "Cleric": 1.1, "Monk": .825,
    "Druid": .9, "Blighter": .9, "Shaman": .9, "Ethermancer": 1.0,
    "Sorcerer": .85, "Necromancer": 1.0, "Conjurer": .8, "Summoner": .8,
    "Rogue": 1.1, "Assassin": 1.0, "Mercenary": 1.0, "Bard": 1.2,
    "Thief": 1.1, "Warlock": .9, "MindFlayer": .9, "Alchemist": 1.0,
    "Berserker": .9, "Reaver": 1.05, "Illusionist": 1.0, "Unholy-Piper": 1.0,
    "Dreadlord": 1.0, "Avenger": 1.0, "Theurgist": .9, "Dragoon": 1.0,
}

HARNESS = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include <cassert>
#include <cmath>
#include <cstdio>
#include <fstream>
#include <map>
#include <string>
extern const race_names race_names_table[];
extern const class_names class_names_table[];
float combat_by_race[LAST_RACE + 1][3];
float combat_by_class[CLASS_COUNT + 1][2];
float class_hitpoints[CLASS_COUNT + 1];
float pulse_all, shield_combat_mult, shield_combat_tank_mult;
room_data rooms[1]{}; P_room world = rooms;
zone_data zones[1]{}; zone_data *zone_table = zones;
static std::map<std::string, float> properties;
float get_property(const char *key, double fallback) {
    auto entry = properties.find(key);
    return entry == properties.end() ? float(fallback) : entry->second;
}
int real_room0(int) { return 0; }
// PRODUCTION
static void close(float actual, float expected) {
    assert(std::abs(actual - expected) < .00001f);
}
int main(int argc, char **argv) {
    assert(argc == 2);
    std::ifstream file(argv[1]); assert(file.good());
    for (std::string line; std::getline(file, line);) {
        char key[256]; float value;
        if (std::sscanf(line.c_str(), "%255[^=]=%f", key, &value) == 2)
            properties[key] = value;
    }
    update_damage_data();
    char_data actor{};
    // All real races, including NPC-only identities, retain their old neutral
    // racial output. Class output, racial pulse and damroll-cap tables still load normally.
    for (int race = 1; race <= LAST_RACE; ++race) {
        close(combat_by_race[race][1], 1.0f);
        const std::string name = race_names_table[race].no_spaces;
        close(combat_by_race[race][2], get_property(("damage.damrollModifier.racial." + name).c_str(), 1.0));
        close(combat_by_race[race][0], get_property(("damage.pulse.racial." + name).c_str(), double(PULSE_VIOLENCE)));
        actor.player.race = race;
        for (int cls = 1; cls <= CLASS_COUNT; ++cls) {
            actor.player.m_class = 1u << (cls - 1);
            assign_damage(&actor);
            const float expected = get_property((std::string("damage.totalOutput.class.") + class_names_table[cls].normal).c_str(), 0.0);
            close(combat_by_class[cls][1], expected);
            close(actor.specials.damage_mod, expected);
        }
    }
    // A missing racial property is neutral, for player and NPC races alike.
    properties.erase("damage.totalOutput.racial.Barbarian");
    properties.erase("damage.totalOutput.racial.Dragon");
    update_damage_data();
    close(combat_by_race[RACE_BARBARIAN][1], 1.0f);
    close(combat_by_race[RACE_DRAGON][1], 1.0f);

    // Re-loading signed adjustments updates the same tables used for combat.
    properties["damage.totalOutput.racial.Barbarian"] = 1.15f;
    properties["damage.totalOutput.racial.DrowElf"] = .825f;
    properties["damage.totalOutput.racial.Dragon"] = 1.2f;
    update_damage_data();
    actor.player.race = RACE_BARBARIAN;
    actor.player.m_class = CLASS_MONK;
    actor.player.secondary_class = 0;
    assign_damage(&actor); close(actor.specials.damage_mod, 1.15f * .825f);
    actor.player.secondary_class = CLASS_WARRIOR;
    assign_damage(&actor); close(actor.specials.damage_mod, 1.15f * 1.15f);
    actor.player.m_class = CLASS_WARRIOR;
    actor.player.secondary_class = CLASS_MONK;
    assign_damage(&actor); close(actor.specials.damage_mod, 1.15f * 1.15f);
    actor.player.race = RACE_DROW;
    assign_damage(&actor); close(actor.specials.damage_mod, .825f * 1.15f);

    // NPC output keeps its existing zone scaling and does not gain PC class factors.
    actor.specials.act = ACT_ISNPC;
    actor.player.race = RACE_DRAGON;
    zones[0].difficulty = 3;
    assign_damage(&actor); close(actor.specials.damage_mod, 1.2f * 1.6f);
    properties["damage.totalOutput.racial.Dragon"] = 1.0f;
    update_damage_data();
    assign_damage(&actor); close(actor.specials.damage_mod, 1.6f);
    puts("PASS: neutral race matrix, missing keys, reload, signed factors, multiclass maximum and NPC scaling");
}
'''


def main():
    properties = (ROOT / "lib/duris.properties").read_text()
    racial = re.findall(r"^damage\.totalOutput\.racial\.([^=]+)=(.+)$", properties, re.M)
    assert len(racial) == 93 and all(value == "1.000" for _, value in racial), racial
    classes = {key: float(value) for key, value in re.findall(
        r"^damage\.totalOutput\.class\.([^=]+)=(.+)$", properties, re.M)}
    assert classes == CLASS_OUTPUT, (classes, CLASS_OUTPUT)
    affects = source("affects.c").read_text()
    start = affects.index("\tch->specials.damage_mod = combat_by_race[ch_race][1];")
    end = affects.index("\n\t/* For testing..", start)
    composition = "void assign_damage(P_char ch) { const int ch_race = GET_RACE(ch);\n" + affects[start:end] + "\n}"
    production = extract_function("affects.c", "void update_damage_data()")
    production += "\n" + extract_function("utility.c", "int flag2idx(")
    production += "\n" + extract_function("utility.c", "int BOUNDED(") + "\n" + composition
    build = ROOT / "bin/tests"
    build.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="damage-output-", dir=build) as temporary:
        directory = Path(temporary)
        harness = directory / "damage.cpp"
        harness.write_text(HARNESS.replace("// PRODUCTION", production))
        binary = directory / "damage"
        subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
                        "-ffunction-sections", "-fdata-sections", "-Wl,--gc-sections",
                        "-fsanitize=address,undefined", "-fno-pie", "-no-pie", "-Isrc",
                        str(harness), "src/core/common.c", "-o", str(binary)], cwd=ROOT, check=True)
        subprocess.run([str(binary), str(ROOT / "lib/duris.properties")], check=True)
    print("PASS: all 93 racial entries neutral and every class setting unchanged")


if __name__ == "__main__":
    main()
