#!/usr/bin/env python3
"""Let bots play the full world for a while and fail on any crash or sanitizer report.

    tests/async/with_disposable_mariadb.sh \
        python3 tests/scenarios/soak.py --server bin/server/dms_san --minutes 30 --bots 6

Usually started through `scripts/mudtest soak`. Build the server with scripts/build-san.sh
so memory errors are reported, not just crashes. Each bot is a level-50, high-HP character
that wanders, fights whatever it finds, loots, wears gear, rests and reconnects. A staff
character runs a copyover halfway through. The run fails if the server dies, does not shut
down cleanly, or its output holds a sanitizer or crash report.
"""

from __future__ import annotations

import argparse
import pathlib
import random
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests/async"))
sys.path.insert(0, str(ROOT / "tests/scenarios"))

import test_mariadb_combat_journey as journey  # noqa: E402
from run_scenarios import CRASH_MARKERS, Actor, define, seed  # noqa: E402

CLASSES = ("WARRIOR", "CLERIC", "ROGUE", "MONK", "BARD", "SORCERER", "PALADIN", "RANGER")
DIRECTIONS = ("north", "south", "east", "west", "up", "down")
IDLE = ("look", "score", "inventory", "equipment", "who", "affects", "time", "consider all")
SKIP_WORDS = {"the", "a", "an", "is", "are", "here", "standing", "sitting", "resting",
              "sleeping", "of", "and", "with", "in", "on", "its", "his", "her", "their"}


def room_targets(text: str) -> list[str]:
    """Keyword guesses for whatever stands in the room, from the lines of a `look`."""
    words = []
    for line in text.splitlines():
        if re.search(r"\b(is|are|stands?|sits?|rests?|floats?|lies|hovers?)\b.*here", line):
            words += [w for w in re.findall(r"[a-z]{3,}", line.lower()) if w not in SKIP_WORDS]
    return words


