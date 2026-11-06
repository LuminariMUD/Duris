#include "item/named_sets.h"

#include "core/prototypes.h"
#include "core/utils.h"
#include "magic/spells.h"
#include "world/db.h"

extern Skill skills[];

// Existing resolved definitions, in their historical order. Stale IDs 30 and
// 250 have no loaded zone; they remain only in the roaming spawn pool.
const named_set_definition named_sets[] = {
	{ 14, { { 3, SPELL_ARMOR }, { 3, SPELL_BLESS } } },
	{ 18, { { 5, SPELL_REGENERATION } } },
	{ 20, { { 3, SPELL_ARMOR }, { 3, SPELL_BLESS } } },
	{ 21, { { 3, SPELL_SPIRIT_ARMOR } } },
	{ 23, { { 3, SPELL_COLD_WARD }, { 4, SPELL_FIRE_WARD }, { 5, SPELL_SPIRIT_SIGHT } } },
	{ 24, { { 4, SPELL_THRYMS_ICERAZOR } } },
	{ 26, { { 3, SPELL_ARMOR }, { 3, SPELL_BLESS } } },
	{ 27, { { 3, SKILL_EPIC_STRENGTH }, { 4, SPELL_TRUE_SEEING } } },
	{ 35, { { 4, SPELL_PASS_WITHOUT_TRACE }, { 6, SPELL_VAMPIRIC_TOUCH } } },
	{ 37, { { 3, SPELL_ARMOR }, { 3, SPELL_BLESS } } },
	{ 38,
	  { { 3, SPELL_PROTECT_FROM_COLD },
	    { 3, SPELL_PROTECT_FROM_FIRE },
	    { 3, SPELL_PROTECT_FROM_LIGHTNING } } },
	{ 40, { { 6, SPELL_CONJURE_ELEMENTAL } } },
	{ 53, { { 2, SPELL_ARMOR }, { 2, SPELL_BLESS }, { 4, SPELL_INVIGORATE } } },
	{ 60, { { 3, SPELL_ARMOR }, { 3, SPELL_BLESS }, { 5, SPELL_ENDURANCE } } },
	{ 67, { { 3, SPELL_BARKSKIN }, { 5, SPELL_ENDURANCE } } },
	{ 68, { { 3, SPELL_GLOBE }, { 6, SPELL_STONE_SKIN }, { 9, SONG_DRAGONS } } },
	{ 73, { { 6, SPELL_STONE_SKIN } } },
	{ 87, { { 3, SPELL_SPIRIT_WARD }, { 5, SPELL_HASTE } } },
	{ 90, { { 3, SPELL_SOULSHIELD } } },
	{ 91, { { 2, SPELL_REGENERATION }, { 4, SPELL_FLY }, { 6, SPELL_TRUE_SEEING } } },
	{ 93, { { 2, SPELL_STRENGTH }, { 2, SPELL_AGILITY }, { 4, SPELL_MINOR_GLOBE } } },
	{ 94, { { 2, SPELL_SPIRIT_ARMOR }, { 4, SPELL_SPIRIT_WARD }, { 6, SPELL_PANTHERSPEED } } },
	{ 103, { { 2, SPELL_SPIRIT_ARMOR }, { 4, SPELL_SPIRIT_WARD } } },
	{ 106, { { 2, SPELL_SPIRIT_ARMOR }, { 4, SPELL_SPIRIT_WARD } } },
	{ 112,
	  { { 2, SPELL_ENHANCED_AGI }, { 3, SPELL_FLESH_ARMOR }, { 4, SPELL_INTELLECT_FORTRESS } } },
	{ 113,
	  { { 3, SPELL_REGENERATION }, { 5, SPELL_ENDURANCE }, { 7, SPELL_PASS_WITHOUT_TRACE } } },
	{ 124, { { 3, SPELL_INVISIBILITY }, { 6, SPELL_STONE_SKIN } } },
	{ 130, { { 6, SPELL_STONE_SKIN } } },
	{ 133, { { 6, SPELL_BATTLE_ECSTASY } } },
	{ 140, { { 2, SPELL_FAERIE_SIGHT } } },
	{ 143, { { 6, SPELL_VAMPIRIC_TOUCH } } },
	{ 151, { { 6, SPELL_STONE_SKIN } } },
	{ 152,
	  { { 2, SPELL_SPIRIT_ARMOR }, { 3, SPELL_SPIRIT_WARD }, { 4, SPELL_ELEPHANTSTRENGTH } } },
	{ 159, { { 6, SPELL_STORNOGS_SPHERES } } },
	{ 160, { { 4, SPELL_THORNSKIN }, { 6, SPELL_ENDURANCE } } },
	{ 162, { { 5, SPELL_INVISIBILITY } } },
	{ 165, { { 2, SPELL_BARKSKIN }, { 3, SPELL_BLESS }, { 6, SPELL_ENDURANCE } } },
	{ 170, { { 2, SPELL_ARMOR }, { 2, SPELL_BLESS }, { 4, SPELL_STRENGTH } } },
	{ 183, { { 4, SPELL_FIRESHIELD } } },
	{ 191, { { 4, SPELL_RAVENFLIGHT } } },
	{ 196,
	  { { 3, SPELL_GREATER_SPIRIT_SIGHT },
	    { 6, SPELL_GREATER_SPIRIT_WARD },
	    { 9, SONG_DRAGONS } } },
	{ 197, { { 7, SPELL_BIOFEEDBACK } } },
	{ 200, { { 2, SPELL_ARMOR }, { 5, SPELL_VITALITY } } },
	{ 202, { { 3, SPELL_BARKSKIN } } },
	{ 213, { { 3, SPELL_PROT_FROM_UNDEAD }, { 5, SPELL_MINOR_GLOBE } } },
	{ 215, { { 3, SPELL_BARKSKIN }, { 6, SPELL_ENDURANCE }, { 9, SPELL_PASS_WITHOUT_TRACE } } },
	{ 220, { { 6, SPELL_PANTHERSPEED }, { 6, SPELL_LIONRAGE } } },
	{ 222, { { 4, SPELL_HASTE } } },
	{ 224, { { 3, SPELL_WATERBREATH } } },
	{ 226, { { 3, SPELL_WATERBREATH } } },
	{ 229, { { 5, SPELL_STONE_SKIN } } },
	{ 230, { { 3, SPELL_GLOBE }, { 4, SPELL_FLY }, { 5, SPELL_DETECT_INVISIBLE } } },
	{ 232, { { 2, SPELL_WATERBREATH } } },
	{ 238, { { 5, SPELL_STONE_SKIN } } },
	{ 244, { { 2, SPELL_FLY } } },
	{ 254, { { 2, SPELL_FIRE_WARD } } },
	{ 257,
	  { { 3, SPELL_GREATER_SPIRIT_SIGHT },
	    { 6, SPELL_GREATER_SPIRIT_WARD },
	    { 9, SONG_DRAGONS } } },
	{ 260, { { 6, SPELL_REGENERATION } } },
	{ 261, { { 4, SPELL_REGENERATION } } },
	{ 262, { { 3, SPELL_DETECT_MAGIC }, { 3, SPELL_FARSEE }, { 5, SPELL_LEVITATE } } },
	{ 264, { { 6, SPELL_SHADOW_SHIELD } } },
	{ 266, { { 3, SPELL_NEG_ENERGY_BARRIER }, { 5, SPELL_NEG_ARMOR } } },
	{ 270, { { 3, SPELL_ENDURANCE } } },
	{ 285, { { 3, SPELL_ARMOR }, { 3, SPELL_BLESS }, { 5, SPELL_ENDURANCE } } },
	{ 289, { { 3, SPELL_ENHANCED_STR }, { 6, SPELL_STONE_SKIN } } },
	{ 294, { { 3, SPELL_ARMOR }, { 3, SPELL_DETECT_MAGIC } } },
	{ 306, { { 3, SPELL_BARKSKIN } } },
	{ 308, { { 4, SPELL_ENDURANCE } } },
	{ 311, { { 4, SPELL_FLY } } },
	{ 313, { { 6, SPELL_INVISIBILITY } } },
	{ 315,
	  { { 2, SPELL_WATERBREATH }, { 5, SPELL_INVISIBILITY }, { 8, SPELL_STORNOGS_SPHERES } } },
	{ 318, { { 3, SPELL_COLD_WARD }, { 5, SPELL_COLDSHIELD } } },
	{ 320, { { 3, SPELL_FLY }, { 6, SPELL_TRUE_SEEING }, { 8, SPELL_INFERNAL_FURY } } },
	{ 324, { { 4, SPELL_DAZZLE }, { 6, SPELL_BLUR } } },
	{ 328, { { 3, SPELL_FLESH_ARMOR }, { 5, SPELL_INTELLECT_FORTRESS } } },
	{ 333, { { 3, SPELL_PROT_FROM_UNDEAD } } },
	{ 335, { { 3, SPELL_PROT_FROM_UNDEAD } } },
	{ 342, { { 3, SPELL_STRENGTH }, { 6, SPELL_CONCEALMENT } } },
	{ 345, { { 4, SPELL_DETECT_INVISIBLE }, { 4, SPELL_INVISIBILITY } } },
	{ 360, { { 3, SPELL_ENDURANCE }, { 6, SPELL_CONCEALMENT } } },
	{ 367, { { 5, SPELL_STONE_SKIN } } },
	{ 368, { { 3, SPELL_PROT_FROM_UNDEAD }, { 5, SPELL_SOULSHIELD } } },
	{ 370, { { 3, SPELL_ENDURANCE } } },
	{ 371, { { 6, SPELL_STONE_SKIN } } },
	{ 377, { { 3, SPELL_ENDURANCE } } },
	{ 381, { { 4, SPELL_GLOBE } } },
	{ 383, { { 3, SPELL_ENDURANCE } } },
	{ 386, { { 3, SPELL_COLD_WARD }, { 5, SPELL_GLOBE } } },
	{ 387, { { 5, SPELL_BIOFEEDBACK } } },
	{ 391,
	  { { 3, SPELL_PROTECT_FROM_COLD }, { 4, SPELL_SPIRIT_ARMOR }, { 5, SPELL_ENDURANCE } } },
	{ 400, { { 3, SPELL_ARMOR }, { 3, SPELL_BLESS } } },
	{ 402, { { 3, SPELL_BARKSKIN } } },
	{ 412, { { 3, SPELL_PROT_FROM_UNDEAD }, { 4, SPELL_VITALITY }, { 5, SPELL_SOULSHIELD } } },
	{ 419, { { 3, SPELL_BARKSKIN }, { 5, SPELL_ENDURANCE }, { 7, SPELL_INVISIBILITY } } },
	{ 441, { { 6, SPELL_CHAOS_SHIELD } } },
	{ 448, { { 2, SPELL_BLESS }, { 4, SPELL_SOULSHIELD }, { 6, SPELL_VITALITY } } },
	{ 450, { { 3, SPELL_BARKSKIN }, { 6, SPELL_ENDURANCE } } },
	{ 583, { { 8, SPELL_VAMPIRE } } },
	{ 662, { { 5, SPELL_FLY } } },
	{ 671, { { 6, SPELL_VITALITY } } },
	{ 676, { { 4, SPELL_ENDURANCE } } },
	{ 700, { { 3, SPELL_ARMOR }, { 6, SPELL_ENDURANCE } } },
	{ 710, { { 6, SPELL_STONE_SKIN } } },
	{ 756, { { 3, SPELL_PROT_FROM_UNDEAD }, { 7, SPELL_STONE_SKIN } } },
	{ 758, { { 5, SPELL_FLY } } },
	{ 800, { { 3, SPELL_BLESS }, { 3, SPELL_BARKSKIN }, { 6, SPELL_ENDURANCE } } },
	{ 824, { { 6, SPELL_VITALITY } } },
	{ 857, { { 3, SPELL_SPIRIT_ARMOR }, { 4, SPELL_SPIRIT_WARD }, { 5, SPELL_ENDURANCE } } },
	{ 936, { { 3, SPELL_PROTECT_FROM_LIVING }, { 5, SPELL_HASTE } } },
	{ 955, { { 3, SPELL_ARMOR }, { 3, SPELL_BLESS }, { 5, SPELL_STRENGTH } } },
	{ 960, { { 3, SPELL_FLY }, { 6, SPELL_STONE_SKIN } } },
	{ 964, { { 6, SPELL_FLESH_ARMOR }, { 6, SPELL_INTELLECT_FORTRESS } } },
	{ 975, { { 3, SPELL_ARMOR }, { 6, SPELL_ENDURANCE } } },
	{ 987, { { 4, SPELL_PROT_FROM_UNDEAD } } },
	{ 1325, { { 3, SPELL_ARMOR }, { 5, SPELL_ENDURANCE } } },
};

