#!/usr/bin/env python3
"""Real headbutt dispatch and three-recipient output on a disposable server.

Only synthetic snapshots are prepared offline. Combat, RNG, wards, raw damage,
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
import tempfile
import time

from _paths import ROOT
from test_account_recovery_journey import IsolatedServer, OLD_PASSWORD, build_flatfile_server, require
from test_character_stat_choice_journey import WebSocketClient
from test_creation_prompt_journey import reboot
from test_flatfile_combat_journey import OVERLORD_FIXTURE


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


def compile_editor(build):
    """Reuse the maintained snapshot writer; customize only its offline fixture."""
    source = OVERLORD_FIXTURE.replace("#include <cstdio>", '#include <cstdio>\n#include <ctime>\n#include "core/prototypes.h"\n#include "core/utils.h"\n#include "magic/spells.h"')
    source = source.replace("argc != 3", "argc != 7")
    start, end = source.index("        for (auto &field"), source.index("        std::vector<uint8_t> payload")
    source = source[:start] + r'''
        const bool observer = !strcmp(argv[2], "Wardwitness");
        const bool actor = !strcmp(argv[2], "Headbutter");
        // Normal skill floors would raise a level-56 failure fixture to 40,
        // and grant double headbutt even when its saved learned value is zero.
        const int level = atoi(argv[3]) == 4 ? 3 : atoi(argv[4]) ? 56 : 55;
        for (auto &field : snapshot.status_integers) {
            using F = player_status_field;
            auto assign = [&](int value) { field.signed_value = value; field.unsigned_value = value; };
            if (field.field == F::level || field.field == F::highest_level) assign(observer ? 62 : level);
            if (field.field == F::class_primary) assign(CLASS_MERCENARY);
            if (field.field == F::specialization) assign(0);
            if (field.field == F::base_strength) assign(180);
            if (field.field == F::base_agility) assign(100);
            if (field.field == F::base_luck) assign(0);
            if (field.field == F::base_hit) assign(10000);
            if (field.field == F::hit_difference) assign(0);
            if (field.field == F::action_flags) assign(0);
            if (field.field == F::action_flags_2) assign(atoi(argv[6]) ? PLR2_TERSE : 0);
            if (field.field == F::wizard_invisibility) assign(0);
            if (field.field == F::screen_length) assign(200);
        }
        snapshot.room_vnum = 22800;
        snapshot.items.clear(); snapshot.pets.clear(); snapshot.affects.clear(); snapshot.timers.clear();
        snapshot.skills.clear(); snapshot.introductions.clear();
        if (actor) {
            snapshot.skills.push_back({SKILL_HEADBUTT, static_cast<uint8_t>(atoi(argv[3])), 100});
            snapshot.skills.push_back({SKILL_DOUBLE_HEADBUTT, static_cast<uint8_t>(atoi(argv[4])), 100});
        }
        int capacity = atoi(argv[5]);
        if (capacity) {
            player_affect_snapshot ward{};
            ward.type = SPELL_GUARDIAN_WARD; ward.duration = 6000;
            ward.flags = AFFTYPE_SHORT | AFFTYPE_DAM_WARD; ward.modifier = capacity;
            snapshot.affects.push_back(ward);
        }
        for (int other = 1; other <= 3; ++other)
            snapshot.introductions.push_back({other - 1, other, static_cast<uint64_t>(time(nullptr))});
''' + source[end:]
    cpp, binary = build / "snapshot-fixture.cpp", build / "snapshot-fixture"
    cpp.write_text(source)
    subprocess.run(["g++", "-std=c++20", "-Isrc", str(cpp),
                    "src/player/player_snapshot_codec.c", "src/flatfile/flatfile_player_snapshot_file.c",
                    "src/flatfile/flatfile_store.c", "-lcrypto", "-o", str(binary)], cwd=ROOT, check=True)
    return binary


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
            game(client, "save", f"Save complete for {name}.")
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


def attempt(server, editor, mode, terse, double):
    capacities = {"Headbutter": 1000 if mode == "backfire" else 0,
                  "Wardtarget": 1000 if mode in ("full", "double") else 8 if mode == "partial" else 0,
                  "Wardwitness": 0}
    for name in NAMES:
        subprocess.run([str(editor), str(server.state_root), name, "4" if mode == "backfire" else "100",
                        "100" if double else "0", str(capacities[name]), str(int(terse))], check=True)
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


def run(binary, editor, evidence, baseline):
    records = []
    with IsolatedServer(binary, {"DURIS_WEBSOCKET": "TRUE"}, fixture) as server:
        try:
            create(server)
            for mode, terse in (("full", False), ("full", True), ("partial", False),
                                ("ordinary", False), ("backfire", True), ("double", True)):
                accepted = None
                for _ in range(30):
                    record = attempt(server, editor, mode, terse, mode == "double")
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
    parser.add_argument("--server", type=Path, help="Explicit fresh qualification binary")
    parser.add_argument("--baseline", action="store_true", help="Qualify the pre-fix binary's missing feedback")
    args = parser.parse_args()
    build = ROOT / "bin/qualification/issue505"
    build.mkdir(parents=True, exist_ok=True)
    binary = args.server.resolve() if args.server else build_flatfile_server(
        Path(tempfile.mkdtemp(prefix="journey-build-", dir=build)))
    fixture_build = build / ("baseline-fixture" if args.baseline else "fixture")
    fixture_build.mkdir(exist_ok=True)
    run(binary, compile_editor(fixture_build), build / ("baseline-journey.json" if args.baseline else "journey.json"), args.baseline)


if __name__ == "__main__":
    main()
