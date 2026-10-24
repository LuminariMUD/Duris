from _paths import SRC
from pathlib import Path

source = (SRC / "sql.c").read_text()
start = source.rindex("bool sql_pwipe(int code_verify)")
end = source.index("void sql_log_player_login", start)
body = source[start:end]

assert 'WIPE COMPLETED!' not in body
assert 'reset_status=\'active\'' not in body
assert body.index('redis_clear_pwipe_state()') < body.index('sql_prepare_pwipe_filesystem()')
assert body.index('sql_prepare_pwipe_filesystem()') < body.index('pwipe_filesystem_ready = true')
assert body.index('pwipe_filesystem_ready = true') < body.index('return TRUE;')
rewards = body[body.index('if (!account_bound_rewards_on_successful_pwipe())'):]
assert rewards.index('return FALSE;') < rewards.index('sql_prepare_pwipe_filesystem()')
assert '{ "player_data", "learned_flight_stops" }' in source
assert 'UPDATE player_data SET active = 0, learned_flight_stops = 0' in body
assert 'WHERE active = 1 OR learned_flight_stops <> 0' in body

print("sql pwipe completion reporting checks passed")

# Execute the production wait predicate with the production reaper owning status.
import subprocess
import tempfile

signals = (SRC / "signals.c").read_text()
reaper = signals[signals.rindex("void reap(int sig)"):signals.index("void reaper(int")]
wait = body[body.index("int status = 0;", body.index("pid_t wipe_child")):
            body.index("\n\t\t}", body.index("pid_t wipe_child"))]
program = r"""
#include <cassert>
#include <cerrno>
#include <csignal>
#include <sys/wait.h>
#include <unistd.h>
#define REAPED_CHILD_STATUS_CAPACITY 64
static volatile sig_atomic_t reaped_child_pids[64];
static volatile sig_atomic_t reaped_child_statuses[64];
static volatile sig_atomic_t reaped_child_cursor;
""" + reaper + r"""
bool check(pid_t wipe_child) {
    bool filesystem_ready = false;
""" + wait + r"""
    return filesystem_ready;
}
int main() {
    for (int code : {0, 7}) {
        for (bool reap_first : {false, true}) {
            pid_t child = fork();
            assert(child >= 0);
            if (!child) _exit(code);
            if (reap_first) {
                siginfo_t info{};
                assert(waitid(P_PID, child, &info, WEXITED | WNOWAIT) == 0);
                reap(SIGCHLD);
            }
            assert(check(child) == (code == 0));
            assert(!check(child)); // Missing/consumed status must fail closed.
        }
    }
}
"""
root = Path(__file__).resolve().parents[2]
(root / "bin/tests").mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(dir=root / "bin/tests") as directory:
    native = Path(directory) / "pwipe_child.cpp"
    native.write_text("#include <initializer_list>\n" + program)
    binary = native.with_suffix("")
    subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
                    str(native), "-o", str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
print("pwipe preflight direct/reaped success, failure and missing status passed")
