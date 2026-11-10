#!/usr/bin/env python3
"""Shared ability numbers, skills batch 3: songs, instruments, actnew.c and sparser.c skills.

Builds src/abilities/abilities.c and the real RNG with the shared and facts functions of
this batch, under sanitizers. Each converted roll keeps its pre-conversion expression
below as the oracle: under the same seeds it must give the same value and leave the RNG
at the same draw, and the value must fall inside the range the facts use. Every page is
built for many viewers, levels and ratings: it must never roll and every line must fit
79 columns. Source checks tie every handler to the functions it must call.
"""
import re
import subprocess
import tempfile
from pathlib import Path

from _paths import ROOT, extract_function, source
from _source_contract import function_bodies, strip_comments

SHARED = {
    "bard.c": """player_bard disharmonist_proc_roll disharmonist_song_chance song_chaos_dispel_chance song_dissonance_interrupt_chance song_chaos_dispel_immunity song_dissonance_interrupt_immunity song_storms_extra_roll song_area_roll song_cowardice_flee_roll seconds_range bard_pulse bard_blind_play_rating song_learned_level bard_instrument_fail_weight bard_instrument_chance bard_instrument_factor bard_instrument_mastery bard_save_cap song_level_roll song_verse_failure_rest song_start_failure_rest song_stop_rest song_area_threshold song_common_facts song_save_facts song_area_facts song_everyone_facts song_allies_facts instrument_facts song_healing_amount song_nimbleness_melee_bonus song_nimbleness_spell_threshold song_healing_cap_gap song_healing_duration song_healing_blind_rating song_healing_poison_rating song_healing_disease_rating song_revelation_empower_levels song_revelation_magic_level song_revelation_align_level song_revelation_farsee_level song_revelation_sense_level song_revelation_duration song_revelation_invisible_roll song_revelation_farsee_roll song_harming_damage song_harming_scaled_damage song_harming_blind_level song_harming_poison_level song_harming_blind_duration song_harming_poison_levels song_harming_wither_levels song_harming_wither_rating song_flight_duration song_flight_move_regen bard_protection_ac song_heroism_haste_level song_heroism_pulse song_heroism_singer_pulse song_heroism_hit_dam song_cowardice_flee_threshold song_cowardice_flee_levels song_cowardice_penalty song_peace_duration song_storms_most_strikes song_storms_strike_roll song_storms_bolt_level song_storms_cyclone_rating song_storms_cyclone_roll song_storms_call_lightning_rating song_storms_call_lightning_roll song_storms_call_lightning_level song_chaos_spell_rating song_chaos_spell_roll song_chaos_spell_pick song_chaos_damage song_chaos_teleport_roll song_chaos_teleport_level song_dragons_duration song_dragons_cold_level song_dragons_gas_level song_dragons_acid_level song_dragons_lightning_level song_dragons_ward_roll song_dissonance_power song_dissonance_disharmonist_bonus song_dissonance_target_lag song_dissonance_pet_death_delay riff_failed_rest riff_rest riff_lag""".split(),
    "actnew.c": """war_cry_hit_points war_cry_bonus war_cry_group_duration war_cry_solo_duration war_cry_lag roar_of_heroes_level roar_of_heroes_duration roar_of_heroes_con_max flurry_total_attacks flurry_hits_per_target flurry_lag flurry_rest hitall_lag hitall_berserk_lag subterfuge_roll subterfuge_resist_score disarm_opening_penalty disarm_other_target_penalty disarm_score disarm_fumble_roll disarm_rest disarm_lag advanced_meditation_cure_threshold advanced_meditation_poison_rating advanced_meditation_poison_roll advanced_meditation_disease_rating advanced_meditation_cure_level advanced_meditation_interval advanced_meditation_hit_regen advanced_meditation_move_regen advanced_meditation_vitality_lag advanced_meditation_lag dirt_toss_blindness dirt_toss_lag lore_failed_lag lore_lag lore_famous_level lore_master_level lore_unidentified_level throat_crush_lag throat_crush_miss_lag throat_crush_size_reach throat_crush_damage throat_crush_silence throat_crush_cooldown throat_crush_cooldown_text hamstring_aware_penalty hamstring_threshold hamstring_vitality_drain hamstring_vitality_floor hamstring_aware_duration hamstring_lag throw_potion_lag throw_potion_rest""".split(),
    "actoff.c": """advanced_meditation_stun_flee_bonus sneaky_strike_bleed_damage""".split(),
    "actmove.c": """crippled_move_cost""".split(),
    "actinf.c": """spell_book_recognizes""".split(),
    "memorize.c": """natures_sanctity_recovery_factor natures_ruin_recovery_factor spatial_focus_mana_threshold spatial_focus_mana_cost""".split(),
    "specs.object.c": """trap_arm_lag trap_arm_lifetime trap_spring_roll trap_dart_damage trap_poison_level trap_cripple_duration trap_bleed_count""".split(),
    "epic_skills.c": """chant_mastery_threshold chant_mastery_result chant_mastery_top_lag chant_mastery_top_time chant_mastery_good_lag chant_mastery_good_time chant_mastery_fair_lag chant_mastery_fair_time chant_mastery_low_time silent_spell_threshold""".split(),
    "sparser.c": """spell_knowledge_hears_name spell_knowledge_name_threshold spell_knowledge_name_roll casting_progress_skill spell_knowledge_facts concentration_threshold spatial_focus_threshold spatial_focus_result spatial_focus_lag disruptive_blow_damage disruptive_blow_hit_margin disruptive_blow_stop_margin silent_spell_failed_lag spellweave_duration totemic_mastery_cast_time natures_sanctity_cast_time natures_ruin_cast_time percent_text nature_epic_facts quick_chant_tank_roll quick_chant_cast_time""".split(),
}

CONVERTED = """
INSTRUMENT_DRUMS instrument_drums bard.c
INSTRUMENT_FLUTE instrument_flute bard.c
INSTRUMENT_HARP instrument_harp bard.c
INSTRUMENT_HORN instrument_horn bard.c
INSTRUMENT_LYRE instrument_lyre bard.c
INSTRUMENT_MANDOLIN instrument_mandolin bard.c
SKILL_EMPOWER_SONG empower_song bard.c
SKILL_RIFF riff bard.c
SONG_CALMING song_calming bard.c
SONG_CHAOS song_chaos bard.c
SONG_COWARDICE song_cowardice bard.c
SONG_DISCORD song_discord bard.c
SONG_DISSONANCE song_dissonance bard.c
SONG_DRAGONS song_dragons bard.c
SONG_DRIFTING song_drifting bard.c
SONG_FLIGHT song_flight bard.c
SONG_FORGETFULNESS song_forgetfulness bard.c
SONG_HARMING song_harming bard.c
SONG_HARMONY song_harmony bard.c
SONG_HEALING song_healing bard.c
SONG_HEROISM song_heroism bard.c
SONG_SHADOW_PIPER song_shadow_piper bard.c
SONG_NIMBLENESS song_nimbleness bard.c
SONG_PEACE song_peace bard.c
SONG_REVELATION song_revelation bard.c
SONG_STORMS song_storms bard.c
SKILL_ADVANCED_MEDITATION advanced_meditation actnew.c
SKILL_DIRTTOSS dirt_toss actnew.c
SKILL_DISARM disarm actnew.c
SKILL_FLURRY_OF_BLOWS flurry_of_blows actnew.c
SKILL_HAMSTRING hamstring actnew.c
SKILL_HITALL hitall actnew.c
SKILL_LORE lore actnew.c
SKILL_REMIX remix actnew.c
SKILL_ROAR_OF_HEROES roar_of_heroes actnew.c
SKILL_SUBTERFUGE subterfuge actnew.c
SKILL_THROAT_CRUSH throat_crush actnew.c
SKILL_THROAT_CRUSHER throat_crusher actnew.c
SKILL_THROW_POTIONS throwpotion actnew.c
SKILL_TRAP trap specs.object.c
SKILL_WAR_CRY war_cry actnew.c
SKILL_CHANT_MASTERY chant_mastery epic_skills.c
SKILL_CONCENTRATION concentration sparser.c
SKILL_DISRUPTIVE_BLOW disruptive_blow sparser.c
SKILL_NATURES_RUIN natures_ruin sparser.c
SKILL_NATURES_SANCTITY natures_sanctity sparser.c
SKILL_QUICK_CHANT quick_chant sparser.c
SKILL_SILENT_SPELL silent_spell epic_skills.c
SKILL_SPATIAL_FOCUS spatial_focus sparser.c
SKILL_SPELLWEAVE spellweave sparser.c
SKILL_SPELL_KNOWLEDGE_CLERICAL spell_knowledge_clerical sparser.c
SKILL_SPELL_KNOWLEDGE_MAGICAL spell_knowledge_magical sparser.c
SKILL_SPELL_KNOWLEDGE_SHAMAN spell_knowledge_shaman sparser.c
SKILL_TOTEMIC_MASTERY totemic_mastery sparser.c
"""
SKILLS = [line.split() for line in CONVERTED.split("\n") if line.strip()]

