#!/usr/bin/env python3
"""Shared ability numbers, innates batch 1: the active innates.

Builds src/abilities/abilities.c and the real RNG with the shared and facts functions of
this batch, under sanitizers. Each converted roll keeps its pre-conversion expression
below as the oracle: under the same seeds it must give the same value and leave the RNG
at the same draw, and the value must fall inside the range the facts use. Every page is
built for many viewers and levels: it must never roll and every line must fit 79 columns.
Source checks tie every handler to the functions it must call. Properties are the live
values of lib/duris.properties, compared against the file below.
"""
import re
import subprocess
import tempfile
from pathlib import Path

from _paths import ROOT, extract_function, source
from _source_contract import function_bodies, strip_comments

SHARED = {
    "fight.c": "aura_healing_mod enhancement_healing_mod divine_force_damage_mod spawn_npc_roll spawn_player_roll",
    "dam_mods.c": "aura_battlelust_mod",
    "magic/magic.c": "haste_duration",
    "paladins.c": "aura_group_check_interval aura_protection_ac aura_precision_hitroll aura_endurance_moves aura_vigor_hit_points aura_spell_protection_percent",
    "psionics.c": "innate_blast_appear_roll innate_blast_paralysis_roll innate_blast_major_roll innate_blast_duration",
    "new_skills.c": "summon_book_delay summon_totem_hit_points summon_totem_pulse summon_totem_delay summoned_mount_factor summoned_mount_level summoned_mount_hit_points summoned_mount_skeleton_vitality summon_mount_delay summoned_mount_facts summon_horde_most summon_horde_orc_level summon_horde_orc_hit_points summon_horde_delay ogre_roar_roll ogre_roar_worst_duration ogre_roar_hitroll_divisor ogre_roar_best_hitroll_divisor ogre_roar_worst_hitroll_divisor ogre_roar_best_duration ogre_roar_duration ogre_roar_best_ac ogre_roar_ac ogre_roar_threshold",
    "necromancy.c": "spawn_tier_roll remort_innate_lag",
    "actnew.c": "stampede_innate_rest stampede_hit_limit stampede_sure_hit_roll stampede_stun stampede_lag shapechange_levelNeeded shapechange_memory_time shapechange_learn_level shapechange_learn_delay shapechange_shift_lag shapechange_return_lag shapechange_form_hits",
    "actoff.c": "takedown_sleeping_target_lag takedown_evade_lag charge_roll charge_base_chance bodyslam_roll bodyslam_base_chance bodyslam_vitality_cost bodyslam_damage bodyslam_lag bodyslam_slip_lag bodyslam_target_lag bodyslam_slip_stun bodyslam_stun_roll bodyslam_stun bodyslam_slip_roll bodyslam_awareness_duration",
    "innates.c": "get_property_format get_innate_property innate_rest_seconds innate_uses innate_rest_facts innate_spell_facts disappear_innate_lag throw_lightning_damage throw_lightning_delay throw_lightning_lag levitate_innate_lag vampire_bite_lag vampire_bite_damage vampire_bite_stun_roll vampire_bite_stun_threshold vampire_bite_stun vampire_bite_con_duration vampire_bite_con_loss venom_bite_damage venom_bite_poison_tries venom_bite_lag snakebite_delay parasite_bite_damage parasite_bite_saved parasite_bite_disease_roll parasite_bite_lag bite_innate_rest venom_bite_facts gaze_innate_target_lag darkness_innate_lag shift_astral_innate_lag shift_prime_innate_lag faerie_fire_innate_lag ud_invisibility_innate_duration strength_innate_duration strength_innate_bonus strength_innate_lag enlarge_innate_duration enlarge_innate_lag plane_shift_innate_lag charm_animal_innate_lag globe_of_darkness_innate_lag hide_innate_lag project_image_innate_lag fireshield_innate_lag firestorm_innate_lag battle_rage_haste_level battle_rage_lag phantasmal_form_duration phantasmal_form_lag stone_skin_innate_rest stone_skin_innate_lag shade_movement_duration god_call_delay god_call_fury_level god_call_fury_duration god_call_fury_bonus god_call_fury_strength god_call_blessing_duration god_call_protection_duration god_call_peace_roll god_call_rest god_call_choice god_call_blessing_facts god_call_calm_facts god_call_fury_facts doorbash_chance doorbash_roll doorbash_stuck_damage doorbash_success_damage doorbash_failed_damage doorbash_lag doorkick_chance doorkick_roll doorkick_stuck_damage doorkick_success_damage doorkick_failed_damage doorkick_lag conjure_water_spring_life conjure_water_delay conjure_water_lag foundry_forge_life foundry_delay foundry_lag branch_roll branch_chance_cap branch_damage branch_target_lag branch_pet_lag branch_lag webwrap_duration webwrap_lag web_spray_interval web_spray_rest web_spray_lag web_spray_chance web_spray_duration web_spray_drain web_spray_roll web_spray_tear_roll web_spray_tear_threshold summon_imp_home_level summon_imp_level summon_imp_bonus lifedrain_step lifedrain_interval lifedrain_gain immolate_innate_lag fade_counter fade_interval lay_hands_amount lay_hands_revenant_amount aura_innate_lag aura_common_facts aura_percent divine_force_duration divine_force_rest",
}

# Constant, facts name, file holding the facts.
CONVERTED = """
INNATE_AURA_BATTLELUST aura_battlelust innates.c
INNATE_AURA_ENDURANCE aura_endurance innates.c
INNATE_AURA_HEALING aura_healing innates.c
INNATE_AURA_PRECISION aura_precision innates.c
INNATE_AURA_PROTECTION aura_protection innates.c
INNATE_AURA_SPELL_PROTECTION aura_spell_protection innates.c
INNATE_AURA_VIGOR aura_vigor innates.c
INNATE_BATTLE_RAGE battle_rage innates.c
INNATE_BITE bite innates.c
INNATE_BLAST blast psionics.c
INNATE_BRANCH branch innates.c
INNATE_CHARM_ANIMAL charm_animal innates.c
INNATE_CONJURE_WATER conjure_water innates.c
INNATE_DARKNESS darkness innates.c
INNATE_DISAPPEAR disappear innates.c
INNATE_DIVINE_FORCE divine_force innates.c
INNATE_DOORBASH doorbash innates.c
INNATE_DOORKICK doorkick innates.c
INNATE_ENLARGE enlarge innates.c
INNATE_FADE fade innates.c
INNATE_FAERIE_FIRE faerie_fire innates.c
INNATE_FIRESHIELD fireshield innates.c
INNATE_FIRESTORM firestorm innates.c
INNATE_FOUNDRY foundry innates.c
INNATE_GAZE gaze innates.c
INNATE_GLOBE_OF_DARKNESS globe_of_darkness innates.c
INNATE_GOD_CALL god_call innates.c
INNATE_HIDE hide innates.c
INNATE_IMMOLATE immolate innates.c
INNATE_LAY_HANDS lay_hands innates.c
INNATE_LEVITATE levitate innates.c
INNATE_LIFEDRAIN lifedrain innates.c
INNATE_PHANTASMAL_FORM phantasmal_form innates.c
INNATE_PLANE_SHIFT plane_shift innates.c
INNATE_PROJECT_IMAGE project_image innates.c
INNATE_SHADE_MOVEMENT shade_movement innates.c
INNATE_SHADOW_DOOR shadow_door innates.c
INNATE_SHAPECHANGE shapechange actnew.c
INNATE_SHIFT_ASTRAL shift_astral innates.c
INNATE_SHIFT_PRIME shift_prime innates.c
INNATE_STONE stone_skin innates.c
INNATE_STRENGTH strength innates.c
INNATE_SUMMON_IMP summon_imp innates.c
INNATE_THROW_LIGHTNING throw_lightning innates.c
INNATE_UD_INVISIBILITY ud_invisibility innates.c
INNATE_WEBWRAP webwrap innates.c
INNATE_WEB_SPRAY web_spray innates.c
INNATE_ALLY ally necromancy.c
INNATE_REMORT remort necromancy.c
INNATE_SPAWN spawn necromancy.c
INNATE_SUMMON_HOST summon_host necromancy.c
INNATE_OGREROAR ogre_roar new_skills.c
INNATE_SUMMON_BOOK summon_book new_skills.c
INNATE_SUMMON_HORDE summon_horde new_skills.c
INNATE_SUMMON_MOUNT summon_mount new_skills.c
INNATE_SUMMON_TOTEM summon_totem new_skills.c
INNATE_SUMMON_WARG summon_warg new_skills.c
INNATE_STAMPEDE stampede actnew.c
INNATE_BODYSLAM bodyslam actoff.c
INNATE_CALL_GRAVE call_grave actoff.c
INNATE_CHARGE charge actoff.c
"""
INNATES = [line.split() for line in CONVERTED.split("\n") if line.strip()]

# Disabled for mortals (no ADD_*_INNATE line, or a stub) and so on the no-numbers list.
NO_NUMBERS = """INNATE_BARB_BREATH INNATE_DISPEL_MAGIC INNATE_ENGULF INNATE_FIREBALL INNATE_FLURRY
INNATE_MASS_DISPEL INNATE_REDUCE INNATE_SHIFT_ETHEREAL INNATE_SLIME INNATE_TUPOR""".split()

