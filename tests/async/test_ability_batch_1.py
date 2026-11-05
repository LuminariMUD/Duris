#!/usr/bin/env python3
"""Shared ability numbers, batch 1: the magic.c spells with handlers in lines 279-6644.

Builds the batch's shared and facts functions, extracted from magic.c, with
src/abilities/abilities.c and the real RNG under sanitizers. The pre-conversion
expressions below are the oracle: under 40 seeds at several levels, each shared roll
draws the same value and leaves the same next draw as the original, and the value lies
within the range its facts show. Facts never roll and keep every line to 79 characters,
and each handler calls its shared functions.
"""
import re
import subprocess
import tempfile
from pathlib import Path

from _paths import ROOT, extract_function, source
from _source_contract import function_bodies, strip_comments

# Each spell the batch converted, and its facts function.
FACTS = {
    "SPELL_FORTITUDE": "fortitude_facts", "SPELL_ARMOR": "armor_facts",
    "SPELL_VIRTUE": "virtue_facts", "SPELL_MAGIC_MISSILE": "magic_missile_facts",
    "SPELL_CHILL_TOUCH": "chill_touch_facts", "SPELL_BURNING_HANDS": "burning_hands_facts",
    "SPELL_SHOCKING_GRASP": "shocking_grasp_facts", "SPELL_FROSTBITE": "frostbite_facts",
    "SPELL_LIGHTNING_BOLT": "lightning_bolt_facts", "SPELL_CONE_OF_COLD": "cone_of_cold_facts",
    "SPELL_ENERVATION": "enervation_facts", "SPELL_RESTORE_SPIRIT": "restore_spirit_facts",
    "SPELL_ENERGY_DRAIN": "energy_drain_facts", "SPELL_LIFE_LEECH": "life_leech_facts",
    "SPELL_WITHER": "wither_facts", "SPELL_LIVING_STONE": "living_stone_facts",
    "SPELL_GREATER_LIVING_STONE": "greater_living_stone_facts",
    "SPELL_METEOR_SWARM": "meteorswarm_facts", "SPELL_ENTROPY_STORM": "entropy_storm_facts",
    "SPELL_CHAIN_LIGHTNING": "chain_lightning_facts", "SPELL_RING_LIGHTNING": "ring_lightning_facts",
    "SPELL_BIGBYS_CLENCHED_FIST": "bigbys_clenched_fist_facts",
    "SPELL_MISSILE_BARRAGE": "missile_barrage_facts", "SPELL_ANTI_MAGIC_RAY": "anti_magic_ray_facts",
    "SPELL_BIGBYS_CRUSHING_HAND": "bigbys_crushing_hand_facts",
    "SPELL_DIMENSION_DOOR": "dimension_door_facts", "SPELL_RELOCATE": "relocate_facts",
    "SPELL_WAY_OF_THE_WIND": "relocate_facts", "SPELL_WIZARD_EYE": "wizard_eye_facts",
    "SPELL_REJUVENATE_MAJOR": "rejuvenate_major_facts", "SPELL_AGE": "age_facts",
    "SPELL_REJUVENATE_MINOR": "rejuvenate_minor_facts",
    "SPELL_RAY_OF_ENFEEBLEMENT": "ray_of_enfeeblement_facts", "SPELL_EARTHQUAKE": "earthquake_facts",
    "SPELL_CALL_WOODLAND": "call_woodland_beings_facts", "SPELL_EARTHEN_MAUL": "earthen_maul_facts",
    "SPELL_DISPEL_EVIL": "dispel_evil_facts", "SPELL_DISPEL_GOOD": "dispel_good_facts",
    "SPELL_HARM": "harm_facts", "SPELL_FULL_HARM": "full_harm_facts",
    "SPELL_DESTROY_UNDEAD": "destroy_undead_facts", "SPELL_FIRESTORM": "firestorm_facts",
    "SPELL_FLAMESTRIKE": "flamestrike_facts", "SPELL_TELEPORT": "teleport_facts",
    "SPELL_BLESS": "bless_facts", "SPELL_BLINDNESS": "blindness_facts", "SPELL_NOVA": "nova_facts",
    "SPELL_ELEMENTAL_SWARM": "elemental_swarm_facts", "SPELL_SERENDIPITY": "serendipity_facts",
    "SPELL_PULCHRITUDE": "pulchritude_facts", "SPELL_CREATE_WATER": "create_water_facts",
    "SPELL_WANDERING_WOODS": "wandering_woods_facts", "SPELL_AID": "aid_facts",
    "SPELL_DISPEL_LIFEFORCE": "dispel_lifeforce_facts",
    "SPELL_ALTER_ENERGY_POLARITY": "alter_energy_polarity_facts",
    "SPELL_INVOKE_NEG_ENERGY": "invoke_negative_energy_facts",
    "SPELL_CHANNEL_NEG_ENERGY": "channel_negative_energy_facts",
    "SPELL_SENSE_HOLINESS": "sense_holiness_facts", "SPELL_LIFELUST": "lifelust_facts",
    "SPELL_CYCLONE": "cyclone_facts", "SPELL_SIREN_SONG": "siren_song_facts",
    "SPELL_DECAYING_FLESH": "decaying_flesh_facts",
    "SPELL_CONJURE_ELEMENTAL": "conjure_elemental_facts", "SPELL_MIRROR_IMAGE": "mirror_image_facts",
    "SPELL_CONJURE_GREATER_ELEMENTAL": "conjure_greater_elemental_facts",
    "SPELL_VITALIZE_MANA": "vitalize_mana_facts", "SPELL_CONSECRATE_LAND": "consecrate_land_facts",
    "SPELL_SUMMON_INSECTS": "summon_insects_facts", "SPELL_PRISMATIC_SPRAY": "prismatic_spray_facts",
    "SPELL_COLOR_SPRAY": "color_spray_facts", "SPELL_PRISMATIC_RAY": "prismatic_ray_facts",
    "SPELL_ELEMENTAL_AURA": "elemental_aura_facts", "SPELL_WIND_TUNNEL": "wind_tunnel_facts",
    "SPELL_BINDING_WIND": "binding_wind_facts",
}