# (file, handler): calls the handler's body must make, whitespace removed before matching.
CALLS = {
    ("bard.c", "int get_bard_pulse"): ["bard_pulse(IS_AFFECTED(ch,AFF_HASTE))"],
    ("bard.c", "P_obj has_instrument"): [">=bard_blind_play_rating()"],
    ("bard.c", "int bard_calc_chance"): ["song_level=song_learned_level(ch,song)", "weight=bard_instrument_fail_weight()",
                                         "chance=bard_instrument_chance(chance,weight,instrument_skill)"],
    ("bard.c", "int bard_song_level"): ["i_factor=bard_instrument_factor()", "bard_instrument_mastery(GET_CHAR_SKILL("],
    ("bard.c", "bool bard_saves"): ["(int)MIN((bard_song_level(ch,song)-GET_LEVEL(victim))/2,bard_save_cap())"],
    ("bard.c", "void bard_drifting"): ["(skill>number(1,300))", "spell_group_teleport(level,ch,0,0,victim,0)"],
    ("bard.c", "void bard_healing"): ["healed=song_healing_amount(ch,level,ch!=victim)", "heal(victim,ch,healed,GET_MAX_HIT(victim)-song_healing_cap_gap(live_rolls))",
                                      "IS_AFFECTED(victim,AFF_BLIND)&&GET_CHAR_SKILL(ch,SONG_HEALING)>=song_healing_blind_rating()",
                                      "IS_AFFECTED2(victim,AFF2_POISONED)&&GET_CHAR_SKILL(ch,SONG_HEALING)>=song_healing_poison_rating()",
                                      "GET_CHAR_SKILL(ch,SONG_HEALING)>=song_healing_disease_rating()", "af.duration=song_healing_duration()"],
    ("bard.c", "void bard_revelation"): ["level+=song_revelation_empower_levels(empower)", "af.duration=song_revelation_duration(x)",
                                         "(level>song_revelation_magic_level())&&!IS_AFFECTED2(victim,AFF2_DETECT_MAGIC)", "level>song_revelation_align_level()",
                                         "(level>song_revelation_sense_level())&&!IS_AFFECTED(victim,AFF_DETECT_INVISIBLE)&&!song_revelation_invisible_roll(live_rolls)",
                                         "(level>song_revelation_sense_level())&&!IS_AFFECTED(victim,AFF_SENSE_LIFE)",
                                         "(level>song_revelation_farsee_level())&&!IS_AFFECTED(victim,AFF_FARSEE)&&!song_revelation_farsee_roll(live_rolls)"],
    ("bard.c", "void bard_harming"): ["dam=song_harming_damage(live_rolls,lvl,empower)", "dam=song_harming_scaled_damage(dam)",
                                      "spell_damage(ch,victim,dam,SPLDAM_SOUND,SPLDAM_NOSHRUG|SPLDAM_NODEFLECT,&messages)",
                                      "resists_spell(ch,victim)", "GET_LEVEL(ch)>song_harming_blind_level()&&!bard_saves(ch,victim,song)",
                                      "blind(ch,victim,song_harming_blind_duration(live_rolls,lvl))",
                                      "(GET_LEVEL(ch)>song_harming_poison_level())", "spell_poison(lvl-song_harming_poison_levels(),ch,0,0,victim,0)",
                                      "(GET_CHAR_SKILL(ch,SONG_HARMING)>=song_harming_wither_rating())",
                                      "spell_wither(lvl-song_harming_wither_levels(live_rolls),ch,0,0,victim,0)"],
    ("bard.c", "void bard_flight"): ["af.duration=song_flight_duration(l)", "af.modifier=song_flight_move_regen(l,empower)"],
    ("bard.c", "void bard_heroism"): ["GET_LEVEL(ch)>=song_heroism_haste_level()", "af.modifier=recipient==ch?song_heroism_singer_pulse(l):song_heroism_pulse(ch)", "af.modifier=song_heroism_hit_dam(l,empower)", "spell_haste(l,ch,0,0,victim,NULL)"],
    ("bard.c", "void bard_cowardice"): ["(song_cowardice_flee_roll(live_rolls)<song_cowardice_flee_threshold())", "(number(0,100)<GET_CHAR_SKILL(ch,SONG_COWARDICE))",
                                        "((GET_LEVEL(ch)+song_cowardice_flee_levels(empower))>=GET_LEVEL(victim))", "af.modifier=song_cowardice_penalty(l,empower)",
                                        "!bard_saves(ch,victim,song)&&!IS_TRUSTED(victim)&&!fear_check(victim)"],
    ("bard.c", "void bard_peace"): ["af.duration=song_peace_duration()"],
    ("bard.c", "void bard_harmony"): ["spell_dispel_evil((int)l,ch,0,SPELL_TYPE_SPELL,victim,0)"],
    ("bard.c", "void bard_discord"): ["spell_dispel_good((int)l,ch,0,SPELL_TYPE_SPELL,victim,0)"],
    ("bard.c", "void bard_storms"): ["i<song_storms_most_strikes(songLevel)", "if(song_storms_strike_roll(live_rolls))break;",
                                     "spell_lightning_bolt(song_storms_bolt_level(songLevel),ch,0,SPELL_TYPE_SPELL,victim,0)",
                                     "GET_CHAR_SKILL(ch,SONG_STORMS)>=song_storms_cyclone_rating()&&!song_storms_cyclone_roll(live_rolls)",
                                     "spell_cyclone(songLevel,ch,0,SPELL_TYPE_SPELL,victim,0)",
                                     "(empower==song_storms_call_lightning_rating())&&(!song_storms_call_lightning_roll(live_rolls))",
                                     "spell_call_lightning(song_storms_call_lightning_level(songLevel),ch,victim,0)"],
    ("bard.c", "void bard_chaos"): ["GET_CHAR_SKILL(ch,SONG_CHAOS)>=song_chaos_spell_rating()", "if(!song_chaos_spell_roll(live_rolls))", "random=song_chaos_spell_pick(live_rolls)",
                                    "spell_damage(ch,victim,song_chaos_damage(live_rolls),SPLDAM_SOUND,SPLDAM_NODEFLECT,0)",
                                    "!bard_saves(ch,victim,song)&&song_chaos_teleport_roll(live_rolls)==3", "spell_teleport(song_chaos_teleport_level(),ch,0,0,victim,0)"],
    ("bard.c", "void bard_dragons"): ["af.duration=song_dragons_duration(x)", "(l>song_dragons_cold_level())&&(song_dragons_ward_roll(live_rolls))",
                                      "(l>song_dragons_gas_level())&&(song_dragons_ward_roll(live_rolls))",
                                      "(l>song_dragons_acid_level())&&(song_dragons_ward_roll(live_rolls))",
                                      "(l>song_dragons_lightning_level())&&(song_dragons_ward_roll(live_rolls))"],
    ("bard.c", "void bard_dissonance"): ["c_roll=song_dissonance_power(ch,GET_CHAR_SKILL(ch,SKILL_EMPOWER_SONG))", "c_roll+=song_dissonance_disharmonist_bonus(c_roll)",
                                         "c_roll+number(0,50)>t_roll+number(0,50)", "CharWait(t,song_dissonance_target_lag())", "c_roll>number(1,2000)",
                                         "add_event(event_pet_death,song_dissonance_pet_death_delay(),t,NULL,NULL,0,NULL,0)"],
    ("bard.c", "void event_bardsong"): ["intsong_level=song_learned_level(ch,song)", "set_short_affected_by(ch,TAG_BARDSONG_FAILURE,song_verse_failure_rest(song_level))",
                                        "l=bard_song_level(ch,song)+song_level_roll(live_rolls)", "aggr_chance=song_area_threshold()", "song_area_roll(live_rolls)>aggr_chance"],
    ("bard.c", "void do_play"): ["set_short_affected_by(ch,TAG_BARDSONG_FAILURE,song_stop_rest())", "intsong_level=song_learned_level(ch,s)",
                                 "set_short_affected_by(ch,TAG_BARDSONG_FAILURE,song_start_failure_rest(song_level))", "verses=NUM_VERSES(ch,s)"],
    ("bard.c", "void do_riff"): ["number(1,90)>GET_CHAR_SKILL(ch,SKILL_RIFF)", "set_short_affected_by(ch,SKILL_RIFF,riff_failed_rest())",
                                 "l=bard_song_level(ch,s)+song_level_roll(live_rolls)", "set_short_affected_by(ch,SKILL_RIFF,riff_rest())", "CharWait(ch,riff_lag())"],
    ("actnew.c", "void do_war_cry"): ["inthpoints=war_cry_hit_points(ch)", "intdampoints=war_cry_bonus(ch)", "af.duration=war_cry_group_duration(dampoints)",
                                      "af.duration=war_cry_solo_duration(dampoints)", "CharWait(ch,war_cry_lag())"],
    ("actnew.c", "int do_roar_of_heroes"): ["GET_LEVEL(ch)<roar_of_heroes_level()", "af.duration=roar_of_heroes_duration();af.modifier=roar_of_heroes_con_max(live_rolls)", "af.location=APPLY_CON_MAX"],
    ("actnew.c", "void do_flurry_of_blows"): ["max_num_attacks=flurry_total_attacks(num_attacks)", "num_hits_per_target=flurry_hits_per_target(max_num_attacks,num_targets,num_attacks)",
                                              "number(1,101)>(IS_PC(ch)?(1+GET_CHAR_SKILL(ch,SKILL_FLURRY_OF_BLOWS))", "CharWait(ch,flurry_lag())", "set_short_affected_by(ch,SKILL_FLURRY_OF_BLOWS,flurry_rest())"],
    ("actnew.c", "void do_hitall"): ["percent=number(1,101)", "GET_CHAR_SKILL(ch,SKILL_HITALL)>=percent", "CharWait(ch,hitall_berserk_lag())", "CharWait(ch,hitall_lag(count))"],
    ("actnew.c", "void do_subterfuge"): ["percent=subterfuge_roll(live_rolls)", "subterfuge_resist_score(GET_LEVEL(npc),GET_LEVEL(ch))>number(1,101)"],
    ("actnew.c", "void do_disarm"): ["GET_CHAR_SKILL(ch,SKILL_DISARM)>number(1,91)", "percent=disarm_opening_penalty()", "percent=disarm_other_target_penalty()",
                                     "percent+=disarm_score(ch,STAT_INDEX(GET_C_DEX(victim)),GET_LEVEL(victim))", "percent>rnd_num", "set_short_affected_by(victim,SKILL_DISARM,disarm_rest())",
                                     "rnd_num>=disarm_fumble_roll()", "set_short_affected_by(ch,SKILL_DISARM,disarm_rest())", "CharWait(ch,disarm_lag())"],
    ("actnew.c", "void event_meditation"): ["advanced_meditation_cure_threshold(ch)>number(0,100)", "spell_cure_blind(advanced_meditation_cure_level(),ch,0,0,ch,0)",
                                            ">advanced_meditation_poison_rating()&&!advanced_meditation_poison_roll(live_rolls)", ">advanced_meditation_disease_rating()",
                                            "add_event(event_meditation,advanced_meditation_interval(),ch,0,0,0,0,0)"],
    ("actnew.c", "void do_meditate"): ["af.modifier=advanced_meditation_hit_regen(ch)", "af.modifier=advanced_meditation_move_regen(ch)", "CharWait(ch,advanced_meditation_vitality_lag())",
                                       "CharWait(ch,advanced_meditation_lag())", "add_event(event_meditation,advanced_meditation_interval(),ch,0,0,0,0,0)"],
    ("actnew.c", "void do_dirttoss"): ["intduration=dirt_toss_blindness(skl_lvl,GET_C_DEX(ch),GET_C_AGI(vict))", "CharWait(ch,dirt_toss_lag())"],
    ("actnew.c", "static void lore_character"): ["number(1,101)>skl_lvl", "CharWait(ch,lore_failed_lag())", "GET_LEVEL(target)>=lore_famous_level()&&lore_power>1",
                                                 "GET_LEVEL(target)>=lore_master_level()&&lore_power>2", "CharWait(ch,lore_lag())"],
    ("actnew.c", "void do_lore"): ["percent=number(1,101)", "percent>skl_lvl", "CharWait(ch,lore_failed_lag())", "CharWait(ch,lore_lag())"],
    ("actnew.c", "static void render_item_lore"): ["GET_LEVEL(ch)<lore_unidentified_level()"],
    ("actnew.c", "void do_throat_crush"): ["CharWait(ch,throat_crush_lag())", "GET_ALT_SIZE(vict)>GET_ALT_SIZE(ch)+throat_crush_size_reach()", "GET_ALT_SIZE(vict)<GET_ALT_SIZE(ch)-throat_crush_size_reach()",
                                           "CharWait(ch,throat_crush_miss_lag())", "melee_damage(ch,vict,throat_crush_damage(),PHSDAM_TOUCH,&messages)",
                                           "af.duration=throat_crush_silence(live_rolls)", "af.duration=throat_crush_cooldown(live_rolls)"],
    ("actnew.c", "void do_hamstring"): ["skl_lvl-=hamstring_aware_penalty()", "i=hamstring_threshold(skl_lvl,GET_C_AGI(vict))", "number(1,100)<i", "i=hamstring_vitality_drain(live_rolls)",
                                        "(GET_VITALITY(vict)-i)<hamstring_vitality_floor()", "i=MAX(0,GET_VITALITY(vict)-hamstring_vitality_floor())", "afs.duration=hamstring_aware_duration()", "CharWait(ch,hamstring_lag())"],
    ("actnew.c", "bool throw_potion"): ["CharWait(ch,throw_potion_lag())", "throw_potion_rest(IS_AFFECTED2(ch,AFF2_FLURRY),IS_AFFECTED(ch,AFF_HASTE))", "number(0,chance)",
                                        "number(1,120)<GET_CHAR_SKILL(ch,SKILL_REMIX)", "victim&&!obj&&IS_NPC(victim)"],
    ("actnew.c", "int chance_throw_potion"): ["number(1,140)>GET_C_AGI(ch)"],
    ("actoff.c", "void do_flee"): ["stun_chance_flee+=advanced_meditation_stun_flee_bonus(ch)"],
    ("actmove.c", "int do_simple_move_skipping_procs"): ["need_movement+=crippled_move_cost()"],
    ("actinf.c", "void ShowCharSpellBookSpells"): ["spell_book_recognizes(GET_CHAR_SKILL(ch,k),number(1,100))&&(GET_CHAR_SKILL(ch,k)&&number(1,70)<=GET_LEVEL(ch))"],
    ("memorize.c", "int get_circle_memtime"): ["time=time*natures_sanctity_recovery_factor()", "time=time*natures_ruin_recovery_factor()"],
    ("memorize.c", "void use_spell"): ["spatial_focus_mana_threshold(spatial)>number(1,100)", "GET_MANA(ch)-=spatial_focus_mana_cost(get_spell_circle(ch,spell))"],
    ("specs.object.c", "int huntsman_ward"): ["set_obj_affected(obj,trap_arm_lifetime(),TAG_OBJ_DECAY,0)", "CharWait(ch,trap_arm_lag())", "if(trap_spring_roll(live_rolls)&&",
                                              "dam=trap_dart_damage(live_rolls)", "af.duration=trap_cripple_duration()", "intnumb=trap_bleed_count(live_rolls)",
                                              "spell_poison(trap_poison_level(),ch,0,0,ch,NULL)", "number(0,120)<GET_C_INT(ch)"],
    ("epic_skills.c", "int chant_mastery_bonus"): ["chant_mastery_threshold(ch)>number(0,100)", "chant_bonus=chant_mastery_result(live_rolls,ch)"],
    ("epic_skills.c", "bool silent_spell_check"): ["skill=silent_spell_threshold(skill)", "number(0,100)<skill"],
    ("sparser.c", "void say_spell"): ["spell_knowledge_hears_name(rand,GET_CHAR_SKILL(tch,SKILL_SPELL_KNOWLEDGE_MAGICAL))", "spell_knowledge_hears_name(rand,GET_CHAR_SKILL(tch,SKILL_SPELL_KNOWLEDGE_CLERICAL))",
                                      "spell_knowledge_hears_name(rand,GET_CHAR_SKILL(tch,SKILL_SPELL_KNOWLEDGE_SHAMAN))", "intrand=number(1,101)"],
    ("sparser.c", "void SpellCastShow"): ["rand<=GET_CHAR_SKILL(tch,SKILL_SPELL_KNOWLEDGE_MAGICAL)", "spell_knowledge_name_roll(live_rolls)>spell_knowledge_name_threshold()"],
    ("sparser.c", "bool ground_casting_check"): ["number(0,120)<concentration_threshold(ch)"],
    ("sparser.c", "bool cast_common_generic"): ["ground_casting_check(ch,spl)"],
    ("sparser.c", "void do_will"): ["spatial_focus_threshold(ch)>number(0,100)", "intchant_bonus=spatial_focus_result(live_rolls,ch)", "CharWait(ch,spatial_focus_lag())"],
    ("sparser.c", "bool check_disruptive_blow"): ["success=skl-number(0,130)", "melee_damage(tch,ch,disruptive_blow_damage(live_rolls),0,&messages)", "melee_damage(tch,ch,disruptive_blow_damage(live_rolls),0,&messages2)"],
    ("sparser.c", "void do_cast"): ["GET_CHAR_SKILL(ch,SKILL_SPELLWEAVE)>number(0,100)", "GET_CHAR_SKILL(ch,SKILL_TOTEMIC_MASTERY)>number(50,200)", "(!is_tank||quick_chant_tank_roll(live_rolls))", "GET_CHAR_SKILL(ch,SKILL_QUICK_CHANT)>number(1,100)",
                                    "dura=quick_chant_cast_time(dura)", "CharWait(ch,silent_spell_failed_lag())"],
    ("sparser.c", "void event_spellcast"): ["skl=casting_progress_skill(ch)", "number(1,100)<=GET_CHAR_SKILL(ch,skl)", "weave_effect.duration=spellweave_duration(GET_LEVEL(ch))"],
}

