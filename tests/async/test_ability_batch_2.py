#!/usr/bin/env python3
"""Spell batch 2: shared numbers match the old handler code, ranges are exact, facts never roll.

Builds the batch's shared and facts functions, extracted from magic.c, with
src/abilities/abilities.c and the real RNG under sanitizers. The pre-conversion
expressions are kept below as the oracle, and each handler must call its shared functions.
"""
import re
import subprocess
import tempfile
from pathlib import Path

from _paths import ROOT, extract_function, source
from _source_contract import function_bodies, strip_comments

# The functions this batch added to magic.c; they are extracted in file order.
SHARED = """
cure_serious_healing cure_serious_facts cure_critic_healing cure_critic_facts cure_light_healing
cure_light_facts curse_duration curse_hitroll curse_saves curse_facts nether_touch_duration
nether_touch_hitroll nether_touch_saves nether_touch_paralysis_save nether_touch_facts
detect_evil_duration detect_evil_facts detect_good_duration detect_good_facts
detect_magic_duration detect_magic_facts detect_invisibility_duration detect_invisibility_facts
unmaking_corpse_healing unmaking_level_healing unmaking_facts enchant_weapon_hitroll
enchant_weapon_damroll enchant_weapon_added_hitroll enchant_weapon_facts heal_cap_shortfall
full_heal_healing full_heal_anatomy_bonus full_heal_facts heal_healing heal_anatomy_bonus
heal_facts natures_touch_healing natures_touch_facts water_to_life_healing water_to_life_facts
healing_salve_wave_healing healing_salve_interval healing_salve_waves healing_salve_facts
sticks_to_snakes_bite sticks_to_snakes_count sticks_to_snakes_cap sticks_to_snakes_facts
shadow_projection_duration
shadow_projection_facts concealment_duration concealment_facts invisibility_duration
invisibility_facts disease_power disease_duration disease_stat_penalty disease_recast_duration
disease_facts major_paralysis_duration major_paralysis_facts minor_paralysis_duration
minor_paralysis_facts slow_duration slow_facts stornogs_lowered_res_duration
stornogs_lowered_res_save stornogs_lowered_res_facts protection_from_evil_duration
protection_from_evil_facts protection_from_good_duration protection_from_good_facts
group_stone_skin_level group_haste_level stone_skin_absorb stone_skin_living_stone
stone_skin_conjurer stone_skin_sorcerer stone_skin_other stone_skin_duration stone_skin_layers
stone_skin_facts_at stone_skin_facts group_stone_skin_facts ironwood_absorb ironwood_duration
ironwood_facts sleep_duration sleep_facts dexterity_duration dexterity_bonus dexterity_facts
agility_duration agility_bonus agility_facts strength_duration strength_bonus strength_facts
word_of_recall_weight_limit word_of_recall_fight_roll word_of_recall_facts group_recall_facts
summon_range summon_lag summon_max_level summon_shadow_roll summon_facts sense_life_duration sense_life_facts blur_duration blur_facts
lodestone_vision_duration lodestone_vision_facts haste_duration haste_facts group_haste_facts
recharger_mana_gained recharger_facts vigorize_serious_level vigorize_light_level
invigorate_movement invigorate_facts_at invigorate_facts vigorize_serious_facts
vigorize_light_facts devitalize_movement devitalize_floor devitalize_facts
divine_warding_duration divine_warding_facts death_blessing_leader_level
death_blessing_member_level vitality_hit_points vitality_duration vitality_facts miracle_facts
mass_invisibility_facts mass_barkskin_facts
vital_intercession_healing vital_intercession_pool vital_intercession_duration
vital_intercession_facts_at vital_intercession_facts holy_intercession_level
holy_intercession_facts vitalize_undead_hit_points vitalize_undead_duration
vitalize_undead_facts death_blessing_facts farsee_duration farsee_facts globe_duration
globe_refresh_duration globe_facts group_globe_facts minor_globe_duration minor_globe_facts deflect_duration
deflect_facts earth_form_duration earth_form_facts fire_form_duration fire_form_armor_class
fire_form_strength fire_form_dexterity fire_form_agility fire_form_constitution fire_form_facts
water_form_duration water_form_strength water_form_dexterity water_form_agility
water_form_constitution water_form_facts air_form_duration air_form_facts
plague_creature_duration plague_player_duration plague_creature_block plague_player_block
plague_facts identify_warded_level identify_facts continual_light_duration continual_light_facts airy_water_duration
airy_water_facts levitate_duration levitate_facts fly_duration fly_facts barkskin_armor_class
barkskin_duration barkskin_facts grow_spike_damage grow_spike_saved grow_spike_terrain
grow_spike_facts
""".split()

