#!/usr/bin/python3 -I
"""Installed root-only systemd adapter for one caller-owned disposable fixture.

Install this reviewed file and duris-mud-production.service.in in a root-owned
non-writable directory. It never imports or executes checkout code as root.
"""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import stat
import subprocess
import sys

STATE = Path("/run/duris-pwipe-qualification")
UNITS = Path("/run/systemd/system")
ENV = {"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def trusted_file(path):
    for entry in (path, *path.parents):
        metadata = entry.lstat()
        require(not stat.S_ISLNK(metadata.st_mode) and metadata.st_uid == 0 and
                not metadata.st_mode & 0o022, "helper assets/parents must be root-owned and non-writable")
    require(path.is_file(), "expected regular installed asset")
    return path.read_bytes()


def control(*arguments, check=True):
    return subprocess.run(["/usr/bin/systemctl", *arguments], env=ENV, check=check,
                          timeout=100, stdout=subprocess.DEVNULL)


def main():
    require(os.geteuid() == 0, "invoke the installed helper through the approved sudo rule")
    uid = int(os.environ.get("SUDO_UID", "0"))
    require(uid > 0, "a non-root sudo caller is required")
    caller = pwd.getpwuid(uid)
    require(len(sys.argv) in (3, 4), "usage: helper ACTION UNIT [RUNTIME]")
    action, unit = sys.argv[1:3]
    require(action in ("check", "prepare", "start", "stop", "logs", "cleanup"), "unknown action")
    require(bool(re.fullmatch(r"duris-pwipe-qualification-" + str(uid) + r"-[0-9a-f]{32}\.service", unit)),
            "unit must be this caller's private qualification identity")
    require(len(sys.argv) == (4 if action == "prepare" else 3), "unexpected arguments")
    os.umask(0o077)
    installed = Path(__file__).absolute()
    trusted_file(installed)
    template_bytes = trusted_file(installed.with_name("duris-mud-production.service.in"))
    if action == "check":
        print(json.dumps({"uid": uid, "unit_template_sha256": hashlib.sha256(template_bytes).hexdigest()}))
        return
    STATE.mkdir(mode=0o700, exist_ok=True)
    metadata = STATE.lstat()
    require(stat.S_ISDIR(metadata.st_mode) and metadata.st_uid == 0 and
            not metadata.st_mode & 0o077, "unsafe helper registration directory")
    with (STATE / ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        record = STATE / (unit + ".json")
        unit_path = UNITS / unit
        pin_path = unit_path.with_suffix(".target")
        if action == "prepare":
            runtime = Path(sys.argv[3])
            require(bool(re.fullmatch(r"/[A-Za-z0-9_./-]+", str(runtime))) and
                    runtime.resolve(strict=True) == runtime, "runtime must be a canonical simple absolute path")
            owner = runtime.stat()
            require(stat.S_ISDIR(owner.st_mode) and owner.st_uid == uid and
                    not owner.st_mode & 0o077, "runtime must be private and owned by the caller")
            require(not list(STATE.glob("duris-pwipe-qualification-" + str(uid) + "-*.json")),
                    "clean up this caller's previous fixture first: " + ", ".join(path.name.removesuffix(".json") for path in STATE.glob("duris-pwipe-qualification-" + str(uid) + "-*.json")))
            require(not unit_path.exists() and not unit_path.is_symlink() and
                    not pin_path.exists() and not pin_path.is_symlink(), "unit identity already exists")
            template = template_bytes.decode()
            unit_text = template.replace("@DURIS_USER@", str(uid)).replace("@DURIS_GROUP@", str(caller.pw_gid))
            unit_text = unit_text.replace("@DURIS_ROOT@", str(runtime)).replace(" --production", " --minimal")
            unit_text = unit_text.replace("Description=DurisMUD production server", "Description=Disposable pwipe qualification")
            binding = {"uid": uid, "unit_sha256": hashlib.sha256(unit_text.encode()).hexdigest(),
                       "unit_template_sha256": hashlib.sha256(template_bytes).hexdigest()}
            with record.open("x") as output:
                json.dump(binding, output)
            # Registration precedes manager operations so an interrupted prepare
            # can always be cleaned up without losing ownership provenance.
            with unit_path.open("x") as output:
                output.write(unit_text)
            with pin_path.open("x") as output:
                output.write("[Unit]\nDescription=Private qualification statistics reference\nAfter=" + unit + "\n")
            control("daemon-reload")
            control("start", pin_path.name)
            print(json.dumps(binding))
            return
        if action in ("stop", "logs", "cleanup") and not record.exists():
            require(not unit_path.exists() and not pin_path.exists(), "refusing unregistered unit cleanup")
            return
        binding = json.loads(record.read_text())
        require(binding["uid"] == uid, "registration belongs to another caller")
        if action in ("stop", "logs") and not unit_path.exists():
            return
        if action != "cleanup":
            require(hashlib.sha256(trusted_file(unit_path)).hexdigest() == binding["unit_sha256"],
                    "registered unit changed")
        if action == "start":
            result = control("start", unit, check=False)
            print(json.dumps({"systemctl_returncode": result.returncode}))
        elif action == "stop":
            control("stop", unit)
        elif action == "logs":
            subprocess.run(["/usr/bin/journalctl", "--unit=" + unit, "--output=cat", "--no-pager"],
                           env=ENV, timeout=10, check=True)
        else:
            control("stop", unit, check=False)
            control("stop", pin_path.name, check=False)
            control("reset-failed", unit, check=False)
            unit_path.unlink(missing_ok=True)
            pin_path.unlink(missing_ok=True)
            control("daemon-reload")
            record.unlink()


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, subprocess.SubprocessError) as error:
        print("pwipe systemd helper refused: " + str(error), file=sys.stderr)
        raise SystemExit(2)
