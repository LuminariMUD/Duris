#!/usr/bin/env python3
"""Real shop commands and cold restart on disposable flat-file/MariaDB state."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import struct
import subprocess
import tempfile
import time

import test_flatfile_combat_journey as journey
from test_flight_network_journey import authority, command
from run_world_quest_dual_backend import setup_run_root

ROOT = journey.ROOT
PLAYER, ACCOUNT = "Shopbuyer", "Shopacct"
GOD, GOD_ACCOUNT = "Shopwarden", "Shopstaff"
ROOM, KEEPER, BAG, RATION, SMALL_BAG, TRINKET = 45035, 1258, 1258, 1259, 1260, 1261


def fixture(runtime):
    # Full-world boot owns shop registration. Keep source copies and every
    # generated world/lookup file inside this disposable runtime.
    areas = runtime / "areas"
    assert areas.is_symlink() and areas.resolve() == (ROOT / "areas").resolve()
    areas.unlink()
    shutil.copytree(ROOT / "areas", areas)
    tools = runtime / "bin/areas/tools"
    tools.parent.mkdir(parents=True)
    tools.symlink_to(ROOT / "bin/areas/tools", target_is_directory=True)
    mobs = areas / "mob/heavens.mob"
    mobs.write_text(mobs.read_text() + f"""#{KEEPER}
