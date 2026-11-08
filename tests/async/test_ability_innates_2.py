#!/usr/bin/env python3
"""Shared ability numbers, innates batch 2: the passive innates.

Builds src/abilities/abilities.c and the real RNG with this batch's shared and facts
functions, under sanitizers. Each roll keeps its pre-conversion expression below as an
oracle: under the same seeds it must give the same value and leave the RNG at the same
draw, inside the range the facts use. Pages are built for every viewer at every level:
they never roll and every line fits 79 columns. Source checks tie every handler to its
shared functions, in order where it has several.
"""
import re
import subprocess
import tempfile
from pathlib import Path

from _paths import ROOT, extract_function, source
from _source_contract import function_bodies, strip_comments

# Shared functions and their pages, by file. Order matters: later ones call earlier ones.
SHARED = {
    "classes/bard.c": "echo_song_level bard_pulse hasted_bard_pulse get_bard_pulse bard_blind_play_rating echo_chance echo_roll echo_delay".split(),
    "classes/drannak.c": "intercept_luck_roll intercept_attack_roll intercept_duration".split(),
    "combat/fight.c": """acid_blood_min_hit acid_blood_dodge_base acid_blood_dodge_divisor spell_absorb_damage_divisor leap_chance_floor leap_chance_top intercept_attack_share rapier_dirk_chance rapier_dirk_more_hits_roll rapier_dirk_more_hits
        two_daggers_riposte_roll rrakkma_ac_step spell_absorb_damage_roll spell_absorb_threshold aura_absorb_healing aura_absorb_cap
        acid_blood_roll acid_blood_damage infernal_fury_shield touch_vamp_share frightening_presence_chance
        battle_frenzy_roll battle_frenzy_damage weapon_immunity_damage weapon_immunity_unarmed_level leap_chance
        giant_avoidance_factor groundfighting_dodge_share""".split(),
    "classes/innates.c": """parasite_bite_disease_roll resurrection_roll resurrection_hit_points resurrection_lag
        embrace_death_first_share embrace_death_second_share embrace_death_third_share
        embrace_death_first_bonus embrace_death_second_bonus embrace_death_third_bonus
        anti_evil_alignment anti_evil_hit_points decrepify_curse holy_crusade_healing holy_crusade_cap
        anti_evil_fade anti_evil_fade_interval embrace_death_check_interval troll_burned_regeneration hatred_check_delay hatred_pulse_modifier rrakkma_max_steps rrakkma_step_percent""".split(),
    "magic/affects.c": """command_aura_hit_dam command_aura_avenger_regen command_aura_stat_max
        command_aura_lightbringer_armor command_aura_fear_save dual_wielding_master_hitroll weapon_master_hitroll
        hammer_master_damroll blade_master_damroll weapon_master_facts gamblers_luck_bonus two_daggers_pulse""".split(),
    "classes/necromancy.c": "unholy_alliance_charm_duration".split(),
    "classes/psionics.c": "wormhole_range improved_wormhole_decay improved_wormhole_bonus".split(),
    "cmd/actoff.c": """flee_vitality_cost flee_mount_vitality_cost dragonmind_roll dragonmind_steal_divisor
        trample_knight_multiplier""".split(),
    "cmd/actoth.c": "combat_mind_quaff_chance".split(),
    "world/handler.c": """calming_delay calming_level_gap calming_gap_roll calming_notarget_percent calming_notarget_roll
        calming_command_roll calming_chance_bonus calming_switch_threshold calming_switch_penalty
        vuln_sun_damage""".split(),
    "cmd/track.c": "perception_track_bonus farsee_track_bonus ophidian_track_bonus track_sense_chance".split(),
    "world/map.c": "eyeless_map_range forest_map_cap perception_map_bonus dayblind_infravision_bonus dayblind_underdark_range".split(),
    "cmd/actinf.c": "ophidian_farsee_level ophidian_invisible_level".split(),
    "core/utility.c": """undead_fealty_gap two_handed_sword_mastery_rating quick_thinking_percent quick_thinking_roll
        haste_stat_save_bonus evasion_remove_chance evasion_dragon_roll evasion_snake_roll""".split(),
    "net/sparser.c": """wildmagic_roll wildmagic_control_roll wildmagic_health_roll wildmagic_health_change
        wildmagic_bystander_roll haste_cast_time_share""".split(),
    "combat/range.c": "archery_haste_speed archery_blur_speed".split(),
    "world/limits.c": "regeneration_sleeping_multiple regeneration_resting_multiple regeneration_lines".split(),
    "combat/dam_mods.c": """spell_mod_text elemental_power_level magical_reduction_mod magic_vulnerability_mod
        troll_burn_duration fire_race_cold_mod sacrilegious_holy_factor vuln_cold_slow_save vuln_cold_slow_duration
        warcallers_fury_bonus warcallers_fury_max_steps warcallers_fury_step""".split(),
    "combat/grapple.c": "entrapment_chance entrapment_lag".split(),
    "magic/smagic.c": """restoration_other_share elemental_power_save_change elemental_power_area_factor
        wellness_improved_bonus lesser_mending_improved_bonus mending_improved_bonus greater_mending_cure_level""".split(),
    "magic/magic.c": "stone_skin_absorb stone_skin_living_stone embalm_hours corpse_embalm_innate_facts blur_duration".split(),
    "magic/spells.c": "wall_climb_roll wall_climb_above wall_climb_text wall_of_flames_protected wall_of_ice_protected".split(),
    "ships/ship_utils.c": "seadog_speed_bonus seadog_sale_multiplier".split(),
}

INNATES = [line.split() for line in """
INNATE_BLINDSINGING blindsinging classes/bard.c
INNATE_ECHO echo classes/bard.c
INNATE_INTERCEPT intercept classes/drannak.c
INNATE_DISEASED_BITE diseased_bite classes/innates.c
INNATE_HATRED hatred classes/innates.c
INNATE_HOLY_CRUSADE holy_crusade classes/innates.c
INNATE_LEAP leap combat/fight.c
INNATE_RAPIER_DIRK rapier_dirk classes/innates.c
INNATE_RESURRECTION resurrection classes/innates.c
INNATE_TWO_DAGGERS two_daggers classes/innates.c
INNATE_UNHOLY_ALLIANCE unholy_alliance classes/necromancy.c
INNATE_IMPROVED_WORMHOLE improved_wormhole classes/psionics.c
INNATE_OPHIDIAN_EYES ophidian_eyes cmd/actinf.c
INNATE_DRAGONMIND dragonmind cmd/actoff.c
INNATE_IMPROVED_FLEE improved_flee cmd/actoff.c
INNATE_KNIGHT knight cmd/actoff.c
INNATE_CALMING calming world/handler.c
INNATE_SACRILEGIOUS_POWER sacrilegious_power combat/dam_mods.c
INNATE_VULN_COLD vuln_cold combat/dam_mods.c
INNATE_VULN_FIRE vuln_fire combat/dam_mods.c
INNATE_WARCALLERS_FURY warcallers_fury combat/dam_mods.c
MAGICAL_REDUCTION magical_reduction combat/dam_mods.c
MAGIC_VULNERABILITY magic_vulnerability combat/dam_mods.c
INNATE_ACID_BLOOD acid_blood combat/fight.c
INNATE_BATTLE_FRENZY battle_frenzy combat/fight.c
INNATE_DECREPIFY decrepify classes/innates.c
INNATE_EMBRACE_DEATH embrace_death classes/innates.c
INNATE_FPRESENCE fpresence combat/fight.c
INNATE_GIANT_AVOIDANCE giant_avoidance combat/fight.c
INNATE_GROUNDFIGHTING groundfighting combat/fight.c
INNATE_GUARDIANS_BULWARK guardians_bulwark combat/fight.c
INNATE_MELEE_MASTER melee_master combat/fight.c
INNATE_MUMMIFY mummify magic/magic.c
INNATE_REQUIEM requiem magic/magic.c
INNATE_RRAKKMA rrakkma classes/innates.c
INNATE_SPELL_ABSORB spell_absorb combat/fight.c
INNATE_TROLL_SKIN troll_skin combat/fight.c
INNATE_WEAPON_IMMUNITY weapon_immunity combat/fight.c
INNATE_ENTRAPMENT entrapment combat/grapple.c
INNATE_BLUR blur magic/magic.c
INNATE_EVASION evasion core/utility.c
INNATE_QUICK_THINKING quick_thinking core/utility.c
INNATE_UNDEAD_FEALTY undead_fealty core/utility.c
TWO_HANDED_SWORD_MASTERY two_handed_sword_mastery core/utility.c
INNATE_SEADOG seadog ships/ship_utils.c
INNATE_COMMAND_AURA command_aura magic/affects.c
INNATE_ANTI_EVIL anti_evil classes/innates.c
INNATE_AXE_MASTER axe_master magic/affects.c
INNATE_DUAL_WIELDING_MASTER dual_wielding_master magic/affects.c
INNATE_DAYBLIND dayblind world/map.c
INNATE_EYELESS eyeless world/map.c
INNATE_FARSEE farsee cmd/track.c
INNATE_FIRE_AURA fire_aura combat/dam_mods.c
INNATE_GAMBLERS_LUCK gamblers_luck magic/affects.c
INNATE_HAMMER_MASTER hammer_master magic/affects.c
INNATE_HASTE haste magic/magic.c
INNATE_ICE_AURA ice_aura combat/dam_mods.c
INNATE_INFERNAL_FURY infernal_fury combat/fight.c
INNATE_LONGSWORD_MASTER longsword_master magic/affects.c
INNATE_PERCEPTION perception cmd/track.c
INNATE_PROT_COLD prot_cold combat/dam_mods.c
INNATE_PROT_FIRE prot_fire combat/dam_mods.c
INNATE_REGENERATION regeneration world/limits.c
INNATE_VAMPIRIC_TOUCH vampiric_touch combat/fight.c
INNATE_LIVING_STONE living_stone magic/magic.c
INNATE_ELEMENTAL_POWER elemental_power combat/dam_mods.c
INNATE_IMPROVED_HEAL improved_heal magic/smagic.c
INNATE_MAGIC_RESISTANCE magic_resistance classes/innates.c
INNATE_WILDMAGIC wildmagic net/sparser.c
INNATE_WALL_CLIMBING wall_climbing magic/spells.c
INNATE_VULN_SUN vuln_sun world/handler.c
INNATE_ELEMENTAL_BODY elemental_body world/limits.c
INNATE_WOODLAND_RENEWAL woodland_renewal world/limits.c
INNATE_FOREST_SIGHT forest_sight world/map.c
""".strip().splitlines()]

