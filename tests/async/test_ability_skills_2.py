#!/usr/bin/env python3
"""Shared ability numbers, skills batch 2: passive combat, archery, monk and epic skills.

Builds src/abilities/abilities.c and the real RNG with this batch's shared and facts
functions, under sanitizers. Each roll keeps its pre-conversion expression below as an
oracle: under the same seeds it must give the same value and leave the RNG at the same
draw, inside the range the facts use. Moved arithmetic is compared with its old form over
a grid. Pages are built for every viewer at every level and rating: they never roll and
every line fits 79 columns. Source checks tie every handler to its shared functions and
pin the rolls the pages count.
"""
import re
import subprocess
import tempfile
from pathlib import Path

from _paths import ROOT, extract_function, source
from _source_contract import function_bodies, strip_comments

# File order matters: each file's functions may call those of the files before it.
SHARED = {
    "fight.c": """soul_trap_hit_points soul_trap_threshold soul_trap_group_threshold soul_trap_cap mangle_rating_needed expert_parry_mangle_penalty mangle_chance mangle_damage mangle_disarm_roll riposte_specialist_score riposte_lucky_share riposte_unlucky_share followup_riposte_threshold followup_riposte_blow followup_riposte_second_blow arcane_riposte_threshold arcane_riposte_damage disperse_flames_roll disperse_flames_level_roll flame_mastery_roll flame_mastery_level_roll flame_mastery_damage fist_of_dragon_roll blindfighting_to_hit_penalty blindfighting_ac_penalty blindfighting_defense_threshold parry_blind_score tainted_blade_roll tainted_blade_damage tainted_blade_bleed tainted_blade_rounds tainted_blade_interval blade_lines anatomy_strike_threshold vicious_strike_anatomy_bonus anatomy_torso_damage anatomy_leg_vitality anatomy_arm_damroll anatomy_wrist_hitroll anatomy_deaf_duration weapon_check_skill weapon_critical_check weapon_fumble_check weapon_skill_lines quick_step_threshold quick_step_miss_threshold indomitable_rage_duration indomitable_rage_hitroll indomitable_rage_damroll indomitable_rage_fear_save devastating_critical_damage plain_critical_damage critical_attack_threshold vicious_attack_threshold bare_hand_damage unarmed_damage_bonus vicious_strike_bonus_damage boiling_blood_threshold boiling_blood_damage sidestep_threshold dodge_agility_score dodge_floor dodge_ceiling dodge_monk_chance dodge_specialist_bonus dodge_drow_roll shield_block_rating_score shield_block_dex_score shield_block_monk_score shield_block_flaying_score improved_shield_combat_threshold improved_shield_combat_damage monk_riposte_chance monk_rise_rest parry_dex_bonus parry_wis_bonus expert_parry_score parry_specialist_score parry_sword_score four_hand_threshold four_hand_late_threshold double_attack_threshold triple_attack_threshold quadruple_attack_threshold extra_attack_note battle_senses_threshold battle_senses_duration shadow_movement_threshold shadow_movement_duration double_strike_threshold devotion_zealot_bonus zealot_regain_threshold critical_attack_roll critical_attack_disarm_roll critical_attack_vitality critical_attack_vitality_floor""".split(),
    "dam_mods.c": """arcane_block_threshold arcane_block_reduction""".split(),
    "range.c": """enchant_arrow_damage enchant_arrows_mark_duration enchant_arrows_effect_top point_blank_shot_threshold point_blank_shot_lag archery_speed_limit archery_hit_skill archery_range_hit_skill archery_speed_per_shot archery_skill_damage archery_fumble_roll archery_fumble_tenths indirect_shot_threshold cursed_arrows_threshold critical_shot_threshold critical_shot_factor shadow_archery_threshold arrow_block_chance""".split(),
    "grapple.c": """bearhug_threshold bearhug_pin_bonus bearhug_free_arms_roll bearhug_duration bearhug_lag bearhug_target_lag bearhug_miss_lag bearhug_interval bearhug_base_damage bearhug_damage_roll bearhug_rest""".split(),
    "guard.c": """guard_multi_limit guard_single_limit guard_agility_limit guard_chance_bound guard_rest""".split(),
    "ship_combat.c": """ship_damage_control_reduction""".split(),
    "affects.c": """shield_combat_value toughness_illithid_hit_points toughness_hit_points epic_stat_bonus epic_stat_facts""".split(),
    "epic_skills.c": """devotion_power_score devotion_power_roll devotion_power_level""".split(),
    "memorize.c": """devotion_keep_spell_threshold""".split(),
    "new_skills.c": """wornweight MonkAcBonus monk_damage_bonus monk_attack_rolls monk_attack_count monk_attack_roll_limit chant_note heroism_duration heroism_rest heroism_lag heroism_hitroll heroism_damroll heroism_dazzle_level heroism_haste_level heroism_blur_level buddha_palm_rest buddha_palm_failed_lag buddha_palm_lag buddha_palm_targets buddha_palm_damage quivering_palm_rest quivering_palm_failed_lag quivering_palm_lag quivering_palm_damage quivering_palm_anatomy_threshold quivering_palm_anatomy_damage jin_touch_rest jin_touch_failed_lag jin_touch_lag jin_touch_damage jin_touch_rated_damage jin_touch_weaken_rating jin_touch_weaken_duration jin_touch_weaken regenerate_rest regenerate_failed_lag regenerate_lag regenerate_duration regenerate_hit_regen tiger_palm_rest tiger_palm_threshold tiger_palm_duration fist_of_dragon_rest fist_of_dragon_duration""".split(),
    "actoth.c": """rage_failed_lag rage_lag rage_ragelord_lag rage_duration rage_rest""".split(),
    "bard.c": """song_charming_level_gap song_charming_pet_limit song_sleep_duration song_sleep_resisting_level""".split(),
}

SKILLS = [line.split() for line in """
SKILL_1H_FLAYING one_h_flaying fight.c
SKILL_1H_PIERCING one_h_piercing fight.c
SKILL_1H_SLASHING one_h_slashing fight.c
SKILL_2H_FLAYING two_h_flaying fight.c
SKILL_ARCANE_RIPOSTE arcane_riposte fight.c
SKILL_BATTLE_SENSES battle_senses fight.c
SKILL_BLINDFIGHTING blindfighting fight.c
SKILL_BOILING_BLOOD boiling_blood fight.c
SKILL_CRITICAL_ATTACK critical_attack fight.c
SKILL_DEVASTATING_CRITICAL devastating_critical fight.c
SKILL_DISPERSE_FLAMES disperse_flames fight.c
SKILL_DODGE dodge fight.c
SKILL_DOUBLE_ATTACK double_attack fight.c
SKILL_DOUBLE_STRIKE double_strike fight.c
SKILL_DUAL_WIELD dual_wield fight.c
SKILL_EXPERT_PARRY expert_parry fight.c
SKILL_EXPERT_RIPOSTE expert_riposte fight.c
SKILL_FLAME_MASTERY flame_mastery fight.c
SKILL_FOLLOWUP_RIPOSTE followup_riposte fight.c
SKILL_HOLY_BLADE holy_blade fight.c
SKILL_IMPROVED_SHIELD_COMBAT improved_shield_combat fight.c
SKILL_IMPROVED_TWOWEAPON improved_twoweapon fight.c
SKILL_INDOMITABLE_RAGE indomitable_rage fight.c
SKILL_MANGLE mangle fight.c
SKILL_PARRY parry fight.c
SKILL_QUADRUPLE_ATTACK quadruple_attack fight.c
SKILL_QUICK_STEP quick_step fight.c
SKILL_REACH_WEAPONS reach_weapons fight.c
SKILL_RIPOSTE riposte fight.c
SKILL_SHADOW_MOVEMENT shadow_movement fight.c
SKILL_SHIELD_BLOCK shield_block fight.c
SKILL_SIDESTEP sidestep fight.c
SKILL_SOUL_TRAP soul_trap fight.c
SKILL_TAINTED_BLADE tainted_blade fight.c
SKILL_TRIPLE_ATTACK triple_attack fight.c
SKILL_UNARMED_DAMAGE unarmed_damage fight.c
SKILL_VICIOUS_ATTACK vicious_attack fight.c
SKILL_VICIOUS_STRIKE vicious_strike fight.c
SKILL_ANATOMY anatomy fight.c
SONG_CHARMING song_charming bard.c
SONG_SLEEP song_sleep bard.c
SKILL_EPIC_AGILITY epic_agility affects.c
SKILL_EPIC_CHARISMA epic_charisma affects.c
SKILL_EPIC_CONSTITUTION epic_constitution affects.c
SKILL_EPIC_DEXTERITY epic_dexterity affects.c
SKILL_EPIC_INTELLIGENCE epic_intelligence affects.c
SKILL_EPIC_LUCK epic_luck affects.c
SKILL_EPIC_POWER epic_power affects.c
SKILL_EPIC_STRENGTH epic_strength affects.c
SKILL_EPIC_WISDOM epic_wisdom affects.c
SKILL_SHIELD_COMBAT shield_combat affects.c
SKILL_TOUGHNESS toughness affects.c
SKILL_ARCHERY archery range.c
SKILL_CRITICAL_SHOT critical_shot range.c
SKILL_CURSED_ARROWS cursed_arrows range.c
SKILL_ENCHANT_ARROWS enchant_arrows range.c
SKILL_INDIRECT_SHOT indirect_shot range.c
SKILL_POINT_BLANK_SHOT point_blank_shot range.c
SKILL_SHADOW_ARCHERY shadow_archery range.c
SKILL_ARCANE_BLOCK arcane_block dam_mods.c
SKILL_TIGER_PALM tiger_palm new_skills.c
SKILL_BEARHUG bearhug grapple.c
SKILL_GUARD guard guard.c
SKILL_BUDDHA_PALM buddha_palm new_skills.c
SKILL_FIST_OF_DRAGON fist_of_dragon new_skills.c
SKILL_HEROISM heroism new_skills.c
SKILL_JIN_TOUCH jin_touch new_skills.c
SKILL_MARTIAL_ARTS martial_arts new_skills.c
SKILL_QUIVERING_PALM quivering_palm new_skills.c
SKILL_REGENERATE regenerate new_skills.c
SKILL_SHIP_DAMAGE_CONTROL ship_damage_control ship_combat.c
SKILL_DEVOTION devotion memorize.c
SKILL_RAGE rage actoth.c
SKILL_SAFE_FALL safe_fall falling.c
""".strip().splitlines()]

