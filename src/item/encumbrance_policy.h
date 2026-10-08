/****************************************************************************
 *
 *  File: encumbrance_policy.h                                  Part of Duris
 *  Usage: encumbrance weight rule
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef ENCUMBRANCE_POLICY_H
#define ENCUMBRANCE_POLICY_H

inline int encumbrance_weight(int object_weight)
{
	return object_weight > 0 ? object_weight : 0;
}

#endif