NO_NUMBERS = """HOLY_COMBAT INNATE_BOW_MASTERY INNATE_DAMAGE_SPREAD INNATE_DAYVISION INNATE_OUTDOOR_SNEAK
    INNATE_SPEED INNATE_UD_SNEAK INNATE_WARDING_FAITH INNATE_ARCANE_RUDIMENTS INNATE_BATTLEAID INNATE_DET_SUBVERSION
    INNATE_DECEPTIVE_FLEE INNATE_HORSE_BODY INNATE_SENSE_WEAKNESS INNATE_SPIDER_BODY INNATE_SNEAK INNATE_AIR_AFFINITY
    INNATE_ASTRAL_NATIVE INNATE_EARTH_AFFINITY INNATE_FIRE_AFFINITY INNATE_WATER_AFFINITY INNATE_BARTER INNATE_ANTI_GOOD
    INNATE_BLOOD_SCENT INNATE_DAUNTLESS INNATE_FLY INNATE_HOLY_LIGHT INNATE_INFRAVISION INNATE_INVISIBILITY
    INNATE_NATURAL_MOVEMENT INNATE_PROT_ACID INNATE_PROT_LIGHTNING INNATE_ULTRAVISION INNATE_WATERBREATH
    INNATE_AMORPHOUS_BODY INNATE_MINER INNATE_SWAMP_SNEAK INNATE_VISION_OF_THE_DEAD""".split()

# Damage factors the pages read, with their properties in lib/duris.properties.
FACTORS = {
    "DF_SWASHBUCKLER_OFFENSE": "damage.increase.swashbuckler",
    "DF_SWASHBUCKLER_DEFENSE": "damage.reduction.swashbuckler",
    "DF_VULNFIRE": "damage.increase.vulnFire",
    "DF_VULNCOLD": "damage.increase.vulnCold",
    "DF_PROTECTION": "damage.reduction.protElement",
    "DF_PROTECTION_TROLL": "damage.reduction.protFire.Troll",
    "DF_ELSHIELDRED_TROLL": "damage.reduction.fireColdShield.Troll",
    "DF_ELEMENTALIST": "damage.increase.elementalist",
    "DF_TROLLSKIN": "damage.reduction.trollskin",
    "DF_GUARDIANS_BULWARK": "damage.reduction.guardians.bulwark",
    "DF_MELEEMASTERY": "damage.modifier.meleemastery",
    "DF_TOUCHVAMP": "vamping.vampiricTouch",
    "DF_ARROWVAMP": "vamping.vampiricTouch.arrow",
    "DF_ANTIPALADINVAMP": "vamping.vampiricTouch.antipaladin",
    "DF_MONKVAMP": "vamping.vampiricTouch.monk",
    "DF_MERCENARYVAMP": "vamping.vampiricTouch.mercenary",
    "DF_WARRIORVAMP": "vamping.vampiricTouch.warrior",
    "DF_BERSERKERVAMP": "vamping.vampiricTouch.berserker",
    "DF_ROGUEVAMP": "vamping.vampiricTouch.rogue",
    "DF_PALADINVAMP": "vamping.vampiricTouch.paladin",
    "DF_RANGERVAMP": "vamping.vampiricTouch.ranger",
    "DF_DLORDAVGRVAMP": "vamping.vampiricTouch.dreadlord.or.avenger",
}


def dam_factors():
    """Each page factor from the live properties file, after checking fight.c reads that key."""
    properties = dict(re.findall(r"^([\w.-]+)=([\d.-]+)", (ROOT / "lib/duris.properties").read_text(errors="replace"), re.M))
    fight = re.sub(r"\s+", "", source("combat/fight.c").read_text(errors="replace"))
    lines = []
    for factor, key in FACTORS.items():
        assert f'dam_factor[{factor}]=get_property("{key}",' in fight, factor
        lines.append(f"    dam_factor[{factor}] = {float(properties[key])}f;")
    return "\n".join(lines)


HARNESS = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "combat/damage.h"
#include "magic/spells.h"
#include "abilities/abilities.h"
#include "ships/ships.h"
#include <algorithm>
#include <cassert>
#include <climits>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <iostream>
#include <map>
#include <sstream>
#include <string>

void randomize(uint64_t seed);

extern const int race_hatred_data[][MAX_HATRED];
const int race_hatred_data[][MAX_HATRED] = { { RACE_MOUNTAIN, RACE_ORC, RACE_DUERGAR, RACE_DROW, -1 }, { -1, -1, -1, -1, -1 } };
static const race_names names_table[LAST_RACE + 2] = {};
extern const struct race_names race_names_table[];
float dam_factor[LAST_DF + 1];
int map_dayblind_modifier;
float regen_factor[REG_MAX + 1];
static std::map<std::string, int> asked;
float get_property(const char *key, double fallback) { asked[key]++; return (float)fallback; }
int get_property(const char *key, int fallback) { asked[key]++; return fallback; }
static bool innate_on;
bool has_innate(P_char, int) { return innate_on; }
int GET_CHAR_SKILL_P(P_char, int) { return 100; }
bool affected_by_spell(P_char, int) { return false; }
static int resistance = 40, regeneration = 56, terrain = 3, load = 150;
int get_innate_resistance(P_char) { return resistance; }
int get_innate_regeneration(P_char) { return regeneration; }
int attuned_to_terrain(P_char) { return terrain; }
int load_modifier(P_char) { return load; }
int desecrate_land_shrug_penalty() { return 10; }
// abilities.c's whole table would pull in every page; the bite only asks for disease's.
static std::string disease_page(P_char) { return "  Disease spell page\n"; }
static AbilityFacts test_ability_facts(int spell) { assert(spell == SPELL_DISEASE); return disease_page; }

FUNCTIONS

static int fingerprint() { return number(0, INT_MAX); }

