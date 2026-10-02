#!/usr/bin/env python3
"""A flat-file locker keeps what it holds across a restart (persistence reset Phase 3 step 8).

The character drops the banana in its account locker and the server restarts: the locker
still holds it. It takes the banana back and the server restarts again: the banana is in its
inventory and the locker is empty. A mace left in the locker of a guild it founds is there when
it enters again once that save has landed (a minimal world loads no guilds after a restart).
The character is promoted to a god, which may use a locker outside a town.
"""

import os
import pathlib
import signal
import subprocess
import sys
import tempfile
import time

import test_flatfile_combat_journey as journey

ROOT = journey.ROOT


def add_lockers(run_root: pathlib.Path) -> None:
    """The locker rooms, a locker counter in the arena, and guild lockers for a new guild."""
    properties = run_root / "lib/duris.properties"
    lines = properties.read_text().splitlines()
    index = next(i for i, line in enumerate(lines) if line.startswith("prestige.locker.required="))
    lines[index] = "prestige.locker.required=0.000"
    properties.write_text("\n".join(lines) + "\n")
    mini = run_root / "areas_mini"
    zone = (mini / "mini.zon").read_text()
    journey.require("29999 0 0 6 11 1" in zone, "the journey zone header changed")
    zone = zone.replace("29999 0 0 6 11 1", "65999 0 0 6 11 1")
    zone = zone.replace("\nS\n", "\nO 0 3097 1 22800 100 0 0 0 * locker counter\nS\n")
    (mini / "mini.zon").write_text(zone)
    rooms = "".join(f"#{vnum}\nA locker room~\n~\n1 0 0\nS\n" for vnum in (65201, 65202))
    world = (mini / "mini.wld").read_text()
    (mini / "mini.wld").write_text(world.replace("$~", rooms + "$~"))
    counter = ("#3097\ncounter locker~\na locker counter~\nA locker counter stands here.~\n~\n"
               "13 0 0 0 0 0 0 0 0 0 0\n0 0 0 0 0 0 0 0\n0 0 100\n")
    objects = (mini / "mini.obj").read_text()
    (mini / "mini.obj").write_text(objects.replace("$~", counter + "$~"))


def boot(binary, run_root, environment, port):
    output_path = run_root / "server.out"
    start = output_path.stat().st_size if output_path.exists() else 0
    with output_path.open("a", encoding="utf-8") as output:
        process = subprocess.Popen(
            [str(binary), "--minimal", "-d", str(run_root), str(port)], cwd=run_root,
            env=environment, text=True, stdout=output, stderr=subprocess.STDOUT)
    deadline = time.monotonic() + 120
    while "Entering game loop." not in output_path.read_text(errors="replace")[start:]:
        journey.require(process.poll() is None and time.monotonic() < deadline,
                        "server did not boot:\n" +
                        output_path.read_text(errors="replace")[-8000:])
        time.sleep(0.1)
    return process


def stop(process):
    process.send_signal(signal.SIGTERM)
    process.wait(timeout=60)
    journey.require(process.returncode == 0, "the server did not stop normally")


def enter_locker(client, items, owner=""):
    client.send(f"enter locker {owner}".strip())
    client.expect(f"You have {items} items, this cost you", timeout=30)


def reenter_locker(client, items, owner):
    """Enter again once the last visit's save has landed."""
    deadline = time.monotonic() + 60
    while True:
        client.send(f"enter locker {owner}")
        matched, entered = client.expect_any(
            ("this cost you", "Please try later", "Slow your roll"), timeout=30)
        if matched == "this cost you":
            break
        journey.require(time.monotonic() < deadline, "the locker was never saved")
        time.sleep(1)
    journey.require(f"You have {items} items, this cost you" in entered,
                    "the locker came back wrong:\n" + entered)


def leave(client):
    client.send("north")
    client.expect("applying magic locks", timeout=30)
    client.send("save")
    client.expect(f"Save complete for {journey.CHARACTER}.", timeout=30)
    client.send("quit")
    client.expect("ACCOUNT MENU", timeout=30)
    client.send("0")
    client.close()


