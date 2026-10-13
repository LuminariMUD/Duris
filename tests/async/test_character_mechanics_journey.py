#!/usr/bin/env python3
"""Mortal specialization and persisted abilities in an isolated full world.

Normal creation/Chaos switches are explicit. Staff supplies boundary levels and
transfers the mortal to the hall adjoining a loaded teacher. This proves the
command and persistence paths, not travel from a hometown or level progression.
No .env, shared listener, production database or staff account is used.
"""

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
from run_world_quest_dual_backend import setup_run_root
from test_flight_network_journey import authority, command

ROOT = journey.ROOT
PLAYER, ACCOUNT = "Mechstudent", "Mechacct"
STAFF, STAFF_ACCOUNT = "Mechwarden", "Mechstaff"
# Existing skill IDs; expected outcomes are independent of production formulas.
GUARD, SHIELD_PUNCH = "1120", "1145"


def run(binary, build):
    inspector = build / "mechanics-inspector"
    subprocess.run(["python3", "tests/async/test_flatfile_player_repository.py",
                    "--build-inspector", str(inspector)], cwd=ROOT, check=True, timeout=180)
    with tempfile.TemporaryDirectory(prefix="character-mechanics-world-", dir=ROOT / "bin/tests") as temporary:
        runtime = Path(temporary)
        _, critical, output_path = setup_run_root(runtime)
        properties = runtime / "lib/duris.properties"
        original_properties = properties.read_text()
        assert "camp.timer=9.000" in original_properties
        properties.write_text(original_properties.replace("camp.timer=9.000", "camp.timer=1.000"))
        executable = runtime / "bin/server/dms"
        executable.parent.mkdir(parents=True)
        shutil.copy2(binary, executable)
        executable.chmod(0o700)
        with (runtime / "lib/misc/event_names").open("w") as names:
            subprocess.run([str(ROOT / "scripts/event_names.sh"), str(executable)], stdout=names, check=True)
        ports = journey.available_ports()
        process = None
        clients = []
        with authority("flatfile", runtime) as (env, _), output_path.open("w") as output:
            env.update(CHAOS_MUD="FALSE", CREATION_ALL_RACES="FALSE", CREATION_ALL_CLASSES="FALSE",
                       CRITICAL_COMMAND_JOURNAL_DIR=str(critical), DURIS_TLS_PORT=str(ports[1]),
                       DURIS_WEBSOCKET_PORT=str(ports[2]),
                       MAINTENANCE_STATE_FILE=str(runtime / "maintenance.state"))

            def boot():
                nonlocal process
                offset = output_path.stat().st_size
                process = subprocess.Popen([str(executable), "-d", str(runtime), str(ports[0])],
                                           cwd=runtime, env=env, stdout=output, stderr=subprocess.STDOUT)
                deadline = time.monotonic() + 180
                while b"Entering game loop." not in output_path.read_bytes()[offset:]:
                    assert process.poll() is None and time.monotonic() < deadline, output_path.read_text()[-6000:]
                    time.sleep(.1)
                assert Path(os.readlink(f"/proc/{process.pid}/exe")).resolve() == executable

            def stop():
                for client in clients:
                    client.close()
                clients.clear()
                if process is not None and process.poll() is None:
                    process.send_signal(signal.SIGTERM)
                    process.wait(timeout=45)
                    assert process.returncode == 0

            def login(name, account):
                client = journey.reconnect_character(ports[0], expected_room=None,
                                                     account=account, character=name)
                clients.append(client)
                client.expect("Welcome to Duris", timeout=60)
                client.expect_any(("Pos: standing >", "<>"), timeout=20)
                command(client, "toggle paging no")
                return client

            def save(client, name=PLAYER):
                client.send("save")
                client.expect("Save complete for " + name + ".", timeout=60)

            def snapshot():
                return json.loads(subprocess.check_output(
                    [str(inspector), env["FLATFILE_STATE_DIR"], "inspect", "1"], text=True))

            try:
                boot()
                for name, account in ((PLAYER, ACCOUNT), (STAFF, STAFF_ACCOUNT)):
                    client = journey.MudClient(ports[0])
                    clients.append(client)
                    journey.create_character(client, expected_room=None, account=account,
                                             character=name, email=name.lower() + "@example.invalid")
                    save(client, name)
                initial = snapshot()
                assert initial["race"] == 1 and initial["class_primary"] == 1 and initial["specialization"] == 0
                assert GUARD not in initial["skills"] and SHIELD_PUNCH not in initial["skills"]
                stop()
                journey.make_overlord(Path(env["FLATFILE_STATE_DIR"]), STAFF)
                boot()
                staff = login(STAFF, STAFF_ACCOUNT)
                player = login(PLAYER, ACCOUNT)
                denied = command(player, "specialize guardian")
                assert "find a teacher first" in denied, denied
                command(staff, "setbit char " + PLAYER + " level 29")
                command(staff, "goto 9724")
                moved = command(staff, "transfer " + PLAYER)
                assert "Ok." in moved, moved
                command(player, "south")  # Existing exit to Arian's reset room 9725.
                denied = command(player, "specialize guardian")
                assert "not yet experienced enough" in denied, denied
                save(player)
                assert snapshot()["specialization"] == 0
                command(staff, "setbit char " + PLAYER + " level 30")
                command(staff, "setbit char " + PLAYER + " race Thri-Kreen")
                denied = command(player, "specialize guardian")
                assert "specialization isn't available" in denied, denied
                command(staff, "setbit char " + PLAYER + " race Human")
                command(staff, "setbit char " + PLAYER + " class Ranger")
                denied = command(player, "specialize guardian")
                assert "find a teacher first" in denied, denied
                command(staff, "setbit char " + PLAYER + " class Warrior")
                command(staff, "setbit char " + PLAYER + " secondary Cleric")
                denied = command(player, "specialize guardian")
                assert "already chosen another path" in denied, denied
                # Exercise the repaired setter/skill-refresh path as well. Its
                # existing invalid-primary policy normalizes None to Warrior.
                command(staff, "setbit char " + PLAYER + " class None")
                save(player)
                reset_state = snapshot()
                assert reset_state["class_primary"] == 1 and reset_state["class_secondary"] == 32
                command(staff, "setbit char " + PLAYER + " secondary None")
                save(player)
                assert snapshot()["class_secondary"] == 0
                denied = command(player, "specialize healer")
                assert "specialization isn't available" in denied, denied
                selected = command(player, "specialize guardian")
                assert "From this day onwards" in selected and "Guardian" in selected, selected
                denied = command(player, "specialize swordsman")
                assert "already specialized" in denied, denied
                save(player)
                selected_state = snapshot()
                assert selected_state["specialization"] == 2 and selected_state["class_secondary"] == 0
                for skill in (GUARD, SHIELD_PUNCH):
                    assert selected_state["skills"][skill] == {"learned": 40, "taught": 100}, selected_state["skills"].get(skill)
                command(staff, "setbit char " + PLAYER + " level 40")
                locked = command(player, "innate")
                assert "*bulwark (unlocks at level 41)" in locked, locked
                denied = command(player, "innate bulwark")
                assert "You know no such ability!" in denied, denied
                command(staff, "setbit char " + PLAYER + " level 41")
                innates = command(player, "innate")
                assert "*bulwark\r\n" in innates and "bulwark (unlocks" not in innates, innates
                passive = command(player, "innate bulwark")
                assert "This innate is always active." in passive, passive
                save(player)
                player.send("quit")
                player.expect("ACCOUNT MENU", timeout=45)
                player.send("0")
                player.close()
                clients.remove(player)
                player = login(PLAYER, ACCOUNT)
                assert "This innate is always active." in command(player, "innate bulwark")
                save(player)
                reloaded = snapshot()
                assert reloaded["specialization"] == 2 and reloaded["level"] == 41
                for skill in (GUARD, SHIELD_PUNCH):
                    assert reloaded["skills"][skill] == selected_state["skills"][skill]
                stop()
                boot()
                player = login(PLAYER, ACCOUNT)
                assert "This innate is always active." in command(player, "innate bulwark")
                save(player)
                assert snapshot()["specialization"] == 2
                print("PASS specialization.entry/persistence: mortal denials, real teacher selection, skills, Bulwark 40/41, relog and restart", flush=True)
                staff = login(STAFF, STAFF_ACCOUNT)
                command(staff, "goto 12116")
                command(staff, "transfer " + PLAYER)
                altar_room = command(player, "look")
                assert "A strange altar the colour of blood is here." in altar_room, altar_room
                command(staff, "setbit char " + PLAYER + " epics 9")
                denied = command(player, "pray altar")
                assert "need 10 epic points" in denied, denied
                save(player)
                denied_state = snapshot()
                assert denied_state["epics"] == 9 and denied_state["specialization"] == 2
                command(staff, "setbit char " + PLAYER + " epics 12")
                reverted = command(player, "pray altar")
                assert "old habits fall away" in reverted, reverted
                assert "You know no such ability!" in command(player, "innate bulwark")
                denied = command(player, "pray altar")
                assert "get no response" in denied, denied
                save(player)
                reverted_state = snapshot()
                assert reverted_state["epics"] == 2 and reverted_state["specialization"] == 0
                assert reverted_state["class_primary"] == 1 and reverted_state["class_secondary"] == 0
                assert reverted_state["race"] == 1 and reverted_state["level"] == 41
                assert SHIELD_PUNCH not in reverted_state["skills"]
                # Guard is also a base Warrior skill at 41: keep it with its
                # lower unspecialized cap instead of erasing all prior grants.
                assert reverted_state["skills"][GUARD] == {"learned": 40, "taught": 70}
                stop()
                boot()
                player = login(PLAYER, ACCOUNT)
                assert "You know no such ability!" in command(player, "innate bulwark")
                save(player)
                restarted = snapshot()
                assert restarted["epics"] == 2 and restarted["specialization"] == 0
                assert SHIELD_PUNCH not in restarted["skills"]
                assert restarted["skills"][GUARD] == reverted_state["skills"][GUARD]
                print("PASS specialization.reversal: loaded altar, insufficient funds, single 10-epic purchase, skill/passive refresh and restart", flush=True)
                print("Fixture: flatfile; Human Warrior; staff levels 29/30/40/41, identity denial cases, epic balances 9/12 and transfers; camp.timer=1; Arian 9432 in room 9725 and altar 12016 in room 12116; acquisition travel and live caps unverified", flush=True)
                print("Server SHA256:", hashlib.sha256(binary.read_bytes()).hexdigest(), flush=True)
            except BaseException:
                for client in clients:
                    print(bytes(client.transcript)[-8000:].decode(errors="replace"), flush=True)
                print(output_path.read_text(errors="replace")[-4000:], flush=True)
                raise
            finally:
                stop()


if __name__ == "__main__":
    subprocess.run(["make", "world"], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    (ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="character-mechanics-build-", dir=ROOT / "bin/tests") as temporary:
        build = Path(temporary)
        binary = journey.build_flatfile_server(build / "server")
        run(binary, build)
