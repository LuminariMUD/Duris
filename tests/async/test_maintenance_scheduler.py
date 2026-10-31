#!/usr/bin/env python3
"""Runtime and source contracts for the bounded maintenance scheduler."""

from _paths import SRC, rel
import subprocess
import tempfile
import shlex
import struct
import shutil
import os
from pathlib import Path
from _paths import HARNESS_STUBS


ROOT = Path(__file__).resolve().parents[2]
SOURCE = (SRC / "maintenance_scheduler.c").read_text()
COMM = (SRC / "comm.c").read_text()
COPYOVER = (SRC / "copyover.c").read_text()
SNAPSHOT = (SRC / "maintenance_snapshot.c").read_text()
REPOSITORY = (SRC / "maintenance_repository.c").read_text()
NEW_EVENTS = (SRC / "new_events.c").read_text()

HARNESS = r'''
#include "persistence/maintenance_scheduler.h"

#include <atomic>
#include <cassert>
#include <chrono>
#include <condition_variable>
#include <ctime>
#include <cstring>
#include <mutex>
#include <string>
#include <sys/stat.h>
#include <thread>
#include <vector>


struct state_type
{
    std::mutex mutex;
    std::condition_variable changed;
    std::vector<maintenance_request> requests;
    bool hold = true;
    bool started = false;
    bool restart = false;
    size_t finished = 0;
};

maintenance_result execute(const maintenance_request &request, void *raw)
{
    auto &state = *static_cast<state_type *>(raw);
    {
        std::unique_lock<std::mutex> lock(state.mutex);
        state.requests.push_back(request);
        if (!state.restart && request.job_id == maintenance_job_id::auction_due_scan &&
            state.requests.size() == 1)
        {
            state.started = true;
            state.changed.notify_all();
            state.changed.wait(lock, [&] { return !state.hold; });
        }
    }
    maintenance_result result = {request.work_id, request.job_id,
                                 maintenance_outcome::complete, 0, 1, 0, 0, 0, {}};
    if (!state.restart && request.job_id == maintenance_job_id::auction_due_scan)
    {
        size_t auction_calls = 0;
        std::lock_guard<std::mutex> lock(state.mutex);
        for (const auto &seen : state.requests)
            if (seen.job_id == maintenance_job_id::auction_due_scan)
                ++auction_calls;
        if (auction_calls == 1)
            result.outcome = maintenance_outcome::retryable_failure;
        else if (auction_calls == 2)
        {
            result.outcome = maintenance_outcome::more;
            result.next_cursor = 77;
        }
    }
    {
        std::lock_guard<std::mutex> lock(state.mutex);
        ++state.finished;
        state.changed.notify_all();
    }
    return result;
}

// Keep the harness deterministic: only the auction job may be submitted, so no
// other job can leave durable request or completion state behind across the
// simulated restarts below.
size_t captures = 0;
bool auction_only(maintenance_request &request, void *)
{
    if (request.job_id != maintenance_job_id::auction_due_scan)
        return false;
    request.value_count = 2;
    request.values[0] = 1791849599 + ++captures;
    request.values[1] = captures * 11;
    return true;
}

bool catalogue_only(maintenance_request &request, void *)
{
    return request.job_id == maintenance_job_id::epic_task_catalog;
}

maintenance_result catalogue_page(const maintenance_request &request, void *raw)
{
    auto &state = *static_cast<state_type *>(raw);
    std::lock_guard<std::mutex> lock(state.mutex);
    state.requests.push_back(request);
    return {request.work_id, request.job_id, maintenance_outcome::more, 77, 1, 0, 0, 1, {77}};
}

template <typename Predicate> void wait_until(Predicate predicate)
{
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(5);
    while (!predicate())
    {
        assert(std::chrono::steady_clock::now() < deadline);
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
}

// A captured retry is a real startup input even after its worker was drained.
bool report_only(maintenance_request &request, void *)
{
    if (request.job_id != maintenance_job_id::web_status) return false;
    const char text[] = "old-season-captured-report";
    memcpy(request.content.data(), text, sizeof(text));
    request.content_size = sizeof(text) - 1;
    return true;
}
maintenance_result report_retry(const maintenance_request &request, void *raw)
{
    auto &state = *static_cast<state_type *>(raw);
    std::lock_guard<std::mutex> lock(state.mutex);
    assert(std::string(request.content.data(), request.content_size) == "old-season-captured-report");
    state.requests.push_back(request);
    return {request.work_id, request.job_id, maintenance_outcome::retryable_failure, 0, 0, 0, 11, 0, {}};
}
int pwipe_report(const char *path, const std::string &mode)
{
    state_type state;
    assert(maintenance_scheduler_set_state_path(path));
    assert(maintenance_scheduler_init(9, report_retry, &state, report_only));
    const auto initial = maintenance_scheduler_health_copy(0);
    const auto report = static_cast<size_t>(maintenance_job_id::web_status);
    maintenance_result results[MAINTENANCE_COMPLETION_MAX] = {};
    if (mode == "pwipe-fresh") {
        assert(initial.queued == 0 && initial.inflight == 0 && initial.completions == 0);
        for (const auto &job : initial.jobs) assert(job.work_id == 0 && job.cursor == 0);
    } else {
        if (mode == "pwipe-seed") {
            uint64_t tick = 0;
            wait_until([&] {
                if (maintenance_scheduler_health_copy(tick).jobs[report].submitted) return true;
                maintenance_scheduler_pulse(++tick, results, MAINTENANCE_COMPLETION_MAX);
                return false;
            });
        } else assert(mode == "pwipe-replay");
        wait_until([&] { return maintenance_scheduler_health_copy(0).completions == 1; });
        maintenance_scheduler_quiesce();
        assert(maintenance_scheduler_drain(3000));
        assert(maintenance_scheduler_pulse(0, results, MAINTENANCE_COMPLETION_MAX) == 1);
        assert(results[0].outcome == maintenance_outcome::retryable_failure);
        assert(state.requests.size() == 1);
    }
    maintenance_scheduler_shutdown();
    return 0;
}

int main(int argc, char **argv)
{
    if (argc == 3) return pwipe_report(argv[1], argv[2]);
    assert(argc == 2);
    size_t count = 0;
    const auto *registry = maintenance_registry(&count);
    assert(registry && count == MAINTENANCE_JOB_COUNT);
    const size_t lifecycle = static_cast<size_t>(maintenance_job_id::lifecycle_archive);
    assert(lifecycle < count && !registry[lifecycle].enabled);
    assert(!registry[static_cast<size_t>(maintenance_job_id::zone_trophy)].enabled);
    for (size_t index = 0; index < count; ++index)
    {
        assert(registry[index].row_budget <= MAINTENANCE_ROW_BUDGET_MAX);
        assert(registry[index].time_budget_usec <= MAINTENANCE_TIME_BUDGET_USEC_MAX);
        assert(maintenance_job_offset(registry[index].id, registry[index].cadence_ticks, 9) <
               registry[index].cadence_ticks);
        assert(maintenance_job_offset(registry[index].id, registry[index].cadence_ticks, 9) ==
               maintenance_job_offset(registry[index].id, registry[index].cadence_ticks, 9));
    }
    size_t distinct_offsets = 0;
    for (size_t index = 1; index < count; ++index)
        if (maintenance_job_offset(registry[index].id, registry[index].cadence_ticks, 9) !=
            maintenance_job_offset(registry[0].id, registry[0].cadence_ticks, 9))
            ++distinct_offsets;
    assert(distinct_offsets > 0);
    assert(!maintenance_activity_due(0, 0, 1));

    state_type state;
    assert(maintenance_scheduler_set_state_path(argv[1]));
    assert(maintenance_scheduler_init(9, execute, &state, auction_only));
    auto health = maintenance_scheduler_health_copy(0);
    assert(!health.jobs[lifecycle].enabled);
    const size_t auction = static_cast<size_t>(maintenance_job_id::auction_due_scan);
    const uint64_t first_tick = health.jobs[auction].next_due_tick;
    maintenance_result results[MAINTENANCE_COMPLETION_MAX] = {};
    maintenance_scheduler_pulse(first_tick, results, MAINTENANCE_COMPLETION_MAX);
    {
        std::unique_lock<std::mutex> lock(state.mutex);
        state.changed.wait(lock, [&] { return state.started; });
    }
    maintenance_scheduler_pulse(first_tick + registry[auction].cadence_ticks, results,
                                MAINTENANCE_COMPLETION_MAX);
    health = maintenance_scheduler_health_copy(first_tick + registry[auction].cadence_ticks);
    assert(health.jobs[auction].overlap_suppressed == 1);
    maintenance_scheduler_quiesce();
    assert(!maintenance_scheduler_drain(1));
    {
        std::lock_guard<std::mutex> lock(state.mutex);
        state.hold = false;
        state.changed.notify_all();
    }
	assert(maintenance_scheduler_drain(5000));
	maintenance_scheduler_resume();

    uint64_t tick = first_tick + registry[auction].cadence_ticks;
    // Stop pulsing as soon as the retry has been resubmitted. Any later pulse
    // could acknowledge its completion, which this phase must leave durable.
    wait_until([&] {
        if (maintenance_scheduler_health_copy(tick).jobs[auction].submitted >= 2)
            return true;
        maintenance_scheduler_pulse(++tick, results, MAINTENANCE_COMPLETION_MAX);
        return false;
    });
	{
		std::unique_lock<std::mutex> lock(state.mutex);
		state.changed.wait(lock, [&] { return state.finished >= 2; });
	}

    std::vector<maintenance_request> auction_requests;
    {
        std::lock_guard<std::mutex> lock(state.mutex);
        for (const auto &request : state.requests)
            if (request.job_id == maintenance_job_id::auction_due_scan)
                auction_requests.push_back(request);
    }
    assert(auction_requests.size() == 2);
    assert(auction_requests[0].work_id == auction_requests[1].work_id);
    assert(auction_requests[0].cursor == 0 && auction_requests[1].cursor == 0);
    // A failed output may have committed one of its effects. Retry must not
    // replace its captured counters/date under the same identity.
    assert(auction_requests[0].values == auction_requests[1].values);
    assert(auction_requests[0].scheduled_tick == auction_requests[1].scheduled_tick);
    assert(captures == 1);
    const uint64_t persisted_work_id = auction_requests[0].work_id;

    // The worker persisted the exact continuation before publishing its completion.
    // Shutdown here simulates a restart between those two operations.
    maintenance_scheduler_shutdown();
    assert(!maintenance_scheduler_health_copy(tick).running);

	state_type restarted;
	restarted.hold = false;
	restarted.restart = true;
	assert(maintenance_scheduler_init(9, execute, &restarted, auction_only));
	assert(maintenance_scheduler_health_copy(0).completions == 1);
	maintenance_scheduler_pulse(0, results, MAINTENANCE_COMPLETION_MAX);
	maintenance_scheduler_pulse(1, results, MAINTENANCE_COMPLETION_MAX);
	wait_until([&] {
		std::lock_guard<std::mutex> lock(restarted.mutex);
		return restarted.finished >= 1;
	});
	maintenance_request resumed = {};
	{
		std::lock_guard<std::mutex> lock(restarted.mutex);
		assert(restarted.requests.size() == 1);
		resumed = restarted.requests[0];
	}
	assert(resumed.job_id == maintenance_job_id::auction_due_scan);
	assert(resumed.work_id == persisted_work_id);
	assert(resumed.cursor == 77);
	assert(resumed.values != auction_requests[0].values); // a new continuation
	wait_until([&] { return maintenance_scheduler_health_copy(2).completions == 1; });
	maintenance_scheduler_pulse(2, results, MAINTENANCE_COMPLETION_MAX);
	health = maintenance_scheduler_health_copy(2);
	assert(!health.jobs[auction].active);
	assert(health.jobs[auction].cursor == 0);
    maintenance_scheduler_reset_for_tests();
	state_type acknowledged;
	acknowledged.hold = false;
	acknowledged.restart = true;
	assert(maintenance_scheduler_set_state_path(argv[1]));
	assert(maintenance_scheduler_init(9, execute, &acknowledged, auction_only));
	assert(maintenance_scheduler_health_copy(0).completions == 0);
	maintenance_scheduler_shutdown();
	maintenance_scheduler_reset_for_tests();

    // A catalogue prefix lives only on the game thread, unlike durable job effects.
    // Restart must discard both unacknowledged pages and acknowledged cursors.
    for (bool acknowledge : {false, true}) {
        const std::string path = std::string(argv[1]) + (acknowledge ? ".catalogue-ack" : ".catalogue-page");
        state_type catalogue;
        assert(maintenance_scheduler_set_state_path(path.c_str()));
        assert(maintenance_scheduler_init(9, catalogue_page, &catalogue, catalogue_only));
        const size_t id = static_cast<size_t>(maintenance_job_id::epic_task_catalog);
        const auto due = maintenance_scheduler_health_copy(0).jobs[id].next_due_tick;
        wait_until([&] {
            if (maintenance_scheduler_health_copy(due).completions == 1) return true;
            maintenance_scheduler_pulse(due, results, MAINTENANCE_COMPLETION_MAX);
            return false;
        });
        if (acknowledge) {
            maintenance_scheduler_quiesce();
            maintenance_scheduler_pulse(due, results, MAINTENANCE_COMPLETION_MAX);
        }
        maintenance_scheduler_shutdown();
        state_type fresh;
        assert(maintenance_scheduler_init(9, catalogue_page, &fresh, catalogue_only));
        auto restored = maintenance_scheduler_health_copy(0);
        assert(restored.completions == 0 && restored.jobs[id].cursor == 0 && restored.jobs[id].work_id == 0);
        wait_until([&] {
            if (maintenance_scheduler_health_copy(due).completions == 1) return true;
            maintenance_scheduler_pulse(restored.jobs[id].next_due_tick, results, MAINTENANCE_COMPLETION_MAX);
            return false;
        });
        maintenance_scheduler_shutdown();
        assert(fresh.requests.size() == 1 && fresh.requests[0].cursor == 0);
        assert(fresh.requests[0].work_id != catalogue.requests[0].work_id);
        maintenance_scheduler_reset_for_tests();
    }

	// A missing directory above the state file is made for the server user alone.
	const std::string made_directory = std::string(argv[1]) + ".made";
	const std::string made = made_directory + "/state";
	assert(maintenance_scheduler_set_state_path(made.c_str()));
	struct stat made_metadata = {};
	assert(stat(made_directory.c_str(), &made_metadata) == 0);
	assert(S_ISDIR(made_metadata.st_mode) && (made_metadata.st_mode & 0777) == 0700);
	assert(maintenance_scheduler_init(9, execute, &acknowledged, auction_only));
	maintenance_scheduler_pulse(first_tick, results, MAINTENANCE_COMPLETION_MAX);
	wait_until([&] { return maintenance_scheduler_health_copy(first_tick).completions == 1; });
	maintenance_scheduler_shutdown();
	maintenance_scheduler_reset_for_tests();
	assert(stat(made.c_str(), &made_metadata) == 0 && S_ISREG(made_metadata.st_mode));
	assert(acknowledged.requests.size() == 1);
	// Same instance, schedule, and tick after a fresh boot is a NEW sample.
	assert(acknowledged.requests[0].work_id != persisted_work_id);
	// Tick-derived legacy IDs always ended with a registered job's index + 1.
	assert((acknowledged.requests[0].work_id & 255) > MAINTENANCE_JOB_COUNT);

	// A state file that cannot be written is tried again after a pause. The worker
	// retried at once, and held a core for as long as the write kept failing. The
	// scheduler makes one missing directory level, not two.
	const std::string unwritable = std::string(argv[1]) + ".missing/below/state";
	assert(maintenance_scheduler_set_state_path(unwritable.c_str()));
	assert(maintenance_scheduler_init(9, execute, &acknowledged, auction_only));
	maintenance_scheduler_pulse(first_tick, results, MAINTENANCE_COMPLETION_MAX);
	wait_until([&] { return maintenance_scheduler_health_copy(first_tick).completions == 1; });
	assert(maintenance_scheduler_pulse(first_tick + 1, results, MAINTENANCE_COMPLETION_MAX) == 1);
	assert(results[0].outcome == maintenance_outcome::retryable_failure);
	const clock_t before = clock();
	std::this_thread::sleep_for(std::chrono::milliseconds(300));
	assert(clock() - before < CLOCKS_PER_SEC / 10);
	maintenance_scheduler_shutdown();
	maintenance_scheduler_reset_for_tests();
    return 0;
}
'''

