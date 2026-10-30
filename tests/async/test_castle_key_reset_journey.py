#!/usr/bin/env python3
"""Castle keys, mode-1 resets and seven mortal escape routes on private flat files.

The authored room graph, key prototypes and selected reset rows are used directly.
Only the timer lifespan (one tick), NPC aggression/wandering and unrelated spawns
are controlled. No .env, shared server or existing player state is accessed.
"""
from collections import deque
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import time

import test_flatfile_combat_journey as base
from test_castle_key_reset import GATES, REVERSE, castle_data, records
from test_flight_network_journey import command

ROOT = base.ROOT
DIRECTIONS = ("north", "east", "south", "west", "up", "down")
PLAYERS = ("Gateone", "Gatetwo", "Gatethree", "Gatefour", "Gatefive", "Gatesix", "Gateseven")
STAFF = "Gatewarden"
ALIASES = ("juku", "giauque", "rat", "cetyla", "povtail", "glynn", "gilman")


def configure(runtime):
    base.make_fixture(runtime)
    rooms, exits, rows = castle_data()
    mini = runtime / "areas_mini"
    merged = records((mini / "mini.wld").read_text())
    merged.update(rooms)
    merged[5760] = "#5760\nOutside Quintaragon Castle~\nThe exit route ends here.\n~\n57 0 0\nS\n"
    (mini / "mini.wld").write_text("".join(merged[v] for v in sorted(merged)) + "$~\n")
    objects = records((mini / "mini.obj").read_text())
    objects.update(records((ROOT / "areas/obj/castle.obj").read_text()))
    (mini / "mini.obj").write_text("".join(objects[v] for v in sorted(objects)) + "$~\n")
    mobiles = records((mini / "mini.mob").read_text())
    authored = records((ROOT / "areas/mob/castle.mob").read_text())
    carriers = {g[1] for g in GATES} | {2401}
    for vnum in carriers:
        parts = authored[vnum].split("~")
        lines = parts[4].strip().splitlines()
        flags = lines[0].split()
        assert len(flags) == 10 and flags[-1] == "S"
        flags[0:4] = ["10", "0", "0", "0"]  # stationary, no aggression; other fields retained
        lines[0] = " ".join(flags)
        parts[4] = "\n" + "\n".join(lines) + "\n"
        mobiles[vnum] = "~".join(parts)
    (mini / "mini.mob").write_text("".join(mobiles[v] for v in sorted(mobiles)) + "$~\n")
    selected, use_carrier = [], False
    for c, args in rows:
        if c in ("M", "F"):
            use_carrier = c == "M" and args[1] in carriers
        if c == "D" or (use_carrier and c in ("M", "E", "G")):
            selected.append(c + " " + " ".join(map(str, args)))
    (mini / "mini.zon").write_text(
        "#1\nMinimal World~\nmini~\n2399 0 0 6 11 1\nS\n"
        "#24\nQuintaragon Castle~\ncastle~\n2532 1 0 1 1 1\n"
        + "\n".join(selected) + "\nS\n"
        "#57\nJourney staging~\nstaging~\n29999 0 0 6 11 1\nS\n$~\n")
    return exits


def escape_route(start, exits):
    queue, seen = deque([(start, [])]), {start}
    while queue:
        room, route = queue.popleft()
        if room == 5760:
            return route
        for (source, direction), (target, _, flags) in exits.items():
            if source == room and target not in seen:
                seen.add(target)
                queue.append((target, route + [(direction, target, bool(flags & 3))]))
    raise AssertionError(f"no authored escape route from {start}")


