#!/usr/bin/env python3
"""Identity, capture order on the writer, fence and bound contracts."""

from _paths import SRC, rel
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
COMMAND = (SRC / "critical_command.c").read_text()
COORDINATOR = (SRC / "critical_command_coordinator.c").read_text()
HEADER = (SRC / "critical_command_coordinator.h").read_text()
COMPLETION = (SRC / "persistence/critical_command_completion.h").read_text()
WORKER = (SRC / "player_save_worker.h").read_text()
PIPELINE = (ROOT / "docs/persistence/CRITICAL_COMMAND_PIPELINE.md").read_text()


HARNESS = r'''
#include "persistence/critical_command_coordinator.h"
#include "player/player_save_worker.h"

#include <cassert>
#include <chrono>
#include <condition_variable>
#include <fcntl.h>
#include <map>
#include <mutex>
#include <set>
#include <string>
#include <thread>
#include <unistd.h>
#include <vector>

struct apply_state
{
    std::mutex mutex;
    std::condition_variable changed;
    std::map<unsigned int, unsigned int> attempts;
    // Everything the writer applied, saves and commands, in order.
    std::vector<std::string> order;
    bool hold_save = false;
    bool save_held = false;
    bool hold_all = false;
    bool release_all = false;
    bool already_applied = false;
    bool uncertain_started = false;
};

apply_state state;

critical_command make_command(unsigned int tag, std::vector<critical_entity_key> keys)
{
    critical_command command = {};
    command.schema_version = CRITICAL_COMMAND_SCHEMA_VERSION;
    assert(critical_operation_id_generate(&command.operation_id));
    command.type = critical_command_type::test;
    command.payload_version = 1;
    command.source_site = critical_source_site::command;
    command.deadline_class = critical_deadline_class::interactive;
    command.keys = std::move(keys);
    command.payload = {static_cast<uint8_t>(tag)};
    return command;
}

critical_apply_result apply(const critical_command &command, void *raw)
{
    auto &applied = *static_cast<apply_state *>(raw);
    const unsigned int tag = command.payload[0];
    std::unique_lock<std::mutex> lock(applied.mutex);
    const unsigned int attempt = ++applied.attempts[tag];
    if (applied.hold_all)
        applied.changed.wait(lock, [&] { return applied.release_all; });
    applied.order.push_back("c" + std::to_string(tag));
    applied.changed.notify_all();
    // Tags 16 and 17 never learn their outcome.
    if (tag == 16 || tag == 17)
    {
        applied.uncertain_started = true;
        return {tag == 16 ? critical_apply_outcome::ambiguous_commit :
                critical_apply_outcome::retryable_failure, 0, 2013};
    }
    if (tag == 4 && attempt == 1)
        return {critical_apply_outcome::ambiguous_commit, 0, 2013};
    if (tag == 18)
        return {critical_apply_outcome::terminal_failure, 0, 1062};
    return {applied.already_applied ? critical_apply_outcome::already_applied :
            critical_apply_outcome::applied, 1, 0};
}

player_save_apply_result apply_save(const player_snapshot &snapshot, void *)
{
    std::unique_lock<std::mutex> lock(state.mutex);
    if (state.hold_save)
    {
        state.save_held = true;
        state.changed.notify_all();
        state.changed.wait(lock, [] { return !state.hold_save; });
    }
    state.order.push_back("p" + std::to_string(snapshot.pid));
    state.changed.notify_all();
    return {player_save_apply_outcome::applied, snapshot.revision, 0};
}

player_snapshot save_of(int pid)
{
    player_snapshot snapshot = {};
    snapshot.schema_version = PLAYER_SNAPSHOT_SCHEMA_VERSION;
    snapshot.pid = pid;
    snapshot.revision = 1;
    snapshot.components = PLAYER_CHECKPOINT_COMPONENT_ALL;
    snapshot.encoded_size_bound = 128;
    return snapshot;
}

template <typename Predicate> void wait_until(Predicate predicate)
{
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(10);
    while (!predicate())
    {
        assert(std::chrono::steady_clock::now() < deadline);
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
}

void release(bool apply_state::*flag, bool value)
{
    std::lock_guard<std::mutex> lock(state.mutex);
    state.*flag = value;
    state.changed.notify_all();
}

int main()
{
    std::set<std::string> identities;
    for (unsigned int index = 0; index < 512; ++index)
    {
        critical_operation_id identity = {};
        assert(critical_operation_id_generate(&identity));
        char hex[CRITICAL_COMMAND_ID_HEX_SIZE] = {};
        assert(critical_operation_id_to_hex(identity, hex, sizeof(hex)));
        assert(identities.insert(hex).second);
        critical_operation_id decoded = {};
        assert(critical_operation_id_from_hex(hex, &decoded));
        assert(critical_operation_id_equal(identity, decoded));
    }

    critical_command codec = make_command(
        7, {{critical_entity_type::item, 9}, {critical_entity_type::player, 2},
            {critical_entity_type::collector, 87}});
    codec.accepted_at_usec = 1700000000000000ULL;
    codec.expected_revisions = {{{critical_entity_type::item, 9}, 3}};
    assert(critical_command_normalize(&codec));
    assert(codec.keys[0].type == critical_entity_type::player);
    std::vector<uint8_t> encoded;
    assert(critical_command_encode(codec, &encoded) == critical_command_codec_result::ok);
    critical_command decoded = {};
    assert(critical_command_decode(encoded.data(), encoded.size(), &decoded) ==
           critical_command_codec_result::ok);
    assert(critical_command_equal(codec, decoded));
    assert(decoded.keys.back().type == critical_entity_type::collector &&
           decoded.keys.back().id == 87);
    auto truncated = encoded;
    truncated.pop_back();
    assert(critical_command_decode(truncated.data(), truncated.size(), &decoded) ==
           critical_command_codec_result::truncated);
    auto malformed = encoded;
    malformed[53] = 1;
    assert(critical_command_decode(malformed.data(), malformed.size(), &decoded) ==
           critical_command_codec_result::invalid);

    // Commands run on the one writer, in capture order with the saves around them.
    assert(player_save_worker_init(apply_save, nullptr));
    assert(critical_command_coordinator_init(apply, &state));
    release(&apply_state::hold_save, true);
    assert(player_save_worker_submit(save_of(1)) == player_save_submit_result::accepted);
    wait_until([] { std::lock_guard<std::mutex> lock(state.mutex); return state.save_held; });
    critical_command a = make_command(
        1, {{critical_entity_type::item, 10}, {critical_entity_type::player, 1}});
    assert(critical_command_coordinator_submit(a) == critical_submit_result::accepted);
    assert(player_save_worker_submit(save_of(2)) == player_save_submit_result::accepted);
    critical_command b = make_command(2, {{critical_entity_type::player, 2}});
    assert(critical_command_coordinator_submit(b) == critical_submit_result::accepted);
    assert(critical_command_coordinator_submit(a) == critical_submit_result::attached);
    critical_command mismatch = a;
    mismatch.payload = {99};
    assert(critical_command_coordinator_submit(mismatch) ==
           critical_submit_result::identity_conflict);
    // While a command waits on the writer its keys are fenced.
    critical_operation_id fenced_by = {};
    assert(critical_command_coordinator_is_fenced({critical_entity_type::item, 10}, &fenced_by));
    assert(critical_operation_id_equal(fenced_by, a.operation_id));
    critical_completion stale = {};
    stale.operation_id = a.operation_id;
    stale.outcome = critical_apply_outcome::applied;
    stale.attempt = 99;
    assert(critical_command_coordinator_inject_completion_for_tests(stale));
    critical_completion completions[16] = {};
    assert(critical_command_coordinator_pulse(completions, 16) == 0);
    assert(critical_command_coordinator_health_copy().stale_completions == 1);
    assert(critical_command_coordinator_is_fenced({critical_entity_type::item, 10}, nullptr));
    release(&apply_state::hold_save, false);
    wait_until([&] {
        critical_command_coordinator_pulse(completions, 16);
        return critical_command_coordinator_health_copy().completed == 2;
    });
    {
        std::lock_guard<std::mutex> lock(state.mutex);
        assert((state.order == std::vector<std::string>{"p1", "c1", "p2", "c2"}));
        state.order.clear();
    }
    assert(!critical_command_coordinator_is_fenced({critical_entity_type::item, 10}, nullptr));

    // An ambiguous commit is retried by the writer until it learns the outcome.
    critical_command d = make_command(4, {{critical_entity_type::guild, 4}});
    assert(critical_command_coordinator_submit(d) == critical_submit_result::accepted);
    wait_until([&] {
        critical_command_coordinator_pulse(completions, 16);
        return critical_command_coordinator_health_copy().completed == 3;
    });
    assert(state.attempts[4] == 2);
    auto health = critical_command_coordinator_health_copy();
    assert(health.ambiguous == 1 && health.retries == 1 && health.fenced_keys == 0);
    assert(critical_command_coordinator_submit(d) == critical_submit_result::attached);

    // A refused command's completion names its type and the reason, for the alert.
    critical_command refused = make_command(18, {{critical_entity_type::item, 18}});
    refused.type = critical_command_type::auction;
    assert(critical_command_coordinator_submit(refused) == critical_submit_result::accepted);
    wait_until([&] { return critical_command_coordinator_pulse(completions, 16) == 1; });
    assert(completions[0].outcome == critical_apply_outcome::terminal_failure &&
           completions[0].type == critical_command_type::auction &&
           completions[0].error_code == 1062);

    critical_command_coordinator_quiesce();
    critical_command rejected = make_command(6, {{critical_entity_type::player, 6}});
    assert(critical_command_coordinator_submit(rejected) == critical_submit_result::unavailable);
    critical_command_coordinator_resume();
    assert(critical_command_coordinator_drain(3000));

    // A command queued before the coordinator stops still lands; its completion is
    // not handed to the next coordinator.
    release(&apply_state::hold_save, true);
    assert(player_save_worker_submit(save_of(3)) == player_save_submit_result::accepted);
    wait_until([] { std::lock_guard<std::mutex> lock(state.mutex); return state.save_held; });
    critical_command late = make_command(5, {{critical_entity_type::account, 50}});
    assert(critical_command_coordinator_submit(late) == critical_submit_result::accepted);
    critical_command_coordinator_shutdown();
    apply_state after;
    assert(critical_command_coordinator_init(apply, &after));
    release(&apply_state::hold_save, false);
    assert(persistence_writer_wait_idle(5000));
    assert(state.attempts[5] == 1);
    assert(critical_command_coordinator_pulse(completions, 16) == 0);
    assert(critical_command_coordinator_health_copy().stale_completions == 0);
    critical_command_coordinator_shutdown();

    // Bounds: accepted work is never dropped because the writer is behind.
    apply_state capacity;
    capacity.hold_all = true;
    assert(critical_command_coordinator_init(apply, &capacity));
    for (size_t index = 0; index < CRITICAL_COORDINATOR_MAX_OPERATIONS; ++index)
    {
        critical_command command = make_command(
            11, {{critical_entity_type::player, 10000 + index}});
        assert(critical_command_coordinator_submit(command) == critical_submit_result::accepted);
    }
    critical_command overflow = make_command(11, {{critical_entity_type::player, 999999}});
    assert(critical_command_coordinator_submit(overflow) == critical_submit_result::overloaded);
    health = critical_command_coordinator_health_copy();
    assert(health.inflight == CRITICAL_COORDINATOR_MAX_OPERATIONS);
    assert(health.high_water_operations == CRITICAL_COORDINATOR_MAX_OPERATIONS);
    assert(health.overloads == 1);
    {
        std::lock_guard<std::mutex> lock(capacity.mutex);
        capacity.release_all = true;
        capacity.changed.notify_all();
    }
    assert(persistence_writer_wait_idle(10000));
    critical_command_coordinator_shutdown();

    // A command whose outcome never becomes known is retried until shutdown, keeps
    // its fences, and is named with what the writer could not write.
    apply_state uncertain;
    assert(critical_command_coordinator_init(apply, &uncertain));
    const uint64_t retries_before = player_save_worker_health_copy().connection_retries;
    critical_command unknown = make_command(16, {{critical_entity_type::item, 16}});
    assert(critical_command_coordinator_submit(unknown) == critical_submit_result::accepted);
    wait_until([&] {
        return player_save_worker_health_copy().connection_retries >= retries_before + 2;
    });
    assert(critical_command_coordinator_pulse(completions, 16) == 0);
    assert(critical_command_coordinator_is_fenced({critical_entity_type::item, 16}, nullptr));
    player_save_worker_shutdown();
    const auto left = persistence_writer_pending_owners();
    assert(left.size() == 1 && left[0].first == persistence_job_kind::critical);
    assert(std::string(persistence_job_kind_name(persistence_job_kind::critical)) == "critical");
    critical_command_coordinator_shutdown();
    player_save_worker_reset_for_tests();
    return 0;
}
'''


