/****************************************************************************
 *  File: telemetry_posthog.c                                  Part of Duris
 *  Usage: worker-side PostHog encodings
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 ****************************************************************************/

#include "telemetry/telemetry_posthog.h"
#include "telemetry/telemetry_config_private.h"

#include <algorithm>
#include <bit>
#include <charconv>
#include <cstdio>
#include <cstring>
#include <ctime>
#include <limits>
#include <type_traits>

#include <cjson/cJSON.h>

#include <openssl/crypto.h>
#include <openssl/hmac.h>
#include <openssl/rand.h>

namespace
{
constexpr char HEX[] = "0123456789abcdef";
constexpr std::string_view CHARACTER_DOMAIN = "duris:posthog:character:v1";
constexpr std::string_view PET_DOMAIN = "duris:posthog:pet:v1";

bool has_key(const telemetry_posthog_identity_key &key) noexcept
{
	return std::any_of(key.begin(), key.end(), [](std::uint8_t byte) { return byte != 0U; });
}

int hex_digit(char digit) noexcept
{
	if (digit >= '0' && digit <= '9')
		return digit - '0';
	if (digit >= 'a' && digit <= 'f')
		return digit - 'a' + 10;
	if (digit >= 'A' && digit <= 'F')
		return digit - 'A' + 10;
	return -1;
}

void append_be64(std::uint8_t *output, std::uint64_t value) noexcept
{
	for (unsigned int index = 0U; index < 8U; ++index)
		output[index] = static_cast<std::uint8_t>(value >> ((7U - index) * 8U));
}

bool pseudonym(const telemetry_posthog_identity_key &key, const std::uint8_t *message,
	       std::size_t bytes, const char *prefix,
	       telemetry_posthog_character_identity &output) noexcept
{
	std::array<unsigned char, EVP_MAX_MD_SIZE> digest{};
	unsigned int length = 0U;
	if (HMAC(EVP_sha256(), key.data(), static_cast<int>(key.size()), message, bytes,
		 digest.data(), &length) == nullptr ||
	    length != 32U)
		return false;
	std::memcpy(output.data(), prefix, 4U);
	for (std::size_t index = 0U; index < length; ++index)
	{
		output[4U + index * 2U] = HEX[digest[index] >> 4U];
		output[5U + index * 2U] = HEX[digest[index] & 0x0FU];
	}
	return true;
}

bool scoped_id(const char *prefix, telemetry_environment_id environment, telemetry_season_id season,
	       const telemetry_producer_id &producer, telemetry_sequence sequence,
	       telemetry_posthog_scoped_identity &output) noexcept
{
	output.fill('\0');
	if (environment == 0U || season == 0U || !telemetry_producer_id_is_valid(producer) ||
	    sequence == 0U)
		return false;
	std::memcpy(output.data(), prefix, 3U);
	char *cursor = output.data() + 3U;
	for (const auto value :
	     { environment, season, producer.boot_id, producer.process_id, sequence })
	{
		*cursor++ = ':';
		const auto result =
			std::to_chars(cursor, output.data() + output.size() - 1U, value);
		if (result.ec != std::errc{})
		{
			output.fill('\0');
			return false;
		}
		cursor = result.ptr;
	}
	return true;
}

} // namespace

bool telemetry_posthog_parse_identity_key(std::string_view hex,
					  telemetry_posthog_identity_key &output) noexcept
{
	output.fill(0U);
	if (hex.size() != output.size() * 2U)
		return false;
	telemetry_posthog_identity_key parsed{};
	bool valid = true;
	for (std::size_t index = 0U; index < parsed.size(); ++index)
	{
		const int high = hex_digit(hex[index * 2U]);
		const int low = hex_digit(hex[index * 2U + 1U]);
		if (high < 0 || low < 0)
		{
			valid = false;
			break;
		}
		parsed[index] = static_cast<std::uint8_t>(high * 16 + low);
	}
	valid = valid && has_key(parsed);
	if (valid)
		output = parsed;
	OPENSSL_cleanse(parsed.data(), parsed.size());
	return valid;
}

bool telemetry_posthog_character_id(const telemetry_posthog_identity_key &key,
				    telemetry_environment_id environment,
				    telemetry_season_id season, telemetry_subject_id subject,
				    telemetry_posthog_character_identity &output) noexcept
{
	output.fill('\0');
	if (!has_key(key) || environment == 0U || season == 0U || subject == 0U)
		return false;
	std::array<std::uint8_t, CHARACTER_DOMAIN.size() + 24U> message{};
	std::memcpy(message.data(), CHARACTER_DOMAIN.data(), CHARACTER_DOMAIN.size());
	append_be64(message.data() + CHARACTER_DOMAIN.size(), environment);
	append_be64(message.data() + CHARACTER_DOMAIN.size() + 8U, season);
	append_be64(message.data() + CHARACTER_DOMAIN.size() + 16U, subject);
	return pseudonym(key, message.data(), message.size(), "dc1_", output);
}

bool telemetry_posthog_pet_id(const telemetry_posthog_identity_key &key,
			      telemetry_environment_id environment, telemetry_season_id season,
			      const telemetry_encounter_id &run, telemetry_id actor,
			      telemetry_posthog_pet_identity &output) noexcept
{
	output.fill('\0');
	if (!has_key(key) || environment == 0U || season == 0U ||
	    !telemetry_encounter_id_is_valid(run) || actor == 0U)
		return false;
	std::array<std::uint8_t, PET_DOMAIN.size() + 48U> message{};
	std::memcpy(message.data(), PET_DOMAIN.data(), PET_DOMAIN.size());
	std::size_t offset = PET_DOMAIN.size();
	for (const auto value : { environment, season, run.producer.boot_id,
				  run.producer.process_id, run.sequence, actor })
	{
		append_be64(message.data() + offset, value);
		offset += 8U;
	}
	return pseudonym(key, message.data(), message.size(), "dp1_", output);
}

bool telemetry_posthog_session_id(const telemetry_session_ref &session,
				  telemetry_posthog_scoped_identity &output) noexcept
{
	output.fill('\0');
	if (!telemetry_session_ref_is_valid(session))
		return false;
	return scoped_id("ds1", session.environment_id, session.season_id, session.id.producer,
			 session.id.session_seq, output);
}

bool telemetry_posthog_run_id(telemetry_environment_id environment, telemetry_season_id season,
			      const telemetry_encounter_id &run,
			      telemetry_posthog_scoped_identity &output) noexcept
{
	return scoped_id("dr1", environment, season, run.producer, run.sequence, output);
}

bool telemetry_posthog_event_uuid(telemetry_posthog_uuid &output) noexcept
{
	output.fill('\0');
	std::array<unsigned char, 16U> bytes{};
	if (RAND_bytes(bytes.data(), static_cast<int>(bytes.size())) != 1)
		return false;
	bytes[6] = static_cast<unsigned char>((bytes[6] & 0x0FU) | 0x40U);
	bytes[8] = static_cast<unsigned char>((bytes[8] & 0x3FU) | 0x80U);
	std::size_t offset = 0U;
	for (std::size_t index = 0U; index < bytes.size(); ++index)
	{
		if (index == 4U || index == 6U || index == 8U || index == 10U)
			output[offset++] = '-';
		output[offset++] = HEX[bytes[index] >> 4U];
		output[offset++] = HEX[bytes[index] & 0x0FU];
	}
	return true;
}

bool telemetry_posthog_format_timestamp(telemetry_utc_usec utc,
					telemetry_posthog_timestamp &output) noexcept
{
	output.fill('\0');
	if (utc < -62'135'596'800'000'000LL || utc > 253'402'300'799'999'999LL)
		return false;
	std::int64_t seconds = utc / 1'000'000;
	std::int64_t fractional = utc % 1'000'000;
	if (fractional < 0)
	{
		--seconds;
		fractional += 1'000'000;
	}
	const auto time = static_cast<std::time_t>(seconds);
	if (static_cast<std::int64_t>(time) != seconds)
		return false;
	std::tm calendar{};
	if (gmtime_r(&time, &calendar) == nullptr)
		return false;
	char formatted[128]{};
	const int size = std::snprintf(formatted, sizeof(formatted),
				       "%04d-%02d-%02dT%02d:%02d:%02d.%06uZ",
				       calendar.tm_year + 1900, calendar.tm_mon + 1,
				       calendar.tm_mday, calendar.tm_hour, calendar.tm_min,
				       calendar.tm_sec, static_cast<unsigned int>(fractional));
	if (size != static_cast<int>(output.size() - 1U))
		return false;
	std::memcpy(output.data(), formatted, output.size());
	return true;
}

