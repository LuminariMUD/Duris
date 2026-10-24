#!/usr/bin/env python3
"""Run the real launcher/filesystem handoff on a private DB and synthetic tree.

This qualifies the cross-process handoff, not the real game command or writer drain.
"""
import fcntl
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import migration_runner


def run():
    if not os.environ.get("TEST_DB_HOST"):
        wrapper = ROOT / "tests/async/with_disposable_mariadb.sh"
        os.execv(str(wrapper), [str(wrapper), sys.executable, str(Path(__file__).resolve())])
    env = dict(PATH=os.environ.get("PATH", "/usr/bin:/bin"), ENVIRONMENT="local",
               PERSISTENCE_MODE="mariadb-primary", DB_HOST=os.environ["TEST_DB_HOST"],
               DB_PORT=os.environ["TEST_DB_PORT"], DB_USER=os.environ["TEST_DB_USER"],
               DB_PASSWD=os.environ["TEST_DB_PASSWORD"], DB_NAME="duris_test")
    env["DB_ALLOWED_TARGETS"] = env["DB_HOST"] + "/duris_test"
    env["MYSQL_PWD"] = env["DB_PASSWD"]
    mysql = [shutil.which("mysql"), "--protocol=tcp", "-h", env["DB_HOST"], "-P", env["DB_PORT"],
             "-u", env["DB_USER"], "-N", "-B"]

    def sql(statement, database=True):
        return subprocess.check_output(mysql + (["duris_test"] if database else []) +
                                       ["-e", statement], env=env, text=True).strip()

    sql("CREATE DATABASE duris_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci", False)
    manifest = migration_runner.load_manifest()
    for path in [ROOT / "migrations/bootstrap_multithread_safe.sql",
                 *(step.apply_path for step in manifest.migrations)]:
        subprocess.run(mysql + ["duris_test"], input=path.read_bytes(), env=env,
                       check=True, stdout=subprocess.DEVNULL)
    import json
    lifecycle = json.loads((ROOT / "migrations/data_lifecycle_manifest.json").read_text())
    expected = {entry["locator"] for entry in lifecycle["entries"] if entry["kind"] == "database_table"}
    actual = set(sql("SHOW TABLES").splitlines())
    assert actual == expected, (actual - expected, expected - actual)
    print(f"Fully migrated MariaDB inventory matches all {len(actual)} lifecycle tables", flush=True)

    # Compile the actual season-state functions with a tiny real-MariaDB caller.
    # The surrounding server remains covered by the later full command journey.
    source = (ROOT / "src/sql/sql.c").read_text()
    functions = source[source.index("static bool sql_connection_execute("):
                       source.index("bool sql_pwipe_crossed_boundary(void)",
                                    source.index("static bool sql_load_active_season_state"))]
    native = ROOT / "bin/tests/pwipe_epoch_mysql.cpp"
    native.parent.mkdir(parents=True, exist_ok=True)
    native.write_text('''#include <mysql/mysql.h>
#include <cerrno>
#include <climits>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
MYSQL *DB;
bool pwipe_crossed_boundary;
uint64_t current_season_epoch;
MYSQL_RES *db_query(const char *statement) {
    return mysql_real_query(DB, statement, strlen(statement)) ? nullptr : mysql_store_result(DB);
}
''' + functions + '''
int main(int argc, char **argv) {
    if (argc != 3) return 2;
    DB = mysql_init(nullptr);
    if (!mysql_real_connect(DB, getenv("DB_HOST"), getenv("DB_USER"), getenv("DB_PASSWD"),
                            getenv("DB_NAME"), atoi(getenv("DB_PORT")), nullptr, 0)) return 2;
    current_season_epoch = strtoull(argv[2], nullptr, 10);
    bool ok = !strcmp(argv[1], "begin") ? sql_begin_pwipe_epoch() :
              !strcmp(argv[1], "ready") ? sql_prepare_pwipe_filesystem() : sql_load_active_season_state();
    mysql_close(DB);
    return ok ? 0 : 1;
}
''')
    binary = native.with_suffix("")
    subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", str(native),
                    "-lmysqlclient", "-o", str(binary)], check=True)

    def epoch_call(command, epoch, expected_code):
        result = subprocess.run([str(binary), command, str(epoch)], env=env)
        assert result.returncode == expected_code, (command, epoch, result.returncode)

    epoch_call("active", 1, 0)
    epoch_call("begin", 1, 0)
    epoch_call("active", 2, 1)
    epoch_call("begin", 2, 1)
    assert sql("SELECT season_epoch FROM season_reset_state WHERE state_id=1") == "2"
    epoch_call("ready", 3, 1)
    epoch_call("ready", 2, 0)
    epoch_call("active", 2, 1)
    print("Native begin/SQL-ready/boot fence passed with real MariaDB", flush=True)

    output = ROOT / "bin/tests"
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="pwipe-handoff-", dir=output) as temporary:
        root = Path(temporary)
        for directory in ("scripts", "Players/wipers", "Players/a", "Players/Backup", "bin/server"):
            (root / directory).mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / "scripts/cycle_mud.sh", root / "scripts/cycle_mud.sh")
        wiper = root / "Players/wipers/wipe_it_all"
        shutil.copy2(ROOT / "Players/wipers/wipe_it_all", wiper)
        original = wiper.read_text()
        (root / "Players/Backup/keep").write_text("archive")
        old = root / "Players/a/old"

        def prepare(ready=True):
            old.write_text("old season")
            sql("UPDATE season_reset_state SET season_epoch=2,reset_status='resetting',"
                "reset_started_at=UTC_TIMESTAMP(6),reset_completed_at=" +
                ("UTC_TIMESTAMP(6)" if ready else "NULL") + " WHERE state_id=1")

        def launch(epoch=2, expected=58, environment=None):
            result = subprocess.run([str(root / "scripts/cycle_mud.sh"), "--dev", "--resume-pwipe", str(epoch)],
                                    env=environment or env, text=True, capture_output=True, timeout=30)
            assert result.returncode == expected, (result.returncode, result.stdout, result.stderr)
            return result

        def status():
            return sql("SELECT CONCAT(season_epoch,':',reset_status) FROM season_reset_state WHERE state_id=1")

        prepare(False); launch(); assert old.exists() and status() == "2:resetting"
        prepare(); launch(epoch=3); assert old.exists()
        with (root / "bin/server/.pwipe.lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            launch(); assert old.exists()
        (root / "Ships").symlink_to(root / "Players/Backup")
        launch(); assert old.exists() and status() == "2:resetting"
        (root / "Ships").unlink()
        wiper.chmod(0o600); launch(); assert old.exists(); wiper.chmod(0o700)
        # Fail after real cleanup: no activation, and a repaired retry finishes once.
        wiper.write_text(original.replace('echo "wipe_it_all: filesystem cleanup completed"', 'exit 1'))
        launch(); assert not old.exists() and status() == "2:resetting"
        wiper.write_text(original)
        launch(expected=55); assert status() == "2:active"
        old.write_text("new season sentinel")
        launch(expected=55); assert old.read_text() == "new season sentinel"
        # A lost activation ACK must be recovered by reading the same epoch;
        # replay must not delete a new season's files.
        prepare()
        commands = root / "commands"; commands.mkdir()
        wrapper = commands / "mysql"
        wrapper.write_text("#!/usr/bin/env python3\nimport subprocess, sys\n"
                           f"result = subprocess.run([{mysql[0]!r}, *sys.argv[1:]])\n"
                           "sys.exit(1 if any(\"UPDATE season_reset_state SET reset_status='active'\" in arg "
                           "for arg in sys.argv) else result.returncode)\n")
        wrapper.chmod(0o700)
        failing_env = dict(env, PATH=str(commands) + ":" + env["PATH"])
        launch(environment=failing_env); assert status() == "2:active"
        old.write_text("saved after ambiguous completion")
        launch(expected=55); assert old.read_text() == "saved after ambiguous completion"
        assert (root / "Players/Backup/keep").read_text() == "archive"
        print("Launcher handoff: incomplete SQL, wrong epoch, concurrent cleanup, symlink, missing access, "
              "partial cleanup, retry, duplicate completion and lost activation ACK passed", flush=True)


if __name__ == "__main__":
    run()
