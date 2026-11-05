#!/usr/bin/env python3
"""Shared ability numbers, skills batch 1: combat and rogue skills.

Builds src/abilities/abilities.c and the real RNG with the shared and facts functions of
this batch, under sanitizers. Each converted roll keeps its pre-conversion expression
below as the oracle: under the same seeds it must give the same value and leave the RNG
at the same draw, and the value must fall inside the range the facts use. Every page is
built at every level for several viewers: it must never roll and every line must fit 79
columns. Source checks tie every handler to the functions it must call.
"""
import re
import subprocess
import tempfile
from pathlib import Path

from _paths import ROOT, extract_function, source
from _source_contract import function_bodies, strip_comments

SHARED = {
    "fight.c": """flank_damage_modifier circle_damage_modifier dreadnaught_attack_factor dreadnaught_melee_defense mounted_combat_redirect_threshold""".split(),
    "dam_mods.c": """dreadnaught_spell_defense""".split(),
    "actoff.c": """backstab_air_aura_below legsweep_prone_up_to tackle_carry_roll headbutt_weak_daze_roll springleap_super_stun_roll restrain_stops_casting_roll dragon_roar_flee_roll evade_threshold evade_rest grapple_threshold lance_charge_rest lance_charge_lag lance_charge_topple_lag lance_charge_topple_damage lance_charge_target_lag lance_charge_knockdown_lag lance_charge_weapon_damage lance_charge_scaled_damage lance_charge_ranged_damage lance_charge_impale_damage lance_charge_glance_damage lance_charge_ram_damage lance_charge_through_damage charge_lag charge_vitality_cost charge_ceiling_knockout charge_target_lag charge_rest charge_damage circle_rest circle_lag circle_threshold circle_duration control_flee_threshold expeditious_retreat_threshold expeditious_retreat_duration mounted_combat_calm_threshold combination_damage combination_skill_required combination_fumble_roll combination_lag combination_stun combination_rest combination_delay blade_barrage_fumble_roll blade_barrage_skill_required blade_barrage_lag blade_barrage_rest blade_barrage_delay rush_lag kick_base_damage kick_rolled_damage kick_scaled_damage kick_quick_damage kick_quick_lag kick_lag kick_room_lag kick_wall_lag kick_groin_lag kick_low_roll kick_stun_roll kick_wall_stun kick_groin_stun dragoon_power dragon_roar_hit_points dragon_roar_bonus dragon_roar_duration dragon_roar_threshold dragon_roar_empower dragon_roar_penalty dragon_roar_rest dragon_roar_lag dragon_roar_flee_threshold dragon_roar_flee_level dragon_breath_threshold dragon_breath_rest dragon_breath_lag dragon_strike_damage dragon_strike_lancer_damage dragon_strike_lag dragon_strike_face_plant_lag dragon_strike_fall_damage dragon_strike_rest dragon_strike_target_lag roundkick_immaterial_lag roundkick_lag roundkick_damage roundkick_target_lag roundkick_rest headbutt_position_lag headbutt_immaterial_lag headbutt_refused_lag headbutt_backfire_lag headbutt_miss_lag headbutt_hit_lag headbutt_backfire_rest headbutt_miss_rest headbutt_hit_rest headbutt_backfire_damage headbutt_miss_damage headbutt_knockout headbutt_hit_roll headbutt_hit_damage headbutt_smaller_factor headbutt_larger_factor headbutt_daze_lag headbutt_daze_stun headbutt_weak_daze double_headbutt_threshold double_headbutt_damage garrote_threshold garrote_miss_rest garrote_hit_rest garrote_miss_lag garrote_hit_lag garrote_rounds garrote_bleed_damage garrote_stops_casting_roll sneaky_strike_bleed_damage sneaky_strike_weapon_damage sneaky_strike_multiplier sneaky_strike_damage sneaky_strike_bleed_rounds sneaky_strike_drain sneaky_strike_blind sneaky_strike_lag backstab_skill backstab_luck_bonus backstab_damage backstab_noticed_damage backstab_helpless_damage backstab_incapacitated_damage backstab_repeat_window backstab_lag backstab_air_aura_roll critical_stab_threshold spinal_tap_threshold critical_stab_damage spinal_tap_damage rolls_below backstab_weapon switch_opponents_lag bash_miss_lag bash_target_down_lag bash_size_lag bash_takedown_penalty_lag bash_target_lag shieldless_bash_modifier skewer_down_threshold skewer_off_target_rating skewer_down_damage skewer_down_lag skewer_down_target_lag skewer_bash_threshold skewer_bash_damage skewer_bash_lag parlay_score parlay_elite_penalty parlay_flee_roll parlay_truce_roll parlay_success_lag parlay_failure_lag tackle_body_lag tackle_size_lag tackle_lag tackle_prone_lag tackle_rest tackle_combat_pulse tackle_combat_pulse_duration tackle_self_stun retreat_chance retreat_lag retreat_page rescue_lag maul_damage maul_mauler_damage maul_penalty_lag maul_failed_lag maul_hit_lag maul_target_lag maul_rest maul_aware_duration maul_clip_roll shieldpunch_lag shieldpunch_bonus shieldpunch_damage sweeping_thrust_lag sweeping_thrust_odds sweeping_thrust_target_lag springleap_failed_lag springleap_lag springleap_fall_lag springleap_target_lag springleap_rest springleap_crash_damage springleap_plain_roll springleap_super_damage springleap_super_stun whirlwind_vitality_needed whirlwind_failed_vitality whirlwind_move_regen whirlwind_duration whirlwind_blindfighting_needed trip_foiled_lag trip_miss_lag trip_lag trip_target_lag trip_miss_damage flank_rest flank_lag flank_duration call_grave_delay call_grave_rest call_grave_lag call_grave_skill call_grave_count_roll call_grave_count call_grave_level_roll call_grave_level call_grave_hit_points call_grave_lifetime call_grave_target_damage battle_orders_lag battle_orders_rest gaze_refused_lag gaze_resisted_lag gaze_size_lag gaze_lag gaze_target_duration gaze_rest gaze_npc_lag anatomy_kill_bonus gaze_kill_hit_points restrain_refused_lag restrain_resisted_lag restrain_lag restrain_duration restrain_rest restrain_npc_lag restrain_kill_hit_points shriek_rest shriek_base_damage shriek_saved_damage shriek_roll_damage dreadnaught_duration dreadnaught_failed_rest dreadnaught_rest shadowstep_duration shadowstep_hide_duration legsweep_size_lag legsweep_lag legsweep_rest legsweep_prone_roll crippling_strike_roll crippling_strike_deaf_duration crippling_strike_best_vitality crippling_strike_second_vitality crippling_strike_best_damage crippling_strike_second_damage crippling_strike_third_damage crippling_strike_fourth_damage taunt_save_modifier taunt_threshold taunt_duration taunt_target_lag taunt_lag""".split(),
    "mount.c": """mounted_combat_mount_threshold""".split(),
    "new_skills.c": """awareness_max_duration awareness_rolled_duration""".split(),
    "actoth.c": """berserk_quality berserk_str_max berserk_con_max berserk_int berserk_wis berserk_pow_max berserk_combat_pulse berserk_hit_points berserk_duration berserk_lag berserk_stop_lag berserk_stop_wounded_share rampage_duration rampage_lag infuriate_duration infuriate_lag infuriate_str_max infuriate_con_max infuriate_agi infuriate_dex infuriate_form_facts sneak_lag sneak_duration sneak_agility_bonus hide_lag hide_agility_bonus ambush_duration climb_duration blood_scent_failed_lag blood_scent_lag blood_scent_duration""".split(),
    "actinf.c": """age_corpse_error_percent legend_lore_lag""".split(),
    "actmove.c": """pick_lock_rest pick_lock_lag""".split(),
    "bard.c": """bard_protection_minor_globe_level bard_protection_skin_level bard_protection_globe_level bard_protection_ac""".split(),
    "track.c": """track_lag track_abandon_lag track_scan_lag""".split(),
}

