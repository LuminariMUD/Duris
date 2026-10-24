void divine_trade_runtime_reconcile() {}
#include <cstdint>
bool divine_trade_runtime_boot(uint64_t)
{
	return true;
}
#include "economy/divine_boon_runtime.h"
#include "persistence/critical_command_coordinator.h"
#include <ctime>
#include "economy/divine_boon_repository.h"
#include "economy/boon_reward_transaction.h"
#include "persistence/persistence_mode.h"
#include "persistence/maintenance_scheduler.h"
#include "player/player_save_worker.h"

#include <cassert>
#include <algorithm>
#include <atomic>
#include <chrono>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <future>
#include <iostream>
#include <thread>

unsigned long long ne_event_tick = 0;
static uint64_t pending_rewards = 0;
static unsigned grants = 0, expiries = 0;
void divine_boon_announce_changes(const std::array<divine_boon_slot, DIVINE_BOON_SLOTS> &before,
				  const std::array<divine_boon_slot, DIVINE_BOON_SLOTS> &after,
				  int64_t now)
{
	for (const auto &slot : after)
		if (slot.id &&
		    std::none_of(before.begin(), before.end(),
				 [id = slot.id](const auto &old) { return old.id == id; }))
			++grants;
	for (const auto &old : before)
		if (old.id && old.expires_at <= now &&
		    std::none_of(after.begin(), after.end(),
				 [id = old.id](const auto &slot) { return slot.id == id; }))
			++expiries;
}

boon_reward_health boon_reward_transaction_health_copy()
{
	boon_reward_health health = {};
	health.pending = pending_rewards;
	return health;
}

