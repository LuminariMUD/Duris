#!/usr/bin/env python3
"""A new database reaches the migration head on every supported engine, through the runner.

The sealed verifiers of 0031 and 0032 accept only MariaDB 10.11 and MySQL 8.0, so a
database built on MariaDB 11.8 stopped at 0031 ("unsupported database engine"). Their
files cannot change: each history row keeps the verifier's checksum. The manifest now
lists an 11.8 verifier for each, and the runner runs it in their place on 11.8.

On each image: bootstrap, `migration_runner.py adopt` and `run` reach all migrations,
with the history checksum the manifest gives on every engine, and an edited history row
then stops the runner.

Usage: run_migration_runner_engines.py [image ...]; the default is all three.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import os
import subprocess
import sys
import tempfile
import time
import uuid
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import migration_runner as runner  # noqa: E402

IMAGES = ("mariadb:11.8", "mariadb:10.11", "mysql:8.0")


def check_lock(environment, sql):
    """Two ordinary executors exclude each other and detect server-side lock loss."""
    with mock.patch.dict(os.environ, environment):
        first = runner.MysqlExecutor(runner.load_manifest())
        second = runner.MysqlExecutor(runner.load_manifest())
        connection = None
        try:
            first.acquire_lock()
            assert sql("SELECT IS_USED_LOCK('duris_immutable_migration')") == str(first.lock_connection_id)
            first.require_quiescent()  # Its own lock session is not another writer.
            try:
                second.acquire_lock()
            except runner.MigrationContractError as error:
                assert 'lock unavailable' in str(error)
            else:
                raise AssertionError('two normal runners acquired the migration lock')
            assert first.sql('SELECT 42') == '42'
            assert first.sql('SELECT CONNECTION_ID()') == str(first.lock_connection_id)
            # Both SQL input and output can exceed a pipe buffer without deadlocking.
            assert first.sql('', ("SELECT REPEAT('x',131072);\n/*" + 'y' * 131072 +
                                  "*/\nSELECT 7;\n").encode()) == 'x' * 131072 + '\n7'

            connection = subprocess.Popen(first.command + ['--unbuffered'],
                                          stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                          stderr=subprocess.PIPE, env=environment, text=True)
            connection.stdin.write('SELECT CONNECTION_ID();\n')
            connection.stdin.flush()
            assert connection.stdout.readline().strip().isdigit()
            try:
                first.require_quiescent()
            except runner.MigrationContractError as error:
                assert 'every other database connection' in str(error)
            else:
                raise AssertionError('ordinary quiescence ignored another connection')
            connection.communicate(timeout=5)
            connection = None
            first.require_quiescent()

            # Kill the owner while apply is in flight, then let a competing runner
            # acquire the lock. No statement after the killed query may execute.
            with tempfile.TemporaryDirectory() as temporary, ThreadPoolExecutor() as pool:
                apply_path = Path(temporary) / 'interrupted.sql'
                apply_path.write_text(
                    "SELECT SLEEP(4) /* migration_lock_inflight */;\n"
                    "CREATE TABLE lock_loss_must_not_write(id INT);\n")
                migration = runner.replace(runner.load_manifest().migrations[0],
                                           apply_path=apply_path)
                operation = pool.submit(first.apply, migration)
                deadline = time.monotonic() + 10
                while sql("SELECT COUNT(*) FROM information_schema.PROCESSLIST "
                          "WHERE INFO LIKE 'SELECT SLEEP(4)%'") != '1':
                    assert time.monotonic() < deadline, 'migration did not enter its long query'
                    time.sleep(0.05)
                sql(f'KILL {first.lock_connection_id}')
                second.acquire_lock()
                try:
                    operation.result(timeout=10)
                except runner.MigrationContractError:
                    pass
                else:
                    raise AssertionError('killed migration reported success')
                assert sql("SELECT COUNT(*) FROM information_schema.tables WHERE "
                           "table_schema=DATABASE() AND table_name='lock_loss_must_not_write'") == '0', \
                    'migration continued writing after its advisory lock was released'
                first.release_lock()
                second.release_lock()
                first.acquire_lock()

            sql(f'KILL {first.lock_connection_id}')
            try:
                first.sql('CREATE TABLE lock_loss_must_not_write(id INT)')
            except runner.MigrationContractError as error:
                assert 'lock connection was lost' in str(error)
            else:
                raise AssertionError('lost server lock allowed another operation')
            assert sql("SELECT COUNT(*) FROM information_schema.tables WHERE "
                       "table_schema=DATABASE() AND table_name='lock_loss_must_not_write'") == '0'
            first.release_lock()
            second.acquire_lock()
            second.require_quiescent()
        finally:
            if connection is not None:
                connection.kill()
                connection.communicate()
            first.release_lock()
            second.release_lock()


def check(image: str, expected_head: str) -> None:
    name = "duris-runner-engines-" + uuid.uuid4().hex[:10]
    password = "runner-" + uuid.uuid4().hex[:12]
    variable = "MARIADB_ROOT_PASSWORD" if image.startswith("mariadb") else "MYSQL_ROOT_PASSWORD"
    # The host's client is MariaDB's; MySQL 8.0 serves it native passwords.
    extra = ["--default-authentication-plugin=mysql_native_password"] \
        if image.startswith("mysql") else []
    subprocess.run(["docker", "run", "-d", "--name", name, "-p", "127.0.0.1::3306",
                    "-e", f"{variable}={password}", image, *extra],
                   check=True, capture_output=True)
    try:
        port = subprocess.check_output(["docker", "port", name, "3306/tcp"],
                                       text=True).split(":")[-1].strip()
        environment = dict(os.environ, ENVIRONMENT="test", DB_HOST="127.0.0.1",
                           DB_PORT=port, DB_USER="root", DB_PASSWD=password,
                           DB_NAME="runner_engines", MYSQL_PWD=password)
        mysql = ["mysql", "--protocol=tcp", "-h", "127.0.0.1", "-P", port, "-uroot", "-N", "-B"]

        def sql(statement, database="runner_engines"):
            return subprocess.check_output(mysql + ([database] if database else []),
                                           input=statement, text=True,
                                           env=environment).strip()

        deadline = time.monotonic() + 120
        while subprocess.run(mysql + ["-e", "SELECT 1"], env=environment,
                             capture_output=True).returncode:
            assert time.monotonic() < deadline, f"{image} did not start"
            time.sleep(1)
        time.sleep(2)
        version = sql("SELECT VERSION();", None)
        sql("CREATE DATABASE runner_engines CHARACTER SET utf8mb4 "
            "COLLATE utf8mb4_unicode_ci;", None)
        check_lock(environment, sql)
        print(f'[PASS] {image}: normal runner lock exclusion, quiescence and server-side loss', flush=True)
        sql((ROOT / "migrations/bootstrap_multithread_safe.sql").read_text())

        # Reproduce the real pre-0044 shape and an interrupted/incorrect partial
        # apply. Existing evidence must survive; a failed verifier cannot advance
        # the ledger. The fresh-bootstrap shape is checked by the runtime leg.
        sql("ALTER TABLE artifact_domain_state DROP INDEX uq_artifact_canonical_uid, "
            "DROP COLUMN identity_state, DROP COLUMN canonical_item_uid")
        sql("INSERT INTO artifact_domain_state(vnum,owned,loc_type,location,timer_epoch,"
            "artifact_type,bind_owner_pid,bind_timer_epoch) "
            "VALUES(2147483000,0,2,81,1234,1,-1,17)")
        sql("INSERT INTO item_current_owner(item_uid,root_item_uid,owner_type,owner_id,"
            "item_revision,vnum,state) VALUES(555,555,3,1200,8,2147482999,1)")
        sql("INSERT INTO artifact_domain_state(vnum,owned,loc_type,location,timer_epoch,"
            "artifact_type,bind_owner_pid,bind_timer_epoch,item_uid,item_revision) "
            "VALUES(2147482999,1,4,1200,4321,2,42,71,555,8)")
        sql("ALTER TABLE artifact_domain_state ADD canonical_item_uid BIGINT UNSIGNED NULL "
            "AFTER updated_at, ADD identity_state SMALLINT UNSIGNED NOT NULL DEFAULT 0 "
            "AFTER canonical_item_uid")

        def migrate(*arguments):
            return subprocess.run([sys.executable, "scripts/migration_runner.py", *arguments],
                                  cwd=ROOT, env=environment, capture_output=True, text=True)

        result = migrate("adopt", "--kind", "fresh_bootstrap")
        assert result.returncode == 0, f"{image} ({version}): {result.stderr}"
        refused = migrate("run")
        assert refused.returncode == 2 and 'artifact canonical identity schema differs' in refused.stderr, \
            f"{image}: incompatible identity column was not refused: {refused.stderr}"
        assert sql("SELECT applied_count FROM mud_schema_migration_state") == '43'
        assert sql("SELECT timer_epoch,bind_timer_epoch,canonical_item_uid IS NULL,identity_state "
                   "FROM artifact_domain_state WHERE vnum=2147483000") == '1234\t17\t1\t0'
        sql("ALTER TABLE artifact_domain_state MODIFY identity_state "
            "TINYINT UNSIGNED NOT NULL DEFAULT 0 AFTER canonical_item_uid")
        result = migrate("run")
        assert result.returncode == 0, f"{image} ({version}): {result.stderr}"
        head = sql("SELECT applied_count, LOWER(HEX(history_checksum)) FROM "
                   "mud_schema_migration_state WHERE state_id=1;")
        assert head == expected_head, f"{image} ({version}) stopped at {head}"
        assert sql('SELECT item_uid,item_revision,canonical_item_uid IS NULL,identity_state,'
                   'timer_epoch,bind_owner_pid,bind_timer_epoch FROM artifact_domain_state '
                   'WHERE vnum=2147482999') == '555\t8\t1\t0\t4321\t42\t71'

        def refused_sql(statement, code):
            result = subprocess.run(mysql + ['runner_engines'], input=statement, text=True,
                                    env=environment, capture_output=True)
            assert result.returncode != 0 and 'ERROR ' + str(code) in result.stderr, \
                f'{image}: expected database refusal {code}'

        # Canonical identity exists before custody (NPC/ground) and after physical
        # retirement. Keep the existing nullable custody FK, without fake owners.
        uid = 18446744073709551600
        refused_sql(f'UPDATE artifact_domain_state SET item_uid={uid} WHERE vnum=2147483000', 1452)
        sql(f'UPDATE artifact_domain_state SET canonical_item_uid={uid},identity_state=1 '
            'WHERE vnum=2147483000')
        assert sql('SELECT canonical_item_uid,identity_state,item_uid IS NULL FROM '
                   'artifact_domain_state WHERE vnum=2147483000') == f'{uid}\t1\t1'
        sql('INSERT INTO artifact_domain_state(vnum) VALUES(2147483001)')
        refused_sql(f'UPDATE artifact_domain_state SET canonical_item_uid={uid},identity_state=1 '
                    'WHERE vnum=2147483001', 1062)
        sql('UPDATE artifact_domain_state SET identity_state=2 WHERE vnum=2147483000')
        sql('UPDATE artifact_domain_state SET identity_state=3 WHERE vnum=2147483001')
        assert sql('SELECT timer_epoch,bind_timer_epoch FROM artifact_domain_state '
                   'WHERE vnum=2147483000') == '1234\t17'
        result = migrate('run')  # exact replay preserves both identity states
        assert result.returncode == 0, f'{image}: exact identity replay failed'
        step = next(step for step in runner.load_manifest().migrations
                    if step.migration_id == '0044_artifact_canonical_identity')

        def verify():
            return subprocess.run(['bash', str(step.verify_path)], cwd=ROOT,
                                  env=environment, capture_output=True, text=True)

        assert verify().returncode == 0
        for state, canonical in ((0, str(uid)), (1, 'NULL'), (2, '0'), (4, 'NULL')):
            sql(f'UPDATE artifact_domain_state SET identity_state={state},'
                f'canonical_item_uid={canonical} WHERE vnum=2147483000')
            assert verify().returncode != 0, f'{image}: inconsistent UID/state accepted'
        sql(f'UPDATE artifact_domain_state SET identity_state=2,canonical_item_uid={uid} '
            'WHERE vnum=2147483000')
        for key in ('KEY uq_artifact_canonical_uid(canonical_item_uid)',
                    'UNIQUE KEY uq_artifact_canonical_uid(canonical_item_uid,vnum)'):
            sql('ALTER TABLE artifact_domain_state DROP INDEX uq_artifact_canonical_uid, ADD ' + key)
            assert verify().returncode != 0, f'{image}: incorrect canonical UID key accepted'
        sql('ALTER TABLE artifact_domain_state DROP INDEX uq_artifact_canonical_uid, '
            'ADD UNIQUE KEY uq_artifact_canonical_uid(canonical_item_uid)')
        assert verify().returncode == 0
        assert sql('SELECT canonical_item_uid,identity_state,timer_epoch,bind_timer_epoch FROM '
                   'artifact_domain_state WHERE vnum=2147483000') == f'{uid}\t2\t1234\t17'
        print(f'[PASS] {image}: artifact UID FK/null/unknown/present/retired/absent, partial '
              'apply, verifier refusal, replay and evidence preservation', flush=True)
        sql("UPDATE mud_schema_history SET description='edited' WHERE sequence_number=31;")
        refused = migrate("run")
        assert refused.returncode == 2 and "history" in refused.stderr, \
            f"{image}: an edited history was not refused: {refused.stderr}"
        print(f"[PASS] {image} ({version}): the runner reaches the head with the same history, "
              "and refuses an edited one", flush=True)
    finally:
        subprocess.run(["docker", "rm", "-fv", name], capture_output=True)


def main() -> int:
    manifest = runner.load_manifest()
    rows = [runner.AppliedMigration(step.migration_id, step.sequence, step.description,
                                    step.apply_checksum, step.verify_checksum,
                                    step.compatibility, manifest.runner_version)
            for step in manifest.migrations]
    expected_head = f"{len(rows)}\t{runner.history_checksum(rows)}"
    for image in sys.argv[1:] or IMAGES:
        check(image, expected_head)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
