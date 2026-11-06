#!/usr/bin/env python3
"""Shared ability numbers, batch 5: shaman spells in smagic.c.

Builds src/abilities/abilities.c and the real RNG with every shared and facts function
of smagic.c, under sanitizers. Each converted roll keeps its pre-conversion expression
below as the oracle: under the same seeds it must give the same value and leave the RNG
at the same draw, and the value must fall inside the range its facts show. Every facts
page is built at every level for several shamans: it must never roll, and every line
must fit 79 columns.
"""
import re
import subprocess
import tempfile
from pathlib import Path

from _paths import ROOT, extract_function, source
from _innate_numbers import with_innate_numbers
from _source_contract import function_bodies, strip_comments

SMAGIC = source("smagic.c").read_text()

# Spell constant and facts name of every spell this batch converted.
CONVERTED = """
SPELL_GASEOUS_CLOUD gaseous_cloud
SPELL_GUARDIAN_SPIRITS guardian_spirits
SPELL_BLOODHOUND bloodhound
SPELL_WOLFSPEED wolfspeed
SPELL_PYTHONSTING pythonsting
SPELL_SNAILSPEED snailspeed
SPELL_MOLEVISION molevision
SPELL_PANTHERSPEED pantherspeed
SPELL_MOUSESTRENGTH mousestrength
SPELL_SUMMON_BEAST summon_beast
SPELL_GREATER_SUMMON_BEAST greater_summon_beast
SPELL_HAWKVISION hawkvision
SPELL_BEARSTRENGTH bearstrength
SPELL_SHREWTAMENESS shrewtameness
SPELL_LIONRAGE lionrage
SPELL_ELEPHANTSTRENGTH elephantstrength
SPELL_RAVENFLIGHT ravenflight
SPELL_GREATER_RAVENFLIGHT greater_ravenflight
SPELL_GREATER_PYTHONSTING greater_pythonsting
SPELL_CALL_OF_THE_WILD call_of_the_wild
SPELL_BEASTFORM beastform
SPELL_ELEM_AFFINITY elemental_affinity
SPELL_CASCADING_ELEMENTAL_BEAM cascading_elemental_beam
SPELL_ELEM_FURY elemental_fury
SPELL_ICE_MISSILE ice_missile
SPELL_FLAMEBURST flameburst
SPELL_SCALDING_BLAST scalding_blast
SPELL_COLD_WARD cold_ward
SPELL_FIRE_WARD fire_ward
SPELL_SCORCHING_TOUCH scorching_touch
SPELL_MOLTEN_SPRAY molten_spray
SPELL_EARTHEN_GRASP earthen_grasp
SPELL_GREATER_EARTHEN_GRASP greater_earthen_grasp
SPELL_ARIEKS_SHATTERING_ICEBALL arieks_shattering_iceball
SPELL_SCATHING_WIND scathing_wind
SPELL_EARTHEN_RAIN earthen_rain
SPELL_TORMENT_SPIRITS torment_spirits
SPELL_INDOMITABILITY indomitability
SPELL_SPIRIT_ARMOR spirit_armor
SPELL_TRANSFER_WELLNESS transfer_wellness
SPELL_LESSER_MENDING lesser_mending
SPELL_MENDING mending
SPELL_SOUL_DISTURBANCE soul_disturbance
SPELL_SPIRIT_SIGHT spirit_sight
SPELL_SENSE_SPIRIT sense_spirit
SPELL_MALISON malison
SPELL_WELLNESS wellness
SPELL_GREATER_MENDING greater_mending
SPELL_SPIRIT_ANGUISH spirit_anguish
SPELL_GREATER_SPIRIT_ANGUISH greater_spirit_anguish
SPELL_GREATER_SOUL_DISTURB greater_soul_disturbance
SPELL_SPIRIT_WARD spirit_ward
SPELL_SPIRIT_JUMP spirit_jump
SPELL_GREATER_SPIRIT_SIGHT greater_spirit_sight
SPELL_GREATER_SPIRIT_WARD greater_spirit_ward
SPELL_ETHERPORTAL etherportal
SPELL_SPIRIT_WALK spirit_walk
SPELL_CORROSIVE_BLAST corrosive_blast
SPELL_FIREBRAND firebrand
SPELL_RESTORATION restoration
SPELL_LESSER_GUARDIAN_WARD lesser_guardian_ward
SPELL_GUARDIAN_WARD guardian_ward
SPELL_GREATER_GUARDIAN_WARD greater_guardian_ward
"""
SPELLS = [line.split() for line in CONVERTED.split("\n") if line.strip()]

