/****************************************************************************
 *
 *  File: telemetry_activity_private.h                          Part of Duris
 *  Usage: telemetry activity bounds shared with its tests
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef DURIS_TELEMETRY_ACTIVITY_PRIVATE_H
#define DURIS_TELEMETRY_ACTIVITY_PRIVATE_H

#include "telemetry/telemetry_activity.h"

#include <limits>

/* Implementation-only bounds shared by the activity state and its tests. */
namespace telemetry_activity_private
{

inline constexpr telemetry_duration_usec CONFIGURED_WINDOW_MAX_USEC =
	TELEMETRY_ACTIVE_WINDOW_USEC_MAX_PROPOSAL;

inline bool checked_monotonic_add(telemetry_monotonic_usec start, telemetry_duration_usec duration,
				  telemetry_monotonic_usec &result) noexcept
{
	if (duration > std::numeric_limits<telemetry_monotonic_usec>::max() - start)
		return false;
	result = start + duration;
	return true;
}

inline bool monotonic_range_is_valid(telemetry_monotonic_usec start,
				     telemetry_monotonic_usec end) noexcept
{
	return end >= start;
}

} // namespace telemetry_activity_private

#endif