# Each handler (or the event or helper that plays it) and the shared functions it calls.
HANDLERS = {
    "spell_single_prismatic_ray": "prismatic_ray_shimmering_damage prismatic_ray_red_damage "
                                  "prismatic_ray_orange_damage prismatic_ray_blue_damage prismatic_ray_saved",
    "spell_prismatic_ray": "prismatic_ray_extra_rays",
    "spell_prismatic_spray": "prismatic_spray_rays",
    "spell_anti_magic_ray": "anti_magic_ray_damage anti_magic_ray_saved anti_magic_ray_noshrug_chance anti_magic_ray_noshrug_roll "
                            "anti_magic_ray_save_penalty",
    "spell_magic_missile": "magic_missile_count magic_missile_damage",
    "spell_chill_touch": "chill_touch_damage chill_touch_failed_save chill_touch_stat_cap "
                         "chill_touch_stat_loss chill_touch_duration chill_touch_drains_all",
    "spell_frostbite": "frostbite_damage frostbite_strength frostbite_duration",
    "spell_burning_hands": "burning_hands_damage",
    "spell_shocking_grasp": "shocking_grasp_damage shocking_grasp_failed_save",
    "spell_lightning_bolt": "lightning_bolt_damage lightning_bolt_failed_save",
    "spell_cone_of_cold": "cone_of_cold_damage cone_of_cold_duration cone_of_cold_wet_duration "
                          "cone_of_cold_strength",
    "spell_invoke_negative_energy": "invoke_negative_energy_damage",
    "spell_restore_spirit": "restore_spirit_damage restore_spirit_untrained "
                            "restore_spirit_untrained_damage restore_spirit_saved "
                            "restore_spirit_level_bonus restore_spirit_vamp",
    "spell_enervation": "enervation_damage enervation_untrained enervation_untrained_damage "
                        "enervation_saved enervation_level_bonus enervation_vamp enervation_duration "
                        "enervation_movement",
    "spell_life_leech": "life_leech_damage life_leech_saved life_leech_kill_level life_leech_vamp",
    "spell_energy_drain": "energy_drain_level energy_drain_damage energy_drain_saved "
                          "energy_drain_kill_level energy_drain_vamp energy_drain_taps "
                          "energy_drain_moves energy_drain_duration energy_drain_regen "
                          "energy_drain_extension",
    "spell_wither": "wither_undead_damage wither_armor_class wither_duration",
    "spell_mirror_image": "mirror_image_count",
    "spell_call_woodland_beings": "call_woodland_beings_level call_woodland_beings_hit_points "
                                  "call_woodland_beings_roll_bonus",
    "spell_elemental_swarm": "elemental_swarm_level elemental_swarm_hit_points elemental_swarm_hitroll "
                             "elemental_swarm_damroll elemental_swarm_lifetime",
    "spell_conjour_elemental": "conjure_elemental_charisma conjure_refused_to_summoner "
                               "conjure_elemental_stronger_level "
                               "conjure_elemental_weaker_level conjure_elemental_level "
                               "conjure_elemental_hit_points conjure_elemental_roll_bonus "
                               "conjure_elemental_home_hit_points conjure_elemental_home_roll_bonus",
    "spell_conjour_greater_elemental": "conjure_elemental_charisma conjure_refused_to_summoner "
                                       "conjure_greater_elemental_level "
                                       "conjure_greater_elemental_hit_points "
                                       "conjure_greater_elemental_hitroll conjure_greater_elemental_damroll",
    "spell_living_stone": "living_stone_level living_stone_hit_points living_stone_hitroll "
                          "living_stone_damroll living_stone_lifetime",
    "spell_greater_living_stone": "greater_living_stone_level greater_living_stone_hit_points "
                                  "greater_living_stone_hitroll greater_living_stone_damroll "
                                  "greater_living_stone_damage_dice greater_living_stone_damage_sides "
                                  "greater_living_stone_lifetime",
    "spell_earthen_maul": "earthen_maul_damage earthen_maul_saved earthen_maul_terrain",
    "spell_bigbys_clenched_fist": "bigbys_clenched_fist_damage bigbys_clenched_fist_failed_save",
    "spell_channel_negative_energy": "channel_negative_energy_damage",
    "spell_bigbys_crushing_hand": "bigbys_crushing_hand_damage bigbys_crushing_hand_failed_save",
    "spell_solbeeps_single_missile": "missile_barrage_damage missile_barrage_failed_save",
    "spell_solbeeps_missile_barrage": "missile_barrage_count",
    "spell_single_chain_lightning": "chain_lightning_damage chain_lightning_leap "
                                    "chain_lightning_player_damage chain_lightning_area_damage",
    "spell_single_lightning_ring": "ring_lightning_damage ring_lightning_player_damage",
    "spell_cyclone": "cyclone_damage cyclone_halved cyclone_stun_chance cyclone_stun_roll cyclone_stun",
    "spell_single_meteorswarm": "meteorswarm_damage meteorswarm_player_damage meteorswarm_area_damage",
    "spell_entropy_storm": "entropy_storm_healing",
    "spell_earthquake": "earthquake_fall_damage earthquake_stagger_damage",
    "spell_single_firestorm": "firestorm_damage firestorm_saved firestorm_player_damage "
                              "firestorm_area_damage",
    "spell_firestorm": "firestorm_room_duration",
    "spell_dispel_good": "dispel_good_damage dispel_good_saved",
    "spell_dispel_evil": "dispel_evil_damage dispel_evil_saved",
    "spell_flamestrike": "flamestrike_damage flamestrike_failed_save flamestrike_zealot_damage "
                         "flamestrike_half flamestrike_brands flamestrike_brand_duration",
    "spell_destroy_undead": "destroy_undead_damage destroy_undead_saved destroy_undead_zealot_damage",
    "spell_harm": "harm_damage harm_zealot_damage",
    "spell_full_harm": "full_harm_damage full_harm_failed_save full_harm_zealot_damage",
    "event_fleshdecay": "decaying_flesh_damage decaying_flesh_interval",
    "spell_decaying_flesh": "decaying_flesh_interval decaying_flesh_waves",
    "spell_fortitude": "fortitude_duration fortitude_constitution",
    "event_nova": "nova_delay",
    "spell_nova": "nova_delay",
    "resolve_nova": "nova_level",
    "spell_siren_song": "siren_song_distance",
    "spell_elemental_aura": "elemental_aura_duration elemental_aura_max_stat",
    "spell_armor": "armor_duration armor_armor_class",
    "spell_virtue": "virtue_duration",
    "spell_dispel_lifeforce": "dispel_lifeforce_duration dispel_lifeforce_modifier",
    "spell_alter_energy_polarity": "alter_energy_polarity_duration",
    "spell_sense_holiness": "sense_holiness_duration",
    "spell_wizard_eye": "wizard_eye_distance",
    "spell_dimension_door": "dimension_door_lag dimension_door_distance",
    "spell_relocate": "relocate_lag",
    "spell_teleport": "teleport_range",
    "spell_lifelust": "lifelust_duration lifelust_bonus",
    "spell_aid": "aid_shortening aid_duration",
    "spell_bless": "bless_duration bless_hitroll bless_saving_spell",
    "spell_blindness": "blindness_duration",
    "spell_pulchritude": "pulchritude_duration pulchritude_charisma",
    "spell_serendipity": "serendipity_duration serendipity_luck",
    "spell_create_water": "create_water_amount",
    "spell_wandering_woods": "wandering_woods_duration",
    "spell_consecrate_land": "consecrate_land_duration",
    "spell_summon_insects": "summon_insects_duration",
    "spell_binding_wind": "binding_wind_duration",
    "spell_wind_tunnel": "wind_tunnel_duration",
    "spell_vitalize_mana": "vitalize_mana_amount",
    "spell_rejuvenate_minor": "rejuvenate_minor_years rejuvenate_minor_move_regen "
                              "rejuvenate_minor_hit_regen",
    "spell_ray_of_enfeeblement": "ray_of_enfeeblement_chance ray_of_enfeeblement_duration "
                                 "ray_of_enfeeblement_damroll",
    "spell_age": "age_years",
    "spell_rejuvenate_major": "rejuvenate_major_years",
}

