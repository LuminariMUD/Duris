#!/usr/bin/env python3
"""Smith and Craft/Forge replacement checkpoints across refusal and cold restart on SQL."""

import argparse
import re
from pathlib import Path
import tempfile
import time

import test_flatfile_combat_journey as journey
from run_item_pilot_journey import Server, object_records
from run_world_quest_dual_backend import collect_logs
from test_flight_network_journey import authority, command

ROOT = journey.ROOT
BUYER, STAFF = "Smithbuyer", "Smithwarden"
ACCOUNTS = {BUYER: "Smithacct", STAFF: "Smithstaff"}


def run(binary):
    (ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="smith-sql-", dir=ROOT / "bin/tests") as temporary:
        runtime = Path(temporary)
        journey.make_fixture(runtime)
        journey.generate_certificate(runtime)
        (runtime / "logs/log").mkdir(parents=True)
        (runtime / "help").symlink_to(ROOT / "help", target_is_directory=True)
        with authority("mariadb", runtime) as (env, sql):
            server = Server(binary, runtime, runtime, "smith", environment=env)
            clients = {}

            def login(name, fresh=False):
                if fresh:
                    client = journey.MudClient(server.port)
                    clients[name] = client
                    journey.create_character(client, expected_room=None, account=ACCOUNTS[name],
                                             character=name, email=name.lower() + "@example.invalid")
                else:
                    client = journey.reconnect_character(server.port, expected_room=None,
                                                         account=ACCOUNTS[name], character=name)
                    clients[name] = client
                    client.expect("Welcome to Duris", timeout=60)
                    client.expect("Pos: standing >", timeout=20)
                command(client, "toggle paging no")
                return client

            def stop(crash=False):
                for client in clients.values():
                    client.close()
                clients.clear()
                if crash:
                    server.process.kill()
                    server.process.wait(timeout=10)
                server.stop()

            def snapshot():
                money = sql(f"SELECT copper+10*silver+100*gold+1000*platinum "
                            f"FROM player_data WHERE name='{BUYER}'")
                items = sql("SELECT i.obj_uid,i.vnum FROM player_items i JOIN player_data p "
                            f"ON p.pid=i.pid WHERE p.name='{BUYER}' "
                            "AND i.vnum IN (220,221,231,1255) ORDER BY i.obj_uid")
                return int(money), [tuple(map(int, row.split())) for row in items.splitlines()]

            def await_snapshot(predicate):
                deadline = time.monotonic() + 30
                while time.monotonic() < deadline:
                    state = snapshot()
                    if predicate(state):
                        return state
                    time.sleep(.1)
                raise AssertionError(("smith checkpoint did not settle", state))

            try:
                server.start(full_world=True)
                for name in ACCOUNTS:
                    command(login(name, fresh=True), "save")
                stop()
                sql(f"UPDATE player_data SET level=62,highest_level=62 WHERE name='{STAFF}'")
                sql(f"UPDATE player_data SET platinum=100,copper=0,silver=0,gold=0 WHERE name='{BUYER}'")
                server.start(full_world=True)
                buyer, staff = login(BUYER), login(STAFF)
                command(staff, "goto 16590")
                # SAFE rooms eject ordinary NPCs on entry; retain the test smith.
                command(staff, "setbit room here flag SAFE 0")
                assert "Ok." in command(staff, "transfer " + BUYER)
                command(staff, "load mob 76010")
                command(staff, "setbit char smith npcact SENTINEL 1")
                for vnum in (220, 220, 221, 231):
                    assert "You have created" in command(staff, f"load obj {vnum}")
                    given = command(staff, "give ore " + BUYER)
                    assert "Ok." in given, given
                command(buyer, "save")
                before = await_snapshot(lambda state: len(state[1]) == 4)
                assert before[0] == 100000 and sorted(v for _, v in before[1]) == [220, 220, 221, 231], before
                assert "1)" in command(buyer, "forge"), "the first smith has no reachable menu"
                print("PASS real first-smith menu and four customer ore UIDs checkpointed", flush=True)

                # The final player checkpoint must roll back payment and all item rows together.
                pid = int(sql(f"SELECT pid FROM player_data WHERE name='{BUYER}'"))
                sql("DELIMITER //\nCREATE TRIGGER reject_smith_output BEFORE INSERT ON player_items FOR EACH ROW "
                    f"BEGIN IF NEW.pid={pid} AND NEW.vnum=1255 THEN "
                    "SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='smith checkpoint refusal'; END IF; END//\nDELIMITER ;\n")
                assert "You hand" in command(buyer, "forge 1")
                deadline = time.monotonic() + 20
                while "error=1644" not in collect_logs(runtime):
                    assert time.monotonic() < deadline, "the injected SQL refusal was not exercised"
                    time.sleep(.1)
                assert snapshot() == before, "refused checkpoint split payment from ore/output"
                stop(crash=True)
                assert snapshot() == before
                sql("DROP TRIGGER reject_smith_output")
                server.start(full_world=True)
                buyer, staff = login(BUYER), login(STAFF)
                command(buyer, "save")
                assert await_snapshot(lambda state: state == before) == before
                print("PASS refused checkpoint + SIGKILL: original balance and exact ore UIDs reload", flush=True)

                # Return to the smith after the restart, then publish the complete replacement.
                command(staff, "goto 16590")
                command(staff, "setbit room here flag SAFE 0")
                command(staff, "transfer " + BUYER)
                command(staff, "load mob 76010")
                command(staff, "setbit char smith npcact SENTINEL 1")
                assert "You hand" in command(buyer, "forge 1")
                after = await_snapshot(lambda state: state[0] == before[0] - 30000 and
                                       len(state[1]) == 1 and state[1][0][1] == 1255)
                uid = after[1][0][0]
                assert uid not in {item_uid for item_uid, _ in before[1]}
                owner = sql(f"SELECT owner_type,owner_id,state FROM item_current_owner WHERE item_uid={uid}")
                assert list(map(int, owner.split())) == [1, pid, 1], owner
                for _ in range(2):
                    command(buyer, "save")
                assert snapshot() == after, "repeat save charged or delivered twice"
                command(staff, "goto 16558")  # The real Woodseer inn permits mortal logout.
                command(staff, "transfer " + BUYER)
                buyer.send("rent")
                buyer.expect("ACCOUNT MENU", timeout=30)
                stop()
                server.start(full_world=True)
                buyer = login(BUYER)
                command(buyer, "save")
                assert await_snapshot(lambda state: state == after) == after
                assert sql(f"SELECT owner_type,owner_id,state FROM item_current_owner WHERE item_uid={uid}") == owner
                print("PASS successful forge: one debit/output UID, exact owner, rent/unload and cold restart", flush=True)

                stop()
                sql(f"UPDATE player_data SET level=50,highest_level=50 WHERE name='{BUYER}'")
                sql(f"INSERT IGNORE INTO player_recipes(pid,recipe_vnum) VALUES({pid},1600)")
                sql("INSERT INTO player_skills(pid,skill_id,learned,taught) VALUES "
                    f"({pid},1132,100,1),({pid},1134,100,1) "
                    "ON DUPLICATE KEY UPDATE learned=100,taught=1")
                objects = object_records((ROOT / 'areas/world.obj').read_text())
                server.start(full_world=True)
                buyer, staff = login(BUYER), login(STAFF)

                def graph():
                    rows = sql("SELECT i.obj_uid,i.vnum,COALESCE(parent.obj_uid,0),i.equip_slot "
                               "FROM player_items i LEFT JOIN player_items parent ON parent.id=i.container_id "
                               f"WHERE i.pid={pid} ORDER BY i.obj_uid")
                    return [tuple(map(int, row.split())) for row in rows.splitlines()]

                def await_graph(predicate):
                    deadline = time.monotonic() + 30
                    while time.monotonic() < deadline:
                        rows = graph()
                        if predicate(rows):
                            return rows
                        time.sleep(.1)
                    raise AssertionError(('crafting graph did not settle', rows))

                for mode, tool in (('craft', 400224), ('forge', 400223)):
                    command(staff, 'goto 16590')
                    command(staff, 'transfer ' + BUYER)
                    requirements = command(buyer, mode + ' info 1600')
                    required = re.search(r'To (?:craft|forge) this item, you will need ([^\r\n]+)', requirements)
                    assert required, requirements
                    counts = list(map(int, re.findall(r'(\d+) of', required[1])))
                    assert len(counts) in (1, 2), requirements
                    provisions = [400054] * counts[0] + [400050] * (counts[1] if len(counts) == 2 else 0) + [tool]
                    if 'magical essence' in requirements.lower():
                        provisions.append(400211)
                    command(buyer, 'save')
                    old_uids = {row[0] for row in graph()}
                    for vnum in provisions:
                        assert 'You have created' in command(staff, f'load obj {vnum}')
                        keyword = objects[vnum].splitlines()[1].split()[0].rstrip('~')
                        given = command(staff, f'give {keyword} {BUYER}')
                        assert 'Ok.' in given, given
                    command(buyer, 'save')
                    provision_vnums = set(provisions)
                    inputs = await_graph(lambda rows: len({row[0] for row in rows if row[1] in provision_vnums} - old_uids) == len(provisions))
                    input_uids = {row[0] for row in inputs if row[1] in provision_vnums} - old_uids
                    # Learning a discipline may also grant its tome. Keep that UID
                    # in the unchanged inventory rather than treating it as material.
                    old_uids = {row[0] for row in inputs} - input_uids
                    original_wallet = snapshot()[0]
                    baseline_uids = ','.join(str(row[0]) for row in inputs)
                    sql("DELIMITER //\nCREATE TRIGGER reject_craft_output BEFORE INSERT ON player_items FOR EACH ROW "
                        f"BEGIN IF NEW.pid={pid} AND NEW.vnum=1600 AND NEW.obj_uid NOT IN ({baseline_uids}) THEN "
                        "SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='craft checkpoint refusal'; END IF; END//\nDELIMITER ;\n")
                    errors_before = collect_logs(runtime).count('error=1644')
                    completed = command(buyer, mode + ' make 1600')
                    assert 'admiring your new' in completed, completed
                    deadline = time.monotonic() + 20
                    while collect_logs(runtime).count('error=1644') <= errors_before:
                        assert time.monotonic() < deadline, 'crafting SQL refusal was not exercised'
                        time.sleep(.1)
                    assert graph() == inputs and snapshot()[0] == original_wallet
                    stop(crash=True)
                    sql('DROP TRIGGER reject_craft_output')
                    server.start(full_world=True)
                    buyer, staff = login(BUYER), login(STAFF)
                    command(buyer, 'save')
                    assert await_graph(lambda rows: rows == inputs) == inputs
                    command(staff, 'goto 16590')
                    command(staff, 'transfer ' + BUYER)
                    assert 'admiring your new' in command(buyer, mode + ' make 1600')
                    after_craft = await_graph(lambda rows: not ({row[0] for row in rows} & input_uids) and
                                             len({row[0] for row in rows} - old_uids) == 1)
                    output_uid = next(row[0] for row in after_craft if row[0] not in old_uids)
                    assert next(row[1] for row in after_craft if row[0] == output_uid) == 1600
                    assert {row[0] for row in after_craft} == old_uids | {output_uid}
                    assert snapshot()[0] == original_wallet
                    command(buyer, 'save')
                    stop(crash=True)
                    server.start(full_world=True)
                    buyer, staff = login(BUYER), login(STAFF)
                    command(buyer, 'save')
                    assert await_graph(lambda rows: rows == after_craft) == after_craft
                    assert list(map(int, sql('SELECT owner_type,owner_id,state FROM item_current_owner '
                                             f'WHERE item_uid={output_uid}').split())) == [1, pid, 1]
                    assert sql('SELECT COUNT(*) FROM item_current_owner WHERE state=1 AND item_uid IN (' +
                               ','.join(map(str, input_uids)) + ')') == '0'
                    print(f'PASS {mode}: refused checkpoint/restart preserves every input UID; success/restart owns one output', flush=True)
            except Exception:
                target = ROOT / "bin/tests/smith-payment-failure.log"
                target.write_text(collect_logs(runtime) + "\n" +
                                  server.output_path.read_text(errors="replace") + "\n" +
                                  "\n".join(name + ": " + bytes(client.transcript).decode(errors="replace")
                                            for name, client in clients.items()))
                print("Failure evidence: " + str(target), flush=True)
                raise
            finally:
                stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", type=Path, default=ROOT / "bin/server/dms_new")
    run(parser.parse_args().server.resolve())
