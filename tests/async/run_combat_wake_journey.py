#!/usr/bin/env python3
"""Real Telnet sleeper/witness journey in a disposable flat-file world.

Usage: python3 tests/async/run_combat_wake_journey.py /absolute/flatfile/server
"""

from pathlib import Path
import re
import subprocess
import sys
import tempfile

import test_flatfile_combat_journey as journey
from run_divine_refusal_journey import drain
from run_item_pilot_journey import Server
from run_paladin_balance_journey import command, hp


def run(binary):
    subprocess.run([
        sys.executable, "tests/async/test_flatfile_player_repository.py",
        "--build-inspector", str(journey.INSPECTOR),
    ], cwd=journey.ROOT, check=True)
    with tempfile.TemporaryDirectory(prefix="combat-wake-", dir=journey.ROOT / "bin/tests") as temporary:
        root = Path(temporary)
        runtime, state = root / "runtime", root / "state"
        runtime.mkdir()
        state.mkdir(mode=0o700)
        (state / "domains").mkdir(mode=0o700)
        (runtime / "logs/log").mkdir(parents=True)
        journey.make_fixture(runtime)
        journey.generate_certificate(runtime)
        zone = runtime / "areas_mini/mini.zon"
        zone.write_text(re.sub(r"^[MGE] .*\n", "", zone.read_text(), flags=re.M))
        # The existing Server helper boots in area-debugger mode. Supply its
        # generated world files privately rather than using the checkout's world.
        (runtime / "areas").unlink()
        (runtime / "areas").mkdir()
        generated = {"world.wld", "world.mob", "world.obj", "world.zon", "world.trg",
                     "world.shp", "world.qst", "world.tab", "world.weather"}
        for path in (journey.ROOT / "areas").iterdir():
            if path.name not in generated:
                (runtime / "areas" / path.name).symlink_to(path, target_is_directory=path.is_dir())
        for suffix in ("wld", "mob", "obj", "zon", "shp", "qst", "tab", "weather"):
            path = runtime / f"areas_mini/mini.{suffix}"
            (runtime / f"areas/world.{suffix}").write_text(path.read_text() if path.exists() else "$~\n")
        (runtime / "areas/world.trg").write_text("#~\n")
        subprocess.run([str(journey.INSPECTOR), str(state), "seed-combat"], check=True)
        server = Server(binary, runtime, state, "combat-wake")
        clients = []
        try:
            server.start()
            staff = server.client = journey.MudClient(server.port)
            journey.create_character(staff)
            staff.send("save")
            staff.expect(f"Saving {journey.CHARACTER}.")
            staff.send("quit")
            staff.expect("ACCOUNT MENU")
            server.stop()
            journey.make_overlord(state, journey.CHARACTER)
            server.start()
            staff = server.client = journey.reconnect_character(server.port)
            command(staff, "vis 0")
            command(staff, "toggle page off")
            command(staff, f"setbit char {journey.CHARACTER} hitrol 100")
            for index, name in enumerate(("Napsleeper", "Napwitness"), 2):
                client = journey.MudClient(server.port, source_host=f"127.0.0.{index}")
                clients.append(client)
                journey.create_character(client, account=name, character=name,
                                         email=f"{name.lower()}@example.invalid")
                command(client, "toggle boon")
                command(staff, f"setbit char {name} basehit 10000")
                command(staff, f"setbit char {name} hit 10000")
            sleeper, witness = clients
            print("Disposable caster, sleeper and witness ready", flush=True)
            for magical in (False, True):
                command(staff, f"tranquilize {journey.CHARACTER}")
                command(sleeper, "stand")
                command(sleeper, "recline")
                if magical:
                    # The real spell can be saved against. Require its room
                    # announcement before testing damage-driven wake.
                    for _ in range(10):
                        command(staff, "cast 'sleep' Napsleeper")
                        if "goes to sleep" in drain(witness, .2):
                            break
                    else:
                        raise AssertionError("sleep spell never landed")
                else:
                    sleep_text = command(sleeper, "sleep")
                    assert "You drift off to sleep." in sleep_text, sleep_text
                position = command(staff, "stat char Napsleeper")
                assert re.search(r"Position:.*Sleeping", position), position
                before, _ = hp(staff, "Napsleeper")
                drain(sleeper, .1)
                drain(witness, .1)
                # Player spell dispatch has its own earlier wake path. A melee
                # hit reaches raw_damage while the victim is still sleeping.
                staff.send("murder Napsleeper")
                victim_text = sleeper.expect("You are rudely awakened!", timeout=10) + drain(sleeper, .5)
                witness_text = drain(witness, .2)
                command(staff, f"tranquilize {journey.CHARACTER}")
                after, _ = hp(staff, "Napsleeper")
                print("Victim:", victim_text, "Witness:", witness_text, flush=True)
                assert 0 < after < before, (before, after, victim_text)
                assert victim_text.count("You are rudely awakened!") == 1, victim_text
                assert "You wake up." not in victim_text, victim_text
                assert witness_text.count("Napsleeper has a RUDE awakening!") == 1, witness_text
                assert "The Regression Arena" in command(sleeper, "look")
                assert "You are already awake" in command(sleeper, "wake")
                print(f"PASS: {'SPELL_SLEEP' if magical else 'ordinary sleep'}: "
                      f"HP {before}->{after}; victim one wake; witness one announcement; can act", flush=True)
        finally:
            for client in clients:
                client.close()
            server.stop()


if __name__ == "__main__":
    run(Path(sys.argv[1]).resolve())
