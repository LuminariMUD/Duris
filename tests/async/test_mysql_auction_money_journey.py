#!/usr/bin/env python3
"""Auction pickup capacity refusal, disconnect and restart against disposable MariaDB."""

import argparse
from pathlib import Path
import tempfile
import time

import test_flatfile_combat_journey as journey
from run_item_pilot_journey import Server
from run_world_quest_dual_backend import collect_logs
from test_flight_network_journey import authority, command

ROOT = journey.ROOT
PLAYER, ACCOUNT = "Creditbuyer", "Creditacct"
INT_MAX = 2147483647


def run(binary):
    (ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="auction-money-", dir=ROOT / "bin/tests") as temporary:
        runtime = Path(temporary)
        journey.make_fixture(runtime)
        journey.generate_certificate(runtime)
        (runtime / "logs/log").mkdir(parents=True)
        (runtime / "help").symlink_to(ROOT / "help", target_is_directory=True)
        with authority("mariadb", runtime) as (env, sql):
            server = Server(binary, runtime, runtime, "auction-money", environment=env)
            client = None

            def login():
                nonlocal client
                client = journey.reconnect_character(server.port, expected_room=None,
                                                     account=ACCOUNT, character=PLAYER)
                client.expect("Welcome to Duris", timeout=60)
                client.expect("Pos: standing >", timeout=20)
                command(client, "toggle paging no")

            def stop(crash=False):
                nonlocal client
                if client:
                    client.close()
                    client = None
                if crash:
                    server.process.kill()
                    server.process.wait(timeout=10)
                server.stop()

            def state():
                return tuple(map(int, sql(
                    "SELECT p.copper+10*p.silver+100*p.gold+1000*p.platinum,"
                    "COALESCE(m.money,0),COALESCE(b.bank_copper+10*b.bank_silver+"
                    "100*b.bank_gold+1000*b.bank_platinum,0) FROM player_data p "
                    "LEFT JOIN auction_money_pickups m ON m.pid=p.pid "
                    "LEFT JOIN account_banks b ON b.account_name=p.account_name AND b.racewar=p.racewar "
                    f"WHERE p.name='{PLAYER}'").split()))

            def await_state(expected):
                deadline = time.monotonic() + 20
                while time.monotonic() < deadline:
                    actual = state()
                    if actual == expected:
                        return
                    time.sleep(.05)
                raise AssertionError(("auction balances did not settle", expected, actual))

            try:
                server.start(full_world=True)
                client = journey.MudClient(server.port)
                journey.create_character(client, expected_room=None, account=ACCOUNT,
                                         character=PLAYER, email="creditbuyer@example.invalid")
                command(client, "save")
                stop()
                sql(f"UPDATE player_data SET level=20,highest_level=20,copper={INT_MAX},"
                    f"silver=0,gold=0,platinum=0,last_room=16590 WHERE name='{PLAYER}'")
                pid = int(sql(f"SELECT pid FROM player_data WHERE name='{PLAYER}'"))
                sql(f"INSERT INTO auction_money_pickups(pid,money) VALUES({pid},1)")
                server.start(full_world=True)
                login()
                assert state() == (INT_MAX, 1, 0)
                client.send("auction pickup")
                response, text = client.expect_any(("money remains staged", "being committed"), timeout=20)
                assert response == "money remains staged", text
                assert state() == (INT_MAX, 1, 0), "a refused wallet credit consumed its durable pickup"
                stop(crash=True)
                server.start(full_world=True)
                login()
                assert state() == (INT_MAX, 1, 0)
                print("PASS full purse refuses admission; exact pickup survives SIGKILL and restart", flush=True)

                # Open one copper of room, then disconnect while the accepted claim resolves.
                response = command(client, "drop 1 copper")
                assert "OK." in response, response
                command(client, "save")
                await_state((INT_MAX - 1, 1, 0))
                client.send("auction pickup")
                client.expect("being committed", timeout=20)
                client.close()
                client = None
                await_state((INT_MAX, 0, 0))
                stop(crash=True)
                server.start(full_world=True)
                login()
                command(client, "save")
                await_state((INT_MAX, 0, 0))
                # Repeating pickup and checkpoint cannot charge or deliver a second time.
                command(client, "auction pickup")
                command(client, "save")
                assert state() == (INT_MAX, 0, 0)
                assert "trade_receipt_unresolved" not in collect_logs(runtime)
                print("PASS accepted claim survives disconnect and restart; repeated pickup/save cannot duplicate credit", flush=True)
            except Exception:
                target = ROOT / "bin/tests/auction-money-failure.log"
                target.write_text(collect_logs(runtime) + "\n" +
                                  server.output_path.read_text(errors="replace") + "\n" +
                                  (bytes(client.transcript).decode(errors="replace") if client else ""))
                print("Failure evidence: " + str(target), flush=True)
                raise
            finally:
                stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", type=Path, default=ROOT / "bin/server/dms_new")
    run(parser.parse_args().server.resolve())