# Every key the pages read. None: lib/duris.properties leaves it to the code's fallback.
PROPERTIES = {
    "innate.paladin_aura.protection_ac_mod": 1.7, "innate.paladin_aura.precision_hitroll_mod": 0.2,
    "innate.paladin_aura.endurance_move_mod": 1.0, "innate.paladin_aura.vigor_hp_mod": 1.0,
    "innate.paladin_aura.protection_spell_mod": 0.5, "innate.paladin_aura.battlelust_mod": 0.2,
    "innate.paladin_aura.healing_mod": 0.2, "enhancement.healing.mod": 1.5,
    "damage.modifier.divineforce": 1.25, "innate.timer.secs.default": 720,
    "innate.timer.secs.conjureWater": 300, "innate.timer.secs.layHands": 720,
    "innate.timer.secs.summonMount": 720, "innate.timer.secs.planeShift": 80,
    "innate.timer.secs.shift_prime": 720, "innate.timer.secs.pyrokinesis": 20,
    "innate.timer.secs.drainLife": 60, "innate.timer.secs.foundry": 120,
    "innate.timer.secs.godCall": 900, "innate.timer.secs.godCallSpec": 300,
    "innate.timer.dura.godCall.Tempus.Cleric": 5, "innate.timer.dura.godCall.Tempus.Other": 3,
    "innate.timer.secs.divineforceAffect": 20, "innate.timer.secs.divineforceTimer": 600,
    "innate.charge.base.chance": 65, "innate.bodyslam.base.chance": 60,
    "mount.summoned.FactorMod": 0.75, "innate.timer.bite": None,
    "innate.timer.secs.stampede": None, "innate.fade.secs.duration": None,
    "innate.shapechange.memory.time": None,
}

