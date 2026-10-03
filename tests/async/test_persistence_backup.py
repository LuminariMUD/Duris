#!/usr/bin/env python3
"""Linux filesystem/unit regressions; all authority is disposable synthetic data.

No database, Redis, live game, or external transport. Capture stubs below model
MariaDB dump bytes only; the separate integration suite exercises real MariaDB.
Run: python3 tests/async/test_persistence_backup.py
"""
import contextlib
import errno
import gzip
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import persistence_backup as backup
import persistence_restore as restore


def policy(base):
    return dict(version=1, approved=True, custodian="synthetic-test", schedule_seconds=3600,
                rpo_seconds=7200, hourly=48, daily=14, weekly=8, max_bytes=20 * 1024**3,
                min_free_bytes=0, drill_seconds=604800, root=base / "backups",
                restore_root=base / "restore", live_roots=[base / "live"], replica_root=None,
                journal_roots={"critical": base / "journals/critical"})


def provision(root):
    for directory in ("identities/names", "identities/accounts", "players", "domains"):
        (root / directory).mkdir(parents=True, mode=0o700, exist_ok=True)
    journal_root = root.parent / "journals"
    (journal_root / "critical").mkdir(parents=True, mode=0o700, exist_ok=True)
    for relative in ("identities/names/catalog.identity", "identities/accounts/synthetic.acct",
                     "players/42", "domains/player_42", "domains/locker_catalog"):
        (root / relative).write_bytes(("synthetic:" + relative).encode())
    for path in [root, *root.rglob("*"), journal_root, *journal_root.rglob("*")]:
        path.chmod(0o700 if path.is_dir() else 0o600)


PREPARED, PAID = 0, 1


def locker_receipt(state, body=b"synthetic receipt"):
    # The native header locker_receipt_encode() writes: "LIDR", version 1, then the state.
    return b"LIDR\x01" + bytes([state]) + b"\x00\x00" + body


def fake_database_capture(stage, unused, capacity_base=None):
    tables = json.loads((stage / "runtime-schema.json").read_text())
    with gzip.open(stage / "database.sql.gz", "wb") as stream:
        for table in tables["runtime_table_sql_list"].replace("'", "").split(","):
            stream.write(f"CREATE TABLE `{table}` (synthetic INT);\n".encode())
    return {"database": "synthetic"}


