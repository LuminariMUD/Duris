#!/usr/bin/env python3
"""Issue #715: execute earthen handlers with the shared elemental modifier.

Use maintained property values, deterministic dice and controlled saves. The
real handler bodies must deliver unscaled damage to the shared modifier once;
separately cover approved Arcane Block bounds, penetration cap and aura floor.
"""
import json
import subprocess

from _paths import ROOT, HARNESS_STUBS, extract_function, source

properties = {}
for line in (ROOT / "lib/duris.properties").read_text().splitlines():
    if "=" in line and not line.startswith(("#", ";")):
        key, value = line.split("=", 1)
        try:
            properties[key.strip()] = float(value)
        except ValueError:
            pass
assert "skill.spellPenetration.highEndpercent" not in properties
properties = {k: v for k, v in properties.items() if k in {
    "damage.increase.elementalist", "skill.arcane.block.dam.reduction",
    "skill.spellPenetration.highEndPercent", "innate.paladin_aura.protection_spell_mod",
    "spell.area.damage.factor.earthenRain", "spell.gEarthGrasp.paraSaveBonus",
}}
initializers = ",\n".join("{" + json.dumps(k) + ", " + repr(v) + "}" for k, v in properties.items())
mods = source("dam_mods.c").read_text()
start = mods.rfind("MAKE_DAM_MOD_PRED()", 0, mods.index("ELEMENTAL_DAM(damageType) && has_innate"))
opening = mods.index("{", start)
depth, end = 1, opening + 1
while depth:
    depth += (mods[end] == "{") - (mods[end] == "}")
    end += 1
predicate = "dam_mod_predicate elemental_modifier = " + mods[start:end] + ";\n"