namespace
{
constexpr std::size_t SESSION_LIMIT = 256U;
constexpr std::size_t BUCKET_LIMIT = 32U;
constexpr std::size_t CONFIGURATION_LIMIT = 64U;
constexpr std::size_t RUN_LIMIT = 128U;
constexpr std::size_t ACTOR_LIMIT = TELEMETRY_COMBAT_SUMMARY_MAX_PARTICIPANTS;
/* A lost exit must not occupy a reducer slot forever. The capture cadence
	 * is bounded to one hour; allow another two minutes of native queue age. */
constexpr telemetry_duration_usec MAX_SESSION_SILENCE_USEC = 3'720'000'000ULL;
/* Leave room for the later streaming batch's token/framing without retaining
 * a second copy of its events. The event arena includes terminating NULs. */
constexpr std::size_t BATCH_FRAMING_RESERVE = 512U;
constexpr telemetry_utc_usec UTC_MIN = -62'135'596'800'000'000LL;
constexpr telemetry_utc_usec UTC_MAX = 253'402'300'799'999'999LL;
constexpr std::uint32_t COVERAGE_GAP = 1U << 0;
constexpr std::uint32_t COVERAGE_TIME = 1U << 1;
constexpr std::uint32_t COVERAGE_XP = 1U << 2;
constexpr std::uint32_t COVERAGE_CONFIG = 1U << 3;
constexpr std::uint32_t COVERAGE_OVERFLOW = 1U << 4;
constexpr std::uint32_t COVERAGE_TAIL = 1U << 5;
constexpr std::uint32_t COVERAGE_CLOCK = 1U << 6;
constexpr std::uint32_t COVERAGE_LATE = 1U << 7;
constexpr std::uint32_t COVERAGE_DIMENSIONS = 1U << 8;
constexpr std::uint32_t COVERAGE_TERMINAL = 1U << 9;
constexpr std::uint32_t COVERAGE_ACTOR = 1U << 10;
constexpr std::uint32_t COVERAGE_COMBAT = 1U << 11;
constexpr std::uint32_t COVERAGE_OUTPUT = 1U << 12;

template <typename Number> struct metric
{
	Number value = 0;
	bool overflow = false;

	void add(Number delta) noexcept
	{
		if (overflow)
			return;
		bool exceeds = false;
		if constexpr (std::is_signed_v<Number>)
			exceeds =
				(delta > 0 && value > std::numeric_limits<Number>::max() - delta) ||
				(delta < 0 && value < std::numeric_limits<Number>::min() - delta);
		else
			exceeds = value > std::numeric_limits<Number>::max() - delta;
		if (exceeds)
			overflow = true;
		else
			value += delta;
	}
};

void add_count(std::uint64_t &value, std::uint64_t delta = 1U) noexcept
{
	value = delta > std::numeric_limits<std::uint64_t>::max() - value ?
			std::numeric_limits<std::uint64_t>::max() :
			value + delta;
}

struct time_totals
{
	/* Native category indices: unknown, idle, active, linkdead. */
	std::array<metric<std::uint64_t>, 4U> category{};
};

struct xp_totals
{
	metric<std::int64_t> requested{};
	metric<std::int64_t> computed{};
	metric<std::int64_t> applied{};
	metric<std::uint64_t> attempts{};
	metric<std::uint64_t> zero_applied{};
};

struct time_bucket
{
	telemetry_dimensions dimensions{};
	telemetry_activity_context context{};
	telemetry_context_quality context_quality{};
	time_totals totals{};
};

struct xp_bucket
{
	telemetry_dimensions dimensions{};
	telemetry_progression_source source{};
	telemetry_progression_reason reason{};
	telemetry_progression_observation_status observation{};
	std::uint32_t modifiers = 0U;
	xp_totals totals{};
};

struct fragment
{
	bool used = false;
	telemetry_utc_usec window = TELEMETRY_UTC_UNKNOWN;
	telemetry_utc_usec first = TELEMETRY_UTC_UNKNOWN;
	telemetry_utc_usec last = TELEMETRY_UTC_UNKNOWN;
	telemetry_monotonic_usec created_at = 0U;
	telemetry_config_id config = 0U;
	std::uint32_t classifier = 0U;
	std::uint32_t policy = 0U;
	telemetry_dimensions dimensions{};
	telemetry_quality_mask quality = 0U;
	std::uint32_t coverage = 0U;
	std::uint64_t interval_observations = 0U;
	std::uint16_t xp_level = 0U;
	time_totals time{};
	xp_totals xp{};
	std::size_t time_count = 0U;
	std::size_t xp_count = 0U;
	std::array<time_bucket, BUCKET_LIMIT> time_buckets{};
	std::array<xp_bucket, BUCKET_LIMIT> xp_buckets{};
	time_totals unattributed_time{};
	xp_totals unattributed_xp{};
};

struct character_state
{
	bool used = false;
	bool logical_entry_observed = false;
	telemetry_session_ref session{};
	telemetry_monotonic_usec last_seen = 0U;
	std::array<fragment, 2U> fragments{};
	telemetry_utc_usec sealed_through = TELEMETRY_UTC_UNKNOWN;
	time_totals observed{};
	time_totals observed_at_checkpoint{};
	telemetry_monotonic_usec observed_through = 0U;
	bool has_checkpoint = false;
	bool checkpoint_comparable = false;
	telemetry_session_checkpoint_payload checkpoint{};
	std::uint32_t coverage = 0U;
};

struct output_entry
{
	std::size_t offset = 0U;
	std::size_t bytes = 0U;
	telemetry_monotonic_usec sealed_at = 0U;
};

struct combat_totals
{
	std::array<metric<std::uint64_t>, 10U> values{};
};

struct encounter_actor
{
	telemetry_combat_actor_kind kind = telemetry_combat_actor_kind::unknown;
	telemetry_id id = 0U;
	telemetry_subject_id owner = 0U;
	bool has_participation = false;
	bool participation_terminal = false;
	bool has_combat = false;
	telemetry_duration_usec participant_usec = 0U;
	telemetry_combat_summary_payload combat{};
};

struct encounter_state
{
	bool used = false;
	bool started = false;
	bool closed = false;
	bool terminal = false;
	bool has_combat = false;
	bool emitting = false;
	telemetry_encounter_id id{};
	telemetry_encounter_source source{};
	telemetry_encounter_mode mode{};
	telemetry_encounter_outcome outcome{};
	telemetry_monotonic_usec start = 0U;
	telemetry_monotonic_usec end = 0U;
	telemetry_monotonic_usec terminal_at = 0U;
	telemetry_utc_usec start_utc = TELEMETRY_UTC_UNKNOWN;
	telemetry_utc_usec end_utc = TELEMETRY_UTC_UNKNOWN;
	telemetry_quality_mask quality = 0U;
	std::uint32_t coverage = COVERAGE_DIMENSIONS;
	std::uint16_t roster_expected = 0U;
	std::uint16_t roster_count = 0U;
	std::uint16_t credit_count = 0U;
	std::uint16_t combat_expected = 0U;
	std::uint16_t dropped_actor_attempts = 0U;
	std::uint16_t unique_players = 0U;
	std::uint16_t npc_count = 0U;
	std::uint16_t actor_count = 0U;
	std::uint16_t output_cursor = 0U;
	std::uint16_t unattributed_players = 0U;
	std::uint16_t unattributed_pets = 0U;
	std::uint64_t combat_revisions = 0U;
	std::array<telemetry_subject_id, ACTOR_LIMIT> roster_subjects{};
	std::array<encounter_actor, ACTOR_LIMIT> actors{};
	metric<std::uint64_t> unattributed_roster_usec{};
	combat_totals unattributed_player_combat{};
	combat_totals unattributed_pet_combat{};
};

struct reducer_state
{
	bool initialized = false;
	telemetry_posthog_reducer_config config{};
	telemetry_posthog_reducer_health health{};
	telemetry_record_sequence last_sequence = 0U;
	std::array<character_state, SESSION_LIMIT> characters{};
	std::array<telemetry_config_snapshot, CONFIGURATION_LIMIT> configurations{};
	std::array<encounter_state, RUN_LIMIT> encounters{};
	/* Exact terminal tombstones plus a conservative evicted prefix. Runs
		 * never cross a producer lifecycle; native copyover closes them first. */
	std::array<telemetry_sequence, RUN_LIMIT> retired_runs{};
	std::size_t retired_cursor = 0U;
	telemetry_sequence retired_through = 0U;
	std::array<output_entry, TELEMETRY_POSTHOG_MAX_EVENTS> output{};
	std::array<char, TELEMETRY_POSTHOG_MAX_OUTPUT_BYTES> bytes{};
};

reducer_state REDUCER{};

bool same_producer(const telemetry_producer_id &a, const telemetry_producer_id &b) noexcept
{
	return a.boot_id == b.boot_id && a.process_id == b.process_id;
}

bool same_session_id(const telemetry_session_id &a, const telemetry_session_id &b) noexcept
{
	return same_producer(a.producer, b.producer) && a.session_seq == b.session_seq;
}

bool same_character_dimensions(const telemetry_dimensions &a,
			       const telemetry_dimensions &b) noexcept
{
	return a.level_band == b.level_band && a.class_id == b.class_id && a.race_id == b.race_id &&
	       a.faction_id == b.faction_id;
}

bool character_dimensions_known(const telemetry_dimensions &value) noexcept
{
	return value.level_band != 0U && value.class_id != 0U && value.race_id != 0U &&
	       value.faction_id != 0U;
}

bool scope_matches(telemetry_environment_id environment, telemetry_season_id season) noexcept
{
	return environment == REDUCER.config.environment_id && season == REDUCER.config.season_id;
}

bool utc_valid(telemetry_utc_usec value) noexcept
{
	return value >= UTC_MIN && value <= UTC_MAX;
}

telemetry_utc_usec window_for(telemetry_utc_usec utc) noexcept
{
	if (!utc_valid(utc))
		return TELEMETRY_UTC_UNKNOWN;
	const auto span =
		static_cast<telemetry_utc_usec>(REDUCER.config.window_seconds) * 1'000'000;
	const auto remainder = utc % span;
	return utc - remainder - (remainder < 0 ? span : 0);
}

const telemetry_config_snapshot *find_configuration(telemetry_config_id id) noexcept
{
	for (std::size_t index = 0U; index < REDUCER.health.configurations; ++index)
		if (REDUCER.configurations[index].config_id == id)
			return &REDUCER.configurations[index];
	return nullptr;
}

struct posthog_row
{
	cJSON *root = cJSON_CreateObject();
	cJSON *properties = root == nullptr ? nullptr : cJSON_AddObjectToObject(root, "properties");
	bool valid = properties != nullptr;

	posthog_row() = default;
	posthog_row(const posthog_row &) = delete;
	posthog_row &operator=(const posthog_row &) = delete;
	~posthog_row() { cJSON_Delete(root); }

	cJSON *put(cJSON *object, const char *name, cJSON *item) noexcept
	{
		if (item == nullptr || object == nullptr ||
		    !cJSON_AddItemToObject(object, name, item))
		{
			cJSON_Delete(item);
			valid = false;
			return nullptr;
		}
		return item;
	}

	void text(cJSON *object, const char *name, const char *value) noexcept
	{
		put(object, name,
		    value == nullptr ? cJSON_CreateNull() : cJSON_CreateString(value));
	}

