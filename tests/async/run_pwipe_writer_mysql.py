#!/usr/bin/env python3
"""Qualify the real shared writer/SQL callback chain on an owned migrated DB."""
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[2]


def main():
    if not os.environ.get("TEST_DB_HOST"):
        wrapper = ROOT / "tests/async/with_disposable_mariadb.sh"
        os.execv(str(wrapper), [str(wrapper), sys.executable, str(Path(__file__).resolve())])
    if os.environ["TEST_DB_HOST"] != "127.0.0.1" or int(os.environ["TEST_DB_PORT"]) in (3306, 3307):
        raise SystemExit("Use the owned disposable SQL wrapper on a random loopback port")
    database = "pwipe_writer_" + uuid.uuid4().hex
    env = dict(PATH=os.environ.get("PATH", "/usr/bin:/bin"), ENVIRONMENT="local",
               PERSISTENCE_MODE="mariadb-primary", DB_HOST="127.0.0.1",
               DB_PORT=os.environ["TEST_DB_PORT"], DB_USER=os.environ["TEST_DB_USER"],
               DB_PASSWD=os.environ["TEST_DB_PASSWORD"], DB_NAME=database)
    env["DB_ALLOWED_TARGETS"] = "127.0.0.1/" + database
    env["MYSQL_PWD"] = env["DB_PASSWD"]
    mysql = [shutil.which("mysql"), "--protocol=tcp", "-h", "127.0.0.1", "-P", env["DB_PORT"],
             "-u", env["DB_USER"], "-N", "-B"]
    subprocess.run(mysql + ["-e", "CREATE DATABASE " + database +
                            " CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"], env=env, check=True)
    try:
        subprocess.run(mysql + [database], input=(ROOT / "migrations/bootstrap_multithread_safe.sql").read_bytes(),
                       env=env, check=True, stdout=subprocess.DEVNULL)
        for arguments in (("adopt", "--kind", "fresh_bootstrap"), ("run",)):
            subprocess.run([sys.executable, str(ROOT / "scripts/migration_runner.py"), *arguments],
                           env=env, cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
        version = subprocess.check_output(mysql + [database, "-e", "SELECT VERSION()"], env=env, text=True).strip()
        print("Real writer/SQL canonical schema on " + version, flush=True)
        compiled = ROOT / "bin/tests"
        compiled.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="pwipe-writer-", dir=compiled) as temporary:
            work = Path(temporary)
            comm = (ROOT / "src/net/comm.c").read_text()
            preparation = comm[comm.index("void pwipe_resume_writers(void)"):
                               comm.index("static void critical_gameplay_handle_completions(")]
            (work / "pwipe_preparation.inc").write_text(preparation)
            sources = ["tests/async/pwipe_writer_mysql_harness.cpp", "tests/async/harness_stubs.cpp",
                       "src/player/player_save_worker.c", "src/player/player_snapshot_repository.c",
                       "src/player/player_snapshot_codec.c", "src/sql/sql_async.c", "src/sql/sql_pool.c",
                       "src/item/item_claim_repository.c", "src/item/item_claim.c", "src/persistence/dupe_log.c",
                       "src/sql/item_extra_descr_codec.c", "src/persistence/persistence_observability.c"]
            cflags = shlex.split(subprocess.check_output(["mysql_config", "--cflags"], text=True))
            libs = shlex.split(subprocess.check_output(["mysql_config", "--libs"], text=True))
            binary = work / "pwipe_writer"
            subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-pthread",
                            "-ffunction-sections", "-fdata-sections", "-Isrc", "-I" + str(work),
                            *cflags, *sources, "-Wl,--gc-sections", *libs, "-lcrypto", "-o", str(binary)],
                           cwd=ROOT, check=True)
            for scenario in ("success", "timeout", "error"):
                subprocess.run([str(binary), scenario], env=env, cwd=work, check=True, timeout=25)
    finally:
        subprocess.run(mysql + ["-e", "DROP DATABASE " + database], env=env, check=True)


if __name__ == "__main__":
    main()