CONVERTED = """
SKILL_AWARENESS awareness new_skills.c
SKILL_BACKSTAB backstab actoff.c
SKILL_BATTLE_ORDERS battle_orders actoff.c
SKILL_BLADE_BARRAGE blade_barrage actoff.c
SKILL_CALL_GRAVE call_grave actoff.c
SKILL_CHARGE charge actoff.c
SKILL_CIRCLE circle actoff.c
SKILL_COMBINATION combination actoff.c
SKILL_CONTROL_FLEE control_flee actoff.c
SKILL_CRIPPLING_STRIKE crippling_strike actoff.c
SKILL_CRITICAL_STAB critical_stab actoff.c
SKILL_DOUBLE_HEADBUTT double_headbutt actoff.c
SKILL_DRAGON_BREATH dragon_breath actoff.c
SKILL_DRAGON_ROAR dragon_roar actoff.c
SKILL_DRAGON_STRIKE dragon_strike actoff.c
SKILL_DREADNAUGHT dreadnaught actoff.c
SKILL_EVADE evade actoff.c
SKILL_EXPEDITED_RETREAT expedited_retreat actoff.c
SKILL_EXPEDITIOUS_RETREAT expeditious_retreat actoff.c
SKILL_FLANK flank actoff.c
SKILL_GARROTE garrote actoff.c
SKILL_GAZE gaze actoff.c
SKILL_GRAPPLE grapple actoff.c
SKILL_HEADBUTT headbutt actoff.c
SKILL_KICK kick actoff.c
SKILL_LANCE_CHARGE lance_charge actoff.c
SKILL_LEGSWEEP legsweep actoff.c
SKILL_MAUL maul actoff.c
SKILL_MOUNTED_COMBAT mounted_combat mount.c
SKILL_PARLAY parlay actoff.c
SKILL_RESCUE rescue actoff.c
SKILL_RESTRAIN restrain actoff.c
SKILL_RETREAT retreat actoff.c
SKILL_ROUNDKICK roundkick actoff.c
SKILL_RUSH rush actoff.c
SKILL_SHADOWSTEP shadowstep actoff.c
SKILL_SHIELDLESS_BASH shieldless_bash actoff.c
SKILL_SHIELDPUNCH shieldpunch actoff.c
SKILL_SHRIEK shriek actoff.c
SKILL_SKEWER skewer actoff.c
SKILL_SNEAKY_STRIKE sneaky_strike actoff.c
SKILL_SPINAL_TAP spinal_tap actoff.c
SKILL_SPRINGLEAP springleap actoff.c
SKILL_SURPRISE surprise actoff.c
SKILL_SWEEPING_THRUST sweeping_thrust actoff.c
SKILL_SWITCH_OPPONENTS switch_opponents actoff.c
SKILL_TACKLE tackle actoff.c
SKILL_TAUNT taunt actoff.c
SKILL_TRIP trip actoff.c
SKILL_WHIRLWIND whirlwind actoff.c
SKILL_BERSERK berserk actoth.c
SKILL_BLOOD_SCENT blood_scent actoth.c
SKILL_CLIMB climb actoth.c
SKILL_HIDE hide actoth.c
SKILL_INFURIATE infuriate actoth.c
SKILL_RAMPAGE rampage actoth.c
SKILL_SNEAK sneak actoth.c
SKILL_AGE_CORPSE age_corpse actinf.c
SKILL_LEGEND_LORE legend_lore actinf.c
SKILL_PICK_LOCK pick_lock actmove.c
SKILL_AMBUSH ambush actoth.c
SKILL_TRACK track track.c
SONG_PROTECTION song_protection bard.c
"""
HANDLER_CALLS = {
    "void lance_charge(": ["set_short_affected_by(ch, SKILL_LANCE_CHARGE, lance_charge_rest())",
                           "dam = lance_charge_weapon_damage(live_rolls, weapon)", "dam = lance_charge_scaled_damage(dam, GET_LEVEL(ch))",
                           "dam = lance_charge_ranged_damage(dam)", "CharWait(ch, lance_charge_lag())",
                           "CharWait(ch, lance_charge_topple_lag())", "lance_charge_topple_damage(live_rolls)",
                           "CharWait(victim, lance_charge_target_lag())", "dam + lance_charge_impale_damage(live_rolls)",
                           "dam / 2 + lance_charge_glance_damage(live_rolls)", "dam + lance_charge_ram_damage(live_rolls)",
                           "dam + lance_charge_through_damage(live_rolls)", "CharWait(victim, lance_charge_knockdown_lag())"],
    "void do_charge(": ["knock_out(ch, charge_ceiling_knockout())", "CharWait(ch, charge_lag())",
                        "GET_VITALITY(ch) < charge_vitality_cost()", "GET_VITALITY(ch) -= charge_vitality_cost()",
                        "CharWait(victim, charge_target_lag())", "set_short_affected_by(ch, SKILL_CHARGE, charge_rest())",
                        "charge_damage(live_rolls, level)"],
    "bool circle(": ["set_short_affected_by(ch, SKILL_CIRCLE, circle_rest())", "CharWait(ch, circle_lag())",
                     "skill = circle_threshold(ch)", "circle_duration(ch, tch)"],
    "void do_flee(": ["expeditious_retreat_threshold(ch) > number(1, 100)", "control_flee_threshold(control_skill)",
                      "af.duration = expeditious_retreat_duration()", "mounted_combat_calm_threshold(rider)"],
    "void event_combination(": ["combination_fumble_roll(live_rolls)", "dam = combination_damage(live_rolls, stage)",
                                "skill_req = combination_skill_required(stage)", "Stun(victim, ch, combination_stun(), TRUE)",
                                "CharWait(ch, combination_lag())"],
    "void do_combination(": ["affect_timer(ch, combination_rest(), SKILL_COMBINATION)", "combination_delay(GET_LEVEL(ch))"],
    "void event_barrage(": ["blade_barrage_fumble_roll(live_rolls)", "CharWait(ch, blade_barrage_lag())",
                            "skill_req = blade_barrage_skill_required(stage)"],
    "void do_barrage(": ["affect_timer(ch, blade_barrage_rest(), SKILL_BLADE_BARRAGE)", "blade_barrage_delay(GET_LEVEL(ch))"],
    "void rush(": ["CharWait(ch, rush_lag())"],
    "void kick(": ["dam = kick_base_damage(ch)", "dam = kick_rolled_damage(live_rolls, dam)", "dam = kick_scaled_damage(dam)",
                   "dam = kick_quick_damage(dam, GET_LEVEL(ch))", "CharWait(ch, kick_quick_lag())", "CharWait(ch, kick_lag(live_rolls))",
                   "CharWait(victim, kick_room_lag())", "kick_stun_roll(live_rolls)", "Stun(victim, ch, kick_wall_stun(live_rolls), TRUE)",
                   "CharWait(victim, kick_wall_lag())", "kick_low_roll(live_rolls)",
                   "Stun(victim, ch, kick_groin_stun(live_rolls), TRUE)", "CharWait(victim, kick_groin_lag())"],
    "void do_dragon_roar(": ["hpoints = dragon_roar_hit_points(ch)", "dampoints = dragon_roar_bonus(ch)",
                             "percent_chance = dragon_roar_threshold(ch)", "power = dragoon_power(ch)", "empower = dragon_roar_empower(ch, is_hunter)",
                             "af.duration = dragon_roar_duration(dampoints)", "af.modifier = dragon_roar_penalty(ch, empower)",
                             "SKILL_DRAGON_ROAR, dragon_roar_rest())", "CharWait(ch, dragon_roar_lag())",
                             "dragon_roar_flee_threshold()", "dragon_roar_flee_level(ch, empower) >="],
    "void do_dragon_breath(": ["percent_chance = dragon_breath_threshold(ch)", "power = dragoon_power(ch)",
                               "SKILL_DRAGON_BREATH, dragon_breath_rest())", "CharWait(ch, dragon_breath_lag())",
                               "spell_burning_hands(GET_LEVEL(mount)", "spell_immolate(GET_LEVEL(mount)"],
    "void do_dragon_strike(": ["dam = dragon_strike_damage(live_rolls, ch)", "dam = dragon_strike_lancer_damage(dam)",
                               "CharWait(ch, dragon_strike_lag())", "CharWait(ch, dragon_strike_face_plant_lag())",
                               "dragon_strike_fall_damage(live_rolls, ch)", "SKILL_DRAGON_STRIKE, dragon_strike_rest())",
                               "CharWait(victim, dragon_strike_target_lag(vict_lag))"],
    "int chance_roundkick(": ["CharWait(ch, roundkick_immaterial_lag())"],
    "bool roundkick(": ["CharWait(ch, roundkick_lag())", "dam = roundkick_damage(ch) - GET_C_AGI(victim)",
                        "CharWait(victim, roundkick_target_lag())", "SKILL_BASH, roundkick_rest())"],
    "void do_headbutt(": ["CharWait(ch, headbutt_position_lag())", "CharWait(ch, headbutt_immaterial_lag())", "CharWait(ch, headbutt_refused_lag())",
                          "dam = headbutt_backfire_damage(live_rolls)", "af.duration = headbutt_backfire_rest()", "CharWait(ch, headbutt_backfire_lag())",
                          "knock_out(ch, headbutt_knockout(live_rolls))", "dam = headbutt_miss_damage(live_rolls)", "af.duration = headbutt_miss_rest()",
                          "CharWait(ch, headbutt_miss_lag())", "headbutt_hit_damage(ch, headbutt_hit_roll(live_rolls))", "headbutt_smaller_factor()",
                          "headbutt_larger_factor()", "CharWait(ch, headbutt_hit_lag())", "double_headbutt_threshold(ch) > number(0, 300)",
                          "double_headbutt_damage(dam)", "af.duration = headbutt_hit_rest()", "knock_out(victim, headbutt_knockout(live_rolls))",
                          "Stun(victim, ch, headbutt_daze_stun(), FALSE)", "Stun(victim, ch, headbutt_weak_daze(), FALSE)"],
    "void event_garroteproc(": ["dam = garrote_bleed_damage(live_rolls, ch)", "garrote_stops_casting_roll(live_rolls)"],
    "void do_garrote(": ["success = garrote_threshold(ch)", "garrote_miss_rest()", "CharWait(ch, garrote_miss_lag())", "garrote_hit_rest()",
                         "numb = garrote_rounds(live_rolls, ch)", "CharWait(ch, garrote_hit_lag())"],
    "void event_bleedproc(": ["sneaky_strike_bleed_damage(live_rolls)"],
    "void event_sneaky_strike(": ["dam = sneaky_strike_weapon_damage(live_rolls, weapon)",
                                  "dam = sneaky_strike_damage(ch, dam, sneaky_strike_multiplier(live_rolls), skill)",
                                  "blind(ch, victim, sneaky_strike_blind())", "numb = sneaky_strike_bleed_rounds(live_rolls)",
                                  "i = sneaky_strike_drain(live_rolls)", "CharWait(ch, sneaky_strike_lag())"],
    "bool single_stab(": ["skill = backstab_skill(skill, ch)", "backstab_damage(ch, skill, weapon, backstab_luck_bonus(live_rolls, ch))",
                          "critical_stab_threshold(ch) > number(1, 100)", "dam = backstab_noticed_damage(dam, quarter)", "backstab_helpless_damage()",
                          "backstab_incapacitated_damage()", "dam = critical_stab_damage(dam)", "spinal_tap_threshold(ch) > number(1, 100)",
                          "spinal_tap_damage(live_rolls, ch, quarter)"],
    "bool backstab(": ["CharWait(ch, backstab_lag())", "backstab_air_aura_roll(live_rolls)", "backstab_repeat_window()"],
    "void bash(": ["shieldless_bash_modifier(ch)", "skewer_off_target_rating(skewer)", "skewer_down_threshold(skewer) > number(1, 100)",
                   "skewer_down_damage(live_rolls)", "CharWait(victim, skewer_down_target_lag())", "CharWait(ch, skewer_down_lag())",
                   "percent_chance = skewer_bash_threshold(ch)", "skewer_bash_damage(live_rolls)", "CharWait(victim, skewer_bash_lag())",
                   "CharWait(ch, skewer_bash_lag())"],
    "void parlay(": ["skl_lvl = parlay_score(skl_lvl, GET_LEVEL(ch))", "parlay_elite_penalty(live_rolls)", "parlay_flee_roll(live_rolls) < skl_lvl", "skl_lvl > parlay_truce_roll(live_rolls)",
                     "CharWait(ch, parlay_success_lag())", "CharWait(ch, parlay_failure_lag())"],
    "void do_tackle(": ["CharWait(ch, tackle_body_lag())", "CharWait(ch, tackle_size_lag())", "SKILL_BASH, tackle_rest())", "CharWait(ch, tackle_lag())",
                        "CharWait(vict, tackle_lag())", "af.modifier = tackle_combat_pulse()", "af.duration = tackle_combat_pulse_duration()",
                        "Stun(ch, ch, tackle_self_stun(), FALSE)", "CharWait(ch, tackle_prone_lag())"],
    "void do_retreat(": ["chance = retreat_chance(retc, expdr, found, ct, backdir)", "CharWait(ch, retreat_lag())"],
    "void rescue(": ["CharWait(ch, rescue_lag(rescue_all))"],
    "void maul(": ["CharWait(ch, maul_penalty_lag())", "dam = maul_damage(live_rolls, ch)", "dam = maul_mauler_damage(dam)", "maul_clip_roll(live_rolls)",
                   "CharWait(ch, maul_failed_lag())", "CharWait(victim, maul_target_lag(true))", "CharWait(ch, maul_hit_lag(true))", "maul_rest(true)",
                   "CharWait(victim, maul_target_lag(false))", "CharWait(ch, maul_hit_lag(false))", "maul_rest(false)", "af.duration = maul_aware_duration()"],
    "void shieldpunch(": ["CharWait(ch, shieldpunch_lag())", "dambonus = shieldpunch_bonus(ch)", "dmg = shieldpunch_damage(live_rolls, ch, dambonus)"],
    "void do_sweeping_thrust(": ["CharWait(ch, sweeping_thrust_lag())", "sweepthrustaffect = sweeping_thrust_odds(GET_LEVEL(ch))",
                                 "CharWait(victim, sweeping_thrust_target_lag())"],
    "void do_springleap(": ["CharWait(ch, springleap_failed_lag())", "springleap_crash_damage(ch)", "SKILL_SPRINGLEAP, springleap_rest())",
                            "springleap_plain_roll(live_rolls)", "springleap_super_damage(live_rolls)", "Stun(vict, ch, springleap_super_stun(), TRUE)",
                            "CharWait(vict, springleap_target_lag())", "CharWait(ch, springleap_fall_lag())", "CharWait(ch, springleap_lag())"],
    "void do_whirlwind(": ["mod = whirlwind_move_regen()", "GET_VITALITY(ch) < whirlwind_vitality_needed()", "GET_VITALITY(ch) -= whirlwind_failed_vitality()",
                           "af.duration = whirlwind_duration()", "GET_CHAR_SKILL(ch, SKILL_BLINDFIGHTING) < whirlwind_blindfighting_needed()"],
    "void do_trip(": ["CharWait(ch, trip_foiled_lag())", "CharWait(ch, trip_miss_lag())", "trip_miss_damage(ch)", "CharWait(vict, trip_target_lag())",
                      "CharWait(ch, trip_lag())"],
    "bool flank(": ["SKILL_FLANK, flank_rest())", "CharWait(ch, flank_lag())", "flank_duration(ch, tch)"],
    "void do_call_grave(": ["call_grave_delay(live_rolls)", "SKILL_CALL_GRAVE, call_grave_rest())", "CharWait(ch, call_grave_lag())"],
    "void event_call_grave(": ["skill = call_grave_skill(ch)", "num = call_grave_count(skill, call_grave_count_roll(live_rolls))",
                               "call_grave_level(ch, call_grave_level_roll(live_rolls))", "call_grave_hit_points(live_rolls, ch)", "call_grave_lifetime(skill)"],
    "void event_call_grave_target(": ["dmg = call_grave_target_damage(live_rolls, ch)"],
    "void battle_orders(": ["CharWait(ch, battle_orders_lag())", "SKILL_BATTLE_ORDERS, battle_orders_rest())"],
    "void gaze(": ["CharWait(ch, gaze_refused_lag())", "CharWait(ch, gaze_resisted_lag())", "CharWait(ch, gaze_size_lag())", "CharWait(ch, gaze_lag())",
                   "anatomy_skill = anatomy_kill_bonus(ch)", "gaze_kill_hit_points(live_rolls, anatomy_skill)", "SKILL_GAZE, gaze_target_duration())",
                   "SKILL_BASH, gaze_rest())", "CharWait(victim, gaze_npc_lag())"],
    "void restrain(": ["CharWait(ch, restrain_refused_lag())", "CharWait(ch, restrain_resisted_lag())", "CharWait(ch, restrain_lag())",
                       "anatomy_skill = anatomy_kill_bonus(ch)", "restrain_kill_hit_points(live_rolls, anatomy_skill)", "af.duration = restrain_duration()",
                       "SKILL_BASH, restrain_rest())", "CharWait(victim, restrain_npc_lag())"],
    "void do_shriek(": ["SKILL_SHRIEK, shriek_rest())", "basedamage = shriek_base_damage(skl_lvl)", "actualdam = shriek_saved_damage(basedamage)",
                        "actualdam + shriek_roll_damage(live_rolls)"],
    "void do_dreadnaught(": ["duration = dreadnaught_duration(live_rolls, ch, skl_lvl)", "TAG_DREADNAUGHT, dreadnaught_rest(duration))",
                             "TAG_DREADNAUGHT, dreadnaught_failed_rest())"],
    "void do_shadowstep(": ["dur = shadowstep_duration(ch)", "af.duration = shadowstep_hide_duration()"],
    "void do_legsweep(": ["CharWait(ch, legsweep_size_lag())", "SKILL_BASH, legsweep_rest())", "legsweep_prone_roll(live_rolls)", "CharWait(ch, legsweep_lag())",
                          "CharWait(vict, legsweep_lag())"],
    "bool check_crippling_strike(": ["success = skl - crippling_strike_roll(live_rolls)", "af.duration = crippling_strike_deaf_duration(live_rolls)",
                                     "crippling_strike_best_vitality(live_rolls)", "crippling_strike_second_vitality(live_rolls)",
                                     "crippling_strike_best_damage(live_rolls)", "crippling_strike_second_damage(live_rolls)",
                                     "crippling_strike_third_damage(live_rolls)", "crippling_strike_fourth_damage(live_rolls)"],
    "void do_taunt(": ["saveMod = taunt_save_modifier(skl_lvl)", "percent_chance = taunt_threshold(skl_lvl)", "duration = taunt_duration(skl_lvl, IS_NPC(vict))",
                       "CharWait(vict, taunt_target_lag())", "CharWait(ch, taunt_lag())"],
}
OTHER_CALLS = {
    ("takedown_check", "actoff.c", "float takedown_check("): ["evade_threshold(victim) >= number(1, 100)", "SKILL_EVADE, evade_rest())",
                                                              "grapple_threshold(victim) >= number(1, 100)", "CharWait(ch, takedown_evade_lag())"],
    ("melee_damage", "fight.c", "int melee_damage("): ["flank_damage_modifier()", "circle_damage_modifier()", "dreadnaught_attack_factor(paf)",
                                                       "dreadnaught_melee_defense(live_rolls, paf)"],
    ("do_mount", "mount.c", "void do_mount("): ["mounted_combat_mount_threshold(ch) < number(0, 100)"],
    ("do_awareness", "new_skills.c", "void do_awareness("): ["duration = awareness_max_duration(ch, skl_lvl)", "duration = awareness_rolled_duration(live_rolls, duration)"],
    ("berserk", "actoth.c", "void berserk("): ["berserk_str_max(live_rolls, ch, berserk_quality)", "berserk_con_max(live_rolls, ch, berserk_quality)",
                                               "berserk_int(ch)", "berserk_wis(ch, berserk_quality)", "berserk_combat_pulse(ch, berserk_quality)",
                                               "berserk_pow_max(live_rolls, ch, berserk_quality)", "berserk_hit_points(ch)"],
    ("do_berserk", "actoth.c", "void do_berserk("): ["CharWait(ch, berserk_stop_lag(ch))", "duration = berserk_duration(ch)", "CharWait(ch, berserk_lag(ch))",
                                                     "GET_MAX_HIT(ch) * berserk_stop_wounded_share()"],
    ("do_rampage", "actoth.c", "void do_rampage("): ["af.duration = rampage_duration()", "CharWait(ch, rampage_lag())"],
    ("do_infuriate", "actoth.c", "void do_infuriate("): ["af.duration = infuriate_duration()", "CharWait(ch, infuriate_lag())", "infuriate_str_max(ch, false)", "infuriate_str_max(ch, true)",
                                                         "infuriate_con_max(ch, false)", "infuriate_con_max(ch, true)", "infuriate_agi(ch, false)", "infuriate_agi(ch, true)",
                                                         "infuriate_dex(ch, false)", "infuriate_dex(ch, true)"],
    ("do_sneak", "actoth.c", "void do_sneak("): ["CharWait(ch, sneak_lag())", "af.duration = sneak_duration(ch)", "sneak_agility_bonus(ch)"],
    ("do_hide", "actoth.c", "void do_hide("): ["CharWait(ch, hide_lag())", "hide_agility_bonus(ch)", "af.duration = ambush_duration()"],
    ("do_steal", "actoth.c", "void do_steal("): ["CharWait(ch, steal_lag())"],
    ("do_climb", "actoth.c", "void do_climb("): ["af.duration = climb_duration()"],
    ("do_blood_scent", "actoth.c", "void do_blood_scent("): ["CharWait(ch, blood_scent_failed_lag())", "CharWait(ch, blood_scent_lag())", "af.duration = blood_scent_duration(ch)"],
    ("ageCorpse", "actinf.c", "int ageCorpse("): ["maxErrorPercent = age_corpse_error_percent(ch)"],
    ("do_examine", "actinf.c", "void do_examine("): ["CharWait(ch, legend_lore_lag())"],
    ("do_pick", "actmove.c", "void do_pick("): ["affect_timer(ch, pick_lock_rest(), SKILL_PICK_LOCK)", "CharWait(ch, pick_lock_lag())"],
    ("bard_protection", "bard.c", "void bard_protection(int"): ["bard_protection_globe_level()", "bard_protection_minor_globe_level()", "bard_protection_skin_level()", "af.modifier = bard_protection_ac(l, empower)"],
    ("do_track", "track.c", "void do_track(P_char ch, char *arg, int /*cmd*/) // do_track_not_in_use"): ["CharWait(ch, track_lag())", "CharWait(ch, track_scan_lag())", "CharWait(ch, track_abandon_lag())"],
}
# Handlers with several paths: after each source fragment, the next call of that kind
# (the text up to its last space, such as "CharWait(ch,") must be this helper, so a helper
# moved onto another path fails even though the handler still calls it somewhere.
BRANCHES = {
    ("actoff.c", "float takedown_check("): [("cannot respond to your attack", "CharWait(ch, takedown_sleeping_target_lag())"),
                                            ("TAKEDOWN_EVADE", "CharWait(ch, takedown_evade_lag())")],
    ("actoff.c", "void lance_charge("): [("IS_OP_GOLEM(victim)", "CharWait(ch, lance_charge_lag())"),
                                         ("You misjudge the distance", "CharWait(ch, lance_charge_topple_lag())"),
                                         ("effect = number(0, 4)", "CharWait(victim, lance_charge_target_lag())"),
                                         ("is knocked to the ground", "CharWait(victim, lance_charge_knockdown_lag())")],
    ("actoff.c", "void kick("): [("IS_CENTAUR(ch)", "CharWait(ch, kick_quick_lag())"), ("kick_quick_lag()", "CharWait(ch, kick_lag(live_rolls))"),
                                 ("flies in, crashing", "CharWait(victim, kick_room_lag())"),
                                 ("forced_rebound_messages", "Stun(victim, ch, kick_wall_stun(live_rolls), TRUE)"),
                                 ("forced_rebound_messages", "CharWait(victim, kick_wall_lag())"),
                                 ("nimble kick slams", "Stun(victim, ch, kick_groin_stun(live_rolls), TRUE)"),
                                 ("nimble kick slams", "CharWait(victim, kick_groin_lag())")],
    ("actoff.c", "void do_dragon_strike("): [("knockdown_chance = 0", "CharWait(ch, dragon_strike_lag())"),
                                             ("You face plant hard", "CharWait(ch, dragon_strike_face_plant_lag())")],
    ("actoff.c", "void do_headbutt("): [("Headbutt requires you", "CharWait(ch, headbutt_position_lag())"),
                                        ("Your head passes through", "CharWait(ch, headbutt_immaterial_lag())"),
                                        ("far too skilled", "CharWait(ch, headbutt_refused_lag())"),
                                        ("still spinning in circles", "CharWait(ch, headbutt_refused_lag())"),
                                        ("dam = headbutt_backfire_damage", "af.duration = headbutt_backfire_rest()"),
                                        ("dam = headbutt_backfire_damage", "CharWait(ch, headbutt_backfire_lag())"),
                                        ("dam = headbutt_miss_damage", "af.duration = headbutt_miss_rest()"),
                                        ("dam = headbutt_miss_damage", "CharWait(ch, headbutt_miss_lag())"),
                                        ("headbutt_hit_damage(", "CharWait(ch, headbutt_hit_lag())"),
                                        ("headbutt_hit_damage(", "af.duration = headbutt_hit_rest()")],
    ("actoff.c", "void do_garrote("): [("block your advance", "CharWait(ch, garrote_miss_lag())"),
                                       ("StopCasting(victim)", "CharWait(ch, garrote_hit_lag())")],
    ("actoff.c", "void bash("): [("avoids being bashed by", "CharWait(ch, bash_target_down_lag())"), ("too huge for you to move", "CharWait(ch, bash_size_lag())"),
                                 ("just too small", "CharWait(ch, bash_size_lag())"), ("skewer_down_damage(live_rolls)", "CharWait(victim, skewer_down_target_lag())"),
                                 ("skewer_down_damage(live_rolls)", "CharWait(ch, skewer_down_lag())"), ("percent_chance == TAKEDOWN_PENALTY", "CharWait(ch, bash_takedown_penalty_lag())"),
                                 ("rolled > (percent_chance * 3)", "CharWait(ch, bash_miss_lag(true))"), ("bash_miss_lag(true)", "CharWait(ch, bash_miss_lag(false))"),
                                 ("dmg = bash_damage(live_rolls, ch)", "CharWait(ch, bash_hit_lag())"), ("skewer_bash_damage(live_rolls)", "CharWait(victim, skewer_bash_lag())"),
                                 ("skewer_bash_damage(live_rolls)", "CharWait(ch, skewer_bash_lag())")],
    ("actoff.c", "void parlay("): [("You convince $N&+W to lay down", "CharWait(ch, parlay_success_lag())"), ("stop the duel with you", "CharWait(ch, parlay_success_lag())"),
                                   ("You fail to spread", "CharWait(ch, parlay_failure_lag())")],
    ("actoff.c", "void do_tackle("): [("too hefty to tackle", "CharWait(ch, tackle_body_lag())"), ("way too small", "CharWait(ch, tackle_size_lag())"),
                                      ("way too big", "CharWait(ch, tackle_size_lag())"), ("SET_POS(vict, POS_SITTING", "CharWait(ch, tackle_lag())"),
                                      ("SET_POS(vict, POS_SITTING", "CharWait(vict, tackle_lag())"), ("is down already", "CharWait(ch, tackle_lag())"),
                                      ("SET_POS(ch, POS_KNEELING", "CharWait(ch, tackle_lag())"), ("SET_POS(ch, POS_PRONE", "Stun(ch, ch, tackle_self_stun(), FALSE)"),
                                      ("SET_POS(ch, POS_PRONE", "CharWait(ch, tackle_prone_lag())")],
    ("actoff.c", "void maul("): [("percent_chance == TAKEDOWN_PENALTY", "CharWait(ch, maul_penalty_lag())"), ("slam your head into $N", "CharWait(ch, maul_failed_lag())"),
                                 ("bitch slap", "CharWait(ch, maul_failed_lag())"), ("SPEC_MAULER) || IS_ELITE(ch)", "CharWait(victim, maul_target_lag(true))"),
                                 ("SPEC_MAULER) || IS_ELITE(ch)", "CharWait(ch, maul_hit_lag(true))"), ("SPEC_MAULER) || IS_ELITE(ch)", "set_short_affected_by(ch, SKILL_BASH, maul_rest(true))"),
                                 ("maul_rest(true)", "CharWait(victim, maul_target_lag(false))"), ("maul_rest(true)", "CharWait(ch, maul_hit_lag(false))"),
                                 ("maul_rest(true)", "set_short_affected_by(ch, SKILL_BASH, maul_rest(false))"), ("when you hit the ground", "CharWait(ch, maul_failed_lag())")],
    ("actoff.c", "void do_springleap("): [("percent_chance == TAKEDOWN_PENALTY", "CharWait(ch, springleap_failed_lag())"), ("not quite the right size", "CharWait(ch, springleap_failed_lag())"),
                                          ("land on your head", "CharWait(ch, springleap_failed_lag())"), ("tackles the ground with", "CharWait(ch, springleap_failed_lag())"),
                                          ("SET_POS(vict, POS_SITTING", "CharWait(vict, springleap_target_lag())"), ("grabs your leg", "CharWait(ch, springleap_fall_lag())"),
                                          ("springleap_fall_lag()", "CharWait(ch, springleap_lag())")],
    ("actoff.c", "void do_trip("): [("you fall on yer ass", "CharWait(ch, trip_foiled_lag())"), ("percent_chance == TAKEDOWN_PENALTY", "CharWait(ch, trip_foiled_lag())"),
                                    ("manages to trip up", "CharWait(ch, trip_miss_lag())"), ("tripping you", "CharWait(vict, trip_target_lag())"), ("tripping you", "CharWait(ch, trip_lag())")],
    ("actoff.c", "void gaze("): [("small mirror", "CharWait(ch, gaze_refused_lag())"), ("eyeless like you", "CharWait(ch, gaze_refused_lag())"),
                                 ("completely immune to the fear", "CharWait(ch, gaze_refused_lag())"), ("is already &+Yterrifed", "CharWait(ch, gaze_resisted_lag())"),
                                 ("They can't see anything", "CharWait(ch, gaze_refused_lag())"), ("hiss a deep monotone", "CharWait(ch, gaze_resisted_lag())"),
                                 ("but $E's just too tall", "CharWait(ch, gaze_size_lag())"), ("but $E's just too short", "CharWait(ch, gaze_size_lag())"),
                                 ("too far away for you to lock", "CharWait(ch, gaze_lag())")],
    ("actoff.c", "void restrain("): [("way too much fun", "CharWait(ch, restrain_refused_lag())"), ("cannot be restrained", "CharWait(ch, restrain_refused_lag())"),
                                     ("appears to be paralyzed", "CharWait(ch, restrain_resisted_lag())"), ("simply shrugs them away", "CharWait(ch, restrain_resisted_lag())"),
                                     ("easily breaks free of your", "CharWait(ch, restrain_resisted_lag())"), ("easily evades your", "CharWait(ch, restrain_resisted_lag())")],
    ("actoff.c", "void do_legsweep("): [("take your own legs out", "CharWait(ch, legsweep_size_lag())"), ("massive shin", "CharWait(ch, legsweep_size_lag())"),
                                        ("SET_POS(vict, POS_SITTING", "CharWait(ch, legsweep_lag())"), ("land on $s ass.", "CharWait(ch, legsweep_lag())")],
    ("actoth.c", "void do_berserk("): [("Your blood cools", "CharWait(ch, berserk_stop_lag(ch))"), ("You fail to evoke", "CharWait(ch, berserk_lag(ch))")],
    ("actoth.c", "void do_blood_scent("): [("cant smell anything", "CharWait(ch, blood_scent_failed_lag())"), ("almost taste it", "CharWait(ch, blood_scent_failed_lag())"),
                                           ("You grin evilly", "CharWait(ch, blood_scent_lag())")],
    ("track.c", "void do_track("): [("You abandon the hunt", "CharWait(ch, track_abandon_lag())"), ("You attempt your skills", "CharWait(ch, track_lag())")],
}
# The page says a takedown's evade lag adds nothing, so the longer wait must already be running.
LAG_BEFORE_TAKEDOWN = {"void kick(": ["CharWait(ch, kick_quick_lag())", "CharWait(ch, kick_lag(live_rolls))"],
                       "void do_dragon_strike(": ["CharWait(ch, dragon_strike_lag())"]}

