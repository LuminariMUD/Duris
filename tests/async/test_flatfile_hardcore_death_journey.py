#!/usr/bin/env python3
"""Prove Hardcore's third counted death through a real MariaDB save and restart."""

import argparse
from pathlib import Path
import signal
import subprocess
import tempfile
import time

import test_flatfile_combat_journey as journey

ROOT = journey.ROOT


def run(binary):
    with tempfile.TemporaryDirectory(prefix="flatfile-hardcore-", dir=ROOT / "bin/tests") as directory, \
            journey.mariadb_authority() as (environment, sql):
        runtime = Path(directory) / "runtime"
        runtime.mkdir()
        journey.make_fixture(runtime)
        journey.generate_certificate(runtime)
        (runtime / "lib/information/hardcore_hall_of_fame").write_text("0\n")
        (runtime / "logs/log").mkdir(parents=True)
        (runtime / "journals/critical").mkdir(parents=True, mode=0o700)
        plain, tls, websocket = journey.available_ports()
        environment.update(CRITICAL_COMMAND_JOURNAL_DIR=str(runtime / "journals/critical"),
                           DURIS_TLS_PORT=str(tls), DURIS_WEBSOCKET_PORT=str(websocket))
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
                        raise AssertionError("Hardcore fixture failed to boot")
                    time.sleep(0.1)
                return proc

            def stop():
                process.send_signal(signal.SIGTERM)
                process.wait(timeout=30)
                assert process.returncode == 0, "Hardcore fixture did not stop normally"

            def assert_deaths(expected):
                deadline = time.monotonic() + 20
                while journey.inspect_authority(sql)["death_count"] != expected:
                    assert time.monotonic() < deadline, "counted death was not saved"
                    time.sleep(0.1)

            def assert_character_deleted():
                deadline = time.monotonic() + 20
                while sql(f"SELECT COUNT(*) FROM player_data WHERE name='{journey.CHARACTER}'") != "0":
                    assert time.monotonic() < deadline, "the deleted character's row remains"
                    time.sleep(0.1)

            def assert_empty_account():
                # SQL commit precedes its game-thread completion callback.
                deadline = time.monotonic() + 20
                while True:
                    client.send("1")
                    result, _ = client.expect_any(("doesn't have any characters (0/",
                                                   "Which character would you like to play?"))
                    if result == "doesn't have any characters (0/":
                        return
                    assert time.monotonic() < deadline, "deleted character remained selectable"
                    client.send("0")
                    client.expect("ACCOUNT MENU")
                    client.expect("Please select an option")
                    time.sleep(0.1)

            try:
                process = boot()
                client = journey.MudClient(plain)
                journey.create_character(client, hardcore=True)
                client.send("save")
                client.expect("Saving " + journey.CHARACTER + ".")
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
                        assert_character_deleted()
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
                    print(f"Hardcore death {death}: {'deleted' if death == 3 else 'reloaded'}",
                          flush=True)

                stop()
                process = boot()
                assert_character_deleted()
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
    parser.add_argument("--server", type=Path, required=True)
    args = parser.parse_args()
    (ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
    run(args.server.resolve())
    print("Hardcore third counted death and restart journey passed")