# (file, handler): after an anchor the next statement of the same kind must be this one.
BRANCHES = {
    ("sparser.c", "void do_cast"): [("SKILL_TOTEMIC_MASTERY)>number(50,200)", "dura=", "dura=totemic_mastery_cast_time(dura)"),
                                    ("SKILL_NATURES_SANCTITY)>number(1,100)", "dura=", "dura=natures_sanctity_cast_time(dura)"),
                                    ("SKILL_NATURES_RUIN)>number(1,100)", "dura=", "dura=natures_ruin_cast_time(dura)"),
                                    ("silent_spell_check(ch)", "CharWait(", "CharWait(ch,silent_spell_failed_lag())")],
    ("sparser.c", "bool check_disruptive_blow"): [("success>disruptive_blow_stop_margin()", "melee_damage(", "melee_damage(tch,ch,disruptive_blow_damage(live_rolls),0,&messages)"),
                                                  ("success>disruptive_blow_hit_margin()", "melee_damage(", "melee_damage(tch,ch,disruptive_blow_damage(live_rolls),0,&messages2)")],
    ("epic_skills.c", "int chant_mastery_bonus"): [("if(chant_bonus==3)", "CharWait(", "CharWait(ch,chant_mastery_top_lag())"), ("chant_mastery_top_lag());", "return", "returnchant_mastery_top_time()"),
                                                   ("if(chant_bonus==2)", "CharWait(", "CharWait(ch,chant_mastery_good_lag(dura))"), ("chant_mastery_good_lag(dura));", "return", "returnchant_mastery_good_time()"),
                                                   ("if(chant_bonus==1)", "CharWait(", "CharWait(ch,chant_mastery_fair_lag(dura))"), ("chant_mastery_fair_lag(dura));", "return", "returnchant_mastery_fair_time(dura)"),
                                                   ("chant_mastery_fair_time(dura);}else{", "return", "returnchant_mastery_low_time(dura)")],
    ("bard.c", "void do_riff"): [("number(1,90)>GET_CHAR_SKILL(ch,SKILL_RIFF)", "set_short_affected_by(", "set_short_affected_by(ch,SKILL_RIFF,riff_failed_rest())"),
                                 ("for(tch=world[room].people", "set_short_affected_by(", "set_short_affected_by(ch,SKILL_RIFF,riff_rest())")],
    ("actnew.c", "void do_war_cry"): [("if(ch->group)", "af.duration=", "af.duration=war_cry_group_duration(dampoints)"), ("else{if(!affected_by_spell(ch,SKILL_WAR_CRY))", "af.duration=", "af.duration=war_cry_solo_duration(dampoints)")],
    ("actnew.c", "void do_hitall"): [("affected_by_spell(ch,SKILL_BERSERK)){CharWait(", "CharWait(", "CharWait(ch,hitall_berserk_lag())")],
    ("actnew.c", "void do_meditate"): [(">advanced_meditation_poison_rating())", "CharWait(", "CharWait(ch,advanced_meditation_vitality_lag())"),
                                       ("Yousinkinmeditation", "CharWait(", "CharWait(ch,advanced_meditation_lag())")],
    ("actnew.c", "void do_throat_crush"): [("Youmisstheirthroat", "CharWait(", "CharWait(ch,throat_crush_miss_lag())"), ("alreadysore", "CharWait(", "CharWait(ch,throat_crush_lag())"),
                                           ("af.type=SKILL_THROAT_CRUSH;", "af.duration=", "af.duration=throat_crush_silence(live_rolls)"),
                                           ("af.type=SKILL_THROAT_CRUSHER;", "af.duration=", "af.duration=throat_crush_cooldown(live_rolls)")],
    ("actnew.c", "void do_hamstring"): [("Suchamaneuverappears", "CharWait(", "CharWait(ch,hamstring_lag())")],
    ("specs.object.c", "int huntsman_ward"): [("if(item==77)", "dam=", "dam=trap_dart_damage(live_rolls)"), ("if(item==400229)", "af.duration=", "af.duration=trap_cripple_duration()"),
                                              ("if(item==73)", "spell_poison(", "spell_poison(trap_poison_level(),ch,0,0,ch,NULL)")],
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
#include <cstdlib>
#include <cstring>
#include <functional>
#include <map>
#include <string>

#define INSTRUMENT_OFFSET (FIRST_INSTRUMENT - 184)
#define NUM_VERSES(ch, song) (GET_LEVEL(ch))
#define SONG_AGGRESSIVE BIT_1
#define SONG_ALLIES BIT_2
#define SONG_SELF_ONLY BIT_3

void randomize(uint64_t seed);

static std::map<int, int> ratings;
int GET_CHAR_SKILL_P(P_char, int skill) { auto it = ratings.find(skill); return it == ratings.end() ? 0 : it->second; }
static bool blind_singer;
bool has_innate(P_char, int innate) { assert(innate == INNATE_BLINDSINGING); return blind_singer; }
// The live values in lib/duris.properties. A key not listed here is a wrong name, and -1
// marks one the file leaves to the code's fallback.
static const std::map<std::string, double> properties = {
    { "bard.instrumentFailWeight", 25 }, { "bard.instrumentFactor", 0.25 }, { "song.bard.harming.mod", 1.2 },
    { "song.bard.cowardice.flee.chance", 10 }, { "spell.area.minChance.aggroBardSong", 75 },
    { "alchemist.throwp.lag.rounds", 0.75 }, { "alchemist.throwp.reorient.rounds", 1.75 },
    { "timer.sec.advancedMeditation", -1 },
};
static double property(const char *key, double fallback) {
    auto it = properties.find(key);
    if (it == properties.end()) { std::fprintf(stderr, "unknown property %s\n", key); std::abort(); }
    return it->second == -1 ? fallback : it->second;
}
float get_property(const char *key, double fallback) { return (float)property(key, fallback); }
int get_property(const char *key, int fallback) { return (int)property(key, fallback); }
int STAT_INDEX(int v) { return std::min(51, std::max(0, v / 3)); }
static std::map<int, int> learned_levels;
static int learned_spec_level;
int flag2idx(int) { return 1; }
int get_song_level(int, int spec, int song) { return spec ? learned_spec_level : learned_levels[song]; }

SONG_TABLE

FUNCTIONS

static int fingerprint() { return number(0, INT_MAX); }

// Single-draw clamps keep every result within the displayed bounds.

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

struct Viewer { const char *name; uint m_class; int spec; };
static const Viewer viewers[] = {
    { "bard", CLASS_BARD, 0 },
    { "minstrel", CLASS_BARD, SPEC_MINSTREL },
    { "disharmonist", CLASS_BARD, SPEC_DISHARMONIST },
    { "scoundrel", CLASS_BARD, SPEC_SCOUNDREL },
    { "warrior", CLASS_WARRIOR, 0 },
    { "swashbuckler", CLASS_WARRIOR, SPEC_SWASHBUCKLER },
    { "berserker", CLASS_BERSERKER, 0 },
    { "thief", CLASS_THIEF, 0 },
    { "rogue thief", CLASS_ROGUE, SPEC_THIEF },
    { "snake monk", CLASS_MONK, SPEC_WAYOFSNAKE },
    { "mercenary", CLASS_MERCENARY, 0 },
    { "alchemist", CLASS_ALCHEMIST, 0 },
    { "sorcerer", CLASS_SORCERER, 0 },
    { "wizard", CLASS_SORCERER, SPEC_WIZARD },
    { "shaman", CLASS_SHAMAN, 0 },
    { "druid", CLASS_DRUID, 0 },
    { "blighter", CLASS_BLIGHTER, 0 },
    { "cleric", CLASS_CLERIC, 0 },
    { "psionicist", CLASS_PSIONICIST, 0 },
    { "ranger", CLASS_RANGER, 0 },
};

static pc_only_data pc_data;
static char_data viewer(const Viewer &v, int level, int stat = 100) {
    char_data ch{};
    ch.player.m_class = v.m_class;
    ch.player.spec = v.spec;
    ch.player.level = level;
    ch.only.pc = &pc_data;
    ch.curr_stats.Str = ch.curr_stats.Dex = ch.curr_stats.Agi = ch.curr_stats.Int = stat;
    ch.curr_stats.Pow = ch.curr_stats.Luk = ch.curr_stats.Cha = stat;
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
#define LACKS(page, part) assert(page(&ch).find(part) == std::string::npos)

static void sweep_pages() {
    bool bad = false;
    for (const Viewer &v : viewers) {
        for (int level = 1; level <= 60; ++level) {
            for (int rating : { 0, 1, 2, 25, 35, 36, 50, 51, 60, 70, 75, 76, 79, 80, 90, 91, 100 }) {
                for (int stat : { 1, 100, 180 }) {
                    char_data ch = viewer(v, level, stat);
                    set_ratings(rating);
                    blind_singer = level > 30;
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
                                one.find("--") != std::string::npos || one.find(": -1-") != std::string::npos) {
                                std::fprintf(stderr, "%s, %s %d rating %d: bad line (%zu): %s\n", page.name, v.name,
                                             level, rating, one.size(), one.c_str());
                                bad = true;
                            }
                            from = line + 1;
                        }
                    }
                }
            }
        }
    }
    blind_singer = false;
    if (bad)
        std::abort();
}

