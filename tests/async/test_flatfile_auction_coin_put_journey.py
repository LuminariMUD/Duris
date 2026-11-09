#!/usr/bin/env python3
"""Auction listing must leave a connected player's next coin put usable."""

import argparse
import pathlib
import shutil
import signal
import subprocess
import tempfile
import time

import test_flatfile_combat_journey as journey
from run_world_quest_dual_backend import setup_run_root
from test_flight_network_journey import authority


TRANSFER_FAILED = "The coin transfer did not commit; nothing changed."
TRANSFER_SUCCEEDED = "coins into a small leather bag."
REMAINING_WALLET = [0, 8, 9, 8]  # Ten platinum less the 1,020-copper listing fee.
COINS_BACK = "There were: 8 platinum coins, 9 gold coins, 8 silver coins."
AUCTION_ROOM = 16885  # Vendurini's Auction House, a registered room.
SEEDED_ITEMS = (
    (980001, 390, "testbag bag leather small", 15, 30, 80),
    (980002, 391, "saleitem bag leather large", 15, 50, 100),
    (980003, 15, "banana", 19, 0, 0),
)


def command(client, text, expected):
    client.send(text)
    matched, output = client.expect_any((
        expected, TRANSFER_FAILED,
        "The coin debit could not start; nothing changed."), timeout=30)
    journey.require(matched == expected, f"{text}: {output}")
    print(f"{text}: {matched}", flush=True)


def seed_character(sql):
    """Replace the starter kit with the journey's bags and banana, ten platinum, and the room."""
    pid = sql(f"SELECT pid FROM player_data WHERE name='{journey.CHARACTER}'")
    rows = ",".join(f"({pid},{vnum},{uid},'{name}',{kind},1,100,{capacity},{limit})"
                    for uid, vnum, name, kind, capacity, limit in SEEDED_ITEMS)
    owners = ",".join(f"({uid},{uid},1,{pid},0,1,{vnum},1)" for uid, vnum, *_ in SEEDED_ITEMS)
    sql(f"DELETE FROM player_items WHERE pid={pid};"
        f"DELETE FROM item_current_owner WHERE owner_type=1 AND owner_id={pid};"
        "INSERT INTO player_items(pid,vnum,obj_uid,name,item_type,weight,item_condition,value0,value3) "
        f"VALUES {rows};"
        "INSERT INTO item_current_owner(item_uid,root_item_uid,owner_type,owner_id,"
        f"owner_context_id,item_revision,vnum,state) VALUES {owners};"
        f"UPDATE player_data SET platinum=10,gold=0,silver=0,copper=0,last_room={AUCTION_ROOM} "
        f"WHERE pid={pid}")


def verify(client, restart, sql, expect_regression=False):
    command(client, "put banana testbag", "Ok.")
    command(client, "auction offer saleitem 1", "is now listed as auction")
    listed = journey.inspect_authority(sql)
    journey.require(listed["wallet"] == REMAINING_WALLET,
                    f"unexpected listing fee: {listed}")

    # No disconnect occurs before these commands.
    if expect_regression:
        for _ in range(2):
            command(client, "put all.coins testbag", TRANSFER_FAILED)
            after = journey.inspect_authority(sql)
            for key in ("wallet", "wallet_revision", "bank", "bank_revision"):
                journey.require(after[key] == listed[key],
                                f"failed coin put changed {key}: {after}")
    else:
        command(client, "put all.coins testbag", TRANSFER_SUCCEEDED)
        command(client, "save", f"Saving {journey.CHARACTER}.")
        journey.require(journey.inspect_authority(sql)["wallet"] == [0, 0, 0, 0],
                        "successful coin put did not durably debit the wallet")
        command(client, "get coins testbag", COINS_BACK)
        command(client, "put all.coins testbag", TRANSFER_SUCCEEDED)

    command(client, "save", f"Saving {journey.CHARACTER}.")
    # The auction house is in a town, where quit is refused; a restart is the full reload.
    reloaded = restart(client)
    try:
        if not expect_regression:
            command(reloaded, "get coins testbag", COINS_BACK)
            command(reloaded, "save", f"Saving {journey.CHARACTER}.")
        after = journey.inspect_authority(sql)
        journey.require(after["wallet"] == REMAINING_WALLET,
                        f"round trip or full reload changed the coin balance: {after}")
        command(reloaded, "put all.coins testbag", TRANSFER_SUCCEEDED)
    finally:
        reloaded.close()


