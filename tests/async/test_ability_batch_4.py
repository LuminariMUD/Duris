#!/usr/bin/env python3
"""Shared ability numbers, batch 4: the spells from soulshield to the end of magic.c.

Builds the batch's shared and facts functions, extracted from magic.c, with
src/abilities/abilities.c and the real RNG under sanitizers. The pre-conversion
expressions are kept below as the oracle: under the same seed, each shared function
with live_rolls returns the old value and leaves the RNG at the same draw, and the
value lies inside the range its facts show. Building any facts page never rolls.
"""
import re
import subprocess
import tempfile
from pathlib import Path

from _paths import ROOT, extract_function, source
from _source_contract import function_bodies, strip_comments

# Every spell this batch converted, with its facts function in ability_facts().
CONVERTED = """
SPELL_REPAIR_ONE_ITEM repair_one_item_facts
SPELL_MAGMA_BURST magma_burst_facts
SPELL_ELECTRICAL_EXECUTION electrical_execution_facts
SPELL_DREAD_WAVE dread_wave_facts
SPELL_GROUP_HEAL group_heal_facts
SPELL_APOCALYPSE apocalypse_facts
SPELL_JUDGEMENT judgement_facts
SPELL_CHAOTIC_RIPPLE chaotic_ripple_facts
SPELL_CHAOS_VOLLEY chaos_volley_facts
SPELL_BLINK blink_facts
SPELL_NATURES_CALLING natures_calling_facts
SPELL_PLEASANTRY pleasantry_facts
SPELL_CONTAIN_BEING contain_being_facts
SPELL_NEGATIVE_CONCUSSION_BLAST negative_concussion_blast_facts
SPELL_ACCEL_HEALING accel_healing_facts
SPELL_MIELIKKI_VITALITY mielikki_vitality_facts
SPELL_SPORE_BURST spore_burst_facts
SPELL_SPORE_CLOUD spore_cloud_facts
SPELL_LIFE_BOLT life_bolt_facts
SPELL_KNOCK knock_facts
SPELL_TRANQUILITY tranquility_facts
SPELL_DAZZLE dazzle_facts
SPELL_PASS_WITHOUT_TRACE pass_without_trace_facts
SPELL_STARSHELL starshell_facts
SPELL_STORNOGS_SPHERES stornogs_spheres_facts
SPELL_STORNOGS_GREATER_SPHERES group_stornog_facts
SPELL_CLOAK_OF_FEAR cloak_of_fear_facts
SPELL_ACIDIMMOLATE acidimmolate_facts
SPELL_IMMOLATE immolate_facts
SPELL_CDOOM cdoom_facts
SPELL_SENSE_FOLLOWER sense_follower_facts
SPELL_PERM_INCREASE_STR perm_increase_facts
SPELL_PERM_INCREASE_AGI perm_increase_facts
SPELL_PERM_INCREASE_DEX perm_increase_facts
SPELL_PERM_INCREASE_CON perm_increase_facts
SPELL_PERM_INCREASE_LUCK perm_increase_facts
SPELL_PERM_INCREASE_POW perm_increase_facts
SPELL_PERM_INCREASE_INT perm_increase_facts
SPELL_PERM_INCREASE_WIS perm_increase_facts
SPELL_PERM_INCREASE_CHA perm_increase_facts
SPELL_SOULSHIELD soulshield_facts
SPELL_HOLY_AURA soulshield_facts
SPELL_HOLY_DHARMA holy_dharma_facts
SPELL_HOLY_SACRIFICE holy_sacrifice_facts
SPELL_BATTLE_ECSTASY battle_ecstasy_facts
SPELL_MASS_HEAL mass_heal_facts
SPELL_TRUE_SEEING true_seeing_facts
SPELL_SHADOW_VISION shadow_vision_facts
SPELL_ANIMAL_VISION animal_vision_facts
SPELL_TREE tree_facts
SPELL_ANIMAL_GROWTH animal_growth_facts
SPELL_NATURES_BLESSING natures_blessing_facts
SPELL_ENLARGE enlarge_facts
SPELL_ROPE_TRICK rope_trick_facts
SPELL_REDUCE reduce_facts
SPELL_COMMAND command_facts
SPELL_CHAOS_SHIELD chaos_shield_facts
SPELL_ANGELIC_COUNTENANCE vampire_facts
SPELL_VAMPIRE vampire_facts
SPELL_DIVINE_BLESSING divine_blessing_facts
SPELL_MOONWELL moonwell_facts
SPELL_SHADOW_GATE shadow_gate_facts
SPELL_MOONSTONE moonstone_facts
SPELL_ANIMAE_CICATRIX animae_cicatrix_facts
SPELL_STIGMATA_DRACONICA stigmata_draconica_facts
SPELL_DRAKESCALE_AEGIS drakescale_aegis_facts
SPELL_JUDICIUM_FIDEI judicium_fidei_facts
SPELL_IGNEUS_VITAE igneus_vitae_facts
SPELL_SANGUINIS_IGNIS sanguinis_ignis_facts
SPELL_SANCTUM_DRACONIS sanctum_draconis_facts
SPELL_VIVERNAE_CONCORDIA vivernae_concordia_facts
SPELL_PACTUM_SERPENTIS pactum_serpentis_facts
SPELL_EDICTUM_CINERIS edictum_cineris_facts
SPELL_SIGILLUM_NEGATI sigillum_negati_facts
SPELL_DRACONIC_APOTHEOSIS draconic_apotheosis_facts
SPELL_WARRING_ZEAL warring_zeal_facts
"""

