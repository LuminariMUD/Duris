#!/usr/bin/env python3
"""Real-server Assassin command, weapon delivery and victim routing regression.

Reuses the verified flat-file build and combat journey isolation. Synthetic
high-HP players make this reachability proof, independent of the balance audit.
No checkout .env, shared server, player data or database is used.
"""

from pathlib import Path
import os
import re
import signal
import subprocess
import tempfile
import time

import test_flatfile_combat_journey as journey
from test_flight_network_journey import command

ROOT = journey.ROOT
ACTORS = (("Venomwarden", "Venomstaff"), ("Shadeblade", "Venomrogue"),
          ("Venomtarget", "Venomguard"))
NOTICE = "poison from your attacker's blade enters your bloodstream!"


def fixture(runtime):
    journey.make_fixture(runtime)
    journey.generate_certificate(runtime)
    zone = runtime / "areas_mini/mini.zon"
    zone.write_text(re.sub(r"^[MG] .*\n", "", zone.read_text(), flags=re.M))
    objects = runtime / "areas_mini/mini.obj"
    additions = """#22810
journeydagger dagger~
a journey dagger~
A small journey dagger rests here.~
~
5 11 2 3 7 0 0 8193 0 0 0
2 1 4 11 0 0 0 0
2 100 100
#22811
journeyvenom vial~
a journey venom vial~
A journey venom vial rests here.~
~
17 7 1 2 7 0 0 16385 0 0 0
200 200 27 1 0 0 0 0
200 0 100
"""
    objects.write_text(objects.read_text().replace("$~", additions + "$~"))


def run(binary, build):
    fixture_binary = build / "assassin-fixture"
    subprocess.run(["g++", "-std=c++20", "-Isrc", "tests/async/assassin_journey_fixture.cpp",
                    "src/player/player_snapshot_codec.c", "src/flatfile/flatfile_player_snapshot_file.c",
                    "src/flatfile/flatfile_store.c", "-lcrypto", "-o", str(fixture_binary)],
                   cwd=ROOT, check=True)
    subprocess.run(["python3", "tests/async/test_flatfile_player_repository.py",
                    "--build-inspector", str(journey.INSPECTOR)], cwd=ROOT, check=True, timeout=180)
    with tempfile.TemporaryDirectory(prefix="assassin-combat-", dir=ROOT / "bin/tests") as temporary:
        runtime = Path(temporary)
        state = runtime / "state"
        state.mkdir(mode=0o700)
        (state / "domains").mkdir(mode=0o700)
        subprocess.run([str(journey.INSPECTOR), str(state), "seed-combat"], check=True)
        fixture(runtime)
        (runtime / "logs/log").mkdir(parents=True)
        critical = runtime / "journals/critical"
        critical.mkdir(parents=True, mode=0o700)
        (runtime / "journals/players").mkdir(mode=0o700)
        plain, tls, websocket = journey.available_ports()
        environment = dict(PATH=os.environ.get("PATH", "/usr/bin:/bin"), ENVIRONMENT="local",
                           PERSISTENCE_MODE="flatfile-primary", FLATFILE_STATE_DIR=str(state),
                           CRITICAL_COMMAND_JOURNAL_DIR=str(critical), REDIS="FALSE", CHAOS_MUD="FALSE",
                           LISTEN_ADDRESS="127.0.0.1", DURIS_TLS_PORT=str(tls),
                           DURIS_WEBSOCKET_PORT=str(websocket), DURIS_WEBSOCKET_LISTEN_ADDRESS="127.0.0.1")
        if "LD_LIBRARY_PATH" in os.environ:
            environment["LD_LIBRARY_PATH"] = os.environ["LD_LIBRARY_PATH"]
        process = None
        clients = []
        output_path = runtime / "server.out"
        with output_path.open("w") as output:
            def boot():
                nonlocal process
                offset = output_path.stat().st_size
                process = subprocess.Popen([str(binary), "--minimal", "-s", "-d", str(runtime), str(plain)],
                                           cwd=runtime, env=environment, stdout=output, stderr=subprocess.STDOUT)
                deadline = time.monotonic() + 120
                while "Entering game loop." not in output_path.read_text(errors="replace")[offset:]:
                    assert process.poll() is None and time.monotonic() < deadline, "isolated boot failed"
                    time.sleep(.1)

            def stop():
                for client in clients:
                    client.close()
                clients.clear()
                if process is not None and process.poll() is None:
                    process.send_signal(signal.SIGTERM)
                    process.wait(timeout=30)
                    assert process.returncode == 0, "isolated server shutdown failed"

            try:
                boot()
                for name, account in ACTORS:
                    client = journey.MudClient(plain)
                    clients.append(client)
                    journey.create_character(client, account=account, character=name,
                                             email=name.lower() + "@example.invalid")
                    client.send("save")
                    client.expect("Save complete for " + name + ".")
                stop()
                subprocess.run([str(fixture_binary), str(state)], check=True)
                boot()
                for name, account in ACTORS:
                    client = journey.reconnect_character(plain, expected_room=None, account=account, character=name)
                    clients.append(client)
                    client.expect("Welcome to Duris", timeout=30)
                    client.expect_any(("Pos: standing >", "<>"), timeout=20)
                    command(client, "toggle paging no")
                staff, assassin, victim = clients
                for vnum, keyword in ((22810, "journeydagger"), (22811, "journeyvenom")):
                    created = command(staff, "load obj " + str(vnum))
                    assert "created" in created, created
                    given = command(staff, "give " + keyword + " Shadeblade")
                    assert "Ok." in given, given
                inventory = command(assassin, "inventory")
                assert "journey dagger" in inventory and "journey venom vial" in inventory, inventory
                command(assassin, "remove all")
                wielded = command(assassin, "wield journeydagger")
                assert "You wield" in wielded, wielded
                results = {}
                for attack in ("hit", "backstab"):
                    print("Assassin command journey:", attack, flush=True)
                    successes = 0
                    for attempt in range(96):
                        settled = command(staff, "tranquilize Shadeblade")
                        assert "monotone" in settled, settled
                        command(staff, "restore all")
                        command(assassin, "wake")
                        command(assassin, "stand")
                        applied = command(assassin, "apply journeyvenom journeydagger")
                        assert "now drips" in applied, applied
                        before = len(victim.transcript)
                        command(assassin, attack + " Venomtarget")
                        settled = command(staff, "tranquilize Shadeblade")
                        assert "monotone" in settled, settled
                        command(victim, "score")
                        received = bytes(victim.transcript[before:]).decode(errors="replace")
                        assert received.count(NOTICE) <= 1, received
                        if NOTICE in received:
                            successes += 1
                            break
                    assert successes, attack + " never delivered a new weapon poison"
                    results[attack] = {"attempts": attempt + 1, "new_notices": successes}
                assert NOTICE not in assassin.transcript.decode(errors="replace")
                assert NOTICE not in staff.transcript.decode(errors="replace")
                print("Assassin real-server weapon delivery and victim-only routing:", results, flush=True)
                stop()
            except Exception:
                print(output_path.read_text(errors="replace")[-5000:])
                print(journey.runtime_logs(runtime)[-8000:])
                for client in clients:
                    print(client.transcript.decode(errors="replace")[-5000:])
                raise
            finally:
                stop()


def main():
    (ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="assassin-build-", dir=ROOT / "bin/tests") as temporary:
        build = Path(temporary)
        binary = journey.build_flatfile_server(build)
        run(binary, build)


if __name__ == "__main__":
    main()
