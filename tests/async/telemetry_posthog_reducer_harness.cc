#include "telemetry/telemetry_posthog.h"
#include "telemetry/telemetry_config_private.h"

#include <cjson/cJSON.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <limits>
#include <string>

namespace
{
constexpr telemetry_utc_usec BASE = 1'728'000'000'000'000LL;
constexpr telemetry_monotonic_usec MONO = 1'000'000U;
constexpr telemetry_producer_id PRODUCER{ 11U, 22U };
telemetry_record_sequence SEQUENCE = 0U;
telemetry_monotonic_usec NOW = 0U;
telemetry_config_snapshot CONFIG{};
telemetry_producer_id SESSION_PRODUCER = PRODUCER;
std::size_t ALLOCATION_BUDGET = 0U;

void check(bool value, const char *expression, int line)
{
	if (!value)
	{
		std::fprintf(stderr, "PostHog reducer fixture line %d: %s\n", line, expression);
		std::abort();
	}
}
#define CHECK(expression) check((expression), #expression, __LINE__)

telemetry_session_ref session(std::uint32_t number = 44U)
{
	return {
		{ SESSION_PRODUCER, number }, number, static_cast<telemetry_pid>(number), 1U, 1000U
	};
}

telemetry_dimensions dimensions(std::int32_t zone = 10)
{
	return { 3U, 3U, 4U, 5U, zone, 1U };
}

bool emit(telemetry_record record, bool expected = true)
{
	record.header = {
		TELEMETRY_SCHEMA_VERSION, record.header.kind, 0U, { PRODUCER, ++SEQUENCE }, BASE
	};
	CHECK(telemetry_record_is_valid(record));
	NOW += 100U;
	const bool actual = telemetry_posthog_consume(record, NOW, BASE + 60'000'000);
	CHECK(actual == expected);
	return actual;
}

telemetry_config_snapshot configuration(std::uint32_t version = 1U)
{
	telemetry_config_snapshot config{};
	config.schema_version = TELEMETRY_SCHEMA_VERSION;
	config.config_id = 1U;
	config.revision = version;
	config.build_version = 1U;
	config.content_version = 1U;
	config.property_version = version;
	config.classifier_version = 1U;
	config.policy_version = 1U;
	config.season_id = 1U;
	config.environment_id = 1000U;
	config.effective_utc_usec = BASE;
	config.interval_usec = 60'000'000U;
	config.checkpoint_interval_usec = 60'000'000U;
	config.active_window_usec = 300'000'000U;
	config.context_segments_per_minute = 8U;
	config.pulse_slot_count = 8U;
	config.backend = telemetry_storage_backend::sql;
	config.enabled = 1U;
	CHECK(telemetry_config_compute_fingerprint(config, config.fingerprint,
						   sizeof(config.fingerprint)));
	config.config_id = telemetry_config_id_from_fingerprint(config.fingerprint,
								sizeof(config.fingerprint));
	CHECK(telemetry_config_is_valid(config));
	return config;
}

void publish(const telemetry_config_snapshot &config, bool expected = true)
{
	telemetry_record record{};
	record.header.kind = telemetry_record_kind::configuration;
	record.payload.configuration.config = config;
	emit(record, expected);
}

void initialize(bool with_configuration = true)
{
	SEQUENCE = 0U;
	NOW = 0U;
	SESSION_PRODUCER = PRODUCER;
	telemetry_posthog_reducer_config config{};
	config.environment_id = 1000U;
	config.season_id = 1U;
	config.producer = PRODUCER;
	for (std::size_t index = 0U; index < config.identity_key.size(); ++index)
		config.identity_key[index] = static_cast<std::uint8_t>(index);
	std::strcpy(config.test_run.data(), "native-unit-fixture");
	CHECK(telemetry_posthog_reducer_init(config));
	CONFIG = configuration();
	if (with_configuration)
		publish(CONFIG);
}

void life(telemetry_lifecycle_kind kind, std::uint32_t subject = 44U, bool expected = true,
	  const telemetry_dimensions &captured = dimensions())
{
	telemetry_record record{};
	record.header.kind = telemetry_record_kind::session_lifecycle;
	auto &value = record.payload.lifecycle;
	value.session = session(subject);
	value.connection = { PRODUCER,
			     kind == telemetry_lifecycle_kind::connection_attached ? 99U : 88U };
	value.lifecycle = kind;
	value.end_reason = kind == telemetry_lifecycle_kind::session_exited ?
				   telemetry_session_end_reason::logout :
				   telemetry_session_end_reason::unknown;
	const auto offset = kind == telemetry_lifecycle_kind::session_entered ? 0U : 45'000'000U;
	value.at_monotonic_usec = MONO + offset;
	value.at_utc_usec = BASE + offset;
	value.dimensions = captured;
	value.config_id = CONFIG.config_id;
	value.classifier_version = 1U;
	value.policy_version = 1U;
	emit(record, expected);
}

telemetry_record
interval(std::uint64_t begin, std::uint64_t end,
	 telemetry_interval_category category = telemetry_interval_category::connected_active,
	 std::int32_t zone = 10, std::uint32_t subject = 44U)
{
	telemetry_record record{};
	record.header.kind = telemetry_record_kind::interval;
	auto &value = record.payload.interval;
	value.session = session(subject);
	if (category != telemetry_interval_category::resident_linkdead)
		value.connection = { PRODUCER, 88U };
	value.window = { MONO + begin, MONO + end, BASE + static_cast<std::int64_t>(begin),
			 BASE + static_cast<std::int64_t>(end) };
	value.duration_usec = end - begin;
	value.category = category;
	value.context = telemetry_activity_context::combat;
	value.context_quality = telemetry_context_quality::observed;
	value.dimensions = dimensions(zone);
	value.config_id = CONFIG.config_id;
	value.classifier_version = 1U;
	value.policy_version = 1U;
	return record;
}

telemetry_record xp(std::int64_t requested, std::int64_t computed, std::int64_t applied,
		    std::uint32_t subject = 44U, std::uint16_t level = 12U)
{
	telemetry_record record{};
	record.header.kind = telemetry_record_kind::progression;
	auto &value = record.payload.progression;
	value.session = session(subject);
	value.connection = { PRODUCER, 88U };
	value.at_monotonic_usec = MONO + 40'000'000U;
	value.at_utc_usec = BASE + 40'000'000;
	value.kind = telemetry_progression_kind::experience_observed;
	value.source = telemetry_progression_source::kill;
	value.reason = telemetry_progression_reason::earned;
	value.observation_status = telemetry_progression_observation_status::observed_mutable;
	value.requested_xp = requested;
	value.computed_xp = computed;
	value.applied_xp = applied;
	value.before_exp = 0;
	value.after_exp = applied;
	value.before_level = level;
	value.after_level = level;
	value.dimensions = dimensions();
	value.config_id = CONFIG.config_id;
	value.classifier_version = 1U;
	value.policy_version = 1U;
	return record;
}

void checkpoint(telemetry_cumulative_counters totals, std::uint64_t revision = 1U,
		bool expected = true)
{
	telemetry_record record{};
	record.header.kind = telemetry_record_kind::session_checkpoint;
	auto &value = record.payload.checkpoint;
	value.session = session();
	value.connection = { PRODUCER, 88U };
	value.revision = revision;
	value.at_monotonic_usec = MONO + 42'000'000U;
	value.at_utc_usec = BASE + 42'000'000;
	value.cumulative = totals;
	value.config_id = CONFIG.config_id;
	emit(record, expected);
}

void finish()
{
	telemetry_posthog_seal_through(NOW, BASE + 60'000'000, true);
	const auto health = telemetry_posthog_reducer_health_copy();
	for (std::size_t index = 0U; index < health.output_events; ++index)
	{
		const auto output = telemetry_posthog_output_peek(index);
		CHECK(!output.json.empty());
		CHECK(output.json.size() <= TELEMETRY_POSTHOG_MAX_EVENT_BYTES);
		CHECK(!output.health);
		std::fwrite(output.json.data(), 1U, output.json.size(), stdout);
		std::putchar('\n');
	}
	CHECK(telemetry_posthog_output_peek(health.output_events).json.empty());
	cJSON *object = cJSON_CreateObject();
	cJSON *values = cJSON_AddObjectToObject(object, "_fixture_health");
#define HEALTH(name) cJSON_AddNumberToObject(values, #name, static_cast<double>(health.name))
	HEALTH(invalid_records);
	HEALTH(reduction_refusals);
	HEALTH(input_sequence_gaps);
	HEALTH(unsupported_records);
	HEALTH(session_refusals);
	HEALTH(abandoned_sessions);
	HEALTH(configuration_refusals);
	HEALTH(missing_configuration_rows);
	HEALTH(counter_overflow_rows);
	HEALTH(checkpoint_conflicts);
	HEALTH(stale_checkpoints);
	HEALTH(native_gaps);
	HEALTH(native_dropped_records);
	HEALTH(native_gap_known_usec);
	HEALTH(unattributed_time_fragments);
	HEALTH(xp_attribution_overflows);
	HEALTH(created_events);
	HEALTH(output_suppressed);
	HEALTH(output_expired);
	HEALTH(serialization_failures);
	HEALTH(clock_failures);
	HEALTH(http_acknowledged);
	HEALTH(ambiguous_events);
	HEALTH(sessions);
	HEALTH(configurations);
	HEALTH(output_events);
	HEALTH(output_bytes);
#undef HEALTH
	char *encoded = cJSON_PrintUnformatted(object);
	CHECK(encoded != nullptr);
	std::puts(encoded);
	cJSON_free(encoded);
	cJSON_Delete(object);
}
} // namespace