SKILLS = [line.split() for line in CONVERTED.split("\n") if line.strip()]

HARNESS = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "item/objmisc.h"
#include "magic/spells.h"
#include "abilities/abilities.h"
#include "world/falling_policy.h"
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

#define MAX_ROOMS 100
#define MAX_CHANCE_TO_CONTROL_FLEE 95

void randomize(uint64_t seed);

static std::map<int, int> ratings;
int GET_CHAR_SKILL_P(P_char, int skill) { auto it = ratings.find(skill); return it == ratings.end() ? 0 : it->second; }
static bool innate_sneak;
bool has_innate(P_char, int innate) { return innate == INNATE_SNEAK && innate_sneak; }
float get_property(const char *, double fallback) { return (float)fallback; }
int get_property(const char *, int fallback) { return fallback; }
int STAT_INDEX(int v) { return std::min(51, std::max(0, v / 3)); }
struct str_app_type str_app[52];
struct agi_app_type agi_app[52];

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

// Handler code before its numbers moved into shared functions.
static int old_lance(P_obj weapon, int level) {
    int dam = dice(weapon->value[2], weapon->value[1]) + weapon->value[2];
    dam = (int)(dam * ((double)level) / 100 + 1);
    dam *= MAX(2, (int)(level / 5));
    return dam;
}
static int old_kick(P_char ch, bool quick) {
    int dam = MAX((int)(GET_C_STR(ch) / 2), GET_CHAR_SKILL(ch, SKILL_MARTIAL_ARTS)) + GET_CHAR_SKILL(ch, SKILL_KICK);
    dam = number((int)(dam / 2), dam);
    dam = (int)(dam * get_property("kick.damage.modifier", 1.000));
    if (quick)
        dam = (dam * 2 * GET_LEVEL(ch)) / 60;
    return dam;
}
static int new_kick(const Rolls &rolls, P_char ch, bool quick) {
    int dam = kick_scaled_damage(kick_rolled_damage(rolls, kick_base_damage(ch)));
    if (quick)
        dam = kick_quick_damage(dam, GET_LEVEL(ch));
    return dam;
}
static int old_headbutt(P_char ch) {
    float dam = (float)GET_CHAR_SKILL(ch, SKILL_HEADBUTT) / 2. + number(20, 30);
    dam = (dam * (float)GET_C_STR(ch)) / 180.;
    dam = dam * (GET_LEVEL(ch) / 2 + 28.) / 56.;
    dam *= get_property("skill.headbutt.damfactor", 1.000);
    if (GET_RACE(ch) == RACE_MINOTAUR)
        dam *= get_property("damage.headbutt.damBonusMinotaur", 1.500);
    if (GET_RACE(ch) == RACE_TIEFLING)
        dam *= get_property("damage.headbutt.damBonusTiefling", 1.250);
    return (int)dam;
}
static int old_sneaky(P_char ch, P_obj weapon, int skill) {
    int dam = (dice(weapon->value[1], MAX(1, weapon->value[2])) + weapon->value[2]);
    dam += str_app[STAT_INDEX(GET_C_STR(ch))].todam + GET_C_DEX(ch) / 4;
    dam = (int)(dam * number(25, 30) * (1 + ((double)GET_LEVEL(ch)) / MAXLVLMORTAL) * (((double)skill) / 100));
    if (GET_SPEC(ch, CLASS_ROGUE, SPEC_THIEF))
        dam /= 16 * 4;
    else
        dam /= 20 * 4;
    return dam;
}
// As event_sneaky_strike draws them: the weapon's roll, then the multiplier.
static int new_sneaky(const Rolls &rolls, P_char ch, P_obj weapon, int skill) {
    const int dam = sneaky_strike_weapon_damage(rolls, weapon);
    return sneaky_strike_damage(ch, dam, sneaky_strike_multiplier(rolls), skill);
}
static int old_backstab(P_char ch, int skill, P_obj weapon) {
    int dice_mult, dam = 0;
    float dice_mod = get_property("backstab.diceMultiplier", 1.000);
    float final_mult = get_property("backstab.finalMultiplier", 1.000);
    float damroll_mult = get_property("backstab.DamrollMultiplier", 0.500);
    float strdex_mod = get_property("backstab.StrDexMultiplier", 0.500);
    dam = (int)((float)GET_DAMROLL(ch) * damroll_mult);
    dam += (GET_C_DEX(ch) + GET_C_STR(ch)) * strdex_mod;
    dam += (number(10, GET_C_LUK(ch)) / 10);
    dam = (dam * (skill + 100)) / 200;
    dice_mult = (int)(weapon->value[1] + (weapon->value[2] / 2)) / 2;
    dice_mult += weapon->value[1] + (weapon->value[1] / 2);
    float level_mult = .50 + (float)GET_LEVEL(ch) / 112.;
    dam = (int)dam * (dice_mult * dice_mod);
    dam = (int)dam * level_mult;
    dam = (int)dam * final_mult;
    return dam;
}
static int old_maul(P_char ch, bool mauler) {
    int dam = dice(MIN(30, GET_LEVEL(ch)), 6) * (get_property("skill.maul.damfactor", 1.000));
    if (mauler)
        dam *= 1.5;
    return dam;
}
static int new_maul(const Rolls &rolls, P_char ch, bool mauler) {
    int dam = maul_damage(rolls, ch);
    if (mauler)
        dam = maul_mauler_damage(dam);
    return dam;
}
static const std::pair<int, int> combination_stages[] = { {1, 30}, {30, 60}, {40, 70}, {50, 90}, {60, 100}, {60, 120}, {100, 150} };