static void check_rolls() {
    for (int level : { 1, 8, 9, 10, 17, 30, 50, 56, 60 }) {
        for (int empower : { 0, 25, 100 }) {
            SAME((int)(level * 3 + empower / 4 + number(-4, 4)), song_harming_damage(rolls, level, empower));
            int dam;
            SAME((dam = (int)(level * 3 + empower / 4 + number(-4, 4)), dam = (int)dam * get_property("song.bard.harming.mod", 1.000), dam),
                 song_harming_scaled_damage(song_harming_damage(rolls, level, empower)));
        }
        SAME(number(MAX(1, level / 18), MIN(6, level / 9)) * WAIT_SEC, song_harming_blind_duration(rolls, level));
    }
    SAME(number(-2, 2), song_level_roll(rolls));
    SAME(number(1, 4), song_healing_cap_gap(rolls));
    SAME(number(0, 1), song_revelation_invisible_roll(rolls));
    SAME(number(0, 2), song_revelation_farsee_roll(rolls));
    SAME(number(5, 10), song_harming_wither_levels(rolls));
    SAME(number(0, 2), song_storms_strike_roll(rolls));
    SAME(number(0, 4), song_storms_cyclone_roll(rolls));
    SAME(number(0, 4), song_storms_call_lightning_roll(rolls));
    SAME(number(0, 2), song_chaos_spell_roll(rolls));
    SAME(number(0, 7), song_chaos_spell_pick(rolls));
    SAME(dice(5, 20), song_chaos_damage(rolls));
    SAME(number(0, 3), song_chaos_teleport_roll(rolls));
    SAME(number(0, 3), song_dragons_ward_roll(rolls));
    SAME(number(9, 13), roar_of_heroes_con_max(rolls));
    SAME(number(1, 101) * 6 / 5, subterfuge_roll(rolls));
    SAME(number(0, 2), advanced_meditation_poison_roll(rolls));
    SAME(number(1, 3) * PULSE_VIOLENCE, throat_crush_silence(rolls));
    SAME(number(2, 4) * PULSE_VIOLENCE, throat_crush_cooldown(rolls));
    SAME(number(40, 70), hamstring_vitality_drain(rolls));
    SAME(number(0, 2), trap_spring_roll(rolls));
    SAME(dice(5, 5), trap_dart_damage(rolls));
    SAME(number(3, 7), trap_bleed_count(rolls));
    SAME(dice(3, 6), sneaky_strike_bleed_damage(rolls));
    SAME(4 * (dice(5, 10)), disruptive_blow_damage(rolls));
    SAME(number(0, 1), quick_chant_tank_roll(rolls));
    char_data ch = viewer(viewers[0], 56);
    for (int rating : { 0, 39, 40, 79, 80, 100 }) {
        set_ratings(rating);
        SAME(std::max(0, GET_CHAR_SKILL(&ch, SKILL_CHANT_MASTERY) / 40 + number(-1, 1)), chant_mastery_result(rolls, &ch));
        SAME(std::max(0, GET_CHAR_SKILL(&ch, SKILL_SPATIAL_FOCUS) / 40 + number(-1, 1)), spatial_focus_result(rolls, &ch));
    }
}

