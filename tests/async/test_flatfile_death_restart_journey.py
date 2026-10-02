#!/usr/bin/env python3
"""Die, restart the full world and loot the restored corpse (persistence reset Phase 3 step 9).

The minimal-world journeys skip corpse restoration, so this one runs the full world: a new
character takes its own life, the server restarts and restores the corpse where it died, and
the character loots its mace from it. After another restart the mace is still the
character's and no longer in the corpse. Put back into the corpse, the mace is there after
a third restart, and the character loots it again.
"""

import os
import pathlib
import shutil
import signal
import subprocess
import tempfile
import time

import test_flatfile_combat_journey as journey

ROOT = journey.ROOT


def boot(binary, run_root, environment, port, name):
    output_path = run_root / name
    with output_path.open("w", encoding="utf-8") as output:
        process = subprocess.Popen([str(binary), "-d", str(run_root), str(port)],
                                   cwd=run_root, env=environment, text=True, stdout=output,
                                   stderr=subprocess.STDOUT)
    deadline = time.monotonic() + 300
    while "Entering game loop." not in output_path.read_text(errors="replace"):
        journey.require(process.poll() is None and time.monotonic() < deadline,
                        "server did not boot:\n" +
                        output_path.read_text(errors="replace")[-8000:])
        time.sleep(0.2)
    return process


def stop(process):
    process.send_signal(signal.SIGTERM)
    process.wait(timeout=120)
    journey.require(process.returncode == 0, "the server did not stop normally")


def listing(client, command):
    # The say marks where the listing ends.
    client.send(command)
    client.send("say end of listing")
    return client.expect("end of listing", timeout=10)


def run(binary: pathlib.Path) -> None:
    with tempfile.TemporaryDirectory(prefix="duris-death-state-") as state_tmp, \
            tempfile.TemporaryDirectory(prefix="duris-death-run-") as run_tmp:
        state_root = pathlib.Path(state_tmp)
        run_root = pathlib.Path(run_tmp)
        state_root.chmod(0o700)
        (run_root / "logs/log").mkdir(parents=True)
        for directory in ("areas_mini", "docs"):
            (run_root / directory).symlink_to(ROOT / directory, target_is_directory=True)
        # A player corpse holds the weight its player carried, and its shell (object 2,
        # weight 200) counts against that, so a new character could put nothing back into
        # its corpse. This run's world gives the shell no weight.
        (run_root / "areas").mkdir()
        for entry in (ROOT / "areas").iterdir():
            if entry.name != "world.obj":
                (run_root / "areas" / entry.name).symlink_to(entry)
        world = (ROOT / "areas/world.obj").read_bytes()
        shell = b"#2\ncorpse~\n&+La corpse&N~\n&+LA corpse is here.&N~\n~\n" \
                b"24 2 3 30 7 0 73728 0 0 0 0\n0 0 0 0 0 0 0 0\n200 0 100\n"
        journey.require(world.count(shell) == 1, "corpse prototype fixture changed")
        (run_root / "areas/world.obj").write_bytes(
            world.replace(shell, shell.replace(b"\n200 0 100\n", b"\n0 0 100\n")))
        shutil.copytree(ROOT / "lib", run_root / "lib")
        # Quitting outside an inn camps; keep the camp short.
        properties = run_root / "lib/duris.properties"
        text = properties.read_text()
        journey.require("camp.timer=9.000" in text, "camp timer fixture changed")
        properties.write_text(text.replace("camp.timer=9.000", "camp.timer=2.000"))
        journey.generate_certificate(run_root)
        (run_root / "journals/critical").mkdir(parents=True, mode=0o700)
        port, tls_port, websocket_port = journey.available_ports()
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
        }
        if runtime_library_path := os.environ.get("LD_LIBRARY_PATH"):
            environment["LD_LIBRARY_PATH"] = runtime_library_path
        process = boot(binary, run_root, environment, port, "first.out")
        try:
            client = journey.MudClient(port)
            journey.create_character(client, expected_room=None)
            client.send("inventory")
            client.expect("a small wooden mace", timeout=10)
            client.send("suicide")
            client.expect("Please confirm that you wish to do this!", timeout=10)
            client.send("yes")
            client.expect("ACCOUNT MENU", timeout=60)
            client.send("0")
            client.close()
            stop(process)

            # The full world restores the corpse where the character died.
            process = boot(binary, run_root, environment, port, "second.out")
            client = journey.reconnect_character(port, "You rejoin the land of the living",
                                                 expected_room=None)
            journey.require("a small wooden mace" in listing(client, "look in corpse"),
                            "the restored corpse lost the mace")
            client.send("get mace corpse")
            client.expect("You get a small wooden mace", timeout=10)
            client.send("save")
            client.expect(f"Save complete for {journey.CHARACTER}.", timeout=30)
            client.send("quit")
            client.expect("ACCOUNT MENU", timeout=30)
            client.send("0")
            client.close()
            stop(process)

            # The loot is the character's after a restart, and gone from the corpse.
            process = boot(binary, run_root, environment, port, "third.out")
            client = journey.reconnect_character(port, "You break camp and get ready to move on",
                                                 expected_room=None)
            client.send("inventory")
            client.expect("a small wooden mace", timeout=10)
            corpse = listing(client, "look in corpse")
            journey.require("corpse of taverek" in corpse.lower() and
                            "a small wooden mace" not in corpse,
                            "the looted mace came back in the corpse:\n" + corpse)
            # An item put into a player corpse is the corpse's to save.
            client.send("put mace corpse")
            client.expect("Ok.", timeout=10)
            client.send("quit")
            client.expect("ACCOUNT MENU", timeout=30)
            client.send("0")
            client.close()
            stop(process)

            # The mace is in the corpse after a restart, not with the character.
            process = boot(binary, run_root, environment, port, "fourth.out")
            client = journey.reconnect_character(port, "You break camp and get ready to move on",
                                                 expected_room=None)
            journey.require("a small wooden mace" not in listing(client, "inventory"),
                            "the mace put into the corpse came back to the character")
            journey.require("a small wooden mace" in listing(client, "look in corpse"),
                            "the mace put into the corpse was lost at the restart")
            client.send("get mace corpse")
            client.expect("You get a small wooden mace", timeout=10)
            client.send("quit")
            client.expect("ACCOUNT MENU", timeout=30)
            client.send("0")
            client.close()
            stop(process)
        except Exception:
            for name in ("first.out", "second.out", "third.out", "fourth.out"):
                path = run_root / name
                if path.exists():
                    print(f"==== {name}\n" + path.read_text(errors="replace")[-4000:])
            raise
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix=f"flatfile-death-{os.getpid()}-",
                                     dir=ROOT / "bin/tests") as build_tmp:
        run(journey.build_flatfile_server(pathlib.Path(build_tmp)))
    print("flat-file die, restart and loot journey passed")