struct Viewer { const char *name; uint m_class; int spec; int race; };
static const Viewer viewers[] = {
    { "warrior", CLASS_WARRIOR, 0, RACE_HUMAN },
    { "guardian", CLASS_WARRIOR, SPEC_GUARDIAN, RACE_HUMAN },
    { "thief", CLASS_ROGUE, SPEC_THIEF, RACE_HUMAN },
    { "assassin", CLASS_ROGUE, SPEC_ASSASSIN, RACE_HUMAN },
    { "mercenary", CLASS_MERCENARY, 0, RACE_MINOTAUR },
    { "bard", CLASS_BARD, 0, RACE_HUMAN },
    { "monk", CLASS_MONK, SPEC_WAYOFDRAGON, RACE_HUMAN },
    { "berserker", CLASS_BERSERKER, SPEC_MAULER, RACE_HUMAN },
    { "dwarf berserker", CLASS_BERSERKER, 0, RACE_MOUNTAIN },
    { "dragoon", CLASS_DRAGOON, SPEC_DRAGON_LANCER, RACE_HUMAN },
    { "hunter", CLASS_DRAGOON, SPEC_DRAGON_HUNTER, RACE_HUMAN },
    { "deathlord", CLASS_DREADLORD, SPEC_DEATHLORD, RACE_LICH },
    { "centaur", CLASS_RANGER, 0, RACE_CENTAUR },
    { "demon", CLASS_WARRIOR, 0, RACE_DEMON },
};