	void replace_text(const char *name, const char *value) noexcept
	{
		auto *item = value == nullptr ? cJSON_CreateNull() : cJSON_CreateString(value);
		if (item == nullptr || properties == nullptr ||
		    !cJSON_ReplaceItemInObjectCaseSensitive(properties, name, item))
		{
			cJSON_Delete(item);
			valid = false;
		}
	}

	void number(cJSON *object, const char *name, std::uint32_t value,
		    bool known = true) noexcept
	{
		put(object, name, known ? cJSON_CreateNumber(value) : cJSON_CreateNull());
	}

	template <typename Number>
	void integer(cJSON *object, const char *name, Number value, bool known = true) noexcept
	{
		if (!known)
		{
			put(object, name, cJSON_CreateNull());
			return;
		}
		char encoded[22]{};
		const auto result = std::to_chars(encoded, encoded + sizeof(encoded) - 1U, value);
		if (result.ec != std::errc{})
			valid = false;
		else
			text(object, name, encoded);
	}

	template <typename Number>
	void value(cJSON *object, const char *name, const metric<Number> &total) noexcept
	{
		integer(object, name, total.value, !total.overflow);
	}

	cJSON *object(cJSON *parent, const char *name) noexcept
	{
		return put(parent, name, cJSON_CreateObject());
	}

	cJSON *array(const char *name) noexcept
	{
		return put(properties, name, cJSON_CreateArray());
	}