class Fixture(unittest.TestCase):
    def setUp(self):
        self.old_umask = os.umask(0o077)
        self.addCleanup(os.umask, self.old_umask)
        self.temp = tempfile.TemporaryDirectory(prefix="duris-backup-unit-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.p = policy(self.base)
        provision(self.base / "live")
        self.env = mock.patch.dict(os.environ, {
            "FLATFILE_STATE_DIR": str(self.base / "live"),
            "CRITICAL_COMMAND_JOURNAL_DIR": str(self.base / "journals/critical"),
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        self.capture = mock.patch.object(backup, "mariadb_capture", fake_database_capture)
        self.capture.start()
        self.addCleanup(self.capture.stop)
        self.schema_check = mock.patch.object(backup, "verify_database_schema")
        self.schema_check.start()
        self.addCleanup(self.schema_check.stop)

    def create(self, mode="flatfile-primary", created=None):
        with contextlib.ExitStack() as stack:
            if created is not None:
                stack.enter_context(mock.patch.object(backup.time, "time", return_value=created))
            result = backup.backup(self.p, mode)
        return self.p["root"] / result["generation"]

    def baseline(self, mode):
        now = int(time.time())
        # Deliberately outside every retention bucket; only the newest two are
        # protected, so a subsequent successful generation can prune one.
        paths = [self.create(mode, now - 90 * 86400 + offset) for offset in (0, 1)]
        return {path: backup.inventory(path) for path in paths}

    def assert_preserved(self, before):
        for path, contents in before.items():
            self.assertEqual(backup.inventory(path), contents)
            backup.verify(path)

    def ledger(self, **changes):
        value = dict(version=1, captured_at=int(time.time()),
                     policy_sha256=backup.digest(ROOT / "migrations/data_lifecycle_manifest.json"),
                     tombstones=[])
        value.update(changes)
        path = self.base / "independent-tombstones.json"
        backup.write_json(path, value)
        return path


class PolicyTests(Fixture):
    def load(self, **changes):
        value = dict(self.p)
        value.update(changes)
        path = self.base / "policy.json"
        path.write_text(json.dumps(value, default=str))
        path.chmod(0o600)
        return backup.policy_load(path)

    def test_approved_defaults(self):
        loaded = self.load()
        expected = dict(self.p,
                        live_roots=self.p["live_roots"] + list(self.p["journal_roots"].values()))
        self.assertEqual(loaded, expected)

    def test_invalid_policy_values(self):
        for changes in ({"approved": False}, {"custodian": "SET_BY_OPERATOR"},
                        {"hourly": 1}, {"hourly": 8761}, {"daily": 3651}, {"weekly": 521},
                        {"max_bytes": 0}, {"max_bytes": True}, {"min_free_bytes": -1},
                        {"schedule_seconds": 59}, {"rpo_seconds": 3599},
                        {"rpo_seconds": 604801}, {"drill_seconds": 3599},
                        {"drill_seconds": 2678401}, {"live_roots": []}, {"unknown": 1}):
            with self.subTest(changes=changes), self.assertRaises(backup.BackupError):
                self.load(**changes)

    def test_overlap_in_both_directions_and_replica(self):
        for changes in ({"root": self.base / "live"}, {"root": self.base},
                        {"root": self.base / "live/child"},
                        {"restore_root": self.p["root"] / "child"},
                        {"replica_root": self.p["root"]},
                        {"replica_root": self.base / "live/replica"}):
            with self.subTest(changes=changes), self.assertRaises(backup.BackupError):
                self.load(**changes)

    def test_unsafe_paths_permissions_links_and_owner(self):
        for path in (Path("relative"), self.base / ".." / "escape"):
            with self.assertRaisesRegex(backup.BackupError, "unsafe_path"):
                backup.secure_path(path)
        file = self.base / "file"
        file.write_bytes(b"fixture")
        file.chmod(0o644)
        with self.assertRaisesRegex(backup.BackupError, "require_owner_only"):
            backup.secure_path(file, False)
        file.chmod(0o600)
        link = self.base / "link"
        link.symlink_to(file)
        with self.assertRaisesRegex(backup.BackupError, "symlink_rejected"):
            backup.secure_path(link)
        hardlink = self.base / "hardlink"
        os.link(file, hardlink)
        with self.assertRaisesRegex(backup.BackupError, "unexpected_file_type"):
            backup.secure_path(file, False)
        hardlink.unlink()
        real_lstat = Path.lstat
        def changed_owner(path):
            info = real_lstat(path)
            if path == file:
                fields = list(info)
                fields[stat.ST_UID] = os.getuid() + 10001
                return os.stat_result(fields)
            return info
        with mock.patch.object(Path, "lstat", changed_owner):
            with self.assertRaisesRegex(backup.BackupError, "unexpected_owner"):
                backup.secure_path(file, False)

    def test_retention_bucket_edges_and_always_two(self):
        now = 200 * 604800 + 12 * 3600
        offsets = [0, 1, 3599, 3600, 7199, 7200, 86400, 172800, 604800, 1209600]
        items = [(Path(str(index)), {"created": now - offset}) for index, offset in enumerate(offsets)]
        p = dict(self.p, hourly=2, daily=2, weekly=2)
        self.assertEqual(backup.retained(items, p, now), {"0", "1", "6"})
        self.assertEqual(backup.retained(items, dict(p, hourly=0, daily=0, weekly=0), now), {"0", "1"})


    def test_each_retention_tier_includes_previous_bucket_and_excludes_boundary(self):
        now = 200 * 604800 + 3 * 86400 + 12 * 3600 + 1800
        for tier, seconds in (("hourly", 3600), ("daily", 86400), ("weekly", 604800)):
            with self.subTest(tier=tier):
                p = dict(self.p, hourly=0, daily=0, weekly=0)
                p[tier] = 2
                items = [(Path("latest"), {"created": now}),
                         (Path("second"), {"created": now - 1}),
                         (Path("previous"), {"created": now - seconds}),
                         (Path("outside"), {"created": now - 2 * seconds})]
                self.assertEqual(backup.retained(items, p, now), {"latest", "second", "previous"})

class GenerationTests(Fixture):
    def test_explicit_deployed_schema_survives_checkout_schema_change(self):
        schema = json.loads((ROOT / "migrations/runtime_compatibility_manifest.json").read_text())
        schema["runtime_table_sql_list"] = "'accounts','player_data','ships'"
        selected = self.base / "deployed-schema.json"
        backup.write_json(selected, schema)
        with mock.patch.dict(os.environ, RUNTIME_COMPATIBILITY_MANIFEST=str(selected)):
            generation = self.create("mariadb-primary")
        selected.unlink()
        self.assertEqual(json.loads((generation / "runtime-schema.json").read_text()), schema)
        self.assertEqual(backup.verify(generation)["mode"], "mariadb-primary")

    def test_schema_mismatch_before_or_after_capture_preserves_generations(self):
        before = self.baseline("mariadb-primary")
        for checks in ([backup.BackupError("schema_mismatch")],
                       [None, backup.BackupError("schema_mismatch")]):
            with self.subTest(checks=len(checks)), \
                 mock.patch.object(backup, "verify_database_schema", side_effect=checks), \
                 self.assertRaisesRegex(backup.BackupError, "schema_mismatch"):
                self.create("mariadb-primary")
            self.assert_preserved(before)
            self.assertEqual(set(self.p["root"].glob("[0-9]*")), set(before))
            self.assertFalse(list(self.p["root"].glob(".staging-*")))

    def test_fallback_mode_captures_database_authority(self):
        generation = self.create("mariadb-primary-flatfile-fallback")
        self.assertEqual(backup.verify(generation)["mode"], "mariadb-primary")
        self.assertTrue((generation / "database.sql.gz").is_file())
        self.assertFalse((generation / "state").exists())

    def test_rpo_measures_from_capture_start(self):
        started = int(time.time())
        clock = [started]
        def delayed_capture(stage, p, capacity_base=None):
            clock[0] += 300
            return fake_database_capture(stage, p, capacity_base)
        with mock.patch.object(backup.time, "time", side_effect=lambda: clock[0]), \
             mock.patch.object(backup, "mariadb_capture", delayed_capture):
            self.create("mariadb-primary")
            self.assertEqual(backup.status(self.p)["age_seconds"], 300)
            clock[0] = started + self.p["rpo_seconds"] + 1
            with self.assertRaisesRegex(backup.BackupError, "rpo_exceeded"):
                backup.status(self.p)

    def test_required_drill_receipt_is_current_and_qualified(self):
        self.create()
        with self.assertRaisesRegex(backup.BackupError, "restore_drill_missing_or_overdue"):
            backup.status(self.p, require_drill=True)
        receipt = self.p["root"] / "drill.json"
        for result, age in (("failed", 0), ("qualified", self.p["drill_seconds"] + 1)):
            backup.write_json(receipt, {"result": result, "completed": int(time.time()) - age})
            with self.assertRaisesRegex(backup.BackupError, "restore_drill_missing_or_overdue"):
                backup.status(self.p, require_drill=True)
        backup.write_json(receipt, {"result": "qualified", "completed": int(time.time())})
        self.assertEqual(backup.status(self.p, require_drill=True)["result"], "ok")


    def test_full_manifest_and_checksum_tamper_both_modes(self):
        for mode in sorted(backup.MODES):
            with self.subTest(mode=mode):
                path = self.create(mode)
                meta = backup.verify(path)
                self.assertEqual(meta["mode"], mode)
                self.assertIn("runtime-schema.json", meta["files"])
                data = path / ("state/players/42" if mode == "flatfile-primary" else "database.sql.gz")
                data.write_bytes(data.read_bytes() + b"corruption")
                with self.assertRaisesRegex(backup.BackupError, "checksum"):
                    backup.verify(path)
                # Restore the fixture for the next mode.
                data.write_bytes(data.read_bytes()[:-len(b"corruption")])

    def test_failures_preserve_live_and_last_two_generations(self):
        for mode in sorted(backup.MODES):
            for failed in ("before_capture", "after_capture", "before_sync", "before_publish",
                           "after_publish", "after_verify", "before_rotation", "before_prune"):
                with self.subTest(mode=mode, stage=failed):
                    self.p["root"] = self.base / (mode + "-" + failed)
                    before = self.baseline(mode)
                    live = backup.inventory(self.base / "live", exclude_locks=True)
                    def interrupt(stage):
                        if stage == failed:
                            raise OSError("synthetic injected failure")
                    with mock.patch.object(backup, "checkpoint", interrupt), self.assertRaises(OSError):
                        self.create(mode)
                    self.assert_preserved(before)
                    self.assertEqual(backup.inventory(self.base / "live", exclude_locks=True), live)
                    self.assertFalse(list(self.p["root"].glob(".staging-*")))

    def test_fsync_verify_and_publication_failures_preserve_previous(self):
        for mode in sorted(backup.MODES):
            for failure in ("sync_tree", "verify", "rename"):
                with self.subTest(mode=mode, operation=failure):
                    self.p["root"] = self.base / (mode + "-" + failure)
                    before = self.baseline(mode)
                    if failure == "verify":
                        original = backup.verify
                        def verify(path):
                            if path not in before:
                                raise backup.BackupError("synthetic_verify_failed")
                            return original(path)
                        patch = mock.patch.object(backup, "verify", verify)
                    else:
                        patch = mock.patch.object(backup if failure == "sync_tree" else backup.os,
                                                  failure, side_effect=OSError("synthetic failure"))
                    with patch, self.assertRaises((OSError, backup.BackupError)):
                        self.create(mode)
                    self.assert_preserved(before)

    def test_overlap_fails_promptly(self):
        backup.mkdir(self.p["root"])
        with backup.lock(self.p["root"] / ".job.lock"):
            with mock.patch.object(backup, "LOCK_WAIT_SECONDS", 0):
                with self.assertRaisesRegex(backup.BackupError, "job_overlap"):
                    self.create()
        self.assertFalse(backup.generations(self.p["root"]))

    def test_hard_capacity_does_not_publish_or_remove_prior(self):
        for mode in sorted(backup.MODES):
            with self.subTest(mode=mode):
                self.p = policy(self.base)
                self.p["root"] = self.base / (mode + "-budget")
                before = self.baseline(mode)
                size = sum(backup.total_size(path) for path in before)
                self.p["max_bytes"] = size + 64
                with self.assertRaises(backup.BackupError):
                    self.create(mode)
                self.assert_preserved(before)
                self.assertEqual(set(path for path, _ in backup.generations(self.p["root"])), set(before))

    def test_generation_and_free_space_limits(self):
        self.p["max_bytes"] = 1
        with self.assertRaisesRegex(backup.BackupError, "capacity"):
            self.create()
        self.assertFalse(backup.generations(self.p["root"]))
        self.p["max_bytes"] = 20 * 1024**3
        self.p["min_free_bytes"] = 1
        with mock.patch.object(backup.shutil, "disk_usage", return_value=mock.Mock(free=0)):
            with self.assertRaisesRegex(backup.BackupError, "low_free_capacity"):
                self.create()

    def test_prune_interruption_preserves_newest_and_trash_for_inspection(self):
        before = self.baseline("flatfile-primary")
        def interrupt(stage):
            if stage == "prune_renamed":
                raise OSError("synthetic interruption")
        with mock.patch.object(backup, "checkpoint", interrupt), self.assertRaises(OSError):
            self.create()
        self.assertEqual(len(list(self.p["root"].glob(".trash-*"))), 1)
        self.assertEqual(len(backup.generations(self.p["root"])), 2)
        self.assertTrue(list(before)[1].exists())
        with self.assertRaises(backup.BackupError):
            backup.status(self.p)
        with self.assertRaises(backup.BackupError):
            self.create()

    def test_status_reads_no_generation_bytes_with_one_or_forty(self):
        now = int(time.time())
        unread = AssertionError("status read a stored generation's bytes")
        for count in (1, 40):
            with self.subTest(generations=count):
                self.p["root"] = self.base / f"backups-{count}"
                for index in reversed(range(count)):
                    self.create("mariadb-primary", now - index * 3600)
                with mock.patch.object(backup, "digest", side_effect=unread), \
                     mock.patch.object(backup, "validate_dump", side_effect=unread):
                    result = backup.status(self.p)
                self.assertEqual((result["result"], result["generations"]), ("ok", count))

    def test_finalize_verifies_a_publication_that_stopped_before_its_check(self):
        self.create()
        def interrupt(stage):
            if stage == "after_publish":
                raise OSError("synthetic publication interruption")
        with mock.patch.object(backup, "checkpoint", interrupt), self.assertRaises(OSError):
            self.create()
        newest = backup.generations(self.p["root"])[0][0]
        (newest / "state/players/42").write_bytes(b"corrupted after publication")
        with mock.patch.object(backup, "policy_load", return_value=self.p), \
             mock.patch.object(sys, "argv", ["backup", "--policy", "/synthetic/policy", "finalize"]), \
             contextlib.redirect_stderr(io.StringIO()) as output:
            self.assertEqual(backup.main(), 1)
        self.assertIn("generation_checksum_mismatch", output.getvalue())
        with self.assertRaisesRegex(backup.BackupError, "backup_or_rotation_incomplete"):
            backup.status(self.p)

    def test_stale_or_incomplete_status(self):
        self.create()
        self.assertEqual(backup.status(self.p)["result"], "ok")
        with mock.patch.object(backup.time, "time", return_value=time.time() + 7201):
            with self.assertRaisesRegex(backup.BackupError, "rpo_exceeded"):
                backup.status(self.p)
        backup.write_json(self.p["root"] / "status.json", {"generation": "missing", "result": "ok"})
        with self.assertRaisesRegex(backup.BackupError, "incomplete"):
            backup.status(self.p)


    def test_actual_file_fsync_failure_preserves_previous_generations(self):
        before = self.baseline("flatfile-primary")
        real_fsync = backup.os.fsync
        def failed_sync(fd):
            if ".staging-" in os.readlink(f"/proc/self/fd/{fd}"):
                raise OSError("synthetic durable file sync failure")
            return real_fsync(fd)
        with mock.patch.object(backup.os, "fsync", failed_sync), self.assertRaises(OSError):
            self.create()
        self.assert_preserved(before)
        self.assertFalse(list(self.p["root"].glob(".staging-*")))

    def test_finalize_after_publication_failure_is_idempotent(self):
        self.baseline("flatfile-primary")
        def interrupt(stage):
            if stage == "after_publish":
                raise OSError("synthetic publication interruption")
        with mock.patch.object(backup, "checkpoint", interrupt), self.assertRaises(OSError):
            self.create()
        newest = backup.generations(self.p["root"])[0][0]
        contents = backup.inventory(newest)
        with self.assertRaises(backup.BackupError):
            self.create()
        with mock.patch.object(backup, "policy_load", return_value=self.p), \
             mock.patch.object(sys, "argv", ["backup", "--policy", "/synthetic/policy", "finalize"]), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(backup.main(), 0)
            self.assertEqual(backup.main(), 0)
        self.assertEqual(backup.status(self.p)["result"], "ok")
        self.assertEqual(backup.inventory(newest), contents)
        self.assertEqual(len(backup.generations(self.p["root"])), 2)

class CapacityAndInputTests(Fixture):
    def test_restore_capacity_requires_dedicated_mount(self):
        backup.mkdir(self.p["restore_root"])
        with self.assertRaisesRegex(backup.BackupError, "dedicated_restore_filesystem"):
            restore.restore_capacity(self.p)
        with mock.patch.object(Path, "is_mount", return_value=True):
            with self.assertRaisesRegex(backup.BackupError, "shared_with_authority"):
                restore.restore_capacity(self.p)
        actual_stat = Path.stat
        def separate_device(path, *args, **kwargs):
            info = actual_stat(path, *args, **kwargs)
            if path == self.p["restore_root"]:
                fields = list(info)
                fields[stat.ST_DEV] += 10001
                return os.stat_result(fields)
            return info
        with mock.patch.object(Path, "is_mount", return_value=True), \
             mock.patch.object(Path, "stat", separate_device), \
             mock.patch.object(restore.shutil, "disk_usage", return_value=mock.Mock(total=self.p["max_bytes"] + 1, free=100)):
            with self.assertRaisesRegex(backup.BackupError, "capacity_invalid"):
                restore.restore_capacity(self.p)

    def test_environment_is_literal_and_never_executes_shell(self):
        path = self.base / "literal.env"
        marker = self.base / "must-not-exist"
        path.write_text("export SYNTHETIC_VALUE='$(touch " + str(marker) + ")'\n"
                        "SYNTHETIC_EMPTY=\nSYNTHETIC_QUOTED='two words' # comment\n")
        with mock.patch.dict(os.environ):
            backup.load_environment(path)
            self.assertEqual(os.environ["SYNTHETIC_VALUE"], "$(touch " + str(marker) + ")")
            self.assertEqual(os.environ["SYNTHETIC_EMPTY"], "")
            self.assertEqual(os.environ["SYNTHETIC_QUOTED"], "two words")
        self.assertFalse(marker.exists())
        path.chmod(0o640)
        with self.assertRaises(backup.BackupError):
            backup.load_environment(path)

    def test_stalled_stream_is_killed_and_reaped(self):
        started = time.monotonic()
        with self.assertRaises(backup.BackupError):
            with backup.streaming_process([sys.executable, "-c", "import time; time.sleep(60)"],
                                          env={}, timeout=0.25) as child:
                self.assertEqual(child.stdout.read(), b"")
        self.assertIsNotNone(child.poll())
        self.assertTrue(child.stdout.closed)
        self.assertLess(time.monotonic() - started, 5)

    def receipt_store(self):
        critical = self.base / "critical-journal"
        receipts = critical / "locker-identification"
        receipts.mkdir(mode=0o700, parents=True)
        critical.chmod(0o700)
        self.p["journal_roots"] = {"critical": critical}
        return critical, receipts

    def test_receipts_changing_during_the_capture_are_copied_after_it(self):
        critical, receipts = self.receipt_store()
        receipt = receipts / "42.receipt"
        # flatfile_atomic_write() writes a receipt to a temporary file renamed over it; one is
        # there while a write is under way, and a crash leaves it behind.
        self.assertIn('".%s.tmp.%ld.%llu"', (ROOT / "src/flatfile/flatfile_store.c").read_text())
        (receipts / ".43.receipt.tmp.1234.7").write_bytes(b"half-written receipt")
        with mock.patch.dict(os.environ, {"CRITICAL_COMMAND_JOURNAL_DIR": str(critical)}):
            for mode, capture in (("flatfile-primary", "flatfile_capture"),
                                  ("mariadb-primary", "mariadb_capture")):
                receipt.write_bytes(locker_receipt(PREPARED))
                original = getattr(backup, capture)
                def paid_during_capture(stage, p, capacity_base=None):
                    result = original(stage, p, capacity_base)
                    receipt.write_bytes(locker_receipt(PAID))
                    return result
                with self.subTest(mode=mode), mock.patch.object(backup, capture, paid_during_capture):
                    generation = self.create(mode)
                    copied = generation / "journals/critical/locker-identification"
                    self.assertEqual([path.name for path in copied.iterdir()], ["42.receipt"])
                    self.assertEqual((copied / "42.receipt").read_bytes(), locker_receipt(PAID))

    def test_a_payment_begun_during_the_capture_fails_it(self):
        # The receipt's state is byte 5, prepared first: what the backup reads to tell a
        # payment that may still be charging.
        self.assertIn("(*bytes)[5] = static_cast<uint8_t>(receipt.state);",
                      (ROOT / "src/item/locker_receipt.c").read_text())
        self.assertIn("\tprepared,\n\tpaid,\n\tfailed,\n\tdelivered",
                      (ROOT / "src/item/locker_receipt.h").read_text())
        critical, receipts = self.receipt_store()
        waiting = locker_receipt(PREPARED, b"waiting since before the capture")
        (receipts / "44.receipt").write_bytes(waiting)
        begun = receipts / "43.receipt"
        with mock.patch.dict(os.environ, {"CRITICAL_COMMAND_JOURNAL_DIR": str(critical)}):
            for mode, capture in (("flatfile-primary", "flatfile_capture"),
                                  ("mariadb-primary", "mariadb_capture")):
                original = getattr(backup, capture)
                def begun_during_capture(stage, p, capacity_base=None):
                    result = original(stage, p, capacity_base)
                    begun.write_bytes(locker_receipt(PREPARED))
                    return result
                with self.subTest(mode=mode), mock.patch.object(backup, capture, begun_during_capture), \
                     self.assertRaisesRegex(backup.BackupError, "receipt_payment_in_flight"):
                    self.create(mode)
                begun.unlink()
            self.assertFalse(backup.generations(self.p["root"]))
            generation = self.create()
        copied = generation / "journals/critical/locker-identification/44.receipt"
        self.assertEqual(copied.read_bytes(), waiting)

    def test_a_receipt_directory_the_game_does_not_use_costs_no_capture(self):
        unused = AssertionError("captured the authority for a mismatched policy")
        with mock.patch.dict(os.environ, {"CRITICAL_COMMAND_JOURNAL_DIR": str(self.base / "other")}), \
             mock.patch.object(backup, "mariadb_capture", side_effect=unused), \
             self.assertRaisesRegex(backup.BackupError, "journal_policy_mismatch"):
            self.create("mariadb-primary")

class FailureRecordTests(Fixture):
    def test_failure_records_name_the_exception_without_private_text(self):
        account = str(self.base / "live/identities/accounts/privatename.acct")
        timeout = subprocess.TimeoutExpired(["mysqldump", "--user=privateuser", "--host=privatehost"], 300)
        for error, cause in (
                (backup.BackupError("journal_filename"), {"code": "journal_filename"}),
                (FileNotFoundError(errno.ENOENT, "No such file or directory", account),
                 {"code": "operation_failed", "error": "FileNotFoundError",
                  "detail": "No such file or directory"}),
                (timeout, {"code": "operation_failed", "error": "subprocess.TimeoutExpired"}),
                (KeyError("mode"), {"code": "operation_failed", "error": "KeyError", "detail": "'mode'"})):
            with self.subTest(error=type(error).__name__), \
                 mock.patch.object(backup, "backup", side_effect=error), \
                 mock.patch.object(backup, "policy_load", return_value=self.p), \
                 mock.patch.object(sys, "argv", ["backup", "--policy", "/synthetic/policy", "backup"]), \
                 contextlib.redirect_stderr(io.StringIO()) as output:
                self.assertEqual(backup.main(), 1)
                self.assertEqual(json.loads(output.getvalue()),
                                 {"event": "backup", "result": "failed", **cause})

    def test_failing_schedule_reports_the_recovery_point_age(self):
        now = int(time.time())
        rpo = self.p["rpo_seconds"]
        self.create("mariadb-primary", now - 3600)
        full = OSError(errno.ENOSPC, "No space left on device", str(self.base / "private"))
        cause = {"code": "operation_failed", "error": "OSError", "detail": "No space left on device"}
        for root, late, record in (
                ("backups", 0, {**cause, "age_seconds": 3600}),
                ("backups", rpo, {"code": "rpo_exceeded", "age_seconds": 3600 + rpo, "backup": cause}),
                ("never-backed-up", 0, {"code": "rpo_exceeded", "age_seconds": None, "backup": cause})):
            self.p["root"] = self.base / root
            with self.subTest(root=root, late=late), \
                 mock.patch.object(backup.time, "time", return_value=now + late), \
                 mock.patch.object(backup, "mariadb_capture", side_effect=full), \
                 mock.patch.object(backup, "policy_load", return_value=self.p), \
                 mock.patch.object(sys, "argv", ["backup", "--policy", "/synthetic/policy", "schedule"]), \
                 contextlib.redirect_stderr(io.StringIO()) as output:
                self.assertEqual(backup.main(), 1)
                self.assertEqual(json.loads(output.getvalue()),
                                 {"event": "schedule", "result": "failed", **record})

class RestoreTests(Fixture):
    def setUp(self):
        super().setUp()
        backup.mkdir(self.p["restore_root"])
        guard = mock.patch.object(restore, "restore_capacity")
        guard.start()
        self.addCleanup(guard.stop)
    def test_tombstone_preflight_fails_closed(self):
        captured = int(time.time()) - 10
        restore.tombstone_preflight(self.ledger(), self.p, captured)
        for changes, code in (({"captured_at": captured - 1}, "stale"),
                              ({"captured_at": int(time.time()) + 60}, "stale"),
                              ({"policy_sha256": "invalid"}, "policy_mismatch"),
                              ({"tombstones": [{"account": "synthetic-erased"}]}, "propagation_required")):
            with self.subTest(changes=changes), self.assertRaisesRegex(backup.BackupError, code):
                restore.tombstone_preflight(self.ledger(**changes), self.p, captured)

    def test_restore_and_drill_verify_what_status_does_not(self):
        older = self.create(created=int(time.time()) - 3600)
        newest = self.create()
        for corrupted, drill in ((older, True), (newest, False)):
            with self.subTest(corrupted=corrupted.name, drill=drill):
                data = corrupted / "state/players/42"
                data.write_bytes(data.read_bytes() + b"corruption")
                self.assertEqual(backup.status(self.p)["result"], "ok")
                with mock.patch.object(restore, "service_load") as service, \
                     self.assertRaisesRegex(backup.BackupError, "generation_checksum_mismatch"):
                    restore.restore(self.p, None, self.ledger(), drill=drill)
                service.assert_not_called()
                self.assertFalse(list(self.p["restore_root"].glob("candidate-*")))
                data.write_bytes(data.read_bytes()[:-len(b"corruption")])

    def test_restore_rejects_tombstones_before_candidate_or_service(self):
        for mode in sorted(backup.MODES):
            with self.subTest(mode=mode):
                self.create(mode)
                ledger = self.ledger(tombstones=[{"account": "synthetic-erased"}])
                with mock.patch.object(restore, "service_load") as service:
                    with self.assertRaisesRegex(backup.BackupError, "propagation_required"):
                        restore.restore(self.p, None, ledger)
                    service.assert_not_called()
                self.assertFalse(list(self.p["restore_root"].glob("candidate-*")))


    def test_failed_service_never_qualifies_and_preserves_generation(self):
        generation = self.create()
        before = backup.inventory(generation)
        live = backup.inventory(self.base / "live", exclude_locks=True)
        with mock.patch.object(backup, "run", return_value=b'{"players_loaded": 1}'), \
             mock.patch.object(restore, "service_load", side_effect=backup.BackupError("synthetic_service_failure")):
            with self.assertRaisesRegex(backup.BackupError, "synthetic_service_failure"):
                restore.restore(self.p, None, self.ledger())
        candidates = list(self.p["restore_root"].glob("candidate-*"))
        self.assertEqual(len(candidates), 1)
        self.assertTrue((candidates[0] / "FAILED.json").is_file())
        self.assertFalse((candidates[0] / "QUALIFIED.json").exists())
        self.assertEqual(backup.inventory(generation), before)
        self.assertEqual(backup.inventory(self.base / "live", exclude_locks=True), live)

    def test_erasure_evidence_changed_during_restore_never_qualifies(self):
        generation = self.create()
        before = backup.inventory(generation)
        ledger = self.ledger()
        def change_evidence(*unused):
            self.ledger(tombstones=[{"account": "synthetic-erased"}])
        with mock.patch.object(backup, "run", return_value=b'{"players_loaded": 1}'), \
             mock.patch.object(restore, "service_load", change_evidence):
            with self.assertRaisesRegex(backup.BackupError, "propagation_required"):
                restore.restore(self.p, None, ledger)
        self.assertFalse(list(self.p["restore_root"].glob("candidate-*/QUALIFIED.json")))
        self.assertEqual(backup.inventory(generation), before)

if __name__ == "__main__":
    unittest.main()
