#!/usr/bin/env python3
"""Isolated real PvP, shared maintenance clock, banked XP and saved restart.

Reuses the maintained full-world setup, account/client and authority helpers.
Only the offline fixture seeds a round near its real deadline; no server clock
override, debug command, production credential or existing player is used.
"""
import argparse
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import tempfile
import time

import test_flatfile_combat_journey as journey
from test_divine_boon_zone_journey import SEED, experience_site, plain_text
from test_flight_network_journey import authority, command
from run_world_quest_dual_backend import setup_run_root

ROOT = journey.ROOT
GOD, PLAYER, VICTIM = "Capwarden", "Capfighter", "Capvictim"
ACCOUNTS = {GOD: "Capstaff", PLAYER: "Capmortal", VICTIM: "Capenemy"}


def build_fixture(binary):
    subprocess.run([
        "g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-Isrc", "-I/usr/include/mysql",
        "tests/async/frag_cap_journey_fixture.cpp", "src/combat/frag_cap.c", "src/combat/frag_cap_repository.c",
        "src/flatfile/flatfile_identity_repository.c", "src/flatfile/flatfile_player_snapshot_file.c",
        "src/player/player_snapshot_codec.c", "src/flatfile/flatfile_authority_transaction.c",
        "src/flatfile/flatfile_store.c", "src/persistence/critical_command.c",
        "-lcrypto", "-lmysqlclient", "-pthread", "-o", str(binary),
    ], cwd=ROOT, check=True)


