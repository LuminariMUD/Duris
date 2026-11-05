#!/usr/bin/env python3
"""The real post-Keep/pre-entry boundary, using disposable persistence only.

MariaDB runs through with_disposable_mariadb.sh; neither leg reads checkout .env.
"""
import argparse
import fcntl
from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import uuid

import test_account_recovery_journey as account
import test_creation_prompt_journey as creation
from test_character_stat_choice_journey import WebSocketClient


@contextmanager
def kept_journey_binary(server: Path | None, backend: str):
    if server is not None:
        yield server.resolve()
        return
    if backend != "flatfile":
        raise SystemExit("--server is required with --backend mariadb")
    output = account.ROOT / "bin/tests"
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="kept-flatfile-build-", dir=output) as directory:
        yield account.build_flatfile_server(Path(directory))


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


def login(server, name=account.ACCOUNT):
    client = account.MudClient(server.plain_port)
    account.enter_account_name(client, name)
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


def character_choices(client, name="Taverek", *, chaos=False):
    creation.start_character(client)
    creation.reply(client, name, "Is this correct?")
    creation.reply(client, "y", "meet these criteria?")
    creation.reply(client, "y", creation.RACE_MENU)
    creation.finish_character_choices(client, chaos=chaos)


def websocket_character(client, name="Taverek"):
    options = client.command("chargen_options")
    human = next(race for race in options["races"] if race["id"] == 1)
    warrior = next(kind for kind in human["classes"] if kind["name"].lower() == "warrior")
    homes = client.command("get_hometowns", {"race": 1}, "hometowns")
    home = next(home for home in homes["options"] if "Plane" in home["name"])
    client.command("roll_stats", {"race": 1, "method": "default"})
    for stat in ("str", "dex", "agi", "luk"):
        client.command("add_bonus", {"stat": stat}, "bonus_added")
    return client.command("create_character", {"name": name, "race": 1, "class": warrior["id"],
                          "sex": 1, "alignment": "good", "hometown": home["id"], "newbie": True})


def saved_character(server, sql, inspector, name="Taverek"):
    if sql:
        row = sql("SELECT pid,level,base_str,base_dex,base_agi,base_con,base_pow,"
                  "base_int,base_wis,base_cha,base_kar,base_luk FROM player_data "
                  f"WHERE name='{name}' AND active=1")
        values = list(map(int, row.split()))
        return values[0], values[1], values[2:]
    snapshots = list((server.state_root / "players").glob("*.snapshot"))
    for snapshot in snapshots:
        pid = int(snapshot.stem)
        record = json.loads(subprocess.check_output(
            [str(inspector), str(server.state_root), "inspect", str(pid)], text=True))
        if record["name"].lower() == name.lower():
            return pid, record["membership_level"], record["base_stats"]
    raise AssertionError(f"No saved {name} in {snapshots}")


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
            creation.reply(replacement, "y", "PRESS RETURN")
            creation.reply(replacement, "", "Your starter kit is ready")
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


@contextmanager
def pause_writer(server, sql, pid=None):
    if sql:
        env = server.environment
        command = ["mysql", "--protocol=tcp", "--skip-ssl", "-h", env["DB_HOST"],
                   "-P", env["DB_PORT"], "-u", env["DB_USER"], "-N", "-B",
                   "--unbuffered", env["DB_NAME"]]
        lock = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                text=True, env=env, bufsize=1)
        try:
            row = (f"SELECT pid FROM player_data WHERE pid={pid}" if pid else
                   f"SELECT account_name FROM accounts WHERE account_name='{account.ACCOUNT}'")
            lock.stdin.write("START TRANSACTION; " + row + " FOR UPDATE;\n")
            lock.stdin.flush()
            assert lock.stdout.readline().strip() == (str(pid) if pid else account.ACCOUNT)
            yield
        finally:
            lock.communicate("COMMIT;\n", timeout=10)
            assert lock.returncode == 0
    else:
        # This fresh fixture's first PID is 1. Its player-file lock blocks the
        # writer without blocking monotonic PID allocation on the game loop.
        players = server.state_root / "players"
        players.mkdir(mode=0o700, exist_ok=True)
        with (players / f".player-{pid or 1}.lock").open("a") as lock:
            os.chmod(lock.name, 0o600)
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)


