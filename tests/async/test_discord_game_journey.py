#!/usr/bin/env python3
"""Real petition/ptell, save and copyover journey against an external Node sink.

All accounts, binaries and runtime state are disposable. Never reads .env or
contacts Discord. The bridge checkout supplies scripts/testing/duris-game-sink.js.
"""
import argparse
import json
import os
from pathlib import Path
import re
import select
import shutil
import signal
import socket
import subprocess
import tempfile
import time

import test_flatfile_combat_journey as journey

ROOT = journey.ROOT
PLAYER, STAFF = "Petra", "Eldren"
ACCOUNTS = (("Petitionacct", PLAYER), ("Staffacct", STAFF))


class NodeSink:
    def __init__(self, driver, port):
        self.process = subprocess.Popen(
            ["node", str(driver), str(port)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")})
        self.next_id = 0
        try:
            assert self.read()["ready"]
        except Exception:
            self.process.kill()
            self.process.wait(timeout=10)
            for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
                stream.close()
            raise

    def read(self):
        assert select.select([self.process.stdout], [], [], 10)[0], "Node sink response timed out"
        line = self.process.stdout.readline()
        if not line:
            raise AssertionError(self.process.stderr.read().decode())
        return json.loads(line)

    def rpc(self, action="status", **fields):
        self.next_id += 1
        self.process.stdin.write((json.dumps(dict(id=self.next_id, action=action, **fields)) + "\n").encode())
        self.process.stdin.flush()
        result = self.read()
        assert result["id"] == self.next_id
        return result

    def until(self, predicate):
        deadline = time.monotonic() + 15
        while True:
            status = self.rpc()
            if predicate(status):
                return status
            assert time.monotonic() < deadline, status
            time.sleep(0.02)

    def expect_posts(self, expected):
        status = self.until(lambda value: len(value["posts"]) >= len(expected))
        assert status["posts"] == expected, status
        assert status["messages"] == {"mudToDiscord": len(expected), "discordToMud": 0}
        assert status["dropped"] == {"mudToDiscord": 0, "discordToMud": 0}
        return status

    def close(self):
        try:
            if self.process.poll() is None:
                self.rpc("quit")
                self.process.wait(timeout=10)
            assert self.process.returncode == 0, self.process.stderr.read().decode()
        finally:
            if self.process.poll() is None:
                self.process.kill()
                self.process.wait(timeout=10)
            for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
                stream.close()


def command(client, text, expected):
    client.send(text)
    return client.expect(expected, timeout=30)


def run(binary, driver):
    with tempfile.TemporaryDirectory(prefix="discord-game-", dir=ROOT / "bin/tests") as temporary:
        runtime = Path(temporary)
        state = runtime / "state"
        state.mkdir(mode=0o700)
        (state / "domains").mkdir(mode=0o700)
        subprocess.run([str(journey.INSPECTOR), str(state), "seed-combat"], check=True)
        journey.make_fixture(runtime)
        zone = runtime / "areas_mini/mini.zon"
        zone.write_text(re.sub(r"^[MG] .*\n", "", zone.read_text(), flags=re.M))
        journey.generate_certificate(runtime)
        (runtime / "logs/log").mkdir(parents=True)
        (runtime / "journals/critical").mkdir(parents=True, mode=0o700)
        (runtime / "bin/server").mkdir(parents=True)
        shutil.copy2(binary, runtime / "bin/server/dms")
        plain, tls, websocket = journey.available_ports()
        feed_port, _, _ = journey.available_ports()
        copyover = runtime / "copyover.dat"
        environment = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"), "ENVIRONMENT": "local",
            "PERSISTENCE_MODE": "flatfile-primary", "FLATFILE_STATE_DIR": str(state),
            "CRITICAL_COMMAND_JOURNAL_DIR": str(runtime / "journals/critical"),
            "COPYOVER_STATE_FILE": str(copyover), "LISTEN_ADDRESS": "127.0.0.1",
            "DURIS_TLS_PORT": str(tls), "DURIS_WEBSOCKET_LISTEN_ADDRESS": "127.0.0.1",
            "DURIS_WEBSOCKET_PORT": str(websocket), "REDIS": "FALSE", "CHAOS_MUD": "FALSE",
            "DURIS_DISCORD_ENABLED": "TRUE", "DURIS_DISCORD_PORT": str(feed_port),
        }
        if "LD_LIBRARY_PATH" in os.environ:
            environment["LD_LIBRARY_PATH"] = os.environ["LD_LIBRARY_PATH"]
        output_path = runtime / "server.out"
        process = output = sink = None
        clients, expected = [], []

        def boot():
            nonlocal process, output
            before = output_path.read_text().count("Entering game loop.") if output_path.exists() else 0
            output = output_path.open("a")
            process = subprocess.Popen([str(runtime / "bin/server/dms"), "--minimal", "-s", str(plain)],
                                       cwd=runtime, env=environment, stdout=output, stderr=subprocess.STDOUT)
            deadline = time.monotonic() + 120
            while output_path.read_text(errors="replace").count("Entering game loop.") == before:
                assert process.poll() is None and time.monotonic() < deadline, "game boot failed"
                time.sleep(0.1)

        def shutdown():
            nonlocal output
            process.terminate()
            process.wait(timeout=30)
            assert process.returncode == 0, "ordinary game shutdown failed"
            assert "Normal termination of game." in output_path.read_text(errors="replace")
            output.close()
            output = None

        def save_quit():
            for client, (_, name) in zip(clients, ACCOUNTS):
                command(client, "save", f"Save complete for {name}.")
                command(client, "quit", "ACCOUNT MENU")
                client.close()
            clients.clear()

        def login():
            for index, (account, name) in enumerate(ACCOUNTS, 1):
                client = journey.reconnect_character(plain, account=account, character=name,
                                                      source_host=f"127.0.0.{index}")
                clients.append(client)
                command(client, "toggle echo yes", "You turn Echoing on.")
                command(client, "toggle petition yes", "You can now hear Petition.")
                if name == STAFF:
                    # Normal staff login defaults to wizard invisibility 56.
                    command(client, "vis 0", "You are now visible only to PCs with level > 0.")

        def petition(text, *, exported=True, echo=True, staff_online=True):
            command(clients[0], "petition " + text, text if echo else "Ok.")
            if staff_online:
                # Native staff output retains its existing act() dollar escaping.
                clients[1].expect(text.replace("$", "$$"))
            if exported:
                expected.append(f"{PLAYER}: {text}")
                sink.expect_posts(expected)

        def reply(text, *, exported=True, hidden=False):
            command(clients[1], f"ptell {PLAYER} {text}", text)
            received = clients[0].expect(text)
            assert ("Someone" if hidden else STAFF) + " responds to your petition" in received
            if exported:
                expected.append(f"{'Someone' if hidden else STAFF} -> {PLAYER}: {text}")
                sink.expect_posts(expected)

        try:
            boot()
            sink = NodeSink(driver, feed_port)
            sink.until(lambda value: value["connected"])
            for index, (account, name) in enumerate(ACCOUNTS, 1):
                client = journey.MudClient(plain, source_host=f"127.0.0.{index}")
                clients.append(client)
                journey.create_character(client, account=account, character=name,
                                         email=account.lower() + "@example.invalid")
                command(client, "toggle echo yes", "You turn Echoing on.")
                command(client, "toggle petition yes", "You can now hear Petition.")
                if index == 1:
                    petition("NO-STAFF-ONLINE", staff_online=False)
            save_quit()
            shutdown()
            sink.until(lambda value: not value["connected"])
            journey.make_overlord(state, STAFF)
            boot()
            sink.until(lambda value: value["connected"] and value["connections"] >= 2)
            login()
            petition('GAME-PETITION $n @everyone "quote" \\')
            reply("GAME-REPLY $1 $$n")
            command(clients[1], "vis 61", "You are now visible only to PCs with level > 61.")
            reply("CONCEALED-REPLY", hidden=True)
            command(clients[1], "vis 0", "You are now visible only to PCs with level > 0.")
            command(clients[0], "toggle echo no", "You turn off Echoing.")
            petition("ECHO-OFF-PETITION", echo=False)
            command(clients[0], "toggle echo yes", "You turn Echoing on.")
            command(clients[0], "petition", "Petition what?")
            command(clients[0], "toggle petition no", "You are now deaf to Petition.")
            command(clients[0], "petition REJECTED-PETITION", "You can't petition!")
            command(clients[0], "toggle petition yes", "You can now hear Petition.")
            command(clients[1], "ptell Missing REJECTED-REPLY", "Nobody by that name seems available.")
            command(clients[0], "say PRIVATE-SAY", "PRIVATE-SAY")
            command(clients[0], f"tell {STAFF} PRIVATE-TELL", "PRIVATE-TELL")
            assert sink.rpc("discord", text="INGRESS-SENTINEL")["accepted"] is False
            sink.rpc("forge", text=f"ptell {PLAYER} INGRESS-SENTINEL")
            # Multiple real game turns establish the server stayed responsive
            # while the incoming control/chat bytes were consumed.
            for _ in range(3):
                command(clients[0], "look", "The Regression Arena")
            petition("AFTER-REJECTIONS")
            assert all(b"INGRESS-SENTINEL" not in client.transcript for client in clients)
            assert "INGRESS-SENTINEL" not in journey.runtime_logs(runtime)
            print("Full game: both commands, native feedback, concealment, exclusions and one-way ingress passed", flush=True)

            before = sink.rpc()
            # A staged executable whose interpreter does not exist forces the
            # actual execl failure path after state saving and socket preparation.
            staged = runtime / "bin/server/dms_new"
            staged.write_text("#!/nonexistent-duris-fixture-interpreter\n")
            staged.chmod(0o700)
            process.send_signal(signal.SIGUSR1)
            for client in clients:
                client.expect("Copyover FAILED!", timeout=90)
            assert process.poll() is None and copyover.exists()
            assert "copyover: execl failed:" in journey.runtime_logs(runtime)
            for client, (_, name) in zip(clients, ACCOUNTS):
                command(client, "look", "The Regression Arena")
                command(client, "save", f"Save complete for {name}.")
            petition("AFTER-FAILED-EXEC")
            reply("REPLY-AFTER-FAILED-EXEC")
            after = sink.rpc()
            assert after["connections"] == before["connections"] and after["closes"] == before["closes"]
            print("Full game: failed exec preserved player sockets, saves and the original bridge connection", flush=True)

            shutil.copy2(binary, staged)
            boots = output_path.read_text().count("Entering game loop.")
            process.send_signal(signal.SIGUSR1)
            for client in clients:
                client.expect("Copyover complete!", timeout=120)
            assert process.poll() is None and not copyover.exists()
            # Player recovery announces completion before listener initialization.
            # Wait for the new loop to accept Node and execute player commands.
            sink.until(lambda value: value["connected"] and value["connections"] > after["connections"])
            for client, (_, name) in zip(clients, ACCOUNTS):
                command(client, "look", "The Regression Arena")
                command(client, "save", f"Save complete for {name}.")
            assert output_path.read_text().count("Entering game loop.") == boots + 1
            petition("AFTER-SUCCESSFUL-COPYOVER")
            reply("REPLY-AFTER-SUCCESSFUL-COPYOVER")
            print("Full game: successful exec recovered original player sockets, saves and Node relay", flush=True)

            sink.rpc("stop")
            petition("OFFLINE-PETITION", exported=False)
            reply("OFFLINE-REPLY", exported=False)
            save_quit()
            shutdown()
            environment["DURIS_DISCORD_ENABLED"] = "FALSE"
            boot()
            with socket.socket() as probe:
                assert probe.connect_ex(("127.0.0.1", feed_port)) != 0, "disabled endpoint still listens"
            login()
            petition("DISABLED-PETITION", exported=False)
            reply("DISABLED-REPLY", exported=False)
            save_quit()
            shutdown()
            sink.expect_posts(expected)
            logs = (runtime / "logs/log/petition").read_text(errors="replace")
            for text in ("GAME-REPLY", "OFFLINE-PETITION", "OFFLINE-REPLY", "DISABLED-PETITION", "DISABLED-REPLY"):
                assert logs.count(text) == 1, "native audit entry missing or duplicated: " + text
            assert "REJECTED-PETITION" not in logs and "REJECTED-REPLY" not in logs
            assert "FATAL:" not in output_path.read_text(errors="replace")
            print("Full game: disconnect/disable rollback, save/reload and ordinary shutdown passed", flush=True)
        except Exception:
            print(output_path.read_text(errors="replace")[-8000:])
            print(journey.runtime_logs(runtime))
            for client in clients:
                print(client.transcript.decode(errors="replace")[-4000:])
            raise
        finally:
            for client in clients:
                client.close()
            try:
                if sink:
                    sink.close()
            finally:
                if process and process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=30)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=10)
                if output:
                    output.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--node-driver", required=True, type=Path)
    parser.add_argument("--server", type=Path, help="previously built flat-file server; otherwise build current source")
    args = parser.parse_args()
    driver = args.node_driver.resolve()
    if not driver.is_file():
        parser.error(f"Node sink driver not found: {driver}")
    (ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
    subprocess.run(["python3", "tests/async/test_flatfile_player_repository.py", "--build-inspector",
                    str(journey.INSPECTOR)], cwd=ROOT, check=True, timeout=180)
    with tempfile.TemporaryDirectory(prefix="discord-game-build-", dir=ROOT / "bin/tests") as build:
        binary = args.server.resolve() if args.server else journey.build_flatfile_server(Path(build))
        run(binary, driver)
