#!/usr/bin/env python3
"""A locker keeps what it holds across a restart (persistence reset Phase 3 step 8).

The character drops the banana in its account locker and the server restarts: the locker
still holds it. It takes the banana back and the server restarts again: the banana is in its
inventory and the locker is empty. A mace left in the locker of a guild it founds is there when
it enters again once that save has landed (a minimal world loads no guilds after a restart).
The character is promoted to a god, which may use a locker outside a town.
Copyover and hotboot from occupied public/private lockers retain the items and
restore the occupant outside the door on the original connection.
"""

import argparse
import pathlib
import shutil
import signal
import subprocess
import tempfile
import time

import test_flatfile_combat_journey as journey
from test_flight_network_journey import command

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
    try:
        deadline = time.monotonic() + 120
        while b"Entering game loop." not in output_path.read_bytes()[start:]:
            journey.require(process.poll() is None and time.monotonic() < deadline,
                            "server did not boot:\n" +
                            output_path.read_text(errors="replace")[-8000:])
            time.sleep(0.1)
        return process
    except BaseException:
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
        raise


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


def walk_out(client):
    """Leave the locker once anything just moved has been saved."""
    deadline = time.monotonic() + 60
    while True:
        client.send("north")
        matched, _ = client.expect_any(("applying magic locks", "still being secured"), timeout=30)
        if matched == "applying magic locks":
            return
        journey.require(time.monotonic() < deadline, "the locker contents were never saved")
        time.sleep(1)


def leave(client):
    walk_out(client)
    client.send("save")
    client.expect(f"Saving {journey.CHARACTER}.", timeout=30)
    client.send("quit")
    client.expect("ACCOUNT MENU", timeout=30)
    client.send("0")
    client.close()


def copyover_occupied_locker(client, process, sql, inventory, *, hotboot=False):
    client.send("shutdown hotboot" if hotboot else "copyover")
    matched, text = client.expect_any(("Copyover complete!", "Copyover cancelled:",
                                       "Copyover FAILED"), timeout=90)
    journey.require(matched == "Copyover complete!", text)
    journey.require(process.poll() is None, "copyover lost the server process")
    journey.require("The Regression Arena" in command(client, "look"),
                    "the occupant did not return outside the locker door")
    journey.require(sql(f"SELECT last_room FROM player_data WHERE name='{journey.CHARACTER}'") ==
                    "22800", "the occupant was saved inside the locker")
    journey.require(sql(f"SELECT obj_uid FROM player_items WHERE pid=(SELECT pid FROM player_data "
                        f"WHERE name='{journey.CHARACTER}') ORDER BY obj_uid") == inventory,
                    "copyover changed the occupant's inventory")
    journey.require("a banana" in command(client, "inventory"), "copyover lost the banana")
    print(f"{'hotboot' if hotboot else 'copyover'} retained inventory and recovered outside "
          "the occupied locker on the original connection", flush=True)