	cJSON *element(cJSON *array_value) noexcept
	{
		auto *item = cJSON_CreateObject();
		if (item == nullptr || array_value == nullptr ||
		    !cJSON_AddItemToArray(array_value, item))
		{
			cJSON_Delete(item);
			valid = false;
			return nullptr;
		}
		return item;
	}
};

void dimensions_json(posthog_row &row, cJSON *object, const telemetry_dimensions *dimensions,
		     bool allocation = false) noexcept
{
	const telemetry_dimensions unknown{};
	const auto &value = dimensions == nullptr ? unknown : *dimensions;
	row.number(object, "class_id", value.class_id, value.class_id != 0U);
	row.number(object, "race_id", value.race_id, value.race_id != 0U);
	row.number(object, "faction_id", value.faction_id, value.faction_id != 0U);
	row.number(object, "level_band", value.level_band, value.level_band != 0U);
	if (allocation)
	{
		row.number(object, "zone", static_cast<std::uint32_t>(value.zone_vnum),
			   dimensions != nullptr && value.zone_vnum >= 0);
		row.number(object, "group_size", value.group_size, value.group_size != 0U);
	}
}

std::array<metric<std::uint64_t>, 6U> duration_values(const time_totals &totals) noexcept
{
	auto connected = totals.category[0];
	connected.add(totals.category[1].value);
	connected.add(totals.category[2].value);
	connected.overflow |= totals.category[1].overflow || totals.category[2].overflow;
	auto resident = connected;
	resident.add(totals.category[3].value);
	resident.overflow |= totals.category[3].overflow;
	return { connected,	     totals.category[2], totals.category[1],
		 totals.category[0], resident,		 totals.category[3] };
}

bool time_overflow(const time_totals &totals) noexcept
{
	const auto values = duration_values(totals);
	return std::any_of(values.begin(), values.end(),
			   [](const auto &value) { return value.overflow; });
}

bool xp_overflow(const xp_totals &totals) noexcept
{
	return totals.requested.overflow || totals.computed.overflow || totals.applied.overflow ||
	       totals.attempts.overflow || totals.zero_applied.overflow;
}

void time_json(posthog_row &row, cJSON *object, const time_totals &totals) noexcept
{
	constexpr const char *names[] = { "connected_usec", "active_usec",   "idle_usec",
					  "unknown_usec",   "resident_usec", "linkdead_usec" };
	const auto values = duration_values(totals);
	for (std::size_t index = 0U; index < values.size(); ++index)
		row.value(object, names[index], values[index]);
}

void xp_json(posthog_row &row, cJSON *object, const xp_totals &totals) noexcept
{
	row.value(object, "requested_xp", totals.requested);
	row.value(object, "computed_xp", totals.computed);
	row.value(object, "applied_xp", totals.applied);
	row.value(object, "attempts", totals.attempts);
	row.value(object, "zero_applied", totals.zero_applied);
}

void coverage_json(posthog_row &row, std::uint32_t coverage) noexcept
{
	constexpr const char *names[] = { "native_gap",
					  "unattributed_time",
					  "unattributed_xp",
					  "missing_configuration",
					  "counter_overflow",
					  "unclosed_tail",
					  "occurrence_utc_unknown",
					  "late_fragment",
					  "historical_dimensions_unavailable",
					  "incomplete_terminal",
					  "unsupported_actor",
					  "unattributed_combat",
					  "output_suppressed" };
	auto *array = row.array("duris_coverage");
	for (std::size_t index = 0U; index < std::size(names); ++index)
		if ((coverage & (1U << index)) != 0U)
		{
			auto *name = cJSON_CreateString(names[index]);
			if (name == nullptr || array == nullptr ||
			    !cJSON_AddItemToArray(array, name))
			{
				cJSON_Delete(name);
				row.valid = false;
			}
		}
}

std::uint32_t native_coverage(telemetry_quality_mask quality) noexcept
{
	std::uint32_t coverage = 0U;
	if ((quality & (TELEMETRY_QUALITY_SEQUENCE_GAP | TELEMETRY_QUALITY_QUEUE_DROP)) != 0U)
		coverage |= COVERAGE_GAP;
	if ((quality & TELEMETRY_QUALITY_UNCLOSED_TAIL) != 0U)
		coverage |= COVERAGE_TAIL;
	if ((quality & TELEMETRY_QUALITY_LATE) != 0U)
		coverage |= COVERAGE_LATE;
	if ((quality & TELEMETRY_QUALITY_DIMENSION_UNKNOWN) != 0U)
		coverage |= COVERAGE_DIMENSIONS;
	return coverage;
}

void common_json(posthog_row &row, const char *event, const telemetry_session_ref *session,
		 telemetry_config_id config, std::uint32_t classifier, std::uint32_t policy,
		 const telemetry_dimensions *dimensions, telemetry_quality_mask quality,
		 std::uint32_t coverage, telemetry_utc_usec first, telemetry_utc_usec last,
		 telemetry_utc_usec sealing_utc) noexcept
{
	telemetry_posthog_uuid uuid{};
	telemetry_posthog_timestamp timestamp{};
	const bool occurrence = utc_valid(first) && utc_valid(last) && first <= last &&
				(quality & TELEMETRY_QUALITY_CLOCK_DISCONTINUITY) == 0U;
	if (!telemetry_posthog_event_uuid(uuid) ||
	    !telemetry_posthog_format_timestamp(occurrence ? first : sealing_utc, timestamp))
	{
		row.valid = false;
		if (!occurrence && !utc_valid(sealing_utc))
			add_count(REDUCER.health.clock_failures);
	}
	row.text(row.root, "event", event);
	row.text(row.root, "uuid", uuid.data());
	row.text(row.root, "timestamp", timestamp.data());
	auto *properties = row.properties;
	row.text(properties, "duris_event_id", uuid.data());
	row.number(properties, "duris_schema_version", TELEMETRY_POSTHOG_SCHEMA_VERSION);
	row.number(properties, "duris_identity_key_version", 1U);
	row.put(properties, "$process_person_profile", cJSON_CreateFalse());
	row.integer(properties, "duris_environment_id", REDUCER.config.environment_id);
	row.integer(properties, "duris_season_id", REDUCER.config.season_id);
	row.integer(properties, "duris_config_id", config, config != 0U);
	row.number(properties, "classifier_version", classifier, classifier != 0U);
	row.number(properties, "policy_version", policy, policy != 0U);
	row.number(properties, "duris_quality_flags", quality);
	row.text(properties, "duris_test_run",
		 REDUCER.config.test_run[0] == '\0' ? nullptr : REDUCER.config.test_run.data());
	row.text(properties, "timestamp_basis", occurrence ? "occurrence" : "emitted_at");
	row.integer(properties, "occurrence_start_utc_usec", first, occurrence);
	row.integer(properties, "occurrence_end_utc_usec", last, occurrence);
	row.text(properties, "duris_run_id", nullptr);
	telemetry_posthog_character_identity character{};
	telemetry_posthog_scoped_identity session_id{};
	telemetry_posthog_scoped_identity system{};
	if (session != nullptr)
	{
		row.valid &= telemetry_posthog_character_id(REDUCER.config.identity_key,
							    session->environment_id,
							    session->season_id, session->subject_id,
							    character);
		row.valid &= telemetry_posthog_session_id(*session, session_id);
	}
	else
	{
		char *cursor = system.data();
		std::memcpy(cursor, "dh1", 3U);
		cursor += 3U;
		for (const auto value : { REDUCER.config.environment_id, REDUCER.config.season_id })
		{
			*cursor++ = ':';
			const auto result =
				std::to_chars(cursor, system.data() + system.size() - 1U, value);
			row.valid &= result.ec == std::errc{};
			cursor = result.ptr;
		}
	}
	row.text(properties, "distinct_id", session == nullptr ? system.data() : character.data());
	row.text(properties, "duris_character_id", session == nullptr ? nullptr : character.data());
	row.text(properties, "duris_session_id", session == nullptr ? nullptr : session_id.data());
	dimensions_json(row, properties, dimensions);
	if (session != nullptr &&
	    (dimensions == nullptr || !character_dimensions_known(*dimensions)))
		coverage |= COVERAGE_DIMENSIONS;
	/* Configuration rows carry their own validated snapshot. */
	if (session != nullptr && config != 0U)
	{
		const auto *known = find_configuration(config);
		if (known == nullptr ||
		    (classifier != 0U && known->classifier_version != classifier) ||
		    (policy != 0U && known->policy_version != policy))
		{
			coverage |= COVERAGE_CONFIG;
			add_count(REDUCER.health.missing_configuration_rows);
		}
	}
	if (!occurrence)
		coverage |= COVERAGE_CLOCK;
	if (REDUCER.health.output_suppressed != 0U)
		coverage |= COVERAGE_OUTPUT;
	coverage_json(row, coverage | native_coverage(quality));
}

bool queue_row(posthog_row &row, telemetry_monotonic_usec now) noexcept
{
	std::array<char, TELEMETRY_POSTHOG_MAX_EVENT_BYTES + 6U> encoded{};
	if (!row.valid || !cJSON_PrintPreallocated(row.root, encoded.data(),
						   static_cast<int>(encoded.size()), false))
	{
		add_count(REDUCER.health.serialization_failures);
		add_count(REDUCER.health.output_suppressed);
		return false;
	}
	const std::size_t bytes = std::strlen(encoded.data()) + 1U;
	if (bytes - 1U > TELEMETRY_POSTHOG_MAX_EVENT_BYTES ||
	    REDUCER.health.output_events == TELEMETRY_POSTHOG_MAX_EVENTS ||
	    bytes > REDUCER.bytes.size() - BATCH_FRAMING_RESERVE - REDUCER.health.output_bytes)
	{
		add_count(REDUCER.health.output_suppressed);
		return false;
	}
	auto &entry = REDUCER.output[REDUCER.health.output_events++];
	entry = { REDUCER.health.output_bytes, bytes, now };
	std::memcpy(REDUCER.bytes.data() + entry.offset, encoded.data(), bytes);
	REDUCER.health.output_bytes += static_cast<std::uint32_t>(bytes);
	add_count(REDUCER.health.created_events);
	return true;
}

character_state *character_for(const telemetry_session_ref &session,
			       telemetry_monotonic_usec now) noexcept
{
	if (!scope_matches(session.environment_id, session.season_id))
		return nullptr;
	character_state *free = nullptr;
	for (auto &character : REDUCER.characters)
	{
		if (!character.used)
		{
			if (free == nullptr)
				free = &character;
			continue;
		}
		if (same_session_id(character.session.id, session.id))
		{
			if (character.session.subject_id != session.subject_id ||
			    character.session.pid != session.pid)
				return nullptr;
			character.last_seen = std::max(character.last_seen, now);
			return &character;
		}
	}
	if (free == nullptr)
	{
		add_count(REDUCER.health.session_refusals);
		return nullptr;
	}
	*free = {};
	free->used = true;
	free->session = session;
	free->last_seen = now;
	++REDUCER.health.sessions;
	return free;
}

void reconciliation_json(posthog_row &row, const character_state &character) noexcept
{
	auto *object = row.object(row.properties, "reconciliation");
	row.put(object, "checkpoint_available", cJSON_CreateBool(character.has_checkpoint));
	row.integer(object, "revision", character.checkpoint.revision, character.has_checkpoint);
	row.number(object, "quality_flags", character.checkpoint.quality_flags,
		   character.has_checkpoint);
	row.integer(object, "at_utc_usec", character.checkpoint.at_utc_usec,
		    character.has_checkpoint && utc_valid(character.checkpoint.at_utc_usec));
	if (!character.has_checkpoint)
	{
		row.put(object, "checkpoint", cJSON_CreateNull());
		row.put(object, "observed_at_checkpoint", cJSON_CreateNull());
		row.put(object, "missing_detail", cJSON_CreateNull());
		row.put(object, "comparison_available", cJSON_CreateFalse());
		return;
	}
	constexpr const char *names[] = { "connected_usec", "active_usec",   "idle_usec",
					  "unknown_usec",   "resident_usec", "linkdead_usec" };
	const auto &checkpoint = character.checkpoint.cumulative;
	const std::array<std::uint64_t, 6U> expected = {
		checkpoint.connected_usec, checkpoint.active_usec,   checkpoint.idle_usec,
		checkpoint.unknown_usec,   checkpoint.resident_usec, checkpoint.linkdead_usec
	};
	const auto observed = duration_values(character.observed_at_checkpoint);
	bool comparable = character.checkpoint_comparable;
	for (std::size_t index = 0U; index < expected.size(); ++index)
		comparable &= !observed[index].overflow && observed[index].value <= expected[index];
	auto *absolute = row.object(object, "checkpoint");
	for (std::size_t index = 0U; index < expected.size(); ++index)
		row.integer(absolute, names[index], expected[index]);
	time_json(row, row.object(object, "observed_at_checkpoint"),
		  character.observed_at_checkpoint);
	row.put(object, "comparison_available", cJSON_CreateBool(comparable));
	if (comparable)
	{
		auto *missing = row.object(object, "missing_detail");
		for (std::size_t index = 0U; index < expected.size(); ++index)
			row.integer(missing, names[index], expected[index] - observed[index].value);
	}
	else
		row.put(object, "missing_detail", cJSON_CreateNull());
}

void seal_fragment(character_state &character, fragment &part, telemetry_monotonic_usec now,
		   telemetry_utc_usec utc) noexcept
{
	if (!part.used)
		return;
	std::uint32_t coverage = part.coverage | character.coverage;
	bool overflow = time_overflow(part.time) || xp_overflow(part.xp) ||
			time_overflow(part.unattributed_time) || xp_overflow(part.unattributed_xp);
	for (std::size_t index = 0U; index < part.time_count; ++index)
		if (time_overflow(part.time_buckets[index].totals))
		{
			overflow = true;
			coverage |= COVERAGE_TIME;
		}
	for (std::size_t index = 0U; index < part.xp_count; ++index)
		if (xp_overflow(part.xp_buckets[index].totals))
		{
			overflow = true;
			coverage |= COVERAGE_XP;
		}
	if (overflow)
	{
		coverage |= COVERAGE_OVERFLOW;
		add_count(REDUCER.health.counter_overflow_rows);
	}
	posthog_row row;
	common_json(row, "duris_character_summary", &character.session, part.config,
		    part.classifier, part.policy,
		    (coverage & COVERAGE_DIMENSIONS) != 0U ? nullptr : &part.dimensions,
		    part.quality, coverage, part.first, part.last, utc);
	row.integer(row.properties, "window_start_utc_usec", part.window, utc_valid(part.window));
	row.integer(row.properties, "interval_observations", part.interval_observations);
	row.number(row.properties, "xp_observed_level", part.xp_level, part.xp_level != 0U);
	time_json(row, row.object(row.properties, "time"), part.time);
	xp_json(row, row.object(row.properties, "xp"), part.xp);
	auto *times = row.array("time_allocations");
	for (std::size_t index = 0U; index < part.time_count; ++index)
	{
		const auto &bucket = part.time_buckets[index];
		auto *object = row.element(times);
		dimensions_json(row, object, &bucket.dimensions, true);
		row.number(object, "context", static_cast<std::uint32_t>(bucket.context));
		row.number(object, "context_quality",
			   static_cast<std::uint32_t>(bucket.context_quality));
		time_json(row, object, bucket.totals);
	}
	auto *xps = row.array("xp_allocations");
	for (std::size_t index = 0U; index < part.xp_count; ++index)
	{
		const auto &bucket = part.xp_buckets[index];
		auto *object = row.element(xps);
		dimensions_json(row, object, &bucket.dimensions, true);
		row.number(object, "source", static_cast<std::uint32_t>(bucket.source));
		row.number(object, "reason", static_cast<std::uint32_t>(bucket.reason));
		row.number(object, "observation_status",
			   static_cast<std::uint32_t>(bucket.observation));
		row.number(object, "modifier_flags", bucket.modifiers);
		xp_json(row, object, bucket.totals);
	}
	time_json(row, row.object(row.properties, "unattributed_time"), part.unattributed_time);
	xp_json(row, row.object(row.properties, "unattributed_xp"), part.unattributed_xp);
	reconciliation_json(row, character);
	(void)queue_row(row, now);
	if (utc_valid(part.window))
	{
		const auto end =
			part.window +
			static_cast<telemetry_utc_usec>(REDUCER.config.window_seconds) * 1'000'000;
		character.sealed_through = !utc_valid(character.sealed_through) ?
						   end :
						   std::max(character.sealed_through, end);
	}
	part = {};
}

fragment *fragment_for(character_state &character, telemetry_utc_usec window,
		       telemetry_config_id config, std::uint32_t classifier, std::uint32_t policy,
		       const telemetry_dimensions &dimensions, telemetry_monotonic_usec now,
		       telemetry_utc_usec utc) noexcept
{
	/* Stable dimensions/configs have one identity per fragment. */
	for (auto &part : character.fragments)
		if (part.used && (part.config != config || part.classifier != classifier ||
				  part.policy != policy ||
				  (character_dimensions_known(part.dimensions) &&
				   character_dimensions_known(dimensions) &&
				   !same_character_dimensions(part.dimensions, dimensions))))
			seal_fragment(character, part, now, utc);
	for (auto &part : character.fragments)
		if (part.used && part.window == window)
		{
			if (!character_dimensions_known(dimensions))
				part.coverage |= COVERAGE_DIMENSIONS;
			else if (!character_dimensions_known(part.dimensions))
				part.dimensions = dimensions;
			return &part;
		}
	fragment *free = nullptr;
	for (auto &part : character.fragments)
		if (!part.used)
		{
			free = &part;
			break;
		}
	if (free == nullptr)
	{
		free = &character.fragments[0];
		if (character.fragments[1].created_at < free->created_at)
			free = &character.fragments[1];
		seal_fragment(character, *free, now, utc);
	}
	*free = {};
	free->used = true;
	free->window = window;
	free->created_at = now;
	free->config = config;
	free->classifier = classifier;
	free->policy = policy;
	free->dimensions = dimensions;
	if (!character_dimensions_known(dimensions))
		free->coverage |= COVERAGE_DIMENSIONS;
	if (utc_valid(window) && utc_valid(character.sealed_through) &&
	    window < character.sealed_through)
		free->coverage |= COVERAGE_LATE;
	return free;
}

void occurrence(fragment &part, telemetry_utc_usec first, telemetry_utc_usec last) noexcept
{
	if (!utc_valid(first) || !utc_valid(last))
	{
		part.coverage |= COVERAGE_CLOCK;
		return;
	}
	if (!utc_valid(part.first) || first < part.first)
		part.first = first;
	if (!utc_valid(part.last) || last > part.last)
		part.last = last;
}

void add_interval(character_state &character, const telemetry_interval_payload &interval,
		  telemetry_duration_usec duration, telemetry_utc_usec first,
		  telemetry_utc_usec last, telemetry_monotonic_usec now,
		  telemetry_utc_usec utc) noexcept
{
	auto &part = *fragment_for(character, window_for(first), interval.config_id,
				   interval.classifier_version, interval.policy_version,
				   interval.dimensions, now, utc);
	occurrence(part, first, last);
	part.quality |= interval.quality_flags;
	add_count(part.interval_observations);
	const auto category = static_cast<std::size_t>(interval.category);
	part.time.category[category].add(duration);
	for (std::size_t index = 0U; index < part.time_count; ++index)
	{
		auto &bucket = part.time_buckets[index];
		if (same_character_dimensions(bucket.dimensions, interval.dimensions) &&
		    bucket.dimensions.zone_vnum == interval.dimensions.zone_vnum &&
		    bucket.dimensions.group_size == interval.dimensions.group_size &&
		    bucket.context == interval.context &&
		    bucket.context_quality == interval.context_quality)
		{
			bucket.totals.category[category].add(duration);
			return;
		}
	}
	if (part.time_count < part.time_buckets.size() &&
	    !telemetry_dimensions_are_unknown(interval.dimensions))
	{
		auto &bucket = part.time_buckets[part.time_count++];
		bucket.dimensions = interval.dimensions;
		bucket.context = interval.context;
		bucket.context_quality = interval.context_quality;
		bucket.totals.category[category].add(duration);
	}
	else
	{
		part.unattributed_time.category[category].add(duration);
		part.coverage |= COVERAGE_TIME;
		add_count(REDUCER.health.unattributed_time_fragments);
	}
}

bool consume_interval(const telemetry_interval_payload &interval, telemetry_monotonic_usec now,
		      telemetry_utc_usec utc) noexcept
{
	auto *character = character_for(interval.session, now);
	if (character == nullptr)
		return false;
	const auto category = static_cast<std::size_t>(interval.category);
	character->observed.category[category].add(interval.duration_usec);
	character->observed_through =
		std::max(character->observed_through, interval.window.end_monotonic_usec);
	if (character->has_checkpoint &&
	    character->checkpoint.at_monotonic_usec > interval.window.start_monotonic_usec)
	{
		const auto end = std::min(character->checkpoint.at_monotonic_usec,
					  interval.window.end_monotonic_usec);
		character->observed_at_checkpoint.category[category].add(
			end - interval.window.start_monotonic_usec);
	}
	const auto first = interval.window.start_utc_usec;
	const auto last = interval.window.end_utc_usec;
	const bool clock = utc_valid(first) && utc_valid(last) && last > first &&
			   static_cast<std::uint64_t>(last) - static_cast<std::uint64_t>(first) ==
				   interval.duration_usec &&
			   (interval.quality_flags & TELEMETRY_QUALITY_CLOCK_DISCONTINUITY) == 0U;
	if (!clock)
	{
		add_interval(*character, interval, interval.duration_usec, TELEMETRY_UTC_UNKNOWN,
			     TELEMETRY_UTC_UNKNOWN, now, utc);
		return true;
	}
	/* At most two recent fragments are retained even for a long native interval.
	 * Splitting stops at the native duration bound; emitted overflow is explicit. */
	auto cursor = first;
	for (std::size_t splits = 0U; cursor < last; ++splits)
	{
		/* A corrupt/stalled native clock can describe centuries. Bound work
		 * per record while conserving the remainder as unallocated time. */
		if (splits == 64U)
		{
			auto &part = *fragment_for(*character, TELEMETRY_UTC_UNKNOWN,
						   interval.config_id, interval.classifier_version,
						   interval.policy_version, interval.dimensions,
						   now, utc);
			const auto remainder = static_cast<std::uint64_t>(last - cursor);
			part.time.category[category].add(remainder);
			part.unattributed_time.category[category].add(remainder);
			part.quality |= interval.quality_flags;
			add_count(part.interval_observations);
			part.coverage |= COVERAGE_TIME | COVERAGE_CLOCK;
			add_count(REDUCER.health.unattributed_time_fragments);
			break;
		}
		const auto boundary =
			window_for(cursor) +
			static_cast<telemetry_utc_usec>(REDUCER.config.window_seconds) * 1'000'000;
		const auto end = std::min(last, boundary);
		add_interval(*character, interval, static_cast<std::uint64_t>(end - cursor), cursor,
			     end, now, utc);
		cursor = end;
	}
	return true;
}

void add_xp(xp_totals &totals, const telemetry_progression_payload &xp) noexcept
{
	totals.requested.add(xp.requested_xp);
	totals.computed.add(xp.computed_xp);
	totals.applied.add(xp.applied_xp);
	totals.attempts.add(1U);
	if (xp.applied_xp == 0)
		totals.zero_applied.add(1U);
}

bool consume_progression(const telemetry_progression_payload &xp, telemetry_monotonic_usec now,
			 telemetry_utc_usec utc) noexcept
{
	auto *character = character_for(xp.session, now);
	if (character == nullptr)
		return false;
	if (xp.kind != telemetry_progression_kind::experience_observed)
	{
		for (auto &part : character->fragments)
			seal_fragment(*character, part, now, utc);
		posthog_row row;
		common_json(row, "duris_level_change", &xp.session, xp.config_id,
			    xp.classifier_version, xp.policy_version, &xp.dimensions,
			    xp.quality_flags, character->coverage, xp.at_utc_usec, xp.at_utc_usec,
			    utc);
		row.number(row.properties, "before_level", xp.before_level, xp.before_level != 0U);
		row.number(row.properties, "after_level", xp.after_level, xp.after_level != 0U);
		row.number(row.properties, "transition", static_cast<std::uint32_t>(xp.kind));
		row.number(row.properties, "reason", static_cast<std::uint32_t>(xp.reason));
		row.number(row.properties, "source", static_cast<std::uint32_t>(xp.source));
		row.number(row.properties, "observation_status",
			   static_cast<std::uint32_t>(xp.observation_status));
		row.integer(row.properties, "threshold_xp", xp.threshold_xp);
		(void)queue_row(row, now);
		return true;
	}
	for (auto &part : character->fragments)
		if (part.used && part.xp.attempts.value != 0U && part.xp_level != xp.before_level)
			seal_fragment(*character, part, now, utc);
	const auto at_utc = (xp.quality_flags & TELEMETRY_QUALITY_CLOCK_DISCONTINUITY) == 0U ?
				    xp.at_utc_usec :
				    TELEMETRY_UTC_UNKNOWN;
	auto &part = *fragment_for(*character, window_for(at_utc), xp.config_id,
				   xp.classifier_version, xp.policy_version, xp.dimensions, now,
				   utc);
	part.xp_level = xp.before_level;
	occurrence(part, at_utc, at_utc);
	part.quality |= xp.quality_flags;
	add_xp(part.xp, xp);
	for (std::size_t index = 0U; index < part.xp_count; ++index)
	{
		auto &bucket = part.xp_buckets[index];
		if (same_character_dimensions(bucket.dimensions, xp.dimensions) &&
		    bucket.dimensions.zone_vnum == xp.dimensions.zone_vnum &&
		    bucket.dimensions.group_size == xp.dimensions.group_size &&
		    bucket.source == xp.source && bucket.reason == xp.reason &&
		    bucket.observation == xp.observation_status &&
		    bucket.modifiers == xp.modifier_flags)
		{
			add_xp(bucket.totals, xp);
			return true;
		}
	}
	if (part.xp_count < part.xp_buckets.size())
	{
		auto &bucket = part.xp_buckets[part.xp_count++];
		bucket.dimensions = xp.dimensions;
		bucket.source = xp.source;
		bucket.reason = xp.reason;
		bucket.observation = xp.observation_status;
		bucket.modifiers = xp.modifier_flags;
		add_xp(bucket.totals, xp);
	}
	else
	{
		part.coverage |= COVERAGE_XP;
		add_xp(part.unattributed_xp, xp);
		add_count(REDUCER.health.xp_attribution_overflows);
	}
	return true;
}

bool consume_lifecycle(const telemetry_session_lifecycle_payload &life,
		       telemetry_monotonic_usec now, telemetry_utc_usec utc) noexcept
{
	auto *character = character_for(life.session, now);
	if (character == nullptr)
		return false;
	if (life.lifecycle == telemetry_lifecycle_kind::session_entered)
		character->logical_entry_observed = true;
	if (life.lifecycle == telemetry_lifecycle_kind::session_exited)
		for (auto &part : character->fragments)
			seal_fragment(*character, part, now, utc);
	posthog_row row;
	common_json(row, "duris_session", &life.session, life.config_id, life.classifier_version,
		    life.policy_version, &life.dimensions, life.quality_flags, character->coverage,
		    life.at_utc_usec, life.at_utc_usec, utc);
	constexpr const char *transitions[] = { "invalid", "logical_entry", "logical_exit",
						"connection_attached", "connection_detached" };
	row.text(row.properties, "transition",
		 transitions[static_cast<std::size_t>(life.lifecycle)]);
	row.number(row.properties, "end_reason", static_cast<std::uint32_t>(life.end_reason));
	reconciliation_json(row, *character);
	(void)queue_row(row, now);
	if (life.lifecycle == telemetry_lifecycle_kind::session_exited)
	{
		*character = {};
		--REDUCER.health.sessions;
	}
	return true;
}

bool consume_checkpoint(const telemetry_session_checkpoint_payload &checkpoint,
			telemetry_monotonic_usec now) noexcept
{
	auto *character = character_for(checkpoint.session, now);
	if (character == nullptr)
		return false;
	if (character->has_checkpoint && checkpoint.revision <= character->checkpoint.revision)
	{
		if (checkpoint.revision < character->checkpoint.revision)
			add_count(REDUCER.health.stale_checkpoints);
		else
		{
			const auto &a = checkpoint.cumulative;
			const auto &b = character->checkpoint.cumulative;
			if (a.connected_usec != b.connected_usec ||
			    a.active_usec != b.active_usec || a.idle_usec != b.idle_usec ||
			    a.unknown_usec != b.unknown_usec ||
			    a.resident_usec != b.resident_usec ||
			    a.linkdead_usec != b.linkdead_usec)
			{
				add_count(REDUCER.health.checkpoint_conflicts);
				character->coverage |= COVERAGE_GAP;
				return false;
			}
		}
		return true;
	}
	if (character->has_checkpoint)
	{
		const auto &a = checkpoint.cumulative;
		const auto &b = character->checkpoint.cumulative;
		if (a.connected_usec < b.connected_usec || a.active_usec < b.active_usec ||
		    a.idle_usec < b.idle_usec || a.unknown_usec < b.unknown_usec ||
		    a.resident_usec < b.resident_usec || a.linkdead_usec < b.linkdead_usec)
		{
			add_count(REDUCER.health.checkpoint_conflicts);
			character->coverage |= COVERAGE_GAP;
			return false;
		}
	}
	character->has_checkpoint = true;
	character->checkpoint = checkpoint;
	character->observed_at_checkpoint = character->observed;
	character->checkpoint_comparable =
		character->logical_entry_observed &&
		(checkpoint.quality_flags & TELEMETRY_QUALITY_CLOCK_DISCONTINUITY) == 0U &&
		character->observed_through <= checkpoint.at_monotonic_usec;
	character->coverage |= native_coverage(checkpoint.quality_flags);
	return true;
}

bool consume_configuration(const telemetry_config_snapshot &config, telemetry_monotonic_usec now,
			   telemetry_utc_usec utc) noexcept
{
	std::array<std::uint8_t, TELEMETRY_CONFIG_FINGERPRINT_BYTES> fingerprint{};
	if (!scope_matches(config.environment_id, config.season_id) ||
	    !telemetry_config_compute_fingerprint(config, fingerprint.data(), fingerprint.size()) ||
	    std::memcmp(fingerprint.data(), config.fingerprint, fingerprint.size()) != 0 ||
	    config.config_id !=
		    telemetry_config_id_from_fingerprint(fingerprint.data(), fingerprint.size()))
	{
		add_count(REDUCER.health.configuration_refusals);
		return false;
	}
	if (const auto *known = find_configuration(config.config_id))
	{
		if (std::memcmp(known->fingerprint, config.fingerprint, fingerprint.size()) == 0)
			return true;
		add_count(REDUCER.health.configuration_refusals);
		return false;
	}
	if (REDUCER.health.configurations == REDUCER.configurations.size())
	{
		add_count(REDUCER.health.configuration_refusals);
		return false;
	}
	posthog_row row;
	common_json(row, "duris_configuration", nullptr, config.config_id,
		    config.classifier_version, config.policy_version, nullptr, 0U, 0U,
		    config.effective_utc_usec, config.effective_utc_usec, utc);
	char hex[65]{};
	for (std::size_t index = 0U; index < fingerprint.size(); ++index)
	{
		hex[index * 2U] = HEX[fingerprint[index] >> 4U];
		hex[index * 2U + 1U] = HEX[fingerprint[index] & 0x0FU];
	}
	row.text(row.properties, "fingerprint", hex);
	row.integer(row.properties, "revision", config.revision);
	row.number(row.properties, "build_version", config.build_version);
	row.number(row.properties, "content_version", config.content_version);
	row.number(row.properties, "property_version", config.property_version);
	row.integer(row.properties, "native_interval_usec", config.interval_usec);
	row.integer(row.properties, "checkpoint_interval_usec", config.checkpoint_interval_usec);
	row.integer(row.properties, "active_window_usec", config.active_window_usec);
	row.number(row.properties, "context_segments_per_minute",
		   config.context_segments_per_minute);
	row.number(row.properties, "pulse_slot_count", config.pulse_slot_count);
	row.number(row.properties, "native_backend", static_cast<std::uint32_t>(config.backend));
	row.put(row.properties, "enabled", cJSON_CreateBool(config.enabled));
	if (queue_row(row, now))
		REDUCER.configurations[REDUCER.health.configurations++] = config;
	return true;
}

bool same_source(const telemetry_encounter_source &a, const telemetry_encounter_source &b) noexcept
{
	return a.environment_id == b.environment_id && a.season_id == b.season_id &&
	       a.config_id == b.config_id && a.classifier_version == b.classifier_version &&
	       a.policy_version == b.policy_version && a.zone_vnum == b.zone_vnum &&
	       a.group_key == b.group_key;
}

bool terminal_conflict(encounter_state &run) noexcept
{
	run.coverage |= COVERAGE_TERMINAL;
	add_count(REDUCER.health.terminal_conflicts);
	return false;
}

encounter_state *encounter_for(const telemetry_encounter_id &id,
			       const telemetry_encounter_source &source,
			       telemetry_encounter_mode mode, telemetry_monotonic_usec start,
			       telemetry_utc_usec start_utc) noexcept
{
	if (!scope_matches(source.environment_id, source.season_id) ||
	    !same_producer(id.producer, REDUCER.config.producer))
		return nullptr;
	encounter_state *free = nullptr;
	for (auto &run : REDUCER.encounters)
	{
		if (!run.used)
		{
			if (free == nullptr)
				free = &run;
			continue;
		}
		if (run.id.sequence != id.sequence)
			continue;
		if (run.emitting)
		{
			add_count(REDUCER.health.late_encounter_records);
			return nullptr;
		}
		if (!same_source(run.source, source) || run.start != start ||
		    run.start_utc != start_utc)
		{
			(void)terminal_conflict(run);
			return nullptr;
		}
		/* Roster mode can become mixed during a run; combat retains its
			 * initial mode. Merge their captured evidence without regressing it. */
		if (mode != telemetry_encounter_mode::unknown && run.mode != mode)
			run.mode = run.mode == telemetry_encounter_mode::unknown ?
					   mode :
					   telemetry_encounter_mode::mixed;
		return &run;
	}
	if (id.sequence <= REDUCER.retired_through ||
	    std::find(REDUCER.retired_runs.begin(), REDUCER.retired_runs.end(), id.sequence) !=
		    REDUCER.retired_runs.end())
	{
		add_count(REDUCER.health.late_encounter_records);
		return nullptr;
	}
	if (free == nullptr)
	{
		add_count(REDUCER.health.run_refusals);
		return nullptr;
	}
	*free = {};
	free->used = true;
	free->id = id;
	free->source = source;
	free->mode = mode;
	free->start = start;
	free->start_utc = start_utc;
	++REDUCER.health.runs;
	return free;
}

bool terminal_metadata(encounter_state &run, telemetry_encounter_outcome outcome,
		       telemetry_monotonic_usec end, telemetry_utc_usec end_utc,
		       telemetry_monotonic_usec now) noexcept
{
	if (run.terminal)
	{
		if (run.outcome != outcome || run.end != end || run.end_utc != end_utc)
			return terminal_conflict(run);
		return true;
	}
	run.terminal = true;
	run.outcome = outcome;
	run.end = end;
	run.end_utc = end_utc;
	run.terminal_at = now;
	return true;
}

encounter_actor *actor_for(encounter_state &run, telemetry_combat_actor_kind kind, telemetry_id id,
			   telemetry_subject_id owner) noexcept
{
	for (std::size_t index = 0U; index < run.actor_count; ++index)
	{
		auto &actor = run.actors[index];
		if (actor.kind == kind && actor.id == id && actor.owner == owner)
			return &actor;
	}
	if (run.actor_count == run.actors.size())
	{
		run.coverage |= COVERAGE_COMBAT;
		add_count(REDUCER.health.actor_attribution_overflows);
		return nullptr;
	}
	auto &actor = run.actors[run.actor_count++];
	actor.kind = kind;
	actor.id = id;
	actor.owner = owner;
	return &actor;
}

std::array<std::uint64_t, 10U> combat_values(const telemetry_combat_summary_payload &value) noexcept
{
	return { value.damage_dealt,	    value.damage_taken,	  value.healing_attempted,
		 value.effective_healing,   value.overhealing,	  value.casting_attempts,
		 value.casting_completions, value.casting_aborts, value.casting_elapsed_usec,
		 value.tanking_usec };
}

void add_combat(combat_totals &totals, const telemetry_combat_summary_payload &value) noexcept
{
	const auto values = combat_values(value);
	for (std::size_t index = 0U; index < values.size(); ++index)
		totals.values[index].add(values[index]);
}

bool combat_overflow(const combat_totals &totals) noexcept
{
	return std::any_of(totals.values.begin(), totals.values.end(),
			   [](const auto &value) { return value.overflow; });
}

bool consume_encounter(const telemetry_encounter_payload &value,
		       telemetry_monotonic_usec now) noexcept
{
	if (value.participant_count > ACTOR_LIMIT ||
	    (value.kind == telemetry_encounter_event_kind::participant_summary &&
	     value.participant_count == 0U))
		return false;
	auto *run = encounter_for(value.encounter, value.source, value.mode,
				  value.start_monotonic_usec, value.start_utc_usec);
	if (run == nullptr)
		return false;
	run->quality |= value.quality_flags;
	if (value.kind == telemetry_encounter_event_kind::start)
	{
		run->started = true;
		return true;
	}
	if (value.kind == telemetry_encounter_event_kind::participant_join)
		return true;
	if (value.kind == telemetry_encounter_event_kind::participant_leave)
	{
		auto *actor = actor_for(*run, telemetry_combat_actor_kind::player,
					value.participant.subject_id, value.participant.subject_id);
		if (actor == nullptr)
			return false;
		if (actor->has_participation && value.participant_usec < actor->participant_usec)
			return terminal_conflict(*run);
		/* A lost terminal must not erase the cumulative effort captured at
			 * leave. Rejoining never adds this absolute observation twice. */
		actor->has_participation = true;
		actor->participant_usec = value.participant_usec;
		return true;
	}
	if (!terminal_metadata(*run, value.outcome, value.at_monotonic_usec, value.at_utc_usec,
			       now))
		return false;
	if ((run->closed || run->roster_count != 0U) &&
	    run->roster_expected != value.participant_count)
		return terminal_conflict(*run);
	run->roster_expected = value.participant_count;
	if (value.kind == telemetry_encounter_event_kind::close)
	{
		if (run->closed)
		{
			if (run->credit_count != value.expected_credit_count)
				return terminal_conflict(*run);
			add_count(REDUCER.health.terminal_duplicates);
			return true;
		}
		run->closed = true;
		run->credit_count = value.expected_credit_count;
		return true;
	}
	const auto end = run->roster_subjects.begin() + run->roster_count;
	if (std::find(run->roster_subjects.begin(), end, value.participant.subject_id) != end)
	{
		add_count(REDUCER.health.terminal_duplicates);
		return true;
	}
	if (run->roster_count >= run->roster_expected)
		return terminal_conflict(*run);
	auto *actor = actor_for(*run, telemetry_combat_actor_kind::player,
				value.participant.subject_id, value.participant.subject_id);
	if (actor == nullptr)
		run->unattributed_roster_usec.add(value.participant_usec);
	else
	{
		if (actor->has_participation && value.participant_usec < actor->participant_usec)
			return terminal_conflict(*run);
		actor->has_participation = true;
		actor->participation_terminal = true;
		actor->participant_usec = value.participant_usec;
	}
	run->roster_subjects[run->roster_count++] = value.participant.subject_id;
	return true;
}

bool consume_combat(const telemetry_combat_summary_payload &value,
		    telemetry_monotonic_usec now) noexcept
{
	if (value.participant_count == 0U || value.revision > value.participant_count)
		return false;
	auto *run = encounter_for(value.encounter, value.source, value.mode,
				  value.start_monotonic_usec, value.start_utc_usec);
	if (run == nullptr)
		return false;
	run->quality |= value.quality_flags;
	if (!terminal_metadata(*run, value.outcome, value.end_monotonic_usec, value.end_utc_usec,
			       now))
		return false;
	if (run->has_combat && (run->combat_expected != value.participant_count ||
				run->unique_players != value.unique_player_count ||
				run->dropped_actor_attempts != value.dropped_participant_count))
		return terminal_conflict(*run);
	run->has_combat = true;
	run->combat_expected = value.participant_count;
	run->unique_players = value.unique_player_count;
	run->dropped_actor_attempts = value.dropped_participant_count;
	const auto bit = std::uint64_t{ 1U } << (value.revision - 1U);
	if ((run->combat_revisions & bit) != 0U)
	{
		add_count(REDUCER.health.terminal_duplicates);
		return true;
	}
	if (value.actor_kind == telemetry_combat_actor_kind::npc)
	{
		/* NPC rows still prove terminal arrival; retain no NPC identities. */
		run->combat_revisions |= bit;
		++run->npc_count;
		run->coverage |= COVERAGE_ACTOR;
		add_count(REDUCER.health.unsupported_npc_rows);
		return true;
	}
	auto *actor = actor_for(*run, value.actor_kind, value.actor_id, value.owner_subject_id);
	if (actor == nullptr)
	{
		if (value.actor_kind == telemetry_combat_actor_kind::player)
		{
			++run->unattributed_players;
			add_combat(run->unattributed_player_combat, value);
		}
		else
		{
			++run->unattributed_pets;
			add_combat(run->unattributed_pet_combat, value);
		}
	}
	else
	{
		if (actor->has_combat)
			return terminal_conflict(*run);
		actor->has_combat = true;
		actor->combat = value;
	}
	run->combat_revisions |= bit;
	return true;
}

bool terminal_complete(const encounter_state &run) noexcept
{
	return run.started && run.closed && run.roster_count == run.roster_expected &&
	       run.has_combat && std::popcount(run.combat_revisions) == run.combat_expected &&
	       (run.coverage & COVERAGE_TERMINAL) == 0U;
}

void combat_json(posthog_row &row, cJSON *object, const combat_totals &totals) noexcept
{
	constexpr const char *names[] = { "damage_dealt",	  "damage_taken",
					  "healing_attempted",	  "effective_healing",
					  "overhealing",	  "casting_attempts",
					  "casting_completions",  "casting_aborts",
					  "casting_elapsed_usec", "tanking_usec" };
	for (std::size_t index = 0U; index < std::size(names); ++index)
		row.value(object, names[index], totals.values[index]);
	/* There are no gameplay callers for the native control hook yet. */
	row.put(object, "control_applications", cJSON_CreateNull());
}

bool seal_encounter_row(const encounter_state &run, const encounter_actor *actor,
			telemetry_monotonic_usec now, telemetry_utc_usec utc) noexcept
{
	posthog_row row;
	auto coverage = run.coverage;
	if (actor == nullptr &&
	    (combat_overflow(run.unattributed_player_combat) ||
	     combat_overflow(run.unattributed_pet_combat) || run.unattributed_roster_usec.overflow))
	{
		coverage |= COVERAGE_OVERFLOW;
		add_count(REDUCER.health.counter_overflow_rows);
	}
	common_json(row, "duris_encounter_summary", nullptr, run.source.config_id,
		    run.source.classifier_version, run.source.policy_version, nullptr, run.quality,
		    coverage, run.start_utc, run.terminal ? run.end_utc : TELEMETRY_UTC_UNKNOWN,
		    utc);
	telemetry_posthog_scoped_identity run_id{};
	row.valid &= telemetry_posthog_run_id(REDUCER.config.environment_id,
					      REDUCER.config.season_id, run.id, run_id);
	row.replace_text("duris_run_id", run_id.data());
	auto *properties = row.properties;
	row.text(properties, "row_type", actor == nullptr ? "run" : "participant");
	row.number(properties, "mode", static_cast<std::uint32_t>(run.mode),
		   run.mode != telemetry_encounter_mode::unknown);
	row.number(properties, "outcome", static_cast<std::uint32_t>(run.outcome), run.terminal);
	row.number(properties, "zone", static_cast<std::uint32_t>(run.source.zone_vnum),
		   run.source.zone_vnum >= 0);
	row.put(properties, "native_terminal_complete", cJSON_CreateBool(terminal_complete(run)));
	row.text(properties, "historical_dimensions_reason", "not_captured_in_native_encounter");
	row.text(properties, "control_applications_reason", "not_instrumented");
	row.put(properties, "native_counters_are_lower_bounds",
		cJSON_CreateBool((run.quality & TELEMETRY_QUALITY_CARDINALITY_OVERFLOW) != 0U));
	if (actor == nullptr)
	{
		row.replace_text("distinct_id", run_id.data());
		row.integer(properties, "run_elapsed_usec", run.end - run.start, run.terminal);
		row.number(properties, "expected_reward_credit_count", run.credit_count,
			   run.closed);
		row.number(properties, "roster_expected", run.roster_expected,
			   run.closed || run.roster_count != 0U);
		row.number(properties, "roster_received", run.roster_count);
		row.number(properties, "combat_expected", run.combat_expected, run.has_combat);
		row.number(properties, "combat_received", std::popcount(run.combat_revisions));
		row.number(properties, "native_dropped_actor_attempts", run.dropped_actor_attempts,
			   run.has_combat);
		row.number(properties, "unique_player_count", run.unique_players, run.has_combat);
		row.number(properties, "participant_rows_expected", run.actor_count);
		row.number(properties, "unsupported_npc_rows", run.npc_count);
		row.number(properties, "unattributed_player_rows", run.unattributed_players);
		row.number(properties, "unattributed_pet_rows", run.unattributed_pets);
		row.value(properties, "unattributed_roster_usec", run.unattributed_roster_usec);
		combat_json(row, row.object(properties, "unattributed_player_combat"),
			    run.unattributed_player_combat);
		combat_json(row, row.object(properties, "unattributed_pet_combat"),
			    run.unattributed_pet_combat);
	}
	else
	{
		telemetry_posthog_character_identity owner{};
		telemetry_posthog_pet_identity pet{};
		row.valid &= telemetry_posthog_character_id(REDUCER.config.identity_key,
							    REDUCER.config.environment_id,
							    REDUCER.config.season_id, actor->owner,
							    owner);
		const bool player = actor->kind == telemetry_combat_actor_kind::player;
		if (!player)
			row.valid &= telemetry_posthog_pet_id(REDUCER.config.identity_key,
							      REDUCER.config.environment_id,
							      REDUCER.config.season_id, run.id,
							      actor->id, pet);
		const char *identity = player ? owner.data() : pet.data();
		row.replace_text("distinct_id", identity);
		row.replace_text("duris_character_id", player ? owner.data() : nullptr);
		row.text(properties, "duris_actor_id", identity);
		row.text(properties, "duris_owner_character_id", player ? nullptr : owner.data());
		row.text(properties, "actor_kind", player ? "player" : "pet");
		row.integer(properties, "participant_usec", actor->participant_usec,
			    actor->has_participation);
		row.text(properties, "participant_time_basis",
			 !actor->has_participation     ? nullptr :
			 actor->participation_terminal ? "terminal" :
							 "observed_lower_bound");
		if (actor->has_combat)
		{
			combat_totals totals{};
			add_combat(totals, actor->combat);
			combat_json(row, row.object(properties, "combat"), totals);
		}
		else
			row.put(properties, "combat", cJSON_CreateNull());
		row.number(properties, "power_band", actor->combat.power_band,
			   actor->has_combat && actor->combat.power_band != 0U);
		row.number(properties, "opponent_power_band", actor->combat.opponent_power_band,
			   actor->has_combat && actor->combat.opponent_power_band != 0U);
		row.number(properties, "opponent_count", actor->combat.opponent_count,
			   actor->has_combat);
		row.number(properties, "combat_modifier_flags", actor->combat.modifier_flags,
			   actor->has_combat);
	}
	return queue_row(row, now);
}

void seal_encounters(telemetry_monotonic_usec now, telemetry_utc_usec utc, bool force) noexcept
{
	for (auto &run : REDUCER.encounters)
	{
		if (!run.used)
			continue;
		const bool expired =
			run.terminal &&
			(now < run.terminal_at ||
			 now - run.terminal_at >= TELEMETRY_POSTHOG_MAX_OUTPUT_AGE_USEC);
		if (!run.emitting)
		{
			if (!force && !expired && !terminal_complete(run))
				continue;
			if (!terminal_complete(run))
			{
				run.coverage |= COVERAGE_TERMINAL;
				add_count(REDUCER.health.incomplete_runs);
			}
			if (!run.terminal)
				run.coverage |= COVERAGE_TAIL;
			run.emitting = true;
		}
		while (run.output_cursor <= run.actor_count)
		{
			/* Pause terminal bursts across worker drains; never build a second
				 * serialized backlog or reseal an already emitted prefix. */
			if (REDUCER.health.output_events == TELEMETRY_POSTHOG_MAX_EVENTS ||
			    REDUCER.bytes.size() - BATCH_FRAMING_RESERVE -
					    REDUCER.health.output_bytes <
				    TELEMETRY_POSTHOG_MAX_EVENT_BYTES + 1U)
			{
				if (!force && !expired)
					break;
				add_count(REDUCER.health.output_suppressed,
					  run.actor_count + 1U - run.output_cursor);
				run.output_cursor = run.actor_count + 1U;
				break;
			}
			if (!seal_encounter_row(run,
						run.output_cursor == 0U ?
							nullptr :
							&run.actors[run.output_cursor - 1U],
						now, utc))
				run.coverage |= COVERAGE_OUTPUT;
			++run.output_cursor;
		}
		if (run.output_cursor <= run.actor_count)
			continue;
		auto &retired = REDUCER.retired_runs[REDUCER.retired_cursor];
		REDUCER.retired_through = std::max(REDUCER.retired_through, retired);
		retired = run.id.sequence;
		REDUCER.retired_cursor =
			(REDUCER.retired_cursor + 1U) % REDUCER.retired_runs.size();
		run = {};
		--REDUCER.health.runs;
	}
}
} // namespace

