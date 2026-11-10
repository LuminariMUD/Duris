#!/usr/bin/env python3

"""Exercise durable player and world-item recovery across a full-world restart.

The first real server process creates an account and character, transactionally
drops an identifiable starter item, saves, and exits.  A fresh process then
boots against the same disposable MariaDB schema, restores the floor item, reloads
the player, and moves the item back to the player. This also keeps the corpse,
saved-item, and shopkeeper boot stages under a real full-world boot rather than
harnesses alone, and requires a sailing path for every leg of every ferry route.

DURIS_FULL_WORLD_ARTIFACT_DIR retains journals, server logs, exit status, and a
redacted monotonic command/response timeline on failure only. Use a private,
untracked destination. DURIS_FULL_WORLD_REPEATS (1..100) repeats fresh fixture
journeys with one server binary. The two DURIS_NEVENT trace switches are forwarded
explicitly; no database or live environment is inherited.
DURIS_FULL_WORLD_CRASH_PHASE=after_ack replaces the first clean logout with SIGKILL
and verifies acknowledged state on restart.
"""

import argparse
import json
import os
from contextlib import contextmanager

import test_mariadb_combat_journey as journey
import pathlib
import shutil
import signal
import socket
import subprocess
import tempfile
import time

from test_flight_network_journey import authority

from test_mariadb_combat_journey import (
    CHARACTER,
    MudClient,
    available_ports,
    create_character,
    reconnect_character,
)


ROOT = pathlib.Path(__file__).resolve().parents[2]


# Optional diagnostic controls; defaults retain the ordinary one-journey gate.
ARTIFACT_ROOT = os.environ.get("DURIS_FULL_WORLD_ARTIFACT_DIR")
CRASH_PHASE = os.environ.get("DURIS_FULL_WORLD_CRASH_PHASE", "")
if CRASH_PHASE not in ("", "after_ack"):
    raise ValueError("DURIS_FULL_WORLD_CRASH_PHASE must be after_ack")
REPEATS = int(os.environ.get("DURIS_FULL_WORLD_REPEATS", "1"))
if not 1 <= REPEATS <= 100:
    raise ValueError("DURIS_FULL_WORLD_REPEATS must be between 1 and 100")
records = []
phase = "build"
attempt = 0
artifact_destination = None
sql = None


def record(event, **fields):
    """Append a monotonic journey event and print non-receive events immediately."""
    entry = dict(monotonic=time.monotonic(), attempt=attempt, phase=phase,
                 event=event, **fields)
    records.append(entry)
    if event != "receive":
        print(json.dumps(entry), flush=True)


class RecordedClient(MudClient):
    def send(self, line):
        """Record a password-redacted command before sending it to the test server."""
        record("send", command=line.replace(journey.PASSWORD, "[REDACTED]"))
        super().send(line)

    def _receive(self):
        """Record newly received transcript bytes with the fixture password redacted."""
        offset = len(self.transcript)
        received = super()._receive()
        if received:
            record("receive", text=self.transcript[offset:].decode(
                "utf-8", errors="replace").replace(journey.PASSWORD, "[REDACTED]"))
        return received

    def expect_disconnect(self, timeout=5):
        """Require the goodbye message and server EOF without sending more input."""
        self.expect("Thank you for playing!", timeout=timeout)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                chunk = self.socket.recv(65536)
            except socket.timeout:
                continue
            if not chunk:
                record("account_disconnected")
                return
        raise AssertionError("account logout did not close the connection after output drained")

    def expect_any(self, needles, timeout=15):
        """Wait for expected output and classify rejection versus observation failures."""
        started = time.monotonic()
        transcript_offset = len(self.transcript)
        try:
            result = super().expect_any(needles, timeout)
        except Exception:
            response = self.transcript[transcript_offset:]
            rejection = any(message in response for message in (
                b"Save failed for", b"your camp is cancelled"))
            record("assertion_failure", expected=needles,
                   classification="server_rejection" if rejection else "observation_deadline_or_disconnect",
                   elapsed=time.monotonic() - started)
            raise
        record("observed", expected=result[0], elapsed=time.monotonic() - started)
        return result


# reconnect_character constructs its client in the helper module too.
MudClient = journey.MudClient = RecordedClient


