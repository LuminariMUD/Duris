#!/usr/bin/env python3
"""WebSocket allocation refusal and subsequent persisted creation on disposable SQL."""
import argparse
from pathlib import Path
import signal
import subprocess
import tempfile
import time

import test_flatfile_combat_journey as journey
from test_character_stat_choice_journey import WebSocketClient
from test_flight_network_journey import authority

ROOT = journey.ROOT


def run(binary):
    (ROOT / 'bin/tests').mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='pid-exhaustion-', dir=ROOT / 'bin/tests') as temporary:
        runtime = Path(temporary)
        journey.make_fixture(runtime)
        journey.generate_certificate(runtime)
        (runtime / 'logs/log').mkdir(parents=True)
        critical = runtime / 'journals/critical'
        critical.mkdir(parents=True, mode=0o700)
        plain, tls, websocket = journey.available_ports()
        output_path = runtime / 'server.out'
        process, client = None, None
        with authority('mariadb', runtime) as (env, sql), output_path.open('w') as output:
            env.update(CRITICAL_COMMAND_JOURNAL_DIR=str(critical), DURIS_TLS_PORT=str(tls),
                       DURIS_WEBSOCKET_PORT=str(websocket), DURIS_WEBSOCKET='TRUE')

            def boot():
                nonlocal process
                offset = output_path.stat().st_size
                process = subprocess.Popen([str(binary), '--minimal', '-d', str(runtime), str(plain)],
                                           cwd=runtime, env=env, stdout=output, stderr=subprocess.STDOUT)
                deadline = time.monotonic() + 120
                while b'Entering game loop.' not in output_path.read_bytes()[offset:]:
                    assert process.poll() is None and time.monotonic() < deadline, 'boot failed'
                    time.sleep(.1)

            def stop():
                nonlocal client
                if client:
                    client.close()
                    client = None
                process.send_signal(signal.SIGTERM)
                process.wait(timeout=60)
                assert process.returncode == 0

            def prepare():
                options = client.command('chargen_options')
                race = next(row for row in options['races'] if row['id'] == 1)
                warrior = next(row for row in race['classes'] if row['name'].lower() == 'warrior')
                homes = client.command('get_hometowns', {'race': 1}, 'hometowns')
                home = next(row for row in homes['options'] if 'Plane' in row['name'])
                client.command('roll_stats', {'race': 1, 'method': 'default'})
                for stat in ('str', 'dex', 'agi', 'luk'):
                    client.command('add_bonus', {'stat': stat}, 'bonus_added')
                return {'name': 'Pidwalker', 'race': 1, 'class': warrior['id'], 'sex': 1,
                        'alignment': 'good', 'hometown': home['id'], 'newbie': True}

            credentials = {'account': 'Pidaccount', 'password': journey.PASSWORD}
            try:
                sql('ALTER TABLE player_data AUTO_INCREMENT=2147483648')
                boot()
                client = WebSocketClient(websocket)
                auth = client.command('register', {**credentials, 'email': 'pid@example.invalid'}, 'auth')
                assert auth['status'] == 'success', auth
                for _ in range(2):
                    denied = client.command('create_character', prepare(), 'error')
                    assert 'Character creation is unavailable' in str(denied), denied
                    assert not any(message.get('status') == 'created' for message in client.messages)
                    assert sql('SELECT COUNT(*) FROM player_data') == '0'
                    assert sql('SELECT COUNT(*) FROM account_characters') == '0'
                    assert sql('SELECT COUNT(*) FROM player_items') == '0'
                stop()
                # Only this disposable fixture's unused allocator is lowered.
                sql('ALTER TABLE player_data AUTO_INCREMENT=100')
                boot()
                client = WebSocketClient(websocket)
                assert client.command('login', credentials, 'auth')['status'] == 'success'
                created = client.command('create_character', prepare())
                assert created['status'] == 'created', created
                deadline = time.monotonic() + 30
                while sql("SELECT COUNT(*) FROM player_data WHERE name='Pidwalker' AND pid=100") != '1':
                    assert time.monotonic() < deadline, 'created identity did not persist'
                    time.sleep(.1)
                assert sql("SELECT pid FROM account_characters WHERE char_name='Pidwalker'") == '100'
                stop()
                boot()
                client = WebSocketClient(websocket)
                assert client.command('login', credentials, 'auth')['status'] == 'success'
                client.command('enter', {'character': 'Pidwalker'}, 'gmcp')
                assert sql("SELECT pid FROM player_data WHERE name='Pidwalker'") == '100'
                stop()
                print('PASS: exhausted WebSocket creation refuses twice without mappings/items; '
                      'valid creation persists and enters after restart', flush=True)
            except Exception:
                print(output_path.read_text(errors='replace')[-5000:])
                raise
            finally:
                if client:
                    client.close()
                if process and process.poll() is None:
                    process.send_signal(signal.SIGTERM)
                    process.wait(timeout=60)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server', type=Path, default=ROOT / 'bin/server/dms_new')
    run(parser.parse_args().server.resolve())
