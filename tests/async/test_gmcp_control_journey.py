#!/usr/bin/env python3
"""Booted lifecycle/time and combat state through normal protocol dispatch.

Uses maintained isolated state, creation, staff promotion and reboot helpers.
--server reuses an explicitly built client-free flatfile binary. No checkout
.env, existing game process, real account or production database is used.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import tempfile
import time

from test_account_recovery_journey import ACCOUNT, OLD_PASSWORD, ROOT, IsolatedServer, MudClient, build_flatfile_server, require
from test_game_loop_session_journey import CHARACTER, create_character, reconnect_character
from test_creation_prompt_journey import reboot, start_character, reply, finish_character_choices
from test_flatfile_combat_journey import make_overlord
from test_character_stat_choice_journey import WebSocketClient


GMCP_FRAME = re.compile(rb"\xff\xfa\xc9(.*?)\xff\xf0", re.S)
SUPPORT = ["Duris.Capabilities 1", "Duris.Time 1", "Duris.Session 1"]
SECOND_CHARACTER = "Secondphase"


def telnet_packets(client):
    packets = []
    for match in GMCP_FRAME.finditer(client.transcript):
        package, payload = match[1].split(b" ", 1)
        packets.append((package.decode(), json.loads(payload)))
    return packets


def send_telnet(client, package, data):
    payload = package.encode() + b" " + json.dumps(data).encode()
    client.socket.sendall(b"\xff\xfa\xc9" + payload + b"\xff\xf0")


def wait_telnet(client, package, after=0, predicate=lambda data: True, timeout=8):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for name, data in telnet_packets(client)[after:]:
            if name == package and predicate(data):
                return data
        client._receive()
    raise AssertionError(f"no {package} after packet {after}: {telnet_packets(client)[-5:]}")


def drain(client, seconds=1.1):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        client._receive()


def negotiate(client):
    client.socket.sendall(b"\xff\xfd\xc9")
    send_telnet(client, "Core.Supports.Set", SUPPORT)
    send_telnet(client, "Duris.Subscribe", ["Duris.Time 1"])
    wait_telnet(client, "Duris.Capabilities")


def wait_websocket(client, package, predicate=lambda data: True, after=0):
    deadline = time.monotonic() + 10
    index = after
    while time.monotonic() < deadline:
        for message in client.messages[index:]:
            if message.get("type") == "gmcp" and message.get("package") == package and predicate(message.get("data")):
                return message["data"]
        index = len(client.messages)
        client.receive()
    raise AssertionError(f"no WebSocket {package}")


def send_websocket(client, package, data):
    client.send_frame(1, json.dumps({"type": "gmcp", "package": package, "data": data}).encode())


def combat_fixture(run_root):
    """Two durable-free NPCs for a real non-GMCP tank and terminal extraction."""
    mini = run_root / "areas_mini"
    path = mini / "mini.mob"
    mobs = path.read_text()
    for vnum, name in ((22800, "foe"), (22801, "ally")):
        mob = f"""#{vnum}
{name} regression~
the regression {name}~
The regression {name} waits here.
~
~
10 0 0 0 0 0 0 0 S
PH 0 0 -1
10 0 100 1000d1+99000 1d1+0
0.0.0.0 0
8 8 0
"""
        mobs = mobs.replace("$~", mob + "$~")
    path.write_text(mobs)
    path = mini / "mini.wld"
    path.write_text(path.read_text().replace("$~", """#22800
