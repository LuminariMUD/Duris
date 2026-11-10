#!/usr/bin/env python3
"""Real server corpse haul and salvage pickup at the item-count cap on MariaDB."""

from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

import test_mariadb_combat_journey as journey

ROOT = Path(__file__).resolve().parents[2]


def drain(client, duration=1):
    deadline = time.monotonic() + duration
    while time.monotonic() < deadline:
        client._receive()
        time.sleep(.02)
    result = client.pending.decode(errors="replace")
    client.pending.clear()
    return result


def add_stock(runtime):
    objects_path = runtime / "areas_mini/mini.obj"
    objects = objects_path.read_text()
    start, end = objects.index("#15\n"), objects.index("#16\n")
    banana = objects[start:end]
    assert "banana~" in banana
    extra = ""
    for vnum, name in ((22810, "ruby"), (22811, "sapphire"), (22812, "marker")):
        extra += banana.replace("#15\n", f"#{vnum}\n", 1).replace(
            "banana", name).replace("Banana", name.capitalize())
    extra += banana.replace("#15\n", "#400025\n", 1).replace(
        "banana", "salvagepiece").replace("Banana", "Salvagepiece")
    objects_path.write_text(objects.replace("$~", extra + "$~"))

    zone_path = runtime / "areas_mini/mini.zon"
    zone = zone_path.read_text()
    anchor = "G 1 15 1 0 100 0 0 0 * corpse-loot marker\n"
    assert anchor in zone
    extra_resets = (
        "G 1 22810 1 0 100 0 0 0 * second corpse root\n"
        "G 1 22811 1 0 100 0 0 0 * third corpse root\n"
    )
    fillers = "O 0 22812 30 22800 100 0 0 0 * count-cap filler\n" * 20
    salvage = "O 0 400025 6 22800 100 0 0 0 * salvaged material\n" * 6
    zone_path.write_text(zone.replace(anchor, anchor + extra_resets + fillers + salvage))

    # A random salvage drop on the kill would put a fourth item in the corpse, and the haul
    # with one free slot could take it instead of a root. These values win over the ones
    # above them in the file.
    with (runtime / "lib/random_equipment.cfg").open("a") as config:
        config.write("drop.piece.percentage=0\ndrop.equipment.percentage=0\n")