with tempfile.TemporaryDirectory(prefix="duris-critical-command-") as temporary:
    temp = Path(temporary)
    source = temp / "critical_command_test.cpp"
    binary = temp / "critical_command_test"
    source.write_text(HARNESS)
    subprocess.run(
        [
            "g++", "-std=c++20", "-Wall", "-Wextra", "-Wpedantic", "-Werror",
            "-pthread", "-Isrc", str(source), rel("critical_command.c"),
            rel("critical_command_coordinator.c"),
            rel("player_save_worker.c"), rel("persistence_observability.c"),
            "-lz", "-lcrypto", "-lmysqlclient", "-o", str(binary),
        ],
        cwd=ROOT,
        check=True,
    )
    subprocess.run([str(binary)], check=True, timeout=60)
print("[PASS] commands run on the one writer, in capture order with the saves around them")
print("[PASS] a fenced command stays fenced until its completion; attach and conflict hold")
print("[PASS] the writer retries an ambiguous commit; an unknown outcome is named at shutdown")
print("[PASS] a refused command's completion carries its type and refusal reason")

for contract in (
    "CRITICAL_COORDINATOR_MAX_OPERATIONS = 1024",
    "CRITICAL_COORDINATOR_MAX_BYTES = 64 * 1024 * 1024",
    "CRITICAL_COORDINATOR_COMPLETED_CACHE_BYTES = 8 * 1024 * 1024",
):
    assert contract in HEADER