# (file, handler): calls the handler's body must make, whitespace removed before matching.
CALLS = {
    ("innates.c", "void do_disappear"): ["CharWait(ch,disappear_innate_lag())"],
    ("innates.c", "void event_throw_lightning"): ["dam=throw_lightning_damage(live_rolls,ch)", "spell_damage(ch,victim,dam,SPLDAM_LIGHTNING,0,&messages)"],
    ("innates.c", "void do_throw_lightning"): ["check_innate_time(ch,INNATE_THROW_LIGHTNING)", "add_event(event_throw_lightning,throw_lightning_delay(),", "CharWait(ch,throw_lightning_lag())"],
    ("innates.c", "void do_levitate"): ["check_innate_time(ch,INNATE_LEVITATE)", "spell_levitate(GET_LEVEL(ch),ch,NULL,0,ch,0)", "CharWait(ch,levitate_innate_lag())"],
    ("innates.c", "void vampire_bite"): ["CharWait(ch,vampire_bite_lag())", "melee_damage(ch,victim,vampire_bite_damage(live_rolls,ch),0,&messages)", "vampire_bite_stun_roll(live_rolls)<vampire_bite_stun_threshold()", "Stun(victim,ch,vampire_bite_stun(),TRUE)", "af.duration=vampire_bite_con_duration(live_rolls)", "af.modifier=vampire_bite_con_loss(ch)"],
    ("innates.c", "void insectbite"): ["raw_damage(ch,victim,venom_bite_damage(live_rolls,ch),RAWDAM_DEFAULT,&messages)", "i=venom_bite_poison_tries(ch)", "CharWait(ch,venom_bite_lag())"],
    ("innates.c", "void event_snakebite"): ["raw_damage(ch,victim,venom_bite_damage(live_rolls,ch),RAWDAM_DEFAULT,&messages)", "i=venom_bite_poison_tries(ch)", "CharWait(ch,venom_bite_lag())"],
    ("innates.c", "void snakebite"): ["add_event(event_snakebite,snakebite_delay(),"],
    ("innates.c", "int parasitebite"): ["damage=parasite_bite_damage(live_rolls,level)", "melee_damage(ch,victim,parasite_bite_saved(damage),0,&messages)", "!parasite_bite_disease_roll(live_rolls,mod)", "CharWait(ch,parasite_bite_lag())"],
    ("innates.c", "void do_bite_target"): ["check_innate_time(ch,INNATE_BITE,bite_innate_rest())"],
    ("innates.c", "void innate_gaze"): ["CharWait(victim,gaze_innate_target_lag())", "saves_spell(tch,SAVING_FEAR)"],
    ("innates.c", "void do_innate_gaze"): ["check_innate_time(ch,INNATE_GAZE)"],
    ("innates.c", "void do_darkness"): ["check_innate_time(ch,INNATE_DARKNESS)", "spell_darkness(GET_LEVEL(ch),ch,0,0,0,0)", "CharWait(ch,darkness_innate_lag())"],
    ("innates.c", "void do_shift_astral"): ["check_innate_time(ch,INNATE_SHIFT_ASTRAL)", "cast_plane_shift(GET_LEVEL(ch),", "CharWait(ch,shift_astral_innate_lag())"],
    ("innates.c", "void do_shift_prime"): ["check_innate_time(ch,INNATE_SHIFT_PRIME)", "CharWait(ch,shift_prime_innate_lag())"],
    ("innates.c", "void do_blast"): ["check_innate_time(ch,INNATE_BLAST)", "spell_innate_blast(GET_LEVEL(ch),ch,0,0,victim,0)"],
    ("psionics.c", "void spell_innate_blast"): ["if(innate_blast_appear_roll(live_rolls))", "!innate_blast_paralysis_roll(live_rolls)&&", "(GET_LEVEL(ch)>25)&&innate_blast_major_roll(live_rolls)", "af.duration=innate_blast_duration(lev)"],
    ("innates.c", "void do_faerie_fire"): ["spell_faerie_fire(GET_LEVEL(ch),ch,NULL,0,victim,0)", "CharWait(ch,faerie_fire_innate_lag())"],
    ("innates.c", "void do_ud_invisibility"): ["check_innate_time(ch,INNATE_UD_INVISIBILITY)", "af.duration=ud_invisibility_innate_duration()"],
    ("innates.c", "void do_strength"): ["check_innate_time(ch,INNATE_STRENGTH)", "af.duration=strength_innate_duration()", "af.modifier=strength_innate_bonus()", "CharWait(ch,strength_innate_lag())"],
    ("innates.c", "void do_enlarge"): ["check_innate_time(ch,INNATE_ENLARGE)", "af.duration=enlarge_innate_duration()", "CharWait(ch,enlarge_innate_lag())"],
    ("innates.c", "void do_plane_shift"): ["check_innate_time(ch,INNATE_PLANE_SHIFT)", "cast_plane_shift(GET_LEVEL(ch),ch,arg,", "CharWait(ch,plane_shift_innate_lag())"],
    ("innates.c", "void do_charm_animal"): ["check_innate_time(ch,INNATE_CHARM_ANIMAL)", "spell_charm_animal(GET_LEVEL(ch),ch,0,0,victim,0)", "CharWait(ch,charm_animal_innate_lag())"],
    ("innates.c", "void do_globe_of_darkness"): ["check_innate_time(ch,INNATE_GLOBE_OF_DARKNESS)", "spell_globe_of_darkness(GET_LEVEL(ch),ch,NULL,SPELL_TYPE_SPELL,ch,0)", "CharWait(ch,globe_of_darkness_innate_lag())"],
    ("innates.c", "void do_innate_hide"): ["check_innate_time(ch,INNATE_HIDE)", "CharWait(ch,hide_innate_lag())"],
    ("innates.c", "void do_project_image"): ["CharWait(ch,project_image_innate_lag())"],
    ("innates.c", "void do_fireshield"): ["spell_fireshield(GET_LEVEL(ch),ch,NULL,0,ch,0)", "CharWait(ch,fireshield_innate_lag())"],
    ("innates.c", "void do_firestorm"): ["spell_firestorm(GET_LEVEL(ch),ch,NULL,0,0,0)", "CharWait(ch,firestorm_innate_lag())"],
    ("innates.c", "void do_dimension_door"): ["check_innate_time(ch,INNATE_SHADOW_DOOR)", "spell_dimension_door(GET_LEVEL(ch),ch,NULL,SPELL_TYPE_SPELL,victim,0)"],
    ("innates.c", "void do_battle_rage"): ["check_innate_time(ch,INNATE_BATTLE_RAGE)", "CharWait(ch,battle_rage_lag())", "spell_haste(battle_rage_haste_level(),ch,0,0,ch,0)"],
    ("innates.c", "void do_phantasmal_form"): ["check_innate_time(ch,INNATE_PHANTASMAL_FORM)", "af.duration=phantasmal_form_duration()", "CharWait(ch,phantasmal_form_lag())"],
    ("innates.c", "void do_stone_skin"): ["check_innate_time(ch,INNATE_STONE,stone_skin_innate_rest())", "spell_stone_skin(GET_LEVEL(ch),ch,0,0,ch,0)", "CharWait(ch,stone_skin_innate_lag())"],
    ("innates.c", "void do_shade_movement"): ["check_innate_time(ch,INNATE_SHADE_MOVEMENT)", "af.duration=shade_movement_duration(ch)"],
    ("innates.c", "void event_tempus"): ["level=god_call_fury_level(ch)", "dura=god_call_fury_duration(ch)", "af.modifier=god_call_fury_bonus(level)", "af1.modifier=god_call_fury_strength()"],
    ("innates.c", "void event_lathander"): ["af.duration=god_call_blessing_duration(level)"],
    ("innates.c", "void event_torm"): ["af.duration=god_call_protection_duration(ch)", "!god_call_peace_roll(live_rolls)&&!IS_ELITE(tch)"],
    ("innates.c", "void do_god_call"): ["duration=god_call_rest(ch)", "check_innate_time(ch,INNATE_GOD_CALL,duration)", "choice=god_call_choice(live_rolls,ch)", "add_event(event_lathander,god_call_delay(),", "add_event(event_torm,god_call_delay(),ch,ch,", "add_event(event_tempus,god_call_delay(),"],
    ("innates.c", "void do_doorbash"): ["chance=doorbash_chance(ch)", "damage(ch,ch,doorbash_stuck_damage(live_rolls),TYPE_UNDEFINED)", "doorbash_roll(live_rolls)<=chance", "damage(ch,ch,doorbash_success_damage(live_rolls),TYPE_UNDEFINED)", "damage(ch,ch,doorbash_failed_damage(live_rolls),TYPE_UNDEFINED)", "CharWait(ch,doorbash_lag())"],
    ("innates.c", "void do_doorkick"): ["chance=doorkick_chance(ch)", "damage(ch,ch,doorkick_stuck_damage(live_rolls),TYPE_UNDEFINED)", "doorkick_roll(live_rolls)<=chance", "damage(ch,ch,doorkick_success_damage(live_rolls),TYPE_UNDEFINED)", "damage(ch,ch,doorkick_failed_damage(live_rolls),TYPE_UNDEFINED)", "CharWait(ch,doorkick_lag())"],
    ("innates.c", "void event_conjure_water"): ["check_innate_time(ch,INNATE_CONJURE_WATER)", "set_obj_affected(spring,conjure_water_spring_life(),TAG_OBJ_DECAY,0)"],
    ("innates.c", "void do_conjure_water"): ["add_event(event_conjure_water,conjure_water_delay(),", "CharWait(ch,conjure_water_lag())"],
    ("innates.c", "void event_foundry"): ["set_obj_affected(forge,foundry_forge_life(),TAG_OBJ_DECAY,0)"],
    ("innates.c", "void do_foundry"): ["check_innate_time(ch,INNATE_FOUNDRY)", "add_event(event_foundry,foundry_delay(),", "CharWait(ch,foundry_lag())"],
    ("innates.c", "void branch"): ["chance=branch_chance_cap(chance)", "chance<branch_roll(live_rolls)", "CharWait(victim,branch_target_lag())", "melee_damage(ch,victim,branch_damage(ch),PHSDAM_NOENGAGE|PHSDAM_NOSHIELDS,&messages)", "CharWait(ch,branch_pet_lag())", "CharWait(ch,branch_lag())"],
    ("innates.c", "void webwrap"): ["af.duration=webwrap_duration(live_rolls)", "CharWait(ch,webwrap_lag())"],
    ("innates.c", "void event_web_spray"): ["add_event(event_web_spray,web_spray_interval(),"],
    ("innates.c", "void do_web_spray"): ["check_innate_time(ch,INNATE_WEB_SPRAY,web_spray_rest())", "CharWait(ch,web_spray_lag())", "chance=web_spray_chance(ch,cagi,vagi)", "web_spray_roll(live_rolls)>chance&&!IS_TRUSTED(ch)", "af.duration=web_spray_duration()", "af.modifier=web_spray_drain(ch)"],
    ("innates.c", "void web_spray_move_check"): ["web_spray_tear_roll(live_rolls)>web_spray_tear_threshold()"],
    ("innates.c", "void do_summon_imp"): ["imp->player.level=summon_imp_home_level(ch)", "imp->player.level=summon_imp_level(ch)", "imp->points.base_hitroll+=summon_imp_bonus()", "imp->points.base_damroll+=summon_imp_bonus()"],
    ("innates.c", "void event_lifedrain"): ["GET_HIT(victim)-=lifedrain_step()", "GET_HIT(ch)+=lifedrain_step()", "gain-=lifedrain_step()", "add_event(event_lifedrain,lifedrain_interval(),"],
    ("innates.c", "void do_lifedrain"): ["intgain=lifedrain_gain(ch)", "check_innate_time(ch,INNATE_LIFEDRAIN)", "add_event(event_lifedrain,lifedrain_interval(),"],
    ("innates.c", "void do_immolate"): ["check_innate_time(ch,INNATE_IMMOLATE)", "cast_as_damage_area(ch,spell_single_incendiary_cloud,GET_LEVEL(ch),victim,", "CharWait(ch,immolate_innate_lag())"],
    ("innates.c", "void event_fade"): ["add_event(event_fade,fade_interval(),"],
    ("innates.c", "void do_fade"): ["fdata.counter=fade_counter()", "add_event(event_fade,fade_interval(),"],
    ("innates.c", "void do_layhand"): ["inthealpoints=lay_hands_amount(live_rolls,ch)", "healpoints=lay_hands_revenant_amount(healpoints)", "check_innate_time(ch,INNATE_LAY_HANDS)", "heal(vict,ch,healpoints,GET_MAX_HIT(vict))"],
    ("innates.c", "void do_aura_protection"): ["do_aura(ch,AURA_PROTECTION)", "CharWait(ch,aura_innate_lag())"],
    ("innates.c", "void do_aura_spell_protection"): ["do_aura(ch,AURA_SPELL_PROTECTION)", "CharWait(ch,aura_innate_lag())"],
    ("innates.c", "void do_aura_precision"): ["do_aura(ch,AURA_PRECISION)", "CharWait(ch,aura_innate_lag())"],
    ("innates.c", "void do_aura_battlelust"): ["do_aura(ch,AURA_BATTLELUST)", "CharWait(ch,aura_innate_lag())"],
    ("innates.c", "void do_aura_healing"): ["do_aura(ch,AURA_HEALING)", "CharWait(ch,aura_innate_lag())"],
    ("innates.c", "void do_aura_endurance"): ["do_aura(ch,AURA_ENDURANCE)", "CharWait(ch,aura_innate_lag())"],
    ("innates.c", "void do_aura_vigor"): ["do_aura(ch,AURA_VIGOR)", "CharWait(ch,aura_innate_lag())"],
    ("innates.c", "void do_divine_force"): ["timer1=divine_force_duration()", "af1.duration=timer1", "timer=divine_force_rest()", "af.duration=timer"],
    ("paladins.c", "void do_aura"): ["add_event(event_apply_group_auras,aura_group_check_interval(),"],
    ("paladins.c", "void event_apply_group_auras"): ["add_event(event_apply_group_auras,aura_group_check_interval(),"],
    ("paladins.c", "void apply_aura"): ["af.modifier=aura_protection_ac(ch)", "af.modifier=aura_precision_hitroll(ch)", "af.modifier=aura_endurance_moves(ch)", "af.modifier=aura_vigor_hit_points(ch)", "af.modifier=aura_spell_protection_percent(ch)"],
    ("fight.c", "int vamp"): ["(aura_healing_mod()*aura_mod(ch,AURA_HEALING))"],
    ("fight.c", "void heal"): ["hits=(int)(hits*enhancement_healing_mod())"],
    ("new_skills.c", "void do_summon_book"): ["add_event(event_summon_book,summon_book_delay(),"],
    ("new_skills.c", "void event_summon_totem"): ["totem->affected[2].modifier=summon_totem_pulse()", "totem->affected[1].modifier=summon_totem_hit_points()"],
    ("new_skills.c", "void do_summon_totem"): ["add_event(event_summon_totem,summon_totem_delay(),"],
    ("new_skills.c", "void mount_summoning_thing"): ["factor=summoned_mount_factor(live_rolls,ch)", "mount->player.level=summoned_mount_level(factor)", "GET_HIT(mount)=summoned_mount_hit_points(ch,factor)", "GET_MAX_HIT(mount)=summoned_mount_hit_points(ch,factor)", "summoned_mount_skeleton_vitality(live_rolls)"],
    ("new_skills.c", "void do_summon_mount"): ["check_innate_time(ch,INNATE_SUMMON_MOUNT)", "sumtime=summon_mount_delay(live_rolls,ch)"],
    ("new_skills.c", "void do_summon_warg"): ["check_innate_time(ch,INNATE_SUMMON_WARG)", "sumtime=summon_mount_delay(live_rolls,ch)"],
    ("new_skills.c", "void orc_summoning_thing"): ["max_respond=summon_horde_most(ch)", "orc->player.level=summon_horde_orc_level()", "GET_HIT(orc)=summon_horde_orc_hit_points()"],
    ("new_skills.c", "void do_summon_orc"): ["check_innate_time(ch,INNATE_SUMMON_HORDE)", "sumtime=summon_horde_delay(live_rolls,ch)"],
    ("new_skills.c", "void do_ogre_roar"): ["check_innate_time(ch,INNATE_OGREROAR)", "temp=BOUNDED(1,ogre_roar_roll(live_rolls)+temp,101)", "if(temp<ogre_roar_threshold())", "GET_HITROLL(vict)*GET_LEVEL(ch)/ogre_roar_hitroll_divisor()", "GET_HITROLL(vict)*GET_LEVEL(ch)/ogre_roar_best_hitroll_divisor()", "GET_HITROLL(ch)*GET_LEVEL(vict)/ogre_roar_worst_hitroll_divisor()", "af.duration=ogre_roar_worst_duration(temp)", "af.duration=ogre_roar_best_duration(temp)", "af.duration=ogre_roar_duration(temp)", "af.modifier=ogre_roar_best_ac(ch)", "af.modifier=ogre_roar_ac(ch)"],
    ("necromancy.c", "void spawn_raise_undead"): ["introll=spawn_tier_roll(live_rolls,corpse->value[CORPSE_LEVEL])"],
    ("necromancy.c", "void do_summon_host"): ["affect_timer(ch,exhume_rest(skl),SKILL_EXHUME)", "CharWait(ch,summon_host_lag(ch))", "obj1->value[CORPSE_LEVEL]=exhume_corpse_level(live_rolls,ch)"],
    ("necromancy.c", "void do_remort"): ["CharWait(ch,remort_innate_lag())"],
    ("actnew.c", "void do_stampede"): ["check_innate_time(ch,INNATE_STAMPEDE,stampede_innate_rest())", "count>=stampede_hit_limit(live_rolls)", "(stampede_sure_hit_roll(live_rolls)&&", "Stun(vict,ch,stampede_stun(),TRUE)", "CharWait(ch,stampede_lag(count))"],
    ("actnew.c", "void event_learn_shape"): ["afp->duration=shapechange_memory_time()", "af.duration=shapechange_memory_time()"],
    ("actnew.c", "void shapechange_learn"): ["intchLevel=shapechange_learn_level(ch)", "add_event(event_learn_shape,shapechange_learn_delay(),"],
    ("actoff.c", "void do_charge"): ["percent_chance=charge_base_chance()", "charge_roll(live_rolls)<=(int)percent_chance"],
    ("actoff.c", "void bodyslam"): ["percent_chance=bodyslam_base_chance()", "percent_chance>=bodyslam_roll(live_rolls)", "GET_VITALITY(ch)<bodyslam_vitality_cost()", "GET_VITALITY(ch)-=bodyslam_vitality_cost()", "CharWait(ch,bodyslam_lag())", "CharWait(victim,bodyslam_target_lag())", "damage(ch,victim,bodyslam_damage(ch),SKILL_BODYSLAM)", "if(bodyslam_stun_roll(live_rolls))Stun(victim,ch,bodyslam_stun(live_rolls),TRUE)", "CharWait(ch,bodyslam_slip_lag())", "if(bodyslam_slip_roll(live_rolls))", "Stun(ch,ch,bodyslam_slip_stun(),FALSE)", "af.duration=bodyslam_awareness_duration()"],
}

