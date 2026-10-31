#!/usr/bin/env python3
"""Runtime and source contracts for the bounded consistent player-load pipeline."""

from _paths import SRC, rel, extract_function
from contract_text import contains
import subprocess
import tempfile
import shlex
from pathlib import Path
from _paths import HARNESS_STUBS


ROOT = Path(__file__).resolve().parents[2]
PIPELINE = (SRC / "player_load_pipeline.c").read_text()
PIPELINE_HEADER = (SRC / "player_load_pipeline.h").read_text()
REPOSITORY = (SRC / "player_load_repository.c").read_text()
ACCOUNT = (SRC / "account.c").read_text()
COPYOVER = (SRC / "copyover.c").read_text()
COMM = (SRC / "comm.c").read_text()
NANNY = (SRC / "nanny.c").read_text()
MATERIALIZE = (SRC / "player_load_materialize.c").read_text()
DIAGNOSTICS = (SRC / "actinf.c").read_text()


HARNESS = r'''
#include "player/player_load_pipeline.h"
#include "persistence/persistence_observability.h"
#include "sql/sql_pool.h"

#include <cassert>
#include <chrono>
#include <condition_variable>
#include <atomic>
#include <mutex>
#include <thread>



bool player_load_request_valid(const player_load_request &request, uint64_t now)
{
    return request.schema_version == PLAYER_LOAD_SCHEMA_VERSION && request.request_id > 0 &&
           request.pid > 0 && !request.account_name.empty() &&
           request.deadline_usec > now &&
           request.deadline_usec - now <= PLAYER_LOAD_TIMEOUT_USEC;
}

player_load_result player_load_repository_execute(MYSQL *, const player_load_request &request)
{
    player_load_result result = {};
    result.request_id = request.request_id;
    result.pid = request.pid;
    result.outcome = player_load_outcome::applied;
    return result;
}

struct callback_state
{
    std::mutex mutex;
    std::condition_variable changed;
    bool hold_started = false;
    bool release = false;
};

player_load_result execute(const player_load_request &request, void *raw)
{
    auto &state = *static_cast<callback_state *>(raw);
    if (request.request_id >= 1000)
    {
        std::unique_lock<std::mutex> lock(state.mutex);
        state.hold_started = true;
        state.changed.notify_all();
        state.changed.wait(lock, [&] { return state.release; });
    }
    if (request.request_id == 4)
        std::this_thread::sleep_for(std::chrono::milliseconds(30));
    player_load_result result = {};
    result.request_id = request.request_id;
    result.pid = request.pid;
    result.outcome = player_load_outcome::applied;
    result.metrics.query_count = 7;
    result.metrics.row_count = 11;
    result.metrics.byte_count = 1234;
    result.metrics.transaction_usec = 456;
    if (request.request_id == 5)
        result.outcome = player_load_outcome::component_failure;
    if (request.request_id == 2)
    {
        result.request_id = 999;
        result.pid = request.pid + 1;
    }
    return result;
}

std::atomic<int> held_pid{0};
bool held(int pid)
{
    return pid == held_pid.load();
}

player_load_request request(uint64_t id, int pid)
{
    player_load_request value = {};
    value.request_id = id;
    value.pid = pid;
    value.account_name = "test-account";
    value.deadline_usec = persistence_observability_now_usec() + PLAYER_LOAD_TIMEOUT_USEC;
    return value;
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

int main()
{
    callback_state state;
    player_load_pipeline_reset_for_tests();
    assert(player_load_pipeline_init(execute, &state));

    assert(player_load_pipeline_submit(request(1, 10)) ==
           player_load_submit_outcome::accepted);
    assert(player_load_pipeline_submit(request(1, 10)) ==
           player_load_submit_outcome::duplicate);
    assert(player_load_pipeline_submit(request(2, 20)) ==
           player_load_submit_outcome::accepted);

    player_load_result results[8] = {};
    size_t received = 0;
    wait_until([&] {
        received += player_load_pipeline_pulse(results + received, 8 - received);
        return received == 2;
    });
    assert(results[0].request_id == 1 && results[0].pid == 10);
    assert(results[0].outcome == player_load_outcome::applied);
    assert(results[1].request_id == 2);
    assert(results[1].outcome == player_load_outcome::stale);

    assert(player_load_pipeline_submit(request(3, 30)) ==
           player_load_submit_outcome::accepted);
    assert(player_load_pipeline_cancel(3));
    assert(player_load_pipeline_cancel(3));
    wait_until([&] { return player_load_pipeline_pulse(results, 8) == 1; });
    assert(results[0].request_id == 3);
    assert(results[0].outcome == player_load_outcome::cancelled);

    player_load_result timed = {};
    assert(!player_load_pipeline_wait(request(4, 40), &timed, 1));
    wait_until([&] { return player_load_pipeline_pulse(results, 8) == 1; });
    assert(results[0].request_id == 4);
    assert(results[0].outcome == player_load_outcome::cancelled);

    // A character with a save still queued waits; other logins go ahead.
    player_load_pipeline_set_hold(held);
    held_pid = 70;
    assert(player_load_pipeline_submit(request(7, 70)) == player_load_submit_outcome::accepted);
    assert(player_load_pipeline_submit(request(8, 80)) == player_load_submit_outcome::accepted);
    wait_until([&] { return player_load_pipeline_pulse(results, 8) == 1; });
    assert(results[0].request_id == 8 && results[0].outcome == player_load_outcome::applied);
    std::this_thread::sleep_for(std::chrono::milliseconds(30));
    assert(player_load_pipeline_pulse(results, 8) == 0);
    held_pid = 0;
    wait_until([&] { return player_load_pipeline_pulse(results, 8) == 1; });
    assert(results[0].request_id == 7 && results[0].outcome == player_load_outcome::applied);
    // A save that never drains times the load out at its deadline instead of loading
    // stale state.
    held_pid = 71;
    player_load_request late = request(9, 71);
    late.deadline_usec = persistence_observability_now_usec() + 20000;
    assert(player_load_pipeline_submit(late) == player_load_submit_outcome::accepted);
    wait_until([&] { return player_load_pipeline_pulse(results, 8) == 1; });
    assert(results[0].request_id == 9 && results[0].outcome == player_load_outcome::timed_out);
    held_pid = 0;
    player_load_pipeline_set_hold(nullptr);

    assert(player_load_pipeline_submit(request(5, 50)) ==
           player_load_submit_outcome::accepted);
    wait_until([&] { return player_load_pipeline_pulse(results, 8) == 1; });
    assert(results[0].request_id == 5);
    assert(results[0].outcome == player_load_outcome::component_failure);

    player_load_result synchronous = {};
    assert(player_load_pipeline_execute_sync(request(6, 60), &synchronous));
    assert(synchronous.request_id == 6 && synchronous.pid == 60);
    assert(synchronous.outcome == player_load_outcome::applied);

    assert(player_load_pipeline_submit(request(1000, 1000)) ==
           player_load_submit_outcome::accepted);
    {
        std::unique_lock<std::mutex> lock(state.mutex);
        state.changed.wait(lock, [&] { return state.hold_started; });
    }
    for (size_t index = 1; index < PLAYER_LOAD_MAX_PENDING; ++index)
        assert(player_load_pipeline_submit(request(1000 + index, 1000 + index)) ==
               player_load_submit_outcome::accepted);
    assert(player_load_pipeline_submit(request(9000, 9000)) ==
           player_load_submit_outcome::capacity_exceeded);
    {
        std::lock_guard<std::mutex> lock(state.mutex);
        state.release = true;
        state.changed.notify_all();
    }
    player_load_pipeline_shutdown();

    const player_load_pipeline_health health = player_load_pipeline_health_copy();
    assert(!health.running);
    assert(health.applied >= 1);
    assert(health.stale >= 1);
    assert(health.cancelled == 2);
    assert(health.component_failures == 1);
    assert(health.high_water == PLAYER_LOAD_MAX_PENDING);
    assert(health.last_query_count == 7);
    assert(health.last_row_count == 11);
    assert(health.last_snapshot_bytes == 1234);
    assert(health.max_completion_latency_usec > 0);
    player_load_pipeline_reset_for_tests();
    return 0;
}
'''

