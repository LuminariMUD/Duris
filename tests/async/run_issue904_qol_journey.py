#!/usr/bin/env python3
"""Exercise issue #904's ten accepted conveniences on disposable MariaDB.

Uses the real server, command dispatcher, item grants, GMCP and save/reload.
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
from test_mariadb_chaos_new_character_kit import world_object_text

ROOT = journey.ROOT
STAFF, MONK, ETHER, ROGUE = "Qolwarden", "Qolmonk", "Qolether", "Qolrogue"
FRAME = re.compile(rb"\xff\xfa\xc9(.*?)\xff\xf0", re.S)


def packets(client, offset=0):
    return [json.loads(frame.split(b" ", 1)[1])
            for frame in FRAME.findall(bytes(client.raw_transcript[offset:]))
            if frame.startswith(b"Room.Info ")]


def configure(runtime):
    journey.make_fixture(runtime)
    journey.generate_certificate(runtime)
    (runtime / "help").symlink_to(ROOT / "help", target_is_directory=True)
    (runtime / "logs/log").mkdir(parents=True)
    (runtime / "journals/critical").mkdir(parents=True, mode=0o700)
    mini = runtime / "areas_mini"
    path = mini / "mini.wld"
    text = path.read_text().replace(
        "This quiet stone arena exists to prove the complete combat journey.\n~\n1 0 0\nS",
        "This quiet stone arena exists to prove the complete combat journey.\n~\n1 0 0\n"
        "D0\nA stone panel.\n~\npanel~\n1 -1 22801\nS")
    text = text.replace("$~", "#22801\nThe QOL Refuge~\nA quiet refuge.\n~\n1 0 0\n"
                        "D2\nAn opening.\n~\n~\n0 -1 22800\nS\n$~")
    path.write_text(text)
    path = mini / "mini.zon"
    text = re.sub(r"^[MGE] .*\n", "", path.read_text(), flags=re.M)
    path.write_text(text.replace("\nS\n", "\nD 0 22800 0 5 100 0 0 0\nS\n"))
    # Add only the real poison templates required by the information page.
    definitions = (ROOT / "src/world/vnum.obj.h").read_text()
    wanted = {int(value) for value in re.findall(
        r"^#define VOBJ_(?:FORAGE_\w+|POISON_VIAL\w*)\s+(\d+)\b", definitions, re.M)}
    path = mini / "mini.obj"
    records = {int(vnum): block for vnum, block in re.findall(
        r"(?ms)^#(\d+)\n(.*?)(?=^#\d+\n|^\$~)", path.read_text())}
    for vnum, block in re.findall(r"(?ms)^#(\d+)\n(.*?)(?=^#\d+\n|^\$~)", world_object_text()):
        if int(vnum) in wanted:
            records.setdefault(int(vnum), block)
    path.write_text("".join(f"#{vnum}\n{records[vnum]}" for vnum in sorted(records)) + "$~\n")


def run(binary):
    report = {"binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(), "checks": []}
    out = ROOT / "bin/tests/issue-904-gameplay.json"
    out.parent.mkdir(parents=True, exist_ok=True)

    def passed(label):
        report["checks"].append(label)
        out.write_text(json.dumps(report, indent=2))
        print("PASS " + label, flush=True)

    with tempfile.TemporaryDirectory(prefix="issue904-", dir=ROOT / "bin/tests") as temporary:
        runtime = Path(temporary)
        configure(runtime)
        plain, tls, websocket = journey.available_ports()
        clients, process = [], None
        output_path = runtime / "server.out"
        with authority("mariadb", runtime) as (env, sql), output_path.open("w") as output:
            env.update(CRITICAL_COMMAND_JOURNAL_DIR=str(runtime / "journals/critical"),
                       DURIS_TLS_PORT=str(tls), DURIS_WEBSOCKET_PORT=str(websocket),
                       MAINTENANCE_STATE_FILE=str(runtime / "maintenance.state"))

            def boot():
                offset = output_path.stat().st_size
                proc = subprocess.Popen([str(binary), "--minimal", "-d", str(runtime), str(plain)],
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
                client = journey.reconnect_character(plain, expected_room=None, account=name, character=name)
                clients.append(client)
                client.expect_any(("Pos: standing >", "<>"), timeout=30)
                command(client, "toggle paging off")
                return client

            def seed_level(name, level):
                sql(f"UPDATE player_data SET level={level},highest_level={level},last_room=22800 "
                    f"WHERE name='{name}'")

            try:
                process = boot()
                for name, cls in ((STAFF, "w"), (MONK, "k"), (ETHER, "g"), (ROGUE, "t")):
                    client = journey.MudClient(plain)
                    clients.append(client)
                    journey.create_character(client, account=name, character=name, class_name=cls,
                                             email=name.lower() + "@example.invalid", alignment="n" if name == ROGUE else "g")
                    if name == ETHER:
                        assert "steel dagger" in command(client, "equipment") + command(client, "inventory")
                    print("Created " + name, flush=True)
                    command(client, "save")
                    client.send("quit")
                    client.expect("ACCOUNT MENU", timeout=30)
                    client.close()
                    clients.remove(client)
                stop()
                journey.make_overlord(sql, STAFF)
                seed_level(MONK, 24)
                seed_level(ROGUE, 56)
                spells = (ROOT / "src/magic/spells.h").read_text()
                mix = int(re.search(r"^#define SKILL_MIXPOISON\s+(\d+)", spells, re.M)[1])
                rogue_pid = sql(f"SELECT pid FROM player_data WHERE name='{ROGUE}'")
                sql(f"UPDATE player_data SET spec=1 WHERE name='{ROGUE}';"
                    f"REPLACE INTO player_skills(pid,skill_id,learned,taught) VALUES({rogue_pid},{mix},100,100)")
                process = boot()
                staff, monk, ether, rogue = (login(name) for name in (STAFF, MONK, ETHER, ROGUE))
                command(staff, "goto 22800")
                command(staff, "setbit room here flag ROOM_MAGIC_LIGHT 1")
                for name in (MONK, ETHER, ROGUE):
                    command(staff, "transfer " + name)
                assert "steel dagger" in command(ether, "equipment") + command(ether, "inventory")
                passed("I11: first-entry Ethermancer dagger is usable and survives save/reload")

                for size in (12, 48, 96, 100):
                    text = command(monk, f"toggle screensize {size}")
                    assert f"{size} lines" in text, text
                for size in ("11", "101", "100 junk", "-1", "12junk", "999999999999999999999"):
                    assert "12-100" in command(monk, "toggle screensize " + size)
                for value in ("", "default", "off", "0"):
                    assert "40 lines" in command(monk, "toggle screensize " + value)
                command(monk, "toggle screensize 100")
                command(monk, "save")
                deadline = time.monotonic() + 20
                while sql(f"SELECT screen_length FROM player_data WHERE name='{MONK}'") != "100":
                    assert time.monotonic() < deadline, "screen size save did not complete"
                    time.sleep(.1)
                passed("I26: 12/48/96/100 accepted, invalid input rejected, defaults preserved, 100 saved")

                command(staff, f"setbit char {ETHER} skill meditate 100")
                command(ether, "sit")
                text = command(ether, "meditate")
                assert "You start meditating" in text, text
                for option in ("afk on", "afk off", "af on"):
                    text = command(ether, "toggle " + option)
                    assert "stop meditating" not in text, text
                    assert "MEDITATE" in command(staff, "stat char " + ETHER), text
                text = command(ether, "stand")
                assert "stop meditating" in text, text
                passed("I21: AFK toggles preserve real meditation while standing still ends it")

                own = command(ether, "spells")
                assert "[future circle]" in own and "Max Circle 1" in own, own
                assert "[future circle]" in command(ether, "spells ethermancer")
                passed("I23: personal and reference spell views show future-circle labels")
                info = command(rogue, "skills info mixpoison")
                assert all(word in info for word in ("Ingredients:", "Effect:", "madness", "Apply Poison")), info
                assert "You have not learned to mix poison" in command(ether, "skills info mixpoison")
                passed("I2: real skill-info dispatch shows eligible poison ingredients and effects")
                for vnum, keyword in ((102, "vial"), (827, "strange"), (825, "blood"),
                                      (822, "root"), (801, "mangrove"),
                                      (817, "purple"), (818, "pink")):
                    assert "You have created" in command(staff, f"load obj {vnum}")
                    text = command(staff, f"give {keyword} {ROGUE}")
                    assert "Ok." in text, text
                assert "finish mixing the poison" in command(rogue, "mixpoison")
                command(rogue, "save")

                assert "Named-set spell bonuses" in command(monk, "area")
                assert "None listed" in command(monk, "area")
                passed("I52: AREA includes the set section and handles an unlisted zone")

                command(monk, "remove all")
                command(staff, "load obj 256")
                command(staff, "give dagger " + MONK)
                text = command(monk, "hold dagger")
                assert "one base attack per round" in text and "bare-hand damage dice" in text, text
                assert "steel dagger" in command(monk, "equipment")
                passed("I19: equipping a weapon explains both monk penalties and still equips it")

                command(staff, "givepet " + MONK + " 11")
                command(staff, "givepet " + MONK + " 22800")
                command(staff, "load obj 256")
                command(staff, "give dagger executioner")
                command(staff, "force executioner hold dagger")
                assert "steel dagger" in command(monk, "look executioner")
                command(monk, "sit")
                assert "sending" in command(monk, "dismiss executioner")
                assert "steel dagger" in command(monk, "look")
                assert "sending" in command(monk, "dismiss")
                assert "no avail" in command(monk, "dismiss")
                command(monk, "stand")
                passed("I31: sitting dismissal removes individual/all pets and drops equipped pet gear safely")

                assert "You still need" in command(monk, "deathsdoor")
                command(staff, "setbit char " + MONK + " level 20")
                assert "You still need" in command(monk, "deathsdoor")
                command(staff, "setbit char " + MONK + " level 19")
                assert "You still need" not in command(monk, "deathsdoor")
                command(staff, "setbit char " + MONK + " level 24")
                command(staff, "setbit char " + MONK + " level 25")
                passed("I22: the actual command shows requirements at 20/24 and hides them below 20")

                monk.socket.sendall(b"\xff\xfd\xc9")
                command(monk, "look")
                # Drain negotiation's initial snapshot and any pre-existing dirty-room
                # broadcast before counting a single explicit command's output.
                deadline = time.monotonic() + 1
                while time.monotonic() < deadline:
                    monk._receive()
                before = len(monk.raw_transcript)
                command(monk, "look")
                rooms = packets(monk, before)
                assert len(rooms) == 1 and "n" not in rooms[0]["exits"], rooms
                before = len(monk.raw_transcript)
                command(monk, "search dagger")
                assert not packets(monk, before)
                before = len(monk.raw_transcript)
                command(staff, "search")
                command(monk, "score")
                rooms = packets(monk, before)
                assert len(rooms) == 1 and "n" in rooms[0]["exits"], rooms
                command(staff, "open panel")
                before = len(monk.raw_transcript)
                command(monk, "north")
                # Existing movement sends directly and via the room-dirty broadcast.
                # Drain that broadcast and ensure automatic look adds no third send.
                deadline = time.monotonic() + 1
                while time.monotonic() < deadline:
                    monk._receive()
                moved = packets(monk, before)
                assert len(moved) == 2 and all(room["num"] == 22801 for room in moved), moved
                passed("I39: look/discovery refresh once, item search stays quiet, movement retains its two existing sends")
                command(monk, "save")
                stop()
                process = boot()
                monk, ether, rogue = login(MONK), login(ETHER), login(ROGUE)
                text = command(monk, "toggle")
                assert re.search(r"Screen[^\r\n]*\b100\b", text, re.I), text
                ether_pid = sql(f"SELECT pid FROM player_data WHERE name='{ETHER}'")
                count = sql(f"SELECT COUNT(*) FROM item_current_owner WHERE owner_type=1 "
                            f"AND owner_id={ether_pid} AND state=1 AND vnum=256")
                assert count == "1", "starter dagger was lost or granted twice: " + count
                assert "steel dagger" in command(ether, "equipment") + command(ether, "inventory")
                passed("I26/I11: restart restores 100-line paging and exactly one Ethermancer starter dagger")
                command(rogue, f"drop {ROGUE}")
                assert "mixed by " + ROGUE in command(rogue, "look")
                assert "mixed by " + ROGUE not in command(rogue, "inventory")
                passed("Crafting: maker keywords survive a MariaDB save and server restart")
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