# Each handler's text: the shared calls, with the rolls the pages count written out.
HANDLER_CALLS = {
    ("fight.c", "bool soul_trap("): ["soul_trap_hit_points(ch, GET_LEVEL(victim))", "number(1, 100) >= soul_trap_threshold(ch)",
                                     "soul_trap_group_threshold(gl->ch) > number(1, 100)", "vamp(ch, soul_trap_hit_points(ch, GET_LEVEL(victim)), soul_trap_cap(ch))"],
    ("fight.c", "bool mangleSucceed("): ["skl = mangle_chance(skl);", "number(1, 100) > skl", "mangle_damage(live_rolls)", "!mangle_disarm_roll(live_rolls)",
                                         "expert_parry_mangle_penalty(victim)", "skl < mangle_rating_needed()"],
    ("fight.c", "int try_riposte("): ["int randomnumber = number(1, 1000);", "skl = riposte_specialist_score(ch, skl);", "skl *= riposte_lucky_share();",
                                      "skl *= riposte_unlucky_share();", "if (randomnumber > skl)", "expertriposte > number(1, 500)",
                                      "followup_riposte_threshold(skl) > number(0, 100)", "followup_riposte_blow(ch)",
                                      "melee_damage(ch, victim, followup_riposte_second_blow(live_rolls), 0, 0)"],
    ("fight.c", "int spell_damage("): ["number(1, 100) < arcane_riposte_threshold(skill_lvl)", "arcane_riposte_damage(skill_lvl, dam)",
                                       "GET_CHAR_SKILL(victim, SKILL_DISPERSE_FLAMES) > number(0, 100)", "!disperse_flames_roll(live_rolls)",
                                       "disperse_flames_level_roll(live_rolls) <= GET_LEVEL(victim)", "GET_CHAR_SKILL(victim, SKILL_FLAME_MASTERY) > number(0, 100)",
                                       "!flame_mastery_roll(live_rolls)", "flame_mastery_level_roll(live_rolls) <= GET_LEVEL(victim)", "flame_mastery_damage(victim, dam)"],
    ("fight.c", "int melee_damage("): ["!fist_of_dragon_roll(live_rolls)"],
    ("fight.c", "int chance_to_hit("): ["to_hit -= blindfighting_to_hit_penalty(ch);", "victim_ac += blindfighting_ac_penalty(victim);"],
    ("fight.c", "void event_tainted_blade("): ["tainted_blade_bleed(live_rolls, ch)"],
    ("fight.c", "bool tainted_blade("): ["raw_damage(ch, victim, tainted_blade_damage(), RAWDAM_DEFAULT, messages)", "af.modifier = tainted_blade_rounds(ch, blade_skill);",
                                         "old_af->modifier = tainted_blade_rounds(ch, blade_skill);", "add_event(event_tainted_blade, tainted_blade_interval(),"],
    ("fight.c", "int anatomy_strike("): ["return anatomy_torso_damage(dam);", "GET_VITALITY(victim) -= anatomy_leg_vitality();", "af.modifier = anatomy_arm_damroll(skl);",
                                         "af.modifier = anatomy_wrist_hitroll(skl);", "af.duration = anatomy_deaf_duration();"],
    ("fight.c", "bool hit("): ["wpn_skill = weapon_check_skill(ch, wpn_skill);", "number(30, 101) > weapon_critical_check(ch, wpn_skill)",
                               "number(1, 101) <= weapon_fumble_check(ch, wpn_skill)", "quick_step_threshold(victim) > number(1, 100)",
                               "quick_step_miss_threshold(victim) > number(0, 40)", "GET_CHAR_SKILL(victim, SKILL_INDOMITABLE_RAGE) > number(50, 160)",
                               "ir.duration = indomitable_rage_duration();", "ir.modifier = indomitable_rage_hitroll();", "ir.modifier = indomitable_rage_damroll();",
                               "ir.modifier = indomitable_rage_fear_save();", "int devcrit = number(1, 100);", "GET_CHAR_SKILL(ch, SKILL_DEVASTATING_CRITICAL) > devcrit",
                               "dam = devastating_critical_damage(dam, ch);", "dam = plain_critical_damage(dam);", "critical_attack_threshold(ch) > number(1, 100)",
                               "vicious_attack_threshold(ch) > number(0, 100)", "dam = bare_hand_damage(live_rolls);", "dam += unarmed_damage_bonus(ch);",
                               "vs_skill += vicious_strike_anatomy_bonus(ch);", "vs_skill > number(1, 1000)", "dam += vicious_strike_bonus_damage(ch);",
                               "boiling_blood_threshold(victim) > number(1, 100)", "dam = boiling_blood_damage();", "anatomy_strike_threshold(ch) >= (number(1, 100))",
                               "GET_CHAR_SKILL(ch, blade_skill) >= number(1, 100) && !tainted_blade_roll(live_rolls)"],
    ("fight.c", "int dodgeSucceed("): ["sidestep_threshold(char_dodger) > number(0, 100)", "learned = dodge_agility_score(char_dodger) -", "minimum = dodge_floor(char_dodger);",
                                       "percent = BOUNDED(minimum, learned, dodge_ceiling());", "percent = dodge_monk_chance(percent);", "percent += dodge_specialist_bonus();",
                                       "!dodge_drow_roll(live_rolls)", "number(1, 101) > percent"],
    ("fight.c", "int blockSucceed("): ["learned = shield_block_rating_score(victim);", "learned += shield_block_dex_score(victim);", "learned = shield_block_monk_score(learned);",
                                       "learned = shield_block_flaying_score(learned);", "number(1, 400) < improved_shield_combat_threshold(victim)",
                                       "int dmg = improved_shield_combat_damage(live_rolls, victim);"],
    ("fight.c", "int MonkRiposte("): ["percent = monk_riposte_chance(learned, percent);", "number(1, 150) > percent", "GET_C_AGI(victim) > number(1, 1000)",
                                      "GET_CHAR_SKILL(victim, SKILL_MARTIAL_ARTS) > number(1, 100)", "set_short_affected_by(victim, SKILL_MARTIAL_ARTS, monk_rise_rest());"],
    ("fight.c", "int parrySucceed("): ["learnedvictim += parry_dex_bonus(victim);", "learnedvictim += parry_wis_bonus(victim);", "parry_blind_score(learnedvictim, blindfightskl)",
                                       "learnedvictim = expert_parry_score(learnedvictim, expertparry);", "learnedvictim = parry_specialist_score(learnedvictim);",
                                       "learnedvictim = parry_sword_score(learnedvictim);", "expertparry > number(1, 250)"],
    ("fight.c", "int calculate_attacks("): ["four_hand_threshold(ch) >= number(1, 100)", "four_hand_late_threshold(ch) > number(1, 100)", "double_attack_threshold(ch) >= number(1, 100)",
                                            "triple_attack_threshold(ch) >= number(1, 100)", "quadruple_attack_threshold(ch) > number(1, 100)",
                                            "number(1, 100) < GET_CHAR_SKILL(ch, SKILL_DUAL_WIELD)", "GET_CHAR_SKILL(ch, SKILL_IMPROVED_TWOWEAPON) >= number(1, 100)"],
    ("fight.c", "bool critical_attack("): ["random = critical_attack_roll(live_rolls);", "critical_attack_vitality(victim->points.vitality)",
                                           "!critical_attack_disarm_roll(live_rolls)", "GET_VITALITY(victim) > critical_attack_vitality_floor()"],
    ("fight.c", "int fear_check("): ["GET_CHAR_SKILL(ch, SKILL_INDOMITABLE_RAGE) > number(1, 150)"],
    ("dam_mods.c", "ALL"): ["number(1, 250) <= arcane_block_threshold(victim)", "dam_mod->mod = -(arcane_block_reduction(live_rolls, victim)) / 100.0;",
                            "GET_CHAR_SKILL(victim, SKILL_FLAME_MASTERY) > number(1, 101)", "dam_factor[DF_TIGERPALM]"],
    ("range.c", "int enchant_arrows("): ["duration = enchant_arrows_mark_duration();", "GET_CHAR_SKILL(ch, SKILL_ENCHANT_ARROWS) >= number(60, 180)",
                                         "GET_CHAR_SKILL(ch, SKILL_ENCHANT_ARROWS) >= number(80, 180)", "GET_CHAR_SKILL(ch, SKILL_ENCHANT_ARROWS) >= number(80, 190)",
                                         "GET_CHAR_SKILL(ch, SKILL_ENCHANT_ARROWS) > number(99, 199)"],
    ("range.c", "ALL"): ["dam = enchant_arrow_damage(live_rolls);", "number(1, 130) <= point_blank_shot_threshold(ch)", "CharWait(ch, point_blank_shot_lag());",
                         "speed = MIN(speed, archery_speed_limit(ch));", "speed_per_shot = archery_speed_per_shot();", "archery_range_hit_skill(ch, i)",
                         "chance_to_hit(ch, victim, archery_hit_skill(ch), 0)", "indirect_shot_threshold(ch) < number(1, 130)", "number(1, 100) <= cursed_arrows_threshold(ch)",
                         "number(1, 100) <= GET_CHAR_SKILL(ch, SKILL_ENCHANT_ARROWS)", "arrow_block_chance(victim);", "number(1, 1600) <= block_chance",
                         "dam += archery_skill_damage(live_rolls, ch);", "GET_CHAR_SKILL(ch, SKILL_ARCHERY) < archery_fumble_roll(live_rolls)",
                         "dam = (dam * archery_fumble_tenths(live_rolls)) / 10.0;", "critical_shot_threshold(ch) >= number(1, 3000)", "dam *= critical_shot_factor();",
                         "shadow_archery_threshold(ch) > number(1, 105)", "number(2, enchant_arrows_effect_top(ch))",
                         "nb_att += double_attack_threshold(ch) > number(0, 100)", "nb_att += triple_attack_threshold(ch) > number(0, 100)"],
    ("interp.c", "ALL"): ["GET_CHAR_SKILL(exec_char,"],
    ("grapple.c", "void do_bearhug("): ["percent = bearhug_threshold(ch);", "percent > number(1, 101)", "gclvl = bearhug_pin_bonus(ch);", "bearhug_free_arms_roll(live_rolls, gclvl)",
                                        "af.duration = bearhug_duration();", "CharWait(ch, bearhug_lag());", "CharWait(victim, bearhug_target_lag());",
                                        "CharWait(ch, bearhug_miss_lag());", "add_event(event_bearhug, bearhug_interval(),"],
    ("grapple.c", "void event_bearhug("): ["af.duration = bearhug_rest();", "int dam = bearhug_base_damage(ch, GET_C_STR(victim));",
                                           "dam += bearhug_damage_roll(live_rolls);", "add_event(event_bearhug, bearhug_interval(),"],
    ("guard.c", "ALL"): ["number_guarding(ch) >= guard_multi_limit()", "number_guarding(ch) >= guard_single_limit()", "chance = guard_chance_bound(chance);",
                         "number(0, 100) > chance", "set_short_affected_by(guard, SKILL_GUARD, guard_rest());", "BOUNDED(-guard_agility_limit(),"],
    ("ship_combat.c", "int epic_ship_damage_control("): ["reduction_mod = ship_damage_control_reduction(dam, skill);"],
    ("affects.c", "int apply_ac("): ["value = shield_combat_value(ch, value);"],
    ("affects.c", "int calculate_hitpoints2("): ["toughness_illithid_hit_points(ch);", "toughness = toughness_hit_points(ch, GET_CHAR_SKILL(ch, SKILL_TOUGHNESS));"],
    ("affects.c", "void get_epic_stat_affects("): [f"af.modifier = epic_stat_bonus(ch, SKILL_EPIC_{name});" for name in "STRENGTH POWER AGILITY INTELLIGENCE DEXTERITY WISDOM CONSTITUTION CHARISMA LUCK".split()],
    ("epic_skills.c", "int devotion_skill_check("): ["int dev_power = devotion_power_score(ch) - devotion_power_roll(live_rolls);", "return devotion_power_level(dev_power);"],
    ("memorize.c", "void use_spell("): ["devotion_keep_spell_threshold(ch) > number(0, 100)"],
    ("new_skills.c", "int MonkDamage("): ["dam += monk_damage_bonus(skl_lvl);"],
    ("new_skills.c", "int MonkNumberOfAttacks("): ["l = monk_attack_rolls(live_rolls, ch)", "a < monk_attack_roll_limit()", "return monk_attack_count(ch, a);"],
    ("new_skills.c", "void chant_heroism("): ["int duration = heroism_duration(ch);", "affect_timer(ch, heroism_rest(), SKILL_HEROISM)", "number(1, 105) > skl_lvl", "CharWait(ch, heroism_lag());",
                                              "af.modifier = heroism_hitroll(ch);", "af.modifier = heroism_damroll(ch);", "GET_LEVEL(ch) >= heroism_dazzle_level()",
                                              "GET_LEVEL(ch) >= heroism_haste_level()", "GET_LEVEL(ch) >= heroism_blur_level()"],
    ("new_skills.c", "void chant_buddha_palm("): ["affect_timer(ch, buddha_palm_rest(), SKILL_BUDDHA_PALM)", "number(1, 101) > skl_lvl", "CharWait(ch, buddha_palm_failed_lag());",
                                                  "num_tar = buddha_palm_targets(ch);", "dam = buddha_palm_damage(live_rolls, ch);", "CharWait(ch, buddha_palm_lag());"],
    ("new_skills.c", "void chant_quivering_palm("): ["affect_timer(ch, quivering_palm_rest(), SKILL_QUIVERING_PALM)", "number(1, 100) > skl_lvl", "CharWait(ch, quivering_palm_failed_lag());",
                                                     "dam = quivering_palm_damage(ch);", "quivering_palm_anatomy_threshold(ch) > number(0, 100)",
                                                     "dam = quivering_palm_anatomy_damage(dam);", "CharWait(ch, quivering_palm_lag());"],
    ("new_skills.c", "void chant_jin_touch("): ["number(1, 50) > skl_lvl", "CharWait(ch, jin_touch_failed_lag());", "CharWait(ch, jin_touch_lag());",
                                                "affect_timer(ch, jin_touch_rest(), SKILL_JIN_TOUCH)", "dam = jin_touch_damage(live_rolls, ch);",
                                                "dam = jin_touch_rated_damage(dam, skl_lvl);", "skl_lvl >= jin_touch_weaken_rating()", "af.duration = jin_touch_weaken_duration();",
                                                "af.modifier = jin_touch_weaken(live_rolls, ch);"],
    ("new_skills.c", "void chant_regenerate("): ["affect_timer(ch, regenerate_rest(), SKILL_REGENERATE)", "number(1, 100) > GET_CHAR_SKILL(ch, SKILL_REGENERATE)", "CharWait(ch, regenerate_failed_lag());",
                                                 "af.duration = regenerate_duration(ch);", "af.modifier = regenerate_hit_regen(ch);", "CharWait(ch, regenerate_lag());"],
    ("new_skills.c", "void chant_tiger_palm("): ["affect_timer(ch, tiger_palm_rest(), SKILL_TIGER_PALM)", "number(1, 101) > tiger_palm_threshold(ch)",
                                                 "set_short_affected_by(ch, SKILL_TIGER_PALM, tiger_palm_duration(ch));"],
    ("new_skills.c", "void chant_fist_of_dragon("): ["affect_timer(ch, fist_of_dragon_rest(), SKILL_FIST_OF_DRAGON)", "number(1, 101) > skl_lvl",
                                                     "set_short_affected_by(ch, SKILL_FIST_OF_DRAGON, fist_of_dragon_duration(ch, skl_lvl));"],
    ("actoth.c", "void do_rage("): ["number(1, 105) > GET_CHAR_SKILL(ch, SKILL_RAGE)", "CharWait(ch, rage_failed_lag());", "CharWait(ch, rage_lag());", "CharWait(ch, rage_ragelord_lag());",
                                    "dura = rage_duration(ch);", "set_short_affected_by(ch, SKILL_RAGE_REORIENT, rage_rest(dura));"],
    ("bard.c", "void bard_charm("): ["GET_LEVEL(ch) - song_charming_level_gap()", "count_pets(ch) >= song_charming_pet_limit()"],
    ("bard.c", "void bard_sleep("): ["GET_LEVEL(victim) > song_sleep_resisting_level()", "number(1, 280) > GET_C_CHA(ch)", "af.duration = song_sleep_duration(level);"],
    ("falling.c", "ALL"): ["safe_fall_skill ? number(1, 101) : 0"],
    ("magic/magic.c", "void spell_earthquake("): ["GET_CHAR_SKILL(tch, SKILL_SAFE_FALL) >= number(1, 101)"],
}

