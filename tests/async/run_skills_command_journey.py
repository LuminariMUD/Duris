#!/usr/bin/env python3
"""Exercise the skills dispatcher, production definitions/help and pager on isolated authority."""
import argparse
from pathlib import Path
import re
import signal
import subprocess
import tempfile
import time

import test_flatfile_combat_journey as journey
from test_flight_network_journey import authority, command

ROOT = journey.ROOT
PLAYER, ACCOUNT = "Skillscholar", "Skillsacct"
GOD, GOD_ACCOUNT = "Skillwarden", "Skillstaff"


def run(binary, backend):
    (ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="skills-journey-", dir=ROOT / "bin/tests") as temporary:
        runtime = Path(temporary)
        journey.make_fixture(runtime)
        (runtime / "help").symlink_to(ROOT / "help", target_is_directory=True)
        journey.generate_certificate(runtime)
        (runtime / "logs/log").mkdir(parents=True)
        critical = runtime / "journals/critical"
        critical.mkdir(parents=True, mode=0o700)
        plain, tls, websocket = journey.available_ports()
        process = None
        clients = []
        output_path = runtime / "server.out"
        with authority(backend, runtime) as (env, sql), output_path.open("w") as output:
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
                                             email=name.lower() + "@example.invalid")
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
                own = command(player, "skills")
                assert PLAYER + " : SKILLS" in own and "bash" in own
                assert "obtained at level 41" in own
                staff = command(god, "skills")
                assert GOD + " : SKILLS" in staff and "[taught " in staff
                assert PLAYER + " : SKILLS" in command(god, "skills " + PLAYER)
                assert PLAYER + " : SKILLS" in command(god, "skills target " + PLAYER)
                assert "staff-only" in command(player, "skills " + GOD)
                assert "staff-only" in command(player, "skills target " + GOD)
                for text in ("skills levels", "skills lev"):
                    assert "staff only" in command(player, text)
                table = command(god, "skills levels")
                assert "BASE CLASS SKILL LEVELS" in table
                assert "War = Warrior" in table and "Dra = Dragoon" in table
                assert "Eth = Ethermancer" in table and "Ave = Avenger" in table
                warrior = command(player, "skills warrior")
                swordsman = command(player, "skills swordsman")
                guardian = command(player, "skills GuArDiAn")
                swash = command(player, "skills swashbuckler")
                assert re.search(r"\b1\s+100\s+bash\b", warrior), warrior
                assert re.search(r"\b1\s+70\s+bash\b", swordsman), swordsman
                assert re.search(r"\b30\s+100\s+guard\b", guardian), guardian
                assert "Skills lost from base class:" in swash
                assert "bash" in swash.split("Skills lost from base class:", 1)[1]
                assert "(Rogue)" in command(player, "skills assassin")
                assert "(Rogue)" in command(player, "skills thief")
                assert "(Anti-Paladin)" in command(player, "skills dark knight")
                bard = command(player, "skills bard")
                assert "drums" in bard and "song of heroism" in bard
                assert "Matching names:" in command(player, "skills s")
                assert "Provide a known skill name" in command(player, "skills info")
                assert "Provide a known skill name" in command(player, "skills info charge cooldown.")
                deadline = time.monotonic() + 20
                while True:
                    info = command(player, "skills info   BAsH")
                    if "bash <victim>" in info:
                        break
                    assert time.monotonic() < deadline, info
                    time.sleep(.1)
                assert "Swordsman" in info and "Swashbuckler" in info and "Unavailable" in info
                assert "Your unlock level: 1  Your cap: 100" in info
                assert "Current rating:" in info and "Learned:" in info and "Taught:" in info
                assert info.index("Your progress") < info.index("Mechanics") < info.index("Helpfile details")
                assert "with your strength and no shield" in info, info
                assert "Your lag on a miss: 8 seconds, or 12 seconds if you fall prone" in info, info
                assert "Target's lag: 8 seconds, or 4 seconds if the target was already down" in info, info
                assert "Mechanics" not in command(player, "skills info parry")
                innate = command(player, "innate info reflection")
                assert "reflection : INNATE INFO" in innate and "Type: Active" in innate, innate
                assert "Not available to your race, class or specialization." in innate, innate
                assert "Uses: 1 before it rests" in innate and "Your lag: 4 seconds" in innate, innate
                assert "Provide a known innate name" in command(player, "innate info nosuchinnate")
                # The converted bash still plays through its real handler.
                command(god, "load mob 11")
                bashed = command(god, "bash raoul")
                assert "to the ground" in bashed, bashed
                assert "Epic skill" in command(player, "skills info anatomy")
                assert "Instrument" in command(player, "skills info drums")
                assert "Bard song" in command(player, "skills info song of heroism")
                assert "nothing to reset" not in command(god, "skills reset " + PLAYER)
                help_text = command(player, "help skills")
                assert "skills info <skill name>" in help_text and "skills levels" in help_text
                assert "skills target <name>" in help_text
                # The real command-output pager handles long browser output and colors.
                command(god, "toggle paging yes")
                god.send("skills levels")
                god.expect("BASE CLASS SKILL LEVELS")
                god.expect("[Return to continue", timeout=20)
                god.send("q")
                god.expect(">", timeout=20)
                command(god, "toggle paging no")
                assert b"\x1b[" in player.raw_transcript
                (ROOT / "bin/tests" / ("skills-info-" + backend + ".txt")).write_text(info)
                (ROOT / "bin/tests" / ("skills-levels-" + backend + ".txt")).write_text(table)
                print("PASS: " + backend + " real staff/mortal dispatcher, catalogs/spec differences, "
                      "live info/help, permissions, color and paging", flush=True)
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
