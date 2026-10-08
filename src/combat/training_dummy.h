/****************************************************************************
 *
 *  File: training_dummy.h                                      Part of Duris
 *  Usage: training dummy interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef DURIS_TRAINING_DUMMY_H
#define DURIS_TRAINING_DUMMY_H

#include "core/structs.h"

bool training_dummy_is(P_char ch);
bool training_dummy_target_allowed(P_char attacker, P_char victim);
bool training_dummy_spellup_target_allowed(P_char caster, P_char target);
bool training_dummy_shape_target_allowed(P_char target);
bool training_dummy_clone_target_allowed(P_char target);
bool training_dummy_disguise_target_allowed(P_char target);
bool training_dummy_capture_target_allowed(P_char target);
P_char training_dummy_item_owner(P_obj object);
void training_dummy_note_attacker(P_char dummy, P_char attacker);
void training_dummy_retarget_nonpet(P_char npc, P_char rejected);
void training_dummy_record_damage(P_char ch, int damage);
void training_dummy_bootstrap();
int training_dummy_parse_race(const char *token);
int training_dummy_parse_class(const char *token);

bool training_dummy_can_enter_room(P_char ch);
bool training_dummy_can_leave_room(P_char ch);
void training_dummy_begin_placement(P_char ch);
void training_dummy_end_placement(P_char ch);
void training_dummy_begin_removal(P_char ch);
void training_dummy_end_removal(P_char ch);

#endif
