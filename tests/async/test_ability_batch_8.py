#!/usr/bin/env python3
"""Shared ability numbers, batch 8: spells.c, blispells.c and reavers.c.

Builds src/abilities/abilities.c and the real RNG with every shared and facts function of
those files, plus call lightning from magic.c, under sanitizers. Each converted roll keeps
its pre-conversion expression below as the oracle: under the same seeds it must give the
same value, leave the RNG at the same draw and fall inside the range its page shows. Every
page is built at every level for several casters: it must never roll, and every line must
fit 79 columns.
"""
import re
import subprocess
import tempfile
from pathlib import Path

from _paths import ROOT, extract_function, source
from _source_contract import function_bodies, strip_comments

SPELLS = [line.split() for line in """
SPELL_AURA_OF_REBIRTH aura_of_rebirth magic/spells.c
SPELL_AWAKEN_FOREST awaken_forest magic/spells.c
SPELL_BLOODTOSTONE blood_to_stone magic/spells.c
SPELL_DEPRESSED_EARTH depressed_earth magic/spells.c
SPELL_EARTHEN_TOMB earthen_tomb magic/spells.c
SPELL_ETHEREAL_GROUNDS ethereal_grounds magic/spells.c
SPELL_GATE gate magic/spells.c
SPELL_GROW grow magic/spells.c
SPELL_HURRICANE hurricane magic/spells.c
SPELL_LIFE_WARD life_ward magic/spells.c
SPELL_LIGHTNING_CURTAIN lightning_curtain magic/spells.c
SPELL_MIRAGE mirage magic/spells.c
SPELL_NETHER_GATE nether_gate magic/spells.c
SPELL_PLANE_SHIFT plane_shift magic/spells.c
SPELL_PRISMATIC_CUBE prismatic_cube magic/spells.c
SPELL_SPIKE_GROWTH spike_growth magic/spells.c
SPELL_STORMSHIELD storm_shield magic/spells.c
SPELL_TRANS_MUD_WATER trans_mud_water magic/spells.c
SPELL_TRANS_ROCK_LAVA trans_rock_lava magic/spells.c
SPELL_TRANS_ROCK_MUD trans_rock_mud magic/spells.c
SPELL_TRANS_WATER_AIR trans_water_air magic/spells.c
SPELL_VINES vines magic/spells.c
SPELL_WALL_OF_FLAMES wall_of_flames magic/spells.c
SPELL_WALL_OF_FORCE wall_of_force magic/spells.c
SPELL_WALL_OF_ICE wall_of_ice magic/spells.c
SPELL_WALL_OF_IRON wall_of_iron magic/spells.c
SPELL_WALL_OF_STONE wall_of_stone magic/spells.c
SPELL_WEB web magic/spells.c
SPELL_CALL_LIGHTNING call_lightning magic.c
SPELL_ACID_RAIN acid_rain blispells.c
SPELL_BLIGHT blight blispells.c
SPELL_BLOODSTONE bloodstone blispells.c
SPELL_CREATE_POND create_pond blispells.c
SPELL_DESECRATE_LAND desecrate_land blispells.c
SPELL_DRAIN_NATURE drain_nature blispells.c
SPELL_FALUZURES_VITALITY faluzures_vitality blispells.c
SPELL_FIRELANCE firelance blispells.c
SPELL_FLAME_SPHERE flame_sphere blispells.c
SPELL_FORBIDDANCE forbiddance blispells.c
SPELL_HORRID_WILTING horrid_wilting blispells.c
SPELL_IMPLOSION implosion blispells.c
SPELL_SANDSTORM sandstorm blispells.c
SPELL_SAP_NATURE sap_nature blispells.c
SPELL_SHAMBLER shambler blispells.c
SPELL_THORNSKIN thornskin blispells.c
SPELL_TOXIC_FOG toxic_fog blispells.c
SPELL_WAVES_FATIGUE waves_fatigue blispells.c
SPELL_BALADORS_PROTECTION baladors_protection reavers.c
SPELL_CEGILUNE_BLADE cegilunes_searing_blade reavers.c
SPELL_CHILLING_IMPLOSION kostchtchies_implosion reavers.c
SPELL_FERRIX_PRECISION ferrix_precision reavers.c
SPELL_GIRILALS_GRANITE_HAMMER girilals_granite_hammer reavers.c
SPELL_ILESHS_SMASHING_FURY ileshs_smashing_fury reavers.c
SPELL_ILIENZES_FLAME_SWORD ilienzes_flame_sword reavers.c
SPELL_KANCHELSIS_FURY kanchelsis_fury reavers.c
SPELL_LLIENDILS_STORMSHOCK lliendils_stormshock reavers.c
SPELL_STORMCALLERS_FURY stormcallers_fury reavers.c
SPELL_THRYMS_ICERAZOR thryms_icerazor reavers.c
""".split("\n") if line.strip()]

# Disabled for mortals: no class has them and no item carries them.
DISABLED = """SPELL_BLOOD_ALLIANCE SPELL_CHANNEL SPELL_CONTAGION SPELL_CONTROL_WEATHER SPELL_CURSE_OF_YZAR
SPELL_ESHABALAS_VITALITY SPELL_REST SPELL_TRANS_AIR_WATER SPELL_TRANS_LAVA_ROCK SPELL_TRANS_MUD_ROCK
SPELL_TRANS_WATER_MUD""".split()

PREFIXES = {
    "magic/spells.c": ("aura_of_rebirth_", "wall_", "lightning_curtain_", "prismatic_wall_", "web_", "life_ward_",
                 "earthen_tomb_", "transmute_", "vines_", "spike_growth_", "awaken_forest_", "hurricane_",
                 "storm_shield_", "blood_to_stone_", "mirage_", "gate_", "plane_shift_"),
    "magic.c": ("call_lightning_", "lightning_bolt_", "resurrect_lag"),
    "blispells.c": ("ruiner_", "thornskin_", "flame_sphere_", "desecrate_land_", "blight_", "forbiddance_",
                    "waves_fatigue_", "acid_rain_", "horrid_wilting_", "shambler_", "implosion_", "sandstorm_",
                    "firelance_", "drain_nature_", "create_pond_", "toxic_fog_", "faluzures_vitality_",
                    "sap_nature_", "bloodstone_"),
    "reavers.c": ("baladors_", "ferrix_precision_", "kanchelsis_", "ilienzes_flame_sword_", "ilienze_sword_damage",
                  "ilienze_sword_fireshield", "ilienze_sword_burst", "cegilune_tier_", "cegilune_burn_",
                  "cegilune_blade_duration", "girilals_granite_hammer_", "ileshs_duration", "ilesh_tier_",
                  "ilesh_immolate_", "ilesh_blindness", "thryms_icerazor_", "lliendils_stormshock_",
                  "stormcallers_fury_", "kostchtchies_implosion_"),
}
# Static page parts other pages build on.
PAGE_PARTS = [("magic/spells.c", "static std::string wall_breakable_facts("), ("magic/spells.c", "static std::string wall_exit_facts("),
              ("magic/spells.c", "static std::string gate_common_facts("), ("magic/spells.c", "static std::string transmute_facts("),
              ("magic.c", "std::string lightning_bolt_facts("), ("magic.c", "std::string resurrect_facts(")]

