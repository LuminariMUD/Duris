#!/usr/bin/env python3
"""Run the actual recurring phase with ready results from the shared writer.

The virtual pulse clock measures publication/output cadence without scheduler
jitter. The real coordinator keeps fences until the game-thread poll; unrelated
recurring owners are spies so their cadence and ordering can be checked.
"""

from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, extract_function


HARNESS = r'''
#include "persistence/critical_command_coordinator.c"
#include <cassert>
#include <cstdio>
#include <ctime>

static int pulse = 0;
static constexpr int WAIT_SEC = 4;
static uint64_t ne_event_tick = 0;
struct game_loop_pulse_context { uint64_t loop_tick = 0; };
struct player_load_result { uint64_t request_id = 0; };
struct descriptor { uint64_t player_load_request_id; descriptor *next; };
using P_desc = descriptor *;
static P_desc descriptor_list = nullptr;
struct maintenance_result {};
static constexpr size_t MAINTENANCE_COMPLETION_MAX = 1;

static std::vector<std::string> calls;
static bool events_finished = false, receipt_queued = false;
static unsigned int handled = 0, output_count = 0;
static int published_at = -1, visible_at = -1;
static uint64_t loop_monotonic_us() { return ne_event_tick * 250000; }
static uint64_t latency_trace_elapsed_us(uint64_t a, uint64_t b) { return b - a; }
static void latency_trace_record(const char *, uint64_t, uint64_t) {}

#define SPY(name) static void name() { calls.emplace_back(#name); }
SPY(gmcp_flush_initial_states)
SPY(gmcp_flush_dirty_rooms)
SPY(gmcp_flush_dirty_ship_contacts)
SPY(gmcp_flush_dirty_ship_info)
SPY(flush_pending_ship_saves)
SPY(retry_unplaced_ships)
SPY(locker_async_pulse)
SPY(critical_gameplay_publish_outbox)
SPY(player_save_pipeline_pulse)
SPY(divine_boon_runtime_pulse)
SPY(persistence_pulse_character_saves)
SPY(information_cache_pulse)
SPY(help_cache_pulse)
SPY(collector_catalog_cache_pulse)
SPY(collector_maintenance_pulse)
SPY(collector_presence_pulse)
SPY(collector_service_pulse)
SPY(account_recovery_pulse)
SPY(redis_world_recovery_pulse)
SPY(sql_async_pulse)
SPY(divine_trade_runtime_retire_pulse)
SPY(sql_ship_write_pulse)
SPY(artifact_guild_transaction_pulse)
SPY(sql_mud_info_refresh)
static void divine_boon_selection_pulse(int64_t) { calls.emplace_back("selection"); }
static size_t player_load_pipeline_pulse(player_load_result *, size_t) {
    calls.emplace_back("loads"); return 0;
}
static void account_player_load_complete(P_desc, player_load_result) { assert(false); }
static bool player_load_offline_complete(player_load_result &) { assert(false); return false; }
static void player_load_pipeline_note_stale() { assert(false); }
static size_t maintenance_scheduler_pulse(uint64_t, maintenance_result *, size_t) {
    calls.emplace_back("maintenance"); return 0;
}
static void maintenance_handle_completions(const maintenance_result *, size_t) {}

static void critical_gameplay_handle_completions(const critical_completion *results, size_t count) {
    assert(events_finished);
    calls.emplace_back("critical");
    for (size_t i = 0; i < count; ++i) {
        assert(results[i].durable_revision == 7);
        ++handled;
        receipt_queued = true;
        published_at = pulse;
    }
}

// PHASE

static critical_apply_result apply(const critical_command &command, void *) {
    return {static_cast<critical_apply_outcome>(command.payload[0]), 7, 0};
}
static player_save_apply_result save(const player_snapshot &snapshot, void *) {
    return {player_save_apply_outcome::applied, snapshot.revision, 0};
}
static void wait_ready() {
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(10);
    for (;;) {
        {
            std::lock_guard<std::mutex> lock(coordinator_mutex);
            if (completion_delivery.size(critical_completion_channel::execution)) return;
        }
        assert(std::chrono::steady_clock::now() < deadline);
        std::this_thread::yield();
    }
}
static void tick(int number) {
    pulse = number;
    ne_event_tick = number;
    calls.clear();
    events_finished = false;
    // The real top-level order is pinned by test_game_loop_phase_contract.py.
    if (receipt_queued) {
        receipt_queued = false;
        ++output_count;
        visible_at = number;
    }
    events_finished = true;
    game_loop_pulse_context context{static_cast<uint64_t>(number)};
    run_recurring_persistence_phase(context);
    std::vector<std::string> expected;
    if (!(pulse % 2))
        expected = {"gmcp_flush_initial_states", "gmcp_flush_dirty_rooms",
                    "gmcp_flush_dirty_ship_contacts", "gmcp_flush_dirty_ship_info",
                    "flush_pending_ship_saves", "retry_unplaced_ships", "locker_async_pulse"};
    expected.emplace_back("critical");
    if (!(pulse % 2)) {
        const std::vector<std::string> periodic = {
            "critical_gameplay_publish_outbox", "player_save_pipeline_pulse",
            "divine_boon_runtime_pulse", "selection", "persistence_pulse_character_saves", "loads",
            "information_cache_pulse", "help_cache_pulse", "collector_catalog_cache_pulse",
            "collector_maintenance_pulse", "collector_presence_pulse", "collector_service_pulse",
            "account_recovery_pulse", "redis_world_recovery_pulse"};
        expected.insert(expected.end(), periodic.begin(), periodic.end());
    }
    expected.insert(expected.end(), {"sql_async_pulse", "divine_trade_runtime_retire_pulse",
                                   "sql_ship_write_pulse", "artifact_guild_transaction_pulse",
                                   "maintenance"});
    assert(calls == expected);
}
static void run_case(int submitted_after, critical_apply_outcome outcome) {
    assert(critical_command_coordinator_init(apply, nullptr));
    handled = output_count = 0;
    published_at = visible_at = -1;
    receipt_queued = false;
    critical_command command = {};
    command.schema_version = CRITICAL_COMMAND_SCHEMA_VERSION;
    assert(critical_operation_id_generate(&command.operation_id));
    command.type = critical_command_type::test;
    command.payload_version = 1;
    command.source_site = critical_source_site::command;
    command.deadline_class = critical_deadline_class::interactive;
    command.keys = {{critical_entity_type::player, 42}};
    command.payload = {static_cast<uint8_t>(outcome)};
    assert(critical_command_coordinator_submit(command) == critical_submit_result::accepted);
    wait_ready();
    assert(handled == 0 && output_count == 0);
    assert(critical_command_coordinator_is_fenced(command.keys[0], nullptr));
    tick(submitted_after + 1);
    assert(handled == 1 && output_count == 0);
    assert(!critical_command_coordinator_is_fenced(command.keys[0], nullptr));
    tick(submitted_after + 2);
    tick(submitted_after + 3);
    assert(handled == 1 && output_count == 1);
    printf("submission phase %d ms: publication %d ms, simulated output %d ms\n",
           submitted_after * 250 + 1, (published_at - submitted_after) * 250 - 1,
           (visible_at - submitted_after) * 250 - 1);
    critical_command_coordinator_shutdown();
}
int main() {
    assert(player_save_worker_init(save, nullptr));
    for (auto outcome : {critical_apply_outcome::applied, critical_apply_outcome::already_applied,
                         critical_apply_outcome::terminal_failure})
        for (int submitted_after : {0, 1}) run_case(submitted_after, outcome);
    player_save_worker_reset_for_tests();
}
'''


out = ROOT / "bin/tests"
out.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="critical-cadence-", dir=out) as directory:
    source = Path(directory) / "cadence.cpp"
    binary = Path(directory) / "cadence"
    source.write_text(HARNESS.replace(
        "// PHASE", extract_function("net/comm.c", "static void run_recurring_persistence_phase(")
    ))
    subprocess.run([
        "g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-g", "-Og", "-pthread",
        "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-fno-pie", "-no-pie",
        "-Isrc", str(source), "src/persistence/critical_command.c",
        "src/player/player_save_worker.c", "src/persistence/persistence_observability.c",
        "-lz", "-lcrypto", "-lmysqlclient", "-o", str(binary),
    ], cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True, timeout=30)

print("critical publication cadence passed: both pulse parities, success/replay/failure, fences and ordering")
