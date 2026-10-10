#!/usr/bin/env python3

import os
import json
import pathlib
import shutil
import subprocess
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[2]
SOURCE = ROOT / "scripts/cycle_mud.sh"


def run(script: pathlib.Path, env: dict[str, str], *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(script), *arguments],
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        # A successful cycle includes a 10-second shutdown delay and a real
        # backup filesystem sync. Allow headroom for concurrent CI builds: the
        # old 20-second budget left everything but that fixed sleep barely ten
        # seconds, which held on an idle machine and not on a loaded runner
        # where this suite runs eight tests at a time and several build a server.
        timeout=60,
    )


subprocess.run(["bash", "-n", str(SOURCE)], check=True)
subprocess.run(["bash", "-n", str(ROOT / ".env.example")], check=True)

# The stop reason the launcher reports for each exit code, from its own case block: a
# signal exit (128 plus the signal) is named, not reported as unknown.
cycle = SOURCE.read_text()
reasons = cycle[cycle.index("case $RESULT in", cycle.index("# determine the reason")):]
reasons = reasons[:reasons.index("esac") + len("esac")]
for code, reason in (("0", "shutdown"), ("139", "crash"), ("137", "killed by SIGKILL"),
                     ("143", "killed by SIGTERM"), ("134", "killed by SIGABRT"),
                     ("200", "unknown"), ("3", "unknown")):
    stopped = subprocess.run(["bash", "-c", f"RESULT={code}\n{reasons}\necho \"$STOP_REASON\""],
                             text=True, capture_output=True, check=True).stdout.strip()
    if stopped != reason:
        raise AssertionError(f"exit {code} was reported as {stopped!r}, not {reason!r}")
# The boot email attaches the previous run's exit log from the checkout's logs.
if '"/logs/old-logs/' in cycle or '-f "logs/old-logs/$DATESTR/exit"' not in cycle:
    raise AssertionError("the boot email looks for the exit log outside the checkout")

example = (ROOT / ".env.example").read_text()
if "GAME_ACCOUNT_PASSWORD=<password>" in example:
    raise AssertionError(".env.example contains a shell-redirection password placeholder")