# The pages of a level 56 human paladin with 100 in every stat, whole.
PALADIN_PAGES = r"""
--- aura_battlelust
  Damage dealt: +11.2% at your level
  Your lag: 4 seconds
  New group members join within: 5 seconds
  It reaches you and your group in the room, while you stand awake.
  One aura at a time: a new one ends the last. It needs no rest.
--- aura_endurance
  Moves: +56 at your level
  Your lag: 4 seconds
  New group members join within: 5 seconds
  It reaches you and your group in the room, while you stand awake.
  One aura at a time: a new one ends the last. It needs no rest.
--- aura_healing
  Healing received: +11.2% at your level
  Your lag: 4 seconds
  New group members join within: 5 seconds
  It reaches you and your group in the room, while you stand awake.
  One aura at a time: a new one ends the last. It needs no rest.
  Players only, and not healers or heals cast by healers.
  No bonus under regeneration or accelerated healing.
--- aura_precision
  Hitroll: +11 at your level
  Your lag: 4 seconds
  New group members join within: 5 seconds
  It reaches you and your group in the room, while you stand awake.
  One aura at a time: a new one ends the last. It needs no rest.
--- aura_protection
  Armor class: -95 at your level
  Your lag: 4 seconds
  New group members join within: 5 seconds
  It reaches you and your group in the room, while you stand awake.
  One aura at a time: a new one ends the last. It needs no rest.
--- aura_spell_protection
  Spell damage taken: 25% less at your level
  Your lag: 4 seconds
  New group members join within: 5 seconds
  It reaches you and your group in the room, while you stand awake.
  One aura at a time: a new one ends the last. It needs no rest.
--- aura_vigor
  Hit points: +56 at your level
  Your lag: 4 seconds
  New group members join within: 5 seconds
  It reaches you and your group in the room, while you stand awake.
  One aura at a time: a new one ends the last. It needs no rest.
--- battle_rage
  Effect: casts haste on you at level 60
  Duration: 10-11 game hours (12.5-13.75 minutes)
  Uses: 1 before it rests
  Rest: all uses return 12 minutes after the first
  Your lag: 8 seconds
  If you are slowed it only removes the slow, and if hasted it does nothing.
--- bite
  Damage: 56-168 at your level, 56
  Poison tries: 5, ending when a spell save fails
  Your lag: 4 seconds on a miss, or if it lands and no one dies
  Level and agility against the target's decide if it lands.
  Gods and the undead shrug off the poison.
  Uses: 1 before it rests
  Rest: all uses return 12 seconds after the first
  It goes by your race or shape: vampires, snakes and parasites differ.
--- blast
  Paralysis chance: 1 in 3, if a power save also fails
  Duration: 2-3 game hours (2.5-3.75 minutes) at your level
  Major instead of minor: 1 in 2
  You appear: 1 in 2 if you are unseen
  Uses: 1 before it rests
  Rest: all uses return 12 minutes after the first
  Freedom of movement, paralysis immunity and existing paralysis stop it.
  A shopkeeper ignores it, but the use is still spent. It has no lag.
--- branch
  Damage: 112 at your level
  Chance: from 40 in 100 to 95 in 100
  Target's lag on a hit: 8 seconds
  Your lag: 8 seconds, or 16 seconds as a pet
  Your level, strength and dexterity against the target's level, constitution
  and agility set the chance, and being bigger helps.
  A hit leaves the target prone. Its defenses apply to the damage after.
  A target bigger than you can't be lifted, with no lag.
  A target not standing always avoids it.
--- charm_animal
  Effect: casts charm animal at your level
  Page of spell 187
  Uses: 1 before it rests
  Rest: all uses return 12 minutes after the first
  Your lag: 4 seconds
--- conjure_water
  Effect: a spring rises from the ground
  It appears after: 4 seconds
  It lasts: 15 minutes
  Uses: 1 before it rests
  Rest: all uses return 5 minutes after the first
  Your lag: 4 seconds
  Stay in the room: the use is spent when the spring appears.
  One spring to a room.
--- darkness
  Effect: casts darkness at your level
  Page of spell 99
  Uses: 1 before it rests
  Rest: all uses return 12 minutes after the first
  Your lag: 4 seconds, even if too tired
--- disappear
  Effect: hides you
  Your lag: 4 seconds
  Only while someone in the room is fighting.
--- divine_force
  Melee damage: 25% more
  Duration: 20 seconds
  Before you can use it again: 10 minutes
  It has no lag.
--- doorbash
  Chance: 96 in 100 at your level
  You take if the door breaks: 2-20
  You take if it holds: 3-24
  You take from a door that can't break: 3-30
  Your lag: 8 seconds if you live
  Pickproof and unbreakable doors never give.
  A broken door lets you through. Not while riding.
--- doorkick
  Chance: 100 in 100 at your level
  You take if the door breaks: 2-10
  You take if it holds: 2-20
  You take from a door that can't break: 2-20
  Your lag: 8 seconds if you live
  Pickproof and unbreakable doors never give.
  You stay where you are. Not while riding.
--- enlarge
  Effect: you grow one size
  Duration: 5-6 game hours (6.25-7.5 minutes)
  Uses: 1 before it rests
  Rest: all uses return 12 minutes after the first
  Your lag: 4 seconds
  Already enlarged or in titan form, it spends a use for nothing.
--- fade
  It takes: 3 minutes 1 second
  It carries you to your birthplace and marks where you were.
  'return' carries you back to that mark instead.
  Not from no-recall rooms or the ocean, with no rest and no lag.
  Fighting, hiding, falling unconscious or going link-dead breaks it.
--- faerie_fire
  Effect: casts faerie fire at your level
  Page of spell 117
  Your lag: 4 seconds
  It needs no rest between uses.
--- fireshield
  Effect: casts fireshield on you at your level
  Page of spell 108
  Your lag: 4 seconds
  It needs no rest between uses.
--- firestorm
  Effect: casts firestorm at your level
  Page of spell 47
  Your lag: 16 seconds
  It needs no rest between uses.
--- foundry
  Effect: you build a forge in the room
  It is ready after: 8 seconds
  It lasts: 15 minutes
  Uses: 1 before it rests
  Rest: all uses return 2 minutes after the first
  Your lag: 8 seconds
--- gaze
  It falls on a random group member of the target, or the target alone.
  It needs you standing and a target you could bash, not blind or eyeless,
  at most 1 size bigger and 2 smaller than you. A fear save avoids it.
  If a group member takes it, the target attacks that member.
  The target alone stops fighting, and lags: 4 seconds
  Uses: 1 before it rests
  Rest: all uses return 12 minutes after the first
--- globe_of_darkness
  Effect: casts globe of darkness on you at your level
  Page of spell 302
  Uses: 1 before it rests
  Rest: all uses return 12 minutes after the first
  Your lag: 4 seconds
--- god_call
  It answers after: 2 seconds
  Unspecialized, one of the three comes at random:
  Healing blessing on you and your group in the room:
  Heals they cast: 50% stronger
  Duration on you: 3-4 game hours (3.75-5 minutes), by level
  It stops at the first member who already has it.
  Forgiveness: all mobs forget you
  Divine fury on you, unless you already have it:
  Hitroll and damroll: +5
  Duration: 3-4 game hours (3.75-5 minutes)
  Uses: 1 before it rests
  Rest: all uses return 15 minutes after the first
--- hide
  Effect: hides you
  Uses: 1 before it rests
  Rest: all uses return 12 minutes after the first
  Your lag: 4 seconds
  It refuses if you are already hidden.
--- immolate
  Effect: spends your fireshield on an incendiary cloud at your level
  Page of spell 110
  Uses: 1 before it rests
  Rest: all uses return 20 seconds after the first
  Your lag: 16 seconds
  It needs fireshield, and does no damage in a safe room.
  With several players in the room, not all may be hit.
--- lay_hands
  Healing: 501-600 with your level and charisma
  Uses: 1 before it rests
  Rest: all uses return 12 minutes after the first
  Only while you are good. It heals up to the target's full hit points.
  It also cures blindness, poison, disease and carried plague.
  Healing modifiers apply after. It has no lag.
--- levitate
  Effect: casts levitate on you at your level
  Page of spell 83
  Uses: 1 before it rests
  Rest: all uses return 12 minutes after the first
  Your lag: 4 seconds, even if it refuses
  It refuses if you already float, or are too tired.
--- lifedrain
  Drain: 5 hit points every 1 second
  Most it moves: 115 at your level
  Uses: 1 before it rests
  Rest: all uses return 1 minute after the first
  No save or defense applies. It ends if either of you leaves the room,
  once you reach 110% of your hit points, or at 6 hit points on the target.
--- phantasmal_form
  Effect: you turn invisible and pass through doors
  Duration: 4 minutes 5 seconds
  Elemental spell damage to you: 50% more
  Uses: 1 before it rests
  Rest: all uses return 12 minutes after the first
  Your lag: 4 seconds
  Using it again ends the form at no cost. Awe armor cancels the extra damage.
--- plane_shift
  Effect: shifts you to a plane you name
  Page of spell 86
  Uses: 1 before it rests
  Rest: all uses return 1 minute 20 seconds after the first
  Your lag: 4 seconds, also if you try in a fight
  It refuses in a fight, or soon after player combat.
--- project_image
  Effect: makes an image of you here; a direction sends it walking
  Your lag: 4 seconds
  It needs no rest between uses.
--- shade_movement
  Effect: hides you, and you can walk unseen through shadows
  Duration: 6-7 game hours (7.5-8.75 minutes) at your level
  Uses: 1 before it rests
  Rest: all uses return 12 minutes after the first
  It refuses in full sunlight or if already in effect.
  Stepping into light or twilight, or any other command, ends it.
--- shadow_door
  Effect: casts dimension door at your level, to someone you name
  Page of spell 63
  Uses: 1 before it rests
  Rest: all uses return 12 minutes after the first
  It refuses in a fight, or soon after player combat.
--- shapechange
  You learn creatures as level: 51
  Level needed: primates 10, animals 15, reptiles and spiders 20, fish 25
  And: quadrupeds 30, plants and fliers 40, insects, worms and slimes 51
  Learning takes: 12 seconds
  A shape stays known for: 500-501 game hours (625-626.25 minutes)
  A form's hit points: 112, worn down by damage and time
  Your lag to shift: 8 seconds
  Your lag to shift back: 12 seconds
  Shapes must be natural and your size. No rest between uses.
  Not in a fight, with a rider, or in a safe or no-mob room.
--- shift_astral
  Effect: shifts you to the astral plane
  Page of spell 86
  Uses: 1 before it rests
  Rest: all uses return 12 minutes after the first
  Your lag: 4 seconds, also if you try in a fight
  It refuses in a fight, or soon after player combat.
--- shift_prime
  Effect: takes you from the astral plane to a random prime destination
  Uses: 1 before it rests
  Rest: all uses return 12 minutes after the first
  Your lag: 4 seconds, also if you try in a fight
  It refuses in a fight, soon after player combat, or off the astral plane.
  Finding no open destination still spends a use.
--- stone_skin
  Effect: casts stone skin on you at your level
  Page of spell 36
  Uses: 1 before it rests
  Rest: all uses return 5 minutes after the first
  Your lag: 12 seconds
--- strength
  Strength maximum: +7
  Duration: 5-6 game hours (6.25-7.5 minutes)
  Uses: 1 before it rests
  Rest: all uses return 12 minutes after the first
  Your lag: 4 seconds if it works
  Trying with strength already on you still spends a use.
--- summon_imp
  Imp's level: 33, or 50 on Avernus or the fire plane
  Imp's hitroll and damroll: +25
  One imp at a time, with no rest and no lag. It joins your fight.
--- throw_lightning
  Lightning damage: 168-840 at your level, 56
  It strikes after: 8 seconds
  Uses: 1 before it rests
  Rest: all uses return 12 minutes after the first
  Your lag: 4 seconds
  In combat only, and it hits your opponent when it strikes.
  Trying out of combat still spends a use.
  Globes and spirit wards do not stop it.
  Spell damage modifiers and the target's defenses apply after.
--- ud_invisibility
  Effect: makes you invisible
  Duration: 45-46 game hours (56.25-57.5 minutes)
  Uses: 1 before it rests
  Rest: all uses return 12 minutes after the first
  Only in the underdark or underworld; trying elsewhere still spends a use.
  It does nothing if you are already invisible.
--- webwrap
  Paralysis if it works: 20 seconds to 40 seconds
  Your lag: 4 seconds if it works
  Freedom of movement stops it, unless you are a god.
  The target can be at most 1 size bigger than you.
  Level and the target's agility decide if it works.
--- web_spray
  Chance: from 58 in 100 to 90 in 100 by agility
  Target's vitality lost: 7 every 4 seconds
  It lasts: 30 seconds
  Each room the target moves: 10 in 100 to tear free
  Uses: 1 before it rests
  Rest: all uses return 5 minutes after the first
  Your lag: 4 seconds
  Freedom of movement stops it, and the target's evade can dodge it.
--- ally
  Chance from a mob you kill: 1 in 2
  From a player you kill: 1 in 4
  Pet roll: corpse level / 5 + 1-20
  Over 27: a dracolich, if no other pets follow you
  Over 22: a lich, if no other pets follow you
  Over 20: a vampire, with under 6 pet points following
  Over 10: a wraith, with under 6 pet points following
  Over 6: a spectre, with under 7 pet points following
  Otherwise: a lesser pet, with under 8 pet points following
  Pet points: skeleton 2, zombie or spectre 3, wraith or vampire 4
  And: lich 5, dracolich 9
  Using it turns this on or off, with no rest or lag.
--- remort
  Effect: ends your vampire or angelic form
  Your lag: 12 seconds
  It needs that form, and has no rest.
--- spawn
  Chance from a mob you kill: 1 in 2
  From a player you kill: 1 in 4
  Pet roll: corpse level / 5 + 1-20
  Over 27: a dracolich, if no other pets follow you
  Over 22: a lich, if no other pets follow you
  Over 20: a vampire, with under 6 pet points following
  Over 10: a wraith, with under 6 pet points following
  Over 6: a spectre, with under 7 pet points following
  Otherwise: a lesser pet, with under 8 pet points following
  Pet points: skeleton 2, zombie or spectre 3, wraith or vampire 4
  And: lich 5, dracolich 9
  Using it turns this on or off, with no rest or lag.
--- summon_host
  Effect: raises an embalmed, soulless corpse in the room
  Exhume page
--- ogre_roar
  Normal roar, with no modifiers: 66 in 101
  Target's armor class: +56
  Its hitroll loss: its hitroll * 56 / 90
  For: 6-16 game hours (7.5-20 minutes)
  Best roar, 1 in 101: armor class: +66
  Its hitroll loss: its hitroll * 56 / 60
  For: 20-21 game hours (25-26.25 minutes)
  Worst roar, 1 in 101: your hitroll loss: your hitroll * its level / 100
  And the target's armor class: +1 + its level / 2
  For: 24-25 game hours (30-31.25 minutes)
  Uses: 1 before it rests
  Rest: all uses return 12 minutes after the first
  Only a plain ogre may roar. Level, power and wisdom shift the roll,
  and a fearful or meditating target favors you. Not while prone.
  Bigger targets and illithids ignore it, as do those who can't hear,
  are already roared at, or stand in a silent room. It has no lag.
--- summon_book
  Your spellbook arrives after: 4 seconds
  It needs no rest, has no lag, and comes on its own when you enter the game.
--- summon_horde
  Orcs: up to 5 at your level, counting those you have
  Each orc's level: 1
  Each orc's hit points: 1
  They arrive after: 3.5 seconds to 17.5 seconds
  Uses: 1 before it rests
  Rest: all uses return 12 minutes after the first
  Only an orc may call. Off the prime plane or on the ocean none come,
  and the use is still spent; nor do they reach single-file rooms or lockers.
--- summon_mount
  It arrives after: 3.5 seconds to 47 seconds
  Its level: 47-57
  Its hit points: 1850-2350
  Uses: 1 before it rests
  Rest: all uses return 12 minutes after the first
  One mount at a time, and none in dragon form.
  Paladins must be good and antipaladins evil.
  Not in a locker, single-file room or ocean. A dragoon may call from
  anywhere else; others need the outdoors or underworld on the prime plane.
--- summon_totem
  Your totem arrives after: 4 seconds
  It grants farsee.
  It grants sense life.
  It grants soulshield.
  Hit points: +10
  Spell pulse: -1
  It replaces your last totem, with no rest and no lag.
--- summon_warg
  It arrives after: 3.5 seconds to 47 seconds
  Its level: 47-57
  Its hit points: 1850-2350
  Uses: 1 before it rests
  Rest: all uses return 12 minutes after the first
  One at a time. It needs the outdoors or underworld on the prime plane,
  and arrives nowhere that is a locker, single-file room or ocean.
--- stampede
  Foes it can hit: 2-3
  A front-line foe hit for sure: 1 in 10
  Stun and prone on a hit: 2 seconds; fear saves shorten or stop it
  Uses: 1 before it rests
  Rest: all uses return 1 minute after the first
  Your lag: 4 seconds after 2 or more hits, else none
  Players only. You need footing and the front line, not a single-file room.
  Back-rank foes dodge it. Level, agility and awareness decide the rest.
  Ghosts, air elementals, efreet, elites and phantasmal forms are immune.
--- bodyslam
  Base chance: 60 in 100, before level and agility
  Damage: 12 with your strength
  Vitality: needs and spends 30
  Target's lag on a hit: 12 seconds
  Stun on a hit: 1 in 2, 4 seconds to 10 seconds; fear saves apply
  Your lag: 12 seconds
  Your lag on a sleeping target: 4 seconds
  Your lag if it evades: 2 seconds
  Your lag if you slip: 8 seconds
  If you slip, a stun: 1 in 2, 4 seconds
  The target stays aware for: 2-3 game hours (2.5-3.75 minutes)
  Not while riding or in combat. A target must stand on its feet, and be no
  bigger than you or more than 2 sizes smaller, or the slam fails with lag.
  The target's defenses apply to the damage after.
--- call_grave
  Grave page
--- charge
  Charge page
  Base chance: 65 in 100, before level, strength and agility
"""

