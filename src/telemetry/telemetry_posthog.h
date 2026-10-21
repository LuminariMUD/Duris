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
using telemetry_posthog_pet_identity = telemetry_posthog_character_identity;
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
bool telemetry_posthog_pet_id(const telemetry_posthog_identity_key &key,
			      telemetry_environment_id environment, telemetry_season_id season,
			      const telemetry_encounter_id &run, telemetry_id actor,
			      telemetry_posthog_pet_identity &output) noexcept;

/* Generate once when sealing, then retain the UUID with the serialized row.
 * Retrying must never invoke this function again for that row. */
bool telemetry_posthog_event_uuid(telemetry_posthog_uuid &output) noexcept;

/* UTC only, six fractional digits, years 0001-9999. Unknown/out-of-range UTC
 * must be handled explicitly by the reducer; it cannot become ingestion time. */
bool telemetry_posthog_format_timestamp(telemetry_utc_usec utc,
					telemetry_posthog_timestamp &output) noexcept;

inline constexpr std::size_t TELEMETRY_POSTHOG_MAX_EVENTS = 128U;
inline constexpr std::size_t TELEMETRY_POSTHOG_MAX_EVENT_BYTES = 32U * 1024U;
inline constexpr std::size_t TELEMETRY_POSTHOG_MAX_OUTPUT_BYTES = 512U * 1024U;
inline constexpr telemetry_duration_usec TELEMETRY_POSTHOG_MAX_OUTPUT_AGE_USEC = 120'000'000U;
inline constexpr telemetry_duration_usec TELEMETRY_POSTHOG_HEALTH_INTERVAL_USEC = 3'600'000'000ULL;
inline constexpr telemetry_duration_usec TELEMETRY_POSTHOG_HEALTH_COALESCE_USEC = 60'000'000U;

enum class telemetry_posthog_family : std::uint8_t
{
	session,
	character_summary,
	level_change,
	encounter_summary,
	configuration,
	health,
	count,
};

inline constexpr std::size_t TELEMETRY_POSTHOG_FAMILY_COUNT =
	static_cast<std::size_t>(telemetry_posthog_family::count);

struct telemetry_posthog_family_health
{
	std::uint64_t created = 0U;
	std::uint64_t suppressed = 0U;
	std::uint64_t expired = 0U;
	std::uint64_t http_acknowledged = 0U;
	std::uint64_t ambiguous = 0U;
};

struct telemetry_posthog_reducer_config
{
	telemetry_environment_id environment_id = 0U;
	telemetry_season_id season_id = 0U;
	telemetry_producer_id producer{};
	telemetry_posthog_identity_key identity_key{};
	std::uint32_t window_seconds = 900U;
	/* Empty for ordinary data; printable ASCII only, at most 64 characters. */
	std::array<char, 65U> test_run{};
};

struct telemetry_posthog_reducer_health
{
	std::array<std::uint64_t, 9U> consumed_by_kind{};
	std::array<std::uint64_t, 9U> refused_by_kind{};
	std::array<telemetry_posthog_family_health, TELEMETRY_POSTHOG_FAMILY_COUNT> by_family{};
	std::uint64_t invalid_health_snapshots = 0U;
	std::uint64_t invalid_records = 0U;
	std::uint64_t reduction_refusals = 0U;
	std::uint64_t input_sequence_gaps = 0U;
	std::uint64_t unsupported_records = 0U;
	std::uint64_t session_refusals = 0U;
	std::uint64_t abandoned_sessions = 0U;
	std::uint64_t configuration_refusals = 0U;
	std::uint64_t missing_configuration_rows = 0U;
	std::uint64_t counter_overflow_rows = 0U;
	std::uint64_t checkpoint_conflicts = 0U;
	std::uint64_t stale_checkpoints = 0U;
	std::uint64_t native_gaps = 0U;
	std::uint64_t native_scoped_gaps = 0U;
	std::uint64_t native_process_gaps = 0U;
	std::uint64_t native_dropped_records = 0U;
	std::uint64_t native_gap_known_usec = 0U;
	std::uint64_t unattributed_time_fragments = 0U;
	std::uint64_t xp_attribution_overflows = 0U;
	std::uint64_t run_refusals = 0U;
	std::uint64_t terminal_duplicates = 0U;
	std::uint64_t terminal_conflicts = 0U;
	std::uint64_t late_encounter_records = 0U;
	std::uint64_t incomplete_runs = 0U;
	std::uint64_t unsupported_npc_rows = 0U;
	std::uint64_t actor_attribution_overflows = 0U;
	std::uint64_t created_events = 0U;
	std::uint64_t output_suppressed = 0U;
	std::uint64_t output_expired = 0U;
	std::uint64_t serialization_failures = 0U;
	std::uint64_t clock_failures = 0U;
	std::uint64_t http_acknowledged = 0U;
	std::uint64_t ambiguous_events = 0U;
	std::uint32_t sessions = 0U;
	std::uint32_t configurations = 0U;
	std::uint32_t runs = 0U;
	std::uint32_t output_events = 0U;
	std::uint32_t output_bytes = 0U;
};

