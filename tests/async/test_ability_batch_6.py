#!/usr/bin/env python3
"""Shared ability numbers, batch 6: psionicist and avenger spells, learning, lucubration.

Builds src/abilities/abilities.c and the real RNG with every shared and facts function of
psionics.c, avengers.c, guild.c's learning and memorize.c's lucubration, under sanitizers.
Each converted roll keeps its pre-conversion expression below as the oracle: under the
same seeds it must give the same value and leave the RNG at the same draw, and the value
must fall inside the range its facts show. Every page is built at every level for several
casters: it must never roll, and every line must fit 79 columns.
"""
import re
import subprocess
import tempfile
from pathlib import Path

from _paths import ROOT, extract_function, source
from _innate_numbers import with_innate_numbers
from _source_contract import function_bodies, strip_comments

PSIONICS = source("psionics.c").read_text()
AVENGERS = source("avengers.c").read_text()
GUILD = source("guild.c").read_text()
MEMORIZE = source("memorize.c").read_text()

SPELLS = [line.split() for line in """
SPELL_ADRENALINE_CONTROL adrenaline_control psionics.c
SPELL_AURA_SIGHT aura_sight psionics.c
SPELL_AWE awe psionics.c
SPELL_BALLISTIC_ATTACK ballistic_attack psionics.c
SPELL_BIOFEEDBACK biofeedback psionics.c
SPELL_CANNIBALIZE cannibalize psionics.c
SPELL_CELERITY celerity psionics.c
SPELL_CELL_ADJUSTMENT cell_adjustment psionics.c
SPELL_COMBAT_MIND combat_mind psionics.c
SPELL_CONFUSE confuse psionics.c
SPELL_CONTROL_FLAMES control_flames psionics.c
SPELL_DEATH_FIELD death_field psionics.c
SPELL_DEPART depart psionics.c
SPELL_DETONATE detonate psionics.c
SPELL_DISPLACEMENT displacement psionics.c
SPELL_ECTOPLASMIC_FORM ectoplasmic_form psionics.c
SPELL_EGO_BLAST ego_blast psionics.c
SPELL_EGO_WHIP ego_whip psionics.c
SPELL_ENERGY_CONTAINMENT energy_containment psionics.c
SPELL_ENHANCED_AGI enhanced_agility psionics.c
SPELL_ENHANCED_CON enhanced_constitution psionics.c
SPELL_ENHANCED_DEX enhanced_dexterity psionics.c
SPELL_ENHANCED_STR enhanced_strength psionics.c
SPELL_ENHANCE_ARMOR enhance_armor psionics.c
SPELL_ENRAGE enrage psionics.c
SPELL_ETHEREAL_RIFT ethereal_rift psionics.c
SPELL_ETHER_WARP ether_warp psionics.c
SPELL_EXCOGITATE excogitate psionics.c
SPELL_FIRE_AURA fire_aura psionics.c
SPELL_FLESH_ARMOR flesh_armor psionics.c
SPELL_INERTIAL_BARRIER inertial_barrier psionics.c
SPELL_INFLICT_PAIN inflict_pain psionics.c
SPELL_INTELLECT_FORTRESS intellect_fortress psionics.c
SPELL_LEND_HEALTH lend_health psionics.c
SPELL_MEMORY_BLOCK memory_block psionics.c
SPELL_MENTAL_ANGUISH mental_anguish psionics.c
SPELL_MIND_BLANK mind_blank psionics.c
SPELL_MIND_TRAVEL mind_travel psionics.c
SPELL_MOLECULAR_AGITATION molecular_agitation psionics.c
SPELL_MOLECULAR_CONTROL molecular_control psionics.c
SPELL_PSIONIC_CLOUD psionic_cloud psionics.c
SPELL_PSIONIC_WAVE_BLAST psionic_wave_blast psionics.c
SPELL_PSYCHIC_CRUSH psychic_crush psionics.c
SPELL_PYROKINESIS pyrokinesis psionics.c
SPELL_RADIAL_NAV radial_navigation psionics.c
SPELL_SPINAL_CORRUPTION spinal_corruption psionics.c
SPELL_THOUGHT_BEACON thought_beacon psionics.c
SPELL_TOWER_IRON_WILL tower_iron_will psionics.c
SPELL_WORMHOLE wormhole psionics.c
SPELL_ATONEMENT atonement avengers.c
SPELL_CELESTIAL_AURA celestial_aura avengers.c
SPELL_DIVINE_POWER divine_power avengers.c
SPELL_HOLY_SWORD holy_sword avengers.c
SPELL_LEARNING learning guild.c
SPELL_MORDENKAINENS_LUCUBRATION mordenkainens_lucubration memorize.c
""".split("\n") if line.strip()]

