/****************************************************************************
 *
 *  File: randobj.h                                             Part of Duris
 *  Usage: random object generation interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef _RANDOBJ_H_
#define _RANDOBJ_H_

typedef enum _randObjType
{
	mundaneObj = 0,
	magicObj,
	rareObj,
	uniqueObj,
	setObj
} randObjType;

typedef enum _randObjAffType
{
	roatAffBit1 = 0,
	roatAffBit2,
	roatAffBit3,
	roatAffBit4,
	roatAff,
	roatExtra1,
	roatExtra2
} randObjAffType;

typedef struct _randObjAff
{
	randObjAffType affType;

	unsigned int where;

	unsigned int cost;
	unsigned int incCost;
	int negGood; // boolean

	unsigned int restrictedLoc; // uses item_wear flags

	int rareOnly; // boolean

	const char *name, *name2;
} randObjAff;

#endif
