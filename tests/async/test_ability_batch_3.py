#!/usr/bin/env python3
"""Spell batch 3 shared numbers: rolls match the old handler code, ranges are exact, facts
never roll.

Builds src/abilities/abilities.c and the real RNG with the batch's shared and facts
functions extracted from magic.c, under sanitizers. The pre-conversion expressions are
kept below as the oracle.
"""
import re
import subprocess
import tempfile
from pathlib import Path

from _paths import ROOT, extract_function, source
from _source_contract import function_bodies, strip_comments

# The shared functions the facts use, by spell; every one is extracted for the harness.
SHARED = """
entangle_bind_chance entangle_bind_roll entangle_duration
vampiric_touch_duration vampiric_touch_hitroll
sanctuary_duration hellfire_duration battletide_damroll battletide_hitroll battletide_duration
mend_soul_healing heal_undead_healing greater_heal_undead_healing
prot_undead_adds_globe prot_undead_skin prot_undead_duration prot_from_undead_duration
create_spring_duration divine_font_duration regeneration_duration endurance_amount
elemental_form_duration elemental_form_armor_duration elemental_form_earth_ac
elemental_form_water_ac elemental_form_water_damroll elemental_form_air_ac
elemental_form_str_max elemental_form_con_max elemental_form_agi elemental_form_dex
command_undead_duration command_undead_level_gap turn_undead_fear_levels mage_flame_duration globe_of_darkness_duration
elemental_shield_duration negative_energy_barrier_duration slow_poison_duration
comprehend_languages_duration
obtenebration_damage obtenebration_blind_chance obtenebration_blind_roll obtenebration_blindness
incendiary_cloud_damage incendiary_cloud_failed_save incendiary_cloud_pc_damage
incendiary_cloud_bonus
disintegrate_damage disintegrate_failed_save shatter_damage shatter_saved
cause_zealot_damage cause_light_damage cause_serious_damage cause_critical_damage
unholy_wind_damage unholy_wind_failed_save purge_living_damage acid_stream_damage
acid_blast_damage acid_blast_failed_save ice_storm_damage ice_storm_pc_damage
faerie_fire_duration faerie_fire_armor faerie_fire_disguise_roll faerie_fog_disguise_roll
blackmantle_duration
pword_kill_max_hits pword_kill_sure_levels pword_kill_damage
infernal_fury_duration freedom_of_movement_roll freedom_of_movement_duration
ghastly_touch_slay_level ghastly_touch_slay_damage ghastly_touch_damage ghastly_touch_pc_damage
ghastly_touch_factor ghastly_touch_paralysis_level
heavens_aid_slay_level heavens_aid_slay_damage heavens_aid_damage heavens_aid_pc_damage
heavens_aid_factor aid_of_the_heavens_lag summon_ghasts_lag
holy_word_slay_level holy_word_slay_damage holy_word_damage holy_word_bane_damage
holy_word_blind_level holy_word_paralysis_level holy_word_zealot_damage holy_word_alignment
unholy_word_alignment unholy_word_factor holy_word_lines
solar_flare_damage solar_flare_boosted solar_flare_boost solar_flare_blindness
solar_flare_blind_roll solar_flare_immolate_roll sunray_blindness
silence_duration feeblemind_stat_loss feeblemind_short_duration feeblemind_long_duration
pword_blind_duration pword_stun_duration dispel_magic_wall_damage dispel_magic_destroy_roll
dispel_magic_fade_roll resurrect_lag
preserve_hours lesser_resurrect_lag waterbreath_duration protection_spell_duration
darkness_duration infravision_duration embalm_hours
divine_fury_duration divine_fury_damroll divine_fury_hitroll
charm_as_druid charm_druid_max_level charm_max_level charm_druid_sure_level charm_max_duration
charm_mindless_duration charm_lag
""".split()

# A new protection and a refreshed one get the same duration.
PROTECTION = ["af.duration = protection_spell_duration(level);",
              "protection_spell_duration(level), false);"]
