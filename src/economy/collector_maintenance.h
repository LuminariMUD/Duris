/****************************************************************************
 *
 *  File: collector_maintenance.h                               Part of Duris
 *  Usage: collector maintenance interface and health
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef DURIS_COLLECTOR_MAINTENANCE_H
#define DURIS_COLLECTOR_MAINTENANCE_H

#include <cstdint>

struct collector_maintenance_health
{
	bool ready = false;
	bool enabled = false;
	bool reconciling = false;
	uint64_t config_revision = 0;
	uint64_t passes = 0;
	uint64_t selected = 0;
	uint64_t submitted = 0;
	uint64_t listing_busy = 0;
	uint64_t ineligible = 0;
	uint64_t submit_failures = 0;
	uint64_t completions = 0;
	uint64_t committed = 0;
	uint64_t rejected = 0;
	uint64_t publication_failures = 0;
	uint64_t recovery_refreshes = 0;
	uint64_t scan_failures = 0;
	uint64_t due_passes = 0;
	uint64_t due_leased = 0;
	uint64_t due_stale = 0;
	uint64_t collection_submissions = 0;
	uint64_t candidate_cancellations = 0;
	uint64_t activation_submissions = 0;
	uint64_t expiry_reads = 0;
	uint64_t expiry_results = 0;
	uint64_t expiry_submissions = 0;
	uint64_t pending_expiry_reads = 0;
};

// Game-thread-only bounded reconciliation. When the feature is disabled it
// pauses every available holding; when enabled it resumes every paused one.
// Candidate intake and timed transitions are layered onto the same service.
void collector_maintenance_pulse(void);
void collector_maintenance_shutdown(void);
collector_maintenance_health collector_maintenance_health_copy(void);
void collector_maintenance_reset_for_tests(void);

#endif
