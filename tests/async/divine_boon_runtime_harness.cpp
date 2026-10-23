#include <cstdint>
bool divine_trade_runtime_boot(uint64_t)
{
	return true;
}
#include "economy/divine_boon_runtime.h"
#include "economy/divine_boon_repository.h"
#include "economy/boon_reward_transaction.h"
#include "persistence/persistence_mode.h"
#include "persistence/maintenance_scheduler.h"
#include "player/player_save_worker.h"

#include <cassert>
#include <chrono>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <future>
#include <iostream>
#include <thread>

unsigned long long ne_event_tick = 0;
static uint64_t pending_rewards = 0;

boon_reward_health boon_reward_transaction_health_copy()
{
	boon_reward_health health = {};
	health.pending = pending_rewards;
	return health;
}

namespace
{
std::string root;

player_save_apply_result unused_player(const player_snapshot &, void *)
{
	std::abort();
}

void finish()
{
	assert(persistence_writer_wait_idle(3000));
	divine_boon_runtime_pulse();
}
}

persistence_mode persistence_mode_get()
{
	return PERSISTENCE_MODE_FLATFILE_PRIMARY;
}
const char *persistence_mode_flatfile_root()
{
	return root.c_str();
}

int main(int argc, char **argv)
{
	assert(argc == 2);
	root = argv[1];
	std::filesystem::create_directories(root + "/domains");
	for (const auto &directory : { root, root + "/domains" })
		std::filesystem::permissions(directory, std::filesystem::perms::owner_all,
					     std::filesystem::perm_options::replace);
	assert(!divine_boon_runtime_boot(100)); // Queue refusal never publishes state.
	assert(!divine_boon_runtime_state() && !divine_boon_runtime_pending());
	assert(!divine_boon_legacy_admissions_allowed());
	assert(player_save_worker_init(unused_player, nullptr));
	std::promise<void> entered, release;
	auto released = release.get_future();
	assert(persistence_writer_submit(persistence_job_kind::log, 1, 1,
					 [&]
					 {
						 entered.set_value();
						 released.wait();
						 return player_save_apply_result{
							 player_save_apply_outcome::applied, 0, 0
						 };
					 }) == player_save_submit_result::accepted);
	assert(entered.get_future().wait_for(std::chrono::seconds(3)) == std::future_status::ready);
	assert(divine_boon_runtime_boot(100));
	assert(divine_boon_runtime_pending() && !divine_boon_runtime_state());
	assert(!divine_boon_runtime_boot(100));
	release.set_value();
	finish();
	assert(!divine_boon_runtime_pending());
	assert(divine_boon_runtime_state()->mode == divine_boon_mode::legacy);
	assert(divine_boon_legacy_admissions_allowed());
	assert(std::string(persistence_job_kind_name(persistence_job_kind::divine_boon)) ==
	       "divine_boon");
	auto next = *divine_boon_runtime_state();
	assert(divine_boon_set_mode(&next, divine_boon_mode::draining, 100));
	// An admitted flat-file scan must reach its game-thread completion before
	// retirement closes the legacy gate, including an undrained completion.
	std::promise<void> scan_release;
	auto scan_released = scan_release.get_future().share();
	assert(maintenance_scheduler_init(
		1,
		[](const maintenance_request &request, void *context)
		{
			auto &wait = *static_cast<std::shared_future<void> *>(context);
			wait.wait();
			return maintenance_result{ request.work_id,
						   request.job_id,
						   request.cursor ? maintenance_outcome::complete :
								    maintenance_outcome::more,
						   64,
						   64,
						   0,
						   0,
						   0,
						   {} };
		},
		&scan_released, [](maintenance_request &request, void *)
		{ return request.job_id == maintenance_job_id::boon_scan; }));
	const auto scan_index = static_cast<size_t>(maintenance_job_id::boon_scan);
	ne_event_tick = maintenance_scheduler_health_copy(0).jobs[scan_index].next_due_tick;
	for (size_t attempt = 0;
	     attempt < MAINTENANCE_JOB_COUNT * 2 &&
	     !maintenance_scheduler_health_copy(ne_event_tick).jobs[scan_index].active;
	     ++attempt)
		maintenance_scheduler_pulse(ne_event_tick, nullptr, 0);
	assert(maintenance_scheduler_health_copy(ne_event_tick).jobs[scan_index].active);
	assert(!divine_boon_runtime_queue(next));
	assert(divine_boon_legacy_admissions_allowed());
	scan_release.set_value();
	const auto scan_deadline = std::chrono::steady_clock::now() + std::chrono::seconds(3);
	while (!maintenance_scheduler_health_copy(ne_event_tick).completions &&
	       std::chrono::steady_clock::now() < scan_deadline)
		std::this_thread::sleep_for(std::chrono::milliseconds(1));
	assert(maintenance_scheduler_health_copy(ne_event_tick).completions == 1);
	assert(!divine_boon_runtime_queue(next));
	maintenance_scheduler_quiesce();
	maintenance_result scan_result = {};
	assert(maintenance_scheduler_pulse(ne_event_tick, &scan_result, 1) == 1);
	assert(scan_result.job_id == maintenance_job_id::boon_scan &&
	       scan_result.outcome == maintenance_outcome::more);
	assert(!maintenance_scheduler_health_copy(ne_event_tick).jobs[scan_index].active);
	assert(!divine_boon_runtime_queue(next)); // A retained page is still unfinished.
	maintenance_scheduler_resume();
	++ne_event_tick;
	for (size_t attempt = 0;
	     attempt < MAINTENANCE_JOB_COUNT * 2 &&
	     !maintenance_scheduler_health_copy(ne_event_tick).jobs[scan_index].active;
	     ++attempt)
		maintenance_scheduler_pulse(ne_event_tick, nullptr, 0);
	const auto page_deadline = std::chrono::steady_clock::now() + std::chrono::seconds(3);
	while (!maintenance_scheduler_health_copy(ne_event_tick).completions &&
	       std::chrono::steady_clock::now() < page_deadline)
		std::this_thread::sleep_for(std::chrono::milliseconds(1));
	maintenance_scheduler_quiesce();
	assert(maintenance_scheduler_pulse(ne_event_tick, &scan_result, 1) == 1);
	assert(scan_result.outcome == maintenance_outcome::complete);
	// The synchronous completion callback still sees an open gate.
	assert(divine_boon_legacy_admissions_allowed());
	pending_rewards = 1;
	assert(!divine_boon_runtime_queue(next));
	assert(divine_boon_legacy_admissions_allowed());
	pending_rewards = 2; // Publishing an admitted reward can submit a level completion.
	assert(!divine_boon_runtime_queue(next));
	pending_rewards = 1; // The parent is acknowledged, but its nested reward is pending.
	assert(!divine_boon_runtime_queue(next));
	pending_rewards = 0;
	assert(divine_boon_runtime_queue(next));
	maintenance_scheduler_reset_for_tests();
	assert(!divine_boon_runtime_queue(next));
	assert(!divine_boon_legacy_admissions_allowed());
	assert(divine_boon_runtime_state()->mode == divine_boon_mode::legacy);
	finish();
	assert(divine_boon_runtime_state()->mode == divine_boon_mode::draining);
	assert(!divine_boon_legacy_admissions_allowed());
	next = *divine_boon_runtime_state();
	assert(divine_boon_set_mode(&next, divine_boon_mode::divine, 100));
	assert(divine_boon_runtime_queue(next));
	finish();
	next = *divine_boon_runtime_state();
	divine_boon_slot choice;
	choice.category = divine_boon_category::experience;
	choice.zones = { 10, 20 };
	assert(divine_boon_rotate(&next, DIVINE_BOON_HOUR, &choice));
	assert(divine_boon_runtime_queue(next));
	finish();
	assert(divine_boon_runtime_state()->slots[0].id == 1);
	assert(divine_boon_runtime_boot(20 * DIVINE_BOON_HOUR));
	assert(!divine_boon_runtime_state()); // Restart skips hours only after committing.
	finish();
	assert(!divine_boon_runtime_state()->slots[0].id);
	assert(divine_boon_runtime_state()->last_opportunity == 20 * DIVINE_BOON_HOUR);
	next = *divine_boon_runtime_state();
	assert(divine_boon_set_paused(&next, true, 20 * DIVINE_BOON_HOUR));
	assert(setenv("DURIS_FLATFILE_TEST_INTERRUPT_AFTER_AUTHORITY_JOURNAL", "1", 1) == 0);
	assert(divine_boon_runtime_queue(next));
	finish();
	assert(!divine_boon_runtime_state() && divine_boon_runtime_pending());
	assert(unsetenv("DURIS_FLATFILE_TEST_INTERRUPT_AFTER_AUTHORITY_JOURNAL") == 0);
	divine_boon_state recovered;
	assert(divine_boon_flatfile_load(root, &recovered) == divine_boon_store_result::ok);
	assert(recovered == next);
	const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(8);
	while (divine_boon_runtime_pending() && std::chrono::steady_clock::now() < deadline)
	{
		divine_boon_runtime_pulse();
		std::this_thread::sleep_for(std::chrono::milliseconds(10));
	}
	assert(divine_boon_runtime_state() && *divine_boon_runtime_state() == next);
	assert(divine_boon_runtime_boot(19 * DIVINE_BOON_HOUR));
	assert(divine_boon_runtime_state()->last_opportunity == 20 * DIVINE_BOON_HOUR);
	std::ofstream(root + "/domains/divine-boons.state", std::ios::binary | std::ios::trunc)
		<< "bad";
	assert(!divine_boon_runtime_boot(20 * DIVINE_BOON_HOUR));
	assert(!divine_boon_runtime_state() && !divine_boon_runtime_pending());
	player_save_worker_shutdown();
	std::cout
		<< "Divine Boon runtime: real writer ordering, commit-before-publication, restart and retry passed\n";
}