with tempfile.TemporaryDirectory(prefix="duris-maintenance-scheduler-") as temp_dir:
    source = Path(temp_dir) / "scheduler_test.cpp"
    binary = Path(temp_dir) / "scheduler_test"
    source.write_text(HARNESS)
    mysql_cflags = shlex.split(subprocess.check_output(["mysql_config", "--cflags"], text=True))
    mysql_libs = shlex.split(subprocess.check_output(["mysql_config", "--libs"], text=True))
    subprocess.run(
        ["g++", "-std=c++20", "-Wall", "-Wextra", "-Wpedantic", "-Werror",
         "-pthread", "-Isrc", *mysql_cflags, str(source), rel("maintenance_scheduler.c"),
         rel("persistence_observability.c"), *mysql_libs, str(HARNESS_STUBS), "-o", str(binary)],
        cwd=ROOT, check=True,
    )
    state_file = Path(temp_dir) / "scheduler.state"
    subprocess.run([str(binary), str(state_file)], check=True, timeout=10)
    # Baseline: actual init replays a captured retry after a successful drain.
    wipe_root = Path(temp_dir) / "wipe"
    (wipe_root / "Players/wipers").mkdir(parents=True)
    wiper = wipe_root / "Players/wipers/wipe_it_all"
    shutil.copy2(ROOT / "Players/wipers/wipe_it_all", wiper)
    default_checkpoint = wipe_root / "runtime/maintenance-scheduler.state"
    for checkpoint in (default_checkpoint, Path(temp_dir) / "custom checkpoint",
                       wipe_root / "Players/a/scheduler.state"):
        subprocess.run([str(binary), str(checkpoint), "pwipe-seed"], check=True, timeout=10)
        subprocess.run([str(binary), str(checkpoint), "pwipe-replay"], check=True, timeout=10)
        checkpoint.unlink()
        subprocess.run([str(binary), str(checkpoint), "pwipe-seed"], check=True, timeout=10)
        original_checkpoint = checkpoint.read_bytes()
        temporary_checkpoint = Path(str(checkpoint) + ".tmp")
        temporary_checkpoint.write_bytes(original_checkpoint)
        wipe_env = dict(os.environ, COPYOVER_STATE_FILE=str(wipe_root / "copyover.dat"),
                        MAINTENANCE_STATE_FILE="" if checkpoint == default_checkpoint else str(checkpoint))
        subprocess.run([str(wiper), "--check"], cwd=wipe_root, env=wipe_env, check=True, stdout=subprocess.DEVNULL)
        assert checkpoint.read_bytes() == original_checkpoint
        subprocess.run([str(wiper)], cwd=wipe_root, env=wipe_env, check=True, stdout=subprocess.DEVNULL)
        assert not checkpoint.exists() and not temporary_checkpoint.exists()
        archives = [archive for archive in (wipe_root / "Players/Backup").glob("pwipe-maintenance.*")
                    if (archive / "source-path").read_text().strip() == str(checkpoint)]
        archive, = archives
        assert archive.stat().st_mode & 0o777 == 0o700
        assert (archive / "state").read_bytes() == (archive / "state.tmp").read_bytes() == original_checkpoint
        subprocess.run([str(binary), str(checkpoint), "pwipe-fresh"], check=True, timeout=10)
    print("Actual maintenance retry replay before wipe; default/custom/external/wipe-target state isolated byte-exact and fresh after wipe")
    current = state_file.read_bytes()
    assert current.startswith(b"DMSMNT4\0" + struct.pack("=II", 4, 13))
    job_size = (len(current) - 24) // 13
    assert 16 + job_size * 13 + 8 == len(current)
    # Versions 2 and 3 held the first 11 and 12 jobs; both still load.
    for version, jobs in ((2, 11), (3, 12)):
        legacy = bytearray(f"DMSMNT{version}\0".encode() + struct.pack("=II", version, jobs))
        legacy.extend(current[16:16 + job_size * jobs])
        checksum = 1469598103934665603
        for byte in legacy:
            checksum ^= byte
            checksum = (checksum * 1099511628211) & ((1 << 64) - 1)
        legacy.extend(struct.pack("=Q", checksum))
        state_file.write_bytes(legacy)
        subprocess.run([str(binary), str(state_file)], check=True, timeout=10)