const size_t named_set_count = sizeof(named_sets) / sizeof(named_sets[0]);

bool named_set_effect_supported(int effect)
{
	if (effect <= 0 || effect > MAX_AFFECT_TYPES || !skills[effect].name ||
	    !*skills[effect].name)
		return false;
	switch (effect)
	{
	case SONG_DRAGONS:
	case SKILL_EPIC_STRENGTH:
	case SKILL_EPIC_POWER:
	case SKILL_EPIC_AGILITY:
	case SKILL_EPIC_INTELLIGENCE:
	case SKILL_EPIC_DEXTERITY:
	case SKILL_EPIC_WISDOM:
	case SKILL_EPIC_CONSTITUTION:
	case SKILL_EPIC_CHARISMA:
	case SKILL_EPIC_LUCK:
		return true;
	default:
		return skills[effect].spell_pointer != nullptr;
	}
}

bool validate_named_sets()
{
	bool valid = true;
	for (size_t i = 0; i < named_set_count; ++i)
	{
		const auto &set = named_sets[i];
		if (set.zone <= 0 || real_zone(set.zone) < 0)
		{
			logit(LOG_SYS, "Named set: zone %d is not loaded", set.zone);
			valid = false;
		}
		for (size_t j = 0; j < i; ++j)
			if (named_sets[j].zone == set.zone)
			{
				logit(LOG_SYS, "Named set: duplicate zone %d", set.zone);
				valid = false;
			}
		bool has_effect = false;
		for (const auto &tier : set.proc_spells)
		{
			if (!tier[0] && !tier[1])
				continue;
			has_effect = true;
			if (tier[0] <= 0 || tier[0] > MAX_WEAR - 2 ||
			    !named_set_effect_supported(tier[1]))
			{
				logit(LOG_SYS,
				      "Named set: zone %d has invalid tier (%d pieces, effect %d)",
				      set.zone, tier[0], tier[1]);
				valid = false;
			}
		}
		if (!has_effect)
		{
			logit(LOG_SYS, "Named set: zone %d has no effects", set.zone);
			valid = false;
		}
	}
	return valid;
}
