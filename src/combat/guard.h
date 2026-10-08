/****************************************************************************
 *
 *  File: guard.h                                               Part of Duris
 *  Usage: guard interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef __GUARD_H__
#define __GUARD_H__

#define CAN_MULTI_GUARD(ch)                            \
	(GET_SPEC(ch, CLASS_PALADIN, SPEC_CAVALIER) || \
	 GET_SPEC(ch, CLASS_ANTIPALADIN, SPEC_DEMONIC))

void do_guard(P_char ch, char *argument, int cmd);
void guard_broken(struct char_link_data *cld);
bool is_being_guarded(P_char);
P_char guard_check(P_char attacker, P_char victim);
P_char guarded_by(P_char ch);
P_char guarding(P_char ch);
P_char guarding2(P_char ch, int n);
int number_guarding(P_char ch);
void drop_one_guard(P_char ch);

#endif // __GUARD_H__
