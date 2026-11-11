#!/usr/bin/env python3
"""Verify the staff book of files (mini object 1278, specials on) reads every topic, whether or not its file exists yet.

Run with with_disposable_mariadb.sh; uses private world fixtures, never .env.
"""
import argparse
from pathlib import Path
import signal
import subprocess
import tempfile
import time

import test_mariadb_combat_journey as journey
from test_flight_network_journey import authority, command

ROOT = journey.ROOT
STAFF, ACCOUNT = "Bookwarden", "Bookstaff"
TOPICS = {
    "bugs": "lib/reports/bugs",
    "typos": "lib/reports/typos",
    "ideas": "lib/reports/ideas",
    "cheats": "lib/reports/cheats",
    "cheaters": "lib/reports/cheaters",
    "donations": "logs/log/donation",
}


def run(server):
    (ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="book-of-files-", dir=ROOT / "bin/tests") as temporary:
        runtime = Path(temporary)
        journey.make_fixture(runtime)
        journey.generate_certificate(runtime)
        (runtime / "help").symlink_to(ROOT / "help", target_is_directory=True)
        (runtime / "logs/log").mkdir(parents=True)
        critical = runtime / "journals/critical"
        critical.mkdir(parents=True, mode=0o700)
        for path in TOPICS.values():
            (runtime / path).unlink(missing_ok=True)
        plain, tls, websocket = journey.available_ports()
        output_path = runtime / "server.out"
        process = client = None
        with authority("mariadb", runtime) as (env, sql), output_path.open("w") as output:
            env.update(CRITICAL_COMMAND_JOURNAL_DIR=str(critical), DURIS_TLS_PORT=str(tls),
                       DURIS_WEBSOCKET_PORT=str(websocket))

            def boot():
                nonlocal process
                offset = output_path.stat().st_size
                process = subprocess.Popen(
                    [str(server), "--minimal", "-d", str(runtime), str(plain)],
                    cwd=runtime, env=env, stdout=output, stderr=subprocess.STDOUT)
                deadline = time.monotonic() + 120
                while b"Entering game loop." not in output_path.read_bytes()[offset:]:
                    assert process.poll() is None and time.monotonic() < deadline, journey.runtime_logs(runtime)
                    time.sleep(.1)

            def stop():
                nonlocal client
                if client:
                    client.close()
                    client = None
                if process is not None and process.poll() is None:
                    process.send_signal(signal.SIGTERM)
                    process.wait(timeout=60)
                    assert process.returncode == 0, journey.runtime_logs(runtime)

            try:
                boot()
                client = journey.MudClient(plain)
                journey.create_character(client, account=ACCOUNT, character=STAFF,
                                         email="book@example.invalid")
                client.send("save")
                client.expect("Saving " + STAFF + ".", timeout=30)
                stop()
                sql(f"UPDATE player_data SET level=62,highest_level=62 WHERE name='{STAFF}'")
                boot()
                client = journey.reconnect_character(plain, expected_room=None,
                                                     account=ACCOUNT, character=STAFF)
                client.expect("Welcome to Duris", timeout=30)
                command(client, "toggle paging no")
                assert "created" in command(client, "load obj 1278").lower()
                usage = command(client, "read files")
                assert 'donations "logs/log/donation"' in usage, usage
                assert "changelog" not in usage, usage
                for topic, path in TOPICS.items():
                    response = command(client, "read " + topic)
                    assert "Nothing has been recorded there yet." in response, (topic, response)
                    (runtime / path).write_text(f"Entry for {topic}\n")
                    response = command(client, "read " + topic)
                    assert f"Entry for {topic}" in response, (topic, response)
                    assert "Could not open file." not in response, (topic, response)
                print("PASS: book of files describes live topics; missing and present files read cleanly")
            finally:
                stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", type=Path, default=ROOT / "bin/server/dms_new")
    args = parser.parse_args()
    run(args.server.resolve())