# The shared functions the batch added beside its handlers, in file order.
SHARED = """
soulshield_duration holy_sacrifice_duration battle_ecstasy_duration mass_heal_base
mass_heal_amount tranquility_chance tranquility_lag true_seeing_duration tree_lag
animal_vision_duration natures_blessing_duration shadow_vision_duration rope_trick_duration
enlarge_duration enlarge_refresh_duration enlarge_str_max enlarge_con_max enlarge_agi
enlarge_dex reduce_duration reduce_refresh_duration reduce_str reduce_con reduce_agi_max
reduce_dex_max judgement_damage judgement_apnecro_damage judgement_smite_damage
judgement_repeat_chance judgement_extra_waves immolate_damage immolate_burn_damage dread_wave_damage
dread_wave_saved dread_wave_waves dread_wave_added_waves magma_burst_damage
magma_burst_flares magma_burst_recast_flares cdoom_damage cdoom_waves sense_follower_duration
pass_without_trace_duration starshell_duration vampire_duration vampire_str_max
vampire_con_max vampire_hitroll vampire_damroll cloak_of_fear_save_mod
apocalypse_max_affected apocalypse_death_damage apocalypse_famine_stun
apocalypse_pestilence_damage stornogs_spheres_count warring_zeal_duration
warring_zeal_hitroll dazzle_duration accel_healing_duration accel_healing_regen
pleasantry_duration command_stun group_heal_base group_heal_amount chaos_volley_damage
chaos_volley_wound_bonus chaos_volley_drain chaos_volley_failed_save chaos_shield_duration
chaos_shield_chance knock_chance knock_fail_lag knock_lag negative_concussion_blast_damage
acidimmolate_damage acidimmolate_burn_damage chaotic_ripple_damage chaotic_ripple_rays
chaotic_ripple_blast chaotic_ripple_bolts blink_fall_lag divine_blessing_parry_chance
divine_blessing_parry_alignment divine_blessing_duration divine_blessing_min_alignment
divine_blessing_penalty
natures_calling_level perm_increase_amount perm_increase_max perm_increase_stat
shadow_gate_throughput shadow_gate_decay moonwell_decay moonwell_throughput
moonstone_duration spore_burst_lag spore_burst_level spore_cloud_damage holy_dharma_drain
holy_dharma_duration electrical_execution_damage electrical_execution_arc_damage
life_bolt_damage life_bolt_unopposed mielikki_vitality_duration mielikki_vitality_hit
mielikki_vitality_moves mielikki_vitality_regen repair_one_item_condition
contain_being_duration dragoon_spell_cost dragoon_cost_fact animae_cicatrix_duration
animae_cicatrix_bonus animae_cicatrix_max_bonus stigmata_draconica_duration
drakescale_aegis_absorb drakescale_aegis_hits drakescale_aegis_duration
judicium_fidei_duration igneus_vitae_heal sanguinis_ignis_duration
sanctum_draconis_duration vivernae_concordia_duration pactum_serpentis_duration
edictum_cineris_berserk_lag edictum_cineris_penalty edictum_cineris_duration
sigillum_negati_duration draconic_apotheosis_duration draconic_apotheosis_cost
"""

