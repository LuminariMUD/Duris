#!/usr/bin/env python3
"""Shared ability numbers, skills batch 4: the last skills, from tradeskills to monk chants.

Builds src/abilities/abilities.c and the real RNG with this batch's shared and facts
functions, under sanitizers. Each roll keeps its pre-conversion expression below as an
oracle: under the same seeds it must give the same value and leave the RNG at the same
draw, inside the range the facts use. Pages are built for every viewer at every level and
rating: they never roll and every line fits 79 columns. Source checks tie every handler to
its shared functions, and to its branch where it has several.
"""
import re
import subprocess
import tempfile
from pathlib import Path

from _paths import ROOT, extract_function, source
from _source_contract import function_bodies, strip_comments

# File order matters: each file's functions may call those of the files before it.
SHARED = {
    "classes/new_skills.c": """chant_note feign_death_threshold feign_death_rest feign_death_forget_level feign_death_lag feign_death_failed_lag calm_lag diamond_soul_duration diamond_soul_rest diamond_soul_failed_lag diamond_soul_lag diamond_soul_save ki_strike_rest ki_strike_failed_lag ki_strike_fall_lag ki_strike_lag ki_strike_target_lag ki_strike_slow_roll ki_strike_anatomy_bonus ki_strike_slow_duration chant_roll_top chant_lag dragon_punch_size_gap dragon_punch_roll dragon_punch_damage dragon_punch_lag carve_roll appraise_roll appraise_wild_multiple appraise_wild_divisor appraise_miss_side_roll appraise_miss_high_divisor appraise_miss_low_divisor appraise_close_divisor appraise_lag chi_purge_poison_level chi_purge_curse_level chi_purge_blind_level chi_purge_wither_level chi_purge_disease_level chi_purge_failed_lag chi_purge_rest""".split(),
    "classes/avengers.c": """holy_smite_failed_lag holy_smite_lag holy_smite_damage holy_smite_blind_threshold holy_smite_blind_duration""".split(),
    "classes/disguise.c": """disguise_kit_roll disguise_score disguise_failed_lag disguise_size_lag disguise_lag disguise_remove_lag disguise_hit_points""".split(),
    "classes/dreadlord.c": """dread_wrath_ac""".split(),
    "world/limits.c": """improved_endurance_vitality improved_endurance_regen meditate_mana_gain""".split(),
    "cmd/actnew.c": """advanced_meditation_poison_rating advanced_meditation_vitality_lag advanced_meditation_lag meditate_lag""".split(),
    "classes/memorize.c": """scribe_mastery_pages scribe_first_page_wait scribe_page_wait scribe_affect_lag scribe_start_lag scribe_taught_lag scribe_lag_lines""".split(),
    "classes/mount.c": """mount_try mount_defense mount_vitality_cost""".split(),
    "classes/drannak.c": """conjure_minion_life_share""".split(),
    "magic/smagic.c": """summon_beast_life_hit_points greater_beast_life_hit_points summon_beast_life_level greater_beast_life_level""".split(),
    "classes/necromancy.c": """raised_undead_spec_life exhume_rest exhume_lag summon_host_lag exhume_corpse_level""".split(),
    "classes/paladins.c": """cleave_damage cleave_target_rest smite_evil_interval smite_evil_threshold smite_evil_damage""".split(),
    "classes/reavers.c": """ice_reaver_1h_bludgeon_penalty ice_reaver_2h_bludgeon_penalty flame_reaver_2h_penalty""".split(),
    "combat/fight.c": """weapon_check_skill weapon_critical_check weapon_fumble_check weapon_skill_lines reaver_round_line""".split(),
    "classes/salchemist.c": """spellbind_failure_roll spellbind_success_damage_roll spellbind_strong_roll spellbind_condition_loss encrust_proc_roll enchant_norepair_roll spellbind_bonus spellbind_fine_bonus mixpoison_lag mix_start_lag mix_lag mix_potion_threshold mix_bottle_roll mix_ingredients_top encrust_lag fix_repaired_condition fix_failed_damage smelt_risk_roll enchant_circle_limit enchant_platinum enchant_min_condition enchant_lag enchant_fumble_roll enchant_fumble_damage enchant_duration""".split(),
    "economy/tradeskill.c": """fishing_pole_damage_roll tradeskill_vitality_cost fishing_rounds fishing_interval fishing_exp_share fishing_exp_step fishing_exp_floor fishing_exp fishing_exp_memory bandage_fumble_roll bandage_heal bandage_poison_roll bandage_interval bandage_duration bandage_lag""".split(),
    "economy/crafting.c": """crafting_level_gate_multiplier crafting_value_limit crafting_facts""".split(),
    "economy/mining.c": """mine_rounds mine_exp mine_ride_roll mine_rock_roll""".split(),
    "item/salvage.c": """salvage_pieces_roll salvage_recipe_score""".split(),
    "net/listen.c": """listen_range improved_listen_emote_range improved_listen_far_threshold listen_hear_threshold improved_listen_emote_threshold improved_listen_small_threshold""".split(),
    "cmd/actobj.c": """slip_get_threshold""".split(),
    "classes/rogues.c": """slip_fighting_penalty""".split(),
    "cmd/track.c": """improved_track_map_range""".split(),
    "combat/dam_mods.c": """spell_penetration_damage_cut spell_penetration_damage_cut_bonus""".split(),
    "classes/innates.c": """spell_penetration_threshold""".split(),
    "classes/epic_skills.c": """bat_dive_roll bat_agility_roll bat_lag_roll bat_attacker_lag summon_blizzard_damage summon_blizzard_interval summon_blizzard_rest summon_blizzard_duration summon_familiar_rest summon_familiar_hit_points summon_familiar_duration two_weapon_bonus infuse_stop_threshold infuse_rest infuse_lag infuse_wear""".split(),
}

SKILLS = [line.split() for line in """
SKILL_1H_BLUDGEON one_h_bludgeon combat/fight.c
SKILL_2H_BLUDGEON two_h_bludgeon combat/fight.c
SKILL_2H_SLASHING two_h_slashing combat/fight.c
SKILL_APPRAISE appraise classes/new_skills.c
SKILL_BANDAGE bandage economy/tradeskill.c
SKILL_CALM calm classes/new_skills.c
SKILL_CARVE carve classes/new_skills.c
SKILL_CHANT chant classes/new_skills.c
SKILL_CHI_PURGE chi_purge classes/new_skills.c
SKILL_CLEAVE cleave classes/paladins.c
SKILL_CRAFT craft economy/crafting.c
SKILL_DIAMOND_SOUL diamond_soul classes/new_skills.c
SKILL_DISGUISE disguise classes/disguise.c
SKILL_DRAGON_PUNCH dragon_punch classes/new_skills.c
SKILL_DREAD_WRATH dread_wrath classes/dreadlord.c
SKILL_ENCHANT enchant classes/salchemist.c
SKILL_ENCRUST encrust classes/salchemist.c
SKILL_EXHUME exhume classes/necromancy.c
SKILL_FEIGN_DEATH feign_death classes/new_skills.c
SKILL_FISHING fishing economy/tradeskill.c
SKILL_FIX fix classes/salchemist.c
SKILL_FORGE forge economy/crafting.c
SKILL_HOLY_SMITE holy_smite classes/avengers.c
SKILL_IMPROVED_ENDURANCE improved_endurance world/limits.c
SKILL_IMPROVED_LISTEN improved_listen net/listen.c
SKILL_IMPROVED_TRACK improved_track cmd/track.c
SKILL_INFUSE_LIFE infuse_life classes/necromancy.c
SKILL_INFUSE_MAGICAL_DEVICE infuse_magical_device classes/epic_skills.c
SKILL_KI_STRIKE ki_strike classes/new_skills.c
SKILL_LISTEN listen net/listen.c
SKILL_MEDITATE meditate cmd/actnew.c
SKILL_MINE mine economy/mining.c
SKILL_MIX mix classes/salchemist.c
SKILL_MIXPOISON mixpoison classes/salchemist.c
SKILL_MOUNT mount classes/mount.c
SKILL_SALVAGE salvage item/salvage.c
SKILL_SCRIBE scribe classes/memorize.c
SKILL_SCRIBE_MASTERY scribe_mastery classes/memorize.c
SKILL_SLIP slip classes/rogues.c
SKILL_SMELT smelt classes/salchemist.c
SKILL_SMITE_EVIL smite_evil classes/paladins.c
SKILL_SPELLBIND spellbind classes/salchemist.c
SKILL_SPELL_PENETRATION spell_penetration classes/innates.c
SKILL_SUMMON_BLIZZARD summon_blizzard classes/epic_skills.c
SKILL_SUMMON_FAMILIAR summon_familiar classes/epic_skills.c
SKILL_TWOWEAPON two_weapon classes/epic_skills.c
""".strip().splitlines()]

