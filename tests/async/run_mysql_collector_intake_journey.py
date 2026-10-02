#!/usr/bin/env python3
"""The collector takes an antiquity from a player's corpse, on an isolated MariaDB schema.

The MariaDB side of test_flatfile_collector_intake_journey.py: the death's corpse save
records the death and its candidates, and maintenance collects the banana from the live
corpse. Set TEST_DB_HOST (loopback), TEST_DB_USER and TEST_DB_PASSWORD; TEST_DB_PORT
defaults to 3306.
"""
from pathlib import Path
import os
import signal
import subprocess
import sys
import tempfile
import time
import uuid

import test_flatfile_collector_intake_journey as collector_journey
import test_flatfile_combat_journey as journey

ROOT = Path(__file__).resolve().parents[2]


def run(server):
    database = 'collector_journey_test_' + uuid.uuid4().hex[:12]
    host = os.environ['TEST_DB_HOST']
    port = os.environ.get('TEST_DB_PORT', '3306')
    assert host in ('127.0.0.1', 'localhost'), 'use a disposable loopback database'
    environment = {
        'PATH': os.environ.get('PATH', '/usr/bin:/bin'),
        'ENVIRONMENT': 'local', 'DB_HOST': host, 'DB_PORT': port,
        'DB_NAME': database, 'DB_USER': os.environ['TEST_DB_USER'],
        'DB_PASSWD': os.environ['TEST_DB_PASSWORD'],
        'DB_ALLOWED_TARGETS': host + '/' + database,
        'MYSQL_PWD': os.environ['TEST_DB_PASSWORD'],
        'PERSISTENCE_MODE': 'mariadb-primary', 'DB_TLS': 'FALSE',
        'REDIS': 'FALSE', 'CHAOS_MUD': 'FALSE',
        'LISTEN_ADDRESS': '127.0.0.1', 'DURIS_WEBSOCKET_LISTEN_ADDRESS': '127.0.0.1',
    }
    if 'LD_LIBRARY_PATH' in os.environ:
        environment['LD_LIBRARY_PATH'] = os.environ['LD_LIBRARY_PATH']
    mysql = ['mysql', '--protocol=tcp', '-h', host, '-P', port,
             '-u', environment['DB_USER'], '-N', '-B']

    def sql(text, selected=True):
        return subprocess.check_output(mysql + ([database] if selected else []), input=text,
                                       text=True, env=environment).strip()

    sql('CREATE DATABASE ' + database + ' CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci',
        False)
    try:
        sql((ROOT / 'migrations/bootstrap_multithread_safe.sql').read_text())
        subprocess.run(['python3', 'scripts/migration_runner.py', 'adopt', '--kind',
                        'fresh_bootstrap'], cwd=ROOT, env=environment, check=True)
        subprocess.run(['python3', 'scripts/migration_runner.py', 'run'], cwd=ROOT,
                       env=environment, check=True)
        with tempfile.TemporaryDirectory(prefix='mysql-collector-',
                                         dir=ROOT / 'bin/tests') as temporary:
            runtime = Path(temporary)
            journey.make_fixture(runtime)
            collector_journey.enable_collector(runtime)
            journey.generate_certificate(runtime)
            (runtime / 'logs/log').mkdir(parents=True)
            (runtime / 'journals/critical').mkdir(parents=True, mode=0o700)
            plain, tls, websocket = journey.available_ports()
            environment.update(CRITICAL_COMMAND_JOURNAL_DIR=str(runtime / 'journals/critical'),
                               DURIS_TLS_PORT=str(tls), DURIS_WEBSOCKET_PORT=str(websocket))
            output_path = runtime / 'server.out'
            with output_path.open('w') as output:
                process = subprocess.Popen(
                    [str(server), '--minimal', '-s', '-d', str(runtime), str(plain)],
                    cwd=runtime, env=environment, stdout=output, stderr=subprocess.STDOUT)
                try:
                    deadline = time.monotonic() + 120
                    while b'Entering game loop.' not in output_path.read_bytes():
                        assert process.poll() is None and time.monotonic() < deadline, \
                            'MariaDB collector fixture failed to boot'
                        time.sleep(.1)
                    client = journey.MudClient(plain)
                    journey.create_character(client)
                    client.send('toggle boon')
                    client.expect('You will no longer be affected by boons.')
                    journey.complete_npc_combat_journey(client)
                    client.close()
                    journey.verify_npc_loot_and_die(plain)
                    collector_journey.wait_for_collection(plain)
                    pid = sql("SELECT pid FROM player_data WHERE name='" + journey.CHARACTER + "'")
                    assert sql('SELECT COUNT(*) FROM collector_deaths WHERE beneficiary_pid=' +
                               pid) == '1', 'the death was not recorded'
                    # The banana left the corpse for the collector; its listing moved on.
                    banana = sql('SELECT status FROM collector_listings l JOIN item_current_owner o '
                                 'ON o.item_uid=l.item_uid WHERE l.beneficiary_pid=' + pid +
                                 ' AND o.vnum=15')
                    assert banana in ('2', '3'), 'the banana was not collected: ' + banana
                    process.send_signal(signal.SIGTERM)
                    process.wait(timeout=30)
                    assert process.returncode == 0
                    print('MariaDB collector intake journey passed', flush=True)
                except Exception as error:
                    raise AssertionError(str(error) + '\n' +
                                         output_path.read_text(errors='replace')[-10000:] +
                                         '\n' + journey.runtime_logs(runtime)) from error
                finally:
                    if process.poll() is None:
                        process.kill()
                        process.wait(timeout=10)
    finally:
        sql('DROP DATABASE ' + database, False)


if __name__ == '__main__':
    run(Path(sys.argv[1]).resolve(strict=True))