# Calls each handler, event or helper must make, so the game uses the shared numbers.
CALLS = {
    "spell_soulshield": ["af.duration = soulshield_duration(ch);"],
    "spell_group_stornog": ["spell_stornogs_spheres(level, ch, 0, 0, gl->ch, 0);"],
    "spell_holy_sacrifice": ["af.duration = holy_sacrifice_duration(ch);"],
    "spell_battle_ecstasy": ["af.duration = battle_ecstasy_duration(ch);"],
    "spell_mass_heal": ["int maxhits = mass_heal_base(ch);",
                        "vamp(tch, mass_heal_amount(live_rolls, level, maxhits),"],
    "spell_tranquility": ["skl_lvl = tranquility_chance(level);", "number(1, 130) < skl_lvl",
                          "CharWait(ch, tranquility_lag());"],
    "spell_true_seeing": ["af1->duration = true_seeing_duration();",
                          "af.duration = true_seeing_duration();"],
    "spell_tree": ["CharWait(ch, tree_lag());"],
    "spell_animal_vision": ["af1->duration = animal_vision_duration();",
                            "af.duration = animal_vision_duration();"],
    "spell_natures_blessing": ["af1->duration = natures_blessing_duration();",
                               "af.duration = natures_blessing_duration();"],
    "spell_shadow_vision": ["af1->duration = shadow_vision_duration();",
                            "af.duration = shadow_vision_duration();"],
    "spell_rope_trick": ["af.duration = rope_trick_duration();"],
    "spell_animal_growth": ["spell_reduce(GET_LEVEL(ch), ch, 0, SPELL_ANIMAL_GROWTH, ch, NULL);",
                            "spell_enlarge(GET_LEVEL(ch), ch, 0, SPELL_ANIMAL_GROWTH, ch, NULL);"],
    "spell_enlarge": ["af.duration = enlarge_duration();", "af.modifier = enlarge_str_max(victim);",
                      "af.modifier = enlarge_con_max(victim);", "af.modifier = enlarge_agi(victim);",
                      "af.modifier = enlarge_dex(victim);",
                      "af1->duration = enlarge_refresh_duration(level);"],
    "spell_reduce": ["af.duration = reduce_duration();", "af.modifier = reduce_str(victim);",
                     "af.modifier = reduce_con(victim);", "af.modifier = reduce_agi_max(victim);",
                     "af.modifier = reduce_dex_max(victim);",
                     "af1->duration = reduce_refresh_duration(level);"],
    "event_judgement": ["damage = judgement_damage(live_rolls, ch);",
                        "damage = judgement_apnecro_damage(damage);",
                        "spell_damage(ch, victim, judgement_smite_damage(live_rolls, ch),",
                        "(judgement_repeat_chance(ch) > number(1, 100))",
                        "j->devotion < judgement_extra_waves()"],
    "spell_immolate": ["int dam = immolate_damage(live_rolls, ch, type);"],
    "event_immolate": ["dam = immolate_burn_damage(live_rolls, ch, burntime);"],
    "event_dread_wave": ["dam = dread_wave_damage(live_rolls, ch, af->modifier, level);",
                         "dam = dread_wave_saved(dam);"],
    "spell_dread_wave": ["af->modifier = dread_wave_waves(live_rolls, ch);",
                         "af->modifier += dread_wave_added_waves(ch);"],
    "event_magma_burst": ["dam = magma_burst_damage(live_rolls, level);"],
    "spell_magma_burst": ["af->modifier = magma_burst_flares(type);",
                          "af->modifier = magma_burst_recast_flares(af->modifier);"],
    "spell_single_cdoom_wave": ["int doomdam = cdoom_damage(live_rolls, level);"],
    "spell_cdoom": ["cDoomData.waves = cdoom_waves(live_rolls);"],
    "spell_sense_follower": ["af.duration = sense_follower_duration(level);",
                             "af1->duration = sense_follower_duration(level);"],
    "spell_pass_without_trace": ["af.duration = pass_without_trace_duration();"],
    "spell_starshell": ["af.duration = starshell_duration(level);\n\taffect_to_room"],
    "spell_vampire": ["afp->duration = vampire_duration();", "af.duration = vampire_duration();",
                      "af.modifier = vampire_str_max();", "af.modifier = vampire_con_max();",
                      "af.modifier = vampire_hitroll();", "af.modifier = vampire_damroll();"],
    "spell_cloak_of_fear": ["NewSaves(vict, SAVING_FEAR, cloak_of_fear_save_mod(level))"],
    "event_apocalypse": ["max_affected = apocalypse_max_affected();",
                         "spell_damage(ch, vict, apocalypse_death_damage(live_rolls), SPLDAM_PSI",
                         "Stun(tch, ch, apocalypse_famine_stun(), TRUE);",
                         "spell_damage(ch, tch, apocalypse_pestilence_damage(ch), SPLDAM_GAS"],
    "spell_stornogs_spheres": ["af.modifier = stornogs_spheres_count(victim);"],
    "spell_warring_zeal": ["paf->duration = warring_zeal_duration();",
                           "paf->modifier = warring_zeal_hitroll(level);",
                           "af.duration = warring_zeal_duration();",
                           "af.modifier = warring_zeal_hitroll(level);"],
    "spell_dazzle": ["af.duration = dazzle_duration(level);"],
    "spell_accel_healing": ["af1->duration = accel_healing_duration(level);",
                            "af.duration = accel_healing_duration(level);",
                            "af.modifier = accel_healing_regen(level);"],
    "spell_pleasantry": ["af.duration = pleasantry_duration();"],
    "spell_command": ["Stun(victim, ch, command_stun(ch), FALSE);"],
    "spell_group_heal": ["int healpoints = group_heal_base(live_rolls);",
                         "healpoints = group_heal_amount(live_rolls, ch, healpoints);"],
    "spell_chaos_volley": ["int cvdam = chaos_volley_wound_bonus(ch);",
                           "int dam = chaos_volley_damage(live_rolls, level);",
                           "GET_HIT(ch) -= chaos_volley_drain(dam);",
                           "dam = chaos_volley_failed_save(dam);"],
    "spell_chaos_shield": ["af.duration = chaos_shield_duration(ch);"],
    "parse_chaos_shield": ["chance = chaos_shield_chance();", "if (chance < number(0, 101))"],
    "spell_knock": ["chance = knock_chance(ch);", "CharWait(ch, knock_fail_lag());",
                    "CharWait(ch, knock_lag());"],
    "spell_negative_concussion_blast": ["dam = negative_concussion_blast_damage(live_rolls, level);"],
    "event_acidimmolate": ["dam = acidimmolate_burn_damage(live_rolls, ch, acidburntime);"],
    "spell_acidimmolate": ["spell_damage(ch, victim, acidimmolate_damage(live_rolls, ch), SPLDAM_ACID"],
    "spell_chaotic_ripple": ["dam = chaotic_ripple_damage(live_rolls, level);",
                             "rays = chaotic_ripple_rays(live_rolls);",
                             "spell_damage(ch, victim, chaotic_ripple_blast(dam), SPLDAM_FIRE",
                             "spell_damage(ch, victim, chaotic_ripple_blast(dam), SPLDAM_COLD",
                             "spell_damage(ch, victim, chaotic_ripple_bolts(dam), SPLDAM_GENERIC"],
    "spell_blink": ["CharWait(tch, blink_fall_lag());"],
    "divine_blessing_parry": ["GET_ALIGNMENT(ch) > divine_blessing_parry_alignment()",
                              "number(0, 99) < divine_blessing_parry_chance()"],
    "spell_divine_blessing": ["if (GET_ALIGNMENT(ch) < divine_blessing_min_alignment())",
                              "spell_damage(ch, ch, divine_blessing_penalty(), SPLDAM_HOLY",
                              "af.duration = divine_blessing_duration();"],
    "spell_natures_calling": ["effectiveness = natures_calling_level(level);"],
    "event_natures_call": ["spell_natures_calling(level, ch, NULL, SPELL_TYPE_SPELL"],
    "spell_shadow_gate": ["set.decay_timer = shadow_gate_decay();",
                          "set.throughput = shadow_gate_throughput(live_rolls, ch, specBonus);"],
    "spell_moonwell": ["set.decay_timer = moonwell_decay(ch);",
                       "set.throughput = moonwell_throughput();"],
    "spell_moonstone": ["int duration = moonstone_duration(level);",
                        "af.duration = duration / PULSES_IN_TICK;"],
    "spell_spore_burst": ["CharWait(ch, spore_burst_lag());"],
    "event_spore_burst": ["spore_burst_level(ch, sbdata->spores)"],
    "spell_spore_cloud": ["dam = spore_cloud_damage(live_rolls, level);"],
    "event_holy_dharma": ["maxhits = holy_dharma_drain(ch);"],
    "spell_holy_dharma": ["af.duration = holy_dharma_duration(ch);"],
    "event_electrical_execution": ["dam = electrical_execution_arc_damage(live_rolls, ch, frytime);"],
    "spell_electrical_execution": ["spell_damage(ch, victim, electrical_execution_damage(live_rolls, ch),"],
    "spell_life_bolt": ["dam = life_bolt_damage(live_rolls, level);",
                        "dam = life_bolt_unopposed(dam);"],
    "spell_mielikki_vitality": ["int healpoints = mielikki_vitality_hit(level);",
                                "af1->duration = mielikki_vitality_duration();",
                                "af.duration = mielikki_vitality_duration();",
                                "af.modifier = mielikki_vitality_moves(level);",
                                "af.modifier = mielikki_vitality_regen(live_rolls);"],
    "spell_repair_one_item": ["set_obj_condition(obj, repair_one_item_condition());"],
    "spell_contain_being": ["af.duration = contain_being_duration();"],
    "spell_animae_cicatrix": ["af.duration = animae_cicatrix_duration(ch);",
                              "af.modifier = animae_cicatrix_bonus();",
                              "af.modifier = animae_cicatrix_max_bonus();",
                              "spell_damage(ch, ch, dragoon_spell_cost(ch), SPLDAM_SPIRIT"],
    "spell_stigmata_draconica": ["af.duration = stigmata_draconica_duration(ch);",
                                 "spell_damage(ch, ch, dragoon_spell_cost(ch), SPLDAM_SPIRIT"],
    "spell_drakescale_aegis": ["int absorb = drakescale_aegis_absorb(live_rolls, level);",
                               "absorb = drakescale_aegis_hits(absorb);",
                               "af.duration = drakescale_aegis_duration(ch);",
                               "spell_damage(ch, ch, dragoon_spell_cost(ch), SPLDAM_SPIRIT"],
    "spell_judicium_fidei": ["af.duration = judicium_fidei_duration(ch);",
                             "spell_damage(ch, ch, dragoon_spell_cost(ch), SPLDAM_SPIRIT"],
    "spell_igneus_vitae": ["healpoints = igneus_vitae_heal(live_rolls, ch);",
                           "spell_damage(ch, ch, dragoon_spell_cost(ch), SPLDAM_SPIRIT"],
    "spell_sanguinis_ignis": ["skl_lvl = sanguinis_ignis_duration(level);",
                              "spell_damage(ch, ch, dragoon_spell_cost(ch), SPLDAM_SPIRIT"],
    "spell_sanctum_draconis": ["skl_lvl = sanctum_draconis_duration(level);",
                               "spell_damage(ch, ch, dragoon_spell_cost(ch), SPLDAM_SPIRIT"],
    "spell_vivernae_concordia": ["af.duration = vivernae_concordia_duration();",
                                 "af1->duration = vivernae_concordia_duration();",
                                 "spell_damage(ch, ch, dragoon_spell_cost(ch), SPLDAM_SPIRIT"],
    "spell_pactum_serpentis": ["skl_lvl = pactum_serpentis_duration(level);",
                               "spell_damage(ch, ch, dragoon_spell_cost(ch), SPLDAM_SPIRIT"],
    "spell_edictum_cineris": ["CharWait(victim, edictum_cineris_berserk_lag());",
                              "af.modifier = edictum_cineris_penalty(level);",
                              "af.duration = edictum_cineris_duration(level);"],
    "spell_sigillum_negati": ["af.duration = sigillum_negati_duration(ch);"],
    "spell_draconic_apotheosis": ["af.duration = draconic_apotheosis_duration();",
                                  "spell_damage(ch, ch, draconic_apotheosis_cost(ch), SPLDAM_SPIRIT"],
    "spell_perm_increase_str": ["if (victim->base_stats.Str >= perm_increase_max())",
                                "victim->base_stats.Str = perm_increase_stat(victim->base_stats.Str);",
                                "victim->curr_stats.Str = perm_increase_stat(victim->curr_stats.Str);"],
}
for handler, field in (("agi", "Agi"), ("dex", "Dex"), ("con", "Con"), ("luck", "Luk"),
                       ("pow", "Pow"), ("int", "Int"), ("wis", "Wis"), ("cha", "Cha")):
    CALLS[f"spell_perm_increase_{handler}"] = [
        call.replace("Str", field) for call in CALLS["spell_perm_increase_str"]]

