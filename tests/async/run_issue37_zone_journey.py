#!/usr/bin/env python3
"""Issue #37 route acceptance on an isolated full world and synthetic authority.

Use --baseline before editing sources; --evidence retains command responses only.
Build caching uses the existing DURIS_REGRESSION_BUILD_CACHE contract.
"""
import argparse
import json
from pathlib import Path
import re
import signal
import subprocess
import tempfile

import test_flatfile_combat_journey as journey
from test_flight_network_journey import authority, command
from run_racial_pulse_journey import paged
from run_world_quest_dual_backend import setup_run_root, wait_for_boot
from test_issue37_zone_routes import MISTY_TRAIL, REVERSE

ROOT = journey.ROOT
PLAYER, ACCOUNT = 'Routewalker', 'Routeacct'
GOD, GOD_ACCOUNT = 'Routewarden', 'Routestaff'


def run(binary, baseline, evidence_path):
    evidence = {'baseline': baseline, 'commands': []}
    with tempfile.TemporaryDirectory(prefix='issue37-', dir=ROOT / 'bin/tests') as temporary:
        runtime = Path(temporary)
        _, critical, output_path = setup_run_root(runtime)
        process = None
        clients = []
        with authority('flatfile', runtime) as (env, _), output_path.open('w') as output:
            plain, tls, websocket = journey.available_ports()
            env.update(CRITICAL_COMMAND_JOURNAL_DIR=str(critical), DURIS_TLS_PORT=str(tls),
                       DURIS_WEBSOCKET_PORT=str(websocket),
                       MAINTENANCE_STATE_FILE=str(runtime / 'maintenance.state'))

            def boot():
                nonlocal process
                print('Booting disposable world', flush=True)
                output.seek(0)
                output.truncate()
                output.flush()
                process = subprocess.Popen([str(binary), '-d', str(runtime), str(plain)],
                                           cwd=runtime, env=env, stdout=output,
                                           stderr=subprocess.STDOUT)
                wait_for_boot(process, output_path)

            def stop():
                for client in clients:
                    client.close()
                clients.clear()
                process.send_signal(signal.SIGTERM)
                process.wait(timeout=60)
                assert process.returncode == 0, process.returncode

            def login(name, account):
                print('Logging in ' + name, flush=True)
                client = journey.reconnect_character(plain, expected_room=None,
                                                       account=account, character=name)
                clients.append(client)
                client.expect('Welcome to Duris', timeout=60)
                client.expect_any(('Pos: standing >', '<>'), timeout=20)
                command(client, 'toggle paging no')
                return client

            def cmd(client, text):
                response = command(client, text)
                evidence['commands'].append({'who': 'staff' if client is god else 'player',
                                             'command': text, 'response': response})
                return response

            def inspect(room):
                response = cmd(god, f'goto {room}')
                assert 'No room exists' not in response, response
                return cmd(god, 'stat room')

            def visit(room):
                inspect(room)
                response = cmd(god, f'transfer {PLAYER}')
                assert 'Ok.' in response, response

            def location():
                response = cmd(god, f'stat char {PLAYER}')
                match = re.search(r'In room:\s*\[?(\d+)', response)
                assert match, response
                return int(match[1])

            def walk(direction, expected):
                response = cmd(player, direction)
                assert location() == expected, (direction, expected, response)

            def checks(phase):
                print('Checking ' + phase, flush=True)
                evidence['commands'].append({'phase': phase})
                for zone in ((113, 300, 358, 71, 530, 857, 150, 7000)
                             if phase == 'first' else (150, 7000)):
                    cmd(god, 'toggle paging yes')
                    report = paged(god, f'zcheck {zone}', 'ZCHECK')
                    evidence['commands'].append({'who': 'staff', 'command': f'zcheck {zone}',
                                                 'response': report})
                    assert 'please tog page' not in report, report
                    cmd(god, 'toggle paging no')
                if phase == 'first' and not baseline:
                    for room in (546861, 543661, 616249, 615849, 546461,
                                 516444, 516843, 517246, 591773, 592172):
                        response = inspect(room)
                        if room in (546861, 543661, 516444, 516843, 517246):
                            assert 'Good Continent' in response, response
                        view = cmd(god, 'map 9')
                        assert 'Invalid map size' not in view and 'not a map room' not in view, view
                    # Teleport only establishes a starting point. Every edge is walked
                    # by the level-one player, with no room flags or doors altered.
                    entrance = 546861
                    visit(entrance)
                    walk('north', 11300)
                    walk('south', entrance)
                    visit(11348)
                    walk('north', 30172)
                    walk('south', 11348)
                    for start, direction, target, reverse in (
                        (517246, 'west', 35800, 'east'),
                        (517645, 'north', 35800, 'south'),
                        (548452, 'north', 7102, 'south'),
                        (7123, 'west', 53000, 'east'),
                        (516444, 'west', 85700, 'east'),
                        (516843, 'north', 85700, 'south'),
                    ):
                        visit(start)
                        walk(direction, target)
                        walk(reverse, start)
                    for neighbor, inward, outward in (
                        (615850, 'west', 'east'), (616249, 'north', 'south'),
                        (615848, 'east', 'west'),
                    ):
                        visit(neighbor)
                        walk(inward, 615849)
                        walk(outward, neighbor)
                    visit(615849)
                    response = cmd(player, 'north')
                    assert 'mountains are too treacherous' in response, response
                    assert location() == 615849
                    visit(546861)
                    for direction, target in (
                        ('east', 546862), ('north', 546462), ('north', 546062),
                        ('west', 546061), ('west', 546060), ('south', 546460),
                        ('south', 546860), ('east', 546861),
                    ):
                        walk(direction, target)

                    for neighbor, inward, outward in (
                        (591773, 'west', 'east'), (592172, 'north', 'south'),
                    ):
                        visit(neighbor)
                        walk(inward, 591772)
                        walk(outward, neighbor)
                    visit(591772)
                    for direction in ('north', 'west'):
                        response = cmd(player, direction)
                        assert 'mountains are too treacherous' in response, response
                        assert location() == 591772
                    visit(516444)
                    for direction, target in (
                        ('south', 516844), ('west', 516843), ('west', 516842),
                        ('north', 516442), ('south', 516842), ('east', 516843),
                        ('east', 516844), ('north', 516444),
                    ):
                        walk(direction, target)

                assert 'Khomani-Khan' in inspect(638825)
                assert 'Zone: 7000' in inspect(834025)
                view = cmd(god, 'map 9')
                assert 'Invalid map size' not in view and 'not a map room' not in view, view
                visit(638825)
                names = ('north', 'east', 'south', 'west', 'up', 'down')
                return_path = []
                current = 638825
                for direction, target in MISTY_TRAIL:
                    walk(names[direction], target)
                    return_path.append((names[REVERSE[direction]], current))
                    current = target
                assert 'A Trail Along a Misty Chasm' in cmd(player, 'look')
                if baseline:
                    cmd(player, 'down')
                    assert location() == 15015, 'baseline unexpectedly has a down route'
                    visit(834025)
                    cmd(player, 'up')
                    assert location() == 834025, 'baseline unexpectedly has an up route'
                else:
                    walk('down', 834025)
                assert 'A Narrow Tunnel in the Underdark' in cmd(player, 'look')
                for direction, target in (('north', 833625), ('south', 834025),
                                          ('east', 834026), ('west', 834025)):
                    walk(direction, target)
                if baseline:
                    visit(15015)
                else:
                    walk('up', 15015)
                for direction, target in reversed(return_path):
                    walk(direction, target)

            try:
                boot()
                for name, account in ((PLAYER, ACCOUNT), (GOD, GOD_ACCOUNT)):
                    client = journey.MudClient(plain)
                    clients.append(client)
                    journey.create_character(client, expected_room=None, account=account,
                                             character=name, email=name.lower() + '@example.invalid')
                    client.send('save')
                    client.expect('Save complete for ' + name + '.', timeout=60)
                stop()
                journey.make_overlord(Path(env['FLATFILE_STATE_DIR']), GOD)
                for phase in (('first',) if baseline else ('first', 'restart')):
                    boot()
                    god = login(GOD, GOD_ACCOUNT)
                    player = login(PLAYER, ACCOUNT)
                    # Health/movement reserves avoid unrelated NPC combat/exhaustion;
                    # level, vision, terrain, exits, and movement permissions stay mortal.
                    cmd(god, f'setbit char {PLAYER} basehit 1000000')
                    cmd(god, f'setbit char {PLAYER} mxvit 30000')
                    cmd(god, f'restore {PLAYER}')
                    checks(phase)
                    for room in (15000, 834025):
                        inspect(room)
                        response = cmd(god, 'zreset ok')
                        assert 'has been reset.' in response, response
                    checks(phase + '-reset')
                    stop()
                evidence['passed'] = True
            finally:
                for client in clients:
                    client.close()
                if process is not None and process.poll() is None:
                    process.send_signal(signal.SIGTERM)
                    process.wait(timeout=60)
                if evidence_path:
                    evidence_path.parent.mkdir(parents=True, exist_ok=True)
                    evidence_path.write_text(json.dumps(evidence, indent=2) + '\n')
                if not evidence.get('passed'):
                    print(output_path.read_text(errors='replace')[-3000:])
    print('Issue #37 ordinary route journey passed (' +
          ('baseline and reset' if baseline else 'reset and restart') + ').')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', action='store_true')
    parser.add_argument('--evidence', type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='issue37-build-', dir=ROOT / 'bin/tests') as build:
        run(journey.build_flatfile_server(Path(build)), args.baseline, args.evidence)
