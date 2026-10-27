#!/usr/bin/env python3
"""Create two full real-PC groups, place them, then reuse the account pool.

This tests provisioning on a disposable native server. Gear and combat belong
to the later end-to-end battle journey; they are not claimed by this test.
"""
import argparse
import asyncio
import hashlib
import json
import os
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


async def battle_cli(server, output, run_dir, room, duration, operator_stop):
    """Drive the delivered CLI and watch through a separate ordinary Telnet client."""
    config = output / "controller.json"
    config.write_text(json.dumps({"host": "127.0.0.1", "port": server.port,
        "staff": {"account": journey.ACCOUNT, "password": journey.PASSWORD, "character": journey.CHARACTER},
        "registration_email": "racewar@example.invalid"}))
    os.chmod(config, 0o600)
    observer_dir = output / f"observer-{run_dir.name}"
    observer_dir.mkdir()
    observer = await battle.Client.connect("127.0.0.1", server.port, "observer", observer_dir)
    process = None
    stopper = None
    sampler = None
    samples = []
    async def sample_server():
        # Fixture-only diagnostics; the delivered runner still works remotely.
        clock_ticks = os.sysconf("SC_CLK_TCK")
        while server.process.poll() is None:
            fields = Path(f"/proc/{server.process.pid}/stat").read_text().rsplit(") ", 1)[1].split()
            status = Path(f"/proc/{server.process.pid}/status").read_text()
            rss = next(int(line.split()[1]) for line in status.splitlines() if line.startswith("VmRSS:"))
            samples.append({"monotonic_seconds": asyncio.get_running_loop().time(),
                            "cpu_seconds": (int(fields[11]) + int(fields[12])) / clock_ticks,
                            "rss_kib": rss, "threads": int(fields[17])})
            await asyncio.sleep(1)
    try:
        await battle.staff_login(observer, {"account": "Raceobserver", "password": journey.PASSWORD,
                                            "character": "Raceobserver"})
        if room is not None:
            await observer.command(f"goto {room}")
        args = [sys.executable, str(journey.ROOT / "scripts/run_racewar_battle.py"),
                "--config", str(config), "--accounts", str(output / "accounts.json"),
                "--output", str(run_dir), "--duration", str(duration)]
        if room is not None:
            args += ["--room", str(room)]
        with (output / f"{run_dir.name}-operator.log").open("w") as log:
            process = await asyncio.create_subprocess_exec(*args, cwd=journey.ROOT,
                stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=log)
            async def request_stop():
                await asyncio.sleep(30)
                if process.returncode is None:
                    process.stdin.write(b"stop\n")
                    await process.stdin.drain()
            while line := await asyncio.wait_for(process.stdout.readline(), 1200):
                text = line.decode()
                log.write(text); log.flush()
                print(text, end="", flush=True)
                if text.startswith("READY:"):
                    # Readiness never starts a fight by itself. The acceptance
                    # driver acts as the human operator, after observing the gate.
                    await asyncio.sleep(1)
                    assert process.returncode is None
                    sampler = asyncio.create_task(sample_server())
                    process.stdin.write(b"status\nstart\n")
                    await process.stdin.drain()
                    if operator_stop:
                        stopper = asyncio.create_task(request_stop())
            code = await process.wait()
            assert code == 0, f"Operator exited {code}; see {log.name}"
        summary = json.loads((run_dir / "summary.json").read_text())
        assert summary["stop"]["confirmed"], summary["stop"]
        assert sum(row["damage_events"] for row in summary["rows"]) > 0
        assert sum(row["actions"]["spells_completed"] for row in summary["rows"]) > 0
        summary["groups"] = json.loads((run_dir / "ready.json").read_text())["groups"]
        return summary
    finally:
        if sampler:
            sampler.cancel()
            await asyncio.gather(sampler, return_exceptions=True)
            (output / f"{run_dir.name}-server-samples.json").write_text(json.dumps(samples, indent=2))
        if stopper:
            stopper.cancel()
            await asyncio.gather(stopper, return_exceptions=True)
        if process and process.returncode is None:
            process.stdin.write(b"stop\n")
            await process.stdin.drain()
            await asyncio.wait_for(process.wait(), 120)
        await observer.close()


