#!/usr/bin/env python3
"""Staff poofs through real commands, movement, saves and reloads on disposable MariaDB.

Run with with_disposable_mariadb.sh; never reads .env or touches a shared game.
"""
import argparse
from pathlib import Path
import signal
import subprocess
import tempfile
import time

import test_flatfile_combat_journey as journey
from test_flight_network_journey import authority, command

ROOT = journey.ROOT
STAFF, STAFF_ACCOUNT = 'Poofwarden', 'Poofstaff'
OBSERVER, OBSERVER_ACCOUNT = 'Poofwatcher', 'Poofwatch'


def run(server):
    (ROOT / 'bin/tests').mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='staff-poof-', dir=ROOT / 'bin/tests') as temporary:
        runtime = Path(temporary)
        journey.make_fixture(runtime)
        journey.generate_certificate(runtime)
        (runtime / 'help').symlink_to(ROOT / 'help', target_is_directory=True)
        (runtime / 'logs/log').mkdir(parents=True)
        (runtime / 'lib/reports').mkdir(exist_ok=True)
        critical = runtime / 'journals/critical'
        critical.mkdir(parents=True, mode=0o700)
        world = runtime / 'areas_mini/mini.wld'
        rooms = ''.join(f'#{vnum}\nPoof test room {vnum}~\nA quiet room.\n~\n1 0 0\nS\n'
                        for vnum in (22801, 22802))
        world.write_text(world.read_text().replace('$~', rooms + '$~'))
        plain, tls, websocket = journey.available_ports()
        output_path = runtime / 'server.out'
        clients = []
        process = None
        with authority('mariadb', runtime) as (env, sql), output_path.open('w') as output:
            env.update(CRITICAL_COMMAND_JOURNAL_DIR=str(critical), DURIS_TLS_PORT=str(tls),
                       DURIS_WEBSOCKET_PORT=str(websocket))

            def boot():
                nonlocal process
                offset = output_path.stat().st_size
                process = subprocess.Popen([str(server), '--minimal', '-s', '-d', str(runtime), str(plain)],
                                           cwd=runtime, env=env, stdout=output, stderr=subprocess.STDOUT)
                deadline = time.monotonic() + 120
                while b'Entering game loop.' not in output_path.read_bytes()[offset:]:
                    assert process.poll() is None and time.monotonic() < deadline, journey.runtime_logs(runtime)
                    time.sleep(.1)

            def stop():
                for client in clients:
                    client.close()
                clients.clear()
                if process is not None and process.poll() is None:
                    process.send_signal(signal.SIGTERM)
                    process.wait(timeout=60)
                    assert process.returncode == 0, journey.runtime_logs(runtime)

            def login(name=STAFF, account=STAFF_ACCOUNT):
                client = journey.reconnect_character(plain, expected_room=None, account=account, character=name)
                clients.append(client)
                client.expect('Welcome to Duris', timeout=30)
                command(client, 'toggle paging no')
                return client

            def save(client, name=STAFF):
                client.send('save')
                client.expect('Save complete for ' + name + '.', timeout=30)
                command(client, 'look')

            def relog(client):
                client.send('quit')
                client.expect('ACCOUNT MENU', timeout=30)
                client.send('0')
                client.close()
                clients.remove(client)
                return login()

            def persisted():
                return sql(f"SELECT CONCAT(HEX(poof_in), ':', HEX(poof_out)) FROM player_data WHERE name='{STAFF}'")

            def check_pair(client, incoming, outgoing):
                assert incoming in command(client, 'poofin ?')
                assert outgoing in command(client, 'poofout ?')

            try:
                boot()
                for name, account in ((STAFF, STAFF_ACCOUNT), (OBSERVER, OBSERVER_ACCOUNT)):
                    client = journey.MudClient(plain)
                    clients.append(client)
                    journey.create_character(client, account=account, character=name,
                                             email=name.lower() + '@example.invalid')
                    save(client, name)
                stop()
                sql(f"UPDATE player_data SET level=62,highest_level=62 WHERE name='{STAFF}';"
                    f"UPDATE player_data SET level=57,highest_level=57 WHERE name='{OBSERVER}';")
                boot()
                staff = login()
                observer = login(OBSERVER, OBSERVER_ACCOUNT)
                command(staff, 'vis 0')
                command(staff, 'goto 22801')
                command(staff, 'transfer ' + OBSERVER)
                command(observer, 'score')
                check_pair(staff, 'appears with an ear-splitting bang.', 'disappears in a puff of smoke.')
                command(staff, 'goto 22802')
                observer.expect(STAFF + ' disappears in a puff of smoke.')
                command(staff, 'goto 22801')
                observer.expect(STAFF + ' appears with an ear-splitting bang.')

                # Both commands use %n, prepend a name without it, and preserve colors.
                command(staff, 'poofin &+GA mist reveals %n.&n')
                command(staff, 'poofout leaves through a portal.')
                check_pair(staff, 'A mist reveals you.', 'You leaves through a portal.')
                command(staff, 'goto 22802')
                observer.expect(STAFF + ' leaves through a portal.')
                command(staff, 'goto 22801')
                observer.expect('A mist reveals ' + STAFF + '.')
                command(staff, 'poofout %n fades; %n is gone.')
                assert 'You fades; you is gone.' in command(staff, 'poofout ?')
                command(staff, 'goto 22802')
                observer.expect(STAFF + ' fades; ' + STAFF + ' is gone.')
                command(staff, 'goto 22801')
                observer.expect('A mist reveals ' + STAFF + '.')
                save(staff)
                before = persisted()
                staff = relog(staff)
                check_pair(staff, 'A mist reveals you.', 'You fades; you is gone.')
                assert persisted() == before

                # Administrative acceptance must retain the existing poofs.
                result = command(staff, 'ok ' + STAFF + ' poof regression')
                assert 'Added to file' in result, result
                assert 'poof regression' in (runtime / 'lib/reports/ok_file').read_text()
                check_pair(staff, 'A mist reveals you.', 'You fades; you is gone.')
                save(staff)
                assert persisted() == before

                for cmd, column in (('poofin', 'poof_in'), ('poofout', 'poof_out')):
                    # Stay under the socket's byte limit while exceeding 512 bytes in UTF-8.
                    accepted = 'x' * 500 + '\u00e9' * 12
                    staff.socket.sendall((cmd + ' ' + accepted + '\n').encode('utf-8'))
                    command(staff, 'score')
                    save(staff)
                    assert sql(f"SELECT CHAR_LENGTH({column}) FROM player_data WHERE name='{STAFF}'") == '512'
                    assert sql(f"SELECT HEX({column}) FROM player_data WHERE name='{STAFF}'") == accepted.encode().hex().upper()
                    for rejected in ('z' * 513, 'x' * 500 + '\u00e9' * 13):
                        staff.socket.sendall((cmd + ' ' + rejected + '\n').encode('utf-8'))
                        staff.expect('at most 512 characters')
                        assert accepted in command(staff, cmd + ' ?')
                        save(staff)
                        assert sql(f"SELECT HEX({column}) FROM player_data WHERE name='{STAFF}'") == accepted.encode().hex().upper()
                    command(staff, cmd + ' ' + 'a' * 512)
                    save(staff)
                    assert sql(f"SELECT CHAR_LENGTH({column}) FROM player_data WHERE name='{STAFF}'") == '512'
                staff = relog(staff)
                check_pair(staff, 'a' * 512, 'a' * 512)

                # Clearing survives a real save/load; visibility still hides both broadcasts.
                command(staff, 'poofin')
                command(staff, 'poofout')
                save(staff)
                assert persisted() == ':'
                staff = relog(staff)
                check_pair(staff, 'appears with an ear-splitting bang.', 'disappears in a puff of smoke.')
                score = command(staff, 'score')
                assert 'PoofIn:  None' in score and 'PoofOut: None' in score, score
                command(staff, 'goto 22801')
                command(staff, 'transfer ' + OBSERVER)
                command(observer, 'score')
                command(staff, 'goto 22802')
                observer.expect(STAFF + ' disappears in a puff of smoke.')
                command(staff, 'goto 22801')
                observer.expect(STAFF + ' appears with an ear-splitting bang.')
                command(staff, 'vis 58')
                command(observer, 'score')
                command(staff, 'goto 22802')
                command(staff, 'goto 22801')
                hidden = command(observer, 'score')
                assert STAFF not in hidden and 'ear-splitting bang' not in hidden and 'puff of smoke' not in hidden, hidden
                command(staff, 'vis 0')

                for topic in ('poofin', 'poofout', 'godpoofin', 'god, poofin'):
                    text = command(staff, 'help ' + topic)
                    assert '%n' in text and '512 characters' in text and 'preview' in text, (topic, text)
                    assert "'%s'" not in text and 'goto, teleport and transfer' not in text, (topic, text)
                print('PASS: poof commands, goto, visibility, ok, UTF-8 length limits, saves/reloads and imported help')
            finally:
                stop()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--server', type=Path, default=ROOT / 'bin/server/dms_new')
    args = parser.parse_args()
    run(args.server.resolve())
