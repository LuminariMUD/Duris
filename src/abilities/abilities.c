/****************************************************************************
 *
 *  File: abilities.c                                           Part of Duris
 *  Usage: shared ability rolls, fact formatting and the facts table
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-11-04
 *
 ****************************************************************************/

#include "abilities/abilities.h"
#include "core/prototypes.h"
#include "magic/spells.h"

#include <algorithm>
#include <cstdio>

// dice() raises a count or size below 1 to 1; number() accepts its bounds in either order.
static int lowest_dice(int count, int /*sides*/)
{
	return std::max(count, 1);
}

static int highest_dice(int count, int sides)
{
	return std::max(count, 1) * std::max(sides, 1);
}

static int lowest_number(int from, int to)
{
	return std::min(from, to);
}

static int highest_number(int from, int to)
{
	return std::max(from, to);
}

const Rolls live_rolls = { dice, number };
const Rolls lowest_rolls = { lowest_dice, lowest_number };
const Rolls highest_rolls = { highest_dice, highest_number };

std::string fact(const std::string &label, const std::string &text)
{
	return "  " + label + ": " + text + "\n";
}

std::string show(Range range)
{
	if (range.low == range.high)
		return std::to_string(range.low);
	return std::to_string(range.low) + "-" + std::to_string(range.high);
}

std::string seconds(int pulses)
{
	if (pulses == WAIT_SEC)
		return "1 second";
	char text[32];
	snprintf(text, sizeof(text), "%g seconds", pulses / static_cast<double>(WAIT_SEC));
	return text;
}

// Affect durations count ticks, one game hour each; -1 never wears off. affect_update()
// takes one off on each of the owner's ticks and removes the affect on the tick after it
// reaches 0, so an affect set to `ticks` lasts more than `ticks` and up to `ticks + 1`
// game hours.
std::string game_hours(int ticks)
{
	if (ticks == -1)
		return "permanent";
	const double minutes = PULSES_IN_TICK / static_cast<double>(WAIT_SEC) / 60.0;
	char text[96];
	if (ticks == 0)
		snprintf(text, sizeof(text), "up to 1 game hour (up to %.10g minutes)", minutes);
	else
		snprintf(text, sizeof(text), "%d-%d game hours (%.10g-%.10g minutes)", ticks,
			 ticks + 1, ticks * minutes, (ticks + 1) * minutes);
	return text;
}

// A real-time span for longer waits: "12 minutes", "1 minute 15 seconds".
std::string real_time(int pulses)
{
	const int total = pulses / WAIT_SEC;
	if (total < 60)
		return seconds(pulses);
	const int minutes = total / 60, rest = total % 60;
	std::string text = std::to_string(minutes) + (minutes == 1 ? " minute" : " minutes");
	if (rest)
		text += " " + std::to_string(rest) + (rest == 1 ? " second" : " seconds");
	return text;
}