static void check_numbers() {
    // Fixed values the handlers used, and the arithmetic of the plain moves.
    for (int value : { 0, 1, 7, 37, 100, 101, 250 }) {
        assert(bard_instrument_mastery(value) == value / 2 + 50.0);
        assert(bard_instrument_chance(value, 25, 60) == (value * ((100 - 25) * 100 + 25 * 60)) / (100 * 100));
        assert(chant_mastery_good_lag(value) == value >> 1);
        assert(chant_mastery_fair_lag(value) == (int)(value * 0.8));
        assert(chant_mastery_fair_time(value) == (int)(value * 0.6));
        assert(chant_mastery_low_time(value) == (int)(value * 0.8));
        assert(quick_chant_cast_time(value) == value >> 1);
        assert(totemic_mastery_cast_time(value) == (int)(value * .75));
        assert(natures_sanctity_cast_time(value) == (int)(value * .75));
        assert(natures_ruin_cast_time(value) == (int)(value * .75));
        assert(spatial_focus_mana_cost(value) == (int)(value * 35 / 10));
        assert(silent_spell_threshold(value) == BOUNDED(25, value, 100));
        assert(song_dissonance_disharmonist_bonus(value) == (int)(value * 1.20));
        assert(song_verse_failure_rest(value) == value / 3 + WAIT_SEC);
        assert(song_start_failure_rest(value) == value / 2 + WAIT_SEC);
    }
    assert(bard_pulse(false) == PULSE_BARD_UPDATE && bard_pulse(true) == PULSE_BARD_UPDATE - 10);
    assert(song_cowardice_penalty(1, 0) == -2 && song_cowardice_penalty(56, 100) == -17);
    assert(song_cowardice_flee_levels(100) == 5 && song_cowardice_flee_levels(39) == 1);
    assert(song_heroism_singer_pulse(19) == 0 && song_heroism_singer_pulse(40) == -2);
    assert(flurry_hits_per_target(8, 1, 4) == 4 && flurry_hits_per_target(8, 3, 4) == 3 && flurry_hits_per_target(8, 100, 4) == 1);
    assert(hitall_lag(0) == 2 * PULSE_VIOLENCE && hitall_lag(5) == 2 * PULSE_VIOLENCE && hitall_lag(6) == 3 * PULSE_VIOLENCE);
    assert(dirt_toss_blindness(100, 100, 0) == 40 && dirt_toss_blindness(100, 100, 1000) == 20 && dirt_toss_blindness(100, 100, 75) == 25);
    assert(hamstring_threshold(100, 57) == 95);
    assert(!spell_knowledge_hears_name(101, 100) && spell_knowledge_hears_name(99, 100) && !spell_knowledge_hears_name(101, 1));
    assert(spell_book_recognizes(30, 30) && !spell_book_recognizes(30, 31));
    // Each odds printer counts the results a handler's comparison passes.
    assert(chance_under(91, 1, 90) == "90 in 90" && chance_under(1, 1, 90) == "0 in 90");
    int hits = 0;
    for (int roll = 1; roll <= 300; ++roll)
        hits += 150 > roll; // skill > number(1, 300)
    assert(chance_under(150, 1, 300) == std::to_string(hits) + " in 300");
    assert(throw_potion_rest(false, false) == (int)(1.75f * PULSE_VIOLENCE));
    assert(throw_potion_rest(false, true) == (int)((float)(1.75f * 0.8) * PULSE_VIOLENCE));
    assert(throw_potion_rest(true, false) == (int)((float)(1.75f * 0.5) * PULSE_VIOLENCE));
    assert(throw_potion_rest(true, true) == throw_potion_rest(true, false));
    assert(advanced_meditation_interval() == 3 * WAIT_SEC);
    for (int rating : {0, 1, 9, 10, 50, 100}) {
        char_data meditator{};
        ratings[SKILL_ADVANCED_MEDITATION] = rating;
        assert(advanced_meditation_stun_flee_bonus(&meditator) == rating / 10);
    }
}

