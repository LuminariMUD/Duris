#!/usr/bin/env python3
"""Native authority/SQL transaction adapter tests; --mysql uses disposable SQL."""

import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import uuid

from _paths import ROOT


def main():
    use_mysql = "--mysql" in sys.argv
    output = ROOT / "bin/tests"
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="frag-cap-store-", dir=output) as directory:
        binary = str(Path(directory) / "harness")
        flags = ["-D__NO_MYSQL__", "-Isrc/no_mysql"]
        libraries = []
        if use_mysql:
            flags = shlex.split(subprocess.check_output(["mysql_config", "--cflags"], text=True))
            libraries = shlex.split(subprocess.check_output(["mysql_config", "--libs"], text=True))
        subprocess.run([
            "g++", "-std=c++20", "-g", "-Og", "-Wall", "-Wextra", "-Wpedantic", "-Werror",
            "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-fno-pie", "-no-pie",
            "-DDURIS_FLATFILE_AUTHORITY_FAULT_TEST", "-Isrc", *flags,
            "tests/async/frag_cap_repository_harness.cpp", "src/combat/frag_cap.c",
            "src/combat/frag_cap_repository.c", "src/flatfile/flatfile_authority_transaction.c",
            "src/flatfile/flatfile_store.c", "-lcrypto", "-pthread", *libraries, "-o", binary,
        ], cwd=ROOT, check=True)
        if not use_mysql:
            subprocess.run([binary, str(Path(directory) / "state")], cwd=ROOT, check=True)
            return
        assert os.environ["TEST_DB_HOST"] == "127.0.0.1", "requires disposable loopback SQL"
        database = "frag_cap_" + uuid.uuid4().hex[:12]
        environment = dict(os.environ, ENVIRONMENT="test", DB_HOST="127.0.0.1",
                           DB_PORT=os.environ["TEST_DB_PORT"], DB_USER=os.environ["TEST_DB_USER"],
                           DB_PASSWD=os.environ["TEST_DB_PASSWORD"], DB_NAME=database,
                           MYSQL_PWD=os.environ["TEST_DB_PASSWORD"])
        mysql = ["mysql", "--protocol=tcp", "-h127.0.0.1", "-P", environment["DB_PORT"],
                 "-u", environment["DB_USER"], "-N", "-B"]

        def sql(statement, selected=True):
            return subprocess.check_output(mysql + ([database] if selected else []),
                                           input=statement, text=True, env=environment)

        sql("CREATE DATABASE " + database + " CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci", False)
        try:
            sql((ROOT / "migrations/bootstrap_multithread_safe.sql").read_text())
            for args in (("adopt", "--kind", "fresh_bootstrap"), ("run",), ("run",)):
                subprocess.run(["python3", "scripts/migration_runner.py", *args],
                               cwd=ROOT, env=environment, check=True, stdout=subprocess.DEVNULL)
            # Applying the additive migration twice preserves played cap/timer values.
            before = sql("SELECT level,level_good,level_evil,next_update,snapshot IS NULL FROM level_cap")
            migration = ROOT / "migrations/immutable/0057_shared_frag_cap.sql"
            sql(migration.read_text())
            sql(migration.read_text())
            assert sql("SELECT level,level_good,level_evil,next_update,snapshot IS NULL FROM level_cap") == before
            subprocess.run(["bash", "migrations/immutable/0057_shared_frag_cap.sh"],
                           cwd=ROOT, env=environment, check=True)
            # Prints a measured metadata fingerprint if the sealed contract is stale.
            subprocess.run(["bash", "migrations/verify_runtime_compatibility.sh"],
                           cwd=ROOT, env=environment, check=True)
            subprocess.run([binary], cwd=ROOT, env=environment, check=True)
        finally:
            sql("DROP DATABASE " + database, False)


if __name__ == "__main__":
    main()
