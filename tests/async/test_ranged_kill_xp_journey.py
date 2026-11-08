#!/usr/bin/env python3
"""Real fire -> NPC death -> damage/kill XP, solo and grouped across rooms (#764)."""

import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile

import test_starter_arrow_journey as arrows

journey = arrows.journey
ROOT = journey.ROOT
MATE = "Torven"


def build_inspector(root):
    source, binary = root / "xp.cpp", root / "xp"
    source.write_text(r'''
#include "flatfile/flatfile_player_snapshot_file.h"
#include <cassert>
#include <cstdio>
#include <cstdlib>
int main(int argc, char **argv) {
    assert(argc == 3);
    player_snapshot snapshot; std::string error;
    assert(flatfile_player_snapshot_read(argv[1], std::atoi(argv[2]), &snapshot, &error) ==
           flatfile_player_load_result::ok);
    for (const auto &field : snapshot.status_integers)
        if (field.field == player_status_field::experience) {
            printf("%lld\n", static_cast<long long>(field.signed_value));
            return 0;
        }
    return 1;
}
''')
    subprocess.run(["g++", "-std=c++20", "-Isrc", str(source),
                    "src/flatfile/flatfile_player_snapshot_file.c",
                    "src/flatfile/flatfile_store.c", "src/player/player_snapshot_codec.c",
                    "-lcrypto", "-o", str(binary)], cwd=ROOT, check=True)
    return binary


def configure(runtime):
    arrows.configure(runtime, "ranger", None)
    objects = runtime / "areas_mini/mini.obj"
    text = objects.read_text()
    journey.require("0 1 4 1 0 0 0 0" in text, "starter arrow fixture changed")
    objects.write_text(text.replace("0 1 4 1 0 0 0 0", "0 100 1 1 0 0 0 0"))
    # Identical NPCs in lit rooms. NO_MOB prevents wandering between test rooms;
    # sentinel NPCs cannot be used because conversion gives them ranged cover.
    world = runtime / "areas_mini/mini.wld"
    world.write_text(world.read_text().replace("1 4194304 0", "1 4194308 0"))
    # A landed arrow kills outright so retaliation cannot supply the killing blow.
    mobile = runtime / "areas_mini/mini.mob"
    text = mobile.read_text()
    targets = ""
    for vnum, name in enumerate(("Solo", "Remote", "Grouped", "Distant", "Split"), 22801):
        targets += (f"#{vnum}\n{name.lower()} quarry~\nthe {name} quarry~\n"
                    f"The {name} quarry waits here.\n~\n~\n"
                    "8 0 0 0 0 0 0 0 S\nPH 0 0 -1\n"
                    "1 0 100 1d1+1 1d1+1\n0.0.0.0 0\n8 8 0\n")
    mobile.write_text(text.replace("$~", targets + "$~"))
    zone = runtime / "areas_mini/mini.zon"
    resets = "".join(f"M 0 {vnum} 1 {room} 100 0 0 0\n" for vnum, room in
                     ((22801, 22800), (22802, 22801), (22803, 22800),
                      (22804, 22801), (22805, 22801)))
    zone.write_text(zone.read_text().replace("\nS\n", "\n" + resets + "S\n"))
    properties = runtime / "lib/duris.properties"
    # Hold level constant while comparing equal NPCs and one-arrow volleys.
    properties.write_text(properties.read_text() +
                          "\nexp.maxExpLevel=1.000\narchery.speedPerShot=1000.000\n")


