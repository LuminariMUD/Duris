#!/usr/bin/env python3
"""Real headbutt dispatch and three-recipient output on a disposable server.

Only synthetic SQL character rows are prepared offline. Combat, RNG, wards, raw damage,
terse filtering and output use the unchanged server implementation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import select
import subprocess
import time

from _paths import ROOT
from test_account_recovery_journey import IsolatedServer, OLD_PASSWORD, require
from test_character_stat_choice_journey import WebSocketClient
from test_creation_prompt_journey import reboot


NAMES = ("Headbutter", "Wardtarget", "Wardwitness")
ACCOUNTS = ("Buttjourney", "Wardjourney", "Seejourney")
ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def fixture(run_root):
    path = run_root / "areas_mini/mini.wld"
    rooms = """#22800
The Headbutt Regression Arena~
A quiet room for disposable headbutt qualification.
~
1 0 0
S
#22801
The Headbutt Observation Room~
A quiet room outside combat.
~
1 0 0
S
$~"""
    path.write_text(path.read_text().replace("$~", rooms))
    path = run_root / "areas_mini/mini.zon"
    path.write_text(path.read_text().replace("1299 0 0 6 11 1", "29999 0 0 6 11 1"))


def prepare_character(sql, name, learned, double, capacity, terse):
    """One synthetic fighter or observer; normal skill floors depend on the level chosen here."""
    pid = sql(f"SELECT pid FROM player_data WHERE name='{name}'")
    # Normal skill floors would raise a level-56 failure fixture to 40,
    # and grant double headbutt even when its saved learned value is zero.
    level = 62 if name == "Wardwitness" else 3 if learned == 4 else 56 if double else 55
    statements = [
        f"UPDATE player_data SET level={level},highest_level={level},m_class={1 << 14},spec=0,base_str=180,"
        f"base_agi=100,base_luk=0,base_hit=10000,hit_diff=0,act=0,act2={64 if terse else 0},wiz_invis=0,"
        f"screen_length=200,last_room=22800 WHERE pid={pid}"]
    statements += [f"DELETE FROM {table} WHERE pid={pid}" for table in
                   ("player_items", "player_affects", "player_timers", "player_skills", "player_intros")]
    statements.append(f"DELETE FROM player_pets WHERE owner_pid={pid}")
    if name == "Headbutter":
        statements.append(f"INSERT INTO player_skills(pid,skill_id,learned,taught) VALUES({pid},1021,{learned},100),"
                          f"({pid},1195,{double},100)")
    if capacity:
        statements.append(f"INSERT INTO player_affects(pid,type,duration,flags,modifier) "
                          f"VALUES({pid},674,6000,{1 | 1 << 13},{capacity})")
    statements += [f"INSERT INTO player_intros(pid,intro_index,intro_pid,intro_time) "
                   f"VALUES({pid},{other - 1},{other},NOW())" for other in range(1, 4)]
    sql(";".join(statements))


def drain(clients, seconds=.2):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        buffered = [c for c in clients if c.buffer]
        ready, _, _ = select.select([c.socket for c in clients], [], [], .02)
        for client in clients:
            if client in buffered or client.socket in ready:
                client.receive()


def text(client, after=0):
    return ANSI.sub("", "".join(m["data"] for m in client.messages[after:]
                               if m.get("type") == "text" and isinstance(m.get("data"), str)))


def game(client, command, needle):
    before = len(client.messages)
    client.send_frame(1, json.dumps({"type": "cmd", "cmd": "game", "data": command}).encode())
    deadline = time.monotonic() + 15
    while needle not in text(client, before):
        require(time.monotonic() < deadline, f"{command}: missing {needle!r}: {text(client, before)}")
        client.receive()
    return text(client, before)


def create(server):
    for index, name in enumerate(NAMES):
        client = WebSocketClient(server.websocket_port)
        try:
            auth = client.command("register", {"account": ACCOUNTS[index], "password": OLD_PASSWORD,
                                              "email": "headbutt@example.invalid"}, "auth")
            require(auth.get("status") == "success", f"synthetic registration failed: {auth}")
            options = client.command("chargen_options")
            race = next(r for r in options["races"] if r["id"] == 1)
            warrior = next(c for c in race["classes"] if c["name"].lower() == "warrior")
            homes = client.command("get_hometowns", {"race": 1}, "hometowns")
            client.command("roll_stats", {"race": 1, "method": "default"})
            for stat in ("str", "dex", "agi", "luk"):
                client.command("add_bonus", {"stat": stat}, "bonus_added")
            result = client.command("create_character", {"name": name, "race": 1, "class": warrior["id"],
                "sex": 1, "alignment": "good", "hometown": homes["options"][0]["id"], "newbie": True})
            require(result["status"] == "created", f"synthetic creation failed: {result}")
            client.enter_created_character(name)
            game(client, "save", f"Saving {name}.")
        finally:
            client.close()
    server.shutdown()


def connect(server):
    clients = []
    for index, name in enumerate(NAMES):
        client = WebSocketClient(server.websocket_port)
        clients.append(client)
        client.command("login", {"account": ACCOUNTS[index], "password": OLD_PASSWORD}, "auth")
        client.command("enter", {"character": name}, "gmcp")
    drain(clients)
    return clients


def stats(client, name):
    value = game(client, f"stat char {name}", "Hits:")
    hp = re.search(r"Hits:\s*\[\s*(\d+)\s*/\s*(\d+)", value)
    require(hp is not None, f"stat omitted HP: {value}")
    ward = re.search(r"by\s+(-?\d+)\s+for\s+\d+\s+from\s+'guardian ward'", value)
    return {"hp": int(hp[1]), "max_hp": int(hp[2]), "ward": int(ward[1]) if ward else 0,
            "text": value}


def attempt(server, mode, terse, double):
    capacities = {"Headbutter": 1000 if mode == "backfire" else 0,
                  "Wardtarget": 1000 if mode in ("full", "double") else 8 if mode == "partial" else 0,
                  "Wardwitness": 0}
    for name in NAMES:
        prepare_character(server.sql, name, 4 if mode == "backfire" else 100,
                          100 if double else 0, capacities[name], terse)
    reboot(server)
    deadline = time.monotonic() + 60
    while "Entering game loop." not in server.server_output():
        require(server.process.poll() is None and time.monotonic() < deadline, server.server_output()[-5000:])
        time.sleep(.05)
    clients = connect(server)
    actor, victim, witness = clients
    try:
        before = {name: stats(witness, name) for name in NAMES[:2]}
        if mode in ("full", "double", "partial"):
            require(before["Wardtarget"]["ward"] == (8 if mode == "partial" else 1000),
                    f"fixture ward was not restored or observed: {before}")
        if mode == "backfire":
            require(before["Headbutter"]["ward"] == 1000, f"backfire ward missing: {before}")
        drain(clients)
        marks = [len(c.messages) for c in clients]
        actor.send_frame(1, json.dumps({"type": "cmd", "cmd": "game", "data": "headbutt Wardtarget"}).encode())
        drain(clients, .2)
        outputs = {name: text(c, mark) for name, c, mark in zip(NAMES, clients, marks)}
        after = {name: stats(witness, name) for name in NAMES[:2]}
        drain(clients, .1)
        return {"mode": mode, "terse": terse, "double": double, "before": before,
                "after": after, "output": outputs}
    finally:
        for client in clients:
            client.close()
        server.shutdown()


def run(binary, evidence, baseline):
    records = []
    with IsolatedServer(binary, {"DURIS_WEBSOCKET": "TRUE"}, fixture) as server:
        try:
            create(server)
            for mode, terse in (("full", False), ("full", True), ("partial", False),
                                ("ordinary", False), ("backfire", True), ("double", True)):
                accepted = None
                for _ in range(30):
                    record = attempt(server, mode, terse, mode == "double")
                    records.append(record)
                    actor = record["output"]["Headbutter"]
                    backfire = (record["after"]["Headbutter"]["ward"] < record["before"]["Headbutter"]["ward"]
                                and record["after"]["Wardtarget"]["hp"] == record["before"]["Wardtarget"]["hp"])
                    if mode == "backfire":
                        if not backfire:
                            continue
                        require(record["after"]["Headbutter"]["hp"] == record["before"]["Headbutter"]["hp"],
                                f"warded backfire changed attacker HP: {record}")
                    elif "Ouch, that seriously hurt!" in actor or "backfires" in actor:
                        continue
                    if mode == "double" and "deftly pull back your head" not in actor:
                        continue
                    if mode in ("full", "double"):
                        before, after = record["before"]["Wardtarget"], record["after"]["Wardtarget"]
                        if after["ward"] == before["ward"]:
                            raise AssertionError(f"headbutt did not reach the prepared ward: {record}")
                        require(after["hp"] == before["hp"] and 0 < after["ward"] < before["ward"],
                                f"full ward changed HP or was not consumed: {record}")
                    if mode in ("ordinary", "partial"):
                        require(record["after"]["Wardtarget"]["hp"] < record["before"]["Wardtarget"]["hp"],
                                f"ordinary hit did not damage target: {record}")
                    zero = mode in ("full", "double", "backfire")
                    for name, output in record["output"].items():
                        require(("does no damage" in output) == (zero and not baseline),
                                f"wrong feedback for {name}: {record}")
                    if mode == "full" and terse and baseline:
                        require("ward around" not in actor.lower() and "headbutt" not in actor.lower(),
                                f"baseline terse absorption was not silent: {record}")
                    accepted = record
                    record["qualified"] = True
                    print(f"PASS booted {mode}, terse={terse}: actual command, ward/HP and three recipients", flush=True)
                    break
                require(accepted is not None, f"no qualifying {mode} in 30 real attempts")
        finally:
            evidence.write_text(json.dumps({"baseline": baseline, "binary": str(binary),
                "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
                "source_sha256": {str(p): hashlib.sha256(subprocess.check_output(
                    ["git", "show", "0a972227636b66c4e0c98900b1120c25ac181353:" + p], cwd=ROOT)
                    if baseline else (ROOT/p).read_bytes()).hexdigest()
                    for p in ("src/cmd/actoff.c", "src/combat/fight.c", "src/net/comm.c")},
                "attempts": records}, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", type=Path, required=True, help="Explicit fresh qualification binary")
    parser.add_argument("--baseline", action="store_true", help="Qualify the pre-fix binary's missing feedback")
    args = parser.parse_args()
    build = ROOT / "bin/qualification/issue505"
    build.mkdir(parents=True, exist_ok=True)
    run(args.server.resolve(), build / ("baseline-journey.json" if args.baseline else "journey.json"), args.baseline)


if __name__ == "__main__":
    main()
