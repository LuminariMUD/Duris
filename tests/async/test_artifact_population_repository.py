#!/usr/bin/env python3
"""Read physical payload pages on a disposable SQL database, never the game DB."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid

from _paths import ROOT

if os.environ.get("TEST_DB_HOST") != "127.0.0.1" or not all(
        os.environ.get(key) for key in ("TEST_DB_PORT", "TEST_DB_USER", "TEST_DB_PASSWORD")):
    raise SystemExit("run with tests/async/with_disposable_mariadb.sh")

output = ROOT / "bin/tests"
output.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="artifact-population-", dir=output) as directory:
    binary = Path(directory) / "population"
    subprocess.run([
        "g++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
        "-fsanitize=undefined", "-fno-sanitize-recover=all", "-Isrc", "-I/usr/include/mysql",
        "tests/async/artifact_population_repository_harness.cpp",
        "src/guild/artifact_population_repository.c", "-lmysqlclient", "-o", str(binary),
    ], cwd=ROOT, check=True)
    subprocess.run([str(binary)], cwd=ROOT, check=True, timeout=30)
    # The small behavioral fixture deliberately admits contradictory legacy rows.
    # Also prove every query against the maintained schema, through its real runner.
    sys.path.insert(0, str(ROOT / "scripts"))
    import migration_runner as runner

    database = "duris_artifact_population_" + uuid.uuid4().hex
    environment = dict(os.environ, MYSQL_PWD=os.environ["TEST_DB_PASSWORD"])
    client = ["mysql", "--protocol=tcp", "-h127.0.0.1", "-P", os.environ["TEST_DB_PORT"],
              "-u", os.environ["TEST_DB_USER"], "-N", "-B"]
    subprocess.run(client + ["-e", "CREATE DATABASE " + database], env=environment, check=True)
    try:
        subprocess.run(client + [database], env=environment, check=True,
                       input=(ROOT / "migrations/bootstrap_multithread_safe.sql").read_text(),
                       text=True)
        os.environ.update(ENVIRONMENT="test", DB_HOST="127.0.0.1",
                          DB_PORT=os.environ["TEST_DB_PORT"], DB_USER=os.environ["TEST_DB_USER"],
                          DB_PASSWD=os.environ["TEST_DB_PASSWORD"], DB_SOCKET="", DB_TLS="FALSE",
                          DB_NAME=database, DB_ALLOWED_TARGETS="127.0.0.1/" + database)
        manifest = runner.load_manifest()
        executor = runner.MysqlExecutor(manifest)
        executor.acquire_lock()
        try:
            executor.adopt("fresh_bootstrap")
        finally:
            executor.release_lock()
        runner.run_pending(manifest, executor)
        subprocess.run([str(binary), database], cwd=ROOT, check=True, timeout=30)
    finally:
        subprocess.run(client + ["-e", "DROP DATABASE " + database], env=environment, check=True)