HARNESS = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "magic/spells.h"
#include "abilities/abilities.h"
#include <climits>
#include <cstdio>
#include <cstdlib>
#include <functional>
#include <set>
#include <string>

void randomize(uint64_t seed);

// The server functions the extracted code reads.
float get_property(const char *, double fallback) { return fallback; }
int get_property(const char *, int fallback) { return fallback; }
P_char get_linked_char(P_char, ush_int) { return nullptr; }
static int infuse_life;
int GET_CHAR_SKILL_P(P_char, int skill) { return skill == SKILL_INFUSE_LIFE ? infuse_life : 0; }

// The caster, and the viewer of every page.
static char_data you;
static const P_char ch = &you;

EXTRACTED_FUNCTIONS

// The next draw after a roll; equal fingerprints after equal seeds mean equal draw counts.
static int fingerprint() { return number(0, INT_MAX); }

static void check(bool ok, const char *what, const std::string &detail = "") {
    if (!ok) {
        fprintf(stderr, "FAIL: %s %s\n", what, detail.c_str());
        abort();
    }
}

// The original expression and the shared function draw the same value and leave the same
// next draw under 40 seeds, and the value lies within `bounds`.
static void same_rolls(const char *name, int level, const std::function<int()> &original,
                       const std::function<int()> &shared, Range bounds) {
    for (uint64_t seed = 1; seed <= 40; ++seed) {
        randomize(seed);
        const int expected = original(), expected_next = fingerprint();
        randomize(seed);
        const int actual = shared(), actual_next = fingerprint();
        const std::string detail = "level " + std::to_string(level) + " seed " + std::to_string(seed) +
            ": " + std::to_string(actual) + " vs " + std::to_string(expected) + ", range " + show(bounds);
        check(actual == expected && actual_next == expected_next, name, detail);
        check(bounds.low <= actual && actual <= bounds.high, name, detail);
    }
}

// An original expression from before the conversion, its shared function, and how its
// facts bound it: by its lowest and highest rolls, swapped when the value falls as its
// roll rises, or by `range` where the facts combine the functions another way.
struct Roll {
    const char *name;
    std::function<int(int)> original;
    std::function<int(const Rolls &, int)> shared;
    bool falls = false;
    std::function<Range(int)> range = nullptr;
};