# Exercise the actual duplicate-login block, request builder, bank publisher and
# hydration statements. The load worker's database snapshot and its delivery are
# controlled so a bank commit can cross the old read without concurrent sessions.
bank_case = r"""
P_desc descriptor_list;
static bool bank_purchase_pending;
bool currency_transaction_chest_account_busy(const char *account)
{
    return bank_purchase_pending && !strcasecmp(account, "load_account");
}
void gmcp_char_vitals(P_char) {}
void write_to_q(const char *, txt_q *, int) {}
void close_socket(P_desc old)
{
    if (old->character) old->character->desc = nullptr;
    for (auto link = &descriptor_list; *link; link = &(*link)->next)
        if (*link == old) { *link = old->next; break; }
}
void replace_account(P_desc d)
{
// DUPLICATE_LOGIN
}
// BUILD_ACCOUNT_REQUEST
// BANK_PUBLICATION
void hydrate_bank(P_char ch, const player_load_result &result)
{
// BANK_HYDRATION
}
struct bank_read_state
{
    std::mutex mutex;
    std::condition_variable changed;
    bool started = false, release = false;
    uint64_t platinum = 1000, revision = 1;
};
player_load_result bank_execute(const player_load_request &request, void *raw)
{
    auto &state = *static_cast<bank_read_state *>(raw);
    std::unique_lock<std::mutex> lock(state.mutex);
    player_load_result result{};
    result.request_id = request.request_id;
    result.pid = request.pid;
    result.outcome = player_load_outcome::applied;
    result.domains.bank[3] = state.platinum;
    result.domains.bank_revision = state.revision;
    state.started = true;
    state.changed.notify_all();
    state.changed.wait(lock, [&] { return state.release; });
    return result;
}
void bank_replacement_case()
{
    acct_entry previous_account{}, incoming_account{}, unrelated_account{};
    previous_account.acct_name = const_cast<char *>("load_account");
    incoming_account.acct_name = const_cast<char *>("LOAD_ACCOUNT");
    unrelated_account.acct_name = const_cast<char *>("another_account");
    descriptor_data previous{}, incoming{}, unrelated{};
    char_data purchaser{}, admitted{};
    pc_only_data purchaser_pc{}, admitted_pc{};
    purchaser.only.pc = &purchaser_pc;
    admitted.only.pc = &admitted_pc;
    purchaser_pc.pid = 111;
    admitted_pc.pid = 222;
    GET_RACEWAR(&purchaser) = GET_RACEWAR(&admitted) = 1;
    previous.account = &previous_account;
    previous.character = &purchaser;
    previous.connected = CON_PLAYING;
    purchaser.desc = &previous;
    incoming.account = &incoming_account;
    incoming.connected = CON_ACCT_CONFIRM_CHAR;
    incoming.next = &previous;
    descriptor_list = &incoming;
    bank_purchase_pending = true;
    replace_account(&incoming);
    assert(incoming.next == nullptr && purchaser.desc == nullptr);
    acct_chars selected{}; selected.pid = 222;
    player_load_request request{};
    unrelated.account = &unrelated_account;
    assert(build_account_load_request(&unrelated, &selected, &request));
    // Metadata-only account deletion is not an admission into the game.
    incoming.connected = CON_ACCT_DELETE_CHAR;
    assert(build_account_load_request(&incoming, &selected, &request));
    incoming.connected = CON_ACCT_CONFIRM_CHAR;
    bank_read_state state;
    assert(player_load_pipeline_init(bank_execute, &state));
    const bool started_before_commit = build_account_load_request(&incoming, &selected, &request);
    if (started_before_commit)
    {
        incoming.connected = CON_PLAYER_LOAD;
        assert(player_load_pipeline_submit(request) == player_load_submit_outcome::accepted);
        std::unique_lock<std::mutex> lock(state.mutex);
        assert(state.changed.wait_for(lock, std::chrono::seconds(2), [&] { return state.started; }));
    }
    {
        std::lock_guard<std::mutex> lock(state.mutex);
        state.platinum = 500;
        state.revision = 2;
    }
    const AccountBankBalances committed{0, 0, 0, 500};
    publish_account_bank_balances_revision("load_account", 1, &committed, 2);
    bank_purchase_pending = false;
    {
        std::lock_guard<std::mutex> lock(state.mutex);
        state.release = true;
        state.changed.notify_all();
    }
    if (!started_before_commit)
    {
        assert(build_account_load_request(&incoming, &selected, &request));
        assert(player_load_pipeline_submit(request) == player_load_submit_outcome::accepted);
    }
    player_load_result loaded{};
    wait_until([&] { return player_load_pipeline_pulse(&loaded, 1) == 1; });
    hydrate_bank(&admitted, loaded);
    incoming.character = &admitted;
    admitted.desc = &incoming;
    incoming.connected = CON_PLAYING;
    assert(GET_BALANCE_PLATINUM(&admitted) == 500 && admitted_pc.bank_revision == 2);
    player_load_pipeline_reset_for_tests();
    descriptor_list = nullptr;
}
"""
duplicate_start = ACCOUNT.index("// Check for duplicate account login")
duplicate_end = ACCOUNT.index("\techo_on(d);", duplicate_start)
bank_case = bank_case.replace("// DUPLICATE_LOGIN", ACCOUNT[duplicate_start:duplicate_end])
bank_case = bank_case.replace("// BUILD_ACCOUNT_REQUEST", extract_function("account/account.c", "bool build_account_load_request("))
bank_case = bank_case.replace("// BANK_PUBLICATION", extract_function("core/utility.c", "void publish_account_bank_balances_revision("))
bank_start = MATERIALIZE.index("\tGET_BALANCE_COPPER(ch) = result.domains.bank[0];")
bank_end = MATERIALIZE.index("\tch->only.pc->epics", bank_start)
bank_case = bank_case.replace("// BANK_HYDRATION", MATERIALIZE[bank_start:bank_end])
HARNESS = HARNESS.replace('#include "player/player_load_pipeline.h"', '#include "player/player_load_pipeline.h"\n#include "core/prototypes.h"\n#include "core/utils.h"\n#include "account/account.h"\n#include "net/comm.h"\n#include "net/gmcp.h"\n#include "sql/sql_player.h"', 1)
HARNESS = HARNESS.replace("int main()\n{", bank_case + "\nint main()\n{", 1)
HARNESS = HARNESS.replace("    player_load_pipeline_reset_for_tests();\n    return 0;", "    player_load_pipeline_reset_for_tests();\n    bank_replacement_case();\n    return 0;", 1)


