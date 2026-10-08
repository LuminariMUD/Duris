/****************************************************************************
 *
 *  File: collector_death_enrollment.h                          Part of Duris
 *  Usage: collector death enrollment interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef DURIS_COLLECTOR_DEATH_ENROLLMENT_H
#define DURIS_COLLECTOR_DEATH_ENROLLMENT_H

#include "economy/collector_storage.h"

#include <cstdint>

struct char_data;
typedef struct char_data *P_char;
struct obj_data;
typedef struct obj_data *P_obj;

// A player's death enters collector intake at corpse creation, with the feature's policy
// as it stands then. The corpse's saves carry the death until one of them is written: the
// writer records the death and the corpse's eligible items as collector candidates in the
// save's own transaction.
void collector_death_enrollment_begin(P_char character, P_obj corpse);
// The death a save of this corpse carries; false when it carries none.
bool collector_death_enrollment_for(P_obj corpse, collector_death_snapshot *death);
// A save of the corpse with this owner id was written; refused is why it could not record
// the death (zero when it did).
void collector_death_enrollment_saved(uint64_t corpse_owner_id, unsigned int refused);

void collector_death_enrollment_reset_for_tests(void);

#endif
