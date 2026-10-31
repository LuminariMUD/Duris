#!/usr/bin/env python3
"""Verify NPC container custody and floor pickup messages on a disposable server."""
import os
from pathlib import Path
import re
import signal
import subprocess
import tempfile
import time
import test_flatfile_combat_journey as journey


def run(binary: Path, expect_abort: bool = False) -> None:
    with tempfile.TemporaryDirectory(prefix="npc-claim-state-") as state_dir:
        with tempfile.TemporaryDirectory(prefix="npc-claim-game-") as game_dir:
            state, game = Path(state_dir), Path(game_dir)
            state.chmod(0o700)
            (state / "domains").mkdir(mode=0o700)
            subprocess.run([str(journey.INSPECTOR), str(state), "seed-combat"], check=True)
            (game / "logs/log").mkdir(parents=True)
            journey.make_fixture(game)
            object_path = game / "areas_mini/mini.obj"
            objects = object_path.read_text()
            assert objects.count("12 28 0 0 7 0 0 16385 0 0 0") == 1
            objects = objects.replace("12 28 0 0 7 0 0 16385 0 0 0",
                                      "12 28 0 0 7 0 0 1 0 0 0")
            # Loading adds HOLD to every takeable object. The token denies Human
            # equipment use (last field = 1) so this NPC leaves it in inventory.
            floor_objects = """#22802
scavengertunic tunic~
a scavenger test tunic~
A scavenger test tunic lies here.~
~
9 16 0 0 7 0 0 9 0 0 0
5 0 0 0 0 0 0 0
1 500 100
#22803
scavengertoken token~
a scavenger test token~
A scavenger test token lies here.~
~
12 16 0 0 7 0 0 1 0 0 1
0 0 0 0 0 0 0 0
1 500 100
"""
            assert objects.count("$~") == 1
            object_path.write_text(objects.replace("$~", floor_objects + "$~"))
            # Separate floor cases from the container and its earlier scavenger.
            world_path = game / "areas_mini/mini.wld"
            world_path.write_text(world_path.read_text().replace("$~", """#22802
The Scavenger Floor~
A quiet room for observing scavenger floor pickups.
~
1 0 0
S
$~"""))
            journey.generate_certificate(game)
            mobile_path = game / "areas_mini/mini.mob"
            mobile_path.write_text(mobile_path.read_text().replace("$~", """#22801
claim scavenger~
a claim scavenger~
A claim scavenger waits here.~
~
6 0 0 0 0 0 0 0 S
PH 0 0 -1
10 0 0 20d1+400 2d1+1
0.0.0.0 0
8 8 0
$~"""))
            zone_path = game / "areas_mini/mini.zon"
            zone = "\n".join(line for line in zone_path.read_text().splitlines()
                             if not line.startswith(("M 0 11 ", "G 1 15 ", "G 1 3 ",
                                                     "M 0 22800 "))) + "\n"
            zone_path.write_text(zone.replace(
                "\nS\n", "\nO 0 48 1 22800 100 0 0 0 * takeable container\n"
                         "P 1 11 1 48 100 0 0 0 * nested ordinary item\nS\n"))
            (game / "journals" / "critical").mkdir(parents=True, mode=0o700)
            port, tls_port, ws_port = journey.available_ports()
            env = dict(PATH=os.environ.get("PATH", "/usr/bin:/bin"),
                       ENVIRONMENT="local", PERSISTENCE_MODE="flatfile-primary",
                       FLATFILE_STATE_DIR=str(state),
                       CRITICAL_COMMAND_JOURNAL_DIR=str(game / "journals/critical"),
                       LISTEN_ADDRESS="127.0.0.1", DURIS_TLS_PORT=str(tls_port),
                       DURIS_WEBSOCKET_LISTEN_ADDRESS="127.0.0.1",
                       DURIS_WEBSOCKET_PORT=str(ws_port), REDIS="FALSE",
                       CHAOS_MUD="FALSE")
            if os.environ.get("LD_LIBRARY_PATH"):
                env["LD_LIBRARY_PATH"] = os.environ["LD_LIBRARY_PATH"]
            output_path = game / "server.out"
            process = None
            client = None

            def boot() -> None:
                nonlocal process
                output = output_path.open("a")
                process = subprocess.Popen([str(binary), "--minimal", "-s", "-d",
                                            str(game), str(port)], cwd=game, env=env,
                                           stdout=output, stderr=subprocess.STDOUT)
                output.close()
                deadline = time.monotonic() + 120
                while "Entering game loop." not in output_path.read_text(errors="replace"):
                    assert process.poll() is None and time.monotonic() < deadline, output_path.read_text(errors="replace")[-4000:]
                    time.sleep(.1)

            def stop() -> None:
                nonlocal process, client
                if client:
                    client.close()
                    client = None
                if process and process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                process = None

            try:
                boot()
                client = journey.MudClient(port)
                journey.create_character(client)
                client.send("save")
                client.expect("Save complete for Taverek.", timeout=20)
                client.send("quit")
                client.expect("ACCOUNT MENU", timeout=20)
                stop()
                subprocess.run([str(journey.INSPECTOR), str(state),
                                "seed-item-operator"], check=True)
                # The new boot resets the test container. A staff player makes the
                # nested item authoritative, then loads the scavenger in that room.
                output_path.write_text("")
                boot()
                client = journey.reconnect_character(port)
                client.send("get miles backpack")
                client.expect("get a 1000 frequent flier miles", timeout=20)
                client.send("get backpack")
                client.expect("get a large leather backpack", timeout=20)
                client.send("put miles backpack")
                client.expect("Ok.", timeout=20)
                client.send("drop backpack")
                client.expect("drop a large leather backpack", timeout=20)
                # Items move in memory: the drop leaves the ownership catalog alone.
                print("player: get miles backpack -> get backpack -> put miles backpack -> drop backpack", flush=True)
                client.send("look in backpack")
                client.expect("a 1000 frequent flier miles")
                client.send("load char 22801")
                client.expect("claim scavenger", timeout=10)
                client.send("setattr scavenger int 103")
                client.expect("OK.", timeout=10)
                print("player: load char 22801; setattr scavenger int 103 -> real NPC spawned", flush=True)
                deadline = time.monotonic() + 90
                moved = False
                while time.monotonic() < deadline and process.poll() is None:
                    if expect_abort:
                        time.sleep(.2)
                        continue
                    client.pending.clear()
                    client.send("look in backpack")
                    response = client.expect_any(("a 1000 frequent flier miles", "Nothing.", "You do not see"),
                                                 timeout=3)[0]
                    if response != "a 1000 frequent flier miles":
                        moved = True
                        break
                    time.sleep(.5)
                logs = journey.runtime_logs(game)
                if expect_abort:
                    assert process.poll() == -signal.SIGABRT, (process.poll(), output_path.read_text(errors="replace")[-2000:])
                    assert "GET_PID called on NPC" in logs, logs[-3000:]
                    print("baseline: SIGABRT; GET_PID called on NPC", flush=True)
                else:
                    assert process.poll() is None, output_path.read_text(errors="replace")[-3000:]
                    assert moved, "NPC did not move the nested item"
                    client.pending.clear()
                    client.send("stat mob scavenger")
                    stat = client.expect("[Return to continue", timeout=10)
                    assert (re.search(r"Carried Items:\s*1\b", stat) or
                            re.search(r"Equipped Items:\s*1\b", stat)), stat
                    client.send("")
                    stat_page_two = client.expect("Pos: standing >", timeout=10)
                    assert "SCAVENGER ISNPC" in stat_page_two, stat_page_two
                    client.pending.clear()
                    client.send("stat obj miles")
                    object_stat = client.expect("Pos: standing >", timeout=10)
                    assert ("Location:" in object_stat and
                            ("equipped by claim scavenger" in object_stat or
                             "carried by claim scavenger" in object_stat)), object_stat
                    client.send("look")
                    room = client.expect("Pos: standing >", timeout=10)
                    assert "backpack lies here" in room and "frequent flier miles" not in room, room
                    print("fixed: NPC carries item; container empty; server alive", flush=True)
                    prompt = "Pos: standing >"

                    def command(line: str, receipt: str) -> str:
                        client.send(line)
                        return client.expect(receipt, timeout=20) + client.expect(prompt, timeout=20)

                    command("goto 22802", "The Scavenger Floor")
                    command("load char 22801", "claim scavenger")
                    command("setattr scavenger int 103", "OK.")
                    floor_start = len(client.transcript)
                    for vnum, keyword, description, equipped in (
                        (22802, "scavengertunic", "a scavenger test tunic", True),
                        (22803, "scavengertoken", "a scavenger test token", False),
                    ):
                        command(f"load obj {vnum}", description)
                        command(f"drop {keyword}", f"You drop {description}.")
                        pickup = f"A claim scavenger gets {description}."
                        client.expect(pickup, timeout=90)
                        if equipped:
                            client.expect(f"A claim scavenger shrugs into {description}.", timeout=10)
                        location = "equipped by" if equipped else "carried by"
                        stat = command(f"stat obj {keyword}", "Location:")
                        assert f"{location} claim scavenger" in stat, stat
                        print(f"floor: {pickup} -> {location} claim scavenger", flush=True)
                    observed = client.transcript[floor_start:].decode(errors="replace")
                    for description in ("a scavenger test tunic", "a scavenger test token"):
                        pickup = f"A claim scavenger gets {description}."
                        assert observed.count(pickup) == 1, observed
                    wear = "A claim scavenger shrugs into a scavenger test tunic."
                    assert observed.count(wear) == 1, observed
                    assert observed.index("A claim scavenger gets a scavenger test tunic.") < observed.index(wear), observed
                    token_lines = [line for line in observed.splitlines()
                                   if line.startswith("A claim scavenger") and "scavenger test token" in line]
                    assert token_lines == ["A claim scavenger gets a scavenger test token."], observed
                    assert process.poll() is None, output_path.read_text(errors="replace")[-3000:]
                    print("floor: exactly one pickup per object; pickup precedes real wear; token stays in inventory", flush=True)
            except Exception:
                print("server tail:", output_path.read_text(errors="replace")[-2000:], flush=True)
                print("logs tail:", journey.runtime_logs(game)[-2000:], flush=True)
                if client:
                    print("game tail:", client.transcript.decode(errors="replace")[-2000:], flush=True)
                raise
            finally:
                stop()


if __name__ == "__main__":
    import sys
    run(Path(sys.argv[1]).resolve(), "--expect-abort" in sys.argv[2:])