async def verify_controls(staff, clients, rows, directory):
    """Small real-socket control proof; this is not full-party acceptance."""
    enemy, fighter, bystander, caster = [clients[row["name"]] for row in rows]
    for player in clients.values():
        hello = b'Core.Hello {"client":"racewar-controls","commandReceipts":true}'
        player.writer.write(bytes((battle.IAC, battle.SB, battle.GMCP)) + hello + bytes((battle.IAC, battle.SE)))
        await player.writer.drain()
        await player.wait_for(lambda: player.gmcp.get("Char.Input") is not None, "negotiating receipts")
        before = player.gmcp["Char.Input"]["sequence"]
        await player.command("look")
        await player.wait_for(lambda: player.gmcp["Char.Input"]["sequence"] == before + 1,
                              "confirming look dequeue")
        assert player.gmcp["Char.Input"]["command"] == "look"
    selectors = {p.label: next(entry["target"] for entry in p.gmcp["Room.Info"]["players"]
                              if entry["name"] == enemy.label) for p in (fighter, caster)}
    assert all(selectors.values()), selectors
    await caster.send(f"cast 'prismatic ray' {selectors[caster.label]}")
    await caster.expect("You start chanting")
    await fighter.send(f"kill {selectors[fighter.label]}")
    await fighter.wait_for(lambda: fighter.gmcp.get("Char.Vitals", {}).get("fighting") == enemy.label,
                           "starting native melee")
    # Queue a second action behind native lag, then stop the exact participants.
    await fighter.send(f"kill {selectors[fighter.label]}")
    selected = " ".join(p.label for p in (enemy, fighter, caster))
    stopped = await staff.command(f"battleprep stop {selected}", expected=f"{caster.label} quiet.")
    assert all(f"{p.label} quiet.".casefold() in stopped.casefold() for p in (enemy, fighter, caster)), stopped
    await caster.expect("You abort your spell")
    await asyncio.sleep(6)
    status = await staff.command(f"battleprep status {selected}", expected=f"{caster.label} quiet.")
    assert all(f"{p.label} quiet.".casefold() in status.casefold() for p in (enemy, fighter, caster)), status
    assert "You complete your spell" not in caster.pending
    observed = await bystander.command("score", expected="Hit points:")
    assert "Pos: standing" in observed, observed
    for player in (enemy, fighter, caster):
        await player.command("save", expected=f"Save complete for {player.label}.")
    receipt = {"result": "passed", "selectors": selectors, "selected": selected.split(),
               "bystander": bystander.label, "settle_seconds": 6,
               "verified": ["opt-in dequeue receipts", "legal mortal racewar targets", "native melee",
                            "cast abort", "queued action stop", "quiet settling", "bystander stays standing",
                            "acknowledged saves"]}
    (Path(directory) / "controls.json").write_text(json.dumps(receipt, indent=2))
    print("Native battle controls passed", flush=True)


async def provision(server, pool, directory, room=None, prepare=False, probe=False, controls=False, actions=False):
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
            if actions:
                cases = [("good", "Human", "Paladin"), ("good", "Centaur", "Ranger"),
                         ("good", "Grey Elf", "Druid"), ("evil", "Kobold", "Bard")]
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
        if controls:
            await verify_controls(staff, clients, rows, directory)
        if actions:
            await battle.prepare_actions(staff, clients, rows, directory)
            bard = clients[next(row["name"] for row in rows if battle.normalized(row["class"]) == "bard")]
            output = await bard.action("play healing")
            assert "You start playing" in output, output
            if "You sing a song to heal all wounds" not in output:
                await bard.expect("You sing a song to heal all wounds", timeout=30)
            stopped = await battle.stop_fighters(staff, rows)
            assert stopped["confirmed"], stopped
            (Path(directory) / "actions.json").write_text(json.dumps({"result": "passed", "stop": stopped}))
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


def run(binary, output, prepare=False, probe=False, controls=False, combat=False, duration=90, runs=2, actions=False):
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
            if combat:
                observer = journey.MudClient(server.port)
                try:
                    journey.create_character(observer, account="Raceobserver", character="Raceobserver",
                                             email="raceobserver@example.invalid")
                    observer.send("save"); observer.expect("Save complete for Raceobserver.")
                    observer.send("quit"); observer.expect("ACCOUNT MENU")
                finally:
                    observer.close()
            server.stop()
            journey.make_overlord(state, journey.CHARACTER)
            if combat:
                journey.make_overlord(state, "Raceobserver")
            pool = battle.AccountPool(output / "accounts.json", "racewar@example.invalid")
            names = set()
            matches = ((1, None), (2, 1200))[:runs] if combat else (((1, None),) if prepare else ((1, None), (2, 1200)))
            for match, room in matches:
                server.start()
                run_dir = output / f"match-{match}"
                if combat:
                    summary = asyncio.run(battle_cli(server, output, run_dir, room, duration, match == 2))
                    pool = battle.AccountPool(output / "accounts.json", "racewar@example.invalid")
                else:
                    run_dir.mkdir()
                    summary = asyncio.run(provision(server, pool, run_dir, room, prepare, probe, controls, actions))
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
            assert all(len(account["characters"]) == len(matches) for side in pool.data.values() for account in side)
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
    parser.add_argument("--controls", action="store_true", help="Four-PC native targeting/receipts/stop proof")
    parser.add_argument("--battle", action="store_true", help="Exercise the delivered operator CLI with full parties and a separate observer")
    parser.add_argument("--actions", action="store_true", help="Four-build pre-fight buff and bard support diagnostic")
    parser.add_argument("--duration", type=float, default=90)
    parser.add_argument("--runs", type=int, choices=(1, 2), default=2, help="Two full matches are required for acceptance")
    args = parser.parse_args()
    (journey.ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
    subprocess.run(["python3", "tests/async/test_flatfile_player_repository.py", "--build-inspector",
                    str(journey.INSPECTOR)], cwd=journey.ROOT, check=True, timeout=180)
    run(args.binary.resolve(), args.output.resolve(), args.prepare or args.probe or args.controls or args.battle or args.actions,
        args.probe or args.controls or args.actions, args.controls, args.battle, args.duration, args.runs, args.actions)
