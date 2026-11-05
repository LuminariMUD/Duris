#!/usr/bin/env python3
"""Create -> menu -> week offline -> first Play, with real sockets and storage."""
import argparse
import json
from pathlib import Path
import subprocess
import time

import test_account_recovery_journey as account
import test_creation_prompt_journey as creation
from test_character_stat_choice_journey import WebSocketClient
from test_kept_character_journey import (
    kept_journey_binary, persistence, login, character_choices, websocket_character,
    websocket_text, saved_character,
)

WELLRESTED = 2108
FLAGS = 1540


def run(binary, backend, transport):
    inspector = account.ROOT / "bin/tests/kept-character-inspector"
    if backend == "flatfile" and (not inspector.exists() or inspector.stat().st_mtime <
            (account.ROOT / "tests/async/flatfile_player_repository_harness.cpp").stat().st_mtime):
        subprocess.run(["python3", "tests/async/test_flatfile_player_repository.py",
                        "--build-inspector", str(inspector)], cwd=account.ROOT, check=True)
    with persistence(backend) as (environment, sql):
        with account.IsolatedServer(binary, dict(environment, DURIS_WEBSOCKET="TRUE")) as server:
            client = None

            def record(pid):
                return json.loads(subprocess.check_output(
                    [str(inspector), str(server.state_root), "inspect", str(pid)], text=True))

            def affects(pid):
                if sql:
                    rows = sql(f"SELECT type,duration,flags FROM player_affects WHERE pid={pid} "
                               f"AND type={WELLRESTED}")
                    return [list(map(int, row.split())) for row in rows.splitlines()]
                return [af for af in record(pid)["affects"] if af[0] == WELLRESTED]

            def items(pid):
                if sql:
                    return sql(f"SELECT obj_uid FROM player_items WHERE pid={pid} ORDER BY obj_uid")
                return sorted(record(pid)["snapshot_uids"])

            def age(pid, seconds):
                assert server.process.poll() is not None, "only age a stopped synthetic fixture"
                if sql:
                    sql(f"UPDATE player_data SET last_save=NOW()-INTERVAL {seconds} SECOND WHERE pid={pid}")
                else:
                    subprocess.run([str(inspector), str(server.state_root), "age-last-save",
                                    str(pid), str(seconds)], check=True)

            def block(pid, blocked):
                assert server.process.poll() is not None
                if sql:
                    sql(f"UPDATE account_characters SET blocked={int(blocked)} WHERE pid={pid}")
                else:
                    subprocess.run([str(inspector), str(server.state_root), "block-membership",
                                    str(pid), str(int(blocked))], check=True)

            def connect():
                if transport == "telnet":
                    return login(server)
                connected = WebSocketClient(server.websocket_port)
                connected.command("login", {"account": account.ACCOUNT,
                                  "password": account.OLD_PASSWORD}, "auth")
                return connected

            def play(first):
                if transport == "telnet":
                    if first:
                        creation.play_saved_character(client)
                        creation.reply(client, "", "Your starter kit is ready")
                    else:
                        creation.reply(client, "1", "Taverek")
                        creation.reply(client, "Taverek", "(Y/N)")
                        creation.reply(client, "y", "Pos: standing >")
                    creation.reply(client, "save", "Save complete for Taverek.")
                else:
                    client.command("enter", {"character": "Taverek"}, "gmcp")
                    if first:
                        websocket_text(client, "Your starter kit is ready")
                    client.command("game", "save", "text")
                    websocket_text(client, "Save complete for Taverek.")

            try:
                if transport == "telnet":
                    client = account.MudClient(server.plain_port)
                    account.create_account(client, account.OLD_PASSWORD)
                    character_choices(client)
                    kept = creation.reply(client, "y", creation.MENU)
                    assert "PRESS RETURN" not in kept and "ENTERS THE GAME" not in kept
                    creation.require_prompt_framed(client, creation.MENU)
                    rested = creation.reply(client, "8", creation.MENU)
                    assert "available when you first enter the game" in rested, rested
                else:
                    client = WebSocketClient(server.websocket_port)
                    client.command("register", {"account": account.ACCOUNT,
                                   "password": account.OLD_PASSWORD,
                                   "email": "deferred@example.invalid"}, "auth")
                    kept = websocket_character(client)
                    assert kept["status"] == "created" and not kept["waitingForApproval"], kept
                    while client.messages[-1].get("type") != "auth":
                        client.receive()
                    assert not any(m.get("package") in ("Char.Status", "Char.Vitals", "Room.Info")
                                   for m in client.messages), client.messages
                    listed = client.messages[-1]["data"]["characters"]
                    assert len(listed) == 1 and listed[0]["level"] == 0, listed
                    rested = client.command("rested_bonus", expected="account")["data"]["characters"][0]
                    assert rested["availableOnFirstEntry"] and rested["restedPercent"] == 100, rested
                    assert rested["restedHours"] == 0, rested
                before = saved_character(server, sql, inspector)
                pid = before[0]
                assert before[1] == 0 and len(before[2]) == 10
                assert not affects(pid) and not items(pid)
                client.close()
                server.shutdown()
                block(pid, True)
                creation.reboot(server)
                client = connect()
                if transport == "telnet":
                    creation.reply(client, "1", "Taverek")
                    creation.reply(client, "Taverek", "blocked and cannot be played")
                else:
                    denied = client.command("enter", {"character": "Taverek"}, "error")
                    assert "blocked and cannot be played" in json.dumps(denied), denied
                assert saved_character(server, sql, inspector) == before
                assert not affects(pid) and not items(pid)
                client.close()
                server.shutdown()
                block(pid, False)
                age(pid, 7 * 24 * 3600)
                creation.reboot(server)
                client = connect()
                assert saved_character(server, sql, inspector) == before
                assert not affects(pid) and not items(pid)
                entered = time.monotonic()
                play(True)
                after = saved_character(server, sql, inspector)
                assert after == (pid, 1, before[2]), (before, after)
                bonus = affects(pid)
                # Fresh boot keeps this below its first scheduled affect tick.
                assert time.monotonic() - entered < 75
                assert bonus == [[WELLRESTED, 150, FLAGS]], bonus
                starter_uids = items(pid)
                assert starter_uids
                client.close()
                server.shutdown()
                age(pid, 150)
                creation.reboot(server)
                client = connect()
                play(False)
                remaining = affects(pid)
                assert len(remaining) == 1 and 0 < remaining[0][1] <= 148, remaining
                assert items(pid) == starter_uids, "starter kit duplicated after restart"
                assert saved_character(server, sql, inspector) == after
                print(f"PASS {backend} {transport}: menu, no affect/items, week deferred, "
                      "blocked Play preserved, full 150 ticks, offline countdown and stable starter UIDs", flush=True)
                server.shutdown()
            except Exception:
                print(server.server_output()[-3000:])
                print(server.runtime_logs()[-4000:])
                raise
            finally:
                if client:
                    client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("mariadb", "flatfile"), default="flatfile")
    parser.add_argument("--server", type=Path)
    parser.add_argument("--transport", choices=("telnet", "websocket"))
    args = parser.parse_args()
    with kept_journey_binary(args.server, args.backend) as binary:
        for transport in (args.transport,) if args.transport else ("telnet", "websocket"):
            run(binary, args.backend, transport)
