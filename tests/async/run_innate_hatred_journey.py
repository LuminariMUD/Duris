#!/usr/bin/env python3
"""Hatred gameplay and persistence on disposable flat-file or MariaDB authority.

Run --backend mariadb through with_disposable_mariadb.sh. No checkout .env or
existing game is used. --output retains the synthetic acceptance evidence.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import signal
import subprocess
import tempfile
import time

import test_flatfile_combat_journey as journey
from test_flight_network_journey import authority, command

ROOT = journey.ROOT
GOD, GOD_ACCOUNT = "Hatredwarden", "Hatredstaff"
PLAYER, ACCOUNT = "Hatredpupil", "Hatredplayer"
ACTIVATION = "At the sight of your nemesis the hatred of old generations BURN in your blood!"
SUBSIDENCE = "You feel the hatred in your heart subside."
HATRED = 2015
ENEMIES = {22801: ("hatredhuman", "PH", "Human"),
           22802: ("hatredorc", "HO", "Orc"),
           22803: ("hatredduergar", "PD", "Duergar"),
           22804: ("hatreddrow", "PL", "Drow")}


def stop(process, clients):
    for client in clients:
        client.close()
    clients.clear()
    if process:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=45)
        assert process.returncode == 0, f"Hatred server exited with status {process.returncode}"


def fixture(runtime):
    journey.make_fixture(runtime)
    journey.generate_certificate(runtime)
    (runtime / "help").symlink_to(ROOT / "help", target_is_directory=True)
    (runtime / "logs/log").mkdir(parents=True)
    (runtime / "logs/log/.gitignore").write_text("*\n!.gitignore\n")
    (runtime / "journals/critical").mkdir(parents=True, mode=0o700)

    def records(path):
        return {int(match[1]): match[0] for match in re.finditer(
            r"(?ms)^#(\d+)\n.*?(?=^#\d+\n|^\$~)", path.read_text())}

    def write(path, rows):
        path.write_text("".join(rows[key] for key in sorted(rows)) + "$~\n")

    world = runtime / "areas_mini/mini.wld"
    rooms = records(world)
    exits = {22800: [(0, 22801), (1, 22802), (2, 22803), (3, 22804), (4, 30000), (5, 22439)],
             22801: [(2, 22800)], 22802: [(3, 22800)], 22803: [(0, 22800)],
             22804: [(1, 22800)], 30000: [(5, 22800)], 22439: [(4, 22800)]}
    for room, links in exits.items():
        name = "Hatred test inn" if room == 22439 else f"Hatred test room {room}"
        sector = 22 if room == 30000 else 0  # SECT_ETHEREAL in the second zone.
        directions = "".join(f"D{direction}\n~\n~\n0 0 {target}\n" for direction, target in links)
        rooms[room] = f"#{room}\n{name}~\nA quiet disposable Hatred test room.\n~\n1 0 {sector}\n{directions}S\n"
    write(world, rooms)
    mobiles = runtime / "areas_mini/mini.mob"
    mobs = records(mobiles)
    for vnum, (name, code, _) in ENEMIES.items():
        mobs[vnum] = (f"#{vnum}\n{name}~\nthe {name} fixture~\nThe {name} fixture waits here.\n~\n~\n"
                      f"10 0 0 0 0 0 0 0 S\n{code} 0 0 -1\n1 0 0 1d1+1000 1d1+1\n0.0.0.0 0\n8 8 0\n")
    write(mobiles, mobs)
    zone = runtime / "areas_mini/mini.zon"
    text = re.sub(r"(?m)^[MG] .*\n", "", zone.read_text())
    resets = "".join(f"M 0 {vnum} 2 {vnum} 100 0 0 0\n" for vnum in ENEMIES)
    resets += "M 0 22802 2 22439 100 0 0 0\n"
    text = text.replace("\nS\n", "\n" + resets + "S\n")
    text = text.replace("$~", "#300\nHatred second zone~\nhatred-test~\n30999 0 0 6 11 1\n"
                        "M 0 22804 2 30000 100 0 0 0\nS\n$~")
    zone.write_text(text)


def run(binary, backend):
    evidence = {"backend": backend, "source_sha": subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
        "timer_pulses": 4, "cases": [], "npc_definitions": ENEMIES}
    (ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="hatred-" + backend + "-", dir=ROOT / "bin/tests") as temporary:
        runtime = Path(temporary)
        fixture(runtime)
        (runtime / "bin/server").mkdir(parents=True)
        executable = runtime / "bin/server/dms"
        shutil.copy2(binary, executable)
        shutil.copy2(binary, runtime / "bin/server/dms_new")
        with (runtime / "lib/misc/event_names").open("w") as names:
            subprocess.run([str(ROOT / "scripts/event_names.sh"), str(executable)], stdout=names, check=True)
        (runtime / "copyover").mkdir()
        plain, tls, websocket = journey.available_ports()
        output_path = runtime / "server.out"
        clients = []
        process = None
        with authority(backend, runtime) as (env, sql), output_path.open("w") as output:
            env.update(CRITICAL_COMMAND_JOURNAL_DIR=str(runtime / "journals/critical"),
                       DURIS_TLS_PORT=str(tls), DURIS_WEBSOCKET_PORT=str(websocket),
                       COPYOVER_STATE_FILE=str(runtime / "copyover/state"))

            def boot():
                nonlocal process
                offset = output_path.stat().st_size
                process = subprocess.Popen([str(executable), "--minimal", "-s", "-d", str(runtime), str(plain)],
                                           cwd=runtime, env=env, stdout=output, stderr=subprocess.STDOUT)
                deadline = time.monotonic() + 120
                while b"Entering game loop." not in output_path.read_bytes()[offset:]:
                    assert process.poll() is None and time.monotonic() < deadline, "Hatred server failed to boot"
                    time.sleep(.1)

            def login(name, account, resident=False):
                client = journey.reconnect_character(plain, expected_room=None, account=account, character=name)
                clients.append(client)
                if not resident:
                    client.expect("Welcome to Duris", timeout=45)
                command(client, "toggle paging no")
                return client

            def drain(client):
                while client._receive():
                    pass
                client.pending.clear()

            def messages(client):
                drain(client)
                text = bytes(client.transcript).decode(errors="replace")
                return text.count(ACTIVATION), text.count(SUBSIDENCE)

            def current_tick():
                text = command(god, "world events event_hatred_check")
                row = re.search(r"^\s*\d+\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|", text, re.M)
                assert row, text
                due, remaining, late = map(int, row.groups())
                return due - remaining + late

            def state(active, label):
                if not active:
                    time.sleep(1.5)  # allow a default watcher callback before accepting absence
                deadline = time.monotonic() + 12
                while True:
                    text = command(god, "stat char " + PLAYER)
                    rows = re.findall(r"^\s*(.*?)\s+by\s+(-?\d+)\s+for\s+(-?\d+)\s+from\s+'hatred'", text, re.M)
                    if len(rows) == (2 if active else 0):
                        break
                    assert time.monotonic() < deadline, label + ":\n" + text
                    time.sleep(.2)
                assert text.count("event_hatred_check") == 1, label + ":\n" + text
                if active:
                    assert all(mod == duration == "-1" for _, mod, duration in rows), rows
                    assert any("combat" in location.lower() for location, _, _ in rows), rows
                    assert any("spell" in location.lower() for location, _, _ in rows), rows
                evidence["cases"].append({"case": label, "active": active, "affects": rows,
                                          "watchers": 1, "messages": messages(player)})
                print("[PASS]", backend, label, flush=True)

            def save(client, name):
                client.send("save")
                client.expect("Save complete for " + name + ".", timeout=45)
                if sql and name == PLAYER:
                    assert sql(f"SELECT COUNT(*) FROM player_affects WHERE pid=(SELECT pid FROM player_data WHERE name='{PLAYER}') AND type={HATRED}") == "0"

            def visit(room):
                command(god, "goto " + str(room))
                command(god, "transfer " + PLAYER)

            try:
                boot()
                for name, account in ((GOD, GOD_ACCOUNT), (PLAYER, ACCOUNT)):
                    client = journey.MudClient(plain)
                    clients.append(client)
                    journey.create_character(client, expected_room=None, account=account,
                                             character=name, email=name.lower() + "@example.invalid")
                    save(client, name)
                stop(process, clients)
                if sql:
                    sql(f"UPDATE player_data SET level=62,highest_level=62 WHERE name='{GOD}'")
                else:
                    journey.make_overlord(Path(env["FLATFILE_STATE_DIR"]), GOD)
                boot()
                god, player = login(GOD, GOD_ACCOUNT), login(PLAYER, ACCOUNT)
                evidence["entry_tick"] = current_tick()
                for room in (22439, 22800, 22801, 22802, 22803, 22804, 30000):
                    command(god, "goto " + str(room))
                    command(god, "setbit room here flag ROOM_MAGIC_LIGHT 1")
                for vnum, (name, _, race) in ENEMIES.items():
                    text = command(god, "stat mob " + name)
                    assert re.search(r"Race:\s*" + re.escape(race), text), (vnum, text)
                visit(22800)
                command(god, f"setbit char {PLAYER} race 'Mountain Dwarf'")
                command(god, f"setbit char {PLAYER} level 20")
                command(god, f"setbit char {PLAYER} platinum 1000")
                command(player, "east")
                state(False, "below unlock with an orc")
                command(god, f"setbit char {PLAYER} level 21")
                state(True, "resident level unlock")
                before = messages(player)
                command(player, "look"); command(player, "look")
                time.sleep(2)  # two default watcher checks must keep the transition silent
                state(True, "unchanged occupancy")
                assert messages(player) == before
                command(player, "west")
                state(False, "empty room after leaving orc")
                command(player, "north")
                state(False, "ordinary human NPC")
                command(player, "south")
                state(False, "self-only room")
                # Synchronize just after a longer check before passing through a hated room.
                command(god, "properties set innate.timer.hatred 32.000")
                deadline = time.monotonic() + 12
                while True:
                    schedule = command(god, "stat char " + PLAYER)
                    due = re.search(r"(\d+) seconds, event_hatred_check", schedule)
                    if due and int(due[1]) >= 7:
                        break
                    assert time.monotonic() < deadline, schedule
                    time.sleep(.1)
                before = messages(player)
                command(player, "east"); command(player, "west")
                time.sleep(8.25)
                state(False, "rapid movement between checks")
                assert messages(player) == before
                command(god, "properties set innate.timer.hatred 4.000")
                for direction, back, label in (("east", "west", "orc"), ("south", "north", "duergar"),
                                                ("west", "east", "drow"), ("up", "down", "second zone ethereal drow")):
                    before = messages(player)
                    command(player, direction)
                    state(True, label)
                    assert messages(player) == (before[0] + 1, before[1])
                    command(player, back)
                    state(False, "leave " + label)
                    assert messages(player) == (before[0] + 1, before[1] + 1)
                command(player, "east")
                state(True, "visible enemy before sleep")
                command(player, "sleep")
                state(False, "sleeping actor cannot see")
                command(player, "wake")
                state(True, "wake restores visibility")
                # The inn has another instance of this prototype; select the local one.
                command(god, "goto 22802")
                command(god, "setbit mob hatredorc aff INVIS 1")
                state(False, "invisible enemy without detection")
                command(god, "cast 'detect invisibility' " + PLAYER)
                state(True, "detection restores enemy visibility")
                command(god, "setbit mob hatredorc aff INVIS 0")
                before = messages(player)
                # Measure game pulses so scheduler delays cannot weaken tick coverage.
                first_tick = current_tick()
                last_tick = first_tick
                deadline = time.monotonic() + 240
                while last_tick - first_tick < 600:
                    assert time.monotonic() < deadline, "sustained Hatred did not span two affect ticks"
                    time.sleep(5)
                    state(True, "sustained presence across affect ticks")
                    last_tick = current_tick()
                evidence["sustained_game_pulses"] = last_tick - first_tick
                evidence["sustained_affect_tick_boundaries"] = last_tick // 300 - first_tick // 300
                assert evidence["sustained_affect_tick_boundaries"] >= 2
                assert messages(player) == before
                save(player, PLAYER)
                player.close(); clients.remove(player)
                player = login(PLAYER, ACCOUNT, resident=True)
                state(True, "linkdead reconnect")
                process.send_signal(signal.SIGUSR1)
                god.expect("Copyover complete!", timeout=120)
                player.expect("Copyover complete!", timeout=120)
                state(True, "copyover reconstructs pair and watcher")
                visit(22800)
                state(False, "post-copyover empty room")
                command(player, "down")
                state(True, "active pair at the inn")
                save(player, PLAYER)
                player.send("rent")
                player.expect("ACCOUNT MENU", timeout=30)
                player.close(); clients.remove(player)
                player = login(PLAYER, ACCOUNT)
                visit(22802)
                state(True, "rent and relogin recompute the pair")
                save(player, PLAYER)
                stop(process, clients); boot()
                god, player = login(GOD, GOD_ACCOUNT), login(PLAYER, ACCOUNT)
                visit(22802)
                state(True, "cold restart recomputes transient state")
                visit(22800)
                state(False, "no carried hatred after restart")
                # Extraction must remove the event-owned pair as well as the watcher.
                command(god, "load mob 22802")
                state(True, "active pair before death")
                command(god, "load mob 22800")
                journey.attack_until_death(player)
                player.expect("ACCOUNT MENU", timeout=30)
                assert "No such character." in command(god, "stat char " + PLAYER)
                evidence["cases"].append({"case": "death extracts the resident", "resident_present": False})
                evidence["completed"] = True
            except Exception:
                print(output_path.read_text(errors="replace")[-5000:])
                print(journey.runtime_logs(runtime))
                for client in clients:
                    print(bytes(client.transcript).decode(errors="replace").replace(journey.PASSWORD, "[REDACTED]")[-7000:])
                raise
            finally:
                stop(process, clients)
    return evidence


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", type=Path, required=True)
    parser.add_argument("--backend", choices=("flatfile", "mariadb"), default="flatfile")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run(args.server.resolve(), args.backend)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
