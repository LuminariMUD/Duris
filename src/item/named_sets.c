#include "item/named_sets.h"

#include "core/prototypes.h"
#include "core/utils.h"
#include "magic/spells.h"
#include "world/db.h"

extern Skill skills[];

// Worksheet assignments; spell choices remain independent of roaming spawns.
const named_set_definition named_sets[] = {
	{ 13, { { 2, SPELL_ARMOR }, { 4, SPELL_BARKSKIN } } },
	{ 14, { { 2, SPELL_SENSE_LIFE }, { 3, SPELL_FARSEE } } },
	{ 16, { { 2, SPELL_ARMOR }, { 3, SPELL_THORNSKIN } } },
	{ 17, { { 2, SPELL_FARSEE }, { 3, SPELL_SENSE_LIFE } } },
	{ 18, { { 2, SPELL_PROTECT_FROM_FIRE }, { 3, SPELL_FIRE_WARD } } },
	{ 20, { { 2, SPELL_ARMOR }, { 3, SPELL_BARKSKIN } } },
	{ 21, { { 2, SPELL_LEVITATE }, { 3, SPELL_FARSEE } } },
	{ 22, { { 2, SPELL_ARMOR }, { 3, SPELL_SOULSHIELD } } },
	{ 23, { { 2, SPELL_LEVITATE }, { 3, SPELL_SENSE_LIFE } } },
	{ 24, { { 2, SPELL_PROTECT_FROM_FIRE }, { 4, SPELL_FIRESHIELD } } },
	{ 26, { { 2, SPELL_PROTECT_FROM_EVIL }, { 3, SPELL_PROTECT_FROM_GOOD } } },
	{ 27, { { 1, SPELL_ELEPHANTSTRENGTH }, { 2, SPELL_LIONRAGE } } },
	{ 34, { { 2, SPELL_LEVITATE }, { 3, SPELL_THORNSKIN } } },
	{ 35, { { 2, SPELL_COLDSHIELD }, { 3, SPELL_SOULSHIELD } } },
	{ 37, { { 2, SPELL_ARMOR }, { 3, SPELL_BARKSKIN } } },
	{ 38, { { 1, SPELL_PROTECT_FROM_ACID }, { 2, SPELL_PROTECT_FROM_LIGHTNING } } },
	{ 40, { { 2, SPELL_LEVITATE }, { 4, SPELL_FARSEE } } },
	{ 42, { { 2, SPELL_FARSEE }, { 3, SPELL_SENSE_LIFE } } },
	{ 44, { { 3, SPELL_HASTE }, { 5, SPELL_NEG_ENERGY_BARRIER } } },
	{ 48, { { 2, SPELL_ACCEL_HEALING }, { 3, SPELL_REGENERATION } } },
	{ 49, { { 2, SPELL_BLESS }, { 3, SPELL_VAPOR_STRIKE } } },
	{ 50, { { 2, SPELL_ARMOR }, { 3, SPELL_SOULSHIELD } } },
	{ 53, { { 3, SPELL_LEVITATE }, { 4, SPELL_PANTHERSPEED } } },
	{ 55, { { 3, SPELL_PROTECT_FROM_LIVING }, { 4, SPELL_SOULSHIELD } } },
	{ 57, { { 1, SPELL_HAWKVISION }, { 2, SPELL_ELEPHANTSTRENGTH } } },
	{ 60, { { 2, SPELL_PROTECT_FROM_COLD }, { 3, SPELL_COLD_WARD } } },
	{ 62, { { 1, SPELL_PROTECT_FROM_COLD }, { 2, SPELL_COLD_WARD } } },
	{ 63, { { 2, SPELL_LEVITATE }, { 3, SPELL_FARSEE } } },
	{ 64, { { 2, SPELL_ARMOR }, { 3, SPELL_THORNSKIN } } },
	{ 65, { { 2, SPELL_PANTHERSPEED }, { 4, SPELL_FLY } } },
	{ 66, { { 3, SPELL_LIFELUST }, { 4, SPELL_LIONRAGE } } },
	{ 67, { { 2, SPELL_BARKSKIN }, { 3, SPELL_PANTHERSPEED } } },
	{ 68, { { 3, SPELL_GLOBE }, { 6, SPELL_STORNOGS_SPHERES } } },
	{ 69, { { 2, SPELL_LEVITATE }, { 3, SPELL_FARSEE } } },
	{ 70, { { 2, SPELL_THORNSKIN }, { 3, SPELL_FARSEE } } },
	{ 71, { { 1, SPELL_PROTECT_FROM_FIRE }, { 2, SPELL_FIRE_WARD } } },
	{ 73, { { 2, SKILL_AWARENESS }, { 4, SPELL_TOWER_IRON_WILL } } },
	{ 76, { { 2, SPELL_BLESS }, { 3, SPELL_FARSEE } } },
	{ 78, { { 1, SPELL_LEVITATE }, { 3, SPELL_PANTHERSPEED } } },
	{ 81, { { 2, SPELL_PROTECT_FROM_COLD }, { 3, SPELL_COLDSHIELD } } },
	{ 84, { { 1, SPELL_PROTECT_FROM_FIRE }, { 3, SPELL_FIRESHIELD } } },
	{ 87, { { 3, SKILL_AWARENESS }, { 4, SPELL_SOULSHIELD } } },
	{ 89, { { 2, SPELL_LEVITATE }, { 3, SPELL_FARSEE } } },
	{ 90, { { 2, SPELL_FIRESHIELD }, { 4, SPELL_SOULSHIELD } } },
	{ 91, { { 2, SPELL_FARSEE }, { 4, SPELL_FLY } } },
	{ 92, { { 1, SPELL_PROTECT_FROM_COLD }, { 2, SPELL_COLD_WARD } } },
	{ 93, { { 3, SKILL_AWARENESS }, { 4, SPELL_TOWER_IRON_WILL } } },
	{ 94, { { 2, SPELL_FARSEE }, { 3, SPELL_SENSE_LIFE } } },
	{ 101, { { 2, SPELL_BLESS }, { 3, SPELL_VAPOR_STRIKE } } },
	{ 103, { { 2, SPELL_ARMOR }, { 3, SPELL_THORNSKIN } } },
	{ 106, { { 2, SPELL_HAWKVISION }, { 3, SPELL_ELEPHANTSTRENGTH } } },
	{ 107, { { 1, SPELL_ARMOR }, { 3, SPELL_THORNSKIN } } },
	{ 108, { { 2, SPELL_PROTECT_FROM_EVIL }, { 3, SPELL_PROTECT_FROM_LIVING } } },
	{ 109, { { 2, SPELL_ARMOR }, { 3, SPELL_BARKSKIN } } },
	{ 113, { { 2, SPELL_PROTECT_FROM_EVIL }, { 3, SPELL_PROTECT_FROM_GOOD } } },
	{ 114, { { 2, SPELL_ARMOR }, { 3, SPELL_THORNSKIN } } },
	{ 115, { { 4, SPELL_REGENERATION } } },
	{ 120, { { 2, SPELL_LEVITATE }, { 3, SPELL_SENSE_LIFE } } },
	{ 124, { { 4, SPELL_DETECT_INVISIBLE }, { 5, SPELL_STONE_SKIN } } },
	{ 127, { { 2, SPELL_ARMOR }, { 3, SPELL_SENSE_LIFE } } },
	{ 130, { { 2, SPELL_FARSEE }, { 4, SPELL_FLY } } },
	{ 132, { { 2, SPELL_LEVITATE }, { 4, SPELL_FARSEE } } },
	{ 133, { { 3, SPELL_REGENERATION }, { 4, SPELL_COMBAT_MIND } } },
	{ 135, { { 2, SPELL_BLESS }, { 3, SPELL_VAPOR_STRIKE } } },
	{ 137, { { 2, SPELL_PROTECT_FROM_COLD }, { 3, SPELL_COLD_WARD } } },
	{ 140, { { 2, SPELL_LEVITATE }, { 3, SPELL_SENSE_LIFE } } },
	{ 143, { { 2, SPELL_PROT_FROM_UNDEAD }, { 3, SPELL_NEG_ENERGY_BARRIER } } },
	{ 148, { { 2, SPELL_SENSE_LIFE }, { 4, SKILL_AWARENESS } } },
	{ 151, { { 2, SPELL_PROT_FROM_UNDEAD }, { 3, SPELL_NEG_ENERGY_BARRIER } } },
	{ 152, { { 2, SPELL_BLESS }, { 3, SPELL_VAPOR_STRIKE } } },
	{ 159, { { 1, SPELL_INFRAVISION }, { 3, SPELL_ULTRAVISION } } },
	{ 160, { { 2, SPELL_BLESS }, { 3, SPELL_VAPOR_STRIKE } } },
	{ 162, { { 2, SPELL_FLY }, { 3, SPELL_HASTE } } },
	{ 163, { { 2, SPELL_LEVITATE }, { 3, SPELL_FARSEE } } },
	{ 164, { { 2, SPELL_ARMOR }, { 3, SPELL_BARKSKIN } } },
	{ 165, { { 3, SPELL_LEVITATE }, { 4, SPELL_FARSEE } } },
	{ 170, { { 2, SPELL_ARMOR }, { 4, SPELL_THORNSKIN } } },
	{ 180, { { 2, SPELL_COLD_WARD }, { 3, SPELL_FIRE_WARD } } },
	{ 183, { { 2, SPELL_FIRESHIELD }, { 3, SPELL_SOULSHIELD } } },
	{ 187, { { 2, SPELL_FARSEE }, { 4, SPELL_FLY } } },
	{ 190, { { 2, SPELL_BLESS }, { 3, SPELL_VAPOR_STRIKE } } },
	{ 191, { { 1, SPELL_FARSEE }, { 3, SPELL_FLY } } },
	{ 194, { { 2, SPELL_ARMOR }, { 4, SPELL_BARKSKIN } } },
	{ 196, { { 2, SPELL_HASTE }, { 3, SKILL_SNEAK } } },
	{ 197, { { 2, SPELL_TOWER_IRON_WILL }, { 5, SPELL_DISPLACEMENT } } },
	{ 198, { { 2, SPELL_TOWER_IRON_WILL }, { 5, SPELL_DISPLACEMENT } } },
	{ 199, { { 2, SKILL_AWARENESS }, { 3, SPELL_TOWER_IRON_WILL } } },
	{ 200, { { 2, SPELL_PROTECT_FROM_COLD }, { 3, SPELL_COLDSHIELD } } },
	{ 202, { { 2, SPELL_LEVITATE }, { 3, SPELL_SENSE_LIFE } } },
	{ 204, { { 2, SPELL_PROTECT_FROM_FIRE }, { 3, SPELL_FIRE_WARD } } },
	{ 206, { { 2, SPELL_FIRE_WARD }, { 3, SPELL_COLD_WARD } } },
	{ 209, { { 2, SPELL_SENSE_LIFE }, { 3, SPELL_FARSEE } } },
	{ 213, { { 2, SPELL_LEVITATE }, { 4, SPELL_PANTHERSPEED } } },
	{ 215, { { 2, SPELL_PROTECT_FROM_COLD }, { 3, SPELL_COLDSHIELD } } },
	{ 220, { { 2, SPELL_FARSEE }, { 3, SPELL_SENSE_LIFE } } },
	{ 222, { { 2, SPELL_SENSE_LIFE }, { 3, SPELL_FARSEE } } },
	{ 224, { { 2, SPELL_PROTECT_FROM_GOOD }, { 3, SPELL_PROTECT_FROM_EVIL } } },
	{ 226, { { 2, SPELL_ARMOR }, { 4, SPELL_SOULSHIELD } } },
	{ 229, { { 2, SPELL_GLOBE_OF_DARKNESS }, { 4, SPELL_VAMPIRIC_TOUCH } } },
	{ 230, { { 1, SPELL_BARKSKIN }, { 3, SPELL_IRONWOOD } } },
	{ 232, { { 2, SPELL_WATERBREATH }, { 5, SPELL_STONE_SKIN } } },
	{ 234, { { 2, SPELL_LEVITATE }, { 4, SPELL_PANTHERSPEED } } },
	{ 236, { { 2, SPELL_HAWKVISION }, { 3, SPELL_ELEPHANTSTRENGTH } } },
	{ 238, { { 2, SPELL_BARKSKIN }, { 4, SPELL_STONE_SKIN } } },
	{ 240, { { 3, SPELL_NEG_ENERGY_BARRIER }, { 5, SPELL_HASTE } } },
	{ 241, { { 2, SPELL_HAWKVISION }, { 3, SPELL_ELEPHANTSTRENGTH } } },
	{ 244, { { 3, SPELL_HASTE }, { 5, SPELL_STONE_SKIN } } },
	{ 254, { { 2, SPELL_FIRESHIELD }, { 5, SPELL_STONE_SKIN } } },
	{ 257, { { 2, SPELL_FLY }, { 4, SPELL_AIR_FORM } } },
	{ 260, { { 2, SPELL_PROTECT_FROM_FIRE }, { 3, SPELL_FIRE_WARD } } },
	{ 261, { { 2, SPELL_FIRESHIELD }, { 3, SPELL_SOULSHIELD } } },
	{ 262, { { 2, SPELL_BARKSKIN }, { 3, SPELL_FARSEE } } },
	{ 264, { { 3, SPELL_FLY }, { 4, SPELL_HASTE } } },
	{ 266, { { 2, SPELL_NEG_ENERGY_BARRIER }, { 4, SPELL_NEG_ARMOR } } },
	{ 270, { { 2, SPELL_PROTECT_FROM_FIRE }, { 3, SPELL_FIRESHIELD } } },
	{ 281, { { 2, SPELL_FARSEE }, { 3, SPELL_SENSE_LIFE } } },
	{ 285, { { 2, SPELL_PROT_FROM_UNDEAD }, { 4, SPELL_SOULSHIELD } } },
	{ 289, { { 2, SPELL_PROTECT_FROM_COLD }, { 3, SPELL_COLDSHIELD } } },
	{ 292, { { 2, SPELL_ARMOR }, { 3, SPELL_BLESS } } },
	{ 294, { { 2, SPELL_SENSE_LIFE }, { 3, SPELL_FARSEE } } },
	{ 300, { { 3, SPELL_HASTE }, { 5, SPELL_NEG_ENERGY_BARRIER } } },
	{ 304, { { 4, SPELL_DETECT_ILLUSION }, { 5, SPELL_STONE_SKIN } } },
	{ 306, { { 2, SPELL_ARMOR }, { 3, SPELL_BARKSKIN } } },
	{ 308, { { 2, SPELL_HAWKVISION }, { 3, SPELL_ELEPHANTSTRENGTH } } },
	{ 311, { { 2, SPELL_LEVITATE }, { 3, SPELL_SENSE_LIFE } } },
	{ 313, { { 2, SPELL_FLY }, { 4, SPELL_INVISIBILITY } } },
	{ 315, { { 2, SPELL_COLDSHIELD }, { 3, SPELL_THRYMS_ICERAZOR } } },
	{ 318, { { 2, SPELL_FARSEE }, { 3, SPELL_SENSE_LIFE } } },
	{ 320, { { 4, SPELL_STONE_SKIN }, { 8, SPELL_INFERNAL_FURY } } },
	{ 324, { { 2, SPELL_PROTECT_FROM_LIVING }, { 3, SPELL_VAMPIRIC_TOUCH } } },
	{ 326, { { 2, SPELL_DETECT_ILLUSION }, { 3, SPELL_DETECT_INVISIBLE } } },
	{ 328, { { 2, SPELL_COMBAT_MIND }, { 3, SPELL_DETECT_INVISIBLE } } },
	{ 333, { { 2, SPELL_PROTECT_FROM_GOOD }, { 3, SPELL_PROTECT_FROM_EVIL } } },
	{ 335, { { 2, SPELL_PROTECT_FROM_GOOD }, { 3, SPELL_PROTECT_FROM_EVIL } } },
	{ 337, { { 2, SPELL_LEVITATE }, { 3, SPELL_SENSE_LIFE } } },
	{ 340, { { 2, SPELL_SENSE_LIFE }, { 4, SPELL_DETECT_INVISIBLE } } },
	{ 342, { { 4, SPELL_HASTE }, { 5, SPELL_FLY } } },
	{ 344, { { 2, SPELL_PROTECT_FROM_COLD }, { 3, SPELL_COLD_WARD } } },
	{ 345, { { 3, SPELL_DISPLACEMENT }, { 5, SPELL_CHAOS_SHIELD } } },
	{ 352, { { 2, SPELL_PROT_FROM_UNDEAD }, { 4, SPELL_PROTECT_FROM_LIVING } } },
	{ 355, { { 2, SPELL_FIRESHIELD }, { 5, SPELL_SOULSHIELD } } },
	{ 358, { { 2, SPELL_FARSEE }, { 4, SPELL_HASTE } } },
	{ 360, { { 2, SPELL_LEVITATE }, { 3, SPELL_FARSEE } } },
	{ 362, { { 2, SPELL_LEVITATE }, { 4, SPELL_THORNSKIN } } },
	{ 364, { { 2, SPELL_LEVITATE }, { 4, SPELL_THORNSKIN } } },
	{ 367, { { 2, SPELL_LEVITATE }, { 3, SPELL_FLY } } },
	{ 368, { { 3, SPELL_GLOBE_OF_DARKNESS }, { 7, SPELL_STONE_SKIN } } },
	{ 370, { { 2, SPELL_ARMOR }, { 3, SPELL_SOULSHIELD } } },
	{ 371, { { 4, SPELL_HASTE }, { 5, SPELL_FLY } } },
	{ 377, { { 2, SPELL_BLESS }, { 3, SPELL_VAPOR_STRIKE } } },
	{ 381, { { 3, SPELL_HASTE }, { 4, SPELL_FLY } } },
	{ 383, { { 2, SPELL_FIRESHIELD }, { 5, SPELL_NEG_ENERGY_BARRIER } } },
	{ 384, { { 3, SPELL_HASTE }, { 4, SPELL_FLY } } },
	{ 386, { { 2, SPELL_FLY }, { 4, SKILL_SNEAK } } },
	{ 387, { { 2, SPELL_LIFELUST }, { 6, SPELL_BATTLE_ECSTASY } } },
	{ 391, { { 4, SPELL_REGENERATION } } },
	{ 400, { { 3, SKILL_AWARENESS }, { 5, SPELL_FLY } } },
	{ 402, { { 2, SPELL_ARMOR }, { 3, SPELL_BARKSKIN } } },
	{ 404, { { 2, SPELL_WATERBREATH }, { 4, SPELL_HASTE } } },
	{ 407, { { 3, SPELL_FIRESHIELD }, { 4, SPELL_SOULSHIELD } } },
	{ 410, { { 2, SPELL_COMBAT_MIND }, { 5, SPELL_DISPLACEMENT } } },
	{ 412, { { 2, SPELL_PROTECT_FROM_LIVING }, { 5, SPELL_STONE_SKIN } } },
	{ 413, { { 2, SPELL_FARSEE }, { 3, SPELL_SENSE_LIFE } } },
	{ 419, { { 2, SPELL_ARMOR }, { 3, SPELL_SOULSHIELD } } },
	{ 422, { { 2, SPELL_FARSEE }, { 4, SPELL_FLY } } },
	{ 425, { { 4, SPELL_HASTE }, { 5, SPELL_FLY } } },
	{ 429, { { 1, SPELL_PROTECT_FROM_FIRE }, { 3, SPELL_FIRESHIELD } } },
	{ 430, { { 3, SPELL_FLY }, { 4, SPELL_HASTE } } },
	{ 431, { { 2, SPELL_LEVITATE }, { 5, SPELL_FLY } } },
	{ 435, { { 4, SPELL_CONJURE_ELEMENTAL }, { 7, SPELL_EARTH_FORM } } },
	{ 437, { { 2, SPELL_PROT_FROM_UNDEAD }, { 4, SPELL_NEG_ENERGY_BARRIER } } },
	{ 441, { { 5, SPELL_CHAOS_SHIELD } } },
	{ 444, { { 2, SPELL_HASTE }, { 3, SPELL_FLY } } },
	{ 448, { { 2, SPELL_ULTRAVISION }, { 4, SPELL_INVISIBILITY } } },
	{ 450, { { 3, SPELL_LEVITATE }, { 4, SPELL_PANTHERSPEED } } },
	{ 455, { { 3, SPELL_WARRING_ZEAL }, { 5, SPELL_DIVINE_FURY }, { 7, SPELL_BATTLETIDE } } },
	{ 458, { { 2, SPELL_ARMOR }, { 4, SPELL_THORNSKIN } } },
	{ 490, { { 2, SPELL_SENSE_LIFE }, { 3, SPELL_FARSEE } } },
	{ 510, { { 4, SPELL_STONE_SKIN }, { 8, SPELL_INFERNAL_FURY } } },
	{ 529, { { 2, SPELL_PROTECT_FROM_COLD }, { 3, SPELL_COLD_WARD } } },
	{ 530, { { 1, SPELL_PROTECT_FROM_FIRE }, { 3, SPELL_FIRESHIELD } } },
	{ 531, { { 2, SPELL_FARSEE }, { 3, SPELL_SENSE_LIFE } } },
	{ 532, { { 2, SPELL_ARMOR }, { 3, SPELL_BLESS } } },
	{ 536, { { 2, SPELL_LEVITATE }, { 8, SPELL_STONE_SKIN } } },
	{ 545, { { 1, SPELL_ARMOR }, { 3, SPELL_THORNSKIN } } },
	{ 546, { { 3, SPELL_SOULSHIELD }, { 4, SPELL_HASTE } } },
	{ 550, { { 3, SPELL_REGENERATION }, { 4, SPELL_COMBAT_MIND } } },
	{ 570, { { 2, SPELL_COLDSHIELD }, { 3, SPELL_SOULSHIELD } } },
	{ 575, { { 2, SPELL_HASTE }, { 3, SPELL_DETECT_INVISIBLE } } },
	{ 583, { { 3, SPELL_BIOFEEDBACK }, { 4, SPELL_INERTIAL_BARRIER } } },
	{ 588, { { 2, SPELL_DETECT_INVISIBLE }, { 3, SPELL_DETECT_ILLUSION } } },
	{ 590, { { 3, SPELL_STONE_SKIN }, { 6, SPELL_SANCTUARY } } },
	{ 600, { { 3, SPELL_PANTHERSPEED }, { 4, SPELL_FLY } } },
	{ 660, { { 3, SPELL_LEVITATE }, { 4, SPELL_SENSE_LIFE } } },
	{ 662, { { 2, SPELL_PROTECT_FROM_COLD }, { 3, SPELL_COLD_WARD } } },
	{ 664, { { 2, SPELL_FIRESHIELD }, { 3, SPELL_SOULSHIELD } } },
	{ 666, { { 2, SPELL_LEVITATE }, { 4, SPELL_FLY } } },
	{ 671, { { 2, SPELL_SENSE_LIFE }, { 3, SPELL_SOULSHIELD } } },
	{ 676, { { 2, SPELL_ARMOR }, { 3, SPELL_BARKSKIN } } },
	{ 678, { { 1, SPELL_COLD_WARD }, { 3, SPELL_COLDSHIELD } } },
	{ 690, { { 2, SPELL_ARMOR }, { 3, SPELL_BARKSKIN } } },
	{ 700, { { 3, SPELL_LEVITATE }, { 4, SPELL_PANTHERSPEED } } },
	{ 708, { { 1, SPELL_PROTECT_FROM_COLD }, { 2, SPELL_COLD_WARD } } },
	{ 709, { { 2, SPELL_HASTE }, { 4, SPELL_DAZZLE } } },
	{ 710, { { 2, SPELL_BARKSKIN }, { 6, SPELL_STONE_SKIN } } },
	{ 712, { { 2, SPELL_HASTE }, { 4, SKILL_SNEAK } } },
	{ 740, { { 2, SPELL_SENSE_LIFE }, { 3, SPELL_FARSEE } } },
	{ 750, { { 2, SPELL_HAWKVISION }, { 3, SPELL_ELEPHANTSTRENGTH } } },
	{ 752, { { 2, SPELL_PROTECT_FROM_COLD }, { 3, SPELL_COLDSHIELD } } },
	{ 755, { { 2, SPELL_PROTECT_FROM_COLD }, { 3, SPELL_COLDSHIELD } } },
	{ 756, { { 2, SPELL_FARSEE }, { 4, SPELL_FLY } } },
	{ 758, { { 2, SPELL_FARSEE }, { 3, SPELL_FLY } } },
	{ 760, { { 2, SPELL_FARSEE }, { 3, SPELL_FLY } } },
	{ 766, { { 3, SPELL_HASTE }, { 4, SPELL_FLY } } },
	{ 772, { { 2, SPELL_COLDSHIELD }, { 4, SPELL_SOULSHIELD } } },
	{ 773, { { 1, SPELL_INFRAVISION }, { 2, SPELL_ULTRAVISION } } },
	{ 775, { { 3, SPELL_FLY }, { 4, SPELL_DETECT_INVISIBLE } } },
	{ 777, { { 3, SPELL_FLY }, { 4, SPELL_DETECT_INVISIBLE } } },
	{ 780, { { 3, SPELL_HASTE }, { 4, SPELL_FLY } } },
	{ 784, { { 3, SPELL_PROTECT_FROM_LIVING }, { 4, SPELL_SOULSHIELD } } },
	{ 800, { { 2, SPELL_HAWKVISION }, { 3, SPELL_ELEPHANTSTRENGTH } } },
	{ 805, { { 1, SPELL_SLOW_POISON }, { 3, SPELL_ENDURANCE } } },
	{ 806, { { 3, SPELL_HASTE }, { 4, SPELL_FLY } } },
	{ 807, { { 2, SPELL_SENSE_LIFE }, { 3, SPELL_FARSEE } } },
	{ 808, { { 2, SPELL_BARKSKIN }, { 6, SPELL_STONE_SKIN } } },
	{ 811, { { 2, SPELL_BARKSKIN }, { 5, SPELL_STONE_SKIN } } },
	{ 814, { { 2, SPELL_BARKSKIN }, { 4, SPELL_STONE_SKIN } } },
	{ 820, { { 2, SPELL_ARMOR }, { 3, SPELL_SOULSHIELD } } },
	{ 821, { { 1, SPELL_ARMOR }, { 4, SPELL_SOULSHIELD } } },
	{ 822, { { 2, SPELL_ARMOR }, { 3, SPELL_BARKSKIN } } },
	{ 823, { { 3, SPELL_HASTE }, { 4, SPELL_FLY } } },
	{ 824, { { 2, SPELL_PROTECT_FROM_FIRE }, { 3, SPELL_FIRE_WARD } } },
	{ 825, { { 2, SPELL_BLESS }, { 3, SPELL_VAPOR_STRIKE } } },
	{ 827, { { 2, SPELL_LEVITATE }, { 3, SPELL_PANTHERSPEED } } },
	{ 828, { { 2, SPELL_LEVITATE }, { 3, SPELL_FARSEE } } },
	{ 831, { { 3, SPELL_HASTE }, { 5, SPELL_DETECT_INVISIBLE } } },
	{ 856, { { 2, SPELL_PROTECT_FROM_EVIL }, { 3, SPELL_PROT_FROM_UNDEAD } } },
	{ 857, { { 2, SPELL_PROTECT_FROM_COLD }, { 3, SPELL_COLDSHIELD } } },
	{ 875, { { 2, SPELL_HASTE }, { 3, SPELL_BLUR } } },
	{ 877, { { 3, SPELL_DAZZLE }, { 4, SPELL_GLOBE } } },
	{ 878, { { 3, SPELL_PROTECT_FROM_LIVING }, { 4, SPELL_SOULSHIELD } } },
	{ 879, { { 2, SPELL_PROT_FROM_UNDEAD }, { 4, SPELL_NEG_ENERGY_BARRIER } } },
	{ 882, { { 2, SPELL_ARMOR }, { 4, SPELL_SOULSHIELD } } },
	{ 883, { { 2, SPELL_FIRESHIELD }, { 4, SPELL_FIRE_FORM } } },
	{ 885, { { 6, SPELL_STONE_SKIN } } },
	{ 886, { { 1, SPELL_ARMOR }, { 2, SPELL_BLESS } } },
	{ 888, { { 2, SPELL_ARMOR }, { 3, SPELL_BARKSKIN } } },
	{ 889, { { 2, SPELL_ARMOR }, { 3, SPELL_THORNSKIN } } },
	{ 890, { { 3, SPELL_COLDSHIELD }, { 4, SPELL_SOULSHIELD } } },
	{ 900, { { 2, SPELL_SENSE_LIFE }, { 3, SPELL_FARSEE } } },
	{ 903, { { 1, SPELL_ARMOR }, { 3, SPELL_THORNSKIN } } },
	{ 904, { { 1, SPELL_ARMOR }, { 2, SPELL_PROTECT_FROM_COLD } } },
	{ 908, { { 2, SPELL_BLESS }, { 3, SPELL_VAPOR_STRIKE } } },
	{ 910, { { 3, SPELL_DETECT_INVISIBLE }, { 4, SPELL_GLOBE } } },
	{ 914, { { 2, SPELL_ARMOR }, { 3, SPELL_BLESS } } },
	{ 920, { { 2, SPELL_ARMOR }, { 4, SPELL_SOULSHIELD } } },
	{ 930, { { 2, SPELL_SENSE_LIFE }, { 3, SPELL_FARSEE } } },
	{ 933, { { 2, SPELL_ARMOR }, { 3, SPELL_THORNSKIN } } },
	{ 935, { { 2, SPELL_ELEPHANTSTRENGTH }, { 3, SPELL_LIONRAGE } } },
	{ 936, { { 2, SPELL_LEVITATE }, { 3, SPELL_SENSE_LIFE } } },
	{ 939, { { 2, SPELL_ARMOR }, { 3, SPELL_BLESS } } },
	{ 940, { { 2, SPELL_SOULSHIELD }, { 3, SPELL_HASTE } } },
	{ 943, { { 3, SPELL_FIRESHIELD }, { 5, SPELL_NEG_ENERGY_BARRIER } } },
	{ 947, { { 1, SPELL_PROTECT_FROM_FIRE }, { 3, SPELL_FIRESHIELD } } },
	{ 949, { { 2, SPELL_ARMOR }, { 3, SPELL_BARKSKIN } } },
	{ 950, { { 2, SPELL_VAPOR_STRIKE }, { 4, SPELL_HAWKVISION } } },
	{ 953, { { 2, SPELL_HAWKVISION }, { 3, SPELL_ELEPHANTSTRENGTH } } },
	{ 954, { { 2, SPELL_ARMOR }, { 3, SPELL_BLESS } } },
	{ 955, { { 2, SPELL_BLESS }, { 3, SPELL_VAPOR_STRIKE } } },
	{ 958, { { 2, SPELL_LEVITATE }, { 3, SPELL_SENSE_LIFE } } },
	{ 960, { { 2, SPELL_BARKSKIN }, { 5, SPELL_STONE_SKIN } } },
	{ 964, { { 3, SPELL_LEVITATE }, { 4, SPELL_SENSE_LIFE } } },
	{ 968, { { 2, SPELL_LEVITATE }, { 3, SPELL_FARSEE } } },
	{ 969, { { 1, SPELL_PROTECT_FROM_FIRE }, { 2, SPELL_FIRE_WARD } } },
	{ 970, { { 2, SPELL_FARSEE }, { 4, SPELL_HASTE } } },
	{ 974, { { 2, SPELL_LEVITATE }, { 3, SPELL_SENSE_LIFE } } },
	{ 975, { { 3, SPELL_BLESS }, { 4, SPELL_VAPOR_STRIKE } } },
	{ 979, { { 6, SPELL_STONE_SKIN } } },
	{ 985, { { 2, SPELL_SENSE_LIFE }, { 4, SKILL_AWARENESS } } },
	{ 986, { { 2, SPELL_LEVITATE }, { 4, SPELL_PANTHERSPEED } } },
	{ 987, { { 2, SPELL_FARSEE }, { 3, SPELL_SENSE_LIFE } } },
	{ 989, { { 2, SPELL_PROTECT_FROM_LIVING }, { 3, SPELL_NEG_ENERGY_BARRIER } } },
	{ 990, { { 2, SPELL_PROTECT_FROM_COLD }, { 4, SPELL_COLDSHIELD } } },
	{ 994, { { 1, SPELL_PROTECT_FROM_COLD }, { 3, SPELL_COLDSHIELD } } },
	{ 995, { { 3, SPELL_LIFELUST }, { 4, SPELL_LIONRAGE } } },
	{ 997, { { 2, SPELL_LEVITATE }, { 3, SPELL_FIRESHIELD } } },
	{ 1200, { { 2, SPELL_PANTHERSPEED }, { 3, SPELL_ENDURANCE } } },
	{ 1300, { { 2, SPELL_ENDURANCE }, { 6, SPELL_PASS_WITHOUT_TRACE } } },
	{ 1301, { { 4, SPELL_VAMPIRIC_TOUCH }, { 5, SPELL_STONE_SKIN } } },
	{ 1302, { { 4, SPELL_VAMPIRIC_TOUCH }, { 5, SPELL_STONE_SKIN } } },
	{ 1303, { { 4, SPELL_VAMPIRIC_TOUCH }, { 5, SPELL_STONE_SKIN } } },
	{ 1304, { { 4, SPELL_VAMPIRIC_TOUCH }, { 5, SPELL_STONE_SKIN } } },
	{ 1310, { { 2, SPELL_COMBAT_MIND }, { 4, SPELL_LIFELUST } } },
	{ 1312, { { 3, SPELL_GIRILALS_GRANITE_HAMMER }, { 4, SPELL_STONE_SKIN } } },
	{ 1316, { { 2, SPELL_LIGHTNINGSHIELD }, { 3, SPELL_LLIENDILS_STORMSHOCK } } },
	{ 1320, { { 2, SKILL_AWARENESS }, { 3, SPELL_TOWER_IRON_WILL } } },
	{ 1325, { { 3, SPELL_ARMOR }, { 4, SPELL_BARKSKIN } } },
	{ 1350, { { 2, SPELL_ARMOR }, { 4, SPELL_BARKSKIN } } },
	{ 1382, { { 2, SPELL_FARSEE }, { 3, SPELL_HASTE } } },
	{ 1385, { { 2, SPELL_BARKSKIN }, { 4, SKILL_AWARENESS } } },
	{ 1389, { { 3, SPELL_PROTECT_FROM_LIVING }, { 4, SPELL_NEG_ENERGY_BARRIER } } },
	{ 1390, { { 2, SPELL_FIRESHIELD }, { 3, SPELL_ILIENZES_FLAME_SWORD } } },
	{ 1398, { { 2, SPELL_FIRESHIELD }, { 5, SPELL_STONE_SKIN } } },
	{ 1424, { { 3, SPELL_CONJURE_ELEMENTAL }, { 6, SPELL_WATER_FORM } } },
	{ 3000, { { 2, SPELL_ELEPHANTSTRENGTH }, { 3, SPELL_LIONRAGE } } },
	{ 4020, { { 3, SPELL_INTELLECT_FORTRESS }, { 5, SPELL_FLY } } },
};

const size_t named_set_count = sizeof(named_sets) / sizeof(named_sets[0]);

bool named_set_effect_supported(int effect)
{
	if (effect <= 0 || effect > MAX_AFFECT_TYPES || !skills[effect].name ||
	    !*skills[effect].name)
		return false;
	switch (effect)
	{
	case SKILL_AWARENESS:
	case SKILL_SNEAK:
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
