#!/usr/bin/env python3
"""Shared ability numbers, batch 7: ethermancer, paladin and alchemist spells.

Builds src/abilities/abilities.c and the real RNG with every shared and facts function of
this batch, under sanitizers. Each converted roll keeps its pre-conversion expression below
as the oracle: under the same seeds it must give the same value and leave the RNG at the
same draw, and the value must fall inside the range its facts show. Every page is built at
every level for several casters: it must never roll, and every line must fit 79 columns.
"""
import re
import subprocess
import tempfile
from pathlib import Path

from _paths import ROOT, extract_function, source
from _source_contract import function_bodies, strip_comments

ETHERMANCER = "ethermancer.c"
PALADINS = "paladins.c"
ALCHEMIST = "salchemist.c"

# Spell constant, facts name and handler file of every spell this batch converted.
CONVERTED = """
SPELL_AMATTER_COLLISION antimatter_collision ethermancer.c
SPELL_ARCANE_WHIRLWIND arcane_whirlwind ethermancer.c
SPELL_ARCTIC_BLAST arctic_blast ethermancer.c
SPELL_COLD_SNAP cold_snap ethermancer.c
SPELL_COMET comet ethermancer.c
SPELL_CONJURE_AIR conjure_air ethermancer.c
SPELL_CONJURE_ICE conjure_ice_elemental ethermancer.c
SPELL_CONJURE_VOID conjure_void_elemental ethermancer.c
SPELL_COSMIC_RIFT cosmic_rift ethermancer.c
SPELL_COSMIC_VACUUM cosmic_vacuum ethermancer.c
SPELL_ETHEREAL_ALLIANCE ethereal_alliance ethermancer.c
SPELL_ETHEREAL_DISCHARGE ethereal_discharge ethermancer.c
SPELL_ETHEREAL_FORM ethereal_form ethermancer.c
SPELL_ETHEREAL_RECHARGE ethereal_recharge ethermancer.c
SPELL_ETHEREAL_TRAVEL ethereal_travel ethermancer.c
SPELL_ETHERIC_GUST etheric_gust ethermancer.c
SPELL_FAERIE_SIGHT faerie_sight ethermancer.c
SPELL_FORKED_LIGHTNING forked_lightning ethermancer.c
SPELL_FROST_BEACON frost_beacon ethermancer.c
SPELL_FROST_BEAM frost_beam ethermancer.c
SPELL_FROST_BOLT frost_bolt ethermancer.c
SPELL_GREATER_ETHEREAL greater_ethereal_recharge ethermancer.c
SPELL_ICE_ARMOR iceflow_armor ethermancer.c
SPELL_ICE_SPIKES ice_spikes ethermancer.c
SPELL_INDUCE_TUPOR induce_tupor ethermancer.c
SPELL_MASS_FLY mass_fly ethermancer.c
SPELL_NEG_ARMOR negative_feedback_barrier ethermancer.c
SPELL_PLANETARY_ALIGNMENT planetary_alignment ethermancer.c
SPELL_POLAR_VORTEX polar_vortex ethermancer.c
SPELL_PURGE purge ethermancer.c
SPELL_RAZOR_WIND razor_wind ethermancer.c
SPELL_STATIC_DISCHARGE static_discharge ethermancer.c
SPELL_STORM_EMPATHY storm_empathy ethermancer.c
SPELL_SUPERNOVA supernova ethermancer.c
SPELL_TEMPEST tempest ethermancer.c
SPELL_TEMPEST_TERRAIN tempest_terrain ethermancer.c
SPELL_VAPOR_ARMOR vapor_armor ethermancer.c
SPELL_VAPOR_STRIKE vapor_strike ethermancer.c
SPELL_WALL_OF_AIR wall_of_air ethermancer.c
SPELL_WINDWALK windwalk ethermancer.c
SPELL_WIND_BLADE wind_blade ethermancer.c
SPELL_WIND_RAGE wind_rage ethermancer.c
SPELL_BLEAK_FOEMAN bleak_foeman paladins.c
SPELL_BLOOD_TITHE blood_tithe paladins.c
SPELL_DREAD_BLADE dread_blade paladins.c
SPELL_RIGHTEOUS_AURA righteous_aura paladins.c
SPELL_VORTEX_OF_FEAR vortex_of_fear paladins.c
SPELL_GLASS_BOMB glass_bomb salchemist.c
SPELL_GREASE grease salchemist.c
SPELL_NAPALM napalm salchemist.c
SPELL_NITROGEN nitrogen salchemist.c
SPELL_STRONG_ACID strong_acid salchemist.c
"""
SPELLS = [line.split() for line in CONVERTED.split("\n") if line.strip()]

# The batch's statics, by file; other statics in these files are not this batch's.
PREFIXES = {
    ETHERMANCER: ("vapor_armor_", "frost_beam_", "faerie_sight_", "cold_snap_", "wind_blade_",
                  "windwalk_", "frost_beacon_", "vapor_strike_", "forked_lightning_", "frost_bolt_",
                  "ethereal_", "greater_ethereal_", "conjured_elemental_", "conjure_", "storm_empathy_",
                  "arcane_whirlwind_", "purge_", "induce_tupor_", "tempest_", "wind_rage_", "comet_",
                  "cosmic_", "supernova_", "planetary_alignment_", "polar_vortex_", "static_discharge_",
                  "razor_wind_", "iceflow_armor_", "negative_feedback_barrier_", "etheric_gust_",
                  "antimatter_collision_", "arctic_blast_", "ice_spikes_", "wall_of_air_", "damage_change"),
    PALADINS: ("vortex_of_fear_", "righteous_aura_", "bleak_foeman_", "dread_blade_", "blood_tithe_"),
    ALCHEMIST: ("napalm_", "strong_acid_", "glass_bomb_", "nitrogen_", "grease_"),
}
# Older statics with the same prefixes.
OLDER = {"wind_blade_grant_completed", "blood_tithe_body"}

