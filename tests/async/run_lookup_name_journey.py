#!/usr/bin/env python3
"""Verify staff name searches through Telnet on disposable MariaDB.

Run with with_disposable_mariadb.sh; uses private world fixtures, never .env.
"""
import argparse
from pathlib import Path
import re
import signal
import subprocess
import tempfile
import time

import test_mariadb_combat_journey as journey
from test_flight_network_journey import authority, command

ROOT = journey.ROOT
STAFF, ACCOUNT = "Lookupwarden", "Lookupstaff"


def run(server):
    (ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="lookup-names-", dir=ROOT / "bin/tests") as temporary:
        runtime = Path(temporary)
        journey.make_fixture(runtime)
        journey.generate_certificate(runtime)
        (runtime / "help").symlink_to(ROOT / "help", target_is_directory=True)
        (runtime / "logs/log").mkdir(parents=True)
        critical = runtime / "journals/critical"
        critical.mkdir(parents=True, mode=0o700)
        names = (
            ("giant fire guard", "&+Ra stone sentinel&n"),
            ("spectral guard", "a &=Rbfi&+Gre &+Lgiant&n"),
            ("thri-kreen", "a mantis guard"),
            ("unspawned ember", "a sleeping sentinel"),
        )
        for suffix, template in (("mob", 11), ("obj", 5)):
            path = runtime / f"areas_mini/mini.{suffix}"
            text = path.read_text()
            record = re.search(rf"(?ms)^#{template}\n(.*?)(?=^#|^\$)", text)[1]
            tail = record.split("~", 2)[2]
            records = "".join(f"#{22901 + i}\n{keys}~\n{description}~{tail}"
                              for i, (keys, description) in enumerate(names))
            path.write_text(text.replace("$~", records + "$~"))
        plain, tls, websocket = journey.available_ports()
        output_path = runtime / "server.out"
        process = client = None
        evidence = []
        with authority("mariadb", runtime) as (env, sql), output_path.open("w") as output:
            env.update(CRITICAL_COMMAND_JOURNAL_DIR=str(critical), DURIS_TLS_PORT=str(tls),
                       DURIS_WEBSOCKET_PORT=str(websocket))

            def boot():
                nonlocal process
                offset = output_path.stat().st_size
                process = subprocess.Popen(
                    [str(server), "--minimal", "-s", "-d", str(runtime), str(plain)],
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

            def check(text, expected):
                response = command(client, text)
                found = set(re.findall(r"\b2290[1-4]\b", response))
                assert found == {str(number) for number in expected}, (text, response)
                evidence.append(text + "\n" + response)
                return response

            try:
                boot()
                client = journey.MudClient(plain)
                journey.create_character(client, account=ACCOUNT, character=STAFF,
                                         email="lookup@example.invalid")
                client.send("save")
                client.expect("Saving " + STAFF + ".", timeout=30)
                stop()
                sql(f"UPDATE player_data SET level=62,highest_level=62 WHERE name='{STAFF}'")
                boot()
                client = journey.reconnect_character(plain, expected_room=None,
                                                     account=ACCOUNT, character=STAFF)
                client.expect("Welcome to Duris", timeout=30)
                command(client, "toggle paging no")
                command(client, "vis 0")
                # All four prototypes are unspawned: their keywords must be ready at boot.
                for kind in ("mob", "char", "obj"):
                    for pattern in ("fire-giant", "GIANT-FIRE"):
                        check(f"lookup {kind} {pattern}", (22901, 22902))
                    check(f"lookup {kind} fire giant", (22902,))
                    check(f"lookup {kind} tone sent", (22901,))
                    check(f"lookup {kind} thri-kreen", (22903,))
                    check(f"lookup {kind} unspawned-ember", (22904,))
                    check(f"lookup {kind} 22904", (22904,))
                assert "Nothing found." in check("where fire-giant", ())
                for kind in ("mob", "obj"):
                    for vnum in (22901, 22902):
                        response = command(client, f"load {kind} {vnum}")
                        assert "created" in response.lower(), response
                check("where fire-giant", (22901, 22902))
                check("where GIANT-FIRE", (22901, 22902))
                check("where fire giant", (22902,))
                assert "Nothing found." in check("where tone sent", ())
                assert "Nothing found." in check("where unspawned-ember", ())
                assert b"\x1b[" in client.raw_transcript
                # The pfile start letter reaches system(); a shell command must not run.
                rejected = command(client, "lookup pfile a;touch${IFS}injected; 50 Human Warrior")
                assert "must be a single letter" in rejected, rejected
                assert not (runtime / "injected").exists(), "lookup pfile ran a shell command"
                for topic in ("godlookup", "godwhere"):
                    assert "fire-giant" in command(client, "help " + topic)
                (ROOT / "bin/tests/lookup-name-journey.txt").write_text("\n".join(evidence))
                print("PASS: MariaDB boot, cold mob/object keywords, staff dispatch, compound and "
                      "colored-description matching, partial text, VNUMs, live WHERE and help")
            finally:
                stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", type=Path, default=ROOT / "bin/server/dms_new")
    args = parser.parse_args()
    run(args.server.resolve())
