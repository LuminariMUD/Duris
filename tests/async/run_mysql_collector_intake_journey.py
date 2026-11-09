#!/usr/bin/env python3
"""Collector corpse intake and atomic buyback across disconnect/restart on disposable SQL.

The MariaDB side of test_flatfile_collector_intake_journey.py: the death's corpse save
records the death and its candidates, then buys the exact collected UID back through the
real service and restarts. Set TEST_DB_HOST (loopback), TEST_DB_USER and TEST_DB_PASSWORD; TEST_DB_PORT
defaults to 3306.
"""
from pathlib import Path
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
import uuid

import test_flatfile_collector_intake_journey as collector_journey
import test_flatfile_combat_journey as journey
from run_item_pilot_journey import object_records

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
            # Add a real collector prototype and one registered service room to
            # the miniature world, preserving the ordinary command/service path.
            mobiles_path = runtime / 'areas_mini/mini.mob'
            mobiles = object_records(mobiles_path.read_text())
            collector = re.search(r'(?ms)^#1257\n.*?(?=^#|\Z)',
                                  (ROOT / 'areas/mob/heavens.mob').read_text())
            assert collector
            mobiles[1257] = collector.group()
            mobiles_path.write_text(''.join(mobiles[v] for v in sorted(mobiles)) + '$~\n')
            rooms_path = runtime / 'areas_mini/mini.wld'
            rooms = object_records(rooms_path.read_text())
            rooms[22800] = rooms[22800].replace('\nS\n', '\nD0\n~\n~\n0 0 16885\nS\n')
            rooms[16885] = ('#16885\nThe Collector Regression House~\nA quiet trading room.\n~\n'
                            '1 0 0\nD2\n~\n~\n0 0 22800\nS\n')
            rooms_path.write_text(''.join(rooms[v] for v in sorted(rooms)) + '$~\n')
            journey.generate_certificate(runtime)
            (runtime / 'logs/log').mkdir(parents=True)
            (runtime / 'journals/critical').mkdir(parents=True, mode=0o700)
            plain, tls, websocket = journey.available_ports()
            environment.update(CRITICAL_COMMAND_JOURNAL_DIR=str(runtime / 'journals/critical'),
                               DURIS_TLS_PORT=str(tls), DURIS_WEBSOCKET_PORT=str(websocket))
            output_path = runtime / 'server.out'
            with output_path.open('w') as output:
                process = None
                def boot():
                    nonlocal process
                    offset = output_path.stat().st_size
                    process = subprocess.Popen(
                        [str(server), '--minimal', '-s', '-d', str(runtime), str(plain)],
                        cwd=runtime, env=environment, stdout=output, stderr=subprocess.STDOUT)
                    deadline = time.monotonic() + 120
                    while b'Entering game loop.' not in output_path.read_bytes()[offset:]:
                        assert process.poll() is None and time.monotonic() < deadline, \
                            'MariaDB collector fixture failed to boot'
                        time.sleep(.1)
                def login():
                    connected = journey.reconnect_character(plain, expected_room=None)
                    connected.expect('Welcome to Duris', timeout=60)
                    connected.expect('Pos: standing >', timeout=20)
                    return connected
                client = None
                try:
                    boot()
                    client = journey.MudClient(plain)
                    journey.create_character(client)
                    client.send('toggle boon')
                    client.expect('Divine Boons apply automatically.')
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
                    deadline = time.monotonic() + 20
                    while banana != '3':
                        assert time.monotonic() < deadline, 'the collected banana never became available'
                        time.sleep(.1)
                        banana = sql('SELECT status FROM collector_listings l JOIN item_current_owner o '
                                     'ON o.item_uid=l.item_uid WHERE l.beneficiary_pid=' + pid + ' AND o.vnum=15')
                    listing, uid, price = map(int, sql('SELECT l.listing_id,l.item_uid,l.price_value FROM collector_listings l '
                                                     'JOIN item_current_owner o ON o.item_uid=l.item_uid '
                                                     'WHERE l.beneficiary_pid=' + pid + ' AND l.status=3 AND o.vnum=15').split())
                    process.send_signal(signal.SIGTERM)
                    process.wait(timeout=30)
                    assert process.returncode == 0
                    print('PASS real corpse collection and availability', flush=True)
                    budget = price + 123
                    # Normal denominations avoid the game's accidental loose-coin spill on movement.
                    sql(f'UPDATE player_data SET copper={budget%10},silver={(budget//10)%10},'
                        f'gold={(budget//100)%10},platinum={budget//1000},'
                        f'wallet_revision=wallet_revision+1 WHERE pid={pid}')
                    boot()
                    client = login()
                    client.send('north')
                    client.expect('The Collector Regression House', timeout=20)
                    client.expect('Pos: standing >', timeout=20)
                    client.send('score')
                    score = client.expect('Coins in bank:', timeout=20)
                    carried = re.search(r'Coins carried:\s*(\d+) platinum\s*(\d+) gold\s*(\d+) silver\s*(\d+) copper', score)
                    assert carried, score
                    live_before = sum(int(amount) * unit for amount, unit in zip(carried.groups(), (1000,100,10,1)))
                    print(f'Collector purchase: live purse before={live_before}, fixture={price+123}, price={price}', flush=True)
                    assert live_before == price + 123, 'fixture purse changed before purchase'
                    client.expect('Pos: standing >', timeout=20)
                    client.send(f'collector buy {listing}')
                    client.expect('committing your purchase', timeout=30)
                    client.close()
                    def purchased_state():
                        return sql('SELECT p.copper+10*p.silver+100*p.gold+1000*p.platinum,'
                                   f'(SELECT COUNT(*) FROM player_items WHERE pid={pid} AND obj_uid={uid}),'
                                   f'o.owner_type,o.owner_id,l.status FROM player_data p JOIN item_current_owner o '
                                   f'ON o.item_uid={uid} JOIN collector_listings l ON l.listing_id={listing} WHERE p.pid={pid}')
                    expected = f'123\t1\t1\t{pid}\t4'
                    deadline = time.monotonic() + 30
                    while purchased_state() != expected:
                        assert time.monotonic() < deadline, 'purchase did not commit payment and exact UID: ' + purchased_state()
                        time.sleep(.05)
                    process.kill()
                    process.wait(timeout=10)
                    boot()
                    client = login()
                    client.send('save')
                    client.expect('Saving ' + journey.CHARACTER + '.', timeout=30)
                    assert purchased_state() == expected, 'cold load or repeated save lost/duplicated payment or UID'
                    client.close()
                    process.send_signal(signal.SIGTERM)
                    process.wait(timeout=30)
                    assert process.returncode == 0
                    assert purchased_state() == expected
                    print('PASS atomic collector buyback, disconnect, SIGKILL/restart and exact purse/UID/ownership', flush=True)
                except Exception as error:
                    (ROOT / 'bin/tests/collector-intake-failure.log').write_text(
                        output_path.read_text(errors='replace') + '\n' + journey.runtime_logs(runtime) +
                        '\n' + (bytes(client.transcript).decode(errors='replace') if client else ''))
                    raise AssertionError(str(error) + '\n' +
                                         output_path.read_text(errors='replace')[-10000:] +
                                         '\n' + journey.runtime_logs(runtime)) from error
                finally:
                    if client:
                        client.close()
                    if process and process.poll() is None:
                        process.kill()
                        process.wait(timeout=10)
    finally:
        sql('DROP DATABASE ' + database, False)


if __name__ == '__main__':
    run(Path(sys.argv[1]).resolve(strict=True))
