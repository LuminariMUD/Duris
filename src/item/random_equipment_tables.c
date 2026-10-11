/****************************************************************************
 *
 *  File: random_equipment_tables.c                             Part of Duris
 *  Usage: the material, prefix, spell and slot tables random equipment is
 *         built from
 *  Copyright  1990, 1991 - see 'license.doc' for complete information.
 *  Copyright 1994 - 2008 - Duris Systems Ltd.
 * ***************************************************************************
 */

#include "core/prototypes.h"
#include "item/objmisc.h"
#include "item/random_equipment.h"
#include "magic/spells.h"

// m_number: MAT_ type; m_name: display material; m_stat: quality for affects and
// weapon dice; m_ac: armour quality; weight_mod: multiplier applied to slot weight.
// Rows are ordered by quality: the generator draws an index from the level range.
struct randomeq_material material_data[] = {
	// m_number                                       m_stat  weight_mod
	//                    m_name                           m_ac
	{ MAT_CLOTH, "cloth", 12, 1, 0.15 }, // 0
	{ MAT_SOFTWOOD, "&+ysoftwood&n", 12, 3, 0.30 },
	{ MAT_HARDWOOD, "&+yhardwood&n", 14, 4, 0.35 },
	{ MAT_BAMBOO, "&+ybamboo&n", 13, 3, 0.25 },
	{ MAT_REEDS, "&+yreed&n", 13, 3, 0.27 },
	{ MAT_BARK, "&+ybark&n", 15, 6, 0.29 }, // 5
	{ MAT_SILICON, "&+Wglass&n", 16, 2, 0.38 },
	{ MAT_RUBBER, "&+Lrubber&n", 10, 3, 0.22 },
	{ MAT_CERAMIC, "&+Lclay&n", 17, 4, 0.57 },
	{ MAT_HIDE, "&+yhide&n", 18, 5, 0.30 },
	{ MAT_LIMESTONE, "&+glimestone&n", 19, 3, 0.56 }, // 10
	{ MAT_COPPER, "&+ycopper&n", 20, 6, 2.12 },
	{ MAT_LEATHER, "&+yleather", 21, 5, 0.32 },
	{ MAT_CURED_LEATHER, "&+ycured leather&n", 25, 6, 0.35 },
	{ MAT_HEMP, "&+ghemp&n", 21, 5, 0.29 },
	{ MAT_BRONZE, "&+ybronze&n", 21, 6, 2.06 }, // 15
	{ MAT_BONE, "&+wbone&n", 22, 7, 0.35 },
	{ MAT_BRASS, "&+ybrass&n", 23, 7, 1.99 },
	{ MAT_IVORY, "&+Wivory&n", 24, 5, 0.60 },
	{ MAT_GRANITE, "&+wgranite&n", 25, 9, 0.39 },
	{ MAT_MARBLE, "&+Wma&+wr&+Lb&+wl&+We&n", 25, 7, 0.64 }, // 20
	{ MAT_STEEL, "&nsteel", 30, 12, 1.89 },
	{ MAT_IRON, "&+ciron&n", 30, 8, 1.22 },
	{ MAT_OBSIDIAN, "&+Lobsidian&n", 30, 10, 0.42 },
	{ MAT_EMERALD, "&+Gemerald&n", 34, 7, 0.72 },
	{ MAT_CRYSTAL, "&+Ccrystal&n", 36, 7, 0.70 }, // 25
	{ MAT_GEM, "&+Rgem&n", 36, 7, 0.70 },
	{ MAT_STONE, "&+Lstone&n", 38, 12, 0.75 },
	{ MAT_FLESH, "&+rflesh&n", 38, 5, 0.30 },
	{ MAT_GOLD, "&+Ygold&n", 38, 9, 4.57 },
	{ MAT_SAPPHIRE, "&+bsapphire&n", 38, 7, 1.07 }, // 30
	{ MAT_SILVER, "&+Wsilver&n", 40, 10, 2.21 },
	{ MAT_TIN, "&+Ctin&n", 25, 15, 1.72 },
	{ MAT_RUBY, "&+rruby&n", 42, 9, 1.08 },
	{ MAT_DIAMOND, "&+Wdiamond&n", 43, 14, 0.95 },
	{ MAT_ELECTRUM, "&+Welectrum&n", 44, 12, 2.23 }, // 35
	{ MAT_ADAMANTIUM, "&+madamantium&n", 50, 32, 5.00 },
	{ MAT_MITHRIL, "&+Cmithril&n", 46, 15, 0.65 },
	{ MAT_PLATINUM, "&+Wplatinum&n", 46, 13, 1.26 },
	{ MAT_GLASSTEEL, "&+cglassteel&n", 40, 18, 1.14 },
	{ MAT_REPTILESCALE, "&+greptile scale&n", 30, 15, 0.55 }, // 40
	{ MAT_CHITINOUS, "&+ychitin&n", 25, 20, 0.65 },
	{ MAT_DRAGONSCALE, "&+rdragon&+Lscale&n", 65, 25, 0.85 } // 42
};
static_assert(ARRAY_SIZE(material_data) == MAXMATERIAL, "MAXMATERIAL is the row count");

