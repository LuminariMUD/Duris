#!/usr/bin/env python3
"""Exercise the installed helper's real privilege boundary on disposable units."""
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import time
import uuid

helper = Path(sys.argv[1]).absolute()
assert os.geteuid() > 0, "run as the ordinary authorized caller"
unit = "duris-pwipe-qualification-" + str(os.geteuid()) + "-" + uuid.uuid4().hex + ".service"


def invoke(*arguments, accepted=True):
    result = subprocess.run(["sudo", "-n", str(helper), *arguments], capture_output=True, text=True, timeout=110)
    assert (result.returncode == 0) == accepted, result.stdout + result.stderr
    return result.stdout


assert json.loads(invoke("check", unit))["uid"] == os.geteuid()
invoke("shell", unit, accepted=False)
invoke("check", "duris-mud-production.service", accepted=False)
invoke("check", unit.replace(str(os.geteuid()), str(os.geteuid() + 1), 1), accepted=False)
invoke("check", unit, "/tmp", accepted=False)
invoke("prepare", unit, "/etc", accepted=False)
with tempfile.TemporaryDirectory(prefix="pwipe-helper-", dir=Path(__file__).resolve().parents[2] / "bin/tests") as temporary:
    root = Path(temporary)
    (root / "scripts").mkdir()
    launcher = root / "scripts/cycle_mud.sh"
    launcher.write_text("#!/bin/sh\necho ordinary-helper-fixture\nexit 55\n")
    launcher.chmod(0o700)
    root.chmod(0o755)
    invoke("prepare", unit, root, accepted=False)
    root.chmod(0o700)
    alias = root / "alias"
    alias.symlink_to(root, target_is_directory=True)
    invoke("prepare", unit, alias, accepted=False)
    try:
        binding = json.loads(invoke("prepare", unit, root))
        assert binding["uid"] == os.geteuid()
        properties = subprocess.check_output(["systemctl", "show", unit, "--property=User,Group,NoNewPrivileges,PrivateTmp,RestartPreventExitStatus"], text=True)
        assert "User=" + str(os.geteuid()) in properties and "NoNewPrivileges=yes" in properties
        assert "PrivateTmp=yes" in properties and "RestartPreventExitStatus=55 58" in properties
        invoke("start", unit)
        for _ in range(100):
            state = subprocess.check_output(["systemctl", "show", unit, "--property=ActiveState,ExecMainStatus,NRestarts"], text=True)
            if "ActiveState=inactive" in state:
                break
            time.sleep(.1)
        assert "ExecMainStatus=55" in state and "NRestarts=0" in state, state
        assert "ordinary-helper-fixture" in invoke("logs", unit)
        invoke("stop", unit)
    finally:
        invoke("cleanup", unit)
assert not (Path("/run/systemd/system") / unit).exists()
invoke("cleanup", unit)
print("Installed helper: caller/arguments/path refusals, nonroot unit, sandbox, exit 55, journal and cleanup passed")