static void check_pages() {
    learned_levels[SONG_HARMING] = 36;
    learned_levels[SONG_CHAOS] = 46;
    char_data ch = viewer(viewers[1], 56); // minstrel
    learned_spec_level = 36;
    set_ratings(100);
PINS
}

int main() {
    check_rolls();
    check_numbers();
    check_pages();
    sweep_pages();
    puts("PASS: skills batch 3 shared rolls match the old code and stay in range, facts never roll");
}
'''

PINS = r'''
    HAS(song_harming_facts, "  Sound damage at song level 56: 226-236\n  Chance each verse reaches each target: 75 in 100\n  A riff always reaches them.\n"
                            "  Magic resistance can stop it. Globes do not, and it can't be deflected.\n");
    HAS(song_harming_facts, "  Blindness if the target fails its save: 3 seconds to 6 seconds\n");
    HAS(song_harming_facts, "  It also poisons those not poisoned, at 5 levels under your song level.\n  Rating to also wither: 70, at 5-10 levels under your song level\n");
    HAS(song_harming_facts, "  Verses: 56, one every 8.75 seconds, 6.25 seconds if hasted\n  No singing after fumbling the first notes: 5.5 seconds\n"
                            "  No singing after fumbling a verse: 4 seconds\n  No singing after you stop it yourself: 2 seconds\n"
                            "  Numbers here use your level, 56, as the song level. Your rating\n  and instrument set the real one, and each verse adds -2 to 2 to it.\n");
    HAS(song_healing_facts, "  Each verse heals you at song level 56: 40\n  Each verse heals others: 26\n  It stops short of full hit points by: 1-4\n"
                            "  Another bard's healing song can't reach them for: 12 seconds\n");
    HAS(song_healing_facts, "  Rating to also cure poison: 50\n  Rating to also cure disease and plague: 70\n  Rating to also cure blindness: 90\n");
    HAS(song_cowardice_facts, "  Hitroll and damroll at song level 56: -17\n");
    HAS(song_cowardice_facts, "  Chance a target flees each verse: 10 in 101, then 100 in 101\n  Highest level that flees: 61\n");
    HAS(song_chaos_facts, "  Sound damage: 5-100\n");
    HAS(song_chaos_facts, "  Chance it teleports a target that fails its save: 1 in 4, at level 30\n");
    HAS(song_chaos_facts, "  Chance of a spell at your song level: 1 in 3 at rating 70\n");
    HAS(song_storms_facts, "  Most lightning bolts per target at song level 56: 9\n  Chance of each bolt: 1 in 3, until one misses\n  Level of each bolt: 112\n");
    HAS(song_storms_facts, "  Chance of a cyclone at your song level: 1 in 5 at rating 70\n  Chance of call lightning with empower song: 1 in 5, at level 46\n");
    HAS(song_dragons_facts, "  Each protection lasts: 18-19 game hours (22.5-23.75 minutes)\n  Fire comes with every verse. The others have this chance each verse:\n"
                            "  Cold at song level above 17: 3 in 4\n  Gas at song level above 19: 3 in 4\n  Acid at song level above 21: 3 in 4\n  Lightning at song level above 23: 3 in 4\n");
    HAS(song_drifting_facts, "  Chance each verse: 99 in 300\n");
    HAS(song_flight_facts, "  Flight at song level 56: 56-57 game hours (70-71.25 minutes)\n  Vitality regeneration while you sing: +28\n");
    HAS(song_flight_facts, "  It works on you and your group in the room.\n");
    LACKS(song_flight_facts, "everyone");
    HAS(song_heroism_facts, "  Combat pulse and spell pulse: -1\n  Yours instead: -2 at song level 56\n");
    HAS(song_peace_facts, "  Peace if the target fails its save: 1-2 game hours (1.25-2.5 minutes)\n");
    HAS(song_revelation_facts, "  Song levels from empower song: +4\n  Detect magic at song level above 7: every verse\n  Detect good and evil at song level above 13: every verse\n"
                               "  Farsee at song level above 21: 1 in 3 each verse\n  Sense life at song level above 30: every verse\n  Detect invisible at song level above 30: 1 in 2 each verse\n");
    HAS(song_dissonance_facts, "  Your strength: 159\n");
    HAS(song_dissonance_facts, "  That singer's lag: 4 seconds\n  Chance to free a pet with its master here: 158 in 2000\n  A freed pet dies after: 90 seconds\n");
    LACKS(song_dissonance_facts, "disharmonist");
    HAS(song_dissonance_facts, "  Only eligible hostile targets in the room, excluding your group and gods.\n");
    HAS(empower_song_facts, "  Harming's damage: +25\n  Protection's armor class: -50\n  Flight's vitality regeneration: +10\n  Revelation's song levels: +4\n"
                            "  Cowardice's hitroll and damroll at song level 56: -17\n  Levels above yours that cowardice can make flee: 5\n  Dissonance's strength: +33\n");
    HAS(riff_facts, "  Chance: 90 in 90\n  Rest if you can't recall the lines: 8 seconds\n  Rest after a verse: 16 seconds\n  Your lag after a verse: 4 seconds\n");
    HAS(instrument_harp_facts, "  Songs it plays: calming, peace\n  Share of your song level from the instrument: 25%\n"
                               "  How much of the instrument's level your rating gets: 100%\n  Song chance threshold with your rating: 100% of normal\n");
    LACKS(instrument_harp_facts, "without seeing");
    blind_singer = true;
    HAS(instrument_lyre_facts, "  Songs it plays: harming, healing\n");
    HAS(instrument_lyre_facts, "  Rating to play it without seeing it: 70\n");
    blind_singer = false;
    HAS(advanced_meditation_facts, "  Hit point regeneration: +75\n  Vitality regeneration: +5\n  Your lag when you start: 2 seconds\n  Chance to cure yourself: 50 in 101 every 3 seconds\n");
    HAS(advanced_meditation_facts, "  It cures blindness, at level: 50\n  It cures poison, on a further: 1 in 3\n  It cures disease and plague.\n"
                                   "  Chance to keep meditating as you speak or emote: 60 in 60\n  Added to fleeing while stunned, a threshold rolled 1-100: 10\n");
    HAS(dirt_toss_facts, "  Blindness on a target with no agility: 10 seconds\n  Blindness on the most agile target: 5 seconds\n  Your lag: 4 seconds\n");
    HAS(disarm_facts, "  Chance against a target of your dexterity and level: 49 in 100\n");
    HAS(disarm_facts, "  You must be fighting the target.\n  Time before the weapon can be wielded again: 12 seconds\n");
    HAS(disarm_facts, "  A failed roll that fumbles your own weapon, with the same wait: 90 or more\n  Your lag: 8 seconds\n");
    HAS(flurry_of_blows_facts, "  Chance on each target: 101 in 101\n  Attacks to spend: twice your normal attacks plus one, shared by the targets\n"
                               "  Hits on each target: at least 1, at most your attacks\n  Your lag: 12 seconds\n  Rest: 10 seconds\n");
    assert(hitall_facts(&ch) == "  With flurry of blows, this command does that instead.\n");
    HAS(hamstring_facts, "  Chance on a target with no agility: 99 in 100\n  Threshold lost per 10 of the target's agility: 1\n  Threshold lost if the target is aware: 10, or its awareness\n"
                         "  Vitality drained on a hit: 40-70, leaving at least 20\n  The target's awareness after a hit: 5-6 game hours (6.25-7.5 minutes)\n  Your lag: 8 seconds\n");
    HAS(lore_facts, "  Chance: 100 in 101\n  Your lag: 0.75 seconds\n  Your lag if you fail: 0.25 seconds\n");
    HAS(lore_facts, "  Lowest level character you can lore: 40\n");
    HAS(remix_facts, "  Chance to keep a potion thrown at an NPC: 99 in 120\n");
    HAS(roar_of_heroes_facts, "  Level needed to roar: 56\n  Constitution maximum: +9-13\n  Duration: 5-6 game hours (6.25-7.5 minutes)\n");
    HAS(subterfuge_facts, "  Chance threshold: your rating, 100, against a roll of 1-121\n  Chance a target above your level resists: 5 for each level, against 1-101\n");
    HAS(throat_crush_facts, "  Damage: 30\n  The target's defenses apply after.\n  Target can't speak or cast for: 4 seconds to 12 seconds\n");
    HAS(throat_crush_facts, "  Before you can do it again: 8 seconds to 16 seconds\n  Your lag: 4 seconds\n  Your lag on a miss: 8 seconds\n");
    assert(throat_crusher_facts(&ch) == "  Before you can throat crush again: 8 seconds to 16 seconds\n  Your lag if you try sooner: 4 seconds\n");
    HAS(throwpotion_facts, "  Chance a throw at someone is steady, from your agility: 100 in 140\n  Otherwise the potion is lost.\n"
                           "  Chance a steady throw goes astray, to anyone or the floor: 1 in 101\n  Your lag: 3 seconds\n  Before you can throw again: 7 seconds\n"
                           "  With haste: 5.5 seconds\n  With flurry: 3.5 seconds\n");
    HAS(trap_facts, "  Your lag when you hide and arm a trap: 4 seconds\n  How long it stays armed: 30 minutes\n  Chance it springs as someone tries to leave: 2 in 3\n");
    HAS(trap_facts, "  Dart trap damage, with no reductions: 5-25\n  Poison trap's level: 56\n  Crippling trap's limp: 10 seconds, 5 more vitality per move\n  Its bleeding: 3-7 rounds, each 3-18\n");
    HAS(war_cry_facts, "  Hit points: +50\n  Hitroll and damroll: +5\n  Duration in a group: 5-6 game hours (6.25-7.5 minutes)\n  Duration alone: 2-3 game hours (2.5-3.75 minutes)\n  Your lag: 8 seconds\n");
    assert(chant_mastery_facts(&ch) == "  Chance on each cast: 15 in 101\n  Best result: cast time 0.25 seconds, lag 0.25 seconds\n"
                                       "  Good result: cast time 0.25 seconds, lag 50%\n  Fair result: cast time 60%, lag 80%\n");
    HAS(concentration_facts, "  Chance to keep casting after being knocked to your knees or seat: 50 in 121\n");
    HAS(disruptive_blow_facts, "  Chance to hit a caster that starts a spell: 65 in 131\n  Chance of those that also stop the spell: 25 in 131\n  Damage: 20-200\n");
    assert(natures_ruin_facts(&ch) == "  Chance outdoors to hasten a cast: 99 in 100\n  Cast time and lag then: 75%\n"
                                      "  Chance outdoors to speed recovering a spell: 99 in 100\n  Recovery time then: 65%\n");
    assert(natures_sanctity_facts(&ch) == natures_ruin_facts(&ch));
    HAS(quick_chant_facts, "  Chance: 99 in 100\n  Cast time then: 50%, same lag\n  Chance it is tried while you are being attacked: 1 in 2\n");
    HAS(silent_spell_facts, "  Chance to start a spell where you can't speak: 100 in 101\n  Your lag if your hands fail you: 4 seconds\n");
    HAS(spatial_focus_facts, "  Chance on each spell you will: 15 in 101\n  At its best, the spell comes at once, with 0.25 seconds of lag.\n"
                             "  Chance to pay less mana: 49 in 100\n  Mana per circle then: 3.5, not 7\n");
    HAS(spellweave_facts, "  How long a woven spell keeps: 5-6 game hours (6.25-7.5 minutes)\n  Chance it works when you call it forth: 100 in 101\n");
    assert(totemic_mastery_facts(&ch) == "  Chance to prepare a spell without its totem: 99 in 100\n  Chance to hasten a cast when you have the totem: 50 in 151\n  Cast time and lag then: 75%\n");
    HAS(spell_knowledge_magical_facts, "  Chance to recognize a spell someone starts: 100 in 101\n  You then know whether it is offensive.\n  Then the chance to know its name: 60 in 100\n"
                                       "  Chance to hear the name when it is cast: 100 in 101\n"
                                       "  Chance to name a spell in a book not of your class: 100 in 100, then 56 in 70\n");
    HAS(spell_knowledge_shaman_facts, "  Chance to see how your casting is going: 100 in 100 at each step\n");
    LACKS(spell_knowledge_magical_facts, "how your casting");
    LACKS(spell_knowledge_shaman_facts, "in a book");

    // Spec and class branches.
    ch = viewer(viewers[0], 56); // plain bard
    LACKS(song_chaos_facts, "Chance of a spell");
    LACKS(song_storms_facts, "cyclone");
    LACKS(song_healing_facts, "cure");
    LACKS(song_harming_facts, "wither");
    HAS(lore_facts, "  Lowest level character you can lore: 50\n");
    ch = viewer(viewers[2], 56); // disharmonist
    HAS(song_dissonance_facts, "  Included disharmonist bonus: 120%\n");
    ch = viewer(viewers[6], 56); // berserker
    set_ratings(0);
    ratings[SKILL_HITALL] = 80;
    HAS(hitall_facts, "  Chance on each target: 80 in 101\n  Your lag: 8 seconds, or 12 seconds with 6 targets, and so on\n"
                      "  Your lag while raging: 8 seconds\n  While raging, each target also takes a hit that needs no roll.\n");
    ch = viewer(viewers[4], 50); // warrior
    LACKS(hitall_facts, "raging");
    ch = viewer(viewers[5], 50); // swashbuckler
    HAS(disarm_facts, "  Threshold change if it starts the fight: -15\n  Threshold change on another foe while in a fight: -30\n");
    LACKS(disarm_facts, "You must be fighting");
    LACKS(disarm_facts, "Chance against");
    ch = viewer(viewers[7], 50); // thief
    ratings[SKILL_DISARM] = 80;
    HAS(disarm_facts, "  Chance to disarm a trap: 79 in 91\n  Failing sets it off.\n");
    HAS(lore_facts, "  You can only lore items.\n");
    ch = viewer(viewers[15], 50); // druid
    set_ratings(0);
    HAS(quick_chant_facts, "  As a single-class druid or blighter you always cast this fast.\n");
    ratings[SKILL_SPELL_KNOWLEDGE_CLERICAL] = 40;
    HAS(spell_knowledge_clerical_facts, "  You always see how your casting is going.\n");
    ch = viewer(viewers[17], 50); // cleric
    HAS(spell_knowledge_clerical_facts, "  Chance to see how your casting is going: 40 in 100 at each step\n");

    // Rating 0: no chance for what the handler refuses, nothing built from nothing.
    set_ratings(0);
    ch = viewer(viewers[0], 56);
    for (AbilityFacts page : { flurry_of_blows_facts, hitall_facts, hamstring_facts, dirt_toss_facts, throwpotion_facts, disruptive_blow_facts })
        assert(page(&ch).find("Chance ") == std::string::npos);
    for (AbilityFacts page : { chant_mastery_facts, advanced_meditation_facts, silent_spell_facts, spatial_focus_facts, natures_ruin_facts, natures_sanctity_facts, totemic_mastery_facts })
        assert(page(&ch) == "  You have not learned it, so it does nothing for you.\n");
    assert(empower_song_facts(&ch) == "  You have not learned it, so it adds nothing to your songs.\n");
    assert(spellweave_facts(&ch) == "  You have not mastered it, so you can't weave.\n");
    assert(spell_knowledge_shaman_facts(&ch) == "  You have not learned it, so you recognize no spells by it.\n");
    LACKS(song_healing_facts, "No singing after");
    assert(war_cry_facts(&ch) == "  You have not learned it, so you can't use it.\n");
    HAS(riff_facts, "  Chance: 0 in 90\n");
    HAS(song_cowardice_facts, "  Hitroll and damroll at song level 56: -7\n");

    // Boundaries and low levels.
    ch = viewer(viewers[0], 1);
    HAS(song_harming_facts, "  Sound damage at song level 1: 0-8 (none below 1 lands)\n");
    LACKS(song_harming_facts, "Blindness");
    LACKS(song_harming_facts, "poisons");
    HAS(song_storms_facts, "  Most lightning bolts per target at song level 1: 0\n");
    HAS(song_dragons_facts, "  Each protection lasts: up to 1 game hour (up to 1.25 minutes)\n");
    ch = viewer(viewers[0], 40);
    LACKS(song_harming_facts, "Blindness");
    ch = viewer(viewers[0], 41);
    HAS(song_harming_facts, "  Blindness if the target fails its save: 2 seconds to 4 seconds\n");
    LACKS(song_harming_facts, "poisons");
    ch = viewer(viewers[0], 51);
    HAS(song_harming_facts, "  It also poisons those not poisoned, at 5 levels under your song level.\n");
    ch = viewer(viewers[0], 20);
    LACKS(song_heroism_facts, "casts haste");
    ch = viewer(viewers[0], 21);
    HAS(song_heroism_facts, "  It also casts haste at your song level on those without it.\n");
    ch = viewer(viewers[0], 49);
    HAS(lore_facts, "  You can't lore an item that can't be identified until level 50.\n");
    ch = viewer(viewers[0], 50);
    LACKS(lore_facts, "can't be identified");
    set_ratings(50);
    LACKS(advanced_meditation_facts, "Vitality");
    HAS(advanced_meditation_facts, "  Your lag when you start: 4 seconds\n");
    LACKS(advanced_meditation_facts, "poison");
    set_ratings(51);
    HAS(advanced_meditation_facts, "  Your lag when you start: 2 seconds\n");
    HAS(advanced_meditation_facts, "  It cures poison, on a further: 1 in 3\n");
    set_ratings(90);
    LACKS(advanced_meditation_facts, "disease");
    set_ratings(91);
    HAS(advanced_meditation_facts, "  It cures disease and plague.\n");
    set_ratings(79);
    HAS(spatial_focus_facts, "  At your rating, that only changes the message.\n");
    set_ratings(80);
    HAS(spatial_focus_facts, "  At its best, the spell comes at once, with 0.25 seconds of lag.\n");
    set_ratings(30);
    assert(chant_mastery_facts(&ch) == "  Chance on each cast: 8 in 101\n  Fair result: cast time 60%, lag 80%\n  Low result: cast time 80%, full lag\n");
    set_ratings(1);
    HAS(throwpotion_facts, "  Chance a steady throw lands as aimed: 1 in 100\n");
    set_ratings(10);
    HAS(silent_spell_facts, "  Chance to start a spell where you can't speak: 25 in 101\n");
    set_ratings(99);
    ch = viewer(viewers[0], 56);
    LACKS(song_storms_facts, "call lightning");
