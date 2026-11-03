#!/usr/bin/env python3
"""Survive four Hardcore deaths, restart, and permanently delete on death five.

Uses the real server and a newly created MariaDB schema. Run through
with_disposable_mariadb.sh; no checkout .env or existing schema is used.
"""

import argparse
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time
import uuid

import test_flatfile_combat_journey as journey

ROOT = journey.ROOT


def run(binary):
    database = "hardcore_death_test_" + uuid.uuid4().hex[:12]
    host = os.environ["TEST_DB_HOST"]
    assert host in ("127.0.0.1", "localhost"), "use a disposable loopback database"
    environment = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "ENVIRONMENT": "local", "PERSISTENCE_MODE": "mariadb-primary",
        "DB_HOST": host, "DB_PORT": os.environ.get("TEST_DB_PORT", "3306"),
        "DB_NAME": database, "DB_USER": os.environ["TEST_DB_USER"],
        "DB_PASSWD": os.environ["TEST_DB_PASSWORD"],
        "MYSQL_PWD": os.environ["TEST_DB_PASSWORD"],
        "DB_ALLOWED_TARGETS": host + "/" + database, "DB_TLS": "FALSE",
        "LISTEN_ADDRESS": "127.0.0.1", "DURIS_WEBSOCKET_LISTEN_ADDRESS": "127.0.0.1",
        "REDIS": "FALSE", "CHAOS_MUD": "FALSE",
    }
    if "LD_LIBRARY_PATH" in os.environ:
        environment["LD_LIBRARY_PATH"] = os.environ["LD_LIBRARY_PATH"]
    mysql = ["mysql", "--protocol=tcp", "-h", host, "-P", environment["DB_PORT"],
             "-u", environment["DB_USER"], "-N", "-B"]

    def sql(text, selected=True):
        return subprocess.check_output(mysql + ([database] if selected else []), input=text,
                                       text=True, env=environment).strip()

    def settle(query, expected):
        deadline = time.monotonic() + 20
        while int(sql(query)) != expected:
            assert time.monotonic() < deadline, "unexpected persisted state: " + query
            time.sleep(0.1)

    sql("CREATE DATABASE " + database + " CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci", False)
    try:
        sql((ROOT / "migrations/bootstrap_multithread_safe.sql").read_text())
        subprocess.run(["python3", "scripts/migration_runner.py", "adopt", "--kind", "fresh_bootstrap"],
                       cwd=ROOT, env=environment, check=True)
        subprocess.run(["python3", "scripts/migration_runner.py", "run"],
                       cwd=ROOT, env=environment, check=True)
        with tempfile.TemporaryDirectory(prefix="mysql-hardcore-death-", dir=ROOT / "bin/tests") as directory:
            runtime = Path(directory)
            journey.make_fixture(runtime)
            journey.generate_certificate(runtime)
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
                    client.expect("Save complete for " + journey.CHARACTER + ".")
                    pid = int(sql("SELECT pid FROM player_data WHERE name='" + journey.CHARACTER + "'"))
                    deaths = f"SELECT numb_deaths FROM player_data WHERE pid={pid}"
                    settle(deaths, 0)
                    for death in range(1, 6):
                        start = len(client.transcript)
                        client.send("suicide")
                        client.expect("Please confirm that you wish to do this!")
                        client.send("yes")
                        client.expect("ACCOUNT MENU", timeout=30)
                        client.expect("Please select an option")
                        result = client.transcript[start:].decode(errors="replace")
                        if death == 5:
                            assert "Your character has been permanently deleted." in result
                            settle(f"SELECT COUNT(*) FROM player_data WHERE pid={pid}", 0)
                            settle(f"SELECT COUNT(*) FROM account_characters WHERE pid={pid} AND deleted_at IS NULL", 0)
                            assert_empty_account()
                        else:
                            assert "permanently deleted" not in result, f"death {death} was final"
                            settle(deaths, death)
                        client.send("0")
                        client.close()
                        client = None
                        if death == 4:
                            stop()
                            process = boot()
                        if death < 5:
                            client = journey.reconnect_character(plain)
                            settle(deaths, death)
                        print(f"MariaDB Hardcore death {death}: {'deleted' if death == 5 else 'reloaded'}",
                              flush=True)

                    stop()
                    process = boot()
                    settle(f"SELECT COUNT(*) FROM player_data WHERE pid={pid}", 0)
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
    finally:
        sql("DROP DATABASE " + database, False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", required=True, type=Path)
    args = parser.parse_args()
    (ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
    run(args.server.resolve())
    print("MariaDB Hardcore fifth counted death and restart journey passed")
