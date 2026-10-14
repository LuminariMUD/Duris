#!/usr/bin/env python3
"""Mortal specialization, multiclass and Revenant lifecycle in an isolated world.

Normal creation/Chaos switches are explicit. Staff supplies boundary state and
transfers mortals to a loaded teacher, altar and multiclass temple. This proves
command and persistence paths, not travel from a hometown or level progression.
No .env, shared listener, production database or staff account is used.
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
from run_world_quest_dual_backend import setup_run_root
from test_flight_network_journey import authority, command

ROOT = journey.ROOT
PLAYER, ACCOUNT = "Mechstudent", "Mechacct"
STAFF, STAFF_ACCOUNT = "Mechwarden", "Mechstaff"
ORC, ORC_ACCOUNT = "Mechorc", "Mechorcacct"
# Existing skill IDs; expected outcomes are independent of production formulas.
GUARD, SHIELD_PUNCH = "1120", "1145"


def run(binary, build, trace="all"):
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

            def snapshot(pid=1):
                return json.loads(subprocess.check_output(
                    [str(inspector), env["FLATFILE_STATE_DIR"], "inspect", str(pid)], text=True))

            def disabled_case(player, staff):
                fields = ("race", "birth_time", "class_primary", "class_secondary", "specialization",
                          "level", "experience", "epics", "skills", "wallet", "snapshot_uids", "player_items")

                def denied(command_text, message):
                    save(player)
                    before = snapshot()
                    reply = command(player, command_text)
                    assert message in reply, reply
                    save(player)
                    after = snapshot()
                    assert {key: before[key] for key in fields} == {key: after[key] for key in fields}

                command(staff, "setbit char " + PLAYER + " epics 300")
                command(staff, "setbit char " + PLAYER + " level 50")
                for cls in ("Paladin", "Avenger", "Theurgist"):
                    command(staff, "setbit char " + PLAYER + " class " + cls)
                    denied("ascend", "too powerful an enchantment")
                command(staff, "setbit char " + PLAYER + " class Warrior")
                denied("descend", "convictions aren't appropriate")
                command(staff, "setbit char " + PLAYER + " class Necromancer")
                command(staff, "setbit char " + PLAYER + " level 49")
                denied("descend", "must be level")
                command(staff, "setbit char " + PLAYER + " level 50")
                denied("descend", "disabled until further notice")
                command(staff, "setbit char " + PLAYER + " class Warrior")
                command(staff, "setbit char " + PLAYER + " level 1")
                print("PASS transformations.disabled/world: mortal interpreter ascend for Paladin/Avenger/Theurgist, wrong-class and level-49/50 descend preserve saved identity, skills, epics, wallet and item ownership; staff supplies classes/levels/resources", flush=True)

            def multiclass_case(player, staff, name, pid, race, safe_room):
                command(staff, "setbit char " + name + " level 50")
                if race == 1:
                    command(staff, "goto 9724")
                    command(staff, "transfer " + name)
                    command(player, "south")
                    assert "From this day onwards" in command(player, "specialize guardian")
                outside = command(player, "multiclass cleric")
                assert "not in the proper location" in outside, outside
                command(staff, "goto 52904")
                # The loaded guardian is an acquisition prerequisite. This
                # fixture isolates command/persistence behavior from combat.
                command(staff, "purge golem")
                assert "ice golem" not in command(staff, "look").lower()
                command(staff, "transfer " + name)
                command(staff, "setbit char " + name + " level 49")
                denied = command(player, "multiclass cleric")
                assert "until you reach level 50" in denied, denied
                command(staff, "setbit char " + name + " level 50")
                command(staff, "setbit char " + name + " race Gnome")
                denied = command(player, "multiclass cleric")
                assert denied.count("not versatile enough") == 1, denied
                command(staff, "setbit char " + name + " race " + ("Human" if race == 1 else "Orc"))
                denied = command(player, "multiclass nonsense")
                assert "no class, bubba" in denied, denied
                denied = command(player, "multiclass sorcerer")
                assert "cannot multiclass to that particular class" in denied, denied
                command(staff, "setbit char " + name + " epics -1")
                denied = command(player, "multiclass cleric")
                assert "need more" in denied and "experience" in denied, denied
                assert "not in the proper location" not in denied, denied
                save(player, name)
                assert snapshot(pid)["epics"] == -1 and snapshot(pid)["class_secondary"] == 0
                command(staff, "setbit char " + name + " epics 17")
                command(staff, "setbit char " + name + " played 12")
                command(staff, "setbit char " + name + " prestige 9")
                save(player, name)
                before = snapshot(pid)
                if race == 1:
                    assert before["specialization"] == 2
                selected = command(player, "multiclass cleric")
                assert "with the potential to be something much greater" in selected, selected
                save(player, name)
                after = snapshot(pid)
                assert after["class_primary"] == 1 and after["class_secondary"] == 32
                assert after["race"] == race and after["specialization"] == 0
                assert after["level"] == 1 and after["experience"] == 1
                assert after["epics"] == before["epics"] == 17  # Threshold, not a charge.
                assert before["played"] <= after["played"] <= before["played"] + 30, (before["played"], after["played"])
                assert after["prestige"] == 0 and after["trophies"] == 0
                assert after["guild_id"] == before["guild_id"] == 0
                denied = command(player, "multiclass mercenary")
                assert "already chosen your secondary class" in denied, denied
                # Staff supplies these boundary levels; this is not XP/cap progression.
                command(staff, "setbit char " + name + " level 5")
                save(player, name)
                assert snapshot(pid)["skills"].get("1022", {"learned": 0})["learned"] == 0
                command(staff, "setbit char " + name + " level 6")
                save(player, name)
                level_six = snapshot(pid)
                assert level_six["skills"]["1022"] == {"learned": 9, "taught": 95}  # Secondary meditate.
                assert level_six["skills"]["1005"]["taught"] == 100  # Primary kick.
                assert level_six["skills"]["1046"]["taught"] == 95  # Best primary/secondary bandage cap.
                # World resets may reload the guardian at the next boot. Save
                # at the character's original creation room for the relog proof.
                command(staff, "goto " + str(safe_room))
                command(staff, "transfer " + name)
                save(player, name)
                return level_six

            def revenant_case(orc, staff, orc_initial):
                command(staff, "goto " + str(orc_initial["room"]))
                command(staff, "setbit char " + ORC + " level 41")
                loaded = command(staff, "load obj 22070")
                assert "icecrown" in command(staff, "inventory").lower(), loaded
                given = command(staff, "give icecrown " + ORC)
                assert "Ok." in given, given
                assert "icecrown" in command(orc, "inventory").lower()
                command(orc, "remove all")
                worn = command(orc, "wear icecrown")
                assert "head" in worn.lower(), worn

                def wait_for_race(expected):
                    deadline = time.monotonic() + 90
                    while time.monotonic() < deadline:
                        report = command(orc, "score")
                        if "Race: " + expected in report:
                            return report
                        time.sleep(.5)
                    raise AssertionError("Revenant lifecycle did not reach " + expected + ": " + report)

                wait_for_race("Revenant")
                save(orc, ORC)
                transformed = snapshot(3)
                assert transformed["race"] == 13, transformed["race"]
                assert all(affect["type"] != 2060 for affect in transformed["affects"])
                assert "Race: Revenant" in command(orc, "score")  # Saving keeps the live form.
                stop()
                boot()
                orc = login(ORC, ORC_ACCOUNT)
                wait_for_race("Revenant")
                # The crown unequips the starter kit; make room for removal.
                command(orc, "drop all")
                removed = command(orc, "remove icecrown")
                assert "stop using" in removed.lower() or "remove" in removed.lower(), removed
                wait_for_race("Orc")
                save(orc, ORC)
                restored = snapshot(3)
                assert restored["race"] == 13
                # Capture uses the existing removal birth-date policy. A
                # race-only repair would leave the much older Revenant birth.
                assert abs(restored["birth_time"] - transformed["birth_time"]) < 180
                print("PASS revenant.reversal/persistence: worn crown applies, checkpoint/restart preserves reversible identity, removal restores Orc", flush=True)

                for death_mode in ("staff", "combat"):
                    staff = login(STAFF, STAFF_ACCOUNT)
                    command(staff, "goto " + str(orc_initial["room"]))
                    if death_mode == "combat":
                        command(staff, "load obj 22070")
                        assert "Ok." in command(staff, "give icecrown " + ORC)
                    assert "head" in command(orc, "wear icecrown").lower()
                    wait_for_race("Revenant")
                    save(orc, ORC)
                    before_death = snapshot(3)
                    if death_mode == "staff":
                        command(staff, "remove all")
                        killed = command(staff, "kill " + ORC)
                        assert "still beating heart" in killed, killed
                    else:
                        command(staff, "goto 52904")
                        assert "ice golem" in command(staff, "look").lower()
                        command(staff, "transfer " + ORC)
                        orc.send("kill golem")
                    death_text = orc.expect("Your wounds claim you at last", timeout=120)
                    if death_mode == "combat":
                        assert "golem" in death_text.lower(), death_text
                    orc.expect("ACCOUNT MENU", timeout=60)
                    deadline = time.monotonic() + 30
                    while True:
                        dead = snapshot(3)
                        if dead["revision"] > before_death["revision"] and dead["intent"] == 4:  # RENT_DEATH.
                            break
                        assert time.monotonic() < deadline, dead
                        time.sleep(.1)
                    assert dead["race"] == 13
                    assert all(affect["type"] != 2060 for affect in dead["affects"])
                    assert abs(dead["birth_time"] - before_death["birth_time"]) < 180
                    stop()
                    boot()
                    orc = journey.reconnect_character(ports[0], return_message="You rejoin the land of the living",
                                                      expected_room=None, account=ORC_ACCOUNT, character=ORC)
                    clients.append(orc)
                    orc.expect_any(("Pos: standing >", "<>"), timeout=20)
                    command(orc, "toggle paging no")
                    assert "Race: Orc" in command(orc, "score")
                    save(orc, ORC)
                    reloaded = snapshot(3)
                    assert reloaded["race"] == 13 and reloaded["birth_time"] == dead["birth_time"]
                    print("PASS revenant.death/persistence (" + death_mode + "): base race/birth survive death cleanup, terminal save, restart and resurrection", flush=True)

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
                if trace == "revenant":
                    orc = journey.MudClient(ports[0])
                    clients.append(orc)
                    journey.create_character(orc, expected_room=None, account=ORC_ACCOUNT,
                                             character=ORC, email="mechorc@example.invalid", race_name="o")
                    save(orc, ORC)
                    orc_initial = snapshot(3)
                    command(orc, "toggle paging no")
                    staff = login(STAFF, STAFF_ACCOUNT)
                    revenant_case(orc, staff, orc_initial)
                    print("Fixture: focused Revenant; normal Orc Warrior, staff level 41, supplied crowns, bare-hand staff kill and transferred temple-golem combat; flatfile, camp.timer=1; acquisition unverified", flush=True)
                    print("Server SHA256:", hashlib.sha256(binary.read_bytes()).hexdigest(), flush=True)
                    return
                staff = login(STAFF, STAFF_ACCOUNT)
                player = login(PLAYER, ACCOUNT)
                disabled_case(player, staff)
                if trace == "disabled":
                    print("Fixture: flatfile, committed full world, normal creation/Chaos switches false; staff supplies class/level/epic boundaries; corpseform callback denial is separate native evidence", flush=True)
                    print("Server SHA256:", hashlib.sha256(binary.read_bytes()).hexdigest(), flush=True)
                    return
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
                staff = login(STAFF, STAFF_ACCOUNT)
                human_multi = multiclass_case(player, staff, PLAYER, 1, 1, initial["room"])
                stop()
                boot()
                player = login(PLAYER, ACCOUNT)
                save(player)
                human_reloaded = snapshot()
                assert human_reloaded["class_secondary"] == 32 and human_reloaded["epics"] == 17
                assert human_reloaded["skills"]["1022"] == human_multi["skills"]["1022"]
                stop()
                boot()
                # Create the opposite-side mortal while the Human is offline.
                orc = journey.MudClient(ports[0])
                clients.append(orc)
                journey.create_character(orc, expected_room=None, account=ORC_ACCOUNT,
                                         character=ORC, email="mechorc@example.invalid", race_name="o")
                save(orc, ORC)
                orc_initial = snapshot(3)
                assert orc_initial["race"] == 13 and orc_initial["class_primary"] == 1
                command(orc, "toggle paging no")
                staff = login(STAFF, STAFF_ACCOUNT)
                orc_multi = multiclass_case(orc, staff, ORC, 3, 13, orc_initial["room"])
                stop()
                boot()
                orc = login(ORC, ORC_ACCOUNT)
                save(orc, ORC)
                orc_reloaded = snapshot(3)
                assert orc_reloaded["class_secondary"] == 32 and orc_reloaded["epics"] == 17
                assert orc_reloaded["skills"]["1022"] == orc_multi["skills"]["1022"]
                print("PASS multiclass.entry/persistence: normal Human/Orc creation, room 52904, denials, level/XP reset, playtime retention, no threshold charge, secondary skill 5/6 boundary/caps and restart", flush=True)
                staff = login(STAFF, STAFF_ACCOUNT)
                revenant_case(orc, staff, orc_initial)
                print("Fixture: flatfile; normally created Human/Orc Warriors; staff levels 5/6/29/30/40/41/49/50, identity denial cases, epic balances -1/9/12/17, played=12 hours, prestige=9 and transfers; temple golem purged and restart saves returned to creation rooms; camp.timer=1; Arian 9432 in room 9725, altar 12016 in room 12116 and multiclass room 52904; acquisition travel/encounters and live caps unverified", flush=True)
                print("Server SHA256:", hashlib.sha256(binary.read_bytes()).hexdigest(), flush=True)
            except BaseException:
                for client in clients:
                    print(bytes(client.transcript)[-8000:].decode(errors="replace"), flush=True)
                print(output_path.read_text(errors="replace")[-4000:], flush=True)
                raise
            finally:
                stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace", choices=("all", "revenant", "disabled"), default="all")
    args = parser.parse_args()
    subprocess.run(["make", "world"], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    (ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="character-mechanics-build-", dir=ROOT / "bin/tests") as temporary:
        build = Path(temporary)
        binary = journey.build_flatfile_server(build / "server")
        run(binary, build, args.trace)
