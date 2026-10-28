#!/usr/bin/env python3
"""Real launch-gate sockets, copyover, restart and deadline on disposable state.

Run MariaDB under with_disposable_mariadb.sh; flatfile needs its own maintained
binary. Never reads checkout .env, changes the host clock or touches live data.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import signal
import socket
import ssl
import subprocess
import tempfile
import time

import test_flatfile_combat_journey as journey
from test_character_stat_choice_journey import WebSocketClient
from test_flight_network_journey import authority, command

ROOT = journey.ROOT
APPROVED, KEEPER = "Launchallow", "Launchkeeper"
PUBLIC, GUEST = "Launchpublic", "Launchguest"
STAFF_ACCOUNT, STAFF = "Launchstaff", "Launchwarden"


class TLSClient(journey.MudClient):
    def __init__(self, port):
        self.socket = ssl._create_unverified_context().wrap_socket(
            socket.create_connection(("127.0.0.1", port), timeout=10), server_hostname="localhost")
        self.socket.settimeout(.25)
        self.pending, self.transcript, self.raw_transcript = bytearray(), bytearray(), bytearray()


def account_prompt(client):
    entry, _ = client.expect_any(("term type", "account name"))
    start = len(client.raw_transcript)
    if entry == "term type":
        client.send("9")
        client.expect("account name")
    return start


def login(client, account, password=journey.PASSWORD):
    start = account_prompt(client)
    client.send(account)
    client.expect("enter your password")
    client.send(password)
    return start


def enter(client, account=APPROVED, character=KEEPER):
    login(client, account)
    client.expect("PRESS RETURN")
    client.send("")
    client.expect("Please select an option")
    client.send("1")
    client.expect(character)
    client.send(character)
    response, _ = client.expect_any(("Play as", "Reconnecting...", "Overriding old connection..."))
    if response == "Play as":
        client.send("y")
        client.expect("Welcome to Duris", timeout=60)
    command(client, "score")
    return client


def drained(client, marker="Reconnect at"):
    client.expect(marker, timeout=30)
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            chunk = client.socket.recv(65536)
        except socket.timeout:
            continue
        if not chunk:
            return bytes(client.raw_transcript)
        client.raw_transcript.extend(chunk)
    raise AssertionError("denied connection did not close after its screen drained")


def websocket_drained(client):
    while True:
        try:
            message = client.receive()
        except AssertionError as error:
            assert str(error).startswith(("WebSocket closed before its response",
                                          "server closed WebSocket:")), str(error)
            return
        except ConnectionError:
            return
        assert message.get("status") not in ("success", "created", "reconnected"), message


def launch_config(path, deadline, approved=APPROVED):
    timestamp = datetime.fromtimestamp(deadline, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    path.write_text("enabled=true\nopens_at_utc=" + timestamp + "\nallowed_accounts=" + approved + "\n")
    return timestamp


def run(binary, backend):
    output_root = ROOT / "bin/analysis/pwipe-launch"
    output_root.mkdir(parents=True, exist_ok=True)
    evidence = {"backend": backend, "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
                "revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                "status": "running"}
    with tempfile.TemporaryDirectory(prefix="pwipe-launch-", dir=ROOT / "bin/tests") as temporary:
        runtime = Path(temporary)
        journey.make_fixture(runtime)
        journey.generate_certificate(runtime)
        (runtime / "logs/log").mkdir(parents=True)
        (runtime / "logs/log/.gitignore").write_text("*\n!.gitignore\n")
        (runtime / "copyover-state").mkdir(mode=0o700)
        critical = runtime / "journals/critical"
        critical.mkdir(parents=True, mode=0o700)
        (runtime / "bin/server").mkdir(parents=True)
        executable = runtime / "bin/server/dms"
        executable.write_bytes(binary.read_bytes())
        executable.chmod(0o700)
        plain, tls, ws_port = journey.available_ports()
        config = runtime / "lib/pwipe_launch.cfg"
        log = runtime / "server.out"
        process, clients, approved_snapshot = None, [], None
        with authority(backend, runtime) as (env, sql), log.open("w") as output:
            env.update(DURIS_DEV_PORT=str(plain), DURIS_TLS_PORT=str(tls), DURIS_WEBSOCKET_PORT=str(ws_port),
                       DURIS_WEBSOCKET="TRUE", CRITICAL_COMMAND_JOURNAL_DIR=str(critical),
                       COPYOVER_STATE_FILE=str(runtime / "copyover-state/copyover.dat"))

            def boot():
                nonlocal process
                offset = log.stat().st_size
                process = subprocess.Popen([str(executable), "--minimal", "-d", str(runtime), str(plain)],
                                           cwd=runtime, env=env, stdout=output, stderr=subprocess.STDOUT)
                deadline = time.monotonic() + 120
                while b"Entering game loop." not in log.read_bytes()[offset:]:
                    assert process.poll() is None and time.monotonic() < deadline, log.read_text(errors="replace")[-5000:]
                    time.sleep(.1)

            def stop():
                nonlocal process
                for client in clients:
                    client.close()
                clients.clear()
                if process and process.poll() is None:
                    process.terminate()
                    process.wait(timeout=45)
                    assert process.returncode == 0
                process = None

            def connect(factory=journey.MudClient):
                client = factory(tls if factory == TLSClient else plain)
                clients.append(client)
                return client

            def websocket():
                client = WebSocketClient(ws_port)
                clients.append(client)
                return client

            def counts():
                if sql:
                    return sql("SELECT (SELECT COUNT(*) FROM accounts),(SELECT COUNT(*) FROM player_data),"
                               "(SELECT COUNT(*) FROM account_characters),(SELECT COUNT(*) FROM player_items)")
                state = Path(env["FLATFILE_STATE_DIR"])
                records = {}
                for directory in ("identities/accounts", "players"):
                    files = [path for path in (state / directory).rglob("*")
                             if path.is_file() and not path.name.startswith(".")]
                    assert len(files) >= 3, "missing seeded account/player authority"
                    records.update({str(path.relative_to(state)):
                                    "admitted player keeps saving" if path == approved_snapshot else
                                    hashlib.sha256(path.read_bytes()).hexdigest()
                                    for path in files})
                return records

            try:
                # Real boot errors must happen before any player listener is reachable.
                shipped = config.read_bytes()
                for invalid in (None, b"enabled=true\nunknown=value\n"):
                    if invalid is None:
                        config.unlink()
                    else:
                        config.write_bytes(invalid)
                    for mode in (["--minimal"], []):
                        bad = subprocess.run([str(executable), *mode, str(plain)], cwd=runtime,
                                             env=env, capture_output=True, timeout=30)
                        assert bad.returncode != 0
                        for port in (plain, tls, ws_port):
                            probe = socket.socket()
                            assert probe.connect_ex(("127.0.0.1", port)) != 0
                            probe.close()
                config.write_bytes(shipped)
                boot()
                for account, name in ((APPROVED, KEEPER), (PUBLIC, GUEST), (STAFF_ACCOUNT, STAFF)):
                    client = connect()
                    journey.create_character(client, account=account, character=name,
                                             email=account.lower() + "@example.invalid")
                    client.send("save")
                    client.expect("Save complete for " + name + ".")
                stop()
                if sql:
                    sql("UPDATE player_data SET level=62,highest_level=62 WHERE name='" + STAFF + "'")
                else:
                    journey.make_overlord(Path(env["FLATFILE_STATE_DIR"]), STAFF)
                    # Identify the synthetic admitted body's uncompressed snapshot.
                    # Its ordinary live saves are allowed; every refused body's bytes
                    # and every account record must stay unchanged during denials.
                    snapshots = [path for path in (Path(env["FLATFILE_STATE_DIR"]) / "players").glob("*.snapshot")
                                 if KEEPER.encode() in path.read_bytes()]
                    assert len(snapshots) == 1
                    approved_snapshot = snapshots[0]
                boot()
                keeper = enter(connect())
                guest = enter(connect(), PUBLIC, GUEST)
                deadline = int(time.time()) + 60
                timestamp = launch_config(config, deadline, APPROVED + ",Missingacct")
                evidence["opens_at_utc"] = timestamp
                # Apply the synthetic config by real copyover; its recovered public
                # descriptor must be denied using the player repository's owner.
                process.send_signal(signal.SIGUSR1)
                keeper.expect("Copyover complete!", timeout=90)
                denied = drained(guest)
                assert timestamp[:10].encode() in denied and b"ACCOUNT MENU" not in guest.pending
                who = command(keeper, "who")
                assert GUEST not in who
                baseline = counts()
                evidence["copyover"] = "approved socket restored; public socket drained and refused before publication"
                print("PASS: real copyover enforces authoritative account ownership", flush=True)

                for factory in (journey.MudClient, TLSClient):
                    # greet() selects ANSI directly; generic/Quick are harness cases.
                    client = connect(factory)
                    start = login(client, PUBLIC)
                    transcript = drained(client)[start:]
                    assert b"THE WORLD REFORGED" in transcript
                    (output_root / (backend + "-" + factory.__name__ + "-ansi.txt")).write_bytes(transcript)
                    wrong = connect(factory)
                    login(wrong, APPROVED, password="Wrong-password!")
                    drained(wrong, "Invalid Password")
                    staff = connect(factory)
                    login(staff, STAFF_ACCOUNT)
                    drained(staff)
                    missing = connect(factory)
                    account_prompt(missing)
                    missing.send("Missingacct")
                    drained(missing)
                for account in (PUBLIC, STAFF_ACCOUNT):
                    client = websocket()
                    denied = client.command("login", {"account": account, "password": journey.PASSWORD}, "auth")
                    assert denied["status"] == "failed" and "Reconnect at" in denied["error"]
                    assert "\x1b" not in denied["error"] and timestamp[:10] in denied["error"]
                    # Later frames may not regain admission while the denial drains.
                    try:
                        client.send_frame(1, b'{"cmd":"register","data":{"account":"Lateaccount"}}')
                    except ConnectionError:
                        pass
                    websocket_drained(client)
                client = websocket()
                wrong = client.command("login", {"account": APPROVED, "password": "Wrong-password!"}, "auth")
                assert wrong["status"] == "failed" and "Reconnect at" not in wrong["error"]
                client = websocket()
                refused = client.command("register", {"account": "Missingacct", "password": journey.PASSWORD,
                                                       "email": "missing@example.invalid"}, "auth")
                assert refused["status"] == "failed" and "Reconnect at" in refused["error"]
                after = counts()
                assert after == baseline, ("refused attempts persisted accounts, bodies or starter items", baseline, after)
                if sql:
                    # Even the account-deletion continuation must not replace the
                    # closed public launch screen after successful authentication.
                    sql("UPDATE accounts SET blocked=2 WHERE account_name='" + PUBLIC + "'")
                    try:
                        client = connect()
                        login(client, PUBLIC)
                        drained(client)
                    finally:
                        sql("UPDATE accounts SET blocked=0 WHERE account_name='" + PUBLIC + "'")
                    evidence["deletion_fence"] = "unlisted deletion-fenced account still receives launch denial"
                evidence["closed_transports"] = "Telnet/TLS ANSI and WS; wrong passwords; unlisted staff; absent allowlisted registration; no new persisted state"
                print("PASS: closed Telnet/TLS/WS login and registration, unchanged body/item counts", flush=True)

                # Native WebSocket auto-reconnect may replace the approved Telnet session.
                client = websocket()
                approved = client.command("login", {"account": APPROVED, "password": journey.PASSWORD}, "auth")
                assert approved["status"] == "reconnected", approved
                client.close()
                keeper = enter(connect(TLSClient))
                keeper.send("quit")
                keeper.expect("ACCOUNT MENU", timeout=45)
                client = connect()
                journey.create_character(client, existing_account=True, account=APPROVED, character="Prepsecond")
                client.send("save")
                client.expect("Save complete for Prepsecond.")
                evidence["approved_creation"] = "new character, starter kit, game entry and save while closed"
                stop()
                assert time.time() < deadline, "closed checks exhausted the launch deadline"
                boot()
                login(connect(), PUBLIC)
                drained(clients[-1])
                keeper = enter(connect())
                command(keeper, "score")
                evidence["restart"] = "same armed configuration stays closed; approved existing-character load and TLS/WS reconnect succeed"
                running_pid = process.pid
                print("PASS: restart retained the gate; waiting for its real UTC deadline", flush=True)
                while time.time() < deadline:
                    assert process.poll() is None
                    time.sleep(.2)
                # Same process, ordinary public login and new-character persistence/gameplay.
                public = enter(connect(), PUBLIC, GUEST)
                command(public, "score")
                public.send("quit")
                public.expect("ACCOUNT MENU", timeout=45)
                public.close()
                public = enter(connect(TLSClient), PUBLIC, GUEST)
                public.send("quit")
                public.expect("ACCOUNT MENU", timeout=45)
                public.close()
                client = websocket()
                public_auth = client.command("login", {"account": PUBLIC, "password": journey.PASSWORD}, "auth")
                assert public_auth["status"] == "success", public_auth
                client.command("enter", {"character": GUEST}, "gmcp")
                client = connect()
                journey.create_character(client, account="Afterlaunch", character="Launchfresh",
                                         email="afterlaunch@example.invalid")
                command(client, "score")
                client.send("save")
                client.expect("Save complete for Launchfresh.")
                assert process.pid == running_pid and process.poll() is None
                evidence.update(status="passed", opening="public Telnet/TLS/WS login/entry; registration, creation, starter kit, gameplay and save without reboot")
                print("PASS: deadline opened ordinary public admission/creation/gameplay without reboot", flush=True)
            except Exception as error:
                evidence.update(status="failed", failure=str(error))
                raise
            finally:
                stop()
                (output_root / (backend + ".log")).write_bytes(log.read_bytes())
                (output_root / (backend + "-runtime.log")).write_text(journey.runtime_logs(runtime))
                (output_root / (backend + ".json")).write_text(json.dumps(evidence, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", type=Path, required=True)
    parser.add_argument("--backend", choices=("mariadb", "flatfile"), required=True)
    args = parser.parse_args()
    run(args.server.resolve(strict=True), args.backend)
