#!/usr/bin/env python3
"""Real five-minute pwipe, launcher cleanup, staff recreation and fresh gameplay.

Own disposable MariaDB/runtime only; never reads a checkout .env or real player data.
"""
from pathlib import Path
import argparse
import contextlib
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
import urllib.request

import test_flatfile_combat_journey as journey

ROOT = Path(__file__).resolve().parents[2]
STAFF = "Wipekeeper"
OBSERVER = "Watchkeeper"
OBSERVER_ACCOUNT = "Shutdownacct"
CLAIMANT = "Claimkeeper"
GIT = ["git", "-c", "safe.directory=" + str(ROOT)]


def run(binary, with_redis=False, systemd=False, matched_restore=False, redis_reenable=False, discard_rewards=False, website=None):
    if not os.environ.get("TEST_DB_HOST"):
        if website:
            # MySQL 8 is supported by both the MUD and the website baseline.
            os.environ.setdefault("TEST_DB_IMAGE", "mysql:8.0")
        wrapper = ROOT / "tests/async/with_disposable_mariadb.sh"
        os.execv(str(wrapper), [str(wrapper), sys.executable, str(Path(__file__).resolve()), str(binary),
                               *(["--redis"] if with_redis else []), *(["--systemd"] if systemd else []),
                               *(["--restore"] if matched_restore else []), *(["--redis-reenable"] if redis_reenable else []), *(["--discard-rewards"] if discard_rewards else []), *(["--website", str(website)] if website else [])])
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
    report = {"database_version": sql("SELECT VERSION()"),
              "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
              "source_diff_sha256": hashlib.sha256(subprocess.check_output([*GIT, "diff", "HEAD", "--", "src"], cwd=ROOT)).hexdigest(),
              "revision": subprocess.check_output([*GIT, "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "backend": "mariadb-primary", "redis": with_redis, "systemd": systemd, "matched_restore": matched_restore, "redis_reenable": redis_reenable, "preserve_rewards": not discard_rewards, "status": "running"}
    if website:
        report["website_revision"] = subprocess.check_output([*GIT, "rev-parse", "HEAD"], cwd=website, text=True).strip()
        report["website_diff_sha256"] = hashlib.sha256(subprocess.check_output([*GIT, "diff", "HEAD"], cwd=website)).hexdigest()
        artifact = hashlib.sha256()
        for path in sorted((website / "backend/dist").rglob("*")):
            if path.is_file():
                artifact.update(str(path.relative_to(website / "backend/dist")).encode() + b"\0")
                artifact.update(path.read_bytes())
        report["website_backend_tree_sha256"] = artifact.hexdigest()
        report["website_node_version"] = subprocess.check_output(["node", "--version"], text=True).strip()
    try:
        sql((ROOT / "migrations/bootstrap_multithread_safe.sql").read_text())
        for arguments in (("adopt", "--kind", "fresh_bootstrap"), ("run",)):
            result = subprocess.run([sys.executable, "scripts/migration_runner.py", *arguments],
                                    cwd=ROOT, env=env, capture_output=True, text=True)
            assert result.returncode == 0, result.stdout + result.stderr
        with tempfile.TemporaryDirectory(prefix="pwipe-runtime-", dir=None if matched_restore else ROOT / "bin/tests") as temporary:
            base = Path(temporary)
            root = base / "runtime" if matched_restore else base
            root.mkdir(mode=0o700, exist_ok=True)
            journey.make_fixture(root)
            if discard_rewards:
                (root / "lib/account_rewards.cfg").write_text("pwipe.preserve=false\nsummon.cooldown.seconds=3600\n")
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
            process = client = observer = redis_server = restored_redis_server = journal = None
            website_process = website_probe = web_mortal = None
            unit_path = pin_path = None
            unit_created = pin_created = False
            unit_name = "duris-pwipe-qualification-" + uuid.uuid4().hex + ".service"
            output_file = path.open("w")

            if website:
                website_root = root / "website"
                website_root.mkdir(mode=0o700)
                website_log = (website_root / "server.log").open("w")
                website_probe_log = (website_root / "probe.log").open("w")
                web_port = journey.available_ports()[0]
                web_env = dict(env, NODE_ENV="development", DB_PASSWORD=env["DB_PASSWD"],
                               TEST_DB_HOST="127.0.0.1", TEST_DB_PORT=env["DB_PORT"],
                               TEST_PWIPE_WEBSITE="1", TEST_WEBSITE_DIRECTORY=str(website_root),
                               HOST="127.0.0.1", PORT=str(web_port), SITE_URL="http://127.0.0.1:" + str(web_port),
                               ALLOWED_ORIGINS="http://127.0.0.1:" + str(web_port), MUD_DIR=str(root),
                               MUD_PROCESS_HOME=str(root), BACKUP_DIR=str(website_root / "backups"),
                               MUD_WS_URL="ws://127.0.0.1:" + str(websocket), MUD_DATABASE_MODE="shared",
                               MUD_REDIS_ENABLED="true", MUD_REDIS_HOST="127.0.0.1", MUD_REDIS_DB="0",
                               MUD_REDIS_AUTH_MODE="none", MUD_REDIS_TLS="false", CACHE_REDIS_DB="1",
                               DONATIONS_ENABLED="true", MUD_REDIS_DONATION_SECRET="synthetic-website-donation-secret-264",
                               KOFI_VERIFICATION_TOKEN="synthetic-kofi-verification-264", TEST_GAME_PASSWORD=journey.PASSWORD,
                               TEST_WEB_ACCOUNT=journey.ACCOUNT, TEST_WEB_EMAIL=journey.EMAIL,
                               TEST_WEB_OBSERVER_ACCOUNT=OBSERVER_ACCOUNT, TEST_WEB_FRESH_CHARACTER=journey.CHARACTER,
                               DURISWEB_SECRET="synthetic-website-bridge-secret-264", DOTENV_CONFIG_QUIET="true")
                env.update(DURISWEB_SECRET=web_env["DURISWEB_SECRET"],
                           REDIS_DONATION_SECRET=web_env["MUD_REDIS_DONATION_SECRET"],
                           REDIS_DONATION_SUBSCRIBER="TRUE", DURIS_WEBSOCKET="TRUE")
                loader = website / "backend/node_modules/tsx/dist/loader.mjs"
                web_node = ["node", "--import", str(loader)]
                web_probe = website / "backend/src/test/pwipeWebsiteProbe.ts"

            def website_command(phase, background=False):
                command = [*web_node, str(web_probe), phase]
                if background:
                    return subprocess.Popen(command, cwd=website_root, env=web_env,
                                            stdout=website_probe_log, stderr=subprocess.STDOUT)
                subprocess.run(command, cwd=website_root, env=web_env, check=True, timeout=120,
                               stdout=website_probe_log, stderr=subprocess.STDOUT)

            def website_start():
                nonlocal website_process
                website_process = subprocess.Popen([*web_node, "--import", str(website / "backend/src/test/setupEnvironment.ts"),
                                                     str(website / "backend/dist/index.js")], cwd=website_root,
                                                    env=web_env, stdout=website_log, stderr=subprocess.STDOUT,
                                                    start_new_session=True)
                until = time.monotonic() + 60
                while True:
                    assert website_process.poll() is None, "website exited during boot"
                    try:
                        with urllib.request.urlopen(web_env["SITE_URL"] + "/health", timeout=1) as response:
                            assert response.status == 200
                        return
                    except OSError:
                        assert time.monotonic() < until, "website health timeout"
                        time.sleep(.1)

            def website_stop():
                nonlocal website_process
                if website_process and website_process.poll() is None:
                    website_process.terminate()
                    try:
                        website_process.wait(timeout=20)
                    except subprocess.TimeoutExpired:
                        os.killpg(website_process.pid, signal.SIGKILL)
                        website_process.wait(timeout=10)
                        raise AssertionError("website graceful shutdown did not complete")
                    assert website_process.returncode == 0, "website shutdown failed"
                website_process = None

            def website_wait(marker):
                until = time.monotonic() + 40
                while not (website_root / marker).exists():
                    assert website_probe.poll() is None and time.monotonic() < until, "website probe did not reach " + marker
                    time.sleep(.1)

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

            def wait_old_world_checkpoint():
                key = env["REDIS_NAMESPACE"] + ":season:1:world_state:current"
                previous = int(redis("GET", key) or "0")
                deadline = time.monotonic() + 45
                while True:
                    current = int(redis("GET", key) or "0")
                    # One capture may already be in flight when the item drops.
                    if current >= previous + 2:
                        print("Post-drop world checkpoint acknowledged sequence=" + str(current), flush=True)
                        return
                    assert running() and time.monotonic() < deadline, "post-drop world checkpoint did not publish"
                    time.sleep(.1)

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
                nonlocal process, client, observer
                if website:
                    website_stop()
                if observer:
                    observer.close(); observer = None
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

            def reward_items(pid):
                rows = sql("SELECT name,obj_uid,vnum,item_type,weight,cost," +
                           ",".join("value" + str(i) for i in range(8)) +
                           " FROM player_items WHERE pid=" + str(pid) +
                           " AND name LIKE 'account_reward:%' ORDER BY name")
                items = {}
                for row in rows.splitlines():
                    name, *values = row.split("\t")
                    grant_id = int(name.split(":")[1])
                    assert grant_id not in items, "duplicate physical copy of one grant"
                    items[grant_id] = tuple(map(int, values))
                return items

            def check_claims(pid, expected):
                client.send("divineclaim list")
                client.expect("Divine reward commands:")
                if discard_rewards:
                    client.send("divineclaim summon 1")
                    client.expect("That reward number is not active.")
                else:
                    # The dismissed third grant must remain on cooldown through login/boot.
                    for number in (1, 2):
                        client.send("divineclaim summon " + str(number))
                        client.expect("already with this character")
                    client.send("divineclaim summon 3")
                    client.expect("is still recovering")
                save(CLAIMANT)
                assert reward_items(pid) == expected, "claim retry/login/boot changed reward instances"

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
                if website:
                    web_env.update(MUD_REDIS_PORT=env["REDIS_PORT"], CACHE_REDIS_PORT=env["REDIS_PORT"],
                                   MUD_REDIS_NAMESPACE=env["REDIS_NAMESPACE"])
                if matched_restore or redis_reenable:
                    env.update(REDIS_WORLD_STATE="TRUE", REDIS_WORLD_STATE_SECRET="synthetic-pwipe-restore-world-secret",
                               REDIS_WORLD_STATE_INTERVAL="5", REDIS_WORLD_STATE_MAX_AGE="3600")
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
                if redis_reenable:
                    old_floor_uid = int(sql("SELECT obj_uid FROM player_items WHERE pid=" + str(old_pid) + " AND vnum=1108"))
                    assert old_floor_uid > 0
                    client.send("drop sword"); client.expect("You drop a long steel sword.")
                    save(STAFF)
                    wait_old_world_checkpoint()
                old_items = sql("SELECT COUNT(*) FROM player_items WHERE pid=" + str(old_pid))
                assert int(old_items) > 0
                client.send("quit"); client.expect("ACCOUNT MENU", timeout=30)
                observer = journey.MudClient(plain)
                journey.create_character(observer, account=OBSERVER_ACCOUNT, character=OBSERVER,
                                         email="shutdown@example.invalid")
                observer.send("quit"); observer.expect("ACCOUNT MENU", timeout=30)
                observer_pid = int(sql("SELECT pid FROM player_data WHERE name='" + OBSERVER + "'"))
                stop()
                # Synthetic staff promotion while offline, as other real-server fixtures do.
                sql("UPDATE player_data SET level=62,highest_level=62 WHERE pid=" + str(old_pid))
                sql("UPDATE account_characters SET racewar=0 WHERE pid=" + str(old_pid))
                sql("UPDATE player_data SET level=60,highest_level=60 WHERE pid=" + str(observer_pid))
                sql("UPDATE account_characters SET racewar=0 WHERE pid=" + str(observer_pid))
                sql("INSERT INTO account_banks(account_name,racewar,bank_platinum) VALUES('" + journey.ACCOUNT + "',1,9)")
                sql("INSERT INTO currency_bank_baseline(bank_id,opening_copper,opening_silver,opening_gold,opening_platinum) "
                    "SELECT id,0,0,0,9 FROM account_banks")
                (root / "Players/a/old-season").write_text("old pfile")
                (root / "Ships/old-season").write_text("old ship")
                (root / "Players/Backup/preserve").write_text("archive")
                if matched_restore:
                    # All game writers are stopped; this private Redis has no external writers.
                    # Keep supplements outside the immutable SQL generation and bind their hashes.
                    import tarfile
                    from test_persistence_backup import policy
                    sys.path.insert(0, str(ROOT / "scripts"))
                    import persistence_backup as backup
                    import persistence_restore as restore
                    import build_restore_qualifier as native
                    qualifier = native.build()
                    recovery = base / "recovery"
                    recovery.mkdir(mode=0o700)
                    p = policy(base)
                    p["live_roots"] = [root]
                    p["journal_roots"] = {"critical": root / "journals/critical"}
                    (root / "journals").chmod(0o700)
                    p["journal_roots"]["critical"].chmod(0o700)
                    policy_file = recovery / "policy.json"
                    backup.write_json(policy_file, {key: {name: str(path) for name, path in value.items()}
                                                   if key == "journal_roots" else value
                                                   for key, value in p.items()} | {
                                                       "root": str(p["root"]), "restore_root": str(p["restore_root"]),
                                                       "live_roots": [str(root)]})
                    world_key = env["REDIS_NAMESPACE"] + ":season:1:world_state:current"
                    world_generation = redis("GET", world_key)
                    assert world_generation, "stopped old world must have a real recovery generation"
                    sql("INSERT INTO account_bound_rewards(account_name,remaining_pwipes,created_at) VALUES('" +
                        journey.ACCOUNT + "',3,NOW())")
                    frozen_roster = sql("SELECT pid,name,level,active FROM player_data ORDER BY pid")
                    captured = subprocess.run([sys.executable, str(ROOT / "scripts/persistence_backup.py"),
                                               "--policy", str(policy_file), "backup"], env=env,
                                              capture_output=True, text=True, check=True)
                    generation = p["root"] / json.loads(captured.stdout)["generation"]
                    backup.verify(generation)
                    filesystem = recovery / "runtime.tar"
                    with tarfile.open(filesystem, "w") as archive:
                        for entry in sorted(root.iterdir()):
                            if entry.name not in ("redis", "logs", "launcher.out", "test-tmp", "areas", "docs"):
                                archive.add(entry, arcname=entry.name)
                    filesystem.chmod(0o600)
                    redis_rdb = recovery / "redis.rdb"
                    subprocess.run(["redis-cli", "-h", "127.0.0.1", "-p", env["REDIS_PORT"],
                                    "--rdb", str(redis_rdb)], check=True, capture_output=True)
                    redis_rdb.chmod(0o600)
                    matched = {"epoch": 1, "sql_generation": generation.name,
                               "sql_manifest_sha256": backup.digest(generation / "manifest.json"),
                               "filesystem_sha256": backup.digest(filesystem), "redis_sha256": backup.digest(redis_rdb),
                               "binary_sha256": report["binary_sha256"], "world_generation": world_generation}
                    backup.write_json(recovery / "matched.json", matched)
                    backup.sync_tree(recovery)
                    report["matched_capture"] = matched
                    print("Frozen matched SQL/journal, filesystem and authenticated Redis world generation captured", flush=True)
                boot()
                client = journey.reconnect_character(plain, character=STAFF)
                for lifetime in ("permanent", "days 7", "wipes 1", "wipes 3"):
                    client.send("divineclaim mace " + OBSERVER_ACCOUNT + " " + lifetime)
                    client.expect("The source item remains in your inventory.")
                save(STAFF)
                grants = []
                for row in sql("SELECT id,reward_vnum,HEX(template_json),COALESCE(UNIX_TIMESTAMP(expires_at),0) "
                               "FROM account_bound_rewards WHERE account_name='" + OBSERVER_ACCOUNT + "' ORDER BY id").splitlines():
                    grant_id, vnum, encoded, expires = row.split("\t")
                    template = json.loads(bytes.fromhex(encoded))
                    grants.append(dict(id=int(grant_id), encoded=encoded, expires=expires,
                                       payload=(int(vnum), template["type"], template["weight"], template["cost"], *template["values"])))
                assert len(grants) == 4
                observer = journey.reconnect_character(plain, account=OBSERVER_ACCOUNT, character=OBSERVER)
                observer.send("shutdown pwipe confirm yes"); observer.expect("Pardon?")
                client.send("grant " + OBSERVER + " shutdown")
                client.expect("You have granted the command 'shutdown'")
                observer.expect("granted you the use of the 'shutdown' command")
                observer.send("shutdown reboot 10 retained delegated request")
                observer.expect("retained delegated request")
                observer.send("shutdown pwipe confirm yes"); observer.expect("higher level")
                observer.send("shutdown"); observer.expect("Scheduled reboot cancelled")
                observer.send("shutdown reboot 10 revoke permission control")
                observer.expect("revoke permission control")
                client.send("revoke " + OBSERVER + " shutdown")
                client.expect("You have revoked the command 'shutdown'")
                observer.expect("revoked your ability to use the 'shutdown' command")
                observer.expect("Scheduled reboot cancelled", timeout=15)
                save(STAFF) # Flush earlier broadcasts before the next command group.
                observer.send("save"); observer.expect("Save complete for " + OBSERVER + ".")
                client.send("shutdown reboot 10 retained malformed-request control")
                client.expect("retained malformed-request control")
                for invalid, message in (("pwipe", "You must"), ("pwipe confirm", "You must"),
                                         ("pwipe confirm yes extra", "You must"),
                                         ("reboot -1", "Invalid shutdown delay"),
                                         ("reboot 2junk", "Invalid shutdown delay")):
                    client.send("shutdown " + invalid); client.expect(message)
                client.send("shutdown"); client.expect("Scheduled reboot cancelled")
                save(STAFF)
                for _ in range(2):
                    client.send("shutdown pwipe confirm yes"); client.expect("five")
                    observer.expect("Confirmed player wipe")
                client.send("quit"); client.expect("ACCOUNT MENU", timeout=30)
                observer.expect("Scheduled pwipe cancelled", timeout=15)
                client.close(); client = journey.reconnect_character(plain, character=STAFF)
                client.send("shutdown pwipe confirm yes"); client.expect("five")
                observer.expect("Confirmed player wipe")
                client.close(); client = None
                observer.expect("Scheduled pwipe cancelled", timeout=15)
                client = journey.reconnect_character(plain, character=STAFF, expected_room=None)
                client.send("look"); client.expect("The Regression Arena")
                save(STAFF)
                observer.close(); observer = None
                assert sql("SELECT CONCAT(season_epoch,':',reset_status) FROM season_reset_state") == "1:active"
                assert (root / "Players/a/old-season").read_text() == "old pfile"
                report["operator_assertions"] = "mortal/ungranted dispatch refusal, trusted granted shutdown and live revocation, underlevel pwipe refusal preserving reboot, malformed input preserves countdown, repeated requests, issuer menu/connection departure cancels, reconnect/save and unchanged epoch/files"
                print("Real operator permissions, malformed/repeated requests and menu/link disconnect cancellation passed", flush=True)
                if redis_reenable:
                    assert "restored world recovery generation" in journey.runtime_logs(root)
                    client.send("get sword"); client.expect("get a long steel sword")
                    client.send("drop sword"); client.expect("You drop a long steel sword.")
                    save(STAFF)
                    wait_old_world_checkpoint()
                    client.send("quit"); client.expect("ACCOUNT MENU", timeout=30)
                    stop()
                    old_world_key = env["REDIS_NAMESPACE"] + ":season:1:world_state:current"
                    old_world_sequence = redis("GET", old_world_key)
                    assert old_world_sequence
                    old_payload_key = env["REDIS_NAMESPACE"] + ":season:1:world_state:generation:" + old_world_sequence
                    def old_payload_hash():
                        payload = subprocess.check_output(["redis-cli", "--raw", "-h", "127.0.0.1", "-p", env["REDIS_PORT"],
                                                           "DUMP", old_payload_key])
                        assert redis("EXISTS", old_payload_key) == "1"
                        return hashlib.sha256(payload).hexdigest()
                    old_payload_sha256 = old_payload_hash()
                    report["retained_old_world"] = dict(epoch=1, sequence=old_world_sequence,
                                                        payload_sha256=old_payload_sha256, floor_item_uid=old_floor_uid)
                    env["REDIS"] = "FALSE"
                    boot()
                    assert "redis disabled (set REDIS=TRUE" in journey.runtime_logs(root)
                    client = journey.reconnect_character(plain, character=STAFF)
                    print("Authenticated old world/floor marker accepted; Redis disabled for the actual wipe", flush=True)
                if with_redis:
                    old_keys = [env["REDIS_NAMESPACE"] + ":season:1:" + suffix for suffix in
                                ("cache:pwipe-sentinel", "presence:session:pwipe-sentinel",
                                 "presence_op:pwipe-sentinel", "world_state:generation:pwipe-sentinel")]
                    old_keys.append("mud:cache:pwipe-sentinel")
                    retained_keys = ["unrelated:pwipe-sentinel", "duris:local:other:season:1:cache:pwipe-sentinel"]
                    for key in old_keys + retained_keys:
                        assert redis("SET", key, "fixture") == "OK"
                if website:
                    website_command("setup")
                    website_start()
                    website_probe = website_command("old", background=True)
                    website_wait("old-peer-ready")
                    web_mortal = journey.MudClient(plain)
                    journey.create_character(web_mortal, account="Webacct", character="Webmortal", email="web@example.invalid")
                    website_wait("old-verified")
                    website_stop()
                    assert website_probe.wait(timeout=15) == 0, "old website probe failed"
                    website_probe = None
                    web_mortal.send("quit"); web_mortal.expect("ACCOUNT MENU", timeout=30)
                    web_mortal.close(); web_mortal = None
                    # Donation publication remains disabled until the new website starts.
                    assert sql("SELECT status FROM donation_outbox") == "pending"
                    sql("UPDATE web_settings SET setting_value='true' WHERE setting_key='hook_enabled_donation_delivery'")
                    print("Normal website old-season HTTP/presence/websocket and graceful drain passed", flush=True)
                began = time.monotonic()
                wall_began = time.time()
                report["schedule_wall_time"] = wall_began
                client.send("shutdown pwipe confirm yes"); client.expect("five")
                next_progress = began + 60
                assert int(sql("SELECT COUNT(*) FROM account_bound_reward_summons WHERE pid=" + str(observer_pid))) > 0
                retired_reward_uids = {int(uid) for uid in sql("SELECT obj_uid FROM player_items WHERE pid=" +
                                                            str(observer_pid) + " AND name LIKE 'account_reward:%'").splitlines()}
                assert retired_reward_uids, "old body must actually hold a reward before reset"
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
                    expected_old_keys = str(len(old_keys)) if redis_reenable else "0"
                    assert redis("EXISTS", *old_keys) == expected_old_keys
                    assert redis("MGET", *retained_keys).splitlines() == ["fixture"] * len(retained_keys)
                    if redis_reenable:
                        assert redis("GET", old_world_key) == old_world_sequence
                        assert old_payload_hash() == old_payload_sha256
                        env["REDIS"] = "TRUE"
                        report["redis_reset_assertions"] = "disabled wipe retained old authenticated payload and keys; re-enable uses new epoch"
                        print("Disabled Redis retained the old authenticated generation; re-enabling after epoch 2 activation", flush=True)
                    else:
                        report["redis_reset_assertions"] = "old scoped/legacy sentinels removed; unrelated namespaces preserved"
                        print("Real Redis reset removed old epoch sentinels and preserved unrelated namespaces", flush=True)
                client.close(); client = None; process = None
                assert sql("SELECT CONCAT(season_epoch,':',reset_status) FROM season_reset_state") == "2:active"
                assert sql("SELECT COUNT(*) FROM account_banks") == "0"
                assert sql("SELECT COUNT(*) FROM account_bound_reward_summons") == "0"
                surviving = sql("SELECT id,HEX(template_json),COALESCE(UNIX_TIMESTAMP(expires_at),0),"
                                "COALESCE(remaining_pwipes,0) FROM account_bound_rewards WHERE account_name='" +
                                OBSERVER_ACCOUNT + "' ORDER BY id")
                expected_grants = [] if discard_rewards else [grants[i] for i in (0, 1, 3)]
                assert surviving == "\n".join("\t".join((str(grant["id"]), grant["encoded"], grant["expires"],
                                                         "2" if grant is grants[3] else "0")) for grant in expected_grants)
                assert sql("SELECT COUNT(*) FROM player_items WHERE pid=" + str(old_pid)) == "0"
                new_pid = int(sql("SELECT pid FROM player_data WHERE name='" + STAFF + "' AND active=1"))
                assert sql("SELECT active FROM player_data WHERE pid=" + str(observer_pid)) == "0"
                assert new_pid > old_pid
                assert not (root / "Players/a/old-season").exists()
                assert not (root / "Ships/old-season").exists()
                assert (root / "Players/Backup/preserve").read_text() == "archive"
                report.update(countdown_seconds=round(wall_elapsed, 2), old_pid=old_pid, new_staff_pid=new_pid)
                print("Real command/launcher/filesystem reset passed; booting the new season", flush=True)
                boot()
                if redis_reenable:
                    assert "restored world recovery generation" not in journey.runtime_logs(root)
                    assert old_payload_hash() == old_payload_sha256
                client = journey.reconnect_character(plain, character=STAFF)
                if redis_reenable:
                    client.send("get sword"); client.expect("You do not see a sword here.")
                client.send("score"); client.expect("Level")
                save(STAFF)
                if with_redis:
                    # Staff login applies wizard invisibility; public presence
                    # must not reveal that body. Check a visible mortal below.
                    assert redis("KEYS", env["REDIS_NAMESPACE"] + ":season:2:presence:session:*:" + str(new_pid)) == ""
                    assert redis("EXISTS", *old_keys) == expected_old_keys
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
                client = journey.MudClient(plain)
                journey.create_character(client, existing_account=True, account=OBSERVER_ACCOUNT, character=CLAIMANT)
                claimant_pid = int(sql("SELECT pid FROM player_data WHERE name='" + CLAIMANT + "' AND active=1"))
                assert claimant_pid > observer_pid
                if discard_rewards:
                    client.send("divineclaim list"); client.expect("Your account has no active divine rewards.")
                    claimed_items = {}
                else:
                    # Login summons the oldest eligible grant; explicitly summon the rest.
                    # Character creation consumes output through the later starter-kit message.
                    assert b"A divine account reward begins to materialize:" in client.transcript
                    for number in (2, 3):
                        client.send("divineclaim summon " + str(number))
                        client.expect("A divine account reward begins to materialize:")
                    save(CLAIMANT)
                    claimed_items = reward_items(claimant_pid)
                    assert set(claimed_items) == {grant["id"] for grant in expected_grants}
                    assert len({item[0] for item in claimed_items.values()}) == 3
                    for grant in expected_grants:
                        assert claimed_items[grant["id"]][1:] == grant["payload"], "exact reward payload changed"
                        assert claimed_items[grant["id"]][0] not in retired_reward_uids
                    for number in (1, 2, 3):
                        client.send("divineclaim summon " + str(number)); client.expect("already with this character")
                    save(CLAIMANT)
                    assert reward_items(claimant_pid) == claimed_items
                    client.send("divineclaim dismiss 3"); client.expect("It may be summoned again in")
                    del claimed_items[grants[3]["id"]]
                check_claims(claimant_pid, claimed_items)
                client.send("quit"); client.expect("ACCOUNT MENU", timeout=30)
                client.close(); client = journey.reconnect_character(plain, account=OBSERVER_ACCOUNT, character=CLAIMANT)
                check_claims(claimant_pid, claimed_items)
                client.send("quit"); client.expect("ACCOUNT MENU", timeout=30)
                client.close(); client = None
                fresh_pid = int(sql("SELECT pid FROM player_data WHERE name='" + journey.CHARACTER + "' AND active=1"))
                assert fresh_pid > new_pid
                before = sql("SELECT exp,copper,silver,gold,platinum FROM player_data WHERE pid=" + str(fresh_pid))
                assert int(sql("SELECT COUNT(*) FROM player_items WHERE pid=" + str(fresh_pid))) > 0
                stop()
                if redis_reenable:
                    new_world_sequence = redis("GET", env["REDIS_NAMESPACE"] + ":season:2:world_state:current")
                    assert new_world_sequence
                boot()
                if redis_reenable:
                    assert "restored world recovery generation sequence=" + new_world_sequence + " " in journey.runtime_logs(root)
                client = journey.reconnect_character(plain)
                client.send("inventory"); client.expect("a banana")
                save(journey.CHARACTER)
                assert sql("SELECT exp,copper,silver,gold,platinum FROM player_data WHERE pid=" + str(fresh_pid)) == before
                assert sql("SELECT active FROM player_data WHERE pid=" + str(old_pid)) == "0"
                client.send("quit"); client.expect("ACCOUNT MENU", timeout=30)
                client.close(); client = journey.reconnect_character(plain, account=OBSERVER_ACCOUNT, character=CLAIMANT)
                check_claims(claimant_pid, claimed_items)
                assert sql("SELECT COUNT(*) FROM account_bound_reward_summons WHERE pid=" + str(observer_pid)) == "0"
                if website:
                    # The probe subscribes to the new donation channel before the publisher starts.
                    website_probe = website_command("new", background=True)
                    website_wait("new-subscribed")
                    website_start()
                    # The real game-thread consumer must accept the signed queued event.
                    client.expect("season-queued-fixture", timeout=30)
                    website_wait("new-peer-ready")
                    # Reconnect a visible mortal through the actual MUD producer.
                    client.send("quit"); client.expect("ACCOUNT MENU", timeout=30)
                    client.close(); client = journey.reconnect_character(plain)
                    website_wait("new-verified")
                    assert website_probe.wait(timeout=15) == 0, "new website probe failed"
                    website_probe = None
                    report["website_assertions"] = json.loads((website_root / "report.json").read_text())
                    report["website_assertions"]["signedDonationAppliedByMud"] = True
                    website_stop()
                report.update(reward_claim_pid=claimant_pid, reward_claim_ids=sorted(claimed_items),
                              reward_claim_assertions="real exact permanent/day/finite grants; policy/reset clears old summons; fresh account character claims or refuses under discard policy; unique new UIDs/exact payload; repeated summon, dismiss cooldown, save/reconnect/second boot")
                stop()
                report.update(status="passed", fresh_pid=fresh_pid,
                              assertions="real command/cancel/countdown/launcher/filesystem/staff login/fresh combat/save/reconnect/reboot")
                print("Recreated Overlord login and fresh mortal combat/loot/save/reconnect/second boot passed", flush=True)
                if redis_reenable:
                    assert old_payload_hash() == old_payload_sha256
                    assert redis("GET", old_world_key) == old_world_sequence
                    assert redis("EXISTS", *old_keys) == expected_old_keys
                    assert redis("MGET", *retained_keys).splitlines() == ["fixture"] * len(retained_keys)
                    report["redis_reenable_assertions"] = "valid old snapshot/floor marker before wipe; disabled reset retains old payload bytes; epoch-2 boot ignores old marker; fresh presence/gameplay/save/reconnect/new-scope recovery succeeds; unrelated keys retained"
                    print("Redis re-enable ignored retained authenticated epoch-1 payloads and recovered fresh epoch-2 gameplay", flush=True)
                if matched_restore:
                    source_root = root
                    source_world_key = env["REDIS_NAMESPACE"] + ":season:2:world_state:current"
                    source_world_generation = redis("GET", source_world_key)
                    assert source_world_generation
                    source_epoch = sql("SELECT CONCAT(season_epoch,':',reset_status) FROM season_reset_state")
                    source_roster = sql("SELECT pid,name,level,active FROM player_data ORDER BY pid")
                    assert source_epoch == "2:active"
                    assert sql("SELECT remaining_pwipes FROM account_bound_rewards WHERE account_name='" + journey.ACCOUNT + "'") == "2"
                    backup.verify(generation)
                    assert backup.digest(generation / "manifest.json") == matched["sql_manifest_sha256"]
                    assert backup.digest(filesystem) == matched["filesystem_sha256"]
                    assert backup.digest(redis_rdb) == matched["redis_sha256"]
                    ledger = recovery / "tombstones.json"
                    backup.write_json(ledger, dict(version=1, captured_at=int(time.time()), tombstones=[],
                                                   policy_sha256=backup.digest(ROOT / "migrations/data_lifecycle_manifest.json")))
                    restore.tombstone_preflight(ledger, p, backup.verify(generation)["created"])
                    candidate = base / "restored"
                    candidate.mkdir(mode=0o700)
                    backup.write_json(candidate / "ISOLATED_RESTORE", {"generation": generation.name})
                    restored_root = candidate / "runtime"
                    restored_root.mkdir(mode=0o700)
                    with tarfile.open(filesystem) as archive:
                        archive.extractall(restored_root, filter="data")
                    for name in ("areas", "docs"):
                        (restored_root / name).symlink_to(ROOT / name, target_is_directory=True)
                    shutil.copytree(generation / "journals", candidate / "journals")
                    backup.run([str(qualifier), "--receipts", str(candidate)], phase="matched_restore_receipts")
                    original_env = dict(env)
                    env["REDIS_PORT"] = str(journey.available_ports()[0])
                    restored_redis = candidate / "redis"
                    restored_redis.mkdir(mode=0o700)
                    shutil.copy2(redis_rdb, restored_redis / "dump.rdb")
                    restored_redis_server = subprocess.Popen(["redis-server", "--bind", "127.0.0.1", "--port", env["REDIS_PORT"],
                                                     "--save", "", "--appendonly", "no", "--dir", str(restored_redis)],
                                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    for _ in range(100):
                        probe = subprocess.run(["redis-cli", "-p", env["REDIS_PORT"], "PING"], capture_output=True, text=True)
                        if probe.returncode == 0 and probe.stdout.strip() == "PONG": break
                        assert restored_redis_server.poll() is None
                        time.sleep(.05)
                    else: raise AssertionError("restored Redis did not start")
                    assert redis("GET", world_key) == world_generation
                    def restore_environment():
                        env.clear(); env.update(original_env)
                    with restore.private_database(candidate) as restored_env, contextlib.ExitStack() as cleanup:
                        cleanup.callback(restore_environment)
                        restore.database_import(generation, restored_env)
                        restore.database_qualify(restored_env, "matched_restore_import")
                        def restored_sql(statement):
                            return backup.run(["mysql", "--no-defaults", "--protocol=socket", "--socket=" + restored_env["DB_SOCKET"],
                                               "--user=restore", "-N", "-B", "duris_restore", "-e", statement],
                                              phase="matched_restore_check", env=restored_env).decode().strip()
                        assert restored_sql("SELECT CONCAT(season_epoch,':',reset_status) FROM season_reset_state") == "1:active"
                        assert restored_sql("SELECT pid,name,level,active FROM player_data ORDER BY pid") == frozen_roster
                        assert restored_sql("SELECT COUNT(*) FROM player_items WHERE pid=" + str(old_pid)) == old_items
                        assert restored_sql("SELECT bank_platinum FROM account_banks") == "9"
                        assert restored_sql("SELECT remaining_pwipes FROM account_bound_rewards") == "3"
                        root = restored_root
                        env.update({key: value for key, value in restored_env.items() if key.startswith("DB_") or key == "MYSQL_PWD"},
                                   CRITICAL_COMMAND_JOURNAL_DIR=str(candidate / "journals/critical"))
                        assert (root / "Players/a/old-season").read_text() == "old pfile"
                        assert (root / "Ships/old-season").read_text() == "old ship"
                        assert (root / "Players/Backup/preserve").read_text() == "archive"
                        offset = len(journey.runtime_logs(root))
                        boot()
                        client = journey.reconnect_character(plain, character=STAFF)
                        client.send("inventory"); client.expect("mace")
                        save(STAFF)
                        stop(); boot()
                        client = journey.reconnect_character(plain, character=STAFF)
                        save(STAFF); stop()
                        assert "restored world recovery generation" in journey.runtime_logs(root)[offset:]
                        restore.database_qualify(restored_env, "matched_restore_after_gameplay")
                        assert restored_sql("SELECT pid FROM player_data WHERE name='" + STAFF + "' AND active=1") == str(old_pid)
                        assert restored_sql("SELECT COUNT(*) FROM player_data WHERE pid=" + str(fresh_pid)) == "0"
                    restored_redis_server.terminate(); restored_redis_server.wait(timeout=10)
                    restored_redis_server = None
                    assert not (source_root / "Players/a/old-season").exists()
                    assert not (source_root / "Ships/old-season").exists()
                    assert redis("GET", source_world_key) == source_world_generation
                    assert redis("EXISTS", world_key) == "0"
                    assert redis("MGET", *retained_keys).splitlines() == ["fixture"] * len(retained_keys)
                    assert sql("SELECT CONCAT(season_epoch,':',reset_status) FROM season_reset_state") == source_epoch
                    assert sql("SELECT pid,name,level,active FROM player_data ORDER BY pid") == source_roster
                    backup.verify(generation)
                    assert backup.digest(filesystem) == matched["filesystem_sha256"]
                    assert backup.digest(redis_rdb) == matched["redis_sha256"]
                    report["matched_restore_assertions"] = "frozen matched hashes/epoch, fresh private DB, banks/rewards/old PID/files restored, authenticated world recovery, account login/save/reconnect/reboot, source SQL/files/Redis/generation unchanged"
                    print("Matched pre-wipe SQL/filesystem/Redis restore, original account/body/world and second boot passed", flush=True)
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
                if restored_redis_server:
                    restored_redis_server.terminate(); restored_redis_server.wait(timeout=10)
                if redis_server:
                    redis_server.terminate(); redis_server.wait(timeout=10)
                if website:
                    if website_probe and website_probe.poll() is None:
                        website_probe.terminate(); website_probe.wait(timeout=10)
                    if web_mortal:
                        web_mortal.close()
                    website_log.close(); website_probe_log.close()
                    shutil.copy2(website_root / "server.log", output / "pwipe-website-server.log")
                    shutil.copy2(website_root / "probe.log", output / "pwipe-website-probe.log")
                output_file.close()
    except Exception:
        report["status"] = "failed"
        raise
    finally:
        suffix = "mariadb-redis-systemd" if systemd and with_redis else "mariadb-redis" if with_redis else "mariadb"
        suffix += "-restore" if matched_restore else "-reenable" if redis_reenable else ""
        suffix += "-discard-rewards" if discard_rewards else ""
        suffix += "-website" if website else ""
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
    parser.add_argument("--website", type=Path, help="run the normal companion backend against the private Redis/MUD journey")
    parser.add_argument("--discard-rewards", action="store_true", help="qualify pwipe.preserve=false and refused new-character claims")
    parser.add_argument("--redis-reenable", action="store_true", help="wipe with Redis off then re-enable against retained old recovery data (requires --redis)")
    parser.add_argument("--restore", action="store_true", help="rehearse a matched pre-wipe restore (requires --redis)")
    parser.add_argument("--redis", action="store_true", help="use a disposable Redis process")
    parser.add_argument("--systemd", action="store_true", help="use a disposable system unit (requires root)")
    parser.add_argument("binary", nargs="?", default=str(ROOT / "bin/server/dms_new"))
    options = parser.parse_args()
    if options.restore and (not options.redis or options.systemd or options.flatfile_rejection):
        parser.error("--restore requires --redis and the direct MariaDB launcher")
    if options.redis_reenable and (not options.redis or options.restore or options.systemd or options.flatfile_rejection):
        parser.error("--redis-reenable requires --redis and the direct MariaDB launcher without --restore")
    if options.discard_rewards and (options.restore or options.flatfile_rejection):
        parser.error("--discard-rewards requires a MariaDB wipe journey without --restore")
    if options.website:
        if not options.redis or options.systemd or options.restore or options.redis_reenable or options.flatfile_rejection or options.discard_rewards:
            parser.error("--website requires the direct --redis preserving MariaDB journey")
        options.website = options.website.resolve(strict=True)
        for name in (".env", "backend/.env", "backend/.env.test"):
            if (options.website / name).exists():
                parser.error("--website refuses a checkout with runtime environment files")
        for name in ("backend/dist/index.js", "backend/src/test/pwipeWebsiteProbe.ts", "backend/node_modules/tsx/dist/loader.mjs"):
            if not (options.website / name).is_file():
                parser.error("--website requires the built backend and native probe")
    binary = Path(options.binary).resolve(strict=True)
    if options.flatfile_rejection:
        assert not options.redis and not options.systemd and not options.restore
        flatfile_rejection(binary)
    else:
        run(binary, options.redis, options.systemd, options.restore, options.redis_reenable, options.discard_rewards, options.website)