def run(binary: pathlib.Path) -> None:
    with tempfile.TemporaryDirectory(prefix="duris-locker-run-") as run_tmp, \
            journey.mariadb_authority() as (environment, sql):
        run_root = pathlib.Path(run_tmp)
        (run_root / "logs/log").mkdir(parents=True)
        journey.make_fixture(run_root, reset_coins=True)
        add_lockers(run_root)
        journey.generate_certificate(run_root)
        (run_root / "logs/log/.gitignore").write_text("*\n")
        (run_root / "bin/server").mkdir(parents=True)
        for name in ("dms", "dms_new"):
            shutil.copy2(binary, run_root / "bin/server" / name)
        binary = run_root / "bin/server/dms"
        (run_root / "journals/critical").mkdir(parents=True, mode=0o700)
        plain_port, tls_port, websocket_port = journey.available_ports()
        environment.update(CRITICAL_COMMAND_JOURNAL_DIR=str(run_root / "journals/critical"),
                           DURIS_TLS_PORT=str(tls_port), DURIS_WEBSOCKET_PORT=str(websocket_port))
        process = boot(binary, run_root, environment, plain_port)
        try:
            # The character loots the banana and 3 silver, then becomes a god.
            client = journey.MudClient(plain_port)
            journey.create_character(client)
            journey.complete_npc_combat_journey(client, reset_coins=True)
            client.close()
            stop(process)
            journey.make_overlord(sql, journey.CHARACTER)
            sql(f"UPDATE player_data SET platinum=1000 WHERE name='{journey.CHARACTER}'")

            process = boot(binary, run_root, environment, plain_port)
            client = journey.reconnect_character(plain_port)
            # First named owner entry must create the same locker as default entry.
            enter_locker(client, 0, journey.CHARACTER)
            # Trusted staff keep their stat command; in mortal mode it routes as for a player.
            assert "Character attributes for" not in command(client, "stat")
            command(client, "toggle fog")
            assert "Character attributes for" in command(client, "stat")
            assert "what item should i tell" in command(client, "stat no-such-item")
            command(client, "toggle fog")
            assert "Character attributes for" not in command(client, "stat")
            client.send("drop banana")
            client.expect("You drop a banana.", timeout=10)
            leave(client)
            client = journey.reconnect_character(plain_port)
            client.send(f"supervise found {journey.CHARACTER} n Journeyguild")
            client.expect("new association is set up", timeout=30)
            client.send("load obj 677")
            client.send("say mace loaded")
            client.expect("mace loaded", timeout=10)
            # This isolated minimal world has no guilds before the one just founded.
            enter_locker(client, 0, "GuIlD.1.LoCkEr")
            client.send("drop mace")
            client.expect("You drop", timeout=10)
            walk_out(client)
            reenter_locker(client, 1, "guild.1")
            walk_out(client)
            reenter_locker(client, 1, "guild")
            leave(client)
            stop(process)

            # The account locker comes back holding the banana; the character takes it.
            process = boot(binary, run_root, environment, plain_port)
            client = journey.reconnect_character(plain_port)
            # A character name must reach the same account locker after restart.
            enter_locker(client, 1, journey.CHARACTER.swapcase())
            client.send("get banana chest")
            client.expect("You get a banana", timeout=10)
            leave(client)
            stop(process)

            # It stays with the character, and the locker comes back empty.
            process = boot(binary, run_root, environment, plain_port)
            client = journey.reconnect_character(plain_port)
            client.send("inventory")
            client.expect("a banana", timeout=10)
            inventory = sql(f"SELECT obj_uid FROM player_items WHERE pid=(SELECT pid FROM player_data "
                            f"WHERE name='{journey.CHARACTER}') ORDER BY obj_uid")
            enter_locker(client, 0)
            client.send("load obj 677")
            client.expect("You have created", timeout=10)
            client.send("drop mace")
            client.expect("You drop", timeout=10)
            copyover_occupied_locker(client, process, sql, inventory)
            enter_locker(client, 1)
            journey.require("mace" in command(client, "look in chest"),
                            "copyover lost the public locker contents")
            client.send("get mace chest")
            client.expect("You get", timeout=10)
            client.send("eq chest create vault fixture-secret")
            client.expect("Private chest 'vault' created", timeout=30)
            client.send("open vault fixture-secret")
            client.expect("You open the 'vault' chest", timeout=30)
            client.send("put mace vault")
            client.expect("Ok.", timeout=10)
            copyover_occupied_locker(client, process, sql, inventory, hotboot=True)
            # The entry count covers public storage; inspect private contents below.
            enter_locker(client, 0)
            client.send("open vault fixture-secret")
            client.expect("You open the 'vault' chest", timeout=30)
            journey.require("mace" in command(client, "look in vault"),
                            "hotboot lost the private chest contents")
            # A newly loaded chest has no in-memory save receipt yet. Its first
            # terminal snapshot must wait for the private destination to commit.
            copyover_occupied_locker(client, process, sql, inventory)
            enter_locker(client, 0)
            client.send("open vault fixture-secret")
            client.expect("You open the 'vault' chest", timeout=30)
            journey.require("mace" in command(client, "look in vault"),
                            "copyover lost the reloaded private chest contents")
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", type=pathlib.Path, required=True)
    run(parser.parse_args().server.resolve())
    print("locker journey passed")
