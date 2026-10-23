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
#include <spawn.h>
#include <sys/wait.h>
#include <unistd.h>
#define TRUE true
#define FALSE false
#define LOG_DEBUG 0
#define LOG_STATUS 1
#define OVERLORD 62
#define ACCT_IMMORTAL 0
bool pwipe_crossed_boundary, pwipe_filesystem_ready;
void logit(int, const char *format, ...) {
    va_list args; va_start(args, format); vfprintf(stderr, format, args); va_end(args); fputc(10, stderr);
}
void send_to_all(const char *) {}
int frag_cap_config_reset_level() { return 26; }
bool pwipe_quiesce_writers() { return true; }
void pwipe_resume_writers() {}
bool redis_validate_pwipe_state() { return true; }
bool redis_clear_pwipe_state() { return true; }
bool account_bound_rewards_on_successful_pwipe() { return true; }
uint64_t current_season_epoch;
MYSQL_RES *db_query(const char *format, ...) {
    char statement[16384]; va_list args; va_start(args, format);
    vsnprintf(statement, sizeof statement, format, args); va_end(args);
    return mysql_real_query(DB, statement, strlen(statement)) ? nullptr : mysql_store_result(DB);
}
bool qry(const char *format, ...) {
    char statement[16384]; va_list args; va_start(args, format);
    vsnprintf(statement, sizeof statement, format, args); va_end(args);
    const char *fail = getenv("PWIPE_TEST_FAIL_SQL");
    if (fail && strstr(statement, fail)) return false;
    if (mysql_real_query(DB, statement, strlen(statement))) return false;
    MYSQL_RES *result = mysql_store_result(DB); if (result) mysql_free_result(result);
    return true;
}
''' + functions + source[source.index("bool sql_verify_pwipe_manifest(void)"):
                            source.index("void sql_log_player_login", source.rindex("bool sql_pwipe(int code_verify)"))] + '''
