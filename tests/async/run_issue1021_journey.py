#!/usr/bin/env python3
"""Exercise issue #1021's fixes and conveniences on disposable MariaDB.

Uses the real server, command dispatcher, quest giver, combat and save/reload.
Never reads .env or connects to an existing game.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
import time

import test_mariadb_combat_journey as journey
from test_flight_network_journey import authority, command

ROOT = journey.ROOT
STAFF, BARD, NECRO, THIEF = "Reportwarden", "Reportbard", "Reportnecro", "Reportthief"
ANSI = re.compile(r"\x1b\[[0-9;]*m")

MOBILES = """#22810
wisp raceless~
a raceless wisp~
A raceless wisp drifts here.
~
~
10 0 0 0 0 0 0 0 S
O 0 0 -1
1 0 0 1d1+30000 1d1+1
0.0.0.0 0
8 8 0
#22811
questgiver~
the questgiver~
The questgiver waits here for a delivery.
~
~
10 0 0 0 0 0 0 0 S
PH 0 0 -1
50 0 0 1d1+30000 1d1+1
0.0.0.0 0
8 8 0
"""

# A banana earns only an item that does not exist; a mace earns a real dagger; a
# silver star earns a real mace beside a missing item; a gold star is wanted
# only together with an item that does not exist.
QUEST = """#22811
M
delivery~
The questgiver says 'Bring me a banana or a mace.'
~
Q
~
R I 29998
G I 15
Q
~
R I 256
G I 677
Q
~
R I 677
R I 29998
G I 24
Q
~
R I 256
G I 23
G I 29997
S
"""


def plain(text):
    return ANSI.sub("", text)


def configure(runtime):
    journey.make_fixture(runtime)
    journey.generate_certificate(runtime)
    (runtime / "help").symlink_to(ROOT / "help", target_is_directory=True)
    (runtime / "logs/log").mkdir(parents=True)
    (runtime / "journals/critical").mkdir(parents=True, mode=0o700)
    mini = runtime / "areas_mini"
    path = mini / "mini.mob"
    path.write_text(path.read_text().replace("$~", MOBILES + "$~"))
    path = mini / "mini.qst"
    text = path.read_text()
    assert text.count("$~") == 1
    path.write_text(text.replace("$~", QUEST + "$~"))
    path = mini / "mini.zon"
    text = re.sub(r"^[MGE] .*\n", "", path.read_text(), flags=re.M)
    path.write_text(text.replace("\nS\n", "\n" + "".join(
        f"M 0 {vnum} 1 22800 100 0 0 0\n" for vnum in (11, 22810, 22811)) + "S\n"))


def run(binary):
    report = {"binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(), "checks": []}
    out = ROOT / "bin/tests/issue-1021-gameplay.json"
    out.parent.mkdir(parents=True, exist_ok=True)

    def passed(label):
        report["checks"].append(label)
        out.write_text(json.dumps(report, indent=2))
        print("PASS " + label, flush=True)

    with tempfile.TemporaryDirectory(prefix="issue1021-", dir=ROOT / "bin/tests") as temporary:
        runtime = Path(temporary)
        configure(runtime)
        plain_port, tls, websocket = journey.available_ports()
        clients, process = [], None
        output_path = runtime / "server.out"
        with authority("mariadb", runtime) as (env, sql), output_path.open("w") as output:
            env.update(CRITICAL_COMMAND_JOURNAL_DIR=str(runtime / "journals/critical"),
                       DURIS_TLS_PORT=str(tls), DURIS_WEBSOCKET_PORT=str(websocket),
                       MAINTENANCE_STATE_FILE=str(runtime / "maintenance.state"))

            def boot():
                offset = output_path.stat().st_size
                proc = subprocess.Popen([str(binary), "--minimal", "-d", str(runtime), str(plain_port)],
                                        cwd=runtime, env=env, stdout=output, stderr=subprocess.STDOUT)
                deadline = time.monotonic() + 90
                while b"Entering game loop." not in output_path.read_bytes()[offset:]:
                    assert proc.poll() is None and time.monotonic() < deadline, output_path.read_text()[-6000:]
                    time.sleep(.1)
                return proc

            def stop():
                for client in clients:
                    client.close()
                clients.clear()
                if process and process.poll() is None:
                    process.terminate()
                    process.wait(timeout=60)
                    assert process.returncode == 0

            def login(name):
                client = journey.reconnect_character(plain_port, expected_room=None, account=name, character=name)
                clients.append(client)
                client.expect_any(("Pos: standing >", "<>"), timeout=30)
                command(client, "toggle paging off")
                return client

            def do(client, text):
                return plain(command(client, text))

            def roster_row(client, name):
                members = do(client, "society").split("Members:")[1]
                return next(line for line in members.splitlines() if name in line)

            def group_list(client):
                return do(client, "group").split("Your group consists of")[1].split("Score information")[0]

            def until(client, text, wanted, seconds=30):
                deadline = time.monotonic() + seconds
                while True:
                    seen = do(client, text)
                    if wanted in seen:
                        return seen
                    assert time.monotonic() < deadline, f"{wanted!r} never followed {text!r}: {seen}"
                    time.sleep(.5)

            try:
                process = boot()
                for name, cls in ((STAFF, "w"), (BARD, "w"), (NECRO, "n"), (THIEF, "t")):
                    client = journey.MudClient(plain_port)
                    clients.append(client)
                    journey.create_character(client, expected_room=None, account=name, character=name,
                                             class_name=cls, email=name.lower() + "@example.invalid",
                                             alignment="n" if name == THIEF else "g",
                                             hometown="p" if name == NECRO else None)
                    print("Created " + name, flush=True)
                    command(client, "save")
                    client.send("quit")
                    client.expect("ACCOUNT MENU", timeout=30)
                    client.close()
                    clients.remove(client)
                stop()
                journey.make_overlord(sql, STAFF)
                defines = (ROOT / "src/core/defines.h").read_text() + (ROOT / "src/core/structs.h").read_text()

                def bit(name):
                    return 1 << (int(re.search(rf"^#define {name} BIT_(\d+)\b", defines, re.M)[1]) - 1)

                minstrel = int(re.search(r"^#define SPEC_MINSTREL (\d+)", defines, re.M)[1])
                thief_spec = int(re.search(r"^#define SPEC_THIEF (\d+)", defines, re.M)[1])
                # A specialized Bard below Riff's level 30, on a second Hardcore life.
                sql(f"UPDATE player_data SET m_class={bit('CLASS_BARD')},spec={minstrel},level=29,"
                    f"highest_level=29,act2=act2|{bit('PLR2_HARDCORE_CHAR')},numb_deaths=1,"
                    f"last_room=22800 WHERE name='{BARD}'")
                sql(f"UPDATE player_data SET level=30,highest_level=30,last_room=22800 WHERE name='{NECRO}'")
                sql(f"UPDATE player_data SET level=30,highest_level=30,spec={thief_spec},last_room=22800 "
                    f"WHERE name='{THIEF}'")
                process = boot()
                staff, bard, necro, thief = (login(name) for name in (STAFF, BARD, NECRO, THIEF))
                do(staff, "goto 22800")
                do(staff, "setbit room here flag ROOM_MAGIC_LIGHT 1")
                do(staff, "setbit char " + STAFF + " winvis 0")
                for name in (BARD, NECRO, THIEF):
                    do(staff, "transfer " + name)

                text = do(bard, "riff healing")
                assert "You have not learned how to riff." in text, text
                assert "cannot seem to recall" not in text, text
                passed("B1: a specialized Bard with no Riff rating is refused instead of failing a roll")

                text = do(bard, "score")
                assert "HardCore lives: 2 of 3 remaining" in text, text
                assert "HardCore lives" not in do(thief, "score")
                passed("I14: score shows a Hardcore character's remaining lives and nobody else's")

                text = do(thief, "look wisp")
                assert "Bogus race" not in text and "raceless wisp is in excellent condition" in text, text
                text = do(thief, "look questgiver")
                assert "appears to be Human and is in excellent condition" in text, text
                passed("B4: a creature authored without a race shows its condition, not 'Bogus race!'")

                for vnum, keyword in ((15, "banana"), (677, "mace"), (23, "gold")):
                    assert "You have created" in do(staff, f"load obj {vnum}")
                    assert "Ok." in do(staff, f"give {keyword} {THIEF}")
                text = do(thief, "give banana questgiver")
                assert "has no reward to offer for that right now, so you keep it." in text, text
                assert "banana" in do(thief, "inventory")
                text = do(thief, "give gold questgiver")
                assert "has no reward to offer for that right now, so you keep it." in text, text
                assert "gold star" in do(thief, "inventory")
                text = do(thief, "give mace questgiver")
                # A full pack puts the reward at the player's feet.
                assert re.search(r"questgiver (gives you|places) a steel dagger", text), text
                assert "mace" not in do(thief, "inventory")
                assert "You have created" in do(staff, "load obj 24")
                assert "Ok." in do(staff, f"give silver {THIEF}")
                text = do(thief, "give silver questgiver")
                assert re.search(r"questgiver (gives you|places) a small wooden mace", text), text
                passed("B5: hand-ins toward completions that cannot pay are refused and kept; sound ones pay")

                # A blow can leave Raoul mortally wounded; stay vicious and keep attacking.
                do(necro, "toggle vicious on")
                deadline = time.monotonic() + 150
                while "corpse of raoul" not in do(necro, "look"):
                    assert time.monotonic() < deadline, "Raoul never died"
                    do(necro, "kill raoul")
                    time.sleep(.5)
                text = do(necro, "examine corpse")
                assert "In life this was a creature of level 1." in text, text
                text = do(thief, "examine corpse")
                assert "examine the dead" in text and "In life this was" not in text, text
                passed("I15: a Necromancer examining a corpse learns its level; a Rogue does not")

                assert "new association is set up" in do(staff, f"supervise found {THIEF} n Reportguild")
                for name, client in ((NECRO, necro), (BARD, bard)):
                    do(client, "society apply " + THIEF)
                    do(thief, "society enroll " + name)
                roster = do(thief, "society")
                rows = {name: next(line for line in roster.split("Members:")[1].splitlines()
                                   if name in line) for name in (THIEF, NECRO, BARD)}
                assert re.search(r"\[30 Necromancer +\] " + NECRO + r" +Human", rows[NECRO]), roster
                assert re.search(r"\[29 .*\] " + BARD + r" +Human +HC \|", rows[BARD]), roster
                assert " HC |" not in rows[NECRO], roster
                columns = {row.index("|") for row in rows.values()}
                assert len(columns) == 1, roster
                do(necro, "save")
                necro.send("quit")
                necro.expect("ACCOUNT MENU", timeout=30)
                necro.close()
                clients.remove(necro)
                row = roster_row(thief, NECRO)
                assert re.search(r"^   \[30 Necromancer +\] " + NECRO, row), row
                necro = login(NECRO)
                do(staff, "transfer " + NECRO)
                assert "Anonymous" in do(necro, "toggle anonymous")
                row = roster_row(thief, NECRO)
                assert "[   - Anonymous -   ] " + NECRO in row, row
                row = roster_row(necro, NECRO)
                assert "[30 Necromancer" in row, row
                do(necro, "toggle anonymous")
                passed("I10: the guild roster aligns level, class, race and Hardcore, online, offline and anonymous")

                do(staff, f"givepet {THIEF} 22810")
                do(thief, "group all")
                do(necro, "consent " + THIEF)
                assert "now a member" in do(thief, "group " + NECRO)
                classic = group_list(thief)
                assert classic.index("raceless wisp") < classic.index(NECRO), classic
                assert "(Human)" in classic, classic
                assert "players before pets" in do(thief, "toggle groupsort")
                listed = group_list(thief)
                assert listed.index(THIEF) < listed.index(NECRO) < listed.index("raceless wisp"), listed
                assert "(Human)" not in listed and "Aura" not in listed, listed
                starts = {line.index("H (") for line in listed.splitlines() if "H (" in line}
                assert len(starts) == 1, listed
                classic = group_list(necro)
                assert classic.index("raceless wisp") < classic.index(NECRO) and "(Human)" in classic, classic
                passed("I11: toggle groupsort lists players before pets for its owner only; classic stays the default")

                warning = "You hold more than one artifact of the same type."
                for vnum, keyword in ((900, "blue"), (901, "red")):
                    assert "You have created" in do(staff, f"load obj {vnum}")
                    do(staff, "drop " + keyword)
                deadline = time.monotonic() + 30
                while sql("SELECT COUNT(*) FROM artifacts WHERE vnum IN (900,901)") != "2":
                    assert time.monotonic() < deadline, "the two artifacts were never recorded"
                    time.sleep(.2)
                # The starter kit fills the pack; make room before lifting the stones.
                do(necro, "wear all")
                do(necro, "drop all")
                text = do(necro, "get blue")
                assert "You get" in text and warning not in text, text
                text = do(necro, "get red")
                assert "You get" in text and warning in text, text
                # Parting with one ends it; the half-hourly sweep is covered by its own test.
                do(necro, "drop red")
                text = do(necro, "wear blue")
                assert warning not in text, text
                passed("I8: picking up a second artifact of one type warns at once; one of a type does not")

                do(staff, f"cast 'concealment' {BARD}")
                until(staff, "stat char " + BARD, "'concealment'")
                do(staff, f"cast 'faerie fire' {BARD}")
                text = until(staff, "stat char " + BARD, "'faerie fire'")
                assert "'concealment'" not in text, text
                assert "this stuff all over you" in do(bard, "hide")
                passed("B3: Faerie Fire strips its target's Concealment spell and still blocks hide")

                do(thief, "save")
                mark = len(staff.transcript)
                until(staff, "force " + THIEF + " dirttoss questgiver", "seems to be blinded", 60)
                # The recovery arrives between commands, so read everything since the toss.
                deadline = time.monotonic() + 40
                while "questgiver blinks as its sight returns." not in plain(
                        bytes(staff.transcript[mark:]).decode(errors="replace")):
                    assert time.monotonic() < deadline, bytes(staff.transcript[mark:]).decode(errors="replace")
                    do(staff, "look")
                    time.sleep(.5)
                passed("I12: observers see a blinded creature regain its sight when the blindness wears off")

                stop()
                process = boot()
                thief = login(THIEF)
                assert re.search(r"Group Sorted:\s*ON", do(thief, "toggle")), do(thief, "toggle")
                assert "classic layout" in do(thief, "toggle groupsort")
                passed("I11: the groupsort preference survives a save and server restart")
                stop()
            except BaseException:
                for client in clients:
                    print(bytes(client.transcript).decode(errors="replace")[-6000:])
                print(output_path.read_text(errors="replace")[-6000:])
                raise
            finally:
                stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", type=Path, required=True)
    run(parser.parse_args().server.resolve())
