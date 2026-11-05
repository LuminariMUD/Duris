/****************************************************************************
 *
 *  File: abilities.h                                           Part of Duris
 *  Usage: shared ability numbers, rolls and info page facts
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-11-04
 *
 ****************************************************************************/

#ifndef DURIS_ABILITIES_H
#define DURIS_ABILITIES_H

#include <string>

// Shared ability numbers: a converted ability's handler and its info page call the same
// function, so the page cannot drift from what the game does.
// See docs/ongoing-projects/ability-framework.md.

struct char_data;

// The RNG calls behind a shared number. A shared function takes `const Rolls &` and
// keeps its original expression, calling rolls.dice() and rolls.number() where the old
// code called dice() and number(). The handler passes live_rolls, which make the real
// calls in the same order. The info page passes lowest_rolls and highest_rolls, which
// return each call's smallest or largest result without touching the RNG; the two
// results bound a number that never decreases as any of its rolls increases.
struct Rolls
{
	int (*dice)(int count, int sides);
	int (*number)(int from, int to);
};
extern const Rolls live_rolls, lowest_rolls, highest_rolls;

struct Range
{
	int low;
	int high;
};

// Info page formatting.
std::string fact(const std::string &label, const std::string &text);
std::string show(Range range);
std::string seconds(int pulses);
std::string game_hours(int ticks);
std::string real_time(int pulses);

// The mechanics lines a converted ability shows to the viewing character.
typedef std::string (*AbilityFacts)(char_data *ch);

// The facts of a converted spell or skill, or nullptr when it is not converted.
AbilityFacts ability_facts(int skill);

// The facts of a converted innate, or nullptr when it is not converted.
AbilityFacts innate_facts(int innate);

// Facts functions, defined beside their handlers.
std::string fireball_facts(char_data *ch);
std::string bash_facts(char_data *ch);
std::string reflection_innate_facts(char_data *ch);
std::string gaseous_cloud_facts(char_data *ch);
std::string guardian_spirits_facts(char_data *ch);
std::string bloodhound_facts(char_data *ch);
std::string wolfspeed_facts(char_data *ch);
std::string pythonsting_facts(char_data *ch);
std::string snailspeed_facts(char_data *ch);
std::string molevision_facts(char_data *ch);
std::string pantherspeed_facts(char_data *ch);
std::string mousestrength_facts(char_data *ch);
std::string summon_beast_facts(char_data *ch);
std::string greater_summon_beast_facts(char_data *ch);
std::string hawkvision_facts(char_data *ch);
std::string bearstrength_facts(char_data *ch);
std::string shrewtameness_facts(char_data *ch);
std::string lionrage_facts(char_data *ch);
std::string elephantstrength_facts(char_data *ch);
std::string ravenflight_facts(char_data *ch);
std::string greater_ravenflight_facts(char_data *ch);
std::string greater_pythonsting_facts(char_data *ch);
std::string call_of_the_wild_facts(char_data *ch);
std::string beastform_facts(char_data *ch);
std::string elemental_affinity_facts(char_data *ch);
std::string cascading_elemental_beam_facts(char_data *ch);
std::string elemental_fury_facts(char_data *ch);
std::string ice_missile_facts(char_data *ch);
std::string flameburst_facts(char_data *ch);
std::string scalding_blast_facts(char_data *ch);
std::string cold_ward_facts(char_data *ch);
std::string fire_ward_facts(char_data *ch);
std::string scorching_touch_facts(char_data *ch);
std::string molten_spray_facts(char_data *ch);
std::string earthen_grasp_facts(char_data *ch);
std::string greater_earthen_grasp_facts(char_data *ch);
std::string arieks_shattering_iceball_facts(char_data *ch);
std::string scathing_wind_facts(char_data *ch);
std::string earthen_rain_facts(char_data *ch);
std::string torment_spirits_facts(char_data *ch);
std::string indomitability_facts(char_data *ch);
std::string spirit_armor_facts(char_data *ch);
std::string transfer_wellness_facts(char_data *ch);
std::string lesser_mending_facts(char_data *ch);
std::string mending_facts(char_data *ch);
std::string soul_disturbance_facts(char_data *ch);
std::string spirit_sight_facts(char_data *ch);
std::string sense_spirit_facts(char_data *ch);
std::string malison_facts(char_data *ch);
std::string wellness_facts(char_data *ch);
std::string greater_mending_facts(char_data *ch);
std::string spirit_anguish_facts(char_data *ch);
std::string greater_spirit_anguish_facts(char_data *ch);
std::string greater_soul_disturbance_facts(char_data *ch);
std::string spirit_ward_facts(char_data *ch);
std::string spirit_jump_facts(char_data *ch);
std::string greater_spirit_sight_facts(char_data *ch);
std::string greater_spirit_ward_facts(char_data *ch);
std::string etherportal_facts(char_data *ch);
std::string spirit_walk_facts(char_data *ch);
std::string corrosive_blast_facts(char_data *ch);
std::string firebrand_facts(char_data *ch);
std::string restoration_facts(char_data *ch);
std::string lesser_guardian_ward_facts(char_data *ch);
std::string guardian_ward_facts(char_data *ch);
std::string greater_guardian_ward_facts(char_data *ch);

#endif