def run(binary, inspector):
    with tempfile.TemporaryDirectory(prefix="ranged-xp-", dir=ROOT / "bin/tests") as temporary:
        root = Path(temporary)
        runtime, state = root / "runtime", root / "state"
        runtime.mkdir(); state.mkdir(mode=0o700)
        configure(runtime)
        journey.generate_certificate(runtime)
        (runtime / "logs/log").mkdir(parents=True)
        (runtime / "journals/critical").mkdir(parents=True, mode=0o700)
        plain, tls, ws = journey.available_ports()
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "ENVIRONMENT": "local",
               "PERSISTENCE_MODE": "flatfile-primary", "FLATFILE_STATE_DIR": str(state),
               "CRITICAL_COMMAND_JOURNAL_DIR": str(runtime / "journals/critical"),
               "LISTEN_ADDRESS": "127.0.0.1", "DURIS_TLS_PORT": str(tls),
               "DURIS_WEBSOCKET_LISTEN_ADDRESS": "127.0.0.1", "DURIS_WEBSOCKET_PORT": str(ws),
               "REDIS": "FALSE", "CHAOS_MUD": "FALSE"}
        if "LD_LIBRARY_PATH" in os.environ:
            env["LD_LIBRARY_PATH"] = os.environ["LD_LIBRARY_PATH"]
        log = runtime / "server.out"
        clients = []
        with log.open("w") as output:
            process = subprocess.Popen([str(binary), "--minimal", "-s", "-d", str(runtime), str(plain)],
                                       cwd=runtime, env=env, stdout=output, stderr=subprocess.STDOUT)
            try:
                shooter = journey.MudClient(plain)
                clients.append(shooter)
                journey.create_character(shooter, class_name="ranger")
                shooter.expect(arrows.PROMPT)
                arrows.command(shooter, "remove all", ("You stop using ", "You are quite naked"))
                arrows.command(shooter, "wield bow", "You wield ")
                arrows.command(shooter, "put all.arrow quiver", "You put ")
                arrows.command(shooter, "wear quiver", "You strap ")
                arrows.command(shooter, "toggle exp", "Experience Display is now ON")

                def balance(client, name, pid):
                    arrows.command(client, "save", f"Saving {name}.")
                    return int(subprocess.check_output([str(inspector), str(state), str(pid)], text=True))

                def kill(name, adjacent, mate=None, mate_present=False):
                    before = balance(shooter, journey.CHARACTER, 1)
                    mate_before = balance(mate, MATE, 2) if mate else 0
                    start = len(shooter.transcript)
                    for _ in range(20):
                        shot = arrows.command(shooter, f"fire {name}" + (" north" if adjacent else ""),
                                              ("You fire ", "Your "))
                        if "killing" in shot:
                            break
                        journey.require("and miss!" in shot, f"landed arrow did not kill: {shot}")
                        if adjacent:
                            arrows.command(shooter, "north", "The Arrow Landing Room")
                        arrows.command(shooter, "gather", "You gathered ")
                        if adjacent:
                            arrows.command(shooter, "south", "The Regression Arena")
                    else:
                        raise AssertionError("no landed arrow in twenty attempts")
                    transcript = shooter.transcript[start:].decode(errors="replace")
                    awards = re.findall(r"EXP:\s+(\d+)", transcript)
                    journey.require(len(awards) == 1, f"expected one kill award: {transcript}")
                    kill_xp = int(awards[0])
                    total = balance(shooter, journey.CHARACTER, 1) - before
                    journey.require(total > kill_xp > 0, f"missing damage or kill XP: {transcript}")
                    mate_xp = balance(mate, MATE, 2) - mate_before if mate else 0
                    journey.require((mate_xp > 0) == mate_present, f"wrong group recipient: {mate_xp}")
                    result = {"command": f"fire {name}" + (" north" if adjacent else ""),
                              "damage_xp": total - kill_xp, "kill_xp": kill_xp, "groupmate_xp": mate_xp}
                    print(json.dumps(result), flush=True)
                    return result

                solo = kill("solo", False)
                remote = kill("remote", True)
                journey.require(solo["kill_xp"] == remote["kill_xp"], "room distance changed solo kill XP")
                mate = journey.MudClient(plain, source_host="127.0.0.2")
                clients.append(mate)
                journey.create_character(mate, account="Mateacct", character=MATE,
                                         email="mate@example.invalid")
                mate.expect(arrows.PROMPT)
                arrows.command(mate, "consent " + journey.CHARACTER, "consent")
                arrows.command(shooter, "group " + MATE, "is now a member of your group.")
                grouped = kill("grouped", False, mate, True)
                distant = kill("distant", True, mate, True)
                journey.require(grouped["kill_xp"] == distant["kill_xp"], "distance changed group kill XP")
                journey.require(grouped["groupmate_xp"] == distant["groupmate_xp"], "distance changed group share")
                arrows.command(mate, "north", "The Arrow Landing Room")
                split = kill("split", True, mate, False)
                journey.require(split["kill_xp"] == solo["kill_xp"], "absent groupmate reduced killer share")
                arrows.command(shooter, "north", "The Arrow Landing Room")
                arrows.command(shooter, "look", "corpse of the Split quarry")
                print("PASS real ranged NPC deaths: damage XP, kill XP and killer-room group eligibility", flush=True)
            except Exception:
                print(log.read_text(errors="replace")[-6000:])
                print(journey.runtime_logs(runtime))
                for client in clients:
                    print(client.transcript.decode(errors="replace")[-6000:])
                raise
            finally:
                for client in clients:
                    client.close()
                process.send_signal(signal.SIGTERM)
                try:
                    process.wait(timeout=40)
                except subprocess.TimeoutExpired:
                    process.kill(); process.wait(timeout=10)


if __name__ == "__main__":
    build_root = ROOT / "bin/tests"
    build_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ranged-xp-build-", dir=build_root) as temporary:
        build = Path(temporary)
        binary = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else journey.build_flatfile_server(build)
        run(binary, build_inspector(build))