# What each handler (or the event or per-target callback doing its work) must call.
HANDLER_CALLS = {
    "spell_guardian_spirits": ["guardian_spirits_renewal(live_rolls, level)",
                               "guardian_spirits_duration(live_rolls, level)",
                               "af.modifier = guardian_spirits_ac(live_rolls)"],
    "spell_lesser_guardian_ward": ["lesser_guardian_ward_duration(level)",
                                   "lesser_guardian_ward_amount(live_rolls, level)"],
    "spell_guardian_ward": ["guardian_ward_duration(level)", "guardian_ward_amount(live_rolls, level)"],
    "spell_greater_guardian_ward": ["greater_guardian_ward_duration(level)",
                                    "greater_guardian_ward_amount(live_rolls, level)"],
    "spell_spirit_walk": ["CharWait(ch, spirit_walk_lag())", "if (!spirit_walk_corpse_roll(live_rolls))"],
    "spell_etherportal": ["set.decay_timer = etherportal_decay_timer(ch)",
                          "set.throughput = etherportal_throughput(live_rolls, ch)"],
    "spell_elemental_affinity": ["af.duration = elemental_affinity_duration(level)"],
    "event_elemental_fury": ["spell_earthen_rain(elemental_fury_level(ch)",
                             "spell_scathing_wind(elemental_fury_level(ch)",
                             "spell_tempest(elemental_fury_level(ch)",
                             "add_event(event_elemental_fury, elemental_fury_interval()"],
    "spell_elemental_fury": ["add_event(event_elemental_fury, elemental_fury_interval()"],
    "spell_ice_missile": ["temp = ice_missile_count(level)", "dam = ice_missile_damage(live_rolls, level)"],
    "spell_corrosive_blast": ["int dam = corrosive_blast_damage(live_rolls, level)",
                              "int ran = corrosive_blast_ac(live_rolls, level)",
                              "af.duration = corrosive_blast_duration()"],
    "spell_restoration": ["gain = restoration_healing(live_rolls, level, ch)"],
    "spell_flameburst": ["dam = flameburst_damage(live_rolls, level)", "dam = flameburst_failed_save(dam)"],
    "spell_scalding_blast": ["dam = scalding_blast_damage(live_rolls, level)",
                             "dam = scalding_blast_failed_save(dam)"],
    "spell_scorching_touch": ["dam = scorching_touch_damage(live_rolls, level)"],
    "spell_molten_spray": ["dam = molten_spray_damage(live_rolls, level)", "dam = molten_spray_failed_save(dam)"],
    "spell_soul_disturbance": ["dam = soul_disturbance_damage(live_rolls, level)"],
    "spell_greater_soul_disturbance": ["dam = greater_soul_disturbance_damage(live_rolls, level)"],
    "spell_greater_spirit_anguish": ["dam = greater_spirit_anguish_damage(live_rolls, level, ch)",
                                     "dam = greater_spirit_anguish_failed_save(dam)"],
    "spell_spirit_anguish": ["dam = spirit_anguish_damage(live_rolls, level, ch)"],
    "spell_gaseous_cloud": ["int dam = gaseous_cloud_damage(live_rolls, level)", "dam = gaseous_cloud_saved(dam)"],
    "spell_arieks_shattering_iceball": ["int dam = arieks_shattering_iceball_damage(live_rolls, level)",
                                        "dam = arieks_shattering_iceball_failed_save(dam)"],
    "spell_single_scathing_wind": ["dam = scathing_wind_damage(live_rolls, level)"],
    "spell_scathing_wind": ["cast_as_damage_area(ch, spell_single_scathing_wind, level"],
    "spell_single_earthen_rain": ["dam = earthen_rain_damage(live_rolls, level)", "dam = earthen_rain_saved(dam)"],
    "spell_earthen_rain": ["cast_as_damage_area(ch, spell_single_earthen_rain, level"],
    "earthen_grasp": ["level = earthen_grasp_level(level, ch)", "earthen_grasp_damage(live_rolls, level)",
                      "earthen_grasp_saved_damage(live_rolls, level)"],
    "spell_earthen_grasp": ["earthen_grasp(level, ch, victim, false)"],
    "spell_single_earthen_grasp": ["earthen_grasp(level, ch, victim, true)"],
    "spell_greater_earthen_grasp": ["cast_as_damage_area(ch, spell_single_earthen_grasp, level"],
    "spell_pythonsting": ["dam = pythonsting_damage(live_rolls, level)", "dam = pythonsting_failed_save(dam)"],
    "spell_greater_pythonsting": ["cast_as_damage_area(ch, spell_pythonsting, level"],
    "spell_bloodhound": ["af.duration = bloodhound_duration(level)"],
    "spell_spirit_armor": ["duration = spirit_armor_duration(level, ch)",
                           "af.modifier = spirit_armor_ac(level, ch)", "int save = spirit_armor_save(level)"],
    "spell_transfer_wellness": ["to = transfer_wellness_healing(live_rolls, level, ch)",
                                "from = transfer_wellness_cost(to)"],
    "spell_wolfspeed": ["level += animalist_level_bonus(live_rolls, ch)", "af.duration = wolfspeed_duration(level)",
                        "af1->duration = wolfspeed_duration(level)",
                        "af.modifier = wolfspeed_move(live_rolls, level)"],
    "spell_snailspeed": ["af.duration = snailspeed_duration()"],
    "spell_pantherspeed": ["level += animalist_level_bonus(live_rolls, ch)",
                           "af.duration = pantherspeed_duration(level)",
                           "af1->duration = pantherspeed_duration(level)",
                           "af.modifier = pantherspeed_move(live_rolls, level)"],
    "spell_molevision": ["af.duration = molevision_duration()"],
    "spell_mousestrength": ["af.duration = mousestrength_strong_duration(live_rolls)",
                            "af.duration = mousestrength_duration()"],
    "spell_hawkvision": ["level = animalist_level(level, ch)", "af.duration = hawkvision_duration(level)",
                         "af1->duration = hawkvision_duration(level)"],
    "spell_bearstrength": ["level = animalist_level(level, ch)",
                           "af.duration = bearstrength_duration(live_rolls, level)",
                           "af.modifier = bearstrength_str(live_rolls, level)", "af.modifier = bearstrength_dex()",
                           "af.modifier = bearstrength_str_max(level)"],
    "spell_elephantstrength": ["level += animalist_level_bonus(live_rolls, ch)",
                               "af.duration = elephantstrength_duration(level)",
                               "af.modifier = elephantstrength_str_max(live_rolls, level)",
                               "af.modifier = elephantstrength_con_max(live_rolls, level)",
                               "af.modifier = elephantstrength_stat_penalty(live_rolls)",
                               "af.modifier = elephantstrength_damroll(level)"],
    "spell_shrewtameness": ["af.duration = shrewtameness_duration()"],
    "spell_lionrage": ["duration = lionrage_duration(level, ch)", "af.modifier = lionrage_agi(live_rolls)",
                       "af.modifier = lionrage_damroll(level)"],
    "spell_ravenflight": ["level += animalist_level_bonus(live_rolls, ch)",
                          "af.duration = ravenflight_duration(level)",
                          "af1->duration = ravenflight_duration(level)"],
    "spell_greater_ravenflight": ["spell_ravenflight(level, ch"],
    "spell_call_of_the_wild": ["af.duration = call_of_the_wild_duration(level)"],
    "spell_malison": ["af.duration = malison_duration(level)", "af.modifier = malison_penalty(level)"],
    "spell_spirit_sight": ["af.duration = spirit_sight_duration(level)",
                           "af1->duration = spirit_sight_duration(level)",
                           "if (spirit_sight_sees_invisible(ch)"],
    "spell_greater_spirit_sight": ["af.duration = greater_spirit_sight_duration(level)",
                                   "af1->duration = greater_spirit_sight_duration(level)"],
    "spell_sense_spirit": ["duration = sense_spirit_duration(level, ch)", "af.duration = duration"],
    "spell_summon_beast": ["dur = summon_beast_duration(level, ch)"],
    "spell_greater_summon_beast": ["dur = greater_summon_beast_duration(level, ch)"],
    "spell_wellness": ["gain = wellness_healing(live_rolls, level, ch)"],
    "spell_lesser_mending": ["gain = lesser_mending_healing(live_rolls, level, ch)"],
    "spell_mending": ["gain = mending_healing(live_rolls, level, ch)"],
    "spell_greater_mending": ["gain = greater_mending_healing(live_rolls, level, ch)"],
    "spell_spirit_ward": ["duration = spirit_ward_duration(level, ch)"],
    "spell_greater_spirit_ward": ["duration = spirit_ward_duration(level, ch)"],
    "spell_cold_ward": ["af.duration = cold_ward_duration(level)", "af1->duration = cold_ward_duration(level)"],
    "spell_fire_ward": ["af.duration = fire_ward_duration(level)", "af1->duration = fire_ward_duration(level)"],
    "spell_spirit_jump": ["CharWait(ch, spirit_jump_lag(ch))", "distance = spirit_jump_distance(level, ch)"],
    "spell_beastform": ["af.duration = beastform_duration(level)"],
    "spell_indomitability": ["af.duration = indomitability_duration(level)"],
    "event_firebrand": ["dam = firebrand_burn_damage(live_rolls, level)",
                        "add_event(event_firebrand, firebrand_interval()"],
    "spell_firebrand": ["dam = firebrand_damage(live_rolls, level)", "af->modifier = firebrand_burns()"],
    "spell_cascading_elemental_beam": ["dam = cascading_elemental_beam_damage(live_rolls, level)",
                                       "blind(ch, victim, cascading_elemental_beam_blind(live_rolls))",
                                       "blind(ch, ch, cascading_elemental_beam_blind(live_rolls))",
                                       "Stun(victim, ch, cascading_elemental_beam_stun(), TRUE)",
                                       "Stun(ch, ch, cascading_elemental_beam_stun(), TRUE)"],
    "event_torment_spirits": ["dam = torment_spirits_damage(live_rolls, ch)",
                              "add_event(event_torment_spirits, torment_spirits_interval()"],
}

