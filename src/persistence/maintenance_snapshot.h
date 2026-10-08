/****************************************************************************
 *
 *  File: maintenance_snapshot.h                                Part of Duris
 *  Usage: maintenance snapshot interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef MAINTENANCE_SNAPSHOT_H
#define MAINTENANCE_SNAPSHOT_H

#include "persistence/maintenance_scheduler.h"

bool maintenance_prepare_request(maintenance_request &request, void *context);

#endif