HARNESS = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "combat/damage.h"
#include "combat/guard.h"
#include "item/objmisc.h"
#include "magic/spells.h"
#include "abilities/abilities.h"
#include <algorithm>
#include <cassert>
#include <climits>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <functional>
#include <map>
#include <sstream>
#include <string>

void randomize(uint64_t seed);

static std::map<int, int> ratings;
int GET_CHAR_SKILL_P(P_char, int skill) { auto it = ratings.find(skill); return it == ratings.end() ? 0 : it->second; }
static std::map<std::string, int> asked;
float get_property(const char *key, double fallback) { asked[key]++; return (float)fallback; }
int get_property(const char *key, int fallback) { asked[key]++; return fallback; }
int STAT_INDEX(int v) { return std::min(51, std::max(0, v / 3)); }
struct dex_app_type dex_app[52];
struct wis_app_type wis_app[52];
float dam_factor[LAST_DF + 1];
float shield_combat_mult = 0.5f, shield_combat_tank_mult = 1.5f;
static int mechanics_race = RACE_HUMAN;
int tutorial_mobile_mechanics_race(P_char) { return mechanics_race; }
int arrow_block_chance(P_char victim);

FUNCTIONS

static int fingerprint() { return number(0, INT_MAX); }

// The original expression and the shared function draw alike, and the value lies in the
// range the facts use (the lowest and highest rolls, in either order).
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
            std::fprintf(stderr, "%s: seed %d gave %d, expected %d in %d..%d\n", name, (int)seed,
                         actual, expected, a, b);
            std::abort();
        }
    }
}
#define SAME(original, shared) \
    same(#shared, [&] { return (int)(original); }, [&](const Rolls &rolls) { return (int)(shared); })

struct Viewer { const char *name; uint m_class; int spec; int race; };
static const Viewer viewers[] = {
    { "warrior", CLASS_WARRIOR, 0, RACE_HUMAN },
    { "guardian", CLASS_WARRIOR, SPEC_GUARDIAN, RACE_HUMAN },
    { "swashbuckler", CLASS_WARRIOR, SPEC_SWASHBUCKLER, RACE_HUMAN },
    { "thief", CLASS_ROGUE, SPEC_THIEF, RACE_HUMAN },
    { "monk", CLASS_MONK, SPEC_WAYOFDRAGON, RACE_HUMAN },
    { "snake monk", CLASS_MONK, SPEC_WAYOFSNAKE, RACE_HUMAN },
    { "berserker", CLASS_BERSERKER, SPEC_RAGELORD, RACE_HUMAN },
    { "avenger", CLASS_AVENGER, 0, RACE_HUMAN },
    { "paladin", CLASS_PALADIN, SPEC_CAVALIER, RACE_HUMAN },
    { "zealot", CLASS_CLERIC, SPEC_ZEALOT, RACE_HUMAN },
    { "scoundrel", CLASS_BARD, SPEC_SCOUNDREL, RACE_HUMAN },
    { "illithid", CLASS_PSIONICIST, 0, RACE_ILLITHID },
    { "thri-kreen", CLASS_RANGER, SPEC_BLADEMASTER, RACE_THRIKREEN },
    { "drow", CLASS_ROGUE, 0, RACE_DROW },
    { "sorcerer", CLASS_SORCERER, 0, RACE_HUMAN },
};

static pc_only_data pc_data;
static char_data viewer(const Viewer &v, int level, int stat = 100) {
    char_data ch{};
    ch.player.m_class = v.m_class;
    ch.player.spec = v.spec;
    ch.player.race = v.race;
    ch.player.level = level;
    ch.points.max_hit = 500;
    ch.points.damroll = 20;
    ch.specials.damage_mod = 1.0;
    ch.only.pc = &pc_data;
    ch.curr_stats.Str = ch.curr_stats.Dex = ch.curr_stats.Agi = ch.curr_stats.Int = stat;
    ch.curr_stats.Pow = ch.curr_stats.Luk = ch.curr_stats.Wis = ch.curr_stats.Cha = stat;
    ch.curr_stats.Con = stat;
    return ch;
}

static void set_ratings(int rating) {
    ratings.clear();
    for (int skill : { SKILLS })
        ratings[skill] = rating;
}

static bool page_failed;
static bool contains(const std::string &text, const std::string &piece) { return text.find(piece) != std::string::npos; }
#define HAS(page, piece)                                                                           \
    do {                                                                                           \
        const std::string text = page(&ch);                                                        \
        if (!contains(text, piece)) {                                                              \
            std::fprintf(stderr, "%s lacks [%s] in:\n%s\n", #page, std::string(piece).c_str(),     \
                         text.c_str());                                                            \
            page_failed = true;                                                                    \
        }                                                                                          \
    } while (0)
#define EXACT(page, whole)                                                                         \
    do {                                                                                           \
        const std::string text = page(&ch);                                                        \
        if (text != whole) {                                                                       \
            std::fprintf(stderr, "%s is not [%s] but:\n%s\n", #page, std::string(whole).c_str(),   \
                         text.c_str());                                                            \
            page_failed = true;                                                                    \
        }                                                                                          \
    } while (0)

struct Page { const char *name; std::string (*facts)(P_char); };
static const Page pages[] = {
PAGES
};

static void sweep_pages() {
    bool bad = false;
    for (const Viewer &v : viewers)
        for (int level = 1; level <= 60; ++level)
            for (int rating : { 0, 1, 19, 20, 50, 90, 100 })
                for (int stat : { 1, 100, 180 }) {
                    char_data ch = viewer(v, level, stat);
                    set_ratings(rating);
                    for (const Page &page : pages) {
                        randomize(7);
                        const int expected = fingerprint();
                        randomize(7);
                        const std::string text = page.facts(&ch);
                        assert(fingerprint() == expected);
                        std::istringstream lines(text);
                        std::string line;
                        while (std::getline(lines, line))
                            if (line.size() > 79 || line.rfind("  ", 0) != 0 || line.find("--") != std::string::npos ||
                                line.find("in -") != std::string::npos || line.find(" -1 in") != std::string::npos) {
                                std::fprintf(stderr, "%s: [%s] %zu\n", page.name, line.c_str(), line.size());
                                bad = true;
                            }
                        assert(text.empty() == false);
                    }
                }
    assert(!bad);
}

static void check_rolls() {
    for (int level : { 1, 10, 30, 50, 56, 60 })
        for (int rating : { 1, 50, 100 })
            for (const Viewer &v : viewers) {
                set_ratings(rating);
                char_data ch = viewer(v, level);
                char_data *c = &ch;
                SAME(4. * dice(2, 4), mangle_damage(rolls));
                SAME(number(0, 3), mangle_disarm_roll(rolls));
                SAME(dice(20, 6), followup_riposte_second_blow(rolls));
                SAME(number(0, 2), disperse_flames_roll(rolls));
                SAME(number(1, 56), disperse_flames_level_roll(rolls));
                SAME(number(0, 10), flame_mastery_roll(rolls));
                SAME(number(1, 56), flame_mastery_level_roll(rolls));
                SAME(number(0, 2), fist_of_dragon_roll(rolls));
                SAME(number(0, 19), tainted_blade_roll(rolls));
                // MAX rolls again above 40, so a value can land below the page's floor.
                for (uint64_t seed = 1; seed <= 40; ++seed) {
                    randomize(seed);
                    const int expected = std::max(40, dice(3, (2 * GET_LEVEL(c)) / 3)), next = fingerprint();
                    randomize(seed);
                    assert(tainted_blade_bleed(live_rolls, c) == expected && fingerprint() == next);
                }
                SAME(number(1, 4), bare_hand_damage(rolls));
                SAME(number(0, 10), dodge_drow_roll(rolls));
                SAME(number(40, MAX(41, GET_CHAR_SKILL(c, SKILL_IMPROVED_SHIELD_COMBAT) *
                                            (int)get_property("skill.improvedShieldCombat.damageMultiplier", 1))),
                     improved_shield_combat_damage(rolls, c));
                SAME(number(0, 3), critical_attack_roll(rolls));
                SAME(number(0, 2), critical_attack_disarm_roll(rolls));
                SAME(number(1, get_property("skill.arcane.block.dam.reduction", .4) *
                                   GET_CHAR_SKILL(c, SKILL_ARCANE_BLOCK)),
                     arcane_block_reduction(rolls, c));
                SAME(number(4, 16) * get_property("archery.enchantArrows.damage.mod", 1), enchant_arrow_damage(rolls));
                SAME(number(0, GET_CHAR_SKILL(c, SKILL_ARCHERY) / 25), archery_skill_damage(rolls, c));
                SAME(number(15, 40), archery_fumble_roll(rolls));
                SAME(number(3, 10), archery_fumble_tenths(rolls));
                SAME(BOUNDED(0, (number(0, 12) - bearhug_pin_bonus(c)), 10), bearhug_free_arms_roll(rolls, bearhug_pin_bonus(c)));
                SAME(number(-20, 20), bearhug_damage_roll(rolls));
                SAME(number(0, 50), devotion_power_roll(rolls));
                SAME(((4 * GET_LEVEL(c)) / number(25, 38)), monk_attack_rolls(rolls, c));
                SAME(dice(GET_LEVEL(c) / 2, 8), buddha_palm_damage(rolls, c));
                SAME((int)(dice(GET_C_DEX(c), 3) + dice(GET_C_AGI(c), 3) + dice(GET_C_WIS(c), 3)) / 4, jin_touch_damage(rolls, c));
                SAME(GET_LEVEL(c) * number(2, 3), jin_touch_weaken(rolls, c));
            }
}

// Moved arithmetic against the form it had in its handler.
static void check_moves() {
    for (const Viewer &v : viewers)
        for (int level : { 1, 7, 30, 51, 56 })
            for (int rating : { 0, 1, 19, 20, 49, 50, 90, 91, 99, 100 })
                for (int stat : { 1, 75, 100, 180 }) {
                    set_ratings(rating);
                    char_data ch = viewer(v, level, stat);
                    char_data *c = &ch;
                    int skl = rating * 3;
                    int expected = skl;
                    expected /= 20;
                    expected = BOUNDED(0, expected, 5);
                    assert(mangle_chance(skl) == expected);
                    double score = rating;
                    if (GET_SPEC(c, CLASS_RANGER, SPEC_BLADEMASTER))
                        score *= 1.05;
                    if (GET_SPEC(c, CLASS_WARRIOR, SPEC_SWASHBUCKLER))
                        score *= 1.10;
                    assert(riposte_specialist_score(c, rating) == score);
                    assert(arcane_riposte_damage(rating, 333.0) == (rating * 333.0) / 100);
                    assert(flame_mastery_damage(c, 333.0) == rating * 333.0 / 80);
                    assert(followup_riposte_threshold(rating) == (double)rating / 3);
                    assert(blindfighting_to_hit_penalty(c) == 40 * (120 - rating) / 100);
                    assert(blindfighting_ac_penalty(c) == (int)(40 * (120 - rating) / 100));
                    assert(parry_blind_score(200, rating) == (int)(rating > 0 ? (200 * (rating / 200.0)) : (200 * 0.05)));
                    assert(weapon_check_skill(c, rating) == BOUNDED(level / 2, rating, 95));
                    assert(weapon_critical_check(c, rating) == rating + stat / 4);
                    assert(weapon_fumble_check(c, rating) == rating + stat / 2);
                    assert(quick_step_miss_threshold(c) == level / 5 + STAT_INDEX(stat));
                    assert(devastating_critical_damage(333.5, c) == (int)(333.5 * (300 + rating) / 150));
                    assert(vicious_attack_threshold(c) == 0.1 * rating);
                    assert(vicious_strike_bonus_damage(c) == static_cast<double>(1.050f) * rating);
                    assert(dodge_monk_chance(rating) == (int)(rating * 1.20));
                    assert(shield_block_monk_score(rating) == (int)(rating * 1.75));
                    assert(expert_parry_score(333, rating) == (int)(333 * (1 + rating / 400.0)));
                    assert(four_hand_threshold(c) == rating / 2 + 50 && four_hand_late_threshold(c) == rating / 2 + 45);
                    assert(ship_damage_control_reduction(333, rating) == (float)(333 * (4.0 + (float)rating / 5.0) / 100.0));
                    assert(jin_touch_rated_damage(333, rating) ==
                           (rating <= 80 ? (int)(0.4 * 333) : rating <= 90 ? (int)(0.6 * 333) : 333) / 2);
                    assert(song_sleep_duration(level) == ((4 + level) / 10 > 1 ? (4 + level) / 10 - 1 : 1));
                    assert(bearhug_base_damage(c, 100) ==
                           BOUNDED(40, (int)(level + (3 * (int)(stat - 100)) * 1.00f * ((float)rating / 100)), 300));
                    int value = 40;
                    value += (int)((float)value * (float)rating * shield_combat_mult) / 100;
                    if (GET_CLASS(c, CLASS_PALADIN | CLASS_ANTIPALADIN | CLASS_MERCENARY) || GET_SPEC(c, CLASS_WARRIOR, SPEC_GUARDIAN) ||
                        GET_SPEC(c, CLASS_WARRIOR, SPEC_SWASHBUCKLER))
                        value *= shield_combat_tank_mult;
                    assert(shield_combat_value(c, 40) == value);
                    int toughness = rating;
                    if (toughness > 0 && !GET_CLASS(c, CLASS_MONK))
                        toughness = static_cast<double>(toughness) * 0.5f * (GET_CLASS(c, CLASS_WARRIOR | CLASS_PALADIN | CLASS_ANTIPALADIN | CLASS_MERCENARY) ? 2. : 1.);
                    else if (toughness < 50)
                        toughness = ((float)toughness * 0.8f);
                    else if (toughness <= 90)
                        toughness = ((float)toughness * 1.0f);
                    else
                        toughness = ((float)toughness * 1.25f);
                    assert(toughness_hit_points(c, rating) == toughness);
                    for (int a = 0; a < 8; ++a) {
                        const int count = level >= 56 ? BOUNDED(1, a + 2, 7) : level >= 51 ? BOUNDED(1, a + 1, 6) : BOUNDED(1, a, 5);
                        assert(monk_attack_count(c, a) == count);
                    }
                }
}

static void check_pages() {
    dam_factor[DF_DODGE_AGI_MODIFIER] = 1.2f;
    dam_factor[DF_TIGERPALM] = 0.65f;
    dam_factor[DF_RAGED] = 1.2f;
    dam_factor[DF_BERSERKRAGE] = 1.1f;
    set_ratings(100);
    char_data ch = viewer(viewers[0], 56);
    EXACT(one_h_piercing_facts, "  Your rating adds to your chance to hit.\n  Chance of a critical hit: 8 in 100, if it stands\n"
                                "  Chance a critical stands: 72 in 72\n  Chance a fumble is saved: 101 in 101\n");
    EXACT(soul_trap_facts, "  Chance when you kill: 32 in 100\n  Hit points from a kill of your level: 112\n"
                           "  It can raise your hit points to: 550\n  Chance when a group member without it kills: 19 in 100\n"
                           "");
    EXACT(mangle_facts, "  Chance against an attacker of your dexterity: 5 in 100\n"
                        "    (the attacker's dexterity and expert parry move it; it never tops 5)\n"
                        "  Damage: 8-32, before the attacker's defenses\n  Chance the attacker then loses its weapon: 1 in 4\n"
                        "    (not under combat mind)\n  You must be standing, and the attacker must be a humanoid wielding a weapon\n  it can drop.\n");
    HAS(riposte_facts, "  Chance after you parry: 195-205 in 1000\n");
    HAS(expert_riposte_facts, "  Chance of an extra attack when you riposte your opponent: 99 in 500\n");
    EXACT(followup_riposte_facts, "  Chance of a blow after each riposte: 34 in 101\n  Its damage, from your damroll: 20\n"
                                  "  Chance of a second blow after that: 34 in 101\n  Its damage: 20-120\n  The target's defenses apply after.\n");
    HAS(arcane_riposte_facts, "  Chance to hurl a spell back: 24 in 100\n  Damage to the caster: 100% of the spell's, and you take none\n");
    HAS(disperse_flames_facts, "  Chance to stop a fire spell: 100 in 101, then 1 in 3, then 56 in 56\n");
    HAS(flame_mastery_facts, "  Chance to hurl a fire spell back: 100 in 101, then 1 in 11\n    (and then your level in 56)\n"
                             "  Damage to the caster: 125% of the spell's, and you take none\n"
                             "  Chance your fire shield doesn't worsen a cold spell on you: 99 in 101\n");
    EXACT(blindfighting_facts, "  To-hit against a target you can't see: -8\n  Armor class worse by, while you are blind: 8\n"
                               "  Chance to defend against an attacker you can't see: 33 in 101\n  Your parry score while blind: 50% of normal\n");
    HAS(tainted_blade_facts, "  Chance on each melee hit: 100 in 100, then 1 in 20\n  Raw damage from the blow: 60\n"
                             "  Raw damage each round after it: 40-111\n"
                             "    (a roll above the floor is rolled again, so it can land lower)\n  Rounds, 4 seconds apart: 5\n");
    HAS(holy_blade_facts, "  Only avengers have a holy blade.\n");
    HAS(anatomy_facts, "  Chance of a strike on a melee hit: 4 in 100\n");
    HAS(anatomy_facts, "  Torso: damage: 110% of the hit's\n  Leg: target's vitality: -5\n  Arm: target's damroll for a round: -20\n"
                       "  Wrist: target's hitroll for a round: -25\n  Ear: target deaf for: 40 seconds\n");
    HAS(anatomy_facts, "  Added to your vicious strike score: 50\n");
    EXACT(quick_step_facts, "  Chance to escape a critical hit: 99 in 100\n  Chance it then misses you outright: 41 in 41\n"
                            "    (otherwise it lands as a normal hit)\n  You must be kneeling or better, not stunned and able to move.\n");
    HAS(indomitable_rage_facts, "  Chance to stop a critical hit on you: 50 in 111\n"
                                "    (you gain, 1.25 seconds: hitroll +5, damroll +5, fear saves -5)\n"
                                "  Chance to shrug off fear: 99 in 150\n");
    EXACT(devastating_critical_facts, "  Chance a critical hit is devastating: 99 in 100\n  Its damage: 266%, against 200% for a plain critical\n");
    HAS(critical_attack_facts, "  Chance on a critical hit: 99 in 100\n  One of 4 follow-ups, picked evenly:\n      Vitality the target keeps above 20: 75%\n");
    HAS(critical_attack_facts, "      Knocks its weapon away: 1 in 3\n");
    HAS(vicious_attack_facts, "  Chance of an extra hit on each hit: 10 in 101\n");
    HAS(unarmed_damage_facts, "  Bare-hand damage: 5-8\n");
    HAS(vicious_strike_facts, "  Chance on each melee hit: 149 in 1000\n  Damage added: 105\n");
    HAS(boiling_blood_facts, "  Chance a melee hit only grazes you: 9 in 100\n  A graze's damage: 1, before defenses\n");
    HAS(sidestep_facts, "  Chance your mount sidesteps a blow: 20 in 101\n");
    HAS(dodge_facts, "  Your rating doesn't matter: dodging uses your agility.\n  Your agility score: 120\n");
    HAS(dodge_facts, "  Chance to dodge: 10-50 in 101\n");
    HAS(shield_block_facts, "  Your score against a monk: 175%\n  Your score against a flaying weapon: 150%\n");
    HAS(shield_block_facts, "  Chance a shield stops a fired arrow: 240 in 1600, a quarter of that in melee\n");
    HAS(improved_shield_combat_facts, "  Chance to slam after a block: 99 in 400\n  Damage: 40-100, before the attacker's defenses\n"
                                      "  You must be standing. A slam replaces the block, so that attack carries on.\n");
    HAS(parry_facts, "  Your parry score: 100\n");
    HAS(expert_parry_facts, "  Your parry score: 125% of normal\n  Taken off a mangle's rating against you: 50\n"
                            "  Chance a parry shows as masterful, with no other effect: 99 in 250\n");
    HAS(dual_wield_facts, "  Chance to swing your second weapon each round: 99 in 100\n");
    HAS(improved_twoweapon_facts, "  Chance of another off-hand swing, if you swing your second weapon: 100 in 100\n");
    EXACT(double_attack_facts, "  Chance of an extra attack each round: 100 in 100\n    (monks don't use it)\n"
                               "  Chance of an extra throw when you throw a weapon: 100 in 101\n");
    HAS(quadruple_attack_facts, "  Chance of an extra attack each round: 99 in 100\n");
    HAS(battle_senses_facts, "  Chance when an attack round on you starts: 11 in 100, then 11 in 100\n  While it lasts your dodge never misses: 0.25 seconds\n");
    HAS(shadow_movement_facts, "  Chance at the start of your attack round: 25 in 100\n  Your attacks can't be parried, blocked or dodged for: 1 second\n");
    HAS(double_strike_facts, "  Chance after each attack: 5 in 101\n");
    EXACT(arcane_block_facts, "  Chance to block a spell of more than 15 damage: 166 in 250\n  Less spell damage you take: 1-40%\n"
                              "    (added with your other spell damage modifiers)\n  Not while stunned or unable to move.\n");
    HAS(enchant_arrows_facts, "  Chance each arrow is marked yours: 100 in 100\n  A mark lasts: 5 minutes\n");
    HAS(enchant_arrows_facts, "      Fire or cold: 41 in 121\n      Lightning: 21 in 101\n      Acid: 21 in 111\n      Their damage: 4-16\n");
    HAS(enchant_arrows_facts, "      Major paralysis at your level: 1 in 101\n");
    EXACT(point_blank_shot_facts, "  Chance to fire while fighting: 100 in 130\n  Your lag if you can't: 2 seconds\n");
    HAS(archery_facts, "  Your rating limits your speed to: 200\n    (your weapon and dexterity can limit it more)\n  Speed for each arrow in a volley: 30\n"
                       "  To-hit skill in the target's room: 70\n  To-hit skill one room away: 60\n  Extra damage per arrow: 0-4\n");
    EXACT(indirect_shot_facts, "  Chance a shot over a wall can hit: 100 in 130\n");
    EXACT(cursed_arrows_facts, "  Chance an arrow returns to your quiver: 50 in 100\n");
    EXACT(critical_shot_facts, "  Chance on each arrow that hits: 100 in 3000\n  Damage: 150% of the arrow's\n");
    EXACT(shadow_archery_facts, "  Chance to fire from hiding without showing yourself: 100 in 100\n  Chance to stay hidden after that: 49 in 105\n");
    HAS(bearhug_facts, "  Chance: 99 in 101\n  Chance it also pins the arms, leaving the target unable to speak: 11 in 13\n"
                       "  The hold lasts: 12 seconds\n  Your lag when it takes: 11.25 seconds\n  Target's lag: 8 seconds\n"
                       "  Your lag when the target slips away: 12 seconds\n  Damage every 2 seconds at equal strength: 36-76\n");
    HAS(bearhug_facts, "  Before you can grapple again: 15 seconds\n");
    HAS(guard_facts, "  Chance to step in: 96 in 101 at equal agility\n    (the attacker's agility and sneaking, and luck, move it; it stays 5-95)\n"
                     "  Most agility can move it: 5\n  Before you can step in again: 4 seconds\n  People you can guard at once: 1\n");
    EXACT(ship_damage_control_facts, "  Less damage to your hull and sails, aboard your own ship: 24%\n"
                                     "    (never below 1; a fraction of a point is a roll to remove one more)\n");
    HAS(shield_combat_facts, "  Your shield's armor value: 150%\n");
    EXACT(toughness_facts, "  Hit points: +100\n");
    EXACT(epic_strength_facts, "  Your maximum strength: +10\n");
    EXACT(epic_luck_facts, "  Your maximum luck: +10\n");
    HAS(devotion_facts, "  Chance a cast spell stays ready for you: 9 in 101\n  Chance a harming or holy attack spell casts twice: 6 in 51\n"
                        "  The extra cast's level: 10-60\n");
    EXACT(rage_facts, "  Chance: 100 in 105\n  Duration: 16 seconds\n  Your melee damage: 120% of normal\n  Before you can rage again: 18.5 seconds\n"
                      "  Your lag: 6 seconds\n  Your lag if you fail: 8 seconds\n  Spell damage added while you rage: +10%\n"
                      "  It needs berserk. You can't dodge, block or parry anyone but your opponent.\n");
    HAS(song_charming_facts, "  Highest level you can charm: 50\n  Most pets: 3\n");
    HAS(song_sleep_facts, "  Duration at song level 56: 5-6 game hours (6.25-7.5 minutes)\n  Chance against a target above level 45: 100 in 280, then its save\n");
    EXACT(safe_fall_facts, "  Chance to halve a fall's damage: 99 in 101\n  Chance an earthquake that drops you lands you on your feet: 100 in 101\n");

    ch = viewer(viewers[0], 5); // a low-level character: no impossible thresholds
    HAS(song_charming_facts, "  You are too low in level to charm anything yet.\n");
    set_ratings(30);
    HAS(archery_facts, "  Chance a hit loses damage: 10 in 26, leaving 30-100%\n");
    set_ratings(100);
    HAS(devastating_critical_facts, "  Its damage: 266%");
    ch = viewer(viewers[4], 56); // way of the dragon monk
    EXACT(heroism_facts, "  Chance: 100 in 105\n  Duration: 16-17 game hours (20-21.25 minutes)\n  Hitroll: +7\n  Damroll: +7\n"
                         "  Before you can chant it again, even after a failure: 120 seconds\n  Your lag: 4 seconds\n"
                         "  It also gives you indomitability, if you lack it.\n  It also hastes you, if you aren't already.\n"
                         "  It also blurs you, if you aren't already.\n  Not under diamond soul.\n"
                         "  Your chant skill has its own roll first, and chanting adds its lag.\n");
    HAS(buddha_palm_facts, "  Chance: 100 in 101\n  Holy damage to each target: 28-224, one roll for all\n  Most targets in the room: 5\n");
    HAS(quivering_palm_facts, "  Chance: 100 in 100\n  Damage: 300, before the target's defenses\n"
                              "  With anatomy, chance of more damage: 15 in 101, for 450\n");
    HAS(jin_touch_facts, "  Chance: 50 in 50\n  Damage: 37-112\n    (past the target's armor and skin spells)\n");
    HAS(jin_touch_facts, "  Target's armor class, on a further roll: +112-168\n");
    assert(jin_touch_facts(&ch).find("even if it's still resting") == std::string::npos);
    HAS(regenerate_facts, "  Chance: 100 in 100\n  Duration: 8-9 game hours (10-11.25 minutes)\n  Hit point regeneration: +5600\n");
    HAS(tiger_palm_facts, "  Chance: 101 in 101\n  Duration: 50 seconds\n  Psionic spell damage you take: 65% of normal, added to other factors\n");
    HAS(fist_of_dragon_facts, "  Chance: 100 in 101\n  Duration: 56 seconds\n  Chance a melee hit ignores armor that helps the target: 1 in 3\n");
    HAS(martial_arts_facts, "  Armor class: -324\n");
    HAS(martial_arts_facts, "  Bare-hand damage added: 9\n");
    HAS(martial_arts_facts, "    (full equipped weight above level * STR / 100 reduces base damage)\n");
    HAS(martial_arts_facts, "  Attacks each round: 2-7\n");
    HAS(martial_arts_facts, "    (sum half of each equipped item's weight, rounded down)\n"
                            "    (lose 1 per full 10 lb above STR / 2; at least 1 remains)\n"
                            "    (weight reduces base attacks before slow and other modifiers)\n"
                            "    (inventory ignored; worn bags include their effective contents)\n");
    HAS(martial_arts_facts, "  Chance to counter a blow: 4-15 in 150\n");
    HAS(martial_arts_facts, "  Chance a knockdown lets you roll back up: 99 in 1000, then 99 in 100\n");
    ch = viewer(viewers[5], 36); // way of the snake
    HAS(heroism_facts, "  It also makes you dazzle, if you don't already.\n");
    ch = viewer(viewers[5], 35);
    assert(!contains(heroism_facts(&ch), "dazzle"));
    ch = viewer(viewers[4], 50);
    assert(!contains(heroism_facts(&ch), "hastes") && !contains(heroism_facts(&ch), "blurs"));
    ch = viewer(viewers[4], 51);
    assert(contains(heroism_facts(&ch), "hastes") && !contains(heroism_facts(&ch), "blurs"));
    ch = viewer(viewers[0], 56);
    EXACT(martial_arts_facts, "  Only monks fight with martial arts.\n");
    EXACT(heroism_facts, "  Only monks can chant heroism.\n");
    ch = viewer(viewers[7], 56); // avenger
    HAS(holy_blade_facts, "  Chance on each melee hit: 100 in 100, then 1 in 20\n");
    HAS(tainted_blade_facts, "  Avengers use holy blade instead.\n");
    ch = viewer(viewers[8], 56); // cavalier
    HAS(guard_facts, "  People you can guard at once: 2\n");
    HAS(parry_facts, "  Your score with a holy sword: 115%\n");
    HAS(shield_combat_facts, "  Your shield's armor value: 225%\n");
    ch = viewer(viewers[2], 56); // swashbuckler
    HAS(parry_facts, "  Your specialization's score: 110%\n");
    HAS(riposte_facts, "  Chance after you parry: 204-215 in 1000\n");
    ch = viewer(viewers[3], 56); // thief
    HAS(one_h_slashing_facts, "    (with a short sword: as a thief, any other blade counts as rating 0)\n");
    ch = viewer(viewers[6], 56); // ragelord
    HAS(rage_facts, "  Your lag: 2 seconds\n");
    ch = viewer(viewers[9], 56); // zealot
    HAS(devotion_facts, "  Chance on a hit to regain a spell: 6 in 100\n");
    HAS(dodge_facts, "  Chance to dodge: 15-55 in 101\n");
    ch = viewer(viewers[12], 56); // thri-kreen
    HAS(dual_wield_facts, "  Chance your third or fourth hand joins a swing: 100 in 100\n  Later in the round: 94 in 100\n");
    HAS(double_attack_facts, "    (monks don't use it; your other hands can join in: see dual wield)\n");
    mechanics_race = RACE_DROW;
    ch = viewer(viewers[13], 56);
    HAS(dodge_facts, "  Chance of a free dodge as a drow, unstunned and lightly loaded: 1 in 11\n");
    mechanics_race = RACE_HUMAN;
    ch = viewer(viewers[11], 56); // illithid psionicist
    HAS(toughness_facts, "  Hit points: +50\n");

    set_ratings(0); // every page must work at rating 0, with no chance the handler refuses
    ch = viewer(viewers[0], 56);
    EXACT(soul_trap_facts, "  You need this skill to trap a soul.\n");
    EXACT(mangle_facts, "  You need a rating of 20 to mangle.\n");
    EXACT(riposte_facts, "  You need this skill for a riposte roll.\n");
    EXACT(expert_riposte_facts, "  You need this skill to riposte expertly.\n");
    EXACT(arcane_block_facts, "  You need this skill to block spells.\n");
    EXACT(improved_shield_combat_facts, "  You need this skill to slam with your shield.\n");
    EXACT(parry_facts, "  You need this skill to parry, or combat mind as a psionicist.\n");
    EXACT(toughness_facts, "  You need this skill to be tougher.\n");
    EXACT(devotion_facts, "  You need this skill to be devoted.\n");
    EXACT(bearhug_facts, "  You need this skill to bearhug.\n");
    EXACT(guard_facts, "  You need this skill to guard someone.\n");
    EXACT(ship_damage_control_facts, "  You need this skill to control ship damage.\n");
    EXACT(safe_fall_facts, "  You need this skill to fall safely.\n");
    HAS(blindfighting_facts, "  Your parry score while blind: 5% of normal\n");
    ch = viewer(viewers[4], 56);
    assert(!contains(martial_arts_facts(&ch), "counter") && contains(martial_arts_facts(&ch), "Attacks each round: 2\n"));
    ch = viewer(viewers[0], 56);
    HAS(dual_wield_facts, "  Without this skill you can't wield a second weapon.\n");
    HAS(shield_block_facts, "  You need this skill to block blows with a shield.\n");
    set_ratings(100);

    // The right property keys, so a stub's fallback can't hide a misspelled one.
    for (const char *key : { "skill.arcane.block.dam.reduction", "damage.modifier.vicious.strike", "archery.hitSkill.percentage", "archery.rangePenalty",
                             "archery.cursedArrows.percentage", "archery.crit.bonus", "archery.speedPerShot", "archery.enchantArrows.damage.mod",
                             "archery.enchantArrows.mark.duration", "grapple.bearhug.duration", "grapple.bearhug.duration.victim", "grapple.bearhug.dmgmod",
                             "grapple.cooldown.timer", "skill.guard.max", "skill.guard.max.multi", "skill.guard.agiDiffMaxBonus", "epic.skill.toughness",
                             "epic.skill.toughness.monk.low", "epic.skill.toughness.monk.medium", "epic.skill.toughness.monk.high",
                             "skill.improvedShieldCombat.damageMultiplier", "timer.secs.monkHeroism", "timer.secs.monkBuddha", "timer.secs.monkQuivering",
                             "timer.secs.monkJintouch", "timer.secs.monkRegenerate", "timer.secs.monkTigerPalm", "timer.secs.monkFistOfDragon", "zealots.memHitChance" })
        if (!asked.count(key)) {
            std::fprintf(stderr, "never asked for %s\n", key);
            std::abort();
        }
}

int main() {
    check_rolls();
    check_moves();
    check_pages();
    assert(!page_failed);
    sweep_pages();
    puts("PASS: skills batch 2 shared rolls match the old code and stay in range, facts never roll");
}
'''


def check_sources():
    for (file, head), calls in HANDLER_CALLS.items():
        text = strip_comments(source(file).read_text())
        if head == "ALL":
            bodies = [text]
        else:
            bodies = function_bodies(text, re.escape(head.split("(")[0].split()[-1]) + r"\s*\(")
            assert bodies, head
        bodies = [re.sub(r"\s+", "", body) for body in bodies]
        for call in calls:
            assert any(re.sub(r"\s+", "", call) in body for body in bodies), f"{head} does not call {call}"
    # A shared number must not linger in its handler beside the call.
    for file, head, old in (("fight.c", "parrySucceed", "reaction * 15"), ("fight.c", "blockSucceed", "reaction * 2"),
                            ("fight.c", "calculate_attacks", "/ 2 + 50"), ("fight.c", "calculate_attacks", "/ 2 + 45"),
                            ("new_skills.c", "chant_jin_touch", "dice("), ("new_skills.c", "chant_buddha_palm", "dice(")):
        bodies = function_bodies(strip_comments(source(file).read_text()), rf"{head}\s*\(")
        assert bodies and all(old not in body for body in bodies), f"{head} still has {old}"
    # Followed branches: each lag sits in its own branch.
    jin = function_bodies(strip_comments(source("new_skills.c").read_text()), r"chant_jin_touch\s*\(")[0]
    assert jin.index("affected_by_skill(ch, SKILL_JIN_TOUCH)") < jin.index("number(1, 50) > skl_lvl") < jin.index("jin_touch_failed_lag") < jin.index("jin_touch_rest") < jin.index("jin_touch_lag"), "jin touch order"
    rage = function_bodies(strip_comments(source("actoth.c").read_text()), r"do_rage\s*\(")[0]
    assert rage.index("rage_failed_lag") < rage.index("notch_skill") < rage.index("rage_lag") < rage.index("rage_ragelord_lag"), "rage order"
    table = strip_comments(source("abilities.c").read_text())
    header = source("abilities.h").read_text()
    for constant, name, _ in SKILLS:
        assert re.search(rf"case {constant}:\s*return {name}_facts;", table), constant
        assert f"std::string {name}_facts(char_data *ch);" in header, name
    # Swim's only rating read is commented out.
    assert "SKILL_SWIM" not in strip_comments(source("specials.c").read_text())
    assert "SKILL_SWIM\n" in (ROOT / "tests/fixtures/ability_coverage_no_numbers.txt").read_text()
    assert "SKILL_SWIM\n" not in (ROOT / "tests/fixtures/ability_coverage_pending.txt").read_text()


def main():
    check_sources()
    functions = [extract_function("utility.c", "int dice(int num, int size)"),
                 extract_function("utility.c", "int BOUNDED(int a, int b, int c)"),
                 extract_function("utility.c", "int GET_CLASS(P_char ch, uint m_class)"),
                 extract_function("utility.c", "int GET_PRIME_CLASS(P_char ch, uint m_class)"),
                 extract_function("utility.c", "int GET_SECONDARY_CLASS(P_char ch, uint m_class)")]
    facts = {}
    for constant, name, file in SKILLS:
        facts.setdefault(file, []).append(name)
    for file in list(SHARED) + ["falling.c"]:
        text = source(file).read_text()
        for name in SHARED.get(file, []):
            match = re.search(rf"^(?:static )?[\w:]+(?: \w+)? \*?{name}\([^;\n]*\)$", text, re.M)
            assert match, name
            functions.append(extract_function(file, match.group(0) + "\n{"))
        for name in facts.get(file, []):
            functions.append(extract_function(file, f"std::string {name}_facts(P_char"))
    pages = ",\n".join(f'    {{ "{name}", {name}_facts }}' for _, name, _ in SKILLS)
    skills = ", ".join(sorted({c for c, _, _ in SKILLS} | {"SKILL_GRAPPLER_COMBAT"}))
    build = ROOT / "bin/tests"
    build.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ability-skills-2-", dir=build) as temporary:
        directory = Path(temporary)
        harness = directory / "skills2.cpp"
        harness.write_text(HARNESS.replace("PAGES", pages).replace("SKILLS", skills).replace("FUNCTIONS", "\n".join(functions)))
        binary = directory / "skills2"
        subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-Wno-unused-function",
                        "-ffunction-sections", "-fdata-sections", "-Wl,--gc-sections",
                        "-fsanitize=address,undefined", "-fno-sanitize-recover=undefined",
                        "-Isrc", "-I/usr/include/mysql", "-I/usr/include/libxml2",
                        str(harness), "src/abilities/abilities.c", "src/core/random.c",
                        "-o", str(binary)], cwd=ROOT, check=True)
        subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    main()