@contextmanager
def fixture_directory(kind):
    """Yield isolated fixture storage and preserve configured diagnostics only on failure."""
    global artifact_destination
    with tempfile.TemporaryDirectory(prefix=f"duris-flatfile-world-{kind}-") as tmp:
        try:
            yield tmp
        except BaseException:
            if ARTIFACT_ROOT:
                if artifact_destination is None:
                    pathlib.Path(ARTIFACT_ROOT).mkdir(parents=True, exist_ok=True, mode=0o700)
                    artifact_destination = pathlib.Path(tempfile.mkdtemp(
                        prefix=f"attempt-{attempt}-", dir=ARTIFACT_ROOT))
                destination = artifact_destination
                source = pathlib.Path(tmp)
                # Only synthetic diagnostics; no TLS private key.
                for name in ("logs", "journals", "boot-first.out", "boot-restart.out"):
                    path = source / name
                    if path.is_dir():
                        shutil.copytree(path, destination / name, dirs_exist_ok=True)
                    elif path.is_file():
                        shutil.copy2(path, destination / name)
                (destination / "timeline.json").write_text(json.dumps(records, indent=2))
                print(f"Failure artifacts: {destination}", flush=True)
            raise


def require(condition: bool, message: str) -> None:
    """Raise an assertion with the supplied diagnostic when a journey invariant fails."""
    if not condition:
        raise AssertionError(message)


def inspect_authority():
    """Read saved custody and reject missing or multiply owned item identities."""
    snapshot = journey.inspect_authority(sql)
    player = [item["uid"] for item in snapshot["player_items"]]
    room = [item["uid"] for item in snapshot["room_items"]]
    require(len(set(player + room)) == len(player + room), "duplicate item UID ownership")
    require(all(uid > 0 for uid in player + room), "missing durable item UID")
    snapshot["revision"] = int(sql(f"SELECT save_revision FROM player_data WHERE pid={snapshot['pid']}"))
    record("authority_observed", **snapshot)
    return snapshot


def save_durably(client, timeout=15):
    """Save and wait for the writer to land it; a save is written asynchronously."""
    revision = inspect_authority()["revision"]
    client.send("save")
    client.expect(f"Saving {CHARACTER}.", timeout=45)
    deadline = time.monotonic() + timeout
    while True:
        snapshot = inspect_authority()
        if snapshot["revision"] > revision:
            return snapshot
        require(time.monotonic() < deadline, "the save did not reach player_data")
        time.sleep(0.05)


def assert_mace_owner(uid, owner):
    """Require the tracked mace UID to belong exclusively to the expected owner."""
    snapshot = inspect_authority()
    locations = [name for name in ("player_items", "room_items")
                 for item in snapshot[name] if item["uid"] == uid]
    require(locations == [owner], f"mace UID {uid} ownership was {locations}, expected {owner}")
    return snapshot


def crash_server(process):
    """Kill the isolated server and verify the intended crash termination boundary."""
    process.kill()
    process.wait(timeout=10)
    require(process.returncode == -signal.SIGKILL, "intentional crash did not terminate the server")
    record("intentional_crash", boundary=CRASH_PHASE, pid=process.pid, returncode=process.returncode)


def wait_for_boot(process: subprocess.Popen[str], output, output_path: pathlib.Path) -> str:
    """Wait for the full-world game loop and verify required world restore stages ran."""
    deadline = time.monotonic() + 600
    boot_output = ""
    while time.monotonic() < deadline:
        output.flush()
        boot_output = output_path.read_text(errors="replace")
        if "Entering game loop." in boot_output:
            break
        if process.poll() is not None:
            break
        time.sleep(0.1)
    require(
        "Entering game loop." in boot_output,
        "full-world server did not reach the game loop:\n" + boot_output,
    )
    for stage in ("-- Player corpses", "-- Shopkeepers", "Booting Ferries"):
        require(stage in boot_output, f"full-world boot skipped {stage}:\n" + boot_output)
    # Ferry::init() routes every leg of every ferries[] entry at boot and puts a
    # ticket automat at every stop.
    require("no path found!" not in boot_output,
            "a ferry route leg has no sailing path:\n" + boot_output)
    require("can't find ferry ticket automat" not in boot_output,
            "a ferry stop has no ticket automat:\n" + boot_output)
    record("boot_ready", pid=process.pid)
    return boot_output