static obj_data dagger, lance, shield;
static pc_only_data pc_data;
static char_data viewer(const Viewer &v, int level, int stat = 100) {
    char_data ch{};
    ch.player.m_class = v.m_class;
    ch.player.spec = v.spec;
    ch.player.race = v.race;
    ch.player.level = level;
    ch.points.max_hit = 500;
    ch.points.damroll = 20;
    ch.only.pc = &pc_data;
    ch.curr_stats.Str = ch.curr_stats.Dex = ch.curr_stats.Agi = ch.curr_stats.Int = stat;
    ch.curr_stats.Pow = ch.curr_stats.Luk = stat;
    ch.base_stats.Str = ch.base_stats.Con = ch.base_stats.Int = stat;
    ch.base_stats.Wis = ch.base_stats.Agi = ch.base_stats.Dex = ch.base_stats.Pow = stat;
    return ch;
}

static void set_ratings(int rating) {
    ratings.clear();
    for (int skill : { SKILLS })
        ratings[skill] = rating;
}

struct Page { const char *name; AbilityFacts facts; };
static const Page pages[] = {
PAGES
};

static bool contains(const std::string &text, const char *lines) {
    const size_t length = std::strlen(lines);
    size_t at = 0;
    while ((at = text.find(lines, at)) != std::string::npos) {
        if ((at == 0 || text[at - 1] == '\n') && (length == 0 || lines[length - 1] == '\n'))
            return true;
        ++at;
    }
    return false;
}
#define HAS(page, lines)                                                       \
    do {                                                                       \
        const std::string text = page(&ch);                                    \
        if (!contains(text, lines)) {                                          \
            std::fprintf(stderr, #page " lacks:\n%s\ngot:\n%s", lines, text.c_str()); \
            std::abort();                                                      \
        }                                                                      \
    } while (0)

static void sweep_pages() {
    bool bad = false;
    dagger.type = lance.type = ITEM_WEAPON;
    dagger.value[0] = WEAPON_DAGGER; dagger.value[1] = 2; dagger.value[2] = 4;
    lance.value[0] = WEAPON_LANCE; lance.value[1] = 8; lance.value[2] = 3;
    shield.weight = 12;
    for (const Viewer &v : viewers)
        for (int level = 1; level <= 60; ++level)
            for (int rating : { 0, 1, 19, 50, 90, 99, 100 })
                for (int stat : { 1, 100, 180 })
                    for (int gear = 0; gear < 3; ++gear) {
                        char_data ch = viewer(v, level, stat);
                        set_ratings(rating);
                        ch.equipment[WIELD] = gear == 1 ? &dagger : gear == 2 ? &lance : nullptr;
                        ch.equipment[WEAR_SHIELD] = gear ? &shield : nullptr;
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
                                    line.find("in -") != std::string::npos) {
                                    std::fprintf(stderr, "%s: [%s] %zu\n", page.name, line.c_str(), line.size());
                                    bad = true;
                                }
                        }
                    }
    assert(!bad);
}