void telemetry_posthog_reducer_reset() noexcept
{
	REDUCER.initialized = false;
	OPENSSL_cleanse(REDUCER.config.identity_key.data(), REDUCER.config.identity_key.size());
	REDUCER.config = {};
	REDUCER.health = {};
	REDUCER.last_sequence = 0U;
	for (auto &character : REDUCER.characters)
		character = {};
	REDUCER.configurations.fill({});
	for (auto &run : REDUCER.encounters)
		run = {};
	REDUCER.retired_runs.fill(0U);
	REDUCER.retired_cursor = 0U;
	REDUCER.retired_through = 0U;
	REDUCER.output.fill({});
	REDUCER.bytes.fill('\0');
}

bool telemetry_posthog_reducer_init(const telemetry_posthog_reducer_config &config) noexcept
{
	telemetry_posthog_reducer_reset();
	if (config.environment_id == 0U || config.season_id == 0U ||
	    !has_key(config.identity_key) || !telemetry_producer_id_is_valid(config.producer) ||
	    (config.window_seconds != 900U && config.window_seconds != 1800U))
		return false;
	const auto end = std::find(config.test_run.begin(), config.test_run.end(), '\0');
	if (end == config.test_run.end() ||
	    std::any_of(config.test_run.begin(), end,
			[](unsigned char value) { return value < 0x20U || value > 0x7EU; }))
		return false;
	REDUCER.config = config;
	REDUCER.initialized = true;
	return true;
}