def stop_server(process: subprocess.Popen[str], output, output_path: pathlib.Path) -> str:
    """Request graceful shutdown and require successful normal termination."""
    process.send_signal(signal.SIGTERM)
    process.wait(timeout=30)
    record("server_exit", pid=process.pid, returncode=process.returncode)
    output.flush()
    server_output = output_path.read_text(errors="replace")
    require(
        process.returncode == 0,
        f"full-world server did not shut down cleanly ({process.returncode}):\n"
        + server_output,
    )
    require(
        "Normal termination of game." in server_output,
        "full-world shutdown did not reach normal termination:\n" + server_output,
    )
    return server_output


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--server", type=pathlib.Path, required=True)
binary = parser.parse_args().server.resolve()
record("configuration", revision=subprocess.check_output(
    ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
    backend="mariadb-primary", compiler=subprocess.check_output(
    ["g++", "--version"], text=True).splitlines()[0],
    cpu_affinity=sorted(os.sched_getaffinity(0)), repeats=REPEATS,
    scheduler="default: 25000 us, no callback limit; catchup +5000 us",
    analytics=os.environ.get("DURIS_NEVENT_ANALYTICS", "0"),
    player_trace=os.environ.get("DURIS_NEVENT_TRACE_PLAYER", "0"))
world = subprocess.run(
    ["make", "world"],
    cwd=ROOT,
    text=True,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    timeout=600,
)
require(world.returncode == 0, "full-world data generation failed:\n" + world.stdout[-8000:])

for attempt in range(1, REPEATS + 1):
    with fixture_directory("run") as run_tmp:
        run_root = pathlib.Path(run_tmp)
        (run_root / "logs/log").mkdir(parents=True)
        (run_root / "logs/log/.gitignore").write_text("*\n!.gitignore\n")
        for directory in ("areas", "areas_mini", "docs", "help"):
            (run_root / directory).symlink_to(ROOT / directory, target_is_directory=True)
        runtime_lib = run_root / "lib"
        shutil.copytree(ROOT / "lib", runtime_lib)
        properties_path = runtime_lib / "duris.properties"
        properties = properties_path.read_text()
        require("camp.timer=9.000" in properties, "camp timer fixture changed")
        properties_path.write_text(properties.replace("camp.timer=9.000", "camp.timer=2.000"))
        journey.generate_certificate(run_root)
        critical_journal = run_root / "journals/critical"
        critical_journal.mkdir(parents=True, mode=0o700)
        with authority("mariadb", run_root) as (environment, sql):
            port, tls_port, websocket_port = available_ports()
            output_path = run_root / "boot-first.out"
            environment.update(CRITICAL_COMMAND_JOURNAL_DIR=str(critical_journal),
                               DURIS_TLS_PORT=str(tls_port), DURIS_WEBSOCKET_PORT=str(websocket_port))
            for switch in ("DURIS_NEVENT_ANALYTICS", "DURIS_NEVENT_TRACE_PLAYER"):
                if switch in os.environ:
                    environment[switch] = os.environ[switch]
            with output_path.open("w", encoding="utf-8") as output:
                process = subprocess.Popen(
                    [str(binary), "-d", str(run_root), str(port)],
                    cwd=run_root,
                    env=environment,
                    text=True,
                    stdout=output,
                    stderr=subprocess.STDOUT,
                )
                client = None
                try:
                    phase = "first_boot" if output_path.name == "boot-first.out" else "second_boot"
                    record("phase_start")
                    wait_for_boot(process, output, output_path)
                    # Every shop's rates are within the loader's bounds, so a boot
                    # adjusts none and logs no "Old buy/sell" line.
                    debug_log = (run_root / "logs/log/debug").read_text(errors="replace")
                    require("Old buy/sell" not in debug_log,
                            "the boot adjusted a shop's rates:\n" + "\n".join(
                                line for line in debug_log.splitlines()
                                if "Old buy/sell" in line))
                    phase = "first_boot:character_creation"
                    client = MudClient(port)
                    create_character(client, expected_room=None)
                    before_drop = save_durably(client)
                    # Memory is the authority: the drop moves the mace at once, and
                    # the next save simply no longer holds it.
                    client.send("drop mace")
                    client.expect("You drop a small wooden mace", timeout=20)
                    require(inspect_authority()["player_items"] ==
                            before_drop["player_items"], "a drop wrote to the ownership catalog")
                    client.send("look")
                    client.expect("A gnoby piece of wood, perhaps a small mace, lies here.")
                    after_drop = save_durably(client)
                    removed = set(before_drop["snapshot_uids"]) - set(after_drop["snapshot_uids"])
                    require(len(removed) == 1, f"drop changed unexpected UIDs: {removed}")
                    mace_uid = removed.pop()
                    # The starter kit fills a new character's hands; free them first.
                    client.send("drop all")
                    client.expect("You drop a steel long sword", timeout=45)
                    client.send("get mace")
                    client.expect("You get a small wooden mace", timeout=20)
                    phase = output_path.stem + ":manual_save"
                    acknowledged = save_durably(client)
                    if CRASH_PHASE:
                        crash_server(process)
                        require(inspect_authority()["revision"] == acknowledged["revision"],
                                "the acknowledged save was not durable")
                    if not CRASH_PHASE:
                        phase = output_path.stem + ":terminal_save"
                        client.send("quit")
                        client.expect("ACCOUNT MENU", timeout=30)
                        client.send("0")
                        client.expect_disconnect()
                        client.close()
                        client = None
                        phase = output_path.stem + ":shutdown"
                        stop_server(process, output, output_path)
                        assert_mace_owner(mace_uid, "player_items")
                finally:
                    if client is not None:
                        client.close()
                    if process.poll() is None:
                        process.terminate()
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait(timeout=5)
                    record("process_cleanup", pid=process.pid, returncode=process.returncode)

            port, tls_port, websocket_port = available_ports()
            environment["DURIS_TLS_PORT"] = str(tls_port)
            environment["DURIS_WEBSOCKET_PORT"] = str(websocket_port)
            output_path = run_root / "boot-restart.out"
            with output_path.open("w", encoding="utf-8") as output:
                process = subprocess.Popen(
                    [str(binary), "-d", str(run_root), str(port)],
                    cwd=run_root,
                    env=environment,
                    text=True,
                    stdout=output,
                    stderr=subprocess.STDOUT,
                )
                client = None
                try:
                    phase = "first_boot" if output_path.name == "boot-first.out" else "second_boot"
                    record("phase_start")
                    wait_for_boot(process, output, output_path)
                    recovered = assert_mace_owner(mace_uid, "player_items")
                    require(mace_uid in recovered["snapshot_uids"], "the saved mace did not survive the restart")
                    require(recovered["revision"] >= acknowledged["revision"],
                            "the restart lost the acknowledged save")
                    phase = "restart_recovery"
                    client = reconnect_character(
                        port,
                        return_message=("Restoring items and pets from crash save info..." if CRASH_PHASE else
                                        "You break camp and get ready to move on"),
                        expected_room=None,
                    )
                    client.send("inventory")
                    client.expect("a small wooden mace", timeout=10)
                    client.send("drop all")
                    client.expect("You drop a small wooden mace", timeout=45)
                    client.send("get mace")
                    client.expect("You get a small wooden mace", timeout=20)
                    assert_mace_owner(mace_uid, "player_items")
                    client.send("inventory")
                    client.expect("a small wooden mace", timeout=10)
                    phase = output_path.stem + ":manual_save"
                    client.send("save")
                    client.expect(f"Saving {CHARACTER}.", timeout=45)
                    phase = output_path.stem + ":terminal_save"
                    client.send("quit")
                    client.expect("ACCOUNT MENU", timeout=30)
                    client.send("0")
                    client.expect_disconnect()
                    client.close()
                    client = None
                    phase = output_path.stem + ":shutdown"
                    stop_server(process, output, output_path)
                finally:
                    if client is not None:
                        client.close()
                    if process.poll() is None:
                        process.terminate()
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait(timeout=5)
                    record("process_cleanup", pid=process.pid, returncode=process.returncode)

            assert_mace_owner(mace_uid, "player_items")

print("full-world player and floor-item process-restart journey passed")
