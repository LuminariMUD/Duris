#!/usr/bin/env python3
"""Real command dispatch, ordinary spell preparation, save and restart for battleprep.

Pass a freshly built flat-file server with --binary. Only the disposable fixture's
staff character is promoted offline; battle characters use the new command.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

import test_flatfile_combat_journey as journey
from run_item_pilot_journey import Server
from run_paladin_balance_journey import command


def configure(root):
    (root / "logs/log").mkdir(parents=True)
    journey.make_fixture(root)
    journey.generate_certificate(root)
    # No hostile reset is needed for a preparation/persistence journey.
    zone = root / "areas_mini/mini.zon"
    zone.write_text(re.sub(r"^[MGE] .*\n", "", zone.read_text(), flags=re.M))
    (root / "areas").unlink()  # only this disposable fixture's symlink
    (root / "areas").mkdir()
    generated = {f"world.{suffix}" for suffix in
                 ("wld", "mob", "obj", "zon", "trg", "shp", "qst", "tab", "weather")}
    for path in (journey.ROOT / "areas").iterdir():
        if path.name not in generated:
            (root / "areas" / path.name).symlink_to(path, target_is_directory=path.is_dir())
    for suffix in ("wld", "mob", "obj", "zon"):
        (root / f"areas/world.{suffix}").write_text((root / f"areas_mini/mini.{suffix}").read_text())
    for suffix in ("shp", "qst", "tab", "weather"):
        path = root / f"areas_mini/world.{suffix}"
        (root / f"areas/world.{suffix}").write_text(path.read_text() if path.exists() else "$~\n")
    (root / "areas/world.trg").write_text("#~\n")


def run(binary):
    with tempfile.TemporaryDirectory(prefix="battleprep-journey-", dir=journey.ROOT / "bin/tests") as directory:
        root = Path(directory)
        runtime, state = root / "runtime", root / "state"
        runtime.mkdir(); state.mkdir(mode=0o700); (state / "domains").mkdir(mode=0o700)
        configure(runtime)
        subprocess.run([str(journey.INSPECTOR), str(state), "seed-combat"], check=True)
        server = Server(binary, runtime, state, "battleprep")
        clients = []
        try:
            server.start()
            staff = server.client = journey.MudClient(server.port)
            journey.create_character(staff)
            staff.send("save"); staff.expect(f"Save complete for {journey.CHARACTER}.")
            staff.send("quit"); staff.expect("ACCOUNT MENU")
            server.stop()
            journey.make_overlord(state, journey.CHARACTER)
            server.start()
            staff = server.client = journey.reconnect_character(server.port)
            command(staff, "toggle page off")
            command(staff, "vis 0")
            for name, cls, spell in (("Battlecleric", "c", "full heal"),
                                     ("Battlemage", "s", "incendiary cloud")):
                client = journey.MudClient(server.port)
                clients.append(client)
                journey.create_character(client, account=name, character=name,
                                         email=f"{name.lower()}@example.invalid", class_name=cls)
                command(client, "toggle page off")
                denied = command(client, f"battleprep {name} baseline")
                assert "baseline ready" not in denied, denied
                prepared = command(staff, f"battleprep {name} baseline")
                assert f"{name} baseline ready at level 56" in prepared, prepared
                assert "Level: 56" in command(client, "score"), "baseline did not advance the PC"
                if cls == "s":
                    loaded = command(staff, "load obj 7")
                    assert "master spellbook" in loaded, loaded
                    command(staff, f"give master {name}")
                    inventory = command(client, "inventory")
                    assert "master spellbook" in inventory, inventory
                request = ("pray" if cls == "c" else "memorize")
                command(client, "rest")
                queued = command(client, f"{request} {spell}")
                assert f"You are {'praying for' if cls == 'c' else 'memorizing'} {spell}" in queued, queued
                prepared = command(staff, f"battleprep {name} spells")
                assert "1 newly prepared spells" in prepared, prepared
                spells = command(client, request)
                assert "You have memorized" in spells and spell in spells, spells
                command(client, "stand")
                client.send("save")
                client.expect(f"Save complete for {name}.", timeout=30)
                print(f"{name}: level 56, queued spell ready, native save complete", flush=True)
                client.close()
                clients.remove(client)
            server.stop()
            assert server.process.returncode == 0
            server.start()
            for name, request, spell in (("Battlecleric", "pray", "full heal"),
                                         ("Battlemage", "memorize", "incendiary cloud")):
                client = journey.reconnect_character(server.port, account=name, character=name)
                clients.append(client)
                assert "Level: 56" in command(client, "score")
                spells = command(client, request)
                assert "You have memorized" in spells and spell in spells, spells
                client.close(); clients.remove(client)
            print(json.dumps({"result": "passed", "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
                              "verified": ["staff command dispatch", "mortal denial", "native advancement",
                                           "master book load/give", "pray/memorize queues", "save/restart/reload"]}))
        except Exception as error:
            raise AssertionError(f"{error}\nServer output:\n{server.output_path.read_text()[-6000:]}") from error
        finally:
            for client in clients:
                client.close()
            server.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    args = parser.parse_args()
    (journey.ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
    subprocess.run(["python3", "tests/async/test_flatfile_player_repository.py", "--build-inspector",
                    str(journey.INSPECTOR)], cwd=journey.ROOT, check=True, timeout=180)
    run(args.binary.resolve())
