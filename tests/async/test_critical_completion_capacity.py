#!/usr/bin/env python3
"""Final notifications survive a full pulse buffer and are delivered once each.

Run the production coordinator on the one writer. The apply adapter controls
outcomes; observing the private queue makes ordering deterministic without sleeps
that assume the writer has finished.
"""

from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
HARNESS = r'''
#include "persistence/critical_command_coordinator.c"
#include <cassert>
#include <cstdio>
#include <map>
#include <set>

template <typename F> void wait_for(F condition) {
    const auto until = std::chrono::steady_clock::now() + std::chrono::seconds(10);
    while (!condition()) {
        assert(std::chrono::steady_clock::now() < until);
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
}
static size_t result_depth() {
    std::lock_guard<std::mutex> lock(coordinator_mutex);
    return completion_delivery.size(critical_completion_channel::execution);
}
static critical_command command(unsigned int tag) {
    critical_command result = {};
    result.schema_version = CRITICAL_COMMAND_SCHEMA_VERSION;
    assert(critical_operation_id_generate(&result.operation_id));
    result.type = critical_command_type::test;
    result.payload_version = 1;
    result.source_site = critical_source_site::command;
    result.deadline_class = critical_deadline_class::interactive;
    result.keys = {{critical_entity_type::player, tag}};
    result.payload = {uint8_t(tag)};
    return result;
}
static critical_apply_result apply(const critical_command &cmd, void *) {
    if (cmd.payload[0] == 200 || cmd.payload[0] == 202) {
        critical_apply_result result = {cmd.payload[0] == 200 ? critical_apply_outcome::applied :
                                       critical_apply_outcome::already_applied, 73, 0};
        result.result_size = 4096;
        static_assert(CRITICAL_COMPLETION_RESULT_MAX_BYTES >= 4096);
        for (size_t n = 0; n < result.result_size; ++n)
            result.result_payload[n] = static_cast<uint8_t>((n * 7 + 3) % 251);
        return result;
    }
    if (cmd.payload[0] == 2)
        return {critical_apply_outcome::terminal_failure, 73, 123};
    if (cmd.payload[0] % 2)
        return {critical_apply_outcome::terminal_failure, 0, 45};
    return {critical_apply_outcome::applied, 1, 0};
}
static player_save_apply_result apply_save(const player_snapshot &snapshot, void *) {
    return {player_save_apply_outcome::applied, snapshot.revision, 0};
}
static void capacity_case(size_t capacity) {
    assert(critical_command_coordinator_init(apply, nullptr));
    // Fill the output with mixed successful and terminal results, then one more.
    std::map<std::string, critical_apply_outcome> expected;
    for (size_t i = 0; i < capacity; ++i) {
        const auto other = command(10 + i);
        expected.emplace(operation_key(other.operation_id), i % 2 ?
                         critical_apply_outcome::terminal_failure : critical_apply_outcome::applied);
        assert(critical_command_coordinator_submit(other) == critical_submit_result::accepted);
    }
    wait_for([&] { return result_depth() == capacity; });
    const auto last = command(2);
    expected.emplace(operation_key(last.operation_id), critical_apply_outcome::terminal_failure);
    assert(critical_command_coordinator_submit(last) == critical_submit_result::accepted);
    wait_for([&] { return result_depth() == capacity + 1; });
    critical_completion delivered[64] = {};
    std::set<std::string> seen;
    const auto consume = [&](size_t count) {
        for (size_t i = 0; i < count; ++i) {
            const auto id = operation_key(delivered[i].operation_id);
            assert(expected.at(id) == delivered[i].outcome);
            assert(seen.insert(id).second);
        }
    };
    assert(critical_command_coordinator_pulse(capacity ? delivered : nullptr, capacity) == capacity);
    consume(capacity);
    assert(result_depth() == 1);
    assert(critical_command_coordinator_is_fenced(last.keys[0], nullptr));
    // Repeated empty pulses cannot consume it.
    for (int i = 0; i < 3; ++i)
        assert(critical_command_coordinator_pulse(nullptr, 0) == 0);
    assert(result_depth() == 1);
    assert(critical_command_coordinator_pulse(delivered, 1) == 1);
    consume(1);
    assert(critical_operation_id_equal(delivered[0].operation_id, last.operation_id));
    assert(delivered[0].error_code == 123 && delivered[0].durable_revision == 73);
    assert(seen.size() == expected.size());
    assert(critical_command_coordinator_pulse(delivered, 64) == 0);
    const auto health = critical_command_coordinator_health_copy();
    assert(health.terminal_failures == capacity / 2 + 1);
    assert(health.completed == capacity + 1);
    assert(!critical_command_coordinator_is_fenced(last.keys[0], nullptr));
    critical_completion cached = {};
    assert(critical_command_coordinator_get_completed(last.operation_id, &cached));
    assert(critical_command_coordinator_submit(last) == critical_submit_result::attached);
    printf("capacity=%zu: all %zu identities delivered once\n", capacity, seen.size());
    critical_command_coordinator_shutdown();
}
static void large_result_case() {
    assert(critical_command_coordinator_init(apply, nullptr));
    for (unsigned int tag : {200, 202}) {
        const auto large = command(tag);
        assert(critical_command_coordinator_submit(large) == critical_submit_result::accepted);
        wait_for([] { return result_depth() == 1; });
        critical_completion delivered = {};
        assert(critical_command_coordinator_pulse(&delivered, 1) == 1);
        assert(critical_operation_id_equal(delivered.operation_id, large.operation_id));
        assert(delivered.outcome == (tag == 200 ? critical_apply_outcome::applied :
                                    critical_apply_outcome::already_applied));
        assert(delivered.result_size == 4096 && delivered.durable_revision == 73);
        for (size_t n = 0; n < delivered.result_size; ++n)
            assert(delivered.result_payload[n] == static_cast<uint8_t>((n * 7 + 3) % 251));
        critical_completion cached = {};
        assert(critical_command_coordinator_get_completed(large.operation_id, &cached));
        assert(cached.result_size == delivered.result_size);
        assert(cached.result_payload == delivered.result_payload);
    }
    critical_command_coordinator_shutdown();
    puts("4096-byte fresh and replay completions survive delivery and retained lookup");
}
int main() {
    assert(player_save_worker_init(apply_save, nullptr));
    large_result_case();
    for (size_t capacity : {0, 1, 63})
        capacity_case(capacity);
    player_save_worker_reset_for_tests();
}
'''

with tempfile.TemporaryDirectory(prefix="duris-completion-capacity-") as directory:
    temporary = Path(directory)
    source = temporary / "capacity.cpp"
    binary = temporary / "capacity"
    source.write_text(HARNESS)
    subprocess.run([
        "g++", "-std=c++20", "-g", "-Og", "-Wall", "-Wextra", "-Werror", "-pthread",
        "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-fno-pie", "-no-pie",
        "-Isrc", str(source), "src/persistence/critical_command.c",
        "src/player/player_save_worker.c",
        "src/persistence/persistence_observability.c", "-lz", "-lcrypto", "-lmysqlclient",
        "-o", str(binary),
    ], cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True, timeout=60)

print("critical completion capacity regression passed")
