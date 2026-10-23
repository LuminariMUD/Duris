#!/usr/bin/env python3
"""One real loaded-world stone award and reconnect, using isolated authorities.

Run explicitly with --backend flatfile or under with_disposable_mariadb.sh with
--backend mariadb. Uses existing generated world data and the supplied binary.
The fixture seeds paused objectives offline; runtime target and reward checks
remain production code. Native selector tests cover weighted population choice.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import subprocess
import tempfile
import time
import test_flatfile_combat_journey as journey
from test_flight_network_journey import authority, command
from run_world_quest_dual_backend import setup_run_root
ROOT = journey.ROOT
GOD, GOD_ACCOUNT = ('Boonwarden', 'Boonstaff')
SEED = json.loads((ROOT / 'migrations/seeds/epic_zone_payouts.json').read_text())['zones']


def stone_site(zone):
    current = None
    mob = None
    room = None
    for line in (ROOT / zone['source']).read_text(encoding='latin-1').splitlines():
        if line.startswith('#'):
            current = int(line[1:])
        fields = line.split()
        if current != zone['number'] or len(fields) < 6:
            continue
        if fields[0] == 'M':
            mob, room = int(fields[2]), int(fields[4])
        if fields[0] in ('O', 'G') and fields[2] in ('358', '359', '360'):
            if fields[0] == 'O':
                return int(fields[4]), None
            mobile = (ROOT / 'areas/world.mob').read_text(encoding='latin-1').split('#' + str(mob) + '\n', 1)[1]
            return room, mobile.split('~', 1)[0].split()[0]
    return None


def run(backend, binary):
    if backend == 'mariadb' and (not os.getenv('TEST_DB_HOST')):
        raise SystemExit('MariaDB requires with_disposable_mariadb.sh')
    output_root = ROOT / 'bin/tests'
    output_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='divine-zone-', dir=output_root) as temporary:
        runtime = Path(temporary)
        _, critical, output_path = setup_run_root(runtime)
        (runtime / 'help').symlink_to(ROOT / 'help', target_is_directory=True)
        (runtime / 'bin/server').mkdir(parents=True)
        executable = runtime / 'bin/server/dms'
        shutil.copy2(binary, executable)
        with (runtime / 'lib/misc/event_names').open('w') as names:
            subprocess.run([str(ROOT / 'scripts/event_names.sh'), str(executable)], stdout=names, check=True)
        plain, tls, websocket = journey.available_ports()
        clients = []
        process = None
        with authority(backend, runtime) as (env, sql), output_path.open('w') as output:
            env.update(CRITICAL_COMMAND_JOURNAL_DIR=str(critical), DURIS_TLS_PORT=str(tls), DURIS_WEBSOCKET_PORT=str(websocket), MAINTENANCE_STATE_FILE=str(runtime / 'maintenance.state'))

            def boot():
                nonlocal process
                offset = output_path.stat().st_size
                process = subprocess.Popen([str(executable), '-d', str(runtime), str(plain)], cwd=runtime, env=env, stdout=output, stderr=subprocess.STDOUT)
                deadline = time.monotonic() + 180
                while b'Entering game loop.' not in output_path.read_bytes()[offset:]:
                    assert process.poll() is None and time.monotonic() < deadline, 'world failed to boot'
                    time.sleep(0.1)

            def stop():
                for client in clients:
                    client.close()
                clients.clear()
                process.send_signal(signal.SIGTERM)
                process.wait(timeout=60)
                assert process.returncode == 0

            def create(name, account, race_name="h"):
                client = journey.MudClient(plain, source_host=None if name == GOD else '127.0.0.2')
                clients.append(client)
                journey.create_character(client, expected_room=None, account=account, character=name, email=name.lower() + '@example.invalid', race_name=race_name)
                command(client, 'toggle paging no')
                return client

            def login(name, account):
                client = journey.reconnect_character(plain, expected_room=None, account=account, character=name, source_host=None if name == GOD else '127.0.0.2')
                clients.append(client)
                client.expect('Welcome to Duris', timeout=60)
                client.expect_any(('Pos: standing >', '<>'), timeout=20)
                command(client, 'toggle paging no')
                return client

            def save(client, name):
                client.send('save')
                client.expect('Save complete for ' + name + '.', timeout=60)
            try:
                boot()
                god = create(GOD, GOD_ACCOUNT)
                save(god, GOD)
                stop()
                if sql:
                    sql("UPDATE player_data SET level=62,highest_level=62 WHERE name='" + GOD + "'")
                    sql(';'.join(f"UPDATE zones SET epic_payout={z['epic_payout']},suggested_group_size=100,alignment=0 WHERE number={z['number']}" for z in SEED))
                else:
                    journey.make_overlord(runtime / 'state', GOD)
                boot()
                god = login(GOD, GOD_ACCOUNT)
                # Stones initialize on their existing object periodic event (up to
                # PULSE_MOBILE+4 pulses after boot), not at catalogue construction.
                deadline = time.monotonic() + 15
                target = None
                while target is None:
                    status = command(god, 'world persistence')
                    eligible = {int(z): side for side, z in re.findall(r'divine_target side=(good|evil) zone=(\d+)', status)}
                    target = next((z for z in SEED if z['number'] in eligible and stone_site(z) is not None), None)
                    assert target or time.monotonic() < deadline, 'No reachable payable ground stone: ' + status
                    if target is None:
                        time.sleep(.5)
                zone, payout = target['number'], target['epic_payout']
                room, carrier = stone_site(target)
                side = 1 if eligible[zone] == 'evil' else 0
                stop()
                helper = runtime / 'zone-fixture'
                flags = shlex.split(subprocess.check_output(['mysql_config', '--cflags'], text=True))
                libraries = shlex.split(subprocess.check_output(['mysql_config', '--libs'], text=True))
                subprocess.run(['g++', '-std=c++20', '-Isrc', *flags, 'tests/async/divine_boon_zone_fixture.cpp',
                    'src/economy/divine_boon.c', 'src/economy/divine_boon_repository.c',
                    'src/flatfile/flatfile_authority_transaction.c', 'src/flatfile/flatfile_store.c',
                    '-lcrypto', '-pthread', *libraries, '-o', str(helper)], cwd=ROOT, check=True)
                subprocess.run([str(helper), backend, str(runtime / 'state'), str(zone), str(side)], env=env, check=True)
                boot()
                god = login(GOD, GOD_ACCOUNT)
                name, account = 'Boonpupil', 'Boonplayer'
                player = create(name, account, "o" if side else "h")
                command(god, f'goto {room}')
                if carrier:
                    given = command(god, f'force {carrier} give rune-covered {GOD}')
                    assert 'gives' in given, given
                command(god, 'purge')
                command(god, 'transfer ' + name)
                if carrier:
                    command(god, 'give rune-covered ' + name)
                    player.expect('gives you', timeout=30)
                player.send('touch rune-covered')
                player.expect('You have gained ', timeout=60)
                tail = player.expect('epic point', timeout=30)
                match = re.search(r'(\d+) epic point', tail)
                assert match, tail
                amount = int(match.group(1))
                print(f'{backend}: real eligible zone {zone} award={amount}, base={payout}', flush=True)
                assert amount == int(payout * 1.5), 'Prepared boon was not applied at the real stone'
                save(player, name)
                awarded = (name, account, amount, player)
                name, account, amount, player = awarded
                player.close()
                clients.remove(player)
                stop()
                boot()
                player = login(name, account)
                score = command(player, 'score')
                assert re.search('\\b' + str(amount) + '\\b', score), score
                print(f'PASS {backend}: loaded real stone +50% award, saved recipient, restart/reconnect', flush=True)
            except Exception as error:
                evidence = output_root / ('divine-zone-failure-' + backend + '-' + str(time.time_ns()))
                evidence.mkdir()
                shutil.copy2(output_path, evidence / 'server.out')
                shutil.copytree(runtime / 'logs', evidence / 'logs')
                transcripts = '\n'.join((bytes(c.transcript[-5000:]).decode(errors='replace') for c in clients))
                raise AssertionError(f'{error}\nEvidence: {evidence}\n{transcripts}') from error
            finally:
                for client in clients:
                    client.close()
                if process and process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=30)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=10)
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--backend', choices=['flatfile', 'mariadb'], required=True)
    parser.add_argument('--server', type=Path, required=True)
    args = parser.parse_args()
    run(args.backend, args.server.resolve())
