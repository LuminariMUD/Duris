#!/usr/bin/env python3
"""Fresh Ranger/Rogue grants -> real fire, event pulses and gather, in private state."""

import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import time

import test_flatfile_combat_journey as journey
from test_flatfile_newbie_regrant_journey import install_legacy_objects
from test_flatfile_chaos_new_character_kit import install_chaos_objects

ROOT = journey.ROOT
PROMPT = "Pos: standing >"


def command(client, text, responses):
    """Keep unsolicited output in the transcript; return this response and its prompt."""
    client.send(text)
    if isinstance(responses, str):
        responses = (responses,)
    matched, _ = client.expect_any(responses, timeout=20)
    return matched + client.expect(PROMPT, timeout=20)


def synchronization_control():
    """A buffered or arriving notification prompt cannot finish a new command."""
    import socket
    import threading

    for buffered in (False, True):
        connection, server = socket.socketpair()
        client = journey.MudClient.__new__(journey.MudClient)
        client.socket = connection
        connection.settimeout(0.25)
        client.pending = bytearray(("old " + PROMPT).encode() if buffered else b"")
        client.transcript = bytearray(client.pending)
        client.raw_transcript = bytearray()

        def respond():
            with server:
                journey.require(server.recv(1024) == b"fire Torven\n", "wrong fixture command")
                server.sendall(("Torven arrives.\n" + PROMPT + "\nYou fire ").encode())
                server.sendall(("an arrow at Torven and miss!\n" + PROMPT).encode())

        worker = threading.Thread(target=respond)
        worker.start()
        try:
            output = command(client, "fire Torven", "You fire ")
            journey.require("and miss!" in output and "Torven arrives" not in output,
                            f"command accepted a notification prompt: {output}")
            journey.require(b"Torven arrives" in client.transcript, "notification was lost")
        finally:
            client.close()
            worker.join(timeout=5)
    print("command synchronization: buffered and arriving prompts passed", flush=True)


def build_inspector(root):
    source, binary = root / "inspect.cpp", root / "inspect"
    source.write_text(r'''
#include "flatfile/flatfile_player_snapshot_file.h"
#include <cassert>
#include <cstdio>
int main(int argc, char **argv) {
    assert(argc == 2);
    player_snapshot snapshot; std::string error;
    assert(flatfile_player_snapshot_read(argv[1], 1, &snapshot, &error) ==
           flatfile_player_load_result::ok);
    for (const auto &item : snapshot.items)
        if ((item.vnum >= 1116 && item.vnum <= 1118) ||
            item.vnum == 25753 || item.vnum == 25757 || item.vnum == 25758)
            printf("%llu %d %d %d %d %d %u %d %d\n",
                   static_cast<unsigned long long>(item.object_uid), item.vnum,
                   item.condition, item.weight, item.values[3], item.equipment_slot,
                   item.extra_flags, item.parent_index, item.cost);
}
''')
    subprocess.run(["g++", "-std=c++20", "-Isrc", str(source),
                    "src/flatfile/flatfile_player_snapshot_file.c",
                    "src/flatfile/flatfile_store.c", "src/player/player_snapshot_codec.c",
                    "-lcrypto", "-o", str(binary)], cwd=ROOT, check=True)
    return binary


def saved(client, inspector, state):
    command(client, "save", f"Save complete for {journey.CHARACTER}.")
    return [list(map(int, line.split())) for line in subprocess.check_output(
        [str(inspector), str(state)], text=True).splitlines()]


def configure(runtime, class_name, profile):
    journey.make_fixture(runtime)
    install_legacy_objects(runtime)
    if profile:
        install_chaos_objects(runtime, class_name.title(), profile)
        install_chaos_objects(runtime, "Warrior", profile)
    world = runtime / "areas_mini/mini.wld"
    text = world.read_text()
    # MAGIC_LIGHT makes visibility stable. A second synthetic player supplies
    # a target without NPC sentinel cover, wandering or retaliation.
    text = text.replace("#22800\nThe Regression Arena~\n"
                        "This quiet stone arena exists to prove the complete combat journey.\n~\n1 0 0\nS\n",
                        "#22800\nThe Regression Arena~\nA dry archery range.\n~\n"
                        "1 4194304 0\nD0\n~\n~\n0 0 22801\nS\n"
                        "#22801\nThe Arrow Landing Room~\nA dry landing room.\n~\n"
                        "1 4194304 0\nD2\n~\n~\n0 0 22800\nS\n")
    journey.require("#22801\n" in text, "archery room fixture did not install")
    # Missing full-world hometowns fall back to room 11 in mini mode;
    # give those races a walkable route to the range.
    text = re.sub(r"(?ms)(^#11\n.*?)(^S\n)",
                  r"\1D1\n~\n~\n0 0 22800\n\2", text, count=1)
    world.write_text(text)
    zone = runtime / "areas_mini/mini.zon"
    text = re.sub(r"^[MGE] .*\n", "", zone.read_text(), flags=re.M)
    zone.write_text(text)
    properties = runtime / "lib/duris.properties"
    properties.write_text(properties.read_text() + "\nhitpoints.class.Warrior=5000.000\n")


