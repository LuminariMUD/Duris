#!/usr/bin/env python3
"""Network addresses are kept 30 days after their last use (ADR 0003), on MariaDB.

A real server: an account's saved address list keeps each address's own last use. A login
rewrites the list, and it used to give every address the save's time, so an account that
logged in once a month kept all of its old addresses for good. Now an address last used
31 days ago is dropped at the login, one used 25 days ago keeps its time, and the one the
login came from is new.

Then the hourly prune, the maintenance job, on the same database: it deletes the address
rows (account_ips, the website's account_login_history) last written over 30 days ago,
and clears the address of older log_entries, ip_info, player_data and account_characters
rows, and nothing else. It runs without account_login_history, which only the website
creates, and with a row budget of one it clears the rest over several runs.
Run through with_disposable_mariadb.sh with the server binary as the argument.
"""
from pathlib import Path
import os
import shlex
import subprocess
import sys
import tempfile
import time
import uuid

import test_flatfile_combat_journey as journey

ROOT = Path(__file__).resolve().parents[2]

LOGIN_HISTORY = """CREATE TABLE account_login_history (
  id bigint unsigned NOT NULL AUTO_INCREMENT,
  account_name varchar(50) NOT NULL,
  ip_address varchar(45) DEFAULT NULL,
  status enum('login','logout') NOT NULL,
  `timestamp` timestamp NOT NULL DEFAULT current_timestamp(),
  character_name varchar(50) DEFAULT NULL,
  hostname varchar(255) DEFAULT NULL,
  PRIMARY KEY (id),
  KEY idx_timestamp (`timestamp`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci"""