static void check_rolls() {
    obj_data weapon{};
    weapon.value[1] = 3; weapon.value[2] = 6;
    shield.weight = 12;
    for (int level : { 1, 10, 30, 50, 56, 60 })
        for (const Viewer &v : viewers) {
            set_ratings(level > 30 ? 100 : level);
            char_data ch = viewer(v, level);
            char_data *c = &ch;
            ch.equipment[WEAR_SHIELD] = &shield;
            const bool quick = IS_DRAGON(c) || IS_CENTAUR(c);
            SAME(number(1, 50), lance_charge_topple_damage(rolls));
            SAME(old_lance(&weapon, level), lance_charge_scaled_damage(lance_charge_weapon_damage(rolls, &weapon), level));
            SAME(dice(20, 5), lance_charge_impale_damage(rolls));
            SAME(dice(15, 5), lance_charge_glance_damage(rolls));
            SAME(dice(20, 6), lance_charge_ram_damage(rolls));
            SAME(dice(30, 6), lance_charge_through_damage(rolls));
            SAME((number(1, level) + level) * 2, charge_damage(rolls, level));
            for (int stage = 0; stage < 7; ++stage) {
                const auto range = combination_stages[stage];
                SAME(number(range.first, range.second), combination_damage(rolls, stage));
            }
            SAME(!number(0, 50), !combination_fumble_roll(rolls));
            SAME(!number(0, 30), !blade_barrage_fumble_roll(rolls));
            SAME(old_kick(c, quick), new_kick(rolls, c, quick));
            SAME((PULSE_VIOLENCE * 3) / 2 + number(-WAIT_SEC, WAIT_SEC), kick_lag(rolls));
            SAME(!number(0, 10), !kick_low_roll(rolls));
            SAME(!number(0, 24), !kick_stun_roll(rolls));
            SAME((PULSE_VIOLENCE * number(4, 9)) / 4, kick_wall_stun(rolls));
            SAME((PULSE_VIOLENCE * number(4, 13)) / 4, kick_groin_stun(rolls));
            SAME(30 + number(1, GET_LEVEL(c)), dragon_strike_damage(rolls, c));
            SAME(number(1, GET_LEVEL(c)), dragon_strike_fall_damage(rolls, c));
            SAME(number(5, 15), headbutt_backfire_damage(rolls));
            SAME(number(1, 8), headbutt_miss_damage(rolls));
            SAME(PULSE_VIOLENCE * number(2, 3), headbutt_knockout(rolls));
            SAME(old_headbutt(c), (int)headbutt_hit_damage(c, headbutt_hit_roll(rolls)));
            SAME((GET_LEVEL(c) - 1) / 11 + number(0, 2), garrote_rounds(rolls, c));
            SAME(dice(GET_LEVEL(c) / 18, 4), garrote_bleed_damage(rolls, c));
            SAME(!number(0, 9), !garrote_stops_casting_roll(rolls));
            SAME(dice(3, 6), sneaky_strike_bleed_damage(rolls));
            SAME(old_sneaky(c, &weapon, 80), new_sneaky(rolls, c, &weapon, 80));
            SAME(number(4, 7), sneaky_strike_bleed_rounds(rolls));
            SAME(number(20, 45), sneaky_strike_drain(rolls));
            SAME(old_backstab(c, 80, &weapon), backstab_damage(c, 80, &weapon, backstab_luck_bonus(rolls, c)));
            SAME(number(1, 20) < 7, backstab_air_aura_roll(rolls) < backstab_air_aura_below());
            SAME((number(-12, 12) + GET_LEVEL(c)) / 1, spinal_tap_damage(rolls, c, false));
            SAME((number(-12, 12) + GET_LEVEL(c)) / 4, spinal_tap_damage(rolls, c, true));
            SAME(dice(20, 10), skewer_down_damage(rolls));
            SAME(dice(45, 10), skewer_bash_damage(rolls));
            SAME(number(50, 150), parlay_elite_penalty(rolls));
            SAME(number(85, 200), parlay_flee_roll(rolls));
            SAME(number(1, 100), parlay_truce_roll(rolls));
            SAME(old_maul(c, false), new_maul(rolls, c, false));
            SAME(old_maul(c, true), new_maul(rolls, c, true));
            SAME(!number(0, 3), !maul_clip_roll(rolls));
            SAME(6 * (number(1, 25) + (ch.equipment[WEAR_SHIELD]->weight)), shieldpunch_damage(rolls, c, 25));
            SAME(number(0, 3) != 0, springleap_plain_roll(rolls) != 0);
            SAME(number(20, 80) + 40, springleap_super_damage(rolls));
            SAME(4 * (5 + dice(1, 5)), call_grave_delay(rolls));
            SAME(BOUNDED(1, (level / 10) - number(0, 5), 6), call_grave_count(level, call_grave_count_roll(rolls)));
            SAME(BOUNDED(6, (GET_LEVEL(c) - number(15, 35)), 42), call_grave_level(c, call_grave_level_roll(rolls)));
            SAME((int)(GET_LEVEL(c) * number(3, 5)), call_grave_hit_points(rolls, c));
            SAME(4 * (GET_LEVEL(c) - 10 + number(0, 20)), call_grave_target_damage(rolls, c));
            SAME((int)(((number(0, 100) + 40)) / 2), gaze_kill_hit_points(rolls, 40));
            SAME((number(0, 100) + 40) / 2, restrain_kill_hit_points(rolls, 40));
            SAME(4 * number(1, 20), shriek_roll_damage(rolls));
            SAME(PULSE_VIOLENCE * ((GET_LEVEL(c) / 14) + number(0, 100 / 50) + 1), dreadnaught_duration(rolls, c, 100));
            for (int skill : { 20, 60, 91, 100 }) {
                struct affected_type paf{};
                paf.level = skill;
                SAME(BOUNDED(20, paf.level, 60) + (paf.level > 90 ? number((paf.level - 90) / 2, paf.level - 90) : 0), dreadnaught_melee_defense(rolls, &paf));
                SAME(BOUNDED(5, paf.level / 5, 20) + (paf.level > 95 ? number(0, paf.level - 95) : 0), dreadnaught_spell_defense(rolls, &paf));
            }
            SAME(number(0, 170), crippling_strike_roll(rolls));
            SAME(number(1, 100) <= 15, legsweep_prone_roll(rolls) <= legsweep_prone_up_to());
            SAME(number(25, 50) * WAIT_SEC, crippling_strike_deaf_duration(rolls));
            SAME(number(10, 25), crippling_strike_best_vitality(rolls));
            SAME(number(5, 25), crippling_strike_second_vitality(rolls));
            SAME(4 * (40 + (dice(2, 20))), crippling_strike_best_damage(rolls));
            SAME(4 * (30 + (dice(2, 20))), crippling_strike_second_damage(rolls));
            SAME(4 * (30 + (dice(1, 20))), crippling_strike_third_damage(rolls));
            SAME(4 * (10 + (dice(1, 20))), crippling_strike_fourth_damage(rolls));
            SAME((ch.base_stats.Str * 1 / 7) + number(-5, 5), berserk_str_max(rolls, c, 2));
            SAME((ch.base_stats.Str * 1 / 10) + number(-5, 5), berserk_str_max(rolls, c, 1));
            SAME(ch.base_stats.Con * 3 / 2 + number(-5, 5), berserk_con_max(rolls, c, 3));
            SAME(ch.base_stats.Con + number(-5, 5), berserk_con_max(rolls, c, 1));
            SAME(ch.base_stats.Pow / 8 + number(-2, 2), berserk_pow_max(rolls, c, 3));
            SAME((ch.base_stats.Pow + 8) / 20 + number(-2, 2), berserk_pow_max(rolls, c, 2));
            SAME(number(1, 4), awareness_rolled_duration(rolls, 4));
        }
}

