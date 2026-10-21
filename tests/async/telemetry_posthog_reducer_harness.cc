#include "telemetry/telemetry_posthog.h"
#include "telemetry/telemetry_config_private.h"
#include "telemetry/telemetry_encounter.h"
#include "telemetry/telemetry_combat_summary.h"

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
std::uint32_t DRAINED_EVENTS = 0U;

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
	DRAINED_EVENTS = 0U;
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

void limit_allocations(std::size_t budget)
{
	ALLOCATION_BUDGET = budget;
	cJSON_Hooks hooks{};
	hooks.malloc_fn = [](std::size_t bytes) -> void *
	{
		if (ALLOCATION_BUDGET == 0U)
			return nullptr;
		--ALLOCATION_BUDGET;
		return std::malloc(bytes);
	};
	hooks.free_fn = std::free;
	cJSON_InitHooks(&hooks);
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

telemetry_record
encounter(telemetry_encounter_event_kind kind, std::uint64_t run = 1U, std::uint32_t subject = 44U,
	  std::uint16_t count = 1U,
	  telemetry_encounter_outcome outcome = telemetry_encounter_outcome::success)
{
	telemetry_record record{};
	record.header.kind = telemetry_record_kind::encounter;
	auto &value = record.payload.encounter;
	value.encounter = { PRODUCER, run };
	value.kind = kind;
	value.mode = telemetry_encounter_mode::pve;
	value.outcome = kind == telemetry_encounter_event_kind::start ||
					kind == telemetry_encounter_event_kind::participant_join ?
				telemetry_encounter_outcome::unknown :
				outcome;
	value.revision = 1U;
	value.source = { 1000U, 1U, CONFIG.config_id, 1U, 1U, 10, 44U };
	value.start_monotonic_usec = MONO;
	value.start_utc_usec = BASE;
	value.at_monotonic_usec =
		kind == telemetry_encounter_event_kind::start ? MONO : MONO + 10'000'000U;
	value.at_utc_usec = kind == telemetry_encounter_event_kind::start ? BASE :
									    BASE + 10'000'000;
	value.participant_count = count;
	value.expected_credit_count = 9U; // Reward membership is not the roster denominator.
	if (kind == telemetry_encounter_event_kind::participant_summary ||
	    kind == telemetry_encounter_event_kind::participant_join ||
	    kind == telemetry_encounter_event_kind::participant_leave)
		value.participant = { subject, static_cast<telemetry_pid>(subject) };
	if (kind == telemetry_encounter_event_kind::close)
		value.elapsed_usec = 10'000'000U;
	if (kind == telemetry_encounter_event_kind::participant_summary ||
	    kind == telemetry_encounter_event_kind::participant_leave)
		value.participant_usec = 1'000'000U;
	return record;
}

telemetry_record combat(std::uint64_t run = 1U, std::uint16_t revision = 1U,
			telemetry_combat_actor_kind kind = telemetry_combat_actor_kind::player,
			std::uint64_t actor = 44U, std::uint64_t owner = 44U,
			std::uint16_t count = 1U)
{
	telemetry_record record{};
	record.header.kind = telemetry_record_kind::combat_summary;
	auto &value = record.payload.combat_summary;
	value.encounter = { PRODUCER, run };
	value.source = { 1000U, 1U, CONFIG.config_id, 1U, 1U, 10, 44U };
	value.mode = telemetry_encounter_mode::pve;
	value.outcome = telemetry_encounter_outcome::success;
	value.actor_kind = kind;
	value.revision = revision;
	value.actor_id = actor;
	value.actor_pid = kind == telemetry_combat_actor_kind::player ?
				  static_cast<telemetry_pid>(actor) :
				  TELEMETRY_UNKNOWN_PID;
	value.owner_subject_id = owner;
	value.unique_player_count = 1U;
	value.participant_count = count;
	value.power_band = 3U;
	value.opponent_power_band = 4U;
	value.opponent_count = 1U;
	value.start_monotonic_usec = MONO;
	value.end_monotonic_usec = MONO + 10'000'000U;
	value.start_utc_usec = BASE;
	value.end_utc_usec = BASE + 10'000'000;
	value.damage_dealt = 10U;
	value.control_applications = 5U; // Deliberately nonzero: export must still be null.
	return record;
}

void complete_encounter(std::uint64_t run, std::uint16_t players = 1U)
{
	emit(encounter(telemetry_encounter_event_kind::start, run));
	emit(encounter(telemetry_encounter_event_kind::close, run, 44U, players));
	for (std::uint16_t index = 0U; index < players; ++index)
		emit(encounter(telemetry_encounter_event_kind::participant_summary, run,
			       44U + index, players));
	for (std::uint16_t index = 0U; index < players; ++index)
		emit(combat(run, index + 1U, telemetry_combat_actor_kind::player, 44U + index,
			    44U + index, players));
}

void print_output()
{
	const auto health = telemetry_posthog_reducer_health_copy();
	for (std::size_t index = 0U; index < health.output_events; ++index)
	{
		const auto output = telemetry_posthog_output_peek(index);
		CHECK(!output.json.empty());
		CHECK(output.json.size() <= TELEMETRY_POSTHOG_MAX_EVENT_BYTES);
		CHECK(output.health == (output.json.find("\"event\":\"duris_telemetry_health\"") !=
					std::string_view::npos));
		std::fwrite(output.json.data(), 1U, output.json.size(), stdout);
		std::putchar('\n');
	}
	CHECK(telemetry_posthog_output_peek(health.output_events).json.empty());
}

void drain_output()
{
	print_output();
	const auto count = telemetry_posthog_reducer_health_copy().output_events;
	if (count != 0U)
	{
		CHECK(telemetry_posthog_output_retire(
			count, telemetry_posthog_output_disposition::http_acknowledged));
		DRAINED_EVENTS += count;
	}
}

void native_encounter()
{
	static telemetry_encounter_state roster{};
	static telemetry_combat_summary_state contributions{};
	telemetry_encounter_state_init(&roster);
	telemetry_combat_summary_state_init(&contributions);
	const auto fixture = encounter(telemetry_encounter_event_kind::start);
	const auto id = fixture.payload.encounter.encounter;
	const auto source = fixture.payload.encounter.source;
	const auto roster_sink = [](void *, const telemetry_encounter_event &value) noexcept
	{
		telemetry_record record{};
		record.header.kind = telemetry_record_kind::encounter;
		record.payload.encounter = value;
		emit(record);
		telemetry_posthog_seal_through(NOW, BASE + 60'000'000);
		return true;
	};
	const auto combat_sink = [](void *, const telemetry_combat_summary_payload &value) noexcept
	{
		telemetry_record record{};
		record.header.kind = telemetry_record_kind::combat_summary;
		record.payload.combat_summary = value;
		emit(record);
		telemetry_posthog_seal_through(NOW, BASE + 60'000'000);
		return true;
	};
	CHECK(telemetry_encounter_begin(&roster, id, source, telemetry_encounter_mode::pve,
					{ 44U, 44 }, MONO, BASE, roster_sink, nullptr)
		      .outcome == telemetry_encounter_update_outcome::accepted);
	CHECK(telemetry_encounter_join_group(&roster, source, { 45U, 45 }, MONO, BASE, roster_sink,
					     nullptr)
		      .outcome == telemetry_encounter_update_outcome::accepted);
	CHECK(telemetry_combat_summary_begin(&contributions, id, source,
					     telemetry_encounter_mode::pve, MONO, BASE)
		      .outcome == telemetry_combat_summary_outcome::accepted);
	CHECK(telemetry_encounter_begin(&roster, { PRODUCER, 2U }, source,
					telemetry_encounter_mode::pvp, { 45U, 45 }, MONO + 1U,
					BASE + 1, roster_sink, nullptr)
		      .outcome == telemetry_encounter_update_outcome::idempotent);
	const telemetry_combat_actor_ref player{ 44U, 44, 44U, telemetry_combat_actor_kind::player,
						 {},  3U };
	const telemetry_combat_actor_ref pet{ 99U, TELEMETRY_UNKNOWN_PID,
					      44U, telemetry_combat_actor_kind::pet,
					      {},  3U };
	const telemetry_combat_actor_ref npc{ 100U, TELEMETRY_UNKNOWN_PID,
					      0U,   telemetry_combat_actor_kind::npc,
					      {},   4U };
	for (const auto &actor : { player, pet, npc })
		CHECK(telemetry_combat_summary_add_actor(&contributions, id, actor, MONO).outcome ==
		      telemetry_combat_summary_outcome::accepted);
	CHECK(telemetry_combat_summary_record_damage(&contributions, player, npc, 11U, MONO + 1U,
						     0U)
		      .outcome == telemetry_combat_summary_outcome::accepted);
	CHECK(telemetry_combat_summary_record_damage(&contributions, pet, npc, 7U, MONO + 2U,
						     TELEMETRY_COMBAT_MODIFIER_PET)
		      .outcome == telemetry_combat_summary_outcome::accepted);
	CHECK(telemetry_combat_summary_record_healing(&contributions, player, player, 20U, 12U,
						      MONO + 3U, 0U)
		      .outcome == telemetry_combat_summary_outcome::accepted);
	CHECK(telemetry_combat_summary_cast_attempt(&contributions, player, 1, MONO + 4U, 0U)
		      .outcome == telemetry_combat_summary_outcome::accepted);
	CHECK(telemetry_combat_summary_cast_complete(&contributions, player, MONO + 9U).outcome ==
	      telemetry_combat_summary_outcome::accepted);
	CHECK(telemetry_combat_summary_record_tanking(&contributions, player, &npc, MONO + 5U, 0U)
		      .outcome == telemetry_combat_summary_outcome::accepted);
	CHECK(telemetry_encounter_leave(&roster, { 44U, 44 },
					telemetry_encounter_outcome::withdrawal, MONO + 5'000'000U,
					BASE + 5'000'000, roster_sink, nullptr)
		      .outcome == telemetry_encounter_update_outcome::accepted);
	CHECK(telemetry_encounter_close(&roster, id, telemetry_encounter_outcome::success, 9U,
					MONO + 10'000'000U, BASE + 10'000'000, roster_sink, nullptr)
		      .outcome == telemetry_encounter_update_outcome::accepted);
	CHECK(telemetry_posthog_reducer_health_copy().output_events ==
	      1U); // Close + complete roster are insufficient.
	CHECK(telemetry_combat_summary_close(
		      &contributions, id, telemetry_encounter_outcome::success, MONO + 10'000'000U,
		      BASE + 10'000'000, combat_sink, nullptr)
		      .rows_accepted == 3U);
	CHECK(telemetry_posthog_reducer_health_copy().runs == 0U);
}

telemetry_health_snapshot native_health()
{
	telemetry_health_snapshot health{};
	health.schema_version = TELEMETRY_SCHEMA_VERSION;
	health.producer = PRODUCER;
	health.state = telemetry_health_state::healthy;
	health.backend = telemetry_storage_backend::sql;
	health.queue_capacity = TELEMETRY_QUEUE_CAPACITY_PROPOSAL;
	return health;
}

void observe(const telemetry_health_snapshot &health, bool expected = true,
	     telemetry_utc_usec utc = BASE + 60'000'000)
{
	CHECK(telemetry_posthog_observe_health(health, NOW, utc) == expected);
}

void finish()
{
	telemetry_posthog_seal_through(NOW, BASE + 60'000'000, true);
	print_output();
	const auto health = telemetry_posthog_reducer_health_copy();
	cJSON *object = cJSON_CreateObject();
	cJSON *values = cJSON_AddObjectToObject(object, "_fixture_health");
	cJSON_AddNumberToObject(values, "drained_events", DRAINED_EVENTS);
#define HEALTH(name) cJSON_AddNumberToObject(values, #name, static_cast<double>(health.name))
	HEALTH(invalid_records);
	HEALTH(invalid_health_snapshots);
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
	HEALTH(native_scoped_gaps);
	HEALTH(native_process_gaps);
	HEALTH(native_dropped_records);
	HEALTH(native_gap_known_usec);
	HEALTH(unattributed_time_fragments);
	HEALTH(xp_attribution_overflows);
	HEALTH(run_refusals);
	HEALTH(terminal_duplicates);
	HEALTH(terminal_conflicts);
	HEALTH(late_encounter_records);
	HEALTH(incomplete_runs);
	HEALTH(unsupported_npc_rows);
	HEALTH(actor_attribution_overflows);
	HEALTH(created_events);
	HEALTH(output_suppressed);
	HEALTH(output_expired);
	HEALTH(serialization_failures);
	HEALTH(clock_failures);
	HEALTH(http_acknowledged);
	HEALTH(ambiguous_events);
	HEALTH(sessions);
	HEALTH(configurations);
	HEALTH(runs);
	HEALTH(output_events);
	HEALTH(output_bytes);
#undef HEALTH
	auto *families = cJSON_AddArrayToObject(values, "by_family");
	for (const auto &family : health.by_family)
	{
		auto *item = cJSON_CreateObject();
		CHECK(cJSON_AddItemToArray(families, item));
		cJSON_AddNumberToObject(item, "created", static_cast<double>(family.created));
		cJSON_AddNumberToObject(item, "suppressed", static_cast<double>(family.suppressed));
		cJSON_AddNumberToObject(item, "expired", static_cast<double>(family.expired));
		cJSON_AddNumberToObject(item, "http_acknowledged",
					static_cast<double>(family.http_acknowledged));
		cJSON_AddNumberToObject(item, "ambiguous", static_cast<double>(family.ambiguous));
	}
	auto *kinds = cJSON_AddArrayToObject(values, "refused_by_kind");
	for (const auto count : health.refused_by_kind)
		CHECK(cJSON_AddItemToArray(kinds, cJSON_CreateNumber(static_cast<double>(count))));
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
		for (const auto budget : { 0U, 4U, 24U, 64U })
		{
			limit_allocations(budget);
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
	else if (name == "encounter-native")
		native_encounter();
	else if (name == "encounter-allocation-failure")
	{
		std::uint64_t run = 0U;
		for (const auto budget : { 0U, 4U, 24U, 64U })
		{
			complete_encounter(++run);
			limit_allocations(budget);
			telemetry_posthog_seal_through(NOW, BASE + 60'000'000);
			cJSON_InitHooks(nullptr);
		}
	}
	else if (name == "encounter-missing")
	{
		emit(encounter(telemetry_encounter_event_kind::start));
		emit(encounter(telemetry_encounter_event_kind::close));
		const auto closed_at = NOW;
		emit(encounter(telemetry_encounter_event_kind::participant_summary));
		NOW = closed_at + TELEMETRY_POSTHOG_MAX_OUTPUT_AGE_USEC - 1U;
		telemetry_posthog_seal_through(NOW, BASE + 120'000'000);
		CHECK(telemetry_posthog_reducer_health_copy().output_events == 1U);
		++NOW;
		telemetry_posthog_seal_through(NOW, BASE + 120'000'000);
		CHECK(telemetry_posthog_reducer_health_copy().runs == 0U);
		emit(combat(), false); // No second run after a partial terminal was sealed.
	}
	else if (name == "encounter-orphan")
	{
		emit(combat()); // Lost start, close and roster: preserve what was captured.
		telemetry_posthog_seal_through(NOW, BASE + 60'000'000);
		CHECK(telemetry_posthog_reducer_health_copy().output_events == 1U);
	}
	else if (name == "encounter-open")
	{
		emit(encounter(telemetry_encounter_event_kind::start));
		auto leave =
			encounter(telemetry_encounter_event_kind::participant_leave, 1U, 44U, 2U);
		emit(leave);
		emit(leave); // Cumulative observations are not additive.
		NOW += 7'200'000'000ULL;
		telemetry_posthog_seal_through(NOW, BASE + 7'200'000'000LL);
		CHECK(telemetry_posthog_reducer_health_copy().runs ==
		      1U); // Silence does not prove run closure.
	}
	else if (name == "encounter-conflict")
	{
		emit(encounter(telemetry_encounter_event_kind::start));
		emit(encounter(telemetry_encounter_event_kind::close));
		emit(encounter(telemetry_encounter_event_kind::close));
		emit(encounter(telemetry_encounter_event_kind::participant_summary));
		emit(encounter(telemetry_encounter_event_kind::participant_summary));
		auto first = combat(1U, 1U, telemetry_combat_actor_kind::player, 44U, 44U, 2U);
		emit(first);
		emit(first);
		auto pet = combat(1U, 2U, telemetry_combat_actor_kind::pet, 99U, 44U, 2U);
		auto conflicting = pet;
		++conflicting.payload.combat_summary.end_monotonic_usec;
		emit(conflicting, false);
		emit(pet);
	}
	else if (name == "encounter-overflow" || name == "encounter-counter-overflow")
	{
		emit(encounter(telemetry_encounter_event_kind::start));
		emit(encounter(telemetry_encounter_event_kind::close, 1U, 44U, 64U));
		for (std::uint32_t subject = 44U; subject < 108U; ++subject)
			emit(encounter(telemetry_encounter_event_kind::participant_summary, 1U,
				       subject, 64U));
		const std::uint16_t count = name == "encounter-overflow" ? 64U : 2U;
		for (std::uint16_t index = 0U; index < count; ++index)
		{
			auto row = combat(1U, index + 1U, telemetry_combat_actor_kind::pet,
					  1000U + index, 44U, count);
			if (name == "encounter-counter-overflow")
				row.payload.combat_summary.damage_dealt =
					std::numeric_limits<std::uint64_t>::max();
			emit(row);
		}
	}
	else if (name == "encounter-burst")
	{
		for (std::uint64_t run = 1U; run <= 8U; ++run)
			complete_encounter(run, 17U);
		telemetry_posthog_seal_through(NOW, BASE + 60'000'000);
		CHECK(telemetry_posthog_reducer_health_copy().runs != 0U);
		CHECK(telemetry_posthog_reducer_health_copy().output_suppressed == 0U);
		const std::string first(telemetry_posthog_output_peek().json);
		telemetry_posthog_seal_through(NOW, BASE + 60'000'000);
		CHECK(first == telemetry_posthog_output_peek().json);
		drain_output();
		telemetry_posthog_seal_through(NOW, BASE + 60'000'000);
		CHECK(telemetry_posthog_reducer_health_copy().runs == 0U);
	}
	else if (name == "encounter-replay")
	{
		emit(encounter(telemetry_encounter_event_kind::start, 1U));
		for (std::uint64_t run = 2U; run <= 131U; ++run)
		{
			complete_encounter(run);
			telemetry_posthog_seal_through(NOW, BASE + 60'000'000);
			drain_output();
		}
		CHECK(telemetry_posthog_reducer_health_copy().runs == 1U);
		emit(encounter(telemetry_encounter_event_kind::close, 2U), false);
		emit(encounter(telemetry_encounter_event_kind::close,
			       1U)); // Active older run survives retired-prefix compaction.
		emit(encounter(telemetry_encounter_event_kind::participant_summary, 1U));
		emit(combat(1U));
		telemetry_posthog_seal_through(NOW, BASE + 60'000'000);
		emit(combat(1U), false);
	}
	else if (name == "encounter-expiry")
	{
		for (std::uint32_t index = 0U; index < 127U; ++index)
			life(telemetry_lifecycle_kind::connection_attached);
		CHECK(telemetry_posthog_reducer_health_copy().output_events == 128U);
		for (std::uint64_t run = 1U; run <= 3U; ++run)
			complete_encounter(run);
		telemetry_posthog_seal_through(NOW, BASE + 60'000'000);
		CHECK(telemetry_posthog_reducer_health_copy().runs == 3U);
		const std::string first(telemetry_posthog_output_peek().json);
		NOW += TELEMETRY_POSTHOG_MAX_OUTPUT_AGE_USEC;
		telemetry_posthog_seal_through(NOW, BASE + 120'000'000);
		CHECK(telemetry_posthog_reducer_health_copy().runs == 0U);
		CHECK(first == telemetry_posthog_output_peek().json);
	}
	else if (name == "encounter-capacity")
	{
		for (std::uint64_t run = 1U; run <= 128U; ++run)
			emit(encounter(telemetry_encounter_event_kind::start, run));
		emit(encounter(telemetry_encounter_event_kind::start, 129U), false);
		CHECK(telemetry_posthog_reducer_health_copy().runs == 128U);
	}
	else if (name == "encounter-scope-clock")
	{
		auto bad = combat();
		bad.payload.combat_summary.source.environment_id = 1U;
		emit(bad, false);
		bad = combat();
		bad.payload.combat_summary.encounter.producer.boot_id = 99U;
		emit(bad, false);
		auto start = encounter(telemetry_encounter_event_kind::start);
		auto close = encounter(telemetry_encounter_event_kind::close);
		auto participant = encounter(telemetry_encounter_event_kind::participant_summary);
		for (auto *record : { &start, &close, &participant })
		{
			record->payload.encounter.quality_flags |=
				TELEMETRY_QUALITY_CLOCK_DISCONTINUITY;
			emit(*record);
		}
		emit(combat());
	}
	else if (name == "health-cadence")
	{
		const auto health = native_health();
		NOW = MONO;
		observe(health);
		drain_output();
		NOW += TELEMETRY_POSTHOG_HEALTH_INTERVAL_USEC - 1U;
		observe(health, false);
		++NOW;
		observe(health);
		observe(health, false);
	}
	else if (name == "health-incidents")
	{
		auto health = native_health();
		NOW = MONO;
		observe(health);
		NOW += 1U;
		health.state = telemetry_health_state::degraded;
		health.last_failure_class = telemetry_failure_class::transient_connection;
		health.last_failure_monotonic_usec = NOW;
		health.last_error_code = 123U;
		observe(health, false);
		NOW += 1U;
		health.state = telemetry_health_state::healthy;
		health.last_success_monotonic_usec = NOW;
		observe(health, false);
		NOW = MONO + TELEMETRY_POSTHOG_HEALTH_COALESCE_USEC;
		observe(health);
		NOW += TELEMETRY_POSTHOG_HEALTH_COALESCE_USEC;
		observe(health, false);
	}
	else if (name == "health-loss")
	{
		auto health = native_health();
		health.applied_records = 9'007'199'254'740'993ULL;
		health.admitted_detail = health.applied_records;
		health.last_admitted_record_seq = std::numeric_limits<std::uint64_t>::max();
		health.last_committed_record_seq = health.last_admitted_record_seq;
		NOW = MONO;
		observe(health);
		emit(xp(1, 1, 1));
		auto refused = xp(1, 1, 1);
		refused.payload.progression.session.environment_id = 1U;
		emit(refused, false);
		telemetry_record gap{};
		gap.header.kind = telemetry_record_kind::coverage_gap;
		gap.payload.gap.reason = telemetry_gap_reason::detail_queue_drop;
		gap.payload.gap.dropped_records = 3U;
		gap.payload.gap.quality_flags = TELEMETRY_QUALITY_QUEUE_DROP;
		emit(gap);
		gap.payload.gap.session = session();
		emit(gap);
		NOW = MONO + TELEMETRY_POSTHOG_HEALTH_COALESCE_USEC;
		observe(health);
	}
	else if (name == "health-capacity")
	{
		for (std::uint32_t index = 0U; index < 127U; ++index)
			life(telemetry_lifecycle_kind::connection_attached);
		const auto health = native_health();
		NOW = MONO;
		observe(health, false);
		observe(health, false);
		CHECK(telemetry_posthog_reducer_health_copy().output_suppressed == 1U);
		CHECK(telemetry_posthog_output_retire(
			1U, telemetry_posthog_output_disposition::suppressed));
		NOW += TELEMETRY_POSTHOG_HEALTH_COALESCE_USEC;
		observe(health);
	}
	else if (name == "health-faults")
	{
		auto health = native_health();
		auto invalid = health;
		invalid.producer.boot_id = 99U;
		observe(invalid, false);
		invalid = health;
		++invalid.schema_version;
		observe(invalid, false);
		invalid = health;
		invalid.state = static_cast<telemetry_health_state>(255U);
		observe(invalid, false);
		NOW = 0U;
		observe(health, false);
		observe(health, false);
		NOW = MONO;
		limit_allocations(0U);
		observe(health, false);
		cJSON_InitHooks(nullptr);
		observe(health, false);
		NOW += TELEMETRY_POSTHOG_HEALTH_COALESCE_USEC;
		observe(health, false, TELEMETRY_UTC_UNKNOWN);
		NOW += TELEMETRY_POSTHOG_HEALTH_COALESCE_USEC;
		observe(health);
		--NOW;
		observe(health, false);
		observe(health, false);
		NOW += TELEMETRY_POSTHOG_HEALTH_COALESCE_USEC + 1U;
		observe(health);
	}
	else if (name == "health-family-expiry")
	{
		const auto health = native_health();
		NOW = MONO;
		observe(health);
		CHECK(telemetry_posthog_output_retire(
			1U, telemetry_posthog_output_disposition::http_acknowledged));
		CHECK(telemetry_posthog_output_peek().health);
		CHECK(telemetry_posthog_output_retire(
			1U, telemetry_posthog_output_disposition::ambiguous));
		NOW += TELEMETRY_POSTHOG_HEALTH_COALESCE_USEC;
		observe(health);
		NOW += TELEMETRY_POSTHOG_MAX_OUTPUT_AGE_USEC;
		telemetry_posthog_output_expire(NOW);
		observe(health);
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
