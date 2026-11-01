#!/usr/bin/env python3
"""Issue #530: rested spell changes survive periodic checkpoints and crashes.

Requires a native MariaDB --server and TEST_DB_HOST=127.0.0.1, TEST_DB_USER,
TEST_DB_PASSWORD (optional TEST_DB_PORT). Creates and drops only its own schema;
never reads checkout .env. Uses real casts, periodic saves, SIGKILL and login.
"""

import argparse
import os
from pathlib import Path
import re
import signal
import subprocess
import tempfile
import time
import uuid

import test_flatfile_combat_journey as journey

ROOT = Path(__file__).resolve().parents[2]
RECIPIENT = "Veralis"
RECIPIENT_ACCOUNT = "Restedacct"
RESTED = 2107
WELLRESTED = 2108
FLAGS = 1540  # AFFTYPE_PERM | AFFTYPE_NODISPEL | AFFTYPE_OFFLINE


def run(server):
    host = os.environ["TEST_DB_HOST"]
    assert host == "127.0.0.1", "requires a disposable loopback database"
    database = "rested_checkpoint_" + uuid.uuid4().hex[:12]
    environment = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "ENVIRONMENT": "local", "DB_HOST": host,
        "DB_PORT": os.environ.get("TEST_DB_PORT", "3306"),
        "DB_NAME": database, "DB_USER": os.environ["TEST_DB_USER"],
        "DB_PASSWD": os.environ["TEST_DB_PASSWORD"],
        "MYSQL_PWD": os.environ["TEST_DB_PASSWORD"],
        "DB_ALLOWED_TARGETS": host + "/" + database,
        "PERSISTENCE_MODE": "mariadb-primary", "DB_TLS": "FALSE",
        "REDIS": "FALSE", "CHAOS_MUD": "FALSE",
        "LISTEN_ADDRESS": host, "DURIS_WEBSOCKET_LISTEN_ADDRESS": host,
    }
    if "LD_LIBRARY_PATH" in os.environ:
        environment["LD_LIBRARY_PATH"] = os.environ["LD_LIBRARY_PATH"]
    mysql = ["mysql", "--protocol=tcp", "-h", host, "-P", environment["DB_PORT"],
             "-u", environment["DB_USER"], "-N", "-B"]

    def sql(text, selected=True):
        return subprocess.check_output(mysql + ([database] if selected else []),
                                       input=text, text=True, env=environment).strip()

    sql("CREATE DATABASE " + database + " CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci", False)
    try:
        sql((ROOT / "migrations/bootstrap_multithread_safe.sql").read_text())
        for args in (["adopt", "--kind", "fresh_bootstrap"], ["run"]):
            result = subprocess.run(["python3", "scripts/migration_runner.py", *args],
                                    cwd=ROOT, env=environment, capture_output=True, text=True)
            assert result.returncode == 0, result.stdout + result.stderr
        (ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="rested-checkpoint-", dir=ROOT / "bin/tests") as temporary:
            runtime = Path(temporary)
            journey.make_fixture(runtime)
            # Quiet inn: no combat resets; one extra room keeps the arena inside
            # the world's valid room range for ordinary rent.
            zone = runtime / "areas_mini/mini.zon"
            zone.write_text(re.sub(r"^[MG] .*\n", "", zone.read_text(), flags=re.M))
            world = runtime / "areas_mini/mini.wld"
            world.write_text(world.read_text().replace(
                "1 0 0\nS\n$~", "1 524288 0\nS\n#22801\nBoundary room~\nUnused.\n~\n1 0 0\nS\n$~"))
            journey.generate_certificate(runtime)
            (runtime / "logs/log").mkdir(parents=True)
            (runtime / "journals/critical").mkdir(parents=True, mode=0o700)
            plain, tls, websocket = journey.available_ports()
            environment.update(CRITICAL_COMMAND_JOURNAL_DIR=str(runtime / "journals/critical"),
                               DURIS_TLS_PORT=str(tls), DURIS_WEBSOCKET_PORT=str(websocket))
            output_path = runtime / "server.out"
            process = caster = recipient = None
            sequence = 0
            pid = None

            def boot():
                nonlocal process
                offset = output_path.stat().st_size if output_path.exists() else 0
                with output_path.open("a") as output:
                    process = subprocess.Popen(
                        [str(server), "--minimal", "-d", str(runtime), str(plain)],
                        cwd=runtime, env=environment, stdout=output, stderr=subprocess.STDOUT)
                deadline = time.monotonic() + 90
                while b"Entering game loop." not in output_path.read_bytes()[offset:]:
                    assert process.poll() is None and time.monotonic() < deadline, \
                        output_path.read_text(errors="replace")[-8000:] + journey.runtime_logs(runtime)
                    time.sleep(.1)

            def stop(crash=False):
                nonlocal process, caster, recipient
                if process is not None:
                    if process.poll() is None:
                        process.send_signal(signal.SIGKILL if crash else signal.SIGTERM)
                        process.wait(timeout=30)
                        assert process.returncode == (-signal.SIGKILL if crash else 0), \
                            journey.runtime_logs(runtime)
                    process = None
                for client in (caster, recipient):
                    if client is not None:
                        client.close()
                caster = recipient = None

            def login():
                nonlocal caster, recipient
                caster = journey.reconnect_character(plain)
                recipient = journey.reconnect_character(
                    plain, account=RECIPIENT_ACCOUNT, character=RECIPIENT,
                    source_host="127.0.0.2")

            def command(client, text):
                nonlocal sequence
                sequence += 1
                marker = "restedmarker" + str(sequence)
                client.send(text)
                client.send("say " + marker)
                return client.expect(marker, timeout=30)

            def affects():
                rows = sql(f"SELECT type,duration,flags FROM player_affects WHERE pid={pid} "
                           f"AND type IN ({RESTED},{WELLRESTED}) ORDER BY type")
                return [tuple(map(int, row.split("\t"))) for row in rows.splitlines()]

            def saved():
                recipient.send("save")
                recipient.expect(f"Save complete for {RECIPIENT}.", timeout=30)
                return affects()

            def seed(tag, duration, offline=0):
                assert process is None, "seed only while the synthetic server is stopped"
                sql(f"DELETE FROM player_affects WHERE pid={pid} AND type IN ({RESTED},{WELLRESTED})")
                if tag is not None:
                    sql(f"INSERT INTO player_affects(pid,type,duration,flags) "
                        f"VALUES({pid},{tag},{duration},{FLAGS})")
                sql(f"UPDATE player_data SET last_save=NOW()-INTERVAL {offline} SECOND WHERE pid={pid}")

            def recovered(expected):
                # Short restarts consume no full 75-second offline tick. Reading
                # score checks live materialization before a full save checks it.
                score = command(recipient, "score").lower()
                bonus = "well-rested bonus" if expected[0] == WELLRESTED else "rested bonus"
                assert bonus in score, score
                assert saved() == [expected], (expected, affects())

            try:
                boot()
                caster = journey.MudClient(plain)
                journey.create_character(caster)
                caster.send("save")
                caster.expect(f"Save complete for {journey.CHARACTER}.", timeout=30)
                recipient = journey.MudClient(plain, source_host="127.0.0.2")
                journey.create_character(recipient, account=RECIPIENT_ACCOUNT, character=RECIPIENT,
                                         email="rested@example.invalid")
                recipient.send("save")
                recipient.expect(f"Save complete for {RECIPIENT}.", timeout=30)
                pid = int(sql(f"SELECT pid FROM player_data WHERE name='{RECIPIENT}'"))
                stop()
                sql(f"UPDATE player_data SET level=62,highest_level=62 WHERE name='{journey.CHARACTER}'")

                # Each branch starts with an acknowledged clean login checkpoint.
                # Then only the periodic checkpoint may publish the spell change.
                for label, tag, duration, expected_tag, message in (
                    ("grant", None, 0, RESTED, "a rested bonus"),
                    ("upgrade", RESTED, 17, WELLRESTED, "upgrade it to well-rested"),
                    ("refresh", WELLRESTED, 17, WELLRESTED, "well-rested bonus"),
                ):
                    seed(tag, duration)
                    boot()
                    login()
                    saved()
                    response = command(caster, f"cast 'rested' {RECIPIENT}")
                    assert message in response, response
                    grant_epoch = int(sql("SELECT UNIX_TIMESTAMP()"))
                    deadline = time.monotonic() + 45
                    while int(sql(f"SELECT UNIX_TIMESTAMP(last_save) FROM player_data WHERE pid={pid}")) <= grant_epoch:
                        assert time.monotonic() < deadline, "no post-cast periodic checkpoint"
                        time.sleep(.2)
                    checkpoint = affects()
                    assert len(checkpoint) == 1, (label, checkpoint)
                    saved_tag, remaining, flags = checkpoint[0]
                    assert (saved_tag, flags) == (expected_tag, FLAGS) and 149 <= remaining <= 150, \
                        (label, checkpoint)
                    stop(crash=True)
                    assert affects() == checkpoint
                    boot()
                    login()
                    recovered(checkpoint[0])
                    stop()
                    print(f"[PASS] {label}: recipient checkpoint survived SIGKILL/reconnect: {checkpoint}", flush=True)

                # Controls: full-save crash, ordinary rent, aging and expiration.
                seed(WELLRESTED, 120)
                boot()
                login()
                acknowledged = saved()[0]
                stop(crash=True)
                boot()
                login()
                recovered(acknowledged)
                recipient.send("rent")
                recipient.expect("ACCOUNT MENU", timeout=30)
                stop()
                boot()
                login()
                recovered(acknowledged)
                stop()
                print("[PASS] full-save crash and ordinary rent controls", flush=True)

                for duration, expected in ((120, [(WELLRESTED, 118, FLAGS)]),
                                           (1, []), (2, [(WELLRESTED, 0, FLAGS)])):
                    seed(WELLRESTED, duration, offline=150)
                    boot()
                    login()
                    assert saved() == expected, (duration, affects(), expected)
                    stop()
                seed(None, 0, offline=3600)
                boot()
                login()
                assert saved() == [], "short offline period granted a replacement bonus"
                stop()
                print("[PASS] offline aging, expiration, zero boundary and no short-reconnect replacement", flush=True)
            finally:
                stop(crash=True)
    finally:
        sql("DROP DATABASE " + database, False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", type=Path, required=True)
    args = parser.parse_args()
    run(args.server.resolve())
