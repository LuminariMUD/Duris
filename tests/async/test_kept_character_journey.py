#!/usr/bin/env python3
"""The real post-Keep/pre-entry boundary, using disposable persistence only.

MariaDB runs through with_disposable_mariadb.sh; neither leg reads checkout .env.
"""
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import time
import uuid

import test_account_recovery_journey as account
import test_creation_prompt_journey as creation
from test_character_stat_choice_journey import WebSocketClient


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


def saved_character(server, sql, inspector):
    if sql:
        row = sql("SELECT pid,level,base_str,base_dex,base_agi,base_con,base_pow,"
                  "base_int,base_wis,base_cha,base_kar,base_luk FROM player_data "
                  "WHERE name='Taverek' AND active=1")
        values = list(map(int, row.split()))
        return values[0], values[1], values[2:]
    snapshots = list((server.state_root / "players").glob("*.snapshot"))
    assert len(snapshots) == 1, snapshots
    pid = int(snapshots[0].stem)
    record = json.loads(subprocess.check_output(
        [str(inspector), str(server.state_root), "inspect", str(pid)], text=True))
    return pid, record["membership_level"], record["base_stats"]


def websocket_text(client, needle):
    deadline = time.monotonic() + 20
    while needle not in json.dumps(client.messages):
        assert time.monotonic() < deadline, f"WebSocket never received {needle!r}"
        client.receive()


def override_entry(original, server, sql, inspector, protocol):
    before = saved_character(server, sql, inspector)
    assert before[1] == 0 and len(before[2]) == 10, before
    replacement = None
    try:
        if protocol == "websocket":
            replacement = WebSocketClient(server.websocket_port)
            auth = replacement.command("login", {"account": account.ACCOUNT,
                                       "password": account.OLD_PASSWORD}, "auth")
            assert auth["status"] == "success", auth
            replacement.command("enter", {"character": "Taverek"}, "gmcp")
            websocket_text(replacement, "Your starter kit is ready")
            replacement.command("game", "save", "text")
            websocket_text(replacement, "Save complete for Taverek.")
        else:
            replacement = login(server)
            # Telnet authentication closes the older pre-entry socket before
            # selection; it must then load the committed PID for confirmation.
            original.socket.settimeout(3)
            while original.socket.recv(4096):
                pass
            creation.reply(replacement, "1", "Taverek")
            creation.reply(replacement, "1", "(Y/N)")
            creation.reply(replacement, "y", "Your starter kit is ready")
            replacement.expect("Pos: standing >")
            creation.reply(replacement, "save", "Save complete for Taverek.")
        after = saved_character(server, sql, inspector)
        assert after == (before[0], 1, before[2]), (before, after)
        original.socket.settimeout(3)
        while original.socket.recv(4096):
            pass
        original.close()
        replacement.close()
        server.shutdown()
        creation.reboot(server)
        replacement = login(server)
        creation.reply(replacement, "1", "Taverek")
        creation.reply(replacement, "1", "(Y/N)")
        creation.reply(replacement, "y", "Pos: standing >")
        creation.reply(replacement, "save", "Save complete for Taverek.")
        assert saved_character(server, sql, inspector) == after
        server.shutdown()
    finally:
        if replacement:
            replacement.close()


def run(binary, backend, *, override=None):
    inspector = account.ROOT / "bin/tests/kept-character-inspector"
    if override and backend == "flatfile":
        subprocess.run(["python3", "tests/async/test_flatfile_player_repository.py",
                        "--build-inspector", str(inspector)], cwd=account.ROOT, check=True)
    with persistence(backend) as (environment, sql):
        if override == "websocket":
            environment = dict(environment, DURIS_WEBSOCKET="TRUE")
        with account.IsolatedServer(binary, environment) as server:
            client = account.MudClient(server.plain_port)
            try:
                creation.reach_race(client)
                creation.finish_character_choices(client)
                creation.reply(client, "y", "PRESS RETURN")
                if override:
                    # Read the real committed baseline before selecting it from
                    # another session. The first writer may still be draining.
                    if sql:
                        deadline = time.monotonic() + 10
                        while sql("SELECT COUNT(*) FROM player_data WHERE name='Taverek' "
                                  "AND save_revision>0") != "1":
                            assert time.monotonic() < deadline, "baseline never committed"
                            time.sleep(0.05)
                    override_entry(client, server, sql, inspector, override)
                    print(f"PASS: {backend} pre-entry {override} override reloads the same PID/stats and survives restart")
                    return
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
    parser.add_argument("--override", choices=("telnet", "websocket"), nargs="?", const="telnet",
                        help="select the kept character while its original pre-entry socket remains open")
    args = parser.parse_args()
    run(args.server.resolve(), args.backend, override=args.override)