HARNESS = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "magic/spells.h"
#include "classes/paladins.h"
#include "combat/damage.h"
#include "abilities/abilities.h"
#include <algorithm>
#include <cassert>
#include <climits>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <functional>
#include <map>
#include <string>

void randomize(uint64_t seed);

static std::map<int, int> ratings;
int GET_CHAR_SKILL_P(P_char, int skill) { auto it = ratings.find(skill); return it == ratings.end() ? 0 : it->second; }

static const std::map<std::string, double> properties = {
PROPERTIES
};
// An innate's own timer and uses look their keys up by name, so absent ones fall through;
// any other key not listed is a wrong name.
static double property(const char *key, double fallback) {
    auto it = properties.find(key);
    if (it == properties.end()) {
        if (!std::strncmp(key, "innate.timer.secs.", 18) || !std::strncmp(key, "innate.uses.", 12))
            return fallback;
        std::fprintf(stderr, "unknown property %s\n", key);
        std::abort();
    }
    return it->second == -1 ? fallback : it->second;
}
float get_property(const char *key, double fallback) { return (float)property(key, fallback); }
int get_property(const char *key, int fallback) { return (int)property(key, fallback); }
int STAT_INDEX(int v) { return std::min(51, std::max(0, v / 3)); }

// Which spell page a page asks for.
static int asked_spell;
static std::string spell_page(P_char) { return "  Page of spell " + std::to_string(asked_spell) + "\n"; }
static AbilityFacts harness_ability_facts(int spell) { asked_spell = spell; return spell_page; }
#define ability_facts harness_ability_facts

