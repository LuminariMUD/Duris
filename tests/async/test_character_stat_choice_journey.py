#!/usr/bin/env python3
"""Real WebSocket creation ordering and numeric save/restart/relogin qualification."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import time

from test_account_recovery_journey import IsolatedServer, require, OLD_PASSWORD, ROOT
import test_creation_prompt_journey as telnet
from test_creation_prompt_journey import reboot
from test_flatfile_combat_journey import make_overlord
from test_connection_limit_journey import upgrade


class WebSocketClient:
    """Small uncompressed socket client for the server's existing JSON protocol."""
    def __init__(self, port):
        self.socket = socket.create_connection(("127.0.0.1", port), timeout=5)
        self.messages = []
        self.buffer = bytearray(upgrade(self.socket, "127.0.0.1"))

    def close(self):
        self.socket.close()

    def send_frame(self, opcode, payload):
        mask = os.urandom(4)
        count = len(payload)
        header = bytes((0x80 | opcode, 0x80 | (count if count < 126 else 126)))
        if count >= 126:
            header += struct.pack("!H", count)
        self.socket.sendall(header + mask + bytes(value ^ mask[i % 4] for i, value in enumerate(payload)))

    def read(self, count):
        while len(self.buffer) < count:
            chunk = self.socket.recv(65536)
            require(bool(chunk), "WebSocket closed before its response")
            self.buffer.extend(chunk)
        result = bytes(self.buffer[:count])
        del self.buffer[:count]
        return result

    def receive(self):
        while True:
            first, second = self.read(2)
            count = second & 127
            if count == 126:
                count = struct.unpack("!H", self.read(2))[0]
            elif count == 127:
                count = struct.unpack("!Q", self.read(8))[0]
            require(not second & 128 and first & 128 and not first & 112,
                    "unexpected masked, fragmented or compressed server frame")
            payload = self.read(count)
            opcode = first & 15
            if opcode == 9:
                self.send_frame(10, payload)
            elif opcode == 1:
                message = json.loads(payload)
                self.messages.append(message)
                return message
            elif opcode == 8:
                raise AssertionError("server closed WebSocket: " + repr(payload))

    def command(self, cmd, data=None, expected=None):
        self.send_frame(1, json.dumps({"type": "cmd", "cmd": cmd, "data": data or {}}).encode())
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            result = self.receive()
            if result.get("type") == "system" and result.get("data", {}).get("status") == "error":
                require(expected == "error", f"{cmd} rejected: {result}")
                return result
            if result.get("type") == (expected or cmd):
                require(expected != "error", f"{cmd} unexpectedly succeeded: {result}")
                return result
        raise AssertionError(f"no {expected or cmd} response to {cmd}")


def inspect_stats(server, inspector):
    snapshots = list((server.state_root / "players").glob("*.snapshot"))
    require(len(snapshots) == 1, f"expected one synthetic saved character: {snapshots}")
    record = json.loads(subprocess.check_output([str(inspector), str(server.state_root),
                                                "inspect", snapshots[0].stem], text=True))
    if server.full_world:
        require(record["room"] == 22800, f"character did not save in the selected tutorial: {record['room']}")
    return record["base_stats"]


