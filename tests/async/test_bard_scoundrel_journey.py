#!/usr/bin/env python3
"""Play the level-56 Scoundrel songs through real commands on disposable MariaDB."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import signal
import subprocess
import tempfile
import time

import test_mariadb_combat_journey as journey
from test_minor_creation_instrument_journey import configure, spell_id
from test_flight_network_journey import command

ROOT = journey.ROOT
BARD, FOLLOWER, PEER = "Piper", "Footstep", "Companion"
NAMES = (journey.CHARACTER, BARD, FOLLOWER, PEER)
REPORT = ROOT / "bin/qualification/issue707/scoundrel-gameplay.json"


def run(binary):
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    report = {"binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest()}
    with tempfile.TemporaryDirectory(prefix="bard-scoundrel-", dir=ROOT / "bin/tests") as temporary, \
            journey.mariadb_authority() as (authority, sql):
        runtime = Path(temporary)
        configure(runtime)
        (runtime / "journals/critical").mkdir(parents=True, mode=0o700)
        # A second room makes separation observable without depending on area exits.
        world = runtime / "areas_mini/mini.wld"
        body = world.read_text()
        at = body.index("#22800\n")
        arena = body[at:body.index("$~", at)]
        assert "1 0 0\nS\n" in arena, arena
        arena = arena.replace("1 0 0\nS\n", "1 0 0\nD0\n~\n~\n0 0 22801\nS\n")
        body = body[:at] + arena + "#22801\nQuiet Alcove~\nA quiet alcove.~\n1 0 0\nD2\n~\n~\n0 0 22800\nS\n$~\n"
        world.write_text(body)
        zone = runtime / "areas_mini/mini.zon"
        zone.write_text(re.sub(r"^[MGEO] .*\n", "", zone.read_text(), flags=re.M))
        port, tls, websocket = journey.available_ports()
        env = {**authority, "CRITICAL_COMMAND_JOURNAL_DIR": str(runtime / "journals/critical"),
               "DURIS_TLS_PORT": str(tls), "DURIS_WEBSOCKET_PORT": str(websocket)}
        output_path = runtime / "server.out"
        process = None
        clients = []
        with output_path.open("a") as output:
            def boot():
                start = output_path.stat().st_size
                proc = subprocess.Popen([str(binary), "--minimal", "-s", "-d", str(runtime), str(port)],
                                        cwd=runtime, env=env, stdout=output, stderr=subprocess.STDOUT)
                deadline = time.monotonic() + 120
                while "Entering game loop." not in output_path.read_text(errors="replace")[start:]:
                    assert proc.poll() is None and time.monotonic() < deadline, "boot failed"
                    time.sleep(.1)
                return proc

            def stop():
                for client in clients:
                    client.close()
                clients.clear()
                process.send_signal(signal.SIGTERM)
                process.wait(timeout=60)
                assert process.returncode == 0

            def login(name):
                client = journey.reconnect_character(port, account=name, character=name)
                clients.append(client)
                client.expect_any(("Pos: standing >", "<>"))
                command(client, "toggle paging no")
                return client

            try:
                process = boot()
                for name in NAMES:
                    print("Creating disposable character: " + name, flush=True)
                    client = journey.MudClient(port)
                    clients.append(client)
                    journey.create_character(client, account=name, character=name,
                                             email=name.lower() + "@example.invalid")
                    command(client, "save")
                    client.send("quit")
                    client.expect("ACCOUNT MENU", timeout=30)
                stop()
                journey.make_overlord(sql, journey.CHARACTER)
                for name in (BARD, FOLLOWER, PEER):
                    sql(f"UPDATE player_data SET m_class={1 << 15 if name == BARD else 1},"
                        f"secondary_class=0,spec={2 if name == BARD else 0},level=56,highest_level=56,"
                        f"played_time=200000,base_hit=10000,hit_diff=0,screen_length=100,last_room=22800 "
                        f"WHERE name='{name}'")
                pid = sql(f"SELECT pid FROM player_data WHERE name='{BARD}'")
                for key in ("SONG_SHADOW_PIPER", "SONG_HEROISM", "SONG_HARMONY",
                            "INSTRUMENT_FLUTE", "INSTRUMENT_DRUMS"):
                    sql(f"REPLACE INTO player_skills(pid,skill_id,learned,taught) "
                        f"VALUES({pid},{spell_id(key)},100,100)")
                process = boot()
                staff = login(journey.CHARACTER)
                command(staff, "vis 0")
                bard, follower, peer = (login(name) for name in (BARD, FOLLOWER, PEER))
                for vnum, keyword in ((1246, "flute"), (1243, "drum")):
                    command(staff, f"load obj {vnum}")
                    command(staff, f"give {keyword} {BARD}")
                for name, client in ((FOLLOWER, follower), (PEER, peer)):
                    command(client, "consent " + BARD)
                    assert "You now follow" in command(client, "follow " + BARD)
                    assert "member of your group" in command(bard, "group " + name)
                command(peer, "follow self") # Still grouped; intentionally not following.
                command(bard, "hold flute")
                assert "You start playing" in command(bard, "play shadow piper")

                def snapshot(name):
                    text = command(staff, "stat char " + name)
                    flags = re.search(r"Affected by \(1\):\s*(\d+)", text)
                    return bool(flags and int(flags[1]) & (1 << 19)), text

                def grant():
                    deadline = time.monotonic() + 20
                    while True:
                        sneak, text = snapshot(FOLLOWER)
                        if sneak:
                            assert "song of the shadow piper" in text, text
                            return text
                        assert time.monotonic() < deadline, text
                        time.sleep(.1)

                grant()
                assert not snapshot(BARD)[0] and not snapshot(PEER)[0]
                assert "Quiet Alcove" in command(bard, "north")
                assert snapshot(FOLLOWER)[0], "ordinary group following lost Sneak"
                assert "The Regression Arena" in command(bard, "south")
                assert snapshot(FOLLOWER)[0], "returning group walk lost Sneak"
                command(follower, "follow self")
                assert not snapshot(FOLLOWER)[0], "unfollowing retained Sneak"
                command(follower, "follow " + BARD)
                grant()
                command(bard, "group " + FOLLOWER)
                assert not snapshot(FOLLOWER)[0], "leaving the group retained Sneak"
                command(bard, "group " + FOLLOWER)
                grant()
                assert "Quiet Alcove" in command(follower, "north")
                assert not snapshot(FOLLOWER)[0], "walking apart retained Sneak"
                assert "The Regression Arena" in command(follower, "south")
                grant()
                command(staff, "at 22801 transfer " + FOLLOWER)
                sneak, text = snapshot(FOLLOWER)
                assert "In room: [22801]" in text and not sneak, text
                command(staff, "transfer " + FOLLOWER)
                grant()
                command(staff, "at 22801 transfer " + BARD)
                assert not snapshot(FOLLOWER)[0], "singer relocation retained follower Sneak"
                command(staff, "transfer " + BARD)
                grant()
                command(staff, "load mob 11")
                command(follower, "kill raoul")
                assert "song of the shadow piper" not in snapshot(FOLLOWER)[1], "combat retained the song affect"
                command(staff, "peace")
                grant()
                command(bard, "play harmony")
                assert not snapshot(FOLLOWER)[0], "changing songs retained Sneak"
                command(bard, "play shadow piper")
                grant()
                command(bard, "play")
                assert not snapshot(FOLLOWER)[0], "stopping the song retained Sneak"
                time.sleep(2.2) # The existing stop-song rest.
                command(bard, "remove flute")
                command(bard, "hold drum")
                assert "You start playing" in command(bard, "play heroism")
                deadline = time.monotonic() + 20
                while True:
                    text = snapshot(FOLLOWER)[1]
                    pulses = re.findall(r"by\s+-2\s+for[^\n]*from 'song of heroism'", text)
                    if len(pulses) == 2:
                        break
                    assert time.monotonic() < deadline, text
                    time.sleep(.1)
                report["shadow_piper"] = "follower-only; unfollow/group/room/combat/change/stop cleanup"
                report["heroism"] = "two -2 listener pulse affects from a level-56 Scoundrel"
                print("PASS: real Shadow Piper eligibility and all cleanup paths; Heroism listener pulses", flush=True)
                stop()
                process = None
            except BaseException:
                print(output_path.read_text(errors="replace")[-6000:])
                for client in clients:
                    print(bytes(client.transcript[-5000:]).decode(errors="replace"))
                raise
            finally:
                if process and process.poll() is None:
                    stop()
    REPORT.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", type=Path, required=True)
    run(parser.parse_args().server.resolve())