# Each handler's calls to its shared numbers, whitespace-insensitive.
CALLS = {
    "spell_cure_serious": ["healpoints = cure_serious_healing(live_rolls);"],
    "spell_mass_invisibility": ["spell_invisibility(level, ch, 0, 0, victim, 0);"],
    "spell_mass_barkskin": ["if (ch->specials.z_cord == victim->specials.z_cord)",
                            "spell_barkskin(level, ch, NULL, SPELL_TYPE_SPELL, victim, 0);"],
    "spell_cure_critic": ["healpoints = cure_critic_healing(live_rolls);"],
    "spell_cure_light": ["healpoints = cure_light_healing(live_rolls);"],
    "spell_curse": ["af.duration = curse_duration(ch);",
                    "af.modifier = curse_hitroll(IS_NPC(victim));", "af.modifier = curse_saves();"],
    "spell_nether_touch": ["af.duration = nether_touch_duration();",
                           "af.modifier = nether_touch_hitroll();", "af.modifier = nether_touch_saves();",
                           "af.modifier = nether_touch_paralysis_save();"],
    **{f"spell_detect_{name}": [f"af.duration = detect_{name}_duration(ch, level);",
                                f"af1->duration = detect_{name}_duration(ch, level);"]
       for name in ("evil", "good", "magic")},
    "spell_detect_invisibility": ["af.duration = detect_invisibility_duration(level);",
                                  "af1->duration = detect_invisibility_duration(level);"],
    "spell_unmaking": ["MIN(GET_MAX_HIT(ch), GET_HIT(ch) + unmaking_corpse_healing(clevel) + "
                       "unmaking_level_healing(level));"],
    "spell_enchant_weapon": ["obj->affected[i].modifier = enchant_weapon_added_hitroll(level);",
                             "obj->affected[0].modifier = enchant_weapon_hitroll(level);",
                             "obj->affected[1].modifier = enchant_weapon_damroll(level);"],
    "spell_full_heal": ["int healpoints = full_heal_healing(live_rolls, ch, level);",
                        "healpoints += full_heal_anatomy_bonus(live_rolls, ch);",
                        "heal(victim, ch, healpoints, GET_MAX_HIT(victim) - heal_cap_shortfall(live_rolls));"],
    "spell_heal": ["healpoints = heal_healing(live_rolls, ch, level);",
                   "healpoints += heal_anatomy_bonus(live_rolls, ch);",
                   "heal(victim, ch, healpoints, GET_MAX_HIT(victim) - heal_cap_shortfall(live_rolls));"],
    "spell_natures_touch": ["healpoints = natures_touch_healing(ch, level);"],
    "spell_water_to_life": ["healpoints = water_to_life_healing(level);"],
    "event_healing_salve": ["heal(vict, ch, healing_salve_wave_healing(live_rolls, vict), GET_MAX_HIT(vict));",
                            "add_event(event_healing_salve, healing_salve_interval(), ch, vict,"],
    "spell_healing_salve": ["int waves = healing_salve_waves(level);"],
    "spell_sticks_to_snakes": ["snakes = sticks_to_snakes_count(live_rolls, world[ch->in_room].sector_type);",
                               "if (++arrowSnakes >= sticks_to_snakes_cap() - snakes)",
                               "spell_damage(ch, victim, sticks_to_snakes_bite(live_rolls, level),"],
    "spell_shadow_projection": ["af.duration = shadow_projection_duration();"],
    **{f"spell_{name}": [f"af.duration = {name}_duration(level);", f"af1->duration = {name}_duration(level);"]
       for name in ("concealment", "invisibility", "sense_life", "farsee", "levitate", "fly")},
    "spell_disease": ["temp = disease_power(level);", "af.duration = disease_duration(temp);",
                      "af.modifier = disease_stat_penalty(temp);",
                      "af1->duration = disease_recast_duration(level);"],
    "spell_major_paralysis": ["af.duration = major_paralysis_duration();"],
    "spell_minor_paralysis": ["af.duration = minor_paralysis_duration(level);"],
    "spell_slow": ["af.duration = slow_duration(level);"],
    "spell_stornogs_lowered_magical_res": ["af.duration = stornogs_lowered_res_duration(level);",
                                           "af.modifier = stornogs_lowered_res_save(level);"],
    **{f"spell_protection_from_{name}": [
        f"af.duration = protection_from_{name}_duration(level);",
        f"set_protection_duration(victim, SPELL_PROTECT_FROM_{name.upper()}, "
        f"protection_from_{name}_duration(level), false);"] for name in ("evil", "good")},
    "spell_group_stone_skin": ["spell_stone_skin(group_stone_skin_level(level), ch, 0, 0, gl->ch, 0);"],
    "spell_group_haste": ["spell_haste(group_haste_level(level), ch, 0, 0, gl->ch, 0);"],
    "spell_stone_skin": ["int absorb = stone_skin_absorb(live_rolls, level);",
                         "layers < stone_skin_layers()", "absorb = stone_skin_living_stone(absorb);",
                         "absorb = stone_skin_conjurer(absorb);", "absorb = stone_skin_sorcerer(absorb);",
                         "absorb = stone_skin_other(absorb);", "af.duration = stone_skin_duration();"],
    "spell_ironwood": ["int absorb = ironwood_absorb(live_rolls, level, IS_AFFECTED(victim, AFF_BARKSKIN));",
                       "af.duration = ironwood_duration();"],
    "spell_sleep": ["af.duration = sleep_duration(level);"],
    **{f"spell_{name}": [f"af.duration = {name}_duration(level);", f"af.modifier = {name}_bonus();"]
       for name in ("strength", "dexterity", "agility")},
    "spell_word_of_recall": ["if (IS_PC(victim) && IS_PC(GET_OPPONENT(victim)) && "
                             "!word_of_recall_fight_roll(live_rolls))",
                             "if (total_carried_weight(victim) > word_of_recall_weight_limit(victim))"],
    "spell_group_recall": ["spell_word_of_recall(level, ch, 0, 0, gl->ch, 0);"],
    "spell_summon": ["if (IS_PC(ch) && !IS_ROOM(ch->in_room, ROOM_NO_SUMMON) && !summon_shadow_roll(live_rolls))",
                     "distance = summon_range(level);", "CharWait(ch, summon_lag(ch));",
                     "max_summon_level = summon_max_level(level);", "(GET_LEVEL(victim) > max_summon_level)"],
    "spell_blur": ["af.duration = blur_duration();", "af1->duration = blur_duration();"],
    "spell_lodestone_vision": ["af.duration = lodestone_vision_duration(live_rolls);"],
    "spell_haste": ["af.duration = haste_duration(ch, level);"],
    "spell_recharger": ["ch->points.mana += recharger_mana_gained(live_rolls, ch, m_points);"],
    "spell_vigorize_critic": ["spell_invigorate(level, ch, 0, SPELL_TYPE_SPELL, victim, 0);"],
    "spell_vigorize_serious": ["spell_invigorate(vigorize_serious_level(level), ch, 0, SPELL_TYPE_SPELL,"],
    "spell_vigorize_light": ["spell_invigorate(vigorize_light_level(level), ch, 0, SPELL_TYPE_SPELL,"],
    "spell_invigorate": ["movepoints = invigorate_movement(live_rolls, ch, level);"],
    "spell_devitalize": ["movepoints = devitalize_movement(live_rolls, level);",
                         "if ((GET_VITALITY(victim) - movepoints) < devitalize_floor())",
                         "GET_VITALITY(victim) = devitalize_floor();"],
    "spell_divine_warding": ["set_protection_duration(victim, spell, divine_warding_duration(), true);"],
    "spell_miracle": ["spell_vitality(level, ch, NULL, 0, gl->ch, 0);"],
    "spell_death_blessing": ["spell_vitalize_undead(death_blessing_leader_level(), ch, NULL, 0, gl->ch, 0);",
                             "spell_vitalize_undead(death_blessing_member_level(), ch, NULL, 0, gl->ch, 0);"],
    "spell_vitality": ["int healpoints = vitality_hit_points(level), duration = 1;",
                       "duration = vitality_duration(ch, victim);"],
    "vital_intercession_heal": ["int healpoints = vital_intercession_healing(live_rolls, dam);"],
    "vital_intercession": ["int maximumHitsHealed = vital_intercession_pool(live_rolls, level);",
                           "af.duration = vital_intercession_duration();",
                           "af1->duration = vital_intercession_duration();"],
    "spell_vital_intercession": ["vital_intercession(level, ch, victim, SPELL_VITAL_INTERCESSION);"],
    "spell_holy_intercession": [
        "vital_intercession(holy_intercession_level(level), ch, gl->ch, SPELL_HOLY_INTERCESSION);",
        "vital_intercession(holy_intercession_level(level), ch, ch, SPELL_HOLY_INTERCESSION);"],
    "spell_vitalize_undead": ["int healpoints = vitalize_undead_hit_points(level);",
                              "af.duration = vitalize_undead_duration(ch);",
                              "af1->duration = vitalize_undead_duration(ch);"],
    "spell_group_globe": ["spell_globe((level / 3) * 2, ch, 0, 0, gl->ch, 0);"],
    "spell_globe": ["af.duration = globe_duration(ch);", "af1->duration = globe_refresh_duration();"],
    "spell_minor_globe": ["af.duration = minor_globe_duration();", "af1->duration = minor_globe_duration();"],
    "spell_deflect": ["af.duration = deflect_duration();"],
    "spell_earth_form": ["af.duration = earth_form_duration();"],
    "spell_air_form": ["af.duration = air_form_duration();"],
    "spell_fire_form": ["af.duration = fire_form_duration();", "af.modifier = fire_form_armor_class();",
                        "af.modifier = fire_form_strength();", "af.modifier = fire_form_dexterity();",
                        "af.modifier = fire_form_agility();", "af.modifier = fire_form_constitution();"],
    "spell_water_form": ["af.duration = water_form_duration();", "af.modifier = water_form_strength();",
                         "af.modifier = water_form_dexterity();", "af.modifier = water_form_agility();",
                         "af.modifier = water_form_constitution();"],
    "spell_identify": ["if (level < identify_warded_level())"],
    "spell_plague": ["af.duration = plague_creature_duration(level);", "af.modifier = plague_creature_block();",
                     "af.duration = plague_player_duration();", "af.modifier = plague_player_block();"],
    "spell_continual_light": ["add_event(cont_light_dissipate_event, continual_light_duration(level),"],
    "spell_airy_water": ["add_event(event_airy_water_dissipate, airy_water_duration(level),"],
    "spell_barkskin": ["af1.modifier = barkskin_armor_class(ch, level);", "af1.duration = barkskin_duration();",
                       "af1->duration = barkskin_duration();"],
    "spell_grow_spike": ["dam = grow_spike_damage(live_rolls, level);", "dam = grow_spike_saved(dam);",
                         "dam = grow_spike_terrain(dam, dam_flag);"],
}