def delayed_disconnect(client, server, sql, inspector, reject=False):
    if reject:
        if sql:
            sql("CREATE TRIGGER reject_kept_mapping BEFORE INSERT ON account_characters "
                "FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='synthetic kept rollback'")
        else:
            subprocess.run([str(inspector), str(server.state_root), "block-account", account.ACCOUNT, "1"], check=True)
    cached = None
    with pause_writer(server, sql):
        response = creation.reply(client, "y", "Saving your character. Please wait.")
        client._receive()
        assert "PRESS RETURN" not in response + client.pending.decode(errors="replace"), response
        probe = WebSocketClient(server.websocket_port)
        try:
            result = probe.command("validate_name", {"name": "tAvErEk"})
            assert result["valid"] is False, "pending Keep did not reserve its name"
            client.close()
            deadline = time.monotonic() + 10
            while "Losing player: Taverek" not in server.runtime_logs():
                assert time.monotonic() < deadline, "pre-entry disconnect did not retire its body"
                time.sleep(0.05)
            result = probe.command("validate_name", {"name": "Taverek"})
            assert result["valid"] is False, "disconnect released an unresolved reservation"
            assert server.process.poll() is None, "server stopped during delayed Keep"
        finally:
            probe.close()
        if not sql and not reject:
            cached = login(server)  # a login before commit initially has no membership
    if reject:
        probe = WebSocketClient(server.websocket_port)
        try:
            deadline = time.monotonic() + 15
            while not probe.command("validate_name", {"name": "Taverek"})["valid"]:
                assert time.monotonic() < deadline, "known failed Keep retained its reservation"
                time.sleep(0.05)
        finally:
            probe.close()
        if sql:
            assert sql("SELECT COUNT(*) FROM player_data WHERE name='Taverek'") == "0"
            assert sql("SELECT COUNT(*) FROM account_characters WHERE char_name='Taverek'") == "0"
            sql("DROP TRIGGER reject_kept_mapping")
        else:
            assert not list((server.state_root / "players").glob("*.snapshot"))
            subprocess.run([str(inspector), str(server.state_root), "block-account", account.ACCOUNT, "0"], check=True)
        server.shutdown()
        creation.reboot(server)
        probe = WebSocketClient(server.websocket_port)
        try:
            assert probe.command("validate_name", {"name": "Taverek"})["valid"]
        finally:
            probe.close()
        retry = login(server)
        try:
            character_choices(retry)
            creation.reply(retry, "y", creation.MENU)
            if sql:
                assert int(sql("SELECT pid FROM player_data WHERE name='Taverek'")) > 1
            else:
                assert all(int(path.stem) > 1 for path in (server.state_root / "players").glob("*.snapshot"))
        finally:
            retry.close()
        check_membership(server, sql)
        server.shutdown()
        creation.reboot(server)
        check_membership(server, sql)
        server.shutdown()
        return
    deadline = time.monotonic() + 15
    while not (sql("SELECT COUNT(*) FROM player_data WHERE name='Taverek' AND save_revision>0") == "1"
               if sql else (server.state_root / "players/1.snapshot").is_file()):
        assert time.monotonic() < deadline, "released writer did not commit the kept character"
        time.sleep(0.05)
    if cached:
        deadline = time.monotonic() + 10
        try:
            while True:
                cached.send("1")
                result, _ = cached.expect_any(("Taverek", "Account currently doesn't have any characters"))
                if result == "Taverek":
                    break
                cached.expect(creation.MENU)
                assert time.monotonic() < deadline, "commit did not refresh a logged-in account cache"
                time.sleep(0.05)
        finally:
            cached.close()
    check_membership(server, sql)
    server.shutdown()
    creation.reboot(server)
    check_membership(server, sql)
    server.shutdown()


def run(binary, backend, *, override=None, delay=False, reject=False):
    inspector = account.ROOT / "bin/tests/kept-character-inspector"
    if (override or reject) and backend == "flatfile":
        subprocess.run(["python3", "tests/async/test_flatfile_player_repository.py",
                        "--build-inspector", str(inspector)], cwd=account.ROOT, check=True)
    with persistence(backend) as (environment, sql):
        if override == "websocket" or delay:
            environment = dict(environment, DURIS_WEBSOCKET="TRUE")
        with account.IsolatedServer(binary, environment) as server:
            client = account.MudClient(server.plain_port)
            try:
                account.create_account(client, account.OLD_PASSWORD)
                character_choices(client)
                if delay:
                    delayed_disconnect(client, server, sql, inspector, reject)
                    print(f"PASS: {backend} delayed Keep {'rollback releases only its attempt' if reject else 'stays responsive/reserved after disconnect, commits and survives restart'}")
                    return
                creation.reply(client, "y", creation.MENU)
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
    parser.add_argument("--backend", choices=("mariadb", "flatfile"), default="flatfile")
    parser.add_argument("--server", type=Path)
    parser.add_argument("--override", choices=("telnet", "websocket"), nargs="?", const="telnet",
                        help="select the kept character while its original pre-entry socket remains open")
    parser.add_argument("--delay", action="store_true", help="hold the initial writer and disconnect before acknowledgment")
    parser.add_argument("--reject", action="store_true", help="refuse the delayed initial save and verify reservation cleanup")
    args = parser.parse_args()
    with kept_journey_binary(args.server, args.backend) as binary:
        run(binary, args.backend, override=args.override, delay=args.delay or args.reject, reject=args.reject)