def run(binary, expect_regression):
    (journey.ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="auction-coin-put-", dir=journey.ROOT / "bin/tests") as tmp:
        runtime = pathlib.Path(tmp)
        _, critical, output_path = setup_run_root(runtime)
        (runtime / "help").symlink_to(journey.ROOT / "help", target_is_directory=True)
        properties = runtime / "lib/duris.properties"
        rates = properties.read_text()
        journey.require("auctions.startPricePctFee=0.040" in rates, "auction fee fixture changed")
        # Pin the rate this journey's wallet arithmetic assumes; it tests the coin put.
        properties.write_text(rates.replace("auctions.startPricePctFee=0.040", "auctions.startPricePctFee=0.020"))
        executable = runtime / "bin/server/dms"
        executable.parent.mkdir(parents=True)
        shutil.copy2(binary, executable)
        with (runtime / "lib/misc/event_names").open("w") as names:
            subprocess.run([str(journey.ROOT / "scripts/event_names.sh"), str(executable)],
                           stdout=names, check=True)
        plain, tls, websocket = journey.available_ports()
        with authority("mariadb", runtime) as (env, sql):
            env.update(CRITICAL_COMMAND_JOURNAL_DIR=str(critical), DURIS_TLS_PORT=str(tls),
                       DURIS_WEBSOCKET_PORT=str(websocket),
                       MAINTENANCE_STATE_FILE=str(runtime / "maintenance.state"))

            def boot():
                """A real boot: `--minimal` skips init_auction_houses()."""
                offset = output_path.stat().st_size if output_path.exists() else 0
                with output_path.open("a") as output:
                    process = subprocess.Popen([str(executable), "-d", str(runtime), str(plain)],
                                               cwd=runtime, env=env, stdout=output,
                                               stderr=subprocess.STDOUT)
                try:
                    deadline = time.monotonic() + 180
                    while b"Entering game loop." not in output_path.read_bytes()[offset:]:
                        journey.require(process.poll() is None and time.monotonic() < deadline,
                                        "server did not boot:\n" + output_path.read_text(errors="replace")[-8000:])
                        time.sleep(.1)
                    return process
                except BaseException:
                    if process.poll() is None:
                        process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=10)
                    raise

            def stop(process):
                process.send_signal(signal.SIGTERM)
                process.wait(timeout=60)
                journey.require(process.returncode == 0, "the server did not stop normally")

            process = boot()
            client = None
            try:
                client = journey.MudClient(plain)
                journey.create_character(client, expected_room=None)
                client.send("save")
                client.expect(f"Saving {journey.CHARACTER}.", timeout=45)
                client.close()
                client = None
                stop(process)
                seed_character(sql)

                def login():
                    nonlocal client
                    client = journey.reconnect_character(plain, expected_room=None)
                    client.expect("Pos: standing >", timeout=30)
                    return client

                def restart(previous):
                    nonlocal process
                    stop(process)
                    previous.close()
                    process = boot()
                    return login()

                process = boot()
                verify(login(), restart, sql, expect_regression)
                client.close()
                client = None
                stop(process)
            except Exception:
                print(output_path.read_text(errors="replace")[-8000:])
                if client:
                    print(bytes(client.transcript).decode(errors="replace")[-6000:])
                raise
            finally:
                if client:
                    client.close()
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=10)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", type=pathlib.Path, required=True)
    parser.add_argument("--expect-regression", action="store_true",
                        help="verify the original failure and full-reload workaround")
    args = parser.parse_args()
    run(args.server.resolve(), args.expect_regression)
    print("Original auction/coin-put regression reproduced." if args.expect_regression else
          "Auction listing, immediate coin put, round trips, and full reload passed.")


if __name__ == "__main__":
    main()