The GMCP Regression Arena~
A quiet room for the disposable combat wire journey.
~
1 0 0
S
$~"""))
    path = mini / "mini.zon"
    zone = path.read_text()
    require("1299 0 0 6 11 1" in zone, "minimal zone header changed")
    path.write_text(zone.replace("1299 0 0 6 11 1", "29999 0 0 6 11 1"))


def combat_journey(client):
    client.send("goto 22800")
    client.expect("The GMCP Regression Arena")
    for vnum in (22800, 22801):
        client.send(f"load mob {vnum}")
        client.expect("You have created")
    send_telnet(client, "Core.Supports.Add", ["Duris.Combat 1"])
    wait_telnet(client, "Duris.Capabilities", predicate=lambda state: "Duris.Combat" in state["supported"])
    send_telnet(client, "Duris.Subscribe", ["Duris.Time 1", "Duris.Combat 1"])
    wait_telnet(client, "Duris.Capabilities", predicate=lambda state: "Duris.Combat" in state["active"])
    client.send("force foe kill ally")
    before = len(telnet_packets(client))
    client.send("hit foe")
    fighting = wait_telnet(client, "Combat.Update", before, lambda state:
        (state.get("target") or {}).get("name") == "foe" and
        (state.get("tank") or {}).get("name") == "ally")
    event = wait_telnet(client, "Duris.Combat", before, lambda state: state["target"] == "foe")
    require(event["damage"] > 0 and event["damageType"] == "physical" and
            isinstance(event["critical"], bool), "authoritative melee metadata missing")
    require(not any(name == "Combat.Update" and "round" in state
                    for name, state in telnet_packets(client)[before:]), "damage event duplicated a legacy round")
    require(0 <= fighting["target"]["healthPercent"] <= 100 and
            0 <= fighting["tank"]["healthPercent"] <= 100,
            "combat subject percentages are invalid")
    before = len(telnet_packets(client))
    client.send("purge ally")
    departed = wait_telnet(client, "Combat.Update", before, lambda state:
        (state.get("tank") or {}).get("name") != "ally")
    before = len(telnet_packets(client))
    client.send("purge foe")
    cleared = wait_telnet(client, "Combat.Update", before, lambda state:
        state.get("target") is None and state.get("tank") is None)
    send_telnet(client, "Duris.Subscribe", ["Duris.Time 1"])
    wait_telnet(client, "Duris.Capabilities", predicate=lambda state: state["active"] == ["Duris.Time"])
    return [fighting, departed, cleared, event]


def item_journey(client):
    drain(client)  # Respect the existing independent control token buckets.
    before = len(telnet_packets(client))
    send_telnet(client, "Core.Supports.Add", ["Char.Items 1"])
    wait_telnet(client, "Duris.Capabilities", before, lambda state: "Char.Items" in state["supported"])
    send_telnet(client, "Duris.Subscribe", ["Duris.Time 1", "Char.Items 1"])
    def snapshot(location, after, predicate=lambda state: True):
        return wait_telnet(client, "Char.Items.List", after, lambda state:
            state["location"] == location and state["complete"] and predicate(state))
    initial = snapshot("inv", before)
    snapshot("eq", before)
    before = len(telnet_packets(client))
    for _ in range(3):
        client.send("load obj 15")
        client.expect("You have created")
    loaded = snapshot("inv", before, lambda state:
        sum("banana" in row["description"] for row in state["items"]) >= 3)
    bananas = [row for row in loaded["items"] if "banana" in row["description"]]
    require(bananas[0]["selector"] != bananas[1]["selector"], "duplicate objects share a selector")
    before = len(telnet_packets(client))
    client.send("drop " + bananas[0]["selector"])
    dropped = snapshot("inv", before, lambda state:
        sum("banana" in row["description"] for row in state["items"]) == len(bananas) - 1)
    require(int(dropped["revision"]) > int(loaded["revision"]), "drop did not replace inventory")
    before = len(telnet_packets(client))
    client.send("drop " + bananas[0]["selector"])
    client.send("inventory")
    client.expect("You are carrying:")
    drain(client)
    require(not any(name == "Char.Items.List" and int(state["revision"]) > int(dropped["revision"])
                    for name, state in telnet_packets(client)[before:]), "stale selector caused a mutation")
    before = len(telnet_packets(client))
    client.send("load obj 677")
    client.expect("You have created")
    carrying_mace = snapshot("inv", before, lambda state:
        any("small wooden mace" in row["description"] for row in state["items"]))
    mace = next(row for row in carrying_mace["items"] if "small wooden mace" in row["description"])
    before = len(telnet_packets(client))
    client.send("wield " + mace["selector"])
    equipped = snapshot("eq", before, lambda state:
        any("small wooden mace" in row["description"] for row in state["items"]))
    worn = next(row for row in equipped["items"] if "small wooden mace" in row["description"])
    require(isinstance(worn["slot"], int), "equipment lost its worn slot")
    before = len(telnet_packets(client))
    client.send("remove " + worn["selector"])
    removed = snapshot("eq", before, lambda state:
        not any("small wooden mace" in row["description"] for row in state["items"]))

    latest = next(state for name, state in reversed(telnet_packets(client))
                  if name == "Char.Items.List" and state["location"] == "inv" and state["complete"])
    mace = next(row for row in latest["items"] if "small wooden mace" in row["description"])
    before = len(telnet_packets(client))
    client.send("string obj " + mace["selector"] + " short a renamed wooden mace&+")
    renamed = snapshot("inv", before, lambda state:
        any(row["description"] == "a renamed wooden mace&+" for row in state["items"]))
    mace = next(row for row in renamed["items"] if "renamed wooden mace" in row["description"])
    client.send("string obj " + mace["selector"] + " short")
    client.expect("Enter string")
    before = len(telnet_packets(client))
    client.send("an edited wooden mace")
    drain(client)
    require(not any(name == "Char.Items.List" and any("edited wooden mace" in row["description"]
                        for row in state["items"]) for name, state in telnet_packets(client)[before:]),
            "partial editor text was published")
    client.send("/s")
    edited = snapshot("inv", before, lambda state:
        any(row["description"].strip() == "an edited wooden mace" for row in state["items"]))
    snapshot("eq", before)
    def latest_item(fragment):
        state = next(state for name, state in reversed(telnet_packets(client))
                     if name == "Char.Items.List" and state["location"] == "inv" and state["complete"])
        return next(row for row in state["items"] if fragment in row["description"])

    def nested(selector, available, count):
        snapshot("eq", 0)  # Both top-level pages must be complete before requesting contents.
        drain(client)
        after = len(telnet_packets(client))
        send_telnet(client, "Char.Items.Get", [selector])
        state = snapshot(selector, after)
        require(state["available"] == available and len(state["items"]) == count,
                f"wrong nested contents: {state}")
        return state

    # Real container gates and nested selectors, using ordinary put/get dispatch.
    before = len(telnet_packets(client))
    client.send("load obj 380")
    client.expect("You have created")
    snapshot("inv", before, lambda state: any("small wooden chest" in row["description"] for row in state["items"]))
    before = len(telnet_packets(client))
    client.send("close chest")
    snapshot("inv", before)
    snapshot("eq", before)
    chest = latest_item("small wooden chest")
    closed = nested(chest["selector"], False, 0)
    before = len(telnet_packets(client))
    client.send("open " + chest["selector"])
    opened = snapshot("inv", before)
    snapshot("eq", before)
    require(int(opened["revision"]) > int(closed["revision"]), "open did not retire the closed view")
    nested(latest_item("small wooden chest")["selector"], True, 0)
    before = len(telnet_packets(client))
    client.send("load obj 379")
    client.expect("You have created")
    snapshot("inv", before, lambda state: any("large iron box" in row["description"] for row in state["items"]))
    before = len(telnet_packets(client))
    client.send("open box")
    snapshot("inv", before)
    snapshot("eq", before)
    before = len(telnet_packets(client))
    client.send("put all.banana box")
    packed = snapshot("inv", before, lambda state: not any("banana" in row["description"] for row in state["items"]))
    snapshot("eq", before)
    before = len(telnet_packets(client))
    client.send("put box chest")
    snapshot("inv", before, lambda state: not any("large iron box" in row["description"] for row in state["items"]))
    snapshot("eq", before)
    contents = nested(latest_item("small wooden chest")["selector"], True, 1)
    inner_selector = contents["items"][0]["selector"]
    inner_contents = nested(inner_selector, True, len(bananas) - 1)
    require(all("banana" in row["description"] for row in inner_contents["items"]), "nested selector returned another owner's data")
    before = len(telnet_packets(client))
    client.send("close chest")
    snapshot("inv", before)
    snapshot("eq", before)
    # Stale nested selectors never resolve against another duplicate after access change.
    client.send("drop " + inner_contents["items"][0]["selector"])
    drain(client)
    before = len(telnet_packets(client))
    client.send("open chest")
    snapshot("inv", before)
    snapshot("eq", before)
    before = len(telnet_packets(client))
    client.send("get all chest")
    snapshot("inv", before, lambda state: any("large iron box" in row["description"] for row in state["items"]))
    snapshot("eq", before)
    box = latest_item("large iron box")
    selectable = nested(box["selector"], True, len(bananas) - 1)
    before = len(telnet_packets(client))
    client.send("get " + selectable["items"][0]["selector"] + " " + box["selector"])
    snapshot("inv", before, lambda state: sum("banana" in row["description"] for row in state["items"]) == 1)
    snapshot("eq", before)
    before = len(telnet_packets(client))
    client.send("put banana box")
    snapshot("inv", before, lambda state: not any("banana" in row["description"] for row in state["items"]))
    snapshot("eq", before)
    before = len(telnet_packets(client))
    client.send("get all box")
    unpacked = snapshot("inv", before, lambda state:
        sum("banana" in row["description"] for row in state["items"]) == len(bananas) - 1)
    snapshot("eq", before)
    drain(client)
    require(len({state["revision"] for name, state in telnet_packets(client)[before:]
                 if name == "Char.Items.List"}) == 1, "get-all published a partial bulk revision")
    # A native wear/remove and transfer exercise the actual ownership/slot paths.
    before = len(telnet_packets(client))
    client.send("load obj 450")
    client.expect("You have created")
    snapshot("inv", before, lambda state: any("rugged leather cap" in row["description"] for row in state["items"]))
    before = len(telnet_packets(client))
    client.send("wear " + latest_item("rugged leather cap")["selector"])
    cap_equipped = snapshot("eq", before, lambda state: any("rugged leather cap" in row["description"] for row in state["items"]))
    cap = next(row for row in cap_equipped["items"] if "rugged leather cap" in row["description"])
    before = len(telnet_packets(client))
    client.send("remove " + cap["selector"])
    snapshot("inv", before, lambda state: any("rugged leather cap" in row["description"] for row in state["items"]))
    snapshot("eq", before)
    client.send("load mob 22801")
    client.expect("You have created")
    before = len(telnet_packets(client))
    client.send("give " + latest_item("banana")["selector"] + " ally")
    given = snapshot("inv", before, lambda state:
        sum("banana" in row["description"] for row in state["items"]) == len(bananas) - 2)
    snapshot("eq", before)
    before = len(telnet_packets(client))
    client.send("switch ally")
    received = snapshot("inv", before, lambda state: any("banana" in row["description"] for row in state["items"]))
    snapshot("eq", before)
    before = len(telnet_packets(client))
    client.send("return")
    client.expect("You return to your original body.")
    snapshot("inv", before, lambda state: any("edited wooden mace" in row["description"] for row in state["items"]))
    snapshot("eq", before)
    before = len(telnet_packets(client))
    client.send("save")
    client.expect(f"Save complete for {CHARACTER}.")
    drain(client)
    require(not any(name == "Char.Items.List" for name, _ in telnet_packets(client)[before:]),
            "ordinary save invented an item revision")
    send_telnet(client, "Duris.Subscribe", ["Duris.Time 1"])
    wait_telnet(client, "Duris.Capabilities", before, lambda state: state["active"] == ["Duris.Time"])
    return {"initial": initial, "loaded": loaded, "dropped": dropped,
            "equipped": equipped, "removed": removed, "renamed": renamed, "edited": edited, "closed": closed, "contents": contents,
            "inner_contents": inner_contents, "packed": packed, "unpacked": unpacked,
            "cap_equipped": cap_equipped, "given": given, "received": received}


def run(binary, evidence):
    with IsolatedServer(binary, {"DURIS_WEBSOCKET": "TRUE"}, combat_fixture) as server:
        client = None
        websocket = None
        try:
            client = MudClient(server.plain_port)
            negotiate(client)
            account = wait_telnet(client, "Duris.Session", predicate=lambda state: state["state"] == "account")
            require(account["generation"] == "0" and account["character"] is None, "pre-entry identity was exposed")
            require(not any(name == "Duris.Time" for name, _ in telnet_packets(client)), "time leaked before character entry")
            create_character(client)
            first = wait_telnet(client, "Duris.Time")
            entry = wait_telnet(client, "Duris.Session", predicate=lambda state: state["state"] == "playing")
            require(entry["context"] == account["context"] and entry["generation"] == "1", "entry did not advance one generation")
            require(entry["character"]["name"] == CHARACTER and not entry["resumed"], "wrong attached identity")
            sessions = [data for name, data in telnet_packets(client) if name == "Duris.Session"]
            require(any(state["state"] == "chargen" and state["character"] is None for state in sessions), "chargen boundary missing")
            require(all(state["generation"] == "0" for state in sessions if state["state"] != "playing"), "chargen advanced entry generation")
            packet_names = [name for name, _ in telnet_packets(client)]
            require(packet_names.index("Duris.Session") < packet_names.index("Char.Vitals"), "initial character data overtook session")
            require(0 <= first["hour"] <= 23 and isinstance(first["revision"], str), "invalid initial clock")
            before = len(telnet_packets(client))
            client.socket.sendall(b"\xff\xfd\xc9")
            drain(client)
            require(not any(name == "Duris.Time" for name, _ in telnet_packets(client)[before:]), "repeated DO/idle replayed time")
            before = len(telnet_packets(client))
            client.send("toggle gmcp maybe")
            client.expect("A boolean flag needed")
            drain(client)
            require(not any(name in ("Duris.Capabilities", "Duris.Time") for name, _ in telnet_packets(client)[before:]), "invalid preference caused resynchronization")
            before = len(telnet_packets(client))
            client.send("toggle gmcp off")
            wait_telnet(client, "Duris.Capabilities", before, lambda state: not state["enabled"] and not state["active"])
            before = len(telnet_packets(client))
            drain(client)
            require(not any(name == "Duris.Time" for name, _ in telnet_packets(client)[before:]), "disabled preference still streamed")
            client.send("toggle gmcp on")
            wait_telnet(client, "Duris.Time", before)
            played = [data for name, data in telnet_packets(client) if name == "Duris.Session" and data["state"] == "playing"]
            require({(state["context"], state["generation"]) for state in played} == {(entry["context"], "1")}, "negotiation/preference replayed character entry")
            client.send("save")
            client.expect(f"Save complete for {CHARACTER}.", timeout=20)
            client.close()
            client = None
            server.shutdown()
            make_overlord(server.state_root, CHARACTER)
            reboot(server)
            client = MudClient(server.plain_port)
            negotiate(client)
            reconnect_character(client)
            wait_telnet(client, "Duris.Time")
            reconnected = wait_telnet(client, "Duris.Session", predicate=lambda state: state["state"] == "playing")
            require(reconnected["context"] != entry["context"] and reconnected["generation"] == "1", "new connection reused the preceding context")
            client.send("load mob 1106")
            client.expect("You have created")
            before = len(telnet_packets(client))
            client.send("switch shadow")
            switched = wait_telnet(client, "Duris.Session", before, lambda value: value["state"] == "playing" and value["character"]["bodyRevision"] != reconnected["character"]["bodyRevision"])
            require(switched["generation"] == reconnected["generation"] and switched["character"]["name"] == CHARACTER, "body switch became a new character entry")
            for package in ("Char.Vitals", "Char.Affects", "Room.Info"):
                wait_telnet(client, package, before)
            before = len(telnet_packets(client))
            client.send("return")
            client.expect("You return to your original body.")
            returned = wait_telnet(client, "Duris.Session", before, lambda value: value["state"] == "playing" and value["character"]["bodyRevision"] != switched["character"]["bodyRevision"])
            require(returned["context"] == reconnected["context"] and returned["generation"] == reconnected["generation"], "body return changed the entry key")
            combat = combat_journey(client)
            require(all(combat[-1][key] == returned[key] for key in ("context", "process", "generation")) and
                    combat[-1]["bodyRevision"] == returned["character"]["bodyRevision"],
                    "combat event crossed the current lifecycle/body boundary")
            items = item_journey(client)
            phases = []
            for hour, expected, phase in ((-1,23,"night"),(4,4,"dawn"),(9,9,"day"),(16,16,"dusk"),(0,0,"night")):
                before = len(telnet_packets(client))
                client.send(f"time {hour}")
                client.expect("You set the time.")
                state = wait_telnet(client, "Duris.Time", before, lambda value: value["hour"] == expected)
                require(state["phase"] == phase, f"wrong phase after staff time: {state}")
                phases.append(state)
            before = len(telnet_packets(client))
            send_telnet(client, "Duris.Subscribe", [])
            wait_telnet(client, "Duris.Capabilities", before, lambda state: not state["active"])
            before = len(telnet_packets(client))
            client.send("time 10")
            client.expect("You set the time.")
            drain(client)
            require(not any(name == "Duris.Time" for name, _ in telnet_packets(client)[before:]), "unsubscribed stream constructed output")
            before = len(telnet_packets(client))
            send_telnet(client, "Duris.Subscribe", ["Duris.Time 1"])
            wait_telnet(client, "Duris.Time", before, lambda state: state["hour"] == 10)
            before = len(telnet_packets(client))
            client.send("quit")
            client.expect("ACCOUNT MENU", timeout=20)
            cleared = wait_telnet(client, "Duris.Session", before, lambda state: state["state"] == "account")
            require(cleared["character"] is None and cleared["generation"] == "1", "departure did not clear the old character")
            wait_telnet(client, "Duris.Capabilities", before, lambda state: not state["active"])
            client.expect("Please select an option")
            before = len(telnet_packets(client))
            start_character(client)
            reply(client, SECOND_CHARACTER, "Is this correct?")
            reply(client, "y", "meet these criteria?")
            reply(client, "y", "Your selection")
            finish_character_choices(client)
            reply(client, "y", "PRESS RETURN")
            reply(client, "", "Your starter kit is ready")
            client.expect("Pos: standing >")
            wait_telnet(client, "Duris.Time", before, lambda state: state["hour"] == 10)
            reentered = wait_telnet(client, "Duris.Session", before, lambda state: state["state"] == "playing")
            require(reentered["context"] == reconnected["context"] and reentered["generation"] == "2" and reentered["character"]["name"] == SECOND_CHARACTER, "same-socket A/account/B transition has wrong identity")
            client.send("save")
            client.expect(f"Save complete for {SECOND_CHARACTER}.")
            client.close()
            client = None
            server.shutdown()
            reboot(server)
            deadline = time.monotonic() + 30
            while "Entering game loop." not in server.server_output():
                require(server.process.poll() is None and time.monotonic() < deadline, "server failed to restart before WebSocket entry")
                time.sleep(0.05)

            # Real WebSocket framing/JSON dispatch, initially unverified and before login.
            websocket = WebSocketClient(server.websocket_port)
            websocket.socket.settimeout(10)
            send_websocket(websocket, "Core.Supports.Set", ["Duris.Capabilities 1"])
            wait_websocket(websocket, "Duris.Capabilities")
            before = len(websocket.messages)
            websocket.send_frame(1, json.dumps({"type": "gmcp", "Package": "Core.Supports.Add", "Data": ["Duris.Time 1\0hidden"]}).encode())
            send_websocket(websocket, "Duris.Subscribe", ["Duris.Time 1"])
            rejected = wait_websocket(websocket, "Duris.Capabilities", after=before)
            require(not rejected["supported"] and not rejected["interested"], "WebSocket adapter accepted an invalid module string")
            time.sleep(1.1)
            before = len(websocket.messages)
            send_websocket(websocket, "Core.Supports.Set", SUPPORT)
            send_websocket(websocket, "Duris.Subscribe", ["Duris.Time 1"])
            capabilities = wait_websocket(websocket, "Duris.Capabilities", after=before)
            require(not capabilities["active"], "WebSocket streamed before character entry")
            auth = websocket.command("login", {"account": ACCOUNT, "password": OLD_PASSWORD}, "auth")
            require(auth["status"] in ("success", "reconnected"), f"WebSocket login failed: {auth}")
            if auth["status"] == "success":
                before = len(websocket.messages)
                websocket.send_frame(1, json.dumps({"type": "cmd", "cmd": "enter", "data": {"character": "Missing"}}).encode())
                time.sleep(1.1)
                send_websocket(websocket, "Core.Supports.Add", [])
                failed = wait_websocket(websocket, "Duris.Session", lambda value: value["state"] == "account", after=before)
                require(failed["generation"] == "0" and failed["character"] is None, "failed entry advanced or exposed a character")
                websocket.send_frame(1, json.dumps({"type": "cmd", "cmd": "enter", "data": {"character": SECOND_CHARACTER}}).encode())
            state = wait_websocket(websocket, "Duris.Time")
            websocket_entry = wait_websocket(websocket, "Duris.Session", lambda value: value["state"] == "playing")
            require(websocket_entry["character"]["name"] == SECOND_CHARACTER and websocket_entry["generation"] == "1", "WebSocket attachment has wrong lifecycle identity")
            require(websocket_entry["context"] != reentered["context"], "WebSocket reused the Telnet context")
            require(0 <= state["hour"] <= 23 and state["process"] == websocket_entry["process"], f"wrong WebSocket clock scope: {state}")
            before = len(websocket.messages)
            send_websocket(websocket, "Core.Supports.Add", ["Char.Items 1"])
            wait_websocket(websocket, "Duris.Capabilities", lambda value: "Char.Items" in value["supported"], after=before)
            send_websocket(websocket, "Duris.Subscribe", ["Duris.Time 1", "Char.Items 1"])
            websocket_items = wait_websocket(websocket, "Char.Items.List", lambda value:
                value["location"] == "inv" and value["complete"], after=before)
            require(websocket_items["context"] == websocket_entry["context"] and
                    websocket_items["generation"] == websocket_entry["generation"], "WebSocket items have stale entry context")
            require(not any("edited wooden mace" in row["description"] for row in websocket_items["items"]),
                    "old character inventory entered the new body")
            before = len(websocket.messages)
            send_websocket(websocket, "Char.Items.Get", [])
            wait_websocket(websocket, "Char.Items.List", lambda value:
                value["location"] == "inv" and value["complete"] and
                int(value["revision"]) > int(websocket_items["revision"]), after=before)
            websocket.close()
            websocket = None
            server.shutdown()
            result = {"staff_phases": phases, "websocket_time": state,
                      "session_entries": [entry, reconnected, reentered, websocket_entry],
                      "body_transitions": [switched, returned], "combat": combat, "items": items, "websocket_items": websocket_items, "binary": str(binary),
                      "source_sha256": hashlib.sha256((ROOT / "src/net/gmcp.c").read_bytes()).hexdigest(),
                      "scope": "Booted disposable lifecycle/control/time plus combat/tank/extraction via normal dispatch; not real Mudlet or overhead qualification."}
            if evidence:
                evidence.parent.mkdir(parents=True, exist_ok=True)
                evidence.write_text(json.dumps(result, indent=2) + "\n")
        except Exception as error:
            raise AssertionError(f"{error}\n--- isolated runtime ---\n{server.server_output()[-8000:]}\n{server.runtime_logs()[-12000:]}") from error
        finally:
            if client:
                client.close()
            if websocket:
                websocket.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", type=Path)
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    build_root = ROOT / "bin/tests"
    build_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="gmcp-control-", dir=build_root) as build:
        run(args.server.resolve() if args.server else build_flatfile_server(Path(build)), args.evidence)
    print("booted GMCP control/time/session and combat state journey passed")
