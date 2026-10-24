#!/usr/bin/env python3
"""Archive both native name-keyed mail inputs before a new season can boot."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]

with tempfile.TemporaryDirectory(prefix="pwipe-mail-") as temporary:
    work = Path(temporary)
    binary = work / "mail"
    subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-ffunction-sections",
                    "-fdata-sections", "-D__NO_MYSQL__", "-Isrc", "-Isrc/no_mysql", "tests/async/pwipe_mail_harness.cpp",
                    "src/cmd/mail.c", "src/core/mm.c", "src/world/handler.c", "src/core/safe_io.c",
                    "tests/async/harness_stubs.cpp", "-Wl,--gc-sections", "-lbsd", "-o", str(binary)],
                   cwd=ROOT, check=True)
    for variant in ("current", "legacy", "both"):
        root = work / variant
        (root / "Players/wipers").mkdir(parents=True)
        (root / "Accounts").mkdir()
        (root / "Accounts/keep").write_text("preserved account registry")
        if variant == "legacy":
            (root / "Players/mail").touch()
        subprocess.run([str(binary), str(root), "seed"], check=True)
        if variant == "both":
            shutil.copy2(root / "Accounts/mail", root / "Players/mail")
        spools = {name: (root / name).read_bytes() for name in ("Accounts/mail", "Players/mail")
                  if (root / name).exists()}
        inspected = work / (variant + "-inspection")
        shutil.copytree(root, inspected)
        subprocess.run([str(binary), str(inspected), "old"], check=True)
        shutil.copy2(ROOT / "Players/wipers/wipe_it_all", root / "Players/wipers/wipe_it_all")
        env = dict(os.environ, COPYOVER_STATE_FILE=str(root / "copyover.dat"),
                   MAINTENANCE_STATE_FILE=str(root / "runtime/maintenance-scheduler.state"))
        wiper = root / "Players/wipers/wipe_it_all"
        subprocess.run([str(wiper), "--check"], env=env, cwd=root, check=True, stdout=subprocess.DEVNULL)
        assert all((root / name).read_bytes() == payload for name, payload in spools.items())
        assert not (root / "Players/Backup").exists()
        subprocess.run([str(wiper)], env=env, cwd=root, check=True, stdout=subprocess.DEVNULL)
        assert not any((root / name).exists() for name in spools), "old mail remains a live new-season input"
        archive, = (root / "Players/Backup").glob("pwipe-mail.*")
        assert archive.stat().st_mode & 0o777 == 0o700
        for name, payload in spools.items():
            assert (archive / ("current" if name == "Accounts/mail" else "legacy")).read_bytes() == payload
        subprocess.run([str(binary), str(root), "fresh"], check=True)
        assert (root / "Accounts/keep").read_text() == "preserved account registry"
        for name, payload in spools.items():
            assert (archive / ("current" if name == "Accounts/mail" else "legacy")).read_bytes() == payload
print("Actual mail producer/index/reader: both old name-keyed inputs archived; fresh same-name mail works")
