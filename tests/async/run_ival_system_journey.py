#!/usr/bin/env python3
"""Qualify one valuation fixture bundle on disposable MariaDB and a real MUD.

Run through with_disposable_mariadb.sh. Never reads .env or uses a running game.
"""
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

import test_flatfile_combat_journey as journey
from test_flight_network_journey import command
from run_world_quest_dual_backend import setup_run_root
from run_item_pilot_journey import object_records
from test_flatfile_locker_journey import reenter_locker

ROOT = Path(__file__).resolve().parents[2]
OWNER, OWNER_ACCOUNT = "Ivalmortal", "Ivalowner"
STAFF, STAFF_ACCOUNT = "Ivalwarden", "Ivalstaff"
ROOM = 16590
IDS = dict(fourth=131990, duplicate=131991, glove=131992, bank5=131993,
           essence=131994, superior=131995, tier=131996, native=23808)
LABELS = {name: "iv" + name for name in IDS if name != "tier"}
RANDOM_VNUMS = (1252, 1253, 1254)
FIELDS = ("vnum", "item_type", "wear_flags", "extra_flags", "extra2_flags",
          "anti_flags", "anti2_flags", "craftsmanship", "item_material",
          *("value" + str(i) for i in range(8)),
          *("bitvector" + str(i) for i in range(1, 6)))


def record(vnum, name, applies=(), *, item_type=11, wear=257, extra2=0, bank5=0, values=None):
    result = (f"#{vnum}\n{name} marker~\nan {name} marker~\nAn {name} marker lies here.~\n~\n"
              f"{item_type} 3 3 6 7 0 0 {wear} {extra2} 0 0\n"
              + " ".join(map(str, values or [0] * 8)) + "\n"
              "1 0 100 0 0 0 0\n")
    if bank5:
        result += f"B5\n{bank5}\n"
    for location, modifier in (*applies, *((0, 0),) * (4 - len(applies))):
        result += f"A\n{location} {modifier}\n"
    return result


def fixtures(root):
    (root / "areas").unlink()
    (root / "areas").mkdir()
    generated = {"world." + kind for kind in ("obj", "mob", "wld", "zon", "trg", "qst", "shp")}
    for path in (ROOT / "areas").iterdir():
        if path.name.startswith("world.") and path.name not in generated:
            shutil.copy2(path, root / "areas" / path.name)
        elif not path.name.startswith(("world.", "tworld.")):
            (root / "areas" / path.name).symlink_to(path, target_is_directory=path.is_dir())
    for kind in ("obj", "mob", "wld", "zon", "trg", "qst", "shp"):
        subprocess.run(["make", "-s", "-C", "areas/src/" + kind], cwd=ROOT, check=True)
        assembled = subprocess.run([str(ROOT / f"bin/areas/tools/make_{kind}")],
                                   cwd=root / "areas", capture_output=True)
        assert assembled.returncode == 0, assembled.stderr[-1500:]
        (root / f"areas/tworld.{kind}").rename(root / f"areas/world.{kind}")
    source = object_records((root / "areas/world.obj").read_text(encoding="latin1"))
    assert all(vnum not in source for name, vnum in IDS.items() if name != "native")
    source[IDS["fourth"]] = record(IDS["fourth"], LABELS["fourth"], ((0, 0), (0, 0), (18, 0), (1, 6)))
    source[IDS["duplicate"]] = record(IDS["duplicate"], LABELS["duplicate"], ((1, 3), (1, 3)))
    source[IDS["glove"]] = record(IDS["glove"], LABELS["glove"], item_type=9, wear=129,
                                           extra2=524288, values=[0, 0, 0, 0, 0, 33032, 60, 30])
    source[IDS["bank5"]] = record(IDS["bank5"], LABELS["bank5"], ((13, 10),), bank5=2048)
    source[IDS["essence"]] = record(IDS["essence"], LABELS["essence"], ((1, 1),))
    source[IDS["superior"]] = record(IDS["superior"], LABELS["superior"], ((1, 2), (4, 2)), wear=9)
    source[IDS["tier"]] = record(IDS["tier"], "ivtier", ((1, 3), (4, 3)), wear=9)
    source[IDS["native"]] = record(IDS["native"], LABELS["native"], ((13, 10),))
    (root / "areas/world.obj").write_text("".join(source[key] for key in sorted(source)) + "$~\n", encoding="latin1")
    # Real mortal logout uses rent at an inn; quit routes to outdoor camping.
    world = root / "areas/world.wld"
    rooms = world.read_text(encoding="latin1")
    rooms, changed = re.subn(
        rf"(?ms)(^#{ROOM}\n.*?~\n.*?~\n)(\d+) (\d+) (\d+)",
        lambda match: f"{match[1]}{match[2]} {int(match[3]) | 524288} {match[4]}", rooms, count=1)
    assert changed == 1
    world.write_text(rooms, encoding="latin1")


