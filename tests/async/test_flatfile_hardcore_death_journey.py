#!/usr/bin/env python3
"""Prove Hardcore's third counted death through real flat-file save and restart.

The synthetic authority includes the empty catalogs required by permanent
character deletion, which the minimal-world boot deliberately skips.
"""

import argparse
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time

import test_flatfile_combat_journey as journey

ROOT = journey.ROOT


def run(binary):
    with tempfile.TemporaryDirectory(prefix="flatfile-hardcore-", dir=ROOT / "bin/tests") as directory:
        root = Path(directory)
        runtime, state = root / "runtime", root / "state"
        runtime.mkdir()
        state.mkdir(mode=0o700)
        (state / "domains").mkdir(mode=0o700)
        subprocess.run([str(journey.INSPECTOR), str(state), "seed-hardcore"], check=True)
        journey.make_fixture(runtime)
        journey.generate_certificate(runtime)
        (runtime / "lib/information/hardcore_hall_of_fame").write_text("0\n")
        (runtime / "logs/log").mkdir(parents=True)
        (runtime / "journals/critical").mkdir(parents=True, mode=0o700)
        plain, tls, websocket = journey.available_ports()
        environment = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "ENVIRONMENT": "local", "PERSISTENCE_MODE": "flatfile-primary",
            "FLATFILE_STATE_DIR": str(state),
            "CRITICAL_COMMAND_JOURNAL_DIR": str(runtime / "journals/critical"),
            "LISTEN_ADDRESS": "127.0.0.1", "DURIS_TLS_PORT": str(tls),
            "DURIS_WEBSOCKET_LISTEN_ADDRESS": "127.0.0.1",
            "DURIS_WEBSOCKET_PORT": str(websocket),
            "REDIS": "FALSE", "CHAOS_MUD": "FALSE",
        }
        if "LD_LIBRARY_PATH" in os.environ:
            environment["LD_LIBRARY_PATH"] = os.environ["LD_LIBRARY_PATH"]
        output_path = runtime / "server.out"
        process = client = None
        with output_path.open("w") as output:
            def boot():
                offset = output_path.stat().st_size
                proc = subprocess.Popen(
                    [str(binary), "--minimal", "-s", "-d", str(runtime), str(plain)],
                    cwd=runtime, env=environment, stdout=output, stderr=subprocess.STDOUT,
                )
                deadline = time.monotonic() + 120
                while b"Entering game loop." not in output_path.read_bytes()[offset:]:
                    if proc.poll() is not None or time.monotonic() > deadline:
                        proc.terminate() if proc.poll() is None else None
                        proc.wait(timeout=10)
                        raise AssertionError("flat-file Hardcore fixture failed to boot")
                    time.sleep(0.1)
                return proc

            def stop():
                process.send_signal(signal.SIGTERM)
                process.wait(timeout=30)
                assert process.returncode == 0, "Hardcore fixture did not stop normally"

            def assert_deaths(expected):
                deadline = time.monotonic() + 20
                while journey.inspect_authority(state)["death_count"] != expected:
                    assert time.monotonic() < deadline, "counted death was not saved"
                    time.sleep(0.1)

            def assert_empty_account():
                client.send("1")
                client.expect("doesn't have any characters (0/")

            try:
                process = boot()
                client = journey.MudClient(plain)
                journey.create_character(client, hardcore=True)
                client.send("save")
                client.expect("Save complete for " + journey.CHARACTER + ".")
                assert_deaths(0)
                for death in range(1, 4):
                    start = len(client.transcript)
                    client.send("suicide")
                    client.expect("Please confirm that you wish to do this!")
                    client.send("yes")
                    client.expect("ACCOUNT MENU", timeout=30)
                    client.expect("Please select an option")
                    result = client.transcript[start:].decode(errors="replace")
                    if death == 3:
                        assert "Your character has been permanently deleted." in result
                        assert_empty_account()
                        assert not (state / "players/1.snapshot").exists()
                    else:
                        assert "permanently deleted" not in result, f"death {death} was final"
                        assert_deaths(death)
                    client.send("0")
                    client.close()
                    client = None
                    if death == 2:
                        stop()
                        process = boot()
                    if death < 3:
                        client = journey.reconnect_character(plain)
                        assert_deaths(death)
                    print(f"flat-file Hardcore death {death}: {'deleted' if death == 3 else 'reloaded'}",
                          flush=True)

                stop()
                process = boot()
                assert not (state / "players/1.snapshot").exists(), "deleted snapshot returned"
                client = journey.MudClient(plain)
                prompt, _ = client.expect_any(("term type", "account name"))
                if prompt == "term type":
                    client.send("9")
                    client.expect("account name")
                client.send(journey.ACCOUNT)
                client.expect("enter your password")
                client.send(journey.PASSWORD)
                client.expect("PRESS RETURN")
                client.send("")
                client.expect("Please select an option")
                assert_empty_account()
                client.close()
                client = None
                stop()
            except Exception as error:
                raise AssertionError(
                    str(error) + "\n" + output_path.read_text(errors="replace")[-8000:]
                    + "\n" + journey.runtime_logs(runtime)
                ) from error
            finally:
                if client:
                    client.close()
                if process and process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=10)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", type=Path)
    args = parser.parse_args()
    (ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
    subprocess.run(["python3", "tests/async/test_flatfile_player_repository.py",
                    "--build-inspector", str(journey.INSPECTOR)], cwd=ROOT, check=True)
    with tempfile.TemporaryDirectory(prefix="hardcore-build-", dir=ROOT / "bin/tests") as directory:
        binary = args.server.resolve() if args.server else journey.build_flatfile_server(Path(directory))
        run(binary)
    print("flat-file Hardcore third counted death and restart journey passed")
