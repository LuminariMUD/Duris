/****************************************************************************
 *
 *  File: dam_mods.h                                            Part of Duris
 *  Usage: damage modifier interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

typedef struct
{
	double baseDamage;
	double addedMod; // +/- base
	double increasedMod; // first multi
	double moreMod; // second multi
} damage_profile;

typedef enum
{
	None,
	Added,
	Increased,
	More
} dam_mod_type;

typedef struct
{
	dam_mod_type type;
	double mod;
} damage_mod;

typedef void (*dam_mod_predicate)(P_char, P_char, double, int, uint, damage_mod *,
				  struct damage_messages *);

/* One macro serves every predicate lambda; which of these a body reads varies
   from predicate to predicate, so the slots are annotated rather than unnamed. */
#define MAKE_DAM_MOD_PRED()                                                                    \
	(dam_mod_predicate)[]([[maybe_unused]] P_char caster, [[maybe_unused]] P_char victim,  \
			      [[maybe_unused]] double damage, [[maybe_unused]] int damageType, \
			      [[maybe_unused]] uint flags, damage_mod *dam_mod,                \
			      [[maybe_unused]] struct damage_messages *messages)
#define NUM_SPELL_PREDICATES 36
#define NUM_RAW_PREDICATES 15