HARNESS = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "magic/spells.h"
#include "abilities/abilities.h"
#include <cassert>
#include <climits>
#include <cstdlib>
#include <functional>
#include <iterator>
#include <sstream>
#include <string>
#include <vector>

void randomize(uint64_t seed);
struct str_app_type str_app[52];

// The services the extracted functions read.
static int anatomy = 0;
int GET_CHAR_SKILL_P(P_char, int skill) { return skill == SKILL_ANATOMY ? anatomy : 0; }
float get_property(const char *, double fallback) { return fallback; }
int get_property(const char *, int fallback) { return fallback; }

// The next draw after a roll; equal fingerprints after equal seeds mean equal draw counts.
static int fingerprint() { return number(0, INT_MAX); }

static void same_rolls(const std::function<int()> &original, const std::function<int()> &shared,
                       Range bounds) {
    for (uint64_t seed = 1; seed <= 40; ++seed) {
        randomize(seed);
        const int expected = original(), expected_next = fingerprint();
        randomize(seed);
        const int actual = shared(), actual_next = fingerprint();
        assert(actual == expected && actual_next == expected_next);
        assert(bounds.low <= actual && actual <= bounds.high);
    }
}

#define BOUNDS(call) Range{ call(lowest_rolls), call(highest_rolls) }

// The handlers' code before it moved into shared functions.
static int old_full_heal(P_char ch, int level) {
    int num_dice = 1;
    if (level >= 36) num_dice += 2;
    if (level >= 41) num_dice += 2;
    if (level >= 46) num_dice += 2;
    if (level >= 51) num_dice += 2;
    if (GET_SPEC(ch, CLASS_CLERIC, SPEC_HEALER)) {
        if (level >= 52) num_dice += 1;
        if (level >= 53) num_dice += 1;
        if (level >= 54) num_dice += 1;
        if (level >= 55) num_dice += 1;
        if (level >= 56) num_dice += 1;
    }
    return 250 + dice(num_dice, 20);
}

static int old_heal(P_char ch, int level) {
    int num_dice = 1;
    if (GET_SPEC(ch, CLASS_CLERIC, SPEC_HEALER)) {
        if (level >= 33) num_dice += 1;
        if (level >= 39) num_dice += 1;
        if (level >= 43) num_dice += 1;
        if (level >= 51) num_dice += 1;
        if (level >= 56) num_dice += 1;
    } else {
        if (level >= 26) num_dice += 1;
        if (level >= 31) num_dice += 1;
        if (level >= 36) num_dice += 1;
        if (level >= 41) num_dice += 1;
    }
    return 100 + dice(num_dice, 5);
}

static int old_snake_bite(int level) {
    int num_dice, num_sides;
    if (level > 50) { num_dice = 8; num_sides = 8; }
    else if (level > 40) { num_dice = 8; num_sides = 7; }
    else if (level > 30) { num_dice = 7; num_sides = 7; }
    else if (level > 25) { num_dice = 7; num_sides = 6; }
    else if (level > 20) { num_dice = 6; num_sides = 6; }
    else if (level > 15) { num_dice = 6; num_sides = 5; }
    else { num_dice = 5; num_sides = 5; }
    return dice(num_dice, num_sides);
}

static int old_snake_count(int sector) {
    switch (sector) {
    case SECT_CITY: case SECT_ROAD: return number(1, 2);
    case SECT_FIELD: return number(1, 5);
    case SECT_FOREST: return number(1, 6);
    case SECT_HILLS: return number(1, 4);
    case SECT_UNDERWATER_GR: case SECT_MOUNTAIN: return number(1, 3);
    case SECT_UNDRWLD_WILD: case SECT_UNDRWLD_CITY: case SECT_UNDRWLD_MOUNTAIN:
    case SECT_UNDRWLD_SLIME: case SECT_UNDRWLD_LOWCEIL: case SECT_UNDRWLD_LIQMITH:
    case SECT_UNDRWLD_MUSHROOM: return number(1, 2);
    default: return 1;
    }
}

static int old_invigorate(P_char ch, int level) {
    int movepoints = dice(3, level);
    if (GET_CLASS(ch, CLASS_CLERIC)) movepoints = (int)(movepoints * 1.5);
    else if (GET_CLASS(ch, CLASS_RANGER)) movepoints = (int)(movepoints * 1.15);
    else if (GET_CLASS(ch, CLASS_PALADIN | CLASS_ANTIPALADIN)) movepoints = (int)(movepoints * .95);
    else movepoints = (int)(movepoints * 0.80);
    return movepoints;
}

