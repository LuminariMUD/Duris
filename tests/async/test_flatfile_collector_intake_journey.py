#!/usr/bin/env python3
"""The collector takes an antiquity from a player's corpse (persistence reset Phase 3 step 6).

The death enters collector intake with the corpse's save; after the collection delay the
collector's maintenance takes the eligible item out of the live corpse. Coins are never
collected and stay.
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
COLLECTOR_PROPERTIES = {
    "collector.enabled": "1.000",
    "collector.collection.delay.seconds": "2.000",
    "collector.sale.delay.seconds": "3.000",
    "collector.maintenance.interval.seconds": "1.000",
}


def enable_collector(run_root: pathlib.Path) -> None:
    path = run_root / "lib/duris.properties"
    lines = path.read_text().splitlines()
    for key, value in COLLECTOR_PROPERTIES.items():
        index = next(i for i, line in enumerate(lines) if line.startswith(key + "="))
        lines[index] = f"{key}={value}"
    path.write_text("\n".join(lines) + "\n")


def wait_for_collection(port: int, *login: str) -> None:
    client = journey.reconnect_character(port, *login)
    try:
        deadline = time.monotonic() + 60
        for check in range(1000):
            # The say marks where the corpse's listing ends.
            client.send(f"look in {journey.CHARACTER}")
            client.send(f"say collector check {check}")
            corpse = client.expect(f"collector check {check}", timeout=10)
            journey.require("copper coin" in corpse,
                            "the collector took coins from the corpse:\n" + corpse)
            if "a banana" not in corpse:
                break
            journey.require(time.monotonic() < deadline,
                            "the collector never took the banana from the corpse")
            time.sleep(1)
        client.send("quit")
        client.expect("ACCOUNT MENU", timeout=30)
        client.send("0")
    finally:
        client.close()


def run(binary: pathlib.Path) -> None:
    with tempfile.TemporaryDirectory(prefix="duris-collector-state-") as state_tmp, \
            tempfile.TemporaryDirectory(prefix="duris-collector-run-") as run_tmp:
        state_root = pathlib.Path(state_tmp)
        run_root = pathlib.Path(run_tmp)
        state_root.chmod(0o700)
        (state_root / "domains").mkdir(mode=0o700)
        subprocess.run([str(journey.INSPECTOR), str(state_root), "seed-combat"], check=True)
        (run_root / "logs/log").mkdir(parents=True)
        journey.make_fixture(run_root)
        enable_collector(run_root)
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
        output_path = run_root / "server.out"
        with output_path.open("w", encoding="utf-8") as output:
            process = subprocess.Popen(
                [str(binary), "--minimal", "-s", "-d", str(run_root), str(plain_port)],
                cwd=run_root, env=environment, text=True, stdout=output,
                stderr=subprocess.STDOUT)
            try:
                deadline = time.monotonic() + 120
                while "Entering game loop." not in output_path.read_text(errors="replace"):
                    journey.require(process.poll() is None and time.monotonic() < deadline,
                                    "server did not boot:\n" +
                                    output_path.read_text(errors="replace")[-8000:])
                    time.sleep(0.1)
                client = journey.MudClient(plain_port)
                journey.create_character(client)
                client.send("toggle boon")
                client.expect("You will no longer be affected by boons.")
                journey.complete_npc_combat_journey(client)
                client.close()
                journey.verify_npc_loot_and_die(plain_port)
                wait_for_collection(plain_port, "You rejoin the land of the living")
                process.send_signal(signal.SIGTERM)
                process.wait(timeout=30)
                server_output = output_path.read_text(errors="replace")
                journey.require("Normal termination of game." in server_output,
                                "the server did not stop normally:\n" + server_output[-8000:])
                journey.require("Collector death intake refused" not in server_output,
                                "the corpse save refused the death:\n" + server_output[-8000:])
            except Exception:
                print(output_path.read_text(errors="replace")[-8000:])
                raise
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=5)


if __name__ == "__main__":
    subprocess.run(["python3", "tests/async/test_flatfile_player_repository.py",
                    "--build-inspector", str(journey.INSPECTOR)], cwd=ROOT, check=True,
                   timeout=180)
    with tempfile.TemporaryDirectory(prefix=f"flatfile-collector-{os.getpid()}-",
                                     dir=ROOT / "bin/tests") as build_tmp:
        run(journey.build_flatfile_server(pathlib.Path(build_tmp)))
    print("flat-file collector intake journey passed")