bool telemetry_posthog_consume(const telemetry_record &record, telemetry_monotonic_usec now,
			       telemetry_utc_usec utc) noexcept
{
	if (!REDUCER.initialized || !telemetry_record_header_is_valid(record.header) ||
	    !same_producer(record.header.key.producer, REDUCER.config.producer) ||
	    record.header.key.record_seq <= REDUCER.last_sequence)
	{
		add_count(REDUCER.health.invalid_records);
		return false;
	}
	if (record.header.key.record_seq - REDUCER.last_sequence > 1U)
	{
		add_count(REDUCER.health.input_sequence_gaps);
		for (auto &character : REDUCER.characters)
			if (character.used)
				character.coverage |= COVERAGE_GAP;
		for (auto &run : REDUCER.encounters)
			if (run.used && !run.emitting)
				run.coverage |= COVERAGE_GAP;
	}
	REDUCER.last_sequence = record.header.key.record_seq;
	if (!telemetry_record_is_valid(record))
	{
		add_count(REDUCER.health.invalid_records);
		return false;
	}
	add_count(REDUCER.health.consumed_by_kind[static_cast<std::size_t>(record.header.kind)]);
	bool accepted = false;
	switch (record.header.kind)
	{
	case telemetry_record_kind::interval:
		accepted = consume_interval(record.payload.interval, now, utc);
		break;
	case telemetry_record_kind::progression:
		accepted = consume_progression(record.payload.progression, now, utc);
		break;
	case telemetry_record_kind::session_lifecycle:
		accepted = consume_lifecycle(record.payload.lifecycle, now, utc);
		break;
	case telemetry_record_kind::session_checkpoint:
		accepted = consume_checkpoint(record.payload.checkpoint, now);
		break;
	case telemetry_record_kind::configuration:
		accepted = consume_configuration(record.payload.configuration.config, now, utc);
		break;
	case telemetry_record_kind::coverage_gap:
	{
		const auto &gap = record.payload.gap;
		add_count(REDUCER.health.native_gaps);
		add_count(REDUCER.health.native_dropped_records, gap.dropped_records);
		add_count(REDUCER.health.native_gap_known_usec, gap.duration_usec);
		if (!telemetry_session_ref_is_zero(gap.session))
		{
			auto *character = character_for(gap.session, now);
			if (character != nullptr)
			{
				character->coverage |= COVERAGE_GAP |
						       native_coverage(gap.quality_flags);
				accepted = true;
			}
		}
		else
		{
			for (auto &character : REDUCER.characters)
				if (character.used)
					character.coverage |= COVERAGE_GAP |
							      native_coverage(gap.quality_flags);
			for (auto &run : REDUCER.encounters)
				if (run.used && !run.emitting)
					run.coverage |= COVERAGE_GAP |
							native_coverage(gap.quality_flags);
			accepted = true;
		}
		break;
	}
	case telemetry_record_kind::encounter:
		accepted = consume_encounter(record.payload.encounter, now);
		break;
	case telemetry_record_kind::combat_summary:
		accepted = consume_combat(record.payload.combat_summary, now);
		break;
	default:
		break;
	}
	if (!accepted)
		add_count(REDUCER.health.reduction_refusals);
	return accepted;
}