# Each handler calls its shared functions where the old expressions were.
CALLS = {
    "spell_entangle": ["chance = entangle_bind_chance();", "af.duration = entangle_duration(level);"],
    "spell_vampiric_touch": ["af.duration = vampiric_touch_duration(level);",
                             "af.modifier = vampiric_touch_hitroll(level);"],
    "spell_sanctuary": ["af.duration = sanctuary_duration();"],
    "spell_hellfire": ["af.duration = hellfire_duration();"],
    "spell_battletide": ["af.modifier = battletide_damroll();", "af.modifier = battletide_hitroll();",
                         "af.duration = battletide_duration();"],
    "spell_mend_soul": ["healpoints = mend_soul_healing(live_rolls, ch);"],
    "spell_heal_undead": ["healpoints = heal_undead_healing(live_rolls, ch);"],
    "spell_greater_heal_undead": ["int healpoints = greater_heal_undead_healing();"],
    "spell_prot_undead": ["prot_undead_adds_globe(level)", "af.modifier = prot_undead_skin(live_rolls, level);",
                          "af.duration = prot_undead_duration(ch);"],
    "spell_prot_from_undead": ["af1->duration = prot_from_undead_duration(ch);",
                               "af.duration = prot_from_undead_duration(ch);"],
    "spell_create_spring": ["set_obj_affected(spring, create_spring_duration(), TAG_OBJ_DECAY, 0);"],
    "spell_divine_font": ["set_obj_affected(font, divine_font_duration(), TAG_OBJ_DECAY, 0);"],
    "spell_regeneration": ["skl_lvl = regeneration_duration(level);"],
    "spell_endurance": ["skl_lvl = endurance_amount(level);"],
    "spell_elemental_form": ["af.duration = elemental_form_armor_duration();", "elemental_form_earth_ac()",
                             "elemental_form_water_ac()", "elemental_form_water_damroll()",
                             "elemental_form_air_ac()", "af.duration = elemental_form_duration();",
                             "elemental_form_str_max(victim)", "elemental_form_con_max(victim)",
                             "elemental_form_agi(victim)", "elemental_form_dex(victim)"],
    "spell_command_undead": ["(GET_LEVEL(ch) - command_undead_level_gap()) > GET_LEVEL(victim)",
                             "setup_pet(victim, ch, command_undead_duration(level), 0);"],
    "spell_turn_undead": ["else if (diff <= turn_undead_fear_levels())"],
    "spell_holy_light": ["af.duration = mage_flame_duration(level);"],
    "spell_mage_flame": ["af.duration = mage_flame_duration(level);"],
    "spell_globe_of_darkness": ["af.duration = globe_of_darkness_duration(level);"],
    "spell_fireshield": ["af.duration = elemental_shield_duration();"],
    "spell_coldshield": ["af.duration = elemental_shield_duration();"],
    "spell_lightning_shield": ["af.duration = elemental_shield_duration();"],
    "spell_negative_energy_barrier": ["af.duration = negative_energy_barrier_duration();"],
    "spell_slow_poison": ["af.duration = slow_poison_duration(level);"],
    "spell_comprehend_languages": ["af.duration = comprehend_languages_duration(level);",
                                   "af1->duration = comprehend_languages_duration(level);"],
    "spell_single_obtenebration": ["dam = obtenebration_damage(live_rolls, level);",
                                   "obtenebration_blind_roll(live_rolls) < obtenebration_blind_chance()",
                                   "blind(ch, victim, obtenebration_blindness(live_rolls));"],
    "spell_single_incendiary_cloud": ["dam = incendiary_cloud_damage(live_rolls, level);",
                                      "dam = incendiary_cloud_failed_save(dam);",
                                      "dam = incendiary_cloud_pc_damage(dam);",
                                      "dam = incendiary_cloud_bonus(ch, dam);"],
    "spell_disintegrate": ["dam = disintegrate_damage(live_rolls, level);", "dam = disintegrate_failed_save(dam);"],
    "spell_shatter": ["dam = shatter_damage(live_rolls, level);", "dam = shatter_saved(dam);"],
    "spell_cause_light": ["dam = cause_light_damage(live_rolls);", "dam = cause_zealot_damage(ch, dam);"],
    "spell_cause_serious": ["dam = cause_serious_damage(live_rolls);", "dam = cause_zealot_damage(ch, dam);"],
    "spell_cause_critical": ["dam = cause_critical_damage(live_rolls);", "dam = cause_zealot_damage(ch, dam);"],
    "spell_unholy_wind": ["dam = unholy_wind_damage(live_rolls, level);", "dam = unholy_wind_failed_save(dam);"],
    "spell_purge_living": ["dam = purge_living_damage(live_rolls, level);"],
    "spell_acid_stream": ["dam = acid_stream_damage(live_rolls, level);"],
    "spell_acid_blast": ["int dam = acid_blast_damage(live_rolls, level);", "dam = acid_blast_failed_save(dam);"],
    "spell_single_icestorm": ["int dam = ice_storm_damage(live_rolls, level);", "dam = ice_storm_pc_damage(dam);"],
    "spell_faerie_fire": ["!faerie_fire_disguise_roll(live_rolls) && IS_DISGUISE(victim)",
                          "af.duration = faerie_fire_duration();", "af.modifier = faerie_fire_armor();"],
    "spell_faerie_fog": ["if (!faerie_fog_disguise_roll(live_rolls))"],
    "spell_blackmantle": ["af.duration = blackmantle_duration(level);"],
    "spell_pword_kill": ["GET_HIT(victim) < pword_kill_max_hits()",
                         "level > GET_LEVEL(victim) + pword_kill_sure_levels()",
                         "dam = pword_kill_damage(live_rolls, level);"],
    "spell_infernal_fury": ["af.duration = infernal_fury_duration();"],
    "spell_freedom_of_movement": ["af.duration = freedom_of_movement_duration(live_rolls, level);"],
    "spell_ghastly_touch": ["GET_LEVEL(victim) < ghastly_touch_slay_level(level)", "ghastly_touch_slay_damage()",
                            "int dam = ghastly_touch_damage(live_rolls, level);",
                            "dam = ghastly_touch_pc_damage(dam);", "dam = ghastly_touch_factor(dam);",
                            "GET_LEVEL(victim) < ghastly_touch_paralysis_level(level)"],
    "spell_heavens_aid": ["GET_LEVEL(victim) < heavens_aid_slay_level(level)", "heavens_aid_slay_damage()",
                          "dam = heavens_aid_damage(live_rolls, level);", "dam = heavens_aid_pc_damage(dam);",
                          "dam = heavens_aid_factor(dam);"],
    "spell_aid_of_the_heavens": ["CharWait(ch, aid_of_the_heavens_lag());"],
    "spell_summon_ghasts": ["CharWait(ch, summon_ghasts_lag());"],
    "spell_unholy_word": ["GET_ALIGNMENT(ch) > unholy_word_alignment()"],
    "spell_voice_of_creation": ["GET_ALIGNMENT(ch) < holy_word_alignment()"],
    "spell_holy_word": ["GET_ALIGNMENT(ch) < holy_word_alignment()"],
    "spell_solar_flare": ["dam = solar_flare_damage(live_rolls, level);",
                          "if (solar_flare_boosted(ch) && type == SPELL_TYPE_SPELL && !obj)",
                          "dam = solar_flare_boost(dam);",
                          "if (!solar_flare_blind_roll(live_rolls) && !NewSaves(victim, SAVING_SPELL, mod))",
                          "blind(ch, victim, solar_flare_blindness(live_rolls));",
                          "if (!solar_flare_immolate_roll(live_rolls))"],
    "spell_sunray": ["blind(ch, victim, sunray_blindness(live_rolls));"],
    "spell_silence": ["af.duration = silence_duration(percent);"],
    "spell_feeblemind": ["intmod = feeblemind_stat_loss(live_rolls, GET_C_INT(victim), level);",
                         "wismod = feeblemind_stat_loss(live_rolls, GET_C_WIS(victim), level);",
                         "af.duration = feeblemind_short_duration();", "af.duration = feeblemind_long_duration();"],
    "spell_pword_blind": ["blind(ch, victim, pword_blind_duration(level, GET_LEVEL(victim)));"],
    "spell_pword_stun": ["Stun(victim, ch, pword_stun_duration(live_rolls, percent), FALSE);"],
    "spell_dispel_magic": ["dispel_magic_wall_damage(live_rolls, level)",
                           "if (!dispel_magic_destroy_roll(live_rolls) && !IS_TRUSTED(ch))",
                           "else if ((dispel_magic_fade_roll(live_rolls) < level) || IS_TRUSTED(ch))"],
    "spell_resurrect": ["CharWait(ch, resurrect_lag(ch, level));"],
    "spell_preserve": ["timePres = preserve_hours(level);"],
    "spell_lesser_resurrect": ["if (int lag = lesser_resurrect_lag(ch, level))"],
    "spell_waterbreath": ["af.duration = waterbreath_duration(level);", "af1->duration = waterbreath_duration(level);"],
    "spell_protection_from_fire": PROTECTION,
    "spell_protection_from_cold": PROTECTION,
    "spell_protection_from_living": ["af.duration = protection_spell_duration(level);",
                                     "af1->duration = protection_spell_duration(level);"],
    "spell_protection_from_animals": ["af.duration = protection_spell_duration(level);",
                                      "af1->duration = protection_spell_duration(level);"],
    "spell_protection_from_gas": PROTECTION,
    "spell_protection_from_acid": PROTECTION,
    "spell_protection_from_lightning": PROTECTION,
    "spell_darkness": ["add_event(darkness_dissipate_event, darkness_duration(level),"],
    "spell_infravision": ["af.duration = infravision_duration(level);", "af1->duration = infravision_duration(level);"],
    "spell_embalm": ["embalm_time = embalm_hours(level);"],
    "spell_divine_fury": ["af.duration = divine_fury_duration();", "af.modifier = divine_fury_damroll(level);",
                          "af.modifier = divine_fury_hitroll(level);"],
    "charm_generic": ["CharWait(ch, charm_lag());", "if (charm_as_druid(ch))",
                      "GET_LEVEL(victim) > charm_druid_max_level(ch)",
                      "else if (charm_max_level(level) < (int)GET_LEVEL(victim))",
                      "if (charm_as_druid(ch) && ((GET_LEVEL(victim) < charm_druid_sure_level(ch)))",
                      "num = MIN(charm_max_duration(ch), 200 / STAT_INDEX(GET_C_INT(victim)));",
                      "num = charm_mindless_duration();"],
    "spell_charm_person": ["charm_generic(level, ch, victim);"],
    "spell_charm_animal": ["charm_generic(level, ch, victim);"],
    "spell_animal_friendship": ["charm_generic(level, ch, victim);"],
}
# The batch's spells, each with a facts function in ability_facts().
BATCH = """
SOLAR_FLARE LESSER_SANCTUARY BATTLETIDE OBTENEBRATION BMANTLE REGENERATION ENDURANCE SHATTER
INFRAVISION MAGE_FLAME HOLY_LIGHT GLOBE_OF_DARKNESS WATERBREATH CAUSE_LIGHT UNHOLY_WIND PURGE_LIVING
CAUSE_SERIOUS CAUSE_CRITICAL DIVINE_FURY NEG_ENERGY_BARRIER LESSER_RESURRECT RESURRECT HANDOFDEATH
PRESERVE MASS_PRESERVE DISPEL_MAGIC SANCTUARY HELLFIRE DARKNESS PROTECT_FROM_FIRE PROTECT_FROM_COLD
PROTECT_FROM_LIVING PROTECT_FROM_ANIMAL PROTECT_FROM_GAS PROTECT_FROM_ACID PROTECT_FROM_LIGHTNING
FIRESHIELD INCENDIARY_CLOUD ICE_STORM DISINTEGRATE ACID_STREAM ACID_BLAST FAERIE_FIRE PWORD_KILL
PWORD_BLIND PWORD_STUN UNHOLY_WORD VOICE_OF_CREATION HOLY_WORD SUNRAY FEEBLEMIND SILENCE TURN_UNDEAD
COMMAND_UNDEAD SELF_COMPREHENSION COMPREHEND_LANGUAGES SLOW_POISON COLDSHIELD LIGHTNINGSHIELD EMBALM
MASS_EMBALM ELEMENTAL_FORM VAMPIRIC_TOUCH PROT_UNDEAD PROTECT_SOUL PROT_FROM_UNDEAD COMMAND_HORDE
HEAL_UNDEAD MEND_SOUL GREATER_HEAL_UNDEAD ENTANGLE CREATE_SPRING SUMMON_GHASTS AID_OF_THE_HEAVENS
GHASTLY_TOUCH INFERNAL_FURY FREEDOM_OF_MOVEMENT DIVINE_FONT FAERIE_FOG CHARM_PERSON CHARM_ANIMAL
ANIMAL_FRIENDSHIP
""".split()
WORDS = {"single_unholy_word": "unholy_word_factor(dam)", "single_voice_of_creation": None,
         "single_holy_word": None}

