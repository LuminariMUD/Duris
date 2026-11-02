#!/usr/bin/env python3
"""Shutdown names every save it could not write and does not wait past the writer's
bound (persistence reset step 8; MR !2 review findings 2 and 5).

The writer drain covers every dirty locker, and the one report of unwritten saves runs
after the last source of writes (the final locker drain) has stopped. At the deadline a
query the writer is still blocked in is cut off, so the process exits on time.
tests/async/run_sql_pool_interrupt_mysql.sh (make test-db) proves the cut-off on a real
server; test_player_save_worker.py proves the writer names the interrupted job.
"""
from _paths import SRC, extract_function
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
COMM = (SRC / "comm.c").read_text()
PIPELINE = (SRC / "player_save_pipeline.c").read_text()
WORKER = (SRC / "player_save_worker.c").read_text()
POOL = (SRC / "sql_pool.c").read_text()


def body(text, signature):
    start = text.index(signature)
    return text[start:text.index("\n}\n", start) + 3]


loop = COMM[COMM.index("// Shutdown always goes (persistence reset step 8)"):]
loop = loop[:loop.index("close_sockets(s);")]
assert loop.index("persistence_save_all_characters_terminal(RENT_CRASH);") < \
    loop.index("locker_async_drain(0);") < \
    loop.index("persistence_observability_now_usec() + SHUTDOWN_WRITER_SECONDS") < \
    loop.index("shutdown_writer_remaining_msec(SHUTDOWN_WRITER_SECONDS * 1000)")
assert "locker_recovery_begin();" not in loop
assert "redis_world_recovery_drain(shutdown_writer_remaining_msec(3000))" in loop
assert "not_written" not in loop and "persistence_writer_pending_owners" not in loop
print("[PASS] the game loop queues every save and dirty locker before the timed drain")

run = body(COMM, "int run_the_game(int port, int sslport)")
assert run.index("game_loop(port, sslport);") < \
    run.index("locker_async_drain(shutdown_writer_remaining_msec(2000));") < \
    run.index("report_unwritten_saves(player_save_pipeline_finish(") < \
    run.index("critical_gameplay_handle_completions(shutdown_completions, count);") < \
    run.index("locker_recovery_begin();") < \
    run.index("locker_recovery_finish(shutdown_writer_deadline_usec);") < \
    run.index("locker_async_shutdown();")
assert run.index("locker_recovery_begin();") < run.rindex("critical_command_coordinator_shutdown();")
assert run.index("locker_recovery_begin();") < run.index("collector_catalog_cache_shutdown();")
assert COMM.index("if (!locker_recovery_boot())") < COMM.index("reap_unheld_player_items_at_boot();")
assert COMM.index("if (!locker_recovery_boot())") < COMM.index("!sql_hydrate_item_owner_revisions()")
assert COMM.index("if (!locker_recovery_boot())") < COMM.index("!hydrate_flatfile_system_item_owner()")
assert "shutdown_writer_deadline_usec - SHUTDOWN_LOCKER_RECOVERY_USEC" in run
assert "locker_recovery_begin" not in body(COMM, "bool pwipe_quiesce_writers(void)")
assert "sql_pool_interrupt_borrowed" in run
# The locker drains wait only for what is left of the writer's 30 s.
assert COMM.count("locker_async_drain(shutdown_writer_remaining_msec(2000));") == 2
remaining = body(COMM, "static int shutdown_writer_remaining_msec(int cap_msec)")
assert "now >= writer_deadline" in remaining and "return 0;" in remaining
assert "shutdown_writer_deadline_usec - SHUTDOWN_LOCKER_RECOVERY_USEC" in remaining
assert COMM.count("report_unwritten_saves(") == 2  # the definition and its one call
report = body(COMM, "static void report_unwritten_saves(")
assert '"not_written"' in report and "persistence_job_kind::log" in report
assert "named.insert(owner).second" in report and "locker_async_job_name(owner.second)" in report
assert '"locker_id=%llu chest_id=%llu"' in report
assert 'std::string("persistence_writer/") + persistence_job_kind_name(owner.first)' in report
print("[PASS] the one report of unwritten saves runs after the last locker drain")

finish = body(PIPELINE, "std::vector<persistence_job_owner> player_save_pipeline_finish(")
assert finish.index("persistence_writer_wait_idle(") < \
    finish.index("player_save_worker_shutdown(drained ? nullptr : interrupt);") < \
    finish.index("persistence_writer_pending_owners();")
stop = body(WORKER, "void player_save_worker_shutdown(void (*interrupt)(void))")
assert stop.index("writing = inflight != nullptr;") < stop.index("interrupt();") < \
    stop.index("writer.join();")
interrupt = body(POOL, "void sql_pool_interrupt_borrowed(void)")
assert "pool_closing = 1;" in interrupt and "shutdown(sql_telemetry_socket(pool[i].conn), SHUT_RDWR);" in interrupt
assert "tests/async/run_sql_pool_interrupt_mysql.sh" in (
    ROOT / "tests/run_db_tests.sh").read_text()
print("[PASS] at the deadline a query the writer is blocked in is cut off, not waited for")
print("shutdown writer bound contracts passed")

# Exercise the actual deadline helper: all writer/Redis drains must leave the
# image's final two seconds available, including when the writer used its budget.
build = ROOT / 'bin/tests/shutdown-budget'
build.mkdir(parents=True, exist_ok=True)
cpp = build / 'harness.cpp'
cpp.write_text('''
#include <algorithm>
#include <cassert>
#include <cstdint>
constexpr uint64_t SHUTDOWN_LOCKER_RECOVERY_USEC = 2000000;
static uint64_t shutdown_writer_deadline_usec, now_usec;
static uint64_t persistence_observability_now_usec() { return now_usec; }
''' + extract_function('net/comm.c', 'static int shutdown_writer_remaining_msec(') + '''
int main() {
    now_usec = 1000000;
    assert(shutdown_writer_remaining_msec(30000) == 0);
    shutdown_writer_deadline_usec = 31000000;
    assert(shutdown_writer_remaining_msec(30000) == 28000);
    assert(shutdown_writer_remaining_msec(3000) == 3000);
    now_usec = 28000000;
    assert(shutdown_writer_remaining_msec(3000) == 1000);
    now_usec = 29000000;
    assert(shutdown_writer_remaining_msec(3000) == 0);
    now_usec = 32000000;
    assert(shutdown_writer_remaining_msec(3000) == 0);
    shutdown_writer_deadline_usec = 1;
    assert(shutdown_writer_remaining_msec(3000) == 0);
}
''')
binary = build / 'harness'
subprocess.run(['g++', '-std=c++20', '-Wall', '-Wextra', '-Werror', str(cpp), '-o', str(binary)], check=True)
subprocess.run([str(binary)], check=True, timeout=5)
print('[PASS] writer and Redis drains preserve the final two seconds without renewing the deadline')
