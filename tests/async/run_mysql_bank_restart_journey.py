#!/usr/bin/env python3
"""A first ATM deposit creates a bank and its baseline, then survives a restart.

The schema starts at migration head 0034 with a bank an older server created without an
opening baseline; the upgrade's migration run (0035) gives it one, so the server boots.
Run through with_disposable_mariadb.sh with the MariaDB server binary as the
argument. Uses a fresh schema, account and runtime; never reads checkout .env.
"""
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import time
import uuid

import test_flatfile_combat_journey as journey

ROOT = Path(__file__).resolve().parents[2]


def run(server):
    host = os.environ['TEST_DB_HOST']
    assert host == '127.0.0.1', 'use a disposable loopback database'
    database = 'bank_restart_' + uuid.uuid4().hex[:12]
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
    try:
        sql((ROOT / 'migrations/bootstrap_multithread_safe.sql').read_text())

        def migrate(*args):
            result = subprocess.run(['python3', 'scripts/migration_runner.py', *args],
                                    cwd=ROOT, env=environment, capture_output=True, text=True)
            assert result.returncode == 0, result.stdout + result.stderr

        (ROOT / 'bin/tests').mkdir(parents=True, exist_ok=True)
        # The database an older server ran: at head 0034, with a bank its first delta
        # created and no opening baseline for it.
        manifest = json.loads((ROOT / 'migrations/migration_manifest.json').read_text())
        manifest['migrations'] = [step for step in manifest['migrations']
                                  if step['sequence'] <= 34]
        with tempfile.TemporaryDirectory(prefix='mysql-bank-older-',
                                         dir=ROOT / 'bin/tests') as older:
            (Path(older) / 'immutable').symlink_to(ROOT / 'migrations/immutable')
            older_manifest = Path(older) / 'migration_manifest.json'
            older_manifest.write_text(json.dumps(manifest))
            migrate('--manifest', str(older_manifest), 'adopt', '--kind', 'fresh_bootstrap')
            migrate('--manifest', str(older_manifest), 'run')
        sql("INSERT INTO accounts(account_name) VALUES('olderbank');"
            "INSERT INTO account_banks(account_name,racewar,bank_platinum,bank_revision) "
            "VALUES('olderbank',1,9,3);")
        migrate('run')
        assert sql('SELECT opening_platinum,opening_revision FROM currency_bank_baseline '
                   'JOIN account_banks bank ON bank.id=bank_id '
                   "WHERE bank.account_name='olderbank'").split() == ['9', '3'], \
            "the migration run did not give the older server's bank its baseline"
        print('[PASS] migration 0035 gave the older bank its opening baseline', flush=True)
        with tempfile.TemporaryDirectory(prefix='mysql-bank-restart-',
                                         dir=ROOT / 'bin/tests') as temporary:
            runtime = Path(temporary)
            journey.make_fixture(runtime)
            # The existing arena supplies login and starter items. Replace its combat
            # resets with an ATM and seven platinum, with no NPC to take the coins.
            objects_path = runtime / 'areas_mini/mini.obj'
            objects = objects_path.read_text()
            start, end = objects.index('#3\n'), objects.index('#4\n')
            coins = objects[start:end]
            assert '0 0 0 0 0 0 0 0' in coins
            objects = objects[:start] + coins.replace(
                '0 0 0 0 0 0 0 0', '0 0 0 7 0 0 0 0') + objects[end:]
            counter = ('#3097\ncounter atm~\na bank counter~\nA bank counter stands here.~\n~\n'
                       '13 0 0 0 0 0 0 0 0 0 0\n0 0 0 0 0 0 0 0\n0 0 100\n')
            assert objects.count('$~') == 1
            objects_path.write_text(objects.replace('$~', counter + '$~'))
            (runtime / 'areas_mini/mini.zon').write_text(
                '#1\nBank deposit journey~\nbank deposit journey~\n29999 0 0 6 11 1\n'
                'O 0 3097 1 22800 100 0 0 0 * ATM\n'
                'O 0 3 1 22800 100 0 0 0 * seven platinum\nS\n$~\n')
            journey.generate_certificate(runtime)
            (runtime / 'logs/log').mkdir(parents=True)
            (runtime / 'journals/critical').mkdir(parents=True, mode=0o700)
            plain, tls, websocket = journey.available_ports()
            environment.update(CRITICAL_COMMAND_JOURNAL_DIR=str(runtime / 'journals/critical'),
                               DURIS_TLS_PORT=str(tls), DURIS_WEBSOCKET_PORT=str(websocket))
            output_path = runtime / 'server.out'
            process = client = None
            with output_path.open('w') as output:
                def boot():
                    nonlocal process
                    offset = output_path.stat().st_size
                    process = subprocess.Popen(
                        [str(server), '--minimal', '-s', '-d', str(runtime), str(plain)],
                        cwd=runtime, env=environment, stdout=output, stderr=subprocess.STDOUT)
                    deadline = time.monotonic() + 120
                    while b'Entering game loop.' not in output_path.read_bytes()[offset:]:
                        assert process.poll() is None and time.monotonic() < deadline, \
                            'bank journey failed to boot'
                        time.sleep(.1)

                def stop():
                    process.terminate()
                    process.wait(timeout=45)
                    assert process.returncode == 0, 'bank journey did not shut down cleanly'

                def wallet():
                    return tuple(map(int, sql(
                        "SELECT copper,silver,gold,platinum FROM player_data WHERE name='" +
                        journey.CHARACTER + "'").split()))

                def bank_and_baseline():
                    return sql(
                        'SELECT bank.bank_copper,bank.bank_silver,bank.bank_gold,'
                        'bank.bank_platinum,bank.bank_revision,'
                        'opening_copper,opening_silver,opening_gold,opening_platinum,'
                        'opening_revision FROM account_banks bank '
                        'JOIN currency_bank_baseline baseline ON baseline.bank_id=bank.id '
                        "JOIN player_data player ON player.name='" + journey.CHARACTER + "' "
                        "WHERE bank.account_name='" + journey.ACCOUNT +
                        "' AND bank.racewar=player.racewar")

                def save():
                    client.send('save')
                    client.expect('Save complete for ' + journey.CHARACTER + '.', timeout=30)

                try:
                    boot()
                    client = journey.MudClient(plain)
                    journey.create_character(client)
                    save()
                    initial_wallet = wallet()
                    assert sql("SELECT COUNT(*) FROM account_banks WHERE account_name='" +
                               journey.ACCOUNT + "'") == '0', \
                        'the fixture already has a bank before its first deposit'
                    assert sql('SELECT COUNT(*) FROM currency_bank_baseline') == '1', \
                        'only the older bank has a baseline before the first deposit'
                    client.send('balance')
                    client.expect('0 platinum, 0 gold, 0 silver, 0 copper coins.')
                    client.send('drop all')
                    client.expect('You drop a steel long sword.')
                    client.send('get coins')
                    client.expect('You get')
                    save()
                    assert wallet() == initial_wallet[:3] + (initial_wallet[3] + 7,), \
                        'the fixture did not receive its seven platinum'
                    client.send('deposit 5 platinum')
                    client.expect('5 platinum, 0 gold, 0 silver, 0 copper coins.')
                    save()
                    deposited_wallet = initial_wallet[:3] + (initial_wallet[3] + 2,)
                    assert wallet() == deposited_wallet, 'the deposit did not debit the wallet'
                    deposited_bank = bank_and_baseline()
                    assert deposited_bank.split() == ['0', '0', '0', '5', '0'] * 2, \
                        'the first deposit did not create matching bank/baseline rows: ' + deposited_bank
                    print('[PASS] first live ATM deposit: bank=5 platinum, baseline=5 platinum; '
                          'wallet debited by 5', flush=True)
                    stop()
                    client.close()
                    client = None

                    # No migration, repair or SQL write between the deposit and reboot.
                    boot()
                    client = journey.reconnect_character(plain)
                    client.send('balance')
                    client.expect('5 platinum, 0 gold, 0 silver, 0 copper coins.')
                    save()
                    assert wallet() == deposited_wallet, 'restart changed the saved wallet'
                    assert bank_and_baseline() == deposited_bank, \
                        'restart changed the bank or its opening baseline'
                    stop()
                    assert bank_and_baseline() == deposited_bank
                    assert wallet() == deposited_wallet
                    print('[PASS] clean restart and real login: bank, wallet and opening '
                          'baseline preserved; subsequent save and shutdown preserve them', flush=True)
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
        sql('DROP DATABASE ' + database, False)


if __name__ == '__main__':
    run(Path(sys.argv[1]).resolve(strict=True))