NO_NUMBERS = "SKILL_AERIAL_CASTING SKILL_AERIAL_COMBAT SKILL_EPIC_WARDING_FAITH SKILL_FADE SKILL_MUG SKILL_SPELL_MASTERY".split()

# Each handler's text: the shared calls, with the rolls the pages count written out. A list
# of calls under one key must appear in that order, tying each helper to its branch.
HANDLER_CALLS = {
    ("classes/new_skills.c", "do_feign_death"): ["af.duration = feign_death_rest(ch);", "number(1, 101) < feign_death_threshold(live_rolls, skl_lvl)", "GET_LEVEL(ch) > feign_death_forget_level()",
                                                 "number(1, 101) < feign_death_threshold(live_rolls, skl_lvl)", "CharWait(ch, feign_death_lag());", "CharWait(ch, feign_death_failed_lag());"],
    ("classes/new_skills.c", "chant_calm"): ["number(1, 130) < skl_lvl", "!IS_GREATER_RACE(d) && !IS_ELITE(d)", "CharWait(ch, calm_lag());"],
    ("classes/new_skills.c", "chant_diamond_soul"): ["int duration = diamond_soul_duration(ch);", "affect_timer(ch, diamond_soul_rest(), SKILL_DIAMOND_SOUL)", "affected_by_spell(ch, SKILL_HEROISM)", "number(1, 105) > skl_lvl",
                                                     "CharWait(ch, diamond_soul_failed_lag());", "af.modifier = diamond_soul_save(ch);", "af.modifier = diamond_soul_save(ch);", "CharWait(ch, diamond_soul_lag());"],
    ("classes/new_skills.c", "chant_ki_strike"): ["affect_timer(ch, ki_strike_rest(), SKILL_KI_STRIKE)", "number(1, 100) > skl_lvl", "CharWait(ch, ki_strike_failed_lag());", "CharWait(ch, ki_strike_fall_lag());", "CharWait(ch, ki_strike_lag());",
                                                  "CharWait(vict, ki_strike_target_lag());", "percent += ki_strike_slow_roll(live_rolls);", "percent += ki_strike_anatomy_bonus(ch);", "percent > number(1, 30)", "af.duration = ki_strike_slow_duration();"],
    ("classes/new_skills.c", "do_chant"): ["CharWait(ch, chant_lag());", "number(1, chant_roll_top(ch)) > (skl_lvl + GET_LEVEL(ch))", "chant_chi_purge(GET_LEVEL(ch), ch, NULL, 0, ch, NULL);"],
    ("classes/new_skills.c", "do_dragon_punch"): ["GET_ALT_SIZE(ch) - dragon_punch_size_gap()", "GET_ALT_SIZE(ch) + dragon_punch_size_gap()", "dam = dragon_punch_roll(live_rolls);", "dam = dragon_punch_damage(dam, skl_lvl);", "melee_damage(ch, vict, dam, PHSDAM_TOUCH, &messages);", "CharWait(ch, dragon_punch_lag());"],
    ("classes/new_skills.c", "do_carve"): ["percent = carve_roll(live_rolls);", "percent == 101", "percent > GET_CHAR_SKILL(ch, SKILL_CARVE)"],
    ("classes/new_skills.c", "do_appraise"): ["percent = appraise_roll(live_rolls);", "percent == 101", "appraise_wild_multiple(live_rolls)", "appraise_wild_divisor(live_rolls)", "percent > GET_CHAR_SKILL(ch, SKILL_APPRAISE)", "appraise_miss_side_roll(live_rolls)",
                                              "appraise_miss_high_divisor(live_rolls)", "appraise_miss_low_divisor(live_rolls)", "appraise_close_divisor(live_rolls)", "appraise_close_divisor(live_rolls)", "CharWait(ch, appraise_lag());"],
    ("classes/new_skills.c", "chant_chi_purge"): ["GET_LEVEL(ch) > chi_purge_poison_level()", "GET_LEVEL(ch) > chi_purge_curse_level()", "GET_LEVEL(ch) > chi_purge_blind_level()", "GET_LEVEL(ch) > chi_purge_wither_level()", "GET_LEVEL(ch) > chi_purge_disease_level()",
                                                  "number(1, 100) > GET_CHAR_SKILL(ch, SKILL_CHI_PURGE)", "CharWait(ch, chi_purge_failed_lag());", "affect_timer(ch, chi_purge_rest(), SKILL_CHI_PURGE)"],
    ("classes/avengers.c", "do_holy_smite"): ["GET_ALIGNMENT(vict) > -1", "number(1, 101) > skl_lvl", "CharWait(ch, holy_smite_failed_lag());", "holy_smite_damage(live_rolls, ch, skl_lvl)", "PHSDAM_NOSHIELDS | PHSDAM_NOREDUCE | PHSDAM_NOPOSITION",
                                              "holy_smite_blind_threshold(ch) > number(1, 150) && IS_ALIVE(vict)", "blind(ch, vict, holy_smite_blind_duration(live_rolls));", "CharWait(ch, holy_smite_lag());"],
    ("classes/disguise.c", "disguise_as"): ["int skl_lvl = disguise_score(ch);", "percent = number(1, 101);", "percent += 30;", "percent += 20;", "percent += 30;", "percent += 10;", "percent += 30;", "CharWait(ch, disguise_failed_lag());", "disguise_kit_roll(live_rolls)",
                                            "CharWait(ch, disguise_size_lag());", "CharWait(ch, disguise_size_lag());", "ch->disguise.hit = disguise_hit_points(ch);", "ch->disguise.hit = disguise_hit_points(ch);", "CharWait(ch, disguise_lag());"],
    ("classes/disguise.c", "do_disguise"): ["skl_lvl = disguise_score(ch);", "CharWait(ch, disguise_remove_lag());"],
    ("classes/dreadlord.c", "do_dread_wrath"): ["IS_CONSTRUCT(victim) || IS_AFFECTED4(victim, AFF4_NOFEAR)", "af.modifier = dread_wrath_ac(ch);"],
    ("world/limits.c", "vitality_limit"): ["max += improved_endurance_vitality(endurance);"],
    ("world/limits.c", "move_regen"): ["gain += improved_endurance_regen(endurance);"],
    ("world/limits.c", "mana_regen"): ["IS_AFFECTED(ch, AFF_MEDITATE) ? meditate_mana_gain(ch) :"],
    ("cmd/actnew.c", "do_meditate"): ["GET_POS(ch) != POS_SITTING", "CharWait(ch, meditate_lag());"],
    ("classes/memorize.c", "event_memorize"): ["GET_CHAR_SKILL(ch, SKILL_MEDITATE) < number(0, 100)", "schedule_memorize(ch, time / 2);"],
    ("classes/memorize.c", "calculate_undead_time"): ["GET_CHAR_SKILL(ch, SKILL_MEDITATE) > number(0, 100)"],
    ("classes/memorize.c", "calculate_harpy_time"): ["GET_CHAR_SKILL(ch, SKILL_MEDITATE) < number(0, 100)"],
    ("classes/memorize.c", "GetSpellPages"): ["int mod = scribe_mastery_pages(skill);"],
    ("classes/memorize.c", "AddScribingAffect"): ["CharWait(ch, scribe_affect_lag(ch));"],
    ("classes/memorize.c", "add_scribe_data"): ["add_event(event_scribe, scribe_first_page_wait(ch),"],
    ("classes/memorize.c", "add_scribing"): ["CharWait(ch, scribe_start_lag(ch));", "CharWait(ch, scribe_taught_lag(ch));"],
    ("classes/memorize.c", "event_scribe"): ["add_event(event_scribe, scribe_page_wait(ch),"],
    ("classes/mount.c", "do_mount"): ["int mounttry = mount_try(ch);", "int mountdef = mount_defense(GET_LEVEL(mount));", "movescost = mount_vitality_cost(ch);"],
    ("classes/necromancy.c", "do_exhume"): ["affect_timer(ch, exhume_rest(skl), SKILL_EXHUME)", "CharWait(ch, exhume_lag(skl));", "obj1->value[CORPSE_LEVEL] = exhume_corpse_level(live_rolls, ch);"],
    ("classes/necromancy.c", "do_summon_host"): ["affect_timer(ch, exhume_rest(skl), SKILL_EXHUME)", "CharWait(ch, summon_host_lag(ch));", "obj1->value[CORPSE_LEVEL] = exhume_corpse_level(live_rolls, ch);"],
    ("classes/paladins.c", "cleave"): ["number(5, 100) < GET_CHAR_SKILL(ch, SKILL_CLEAVE)", "int dam = cleave_damage(live_rolls, ch);", "set_short_affected_by(victim, SKILL_CLEAVE, cleave_target_rest());"],
    ("classes/paladins.c", "event_smite_evil"): ["GET_HIT(tch) < 15", "smite_evil_threshold(ch) > number(0, 100)", "damage(ch, tch, smite_evil_damage(live_rolls), SKILL_SMITE_EVIL);", "add_event(event_smite_evil, smite_evil_interval(),"],
    ("account/nanny.c", "ALL"): ["add_event(event_smite_evil, smite_evil_interval(),"],
    ("classes/reavers.c", "apply_reaver_mods"): ["base_combat_round += ice_reaver_1h_bludgeon_penalty();", "base_combat_round += ice_reaver_2h_bludgeon_penalty();", "base_combat_round += flame_reaver_2h_penalty();"],
    ("classes/rogues.c", "do_slip"): ["number(1, 100)", "percent -= slip_fighting_penalty();", "check <= percent"],
    ("cmd/actobj.c", "ALL"): ["number(0, 100) < slip_get_threshold(ch)"],
    ("classes/salchemist.c", "spellbind_committed"): ["const int bonus = spellbind_bonus(context.skill);", "spellbind_fine_bonus(context.skill)"],
    ("classes/salchemist.c", "do_mixpoison"): ["CharWait(ch, mixpoison_lag());", "CharWait(ch, mixpoison_lag());"],
    ("classes/salchemist.c", "do_mix"): ["CharWait(ch, mix_start_lag());", "number(1, 160) < mix_potion_threshold(ch)", "mix_bottle_roll(live_rolls)", "number(0, mix_ingredients_top(live_rolls, ch))", "CharWait(ch, mix_lag());"],
    ("classes/salchemist.c", "do_spellbind"): ["skill < number(10, 140)", "!spellbind_failure_roll(live_rolls)"],
    ("classes/salchemist.c", "do_encrust"): ["number(1, 110) <= skill", "CharWait(ch, encrust_lag());", "CharWait(ch, encrust_lag());"],
    ("classes/salchemist.c", "encrusted_eq_proc"): ["!encrust_proc_roll(live_rolls)"],
    ("classes/salchemist.c", "do_fix"): ["item->condition > 90", "item->condition < 20", "skill > number(0, 105)", "fix_repaired_condition(live_rolls)", "fix_failed_damage(live_rolls)"],
    ("classes/salchemist.c", "do_smelt"): ["!smelt_risk_roll(live_rolls)", "GET_CHAR_SKILL(ch, SKILL_SMELT) < number(0, 99)"],
    ("classes/salchemist.c", "do_enchant"): ["circle > enchant_circle_limit(skill)", "GET_PLATINUM(ch) < enchant_platinum(circle)", "item->condition < enchant_min_condition()", "add_event(event_enchant, enchant_lag(),", "CharWait(ch, enchant_lag());"],
    ("classes/salchemist.c", "event_enchant"): ["!enchant_fumble_roll(live_rolls, skill)", "enchant_fumble_damage(live_rolls)", "!enchant_norepair_roll(live_rolls)", "set_obj_affected(item, enchant_duration(skill), SKILL_ENCHANT, spll);"],
    ("economy/tradeskill.c", "do_fish"): ["data.counter = fishing_rounds(ch);", "add_event(event_fish_check, fishing_interval(),"],
    ("economy/tradeskill.c", "event_fish_check"): ["GET_CHAR_SKILL(ch, SKILL_FISHING) < number(1, 125)", "af.modifier = fishing_exp_share();", "af.duration = fishing_exp_memory();", "afp->modifier -= fishing_exp_step();", "MAX(afp->modifier, fishing_exp_floor())", "afp->duration = fishing_exp_memory();",
                                                   "fishing_exp(GET_CHAR_SKILL(ch, SKILL_FISHING), afp->modifier)", "GET_VITALITY(ch) < 10", "tradeskill_vitality_cost(live_rolls, GET_CHAR_SKILL(ch, SKILL_FISHING))", "add_event(event_fish_check, fishing_interval(),"],
    ("economy/tradeskill.c", "event_bandage_check"): ["GET_VITALITY(ch) < 10", "!bandage_fumble_roll(live_rolls, (GET_CHAR_SKILL(ch, SKILL_BANDAGE)))", "healed = bandage_heal(mdata->maxheal, GET_CHAR_SKILL(ch, SKILL_BANDAGE));", "GET_MAX_HIT(victim) * 0.875", "!bandage_poison_roll(live_rolls)",
                                                      "number(0, 100) < GET_CHAR_SKILL(ch, SKILL_BANDAGE)", "tradeskill_vitality_cost(live_rolls, GET_CHAR_SKILL(ch, SKILL_BANDAGE))", "add_event(event_bandage_check, bandage_interval(),"],
    ("economy/tradeskill.c", "do_bandage"): ["add_event(event_bandage_check, bandage_interval(),", "af.duration = bandage_duration();", "CharWait(ch, bandage_lag());"],
    ("economy/crafting.c", "ALL"): ["iVal > crafting_value_limit(ch) ||"],
    ("economy/mining.c", "mine"): ["data.counter = mine_rounds(obj->value[2], GET_CHAR_SKILL(ch, SKILL_MINE));"],
    ("economy/mining.c", "event_mine_check"): ["mine_exp(GET_CHAR_SKILL(ch, SKILL_MINE))", "GET_VITALITY(ch) < 10", "!mine_ride_roll(live_rolls, GET_CHAR_SKILL(ch, SKILL_MINE))", "!mine_rock_roll(live_rolls, GET_CHAR_SKILL(ch, SKILL_MINE))", "tradeskill_vitality_cost(live_rolls, GET_CHAR_SKILL(ch, SKILL_MINE))"],
    ("item/salvage.c", "do_salvage"): ["GET_CHAR_SKILL(ch, SKILL_SALVAGE) < number(1, 105)", "!salvage_pieces_roll(live_rolls)", "playerroll = salvage_recipe_score(ch);"],
    ("net/listen.c", "listen_say"): ["range = listen_range(iskl);", "improved_listen_far_threshold(iskl) < number(0, 100)", "listen_hear_threshold(tch) > (number(25, 45))", "GET_CHAR_SKILL(tch, SKILL_LISTEN) > number(15, 35)"],
    ("net/listen.c", "listen_gsay"): ["range = listen_range(iskl);", "improved_listen_far_threshold(iskl) < number(0, 100)", "listen_hear_threshold(tch) > (number(25, 45))", "GET_CHAR_SKILL(tch, SKILL_LISTEN) > number(20, 40)"],
    ("net/listen.c", "listen_emote"): ["irange = improved_listen_emote_range();", "(improved_listen_far_threshold(iskl)) < number(0, 100)", "improved_listen_emote_threshold(iskl) > (number(15, 55))", "number(70, 90) > improved_listen_small_threshold(iskl)"],
    ("net/listen.c", "muddle_listened_string"): ["listen_hear_threshold(vict) < (number(25, 75) + (extr_depth * 10))"],
    ("cmd/actoth.c", "do_listen"): ["percent = number(1, 101);", "percent = (int)(percent * 0.9);", "GET_CHAR_SKILL(ch, SKILL_LISTEN) < percent"],
    ("world/map.c", "whats_in_maproom"): ["distance <= improved_track_map_range(ch)", "distance <= improved_track_map_range(ch)", "GET_CHAR_SKILL(ch, SKILL_IMPROVED_TRACK) > number(50, 80)", "GET_CHAR_SKILL(ch, SKILL_IMPROVED_TRACK) >= number(80, 100)"],
    ("cmd/track.c", "ALL"): ["epic_skill >= number(50, 70)", "epic_skill >= number(90, 100)", "skill > percent || forest_check"],
    ("combat/dam_mods.c", "ALL"): ["int damageReductionMod = spell_penetration_damage_cut(live_rolls);", "-(spell_penetration_damage_cut_bonus() / 100.0)"],
    ("classes/innates.c", "resists_spell"): ["number(0, 110) < spell_penetration_threshold(skill) && caster->in_room == victim->in_room"],
    ("classes/epic_skills.c", "event_blizzard"): ["spell_damage(ch, victim, summon_blizzard_damage(live_rolls), SPLDAM_COLD, SPLDAM_NOSHRUG | SPLDAM_NODEFLECT,", "add_event(event_blizzard, summon_blizzard_interval(live_rolls, count),"],
    ("classes/epic_skills.c", "do_summon_blizzard"): ["affect_timer(ch, summon_blizzard_rest(), SKILL_SUMMON_BLIZZARD)", "raf.duration = summon_blizzard_duration(GET_CHAR_SKILL(ch, SKILL_SUMMON_BLIZZARD));"],
    ("classes/epic_skills.c", "do_summon_familiar"): ["affect_timer(ch, summon_familiar_rest(ch_skill_level), SKILL_SUMMON_FAMILIAR)", "int hits = GET_HIT(mob) + summon_familiar_hit_points(ch_skill_level);", "setup_pet(mob, ch, summon_familiar_duration(), PET_NOCASH);"],
    ("classes/epic_skills.c", "two_weapon_check"): ["const int bonus = two_weapon_bonus(twoskl);", "ch->points.hitroll += bonus;", "ch->points.damroll += bonus;"],
    ("classes/epic_skills.c", "do_infuse"): ["(skill < 40)", "device->value[7] >= 2", "number(0, 100) < infuse_stop_threshold(check, skill)", "af.duration = infuse_rest();", "device->value[7] += infuse_wear(skill);", "CharWait(ch, infuse_lag());"],
    ("classes/drannak.c", "do_conjure"): ["conjure_minion_life_share(GET_CHAR_SKILL(ch, SKILL_INFUSE_LIFE))"],
    ("magic/smagic.c", "summon_beast_common"): ["greater_beast_life_hit_points(life)", "summon_beast_life_hit_points(life)", "greater_beast_life_hit_points(life)", "summon_beast_life_hit_points(life)", "greater_beast_life_level(live_rolls, life)", "summon_beast_life_level(live_rolls, life)"],
}