class Bot(threading.Thread):
    def __init__(self, actor: Actor, port: int, deadline: float, pause: threading.Event,
                 errors: list[str]):
        super().__init__(daemon=True)
        self.actor, self.port, self.deadline, self.pause, self.errors = actor, port, deadline, pause, errors
        self.commands = 0
        self.random = random.Random(actor.name)

    def connect(self):
        client = journey.reconnect_character(self.port, expected_room=None,
                                             account=self.actor.account, character=self.actor.name)
        client.expect_any(("Pos: ", "<>"), timeout=60)
        client.send("toggle paging no")
        return client

    def act(self, client, command: str) -> str:
        start = len(client.transcript)
        client.send(command)
        self.commands += 1
        end = time.monotonic() + 0.4
        while time.monotonic() < end:
            client._receive()
        text = bytes(client.transcript[start:]).decode(errors="replace")
        for prompt in ("PRESS RETURN", "Press return", "[Hit Return]"):
            if prompt in text:
                client.send("")
        return text

    def run(self):
        client = None
        try:
            client = self.connect()
            while time.monotonic() < self.deadline:
                if self.pause.is_set():
                    client.close()
                    client = None
                    while self.pause.is_set():
                        time.sleep(1)
                    client = self.connect()
                roll = self.random.random()
                if roll < 0.35:
                    self.act(client, self.random.choice(DIRECTIONS))
                elif roll < 0.60:
                    targets = room_targets(self.act(client, "look"))
                    if targets:
                        self.act(client, "kill " + self.random.choice(targets))
                        for _ in range(self.random.randint(2, 6)):
                            self.act(client, self.random.choice(("kick", "bash", "score", "look")))
                elif roll < 0.70:
                    self.act(client, "get all")
                    self.act(client, "get all corpse")
                    self.act(client, "wear all")
                elif roll < 0.78:
                    self.act(client, self.random.choice(("rest", "sit", "stand", "sleep", "wake", "stand")))
                elif roll < 0.80:
                    self.act(client, "save")
                elif roll < 0.81:
                    client.send("quit")
                    time.sleep(2)
                    client.close()
                    client = self.connect()
                else:
                    self.act(client, self.random.choice(IDLE))
        except Exception as error:  # a dead server shows up here first
            self.errors.append(f"{self.actor.name}: {error!r}")
        finally:
            if client is not None:
                client.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--server", type=pathlib.Path, required=True)
    parser.add_argument("--minutes", type=float, default=20)
    parser.add_argument("--bots", type=int, default=6)
    parser.add_argument("--keep", type=pathlib.Path, help="copy the server output and logs here")
    args = parser.parse_args()
    binary = args.server.resolve()
    (ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)

    actors = {"Soakstaff": Actor("Soakstaff", level=62)}
    for n in range(args.bots):
        name = "Soakbot" + "abcdefghijklmnopqrstuvwxyz"[n]
        actors[name] = Actor(name, classes=define("CLASS_" + CLASSES[n % len(CLASSES)]), level=50)

    with tempfile.TemporaryDirectory(prefix="soak-", dir=ROOT / "bin/tests") as temporary, \
            journey.mariadb_authority() as (authority, sql):
        runtime = pathlib.Path(temporary)
        for directory in ("areas", "areas_mini", "docs", "help"):
            (runtime / directory).symlink_to(ROOT / directory, target_is_directory=True)
        shutil.copytree(ROOT / "lib", runtime / "lib")
        journey.generate_certificate(runtime)
        # Copyover promotes a staged bin/server/dms_new over the running bin/server/dms.
        (runtime / "bin/server").mkdir(parents=True)
        shutil.copy2(binary, runtime / "bin/server/dms_new")
        binary = shutil.copy2(binary, runtime / "bin/server/dms")
        (runtime / "logs/log").mkdir(parents=True)
        critical = runtime / "journals/critical"
        critical.mkdir(parents=True, mode=0o700)
        (runtime / "journals/players").mkdir(mode=0o700)
        plain, tls, websocket = journey.available_ports()
        environment = dict(authority, CRITICAL_COMMAND_JOURNAL_DIR=str(critical),
                           DURIS_TLS_PORT=str(tls), DURIS_WEBSOCKET_PORT=str(websocket),
                           ASAN_OPTIONS="detect_leaks=0:abort_on_error=0",
                           UBSAN_OPTIONS="print_stacktrace=1")
        output_path = runtime / "server.out"
        output = output_path.open("a")
        process = None
        failures: list[str] = []

        def boot():
            nonlocal process
            offset = output_path.stat().st_size
            process = subprocess.Popen([str(binary), "-d", str(runtime), str(plain)], cwd=runtime,
                                       env=environment, stdout=output, stderr=subprocess.STDOUT)
            deadline = time.monotonic() + 900
            while "Entering game loop." not in output_path.read_text(errors="replace")[offset:]:
                if process.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError("full-world server did not boot")
                time.sleep(1)

        def stop():
            if process is not None and process.poll() is None:
                process.send_signal(signal.SIGTERM)
                try:
                    process.wait(timeout=300)
                except subprocess.TimeoutExpired:
                    # Never release the schema or runtime directory under a live server.
                    process.kill()
                    process.wait()
                    failures.append("server ignored SIGTERM for 300s and was killed")
                    return
                if process.returncode != 0:
                    failures.append(f"server exited {process.returncode} on shutdown")

        try:
            boot()
            print("full world booted; creating characters", flush=True)
            for actor in actors.values():
                client = journey.MudClient(plain)
                # Tharnadia, not the sealed Beginner Introduction the helper prefers.
                journey.create_character(client, expected_room=None, account=actor.account,
                                         character=actor.name, email=actor.name.lower() + "@example.invalid",
                                         hometown="T", expected_hometown="Tharnadia")
                client.send("save")
                client.expect("Saving " + actor.name + ".", timeout=60)
                client.close()
            stop()
            seed(sql, actors)
            sql("UPDATE player_data SET base_hit=10000,hit_diff=0 WHERE name LIKE 'Soakbot%'")
            boot()
            print(f"soaking {args.bots} bots for {args.minutes} minutes", flush=True)
            deadline = time.monotonic() + args.minutes * 60
            pause, errors = threading.Event(), []
            bots = [Bot(actor, plain, deadline, pause, errors)
                    for name, actor in actors.items() if name != "Soakstaff"]
            for bot in bots:
                bot.start()
            time.sleep(args.minutes * 30)
            if process.poll() is None:
                pause.set()
                time.sleep(3)
                staff = journey.reconnect_character(plain, expected_room=None,
                                                    account=actors["Soakstaff"].account, character="Soakstaff")
                staff.expect_any(("Pos: ", "<>"), timeout=60)
                offset = output_path.stat().st_size
                staff.send("copyover")
                rebooted = time.monotonic() + 900
                while "Entering game loop." not in output_path.read_text(errors="replace")[offset:]:
                    if process.poll() is not None or time.monotonic() > rebooted:
                        raise RuntimeError("server did not come back from copyover")
                    time.sleep(1)
                staff.close()
                print("copyover done; bots resume", flush=True)
                pause.clear()
            for bot in bots:
                bot.join()
            if process.poll() is not None:
                failures.append(f"server died during the soak (exit {process.returncode})")
            failures += errors
            print(f"bots sent {sum(bot.commands for bot in bots)} commands", flush=True)
            stop()
        except Exception as error:
            failures.append(f"soak aborted: {error!r}")
            stop()
        finally:
            output.close()
            logs = output_path.read_text(errors="replace") + journey.runtime_logs(runtime)
            found = [marker for marker in CRASH_MARKERS if marker in logs]
            if found:
                failures.append(f"server output reports {', '.join(found)}")
            if args.keep:
                args.keep.mkdir(parents=True, exist_ok=True)
                shutil.copy2(output_path, args.keep / "server.out")
                shutil.copytree(runtime / "logs", args.keep / "logs", dirs_exist_ok=True)
        for failure in failures:
            print("FAIL", failure, flush=True)
        print("soak passed" if not failures else f"soak failed ({len(failures)} problem(s))")
        return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
