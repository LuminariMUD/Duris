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

// Info page styling shared by spells info, skills info and innate info: labels in cyan,
// numbers in bright white. Facts stay plain text; mechanics_section() styles them.
std::string info_field(const std::string &label, const std::string &value);
std::string mechanics_section(const std::string &facts);

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
std::string repair_one_item_facts(char_data *ch);
std::string magma_burst_facts(char_data *ch);
std::string electrical_execution_facts(char_data *ch);
std::string dread_wave_facts(char_data *ch);
std::string group_heal_facts(char_data *ch);
std::string apocalypse_facts(char_data *ch);
std::string judgement_facts(char_data *ch);
std::string chaotic_ripple_facts(char_data *ch);
std::string chaos_volley_facts(char_data *ch);
std::string blink_facts(char_data *ch);
std::string natures_calling_facts(char_data *ch);
std::string pleasantry_facts(char_data *ch);
std::string contain_being_facts(char_data *ch);
std::string negative_concussion_blast_facts(char_data *ch);
std::string accel_healing_facts(char_data *ch);
std::string mielikki_vitality_facts(char_data *ch);
std::string spore_burst_facts(char_data *ch);
std::string spore_cloud_facts(char_data *ch);
std::string life_bolt_facts(char_data *ch);
std::string knock_facts(char_data *ch);
std::string tranquility_facts(char_data *ch);
std::string dazzle_facts(char_data *ch);
std::string pass_without_trace_facts(char_data *ch);
std::string starshell_facts(char_data *ch);
std::string stornogs_spheres_facts(char_data *ch);
std::string cloak_of_fear_facts(char_data *ch);
std::string acidimmolate_facts(char_data *ch);
std::string immolate_facts(char_data *ch);
std::string cdoom_facts(char_data *ch);
std::string sense_follower_facts(char_data *ch);
std::string perm_increase_facts(char_data *ch);
std::string soulshield_facts(char_data *ch);
std::string holy_dharma_facts(char_data *ch);
std::string holy_sacrifice_facts(char_data *ch);
std::string battle_ecstasy_facts(char_data *ch);
std::string mass_heal_facts(char_data *ch);
std::string true_seeing_facts(char_data *ch);
std::string shadow_vision_facts(char_data *ch);
std::string animal_vision_facts(char_data *ch);
std::string tree_facts(char_data *ch);
std::string animal_growth_facts(char_data *ch);
std::string natures_blessing_facts(char_data *ch);
std::string enlarge_facts(char_data *ch);
std::string rope_trick_facts(char_data *ch);
std::string reduce_facts(char_data *ch);
std::string command_facts(char_data *ch);
std::string chaos_shield_facts(char_data *ch);
std::string vampire_facts(char_data *ch);
std::string divine_blessing_facts(char_data *ch);
std::string moonwell_facts(char_data *ch);
std::string shadow_gate_facts(char_data *ch);
std::string moonstone_facts(char_data *ch);
std::string animae_cicatrix_facts(char_data *ch);
std::string stigmata_draconica_facts(char_data *ch);
std::string drakescale_aegis_facts(char_data *ch);
std::string judicium_fidei_facts(char_data *ch);
std::string igneus_vitae_facts(char_data *ch);
std::string sanguinis_ignis_facts(char_data *ch);
std::string sanctum_draconis_facts(char_data *ch);
std::string vivernae_concordia_facts(char_data *ch);
std::string pactum_serpentis_facts(char_data *ch);
std::string edictum_cineris_facts(char_data *ch);
std::string sigillum_negati_facts(char_data *ch);
std::string draconic_apotheosis_facts(char_data *ch);
std::string warring_zeal_facts(char_data *ch);
std::string cure_serious_facts(char_data *ch);
std::string cure_critic_facts(char_data *ch);
std::string cure_light_facts(char_data *ch);
std::string curse_facts(char_data *ch);
std::string nether_touch_facts(char_data *ch);
std::string detect_evil_facts(char_data *ch);
std::string detect_good_facts(char_data *ch);
std::string detect_magic_facts(char_data *ch);
std::string detect_invisibility_facts(char_data *ch);
std::string unmaking_facts(char_data *ch);
std::string enchant_weapon_facts(char_data *ch);
std::string full_heal_facts(char_data *ch);
std::string heal_facts(char_data *ch);
std::string natures_touch_facts(char_data *ch);
std::string water_to_life_facts(char_data *ch);
std::string healing_salve_facts(char_data *ch);
std::string sticks_to_snakes_facts(char_data *ch);
std::string shadow_projection_facts(char_data *ch);
std::string concealment_facts(char_data *ch);
std::string invisibility_facts(char_data *ch);
std::string disease_facts(char_data *ch);
std::string major_paralysis_facts(char_data *ch);
std::string minor_paralysis_facts(char_data *ch);
std::string slow_facts(char_data *ch);
std::string stornogs_lowered_res_facts(char_data *ch);
std::string protection_from_evil_facts(char_data *ch);
std::string protection_from_good_facts(char_data *ch);
std::string stone_skin_facts(char_data *ch);
std::string group_stone_skin_facts(char_data *ch);
std::string ironwood_facts(char_data *ch);
std::string sleep_facts(char_data *ch);
std::string dexterity_facts(char_data *ch);
std::string agility_facts(char_data *ch);
std::string strength_facts(char_data *ch);
std::string word_of_recall_facts(char_data *ch);
std::string group_recall_facts(char_data *ch);
std::string summon_facts(char_data *ch);
std::string sense_life_facts(char_data *ch);
std::string blur_facts(char_data *ch);
std::string lodestone_vision_facts(char_data *ch);
std::string haste_facts(char_data *ch);
std::string group_haste_facts(char_data *ch);
std::string recharger_facts(char_data *ch);
std::string invigorate_facts(char_data *ch);
std::string vigorize_serious_facts(char_data *ch);
std::string vigorize_light_facts(char_data *ch);
std::string devitalize_facts(char_data *ch);
std::string divine_warding_facts(char_data *ch);
std::string vitality_facts(char_data *ch);
std::string miracle_facts(char_data *ch);
std::string vital_intercession_facts(char_data *ch);
std::string holy_intercession_facts(char_data *ch);
std::string vitalize_undead_facts(char_data *ch);
std::string death_blessing_facts(char_data *ch);
std::string farsee_facts(char_data *ch);
std::string globe_facts(char_data *ch);
std::string group_globe_facts(char_data *ch);
std::string minor_globe_facts(char_data *ch);
std::string deflect_facts(char_data *ch);
std::string earth_form_facts(char_data *ch);
std::string fire_form_facts(char_data *ch);
std::string water_form_facts(char_data *ch);
std::string air_form_facts(char_data *ch);
std::string plague_facts(char_data *ch);
std::string continual_light_facts(char_data *ch);
std::string airy_water_facts(char_data *ch);
std::string levitate_facts(char_data *ch);
std::string fly_facts(char_data *ch);
std::string barkskin_facts(char_data *ch);
std::string grow_spike_facts(char_data *ch);
std::string identify_facts(char_data *ch);
std::string fortitude_facts(char_data *ch);
std::string armor_facts(char_data *ch);
std::string virtue_facts(char_data *ch);
std::string magic_missile_facts(char_data *ch);
std::string chill_touch_facts(char_data *ch);
std::string burning_hands_facts(char_data *ch);
std::string shocking_grasp_facts(char_data *ch);
std::string frostbite_facts(char_data *ch);
std::string lightning_bolt_facts(char_data *ch);
std::string cone_of_cold_facts(char_data *ch);
std::string enervation_facts(char_data *ch);
std::string restore_spirit_facts(char_data *ch);
std::string energy_drain_facts(char_data *ch);
std::string life_leech_facts(char_data *ch);
std::string wither_facts(char_data *ch);
std::string living_stone_facts(char_data *ch);
std::string greater_living_stone_facts(char_data *ch);
std::string meteorswarm_facts(char_data *ch);
std::string entropy_storm_facts(char_data *ch);
std::string chain_lightning_facts(char_data *ch);
std::string ring_lightning_facts(char_data *ch);
std::string bigbys_clenched_fist_facts(char_data *ch);
std::string missile_barrage_facts(char_data *ch);
std::string anti_magic_ray_facts(char_data *ch);
std::string bigbys_crushing_hand_facts(char_data *ch);
std::string dimension_door_facts(char_data *ch);
std::string relocate_facts(char_data *ch);
std::string wizard_eye_facts(char_data *ch);
std::string rejuvenate_major_facts(char_data *ch);
std::string age_facts(char_data *ch);
std::string rejuvenate_minor_facts(char_data *ch);
std::string ray_of_enfeeblement_facts(char_data *ch);
std::string earthquake_facts(char_data *ch);
std::string call_woodland_beings_facts(char_data *ch);
std::string earthen_maul_facts(char_data *ch);
std::string dispel_evil_facts(char_data *ch);
std::string dispel_good_facts(char_data *ch);
std::string harm_facts(char_data *ch);
std::string full_harm_facts(char_data *ch);
std::string destroy_undead_facts(char_data *ch);
std::string firestorm_facts(char_data *ch);
std::string flamestrike_facts(char_data *ch);
std::string teleport_facts(char_data *ch);
std::string bless_facts(char_data *ch);
std::string blindness_facts(char_data *ch);
std::string nova_facts(char_data *ch);
std::string elemental_swarm_facts(char_data *ch);
std::string serendipity_facts(char_data *ch);
std::string pulchritude_facts(char_data *ch);
std::string create_water_facts(char_data *ch);
std::string wandering_woods_facts(char_data *ch);
std::string aid_facts(char_data *ch);
std::string dispel_lifeforce_facts(char_data *ch);
std::string alter_energy_polarity_facts(char_data *ch);
std::string invoke_negative_energy_facts(char_data *ch);
std::string channel_negative_energy_facts(char_data *ch);
std::string sense_holiness_facts(char_data *ch);
std::string lifelust_facts(char_data *ch);
std::string cyclone_facts(char_data *ch);
std::string siren_song_facts(char_data *ch);
std::string decaying_flesh_facts(char_data *ch);
std::string conjure_elemental_facts(char_data *ch);
std::string conjure_greater_elemental_facts(char_data *ch);
std::string mirror_image_facts(char_data *ch);
std::string vitalize_mana_facts(char_data *ch);
std::string consecrate_land_facts(char_data *ch);
std::string summon_insects_facts(char_data *ch);
std::string prismatic_spray_facts(char_data *ch);
std::string color_spray_facts(char_data *ch);
std::string prismatic_ray_facts(char_data *ch);
std::string elemental_aura_facts(char_data *ch);
std::string wind_tunnel_facts(char_data *ch);
std::string binding_wind_facts(char_data *ch);