HARNESS = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "magic/spells.h"
#include "abilities/abilities.h"
#include <algorithm>
#include <cassert>
#include <climits>
#include <cstdio>
#include <cstring>
#include <functional>
#include <string>

void randomize(uint64_t seed);

static bool improved_heal, elemental_power;
bool has_innate(P_char, int innate)
{
    return (innate == INNATE_IMPROVED_HEAL && improved_heal) ||
           (innate == INNATE_ELEMENTAL_POWER && elemental_power);
}
float get_property(const char *, double fallback) { return (float)fallback; }
// Etherportal's properties differ from their fallbacks, so reading a wrong key shows.
int get_property(const char *key, int fallback)
{
    if (!std::strcmp(key, "portals.etherportal.maxToPass"))
        return 6;
    if (!std::strcmp(key, "portals.etherportal.decayTimeout"))
        return 100;
    return fallback;
}
P_char get_linked_char(P_char, ush_int) { return nullptr; }

FUNCTIONS

// The next draw after a roll; equal fingerprints after equal seeds mean equal draw counts.
static int fingerprint() { return number(0, INT_MAX); }

// The original expression and the shared function draw alike, and the value lies in the
// range the facts show (the lowest and highest rolls, in either order).
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

// Handler code before its numbers moved into shared functions.
static int old_flameburst(int level) {
    int num_dice = (level / 10);
    int dam = (dice((num_dice + 4), 6) * 5);
    dam = BOUNDED(1, dam, 200);
    return dam;
}
static int old_scalding_blast(int level) {
    int num_dice = (level / 10);
    int dam = (dice((num_dice + 4), 6) * 7);
    dam = BOUNDED(1, dam, 240);
    return dam;
}
static int old_pythonsting(int level) {
    int dam = number(1, level * 4);
    dam = BOUNDED(1, dam, 160);
    return dam;
}
static int old_restoration(int level, P_char ch) {
    int gain = (int)(level * 5 + number(0, 40));
    if (!has_innate(ch, INNATE_IMPROVED_HEAL))
        gain = (int)(gain * 0.66);
    return gain;
}
static int old_greater_spirit_anguish(int level, P_char ch) {
    int dam = dice(level * 3, 6);
    if (IS_SPIRITUALIST(ch))
    {
        dam += level * 4;
    }
    return dam;
}
static int old_spirit_anguish(int level, P_char ch) {
    int dam = dice(level * 4, 2);
    if (IS_SPIRITUALIST(ch))
        dam += level;
    return dam;
}
static int old_wellness(int level, P_char ch) {
    int gain = (int)(dice(4, 7 + (level / 10)));
    if (has_innate(ch, INNATE_IMPROVED_HEAL))
    {
        gain += GET_LEVEL(ch);
    }
    return gain;
}
static int old_lesser_mending(int level, P_char ch) {
    int gain = (int)(level / 2 + number(0, 5));
    if (has_innate(ch, INNATE_IMPROVED_HEAL))
        gain += (int)(number((int)(level / 2), (int)(level * 1.5)));
    return gain;
}
static int old_mending(int level, P_char ch) {
    int gain = (level * 2) + number(-20, 20);
    if (has_innate(ch, INNATE_IMPROVED_HEAL))
        gain += (int)(number((int)(level / 2), (int)(level)));
    return MAX(1, gain);
}
static int old_greater_mending(int level, P_char ch) {
    int gain = (level * 3) + number(-30, 30);
    if (has_innate(ch, INNATE_IMPROVED_HEAL))
        gain += (int)(number((int)(level / 2), (int)(level)));
    return MAX(1, gain);
}
// The animalist cast level, as wolfspeed, pantherspeed, elephantstrength and ravenflight roll it.
static int old_animalist(int level, P_char ch) {
    if (IS_ANIMALIST(ch))
        level += number(10, (int)(GET_LEVEL(ch) / 2));
    return level;
}
static int new_animalist(const Rolls &rolls, int level, P_char ch) {
    if (IS_ANIMALIST(ch))
        level += animalist_level_bonus(rolls, ch);
    return level;
}
// Etherportal's settings before they moved into shared functions.
static int old_etherportal(P_char ch, int *decay_timer) {
    int specBonus = 0;
    int maxToPass = get_property("portals.etherportal.maxToPass", 5);
    *decay_timer = get_property("portals.etherportal.decayTimeout", 60 * 2);
    if (GET_SPEC(ch, CLASS_SHAMAN, SPEC_ELEMENTALIST))
    {
        specBonus = 2;
        *decay_timer = (*decay_timer / 2) * 3;
    }
    return MAX(0, (int)((ch->player.level - 46))) + number(2, maxToPass + specBonus);
}

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

