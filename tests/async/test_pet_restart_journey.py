#!/usr/bin/env python3
"""Real-server recovery of generated pets and held equipment on disposable MariaDB."""
import argparse
import os
from pathlib import Path
import re
import signal
import subprocess
import tempfile
import time
import test_mariadb_combat_journey as journey

ROOT = journey.ROOT
PET_OWNER_TYPE = 11  # item_owner_type::pet
INVALID_STATE_HOLD = 2  # pet_hold_reason::invalid_state
ARTIFACT_ON_NPC = 2


def run(binary):
    with tempfile.TemporaryDirectory(prefix="duris-pet-restart-") as temporary, \
            journey.mariadb_authority() as (env, sql):
        root = Path(temporary)
        runtime = root / "runtime"
        runtime.mkdir()
        (runtime / "logs/log").mkdir(parents=True)
        (runtime / "logs/log/.gitignore").write_text("*\n")
        journey.make_fixture(runtime)
        zone = runtime / "areas_mini/mini.zon"
        zone.write_text(re.sub(r"^[MG] .*\n", "", zone.read_text(), flags=re.M))
        mobile = runtime / "areas_mini/mini.mob"
        source = (ROOT / "areas/mob/heavens.mob").read_text()
        prototype = re.search(r"^#1201\n.*?(?=^#|^\$)", source, re.M | re.S).group()
        mobile.write_text(mobile.read_text().replace("$~", prototype + "$~"))
        journey.generate_certificate(runtime)
        (runtime / "journals" / "critical").mkdir(parents=True, mode=0o700)
        port, tls, websocket = journey.available_ports()
        env.update(CRITICAL_COMMAND_JOURNAL_DIR=str(runtime / "journals/critical"),
                   DURIS_TLS_PORT=str(tls), DURIS_WEBSOCKET_PORT=str(websocket))
        fixture = root / "pet-fixture"
        subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-Isrc",
                        "tests/async/pet_restart_fixture.cpp", "src/player/pet_restore_state.c",
                        "-o", str(fixture)], cwd=ROOT, check=True, timeout=90)

        def encoder(*arguments):
            return subprocess.check_output([str(fixture), *arguments], text=True)

        constants = dict(field.split("=") for field in encoder("constants").split())
        spells = constants["SPELLS"].split(",")
        tag = constants["TAG_SKILL_TIMER"]
        pid = 1
        item_columns = [column for column in sql(
            "SELECT column_name FROM information_schema.columns WHERE table_schema=DATABASE() "
            "AND table_name='player_pet_items' AND column_name NOT IN ('id','pet_id','container_id',"
            "'equip_slot') ORDER BY ordinal_position").split()
            if column in sql("SELECT GROUP_CONCAT(column_name) FROM information_schema.columns "
                             "WHERE table_schema=DATABASE() AND table_name='player_items'").split(",")]

        def pets():
            """Each pet as (id, hold reason, restore state, max hp, uid...), in pet order."""
            result = []
            # A maintenance checkpoint can replace a legacy pet's row ID.
            # Read the row and its gear in one committed SQL view.
            for line in sql(
                    "SELECT p.id,p.hold_reason,COALESCE(p.restore_state,''),p.max_hit,"
                    "COALESCE((SELECT GROUP_CONCAT(COALESCE(CAST(i.obj_uid AS CHAR),'NULL') "
                    "ORDER BY i.id) FROM player_pet_items i WHERE i.pet_id=p.id),'-') "
                    f"FROM player_pets p WHERE p.owner_pid={pid} ORDER BY p.pet_order,p.id").splitlines():
                pet_id, hold, state, max_hit, uid_list = line.split("\t")
                uids = uid_list.split(",") if uid_list != "-" else []
                result.append([pet_id, hold, state, max_hit, *uids])
            return result

        def rows():
            """What each pet's saved row holds: hold reason, restore state, max hp, then uids."""
            return [pet[1:] for pet in pets()]

        def leaves(count):
            """The first `count` root inventory items with no children and no container type."""
            found = sql(f"SELECT i.obj_uid FROM player_items i WHERE i.pid={pid} AND i.container_id IS NULL "
                        "AND i.item_type<>15 AND NOT EXISTS (SELECT 1 FROM player_items c "
                        f"WHERE c.container_id=i.id) ORDER BY i.obj_uid LIMIT {count}").split()
            assert len(found) == count, found
            return found

        def move_to_pet(uid, pet_id, slot, extra=""):
            """Move one item's row to a pet, keeping its uid and its custody."""
            columns = ",".join(item_columns)
            sql(f"INSERT INTO player_pet_items(pet_id,equip_slot,{columns}) "
                f"SELECT {pet_id},{slot},{columns} FROM player_items WHERE obj_uid={uid} AND pid={pid};"
                f"DELETE FROM player_items WHERE obj_uid={uid} AND pid={pid};{extra}")

        def seed():
            """Three legacy pets, each holding one of the character's leaf items."""
            room = sql(f"SELECT last_room FROM player_data WHERE pid={pid}")
            sql(f"UPDATE player_data SET level=56,highest_level=56 WHERE pid={pid}")
            for order, uid in enumerate(leaves(3)):
                # Expired stat bonuses may leave current resources above saved maxima.
                # This must survive a real login, save and second restart with all gear.
                bonus = (138, 10, 10) if order == 0 else (0, 0, 0)
                state = "NULL" if order == 2 else "'" + encoder("seed", str(order)) + "'"
                pet_id = sql(
                    "INSERT INTO player_pets(owner_pid,mob_vnum,pet_order,hit,max_hit,mana,max_mana,"
                    "vitality,max_vitality,charm_duration,room_vnum,saved_at,restore_state,hold_reason) "
                    f"VALUES({pid},1201,{order},{1234 + bonus[0]},1234,{55 + bonus[1]},55,"
                    f"{100 + bonus[2]},100,{5 if order == 1 else -1},{room},NOW(),{state},0);"
                    "SELECT LAST_INSERT_ID()")
                slot = int(constants["WEAR_BODY"]) + 1 if order == 0 else 0
                move_to_pet(uid, pet_id, slot)
                sql("INSERT INTO player_pet_item_affects(item_id,location,modifier) "
                    f"SELECT id,{constants['APPLY_HIT']},19 FROM player_pet_items WHERE obj_uid={uid}")
            return rows()

        def seed_artifact():
            """Give a durable pet a uid and an expired artifact, as the owner stays offline."""
            pet = next(row for row in pets() if row[1] == "0" and len(row) > 4)
            pet_id, pet_uid = pet[0], "100001"
            uid = leaves(1)[0]
            vnum = sql(f"SELECT vnum FROM player_items WHERE obj_uid={uid}")
            revision = sql(f"SELECT item_revision FROM item_current_owner WHERE item_uid={uid}")
            custody = ",".join([uid, *pet[4:]])
            move_to_pet(uid, pet_id, 0,
                        f"UPDATE player_pet_items SET extra_flags=extra_flags|{constants['ITEM_ARTIFACT']} "
                        f"WHERE obj_uid={uid};"
                        f"UPDATE player_pets SET pet_uid={pet_uid} WHERE id={pet_id};"
                        f"UPDATE item_current_owner SET owner_type={PET_OWNER_TYPE},owner_id={pet_uid},"
                        f"owner_context_id={pid} WHERE item_uid IN ({custody});"
                        "INSERT INTO item_owner_revision(owner_type,owner_id,owner_context_id,revision) "
                        f"VALUES({PET_OWNER_TYPE},{pet_uid},{pid},1);"
                        f"INSERT INTO artifacts(vnum,owned,locType,location,timer,type) "
                        f"VALUES({vnum},'Y',{ARTIFACT_ON_NPC},1201,'2000-01-01 00:00:00',1);"
                        "INSERT INTO artifact_domain_state(vnum,owned,loc_type,location,timer_epoch,"
                        "artifact_type,item_uid,item_revision,canonical_item_uid,identity_state) "
                        f"VALUES({vnum},1,{ARTIFACT_ON_NPC},1201,946684800,1,{uid},{revision},{uid},1)")
            return int(vnum), uid

        def arm(mode):
            """Rewrite pet restore states through the codec; pets the mode skips stay as they are."""
            armed = False
            for pet in pets():
                if not pet[2] or (mode == "arm-cooldowns" and pet[1] != "0"):
                    continue
                result = subprocess.run([str(fixture), mode, pet[2]], capture_output=True, text=True)
                if result.returncode:
                    continue
                sql(f"UPDATE player_pets SET restore_state='{result.stdout}' WHERE id={pet[0]}")
                armed = True
            assert armed, mode

        def timers():
            """The player's short timers and each pet's named-set cooldowns."""
            result = [["player", *line.split()] for line in sql(
                f"SELECT modifier,duration FROM player_affects WHERE pid={pid} AND type={tag} "
                f"AND modifier IN ({','.join(spells)}) ORDER BY modifier").splitlines()]
            for pet in pets():
                if pet[2]:
                    result += [line.split("|") for line in encoder("cooldowns", pet[2]).splitlines()]
            return result

        process = client = output = None

        def stop():
            nonlocal process, client, output
            if client:
                client.close()
                client = None
            if process and process.poll() is None:
                process.send_signal(signal.SIGTERM)
                try:
                    process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            if output:
                output.close()

        def boot():
            nonlocal process, output
            output = (runtime / "server.out").open("w")
            command = [str(binary), "--minimal", "-s", "-d", str(runtime), str(port)]
            if os.environ.get("PET_RESTART_GDB"):
                command = ["gdb", "--batch", "-ex", "run", "-ex", "thread apply all bt", "--args"] + command
            process = subprocess.Popen(command,
                                       cwd=runtime, env=env, stdout=output, stderr=subprocess.STDOUT)
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                if "Entering game loop." in (runtime / "server.out").read_text(errors="replace"):
                    return
                assert process.poll() is None, "server failed to boot"
                time.sleep(0.1)
            raise AssertionError("boot deadline exceeded")

        try:
            boot()
            client = journey.MudClient(port)
            journey.create_character(client)
            client.send("save")
            client.expect(f"Saving {journey.CHARACTER}.", timeout=30)
            stop()
            seeded = seed()
            expected_states = {row[1] for row in seeded if row[1]}
            expected_uids = {row[3] for row in seeded}
            assert len(expected_states) == 2 and len(expected_uids) == 3
            for cycle in range(2):
                boot()
                client = journey.reconnect_character(port)
                client.send("look")
                visible = client.expect("Pos: standing >", timeout=15)
                assert "skeleton of fixture0" in visible and "skeleton of fixture1" in visible, visible
                assert "undead corpse stands" not in visible, visible
                client.send("save")
                client.expect(f"Saving {journey.CHARACTER}.", timeout=30)
                current = rows()
                assert len(current) == 3, current
                assert {row[1] for row in current if row[1]} == expected_states, "generated state changed"
                assert {row[3] for row in current} == expected_uids, "equipment lost or duplicated"
                assert sum(row[0] == "1" for row in current) == 1, "legacy pet not held"
                # Gear contributes once to derived HP; the serialized base stays 1234.
                assert sorted(int(row[2]) for row in current) == [1234, 1234, 1253], current
                print(f"restart cycle {cycle + 1}: identity, base stats, gear, deadlines, held UID passed", flush=True)
                if cycle == 0:
                    stop()
            stop()
            # The owner stays offline while the maintenance event loads the
            # complete pet graph, retires only its expired artifact, and saves it.
            artifact_vnum, artifact_uid = seed_artifact()
            before_expiry = rows()
            boot()
            deadline = time.monotonic() + 90
            while True:
                identity = sql(f"SELECT identity_state FROM artifact_domain_state WHERE vnum={artifact_vnum}")
                current = rows()
                if identity == "2" and all(str(artifact_uid) not in row[3:] for row in current):
                    break
                assert process.poll() is None and time.monotonic() < deadline, (identity, current)
                time.sleep(.2)
            assert len(current) == len(before_expiry) == 3, (before_expiry, current)
            assert {uid for row in current for uid in row[3:]} == expected_uids, (
                "offline expiry sibling UIDs", sorted(expected_uids), artifact_uid,
                before_expiry, current, rows())
            stop(); boot()
            client = journey.reconnect_character(port)
            client.send("save")
            client.expect(f"Saving {journey.CHARACTER}.", timeout=30)
            assert {uid for row in rows() for uid in row[3:]} == expected_uids
            print("offline pet artifact expiry preserves pets and sibling UIDs across restart", flush=True)
            stop()
            arm("arm-expiry")
            boot()
            client = journey.reconnect_character(port)
            deadline = time.monotonic() + 30
            while True:
                client.pending.clear()
                client.send("look")
                visible = client.expect("Pos: standing >", timeout=15)
                if "The skeleton of fixture1 waits here" not in visible:
                    break
                assert time.monotonic() < deadline, "restored finite pet did not die at its deadline"
                time.sleep(1)
            client.send("save")
            client.expect(f"Saving {journey.CHARACTER}.", timeout=30)
            assert len(rows()) == 2, "expired pet remained in owner's checkpoint"
            assert any(row[1] == seeded[0][1] for row in rows()), "permanent pet expired"
            print("restored finite pet dies at its deadline; permanent pet remains", flush=True)
            stop()
            arm("arm-cooldowns")
            sql("INSERT INTO player_affects(pid,type,duration,flags,modifier) VALUES " + ",".join(
                f"({pid},{tag},{constants['TIMER_DURATION']},{constants['TIMER_FLAGS']},{spell})"
                for spell in spells))
            initial_timers = timers()
            assert len(initial_timers) == 6, initial_timers
            cooled = {row[3] for row in rows() if row[0] == "0"}
            for cycle in range(2):
                boot()
                client = journey.reconnect_character(port)
                client.send("save")
                client.expect(f"Saving {journey.CHARACTER}.", timeout=30)
                current_timers = timers()
                assert len(current_timers) == 6, current_timers
                for kind, spell, remaining in current_timers:
                    initial = next(int(row[2]) for row in initial_timers
                                   if row[:2] == [kind, spell])
                    if kind == "player":
                        assert 0 < int(remaining) <= initial, current_timers
                    else:
                        # Pet payloads round remaining pulses up to seconds.
                        assert time.time() < int(remaining) <= initial + cycle + 1, current_timers
                print(f"cooldown restart {cycle + 1}: player short timers and v2 pet deadlines preserved", flush=True)
                if cycle == 0:
                    stop()
            # A rollback holds the v2 states; the upgrade releases them with their timers.
            stop()
            sql(f"UPDATE player_pets SET hold_reason={INVALID_STATE_HOLD} WHERE owner_pid={pid} "
                "AND COALESCE(restore_state,'')<>''")
            assert all(row[0] == "2" for row in rows() if row[3] in cooled), rows()
            boot()
            client = journey.reconnect_character(port)
            client.send("save")
            client.expect(f"Saving {journey.CHARACTER}.", timeout=30)
            assert all(row[0] == "0" for row in rows() if row[3] in cooled), rows()
            assert len(timers()) == 6, timers()
            print("upgrade releases pets a rollback held", flush=True)
            client.send("quit")
            client.expect("ACCOUNT MENU", timeout=30)
            remaining = rows()
            # A pet whose items still have custody keeps its row as custody-pending.
            held = [row for row in remaining if row[0] != "6"]
            assert len(held) == 1 and held[0][0] == "1", remaining
            assert held[0][3] == seeded[2][3], "quit discarded held equipment"
            stop()
            boot()
            client = journey.reconnect_character(port)
            client.send("save")
            client.expect(f"Saving {journey.CHARACTER}.", timeout=30)
            assert rows() == remaining, "held record changed across quit/restart"
            print("held pet equipment survives quit, restart and subsequent save", flush=True)
        except Exception:
            print((runtime / "server.out").read_text(errors="replace")[-12000:])
            print(journey.runtime_logs(runtime))
            if client:
                print(bytes(client.transcript).decode(errors="replace")[-8000:])
            raise
        finally:
            stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", type=Path, required=True)
    run(parser.parse_args().server.resolve())
