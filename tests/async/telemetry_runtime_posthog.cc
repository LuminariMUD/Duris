// Reuse the native runtime's synthetic sessions/configuration and game stubs.
#define main ordinary_runtime_test_main
#include "telemetry_runtime_integration.cc"
#undef main

#include <filesystem>

int main(int argc, char **argv)
{
	assert(argc == 3);
	const std::string scenario = argv[1];
	const char *directory = argv[2];
	telemetry_monotonic_usec now = 0U;
	telemetry_utc_usec utc = 0;
	utc = std::chrono::duration_cast<std::chrono::microseconds>(
		      std::chrono::system_clock::now().time_since_epoch())
		      .count();
	telemetry_quota_binding binding{ 678214U, 99U, 1000U, 1U, 90U, 10U, 100U };
	if (scenario == "invalid-scope")
		binding.environment_id = 2U;
	if (scenario == "quota")
		binding = { 678214U, 99U, 1000U, 1U, 2U, 10U, 12U };
	telemetry_outage_journal journal{};
	assert(telemetry_outage_read(&journal, directory) == telemetry_outage_result::ready);
	if (scenario != "missing-quota")
		assert(telemetry_outage_quota_initialize(
			       &journal, binding,
			       utc + (scenario == "rollback" ? 86'400'000'000LL : 0LL)) ==
		       telemetry_outage_result::ready);
	if (scenario != "owner")
		telemetry_outage_close(&journal);
	setenv("TELEMETRY_OUTAGE_LEDGER_DIR", directory, 1);
	if (scenario == "missing-key")
		unsetenv("TELEMETRY_IDENTITY_KEY");
	if (scenario == "missing-token")
		unsetenv("POSTHOG_API_KEY");
	if (scenario == "missing-host")
		unsetenv("POSTHOG_HOST");
	if (scenario == "missing-sender")
		unsetenv("POSTHOG_SENDER_ID");
	if (scenario == "invalid-host")
		setenv("POSTHOG_HOST", "https://invalid.example", 1);
	if (scenario == "invalid-project")
		setenv("POSTHOG_PROJECT_ID", "1", 1);
	if (scenario == "quota-mismatch")
		setenv("POSTHOG_SENDER_ID", "100", 1);
	if (scenario == "quota")
	{
		setenv("POSTHOG_NORMAL_LIMIT", "2", 1);
		setenv("POSTHOG_DAILY_LIMIT", "12", 1);
	}
	const bool configuration = scenario == "missing-key" || scenario == "missing-token" ||
				   scenario == "missing-host" || scenario == "missing-sender" ||
				   scenario == "invalid-host" || scenario == "invalid-project" ||
				   scenario == "invalid-scope";
	const bool refused = configuration || scenario == "missing-quota" ||
			     scenario == "quota-mismatch" || scenario == "owner";
	std::uint32_t prior_reserved = 0U;
	for (unsigned int incarnation = 0U; incarnation < (scenario == "restart" ? 2U : 1U);
	     ++incarnation)
	{
		std::uint64_t expected_connected = 0U;
		auto options = make_enabled_options();
		options.config.backend = telemetry_storage_backend::posthog;
		options.config.environment_id = binding.environment_id;
		options.config.interval_usec = 100'000U;
		options.config.checkpoint_interval_usec = 200'000U;
		options.config.active_window_usec = 2'000'000U;
		assert(telemetry_config_compute_fingerprint(options.config,
							    options.config.fingerprint,
							    sizeof(options.config.fingerprint)));
		options.config.config_id = telemetry_config_id_from_fingerprint(
			options.config.fingerprint, sizeof(options.config.fingerprint));
		if (refused)
		{
			assert(telemetry_runtime_init(options) ==
			       telemetry_runtime_outcome::accepted);
			const auto end = std::chrono::steady_clock::now() + std::chrono::seconds(2);
			while (telemetry_runtime_health_copy().state !=
				       telemetry_health_state::circuit_open &&
			       std::chrono::steady_clock::now() < end)
				std::this_thread::sleep_for(std::chrono::milliseconds(1));
			assert(telemetry_runtime_health_copy().state ==
			       telemetry_health_state::circuit_open);
			const auto health = telemetry_runtime_health_copy();
			assert(health.last_storage_check ==
			       (configuration	    ? telemetry_storage_check::configuration :
				scenario == "owner" ? telemetry_storage_check::owner :
						      telemetry_storage_check::quota));
			assert(health.last_error_code ==
			       (configuration || scenario == "quota-mismatch" ? EINVAL :
				scenario == "missing-quota"		      ? ENODATA :
										EWOULDBLOCK));
		}
		else
			telemetry_test_start_runtime(options);
		auto enter = make_enter(options.producer, options.config);
		enter.session.environment_id = 1000U;
		assert(telemetry_runtime_now(&enter.at_monotonic_usec, &enter.at_utc_usec));
		const auto entered = telemetry_runtime_session_enter(enter);
		if (refused)
			assert(entered.outcome != telemetry_runtime_outcome::accepted);
		else
		{
			assert(entered.outcome == telemetry_runtime_outcome::accepted);
			assert(telemetry_runtime_health_copy().advisory_lock_state ==
			       telemetry_advisory_lock_state::not_applicable);
			std::this_thread::sleep_for(std::chrono::milliseconds(25));
			assert(telemetry_runtime_now(&now, &utc));
			(void)telemetry_runtime_pulse({ now, utc, 0U, 0U });
			const auto handoff = telemetry_runtime_session_handoff_copy(enter.session);
			assert(handoff.outcome == telemetry_runtime_outcome::accepted);
			assert(handoff.handoff.cumulative.connected_usec > 0U);
			if (scenario == "storage")
				std::filesystem::create_directory(std::filesystem::path(directory) /
								  "outages.pending");
			assert(telemetry_runtime_now(&now, &utc));
			const auto start = std::chrono::steady_clock::now();
			const auto flushed = telemetry_runtime_flush_for_copyover(now + 250'000U);
			assert(std::chrono::steady_clock::now() - start <
			       std::chrono::milliseconds(350));
			if (scenario == "success" || scenario == "restart")
				assert(flushed == telemetry_runtime_outcome::accepted);
			else
				assert(flushed != telemetry_runtime_outcome::accepted);
			// Handoff identity and cumulative counters survive any HTTP result.
			const auto retained = telemetry_runtime_session_handoff_copy(enter.session);
			if (scenario == "storage")
				assert(retained.outcome != telemetry_runtime_outcome::accepted);
			else
			{
				assert(retained.outcome == telemetry_runtime_outcome::accepted);
				assert(retained.handoff.session.id.session_seq ==
				       handoff.handoff.session.id.session_seq);
			}
			expected_connected = retained.handoff.cumulative.connected_usec;
			if (scenario == "deadline")
			{
				// Simulate failed exec: the same process resumes without resetting quota/counters.
				std::this_thread::sleep_for(std::chrono::milliseconds(60));
				assert(telemetry_runtime_now(&now, &utc));
				(void)telemetry_runtime_pulse({ now, utc, 0U, 0U });
				(void)telemetry_runtime_flush_for_copyover(now + 1'000'000U);
			}
		}
		assert(telemetry_runtime_now(&now, &utc));
		(void)telemetry_runtime_shutdown({ now + 300'000U, 1U, {} });
		assert(telemetry_runtime_final_reap() == telemetry_runtime_outcome::accepted);
		telemetry_runtime_posthog_health health{};
		if (!refused)
		{
			assert(telemetry_runtime_posthog_health_copy(&health));
			assert(health.native.consumed_records ==
			       health.native.admitted_control + health.native.admitted_detail);
			assert(health.native.applied_records == 0U &&
			       health.native.last_committed_record_seq == 0U);
			assert(health.reducer.invalid_records == 0U &&
			       health.reducer.reduction_refusals == 0U);
			if (scenario != "storage")
				assert(health.sender.reserved_events + prior_reserved ==
				       health.normal_reserved + health.health_reserved);
			prior_reserved = health.normal_reserved + health.health_reserved;
			if (scenario == "quota")
				assert(health.sender.quota_refusals > 0U);
			if (scenario == "storage")
				assert(health.sender.storage_failures > 0U);
			if (scenario == "rollback")
				assert(health.sender.clock_failures > 0U);
			if (scenario == "storage" || scenario == "400" || scenario == "401" ||
			    scenario == "403")
			{
				assert(health.native.last_failure_class ==
				       (scenario == "401" || scenario == "403" ?
						telemetry_failure_class::permanent_permission :
						telemetry_failure_class::permanent_repository));
				assert(health.native.state == telemetry_health_state::degraded);
				telemetry_health_monitor_state monitor{};
				const auto config =
					telemetry_health_monitor_default_config(100'000U, 256U);
				const auto event = telemetry_health_monitor_evaluate(
					&monitor, &config, health.native, now + 1'000'000U);
				assert(event.severity == telemetry_health_alert_severity::critical);
				assert((event.reason_mask &
					TELEMETRY_HEALTH_REASON_PERMANENT_FAILURE) != 0U);
			}
			if (scenario == "rollback" ||
			    health.sender.state == telemetry_posthog_sender_state::quota_blocked)
				assert(health.native.last_failure_class ==
				       telemetry_failure_class::transient_internal);
			if (scenario == "deadline")
			{
				assert(health.sender.cancellations > 0U);
				assert(health.reducer.ambiguous_events > 0U);
				assert(health.reducer.http_acknowledged > 0U);
			}
			if (scenario == "success" || scenario == "restart")
			{
				assert(health.reducer.http_acknowledged ==
				       health.reducer.created_events);
				assert(health.reducer.output_suppressed == 0U);
			}
			std::printf(
				"{\"consumed\":%llu,\"reserved\":%u,\"acknowledged\":%llu,\"connected\":%llu}\n",
				(unsigned long long)health.native.consumed_records, prior_reserved,
				(unsigned long long)health.reducer.http_acknowledged,
				(unsigned long long)expected_connected);
		}
	}
	if (scenario == "owner")
		telemetry_outage_close(&journal);
	if (scenario != "storage")
	{
		assert(telemetry_outage_read(&journal, directory) ==
		       telemetry_outage_result::ready);
		if (!refused)
			assert(journal.observations[journal.count - 1U].phase ==
			       telemetry_outage_phase::unknown_tail);
		telemetry_outage_close(&journal);
	}
	std::puts("telemetry PostHog runtime path passed");
}
