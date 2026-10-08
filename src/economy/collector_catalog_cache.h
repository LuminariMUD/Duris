/****************************************************************************
 *
 *  File: collector_catalog_cache.h                             Part of Duris
 *  Usage: collector catalog cache interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef DURIS_COLLECTOR_CATALOG_CACHE_H
#define DURIS_COLLECTOR_CATALOG_CACHE_H

#include <string>

// Read I/O occurs on one refresh worker. Pulse and runtime publication are
// game-thread only. A failed refresh retains the last authoritative runtime.
bool collector_catalog_cache_refresh(void);
// Request a read that is guaranteed to begin after the calling authority
// commit. If an older read is already in flight, pulse schedules one more read
// after it completes instead of losing the invalidation.
void collector_catalog_cache_invalidate(void);
void collector_catalog_cache_pulse(void);
void collector_catalog_cache_shutdown(void);
bool collector_catalog_cache_ready(void);
bool collector_catalog_cache_busy(void);
std::string collector_catalog_cache_status(void);

#endif
