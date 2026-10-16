#!/usr/bin/env python3
"""Real news acknowledgement, reload, reconnect, copyover and restart.

Use --backend flatfile or a disposable TEST_DB_* server for --backend mariadb.
The supplied binary is copied into a private full-world fixture. No checkout
environment, live server, or real player/account data is used.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time

import test_flatfile_combat_journey as journey
from test_flight_network_journey import authority, command
from run_world_quest_dual_backend import setup_run_root

ROOT = journey.ROOT
PLAYER, ACCOUNT = 'Newsreader', 'Newsplayer'
GOD, GOD_ACCOUNT = 'Newswarden', 'Newsstaff'


def run(binary, backend):
    build = ROOT / 'bin/analysis/news'
    build.mkdir(parents=True, exist_ok=True)
    inspector = build / 'news-inspector'
    if backend == 'flatfile':
        subprocess.run(['python3', 'tests/async/test_flatfile_player_repository.py',
                        '--build-inspector', str(inspector)], cwd=ROOT, check=True)
    with tempfile.TemporaryDirectory(prefix='news-' + backend + '-', dir=ROOT / 'bin/tests') as temporary:
        runtime = Path(temporary)
        _, critical, output_path = setup_run_root(runtime)
        (runtime / 'help').symlink_to(ROOT / 'help', target_is_directory=True)
        (runtime / 'bin/server').mkdir(parents=True)
        executable = runtime / 'bin/server/dms'
        shutil.copy2(binary, executable)
        with (runtime / 'lib/misc/event_names').open('w') as names:
            subprocess.run([str(ROOT / 'scripts/event_names.sh'), str(executable)], stdout=names, check=True)
        news_file = runtime / 'lib/information/news'
        news_file.write_text('NEWS-A\n')

        properties = runtime / 'lib/duris.properties'
        properties.write_text(properties.read_text().replace('camp.timer=9.000', 'camp.timer=1.000'))
        plain, tls, websocket = journey.available_ports()
        process = None
        clients = []
        evidence = {'backend': backend, 'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest()}
        with authority(backend, runtime) as (env, sql), output_path.open('w') as output:
            env.update(CRITICAL_COMMAND_JOURNAL_DIR=str(critical), DURIS_TLS_PORT=str(tls),
                       DURIS_WEBSOCKET_PORT=str(websocket),
                       MAINTENANCE_STATE_FILE=str(runtime / 'maintenance.state'))

            def boot():
                nonlocal process
                offset = output_path.stat().st_size
                process = subprocess.Popen([str(executable), '-d', str(runtime), str(plain)],
                                           cwd=runtime, env=env, stdout=output, stderr=subprocess.STDOUT)
                deadline = time.monotonic() + 180
                while b'Entering game loop.' not in output_path.read_bytes()[offset:]:
                    assert process.poll() is None and time.monotonic() < deadline, 'news world failed to boot'
                    time.sleep(.1)

            def stop():
                for client in clients:
                    client.close()
                clients.clear()
                process.send_signal(signal.SIGTERM)
                process.wait(timeout=60)
                assert process.returncode == 0

            def login(name=PLAYER, account=ACCOUNT):
                client = journey.reconnect_character(plain, expected_room=None, account=account, character=name)
                clients.append(client)
                client.expect('Welcome to Duris', timeout=60)
                command(client, 'toggle paging no')
                return client

            def prompt(client):
                client.send('score')
                client.expect('Score information for', timeout=30)
                return client.expect('> ', timeout=30)

            def read_news(client, version):
                command(client, 'toggle paging yes')
                client.send('news')
                client.expect('NEWS-' + version, timeout=30)
                client.expect('> ', timeout=30)
                command(client, 'toggle paging no')
                assert '(news)' not in prompt(client), 'news was still unread after display'

            def save(client, name=PLAYER):
                client.send('save')
                client.expect('Save complete for ' + name + '.', timeout=60)

            def stored():
                if sql:
                    return sql("SELECT last_read_news_hash FROM player_data WHERE name='" + PLAYER + "'")
                state = json.loads(subprocess.check_output([str(inspector), env['FLATFILE_STATE_DIR'],
                                                           'inspect', '1'], text=True))
                return state['last_read_news_hash']

            def publish(version):
                text = 'NEWS-' + version + '\n'
                if sql:
                    sql("UPDATE mud_info SET content=CONVERT(0x" + text.encode().hex() + " USING utf8mb4) WHERE name='news'")
                else:
                    news_file.write_text(text)

            try:
                boot()
                for name, account in ((PLAYER, ACCOUNT), (GOD, GOD_ACCOUNT)):
                    client = journey.MudClient(plain)
                    clients.append(client)
                    journey.create_character(client, expected_room=None, account=account,
                                             character=name, email=name.lower() + '@example.invalid')
                    command(client, 'toggle paging no')
                    assert '(news)' in prompt(client), 'login notice acknowledged news'
                    save(client, name)
                player, god = clients
                read_news(player, 'A')
                assert '(news)' in prompt(god), 'another character acknowledged this news'
                save(player)
                assert stored() == hashlib.sha256(b'NEWS-A\n').hexdigest()
                stop()
                if sql:
                    sql("UPDATE player_data SET level=62,highest_level=62 WHERE name='" + GOD + "'")
                    # Distinct neighbors expose shifted SQL domain columns on every reload.
                    sql("UPDATE player_data SET spells_memmed_extra=31,copper=101,silver=202,"
                        "gold=303,platinum=404,exp=12345,epics=505,"
                        "time_unspecced=FROM_UNIXTIME(1000000),frags=606,oldfrags=707 "
                        "WHERE name='" + PLAYER + "'")
                else:
                    journey.make_overlord(Path(env['FLATFILE_STATE_DIR']), GOD)
                boot()
                player, god = login(), login(GOD, GOD_ACCOUNT)
                assert '(news)' not in prompt(player) and '(news)' in prompt(god)
                player.send('quit')
                player.expect('ACCOUNT MENU', timeout=60)
                player.close()
                clients.remove(player)
                player = login()
                assert '(news)' not in prompt(player)
                process.send_signal(signal.SIGUSR1)
                player.expect('Copyover complete!', timeout=180)
                assert '(news)' not in prompt(player)
                evidence['restart_reconnect_copyover'] = 'passed'
                if sql:
                    sql("UPDATE mud_info SET content=CONVERT(0x4e4557532d5800626164 USING utf8mb4) WHERE name='news'")
                else:
                    news_file.write_bytes(b'NEWS-X\0bad')
                god.send('page')
                refused = god.expect('News reload failed; previous news retained.', timeout=30)
                refused += god.expect('> ', timeout=30)
                assert 'Done.' not in refused, 'failed publication reported success'
                read_news(player, 'A')
                evidence['failed_reload_retains_news'] = 'passed'
                publish('B')
                god.send('page')
                god.expect('Done.', timeout=30)
                assert '(news)' in prompt(player)
                read_news(player, 'B')
                god.send('page')
                god.expect('Done.', timeout=30)
                assert '(news)' not in prompt(player), 'unchanged reload marked news unread'
                if sql:
                    publish('C')
                    deadline = time.monotonic() + 90
                    while '(news)' not in prompt(player):
                        assert time.monotonic() < deadline, 'periodic SQL refresh did not publish news'
                        time.sleep(1)
                    read_news(player, 'C')
                    evidence['periodic_sql_refresh'] = 'passed'
                save(player)
                final = 'C' if sql else 'B'
                assert stored() == hashlib.sha256(('NEWS-' + final + '\n').encode()).hexdigest()
                if sql:
                    assert sql("SELECT copper,silver,gold,platinum,epics,frags,oldfrags "
                               "FROM player_data WHERE name='" + PLAYER + "'").strip() == '101\t202\t303\t404\t505\t606\t707'
                    evidence['domain_balances_after_load_save'] = 'passed'
                stop()
                boot()
                player = login()
                assert '(news)' not in prompt(player)
                evidence['updated_acknowledgement_restart'] = 'passed'
                evidence['status'] = 'passed'
                print(backend + ': unread/read, independent characters, reload, reconnect, copyover and restart passed', flush=True)
            finally:
                for client in clients:
                    client.close()
                if process and process.poll() is None:
                    process.send_signal(signal.SIGTERM)
                    process.wait(timeout=60)
                shutil.copy2(output_path, build / ('journey-' + backend + '.log'))
                (build / ('journey-' + backend + '.json')).write_text(json.dumps(evidence, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--backend', choices=('mariadb', 'flatfile'), required=True)
    parser.add_argument('--server', type=Path, required=True)
    args = parser.parse_args()
    run(args.server.resolve(), args.backend)