# What each handler (or event, or callback) must call, tying each helper to its own branch.
HANDLER_CALLS = {
    "psionics.c": {
        "spell_molecular_control": ["af1->duration = molecular_control_duration(level)",
                                    "af.duration = molecular_control_duration(level)"],
        "spell_molecular_agitation": ["dam = molecular_agitation_damage(live_rolls, level)",
                                      "dam = molecular_agitation_saved(dam)"],
        "spell_adrenaline_control": ["af.duration = adrenaline_control_duration(level)",
                                     "af.modifier = adrenaline_control_bonus()"],
        "spell_aura_sight": ["af1->duration = aura_sight_duration()", "af.duration = aura_sight_duration()",
                             "GET_LEVEL(ch) > aura_sight_alignment_above()", "GET_LEVEL(ch) > aura_sight_life_above()",
                             "GET_LEVEL(ch) > aura_sight_invisible_above()", "GET_LEVEL(ch) > aura_sight_farsee_above()"],
        "spell_awe": ["num >= awe_follower_limit()", "max_level = awe_limits(level, ch, &max_total_levels)",
                      "int save = awe_threshold(GET_C_POW(ch), level", "save < awe_roll(live_rolls)"],
        "spell_mind_travel": ["CharWait(ch, mind_travel_lag())"],
        "spell_ballistic_attack": ["dam = ballistic_attack_damage(live_rolls, level)",
                                   "dam = ballistic_attack_failed_save(dam)"],
        "spell_biofeedback": ["af.duration = biofeedback_duration()",
                              "af.modifier = biofeedback_absorb(live_rolls, level)"],
        "spell_cell_adjustment": ["GET_LEVEL(ch) > cell_adjustment_poison_above()",
                                  "GET_LEVEL(ch) > cell_adjustment_curse_above()",
                                  "GET_LEVEL(ch) > cell_adjustment_blindness_above()",
                                  "GET_LEVEL(ch) > cell_adjustment_wither_above()",
                                  "GET_LEVEL(ch) > cell_adjustment_disease_above()"],
        "spell_combat_mind": ["af1->duration = combat_mind_duration(level)", "af.duration = combat_mind_duration(level)",
                              "af.modifier = combat_mind_hitroll(level)", "af.modifier = combat_mind_damroll(level)"],
        "spell_fire_aura": ["af.duration = fire_aura_duration()", "af.modifier = fire_aura_ac()",
                            "af.modifier = fire_aura_str_max()", "af.modifier = fire_aura_nimbleness()",
                            "af.modifier = fire_aura_con_max()",
                            "NewSaves(ch, SAVING_FEAR, fire_aura_full_form_save())"],
        "spell_control_flames": ["dam = control_flames_damage(live_rolls, level)",
                                 "dam = control_flames_saved(dam)", "damage(ch, victim, dam, SPELL_EGO_BLAST)"],
        "spell_ego_blast": ["dam = ego_blast_damage(live_rolls, level)", "dam = ego_blast_saved(dam)",
                            "damage(ch, victim, dam, SPELL_EGO_BLAST)"],
        "spell_psychic_crush": ["dam = psychic_crush_damage(live_rolls, level)",
                                "af.duration = psychic_crush_penalty_duration()",
                                "af.modifier = psychic_crush_penalty(level)", "psychic_crush_saved(dam)",
                                "spec_affect = psychic_crush_enslaver_roll(live_rolls)",
                                "spec_affect < psychic_crush_stun_below()", "Stun(victim, ch, psychic_crush_stun(), TRUE)",
                                "spec_affect < psychic_crush_kneel_below()"],
        "spell_single_death_field": ["dam = death_field_damage(live_rolls, level)",
                                     "dam = death_field_enslaver_damage(dam, ch)", "dam = death_field_player_damage(dam)"],
        "spell_death_field": ["stack_area(ch, SPELL_DEATH_FIELD, death_field_stack_seconds())",
                              "level = death_field_stacked_level(level)",
                              "cast_as_damage_area(ch, spell_single_death_field, level",
                              "CharWait(ch, death_field_lag())"],
        "spell_detonate": ["dam = detonate_damage(live_rolls, level)", "dam += detonate_damroll_bonus(ch)",
                           "dam += detonate_mindflayer_bonus(level)", "dam = detonate_construct_damage(dam)",
                           "dam = detonate_pyrokinetic_shrug(dam)", "dam = detonate_mindflayer_shrug(dam)",
                           "detonate_saved(dam)"],
        "spell_spinal_corruption": ["switch (spinal_corruption_effect_roll(live_rolls))",
                                    "CharWait(victim, spinal_corruption_lag())",
                                    "af.duration = spinal_corruption_slow_duration()"],
        "spell_mental_anguish": ["af.duration = mental_anguish_duration(ch)"],
        "spell_psionic_cloud": ["af.duration = psionic_cloud_duration(level)",
                                "af.modifier = -1 * psionic_cloud_penalty(live_rolls, level)",
                                "af1.duration = psionic_cloud_duration(level)",
                                "af1.modifier = -1 * psionic_cloud_penalty(live_rolls, level)"],
        "spell_displacement": ["af.duration = displacement_duration(level)", "af.modifier = displacement_ac(level)"],
        "spell_ectoplasmic_form": ["af.duration = ectoplasmic_form_duration(level)",
                                   "af1->duration = ectoplasmic_form_duration(level)"],
        "spell_ego_whip": ["dam = ego_whip_damage(live_rolls, level)", "dam = ego_whip_saved(dam)",
                           "dam = ego_whip_iron_will(dam)"],
        "spell_energy_containment": ["af1->duration = energy_containment_duration(level)",
                                     "af.duration = energy_containment_duration(level)",
                                     "af.modifier = energy_containment_save(level)"],
        "spell_enhance_armor": ["af.duration = enhance_armor_duration()", "af.modifier = enhance_armor_ac(level)",
                                "af1->duration = enhance_armor_duration()"],
        "spell_enhanced_strength": ["af.duration = enhanced_strength_duration(level)",
                                    "af.modifier = enhanced_strength_bonus(level)"],
        "spell_enhanced_dexterity": ["af.duration = enhanced_dexterity_duration(level)",
                                     "af.modifier = enhanced_dexterity_bonus(level)"],
        "spell_enhanced_agility": ["af.duration = enhanced_agility_duration(level)",
                                   "af.modifier = enhanced_agility_bonus(level)"],
        "spell_enhanced_constitution": ["af.duration = enhanced_constitution_duration(level)",
                                        "af.modifier = enhanced_constitution_bonus(level)"],
        "spell_flesh_armor": ["af1->duration = flesh_armor_duration()", "af.duration = flesh_armor_duration()",
                              "af.modifier = flesh_armor_ac(level)"],
        "spell_inertial_barrier": ["af1->duration = inertial_barrier_duration()",
                                   "af.duration = inertial_barrier_duration()"],
        "spell_inflict_pain": ["int dam = inflict_pain_damage(live_rolls, level)", "dam = inflict_pain_saved(dam)"],
        "spell_intellect_fortress": ["af1->duration = intellect_fortress_duration()",
                                     "af.duration = intellect_fortress_duration()",
                                     "af.modifier = intellect_fortress_intelligence(level)"],
        "spell_lend_health": ["hp = MIN(lend_health_most(ch)", "GET_HIT(ch) - hp < lend_health_lowest_health()",
                              "heal(victim, ch, lend_health_healing(hp)", "GET_MAX_HIT(victim) - lend_health_short_roll(live_rolls)",
                              "GET_HIT(ch) -= lend_health_cost(hp)"],
        "spell_confuse": ["max_level = confuse_target_levels(level)", "temp = confuse_effect_roll(live_rolls)",
                          "Stun(tch, ch, confuse_stun(), TRUE)", "GET_MANA(ch) - confuse_githyanki_mana()"],
        "spell_pyrokinesis": ["pyrokinesis_shrug_roll(live_rolls) < pyrokinesis_shrug_below()",
                              "int phys_dam = pyrokinesis_damage(live_rolls, level)",
                              "int fire_dam = pyrokinesis_damage(live_rolls, level)",
                              "fire_dam = pyrokinesis_pyrokinetic_fire(fire_dam)",
                              "phys_dam = pyrokinesis_failed_psionic(phys_dam)",
                              "fire_dam = pyrokinesis_failed_fire(fire_dam)",
                              "af.duration = pyrokinesis_penalty_duration()", "af.modifier = pyrokinesis_penalty(level)",
                              "CharWait(ch, pyrokinesis_lag())"],
        "spell_celerity": ["movepoints = celerity_vitality(live_rolls, level)", "celerity_cost(movepoints)"],
        "spell_depart": ["int range = depart_range()", "level < depart_free_level()", "how_close(victim->in_room, to_room, depart_limited_range()) < 0",
                         "CharWait(victim, depart_lag())"],
        "spell_psionic_wave_blast": ["dam = psionic_wave_blast_damage(live_rolls, level)",
                                     "af->modifier = psionic_wave_blast_waves()"],
        "event_psionic_wave_blast": ["dam = psionic_wave_blast_wave_damage(live_rolls, level)",
                                     "dam = psionic_wave_blast_failed_save(dam)", "dam = psionic_wave_blast_away(dam)",
                                     "GET_MANA(ch) -= psionic_wave_blast_mana()",
                                     "add_event(event_psionic_wave_blast, psionic_wave_blast_interval()"],
        "spell_enrage": ["attdiff = enrage_attack(live_rolls, ch, victim)",
                         "attdiff = BOUNDED(enrage_least(), attdiff, enrage_most())",
                         "berserk(victim, enrage_berserk(live_rolls, attdiff))"],
        "spell_mind_blank": ["af.duration = mind_blank_duration(level)", "af.duration = mind_blank_cooldown()"],
        "spell_cannibalize": ["af1->duration = cannibalize_duration(level)", "af.duration = cannibalize_duration(level)"],
        "spell_tower_iron_will": ["af1->duration = tower_iron_will_duration(level)",
                                  "af.duration = tower_iron_will_duration(level)"],
        "spell_radial_navigation": ["distance > radial_navigation_range(ch)",
                                    "GET_MANA(ch) -= radial_navigation_mana(distance)",
                                    "CharWait(ch, radial_navigation_lag())",
                                    "KnockOut(ch, radial_navigation_knockout(GET_MANA(ch)))"],
        "spell_ethereal_rift": ["CharWait(ch, ethereal_rift_lag())"],
        "spell_ether_warp": ["GET_LEVEL(victim) < ether_warp_protected_below()",
                             "CharWait(ch, ether_warp_punishment_lag())", "distance = ether_warp_range(level)",
                             "CharWait(ch, ether_warp_lag())"],
        "spell_thought_beacon": ["int duration = thought_beacon_duration(level)",
                                 "af.duration = duration",
                                 "set_obj_affected(beacon, duration, TAG_OBJ_DECAY, 0)"],
        "spell_wormhole": ["GET_LEVEL(victim) < wormhole_protected_below()",
                           "CharWait(ch, wormhole_punishment_lag())", "distance = wormhole_range(level)",
                           "set.decay_timer = wormhole_decay_timer(ch)",
                           "set.throughput = wormhole_throughput(live_rolls, ch)"],
        "spell_excogitate": ["diff < excogitate_far_greater_below()", "diff < excogitate_greater_below()",
                             "diff < excogitate_equal_below()", "diff < excogitate_less_below()",
                             "diff < excogitate_much_less_below()"],
    },
    "avengers.c": {
        "spell_holy_sword": ["af.duration = holy_sword_duration(level)", "af.modifier = holy_sword_bonus()"],
        "spell_divine_power": ["af.duration = divine_power_duration(level)",
                               "af.modifier = divine_power_bonus(live_rolls)",
                               "GET_LEVEL(ch) > divine_power_health_above()"],
        "spell_atonement": ["af.duration = atonement_duration(level)", "af.modifier = atonement_regeneration(level)"],
        "spell_celestial_aura": ["af.duration = celestial_aura_duration()",
                                 "af.modifier = -celestial_aura_ac(live_rolls)",
                                 "af.modifier = celestial_aura_health(live_rolls)"],
    },
    "guild.c": {
        "notch_skill": ["learning_extra_notch_roll(live_rolls) && affected_by_spell(ch, SPELL_LEARNING)"],
        "spell_learning": ["af.duration = learning_duration(level)"],
    },
    "memorize.c": {
        "spell_mordenkainens_lucubration": ["lucubration_roll(live_rolls) < lucubration_chance()"],
    },
    "fight.c": {
        "update_dam_factors": ["dam_factor[DF_IRONWILL] = tower_iron_will_share()",
                               "dam_factor[DF_ENERGY_CONTAINMENT] = energy_containment_share()"],
        "melee_damage": ["(!displacement_absorb_roll(live_rolls))", "reduction = 1. - biofeedback_melee_share()",
                         "dam -= skin_spell_deduct()"],
        "check_vamp": ["dam > cannibalize_least_damage()", "can_mana = cannibalize_mana(dam, GET_LEVEL(ch))",
                       "can_mana = BOUNDED(0, GET_MANA(victim), can_mana)"],
        "calculate_thac_zero": ["to_hit = combat_mind_to_hit()"],
        "parrySucceed": ["learnedvictim += combat_mind_parry_skill(GET_LEVEL(victim))",
                         "learnedvictim += combat_mind_parry_bonus(GET_LEVEL(victim))"],
        "calculate_attacks": ["GET_LEVEL(ch) > combat_mind_second_attack_above()"],
        "perform_violence": ["attacksMultiplier = inertial_barrier_attack_share()",
                             "float cmMulti = combat_mind_attack_floor()"],
    },
    "actoff.c": {
        "takedown_check": ["displacement_takedown_chance(GET_LEVEL(ch)) >= displacement_takedown_roll(live_rolls)"],
    },
    "actoth.c": {
        "do_quaff": ["chance = combat_mind_quaff_chance(chance)"],
    },
    "sparser.c": {
        "do_will": ["AFF5_MEMORY_BLOCK) && memory_block_forget_roll(live_rolls)"],
        "do_cast": ["AFF5_MEMORY_BLOCK) && memory_block_forget_roll(live_rolls)"],
    },
}

HARNESS = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "magic/spells.h"
#include "abilities/abilities.h"
#include <algorithm>
#include <cassert>
#include <climits>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <functional>
#include <string>