def run(backend, binary):
    output_root = ROOT / "bin/tests"
    output_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="frag-cap-journey-", dir=output_root) as temporary:
        runtime = Path(temporary)
        _, critical, output_path = setup_run_root(runtime)
        (runtime / "help").symlink_to(ROOT / "help", target_is_directory=True)
        (runtime / "bin/server").mkdir(parents=True)
        executable = runtime / "bin/server/dms"
        shutil.copy2(binary, executable)
        with (runtime / "lib/misc/event_names").open("w") as names:
            subprocess.run([str(ROOT / "scripts/event_names.sh"), str(executable)], stdout=names, check=True)
        helper = runtime / "fixture"
        build_fixture(helper)
        port, tls, websocket = journey.available_ports()
        clients = []
        process = None
        redis = None
        with authority(backend, runtime) as (env, sql), output_path.open("w") as output:
            env.update(CRITICAL_COMMAND_JOURNAL_DIR=str(critical), DURIS_TLS_PORT=str(tls),
                       DURIS_WEBSOCKET_PORT=str(websocket), MAINTENANCE_STATE_FILE=str(runtime / "maintenance.state"))
            redis_socket = runtime / "redis.sock"
            if sql:
                redis = subprocess.Popen(["redis-server", "--port", "0", "--unixsocket", str(redis_socket),
                                          "--save", "", "--appendonly", "no"],
                                         stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
                deadline = time.monotonic() + 10
                while not redis_socket.exists():
                    assert redis.poll() is None and time.monotonic() < deadline
                    time.sleep(0.05)
                env.update(REDIS="TRUE", REDIS_SOCKET=str(redis_socket), REDIS_TLS="FALSE",
                           REDIS_NAMESPACE="duris:local:fragcap")

            def fixture(action, owner=PLAYER, *values):
                return subprocess.check_output([str(helper), backend, str(runtime / "state"), action,
                                                owner, *map(str, values)], env=env, text=True)

            def boot():
                nonlocal process
                offset = output_path.stat().st_size
                process = subprocess.Popen([str(executable), "-d", str(runtime), str(port)],
                                           cwd=runtime, env=env, stdout=output, stderr=subprocess.STDOUT)
                deadline = time.monotonic() + 180
                while b"Entering game loop." not in output_path.read_bytes()[offset:]:
                    assert process.poll() is None and time.monotonic() < deadline, "world failed to boot"
                    time.sleep(0.1)

            def stop():
                nonlocal process
                for client in clients:
                    client.close()
                clients.clear()
                process.send_signal(signal.SIGTERM)
                process.wait(timeout=60)
                assert process.returncode == 0
                process = None

            def connect(name, create=False):
                source = None if name == GOD else "127.0.0.2" if name == PLAYER else "127.0.0.3"
                if create:
                    client = journey.MudClient(port, source_host=source)
                    clients.append(client)
                    journey.create_character(client, expected_room=None, account=ACCOUNTS[name], character=name,
                                             email=name.lower() + "@example.invalid", race_name="o" if name == VICTIM else "h")
                else:
                    client = journey.reconnect_character(port, expected_room=None, account=ACCOUNTS[name],
                                                         character=name, source_host=source)
                    clients.append(client)
                    client.expect("Welcome to Duris", timeout=60)
                    client.expect_any(("Pos: standing >", "<>"), timeout=20)
                command(client, "toggle paging no")
                return client

            def save(client, name):
                client.send("save")
                client.expect("Save complete for " + name + ".", timeout=60)

            try:
                boot()
                for name in (GOD, PLAYER, VICTIM):
                    save(connect(name, create=True), name)
                stop()
                if sql:
                    sql("UPDATE player_data SET level=62,highest_level=62 WHERE name='" + GOD + "'")
                else:
                    journey.make_overlord(runtime / "state", GOD)
                fixture("actor", PLAYER)
                fixture("actor", VICTIM)
                earliest = int(time.time()) + 120
                fixture("seed", PLAYER, earliest)
                boot()
                god, player, victim = (connect(name) for name in (GOD, PLAYER, VICTIM))
                assert re.search(r"Level:\s*31\b", plain_text(command(player, "score")))
                for client in (player,victim):
                    for view in ("fraglist", "fraglist normal"):
                        shown = plain_text(command(client, view))
                        assert "Faction level caps: Good 31 / Evil 31" in shown and "Good 0.05 / Evil 0.10" in shown, shown
                        assert "Result in" in shown and "Evil currently leads" in shown, shown
                if sql:
                    keys = subprocess.check_output(["redis-cli", "-s", str(redis_socket), "--raw", "keys", "*fraglist*"], text=True).splitlines()
                    assert len(keys) == 1, keys
                    cached = subprocess.check_output(["redis-cli", "-s", str(redis_socket), "--raw", "get", keys[0]], text=True)
                    assert cached.startswith("FRAGLIST2\n") and "earned" not in cached and "Faction level caps" not in cached

                room, mob, keyword = experience_site(SEED[0]["number"])
                command(god, f"goto {room}")
                command(god, "purge")
                command(god, "transfer " + PLAYER)
                command(god, "transfer " + VICTIM)
                for attribute in ("str", "dex"):
                    command(god, f"setattr {PLAYER} {attribute} 250")
                for attribute in ("dex", "agi"):
                    command(god, f"setattr {VICTIM} {attribute} 1")
                hp = re.search(r"Hit points:\s*(\d+)\((\d+)\)", plain_text(command(victim, "score")))
                assert hp
                command(god, f"setattr {VICTIM} hit " + str(sum(map(int, hp.groups())) - 1))
                assert time.time() < earliest - 10, "setup consumed the seeded acceleration window"
                deadline = time.monotonic() + 40
                while b"Your wounds claim you at last" not in victim.pending:
                    assert time.monotonic() < deadline, "ordinary PvP death did not complete"
                    command(god, "purge")
                    player.send("kill orc")
                    victim._receive()
                    time.sleep(0.2)
                victim.expect("Your wounds claim you at last", timeout=5)
                player.expect("You just gained", timeout=60)
                assert re.search(r"Level:\s*31\b", plain_text(command(player, "score"))), "cap granted an early level"
                durable = fixture("inspect")
                assert "LEVEL 31 " in durable and re.search(r"SCORES (\d+):10",durable) and int(re.search(r"SCORES (\d+):10",durable).group(1)) > 10, durable
                shown = plain_text(command(player, "fraglist"))
                assert "Good currently leads" in shown, shown
                print(f"{backend}: ordinary PvP receipt changed the provisional leader without opening early", flush=True)

                deadline = time.monotonic() + 190
                while True:
                    shown = plain_text(command(player, "fraglist normal"))
                    if "Faction level caps: Good 32 / Evil 31" in shown:
                        break
                    assert time.monotonic() < deadline, shown
                    time.sleep(1)
                assert time.time() >= earliest
                assert "LEVEL 32 " in fixture("inspect")
                assert re.search(r"Level:\s*31\b", plain_text(command(player, "score"))), "unlock granted a free level"
                command(god, "purge")
                command(god, f"load mob {mob}")
                player.send("kill " + keyword)
                deadline = time.monotonic() + 30
                while True:
                    shown = plain_text(command(player, "score"))
                    if re.search(r"Level:\s*32\b", shown):
                        break
                    assert time.monotonic() < deadline, shown
                    time.sleep(0.2)
                command(god, "goto 22800")
                command(god, "transfer " + PLAYER)
                save(player, PLAYER)
                confirmed = fixture("inspect")
                stop()
                boot()
                player = connect(PLAYER)
                assert re.search(r"Level:\s*32\b", plain_text(command(player, "score")))
                shown = plain_text(command(player, "fraglist"))
                assert "Faction level caps: Good 32 / Evil 31" in shown and "Good 0.00 / Evil 0.00" in shown, shown
                assert fixture("inspect") == confirmed
                stop()
                for action,expected in (("quiet","Good 33 / Evil 32"),("circle","Good 36 / Evil 36")):
                    fixture(action,PLAYER,int(time.time())+30)
                    boot();player=connect(PLAYER)
                    deadline=time.monotonic()+110
                    while True:
                        shown=plain_text(command(player,"fraglist normal"))
                        if "Faction level caps: "+expected in shown:break
                        assert time.monotonic()<deadline,shown
                        time.sleep(1)
                    assert "Good 0.00 / Evil 0.00" in shown,shown
                    assert re.search(r"Level:\s*32\b",plain_text(command(player,"score"))),"quiet result granted a free character level"
                    stop()
                    print(f"{backend}: no-PvP {action} result {expected}",flush=True)
                print(f"PASS {backend}: per-viewer status, real PvP → receipt → maintenance → shared cap → banked XP → restart", flush=True)
            except Exception:
                evidence = output_root / ("issue-508-journey-" + backend + ".log")
                evidence.write_bytes(output_path.read_bytes())
                for index, client in enumerate(clients):
                    (output_root / f"issue-508-journey-{backend}-client-{index}.txt").write_bytes(client.transcript)
                print("Journey failure evidence:", evidence, flush=True)
                raise
            finally:
                for client in clients:
                    client.close()
                if process and process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=30)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=10)
                if redis:
                    redis.terminate()
                    redis.wait(timeout=10)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", choices=("flatfile", "mariadb"), default="flatfile")
    parser.add_argument("--server", type=Path)
    args = parser.parse_args()
    (ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="frag-cap-build-", dir=ROOT / "bin/tests") as temporary:
        if args.server:
            binary = args.server.resolve()
        else:
            assert args.backend == "flatfile", "pass a MariaDB binary with --server"
            binary = journey.build_flatfile_server(Path(temporary))
        run(args.backend, binary)