critical_coordinator_health old_work = {};
critical_coordinator_health critical_command_coordinator_health_copy()
{
	return old_work;
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

	assert(divine_boon_runtime_state()->mode == divine_boon_mode::draining);
	assert(!divine_boon_legacy_admissions_allowed());
	old_work.initialized = old_work.running = true;
	old_work.queued = 1;
	divine_boon_runtime_pulse();
	assert(!divine_boon_runtime_pending());
	old_work.queued = 0;
	old_work.inflight = 1;
	divine_boon_runtime_pulse();
	assert(!divine_boon_runtime_pending());
	old_work.inflight = 0;
	old_work.blocked = 1;
	divine_boon_runtime_pulse();
	assert(!divine_boon_runtime_pending());
	old_work.blocked = 0;
	old_work.fenced_keys = 1;
	divine_boon_runtime_pulse();
	assert(!divine_boon_runtime_pending());
	old_work.fenced_keys = 0;
	const auto scheduler_path = root + "/maintenance.state";
	assert(maintenance_scheduler_set_state_path(scheduler_path.c_str()));
	std::atomic<bool> scan_executed{ false };
	auto execute_scan = [](const maintenance_request &request, void *context)
	{
		maintenance_result result{};
		result.work_id = request.work_id;
		result.job_id = request.job_id;
		result.outcome = maintenance_outcome::complete;
		if (request.job_id == maintenance_job_id::boon_scan)
			static_cast<std::atomic<bool> *>(context)->store(true);
		return result;
	};
	assert(maintenance_scheduler_init(1, execute_scan, &scan_executed));
	const auto scan = static_cast<size_t>(maintenance_job_id::boon_scan);
	std::array<maintenance_result, MAINTENANCE_JOB_COUNT> restored_results;
	maintenance_scheduler_pulse(0, restored_results.data(), restored_results.size());
	const auto scan_tick = maintenance_scheduler_health_copy(0).jobs[scan].next_due_tick;
	const auto queued_deadline = std::chrono::steady_clock::now() + std::chrono::seconds(5);
	while (!maintenance_scheduler_health_copy(scan_tick).jobs[scan].work_id)
	{
		assert(std::chrono::steady_clock::now() < queued_deadline);
		maintenance_scheduler_pulse(scan_tick, restored_results.data(),
					    restored_results.size());
		std::this_thread::sleep_for(std::chrono::milliseconds(1));
	}
	while (!scan_executed.load())
	{
		assert(std::chrono::steady_clock::now() < queued_deadline);
		std::this_thread::sleep_for(std::chrono::milliseconds(1));
	}
	maintenance_scheduler_shutdown();
	assert(maintenance_scheduler_init(1, execute_scan, &scan_executed));
	assert(maintenance_scheduler_health_copy(scan_tick).jobs[scan].work_id);
	divine_boon_runtime_pulse();
	assert(!divine_boon_runtime_pending() &&
	       divine_boon_runtime_state()->mode == divine_boon_mode::draining);
	const auto scan_deadline = std::chrono::steady_clock::now() + std::chrono::seconds(5);
	while (maintenance_scheduler_health_copy(scan_tick).jobs[scan].work_id)
	{
		assert(std::chrono::steady_clock::now() < scan_deadline);
		maintenance_scheduler_pulse(scan_tick, restored_results.data(),
					    restored_results.size());
		std::this_thread::sleep_for(std::chrono::milliseconds(1));
	}
	maintenance_scheduler_shutdown();
	divine_boon_runtime_pulse();
	assert(divine_boon_runtime_pending());
	assert(divine_boon_runtime_state()->mode == divine_boon_mode::draining);
	finish();
	assert(divine_boon_runtime_state()->mode == divine_boon_mode::divine);
	assert(grants == 0 && expiries == 0);
	const auto base = divine_boon_runtime_state()->last_opportunity;
	auto next = *divine_boon_runtime_state();

	divine_boon_slot choice;
	choice.category = divine_boon_category::experience;
	choice.zones = { 10, 20 };
	assert(divine_boon_rotate(&next, base + DIVINE_BOON_HOUR, &choice));
	assert(divine_boon_runtime_queue(next));
	finish();
	assert(divine_boon_runtime_state()->slots[0].id == 1);
	assert(grants == 1 && expiries == 0);
	assert(divine_boon_runtime_boot(base + 20 * DIVINE_BOON_HOUR));
	assert(!divine_boon_runtime_state()); // Restart skips hours only after committing.
	finish();
	assert(!divine_boon_runtime_state()->slots[0].id);
	assert(grants == 1 && expiries == 0); // No duplicate after reboot.
	assert(divine_boon_runtime_state()->last_opportunity == base + 20 * DIVINE_BOON_HOUR);
	next = *divine_boon_runtime_state();
	assert(divine_boon_set_paused(&next, true, base + 20 * DIVINE_BOON_HOUR));
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
	assert(divine_boon_runtime_boot(base + 19 * DIVINE_BOON_HOUR));
	assert(divine_boon_runtime_state()->last_opportunity == base + 20 * DIVINE_BOON_HOUR);
	std::ofstream(root + "/domains/divine-boons.state", std::ios::binary | std::ios::trunc)
		<< "bad";
	assert(!divine_boon_runtime_boot(base + 20 * DIVINE_BOON_HOUR));
	assert(!divine_boon_runtime_state() && !divine_boon_runtime_pending());
	// An existing legacy snapshot closes admission immediately while its draining
	// transition is queued, then waits for accepted work before publishing Divine.
	root += "-legacy";
	std::filesystem::create_directories(root + "/domains");
	for (const auto &directory : { root, root + "/domains" })
		std::filesystem::permissions(directory, std::filesystem::perms::owner_all,
					     std::filesystem::perm_options::replace);
	divine_boon_state legacy;
	assert(divine_boon_flatfile_save(root, 0, legacy) == divine_boon_store_result::ok);
	old_work.inflight = 1;
	assert(divine_boon_runtime_boot(100) && divine_boon_runtime_pending());
	assert(!divine_boon_legacy_admissions_allowed());
	finish();
	assert(divine_boon_runtime_state()->mode == divine_boon_mode::draining);
	divine_boon_runtime_pulse();
	assert(!divine_boon_runtime_pending());
	old_work.inflight = 0;
	divine_boon_runtime_pulse();
	assert(divine_boon_runtime_pending());
	finish();
	assert(divine_boon_runtime_state()->mode == divine_boon_mode::divine);
	assert(grants == 1 && expiries == 0);
	assert(!divine_boon_legacy_admissions_allowed());

	player_save_worker_shutdown();
	std::cout
		<< "Divine Boon runtime: real writer ordering, commit-before-publication, restart and retry passed\n";
}
