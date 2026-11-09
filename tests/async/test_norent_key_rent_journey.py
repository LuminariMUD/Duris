#!/usr/bin/env python3
"""Real no-rent rent/camp/link-death, crash and copyover on disposable authority.

The staff fixture uses the same inn and player save/load paths as a mortal.
Staff access supplies objects and controls their initial ownership history.
No checkout .env, existing account, or running server is used.
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
from test_flight_network_journey import authority, command
from run_world_quest_dual_backend import setup_run_root

ROOT = journey.ROOT
PLAYER, ACCOUNT = "Keywarden", "Keyacct"
MORTAL, MORTAL_ACCOUNT = "Campwarden", "Campacct"
INN, KEY, BAG, SIBLING, TICKET = 40454, 40401, 48, 15, 47003
SHOP, SHOP_KEY = 5848, 5783
CAMP_ROOM = 1457
NORENT = 8388608
FALLS, CRUMBLES = "is no-rent and falls to the floor", "is no-rent and crumbles to dust"


def run(binary, backend, inspector, evidence_dir):
    with tempfile.TemporaryDirectory(prefix="key-rent-" + backend + "-", dir=ROOT / "bin/tests") as temporary:
        runtime = Path(temporary)
        _, critical, output_path = setup_run_root(runtime)
        (runtime / "help").symlink_to(ROOT / "help", target_is_directory=True)
        properties = runtime / "lib/duris.properties"
        properties.write_text(properties.read_text().replace("camp.timer=9.000", "camp.timer=1.000"))
        executable = runtime / "bin/server/dms"
        executable.parent.mkdir(parents=True)
        shutil.copy2(binary, executable)
        with (runtime / "lib/misc/event_names").open("w") as names:
            subprocess.run([str(ROOT / "scripts/event_names.sh"), str(executable)], stdout=names, check=True)
        process = None
        client = None
        mortal = None
        evidence = {"backend": backend, "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
                    "rent_cases": [], "checks": []}
        plain, tls, websocket = journey.available_ports()
        with authority(backend, runtime) as (env, sql), output_path.open("w") as output:
            env.update(CRITICAL_COMMAND_JOURNAL_DIR=str(critical), DURIS_TLS_PORT=str(tls),
                       DURIS_WEBSOCKET_PORT=str(websocket), MAINTENANCE_STATE_FILE=str(runtime / "maintenance.state"))

            def boot():
                nonlocal process
                offset = output_path.stat().st_size
                process = subprocess.Popen([str(executable), "-d", str(runtime), str(plain)], cwd=runtime,
                                           env=env, stdout=output, stderr=subprocess.STDOUT)
                deadline = time.monotonic() + 180
                while b"Entering game loop." not in output_path.read_bytes()[offset:]:
                    assert process.poll() is None and time.monotonic() < deadline, "server failed to boot"
                    time.sleep(.1)

            def stop(crash=False):
                nonlocal client, process
                if client:
                    client.close()
                    client = None
                process.send_signal(signal.SIGKILL if crash else signal.SIGTERM)
                process.wait(timeout=60)
                assert process.returncode == (-signal.SIGKILL if crash else 0)
                process = None

            def enter(account, character):
                session = journey.reconnect_character(plain, expected_room=None, account=account, character=character)
                session.expect("Welcome to Duris", timeout=60)
                session.expect_any(("Pos: standing >", "<>"), timeout=20)
                command(session, "toggle paging no")
                return session

            def login():
                nonlocal client
                client = enter(ACCOUNT, PLAYER)
                command(client, "goto " + str(INN))
                command(client, "setbit room here flag ROOM_MAGIC_LIGHT 1")

            def inspect():
                if not sql:
                    return json.loads(subprocess.check_output(
                        [str(inspector), env["FLATFILE_STATE_DIR"], "norent-inspect", "1"], text=True))
                revision = int(sql("SELECT save_revision FROM player_data WHERE name='" + PLAYER + "'"))
                rows = sql("SELECT p.obj_uid,p.vnum,p.extra_flags,p.equip_slot,COALESCE(b.obj_uid,0) "
                           "FROM player_items p LEFT JOIN player_items b ON b.id=p.container_id "
                           "WHERE p.pid=(SELECT pid FROM player_data WHERE name='" + PLAYER + "') ORDER BY p.id")
                owners = sql("SELECT item_uid,state,owner_type,owner_id,root_item_uid,COALESCE(parent_item_uid,0) "
                             "FROM item_current_owner WHERE vnum IN (%d,%d,%d) ORDER BY item_uid" % (KEY, TICKET, SHOP_KEY))
                return {"revision": revision,
                        "items": [list(map(int, line.split())) for line in rows.splitlines()],
                        "keys": [list(map(int, line.split())) for line in owners.splitlines()]}

            def save():
                client.send("save")
                client.expect("Saving " + PLAYER + ".", timeout=60)
                return inspect()

            def preserved(data):
                return sorted(row for row in data["items"] if row[1] in (BAG, SIBLING))

            def rent(gone=None, message=FALLS):
                """Rent at the inn. `gone` is a vnum that must be off the character and out of the save."""
                nonlocal client
                before = inspect()
                client.send("rent")
                text = client.expect("shows you to your room", timeout=30)
                if gone:
                    assert message in text, text
                client.expect("ACCOUNT MENU", timeout=30)
                client.close()
                client = None
                deadline = time.monotonic() + 60
                while True:
                    data = inspect()
                    complete = (not any(row[1] == gone for row in data["items"])) if gone else data["items"] == before["items"]
                    if data["revision"] > before["revision"] and (sql or data["intent"] == 3) and complete:
                        return data
                    assert time.monotonic() < deadline, "rent did not commit"
                    time.sleep(.1)

            def on_floor(session, word):
                """A staff purge succeeds only for something lying in the room."""
                return "don't know anyone" not in command(session, "purge " + word)

            def grant(vnum, word, label, owned):
                assert label not in command(client, "inventory").lower()
                assert "created" in command(client, "load obj " + str(vnum)).lower()
                if owned:
                    # Save a valid non-NORENT fixture, then hydrate it through real
                    # logout/login before restoring the original lifetime flag.
                    command(client, "setbit obj " + word + " extra NORENT 0")
                    data = save()
                    row = next(item for item in data["items"] if item[1] == vnum)
                    assert not row[2] & NORENT, data
                    uid = row[0]
                    rent()
                    login()
                    command(client, "setbit obj " + word + " extra NORENT 1")
                    data = save()
                    row = next(item for item in data["items"] if item[0] == uid)
                    assert row[2] & NORENT, data
                    assert any(item[0] == uid and item[1] == 1 for item in data["keys"]), data
                    # With NORENT restored, successful save retention proves the
                    # production loader hydrated active runtime custody.
                    return uid
                data = save()
                assert not any(item[1] == vnum for item in data["items"]), data
                assert label in command(client, "inventory").lower()
                return None

            def copyover():
                # A full-world handoff can leave background artifact writes pending.
                # Qualify key retention after those writers settle, without weakening
                # the production handoff's bounded durability drain.
                deadline = time.monotonic() + 180
                while True:
                    status = command(client, "world persistence")
                    artifact = next(line for line in status.splitlines()
                                    if line.startswith("artifact_guild "))
                    counts = dict(re.findall(r"(\w+)=(\d+)", artifact))
                    if (all(counts[name] == "0" for name in
                            ("dirty_artifacts", "dirty_guilds", "history_pending")) and
                            "critical_commands state=ready " in status):
                        break
                    assert time.monotonic() < deadline, status
                    time.sleep(.1)
                process.send_signal(signal.SIGUSR1)
                result, output_text = client.expect_any(
                    ("Copyover complete!", "Copyover FAILED", "Copyover cancelled"), timeout=180)
                assert result == "Copyover complete!", output_text + journey.runtime_logs(runtime)

            def mortal_revision():
                return int(sql("SELECT save_revision FROM player_data WHERE name='" + MORTAL + "'"))

            def mortal_tickets():
                return int(sql("SELECT COUNT(*) FROM player_items WHERE vnum=" + str(TICKET) +
                               " AND pid=(SELECT pid FROM player_data WHERE name='" + MORTAL + "')"))

            def wait_mortal_saved(before):
                deadline = time.monotonic() + 60
                while mortal_revision() <= before:
                    assert time.monotonic() < deadline, "mortal departure did not commit"
                    time.sleep(.1)
                assert mortal_tickets() == 0, "the no-rent ticket stayed with the mortal"

            def mortal_with_ticket():
                """Bring the mortal to the staff character and hand over a no-rent ticket."""
                nonlocal mortal
                mortal = enter(MORTAL_ACCOUNT, MORTAL)
                command(client, "trans " + MORTAL)
                assert "created" in command(client, "load obj " + str(TICKET)).lower()
                command(client, "give ticket " + MORTAL)
                assert "ticket" in command(mortal, "inventory").lower()

            try:
                boot()
                client = journey.MudClient(plain)
                journey.create_character(client, expected_room=None, account=ACCOUNT,
                                         character=PLAYER, email="keyfixture@example.invalid")
                save()
                mortal = journey.MudClient(plain)
                journey.create_character(mortal, expected_room=None, account=MORTAL_ACCOUNT,
                                         character=MORTAL, email="campfixture@example.invalid")
                mortal.close()
                mortal = None
                stop()
                if sql:
                    sql("UPDATE player_data SET level=62,highest_level=62,platinum=5000 WHERE name='" + PLAYER + "'")
                boot()
                login()
                assert "created" in command(client, "load obj " + str(BAG)).lower()
                assert "created" in command(client, "load obj " + str(SIBLING)).lower()
                assert "Ok." in command(client, "put banana backpack")
                baseline = preserved(save())
                assert len(baseline) == 2 and any(row[4] for row in baseline), baseline

                cases = [(KEY, "golden", "golden key", owned, place) for owned in (False, True)
                         for place in ("carried", "equipped", "nested")]
                cases += [(TICKET, "ticket", "ticket", owned, "carried") for owned in (False, True)]
                for vnum, word, label, owned, place in cases:
                    grant(vnum, word, label, owned)
                    if place == "equipped":
                        text = command(client, "hold " + word)
                        assert "hold" in text.lower(), text
                        assert label in command(client, "equipment").lower()
                    elif place == "nested":
                        text = command(client, "put " + word + " backpack")
                        assert "Ok." in text, text
                    data = rent(gone=vnum)
                    assert preserved(data) == baseline, data
                    login()
                    assert label not in command(client, "inventory").lower()
                    assert label not in command(client, "equipment").lower()
                    assert label not in command(client, "look in backpack").lower()
                    assert on_floor(client, word), word + " did not land on the floor"
                    assert preserved(save()) == baseline
                    evidence["rent_cases"].append({"item": word, "owned": owned, "placement": place})
                    print(backend, "rent", word, owned, place, "passed", flush=True)
                stop()
                boot()
                login()
                data = save()
                assert preserved(data) == baseline
                assert not any(row[1] in (KEY, TICKET) for row in data["items"])
                evidence["checks"].append("no-rent items stay gone after a restart")

                command(client, "goto " + str(SHOP))
                command(client, "setbit room here flag ROOM_MAGIC_LIGHT 1")
                text = command(client, "buy small", timeout=60)
                deadline = time.monotonic() + 30
                while "small key" not in command(client, "inventory").lower():
                    assert time.monotonic() < deadline, "shop key never arrived: " + text
                    time.sleep(1)
                assert any(row[1] == SHOP_KEY for row in save()["items"]), "shop key has no saved record"
                command(client, "goto " + str(INN))
                data = rent(gone=SHOP_KEY)
                assert preserved(data) == baseline, data
                login()
                assert on_floor(client, "small"), "shop key did not land on the floor"
                evidence["checks"].append("a shop-bought no-rent item falls")

                for field, flag in (("extra", "NODROP"), ("extra2", "SOULBIND")):
                    assert "created" in command(client, "load obj " + str(TICKET)).lower()
                    command(client, "setbit obj ticket " + field + " " + flag + " 1")
                    rent(gone=TICKET, message=CRUMBLES)
                    login()
                    assert not on_floor(client, "ticket"), flag + " item reached the floor"
                    evidence["checks"].append("a " + flag + " no-rent item crumbles")

                command(client, "goto " + str(CAMP_ROOM))
                command(client, "setbit room here flag ROOM_MAGIC_LIGHT 1")
                command(client, "setbit room here flag SAFE 1")
                mortal_with_ticket()
                before = mortal_revision()
                mortal.send("camp")
                mortal.expect("setting up camp", timeout=20)
                text = mortal.expect("hunker down", timeout=120)
                assert FALLS in text, text
                mortal.close()
                mortal = None
                wait_mortal_saved(before)
                assert on_floor(client, "ticket"), "camped ticket did not land on the floor"
                evidence["checks"].append("a mortal's no-rent item falls when camp finishes")

                mortal_with_ticket()
                before = mortal_revision()
                mortal.close()
                mortal = None
                deadline = time.monotonic() + 30
                while "Extracted ghost" not in command(client, "extractlink " + MORTAL):
                    assert time.monotonic() < deadline, "the link-dead mortal could not be extracted"
                    time.sleep(1)
                wait_mortal_saved(before)
                assert on_floor(client, "ticket"), "link-dead ticket did not land on the floor"
                evidence["checks"].append("a link-dead character's no-rent item falls on extractlink")

                mortal_with_ticket()
                before = mortal_revision()
                command(client, "setbit char " + MORTAL + " timer 16")
                mortal.expect("pulled into a void", timeout=100)
                mortal.close()
                mortal = None
                wait_mortal_saved(before)
                assert on_floor(client, "ticket"), "idle-voided ticket did not land on the floor"
                evidence["checks"].append("an idle-voided character's no-rent item falls")
                command(client, "goto " + str(INN))

                active_uid = grant(KEY, "golden", "golden key", True)
                save()
                stop(crash=True)
                boot()
                login()
                assert any(row[0] == active_uid for row in save()["items"]), "active key lost on crash"
                copyover()
                assert "golden key" in command(client, "inventory").lower()
                assert any(row[0] == active_uid for row in save()["items"]), "active key lost on copyover"
                evidence["checks"].append("active key survives checkpoint, SIGKILL/relogin and copyover")
                rent(gone=KEY)
                login()
                assert on_floor(client, "golden"), "active key did not land on the floor"

                # Fresh NORENT keys have always been omitted from crash snapshots.
                # PC inventory is not part of copyover's separate world/NPC trees.
                grant(KEY, "golden", "golden key", False)
                copyover()
                assert "golden key" not in command(client, "inventory").lower()
                assert not any(row[1] == KEY for row in save()["items"])
                grant(KEY, "golden", "golden key", False)
                stop(crash=True)
                boot()
                login()
                assert "golden key" not in command(client, "inventory").lower()
                assert not any(row[1] == KEY for row in save()["items"])
                evidence["checks"].append("fresh-key omission unchanged on checkpoint, crash and copyover")
                assert preserved(inspect()) == baseline

                command(client, "setbit obj backpack extra NORENT 1")
                data = rent(gone=BAG)
                banana = next(row for row in data["items"] if row[1] == SIBLING)
                assert banana[3] == 0 and banana[4] == 0, data
                login()
                assert on_floor(client, "backpack"), "no-rent bag did not land on the floor"
                assert "banana" in command(client, "inventory").lower()
                evidence["checks"].append("a saved item in a no-rent bag survives and the bag falls")
                stop()
                evidence["passed"] = True
                print(backend, "all rent, camp, link-death, restart, crash and copyover checks passed", flush=True)
            finally:
                evidence_dir.mkdir(parents=True, exist_ok=True)
                if mortal:
                    mortal.close()
                if client:
                    (evidence_dir / (backend + "-transcript.txt")).write_bytes(bytes(client.transcript))
                    client.close()
                if process and process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=60)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=10)
                (evidence_dir / (backend + ".json")).write_text(json.dumps(evidence, indent=2) + "\n")
                shutil.copy2(output_path, evidence_dir / (backend + "-server.log"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("flatfile", "mariadb"), default="flatfile")
    parser.add_argument("--server", type=Path)
    args = parser.parse_args()
    if args.backend == "mariadb" and not args.server:
        parser.error("pass --server for MariaDB")
    evidence = ROOT / "bin/qualification/issue419"
    evidence.mkdir(parents=True, exist_ok=True)
    subprocess.run(["make", "world"], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    inspector = evidence / "rent-inspector"
    binary = args.server.resolve() if args.server else journey.build_flatfile_server(evidence / "journey-build")
    run(binary, args.backend, inspector, evidence)


if __name__ == "__main__":
    main()