def run(binary, inspector, race, class_name="ranger", profile=None):
    quiver_vnum, arrow_vnum = (25757, 25758) if profile else (1116, 1117)
    with tempfile.TemporaryDirectory(prefix="starter-arrow-", dir=ROOT / "bin/tests") as temp:
        root = Path(temp)
        runtime, state = root / "runtime", root / "state"
        runtime.mkdir(); state.mkdir(mode=0o700)
        (runtime / "logs/log").mkdir(parents=True)
        configure(runtime, class_name, profile)
        journey.generate_certificate(runtime)
        (runtime / "journals/critical").mkdir(parents=True, mode=0o700)
        plain, tls, ws = journey.available_ports()
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "ENVIRONMENT": "local",
               "PERSISTENCE_MODE": "flatfile-primary", "FLATFILE_STATE_DIR": str(state),
               "CRITICAL_COMMAND_JOURNAL_DIR": str(runtime / "journals/critical"),
               "LISTEN_ADDRESS": "127.0.0.1", "DURIS_TLS_PORT": str(tls),
               "DURIS_WEBSOCKET_LISTEN_ADDRESS": "127.0.0.1", "DURIS_WEBSOCKET_PORT": str(ws),
               "REDIS": "FALSE", "CHAOS_MUD": "TRUE" if profile else "FALSE",
               "CHAOS_EQ_PROFILE": profile or "standard", "CHAOS_STARTER_BONUSES": "FALSE",
               # These historical races are deliberately available only in this fixture.
               "CREATION_ALL_RACES": "TRUE", "CREATION_ALL_CLASSES": "TRUE"}
        if "LD_LIBRARY_PATH" in os.environ:
            env["LD_LIBRARY_PATH"] = os.environ["LD_LIBRARY_PATH"]
        log = runtime / "server.out"
        with log.open("w") as output:
            process = subprocess.Popen([str(binary), "--minimal", "-s", "-d",
                                        str(runtime), str(plain)], cwd=runtime, env=env,
                                       stdout=output, stderr=subprocess.STDOUT)
            client = target = None
            try:
                client = journey.MudClient(plain)
                journey.create_character(client, expected_room=None, race_name=race, class_name=class_name,
                                         alignment="n" if class_name == "rogue" else "g")
                client.expect(PROMPT)
                location = command(client, "look", ("The Regression Arena", "Cage of Smoke"))
                if "Cage of Smoke" in location:
                    location = command(client, "east", "The Regression Arena")
                journey.require("The Regression Arena" in location, "character did not reach the archery range")
                initial = saved(client, inspector, state)
                arrows = [item for item in initial if item[1] == arrow_vnum]
                journey.require(len(arrows) == 10, f"fresh {race} {class_name} profile={profile} has no ten-arrow kit: {initial}")
                journey.require(all(item[2] == 100 and not item[6] & (1 << 19)
                                    and item[8] == 1 for item in arrows), "bad fresh missile flags/cost/condition")
                if profile:
                    # Store spare Chaos gear first so ordinary carry limits leave
                    # enough room to retrieve and load the archery package.
                    command(client, "put all bag", "You put ")
                    command(client, "get quiver bag", "You get ")
                    command(client, "open quiver", "Ok.")
                    for _ in range(10):
                        command(client, "get arrow bag", "You get ")
                        command(client, "put arrow quiver", "Ok.")
                    command(client, "get bow bag", "You get ")
                command(client, "remove all", ("You stop using ", "You are quite naked"))
                command(client, "wield bow", "You wield ")
                if not profile:
                    command(client, "put all.arrow quiver", "You put ")
                command(client, "wear quiver", "You strap ")
                target = journey.MudClient(plain, source_host="127.0.0.2")
                journey.create_character(target, expected_room=None, account="Targetacct", character="Torven",
                                         email="target@example.invalid", race_name=race if profile else "human",
                                         alignment="n" if class_name == "rogue" else "g")
                target.expect(PROMPT)
                target_location = command(target, "look", ("The Regression Arena", "Cage of Smoke"))
                if "Cage of Smoke" in target_location:
                    command(target, "east", "The Regression Arena")
                command(target, "introduce", ("Introduce yourself to whom?", "Pardon?"))
                result = {"race": race, "class": class_name, "profile": profile, "fresh_arrow_uids": [item[0] for item in arrows], "cases": []}
                for adjacent in (False, True):
                    if adjacent:
                        command(target, "north", "The Arrow Landing Room")
                    # Normal kits must demonstrate miss recovery. Chaos also
                    # checks real fire/gather, accepting a successful shot.
                    for attempt in range(1 if profile else 8):
                        before = saved(client, inspector, state)
                        before_arrows = {item[0]: item for item in before if item[1] == arrow_vnum}
                        quiver_before = next(item for item in before if item[1] == quiver_vnum)
                        firing_start = len(client.transcript)
                        command(client, "fire Torven north" if adjacent else "fire Torven",
                                ("You fire ", "hit strikes "))
                        # A high-level volley can mix hits and misses before the
                        # prompt. Count all shot messages, including the first.
                        shot = client.transcript[firing_start:].decode(errors="replace")
                        missed = "and miss!" in shot
                        journey.require("fire" in shot.lower() or "hit strikes" in shot,
                                        f"fire did not execute:\n{shot}")
                        time.sleep(1.25)  # five real server pulses, beyond zero-delay decay
                        if adjacent:
                            command(client, "north", "The Arrow Landing Room")
                        floor = command(client, "look", "The Arrow Landing Room" if adjacent
                                        else "The Regression Arena")
                        gather = command(client, "gather", ("You gathered ", "There are no arrows"))
                        after = saved(client, inspector, state)
                        after_arrows = {item[0]: item for item in after if item[1] == arrow_vnum}
                        journey.require(set(after_arrows) <= set(before_arrows), "fire/gather changed missile identities")
                        hits = shot.count("hit strikes ")
                        journey.require(len(before_arrows) - len(after_arrows) == hits,
                                        f"missed missile lost across event/gather boundary:\n{shot}\n{floor}\n{gather}")
                        journey.require(all(item[2] == 100 for item in after_arrows.values()),
                                        "a missed missile lost condition")
                        quiver_after = next(item for item in after if item[1] == quiver_vnum)
                        journey.require(quiver_after[4] == len(after_arrows), "quiver count disagrees with contents")
                        journey.require(quiver_after[3] == quiver_before[3] -
                                        sum(before_arrows[uid][3] for uid in before_arrows.keys() - after_arrows.keys()),
                                        "quiver weight changed beyond hit consumption")
                        if adjacent:
                            command(client, "south", "The Regression Arena")
                        if missed:
                            journey.require("arrow" in floor, "missed missile absent from landing room")
                            journey.require("gather" in gather.lower(), "gather did not report recovery")
                        if missed or profile:
                            result["cases"].append({"adjacent": adjacent, "attempts": attempt + 1,
                                                    "misses": shot.count("and miss!"), "hits": hits,
                                                    "remaining_uids": sorted(after_arrows),
                                                    "quiver_count": quiver_after[4],
                                                    "quiver_weight": quiver_after[3]})
                            break
                    else:
                        raise AssertionError("no missed shot observed in eight attempts")
                # Save, stop, restart and reconnect: no automatic duplicate grant,
                # and loaded arrows retain their IDs, condition and containment.
                before_restart = saved(client, inspector, state)
                client.send("quit")
                client.expect("ACCOUNT MENU", timeout=40)
                client.close(); client = None
                target.close(); target = None
                process.send_signal(signal.SIGTERM)
                process.wait(timeout=40)
                journey.require(process.returncode == 0, "first server shutdown failed")
                process = subprocess.Popen([str(binary), "--minimal", "-s", "-d",
                                            str(runtime), str(plain)], cwd=runtime, env=env,
                                           stdout=output, stderr=subprocess.STDOUT)
                client = journey.reconnect_character(plain, expected_room=None)
                client.expect(PROMPT)
                journey.require(saved(client, inspector, state) == before_restart,
                                "restart/relogin changed the archery kit")
                result["restart_relogin"] = "passed"
                print(json.dumps(result), flush=True)
                return result
            except Exception:
                print(log.read_text(errors="replace")[-6000:])
                print(journey.runtime_logs(runtime))
                if client:
                    print(client.transcript.decode(errors="replace")[-6000:])
                raise
            finally:
                for connection in (client, target):
                    if connection:
                        connection.close()
                process.send_signal(signal.SIGTERM)
                try:
                    process.wait(timeout=40)
                except subprocess.TimeoutExpired:
                    process.kill(); process.wait(timeout=10)


if __name__ == "__main__":
    synchronization_control()
    build_root = ROOT / "bin/tests"
    build_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="starter-arrow-build-", dir=build_root) as temp:
        build = Path(temp)
        executable = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else journey.build_flatfile_server(build)
        inspector = build_inspector(build)
        report = {"binary_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
                  "cases": [run(executable, inspector, race, role, profile) for race, role, profile in (
                      ("half-elf", "ranger", None), ("wood-elf", "ranger", None),
                      ("human", "ranger", None), ("human", "rogue", None),
                      ("centaur", "ranger", "standard"), ("drider", "rogue", "enhanceable"))]}
        path = ROOT / "bin/qualification/issue429/gameplay-report.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2) + "\n")
