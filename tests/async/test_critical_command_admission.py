#!/usr/bin/env python3
"""Submitting a critical command never waits: it queues on the writer with no file I/O."""

from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, rel


HARNESS = r'''
#include "persistence/critical_command_coordinator.h"
#include "player/player_save_worker.h"

#include <algorithm>
#include <atomic>
#include <cassert>
#include <chrono>
#include <condition_variable>
#include <cstdio>
#include <mutex>
#include <thread>
#include <unistd.h>
#include <vector>

static std::atomic<unsigned int> submitter_file_io{0};
static std::atomic<unsigned int> applied{0};
static std::thread::id submitter;
static std::mutex hold_mutex;
static std::condition_variable hold_changed;
static bool hold = false;

extern "C" int __real_fsync(int);
extern "C" int __wrap_fsync(int fd)
{
    if (std::this_thread::get_id() == submitter)
        ++submitter_file_io;
    return __real_fsync(fd);
}

extern "C" ssize_t __real_write(int, const void *, size_t);
extern "C" ssize_t __wrap_write(int fd, const void *data, size_t size)
{
    if (fd > 2 && std::this_thread::get_id() == submitter)
        ++submitter_file_io;
    return __real_write(fd, data, size);
}

static critical_command command(unsigned int tag)
{
    critical_command result = {};
    result.schema_version = CRITICAL_COMMAND_SCHEMA_VERSION;
    assert(critical_operation_id_generate(&result.operation_id));
    result.type = critical_command_type::test;
    result.payload_version = 1;
    result.source_site = critical_source_site::command;
    result.deadline_class = critical_deadline_class::interactive;
    result.keys = {{critical_entity_type::player, 1000 + tag}};
    result.payload = {static_cast<uint8_t>(tag)};
    return result;
}

// The writer is stalled, as it is behind a locked table or a lost database.
static critical_apply_result apply(const critical_command &, void *)
{
    std::unique_lock<std::mutex> lock(hold_mutex);
    hold_changed.wait(lock, [] { return !hold; });
    ++applied;
    return {critical_apply_outcome::applied, 1, 0};
}

static player_save_apply_result apply_save(const player_snapshot &snapshot, void *)
{
    return {player_save_apply_outcome::applied, snapshot.revision, 0};
}

static unsigned long long percentile(std::vector<unsigned long long> values,
                                     unsigned int percentage)
{
    std::sort(values.begin(), values.end());
    const size_t index = (values.size() - 1) * percentage / 100;
    return values[index];
}

int main(int argc, char **argv)
{
    assert(argc == 2);
    submitter = std::this_thread::get_id();
    assert(player_save_worker_init(apply_save, nullptr));
    // A journal directory is only read for an older server's journal.
    assert(critical_command_coordinator_init(argv[1], apply, nullptr));
    {
        std::lock_guard<std::mutex> lock(hold_mutex);
        hold = true;
    }
    std::vector<critical_command> submitted;
    std::vector<unsigned long long> submit_latencies;
    for (unsigned int tag = 1; tag <= 33; ++tag)
    {
        submitted.push_back(command(tag));
        const auto started = std::chrono::steady_clock::now();
        assert(critical_command_coordinator_submit(submitted.back()) ==
               critical_submit_result::accepted);
        submit_latencies.push_back(static_cast<unsigned long long>(
            std::chrono::duration_cast<std::chrono::microseconds>(
                std::chrono::steady_clock::now() - started)
                .count()));
    }
    auto health = critical_command_coordinator_health_copy();
    assert(health.inflight == 33);
    assert(critical_command_coordinator_durability(submitted[0].operation_id) ==
           critical_command_durability::awaiting_durability);
    assert(submitter_file_io == 0);
    assert(critical_command_journal_health_copy().records == 0);
    assert(percentile(submit_latencies, 95) < 40000);
    printf("stalled_writer_submit: n=%zu p50_us=%llu p95_us=%llu p99_us=%llu file_io=%u\n",
           submit_latencies.size(), percentile(submit_latencies, 50),
           percentile(submit_latencies, 95), percentile(submit_latencies, 99),
           submitter_file_io.load());
    {
        std::lock_guard<std::mutex> lock(hold_mutex);
        hold = false;
        hold_changed.notify_all();
    }
    assert(critical_command_coordinator_drain(15000));
    assert(applied == 33);
    assert(critical_command_coordinator_durability(submitted[0].operation_id) ==
           critical_command_durability::durable);
    assert(critical_command_journal_health_copy().records == 0);
    critical_command_coordinator_shutdown();
    player_save_worker_reset_for_tests();
}
'''


with tempfile.TemporaryDirectory(prefix="duris-critical-admission-") as directory:
    temporary = Path(directory)
    source = temporary / "admission.cpp"
    binary = temporary / "admission"
    source.write_text(HARNESS, encoding="utf-8")
    subprocess.run(
        [
            "g++", "-std=c++20", "-g", "-Og", "-Wall", "-Wextra", "-Wpedantic",
            "-Werror", "-pthread", "-fsanitize=address,undefined",
            "-fno-omit-frame-pointer", "-fno-pie", "-no-pie", "-Isrc", str(source),
            rel("critical_command.c"), rel("critical_command_journal.c"),
            rel("critical_command_coordinator.c"), rel("player_save_worker.c"),
            rel("persistence_observability.c"), "-lz", "-lcrypto", "-lmysqlclient",
            "-Wl,--wrap=fsync", "-Wl,--wrap=write", "-o", str(binary),
        ],
        cwd=ROOT,
        check=True,
    )
    subprocess.run([str(binary), str(temporary / "journal")], check=True, timeout=60)

# Every domain adapter keeps its pending state for each result that keeps the operation.
for relative in (
    "src/world/zone_touch_transaction.c",
    "src/world/epic_transaction.c",
    "src/economy/shop_trade_transaction.c",
    "src/economy/auction_transaction.c",
    "src/economy/boon_shop_transaction.c",
    "src/economy/boon_reward_transaction.c",
    "src/economy/currency_transaction.c",
    "src/guild/artifact_guild_transaction.c",
    "src/combat/combat_outcome_transaction.c",
    "src/persistence/corpse_lifecycle_transaction.c",
    "src/item/item_transfer_synthetic.c",
    "src/account/session_audit_transaction.c",
):
    assert "critical_submit_result_keeps_operation" in (ROOT / relative).read_text()

print("a critical command submitted to a stalled writer queues at once with no file I/O")
