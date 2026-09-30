#!/usr/bin/env python3
"""The game loop never waits on a query after boot (persistence reset phase 2, step 8).

A real server on a disposable MariaDB, in the combat journey's fixture world: a new
account and character are created, the character plays, saves and quits, the account
menu lists its characters, and the character enters the game again and quits. Every
query the game thread issues while the loop runs logs its site once (`game loop query
site <file>:<line> <function> (<kind>)`). No site may appear except the functions
NOT_CONVERTED still lists: the rest of step 8 empties it. Run it through
with_disposable_mariadb.sh (make test-db); --server picks the executable.
"""
from pathlib import Path
import argparse
import os
import re
import signal
import subprocess
import tempfile
import time
import uuid

import test_flatfile_combat_journey as journey

ROOT = Path(__file__).resolve().parents[2]

# The functions this session still reaches with a query on the game loop.
NOT_CONVERTED = {
    # login-time reads
    'query_grants', 'check_frag_position', 'player_death_restitution_locker_notice',
    # periodic artifact events
    'event_artifact_check_poof_sql', 'event_artifact_wars_sql',
    'event_artifact_check_bind_sql',
    # character creation: the name check, the first save and its pid
    'sql_player_exists', 'sql_try_get_player_pid', 'sql_begin_transaction', 'sql_commit',
    'sql_rollback', 'sql_run_query', 'sql_run_multi_query',
}


def run(server):
    database = 'loop_queries_' + uuid.uuid4().hex[:12]
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
    subprocess.run(mysql, input='CREATE DATABASE ' + database +
                   ' CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci', text=True,
                   env=environment, check=True)
    subprocess.run(mysql + [database],
                   input=(ROOT / 'migrations/bootstrap_multithread_safe.sql').read_text(),
                   text=True, env=environment, check=True)
    for args in (('adopt', '--kind', 'fresh_bootstrap'), ('run',)):
        subprocess.run(['python3', 'scripts/migration_runner.py', *args], cwd=ROOT,
                       env=environment, check=True, capture_output=True)
    with tempfile.TemporaryDirectory(prefix='loop-queries-', dir=ROOT / 'bin/tests') as tmp:
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
        output = output_path.open('w')
        process = subprocess.Popen(
            [str(server), '--minimal', '-s', '-d', str(runtime), str(plain)], cwd=runtime,
            env=environment, stdout=output, stderr=subprocess.STDOUT)
        client = None
        try:
            deadline = time.monotonic() + 120
            while b'Entering game loop.' not in output_path.read_bytes():
                assert process.poll() is None and time.monotonic() < deadline, 'boot failed'
                time.sleep(0.1)

            client = journey.MudClient(plain)
            journey.create_character(client)
            client.send('save')
            client.expect('Save complete for ' + journey.CHARACTER + '.', timeout=30)
            # `save` leaves a command lag; let it pass so quit runs when it is sent.
            client.send('look')
            client.expect('Obvious exits', timeout=20)
            client.expect('Pos: standing >', timeout=10)
            client.send('quit')
            client.expect('Please select an option', timeout=60)
            # The account menu's lists come from the account in memory.
            client.send('8')
            client.expect('RESTED BONUS STATUS', timeout=15)
            client.expect('Please select an option', timeout=15)
            client.send('3')
            client.expect('Which character do you want to', timeout=15)
            client.send('0')
            client.expect('Please select an option', timeout=15)
            client.send('1')
            client.expect(journey.CHARACTER, timeout=15)
            client.send('1')
            client.expect('Play as', timeout=15)
            client.send('y')
            client.expect('The Regression Arena', timeout=30)
            client.send('quit')
            client.expect('Please select an option', timeout=60)
            client.send('0')
            client.close()
            client = None
        except Exception:
            print(output_path.read_text(errors='replace')[-6000:])
            print(journey.runtime_logs(runtime)[-6000:])
            if client:
                print(client.transcript.decode(errors='replace')[-6000:])
            raise
        finally:
            if client:
                client.close()
            process.send_signal(signal.SIGTERM)
            try:
                process.wait(timeout=90)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            output.close()

        logs = output_path.read_text(errors='replace') + '\n'.join(
            path.read_text(errors='replace') for path in (runtime / 'logs/log').glob('*')
            if path.is_file())
        sites = sorted(set(re.findall(r'game loop query site (\S+) (\S+) \((\w+)\)', logs)))
        unexpected = [site for site in sites if site[1] not in NOT_CONVERTED]
        for site in sites:
            print('game loop query site', *site)
        assert not unexpected, f'the game loop still queries: {unexpected}'
    print(f'game loop queries journey passed ({len(sites)} sites still listed as not converted)')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server', type=Path, default=ROOT / 'bin/server/dms_new')
    arguments = parser.parse_args()
    if not os.getenv('TEST_DB_HOST'):
        print('game loop queries journey skipped: run it through with_disposable_mariadb.sh')
    else:
        run(arguments.server.resolve(strict=True))
