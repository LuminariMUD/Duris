#!/usr/bin/env python3
"""Run the exact coin journey on disposable MariaDB using its real saved rows.

Invoke through tests/async/with_disposable_mariadb.sh. No checkout .env is read.
"""

import argparse
import os
from pathlib import Path
import subprocess
import uuid
from unittest.mock import patch

import test_coin_denomination_journey as coins

ROOT = coins.ROOT


def run(binary):
    database = "coin_journey_test_" + uuid.uuid4().hex[:12]
    host = os.environ["TEST_DB_HOST"]
    assert host == "127.0.0.1", "use the disposable loopback database runner"
    environment = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "ENVIRONMENT": "local", "DB_HOST": host,
        "DB_PORT": os.environ["TEST_DB_PORT"], "DB_NAME": database,
        "DB_USER": os.environ["TEST_DB_USER"], "DB_PASSWD": os.environ["TEST_DB_PASSWORD"],
        "DB_ALLOWED_TARGETS": host + "/" + database,
        "MYSQL_PWD": os.environ["TEST_DB_PASSWORD"], "DB_TLS": "FALSE", "DB_SOCKET": "",
        "PERSISTENCE_MODE": "mariadb-primary", "REDIS": "FALSE", "CHAOS_MUD": "FALSE",
    }
    if "LD_LIBRARY_PATH" in os.environ:
        environment["LD_LIBRARY_PATH"] = os.environ["LD_LIBRARY_PATH"]
    mysql = ["mysql", "--protocol=tcp", "--skip-ssl", "-h", host,
             "-P", environment["DB_PORT"], "-u", environment["DB_USER"], "-N", "-B"]

    def sql(text, selected=True):
        return subprocess.check_output(
            mysql + ([database] if selected else []), input=text,
            text=True, env=environment, timeout=120).strip()

    def inspect(_state, pid=1):
        assert pid in (1, 2)
        name = coins.journey.CHARACTER if pid == 1 else coins.TARGET
        account = coins.journey.ACCOUNT if pid == 1 else coins.TARGET_ACCOUNT
        fields = list(map(int, sql(
            "SELECT pid,copper,silver,gold,platinum,wallet_revision,level,racewar "
            f"FROM player_data WHERE name='{name}'").split("\t")))
        actual_pid, *values = fields
        bank = sql("SELECT bank_copper,bank_silver,bank_gold,bank_platinum "
                   f"FROM account_banks WHERE account_name='{account}' AND racewar={values[6]}")
        piles = sql("SELECT obj_uid,container_id,value0,value1,value2,value3 "
                    f"FROM player_items WHERE pid={actual_pid} AND item_type=20 ORDER BY id")
        return {
            "wallet": values[:4], "wallet_revision": values[4], "level": values[5],
            "bank": list(map(int, bank.split("\t"))) if bank else [0, 0, 0, 0],
            "coin_items": [
                {"uid": int(row[0]), "coins": list(map(int, row[2:]))}
                for row in (line.split("\t") for line in piles.splitlines())
            ],
        }

    sql("CREATE DATABASE " + database + " CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci", False)
    try:
        sql((ROOT / "migrations/bootstrap_multithread_safe.sql").read_text())
        subprocess.run(["python3", "scripts/migration_runner.py", "adopt", "--kind", "fresh_bootstrap"],
                       cwd=ROOT, env=environment, check=True)
        subprocess.run(["python3", "scripts/migration_runner.py", "run"],
                       cwd=ROOT, env=environment, check=True)
        # Only the read-only inspector changes; all commands, assertions, server
        # restarts, and the production currency/save/load implementations are real.
        with patch.object(coins, "inspect", inspect):
            coins.run(binary, environment)
    finally:
        sql("DROP DATABASE " + database, False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", type=Path, required=True)
    args = parser.parse_args()
    run(args.server.resolve())