STALE = (("classes/new_skills.c", "do_dragon_punch", "dice("), ("classes/avengers.c", "do_holy_smite", "dice("),
         ("classes/paladins.c", "cleave", "dice("), ("economy/tradeskill.c", "event_bandage_check", "? 3 : 2"),
         ("economy/tradeskill.c", "event_fish_check", "? 3 : 2"), ("economy/mining.c", "event_mine_check", "? 3 : 2"),
         ("classes/epic_skills.c", "two_weapon_check", "points.hitroll += 1"), ("classes/necromancy.c", "do_exhume", "MIN(50"))

HARNESS = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "combat/damage.h"
#include "magic/spells.h"
#include "abilities/abilities.h"
#include "classes/salchemist.h"
#include "classes/epic_skills.h"
#include <algorithm>
#include <cassert>
#include <climits>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <map>
#include <sstream>
#include <string>

void randomize(uint64_t seed);

static std::map<int, int> ratings;
int GET_CHAR_SKILL_P(P_char, int skill) { auto it = ratings.find(skill); return it == ratings.end() ? 0 : it->second; }
static std::map<std::string, int> asked;
static std::map<std::string, float> live_properties;
float get_property(const char *key, double fallback) { asked[key]++; auto it = live_properties.find(key); return it == live_properties.end() ? (float)fallback : it->second; }
int get_property(const char *key, int fallback) { asked[key]++; auto it = live_properties.find(key); return it == live_properties.end() ? fallback : (int)it->second; }
static bool innate_on, spell_on, tools_prevent = true;
bool has_innate(P_char, int) { return innate_on; }
bool affected_by_spell(P_char, int) { return spell_on; }
int is_wearing_necroplasm(P_char) { return 0; }
bool crafting_scientific_tools_prevent_breakage(void) { return tools_prevent; }
static int crafting_level_gate = 3;
struct potion potion_data[] = { { SPELL_ENTANGLE, 41, { 0 }, 1 }, { SPELL_GREASE, 11, { 0 }, 2 }, { 0, 0, { 0 }, 0 } };
struct poison { int poison_type; int level_required; int skill_required; int ingredients[MAX_INGREDIENTS + 1]; int vnum; };
struct poison poison_data[] = { { 1, 51, 100, { 0 }, 1 }, { 2, 21, 30, { 0 }, 2 }, { 0, 0, 0, { 0 }, 0 } };

