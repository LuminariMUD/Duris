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
DART_NOTICE = NOTICE.replace("blade", "weapon")


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
#22812
journeydart dart~
a journey dart~
A small journey dart rests here.~
~
7 11 2 3 7 0 256 8193 0 0 0
0 1 4 6 0 0 0 0
2 100 100
"""
    objects.write_text(objects.read_text().replace("$~", additions + "$~"))
    # Minimal worlds omit the seven production recipe outputs.
    heavens = (ROOT / "areas/obj/heavens.obj").read_text()
    recipes = "".join(re.search(rf"(?ms)^#{vnum}\n.*?(?=^#\d+\n)", heavens)[0]
                      for vnum in range(470, 477))
    objects.write_text(objects.read_text().replace("$~", recipes + "$~"))
    # The area's object index is searched by vnum; keep the copied file ordered.
    records = re.findall(r"(?ms)^#(\d+)\n(.*?)(?=^#\d+\n|^\$~)", objects.read_text())
    objects.write_text("".join("#" + number + "\n" + body
                               for number, body in sorted(records, key=lambda row: int(row[0]))) + "$~\n")


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

            def login(name, account):
                client = journey.reconnect_character(plain, expected_room=None, account=account, character=name)
                clients.append(client)
                client.expect("Welcome to Duris", timeout=30)
                client.expect_any(("Pos: standing >", "<>"), timeout=20)
                command(client, "toggle paging no")
                return client

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
                staff, assassin, victim = (login(*actor) for actor in ACTORS)
                for vnum, keyword in ((22810, "journeydagger"), (22811, "journeyvenom"), (22812, "journeydart")):
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
                for attack in ("hit", "backstab", "throw"):
                    keyword = "journeydart" if attack == "throw" else "journeydagger"
                    expected_notice = DART_NOTICE if attack == "throw" else NOTICE
                    print("Assassin command journey:", attack, flush=True)
                    successes = 0
                    for attempt in range(96):
                        settled = command(staff, "tranquilize Shadeblade")
                        assert "monotone" in settled, settled
                        command(staff, "restore all")
                        command(assassin, "wake")
                        command(assassin, "stand")
                        applied = command(assassin, "apply journeyvenom " + keyword)
                        assert "now drips" in applied, applied
                        before = len(victim.transcript)
                        command(assassin, "throw journeydart Venomtarget" if attack == "throw" else attack + " Venomtarget")
                        settled = command(staff, "tranquilize Shadeblade")
                        assert "monotone" in settled, settled
                        command(victim, "score")
                        received = bytes(victim.transcript[before:]).decode(errors="replace")
                        assert received.count(expected_notice) <= 1, received
                        if expected_notice in received and (attack != "backstab" or "stabs you in the back" in received):
                            successes += 1
                            break
                    assert successes, attack + " never delivered a new weapon poison"
                    results[attack] = {"attempts": attempt + 1, "new_notices": successes}
                assert NOTICE not in assassin.transcript.decode(errors="replace")
                assert NOTICE not in staff.transcript.decode(errors="replace")
                assert DART_NOTICE not in assassin.transcript.decode(errors="replace")
                assert DART_NOTICE not in staff.transcript.decode(errors="replace")
                print("Assassin real-server weapon delivery and victim-only routing:", results, flush=True)
                stop()

                # Reconfigure only while stopped; now exercise the level-46 curve.
                subprocess.run([str(fixture_binary), str(state), "46"], check=True)
                boot()
                staff, assassin, victim = (login(*actor) for actor in ACTORS)
                listing = command(assassin, "mixpoison list").lower()
                assert all(name in listing for name in ("lifeleak", "weakness", "moveleak", "slowness", "neurotoxin", "heart toxin")), listing
                assert "madness" not in listing, listing
                prototype_text = (runtime / "areas_mini/mini.obj").read_text()
                for vnum in (102, 806, 808):
                    keyword = re.search(rf"(?m)^#{vnum}\n([^~]+)~", prototype_text)[1].split()[0]
                    assert "created" in command(staff, "load obj " + str(vnum))
                    assert "Ok." in command(staff, "give " + keyword + " Shadeblade")
                mixed = command(assassin, "mixpoison")
                assert "finish mixing" in mixed, mixed
                print("Assassin command journey: level-46 recipes and crafting passed", flush=True)
                before_stats = command(staff, "stat mob Venomtarget")
                baseline_strength = re.search(r"Str:\s*(\d+)\s*\(\s*(\d+)\)", before_stats)
                assert baseline_strength, before_stats
                for attempt in range(96):
                    assert "monotone" in command(staff, "tranquilize Shadeblade")
                    command(staff, "restore all")
                    command(assassin, "wake"); command(assassin, "stand")
                    if attempt % 3 == 0:
                        assert "created" in command(staff, "load obj 471")
                        assert "Ok." in command(staff, "give weakness Shadeblade")
                    applied = command(assassin, "apply weakness journeydagger")
                    assert "now drips" in applied, applied
                    before = len(victim.transcript)
                    command(assassin, "hit Venomtarget")
                    assert "monotone" in command(staff, "tranquilize Shadeblade")
                    command(victim, "score")
                    if NOTICE in bytes(victim.transcript[before:]).decode(errors="replace"):
                        break
                else:
                    raise AssertionError("level-46 Weakness never established")
                victim.send("save"); victim.expect("Save complete for Venomtarget.")
                saved = subprocess.check_output([str(fixture_binary), str(state), "inspect"], text=True)
                weakness = re.search(r"affect 3 1537 (\d+) (-\d+)", saved)
                assert weakness and int(weakness[1]) == 46 and -15 <= int(weakness[2]) <= -5, saved
                after_stats = command(staff, "stat mob Venomtarget")
                weakened_strength = re.search(r"Str:\s*(\d+)\s*\(\s*(\d+)\)", after_stats)
                assert weakened_strength, after_stats
                assert int(weakened_strength[1]) - int(baseline_strength[1]) == int(weakness[2]), after_stats
                # Raise the source, then reload the victim: delivery potency must remain 46.
                advanced = command(staff, "advance Shadeblade 56")
                assert "generous" in advanced, advanced
                assert "created" in command(staff, "load obj 471")
                assert "Ok." in command(staff, "give weakness Shadeblade")
                command(assassin, "wake"); command(assassin, "stand")
                assert "now drips" in command(assassin, "apply weakness journeydagger")
                assassin.send("save"); assassin.expect("Save complete for Shadeblade.")
                assassin.send("quit"); assassin.expect("ACCOUNT MENU", timeout=30)
                assassin.send("0"); assassin.close(); clients.remove(assassin)
                assassin = login(*ACTORS[1])
                assassin.send("save"); assassin.expect("Save complete for Shadeblade.")
                coated = subprocess.check_output([str(fixture_binary), str(state), "inspect"], text=True)
                assert "coating 2 1537" in coated, coated
                victim.send("quit"); victim.expect("ACCOUNT MENU", timeout=30)
                victim.send("0"); victim.close(); clients.remove(victim)
                victim = login(*ACTORS[2])
                victim.send("save"); victim.expect("Save complete for Venomtarget.")
                restored = subprocess.check_output([str(fixture_binary), str(state), "inspect"], text=True)
                assert re.search(r"affect 3 1537 46 " + re.escape(weakness[2]) + r"\b", restored), restored
                print("Assassin Weakness persisted delivery level 46 after source advance and victim reconnect:", weakness[2], flush=True)
                print("Assassin coated weapon retained poison ID 1537 through real save/reconnect", flush=True)
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