static void check_pages() {
    dagger.type = lance.type = ITEM_WEAPON;
    dagger.value[0] = WEAPON_DAGGER; dagger.value[1] = 2; dagger.value[2] = 4;
    lance.value[0] = WEAPON_LANCE; lance.value[1] = 8; lance.value[2] = 3;
    shield.weight = 12;
    set_ratings(100);
    char_data ch = viewer(viewers[0], 56);
    HAS(evade_facts, "  Chance to evade a takedown: 33 in 100\n  Before you can evade again: 2 seconds\n"
                     "  Attacker's lag when you evade: 2 seconds, unless already lagged longer\n");
    HAS(grapple_facts, "  Chance to foil a takedown: 16 in 100\n");
    HAS(charge_facts, "  Damage on a hit: 114-224 at your level\n  Vitality: needs and spends 30\n  Your lag: 8 seconds\n"
                      "  Before you can charge again after a hit: 12 seconds\n  Target's lag on a hit: 6 seconds\n"
                      "  Knocked out by a low ceiling: 4 seconds\n");
    HAS(kick_facts, "  Your lag: 5 seconds to 7 seconds\n");
    HAS(kick_facts, "  A target that evades being sent flying adds no lag to yours.\n");
    HAS(kick_facts, "    (only a humanoid 2 or more sizes bigger than you, at most 1 in 11 kicks,\n"
                    "    after the takedown roll)\n");
    assert(kick_facts(&ch).find("incapacitated") == std::string::npos);
    assert(kick_lag(lowest_rolls) >= takedown_sleeping_target_lag() && kick_quick_lag() > takedown_evade_lag());
    HAS(dragon_roar_facts, "  Before your next dragon command if it works: 12 seconds\n");
    assert(dragon_roar_facts(&ch).find("flees") == std::string::npos);
    HAS(dragon_breath_facts, "  Before your next dragon command if it works: 12 seconds\n");
    HAS(switch_opponents_facts, "  If your current opponent can't fight back, you switch for sure, with no lag.\n"
                                "  Your lag otherwise, whether or not you switch: 4.5 seconds\n");
    HAS(whirlwind_facts, "  Blindfighting needed under the blindness spell: 80\n");
    HAS(blade_barrage_facts, "  You must wield a weapon and be fighting. Each later attack also needs a\n"
                             "  roll; a miss ends the barrage.\n");
    HAS(berserk_facts, "  Chance to stop: 101 in 101\n    (never below 30% of your hit points under a PvP delay)\n");
    HAS(rescue_facts, "  Not while blind or in a single-file room.\n");
    HAS(parlay_facts, "  Your score: 156 (rating plus level; luck can raise the rating)\n");
    HAS(tackle_facts, "  Your lag if the target is asleep: 4 seconds (you attack it instead)\n"
                      "  Your lag if the target evades: 2 seconds\n");
    HAS(trip_facts, "  Your lag on a hit: 9 seconds\n  Your lag on a miss: 8 seconds\n"
                    "  Damage to you on a miss: 20, a 25th of your hit points\n");
    HAS(trip_facts, "  Your lag if the target is asleep: 4 seconds (you attack it instead)\n"
                    "  Your lag if the target evades: 2 seconds\n");
    HAS(maul_facts, "  Your lag if the target is asleep: 4 seconds (you attack it instead)\n"
                    "  Your lag if the target evades: 2 seconds\n");
    HAS(circle_facts, "  Chance to get behind the target: 100 in 100\n");
    HAS(taunt_facts, "  Chance: 99 in 100\n  Modifier on the target's fear save: +20\n"
                     "  Target stays on you: 10 seconds, a mob 20 seconds\n  Target's lag: 2 seconds\n  Your lag: 4 seconds\n");
    HAS(flank_facts, "  Chance: 101 in 101\n  Damage on the flanked target: 150% against a standing target, 125% otherwise\n");
    HAS(dreadnaught_facts, "  Chance: 99 in 101\n  Duration: 20 seconds to 28 seconds\n  Melee damage you deal: 60% of normal\n"
                           "  Less melee damage you take: 65-70%\n  Less spell damage you take: 20-25%\n");
    HAS(shriek_facts, "  Sound damage to each target in the room: 204-280\n  If the target saves: 104-180\n"
                      "  Before you can shriek again: 5 minutes\n");
    HAS(crippling_strike_facts, "  Best strike: 15 in 171\n    Damage: 168-320\n") ;
    HAS(rescue_facts, "  Chance: up to 100 in 100\n  Your lag: 4 seconds\n");
    HAS(mounted_combat_facts, "  Chance to mount while fighting: 67 in 101\n  Chance a hit on you lands on your mount: 30 in 101\n"
                              "  Chance to calm a mount that tries to flee: 94 in 100\n");
    HAS(rampage_facts, "  Chance: 100 in 110\n  Blur: 3-4 game hours (3.75-5 minutes)\n  Your lag when it works: 2 seconds\n");
    pc_data.skills[SKILL_TRACK].learned = 100;
    HAS(track_facts, "  Farthest you can track: 33 rooms\n  Your lag: 4 seconds\n"
                     "  Your lag if you abandon the hunt (track stop): 8 seconds\n"
                     "  Your lag after track scan on the map: 4 seconds\n");
    HAS(age_corpse_facts, "  How far your guess can be off: 0% of the corpse's age\n");
    HAS(legend_lore_facts, "  Chance when you examine an item: 100 in 111\n  Your lag when it works: 6 seconds\n");
    HAS(climb_facts, "  Chance to catch yourself when you start to fall: 50 in 100\n");
    HAS(song_protection_facts, "  Armor class: -50 and minus your song level\n"
                               "  It also casts globe of invulnerability on those without it, and minor\n"
                               "  globe on those with it who lack that.\n");
    ch = viewer(viewers[0], 40);
    HAS(song_protection_facts, "  It also casts minor globe of invulnerability on those without it.\n");
    set_ratings(0);
    HAS(song_protection_facts, "  Armor class: minus your song level\n");
    HAS(flank_facts, "  Chance: 0 in 101\n");
    HAS(berserk_facts, "  Chance to stop: 0 in 101\n");
    ch = viewer(viewers[0], 56, 1);
    set_ratings(100);
    HAS(awareness_facts, "  Duration: up to 1 game hour (up to 1.25 minutes)\n");
    ch = viewer(viewers[10], 50); // dragon hunter
    HAS(dragon_roar_facts, "  Chance each other target also flees: 10 in 101, then 100 in 101\n"
                           "    (up to level 55, on a failed fear check; not elites or greater races)\n");
    ch = viewer(viewers[0], 1);
    set_ratings(1);
    HAS(charge_facts, "  Damage on a hit: 4 at your level\n");
    ch = viewer(viewers[0], 50);
    ch.equipment[WIELD] = &lance;
    set_ratings(100);
    HAS(lance_charge_facts, "  Your lag if you topple off your mount: 8 seconds\n  Falling damage if you topple off: 1-50\n"
                            "  Base damage with your lance: 40-140\n  Base damage from another room: 80-280\n");
    ch = viewer(viewers[0], 51);
    ch.equipment[WIELD] = &lance;
    assert(lance_charge_facts(&ch).find("topple") == std::string::npos);
    ch = viewer(viewers[3], 56); // assassin
    ch.equipment[WIELD] = &dagger;
    HAS(backstab_facts, "  Your lag: 1.5 seconds\n  Chance a target's air aura foils it: 6 in 20\n");
    HAS(critical_stab_facts, "  Chance on each stab: 19 in 100\n");
    HAS(critical_stab_facts, "  A critical stab gets past a target that would notice it, but a player you\n"
                             "  stabbed moments ago still takes a quarter of the damage.\n");
    HAS(spinal_tap_facts, "  Chance on each stab that isn't critical: 15 in 100\n  Extra damage: up to 68 at your level\n");
    HAS(garrote_facts, "  Chance: 100 in 105\n  Rounds of bleeding: 5-7 at your level\n  Bleeding per round on a target of your level: 3-12\n");
    ch = viewer(viewers[0], 1);
    set_ratings(0);
    HAS(garrote_facts, "  Rounds of bleeding: 1-2 at your level\n");
    ch = viewer(viewers[4], 56);
    set_ratings(100);
    assert(contains(sneaky_strike_facts(&ch), "  Follow-up: stun an NPC, or take 20-45 vitality from a player\n"));
    ch = viewer(viewers[6], 56); // way of the dragon monk
    assert(contains(springleap_facts(&ch), "  Chance of your dragon leap: 1 in 4\n    Its damage: 60-120\n"));
    assert(contains(combination_facts(&ch), "  Blow 1: 1-30\n  Blow 2 (rating 25): 30-60\n"));
    assert(contains(blade_barrage_facts(&ch), "  Most weapon attacks at your rating: 7\n"));
    ch = viewer(viewers[8], 56); // dwarven berserker
    assert(contains(berserk_facts(&ch), "  Chance to start: 100 in 100\n  Duration: 13 minutes\n  Your lag after trying: 0.5 seconds\n"));
    assert(contains(berserk_facts(&ch), "  Hit points: +100\n"));
    ch = viewer(viewers[12], 50); // centaur
    assert(contains(kick_facts(&ch), "  Your lag: 2.5 seconds\n"));
    assert(contains(kick_facts(&ch), "  Your lag if it leaves a target 2+ sizes off incapacitated: 4 seconds\n"
                                     "    (you attack it again; a sleeper just wakes when the kick lands)\n"));
    assert(kick_facts(&ch).find("Your lag if the target evades") == std::string::npos);
    ch = viewer(viewers[13], 56);
    assert(contains(track_facts(&ch), "  Farthest you can track: no limit\n"));
    innate_sneak = true;
    assert(sneak_facts(&ch) == "  You sneak by nature: starting again always works, with no lag.\n");
    innate_sneak = false;
}