def run(binary: pathlib.Path) -> None:
    with tempfile.TemporaryDirectory(prefix="duris-locker-state-") as state_tmp, \
            tempfile.TemporaryDirectory(prefix="duris-locker-run-") as run_tmp:
        state_root = pathlib.Path(state_tmp)
        run_root = pathlib.Path(run_tmp)
        state_root.chmod(0o700)
        (state_root / "domains").mkdir(mode=0o700)
        subprocess.run([str(journey.INSPECTOR), str(state_root), "seed-combat"], check=True)
        (run_root / "logs/log").mkdir(parents=True)
        journey.make_fixture(run_root, reset_coins=True)
        add_lockers(run_root)
        journey.generate_certificate(run_root)
        (run_root / "journals/critical").mkdir(parents=True, mode=0o700)
        plain_port, tls_port, websocket_port = journey.available_ports()
        environment = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "ENVIRONMENT": "local",
            "PERSISTENCE_MODE": "flatfile-primary",
            "FLATFILE_STATE_DIR": str(state_root),
            "CRITICAL_COMMAND_JOURNAL_DIR": str(run_root / "journals/critical"),
            "LISTEN_ADDRESS": "127.0.0.1",
            "DURIS_TLS_PORT": str(tls_port),
            "DURIS_WEBSOCKET_LISTEN_ADDRESS": "127.0.0.1",
            "DURIS_WEBSOCKET_PORT": str(websocket_port),
            "REDIS": "FALSE",
            "CHAOS_MUD": "FALSE",
        }
        if runtime_library_path := os.environ.get("LD_LIBRARY_PATH"):
            environment["LD_LIBRARY_PATH"] = runtime_library_path
        process = boot(binary, run_root, environment, plain_port)
        try:
            # The character loots the banana and 3 silver, then becomes a god.
            client = journey.MudClient(plain_port)
            journey.create_character(client)
            journey.complete_npc_combat_journey(client, reset_coins=True)
            client.close()
            stop(process)
            journey.make_overlord(state_root, journey.CHARACTER)

            process = boot(binary, run_root, environment, plain_port)
            client = journey.reconnect_character(plain_port)
            enter_locker(client, 0)
            client.send("drop banana")
            client.expect("You drop a banana.", timeout=10)
            leave(client)
            client = journey.reconnect_character(plain_port)
            client.send(f"supervise found {journey.CHARACTER} n Journeyguild")
            client.expect("new association is set up", timeout=30)
            client.send("load obj 677")
            client.send("say mace loaded")
            client.expect("mace loaded", timeout=10)
            enter_locker(client, 0, "guild")
            client.send("drop mace")
            client.expect("You drop", timeout=10)
            client.send("north")
            client.expect("applying magic locks", timeout=30)
            reenter_locker(client, 1, "guild")
            leave(client)
            stop(process)

            # The account locker comes back holding the banana; the character takes it.
            process = boot(binary, run_root, environment, plain_port)
            client = journey.reconnect_character(plain_port)
            enter_locker(client, 1)
            client.send("get banana chest")
            client.expect("You get a banana", timeout=10)
            leave(client)
            stop(process)

            # It stays with the character, and the locker comes back empty.
            process = boot(binary, run_root, environment, plain_port)
            client = journey.reconnect_character(plain_port)
            client.send("inventory")
            client.expect("a banana", timeout=10)
            enter_locker(client, 0)
            leave(client)
            stop(process)
        except Exception:
            print((run_root / "server.out").read_text(errors="replace")[-8000:])
            raise
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)


if __name__ == "__main__":
    subprocess.run(["python3", "tests/async/test_flatfile_player_repository.py",
                    "--build-inspector", str(journey.INSPECTOR)], cwd=ROOT, check=True,
                   timeout=180)
    with tempfile.TemporaryDirectory(prefix=f"flatfile-locker-{os.getpid()}-",
                                     dir=ROOT / "bin/tests") as build_tmp:
        run(journey.build_flatfile_server(pathlib.Path(build_tmp)))
    print("flat-file locker journey passed")