def run(server):
    host = os.environ['TEST_DB_HOST']
    assert host == '127.0.0.1', 'use a disposable loopback database'
    database = 'address_retention_' + uuid.uuid4().hex[:12]
    environment = {
        'PATH': os.environ.get('PATH', '/usr/bin:/bin'),
        'ENVIRONMENT': 'local', 'DB_HOST': host,
        'DB_PORT': os.environ['TEST_DB_PORT'], 'DB_NAME': database,
        'DB_USER': os.environ['TEST_DB_USER'],
        'DB_PASSWD': os.environ['TEST_DB_PASSWORD'],
        'DB_ALLOWED_TARGETS': host + '/' + database,
        'MYSQL_PWD': os.environ['TEST_DB_PASSWORD'],
        'PERSISTENCE_MODE': 'mariadb-primary', 'DB_TLS': 'FALSE',
        'REDIS': 'FALSE', 'CHAOS_MUD': 'FALSE',
        'LISTEN_ADDRESS': host, 'DURIS_WEBSOCKET_LISTEN_ADDRESS': host,
    }
    if 'LD_LIBRARY_PATH' in os.environ:
        environment['LD_LIBRARY_PATH'] = os.environ['LD_LIBRARY_PATH']
    mysql = ['mysql', '--protocol=tcp', '-h', host, '-P', environment['DB_PORT'],
             '-u', environment['DB_USER'], '-N', '-B']

    def sql(statement, selected=True):
        return subprocess.check_output(mysql + ([database] if selected else []),
                                       input=statement, text=True, env=environment).strip()

    def addresses():
        return dict(line.split('\t') for line in sql(
            "SELECT ip_address, DATEDIFF(NOW(), updated_at) FROM account_ips WHERE "
            f"account_name='{journey.ACCOUNT}'").splitlines())

    sql('CREATE DATABASE ' + database + ' CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci',
        False)
    try:
        sql((ROOT / 'migrations/bootstrap_multithread_safe.sql').read_text())
        for args in (('adopt', '--kind', 'fresh_bootstrap'), ('run',)):
            result = subprocess.run(['python3', 'scripts/migration_runner.py', *args],
                                    cwd=ROOT, env=environment, capture_output=True, text=True)
            assert result.returncode == 0, result.stdout + result.stderr
        (ROOT / 'bin/tests').mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='address-retention-',
                                         dir=ROOT / 'bin/tests') as temporary:
            runtime = Path(temporary)
            journey.make_fixture(runtime)
            journey.generate_certificate(runtime)
            (runtime / 'logs/log').mkdir(parents=True)
            (runtime / 'journals/critical').mkdir(parents=True, mode=0o700)
            plain, tls, websocket = journey.available_ports()
            environment.update(CRITICAL_COMMAND_JOURNAL_DIR=str(runtime / 'journals/critical'),
                               DURIS_TLS_PORT=str(tls), DURIS_WEBSOCKET_PORT=str(websocket))
            output_path = runtime / 'server.out'
            process = client = None

            def boot():
                with output_path.open('w') as output:
                    started = subprocess.Popen(
                        [str(server), '--minimal', '-s', '-d', str(runtime), str(plain)],
                        cwd=runtime, env=environment, stdout=output, stderr=subprocess.STDOUT)
                deadline = time.monotonic() + 120
                while b'Entering game loop.' not in output_path.read_bytes():
                    assert started.poll() is None and time.monotonic() < deadline, \
                        'the address retention journey failed to boot'
                    time.sleep(.1)
                return started

            def leave_and_stop():
                client.send('quit')
                client.expect('ACCOUNT MENU', timeout=30)
                client.send('0')
                client.close()
                process.terminate()
                process.wait(timeout=45)
                assert process.returncode == 0, 'the server did not shut down cleanly'

            try:
                process = boot()
                client = journey.MudClient(plain)
                journey.create_character(client)
                leave_and_stop()
                # With the server down, so that no save of the account is still queued.
                sql("INSERT INTO account_ips (account_name, hostname, ip_address, count, "
                    f"updated_at) VALUES ('{journey.ACCOUNT}', 'a', '10.0.0.25', 1, "
                    f"NOW() - INTERVAL 25 DAY), ('{journey.ACCOUNT}', 'b', '10.0.0.31', 1, "
                    "NOW() - INTERVAL 31 DAY)")
                process = boot()
                client = journey.reconnect_character(plain)
                leave_and_stop()
                kept = addresses()
                assert kept == {'10.0.0.25': '25', '127.0.0.1': '0'}, kept
                print('[PASS] a login keeps each address its own last use and drops one '
                      'past 30 days', flush=True)
            except Exception:
                print(output_path.read_text(errors='replace')[-6000:])
                print(journey.runtime_logs(runtime)[-6000:])
                if client:
                    print(client.transcript.decode(errors='replace')[-6000:])
                raise
            finally:
                if client:
                    client.close()
                if process and process.poll() is None:
                    process.kill()
                    process.wait(timeout=10)

        harness = ROOT / 'bin/tests/address_retention_mysql_harness'
        subprocess.run(
            ['g++', '-std=c++20', '-Wall', '-Wextra', '-Werror', '-Isrc',
             *shlex.split(subprocess.check_output(['mysql_config', '--cflags'], text=True)),
             '-ffunction-sections', '-fdata-sections',
             'tests/async/address_retention_mysql_harness.cpp',
             'src/persistence/maintenance_repository.c',
             'src/persistence/persistence_observability.c', '-Wl,--gc-sections',
             *shlex.split(subprocess.check_output(['mysql_config', '--libs'], text=True)),
             '-o', str(harness)], cwd=ROOT, check=True)

        def prune(budget):
            # The job also expires log files under its working directory.
            with tempfile.TemporaryDirectory(dir=ROOT / 'bin/tests') as cwd:
                return subprocess.run(
                    [str(harness), host, environment['DB_PORT'], environment['DB_USER'],
                     environment['DB_PASSWD'], database, str(budget)],
                    cwd=cwd, capture_output=True, text=True, check=True).stdout.split('\n')[:-1]

        # The database the migrations build has no account_login_history.
        assert prune(256) == ['complete 0'], 'the prune failed without the website table'

        sql(LOGIN_HISTORY)
        sql(f"""
INSERT INTO account_ips (account_name, hostname, ip_address, count, updated_at) VALUES
  ('{journey.ACCOUNT}', 'c', '10.0.0.40', 1, NOW() - INTERVAL 40 DAY);
INSERT INTO account_login_history (account_name, ip_address, status, `timestamp`) VALUES
  ('{journey.ACCOUNT}', '10.4.4.4', 'login', NOW() - INTERVAL 31 DAY),
  ('{journey.ACCOUNT}', '10.4.4.5', 'login', NOW() - INTERVAL 29 DAY);
INSERT INTO log_entries (date, kind, player_name, ip_address, message) VALUES
  (NOW() - INTERVAL 31 DAY, 'wiz', 'Oldone', '10.1.1.1', 'old line'),
  (NOW() - INTERVAL 45 DAY, 'wiz', 'Oldone', '10.1.1.1', 'older line'),
  (NOW() - INTERVAL 29 DAY, 'wiz', 'Newone', '10.1.1.2', 'new line');
INSERT INTO ip_info (pid, last_ip, last_connect, last_disconnect) VALUES
  (9001, '10.2.2.1', NOW() - INTERVAL 31 DAY, NOW() - INTERVAL 31 DAY),
  (9002, '10.2.2.2', NOW() - INTERVAL 29 DAY, NOW() - INTERVAL 29 DAY);
INSERT INTO player_data (pid, name, last_ip, last_save) VALUES
  (9001, 'Oldone', 167838209, NOW() - INTERVAL 31 DAY),
  (9002, 'Newone', 167838210, NOW() - INTERVAL 29 DAY);
INSERT INTO account_characters (account_name, pid, char_name, last_ip, last_login) VALUES
  ('{journey.ACCOUNT}', 9001, 'Oldone', '10.3.3.1', NOW() - INTERVAL 31 DAY),
  ('{journey.ACCOUNT}', 9002, 'Newone', '10.3.3.2', NOW() - INTERVAL 29 DAY);
""")
        before = {
            'log_entries': sql('SELECT COUNT(*) FROM log_entries'),
            'player_data': sql('SELECT COUNT(*) FROM player_data'),
        }
        # One row per table a run: the second old log line waits for the second run.
        assert prune(1) == ['more 6', 'more 1', 'complete 0']
        assert addresses() == {'10.0.0.25': '25', '127.0.0.1': '0'}, addresses()
        assert sql('SELECT ip_address FROM account_login_history') == '10.4.4.5'
        assert sql("SELECT player_name, ip_address, message FROM log_entries WHERE "
                   "player_name IN ('Oldone','Newone') ORDER BY id").splitlines() == \
            ['Oldone\t\told line', 'Oldone\t\tolder line', 'Newone\t10.1.1.2\tnew line']
        assert sql('SELECT pid, last_ip FROM ip_info WHERE pid > 9000 ORDER BY pid'
                   ).splitlines() == ['9001\tnone', '9002\t10.2.2.2']
        assert sql('SELECT pid, last_ip FROM player_data WHERE pid > 9000 ORDER BY pid'
                   ).splitlines() == ['9001\t0', '9002\t167838210']
        assert sql('SELECT pid, IFNULL(last_ip, "NULL") FROM account_characters WHERE '
                   'pid > 9000 ORDER BY pid').splitlines() == ['9001\tNULL', '9002\t10.3.3.2']
        # The game's own rows of this run are recent and keep their addresses.
        assert sql("SELECT COUNT(*) FROM ip_info WHERE pid < 9000 AND last_ip='127.0.0.1'") == '1'
        assert before == {'log_entries': sql('SELECT COUNT(*) FROM log_entries'),
                          'player_data': sql('SELECT COUNT(*) FROM player_data')}
        print('[PASS] the prune clears exactly the addresses past 30 days', flush=True)
    finally:
        sql('DROP DATABASE ' + database, False)


if __name__ == '__main__':
    run(Path(sys.argv[1]).resolve(strict=True))