AbilityFacts ability_facts(int skill)
{
	switch (skill)
	{
	case SKILL_BASH:
		return bash_facts;
	case SPELL_FIREBALL:
		return fireball_facts;
	case SPELL_GASEOUS_CLOUD:
		return gaseous_cloud_facts;
	case SPELL_GUARDIAN_SPIRITS:
		return guardian_spirits_facts;
	case SPELL_BLOODHOUND:
		return bloodhound_facts;
	case SPELL_WOLFSPEED:
		return wolfspeed_facts;
	case SPELL_PYTHONSTING:
		return pythonsting_facts;
	case SPELL_SNAILSPEED:
		return snailspeed_facts;
	case SPELL_MOLEVISION:
		return molevision_facts;
	case SPELL_PANTHERSPEED:
		return pantherspeed_facts;
	case SPELL_MOUSESTRENGTH:
		return mousestrength_facts;
	case SPELL_SUMMON_BEAST:
		return summon_beast_facts;
	case SPELL_GREATER_SUMMON_BEAST:
		return greater_summon_beast_facts;
	case SPELL_HAWKVISION:
		return hawkvision_facts;
	case SPELL_BEARSTRENGTH:
		return bearstrength_facts;
	case SPELL_SHREWTAMENESS:
		return shrewtameness_facts;
	case SPELL_LIONRAGE:
		return lionrage_facts;
	case SPELL_ELEPHANTSTRENGTH:
		return elephantstrength_facts;
	case SPELL_RAVENFLIGHT:
		return ravenflight_facts;
	case SPELL_GREATER_RAVENFLIGHT:
		return greater_ravenflight_facts;
	case SPELL_GREATER_PYTHONSTING:
		return greater_pythonsting_facts;
	case SPELL_CALL_OF_THE_WILD:
		return call_of_the_wild_facts;
	case SPELL_BEASTFORM:
		return beastform_facts;
	case SPELL_ELEM_AFFINITY:
		return elemental_affinity_facts;
	case SPELL_CASCADING_ELEMENTAL_BEAM:
		return cascading_elemental_beam_facts;
	case SPELL_ELEM_FURY:
		return elemental_fury_facts;
	case SPELL_ICE_MISSILE:
		return ice_missile_facts;
	case SPELL_FLAMEBURST:
		return flameburst_facts;
	case SPELL_SCALDING_BLAST:
		return scalding_blast_facts;
	case SPELL_COLD_WARD:
		return cold_ward_facts;
	case SPELL_FIRE_WARD:
		return fire_ward_facts;
	case SPELL_SCORCHING_TOUCH:
		return scorching_touch_facts;
	case SPELL_MOLTEN_SPRAY:
		return molten_spray_facts;
	case SPELL_EARTHEN_GRASP:
		return earthen_grasp_facts;
	case SPELL_GREATER_EARTHEN_GRASP:
		return greater_earthen_grasp_facts;
	case SPELL_ARIEKS_SHATTERING_ICEBALL:
		return arieks_shattering_iceball_facts;
	case SPELL_SCATHING_WIND:
		return scathing_wind_facts;
	case SPELL_EARTHEN_RAIN:
		return earthen_rain_facts;
	case SPELL_TORMENT_SPIRITS:
		return torment_spirits_facts;
	case SPELL_INDOMITABILITY:
		return indomitability_facts;
	case SPELL_SPIRIT_ARMOR:
		return spirit_armor_facts;
	case SPELL_TRANSFER_WELLNESS:
		return transfer_wellness_facts;
	case SPELL_LESSER_MENDING:
		return lesser_mending_facts;
	case SPELL_MENDING:
		return mending_facts;
	case SPELL_SOUL_DISTURBANCE:
		return soul_disturbance_facts;
	case SPELL_SPIRIT_SIGHT:
		return spirit_sight_facts;
	case SPELL_SENSE_SPIRIT:
		return sense_spirit_facts;
	case SPELL_MALISON:
		return malison_facts;
	case SPELL_WELLNESS:
		return wellness_facts;
	case SPELL_GREATER_MENDING:
		return greater_mending_facts;
	case SPELL_SPIRIT_ANGUISH:
		return spirit_anguish_facts;
	case SPELL_GREATER_SPIRIT_ANGUISH:
		return greater_spirit_anguish_facts;
	case SPELL_GREATER_SOUL_DISTURB:
		return greater_soul_disturbance_facts;
	case SPELL_SPIRIT_WARD:
		return spirit_ward_facts;
	case SPELL_SPIRIT_JUMP:
		return spirit_jump_facts;
	case SPELL_GREATER_SPIRIT_SIGHT:
		return greater_spirit_sight_facts;
	case SPELL_GREATER_SPIRIT_WARD:
		return greater_spirit_ward_facts;
	case SPELL_ETHERPORTAL:
		return etherportal_facts;
	case SPELL_SPIRIT_WALK:
		return spirit_walk_facts;
	case SPELL_CORROSIVE_BLAST:
		return corrosive_blast_facts;
	case SPELL_FIREBRAND:
		return firebrand_facts;
	case SPELL_RESTORATION:
		return restoration_facts;
	case SPELL_LESSER_GUARDIAN_WARD:
		return lesser_guardian_ward_facts;
	case SPELL_GUARDIAN_WARD:
		return guardian_ward_facts;
	case SPELL_GREATER_GUARDIAN_WARD:
		return greater_guardian_ward_facts;
	case SPELL_REPAIR_ONE_ITEM:
		return repair_one_item_facts;
	case SPELL_MAGMA_BURST:
		return magma_burst_facts;
	case SPELL_ELECTRICAL_EXECUTION:
		return electrical_execution_facts;
	case SPELL_DREAD_WAVE:
		return dread_wave_facts;
	case SPELL_GROUP_HEAL:
		return group_heal_facts;
	case SPELL_APOCALYPSE:
		return apocalypse_facts;
	case SPELL_JUDGEMENT:
		return judgement_facts;
	case SPELL_CHAOTIC_RIPPLE:
		return chaotic_ripple_facts;
	case SPELL_CHAOS_VOLLEY:
		return chaos_volley_facts;
	case SPELL_BLINK:
		return blink_facts;
	case SPELL_NATURES_CALLING:
		return natures_calling_facts;
	case SPELL_PLEASANTRY:
		return pleasantry_facts;
	case SPELL_CONTAIN_BEING:
		return contain_being_facts;
	case SPELL_NEGATIVE_CONCUSSION_BLAST:
		return negative_concussion_blast_facts;
	case SPELL_ACCEL_HEALING:
		return accel_healing_facts;
	case SPELL_MIELIKKI_VITALITY:
		return mielikki_vitality_facts;
	case SPELL_SPORE_BURST:
		return spore_burst_facts;
	case SPELL_SPORE_CLOUD:
		return spore_cloud_facts;
	case SPELL_LIFE_BOLT:
		return life_bolt_facts;
	case SPELL_KNOCK:
		return knock_facts;
	case SPELL_TRANQUILITY:
		return tranquility_facts;
	case SPELL_DAZZLE:
		return dazzle_facts;
	case SPELL_PASS_WITHOUT_TRACE:
		return pass_without_trace_facts;
	case SPELL_STARSHELL:
		return starshell_facts;
	case SPELL_STORNOGS_SPHERES:
		return stornogs_spheres_facts;
	case SPELL_CLOAK_OF_FEAR:
		return cloak_of_fear_facts;
	case SPELL_ACIDIMMOLATE:
		return acidimmolate_facts;
	case SPELL_IMMOLATE:
		return immolate_facts;
	case SPELL_CDOOM:
		return cdoom_facts;
	case SPELL_SENSE_FOLLOWER:
		return sense_follower_facts;
	case SPELL_PERM_INCREASE_STR:
		return perm_increase_facts;
	case SPELL_PERM_INCREASE_AGI:
		return perm_increase_facts;
	case SPELL_PERM_INCREASE_DEX:
		return perm_increase_facts;
	case SPELL_PERM_INCREASE_CON:
		return perm_increase_facts;
	case SPELL_PERM_INCREASE_LUCK:
		return perm_increase_facts;
	case SPELL_PERM_INCREASE_POW:
		return perm_increase_facts;
	case SPELL_PERM_INCREASE_INT:
		return perm_increase_facts;
	case SPELL_PERM_INCREASE_WIS:
		return perm_increase_facts;
	case SPELL_PERM_INCREASE_CHA:
		return perm_increase_facts;
	case SPELL_SOULSHIELD:
		return soulshield_facts;
	case SPELL_HOLY_AURA:
		return soulshield_facts;
	case SPELL_HOLY_DHARMA:
		return holy_dharma_facts;
	case SPELL_HOLY_SACRIFICE:
		return holy_sacrifice_facts;
	case SPELL_BATTLE_ECSTASY:
		return battle_ecstasy_facts;
	case SPELL_MASS_HEAL:
		return mass_heal_facts;
	case SPELL_TRUE_SEEING:
		return true_seeing_facts;
	case SPELL_SHADOW_VISION:
		return shadow_vision_facts;
	case SPELL_ANIMAL_VISION:
		return animal_vision_facts;
	case SPELL_TREE:
		return tree_facts;
	case SPELL_ANIMAL_GROWTH:
		return animal_growth_facts;
	case SPELL_NATURES_BLESSING:
		return natures_blessing_facts;
	case SPELL_ENLARGE:
		return enlarge_facts;
	case SPELL_ROPE_TRICK:
		return rope_trick_facts;
	case SPELL_REDUCE:
		return reduce_facts;
	case SPELL_COMMAND:
		return command_facts;
	case SPELL_CHAOS_SHIELD:
		return chaos_shield_facts;
	case SPELL_ANGELIC_COUNTENANCE:
		return vampire_facts;
	case SPELL_VAMPIRE:
		return vampire_facts;
	case SPELL_DIVINE_BLESSING:
		return divine_blessing_facts;
	case SPELL_MOONWELL:
		return moonwell_facts;
	case SPELL_SHADOW_GATE:
		return shadow_gate_facts;
	case SPELL_MOONSTONE:
		return moonstone_facts;
	case SPELL_ANIMAE_CICATRIX:
		return animae_cicatrix_facts;
	case SPELL_STIGMATA_DRACONICA:
		return stigmata_draconica_facts;
	case SPELL_DRAKESCALE_AEGIS:
		return drakescale_aegis_facts;
	case SPELL_JUDICIUM_FIDEI:
		return judicium_fidei_facts;
	case SPELL_IGNEUS_VITAE:
		return igneus_vitae_facts;
	case SPELL_SANGUINIS_IGNIS:
		return sanguinis_ignis_facts;
	case SPELL_SANCTUM_DRACONIS:
		return sanctum_draconis_facts;
	case SPELL_VIVERNAE_CONCORDIA:
		return vivernae_concordia_facts;
	case SPELL_PACTUM_SERPENTIS:
		return pactum_serpentis_facts;
	case SPELL_EDICTUM_CINERIS:
		return edictum_cineris_facts;
	case SPELL_SIGILLUM_NEGATI:
		return sigillum_negati_facts;
	case SPELL_DRACONIC_APOTHEOSIS:
		return draconic_apotheosis_facts;
	case SPELL_WARRING_ZEAL:
		return warring_zeal_facts;
	default:
		return nullptr;
	}
}

AbilityFacts innate_facts(int innate)
{
	switch (innate)
	{
	case INNATE_REFLECTION:
		return reflection_innate_facts;
	default:
		return nullptr;
	}
}
