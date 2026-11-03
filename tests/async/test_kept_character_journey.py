#!/usr/bin/env python3
"""The real post-Keep/pre-entry boundary, using disposable persistence only.

MariaDB runs through with_disposable_mariadb.sh; neither leg reads checkout .env.
"""
import argparse
from contextlib import contextmanager
import os
from pathlib import Path
import subprocess
import time
import uuid

import test_account_recovery_journey as account
import test_creation_prompt_journey as creation


@contextmanager
def persistence(backend):
    if backend == "flatfile":
        yield {}, None
        return
    host = os.environ["TEST_DB_HOST"]
    assert host == "127.0.0.1", "use with_disposable_mariadb.sh"
    password = os.environ["TEST_DB_PASSWORD"]
    assert password, "the disposable database must have a nonempty password"
    database = "kept_character_" + uuid.uuid4().hex[:12]
    environment = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"), "ENVIRONMENT": "local",
        "DB_HOST": host, "DB_PORT": os.environ["TEST_DB_PORT"], "DB_NAME": database,
        "DB_USER": os.environ["TEST_DB_USER"], "DB_PASSWD": password,
        "DB_ALLOWED_TARGETS": host + "/" + database, "MYSQL_PWD": password,
        "DB_TLS": "FALSE", "DB_SOCKET": "", "PERSISTENCE_MODE": "mariadb-primary",
    }
    mysql = ["mysql", "--protocol=tcp", "--skip-ssl", "-h", host,
             "-P", environment["DB_PORT"], "-u", environment["DB_USER"], "-N", "-B"]

    def sql(statement, selected=True):
        return subprocess.check_output(mysql + ([database] if selected else []),
                                       input=statement, text=True, env=environment,
                                       timeout=120).strip()

    sql("CREATE DATABASE " + database + " CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci", False)
    try:
        sql((account.ROOT / "migrations/bootstrap_multithread_safe.sql").read_text())
        for arguments in (("adopt", "--kind", "fresh_bootstrap"), ("run",)):
            result = subprocess.run(["python3", "scripts/migration_runner.py", *arguments],
                                    cwd=account.ROOT, env=environment, capture_output=True, text=True)
            assert result.returncode == 0, result.stdout + result.stderr
        # The minimal world has no legacy level-cap seed. Supply valid fixture
        # data rather than weakening the server's boot policy.
        sql("UPDATE level_cap SET level=31,level_good=31,level_evil=31 WHERE id=1")
        yield environment, sql
    finally:
        sql("DROP DATABASE " + database, False)


def login(server):
    client = account.MudClient(server.plain_port)
    account.enter_account_name(client)
    client.expect("Please enter your password:")
    account.login_to_menu(client, account.OLD_PASSWORD)
    return client


def check_membership(server, sql):
    if sql:
        # Inspect before login, whose projection repair could hide a missing
        # membership if the first snapshot committed only its owner.
        row = sql("SELECT CONCAT(pd.pid,':',COALESCE(pd.account_name,'NULL'),':',pd.level,':',"
                  "pd.save_revision,':',ac.account_name) FROM player_data pd "
                  "JOIN account_characters ac ON ac.pid=pd.pid AND ac.deleted_at IS NULL "
                  "WHERE pd.name='Taverek' AND pd.active=1")
        assert row and f":{account.ACCOUNT}:0:" in row and row.endswith(":" + account.ACCOUNT), row
        for table in ("currency_wallet_baseline", "epic_balance_baseline", "combat_frag_baseline"):
            assert sql(f"SELECT COUNT(*) FROM {table} WHERE pid=(SELECT pid FROM player_data "
                       "WHERE name='Taverek')") == "1", table
    client = login(server)
    try:
        listing = creation.reply(client, "1", "Taverek")
        assert "Taverek" in listing, "kept character is absent from its account"
    finally:
        client.close()


def run(binary, backend):
    with persistence(backend) as (environment, sql):
        with account.IsolatedServer(binary, environment) as server:
            client = account.MudClient(server.plain_port)
            try:
                creation.reach_race(client)
                creation.finish_character_choices(client)
                creation.reply(client, "y", "PRESS RETURN")
                client.close()
                # Allow the real disconnect handler to retire the body before relog.
                time.sleep(0.3)
                if sql:
                    print("post-Keep row:", sql("SELECT pid,name,COALESCE(account_name,'NULL'),"
                                               "level,save_revision FROM player_data "
                                               "WHERE name='Taverek'"), flush=True)
                check_membership(server, sql)
                server.shutdown()
                creation.reboot(server)
                check_membership(server, sql)
                server.shutdown()
            except Exception:
                print(server.server_output()[-3000:])
                print(server.runtime_logs()[-6000:])
                raise
            finally:
                client.close()
    print(f"PASS: {backend} kept level-0 character selectable after disconnect and cold restart")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("mariadb", "flatfile"), required=True)
    parser.add_argument("--server", type=Path, required=True)
    args = parser.parse_args()
    run(args.server.resolve(), args.backend)
