#!/usr/bin/env python3
"""Pet finishing blow, owner salvage message and corpse delivery on isolated state.

Usage: python3 tests/async/run_pet_random_drop_journey.py /absolute/flatfile/server
Probability/attribute parity is covered by test_random_equipment_golden.py.
"""
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import time

import test_flatfile_combat_journey as journey
from test_flight_network_journey import authority, command

ROOT = journey.ROOT


def run(binary):
    subprocess.run(["python3", "tests/async/test_flatfile_player_repository.py",
                    "--build-inspector", str(journey.INSPECTOR)], check=True, cwd=ROOT)
    # Standard TMPDIR lets Windows/WSL checkouts put private authority on a POSIX
    # filesystem, where the store's required 0700 directory permissions apply.
    with tempfile.TemporaryDirectory(prefix="pet-drop-") as tmp:
        runtime = Path(tmp)
        journey.make_fixture(runtime)
        journey.generate_certificate(runtime)
        (runtime / "logs/log").mkdir(parents=True)
        critical = runtime / "journals/critical"
        critical.mkdir(parents=True, mode=0o700)
        zone = runtime / "areas_mini/mini.zon"
        zone.write_text(re.sub(r"^M 0 22800 .*\n", "", zone.read_text(), flags=re.M))
        # Only private runtime settings change: guarantee the equipment roll,
        # suppress materials, and allow the promoted fixture owner's level gap.
        config = runtime / "lib/random_equipment.cfg"
        text = config.read_text()
        for key, value in {"drop.piece.percentage": 100, "drop.equipment.percentage": 0,
                           "drop.maximum.level.gap": 100, "drop.jitter.minimum": 100,
                           "drop.jitter.maximum": 100}.items():
            text, count = re.subn(r"^" + re.escape(key) + r"=.*$", f"{key}={value}", text, flags=re.M)
            assert count == 1
        config.write_text(text)
        plain, tls, websocket = journey.available_ports()
        output_path = runtime / "server.out"
        process = client = None
        with authority("flatfile", runtime) as (env, _), output_path.open("w") as output:
            env.update(CRITICAL_COMMAND_JOURNAL_DIR=str(critical), DURIS_TLS_PORT=str(tls),
                       DURIS_WEBSOCKET_PORT=str(websocket))
            (Path(env["FLATFILE_STATE_DIR"]) / "domains").mkdir(mode=0o700)
            subprocess.run([str(journey.INSPECTOR), env["FLATFILE_STATE_DIR"], "seed-combat"], check=True)

            def boot():
                nonlocal process
                offset = output_path.stat().st_size
                process = subprocess.Popen([str(binary), "--minimal", "-s", "-d", str(runtime), str(plain)],
                                           cwd=runtime, env=env, stdout=output, stderr=subprocess.STDOUT)
                deadline = time.monotonic() + 120
                while b"Entering game loop." not in output_path.read_bytes()[offset:]:
                    assert process.poll() is None and time.monotonic() < deadline, journey.runtime_logs(runtime)
                    time.sleep(.1)

            def stop():
                nonlocal client
                if client:
                    client.close()
                    client = None
                if process and process.poll() is None:
                    process.send_signal(signal.SIGTERM)
                    process.wait(timeout=30)
                    assert process.returncode == 0, journey.runtime_logs(runtime)

            try:
                boot()
                client = journey.MudClient(plain)
                journey.create_character(client)
                client.send("save")
                client.expect("Saving " + journey.CHARACTER + ".")
                command(client, "score")
                client.send("quit")
                client.expect("ACCOUNT MENU", timeout=30)
                stop()
                journey.make_overlord(Path(env["FLATFILE_STATE_DIR"]), journey.CHARACTER)
                boot()
                client = journey.reconnect_character(plain)
                command(client, "toggle paging no")
                command(client, "givepet " + journey.CHARACTER + " 22800")
                assert "regression executioner" in command(client, "look")
                for attempt in range(8):
                    start = len(client.transcript)
                    client.send("order executioner kill raoul")
                    client.expect("is dead! R.I.P.", timeout=30)
                    command(client, "look in corpse")
                    feedback = bytes(client.transcript[start:]).decode(errors="replace")
                    salvage = "It appears you were able to salvage a piece of equipment"
                    if salvage in feedback:
                        assert feedback.count(salvage) == 1, feedback
                        loot = command(client, "get random corpse")
                        assert "You get" in loot, loot
                        item = re.search(r"You get (.+?) from ", loot)
                        assert item, loot
                        assert "You get" not in command(client, "get random corpse")
                        assert item[1] in command(client, "inventory")
                        break
                    # The unchanged stone-substitution roll may select a stone;
                    # retry a new real fight, rather than bypassing the death path.
                    command(client, "purge corpse")
                    command(client, "load mob 11")
                else:
                    raise AssertionError("no equipment branch observed in eight controlled pet kills")
                print("PASS: linked pet killed NPC; one owner salvage message; one generated item looted from corpse")
            finally:
                if client:
                    (ROOT / "bin/tests/issue812-pet-transcript.txt").write_bytes(client.transcript)
                stop()
                (ROOT / "bin/tests/issue812-pet-server.log").write_text(output_path.read_text(errors="replace"))


if __name__ == "__main__":
    run(Path(sys.argv[1]).resolve())
