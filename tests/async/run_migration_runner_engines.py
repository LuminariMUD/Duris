#!/usr/bin/env python3
"""A new database reaches the migration head on every supported engine, through the runner.

The sealed verifiers of 0031 and 0032 accept only MariaDB 10.11 and MySQL 8.0, so a
database built on MariaDB 11.8 stopped at 0031 ("unsupported database engine"). Their
files cannot change: each history row keeps the verifier's checksum. The manifest now
lists an 11.8 verifier for each, and the runner runs it in their place on 11.8.

On each image: bootstrap, `migration_runner.py adopt` and `run` reach all migrations,
with the history checksum the manifest gives on every engine, and an edited history row
then stops the runner.

Usage: run_migration_runner_engines.py [image ...]; the default is all three.
"""
from pathlib import Path
import os
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import migration_runner as runner  # noqa: E402

IMAGES = ("mariadb:11.8", "mariadb:10.11", "mysql:8.0")


def check(image: str, expected_head: str) -> None:
    name = "duris-runner-engines-" + uuid.uuid4().hex[:10]
    password = "runner-" + uuid.uuid4().hex[:12]
    variable = "MARIADB_ROOT_PASSWORD" if image.startswith("mariadb") else "MYSQL_ROOT_PASSWORD"
    # The host's client is MariaDB's; MySQL 8.0 serves it native passwords.
    extra = ["--default-authentication-plugin=mysql_native_password"] \
        if image.startswith("mysql") else []
    subprocess.run(["docker", "run", "-d", "--name", name, "-p", "127.0.0.1::3306",
                    "-e", f"{variable}={password}", image, *extra],
                   check=True, capture_output=True)
    try:
        port = subprocess.check_output(["docker", "port", name, "3306/tcp"],
                                       text=True).split(":")[-1].strip()
        environment = dict(os.environ, ENVIRONMENT="test", DB_HOST="127.0.0.1",
                           DB_PORT=port, DB_USER="root", DB_PASSWD=password,
                           DB_NAME="runner_engines", MYSQL_PWD=password)
        mysql = ["mysql", "--protocol=tcp", "-h", "127.0.0.1", "-P", port, "-uroot", "-N", "-B"]

        def sql(statement, database="runner_engines"):
            return subprocess.check_output(mysql + ([database] if database else []),
                                           input=statement, text=True,
                                           env=environment).strip()

        deadline = time.monotonic() + 120
        while subprocess.run(mysql + ["-e", "SELECT 1"], env=environment,
                             capture_output=True).returncode:
            assert time.monotonic() < deadline, f"{image} did not start"
            time.sleep(1)
        time.sleep(2)
        version = sql("SELECT VERSION();", None)
        sql("CREATE DATABASE runner_engines CHARACTER SET utf8mb4 "
            "COLLATE utf8mb4_unicode_ci;", None)
        sql((ROOT / "migrations/bootstrap_multithread_safe.sql").read_text())

        def migrate(*arguments):
            return subprocess.run([sys.executable, "scripts/migration_runner.py", *arguments],
                                  cwd=ROOT, env=environment, capture_output=True, text=True)

        for arguments in (("adopt", "--kind", "fresh_bootstrap"), ("run",)):
            result = migrate(*arguments)
            assert result.returncode == 0, f"{image} ({version}): {result.stderr}"
        head = sql("SELECT applied_count, LOWER(HEX(history_checksum)) FROM "
                   "mud_schema_migration_state WHERE state_id=1;")
        assert head == expected_head, f"{image} ({version}) stopped at {head}"
        sql("UPDATE mud_schema_history SET description='edited' WHERE sequence_number=31;")
        refused = migrate("run")
        assert refused.returncode == 2 and "history" in refused.stderr, \
            f"{image}: an edited history was not refused: {refused.stderr}"
        print(f"[PASS] {image} ({version}): the runner reaches the head with the same history, "
              "and refuses an edited one", flush=True)
    finally:
        subprocess.run(["docker", "rm", "-fv", name], capture_output=True)


def main() -> int:
    manifest = runner.load_manifest()
    rows = [runner.AppliedMigration(step.migration_id, step.sequence, step.description,
                                    step.apply_checksum, step.verify_checksum,
                                    step.compatibility, manifest.runner_version)
            for step in manifest.migrations]
    expected_head = f"{len(rows)}\t{runner.history_checksum(rows)}"
    for image in sys.argv[1:] or IMAGES:
        check(image, expected_head)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
