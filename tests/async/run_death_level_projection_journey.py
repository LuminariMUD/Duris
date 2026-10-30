#!/usr/bin/env python3
"""Death/menu/reload levels through real telnet and WebSocket on disposable state.

Run each --backend with its matching --binary; wrap MariaDB with
tests/async/with_disposable_mariadb.sh. No checkout .env or live accounts are used.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
import time

import test_flatfile_combat_journey as journey
from test_character_stat_choice_journey import WebSocketClient
from test_flight_network_journey import authority, command
from run_battleprep_journey import configure

ROOT = journey.ROOT
GOD, STAFF = "Levelwarden", "Levelstaff"
ACCOUNT, OTHER = "Levelpupils", "Othermonk"
PLAYERS = (("telnet", "Levelmonk"), ("websocket", "Webmonk"))


def run(binary, backend, output):
    output.mkdir(parents=True, exist_ok=False)
    inspector = output / "player-inspector"
    if backend == "flatfile":
        subprocess.run(["python3", "tests/async/test_flatfile_player_repository.py",
                        "--build-inspector", str(inspector)], cwd=ROOT, check=True)
    evidence = {"backend": backend, "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
                "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                "cases": [], "complete": False}
    (ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="death-level-", dir=ROOT / "bin/tests") as temporary:
        runtime = Path(temporary)
        configure(runtime)
        critical, boot_log = runtime / "journals/critical", runtime / "boot.out"
        critical.mkdir(parents=True, mode=0o700)
        clients, history, ids = [], [], {}
        process = None
        plain, tls, websocket = journey.available_ports()
        properties = runtime / "lib/duris.properties"
        properties.write_text(re.sub(r"camp.timer=\d+\.\d+", "camp.timer=1.000", properties.read_text()))
        with authority(backend, runtime) as (env, sql):
            env.update(CRITICAL_COMMAND_JOURNAL_DIR=str(critical), DURIS_TLS_PORT=str(tls),
                       DURIS_WEBSOCKET_PORT=str(websocket), DURIS_WEBSOCKET="TRUE")

            def boot():
                nonlocal process
                offset = boot_log.stat().st_size if boot_log.exists() else 0
                with boot_log.open("a") as log:
                    process = subprocess.Popen([str(binary), "-z", "-d", str(runtime), str(plain)],
                        cwd=runtime, env=env, stdout=log, stderr=subprocess.STDOUT)
                deadline = time.monotonic() + 180
                while "Entering game loop." not in boot_log.read_text(errors="replace")[offset:]:
                    assert process.poll() is None and time.monotonic() < deadline, boot_log.read_text(errors="replace")[-6000:]
                    time.sleep(.1)

            def stop():
                nonlocal process
                for client in clients:
                    client.close()
                clients.clear()
                if process and process.poll() is None:
                    process.terminate()
                    process.wait(timeout=60)
                    assert process.returncode == 0
                process = None

            def track(client):
                clients.append(client)
                history.append(client)
                return client

            def menu(protocol, account=ACCOUNT):
                if protocol == "websocket":
                    client = track(WebSocketClient(websocket))
                    # Mortal camping can be quiet longer than the shared client's
                    # five-second handshake timeout; retain the game's normal delay.
                    client.socket.settimeout(30)
                    auth = client.command("login", {"account": account, "password": journey.PASSWORD}, "auth")
                    assert auth["status"] == "success", auth
                    return client, auth["data"]["characters"]
                client = track(journey.MudClient(plain))
                first, _ = client.expect_any(("term type", "account name"))
                if first == "term type":
                    client.send("9")
                    client.expect("account name")
                client.send(account)
                client.expect("enter your password")
                client.send(journey.PASSWORD)
                client.expect("PRESS RETURN")
                client.send("")
                client.expect("Please select an option")
                return client, None

            def listing(client):
                if isinstance(client, WebSocketClient):
                    return client.command("account_info", expected="account")["data"]["characters"]
                client.send("1")
                return client.expect("Which character would you like to play?")

            def levels(rows):
                if isinstance(rows, list):
                    return {row["name"]: row["level"] for row in rows}
                return {name: int(level) for name, level in re.findall(r"\|\s*\d+\s*\|\s*(\w+)\s*\|\s*(\d+)\s*\|", rows)}

            def check(rows, name, level):
                found = levels(rows)
                assert found.get(name) == level, ("menu level mismatch", name, level, found)
                assert found.get(OTHER) == 1, ("unrelated character changed", found)

            def ws_until(client, predicate):
                deadline = time.monotonic() + 45
                while time.monotonic() < deadline:
                    message = client.receive()
                    if predicate(message):
                        return message
                raise AssertionError("WebSocket did not reach the expected response")

            def game(client, text):
                if not isinstance(client, WebSocketClient):
                    return command(client, text)
                client.send_frame(1, json.dumps({"type": "cmd", "cmd": "game", "data": text}).encode())
                if text != "score":
                    client.send_frame(1, json.dumps({"type": "cmd", "cmd": "game", "data": "score"}).encode())
                return ws_until(client, lambda msg: msg.get("type") == "text" and "Score information for" in msg.get("data", ""))["data"]

            def enter(client, name):
                if isinstance(client, WebSocketClient):
                    client.command("enter", {"character": name}, "gmcp")
                    game(client, "toggle paging no")
                    return
                client.send(name)
                client.expect("Play as")
                client.send("y")
                client.expect("Welcome to Duris", timeout=45)
                command(client, "toggle paging no")

            def live(name):
                text = command(god, "stat char " + name)
                pid = re.search(r"ID numb:\s*(\d+)", text)
                status = re.search(r"Level:\s*(\d+)\(\d+\)\s+Experience:\s*([\d,]+)", text)
                assert pid and status, text
                ids[name] = int(pid[1])
                return {"level": int(status[1]), "experience": int(status[2].replace(",", ""))}

            def saved(name):
                if sql:
                    values = sql(f"SELECT level,exp,save_revision FROM player_data WHERE pid={ids[name]}").split("\t")
                    return dict(zip(("level", "experience", "revision"), map(int, values)))
                return json.loads(subprocess.check_output([str(inspector), env["FLATFILE_STATE_DIR"],
                                                          "inspect", str(ids[name])], text=True))

            def wait_saved(name, expected, previous):
                deadline = time.monotonic() + 30
                while True:
                    state = saved(name)
                    if state["revision"] > previous and all(state[key] == value for key, value in expected.items()):
                        if backend == "flatfile":
                            assert state["membership_level"] == expected["level"], state
                        return state
                    assert time.monotonic() < deadline, ("saved state mismatch", expected, previous, state)
                    time.sleep(.05)

            def set_level(name, level, xp=12345):
                # Death reloads at 1 HP. Restore before changing derived maxima
                # so a fixture level reduction cannot itself kill the player.
                command(god, "restore " + name)
                # advance deliberately refuses reductions; use the existing staff
                # field command when resetting this synthetic delevel control.
                text = (f"advance {name} {level}" if live(name)["level"] <= level else
                        f"setbit char {name} level {level}")
                command(god, text)
                command(god, f"setbit char {name} exp {xp}")
                actual = live(name)
                assert actual == {"level": level, "experience": xp}, actual

            def return_rows(client):
                if isinstance(client, WebSocketClient):
                    message = ws_until(client, lambda msg: msg.get("action") == "return_to_menu")
                    return message["data"]["characters"]
                client.expect("Your wounds claim you at last", timeout=45)
                client.expect("ACCOUNT MENU", timeout=45)
                client.expect("Please select an option")
                return listing(client)

            def die(client, protocol, name, label, delevel=False):
                before = live(name)
                previous = saved(name)["revision"]
                command(god, "goto " + name)
                killed = command(god, "kill " + name)
                assert name + " is dead! R.I.P." in killed, killed
                expected = dict(before)
                if delevel:
                    expected["level"] -= 1
                rows = return_rows(client)
                evidence["cases"].append({"case": protocol + " " + label, "before": before, "menu": levels(rows)})
                check(rows, name, expected["level"])
                client.close()
                # No durable-state wait precedes fresh authentication or reselection.
                fresh, rows = menu(protocol)
                check(rows if rows is not None else listing(fresh), name, expected["level"])
                enter(fresh, name)
                after = live(name)
                if delevel:
                    assert after["level"] == expected["level"] and after["experience"] != before["experience"], (before, after)
                    expected = after
                else:
                    assert after == expected, (before, after)
                state = wait_saved(name, expected, previous)
                evidence["cases"][-1].update(after=after, saved=state)
                print("PASS", backend, protocol, label, before, "->", after, flush=True)
                return fresh

            try:
                boot()
                for name, account in ((GOD, STAFF), (PLAYERS[0][1], ACCOUNT),
                                      (PLAYERS[1][1], ACCOUNT), (OTHER, ACCOUNT)):
                    client = track(journey.MudClient(plain))
                    journey.create_character(client, expected_room=None, account=account, character=name,
                        existing_account=name in (PLAYERS[1][1], OTHER),
                        class_name="w" if name == GOD else "k", hometown="p",
                        email=name.lower() + "@example.invalid")
                    client.send("save")
                    client.expect("Save complete for " + name + ".", timeout=30)
                    client.close()
                print("SETUP", backend, "four disposable characters saved", flush=True)
                stop()
                if sql:
                    sql(f"UPDATE player_data SET level=62,highest_level=62 WHERE name='{GOD}'")
                else:
                    journey.make_overlord(Path(env["FLATFILE_STATE_DIR"]), GOD)
                boot()
                god = track(journey.reconnect_character(plain, account=STAFF, character=GOD, expected_room=None))
                god.expect("Welcome to Duris", timeout=45)
                command(god, "toggle paging no")
                # Character entry is the existing authoritative repair path. Warm
                # each new membership once; telnet creation may initially store 0.
                for name in (PLAYERS[0][1], PLAYERS[1][1], OTHER):
                    client, _ = menu("telnet")
                    listing(client)
                    enter(client, name)
                    client.send("quit")
                    client.expect("ACCOUNT MENU", timeout=30)
                    client.close()
                print("SETUP", backend, "memberships entered at level 1", flush=True)
                for protocol, name in PLAYERS:
                    client, rows = menu(protocol)
                    check(rows if rows is not None else listing(client), name, 1)
                    enter(client, name)
                    set_level(name, 16)
                    client = die(client, protocol, name, "in-session 1 to 16")
                    client = die(client, protocol, name, "entered at 16")
                    set_level(name, 30, 0)
                    client = die(client, protocol, name, "actual delevel", delevel=True)
                    set_level(name, 17)
                    if isinstance(client, WebSocketClient):
                        returned = client.command("game", "quit", "account")
                        check(returned["data"]["characters"], name, 17)
                    else:
                        client.send("quit")
                        client.expect("ACCOUNT MENU", timeout=30)
                        client.expect("Please select an option")
                        check(listing(client), name, 17)
                    evidence["cases"].append({"case": protocol + " quit", "level": 17})
                    print("PASS", backend, protocol, "quit after in-session level change", flush=True)
                    client.close()
                stop()
                boot()
                god = track(journey.reconnect_character(plain, account=STAFF, character=GOD, expected_room=None))
                god.expect("Welcome to Duris", timeout=45)
                command(god, "toggle paging no")
                for protocol, name in PLAYERS:
                    client, rows = menu(protocol)
                    check(rows if rows is not None else listing(client), name, 17)
                    enter(client, name)
                    assert live(name) == {"level": 17, "experience": 12345}
                    evidence["cases"].append({"case": protocol + " cold restart", "state": saved(name)})
                    print("PASS", backend, protocol, "cold restart", flush=True)
                    if isinstance(client, WebSocketClient):
                        client.command("game", "quit", "account")
                    else:
                        client.send("quit")
                        client.expect("ACCOUNT MENU", timeout=30)
                    client.close()
                stop()
                if backend == "flatfile":
                    name = PLAYERS[0][1]
                    subprocess.run([str(inspector), env["FLATFILE_STATE_DIR"], "stale-membership", str(ids[name])], check=True)
                    assert saved(name)["membership_level"] == 1 and saved(name)["level"] == 17
                    boot()
                    god = track(journey.reconnect_character(plain, account=STAFF, character=GOD, expected_room=None))
                    god.expect("Welcome to Duris", timeout=45)
                    command(god, "toggle paging no")
                    client, _ = menu("telnet")
                    check(listing(client), name, 1)
                    enter(client, name)
                    assert live(name)["level"] == 17
                    client = die(client, "telnet", name, "legacy stale membership repaired at entry")
                evidence["complete"] = True
            finally:
                for index, client in enumerate(history):
                    data = client.messages if isinstance(client, WebSocketClient) else bytes(client.transcript).decode(errors="replace")
                    (output / f"client-{index}.json").write_text(json.dumps(data, indent=2))
                stop()
                if boot_log.exists():
                    (output / "server.log").write_bytes(boot_log.read_bytes())
                (output / "result.json").write_text(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("mariadb", "flatfile"), required=True)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.binary.resolve(), args.backend, args.output.resolve())
