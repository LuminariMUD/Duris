#!/usr/bin/env python3
"""Disposable Linux/MariaDB/native recovery integration.

Build bin/server/dms_new with make -C src, then run
DURIS_RUN_BACKUP_INTEGRATION=1 python3 tests/async/test_persistence_backup_integration.py.
Requires g++, libcrypto,
MariaDB server/client tools, bash, openssl and unshare permission (CAP_SYS_ADMIN
in the validation container). Uses no existing DB, runtime .env, Redis or game.
Every daemon has its own new datadir and Unix socket with TCP disabled; candidate
game processes boot in their own network namespaces and are terminated afterward.
All filesystem deletion is limited to this test's TemporaryDirectory. Startup
timeouts (60s) may need investigation on heavily contended machines.
"""
import functools
import os
from pathlib import Path
import shutil
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
import build_restore_qualifier as native
import migration_runner as migrations
from test_persistence_backup import policy


def sql(env, query=None, payload=None):
    args = ["mysql", "--no-defaults", "--protocol=socket", "--socket=" + env["DB_SOCKET"],
            "--user=restore", "-N", "-B", "duris_restore"]
    if query is not None:
        args += ["-e", query]
    return backup.run(args, phase="test", env=env, input=payload).decode().strip()


FIXTURE = ROOT / "bin/tools/persistence_restore_fixture"


@functools.cache
def build_native_fixture():
    native.build()
    sources = []
    for name in native.SOURCES:
        found = list((ROOT / "src").rglob(name + ".c"))
        if len(found) != 1:
            raise RuntimeError("ambiguous fixture source")
        sources.append(str(found[0]))
    subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Wpedantic", "-Werror", "-Isrc",
                    "-ffunction-sections", "-fdata-sections", "-Wl,--gc-sections",
                    "tests/async/persistence_restore_fixture.cpp", *sources, "-lcrypto", "-lz", "-pthread",
                    "-o", str(FIXTURE)], cwd=ROOT, check=True)
    return FIXTURE


@unittest.skipUnless(os.environ.get("DURIS_RUN_BACKUP_INTEGRATION") == "1",
                     "requires explicit disposable Linux integration invocation")
class PersistenceRecoveryIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for command in ("g++", "mysql", "mysqldump", "mariadbd", "mariadb-install-db", "unshare", "openssl"):
            if not shutil.which(command):
                raise RuntimeError("integration prerequisite unavailable: " + command)
        if not (ROOT / "bin/server/dms_new").is_file():
            raise RuntimeError("build the server binary before integration")
        cls.old_umask = os.umask(0o077)
        cls.fixture = FIXTURE

    @classmethod
    def tearDownClass(cls):
        os.umask(cls.old_umask)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="duris-restore-integration-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.p = policy(self.base)
        self.p["journal_roots"] = {}
        self.p["restore_root"].mkdir(mode=0o700)
        subprocess.run(["mount", "-t", "tmpfs", "-o", "size=512M,mode=0700", "tmpfs",
                        str(self.p["restore_root"])], check=True)
        self.addCleanup(subprocess.run, ["umount", str(self.p["restore_root"])], check=True)

    def ledger(self):
        path = self.base / "independent-tombstones.json"
        backup.write_json(path, dict(version=1, captured_at=int(time.time()), tombstones=[],
                                    policy_sha256=backup.digest(ROOT / "migrations/data_lifecycle_manifest.json")))
        return path

    def test_locker_receipt_qualification_rejects_corruption_and_unexpected_entries(self):
        build_native_fixture()
        for case in ("valid", "retired-journal", "corrupt", "wrong-pid", "zero-pid", "oversized",
                     "extra-file", "foreign-file", "nested-directory", "nonempty-lock",
                     "public-file", "public-directory", "symlink-file", "symlink-directory",
                     "hardlink-file"):
            with self.subTest(case=case):
                candidate = self.p["restore_root"] / case
                candidate.mkdir(mode=0o700)
                backup.write_json(candidate / "ISOLATED_RESTORE", {"synthetic": True})
                store = candidate / "journals/critical/locker-identification"
                backup.run([str(self.fixture), "seed-receipt", str(store)], phase="test")
                receipt = store / "42.receipt"
                lock = store / ".service-lock"
                lock.touch(mode=0o600)
                if case == "corrupt":
                    receipt.write_bytes(b"corrupt")
                elif case in ("wrong-pid", "zero-pid"):
                    receipt.rename(store / ("43.receipt" if case == "wrong-pid" else "0.receipt"))
                elif case == "oversized":
                    receipt.write_bytes(b"x" * (70 * 1024))
                elif case == "retired-journal":
                    # What an older server's critical-command journal left behind.
                    (store.parent / "critical-command.journal").write_bytes(b"old records")
                    (store.parent / "critical-command.journal.tmp").touch(mode=0o600)
                elif case == "extra-file":
                    (store / "unexpected").touch(mode=0o600)
                elif case == "foreign-file":
                    (store.parent / "player-save.journal").touch(mode=0o600)
                elif case == "nested-directory":
                    (store / "unexpected").mkdir(mode=0o700)
                elif case == "nonempty-lock":
                    lock.write_bytes(b"not lock metadata")
                elif case == "public-file":
                    receipt.chmod(0o644)
                elif case == "public-directory":
                    store.chmod(0o755)
                elif case == "symlink-file":
                    target = candidate / "target"
                    receipt.rename(target)
                    receipt.symlink_to(target)
                elif case == "symlink-directory":
                    target = candidate / "target"
                    store.rename(target)
                    store.symlink_to(target, target_is_directory=True)
                elif case == "hardlink-file":
                    os.link(receipt, candidate / "alias")
                command = [str(ROOT / "bin/tools/qualify_flatfile_restore"), "--receipts", str(candidate)]
                if case in ("valid", "retired-journal"):
                    backup.run(command, phase="test")
                else:
                    with self.assertRaises(backup.BackupError):
                        backup.run(command, phase="test")

    def test_qualifier_checks_nonempty_combat_and_starter_records(self):
        build_native_fixture()
        for case in ("combat-valid", "combat-corrupt", "combat-truncated", "starter-valid",
                     "starter-committed", "starter-corrupt", "starter-wrong-pid"):
            with self.subTest(case=case):
                candidate = self.p["restore_root"] / case
                candidate.mkdir(mode=0o700)
                backup.write_json(candidate / "ISOLATED_RESTORE", {"synthetic": True})
                critical = candidate / "journals/critical"
                combat = case.startswith("combat")
                seed = ("seed-combat" if combat else
                        "seed-starter-committed" if case == "starter-committed" else "seed-starter")
                backup.run([str(self.fixture), seed, str(critical)], phase="test")
                record = (critical / "combat-intents" / ("c1" + "00" * 15 + ".intent") if combat
                          else critical / "starter-kits/42.kit")
                if case.endswith("-corrupt"):
                    data = record.read_bytes()
                    record.write_bytes(data[:-1] + bytes([data[-1] ^ 1]))
                elif case.endswith("-truncated"):
                    record.write_bytes(record.read_bytes()[:-1])
                elif case.endswith("-wrong-pid"):
                    record.rename(record.with_name("43.kit"))
                command = [str(ROOT / "bin/tools/qualify_flatfile_restore"), "--receipts", str(candidate)]
                if case.endswith(("-valid", "-committed")):
                    backup.run(command, phase="test")
                else:
                    with self.assertRaises(backup.BackupError):
                        backup.run(command, phase="test")
    def test_mariadb_full_dump_schema_history_values_and_isolated_service_boot(self):
        build_native_fixture()
        source = self.base / "live"
        source.mkdir(mode=0o700)
        with restore.private_database(source) as env:
            self.p["journal_roots"] = {"critical": Path(env["CRITICAL_COMMAND_JOURNAL_DIR"])}
            for journal in self.p["journal_roots"].values():
                journal.mkdir(mode=0o700, parents=True)
            sql(env, payload=(ROOT / "migrations/bootstrap_multithread_safe.sql").read_bytes())
            with mock.patch.dict(os.environ, env, clear=True):
                manifest = migrations.load_manifest()
                executor = migrations.MysqlExecutor(manifest)
                executor.command.insert(1, "--no-defaults")
                executor.adopt("fresh_bootstrap")
                migrations.run_pending(manifest, executor)
            sql(env, "INSERT INTO accounts(account_name,email,confirmed) VALUES('SyntheticRestore','fixture@example.test',1);"
                     "INSERT INTO player_data(pid,name,account_name,copper,silver,gold,platinum,epics,epic_revision) "
                     "VALUES(42,'SyntheticPlayer','SyntheticRestore',11,12,13,14,15,0);"
                     "INSERT INTO account_characters(account_name,pid,char_name) VALUES('SyntheticRestore',42,'SyntheticPlayer');"
                     "INSERT INTO account_banks(id,account_name,racewar,bank_copper,bank_silver,bank_gold,bank_platinum) "
                     "VALUES(1,'SyntheticRestore',0,21,22,23,24);"
                     "INSERT INTO currency_wallet_baseline(pid,opening_copper,opening_silver,opening_gold,opening_platinum) VALUES(42,11,12,13,14);"
                     "INSERT INTO currency_bank_baseline(bank_id,opening_copper,opening_silver,opening_gold,opening_platinum) VALUES(1,21,22,23,24);"
                     "INSERT INTO epic_balance_baseline(pid,opening_balance) VALUES(42,15);"
                     "INSERT INTO combat_frag_baseline(pid,opening_frags) VALUES(42,0);")
            restore.database_qualify(env, "test")
            query = ("SELECT CONCAT(a.account_name,':',p.pid,':',p.copper,':',p.epics,':',b.bank_gold) "
                     "FROM accounts a JOIN player_data p ON p.account_name=a.account_name "
                     "JOIN account_banks b ON b.account_name=a.account_name WHERE p.pid=42;")
            expected = sql(env, query)
            self.assertEqual(expected, "SyntheticRestore:42:11:15:23")
            store = self.p["journal_roots"]["critical"] / "locker-identification"
            backup.run([str(self.fixture), "seed-receipt", str(store)], phase="test")
            receipt_bytes = (store / "42.receipt").read_bytes()
            critical = self.p["journal_roots"]["critical"]
            backup.run([str(self.fixture), "seed-combat-recorded", str(critical)], phase="test")
            backup.run([str(self.fixture), "seed-starter-committed", str(critical)], phase="test")
            with mock.patch.dict(os.environ, env, clear=True):
                result = backup.backup(self.p, "mariadb-primary")
            generation = self.p["root"] / result["generation"]
            captured = backup.inventory(generation)
            # Preserve the shared foreign-owned checkout regression on MariaDB:
            # mapped namespace root cannot traverse this private source directory.
            checkout = self.base / "private-checkout"
            checkout.mkdir(mode=0o700)
            for name in ("areas_mini", "lib"):
                shutil.copytree(ROOT / name, checkout / name)
            for name in ("bin/server/dms_new", "scripts/qualify_service_restore.py"):
                destination = checkout / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / name, destination)
            os.chown(checkout, 65534, 65534)
            actual_service_load = restore.service_load
            checked = []
            def check_values_then_boot(candidate, mode, restored_env):
                self.assertNotEqual(restored_env["DB_SOCKET"], env["DB_SOCKET"])
                self.assertEqual(sql(restored_env, query), expected)
                checked.append(mode)
                with mock.patch.object(backup, "ROOT", checkout):
                    actual_service_load(candidate, mode, restored_env)
            with mock.patch.object(restore, "service_load", check_values_then_boot):
                receipt = restore.restore(self.p, result["generation"], self.ledger())
            self.assertEqual(checked, ["mariadb-primary"])
            self.assertEqual(checkout.stat().st_uid, 65534)
            self.assertEqual(checkout.stat().st_mode & 0o777, 0o700)
            self.assertEqual(receipt["result"], "qualified")
            self.assertEqual(sql(env, query), expected)
            self.assertEqual(backup.inventory(generation), captured)
            candidate = self.p["restore_root"] / receipt["candidate"]
            restored = candidate / "journals/critical"
            self.assertEqual((restored / "locker-identification/42.receipt").read_bytes(), receipt_bytes)
            self.assertTrue((restored / "combat-intents" / ("c2" + "00" * 15 + ".recorded")).exists())
            self.assertTrue((restored / "starter-kits/42.kit").exists())
            self.assertIn(b"Entering game loop.", (candidate / "service.log").read_bytes())
            sql(env, "INSERT INTO accounts(account_name,confirmed) VALUES('OtherSynthetic',1);"
                     "UPDATE player_data SET account_name='OtherSynthetic' WHERE pid=42;")
            with self.assertRaises(backup.BackupError):
                restore.database_qualify(env, "test")
            # Corrupt only the disposable source's migration history: the same qualifier
            # that accepted the restored values must now reject it.
            sql(env, "UPDATE player_data SET account_name='SyntheticRestore' WHERE pid=42;"
                     "UPDATE mud_schema_history SET apply_checksum=UNHEX(REPEAT('00',32)) WHERE sequence_number=1;")
            with self.assertRaises(backup.BackupError):
                restore.database_qualify(env, "test")


if __name__ == "__main__":
    unittest.main()
