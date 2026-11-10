#!/usr/bin/env python3
"""Exercise race commands as a mortal on an isolated game, without checkout state."""
import argparse
from pathlib import Path
import signal
import subprocess
import tempfile
import time

import test_mariadb_combat_journey as journey
from test_flight_network_journey import authority, command

ROOT = journey.ROOT


def run(binary, backend):
    with tempfile.TemporaryDirectory(prefix="race-journey-", dir=ROOT / "bin/tests") as temporary:
        runtime = Path(temporary)
        journey.make_fixture(runtime)
        (runtime / "help").symlink_to(ROOT / "help", target_is_directory=True)
        journey.generate_certificate(runtime)
        (runtime / "logs/log").mkdir(parents=True)
        critical = runtime / "journals/critical"
        critical.mkdir(parents=True, mode=0o700)
        plain, tls, websocket = journey.available_ports()
        process = client = None
        output_path = runtime / "server.out"
        with authority(backend, runtime) as (env, _), output_path.open("w") as output:
            env.update(CRITICAL_COMMAND_JOURNAL_DIR=str(critical), DURIS_TLS_PORT=str(tls),
                       DURIS_WEBSOCKET_PORT=str(websocket),
                       MAINTENANCE_STATE_FILE=str(runtime / "maintenance.state"))
            try:
                process = subprocess.Popen([str(binary), "--minimal", "-d", str(runtime), str(plain)],
                                           cwd=runtime, env=env, stdout=output, stderr=subprocess.STDOUT)
                deadline = time.monotonic() + 120
                while b"Entering game loop." not in output_path.read_bytes():
                    assert process.poll() is None and time.monotonic() < deadline, "boot failed"
                    time.sleep(.1)
                client = journey.MudClient(plain)
                journey.create_character(client, account="Raceacct", character="Racewalker",
                                         email="race@example.invalid")
                client.send("toggle paging no")
                client.expect("Paging mode off")
                roster = command(client, "race list")
                good, evil, neutral = map(roster.index, ("GOOD RACES", "EVIL RACES", "NEUTRAL RACES"))
                special = roster.index("DISABLED RACES")
                assert good < roster.index("Human", good) < evil
                assert evil < roster.index("Drow Elf", evil) < neutral
                assert neutral < roster.index("Thri-Kreen", neutral) < special
                assert "Lich" in roster[special:]
                assert "Mountain Dwarf" in roster[good:evil]
                assert "Duergar Dwarf" in roster[evil:neutral]
                assert "Planetbound Illithid" in roster[special:]
                assert "Choose their racewar side during creation" in roster[neutral:special]
                assert "descend:" not in roster and "SPECIAL / LEGACY RACES" not in roster
                panel = roster[roster.index("  /==="):roster.index("  Race info")]
                for line in panel.splitlines():
                    if line:
                        assert len(line) == 72, repr(line)
                assert "THE RACEWAR ROSTER" in command(client, "race")
                assert b"\x1b[" in client.raw_transcript, "terminal color was not rendered"
                # The SQL catalog loads in the background; wait for actual authored lore.
                deadline = time.monotonic() + 20
                while True:
                    human = command(client, "race info human")
                    if "The Human race encompasses" in human:
                        break
                    assert time.monotonic() < deadline, human
                    time.sleep(.1)
                classes = human.split("Valid classes (current character creation rules)", 1)[1]
                classes = classes.split("Racial stat factors", 1)[0]
                assert "Warrior" in classes and "Paladin" in classes
                assert "Anti-Paladin" not in classes and "Dragoon" not in classes
                assert "Warrior     : Swordsman, Guardian, Swashbuckler" in classes
                assert "100% is the baseline" in human
                barbarian = command(client, "race info barbarian")
                assert "Combat speed : 18.250 pulses\r\n" in barbarian
                assert "Spell speed  : 1.220x casting time\r\n" in barbarian
                tiefling = command(client, "race info tiefling")
                assert "Spell speed  : 0.875x casting time\r\n" in tiefling
                illithid = command(client, "race info illithid")
                assert "Spell speed  : 0.025x casting time\r\n" in illithid
                goblin = command(client, "race info goblin")
                assert "Warrior     : Swordsman, Guardian" in goblin
                assert "Rogue       : Assassin, Thief" in goblin
                assert "Summoner    : Controller, Mentalist, Naturalist" in goblin
                assert "Swashbuckler" not in goblin and "Shadow Archer" not in goblin
                assert "Not Used" not in goblin
                thri_kreen = command(client, "race info thri-kreen")
                assert "Warrior     : Swordsman\r\n" in thri_kreen
                assert "Guardian" not in thri_kreen
                assert "Grey Elf" in command(client, "race info GrEy ElF")
                assert "Mountain Dwarf" in command(client, "race info mountaindwarf")
                drow = command(client, "race info drow elf")
                classes = drow.split("Valid classes (current character creation rules)", 1)[1]
                classes = classes.split("Racial stat factors", 1)[0]
                assert "Necromancer" in classes and "    Paladin" not in classes
                innates = command(client, "race innates gnome")
                assert "reflection" in innates and "obtained at level 31" in innates
                assert "Designates passive ability" in innates
                dwarf = command(client, "race innates mountain dwarf")
                assert "*infravision" in dwarf
                assert "Matching races: Githyanki, Githzerai" in command(client, "race info gith")
                assert "No such player race" in command(client, "race info nonexistent")
                assert "provide a race name" in command(client, "race innates")
                assert "Usage: race list" in command(client, "race feats human")
                help_text = command(client, "help race")
                assert "race innates <race name>" in help_text and "valid classes" in help_text
                # Keep a reviewable terminal transcript outside the disposable authority.
                (ROOT / "bin/tests" / ("race-roster-" + backend + ".txt")).write_text(roster)
                (ROOT / "bin/tests" / ("race-info-goblin-" + backend + ".txt")).write_text(goblin)
                print("PASS: " + backend + " mortal command dispatch, faction roster/colors, live lore, "
                      "numeric racial timing, race/class/spec restrictions, future/passive racial innates "
                      "and command help", flush=True)
            except Exception:
                print(output_path.read_text(errors="replace")[-5000:])
                if client:
                    print(bytes(client.transcript[-6000:]).decode(errors="replace"))
                raise
            finally:
                if client:
                    client.close()
                if process and process.poll() is None:
                    process.send_signal(signal.SIGTERM)
                    process.wait(timeout=60)
                    assert process.returncode == 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", choices=("mariadb",), default="mariadb")
    parser.add_argument("--server", type=Path, required=True)
    args = parser.parse_args()
    run(args.server.resolve(), args.backend)
