#!/usr/bin/env python3
"""Real barehand proc, exclusions, inspection and save/reload on both backends.

Uses disposable state and MariaDB; never reads .env or uses a running MUD.
The normal packed denominator is one in this test-only object. No live glove
or combat endpoint is changed by the fixture.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import uuid

import test_flatfile_combat_journey as journey
import run_weapon_actions_journey as weapon
from run_item_pilot_journey import Server, set_properties, configure, object_records
from run_world_quest_dual_backend import prepare_mariadb

ROOT = Path(__file__).resolve().parents[2]
FLARE = "The regression gloves flare with monk magic."
GLOVE = """#22802
regression gloves~
the regression gloves~
A pair of regression gloves lies here.~
~
9 13 3 6 7 0 0 129 524288 0 0
0 0 0 0 0 32 1 1
1 0 100
E
_char_msg~
The regression gloves flare with monk magic.
~
"""


def command(client, text, seconds=.3):
    client.pending.clear()
    client.send(text)
    return weapon.drain(client, seconds)


def fight(client, expected, staff=False):
    if staff:
        command(client, "restore Taverek")
        command(client, "goto 22800")
    output = command(client, "hit sentinel", .5)
    assert "isn't here" not in output, output
    deadline = time.monotonic() + (35 if expected else 10)
    while time.monotonic() < deadline:
        output += weapon.drain(client, 1)
        if expected and FLARE in output:
            break
    assert (FLARE in output) == expected, output[-5000:]
    if staff:
        command(client, "tranquilize Taverek")
        command(client, "goto 22801")
        return output
    command(client, "flee", 1)
    # Flee can fail. The fixture has a single north exit; keep trying until out.
    for _ in range(10):
        location = command(client, "look")
        if "Regression Refuge" in location:
            break
        command(client, "flee", .5)
    else:
        raise AssertionError("could not leave fixture fight")
    return output


def run(binary, backend):
    container = None
    database = "monk_gloves_" + uuid.uuid4().hex[:10]
    db_env = {}
    root_password = None
    if backend == "mariadb":
        container, _, root_password, _, prepared = prepare_mariadb(database)
        db_env = {key: prepared[key] for key in (
            "DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWD", "DB_NAME",
            "DB_ALLOWED_TARGETS", "DB_TLS", "DB_SOCKET")}
        db_env["PERSISTENCE_MODE"] = "mariadb-primary"

    def sql(statement):
        return subprocess.check_output(["docker", "exec", "-i", "-e",
            "MYSQL_PWD=" + root_password, container, "mariadb", "-h127.0.0.1",
            "-uroot", "-N", "-B", database], input=statement, text=True).strip()

    with tempfile.TemporaryDirectory(prefix="monk-glove-journey-", dir=ROOT / "bin/tests") as temporary:
        root = Path(temporary) / "runtime"
        state = Path(temporary) / "state"
        root.mkdir(); state.mkdir(mode=0o700); (state / "domains").mkdir(mode=0o700)
        if backend == "flatfile":
            subprocess.run([str(journey.INSPECTOR), str(state), "seed-combat"], check=True)
        configure(root, "studio", False)
        set_properties(root, {"hitpoints.class.Monk": 5000, "hitpoints.class.Warrior": 5000})
        objects = root / "areas_mini/mini.obj"
        records = object_records(objects.read_text()); records[22802] = GLOVE
        objects.write_text("".join(records[key] for key in sorted(records)) + "$~\n")
        zone = root / "areas_mini/mini.zon"
        zone.write_text(re.sub(r"^E .*\n", "", zone.read_text(), flags=re.M).replace(
            "\nS\n", "\nO 0 22802 1 22800 100 0 0 0 * monk glove\nS\n"))
        (root / "areas/world.obj").write_text(objects.read_text())
        (root / "areas/world.zon").write_text(zone.read_text())
        runtime_binary = root / "server"
        shutil.copy2(binary, runtime_binary)
        server = Server(runtime_binary, root, state, "studio", db_env)
        client = None
        try:
            server.start()
            client = server.client = journey.MudClient(server.port)
            journey.create_character(client, class_name="k")
            command(client, "remove all"); command(client, "drop all")
            assert "You get" in command(client, "get gloves")
            assert "hands" in command(client, "wear gloves")
            output = fight(client, True)
            print(backend + ": real level-one monk punch dispatched", flush=True)
            command(client, "remove gloves"); command(client, "south")
            fight(client, False)
            command(client, "wear gloves")
            command(client, "save"); command(client, "quit", 1)
            server.stop()
            if backend == "flatfile":
                journey.make_overlord(state, journey.CHARACTER)
            else:
                sql("UPDATE player_data SET level=62,highest_level=62 WHERE name='Taverek'")
            server.start()
            client = server.client = journey.reconnect_character(server.port, expected_room="The Regression Refuge")
            inspection = command(client, "stat obj gloves", 1)
            assert "MONK_PROC" in inspection and "primary hands" in inspection, inspection
            assert "1/1" in inspection and "level" in inspection, inspection
            command(client, "vis 0")
            command(client, "setbit char sentinel basehit 100000000")
            command(client, "restore sentinel")
            command(client, "setbit char sentinel hit 100000000")
            # A live opponent can provoke a legitimate barehand monk riposte
            # even while a weapon is wielded. Isolate the actual weapon hits here.
            command(client, "setbit char sentinel aff5 'NOT OFFENSIVE' 1")
            # Use the ordinary weapon proc path with the same marked gloves on.
            command(client, "load obj 22801")
            command(client, "wield wandblade")
            fight(client, False, staff=True)
            command(client, "remove wandblade")
            command(client, "setbit char Taverek class Warrior")
            fight(client, False, staff=True)
            # Persistence must retain the original source's flag and fields.
            command(client, "setbit char Taverek class Monk")
            fight(client, True, staff=True)
            command(client, "save")
            print(backend + ": real punches proc; removal, weapon and non-monk exclusions; restart/stat passed", flush=True)
            return {"backend": backend, "barehand_proc": True, "unequipped_excluded": True,
                    "weapon_excluded": True, "non_monk_excluded": True,
                    "save_restart_inspection": True, "first_fight_messages": len(output)}
        except Exception:
            if client:
                print(bytes(client.transcript).decode(errors="replace").replace(journey.PASSWORD, "[REDACTED]")[-7000:])
            print(journey.runtime_logs(root)[-7000:])
            raise
        finally:
            server.stop()
            if container:
                subprocess.run(["docker", "rm", "-f", container], check=True,
                               stdout=subprocess.DEVNULL)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--flatfile", type=Path)
    parser.add_argument("--mariadb", type=Path)
    args = parser.parse_args()
    assert args.flatfile or args.mariadb
    results = [run(binary.resolve(), backend) for backend, binary in
               (("flatfile", args.flatfile), ("mariadb", args.mariadb)) if binary]
    print(json.dumps(results, indent=2))