for contract in (
    "MAINTENANCE_QUEUE_MAX", "maintenance_job_offset", "overlap_suppressed",
    "MAINTENANCE_RETRY_MAX_TICKS", "next_cursor", "time_budget_usec",
    "maintenance_scheduler_shutdown", "maintenance_scheduler_quiesce",
    "maintenance_scheduler_drain", "persist_state",
):
    assert contract in SOURCE or contract in (SRC / "maintenance_scheduler.h").read_text()

assert "J_NAME" not in SOURCE and "account_name" not in SOURCE

for aligned_callback in ("timers_activity();", "web_info();"):
    assert aligned_callback not in COMM
# Flat-file runs its auction and boon expiry on the game thread when the scheduler says the
# job is due; its worker completes the job without the SQL pool.
completions = COMM[COMM.index("static void maintenance_handle_completions("):]
completions = completions[:completions.index("\n}\n")]
flat_completions = completions[completions.index("#ifdef __NO_MYSQL__"):completions.index("#endif")]
for flat_callback in ("auction_houses_activity();", "boon_maintenance();"):
    assert COMM.count(flat_callback) == 1 and flat_callback in flat_completions
flat_execute = REPOSITORY[REPOSITORY.index("#ifdef __NO_MYSQL__\n\t// Flat-file expires"):]
assert flat_execute.index("maintenance_job_id::boon_scan") < flat_execute.index("sql_pool_acquire()")
assert "add_event(0, 0, 0, event_write_statistic" not in NEW_EVENTS
for forbidden_io in ("mysql_", "qry(", "redis_", "open(", "write(", "rename(", "fsync("):
    assert forbidden_io not in SNAPSHOT
for copyover_contract in (
    "maintenance_scheduler_quiesce();", "maintenance_scheduler_drain(3000)",
    "maintenance_scheduler_resume();",
):
    assert copyover_contract in COPYOVER
for repository_contract in (
    "ORDER BY id LIMIT ", "before_deadline(request)",
    "frag_cap_sql_load", "maintenance_cargo", "maintenance_boon",
    "frag_cap_settle", "frag_cap_sql_save(connection, state)",
    "atomic_replace", "sql_pool_acquire()",
):
    assert repository_contract in REPOSITORY
assert "frag_cap_runtime_refresh();" in COMM
print("bounded maintenance scheduler contracts passed")