prelude = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "magic/spells.h"
#include "combat/damage.h"
#include "combat/dam_mods.h"
#include "classes/paladins.h"
#include "abilities/abilities.h"
#include "net/comm.h"
#include <cassert>
#include <cmath>
#include <cstring>
#include <map>
#include <string>
room_data rooms[1]{};
P_room world = rooms;
float dam_factor[LAST_DF + 1]{};
static std::map<std::string, float> properties = {PROPERTIES};
static bool elemental, saved;
static int damage_calls, raw_damage_seen, damage_seen, para_mod;
static affected_type applied{};
float get_property(const char *key, double fallback) {
    auto found = properties.find(key);
    return found == properties.end() ? fallback : found->second;
}
int GET_CHAR_SKILL_P(P_char, int skill) { assert(skill == SKILL_ARCANE_BLOCK); return 100; }
bool has_innate(P_char, int id) { return elemental && id == INNATE_ELEMENTAL_POWER; }
int number(int low, int) { return low; }
int dice(int count, int) { return count * 4; }
const Rolls live_rolls = {dice, number};
const Rolls lowest_rolls = {[](int n, int) { return n; }, [](int a, int) { return a; }};
const Rolls highest_rolls = {[](int n, int s) { return n*s; }, [](int, int b) { return b; }};
int BOUNDED(int a, int b, int c) { return std::max(a, std::min(b,c)); }
int GET_CLASS(P_char ch, uint cls) { return (ch->player.m_class & cls) != 0; }
bool IS_OUTDOORS(int) { return true; }
bool IS_IN_UNDERWORLD(int) { return false; }
bool NewSaves(P_char, int kind, int mod) {
    if (kind == SAVING_PARA) { para_mod = mod; return false; }
    return saved;
}
bool resists_spell(P_char, P_char) { return false; }
bool affected_by_spell(P_char, int) { return false; }
bool check_freedom_of_movement(P_char) { return false; }
int get_default_save_mod(P_char, P_char, int, int) { return 0; }
affected_type *affect_to_char(P_char, affected_type *af) { applied = *af; return nullptr; }
void stop_fighting(P_char) {}
void StopMercifulAttackers(P_char) {}
void act(const char *, int, P_char, P_obj, void *, int) {}
void send_to_char(const char *, P_char) {}
'''.replace("PROPERTIES", initializers)
functions = [extract_function(file, signature) for file, signature in (
    ("paladins.c", "int aura_spell_protection_percent("),
    ("innates.c", "static int spell_penetration_threshold("),
    ("dam_mods.c", "static int arcane_block_reduction("),
    ("dam_mods.c", "static int elemental_power_level("),
    ("smagic.c", "int elemental_power_save_change("),
    ("smagic.c", "static int earthen_rain_damage("),
    ("smagic.c", "static int earthen_rain_saved("),
    ("smagic.c", "static int earthen_grasp_damage("),
    ("smagic.c", "static int earthen_grasp_saved_damage("),
)]
delivery = r'''
int spell_damage(P_char ch, P_char victim, double dam, int type, uint, damage_messages *, int *) {
    ++damage_calls;
    assert(type == SPLDAM_EARTH);
    raw_damage_seen = dam;
    damage_mod mod{dam_mod_type::None, 0};
    elemental_modifier(ch, victim, dam, type, 0, &mod, nullptr);
    damage_seen = int(dam * (1 + mod.mod));
    return DAM_NONEDEAD;
}
'''
handlers = [extract_function("smagic.c", signature) for signature in (
    "void spell_single_earthen_rain(", "void earthen_grasp(int level,"
)]
driver = r'''
int main() {
    char_data caster{}, victim{};
    caster.player.level = 50;
    caster.player.m_class = CLASS_SHAMAN;
    victim.player.m_class = CLASS_WARRIOR;
    SET_POS(&caster, POS_STANDING + STAT_NORMAL);
    SET_POS(&victim, POS_STANDING + STAT_NORMAL);
    // NPC victim avoids the independent PvP area multiplier.
    victim.player.name = const_cast<char *>("target");
    SET_BIT(victim.specials.act, ACT_ISNPC);
    rooms[0].sector_type = SECT_FIELD;
    dam_factor[DF_ELEMENTALIST] = get_property("damage.increase.elementalist", 1.15);
    assert(std::abs(dam_factor[DF_ELEMENTALIST] - 1.25) < 0.00001);
    for (bool bonus : {false, true}) {
        elemental = bonus;
        for (bool save : {false, true}) {
            saved = save;
            damage_calls = 0;
            spell_single_earthen_rain(50, &caster, nullptr, 0, &victim, nullptr);
            int base = int((save ? 396 : 600) * get_property("spell.area.damage.factor.earthenRain", 1.0));
            assert(damage_calls == 1 && raw_damage_seen == base);
            assert(damage_seen == (bonus ? base * 5 / 4 : base));
            for (bool greater : {false, true}) {
                damage_calls = 0;
                earthen_grasp(50, &caster, &victim, greater);
                assert(damage_calls == 1 && raw_damage_seen == 200);
                assert(damage_seen == (bonus ? 250 : 200));
                assert(applied.type == SPELL_EARTHEN_GRASP);
                assert(applied.duration == 5 * WAIT_SEC);
                assert(para_mod == (greater ? -2 : -WAIT_SEC / 3));
            }
        }
    }
    assert(elemental_power_save_change(50) == 5);
    assert(arcane_block_reduction(lowest_rolls, &victim) == 1);
    assert(arcane_block_reduction(highest_rolls, &victim) == 40);
    assert(spell_penetration_threshold(5) == 10);
    assert(spell_penetration_threshold(50) == 50);
    assert(spell_penetration_threshold(100) == 60);
    for (int level = 1; level <= 60; ++level) {
        caster.player.level = level;
        assert(aura_spell_protection_percent(&caster) == std::max(0, level / 2 - 3));
    }
    puts("Medium damage dispositions: single elemental bonus, preserved saves, configured bounds and aura floor passed.");
}
'''
build = ROOT / "bin/tests/medium-damage-dispositions"
build.mkdir(parents=True, exist_ok=True)
cpp, binary = build / "harness.cpp", build / "harness"
cpp.write_text(prelude + "\n".join(functions) + predicate + delivery + "\n".join(handlers) + driver)
subprocess.run(["g++", "-std=c++20", "-fsanitize=address,undefined,float-cast-overflow", "-g",
                "-I" + str(ROOT / "src"), str(cpp), str(HARNESS_STUBS), "-o", str(binary)], check=True)
subprocess.run([str(binary)], check=True)