// Spell batch 3.
std::string solar_flare_facts(char_data *ch);
std::string sanctuary_facts(char_data *ch);
std::string battletide_facts(char_data *ch);
std::string obtenebration_facts(char_data *ch);
std::string blackmantle_facts(char_data *ch);
std::string regeneration_facts(char_data *ch);
std::string endurance_facts(char_data *ch);
std::string shatter_facts(char_data *ch);
std::string infravision_facts(char_data *ch);
std::string mage_flame_facts(char_data *ch);
std::string globe_of_darkness_facts(char_data *ch);
std::string waterbreath_facts(char_data *ch);
std::string cause_light_facts(char_data *ch);
std::string unholy_wind_facts(char_data *ch);
std::string purge_living_facts(char_data *ch);
std::string cause_serious_facts(char_data *ch);
std::string cause_critical_facts(char_data *ch);
std::string divine_fury_facts(char_data *ch);
std::string negative_energy_barrier_facts(char_data *ch);
std::string lesser_resurrect_facts(char_data *ch);
std::string resurrect_facts(char_data *ch);
std::string preserve_facts(char_data *ch);
std::string dispel_magic_facts(char_data *ch);
std::string hellfire_facts(char_data *ch);
std::string darkness_facts(char_data *ch);
std::string protection_spell_facts(char_data *ch);
std::string elemental_shield_facts(char_data *ch);
std::string incendiary_cloud_facts(char_data *ch);
std::string ice_storm_facts(char_data *ch);
std::string disintegrate_facts(char_data *ch);
std::string acid_stream_facts(char_data *ch);
std::string acid_blast_facts(char_data *ch);
std::string faerie_fire_facts(char_data *ch);
std::string faerie_fog_facts(char_data *ch);
std::string pword_kill_facts(char_data *ch);
std::string pword_blind_facts(char_data *ch);
std::string pword_stun_facts(char_data *ch);
std::string unholy_word_facts(char_data *ch);
std::string voice_of_creation_facts(char_data *ch);
std::string holy_word_facts(char_data *ch);
std::string sunray_facts(char_data *ch);
std::string feeblemind_facts(char_data *ch);
std::string silence_facts(char_data *ch);
std::string turn_undead_facts(char_data *ch);
std::string command_undead_facts(char_data *ch);
std::string comprehend_languages_facts(char_data *ch);
std::string slow_poison_facts(char_data *ch);
std::string embalm_facts(char_data *ch);
std::string elemental_form_facts(char_data *ch);
std::string vampiric_touch_facts(char_data *ch);
std::string prot_undead_facts(char_data *ch);
std::string prot_from_undead_facts(char_data *ch);
std::string heal_undead_facts(char_data *ch);
std::string mend_soul_facts(char_data *ch);
std::string greater_heal_undead_facts(char_data *ch);
std::string entangle_facts(char_data *ch);
std::string create_spring_facts(char_data *ch);
std::string summon_ghasts_facts(char_data *ch);
std::string aid_of_the_heavens_facts(char_data *ch);
std::string ghastly_touch_facts(char_data *ch);
std::string infernal_fury_facts(char_data *ch);
std::string freedom_of_movement_facts(char_data *ch);
std::string divine_font_facts(char_data *ch);
std::string charm_facts(char_data *ch);

#endif
