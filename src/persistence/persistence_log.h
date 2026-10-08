/****************************************************************************
 *
 *  File: persistence_log.h                                     Part of Duris
 *  Usage: persistence log interface and metrics
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#pragma once

#include <cstddef>
#include <cstdint>

constexpr size_t PERSISTENCE_LOG_CAPACITY = 128;
constexpr size_t PERSISTENCE_LOG_RECORD_BYTES = 4096;

struct persistence_log_metrics
{
	uint64_t accepted, completed, rejected, file_failures, wiz_failures;
};

// Start once during boot, after chdir/fork. No game state enters the worker.
bool persistence_log_start(const char *file_path, const char *wiz_path);
bool persistence_log_submit(const char *record);
persistence_log_metrics persistence_log_snapshot();
// Lifecycle-only wait, including the record currently being written. A successful
// drain means attempts completed, not fsync durability; inspect failure counters.
bool persistence_log_drain(unsigned timeout_ms);
// Game-thread observer; implemented alongside wizlog, never called by the worker.
void persistence_log_poll();
