#!/usr/bin/env python3
"""The server keeps saving after MariaDB closes its idle connections.

MariaDB closes a connection idle past wait_timeout (8 hours by default). The game
thread's own connection is idle from the end of boot, and it holds the lock that keeps a
second server off the database; the pool's connections are idle whenever nothing is
saved. Here wait_timeout is 3 seconds. The server boots, a character is created and
saved, and nothing runs for longer than that. Then the server must still hold its lock,
and the character saves, quits and logs in again, and the server shuts down cleanly.
Run through with_disposable_mariadb.sh with the MariaDB server binary as the argument.
"""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import time
import uuid

import test_flatfile_combat_journey as journey

ROOT = Path(__file__).resolve().parents[2]
IDLE_TIMEOUT = 3


def run(server):
    host = os.environ['TEST_DB_HOST']
    assert host == '127.0.0.1', 'use a disposable loopback database'
    database = 'idle_timeout_' + uuid.uuid4().hex[:12]
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

    sql('CREATE DATABASE ' + database +
        ' CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci', False)
    old_timeout = sql('SELECT @@GLOBAL.wait_timeout', False)
    try:
        sql((ROOT / 'migrations/bootstrap_multithread_safe.sql').read_text())
        for args in (('adopt', '--kind', 'fresh_bootstrap'), ('run',)):
            result = subprocess.run(['python3', 'scripts/migration_runner.py', *args],
                                    cwd=ROOT, env=environment, capture_output=True, text=True)
            assert result.returncode == 0, result.stdout + result.stderr
        # Every connection the server opens from here on is closed after this much idling.
        sql(f'SET GLOBAL wait_timeout={IDLE_TIMEOUT}', False)
        (ROOT / 'bin/tests').mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='mysql-idle-timeout-',
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

            def idle():
                time.sleep(IDLE_TIMEOUT * 2 + 1)
                assert sql("SELECT IS_USED_LOCK('duris.runtime." + database + "') IS NOT NULL")\
                    == '1', 'MariaDB closed the idle connection that holds the runtime lock'

            def save():
                client.send('save')
                client.expect('Save complete for ' + journey.CHARACTER + '.', timeout=30)

            def saved_items():
                return int(sql("SELECT COUNT(*) FROM player_items items JOIN player_data player "
                               "ON player.pid=items.pid WHERE player.name='" +
                               journey.CHARACTER + "'"))

            with output_path.open('w') as output:
                try:
                    process = subprocess.Popen(
                        [str(server), '--minimal', '-s', '-d', str(runtime), str(plain)],
                        cwd=runtime, env=environment, stdout=output, stderr=subprocess.STDOUT)
                    deadline = time.monotonic() + 120
                    while b'Entering game loop.' not in output_path.read_bytes():
                        assert process.poll() is None and time.monotonic() < deadline, \
                            'idle timeout journey failed to boot'
                        time.sleep(.1)
                    client = journey.MudClient(plain)
                    journey.create_character(client)
                    save()
                    carried = saved_items()
                    idle()
                    client.send('drop all')
                    client.expect('You drop a steel long sword.')
                    save()
                    assert saved_items() < carried, \
                        'the save after the idle timeout did not reach the database'
                    print('[PASS] after the idle timeout the runtime lock holds and a save '
                          'lands', flush=True)
                    client.send('quit')
                    client.expect('ACCOUNT MENU', timeout=30)
                    client.send('0')
                    client.close()
                    client = None
                    idle()
                    client = journey.reconnect_character(plain)
                    save()
                    print('[PASS] after another idle timeout the character logs in and '
                          'saves', flush=True)
                    process.terminate()
                    process.wait(timeout=45)
                    assert process.returncode == 0, 'the server did not shut down cleanly'
                    print('[PASS] the server shuts down cleanly', flush=True)
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
                        process.terminate()
                        try:
                            process.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait(timeout=10)
    finally:
        sql(f'SET GLOBAL wait_timeout={old_timeout}', False)
        sql('DROP DATABASE ' + database, False)


if __name__ == '__main__':
    run(Path(sys.argv[1]).resolve(strict=True))