def run(binary, backend):
    assert backend == "mariadb"
    with journey.mariadb_authority() as (env, sql):
        def owner_count(pid):
            return int(sql(f"SELECT COUNT(*) FROM item_current_owner WHERE owner_type=1 AND owner_id={pid} AND vnum IN (15,22810,22811) AND state=1"))

        def wallet(pid):
            return [int(value) for value in sql(
                f"SELECT copper,silver,gold,platinum FROM player_data WHERE pid={pid}").split()]

        (ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="haul-cap-", dir=ROOT / "bin/tests") as temporary:
            runtime = Path(temporary)
            journey.make_fixture(runtime, True)
            add_stock(runtime)
            journey.generate_certificate(runtime)
            (runtime / "logs/log").mkdir(parents=True)
            (runtime / "journals" / "critical").mkdir(parents=True, mode=0o700)
            game_port, tls_port, ws_port = journey.available_ports()
            env.update(CRITICAL_COMMAND_JOURNAL_DIR=str(runtime / "journals/critical"),
                       DURIS_TLS_PORT=str(tls_port), DURIS_WEBSOCKET_PORT=str(ws_port))
            output = (runtime / "server.out").open("w")
            process = None
            actor = None
            try:
                process = subprocess.Popen([str(binary), "--minimal", "-s", "-d",
                                            str(runtime), str(game_port)], cwd=runtime,
                                           env=env, stdout=output, stderr=subprocess.STDOUT)
                deadline = time.monotonic() + 120
                while "Entering game loop." not in (runtime / "server.out").read_text(errors="replace"):
                    assert process.poll() is None and time.monotonic() < deadline, "boot failed"
                    time.sleep(.1)
                # add_stock() turned the random drops off; a server that did not read that
                # file would put a random item in the corpse now and then.
                status = runtime / "logs/log/status"
                while "random equipment config: piece 0.00%, equipment 0.00%" not in (
                        status.read_text(errors="replace") if status.exists() else ""):
                    assert time.monotonic() < deadline, "the random drops were not turned off"
                    time.sleep(.1)
                actor = journey.MudClient(game_port)
                journey.create_character(actor)
                actor.send("toggle boon")
                actor.expect("Divine Boons apply automatically.")
                actor.send("wield mace")
                actor.expect("You wield")
                actor.send("drop all")
                actor.expect("You drop a steel long sword.", timeout=20)
                drain(actor)
                actor.send("get bag")
                actor.expect("You get a small leather bag.", timeout=20)
                actor.send("get all.salvagepiece")
                actor.expect("You got 6 items.", timeout=20)
                actor.send("put all.salvagepiece bag")
                actor.expect("You put", timeout=20)
                drain(actor)
                actor.send("get all.marker")
                full = actor.expect("You can't carry anything more.", timeout=60) + drain(actor)
                actor.send("inventory")
                inventory = actor.expect("Pos: standing >", timeout=20) + drain(actor)
                assert "marker" in inventory, inventory
                # Single GET starts at the cap; bulk GET must then work above it.
                # Repeat with the same bag carried and on the room floor.
                for carried_bag in (True, False):
                    if not carried_bag:
                        actor.send("drop bag")
                        actor.expect("You drop a small leather bag.", timeout=20)
                        actor.send("get marker")
                        actor.expect("You get a marker.", timeout=20)
                    drain(actor)
                    actor.send("get salvagepiece bag")
                    single = actor.expect("You get a salvagepiece", timeout=20) + drain(actor)
                    assert "can't carry" not in single, single
                    actor.send("get all.salvagepiece bag")
                    bulk = actor.expect("You got 5 items.", timeout=20) + drain(actor)
                    assert "can't carry" not in bulk, bulk
                    actor.send("save")
                    actor.expect("Saving Taverek.", timeout=30)
                    pid = int(sql("SELECT pid FROM player_data WHERE name='Taverek'"))
                    assert int(sql("SELECT COUNT(*) FROM item_current_owner WHERE "
                                   f"owner_type=1 AND owner_id={pid} AND state=1 "
                                   "AND vnum=400025 AND parent_item_uid IS NULL")) == 6
                    if not carried_bag:
                        actor.send("drop all.salvagepiece")
                        actor.expect("You drop 6 salvagepiece(s).", timeout=20)
                        drain(actor)
                        actor.send("get salvagepiece")
                        actor.expect("You get a salvagepiece.", timeout=20)
                        actor.send("get all.salvagepiece")
                        floor = actor.expect("You got 5 items.", timeout=20) + drain(actor)
                        assert "can't carry" not in floor, floor
                    actor.send("put all.salvagepiece bag")
                    actor.expect("You put", timeout=20)
                    drain(actor)
                print("PASS: capped single/bulk salvage pickup from carried/room bag and floor; six saved material roots", flush=True)
                actor.send("kill raoul")
                deadline = time.monotonic() + 45
                while True:
                    event, _ = actor.expect_any(("is dead! R.I.P.",
                                                 "You stumble, but recover in time!",
                                                 "You stumble in your attack, and jab at",
                                                 "You stumble in your attack, and hit yourself!"),
                                                timeout=max(1, deadline - time.monotonic()))
                    if event == "is dead! R.I.P.":
                        break
                    assert time.monotonic() < deadline
                    actor.send("kill raoul")
                actor.send("look in corpse")
                contents = actor.expect("sapphire", timeout=20) + drain(actor)
                assert "banana" in contents and "ruby" in contents, contents
                drain(actor)
                actor.send("get all corpse")
                first = actor.expect("You get ", timeout=60) + drain(actor)
                print("NPC corpse at cap:", first, flush=True)
                assert first.count("You can't carry any more.") == 1, first
                assert "3s" in first and "Nothing acquired." not in first, first
                actor.send("save")
                actor.expect("Saving Taverek.", timeout=30)
                pid = int(sql("SELECT pid FROM player_data WHERE name='Taverek'"))
                assert wallet(pid) == [0, 3, 0, 0]
                assert owner_count(pid) == 0
                actor.send("look in corpse")
                remaining = actor.expect("sapphire") + drain(actor)
                assert "banana" in remaining and "ruby" in remaining
                print("PASS: NPC corpse coin persisted and all three roots retained at cap", flush=True)
                actor.send("drop marker")
                actor.expect("You drop a marker.", timeout=20)
                drain(actor)
                actor.send("get all corpse")
                partial = actor.expect("You get ", timeout=60) + drain(actor)
                print("NPC corpse with one free slot:", partial, flush=True)
                assert partial.count("You can't carry any more.") == 1, partial
                assert "You get a " in partial and " from the corpse of Raoul." in partial, partial
                # The haul moves the item in memory; the save makes the ownership
                # table name the player (persistence reset step 4).
                actor.send("save")
                actor.expect("Saving Taverek.", timeout=30)
                deadline = time.monotonic() + 20
                while owner_count(pid) != 1:
                    assert time.monotonic() < deadline, "the save did not claim the hauled item"
                    time.sleep(0.1)
                actor.send("quit")
                actor.expect("ACCOUNT MENU", timeout=30)
                actor.close()
                actor = journey.reconnect_character(game_port)
                actor.send("inventory")
                inventory = actor.expect("Pos: standing >") + drain(actor)
                assert "marker" in inventory and any(
                    name in inventory for name in ("banana", "ruby", "sapphire")), inventory
                assert owner_count(pid) == 1
                journey.attack_until_death(actor)
                actor.expect("ACCOUNT MENU", timeout=45)
                actor.close()
                actor = journey.reconnect_character(game_port)
                actor.send("look")
                actor.expect("The corpse of a Human is lying here.")
                drain(actor)
                actor.send("get all Taverek")
                player = actor.expect("You can't carry any more.", timeout=60) + drain(actor)
                print("Player corpse at cap:", player, flush=True)
                assert player.count("You can't carry any more.") == 1, player
                assert "Haul:" not in player and "pulling things" not in player
                if "The coin transfer could not start; nothing changed." in player:
                    # An independent transaction admission may refuse a coin
                    # after the durable roots commit. It must remain in the
                    # corpse and be retrievable by a later capped command.
                    assert wallet(pid) == [0, 0, 0, 0]
                    actor.send("look in Taverek")
                    assert "coins" in actor.expect("coins", timeout=20) + drain(actor)
                    actor.send("get coins Taverek")
                    coin_retry = actor.expect("You get 3s.", timeout=30) + drain(actor)
                    print("Separate coin retry:", coin_retry, flush=True)
                actor.send("save")
                actor.expect("Saving Taverek.", timeout=30)
                assert wallet(pid) == [0, 3, 0, 0]
                print(f"PASS: {backend} NPC/player corpse count notice, partial haul, saved custody, wallet and reconnect", flush=True)
            except Exception:
                output.flush()
                print((runtime / "server.out").read_text(errors="replace")[-2000:])
                if actor:
                    print(actor.transcript.decode(errors="replace")[-3000:])
                raise
            finally:
                if actor:
                    actor.close()
                if process and process.poll() is None:
                    process.send_signal(signal.SIGTERM)
                    process.wait(timeout=30)
                output.close()


if __name__ == "__main__":
    run(Path(sys.argv[1]).resolve(), sys.argv[2] if len(sys.argv) > 2 else "mariadb")