void telemetry_posthog_seal_through(telemetry_monotonic_usec now, telemetry_utc_usec utc,
				    bool force) noexcept
{
	if (!REDUCER.initialized)
		return;
	const auto span =
		static_cast<telemetry_utc_usec>(REDUCER.config.window_seconds) * 1'000'000;
	for (auto &character : REDUCER.characters)
	{
		if (!character.used)
			continue;
		const bool silent = now >= character.last_seen &&
				    now - character.last_seen >= MAX_SESSION_SILENCE_USEC;
		if (silent)
			character.coverage |= COVERAGE_TAIL;
		for (auto &part : character.fragments)
		{
			if (!part.used)
				continue;
			const bool completed_window = utc_valid(part.window) && utc_valid(utc) &&
						      part.window + span <= utc;
			const bool aged = now >= part.created_at &&
					  now - part.created_at >= static_cast<std::uint64_t>(span);
			if (force || completed_window || aged || silent)
				seal_fragment(character, part, now, utc);
		}
		if (silent)
		{
			character = {};
			--REDUCER.health.sessions;
			add_count(REDUCER.health.abandoned_sessions);
		}
	}
	seal_encounters(now, utc, force);
}

telemetry_posthog_output telemetry_posthog_output_peek(std::size_t offset) noexcept
{
	if (offset >= REDUCER.health.output_events)
		return {};
	const auto &entry = REDUCER.output[offset];
	return { std::string_view(REDUCER.bytes.data() + entry.offset, entry.bytes - 1U),
		 entry.sealed_at, false };
}