static int old_grow_spike(int level) {
    int temp = MIN(20, (level / 2 + 1));
    int dam = dice(6 * temp, 6);
    if (level > 50) dam = dice(6 * temp, 7);
    return dam;
}

static int old_natures_touch(P_char ch, int level) {
    int healpoints = (level / 2) + 22;
    if (!GET_CLASS(ch, CLASS_DRUID)) {
        if (!GET_CLASS(ch, CLASS_RANGER)) healpoints /= 4;
        else healpoints /= 2;
    }
    if (healpoints < 8) healpoints = 8;
    return healpoints;
}

static int old_sleep(int level) {
    int duration = 4 + (level < 0 ? -level : level);
    duration /= 10;
    if (duration > 1) duration--;
    else duration = 1;
    return duration;
}

static int old_haste(P_char ch, int level) {
    if (GET_SPEC(ch, CLASS_CONJURER, SPEC_AIR)) return (int)(level / 2);
    if (GET_CLASS(ch, CLASS_RANGER) || GET_CLASS(ch, CLASS_REAVER) ||
        GET_CLASS(ch, CLASS_CONJURER) || GET_CLASS(ch, CLASS_SORCERER)) return 15;
    return 10;
}

static int old_globe(P_char ch) {
    if (GET_CLASS(ch, CLASS_CONJURER)) return 15;
    if (GET_CLASS(ch, CLASS_SUMMONER)) return 12;
    return 8;
}

static int old_barkskin(P_char ch, int level) {
    double mod = GET_SPEC(ch, CLASS_DRUID, SPEC_WOODLAND) ? 1.25 : 1;
    return (int)(-1 * mod * level);
}

static bool contains(const std::string &text, const char *part) {
    return text.find(part) != std::string::npos;
}

static void set_class(char_data &ch, uint m_class, int spec) {
    ch.player.m_class = m_class;
    ch.player.spec = spec;
}