shopkeeper provisioner~
the test provisioner~
The test provisioner is ready to sell supplies.
~
~
10 0 0 0 0 0 0 0 S
PH 0 0 -1
1 0 0 1d1+1 1d1+1
0.0.0.0 0
8 8 0
""")
    objects = areas / "obj/heavens.obj"
    additions = ""
    for vnum, name, short, kind, capacity, weight, cost in (
        (BAG, "bag purchasebag", "a purchase bag", 15, 1000, 0, 10),
        (RATION, "ration food", "a test ration", 19, 0, 1, 10),
        (SMALL_BAG, "smallbag", "a small purchase bag", 15, 3, 0, 10),
        (TRINKET, "trinket", "a finite stock trinket", 8, 0, 1, 20),
    ):
        additions += f"""#{vnum}
{name}~
{short}~
{short.capitalize()} is here.~
~
{kind} 15 3 0 7 0 0 1 0 0 0
{capacity} 1 0 0 0 0 0 0
{weight} {cost} 100
"""
    original = objects.read_text()
    assert not any(re.search(rf"^#{vnum}$", original, re.M) for vnum in (BAG, RATION, SMALL_BAG, TRINKET))
    # The engine binary-searches prototype indexes; keep the fixture records
    # in the existing gap before vnum 1270.
    objects.write_text(original.replace("#1270\n", additions + "#1270\n", 1))
    shop = (ROOT / "areas/shp/newbie.shp").read_text().split("#29206~")[0]
    shop = re.sub(r"(?s)N\n.*?\n0\n", f"N\n{RATION}\n0\n", shop, count=1)
    shop = shop.replace("#29201~", f"#{KEEPER}~")
    shop = shop.replace("\n29201\n0\n29201\n", f"\n{KEEPER}\n0\n{ROOM}\n")
    shop = shop.replace("0.80\n1.10\n0\n", "0.80\n1.10\n19\n15\n8\n0\n")
    end = areas / "shp/end.shp"
    end.write_text(end.read_text().replace("$~", shop + "$~"))
    zone = areas / "zon/charing.zon"
    zone.write_text(zone.read_text().replace("\nS\n", f"\nM 0 {KEEPER} 1 {ROOM} 100 0 0 0\nS\n"))
    generated = subprocess.run(["./m_slow"], cwd=areas, capture_output=True, text=True)
    assert generated.returncode == 0, generated.stdout[-4000:] + generated.stderr[-4000:]


def run(binary, backend, report):
    report.parent.mkdir(parents=True, exist_ok=True)
    evidence = {"backend": backend, "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
                "purchases": [], "checks": [], "passed": False}
    inspector = ROOT / "bin/tests/shop-multi-buy-inspector"
    if backend == "flatfile":
        subprocess.run(["python3", "tests/async/test_flatfile_player_repository.py",
                        "--build-inspector", str(inspector)], cwd=ROOT, check=True)
    with tempfile.TemporaryDirectory(prefix="shop-journey-", dir=ROOT / "bin/tests") as temporary:
        runtime = Path(temporary)
        _, critical, log = setup_run_root(runtime)
        fixture(runtime)
        plain, tls, websocket = journey.available_ports()
        clients, process = [], None
        with authority(backend, runtime) as (env, sql), log.open("w") as output:
            env.update(CRITICAL_COMMAND_JOURNAL_DIR=str(critical), DURIS_TLS_PORT=str(tls),
                       DURIS_WEBSOCKET_PORT=str(websocket),
                       MAINTENANCE_STATE_FILE=str(runtime / "maintenance.state"))

            def boot():
                nonlocal process
                offset = log.stat().st_size
                process = subprocess.Popen([str(binary), "-d", str(runtime), str(plain)],
                                           cwd=runtime, env=env, stdout=output, stderr=subprocess.STDOUT)
                deadline = time.monotonic() + 120
                while b"Entering game loop." not in log.read_bytes()[offset:]:
                    assert process.poll() is None and time.monotonic() < deadline, log.read_text(errors="replace")[-5000:]
                    time.sleep(.1)

            def stop():
                for client in clients:
                    client.close()
                clients.clear()
                process.send_signal(signal.SIGTERM)
                process.wait(timeout=60)
                assert process.returncode == 0

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

            def action(client, text, receipt):
                # Legacy trades can accept the following score before their
                # authority callback. Wait for the trade's own receipt first.
                start = len(client.transcript)
                client.send(text)
                client.expect(receipt, timeout=60)
                response = bytes(client.transcript[start:]).decode(errors="replace")
                command(client, "score")
                return response

            def inspect():
                if sql:
                    wallet = [int(value) for value in sql(
                        f"SELECT copper,silver,gold,platinum FROM player_data WHERE name='{PLAYER}'").split("\t")]
                    # Saved physical rows are MariaDB's live inventory source;
                    # legacy sales can leave historical custody-only records.
                    rows = sql("SELECT i.item_uid,i.vnum,i.root_item_uid,COALESCE(i.parent_item_uid,0),"
                               "COALESCE(parent.obj_uid,0) FROM item_current_owner i "
                               "JOIN player_items physical ON physical.obj_uid=i.item_uid AND physical.pid=i.owner_id "
                               "LEFT JOIN player_items parent ON parent.id=physical.container_id "
                               f"JOIN player_data p ON p.pid=i.owner_id WHERE i.owner_type=1 AND p.name='{PLAYER}' "
                               "AND i.state=1 ORDER BY i.item_uid")
                    items = [dict(zip(("uid", "vnum", "root", "parent", "physical_parent"), map(int, row.split("\t"))))
                             for row in rows.splitlines()]
                    return {"wallet": wallet, "player_items": items}
                return json.loads(subprocess.check_output([str(inspector), env["FLATFILE_STATE_DIR"], "inspect", "1"], text=True))

            def operations():
                if sql:
                    return int(sql("SELECT COUNT(*) FROM critical_operation_inbox WHERE command_type=5"))
                path = Path(env["FLATFILE_STATE_DIR"]) / "domains/shop_trade_operations"
                return struct.unpack_from("<I", path.read_bytes(), 56)[0] if path.exists() else 0

            def money(god, platinum=100, copper=0):
                for denomination, amount in (("platinum", platinum), ("gold", 0), ("silver", 0), ("copper", copper)):
                    command(god, f"setbit char {PLAYER} {denomination} {amount}")
                save(player, PLAYER)

            def purchase(count, container="bag", delivered=None):
                delivered = count if delivered is None else delivered
                before = operations()
                start = time.monotonic()
                transcript_start = len(player.transcript)
                raw_start = len(player.raw_transcript)
                player.send(f"buy ration {container} {count}")
                receipt = (f"{delivered} of {count} items delivered" if count > 1 else
                           "You now have a test ration.")
                player.expect(receipt, timeout=60)
                player.expect(">", timeout=30)
                deadline = time.monotonic() + 5
                while b"\xff\xf9" not in player.raw_transcript[raw_start:]:
                    assert time.monotonic() < deadline, "purchase prompt lacks Telnet GA"
                    player._receive()
                elapsed = time.monotonic() - start
                response = bytes(player.transcript[transcript_start:]).decode(errors="replace")
                command(player, "score")
                assert response.count("You now have a test ration.") == delivered, response
                if count > 1:
                    assert f"{delivered} of {count} items delivered" in response, response
                assert operations() == before + 1, "purchase did not use one authority command"
                save(player, PLAYER)
                evidence["purchases"].append({"requested": count, "delivered": delivered,
                                               "seconds": elapsed, "authority_operations": 1})

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
                assert "No room exists" not in command(god, f"goto {ROOM}")
                assert "Ok." in command(god, "transfer " + PLAYER)
                command(god, "setbit room here flag ROOM_MAGIC_LIGHT 1")
                command(god, "setbit room here flag SAFE 1")
                command(player, "drop all")
                for vnum, keyword in ((BAG, "bag"), (SMALL_BAG, "smallbag")):
                    loaded = command(god, f"load obj {vnum}")
                    assert "created" in loaded, loaded
                    assert "Ok." in command(god, f"give {keyword} {PLAYER}")
                assert "created" in command(god, f"load obj {BAG}")
                money(god)
                # Qualify the carried bag as restored ordinary player state;
                # legacy MariaDB GIVE leaves its old runtime custody cache
                # until reload even though the player's save claims the item.
                save(god, GOD)
                stop()
                boot()
                god, player = login(GOD, GOD_ACCOUNT), login(PLAYER, ACCOUNT)
                command(god, f"goto {ROOM}")
                command(god, "transfer " + PLAYER)
                listing = command(player, "list")
                assert "ration" in listing.lower(), listing
                initial = inspect()
                purchase(1)
                after_one = inspect()
                value = lambda state: sum(amount * unit for amount, unit in zip(state["wallet"], (1, 10, 100, 1000)))
                unit_price = value(initial) - value(after_one)
                assert unit_price > 0
                # Exercise the legacy SMARTPROMPT output path directly; its
                # player toggle is retired. Await the purchase's prompt and GA
                # without sending another command to restore prompt_mode.
                command(god, f"setbit char {PLAYER} pcact SMARTPROMPT on")
                for count in (2, 12, 13, 20, 50):
                    before = inspect()
                    purchase(count)
                    after = inspect()
                    assert value(before) - value(after) == unit_price * count
                command(god, f"setbit char {PLAYER} pcact SMARTPROMPT off")
                evidence["checks"].append("smart-prompt purchases restore the prompt and Telnet GA without further input")
                money(god, platinum=0, copper=unit_price * 7)
                purchase(20, delivered=7)
                assert value(inspect()) == 0
                money(god)
                purchase(20, container="smallbag", delivered=3)
                before = inspect()
                before_ops = operations()
                command(player, "close bag")
                response = command(player, "buy ration bag 20")
                assert "You now have" not in response and operations() == before_ops
                command(player, "open bag")
                for invalid in ("0", "51", "2junk", "2 extra"):
                    response = command(player, "buy ration bag " + invalid)
                    assert "nothing was purchased" in response, response
                save(player, PLAYER)
                assert inspect()["wallet"] == before["wallet"]
                evidence["checks"].append("mortal quantities, partial funds/capacity, closed bag and invalid arguments")
                response = command(player, "buy ration")
                assert "You now have a test ration." in response, response
                sold_ration = action(player, "sell ration", "The shopkeeper gives you")
                assert "gives you" in sold_ration, sold_ration
                save(player, PLAYER)
                assert "created" in command(god, f"load obj {TRINKET}")
                assert "Ok." in command(god, "give trinket " + PLAYER)
                sold_trinket = action(player, "sell trinket", "The shopkeeper gives you")
                assert "gives you" in sold_trinket, sold_trinket
                save(player, PLAYER)
                assert "You now have a finite stock trinket." in action(
                    player, "buy trinket", "You now have a finite stock trinket.")
                save(player, PLAYER)
                evidence["checks"].append("single inventory purchase, produced sale and finite-stock sell/buy")
                staff_coins = re.search(r"Coins carried:[^\r\n]+", command(god, "score"))[0]
                before_ops = operations()
                free_purchase = command(god, "buy ration purchasebag 20", timeout=60)
                assert free_purchase.count("You now have a test ration.") == 20, free_purchase
                assert "20 of 20 items delivered" in free_purchase and operations() == before_ops + 1
                assert re.search(r"Coins carried:[^\r\n]+", command(god, "score"))[0] == staff_coins
                evidence["checks"].append("trusted purchase delivers twenty items in one operation without charging")
                if backend == "flatfile":
                    # LOAD deliberately waits for a holder's next save. The free
                    # purchase must establish this fresh bag before claiming it.
                    assert "created" in command(god, f"load obj {BAG}")
                    before_ops = operations()
                    free_fresh = action(god, "buy ration purchasebag 2", "2 of 2 items delivered")
                    assert free_fresh.count("You now have a test ration.") == 2 and operations() == before_ops + 1
                    evidence["checks"].append("free purchase into an unsaved staff bag preserves readable custody")
                save(god, GOD)
                save(player, PLAYER)
                completed = inspect()
                bags = {row["vnum"]: row["uid"] for row in completed["player_items"] if row["vnum"] in (BAG, SMALL_BAG)}
                purchased = [row for row in completed["player_items"] if row["vnum"] == RATION]
                assert len(purchased) == 108 and len({row["uid"] for row in purchased}) == 108, len(purchased)
                assert sum(row["parent"] == bags[BAG] for row in purchased) == 105
                assert sum(row["parent"] == bags[SMALL_BAG] for row in purchased) == 3
                if sql:
                    assert all(row["physical_parent"] == row["parent"] for row in purchased)
                stop()
                boot()
                god, player = login(GOD, GOD_ACCOUNT), login(PLAYER, ACCOUNT)
                assert "test ration" in command(player, "look in bag")
                save(player, PLAYER)
                restored = inspect()
                assert restored["wallet"] == completed["wallet"]
                assert restored["player_items"] == completed["player_items"], "cold restart changed purchase identities/topology"
                evidence["checks"].append("cold restart preserves all 108 ration UIDs, parentage and wallet")
                evidence["passed"] = True
                stop()
                print("[PASS]", backend, "real shop batches and cold restart", flush=True)
            finally:
                if process is not None and process.poll() is None:
                    for client in clients:
                        client.close()
                    process.terminate()
                    process.wait(timeout=60)
                report.write_text(json.dumps(evidence, indent=2) + "\n")
                report.with_suffix(".log").write_bytes(log.read_bytes())
                diagnostic = []
                for path in (runtime / "logs").rglob("*"):
                    if path.is_file() and path.name != ".gitignore":
                        diagnostic.append(str(path.relative_to(runtime)) + "\n" +
                                          path.read_text(errors="replace")[-20000:])
                report.with_suffix(".runtime.log").write_text("\n".join(diagnostic))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("flatfile", "mariadb"), default="flatfile")
    parser.add_argument("--server", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    (ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
    subprocess.run(["make", "build-area-tools"], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    with tempfile.TemporaryDirectory(prefix="shop-build-", dir=ROOT / "bin/tests") as build:
        if args.server:
            binary = args.server.resolve()
        else:
            assert args.backend == "flatfile", "pass a MariaDB executable with --server"
            binary = journey.build_flatfile_server(Path(build) / "server")
        run(binary, args.backend, args.report or ROOT / f"bin/qualification/issue454/{args.backend}-journey.json")


if __name__ == "__main__":
    main()
