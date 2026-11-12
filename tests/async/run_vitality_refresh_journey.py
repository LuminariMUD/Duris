#!/usr/bin/env python3
"""Qualify issue #1010's Vitality refresh rule through a disposable real server.

A level-56 player holds Vitality while staff turn spell.generousRefresh.enabled
off at runtime. Run under with_disposable_mariadb.sh with a MariaDB dms binary.
"""
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import test_mariadb_combat_journey as journey
from run_divine_refusal_journey import drain

ROOT = journey.ROOT
PLAYER = 'Vitalis'
SURGE = 'magical surge'
NOTHING = 'Nothing new seems to happen.'
PROMPT = 'Pos: standing >'
OBJECTS = ''.join(f'''#{vnum}
{keywords}~
a {keywords}~
A {keywords} lies here.~
~
{kind} 7 2 4 7 0 0 1 64 0 0
{power} 56 -1 -1 0 0 0 0
2 8742 100
''' for vnum, keywords, kind, power in (
    (22810, 'scroll lesser vitality', 2, 22),
    (22811, 'scroll greater vitality', 2, 56),
    (22812, 'potion weak vitality', 10, 22)))


def configure(runtime: Path) -> None:
    (runtime / 'logs/log').mkdir(parents=True)
    (runtime / 'journals/critical').mkdir(parents=True, mode=0o700)
    journey.make_fixture(runtime)
    journey.generate_certificate(runtime)
    shipped = (runtime / 'lib/duris.properties').read_text()
    assert shipped.count('spell.generousRefresh.enabled=1.000\n') == 1, 'shipped setting changed'
    mini = runtime / 'areas_mini'
    objects = (mini / 'mini.obj').read_text()
    (mini / 'mini.obj').write_text(objects.replace('$~', OBJECTS + '$~'))