struct telemetry_posthog_output
{
	std::string_view json{};
	telemetry_monotonic_usec sealed_at = 0U;
	bool health = false;
};

enum class telemetry_posthog_sender_state : std::uint8_t
{
	disabled,
	ready,
	sending,
	backoff,
	recovery,
	permanent_failure,
	quota_blocked,
	clock_blocked,
	stopped,
};

struct telemetry_posthog_sender_health
{
	telemetry_posthog_sender_state state{};
	std::uint64_t attempted_batches = 0U;
	std::uint64_t reserved_events = 0U;
	std::uint64_t submitted_events = 0U;
	std::uint64_t submitted_bytes = 0U;
	std::uint64_t retry_attempts = 0U;
	std::uint64_t retry_exhaustions = 0U;
	std::uint64_t recovery_probes = 0U;
	std::uint64_t quota_refusals = 0U;
	std::uint64_t storage_failures = 0U;
	std::uint64_t clock_failures = 0U;
	std::uint64_t cancellations = 0U;
	std::uint64_t response_limit_failures = 0U;
	telemetry_monotonic_usec next_attempt = 0U;
	telemetry_monotonic_usec last_http_acknowledged = 0U;
	std::uint32_t http_status = 0U;
	std::uint32_t curl_error = 0U;
	std::uint32_t quota_error = 0U;
	std::uint32_t batch_events = 0U;
	std::uint32_t batch_bytes = 0U;
	std::uint32_t batch_attempts = 0U;
};

enum class telemetry_posthog_output_disposition : std::uint8_t
{
	http_acknowledged,
	suppressed,
	ambiguous,
};

/* Single worker owner. Init/reset is legal only outside an active lifecycle.
 * The runtime remains unconnected until HTTP/quota/lifecycle integration is
 * complete. Reducer operations do not perform network or disk I/O. Reset closes
 * the sender first, invalidating any borrowed output views. */
bool telemetry_posthog_reducer_init(const telemetry_posthog_reducer_config &config) noexcept;
void telemetry_posthog_reducer_reset() noexcept;
bool telemetry_posthog_consume(const telemetry_record &record, telemetry_monotonic_usec now,
			       telemetry_utc_usec utc) noexcept;
/* Call after consuming through the native admitted-tail fence. force seals
 * remaining fragments for a lifecycle deadline; it does not perform I/O. */
void telemetry_posthog_seal_through(telemetry_monotonic_usec now, telemetry_utc_usec utc,
				    bool force = false) noexcept;
/* Worker-only copied native health. Initial/hourly snapshots and coalesced
 * incidents use the same bounded output arena. True means a row was sealed,
 * never that it was sent/ingested. Native applied_records is not an HTTP ack. */
bool telemetry_posthog_observe_health(const telemetry_health_snapshot &native,
				      telemetry_monotonic_usec now,
				      telemetry_utc_usec utc) noexcept;
/* Views remain immutable while appending. Retiring/expiring/reset invalidates
 * all borrowed views; the sender must resolve its retry prefix first. */
telemetry_posthog_output telemetry_posthog_output_peek(std::size_t offset = 0U) noexcept;
bool telemetry_posthog_output_retire(std::size_t count,
				     telemetry_posthog_output_disposition disposition) noexcept;
void telemetry_posthog_output_expire(telemetry_monotonic_usec now) noexcept;
/* Worker-only value copy; runtime will publish it through its cached health. */
telemetry_posthog_reducer_health telemetry_posthog_reducer_health_copy() noexcept;

struct telemetry_outage_journal;
struct telemetry_quota_binding;
/* Existing worker only. The journal must outlive sender_close. Production host
 * is exactly https://us.i.posthog.com (an optional trailing slash is accepted).
 * Pulse advances asynchronous curl work without waiting on sockets or sleeping.
 * A nonzero deadline shortens the attempt and cancels it when reached. */
bool telemetry_posthog_sender_init(std::string_view host, std::string_view project_token,
				   const telemetry_quota_binding &binding,
				   telemetry_outage_journal *journal) noexcept;
void telemetry_posthog_sender_pulse(telemetry_monotonic_usec now, telemetry_utc_usec utc,
				    telemetry_monotonic_usec deadline = 0U,
				    bool force = false) noexcept;
void telemetry_posthog_sender_close() noexcept;
/* Failed copyover exec: resume after a bounded flush cancelled the attempt.
 * Retains counters, immutable configuration and the already-charged quota. */
void telemetry_posthog_sender_resume() noexcept;
telemetry_posthog_sender_health telemetry_posthog_sender_health_copy() noexcept;

#ifdef TELEMETRY_POSTHOG_TESTING
/* Compiled out of production. HTTPS loopback or injected DNS stall; TLS stays enabled. */
bool telemetry_posthog_sender_test_endpoint(std::uint16_t port, std::string_view ca_file,
					    bool resolve_dns = false) noexcept;
#endif

#endif