def run(binary):
    report = {"binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
              "routes": [], "key_sequences": []}
    evidence = ROOT / "bin/qualification/issue418"
    evidence.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="castle-journey-", dir=ROOT / "bin/tests") as temp:
        runtime = Path(temp)
        exits = configure(runtime)
        base.generate_certificate(runtime)
        (runtime / "logs/log").mkdir(parents=True)
        (runtime / "journals/critical").mkdir(parents=True, mode=0o700)
        state = runtime / "state"
        state.mkdir(mode=0o700)
        plain, tls, ws = base.available_ports()
        env = dict(PATH=os.environ.get("PATH", "/usr/bin:/bin"), ENVIRONMENT="local",
                   PERSISTENCE_MODE="flatfile-primary", FLATFILE_STATE_DIR=str(state),
                   CRITICAL_COMMAND_JOURNAL_DIR=str(runtime / "journals/critical"),
                   LISTEN_ADDRESS="127.0.0.1", DURIS_TLS_PORT=str(tls),
                   DURIS_WEBSOCKET_LISTEN_ADDRESS="127.0.0.1", DURIS_WEBSOCKET_PORT=str(ws),
                   REDIS="FALSE", CHAOS_MUD="FALSE", DURIS_ZONE_RESET_TRACE="1")
        if "LD_LIBRARY_PATH" in os.environ:
            env["LD_LIBRARY_PATH"] = os.environ["LD_LIBRARY_PATH"]
        output_path = runtime / "server.out"
        clients, transcripts = {}, []
        process = None
        with output_path.open("w") as output:
            def boot():
                nonlocal process
                offset = output_path.stat().st_size
                process = subprocess.Popen([str(binary), "--minimal", "-s", "-d", str(runtime), str(plain)],
                                           cwd=runtime, env=env, stdout=output, stderr=subprocess.STDOUT)
                deadline = time.monotonic() + 120
                while "Entering game loop." not in output_path.read_text(errors="replace")[offset:]:
                    assert process.poll() is None and time.monotonic() < deadline, base.runtime_logs(runtime)
                    time.sleep(.1)

            def disconnect(name):
                client = clients.pop(name)
                client.close()
                transcripts.append(client.transcript)

            def stop():
                for name in list(clients):
                    disconnect(name)
                if process is not None and process.poll() is None:
                    process.send_signal(signal.SIGTERM)
                    process.wait(timeout=60)
                    assert process.returncode == 0, base.runtime_logs(runtime)

            def account(name):
                return "Acct" + name[4:]

            def source(name):
                return "127.0.0." + str(20 if name == STAFF else PLAYERS.index(name) + 2)

            def login(name):
                client = base.reconnect_character(plain, expected_room=None, account=account(name),
                                                  character=name, source_host=source(name))
                clients[name] = client
                client.expect("Pos: standing >", timeout=30)
                command(client, "toggle paging no")
                return client

            def cmd(name, text):
                return command(clients[name], text)

            def save_player():
                clients[PLAYERS[0]].send("save")
                clients[PLAYERS[0]].expect(f"Save complete for {PLAYERS[0]}.", timeout=30)
                command(clients[PLAYERS[0]], "look")

            def object_state(key):
                text = cmd(STAFF, f"stat obj {key}")
                # stat subtracts its temporary inspection object from this count.
                match = re.search(r"Number in game\s*:\s*(\d+)", text)
                assert match, text
                return int(match[1]), text

            def location(name):
                text = cmd(STAFF, "stat char " + name)
                match = re.search(r"In room: \[(\d+)\]", text)
                assert match, text
                return int(match[1])

            def place(name, room):
                cmd(STAFF, f"goto {room}")
                cmd(STAFF, f"transfer {name}")
                assert location(name) == room

            def pair_flags(gate, locked):
                _, _, _, near, direction, far, _ = gate
                for room, d in ((near, direction), (far, REVERSE[direction])):
                    text = cmd(STAFF, f"stat room {room}")
                    # Filled from the actual stat command's direction/flag rows.
                    match = re.search(r"Direction\s+" + DIRECTIONS[d] + r"\s+[^\n]*",
                                      text, re.S | re.I)
                    assert match, text
                    flags = match[0].lower()
                    assert ("locked" in flags) == locked, flags
                    assert ("secret" in flags) == (locked and gate[0] == 2436), flags

            def assert_pairs(locked, entrance=False):
                for gate in GATES:
                    pair_flags(gate, locked)
                if entrance:
                    pair_flags((2402, 2401, 2401, 2401, 0, 2402, 18), locked)

            def trace_count():
                return len(re.findall(r"ZONE RESET TRACE:.*zone_vnum=24\b", base.runtime_logs(runtime)))

            def wait_timer(reset, description):
                before = trace_count()
                deadline = time.monotonic() + 100
                while True:
                    traces = re.findall(r"ZONE RESET TRACE:.*zone_vnum=24\b[^\n]*", base.runtime_logs(runtime))
                    if len(traces) > before:
                        latest = traces[-1]
                        assert f"will_reset={int(reset)}" in latest, latest
                        if not reset:
                            age = re.search(r"age_before=(\d+) lifespan=(\d+)", latest)
                            assert age and int(age[1]) + 1 >= int(age[2]), latest
                        report.setdefault("timer_events", []).append({"case": description, "trace": latest})
                        cmd(STAFF, "look")  # a command after the callback fences reset completion
                        print("castle journey: " + description, flush=True)
                        return
                    assert process.poll() is None and time.monotonic() < deadline, base.runtime_logs(runtime)
                    time.sleep(.5)

            def walk_out(name, start):
                route = escape_route(start, exits)
                assert location(name) == start
                for d, target, is_door in route:
                    if is_door:
                        opened = cmd(name, "open " + DIRECTIONS[d])
                        assert "seems to be locked" not in opened.lower(), opened
                    moved = cmd(name, DIRECTIONS[d])
                    assert location(name) == target, moved
                assert location(name) == 5760
                return [start] + [target for _, target, _ in route]

            try:
                boot()
                for name in PLAYERS + (STAFF,):
                    client = base.MudClient(plain, source_host=source(name))
                    clients[name] = client
                    base.create_character(client, account=account(name), character=name,
                                          email=name.lower() + "@example.invalid")
                    client.send("save")
                    client.expect(f"Save complete for {name}.", timeout=30)
                    print(f"castle journey: created {name}", flush=True)
                stop()
                base.make_overlord(state, STAFF)
                boot()
                for name in PLAYERS + (STAFF,):
                    login(name)
                for name in PLAYERS:
                    cmd(STAFF, f"setbit char {name} mxvit 30000")
                    cmd(STAFF, f"setbit char {name} vit 30000")
                assert_pairs(True, entrance=True)
                print("castle journey: cold boot retains all authored gate states", flush=True)
                # Retire each source and give its one real key to the first mortal.
                for gate, alias in zip(GATES, ALIASES):
                    key, _, home, *_ = gate
                    cmd(STAFF, f"goto {home}")
                    purged = cmd(STAFF, "purge " + alias)
                    assert "not" not in purged.split("Score information")[0].lower(), purged
                    # NPC extraction drops ordinary belongings into this room.
                    # Take that original key; loading another would create a duplicate.
                    taken = cmd(STAFF, "get key")
                    assert "You get" in taken, taken
                    cmd(STAFF, "goto 22800")
                    given = cmd(STAFF, f"give key {PLAYERS[0]}")
                    assert "Ok." in given, given
                save_player()
                for gate in GATES:
                    count, text = object_state(gate[0])
                    assert count == 1 and PLAYERS[0] in text, text
                print("castle journey: all seven live keys verified on the mortal", flush=True)
                wait_timer(True, "empty reset with seven held keys")
                assert_pairs(False)
                carrier_ids = {}
                for gate, alias in zip(GATES, ALIASES):
                    key, _, _, near, direction, _, _ = gate
                    text = cmd(STAFF, "stat char " + alias)
                    match = re.search(r"(\d+)-I\s+# in game:\s*1", text)
                    assert match, text
                    carrier_ids[key] = match[1]
                    place(PLAYERS[0], near)
                    for verb in ("close", "lock"):
                        cmd(PLAYERS[0], verb + " " + DIRECTIONS[direction])
                    unlocked = cmd(PLAYERS[0], "unlock " + DIRECTIONS[direction])
                    assert "*click*" in unlocked and "broke your key" in unlocked.lower(), unlocked
                    save_player()
                    count, text = object_state(key)
                    assert count == 0, text
                    report["key_sequences"].append({"key": key, "before_count": 1,
                                                     "after_count": count,
                                                     "carrier_id": carrier_ids[key]})
                place(PLAYERS[0], 22800)
                cmd(STAFF, "goto 22800")
                wait_timer(True, "empty reset after all seven keys were consumed")
                assert_pairs(False)
                for gate, alias in zip(GATES, ALIASES):
                    text = cmd(STAFF, "stat char " + alias)
                    assert f"{carrier_ids[gate[0]]}-I" in text and "# in game: 1" in text, text
                save_player()
                for gate in GATES:
                    count, text = object_state(gate[0])
                    assert count == 0, text
                # Dead-source control restores normal locks and source keys.
                for gate, alias in zip(GATES, ALIASES):
                    cmd(STAFF, f"goto {gate[2]}")
                    cmd(STAFF, "purge " + alias)
                cmd(STAFF, "goto 22800")
                wait_timer(True, "dead carriers and absent keys reload normally")
                assert_pairs(True, entrance=True)
                for name, gate in zip(PLAYERS, GATES):
                    place(name, gate[5])
                cmd(STAFF, "goto 22800")
                wait_timer(False, "connected party blocks due mode-1 reset")
                assert_pairs(True, entrance=True)
                for name in PLAYERS:
                    disconnect(name)
                wait_timer(True, "descriptorless player bodies permit reset and retain escape")
                assert_pairs(False, entrance=True)
                for name, gate in zip(PLAYERS, GATES):
                    login(name)
                    route = walk_out(name, gate[5])
                    report["routes"].append({"character": name, "key": gate[0], "rooms": route})
                    print(f"castle journey: {name} escaped {gate[5]} -> 5760 ({len(route)-1} steps)", flush=True)
                # Staff resets cannot close the escape route around a connected mortal.
                for mode, start in (("ok", 2415), ("full", 2479)):
                    place(PLAYERS[0], start)
                    result = cmd(STAFF, "zreset " + mode)
                    assert "has been reset" in result, result
                    assert_pairs(False, entrance=True)
                    walk_out(PLAYERS[0], start)
                    cmd(STAFF, "goto 22800")
                    report.setdefault("staff_resets", []).append(mode)
                wait_timer(True, "empty stocked castle restores progression locks")
                assert_pairs(True, entrance=True)
                report["result"] = "passed"
                (evidence / "gameplay-report.json").write_text(json.dumps(report, indent=2) + "\n")
                print(json.dumps(report, indent=2), flush=True)
            except Exception:
                print(output_path.read_text(errors="replace")[-6000:], flush=True)
                print(base.runtime_logs(runtime)[-12000:], flush=True)
                for name, client in clients.items():
                    print(name + ":\n" + client.transcript.decode(errors="replace")[-4000:], flush=True)
                raise
            finally:
                stop()
                (evidence / "gameplay-transcript.txt").write_bytes(b"\n".join(transcripts))
                (evidence / "gameplay-server.log").write_text(base.runtime_logs(runtime))


if __name__ == "__main__":
    build_root = ROOT / "bin/tests"
    build_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="castle-build-", dir=build_root) as temp:
        build = Path(temp)
        binary = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else base.build_flatfile_server(build)
        run(binary)
