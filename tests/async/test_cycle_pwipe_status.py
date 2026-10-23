#!/usr/bin/env python3
"""Filesystem preflight and launcher handoff contracts, without real player data."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class FilesystemWipeTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="duris-wipe-files-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "Players/wipers").mkdir(parents=True)
        for path in ("Players/a/old", "Ships/old", "Players/Backup/keep", "Accounts/keep", "config/keep"):
            target = self.root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("sentinel")
        self.script = self.root / "Players/wipers/wipe_it_all"
        shutil.copy2(ROOT / "Players/wipers/wipe_it_all", self.script)

    def run_wipe(self, *args):
        return subprocess.run([str(self.script), *args], capture_output=True, text=True)

    def test_preflight_is_read_only_and_cleanup_preserves_carryovers(self):
        self.assertEqual(self.run_wipe("--check").returncode, 0)
        self.assertTrue((self.root / "Players/a/old").exists())
        outside = self.root / "outside"
        outside.write_text("preserved")
        (self.root / "Players/a/nested-link").symlink_to(outside)
        self.assertEqual(self.run_wipe().returncode, 0)
        self.assertFalse((self.root / "Players/a/old").exists())
        for path in ("outside", "Players/Backup/keep", "Accounts/keep", "config/keep"):
            self.assertTrue((self.root / path).is_file(), path)
        self.assertEqual(self.run_wipe().returncode, 0)

    def test_top_level_symlinks_and_wrong_types_fail_before_any_deletion(self):
        for dangling in (False, True):
            with self.subTest(dangling=dangling):
                ship = self.root / "Ships"
                shutil.rmtree(ship)
                ship.symlink_to(self.root / ("absent" if dangling else "Players/Backup"))
                self.assertNotEqual(self.run_wipe().returncode, 0)
                self.assertTrue((self.root / "Players/a/old").exists())
                ship.unlink()
                ship.mkdir()
        (self.root / "Players/Corpses").write_text("unexpected file")
        self.assertNotEqual(self.run_wipe().returncode, 0)
        self.assertTrue((self.root / "Players/a/old").exists())

    @unittest.skipIf(os.geteuid() == 0, "permission checks require an unprivileged process")
    def test_denied_access_fails_before_any_deletion(self):
        path = self.root / "Ships"
        path.chmod(0o500)
        self.addCleanup(path.chmod, 0o700)
        self.assertNotEqual(self.run_wipe("--check").returncode, 0)
        self.assertNotEqual(self.run_wipe().returncode, 0)
        self.assertTrue((self.root / "Players/a/old").exists())

    def test_launcher_and_service_preserve_fenced_stop_status(self):
        launcher = (ROOT / "scripts/cycle_mud.sh").read_text()
        self.assertIn('finish_pwipe "$RESET_EPOCH" || exit 58', launcher)
        self.assertIn("AND reset_completed_at IS NOT NULL", launcher)
        self.assertIn('exit "$RESULT"', launcher)
        self.assertIn('sql_pwipe_filesystem_ready() ? 55 : 58',
                      (ROOT / "src/net/comm.c").read_text())
        unit = (ROOT / "deploy/systemd/duris-mud-production.service.in").read_text()
        self.assertIn("RestartPreventExitStatus=55 58", unit)


if __name__ == "__main__":
    unittest.main()