def run(binary: Path) -> None:
    with journey.mariadb_authority() as (environment, sql), \
            tempfile.TemporaryDirectory(prefix='vitality-refresh-', dir=ROOT / 'bin/tests') as temporary:
        runtime = Path(temporary)
        configure(runtime)
        port, tls_port, websocket_port = journey.available_ports()
        environment.update(
            PATH='/usr/bin:/bin', ENVIRONMENT='local', REDIS='FALSE', CHAOS_MUD='FALSE',
            CRITICAL_COMMAND_JOURNAL_DIR=str(runtime / 'journals/critical'),
            LISTEN_ADDRESS='127.0.0.1', DURIS_TLS_PORT=str(tls_port),
            DURIS_WEBSOCKET_PORT=str(websocket_port), DURIS_WEBSOCKET_LISTEN_ADDRESS='127.0.0.1')
        server_out = runtime / 'server.out'
        process = None
        clients: list[journey.MudClient] = []

        def boot() -> None:
            nonlocal process
            process = subprocess.Popen([str(binary), '--minimal', '-s', str(port)], cwd=runtime,
                                       env=environment, stdout=server_out.open('w'),
                                       stderr=subprocess.STDOUT)
            deadline = time.monotonic() + 90
            while 'Entering game loop.' not in server_out.read_text(errors='replace'):
                assert process.poll() is None and time.monotonic() < deadline, 'boot failed'
                time.sleep(0.1)

        def stop() -> None:
            while clients:
                clients.pop().close()
            if process and process.poll() is None:
                process.terminate()
                process.wait(timeout=30)

        def connect() -> journey.MudClient:
            client = journey.reconnect_character(port, account=PLAYER, character=PLAYER,
                                                 source_host='127.0.0.2')
            clients.append(client)
            drain(client)
            return client

        def leave(client: journey.MudClient) -> None:
            client.send('save')
            client.expect('Saving ' + PLAYER + '.', timeout=30)
            client.send('quit')
            client.expect('ACCOUNT MENU', timeout=30)
            clients.remove(client)
            client.close()

        def say(client: journey.MudClient, text: str, until: str | None = PROMPT) -> str:
            # Waiting for the reply covers the lag recite and quaff leave behind.
            drain(client, 0.1)
            client.send(text)
            return (client.expect(until, timeout=20) if until else '') + drain(client, 0.5)

        def hit_points(client: journey.MudClient) -> tuple[int, int]:
            score = say(client, 'score', 'Moves:')
            found = re.search(r'Hit points: (\d+)\((\d+)\)', score)
            assert found, score
            return int(found.group(1)), int(found.group(2))

        def check_hit_points(client: journey.MudClient, before: tuple[int, int],
                             gain: int) -> tuple[int, int]:
            # Maximum moves by exactly the gain; current never drops (regeneration may add).
            after = hit_points(client)
            assert after[1] == before[1] + gain and after[0] >= before[0] + gain, (before, after)
            return after

        def vitality() -> tuple[int, int]:
            row = sql(f"SELECT a.modifier, a.duration FROM player_affects a JOIN player_data p "
                      f"ON p.pid=a.pid WHERE p.name='{PLAYER}' AND a.type=56")
            modifier, duration = row.split()
            return int(modifier), int(duration)

        def shorten_vitality() -> None:
            # A saved shorter timer shows whether the next potion renews it.
            sql(f"UPDATE player_affects a JOIN player_data p ON p.pid=a.pid SET a.duration=3 "
                f"WHERE p.name='{PLAYER}' AND a.type=56")
            sql(f"DELETE a FROM player_affects a JOIN player_data p ON p.pid=a.pid "
                f"WHERE p.name='{PLAYER}' AND a.type=2096")

        try:
            boot()
            staff = journey.MudClient(port)
            clients.append(staff)
            journey.create_character(staff)
            player = journey.MudClient(port, source_host='127.0.0.2')
            clients.append(player)
            journey.create_character(player, account=PLAYER, character=PLAYER,
                                     email='vitality@example.invalid')
            for client, name in ((staff, journey.CHARACTER), (player, PLAYER)):
                client.send('save')
                client.expect('Saving ' + name + '.', timeout=30)
            stop()
            journey.make_overlord(sql, journey.CHARACTER)
            sql(f"UPDATE player_data SET level=56,highest_level=56,base_hit=1000,hit_diff=100 "
                f"WHERE name='{PLAYER}'")

            boot()
            staff = journey.reconnect_character(port)
            clients.append(staff)
            player = connect()
            say(player, 'drop all')  # make room for the fixture items
            for vnum, keyword in ((22810, 'lesser'), (22811, 'greater'), (22812, 'potion'),
                                  (22812, 'potion')):
                say(staff, f'load obj {vnum}', None)
                say(staff, f'give {keyword} {PLAYER}', None)
            assert '[2] a potion weak vitality' in say(player, 'inventory')
            wounded = hit_points(player)
            assert wounded[0] < wounded[1], wounded
            say(player, f'recite lesser {PLAYER}', 'You feel vitalized.')
            weak = check_hit_points(player, wounded, 88)
            say(player, f'recite greater {PLAYER}', SURGE)
            strong = check_hit_points(player, weak, 136)
            leave(player)
            assert vitality() == (224, 14), vitality()
            print('PASS stronger cast on +88 raises it to +224 and raises current hit points',
                  flush=True)

            shorten_vitality()
            player = connect()
            strong = check_hit_points(player, strong, 0)  # persisted across re-entry
            say(player, 'quaff potion', SURGE)
            strong = check_hit_points(player, strong, 0)
            leave(player)
            assert vitality() == (224, 14), vitality()
            print('PASS setting on (shipped): weak potion renews the timer, +224 stays', flush=True)

            say(staff, 'properties set spell.generousRefresh.enabled 0')
            reply = say(staff, 'properties show spell.generousRefresh.enabled', '.enabled:')
            assert 'spell.generousRefresh.enabled: 0.000(1.000)' in reply, reply
            shorten_vitality()
            player = connect()
            reply = say(player, 'quaff potion', NOTHING)
            assert 'vial disappears' in reply and SURGE not in reply, reply
            assert 'potion weak vitality' not in say(player, 'inventory'), 'potion not consumed'
            check_hit_points(player, strong, 0)
            leave(player)
            assert vitality() == (224, 3), vitality()
            print('PASS setting off at runtime: weak potion is consumed and does nothing',
                  flush=True)
        except Exception:
            print(server_out.read_text(errors='replace')[-6000:])
            for client in clients:
                print(bytes(client.transcript).decode(errors='replace')
                      .replace(journey.PASSWORD, '[REDACTED]')[-4000:])
            raise
        finally:
            stop()


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit('usage: run_vitality_refresh_journey.py /path/to/mariadb/dms')
    run(Path(sys.argv[1]).resolve())
