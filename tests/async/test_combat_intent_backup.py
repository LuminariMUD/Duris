#!/usr/bin/env python3
"""Disposable native backup/recovery fixtures; no live DB, mounts or game."""
import fcntl
import hashlib
import os
import shutil
import unittest
from unittest import mock

from test_persistence_backup import Fixture, ROOT, backup, restore
from test_persistence_backup_integration import build_native_fixture


class CombatIntentBackupTests(Fixture):
    @classmethod
    def setUpClass(cls):
        cls.fixture = build_native_fixture()

    def setUp(self):
        super().setUp()
        self.live = self.base / "live"
        shutil.rmtree(self.live)  # Only Fixture's freshly provisioned synthetic state.
        backup.run([str(self.fixture), "seed", str(self.live)], phase="test")
        backup.run([str(self.fixture), "seed-combat", str(self.live)], phase="test")
        self.store = self.p["journal_roots"]["critical"] / "combat-intents"
        self.pending = self.store / ("c1" + "00" * 15 + ".intent")
        self.recorded = self.store / ("c2" + "00" * 15 + ".recorded")

    def test_boot_lock_durable_evidence_temporaries_and_schedule(self):
        temporary = self.store / ("." + self.pending.name + ".tmp.123.4")
        temporary.write_bytes(b"unpublished partial command")
        before = backup.inventory(self.store)
        with (self.store / ".service-lock").open("rb") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = backup.schedule(self.p, "flatfile-primary")
        self.assertEqual(result["result"], "ok")
        generation = self.p["root"] / result["generation"]
        captured = generation / "journals/critical/combat-intents"
        self.assertEqual(set(backup.inventory(captured)),
                         {".service-lock", self.pending.name, self.recorded.name})
        for name in (self.pending.name, self.recorded.name):
            self.assertEqual((captured / name).read_bytes(), (self.store / name).read_bytes())
        self.assertEqual(backup.inventory(self.store), before)
        self.assertGreater(backup.read_json(self.p["root"] / "schedule.json")["completed"], 0)
        self.assertEqual(backup.status(self.p)["result"], "ok")
        self.assertEqual(backup.schedule(self.p, "flatfile-primary")["event"], "status")

    def test_capture_rejects_invalid_combat_entries(self):
        valid = self.pending.read_bytes()
        for index, (name, data, code) in enumerate((
                ("unexpected", valid, "journal_filename"),
                ("ab.intent", valid, "journal_filename"),
                ("0" * 32 + ".intent", valid, "journal_combat_operation"),
                ("a" * 32 + ".recorded", b"", "journal_combat_size"),
                ("a" * 32 + ".intent", b"x" * (backup.COMBAT_MAX_BYTES + 1), "journal_combat_size"),
                ("a" * 32 + ".recorded", valid[:-1] + bytes([valid[-1] ^ 1]),
                 "journal_combat_checksum"),
                (".service-lock", b"not empty", "journal_service_lock_nonempty"))):
            with self.subTest(name=name):
                entry = self.store / name
                original = entry.read_bytes() if entry.exists() else None
                entry.write_bytes(data)
                stage = self.base / f"stage-{index}"
                stage.mkdir(mode=0o700)
                with self.assertRaisesRegex(backup.BackupError, code):
                    backup.journal_capture(stage, self.p, combat=True)
                if original is None:
                    entry.unlink()
                else:
                    entry.write_bytes(original)
        for index, kind in enumerate(("directory", "symlink", "hardlink", "public",
                                      "temporary-directory", "temporary-symlink")):
            entry = self.store / ("a" * 32 + ".intent")
            if kind.startswith("temporary-"):
                entry = self.store / ("." + entry.name + ".tmp.123.4")
            if kind.endswith("directory"):
                entry.mkdir(mode=0o700)
            elif kind.endswith("symlink"):
                entry.symlink_to(self.pending)
            elif kind == "hardlink":
                os.link(self.pending, entry)
            else:
                entry.write_bytes(valid)
                entry.chmod(0o644)
            stage = self.base / f"unsafe-{index}"
            stage.mkdir(mode=0o700)
            with self.subTest(kind=kind), self.assertRaises(backup.BackupError):
                backup.journal_capture(stage, self.p, combat=True)
            entry.rmdir() if kind.endswith("directory") else entry.unlink()

    def test_completion_during_copy_fails_safely_then_retries(self):
        previous = self.create()
        preserved = backup.inventory(previous)
        copy = backup.shutil.copy2

        def racing_copy(source, destination, *args, **kwargs):
            if source == self.pending:
                backup.run([str(self.fixture), "recover-combat", str(self.live)], phase="test")
            return copy(source, destination, *args, **kwargs)

        with mock.patch.object(backup.shutil, "copy2", side_effect=racing_copy):
            result = backup.schedule(self.p, "flatfile-primary")
        self.assertEqual(result["result"], "failed")
        self.assertEqual(backup.inventory(previous), preserved)
        self.assertEqual(len(backup.generations(self.p["root"])), 1)
        self.assertFalse(list(self.p["root"].glob(".staging-*")))
        self.assertFalse((self.p["root"] / "schedule.json").exists())
        self.assertEqual(backup.schedule(self.p, "flatfile-primary")["result"], "ok")
        self.assertEqual(backup.status(self.p)["result"], "ok")

    def test_native_qualifier_checks_completed_and_pending_commands(self):
        for case in ("valid", "wrong-id", "invalid-codec", "corrupt-recorded", "duplicate",
                     "temporary", "nonempty-lock", "public", "nested"):
            candidate = self.base / case
            candidate.mkdir(mode=0o700)
            backup.write_json(candidate / "ISOLATED_RESTORE", {"synthetic": True})
            store = candidate / "journals/critical/combat-intents"
            shutil.copytree(self.store, store)
            pending = store / self.pending.name
            recorded = store / self.recorded.name
            if case == "wrong-id":
                pending.rename(store / ("a" * 32 + ".intent"))
            elif case == "invalid-codec":
                data = b"bad!" + pending.read_bytes()[4:-32]
                pending.write_bytes(data + hashlib.sha256(data).digest())
            elif case == "corrupt-recorded":
                recorded.write_bytes(b"corrupt")
            elif case == "duplicate":
                shutil.copyfile(pending, pending.with_suffix(".recorded"))
            elif case == "temporary":
                (store / ("." + pending.name + ".tmp.123.4")).touch(mode=0o600)
            elif case == "nonempty-lock":
                (store / ".service-lock").write_bytes(b"not empty")
            elif case == "public":
                recorded.chmod(0o644)
            elif case == "nested":
                (store / "unexpected").mkdir(mode=0o700)
            command = [str(ROOT / "bin/tools/qualify_flatfile_restore"), "--receipts", str(candidate)]
            with self.subTest(case=case):
                if case == "valid":
                    backup.run(command, phase="test")
                else:
                    with self.assertRaises(backup.BackupError):
                        backup.run(command, phase="test")

    def restore_during_commit(self, before_snapshot):
        capture = backup.flatfile_capture

        def commit():
            backup.run([str(self.fixture), "recover-combat", str(self.live)], phase="test")

        def racing_capture(stage, p, capacity_base=None):
            self.assertTrue((stage / "journals/critical/combat-intents" / self.pending.name).exists())
            if before_snapshot:
                commit()
            detail = capture(stage, p, capacity_base)
            if not before_snapshot:
                commit()
            return detail

        with mock.patch.object(backup, "flatfile_capture", side_effect=racing_capture):
            generation = self.create()
        captured = backup.inventory(generation)
        live_before = backup.inventory(self.live)
        journals_before = backup.inventory(self.store)

        def recover(candidate, mode, env):
            self.assertEqual(mode, "flatfile-primary")
            result = backup.run([str(self.fixture), "recover-combat", str(candidate / "state")],
                                phase="test")
            self.assertEqual(result.strip(), b"already_applied" if before_snapshot else b"applied")

        # Replace only the dedicated-filesystem guard and game boot. Copy, checksums,
        # native qualification and repository replay all run against real fixture bytes.
        self.p["restore_root"].mkdir(mode=0o700)
        with mock.patch.object(restore, "restore_capacity"), \
             mock.patch.object(restore, "service_load", side_effect=recover):
            result = restore.restore(self.p, generation.name, self.ledger())
        self.assertEqual(result["result"], "qualified")
        candidate = self.p["restore_root"] / result["candidate"]
        store = candidate / "journals/critical/combat-intents"
        self.assertFalse((store / self.pending.name).exists())
        self.assertTrue((store / self.pending.with_suffix(".recorded").name).exists())
        backup.run([str(self.fixture), "recover-combat", str(candidate / "state")], phase="test")
        self.assertEqual(backup.inventory(generation), captured)
        self.assertEqual(backup.inventory(self.live), live_before)
        self.assertEqual(backup.inventory(self.store), journals_before)

    def test_restore_replays_commit_newer_than_authority_snapshot(self):
        self.restore_during_commit(False)

    def test_restore_replays_idempotently_when_commit_precedes_snapshot(self):
        self.restore_during_commit(True)

    def test_mariadb_capture_keeps_pre_snapshot_combat_evidence(self):
        capture = backup.mariadb_capture

        def racing_capture(stage, p, capacity_base=None):
            captured = stage / "journals/critical/combat-intents" / self.pending.name
            self.assertEqual(captured.read_bytes(), self.pending.read_bytes())
            detail = capture(stage, p, capacity_base)
            backup.run([str(self.fixture), "recover-combat", str(self.live)], phase="test")
            return detail

        with mock.patch.object(backup, "mariadb_capture", side_effect=racing_capture):
            generation = self.create("mariadb-primary")
        self.assertTrue((generation / "journals/critical/combat-intents" / self.pending.name).exists())


if __name__ == "__main__":
    unittest.main()