def run(binary, inspector, method, *, legacy=False, full_world=False):
    with IsolatedServer(binary, {"DURIS_WEBSOCKET": "TRUE"}, full_world=full_world) as server:
        client = WebSocketClient(server.websocket_port)
        try:
            for cmd, data in (("roll_stats", {"race": 1}), ("add_bonus", {"stat": "str"}),
                              ("swap_stats", {"stat1": "str", "stat2": "luk"}),
                              ("create_character", {}), ("reset_chargen", {})):
                client.command(cmd, data, "error")
            auth = client.command("register", {"account": "Statjourney", "password": OLD_PASSWORD,
                                              "email": "stats@example.invalid"}, "auth")
            require(auth["status"] == "success" and auth["data"]["account"] == "Statjourney", f"registration failed: {auth}")
            options = client.command("chargen_options")
            require(options["statMethods"] == ["default", "advanced"] and options["bonusCount"] == 4,
                    f"bad capabilities: {options}")
            race = next(r for r in options["races"] if r["id"] == 1)
            warrior = next(c for c in race["classes"] if c["name"].lower() == "warrior")
            homes = client.command("get_hometowns", {"race": 1}, "hometowns")
            hometown = next(h for h in homes["options"] if "Plane" in h["name"])
            single_home = client.command("get_hometowns", {"race": 6}, "hometowns")
            require(single_home["count"] == 1 and single_home["hasChoice"] is False,
                    "single hometown was incorrectly advertised as a choice")
            creation = {"name": "Taverek", "race": 1, "class": warrior["id"], "sex": 1,
                        "alignment": "good", "hometown": hometown["id"], "newbie": True}
            for cmd, data in (("add_bonus", {"stat": "str"}), ("accept_stats", {}),
                              ("swap_stats", {"stat1": "str", "stat2": "luk"}),
                              ("create_character", creation)):
                client.command(cmd, data, "error")
            for value in (False, None, "invalid"):
                client.command("roll_stats", {"race": 1, "method": value}, "error")
            # Reset in rolling, bonuses and ready; every new attempt gets exactly four awards.
            for phase in ("rolling", "bonuses", "ready"):
                state = client.command("roll_stats", {"race": 1, "method": "advanced"})
                if phase != "rolling":
                    state = client.command("accept_stats", expected="stats_accepted")
                if phase == "ready":
                    for stat in ("str", "dex", "agi", "luk"):
                        state = client.command("add_bonus", {"stat": stat}, "bonus_added")
                require(state["phase"] == phase, f"did not reach reset phase {phase}")
                client.command("reset_chargen", expected="chargen_reset")
            # Reconnect clears an unfinished attempt for legacy clients with local-only Cancel.
            client.command("roll_stats", {"race": 1})
            client.close()
            client = WebSocketClient(server.websocket_port)
            auth = client.command("login", {"account": "Statjourney", "password": OLD_PASSWORD}, "auth")
            require(auth["status"] == "success", f"login failed: {auth}")
            # Reauthentication replaces the account/session and invalidates its old attempt.
            client.command("roll_stats", {"race": 1})
            auth = client.command("login", {"account": "Statjourney", "password": OLD_PASSWORD}, "auth")
            require(auth["status"] == "success", "account replacement failed")
            payload = {"race": 1}
            if not legacy:
                payload["method"] = method
            state = client.command("roll_stats", payload)
            require(state["method"] == method and state["bonusRemaining"] == 4, "wrong initial state")
            client.command("chargen_options")  # must not reset the attempt
            for request in ({"race": 5, "method": method},
                            {"race": 1, "method": "default" if method == "advanced" else "advanced"}):
                client.command("roll_stats", request, "error")
            if method == "advanced":
                state = client.command("roll_stats", payload)
                client.command("add_bonus", {"stat": "str"}, "error")
                client.command("create_character", creation, "error")
                accepted = client.command("accept_stats", expected="stats_accepted")
                require(accepted["stats"] == state["stats"], "acceptance changed stats")
            client.command("roll_stats", payload, "error")
            client.command("create_character", creation, "error")
            client.command("swap_stats", {"stat1": "str", "stat2": "luk"}, "error")
            client.command("add_bonus", {"stat": "kar"}, "error")
            for remaining, stat in zip((3, 2, 1, 0), ("str", "dex", "agi", "luk")):
                state = client.command("add_bonus", {"stat": stat}, "bonus_added")
                require(state["bonusRemaining"] == remaining, "wrong bonus count")
                if method == "advanced":
                    again = client.command("accept_stats", expected="stats_accepted")
                    require(again["stats"] == state["stats"] and again["bonusRemaining"] == remaining
                            and again["phase"] == state["phase"], "duplicate accept changed state")
            require(state["phase"] == "ready", "fourth bonus did not finish")
            client.command("add_bonus", {"stat": "con"}, "error")
            client.command("swap_stats", {"stat1": "str", "stat2": "kar"}, "error")
            original = state["stats"]
            swapped = client.command("swap_stats", {"stat1": "str", "stat2": "luk"}, "stats_swapped")
            require(swapped["stats"]["str"] == original["luk"] and swapped["stats"]["luk"] == original["str"],
                    "luck swap failed")
            client.command("swap_stats", {"stat1": "str", "stat2": "luk"}, "stats_swapped")
            client.command("create_character", {**creation, "race": 5}, "error")
            created = client.command("create_character", creation)
            require(created["status"] == "created" and created["hardcore"] is False
                    and created["newbie"] is True, f"creation failed or returned incorrect flags: {created}")
            if full_world:
                rooms = [m["data"]["num"] for m in client.messages if m.get("package") == "Room.Info"]
                require(rooms and rooms[-1] == 22800, f"new character missed the selected tutorial: {rooms}")
            save = client.command("game", "save", "text")
            deadline = time.monotonic() + 15
            while "Save complete for Taverek" not in json.dumps(save):
                require(time.monotonic() < deadline, "no durable save acknowledgement")
                save = client.receive()
            # The initial entry snapshot precedes detached kit publication. The
            # readiness boundary must publish the resulting derived HP before play.
            vitals = [m["data"] for m in client.messages if m.get("package") == "Char.Vitals"]
            require(len(vitals) >= 2 and (not full_world or vitals[-1]["maxHp"] > 1)
                    and vitals[-1]["hp"] == vitals[-1]["maxHp"],
                    f"starter readiness left the browser's pre-kit vitals stale: {vitals}")
            before = inspect_stats(server, inspector)
            account_info = client.command("account_info", expected="account")
            require(account_info["data"]["characters"][0]["level"] == 1,
                    "new character account summary retained its pre-entry level")
            low, high = (87, 90) if method == "default" else (80, 95)
            for index, stat in enumerate(before):
                require(low + (5 if index in (0,1,2,9) else 0) <= stat <= min(100, high + (5 if index in (0,1,2,9) else 0)),
                        f"saved {method} stat outside selected distribution/bonuses: {before}")
            # Creation commands while playing must not touch either runtime or saved stats.
            for cmd, data in (("create_character", {**creation, "name": "Veralis"}),
                              ("roll_stats", payload), ("add_bonus", {"stat": "con"}),
                              ("swap_stats", {"stat1": "str", "stat2": "con"}),
                              ("accept_stats", {}), ("reset_chargen", {})):
                client.command(cmd, data, "error")
            require(inspect_stats(server, inspector) == before, "playing creation command changed saved stats")
            client.close()
            server.shutdown()
            # Promote only this synthetic offline character to make quit immediate.
            # This fixture command changes level, never the authoritative base stats.
            make_overlord(server.state_root, "Taverek")
            reboot(server)
            deadline = time.monotonic() + 120
            while "Entering game loop." not in server.server_output():
                require(server.process.poll() is None and time.monotonic() < deadline,
                        "restart failed: " + server.server_output()[-4000:])
                time.sleep(0.1)
            client = WebSocketClient(server.websocket_port)
            auth = client.command("login", {"account": "Statjourney", "password": OLD_PASSWORD}, "auth")
            require(auth["status"] == "success" and auth["data"]["characters"][0]["level"] == 1,
                    f"restart login failed or lost new-character projection: {auth}")
            client.command("enter", {"character": "Taverek"}, "gmcp")
            # The saved-character path must load unchanged stats and bypass method choice.
            save = client.command("game", "save", "text")
            deadline = time.monotonic() + 15
            while "Save complete for Taverek" not in json.dumps(save):
                require(time.monotonic() < deadline, "no save after reload")
                save = client.receive()
            require(inspect_stats(server, inspector) == before, "saved base stats changed across restart/relogin")
            returned = client.command("game", "quit", "account")
            require(returned["action"] == "return_to_menu", "quit did not return to account menu")
            # Success consumed the old attempt; there are no reusable ready stats.
            client.command("create_character", {**creation, "name": "Veralis"}, "error")
            fresh = client.command("roll_stats", {"race": 1})
            require(fresh["bonusRemaining"] == 4, "success retained old bonus state")
            for stat in ("str", "dex", "agi", "luk"):
                fresh = client.command("add_bonus", {"stat": stat}, "bonus_added")
            collision = client.command("create_character", creation)
            require(collision["status"] == "error" and "already in use" in collision["message"],
                    "name collision was not retained for retry")
            require(inspect_stats(server, inspector) == before, "name collision changed existing character")
            swapped = client.command("swap_stats", {"stat1": "str", "stat2": "luk"}, "stats_swapped")
            require(swapped["phase"] == "ready", "collision lost the valid attempt")
            retried = client.command("create_character", {**creation, "name": "Veralis"})
            require(retried["status"] == "created", "name correction could not reuse valid attempt")
            server.shutdown()
            print(f"PASS {'full-world' if full_world else 'minimal-world'} real WebSocket {method}{' legacy' if legacy else ''}: ordering, lifecycle, create/save/restart/relogin and ten saved numeric stats", flush=True)
        finally:
            client.close()