with tempfile.TemporaryDirectory(prefix="duris-player-load-pipeline-") as temp_dir:
    source = Path(temp_dir) / "pipeline_test.cpp"
    binary = Path(temp_dir) / "pipeline_test"
    source.write_text(HARNESS)
    mysql_cflags = shlex.split(subprocess.check_output(["mysql_config", "--cflags"], text=True))
    mysql_libs = shlex.split(subprocess.check_output(["mysql_config", "--libs"], text=True))
    subprocess.run(
        [
            "g++",
            "-std=c++20",
            "-Wall",
            "-Wextra",
            "-Wpedantic",
            "-Werror",
            "-pthread",
            "-Isrc",
            *mysql_cflags,
            str(source),
            rel("player_load_pipeline.c"),
            rel("persistence_observability.c"),
            *mysql_libs,
            str(HARNESS_STUBS), "-o",
            str(binary),
        ],
        cwd=ROOT,
        check=True,
    )
    subprocess.run([str(binary)], check=True, timeout=10)

for contract in (
    "PLAYER_LOAD_MAX_PENDING = 256",
    "PLAYER_LOAD_MAX_COMPLETIONS = 256",
    "player_load_pipeline_cancel",
    "player_load_pipeline_note_stale",
    "player_load_pipeline_next_request_id",
    "last_completion_latency_usec",
):
    assert contract in PIPELINE_HEADER