void randomize(uint64_t seed);

static bool improved_wormhole;
bool has_innate(P_char, int innate) { return innate == INNATE_IMPROVED_WORMHOLE && improved_wormhole; }
// The properties differ from their fallbacks where a wrong key would otherwise pass.
float get_property(const char *key, double fallback)
{
    if (!std::strcmp(key, "spell.detonate.shrugModifier"))
        return 0.5f;
    if (!std::strcmp(key, "damage.reduction.towerOfIronWill"))
        return 0.75f;
    if (!std::strcmp(key, "damage.reduction.EnergyContainment"))
        return 0.6f;
    if (!std::strcmp(key, "damage.reduction.biofeedback"))
        return 0.45f;
    if (!std::strcmp(key, "attacks.inertialBarrier.multiplier"))
        return 0.4f;
    if (!std::strcmp(key, "attacks.combatMind.multiplier"))
        return 0.8f;
    return (float)fallback;
}
int get_property(const char *key, int fallback)
{
    if (!std::strcmp(key, "portals.wormhole.maxToPass"))
        return 4;
    if (!std::strcmp(key, "portals.wormhole.decayTimeout"))
        return 100;
    if (!std::strcmp(key, "damage.reduction.skinSpell.deduct"))
        return 40;
    if (!std::strcmp(key, "to.hit.WarriorTypes"))
        return 11;
    return fallback;
}

FUNCTIONS

// The next draw after a roll; equal fingerprints after equal seeds mean equal draw counts.
static int fingerprint() { return number(0, INT_MAX); }

