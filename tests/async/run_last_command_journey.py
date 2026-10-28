#!/usr/bin/env python3
"""Run last through real staff/mortal sockets on an isolated migrated MariaDB game."""
import argparse
from pathlib import Path
import signal
import subprocess
import tempfile
import time

import test_flatfile_combat_journey as journey
from test_flight_network_journey import authority

ROOT = journey.ROOT


def run(binary):
    with tempfile.TemporaryDirectory(prefix='last-journey-', dir=ROOT / 'bin/tests') as temporary:
        runtime = Path(temporary)
        journey.make_fixture(runtime)
        journey.generate_certificate(runtime)
        (runtime / 'logs/log').mkdir(parents=True)
        critical = runtime / 'journals/critical'
        critical.mkdir(parents=True, mode=0o700)
        properties = runtime / 'lib/duris.properties'
        properties.write_text(properties.read_text().replace('camp.timer=2.000', 'camp.timer=1.000'))
        plain, tls, websocket = journey.available_ports()
        process = None
        clients = []
        output_path = runtime / 'server.out'
        with authority('mariadb', runtime) as (env, sql), output_path.open('w') as output:
            env.update(CRITICAL_COMMAND_JOURNAL_DIR=str(critical), DURIS_TLS_PORT=str(tls),
                       DURIS_WEBSOCKET_PORT=str(websocket))

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
                for client in clients:
                    client.close()
                clients.clear()
                process.send_signal(signal.SIGTERM)
                process.wait(timeout=60)
                assert process.returncode == 0

            def response(client, text, end):
                client.send(text)
                return client.expect(end, timeout=30)

            try:
                boot()
                for name, account in (('Lastwarden', 'Laststaff'), ('Lastplayer', 'Lastmortal')):
                    client = journey.MudClient(plain)
                    clients.append(client)
                    journey.create_character(client, account=account, character=name,
                                             email=name.lower() + '@example.invalid')
                    response(client, 'save', 'Save complete for ' + name + '.')
                    response(client, 'look', 'Obvious exits')
                    response(client, 'quit', 'Please select an option')
                stop()
                sql("UPDATE player_data SET level=57,highest_level=57 WHERE name='Lastwarden'")
                boot()
                god = journey.reconnect_character(plain, account='Laststaff', character='Lastwarden')
                player = journey.reconnect_character(plain, account='Lastmortal', character='Lastplayer')
                clients.extend((god, player))
                for client in clients:
                    response(client, 'toggle paging no', 'Paging mode off')
                denied = response(player, 'last', 'Pardon?')
                assert 'Login history' not in denied
                # Persist a second login, then query the now-offline character by current name.
                response(player, 'quit', 'Please select an option')
                deadline = time.monotonic() + 30
                while int(sql("SELECT COUNT(*) FROM session_audit_outcome s JOIN player_data p "
                              "ON p.pid=s.pid WHERE p.name='Lastplayer' AND s.event_type=1")) < 2:
                    assert time.monotonic() < deadline, 'login audit did not persist'
                    time.sleep(.1)
                for command in ('last', 'last 24h', 'last 7d', 'last Lastplayer 7d'):
                    text = response(god, command, 'End of login history.')
                    assert 'Login history' in text and 'Times are UTC' in text
                    assert text.count('| Lastplayer') == 2, text
                    assert 'lastmortal' in text
                unique = response(god, 'last unique 7d', 'End of login history.')
                assert unique.count('| Lastplayer') == 1 and unique.count('| Lastwarden') == 1, unique
                second = response(god, 'last 24h page 2', 'End of login history.')
                assert 'No logins on this page.' in second
                assert 'Previous: last 24h page 1' in second
                response(god, 'last 0h', 'Examples:')
                response(god, 'last Missingperson', 'No such character.')
                help_text = response(god, 'help last', 'See also:')
                assert 'Syntax: last' in help_text and 'Avatar command' in help_text, help_text
                stop()
                assert 'game loop query site cmd/last.c' not in journey.runtime_logs(runtime)
                print('PASS: real mortal denial, Avatar dispatch, persisted repeated logins, '
                      'offline lookup, time filters, unique accounts, paging and imported help', flush=True)
            except Exception:
                print(output_path.read_text(errors='replace')[-7000:])
                for client in clients:
                    print(bytes(client.transcript[-4000:]).decode(errors='replace'))
                raise
            finally:
                for client in clients:
                    client.close()
                if process and process.poll() is None:
                    process.send_signal(signal.SIGTERM)
                    process.wait(timeout=60)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--server', type=Path, default=ROOT / 'bin/server/dms_new')
    run(parser.parse_args().server.resolve())