for contract in (
    "CRITICAL_COORDINATOR_MAX_RESULTS = 2048",
    "critical_completion_delivery",
    "critical_completion_channel::execution",
):
    assert contract in COMPLETION or contract in COORDINATOR
assert "critical," in WORKER
# The coordinator runs no threads of its own and journals nothing.
for retired in (
    "admission_worker", "worker_main", "pending_admission", "keys_available",
    "critical_command_journal", "std::thread admission", "std::vector<std::thread>",
):
    assert retired not in COORDINATOR
assert "persistence_writer_submit(persistence_job_kind::critical" in COORDINATOR
assert "struct critical_completion" in COMPLETION
assert "struct critical_completion" not in HEADER
for forbidden in ("P_char", "P_obj", "MYSQL", "redis", "sql_"):
    assert forbidden not in COORDINATOR
assert "critical_completion_delivery completion_delivery" in COORDINATOR
assert "getrandom(" in COMMAND and "rand(" not in COMMAND

MAKEFILE = (SRC / "Makefile").read_text()
COMM = (SRC / "comm.c").read_text()
COPYOVER = (SRC / "copyover.c").read_text()
ACTINF = (SRC / "actinf.c").read_text()
for object_name in (
    "critical_command.o",
    "critical_command_coordinator.o",
):
    assert object_name in MAKEFILE