static void same(const char *name, const std::function<int()> &original,
                 const std::function<int(const Rolls &)> &shared) {
    const int a = shared(lowest_rolls), b = shared(highest_rolls);
    for (uint64_t seed = 1; seed <= 40; ++seed) {
        randomize(seed);
        const int expected = original(), expected_next = fingerprint();
        randomize(seed);
        const int actual = shared(live_rolls), actual_next = fingerprint();
        if (actual != expected || actual_next != expected_next ||
            actual < std::min(a, b) || actual > std::max(a, b)) {
            std::fprintf(stderr, "%s: seed %d gave %d, expected %d in %d..%d\n", name,
                         (int)seed, actual, expected, a, b);
            std::abort();
        }
    }
}
#define SAME(original, shared) \
    same(#shared, [&] { return original; }, [&](const Rolls &rolls) { return shared; })

static bool contains(const std::string &text, const char *lines) {
    for (size_t at = text.find(lines); at != std::string::npos; at = text.find(lines, at + 1))
        if (at == 0 || text[at - 1] == '\n')
            return true;
    std::fprintf(stderr, "missing \"%s\" in:\n%s", lines, text.c_str());
    return false;
}

// Handler code before its numbers moved into shared functions.
static int clamp_level(int level) { return MAX(0, MIN(level, 60)); }
static const int agitation_each[61] = { 0,  0,  0,  0,  0,  12, 15, 18, 21, 24, 24, 24, 25, 25, 26, 26,
    26, 27, 27, 27, 28, 28, 28, 29, 29, 29, 30, 30, 30, 31, 31, 31, 32, 32, 32, 33, 33, 33, 34, 34, 34,
    35, 35, 35, 36, 36, 36, 37, 37, 37, 38, 38, 38, 38, 39, 39, 39, 39, 40, 40, 41 };
static const int whip_each[61] = { 0,  3,  4,  4,  5,  6,  6,  6,  7,  7,  7,  7,  7,  8,  8,  8,
    9,  9,  9,  10, 10, 10, 11, 11, 11, 12, 12, 12, 13, 13, 13, 14, 14, 14, 15, 15, 15, 16, 16, 16,
    17, 17, 17, 18, 18, 18, 19, 19, 19, 20, 20, 21, 21, 21, 22, 22, 22, 23, 23, 23, 24 };
static const int blast_each[61] = { 0,  0,  0,  0,  0,  0,  0,  0,  16, 20, 24, 28, 32, 35, 38, 40,
    42, 44, 45, 45, 45, 46, 46, 46, 47, 47, 47, 48, 48, 48, 49, 49, 49, 50, 50, 50, 51, 51, 51, 52,
    52, 52, 53, 53, 53, 54, 54, 54, 55, 55, 55, 56, 56, 56, 57, 57, 58, 58, 58, 59, 59 };
static int old_detonate(int level, P_char ch) {
    int dam = dice(MIN(level, 40) * 2, 8) + 60;
    dam += 2 * GET_DAMROLL(ch);
    return dam;
}
static int old_wormhole(P_char ch, int *decay_timer) {
    int specBonus = 0;
    int maxToPass = get_property("portals.wormhole.maxToPass", 3);
    *decay_timer = get_property("portals.wormhole.decayTimeout", 60 * 2);
    if (has_innate(ch, INNATE_IMPROVED_WORMHOLE)) {
        specBonus = 3;
        *decay_timer = (*decay_timer / 2) * 3;
    }
    return (int)((ch->player.level - 46) / 2) + number(1, maxToPass + specBonus);
}
static int old_awe_level(int level, P_char ch, int *max_total_levels) {
    int max_level = 0;
    *max_total_levels = (int)(GET_LEVEL(ch) * 2);
    if (IS_ILLITHID(ch)) {
        if (level > 51)
            max_level = level + 5;
        else if (level > 30)
            max_level = level;
        else if (level > 20)
            max_level = level - 4;
        else if (level > 15)
            max_level = level - 8;
        else
            max_level = 5;
        max_level = BOUNDED(5, max_level, 56);
    } else if (IS_TRUSTED(ch)) {
        *max_total_levels = 500;
        max_level = 65;
    } else {
        *max_total_levels = 110;
        max_level = BOUNDED(5, level - 10, 36);
    }
    return max_level;
}

struct Viewer { const char *name; uint m_class; int spec; int race; bool improved_wormhole; int damroll; };
static const Viewer viewers[] = {
    { "warrior", CLASS_WARRIOR, 0, RACE_HUMAN, false, 0 },
    { "psionicist", CLASS_PSIONICIST, 0, RACE_HUMAN, false, 0 },
    { "pyrokinetic", CLASS_PSIONICIST, SPEC_PYROKINETIC, RACE_HUMAN, false, 10 },
    { "enslaver", CLASS_PSIONICIST, SPEC_ENSLAVER, RACE_HUMAN, false, -200 },
    { "psycheporter", CLASS_PSIONICIST, SPEC_PSYCHEPORTER, RACE_HUMAN, true, 0 },
    { "mindflayer", CLASS_MINDFLAYER, 0, RACE_ILLITHID, true, 5 },
    { "githyanki", CLASS_PSIONICIST, 0, RACE_GITHYANKI, false, 0 },
    { "avenger", CLASS_AVENGER, 0, RACE_HUMAN, false, 0 },
};

static char_data viewer(const Viewer &v, int level) {
    char_data ch{};
    ch.player.m_class = v.m_class;
    ch.player.spec = v.spec;
    ch.player.race = v.race;
    ch.player.level = level;
    ch.points.damroll = v.damroll;
    improved_wormhole = v.improved_wormhole;
    return ch;
}

struct Page { const char *name; AbilityFacts facts; };
static const Page pages[] = {
PAGES
};

int main() {
    // Every page at every level for every kind of caster: no rolls, short lines.
    randomize(9);
    const int untouched = fingerprint();
    for (const Viewer &v : viewers)
        for (int level = 1; level <= 62; ++level)
            for (const Page &page : pages) {
                char_data ch = viewer(v, level);
                randomize(9);
                const std::string text = page.facts(&ch);
                assert(fingerprint() == untouched);
                assert(!text.empty() && text.back() == '\n');
                assert(text.find("--") == std::string::npos);
                size_t start = 0;
                for (size_t end; (end = text.find('\n', start)) != std::string::npos; start = end + 1)
                    if (end - start > 79 || text.compare(start, 2, "  ") != 0) {
                        std::fprintf(stderr, "%s, %s %d: bad line \"%s\"\n", page.name, v.name, level,
                                     text.substr(start, end - start).c_str());
                        return 1;
                    }
            }

    // Every converted roll draws exactly as its original expression did.
    for (const Viewer &v : viewers)
        for (int level : { 1, 10, 30, 50, 56, 60 }) {
            char_data caster = viewer(v, level);
            char_data target = viewer(viewers[0], 40);
            target.curr_stats.Pow = 90;
            caster.curr_stats.Pow = 120;
            P_char ch = &caster, victim = &target;
            const int at = clamp_level(level);
            SAME(number((agitation_each[at] / 2), (agitation_each[at] * 2)), molecular_agitation_damage(rolls, level));
            SAME(number(whip_each[at] / 2, whip_each[at] * 4), ballistic_attack_damage(rolls, level));
            SAME(number(whip_each[at] >> 1, whip_each[at] << 1), ego_whip_damage(rolls, level));
            SAME(number(blast_each[at] / 2, blast_each[at] * 2), control_flames_damage(rolls, level));
            SAME(number(blast_each[at] / 2, blast_each[at] * 2), ego_blast_damage(rolls, level));
            SAME((level / 2 + number(1, 4)), biofeedback_absorb(rolls, level));
            SAME(dice((int)(MIN(level, 51) * 3), 10), psychic_crush_damage(rolls, level));
            SAME(number(1, 100), psychic_crush_enslaver_roll(rolls));
            SAME(130 + level * 3 + number(1, 10), death_field_damage(rolls, level));
            SAME(old_detonate(level, ch), detonate_damage(rolls, level) + detonate_damroll_bonus(ch));
            SAME(number(1, 5), spinal_corruption_effect_roll(rolls));
            SAME(number(0, 1), memory_block_forget_roll(rolls));
            SAME(number(level / 4, 35), psionic_cloud_penalty(rolls, level));
            SAME(dice((int)(MIN(level, 31) * 1.5), 10), inflict_pain_damage(rolls, level));
            SAME(number(1, 10), confuse_effect_roll(rolls));
            SAME(number(1, 101), confuse_turn_roll(rolls));
            SAME(number(0, 100), awe_roll(rolls));
            SAME(number(0, 2), psionic_wave_blast_shrug_roll(rolls));
            SAME(number(1, 100), pyrokinesis_shrug_roll(rolls));
            SAME(dice(level * 2, 5), pyrokinesis_damage(rolls, level));
            SAME(dice(3, level / 2), celerity_vitality(rolls, level));
            SAME(dice(level, 4), psionic_wave_blast_damage(rolls, level));
            SAME(dice(level, 16), psionic_wave_blast_wave_damage(rolls, level));
            SAME((GET_C_POW(ch) - GET_C_POW(victim)) + number(-2, 2) * WAIT_SEC, enrage_attack(rolls, ch, victim));
            for (int attdiff : { WAIT_SEC, WAIT_SEC * 7, WAIT_SEC * 15 })
                SAME(number((2 * attdiff) / 3, (4 * attdiff) / 3), enrage_berserk(rolls, attdiff));
            int decay_timer = 0;
            SAME(std::max(1, old_wormhole(ch, &decay_timer)), wormhole_throughput(rolls, ch));
            assert(decay_timer == wormhole_decay_timer(ch));
            SAME(number(2, 5), divine_power_bonus(rolls));
            SAME(number(80, 150), celestial_aura_ac(rolls));
            SAME(number(50, 150), celestial_aura_health(rolls));
            SAME(number(0, 1), learning_extra_notch_roll(rolls));
            SAME(number(0, 100), lucubration_roll(rolls));
            SAME(number(0, 5), displacement_absorb_roll(rolls));
            SAME(number(1, 100), displacement_takedown_roll(rolls));
            SAME(number(1, 4), lend_health_short_roll(rolls));
            SAME(dice(2, 6), holy_sword_alignment_damage(rolls));
            caster.points.damnodice = 3;
            caster.points.damsizedice = 7;
            SAME(dice(ch->points.damnodice, ch->points.damsizedice), combat_mind_bare_hand_damage(rolls, ch));
        }

    // The fixed numbers against their pre-conversion expressions, at every level.
    for (int level = 1; level <= 62; ++level) {
        assert(molecular_control_duration(level) == level / 4);
        assert(adrenaline_control_duration(level) == level + 5);
        assert(combat_mind_duration(level) == level + 3 && combat_mind_hitroll(level) == level / 6 &&
               combat_mind_damroll(level) == level / 8);
        assert(psychic_crush_penalty(level) == (int)(-1 * (level / 2)));
        assert(displacement_duration(level) == level - 4 && displacement_ac(level) == -level * 2);
        assert(ectoplasmic_form_duration(level) == level / 2);
        assert(energy_containment_duration(level) == level / 2 + 7 && energy_containment_save(level) == -(level / 8));
        assert(enhance_armor_ac(level) == -1 * level && flesh_armor_ac(level) == (int)(-1 * level));
        assert(enhanced_strength_bonus(level) == 1 + (level / 4) && enhanced_dexterity_bonus(level) == 1 + (level / 4) &&
               enhanced_agility_bonus(level) == 1 + (level / 4) && enhanced_constitution_bonus(level) == 1 + (level / 5));
        assert(enhanced_strength_duration(level) == level && enhanced_dexterity_duration(level) == level &&
               enhanced_agility_duration(level) == level && enhanced_constitution_duration(level) == level);
        assert(intellect_fortress_intelligence(level) == 1 + level / 5);
        assert(pyrokinesis_penalty(level) == (int)(-1 * (level / 5)));
        assert(mind_blank_duration(level) == level * 2 * WAIT_SEC);
        assert(cannibalize_duration(level) == level);
        assert(tower_iron_will_duration(level) == level / 2);
        assert(thought_beacon_duration(level) == level * 4 * WAIT_MIN);
        assert(holy_sword_duration(level) == level / 2 && divine_power_duration(level) == level / 2);
        assert(atonement_duration(level) == level / 2 && atonement_regeneration(level) == level * 2);
        assert(learning_duration(level) == 2 * level);
        assert(confuse_target_levels(level) == level * 3);
        assert(displacement_takedown_chance(level) == (5 + level / 10));
        assert(combat_mind_parry_skill(level) == level && combat_mind_parry_bonus(level) == (int)(level / 2));
        for (int dam : { 0, 2, 3, 10, 11, 57, 100, 101, 1000, INT_MAX }) {
            double can_mana = MAX(10, dam);
            can_mana = BOUNDED(0, can_mana, 100);
            can_mana *= level / 30.;
            assert(cannibalize_mana(dam, level) == can_mana);
        }
        // Awe's one chain, old against new, for every kind of caster at every level. Level 57
        // and up is trusted: its branch is the one the fixed levels above barely reach.
        for (const Viewer &v : viewers) {
            char_data caster = viewer(v, level);
            P_char awe_caster = &caster;
            int old_total = 0, new_total = 0;
            const int old_max = old_awe_level(level, awe_caster, &old_total);
            assert(old_max == awe_limits(level, awe_caster, &new_total) && old_total == new_total);
            assert(IS_ILLITHID(awe_caster) || !IS_TRUSTED(awe_caster) || (new_total == 500 && old_max == 65));
        }
        char_data ch = viewer(viewers[1], level);
        // Below 57 the old if-chain's "< 57" branch took every level.
        assert(inertial_barrier_duration() == 30);
        assert(mental_anguish_duration(&ch) == WAIT_SEC * (level / 2));
        assert(radial_navigation_range(&ch) == level + 10);
        assert(lend_health_most(&ch) == 25 + level * 3 / 2);
    }

    assert(combat_mind_quaff_chance(50) == (int)(50 * 1.25));
    assert(cannibalize_least_damage() == 2 && combat_mind_second_attack_above() == 51);

    // Exact pages at level 56.
    char_data ch = viewer(viewers[1], 56);
    assert(molecular_control_facts(&ch) ==
           "  Duration: 14-15 game hours (17.5-18.75 minutes) at your level, 56\n"
           "  You can walk through closed doors, except locked pickproof ones.\n"
           "  Casting it again renews the duration.\n");
    assert(molecular_agitation_facts(&ch) ==
           "  Psionic damage: 19-78 at your level, 56\n"
           "  If the target makes a power save: 12-52\n"
           "  Globes and spirit wards do not stop it.\n"
           "  Spell damage modifiers and the target's defenses apply after.\n");
    assert(adrenaline_control_facts(&ch) ==
           "  Duration: 61-62 game hours (76.25-77.5 minutes) at your level, 56\n"
           "  Strength: +15\n  Constitution: +15\n"
           "  It has no effect while you already have it.\n");
    assert(aura_sight_facts(&ch) ==
           "  Duration: 36-37 game hours (45-46.25 minutes)\n"
           "  It shows magic at any level.\n"
           "  Detect good and evil: above level 20\n  Sense life: above level 25\n"
           "  Detect invisibility: above level 36\n  Farsee: above level 41\n"
           "  Casting it again renews the duration.\n");
    assert(contains(awe_facts(&ch),
                    "  Highest target level: 36 at your level, 56\n"
                    "  Target plus charmed followers: below 110 total levels\n"
                    "  Refused at: 5 charmed followers\n"
                    "  Chance threshold: 5-95 on a roll of 0-100, from your power and level\n"
                    "    against the target's intelligence and level.\n"));
    assert(contains(ballistic_attack_facts(&ch),
                    "  Damage: 11-88 at your level, 56\n"
                    "  If the target fails a dexterity save: 22-176\n"
                    "  Globes, minor globes and spirit wards stop it.\n"));
    assert(biofeedback_facts(&ch) ==
           "  Hits absorbed: 29-32 at your level, 56\n"
           "  Each melee hit on you: 40 less\n"
           "  Then, if over 10 is left: 45% of that\n"
           "  It applies before the raw damage modifiers.\n"
           "  Hits that ignore reductions go through it and use up nothing.\n"
           "  An attacker's fist of dragon can do the same.\n"
           "  Duration: 6-7 game hours (7.5-8.75 minutes)\n"
           "  It has no effect while you have any skin spell.\n");
    assert(contains(cannibalize_facts(&ch),
                    "  Duration: 56-57 game hours (70-71.25 minutes) at your level, 56\n"
                    "  Casting it again renews the full duration.\n"
                    "  Mana you take per hit: 18-186\n"
                    "  It rises with the damage dealt, and is taken after the damage lands.\n"
                    "  A hit must deal more than: 2\n"
                    "  It never takes more than the target has, or past your maximum.\n"));
    assert(contains(celerity_facts(&ch), "  Movement restored: 3-84 at your level, 56\n"
                                         "  Psionic damage to yourself: 12-336\n"));
    assert(cell_adjustment_facts(&ch) ==
           "  Cures poison: above level 2\n  Removes curses: above level 9\n"
           "  Cures blindness: above level 29\n  Removes wither: above level 50\n"
           "  Cures disease: above level 55\n");
    assert(contains(combat_mind_facts(&ch),
                    "  Duration: 59-60 game hours (73.75-75 minutes) at your level, 56\n"
                    "  Hitroll: +9\n  Damroll: +7\n"
                    "  To-hit rate: 11, the warrior rate\n"
                    "  When something cuts your melee attacks, you keep at least: 80%\n"
                    "  Chance not to spill a potion in combat: 125% of normal\n"
                    "  Your hits ignore displacement's absorption, and you never fumble.\n"
                    "  A berserker's mangle cannot disarm you.\n"
                    "  Improving your parry skill no longer costs you that parry.\n"
                    "  As a psionicist, parry rating: +84\n"
                    "  Extra main weapon attacks: 2\n"
                    "  Bare-handed damage before your bonuses: 1\n"
                    "  Casting it again renews the duration.\n"));
    assert(contains(confuse_facts(&ch),
                    "  Stops after reaching target levels totalling: 168 at your level, 56\n"
                    "  A target that fails its power save suffers one of these:\n"
                    "  Stunned: 3 in 10, up to 8 seconds; fear saves shorten or stop it\n"
                    "  Stops fighting, and a player flees: 3 in 10\n"
                    "  Nothing: 2 in 10\n"
                    "  A player may turn on someone in the room: 2 in 10\n"
                    "  Chance for each person there, until one is picked: 30 in 101\n"
                    "  Elites cannot be stunned. Greater races, plants, golems and constructs\n"
                    "  may resist a stun, more often the higher their level.\n"));
    assert(confuse_facts(&ch).find("githyanki") == std::string::npos);
    assert(contains(control_flames_facts(&ch),
                    "  Damage: 29-116 at your level, 56\n"
                    "  If the target makes a power save: 14-58\n"
                    "  The target must be carrying a torch.\n"
                    "  Globes and spirit wards stop it; minor globes do not.\n"));
    assert(contains(ego_blast_facts(&ch), "  Damage: 29-116 at your level, 56\n"
                                          "  If the target makes a power save: 14-58\n"
                                          "  Globes and spirit wards stop it; minor globes do not.\n"));
    assert(contains(death_field_facts(&ch),
                    "  Psionic damage to each target hit: 299-308 at your level, 56\n"
                    "  Against a player: 149-154\n"
                    "  Cast within 5 seconds of yours or your group's here: level 28\n"
                    "    That is 215-224 before the adjustment against a player.\n"
                    "  An area cast can skip some of the players in the room.\n"
                    "  Your lag: 2 seconds\n"));
    assert(contains(depart_facts(&ch), "  Distance on the map: up to 5 rooms\n"
                                       "  Off the map it takes you to a random room in the zone.\n"
                                       "  Your lag if it works: 3 seconds\n"
                                       "  Fails in no-teleport rooms, hometowns and oceans: below level 60\n"
                                       "  Fizzles in rooms 5700-5999 if the landing is farther than: 5 rooms\n"
                                       "  It fails if you are not raidable.\n"));
    assert(contains(detonate_facts(&ch),
                    "  Psionic damage: 140-700 at your level, 56\n"
                    "  It includes twice your damroll.\n"
                    "  If the target saves or is elite: 70-350\n"
                    "  Against golems and plants: 280-1400, before a save\n"
                    "  A target's shrug stops it.\n"));
    assert(contains(displacement_facts(&ch),
                    "  Duration: 52-53 game hours (65-66.25 minutes) at your level, 56\n"
                    "  Armor class: -112\n"
                    "  Chance a melee hit on you deals nothing: 1 in 6\n"
                    "  Combat mind, and hits that ignore reductions, get through.\n"
                    "  Chance to dodge a takedown: 5 in 100, +1 per 10 levels of the attacker\n"
                    "  It has no effect while you already have it.\n"));
    assert(contains(ectoplasmic_form_facts(&ch),
                    "  Duration: 28-29 game hours (35-36.25 minutes) at your level, 56\n"));
    assert(contains(ego_whip_facts(&ch), "  Damage: 11-44 at your level, 56\n"
                                         "  If the target makes a power save: 7-29\n"
                                         "  With tower of iron will: half of either, 3-22\n"));
    assert(contains(energy_containment_facts(&ch),
                    "  Duration: 35-36 game hours (43.75-45 minutes) at your level, 56\n"
                    "  Saving throw against spells: -7\n"
                    "  Fire, cold, lightning, gas, acid and earth damage you take: 60%\n"
                    "  That is one of the spell damage modifiers.\n"
                    "  Casting it again renews the duration.\n"));
    assert(contains(enhance_armor_facts(&ch), "  Armor class: -56 at your level, 56\n"
                                              "  Duration: 25-26 game hours (31.25-32.5 minutes)\n"));
    assert(contains(enhanced_strength_facts(&ch), "  Strength: +15 at your level, 56\n"
                                                  "  Duration: 56-57 game hours (70-71.25 minutes)\n"));
    assert(contains(enhanced_dexterity_facts(&ch), "  Dexterity: +15 at your level, 56\n"));
    assert(contains(enhanced_agility_facts(&ch), "  Agility: +15 at your level, 56\n"));
    assert(contains(enhanced_constitution_facts(&ch), "  Constitution: +12 at your level, 56\n"));
    assert(enrage_facts(&ch).rfind("  Berserk: 0.5 seconds to 20 seconds\n", 0) == 0);
    assert(ethereal_rift_facts(&ch) ==
           "  Your lag: 1 second\n"
           "  It takes you to a random room in the target's zone.\n"
           "  In a private, no-teleport, hometown or ocean room, yours or the target's,\n"
           "  it leaves you where you are.\n"
           "  It cannot target an NPC.\n");
    assert(contains(ether_warp_facts(&ch), "  Your lag: 7 seconds\n  You cannot warp to an NPC.\n"));
    assert(contains(excogitate_facts(&ch),
                    "  Your power minus the target's splits the report at: -20, -10, 10, 20 and 30\n"
                    "  A target notices unless your power beats it by 10 or more.\n"));
    assert(contains(fire_aura_facts(&ch),
                    "  Duration: 30-31 game hours (37.5-38.75 minutes)\n"
                    "  Armor class: -15\n  Maximum strength: +15\n  Maximum dexterity: -20\n"
                    "  Maximum agility: -20\n  Maximum constitution: +25\n"
                    "  Fear save for the full form: +4, worse\n"));
    assert(contains(flesh_armor_facts(&ch), "  Armor class: -56 at your level, 56\n"
                                            "  Duration: 25-26 game hours (31.25-32.5 minutes)\n"));
    assert(inertial_barrier_facts(&ch) ==
           "  Duration: 30-31 game hours (37.5-38.75 minutes)\n"
           "  Melee attacks against you: 40% of normal, rounded up, before any hit rolls\n"
           "  An attacker with combat mind keeps at least: 80%\n"
           "  Casting it again renews the duration.\n");
    assert(contains(inflict_pain_facts(&ch),
                    "  Psionic damage: 46-460 at your level, 56\n"
                    "  If the target makes a power save: 30-306\n"
                    "  It cannot kill. A globe of invulnerability stops it.\n"));
    assert(contains(intellect_fortress_facts(&ch),
                    "  Intelligence: +12 at your level, 56\n"
                    "  Duration: 24-25 game hours (30-31.25 minutes)\n"));
    assert(contains(lend_health_facts(&ch),
                    "  Healing: up to 50 at your level, 56\n"
                    "  Your health spent: up to 50\n"
                    "  Never more than the target is missing. Healing modifiers apply.\n"
                    "  The target stops short of full health by: 1-4\n"
                    "  Refused if it would leave you below: -9 health\n"));
    assert(memory_block_facts(&ch) == "  Duration: 28 seconds\n"
                                      "  Chance each cast fails: 1 in 2\n"
                                      "  A target that makes its power save is unaffected.\n");
    assert(contains(mental_anguish_facts(&ch), "  Duration: 28 seconds at your level, 56\n"));
    assert(contains(mind_blank_facts(&ch),
                    "  Hidden from detection for: 1 minute 52 seconds at your level, 56\n"
                    "  You cannot cast it again for: 15-16 game hours (18.75-20 minutes)\n"));
    assert(contains(mind_travel_facts(&ch), "  Your lag on arriving: 1.25 seconds\n"));
    assert(contains(psionic_cloud_facts(&ch), "  Power: -35 to -14 at your level, 56\n"
                                              "  Movement: -35 to -14\n"
                                              "  Duration: 56-57 game hours (70-71.25 minutes)\n"));
    assert(contains(psionic_wave_blast_facts(&ch),
                    "  First psionic hit: 56-224 at your level, 56; it cannot kill\n"
                    "  Waves after it: up to 6, 4 seconds apart\n"
                    "  Damage per wave: 56-896\n"
                    "  If the target fails its power save: 70-1120\n"
                    "  If the target has left your room: a third, 18-298\n"
                    "  Mana per continuing wave: 50\n"
                    "  Chance a target may try to shrug the first hit: 1 in 3\n"
                    "  Chance it may try to shrug a wave: 1 in 3\n"
                    "  This gates the shrug attempt; it does not change the target's shrug rating.\n"
                    "  A shrug of the first hit ends it; a shrugged wave still costs mana.\n"
                    "  Waves need the target to survive what came before.\n"
                    "  The target must be at full health when you cast it.\n"
                    "  Being stunned or off your feet interrupts the waves.\n"
                    "  Globes and spirit wards do not stop it.\n"));
    assert(contains(psychic_crush_facts(&ch),
                    "  Psionic damage: 153-1530 at your level, 56\n"
                    "  If the target makes a power save: 76-765\n"
                    "  An elite target always takes the lower amount.\n"));
    assert(contains(psychic_crush_facts(&ch),
                    "  Penalty: -28 to power, intelligence or wisdom, at random\n"
                    "  Penalty duration: 3.75 seconds\n"));
    assert(psychic_crush_facts(&ch).find("Enslaver") == std::string::npos);
    assert(contains(pyrokinesis_facts(&ch),
                    "  Psionic damage: 112-560 at your level, 56\n"
                    "  If the target fails its save: 134-672\n"
                    "  Fire damage first, on an NPC only: 112-560, and it cannot kill\n"
                    "  If the NPC fails its save: 128-644\n"
                    "  Chance a target may try to shrug it: 59 in 100\n"));
    assert(contains(pyrokinesis_facts(&ch),
                    "  A shrug stops all of it, and neither the penalty nor your lag applies.\n"
                    "  Globes and spirit wards do not stop it.\n"
                    "  Penalty if it survives: -11 to agility, dexterity or strength, at random\n"
                    "  Penalty duration: 1-2 game hours (1.25-2.5 minutes)\n"
                    "  A target already under the penalty does not get another.\n"
                    "  Your lag if the target survives: 2 seconds\n"));
    assert(contains(radial_navigation_facts(&ch),
                    "  Range: 66 rooms at your level, 56\n"
                    "  Mana per room asked for: 12\n"
                    "  You pay it even if the jaunt fails.\n"
                    "  Your lag: 2.5 seconds\n"
                    "  Knocked out below 0 mana: 37.5 seconds per 100 mana below\n"));
    assert(contains(spinal_corruption_facts(&ch), "  Chance of each effect: 1 in 5\n"
                                                  "  Lag on the target: 3 seconds\n"));
    assert(contains(spinal_corruption_facts(&ch), "  Slowness if not already under it: 3-4 game hours (3.75-5 minutes)\n"));
    assert(contains(thought_beacon_facts(&ch),
                    "  Beacon lasts: 224 minutes at your level, 56\n"
                    "  Your link to it: 224 minutes\n"));
    assert(tower_iron_will_facts(&ch) ==
           "  Duration: 28-29 game hours (35-36.25 minutes) at your level, 56\n"
           "  Psionic damage you take: 75% of normal\n"
           "  That is one of the spell damage modifiers.\n"
           "  Casting it again renews the duration.\n");
    // The test's wormhole properties: 4 to pass, 100 pulses to decay.
    assert(contains(wormhole_facts(&ch),
                    "  Can pass each way: 6-9 at your level, 56\n"
                    "  Portal lasts: up to 25 seconds\n"
                    "  Cast on yourself, it opens to your thought beacon.\n"
                    "  It can only reach another player.\n"
                    "  It fails from or to a no-teleport room or hometown, from an ocean,\n"
                    "  and to a single-file or no-magic room.\n"));
    assert(contains(atonement_facts(&ch),
                    "  Duration: 28-29 game hours (35-36.25 minutes) at your level, 56\n"
                    "  Health regeneration: +112\n"));
    assert(contains(celestial_aura_facts(&ch),
                    "  Armor class: -150 to -80\n  Hit points: +50 to +150\n"
                    "  Duration: 4-5 game hours (5-6.25 minutes)\n"));
    assert(contains(divine_power_facts(&ch),
                    "  Duration: 28-29 game hours (35-36.25 minutes) at your level, 56\n"
                    "  Hitroll: +2 to +5\n  Maximum strength: +2 to +5\n  Hit points: +56\n"));
    assert(contains(holy_sword_facts(&ch),
                    "  Duration: 28-29 game hours (35-36.25 minutes) at your level, 56\n"
                    "  Hitroll: +5\n  Damroll: +5\n"
                    "  Added to damage against the opposite alignment: 2-12\n"
                    "  It is added before other damage multipliers.\n"
                    "  It also gives you an extra attack with your main weapon.\n"
                    "  Removing your main weapon or being disarmed ends it.\n"));
    assert(contains(learning_facts(&ch),
                    "  Duration: 112-113 game hours (140-141.25 minutes) at your level, 56\n"
                    "  Chance of another notch after each skill notch: 1 in 2\n"));
    assert(contains(mordenkainens_lucubration_facts(&ch),
                    "  Chance to regain each spent spell or slot: 80 in 101\n"
                    "  Among memorized spells, it does not regain itself.\n"
                    "  Slot casters regain only circles below their highest.\n"));

    // Level boundaries.
    ch = viewer(viewers[1], 1);
    assert(contains(molecular_agitation_facts(&ch), "  Psionic damage: 0 (none below 1 lands) at your level, 1\n"
                                                    "  If the target makes a power save: 0 (none below 1 lands)\n"));
    assert(contains(ego_blast_facts(&ch), "  Damage: 0 (none below 1 lands) at your level, 1\n"));
    assert(contains(ego_whip_facts(&ch), "  Damage: 1-6 at your level, 1\n"
                                         "  If the target makes a power save: 0-4 (none below 1 lands)\n"));
    assert(contains(awe_facts(&ch), "  Highest target level: 5 at your level, 1\n"));
    // A modifier of nothing is not a line.
    assert(psychic_crush_facts(&ch).find("Penalty") == std::string::npos);
    assert(pyrokinesis_facts(&ch).find("Penalty") == std::string::npos);
    assert(combat_mind_facts(&ch).find("roll") == std::string::npos);
    assert(energy_containment_facts(&ch).find("Saving") == std::string::npos);
    assert(contains(celerity_facts(&ch), "  Movement restored: 3 at your level, 1\n"
                                         "  Psionic damage to yourself: 12\n"));
    assert(contains(displacement_facts(&ch), "  Duration: up to 1 game hour (up to 1.25 minutes) at your level, 1\n"));
    assert(contains(divine_power_facts(&ch), "  Hit points: above level 49\n"));
    assert(contains(mental_anguish_facts(&ch), "  Duration: 0 seconds at your level, 1\n"));
    assert(contains(thought_beacon_facts(&ch), "  Beacon lasts: 4 minutes at your level, 1\n"
                                               "  Your link to it: 4 minutes\n"));
    assert(contains(wormhole_facts(&ch), "  Can pass each way: 1 at your level, 1\n"));
    assert(contains(cannibalize_facts(&ch), "  Mana you take per hit: 0-3\n"));
    assert(contains(combat_mind_facts(&ch), "  Extra main weapon attacks: 1, or 2 above level 51\n"));
    ch = viewer(viewers[1], 51);
    assert(contains(combat_mind_facts(&ch), "  Extra main weapon attacks: 1, or 2 above level 51\n"));
    ch = viewer(viewers[1], 52);
    assert(contains(combat_mind_facts(&ch), "  Extra main weapon attacks: 2\n"));
    ch.points.damnodice = 3;
    ch.points.damsizedice = 7;
    assert(contains(combat_mind_facts(&ch), "  Bare-handed damage before your bonuses: 3-21\n"));
    ch = viewer(viewers[0], 56); // a warrior gets the common lines only
    assert(contains(combat_mind_facts(&ch), "  Improving your parry skill no longer costs you that parry.\n"
                                            "  Casting it again renews the duration.\n"));
    assert(combat_mind_facts(&ch).find("psionicist") == std::string::npos);
    ch = viewer(viewers[1], 3);
    assert(contains(displacement_facts(&ch), "  Duration: permanent at your level, 3\n"));
    ch = viewer(viewers[1], 44);
    assert(contains(wormhole_facts(&ch), "  Can pass each way: 1-3"
                                         " at your level, 44\n"));
    ch = viewer(viewers[1], 49);
    assert(contains(divine_power_facts(&ch), "  Hit points: above level 49\n"));
    ch = viewer(viewers[1], 50);
    assert(contains(divine_power_facts(&ch), "  Hit points: +50\n"));
    ch = viewer(viewers[1], 57);
    assert(contains(inertial_barrier_facts(&ch), "  Duration: 30-31 game hours (37.5-38.75 minutes)\n"));
    assert(contains(awe_facts(&ch), "  Highest target level: 65 at your level, 57\n"
                                    "  Target plus charmed followers: below 500 total levels\n"
                                    "  Chance threshold: "));
    assert(wormhole_facts(&ch).find("no-teleport") == std::string::npos);

    // The specializations, races and innates the pages read.
    ch = viewer(viewers[2], 56); // pyrokinetic with +10 damroll
    assert(contains(detonate_facts(&ch),
                    "  Psionic damage: 160-720 at your level, 56\n"
                    "  It includes twice your damroll.\n"
                    "  If the target saves or is elite: 80-360\n"
                    "  Against golems and plants: 320-1440, before a save\n"
                    "  A shrug leaves 80-360 instead of stopping it.\n"));
    assert(contains(pyrokinesis_facts(&ch),
                    "  Fire damage first, on an NPC only: 134-672, and it cannot kill\n"
                    "  If the NPC fails its save: 154-772\n"));
    ch = viewer(viewers[3], 56); // enslaver with -200 damroll
    assert(contains(detonate_facts(&ch),
                    "  Psionic damage: 0-300 (none below 1 lands) at your level, 56\n"
                    "  It includes twice your damroll.\n"
                    "  If the target saves or is elite: 0-150 (none below 1 lands)\n"));
    assert(contains(death_field_facts(&ch),
                    "  Psionic damage to each target hit: 598-616 at your level, 56\n"
                    "  Against a player: 299-308\n"));
    assert(contains(psychic_crush_facts(&ch),
                    "  Enslaver stun: 9 in 100, up to 4 seconds; fear saves shorten or stop it\n"
                    "  Enslaver knockdown to the knees: 5 in 100\n"
                    "  Both need the target to survive the hit.\n"
                    "  Elites, zombies, golems, dragons and plants are immune to both.\n"
                    "  Other greater races and constructs may resist the stun, more often\n"
                    "  the higher their level.\n"));
    ch = viewer(viewers[4], 56); // psycheporter with improved wormhole
    assert(contains(ether_warp_facts(&ch), "  Your lag: none, as a psycheporter\n"
                                           "  Range to an NPC: 75 rooms at your level, 56\n"));
    assert(contains(wormhole_facts(&ch),
                    "  Can pass each way: 6-12 at your level, 56\n"
                    "  Portal lasts: up to 37.5 seconds\n"
                    "  Cast on yourself, it opens to your thought beacon.\n"
                    "  Range to an NPC: 75 rooms\n"
                    "  It cannot reach an NPC that cannot be summoned.\n"));
    ch = viewer(viewers[5], 56); // illithid mindflayer with +5 damroll
    assert(contains(awe_facts(&ch), "  Highest target level: 56 at your level, 56\n"
                                    "  Target plus charmed followers: below 112 total levels\n"));
    assert(contains(detonate_facts(&ch),
                    "  Psionic damage: 318-878 at your level, 56\n"
                    "  It includes twice your damroll.\n"
                    "  If the target saves or is elite: 159-439\n"
                    "  Against golems and plants: 636-1756, before a save\n"
                    "  An NPC's shrug leaves 286-790; a player's stops it.\n"));
    assert(contains(ether_warp_facts(&ch),
                    "  Your lag: 7 seconds\n"
                    "  Range to an NPC: 75 rooms at your level, 56\n"
                    "  Warping to a non-illithid player below level 51: refused\n"
                    "  Your lag for trying: 22.5 seconds\n"));
    assert(contains(wormhole_facts(&ch), "  To a non-illithid player below level 51: refused\n"
                                         "  Your lag for trying: 22.5 seconds\n"));
    ch = viewer(viewers[6], 56); // githyanki
    assert(contains(confuse_facts(&ch), "  Extra mana for a githyanki: 50\n"));
    puts("PASS: batch 6 shared rolls match the old code and stay in range, facts never roll");
}
'''


# Multi-path handlers: each helper must sit in its own branch, in the original order.
BRANCHES = {
    "psionics.c": {
        "spell_confuse": [r"confuse_turn_roll\(live_rolls\) <=\s*confuse_turn_limit\(\)"],
        "spell_aura_sight": [r"aura_sight_alignment_above\(\)\)\s*\{\s*af\.bitvector2 = AFF2_DETECT_GOOD",
                             r"aura_sight_life_above\(\)\)\s*\{\s*af\.bitvector = AFF_SENSE_LIFE",
                             r"aura_sight_invisible_above\(\)\)\s*\{\s*af\.bitvector = AFF_DETECT_INVISIBLE",
                             r"aura_sight_farsee_above\(\)\)\s*\{\s*af\.bitvector = AFF_FARSEE"],
        "spell_cell_adjustment": [r"poison_above\(\)\)\s*poison = TRUE", r"curse_above\(\)\)\s*curse = TRUE",
                                  r"blindness_above\(\)\)\s*blind = TRUE", r"wither_above\(\)\)\s*wither = TRUE",
                                  r"disease_above\(\)\)\s*disease = TRUE"],
        "spell_combat_mind": [r"combat_mind_hitroll\(level\);[^;]*;\s*af\.location = APPLY_HITROLL",
                              r"combat_mind_damroll\(level\);\s*af\.location = APPLY_DAMROLL"],
        "spell_fire_aura": [r"APPLY_AC;\s*af\.modifier = fire_aura_ac\(\)",
                            r"APPLY_STR_MAX;\s*af\.modifier = fire_aura_str_max\(\)",
                            r"APPLY_DEX_MAX;\s*af\.modifier = fire_aura_nimbleness\(\)",
                            r"APPLY_AGI_MAX;\s*af\.modifier = fire_aura_nimbleness\(\)",
                            r"APPLY_CON_MAX;\s*af\.modifier = fire_aura_con_max\(\)"],
        "spell_psychic_crush": [r"!IS_ELITE\(victim\)\)\s*\{\s*if \(\(spell_damage\(ch, victim, dam, SPLDAM_PSI",
                                r"else\s*\{\s*if \(\(spell_damage\(ch, victim, psychic_crush_saved\(dam\)",
                                r"spec_affect < psychic_crush_stun_below\(\)\)\s*\{\s*Stun\(victim, ch, psychic_crush_stun\(\)",
                                r"SPEC_ENSLAVER\).*psychic_crush_enslaver_roll\(live_rolls\)"],
        "spell_detonate": [r"SPEC_PYROKINETIC\)\)\s*\{\s*dam = detonate_pyrokinetic_shrug",
                           r"CLASS_MINDFLAYER\) && IS_NPC\(victim\)\)\s*\{\s*dam = detonate_mindflayer_shrug",
                           r"CLASS_MINDFLAYER\)\)\s*\{\s*dam \+= detonate_mindflayer_bonus",
                           r"RACE_PLANT\)\s*\{\s*dam = detonate_construct_damage",
                           r"else\s*\{\s*spell_damage\(ch, victim, detonate_saved\(dam\)"],
        "spell_pyrokinesis": [r"phys_dam = pyrokinesis_damage\(live_rolls, level\);\s*int fire_dam = pyrokinesis_damage",
                              r"SPEC_PYROKINETIC\)\)\s*fire_dam = pyrokinesis_pyrokinetic_fire",
                              r"!NewSaves\(victim, SAVING_SPELL, mod\)\)\s*\{\s*phys_dam = pyrokinesis_failed_psionic\(phys_dam\);\s*fire_dam = pyrokinesis_failed_fire\(fire_dam\)",
                              r"affect_to_char\(victim, &af\);\s*\}\s*CharWait\(ch, pyrokinesis_lag\(\)\)"],
        "spell_ego_whip": [r"POW_DIFF\(ch, victim\)\)\)\s*dam = ego_whip_saved\(dam\)",
                           r"AFF3_TOWER_IRON_WILL\)\)\s*dam = ego_whip_iron_will\(dam\)"],
        "event_psionic_wave_blast": [r"!psionic_wave_blast_shrug_roll\(live_rolls\) && resists_spell",
                                     r"POW_DIFF\(ch, victim\)\)\)\s*dam = psionic_wave_blast_failed_save\(dam\)",
                                     r"victim->in_room\)\s*dam = psionic_wave_blast_away\(dam\)"],
        "spell_psionic_wave_blast": [r"dam = psionic_wave_blast_damage\(live_rolls, level\);\s*if \(!psionic_wave_blast_shrug_roll\(live_rolls\) && resists_spell"],
        "spell_ether_warp": [r"SPEC_PSYCHEPORTER\)\)\s*\{.*?\}\s*else\s*\{\s*CharWait\(ch, ether_warp_lag\(\)\)"],
        "spell_cannibalize": [r"SPELL_CANNIBALIZE\)\s*\{\s*af1->duration = cannibalize_duration\(level\)"],
    },
    "avengers.c": {
        "spell_holy_sword": [r"APPLY_DAMROLL;\s*af\.modifier = holy_sword_bonus\(\)",
                             r"APPLY_HITROLL;\s*af\.modifier = holy_sword_bonus\(\)"],
        "spell_divine_power": [r"int healpoints = divine_power_health\(level\)",
                               r"APPLY_HITROLL;\s*af\.modifier = divine_power_bonus\(live_rolls\)",
                               r"APPLY_STR_MAX;\s*af\.modifier = divine_power_bonus\(live_rolls\)",
                               r"divine_power_health_above\(\)\)\s*\{\s*af\.location = APPLY_HIT;\s*af\.modifier = healpoints"],
        "spell_celestial_aura": [r"APPLY_AC;\s*af\.modifier = -celestial_aura_ac\(live_rolls\)",
                                 r"APPLY_HIT;\s*af\.modifier = celestial_aura_health\(live_rolls\)"],
    },
}


# Numbers read through the code that uses them, in other files.
SHARED_ELSEWHERE = [
    ("fight.c", "float tower_iron_will_share("), ("fight.c", "float energy_containment_share("),
    ("fight.c", "int displacement_absorb_roll("), ("fight.c", "float biofeedback_melee_share("),
    ("fight.c", "int skin_spell_deduct("), ("fight.c", "int combat_mind_bare_hand_damage("),
    ("fight.c", "float inertial_barrier_attack_share("), ("fight.c", "float combat_mind_attack_floor("),
    ("fight.c", "int cannibalize_least_damage("), ("fight.c", "double cannibalize_mana("),
    ("fight.c", "int combat_mind_to_hit("), ("fight.c", "int combat_mind_parry_skill("),
    ("fight.c", "int combat_mind_parry_bonus("), ("fight.c", "int combat_mind_second_attack_above("),
    ("actoff.c", "int displacement_takedown_chance("), ("actoff.c", "int displacement_takedown_roll("),
    ("actoth.c", "int combat_mind_quaff_chance("), ("dam_mods.c", "int holy_sword_alignment_damage("),
]


def shared_functions(file, text, prefixes):
    names = [name for name in re.findall(r"^(?:static )?[\w:]+ (\w+)\(", text, re.M)
             if name.startswith(prefixes) and not name.endswith("_facts")]
    found = []
    for name in names:
        match = re.search(rf"^(?:static )?[\w:]+ {name}\(", text, re.M)
        found.append(extract_function(file, match.group(0)))
    return found


def check_sources():
    for file, handlers in HANDLER_CALLS.items():
        code = strip_comments(source(file).read_text())
        for handler, calls in handlers.items():
            bodies = function_bodies(code, rf"\b(?:void|bool|int|float)\s+{handler}\s*\(")
            assert len(bodies) == 1, handler
            for call in calls:
                assert call in bodies[0], f"{handler} does not call {call}"
    for file, handlers in BRANCHES.items():
        code = strip_comments(source(file).read_text())
        for handler, patterns in handlers.items():
            body = function_bodies(code, rf"\bvoid\s+{handler}\s*\(")[0]
            for pattern in patterns:
                assert re.search(pattern, body, re.S), f"{handler}: {pattern}"
    # Every shared roll has an oracle in the harness.
    for text in (PSIONICS, AVENGERS, GUILD, MEMORIZE):
        for name in re.findall(r"^(?:static )?int (\w+)\(const Rolls &rolls", text, re.M):
            # Holy smite's rolls came in a later batch, and have their oracles in its test.
            if name in ("holy_smite_damage", "holy_smite_blind_duration"):
                assert re.search(rf"SAME\(.*\b{name}\(rolls", (ROOT / "tests/async/test_ability_skills_4.py").read_text()), name
                continue
            # Innate blast's rolls came with the innates, and have their oracles in that test.
            if name.startswith("innate_blast_"):
                assert re.search(rf"SAME\(.*\b{name}\(rolls", (ROOT / "tests/async/test_ability_innates_1.py").read_text()), name
                continue
            assert re.search(rf"SAME\(.*\b{name}\(rolls", HARNESS), f"{name} has no oracle"
    for file, signature in SHARED_ELSEWHERE:
        if "const Rolls" in source(file).read_text().split(signature)[1].split(")")[0]:
            assert re.search(rf"SAME\(.*\b{signature.split()[-1].rstrip('(')}\(rolls", HARNESS), signature
    # Holy sword's roll sits in its alignment predicate, among the raw damage modifiers.
    mods = strip_comments(source("dam_mods.c").read_text())
    assert re.search(r"SPELL_HOLY_SWORD\) && IS_GOOD\(victim\)\)\)\{\s*"
                     r"dam_mod->mod \+= holy_sword_alignment_damage\(live_rolls\);\s*dam_mod->type = dam_mod_type::Added",
                     mods)
    assert mods.index("raw_damage_modifiers[] =") < mods.index("holy_sword_alignment_damage(live_rolls)")
    # What the pages say about combat mind, displacement and holy sword.
    fight = strip_comments(source("fight.c").read_text())
    melee = function_bodies(fight, r"\bint\s+melee_damage\s*\(")[0]
    assert re.search(r"displacement_absorb_roll\(live_rolls\)\)\s*&&\s*!\(flags & PHSDAM_NOREDUCE\)\s*&&\s*"
                     r"!affected_by_spell\(ch, SPELL_COMBAT_MIND\)\)\s*\{\s*dam = 0", melee)
    assert re.search(r"if \(sic == 1 && !affected_by_spell\(ch, SPELL_COMBAT_MIND\)\)", fight)
    assert re.search(r"!mangle_disarm_roll\(live_rolls\) &&\s*!affected_by_spell\(victim, SPELL_COMBAT_MIND\)", fight)
    assert re.search(r"SKILL_PARRY, get_property\(\"skill.notch.defensive\", 17\)\) &&\s*"
                     r"!affected_by_spell\(victim, SPELL_COMBAT_MIND\)", fight)
    assert "strip_holy_sword(victim)" in source("actnew.c").read_text()
    assert re.search(r"ch->equipment\[WIELD\] == obj\)\s*\{\s*strip_holy_sword\(ch\)",
                     strip_comments(source("actobj.c").read_text()))
    psionics = strip_comments(PSIONICS)
    assert "return 30;" in function_bodies(psionics, r"\bint\s+inertial_barrier_duration\s*\(")[0]
    # The depart page names the rooms of this macro.
    assert "world[r].number >= 5700 && world[r].number <= 5999" in source("utils.h").read_text()
    # An area cast can skip players.
    assert "pc_skip--" in source("utility.c").read_text()
    # Lucubration's slot loop stops below the top circle.
    assert "for (int i = 1; i < get_max_circle(ch); i++)" in function_bodies(
        strip_comments(MEMORIZE), r"\bvoid\s+spell_mordenkainens_lucubration\s*\(")[0]
    # Wave blast and pyrokinesis carry no globe or ward flag.
    for handler in ("spell_psionic_wave_blast", "event_psionic_wave_blast", "spell_pyrokinesis"):
        body = function_bodies(psionics, rf"\bvoid\s+{handler}\s*\(")[0]
        assert "spell_damage(" in body and not re.search(r"SPLDAM_(?:GLOBE|MINORGLOBE|SPIRITWARD|GRSPIRIT)", body), handler
    # Each effect of confuse's roll is the case the page counts.
    confuse = function_bodies(strip_comments(PSIONICS), r"\bvoid\s+spell_confuse\s*\(")[0]
    assert re.search(r"case 1:\s*case 2:\s*case 3:\s*Stun\(", confuse)
    assert re.search(r"case 4:\s*case 5:\s*case 6:\s*if \(IS_FIGHTING\(tch\)\)", confuse)
    assert re.search(r"case 7:\s*case 8:\s*break;\s*case 9:\s*case 10:", confuse)
    # Pyrokinesis' fire damage only reaches an NPC; a player takes the psionic part.
    pyrokinesis = function_bodies(strip_comments(PSIONICS), r"\bvoid\s+spell_pyrokinesis\s*\(")[0]
    assert pyrokinesis.index("SPLDAM_FIRE") < pyrokinesis.index("else")
    # The stage lines rest on these flags and circles.
    death = function_bodies(strip_comments(PSIONICS), r"\bvoid\s+spell_single_death_field\s*\(")[0]
    assert "spell_damage(ch, victim, dam, SPLDAM_PSI, 0, &messages)" in death
    pain = function_bodies(strip_comments(PSIONICS), r"\bvoid\s+spell_inflict_pain\s*\(")[0]
    assert "SPLDAM_PSI, SPLDAM_GLOBE | RAWDAM_NOKILL" in pain
    registrations = strip_comments(source("skills.c").read_text())
    blocks = {block.split(",")[1].strip(): block for block in re.split(r"(?=SPELL_CREATE)", registrations)
              if block.startswith("SPELL_CREATE") and "," in block}
    for spell, lowest in (("SPELL_BALLISTIC_ATTACK", 2), ("SPELL_EGO_WHIP", 1), ("SPELL_EGO_BLAST", 4)):
        circles = [int(circle) for circle in re.findall(r"SPELL_ADD\(\w+, (\d+)", blocks[spell])]
        assert min(circles) == lowest, spell
    table = strip_comments(source("abilities.c").read_text())
    header = source("abilities.h").read_text()
    for constant, name, _ in SPELLS:
        assert re.search(rf"case {constant}:\s*return {name}_facts;", table), constant
        assert f"std::string {name}_facts(char_data *ch);" in header, name
    assert "SPELL_CREATE_SOUND" in (ROOT / "tests/fixtures/ability_coverage_no_numbers.txt").read_text().split()


def main():
    check_sources()
    psionic_prefixes = tuple(name + "_" for _, name, file in SPELLS if file == "psionics.c")
    avenger_prefixes = tuple(name + "_" for _, name, file in SPELLS if file == "avengers.c")
    functions = [extract_function("utility.c", "int dice(int num, int size)"),
                 extract_function("utility.c", "int BOUNDED(int a, int b, int c)"),
                 extract_function("utility.c", "int GET_CLASS(P_char ch, uint m_class)")]
    functions += [extract_function(file, signature) for file, signature in SHARED_ELSEWHERE]
    functions += shared_functions("psionics.c", PSIONICS, psionic_prefixes)
    functions += shared_functions("avengers.c", AVENGERS, avenger_prefixes)
    functions += shared_functions("guild.c", GUILD, ("learning_",))
    functions += shared_functions("memorize.c", MEMORIZE, ("lucubration_",))
    functions += [extract_function(file, f"std::string {name}_facts(") for _, name, file in SPELLS]
    pages = ",\n".join(f'    {{ "{name}", {name}_facts }}' for _, name, _ in SPELLS)
    build = ROOT / "bin/tests"
    build.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ability-batch-6-", dir=build) as temporary:
        directory = Path(temporary)
        harness = directory / "batch6.cpp"
        harness.write_text(with_innate_numbers(HARNESS.replace("PAGES", pages).replace("FUNCTIONS", "\n".join(functions)), define_rolls=False))
        binary = directory / "batch6"
        subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
                        "-ffunction-sections", "-fdata-sections", "-Wl,--gc-sections",
                        "-fsanitize=address,undefined", "-fno-sanitize-recover=undefined",
                        "-Isrc", "-I/usr/include/mysql", "-I/usr/include/libxml2",
                        str(harness), "src/abilities/abilities.c", "src/core/random.c",
                        "-o", str(binary)], cwd=ROOT, check=True)
        subprocess.run([str(binary)], cwd=directory, check=True)


if __name__ == "__main__":
    main()
