#!/usr/bin/env python3
"""Compile the character identity connections; broader site migration is still open."""

import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from _paths import ROOT, HARNESS_STUBS, source, extract_function


build = ROOT / "bin/tests"
build.mkdir(parents=True, exist_ok=True)
inputs = [
    ROOT / "tests/async/character_mechanics_harness.cpp",
    source("character_mechanics.c"), source("common.c"), source("constant.c"),
    source("creation_availability_config.c"), source("specializations.c"), source("utility.c"),
    HARNESS_STUBS,
]

# Compile these production bodies without unrelated world/combat services. The
# fixture observes the value delivered by melee_damage to raw_damage; it does
# not claim to exercise the latter's HP, death, ward or persistence machinery.
innates = source("innates.c").read_text()
properties = source("properties.c").read_text()
combat_prelude = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "net/comm.h"
#include "combat/damage.h"
#include "magic/spells.h"
#include "classes/necromancy.h"
#include <cassert>
#include <cctype>
#include <cmath>
#include <cstring>
#define PROPERTIES_FILE "lib/duris.properties"
#define MAX_PROPERTIES 3000
int properties_count;
float dam_factor[LAST_DF + 1];
static double delivered_damage;
static int damage_calls;
P_desc descriptor_list = nullptr;
void *__malloc(size_t size, const char *, const char *, int) { return malloc(size); }
void __free(void *p, const char *, int) { free(p); }
affected_type *get_spell_from_char(P_char ch, int spell, void *, int) {
    for (auto *af = ch->affected; af; af = af->next)
        if (af->type == spell) return af;
    return nullptr;
}
bool collector_presence_is_npc(P_char) { return false; }
int calculate_ac(P_char) { return 0; }
int number(int, int high) { return high; }
bool rapier_dirk_check(P_char) { return false; }
bool opposite_racewar(P_char, P_char) { assert(false && "fixture has no soulshield"); return false; }
int check_damage_ward(P_char, P_char, int) { return 0; }
bool decrease_skin_counter(P_char, unsigned int) { return false; }
void set_fighting(P_char, P_char) { assert(false && "fixture uses PHSDAM_NOENGAGE"); }
void DamageStuff(P_char, int) { assert(false && "fixture RNG suppresses equipment damage"); }
int attack_back(P_char, P_char, int) { assert(false && "fixture uses PHSDAM_NOENGAGE"); return 0; }
int check_shields(P_char, P_char, int, int) { assert(false && "fixture uses PHSDAM_NOSHIELDS"); return 0; }
int spell_damage(P_char, P_char, double, int, unsigned int, damage_messages *, int *) {
    assert(false && "fixture has no spell affects"); return 0;
}
int raw_damage(P_char, P_char, double amount, unsigned int, damage_messages *, int *) {
    delivered_damage = amount; ++damage_calls; return DAM_NONEDEAD;
}
'''
combat_bodies = (
    properties[properties.index("struct property\n{"):properties.index("int key_property_comp(")]
    + innates[innates.index("#define ADD_RACIAL_INNATE"):innates.index("float regen_factor")]
    + innates[innates.index("char racial_innates["):innates.index("extern const struct race_names")]
    + "\n".join(extract_function(file, signature) for file, signature in [
        ("properties.c", "int key_property_comp("),
        ("properties.c", "int property_comp("),
        ("properties.c", "int parse_property("),
        ("properties.c", "int load_properties("),
        ("properties.c", "float get_property(const char *key, double default_value, bool"),
        ("properties.c", "float get_property(const char *key, double default_value)"),
        ("properties.c", "int get_property(const char *key, int default_value, bool"),
        ("properties.c", "int get_property(const char *key, int default_value)"),
        ("innates.c", "static int innate_char_race("),
        ("innates.c", "static int innate_unlock_level("),
        ("innates.c", "bool has_innate("),
        ("innates.c", "void assign_innates("),
        ("fight.c", "void update_dam_factors("),
        ("fight.c", "int melee_damage("),
    ])
)
combat_driver = r'''
void load_character_properties() {
    properties_count = load_properties(duris_properties);
    assert(properties_count > 0);
    qsort(duris_properties, properties_count, sizeof(property), property_comp);
    update_dam_factors();
}
void set_bulwark_property(float value) {
    auto *p = static_cast<property *>(bsearch("damage.reduction.guardians.bulwark",
        duris_properties, properties_count, sizeof(property), key_property_comp));
    assert(p); p->value = value; update_dam_factors();
}
void clear_character_properties() {
    for (int i = 0; i < properties_count; ++i) free(duris_properties[i].key);
    properties_count = 0;
}
double bulwark_melee(P_char attacker, P_char victim, bool bypass) {
    damage_calls = 0; delivered_damage = -1;
    int flags = PHSDAM_NOPOSITION | PHSDAM_NOENGAGE | PHSDAM_NOSHIELDS;
    if (bypass) flags |= PHSDAM_NOREDUCE;
    assert(melee_damage(attacker, victim, 1000, flags, nullptr, nullptr) == DAM_NONEDEAD);
    assert(damage_calls == 1);
    return delivered_damage;
}
'''
with tempfile.TemporaryDirectory(prefix="character-mechanics-", dir=build) as directory:
    work = Path(directory)
    (work / "lib").mkdir()
    shutil.copyfile(ROOT / "lib/creation_availability.cfg", work / "lib/creation_availability.cfg")
    shutil.copyfile(ROOT / "lib/duris.properties", work / "lib/duris.properties")
    combat = work / "combat.cpp"
    combat.write_text(combat_prelude + combat_bodies + combat_driver)
    binary = work / "harness"
    subprocess.run([
        "g++", "-std=c++20", "-g", "-D__NO_MYSQL__", "-ffunction-sections", "-fdata-sections",
        "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-fno-pie", "-no-pie",
        "-I" + str(ROOT / "src"), "-I" + str(ROOT / "src/no_mysql"),
        *map(str, inputs), str(combat), "-Wl,--gc-sections", "-lbsd",
        "-o", str(binary),
    ], check=True)
    # Deliberately replace inherited overrides. No .env or running game is used.
    env = dict(os.environ, CHAOS_MUD="FALSE", CREATION_ALL_RACES="FALSE",
               CREATION_ALL_CLASSES="FALSE")
    subprocess.run([str(binary)], cwd=work, env=env, check=True)
    print("Native executable SHA256:", hashlib.sha256(binary.read_bytes()).hexdigest())
