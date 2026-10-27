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
import subprocess
import sys
import tempfile

import test_flatfile_combat_journey as journey
from run_battleprep_journey import configure
from run_item_pilot_journey import Server

sys.path.insert(0, str(journey.ROOT / "scripts"))
import run_racewar_battle as battle


async def provision(server, pool, directory, room=None):
    staff = await battle.Client.connect("127.0.0.1", server.port, "controller", directory)
    clients = {}
    try:
        await battle.staff_login(staff, {"account": journey.ACCOUNT, "password": journey.PASSWORD,
                                        "character": journey.CHARACTER})
        captured_room = await battle.current_room(staff)
        clients, rows, caps = await battle.connect_roster("127.0.0.1", server.port, pool, directory)
        print(f"Connected full rosters: {caps}", flush=True)
        await battle.place_groups(staff, clients, rows, caps, captured_room if room is None else room)
        summary = {"caps": caps, "room": captured_room if room is None else room, "rows": rows,
                   "groups": {side: clients[next(row["name"] for row in rows if row["side"] == side and row["index"] == 0)].gmcp["Group.Status"]
                              for side in battle.ROSTERS}}
        (Path(directory) / "summary.json").write_text(json.dumps(summary, indent=2))
        for row in rows:
            await clients[row["name"]].command("save", expected=f"Save complete for {row['name']}.")
        return summary
    finally:
        await asyncio.gather(*(client.close() for client in clients.values()), return_exceptions=True)
        await staff.close()


def run(binary, output):
    output.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix="racewar-provision-", dir=journey.ROOT / "bin/tests") as directory:
        root = Path(directory)
        runtime, state = root / "runtime", root / "state"
        runtime.mkdir(); state.mkdir(mode=0o700); (state / "domains").mkdir(mode=0o700)
        configure(runtime)
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
            for match, room in ((1, None), (2, 1200)):
                server.start()
                run_dir = output / f"match-{match}"
                run_dir.mkdir()
                summary = asyncio.run(provision(server, pool, run_dir, room))
                new_names = {row["name"] for row in summary["rows"]}
                assert not names & new_names
                names |= new_names
                assert summary["caps"] == {"good": 20, "evil": 20}, summary["caps"]
                assert len(new_names) == 40
                print(f"Match {match}: two full real-PC groups placed in room {summary['room']}", flush=True)
                server.stop()
                assert server.process.returncode == 0
            assert len(pool.data["good"]) == len(pool.data["evil"]) == 20
            assert all(len(account["characters"]) == 2 for side in pool.data.values() for account in side)
            (output / "result.json").write_text(json.dumps({"result": "passed", "characters": 80,
                "accounts": 40, "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest()}, indent=2))
        finally:
            server.stop()
            if server.output_path.exists():
                (output / "server.out").write_bytes(server.output_path.read_bytes())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    (journey.ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
    subprocess.run(["python3", "tests/async/test_flatfile_player_repository.py", "--build-inspector",
                    str(journey.INSPECTOR)], cwd=journey.ROOT, check=True, timeout=180)
    run(args.binary.resolve(), args.output.resolve())