# What each handler (or the event or per-target callback doing its work) must call, per file.
HANDLER_CALLS = {
    ETHERMANCER: {
        "spell_vapor_armor": ["af.duration = vapor_armor_duration(level)", "af.modifier = vapor_armor_ac(level)",
                              "af1->duration = vapor_armor_duration(level)"],
        "spell_frost_beam": ["int dam = frost_beam_damage(live_rolls, ch)",
                             "frost_beam_noshrug_roll(live_rolls) < frost_beam_noshrug_chance()",
                             "af.duration = frost_beam_paralysis(level)"],
        "spell_faerie_sight": ["pAff->duration < faerie_sight_duration(level)",
                               "pAff->duration = faerie_sight_duration(level)",
                               "af.duration = faerie_sight_duration(level)",
                               "if (faerie_sight_detects_invisible(ch))"],
        "spell_cold_snap": ["num = cold_snap_amount(live_rolls)", "af.duration = cold_snap_duration()",
                            "af2.duration = cold_snap_duration()", "af2.modifier = cold_snap_caster_ac(num)",
                            "cold_snap_slow_roll(live_rolls) < cold_snap_slow_chance()"],
        "spell_mass_fly": ["spell_fly(level, ch, 0, SPELL_TYPE_SPELL, gl->ch, 0)"],
        "wind_blade_attack_routine": ["int attacks = wind_blade_attacks(live_rolls, ch)",
                                      "af.modifier = wind_blade_hitroll(live_rolls)"],
        "grant_wind_blade": ["if (wind_blade_procs_ice_missile(ch))", "if (wind_blade_protects_from_cold(ch))",
                             "if (wind_blade_gives_coldshield(ch))", "if (wind_blade_procs_cone_of_cold(ch))",
                             "if (wind_blade_procs_frostbite(ch))", "if (wind_blade_procs_iceball(ch))",
                             "if (wind_blade_gives_air_aura(ch))", "blade->value[7] = wind_blade_proc_chance()"],
        "spell_windwalk": ["if (IS_PC(ch)) CharWait(ch, windwalk_pc_lag()); else CharWait(ch, windwalk_npc_lag());",
                           "distance = windwalk_distance(level, ch)", "!windwalk_unseen_roll(live_rolls)"],
        "spell_frost_beacon": ["set_obj_affected(beacon, frost_beacon_decay(live_rolls, level)"],
        "spell_vapor_strike": ["af.duration = vapor_strike_duration(level)",
                               "af.modifier = vapor_strike_hitroll(live_rolls)",
                               "af1->duration = vapor_strike_duration(level)"],
        "spell_forked_lightning": ["int num_missiles = forked_lightning_forks(ch)",
                                   "dam = forked_lightning_damage(live_rolls, level)",
                                   "dam = forked_lightning_saved(dam)"],
        "event_frost_bolt": ["dam = frost_bolt_damage(live_rolls, fdata->level)", "dam = frost_bolt_saved(dam)",
                             "++(fdata->round) < frost_bolt_later_hits()",
                             "add_event(event_frost_bolt, frost_bolt_next_delay()"],
        "spell_frost_bolt": ["level = frost_bolt_level(level)", "dam = frost_bolt_damage(live_rolls, level)",
                             "dam = frost_bolt_saved(dam)", "af.duration = frost_bolt_chill_duration()",
                             "af.modifier = frost_bolt_chill_strength()",
                             "add_event(event_frost_bolt, frost_bolt_first_delay()"],
        "spell_ethereal_form": ["int duration = ethereal_form_duration(ch)"],
        "spell_conjure_air": ["conjure_air_huge_roll(live_rolls) < conjure_air_huge_chance()",
                              "conjure_air_tempest_hit_points(ch, charisma)"],
        "spell_conjure_void_elemental": ["conjure_void_star_hit_points(live_rolls, GET_LEVEL(mob), charisma)"],
        "spell_conjure_ice_elemental": ["conjure_ice_frost_hit_points(live_rolls, GET_LEVEL(mob), charisma)"],
        "spell_storm_empathy": ["af.duration = storm_empathy_duration(level)"],
        "spell_greater_ethereal_recharge": ["healpoints = greater_ethereal_recharge_healing(live_rolls, ch)"],
        "spell_ethereal_recharge": ["healpoints = ethereal_recharge_healing(live_rolls, level)",
                                    "GET_HIT(victim) + ethereal_recharge_air_cap()"],
        "spell_arcane_whirlwind": ["arcane_whirlwind_roll(live_rolls) < level"],
        "spell_purge": ["dam = purge_damage(level, GET_LEVEL(victim))"],
        "spell_induce_tupor": ["if (induce_tupor_save_roll(live_rolls))",
                               "NewSaves(victim, SAVING_SPELL, induce_tupor_save_mod())",
                               "af.duration = induce_tupor_duration()",
                               "induce_tupor_forget_roll(live_rolls) && IS_NPC(victim)",
                               "add_event(event_tupor_wake, induce_tupor_wake_delay()"],
        "spell_tempest_terrain": ["add_event(event_tempest_terrain, tempest_terrain_delay()"],
        "event_tempest_terrain": ["add_event(event_tempest_terrain_bye, tempest_terrain_duration()"],
        "spell_single_tempest": ["dam = tempest_damage(live_rolls, level)",
                                 "takedown_chance = tempest_takedown_threshold(level)",
                                 "takedown_chance = tempest_takedown_flying(takedown_chance)",
                                 "takedown_chance = tempest_takedown_wind_tunnel(takedown_chance)",
                                 "takedown_chance = tempest_takedown_binding_wind(takedown_chance)",
                                 "takedown_chance = tempest_takedown_indoors(takedown_chance)",
                                 "(GET_C_LUK(victim) / 10) < tempest_luck_roll(live_rolls)",
                                 "takedown_chance = tempest_takedown_unlucky(takedown_chance)",
                                 "takedown_chance > tempest_takedown_roll(live_rolls)",
                                 "door = tempest_door_roll(live_rolls)", "door = tempest_flat_door_roll(live_rolls)",
                                 "dam = tempest_flying_damage(dam)", "dam = tempest_wind_tunnel_damage(dam)",
                                 "dam = tempest_binding_wind_damage(dam)", "dam = tempest_indoors_damage(dam)",
                                 "dam = tempest_player_damage(dam)", "dam = tempest_area_damage(dam)",
                                 "CharWait(victim, tempest_thrown_lag())"],
        "spell_tempest": ["cast_as_damage_area(ch, spell_single_tempest, level", "CharWait(ch, tempest_lag())"],
        "spell_wind_rage": ["af.duration = wind_rage_duration(level)", "af.modifier = wind_rage_wisdom_max(level)",
                            "if (wind_rage_quickens(level))", "af.modifier = wind_rage_spell_pulse(level)"],
        "spell_ethereal_alliance": ["af1.duration = ethereal_alliance_duration()",
                                    "af2.duration = ethereal_alliance_duration()"],
        "spell_comet": ["dam = comet_damage(live_rolls, level)", "dam = comet_star_damage(live_rolls, level)",
                        "dam = comet_failed_save(dam)"],
        "spell_cosmic_vacuum": ["success_chance = cosmic_success_chance(GET_LEVEL(ch), GET_LEVEL(victim))",
                                "success_chance < cosmic_success_roll(live_rolls)",
                                "af.duration = cosmic_saved_duration(level)",
                                "af.duration = cosmic_failed_duration(level)",
                                "af.modifier = cosmic_vacuum_ac(level, GET_AC(victim))",
                                "af.modifier = cosmic_vacuum_curse(level)"],
        "spell_single_supernova": ["dam = supernova_damage(live_rolls, level)", "dam = supernova_player_damage(dam)",
                                   "dam = supernova_area_damage(dam)",
                                   "int success_chance = cosmic_success_chance(GET_LEVEL(ch), GET_LEVEL(victim))",
                                   "success_chance < cosmic_success_roll(live_rolls)",
                                   "af.duration = cosmic_saved_duration(level)",
                                   "af.duration = cosmic_failed_duration(level)",
                                   "af.modifier = supernova_constitution(level)"],
        "spell_supernova": ["cast_as_damage_area(ch, spell_single_supernova, level",
                            "KnockOut(ch, supernova_knockout())"],
        "spell_ethereal_discharge": ["dam = ethereal_discharge_damage(level, ch)", "mod = ethereal_discharge_save_mod(",
                                     "!ethereal_discharge_strip_roll(live_rolls)"],
        "spell_planetary_alignment": ["affect_timer(ch, planetary_alignment_rest(), SPELL_PLANETARY_ALIGNMENT)",
                                      "planetary_alignment_roll(live_rolls) < planetary_alignment_perfect_chance()",
                                      "planetary_alignment_roll(live_rolls) < planetary_alignment_strong_chance()",
                                      "planetary_alignment_roll(live_rolls) < planetary_alignment_partial_chance()",
                                      "planetary_alignment_roll(live_rolls) < planetary_alignment_nudge_chance()",
                                      "af.modifier = planetary_alignment_perfect_modifier()",
                                      "af.modifier = planetary_alignment_strong_modifier()",
                                      "af.modifier = planetary_alignment_partial_modifier()",
                                      "af.modifier = planetary_alignment_nudge_modifier()",
                                      "af.duration = planetary_alignment_long_duration(level)",
                                      "af.duration = planetary_alignment_short_duration(level)"],
        "spell_single_polar_vortex": ["int dam = polar_vortex_damage(live_rolls, level)",
                                      "dam = polar_vortex_player_damage(dam)", "dam = polar_vortex_area_damage(dam)",
                                      "NewSaves(victim, SAVING_PARA, polar_vortex_save_mod())",
                                      "af.duration = polar_vortex_paralysis(live_rolls)"],
        "spell_polar_vortex": ["cast_as_damage_area(ch, spell_single_polar_vortex, level"],
        "spell_ethereal_travel": ["CharWait(gl->ch, ethereal_travel_member_lag())",
                                  "CharWait(ch, ethereal_travel_caster_lag())"],
        "spell_single_cosmic_rift": ["int dam = cosmic_rift_damage(live_rolls)", "dam = cosmic_rift_player_damage(dam)",
                                     "dam = cosmic_rift_area_damage(dam)",
                                     "GET_HIT(victim) < cosmic_rift_kill_threshold(dam)",
                                     "real_room(cosmic_rift_astral_room(live_rolls))"],
        "spell_cosmic_rift": ["cast_as_damage_area(ch, spell_single_cosmic_rift, level"],
        "static_discharge": ["level = static_discharge_level(level)",
                             "dam = static_discharge_damage(live_rolls, level, intensity)",
                             "dam += static_discharge_failed_save(dam, intensity)",
                             "dam = static_discharge_wet_damage(dam)"],
        "event_static_discharge": ["!static_discharge_trigger_roll(live_rolls, sdata->intensity)",
                                   "(++(sdata->round) > static_discharge_tries())",
                                   "add_event(event_static_discharge, static_discharge_interval()"],
        "spell_static_discharge": ["sdata.level = GET_LEVEL(ch)", "delay = static_discharge_interval()",
                                   "!static_discharge_trigger_roll(live_rolls, sdata.intensity)"],
        "event_razor_wind": ["dam = razor_wind_damage(live_rolls)", "dam = razor_wind_failed_save(dam)",
                             "add_event(event_razor_wind, razor_wind_interval()"],
        "spell_razor_wind": ["int duration = razor_wind_gusts()", "+ razor_wind_recast_gusts()",
                             "add_event(event_razor_wind, razor_wind_interval()"],
        "spell_iceflow_armor": ["int absorb = iceflow_armor_absorb(live_rolls, level)",
                                "absorb = iceflow_armor_doubled(absorb)", "af.duration = iceflow_armor_duration()"],
        "spell_negative_feedback_barrier": ["int absorb = negative_feedback_barrier_absorb(live_rolls, level)",
                                            "absorb = negative_feedback_barrier_doubled(absorb)",
                                            "af.duration = negative_feedback_barrier_duration()"],
        "spell_etheric_gust": ["int range = etheric_gust_range()", "dir = etheric_gust_direction_roll(live_rolls)",
                               "to_room = etheric_gust_zone_room_roll(live_rolls, victim)", "etheric_gust_room_limited(level)",
                               "how_close(victim->in_room, to_room, etheric_gust_limited_range())",
                               "CharWait(victim, etheric_gust_lag())"],
        "event_antimatter_collision": ["dam = antimatter_collision_damage(live_rolls)",
                                       "dam = antimatter_collision_failed_save(dam)",
                                       "add_event(event_antimatter_collision, antimatter_collision_interval()"],
        "spell_antimatter_collision": ["int duration = antimatter_collision_hits()",
                                       "+ antimatter_collision_recast_hits()",
                                       "add_event(event_antimatter_collision, antimatter_collision_interval()"],
        "event_arctic_blast": ["dam = arctic_blast_damage(live_rolls)", "dam = arctic_blast_failed_save(dam)",
                               "add_event(event_arctic_blast, arctic_blast_interval()"],
        "spell_arctic_blast": ["int duration = arctic_blast_blasts(level)",
                               "duration = arctic_blast_recast_blasts(*((int *)e1->data), duration)",
                               "add_event(event_arctic_blast, arctic_blast_first_delay()"],
        "spell_ice_spikes": ["int num_missiles = ice_spikes_count(live_rolls, level)",
                             "base_dam = missile_dam = ice_spikes_damage(live_rolls, level)",
                             "missile_dam = ice_spikes_saved(base_dam)"],
        "spell_wall_of_air": ["WALL_OF_AIR, level, wall_of_air_decay()"],
    },
    PALADINS: {
        "spell_vortex_of_fear": ["NewSaves(vict, SAVING_FEAR, vortex_of_fear_save_mod(level))",
                                 "int healpoints = vortex_of_fear_healing(live_rolls, num_hit)",
                                 "GET_MAX_HIT(gl->ch) - vortex_of_fear_cap_gap(live_rolls)"],
        "spell_righteous_aura": ["if (IS_PC(ch)) { af.duration = righteous_aura_pc_duration(); } else { af.duration = righteous_aura_npc_duration(); }",
                                 "add_event(event_righteous_aura_check, righteous_aura_interval()"],
        "event_righteous_aura_check": ["GET_ALIGNMENT(ch) >= righteous_aura_soulshield_alignment()",
                                       "if (IS_PC(ch)) { af.duration = righteous_aura_pc_blessing_duration(ch); } else { af.duration = righteous_aura_npc_blessing_duration(); }",
                                       "righteous_aura_dharma_delay(live_rolls)",
                                       "GET_ALIGNMENT(opponent) <= righteous_aura_taunt_alignment()",
                                       "add_event(event_righteous_aura_check, righteous_aura_interval()"],
        "spell_bleak_foeman": ["if (IS_PC(ch)) { af.duration = bleak_foeman_pc_duration(); } else { af.duration = bleak_foeman_npc_duration(); }",
                               "add_event(event_bleak_foeman_check, bleak_foeman_interval()"],
        "event_bleak_foeman_check": ["add_event(event_bleak_foeman_check, bleak_foeman_interval()"],
        "spell_dread_blade": ["af.duration = dread_blade_duration()"],
        "spell_blood_tithe": ["af.duration = blood_tithe_duration(ch)",
                              "add_event(event_blood_tithe, blood_tithe_interval()"],
        "event_blood_tithe": ["1.0 - blood_tithe_decay()", "add_event(event_blood_tithe, blood_tithe_interval()"],
        "blood_tithe_charge": ["GET_MAX_HIT(victim) * blood_tithe_hit_cap()"],
    },
    ALCHEMIST: {
        "spell_napalm": ["dam = napalm_damage(live_rolls, level)"],
        "spell_strong_acid": ["dam = strong_acid_damage(live_rolls, level)"],
        "spell_glass_bomb": ["dam = glass_bomb_damage(live_rolls, level)"],
        "spell_nitrogen": ["dam = nitrogen_damage(live_rolls, level)"],
        "spell_grease": ["afp->duration = grease_duration()", "afp->modifier = grease_slips(live_rolls)",
                         "af.duration = grease_duration()", "af.modifier = grease_slips(live_rolls)"],
    },
}

