#!/usr/bin/env python3
"""Real finite-stock purchases, resale, clean boots, copyover, and crash recovery.

Use a disposable authority; checkout credentials and running servers are unused.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time

import test_flatfile_combat_journey as journey
from test_flight_network_journey import authority, command
from run_world_quest_dual_backend import setup_run_root
from test_shop_multi_buy_journey import fixture, KEEPER, BAG, TRINKET, SMALL_BAG, RATION
from _paths import rel

ROOT = journey.ROOT
PLAYER, ACCOUNT = "Stockbuyer", "Stockacct"
GOD, GOD_ACCOUNT = "Stockwarden", "Stockstaff"
MAGGEYNEL, BOTTOMLESS, POTION = 83385, 83185, 3102
ROOM = 45016  # Ordinary road: no merchant or pet-shop room procedure.


def build_inspector():
    binary = ROOT / "bin/tests/shop-stock-inspector"
    sources = ["tests/async/shop_stock_inspector.cpp"] + [rel(name) for name in (
        "flatfile_shopkeeper_repository.c", "flatfile_shopkeeper_ownership.c",
        "flatfile_item_repository.c", "item_ownership_runtime.c", "item_claim.c",
        "player_snapshot_codec.c", "flatfile_authority_transaction.c", "flatfile_store.c",
        "shop_trade_command.c", "item_transfer_command.c", "currency_command.c", "critical_command.c")]
    subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-Isrc",
                    "-ffunction-sections", "-fdata-sections", *sources, "-Wl,--gc-sections",
                    "-lcrypto", "-pthread", "-o", str(binary)], cwd=ROOT, check=True)
    return binary


def run(binary, backend, report):
    report.parent.mkdir(parents=True, exist_ok=True)
    evidence = {"backend": backend, "passed": False, "checks": [],
                "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest()}
    inspector = build_inspector() if backend == "flatfile" else None
    with tempfile.TemporaryDirectory(prefix="shop-reboot-", dir=ROOT / "bin/tests") as temporary:
        runtime = Path(temporary)
        _, critical, log = setup_run_root(runtime)
        fixture(runtime, reboot_stock=True, room=ROOM)
        executable = runtime / "bin/server/dms"
        executable.parent.mkdir(parents=True)
        shutil.copy2(binary, executable)
        executable.chmod(0o700)
        plain, tls, websocket = journey.available_ports()
        clients, transcripts, process = [], [], None
        with authority(backend, runtime) as (env, sql), log.open("w") as output:
            env.update(CRITICAL_COMMAND_JOURNAL_DIR=str(critical), DURIS_TLS_PORT=str(tls),
                       DURIS_WEBSOCKET_PORT=str(websocket),
                       DURIS_PERSISTENCE_TRACE="1",
                       MAINTENANCE_STATE_FILE=str(runtime / "maintenance.state"))

            def boot():
                nonlocal process
                offset = log.stat().st_size
                process = subprocess.Popen([str(executable), "-d", str(runtime), str(plain)],
                                           cwd=runtime, env=env, stdout=output, stderr=subprocess.STDOUT)
                deadline = time.monotonic() + 120
                while b"Entering game loop." not in log.read_bytes()[offset:]:
                    assert process.poll() is None and time.monotonic() < deadline, log.read_text(errors="replace")[-5000:]
                    time.sleep(.1)

            def stop(crash=False):
                for client in clients:
                    transcripts.append(bytes(client.transcript))
                    client.close()
                clients.clear()
                process.send_signal(signal.SIGKILL if crash else signal.SIGTERM)
                process.wait(timeout=60)
                assert process.returncode == (-signal.SIGKILL if crash else 0)
                assert (runtime / "shopkeeper-boot/state").read_bytes() == (b"R" if crash else b"C")

            def login(name, account):
                client = journey.reconnect_character(plain, expected_room=None, account=account, character=name)
                clients.append(client)
                client.expect("Welcome to Duris", timeout=60)
                client.expect_any(("Pos: standing >", "<>"), timeout=30)
                command(client, "toggle paging no")
                return client

            def save(client, name):
                client.send("save")
                client.expect("Save complete for " + name + ".", timeout=60)
                command(client, "score")

            def action(text, receipt):
                player.send(text)
                player.expect(receipt, timeout=60)
                command(player, "score")

            def visit(room):
                assert "No room exists" not in command(god, f"goto {room}")
                command(god, "setbit room here flag ROOM_MAGIC_LIGHT 1")
                command(god, "setbit room here flag SAFE 1")
                assert "Ok." in command(god, "transfer " + PLAYER)
                command(god, f"setbit char {PLAYER} platinum 100000")
                # A real produced purchase checkpoints SQL's dirty restored
                # keeper through its normal trade completion. Flat-file trades
                # already commit their catalog; also exercise production there.
                keyword = "wand" if room == MAGGEYNEL else "ration"
                action("buy " + keyword, "You now have")
                command(player, "drop " + keyword)

            def stock(room):
                keeper = 83189 if room == MAGGEYNEL else KEEPER
                if sql:
                    rows = sql("SELECT i.obj_uid,i.vnum,COALESCE(p.obj_uid,0),i.equip_slot,i.cost "
                               "FROM shopkeeper_items i JOIN shopkeepers s ON s.id=i.shopkeeper_id "
                               f"LEFT JOIN shopkeeper_items p ON p.id=i.container_id "
                               f"WHERE s.room_vnum={room} AND s.mob_vnum={keeper}")
                else:
                    rows = subprocess.check_output([str(inspector), env["FLATFILE_STATE_DIR"], str(room), str(keeper)], text=True)
                return sorted([dict(zip(("uid", "vnum", "parent", "slot", "cost"), map(int, row.split("\t"))))
                               for row in rows.splitlines()], key=lambda item: item["uid"])

            def roots(rows, vnum):
                return [row for row in rows if row["vnum"] == vnum and not row["parent"] and not row["slot"]]

            def settled_stock(room, expected):
                deadline = time.monotonic() + 45
                while True:
                    rows = stock(room)
                    if all(len(roots(rows, vnum)) == count for vnum, count in expected.items()):
                        return rows
                    assert time.monotonic() < deadline, (room, expected, rows)
                    time.sleep(.2)

            try:
                boot()
                for name, account in ((PLAYER, ACCOUNT), (GOD, GOD_ACCOUNT)):
                    client = journey.MudClient(plain)
                    clients.append(client)
                    journey.create_character(client, expected_room=None, account=account, character=name,
                                             email=name.lower() + "@example.invalid")
                    save(client, name)
                stop()
                if sql:
                    sql(f"UPDATE player_data SET level=62,highest_level=62 WHERE name='{GOD}'")
                else:
                    journey.make_overlord(Path(env["FLATFILE_STATE_DIR"]), GOD)
                boot()
                god, player = login(GOD, GOD_ACCOUNT), login(PLAYER, ACCOUNT)
                command(player, "drop all")
                visit(MAGGEYNEL)
                listing = command(player, "list").lower()
                assert "bottomless bag" in listing and "see invisible" in listing, listing
                action("buy bottomless", "You now have a bottomless bag")
                action("buy yellow", "You now have a yellow potion")
                save(player, PLAYER)
                settled_stock(MAGGEYNEL, {BOTTOMLESS: 0, POTION: 0})
                assert "wand" in command(player, "list").lower()
                save(god, GOD)
                stop()
                boot()
                god, player = login(GOD, GOD_ACCOUNT), login(PLAYER, ACCOUNT)
                visit(MAGGEYNEL)
                replenished = settled_stock(MAGGEYNEL, {BOTTOMLESS: 1, POTION: 1})
                evidence["checks"].append("Maggeynel finite bag and potion return after buy/save/clean reboot")

                visit(ROOM)
                initial = settled_stock(ROOM, {BAG: 1, TRINKET: 2, SMALL_BAG: 1})
                unsold = roots(initial, SMALL_BAG)
                action("buy purchasebag", "You now have a purchase bag.")
                action("buy trinket", "You now have a finite stock trinket.")
                action("buy trinket", "You now have a finite stock trinket.")
                action("sell trinket", "The shopkeeper gives you")
                action("sell yellow", "The shopkeeper gives you")
                save(player, PLAYER)
                partial = settled_stock(ROOM, {BAG: 0, TRINKET: 1, POTION: 1})
                resale = roots(partial, POTION)
                retained_trinket = roots(partial, TRINKET)
                save(god, GOD)
                stop()
                boot()
                god, player = login(GOD, GOD_ACCOUNT), login(PLAYER, ACCOUNT)
                visit(ROOM)
                refilled = settled_stock(ROOM, {BAG: 1, TRINKET: 2, SMALL_BAG: 1, POTION: 1})
                assert roots(refilled, SMALL_BAG) == unsold
                assert roots(refilled, POTION) == resale
                assert all(item in roots(refilled, TRINKET) for item in retained_trinket)
                bag = roots(refilled, BAG)[0]
                assert any(item["parent"] == bag["uid"] and item["vnum"] == TRINKET for item in refilled)
                finite = [item for item in refilled if item["vnum"] != RATION]
                evidence["checks"].append("partial stock tops up; unsold/resale UIDs and cost survive; new bag retains its child")
                save(player, PLAYER)
                save(god, GOD)
                stop()
                boot()
                god, player = login(GOD, GOD_ACCOUNT), login(PLAYER, ACCOUNT)
                visit(ROOM)
                repeated = settled_stock(ROOM, {BAG: 1, TRINKET: 2, SMALL_BAG: 1, POTION: 1})
                assert [item for item in repeated if item["vnum"] != RATION] == finite
                evidence["checks"].append("another clean reboot does not duplicate or replace unsold stock")

                visit(MAGGEYNEL)
                unchanged = settled_stock(MAGGEYNEL, {BOTTOMLESS: 1, POTION: 1})
                assert roots(unchanged, BOTTOMLESS) == roots(replenished, BOTTOMLESS)
                action("buy bottomless", "You now have a bottomless bag")
                action("buy yellow", "You now have a yellow potion")
                save(player, PLAYER)
                settled_stock(MAGGEYNEL, {BOTTOMLESS: 0, POTION: 0})
                process.send_signal(signal.SIGUSR1)
                player.expect("Copyover complete!", timeout=180)
                settled_stock(MAGGEYNEL, {BOTTOMLESS: 0, POTION: 0})
                assert "wand" in command(player, "list").lower()
                save(player, PLAYER)
                stop(crash=True)
                boot()
                god, player = login(GOD, GOD_ACCOUNT), login(PLAYER, ACCOUNT)
                visit(MAGGEYNEL)
                settled_stock(MAGGEYNEL, {BOTTOMLESS: 0, POTION: 0})
                assert "bottomless bag" not in command(player, "list").lower()
                evidence["checks"].append("copyover and crash without Redis retain sold-out finite stock")
                save(player, PLAYER)
                save(god, GOD)
                stop()
                boot()
                god, player = login(GOD, GOD_ACCOUNT), login(PLAYER, ACCOUNT)
                visit(MAGGEYNEL)
                settled_stock(MAGGEYNEL, {BOTTOMLESS: 1, POTION: 1})
                stop()
                evidence["checks"].append("clean stop after crash restores eligibility for the next cold reboot")
                evidence["passed"] = True
                print("[PASS]", backend, "finite shop stock journeys", flush=True)
            finally:
                if process is not None and process.poll() is None:
                    for client in clients:
                        client.close()
                    process.terminate()
                    process.wait(timeout=60)
                report.write_text(json.dumps(evidence, indent=2) + "\n")
                report.with_suffix(".log").write_bytes(log.read_bytes())
                report.with_suffix(".runtime.log").write_text("\n".join(
                    str(path.relative_to(runtime)) + "\n" + path.read_text(errors="replace")
                    for path in (runtime / "logs").rglob("*") if path.is_file()))
                report.with_suffix(".transcript.log").write_bytes(b"\n".join(
                    transcripts + [bytes(client.transcript) for client in clients]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("flatfile", "mariadb"), default="flatfile")
    parser.add_argument("--server", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    (ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
    subprocess.run(["make", "build-area-tools"], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    run(args.server.resolve(), args.backend, args.report.resolve())
