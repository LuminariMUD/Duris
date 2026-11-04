#!/usr/bin/env python3
"""Exercise the spells dispatcher, production definitions/help and pager on isolated authority."""
import argparse
from pathlib import Path
import re
import signal
import shutil
import subprocess
import tempfile
import time

import test_flatfile_combat_journey as journey
from test_flight_network_journey import authority, command

ROOT = journey.ROOT
PLAYER, ACCOUNT = "Spellscholar", "Spellsacct"
GOD, GOD_ACCOUNT = "Spellwarden", "Spellstaff"


def run(binary, backend):
    (ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="spells-journey-", dir=ROOT / "bin/tests") as temporary:
        runtime = Path(temporary)
        journey.make_fixture(runtime)
        shutil.copytree(ROOT / "help", runtime / "help")
        mob = runtime / "areas_mini/mini.mob"
        mob.write_text(mob.read_text().replace("raoul~", "raoul cleric all s~", 1))
        for path, separator in ((runtime / "help/duris_help_parsed.hlp", "#0"),
                                (runtime / "lib/information/help_index", "#")):
            topics = re.split(r"(?m)^" + separator + r"[ \t]*$", path.read_text())
            kept = []
            for topic in topics:
                lines = topic.strip().splitlines()
                title = re.sub(r"\s+\([^)]*\)$", "", lines[0]).strip('"').lower() if lines else ""
                if title == "fire form":
                    continue
                if title == "magic missile":
                    # Index aliases start with Redirect:, while parsed help retains its header.
                    if separator == "#0":
                        continue
                    topic = "\nMagic Missile\nRedirect: Spells journey details\n\n"
                kept.append(topic)
            path.write_text((separator + "\n").join(kept))
        with (runtime / "help/duris_help_parsed.hlp").open("a") as help_file:
            help_file.write("\nSpells journey details\nSpells journey details - Last Edited: 2026-11-02\n"
                            "============================================================\n"
                            "Redirected spell details for the disposable journey.\n\n#0\n")
        journey.generate_certificate(runtime)
        (runtime / "logs/log").mkdir(parents=True)
        critical = runtime / "journals/critical"
        critical.mkdir(parents=True, mode=0o700)
        plain, tls, websocket = journey.available_ports()
        process = None
        clients = []
        output_path = runtime / "server.out"
        with authority(backend, runtime) as (env, sql), output_path.open("w") as output:
            if sql:
                # SQL redirects use the help catalog's redirect category.
                sql("UPDATE pages SET category_id=1 WHERE title='Magic Missile'")
            env.update(CRITICAL_COMMAND_JOURNAL_DIR=str(critical), DURIS_TLS_PORT=str(tls),
                       DURIS_WEBSOCKET_PORT=str(websocket),
                       MAINTENANCE_STATE_FILE=str(runtime / "maintenance.state"))

            def boot():
                start = output_path.stat().st_size
                proc = subprocess.Popen([str(binary), "--minimal", "-d", str(runtime), str(plain)],
                                        cwd=runtime, env=env, stdout=output, stderr=subprocess.STDOUT)
                deadline = time.monotonic() + 120
                while b"Entering game loop." not in output_path.read_bytes()[start:]:
                    assert proc.poll() is None and time.monotonic() < deadline, "boot failed"
                    time.sleep(.1)
                return proc

            def stop():
                for client in clients:
                    client.close()
                clients.clear()
                process.send_signal(signal.SIGTERM)
                process.wait(timeout=60)
                assert process.returncode == 0

            def login(name, account):
                client = journey.reconnect_character(plain, expected_room=None, account=account, character=name)
                clients.append(client)
                client.expect("Welcome to Duris", timeout=60)
                client.expect_any(("Pos: standing >", "<>"), timeout=20)
                command(client, "toggle paging no")
                return client

            try:
                process = boot()
                for name, account in ((PLAYER, ACCOUNT), (GOD, GOD_ACCOUNT)):
                    client = journey.MudClient(plain)
                    clients.append(client)
                    journey.create_character(client, account=account, character=name,
                                             email=name.lower() + "@example.invalid",
                                             class_name="j" if name == PLAYER else "w")
                    client.send("save")
                    client.expect("Save complete for " + name + ".", timeout=30)
                stop()
                if sql:
                    sql("UPDATE player_data SET level=62,highest_level=62 WHERE name='" + GOD + "'")
                else:
                    journey.make_overlord(Path(env["FLATFILE_STATE_DIR"]), GOD)
                process = boot()
                god = login(GOD, GOD_ACCOUNT)
                player = login(PLAYER, ACCOUNT)
                raw_start = len(player.raw_transcript)
                own = command(player, "spells")
                raw_own = player.raw_transcript[raw_start:]
                header = f">====[ {PLAYER} | Conjurer | Max Circle 1 ]====<"
                footer = "See: spells <class or specialization> | spells info <spell name>"
                own_lines = own.splitlines()
                assert header in own_lines and own_lines[own_lines.index(header) + 2] == "1st CIRCLE:"
                assert footer in own_lines and "magic missile [in spellbook]" in own_lines
                assert "12th CIRCLE:" in own_lines
                assert "(circle accessible)" not in own and "(future circle)" not in own
                assert b"\x1b[0;1;30mburning hands" in raw_own
                assert b"\x1b[0;1;37mspells <class or specialization>" in raw_own
                assert b"\x1b[0;1;37mspells info <spell name>" in raw_own
                staff = command(god, "spells")
                assert f">====[ {GOD} | Warrior | Max Circle 12 ]====<" in staff
                assert "No eligible spells" in staff
                assert "BASE-CLASS CIRCLE REFERENCE" not in staff
                inspected = command(god, "spells " + PLAYER)
                assert header in inspected and footer in inspected
                assert header in command(god, "spells target " + PLAYER)
                assert "staff-only" in command(player, "spells " + GOD)
                assert "staff-only" in command(player, "spells target " + GOD)
                for text in ("spells all", "spells a", "spells al"):
                    assert "staff only" in command(player, text)
                table = command(god, "spells all")
                assert "BASE-CLASS CIRCLE REFERENCE" in table and "AGGR" in table
                assert "War = Warrior" in table and "Dra = Dragoon" in table
                assert "Eth = Ethermancer" in table and "Ave = Avenger" in table
                assert "No base-class grant; see info for specialization access." in table
                assert "holy intercession" in table and "Undefined" not in table
                names = [name.strip().removesuffix(" AGGR") for name in
                         re.findall(r"^  \[\d+\] (.+)$", table, re.M)]
                assert names and names == sorted(names, key=str.casefold)
                cleric = command(player, "spells cleric")
                assert "Circle 12" in cleric and "heal" in cleric
                assert "No spells assigned" in command(player, "spells warrior")
                fire = command(player, "spells FiRe-MaGuS")
                assert "SPECIALIZATION" in fire and "  * fire form" in fire.splitlines()
                assert "  magic missile" in fire.splitlines()
                assert "fire form" not in command(player, "spells conjurer")
                wizard = command(player, "spells wizard")
                assert "  * anti-magic ray" in wizard.splitlines()
                assert "* indicates spells gained from spec. Spells lost from base class:" in wizard
                assert "solbeeps missile barrage" in wizard.split("Spells lost from base class:", 1)[1]
                assert "(Rogue)" in command(player, "spells assassin")
                assert "(Rogue)" in command(player, "spells thief")
                assert "(Anti-Paladin)" in command(player, "spells dark knight")
                bard = command(player, "spells bard")
                assert "magic missile" in bard and "song of heroism" not in bard and "drums" not in bard
                assert "Matching names:" in command(player, "spells s")
                assert "Provide a known spell name" in command(player, "spells info")
                assert "Provide a known spell name" in command(player, "spells info holy intercession")
                assert "No ordinary class/specialization grants" in command(god, "spells info holy intercession")
                assert "Provide one visible character name" in command(god, "spells target")
                assert "Provide one visible character name" in command(god, "spells target " + PLAYER + " extra")
                assert "No such visible" in command(god, "spells target missingcharacter")
                assert "Usage:" in command(god, "spells all extra")
                deadline = time.monotonic() + 20
                while True:
                    info = command(player, "spells info   FiReBaLl")
                    if "Area of effect" in info:
                        break
                    assert time.monotonic() < deadline, info
                    time.sleep(.1)
                assert "Flame Reaver" in info and "Circle 8 (added)" in info
                lost_info = command(player, "spells info solbeeps missile barrage")
                assert "Wizard" in lost_info and "Unavailable (lost from base class)" in lost_info
                assert "Circle 8 (changed)" in command(player, "spells info haste")
                assert "Your required Circle:" in info and "Current maximum Circle: 1" in info
                assert "Circle requirement: not yet met" in info and "Spellbook" in info
                assert info.index("Class / specialization") < info.index("Your access") < info.index("Helpfile details")
                redirected = command(player, "spells info magic missile")
                assert "Redirected spell details for the disposable journey" in redirected
                missing = command(player, "spells info fire form")
                assert "Circle 10 (added)" in missing and "Your access" in missing
                assert "Help topic not found" in missing
                help_text = command(player, "help spells")
                assert "spells info <spell name>" in help_text and "spells all" in help_text
                assert "spells target <name>" in help_text
                # Navigation back to the existing browsers remains available.
                assert "SKILLS" in command(player, "skills")
                assert "Human" in command(player, "race info human")
                # Real dispatcher and NPC inspection, including class/reserved collisions.
                command(god, "load mob 11")
                assert "BASE CLASS" in command(god, "spells cleric")
                assert "Matching names:" in command(god, "spells s")
                for alias in ("cleric", "all", "s"):
                    assert ">====[ raoul cleric all s | None | Max Circle 1 ]====<" in command(
                        god, f"spells target {alias}")
                command(god, "toggle paging yes")
                god.send("spells all")
                god.expect("BASE-CLASS CIRCLE REFERENCE")
                god.expect("[Return to continue", timeout=20)
                god.send("q")
                god.expect(">", timeout=20)
                command(god, "toggle paging no")
                assert b"\x1b[" in player.raw_transcript
                for name, text in (("info", info), ("all", table), ("personal", own), ("fire", fire)):
                    (ROOT / "bin/tests" / ("spells-" + name + "-" + backend + ".txt")).write_text(text)
                    # Browser-generated sections, excluding authored help and the score fence.
                    generated = text.split("Helpfile details", 1)[0].split("Score information", 1)[0]
                    assert max(map(len, generated.splitlines()), default=0) <= 79, generated
                print("PASS: " + backend + " real staff/mortal dispatcher, personal/spec catalogs, "
                      "live info/help, NPC collisions, permissions, color, width and paging", flush=True)
            except BaseException:
                print(output_path.read_text(errors="replace")[-5000:])
                for client in clients:
                    print(bytes(client.transcript[-5000:]).decode(errors="replace"))
                raise
            finally:
                for client in clients:
                    client.close()
                if process and process.poll() is None:
                    process.send_signal(signal.SIGTERM)
                    process.wait(timeout=60)
                    assert process.returncode == 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("mariadb", "flatfile"), default="flatfile")
    parser.add_argument("--server", type=Path, required=True)
    args = parser.parse_args()
    run(args.server.resolve(), args.backend)