HARNESS = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "magic/spells.h"
#include "abilities/abilities.h"
#include <cassert>
#include <climits>
#include <cstring>
#include <functional>
#include <map>
#include <string>
#include <tuple>

void randomize(uint64_t seed);

// Unset properties return their default, as with an empty properties file.
static std::map<std::string, float> properties;
float get_property(const char *key, double default_value)
{
    auto found = properties.find(key);
    return found == properties.end() ? (float)default_value : found->second;
}

static int devotion;
int GET_CHAR_SKILL_P(P_char, int) { return devotion; }

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

// A shared roll at `level` against its old expression, bounded by the lowest and highest rolls.
static void check(int level, const std::function<int()> &original,
                  const std::function<int(const Rolls &, int)> &shared) {
    same_rolls(original, [&] { return shared(live_rolls, level); },
               { shared(lowest_rolls, level), shared(highest_rolls, level) });
}

// Every value from low to high must turn up over enough seeds.
static void reaches(const std::function<int()> &shared, Range bounds) {
    int low = INT_MAX, high = INT_MIN;
    for (uint64_t seed = 1; seed <= 2000; ++seed) {
        randomize(seed);
        const int value = shared();
        low = std::min(low, value);
        high = std::max(high, value);
    }
    assert(low == bounds.low && high == bounds.high);
}