static const Roll oracle[] = {
    { "prismatic_ray_shimmering_damage", [](int level) { return dice(level, 9); },
      [](const Rolls &r, int level) { return prismatic_ray_shimmering_damage(r, level); } },
    { "prismatic_ray_red_damage", [](int level) { return 400 + dice(level, 2); },
      [](const Rolls &r, int level) { return prismatic_ray_red_damage(r, level); } },
    { "prismatic_ray_orange_damage", [](int level) { return 275 + dice(level, 2); },
      [](const Rolls &r, int level) { return prismatic_ray_orange_damage(r, level); } },
    { "prismatic_ray_blue_damage", [](int level) { return 150 + dice(level, 2); },
      [](const Rolls &r, int level) { return prismatic_ray_blue_damage(r, level); } },
    { "prismatic_spray_rays", [](int) { return number(1, 2); },
      [](const Rolls &r, int) { return prismatic_spray_rays(r); } },
    { "anti_magic_ray_damage",
      [](int level) { int temp = MIN(46, (level + 1)); return dice(5 * temp, 10); },
      [](const Rolls &r, int level) { return anti_magic_ray_damage(r, level); } },
    { "magic_missile_damage", [](int level) { return (dice(1, 4) * 4 + number(1, level)); },
      [](const Rolls &r, int level) { return magic_missile_damage(r, level); } },
    { "chill_touch_damage", [](int level) { return (dice(1, 6) + 5 * 4 + level); },
      [](const Rolls &r, int level) { return chill_touch_damage(r, level); } },
    { "chill_touch_stat_loss", [](int dam) { return -(number(1, dam)); },
      [](const Rolls &r, int dam) { return chill_touch_stat_loss(r, dam); }, true },
    { "frostbite_damage", [](int level) { return (int)(MIN(40, level) * 5) + number(1, 20); },
      [](const Rolls &r, int level) { return frostbite_damage(r, level); } },
    { "frostbite_strength", [](int) { return -number(10, 15); },
      [](const Rolls &r, int) { return frostbite_strength(r); }, true },
    { "burning_hands_damage",
      [](int level) { int num_dice = (level / 10); return (dice((num_dice + 5), 6) * 4); },
      [](const Rolls &r, int level) { return burning_hands_damage(r, level); } },
    { "shocking_grasp_damage",
      [](int level) { int num_dice = (level / 6); return (dice(num_dice + 5, 6) * 4); },
      [](const Rolls &r, int level) { return shocking_grasp_damage(r, level); } },
    { "lightning_bolt_damage",
      [](int level) { int num_dice = (level / 5); return (dice(num_dice + 5, 6) * 4); },
      [](const Rolls &r, int level) { return lightning_bolt_damage(r, level); } },
    { "cone_of_cold_damage",
      [](int level) { int num_dice = (level / 4); return (dice(num_dice + 5, 6) * 4); },
      [](const Rolls &r, int level) { return cone_of_cold_damage(r, level); } },
    { "cone_of_cold_strength, wet",
      [](int) {
          int modifier = -number(5, 10);
          modifier -= number(5, 10);
          return modifier;
      },
      [](const Rolls &r, int) {
          int modifier = cone_of_cold_strength(r);
          modifier += cone_of_cold_strength(r);
          return modifier;
      },
      true },
    { "invoke_negative_energy_damage", [](int) { return dice(5, 10) + GET_LEVEL(ch); },
      [](const Rolls &r, int) { return invoke_negative_energy_damage(r, ch); } },
    { "restore_spirit_damage", [](int level) { return (int)((level * 2.5) + number(-10, 10)); },
      [](const Rolls &r, int level) { return restore_spirit_damage(r, level); } },
    { "enervation_damage", [](int level) { return (int)((level * 2.75) + number(-10, 10)); },
      [](const Rolls &r, int level) { return enervation_damage(r, level); } },
    { "enervation_duration",
      [](int) { return number(GET_LEVEL(ch) / 4, GET_LEVEL(ch)) * PULSE_VIOLENCE; },
      [](const Rolls &r, int) { return enervation_duration(r, ch, false); } },
    { "enervation_duration, saved",
      [](int) { return number(GET_LEVEL(ch) / 4, GET_LEVEL(ch) / 2) * PULSE_VIOLENCE; },
      [](const Rolls &r, int) { return enervation_duration(r, ch, true); } },
    { "life_leech_damage", [](int level) { return dice(1.5 * level, 5); },
      [](const Rolls &r, int level) { return life_leech_damage(r, level); } },
    { "energy_drain_damage", [](int level) { return (6 * level) + dice(level, 5); },
      [](const Rolls &r, int level) { return energy_drain_damage(r, level); } },
    { "energy_drain_moves", [](int) { return number(5, 30); },
      [](const Rolls &r, int) { return energy_drain_moves(r); } },
    { "wither_undead_damage", [](int level) { return dice(MIN(level, 46), 10); },
      [](const Rolls &r, int level) { return wither_undead_damage(r, level); } },
    { "call_woodland_beings hit points",
      [](int level) {
          int mlvl = (level / 5) * 2;
          int lvl = number(mlvl, mlvl * 3);
          int mob_level = BOUNDED(10, lvl, 42);
          return dice(mob_level / 2, 8) + mob_level;
      },
      [](const Rolls &r, int level) {
          return call_woodland_beings_hit_points(r, call_woodland_beings_level(r, level));
      } },
    { "elemental_swarm hit points",
      [](int level) {
          int lvl = number(level - 3, level + 3);
          int mob_level = BOUNDED(1, lvl, 51);
          return dice(mob_level, 7) + (mob_level * 2);
      },
      [](const Rolls &r, int level) {
          return elemental_swarm_hit_points(r, elemental_swarm_level(r, level));
      } },
    { "elemental_swarm_lifetime", [](int) { return number(5, 30) * WAIT_SEC; },
      [](const Rolls &r, int) { return elemental_swarm_lifetime(r); } },
    { "conjure_elemental level",
      [](int level) {
          int lvl;
          if (number(1, 100) < 20)
              lvl = level + number(2, 5);
          else
              lvl = level - number(-1, 5);
          return BOUNDED(10, lvl, 45);
      },
      [](const Rolls &r, int level) {
          int lvl;
          if (r.number(1, 100) < 20)
              lvl = conjure_elemental_stronger_level(r, level);
          else
              lvl = conjure_elemental_weaker_level(r, level);
          return conjure_elemental_level(lvl);
      },
      false,
      [](int level) {
          return Range{ conjure_elemental_level(conjure_elemental_weaker_level(highest_rolls, level)),
                        conjure_elemental_level(conjure_elemental_stronger_level(highest_rolls, level)) };
      } },
    { "conjure_elemental_weaker_level", [](int level) { return level - number(-1, 5); },
      [](const Rolls &r, int level) { return conjure_elemental_weaker_level(r, level); }, true },
    { "conjure_elemental_hit_points",
      [](int mob_level) { return dice(mob_level / 2, 10) + 3 * mob_level + infuse_life + 77; },
      [](const Rolls &r, int mob_level) { return conjure_elemental_hit_points(r, mob_level, infuse_life, 77); } },
    { "conjure_elemental_home_hit_points",
      [](int mob_level) { return (int)(dice(mob_level / 2, 12) + 6 * mob_level + infuse_life + 77); },
      [](const Rolls &r, int mob_level) {
          return conjure_elemental_home_hit_points(r, mob_level, infuse_life, 77);
      } },
    { "conjure_greater_elemental_level", [](int) { return number(49, 53); },
      [](const Rolls &r, int) { return conjure_greater_elemental_level(r); } },
    { "conjure_greater_elemental hit points",
      [](int) {
          ubyte level = number(49, 53);
          int hit;
          if (level == 49)
              hit = 450 + number(0, 50) + (infuse_life * 3) + 77;
          else if (level == 50)
              hit = 500 + number(0, 50) + (infuse_life * 3) + 77;
          else if (level == 51)
              hit = 550 + number(0, 50) + (infuse_life * 3) + 77;
          else if (level == 52)
              hit = 600 + number(0, 50) + (infuse_life * 3) + 77;
          else
              hit = 700 + number(0, 50) + (infuse_life * 3) + 77;
          return hit;
      },
      [](const Rolls &r, int) {
          return conjure_greater_elemental_hit_points(r, conjure_greater_elemental_level(r), infuse_life, 77);
      } },
    { "living_stone hit points",
      [](int level) {
          int lvl = number(level - 3, level + 3);
          int mob_level = BOUNDED(1, lvl, 56);
          return dice(mob_level, 3) + (mob_level * 2);
      },
      [](const Rolls &r, int level) {
          return living_stone_hit_points(r, living_stone_level(r, level));
      } },
    { "living_stone_lifetime", [](int) { return number(5, 10) * WAIT_SEC; },
      [](const Rolls &r, int) { return living_stone_lifetime(r); } },
    { "greater_living_stone hit points",
      [](int level) {
          int lvl = number(level - 3, level + 3);
          int mob_level = BOUNDED(1, lvl, 56);
          return dice(mob_level, 3) + (mob_level * 2);
      },
      [](const Rolls &r, int level) {
          return greater_living_stone_hit_points(r, greater_living_stone_level(r, level));
      } },
    { "greater_living_stone_lifetime", [](int) { return number(7, 12) * WAIT_SEC; },
      [](const Rolls &r, int) { return greater_living_stone_lifetime(r); } },
    { "earthen_maul_damage",
      [](int level) {
          int temp = MIN(20, (level / 2 + 1));
          int dam = dice(5 * temp, 9);
          if (level > 50)
              dam = dice(6 * temp, 9);
          return dam;
      },
      [](const Rolls &r, int level) { return earthen_maul_damage(r, level); } },
    { "bigbys_clenched_fist_damage",
      [](int level) { if (level > 50) level = 50; return (10 * level) + number(1, 25); },
      [](const Rolls &r, int level) { return bigbys_clenched_fist_damage(r, level); } },
    { "bigbys_crushing_hand, failed save",
      [](int level) {
          int dam = (12 * level) + number(1, 50);
          return (int)(dam * (number(175, 175 + MAX(0, level - 45) * 2) / 100.0));
      },
      [](const Rolls &r, int level) {
          return bigbys_crushing_hand_failed_save(r, bigbys_crushing_hand_damage(r, level), level);
      } },
    { "missile_barrage_damage", [](int) { return dice(30, 11); },
      [](const Rolls &r, int) { return missile_barrage_damage(r); } },
    { "missile_barrage_count",
      [](int level) {
          int num_missiles = 3;
          if (level >= 56 || !number(0, 55 - level))
              num_missiles++;
          return num_missiles;
      },
      [](const Rolls &r, int level) { return missile_barrage_count(r, level); }, true },
    { "chain_lightning_damage", [](int level) { return 8 * MIN(51, level) + number(level / 3, level) + 30; },
      [](const Rolls &r, int level) { return chain_lightning_damage(r, level); } },
    { "ring_lightning_damage",
      [](int level) {
          return (6 * MIN(51, level)) +
                 (GET_CLASS(ch, CLASS_ETHERMANCER) ? dice(level, 4) : number(1, level));
      },
      [](const Rolls &r, int level) { return ring_lightning_damage(r, ch, level); } },
    { "cyclone_damage",
      [](int level) {
          bool casterIsTempestMagus = GET_SPEC(ch, CLASS_ETHERMANCER, SPEC_TEMPESTMAGUS);
          int dam = dice((int)(MIN(level, 40) * 2), 10);
          if (casterIsTempestMagus)
              dam = (int)(dam * (1.5 + MAX(level - 30, 20) / 40.0));
          return dam;
      },
      [](const Rolls &r, int level) { return cyclone_damage(r, ch, level); } },
    { "meteorswarm_damage", [](int level) { return 80 + level * 7 + number(1, 40); },
      [](const Rolls &r, int level) { return meteorswarm_damage(r, level); } },
    { "earthquake_fall_damage",
      [](int level) {
          int dam = (int)(dice(1, 30) + level);
          if (GET_SPEC(ch, CLASS_CLERIC, SPEC_ZEALOT))
              dam = (int)(dam * 1.25);
          return dam;
      },
      [](const Rolls &r, int level) { return earthquake_fall_damage(r, ch, level); } },
    { "earthquake_stagger_damage, outdoors", [](int level) { return (int)(dice(1, 4) + (1 * (level / 2))); },
      [](const Rolls &r, int level) { return earthquake_stagger_damage(r, level, 1); } },
    { "earthquake_stagger_damage, indoors", [](int level) { return (int)(dice(1, 4) + (3 * (level / 2))); },
      [](const Rolls &r, int level) { return earthquake_stagger_damage(r, level, 3); } },
    { "firestorm_damage", [](int level) { return dice(level, 10); },
      [](const Rolls &r, int level) { return firestorm_damage(r, level); } },
    { "dispel_good_damage", [](int level) { return dice(level, 8); },
      [](const Rolls &r, int level) { return dispel_good_damage(r, level); } },
    { "dispel_evil_damage", [](int level) { return dice((level + 1), 5); },
      [](const Rolls &r, int level) { return dispel_evil_damage(r, level); } },
    { "flamestrike_damage",
      [](int level) { int num_dice = (level / 5); return (dice(num_dice, 6) * 4); },
      [](const Rolls &r, int level) { return flamestrike_damage(r, level); } },
    { "destroy_undead_damage", [](int level) { return (15 * MIN(level, 56)) + number(-40, 40); },
      [](const Rolls &r, int level) { return destroy_undead_damage(r, level); } },
    { "decaying_flesh_damage", [](int) { return dice(5, 10); },
      [](const Rolls &r, int) { return decaying_flesh_damage(r); } },
    { "decaying_flesh_waves", [](int) { return number(2, 6); },
      [](const Rolls &r, int) { return decaying_flesh_waves(r); } },
    { "armor_armor_class",
      [](int level) {
          double mod;
          if (GET_SPEC(ch, CLASS_CLERIC, SPEC_HOLYMAN))
              mod = 1.25;
          else
              mod = 1;
          return (int)(-1 * (mod * level) - number(0, 10));
      },
      [](const Rolls &r, int level) { return armor_armor_class(r, ch, level); }, true },
    { "blindness_duration", [](int) { return number(4, 12) * WAIT_SEC; },
      [](const Rolls &r, int) { return blindness_duration(r); } },
    { "vitalize_mana transfer",
      [](int) { return MIN(GET_VITALITY(ch), number(33, GET_MAX_MANA(ch))); },
      [](const Rolls &r, int) { return MIN(GET_VITALITY(ch), vitalize_mana_amount(r, ch)); },
      false,
      [](int) { return Range{ vitalize_mana_amount(lowest_rolls, ch), vitalize_mana_amount(highest_rolls, ch) }; } },
    { "rejuvenate_minor_years", [](int level) { return dice(2, level) / 2; },
      [](const Rolls &r, int level) { return rejuvenate_minor_years(r, level); } },
    { "ray_of_enfeeblement_damroll", [](int level) { return level / 10 + number(1, 6); },
      [](const Rolls &r, int level) { return ray_of_enfeeblement_damroll(r, level); } },
    { "age_years", [](int) { return dice(2, 8); }, [](const Rolls &r, int) { return age_years(r); } },
    { "rejuvenate_major_years", [](int) { return dice(2, 4); },
      [](const Rolls &r, int) { return rejuvenate_major_years(r); } },
};