struct Viewer { const char *name; uint m_class; int spec; bool improved_heal, elemental_power; };
static const Viewer viewers[] = {
    { "warrior", CLASS_WARRIOR, 0, false, false },
    { "shaman", CLASS_SHAMAN, 0, false, false },
    { "animalist", CLASS_SHAMAN, SPEC_ANIMALIST, false, false },
    { "spiritualist", CLASS_SHAMAN, SPEC_SPIRITUALIST, true, false },
    { "elementalist", CLASS_SHAMAN, SPEC_ELEMENTALIST, false, true },
};

static char_data viewer(const Viewer &v, int level) {
    char_data ch{};
    ch.player.m_class = v.m_class;
    ch.player.spec = v.spec;
    ch.player.level = level;
    ch.points.hit = 300;
    improved_heal = v.improved_heal;
    elemental_power = v.elemental_power;
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
            SAME(-1 * number(150, 200), guardian_spirits_ac(rolls));
            SAME(MIN(level * 4, 150) + number(-level / 2, level / 2), lesser_guardian_ward_amount(rolls, level));
            SAME(MIN(level * 10, 450) + number(-level, level), guardian_ward_amount(rolls, level));
            SAME(MIN(level * 15, 760) + number(-level, level), greater_guardian_ward_amount(rolls, level));
            SAME((dice(1, 3) * 4 + level / 2), ice_missile_damage(rolls, level));
            SAME(dice(level, 3) * 4, corrosive_blast_damage(rolls, level));
            SAME(number(level, level * 2), corrosive_blast_ac(rolls, level));
            SAME(old_restoration(level, ch), restoration_healing(rolls, level, ch));
            SAME(old_flameburst(level), flameburst_damage(rolls, level));
            SAME(old_scalding_blast(level), scalding_blast_damage(rolls, level));
            SAME(dice(level, 2) * 4, scorching_touch_damage(rolls, level));
            SAME(dice(level, 2) * 4, molten_spray_damage(rolls, level));
            SAME(dice(level * 3, 2), soul_disturbance_damage(rolls, level));
            SAME(dice(level * 6, 2), greater_soul_disturbance_damage(rolls, level));
            SAME(old_greater_spirit_anguish(level, ch), greater_spirit_anguish_damage(rolls, level, ch));
            SAME(old_spirit_anguish(level, ch), spirit_anguish_damage(rolls, level, ch));
            SAME(dice(level * 3, 6), gaseous_cloud_damage(rolls, level));
            SAME(dice(level * 3, 5) + number(1, 80), arieks_shattering_iceball_damage(rolls, level));
            SAME(dice(3 * level, 5), scathing_wind_damage(rolls, level));
            SAME(dice(level, 5) * 3, earthen_rain_damage(rolls, level));
            SAME(dice(level, 12), earthen_grasp_damage(rolls, level));
            SAME(dice(level, 7), earthen_grasp_saved_damage(rolls, level));
            SAME(old_pythonsting(level), pythonsting_damage(rolls, level));
            for (int hit : { -5, 0, 300, 2000 }) {
                caster.points.hit = hit;
                SAME((int)(level * 2 + dice(2, 8) + GET_HIT(ch) / 3),
                     transfer_wellness_healing(rolls, level, ch));
            }
            // The animalist roll comes first, as in the handlers, then the spell's own dice.
            const int cast = GET_LEVEL(ch);
            int raised;
            SAME(old_animalist(cast, ch), new_animalist(rolls, cast, ch));
            SAME((raised = old_animalist(cast, ch), (raised / 2) + dice(2, 2)),
                 wolfspeed_move(rolls, new_animalist(rolls, cast, ch)));
            SAME((raised = old_animalist(cast, ch), raised + 5 + dice(3, 6)),
                 pantherspeed_move(rolls, new_animalist(rolls, cast, ch)));
            SAME((raised = old_animalist(cast, ch), (int)(raised / 10) + dice(2, 2)),
                 elephantstrength_str_max(rolls, new_animalist(rolls, cast, ch)));
            SAME((raised = old_animalist(cast, ch), (int)(raised / 5) + dice(3, 3)),
                 elephantstrength_con_max(rolls, new_animalist(rolls, cast, ch)));
            SAME(2 + (number(0, 2)), mousestrength_strong_duration(rolls));
            SAME(level + number(0, (int)(level / 10)), bearstrength_duration(rolls, level));
            SAME((int)(level / 3 + number(0, (int)(level / 10))), bearstrength_str(rolls, level));
            SAME(-10 - number(0, 5), elephantstrength_stat_penalty(rolls));
            SAME(-10 + (number(-3, 3)), lionrage_agi(rolls));
            SAME(old_wellness(level, ch), wellness_healing(rolls, level, ch));
            SAME(old_lesser_mending(level, ch), lesser_mending_healing(rolls, level, ch));
            SAME(old_mending(level, ch), mending_healing(rolls, level, ch));
            SAME(old_greater_mending(level, ch), greater_mending_healing(rolls, level, ch));
            SAME(level * 2 + number(0, 80), firebrand_damage(rolls, level));
            SAME(dice(level, 4), firebrand_burn_damage(rolls, level));
            SAME(dice((int)(level * 2.0), 7), cascading_elemental_beam_damage(rolls, level));
            SAME(number(4, 12) * WAIT_SEC, cascading_elemental_beam_blind(rolls));
            SAME(number(GET_LEVEL(ch) / 2, GET_LEVEL(ch) * 2) + 8, torment_spirits_damage(rolls, ch));
            SAME(number(0, 9), spirit_walk_corpse_roll(rolls));
            int decay_timer;
            SAME(old_etherportal(ch, &decay_timer), etherportal_throughput(rolls, ch));
            assert(decay_timer == etherportal_decay_timer(ch));
        }
    // Initial and renewed guardian spirits respect their four-hour floor.
    for (int level = 1; level <= 62; ++level) {
        const bool shown = true;
        const bool renewal_shown = true;
        same("guardian_spirits_duration", [&] { return std::max(4, level / 2 + number(-4, 0)); },
             [&](const Rolls &rolls) { return guardian_spirits_duration(rolls, level); }, shown);
        same("guardian_spirits_renewal", [&] { return std::max(4, level / 2 + number(-8, 0)); },
             [&](const Rolls &rolls) { return guardian_spirits_renewal(rolls, level); },
             renewal_shown);
        char_data ch = viewer(viewers[1], level);
        const std::string text = guardian_spirits_facts(&ch);
        assert((text.find("  Duration: ") != std::string::npos) == shown);
        assert((text.find("  Recast while active: ") != std::string::npos) == renewal_shown);
    }

    // Exact pages at level 56.
    char_data ch = viewer(viewers[0], 56);
    assert(contains(gaseous_cloud_facts(&ch), "  Gas damage: 168-1008 at your level, 56\n"
                                              "  If the target saves: 126-756\n"));
    assert(contains(guardian_spirits_facts(&ch),
                    "  Duration: 24-29 game hours (30-36.25 minutes) at your level, 56\n"
                    "  Recast while active: 20-29 game hours (25-36.25 minutes)\n"
                    "  Armor class: -200 to -150\n"));
    assert(contains(lesser_guardian_ward_facts(&ch), "  Ward strength: 122-178 at your level, 56\n"
                                                     "  Duration: 36 seconds\n"));
    assert(contains(greater_guardian_ward_facts(&ch), "  Ward strength: 704-816 at your level, 56\n"
                                                      "  Duration: 48 seconds\n"));
    assert(contains(ice_missile_facts(&ch), "  Missiles: 4 at your level, 56\n"
                                            "  Cold damage per missile: 32-40, one roll for all of them\n"
                                            "  Stopped by: minor globe, globe of invulnerability, spirit wards\n"));
    assert(contains(flameburst_facts(&ch), "  Fire damage: 45-200 at your level, 56\n"
                                           "  If the target fails its save: 59-266\n"));
    assert(contains(corrosive_blast_facts(&ch), "  If the target is already corroded: half\n"
                                                "  Armor class penalty if not already corroded: 56-112\n"
                                                "  The penalty cannot raise armor class above 0.\n"
                                                "  Penalty duration: 1-2 game hours (1.25-2.5 minutes)\n"));
    assert(contains(restoration_facts(&ch), "  Healing: 184-211 at your level, 56\n"));
    assert(contains(pythonsting_facts(&ch), "  Damage: 1-160 at your level, 56\n"
                                            "  If the target fails an agility save: 2-320\n"));
    assert(contains(transfer_wellness_facts(&ch), "  Healing: 214-228 at your level, 56, with your hit points\n"
                                                  "  Your cost: 107-114 hit points\n"));
    assert(contains(spirit_armor_facts(&ch), "  Duration: 56-57 game hours (70-71.25 minutes) at your level, 56\n"
                                             "  Armor class: -56\n  Saving throw vs spells: -2\n"));
    assert(contains(wolfspeed_facts(&ch), "  Casting level: 56\n"
                                          "  Duration: 57-58 game hours (71.25-72.5 minutes)\n"
                                          "  Maximum movement: 30-32\n"));
    assert(contains(elephantstrength_facts(&ch), "  Duration: 57-58 game hours (71.25-72.5 minutes)\n"
                                                 "  Maximum strength: 7-9\n  Maximum constitution: 14-20\n"
                                                 "  Damroll: 6\n  Dexterity and agility (rolled separately): -15 to -10\n"));
    assert(contains(bearstrength_facts(&ch), "  Casting level: 56\n  Duration: 56-62 game hours (70-77.5 minutes)\n"
                                             "  Strength: 18-23\n  Maximum strength: 3\n  Dexterity: -10\n"));
    assert(contains(lionrage_facts(&ch), "  Duration: 29-30 game hours (36.25-37.5 minutes) at your level, 56\n"
                                         "  Strength: 12\n  Damroll: 6\n  Agility: -13 to -7\n"));
    assert(contains(mousestrength_facts(&ch), "  Duration: 1-2 game hours (1.25-2.5 minutes)\n"
                                              "  On its two strongest results: 2-5 game hours (2.5-6.25 minutes)\n"));
    assert(contains(malison_facts(&ch), "  Duration: 19-20 game hours (23.75-25 minutes) at your level, 56\n"
                                        "  Every saving throw: +9, worse\n"));
    assert(contains(spirit_sight_facts(&ch), "  Detect invisibility: yes, at your level\n"));
    assert(contains(spirit_jump_facts(&ch), "  Range: 75 rooms at your level, 56\n"
                                            "  Your lag: 10.5 seconds\n"));
    assert(contains(spirit_walk_facts(&ch), "  Your lag: 10 seconds\n"
                                            "  Chance the corpse decays when you arrive: 1 in 10\n"));
    assert(contains(firebrand_facts(&ch), "  Fire damage: 112-192 at your level, 56\n"
                                          "  Then it burns: up to 3 times, 4 seconds apart\n"
                                          "  Fire damage per burn: 56-224\n"));
    assert(contains(cascading_elemental_beam_facts(&ch),
                    "  Damage: 112-784 at your level, 56\n"
                    "  Element: set by the target's shields and surroundings\n"
                    "  Fire: blinds 4 seconds to 12 seconds if the target fails its save\n"
                    "  Lightning: stuns up to 8 seconds; fear saves shorten or stop it\n"));
    assert(contains(torment_spirits_facts(&ch), "  Psionic damage per torment: 36-120 at your level, 56\n"
                                                "  Time between torments: 8 seconds\n"));
    assert(contains(elemental_fury_facts(&ch), "  Time between rounds: 4 seconds\n"
                                               "  Earthen rain, scathing wind and tempest: at level 46\n"));
    assert(contains(summon_beast_facts(&ch),
                    "  Charm duration: 31-32 game hours (38.75-40 minutes) at your level, 56\n"
                    "  Permanent instead if you hold a globe of shadows or have unholy alliance.\n"));
    assert(contains(greater_summon_beast_facts(&ch),
                    "  Charm duration: 66-67 game hours (82.5-83.75 minutes) at your level, 56\n"
                    "  Permanent instead if you hold a globe of shadows or have unholy alliance.\n"));
    assert(contains(sense_spirit_facts(&ch), "  Duration: 33-34 game hours (41.25-42.5 minutes) at your level, 56\n"));
    assert(contains(spirit_ward_facts(&ch), "  Duration: 28-29 game hours (35-36.25 minutes) at your level, 56\n"));
    assert(contains(lionrage_facts(&ch), "  Duration: 29-30 game hours (36.25-37.5 minutes) at your level, 56\n"));
    assert(contains(mending_facts(&ch), "  Healing: 92-132 at your level, 56\n"));
    // The test's etherportal properties: 6 to pass, 100 pulses to decay.
    assert(contains(etherportal_facts(&ch), "  People who can pass each way: 12-16 at your level, 56\n"
                                            "  Portal lasts: up to 25 seconds\n"));
    ch = viewer(viewers[0], 1);
    assert(contains(mending_facts(&ch), "  Healing: 1-22 at your level, 1\n"));
    assert(contains(spirit_sight_facts(&ch), "  Detect invisibility: not at your level\n"));
    assert(contains(etherportal_facts(&ch), "  People who can pass each way: 2-6 at your level, 1\n"));

    // The specializations and innates the pages read.
    ch = viewer(viewers[1], 56); // a shaman without a specialization
    assert(contains(lionrage_facts(&ch), "  Duration: 56-57 game hours (70-71.25 minutes) at your level, 56\n"));
    assert(contains(sense_spirit_facts(&ch), "  Duration: 61-62 game hours (76.25-77.5 minutes) at your level, 56\n"));
    assert(contains(spirit_ward_facts(&ch), "  Duration: 56-57 game hours (70-71.25 minutes) at your level, 56\n"));
    assert(greater_ravenflight_facts(&ch) == "  Casting level: 56\n  Duration: 56-57 game hours (70-71.25 minutes)\n");
    ch = viewer(viewers[2], 56); // animalist
    assert(contains(wolfspeed_facts(&ch), "  Casting level: 66-84\n"
                                          "  Duration: 67-86 game hours (83.75-107.5 minutes)\n"
                                          "  Maximum movement: 35-46\n"));
    assert(contains(hawkvision_facts(&ch), "  Casting level: 76\n  Duration: 38-39 game hours (47.5-48.75 minutes)\n"));
    assert(contains(summon_beast_facts(&ch),
                    "  Charm duration: 87-88 game hours (108.75-110 minutes) at your level, 56\n"));
    assert(contains(greater_summon_beast_facts(&ch),
                    "  Charm duration: 122-123 game hours (152.5-153.75 minutes) at your level, 56\n"));
    assert(greater_ravenflight_facts(&ch) == "  Casting level: 66-84\n"
                                             "  Duration: 66-85 game hours (82.5-106.25 minutes)\n"
                                             "  Each person in the room rolls separately.\n");
    ch = viewer(viewers[3], 56); // spiritualist with improved heal
    assert(contains(restoration_facts(&ch), "  Healing: 280-320 at your level, 56\n"));
    assert(contains(spirit_armor_facts(&ch), "  Armor class: -112\n"));
    assert(contains(spirit_ward_facts(&ch), "  Duration: 66-67 game hours (82.5-83.75 minutes) at your level, 56\n"));
    assert(contains(spirit_jump_facts(&ch), "  Range: 90 rooms at your level, 56\n  Your lag: 3 seconds\n"));
    assert(contains(greater_spirit_anguish_facts(&ch), "  Spirit damage: 392-1232 at your level, 56\n"
                                                       "  If the target fails its save: 470-1478\n"));
    assert(contains(wellness_facts(&ch), "  Healing per person: 60-104 at your level, 56\n"));
    ch = viewer(viewers[4], 56); // elementalist with elemental power
    assert(contains(earthen_grasp_facts(&ch), "  Damage level: 64, raised by elemental power\n"
                                              "  Earth damage on a grasp: 64-768, or 64-448 if the target saves\n"));
    assert(contains(etherportal_facts(&ch), "  People who can pass each way: 12-18 at your level, 56\n"
                                            "  Portal lasts: up to 37.5 seconds\n"));
    elemental_power = false;
    assert(contains(greater_earthen_grasp_facts(&ch), "  Damage level: 56, your level\n"));
    puts("PASS: batch 5 shared rolls match the old code and stay in range, facts never roll");
}
'''


def check_sources():
    code = strip_comments(SMAGIC)
    for handler, calls in HANDLER_CALLS.items():
        bodies = function_bodies(code, rf"\bvoid\s+{handler}\s*\(")
        assert len(bodies) == 1, handler
        for call in calls:
            assert call in bodies[0], f"{handler} does not call {call}"
    table = strip_comments(source("abilities.c").read_text())
    header = source("abilities.h").read_text()
    for constant, name in SPELLS:
        assert re.search(rf"case {constant}:\s*return {name}_facts;", table), constant
        assert f"std::string {name}_facts(char_data *ch);" in header, name


def main():
    check_sources()
    shared = [name for name in re.findall(r"^static [\w:]+ (\w+)\(", SMAGIC, re.M)
              if name != "greater_mending_cure_level"]  # only innates batch 2's page reads it here
    functions = [extract_function("utility.c", "int dice(int num, int size)"),
                 extract_function("utility.c", "int BOUNDED(int a, int b, int c)"),
                 extract_function("utility.c", "int GET_CLASS(P_char ch, uint m_class)")]
    functions += [extract_function("smagic.c", re.search(rf"^static [\w:]+ {name}\(", SMAGIC, re.M).group(0))
                  for name in shared]
    functions += [extract_function("smagic.c", f"std::string {name}_facts(") for _, name in SPELLS]
    pages = ",\n".join(f'    {{ "{name}", {name}_facts }}' for _, name in SPELLS)
    build = ROOT / "bin/tests"
    build.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ability-batch-5-", dir=build) as temporary:
        directory = Path(temporary)
        harness = directory / "batch5.cpp"
        harness.write_text(with_innate_numbers(HARNESS.replace("PAGES", pages).replace("FUNCTIONS", "\n".join(functions)), define_rolls=False))
        binary = directory / "batch5"
        subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
                        "-ffunction-sections", "-fdata-sections", "-Wl,--gc-sections",
                        "-fsanitize=address,undefined", "-fno-sanitize-recover=undefined",
                        "-Isrc", "-I/usr/include/mysql", "-I/usr/include/libxml2",
                        str(harness), "src/abilities/abilities.c", "src/core/random.c",
                        "-o", str(binary)], cwd=ROOT, check=True)
        subprocess.run([str(binary)], cwd=directory, check=True)


if __name__ == "__main__":
    main()