int telemetry_posthog_reducer_scenario(std::string_view name)
{
	initialize(name != "config-capacity" && name != "initial-gap" &&
		   name != "config-allocation-failure");
	if (name == "conservation")
	{
		life(telemetry_lifecycle_kind::session_entered);
		emit(interval(0U, 20'000'000U));
		emit(interval(20'000'000U, 30'000'000U, telemetry_interval_category::connected_idle,
			      11));
		emit(interval(30'000'000U, 35'000'000U, telemetry_interval_category::unknown, 12));
		emit(interval(35'000'000U, 42'000'000U,
			      telemetry_interval_category::resident_linkdead, 13));
		emit(xp(100, 150, 120));
		emit(xp(20, 0, 0));
		auto negative = xp(-20, -10, -10);
		negative.payload.progression.source = telemetry_progression_source::death;
		negative.payload.progression.reason = telemetry_progression_reason::death_loss;
		emit(negative);
		checkpoint({ 37'000'000U, 22'000'000U, 10'000'000U, 5'000'000U, 44'000'000U,
			     7'000'000U });
		auto level = xp(0, 0, 0);
		level.payload.progression.kind = telemetry_progression_kind::level_advanced;
		level.payload.progression.after_level = 13U;
		level.payload.progression.reason = telemetry_progression_reason::level_threshold;
		level.payload.progression.threshold_xp = 9'223'372'036'854'775'809ULL;
		emit(level);
		emit(xp(5, 5, 5, 44U, 13U));
		life(telemetry_lifecycle_kind::connection_detached);
		life(telemetry_lifecycle_kind::connection_attached);
		life(telemetry_lifecycle_kind::session_exited);
	}
	else if (name == "boundaries")
	{
		emit(interval(899'500'000U, 900'500'000U));
		telemetry_posthog_seal_through(NOW, BASE + 901'000'000);
		const auto saved = std::string(telemetry_posthog_output_peek(1U).json);
		emit(interval(899'000'000U, 899'500'000U));
		CHECK(saved == telemetry_posthog_output_peek(1U).json);
		auto experience = xp(1, 1, 1);
		experience.header = { TELEMETRY_SCHEMA_VERSION,
				      telemetry_record_kind::progression,
				      0U,
				      { PRODUCER, ++SEQUENCE },
				      BASE };
		experience.payload.progression.at_utc_usec = BASE + 899'000'000;
		CHECK(telemetry_posthog_consume(experience, NOW, BASE + 901'000'000));
		CHECK(!telemetry_posthog_consume(experience, NOW, BASE + 901'000'000));
	}
	else if (name == "midnight")
		emit(interval(86'398'000'000U, 86'402'000'000U));
	else if (name == "unknown-utc")
	{
		auto record = interval(0U, 1000U);
		record.payload.interval.window.end_utc_usec += 500;
		emit(record);
		auto experience = xp(2, 2, 2);
		experience.payload.progression.at_utc_usec = TELEMETRY_UTC_UNKNOWN;
		emit(experience);
	}
	else if (name == "missing-clock")
	{
		auto record = interval(0U, 1000U);
		record.payload.interval.window.start_utc_usec = TELEMETRY_UTC_UNKNOWN;
		record.payload.interval.window.end_utc_usec = TELEMETRY_UTC_UNKNOWN;
		emit(record);
		telemetry_posthog_seal_through(NOW, TELEMETRY_UTC_UNKNOWN, true);
	}
	else if (name == "buckets" || name == "byte-capacity")
	{
		const std::uint32_t count = name == "buckets" ? 1U : 32U;
		for (std::uint32_t subject = 44U; subject < 44U + count; ++subject)
		{
			for (std::uint32_t index = 0U; index < 34U; ++index)
			{
				emit(interval(index, index + 1U,
					      telemetry_interval_category::connected_active,
					      static_cast<std::int32_t>(index), subject));
				auto experience = xp(10'000'000'000'000'000LL,
						     10'000'000'000'000'000LL, 0, subject);
				experience.payload.progression.modifier_flags = index;
				emit(experience);
			}
			if (name == "byte-capacity")
				telemetry_posthog_seal_through(NOW, BASE + 60'000'000, true);
		}
		if (name == "byte-capacity")
		{
			const auto health = telemetry_posthog_reducer_health_copy();
			CHECK(health.output_events < TELEMETRY_POSTHOG_MAX_EVENTS);
			CHECK(health.output_suppressed > 0U);
			const auto half = health.output_events / 2U;
			const auto saved = std::string(telemetry_posthog_output_peek(half).json);
			CHECK(telemetry_posthog_output_retire(
				half, telemetry_posthog_output_disposition::http_acknowledged));
			CHECK(saved == telemetry_posthog_output_peek().json);
			life(telemetry_lifecycle_kind::connection_attached);
			CHECK(saved == telemetry_posthog_output_peek().json);
		}
	}
	else if (name == "bucket-overflow")
	{
		const auto maximum = std::numeric_limits<std::int64_t>::max();
		emit(xp(maximum, maximum, maximum));
		auto loss = xp(-maximum, -maximum, -maximum);
		loss.payload.progression.source = telemetry_progression_source::death;
		loss.payload.progression.reason = telemetry_progression_reason::death_loss;
		emit(loss);
		emit(xp(maximum, maximum, maximum));
	}
	else if (name == "integer-overflow")
	{
		const auto maximum = std::numeric_limits<std::int64_t>::max();
		const auto minimum = std::numeric_limits<std::int64_t>::min();
		emit(xp(maximum, maximum, maximum));
		emit(xp(1, 1, 1));
		emit(xp(minimum, minimum, minimum, 45U));
		emit(xp(-1, -1, -1, 45U));
		auto record =
			interval(0U, 1U, telemetry_interval_category::connected_active, 10, 46U);
		record.payload.interval.window = { 0U, std::numeric_limits<std::uint64_t>::max(),
						   TELEMETRY_UTC_UNKNOWN, TELEMETRY_UTC_UNKNOWN };
		record.payload.interval.duration_usec = std::numeric_limits<std::uint64_t>::max();
		emit(record);
		auto extra =
			interval(0U, 1U, telemetry_interval_category::connected_active, 10, 46U);
		extra.payload.interval.window.start_utc_usec = TELEMETRY_UTC_UNKNOWN;
		extra.payload.interval.window.end_utc_usec = TELEMETRY_UTC_UNKNOWN;
		emit(extra);
	}
	else if (name == "sessions")
	{
		for (std::uint32_t subject = 1U; subject <= 256U; ++subject)
			emit(xp(1, 1, 1, subject));
		emit(xp(1, 1, 1, 257U), false);
		telemetry_posthog_seal_through(NOW, BASE + 60'000'000, true);
		CHECK(telemetry_posthog_reducer_health_copy().output_events == 128U);
		CHECK(telemetry_posthog_reducer_health_copy().output_suppressed == 129U);
		CHECK(!telemetry_posthog_output_retire(
			129U, telemetry_posthog_output_disposition::http_acknowledged));
		CHECK(telemetry_posthog_output_retire(
			128U, telemetry_posthog_output_disposition::http_acknowledged));
		life(telemetry_lifecycle_kind::session_exited, 1U);
		emit(xp(1, 1, 1, 257U));
	}
	else if (name == "config-capacity")
	{
		for (std::uint32_t version = 1U; version <= 64U; ++version)
			publish(configuration(version));
		publish(configuration(65U), false);
		publish(configuration(1U));
		auto bad = configuration(1U);
		bad.fingerprint[0] ^= 0xFFU;
		publish(bad, false);
	}
	else if (name == "checkpoint")
	{
		/* No entry in this process: copyover/reconnect can carry older totals. */
		SESSION_PRODUCER = { 7U, 8U };
		life(telemetry_lifecycle_kind::connection_attached);
		emit(interval(0U, 1000U));
		checkpoint({ 2000U, 2000U, 0U, 0U, 2000U, 0U }, 2U);
		checkpoint({ 2000U, 2000U, 0U, 0U, 2000U, 0U }, 1U);
		checkpoint({ 3000U, 3000U, 0U, 0U, 3000U, 0U }, 2U, false);
		checkpoint({ 1000U, 1000U, 0U, 0U, 1000U, 0U }, 3U, false);
	}
	else if (name == "checkpoint-late-detail")
	{
		life(telemetry_lifecycle_kind::session_entered);
		checkpoint({ 1000U, 1000U, 0U, 0U, 1000U, 0U });
		emit(interval(0U, 1000U));
	}
	else if (name == "dimension-unknown")
	{
		emit(interval(0U, 1U));
		emit(xp(1, 1, 1));
		for (std::uint32_t index = 1U; index < 10U; ++index)
		{
			auto unknown = interval(index * 2U, index * 2U + 1U);
			unknown.payload.interval.dimensions = { 0U, 0U, 0U, 0U, -1, 0U };
			unknown.payload.interval.context =
				telemetry_activity_context::overflow_unknown;
			unknown.payload.interval.context_quality =
				telemetry_context_quality::overflow;
			unknown.payload.interval.quality_flags =
				TELEMETRY_QUALITY_CONTEXT_OVERFLOW |
				TELEMETRY_QUALITY_DIMENSION_UNKNOWN;
			emit(unknown);
			emit(interval(index * 2U + 1U, index * 2U + 2U));
		}
	}
	else if (name == "level-config")
	{
		emit(xp(1, 1, 1));
		emit(xp(2, 2, 2, 44U, 13U)); // Same level band; the level fact may be missing.
		CONFIG = configuration(2U);
		publish(CONFIG);
		emit(xp(3, 3, 3, 44U, 13U));
		auto changed = xp(4, 4, 4, 44U, 13U);
		changed.payload.progression.dimensions.class_id = 6U;
		emit(changed);
	}
	else if (name == "gap-scope")
	{
		emit(interval(0U, 1U));
		auto bad = xp(1, 1, 1);
		bad.payload.progression.session.environment_id = 1001U;
		emit(bad, false);
		telemetry_record gap{};
		gap.header.kind = telemetry_record_kind::coverage_gap;
		gap.payload.gap.reason = telemetry_gap_reason::detail_queue_drop;
		gap.payload.gap.dropped_records = 2U;
		gap.payload.gap.quality_flags = TELEMETRY_QUALITY_QUEUE_DROP;
		emit(gap);
		++SEQUENCE;
		emit(xp(1, 1, 1));
	}
	else if (name == "long-interval")
		emit(interval(0U, 900'000'000ULL * 1'000'000U));
	else if (name == "config-output-pressure" || name == "config-byte-pressure")
	{
		if (name == "config-output-pressure")
			while (telemetry_posthog_reducer_health_copy().output_events < 128U)
				life(telemetry_lifecycle_kind::connection_attached);
		else
			for (std::uint32_t subject = 44U; subject < 76U; ++subject)
			{
				for (std::uint32_t index = 0U; index < 32U; ++index)
				{
					emit(interval(index, index + 1U,
						      telemetry_interval_category::connected_active,
						      static_cast<std::int32_t>(index), subject));
					auto experience = xp(10, 10, 10, subject);
					experience.payload.progression.modifier_flags = index;
					emit(experience);
				}
				telemetry_posthog_seal_through(NOW, BASE + 60'000'000, true);
			}
		std::uint32_t retained = 0U;
		for (std::uint32_t version = 2U; version <= 64U; ++version)
		{
			const auto before = telemetry_posthog_reducer_health_copy();
			CONFIG = configuration(version);
			publish(CONFIG);
			const auto after = telemetry_posthog_reducer_health_copy();
			if (after.output_events == before.output_events)
			{
				CHECK(after.configurations == before.configurations);
				retained = after.output_events;
				break;
			}
		}
		CHECK(retained > 0U);
		CHECK(name != "config-byte-pressure" || retained < 128U);
		CHECK(telemetry_posthog_output_retire(
			retained, telemetry_posthog_output_disposition::http_acknowledged));
		life(telemetry_lifecycle_kind::connection_attached);
		publish(CONFIG);
		emit(xp(1, 1, 1));
	}
	else if (name == "config-allocation-failure")
	{
		cJSON_Hooks hooks{};
		hooks.malloc_fn = [](std::size_t bytes) -> void *
		{
			if (ALLOCATION_BUDGET == 0U)
				return nullptr;
			--ALLOCATION_BUDGET;
			return std::malloc(bytes);
		};
		hooks.free_fn = std::free;
		for (const auto budget : { 0U, 4U, 24U, 64U })
		{
			ALLOCATION_BUDGET = budget;
			cJSON_InitHooks(&hooks);
			publish(CONFIG);
			cJSON_InitHooks(nullptr);
			CHECK(telemetry_posthog_reducer_health_copy().configurations == 0U);
		}
		life(telemetry_lifecycle_kind::connection_attached);
		publish(CONFIG);
		emit(xp(1, 1, 1));
	}
	else if (name == "sealed-force" || name == "sealed-age" || name == "sealed-config" ||
		 name == "sealed-dimensions" || name == "sealed-level" || name == "sealed-eviction")
	{
		emit(xp(1, 1, 1));
		if (name == "sealed-force")
			telemetry_posthog_seal_through(NOW, BASE + 60'000'000, true);
		else if (name == "sealed-age")
		{
			NOW += 900'000'000U;
			telemetry_posthog_seal_through(NOW, BASE + 60'000'000);
		}
		else if (name == "sealed-config")
		{
			CONFIG = configuration(2U);
			publish(CONFIG);
			emit(xp(2, 2, 2));
		}
		else if (name == "sealed-dimensions")
		{
			auto changed = xp(2, 2, 2);
			changed.payload.progression.dimensions.class_id = 6U;
			emit(changed);
		}
		else if (name == "sealed-level")
			emit(xp(2, 2, 2, 44U, 13U));
		else
		{
			emit(interval(900'000'000U, 900'000'001U));
			emit(interval(1'800'000'000U, 1'800'000'001U));
		}
		const auto saved = std::string(telemetry_posthog_output_peek(1U).json);
		CHECK(!saved.empty());
		emit(interval(0U, 1U));
		CHECK(saved == telemetry_posthog_output_peek(1U).json);
	}
	else if (name == "initial-gap")
	{
		SEQUENCE = 2U;
		publish(CONFIG);
		emit(xp(1, 1, 1));
	}
	else if (name == "unknown-xp-level")
	{
		emit(xp(1, 1, 1, 44U, 0U));
		emit(xp(2, 2, 2, 44U, 0U));
		emit(xp(3, 3, 3, 44U, 12U));
		emit(xp(4, 4, 4, 44U, 0U));
	}
	else if (name == "xp-dimensions")
	{
		emit(xp(1, 1, 1));
		auto changed = xp(2, 2, 2);
		changed.payload.progression.dimensions.zone_vnum = 11;
		emit(changed);
		changed = xp(3, 3, 3);
		changed.payload.progression.dimensions.zone_vnum = 11;
		changed.payload.progression.dimensions.group_size = 2U;
		emit(changed);
		emit(xp(4, 4, 4));
	}
	else if (name == "direct-unknown-dimensions")
	{
		for (std::uint32_t index = 0U; index < 4U; ++index)
		{
			auto captured = dimensions();
			if (index == 0U)
				captured.class_id = 0U;
			else if (index == 1U)
				captured.race_id = 0U;
			else if (index == 2U)
				captured.faction_id = 0U;
			else
				captured.level_band = 0U;
			life(telemetry_lifecycle_kind::connection_attached, 44U, true, captured);
			auto level = xp(0, 0, 0);
			level.payload.progression.kind = telemetry_progression_kind::level_advanced;
			level.payload.progression.after_level = 13U;
			level.payload.progression.reason =
				telemetry_progression_reason::level_threshold;
			level.payload.progression.dimensions = captured;
			emit(level);
		}
		auto flagged = xp(1, 1, 1);
		flagged.payload.progression.quality_flags = TELEMETRY_QUALITY_DIMENSION_UNKNOWN;
		emit(flagged);
	}
	else if (name == "expiry")
	{
		const auto first = telemetry_posthog_output_peek();
		telemetry_posthog_output_expire(first.sealed_at +
						TELEMETRY_POSTHOG_MAX_OUTPUT_AGE_USEC - 1U);
		CHECK(telemetry_posthog_reducer_health_copy().output_events == 1U);
		telemetry_posthog_output_expire(first.sealed_at +
						TELEMETRY_POSTHOG_MAX_OUTPUT_AGE_USEC);
		CHECK(telemetry_posthog_reducer_health_copy().output_events == 0U);
		life(telemetry_lifecycle_kind::session_entered);
		CHECK(telemetry_posthog_output_retire(
			1U, telemetry_posthog_output_disposition::ambiguous));
	}
	else if (name == "allocation-failure")
	{
		cJSON_Hooks hooks{};
		hooks.malloc_fn = [](std::size_t bytes) -> void *
		{
			if (ALLOCATION_BUDGET == 0U)
				return nullptr;
			--ALLOCATION_BUDGET;
			return std::malloc(bytes);
		};
		hooks.free_fn = std::free;
		for (const auto budget : { 0U, 4U, 24U, 64U })
		{
			ALLOCATION_BUDGET = budget;
			cJSON_InitHooks(&hooks);
			life(telemetry_lifecycle_kind::session_entered);
			cJSON_InitHooks(nullptr);
		}
		life(telemetry_lifecycle_kind::connection_attached);
	}
	else if (name == "output-suppression-coverage")
	{
		while (telemetry_posthog_reducer_health_copy().output_events < 128U)
			life(telemetry_lifecycle_kind::connection_attached);
		const auto saved = std::string(telemetry_posthog_output_peek().json);
		emit(xp(3, 3, 3));
		telemetry_posthog_seal_through(NOW, BASE + 60'000'000, true);
		CHECK(telemetry_posthog_reducer_health_copy().output_suppressed == 1U);
		CHECK(saved == telemetry_posthog_output_peek().json);
		CHECK(telemetry_posthog_output_retire(
			128U, telemetry_posthog_output_disposition::http_acknowledged));
		life(telemetry_lifecycle_kind::connection_attached, 45U);
		emit(xp(7, 7, 7));
	}
	else if (name == "unknown-transition-levels")
	{
		auto advanced = xp(0, 0, 0, 44U, 0U);
		advanced.payload.progression.kind = telemetry_progression_kind::level_advanced;
		advanced.payload.progression.reason = telemetry_progression_reason::level_threshold;
		advanced.payload.progression.after_level = 1U;
		emit(advanced);
		auto lost = xp(0, 0, 0, 44U, 1U);
		lost.payload.progression.kind = telemetry_progression_kind::level_lost;
		lost.payload.progression.reason = telemetry_progression_reason::death_loss;
		lost.payload.progression.after_level = 0U;
		emit(lost);
	}
	else if (name == "lost-exit")
	{
		life(telemetry_lifecycle_kind::session_entered);
		emit(interval(0U, 1U));
		NOW += 3'720'000'000ULL;
		telemetry_posthog_seal_through(NOW, BASE + 3'720'000'000LL);
		CHECK(telemetry_posthog_reducer_health_copy().sessions == 0U);
		emit(xp(1, 1, 1));
	}
	else if (name == "clock-flag")
	{
		auto record = xp(1, 1, 1);
		record.payload.progression.quality_flags = TELEMETRY_QUALITY_CLOCK_DISCONTINUITY;
		emit(record);
	}
	else if (name == "unimplemented-encounters")
	{
		telemetry_record record{};
		record.header.kind = telemetry_record_kind::encounter;
		auto &encounter = record.payload.encounter;
		encounter.encounter = { PRODUCER, 1U };
		encounter.kind = telemetry_encounter_event_kind::start;
		encounter.mode = telemetry_encounter_mode::pve;
		encounter.revision = 1U;
		encounter.source = { 1000U, 1U, CONFIG.config_id, 1U, 1U, 10, 44U };
		emit(record, false);
		record = {};
		record.header.kind = telemetry_record_kind::combat_summary;
		auto &combat = record.payload.combat_summary;
		combat.encounter = { PRODUCER, 1U };
		combat.source = { 1000U, 1U, CONFIG.config_id, 1U, 1U, 10, 44U };
		combat.mode = telemetry_encounter_mode::pve;
		combat.outcome = telemetry_encounter_outcome::success;
		combat.actor_kind = telemetry_combat_actor_kind::player;
		combat.revision = 1U;
		combat.actor_id = 44U;
		combat.actor_pid = 44;
		combat.owner_subject_id = 44U;
		emit(record, false);
	}
	else if (name == "initialization")
	{
		telemetry_posthog_reducer_config invalid{};
		CHECK(!telemetry_posthog_reducer_init(invalid));
		emit(xp(1, 1, 1), false);
	}
	else if (name == "missing-config")
	{
		auto record = xp(1, 1, 1);
		record.payload.progression.config_id = 999U;
		emit(record);
	}
	else
		return 2;
	finish();
	return 0;
}
