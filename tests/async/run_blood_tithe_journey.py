#!/usr/bin/env python3
"""Cast Blood Tithe on a disposable real server and watch it charge and fade.

A staff character casts the spell, groups a second player, and is beaten on by a
fixture brute. Score must show the tithe charging while the brute lands hits and
fading once the fight ends, while the groupmate's attacks run through the bonus.

usage: run_blood_tithe_journey.py /path/to/flatfile/dms_new
"""

from pathlib import Path
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

import test_flatfile_combat_journey as journey
from run_divine_refusal_journey import drain, require

BRUTE = """#22804
tithe brute~
a tithe brute~
A tithe brute stands here, eager to test a blood oath.
~
~
10 0 0 0 0 0 0 0 S
PH 0 1 -1
50 0 0 200d1+20000 1d1+1
0.0.0.0 0
8 8 0
"""
TITHE = re.compile(r"Blood Tithe \(\+([0-9.]+)% group damage\)")


def tithe_percent(client: journey.MudClient) -> float:
    client.send("score")
    output = client.expect("Pos:", timeout=20) + drain(client)
    match = TITHE.search(output)
    require(match is not None, f"score does not show Blood Tithe:\n{output[-3000:]}")
    return float(match.group(1))


def run(server_binary: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="blood-tithe-") as temporary:
        root = Path(temporary)
        state = root / "state"
        runtime = root / "runtime"
        state.mkdir(mode=0o700)
        (state / "domains").mkdir(mode=0o700)
        runtime.mkdir()
        (runtime / "logs/log").mkdir(parents=True)
        journey.make_fixture(runtime)
        journey.generate_certificate(runtime)
        mobiles = runtime / "areas_mini/mini.mob"
        text = mobiles.read_text(encoding="utf-8")
        require(text.count("$~") == 1, "minimal mobile terminator changed")
        mobiles.write_text(text.replace("$~", BRUTE + "$~"), encoding="utf-8")
        (runtime / "journals/critical").mkdir(parents=True, mode=0o700)
        (runtime / "bin/server").mkdir(parents=True)
        for name in ("dms", "dms_new"):
            shutil.copy2(server_binary, runtime / "bin/server" / name)
        subprocess.run([str(journey.INSPECTOR), str(state), "seed-combat"], check=True)

        port, tls_port, websocket_port = journey.available_ports()
        environment = dict(
            PATH=os.environ.get("PATH", "/usr/bin:/bin"),
            ENVIRONMENT="local",
            PERSISTENCE_MODE="flatfile-primary",
            FLATFILE_STATE_DIR=str(state),
            CRITICAL_COMMAND_JOURNAL_DIR=str(runtime / "journals/critical"),
            REDIS="FALSE",
            CHAOS_MUD="FALSE",
            LISTEN_ADDRESS="127.0.0.1",
            DURIS_TLS_PORT=str(tls_port),
            DURIS_WEBSOCKET_PORT=str(websocket_port),
            DURIS_WEBSOCKET_LISTEN_ADDRESS="127.0.0.1",
        )
        for loader_setting in ("LD_LIBRARY_PATH", "LD_PRELOAD"):
            if loader_setting in os.environ:
                environment[loader_setting] = os.environ[loader_setting]
        process = None
        clients: list[journey.MudClient] = []

        def boot() -> None:
            nonlocal process
            output = (runtime / "server.out").open("w", encoding="utf-8")
            process = subprocess.Popen(
                [str(runtime / "bin/server/dms"), "--minimal", "-s", str(port)],
                cwd=runtime, env=environment, stdout=output, stderr=subprocess.STDOUT,
            )
            deadline = time.monotonic() + 90
            while "Entering game loop." not in (runtime / "server.out").read_text(
                encoding="utf-8", errors="replace"
            ):
                require(process.poll() is None, "server exited during boot")
                require(time.monotonic() < deadline, "server boot timed out")
                time.sleep(0.1)

        def stop() -> None:
            nonlocal process
            while clients:
                clients.pop().close()
            if process and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            process = None

        try:
            boot()
            staff = journey.MudClient(port)
            clients.append(staff)
            journey.create_character(staff)
            staff.send("save")
            staff.expect("Save complete for Taverek.")
            staff.send("quit")
            staff.expect("ACCOUNT MENU", timeout=30)
            stop()
            journey.make_overlord(state, "Taverek")

            boot()
            staff = journey.reconnect_character(port)
            clients.append(staff)
            mate = journey.MudClient(port)
            clients.append(mate)
            journey.create_character(mate, account="Tithemate", character="Tithemate",
                                     email="tithe-journey@example.invalid")
            drain(mate)
            drain(staff)

            staff.send("vis 0")  # staff log in wizinvis, and consent needs a visible target
            drain(staff)
            mate.send("consent Taverek")
            drain(mate)
            staff.send("group Tithemate")
            grouped = staff.expect("is now a member of your group", timeout=15)
            require("Tithemate" in grouped, grouped)

            staff.send("cast 'blood tithe'")
            staff.expect("You pledge your blood", timeout=30)
            require(tithe_percent(staff) == 0.0, "a fresh tithe should start empty")

            staff.send("load mob 22804")
            drain(staff)
            staff.send("force brute kill Taverek")
            drain(staff, 2.0)
            mate.send("kill brute")
            drain(mate)

            peak = 0.0
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline and peak <= 0:
                time.sleep(4)
                peak = tithe_percent(staff)
            require(peak > 0, "the brute's hits never charged the tithe")
            require(peak <= 12.0, f"bonus {peak}% exceeds the 12% ceiling")
            print(f"PASS charged while hit: score shows +{peak}% group damage", flush=True)

            staff.send("purge brute")
            drain(staff, 1.0)
            time.sleep(14)  # three combat rounds and change
            faded = tithe_percent(staff)
            require(faded < peak, f"tithe did not fade after the fight ({peak} -> {faded})")
            print(f"PASS faded after the fight: +{peak}% -> +{faded}%", flush=True)

            log = (runtime / "server.out").read_text(errors="replace")
            require("SIGSEGV" not in log and "Segmentation" not in log, log[-4000:])
        except Exception:
            print((runtime / "server.out").read_text(errors="replace")[-8000:])
            print(journey.runtime_logs(runtime)[-8000:])
            for client in clients:
                print(client.transcript.decode(errors="replace")[-6000:])
            raise
        finally:
            stop()


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    binary = Path(sys.argv[1]).resolve()
    require(binary.is_file(), f"server binary does not exist: {binary}")
    journey.INSPECTOR.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["python3", "tests/async/test_flatfile_player_repository.py",
         "--build-inspector", str(journey.INSPECTOR)],
        cwd=journey.ROOT, check=True, timeout=180,
    )
    run(binary)
    print("Blood Tithe live journey passed.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
