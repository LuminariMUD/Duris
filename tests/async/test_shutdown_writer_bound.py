#!/usr/bin/env python3
"""Shutdown names every save it could not write and does not wait past the writer's
bound (persistence reset step 8; MR !2 review findings 2 and 5).

The writer drain covers every dirty locker, and the one report of unwritten saves runs
after the last source of writes (the final locker drain) has stopped. At the deadline a
query the writer is still blocked in is cut off, so the process exits on time.
tests/async/run_sql_pool_interrupt_mysql.sh (make test-db) proves the cut-off on a real
server; test_player_save_worker.py proves the writer names the interrupted job.
"""
from _paths import SRC
from pathlib import Path

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
    loop.index("player_save_pipeline_drain(SHUTDOWN_WRITER_SECONDS * 1000ULL);")
assert "not_written" not in loop and "persistence_writer_pending_owners" not in loop
print("[PASS] the game loop queues every save and dirty locker before the timed drain")

run = body(COMM, "int run_the_game(int port, int sslport)")
assert run.index("game_loop(port, sslport);") < run.index("locker_async_shutdown();") < \
    run.index("report_unwritten_saves(player_save_pipeline_finish(shutdown_writer_deadline_usec,")
assert "sql_pool_interrupt_borrowed" in run
assert COMM.count("report_unwritten_saves(") == 2  # the definition and its one call
report = body(COMM, "static void report_unwritten_saves(")
assert '"not_written"' in report and "persistence_job_kind::log" in report
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
assert "tests/async/run_sql_pool_interrupt_mysql.sh" in (ROOT / "Makefile").read_text()
print("[PASS] at the deadline a query the writer is blocked in is cut off, not waited for")
print("shutdown writer bound contracts passed")
