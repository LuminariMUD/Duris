#!/usr/bin/env python3
"""Create two full real-PC groups, place them, then reuse the account pool.

This tests provisioning on a disposable native server. Gear and combat belong
to the later end-to-end battle journey; they are not claimed by this test.
"""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import test_flatfile_combat_journey as journey
from run_battleprep_journey import configure
from run_item_pilot_journey import Server

sys.path.insert(0, str(journey.ROOT / "scripts"))
import run_racewar_battle as battle


async def provision(server, pool, directory, room=None, prepare=False, probe=False):
    staff = await battle.Client.connect("127.0.0.1", server.port, "controller", directory)
    clients = {}
    try:
        await battle.staff_login(staff, {"account": journey.ACCOUNT, "password": journey.PASSWORD,
                                        "character": journey.CHARACTER})
        captured_room = await battle.current_room(staff)
        if probe:
            rows, caps = [], {}
            cases = [("evil", "Thri-kreen", "Warrior"), ("good", "Human", "Warrior"),
                     ("good", "Human", "Monk"), ("good", "Human", "Sorcerer")]
            for side, race, cls in cases:
                index = sum(row["side"] == side for row in rows)
                account, name = pool.account(side, index)
                client = await battle.Client.connect("127.0.0.1", server.port, name, directory)
                clients[name] = client
                actual = await battle.create_character(client, account, name, side, battle.Build(race, cls))
                rows.append({"name": name, "account": account["account"], "side": side, "index": index,
                             "race": actual.race, "class": actual.cls})
                await staff.command(f"transfer {name}")
        else:
            clients, rows, caps = await battle.connect_roster("127.0.0.1", server.port, pool, directory)
            print(f"Connected full rosters: {caps}", flush=True)
            await battle.place_groups(staff, clients, rows, caps, captured_room if room is None else room)
        if prepare:
            await battle.prepare_fighters(staff, clients, rows, directory)
        groups = await battle.refresh_groups(clients, rows, caps)
        summary = {"caps": caps, "room": captured_room if room is None else room, "rows": rows,
                   "groups": groups, "probe": probe}
        (Path(directory) / "summary.json").write_text(json.dumps(summary, indent=2))
        for row in rows:
            await clients[row["name"]].command("save", expected=f"Save complete for {row['name']}.")
        return summary
    finally:
        await asyncio.gather(*(client.close() for client in clients.values()), return_exceptions=True)
        await staff.close()


def run(binary, output, prepare=False, probe=False):
    output.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix="racewar-provision-", dir=journey.ROOT / "bin/tests") as directory:
        root = Path(directory)
        runtime, state = root / "runtime", root / "state"
        runtime.mkdir(); state.mkdir(mode=0o700); (state / "domains").mkdir(mode=0o700)
        configure(runtime)
        if prepare:
            # Real kit prototypes in the small world; no synthetic equipment or
            # changed character/combat stats. Only this disposable fixture changes.
            shutil.copy2(journey.ROOT / "areas/world.obj", runtime / "areas/world.obj")
            shutil.copy2(journey.ROOT / "areas/world.obj", runtime / "areas_mini/mini.obj")
        subprocess.run([str(journey.INSPECTOR), str(state), "seed-combat"], check=True)
        server = Server(binary, runtime, state, "racewar")
        try:
            server.start()
            staff = server.client = journey.MudClient(server.port)
            journey.create_character(staff)
            staff.send("save"); staff.expect(f"Save complete for {journey.CHARACTER}.")
            staff.send("quit"); staff.expect("ACCOUNT MENU")
            server.stop()
            journey.make_overlord(state, journey.CHARACTER)
            pool = battle.AccountPool(output / "accounts.json", "racewar@example.invalid")
            names = set()
            runs = ((1, None),) if prepare else ((1, None), (2, 1200))
            for match, room in runs:
                server.start()
                run_dir = output / f"match-{match}"
                run_dir.mkdir()
                summary = asyncio.run(provision(server, pool, run_dir, room, prepare, probe))
                new_names = {row["name"] for row in summary["rows"]}
                assert not names & new_names
                names |= new_names
                if not probe:
                    assert summary["caps"] == {"good": 20, "evil": 20}, summary["caps"]
                    assert len(new_names) == 40
                if prepare:
                    assert all(row["preparation"] == "ready" for row in summary["rows"])
                print(f"Run {match}: {len(new_names)} PCs verified in room {summary['room']} (probe={probe})", flush=True)
                server.stop()
                assert server.process.returncode == 0
            if not probe:
                assert len(pool.data["good"]) == len(pool.data["evil"]) == 20
            assert all(len(account["characters"]) == len(runs) for side in pool.data.values() for account in side)
            (output / "result.json").write_text(json.dumps({"result": "passed", "characters": len(names),
                "accounts": sum(len(side) for side in pool.data.values()), "prepared": prepare, "probe": probe,
                "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest()}, indent=2))
        finally:
            server.stop()
            if server.output_path.exists():
                (output / "server.out").write_bytes(server.output_path.read_bytes())
            shutil.copytree(runtime / "logs", output / "server-logs", dirs_exist_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prepare", action="store_true", help="Verify one fully equipped/spell-ready setup using real object prototypes")
    parser.add_argument("--probe", action="store_true", help="Short four-PC preparation diagnostic; not full-party acceptance")
    args = parser.parse_args()
    (journey.ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
    subprocess.run(["python3", "tests/async/test_flatfile_player_repository.py", "--build-inspector",
                    str(journey.INSPECTOR)], cwd=journey.ROOT, check=True, timeout=180)
    run(args.binary.resolve(), args.output.resolve(), args.prepare or args.probe, args.probe)
