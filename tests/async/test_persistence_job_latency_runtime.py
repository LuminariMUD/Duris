#!/usr/bin/env python3
"""Execute the real recurring phase with delayed jobs and the real latency tracer."""

from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, SRC, extract_function


SIMPLE_JOBS = """
gmcp_flush_initial_states gmcp_flush_dirty_rooms gmcp_flush_dirty_ship_contacts
gmcp_flush_dirty_ship_info flush_pending_ship_saves retry_unplaced_ships
locker_async_pulse combat_outcome_transaction_pulse critical_gameplay_publish_outbox
player_save_pipeline_pulse divine_boon_runtime_pulse frag_cap_runtime_pulse
persistence_pulse_character_saves information_cache_pulse help_cache_pulse
collector_catalog_cache_pulse collector_maintenance_pulse collector_presence_pulse
collector_service_pulse account_recovery_pulse redis_world_recovery_pulse
sql_async_pulse divine_trade_runtime_retire_pulse sql_ship_write_pulse
artifact_guild_transaction_pulse arti_cache_retry sql_mud_info_refresh
""".split()
OTHER_JOBS = """
critical_command_coordinator_pulse critical_gameplay_handle_completions
player_load_pipeline_pulse player_load_delivery divine_boon_selection_pulse
maintenance_scheduler_pulse maintenance_handle_completions
""".split()

PREAMBLE = r'''
#include "persistence/latency_trace.h"
#include <cassert>
#include <cstdarg>
#include <ctime>
#include <string>
#include <utility>
#include <vector>

static uint64_t now_us = 1000000;
static bool clock_failed = false;
static const char *delayed_job = "";
static uint64_t delay_us = 0;
static std::vector<std::string> reports;
static std::vector<std::string> calls;
static int pulse = 0;
static constexpr int WAIT_SEC = 4;
static constexpr int LOG_STATUS = 1;
static constexpr size_t MAINTENANCE_COMPLETION_MAX = 4;
static constexpr uint64_t ne_event_tick = UINT64_C(1) << 42;
struct game_loop_pulse_context
{
    uint64_t loop_tick = ne_event_tick;
    uint64_t loop_start_mono_us = 998877;
    uint64_t persistence_us = 0;
};
struct critical_completion {};
struct maintenance_result {};
struct player_load_result { uint64_t request_id = 0; };
struct descriptor
{
    uint64_t player_load_request_id = 77;
    descriptor *next = nullptr;
};
using P_desc = descriptor *;
static descriptor online;
static P_desc descriptor_list = &online;
static unsigned int delivered = 0, offline = 0, stale = 0;

static uint64_t loop_monotonic_us() { return clock_failed ? 0 : now_us; }
static void work(const char *name)
{
    calls.emplace_back(name);
    if (name == std::string(delayed_job)) now_us += delay_us;
}
static void logit(int, const char *format, ...)
{
    char buffer[512];
    va_list args;
    va_start(args, format);
    vsnprintf(buffer, sizeof buffer, format, args);
    va_end(args);
    reports.emplace_back(buffer);
    now_us += 9000; // Reporting must not look like work by the next job.
}
static size_t critical_command_coordinator_pulse(critical_completion *, size_t capacity)
{
    assert(capacity == 64);
    work("critical_command_coordinator_pulse");
    return 1;
}
static void critical_gameplay_handle_completions(critical_completion *, size_t count)
{
    assert(count == 1);
    work("critical_gameplay_handle_completions");
}
static void divine_boon_selection_pulse(int64_t) { work("divine_boon_selection_pulse"); }
static size_t player_load_pipeline_pulse(player_load_result *results, size_t capacity)
{
    assert(capacity == 32);
    results[0].request_id = 77;
    results[1].request_id = 78;
    results[2].request_id = 79;
    work("player_load_pipeline_pulse");
    return 3;
}
static void account_player_load_complete(P_desc desc, player_load_result &&result)
{
    assert(desc == &online && result.request_id == 77);
    ++delivered;
    work("player_load_delivery");
}
static bool player_load_offline_complete(player_load_result &result)
{
    assert(result.request_id == 78 || result.request_id == 79);
    ++offline;
    return result.request_id == 78;
}
static void player_load_pipeline_note_stale() { ++stale; }
static size_t maintenance_scheduler_pulse(uint64_t tick, maintenance_result *, size_t capacity)
{
    assert(tick == ne_event_tick && capacity == MAINTENANCE_COMPLETION_MAX);
    work("maintenance_scheduler_pulse");
    return 1;
}
static void maintenance_handle_completions(maintenance_result *, size_t count)
{
    assert(count == 1);
    work("maintenance_handle_completions");
}
'''