def run_telnet(binary, inspector, method, *, full_world=False):
    with IsolatedServer(binary, {}, full_world=full_world) as server:
        client = telnet.MudClient(server.plain_port)
        try:
            telnet.reach_race(client)
            telnet.finish_character_choices(client, method="a" if method == "advanced" else "d")
            telnet.reply(client, "y", "PRESS RETURN")
            telnet.reply(client, "", "Your starter kit is ready")
            client.expect("Pos: standing >")
            telnet.reply(client, "save", "Save complete for Taverek.")
            before = inspect_stats(server, inspector)
            low, high = (87, 90) if method == "default" else (80, 95)
            for index, value in enumerate(before):
                bonus = 5 if index in (0, 1, 2, 9) else 0
                require(low + bonus <= value <= min(100, high + bonus),
                        f"Telnet {method} saved stats did not preserve its formula/bonuses: {before}")
            client.close()
            server.shutdown()
            reboot(server)
            client = telnet.MudClient(server.plain_port)
            telnet.enter_account_name(client)
            client.expect("Please enter your password:")
            telnet.reply(client, telnet.OLD_PASSWORD, "PRESS RETURN")
            telnet.reply(client, "", telnet.MENU)
            telnet.reply(client, "1", "Taverek")
            telnet.reply(client, "1", "(Y/N)")
            telnet.reply(client, "y", "Pos: standing >")
            telnet.reply(client, "save", "Save complete for Taverek.")
            require(inspect_stats(server, inspector) == before,
                    "Telnet saved stats changed across restart/relogin")
            server.shutdown()
            print(f"PASS {'full-world' if full_world else 'minimal-world'} real Telnet {method}: "
                  "create/save/restart/relogin and ten saved numeric stats", flush=True)
        finally:
            client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, default=ROOT / "bin/server/dms_new")
    parser.add_argument("--full-world", action="store_true", help="qualify the actual tutorial rooms and world")
    args = parser.parse_args()
    inspector = ROOT / "bin/tests/stat-choice/inspector"
    subprocess.run(["python3", "tests/async/test_flatfile_player_repository.py", "--build-inspector", str(inspector)], cwd=ROOT, check=True)
    for method in ("default", "advanced"):
        run_telnet(args.binary.resolve(), inspector, method, full_world=args.full_world)
    for method, legacy in (("default", False), ("advanced", False), ("default", True)):
        run(args.binary.resolve(), inspector, method, legacy=legacy, full_world=args.full_world)