// The casters the rolls run for: their class and spec select a roll's branch.
static const struct { unsigned m_class; int spec; } casters[] = {
    { 0, 0 }, { CLASS_ETHERMANCER, SPEC_TEMPESTMAGUS }, { CLASS_CLERIC, SPEC_ZEALOT },
    { CLASS_CLERIC, SPEC_HOLYMAN }, { CLASS_NECROMANCER, SPEC_REAPER }, { CLASS_CONJURER, SPEC_FIRE },
};

static void caster(int level, unsigned m_class = 0, int spec = 0) {
    you = char_data{};
    you.player.level = level;
    you.player.m_class = m_class;
    you.player.spec = spec;
    you.curr_stats.Cha = 77;
    you.points.max_mana = 40 + level * 10;
    you.points.vitality = 33 + level * 4;
}

static bool contains(const std::string &text, const char *part) {
    return text.find(part) != std::string::npos;
}

// The page `facts` shows the caster, built without drawing from the RNG.
static std::string page(AbilityFacts facts) {
    randomize(5);
    const std::string text = facts(ch);
    const int next = fingerprint();
    randomize(5);
    check(fingerprint() == next, "facts drew from the RNG", text);
    return text;
}

int main() {
    for (const Roll &roll : oracle)
        for (const auto &who : casters)
            for (int level : { 1, 10, 30, 50, 56, 60 }) {
                caster(level, who.m_class, who.spec);
                infuse_life = level;
                Range bounds = { roll.shared(lowest_rolls, level), roll.shared(highest_rolls, level) };
                if (roll.falls)
                    bounds = { bounds.high, bounds.low };
                if (roll.range)
                    bounds = roll.range(level);
                same_rolls(roll.name, level, [&] { return roll.original(level); },
                           [&] { return roll.shared(live_rolls, level); }, bounds);
            }

    // Every page stays within 79 columns and never draws, for each level and caster.
    const AbilityFacts pages[] = { FACTS_LIST };
    std::set<std::string> long_lines;
    for (const auto &who : casters)
        for (int level : { 1, 10, 30, 50, 56, 60 })
            for (AbilityFacts facts : pages) {
                caster(level, who.m_class, who.spec);
                const std::string text = page(facts);
                check(!text.empty() && text.back() == '\n', "page ends its last line", text);
                for (size_t start = 0, end; start < text.size(); start = end + 1) {
                    end = text.find('\n', start);
                    if (end - start > 79 && long_lines.insert(text.substr(start, end - start)).second)
                        fprintf(stderr, "over 79 columns: %s\n", text.substr(start, end - start).c_str());
                }
            }
    check(long_lines.empty(), "lines over 79 columns");

    // ability_facts() maps each spell to its page.
    REGISTRATIONS

    // A few pages, worked out by hand from the handlers at level 50.
    caster(50);
    std::string text = page(magic_missile_facts);
    check(contains(text, "  Missiles: 5 at your level, 50\n"), "magic missile count", text);
    check(contains(text, "  Damage per missile: 5-66, the same for every missile\n"), "magic missile", text);
    check(contains(text, "  Stopped by: any globe of invulnerability or spirit ward\n"), "missile globes", text);

    text = page(chill_touch_facts);
    check(contains(text, "  Cold damage: 71-76 at your level, 50\n"), "chill touch", text);
    check(contains(text, "  If the target fails its save: 142-152\n"), "chill touch save", text);
    check(contains(text, "  If it then survives: it loses up to 38 strength\n"), "chill touch loss", text);
    check(contains(text, "  Weakness lasts: 1-2 game hours (1.25-2.5 minutes)\n"), "chill duration", text);

    text = page(cone_of_cold_facts);
    check(contains(text, "  Cold damage: 68-408 at your level, 50\n"), "cone of cold", text);
    check(contains(text, "  If it survives and fails a save: it loses 5-10 strength for 1.5 seconds\n"),
          "cone of cold loss", text);
    check(contains(text, "  If it is wet: it loses 10-20 strength and is slowed for 2 seconds\n"),
          "cone of cold wet", text);

    text = page(anti_magic_ray_facts);
    check(contains(text, "  Damage: 230-2300 at your level, 50\n"), "anti-magic ray", text);
    check(contains(text, "  If the target saves: 115-1150\n"), "anti-magic ray save", text);
    check(contains(text, "  Cannot be shrugged: 61 in 100\n"), "anti-magic shrug", text);
    check(contains(text, "  If the target survives: dispel magic, its spell save 4 worse\n"),
          "anti-magic dispel", text);

    text = page(prismatic_ray_facts);
    check(contains(text, "  Shimmering ray: 50-450 damage at your level, 50\n"), "shimmering ray", text);
    check(contains(text, "  Red ray: 450-500 fire damage, 225-250 if the target saves\n"), "red ray", text);

    text = page(aid_facts);
    check(contains(text, "  Shortens harmful spells by: 12 game hours, to at least 1\n"), "aid", text);
    check(contains(text, "  Duration: 50-51 game hours (62.5-63.75 minutes)\n"), "aid duration", text);

    // number(1, 100) is below 70 for 69 of its 100 values.
    text = page(ray_of_enfeeblement_facts);
    check(contains(text, "  Takes hold: 69% of the time on a target of your level\n"), "ray chance", text);
    check(contains(text, "  On other targets: 49% to 79%, more often on lower levels\n"), "ray range", text);
    check(contains(text, "  If the target fails its save: it loses some strength and 6-11 damroll\n"),
          "ray damroll", text);

    text = page(earthquake_facts);
    check(contains(text, "  If a target fails an agility save: 51-80 damage at your level, 50\n"), "quake", text);
    check(contains(text, "  It falls unless it is a player who lands a safe fall, avoiding the damage.\n"),
          "quake safe fall", text);
    check(contains(text, "  If it keeps its feet: 26-29 earth damage outdoors\n"), "quake stagger", text);
    check(contains(text, "  On mountains: 51-54\n"), "quake mountains", text);
    check(contains(text, "  Elsewhere indoors, in the underdark or on the earth plane: 76-79\n"),
          "quake indoors", text);
    check(contains(text, "  Only standing targets your area spells can hit take damage; others that\n"
                         "  fail the save fall to their knees.\n"
                         "  Nothing quakes while you fly or swim.\n"), "quake targets", text);

    // dice(100, 9) and its half, each raised a tenth per terrain step.
    text = page(earthen_maul_facts);
    check(contains(text, "  Damage: 110-990 at your level, 50\n"
                         "  If the target saves: 55-495\n"
                         "  Rougher ground raises both while you stand on it, not flying or swimming:\n"
                         "  On mountains or underdark land: 120-1080\n"
                         "  In an inside room, or indoors on ordinary land: 130-1170\n"
                         "  On lava: 140-1260, as fire damage\n"
                         "  Ordinary land: city, field, forest, hills, road, desert, tundra, snowy\n"
                         "  forest or underwater ground. Underdark land: all of the underdark but\n"
                         "  its water, open air and inside rooms.\n"), "earthen maul", text);

    check(contains(page(decaying_flesh_facts),
                   "  Physical damage that ignores armor, skin spells, displacement and other\n"
                   "  damage reduction; wards and sanctuary still apply.\n"), "decaying flesh stage");

    // spell_damage() and vamp() skip amounts below 1, so a low caster's ranges start at 0.
    text = page(destroy_undead_facts);
    check(contains(text, "  Holy damage: 710-790 at your level, 50\n"), "destroy undead", text);
    check(contains(text, "  If the target saves: 355-395\n"), "destroy undead save", text);
    caster(1);
    text = page(destroy_undead_facts);
    check(contains(text, "  Holy damage: 0-55 (none below 1 lands) at your level, 1\n"), "destroy at 1", text);
    check(contains(text, "  If the target saves: 0-27 (none below 1 lands)\n"), "destroy save at 1", text);
    caster(1, CLASS_CLERIC, SPEC_ZEALOT);
    text = page(destroy_undead_facts);
    check(contains(text, "  Holy damage: 0-68 (none below 1 lands) at your level, 1\n"), "zealot at 1", text);
    check(contains(text, "  If the target saves: 0-33 (none below 1 lands)\n"), "zealot save at 1", text);
    // Untrained: (int)(-7 * 0.8) and (int)(12 * 0.8).
    caster(1);
    text = page(restore_spirit_facts);
    check(contains(text, "  Holy damage: 0-9 (none below 1 lands) at your level, 1\n"), "restore at 1", text);
    check(contains(text, "  If the target saves: 0-4 (none below 1 lands)\n"), "restore save at 1", text);
    check(contains(text, "  You heal up to: 0-2 (none below 1 lands) on an unsaved hit\n"), "restore heal", text);
    caster(1, CLASS_NECROMANCER, SPEC_REAPER);
    text = page(enervation_facts);
    check(contains(text, "  Negative damage: 0-12 (none below 1 lands) at your level, 1\n"), "enervate at 1", text);
    check(contains(text, "  If the target saves: 0-6 (none below 1 lands)\n"), "enervate save at 1", text);
    check(contains(text, "  You heal up to: 0-3 (none below 1 lands) on an unsaved hit\n"), "enervate heal", text);
    caster(50, CLASS_NECROMANCER, SPEC_REAPER);
    text = page(enervation_facts);
    check(contains(text, "  Negative damage: 254-294 at your level, 50\n"), "enervation", text);
    check(contains(text, "  If the target saves: 126-146\n"), "enervation save", text);
    check(contains(text, "  You heal up to: 63-73 on an unsaved hit\n"), "enervation heal", text);
    // No range on these pages falls wholly below 1 or shows a negative number.
    for (int level = 1; level <= 60; ++level)
        for (const auto &who : casters)
            for (AbilityFacts facts : { restore_spirit_facts, enervation_facts, destroy_undead_facts }) {
                caster(level, who.m_class, who.spec);
                text = page(facts);
                check(!contains(text, " -") && !contains(text, "--") && !contains(text, " 0 ("),
                      "a range below 1", text);
            }
    caster(50);

    text = page(missile_barrage_facts);
    check(contains(text, "  Missiles: 3-4 at your level, 50\n"), "barrage count", text);
    check(contains(text, "  Damage per missile: 30-330\n"), "barrage damage", text);
    caster(56);
    check(contains(page(missile_barrage_facts), "  Missiles: 4 at your level, 56\n"), "barrage at 56");

    caster(50);
    text = page(dimension_door_facts);
    check(contains(text, "  Range: 67 rooms at your level, 50\n"), "dimension door range", text);
    check(contains(text, "  Your lag: 9 seconds\n"), "dimension door lag", text);

    text = page(teleport_facts);
    check(contains(text, "  On the map: up to 30 rooms away\n"), "teleport", text);
    check(contains(text, "  Elsewhere it takes the target to a random room in the zone.\n"), "teleport zone", text);
    check(contains(page(elemental_aura_facts), "  Fire: Str +50, Dex -20, Agi -10, Con +25\n"), "aura");
    you.points.max_mana = 200;
    check(contains(page(vitalize_mana_facts), "  Movement turned into mana: 33-200, or all of it if you have less\n"),
          "vitalize mana");

    caster(50, CLASS_CLERIC, SPEC_ZEALOT);
    text = page(flamestrike_facts);
    check(contains(text, "  Holy damage, then fire: 25-150 each at your level, 50\n"), "zealot strike", text);
    check(contains(text, "  If the target fails its save: 50-300 each\n"), "zealot strike save", text);
    check(contains(text, "  If it survives, your brand lasts: 5-6 game hours (6.25-7.5 minutes)\n"),
          "zealot brand", text);
    caster(50, CLASS_CLERIC);
    text = page(flamestrike_facts);
    check(contains(text, "  Holy damage, then fire: 20-120 each at your level, 50\n"), "flame strike", text);
    check(!contains(text, "brand"), "brand only for zealots", text);

    caster(50, CLASS_NECROMANCER, SPEC_REAPER);
    text = page(energy_drain_facts);
    check(contains(text, "  Negative damage: 420-660 at casting level 60\n"), "reaper drain", text);
    check(contains(text, "  You drain: 5-30 movement, half if it is already drained\n"), "reaper moves", text);
    check(contains(text, "  If it fails its save and survives: its regeneration drops by 3\n"), "drain regen", text);
    check(contains(text, "  Hit point and movement regeneration loss lasts: 6 seconds\n"
                         "  Not if it is already drained: its loss lasts 0.25 seconds longer instead,\n"
                         "  even if it saves.\n"), "drain time", text);

    // Charisma 77 + 30 / 5; the weaker level's highest roll is the lowest level.
    caster(30);
    infuse_life = 0;
    text = page(conjure_elemental_facts);
    check(contains(text, "  Elemental's level: 25-35 at your level, 30\n"), "elemental level", text);
    check(contains(text, "  Its hit points: 170-358 with your charisma and infuse life\n"), "elemental hp", text);
    check(contains(text, "  Its hitroll and damroll: 8-11\n"), "elemental rolls", text);
    check(!contains(text, "home terrain"), "home terrain only for specialized conjurers", text);
    caster(30, CLASS_CONJURER, SPEC_FIRE);
    infuse_life = 0;
    check(contains(page(conjure_elemental_facts),
                   "  In its home terrain: 245-497 hit points, hitroll and damroll 12-17\n"),
          "elemental home terrain");

    // Charisma 77 + 30 / 5: 450 + 0 + 83 to 700 + 50 + 83.
    caster(30);
    infuse_life = 0;
    text = page(conjure_greater_elemental_facts);
    check(text == "  Elemental's level: 49-53\n"
                  "  Its hit points: 533-833 with your charisma and infuse life\n"
                  "  Its hitroll: 16-17, damroll 12-13\n"
                  "  A specialized conjurer summons one of its own element instead, with\n"
                  "  numbers this page does not show.\n", "greater elemental", text);
    caster(30, CLASS_CONJURER, SPEC_FIRE);
    text = page(conjure_greater_elemental_facts);
    check(text == "  A specialized conjurer summons one of its own element instead, with\n"
                  "  numbers this page does not show.\n", "specialized greater elemental", text);
    // Specialized summoners can't cast either spell; the handlers refuse them.
    caster(30, CLASS_SUMMONER, 1);
    for (AbilityFacts facts : { conjure_elemental_facts, conjure_greater_elemental_facts }) {
        text = page(facts);
        check(text == "  Specialized summoners use the conjure command instead.\n", "summoner", text);
    }

    puts("PASS: batch 1 rolls match the old code, ranges hold, facts never roll");
}
'''


def statics_used(code, names):
    """The names, and every static function of magic.c their bodies call, in file order."""
    defined = {m.group(1): m.start() for m in re.finditer(
        r"^(?:static )?(?:int|bool|std::string) (\w+)\(", code, re.M)}
    seen, todo = set(), list(names)
    while todo:
        name = todo.pop()
        if name in seen:
            continue
        seen.add(name)
        body = function_bodies(code, r"(?m)^(?:static )?(?:int|bool|std::string) " + name + r"\s*\(")[0]
        todo += [called for called in re.findall(r"\b(\w+)\(", body)
                 if called in defined and called not in seen]
    return sorted(seen, key=defined.get)


def check_handlers_use_shared_numbers(code):
    rolling = set(re.findall(r"^static int (\w+)\(const Rolls &rolls", code, re.M))
    for handler, shared in HANDLERS.items():
        body = function_bodies(code, r"(?m)^(?:void|bool) " + handler + r"\s*\(")[0]
        for name in shared.split():
            call = name + ("(live_rolls" if name in rolling else "(")
            assert call in body, (handler, call)


def main():
    text = source("magic.c").read_text()
    code = strip_comments(text)
    check_handlers_use_shared_numbers(code)
    facts = sorted(set(FACTS.values()))
    functions = [extract_function("utility.c", "int dice(int num, int size)"),
                 extract_function("utility.c", "int BOUNDED(int a, int b, int c)"),
                 extract_function("utility.c", "int GET_CLASS(P_char ch, uint m_class)")]
    for name in statics_used(code, facts):
        head = re.search(r"^(?:static )?(?:int|bool|std::string) " + name + r"\(", text, re.M)
        functions.append(extract_function("magic.c", head.group(0)))
    registrations = "".join(f'    check(ability_facts({spell}) == {name}, "{spell}");\n'
                            for spell, name in FACTS.items())
    harness_text = (HARNESS.replace("FACTS_LIST", ", ".join(facts))
                    .replace("    REGISTRATIONS\n", registrations)
                    .replace("EXTRACTED_FUNCTIONS\n", "\n".join(functions) + "\n"))
    # Weak stand-ins for the facts of other batches, so ability_facts() links.
    others = re.findall(r"^std::string (\w+)\(char_data \*ch\);", source("abilities.h").read_text(), re.M)
    stubs_text = "#include <string>\nstruct char_data;\n" + "".join(
        f"__attribute__((weak)) std::string {name}(char_data *) {{ return {{}}; }}\n" for name in others)
    build = ROOT / "bin/tests"
    build.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ability-batch-1-", dir=build) as temporary:
        directory = Path(temporary)
        harness = directory / "batch.cpp"
        harness.write_text(harness_text)
        stubs = directory / "weak_facts.cpp"
        stubs.write_text(stubs_text)
        binary = directory / "batch"
        subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
                        "-ffunction-sections", "-fdata-sections", "-Wl,--gc-sections",
                        "-fsanitize=address,undefined", "-fno-sanitize-recover=undefined",
                        "-Isrc", "-I/usr/include/mysql", "-I/usr/include/libxml2",
                        str(harness), str(stubs), "src/abilities/abilities.c", "src/core/random.c",
                        "-o", str(binary)], cwd=ROOT, check=True)
        subprocess.run([str(binary)], cwd=directory, check=True)


if __name__ == "__main__":
    main()