HARNESS = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "magic/spells.h"
#include "abilities/abilities.h"
#include "world/hardcore_config.h"
#include <algorithm>
#include <cassert>
#include <climits>
#include <cstdio>
#include <functional>
#include <map>
#include <string>
#include <vector>

void randomize(uint64_t seed);

// What the shared functions read from the rest of the game.
static int skill_level;
int GET_CHAR_SKILL_P(P_char, int) { return skill_level; }
int GET_CLASS(P_char ch, uint cls) { return (ch->player.m_class & cls) || (ch->player.secondary_class & cls); }
static std::map<std::string, double> properties;
float get_property(const char *key, double fallback) {
    return properties.count(key) ? properties[key] : fallback;
}
int get_property(const char *key, int fallback) {
    return properties.count(key) ? (int)properties[key] : fallback;
}
static hardcore_config hardcore{};
const hardcore_config *hardcore_config_get() { return &hardcore; }
P_room world;

// The next draw after a roll; equal fingerprints after equal seeds mean equal draw counts.
static int fingerprint() { return number(0, INT_MAX); }

// How a roll's facts bounds are checked: both hold; both hold and are reached by sampling;
// or only the highest holds and is reached.
enum class Bounds { hold, reached, high };

// Same value and draw count as the original, inside the facts bounds, for 40 seeds.
static void same_rolls(const char *name, const std::function<int()> &original,
                       const std::function<int(const Rolls &)> &shared, Bounds bounds) {
    const int a = shared(lowest_rolls), b = shared(highest_rolls);
    const int low = bounds == Bounds::high ? INT_MIN : std::min(a, b), high = std::max(a, b);
    for (uint64_t seed = 1; seed <= 40; ++seed) {
        randomize(seed);
        const int expected = original(), expected_next = fingerprint();
        randomize(seed);
        const int actual = shared(live_rolls), actual_next = fingerprint();
        if (actual != expected || actual_next != expected_next || actual < low || actual > high) {
            fprintf(stderr, "%s: seed %llu: %d vs %d in %d-%d\n", name, (unsigned long long)seed,
                    actual, expected, low, high);
            assert(false);
        }
    }
    if (bounds == Bounds::hold)
        return; // dice of many rolls: exact by monotonicity, too rare to reach by sampling
    int seen_low = INT_MAX, seen_high = INT_MIN;
    for (uint64_t seed = 1; seed <= 3000; ++seed) {
        randomize(seed);
        const int value = shared(live_rolls);
        seen_low = std::min(seen_low, value);
        seen_high = std::max(seen_high, value);
    }
    if ((bounds == Bounds::reached && seen_low != low) || seen_high != high) {
        fprintf(stderr, "%s: reached %d-%d, facts %d-%d\n", name, seen_low, seen_high, low, high);
        assert(false);
    }
}

static bool contains(const std::string &text, const std::string &part) {
    return text.find(part) != std::string::npos;
}

static void check_page(const std::string &text) {
    size_t start = 0;
    while (start < text.size()) {
        const size_t end = text.find('\n', start);
        assert(end != std::string::npos);
        if (end - start > 79 || text.compare(start, 2, "  ") != 0) {
            fprintf(stderr, "bad line: [%s]\n", text.substr(start, end - start).c_str());
            assert(false);
        }
        start = end + 1;
    }
}