int main(int argc, char **argv) {
    if (argc != 3) return 2;
    DB = mysql_init(nullptr);
    if (!mysql_real_connect(DB, getenv("DB_HOST"), getenv("DB_USER"), getenv("DB_PASSWD"),
                            getenv("DB_NAME"), atoi(getenv("DB_PORT")), nullptr, 0)) return 2;
    current_season_epoch = strtoull(argv[2], nullptr, 10);
    bool ok = !strcmp(argv[1], "begin") ? sql_begin_pwipe_epoch() :
              !strcmp(argv[1], "ready") ? sql_prepare_pwipe_filesystem() :
              !strcmp(argv[1], "wipe") ? sql_pwipe(1723699) : sql_load_active_season_state();
    mysql_close(DB);
    return ok ? 0 : 1;
}
''')
    binary = native.with_suffix("")
    subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", str(native),
                    "-lmysqlclient", "-o", str(binary)], check=True)

    def epoch_call(command, epoch, expected_code, cwd=None):
        result = subprocess.run([str(binary), command, str(epoch)], env=env, cwd=cwd,
                                capture_output=True, text=True)
        assert result.returncode == expected_code, (command, epoch, result.returncode, result.stderr)

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
        sql("UPDATE season_reset_state SET season_epoch=1,reset_status='active',"
            "reset_completed_at=NULL WHERE state_id=1")
        sql("INSERT INTO zones(number,name,alignment,epic_type) VALUES(900,'fixture',1,1)")
        sql("INSERT INTO accounts(account_name,password,email,total_donated,confirmed) "
            "VALUES('fixturebank','fixture-password','fixture@example.invalid',123.45,1)")
        account_before = sql("SELECT CONCAT_WS(':',password,email,total_donated,confirmed) "
                             "FROM accounts WHERE account_name='fixturebank'")
        sql("INSERT INTO account_banks(id,account_name,racewar,bank_copper,bank_silver,bank_gold,bank_platinum) "
            "VALUES(900,'fixturebank',1,123,456,789,987),"
            "(901,'fixturebank',2,2,3,4,5),(902,'fixturebank',0,6,7,8,9)")
        sql("INSERT INTO currency_bank_baseline(bank_id,opening_copper,opening_silver,opening_gold,opening_platinum) "
            "SELECT id,bank_copper,bank_silver,bank_gold,bank_platinum FROM account_banks")
        for pid, name, level in ((1001, "Freshgod", 62), (1002, "Lesserstaff", 61),
                                 (1003, "Outofrange", 63), (1004, "Oldmortal", 56)):
            sql("INSERT INTO player_data(pid,name,account_name,level,highest_level,m_class,race,sex,"
                "copper,epics,frags,learned_flight_stops) VALUES(" + str(pid) + ",'" + name +
                "','fixturebank'," + str(level) + "," + str(level) + ",1,1,1,999,888,777,63)")
            sql("INSERT INTO account_characters(account_name,pid,char_name) VALUES('fixturebank'," +
                str(pid) + ",'" + name + "')")
        epoch_call("wipe", 1, 0, cwd=root)
        assert sql("SELECT alignment FROM zones WHERE number=900") == "0"
        assert sql("SELECT CONCAT(season_epoch,':',reset_status,':',reset_completed_at IS NOT NULL) "
                   "FROM season_reset_state WHERE state_id=1") == "2:resetting:1"
        print("Actual native SQL reset/preflight/postflight passed without shared-writer admission", flush=True)
        assert sql("SELECT COUNT(*) FROM player_data WHERE active=1") == "1"
        new_god = int(sql("SELECT pid FROM player_data WHERE name='Freshgod' AND active=1 AND level=62"))
        assert new_god > 1004
        assert sql("SELECT CONCAT_WS(':',copper,epics,frags,learned_flight_stops,assoc_id) "
                   "FROM player_data WHERE pid=" + str(new_god)) == "0:0:0:0:0"
        assert sql("SELECT COUNT(*) FROM account_characters WHERE deleted_at IS NULL AND pid=" + str(new_god)) == "1"
        assert sql("SELECT COUNT(*) FROM player_data WHERE pid BETWEEN 1001 AND 1004 AND active=0 "
                   "AND name=CONCAT('~pwipe-',pid)") == "4"
        assert sql("SELECT COUNT(*) FROM currency_wallet_baseline WHERE pid=" + str(new_god)) == "1"
        sql("INSERT INTO player_data(name,account_name) VALUES('Oldmortal','fixturebank')")
        print("Overlord recreation: exact 62 only, new PID, clean balances/progression, account mapping and freed mortal name passed", flush=True)
        assert sql("SELECT COUNT(*) FROM account_banks") == "0"
        assert sql("SELECT CONCAT_WS(':',password,email,total_donated,confirmed) "
                   "FROM accounts WHERE account_name='fixturebank'") == account_before
        assert sql("SELECT opening_platinum FROM currency_bank_baseline WHERE bank_id=900") == "987"
        sql("INSERT INTO account_banks(account_name,racewar) VALUES('fixturebank',1)")
        new_bank = int(sql("SELECT id FROM account_banks WHERE account_name='fixturebank' AND racewar=1"))
        assert new_bank > 902
        assert sql("SELECT CONCAT_WS(':',bank_copper,bank_silver,bank_gold,bank_platinum) "
                   "FROM account_banks WHERE id=" + str(new_bank)) == "0:0:0:0"
        assert sql("SELECT COUNT(*) FROM currency_bank_baseline WHERE bank_id=" + str(new_bank)) == "0"
        print("Bank reset: all sides removed, credentials/donations/history retained, new ID and zero balances passed", flush=True)
        roster_before = sql("SELECT pid,name,level,active FROM player_data ORDER BY pid")
        mappings_before = sql("SELECT pid,char_name,deleted_at FROM account_characters ORDER BY id")
        sql("UPDATE season_reset_state SET reset_status='active' WHERE state_id=1")
        env["PWIPE_TEST_FAIL_SQL"] = "INSERT INTO epic_balance_baseline"
        try:
            epoch_call("wipe", 2, 1, cwd=root)
        finally:
            del env["PWIPE_TEST_FAIL_SQL"]
        assert sql("SELECT pid,name,level,active FROM player_data ORDER BY pid") == roster_before
        assert sql("SELECT pid,char_name,deleted_at FROM account_characters ORDER BY id") == mappings_before
        assert sql("SELECT CONCAT(reset_status,':',reset_completed_at IS NULL) "
                   "FROM season_reset_state WHERE state_id=1") == "resetting:1"
        print("Mid-recreation failure rolled back the entire roster and kept startup fenced", flush=True)
        sql("UPDATE season_reset_state SET reset_status='active' WHERE state_id=1")
        before = sql("SELECT season_epoch,reset_status FROM season_reset_state WHERE state_id=1")
        sql("ALTER TABLE player_data RENAME COLUMN base_luk TO fixture_base_luk")
        try:
            epoch_call("wipe", 3, 1, cwd=root)
            assert sql("SELECT season_epoch,reset_status FROM season_reset_state WHERE state_id=1") == before
        finally:
            sql("ALTER TABLE player_data RENAME COLUMN fixture_base_luk TO base_luk")
        print("Missing recreation schema rejected before the irreversible boundary", flush=True)



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
