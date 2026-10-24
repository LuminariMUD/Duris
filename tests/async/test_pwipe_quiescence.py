from _paths import SRC
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
actwiz = (SRC / "actwiz.c").read_text()
comm = (SRC / "comm.c").read_text()

pwipe_start = actwiz.rindex("case TimedShutdownData::PWIPE:")
pwipe_case = actwiz[pwipe_start:actwiz.index("default:", pwipe_start)]
assert "shutdownflag = _pwipe = 1" in pwipe_case
assert "shutdownData.eShutdownType = TimedShutdownData::NONE" in pwipe_case
assert "sql_pwipe_crossed_boundary()" in pwipe_case
assert "forcing fenced shutdown" in pwipe_case

terminal_gate = "if (!_pwipe)\n\t{\n\t\tpersistence_save_all_characters_terminal(RENT_CRASH);"
assert terminal_gate in comm
assert comm.index(terminal_gate) < comm.index("if (!_copyover && !_pwipe)\n\t{", comm.index(terminal_gate))
main_shutdown = comm[comm.index("game_loop(port, sslport);"):comm.index("/* Don't need this anymore")]
assert main_shutdown.index("game_loop(port, sslport);") < main_shutdown.index(
    "critical_command_coordinator_shutdown();"
)
assert "if (!_pwipe)" in comm[comm.index("game_loop(port, sslport);"):comm.index("/* Don't need this anymore")]

sql = (SRC / "sql.c").read_text()
wipe = sql[sql.rindex("bool sql_pwipe(int code_verify)"):]
assert wipe.index("pwipe_quiesce_writers()") < wipe.index("sql_begin_pwipe_epoch()")
begin_failure = wipe[wipe.index("if (!sql_begin_pwipe_epoch())"):wipe.index('qry("UPDATE zones SET alignment=0')]
assert "if (!pwipe_crossed_boundary && !pwipe_recovery_epoch)" in begin_failure
assert "pwipe_resume_writers()" in begin_failure
assert "if (!_pwipe)\n\t\tkingdom_shutdown();" in comm
assert "if (_pwipe)\n\t\t\tbreak;" in comm
print("pwipe quiescence source checks passed")


# Execute the production preparation with the real shared writer. Peripheral drains
# are controlled here; their own subsystem tests cover their implementation.
preparation = comm[comm.index("void pwipe_resume_writers(void)"):
                   comm.index("static void critical_gameplay_handle_completions(")]
harness = r'''
#include "player/player_save_worker.h"
#include "persistence/critical_command_coordinator.h"
#include "persistence/critical_outbox.h"
#include "persistence/persistence_observability.h"
#include <atomic>
#include <cassert>
#include <chrono>
#include <thread>
bool fail_drain = false, inject_failure = false, sql_callback = false;
int resumed = 0;
bool fail_command = false, fail_delivery = false;
uint64_t command_errors = 0, delivery_errors = 0;
critical_coordinator_health critical_command_coordinator_health_copy() {
    critical_coordinator_health health{}; health.terminal_failures = command_errors; return health;
}
critical_outbox_health critical_outbox_health_copy() {
    critical_outbox_health health{}; health.terminal_failures = delivery_errors; return health;
}
std::atomic<bool> started{false}, released{false};
std::atomic<int> rows{0};
void player_save_pipeline_resume() { ++resumed; }
void critical_outbox_resume() {}
void critical_command_coordinator_resume() {}
void maintenance_scheduler_resume() {}
void maintenance_scheduler_quiesce() {}
void critical_command_coordinator_quiesce() {}
void critical_outbox_quiesce() {}
bool artifact_guild_transaction_drain(uint64_t) { return true; }
bool locker_async_drain(int) { return true; }
bool maintenance_scheduler_drain(uint64_t) { return !fail_drain; }
bool critical_command_coordinator_drain(uint64_t) { if (fail_command) ++command_errors; return true; }
bool critical_outbox_drain(uint64_t) { if (fail_delivery) ++delivery_errors; return true; }
bool persistence_flush_all_character_saves() { return true; }
bool artifact_save_drain(uint64_t) {
    if (inject_failure) {
        assert(persistence_writer_submit(persistence_job_kind::sql, 3, 1, [] {
            return player_save_apply_result{player_save_apply_outcome::terminal_failure, 0, 1452};
        }) == player_save_submit_result::accepted);
    }
    return true;
}
bool player_save_pipeline_drain(uint64_t timeout) { return persistence_writer_wait_idle(timeout); }
size_t sql_async_pulse() {
    if (!sql_callback) return 0;
    sql_callback = false;
    assert(persistence_writer_submit(persistence_job_kind::sql, 2, 1, [] {
        ++rows;
        return player_save_apply_result{player_save_apply_outcome::applied, 0, 0};
    }) == player_save_submit_result::accepted);
    return 1;
}
''' + preparation + r'''
int main() {
    assert(player_save_worker_init([](const player_snapshot &, void *) {
        return player_save_apply_result{player_save_apply_outcome::applied, 0, 0};
    }, nullptr));
    assert(persistence_writer_submit(persistence_job_kind::sql, 1, 1, [] {
        started = true;
        while (!released) std::this_thread::sleep_for(std::chrono::milliseconds(1));
        ++rows;
        return player_save_apply_result{player_save_apply_outcome::applied, 0, 0};
    }) == player_save_submit_result::accepted);
    while (!started) std::this_thread::yield();
    std::thread release([] { std::this_thread::sleep_for(std::chrono::milliseconds(30)); released = true; });
    sql_callback = true;
    assert(pwipe_quiesce_writers());
    release.join();
    assert(rows == 2); // Held work and its read callback's follow-up finished first.
    rows = 0; // Model destructive SQL only after successful preparation.
    assert(persistence_writer_submit(persistence_job_kind::sql, 4, 1, [] {
        ++rows;
        return player_save_apply_result{player_save_apply_outcome::applied, 0, 0};
    }) == player_save_submit_result::unavailable);
    assert(rows == 0);
    pwipe_resume_writers();
    fail_drain = true;
    const int before = resumed;
    assert(!pwipe_quiesce_writers() && resumed == before + 1);
    fail_drain = false;
    inject_failure = true;
    assert(!pwipe_quiesce_writers()); // A failed accepted write forbids reset.
    inject_failure = false;
    fail_command = true; assert(!pwipe_quiesce_writers()); fail_command = false;
    fail_delivery = true; assert(!pwipe_quiesce_writers()); fail_delivery = false;
    assert(persistence_writer_submit(persistence_job_kind::sql, 5, 1, [] {
        ++rows;
        return player_save_apply_result{player_save_apply_outcome::applied, 0, 0};
    }) == player_save_submit_result::accepted);
    assert(persistence_writer_wait_idle(3000));
    assert(rows == 1); // Abort resumed normal persistence.
    player_save_worker_shutdown();
}
'''
with tempfile.TemporaryDirectory(prefix="duris-pwipe-writers-") as temporary:
    path = Path(temporary)
    (path / "test.cpp").write_text(harness)
    subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-D__NO_MYSQL__", "-Isrc",
                    str(path / "test.cpp"), str(SRC / "player_save_worker.c"),
                    str(SRC / "persistence_observability.c"), "-pthread", "-o", str(path / "test")],
                   cwd=ROOT, check=True)
    subprocess.run([str(path / "test")], check=True, timeout=15)
print("pwipe held shared-writer / callback chain / refusal / abort-resume checks passed")
