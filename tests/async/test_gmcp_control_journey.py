#!/usr/bin/env python3
"""Booted control/time protocol through normal Telnet and WebSocket dispatch.

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
from test_creation_prompt_journey import reboot
from test_flatfile_combat_journey import make_overlord
from test_character_stat_choice_journey import WebSocketClient


GMCP_FRAME = re.compile(rb"\xff\xfa\xc9(.*?)\xff\xf0", re.S)
SUPPORT = ["Duris.Capabilities 1", "Duris.Time 1"]


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


def run(binary, evidence):
    with IsolatedServer(binary, {"DURIS_WEBSOCKET": "TRUE"}) as server:
        client = None
        websocket = None
        try:
            client = MudClient(server.plain_port)
            negotiate(client)
            require(not any(name == "Duris.Time" for name, _ in telnet_packets(client)), "time leaked before character entry")
            create_character(client)
            first = wait_telnet(client, "Duris.Time")
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
            wait_telnet(client, "Duris.Capabilities", before, lambda state: not state["active"])
            client.expect("Please select an option")
            before = len(telnet_packets(client))
            client.send("1")
            client.expect(CHARACTER)
            client.send("1")
            client.expect("Play as")
            client.send("y")
            client.expect("Pos: standing >")
            wait_telnet(client, "Duris.Time", before, lambda state: state["hour"] == 10)
            client.close()
            client = None

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
                websocket.send_frame(1, json.dumps({"type": "cmd", "cmd": "enter", "data": {"character": CHARACTER}}).encode())
            state = wait_websocket(websocket, "Duris.Time")
            require(state["hour"] == 10 and state["phase"] == "day", f"wrong WebSocket clock: {state}")
            websocket.close()
            websocket = None
            server.shutdown()
            result = {"staff_phases": phases, "websocket_time": state, "binary": str(binary),
                      "source_sha256": hashlib.sha256((ROOT / "src/net/gmcp.c").read_bytes()).hexdigest(),
                      "scope": "Booted disposable server and normal Telnet/WebSocket dispatch; not real Mudlet or overhead qualification."}
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
    print("booted GMCP control/time Telnet and WebSocket journey passed")
