/****************************************************************************
 *
 *  File: avengers.h                                            Part of Duris
 *  Usage: avenger interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef __AVENGERS_H__
#define __AVENGERS_H__

void spell_holy_sword(int, P_char, char *, int, P_char, P_obj);
void spell_divine_power(int, P_char, char *, int, P_char, P_obj);
void spell_atonement(int, P_char, char *, int, P_char, P_obj);
void do_holy_smite(P_char, char *, int);
void spell_celestial_aura(int, P_char, char *, int, P_char, P_obj);

#endif // __AVENGERS_H__
