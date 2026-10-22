#!/usr/bin/env python3
"""Real persistence writer exercises the Divine Boon boot/publication boundary."""

import subprocess
import tempfile
from pathlib import Path

from _paths import ROOT, HARNESS_STUBS, extract_function


output_root = ROOT / "bin" / "tests"
output_root.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="divine-boon-runtime-", dir=output_root) as directory:
    binary = f"{directory}/divine_boon_runtime_test"
    subprocess.run(
        [
            "g++", "-std=c++20", "-g", "-Og", "-Wall", "-Wextra", "-Wpedantic",
            "-Werror", "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
            "-fno-pie", "-no-pie", "-D__NO_MYSQL__",
            "-DDURIS_FLATFILE_AUTHORITY_FAULT_TEST", "-Isrc", "-Isrc/no_mysql",
            "tests/async/divine_boon_runtime_harness.cpp",
            "src/economy/divine_boon.c", "src/economy/divine_boon_repository.c",
            "src/economy/divine_boon_runtime.c", "src/player/player_save_worker.c",
            "src/persistence/persistence_observability.c",
            "src/persistence/maintenance_scheduler.c",
            str(HARNESS_STUBS),
            "src/flatfile/flatfile_authority_transaction.c", "src/flatfile/flatfile_store.c",
            "-lcrypto", "-pthread", "-o", binary,
        ],
        cwd=ROOT, check=True,
    )
    subprocess.run([binary, f"{directory}/state"], cwd=ROOT, check=True, timeout=20)

comm = (ROOT / "src/net/comm.c").read_text()
boot = comm[comm.index("int run_the_game("):comm.index("static void run_recurring_persistence_phase(")]
assert boot.index("player_save_pipeline_init()") < boot.index("divine_boon_runtime_boot(")
assert "divine_boon_runtime_pulse();" in comm

# Exercise the production SQL callback with the real shared writer and a missing
# pool. A Divine retry must release the writer for unrelated persistence jobs.
runtime = (ROOT / "src/economy/divine_boon_runtime.c").read_text()
callback = runtime[runtime.index("player_save_apply_result write_state("):runtime.index("\nbool submit_pending()")]
success = callback[:callback.index("\ncatch")]
assert success.rfind("operation->") == success.index("operation->finished.store(")
sql_harness = r'''
#include "economy/divine_boon_repository.h"
#include "player/player_save_worker.h"
#include "sql/sql_pool.h"
#include <atomic>
#include <cassert>
#include <cerrno>
#include <memory>
#include <new>
using store_result = divine_boon_store_result;
static bool pool_available = false;
static MYSQL connection;
MYSQL *sql_pool_acquire() { return pool_available ? &connection : nullptr; }
void sql_pool_release(MYSQL *) {}
MYSQL *sql_pool_replace_connection(MYSQL *value) { return value; }
unsigned int mysql_errno(MYSQL *) { return 0; }
store_result divine_boon_sql_save(MYSQL *, uint64_t, const divine_boon_state &) { return store_result::ok; }
store_result divine_boon_flatfile_save(const std::string &, uint64_t, const divine_boon_state &) { return store_result::ok; }
// OPERATION
// CALLBACK
int main() {
    assert(player_save_worker_init([](const player_snapshot &, void *) {
        std::abort(); return player_save_apply_result{};
    }, nullptr));
    auto operation = std::make_shared<pending_write>();
    operation->flatfile = false;
    operation->next.revision = 9;
    assert(persistence_writer_submit(persistence_job_kind::divine_boon, 1, 1,
        [operation] { return write_state(operation); }) == player_save_submit_result::accepted);
    std::atomic<bool> other_saved = false;
    assert(persistence_writer_submit(persistence_job_kind::log, 2, 1, [&] {
        other_saved = true; return player_save_apply_result{player_save_apply_outcome::applied, 0, 0};
    }) == player_save_submit_result::accepted);
    assert(persistence_writer_wait_idle(1000) && other_saved);
    assert(operation->finished.load(std::memory_order_acquire));
    assert(operation->result == store_result::io_error);
    pool_available = true;
    operation->finished = false;
    const auto result = write_state(operation);
    assert(result.outcome == player_save_apply_outcome::applied && result.durable_revision == 9);
    assert(operation->finished.load(std::memory_order_acquire));
    player_save_worker_shutdown();
}
'''
sql_harness = sql_harness.replace("// OPERATION", extract_function("divine_boon_runtime.c", "struct pending_write") + ";")
sql_harness = sql_harness.replace("// CALLBACK", callback)
with tempfile.TemporaryDirectory(prefix="divine-writer-sql-", dir=output_root) as directory:
    source = Path(directory) / "callback.cpp"
    binary = Path(directory) / "callback"
    source.write_text(sql_harness)
    subprocess.run([
        "g++", "-std=c++20", "-g", "-Og", "-Wall", "-Wextra", "-Werror",
        "-fsanitize=address,undefined", "-fno-pie", "-no-pie", "-Isrc", "-I/usr/include/mysql",
        str(source), "src/player/player_save_worker.c", "src/persistence/persistence_observability.c",
        str(HARNESS_STUBS), "-pthread", "-lcrypto", "-lmysqlclient", "-o", str(binary),
    ], cwd=ROOT, check=True)
    subprocess.run([str(binary)], cwd=ROOT, check=True, timeout=5)
print("Divine SQL callback releases the shared writer without a pool and publishes completion last")
