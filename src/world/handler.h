/****************************************************************************
 *
 *  File: handler.h                                             Part of Duris
 *  Usage: prime-class item use check declaration
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

int can_prime_class_use_item(P_char, P_obj);
bool get_char_room_target(P_char viewer, P_char target, char *out, size_t capacity);

// Reserved protocol selectors never fall back to an ordinary keyword.
bool obj_name_matches(P_char viewer, P_obj object, const char *name);
