#!/usr/bin/env python3
"""Real NORENT-key rent/reconnect, crash and copyover on disposable authority.

The staff fixture uses the same inn and player save/load paths as a mortal.
Staff access supplies objects and controls their initial ownership history.
No checkout .env, existing account, or running server is used.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
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
INN, KEY, BAG, SIBLING = 40454, 40401, 48, 15
NORENT = 8388608


def run(binary, backend, inspector, evidence_dir):
    with tempfile.TemporaryDirectory(prefix="key-rent-" + backend + "-", dir=ROOT / "bin/tests") as temporary:
        runtime = Path(temporary)
        _, critical, output_path = setup_run_root(runtime)
        (runtime / "help").symlink_to(ROOT / "help", target_is_directory=True)
        executable = runtime / "bin/server/dms"
        executable.parent.mkdir(parents=True)
        shutil.copy2(binary, executable)
        with (runtime / "lib/misc/event_names").open("w") as names:
            subprocess.run([str(ROOT / "scripts/event_names.sh"), str(executable)], stdout=names, check=True)
        process = None
        client = None
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

            def login():
                nonlocal client
                client = journey.reconnect_character(plain, expected_room=None, account=ACCOUNT, character=PLAYER)
                client.expect("Welcome to Duris", timeout=60)
                client.expect_any(("Pos: standing >", "<>"), timeout=20)
                command(client, "toggle paging no")
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
                keys = sql("SELECT item_uid,state,owner_type,owner_id,root_item_uid,COALESCE(parent_item_uid,0) "
                           "FROM item_current_owner WHERE vnum=40401 ORDER BY item_uid")
                return {"revision": revision,
                        "items": [list(map(int, line.split())) for line in rows.splitlines()],
                        "keys": [list(map(int, line.split())) for line in keys.splitlines()]}

            def save():
                client.send("save")
                client.expect("Save complete for " + PLAYER + ".", timeout=60)
                return inspect()

            def retired(data):
                return {row[0] for row in data["keys"] if row[1] == 2}

            def preserved(data):
                return sorted(row for row in data["items"] if row[1] in (BAG, SIBLING))

            def rent(dispose=True):
                nonlocal client
                before = inspect()
                client.send("rent")
                client.expect("shows you to your room", timeout=30)
                client.expect("ACCOUNT MENU", timeout=30)
                client.close()
                client = None
                deadline = time.monotonic() + 60
                while True:
                    data = inspect()
                    complete = len(retired(data) - retired(before)) == 1 if dispose else data["items"] == before["items"]
                    if data["revision"] > before["revision"] and (sql or data["intent"] == 3) and complete:
                        return data
                    assert time.monotonic() < deadline, "rent did not commit"
                    time.sleep(.1)

            def grant_key(owned):
                assert "golden key" not in command(client, "inventory").lower()
                assert "created" in command(client, "load obj " + str(KEY)).lower()
                if owned:
                    # Save a valid non-NORENT fixture, then hydrate it through real
                    # logout/login before restoring the original lifetime flag.
                    command(client, "setbit obj golden extra NORENT 0")
                    data = save()
                    row = next(item for item in data["items"] if item[1] == KEY)
                    assert not row[2] & NORENT, data
                    uid = row[0]
                    rent(dispose=False)
                    login()
                    command(client, "setbit obj golden extra NORENT 1")
                    data = save()
                    row = next(item for item in data["items"] if item[0] == uid)
                    assert row[2] & NORENT, data
                    assert any(item[0] == uid and item[1] == 1 for item in data["keys"]), data
                    # With NORENT restored, successful save retention proves the
                    # production loader hydrated active runtime custody.
                    return uid
                data = save()
                assert not any(item[1] == KEY for item in data["items"]), data
                assert "golden key" in command(client, "inventory").lower()
                return None

            try:
                boot()
                client = journey.MudClient(plain)
                journey.create_character(client, expected_room=None, account=ACCOUNT,
                                         character=PLAYER, email="keyfixture@example.invalid")
                save()
                stop()
                if sql:
                    sql("UPDATE player_data SET level=62,highest_level=62 WHERE name='" + PLAYER + "'")
                else:
                    journey.make_overlord(Path(env["FLATFILE_STATE_DIR"]), PLAYER)
                boot()
                login()
                assert "created" in command(client, "load obj " + str(BAG)).lower()
                assert "created" in command(client, "load obj " + str(SIBLING)).lower()
                assert "Ok." in command(client, "put banana backpack")
                baseline = preserved(save())
                assert len(baseline) == 2 and any(row[4] for row in baseline), baseline
                retired_uids = set()
                for owned in (False, True):
                    for placement in ("carried", "equipped", "nested"):
                        uid = grant_key(owned)
                        before = inspect()
                        if placement == "equipped":
                            text = command(client, "hold golden")
                            assert "hold" in text.lower(), text
                            assert "golden key" in command(client, "equipment").lower()
                        elif placement == "nested":
                            text = command(client, "put golden backpack")
                            assert "Ok." in text, text
                        data = rent()
                        newly_retired = retired(data) - retired(before)
                        assert len(newly_retired) == 1, (before, data)
                        if uid is not None:
                            assert newly_retired == {uid}
                        uid = newly_retired.pop()
                        assert any(row == [uid, 2, 8, 0, uid, 0] for row in data["keys"]), data
                        assert not any(row[1] == KEY for row in data["items"]), data
                        assert preserved(data) == baseline, data
                        retired_uids.add(uid)
                        login()
                        assert "golden key" not in command(client, "inventory").lower()
                        assert "golden key" not in command(client, "equipment").lower()
                        assert "golden key" not in command(client, "look in backpack").lower()
                        data = save()
                        assert retired_uids <= retired(data) and preserved(data) == baseline
                        evidence["rent_cases"].append({"owned": owned, "placement": placement, "uid": uid})
                        print(backend, "rent", owned, placement, "passed", flush=True)
                stop()
                boot()
                login()
                data = save()
                assert retired_uids <= retired(data) and preserved(data) == baseline
                assert not any(row[1] == KEY for row in data["items"])
                evidence["checks"].append("all six rent cases remain absent after server restart")

                active_uid = grant_key(True)
                save()
                stop(crash=True)
                boot()
                login()
                assert any(row[0] == active_uid for row in save()["items"]), "active key lost on crash"
                process.send_signal(signal.SIGUSR1)
                client.expect("Copyover complete!", timeout=180)
                assert "golden key" in command(client, "inventory").lower()
                assert any(row[0] == active_uid for row in save()["items"]), "active key lost on copyover"
                evidence["checks"].append("active key survives checkpoint, SIGKILL/relogin and copyover")
                rent()
                login()

                # Fresh NORENT keys have always been omitted from crash snapshots.
                # PC inventory is not part of copyover's separate world/NPC trees.
                grant_key(False)
                process.send_signal(signal.SIGUSR1)
                client.expect("Copyover complete!", timeout=180)
                assert "golden key" not in command(client, "inventory").lower()
                assert not any(row[1] == KEY for row in save()["items"])
                grant_key(False)
                stop(crash=True)
                boot()
                login()
                assert "golden key" not in command(client, "inventory").lower()
                assert not any(row[1] == KEY for row in save()["items"])
                evidence["checks"].append("fresh-key omission unchanged on checkpoint, crash and copyover")
                assert preserved(inspect()) == baseline
                stop()
                evidence["passed"] = True
                print(backend, "all rent, restart, crash and copyover checks passed", flush=True)
            finally:
                evidence_dir.mkdir(parents=True, exist_ok=True)
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
    if args.backend == "flatfile":
        subprocess.run(["python3", "tests/async/test_flatfile_player_repository.py",
                        "--build-inspector", str(inspector)], cwd=ROOT, check=True)
    binary = args.server.resolve() if args.server else journey.build_flatfile_server(evidence / "journey-build")
    run(binary, args.backend, inspector, evidence)


if __name__ == "__main__":
    main()