FUNCTIONS

static int fingerprint() { return number(0, INT_MAX); }

// The original expression and the shared function draw alike, and the value lies in the
// range the facts use (the lowest and highest rolls, in either order).
template <typename Original, typename Shared>
static void same(const char *name, Original original, Shared shared, int slack = 0) {
    const int a = shared(lowest_rolls), b = shared(highest_rolls);
    for (uint64_t seed = 1; seed <= 40; ++seed) {
        randomize(seed);
        const int expected = original(), expected_next = fingerprint();
        randomize(seed);
        const int actual = shared(live_rolls), actual_next = fingerprint();
        if (actual != expected || actual_next != expected_next ||
            actual < std::min(a, b) || actual > std::max(a, b) + slack) {
            std::fprintf(stderr, "%s: seed %d gave %d, expected %d in %d..%d\n", name, (int)seed,
                         actual, expected, a, b);
            std::abort();
        }
    }
}
#define SAME(original, shared) \
    same(#shared, [&] { return (int)(original); }, [&](const Rolls &rolls) { return (int)(shared); })
#define SAME_SLACK(original, shared, slack) \
    same(#shared, [&] { return (int)(original); }, [&](const Rolls &rolls) { return (int)(shared); }, slack)

struct Viewer { const char *name; uint m_class; int spec; int race; };
static const Viewer viewers[] = {
    { "warrior", CLASS_WARRIOR, 0, RACE_HUMAN },
    { "monk", CLASS_MONK, SPEC_WAYOFDRAGON, RACE_HUMAN },
    { "necromancer", CLASS_NECROMANCER, SPEC_REAPER, RACE_HUMAN },
    { "theurgist", CLASS_THEURGIST, SPEC_THAUMATURGE, RACE_HUMAN },
    { "ice reaver", CLASS_REAVER, SPEC_ICE_REAVER, RACE_HUMAN },
    { "flame reaver", CLASS_REAVER, SPEC_FLAME_REAVER, RACE_HUMAN },
    { "paladin", CLASS_PALADIN, SPEC_CRUSADER, RACE_HUMAN },
    { "thief", CLASS_ROGUE, SPEC_THIEF, RACE_HUMAN },
    { "alchemist", CLASS_ALCHEMIST, 0, RACE_HUMAN },
    { "harpy", CLASS_SORCERER, 0, RACE_HARPY },
    { "warlock", CLASS_WARLOCK, 0, RACE_HUMAN },
};

static pc_only_data pc_data;
static char_data viewer(const Viewer &v, int level, int stat = 100) {
    char_data ch{};
    ch.player.m_class = v.m_class;
    ch.player.spec = v.spec;
    ch.player.race = v.race;
    ch.player.level = level;
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

// Every page for every viewer, level and rating: no rolls, nothing over 79 columns, and a
// rating of 0 says so.
static void sweep_pages() {
    bool bad = false;
    for (const Viewer &v : viewers)
        for (int level : { 1, 2, 3, 10, 15, 20, 30, 40, 41, 46, 47, 50, 51, 55, 56, 57, 60 })
            for (int rating : { 0, 1, 2, 9, 10, 11, 19, 20, 33, 40, 45, 50, 60, 70, 80, 95, 99, 100 })
                for (int stat : { 1, 100, 200 })
                    for (bool flag : { false, true }) {
                        innate_on = spell_on = flag;
                        set_ratings(rating);
                        char_data ch = viewer(v, level, stat);
                        for (const Page &page : pages) {
                            randomize(7);
                            const int expected = fingerprint();
                            randomize(7);
                            const std::string text = page.facts(&ch);
                            assert(fingerprint() == expected);
                            assert(!text.empty());
                            std::istringstream lines(text);
                            std::string line;
                            while (std::getline(lines, line))
                                if (line.size() > 79 || line.rfind("  ", 0) != 0 || line.find("--") != std::string::npos ||
                                    line.find("in -") != std::string::npos || line.find(" -1 in") != std::string::npos ||
                                    line.find(": ,") != std::string::npos) {
                                    std::fprintf(stderr, "%s: [%s] %zu\n", page.name, line.c_str(), line.size());
                                    bad = true;
                                }
                        }
                    }
    innate_on = spell_on = false;
    assert(!bad);
}

// Bandage destroys on zero from number(number(0, 3), rating): walk the rolls exactly.
static void check_bandage_odds() {
    for (int rating = 1; rating <= 100; ++rating) {
        double chance = 0;
        for (int first = 0; first <= 3; ++first) {
            const int low = std::min(first, rating), high = std::max(first, rating);
            if (low == 0)
                chance += 0.25 / (high - low + 1);
        }
        assert(std::fabs(chance - 1.0 / (4 * (rating + 1))) < 1e-12);
    }
}

static void check_rolls() {
    for (const Viewer &v : viewers)
        for (int level : { 1, 10, 30, 47, 50, 56, 60 }) {
            char_data subject = viewer(v, level);
            P_char ch = &subject;
            for (int rating : { 1, 9, 40, 80, 100 }) {
                set_ratings(rating);
                SAME(rating * number(2, 5) / 2, feign_death_threshold(rolls, rating));
                SAME(dice(60, 8), dragon_punch_roll(rolls));
                SAME(number(0, 4), spellbind_failure_roll(rolls));
                SAME(number(0, 2), spellbind_success_damage_roll(rolls));
                SAME(number(0, 40), spellbind_strong_roll(rolls));
                SAME(number(1, 20), spellbind_condition_loss(rolls));
                SAME(number(0, 29), encrust_proc_roll(rolls));
                SAME(number(0, 5), enchant_norepair_roll(rolls));
                SAME(number(0, 2), fishing_pole_damage_roll(rolls));
                SAME(number(0, 2), bat_dive_roll(rolls));
                SAME(number(0, 150), bat_agility_roll(rolls));
                SAME(number(0, 2), bat_lag_roll(rolls));
                SAME(number(0, 1), disguise_kit_roll(rolls));
                SAME((dice(60, 8)) * MAX(30, rating) / 100, dragon_punch_damage(dragon_punch_roll(rolls), rating));
                SAME(dice((GET_LEVEL(ch) / 2), (rating / 10)) / 2, holy_smite_damage(rolls, ch, rating));
                SAME(number(0, GET_CHAR_SKILL(ch, SKILL_MIX) / 10 + number(1, 2)), rolls.number(0, mix_ingredients_top(rolls, ch)));
                SAME(rating / 10 + number(1, 2), mix_ingredients_top(rolls, ch));
                SAME((number(0, 100) > rating) ? 3 : 2, tradeskill_vitality_cost(rolls, rating));
                SAME(number(0, rating - 10), enchant_fumble_roll(rolls, rating));
                SAME(number(0, rating / 20), mine_ride_roll(rolls, rating));
                SAME(number(0, (rating * 2)), mine_rock_roll(rolls, rating));
                // Both rolls of the nested bandage fumble: the bounds don't hold it, the draws do.
                for (uint64_t seed = 1; seed <= 40; ++seed) {
                    randomize(seed);
                    const int expected = number(number(0, 3), rating), expected_next = fingerprint();
                    randomize(seed);
                    const int actual = bandage_fumble_roll(live_rolls, rating), actual_next = fingerprint();
                    assert(actual == expected && actual_next == expected_next);
                }
                SAME(((int)(rating / 20) + number(0, 2)), summon_beast_life_level(rolls, rating));
                SAME(((int)(rating / 15) + number(0, 2)), greater_beast_life_level(rolls, rating));
            }
            // MIN rolls again, so a level near the cap can land above the page's top.
            SAME_SLACK(MIN(50, GET_LEVEL(ch) + number(0, 8) - 4), exhume_corpse_level(rolls, ch), 4);
        }
    SAME(number(-5, 20), ki_strike_slow_roll(rolls));
    SAME(number(1, 101), carve_roll(rolls));
    SAME(number(1, 101), appraise_roll(rolls));
    SAME(number(1, 3), appraise_wild_multiple(rolls));
    SAME(number(2, 4), appraise_wild_divisor(rolls));
    SAME(number(0, 2), appraise_miss_side_roll(rolls));
    SAME(number(1, 15), appraise_miss_high_divisor(rolls));
    SAME(number(2, 15), appraise_miss_low_divisor(rolls));
    SAME(number(80, 120), appraise_close_divisor(rolls));
    SAME(number(8, 10) * WAIT_SEC, holy_smite_blind_duration(rolls));
    SAME(number(5, 25), smite_evil_damage(rolls));
    SAME(number(0, 5), mix_bottle_roll(rolls));
    SAME(number(2, 30), fix_failed_damage(rolls));
    SAME(number(0, 2), smelt_risk_roll(rolls));
    SAME(number(5, 10), enchant_fumble_damage(rolls));
    SAME(number(0, 4), bandage_poison_roll(rolls));
    SAME(number(0, 2), salvage_pieces_roll(rolls));
    SAME(number(20, 70), spell_penetration_damage_cut(rolls));
    SAME(70 + dice(4, 6), summon_blizzard_damage(rolls));
    for (int count : { 1, 2, 5 })
        SAME(number(20, 30) / count, summon_blizzard_interval(rolls, count));
    // A subtracted roll: the highest roll gives the lowest value.
    same("fix_repaired_condition", [&] { return 100 - number(0, 10); }, [&](const Rolls &rolls) { return fix_repaired_condition(rolls); });
    for (int level : { 1, 10, 30, 47, 56 }) {
        char_data subject = viewer(viewers[8], level);
        P_char ch = &subject;
        for (int rating : { 1, 50, 100 }) {
            ratings[SKILL_CLEAVE] = rating;
            SAME(dice(GET_LEVEL(ch) / 2, 10), cleave_damage(rolls, ch));
        }
    }
    check_bandage_odds();
}

// The old if-chains and arithmetic over their whole range.
static void check_moves() {
    for (int twoskl = 0; twoskl <= 110; ++twoskl) {
        int old = 0;
        if (twoskl > 0 && twoskl < 20) old = 1;
        else if (twoskl >= 20 && twoskl < 40) old = 2;
        else if (twoskl >= 40 && twoskl < 60) old = 3;
        else if (twoskl >= 60 && twoskl < 80) old = 4;
        else if (twoskl >= 80 && twoskl < 100) old = 5;
        else if (twoskl == 100) old = 6;
        assert(two_weapon_bonus(twoskl) == old);
    }
    for (int skill : { 0, 1, 69, 70, 100 })
        assert(infuse_wear(skill) == (skill >= 70 ? 1 : 2));
    for (int rating = 0; rating <= 100; ++rating) {
        assert(improved_endurance_vitality(rating) == rating / 2 && improved_endurance_regen(rating) == rating / 10);
        assert(mine_rounds(30, rating) == (30 * 200) / (100 + rating));
        assert(bandage_heal(100, rating) == 100 / 20 + rating / 7);
        assert(fishing_exp(rating, 500) == (rating * 500) / 100);
        assert(summon_blizzard_duration(rating) == 3 * PULSE_VIOLENCE + (rating * PULSE_VIOLENCE) / 30);
        assert(summon_familiar_rest(rating) == (10 + 10 - 2 * (rating / 20)) * WAIT_MIN);
        assert(exhume_rest(rating) == (10 * WAIT_MIN * (150 - rating)) / 100);
        assert(exhume_lag(rating) == 6 * WAIT_SEC - (rating / 10));
        ratings[SKILL_EXHUME] = rating;
        char_data subject = viewer(viewers[2], 56);
        assert(summon_host_lag(&subject) == 24 - (rating / 10));
        // The handler's mana arithmetic.
        const int gain = (GET_C_POW(&subject) + GET_C_INT(&subject)) / .2;
        assert((int)meditate_mana_gain(&subject) == gain);
    }
    // Spell page ranges use the handler's own property reads.
    assert(enchant_duration(100) == (100 / 2) * WAIT_MIN);
}

static void check_pages() {
    set_ratings(100);
    char_data ch = viewer(viewers[1], 56);
    EXACT(calm_facts, "  Chance for each fighter in the room: 99 in 130\n"
                      "  A calmed fighter, you included, stops fighting and forgets its grudges.\n"
                      "  Not on elites or greater races.\n"
                      "  Your lag: 4 seconds\n"
                      "  Your chant skill has its own roll first, and chanting adds its lag.\n");
    EXACT(chant_facts, "  Chance: 113 in 113\n"
                       "  Your lag, even if you fail: 2.25 seconds\n"
                       "  Each chant adds its own roll and lag after this one.\n");
    EXACT(chi_purge_facts, "  Chance: 100 in 100\n"
                           "  Cures on you: poison, curses, blindness, withering, disease\n"
                           "  Before you can chant it again, if it works: 25 seconds\n"
                           "  Your lag if you fail: 8 seconds\n"
                           "  Your chant skill has its own roll first, and chanting adds its lag.\n");
    EXACT(diamond_soul_facts, "  Chance: 100 in 105\n"
                              "  Duration: 5-6 game hours (6.25-7.5 minutes)\n"
                              "  Saving throws against spells and paralysis: -7 (lower is better)\n"
                              "  Before you can chant it again, even after a failure: 120 seconds\n"
                              "  Your lag: 4 seconds\n"
                              "  Your lag if you fail: 4 seconds\n"
                              "  Not under heroism.\n"
                              "  Your chant skill has its own roll first, and chanting adds its lag.\n");
    EXACT(dragon_punch_facts, "  Damage: 60-480 at your rating\n"
                              "    (a helpless target, such as a stunned or sleeping one, counts it higher)\n"
                              "  It always lands. The target's defenses apply to the damage after.\n"
                              "  Your lag: 8 seconds\n"
                              "  Sizes the target may differ from yours: 1\n");
    EXACT(carve_facts, "  Chance of a clean cut: 100 in 101\n"
                       "  Chance you ruin every part: 1 in 101\n"
                       "  A failed cut still costs that part.\n"
                       "  It takes a humanoid corpse, and a wielded blade, dagger or knife.\n");
    EXACT(appraise_facts, "  Chance of a close estimate: 100 in 101\n"
                          "  A close estimate is off by 1/120 to 1/80 of the value, either way.\n"
                          "  A miss reads high: 2 in 3, by up to 1/1 of the value\n"
                          "  Otherwise it reads low: by up to 1/2\n"
                          "  Chance of a wild estimate: 1 in 101\n"
                          "    (half the time high by up to 3 times the value, else low by up to 1/2)\n"
                          "  Your lag: 8 seconds\n");
    EXACT(two_weapon_facts, "  Hitroll and damroll while you wield a second weapon: +6\n");
    EXACT(scribe_facts, "  Time for the first page: 0.25 seconds\n"
                        "  Time for each later page: 0.25 seconds\n"
                        "  Your lag starting a spell: 4 seconds\n"
                        "  Your lag starting one from a teacher: 4 seconds\n");
    EXACT(scribe_mastery_facts, "  Pages each spell takes: -20, but at least 1\n"
                                "  Time for each later page: 0.25 seconds\n"
                                "  Your lag starting a spell: 4 seconds\n"
                                "  Your lag starting one from a teacher: 4 seconds\n");
    EXACT(improved_endurance_facts, "  Maximum vitality: +50\n"
                                    "  Vitality recovery base: +10\n"
                                    "    (the recovery formula then squares its base)\n");
    EXACT(fix_facts, "  Chance: 100 in 106\n"
                     "  Condition afterward: 90-100\n"
                     "  Condition lost if you fail: 2-30\n"
                     "  An item at 0 condition is destroyed.\n"
                     "  Only at condition 20-90, and it uses up a piece of the item's material.\n");
    EXACT(smelt_facts, "  Chance a smelt risks a mishap: 1 in 3\n"
                       "  Chance you then avoid it: 100 in 100\n"
                       "    (a mishap leaves alloy)\n"
                       "  It takes a furnace in the room, holding one or two things. One is destroyed.\n");
    ch = viewer(viewers[0], 56);
    EXACT(chant_facts, "  Only monks can chant.\n");
    EXACT(calm_facts, "  Only monks can chant calm.\n");
    EXACT(ki_strike_facts, "  Only monks can chant ki strike.\n");
    EXACT(diamond_soul_facts, "  Only monks can chant diamond soul.\n");
    // Reavers' own penalties, read live: a zero property shows nothing.
    ch = viewer(viewers[4], 56);
    live_properties["reavers.ice.penalty.pulse.1hBludgeon"] = 0;
    live_properties["reavers.ice.penalty.pulse.2hBludgeon"] = 1;
    const std::string plain = weapon_skill_lines(&ch, 100);
    EXACT(one_h_bludgeon_facts, plain);
    EXACT(two_h_bludgeon_facts, plain + "  As an ice reaver, one makes your combat round 1 pulses longer.\n");
    ch = viewer(viewers[5], 56);
    live_properties["reavers.flame.penalty.pulse.2hSlashing"] = 1;
    EXACT(two_h_slashing_facts, weapon_skill_lines(&ch, 100) + "  As a flame reaver, one makes your combat round 1 pulses longer.\n");
    EXACT(two_h_bludgeon_facts, weapon_skill_lines(&ch, 100));
    live_properties.clear();
    // Rating 0.
    set_ratings(0);
    ch = viewer(viewers[1], 56);
    for (const Page &page : pages) {
        const std::string name = page.name;
        const std::string text = page.facts(&ch);
        if (name.find("h_bludgeon") != std::string::npos || name == "two_h_slashing" || name == "mount" || name == "appraise" || name == "chant")
            continue;
        if (text.find("not learned") == std::string::npos && text.find("need this skill") == std::string::npos) {
            std::fprintf(stderr, "%s at rating 0: %s\n", page.name, text.c_str());
            page_failed = true;
        }
    }
    EXACT(chant_facts, "  You have not learned to chant.\n");
    set_ratings(40);
    ch = viewer(viewers[2], 56);
    EXACT(infuse_life_facts, "  Your rating adds hit points to what you raise, conjure or summon.\n"
                             "  Raising and elemental spell pages show them with your rating.\n"
                             "  Your raised undead count your rating as: 53\n"
                             "  Hit points of minions from the conjure command: 108% of normal\n"
                             "  Hit points a summoned beast gains: 80, a greater one 200\n"
                             "    (about two-thirds of that with the dice, unless you're an animalist)\n"
                             "  Levels a summoned beast gains: 2-4\n"
                             "  Levels a greater summoned beast gains: 2-4\n"
                             "    (an animalist's greater beast uses its own, larger gain)\n");
    EXACT(feign_death_facts, "  Chance it stops the fight: 39 in 101 to 99 in 101\n"
                             "  Each attacker then rolls the same chance: it stops casting, and you hide.\n"
                             "  Your lag if it works: 8 seconds\n"
                             "  Your lag if it fails: 12 seconds\n"
                             "  You end up prone if it fails, or if it works while anyone attacks you.\n"
                             "  Before you can try again, even after a failure: 20 seconds\n"
                             "  Above level 40, NPCs in the room also forget you when it works.\n"
                             "  Only while fighting, and not while riding.\n");
    ch = viewer(viewers[9], 56);
    set_ratings(40);
    EXACT(meditate_facts, "  Chance a spell's recovery skips its extra half: 41 in 101\n"
                          "  Chance your recovery time halves: 60 in 101\n"
                          "  Base mana recovery, if you use mana: 1000 while you meditate\n"
                          "  Your lag: 4 seconds\n"
                          "  You must be sitting. An attack on you or most commands end it.\n");
    ratings.erase(SKILL_ADVANCED_MEDITATION);
    ch = viewer(viewers[10], 56);
    EXACT(meditate_facts, "  Chance a spell's recovery skips its extra half: 41 in 101\n"
                          "  Chance your recovery time halves: 40 in 101\n"
                          "  Base mana recovery, if you use mana: 1000 while you meditate\n"
                          "  Your lag: 4 seconds\n"
                          "  You must be sitting. An attack on you or most commands end it.\n");
    set_ratings(100);
    ch = viewer(viewers[0], 56);
    EXACT(bandage_facts, "  Healing every 4 seconds: 14, plus 1/20 of the bandage's strength\n"
                         "    (up to its strength in all, and to 7/8 of the target's maximum)\n"
                         "  Chance each round destroys the bandage: 1 in 404\n"
                         "  Chance each round cures poison: 1 in 5, then 100 in 101\n"
                         "  Vitality each round: 2\n"
                         "    (you stop below 10)\n"
                         "  Your lag: 8 seconds\n"
                         "  Before the same target can be bandaged again: 3-4 game hours (3.75-5 minutes)\n"
                         "    (unless it is dying)\n"
                         "  It takes a bandage and a target at or below 7/8 of its maximum, with nobody\n"
                         "  fighting you or it.\n");
    EXACT(fishing_facts, "  Wait for a bite: 44 seconds\n"
                         "  Chance you catch something: 100 in 125\n"
                         "  Experience for a catch: 500, falling to 20\n"
                         "    It recovers after no catch for: 10-11 game hours (12.5-13.75 minutes)\n"
                         "  Vitality each round: 2\n"
                         "    (you stop below 10)\n"
                         "  A catch damages the pole 1 in 3 times.\n"
                         "  It takes a pole and water, and it ruins a disguise.\n");
    ch = viewer(viewers[0], 56);
    EXACT(salvage_facts, "  Chance it doesn't break: 100 in 105\n"
                         "    (Lantan scientific tools prevent that break)\n"
                         "  Chance of two pieces of material: 1 in 3\n"
                         "  Material's value scales with your level over 56 and your rating over 100.\n"
                         "  Recipe score: 312\n"
                         "    (from your luck, level and rating, against 1-10000: easier on cheap\n"
                         "    items and with tools, impossible on the most valuable)\n");
    EXACT(listen_facts, "  Chance the listen command hears something: 100 in 101\n"
                        "    (your luck can take a tenth off the roll)\n"
                        "  It finds beings you can't see here, and counts them from level 15.\n"
                        "  Rooms away you overhear a say or group say: 2\n"
                        "  Chance you overhear it: 21 in 21\n"
                        "  Chance you catch a speaker's name: 21 in 21, in a group say 21 in 21\n"
                        "  Chance you catch each word, one room away: 51 in 51\n"
                        "    (10 worse for each further room)\n"
                        "  Nothing carries into a silent room.\n");
    EXACT(improved_listen_facts, "  Rooms away you overhear a say or group say: 2\n"
                                 "  Chance past the next room: 96 in 101\n"
                                 "  Rooms away you notice an emote: 2\n"
                                 "  Chance you notice it: 41 in 41\n"
                                 "  Chance you see who a smaller emoter is: 21 in 21\n"
                                 "  You also need the listen skill.\n");
    EXACT(improved_track_facts, "  Rooms a track scan shows on the map: 5\n"
                                "  Chance the map shows fresh blood: 31 in 31\n"
                                "  Chance the map shows old blood: 21 in 21\n"
                                "  Chance a scan shows blood here: 21 in 21\n"
                                "    If it has dried: 11 in 11\n"
                                "  Base chance you notice tracks on entering a room: 99 in 100\n"
                                "    (terrain, race, class, position and sight change the roll)\n"
                                "  A track scan needs the track skill.\n");
    EXACT(spell_penetration_facts, "  Chance a spell bursts through magic resistance: 50 in 111\n"
                                   "    (with the target in your room; never past a beholder's eye)\n"
                                   "  Percent less damage it takes from its next spell damage: 20-70 plus 1\n");
    EXACT(summon_blizzard_facts, "  Cold damage on a random target outside your group: 74-94\n"
                                 "    (it can't be shrugged off or deflected; other defenses apply)\n"
                                 "  Time between strikes: 5 seconds to 7.5 seconds\n"
                                 "    (divided by 1 plus the others in the room outside your group)\n"
                                 "  Duration: 25.25 seconds\n"
                                 "  Before you can summon another: 3 minutes\n"
                                 "  A firestorm, scathing wind or incendiary cloud here melts it to water.\n"
                                 "  Only one can rage in a room.\n");
    EXACT(summon_familiar_facts, "  Familiars you can summon: cat, bat, iguana, raven, owl, imp\n"
                                 "  Extra hit points: 200\n"
                                 "  It stays for: 1000-1001 game hours (1250-1251.25 minutes)\n"
                                 "  Before you can call again: 10 minutes\n"
                                 "    (even for a kind you can't summon)\n"
                                 "  A bat dives 1 in 3 times to stop a takedown on you; 1 in 3 of those, if the\n"
                                 "  attacker's agility loses a roll of 0-150, lags it 4 seconds.\n"
                                 "  You can have one at a time.\n");
    EXACT(infuse_magical_device_facts, "  Chance it stops after the first charge: 0 in 101\n"
                                       "    (10 worse after each further charge; it never adds more than 10)\n"
                                       "  Wear each infusion adds to the device: 1, and it takes no more at 2\n"
                                       "  Before you can infuse again: 24-25 game hours (30-31.25 minutes)\n"
                                       "  Your lag: 20 seconds\n"
                                       "  It uses up an encrusting jewel on a held wand, or a staff at rating 40.\n");
    EXACT(holy_smite_facts, "  Chance: 100 in 101\n"
                            "  Damage: 14-140\n"
                            "  Armor and skin spells don't reduce it, and shields don't answer it.\n"
                            "  Your lag: 8 seconds\n"
                            "  Your lag if you fail: 4 seconds\n"
                            "  Chance it blinds a target it leaves alive: 27 in 150\n"
                            "    For: 8 seconds to 10 seconds\n"
                            "    (not on a target that is already blind or can't be blinded)\n"
                            "  Only on an evil target.\n");
    EXACT(cleave_facts, "  Chance: 95 in 96\n"
                        "  Damage: 28-280\n"
                        "  Raw damage, past armor and most skin spells.\n"
                        "  Before it can cleave the same target again: 16 seconds\n"
                        "  It strikes the attacker when you rescue someone, not when you rescue all,\n"
                        "  and only with a paladin sword wielded.\n");
    EXACT(smite_evil_facts, "  Chance for each dying evil target in the room: 50 in 101 every 5 seconds\n"
                            "    (below 15 hit points and a tenth of its maximum, and not in your group\n"
                            "    or on the good side of the racewar)\n"
                            "  Damage: 5-25\n"
                            "  Raw damage, past armor and most skin spells.\n"
                            "  You must be awake and free to move, with a paladin sword wielded.\n");
    EXACT(dread_wrath_facts, "  Armor class of the target you fight: +200\n"
                             "    (worse for it, while you keep fighting it)\n"
                             "  Not on constructs or targets that can't be frightened.\n");
    EXACT(mount_facts, "  Vitality it costs to climb on: 1\n"
                       "  Highest level of untrained animal you can ride: 78\n"
                       "  Trained mounts need no such level. Other creatures can't be ridden.\n");
    EXACT(craft_facts, "  Highest recipe value you can make: 168, 3 per level\n"
                       "  Each recipe also takes its materials and a tool box.\n"
                       "  You can know only one of forge, mine and craft.\n");
    EXACT(forge_facts, "  Highest recipe value you can make: 168, 3 per level\n"
                       "  Each recipe also takes its materials and flux.\n"
                       "  You can know only one of forge, mine and craft.\n");
    EXACT(mine_facts, "  Time a vein takes: 100% of its base, give or take a round\n"
                      "  Experience for what you find: 400\n"
                      "  Chance each round finds only rock: 1 in 201\n"
                      "  Chance each round fumbles the pick if you ride: 1 in 6\n"
                      "  Vitality each round: 2\n"
                      "    (you stop below 10)\n"
                      "  Ore's value scales with your level over 56 and your rating over 100.\n"
                      "  It takes a wielded pick. You can know only one of forge, mine and craft.\n");
    EXACT(mix_facts, "  Potions your level can mix: 2 of 2\n"
                     "  Chance each bottle makes one: 99 in 160\n"
                     "    (from your wisdom and dexterity)\n"
                     "  Chance a bottle is used up: 1 in 6\n"
                     "  Chance the ingredients run out after each bottle: 1 in 12-13\n"
                     "  Your lag: 8 seconds\n"
                     "  Your lag if you have nothing to mix: 4 seconds\n"
                     "  It takes a potion bottle and the ingredients.\n");
    EXACT(mixpoison_facts, "  Poisons your level and rating can mix: 2 of 2\n"
                           "  Your lag: 4 seconds\n"
                           "  It takes a poison vial and the ingredients. Type mixpoison list for them.\n");
    EXACT(encrust_facts, "  Chance: 100 in 110\n"
                         "  A failure destroys the item and the jewel.\n"
                         "  Your lag: 4 seconds\n"
                         "  Chance the worn item casts the jewel's spell: 1 in 30 on each trigger\n"
                         "    (at your level when you encrusted it; it can't then be repaired)\n"
                         "  Weapons, armor, shields, lights, instruments and worn gear, once each.\n");
    EXACT(enchant_facts, "  Highest spell circle you can bind: 10\n"
                         "  Platinum it costs per circle: 10\n"
                         "  Lowest item condition: 30\n"
                         "  Duration: 50 minutes\n"
                         "  Chance it spoils: 1 in 91\n"
                         "  Condition that costs: 5-10\n"
                         "    (and 1 in 6 stops repairs)\n"
                         "  Your lag, and the wait for it to take: 4 seconds\n"
                         "  The spell must be on you, harmless, and castable on others, and\n"
                         "  wearing the item casts it at your level. No artifacts.\n");
    EXACT(spellbind_facts, "  Chance: 91 in 131\n"
                           "  A failure has a 1 in 5 chance to cost 1-20 condition and stop repairs.\n"
                           "  A success spends 1 epic point and stops repairs; 1 in 3 also costs 1-20\n"
                           "  condition, and otherwise 1 in 41 brings strong magic.\n"
                           "  Each of its first 3 affects improves by: 5\n"
                           "  Stat maximums and saving throws improve by: 2\n"
                           "  Armor is multiplied by: 2\n"
                           "    (later affects on the item also carry the total so far)\n"
                           "  It takes a repairable item in perfect condition, and no artifacts.\n");
    EXACT(slip_facts, "  Chance to slip something to someone: 100 less its weight, in 100\n"
                      "    Less, while you fight: 20\n"
                      "    (if it fails, it falls to the ground)\n"
                      "  Slipping it into a container always works, on the same chance unseen.\n"
                      "  Chance you get something from a container unseen: 95 in 101\n"
                      "    (from your rating and dexterity)\n");
    EXACT(disguise_facts, "  Chance, as a listed type of your race: 101 in 101\n"
                          "  Chance, as another race's type or someone you match: 101 in 101\n"
                          "    (someone of another race is 30 harder, another sex 10, an enemy 20)\n"
                          "  Your lag: 20 seconds\n"
                          "  Your lag if you fail: 12 seconds\n"
                          "  Your lag if the size is off by more than 1: 8 seconds\n"
                          "  Your lag removing a disguise: 12 seconds\n"
                          "  Its strength: 224\n"
                          "    (damage you take wears it down, and so does time)\n"
                          "  It uses up a disguise kit; a failure ruins it 1 in 2 times.\n"
                          "  Not while fighting.\n");
    EXACT(exhume_facts, "  Corpse level: 50\n"
                        "    (near the cap of 50 the second roll of its check can pass it)\n"
                        "  Before you can do it again: 5 minutes\n"
                        "  Your lag exhuming: 3.5 seconds\n"
                        "  Exhuming takes a held or wielded shovel, hoe or pick, on the ground\n"
                        "  in a field, forest, hills, mountains or wild underdark.\n");
    live_properties["timer.mins.exhume"] = 8;
    EXACT(exhume_facts, "  Corpse level: 50\n"
                        "    (near the cap of 50 the second roll of its check can pass it)\n"
                        "  Before you can do it again: 4 minutes\n"
                        "  Your lag exhuming: 3.5 seconds\n"
                        "  Exhuming takes a held or wielded shovel, hoe or pick, on the ground\n"
                        "  in a field, forest, hills, mountains or wild underdark.\n");
    live_properties.clear();
    ch = viewer(viewers[1], 56);
    EXACT(ki_strike_facts, "  Chance: 100 in 100\n"
                           "  Your lag: 10 seconds\n"
                           "  Target's lag: 6 seconds\n"
                           "  Your lag if you fail: 8 seconds\n"
                           "  Your lag if the target isn't standing: 4 seconds, and you fall over\n"
                           "  Before you can chant it again, even after a failure: 45 seconds\n"
                           "  A further roll slows the target for: 1-2 game hours (1.25-2.5 minutes)\n"
                           "    (your level above its, capped at 100, -5 to 20 more,\n"
                           "    and 10 from anatomy, against 1-30)\n"
                           "    (not on elites, greater races or a target it already slowed)\n"
                           "  Not in a safe room, or past the next in line in a single-file room.\n"
                           "  Your chant skill has its own roll first, and chanting adds its lag.\n");

    // The right property keys, so a stub's fallback can't hide a misspelled one.
    for (const char *key : { "timer.secs.feignDeath", "timer.secs.monkDiamond", "timer.secs.monkKistrike", "timer.secs.monkChipurge",
                             "timer.mins.exhume", "timer.mins.summonBlizzard", "timer.mins.summonFamiliar", "skill.timer.secs.smiteEvil",
                             "reavers.ice.penalty.pulse.1hBludgeon", "reavers.ice.penalty.pulse.2hBludgeon", "reavers.flame.penalty.pulse.2hSlashing",
                             "skill.enchant.minItemCondition", "skill.listen.range.norm", "skill.listen.range.norm.extend", "skill.listen.range.improved",
                             "skill.slip.fightingPenalty", "skill.spellPenetration.highEndPercent", "skill.spellPenetration.damageReductionMod" })
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
    puts("PASS: skills batch 4 shared rolls match the old code and stay in range, facts never roll");
}
'''


def in_order(body, calls):
    position = 0
    compact = re.sub(r"\s+", "", body)
    for call in calls:
        position = compact.find(re.sub(r"\s+", "", call), position) + 1
        if not position:
            return call
    return None


def check_sources():
    for (file, head), calls in HANDLER_CALLS.items():
        text = strip_comments(source(file).read_text())
        if head == "ALL":
            for call in calls:
                assert re.sub(r"\s+", "", call) in re.sub(r"\s+", "", text), f"{file} lacks {call}"
            continue
        bodies = function_bodies(text, re.escape(head) + r"\s*\(")
        assert bodies, head
        missing = [in_order(body, calls) for body in bodies]
        assert None in missing, f"{head}: missing or out of order: {missing}"
    for file, head, old in STALE:
        bodies = function_bodies(strip_comments(source(file).read_text()), rf"{head}\s*\(")
        assert bodies and all(old not in body for body in bodies), f"{head} still has {old}"
    table = strip_comments(source("abilities.c").read_text())
    header = source("abilities.h").read_text()
    for constant, name, _ in SKILLS:
        assert re.search(rf"case {constant}:\s*return {name}_facts;", table), constant
        assert f"std::string {name}_facts(char_data *ch);" in header, name
    # A dispatched chant runs at the chanter's level.
    no_numbers = (ROOT / "tests/fixtures/ability_coverage_no_numbers.txt").read_text()
    pending = (ROOT / "tests/fixtures/ability_coverage_pending.txt").read_text()
    for constant in NO_NUMBERS:
        assert f"{constant}\n" in no_numbers and f"{constant}\n" not in pending, constant
        reads = 0
        for path in (ROOT / "src").rglob("*.c"):
            reads += len(re.findall(rf"\b{constant}\b", strip_comments(path.read_text(errors="replace"))))
        assert reads == 1, f"{constant} is read outside its registration ({reads})"
    assert "do_mug(P_char /*ch*/, char * /*argument*/, int /*cmd*/) {}" in source("cmd/actoff.c").read_text()


def extract_named(file, name):
    text = source(file).read_text()
    match = re.search(rf"^(?:static )?[\w:]+(?: \w+)? \*?{name}\([^;\n]*\)$", text, re.M)
    if not match:
        match = re.search(rf"^(?:static )?[\w:]+(?: \w+)? \*?{name}\([^;\n]*\)\n{{", text, re.M)
    assert match, name
    return extract_function(file, match.group(0).split("\n")[0] + "\n{")


def main():
    check_sources()
    functions = [extract_function("utility.c", "int dice(int num, int size)"),
                 extract_function("utility.c", "int BOUNDED(int a, int b, int c)"),
                 extract_function("utility.c", "int GET_CLASS(P_char ch, uint m_class)"),
                 extract_function("utility.c", "int GET_PRIME_CLASS(P_char ch, uint m_class)"),
                 extract_function("utility.c", "int GET_SECONDARY_CLASS(P_char ch, uint m_class)")]
    facts = {}
    for _, name, file in SKILLS:
        facts.setdefault(file, []).append(name)
    for file in SHARED:
        for name in SHARED[file]:
            if name == "summon_familiar_rest":
                text = source(file).read_text()
                start = text.index("typedef struct\n{\n\tint vnum;\n\tint skill;\n\tconst char *name;\n} familiar_data;")
                functions.append(text[start:text.index("static int summon_familiar_rest", start)])
            functions.append(extract_named(file, name))
        for name in facts.get(file, []):
            functions.append(extract_function(file, f"std::string {name}_facts(P_char"))
    pages = ",\n".join(f'    {{ "{name}", {name}_facts }}' for _, name, _ in SKILLS)
    skills = ", ".join(sorted({c for c, _, _ in SKILLS} | {"SKILL_ANATOMY", "SKILL_ADVANCED_MEDITATION"}))
    build = ROOT / "bin/tests"
    build.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ability-skills-4-", dir=build) as temporary:
        directory = Path(temporary)
        harness = directory / "skills4.cpp"
        harness.write_text(HARNESS.replace("PAGES", pages).replace("SKILLS", skills).replace("FUNCTIONS", "\n".join(functions)))
        binary = directory / "skills4"
        subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-Wno-unused-function",
                        "-ffunction-sections", "-fdata-sections", "-Wl,--gc-sections",
                        "-fsanitize=address,undefined", "-fno-sanitize-recover=undefined",
                        "-Isrc", "-I/usr/include/mysql", "-I/usr/include/libxml2",
                        str(harness), "src/abilities/abilities.c", "src/core/random.c",
                        "-o", str(binary)], cwd=ROOT, check=True)
        subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    main()
