#!/usr/bin/env python3
"""Real five-minute pwipe, launcher cleanup, staff recreation and fresh gameplay.

Own disposable MariaDB/runtime only; never reads a checkout .env or real player data.
"""
from pathlib import Path
import argparse
import shlex
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
GIT = ["git", "-c", "safe.directory=" + str(ROOT)]


def run(binary, with_redis=False, systemd=False):
    if not os.environ.get("TEST_DB_HOST"):
        wrapper = ROOT / "tests/async/with_disposable_mariadb.sh"
        os.execv(str(wrapper), [str(wrapper), sys.executable, str(Path(__file__).resolve()), str(binary),
                               *(["--redis"] if with_redis else []), *(["--systemd"] if systemd else [])])
    assert not systemd or os.geteuid() == 0, "the disposable system-unit fixture requires root"
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
              "source_diff_sha256": hashlib.sha256(subprocess.check_output([*GIT, "diff", "HEAD", "--", "src"], cwd=ROOT)).hexdigest(),
              "revision": subprocess.check_output([*GIT, "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "backend": "mariadb-primary", "redis": with_redis, "systemd": systemd, "status": "running"}
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
            tracked = subprocess.check_output([*GIT, "ls-files", "scripts", "migrations"],
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
            # A private allocator avoids another user's sticky-/tmp lock when
            # this fixture runs as root to manage its disposable system unit.
            port_root = root / "test-tmp"
            port_root.mkdir(mode=0o700)
            prior_tempdir = tempfile.tempdir
            tempfile.tempdir = str(port_root)
            try:
                plain, tls, websocket = journey.available_ports()
            finally:
                tempfile.tempdir = prior_tempdir
            env.update(DURIS_DEV_PORT=str(plain), DURIS_TLS_PORT=str(tls),
                       DURIS_WEBSOCKET_PORT=str(websocket), DURIS_WEBSOCKET_LISTEN_ADDRESS="127.0.0.1",
                       CRITICAL_COMMAND_JOURNAL_DIR=str(root / "journals/critical"))
            path = root / "launcher.out"
            process = client = redis_server = journal = None
            unit_path = pin_path = None
            unit_created = pin_created = False
            unit_name = "duris-pwipe-qualification-" + uuid.uuid4().hex + ".service"
            output_file = path.open("w")

            def unit_state():
                properties = ("ExecMainStatus", "ActiveState", "SubState", "NRestarts", "Result")
                text = subprocess.check_output(["systemctl", "show", unit_name,
                                                *("--property=" + key for key in properties)], text=True)
                return dict(line.split("=", 1) for line in text.splitlines())

            def running():
                # The system unit owns this lifetime; no CLI helper is a
                # substitute for its actual state and final exit status.
                return unit_state()["ActiveState"] not in ("failed", "inactive") if systemd else process.poll() is None

            def exit_status():
                return int(unit_state()["ExecMainStatus"]) if systemd else process.returncode

            def redis(*arguments):
                return subprocess.check_output(["redis-cli", "--raw", "-h", "127.0.0.1", "-p",
                                                env["REDIS_PORT"], *arguments], text=True).strip()

            def expect_presence(pid, epoch):
                deadline = time.monotonic() + 15
                while True:
                    prefix = env["REDIS_NAMESPACE"] + ":season:" + str(epoch) + ":presence:"
                    generation = redis("GET", prefix + "current")
                    session = prefix + "session:" + generation + ":" + str(pid)
                    if generation and redis("EXISTS", session) == "1":
                        return
                    assert time.monotonic() < deadline, "visible character presence was not published"
                    time.sleep(.1)

            def start():
                if systemd:
                    subprocess.run(["systemctl", "start", unit_name], stdout=subprocess.DEVNULL,
                                   stderr=output_file, timeout=90, check=False)
                    return None
                return subprocess.Popen([str(root / "scripts/cycle_mud.sh"), "--minimal"],
                                        cwd=root, env=env, stdout=output_file,
                                        stderr=subprocess.STDOUT, start_new_session=True)

            def stop():
                nonlocal process, client
                if client:
                    client.close(); client = None
                if systemd and unit_created:
                    subprocess.run(["systemctl", "stop", unit_name], check=True, timeout=100)
                if process and process.poll() is None:
                    process.terminate()
                    try: process.wait(timeout=45)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL); process.wait(timeout=10)
                process = None

            def boot():
                nonlocal process
                offset = path.stat().st_size
                process = start()
                deadline = time.monotonic() + 120
                while "Entering game loop." not in path.read_text(errors="replace")[offset:]:
                    assert running() and time.monotonic() < deadline, "boot failed"
                    time.sleep(0.1)

            def save(name):
                client.send("save"); client.expect("Save complete for " + name + ".", timeout=30)

            try:
                if with_redis:
                    redis_root = root / "redis"
                    redis_root.mkdir()
                    redis_port = journey.available_ports()[0]
                    assert redis_port not in (plain, tls, websocket)
                    redis_server = subprocess.Popen(["redis-server", "--bind", "127.0.0.1", "--port", str(redis_port),
                                                     "--save", "", "--appendonly", "no", "--dir", str(redis_root)],
                                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    env.update(REDIS="TRUE", REDIS_HOST="127.0.0.1", REDIS_PORT=str(redis_port),
                               REDIS_DB="0", REDIS_NAMESPACE="duris:local:pwipe-" + uuid.uuid4().hex[:12])
                    for attempt in range(100):
                        probe = subprocess.run(["redis-cli", "-h", "127.0.0.1", "-p", str(redis_port), "PING"],
                                               capture_output=True, text=True)
                        if probe.returncode == 0 and probe.stdout.strip() == "PONG":
                            break
                        time.sleep(.05)
                    else: raise AssertionError("private Redis did not start")
                if systemd:
                    template = (ROOT / "deploy/systemd/duris-mud-production.service.in").read_text()
                    owner = ROOT.stat()
                    assert owner.st_uid != 0, "fixture service must run unprivileged"
                    unit = template.replace("@DURIS_USER@", str(owner.st_uid)).replace("@DURIS_GROUP@", str(owner.st_gid))
                    unit = unit.replace("@DURIS_ROOT@", str(root)).replace(" --production", " --minimal")
                    unit = unit.replace("Description=DurisMUD production server", "Description=Disposable pwipe qualification")
                    (root / ".env").write_text("".join(key + "=" + shlex.quote(value) + "\n" for key, value in env.items()))
                    (root / ".env").chmod(0o600)
                    for directory, _, files in os.walk(root, followlinks=False):
                        os.chown(directory, owner.st_uid, owner.st_gid)
                        for name in files:
                            os.chown(Path(directory) / name, owner.st_uid, owner.st_gid, follow_symlinks=False)
                    unit_path = Path("/run/systemd/system") / unit_name
                    assert not unit_path.exists()
                    unit_path.write_text(unit)
                    unit_created = True
                    # Successful inactive units may be garbage-collected along
                    # with their exit statistics. An active After reference pins
                    # this unit without starting or restarting it.
                    pin_path = unit_path.with_suffix(".target")
                    assert not pin_path.exists()
                    pin_path.write_text("[Unit]\nDescription=Private qualification statistics reference\nAfter=" + unit_name + "\n")
                    pin_created = True
                    subprocess.run(["systemctl", "daemon-reload"], check=True)
                    subprocess.run(["systemctl", "start", pin_path.name], check=True)
                    journal = subprocess.Popen(["journalctl", "--follow", "--unit=" + unit_name,
                                                "--output=cat", "--no-pager"], stdout=output_file, stderr=subprocess.STDOUT)
                    report.update(unit_template_sha256=hashlib.sha256(template.encode()).hexdigest(),
                                  unit_sha256=hashlib.sha256(unit.encode()).hexdigest())
                    sql("UPDATE season_reset_state SET reset_status='resetting',reset_started_at=UTC_TIMESTAMP(6),reset_completed_at=NULL")
                    process = start()
                    deadline = time.monotonic() + 90
                    while running():
                        assert time.monotonic() < deadline, "fenced unit did not stop"
                        time.sleep(.1)
                    assert exit_status() == 58, unit_state()
                    time.sleep(12)
                    fenced = unit_state()
                    assert fenced["NRestarts"] == "0" and fenced["ActiveState"] in ("failed", "inactive"), fenced
                    report["service_incomplete_reset"] = fenced
                    sql("UPDATE season_reset_state SET reset_status='active',reset_started_at=NULL")
                    process = None
                    print("Actual full-sandbox system service refused an incomplete reset with exit 58 and no restart", flush=True)
                boot()
                client = journey.MudClient(plain)
                journey.create_character(client, character=STAFF)
                client.send("shutdown pwipe confirm yes"); client.expect("Pardon?")
                save(STAFF)
                old_pid = int(sql("SELECT pid FROM player_data WHERE name='" + STAFF + "'"))
                if with_redis:
                    expect_presence(old_pid, 1)
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
                if with_redis:
                    old_keys = [env["REDIS_NAMESPACE"] + ":season:1:" + suffix for suffix in
                                ("cache:pwipe-sentinel", "presence:session:pwipe-sentinel",
                                 "presence_op:pwipe-sentinel", "world_state:generation:pwipe-sentinel")]
                    old_keys.append("mud:cache:pwipe-sentinel")
                    retained_keys = ["unrelated:pwipe-sentinel", "duris:local:other:season:1:cache:pwipe-sentinel"]
                    for key in old_keys + retained_keys:
                        assert redis("SET", key, "fixture") == "OK"
                began = time.monotonic()
                wall_began = time.time()
                report["schedule_wall_time"] = wall_began
                client.send("shutdown pwipe confirm yes"); client.expect("five")
                next_progress = began + 60
                print("Real pwipe scheduled; beginning the required five-minute countdown", flush=True)
                while running():
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
                assert exit_status() == 55, (exit_status(), path.read_text(errors="replace")[-6000:])
                if systemd:
                    time.sleep(12)
                    completed = unit_state()
                    assert completed["NRestarts"] == "0" and completed["ActiveState"] == "inactive", completed
                    report["service_completed_reset"] = completed
                if with_redis:
                    assert redis("EXISTS", *old_keys) == "0"
                    assert redis("MGET", *retained_keys).splitlines() == ["fixture"] * len(retained_keys)
                    report["redis_reset_assertions"] = "old scoped/legacy sentinels removed; unrelated namespaces preserved"
                    print("Real Redis reset removed old epoch sentinels and preserved unrelated namespaces", flush=True)
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
                if with_redis:
                    # Staff login applies wizard invisibility; public presence
                    # must not reveal that body. Check a visible mortal below.
                    assert redis("KEYS", env["REDIS_NAMESPACE"] + ":season:2:presence:session:*:" + str(new_pid)) == ""
                    assert redis("EXISTS", *old_keys) == "0"
                client.send("quit"); client.expect("ACCOUNT MENU", timeout=30)
                client.close(); client = None
                client = journey.MudClient(plain)
                journey.create_character(client, existing_account=True)
                if with_redis:
                    fresh = int(sql("SELECT pid FROM player_data WHERE name='" + journey.CHARACTER + "' AND active=1"))
                    expect_presence(fresh, 2)
                    assert redis("KEYS", env["REDIS_NAMESPACE"] + ":season:2:presence:session:*:" + str(old_pid)) == ""
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
                stop()
                if journal:
                    journal.terminate(); journal.wait(timeout=10)
                if unit_created:
                    subprocess.run(["systemctl", "reset-failed", unit_name], check=False, capture_output=True)
                    assert unit_path.parent == Path("/run/systemd/system") and unit_path.name.startswith("duris-pwipe-qualification-")
                    if pin_created:
                        subprocess.run(["systemctl", "stop", pin_path.name], check=True)
                        pin_path.unlink()
                    unit_path.unlink()
                    subprocess.run(["systemctl", "daemon-reload"], check=True)
                if redis_server:
                    redis_server.terminate(); redis_server.wait(timeout=10)
                output_file.close()
    except Exception:
        report["status"] = "failed"
        raise
    finally:
        suffix = "mariadb-redis-systemd" if systemd and with_redis else "mariadb-redis" if with_redis else "mariadb"
        (output / ("pwipe-runtime-" + suffix + ".json")).write_text(json.dumps(report, indent=2) + "\n")
        sql("DROP DATABASE " + database, False)


def flatfile_rejection(binary):
    """Exercise the unsupported command on a real private flat-file authority."""
    output = ROOT / "bin/analysis"
    output.mkdir(parents=True, exist_ok=True)
    (ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
    report = {"revision": subprocess.check_output([*GIT, "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
              "source_diff_sha256": hashlib.sha256(subprocess.check_output([*GIT, "diff", "HEAD", "--", "src"], cwd=ROOT)).hexdigest(),
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--flatfile-rejection", action="store_true")
    parser.add_argument("--redis", action="store_true", help="use a disposable Redis process")
    parser.add_argument("--systemd", action="store_true", help="use a disposable system unit (requires root)")
    parser.add_argument("binary", nargs="?", default=str(ROOT / "bin/server/dms_new"))
    options = parser.parse_args()
    binary = Path(options.binary).resolve(strict=True)
    if options.flatfile_rejection:
        assert not options.redis and not options.systemd
        flatfile_rejection(binary)
    else:
        run(binary, options.redis, options.systemd)
