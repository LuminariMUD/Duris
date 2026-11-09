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
from test_gmcp_control_journey import drain, send_telnet, telnet_packets, wait_telnet


PREPARATION = "Char.SpellPreparation"
COMPLETE = {"state": "complete", "estimatedSeconds": 0}


def support_preparation(client):
    client.socket.sendall(b"\xff\xfd\xc9")
    send_telnet(client, "Core.Supports.Set", ["Duris.Capabilities 1", PREPARATION + " 1"])
    caps = wait_telnet(client, "Duris.Capabilities", predicate=lambda value:
                       PREPARATION in value["supported"])
    assert caps["features"][PREPARATION] == 1 and PREPARATION not in caps["active"], caps


def subscribe_preparation(client):
    send_telnet(client, "Duris.Subscribe", [PREPARATION + " 1"])


def preparation(client, after, state, timeout=8):
    return wait_telnet(client, PREPARATION, after, lambda value: value["state"] == state,
                       timeout=timeout)


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
            staff.send("save"); staff.expect(f"Saving {journey.CHARACTER}.")
            staff.send("quit"); staff.expect("ACCOUNT MENU")
            server.stop()
            journey.make_overlord(state, journey.CHARACTER)
            server.start()
            staff = server.client = journey.reconnect_character(server.port)
            command(staff, "toggle page off")
            command(staff, "vis 0")
            support_preparation(staff)
            subscribe_preparation(staff)
            assert preparation(staff, 0, "complete") == COMPLETE
            staff_before = len(telnet_packets(staff))
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
                # Keep the real preparation events long enough for several GMCP flushes.
                timing_stat = "wis" if cls == "c" else "int"
                command(staff, f"setbit char {name} {timing_stat} 20")
                command(client, "rest")
                support_preparation(client)
                queued = command(client, f"{request} {spell}")
                assert f"You are {'praying for' if cls == 'c' else 'memorizing'} {spell}" in queued, queued
                drain(client)
                assert not any(package == PREPARATION for package, _ in telnet_packets(client))
                subscribe_preparation(client)
                active = preparation(client, 0, "active")
                assert active["estimatedSeconds"] > 0, active
                queued_count = 1
                if cls == "c":
                    before = len(telnet_packets(client))
                    command(client, f"{request} {spell}")
                    added = preparation(client, before, "active")
                    assert added["estimatedSeconds"] > active["estimatedSeconds"], (active, added)
                    queued_count = 2
                before = len(telnet_packets(client))
                command(client, "stand")
                paused = preparation(client, before, "paused")
                assert paused["estimatedSeconds"] > 0, paused
                before = len(telnet_packets(client))
                drain(client)
                assert not any(package == PREPARATION for package, _ in telnet_packets(client)[before:])
                command(client, "rest")
                command(client, request)
                preparation(client, before, "active")
                before = len(telnet_packets(client))
                prepared = command(staff, f"battleprep {name} spells")
                assert preparation(client, before, "complete") == COMPLETE
                assert f"{queued_count} newly prepared spells" in prepared, prepared
                spells = command(client, request)
                assert "You have memorized" in spells and spell in spells, spells
                command(client, "stand")
                client.send("save")
                client.expect(f"Saving {name}.", timeout=30)
                print(f"{name}: level 56, queued spell ready, native save complete", flush=True)
                client.close()
                clients.remove(client)
            druid = journey.MudClient(server.port)
            clients.append(druid)
            journey.create_character(druid, account="Battledruid", character="Battledruid",
                                     email="battledruid@example.invalid", class_name="d")
            command(druid, "toggle page off")
            assert "Battledruid baseline ready" in command(staff, "battleprep Battledruid baseline")
            command(staff, "setbit char Battledruid agi 100")
            command(staff, "setbit char Battledruid wis 20")
            support_preparation(druid)
            subscribe_preparation(druid)
            assert preparation(druid, 0, "complete") == COMPLETE
            before = len(telnet_packets(druid))
            command(druid, "cast 'barkskin' self")
            active = preparation(druid, before, "active")
            assert active["estimatedSeconds"] > 0, active
            assert preparation(druid, before, "complete", timeout=active["estimatedSeconds"] + 15) == COMPLETE

            drain(staff)
            assert not any(package == PREPARATION for package, _ in telnet_packets(staff)[staff_before:])
            druid.close()
            clients.remove(druid)
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
                                           "master book load/give", "pray/memorize queues", "private spell preparation GMCP",
                                                        "slot recovery", "save/restart/reload"]}))
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
    run(args.binary.resolve())
