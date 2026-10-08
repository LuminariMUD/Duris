/****************************************************************************
 *
 *  File: maintenance_repository.h                              Part of Duris
 *  Usage: SQL maintenance repository interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef MAINTENANCE_REPOSITORY_H
#define MAINTENANCE_REPOSITORY_H

#include "persistence/maintenance_scheduler.h"

maintenance_result maintenance_repository_execute(const maintenance_request &request,
						  void *context);

#endif
