/****************************************************************************
 *  File: telemetry_posthog.h                                  Part of Duris
 *  Usage: worker-side PostHog encoding contract
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 ****************************************************************************/

#ifndef DURIS_TELEMETRY_POSTHOG_H
#define DURIS_TELEMETRY_POSTHOG_H

#include "telemetry/telemetry_types.h"

#include <array>
#include <string_view>

/* These functions belong to the worker, never the gameplay capture path.
 * Export schema 1 is independent of the native record schema. */
inline constexpr std::uint16_t TELEMETRY_POSTHOG_SCHEMA_VERSION = 1U;
inline constexpr std::size_t TELEMETRY_POSTHOG_IDENTITY_KEY_BYTES = 32U;
using telemetry_posthog_identity_key =
	std::array<std::uint8_t, TELEMETRY_POSTHOG_IDENTITY_KEY_BYTES>;
using telemetry_posthog_character_identity = std::array<char, 69U>;
using telemetry_posthog_scoped_identity = std::array<char, 109U>;
using telemetry_posthog_uuid = std::array<char, 37U>;
using telemetry_posthog_timestamp = std::array<char, 28U>;

/* Keys are exactly 64 hexadecimal characters, separate from the project token.
 * Invalid inputs clear output, so a caller cannot reuse an earlier identity. */
bool telemetry_posthog_parse_identity_key(std::string_view hex,
					  telemetry_posthog_identity_key &output) noexcept;
bool telemetry_posthog_character_id(const telemetry_posthog_identity_key &key,
				    telemetry_environment_id environment,
				    telemetry_season_id season, telemetry_subject_id subject,
				    telemetry_posthog_character_identity &output) noexcept;
bool telemetry_posthog_session_id(const telemetry_session_ref &session,
				  telemetry_posthog_scoped_identity &output) noexcept;
bool telemetry_posthog_run_id(telemetry_environment_id environment, telemetry_season_id season,
			      const telemetry_encounter_id &run,
			      telemetry_posthog_scoped_identity &output) noexcept;

/* Generate once when sealing, then retain the UUID with the serialized row.
 * Retrying must never invoke this function again for that row. */
bool telemetry_posthog_event_uuid(telemetry_posthog_uuid &output) noexcept;

/* UTC only, six fractional digits, years 0001-9999. Unknown/out-of-range UTC
 * must be handled explicitly by the reducer; it cannot become ingestion time. */
bool telemetry_posthog_format_timestamp(telemetry_utc_usec utc,
					telemetry_posthog_timestamp &output) noexcept;

#endif