template <typename Original, typename Shared>
static void same(const char *name, Original original, Shared shared) {
    const int a = shared(lowest_rolls), b = shared(highest_rolls);
    for (uint64_t seed = 1; seed <= 40; ++seed) {
        randomize(seed);
        const int expected = original(), expected_next = fingerprint();
        randomize(seed);
        const int actual = shared(live_rolls), actual_next = fingerprint();
        if (actual != expected || actual_next != expected_next ||
            actual < std::min(a, b) || actual > std::max(a, b)) {
            std::fprintf(stderr, "%s: seed %d gave %d, expected %d in %d..%d\n", name, (int)seed,
                         actual, expected, a, b);
            std::abort();
        }
    }
}
#define SAME(original, shared) \
    same(#shared, [&] { return (int)(original); }, [&](const Rolls &rolls) { return (int)(shared); })

static pc_only_data pc_data;
static char_data viewer(uint m_class, int spec, int race, int level, int stat = 100) {
    char_data ch{};
    ch.player.m_class = m_class;
    ch.player.spec = spec;
    ch.player.race = race;
    ch.player.level = level;
    ch.only.pc = &pc_data;
    ch.curr_stats.Str = ch.curr_stats.Dex = ch.curr_stats.Agi = ch.curr_stats.Int = stat;
    ch.curr_stats.Pow = ch.curr_stats.Luk = ch.curr_stats.Wis = ch.curr_stats.Cha = stat;
    ch.curr_stats.Con = stat;
    ch.points.base_hit = stat * 3;
    ch.points.max_hit = stat * 3;
    ch.points.damroll = stat / 5;
    return ch;
}

struct Page { const char *name; std::string (*facts)(P_char); };
static const Page pages[] = {
PAGES
};

static void setup() {
    for (int race = 0; race <= LAST_RACE; ++race)
        stub_race_names[race].normal = "race";
    stub_race_names[RACE_MOUNTAIN].normal = "Mountain Dwarf";
    stub_race_names[RACE_ORC].normal = "Orc";
    stub_race_names[RACE_DUERGAR].normal = "Duergar";
    stub_race_names[RACE_DROW].normal = "Drow Elf";
    // The live values of lib/duris.properties, checked against the file below.
DAM_FACTORS
    regen_factor[REG_HUNTSMAN] = 3.0f;
}

MAIN
'''

def extract_named(file, name):
    text = source(file).read_text(errors="replace")
    match = re.search(rf"^(?:static )?[\w:]+(?: \w+)? \*?{name}\([^;\n]*\)\n{{", text, re.M)
    assert match, name
    return extract_function(file, match.group(0))


def build(main_text, run=True):
    period = re.search(r"#define GENERIC_CHAR_EVENT_PERIOD .*", source("world/handler.c").read_text()).group(0)
    functions = [period, extract_function("utility.c", "int dice(int num, int size)"),
                 extract_function("utility.c", "int BOUNDED(int a, int b, int c)"),
                 extract_function("utility.c", "float BOUNDEDF(float a, float b, float c)"),
                 extract_function("utility.c", "int GET_CLASS(P_char ch, uint m_class)"),
                 extract_function("utility.c", "int GET_PRIME_CLASS(P_char ch, uint m_class)"),
                 extract_function("utility.c", "int GET_SECONDARY_CLASS(P_char ch, uint m_class)")]
    facts = {}
    for _, name, file in INNATES:
        facts.setdefault(file, []).append(name)
    for file in SHARED:
        for name in SHARED[file]:
            functions.append(extract_named(file, name))
        for name in facts.get(file, []):
            functions.append(extract_function(file, f"std::string {name}_innate_facts(P_char"))
    missing = set(facts) - set(SHARED)
    pages = ",\n".join(f'    {{ "{name}", {name}_innate_facts }}' for _, name, _ in INNATES)
    text = HARNESS.replace("DAM_FACTORS", dam_factors()).replace("PAGES", pages).replace("MAIN", main_text).replace("FUNCTIONS", "\n".join(functions))
    text = text.replace("= ability_facts(SPELL_DISEASE)", "= test_ability_facts(SPELL_DISEASE)")
    text = text.replace("race_names_table", "stub_race_names", 99).replace(
        "static const race_names names_table[LAST_RACE + 2] = {};\nextern const struct race_names stub_race_names[];",
        "static struct race_names stub_race_names[LAST_RACE + 2];")
    assert not missing, missing
    out = ROOT / "bin/tests"
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ability-innates-2-", dir=out) as temporary:
        directory = Path(temporary)
        harness = directory / "innates2.cpp"
        harness.write_text(text)
        binary = directory / "innates2"
        subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-Wno-unused-function",
                        "-ffunction-sections", "-fdata-sections", "-Wl,--gc-sections",
                        "-fsanitize=address,undefined", "-fno-sanitize-recover=undefined",
                        "-Isrc", "-I/usr/include/mysql", "-I/usr/include/libxml2",
                        str(harness), "src/abilities/abilities.c", "src/core/random.c",
                        "-o", str(binary)], cwd=ROOT, check=True)
        return subprocess.run([str(binary)], check=True, stdout=subprocess.PIPE, text=True).stdout


CHECKS = r"""
static bool failed;
#define CHECK(condition) do { if (!(condition)) { std::fprintf(stderr, "failed: %s\n", #condition); failed = true; } } while (0)

static void check_rolls() {
    for (int level : { 1, 10, 28, 30, 50, 56, 60 }) {
        char_data subject = viewer(CLASS_PALADIN, 0, RACE_HUMAN, level);
        P_char ch = &subject;
        SAME(number(1, GET_C_LUK(ch)), intercept_luck_roll(rolls, ch));
        SAME(number(1, (int)(level / 28)), rapier_dirk_more_hits(rolls, level));
        SAME(GET_DAMROLL(ch) * GET_LEVEL(ch) * number(1, 2) / 40, battle_frenzy_damage(rolls, ch));
        SAME((int)(level / 4 + number(1, 5)), wildmagic_health_change(rolls, level));
        SAME((int)(number((int)(level / 2), (int)(level * 1.5))), lesser_mending_improved_bonus(rolls, level));
        SAME((int)(number((int)(level / 2), (int)(level))), mending_improved_bonus(rolls, level));
        SAME(level / 4 + number(1, 4), stone_skin_absorb(rolls, level));
        for (int attacker : { 1, 30, 56, 62 }) {
            const int holder = level;
            same("frightening_presence_chance",
                 [&] { int chance; if (holder >= attacker) chance = 15 + dice(1, 10); else chance = 15; return chance; },
                 [&](const Rolls &rolls) { return frightening_presence_chance(rolls, holder, attacker); });
        }
    }
    SAME(number(1, 800), intercept_attack_roll(rolls));
    SAME(number(0, 3), rapier_dirk_more_hits_roll(rolls));
    SAME(number(0, 19), two_daggers_riposte_roll(rolls));
    SAME(number(0, 7 - 0), parasite_bite_disease_roll(rolls, 0));
    SAME(number(0, 8), resurrection_roll(rolls));
    SAME(dice(2, 2) * 4, resurrection_lag(rolls));
    SAME(number(0, 9), acid_blood_roll(rolls));
    SAME(40 + number(1, 40), acid_blood_damage(rolls));
    SAME(number(0, 20), battle_frenzy_roll(rolls));
    SAME(number(20, 30), flee_vitality_cost(rolls));
    SAME(number(30, 40), flee_mount_vitality_cost(rolls));
    SAME(number(0, 1), dragonmind_roll(rolls));
    SAME(number(0, 3), calming_gap_roll(rolls));
    SAME(number(0, 19), calming_command_roll(rolls));
    SAME(number(5, 20), vuln_sun_damage(rolls));
    SAME(number(0, 5), wildmagic_roll(rolls));
    SAME(number(0, 2), wildmagic_control_roll(rolls));
    SAME(number(0, 3), wildmagic_health_roll(rolls));
    SAME(number(0, 6), wildmagic_bystander_roll(rolls));
    SAME(number(1, 100), wall_climb_roll(rolls));
}

// The old if-chains and arithmetic over their whole range.
static void check_moves() {
    CHECK(echo_chance(SECT_MOUNTAIN) == 30 && echo_chance(SECT_HILLS) == 25);
    CHECK(echo_chance(SECT_FOREST) == 15 && echo_chance(SECT_INSIDE) == 20);
    for (int level = 1; level <= 62; ++level) {
        double old = 1.0;
        if (level >= 46) old = 0.75;
        if (level >= 51) old = 0.5;
        if (level >= 56) old = 0.25;
        CHECK(sacrilegious_holy_factor(level) == old);
        CHECK(decrepify_curse(level) == BOUNDED(1, (int)(level / 10), 5));
        CHECK(command_aura_hit_dam(level) == level / 12 && command_aura_avenger_regen(level) == level / 2);
        CHECK(command_aura_stat_max(level) == level / 10 && command_aura_lightbringer_armor(level) == -level);
        CHECK(command_aura_fear_save(level) == -(level / 10));
        CHECK(dual_wielding_master_hitroll(level) == level / 5 && weapon_master_hitroll(level) == level / 8);
        CHECK(hammer_master_damroll(level) == level / 10 && blade_master_damroll(level) == level / 12);
        CHECK(calming_switch_threshold(level) == level * 2);
        CHECK(spell_absorb_threshold(level) == level / 2);
        CHECK(elemental_power_save_change(level) == level / 10);
        CHECK(track_sense_chance(level) == 10 + ((level > 46) ? (2 * (level - 46)) : 0));
        CHECK(anti_evil_hit_points(level) == level * 2 && holy_crusade_healing(level) == 2 * level);
        for (int group = 0; group <= 8; ++group)
            CHECK(warcallers_fury_bonus(group, level) ==
                  BOUNDEDF(.02, (group / 100.0) + (level / 1120.0), (double).15));
        for (int rating : { 0, 50, 100 })
            CHECK(entrapment_chance(level, rating) == (int)(((level / 2) + (rating / 10)) * 1.0f));
    }
    CHECK(embrace_death_first_share() == .75 && embrace_death_second_share() == .45 && embrace_death_third_share() == .25);
    CHECK(embrace_death_first_bonus() == 5 && embrace_death_second_bonus() == 10 && embrace_death_third_bonus() == 15);
    CHECK(calming_switch_penalty(40) == 70 && calming_chance_bonus() == 10 && calming_level_gap() == 5);
    CHECK(wall_climb_above() == 60 && intercept_duration() == 100 && unholy_alliance_charm_duration() == -1);
    CHECK(acid_blood_min_hit(0) == 5 && acid_blood_min_hit(PHSDAM_TOUCH) == 9 && acid_blood_dodge_base() == 15 && acid_blood_dodge_divisor() == 6);
    CHECK(spell_absorb_damage_divisor() == 50 && anti_evil_fade() == 2 && anti_evil_fade_interval() == 2 * WAIT_SEC);
    CHECK(embrace_death_check_interval() == 2 * WAIT_SEC && troll_burned_regeneration() == 1 && echo_song_level(100) == 50);
    CHECK(hatred_pulse_modifier() == -1 && two_handed_sword_mastery_rating() == 100 && gamblers_luck_bonus() == 10);
    CHECK(improved_wormhole_decay(120) == 180 && improved_wormhole_bonus() == 3);
    CHECK(aura_absorb_healing(100.0) == 25.0 && giant_avoidance_factor() == 1.10 && groundfighting_dodge_share() == 0.50);
    CHECK(seadog_speed_bonus() == 2 && seadog_sale_multiplier() == 1.10 && haste_cast_time_share() == .8);
    CHECK(magical_reduction_mod() == -0.2 && magic_vulnerability_mod() == 0.1 && restoration_other_share() == 0.66);
    CHECK(fire_race_cold_mod(false) == (double)dam_factor[DF_VULNCOLD] - 1.0);
    CHECK(fire_race_cold_mod(true) == (.75 * dam_factor[DF_VULNCOLD]) - 1.0);
    char_data big = viewer(CLASS_PALADIN, 0, RACE_HUMAN, 56);
    big.points.max_hit = 50;
    CHECK(resurrection_hit_points(&big) == 50);
    big.points.max_hit = 500;
    CHECK(resurrection_hit_points(&big) == 100 && (int)holy_crusade_cap(&big) == 550 && (int)aura_absorb_cap(&big) == 550);
    big.points.max_hit = 5;
    CHECK(resurrection_hit_points(&big) == 10);
    // Leap's clamp, and its level gap.
    char_data leaper = viewer(CLASS_WARRIOR, 0, RACE_THRIKREEN, 30, 140);
    load = 0;
    CHECK(leap_chance(&leaper, 30) == 20 && leap_chance(&leaper, 62) == 4);
    load = 5000;
    CHECK(leap_chance(&leaper, 30) == 1);
    load = 150;
    // The touch share's class order: illithid before class, antipaladin before warrior.
    char_data toucher = viewer(CLASS_ANTIPALADIN, 0, RACE_ILLITHID, 56);
    CHECK(touch_vamp_share(&toucher) == dam_factor[DF_TOUCHVAMP]);
    toucher.player.race = RACE_HUMAN;
    CHECK(touch_vamp_share(&toucher) == dam_factor[DF_ANTIPALADINVAMP]);
    toucher.player.m_class = CLASS_DREADLORD;
    CHECK(touch_vamp_share(&toucher) == dam_factor[DF_DLORDAVGRVAMP]);
    toucher.player.m_class = CLASS_SORCERER;
    CHECK(touch_vamp_share(&toucher) == dam_factor[DF_TOUCHVAMP]);
}

// Every page for every viewer and level: no rolls, nothing over 79 columns, no broken ranges.
static void sweep_pages() {
    const uint classes[] = { CLASS_PALADIN, CLASS_ANTIPALADIN, CLASS_MONK, CLASS_DREADLORD, CLASS_AVENGER, CLASS_ROGUE, CLASS_SORCERER, CLASS_BARD };
    const int races[] = { RACE_HUMAN, RACE_TROLL, RACE_THRIKREEN, RACE_EFREET, RACE_MOUNTAIN, RACE_ILLITHID };
    for (uint m_class : classes)
        for (int race : races)
            for (int level = 1; level <= 62; ++level)
                for (int stat : { 1, 100, 200 })
                    for (bool flag : { false, true }) {
                        innate_on = flag;
                        resistance = level;
                        regeneration = level * 2;
                        char_data ch = viewer(m_class, 0, race, level, stat);
                        for (const Page &page : pages) {
                            randomize(7);
                            const int expected = fingerprint();
                            randomize(7);
                            const std::string text = page.facts(&ch);
                            CHECK(fingerprint() == expected);
                            CHECK(!text.empty());
                            std::istringstream lines(text);
                            std::string line;
                            while (std::getline(lines, line))
                                if (line.size() > 79 || line.rfind("  ", 0) != 0 || line.find("--") != std::string::npos ||
                                    line.find("+-") != std::string::npos || line.find("in -") != std::string::npos ||
                                    line.find(" -1 in") != std::string::npos || line.find(": ,") != std::string::npos) {
                                    std::fprintf(stderr, "%s: [%s] %zu\n", page.name, line.c_str(), line.size());
                                    failed = true;
                                }
                        }
                    }
    innate_on = false;
    resistance = 40;
    regeneration = 56;
}

// The one conditional line: a troll's burn.
static void check_conditions() {
    char_data human = viewer(CLASS_PALADIN, 0, RACE_HUMAN, 56), troll = viewer(CLASS_PALADIN, 0, RACE_TROLL, 56);
    CHECK(regeneration_innate_facts(&human).find("After fire") == std::string::npos);
    CHECK(regeneration_innate_facts(&troll).find("  After fire spell damage, awake: +1 for 30 seconds\n") != std::string::npos);
    char_data low = viewer(CLASS_MONK, SPEC_WAYOFSNAKE, RACE_HUMAN, 10);
    CHECK(evasion_innate_facts(&low).find("  Way of the snake: chance to avoid an area spell: 0 in 100\n") != std::string::npos);
    CHECK(rapier_dirk_innate_facts(&low).find("1 plus 0-1 on a 1 in 4") != std::string::npos);
}

static void check_keys() {
    for (const char *key : { "attacks.intercept.multiplier", "damage.shield.infernalfuryshield", "innate.dualDaggers.pulse",
                             "innate.rrakkma.maxSteps", "innate.rrakkma.stepPct", "innate.timer.hatred", "innate.calming.delay",
                             "innate.calming.notarget.perc", "saves.quickthinking.percentage", "innate.evasion.removechance",
                             "innate.warcallersfury.maxSteps", "grapple.entrapment.chance.mod", "skill.trample.Knight.DamageMultiplier",
                             "damage.increase.elementalist", "portals.wormhole.decayTimeout", "spell.dim.perlevel.modifier" })
        if (!asked[key]) {
            std::fprintf(stderr, "nothing read %s\n", key);
            failed = true;
        }
}

int main() {
    setup();
    check_rolls();
    check_moves();
    sweep_pages();
    check_conditions();
    asked.clear();
    char_data ch = viewer(CLASS_PALADIN, 0, RACE_HUMAN, 56);
    for (const Page &page : pages)
        std::cout << "== " << page.name << "\n" << page.facts(&ch);
    entrapment_chance(56, 100);
    wormhole_range(56);
    check_keys();
    return failed ? 1 : 0;
}
"""

# Each handler's text: the shared calls, in order. "ALL" looks through the whole file.
HANDLER_CALLS = {
    ("classes/bard.c", "has_instrument"): ["bard_blind_play_rating()"],
    ("classes/bard.c", "event_bardsong"): ["echoChance = echo_chance(terrainType);", "echoChance >= echo_roll(live_rolls)", "add_event(event_echosong, echo_delay(ch),"],
    ("classes/drannak.c", "intercept_defensiveproc"): ["int num1 = intercept_luck_roll(live_rolls, merc);", "int num2 = intercept_attack_roll(live_rolls);", "num1 < num2", "af.duration = intercept_duration();"],
    ("combat/fight.c", "rapier_dirk"): ["chance = rapier_dirk_chance(victim);", "chance > number(1, 1000)", "!rapier_dirk_more_hits_roll(live_rolls) && CanDoFightMove(victim, attacker)", "f = rapier_dirk_more_hits(live_rolls, GET_LEVEL(victim));"],
    ("combat/fight.c", "try_riposte"): ["innate_two_daggers(ch) && !two_daggers_riposte_roll(live_rolls)"],
    ("combat/fight.c", "calculate_ac"): ["victim_ac -= rrakkma_ac_step();"],
    ("combat/fight.c", "check_shields"): ["double ifshield = infernal_fury_shield();", "(int)(dam * ifshield), SPLDAM_NEGATIVE", "(dam > acid_blood_min_hit(flags)) && !acid_blood_roll(live_rolls)", "(acid_blood_dodge_base() + GET_C_AGI(ch) / acid_blood_dodge_divisor()) > number(0, 100)", "spell_damage(victim, ch, acid_blood_damage(live_rolls), SPLDAM_ACID, SPLDAM_NOSHRUG | SPLDAM_NODEFLECT,"],
    ("combat/fight.c", "check_vamp"): ["static_cast<double>(dam) * touch_vamp_share(ch)"],
    ("combat/fight.c", "spell_damage"): ["vamp(victim, aura_absorb_healing(dam), aura_absorb_cap(victim));", "vamp(victim, aura_absorb_healing(dam), aura_absorb_cap(victim));", "evasion_remove_chance() > evasion_dragon_roll(live_rolls)", "(dam / spell_absorb_damage_divisor()) > spell_absorb_damage_roll(live_rolls)", "number(1, 100) <= spell_absorb_threshold(GET_LEVEL(victim))"],
    ("combat/fight.c", "melee_damage"): ["dam *= dam_factor[DF_TROLLSKIN];", "victim->equipment[WEAR_SHIELD]", "dam *= dam_factor[DF_GUARDIANS_BULWARK];", "dam *= dam_factor[DF_SWASHBUCKLER_DEFENSE];", "dam *= dam_factor[DF_SWASHBUCKLER_OFFENSE];"],
    ("combat/fight.c", "frightening_presence"): ["chance = frightening_presence_chance(live_rolls, GET_LEVEL(victim), GET_LEVEL(ch));", "number(0, 100) < chance && !fear_check(ch)"],
    ("combat/fight.c", "battle_frenzy"): ["dam = battle_frenzy_damage(live_rolls, ch);", "chance_to_hit(ch, victim, GET_CHAR_SKILL(ch, SKILL_UNARMED_DAMAGE), 0) > number(0, 100)"],
    ("combat/fight.c", "leapSucceed"): ["chance = leap_chance(victim, GET_LEVEL(attacker));", "number(1, 100) > chance"],
    ("combat/fight.c", "dodgeSucceed"): ["learned *= giant_avoidance_factor();", "percent = (int)(percent * groundfighting_dodge_share());"],
    ("combat/fight.c", "ALL"): ["has_innate(ch, INNATE_BATTLE_FRENZY) && !battle_frenzy_roll(live_rolls) && IS_HUMANOID(victim)", "dam *= dam_factor[DF_MELEEMASTERY];", "dam = weapon_immunity_damage();", "GET_LEVEL(ch) < weapon_immunity_unarmed_level()", "attacksMultiplier = intercept_attack_share();", "mummify(killer, ch, corpse);"],
    ("classes/necromancy.c", "mummify"): ["spell_embalm(MAXLVL, ch, 0, SPELL_TYPE_SPELL, NULL, corpse);"],
    ("classes/innates.c", "parasitebite"): ["!parasite_bite_disease_roll(live_rolls, mod)", "spell_disease(level, ch, 0, SPELL_TYPE_SPELL, victim, 0);"],
    ("classes/innates.c", "check_reincarnate"): ["!resurrection_roll(live_rolls)", "GET_HIT(ch) = resurrection_hit_points(ch);", "CharWait(ch, resurrection_lag(live_rolls));"],
    ("classes/innates.c", "event_embrace_death"): ["hp_state > embrace_death_first_share()", "hp_state > embrace_death_second_share()", "afp->modifier = embrace_death_first_bonus();", "hp_state > embrace_death_third_share()", "afp->modifier = embrace_death_second_bonus();", "add_event(event_embrace_death, embrace_death_check_interval(),"],
    ("classes/innates.c", "do_innate_embrace_death"): ["hp_state <= embrace_death_third_share() && bonus < embrace_death_third_bonus()", "bonus = embrace_death_third_bonus();", "hp_state <= embrace_death_second_share() && bonus < embrace_death_second_bonus()", "bonus = embrace_death_second_bonus();", "hp_state <= embrace_death_first_share() && bonus < embrace_death_first_bonus()", "bonus = embrace_death_first_bonus();", "hp_state > embrace_death_first_share() && afp"],
    ("classes/innates.c", "do_innate_anti_evil"): ["GET_ALIGNMENT(ch) < anti_evil_alignment()", "af.modifier = anti_evil_hit_points(GET_LEVEL(vict));", "afp->modifier = anti_evil_hit_points(GET_LEVEL(vict));"],
    ("classes/innates.c", "do_innate_decrepify"): ["af.modifier = decrepify_curse(GET_LEVEL(ch));"],
    ("classes/innates.c", "holy_crusade_check"): ["vamp(ch, holy_crusade_healing(GET_LEVEL(victim)), holy_crusade_cap(ch))"],
    ("classes/innates.c", "event_paladin_vit"): ["af->modifier > anti_evil_fade()", "af->modifier -= anti_evil_fade();", "add_event(event_paladin_vit, anti_evil_fade_interval(),"],
    ("classes/innates.c", "get_innate_regeneration"): ["return troll_burned_regeneration();"],
    ("classes/bard.c", "event_echosong"): ["songLevel = echo_song_level(bard_song_level(ch, song));"],
    ("classes/innates.c", "start_hatred_check"): ["int delay = hatred_check_delay();"],
    ("classes/innates.c", "event_hatred_check"): ["af->modifier != hatred_pulse_modifier()", "af.modifier = hatred_pulse_modifier();"],
    ("classes/innates.c", "get_innate_resistance"): ["count = MIN(count, rrakkma_max_steps());", "res += count * rrakkma_step_percent();"],
    ("classes/necromancy.c", "setup_pet"): ["af.duration = unholy_alliance_charm_duration();", "GET_LEVEL(mob) > number(30, 62)"],
    ("classes/psionics.c", "wormhole_decay_timer"): ["decay_timer = improved_wormhole_decay(decay_timer);"],
    ("classes/psionics.c", "wormhole_throughput"): ["specBonus = improved_wormhole_bonus();"],
    ("magic/affects.c", "get_aura_affects"): ["af.modifier = command_aura_hit_dam(GET_LEVEL(ch));", "af.modifier = command_aura_hit_dam(GET_LEVEL(ch));", "af.modifier = command_aura_avenger_regen(GET_LEVEL(ch));", "af.modifier = command_aura_stat_max(GET_LEVEL(ch));", "af.modifier = command_aura_lightbringer_armor(GET_LEVEL(ch));", "af.modifier = command_aura_fear_save(GET_LEVEL(ch));", "af.modifier = command_aura_stat_max(GET_LEVEL(ch));", "af.modifier = command_aura_stat_max(GET_LEVEL(ch));"],
    ("magic/affects.c", "ALL"): ["dual_wielding_master_hitroll(GET_LEVEL(ch))", "hammer_master_damroll(GET_LEVEL(ch))", "weapon_master_hitroll(GET_LEVEL(ch))", "blade_master_damroll(GET_LEVEL(ch))", "GET_C_LUK(ch) = GET_C_LUK(ch) + gamblers_luck_bonus();", "base_combat_round += two_daggers_pulse();"],
    ("cmd/actoff.c", "do_flee"): ["!has_innate(ch, INNATE_IMPROVED_FLEE)", "flee_vitality_cost(live_rolls)", "number(5, 15)", "flee_mount_vitality_cost(live_rolls)"],
    ("cmd/actoff.c", "event_sneaky_strike"): ["has_innate(victim, INNATE_DRAGONMIND) && !dragonmind_roll(live_rolls)"],
    ("cmd/actoff.c", "backstab"): ["has_innate(victim, INNATE_DRAGONMIND) && dragonmind_roll(live_rolls)"],
    ("cmd/actobj.c", "find_chance"): ["has_innate(ch, INNATE_DRAGONMIND) && dragonmind_roll(live_rolls)"],
    ("cmd/actoth.c", "do_steal"): ["percent = percent / dragonmind_steal_divisor();"],
    ("cmd/actoff.c", "do_trample"): ["is_knight = has_innate(ch, INNATE_KNIGHT);", "dam = (int)(dam * trample_knight_multiplier());", "else if (!is_knight)", "!(is_knight && (vict_size == ch_size - 2))", "|| is_knight"],
    ("cmd/actoff.c", "ALL"): ["number(0, 120) <= calming_switch_threshold(GET_LEVEL(victim))", "skl -= calming_switch_penalty(GET_CHAR_SKILL(ch, SKILL_SWITCH_OPPONENTS));"],
    ("world/handler.c", "sun_damage_check"): ["IS_SWAMP_ROOM(ch->in_room) || IS_FOREST_ROOM(ch->in_room)", "int dam = vuln_sun_damage(live_rolls);", "GET_HIT(ch) = MAX(1, GET_HIT(ch) - dam);"],
    ("world/handler.c", "ALL"): ["<= calming_level_gap()) || !calming_gap_roll(live_rolls)", "calming = calming_delay();", "!IS_BLOODLUST && has_innate(i, INNATE_VULN_SUN)"],
    ("cmd/actmove.c", "ALL"): ["<= calming_level_gap()) || !calming_gap_roll(live_rolls)", "calming = calming_delay();"],
    ("mob/mobact.c", "ALL"): ["calming_notarget_roll(live_rolls) <= calming_notarget_percent()", "<= calming_level_gap()) || !calming_gap_roll(live_rolls)", "calming = calming_delay();"],
    ("cmd/interp.c", "ALL"): ["!innate_calming_active(exec_char) || !calming_command_roll(live_rolls)", "calming_chance += calming_chance_bonus();", "(innate_calming_active(exec_char) ? calming_chance_bonus() : 0)", "calming_chance >= number(1, 100)"],
    ("world/limits.c", "hit_regen"): ["regeneration_sleeping_multiple() * get_innate_regeneration(ch)", "regeneration_resting_multiple() * get_innate_regeneration(ch)"],
    ("world/map.c", "map_view_distance"): ["return eyeless_map_range();", "dayblind_infravision_bonus()", "n = dayblind_underdark_range();", "n > forest_map_cap()", "n = forest_map_cap();", "n += perception_map_bonus();"],
    ("cmd/track.c", "show_tracks"): ["skill += perception_track_bonus();", "percent -= farsee_track_bonus();", "percent -= ophidian_track_bonus();", "chance = track_sense_chance(GET_LEVEL(ch));"],
    ("cmd/actinf.c", "ALL"): ["GET_LEVEL(ch) > ophidian_farsee_level()", "GET_LEVEL(ch) > ophidian_invisible_level()"],
    ("core/utility.c", "aggressive_to_at"): ["GET_LEVEL(ch) <= (GET_LEVEL(target) - undead_fealty_gap())"],
    ("core/utility.c", "GET_CHAR_SKILL_P"): ["return two_handed_sword_mastery_rating();"],
    ("core/utility.c", "StatSave"): ["save_num += haste_stat_save_bonus();", "save_num += haste_stat_save_bonus();", "quick_thinking_roll(live_rolls) <= quick_thinking_percent()", "quick_thinking_roll(live_rolls) <= quick_thinking_percent()"],
    ("core/utility.c", "ALL"): ["(GET_LEVEL(area_target) - evasion_remove_chance()) > evasion_snake_roll(live_rolls)", "GET_LEVEL(sub) > ophidian_invisible_level()"],
    ("cmd/actoth.c", "do_quaff"): ["has_innate(ch, INNATE_QUICK_THINKING) || affected_by_spell(ch, SPELL_COMBAT_MIND)", "chance = combat_mind_quaff_chance(chance);"],
    ("net/sparser.c", "perform_chaos_check"): ["controlled = wildmagic_control_roll(live_rolls);", "!wildmagic_health_roll(live_rolls)", "!wildmagic_health_roll(live_rolls)", "GET_HIT(ch) -= wildmagic_health_change(live_rolls, GET_LEVEL(ch));", "GET_HIT(ch) += wildmagic_health_change(live_rolls, GET_LEVEL(ch));", "!wildmagic_bystander_roll(live_rolls)"],
    ("net/sparser.c", "SpellCastTime"): ["dura = (dura * .3);", "dura = (dura * haste_cast_time_share());"],
    ("net/sparser.c", "ALL"): ["!wildmagic_roll(live_rolls) && IS_AGG_SPELL(arg->spell)"],
    ("combat/range.c", "ALL"): ["speed += archery_haste_speed();", "speed += archery_blur_speed();"],
    ("combat/grapple.c", "grapple_check_entrapment"): ["percent = entrapment_chance(GET_LEVEL(attacker), gcskl);", "number(1, 100) < percent", "CharWait(ch, entrapment_lag());"],
    ("magic/smagic.c", "restoration_healing"): ["gain = (int)(gain * restoration_other_share());"],
    ("magic/smagic.c", "wellness_healing"): ["gain += wellness_improved_bonus(ch);"],
    ("magic/smagic.c", "lesser_mending_healing"): ["gain += lesser_mending_improved_bonus(rolls, level);"],
    ("magic/smagic.c", "mending_healing"): ["gain += mending_improved_bonus(rolls, level);"],
    ("magic/smagic.c", "greater_mending_healing"): ["gain += mending_improved_bonus(rolls, level);"],
    ("magic/smagic.c", "spell_greater_mending"): ["level > greater_mending_cure_level()"],
    ("magic/smagic.c", "spell_single_scathing_wind"): ["mod += elemental_power_save_change(level);"],
    ("magic/smagic.c", "earthen_grasp_level"): ["level = (int)(level * elemental_power_area_factor());"],
    ("magic/smagic.c", "spell_single_earthen_rain"): ["dam = (int)(dam * elemental_power_area_factor());"],
    ("magic/magic.c", "spell_stone_skin"): ["has_innate(ch, INNATE_LIVING_STONE)", "absorb = stone_skin_living_stone(absorb);"],
    ("combat/dam_mods.c", "ALL"): ["GET_LEVEL(caster) >= elemental_power_level()", "has_innate(victim, MAGICAL_REDUCTION)", "magical_reduction_mod()", "af.duration = troll_burn_duration();", "af1->duration = troll_burn_duration();", "dam_mod->mod += fire_race_cold_mod(IS_EFREET(victim));", "levelmod = sacrilegious_holy_factor(GET_LEVEL(victim));", "dam_mod->mod += magic_vulnerability_mod();", "NewSaves(victim, SAVING_PARA, vuln_cold_slow_save())", "af.duration = vuln_cold_slow_duration();", "double bonus = warcallers_fury_bonus(group_size, GET_LEVEL(caster));", "count = MIN(count, warcallers_fury_max_steps());", "dam_mod->mod += warcallers_fury_step(count);"],
    ("ships/ship_utils.c", "ALL"): ["speed += seadog_speed_bonus();"],
    ("ships/ship_shop.c", "ALL"): ["static_cast<double>(cost) * seadog_sale_multiplier() > INT_MAX", "cost *= seadog_sale_multiplier();"],
    ("economy/divine_trade_runtime.c", "ALL"): ["has_innate(ch, INNATE_SEADOG) ? seadog_sale_multiplier() : 1.0"],
}

# Literals the conversion must have left nowhere in these handlers.
STALE = (("classes/innates.c", "check_reincarnate", "number(0,8)"), ("classes/drannak.c", "intercept_defensiveproc", "800"),
         ("cmd/actoff.c", "do_flee", "number(20,30)"), ("cmd/actoff.c", "do_flee", "number(30,40)"),
         ("world/handler.c", "sun_damage_check", "number(5,20)"), ("net/sparser.c", "perform_chaos_check", "number(0,2)"),
         ("net/sparser.c", "perform_chaos_check", "number(0,3)"),
         ("specs/specs.object.c", "wall_generic", "number(1,100)>60"), ("combat/grapple.c", "grapple_check_entrapment", "get_property"),
         ("combat/fight.c", "leapSucceed", "BOUNDED"),)

# An innate with a registration but no effect, or none at all, stays on the no-numbers list.
NO_ADD_LINE = "INNATE_BOW_MASTERY INNATE_DAMAGE_SPREAD INNATE_SPEED INNATE_WARDING_FAITH INNATE_ARCANE_RUDIMENTS INNATE_BARTER INNATE_BLOOD_SCENT INNATE_PROT_ACID INNATE_PROT_LIGHTNING INNATE_MINER".split()
NO_EFFECT = "HOLY_COMBAT INNATE_BOW_MASTERY INNATE_DAMAGE_SPREAD INNATE_DAYVISION INNATE_SPEED INNATE_WARDING_FAITH".split()


def in_order(body, calls):
    position = 0
    compact = re.sub(r"\s+", "", body)
    for call in calls:
        position = compact.find(re.sub(r"\s+", "", call), position) + 1
        if not position:
            return call
    return None


def check_sources():
    for (file, head), calls in HANDLER_CALLS.items():
        text = strip_comments(source(file).read_text(errors="replace"))
        if head == "ALL":
            compact = re.sub(r"\s+", "", text)
            for call in calls:
                assert re.sub(r"\s+", "", call) in compact, f"{file} lacks {call}"
            continue
        bodies = function_bodies(text, r"\b" + re.escape(head) + r"\s*\(")
        assert bodies, head
        missing = [in_order(body, calls) for body in bodies]
        assert None in missing, f"{head}: missing or out of order: {missing}"
    for file, head, old in STALE:
        bodies = function_bodies(strip_comments(source(file).read_text(errors="replace")), rf"\b{head}\s*\(")
        assert bodies and all(old not in re.sub(r"\s+", "", body) for body in bodies), f"{head} still has {old}"
    # Every wall a climber can cross rolls through the shared roll.
    wall = strip_comments(source("specs/specs.object.c").read_text(errors="replace"))
    assert len(re.findall(r"wall_climb_roll\(live_rolls\)", wall)) == 8
    table = strip_comments(source("abilities.c").read_text())
    header = source("abilities.h").read_text()
    for constant, name, _ in INNATES:
        assert re.search(rf"case {constant}:\s*return {name}_innate_facts;", table), constant
        assert f"std::string {name}_innate_facts(char_data *ch);" in header, name
    fixtures = ROOT / "tests/fixtures"
    no_numbers = (fixtures / "ability_coverage_no_numbers.txt").read_text().split()
    pending = (fixtures / "ability_coverage_pending.txt").read_text().split()
    converted = {constant for constant, _, _ in INNATES}
    assert len(converted) + len(NO_NUMBERS) == 112
    for constant in NO_NUMBERS:
        assert constant in no_numbers and constant not in pending, constant
        assert not re.search(rf"case {constant}:", table), constant
    for constant in converted:
        assert constant not in no_numbers and constant not in pending, constant
    innates = strip_comments(source("classes/innates.c").read_text())
    for constant in NO_ADD_LINE:
        assert not re.search(rf"ADD_(?:RACIAL|CLASS)_INNATE\({constant}\b", innates), constant
    everything = "".join(path.read_text(errors="replace") for path in (ROOT / "src").rglob("*.[ch]"))
    everything = strip_comments(everything)
    for constant in NO_EFFECT:
        uses = re.findall(rf"\b{constant}\b(?!\s+\d)", everything)
        adds = re.findall(rf"ADD_(?:RACIAL|CLASS)_INNATE\({constant}\b", everything)
        assert len(uses) == len(adds), f"{constant} now has an effect: reclassify it"
    # Battlefield aid's only reads are behind a dead return and an unregistered command.
    assert 'send_to_char("Try using the bandage instead.", ch);\n\treturn;' in source("classes/new_skills.c").read_text(errors="replace")
    assert "do_OLD_bandage" not in source("cmd/interp.c").read_text(errors="replace")


GOLDEN = """== blindsinging
  Instrument rating to play one you cannot see: 70
== echo
  Chance of an echo each song beat: 20 in 100
  In the mountains: 30 in 100
  In the hills: 25 in 100
  In a forest: 15 in 100
  It sounds after: 1.25 seconds
  The echo's song level, from a song level of 100: 50
  At least 1. It plays in the room you sang in. Not underwater, and not
  while another echo is waiting.
== intercept
  Your luck roll against each attack: 1-100
  The attack's roll: 1-800
  At least as high stops an attack aimed at you, if you are standing.
  If it works, attacker's attacks: 50% of normal
  For: 25 seconds
  An attacker it is already holding cannot be intercepted again.
== diseased_bite
  Chance of disease on each parasite bite: 1 in 8
  It casts your disease spell on the target at your level:
  Disease spell page
== hatred
  Mountain Dwarf hated races: Orc, Duergar, Drow Elf
  Your combat pulse while you see one: -1
  Your spell pulse while you see one: -1
  It looks every: 1 second
  It needs one in your room that you can see, and ends when none is.
== holy_crusade
  Your healing when you kill an evil being: 2 per level of the victim
  Up to: 330 hit points
  Plague, blackmantle and flamestrike can block some of it.
== leap
  Thri-kreen or harpy: chance to avoid an attacker of your level: 13 in 100
  Lowest and highest chance: 1 in 100, 20 in 100
  It compares your agility, your load, and your level with the attacker's.
  It needs you standing and not gazed at. These races have it at any level.
== rapier_dirk
  With a sword and a dagger or short sword, damage you deal: 110% of normal
  Damage you take: 90% of normal
  Chance a parry becomes a counter: 155 in 1000
  Hits in a counter: 2, or 1 plus 1-2 on a 1 in 4
  The chance comes from your agility, wisdom and level. It needs you standing
  and your opponent as the attacker, and it never works on a dragon.
== resurrection
  Chance when you die: 1 in 9
  Hit points you come back with: 100
  Your lag: 2 seconds to 4 seconds
  The fight ends for you and for those fighting you.
== two_daggers
  With a dagger in each hand, your combat pulse: -3
  Chance to counter an attack with both daggers: 1 in 20
  The counter comes before any riposte skill check.
== unholy_alliance
  Duration of a new pet's charm: permanent
  A new pet also never remembers you as an enemy.
== improved_wormhole
  Your wormholes last up to: 45 seconds
  Added to the top of the roll for how many can pass: +3
  Range to an NPC: 75 rooms
  A wormhole can reach an NPC, unless it cannot be summoned.
== ophidian_eyes
  You see heat, as infravision does.
  Farsee above level: 40
  Sees invisible above level: 45
  Dragon priest: you see illusions and magic.
  Dragon lancer: you see good and evil.
  Dragon hunter: you sense life and traces beyond the veil.
  Dragon hunter: chance to sense a trace: 29 in 100
  Dragon hunter: improved tracking roll: 5 easier
== dragonmind
  Chance to dodge a sneaky strike: 1 in 2
  Chance to foil a backstab: 1 in 2
  Chance to find what you search for at once: 1 in 2
  A thief's chance to steal from you: divided by 2
== improved_flee
  Vitality you lose when you flee: none
  Without this innate, a non-rogue player loses: 20-30
  A mount you ride loses: 30-40
== knight
  Your trample damage: 250% of normal
  One size below a target, your knockdown chance is not halved.
  Two sizes above one, your chances are not cut.
  A mount that bucks never throws you.
== calming
  Extra wait before an aggressive mob attacks: 2.5 seconds
  Innate Calming is disabled in enemy hometowns.
  Elites ignore the extra wait. A mob over 5 levels above you waits
  only 1 in 4 times.
  Chance a mob picking a target passes you over: 76 in 102
  Your commands that draw an aggression check: 1 in 20
  Chance an aggressive mob then leaves you be: 24 in 100
  That chance is +10 on what your charisma gives.
  Chance a foe switching to you is hindered: 113 in 121
  It costs that foe 110 minus its switch rating.
== sacrilegious_power
  Holy spell damage you take from level 46: 75% of normal
  Holy spell damage you take from level 51: 50% of normal
  Holy spell damage you take from level 56: 25% of normal
  At your level: 25% of normal
  Only if you are of an undead race. Other holy modifiers add to it.
== vuln_cold
  Cold spell damage you take, of its base: +35%
  It adds to the other modifiers of that kind before multipliers apply.
  You are slowed if you fail a paralysis save, 2 harder: 15 seconds
== vuln_fire
  Fire spell damage you take: +30%
  With a fire shield, added to that: -10%
  Or with protection from fire: -10%
  Other fire modifiers add to these.
  A troll's regeneration also falls to 1 for 30 seconds after each one.
== warcallers_fury
  Damage you deal to a lone target: +5% at your level
  Most for a target's group: +15%
  Each player in the target's group here adds 1%.
  Each other holder grouped with you here: +3.3%
  Holders counted, at most: 3
== magical_reduction
  Generic spell damage you take: -20%
  Only damage with no element counts, multiplied with other modifiers.
== magic_vulnerability
  Ogre or firbolg: spell damage you take, of its base: +10%
  It adds to the other modifiers of that kind before multipliers apply.
== acid_blood
  Chance when a hit wounds you: 1 in 10
  The hit must deal over 5, or over 9 if it is a touch.
  Acid damage to the attacker: 41-80
  The attacker's agility can dodge it: 15 plus agility/6, in 101.
  It cannot be shrugged or deflected; spell damage modifiers apply.
== battle_frenzy
  Chance on each hit at a humanoid: 1 in 21
  Extra blow's damage, from your damroll and level: 28-56
  It needs a to-hit roll with your unarmed damage rating, against the
  target's armor; the target's melee defenses apply.
== decrepify
  Your opponent's saves: worse by 5 at your level, 56
  It holds while you fight that opponent.
== embrace_death
  Your maximum strength at 75% hit points or below: +5
  Your maximum strength at 45% hit points or below: +10
  Your maximum strength at 25% hit points or below: +15
  It starts when you are hurt and ends once you are above the first share.
  Healing lowers it at the next check, every 2 seconds.
== fpresence
  Attacker at or below your level flees: 16 in 101 to 25 in 101
  Attacker above your level flees: 15 in 101
  Each round, from an attacker you are not fighting. Elites, guardians,
  dreadlords, the fearless, the indomitable and level 51+ greater races
  resist it, and so can a berserker with indomitable rage.
== giant_avoidance
  Dodge score against a troll, ogre or giant: 110% of normal
  It applies before your dodge limits and the level and stat comparisons.
== groundfighting
  Your dodge chance when not standing: 50% of normal
  Others cannot dodge at all when down.
  Being down does not cost you attacks or add to the melee damage you take.
== guardians_bulwark
  Melee damage you take with a shield worn: 85% of normal
  Hits that ignore reductions go through it.
== melee_master
  Damage of your melee hits: 110% of normal
== mummify
  A corpse you kill is embalmed at level 62: 124 more game hours
== requiem
  A corpse you kill is embalmed at level 62: 124 more game hours
== rrakkma
  Your armor class per other holder grouped in the room: -10
  Your magic resistance per other holder: +5, for up to 5 of them
  They must be players in your group.
== spell_absorb
  Chance to regain a spell slot: 28 in 100 at your level, 56
  First the spell's damage/50 must beat a 0-9 roll, so bigger spells pass
  more often. An absorbed spell refills your highest spent circle.
  Only for spell slot users; not unshruggable spells or your own.
== troll_skin
  Melee damage you take: 85% of normal
  Hits that ignore reductions go through it.
== weapon_immunity
  A non-magic weapon's blow on you: 1
  An unarmed blow on you, below level 51 without magic gloves: 1
  A non-magic arrow does nothing, and a thrown non-magic weapon deals 1.
== entrapment
  Chance to stop your opponent fleeing: 37 in 100 at your level
  It comes from your level and grappler combat rating.
  Your opponent's lag if it works: 4 seconds
  You must be standing, able to act and see it. Immaterial foes get away.
== blur
  Your attacks each round: +1
  Archery speed: +20
  It is permanent; temporary blur ending cannot remove it.
== evasion
  Way of the dragon: chance to avoid spell damage: 14 in 100
  Way of the snake: chance to avoid an area spell: 40 in 100
== quick_thinking
  Chance an intelligence or power save passes at once: 15 in 100
  A saving throw you fail is rolled once more.
  Your chance not to spill a potion in combat: 125% of normal
== undead_fealty
  Undead that will not attack you first: 10 or more levels below you
== two_handed_sword_mastery
  Two-handed slashing rating: 100
== seadog
  Top speed of a ship at your helm: +2
  What you get for selling cargo: 110% of normal
  It does not add to contraband sales.
== command_aura
  As group leader, you and members in your room get these, by your level.
  Hitroll: +4
  Damroll: +4
  Avenger: hit point regeneration: +28
  Inquisitor: maximum constitution: +5
  Lightbringer: armor class: -56
  Dreadlord: fear saves, lower is better: -5
  Deathlord: maximum strength: +5
  Shadowlord: maximum agility: +5
== anti_evil
  Alignment needed for the halo: 900
  Your hit points while you hit evil: +2 per level of your target
  They fade 2 every 2 seconds once your opponent is not evil.
  You also stay aware, and you detect good and evil.
== axe_master
  Your hitroll with an axe as your main weapon: +7 at your level, 56
  Your damroll with one: +4
== dual_wielding_master
  Your hitroll with a weapon in each main hand: +11 at your level, 56
== dayblind
  In a lit room you see only red shapes by infravision, and nothing without
  it, unless someone there has a globe of darkness.
  Your map sight in the sun at this hour: 0
  With infravision or ophidian eyes: +2
  Your map sight underground: 8
== eyeless
  Your map sight range, whatever the light: 8
  You cannot be blinded, dazzled or gazed at.
== farsee
  You can look into the next rooms, unless a closed door blocks the view.
  Your improved tracking roll, if you have that skill: 10 easier
== fire_aura
  Fire elemental: cold spell damage you take: +35%
  Efreet: cold spell damage you take: +1%
  Fire spells absorbed heal: 25% of their damage
  Up to: 330 hit points
  A fire elemental absorbs them always, others under a fire shield.
== gamblers_luck
  Your luck: +10
== hammer_master
  Your hitroll with a hammer as your main weapon: +7 at your level, 56
  Your damroll with one: +5
== haste
  Your attacks each round: +1, none while slowed
  Time between your song beats: 6.25 seconds
  Your spell casting time: 80% of normal
  Your dexterity saves: +2
  Your agility saves, not for monks: +2
  Archery speed: +20
== ice_aura
  Fire spell damage you take: +30%
  Under a cold shield, cold spells absorbed heal: 25% of their damage
  Up to: 330 hit points
== infernal_fury
  Negative damage back on each melee hit: 90% of the hit
  A greater spirit ward stops it, but shrugs and deflections do not.
  It takes the place of a fire, cold or lightning shield's damage.
== longsword_master
  Your hitroll with a longsword as your main weapon: +7 at your level, 56
  Your damroll with one: +4
== perception
  Your map sight range: +1
  Your improved tracking rating, if you have that skill: +30
== prot_cold
  Cold spell damage you take: -15%
  A cold shield's reduction replaces it, and other cold modifiers add to it.
  Damage from a wall of ice: 67% of normal
== prot_fire
  Fire spell damage you take: -15%
  A fire shield's reduction replaces it, and vulnerability to fire changes
  it; other fire modifiers add to it.
  A wall of flames' burn: 33% of normal
== regeneration
  Hit point regeneration here: +56 awake, +112 resting, +168 sleeping
  It uses your level, race, class and this room.
  In combat all your regeneration is halved, unless a spell gives it too.
== vampiric_touch
  Healing from your melee touch: 10% of the damage, for your class
  From an arrow hit of 4 or more: 5% of the damage
  Your hit points stop at: 111% of your maximum
  That comes from your power. A construct target or one with a negative
  energy barrier gives none. Touch healing stops in vampire form, and
  arrow healing under battle ecstasy.
== living_stone
  Stone skin you cast absorbs: 22-27 hits at your level, 56
  That replaces the bonus from your class.
== elemental_power
  Your elemental spell damage from level 35: +25%
  It counts fire, cold, lightning, gas, acid and earth damage.
  A target's save against your scathing wind: 5 harder at your level, 56
  Your earthen rain's damage: 115% of normal
  Your earthen grasp's damage level: 115% of your level
== improved_heal
  Healing your restoration gives: full; 66% of that without this innate
  Healing your wellness gives each person: +56
  Healing your lesser mending gives: +28-84 at your level, 56
  Healing your other mendings give: +28-56 at your level, 56
  Greater mending cures disease above level: 46
== magic_resistance
  Your chance to shrug a spell: 40 in 101
  In desecrated land: 30 in 101
  It comes from your race and level, and is never below 5.
  Spell penetration can burst through it, and a god's spell ignores it.
== wildmagic
  Chance on each aggressive spell at one target: 1 in 6
  It adds a random spell on your target, and your spell can hit others.
  Chance each other being here is hit: 1 in 7
  Chance you lose control, which can hit your group: 1 in 3
  A roll against your luck can stop it there.
  Chance your health changes: 1 in 4
  By: 15-19 hit points at your level, 56
  It heals you, or 1 in 4 times drains you.
== wall_climbing
  Chance to get over a wall: 40%
  It works on walls of ice, force, iron, stone and bones, and on prismatic
  walls, life wards and watching walls. Ice and a life ward still hurt.
== vuln_sun
  Burn in direct sun: 5-20 hit points every 20 seconds
  It never takes you below 1, and spares you at twilight, in a swamp or
  forest, on Bloodlust day and under a globe of darkness.
  In direct sun, outside a globe, you regain no mana, and no hit points
  unless the room is magically dark.
== elemental_body
  Hit point regeneration here: +56 awake, +112 resting, +168 sleeping
  It uses your level, race, class and this room.
  Per level for this terrain: +3
  Combat stops it.
== woodland_renewal
  Hit point regeneration here: +56 awake, +112 resting, +168 sleeping
  It uses your level, race, class and this room.
  It only works in a forest, where combat halves your regeneration
  instead of stopping it.
  A huntsman's regeneration per level in a forest: +3
== forest_sight
  Forests do not cut your map sight.
  Others see this far in one: 3
"""


def main():
    check_sources()
    output = build(CHECKS)
    if "--print" in __import__("sys").argv:
        print(output)
        return
    assert output == GOLDEN, "pages differ:\n" + "\n".join(
        line for line in __import__("difflib").unified_diff(GOLDEN.splitlines(), output.splitlines(), lineterm="", n=1))
    print(f"PASS: {len(INNATES)} innates converted, {len(NO_NUMBERS)} with no numbers")


if __name__ == "__main__":
    main()