std::string charge_facts(P_char) { return "  Charge page\n"; }
std::string call_grave_facts(P_char) { return "  Grave page\n"; }
std::string exhume_facts(P_char) { return "  Exhume page\n"; }
float dam_factor[LAST_DF + 1];
struct str_app_type str_app[52];

TABLE

FUNCTIONS

static int fingerprint() { return number(0, INT_MAX); }

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
    { "human warrior", CLASS_WARRIOR, 0, RACE_HUMAN },
    { "paladin", CLASS_PALADIN, 0, RACE_HUMAN },
    { "antipaladin", CLASS_ANTIPALADIN, 0, RACE_ORC },
    { "cleric", CLASS_CLERIC, 0, RACE_HUMAN },
    { "zealot", CLASS_CLERIC, SPEC_ZEALOT, RACE_HUMAN },
    { "healer", CLASS_CLERIC, SPEC_HEALER, RACE_HUMAN },
    { "holyman", CLASS_CLERIC, SPEC_HOLYMAN, RACE_HUMAN },
    { "avenger", CLASS_AVENGER, 0, RACE_HUMAN },
    { "inquisitor", CLASS_AVENGER, SPEC_INQUISITOR, RACE_HUMAN },
    { "lightbringer", CLASS_AVENGER, SPEC_LIGHTBRINGER, RACE_HUMAN },
    { "druid", CLASS_DRUID, 0, RACE_GREY },
    { "woodland druid", CLASS_DRUID, SPEC_WOODLAND, RACE_GREY },
    { "shaman", CLASS_SHAMAN, 0, RACE_GOBLIN },
    { "necromancer", CLASS_NECROMANCER, 0, RACE_HUMAN },
    { "theurgist", CLASS_THEURGIST, 0, RACE_HUMAN },
    { "dragoon", CLASS_DRAGOON, 0, RACE_HUMAN },
    { "conjurer", CLASS_CONJURER, 0, RACE_HUMAN },
    { "air conjurer", CLASS_CONJURER, SPEC_AIR, RACE_HUMAN },
    { "ranger", CLASS_RANGER, 0, RACE_HUMAN },
    { "vampire", CLASS_WARRIOR, 0, RACE_VAMPIRE },
    { "pvampire", CLASS_WARRIOR, 0, RACE_PVAMPIRE },
    { "snake", CLASS_WARRIOR, 0, RACE_SNAKE },
    { "parasite", CLASS_WARRIOR, 0, RACE_PARASITE },
    { "thrikreen", CLASS_WARRIOR, 0, RACE_THRIKREEN },
    { "revenant", CLASS_PALADIN, 0, RACE_REVENANT },
    { "skeleton", CLASS_WARRIOR, 0, RACE_SKELETON },
    { "ogre", CLASS_WARRIOR, 0, RACE_OGRE },
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
    ch.curr_stats.Pow = ch.curr_stats.Luk = ch.curr_stats.Cha = ch.curr_stats.Wis = stat;
    return ch;
}

struct Page { const char *name; AbilityFacts facts; };
static const Page pages[] = {
PAGES
};

static void sweep_pages() {
    bool bad = false;
    for (const Viewer &v : viewers) {
        for (int level = 1; level <= 62; ++level) {
            for (int rating : { 0, 40, 100 }) {
                for (int stat : { 1, 100, 180 }) {
                    char_data ch = viewer(v, level, stat);
                    ratings[SKILL_EXHUME] = rating;
                    for (const Page &page : pages) {
                        randomize(9);
                        const int expected = fingerprint();
                        randomize(9);
                        const std::string text = page.facts(&ch);
                        if (fingerprint() != expected || text.empty() || text.back() != '\n') {
                            std::fprintf(stderr, "%s rolled or is empty for %s\n", page.name, v.name);
                            bad = true;
                        }
                        size_t from = 0, line;
                        while ((line = text.find('\n', from)) != std::string::npos) {
                            const std::string one = text.substr(from, line - from);
                            if (one.size() > 79 || one.compare(0, 2, "  ") != 0 ||
                                one.find("--") != std::string::npos || one.find("-1-") != std::string::npos) {
                                std::fprintf(stderr, "%s, %s %d: bad line (%zu): %s\n", page.name, v.name, level, one.size(), one.c_str());
                                bad = true;
                            }
                            from = line + 1;
                        }
                    }
                }
            }
        }
    }
    ratings.clear();
    if (bad)
        std::abort();
}

