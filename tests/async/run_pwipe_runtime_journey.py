#!/usr/bin/env python3
"""Real five-minute pwipe, launcher cleanup, staff recreation and fresh gameplay.

Own disposable MariaDB/runtime only; never reads a checkout .env or real player data.
"""
from pathlib import Path
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid

import test_flatfile_combat_journey as journey

ROOT = Path(__file__).resolve().parents[2]
STAFF = "Wipekeeper"


def run(binary):
    if not os.environ.get("TEST_DB_HOST"):
        wrapper = ROOT / "tests/async/with_disposable_mariadb.sh"
        os.execv(str(wrapper), [str(wrapper), sys.executable, str(Path(__file__).resolve()), str(binary)])
    assert os.environ["TEST_DB_HOST"] == "127.0.0.1"
    assert not Path("/usr/bin/sendemail").exists(), "fixture requires the launcher mail command absent"
    database = "pwipe_journey_" + uuid.uuid4().hex[:12]
    env = dict(PATH=os.environ.get("PATH", "/usr/bin:/bin"), ENVIRONMENT="local",
               PERSISTENCE_MODE="mariadb-primary", DB_HOST="127.0.0.1",
               DB_PORT=os.environ["TEST_DB_PORT"], DB_USER=os.environ["TEST_DB_USER"],
               DB_PASSWD=os.environ["TEST_DB_PASSWORD"], DB_NAME=database,
               DB_ALLOWED_TARGETS="127.0.0.1/" + database, MYSQL_PWD=os.environ["TEST_DB_PASSWORD"],
               REDIS="FALSE", TELEMETRY_ENABLED="FALSE", DURIS_DISCORD_ENABLED="FALSE",
               CHAOS_MUD="FALSE", LISTEN_ADDRESS="127.0.0.1")
    if "LD_LIBRARY_PATH" in os.environ:
        env["LD_LIBRARY_PATH"] = os.environ["LD_LIBRARY_PATH"]
    mysql = ["mysql", "--protocol=tcp", "-h", env["DB_HOST"], "-P", env["DB_PORT"],
             "-u", env["DB_USER"], "-N", "-B"]

    def sql(statement, selected=True):
        return subprocess.check_output(mysql + ([database] if selected else []),
                                       input=statement, text=True, env=env).strip()

    sql("CREATE DATABASE " + database + " CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci", False)
    output = ROOT / "bin/analysis"
    output.mkdir(parents=True, exist_ok=True)
    (ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
    report = {"binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
              "source_diff_sha256": hashlib.sha256(subprocess.check_output(["git", "diff", "HEAD", "--", "src"], cwd=ROOT)).hexdigest(),
              "revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "backend": "mariadb-primary", "redis": False, "status": "running"}
    try:
        sql((ROOT / "migrations/bootstrap_multithread_safe.sql").read_text())
        for arguments in (("adopt", "--kind", "fresh_bootstrap"), ("run",)):
            result = subprocess.run([sys.executable, "scripts/migration_runner.py", *arguments],
                                    cwd=ROOT, env=env, capture_output=True, text=True)
            assert result.returncode == 0, result.stdout + result.stderr
        with tempfile.TemporaryDirectory(prefix="pwipe-runtime-", dir=ROOT / "bin/tests") as temporary:
            root = Path(temporary)
            journey.make_fixture(root)
            journey.generate_certificate(root)
            tracked = subprocess.check_output(["git", "ls-files", "scripts", "migrations"],
                                              cwd=ROOT, text=True).splitlines()
            for relative in tracked:
                destination = root / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / relative, destination)
            for directory in ("Players/wipers", "Players/a", "Players/Backup", "Ships", "bin/server",
                              "logs/log", "journals/critical"):
                (root / directory).mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / "Players/wipers/wipe_it_all", root / "Players/wipers/wipe_it_all")
            shutil.copy2(binary, root / "bin/server/dms_new")
            plain, tls, websocket = journey.available_ports()
            env.update(DURIS_DEV_PORT=str(plain), DURIS_TLS_PORT=str(tls),
                       DURIS_WEBSOCKET_PORT=str(websocket), DURIS_WEBSOCKET_LISTEN_ADDRESS="127.0.0.1",
                       CRITICAL_COMMAND_JOURNAL_DIR=str(root / "journals/critical"))
            path = root / "launcher.out"
            process = client = None
            output_file = path.open("w")

            def stop():
                nonlocal process, client
                if client:
                    client.close(); client = None
                if process and process.poll() is None:
                    process.terminate()
                    try: process.wait(timeout=45)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL); process.wait(timeout=10)
                process = None

            def boot():
                nonlocal process
                offset = path.stat().st_size
                process = subprocess.Popen([str(root / "scripts/cycle_mud.sh"), "--minimal"],
                                           cwd=root, env=env, stdout=output_file,
                                           stderr=subprocess.STDOUT, start_new_session=True)
                deadline = time.monotonic() + 120
                while "Entering game loop." not in path.read_text(errors="replace")[offset:]:
                    assert process.poll() is None and time.monotonic() < deadline, "boot failed"
                    time.sleep(0.1)

            def save(name):
                client.send("save"); client.expect("Save complete for " + name + ".", timeout=30)

            try:
                boot()
                client = journey.MudClient(plain)
                journey.create_character(client, character=STAFF)
                client.send("shutdown pwipe confirm yes"); client.expect("Pardon?")
                save(STAFF)
                old_pid = int(sql("SELECT pid FROM player_data WHERE name='" + STAFF + "'"))
                old_items = sql("SELECT COUNT(*) FROM player_items WHERE pid=" + str(old_pid))
                assert int(old_items) > 0
                client.send("quit"); client.expect("ACCOUNT MENU", timeout=30)
                stop()
                # Synthetic staff promotion while offline, as other real-server fixtures do.
                sql("UPDATE player_data SET level=62,highest_level=62 WHERE pid=" + str(old_pid))
                sql("UPDATE account_characters SET racewar=0 WHERE pid=" + str(old_pid))
                sql("INSERT INTO account_banks(account_name,racewar,bank_platinum) VALUES('" + journey.ACCOUNT + "',1,9)")
                sql("INSERT INTO currency_bank_baseline(bank_id,opening_copper,opening_silver,opening_gold,opening_platinum) "
                    "SELECT id,0,0,0,9 FROM account_banks")
                (root / "Players/a/old-season").write_text("old pfile")
                (root / "Ships/old-season").write_text("old ship")
                (root / "Players/Backup/preserve").write_text("archive")
                boot()
                client = journey.reconnect_character(plain, character=STAFF)
                client.send("shutdown pwipe confirm"); client.expect("You must")
                client.send("shutdown pwipe confirm yes"); client.expect("five")
                client.send("shutdown"); client.expect("cancelled")
                assert sql("SELECT CONCAT(season_epoch,':',reset_status) FROM season_reset_state") == "1:active"
                began = time.monotonic()
                wall_began = time.time()
                report["schedule_wall_time"] = wall_began
                client.send("shutdown pwipe confirm yes"); client.expect("five")
                next_progress = began + 60
                print("Real pwipe scheduled; beginning the required five-minute countdown", flush=True)
                while process.poll() is None:
                    elapsed = time.monotonic() - began
                    assert elapsed < 420, "pwipe countdown/reset did not finish"
                    if time.time() - wall_began < 290:
                        assert sql("SELECT CONCAT(season_epoch,':',reset_status) FROM season_reset_state") == "1:active"
                        assert (root / "Players/a/old-season").exists()
                    if time.monotonic() >= next_progress:
                        print(f"Countdown observation: {int(elapsed)} seconds, launcher still running", flush=True)
                        next_progress += 60
                    time.sleep(1)
                elapsed = time.monotonic() - began
                wall_elapsed = time.time() - wall_began
                report.update(monotonic_countdown_seconds=elapsed, wall_countdown_seconds=wall_elapsed)
                assert wall_elapsed >= 295, (wall_elapsed, elapsed)
                assert process.returncode == 55, (process.returncode, path.read_text(errors="replace")[-6000:])
                client.close(); client = None; process = None
                assert sql("SELECT CONCAT(season_epoch,':',reset_status) FROM season_reset_state") == "2:active"
                assert sql("SELECT COUNT(*) FROM account_banks") == "0"
                assert sql("SELECT COUNT(*) FROM player_items WHERE pid=" + str(old_pid)) == "0"
                new_pid = int(sql("SELECT pid FROM player_data WHERE name='" + STAFF + "' AND active=1"))
                assert new_pid > old_pid
                assert not (root / "Players/a/old-season").exists()
                assert not (root / "Ships/old-season").exists()
                assert (root / "Players/Backup/preserve").read_text() == "archive"
                report.update(countdown_seconds=round(wall_elapsed, 2), old_pid=old_pid, new_staff_pid=new_pid)
                print("Real command/launcher/filesystem reset passed; booting the new season", flush=True)
                boot()
                client = journey.reconnect_character(plain, character=STAFF)
                client.send("score"); client.expect("Level")
                save(STAFF)
                client.send("quit"); client.expect("ACCOUNT MENU", timeout=30)
                client.close(); client = None
                client = journey.MudClient(plain)
                journey.create_character(client, existing_account=True)
                journey.complete_npc_combat_journey(client)
                client.close(); client = None
                fresh_pid = int(sql("SELECT pid FROM player_data WHERE name='" + journey.CHARACTER + "' AND active=1"))
                assert fresh_pid > new_pid
                before = sql("SELECT exp,copper,silver,gold,platinum FROM player_data WHERE pid=" + str(fresh_pid))
                assert int(sql("SELECT COUNT(*) FROM player_items WHERE pid=" + str(fresh_pid))) > 0
                stop(); boot()
                client = journey.reconnect_character(plain)
                client.send("inventory"); client.expect("a banana")
                save(journey.CHARACTER)
                assert sql("SELECT exp,copper,silver,gold,platinum FROM player_data WHERE pid=" + str(fresh_pid)) == before
                assert sql("SELECT active FROM player_data WHERE pid=" + str(old_pid)) == "0"
                stop()
                report.update(status="passed", fresh_pid=fresh_pid,
                              assertions="real command/cancel/countdown/launcher/filesystem/staff login/fresh combat/save/reconnect/reboot")
                print("Recreated Overlord login and fresh mortal combat/loot/save/reconnect/second boot passed", flush=True)
            except Exception:
                report["status"] = "failed"
                print(path.read_text(errors="replace")[-8000:])
                print(journey.runtime_logs(root)[-8000:])
                if client: print(client.transcript.decode(errors="replace")[-6000:])
                shutil.copy2(path, output / "pwipe-runtime-failed.log")
                raise
            finally:
                stop(); output_file.close()
    finally:
        (output / "pwipe-runtime-mariadb.json").write_text(json.dumps(report, indent=2) + "\n")
        sql("DROP DATABASE " + database, False)