assert "critical_command_coordinator_pulse(critical_completions, 64)" in COMM
assert "critical_command_coordinator_quiesce()" in COMM
assert "critical_command_coordinator_drain(3000)" in COMM
assert "critical_command_coordinator_quiesce()" in COPYOVER
assert "critical_command_coordinator_drain(3000)" in COPYOVER
assert COPYOVER.index("critical_command_coordinator_drain(3000)") < COPYOVER.index(
    "player_save_pipeline_quiesce()"
)
assert (
    "critical_command_coordinator_resume();\n"
    "\tcritical_outbox_resume();\n"
    "\tplayer_save_pipeline_resume();"
) in COPYOVER
assert '\"critical_commands state=%s' in ACTINF
assert "command.payload" not in ACTINF and "operation_id" not in ACTINF
assert "critical_command_equal" in COORDINATOR and "identity_conflict" in COORDINATOR
for state in (
    "Queued on the writer",
    "Final notification retained",
    "Snapshot pending and outbox pending",
):
    assert state in PIPELINE
# Money is no longer a critical command: it lives in memory.
assert "Currency publication ready" not in PIPELINE and "## Money lives in memory" in PIPELINE
assert "There is no second generic lifecycle framework" in PIPELINE

print("critical command identity, ordering, fence, and bound contracts passed")
