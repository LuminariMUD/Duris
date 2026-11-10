#!/usr/bin/env python3
"""Real shop commands and cold restart on disposable MariaDB state."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import tempfile
import time

import test_mariadb_combat_journey as journey
from test_flight_network_journey import authority, command
from run_world_quest_dual_backend import setup_run_root

ROOT = journey.ROOT
PLAYER, ACCOUNT = "Shopbuyer", "Shopacct"
GOD, GOD_ACCOUNT = "Shopwarden", "Shopstaff"
ROOM, KEEPER, BAG, RATION, SMALL_BAG, TRINKET = 45016, 1258, 1258, 1259, 1260, 1261


def fixture(runtime, *, reboot_stock=False, room=ROOM):
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
    shop = shop.replace("\n29201\n0\n29201\n", f"\n{KEEPER}\n0\n{room}\n")
    shop = shop.replace("0.80\n1.10\n0\n", "0.80\n1.10\n19\n15\n8\n0\n")
    if reboot_stock:
        shop = shop.replace("1.10\n19\n", "1.10\n10\n19\n")
    end = areas / "shp/end.shp"
    end.write_text(end.read_text().replace("$~", shop + "$~"))
    zone = areas / "zon/charing.zon"
    stock = (f"G 1 {BAG} 99 0 100 0 0 0\n"
             f"P 1 {TRINKET} 99 {BAG} 100 0 0 0\n"
             f"G 1 {TRINKET} 99 0 100 0 0 0\n"
             f"G 1 {TRINKET} 99 0 100 0 0 0\n"
             f"G 1 {SMALL_BAG} 99 0 100 0 0 0\n") if reboot_stock else ""
    zone.write_text(zone.read_text().replace("\nS\n", f"\nM 0 {KEEPER} 1 {room} 100 0 0 0\n{stock}S\n"))
    generated = subprocess.run(["./m_slow"], cwd=areas, capture_output=True, text=True)
    assert generated.returncode == 0, generated.stdout[-4000:] + generated.stderr[-4000:]


def run(binary, backend, report, crash_paid_fresh=False):
    report.parent.mkdir(parents=True, exist_ok=True)
    evidence = {"backend": backend, "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
                "purchases": [], "checks": [], "passed": False}
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
                client.expect("Saving " + name + ".", timeout=60)
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
                wallet = [int(value) for value in sql(
                    f"SELECT copper,silver,gold,platinum FROM player_data WHERE name='{PLAYER}'").split("\t")]
                # Saved physical rows are MariaDB's live inventory source;
                # legacy sales can leave historical custody-only records.
                rows = sql("SELECT i.item_uid,i.vnum,i.root_item_uid,COALESCE(i.parent_item_uid,0),"
                           "COALESCE(parent.obj_uid,0),i.item_revision FROM item_current_owner i "
                           "JOIN player_items physical ON physical.obj_uid=i.item_uid AND physical.pid=i.owner_id "
                           "LEFT JOIN player_items parent ON parent.id=physical.container_id "
                           f"JOIN player_data p ON p.pid=i.owner_id WHERE i.owner_type=1 AND p.name='{PLAYER}' "
                           "AND i.state=1 ORDER BY i.item_uid")
                items = [dict(zip(("uid", "vnum", "root", "parent", "physical_parent", "revision"), map(int, row.split("\t"))))
                         for row in rows.splitlines()]
                return {"wallet": wallet, "player_items": items}

            def operations():
                return int(sql("SELECT COUNT(*) FROM critical_operation_inbox WHERE command_type=5"))

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
                sql(f"UPDATE player_data SET level=62,highest_level=62 WHERE name='{GOD}'")
                boot()
                god, player = login(GOD, GOD_ACCOUNT), login(PLAYER, ACCOUNT)
                assert "No room exists" not in command(god, f"goto {ROOM}")
                assert "Ok." in command(god, "transfer " + PLAYER)
                command(god, "setbit room here flag ROOM_MAGIC_LIGHT 1")
                command(god, "setbit room here flag SAFE 1")
                command(player, "drop all")
                if crash_paid_fresh:
                    money(god)
                for vnum, keyword in ((BAG, "bag"), (SMALL_BAG, "smallbag")):
                    loaded = command(god, f"load obj {vnum}")
                    assert "created" in loaded, loaded
                    assert "Ok." in command(god, f"give {keyword} {PLAYER}")
                if crash_paid_fresh:
                    # A fresh bag has no saved owner. The debit and produced UID
                    # must survive the same crash, even before the output callback.
                    def financial_state():
                        row = sql(
                            "SELECT p.copper+10*p.silver+100*p.gold+1000*p.platinum,"
                            "(SELECT COUNT(*) FROM item_current_owner o JOIN player_items i "
                            "ON i.obj_uid=o.item_uid WHERE o.owner_type=1 AND o.owner_id=p.pid "
                            f"AND o.state=1 AND i.vnum={RATION}) FROM player_data p "
                            f"WHERE p.name='{PLAYER}'")
                        return tuple(map(int, row.split("\t")))

                    # A first paid purchase raises the wallet revision. The next one into a
                    # different fresh bag must still read that revision after preparing the bag.
                    first_wallet, first_items = financial_state()
                    assert first_wallet == 100000 and first_items == 0
                    player.send("buy ration smallbag 1")
                    deadline = time.monotonic() + 30
                    while financial_state()[1] != 1:
                        assert time.monotonic() < deadline, "first paid fresh-bag purchase never committed"
                        time.sleep(.05)
                    before_wallet, before_items = financial_state()
                    assert before_wallet < first_wallet and before_items == 1
                    player.send("buy ration bag 1")
                    deadline = time.monotonic() + 15
                    while time.monotonic() < deadline:
                        wallet, items = financial_state()
                        if wallet < before_wallet:
                            os.kill(process.pid, signal.SIGSTOP)
                            break
                        time.sleep(.005)
                    else:
                        raise AssertionError("paid fresh-bag purchase did not commit")
                    paid_wallet, paid_items = financial_state()
                    assert paid_wallet == wallet and paid_items == items
                    process.kill()
                    process.wait(timeout=10)
                    for client in clients:
                        client.close()
                    clients.clear()
                    boot()
                    player = login(PLAYER, ACCOUNT)
                    restored_wallet, restored_items = financial_state()
                    assert (restored_wallet, restored_items) == (paid_wallet, paid_items)
                    assert 0 < before_wallet - restored_wallet < before_wallet
                    assert restored_items == 2, (
                        "paid fresh-bag purchase lost the item after crash",
                        before_wallet, restored_wallet, restored_items)
                    uid, parent, physical_parent = map(int, sql(
                        "SELECT o.item_uid,COALESCE(o.parent_item_uid,0),"
                        "COALESCE(b.obj_uid,0) FROM item_current_owner o "
                        "JOIN player_items i ON i.obj_uid=o.item_uid "
                        "LEFT JOIN player_items b ON b.id=i.container_id "
                        f"WHERE o.owner_type=1 AND o.owner_id=(SELECT pid FROM player_data WHERE name='{PLAYER}') "
                        f"AND o.state=1 AND i.vnum={RATION} AND b.vnum={BAG}").split("\t"))
                    assert uid and parent and parent == physical_parent
                    assert "test ration" in command(player, "look in bag")
                    evidence["paid_fresh_bag_crash"] = {
                        "wallet_before": before_wallet, "wallet_after": restored_wallet,
                        "item_uid": uid, "parent_uid": parent}
                    evidence["passed"] = True
                    print("PASS paid fresh-bag wallet, item UID and parent across SIGKILL/restart", flush=True)
                    return
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
                save(god, GOD)
                assert "Ok." in command(god, "give trinket " + PLAYER)
                save(player, PLAYER)
                # Hydrate this revision, then ordinary handoffs/save claims leave
                # that cache behind. Sale/buyback must publish exact later versions.
                stop(); boot()
                god, player = login(GOD, GOD_ACCOUNT), login(PLAYER, ACCOUNT)
                command(god, f"goto {ROOM}")
                command(god, "transfer " + PLAYER)
                command(god, "vis 0")
                command(god, "setbit room here flag ROOM_MAGIC_LIGHT 1")
                response = command(player, "give trinket " + GOD)
                assert "Ok." in response, response
                save(god, GOD)
                assert "Ok." in command(god, "give trinket " + PLAYER)
                save(player, PLAYER)
                before_trade = next(row for row in inspect()["player_items"] if row["vnum"] == TRINKET)
                sold_trinket = action(player, "sell trinket", "The shopkeeper gives you")
                assert "gives you" in sold_trinket, sold_trinket
                save(player, PLAYER)
                assert "You now have a finite stock trinket." in action(
                    player, "buy trinket", "You now have a finite stock trinket.")
                save(player, PLAYER)
                after_trade = next(row for row in inspect()["player_items"] if row["vnum"] == TRINKET)
                assert after_trade["uid"] == before_trade["uid"] and after_trade["revision"] == before_trade["revision"] + 2
                evidence["checks"].append("single inventory purchase, produced sale and finite-stock sell/buy")
                evidence["checks"].append("ordinary handoff claims followed by exact-revision sale and buyback")
                staff_coins = re.search(r"Coins carried:[^\r\n]+", command(god, "score"))[0]
                before_ops = operations()
                free_purchase = command(god, "buy ration purchasebag 20", timeout=60)
                assert free_purchase.count("You now have a test ration.") == 20, free_purchase
                assert "20 of 20 items delivered" in free_purchase and operations() == before_ops + 1
                assert re.search(r"Coins carried:[^\r\n]+", command(god, "score"))[0] == staff_coins
                evidence["checks"].append("trusted purchase delivers twenty items in one operation without charging")
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
                command(god, f"goto {ROOM}")
                command(god, "transfer " + PLAYER)
                # Trusted quit is immediate; this controls actor unload
                # without introducing a camp timer into the writer stall.
                command(god, "setbit char " + PLAYER + " level 62")
                command(god, "setbit char " + PLAYER + " pcact MORTALIZED off")
                before_quit = inspect()
                trinket_uid = next(row["uid"] for row in before_quit["player_items"] if row["vnum"] == TRINKET)
                # Sales apply in memory; their snapshots catch up on the writer.
                # Hold the actual player/shop/log tables through quit, then prove
                # the offline save and buyback settle exactly once after release.
                held = subprocess.Popen(
                    ["mysql", "--protocol=tcp", "--skip-ssl", "-h", env["DB_HOST"],
                     "-P", env["DB_PORT"], "-u", env["DB_USER"], "-N", "-B",
                     "--unbuffered", env["DB_NAME"]], stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE, text=True, env=env, bufsize=1)
                try:
                    held.stdin.write("LOCK TABLES player_items WRITE, shopkeeper_items WRITE, log_entries WRITE; SELECT 'held';\n")
                    held.stdin.flush()
                    assert held.stdout.readline().strip() == "held"
                    player.send("sell trinket\nquit")
                    player.expect("The shopkeeper gives you", timeout=5)
                    player.expect("ACCOUNT MENU", timeout=30)
                finally:
                    held.communicate("UNLOCK TABLES;\n", timeout=15)
                    assert held.returncode == 0
                player.close(); clients.remove(player)
                player = login(PLAYER, ACCOUNT)
                save(player, PLAYER)
                paid = inspect()
                value = lambda wallet: sum(amount * (10 ** index) for index, amount in enumerate(wallet))
                assert value(paid["wallet"]) > value(before_quit["wallet"]), "offline sale lost its payment"
                assert all(row["uid"] != trinket_uid for row in paid["player_items"]), "offline sale returned its sold UID"
                assert {row["uid"] for row in paid["player_items"] if row["vnum"] == RATION} == {row["uid"] for row in purchased}
                stop(); boot()
                god, player = login(GOD, GOD_ACCOUNT), login(PLAYER, ACCOUNT)
                save(player, PLAYER)
                assert inspect()["wallet"] == paid["wallet"], "offline sale paid twice after restart"
                command(god, f"goto {ROOM}"); command(god, "transfer " + PLAYER)
                assert "finite stock trinket" in action(player, "buy trinket", "You now have a finite stock trinket.")
                save(player, PLAYER)
                assert next(row["uid"] for row in inspect()["player_items"] if row["vnum"] == TRINKET) == trinket_uid
                evidence["checks"].append("memory sale and quit behind a stalled SQL writer: payment once, no returned sold UID, stable buyback after restart")
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
    parser.add_argument("--backend", choices=("mariadb",), default="mariadb")
    parser.add_argument("--server", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--crash-paid-fresh", action="store_true")
    args = parser.parse_args()
    if args.crash_paid_fresh and args.backend != "mariadb":
        parser.error("crash-paid-fresh requires MariaDB")
    (ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
    subprocess.run(["make", "build-area-tools"], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    with tempfile.TemporaryDirectory(prefix="shop-build-", dir=ROOT / "bin/tests") as build:
        if args.server:
            binary = args.server.resolve()
        else:
            binary = journey.build_mariadb_server(Path(build) / "server")
        run(binary, args.backend, args.report or ROOT / f"bin/qualification/issue454/{args.backend}-journey.json", args.crash_paid_fresh)


if __name__ == "__main__":
    main()
