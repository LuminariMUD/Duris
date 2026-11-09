#!/usr/bin/env python3
"""Native named-set player, private-chest, shop and world storage on MariaDB.

Run through with_disposable_mariadb.sh. Uses the already generated private world
from the named-set area journeys, but creates a separate authority and accounts.
Artifacts remain under bin/tests; no checkout .env or existing player is used.
"""

import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time

import test_mariadb_combat_journey as journey
from test_flight_network_journey import authority
from named_set_gameplay import (
    enable_items, expect_max_hp, get_from_container, put, save, score, selector,
)

ROOT = journey.ROOT
OWNER, ACCOUNT = journey.CHARACTER, journey.ACCOUNT
GOD, STAFF = "Chestwarden", "Cheststaff"
LOCKER = "account." + ACCOUNT.lower() + ".1.locker"
ORIGIN = "DURIS_NAMED_SET_ORIGIN_V1"


def run():
    runtime = Path(tempfile.mkdtemp(prefix="named-set-mariadb-", dir=ROOT / "bin/tests"))
    print("Artifacts: " + str(runtime), flush=True)
    world = Path(os.environ.get("NAMED_SET_RUNTIME", ROOT / "bin/tests/named-set-roster-world")) / "areas"
    assert (world / "world.zon").is_file(), "prepare the isolated named-set world first"
    (runtime / "areas").symlink_to(world, target_is_directory=True)
    (runtime / "docs").symlink_to(ROOT / "docs", target_is_directory=True)
    archive = subprocess.Popen(["git", "archive", "HEAD", "lib", "help"], cwd=ROOT,
                               stdout=subprocess.PIPE)
    subprocess.run(["tar", "-x", "-C", str(runtime)], stdin=archive.stdout, check=True)
    archive.stdout.close()
    assert archive.wait() == 0
    for directory in ("logs", "log", "journals/critical"):
        (runtime / directory).mkdir(parents=True, exist_ok=True)
    journey.generate_certificate(runtime)
    binary = ROOT / "bin/server/dms_new"
    plain, tls, websocket = journey.available_ports()
    clients, transcripts = {}, []
    process = output = None
    evidence = {"checks": []}

    with authority("mariadb", runtime) as (env, sql):
        env.update(CRITICAL_COMMAND_JOURNAL_DIR=str(runtime / "journals/critical"),
                   DURIS_TLS_PORT=str(tls), DURIS_WEBSOCKET_PORT=str(websocket),
                   MAINTENANCE_STATE_FILE=str(runtime / "maintenance.state"))

        def check(label):
            evidence["checks"].append(label)
            (runtime / "evidence.json").write_text(json.dumps(evidence, indent=2))
            print("PASS " + label, flush=True)

        def boot(label):
            nonlocal process, output
            log = runtime / (label + ".log")
            output = log.open("w")
            process = subprocess.Popen([str(binary), "-d", str(runtime), str(plain)],
                                       cwd=runtime, env=env, stdout=output,
                                       stderr=subprocess.STDOUT)
            deadline = time.monotonic() + 150
            while "Entering game loop." not in log.read_text(errors="replace"):
                assert process.poll() is None and time.monotonic() < deadline, str(log)
                time.sleep(.1)

        def stop():
            nonlocal process, output
            for client in clients.values():
                transcripts.append(bytes(client.transcript))
                client.close()
            clients.clear()
            if process and process.poll() is None:
                process.send_signal(signal.SIGTERM)
                process.wait(timeout=60)
                assert process.returncode == 0, "unclean shutdown"
            process = None
            if output:
                output.close()
                output = None

        def login(name=OWNER, account=ACCOUNT):
            client = journey.reconnect_character(plain, expected_room=None,
                                                  account=account, character=name)
            clients[name] = client
            client.send("")
            client.expect("Pos:", timeout=30)
            client.expect(">")
            enable_items(client)
            act(client, "toggle paging no")
            return client

        def act(client, text, expected=None):
            evidence["last_command"] = text
            (runtime / "evidence.json").write_text(json.dumps(evidence, indent=2))
            client.send(text)
            if expected:
                client.expect(expected, timeout=30)
            return score(client)[1]

        def player_rows():
            rows = sql("SELECT i.obj_uid,i.vnum,COALESCE(parent.obj_uid,0),i.equip_slot,"
                       "COALESCE(e.description,'-') FROM player_items i "
                       "JOIN player_data p ON p.pid=i.pid "
                       "LEFT JOIN player_items parent ON parent.id=i.container_id "
                       f"LEFT JOIN player_item_extra_descr e ON e.item_id=i.id AND e.keyword='{ORIGIN}' "
                       f"WHERE p.name='{OWNER}' ORDER BY i.obj_uid")
            return {int(parts[0]): [int(value) for value in parts[1:4]] + [parts[4]]
                    for line in rows.splitlines() if (parts := line.split("\t"))}

        def chest_rows():
            rows = sql("SELECT i.obj_uid,i.vnum,COALESCE(parent.obj_uid,0),"
                       "COALESCE(e.description,'-') FROM locker_items i "
                       "JOIN private_chests c ON c.id=i.chest_id JOIN lockers l ON l.id=c.locker_id "
                       "LEFT JOIN locker_items parent ON parent.id=i.container_id "
                       f"LEFT JOIN locker_item_extra_descr e ON e.item_id=i.id AND e.keyword='{ORIGIN}' "
                       f"WHERE l.locker_name='{LOCKER}' AND c.chest_name='vault' ORDER BY i.obj_uid")
            return {int(parts[0]): [int(parts[1]), int(parts[2]), 0, parts[3]]
                    for line in rows.splitlines() if (parts := line.split("\t"))}

        def shop_item(uid):
            rows = sql("SELECT i.vnum,COALESCE(parent.obj_uid,0),i.equip_slot,i.cost,"
                       "COALESCE(e.description,'-') FROM shopkeeper_items i "
                       "JOIN shopkeepers s ON s.id=i.shopkeeper_id "
                       "LEFT JOIN shopkeeper_items parent ON parent.id=i.container_id "
                       f"LEFT JOIN shopkeeper_item_extra_descr e ON e.item_id=i.id AND e.keyword='{ORIGIN}' "
                       f"WHERE s.room_vnum=132500 AND s.mob_vnum=132617 AND i.obj_uid={uid}")
            if not rows:
                return None
            assert len(rows.splitlines()) == 1, rows
            values = rows.split("\t")
            return [int(value) for value in values[:4]] + [values[4]]

        def world_rows():
            rows = sql("SELECT i.obj_uid,i.vnum,COALESCE(parent.obj_uid,0),"
                       "COALESCE(e.description,'-') FROM saved_items i "
                       "LEFT JOIN saved_items parent ON parent.id=i.container_id "
                       f"LEFT JOIN saved_item_extra_descr e ON e.item_id=i.id AND e.keyword='{ORIGIN}' "
                       "WHERE i.room_vnum=132500 ORDER BY i.obj_uid")
            result = {int(parts[0]): [int(parts[1]), int(parts[2]), 0, parts[3]]
                      for line in rows.splitlines() if (parts := line.split("\t"))}
            assert len(result) == len(rows.splitlines()), "duplicate saved-world UID"
            return result

        def wait_world(expected):
            deadline = time.monotonic() + 45
            while True:
                rows = world_rows()
                if rows == expected:
                    return
                assert time.monotonic() < deadline, (rows, expected)
                time.sleep(.2)

        def bank():
            god = login(GOD, STAFF) if GOD not in clients else clients[GOD]
            act(god, "goto 16590")
            act(god, "load obj 3097", "You have created")
            act(god, "transfer " + OWNER, "Ok.")

        def enter(client):
            deadline = time.monotonic() + 60
            while True:
                client.send("enter locker")
                match, text = client.expect_any(("this cost you", "Please try later", "Slow your roll"), timeout=30)
                if match == "this cost you":
                    text += score(client)[1]
                    assert "GET OUT" not in text and "could not complete the payment" not in text, text
                    act(client, "look", "The Storage Locker for")
                    return
                assert time.monotonic() < deadline, text
                score(client)
                time.sleep(.2)

        def leave(client):
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline:
                opened = act(client, "open door")
                if "being secured" not in opened:
                    client.send("north")
                    match, _ = client.expect_any(("applying magic locks", "still being secured"), timeout=30)
                    score(client)
                    if match == "applying magic locks":
                        save(client)
                        return
                time.sleep(.2)
            raise AssertionError("private chest did not become durable")

        try:
            boot("create")
            for name, account in ((OWNER, ACCOUNT), (GOD, STAFF)):
                client = journey.MudClient(plain)
                clients[name] = client
                journey.create_character(client, expected_room=None, account=account,
                                         character=name, email=name.lower() + "@example.invalid")
                save(client, name)
            stop()
            sql(f"UPDATE player_data SET level=62,highest_level=62 WHERE name IN ('{OWNER}','{GOD}')")
            boot("generate")
            actor = login()
            act(actor, "goto 132500")
            selected = []
            for slot, flag in (("head", 16), ("body", 8), ("legs", 32)):
                act(actor, f"randobj eq {slot} 56 30", "Created 30 equipment items.")
                save(actor)
                candidates = sql("SELECT i.obj_uid FROM player_items i JOIN player_data p ON p.pid=i.pid "
                    f"JOIN player_item_extra_descr e ON e.item_id=i.id AND e.keyword='{ORIGIN}' "
                    f"WHERE p.name='{OWNER}' AND e.description='1325' AND (i.wear_flags & {flag})<>0 "
                    "AND (COALESCE(i.bitvector1,0) & 528)=0 AND NOT EXISTS "
                    "(SELECT 1 FROM player_item_affects a WHERE a.item_id=i.id "
                    "AND a.location IN (5,13,35,45) AND a.modifier<>0) ORDER BY i.id")
                assert candidates, ("no HP/CON-clean native candidate", slot)
                uid = int(candidates.splitlines()[0])
                if not selected:
                    act(actor, "string obj " + selector(actor, uid) + " name namedshopwitness", "Ok.")
                act(actor, "wear " + selector(actor, uid))
                selected.append(uid)
            save(actor)
            assert all(player_rows()[uid][2] > 0 for uid in selected)
            act(actor, "load obj 83445", "You have created")
            act(actor, "open collector", "Ok.")
            act(actor, "put all collector")
            save(actor)
            previous = set(player_rows())
            act(actor, "load obj 83445", "You have created")
            save(actor)
            bag, = set(player_rows()) - previous
            act(actor, "open " + selector(actor, bag), "Ok.")
            stop()
            sql(f"UPDATE player_data SET level=56,highest_level=56,base_hit=1000,platinum=50 WHERE name='{OWNER}'")
            sql("INSERT INTO account_banks(account_name,racewar,bank_copper,bank_silver,bank_gold,bank_platinum) "
                f"VALUES ('{ACCOUNT}',1,0,0,0,4000) ON DUPLICATE KEY UPDATE bank_platinum=4000")
            sql("INSERT INTO currency_bank_baseline(bank_id,opening_copper,opening_silver,opening_gold,opening_platinum,opening_revision) "
                "SELECT id,bank_copper,bank_silver,bank_gold,bank_platinum,bank_revision FROM account_banks "
                f"WHERE account_name='{ACCOUNT}' AND racewar=1")
            boot("mortal-wear")
            actor = login()
            act(actor, "remove all")
            time.sleep(6)
            baseline, text = score(actor)
            assert "Level: 56" in text and "armor (" not in text
            for count, uid in enumerate(selected, 1):
                act(actor, "wear " + selector(actor, uid))
                if count == 2:
                    time.sleep(6)
                    assert "armor (" not in expect_max_hp(actor, baseline)
            assert "armor (" in expect_max_hp(actor, baseline + 5)
            save(actor)
            assert sql("SELECT COUNT(*) FROM player_affects a JOIN player_data p ON p.pid=a.pid "
                       f"WHERE p.name='{OWNER}' AND a.type=1") == "0", "set Armor must not be saved as an ordinary cast"
            worn = {uid: player_rows()[uid] for uid in selected}
            assert all(row[2] > 0 and row[3] == "1325" for row in worn.values())
            evidence.update(uids=selected, bag=bag, worn=worn, baseline_hp=baseline)
            stop()
            boot("player-reload")
            actor = login()
            assert "armor (" in expect_max_hp(actor, baseline + 5)
            save(actor)
            assert {uid: player_rows()[uid] for uid in selected} == worn
            check("native MariaDB generation, mortal wear and player reload retain UIDs/origins/slots and Armor/+5 HP")
            act(actor, "remove all")
            assert "armor (" not in expect_max_hp(actor, baseline)
            for uid in selected:
                put(actor, uid, bag)
            save(actor)
            tree = {uid: player_rows()[uid] for uid in [bag] + selected}
            assert all(tree[uid][1] == bag for uid in selected)
            bank()
            enter(actor)
            act(actor, "eq chest create vault fixture-secret", "Private chest 'vault' created")
            act(actor, "open vault", "You open the 'vault' chest")
            act(actor, "put " + selector(actor, bag) + " vault", "Ok.")
            act(actor, "close vault", "You close")
            leave(actor)
            assert chest_rows() == tree, (chest_rows(), tree)
            assert set(tree).isdisjoint(player_rows())
            check("native private chest purchase/deposit durably moves the exact marked container tree")
            stop()
            boot("chest-reload")
            assert chest_rows() == tree
            actor = login()
            bank()
            enter(actor)
            act(actor, "open vault", "You open the 'vault' chest")
            act(actor, "get collector vault", "You get")
            save(actor)
            assert {uid: player_rows()[uid] for uid in tree} == tree
            leave(actor)
            assert not chest_rows()
            for uid in selected:
                get_from_container(actor, uid, bag)
                act(actor, "wear " + selector(actor, uid))
            assert "armor (" in expect_max_hp(actor, baseline + 5)
            save(actor)
            assert {uid: player_rows()[uid] for uid in selected} == worn
            stop()
            boot("retrieved-reload")
            actor = login()
            assert "armor (" in expect_max_hp(actor, baseline + 5)
            save(actor)
            assert {uid: player_rows()[uid] for uid in selected} == worn
            check("private chest reboot/retrieval and final player reboot retain the graph, origins and worn set")

            god = login(GOD, STAFF)
            act(god, "goto 132500")
            act(god, "transfer " + OWNER, "Ok.")
            act(god, "setbit char " + OWNER + " platinum 10")
            uid = selected[0]
            act(actor, "remove " + selector(actor, uid))
            act(actor, "sell namedshopwitness", "gives you")
            save(actor)
            sold = shop_item(uid)
            assert sold and sold[1:3] == [0, 0] and sold[4] == "1325", sold
            assert uid not in player_rows()
            stop()
            boot("shop-reload")
            actor = login()
            assert shop_item(uid) == sold
            act(actor, "buy namedshopwitness", "You now have")
            save(actor)
            assert shop_item(uid) is None and player_rows()[uid][3] == "1325"
            act(actor, "wear " + selector(actor, uid))
            assert "armor (" in expect_max_hp(actor, baseline + 5)
            save(actor)
            assert {uid: player_rows()[uid] for uid in selected} == worn
            check("native mortal sale/shop reboot/paid repurchase retain the exact UID, origin, slots and set")

            act(actor, "remove all")
            assert "armor (" not in expect_max_hp(actor, baseline)
            for uid in selected:
                put(actor, uid, bag)
            save(actor)
            assert {uid: player_rows()[uid] for uid in tree} == tree
            god = login(GOD, STAFF)
            act(god, "goto 132500")
            # A plain backpack has a distinct keyword from both carried collector
            # bags. Native storage creation makes the floor root durable/non-takeable.
            act(god, "storage new 4917", "This object now loads here")
            deadline = time.monotonic() + 30
            while True:
                roots = sql("SELECT obj_uid FROM saved_items WHERE room_vnum=132500 "
                            "AND vnum=4917 AND item_type=35 AND container_id IS NULL")
                if roots:
                    root, = map(int, roots.splitlines())
                    break
                assert time.monotonic() < deadline, "storage root did not become durable"
                time.sleep(.2)
            act(actor, "open backpack")
            act(actor, "put " + selector(actor, bag) + " backpack", "Ok.")
            save(actor)
            stored = dict(tree)
            stored[bag] = [tree[bag][0], root, 0, tree[bag][3]]
            stored[root] = [4917, 0, 0, "-"]
            wait_world(stored)
            assert set(tree).isdisjoint(player_rows())
            evidence.update(shop_uid=selected[0], shop_record=sold, world_root=root)
            stop()
            boot("world-reload")
            actor = login()
            wait_world(stored)
            act(actor, "open backpack")
            act(actor, "get collector backpack", "You get")
            save(actor)
            wait_world({root: stored[root]})
            assert {uid: player_rows()[uid] for uid in tree} == tree
            for uid in selected:
                get_from_container(actor, uid, bag)
                act(actor, "wear " + selector(actor, uid))
            assert "armor (" in expect_max_hp(actor, baseline + 5)
            save(actor)
            assert {uid: player_rows()[uid] for uid in selected} == worn
            stop()
            boot("world-retrieved-reload")
            actor = login()
            assert "armor (" in expect_max_hp(actor, baseline + 5)
            save(actor)
            assert {uid: player_rows()[uid] for uid in selected} == worn
            wait_world({root: stored[root]})
            assert not chest_rows() and shop_item(selected[0]) is None
            check("native SQL storage/world reboot/mortal retrieval/player reboot retain the complete graph and set")
        except BaseException:
            # Preserve the disposable authority before the context manager drops it.
            with (runtime / "failure.sql").open("w") as dump:
                subprocess.run(["mysqldump", "--skip-ssl", "--protocol=tcp", "-h", env["DB_HOST"],
                                "-P", env["DB_PORT"], "-u", env["DB_USER"], env["DB_NAME"]],
                               env=env, stdout=dump, check=False)
            raise
        finally:
            stop()
            (runtime / "transcript.txt").write_bytes(b"\n\n".join(transcripts))
            (runtime / "evidence.json").write_text(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    run()