bool telemetry_posthog_output_retire(std::size_t count,
				     telemetry_posthog_output_disposition disposition) noexcept
{
	if (count == 0U || count > REDUCER.health.output_events)
		return false;
	const auto &last = REDUCER.output[count - 1U];
	const auto removed_bytes = last.offset + last.bytes;
	std::memmove(REDUCER.bytes.data(), REDUCER.bytes.data() + removed_bytes,
		     REDUCER.health.output_bytes - removed_bytes);
	for (std::size_t index = count; index < REDUCER.health.output_events; ++index)
	{
		REDUCER.output[index - count] = REDUCER.output[index];
		REDUCER.output[index - count].offset -= removed_bytes;
	}
	REDUCER.health.output_events -= static_cast<std::uint32_t>(count);
	REDUCER.health.output_bytes -= static_cast<std::uint32_t>(removed_bytes);
	switch (disposition)
	{
	case telemetry_posthog_output_disposition::http_acknowledged:
		add_count(REDUCER.health.http_acknowledged, count);
		break;
	case telemetry_posthog_output_disposition::suppressed:
		add_count(REDUCER.health.output_suppressed, count);
		break;
	case telemetry_posthog_output_disposition::ambiguous:
		add_count(REDUCER.health.ambiguous_events, count);
		break;
	}
	return true;
}

void telemetry_posthog_output_expire(telemetry_monotonic_usec now) noexcept
{
	std::size_t expired = 0U;
	while (expired < REDUCER.health.output_events)
	{
		const auto at = REDUCER.output[expired].sealed_at;
		if (now >= at && now - at < TELEMETRY_POSTHOG_MAX_OUTPUT_AGE_USEC)
			break;
		++expired;
	}
	if (expired != 0U)
	{
		(void)telemetry_posthog_output_retire(
			expired, telemetry_posthog_output_disposition::suppressed);
		add_count(REDUCER.health.output_expired, expired);
	}
}

telemetry_posthog_reducer_health telemetry_posthog_reducer_health_copy() noexcept
{
	return REDUCER.health;
}