for contract in (
    "std::unordered_set<uint64_t> active_ids",
    "std::unordered_set<uint64_t> cancelled_ids",
    "player_load_outcome::stale",
    "sql_pool_acquire()",
    "sql_worker_thread_init()",
    "pool_connection_guard guard",
    "mysql_rollback(connection)",
    "selected_execute_callback()",
    "flatfile_player_load_repository_execute_selected",
):
    assert contract in PIPELINE

for contract in (
    "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ",
    "START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY",
    'execute(connection, "COMMIT"',
    'execute(connection, "ROLLBACK"',
    "PLAYER_LOAD_QUERY_MAX",
    "PLAYER_SNAPSHOT_MAX_ROWS",
    "PLAYER_SNAPSHOT_MAX_BYTES",
    "PERSISTENCE_QUERY_CONTEXT_PLAYER_LOAD_WORKER",
):
    assert contract in REPOSITORY
assert REPOSITORY.index("load_status(connection") < REPOSITORY.index("load_components(connection")
assert REPOSITORY.index("load_components(connection") < REPOSITORY.index("load_bank(connection")

assert "restoreCharOnly(player" not in ACCOUNT
assert "player_load_pipeline_submit(request)" in ACCOUNT
# Account logins never block the game loop: no synchronous or waiting fallback.
assert "player_load_pipeline_execute_sync" not in ACCOUNT
assert "player_load_pipeline_wait" not in ACCOUNT
assert "PLAYER_LOAD_MODE_ACCOUNT_DELETE" in ACCOUNT
assert "player_load_pipeline_set_hold(player_save_pipeline_load_held)" in COMM
# An offline load names the character by pid when it exists, so the worker holds it behind
# the character's queued saves like a login, and a copy saved back is never older.
OFFLINE = (SRC / "player_load_offline.c").read_text()
assert "const int pid = sql_get_player_pid(name);" in OFFLINE
assert "request.pid = pid;" in OFFLINE and "request.player_name = name;" in OFFLINE
validity = REPOSITORY[REPOSITORY.index("bool player_load_request_valid(") :]
assert contains(validity, "request.pid > 0 && request.account_name.size() <= PLAYER_LOAD_ACCOUNT_MAX")
assert contains(REPOSITORY, "(!request.account_name.empty() && strcasecmp(result->account_name.c_str()")
assert "STATE(d) = CON_PLAYER_LOAD" in ACCOUNT
assert "player_load_materialize(player, loaded)" in ACCOUNT
assert "d->rtype = loaded.snapshot.save_intent;" in ACCOUNT
completion = ACCOUNT[ACCOUNT.index("void account_player_load_complete") :]
recheck = completion.index('account_confirm_char(d, writable_arg("Y"))')
discard = completion.index("ready_player_loads.erase(completed_request_id)")
assert recheck < discard
assert "d->player_load_request_id = 0" in completion[discard:]
blocking = ACCOUNT[ACCOUNT.index("P_char load_char_into_game") : ACCOUNT.index("void account_player_load_complete")]
assert "ready_player_loads.emplace(request.request_id" not in blocking
assert "restoreCharOnly(player" not in COPYOVER
assert "player_load_pipeline_wait(request" in COPYOVER
assert "player_load_pipeline_execute_sync(request" in COPYOVER
assert "player_load_outcome::degraded" not in COPYOVER
assert "player_load_materialize(player, result)" in COPYOVER
assert "player_load_pipeline_cancel(d->player_load_request_id)" in COMM
assert "player_load_pipeline_shutdown()" in COMM
assert "restoreCharOnly(d->character" not in NANNY
# No login blocks on a load: a refused submit asks the player to try again.
assert "player_load_pipeline_execute_sync" not in NANNY
assert "player_load_pipeline_wait" not in NANNY
assert "degraded" not in (SRC / "player_load_repository.h").read_text()
assert "degraded" not in (SRC / "player_load_pipeline.h").read_text()
assert "restoreItemsOnly" not in NANNY
assert "valid_snapshot(result)" in MATERIALIZE
assert "result.snapshot.save_intent > RENT_FIGHTARTI" in MATERIALIZE
assert "player_revision_hydrate" in MATERIALIZE
assert "ZONE_TROPHY(ch) = zone_trophies.release()" in MATERIALIZE
# There are no degraded loads: a load either succeeds with the rows that pass the
# ownership filter or is refused outright.
assert "mark_degraded" not in MATERIALIZE and "degraded" not in MATERIALIZE
assert 'return refuse("items", "materialize_failure");' in MATERIALIZE
assert "mark_degraded" not in REPOSITORY
assert "CHAR_RFLAG_LOAD_DEGRADED" not in (SRC / "files.c").read_text()
assert "CHAR_RFLAG_LOAD_DEGRADED" not in (SRC / "player_save_pipeline.c").read_text()
assert "player_load state=" in DIAGNOSTICS
assert "account_name" not in DIAGNOSTICS[DIAGNOSTICS.index("player_load state=") :][:1000]

print("bounded consistent player-load pipeline contracts passed")