// m_number: historical serial; m_name: display adjective; m_stat: stat/dice
// multiplier; m_ac: armour multiplier; weight_mod: weight multiplier.
struct randomeq_prefix prefix_data[] = { { 1, "&+Wm&+Ya&+Wg&+Yic&+Wal&n", 1.50, 1.50, 0.80 },
					 { 2, "&+Lmaste&+brly-craf&+Lted&n", 1.47, 1.45, 0.85 },
					 { 3, "&+Lsuperior&n", 1.41, 1.25, 0.95 },
					 { 4, "&+Yun&+Liq&+Yue&n", 1.40, 1.10, 0.75 },
					 { 5, "&+Cbeautiful&n", 1.35, 1.00, 1.15 },
					 { 6, "&+Lwell-cr&+ga&+Gf&+gt&+Led", 1.31, 1.40, 0.95 },
					 { 7, "&+Cfro&+Wst-rim&+Ced&n", 1.26, 0.90, 1.15 },
					 { 8, "&+Rfl&+Ya&+Wm&+Yi&+Rng", 1.25, 0.85, 0.95 },
					 { 9, "&+Mhumming&n", 1.23, 1.50, 1.05 },
					 { 10, "&+Bicy&n", 1.18, 0.82, 1.10 },
					 { 11, "&+Cfrozen&n", 1.16, 0.94, 1.12 },
					 { 12, "&+Wfine&n", 1.15, 1.20, 0.97 },
					 { 13, "&+wgl&+Wowi&+wng&n", 1.14, 1.00, 1.02 },
					 { 14, "&+gde&+Gc&+gent&n", 1.00, 1.00, 0.99 },
					 { 15, "&+wtarnished&n", 1.09, 1.00, 1.02 },
					 { 16, "&+Yg&+Wl&+Yitt&+We&+Yri&+Wn&+Yg&n", 1.05, 1.40,
					   1.05 },
					 { 17, "&+ytwined&n", 0.75, 0.80, 1.10 },
					 { 18, "&+cdented&n", 0.68, 0.90, 0.85 },
					 { 19, "&+gpitted&n", 0.62, 0.62, 0.80 },
					 { 20, "&+wcrude&n", 0.55, 0.70, 1.15 },
					 { 21, "&+ycracked&n", 0.50, 0.50, 1.00 },
					 { 22, "&+Wexquisite&n", 1.39, 1.40, 0.88 },
					 { 23, "&+rrusty&n", 0.70, 0.70, 1.05 },
					 { 24, "&+Lspiked&n", 1.20, 1.00, 1.15 },
					 { 25, "&+Cfanged&n", 1.30, 1.00, 1.10 },
					 { 26, "&+cstylish&n", 1.15, 1.05, 1.12 },
					 { 27, "&+Ldiabolical&n", 1.40, 1.40, 1.20 },
					 { 28, "&+Rsparkling&n", 1.40, 1.35, 1.15 },
					 { 29, "&+Ytwisted&n", 1.30, 1.20, 1.08 },
					 { 30, "&+Yshi&+Wmme&+Yring&n", 1.30, 1.40, 0.95 },
					 { 31, "&+whardened&n", 1.24, 1.23, 1.03 },
					 { 32, "&+Lgha&n&+wstly&n", 0.95, 1.00, 0.95 },
					 { 33, "&+Wan&+Cgel&n&+cic&n", 1.45, 1.35, 0.777 },
					 { 34, "&+mdrow&+L-made&n", 1.25, 1.00, 0.86 },
					 { 35, "&+Chuman&+L-made&n", 0.90, 1.15, 1.00 },
					 { 36, "&+Ydwarven&+L-made&n", 0.70, 0.90, 1.12 },
					 { 37, "&+run&+Learthly&n", 1.33, 1.30, 1.21 },
					 { 38, "&+yskin&+L-wrapped", 0.60, 0.70, 1.02 },
					 { 39, "&+Wje&+Cw&+Weled&n", 1.40, 1.30, 1.05 },
					 { 40, "&+Lsinister&n", 1.20, 1.20, 1.16 },
					 { 41, "&+Wsta&n&+wtic&n", 1.10, 1.20, 1.10 },
					 { 42, "&+Cgle&n&+cam&+Wing&n", 1.22, 0.90, 1.02 },
					 { 43, "&+wwell-used&n", 0.60, 0.50, 0.98 },
					 { 44, "&+Wleg&n&+wend&+Lary&n", 1.50, 1.40, 0.78 },
					 { 45, "&+Wknight's&n", 1.00, 1.11, 1.10 },
					 { 46, "&+Lsold&n&+wier's&n", 0.80, 0.90, 1.12 },
					 { 47, "&+Rbrutal&n", 0.80, 1.40, 1.21 },
					 { 48, "&+Cbor&+Weal&n", 0.80, 0.80, 0.80 },
					 { 49, "&+rbl&+Roo&+rdy&n", 0.90, 1.20, 1.03 },
					 { 50, "&+rblood-stained&n", 0.50, 0.60, 1.02 },
					 { 51, "&+Wlight&n", 0.80, 0.90, 0.90 },
					 { 52, "&+Ldark&n", 0.80, 0.90, 1.01 },
					 { 53, "&+cfr&+Cagi&+cle&n", 1.00, 1.00, 0.89 },
					 { 54, "&+rb&+yurn&+rt&n", 1.20, 0.90, 0.98 },
					 { 55, "&+mpatched&n", 1.23, 1.20, 1.01 },
					 { 56, "&+Rmisshaped&n", 1.03, 1.00, 1.02 },
					 { 57, "&+La&+ws&+Lh&+we&+Ln&n", 1.11, 1.20, 1.01 } };
