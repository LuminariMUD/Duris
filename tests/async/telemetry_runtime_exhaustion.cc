// Include the real runtime in this test translation unit to exhaust its private
// sequence allocator without adding a production test API or changing its ABI.
#include <openssl/rand.h>
static int entropy_mode = 0;
static unsigned entropy_calls = 0;
static int runtime_test_random(unsigned char *bytes, int count)
{
	++entropy_calls;
	if (entropy_mode == 1)
		return 0;
	if (entropy_mode == 2)
	{
		for (int index = 0; index < count; ++index)
			bytes[index] = 0;
		return 1;
	}
	return RAND_bytes(bytes, count);
}
#define RAND_bytes runtime_test_random
#include "telemetry/telemetry_runtime.c"
#undef RAND_bytes
#define main ordinary_runtime_test_main
#include "telemetry_runtime_integration.cc"
#undef main

#include <filesystem>

namespace
{
void check_posthog_byte_pressure()
{
	telemetry_transport_unbind_for_tests();
	auto transport = make_transport_config();
	transport.backend = telemetry_storage_backend::posthog;
	transport.fresh_producer = { 903U, 904U };
	assert(telemetry_transport_init(transport) == telemetry_transport_outcome::started);
	telemetry_transport_posthog_start_for_worker();
	telemetry_posthog_reducer_config reducer{};
	reducer.producer = transport.fresh_producer;
	reducer.environment_id = 1000U;
	reducer.season_id = 1U;
	reducer.identity_key.fill(1U);
	assert(telemetry_posthog_reducer_init(reducer));
	telemetry_record_sequence sequence = 0U;
	telemetry_monotonic_usec now = 1'000'000U;
	constexpr telemetry_utc_usec utc = 1'728'000'060'000'000LL;
	assert(telemetry_transport_posthog_pulse_for_worker(now, utc));
	assert(telemetry_transport_health_copy().last_success_monotonic_usec == 0U);
	const auto consume = [&](telemetry_record record)
	{
		now += 1000U;
		record.header = { TELEMETRY_SCHEMA_VERSION,
				  record.header.kind,
				  0U,
				  { transport.fresh_producer, ++sequence },
				  utc };
		assert(telemetry_record_is_valid(record));
		assert(telemetry_posthog_consume(record, now, utc));
	};
	telemetry_session_ref last_session{};
	for (std::uint32_t subject = 1U;
	     telemetry_posthog_reducer_health_copy().output_bytes <=
	     TELEMETRY_POSTHOG_MAX_OUTPUT_BYTES - 4U * TELEMETRY_POSTHOG_MAX_EVENT_BYTES;
	     ++subject)
	{
		assert(subject < 100U);
		last_session = { { transport.fresh_producer, subject },
				 subject,
				 static_cast<telemetry_pid>(subject),
				 1U,
				 1000U };
		for (std::uint32_t bucket = 0U; bucket < 32U; ++bucket)
		{
			telemetry_record record{};
			record.header.kind = telemetry_record_kind::interval;
			auto &value = record.payload.interval;
			value.session = last_session;
			value.connection = { transport.fresh_producer, subject };
			value.window = { now, now + 1000U, utc + bucket * 1000LL,
					 utc + (bucket + 1U) * 1000LL };
			value.duration_usec = 1000U;
			value.category = telemetry_interval_category::connected_active;
			value.context = telemetry_activity_context::combat;
			value.context_quality = telemetry_context_quality::observed;
			value.dimensions = { 1U, 1U, 1U, 1U, static_cast<std::int32_t>(bucket), 1U };
			value.config_id = 1U;
			value.classifier_version = 1U;
			value.policy_version = 1U;
			consume(record);
		}
		assert(telemetry_posthog_seal_through(now, utc, true));
	}
	const auto full = telemetry_posthog_reducer_health_copy();
	assert(full.output_events < TELEMETRY_POSTHOG_MAX_EVENTS - 16U);
	assert(full.output_suppressed == 0U);
	telemetry_record exit{};
	exit.header = { TELEMETRY_SCHEMA_VERSION,
			telemetry_record_kind::session_lifecycle,
			0U,
			{ transport.fresh_producer, ++sequence },
			utc };
	exit.payload.lifecycle.session = last_session;
	exit.payload.lifecycle.connection = { transport.fresh_producer,
					      last_session.id.session_seq };
	exit.payload.lifecycle.lifecycle = telemetry_lifecycle_kind::session_exited;
	exit.payload.lifecycle.end_reason = telemetry_session_end_reason::logout;
	exit.payload.lifecycle.at_monotonic_usec = now;
	exit.payload.lifecycle.at_utc_usec = utc;
	exit.payload.lifecycle.dimensions = { 1U, 1U, 1U, 1U, 1, 1U };
	exit.payload.lifecycle.config_id = 1U;
	exit.payload.lifecycle.classifier_version = 1U;
	exit.payload.lifecycle.policy_version = 1U;
	assert(telemetry_transport_enqueue(exit).admission ==
	       telemetry_queue_admission::accepted_control_reserve);
	assert(!telemetry_transport_posthog_pulse_for_worker(now, utc));
	assert(telemetry_transport_health_copy().consumed_records == 0U);
	assert(telemetry_transport_health_copy().queue_depth == 1U);
	assert(telemetry_posthog_output_retire(
		full.output_events, telemetry_posthog_output_disposition::http_acknowledged));
	assert(telemetry_transport_posthog_pulse_for_worker(now, utc));
	assert(telemetry_transport_health_copy().consumed_records == 1U);
	assert(telemetry_transport_health_copy().queue_depth == 0U);
	assert(telemetry_transport_health_copy().last_success_monotonic_usec == now);
	assert(telemetry_transport_posthog_pulse_for_worker(now + 1000U, utc + 1000U));
	assert(telemetry_transport_health_copy().last_success_monotonic_usec == now);
	assert(telemetry_posthog_reducer_health_copy().output_suppressed == 0U);
	telemetry_outage_journal journal{};
	assert(telemetry_posthog_output_retire(telemetry_posthog_reducer_health_copy().output_events,
					       telemetry_posthog_output_disposition::suppressed));
	publish_posthog_health(journal);
	assert(R.posthog_health.native.state == telemetry_health_state::degraded);
	assert(R.posthog_health.native.last_failure_class ==
	       telemetry_failure_class::transient_internal);
	telemetry_record refused{};
	refused.header = { TELEMETRY_SCHEMA_VERSION,
			   telemetry_record_kind::configuration,
			   0U,
			   { transport.fresh_producer, ++sequence },
			   utc };
	refused.payload.configuration.config = make_enabled_options().config;
	assert(telemetry_record_is_valid(refused));
	assert(!telemetry_posthog_consume(refused, now, utc));
	assert(telemetry_posthog_reducer_health_copy().reduction_refusals == 1U);
	publish_posthog_health(journal);
	assert(R.posthog_health.native.state == telemetry_health_state::degraded);
	assert(R.posthog_health.native.last_failure_class ==
	       telemetry_failure_class::invalid_record);
	telemetry_health_monitor_state monitor{};
	const auto monitor_config = telemetry_health_monitor_default_config(100'000U, 8192U);
	const auto alert = telemetry_health_monitor_evaluate(&monitor, &monitor_config,
							     R.posthog_health.native,
							     R.posthog_health.observed_at + 1000U);
	assert(alert.severity == telemetry_health_alert_severity::warning);
	assert((alert.reason_mask & TELEMETRY_HEALTH_REASON_WRITER_DEGRADED) != 0U);
	telemetry_posthog_reducer_reset();
	(void)telemetry_transport_request_stop();
	telemetry_transport_repository_shutdown_for_owner();
	telemetry_transport_shutdown();
	std::puts("PostHog byte pressure retains the native record until output drains");
	std::puts(
		"PostHog idle pulses never invent progress; reduction/output loss raises local warning");
}

void check_posthog_consumption_checkpoint()
{
	char directory[] = "/tmp/duris-consumption-checkpoint-XXXXXX";
	assert(mkdtemp(directory) != nullptr);
	setenv("TELEMETRY_OUTAGE_LEDGER_DIR", directory, 1);
	telemetry_transport_unbind_for_tests();
	auto transport = make_transport_config();
	transport.backend = telemetry_storage_backend::posthog;
	transport.fresh_producer = { 901U, 902U };
	assert(telemetry_transport_init(transport) == telemetry_transport_outcome::started);
	telemetry_transport_posthog_start_for_worker();
	R.worker_backend = telemetry_storage_backend::posthog;
	R.producer = transport.fresh_producer;
	R.session_scope_environment_id = 1000U;
	R.session_scope_season_id = 1U;
	{
		worker_outage_guard outage;
		assert(outage.start());
		telemetry_posthog_reducer_config reducer{};
		reducer.producer = R.producer;
		reducer.environment_id = 1000U;
		reducer.season_id = 1U;
		reducer.identity_key.fill(1U);
		assert(telemetry_posthog_reducer_init(reducer));
		auto config = make_enabled_options().config;
		config.backend = telemetry_storage_backend::posthog;
		config.environment_id = 1000U;
		assert(telemetry_config_compute_fingerprint(config, config.fingerprint,
							    sizeof(config.fingerprint)));
		config.config_id = telemetry_config_id_from_fingerprint(config.fingerprint,
									sizeof(config.fingerprint));
		telemetry_record record{};
		record.header = { TELEMETRY_SCHEMA_VERSION,
				  telemetry_record_kind::configuration,
				  0U,
				  { R.producer, 1U },
				  config.effective_utc_usec };
		record.payload.configuration.config = config;
		assert(telemetry_transport_enqueue(record).admission ==
		       telemetry_queue_admission::accepted_control_reserve);
		assert(outage.checkpoint(false, true));
		assert(outage.journal.observations[outage.journal.current].health.consumed_records ==
		       0U);
		telemetry_monotonic_usec now = 0U;
		telemetry_utc_usec utc = 0;
		assert(production_clock_now(nullptr, &now, &utc));
		assert(telemetry_transport_posthog_pulse_for_worker(now, utc));
		// Advance only the cadence gate; no extra admission or incident occurs.
		outage.journal.observations[outage.journal.current].observed_monotonic_usec -=
			60'000'000U;
		assert(outage.checkpoint());
		const auto &saved = outage.journal.observations[outage.journal.current].health;
		assert(saved.consumed_records == 1U && saved.last_consumed_record_seq == 1U);
		assert(saved.last_admitted_record_seq == 1U);
	}
	telemetry_outage_journal persisted{};
	assert(telemetry_outage_read(&persisted, directory) == telemetry_outage_result::ready);
	assert(persisted.observations[persisted.count - 1U].health.last_consumed_record_seq == 1U);
	assert(persisted.observations[persisted.count - 1U].health.consumed_records == 1U);
	telemetry_outage_close(&persisted);
	telemetry_posthog_reducer_reset();
	(void)telemetry_transport_request_stop();
	telemetry_transport_repository_shutdown_for_owner();
	telemetry_transport_shutdown();
	unsetenv("TELEMETRY_OUTAGE_LEDGER_DIR");
	std::filesystem::remove_all(directory);
	std::puts("PostHog consumption-only progress persists without new admission");
}

void check_copyover_caller_ack_race()
{
	R.flush_completed.store(0U);
	R.flush_durable.store(false);
	static unsigned reads = 0U;
	reads = 0U;
	const auto delayed_clock = [](telemetry_monotonic_usec *now) noexcept
	{
		++reads;
		// On the first clock query, the caller sampled time before deadline,
		// then was suspended while a late durable acknowledgement appeared.
		// Clock-before-ack code incorrectly accepts using the stale 99 value.
		*now = reads == 1U ? 99U : 101U;
		R.flush_durable.store(true);
		R.flush_completed.store(1U, std::memory_order_release);
		return true;
	};
	assert(wait_for_copyover_flush(1U, 100U, delayed_clock) ==
	       telemetry_runtime_outcome::queue_full);
	assert(reads == 2U);
	std::puts("copyover caller late-publication race: rejected");
}

struct generation_barrier_repository
{
	std::mutex mutex;
	std::condition_variable condition;
	bool first_entered = false;
	bool second_entered = false;
	bool release_first = false;
	bool release_second = false;
	std::uint32_t init_calls = 0U;
	std::uint32_t apply_calls = 0U;
	std::uint32_t shutdown_calls = 0U;
	telemetry_record_sequence first_record_seq = 0U;
	telemetry_record_sequence first_last_record_seq = 0U;
	telemetry_record_sequence second_record_seq = 0U;
	telemetry_record_sequence second_last_record_seq = 0U;
	telemetry_batch_outcome first_outcome = telemetry_batch_outcome::committed;
	telemetry_batch_outcome second_outcome = telemetry_batch_outcome::committed;

	bool wait_first_entered(std::chrono::milliseconds timeout)
	{
		std::unique_lock<std::mutex> lock(mutex);
		return condition.wait_for(lock, timeout, [this] { return first_entered; });
	}

	bool wait_second_entered(std::chrono::milliseconds timeout)
	{
		std::unique_lock<std::mutex> lock(mutex);
		return condition.wait_for(lock, timeout, [this] { return second_entered; });
	}

	void release_first_callback()
	{
		{
			std::lock_guard<std::mutex> lock(mutex);
			release_first = true;
		}
		condition.notify_all();
	}

	void release_second_callback()
	{
		{
			std::lock_guard<std::mutex> lock(mutex);
			release_second = true;
		}
		condition.notify_all();
	}
};

telemetry_repository_outcome generation_barrier_init(void *context,
						     telemetry_repository_config) noexcept
{
	auto *repository = static_cast<generation_barrier_repository *>(context);
	++repository->init_calls;
	return telemetry_repository_outcome::ready;
}

telemetry_apply_batch_result
generation_barrier_apply(void *context, const telemetry_record *records, std::size_t count) noexcept
{
	auto *repository = static_cast<generation_barrier_repository *>(context);
	assert(records != nullptr && count != 0U);
	std::unique_lock<std::mutex> lock(repository->mutex);
	++repository->apply_calls;
	const std::uint32_t call = repository->apply_calls;
	assert(call <= 2U);
	if (call == 1U)
	{
		repository->first_record_seq = records[0].header.key.record_seq;
		repository->first_last_record_seq = records[count - 1U].header.key.record_seq;
		repository->first_outcome = telemetry_batch_outcome::commit_ambiguous;
		repository->first_entered = true;
		repository->condition.notify_all();
		repository->condition.wait(lock,
					   [repository] { return repository->release_first; });
	}
	else
	{
		repository->second_record_seq = records[0].header.key.record_seq;
		repository->second_last_record_seq = records[count - 1U].header.key.record_seq;
		repository->second_outcome = telemetry_batch_outcome::committed;
		repository->second_entered = true;
		repository->condition.notify_all();
		repository->condition.wait(lock,
					   [repository] { return repository->release_second; });
	}
	lock.unlock();

	telemetry_apply_batch_result result{};
	result.input_count = static_cast<std::uint16_t>(count);
	result.result_count = static_cast<std::uint16_t>(count);
	result.first_record_seq = records[0].header.key.record_seq;
	result.last_record_seq = records[count - 1U].header.key.record_seq;
	if (call == 1U)
	{
		result.outcome = telemetry_batch_outcome::commit_ambiguous;
		result.failure_class = telemetry_failure_class::commit_ambiguous;
		result.error_code = 2013U;
		for (std::size_t index = 0U; index < count; ++index)
		{
			result.results[index].key = records[index].header.key;
			result.results[index].outcome = telemetry_apply_outcome::commit_ambiguous;
			result.results[index].failure_class =
				telemetry_failure_class::commit_ambiguous;
			result.results[index].error_code = 2013U;
		}
	}
	else
	{
		result.outcome = telemetry_batch_outcome::committed;
		result.duplicate_count = static_cast<std::uint16_t>(count);
		for (std::size_t index = 0U; index < count; ++index)
		{
			result.results[index].key = records[index].header.key;
			result.results[index].outcome =
				telemetry_apply_outcome::duplicate_identical;
		}
	}
	return result;
}

telemetry_repository_outcome generation_barrier_request_stop(void *) noexcept
{
	return telemetry_repository_outcome::stopping;
}

void generation_barrier_shutdown(void *context) noexcept
{
	auto *repository = static_cast<generation_barrier_repository *>(context);
	++repository->shutdown_calls;
}

void check_copyover_generation_barrier_recovery()
{
	generation_barrier_repository barrier{};
	const telemetry_transport_repository_binding repository = {
		generation_barrier_init, generation_barrier_apply, generation_barrier_request_stop,
		generation_barrier_shutdown, &barrier
	};
	const telemetry_transport_clock_binding clock = { fake_clock, nullptr };
	assert(telemetry_transport_bind_for_tests(&repository, &clock) ==
	       telemetry_transport_outcome::started);
	const auto options = make_enabled_options();
	telemetry_test_start_runtime(options);
	const auto enter = make_enter(options.producer, options.config);
	assert(telemetry_runtime_session_enter(enter).outcome ==
	       telemetry_runtime_outcome::accepted);

	// Start generation 1 explicitly so the first repository callback belongs to
	// its drain, then leave that callback unresolved past its deadline.
	telemetry_monotonic_usec now = 0U;
	assert(production_monotonic_now(&now));
	const auto generation1_deadline = now + 2'000'000U;
	R.flush_deadline.store(generation1_deadline, std::memory_order_release);
	R.flush_requested.store(1U, std::memory_order_release);
	wake_worker();
	assert(barrier.wait_first_entered(std::chrono::seconds(2)));
	const auto first = wait_for_copyover_flush(1U, generation1_deadline);
	assert(first == telemetry_runtime_outcome::queue_full);
	assert(R.flush_requested.load(std::memory_order_acquire) == 1U);
	assert(R.flush_completed.load(std::memory_order_acquire) != 1U);
	const bool after_deadline = production_monotonic_now(&now) && now >= generation1_deadline;
	std::printf(
		"generation1 wait: deadline=%llu now=%llu completed=%llu durable=%u after=%u\n",
		static_cast<unsigned long long>(generation1_deadline),
		static_cast<unsigned long long>(now),
		static_cast<unsigned long long>(R.flush_completed.load(std::memory_order_acquire)),
		R.flush_durable.load(std::memory_order_acquire), after_deadline);
	std::fflush(stdout);
	assert(after_deadline);

	// Request generation 2 before releasing the old callback. Its duplicate
	// response is the explicit reconciliation of generation 1's ambiguity.
	telemetry_runtime_outcome second = telemetry_runtime_outcome::invalid;
	std::thread next_flush(
		[&]
		{
			telemetry_monotonic_usec second_now = 0U;
			assert(production_monotonic_now(&second_now));
			second = telemetry_runtime_flush_for_copyover(second_now + 250'000U);
		});
	const auto request_wait_until = std::chrono::steady_clock::now() + std::chrono::seconds(2);
	while (R.flush_requested.load(std::memory_order_acquire) != 2U &&
	       std::chrono::steady_clock::now() < request_wait_until)
		std::this_thread::sleep_for(std::chrono::milliseconds(1));
	assert(R.flush_requested.load(std::memory_order_acquire) == 2U);
	assert(R.flush_completed.load(std::memory_order_acquire) != 1U);
	assert(!R.flush_durable.load(std::memory_order_acquire));

	barrier.release_first_callback();
	assert(barrier.wait_second_entered(std::chrono::seconds(2)));
	barrier.release_second_callback();
	next_flush.join();

	const auto health = telemetry_runtime_health_copy();
	assert(second == telemetry_runtime_outcome::accepted);
	assert(barrier.first_outcome == telemetry_batch_outcome::commit_ambiguous);
	assert(barrier.second_outcome == telemetry_batch_outcome::committed);
	assert(barrier.first_record_seq == barrier.second_record_seq);
	assert(barrier.first_last_record_seq == barrier.second_last_record_seq);
	assert(health.ambiguous_commits > 0U);
	assert(health.duplicate_records > 0U);
	assert(health.queue_depth == 0U);
	std::printf("copyover generations: gen1=queue_full gen2=accepted ambiguous=%llu "
		    "duplicates=%llu reused=%llu/%llu\n",
		    static_cast<unsigned long long>(health.ambiguous_commits),
		    static_cast<unsigned long long>(health.duplicate_records),
		    static_cast<unsigned long long>(barrier.first_record_seq),
		    static_cast<unsigned long long>(barrier.second_record_seq));
	std::fflush(stdout);
	assert(production_monotonic_now(&now));
	assert(telemetry_runtime_shutdown({ now + 5'000'000U, 0U, {} }) ==
	       telemetry_runtime_outcome::accepted);
	assert(telemetry_runtime_final_reap() == telemetry_runtime_outcome::accepted);
	assert(barrier.init_calls == 1U);
	assert(barrier.apply_calls == 2U);
	assert(barrier.shutdown_calls == 1U);
	telemetry_transport_unbind_for_tests();
}

void check_late_copyover_ack()
{
	fake_repository fake{};
	fake.block_apply = true;
	const telemetry_transport_repository_binding repository = { fake_init, fake_apply,
								    fake_request_stop,
								    fake_shutdown, &fake };
	const telemetry_transport_clock_binding clock = { fake_clock, nullptr };
	assert(telemetry_transport_bind_for_tests(&repository, &clock) ==
	       telemetry_transport_outcome::started);
	telemetry_test_start_runtime(make_enabled_options());
	telemetry_monotonic_usec now = 0U;
	assert(production_monotonic_now(&now));
	const auto deadline = now + 500'000U;
	// Drive the same request protocol directly to inspect the worker's late ack,
	// even after the ordinary caller would already have timed out.
	R.flush_deadline.store(deadline);
	R.flush_requested.store(1U, std::memory_order_release);
	wake_worker();
	assert(fake.apply_callback.wait_until_entered(std::chrono::seconds(2)));
	assert(production_monotonic_now(&now) && now < deadline);
	std::this_thread::sleep_for(std::chrono::microseconds(deadline - now + 10'000U));
	fake.apply_callback.unblock();
	const auto wait_until = std::chrono::steady_clock::now() + std::chrono::seconds(2);
	while (R.flush_completed.load(std::memory_order_acquire) != 1U &&
	       std::chrono::steady_clock::now() < wait_until)
		std::this_thread::sleep_for(std::chrono::milliseconds(1));
	assert(R.flush_completed.load(std::memory_order_acquire) == 1U);
	const bool late_durable = R.flush_durable.load();
	assert(production_monotonic_now(&now));
	const auto fresh = telemetry_runtime_flush_for_copyover(now + 250'000U);
	assert(telemetry_runtime_shutdown({ now + 1'000'000U, 0U, {} }) ==
	       telemetry_runtime_outcome::accepted);
	assert(telemetry_runtime_final_reap() == telemetry_runtime_outcome::accepted);
	telemetry_transport_unbind_for_tests();
	std::printf("late copyover ack: durable=%u fresh=%u\n", late_durable,
		    static_cast<unsigned>(fresh));
	std::fflush(stdout);
	assert(!late_durable);
	assert(fresh == telemetry_runtime_outcome::accepted);
}

void check_identity_fail_closed()
{
	for (int mode : { 1, 2 })
	{
		entropy_mode = mode;
		entropy_calls = 0;
		const auto options = telemetry_runtime_default_options();
		assert(telemetry_producer_id_is_zero(options.producer));
		assert(telemetry_runtime_init(options) == telemetry_runtime_outcome::invalid);
		assert(entropy_calls == (mode == 1 ? 1U : 4U));
	}
	entropy_mode = 0;
	const auto options = make_enabled_options();
	assert(telemetry_producer_id_is_valid(options.producer));
	const auto saved_count = used_producer_count;
	used_producer_count = sizeof(used_producers) / sizeof(used_producers[0]);
	assert(telemetry_runtime_init(options) == telemetry_runtime_outcome::invalid);
	assert(used_producer_count == sizeof(used_producers) / sizeof(used_producers[0]));
	used_producer_count = saved_count;
	std::puts("producer entropy failure, zero-token retry bound, and ledger exhaustion passed");
}

void check_exhausted_lifecycle(bool exiting, bool reattaching = false)
{
	fake_repository fake{};
	const telemetry_transport_repository_binding repository = { fake_init, fake_apply,
								    fake_request_stop,
								    fake_shutdown, &fake };
	const telemetry_transport_clock_binding clock = { fake_clock, nullptr };
	assert(telemetry_transport_bind_for_tests(&repository, &clock) ==
	       telemetry_transport_outcome::started);
	const auto options = make_enabled_options();
	telemetry_test_start_runtime(options);
	auto enter = make_enter(options.producer, options.config);
	assert(telemetry_runtime_now(&enter.at_monotonic_usec, &enter.at_utc_usec));
	assert(telemetry_runtime_session_enter(enter).outcome ==
	       telemetry_runtime_outcome::accepted);
	assert(telemetry_runtime_record_evidence({ enter.session,
						   enter.connection,
						   enter.at_monotonic_usec,
						   enter.at_utc_usec,
						   telemetry_runtime_evidence_kind::player_action,
						   {},
						   TELEMETRY_QUALITY_NONE })
		       .outcome == telemetry_runtime_outcome::accepted);

	// Zero is the real allocator's exhausted sentinel. It must never wrap or
	// acquire a fresh identity just to keep emitting records.
	if (reattaching)
	{
		telemetry_connection_transition prior{};
		prior.session = enter.session;
		prior.connection = enter.connection;
		prior.at_monotonic_usec = enter.at_monotonic_usec + 500U;
		prior.at_utc_usec = enter.at_utc_usec + 500;
		prior.kind = telemetry_connection_transition_kind::detached;
		assert(telemetry_runtime_connection_transition(prior).outcome ==
		       telemetry_runtime_outcome::accepted);
	}
	R.next_record_sequence = 0U;
	telemetry_capture_result changed{};
	if (exiting)
	{
		telemetry_session_exit exit{};
		exit.session = enter.session;
		exit.connection = enter.connection;
		exit.at_monotonic_usec = enter.at_monotonic_usec + 1'000U;
		exit.at_utc_usec = enter.at_utc_usec + 1'000;
		exit.reason = telemetry_session_end_reason::logout;
		changed = telemetry_runtime_session_exit(exit);
	}
	else
	{
		telemetry_connection_transition detach{};
		detach.session = enter.session;
		detach.connection = enter.connection;
		detach.at_monotonic_usec = enter.at_monotonic_usec + 1'000U;
		detach.at_utc_usec = enter.at_utc_usec + 1'000;
		detach.kind = reattaching ? telemetry_connection_transition_kind::attached :
					    telemetry_connection_transition_kind::detached;
		if (reattaching)
			detach.connection.connection_seq = 2U;
		changed = telemetry_runtime_connection_transition(detach);
	}
	const auto pulse = telemetry_runtime_pulse(
		{ enter.at_monotonic_usec + 2'000U, enter.at_utc_usec + 2'000, 0U, 0U });
	telemetry_activity_state_view activity{};
	telemetry_session_state_view session{};
	assert(telemetry_activity_state_copy_view(&R.activity, enter.session, &activity));
	assert(telemetry_session_state_copy_view(&R.session, enter.session, &session));
	std::printf("exhausted %s: outcome=%u pulse=%u connected=%u/%u closed=%u/%u "
		    "resident=%llu/%llu linkdead=%llu/%llu\n",
		    exiting ? "exit" : (reattaching ? "attach" : "detach"),
		    static_cast<unsigned>(changed.outcome), static_cast<unsigned>(pulse.outcome),
		    activity.connected, session.connected, activity.closed, session.closed,
		    static_cast<unsigned long long>(activity.cumulative.resident_usec),
		    static_cast<unsigned long long>(session.cumulative.resident_usec),
		    static_cast<unsigned long long>(activity.cumulative.linkdead_usec),
		    static_cast<unsigned long long>(session.cumulative.linkdead_usec));
	std::fflush(stdout);
	assert(R.next_record_sequence == 0U);
	telemetry_monotonic_usec now = 0U;
	telemetry_utc_usec utc = 0;
	assert(telemetry_runtime_now(&now, &utc));
	assert(telemetry_runtime_shutdown({ now + 5'000'000U, 1U, {} }) ==
	       telemetry_runtime_outcome::accepted);
	assert(telemetry_runtime_final_reap() == telemetry_runtime_outcome::accepted);
	telemetry_transport_unbind_for_tests();
	assert(changed.outcome == telemetry_runtime_outcome::queue_full);
	assert(activity.connected == session.connected);
	assert(activity.closed == session.closed);
	assert(session.closed == (exiting ? 1U : 0U));
	assert(activity.cumulative.resident_usec == session.cumulative.resident_usec);
	assert(activity.cumulative.active_usec == session.cumulative.active_usec);
	assert(activity.cumulative.linkdead_usec == session.cumulative.linkdead_usec);
	assert(session.cumulative.active_usec == (reattaching ? 500U : 1'000U));
	assert(session.cumulative.linkdead_usec == (exiting ? 0U : (reattaching ? 500U : 1'000U)));
	assert(((changed.quality_flags | pulse.quality_flags) & TELEMETRY_QUALITY_SEQUENCE_GAP) !=
	       0U);
}
} // namespace

int main()
{
	check_posthog_byte_pressure();
	check_posthog_consumption_checkpoint();
	check_identity_fail_closed();
	check_copyover_caller_ack_race();
	check_copyover_generation_barrier_recovery();
	check_late_copyover_ack();
	check_exhausted_lifecycle(false);
	check_exhausted_lifecycle(true);
	check_exhausted_lifecycle(false, true);
	std::puts("telemetry sequence-exhausted lifecycle consistency passed");
}
