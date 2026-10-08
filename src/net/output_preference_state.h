/****************************************************************************
 *
 *  File: output_preference_state.h                             Part of Duris
 *  Usage: output preference state type
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

#include "net/output_channel.h"
#include <cstddef>
#include <cstdint>

inline constexpr size_t OUTPUT_PREFERENCE_MAX_BYTES = 512;

// All-zero is inherited defaults with motion allowed. Plain storage is safe in
// pc_only_data, whose existing allocator does not invoke C++ constructors.
struct OutputPreferenceState
{
	// 0 inherits; 1/2/3 preserve/static/animated; 17..31 are named foreground IDs.
	uint8_t choices[(size_t)OutputChannel::Count];
	bool motion_off;
	bool operator==(const OutputPreferenceState &) const = default;
};