static bool contains(const std::string &text, const std::string &part) {
    return text.find(part) != std::string::npos;
}

static const int levels[] = { 1, 10, 30, 50, 56, 60 };

static const int batch[] = { BATCH };

// Every page fits the screen and never rolls.
static void pages_fit(P_char ch) {
    for (int spell : batch) {
        AbilityFacts facts = ability_facts(spell);
        assert(facts);
        randomize(9);
        const int untouched = fingerprint();
        randomize(9);
        const std::string text = facts(ch);
        assert(fingerprint() == untouched);
        assert(!text.empty() && text.back() == '\n');
        size_t start = 0;
        for (size_t end; (end = text.find('\n', start)) != std::string::npos; start = end + 1)
            assert(end - start <= 79 && text.compare(start, 2, "  ") == 0);
        for (const char *never : { "below level -", "below level 0", "below level 1:", "below level 1\n" })
            assert(!contains(text, never));
    }
}

int main() {
    // Shared rolls draw exactly as the old expressions did.
    for (int level : levels) {
        check(level, [=] { int dam = 100 + level * 6 + number(1, 40);
                           dam = dam * get_property("spell.area.damage.factor.obtenebration", 1.000);
                           return dam; }, obtenebration_damage);
        check(level, [] { return number(4, 12) * WAIT_SEC; },
              [](const Rolls &r, int) { return obtenebration_blindness(r); });
        check(level, [=] { return dice(3 * level, 7) / 2; }, incendiary_cloud_damage);
        check(level, [=] { return dice(level, 13); }, disintegrate_damage);
        check(level, [=] { return (10 * level) + dice(level, 3); }, shatter_damage);
        check(level, [] { return 4 * dice(1, 8); }, [](const Rolls &r, int) { return cause_light_damage(r); });
        check(level, [] { return 4 * dice(2, 8); }, [](const Rolls &r, int) { return cause_serious_damage(r); });
        check(level, [] { return dice(12, 8) + 40; }, [](const Rolls &r, int) { return cause_critical_damage(r); });
        check(level, [=] { return (dice(1, 6) + 5 * 4 + level); }, unholy_wind_damage);
        check(level, [=] { int temp = MIN(35, (level + 1)); return dice(temp, 10); }, purge_living_damage);
        check(level, [=] { return dice(MIN(51, level - 4) + 3, 14); }, acid_stream_damage);
        check(level, [=] { return dice(MIN(level, 21), 10) + level / 2; }, acid_blast_damage);
        check(level, [=] { int num_dice = MIN(level, 36);
                           int dam = dice(num_dice, 8);
                           dam = dam * get_property("spell.area.damage.factor.iceStorm", 1.000);
                           return dam; }, ice_storm_damage);
        check(level, [=] { return ((dice(3, 6) + level) * 4); }, pword_kill_damage);
        check(level, [=] { return (int)number(level * 5, level * 7); }, ghastly_touch_damage);
        check(level, [=] { return (int)number(level * 5, level * 7); }, heavens_aid_damage);
        check(level, [=] { return (6 * level) + number(1, 25); }, solar_flare_damage);
        check(level, [] { return number(4, 12) * WAIT_SEC; },
              [](const Rolls &r, int) { return solar_flare_blindness(r); });
        check(level, [] { return number(4, 12) * WAIT_SEC; },
              [](const Rolls &r, int) { return sunray_blindness(r); });
        check(level, [=] { return number(level / 4, level); }, dispel_magic_wall_damage);
        check(level, [] { return number(25, 59); },
              [](const Rolls &r, int) { return dispel_magic_fade_roll(r); });
        check(level, [=] { return (level / 4) + number(1, 4); }, prot_undead_skin);
        for (sh_int stat : { 0, 37, 100 })
            check(level, [=] { return (int)((stat / 3) + (level / 5) + number(-15, 5)); },
                  [=](const Rolls &r, int l) { return feeblemind_stat_loss(r, stat, l); });
        char_data healer_data{};
        const P_char healer = &healer_data;
        healer->player.level = level;
        check(level, [=] { return number(150, (GET_LEVEL(healer) * 5)); },
              [=](const Rolls &r, int) { return mend_soul_healing(r, healer); });
        check(level, [=] { return number(150, (GET_LEVEL(healer) * 5)); },
              [=](const Rolls &r, int) { return heal_undead_healing(r, healer); });
    }
    // Freedom of movement rolls once and respects the three-hour floor at low levels.
    const std::map<int, Range> freedom = { { 1, { 3, 3 } }, { 9, { 3, 3 } }, { 10, { 3, 3 } },
                                           { 12, { 3, 4 } }, { 16, { 3, 5 } }, { 18, { 3, 6 } },
                                           { 50, { 14, 17 } }, { 56, { 16, 19 } } };
    for (const auto &[level, bounds] : freedom) {
        same_rolls([=] { return std::max(3, (level / 2 + number(-4, 0)) * 7 / 10); },
                   [=] { return freedom_of_movement_duration(live_rolls, level); }, bounds);
        reaches([=] { return freedom_of_movement_duration(live_rolls, level); }, bounds);
        char_data reader{};
        reader.player.level = level;
        const std::string at_level = " at your level, " + std::to_string(level);
        assert(freedom_of_movement_facts(&reader) ==
               (bounds.low == bounds.high
                        ? fact("Duration", game_hours(bounds.low) + at_level)
                        : fact("Shortest duration", game_hours(bounds.low) + at_level) +
                                  fact("Longest duration", game_hours(bounds.high))));
    }
    // The tiered durations follow the handlers' branches.
    for (int percent = 0; percent <= 100; ++percent) {
        check(percent, [=] { if (percent > 90) return (number(3, 4) * PULSE_VIOLENCE);
                             else if (percent > 70) return (number(2, 3) * PULSE_VIOLENCE);
                             else if (percent > 50) return (number(1, 2) * PULSE_VIOLENCE);
                             return PULSE_VIOLENCE; }, pword_stun_duration);
        if (percent >= 10) // silence gives up below 10
            assert(silence_duration(percent) == (percent > 90 ? 10 * WAIT_SEC : percent > 70 ? 8 * WAIT_SEC :
                                                 percent > 40 ? 5 * WAIT_SEC : 3 * WAIT_SEC));
    }
    // The lags moved with their conditions.
    char_data ch{};
    const P_char caster = &ch;
    for (uint cls : { 0u, (uint)CLASS_CLERIC, (uint)CLASS_SHAMAN })
        for (int level : { 50, 51, 52, 55, 56, 60 })
            for (int skill : { 0, 20, 21, 80 }) {
                ch.player.m_class = cls;
                ch.player.level = level;
                devotion = skill;
                assert(resurrect_lag(caster, level) ==
                       ((!GET_CLASS(caster, CLASS_CLERIC) || level < 56) ? 25 * WAIT_SEC : 10 * WAIT_SEC));
                const bool lags = (GET_CHAR_SKILL(caster, SKILL_DEVOTION) <= 20 && !IS_TRUSTED(caster)) ||
                                  (GET_CLASS(caster, CLASS_SHAMAN) && level < 52);
                assert(lesser_resurrect_lag(caster, level) == (lags ? 100 : 0));
            }

    // Pages at level 50 with no class.
    ch = char_data{};
    ch.player.level = 50;
    ch.base_stats.Str = 80;
    ch.base_stats.Con = 70;
    ch.base_stats.Agi = 60;
    ch.base_stats.Dex = 50;
    devotion = 0;
    const std::map<int, std::string> pages = {
        { SPELL_OBTENEBRATION, "  Sound damage: 401-440 to each target at your level, 50\n"
                               "  Blindness: 19 in 100, for 4 seconds to 12 seconds\n"
                               "  Globes and spirit wards: do not stop it\n" },
        { SPELL_INCENDIARY_CLOUD, "  Fire damage: 75-525 to each target at your level, 50\n"
                                  "  If the target fails its save: 112-787\n"
                                  "  Against a player: 37-262, or 56-393 if it fails its save\n" },
        { SPELL_SUNRAY, "  Blindness: 4 seconds to 12 seconds if the target fails a second save\n"
                        "  Less damage against a blinded target or indoors, more if it fails its save.\n"
                        "  Globes and spirit wards: do not stop it\n" },
        { SPELL_HOLY_WORD, "  Required alignment: 900 or higher\n"
                           "  It harms only targets with alignment 0 or lower, and enemy players.\n"
                           "  Holy damage: 170 to each target at your level, 50\n"
                           "  Against a githyanki: 255\n"
                           "  Targets below level 16: 1000 damage instead\n"
                           "  Survivors below level 27: blinded\n"
                           "  Survivors below level 22: also paralyzed\n"
                           "  Globes and spirit wards: do not stop it\n" },
        { SPELL_UNHOLY_WORD, "  Required alignment: -900 or lower\n"
                             "  It harms only targets with alignment 0 or higher, and enemy players.\n"
                             "  Holy damage: 170 to each target at your level, 50\n"
                             "  Against a githzerai: 255\n" },
        { SPELL_CAUSE_CRITICAL, "  Damage: 52-136\n  Globes and spirit wards: do not stop it\n" },
        { SPELL_SHATTER, "  Sound damage: 550-650 at your level, 50\n  If the target saves: 366-433\n" },
        { SPELL_ACID_BLAST, "  Acid damage: 46-235 at your level, 50\n  If the target fails its save: 57-293\n"
                            "  Any globe or spirit ward: stops it\n" },
        { SPELL_ICE_STORM, "  Globe of invulnerability: stops it; minor globes and spirit wards do not\n" },
        { SPELL_SOLAR_FLARE, "  Fire damage: 301-325 at your level, 50\n"
                             "  Blindness if it survives: 1 in 2, 4 seconds to 12 seconds\n"
                             "    if it fails its save\n"
                             "  Immolate if it survives: 1 in 2 to also cast it on the target\n" },
        { SPELL_PWORD_KILL, "  Slays a target with under 1500 hit points that fails its save,\n"
                            "  unless it is a greater race or elite.\n"
                            "  Chance to slay: 1% plus 1% per level the target is below you\n"
                            "  Certain to slay: more than 15 levels below you\n"
                            "  Damage otherwise: 212-272 at your level, 50\n" },
        { SPELL_GHASTLY_TOUCH, "  Negative damage: 250-350 at your level, 50\n  Against a player: 125-175\n"
                               "  Targets below level 10: 10000 damage instead\n"
                               "  Paralysis: survivors below level 25\n" },
        { SPELL_SUMMON_GHASTS, "  Your lag: 4 seconds\n  Negative damage: 250-350 at your level, 50\n" },
        { SPELL_AID_OF_THE_HEAVENS, "  Holy damage: 250-350 to each target at your level, 50\n"
                                    "  Against a player: 125-175\n"
                                    "  Targets below level 10: 10000 damage instead\n"
                                    "  Your lag: 4 seconds\n"
                                    "  It does not harm good races or angels.\n" },
        { SPELL_ENTANGLE, "  Paralysis if the target fails its save: 20 seconds at your level, 50\n"
                          "  In a forest, if it fails its save: 4 in 100 to bind it until freed instead\n" },
        { SPELL_SANCTUARY, "  Duration: 15-16 game hours (18.75-20 minutes)\n" },
        { SPELL_BATTLETIDE, "  Damroll: +10\n  Hitroll: +10\n  Duration: 10-11 game hours (12.5-13.75 minutes)\n" },
        { SPELL_VAMPIRIC_TOUCH, "  Hitroll: +9 at your level, 50\n  Duration: 10-11 game hours" },
        { SPELL_PROT_UNDEAD, "  Stone skin: lasts 13-16 hits at your level, 50\n"
                             "  Duration: 10-11 game hours (12.5-13.75 minutes)\n"
                             "  Globe of invulnerability: also cast, unless the target has one\n" },
        { SPELL_COMMAND_HORDE, "  Good-aligned casters cannot use it.\n"
                               "  Only an unowned animated undead more than 10 levels below you obeys,\n"
                               "  and only if it fails its save.\n"
                               "  Control: 12-13 game hours (15-16.25 minutes) at your level, 50\n"
                               "  Permanent with unholy alliance or a held globe of shadows.\n" },
        { SPELL_FREEDOM_OF_MOVEMENT, "  Shortest duration: 14-15 game hours (17.5-18.75 minutes) at your level, 50\n"
                                     "  Longest duration: 17-18 game hours (21.25-22.5 minutes)\n" },
        { SPELL_SILENCE, "  Duration: 3 seconds to 10 seconds\n" },
        { SPELL_PWORD_STUN, "  Stun: 4 seconds to 16 seconds\n" },
        { SPELL_PWORD_BLIND, "  Blindness: 1 second per level the target is below you, at least 4 seconds\n" },
        { SPELL_FEEBLEMIND, "  Intelligence and wisdom loss at your level, 50:\n"
                            "    a third of the target's, plus -5 to 15\n  Duration: 20 seconds\n"
                            "  On a wide success: 1-2 game hours (1.25-2.5 minutes)\n" },
        { SPELL_DISPEL_MAGIC, "  Damage to a conjured wall: 12-50 at your level, 50\n"
                              "  A magic item: 1 in 5 to be destroyed\n"
                              "  Otherwise its magic fades: 25 in 35 chance at your level, 50\n" },
        { SPELL_DARKNESS, "  Duration: 10 minutes 25 seconds at your level, 50\n"
                          "  In a magically lit room it only removes the light.\n" },
        { SPELL_CREATE_SPRING, "  The spring lasts: 2 minutes 30 seconds\n" },
        { SPELL_DIVINE_FONT, "  The font lasts: 2 minutes 30 seconds\n" },
        { SPELL_ELEMENTAL_FORM, "  Duration: 6-7 game hours (7.5-8.75 minutes)\n  Maximum strength: +16\n"
                                "  Maximum constitution: +35\n  Agility: -30\n  Dexterity: -25\n" },
        { SPELL_MEND_SOUL, "  Healing: 150-250 at your level, 50\n" },
        { SPELL_GREATER_HEAL_UNDEAD, "  Healing: 300\n" },
        { SPELL_ENDURANCE, "  Movement regeneration: +11 at your level, 50\n"
                           "  Duration: 11-12 game hours (13.75-15 minutes)\n" },
        { SPELL_LESSER_RESURRECT, "  Your lag: 25 seconds\n" },
        { SPELL_HANDOFDEATH, "  Your lag: 25 seconds\n" },
        { SPELL_PRESERVE, "  Decay delayed: 25 game hours (31 minutes 15 seconds) at your level, 50\n" },
        { SPELL_MASS_EMBALM, "  Decay delayed: 100 game hours (125 minutes) at your level, 50\n" },
        { SPELL_PROTECT_FROM_ANIMAL, "  Duration: 50-51 game hours (62.5-63.75 minutes) at your level, 50\n" },
        { SPELL_TURN_UNDEAD, "  Undead and angels up to 30 levels below you: must save or flee\n"
                             "  Further below: a chance to be destroyed, otherwise they flee\n"
                             "  An undead or angel at or above your level (not a player's pet) ends it.\n" },
        { SPELL_DIVINE_FURY, "  Damroll: +10 at your level, 50\n  Hitroll: +10\n" },
        { SPELL_FAERIE_FIRE, "  Target's armor class: +20\n  Duration: 5-6 game hours (6.25-7.5 minutes)\n"
                             "  A visible, disguised target: 1 in 2 to lose its disguise\n" },
        { SPELL_FAERIE_FOG, "  Reveals invisible and hidden creatures in the room that fail their save.\n"
                            "  A visible, disguised creature: 1 in 2 to lose its disguise\n" },
        { SPELL_CHARM_PERSON, "  Highest target level: 33 at your level, 50\n"
                              "  Duration: up to 121-122 game hours (151.25-152.5 minutes)\n"
                              "  The more intelligent the target, the shorter it lasts.\n"
                              "  A target without intelligence: 4-5 game hours (5-6.25 minutes)\n"
                              "  Permanent with unholy alliance or a held globe of shadows.\n"
                              "  Your lag: 4 seconds\n" },
    };
    for (const auto &[spell, lines] : pages)
        assert(contains(ability_facts(spell)(&ch), lines));
    pages_fit(&ch);

    // A "below level" line shows only when some target, at least level 1, can meet it.
    char_data low{};
    low.player.level = 3;
    const std::string after = "  Globes and spirit wards: do not stop it\n"
                              "  Spell damage modifiers and the target's defenses apply after.\n";
    assert(ghastly_touch_facts(&low) == "  Negative damage: 15-21 at your level, 3\n"
                                        "  Against a player: 7-10\n"
                                        "  It does not affect undead.\n" + after);
    assert(aid_of_the_heavens_facts(&low) == "  Holy damage: 15-21 to each target at your level, 3\n"
                                             "  Against a player: 7-10\n"
                                             "  Your lag: 4 seconds\n"
                                             "  It does not harm good races or angels.\n" + after);
    assert(holy_word_facts(&low) == "  Required alignment: 900 or higher\n"
                                    "  It harms only targets with alignment 0 or lower, and enemy players.\n"
                                    "  Holy damage: 29 to each target at your level, 3\n"
                                    "  Against a githyanki: 43\n"
                                    "  Survivors below level 3: blinded\n" + after);
    // Each line first shows where its threshold reaches 2. Only holy word's survivors, at or
    // above its slay level, can be paralyzed, so its paralysis needs a threshold above that.
    const std::tuple<AbilityFacts, int, const char *, const char *> thresholds[] = {
        { ghastly_touch_facts, 3, "Paralysis", nullptr },
        { ghastly_touch_facts, 4, "Paralysis", "  Paralysis: survivors below level 2\n" },
        { ghastly_touch_facts, 9, "Targets below", nullptr },
        { ghastly_touch_facts, 10, "Targets below", "  Targets below level 2: 10000 damage instead\n" },
        { aid_of_the_heavens_facts, 9, "Targets below", nullptr },
        { aid_of_the_heavens_facts, 10, "Targets below", "  Targets below level 2: 10000 damage instead\n" },
        { holy_word_facts, 5, "Targets below", nullptr },
        { holy_word_facts, 6, "Targets below", "  Targets below level 2: 1000 damage instead\n" },
        { holy_word_facts, 19, "paralyzed", nullptr },
        { holy_word_facts, 20, "paralyzed", "  Survivors below level 7: also paralyzed\n" },
        { holy_word_facts, 21, "paralyzed", nullptr },
        { holy_word_facts, 22, "paralyzed", "  Survivors below level 8: also paralyzed\n" },
    };
    for (const auto &[facts, level, marker, line] : thresholds) {
        low.player.level = level;
        const std::string text = facts(&low);
        assert(line ? contains(text, line) : !contains(text, marker));
    }

    // A zealot, a fire conjurer, a wizard and a devoted cleric see their own numbers.
    ch.player.m_class = CLASS_CLERIC;
    ch.player.spec = SPEC_ZEALOT;
    assert(cause_light_facts(&ch) == "  Damage: 5-40\n"
                                     "  Globes and spirit wards: do not stop it\n"
                                     "  Spell damage modifiers and the target's defenses apply after.\n");
    assert(contains(holy_word_facts(&ch), "  Holy damage: 212 to each target at your level, 50\n"
                                          "  Against a githyanki: 318\n"));
    assert(contains(voice_of_creation_facts(&ch), "  Holy damage: 170 to each target"));
    ch.player.spec = 0;
    devotion = 21;
    assert(contains(lesser_resurrect_facts(&ch), "  Your lag: none\n"));
    ch.player.level = 56;
    assert(contains(resurrect_facts(&ch), "  Your lag: 10 seconds\n"));
    ch.player.level = 50;
    ch.player.m_class = CLASS_CONJURER;
    ch.player.spec = SPEC_FIRE;
    assert(contains(solar_flare_facts(&ch), "  Fire damage: 331-357 at your level, 50\n"));
    ch.specials.act = ACT_ISNPC;
    assert(contains(solar_flare_facts(&ch), "  Fire damage: 301-325 at your level, 50\n"));
    ch.specials.act = 0;
    ch.player.m_class = CLASS_SORCERER;
    ch.player.spec = SPEC_WIZARD;
    assert(contains(incendiary_cloud_facts(&ch), "  Fire damage: 105-735 to each target"));
    // The configured area factors and player damage reach the page.
    properties["spell.area.damage.factor.incendiaryCloud"] = 0.7f;
    properties["spell.area.damage.to.pc"] = 1.15f;
    properties["spell.area.damage.factor.unholyWord"] = 2.0f;
    assert(contains(incendiary_cloud_facts(&ch), "  Fire damage: 72-513 to each target"));
    assert(contains(ice_storm_facts(&ch), "  Cold damage: 36-288 to each target at your level, 50\n"
                                          "  Against a player: 41-331\n"));
    assert(contains(unholy_word_facts(&ch), "  Holy damage: 340 to each target"));
    ch = char_data{};
    ch.player.level = 10;
    assert(entangle_facts(&ch) ==
           "  In a forest, if it fails its save: 4 in 100 to bind it until freed instead\n");
    // A druid charms by its own level rules; a druid by second class too.
    ch.player.level = 50;
    ch.player.m_class = CLASS_DRUID;
    const std::string druid = "  Highest target level: 40 at your level, 50\n"
                              "  Natural creatures below level 25: charmed without a save\n"
                              "  Duration: up to 121-122 game hours";
    assert(contains(charm_facts(&ch), druid));
    ch.player.level = 26;
    assert(!contains(charm_facts(&ch), "Natural creatures"));
    ch.player.level = 27;
    assert(contains(charm_facts(&ch), "  Natural creatures below level 2: charmed without a save\n"));
    ch.player.level = 50;
    ch.player.m_class = CLASS_RANGER;
    ch.player.secondary_class = CLASS_DRUID;
    assert(contains(charm_facts(&ch), druid));
    ch.player.secondary_class = 0;
    assert(contains(charm_facts(&ch), "  Highest target level: 33 at your level, 50\n  Duration:"));

    // Every page fits and never rolls at any level, class and property set.
    for (int level = 1; level <= 62; ++level)
        for (uint cls : { 0u, (uint)CLASS_CLERIC, (uint)CLASS_SORCERER, (uint)CLASS_CONJURER,
                          (uint)CLASS_DRUID })
            for (int spec : { 0, (int)SPEC_ZEALOT, (int)SPEC_WIZARD, (int)SPEC_FIRE }) {
                ch.player.level = level;
                ch.player.m_class = cls;
                ch.player.spec = spec;
                pages_fit(&ch);
            }
    puts("PASS: batch 3 shared rolls match the old code, ranges are exact, facts never roll");
}
'''


def definition(magic, name):
    match = re.search(r"^(?:static )?[\w:]+ " + name + r"\(", magic, re.M)
    assert match, name
    return extract_function("magic.c", match.group(0))


def check_handlers_use_shared_numbers(magic):
    code = strip_comments(magic)
    for handler, calls in CALLS.items():
        bodies = function_bodies(code, r"\bvoid\s+" + handler + r"\s*\(")
        assert len(bodies) == 1, handler
        for call in calls:
            assert call in bodies[0], (handler, call)
    for handler, factor in WORDS.items():
        body = function_bodies(code, r"\bvoid\s+" + handler + r"\s*\(")[0]
        for call in ("< holy_word_slay_level(level)", "holy_word_slay_damage()",
                     "int dam = holy_word_damage(level);", "holy_word_bane_damage(dam)",
                     "lev < holy_word_blind_level(level)", "lev < holy_word_paralysis_level(level)"):
            assert call in body, (handler, call)
        assert (factor in body) if factor else "unholy_word_factor" not in body, handler
        assert ("holy_word_zealot_damage(ch, dam)" in body) == (handler != "single_voice_of_creation"), handler


def facts_functions():
    """The batch's facts functions, from its ability_facts() cases."""
    table = dict(re.findall(r"case (SPELL_\w+):\s*return (\w+);", source("abilities.c").read_text()))
    return sorted({table["SPELL_" + spell] for spell in BATCH})


def other_facts(defined):
    """Empty stand-ins for the facts functions of abilities this harness does not build."""
    declared = re.findall(r"^std::string (\w+_facts)\(char_data \*ch\);", source("abilities.h").read_text(), re.M)
    return "".join(f"std::string {name}(char_data *) {{ return {{}}; }}\n"
                   for name in declared if name not in defined)


def main():
    magic = source("magic.c").read_text()
    check_handlers_use_shared_numbers(magic)
    facts = facts_functions()
    functions = [other_facts(facts),
                 extract_function("utility.c", "int dice(int num, int size)"),
                 extract_function("utility.c", "int BOUNDED(int a, int b, int c)"),
                 extract_function("utility.c", "int GET_CLASS(P_char ch, uint m_class)"),
                 extract_function("utility.c", "int GET_SECONDARY_CLASS(P_char ch, uint m_class)")]
    functions += [definition(magic, name) for name in SHARED + facts]
    build = ROOT / "bin/tests"
    build.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ability-batch-3-", dir=build) as temporary:
        directory = Path(temporary)
        harness = directory / "batch3.cpp"
        code = HARNESS.replace("BATCH", ", ".join("SPELL_" + spell for spell in BATCH))
        harness.write_text(code.replace("int main() {", "\n".join(functions) + "\nint main() {"))
        binary = directory / "batch3"
        subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
                        "-ffunction-sections", "-fdata-sections", "-Wl,--gc-sections",
                        "-fsanitize=address,undefined", "-fno-sanitize-recover=undefined",
                        "-Isrc", "-I/usr/include/mysql", "-I/usr/include/libxml2",
                        str(harness), "src/abilities/abilities.c", "src/core/random.c",
                        "-o", str(binary)], cwd=ROOT, check=True)
        subprocess.run([str(binary)], cwd=directory, check=True)


if __name__ == "__main__":
    main()