CHECKS = r'''
static const latency_section *section(const latency_trace_snapshot &snapshot, const char *name)
{
    for (int i = 0; i < snapshot.section_count; ++i)
        if (name == std::string(snapshot.sections[i].name)) return &snapshot.sections[i];
    return nullptr;
}

static latency_trace_snapshot run(const char *job, uint64_t duration, int current_pulse)
{
    delayed_job = job;
    delay_us = duration;
    pulse = current_pulse;
    now_us = 1000000;
    reports.clear();
    calls.clear();
    delivered = offline = stale = 0;
    latency_trace_reset();
    game_loop_pulse_context ctx;
    run_recurring_persistence_phase(ctx);
    latency_trace_snapshot snapshot{};
    latency_trace_snapshot_take_and_reset(&snapshot);
    const auto *total = section(snapshot, "recurring_persistence");
    if (clock_failed) assert(!total && ctx.persistence_us == LATENCY_TRACE_DURATION_INVALID);
    else assert(total && total->max_us == ctx.persistence_us);
    assert(snapshot.dropped_section_samples == 0);
    return snapshot;
}

int main()
{
    const char *jobs[] = {JOB_NAMES};
    for (const char *job : jobs)
    {
        const auto snapshot = run(job, 277173, 0);
        assert(delivered == 1 && offline == 2 && stale == 1);
        for (const char *name : jobs)
        {
            const auto *sample = section(snapshot, name);
            assert(sample && sample->count == 1);
            assert(sample->max_us == (std::string(job) == name ? 277173 : 0));
        }
        assert(reports.size() == 1);
        const auto &report = reports.front();
        assert(report.find("PERSISTENCE JOB SLOW:") == 0);
        assert(report.find(std::string("boot=") + latency_trace_boot_id()) != std::string::npos);
        assert(report.find("tick=4398046511104 pulse_start_mono_us=998877") != std::string::npos);
        assert(report.find(std::string("job=") + job + " duration_us=277173") != std::string::npos);
        bool correlated = false;
        for (int i = 0; i < snapshot.top_count; ++i)
            if (std::string(snapshot.top[i].name) == job)
                correlated = snapshot.top[i].tick == ne_event_tick;
        assert(correlated);
    }

    // Retain all phase names alongside every job in the same bounded window.
    run("", 0, 0);
    assert(reports.empty());
    const char *phases[] = {"connections", "commands", "prompts", "ne_events", "activities",
                          "combat", "affect_and_points", "affect_update", "point_update", "total_tick"};
    game_loop_pulse_context ctx;
    run_recurring_persistence_phase(ctx);
    for (const char *name : phases) latency_trace_record(name, 1, ne_event_tick);
    latency_trace_snapshot full{};
    latency_trace_snapshot_take_and_reset(&full);
    assert(full.dropped_section_samples == 0);
    for (const char *name : jobs) assert(section(full, name));
    for (const char *name : phases) assert(section(full, name));
    assert(section(full, "gmcp_flush") && section(full, "gmcp_protocol"));

    // Half-second, second and minute jobs keep their existing cadence.
    auto odd = run("sql_async_pulse", 50000, 1);
    assert(reports.size() == 1);
    assert(section(odd, "sql_async_pulse")->max_us == 50000);
    assert(!section(odd, "gmcp_flush") && !section(odd, "gmcp_protocol"));
    assert(!section(odd, "player_save_pipeline_pulse") && !section(odd, "player_load_delivery"));
    assert(!section(odd, "arti_cache_retry") && !section(odd, "sql_mud_info_refresh"));
    assert(delivered == 0 && offline == 0 && stale == 0);
    auto even = run("", 0, 2);
    assert(section(even, "gmcp_flush"));
    assert(!section(even, "arti_cache_retry") && !section(even, "sql_mud_info_refresh"));
    auto second = run("", 0, WAIT_SEC);
#ifndef __NO_MYSQL__
    assert(section(second, "arti_cache_retry"));
#endif
    assert(!section(second, "sql_mud_info_refresh"));
    run("sql_async_pulse", 49999, 1);
    assert(reports.empty());

    // Failed clocks are excluded from the trace and never emit a huge stall.
    clock_failed = true;
    auto invalid = run("help_cache_pulse", 277173, 0);
    assert(reports.empty() && invalid.invalid_clock_samples > 0);
    assert(invalid.section_count == 0);
    puts("persistence job latency runtime checks passed");
}
'''
# The MariaDB-only calls must disappear with the flatfile build, as in comm.c.
MYSQL_JOBS = {"sql_ship_write_pulse", "arti_cache_retry"}
phase = extract_function("comm.c", "static void run_recurring_persistence_phase(")

(ROOT / "bin").mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix="persistence-job-latency-", dir=ROOT / "bin") as directory:
    temporary = Path(directory)
    for backend in ("mariadb", "flatfile"):
        jobs = [name for name in SIMPLE_JOBS + OTHER_JOBS
                if backend == "mariadb" or name not in MYSQL_JOBS]
        stubs = "\n".join(f'static void {name}() {{ work("{name}"); }}'
                          for name in SIMPLE_JOBS if name in jobs)
        checks = CHECKS.replace("JOB_NAMES", ", ".join(f'"{name}"' for name in jobs))
        harness = temporary / f"{backend}.cc"
        binary = temporary / backend
        harness.write_text(PREAMBLE + stubs + "\n" + phase + "\n" + checks)
        subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-pthread",
                        *(["-D__NO_MYSQL__"] if backend == "flatfile" else []),
                        "-I", str(SRC), str(harness), str(SRC / "latency_trace.c"),
                        "-o", str(binary)], check=True)
        subprocess.run([str(binary)], check=True)
