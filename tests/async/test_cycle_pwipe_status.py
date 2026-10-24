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

    def run_wipe(self, *args, environment=None, maintenance_state=None):
        if environment is None:
            environment = dict(os.environ, COPYOVER_STATE_FILE=str(self.root / "copyover.dat"))
        environment = dict(environment, MAINTENANCE_STATE_FILE=str(
            maintenance_state or self.root / "runtime/maintenance-scheduler.state"))
        return subprocess.run([str(self.script), *args], capture_output=True, text=True, env=environment)

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

    def test_copyover_inputs_are_archived_before_cleanup(self):
        original = self.root / "copyover.dat"
        original.write_bytes(b"COPYold native world and descriptors")
        self.assertEqual(self.run_wipe("--check").returncode, 0)
        self.assertTrue(original.exists())
        self.assertEqual(self.run_wipe().returncode, 0)
        self.assertFalse(original.exists())
        archives = list((self.root / "Players/Backup").glob("pwipe-copyover.*"))
        self.assertEqual(len(archives), 1)
        self.assertEqual((archives[0] / "publication").read_bytes(), b"COPYold native world and descriptors")
        self.assertEqual(self.run_wipe().returncode, 0)
        self.assertEqual(list((self.root / "Players/Backup").glob("pwipe-copyover.*")), archives)

    def test_configured_native_inputs_and_consumption_barriers_survive_in_archive(self):
        with tempfile.TemporaryDirectory(prefix="duris-private-copyover-") as external:
            source = Path(external) / "native state"
            published, recovering = source, Path(str(source) + ".recovering")
            published.write_bytes(b"COPYpublication")
            recovering.write_bytes(b"COPYclaimed")
            barrier = Path(str(source) + ".recovering.consuming")
            barrier.mkdir(mode=0o700)
            (barrier / "image").write_bytes(b"COPYisolated")
            empty_barrier = Path(str(source) + ".consuming")
            empty_barrier.mkdir(mode=0o700)
            env = dict(os.environ, COPYOVER_STATE_FILE=str(source))
            self.assertEqual(self.run_wipe("--check", environment=env).returncode, 0)
            self.assertTrue(published.exists() and recovering.exists() and barrier.exists())
            self.assertEqual(self.run_wipe(environment=env).returncode, 0)
            self.assertFalse(any(path.exists() for path in (published, recovering, barrier, empty_barrier)))
            archive, = (self.root / "Players/Backup").glob("pwipe-copyover.*")
            self.assertEqual(archive.stat().st_mode & 0o777, 0o700)
            self.assertEqual((archive / "source-path").read_text(), str(source) + "\n")
            self.assertEqual((archive / "publication").read_bytes(), b"COPYpublication")
            self.assertEqual((archive / "recovering").read_bytes(), b"COPYclaimed")
            self.assertEqual((archive / "recovering.consuming/image").read_bytes(), b"COPYisolated")
            self.assertTrue((archive / "publication.consuming").is_dir())

    def test_native_input_inside_wiped_tree_is_archived_first(self):
        source = self.root / "Players/a/native.dat"
        source.write_bytes(b"COPYinside season store")
        env = dict(os.environ, COPYOVER_STATE_FILE=str(source))
        self.assertEqual(self.run_wipe(environment=env).returncode, 0)
        archive, = (self.root / "Players/Backup").glob("pwipe-copyover.*")
        self.assertEqual((archive / "publication").read_bytes(), b"COPYinside season store")
        self.assertEqual(self.run_wipe(environment=env).returncode, 0)

    def test_nested_recovery_parent_refuses_before_cleanup_can_remove_it(self):
        for maintenance in (False, True):
            parent = self.root / "Players/a/native"
            parent.mkdir()
            state = parent / "state"
            state.write_bytes(b"DMSMNT4old state" if maintenance else b"COPYold handoff")
            env = dict(os.environ, COPYOVER_STATE_FILE=str(state if not maintenance else self.root / "copyover.dat"))
            arguments = {"environment": env}
            if maintenance: arguments["maintenance_state"] = state
            self.assertNotEqual(self.run_wipe("--check", **arguments).returncode, 0)
            self.assertNotEqual(self.run_wipe(**arguments).returncode, 0)
            self.assertTrue(state.exists() and (self.root / "Players/a/old").exists())
            state.unlink(); parent.rmdir()

    @unittest.skipIf(os.geteuid() == 0, "permission checks require an unprivileged process")
    def test_nonsearchable_maintenance_ancestors_are_not_absence(self):
        for nested in (False, True):
            parent = self.root / "runtime"
            parent.mkdir()
            location = parent / "nested" if nested else parent
            location.mkdir(exist_ok=True)
            state = location / "state"
            state.write_bytes(b"DMSMNT4hidden old state")
            for mode in (0o600, 0):
                parent.chmod(mode)
                try:
                    self.assertNotEqual(self.run_wipe("--check", maintenance_state=state).returncode, 0)
                    self.assertNotEqual(self.run_wipe(maintenance_state=state).returncode, 0)
                    self.assertTrue((self.root / "Players/a/old").exists())
                finally:
                    parent.chmod(0o700)
                self.assertEqual(state.read_bytes(), b"DMSMNT4hidden old state")
            state.unlink()
            if nested: location.rmdir()
            parent.rmdir()

    def test_unsafe_native_state_refuses_before_seasonal_deletion(self):
        path = self.root / "copyover.dat"
        for case in ("invalid", "symlink", "barrier-entry", "barrier-link", "parent-link", "parent-link-dotdot", "missing-parent", "backup-link"):
            with self.subTest(case=case):
                env = dict(os.environ, COPYOVER_STATE_FILE=str(path))
                if case == "invalid":
                    path.write_text("configuration must not be moved")
                elif case == "symlink":
                    path.symlink_to(self.root / "Accounts/keep")
                elif case.startswith("barrier"):
                    barrier = self.root / "copyover.dat.recovering.consuming"
                    barrier.mkdir()
                    if case == "barrier-entry":
                        (barrier / "unrecognized").touch()
                    else:
                        (barrier / "image").symlink_to(self.root / "Accounts/keep")
                elif case == "parent-link":
                    path.symlink_to(self.root / "Accounts", target_is_directory=True)
                    env["COPYOVER_STATE_FILE"] = str(path / "absent")
                elif case == "parent-link-dotdot":
                    elsewhere = self.root / "elsewhere/child"
                    elsewhere.mkdir(parents=True)
                    (elsewhere.parent / "publication.dat").write_bytes(b"COPYactual native input")
                    path.symlink_to(elsewhere, target_is_directory=True)
                    env["COPYOVER_STATE_FILE"] = str(path / ".." / "publication.dat")
                elif case == "missing-parent":
                    env["COPYOVER_STATE_FILE"] = str(self.root / "absent/native.dat")
                else:
                    backup = self.root / "Players/Backup"
                    backup.rename(self.root / "saved-backup")
                    backup.symlink_to(self.root / "saved-backup", target_is_directory=True)
                self.assertNotEqual(self.run_wipe("--check", environment=env).returncode, 0)
                self.assertNotEqual(self.run_wipe(environment=env).returncode, 0)
                self.assertTrue((self.root / "Players/a/old").exists())
                self.assertEqual((self.root / "Accounts/keep").read_text(), "sentinel")
                if path.exists() or path.is_symlink():
                    path.unlink()
                if case.startswith("barrier"):
                    shutil.rmtree(barrier)
                if case == "backup-link":
                    backup.unlink()
                    (self.root / "saved-backup").rename(backup)

    def test_partial_native_archive_retry_preserves_each_image(self):
        published = self.root / "copyover.dat"
        claimed = self.root / "copyover.dat.recovering"
        published.write_bytes(b"COPYpublished")
        claimed.write_bytes(b"COPYclaimed")
        commands = self.root / "commands"
        commands.mkdir()
        (commands / "mv").write_text("#!/bin/sh\ncase \"$*\" in *.recovering*) exit 1;; esac\nexec /usr/bin/mv \"$@\"\n")
        (commands / "mv").chmod(0o700)
        env = dict(os.environ, PATH=str(commands) + ":" + os.environ["PATH"],
                   COPYOVER_STATE_FILE=str(published))
        self.assertNotEqual(self.run_wipe(environment=env).returncode, 0)
        self.assertFalse(published.exists())
        self.assertTrue(claimed.exists() and (self.root / "Players/a/old").exists())
        self.assertEqual(self.run_wipe().returncode, 0)
        archives = list((self.root / "Players/Backup").glob("pwipe-copyover.*"))
        self.assertEqual(len(archives), 2)
        self.assertEqual(sorted(path.read_bytes() for archive in archives for path in archive.iterdir()
                                if path.name != "source-path"), [b"COPYclaimed", b"COPYpublished"])

    def test_maintenance_unsafe_inputs_refuse_before_any_deletion(self):
        for case in ("unrecognized", "symlink", "directory", "parent-link", "temporary-unrecognized"):
            with self.subTest(case=case), tempfile.TemporaryDirectory(prefix="duris-maintenance-path-") as directory:
                parent = Path(directory)
                state = parent / "scheduler.state"
                if case == "unrecognized":
                    state.write_text("unrelated configuration")
                elif case == "symlink":
                    state.symlink_to(self.root / "Accounts/keep")
                elif case == "directory":
                    state.mkdir()
                elif case == "parent-link":
                    link = parent / "alias"
                    link.symlink_to(self.root / "Accounts", target_is_directory=True)
                    state = link / "absent"
                else:
                    Path(str(state) + ".tmp").write_text("unrelated temporary file")
                self.assertNotEqual(self.run_wipe("--check", maintenance_state=state).returncode, 0)
                self.assertNotEqual(self.run_wipe(maintenance_state=state).returncode, 0)
                self.assertTrue((self.root / "Players/a/old").exists())
                self.assertEqual((self.root / "Accounts/keep").read_text(), "sentinel")

    @unittest.skipIf(os.geteuid() == 0, "permission checks require an unprivileged process")
    def test_denied_maintenance_access_refuses_before_deletion(self):
        state = self.root / "runtime/maintenance-scheduler.state"
        state.parent.mkdir()
        state.write_bytes(b"DMSMNT4protected state")
        for path, mode in ((state, 0), (state.parent, 0o500)):
            original_mode = path.stat().st_mode & 0o777
            path.chmod(mode)
            try:
                self.assertNotEqual(self.run_wipe("--check").returncode, 0)
                self.assertNotEqual(self.run_wipe().returncode, 0)
                self.assertTrue((self.root / "Players/a/old").exists())
            finally:
                path.chmod(original_mode)

    def test_partial_maintenance_archive_retries_without_losing_evidence(self):
        state = self.root / "runtime/maintenance-scheduler.state"
        state.parent.mkdir()
        state.write_bytes(b"DMSMNT4old captured request")
        temporary = Path(str(state) + ".tmp")
        temporary.write_bytes(b"DMSMNT4interrupted state save")
        commands = self.root / "commands"; commands.mkdir()
        (commands / "mv").write_text("#!/bin/sh\ncase \"$*\" in *.state.tmp*) exit 1;; esac\nexec /usr/bin/mv \"$@\"\n")
        (commands / "mv").chmod(0o700)
        env = dict(os.environ, PATH=str(commands) + ":" + os.environ["PATH"],
                   COPYOVER_STATE_FILE=str(self.root / "copyover.dat"))
        self.assertNotEqual(self.run_wipe(environment=env).returncode, 0)
        self.assertFalse(state.exists())
        self.assertTrue(temporary.exists() and (self.root / "Players/a/old").exists())
        self.assertEqual(self.run_wipe().returncode, 0)
        self.assertFalse(temporary.exists())
        archives = list((self.root / "Players/Backup").glob("pwipe-maintenance.*"))
        self.assertEqual(len(archives), 2)
        self.assertEqual(sorted(path.read_bytes() for archive in archives for path in archive.iterdir()
                                if path.name != "source-path"),
                         [b"DMSMNT4interrupted state save", b"DMSMNT4old captured request"])

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

    @unittest.skipIf(os.geteuid() == 0, "permission checks require an unprivileged process")
    def test_denied_native_or_archive_access_fails_before_deletion(self):
        parent = self.root / "native"
        parent.mkdir()
        state = parent / "copyover.dat"
        state.write_bytes(b"COPYnative")
        env = dict(os.environ, COPYOVER_STATE_FILE=str(state))
        for path, mode in ((state, 0), (parent, 0o500), (self.root / "Players/Backup", 0o500)):
            old_mode = path.stat().st_mode & 0o777
            path.chmod(mode)
            try:
                self.assertNotEqual(self.run_wipe("--check", environment=env).returncode, 0)
                self.assertNotEqual(self.run_wipe(environment=env).returncode, 0)
                self.assertTrue((self.root / "Players/a/old").exists())
            finally:
                path.chmod(old_mode)

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