static_assert(ARRAY_SIZE(prefix_data) == MAXPREFIX + 1, "MAXPREFIX is the last row");

// s_number: level-indexed row; spell: SPELL_ id; self_only: targets the wielder;
// name: true-name suffix, empty for self-only spells.
struct random_spells spells_data[61] = {
	//  s_number                      self_only
	//     spell                         name
	{ 0, SPELL_ICE_MISSILE, FALSE, "&+Cice missiles" },
	{ 1, SPELL_CURE_LIGHT, TRUE },
	{ 2, SPELL_CURE_BLIND, TRUE },
	{ 3, SPELL_MAGIC_MISSILE, FALSE, "&+Ymagic missiles" },
	{ 4, SPELL_SHOCKING_GRASP, FALSE, "&+Bshocking" },
	{ 5, SPELL_SLOW, FALSE, "slowness" },
	{ 6, SPELL_ARMOR, TRUE },
	{ 7, SPELL_CONTINUAL_LIGHT, TRUE },
	{ 8, SPELL_DISPEL_EVIL, FALSE, "&+Wthe holy" },
	{ 9, SPELL_BLESS, TRUE },
	{ 10, SPELL_SLEEP, FALSE, "&+Lsleep" },
	{ 11, SPELL_MINOR_GLOBE, TRUE },
	{ 12, SPELL_DISPEL_GOOD, FALSE, "the unholy" },
	{ 13, SPELL_FAERIE_FOG, FALSE, "the faeries" },
	{ 14, SPELL_EGO_WHIP, FALSE, "mindwhipping" },
	{ 15, SPELL_FLESH_ARMOR, TRUE },
	{ 16, SPELL_WOLFSPEED, TRUE },
	{ 17, SPELL_HAWKVISION, TRUE },
	{ 18, SPELL_PYTHONSTING, FALSE, "&+gthe snake" },
	{ 19, SPELL_FLAMEBURST, FALSE, "&+Rflameburst" },
	{ 20, SPELL_SCORCHING_TOUCH, FALSE, "&+Rscorching" },
	{ 21, SPELL_CURE_SERIOUS, TRUE },
	{ 22, SPELL_MINOR_GLOBE, TRUE },
	{ 23, SPELL_RAY_OF_ENFEEBLEMENT, FALSE, "feebleness" },
	{ 24, SPELL_DARKNESS, TRUE },
	{ 25, SPELL_PWORD_STUN, FALSE, "&+Wstunning" },
	{ 26, SPELL_BARKSKIN, TRUE },
	{ 27, SPELL_ADRENALINE_CONTROL, TRUE },
	{ 28, SPELL_BALLISTIC_ATTACK, FALSE, "stones" },
	{ 29, SPELL_SOUL_DISTURBANCE, FALSE, "&+Lsoul crushing" },
	{ 30, SPELL_MENDING, TRUE },
	{ 31, SPELL_BEARSTRENGTH, TRUE },
	{ 32, SPELL_SHADOW_MONSTER, FALSE, "&+Lshadows" },
	{ 33, SPELL_COLD_WARD, TRUE },
	{ 34, SPELL_MOLTEN_SPRAY, FALSE, "molten rocks" },
	{ 35, SPELL_FLAMEBURST, FALSE, "&+rflamebursts" },
	{ 36, SPELL_WITHER, FALSE, "&+Lwithering" },
	{ 37, SPELL_MASS_INVIS, TRUE },
	{ 38, SPELL_ICE_STORM, FALSE, "&+cblizzards" },
	{ 39, SPELL_COLDSHIELD, TRUE },
	{ 40, SPELL_FEEBLEMIND, FALSE, "&+Lmindbreaking" },
	{ 41, SPELL_COLOR_SPRAY, FALSE, "magespray" },
	{ 42, SPELL_FIRESHIELD, TRUE },
	{ 43, SPELL_CHILL_TOUCH, FALSE, "&+bchilling" },
	{ 44, SPELL_FIREBALL, FALSE, "&+Rfireballs" },
	{ 45, SPELL_HEAL, TRUE },
	{ 46, SPELL_POISON, FALSE, "&+gvenom" },
	{ 47, SPELL_FEAR, FALSE, "&+Lfear" },
	{ 48, SPELL_FLY, TRUE },
	{ 49, SPELL_COLOR_SPRAY, FALSE, "magespray" },
	{ 50, SPELL_GLOBE, TRUE },
	{ 51, SPELL_HARM, FALSE, "harming" },
	{ 52, SPELL_ENLARGE, TRUE },
	{ 53, SPELL_REDUCE, TRUE },
	{ 54, SPELL_ELEPHANTSTRENGTH, TRUE },
	{ 55, SPELL_DETONATE, FALSE, "detonating" },
	{ 56, SPELL_CURSE, FALSE, "&+ycurse" },
	{ 57, SPELL_STONE_SKIN, TRUE },
	{ 58, SPELL_BIOFEEDBACK, TRUE },
	{ 59, SPELL_IMMOLATE, FALSE, "&+Rimmolating" },
	{ 60, SPELL_BLUR, TRUE }
};