# What each handler must call, tying each helper to its own branch.
HANDLER_CALLS = {
    "magic/spells.c": {
        "cast_gate": ["set.throughput = gate_throughput()", "set.decay_timer = gate_decay()"],
        "cast_nether_gate": ["set.throughput = gate_throughput()", "set.decay_timer = gate_decay()"],
        "cast_plane_shift": ["GET_LEVEL(ch) < plane_shift_druid_level()"],
        "cast_area_resurrect": ["GET_HIT(ch) = aura_of_rebirth_hit_points(i)", "if (i > aura_of_rebirth_fatal_above())",
                                "CharWait(ch, aura_of_rebirth_lag(i))", "spell_resurrect(level, ch"],
        "spell_wall_of_flames": ["WALL_OF_FLAMES, wall_of_flames_power(live_rolls, level)", "wall_decay()"],
        "spell_wall_of_ice": ["WALL_OF_ICE, wall_of_ice_power()", "wall_decay()", "EX_BREAKABLE"],
        "cast_life_ward": ["LIFE_WARD, 40, wall_decay()"],
        "spell_wall_of_stone": ["WALL_OF_STONE, wall_strength(level), wall_decay()", "EX_BREAKABLE"],
        "spell_wall_of_iron": ["WALL_OF_IRON, wall_strength(level), wall_decay()", "EX_BREAKABLE"],
        "spell_wall_of_force": ["WALL_OF_FORCE, wall_strength(level), wall_decay()", "ITEM_INVISIBLE", "EX_BREAKABLE"],
        "cast_lightning_curtain": ["lightning_curtain_power(live_rolls, level)", "wall_decay()"],
        "cast_web": ["WEB, 0, wall_decay()"],
        "cast_prismatic_cube": ["PRISMATIC_WALL, level, wall_decay()"],
        "event_earthen_tomb": ["earthen_tomb_quake_roll(live_rolls) < earthen_tomb_quake_below()",
                               "add_event(event_earthen_tomb, earthen_tomb_interval()",
                               "add_event(event_earthen_tomb, earthen_tomb_blocked_interval()",
                               "earthen_tomb_wall_level(), WALL_OF_STONE, earthen_tomb_wall_level(), wall_decay()"],
        "cast_earthen_tomb": ["af.duration = earthen_tomb_duration(live_rolls)",
                              "add_event(event_earthen_tomb, earthen_tomb_interval()"],
        "cast_vines": ["++count == vines_most_herbs()", "af.duration = vines_duration(level)",
                       "af.modifier = vines_absorb(count)"],
        "event_spike_growth": ["duration = spike_growth_duration(live_rolls)", "chance = spike_growth_affect_chance()",
                               "spike_growth_affect_roll(live_rolls) < 100 - chance",
                               "technique = spike_growth_technique(live_rolls)", "spell_grow_spike(GET_LEVEL(ch), ch",
                               "spike_growth_foot_damage(live_rolls, ch)", "CharWait(tch, spike_growth_foot_lag())",
                               "dam = spike_growth_bone_damage(live_rolls, ch)",
                               "add_event(event_spike_growth, spike_growth_interval()"],
        "event_awaken_forest": ["duration = awaken_forest_duration(live_rolls)",
                                "awaken_forest_affect_roll(live_rolls, nCnt) > awaken_forest_pass_above()",
                                "technique = awaken_forest_technique(live_rolls)",
                                "spell_entangle(awaken_forest_entangle_level(), ch",
                                "GET_C_AGI(tch) < awaken_forest_root_roll(live_rolls)",
                                "NewSaves(tch, SAVING_SPELL, awaken_forest_root_save())",
                                "CharWait(tch, awaken_forest_root_lag())",
                                "dam = awaken_forest_branch_damage(live_rolls)",
                                "add_event(event_awaken_forest, awaken_forest_interval()"],
        "cast_spike_growth": ["add_event(event_spike_growth, spike_growth_start()"],
        "cast_awaken_forest": ["add_event(event_awaken_forest, awaken_forest_start()"],
        "cast_hurricane": ["dam = hurricane_damage(live_rolls, level)",
                           "hurricane_miss_roll(live_rolls) < hurricane_miss_below()",
                           "chance = hurricane_knockdown_chance(IS_AFFECTED(tch, AFF_FLY), GET_LEVEL(ch))",
                           "affchance = hurricane_knockdown_roll(live_rolls)"],
        "cast_storm_shield": ["af.duration = storm_shield_duration(level)"],
        "cast_bloodstone": ["NewSaves(victim, SAVING_PARA, blood_to_stone_save())", "dur = blood_to_stone_saved(dur)",
                            "GET_VITALITY(victim) -= blood_to_stone_vitality()",
                            "af.duration = blood_to_stone_duration(dur)", "resists_spell(ch, victim)"],
        "spell_mirage": ["af.duration = mirage_duration()"],
    },
    "magic.c": {
        "event_call_lightning": ["dam = call_lightning_damage(live_rolls, clData->level)",
                                 "Stun(vict, ch, call_lightning_stun(), TRUE)",
                                 "clData->waves++ < call_lightning_more_strikes()",
                                 "add_event(event_call_lightning, call_lightning_interval()"],
        "spell_call_lightning": ["add_event(event_call_lightning, call_lightning_delay()"],
    },
    "blispells.c": {
        "spell_thornskin": ["af1.duration = thornskin_duration()", "af1.modifier = thornskin_armor_class(level)",
                            "af1->duration = thornskin_duration()"],
        "spell_flame_sphere": ["int dam = flame_sphere_damage(live_rolls, level)",
                               "dam = flame_sphere_failed_save(dam)", "dam = ruiner_damage(ch, dam)"],
        "spell_desecrate_land": ["af.duration = desecrate_land_duration(ch)"],
        "spell_blight": ["int dam = blight_damage(live_rolls, level)", "dam = blight_spec_damage(ch, dam)",
                         "dam = blight_failed_save(dam)"],
        "spell_forbiddance": ["af.duration = forbiddance_duration(ch)"],
        "spell_waves_fatigue": ["moves = waves_fatigue_moves(live_rolls, ch)",
                                "NewSaves(victim, SAVING_PARA, waves_fatigue_save(level))",
                                "moves = waves_fatigue_saved(moves)",
                                "add_event(event_waves_fatigue, waves_fatigue_second_wave()",
                                "add_event(event_waves_fatigue, waves_fatigue_third_wave()"],
        "event_acid_rain": ["dam = acid_rain_damage(live_rolls, ch)", "dam = acid_rain_stormbringer_damage(ch, dam)",
                            "acid_rain_saved(dam), SPLDAM_ACID"],
        "spell_acid_rain": ["int waves = acid_rain_waves(level)", "add_event(event_acid_rain, acid_rain_wave_delay(i)"],
        "spell_horrid_wilting": ["int dam = horrid_wilting_damage(live_rolls, level)",
                                 "dam = horrid_wilting_failed_save(dam)",
                                 "blind(ch, victim, horrid_wilting_blindness(live_rolls))",
                                 "dam = ruiner_damage(ch, dam)", "horrid_wilting_dry_target(dam), SPLDAM_ACID"],
        "spell_shambler": ["count > shambler_pet_limit()", "count = shambler_count_poor(live_rolls)",
                           "count = shambler_count_open(live_rolls)", "count = shambler_count_rich(live_rolls)",
                           "setup_pet(mob, ch, shambler_charm()", "add_event(event_pet_death, shambler_life(live_rolls)"],
        "spell_implosion": ["int dam = implosion_damage(live_rolls, level)", "dam = implosion_saved(dam)",
                            "dam = ruiner_damage(ch, dam)"],
        "event_sandstorm": ["sandstorm_damage(live_rolls, level), SPLDAM_GAS",
                            "blind(ch, victim, sandstorm_blindness(live_rolls))",
                            "sandstorm_saved(sandstorm_damage(live_rolls, level))"],
        "event_sandstorm_message": ["add_event(event_sandstorm_message, sandstorm_interval()",
                                    "add_event(event_sandstorm, sandstorm_interval()"],
        "spell_sandstorm": ["int num_rounds = sandstorm_rounds(live_rolls)", "make_wet(roomie, sandstorm_wet())"],
        "spell_firelance": ["dam = firelance_damage(live_rolls, level)", "dam = ruiner_damage(ch, dam)",
                            "dam = firelance_saved(dam)"],
        "event_drain_nature": ["healpoints = drain_nature_terrain(healpoints, world[vict->in_room].sector_type)",
                               "wavevalue = drain_nature_next_wave(wavevalue)",
                               "wavevalue > drain_nature_last_above()"],
        "spell_drain_nature": ["healpoints = drain_nature_first_wave(level)", "healpoints = drain_nature_outsider(healpoints)",
                               "healpoints < drain_nature_least()", "healpoints = drain_nature_scourge(healpoints)"],
        "spell_create_pond": ["set_obj_affected(pond, create_pond_decay()"],
        "spell_toxic_fog": ["dam = toxic_fog_damage(live_rolls, level)", "dam = toxic_fog_failed_save(dam)"],
        "spell_faluzures_vitality": ["int healpoints = faluzures_vitality_hit_points(level)",
                                     "paf->duration = faluzures_vitality_duration()",
                                     "af.duration = faluzures_vitality_duration()",
                                     "af.modifier = faluzures_vitality_moves(level)"],
        "spell_sap_nature": ["skl_lvl = sap_nature_amount(level)", "skl_lvl = sap_nature_scourge(skl_lvl)"],
        "spell_bloodstone": ["int duration = bloodstone_duration(level)", "af.duration = duration / PULSES_IN_TICK"],
    },
    "reavers.c": {
        "spell_baladors_protection": ["GET_LEVEL(ch) > baladors_alignment_above()", "GET_LEVEL(ch) > baladors_saves_above()",
                                      "GET_LEVEL(ch) > baladors_armor_above()", "af.modifier = baladors_save()",
                                      "af.modifier = baladors_armor_class()", "af.duration = baladors_duration()"],
        "spell_ferrix_precision": ["af.duration = ferrix_precision_duration()", "af.modifier = ferrix_precision_bonus(level)"],
        "spell_kanchelsis_fury": ["level -= kanchelsis_earth_penalty()", "af.modifier = kanchelsis_strength(level)",
                                  "level >= kanchelsis_fastest_level()", "af.modifier = kanchelsis_fastest_pulse()",
                                  "level >= kanchelsis_faster_level()", "af.modifier = kanchelsis_faster_pulse()",
                                  "level >= kanchelsis_fast_level()", "af.modifier = kanchelsis_fast_pulse()",
                                  "af1->duration = kanchelsis_duration()"],
        "spell_ilienzes_flame_sword": ["af.duration = ilienzes_flame_sword_duration(level)",
                                       "af.modifier = ilienzes_flame_sword_hitroll(live_rolls)"],
        "ilienze_sword": ["dam = ilienze_sword_damage(live_rolls, GET_LEVEL(ch))",
                          "dam += ilienze_sword_fireshield(live_rolls)",
                          "afp->modifier > ilienze_sword_burst_roll(live_rolls)",
                          "dam = ilienze_sword_burst(live_rolls, afp->modifier)"],
        "spell_cegilunes_searing_blade": ["MIN(afp->duration, cegilune_blade_duration(level))"],
        "cegilune_blade": ["!cegilune_tier_roll(live_rolls)", "afp->modifier >= cegilune_burn_tier()",
                           "!cegilune_burn_roll(live_rolls)", "af.modifier = cegilune_burn_rounds()",
                           "af2p->modifier = cegilune_burn_rounds()"] +
                          [f"cegilune_tier_{n}(live_rolls), SPLDAM_FIRE" for n in range(6)],
        "spell_girilals_granite_hammer": ["af.duration = girilals_granite_hammer_duration(level)",
                                          "af.modifier = girilals_granite_hammer_damroll(level)"],
        "girilals_granite_hammer": ["dam = girilals_granite_hammer_damage(live_rolls, GET_LEVEL(ch))", "dam = MAX(1, dam)"],
        "spell_ileshs_smashing_fury": ["MIN(afp->duration, ileshs_duration(level))"],
        "ilesh_fury": ["!ilesh_tier_roll(live_rolls)", "!ilesh_immolate_roll(live_rolls)",
                       "blind(ch, victim, ilesh_blindness(live_rolls))", "spell_blindness(GET_LEVEL(ch), ch"],
        "spell_thryms_icerazor": ["af.duration = thryms_icerazor_duration(level)", "af.modifier = thryms_icerazor_hitroll(level)"],
        "thryms_icerazor": ["dam = thryms_icerazor_damage(live_rolls)", "dam += thryms_icerazor_coldshield(live_rolls)",
                            "dam -= thryms_icerazor_fireshield(live_rolls)",
                            "thryms_icerazor_slow_roll(live_rolls) <= thryms_icerazor_slow_upto()",
                            "af.duration = thryms_icerazor_slow_duration()"],
        "spell_lliendils_stormshock": ["af.duration = lliendils_stormshock_duration(level)",
                                       "af.modifier = lliendils_stormshock_pulse(live_rolls)"],
        "lliendils_stormshock": ["dam = lliendils_stormshock_damage(live_rolls, GET_LEVEL(ch))"],
        "spell_stormcallers_fury": ["af.duration = stormcallers_fury_duration(level)"],
        "stormcallers_fury": ["!stormcallers_fury_build_roll(live_rolls)", "afp->modifier > stormcallers_fury_trigger_roll(live_rolls)",
                              "int num_hits = stormcallers_fury_hits(live_rolls)"],
        "spell_kostchtchies_implosion": ["af.duration = kostchtchies_implosion_duration(level)"],
        "kostchtchies_implosion": ["!kostchtchies_implosion_build_roll(live_rolls)",
                                   "afp->modifier > kostchtchies_implosion_trigger_roll(live_rolls)",
                                   "int dam = kostchtchies_implosion_damage(live_rolls)"],
    },
    "specs.object.c": {
        "wall_generic": ["CharWait(ch, wall_hit_lag())", "dam = wall_of_flames_protected(dam)",
                         "GET_HIT(ch) - wall_of_flames_margin()", "dam = wall_of_ice_protected(dam)",
                         "wall_of_ice_bump(dam)", "wall_of_ice_climb(dam)", "dam = lightning_curtain_protected(dam)",
                         "GET_HIT(ch) - lightning_curtain_margin()", "!prismatic_wall_pass_roll(live_rolls) && IS_PC(ch)",
                         "!prismatic_wall_pass_roll(live_rolls) && IS_PC_PET(ch)", "GET_HIT(ch) - prismatic_wall_pass_cost()",
                         "switch (prismatic_wall_colour_roll(live_rolls))", "dam = prismatic_wall_red()",
                         "dam = prismatic_wall_orange()", "dam = prismatic_wall_yellow()",
                         "spell_pointer(prismatic_wall_effect_level(), ch", "dam = prismatic_wall_saved(dam)",
                         "af.duration = web_paralysis(live_rolls)", "!life_ward_pass_roll(live_rolls)",
                         "dam = life_ward_climb_drain(live_rolls)", "dam = life_ward_bump_drain(live_rolls)",
                         "wall_climb_roll(live_rolls) > wall_climb_above()"],
        "blighter_pond": ["obj->value[0] < create_pond_drain_level()", "obj->value[0] >= create_pond_drain_level()",
                          "obj->value[0] >= create_pond_regeneration_level()", "CharWait(ch, create_pond_lag())"],
    },
    "fight.c": {
        "blockSucceed": ["affected_by_spell(victim, SPELL_STORMSHIELD) && !storm_shield_discharge_roll(live_rolls)",
                         "spell_lightning_bolt(GET_LEVEL(victim), victim"],
        "check_shields": ["thornskin_damage(", "thornDamage *= thornskin_ironwood_multiplier()"],
        "calculate_attacks": ["GET_LEVEL(ch) >= kanchelsis_second_attack_level()",
                              "GET_LEVEL(ch) >= kanchelsis_third_attack_level()",
                              "GET_LEVEL(ch) >= kanchelsis_fourth_attack_level()"],
    },
    "innates.c": {
        "resists_spell": ["get_innate_resistance(victim) - desecrate_land_shrug_penalty()"],
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

static int gate_pass = -1;
// The properties differ from their fallbacks where a wrong key would otherwise pass.
float get_property(const char *key, double fallback)
{
    if (!std::strcmp(key, "spell.spikeGrowth.affectChance"))
        return 20.f;
    if (!std::strcmp(key, "spell.endurance.modifiers"))
        return 2.f;
    if (!std::strcmp(key, "damage.increase.barkskin"))
        return 1.3f;
    return (float)fallback;
}
int get_property(const char *key, int fallback)
{
    if (!std::strcmp(key, "portals.gate.maxToPass"))
        return gate_pass;
    if (!std::strcmp(key, "portals.gate.decayTimeout"))
        return 480;
    return fallback;
}

FUNCTIONS

static int fingerprint() { return number(0, INT_MAX); }

static void same_within(const char *name, const std::function<int()> &original,
                        const std::function<int(const Rolls &)> &shared, int a, int b) {
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
static void same(const char *name, const std::function<int()> &original,
                 const std::function<int(const Rolls &)> &shared) {
    same_within(name, original, shared, shared(lowest_rolls), shared(highest_rolls));
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

struct Viewer { const char *name; uint m_class; int spec; };
static const Viewer viewers[] = {
    { "warrior", CLASS_WARRIOR, 0 },
    { "blighter", CLASS_BLIGHTER, 0 },
    { "ruiner", CLASS_BLIGHTER, SPEC_RUINER },
    { "scourge", CLASS_BLIGHTER, SPEC_SCOURGE },
    { "stormbringer", CLASS_BLIGHTER, SPEC_STORMBRINGER },
    { "druid", CLASS_DRUID, 0 },
    { "conjurer", CLASS_CONJURER, 0 },
    { "reaver", CLASS_REAVER, 0 },
    { "earth reaver", CLASS_REAVER, SPEC_EARTH_REAVER },
    { "cleric", CLASS_CLERIC, 0 },
};
static char_data viewer(const Viewer &v, int level) {
    char_data ch{};
    ch.player.m_class = v.m_class;
    ch.player.spec = v.spec;
    ch.player.race = RACE_HUMAN;
    ch.player.level = level;
    return ch;
}

struct Page { const char *name; AbilityFacts facts; };
static const Page pages[] = {
PAGES
};

static std::string page(AbilityFacts facts, const Viewer &v, int level) {
    char_data ch = viewer(v, level);
    return facts(&ch);
}

int main() {
    // Every page at every level for every kind of caster: no rolls, short lines.
    randomize(9);
    const int untouched = fingerprint();
    bool bad = false;
    for (const Viewer &v : viewers)
        for (int level = 1; level <= 62; ++level)
            for (const Page &p : pages) {
                randomize(9);
                const std::string text = page(p.facts, v, level);
                assert(fingerprint() == untouched);
                assert(!text.empty() && text.back() == '\n');
                assert(text.find("--") == std::string::npos);
                size_t start = 0;
                for (size_t end; (end = text.find('\n', start)) != std::string::npos; start = end + 1)
                    if (end - start > 79 || text.compare(start, 2, "  ") != 0) {
                        std::fprintf(stderr, "%s, %s %d: bad line \"%s\"\n", p.name, v.name, level,
                                     text.substr(start, end - start).c_str());
                        bad = true;
                    }
            }

    if (bad)
        return 1;

    // Every converted roll draws exactly as its original expression did.
    for (int level : { 1, 3, 4, 10, 19, 20, 30, 40, 41, 50, 51, 56, 60 }) {
        char_data c = viewer(viewers[0], level);
        P_char ch = &c;
        SAME(dice(MIN(40, level), 9), call_lightning_damage(rolls, level));
        SAME(dice(level / 4, 10), wall_of_flames_power(rolls, level));
        SAME(dice(level / 4, 10), lightning_curtain_power(rolls, level));
        SAME(GET_LEVEL(ch) * number(1, 3), spike_growth_foot_damage(rolls, ch));
        SAME(dice(1, GET_LEVEL(ch)) + 160, spike_growth_bone_damage(rolls, ch));
        SAME(40 + level * 6 + number(1, 30), hurricane_damage(rolls, level));
        SAME((dice((level / 5) + 5, 6) * 3), flame_sphere_damage(rolls, level));
        SAME((level > 40) ? dice(40 * 3, 6) : dice(level * 3, 6), blight_damage(rolls, level));
        SAME(GET_LEVEL(ch) / 4 + number(-4, 2), waves_fatigue_moves(rolls, ch));
        SAME(30 + GET_LEVEL(ch) + number(0, 20), acid_rain_damage(rolls, ch));
        SAME(5 * level + dice(level * 2, 10), implosion_damage(rolls, level));
        SAME(dice(level * 3, 6), sandstorm_damage(rolls, level));
        SAME(dice(4 * MIN(17, level / 2 + 1), 7), firelance_damage(rolls, level));
        SAME(level > 50 ? dice(4 * MIN(20, (level / 2 + 1)), 8) : dice(4 * MIN(20, (level / 2 + 1)), 7),
             toxic_fog_damage(rolls, level));
        SAME(dice(MAX(2, level / 10), 2), thornskin_damage(rolls, level));
        SAME(number(1, (GET_LEVEL(ch) / 4)), ilienze_sword_damage(rolls, level));
        SAME(number(8, (GET_LEVEL(ch) * 2) / 5), girilals_granite_hammer_damage(rolls, level));
        SAME(number(1, GET_LEVEL(ch) / 4), lliendils_stormshock_damage(rolls, level));
        // A subtracted roll: its bounds come from pairing the dice low with the subtraction high.
        const Rolls least = { lowest_rolls.dice, highest_rolls.number };
        const Rolls most = { highest_rolls.dice, lowest_rolls.number };
        same_within("horrid_wilting_damage", [&] { return dice((int)(level * 3), 6) - number(0, 40); },
                    [&](const Rolls &rolls) { return horrid_wilting_damage(rolls, level); },
                    horrid_wilting_damage(least, level), horrid_wilting_damage(most, level));
    }
    for (int nCnt : { 0, 2, 3, 8 })
        SAME(number(0, MAX(2, nCnt)), awaken_forest_affect_roll(rolls, nCnt));
    for (int charge : { 1, 8, 40 })
        SAME(dice(charge, 12), ilienze_sword_burst(rolls, charge));
    SAME(number(1, 100), wall_climb_roll(rolls));
    SAME(number(0, 2), prismatic_wall_pass_roll(rolls));
    SAME(number(0, 6), prismatic_wall_colour_roll(rolls));
    SAME(number(4, 15) * WAIT_SEC, web_paralysis(rolls));
    SAME(number(0, 3), life_ward_pass_roll(rolls));
    SAME(number(10, 28), life_ward_climb_drain(rolls));
    SAME(number(8, 22), life_ward_bump_drain(rolls));
    SAME(number(1, 10), earthen_tomb_quake_roll(rolls));
    SAME(number(8, 10) * PULSE_VIOLENCE, earthen_tomb_duration(rolls));
    SAME(5 + dice(2, 5), transmute_seconds(rolls));
    SAME(WAIT_SEC * (10 + dice(3, 2)), spike_growth_duration(rolls));
    SAME(dice(1, 100), spike_growth_affect_roll(rolls));
    SAME(dice(1, 3), spike_growth_technique(rolls));
    SAME(WAIT_SEC * (5 + dice(3, 2)), awaken_forest_duration(rolls));
    SAME(dice(1, 3), awaken_forest_technique(rolls));
    SAME(number(0, 125), awaken_forest_root_roll(rolls));
    SAME(dice(1, 40) + 160, awaken_forest_branch_damage(rolls));
    SAME(dice(1, 100), hurricane_miss_roll(rolls));
    SAME(number(1, 100), hurricane_knockdown_roll(rolls));
    SAME(number(0, 2), storm_shield_discharge_roll(rolls));
    SAME(number(1, 4), blood_to_stone_move_cost(rolls));
    SAME(number(6, 12) * WAIT_SEC, horrid_wilting_blindness(rolls));
    SAME(dice(1, 2), shambler_count_poor(rolls));
    SAME(dice(1, 3) + 1, shambler_count_open(rolls));
    SAME(dice(1, 4) + 2, shambler_count_rich(rolls));
    SAME(dice(2, 6) * 60 * WAIT_SEC, shambler_life(rolls));
    SAME(number(6, 12) * WAIT_SEC, sandstorm_blindness(rolls));
    SAME(number(1, 3), sandstorm_rounds(rolls));
    SAME(number(1, 4), ilienzes_flame_sword_hitroll(rolls));
    SAME(number(2, 8), ilienze_sword_fireshield(rolls));
    SAME(number(4, 40), ilienze_sword_burst_roll(rolls));
    SAME(number(0, 4), cegilune_tier_roll(rolls));
    SAME(number(8, 16), cegilune_tier_0(rolls));
    SAME(number(16, 32), cegilune_tier_1(rolls));
    SAME(number(32, 40), cegilune_tier_2(rolls));
    SAME(number(40, 56), cegilune_tier_3(rolls));
    SAME(number(56, 64), cegilune_tier_4(rolls));
    SAME(number(64, 80), cegilune_tier_5(rolls));
    SAME(number(0, 5), cegilune_burn_roll(rolls));
    SAME(dice(12, 4), cegilune_burn_damage(rolls));
    SAME(number(0, 4), ilesh_tier_roll(rolls));
    SAME(number(0, 3), ilesh_immolate_roll(rolls));
    SAME(number(4, 12) * WAIT_SEC, ilesh_blindness(rolls));
    SAME(number(8, 6), thryms_icerazor_damage(rolls));
    SAME(number(4, 3), thryms_icerazor_coldshield(rolls));
    SAME(number(4, 4), thryms_icerazor_fireshield(rolls));
    SAME(number(1, 100), thryms_icerazor_slow_roll(rolls));
    SAME(number(-1, -2), lliendils_stormshock_pulse(rolls));
    SAME(number(0, 1), stormcallers_fury_build_roll(rolls));
    SAME(number(14, 16), stormcallers_fury_trigger_roll(rolls));
    SAME(number(3, 6), stormcallers_fury_hits(rolls));
    SAME(number(0, 1), kostchtchies_implosion_build_roll(rolls));
    SAME(number(14, 16), kostchtchies_implosion_trigger_roll(rolls));
    SAME(450 + dice(10, 10), kostchtchies_implosion_damage(rolls));

    // The hurricane's knockdown chain.
    assert(hurricane_knockdown_chance(true, 50) == 5 && hurricane_knockdown_chance(false, 50) == 1);
    assert(hurricane_knockdown_chance(true, 51) == 10 && hurricane_knockdown_chance(false, 51) == 2);
    // Drain nature's terrain table and waves.
    assert(drain_nature_terrain(47, SECT_CITY) == 31 && drain_nature_terrain(47, SECT_FIELD) == 62);
    assert(drain_nature_terrain(47, SECT_FOREST) == 70 && drain_nature_terrain(47, SECT_HILLS) == 58);
    assert(drain_nature_terrain(47, SECT_MOUNTAIN) == 56 && drain_nature_terrain(47, SECT_UNDRWLD_LOWCEIL) == 54);
    assert(drain_nature_terrain(47, SECT_INSIDE) == 47);
    assert(drain_nature_total(47, SECT_INSIDE) == 47 + 23 + 11 + 5 + 2);
    // A saved firelance, implosion and fog truncate as the original int /= double did.
    { int dam = 476; dam /= 1.5; assert(firelance_saved(476) == dam && toxic_fog_failed_save(476) == dam); }
    { int dam = 1250; dam /= 1.8; assert(implosion_saved(1250) == dam); }

    const Viewer &plain = viewers[1], &ruiner = viewers[2], &scourge = viewers[3], &storm = viewers[4];
    const Viewer &warrior = viewers[0], &reaver = viewers[7], &earth = viewers[8];
    #define PAGE_HAS(name, who, level, line) assert(contains(page(name##_facts, who, level), line "\n"))
    PAGE_HAS(call_lightning, plain, 50, "  Lightning damage per strike: 40-360 at your level, 50");
    PAGE_HAS(call_lightning, plain, 50, "  Strikes: 3, the first after 4 seconds, then every 2 seconds");
    PAGE_HAS(call_lightning, plain, 50, "  If it stays and fails a fear save, stun: 2 seconds");
    PAGE_HAS(call_lightning, plain, 50, "  effects, greater races of level 51 or more, and at times indomitable rage.");
    PAGE_HAS(wall_of_flames, plain, 50, "  Burn when crossing: 12-120 at your level, 50");
    PAGE_HAS(wall_of_flames, plain, 50, "  With protection from fire: 4-40");
    PAGE_HAS(wall_of_flames, plain, 1, "  Burn when crossing: 1-10 at your level, 1");
    PAGE_HAS(wall_of_flames, plain, 50, "  It kills anyone it would leave under: 8 hit points");
    PAGE_HAS(wall_of_flames, plain, 50, "  Stays: 7 minutes 30 seconds");
    PAGE_HAS(lightning_curtain, plain, 50, "  With protection from lightning: 8-80");
    PAGE_HAS(lightning_curtain, plain, 50, "  It kills anyone it would leave under: 10 hit points");
    PAGE_HAS(wall_of_ice, plain, 50, "  Strength: 40");
    PAGE_HAS(wall_of_ice, plain, 50, "  Bumping it takes: 20 hit points, never below 1");
    PAGE_HAS(wall_of_ice, plain, 50, "  A wall climber gets over: 40%");
    PAGE_HAS(wall_of_ice, plain, 50, "  Going over takes: up to 40 hit points, never below 1");
    PAGE_HAS(wall_of_ice, plain, 50, "  With protection from cold: up to 27");
    PAGE_HAS(wall_of_ice, plain, 50, "  Lag from hitting it: 16 seconds");
    PAGE_HAS(wall_of_stone, plain, 50, "  Strength: 50 at your level");
    PAGE_HAS(wall_of_iron, plain, 30, "  Strength: 30 at your level");
    PAGE_HAS(wall_of_force, plain, 30, "  Strength: 30 at your level");
    PAGE_HAS(life_ward, plain, 50, "  Anyone else passes unharmed: 1 in 4");
    PAGE_HAS(life_ward, plain, 50, "  Vitality lost bumping it: 8-22, never below 1");
    PAGE_HAS(life_ward, plain, 50, "  Vitality lost going over: 10-28");
    PAGE_HAS(web, plain, 50, "  Paralysis if a crosser fails a paralysis save: 4 seconds to 15 seconds");
    PAGE_HAS(prismatic_cube, plain, 50, "  A player or pet gets through: 1 in 3 for 75 hit points, never below 1");
    PAGE_HAS(prismatic_cube, plain, 50, "  Bumping it lands on: 1 of 7 colours");
    PAGE_HAS(prismatic_cube, plain, 50, "  Fire damage, halved on a save: red 100, orange 70, yellow 40");
    PAGE_HAS(prismatic_cube, plain, 50, "  Cast at level 50: minor paralysis, feeblemind, poison, blindness");
    PAGE_HAS(earthen_tomb, plain, 50, "  The ground shakes for: 32 seconds to 40 seconds");
    PAGE_HAS(earthen_tomb, plain, 50, "  Chance of a wall every 4 seconds: 6 in 10");
    PAGE_HAS(earthen_tomb, plain, 50, "  With no exit to wall, it waits: 6 seconds");
    PAGE_HAS(aura_of_rebirth, plain, 50, "  Your hit points after: 20, less 1 per corpse raised");
    PAGE_HAS(aura_of_rebirth, plain, 50, "  Corpses that kill you: 20");
    PAGE_HAS(aura_of_rebirth, plain, 50, "  Afterwards, lag per corpse: 4 seconds");
    PAGE_HAS(gate, plain, 50, "  People who can pass: no limit");
    PAGE_HAS(gate, plain, 50, "  Stays open: 2 minutes");
    gate_pass = 0;
    PAGE_HAS(nether_gate, plain, 50, "  People who can pass: no limit");
    gate_pass = 6;
    PAGE_HAS(nether_gate, plain, 50, "  People who can pass: 6");
    gate_pass = -1;
    PAGE_HAS(plane_shift, plain, 50, "  Level a druid needs: 41");
    for (AbilityFacts facts : { ethereal_grounds_facts, trans_rock_mud_facts, trans_mud_water_facts, trans_water_air_facts,
                                trans_rock_lava_facts, depressed_earth_facts, grow_facts }) {
        assert(contains(page(facts, plain, 50), "  Takes hold after: 7 seconds to 15 seconds\n"));
        assert(contains(page(facts, plain, 50), "  Lasts: 1 minute\n"));
    }
    PAGE_HAS(vines, plain, 50, "  Damage absorbed: 40 per green herb, up to 4 herbs");
    PAGE_HAS(vines, plain, 50, "  Duration: 25-26 game hours (31.25-32.5 minutes) at your level");
    PAGE_HAS(vines, plain, 50, "  Fist of dragon does not get through them.");
    PAGE_HAS(spike_growth, plain, 50, "  Lasts: 13 seconds to 16 seconds");
    PAGE_HAS(spike_growth, plain, 50, "  Works every: 2 seconds, first 5 seconds after the cast");
    PAGE_HAS(spike_growth, plain, 50, "  Chance per target each time: 21%");
    PAGE_HAS(spike_growth, plain, 50, "  Spike in the foot: 50-150, knocks down, lags 4 seconds");
    PAGE_HAS(spike_growth, plain, 50, "  Snapped bones: 161-210");
    PAGE_HAS(awaken_forest, plain, 50, "  Lasts: 8 seconds to 11 seconds");
    PAGE_HAS(awaken_forest, plain, 50, "  Works every: 1.5 seconds, first 4 seconds after the cast");
    PAGE_HAS(awaken_forest, plain, 50, "  Chance per target with more than 2 targets: 3 in (targets + 1)");
    PAGE_HAS(awaken_forest, plain, 50, "  Entangle: cast at level 60");
    PAGE_HAS(awaken_forest, plain, 50, "  If it then fails a save, 3 harder, lag: 6 seconds");
    PAGE_HAS(awaken_forest, plain, 50, "  Crushing branches: 161-200");
    PAGE_HAS(hurricane, plain, 50, "  Damage to everyone it hits: 341-370 at your level, 50");
    PAGE_HAS(hurricane, plain, 50, "  Chance a target escapes: 29%");
    PAGE_HAS(hurricane, plain, 50, "  Knockdown outdoors, if flying: 4%");
    PAGE_HAS(hurricane, plain, 50, "  Knockdown outdoors, otherwise: never");
    PAGE_HAS(hurricane, plain, 51, "  Knockdown outdoors, if flying: 9%");
    PAGE_HAS(hurricane, plain, 51, "  Knockdown outdoors, otherwise: 1%");
    PAGE_HAS(storm_shield, plain, 50, "  Duration: 10-11 game hours (12.5-13.75 minutes) at your level");
    PAGE_HAS(storm_shield, plain, 50, "  Chance of a lightning bolt when you block: 1 in 3");
    PAGE_HAS(storm_shield, plain, 50, "  Lightning damage: 60-360 at your level, 50");
    PAGE_HAS(blood_to_stone, plain, 50, "  Lasts: 50 seconds, or its missing health % in seconds if more");
    PAGE_HAS(blood_to_stone, plain, 50, "  If it passes a paralysis save, 5 harder: half that");
    PAGE_HAS(blood_to_stone, plain, 50, "  Vitality lost: 3");
    PAGE_HAS(blood_to_stone, plain, 50, "  Extra moves per step: 1-4");
    PAGE_HAS(mirage, plain, 50, "  Duration: 3-4 game hours (3.75-5 minutes)");

    PAGE_HAS(thornskin, plain, 50, "  Armor class: -12 at your level, 50");
    PAGE_HAS(thornskin, plain, 50, "  Thorns on a melee hit of over 5: 5-10");
    PAGE_HAS(thornskin, plain, 50, "  With ironwood: 10-20");
    PAGE_HAS(thornskin, plain, 1, "  Thorns on a melee hit of over 5: 2-4");
    PAGE_HAS(thornskin, plain, 50, "  Fire damage to the wearer: 130% of normal");
    PAGE_HAS(thornskin, plain, 50, "  Other effects on fire damage, such as ironwood, add to that.");
    PAGE_HAS(flame_sphere, plain, 50, "  Fire damage: 45-270 at your level, 50");
    PAGE_HAS(flame_sphere, plain, 50, "  If the target fails its save: 59-359");
    PAGE_HAS(flame_sphere, ruiner, 50, "  Fire damage: 50-302 at your level, 50");
    PAGE_HAS(flame_sphere, ruiner, 50, "  If the target fails its save: 66-402");
    PAGE_HAS(flame_sphere, plain, 50, "  Stopped by: globe of invulnerability or greater spirit ward");
    PAGE_HAS(blight, plain, 50, "  Damage: 120-720 at your level, 50");
    PAGE_HAS(blight, plain, 50, "  If the target fails its save: 240-1440");
    PAGE_HAS(blight, scourge, 50, "  Damage: 134-806 at your level, 50");
    PAGE_HAS(desecrate_land, plain, 50, "  Lasts: 50 seconds at your level");
    PAGE_HAS(desecrate_land, plain, 50, "  Innate magic resistance here: 10 points worse");
    PAGE_HAS(forbiddance, plain, 50, "  Lasts: 50 seconds at your level");
    PAGE_HAS(waves_fatigue, plain, 50, "  Vitality lost per wave: 8-14 at your level, 50");
    PAGE_HAS(waves_fatigue, plain, 50, "  If it passes a paralysis save, 8 harder: 2-3");
    PAGE_HAS(waves_fatigue, plain, 50, "  Waves: one now, then after 2 seconds and 4 seconds");
    PAGE_HAS(waves_fatigue, plain, 1, "  Vitality lost per wave: -4 to 2 at your level, 1");
    PAGE_HAS(waves_fatigue, plain, 1, "  A wave below 0 gives the target vitality.");
    assert(page(waves_fatigue_facts, plain, 50).find("gives the target") == std::string::npos);
    PAGE_HAS(acid_rain, plain, 50, "  Acid damage per wave: 80-100 at your level, 50");
    PAGE_HAS(acid_rain, storm, 50, "  Acid damage per wave: 100-120 at your level, 50");
    PAGE_HAS(acid_rain, plain, 50, "  Waves: 5, one every 2 seconds");
    PAGE_HAS(acid_rain, plain, 9, "  Waves: none at your level");
    PAGE_HAS(acid_rain, plain, 50, "  Cast on the room, on a passed save: 40-50");
    PAGE_HAS(horrid_wilting, plain, 50, "  Acid damage: 110-900 at your level");
    PAGE_HAS(horrid_wilting, plain, 50, "  If it fails its save: 143-1170");
    PAGE_HAS(horrid_wilting, plain, 1, "  Acid damage: 0-18 (none below 1 lands) at your level");
    PAGE_HAS(horrid_wilting, plain, 50, "  Plants, slimes, water elementals: 146-1200 if saved");
    PAGE_HAS(horrid_wilting, plain, 50, "  Blindness on a second failed save: 6 seconds to 12 seconds");
    PAGE_HAS(shambler, plain, 50, "  Mounds in city, desert or road: 1-2");
    PAGE_HAS(shambler, plain, 50, "  In field, hills or mountain: 2-4");
    PAGE_HAS(shambler, plain, 50, "  In forest, swamp or mushroom ground: 3-6");
    PAGE_HAS(shambler, plain, 50, "  A mound whose charm can lapse dies after: 2 minutes to 12 minutes");
    PAGE_HAS(implosion, plain, 50, "  Negative damage: 350-1250 at your level, 50");
    PAGE_HAS(implosion, plain, 50, "  If the target saves: 194-694");
    PAGE_HAS(sandstorm, plain, 50, "  Hits after: 16 seconds to 32 seconds");
    PAGE_HAS(sandstorm, plain, 50, "  Gas damage on a failed save: 150-900 at your level, 50");
    PAGE_HAS(sandstorm, plain, 50, "  On a passed save: 75-450");
    PAGE_HAS(sandstorm, plain, 50, "  In water, it only soaks the room for: 1 minute");
    PAGE_HAS(firelance, plain, 50, "  Fire damage: 68-476 at your level, 50");
    PAGE_HAS(firelance, plain, 50, "  If the target saves: 45-317");
    PAGE_HAS(drain_nature, plain, 50, "  Healing at your level on most ground: 88");
    PAGE_HAS(drain_nature, plain, 50, "  City: 57");
    PAGE_HAS(drain_nature, scourge, 50, "  Healing at your level on most ground: 190");
    PAGE_HAS(drain_nature, warrior, 50, "  Healing at your level on most ground: 41");
    PAGE_HAS(create_pond, plain, 50, "  Stays: 2 minutes 30 seconds");
    PAGE_HAS(create_pond, plain, 50, "  From level 31: drinking casts drain nature and invigorate at that level");
    PAGE_HAS(create_pond, plain, 50, "  From level 51: it also casts regeneration");
    PAGE_HAS(toxic_fog, plain, 50, "  Gas damage: 80-560 at your level, 50");
    PAGE_HAS(toxic_fog, plain, 51, "  Gas damage: 80-640 at your level, 51");
    PAGE_HAS(toxic_fog, plain, 50, "  If the target fails its save: 53-373");
    PAGE_HAS(faluzures_vitality, plain, 50, "  Maximum hit points: +175 at your level, 50");
    PAGE_HAS(faluzures_vitality, plain, 50, "  Maximum moves: +50");
    PAGE_HAS(sap_nature, plain, 50, "  Move regeneration: +22 at your level");
    PAGE_HAS(sap_nature, scourge, 50, "  Move regeneration: +27 at your level");
    PAGE_HAS(sap_nature, plain, 50, "  Endurance refuses it, and Mielikki's vitality except on druids and huntsmen.");
    PAGE_HAS(sap_nature, plain, 50, "  With Faluzure's vitality up, you cannot give it to a non-blighter.");
    PAGE_HAS(bloodstone, plain, 50, "  Duration: 160-161 game hours (200-201.25 minutes) at your level");

    PAGE_HAS(baladors_protection, reaver, 50, "  Armor class: -20");
    PAGE_HAS(baladors_protection, reaver, 50, "  All five saves: -3");
    PAGE_HAS(baladors_protection, reaver, 45, "  It protects you from good and from evil.");
    assert(page(baladors_protection_facts, reaver, 45).find("saves") == std::string::npos);
    PAGE_HAS(baladors_protection, reaver, 4, "  It gives you nothing until level 5.");
    assert(page(baladors_protection_facts, reaver, 5).find("protects") == std::string::npos);
    PAGE_HAS(ferrix_precision, reaver, 50, "  Maximum dexterity and hitroll: +9 at your level, 50");
    PAGE_HAS(kanchelsis_fury, reaver, 50, "  Maximum strength: +9 at your level, 50");
    PAGE_HAS(kanchelsis_fury, reaver, 51, "  Combat pulse: -1");
    PAGE_HAS(kanchelsis_fury, reaver, 53, "  Combat pulse: -2");
    PAGE_HAS(kanchelsis_fury, reaver, 56, "  Combat pulse: -3");
    PAGE_HAS(kanchelsis_fury, earth, 56, "  Combat pulse: -2");
    assert(page(kanchelsis_fury_facts, reaver, 50).find("Combat pulse") == std::string::npos);
    PAGE_HAS(kanchelsis_fury, reaver, 41, "  One with the off hand too, on a dual wield skill roll.");
    assert(page(kanchelsis_fury_facts, reaver, 40).find("off hand") == std::string::npos);
    PAGE_HAS(kanchelsis_fury, reaver, 56, "  Another with the off hand.");
    PAGE_HAS(ilienzes_flame_sword, reaver, 50, "  Hitroll: +1-4");
    PAGE_HAS(ilienzes_flame_sword, reaver, 50, "  Fire on each hit: 1-12");
    PAGE_HAS(ilienzes_flame_sword, reaver, 1, "  Fire on each hit: 0-1 (none below 1 lands)");
    PAGE_HAS(ilienzes_flame_sword, reaver, 50, "  It bursts at a charge above: 4-40");
    PAGE_HAS(ilienzes_flame_sword, reaver, 50, "  A burst of fire deals, per charge: 1-12");
    PAGE_HAS(cegilunes_searing_blade, reaver, 50, "  Each hit raises the tier: 1 in 5");
    PAGE_HAS(cegilunes_searing_blade, reaver, 50, "  Fire by tier: 8-16, 16-32, 32-40, 40-56, 56-64, 64-80");
    PAGE_HAS(cegilunes_searing_blade, reaver, 50, "  From tier 3, each hit sets a burn: 1 in 6");
    PAGE_HAS(cegilunes_searing_blade, reaver, 50, "  Burn: 12-48 fire every 4 seconds, 4 times");
    PAGE_HAS(girilals_granite_hammer, reaver, 50, "  Damroll: +3 at your level, 50");
    PAGE_HAS(girilals_granite_hammer, reaver, 50, "  Earth damage on each hit: 8-20");
    PAGE_HAS(girilals_granite_hammer, reaver, 1, "  Earth damage on each hit: 1-8");
    PAGE_HAS(ileshs_smashing_fury, reaver, 50, "  Each hit casts at your level: 1 in 5");
    PAGE_HAS(ileshs_smashing_fury, reaver, 50, "  Acid immolate replaces the stream: 1 in 4");
    PAGE_HAS(thryms_icerazor, reaver, 50, "  Hitroll: +5 at your level, 50");
    PAGE_HAS(thryms_icerazor, reaver, 56, "  Hitroll: +10 at your level, 56");
    PAGE_HAS(thryms_icerazor, reaver, 50, "  Cold damage on each hit: 6-8");
    PAGE_HAS(thryms_icerazor, reaver, 50, "  With coldshield: +3-4");
    PAGE_HAS(thryms_icerazor, reaver, 50, "  With fireshield: -4");
    PAGE_HAS(lliendils_stormshock, reaver, 50, "  Combat pulse: -2 to -1");
    PAGE_HAS(lliendils_stormshock, reaver, 50, "  Lightning on each hit: 1-12");
    PAGE_HAS(stormcallers_fury, reaver, 50, "  Each hit on the same target builds a charge: 1 in 2");
    PAGE_HAS(stormcallers_fury, reaver, 50, "  A flurry comes above: 14-16 charges");
    PAGE_HAS(stormcallers_fury, reaver, 50, "  Extra hits in the flurry: 3-6");
    PAGE_HAS(kostchtchies_implosion, reaver, 50, "  Cold damage: 460-550");
    return 0;
}
'''


def shared_functions(file, prefixes):
    text = source(file).read_text()
    names = [name for name in re.findall(r"^(?:static )?[\w:]+ (\w+)\(", text, re.M)
             if name.startswith(prefixes) and not name.endswith("_facts")]
    found = []
    for name in dict.fromkeys(names):
        match = re.search(rf"^(?:static )?[\w:]+ {name}\(", text, re.M)
        found.append(extract_function(file, match.group(0)))
    return found


def check_sources():
    for file, handlers in HANDLER_CALLS.items():
        code = strip_comments(source(file).read_text())
        for handler, calls in handlers.items():
            bodies = function_bodies(code, rf"\b(?:void|bool|int|float)\s+{handler}\s*\(")
            assert bodies, handler
            normal = re.sub(r"\s+", " ", bodies[0])
            for call in calls:
                assert call in normal, f"{handler}: {call}"
    # The steps cost lives in the move code; the page's number must be the one it reads.
    actmove = re.sub(r"\s+", " ", strip_comments(source("actmove.c").read_text()))
    assert "SPELL_BLOODTOSTONE)) { extern int blood_to_stone_move_cost(const Rolls &rolls); " \
           "need_movement += blood_to_stone_move_cost(live_rolls);" in actmove
    # The thorn's no-affect fallback stays beside the shared roll.
    fight = re.sub(r"\s+", " ", strip_comments(source("fight.c").read_text()))
    assert "afp == NULL ? 2 : thornskin_damage( live_rolls, afp->level)" in fight
    # Thornskin's fire line is the live barkskin factor, a spell damage modifier for fire.
    mods = re.sub(r"\s+", " ", strip_comments(source("dam_mods.c").read_text()))
    assert mods.index("spell_damage_modifiers[] =") < mods.index("dam_factor[DF_BARKFIRE]")
    assert "IS_AFFECTED5(victim, AFF5_THORNSKIN)) { dam_mod->type = dam_mod_type::More; " \
           "dam_mod->mod += dam_factor[DF_BARKFIRE] - 1.0;" in mods
    assert "dam_factor[DF_BARKFIRE] = barkskin_fire_factor();" in fight
    # Vines are spent in raw_damage, outside the melee skin chain fist of dragon bypasses.
    assert "skin = SPELL_VINES" not in fight
    assert "IS_AFFECTED5(victim, AFF5_VINES) && (flags & RAWDAM_VINES)" in fight
    # Flags the stage lines rest on.
    blis = re.sub(r"\s+", " ", strip_comments(source("blispells.c").read_text()))
    for line in ("spell_damage(ch, victim, dam, SPLDAM_FIRE, SPLDAM_GLOBE | SPLDAM_GRSPIRIT, &messages)",
                 "spell_damage(ch, victim, dam, SPLDAM_GENERIC, SPLDAM_GLOBE | SPLDAM_GRSPIRIT, &messages)",
                 "spell_damage(ch, victim, dam, SPLDAM_NEGATIVE, 0, &messages)",
                 "spell_damage(ch, victim, dam, SPLDAM_GAS, 0, &messages)",
                 "spell_damage(ch, victim, dam, SPLDAM_ACID, SPLDAM_NODEFLECT, &messages)"):
        assert line in blis, line
    spells = re.sub(r"\s+", " ", strip_comments(source("magic/spells.c").read_text()))
    assert "spell_damage(ch, tch, dam, SPLDAM_GENERIC, 0, &messages)" in spells
    assert "spell_damage(ch, tch, dam, SPLDAM_GENERIC, 0, &message)" in spells
    magic = re.sub(r"\s+", " ", strip_comments(source("magic.c").read_text()))
    assert "result = spell_damage(ch, vict, dam, SPLDAM_LIGHTNING, 0, &messages)" in magic
    # Cast level reaches the handlers the pages describe.
    assert "spell_call_lightning(level, ch, victim, 0)" in spells
    # Registration and lists.
    table = strip_comments(source("abilities.c").read_text())
    header = source("abilities.h").read_text()
    for constant, name, _ in SPELLS:
        assert re.search(rf"case {constant}:\s*return {name}_facts;", table), constant
        assert f"std::string {name}_facts(char_data *ch);" in header, name
    no_numbers = (ROOT / "tests/fixtures/ability_coverage_no_numbers.txt").read_text().split()
    pending = (ROOT / "tests/fixtures/ability_coverage_pending.txt").read_text().split()
    registrations = strip_comments(source("skills.c").read_text())
    blocks = {re.split(r",\s*", block, 2)[1].strip(): block for block in re.split(r"(?=SPELL_CREATE)", registrations)
              if block.startswith("SPELL_CREATE") and block.count(",") >= 2}
    for constant in DISABLED:
        assert constant in no_numbers and constant not in pending, constant
        assert "SPELL_ADD(" not in blocks[constant], constant
    assert "SPELL_MINOR_CREATION" in no_numbers and "SPELL_MINOR_CREATION" not in pending


def main():
    check_sources()
    functions = [extract_function("utility.c", "int dice(int num, int size)"),
                 extract_function("utility.c", "int GET_CLASS(P_char ch, uint m_class)"),
                 extract_function("fight.c", "float barkskin_fire_factor(")]
    for file, prefixes in PREFIXES.items():
        functions += shared_functions(file, prefixes)
    functions += [extract_function(file, signature) for file, signature in PAGE_PARTS]
    functions += [extract_function(file, f"std::string {name}_facts(") for _, name, file in SPELLS]
    pages = ",\n".join(f'    {{ "{name}", {name}_facts }}' for _, name, _ in SPELLS)
    build = ROOT / "bin/tests"
    build.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ability-batch-8-", dir=build) as temporary:
        directory = Path(temporary)
        harness = directory / "batch8.cpp"
        harness.write_text(HARNESS.replace("PAGES", pages).replace("FUNCTIONS", "\n".join(functions)))
        binary = directory / "batch8"
        subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-Wno-unused-function",
                        "-ffunction-sections", "-fdata-sections", "-Wl,--gc-sections",
                        "-fsanitize=address,undefined", "-fno-sanitize-recover=undefined",
                        "-Isrc", "-I/usr/include/mysql", "-I/usr/include/libxml2",
                        str(harness), "src/abilities/abilities.c", "src/core/random.c",
                        "-o", str(binary)], cwd=ROOT, check=True)
        subprocess.run([str(binary)], cwd=directory, check=True)


if __name__ == "__main__":
    main()