int main() {
    check_rolls();
    check_pages();
    sweep_pages();
    puts("PASS: skills batch 1 shared rolls match the old code and stay in range, facts never roll");
}
'''


def check_sources():
    for head, calls in HANDLER_CALLS.items():
        OTHER_CALLS[(head, "actoff.c", head)] = calls
    for (name, file, head), calls in OTHER_CALLS.items():
        bodies = function_bodies(strip_comments(source(file).read_text()), re.escape(head.split("(")[0]) + r"\s*\(")
        assert bodies, head
        for call in calls:
            assert any(call in body for body in bodies), f"{head} does not call {call}"
    for (file, head), branches in BRANCHES.items():
        bodies = function_bodies(strip_comments(source(file).read_text()), re.escape(head.split("(")[0]) + r"\s*\(")
        assert len(bodies) == 1, head
        for anchor, call in branches:
            at = bodies[0].index(anchor)
            kind = call.rsplit(" ", 1)[0]
            assert bodies[0].find(kind, at) == bodies[0].find(call, at) >= 0, f"{head}: after {anchor!r} the next {kind} is not {call}"
    for head, lags in LAG_BEFORE_TAKEDOWN.items():
        body = function_bodies(strip_comments(source("actoff.c").read_text()), re.escape(head.split("(")[0]) + r"\s*\(")[0]
        for lag in lags:
            assert 0 <= body.index(lag) < body.index("takedown_check("), f"{head}: {lag} must come before takedown_check"
    table = strip_comments(source("abilities.c").read_text())
    header = source("abilities.h").read_text()
    for constant, name, _ in SKILLS:
        assert re.search(rf"case {constant}:\s*return {name}_facts;", table), constant
        assert f"std::string {name}_facts(char_data *ch);" in header, name


def main():
    check_sources()
    functions = [extract_function("utility.c", "int dice(int num, int size)"),
                 extract_function("utility.c", "int BOUNDED(int a, int b, int c)"),
                 extract_function("utility.c", "int GET_CLASS(P_char ch, uint m_class)"),
                 extract_function("falling_policy.c", "bool falling_climb_catches(bool climb_active"),
                 extract_function("actoff.c", "static int takedown_sleeping_target_lag()"),
                 extract_function("actoff.c", "static int takedown_evade_lag()")]
    facts = {}
    for constant, name, file in SKILLS:
        facts.setdefault(file, []).append(name)
    for file in SHARED:
        text = source(file).read_text()
        for name in SHARED[file]:
            match = re.search(rf"^(?:static )?[\w:]+(?: \w+)? \*?{name}\([^;\n]*\)$", text, re.M)
            assert match, name
            functions.append(extract_function(file, match.group(0) + "\n{"))
        for name in facts.get(file, []):
            functions.append(extract_function(file, f"std::string {name}_facts(P_char"))
    functions.insert(0, extract_function("track.c", "int MaxTrackDist(P_char ch)\n{"))
    pages = ",\n".join(f'    {{ "{name}", {name}_facts }}' for _, name, _ in SKILLS)
    skills = ", ".join(sorted({c for c, _, _ in SKILLS} | {"SKILL_MARTIAL_ARTS", "SKILL_SHIELD_COMBAT", "SKILL_ANATOMY", "SKILL_EMPOWER_SONG", "SKILL_INDOMITABLE_RAGE"} - {"SONG_PROTECTION"}))
    build = ROOT / "bin/tests"
    build.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ability-skills-1-", dir=build) as temporary:
        directory = Path(temporary)
        harness = directory / "skills1.cpp"
        harness.write_text(HARNESS.replace("PAGES", pages).replace("SKILLS", skills).replace("FUNCTIONS", "\n".join(functions)))
        binary = directory / "skills1"
        subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-Wno-unused-function",
                        "-ffunction-sections", "-fdata-sections", "-Wl,--gc-sections",
                        "-fsanitize=address,undefined", "-fno-sanitize-recover=undefined",
                        "-Isrc", "-I/usr/include/mysql", "-I/usr/include/libxml2",
                        str(harness), "src/abilities/abilities.c", "src/core/random.c",
                        "-o", str(binary)], cwd=ROOT, check=True)
        subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    main()
