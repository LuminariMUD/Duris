/****************************************************************************
 *
 *  File: specs.snogres.h                                       Part of Duris
 *  Usage: declarations for the snogres area's special procedures
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef _SPECS_SNOGRES_H_
#define _SPECS_SNOGRES_H_

int snogres_lich_shout(P_char, P_char, int, char *);
int snogres_flesh_golem(P_char, P_char, int, char *);
void event_snogres_golem_helper(P_char ch, P_char victim, P_obj obj, void *data);
int hellfire_axe(P_obj, P_char, int, char *);
int berserker_toss(P_char, P_char, int, char *);
int remo_burn(P_char, P_char, int, char *);
int illithid_whip(P_obj, P_char, int, char *);
int skull_leggings(P_obj, P_char, int, char *);
int flesh_golem_repop(P_obj, P_char, int, char *);

#endif
