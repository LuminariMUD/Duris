#!/usr/bin/env python3
"""Replay the real migration runner on a fresh, disposable database container."""
import argparse
from dataclasses import replace
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import migration_runner as runner


def run(image):
    name = 'duris-news-migration-' + secrets.token_hex(6)
    password = secrets.token_urlsafe(24)
    variable = 'MYSQL_ROOT_PASSWORD' if image.startswith('mysql:') else 'MARIADB_ROOT_PASSWORD'
    environment = dict(os.environ, **{variable: password, 'MYSQL_PWD': password})
    started = subprocess.run(['docker', 'run', '-d', '--name', name, '-p', '127.0.0.1::3306',
                              '-e', variable, image], env=environment, capture_output=True)
    assert started.returncode == 0, 'could not start disposable schema container'
    try:
        mapping = subprocess.check_output(['docker', 'port', name, '3306/tcp'], text=True).strip()
        port = mapping.rsplit(':', 1)[1]
        client = ['mysql', '--protocol=tcp', '-h127.0.0.1', '-P', port, '-uroot', '-N', '-B']
        for _ in range(90):
            ready = subprocess.run(client + ['-e', 'SELECT 1'], env=environment, capture_output=True)
            if ready.returncode == 0:
                break
            time.sleep(1)
        assert ready.returncode == 0, 'disposable schema container did not become ready'

        def sql(text, database=None):
            result = subprocess.run(client + ([database] if database else []), input=text,
                                    text=True, env=environment, capture_output=True)
            assert result.returncode == 0, result.stderr[-2000:]
            return result.stdout.strip()

        manifest = runner.load_manifest()
        assert manifest.migrations[-1].migration_id == '0043_news_acknowledgement'
        previous = replace(manifest, migrations=manifest.migrations[:-1])
        os.environ.update(ENVIRONMENT='test', DB_HOST='127.0.0.1', DB_PORT=port,
                          DB_USER='root', DB_PASSWD=password, DB_SOCKET='', DB_TLS='FALSE')
        for database in ('news_upgrade_test', 'news_fresh_test'):
            sql('CREATE DATABASE ' + database + ' CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
            sql((ROOT / 'migrations/bootstrap_multithread_safe.sql').read_text(), database)
            os.environ.update(DB_NAME=database, DB_ALLOWED_TARGETS='127.0.0.1/' + database)
            executor = runner.MysqlExecutor(previous if database == 'news_upgrade_test' else manifest)
            executor.acquire_lock()
            try:
                executor.adopt('fresh_bootstrap')
            finally:
                executor.release_lock()
            if database == 'news_upgrade_test':
                runner.run_pending(previous, executor)
                sql("INSERT INTO player_data(pid,name,level) VALUES(1,'Newsfixture',12)", database)
                sql("ALTER TABLE player_data ADD COLUMN last_read_news_hash VARBINARY(63) NOT NULL DEFAULT ''", database)
                executor = runner.MysqlExecutor(manifest)
                try:
                    runner.run_pending(manifest, executor)
                except runner.MigrationContractError:
                    pass
                else:
                    raise AssertionError('incompatible column was recorded as migrated')
                assert sql('SELECT applied_count FROM mud_schema_migration_state', database) == '42'
                assert sql("SELECT character_maximum_length FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='player_data' AND column_name='last_read_news_hash'", database) == '63'
                sql('ALTER TABLE player_data DROP COLUMN last_read_news_hash', database)
            runner.run_pending(manifest, executor)
            if database == 'news_fresh_test':
                sql("INSERT INTO player_data(pid,name,level) VALUES(1,'Newsfixture',12)", database)
            assert sql('SELECT name,level,LENGTH(last_read_news_hash) FROM player_data WHERE pid=1', database) == 'Newsfixture\t12\t0'
            sql("UPDATE player_data SET last_read_news_hash=REPEAT('a',64) WHERE pid=1", database)
            runner.run_pending(manifest, executor)
            step = manifest.migrations[-1]
            executor.apply(step)
            executor.verify(step)
            assert sql('SELECT applied_count FROM mud_schema_migration_state', database) == '43'
            assert sql('SELECT last_read_news_hash FROM player_data WHERE pid=1', database) == 'a' * 64
            canonical = "VARBINARY(64) NOT NULL DEFAULT ''"
            for shape in ("VARBINARY(63) NOT NULL DEFAULT ''", "VARBINARY(64) NULL DEFAULT NULL",
                          "VARCHAR(64) NOT NULL DEFAULT ''", "VARBINARY(64) NOT NULL DEFAULT 'b'"):
                # Shorten the test value before testing a smaller column; retain the row.
                sql("UPDATE player_data SET last_read_news_hash='a' WHERE pid=1", database)
                sql('ALTER TABLE player_data MODIFY last_read_news_hash ' + shape, database)
                try:
                    executor.verify(step)
                except runner.MigrationContractError:
                    pass
                else:
                    raise AssertionError('verifier accepted drift: ' + shape)
                assert sql('SELECT name,level,last_read_news_hash FROM player_data WHERE pid=1', database) == 'Newsfixture\t12\ta'
                sql('ALTER TABLE player_data MODIFY last_read_news_hash ' + canonical, database)
            executor.verify(step)
            print(image + ': ' + database + ' runner, defaults, rerun, row preservation and drift passed', flush=True)
    finally:
        subprocess.run(['docker', 'rm', '-fv', name], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, check=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--image', choices=('mysql:8.0', 'mariadb:10.11'), required=True)
    run(parser.parse_args().image)