'''


def squeeze(text):
    return re.sub(r"\s+", "", text)


def body(file, head):
    bodies = function_bodies(strip_comments(source(file).read_text()), re.escape(head) + r"\s*\(")
    assert bodies, head
    return [squeeze(one) for one in bodies]


def check_sources():
    for (file, head), calls in CALLS.items():
        bodies = body(file, head)
        for call in calls:
            assert any(call in one for one in bodies), f"{head} does not call {call}"
    for (file, head), branches in BRANCHES.items():
        one = body(file, head)[0]
        for anchor, kind, call in branches:
            at = one.index(anchor)
            assert one.find(kind, at) == one.find(call, at) >= 0, f"{head}: after {anchor!r} the next {kind} is not {call}"
    # All four Heroism effects share the song lifecycle.
    heroism = body("bard.c", "void bard_heroism")[0]
    assert "af.modifier=song_heroism_hit_dam(l,empower)" in heroism
    assert heroism.count("linked_affect_to_char(recipient,&af,ch,LNK_SONG)") == 4
    assert "notch_skill(ch,SKILL_THROAT_CRUSH,get_property(\"skill.notch.offensive\",4));if(number(1,100)>skl_lvl)" in body("actnew.c", "void do_throat_crush")[0]
    table = strip_comments(source("abilities.c").read_text())
    header = source("abilities.h").read_text()
    pending = (ROOT / "tests/fixtures/ability_coverage_pending.txt").read_text().split()
    for constant, name, file in SKILLS:
        assert re.search(rf"case {constant}:\s*return {name}_facts;", table), constant
        assert f"std::string {name}_facts(char_data *ch);" in header, name
        assert constant not in pending, constant
        assert function_bodies(strip_comments(source(file).read_text()), rf"std::string\s+{name}_facts\s*\("), name


def main():
    check_sources()
    functions = [extract_function("utility.c", "int dice(int num, int size)"),
                 extract_function("utility.c", "int BOUNDED(int a, int b, int c)"),
                 extract_function("utility.c", "int GET_CLASS(P_char ch, uint m_class)")]
    facts = {}
    for constant, name, file in SKILLS:
        facts.setdefault(file, []).append(name)
    order = ["actoff.c", "actmove.c", "actinf.c", "memorize.c", "bard.c", "actnew.c", "specs.object.c", "epic_skills.c", "sparser.c"]
    for file in order:
        text = source(file).read_text()
        for name in SHARED[file]:
            match = re.search(rf"^(?:static )?[\w:]+(?: \w+)? \*?{name}\([^;\n]*\)$", text, re.M)
            assert match, name
            functions.append(extract_function(file, match.group(0) + "\n{"))
        for name in facts.get(file, []):
            functions.append(extract_function(file, f"std::string {name}_facts(P_char"))
    bard = source("bard.c").read_text()
    table = bard[bard.index("typedef void song_function"):bard.index("struct echo_details")]
    stubs = "".join(f"void {name}(int, P_char, P_char, int) {{}}\n" for name in re.findall(r"^void (bard_\w+)\(int, P_char, P_char, int\);", bard, re.M))
    pages = ",\n".join(f'    {{ "{name}", {name}_facts }}' for _, name, _ in SKILLS)
    skills = ", ".join(sorted({c for c, _, _ in SKILLS}))
    build = ROOT / "bin/tests"
    build.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ability-skills-3-", dir=build) as temporary:
        directory = Path(temporary)
        harness = directory / "skills3.cpp"
        harness.write_text(HARNESS.replace("PAGES", pages).replace("SKILLS", skills).replace("PINS", PINS)
                           .replace("SONG_TABLE", table + stubs).replace("FUNCTIONS", "\n".join(functions)))
        binary = directory / "skills3"
        subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-Wno-unused-function",
                        "-ffunction-sections", "-fdata-sections", "-Wl,--gc-sections",
                        "-fsanitize=address,undefined", "-fno-sanitize-recover=undefined",
                        "-Isrc", "-I/usr/include/mysql", "-I/usr/include/libxml2",
                        str(harness), "src/abilities/abilities.c", "src/core/random.c",
                        "-o", str(binary)], cwd=ROOT, check=True)
        subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    main()