// m_number: historical serial; m_name: display noun; m_stat and m_ac: stat/dice
// and armour multipliers; wear_bit: wear location; numb_material: material units;
// damage_type: WEAPON_ category (zero for worn items); base_weight: unscaled weight.
const struct randomeq_slots slot_data[] = {
	//   m_number                  m_stat      wear_bit                 damage_type - for weapons
	//      m_name                       m_ac                        numb_material .. base_weight
	{ 1, "&+Lring&N", 1.00, 0.00, ITEM_WEAR_FINGER, 1, 0, 1 },
	{ 2, "&+Lband&N", 1.10, 0.00, ITEM_WEAR_FINGER, 1, 0, 1 },
	{ 3, "&+Lsignet&n", 1.25, 0.00, ITEM_WEAR_FINGER, 1, 0, 1 },
	{ 4, "&+Lnecklace&N", 1.10, 0.00, ITEM_WEAR_NECK, 2, 0, 3 },
	{ 5, "&+Lcollar&N", 1.05, 1.00, ITEM_WEAR_NECK, 2, 0, 3 },
	{ 6, "&+Lchoker&N", 1.08, 0.50, ITEM_WEAR_NECK, 2, 0, 2 },
	{ 7, "&+Lchestplate&N", 1.30, 1.30, ITEM_WEAR_BODY, 3, 0, 25 },
	{ 8, "&+Lplatemail&N", 1.70, 1.70, ITEM_WEAR_BODY, 3, 0, 40 },
	{ 9, "&+Lringmail&N", 1.50, 1.45, ITEM_WEAR_BODY, 3, 0, 30 },
	{ 10, "&+Lrobe&N", 1.50, 0.70, ITEM_WEAR_BODY, 2, 0, 10 },
	{ 11, "&+Ltunic&n", 0.80, 0.50, ITEM_WEAR_BODY, 1, 0, 8 },
	{ 12, "&+Lhelmet&N", 1.05, 1.00, ITEM_WEAR_HEAD, 2, 0, 6 },
	{ 13, "&+Lhelm&N", 1.00, 1.00, ITEM_WEAR_HEAD, 2, 0, 5 },
	{ 14, "&+Lcrown&N", 1.06, 0.60, ITEM_WEAR_HEAD, 2, 0, 5 },
	{ 15, "&+Lhat&N", 1.00, 0.40, ITEM_WEAR_HEAD, 2, 0, 4 },
	{ 16, "&+Lskullcap&n", 1.20, 0.30, ITEM_WEAR_HEAD, 2, 0, 3 },
	{ 17, "&+Lleggings&N", 1.20, 1.00, ITEM_WEAR_LEGS, 2, 0, 8 },
	{ 18, "&+Lleg plates&N", 1.15, 1.10, ITEM_WEAR_LEGS, 2, 0, 10 },
	{ 19, "&+Lpants&N", 1.05, 0.80, ITEM_WEAR_LEGS, 2, 0, 7 },
	{ 20, "&+Lgreaves&n", 1.25, 1.50, ITEM_WEAR_LEGS, 3, 0, 6 },
	{ 21, "&+Lshoes&N", 1.00, 0.70, ITEM_WEAR_FEET, 2, 0, 3 },
	{ 22, "&+Lboots&N", 1.10, 1.00, ITEM_WEAR_FEET, 2, 0, 4 },
	{ 23, "&+Lmoccasins&n", 1.20, 0.70, ITEM_WEAR_FEET, 2, 0, 2 },
	{ 24, "&+Lgauntlets&N", 1.35, 1.00, ITEM_WEAR_HANDS, 2, 0, 6 },
	{ 25, "&+Ltalons&N", 1.20, 1.00, ITEM_WEAR_HANDS, 2, 0, 4 },
	{ 26, "&+Lgloves&N", 1.25, 1.10, ITEM_WEAR_HANDS, 2, 0, 3 },
	{ 27, "&+Lmitts&n", 0.90, 0.90, ITEM_WEAR_HANDS, 2, 0, 2 },
	{ 28, "&+Lsleeves&N", 1.30, 0.80, ITEM_WEAR_ARMS, 2, 0, 7 },
	{ 29, "&+Larm plates&N", 1.20, 1.20, ITEM_WEAR_ARMS, 2, 0, 9 },
	{ 30, "&+Lvambraces&n", 1.40, 1.40, ITEM_WEAR_ARMS, 3, 0, 9 },
	{ 31, "&+Lshield&N", 1.40, 1.30, ITEM_WEAR_SHIELD, 3, 0, 7 },
	{ 32, "&+Lheater shield&N", 1.30, 1.80, ITEM_WEAR_SHIELD, 3, 0, 6 },
	{ 33, "&+Lbodycloak&N", 1.42, 1.00, ITEM_WEAR_ABOUT, 3, 0, 8 },
	{ 34, "&+Lcloak&N", 1.37, 1.00, ITEM_WEAR_ABOUT, 3, 0, 6 },
	{ 35, "&+Lmantle&N", 1.40, 1.00, ITEM_WEAR_ABOUT, 3, 0, 7 },
	{ 36, "&+Lbelt&N", 1.23, 0.50, ITEM_WEAR_WAIST, 2, 0, 3 },
	{ 37, "&+Lgirth&N", 1.00, 1.00, ITEM_WEAR_WAIST, 2, 0, 4 },
	{ 38, "&+Lbracer&N", 1.00, 0.70, ITEM_WEAR_WRIST, 2, 0, 5 },
	{ 39, "&+Lbracelet&N", 1.10, 0.50, ITEM_WEAR_WRIST, 2, 0, 3 },
	{ 40, "&+Lwristguard&N", 1.00, 0.50, ITEM_WEAR_WRIST, 2, 0, 4 },
	{ 41, "&+Leyepatch&N", 1.10, 0.60, ITEM_WEAR_EYES, 2, 0, 1 },
	{ 42, "&+Lvisor&N", 1.10, 0.60, ITEM_WEAR_EYES, 2, 0, 3 },
	{ 43, "&+Lmask&N", 1.00, 1.00, ITEM_WEAR_FACE, 2, 0, 5 },
	{ 44, "&+Lveil&N", 1.05, 0.50, ITEM_WEAR_FACE, 2, 0, 2 },
	{ 45, "&+Learring&N", 1.00, 0.00, ITEM_WEAR_EARRING, 1, 0, 1 },
	{ 46, "&+Lstud&N", 0.70, 0.00, ITEM_WEAR_EARRING, 1, 0, 1 },
	{ 47, "&+Lquiver&N", 0.50, 0.00, ITEM_WEAR_QUIVER, 2, 0, 6 },
	{ 48, "&+Lbadge&N", 0.50, 0.00, ITEM_GUILD_INSIGNIA, 1, 0, 1 },
	{ 49, "&+Lsaddle&N", 0.70, 0.80, ITEM_HORSE_BODY, 1, 0, 8 },
	{ 50, "&+Ltail protector&N", 0.80, 0.20, ITEM_WEAR_TAIL, 1, 0, 3 },
	{ 51, "&+Lnose ring&N", 0.80, 0.00, ITEM_WEAR_NOSE, 1, 0, 1 },
	{ 52, "&+Lbelt buckle&N", 0.20, 0.10, ITEM_ATTACH_BELT, 1, 0, 2 },
	{ 53, "&+Lskull&N", 1.40, 0.50, ITEM_WEAR_HEAD, 2, 0, 3 },
	{ 54, "&+Lhorn&N", 1.00, 0.00, ITEM_WEAR_HORN, 1, 0, 2 },
	{ 55, "&+Lchainmail&N", 1.50, 1.30, ITEM_WEAR_BODY, 3, 0, 35 },
	{ 56, "&+Lcuirass&N", 1.30, 1.20, ITEM_WEAR_BODY, 2, 0, 20 },
	{ 57, "&+Lbreastplate&N", 1.40, 1.50, ITEM_WEAR_BODY, 2, 0, 25 },
	{ 58, "&+Lamulet&N", 1.10, 0.00, ITEM_WEAR_NECK, 2, 0, 2 },
	{ 59, "&+Lmedallion&N", 1.20, 0.00, ITEM_WEAR_NECK, 2, 0, 2 },
	{ 60, "&+Lcharm&N", 1.00, 0.00, ITEM_WEAR_NECK, 2, 0, 2 },
	{ 61, "&+Lpendant&N", 1.20, 0.00, ITEM_WEAR_NECK, 2, 0, 2 },
	{ 62, "&+Ltorque&N", 1.20, 1.00, ITEM_WEAR_NECK, 2, 0, 2 },
	{ 63, "&+Lgorget&n", 1.30, 1.50, ITEM_WEAR_NECK, 3, 0, 2 },
	{ 64, "&+Lcap&N", 1.10, 0.30, ITEM_WEAR_HEAD, 2, 0, 3 },
	{ 65, "&+Lcoif&N", 1.00, 1.10, ITEM_WEAR_HEAD, 2, 0, 5 },
	{ 66, "&+Lcirclet&N", 1.40, 0.60, ITEM_WEAR_HEAD, 2, 0, 4 },
	{ 67, "&+Ltiara&N", 1.30, 0.30, ITEM_WEAR_HEAD, 2, 0, 4 },
	{ 68, "&+Lhood&N", 1.20, 0.80, ITEM_WEAR_HEAD, 2, 0, 4 },
	{ 69, "&+Lclaws&N", 1.20, 1.00, ITEM_WEAR_HANDS, 2, 0, 4 },
	{ 70, "&+Lbuckler&N", 1.00, 1.00, ITEM_WEAR_SHIELD, 3, 0, 3 },
	{ 71, "&+Ltower shield&N", 1.10, 2.00, ITEM_WEAR_SHIELD, 3, 0, 11 },
	{ 72, "&+Lcord&n", 0.90, 0.10, ITEM_WEAR_TAIL, 2, 0, 2 },
	{ 73, "&+Lspider armor&N", 0.70, 1.20, ITEM_SPIDER_BODY, 1, 0, 6 },

	/*
    How to setting stats to random weapons works - Astansus's school for the inexperienced

    #1, The first number is just the serial number - MAX_SLOT in random_equipment.h must match the row count
    #2, Name of the weapon
    #3, Modifier to the hit/dam of the weapon
           a value = 2.5 will give up to 9/9 if you get material = dragonscale
    #4, Modifier to the dice of the weapon
           a value = 2.5 will give up to 9d9 if you get material = dragonscale
    #5, ITEM_WIELD just makes this a weapon
    #6, the number of pieces needed to craft a weapon of this type
           1-2 pieces 1handed weapon, 3+ pieces 2handed weapon
           the more pieces you add the heavier the weapon will become
    #7, type of damage the weapon has - slash, bludgeon, pierce...

    */
	{ 74, "&+Llong sword&n", 1.00, 1.00, ITEM_WIELD, 2, WEAPON_LONGSWORD, 4 },
	{ 75, "&+Ybattle axe&n", 1.10, 1.20, ITEM_WIELD, 3, WEAPON_AXE, 6 },
	{ 76, "&+Ldagger&n", 0.80, 0.80, ITEM_WIELD, 2, WEAPON_DAGGER, 1 },
	{ 77, "&+rwarhammer&n", 1.00, 1.00, ITEM_WIELD, 2, WEAPON_HAMMER, 5 },
	{ 78, "&+Lsword&n", 1.00, 1.00, ITEM_WIELD, 2, WEAPON_LONGSWORD, 3 },
	{ 79, "&+Lshort sword&n", 0.80, 0.90, ITEM_WIELD, 2, WEAPON_SHORTSWORD, 2 },
	{ 80, "&+Glance&n", 1.20, 1.20, ITEM_WIELD, 2, WEAPON_LANCE, 10 },
	{ 81, "&+Ldrusus&n", 0.80, 0.80, ITEM_WIELD, 2, WEAPON_SHORTSWORD, 3 },
	{ 82, "&+Yghurka&n", 0.80, 0.90, ITEM_WIELD, 2, WEAPON_SHORTSWORD, 2 },
	{ 83, "&+Lflail&n", 1.20, 1.10, ITEM_WIELD, 3, WEAPON_FLAIL, 5 },
	{ 84, "&+rfalchion&n", 1.00, 1.00, ITEM_WIELD, 2, WEAPON_LONGSWORD, 8 },
	{ 85, "&+Rmaul&n", 0.90, 1.40, ITEM_WIELD, 3, WEAPON_HAMMER, 8 },
	{ 86, "&+Lbroad sword&n", 1.10, 1.20, ITEM_WIELD, 2, WEAPON_LONGSWORD, 7 },
	{ 87, "&+Lgreat sword&n", 1.10, 1.20, ITEM_WIELD, 3, WEAPON_2HANDSWORD, 10 },
	{ 88, "&+Lmorningstar&n", 1.00, 1.00, ITEM_WIELD, 2, WEAPON_MACE, 6 },
	{ 89, "&+ycudgel&n", 1.00, 1.00, ITEM_WIELD, 2, WEAPON_CLUB, 3 },
	{ 90, "&+Lscythe&n", 1.00, 1.00, ITEM_WIELD, 2, WEAPON_SICKLE, 10 },
	{ 91, "&+Wscimitar&n", 1.10, 0.90, ITEM_WIELD, 2, WEAPON_LONGSWORD, 4 },
	{ 92, "&+Btrident&n", 1.00, 1.00, ITEM_WIELD, 2, WEAPON_TRIDENT, 4 },
	{ 93, "&+Lmace&n", 1.00, 1.00, ITEM_WIELD, 2, WEAPON_MACE, 6 },
	{ 94, "&+Lpronged fork&n", 1.00, 1.00, ITEM_WIELD, 2, WEAPON_TRIDENT, 4 },
	{ 95, "&+Lwhip&n", 1.10, 0.90, ITEM_WIELD, 2, WEAPON_WHIP, 2 },
	{ 96, "&+Lknife&n", 0.80, 0.80, ITEM_WIELD, 2, WEAPON_DAGGER, 1 },
	{ 97, "&+Lshillelagh&n", 1.20, 1.20, ITEM_WIELD, 3, WEAPON_CLUB, 3 },
	{ 98, "&+Lrod&n", 1.00, 1.00, ITEM_WIELD, 2, WEAPON_CLUB, 2 },
	{ 99, "&+Llongbow&n", 1.00, 1.00, ITEM_WIELD, 3, 0, 3 },
	{ 100, "&+Lstiletto&n", 1.00, 0.60, ITEM_WIELD, 2, WEAPON_DAGGER, 2 },
	{ 101, "&+Lbastard sword&n", 1.10, 1.20, ITEM_WIELD, 3, WEAPON_2HANDSWORD, 6 },
	{ 102, "&+Whand axe&n", 0.90, 1.10, ITEM_WIELD, 2, WEAPON_AXE, 3 },
	{ 103, "&+yquarterstaff&n", 1.40, 0.90, ITEM_WIELD, 2, WEAPON_CLUB, 4 },
	{ 104, "&+Lleister&n", 1.10, 1.20, ITEM_WIELD, 3, WEAPON_TRIDENT, 3 },
	{ 105, "&+Lsickle&n", 1.00, 1.00, ITEM_WIELD, 2, WEAPON_SICKLE, 2 },
	{ 106, "&+Ldirk&n", 1.00, 0.70, ITEM_WIELD, 2, WEAPON_DAGGER, 2 },
	{ 107, "&+Rswitchblade&n", 0.80, 0.80, ITEM_WIELD, 2, WEAPON_DAGGER, 1 },
	{ 108, "&+rmallet&n", 1.00, 1.00, ITEM_WIELD, 2, WEAPON_HAMMER, 6 },
	{ 109, "&+mtruncheon&n", 1.10, 1.20, ITEM_WIELD, 3, WEAPON_CLUB, 4 }
};
static_assert(ARRAY_SIZE(slot_data) == MAX_SLOT, "MAX_SLOT is the row count");