static void check_rolls() {
    for (int level : { 1, 5, 6, 7, 8, 10, 12, 25, 26, 30, 50, 56, 60 }) {
        char_data one = viewer(viewers[0], level, 100), *ch = &one;
        SAME(dice(3 * GET_LEVEL(ch), 5), throw_lightning_damage(rolls, ch));
        SAME(dice(2, GET_LEVEL(ch)), vampire_bite_damage(rolls, ch));
        SAME(number(GET_LEVEL(ch), GET_LEVEL(ch) * 3), venom_bite_damage(rolls, ch));
        SAME(40 + dice(4, level), parasite_bite_damage(rolls, level));
        SAME((GET_LEVEL(ch) / 10) * GET_C_CHA(ch) + number(1, 100), lay_hands_amount(rolls, ch));
        SAME(number(70 - GET_LEVEL(ch), 100 + number(1, 200 - 2 * GET_LEVEL(ch))), summon_mount_delay(rolls, ch));
        SAME(number(70 - GET_LEVEL(ch), 70), summon_horde_delay(rolls, ch));
        SAME(std::max(1, level < 6 ? (int)(level * 0.75f + number(1, 5)) : (int)(level * 0.75f + number(-5, 5))), summoned_mount_factor(rolls, ch));
        for (int corpse : { 0, 10, 56 })
            SAME(corpse / 5 + number(1, 20), spawn_tier_roll(rolls, corpse));
    }
    SAME(number(0, 100), vampire_bite_stun_roll(rolls));
    SAME(number(2, 4), vampire_bite_con_duration(rolls));
    SAME(number(0, 7), parasite_bite_disease_roll(rolls, 0));
    SAME(number(0, 1), god_call_peace_roll(rolls));
    SAME(number(1, 100), doorbash_roll(rolls));
    SAME(dice(3, number(2, 10)), doorbash_stuck_damage(rolls));
    SAME(dice(2, number(1, 10)), doorbash_success_damage(rolls));
    SAME(dice(3, number(2, 8)), doorbash_failed_damage(rolls));
    SAME(number(1, 100), doorkick_roll(rolls));
    SAME(dice(2, number(2, 10)), doorkick_stuck_damage(rolls));
    SAME(dice(2, 5), doorkick_success_damage(rolls));
    SAME(dice(2, number(1, 10)), doorkick_failed_damage(rolls));
    SAME(number(5, 10) * PULSE_VIOLENCE, webwrap_duration(rolls));
    SAME(number(1, 100), web_spray_tear_roll(rolls));
    SAME(number(0, 1), innate_blast_appear_roll(rolls));
    SAME(number(0, 2), innate_blast_paralysis_roll(rolls));
    SAME(number(0, 1), innate_blast_major_roll(rolls));
    SAME(100 + number(-25, 25), summoned_mount_skeleton_vitality(rolls));
    SAME(number(1, 101), ogre_roar_roll(rolls));
    SAME(number(1, 100), branch_roll(rolls));
    SAME(number(1, 100), web_spray_roll(rolls));
    SAME(number(1, 100), charge_roll(rolls));
    SAME(number(1, 100), bodyslam_roll(rolls));
    SAME(number(2, 3), stampede_hit_limit(rolls));
    SAME(number(0, 9), stampede_sure_hit_roll(rolls));
    SAME(number(0, 1), bodyslam_stun_roll(rolls));
    SAME(number(PULSE_VIOLENCE, (int)(PULSE_VIOLENCE * 2.5)), bodyslam_stun(rolls));
    SAME(number(0, 1), bodyslam_slip_roll(rolls));
    SAME(number(0, 1), spawn_npc_roll(rolls));
    SAME(number(0, 3), spawn_player_roll(rolls));
    // God call: only an unspecialized caller rolls.
    char_data cleric = viewer(viewers[3], 30), *ch = &cleric;
    SAME(number(1, 3), god_call_choice(rolls, ch));
    char_data zealot = viewer(viewers[4], 30);
    ch = &zealot;
    SAME(SPEC_ZEALOT, god_call_choice(rolls, ch));
    char_data inquisitor = viewer(viewers[8], 30);
    ch = &inquisitor;
    SAME(SPEC_ZEALOT, god_call_choice(rolls, ch));
    char_data lightbringer = viewer(viewers[9], 30);
    ch = &lightbringer;
    SAME(SPEC_HOLYMAN, god_call_choice(rolls, ch));
    // Web spray's chance, keeping its float steps.
    for (int level : { 1, 31, 56 })
        for (int cagi : { 1, 60, 100, 180 })
            for (int vagi : { 1, 60, 100, 180 }) {
                char_data one = viewer(viewers[0], level), *c = &one;
                float chance = GET_LEVEL(c) * 1.5;
                chance = .70 * chance +
                         .30 * BOUNDED(0.0, 100.0 + (cagi - vagi) * ((cagi - vagi <= 0) ? 2.0 : .5), 125.0);
                chance = BOUNDED(5, chance, 90);
                assert(web_spray_chance(c, cagi, vagi) == chance);
                assert(web_spray_chance(c, 1000, 0) >= chance && web_spray_chance(c, 0, 1000) <= chance);
            }
    // Aura and fixed numbers against their pre-conversion expressions.
    for (int level : { 1, 5, 6, 7, 8, 30, 50, 56, 60 }) {
        char_data one = viewer(viewers[1], level), *c = &one;
        assert(aura_protection_ac(c) == (int)(-1 * get_property("innate.paladin_aura.protection_ac_mod", 1.0) * GET_LEVEL(c)));
        assert(aura_precision_hitroll(c) == (int)(get_property("innate.paladin_aura.precision_hitroll_mod", 0.2) * GET_LEVEL(c)));
        assert(aura_endurance_moves(c) == (int)(get_property("innate.paladin_aura.endurance_move_mod", 1.0) * GET_LEVEL(c)));
        assert(aura_vigor_hit_points(c) == (int)(get_property("innate.paladin_aura.vigor_hp_mod", 1.0) * GET_LEVEL(c)));
        assert(aura_spell_protection_percent(c) == (int)(get_property("innate.paladin_aura.protection_spell_mod", 0.5) * GET_LEVEL(c)) - 3);
    }
}

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
#define HAS(page, lines)                                                         \
    do {                                                                         \
        const std::string text = page(&ch);                                      \
        if (!contains(text, lines)) {                                            \
            std::fprintf(stderr, #page " lacks:\n%s\ngot:\n%s", lines, text.c_str()); \
            std::abort();                                                        \
        }                                                                        \
    } while (0)
#define LACKS(page, part) assert(page(&ch).find(part) == std::string::npos)
#define IS(page, lines)                                                          \
    do {                                                                         \
        const std::string text = page(&ch);                                      \
        const std::string want = lines;                                          \
        if (text != want) {                                                     \
            std::fprintf(stderr, #page " wants:\n%s\ngot:\n%s", want.c_str(), text.c_str()); \
            std::abort();                                                        \
        }                                                                        \
    } while (0)

static std::string paladin_page(const char *name) {
    static const std::string all = R"TEXT(EXPECTED)TEXT";
    const std::string head = std::string("--- ") + name + "\n";
    const size_t from = all.find(head);
    assert(from != std::string::npos);
    const size_t start = from + head.size(), end = all.find("--- ", start);
    return all.substr(start, end == std::string::npos ? end : end - start);
}

static void check_text() {
    dam_factor[DF_PHANTFORM] = 1.5;
    str_app[STAT_INDEX(100)].todam = 7;
    const std::string rest_12 = "  Uses: 1 before it rests\n  Rest: all uses return 12 minutes after the first\n";
    char_data ch = viewer(viewers[1], 56);
    (void)rest_12;
    for (const Page &page : pages) {
        const std::string want = paladin_page(page.name), got = page.facts(&ch);
        if (got != want) {
            std::fprintf(stderr, "%s wants:\n%sgot:\n%s", page.name, want.c_str(), got.c_str());
            std::abort();
        }
    }
    CHECKS
}

int main() {
    check_rolls();
    sweep_pages();
    check_text();
    puts("PASS: innates batch 1");
}
'''

CHECKS = r'''
    #define AT(index, level) ch = viewer(viewers[index], level)
    // Low levels and boundaries.
    AT(1, 1);
    IS(aura_protection_innate_facts, "  Armor class: -1 at your level\n" + aura_common_facts());
    IS(aura_precision_innate_facts, "  Hitroll: +0 at your level\n" + aura_common_facts());
    IS(aura_spell_protection_innate_facts, "  Spell damage taken: 3% more at your level\n" + aura_common_facts());
    IS(aura_battlelust_innate_facts, "  Damage dealt: +0.2% at your level\n" + aura_common_facts());
    AT(1, 6);
    IS(aura_spell_protection_innate_facts, "  Spell damage taken: no change at your level\n" + aura_common_facts());
    AT(1, 8);
    IS(aura_spell_protection_innate_facts, "  Spell damage taken: 1% less at your level\n" + aura_common_facts());
    AT(1, 1);
    HAS(shade_movement_innate_facts, "  Duration: 1-2 game hours (1.25-2.5 minutes) at your level\n");
    HAS(blast_innate_facts, "  Duration: 1-2 game hours (1.25-2.5 minutes) at your level\n");
    HAS(lifedrain_innate_facts, "  Most it moves: 5 at your level\n");
    HAS(summon_mount_innate_facts, "  Its level: 11-15\n  Its hit points: 50-250\n");
    AT(1, 6);
    HAS(summon_mount_innate_facts, "  Its level: 11-19\n  Its hit points: 50-450\n");
    AT(1, 25);
    HAS(blast_innate_facts, "  Paralysis is minor at your level.\n");
    LACKS(blast_innate_facts, "Major instead");
    AT(1, 26);
    HAS(blast_innate_facts, "  Major instead of minor: 1 in 2\n");
    LACKS(blast_innate_facts, "Paralysis is minor");
    AT(1, 30);
    IS(summon_totem_innate_facts, "  Your totem arrives after: 4 seconds\n  More powers come with level: 31, 36, 41, 51 and 56.\n  It replaces your last totem, with no rest and no lag.\n");
    AT(1, 31);
    HAS(summon_totem_innate_facts, "  It grants farsee.\n");
    LACKS(summon_totem_innate_facts, "sense life");
    AT(1, 50);
    LACKS(summon_totem_innate_facts, "Hit points");
    AT(1, 51);
    HAS(summon_totem_innate_facts, "  Hit points: +10\n");
    LACKS(summon_totem_innate_facts, "Spell pulse");
    AT(1, 5);
    HAS(summon_horde_innate_facts, "  Orcs: up to 1 at your level, counting those you have\n");
    HAS(summon_horde_innate_facts, "  They arrive after: 16.25 seconds to 17.5 seconds\n");
    AT(1, 60);
    HAS(doorkick_innate_facts, "  Chance: 100 in 100 at your level\n");
    HAS(doorbash_innate_facts, "  Chance: 100 in 100 at your level\n");
    // Rests by path.
    AT(3, 56);
    HAS(god_call_innate_facts, "  Unspecialized, one of the three comes at random:\n");
    HAS(god_call_innate_facts, "  Rest: all uses return 15 minutes after the first\n");
    HAS(god_call_innate_facts, "  Forgiveness: all mobs forget you\n");
    AT(4, 56);
    IS(god_call_innate_facts, "  It answers after: 2 seconds\n  Divine fury on you, unless you already have it:\n  Hitroll and damroll: +11\n  Duration: 5-6 game hours (6.25-7.5 minutes)\n  Uses: 1 before it rests\n  Rest: all uses return 5 minutes after the first\n");
    AT(5, 14);
    HAS(god_call_innate_facts, "  Duration on you: up to 1 game hour (up to 1.25 minutes), by level\n");
    HAS(god_call_innate_facts, "  Heals they cast: 50% stronger\n");
    AT(6, 56);
    IS(god_call_innate_facts, "  It answers after: 2 seconds\n  Naming yourself: all mobs forget you\n  Otherwise fights in the room stop. Each non-elite mob has 1 in 2\n  to forget everyone.\n  Uses: 1 before it rests\n  Rest: all uses return 5 minutes after the first\n");
    AT(8, 56);
    HAS(god_call_innate_facts, "  Strength: +5\n");
    HAS(god_call_innate_facts, "  Duration: 3-4 game hours (3.75-5 minutes)\n");
    HAS(god_call_innate_facts, "  Rest: all uses return 15 minutes after the first\n");
    AT(9, 56);
    IS(god_call_innate_facts, "  It answers after: 2 seconds\n  Soulshield and sanctuary on you:\n  Duration: 3-4 game hours (3.75-5 minutes)\n  Uses: 1 before it rests\n  Rest: all uses return 15 minutes after the first\n");
    // Bite by race.
    AT(19, 56);
    HAS(bite_innate_facts, "  Damage: 2-112 at your level, 56\n  Your lag: 12 seconds\n");
    HAS(bite_innate_facts, "  Stun chance, if not stunned yet: 30 in 101\n  Stun: 4 seconds; fear saves shorten or stop it\n  Target's constitution: -5\n  For: 2-5 game hours (2.5-6.25 minutes)\n");
    AT(19, 9);
    HAS(bite_innate_facts, "  Target's constitution: -1\n");
    AT(21, 56);
    HAS(bite_innate_facts, "  It strikes after: 4 seconds\n  Damage: 56-168 at your level, 56\n  Poison tries: 5, ending when a spell save fails\n");
    AT(22, 56);
    HAS(bite_innate_facts, "  Damage: 44-264 at your level, 56\n  If the target makes an agility save: 22-132\n  With the diseased bite innate: 1 in 8 to cast disease\n  Your lag: 4 seconds if you live\n");
    AT(23, 12);
    HAS(bite_innate_facts, "  Poison tries: 2, ending when a spell save fails\n");
    // Whose numbers.
    AT(24, 56);
    HAS(lay_hands_innate_facts, "  Healing: 1002-1200 with your level and charisma\n");
    AT(14, 56);
    HAS(spawn_innate_facts, "  Over 27: a titan, if no other pets follow you\n");
    HAS(spawn_innate_facts, "  Over 22: a liberator, if no other pets follow you\n");
    HAS(spawn_innate_facts, "  Pet points: hound archon 2, lantern archon or asura 3, bralani 4\n  And: knight errant 4, liberator 5, titan 9\n");
    IS(ally_innate_facts, spawn_innate_facts(&ch));
    AT(25, 56);
    HAS(summon_mount_innate_facts, "  Its hit points: 555-705\n  Its vitality: 75-125\n");
    AT(1, 56);
    LACKS(summon_mount_innate_facts, "vitality");
    AT(17, 56);
    HAS(battle_rage_innate_facts, "  Duration: 30-31 game hours (37.5-38.75 minutes)\n");
    AT(11, 56);
    HAS(shapechange_innate_facts, "  You learn creatures as level: 57\n");
    AT(10, 56);
    HAS(shapechange_innate_facts, "  You learn creatures as level: 56\n");
    // Gods.
    AT(1, MAXLVLMORTAL);
    LACKS(web_spray_innate_facts, "As a god");
    LACKS(shapechange_innate_facts, "As a god");
    AT(1, MAXLVLMORTAL + 1);
    HAS(web_spray_innate_facts, "  As a god, you never miss.\n");
    HAS(shapechange_innate_facts, "  As a god, you need no level to learn.\n");
    LACKS(project_image_innate_facts, "Uses:");
    assert(innate_uses(INNATE_LEVITATE) == 1);
    assert(innate_rest_seconds(INNATE_STONE, stone_skin_innate_rest()) == 300);
    assert(innate_rest_seconds(INNATE_WEB_SPRAY, web_spray_rest()) == 300);
    assert(innate_rest_seconds(INNATE_BITE, bite_innate_rest()) == 12);
    assert(innate_rest_seconds(INNATE_STAMPEDE, stampede_innate_rest()) == 60);
    assert(innate_rest_seconds(INNATE_CONJURE_WATER, 0) == 300);
    assert(innate_rest_seconds(INNATE_IMMOLATE, 0) == 20);
    assert(innate_rest_seconds(INNATE_HIDE, 0) == 720);
'''


def squeeze(text):
    return re.sub(r"\s+", "", text)


def body(file, head):
    bodies = function_bodies(strip_comments(source(file).read_text()), re.escape(head) + r"\s*\(")
    assert bodies, head
    return [squeeze(one) for one in bodies]


def check_properties():
    live = {}
    for line in (ROOT / "lib/duris.properties").read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            live[key.strip()] = float(value)
    for key, value in PROPERTIES.items():
        if value is None:
            assert key not in live, f"{key} is now in the file: {live[key]}"
        else:
            assert live.get(key) == value, f"{key}: file has {live.get(key)}, test has {value}"


def check_sources():
    for (file, head), calls in CALLS.items():
        bodies = body(file, head)
        for call in calls:
            assert any(call in one for one in bodies), f"{head} does not call {call}"
    # A multi-path handler's lags, each tied to its own branch.
    shape = source("actnew.c").read_text()
    assert squeeze('stop_riding(get_linking_char(ch, LNK_RIDING));\n\n\tCharWait(ch, shapechange_shift_lag());') in squeeze(shape)
    assert squeeze('remove_disguise') and squeeze('CharWait(ch, shapechange_return_lag());\n\t\t\tremove_disguise(ch, FALSE);') in squeeze(shape)
    assert "ch->disguise.hit = shapechange_form_hits(ch);" in shape
    fight = squeeze(strip_comments(source("fight.c").read_text()))
    assert "if((IS_NPC(ch)&&!spawn_npc_roll(live_rolls))||(IS_PC(ch)&&!spawn_player_roll(live_rolls)))" in fight
    assert "dam*=divine_force_damage_mod();" in fight
    mods = squeeze(strip_comments(source("dam_mods.c").read_text()))
    assert "(aura_battlelust_mod()*aura_mod(caster,AURA_BATTLELUST))" in mods
    # The reused pages come from the handlers' own spells.
    innates = squeeze(strip_comments(source("innates.c").read_text()))
    for name, spell in (("levitate", "SPELL_LEVITATE"), ("darkness", "SPELL_DARKNESS"), ("shift_astral", "SPELL_PLANE_SHIFT"),
                        ("faerie_fire", "SPELL_FAERIE_FIRE"), ("plane_shift", "SPELL_PLANE_SHIFT"), ("charm_animal", "SPELL_CHARM_ANIMAL"),
                        ("globe_of_darkness", "SPELL_GLOBE_OF_DARKNESS"), ("fireshield", "SPELL_FIRESHIELD"), ("firestorm", "SPELL_FIRESTORM"),
                        ("shadow_door", "SPELL_DIMENSION_DOOR"), ("stone_skin", "SPELL_STONE_SKIN"), ("immolate", "SPELL_INCENDIARY_CLOUD")):
        assert f"std::string{name}_innate_facts(P_charch){{returninnate_spell_facts(ch,{spell}," in innates, name
    table = strip_comments(source("abilities.c").read_text())
    header = source("abilities.h").read_text()
    pending = (ROOT / "tests/fixtures/ability_coverage_pending.txt").read_text().split()
    no_numbers = (ROOT / "tests/fixtures/ability_coverage_no_numbers.txt").read_text().split()
    for constant, name, file in INNATES:
        assert re.search(rf"case {constant}:\s*return {name}_innate_facts;", table), constant
        assert f"std::string {name}_innate_facts(char_data *ch);" in header, name
        assert constant not in pending, constant
        assert function_bodies(strip_comments(source(file).read_text()), rf"std::string\s+{name}_innate_facts\s*\("), name
    grants = strip_comments(source("innates.c").read_text())
    for constant in NO_NUMBERS:
        assert constant in no_numbers and constant not in pending, constant
        assert not re.search(rf"ADD_(RACIAL|CLASS)_INNATE\({constant},", grants), f"{constant} is granted"


def main():
    check_properties()
    check_sources()
    functions = [extract_function("utility.c", "int dice(int num, int size)"),
                 extract_function("utility.c", "int BOUNDED(int a, int b, int c)"),
                 extract_function("utility.c", "int GET_CLASS(P_char ch, uint m_class)")]
    facts = {}
    for constant, name, file in INNATES:
        facts.setdefault(file, []).append(name)
    for file in ["fight.c", "dam_mods.c", "magic/magic.c", "paladins.c", "psionics.c", "new_skills.c", "necromancy.c", "actnew.c", "actoff.c", "innates.c"]:
        text = source(file).read_text()
        for name in SHARED[file].split():
            match = re.search(rf"^(?:static )?[\w:]+(?: \w+)? \*?{name}\([^;\n]*\)$", text, re.M)
            assert match, name
            functions.append(extract_function(file, match.group(0) + "\n{"))
        for name in facts.get(file, []):
            functions.append(extract_function(file, f"std::string {name}_innate_facts(P_char"))
    innates = source("innates.c").read_text()
    table = re.search(r"const struct innate_data innates_data\[LAST_INNATE \+ 1\] = .*?\n};", innates, re.S).group()
    table = re.sub(r'(\{ "[^"]+", )(\w+)( \})', lambda m: m[1] + "NULL" + m[3], table)
    pages = ",\n".join(f'    {{ "{name}", {name}_innate_facts }}' for _, name, _ in INNATES)
    properties = ", ".join(f'{{ "{key}", {-1 if value is None else value} }}' for key, value in PROPERTIES.items())
    build = ROOT / "bin/tests"
    build.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ability-innates-1-", dir=build) as temporary:
        directory = Path(temporary)
        harness = directory / "innates1.cpp"
        harness.write_text(HARNESS.replace("PROPERTIES", properties).replace("PAGES", pages).replace("TABLE", table)
                           .replace("FUNCTIONS", "\n".join(functions)).replace("CHECKS", CHECKS).replace("EXPECTED", PALADIN_PAGES))
        binary = directory / "innates1"
        subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-Wno-unused-function",
                        "-ffunction-sections", "-fdata-sections", "-Wl,--gc-sections",
                        "-fsanitize=address,undefined", "-fno-sanitize-recover=undefined",
                        "-Isrc", "-I/usr/include/mysql", "-I/usr/include/libxml2",
                        str(harness), "src/abilities/abilities.c", "src/core/random.c",
                        "-o", str(binary)], cwd=ROOT, check=True)
        subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    main()