HARNESS = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "magic/spells.h"
#include "abilities/abilities.h"
#include "combat/damage.h"
#include "world/db.h"
#include <algorithm>
#include <cassert>
#include <climits>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <functional>
#include <string>

void randomize(uint64_t seed);

static int devotion;
int GET_CHAR_SKILL_P(P_char, int) { return devotion; }
float get_property(const char *, double fallback) { return (float)fallback; }
int get_property(const char *, int fallback) { return fallback; }
std::string fly_facts(P_char) { return "  Duration: fly's own page\n"; }
// lib/duris.properties values, which differ from the code's fallbacks.
float dam_factor[LAST_DF + 1];
static room_data rooms[1];
P_room world = rooms;
static zone_data zones[1];
zone_data *zone_table = zones;

FUNCTIONS

// The next draw after a roll; equal fingerprints after equal seeds mean equal draw counts.
static int fingerprint() { return number(0, INT_MAX); }

static void same(const char *name, const std::function<int()> &original,
                 const std::function<int(const Rolls &)> &shared, bool in_range = true) {
    const int a = shared(lowest_rolls), b = shared(highest_rolls);
    for (uint64_t seed = 1; seed <= 40; ++seed) {
        randomize(seed);
        const int expected = original(), expected_next = fingerprint();
        randomize(seed);
        const int actual = shared(live_rolls), actual_next = fingerprint();
        if (actual != expected || actual_next != expected_next ||
            (in_range && (actual < std::min(a, b) || actual > std::max(a, b)))) {
            std::fprintf(stderr, "%s: seed %d gave %d, expected %d in %d..%d\n", name,
                         (int)seed, actual, expected, a, b);
            std::abort();
        }
    }
}
#define SAME(original, shared) \
    same(#shared, [&] { return original; }, [&](const Rolls &rolls) { return shared; })

// The text holds these whole lines.
static bool contains(const std::string &text, const char *lines) {
    const size_t length = std::strlen(lines);
    assert(length && lines[length - 1] == '\n');
    for (size_t at = text.find(lines); at != std::string::npos; at = text.find(lines, at + 1))
        if (at == 0 || text[at - 1] == '\n')
            return true;
    std::fprintf(stderr, "missing \"%s\" in:\n%s", lines, text.c_str());
    return false;
}

struct Viewer { const char *name; uint m_class; int spec; int devotion; };
static const Viewer viewers[] = {
    { "warrior", CLASS_WARRIOR, 0, 0 },
    { "ethermancer", CLASS_ETHERMANCER, 0, 0 },
    { "tempest", CLASS_ETHERMANCER, SPEC_TEMPESTMAGUS, 0 },
    { "frost", CLASS_ETHERMANCER, SPEC_FROSTMAGUS, 0 },
    { "star", CLASS_ETHERMANCER, SPEC_STARMAGUS, 100 },
    { "air conjurer", CLASS_CONJURER, SPEC_AIR, 0 },
    { "paladin", CLASS_PALADIN, 0, 100 },
    { "anti-paladin", CLASS_ANTIPALADIN, 0, 50 },
};

static char_data viewer(const Viewer &v, int level) {
    char_data ch{};
    ch.player.m_class = v.m_class;
    ch.player.spec = v.spec;
    ch.player.level = level;
    ch.curr_stats.Cha = 100;
    ch.points.base_hit = 500;
    ch.points.max_hit = 1000;
    devotion = v.devotion;
    return ch;
}

struct Page { const char *name; AbilityFacts facts; };
static const Page pages[] = {
PAGES
};

int main() {
    dam_factor[DF_PROTECTION] = 0.85f;
    dam_factor[DF_ELSHIELDRED] = 0.75f;
    dam_factor[DF_PHANTFORM] = 1.5f;
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
            P_char ch = &caster;
            const int charisma = 111;
            SAME(GET_LEVEL(ch) * 14 + number(10, 20), frost_beam_damage(rolls, ch));
            SAME(number(0, 99), frost_beam_noshrug_roll(rolls));
            SAME(dice(10, 5), cold_snap_amount(rolls));
            SAME(number(0, 100), cold_snap_slow_roll(rolls));
            SAME(BOUNDED(2, number(1, GET_LEVEL(ch) / 10), 4), wind_blade_attacks(rolls, ch));
            SAME(number(5, 15), wind_blade_hitroll(rolls));
            SAME(dice(level / 7, 2) * WAIT_MIN, frost_beacon_decay(rolls, level));
            SAME(number(0, 2), frost_beacon_alert_roll(rolls));
            SAME(dice(3, 3) + number(0, 2), vapor_strike_hitroll(rolls));
            SAME(2 * level + number(30, 64), forked_lightning_damage(rolls, level));
            SAME(4 * (number(6, 9) + (frost_bolt_level(level) / 3)),
                 frost_bolt_damage(rolls, frost_bolt_level(level)));
            const int mlvl = (level / 5) * 2;
            SAME(number(mlvl, mlvl * 3), conjured_elemental_roll(rolls, mlvl));
            for (int mob : { 10, 22, 45, 51 }) {
                SAME(dice(mob / 2, 10) + mob + charisma, conjured_elemental_hit_points(rolls, mob, charisma));
                SAME(dice(mob / 2, 40) + mob + charisma, conjure_void_star_hit_points(rolls, mob, charisma));
                SAME(dice(mob / 2, 50) + mob + charisma, conjure_ice_frost_hit_points(rolls, mob, charisma));
            }
            SAME(number(10, 100), conjured_elemental_temper_roll(rolls));
            SAME((4 + number(1, 6)) * WAIT_SEC, conjured_elemental_poof(rolls));
            SAME(number(0, 100), conjure_air_huge_roll(rolls));
            SAME(number(150, (GET_LEVEL(ch) * 5)), greater_ethereal_recharge_healing(rolls, ch));
            // MIN() rolls again when the dice do not clear the cap, so that second roll can pass it.
            same("ethereal_recharge_healing", [&] { return std::min(150, dice(5, level)); },
                 [&](const Rolls &rolls) { return ethereal_recharge_healing(rolls, level); }, level * 5 <= 150);
            SAME(number(0, 100), arcane_whirlwind_roll(rolls));
            SAME(number(0, 9), induce_tupor_save_roll(rolls));
            SAME(number(0, 2), induce_tupor_forget_roll(rolls));
            SAME(level * 5 + number(1, 20), tempest_damage(rolls, level));
            SAME(dice(((int)(level / 3) + 5), 6) * 4, comet_damage(rolls, level));
            SAME(dice(((int)(level / 3) + 5), 8) * 4 + 40, comet_star_damage(rolls, level));
            SAME(120 + level * 6 + number(1, 40), supernova_damage(rolls, level));
            SAME(number(0, 9), ethereal_discharge_strip_roll(rolls));
            SAME(number(0, 5), windwalk_unseen_roll(rolls));
            SAME(number(1, 10), conjured_elemental_late_death_roll(rolls));
            SAME(number(1, 100), tempest_luck_roll(rolls));
            SAME(number(0, 100), tempest_takedown_roll(rolls));
            SAME(number(0, 9), tempest_door_roll(rolls));
            SAME(number(0, 3), tempest_flat_door_roll(rolls));
            SAME(number(1, 100), cosmic_success_roll(rolls));
            SAME(number(ASTRAL_VNUM_BEGIN, ASTRAL_VNUM_END), cosmic_rift_astral_room(rolls));
            SAME(number(0, 3), etheric_gust_direction_roll(rolls));
            zones[0].real_bottom = 10;
            zones[0].real_top = 90;
            SAME(number(zone_table[world[caster.in_room].zone].real_bottom,
                        zone_table[world[caster.in_room].zone].real_top),
                 etheric_gust_zone_room_roll(rolls, ch));
            SAME(number(0, 4), dread_blade_spell_roll(rolls));
            SAME(number(1, 100), wall_of_air_roll(rolls));
            SAME(number(0, 100), planetary_alignment_roll(rolls));
            SAME(dice(level, 6) * 3, polar_vortex_damage(rolls, level));
            SAME(WAIT_SEC * number(1, 3), polar_vortex_paralysis(rolls));
            SAME(dice(number(25, 75), 4) * 4, cosmic_rift_damage(rolls));
            for (int intensity : { 1, 2, 3, 4, 5, 6 }) {
                SAME((dice(((level / 5) + 5) * intensity, 5) * 3), static_discharge_damage(rolls, level, intensity));
                SAME(number(0, 4 - intensity), static_discharge_trigger_roll(rolls, intensity));
            }
            SAME(180 + number(-40, 40), razor_wind_damage(rolls));
            SAME((level / 4) + number(1, 4), iceflow_armor_absorb(rolls, level));
            SAME((level / 4) + number(1, 4), negative_feedback_barrier_absorb(rolls, level));
            SAME(200 + number(-40, 40), antimatter_collision_damage(rolls));
            SAME(180 + number(-40, 40), arctic_blast_damage(rolls));
            SAME(number(3, 4) + (level > 50 ? 1 : 0), ice_spikes_count(rolls, level));
            SAME((3 * level) + number(0, level), ice_spikes_damage(rolls, level));
            for (int fled : { 0, 1, 2, 5 })
                SAME(70 + number(0, 10) + dice(fled, 10), vortex_of_fear_healing(rolls, fled));
            SAME(number(1, 4), vortex_of_fear_cap_gap(rolls));
            SAME((PULSE_VIOLENCE * number(3, 6)), righteous_aura_dharma_delay(rolls));
            SAME(number(0, 32), dread_blade_proc_roll(rolls));
            SAME(number(1, GET_LEVEL(ch)), dread_blade_spell_level(rolls, ch));
            SAME(MIN(40, level) * 4 + number(0, level), napalm_damage(rolls, level));
            SAME((int)(10.5 * MIN(level, 50)) + number(1, 25), strong_acid_damage(rolls, level));
            SAME(6 * MIN(level, 45) + number(1, 25), glass_bomb_damage(rolls, level));
            SAME(4 * MIN(26, level) + number(0, 9), nitrogen_damage(rolls, level));
            SAME(number(1, 4), grease_slips(rolls));
            SAME(number(0, 2), grease_slip_roll(rolls));
            SAME(number(0, 115), grease_agility_roll(rolls));
        }

    // The walker sizes the wall's proc reads.
    const struct { int size, chance, fall; } walls[] = {
        { SIZE_NONE, 15, 20 }, { SIZE_TINY, 15, 20 }, { SIZE_SMALL, 15, 20 }, { SIZE_MEDIUM, 25, 15 },
        { SIZE_LARGE, 50, 10 }, { SIZE_HUGE, 50, 10 }, { SIZE_GIANT, 70, 0 }, { SIZE_GARGANTUAN, 70, 0 },
        { SIZE_DEFAULT, 0, 100 },
    };
    for (const auto &wall : walls) {
        int chance = -1, fall = -1;
        wall_of_air_chances(wall.size, chance, fall);
        assert(chance == wall.chance && fall == wall.fall);
    }

    {
        char_data walker{};
        walker.curr_stats.Agi = 100;
        walker.curr_stats.Str = 60;
        assert(wall_of_air_stat_bonus(&walker) == 3);
    }
    assert(conjured_elemental_charm(4) == 100);
    assert(conjured_elemental_death_delay(1, 1) == PULSES_IN_TICK + 2 * WAIT_MIN);
    assert(conjured_elemental_death_delay(100, 10) == 100 * PULSES_IN_TICK + 11 * WAIT_MIN);
    assert(arctic_blast_recast_blasts(2, 6) == 7);
    // The takedown changes as the handler wrote them, the binding wind's included.
    assert(tempest_takedown_unlucky(14.0) == 7.0);
    assert(tempest_takedown_flying(14.0) == 14.0 * 1.5);
    assert(tempest_takedown_wind_tunnel(14.0) == 14.0 * 1.3);
    assert(tempest_takedown_indoors(14.0) == 14.0 / 1.1);
    { double chance = 14.0; chance /= 1.3; assert(tempest_takedown_binding_wind(14.0) == chance); }

    // The bounds of the chance cosmic vacuum and supernova roll against number(1, 100).
    assert(cosmic_success_chance(1, 60) == 50 && cosmic_success_chance(60, 1) == 80);
    assert(cosmic_success_chance(50, 50) == 70);
    assert(cosmic_vacuum_ac(56, 0) == 56 && cosmic_vacuum_ac(56, 90) == 10);

    // Exact pages at level 56 for an ethermancer without a specialization.
    char_data ch = viewer(viewers[1], 56);
    assert(vapor_armor_facts(&ch) == "  Duration: 28-29 game hours (35-36.25 minutes) at your level, 56\n"
                                     "  Armor class: -70\n"
                                     "  Recasting it only renews the duration.\n"
                                     "  It does nothing to a target with another armor-type spell.\n");
    assert(contains(frost_beam_facts(&ch), "  Cold damage: 794-804 at your level, 56\n"
                                           "  Cannot be shrugged: 50 in 100\n"
                                           "  Minor paralysis: 42 seconds if the target lives and fails a paralysis save\n"
                                           "  Globes and spirit wards do not stop it.\n"));
    assert(contains(faerie_sight_facts(&ch), "  Duration: 28-29 game hours (35-36.25 minutes) at your level, 56\n"
                                             "  Detect invisibility: yes, at your level\n"));
    assert(cold_snap_facts(&ch) == "  Target's armor class: 10-50 worse\n"
                                   "  Your armor class: -50 to -10, unless you already have it\n"
                                   "  Duration: 10-11 game hours (12.5-13.75 minutes)\n"
                                   "  Chance to also cast slow: 10 in 101\n"
                                   "  It does nothing to a target that already has it.\n");
    assert(contains(mass_fly_facts(&ch), "  It does nothing outside a group.\n  Duration: fly's own page\n"));
    assert(wind_blade_facts(&ch) == "  Extra attacks if cast in combat with it wielded: 2-4\n"
                                    "  Hitroll during those attacks: +5 to +15\n"
                                    "  Blade's spell: shattering iceball at your level, 1 in 40 hits\n"
                                    "  Cold shield while wielded: 25% less cold spell damage\n"
                                    "  Wielding it gives you an air aura.\n");
    assert(contains(windwalk_facts(&ch), "  Range: 75 rooms by exits, either way, at your level, 56\n"
                                         "  Your lag: 9 seconds, even if it fails\n"
                                         "  Chance each onlooker misses you going or coming: 1 in 6\n"));
    assert(contains(frost_beacon_facts(&ch), "  Beacon lasts: 8 minutes to 16 minutes at your level, 56\n"
                                             "  Warns you of a player walking out of its room: 2 in 3\n"));
    assert(contains(vapor_strike_facts(&ch), "  Hitroll: +3-11\n"));
    assert(contains(forked_lightning_facts(&ch), "  Forks: 4 at your level, 56\n"
                                                 "  Lightning damage per fork: 142-176\n"
                                                 "  If the target saves, once for all forks: 94-117\n"));
    assert(contains(frost_bolt_facts(&ch), "  Cold damage per hit: 64-76 at level 30, your level up to 30\n"
                                           "  If the target saves, each hit: 42-50\n"
                                           "  Hits: 3: on casting, 4 seconds later, then 3.25 seconds later\n"
                                           "  Stopped by: any globe of invulnerability or spirit ward\n"
                                           "  If its first hit lands and a second save fails: strength -1\n"
                                           "  That strength loss lasts: 2-3 game hours (2.5-3.75 minutes)\n"));
    assert(conjure_air_facts(&ch) == "  Huge elemental: 15 in 101\n"
                                     "  Elemental's level: 22-45 at your level, 56\n"
                                     "  Its hit points: 144-376 with your charisma\n"
                                     "  Its hitroll and damroll: 7-15\n"
                                     "  It dies after its charm, plus: 2 minutes to 11 minutes\n"
                                     "  Its charm depends on its intelligence; a globe of shadows or unholy\n"
                                     "  alliance makes the charm permanent, and then it does not die.\n"
                                     "  Only one elemental at a time; safe rooms block it.\n");
    assert(contains(storm_empathy_facts(&ch), "  Duration: 56-57 game hours (70-71.25 minutes) at your level, 56\n"
                                              "  Cold and lightning spell damage: 15% less\n"
                                              "  Lightning breath damage: 20% less\n"));
    assert(contains(greater_ethereal_recharge_facts(&ch), "  Healing: 150-280 at your level, 56\n"));
    assert(contains(ethereal_recharge_facts(&ch), "  Healing: 5-150 at your level, 56\n"
                                                  "  It also cures blindness.\n"));
    assert(contains(arcane_whirlwind_facts(&ch), "  Chance to steal each spell: 56 in 101 at your level, 56\n"));
    assert(contains(purge_facts(&ch), "  Damage: 1680 at your level, 56, less 10 per target level\n"));
    assert(contains(induce_tupor_facts(&ch), "  Sleep: 20 seconds\n  Target wakes after: 20 seconds\n"
                                             "  Chance of no save: 1 in 10\n"
                                             "  Otherwise a spell save: +5, harder\n"
                                             "  Chance a slept NPC forgets its enemies: 2 in 3\n"));
    assert(tempest_terrain_facts(&ch) == "  Takes hold after: 8 seconds\n  Lasts: 80 seconds\n"
                                         "  Not in towns, on roads, indoors or on the air plane.\n");
    assert(contains(tempest_facts(&ch), "  Cold damage: 281-300 to each target at your level, 56\n"
                                        "  Against a player: 140-150\n"
                                        "  Against a flying target: 337-360\n"
                                        "  With a wind tunnel in the room: 337-360\n"
                                        "  With a binding wind in the room: 234-250\n"
                                        "  Indoors: 140-150\n"
                                        "  Room-throw threshold: 14 of a 0-100 roll\n"
                                        "  It becomes if flying, or with a wind tunnel: 21, 18.2\n"
                                        "  With a binding wind, or indoors: 10.8, 12.7\n"
                                        "  Halved unless the target's luck over 10 reaches a roll of: 1-100\n"
                                        "  It needs an open exit in a random direction.\n"
                                        "  A thrown target's lag: 4 seconds\n"
                                        "  Your lag: 2.25 seconds\n"));
    assert(wind_rage_facts(&ch) == "  Duration: 18-19 game hours (22.5-23.75 minutes) at your level, 56\n"
                                   "  Maximum wisdom: +14\n  Spell pulse: -2\n");
    assert(contains(ethereal_alliance_facts(&ch), "  Duration: 32-33 game hours (40-41.25 minutes)\n"
                                                  "  Spell damage to either of you: 50% less\n"
                                                  "  Share of it the other ally takes: 50%\n"));
    assert(contains(comet_facts(&ch), "  Damage: 92-552 at your level, 56\n"
                                      "  If the target fails its save: 110-662\n"));
    assert(contains(cosmic_vacuum_facts(&ch), "  Chance to work: 50-80%, higher the more you outlevel the target\n"
                                              "  Lasts if the target saves: 18 seconds\n"
                                              "  Lasts if it fails: 5-6 game hours (6.25-7.5 minutes)\n"
                                              "  Armor class: 56 worse at your level, 56, at most to 100\n"
                                              "  All saving throws: 9 worse\n"));
    assert(contains(supernova_facts(&ch), "  Damage: 457-496 to each target at your level, 56\n"
                                          "  Against a player: 228-248\n"
                                          "  Chance a survivor also burns: 50-80%, higher the more you outlevel the target\n"
                                          "  Its constitution: -5\n"));
    assert(contains(supernova_facts(&ch), "  You are then knocked out: 0.25 seconds, left prone\n"));
    assert(contains(ethereal_discharge_facts(&ch), "  Damage per spell stripped: 28\n"
                                                   "  Save against each strip: +0 with your devotion, harder\n"));
    assert(planetary_alignment_facts(&ch) == "  First roll, 11 in 101: all maximum stats +15\n"
                                             "  Else 31 in 101: all maximum stats +10\n"
                                             "  Maximum stats last: 14-15 game hours (17.5-18.75 minutes)\n"
                                             "  Else 51 in 101: all stats +10\n"
                                             "  Else 80 in 101: all stats +5\n"
                                             "  Stats last: 11-12 game hours (13.75-15 minutes)\n"
                                             "  Otherwise it fails.\n"
                                             "  Rest between casts: 3 minutes\n");
    assert(contains(polar_vortex_facts(&ch), "  Cold damage: 168-1008 to each target at your level, 56\n"
                                             "  Against a player: 84-504\n"
                                             "  Major paralysis first: 1 second to 3 seconds\n"
                                             "  Its paralysis save: +2, harder\n"));
    assert(contains(ethereal_travel_facts(&ch), "  Your lag in a group: 10 seconds\n"
                                                "  Lag of each group member moved: 8 seconds\n"
                                                "  Travelling alone has no lag.\n"));
    assert(contains(cosmic_rift_facts(&ch), "  Damage: 100-1200 to each target\n"
                                            "  Against a player: 50-600\n"
                                            "  Dies outright below: 25-300 hit points, a quarter of its damage\n"));
    assert(contains(static_discharge_facts(&ch), "  Lightning damage: 42-210 at level 46, your level up to 46\n"
                                                 "  If the target fails its save: 46-231\n"
                                                 "  Against a wet target: 63-315 before its save\n"
                                                 "  Goes off: 1 in 4 every 4 seconds, at most 24 seconds\n"));
    assert(contains(static_discharge_facts(&ch), "  If recast first, two casts of yours: 84-420\n"));
    assert(contains(static_discharge_facts(&ch), "  Stopped by: globe of invulnerability, greater spirit ward\n"));
    assert(contains(razor_wind_facts(&ch), "  Cold damage per gust: 140-220\n"
                                           "  If the target fails its save, each gust: 168-264\n"
                                           "  Gusts: 3, 2.25 seconds apart, the first after 2.25 seconds\n"
                                           "  Recasting while it blows adds: 2 gusts\n"));
    assert(contains(iceflow_armor_facts(&ch), "  Hits absorbed: 30-36 at your level, 56\n"
                                              "  Duration: 8-9 game hours (10-11.25 minutes)\n"
                                              "  Each melee hit on you: 46 less\n"
                                              "  Then, if over 10 is left: 75% of that\n"
                                              "  It applies before the raw damage modifiers.\n"
                                              "  Hits that ignore reductions go through it and use up nothing.\n"
                                              "  An attacker's fist of dragon can do the same.\n"));
    assert(contains(negative_feedback_barrier_facts(&ch), "  Hits absorbed: 30-36 at your level, 56\n"
                                                          "  Duration: 8-9 game hours (10-11.25 minutes)\n"
                                                          "  Each melee hit on you: 46 less\n"
                                              "  Then, if over 10 is left: 75% of that\n"
                                              "  It applies before the raw damage modifiers.\n"
                                              "  Hits that ignore reductions go through it and use up nothing.\n"
                                              "  An attacker's fist of dragon can do the same.\n"));
    assert(contains(ethereal_form_facts(&ch), "  Elemental spell damage to you: 50% more\n"));
    assert(contains(etheric_gust_facts(&ch), "  Your lag on arrival: 3 seconds\n"
                                             "  On the world map: up to 5 rooms away\n"
                                             "  In a limited-teleport zone: within 5 rooms, or fails\n"));
    assert(contains(etheric_gust_facts(&ch), "  No-teleport rooms, hometowns and ocean block it.\n"));
    assert(contains(antimatter_collision_facts(&ch), "  Negative damage per hit: 160-240\n"
                                                     "  If the target fails its save, each hit: 192-288\n"
                                                     "  Hits: 3, 4.5 seconds apart, the first after 4.5 seconds\n"));
    assert(contains(arctic_blast_facts(&ch), "  Cold damage per blast: 140-220\n"
                                             "  If the target fails its save, each blast: 168-264\n"
                                             "  Blasts: 6 at your level, 56\n"
                                             "  The first comes after: 2.25 seconds, the rest 4.5 seconds apart\n"
                                             "  Recasting while it blows adds: 5 blasts\n"));
    assert(contains(ice_spikes_facts(&ch), "  Spikes: 4-5 at your level, 56\n"
                                           "  Cold damage per spike: 168-224, one roll for all of them\n"
                                           "  If the target saves, per spike: 112-149\n"));
    assert(contains(wall_of_air_facts(&ch), "  Wall lasts: 7 minutes 30 seconds\n"
                                            "  Breaking through: 15% small, 25% medium, 50% large, 70% giant\n"
                                            "  Else knocked down: 20% small, 15% medium, 10% large, 0% giant\n"));
    assert(contains(vortex_of_fear_facts(&ch), "  Fear save: +2, harder at your level, 56\n"));
    assert(contains(vortex_of_fear_facts(&ch), "  So do elites, guardians, dreadlords, the fearless, those under\n"
                                               "  indomitability, greater NPC races from level 51, some raging berserkers.\n"));
    assert(contains(vortex_of_fear_facts(&ch), "  Your group's healing: 71-90\n"
                                               "  Each target fleeing after the first adds: 1-10\n"
                                               "  Healing stops below maximum hit points by: 1-4\n"));
    assert(contains(bleak_foeman_facts(&ch), "  Duration: 5-6 game hours (6.25-7.5 minutes)\n"
                                             "  Foeman checks: every 1 second\n"));
    assert(contains(dread_blade_facts(&ch), "  Duration: 16-17 game hours (20-21.25 minutes)\n"
                                            "  Chance on each hit in a fight: 1 in 33\n"
                                            "  It casts at level: 1-56\n"
                                            "  Chance of each of disease, blindness, wither, harm, unholy word: 1 in 5\n"));
    assert(contains(dread_blade_facts(&ch), "  Target's spell save against it: +15, harder\n"));
    assert(contains(napalm_facts(&ch), "  Fire damage: 160-216 from a flask mixed at your level, 56\n"));
    assert(contains(strong_acid_facts(&ch), "  Acid damage: 526-550 from a flask mixed at your level, 56\n"));
    assert(contains(glass_bomb_facts(&ch), "  Damage: 271-295 from a flask mixed at your level, 56\n"
                                           "  It cannot be shrugged, and globes and spirit wards do not stop it.\n"));
    assert(contains(nitrogen_facts(&ch), "  Cold damage: 104-113 from a flask mixed at your level, 56\n"
                                         "  It cannot be shrugged, and globes and spirit wards do not stop it.\n"));
    assert(contains(grease_facts(&ch), "  Duration: 1-2 game hours (1.25-2.5 minutes)\n"
                                       "  Slips before it comes off: 2-5\n"
                                       "  Chance each move slips: 1 in 3, if the target's agility is below\n"
                                       "  Agility check: a roll of 0-115\n"));

    // Level boundaries and low levels.
    ch = viewer(viewers[1], 1);
    assert(contains(ethereal_discharge_facts(&ch), "  Damage per spell stripped: 0 (none below 1 lands)\n"));
    assert(contains(cosmic_vacuum_facts(&ch), "  All saving throws: 0 worse\n"));
    assert(contains(vortex_of_fear_facts(&ch), "  Fear save: -3, easier at your level, 1\n"));
    assert(contains(frost_beacon_facts(&ch), "  Beacon lasts: 1 minute to 2 minutes at your level, 1\n"));
    assert(contains(purge_facts(&ch), "  Damage: 30 at your level, 1, less 10 per target level\n"));
    assert(contains(wind_blade_facts(&ch), "  Extra attacks if cast in combat with it wielded: 2\n"));
    assert(wind_blade_facts(&ch).find("Blade's spell") == std::string::npos);
    assert(wind_blade_facts(&ch).find("cold spell damage") == std::string::npos);
    assert(contains(conjure_air_facts(&ch), "  If it outlevels you, by charisma: attacks, gone in 5 seconds to 10 seconds\n"));
    ch = viewer(viewers[1], 10);
    assert(contains(greater_ethereal_recharge_facts(&ch), "  Healing: 50-150 at your level, 10\n"));
    ch = viewer(viewers[1], 20);
    assert(ethereal_recharge_facts(&ch).find("rolled twice") == std::string::npos);
    ch = viewer(viewers[1], 30);
    assert(ethereal_recharge_facts(&ch).find("rolled twice") == std::string::npos);
    ch = viewer(viewers[1], 31);
    assert(ethereal_recharge_facts(&ch).find("rolled twice") == std::string::npos);
    ch = viewer(viewers[1], 35);
    assert(contains(faerie_sight_facts(&ch), "  Detect invisibility: not at your level\n"));
    ch = viewer(viewers[1], 50);
    assert(wind_rage_facts(&ch).find("Spell pulse") == std::string::npos);
    assert(contains(ice_spikes_facts(&ch), "  Spikes: 3-4 at your level, 50\n"));
    ch = viewer(viewers[1], 51);
    assert(contains(wind_rage_facts(&ch), "  Spell pulse: -1\n"));
    assert(contains(ice_spikes_facts(&ch), "  Spikes: 4-5 at your level, 51\n"));
    ch = viewer(viewers[1], 52);
    assert(contains(forked_lightning_facts(&ch), "  Forks: 3 at your level, 52\n"));
    ch = viewer(viewers[1], 53);
    assert(contains(forked_lightning_facts(&ch), "  Forks: 4 at your level, 53\n"));
    ch = viewer(viewers[1], 60);
    assert(etheric_gust_facts(&ch).find("No-teleport") == std::string::npos);
    ch = viewer(viewers[1], 40);
    assert(contains(arctic_blast_facts(&ch), "  Blasts: 3 at your level, 40\n"));
    assert(contains(wind_blade_facts(&ch), "  Blade's spell: cone of cold at your level, 1 in 40 hits\n"));
    ch = viewer(viewers[1], 26);
    assert(contains(wind_blade_facts(&ch), "  Cold protection while wielded: 15% less cold spell damage\n"));
    ch = viewer(viewers[1], 31);
    assert(contains(wind_blade_facts(&ch), "  Cold shield while wielded: 25% less cold spell damage\n"));
    assert(wind_blade_facts(&ch).find("Cold protection") == std::string::npos);
    ch = viewer(viewers[1], 2);
    assert(tempest_facts(&ch).find("binding wind, or") == std::string::npos); // a threshold of 0

    // The specializations the pages read.
    ch = viewer(viewers[2], 56); // tempest magus
    assert(contains(conjure_air_facts(&ch), "  Huge elemental: always, as a tempest magus\n"
                                            "  Elemental's level: 51 at your level, 56\n"
                                            "  Its hit points: 723 with your base hit points and charisma\n"
                                            "  Its hitroll and damroll: 17\n"));
    assert(contains(windwalk_facts(&ch), "  Range: 90 rooms by exits, either way, at your level, 56\n"));
    ch = viewer(viewers[3], 56); // frost magus
    assert(contains(frost_beam_facts(&ch), "  Cannot be shrugged: always, as a frost magus\n"));
    assert(contains(conjure_ice_elemental_facts(&ch), "  Elemental's level: 51 at your level, 56\n"
                                                      "  Its hit points: 187-1412 with your charisma\n"));
    assert(contains(conjure_void_elemental_facts(&ch), "  Its hit points: 144-376 with your charisma\n"));
    ch = viewer(viewers[4], 56); // star magus, devotion 100
    assert(contains(comet_facts(&ch), "  Damage: 132-776 at your level, 56\n"
                                      "  If the target fails its save: 158-931\n"));
    assert(contains(conjure_void_elemental_facts(&ch), "  Its hit points: 187-1162 with your charisma\n"));
    assert(contains(conjure_ice_elemental_facts(&ch), "  Its hit points: 144-376 with your charisma\n"));
    assert(contains(ethereal_form_facts(&ch), "  Duration: 23-24 game hours (28.75-30 minutes) with your level and devotion\n"));
    assert(contains(ethereal_discharge_facts(&ch), "  Damage per spell stripped: 38\n"
                                                   "  Save against each strip: +4 with your devotion, harder\n"));
    ch = viewer(viewers[5], 56); // air conjurer
    assert(contains(ethereal_recharge_facts(&ch), "  On your own air form: at most 100 hit points\n"));
    ch = viewer(viewers[6], 56); // paladin, devotion 100
    assert(righteous_aura_facts(&ch) == "  Duration: 5-6 game hours (6.25-7.5 minutes)\n"
                                        "  Aura checks: every 1 second\n"
                                        "  A bleak foeman in the room attacks you when the aura checks.\n"
                                        "  Soulshield at alignment 950 up: 25-26 game hours (31.25-32.5 minutes)\n"
                                        "  Holy dharma it adds to a soulshield: 25-26 game hours (31.25-32.5 minutes)\n"
                                        "  Dharma's first effect after: 12 seconds to 24 seconds\n"
                                        "  An opponent turns on you at alignment: -500 or lower\n");
    ch = viewer(viewers[7], 56); // anti-paladin, devotion 50
    assert(contains(blood_tithe_facts(&ch), "  Duration: 20-21 game hours (25-26.25 minutes) with your devotion\n"
                                            "  Your groupmates' damage bonus: up to 12%\n"
                                            "  Against players: 50% of that\n"));
    assert(contains(blood_tithe_facts(&ch), "  Most malice from one hit: 5% of your maximum hit points\n"
                                            "  The meter decays by: 25% every 4 seconds\n"
                                            "  More than 3 player groupmates here share a smaller bonus.\n"));
    puts("PASS: batch 7 shared rolls match the old code and stay in range, facts never roll");
}
'''


def statics_of(file):
    """The batch's static function names in one file."""
    text = source(file).read_text(encoding="utf-8", errors="replace")
    names = re.findall(r"^static [\w:]+ (\w+)\(", text, re.M)
    return text, [n for n in names if n.startswith(PREFIXES[file]) and n not in OLDER]


def check_sources():
    for file, handlers in HANDLER_CALLS.items():
        code = strip_comments(source(file).read_text(encoding="utf-8", errors="replace"))
        for handler, calls in handlers.items():
            bodies = function_bodies(code, rf"\b(void|bool)\s+{handler}\s*\(")
            assert len(bodies) == 1, handler
            body = re.sub(r"\s+", " ", bodies[0])
            for call in calls:
                assert call in body, f"{handler} does not call {call}"
    code = strip_comments(source(ETHERMANCER).read_text(encoding="utf-8", errors="replace"))
    # Multi-path handlers: each helper sits on its own branch.
    beam = re.sub(r"\s+", " ", function_bodies(code, r"\bvoid\s+spell_frost_beam\s*\(")[0])
    assert beam.index("GET_SPEC(ch, CLASS_ETHERMANCER, SPEC_FROSTMAGUS)") < beam.index("frost_beam_noshrug_roll")
    comet = re.sub(r"\s+", " ", function_bodies(code, r"\bvoid\s+spell_comet\s*\(")[0])
    assert re.search(r"if \(!GET_SPEC\(ch, CLASS_ETHERMANCER, SPEC_STARMAGUS\)\) \{ // Fireball|"
                     r"if \(!GET_SPEC\(ch, CLASS_ETHERMANCER, SPEC_STARMAGUS\)\) \{ dam = comet_damage", comet)
    assert comet.index("comet_damage(live_rolls") < comet.index("comet_star_damage(live_rolls")
    vacuum = re.sub(r"\s+", " ", function_bodies(code, r"\bvoid\s+spell_cosmic_vacuum\s*\(")[0])
    assert vacuum.index("cosmic_saved_duration") < vacuum.index("cosmic_failed_duration")
    assert "if (NewSaves(victim, SAVING_SPELL, mod)) { af.flags = AFFTYPE_SHORT;" in vacuum
    travel = re.sub(r"\s+", " ", function_bodies(code, r"\bvoid\s+spell_ethereal_travel\s*\(")[0])
    assert travel.index("if (ch->group)") < travel.index("ethereal_travel_member_lag")
    assert travel.count("CharWait") == 2
    for handler, level_call in (("spell_conjure_air", "conjured_elemental_spec_level(level)"),
                                ("spell_conjure_void_elemental", "conjured_elemental_spec_level(level)"),
                                ("spell_conjure_ice_elemental", "conjured_elemental_spec_level(level)")):
        body = function_bodies(code, rf"\bvoid\s+{handler}\s*\(")[0]
        for call in (level_call, "conjured_elemental_level(lvl)", "conjured_elemental_base(level)",
                     "conjured_elemental_roll(live_rolls, mlvl)", "conjured_elemental_roll_bonus(GET_LEVEL(mob))",
                     "conjured_elemental_temper_roll(live_rolls)", "conjured_elemental_poof(live_rolls)",
                     "conjured_elemental_hit_points(live_rolls, GET_LEVEL(mob), charisma)",
                     "int charisma = conjured_elemental_charisma(ch)",
                     "conjured_elemental_charm(STAT_INDEX(GET_C_INT(mob)))",
                     "conjured_elemental_late_death_roll(live_rolls)",
                     "conjured_elemental_death_delay("):
            assert call in body, f"{handler} does not call {call}"
    # Ethermancer summons may be cast in combat (#1003); timing and specialization stay.
    skills = re.sub(r"\s+", " ", strip_comments(source("skills.c").read_text(encoding="utf-8", errors="replace")))
    for name, spell, handler, circle, spec in (
            ("conjure air", "SPELL_CONJURE_AIR", "spell_conjure_air", 5, "SPEC_TEMPESTMAGUS"),
            ("conjure void", "SPELL_CONJURE_VOID", "spell_conjure_void_elemental", 7, "SPEC_STARMAGUS"),
            ("conjure ice", "SPELL_CONJURE_ICE", "spell_conjure_ice_elemental", 7, "SPEC_FROSTMAGUS")):
        assert (f'SPELL_CREATE("{name}", {spell}, PULSE_SPELLCAST * 3, TAR_IGNORE, {handler}); '
                f"SPEC_SPELL_ADD(CLASS_ETHERMANCER, {circle}, {spec});") in skills, name
    # Each property reads its own key.
    for function, key in (("tempest_player_damage", "spell.area.damage.to.pc"),
                          ("tempest_area_damage", "spell.area.damage.factor.squallTempest"),
                          ("supernova_area_damage", "spell.area.damage.factor.superNova"),
                          ("polar_vortex_area_damage", "spell.area.damage.factor.polarVortex"),
                          ("cosmic_rift_area_damage", "spell.area.damage.factor.cosmicRift")):
        assert f'"{key}"' in function_bodies(code, rf"\bstatic\s+\w+\s+{function}\s*\(")[0], function
    # The object procs read the numbers on the pages.
    procs = strip_comments(source("specs.object.c").read_text(encoding="utf-8", errors="replace"))
    wall = function_bodies(procs, r"\bint\s+wall_generic\s*\(")[0]
    for call in ("wall_of_air_chances(GET_SIZE(ch), chance, fall_chance)", "chance += wall_of_air_stat_bonus(ch)",
                 "fall_chance -= wall_of_air_stat_bonus(ch)", "chance >= wall_of_air_roll(live_rolls)",
                 "fall_chance >= wall_of_air_roll(live_rolls)"):
        assert call in wall, call
    # The passive effects read the numbers on the pages.
    fight = strip_comments(source("fight.c").read_text(encoding="utf-8", errors="replace"))
    melee = function_bodies(fight, r"\bint\s+melee_damage\s*\(")[0]
    for call in ("reduction = 1. - iceflow_armor_melee_share()",
                 "reduction = 1. - negative_feedback_barrier_melee_share()",
                 "dam -= skin_spell_deduct()"):
        assert call in melee, call
    mods = strip_comments(source("dam_mods.c").read_text(encoding="utf-8", errors="replace"))
    assert "double localDam = ethereal_alliance_partner_damage(damage)" in mods
    assert "dam_mod->mod += ethereal_alliance_damage_mod()" in mods
    assert "dam_mod->mod += dam_factor[DF_PHANTFORM] - 1.0" in mods
    breath = strip_comments(source("breath_weapons.c").read_text(encoding="utf-8", errors="replace"))
    assert breath.count("(float)dam * storm_empathy_lightning_breath_factor()") == 2
    assert "frost_beacon_alert_roll(live_rolls)" in function_bodies(procs, r"\bint\s+frost_beacon\s*\(")[0]
    # Flasks throw at the level they were mixed at.
    mix = strip_comments(source("salchemist.c").read_text(encoding="utf-8", errors="replace"))
    assert "potion->value[0] = GET_LEVEL(ch);" in mix
    assert "(*skills[j].spell_pointer)((int)potion->value[0]" in \
        strip_comments(source("actnew.c").read_text(encoding="utf-8", errors="replace"))
    # Dread blade's saved spell level and restore, and blood tithe's bonus.
    paladins = strip_comments(source(PALADINS).read_text(encoding="utf-8", errors="replace"))
    dread = function_bodies(paladins, r"\bbool\s+dread_blade_proc\s*\(")[0]
    for call in ("dread_blade_proc_roll(live_rolls)", "dread_blade_spell_level(live_rolls, ch)",
                 "+= dread_blade_save_penalty()"):
        assert call in dread, call
    assert "dread_blade_spell_roll(live_rolls)" in dread
    assert "blood_tithe_max_bonus()" in function_bodies(paladins, r"\bdouble\s+blood_tithe_bonus\s*\(")[0]
    assert "blood_tithe_pvp_mod()" in function_bodies(paladins, r"\bdouble\s+blood_tithe_damage_bonus\s*\(")[0]
    grease = function_bodies(strip_comments(source(ALCHEMIST).read_text(encoding="utf-8", errors="replace")),
                             r"\bbool\s+grease_check\s*\(")[0]
    assert "grease_slip_roll(live_rolls)" in grease and "grease_agility_roll(live_rolls)" in grease
    # Registration, and the disabled spell on the no-numbers list.
    table = strip_comments(source("abilities.c").read_text())
    header = source("abilities.h").read_text()
    for constant, name, _ in SPELLS:
        assert re.search(rf"case {constant}:\s*return {name}_facts;", table), constant
        assert f"std::string {name}_facts(char_data *ch);" in header, name
    assert "SPELL_PATH_OF_FROST" not in table
    assert "SPELL_PATH_OF_FROST" in (ROOT / "tests/fixtures/ability_coverage_no_numbers.txt").read_text().split()


def main():
    check_sources()
    functions = [extract_function("utility.c", "int dice(int num, int size)"),
                 extract_function("utility.c", "int BOUNDED(int a, int b, int c)")]
    for file in PREFIXES:
        text, names = statics_of(file)
        for name in names:
            functions.append(extract_function(file, re.search(rf"^static [\w:]+ {name}\(", text, re.M).group(0)))
    functions.append(extract_function(ETHERMANCER, "int frost_beacon_alert_roll("))
    functions.append(extract_function(ETHERMANCER, "void wall_of_air_chances("))
    for signature in ("int wall_of_air_roll(", "int wall_of_air_stat_bonus(", "double ethereal_alliance_partner_damage(",
                      "double ethereal_alliance_damage_mod(", "double storm_empathy_lightning_breath_factor("):
        functions.append(extract_function(ETHERMANCER, signature))
    for signature in ("int skin_spell_deduct(", "float iceflow_armor_melee_share(",
                      "float negative_feedback_barrier_melee_share("):
        functions.append(extract_function("fight.c", signature))
    functions += [extract_function(file, f"std::string {name}_facts(") for _, name, file in SPELLS]
    pages = ",\n".join(f'    {{ "{name}", {name}_facts }}' for _, name, _ in SPELLS)
    build = ROOT / "bin/tests"
    build.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ability-batch-7-", dir=build) as temporary:
        directory = Path(temporary)
        harness = directory / "batch7.cpp"
        harness.write_text(HARNESS.replace("PAGES", pages).replace("FUNCTIONS", "\n".join(functions)))
        binary = directory / "batch7"
        subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
                        "-ffunction-sections", "-fdata-sections", "-Wl,--gc-sections",
                        "-fsanitize=address,undefined", "-fno-sanitize-recover=undefined",
                        "-Isrc", "-I/usr/include/mysql", "-I/usr/include/libxml2",
                        str(harness), "src/abilities/abilities.c", "src/core/random.c",
                        "-o", str(binary)], cwd=ROOT, check=True)
        subprocess.run([str(binary)], cwd=directory, check=True)


if __name__ == "__main__":
    main()