def run(binary, destination):
    evidence = {"backend": "MariaDB", "complete": False,
                "valuation_bundle_complete": False, "economic_journeys_complete": False, "checks": [],
                "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
                "formula_revision": "ival-v8-proc-semantics"}
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Native private-directory checks require POSIX modes; the Windows worktree
    # mount does not preserve them. Existing real-server rigs also use /tmp.
    with tempfile.TemporaryDirectory(prefix="ival-system-") as temporary:
        root = Path(temporary)
        _, critical, output = setup_run_root(root)
        fixtures(root)
        # Keep superior tier selection deterministic without changing its policy.
        config = root / "lib/enhance.cfg"
        config.write_text(config.read_text().replace("enhance.search.vnum.min=1300", "enhance.search.vnum.min=131990")
                          .replace("enhance.search.vnum.max=134000", "enhance.search.vnum.max=131996"))
        context_files = ("areas/world.obj", "areas/world.trg", "areas/world.wld", "lib/duris.properties",
                         "lib/enhance.cfg", "lib/crafting.cfg", "lib/random_equipment.cfg",
                         "lib/kingdom.cfg", "lib/item_abilities.json")
        context = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in context_files}
        evidence["context_sha256"] = context
        executable = root / "bin/server/dms"
        executable.parent.mkdir(parents=True)
        shutil.copy2(binary, executable)
        clients = {}
        process = None
        plain, tls, websocket = journey.available_ports()
        with journey.mariadb_authority() as (env, sql):
            env.update(CRITICAL_COMMAND_JOURNAL_DIR=str(critical), DURIS_TLS_PORT=str(tls),
                       DURIS_WEBSOCKET_PORT=str(websocket), REDIS_WORLD_STATE="FALSE")

            def check(label):
                evidence["checks"].append(label)
                destination.write_text(json.dumps(evidence, indent=2) + "\n")
                print("PASS " + label, flush=True)

            def boot():
                nonlocal process
                assert context == {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                                   for name in context_files}, "valuation context changed within journey"
                offset = output.stat().st_size if output.exists() else 0
                with output.open("a") as stream:
                    process = subprocess.Popen([str(executable), "-d", str(root), str(plain)],
                                               cwd=root, env=env, stdout=stream, stderr=subprocess.STDOUT)
                deadline = time.monotonic() + 180
                while b"Entering game loop." not in output.read_bytes()[offset:]:
                    assert process.poll() is None and time.monotonic() < deadline, output.read_text(errors="replace")[-3500:]
                    time.sleep(.1)

            def stop():
                nonlocal process
                for client in clients.values():
                    client.close()
                clients.clear()
                process.send_signal(signal.SIGTERM)
                assert process.wait(timeout=90) == 0
                process = None

            def login(name, account):
                client = journey.reconnect_character(plain, expected_room=None, account=account, character=name)
                clients[name] = client
                client.expect("Welcome to Duris", timeout=60)
                client.expect_any(("Pos: standing >", "<>"), timeout=30)
                command(client, "toggle paging no")
                if name == STAFF:
                    command(client, "goto " + str(ROOM))
                return client

            def save(name=OWNER):
                client = clients[name]
                client.send("save")
                client.expect("Saving " + name + ".", timeout=60)

            def quit_owner(exit_command="rent"):
                client = clients.pop(OWNER)
                client.send(exit_command)
                client.expect("ACCOUNT MENU", timeout=60)
                client.close()

            def scores(labels):
                result = {}
                for label, keyword in labels.items():
                    for _ in range(3):
                        text = command(clients[OWNER], "lore " + keyword, timeout=30)
                        found = re.search(r"has an item value of\s+(\d+)", text)
                        if found:
                            result[label] = int(found[1])
                            break
                    else:
                        raise AssertionError("lore did not return value for " + label + ": " + text[-1200:])
                return result

            def state(table="player_items"):
                wanted = (*[IDS[name] for name in LABELS], *RANDOM_VNUMS)
                owner = {
                    "player_items": f"JOIN player_data p ON p.pid=i.pid WHERE p.name='{OWNER}'",
                    "locker_items": "JOIN lockers l ON l.id=i.locker_id WHERE l.locker_name='account.ivalowner.1.locker'",
                    "corpse_items": f"JOIN corpses c ON c.id=i.corpse_id WHERE c.player_name='{OWNER}'",
                }[table]
                affects = table.replace("_items", "_item_affects")
                rows = sql("SELECT i.obj_uid," + ",".join("i." + field for field in FIELDS) + ","
                           "COALESCE((SELECT GROUP_CONCAT(CONCAT_WS(':',affect_slot,location,modifier) "
                           f"ORDER BY affect_slot SEPARATOR ';') FROM {affects} a WHERE a.item_id=i.id),'') "
                           f"FROM {table} i {owner} AND i.vnum IN {wanted} ORDER BY i.obj_uid")
                result = {}
                for row in rows.splitlines():
                    parts = row.split("\t")
                    item = dict(zip((*FIELDS, "applies"), parts[1:]))
                    slots = [(0, 0)] * 4
                    for apply in item["applies"].split(";") if item["applies"] else ():
                        slot, location, modifier = map(int, apply.split(":"))
                        assert 0 <= slot < 4
                        slots[slot] = (location, modifier)
                    item["applies"] = ";".join(f"{slot}:{location}:{modifier}" for slot, (location, modifier) in enumerate(slots))
                    result[int(parts[0])] = item
                return result

            def act(text, expected):
                client = clients[OWNER]
                client.send(text)
                client.expect(expected, timeout=60)
                command(client, "score")

            def purse():
                save()
                row = sql(f"SELECT copper+10*silver+100*gold+1000*platinum FROM player_data WHERE name='{OWNER}'")
                return int(row)

            def wait_for_state(table, expected):
                deadline = time.monotonic() + 60
                while state(table) != expected:
                    assert process.poll() is None and time.monotonic() < deadline, (table, state(table))
                    time.sleep(.1)

            def leave_locker():
                client = clients[OWNER]
                deadline = time.monotonic() + 60
                while time.monotonic() < deadline:
                    opened = command(client, "open door")
                    if "being secured" not in opened:
                        assert "Ok." in opened or "It's already open!" in opened, opened
                        client.send("north")
                        matched, _ = client.expect_any(("applying magic locks", "still being secured"), timeout=30)
                        if matched == "applying magic locks":
                            command(client, "score")
                            return
                    time.sleep(.1)
                raise AssertionError("locker contents were not secured")

            try:
                boot()
                for name, account in ((OWNER, OWNER_ACCOUNT), (STAFF, STAFF_ACCOUNT)):
                    client = journey.MudClient(plain)
                    clients[name] = client
                    journey.create_character(client, expected_room=None, account=account, character=name,
                                             email=name.lower() + "@example.invalid")
                    save(name)
                stop()
                sql(f"UPDATE player_data SET level=62,highest_level=62,last_room={ROOM},platinum=50 "
                    f"WHERE name IN ('{OWNER}','{STAFF}')")
                boot()
                login(STAFF, STAFF_ACCOUNT)
                actor = login(OWNER, OWNER_ACCOUNT)
                command(actor, "drop all")
                for name in LABELS:
                    assert "You have created" in command(actor, "load obj " + str(IDS[name]))
                for vnum, count in ((400015, 6), (400019, 8), (400254, 1)):
                    for _ in range(count):
                        assert "You have created" in command(actor, "load obj " + str(vnum))
                generated = command(actor, "randobj eq any 20 1")
                assert "Item Value:" in generated, generated[-1800:]
                evidence["generated_birth_score"] = int(re.search(r"Item Value:\s*(\d+)", generated)[1])
                save()
                generated_name = sql("SELECT SUBSTRING_INDEX(i.name,' ',1) FROM player_items i "
                                     "JOIN player_data p ON p.pid=i.pid "
                                     f"WHERE p.name='{OWNER}' AND i.vnum IN {RANDOM_VNUMS}")
                assert generated_name and "\n" not in generated_name
                labels = {**LABELS, "generated": generated_name}
                quit_owner("quit")
                stop()
                sql(f"UPDATE player_data SET level=37,highest_level=37,m_class=524288,spec=0,base_str=150,base_dex=150 "
                    f"WHERE name='{OWNER}'; INSERT INTO player_skills(pid,skill_id,learned,taught) "
                    f"SELECT pid,1074,100,100 FROM player_data WHERE name='{OWNER}' "
                    "ON DUPLICATE KEY UPDATE learned=100,taught=100")
                boot()
                login(STAFF, STAFF_ACCOUNT)
                login(OWNER, OWNER_ACCOUNT)
                original = scores({"essence": LABELS["essence"], "superior": LABELS["superior"]})
                before = purse()
                act("enhance ivessence essence", "Your enhancement is a success!")
                assert purse() == before - 1000
                before = purse()
                act("enhance ivsuperior", "thrums with superior energy!")
                assert purse() == before - (1000 + 100 * original["superior"])
                # Loading as staff bypassed mortal carry limits. Keep only the
                # eight-item bundle for the later real locker/corpse retrievals.
                act("drop all.salvaged", "You drop")
                baseline = scores(labels)
                assert {name: baseline[name] for name in ("fourth", "duplicate", "bank5", "native")} == {
                    "fourth": 25, "duplicate": 25, "bank5": 29, "native": 154}
                assert baseline["essence"] > original["essence"] and baseline["superior"] > original["superior"]
                assert baseline["generated"] == evidence["generated_birth_score"]
                save()
                inputs = state()
                assert len(inputs) == 8, inputs
                by_vnum = {int(row["vnum"]): row for row in inputs.values()}
                assert by_vnum[IDS["fourth"]]["applies"] == "0:0:0;1:0:0;2:18:0;3:1:6"
                assert by_vnum[IDS["duplicate"]]["applies"].startswith("0:1:3;1:1:3")
                assert by_vnum[IDS["bank5"]]["bitvector5"] == "2048"
                evidence.update(initial_scores=baseline, initial_inputs=inputs)
                check("eight real item classes: indexed inputs and runtime lore values captured")
                quit_owner()
                login(OWNER, OWNER_ACCOUNT)
                assert scores(labels) == baseline
                save()
                assert state() == inputs
                check("full valuation bundle preserves inputs and scores through save/logout/login")
                stop()
                boot()
                login(STAFF, STAFF_ACCOUNT)
                login(OWNER, OWNER_ACCOUNT)
                assert scores(labels) == baseline
                save()
                assert state() == inputs
                check("full valuation bundle preserves inputs and scores through server restart")
                command(clients[STAFF], "load obj 3097")
                reenter_locker(clients[OWNER], 0, OWNER)
                for keyword in labels.values():
                    act("drop " + keyword, "You drop")
                leave_locker()
                save()
                wait_for_state("locker_items", inputs)
                assert not state()
                stop()
                boot()
                login(STAFF, STAFF_ACCOUNT)
                login(OWNER, OWNER_ACCOUNT)
                reenter_locker(clients[OWNER], 8, OWNER)
                for keyword in labels.values():
                    act("get " + keyword + " chest", "You get")
                leave_locker()
                assert scores(labels) == baseline
                save()
                assert state() == inputs
                check("same bundle preserves all inputs/scores through locker store, restart and retrieval")

                command(clients[STAFF], "remove all")
                command(clients[STAFF], "kill " + OWNER)
                wait_for_state("corpse_items", inputs)
                clients.pop(OWNER).close()
                stop()
                boot()
                login(STAFF, STAFF_ACCOUNT)
                login(OWNER, OWNER_ACCOUNT)
                assert state("corpse_items") == inputs
                command(clients[STAFF], "transfer " + OWNER)
                for keyword in labels.values():
                    act("get " + keyword + " corpse", "You get")
                assert scores(labels) == baseline
                save()
                assert state() == inputs
                evidence["valuation_bundle_complete"] = True
                check("same bundle preserves all inputs/scores through real death, corpse restart and recovery")
                # Craft/forge/salvage/reward command phases still extend this same run.
                stop()
            except BaseException:
                target = ROOT / "bin/qualification/ival-failure"
                target.mkdir(parents=True, exist_ok=True)
                if output.exists():
                    shutil.copy2(output, target / "server.out")
                destination.write_text(json.dumps(evidence, indent=2) + "\n")
                raise
            finally:
                for client in clients.values():
                    client.close()
                if process and process.poll() is None:
                    process.terminate()
                    process.wait(timeout=90)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", type=Path, default=ROOT / "bin/server/dms_new")
    parser.add_argument("--evidence", type=Path,
                        default=ROOT / "bin/qualification/ival-system/journey.json")
    args = parser.parse_args()
    assert os.getenv("TEST_DB_HOST"), "run with with_disposable_mariadb.sh"
    run(args.server.resolve(), args.evidence.resolve())