int main() {
    const int levels[] = { 1, 10, 21, 26, 30, 41, 50, 51, 56, 60, 62 };
    const std::pair<uint, int> classes[] = {
        { 0, 0 }, { CLASS_CLERIC, 0 }, { CLASS_CLERIC, SPEC_HEALER }, { CLASS_CONJURER, 0 },
        { CLASS_CONJURER, SPEC_AIR }, { CLASS_SORCERER, 0 }, { CLASS_SUMMONER, 0 },
        { CLASS_DRUID, 0 }, { CLASS_DRUID, SPEC_WOODLAND }, { CLASS_RANGER, 0 }, { CLASS_REAVER, 0 },
        { CLASS_PALADIN, 0 }, { CLASS_ANTIPALADIN, 0 } };
    char_data ch{};
    const P_char self = &ch; // for macros that do not parenthesize their argument

    // Every roll draws exactly as the old code did, within the bounds the page shows.
    same_rolls([] { return dice(3, 8); }, [] { return cure_serious_healing(live_rolls); },
               BOUNDS(cure_serious_healing));
    same_rolls([] { return dice(3, 10) + 10; }, [] { return cure_critic_healing(live_rolls); },
               BOUNDS(cure_critic_healing));
    same_rolls([] { return number(2, 10); }, [] { return cure_light_healing(live_rolls); },
               BOUNDS(cure_light_healing));
    same_rolls([] { return number(1, 4); }, [] { return heal_cap_shortfall(live_rolls); },
               BOUNDS(heal_cap_shortfall));
    same_rolls([] { return number(5, 7); }, [] { return lodestone_vision_duration(live_rolls); },
               BOUNDS(lodestone_vision_duration));
    same_rolls([] { return number(0, 9); }, [] { return summon_shadow_roll(live_rolls); },
               BOUNDS(summon_shadow_roll));
    same_rolls([] { return number(0, 2); }, [] { return word_of_recall_fight_roll(live_rolls); },
               BOUNDS(word_of_recall_fight_roll));
    same_rolls([] { return number(30, 40); }, [] { return plague_heal_block_percent(live_rolls); },
               BOUNDS(plague_heal_block_percent));
    for (int skill : { 0, 1, 4, 5, 37, 100 }) {
        anatomy = skill;
        same_rolls([&] { return number(10, 2 * GET_CHAR_SKILL(&ch, SKILL_ANATOMY)); },
                   [&] { return full_heal_anatomy_bonus(live_rolls, &ch); },
                   { full_heal_anatomy_bonus(lowest_rolls, &ch), full_heal_anatomy_bonus(highest_rolls, &ch) });
        same_rolls([&] { return number(1, (GET_CHAR_SKILL(&ch, SKILL_ANATOMY) / 2)); },
                   [&] { return heal_anatomy_bonus(live_rolls, &ch); },
                   { heal_anatomy_bonus(lowest_rolls, &ch), heal_anatomy_bonus(highest_rolls, &ch) });
    }
    anatomy = 0;
    for (int dam : { 0, 1, 7, 100, 333 })
        same_rolls([=] { return number((int)(dam * get_property("spell.vitalIntercession.healScalarMin", 0.4)),
                                       (int)(dam * get_property("spell.vitalIntercession.healScalarMax", 0.6))); },
                   [=] { return vital_intercession_healing(live_rolls, dam); },
                   { vital_intercession_healing(lowest_rolls, dam), vital_intercession_healing(highest_rolls, dam) });
    for (int sector = 0; sector < NUM_SECT_TYPES; ++sector)
        same_rolls([=] { return old_snake_count(sector); },
                   [=] { return sticks_to_snakes_count(live_rolls, sector); },
                   { sticks_to_snakes_count(lowest_rolls, sector), sticks_to_snakes_count(highest_rolls, sector) });
    for (int level : levels) {
        ch.player.level = level;
        for (auto [m_class, spec] : classes) {
            set_class(ch, m_class, spec);
            same_rolls([&] { return old_full_heal(&ch, level); },
                       [&] { return full_heal_healing(live_rolls, &ch, level); },
                       { full_heal_healing(lowest_rolls, &ch, level), full_heal_healing(highest_rolls, &ch, level) });
            same_rolls([&] { return old_heal(&ch, level); }, [&] { return heal_healing(live_rolls, &ch, level); },
                       { heal_healing(lowest_rolls, &ch, level), heal_healing(highest_rolls, &ch, level) });
            same_rolls([&] { return old_invigorate(&ch, level); },
                       [&] { return invigorate_movement(live_rolls, &ch, level); },
                       { invigorate_movement(lowest_rolls, &ch, level), invigorate_movement(highest_rolls, &ch, level) });
            for (int m_points : { 0, 1, 57, 100, 1000 })
                same_rolls([&] { return number(GET_LEVEL(self) / 2, GET_LEVEL(self)) * m_points / 100; },
                           [&] { return recharger_mana_gained(live_rolls, &ch, m_points); },
                           { recharger_mana_gained(lowest_rolls, &ch, m_points),
                             recharger_mana_gained(highest_rolls, &ch, m_points) });
            // Restructured fixed numbers: the moved branches give the old results.
            assert(natures_touch_healing(&ch, level) == old_natures_touch(&ch, level));
            assert(haste_duration(&ch, level) == old_haste(&ch, level));
            assert(globe_duration(&ch) == old_globe(&ch));
            assert(barkskin_armor_class(&ch, level) == old_barkskin(&ch, level));
        }
        same_rolls([&] { return number(GET_LEVEL(self), (GET_LEVEL(self) * 2)); },
                   [&] { return healing_salve_wave_healing(live_rolls, &ch); },
                   { healing_salve_wave_healing(lowest_rolls, &ch), healing_salve_wave_healing(highest_rolls, &ch) });
        same_rolls([=] { return old_snake_bite(level); }, [=] { return sticks_to_snakes_bite(live_rolls, level); },
                   { sticks_to_snakes_bite(lowest_rolls, level), sticks_to_snakes_bite(highest_rolls, level) });
        same_rolls([=] { return (level / 4) + number(1, 4); }, [=] { return stone_skin_absorb(live_rolls, level); },
                   { stone_skin_absorb(lowest_rolls, level), stone_skin_absorb(highest_rolls, level) });
        for (bool barkskin : { true, false })
            same_rolls([=] { return (level / (barkskin ? 5 : 10)) + number(1, 4); },
                       [=] { return ironwood_absorb(live_rolls, level, barkskin); },
                       { ironwood_absorb(lowest_rolls, level, barkskin), ironwood_absorb(highest_rolls, level, barkskin) });
        same_rolls([=] { return dice(3, (level / 3)); }, [=] { return devitalize_movement(live_rolls, level); },
                   { devitalize_movement(lowest_rolls, level), devitalize_movement(highest_rolls, level) });
        same_rolls([=] { return (int)(level * get_property("spell.vitalIntercession.maxHitsHealedMultiplier", 6)) +
                                number(-20, 20); },
                   [=] { return vital_intercession_pool(live_rolls, level); },
                   { vital_intercession_pool(lowest_rolls, level), vital_intercession_pool(highest_rolls, level) });
        same_rolls([=] { return old_grow_spike(level); }, [=] { return grow_spike_damage(live_rolls, level); },
                   { grow_spike_damage(lowest_rolls, level), grow_spike_damage(highest_rolls, level) });
        for (int sign : { 1, -1 })
            assert(sleep_duration(sign * level) == old_sleep(sign * level));
    }
    set_class(ch, 0, 0);
    for (int dam : { 0, 1, 99, 100, 101, 720 }) {
        assert(grow_spike_saved(dam) == dam >> 1);
        for (int dam_flag = 0; dam_flag <= 4; ++dam_flag)
            assert(grow_spike_terrain(dam, dam_flag) == (int)(dam + 0.1 * dam * dam_flag));
    }

    // Vitality lasts 30 hours only between two NPCs; otherwise the caster's level sets it.
    char_data npc{};
    npc.specials.act = ACT_ISNPC;
    npc.player.level = 20;
    ch.player.level = 50;
    assert(vitality_duration(&npc, &npc) == 30 && vitality_duration(&npc, &ch) == 10);
    assert(vitality_duration(&ch, &npc) == 12 && summon_lag(&npc) == 2 * PULSE_VIOLENCE);
    // A globe recast never reaches its renewal: spell_globe() returns on a globed target.
    assert(globe_refresh_duration() == 8);

    // Each converted spell's ID maps to its facts.
    const std::pair<int, AbilityFacts> registered[] = {
        { SPELL_WATER_TO_LIFE, water_to_life_facts }, { SPELL_AIR_FORM, air_form_facts },
        { SPELL_EARTH_FORM, earth_form_facts }, { SPELL_FIRE_FORM, fire_form_facts },
        { SPELL_WATER_FORM, water_form_facts }, { SPELL_SHADOW_PROJECTION, shadow_projection_facts },
        { SPELL_HEALING_SALVE, healing_salve_facts }, { SPELL_PLAGUE, plague_facts },
        { SPELL_POWERCAST_FLY, fly_facts }, { SPELL_GROW_SPIKES, grow_spike_facts },
        { SPELL_MINOR_GLOBE, minor_globe_facts }, { SPELL_DEFLECT, deflect_facts },
        { SPELL_VIGORIZE_LIGHT, vigorize_light_facts }, { SPELL_DEVITALIZE, devitalize_facts },
        { SPELL_VIGORIZE_SERIOUS, vigorize_serious_facts }, { SPELL_INVIGORATE, invigorate_facts },
        { SPELL_VIGORIZE_CRITIC, invigorate_facts }, { SPELL_DISEASE, disease_facts },
        { SPELL_CURSE, curse_facts }, { SPELL_NETHER_TOUCH, nether_touch_facts },
        { SPELL_FARSEE, farsee_facts }, { SPELL_RECHARGER, recharger_facts },
        { SPELL_CURE_LIGHT, cure_light_facts }, { SPELL_CURE_SERIOUS, cure_serious_facts },
        { SPELL_CURE_CRITIC, cure_critic_facts }, { SPELL_HEAL, heal_facts },
        { SPELL_NATURES_TOUCH, natures_touch_facts }, { SPELL_STICKS_TO_SNAKES, sticks_to_snakes_facts },
        { SPELL_FULL_HEAL, full_heal_facts }, { SPELL_VITALIZE_UNDEAD, vitalize_undead_facts },
        { SPELL_VITALIZE_SOUL, vitalize_undead_facts }, { SPELL_VITALITY, vitality_facts },
        { SPELL_MIRACLE, miracle_facts }, { SPELL_DETECT_INVISIBLE, detect_invisibility_facts },
        { SPELL_DETECT_EVIL, detect_evil_facts }, { SPELL_DETECT_GOOD, detect_good_facts },
        { SPELL_DETECT_MAGIC, detect_magic_facts }, { SPELL_DEATH_BLESSING, death_blessing_facts },
        { SPELL_ENCHANT_WEAPON, enchant_weapon_facts }, { SPELL_UNMAKING, unmaking_facts },
        { SPELL_RETURN_SOUL, unmaking_facts }, { SPELL_INVISIBILITY, invisibility_facts },
        { SPELL_CONCEALMENT, concealment_facts }, { SPELL_PROTECT_FROM_EVIL, protection_from_evil_facts },
        { SPELL_PROTECT_FROM_GOOD, protection_from_good_facts }, { SPELL_IRONWOOD, ironwood_facts },
        { SPELL_STONE_SKIN, stone_skin_facts }, { SPELL_GROUP_STONE_SKIN, group_stone_skin_facts },
        { SPELL_SLEEP, sleep_facts }, { SPELL_STRENGTH, strength_facts },
        { SPELL_DEXTERITY, dexterity_facts }, { SPELL_AGILITY, agility_facts },
        { SPELL_SUMMON, summon_facts }, { SPELL_BLUR, blur_facts },
        { SPELL_STORNOGS_LOWERED_RES, stornogs_lowered_res_facts }, { SPELL_LODESTONE, lodestone_vision_facts },
        { SPELL_HASTE, haste_facts }, { SPELL_GROUP_HASTE, group_haste_facts },
        { SPELL_WORD_OF_RECALL, word_of_recall_facts }, { SPELL_GROUP_RECALL, group_recall_facts },
        { SPELL_MINOR_PARALYSIS, minor_paralysis_facts }, { SPELL_MAJOR_PARALYSIS, major_paralysis_facts },
        { SPELL_SLOW, slow_facts }, { SPELL_SENSE_LIFE, sense_life_facts },
        { SPELL_CONTINUAL_LIGHT, continual_light_facts }, { SPELL_LEVITATE, levitate_facts },
        { SPELL_FLY, fly_facts }, { SPELL_AIRY_WATER, airy_water_facts }, { SPELL_GLOBE, globe_facts },
        { SPELL_GROUP_GLOBE, group_globe_facts }, { SPELL_BARKSKIN, barkskin_facts },
        { SPELL_DIVINE_WARDING, divine_warding_facts },
        { SPELL_VITAL_INTERCESSION, vital_intercession_facts },
        { SPELL_HOLY_INTERCESSION, holy_intercession_facts }, { SPELL_IDENTIFY, identify_facts },
        { SPELL_MASS_INVIS, mass_invisibility_facts }, { SPELL_MASS_BARKSKIN, mass_barkskin_facts } };
    static_assert(std::size(registered) == 77);
    for (auto [spell, facts] : registered)
        assert(ability_facts(spell) == facts);
    assert(ability_facts(SPELL_STORNOGS_GREATER_SPHERES) == group_stornog_facts);

    // Building any page leaves the RNG untouched, and every line is indented and fits.
    for (int i = 0; i < 52; ++i)
        str_app[i].carry_w = static_cast<sh_int>(100 + 10 * i);
    randomize(9);
    const int untouched = fingerprint();
    for (int level : levels)
        for (auto [m_class, spec] : classes)
            for (int skill : { 0, 100 })
                for (auto [spell, facts] : registered) {
                    ch.player.level = level;
                    set_class(ch, m_class, spec);
                    anatomy = skill;
                    randomize(9);
                    std::istringstream lines(facts(&ch));
                    assert(fingerprint() == untouched);
                    std::string line;
                    while (std::getline(lines, line))
                        assert(line.rfind("  ", 0) == 0 && line.size() <= 79);
                }
    anatomy = 0;
    set_class(ch, 0, 0);
    ch.player.level = 50;

    // Healing.
    assert(cure_light_facts(&ch) == "  Healing: 2-10\n  Healing modifiers apply after.\n");
    assert(contains(cure_serious_facts(&ch), "  Healing: 3-24\n"));
    assert(contains(cure_critic_facts(&ch), "  Healing: 13-40\n"));
    std::string text = heal_facts(&ch);
    assert(contains(text, "  Healing: 105-125 at your level, 50\n"));
    assert(contains(text, "  Healing cap: 1-4 below the target's maximum hit points\n"));
    assert(!contains(text, "anatomy"));
    anatomy = 100;
    assert(contains(heal_facts(&ch), "  If your anatomy diagnosis succeeds: 1-50 more\n"));
    assert(contains(full_heal_facts(&ch), "  If your anatomy diagnosis succeeds: 10-200 more\n"));
    anatomy = 0;
    assert(contains(full_heal_facts(&ch), "  Healing: 257-390 at your level, 50\n"));
    ch.player.level = 56;
    set_class(ch, CLASS_CLERIC, SPEC_HEALER);
    assert(contains(heal_facts(&ch), "  Healing: 106-130 at your level, 56\n"));
    assert(contains(full_heal_facts(&ch), "  Healing: 264-530 at your level, 56\n"));
    assert(contains(water_to_life_facts(&ch), "  Healing: 232 at your level, 56\n"));
    ch.player.level = 50;
    set_class(ch, CLASS_DRUID, 0);
    assert(contains(natures_touch_facts(&ch), "  First wave of healing: 47 at your level, 50\n"));
    set_class(ch, 0, 0);
    assert(contains(natures_touch_facts(&ch), "  First wave of healing: 11 at your level, 50\n"));
    assert(contains(healing_salve_facts(&ch), "  Healing waves: 6 at your level, 50, every 3 seconds\n"
                                              "  Healing per wave: the target's level to twice it; 50-100 on you\n"));
    assert(unmaking_facts(&ch) == "  Healing: 100 at your level, 50, plus 4 per level of the corpse\n"
                                  "  It heals you, up to your maximum hit points.\n");
    assert(contains(vitality_facts(&ch), "  Maximum hit points: +200 at your level, 50\n"
                                         "  Duration: 12-13 game hours (15-16.25 minutes)\n"));
    assert(contains(miracle_facts(&ch), "  Maximum hit points: +200 at your level, 50\n"));
    assert(contains(vitalize_undead_facts(&ch), "  Maximum hit points: +100 at your level, 50\n"
                                                "  Duration: 20-21 game hours (25-26.25 minutes)\n"));
    assert(death_blessing_facts(&ch) == "  Vitalize undead on each group member in the room:\n"
                                        "  Maximum hit points: +112 for the group leader, +100 for the others\n"
                                        "  Duration: 20-21 game hours (25-26.25 minutes)\n"
                                        "  Only undead, angels, golems and necromancers gain it.\n"
                                        "  It also casts protection from living on each group member.\n");
    assert(contains(vital_intercession_facts(&ch), "  Healing pool: 280-320 at your level, 50\n"
                                                   "  Each hit taken heals: 40-60% of its damage, from the pool\n"
                                                   "  Duration: 5-6 game hours (6.25-7.5 minutes)\n"));
    assert(contains(holy_intercession_facts(&ch), "  Healing pool: 178-218 at level 33\n"));

    // Movement and mana.
    assert(contains(invigorate_facts(&ch), "  Movement restored: 2-120 at your level, 50\n"));
    assert(contains(vigorize_serious_facts(&ch), "  Movement restored: 2-79 at level 33\n"));
    assert(contains(vigorize_light_facts(&ch), "  Movement restored: 2-38 at level 16\n"));
    set_class(ch, CLASS_CLERIC, 0);
    assert(contains(invigorate_facts(&ch), "  Movement restored: 4-225 at your level, 50\n"));
    set_class(ch, 0, 0);
    assert(devitalize_facts(&ch) == "  Movement drained: 3-48 at your level, 50\n"
                                    "  Lowest it leaves the target: 20 movement\n");
    assert(recharger_facts(&ch) == "  Mana you gain: 25-50% of the mana you drain\n");

    // Damage.
    assert(contains(sticks_to_snakes_facts(&ch), "  Damage per snake: 8-56 at your level, 50\n"
                                                 "  Snakes: 1 indoors, up to 6 in a forest\n"
                                                 "  Arrows the target carries turn into snakes as well, "
                                                 "up to 8 snakes in all.\n"));
    text = grow_spike_facts(&ch);
    assert(contains(text, "  Damage in the open: 132-792 at your level, 50\n"));
    assert(contains(text, "  In mountains or most of the Underdark: 144-864\n  Indoors: 156-936\n"));
    assert(contains(text, "  On lava or liquid mithril, as fire: 168-1008\n"));
    ch.player.level = 51;
    assert(contains(grow_spike_facts(&ch), "  Damage in the open: 132-924 at your level, 51\n"));
    ch.player.level = 50;

    // Skins and armor.
    text = stone_skin_facts(&ch);
    assert(contains(text, "  Hits absorbed: 10-12 at your level, 50\n"));
    assert(contains(text, "  With living stone or the Mace of Earth: 19-24\n"));
    assert(contains(text, "  Duration: 4-5 game hours (5-6.25 minutes)\n  Layers on an earth conjurer: up to 3\n"));
    set_class(ch, CLASS_CONJURER, 0);
    assert(contains(stone_skin_facts(&ch), "  Hits absorbed: 15-19 at your level, 50\n"));
    set_class(ch, CLASS_SORCERER, 0);
    assert(contains(stone_skin_facts(&ch), "  Hits absorbed: 13-16 at your level, 50\n"));
    set_class(ch, 0, 0);
    assert(contains(group_stone_skin_facts(&ch), "  Stone skin on each group member in the room:\n"
                                                 "  Hits absorbed: 7-9 at level 32\n"
                                                 "  With living stone or the Mace of Earth: 13-18\n"));
    assert(contains(ironwood_facts(&ch), "  Hits absorbed: 11-14 over barkskin, 6-9 over thornskin\n"));
    assert(contains(barkskin_facts(&ch), "  Armor class: -50 at your level, 50\n"
                                         "  Duration: 25-26 game hours (31.25-32.5 minutes)\n"));
    assert(contains(barkskin_facts(&ch), "  A player on the enemy side of the race war may resist "
                                         "with a paralysis save.\n"));
    // The mass spells cast the single-target spell at the caster's own level.
    assert(mass_barkskin_facts(&ch) ==
           "  Casts: barkskin on everyone in the room at your height, at your level\n" + barkskin_facts(&ch));
    assert(mass_invisibility_facts(&ch) == "  Casts: invisibility on everyone in the room, at your level\n" +
                                               invisibility_facts(&ch) + "  A mortal caster skips immortals.\n");
    set_class(ch, CLASS_DRUID, SPEC_WOODLAND);
    assert(contains(barkskin_facts(&ch), "  Armor class: -62 at your level, 50\n"));
    set_class(ch, 0, 0);
    assert(fire_form_facts(&ch) == "  Armor class: -15\n  Strength and its maximum: +15\n"
                                   "  Dexterity and its maximum: -20\n  Agility and its maximum: -20\n"
                                   "  Constitution and its maximum: +25\n"
                                   "  Duration: 8-9 game hours (10-11.25 minutes)\n");
    assert(water_form_facts(&ch) == "  Strength and its maximum: -20\n  Dexterity and its maximum: +50\n"
                                    "  Agility and its maximum: +25\n  Constitution and its maximum: -10\n"
                                    "  Duration: 8-9 game hours (10-11.25 minutes)\n");
    assert(enchant_weapon_facts(&ch) == "  Hitroll: +2 at your level, 50\n  Damroll: +2 at your level, 50\n"
                                        "  If the weapon already has effects: hitroll +2 only\n");
    ch.player.level = 56;
    assert(contains(enchant_weapon_facts(&ch), "  Hitroll: +3 at your level, 56\n  Damroll: +3 at your level, 56\n"));
    ch.player.level = 50;

    // Afflictions.
    assert(curse_facts(&ch) == "  Hitroll: -5 on a player, -10 on a creature\n  All saving throws: 10 worse\n"
                               "  Duration: 50-51 game hours (62.5-63.75 minutes)\n");
    assert(nether_touch_facts(&ch) == "  Hitroll: -3\n  All saving throws: 10 worse\n"
                                      "  Saving throw against paralysis: 2 worse again\n  Duration: 25 seconds\n");
    assert(contains(disease_facts(&ch), "  Strength, dexterity, agility and constitution: -30 at your level, 50\n"
                                        "  Duration: 18-19 game hours (22.5-23.75 minutes)\n"
                                        "  Recast duration: 12-13 game hours (15-16.25 minutes)\n"));
    assert(plague_facts(&ch) == "  Duration on a player: 2-3 game hours (2.5-3.75 minutes)\n"
                                "  On a creature at your level, 50: 4-5 game hours (5-6.25 minutes)\n"
                                "  Healing it blocks: 30-40% of each heal\n"
                                "  Total it can block: 500 on a player, 3500 on a creature; then it ends\n");
    assert(stornogs_lowered_res_facts(&ch) == "  Saving throw against spells: 8 worse at your level, 50\n"
                                              "  Duration: 5-6 game hours (6.25-7.5 minutes)\n");
    assert(major_paralysis_facts(&ch) == "  Duration: 25 seconds\n");
    assert(minor_paralysis_facts(&ch) == "  Duration: 37.5 seconds at your level, 50\n");
    assert(slow_facts(&ch) == "  Duration: 4-5 game hours (5-6.25 minutes)\n");
    assert(sleep_facts(&ch) == "  Duration: 4-5 game hours (5-6.25 minutes)\n");

    // Durations and utility.
    const std::pair<AbilityFacts, const char *> durations[] = {
        { shadow_projection_facts, "1-2 game hours (1.25-2.5 minutes)" },
        { concealment_facts, "25-26 game hours (31.25-32.5 minutes)" },
        { invisibility_facts, "25-26 game hours (31.25-32.5 minutes)" },
        { detect_evil_facts, "50-51 game hours (62.5-63.75 minutes)" },
        { detect_good_facts, "50-51 game hours (62.5-63.75 minutes)" },
        { detect_magic_facts, "50-51 game hours (62.5-63.75 minutes)" },
        { detect_invisibility_facts, "50-51 game hours (62.5-63.75 minutes)" },
        { protection_from_evil_facts, "50-51 game hours (62.5-63.75 minutes)" },
        { protection_from_good_facts, "50-51 game hours (62.5-63.75 minutes)" },
        { sense_life_facts, "50-51 game hours (62.5-63.75 minutes)" },
        { levitate_facts, "50-51 game hours (62.5-63.75 minutes)" },
        { farsee_facts, "100-101 game hours (125-126.25 minutes)" },
        { fly_facts, "100-101 game hours (125-126.25 minutes)" },
        { blur_facts, "10-11 game hours (12.5-13.75 minutes)" },
        { haste_facts, "10-11 game hours (12.5-13.75 minutes)" },
        { globe_facts, "8-9 game hours (10-11.25 minutes)" },
        { minor_globe_facts, "6-7 game hours (7.5-8.75 minutes)" },
        { earth_form_facts, "8-9 game hours (10-11.25 minutes)" },
        { air_form_facts, "8-9 game hours (10-11.25 minutes)" },
        { deflect_facts, "until it deflects a damage spell" },
        { airy_water_facts, "125 seconds at your level, 50" } };
    for (auto [facts, duration] : durations)
        assert(facts(&ch) == "  Duration: " + std::string(duration) + "\n");
    assert(lodestone_vision_facts(&ch) == "  Shortest duration: 5-6 game hours (6.25-7.5 minutes)\n"
                                          "  Longest duration: 7-8 game hours (8.75-10 minutes)\n");
    assert(strength_facts(&ch) == "  Strength: +10\n  Duration: 50-51 game hours (62.5-63.75 minutes)\n");
    assert(contains(dexterity_facts(&ch), "  Dexterity: +10\n"));
    assert(contains(agility_facts(&ch), "  Agility: +10\n"));
    assert(contains(divine_warding_facts(&ch), "  Duration: 11 minutes\n"));
    assert(identify_facts(&ch) == "  Items warded against identification: readable from level 51\n");
    assert(continual_light_facts(&ch) == "  Room light: 625 seconds at your level, 50\n");
    assert(summon_facts(&ch) == "  Range: 75 rooms at your level, 50\n  Targets up to level: 53\n"
                                "  A target that has not given you consent gets a saving throw.\n"
                                "  Your lag when the target is in range and summonable: 12 seconds\n"
                                "  Chance a hostile shadow answers instead: 1 in 10 outside no-summon rooms\n");
    ch.player.level = 56;
    assert(contains(summon_facts(&ch), "  Targets up to level: 56\n"));
    ch.player.level = 50;
    set_class(ch, CLASS_CONJURER, SPEC_AIR);
    assert(haste_facts(&ch) == "  Duration: 25-26 game hours (31.25-32.5 minutes)\n");
    assert(group_haste_facts(&ch) == "  Haste on each group member in the room:\n"
                                     "  Duration: 16-17 game hours (20-21.25 minutes)\n");
    assert(globe_facts(&ch) == "  Duration: 15-16 game hours (18.75-20 minutes)\n");
    assert(contains(group_globe_facts(&ch), "  Duration: 15-16 game hours (18.75-20 minutes)\n"));
    set_class(ch, CLASS_SUMMONER, 0);
    assert(globe_facts(&ch) == "  Duration: 12-13 game hours (15-16.25 minutes)\n");
    set_class(ch, 0, 0);
    ch.curr_stats.Str = 80;
    const std::string limit = std::to_string((CAN_CARRY_W(self) / 100) * 70);
    assert(word_of_recall_facts(&ch) == "  Weight limit: " + limit + " pounds; above it you leave worn gear behind\n"
                                        "  Chance it fails on a player fighting a player: 1 in 3\n");
    assert(contains(group_recall_facts(&ch), ("  Weight limit: " + limit).c_str()));
    puts("PASS: batch 2 shared rolls match the old code, ranges are exact, facts never roll");
}
'''


def definitions():
    """Each SHARED function's source, in magic.c order."""
    text = source("magic.c").read_text()
    found = []
    for name in SHARED:
        match = re.search(rf"^(?:static )?(?:int|bool|Range|std::string) {name}\(", text, re.M)
        assert match, name
        found.append((match.start(), extract_function("magic.c", match.group(0))))
    return [body for _, body in sorted(found)]


def check_handlers_use_shared_numbers():
    code = strip_comments(source("magic.c").read_text())
    for handler, calls in CALLS.items():
        bodies = function_bodies(code, rf"\bvoid\s+{handler}\s*\(")
        assert len(bodies) == 1, handler
        body = " ".join(bodies[0].split())
        for call in calls:
            assert " ".join(call.split()) in body, (handler, call)


def check_vamp_uses_plague_block():
    bodies = function_bodies(strip_comments(source("fight.c").read_text()), r"\bint\s+vamp\s*\(")
    assert len(bodies) == 1
    call = "blocked = (int)(MIN(hits * (((float)plague_heal_block_percent(live_rolls)) / 100), af->modifier));"
    assert " ".join(call.split()) in " ".join(bodies[0].split())


def main():
    check_handlers_use_shared_numbers()
    check_vamp_uses_plague_block()
    extracted = set(SHARED)
    declared = re.findall(r"^std::string (\w+_facts)\(char_data \*ch\);", source("abilities.h").read_text(), re.M)
    # abilities.c's table names every facts function; the ones outside this batch never run here.
    stubs = "".join(f"std::string {name}(char_data *) {{ std::abort(); }}\n"
                    for name in declared if name not in extracted)
    functions = [extract_function("utility.c", "int dice(int num, int size)"),
                 extract_function("utility.c", "int GET_CLASS(P_char ch, uint m_class)"),
                 extract_function("utility.c", "// Example: str_app[STAT_INDEX(GET_C_STR(ch))].todam\nint STAT_INDEX("),
                 extract_function("magic.c", "int KludgeDuration(P_char ch, int baselevel, int baseduration)"),
                 extract_function("fight.c", "int plague_heal_block_percent(const Rolls &rolls)"),
                 stubs] + definitions()
    build = ROOT / "bin/tests"
    build.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ability-batch-2-", dir=build) as temporary:
        directory = Path(temporary)
        harness = directory / "abilities.cpp"
        harness.write_text(HARNESS.replace("int main() {", "\n".join(functions) + "\nint main() {"))
        binary = directory / "abilities"
        subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
                        "-ffunction-sections", "-fdata-sections", "-Wl,--gc-sections",
                        "-fsanitize=address,undefined", "-fno-sanitize-recover=undefined",
                        "-Isrc", "-I/usr/include/mysql", "-I/usr/include/libxml2",
                        str(harness), "src/abilities/abilities.c", "src/core/random.c",
                        "-o", str(binary)], cwd=ROOT, check=True)
        subprocess.run([str(binary)], cwd=directory, check=True)


if __name__ == "__main__":
    main()