with tempfile.TemporaryDirectory(prefix="duris-flatfile-launcher-") as temporary:
    project = pathlib.Path(temporary)
    scripts = project / "scripts"
    scripts.mkdir()
    script = scripts / "cycle_mud.sh"
    shutil.copy2(SOURCE, script)
    shutil.copy2(ROOT / "scripts/backup_pfiles.sh", scripts / "backup_pfiles.sh")

    shutil.copy2(ROOT / "scripts/persistence_backup.py", scripts / "persistence_backup.py")
    (project / "migrations").mkdir()
    shutil.copy2(ROOT / "migrations/runtime_compatibility_manifest.json",
                 project / "migrations/runtime_compatibility_manifest.json")
    policy = json.loads((ROOT / "scripts/backup_policy.example.json").read_text())
    policy.update(approved=True, custodian="synthetic-launcher", root=str(project / "backups"),
                  restore_root=str(project / "restore"), live_roots=[str(project / "state")],
                  journal_roots={"critical": str(project / "critical-command-journal")},
                  replica_root=None, min_free_bytes=0)
    (project / "critical-command-journal").mkdir(mode=0o700)
    config = project / "backup-policy.json"
    config.write_text(json.dumps(policy))
    config.chmod(0o600)

    flat_env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "ENVIRONMENT": "local",
        "PERSISTENCE_MODE": "flatfile-primary",
        "FLATFILE_STATE_DIR": str(project / "state"),
        "BACKUP_POLICY_FILE": str(config),
        "REDIS": "1",
    }
    checked = run(script, flat_env, "--check-config")
    if checked.returncode != 0 or "database-independent configuration" not in checked.stdout:
        raise AssertionError("flat-file config check required a database:\n" + checked.stdout)

    alternate_port_env = dict(flat_env)
    alternate_port_env["DURIS_DEV_PORT"] = "14000"
    checked = run(script, alternate_port_env, "--dev", "--check-config")
    if checked.returncode != 0 or "database-independent configuration" not in checked.stdout:
        raise AssertionError("alternate development port was rejected:\n" + checked.stdout)

    production_port_env = dict(flat_env)
    production_port_env["DURIS_DEV_PORT"] = "7777"
    rejected = run(script, production_port_env, "--dev", "--check-config")
    if rejected.returncode == 0 or "must not use production port 7777" not in rejected.stdout:
        raise AssertionError("development launcher accepted production port 7777")

    invalid_port_env = dict(flat_env)
    invalid_port_env["DURIS_DEV_PORT"] = "not-a-port"
    rejected = run(script, invalid_port_env, "--dev", "--check-config")
    if rejected.returncode == 0 or "must be a decimal port" not in rejected.stdout:
        raise AssertionError("development launcher accepted an invalid port")

    production_env = dict(flat_env)
    production_env["ENVIRONMENT"] = "production"
    production_env["DURIS_DEV_PORT"] = "14000"
    rejected = run(script, production_env, "--dev", "--check-config")
    if rejected.returncode == 0 or "require ENVIRONMENT=local" not in rejected.stdout:
        raise AssertionError("development launcher accepted a production environment")

    production_check_env = dict(flat_env)
    production_check_env.update(
        {
            "ENVIRONMENT": "production",
            "DURISWEB_SECRET": "0123456789abcdef0123456789abcdef",
        }
    )
    checked = run(script, production_check_env, "--production", "--check-config")
    if checked.returncode != 0 or "database-independent configuration" not in checked.stdout:
        raise AssertionError("valid production secret was rejected:\n" + checked.stdout)

    shared_host_env = dict(production_check_env)
    shared_host_env["DURIS_PRODUCTION_PORT"] = "14000"
    checked = run(script, shared_host_env, "--production", "--check-config")
    if checked.returncode != 0 or "database-independent configuration" not in checked.stdout:
        raise AssertionError("configured production port was rejected:\n" + checked.stdout)

    for invalid_production_port in ("0", "04000", "65536", "not-a-port"):
        invalid_production_env = dict(production_check_env)
        invalid_production_env["DURIS_PRODUCTION_PORT"] = invalid_production_port
        rejected = run(script, invalid_production_env, "--production", "--check-config")
        if rejected.returncode == 0 or "DURIS_PRODUCTION_PORT must be a decimal port" not in rejected.stdout:
            raise AssertionError(f"production launcher accepted port {invalid_production_port!r}")

    colliding_dev_env = dict(flat_env)
    colliding_dev_env.update({"DURIS_PRODUCTION_PORT": "14000", "DURIS_DEV_PORT": "14000"})
    rejected = run(script, colliding_dev_env, "--dev", "--check-config")
    if rejected.returncode == 0 or "must not use production port 14000" not in rejected.stdout:
        raise AssertionError("development launcher accepted the configured production port")

    placeholder_secret_env = dict(production_check_env)
    placeholder_secret_env["DURISWEB_SECRET"] = "put-secret-here"
    rejected = run(script, placeholder_secret_env, "--production", "--check-config")
    if rejected.returncode == 0 or "must not use the example placeholder" not in rejected.stdout:
        raise AssertionError("production launcher accepted the public example secret")

    short_previous_secret_env = dict(production_check_env)
    short_previous_secret_env["DURISWEB_SECRET_PREVIOUS"] = "short-old-key"
    rejected = run(script, short_previous_secret_env, "--production", "--check-config")
    if rejected.returncode == 0 or "must be empty" not in rejected.stdout:
        raise AssertionError("production launcher accepted a weak previous secret")

    missing_root = dict(flat_env)
    del missing_root["FLATFILE_STATE_DIR"]
    rejected = run(script, missing_root, "--check-config")
    if rejected.returncode == 0 or "FLATFILE_STATE_DIR is required" not in rejected.stdout:
        raise AssertionError("flat-file config accepted a missing state root")

    db_env = {
        "PATH": flat_env["PATH"],
        "ENVIRONMENT": "local",
        "PERSISTENCE_MODE": "mariadb-primary",
    }
    rejected = run(script, db_env, "--check-config")
    if rejected.returncode == 0 or "Missing required database field: DB_HOST" not in rejected.stdout:
        raise AssertionError("MariaDB config stopped requiring database credentials")

    valid_db_env = dict(db_env)
    valid_db_env.update(
        {
            "DB_HOST": "127.0.0.1",
            "DB_USER": "test-user",
            "DB_PASSWD": "test-password",
            "DB_NAME": "duris_dev",
            "DB_ALLOWED_TARGETS": "127.0.0.1/duris_dev",
        }
    )
    checked = run(script, valid_db_env, "--check-config")
    if checked.returncode != 0 or "explicit database configuration" not in checked.stdout:
        raise AssertionError("valid MariaDB config was rejected:\n" + checked.stdout)

    shared_host_db_env = dict(valid_db_env)
    shared_host_db_env.update(
        {
            "ENVIRONMENT": "production",
            "DURISWEB_SECRET": "0123456789abcdef0123456789abcdef",
            "DURIS_PRODUCTION_PORT": "14000",
            "DB_NAME": "duris",
            "DB_ALLOWED_TARGETS": "127.0.0.1/duris",
        }
    )
    checked = run(script, shared_host_db_env, "--production", "--check-config")
    if checked.returncode != 0 or "explicit database configuration" not in checked.stdout:
        raise AssertionError("configured production port redirected its database:\n" + checked.stdout)

    redirected_dev_env = dict(shared_host_db_env)
    redirected_dev_env.update({"ENVIRONMENT": "local", "DURIS_DEV_PORT": "14001"})
    rejected = run(script, redirected_dev_env, "--dev", "--check-config")
    if rejected.returncode == 0 or "Resolved database target is not allow-listed" not in rejected.stdout:
        raise AssertionError("non-production port kept a production database name")

    fallback_env = dict(flat_env)
    fallback_env["PERSISTENCE_MODE"] = "mariadb-primary-flatfile-fallback"
    rejected = run(script, fallback_env, "--check-config")
    if rejected.returncode == 0 or "Missing required database field: DB_HOST" not in rejected.stdout:
        raise AssertionError("fallback config stopped requiring database credentials")

    invalid_env = dict(flat_env)
    invalid_env["PERSISTENCE_MODE"] = "unknown"
    rejected = run(script, invalid_env, "--check-config")
    if rejected.returncode == 0 or "Invalid PERSISTENCE_MODE" not in rejected.stdout:
        raise AssertionError("invalid persistence mode was accepted")

    (project / "areas_mini").mkdir()
    for name in (
        "mini.mob",
        "mini.obj",
        "mini.qst",
        "mini.wld",
        "mini.zon",
        "world.shp",
        "world.tab",
        "world.weather",
    ):
        (project / "areas_mini" / name).write_text("test\n")
    (project / "bin/server").mkdir(parents=True, exist_ok=True)
    (project / "lib/misc").mkdir(parents=True)
    (project / "logs").mkdir()
    state_record = project / "state/metadata/timer.test"
    state_record.parent.mkdir(parents=True, mode=0o700)
    (project / "state").chmod(0o700)
    state_record.write_text("durable state\n")
    state_record.chmod(0o600)
    server = project / "bin/server/dms_new"
    server.write_text("#!/bin/sh\nexit 0\n")
    server.chmod(0o755)

    # The backup before a boot is off unless PREBOOT_BACKUP=1: without it the launcher
    # boots and leaves no backup.
    launched = run(script, flat_env, "--minimal")
    if launched.returncode != 0 or "Mud stopped, reason: shutdown [0]" not in launched.stdout:
        raise AssertionError("flat-file launcher did not boot without a pre-boot backup:\n"
                             + launched.stdout)
    if "Backing up" in launched.stdout or (project / "backups").exists():
        raise AssertionError("flat-file launcher took a backup it was not asked for:\n"
                             + launched.stdout)
    flat_env["PREBOOT_BACKUP"] = "1"

    nested_backup_env = dict(flat_env)
    nested_config = project / "nested-policy.json"
    nested_config.write_text(json.dumps(dict(policy, root=str(project / "state/backups"))))
    nested_config.chmod(0o600)
    nested_backup_env["BACKUP_POLICY_FILE"] = str(nested_config)
    rejected = run(script, nested_backup_env, "--minimal")
    if rejected.returncode == 0 or "refusing to boot" not in rejected.stdout:
        raise AssertionError("flat-file launcher ignored an unsafe backup target:\n" + rejected.stdout)

    # Every boot moves the last run's logs into logs/old-logs/<date>/ and drops the
    # oldest generations until the archive fits its cap.
    logs = project / "logs"
    (logs / "log").mkdir(exist_ok=True)
    (logs / "log/status").write_text("last run\n")
    (logs / "player-log").mkdir(exist_ok=True)
    (logs / "player-log/wizcmds").write_text("last run\n")
    (logs / "latency_trace.log").write_text("last run\n")
    (logs / "old-logs/2000.01.01-00.00.00").mkdir(parents=True)
    (logs / "old-logs/2000.01.01-00.00.00/status").write_bytes(b"x" * (2 << 20))
    (logs / "old-logs/2000.01.02-00.00.00").mkdir()
    (logs / "old-logs/2000.01.02-00.00.00/status").write_text("kept\n")
    capped_env = dict(flat_env, DURIS_LOG_ARCHIVE_MB="1")
    launched = run(script, capped_env, "--minimal")
    if launched.returncode != 0 or "Mud stopped, reason: shutdown [0]" not in launched.stdout:
        raise AssertionError("flat-file launcher did not complete without DB tools:\n" + launched.stdout)
    rotated = [path for path in (logs / "old-logs").iterdir()
               if path.is_dir() and (path / "latency_trace.log").exists()]
    if (len(rotated) != 1 or (rotated[0] / "status").read_text() != "last run\n"
            or (rotated[0] / "player-log/wizcmds").read_text() != "last run\n"):
        raise AssertionError("the boot did not move the last run's logs into old-logs")
    if (logs / "latency_trace.log").exists() or any((logs / "player-log").iterdir()):
        raise AssertionError("the boot left the last run's logs in place")
    # The address_retention job moves the new live set on once this marker is a day old.
    if not (logs / "log/.since").is_file():
        raise AssertionError("the boot did not mark when its live logs began")
    if (logs / "old-logs/2000.01.01-00.00.00").exists() or \
            not (logs / "old-logs/2000.01.02-00.00.00").exists():
        raise AssertionError("the archive cap did not drop only the oldest generation")
    forbidden = (
        "database migrations",
        "runtime database compatibility",
        "Logged reboot:",
        "DB mode enabled",
        "mysqldump",
    )
    if any(message in launched.stdout for message in forbidden):
        raise AssertionError("flat-file launcher entered a database-only path:\n" + launched.stdout)
    backups = list((project / "backups").glob("*/state/metadata/timer.test"))
    if len(backups) != 1 or backups[0].read_text() != "durable state\n":
        raise AssertionError("flat-file launcher did not back up its selected state root")
    if backups[0].stat().st_mode & 0o077 or backups[0].parents[1].stat().st_mode & 0o077:
        raise AssertionError("flat-file launcher created a non-private backup")

    # --production logs a staged binary whose stamp is not mariadb/production, leaves it
    # where it is and runs the stamped runtime binary; it exits only when that one is
    # unstamped too. The regression suite stages a development build, and the exit
    # here kept the systemd service in a ten-second restart loop.
    tools = project / "bin/areas/tools"
    tools.mkdir(parents=True)
    for name in ("make_mob", "make_obj", "make_qst", "make_shp", "make_trg", "make_wld", "make_zon"):
        (tools / name).write_text("#!/bin/sh\nexit 0\n")
        (tools / name).chmod(0o755)
    generator = project / "areas/m_slow"
    generator.parent.mkdir()
    generator.write_text("#!/bin/sh\nexit 0\n")
    generator.chmod(0o755)
    runtime = project / "bin/server/dms"
    runtime.write_text("#!/bin/sh\necho runtime binary ran\nexit 0\n")
    runtime.chmod(0o755)
    (project / "bin/server/.dms-backend").write_text("mariadb/production\n")
    server.write_text("#!/bin/sh\necho staged binary ran\nexit 0\n")
    server.chmod(0o755)
    (project / "bin/server/.dms_new-backend").write_text("flatfile/development\n")
    launched = run(script, production_check_env, "--production")
    if (launched.returncode != 0 or "Ignoring staged bin/server/dms_new" not in launched.stdout
            or "runtime binary ran" not in launched.stdout or "staged binary ran" in launched.stdout):
        raise AssertionError("production launcher did not run the runtime binary past a development build:\n"
                             + launched.stdout)
    if not server.exists() or (project / "bin/server/.dms-backend").read_text() != "mariadb/production\n":
        raise AssertionError("production launcher promoted or removed the development build")
    # A failed world generation stops the boot: the server would otherwise start on the
    # previous areas/world.* (or on none) and nothing would say so.
    generator.write_text("#!/bin/sh\necho error: trg/limbo.trg:4: a trigger is not ended by ~ >&2\nexit 1\n")
    rejected = run(script, production_check_env, "--production")
    if (rejected.returncode == 0 or "refusing to boot on stale area files" not in rejected.stdout
            or "runtime binary ran" in rejected.stdout):
        raise AssertionError("the launcher booted after world generation failed:\n" + rejected.stdout)
    generator.write_text("#!/bin/sh\nexit 0\n")
    (project / "bin/server/.dms-backend").write_text("flatfile/development\n")
    rejected = run(script, production_check_env, "--production")
    if rejected.returncode == 0 or "requires a mariadb/production server build" not in rejected.stdout:
        raise AssertionError("production launcher ran an unstamped runtime binary:\n" + rejected.stdout)

print("flat-file launcher regression passed")
