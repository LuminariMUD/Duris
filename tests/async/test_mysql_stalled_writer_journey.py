#!/usr/bin/env python3
"""Logging out and shutting down never wait on the database (persistence reset phase 1).

A real server on a disposable MariaDB: with the writer stalled on a locked table, quit
reaches the account menu at once and the save lands once the table is free; a relog
reads it. With the database stopped, shutdown still exits within its bound and names
the save it could not write. Run through run_mysql_stalled_writer_journey.sh, which
sets TEST_DB_* and TEST_DB_CONTAINER; --server picks the executable.
"""
from pathlib import Path
import argparse
import os
import signal
import subprocess
import tempfile
import time
import uuid

import test_flatfile_combat_journey as journey

ROOT = Path(__file__).resolve().parents[2]


def run(server):
    database = 'stalled_writer_' + uuid.uuid4().hex[:12]
    host, port = os.environ['TEST_DB_HOST'], os.environ['TEST_DB_PORT']
    assert host == '127.0.0.1', 'use a disposable loopback database'
    environment = {
        'PATH': os.environ.get('PATH', '/usr/bin:/bin'),
        'ENVIRONMENT': 'local', 'DB_HOST': host, 'DB_PORT': port, 'DB_NAME': database,
        'DB_USER': os.environ['TEST_DB_USER'], 'DB_PASSWD': os.environ['TEST_DB_PASSWORD'],
        'DB_ALLOWED_TARGETS': host + '/' + database,
        'MYSQL_PWD': os.environ['TEST_DB_PASSWORD'], 'PERSISTENCE_MODE': 'mariadb-primary',
        'DB_TLS': 'FALSE', 'REDIS': 'FALSE', 'CHAOS_MUD': 'FALSE',
        'LISTEN_ADDRESS': '127.0.0.1', 'DURIS_WEBSOCKET_LISTEN_ADDRESS': '127.0.0.1',
    }
    if 'LD_LIBRARY_PATH' in os.environ:
        environment['LD_LIBRARY_PATH'] = os.environ['LD_LIBRARY_PATH']
    mysql = ['mysql', '--protocol=tcp', '-h', host, '-P', port, '-u', environment['DB_USER'],
             '-N', '-B']

    def sql(text, selected=True):
        return subprocess.check_output(mysql + ([database] if selected else []), input=text,
                                       text=True, env=environment).strip()

    sql('CREATE DATABASE ' + database + ' CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci',
        False)
    sql((ROOT / 'migrations/bootstrap_multithread_safe.sql').read_text())
    for args in (('adopt', '--kind', 'fresh_bootstrap'), ('run',)):
        subprocess.run(['python3', 'scripts/migration_runner.py', *args], cwd=ROOT,
                       env=environment, check=True, capture_output=True)
    with tempfile.TemporaryDirectory(prefix='stalled-writer-', dir=ROOT / 'bin/tests') as tmp:
        runtime = Path(tmp)
        journey.make_fixture(runtime)
        journey.generate_certificate(runtime)
        (runtime / 'logs/log').mkdir(parents=True)
        for name in ('players', 'critical'):
            (runtime / 'journals' / name).mkdir(parents=True, mode=0o700)
        plain, tls, websocket = journey.available_ports()
        environment.update(PLAYER_SAVE_JOURNAL_DIR=str(runtime / 'journals/players'),
                           CRITICAL_COMMAND_JOURNAL_DIR=str(runtime / 'journals/critical'),
                           DURIS_TLS_PORT=str(tls), DURIS_WEBSOCKET_PORT=str(websocket))
        output_path = runtime / 'server.out'
        with output_path.open('w') as output:
            process = subprocess.Popen(
                [str(server), '--minimal', '-s', '-d', str(runtime), str(plain)], cwd=runtime,
                env=environment, stdout=output, stderr=subprocess.STDOUT)
            client = None
            lock = None
            try:
                deadline = time.monotonic() + 120
                while b'Entering game loop.' not in output_path.read_bytes():
                    assert process.poll() is None and time.monotonic() < deadline, 'boot failed'
                    time.sleep(0.1)
                client = journey.MudClient(plain)
                journey.create_character(client)
                client.send('save')
                client.expect('Save complete for ' + journey.CHARACTER + '.', timeout=30)
                pid = int(sql("SELECT pid FROM player_data WHERE name='" + journey.CHARACTER +
                              "'"))
                held = sql(f'SELECT COUNT(*) FROM player_items WHERE pid={pid}')
                # `save` leaves a command lag; let it pass so quit runs when it is sent.
                client.send('look')
                client.expect('Obvious exits', timeout=20)
                client.expect('Pos: standing >', timeout=10)

                # The writer stalls on a locked table; quit still leaves at once.
                lock = subprocess.Popen(mysql + ['--unbuffered', database], stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, text=True, env=environment,
                                        bufsize=1)
                lock.stdin.write("LOCK TABLES player_items WRITE; SELECT 'held';\n")
                lock.stdin.flush()
                assert lock.stdout.readline().strip() == 'held'
                # Quitting here is camping, which has its own delay. The old terminal
                # save timed out on the stalled writer and cancelled the camp; now the
                # character reaches the menu while the table is still locked.
                started = time.monotonic()
                client.send('quit')
                _, camped = client.expect_any(('ACCOUNT MENU',), timeout=60)
                quit_elapsed = time.monotonic() - started
                assert 'could not be saved' not in camped, camped
                client.send('0')
                client.close()
                client = None
                lock.stdin.write('UNLOCK TABLES;\n')
                lock.stdin.close()
                assert lock.wait(timeout=15) == 0
                lock = None
                # The queued save lands, and a relog reads it.
                client = journey.reconnect_character(plain)
                client.send('inventory')
                client.expect('Pos: standing >', timeout=15)
                assert sql(f'SELECT COUNT(*) FROM player_items WHERE pid={pid}') == held
                print(f'camp on a stalled writer: menu after {quit_elapsed:.1f}s with the table locked; relog '
                      'read the save', flush=True)

                # With the database stopped, shutdown still exits within its bound.
                subprocess.run(['docker', 'stop', '-t', '0', os.environ['TEST_DB_CONTAINER']],
                               check=True, capture_output=True)
                client.send('drop all')
                client.expect('Pos: standing >', timeout=15)
                started = time.monotonic()
                process.send_signal(signal.SIGTERM)
                process.wait(timeout=90)
                shutdown_elapsed = time.monotonic() - started
                assert shutdown_elapsed < 60, f'shutdown took {shutdown_elapsed:.1f}s'
                logs = journey.runtime_logs(runtime) + output_path.read_text(errors='replace')
                assert 'not_written' in logs, 'shutdown did not name the unwritten save'
                print(f'shutdown with the database down: exited in {shutdown_elapsed:.1f}s and '
                      'named the unwritten save', flush=True)
            except Exception:
                print(output_path.read_text(errors='replace')[-6000:])
                print(journey.runtime_logs(runtime)[-6000:])
                raise
            finally:
                if client:
                    client.close()
                if lock and lock.poll() is None:
                    lock.kill()
                if process.poll() is None:
                    process.kill()
                    process.wait()
    print('stalled writer journey passed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server', type=Path, default=ROOT / 'bin/server/dms_new')
    run(parser.parse_args().server.resolve(strict=True))