int main() {
    room_data rooms[2]{};
    world = rooms;
    char_data ch{};

    // Every roll matches its pre-conversion expression across levels and characters.
    for (int level : { 1, 10, 30, 50, 56, 60 })
        for (int kind = 0; kind < 4; ++kind) {
            ch = char_data{};
            ch.player.level = level;
            ch.points.max_hit = 900;
            ch.points.hit = 700;
            skill_level = kind * 30;
            if (kind == 1) {
                ch.player.m_class = CLASS_CONJURER;
                ch.player.spec = SPEC_WATER;
            } else if (kind == 2) {
                ch.player.m_class = CLASS_CLERIC;
                ch.player.spec = SPEC_HEALER;
            }
            properties.clear();
            if (kind == 3)
                properties = { { "spell.judgement.dam.modifier", 0.7 },
                               { "portals.shadowportal.maxToPass", 3 } };
            P_char c = &ch;
            same_rolls("mass_heal_amount", [&] { int maxhits = 100; return (int)maxhits + number(1, level / 3); },
                       [&](const Rolls &r) { return mass_heal_amount(r, level, mass_heal_base(c)); }, Bounds::reached);
            same_rolls("judgement_damage",
                       [&] { return dice(20, (int)(GET_LEVEL(c) * get_property("spell.judgement.dam.modifier", 0.500))); },
                       [&](const Rolls &r) { return judgement_damage(r, c); }, Bounds::hold);
            same_rolls("judgement_smite_damage", [&] { return dice(10, GET_LEVEL(c)); },
                       [&](const Rolls &r) { return judgement_smite_damage(r, c); }, Bounds::hold);
            for (int type : { SPELL_TYPE_SPELL, SPELL_TYPE_WAND })
                same_rolls("immolate_damage", [&] {
                    int dam = GET_LEVEL(c) * 4 + number(4, 20);
                    if (type > 1)
                        dam += dam * 0.05;
                    return dam;
                }, [&](const Rolls &r) { return immolate_damage(r, c, type); }, Bounds::reached);
            for (int burntime = 1; burntime <= 6; ++burntime)
                same_rolls("immolate_burn_damage", [&] {
                    int dam = (int)GET_LEVEL(c) * 2 + number(4, 20);
                    if (burntime >= 3)
                        dam = (int)GET_LEVEL(c) * 2 - number(4, 20);
                    if (burntime >= 4)
                        dam = (int)GET_LEVEL(c) + number(4, 12);
                    return dam;
                }, [&](const Rolls &r) { return immolate_burn_damage(r, c, burntime); }, Bounds::reached);
            for (int modifier = 0; modifier <= 6; ++modifier)
                same_rolls("dread_wave_damage", [&] {
                    int dam = MAX(1, (int)(((modifier + 2) * level) + number(-60, 0)));
                    dam = (int)(dam * GET_LEVEL(c) / 56);
                    return dam;
                }, [&](const Rolls &r) { return dread_wave_damage(r, c, modifier, level); }, Bounds::high);
            same_rolls("dread_wave_waves", [&] {
                int modifier;
                if (GET_SPEC(c, CLASS_CONJURER, SPEC_WATER))
                    modifier = number(1, 3);
                else
                    modifier = 0;
                modifier += 2;
                return modifier;
            }, [&](const Rolls &r) { return dread_wave_waves(r, c); }, Bounds::reached);
            same_rolls("magma_burst_damage", [&] { return (3 * level) + number(0, 30); },
                       [&](const Rolls &r) { return magma_burst_damage(r, level); }, Bounds::reached);
            same_rolls("cdoom_damage", [&] { return 40 + level + number(0, 20); },
                       [&](const Rolls &r) { return cdoom_damage(r, level); }, Bounds::reached);
            same_rolls("cdoom_waves", [&] { return number(4, 5); },
                       [&](const Rolls &r) { return cdoom_waves(r); }, Bounds::reached);
            same_rolls("apocalypse_death_damage", [&] { return dice(20, 30); },
                       [&](const Rolls &r) { return apocalypse_death_damage(r); }, Bounds::hold);
            same_rolls("group_heal", [&] {
                int healpoints = 70 + number(0, 10);
                if (GET_SPEC(c, CLASS_CLERIC, SPEC_HEALER))
                    healpoints = 120 + number(0, 20);
                if (GET_CHAR_SKILL(c, SKILL_DEVOTION) > 0)
                    healpoints += (int)(GET_CHAR_SKILL(c, SKILL_DEVOTION) / 5);
                return healpoints;
            }, [&](const Rolls &r) { return group_heal_amount(r, c, group_heal_base(r)); }, Bounds::reached);
            same_rolls("chaos_volley_damage", [&] { return MIN(level, 56) * 9 + number(1, 20); },
                       [&](const Rolls &r) { return chaos_volley_damage(r, level); }, Bounds::reached);
            same_rolls("negative_concussion_blast_damage", [&] { return dice(2 * level, 6); },
                       [&](const Rolls &r) { return negative_concussion_blast_damage(r, level); }, Bounds::hold);
            same_rolls("acidimmolate_damage", [&] { return (int)GET_LEVEL(c) * 2 + number(20, 120); },
                       [&](const Rolls &r) { return acidimmolate_damage(r, c); }, Bounds::reached);
            for (bool conjurer : { false, true })
                for (int burntime = 1; burntime <= 5; ++burntime) {
                    char_data caster = ch;
                    caster.player.m_class = conjurer ? CLASS_CONJURER : CLASS_WARRIOR;
                    P_char a = &caster;
                    same_rolls("acidimmolate_burn_damage", [&] {
                        int dam = (int)(GET_LEVEL(a) * 2);
                        if (!GET_CLASS(a, CLASS_CONJURER)) {
                            if (burntime >= 4)
                                dam = (int)GET_LEVEL(a) + number(4, 12);
                            else if (burntime == 3)
                                dam = (int)(GET_LEVEL(a) * 2 - number(4, 20));
                        }
                        return dam;
                    }, [&](const Rolls &r) { return acidimmolate_burn_damage(r, a, burntime); }, Bounds::reached);
                }
            same_rolls("chaotic_ripple_damage", [&] { return 370 + (30 * MAX(1, level - 50)) + number(1, level); },
                       [&](const Rolls &r) { return chaotic_ripple_damage(r, level); }, Bounds::reached);
            same_rolls("chaotic_ripple_rays", [&] { return number(2, 4); },
                       [&](const Rolls &r) { return chaotic_ripple_rays(r); }, Bounds::reached);
            same_rolls("shadow_gate_throughput", [&] {
                int specBonus = 0;
                int maxToPass = get_property("portals.shadowportal.maxToPass", 5);
                return MAX(0, (int)((c->player.level - 46))) + number(2, maxToPass + specBonus);
            }, [&](const Rolls &r) { return shadow_gate_throughput(r, c, 0); }, Bounds::reached);
            same_rolls("spore_cloud_damage", [&] { return 100 + level * 4 + number(1, 20); },
                       [&](const Rolls &r) { return spore_cloud_damage(r, level); }, Bounds::reached);
            same_rolls("electrical_execution_damage", [&] { return (int)GET_LEVEL(c) * 4 + number(4, 60); },
                       [&](const Rolls &r) { return electrical_execution_damage(r, c); }, Bounds::reached);
            for (int frytime = 1; frytime <= 7; ++frytime)
                same_rolls("electrical_execution_arc_damage", [&] {
                    int dam;
                    if (frytime >= 4)
                        dam = (int)(GET_LEVEL(c) / 2 + number(4, 12));
                    else if (frytime >= 2)
                        dam = (int)((2 * GET_LEVEL(c)) / 3 - number(-20, 20));
                    else
                        dam = (int)((3 * GET_LEVEL(c)) / 2 + number(4, 20));
                    return dam;
                }, [&](const Rolls &r) { return electrical_execution_arc_damage(r, c, frytime); }, Bounds::reached);
            same_rolls("life_bolt_damage", [&] {
                int num_missiles = BOUNDED(1, (level / 3), 5);
                return (dice(1, 4) * 4 + number(1, level)) * num_missiles;
            }, [&](const Rolls &r) { return life_bolt_damage(r, level); }, Bounds::reached);
            same_rolls("mielikki_vitality_regen", [&] { return number(20, 45); },
                       [&](const Rolls &r) { return mielikki_vitality_regen(r); }, Bounds::reached);
            same_rolls("drakescale_aegis_absorb", [&] { return (level / 4) + number(1, 4); },
                       [&](const Rolls &r) { return drakescale_aegis_absorb(r, level); }, Bounds::reached);
            same_rolls("igneus_vitae_heal", [&] { return number(150, (GET_LEVEL(c) * 5)); },
                       [&](const Rolls &r) { return igneus_vitae_heal(r, c); }, Bounds::reached);
        }

    // The permanent stat spells keep their old bounds.
    for (int stat : { -5, 0, 1, 50, 94, 95, 100 })
        assert(perm_increase_stat(stat) == BOUNDED(1, stat + 1, 95));

    // No facts page rolls or runs past 79 columns.
    const std::vector<AbilityFacts> converted = { CONVERTED };
    randomize(9);
    const int untouched = fingerprint();
    for (int level = 1; level <= 62; ++level)
        for (int kind = 0; kind < 6; ++kind) {
            ch = char_data{};
            ch.player.level = level;
            ch.points.max_hit = 1500;
            ch.points.hit = 523;
            ch.base_stats.Str = ch.base_stats.Con = ch.base_stats.Agi = ch.base_stats.Dex = 100;
            skill_level = kind * 20;
            const int classes[] = { 0, CLASS_CONJURER, CLASS_CLERIC, CLASS_DRUID, CLASS_DRAGOON, CLASS_RANGER };
            ch.player.m_class = classes[kind];
            ch.player.spec = kind == 1 ? SPEC_WATER : kind == 2 ? SPEC_HEALER : kind == 3 ? SPEC_WOODLAND : 0;
            rooms[0].sector_type = kind == 3 ? SECT_FOREST : SECT_CITY;
            for (AbilityFacts facts : converted) {
                randomize(9);
                check_page(facts(&ch));
                assert(fingerprint() == untouched);
            }
        }

    // Pages at level 50 with no skills, default properties and full health.
    ch = char_data{};
    ch.player.level = 50;
    ch.points.max_hit = ch.points.hit = 1000;
    ch.base_stats.Str = 80;
    ch.base_stats.Con = 60;
    ch.base_stats.Agi = 70;
    ch.base_stats.Dex = 50;
    skill_level = 0;
    properties.clear();
    // The recast top-up is the handler's original expression.
    for (int flares = 0; flares < 8; ++flares)
        assert(magma_burst_recast_flares(flares) == ((flares < 3) ? 3 : flares + 1));
    const std::vector<std::pair<std::string, std::string>> pages = {
        { soulshield_facts(&ch), "  Duration: 15-16 game hours (18.75-20 minutes) with your devotion\n" },
        { mass_heal_facts(&ch), "  Healing: 101-116 to each person in the room at your level, 50\n" },
        { tranquility_facts(&ch), "  Chance to calm each fighter: 56 in 130 at your level, 50\n"
                                  "  Your lag: 4 seconds\n" },
        { true_seeing_facts(&ch), "  Duration: 72-73 game hours (90-91.25 minutes)\n" },
        { tree_facts(&ch), "  Your lag: 12 seconds\n" },
        { enlarge_facts(&ch), "  Duration: 3-4 game hours (3.75-5 minutes)\n"
                              "  Recast while enlarged: 50-51 game hours (62.5-63.75 minutes)\n"
                              "  On you: max strength +8, max constitution +15, agility -14, dexterity -10\n" },
        { reduce_facts(&ch), "  On you: strength -20, constitution -12, max agility +14, max dexterity +10\n" },
        { judgement_facts(&ch), "  Holy damage per strike: 20-500 at your level, 50\n"
                                "  Against antipaladins and necromancers: 20-500\n"
                                "  A strike that knocks its target down adds: 10-500\n"
                                "  Chance a striking wave repeats: 0% with your devotion, up to 3 times\n"
                                "  A wave may judge foes instead of striking them. Strikes cannot kill.\n" },
        { immolate_facts(&ch), "  Fire damage: 204-220 at your level, 50\n"
                               "  Burning, rounds 1-2: 104-120 each\n"
                               "  Burning, rounds 4-6: 54-62 each, if the fire lasts\n"
                               "  Round 3 burns for less than rounds 1-2. Spell damage modifiers and the\n" },
        { dread_wave_facts(&ch), "  Waves: 2\n  First wave: up to 133 damage at your level, 50\n"
                                 "  First wave if the target makes both saves: up to 87\n"
                                 "  Waves added by recasting: 1\n" },
        { magma_burst_facts(&ch), "  Fire damage per flare: 150-180 at your level, 50\n  Flares: 3\n"
                                  "  Cast again on a burning target: back up to 3 flares left, or 1 more\n" },
        { cdoom_facts(&ch), "  Damage per wave: 90-110 at your level, 50\n  Waves: 4-5\n" },
        { starshell_facts(&ch), "  Duration: 38 seconds\n" },
        { vampire_facts(&ch), "  Duration: 10-11 game hours (12.5-13.75 minutes)\n  Hitroll: 15\n"
                              "  Damroll: 10\n" },
        { cloak_of_fear_facts(&ch), "  Targets' fear save modifier: 2 at your level; higher is harder to resist\n" },
        { apocalypse_facts(&ch), "  Horseman of Death: 20-600 psionic damage to one foe\n"
                                 "  Horseman of Famine: stuns for 4 seconds if a foe fails a fear save\n"
                                 "  A foe that saves is stunned for half that if it fails a second.\n"
                                 "  Horseman of Pestilence: 150 gas damage to each foe it breathes on\n"
                                 "  Foes each later horseman can affect: up to 4\n" },
        { stornogs_spheres_facts(&ch), "  Spheres: 1, each stopping one damage spell that can be deflected\n" },
        { warring_zeal_facts(&ch), "  Hitroll: 10 at your level\n" },
        { accel_healing_facts(&ch), "  Duration: 42-43 game hours (52.5-53.75 minutes)\n"
                                    "  Hit point regeneration: 1000 at your level\n" },
        { command_facts(&ch), "  Stun if the target fails its save: 4 seconds\n" },
        { group_heal_facts(&ch), "  Healing: 70-80 to you and each group member here\n" },
        { chaos_volley_facts(&ch), "  Damage: 451-470 at your level, 50, and current health\n"
                                   "  Of that, from your missing hit points: 0\n"
                                   "  If the target fails its save: 902-940\n"
                                   "  Your hit points spent above half health: 15\n"
                                   "  It lands as one or two hits of random types, then spell damage modifiers\n" },
        { chaos_shield_facts(&ch), "  Duration: 16-17 game hours (20-21.25 minutes)\n"
                                   "  Chance to absorb part of a spell: 11 in 102\n" },
        { knock_facts(&ch), "  Chance to unlock: 50% at your level\n"
                            "  Your lag: 1.5 seconds, or 2 seconds if it fails\n" },
        { negative_concussion_blast_facts(&ch), "  Negative energy damage: 100-600 at your level, 50\n" },
        { acidimmolate_facts(&ch), "  Acid damage: 120-220 at your level, 50\n"
                                   "  Burning, rounds 1-2: 100 each\n"
                                   "  Burning, round 4 on: 54-62 each, until it wears off\n"
                                   "  Round 3 burns for no more than rounds 1-2. Spell damage modifiers and\n" },
        { chaotic_ripple_facts(&ch), "  Damage: 401-450 at your level, 50\n"
                                     "  Rays that follow: 2-4, rarely more\n"
                                     "  Fireball or freezing ray: 160-180\n  Twin bolts: 140-157\n" },
        { blink_facts(&ch), "  An attacker who stumbles is lagged: 4 seconds\n" },
        { divine_blessing_facts(&ch), "  Duration: 15-16 game hours (18.75-20 minutes)\n"
                                      "  Chance to parry an attack: 10% above alignment 990\n"
                                      "  If your alignment is below 950: 600 holy damage to you, which cannot kill\n"
                                      "  That damage is before spell damage modifiers, and the blessing fails.\n" },
        { natures_calling_facts(&ch), "  Blessings cast at level: 25\n" },
        { perm_increase_facts(&ch), "  Base and current stat: raised by 1, up to 95\n" },
        { shadow_gate_facts(&ch), "  People who can pass: 6-9 at your level\n  Stays open: 30 seconds\n" },
        { moonwell_facts(&ch), "  People who can pass: 20\n  Stays open: 30 seconds if cast here\n" },
        { moonstone_facts(&ch), "  Duration: 160-161 game hours (200-201.25 minutes) at your level\n" },
        { spore_cloud_facts(&ch), "  Gas damage: 301-320 at your level, 50\n" },
        { spore_burst_facts(&ch), "  Gas damage: 289-316 to each foe at your level\n  Your lag: 8 seconds\n" },
        { holy_dharma_facts(&ch), "  Drawn from an opponent above full health: up to 25 hit points at a time\n" },
        { electrical_execution_facts(&ch), "  Lightning damage: 204-260 at your level, 50\n"
                                           "  First arc: 79-95\n"
                                           "  Arcs 4 and on: 29-37 each, until they ground out\n"
                                           "  Arcs 2-3 vary more widely. Arcs strike every half round. Spell damage\n" },
        { life_bolt_facts(&ch), "  Damage if the target's alignment opposes yours: 25-330 at your level, 50\n"
                                "  Otherwise: 12-165\n" },
        { mielikki_vitality_facts(&ch), "  Duration: 15-16 game hours (18.75-20 minutes)\n"
                                        "  Hit points: 175 at your level\n  Moves, from a druid: 50\n"
                                        "  Hit point regeneration, from a ranger: 20-45\n"
                                        "  A ranger who has regeneration or accelerated healing adds none.\n" },
        { repair_one_item_facts(&ch), "  Item condition: set to 100\n" },
        { contain_being_facts(&ch), "  Duration: 25 seconds\n" },
        { animae_cicatrix_facts(&ch), "  Power, wisdom, agility, strength, hitroll, damroll: 10 each\n"
                                      "  Fire protection: 10\n  Max power: 5\n" },
        { stigmata_draconica_facts(&ch), "  Duration: 10-11 game hours (12.5-13.75 minutes)\n"
                                         "  Spirit damage to yourself: 100 at your current health, before defenses\n" },
        { drakescale_aegis_facts(&ch), "  Hits it weakens: 10-12 at your level\n" },
        { igneus_vitae_facts(&ch), "  Healing to your mount: 150-250 at your level\n" },
        { sanguinis_ignis_facts(&ch), "  Duration: 10-11 game hours (12.5-13.75 minutes)\n" },
        { edictum_cineris_facts(&ch), "  Hitroll and damroll: -7 each at your level, never taking the target below 0\n"
                                      "  Duration: 8-9 game hours (10-11.25 minutes)\n"
                                      "  A berserking target instead calms and is lagged: 4 seconds\n"
                                      "  Works only when a fear save fails.\n"
                                      "  No effect on elites, undead, angels or a target already afraid.\n" },
        { draconic_apotheosis_facts(&ch), "  Spirit damage to yourself: 200 at your current health, before defenses\n" },
    };
    for (const auto &[page, lines] : pages)
        if (!contains(page, lines)) {
            fprintf(stderr, "missing:\n%s\nin:\n%s\n", lines.c_str(), page.c_str());
            assert(false);
        }
    assert(animal_growth_facts(&ch) == "  Matching a larger animal works as enlarge on you:\n" +
           enlarge_facts(&ch) + "  Matching a smaller animal works as reduce on you:\n" + reduce_facts(&ch));

    // The viewer's own skills, class, health and configured properties change the page.
    skill_level = 100;
    assert(contains(soulshield_facts(&ch), "Duration: 35-36 game hours (43.75-45 minutes)"));
    assert(contains(judgement_facts(&ch), "Chance a striking wave repeats: 19%"));
    assert(contains(group_heal_facts(&ch), "Healing: 90-100 "));
    assert(contains(holy_dharma_facts(&ch), "Duration: 25-26 game hours"));
    assert(contains(holy_dharma_facts(&ch), "up to 75 hit points"));
    assert(contains(drakescale_aegis_facts(&ch), "Duration: 30-31 game hours"));
    ch.player.m_class = CLASS_CLERIC;
    ch.player.spec = SPEC_HEALER;
    assert(contains(group_heal_facts(&ch), "Healing: 140-160 "));
    skill_level = 0;
    ch.player.m_class = CLASS_CONJURER;
    ch.player.spec = SPEC_WATER;
    assert(contains(dread_wave_facts(&ch), "Waves: 3-5\n  First wave: up to 267 damage "));
    assert(contains(dread_wave_facts(&ch), "Waves added by recasting: 2\n"));
    assert(contains(acidimmolate_facts(&ch), "Burning, round 4 on: 100 each,"));
    ch.player.level = 56;
    assert(contains(stornogs_spheres_facts(&ch), "Spheres: 4,"));
    assert(contains(stornogs_spheres_facts(&ch), "  It does nothing to a target that still has spheres.\n"));
    assert(group_stornog_facts(&ch) ==
           "  Casts: stornog's spheres on each group member in the room\n"
           "  Each member gets the spheres that stornog's spheres would give them; yours:\n" +
           stornogs_spheres_facts(&ch) + "  Nothing happens unless you are in a group.\n");
    assert(contains(command_facts(&ch), "save: 8 seconds\n"));
    ch.player.m_class = CLASS_DRUID;
    ch.player.spec = SPEC_WOODLAND;
    rooms[0].sector_type = SECT_FOREST;
    assert(contains(moonwell_facts(&ch), "Stays open: 45 seconds if cast here\n"));
    ch.player.level = 20;
    assert(contains(igneus_vitae_facts(&ch), "Healing to your mount: 100-150 "));
    assert(contains(starshell_facts(&ch), "Duration: none at your level\n"));
    ch.player.level = 50;
    ch.points.hit = 523;
    assert(contains(stigmata_draconica_facts(&ch), "yourself: 52.3 at your current health,"));
    ch.points.hit = 600;
    assert(contains(chaos_volley_facts(&ch), "Damage: 701-720 at your level, 50, and current health\n"
                                            "  Of that, from your missing hit points: 250\n"));
    ch.specials.act2 = PLR2_HARDCORE_CHAR;
    hardcore.bonus_mass_heal_base = 150;
    assert(contains(mass_heal_facts(&ch), "Healing: 151-166 "));
    properties = { { "stats.str.Vampire", 120 }, { "spell.judgement.dam.modifier", 0.7 },
                   { "spell.judgement.dam.modifier.apnecro", 1.5 }, { "hit.regen.Spell", 6 } };
    assert(contains(vampire_facts(&ch), "Damroll: 10\n  Max strength: 20\n"));
    assert(!contains(vampire_facts(&ch), "Max constitution"));
    assert(contains(judgement_facts(&ch), "per strike: 20-700 at your level, 50\n"
                                          "  Against antipaladins and necromancers: 30-1050\n"));
    assert(contains(accel_healing_facts(&ch), "regeneration: 700 at your level\n"));
    puts("PASS: batch 4 shared rolls match the old code, ranges hold, facts never roll");
}
'''


def check_facts_table():
    table = dict(re.findall(r"case\s+(\w+):\s*return\s+(\w+);",
                            strip_comments(source("abilities.c").read_text())))
    for line in CONVERTED.strip().splitlines():
        spell, facts = line.split()
        assert table.get(spell) == facts, spell


def check_handlers_use_shared_numbers():
    code = strip_comments(source("magic.c").read_text())
    for handler, calls in CALLS.items():
        bodies = function_bodies(code, rf"\b(?:void|int|bool)\s+{handler}\s*\(")
        assert len(bodies) == 1, handler
        for call in calls:
            assert call in bodies[0], f"{handler}: {call}"


def main():
    check_facts_table()
    check_handlers_use_shared_numbers()
    text = source("magic.c").read_text()
    names = SHARED.split() + [name for line in CONVERTED.strip().splitlines()
                              for name in line.split()[1:]]
    signatures = {}
    for name in names:
        found = re.findall(rf"^((?:static )?[\w:]+ {name}\()", text, re.M)
        assert len(found) == 1, name
        signatures[found[0]] = text.index(found[0])
    functions = [extract_function("utility.c", "int dice(int num, int size)"),
                 extract_function("utility.c", "int BOUNDED(int a, int b, int c)")]
    functions += [extract_function("magic.c", signature)
                  for signature in sorted(signatures, key=signatures.get)]
    converted = ", ".join(sorted({line.split()[1] for line in CONVERTED.strip().splitlines()}))
    build = ROOT / "bin/tests"
    build.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ability-batch-4-", dir=build) as temporary:
        directory = Path(temporary)
        harness = directory / "batch.cpp"
        harness.write_text(HARNESS.replace("{ CONVERTED }", "{ " + converted + " }")
                           .replace("int main() {", "\n".join(functions) + "\nint main() {"))
        binary = directory / "batch"
        subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
                        "-ffunction-sections", "-fdata-sections", "-Wl,--gc-sections",
                        "-fsanitize=address,undefined", "-fno-sanitize-recover=undefined",
                        "-Isrc", "-I/usr/include/mysql", "-I/usr/include/libxml2",
                        str(harness), "src/abilities/abilities.c", "src/core/random.c",
                        "-o", str(binary)], cwd=ROOT, check=True)
        subprocess.run([str(binary)], cwd=directory, check=True)


if __name__ == "__main__":
    main()
