#!/usr/bin/env python3
"""Queued gameplay commands must not be read as account-menu input after death."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

import test_flatfile_combat_journey as journey
from run_battleprep_journey import configure
from run_item_pilot_journey import Server


def run(binary, output):
    output.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix="death-input-", dir=journey.ROOT / "bin/tests") as directory:
        root = Path(directory)
        runtime, state = root / "runtime", root / "state"
        runtime.mkdir(); state.mkdir(mode=0o700); (state / "domains").mkdir(mode=0o700)
        configure(runtime)
        for path in (runtime / "areas/world.zon", runtime / "areas_mini/mini.zon"):
            path.write_text(path.read_text().replace("\nS\n",
                "\nM 0 22800 1 22800 100 0 0 0 * native death input boundary\nS\n"))
        subprocess.run([str(journey.INSPECTOR), str(state), "seed-combat"], check=True)
        server = Server(binary, runtime, state, "death-input")
        client = None
        gameplay_start = 0
        try:
            server.start()
            client = journey.MudClient(server.port)
            journey.create_character(client)
            gameplay_start = len(client.transcript)
            # Ordinary benign type-ahead behind an attack. A fumbled opening can
            # leave combat idle, so retry only the fixture's native fumble case.
            for attempt in range(6):
                client.socket.sendall(("hit executioner\n" + "look\n" * 16).encode())
                result, _ = client.expect_any(("Your wounds claim you at last",
                    "You stumble, but recover in time!", "You stumble in your attack, and jab at",
                    "You stumble in your attack, and hit yourself!"), timeout=45)
                if result == "Your wounds claim you at last":
                    break
            else:
                raise AssertionError("Fixture player never entered native death")
            client.expect("ACCOUNT MENU")
            client.expect("Please select an option")
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                client._receive()
            transcript = client.transcript[gameplay_start:].decode("utf-8", errors="replace")
            menu = transcript.split("ACCOUNT MENU", 1)[1]
            assert "Invalid Selection" not in menu, "queued gameplay reached the account menu"
            client.send("1")
            client.expect(journey.CHARACTER)
            (output / "result.json").write_text(json.dumps({"result": "passed",
                "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
                "verified": ["real combat death", "queued gameplay discarded",
                             "death and account menu output retained", "fresh menu selection works"]}, indent=2))
            print("native death input boundary passed", flush=True)
        finally:
            if client:
                (output / "gameplay.txt").write_bytes(client.transcript[gameplay_start:])
                client.close()
            server.stop()
            if server.output_path.exists():
                (output / "server.out").write_bytes(server.output_path.read_bytes())
            shutil.copytree(runtime / "logs", output / "server-logs", dirs_exist_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    (journey.ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
    if not journey.INSPECTOR.exists():
        subprocess.run(["python3", "tests/async/test_flatfile_player_repository.py", "--build-inspector",
                        str(journey.INSPECTOR)], cwd=journey.ROOT, check=True, timeout=180)
    run(args.binary.resolve(), args.output.resolve())