def flatfile_rejection(binary):
    """Exercise the unsupported command on a real private flat-file authority."""
    output = ROOT / "bin/analysis"
    output.mkdir(parents=True, exist_ok=True)
    (ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
    report = {"revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
              "source_diff_sha256": hashlib.sha256(subprocess.check_output(["git", "diff", "HEAD", "--", "src"], cwd=ROOT)).hexdigest(),
              "backend": "flatfile-primary", "status": "running"}
    with tempfile.TemporaryDirectory(prefix="pwipe-flatfile-", dir=ROOT / "bin/tests") as temporary:
        root = Path(temporary)
        state, runtime = root / "state", root / "runtime"
        state.mkdir(mode=0o700)
        (state / "domains").mkdir(mode=0o700)
        (runtime / "logs/log").mkdir(parents=True)
        (runtime / "journals/critical").mkdir(parents=True, mode=0o700)
        journey.make_fixture(runtime)
        journey.generate_certificate(runtime)
        sentinel = runtime / "Players/a/keep"
        sentinel.parent.mkdir(parents=True)
        sentinel.write_text("preserved legacy state")
        plain, tls, websocket = journey.available_ports()
        env = dict(PATH=os.environ.get("PATH", "/usr/bin:/bin"), ENVIRONMENT="local",
                   PERSISTENCE_MODE="flatfile-primary", FLATFILE_STATE_DIR=str(state),
                   CRITICAL_COMMAND_JOURNAL_DIR=str(runtime / "journals/critical"),
                   LISTEN_ADDRESS="127.0.0.1", DURIS_TLS_PORT=str(tls),
                   DURIS_WEBSOCKET_PORT=str(websocket), DURIS_WEBSOCKET_LISTEN_ADDRESS="127.0.0.1",
                   REDIS="FALSE", CHAOS_MUD="FALSE", TELEMETRY_ENABLED="FALSE",
                   DURIS_DISCORD_ENABLED="FALSE")
        if "LD_LIBRARY_PATH" in os.environ:
            env["LD_LIBRARY_PATH"] = os.environ["LD_LIBRARY_PATH"]
        process = client = None
        path = runtime / "server.out"
        output_file = path.open("w")

        def stop():
            nonlocal process, client
            if client:
                client.close(); client = None
            if process and process.poll() is None:
                process.terminate()
                try: process.wait(timeout=30)
                except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=10)
            process = None

        def boot():
            nonlocal process
            offset = path.stat().st_size
            process = subprocess.Popen([str(binary), "--minimal", "-s", str(plain)], cwd=runtime,
                                       env=env, stdout=output_file, stderr=subprocess.STDOUT)
            deadline = time.monotonic() + 90
            while "Entering game loop." not in path.read_text(errors="replace")[offset:]:
                assert process.poll() is None and time.monotonic() < deadline, "flat-file boot failed"
                time.sleep(0.1)

        def save():
            client.send("save"); client.expect("Save complete for " + STAFF + ".", timeout=30)

        try:
            boot()
            client = journey.MudClient(plain)
            journey.create_character(client, character=STAFF)
            save()
            client.send("quit"); client.expect("ACCOUNT MENU", timeout=30)
            stop()
            journey.make_overlord(state, STAFF)
            boot()
            client = journey.reconnect_character(plain, character=STAFF)
            save()
            snapshot = state / "players/1.snapshot"
            before = snapshot.read_bytes()
            for command in ("shutdown pwipe", "shutdown pwipe confirm yes"):
                client.send(command); client.expect("Pwipe is unavailable in flatfile-primary mode.")
                assert process.poll() is None and snapshot.read_bytes() == before
                assert sentinel.read_text() == "preserved legacy state"
            client.send("shutdown"); reply = client.expect("Syntax: shutdown")
            assert "cancelled" not in reply
            client.send("shutdown reboot 10 retained-countdown-control")
            client.expect("retained-countdown-control")
            client.send("shutdown pwipe confirm yes")
            client.expect("Pwipe is unavailable in flatfile-primary mode.")
            client.send("shutdown"); reply = client.expect("Syntax: shutdown")
            assert "Scheduled reboot cancelled" in reply
            client.send("look"); client.expect("The Regression Arena")
            save()
            client.send("quit"); client.expect("ACCOUNT MENU", timeout=30)
            client.close(); client = None
            client = journey.reconnect_character(plain, character=STAFF)
            save(); stop(); boot()
            client = journey.reconnect_character(plain, character=STAFF)
            client.send("score"); client.expect("Level")
            save(); stop()
            assert sentinel.read_text() == "preserved legacy state"
            logs = path.read_text(errors="replace") + journey.runtime_logs(runtime)
            assert "Shutdown pwipe called" not in logs
            report.update(status="passed", assertions="immediate rejection/no wipe countdown/existing reboot preserved/no file mutation/save/logout/reconnect/second boot")
            print("Real flatfile-primary pwipe rejection, preserved snapshot/files and continued save/reconnect/second boot passed", flush=True)
        except Exception:
            report["status"] = "failed"
            print(path.read_text(errors="replace")[-6000:])
            if client: print(client.transcript.decode(errors="replace")[-4000:])
            raise
        finally:
            stop(); output_file.close()
            (output / "pwipe-runtime-flatfile.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    if sys.argv[1:2] == ["--flatfile-rejection"]:
        flatfile_rejection(Path(sys.argv[2]).resolve(strict=True))
    else:
        run(Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "bin/server/dms_new").resolve(strict=True))
