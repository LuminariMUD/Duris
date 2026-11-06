#!/usr/bin/env python3
"""A storage chest never loses an item to a crash or to a nested container's save.

Killing the server right after `get` must leave the item with exactly one owner, and an
item decaying inside a nested chest must not remove that chest from the saved world.

No arguments runs the flat-file leg; --backend mariadb --server PATH runs under
with_disposable_mariadb.sh. No checkout .env or running game is used.
"""
import argparse
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time

import test_flatfile_combat_journey as journey
from test_flight_network_journey import authority, command

ROOT = journey.ROOT
ROOM = 132500
POTION = "a thick cyan potion"


def run(binary, backend):
    if backend == "flatfile":
        subprocess.run(["python3", "tests/async/test_flatfile_player_repository.py",
                        "--build-inspector", str(journey.INSPECTOR)], cwd=ROOT, check=True,
                       timeout=300)
    with tempfile.TemporaryDirectory(prefix="chest-crash-", dir=ROOT / "bin/tests") as temporary:
        runtime = Path(temporary)
        (runtime / "logs/log").mkdir(parents=True)
        (runtime / "journals/critical").mkdir(parents=True, mode=0o700)
        journey.make_fixture(runtime)
        (runtime / "help").symlink_to(ROOT / "help", target_is_directory=True)
        journey.generate_certificate(runtime)
        properties = runtime / "lib/duris.properties"
        text = properties.read_text()
        assert "timer.decay.corpse.npc=20.000" in text
        properties.write_text(text.replace("timer.decay.corpse.npc=20.000",
                                           "timer.decay.corpse.npc=1.000"))
        plain, tls, websocket = journey.available_ports()
        output_path = runtime / "server.out"
        process = client = None

        with authority(backend, runtime) as (env, sql):
            env.update(CRITICAL_COMMAND_JOURNAL_DIR=str(runtime / "journals/critical"),
                       DURIS_TLS_PORT=str(tls), DURIS_WEBSOCKET_PORT=str(websocket),
                       MAINTENANCE_STATE_FILE=str(runtime / "maintenance.state"))
            state = runtime / "state"
            if not sql:
                (state / "domains").mkdir(mode=0o700)
                subprocess.run([str(journey.INSPECTOR), str(state), "seed-combat"], check=True)

            def boot():
                nonlocal process
                start = output_path.stat().st_size if output_path.exists() else 0
                with output_path.open("a") as output:
                    process = subprocess.Popen(
                        [str(binary), "-d", str(runtime), str(plain)], cwd=runtime,
                        env=env, stdout=output, stderr=subprocess.STDOUT)
                deadline = time.monotonic() + 150
                while b"Entering game loop." not in output_path.read_bytes()[start:]:
                    assert process.poll() is None and time.monotonic() < deadline, "boot failed"
                    time.sleep(.1)

            def stop(sent=signal.SIGTERM):
                client.close()
                process.send_signal(sent)
                process.wait(timeout=60)
                assert process.returncode == (-signal.SIGKILL if sent == signal.SIGKILL else 0)

            def login():
                nonlocal client
                client = journey.reconnect_character(plain, expected_room=None)
                client.expect_any(("Pos:", "<>"), timeout=30)
                command(client, "toggle paging no")
                command(client, f"goto {ROOM}")

            def owners(label):
                """Where the potion is; each listing is fenced by its own score."""
                found = []
                if POTION in command(client, "look in huge"):
                    found.append("chest")
                if POTION in command(client, "inventory"):
                    found.append("inventory")
                if "A potion lies here" in command(client, "look"):
                    found.append("floor")
                print(label + ": " + (",".join(found) or "nowhere"), flush=True)
                return found

            try:
                boot()
                client = journey.MudClient(plain)
                journey.create_character(client, expected_room=None)
                stop()
                if sql:
                    sql(f"UPDATE player_data SET level=62,highest_level=62 "
                        f"WHERE name='{journey.CHARACTER}'")
                else:
                    journey.make_overlord(state, journey.CHARACTER)

                # A floor chest holds a storage chest holding a potion and a decaying corpse.
                boot()
                login()
                command(client, "goto 82400")
                command(client, "kill buck")
                command(client, "get corpse")
                command(client, f"goto {ROOM}")
                for text in ("load obj 130", "open chest", "put corpse chest", "load obj 2800",
                             "get potion", "put potion chest", "get chest", "load obj 115",
                             "open huge", "put chest huge", "load obj 2800", "get potion",
                             "put potion huge", "save"):
                    command(client, text)
                inside = command(client, "look in huge")
                assert "a storage chest" in inside and POTION in inside, inside

                # The decay writes the nested chest, which must not remove it from the world.
                time.sleep(80)
                stop()
                boot()
                login()
                assert owners("after decay and clean reboot") == ["chest"]
                command(client, "get chest huge")
                nested = command(client, "look in chest")
                assert POTION in nested and "corpse" not in nested, nested

                # No kill point may lose the item or leave it with two owners.
                for delay in (0, 0, .02, .1, 2):
                    client.send("get potion huge")
                    client.expect("You get a thick cyan potion", timeout=20)
                    time.sleep(delay)
                    stop(signal.SIGKILL)
                    boot()
                    login()
                    found = owners(f"killed {delay}s after get")
                    assert len(found) == 1, found
                    if found == ["inventory"]:
                        command(client, "put potion huge")
                    elif found == ["floor"]:
                        for text in ("get potion", "put potion huge"):
                            command(client, text)
                    time.sleep(3)
                client.close()
                process.send_signal(signal.SIGTERM)
                process.wait(timeout=60)
            except Exception:
                print(output_path.read_text(errors="replace")[-6000:])
                if client:
                    print(bytes(client.transcript)[-12000:].decode(errors="replace"))
                raise
            finally:
                if process and process.poll() is None:
                    process.kill()
                    process.wait(timeout=5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", choices=("flatfile", "mariadb"), default="flatfile")
    parser.add_argument("--server", type=Path)
    args = parser.parse_args()
    subprocess.run(["make", "world"], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    (ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="chest-crash-build-", dir=ROOT / "bin/tests") as build:
        server = args.server.resolve() if args.server else journey.build_flatfile_server(Path(build))
        run(server, args.backend)
    print(f"storage chest crash journey passed ({args.backend})")
