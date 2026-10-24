#!/usr/bin/env python3
"""Exercise authored onboarding routes and persisted homes on disposable authority.

Supply the matching --server/--backend. Run the SQL leg through the existing
with_disposable_mariadb.sh wrapper. No checkout .env, shared account or toy
tutorial room is used. Additional acceptance scenarios are recorded in the
issue-213 handoff; this runner reports only cases it actually executes.
"""
import argparse
from collections import deque
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
import time

import test_flatfile_combat_journey as journey
from test_flight_network_journey import authority, command
from run_world_quest_dual_backend import setup_run_root
from test_issue213_tutorial_parity import records, room_exit_fields

ROOT = journey.ROOT
GOD, GOD_ACCOUNT = 'Onboardward', 'Onboardteam'
DIRS = ('north', 'east', 'south', 'west', 'up', 'down', 'northwest', 'southwest', 'northeast', 'southeast')
CASES = (
    {'name': 'Ogreryder', 'account': 'Ogrepupils', 'race': 'r', 'home': 'c', 'entry': 91200,
     'guide': 91204, 'guide_name': 'reaver', 'sword': 91204, 'outpost': 91401, 'portal': 91440,
     'map_name': 'grubruk', 'map': 91401, 'racial_home': 9, 'class_index': 1},
    {'name': 'Firwalker', 'account': 'Firpupils', 'race': 'p', 'home': 'p', 'entry': 22800,
     'guide': 22804, 'guide_name': 'paladin', 'sword': 22804, 'outpost': 29201, 'portal': 29240,
     'map_name': 'burbul', 'map': 29201, 'racial_home': 11, 'class_index': 1},
)


def guild_rooms():
    text = (ROOT / 'src/core/constant.c').read_text().split('const int guild_locations[][CLASS_COUNT + 1] =', 1)[1].split('\n};', 1)[0]
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    return [[int(value) for value in match[1].split(',')]
            for match in re.finditer(r'\{([\d,\s-]+)\}', text)]


def authored_graph():
    graph = {}
    for name in ('newbie2', 'newbie', 'chaos_intro', 'wutvr'):
        for room, record in records((ROOT / f'areas/wld/{name}.wld').read_text()).items():
            graph[room] = {DIRS[direction]: fields[2]
                           for direction, _, fields in room_exit_fields(record.splitlines(keepends=True))}
    return graph


def path_between(graph, start, target):
    pending = deque([(start, [])])
    seen = {start}
    while pending:
        room, path = pending.popleft()
        if room == target:
            return path
        for direction, next_room in graph.get(room, {}).items():
            if next_room not in seen:
                seen.add(next_room)
                pending.append((next_room, path + [(direction, next_room)]))
    raise AssertionError(f'no authored route from {start} to {target}')


def run(binary, backend, output_path):
    evidence = {'backend': backend, 'source_commit': subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'source_dirty': bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip()),
        'world_sha256': {kind: hashlib.sha256((ROOT / f'areas/world.{kind}').read_bytes()).hexdigest()
                         for kind in ('wld', 'mob', 'obj', 'zon', 'qst', 'shp', 'trg')},
        'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(), 'cases': []}
    graph, guilds = authored_graph(), guild_rooms()
    assert len(guilds) == 27, 'guild catalog includes only active hometown rows'
    inspector = ROOT / 'bin/qualification/issue213/player-inspector'
    if backend == 'flatfile' and not inspector.exists():
        subprocess.run(['python3', 'tests/async/test_flatfile_player_repository.py',
                        '--build-inspector', str(inspector)], cwd=ROOT, check=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    (ROOT / 'bin/tests').mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='issue213-' + backend + '-', dir=ROOT / 'bin/tests') as temporary:
        runtime = Path(temporary)
        _, critical, boot_log = setup_run_root(runtime)
        (runtime / 'help').symlink_to(ROOT / 'help', target_is_directory=True)
        port, tls, websocket = journey.available_ports()
        process = None
        clients = []
        history = []
        with authority(backend, runtime) as (environment, sql):
            environment.update(CRITICAL_COMMAND_JOURNAL_DIR=str(critical), DURIS_TLS_PORT=str(tls),
                               DURIS_WEBSOCKET_PORT=str(websocket), DURIS_WEBSOCKET='TRUE')

            def boot():
                nonlocal process
                offset = boot_log.stat().st_size if boot_log.exists() else 0
                with boot_log.open('a') as log:
                    process = subprocess.Popen([str(binary), '-d', str(runtime), str(port)],
                        cwd=runtime, env=environment, stdout=log, stderr=subprocess.STDOUT)
                deadline = time.monotonic() + 120
                while 'Entering game loop.' not in boot_log.read_text(errors='replace')[offset:]:
                    assert process.poll() is None and time.monotonic() < deadline, boot_log.read_text(errors='replace')[-6000:]
                    time.sleep(.1)

            def stop():
                nonlocal process
                for client in clients:
                    client.close()
                clients.clear()
                if process and process.poll() is None:
                    process.terminate()
                    process.wait(timeout=45)
                    assert process.returncode == 0
                process = None

            def login(name, account):
                client = journey.reconnect_character(port, expected_room=None, account=account, character=name)
                clients.append(client)
                history.append(client)
                client.expect('Welcome to Duris', timeout=45)
                command(client, 'toggle paging no')
                return client

            def save(client, name):
                client.send('save')
                client.expect('Save complete for ' + name + '.', timeout=45)

            def stat(name):
                text = command(god, 'stat char ' + name)
                room = re.search(r'In room:\s*\[(\d+)\]', text)
                pid = re.search(r'ID numb:\s*(\d+)', text)
                assert room and pid, text
                return int(room[1]), int(pid[1])

            def state(name):
                room, pid = stat(name)
                if sql:
                    row = list(map(int, sql(f"SELECT hometown,birthplace,orig_birthplace,exp,level,race FROM player_data WHERE pid={pid}").split('\t')))
                    result = dict(zip(('hometown', 'birthplace', 'original_birthplace', 'experience', 'level', 'race'), row))
                    result['player_items'] = [{'vnum': int(value)} for value in sql(
                        f'SELECT vnum FROM item_current_owner WHERE owner_type=1 AND owner_id={pid} AND state=1').splitlines()]
                else:
                    result = json.loads(subprocess.check_output([str(inspector), environment['FLATFILE_STATE_DIR'], 'inspect', str(pid)], text=True))
                result['current_room'] = room
                return result

            def count_item(snapshot, vnum):
                return sum(item['vnum'] == vnum for item in snapshot['player_items'])

            def walk(client, case, destination):
                for direction, expected in path_between(graph, stat(case['name'])[0], destination):
                    text = command(client, direction)
                    if stat(case['name'])[0] != expected:
                        command(client, 'open ' + direction)
                        text += command(client, direction)
                    assert stat(case['name'])[0] == expected, (case['name'], direction, expected, text)

            try:
                boot()
                for index, case in enumerate(({'name': GOD, 'account': GOD_ACCOUNT, 'race': 'h', 'home': 't'}, *CASES)):
                    client = journey.MudClient(port, source_host='127.0.0.' + str(20 + index))
                    clients.append(client)
                    history.append(client)
                    journey.create_character(client, expected_room=None, account=case['account'], character=case['name'],
                        email=case['name'].lower() + '@example.invalid', race_name=case['race'], hometown=case['home'])
                    save(client, case['name'])
                stop()
                if sql:
                    sql(f"UPDATE player_data SET level=62,highest_level=62 WHERE name='{GOD}'")
                else:
                    journey.make_overlord(Path(environment['FLATFILE_STATE_DIR']), GOD)
                boot()
                god = login(GOD, GOD_ACCOUNT)
                pupils = {case['name']: login(case['name'], case['account']) for case in CASES}
                for case in CASES:
                    player = pupils[case['name']]
                    assert stat(case['name'])[0] == case['entry']
                    command(player, 'wear all')
                    command(player, 'read sign')
                    assert "from 'armor'" in command(god, 'stat char ' + case['name'])
                    walk(player, case, case['entry'] + 1)
                    command(player, 'read sign')
                    assert "from 'bless'" in command(god, 'stat char ' + case['name'])
                    walk(player, case, case['entry'] + 6)
                    refused = command(player, 'enter stream')
                    assert 'not ready' in refused and stat(case['name'])[0] == case['entry'] + 6, refused
                    walk(player, case, case['guide'])
                    command(player, 'ask ' + case['guide_name'] + ' racewars')
                    save(player, case['name'])
                    snapshot = state(case['name'])
                    assert count_item(snapshot, case['sword']) == 1, snapshot
                    command(player, 'ask ' + case['guide_name'] + ' racewars')
                    save(player, case['name'])
                    assert count_item(state(case['name']), case['sword']) == 1
                    evidence['cases'].append({'case': case['name'] + ' guide gate and single reward', 'state': snapshot})
                    print('[PASS]', backend, case['name'], 'gate and one-time guide reward', flush=True)
                stop()
                boot()
                god = login(GOD, GOD_ACCOUNT)
                for case in CASES:
                    player = login(case['name'], case['account'])
                    assert count_item(state(case['name']), case['sword']) == 1
                    walk(player, case, case['guide'])
                    command(player, 'ask ' + case['guide_name'] + ' racewars')
                    save(player, case['name'])
                    assert count_item(state(case['name']), case['sword']) == 1
                    walk(player, case, case['entry'] + 6)
                    command(player, 'enter stream')
                    assert stat(case['name'])[0] == case['outpost']
                    delivered = command(player, 'ask ' + case['map_name'] + ' map')
                    assert 'hands you' in delivered, delivered
                    inventory = command(player, 'inventory')
                    assert 'small map of the newbie area' in inventory, inventory
                    save(player, case['name'])
                    snapshot = state(case['name'])
                    # The source map is transient/no-rent, so live delivery is
                    # the contract; it must not become a durable new reward.
                    assert count_item(snapshot, case['map']) == 0, snapshot
                    assert snapshot['birthplace'] == case['entry'], snapshot
                    walk(player, case, case['portal'])
                    command(player, 'enter archway')
                    save(player, case['name'])
                    snapshot = state(case['name'])
                    expected = guilds[case['racial_home']][case['class_index']]
                    if expected == -1:
                        expected = guilds[case['racial_home']][0]
                    assert [snapshot[key] for key in ('hometown', 'birthplace', 'original_birthplace')] == [expected] * 3, snapshot
                    evidence['cases'].append({'case': case['name'] + ' full authored route and racial home', 'state': snapshot})
                    print('[PASS]', backend, case['name'], 'authored route and three racial home fields', flush=True)
            finally:
                for index, client in enumerate(history):
                    (output_path.parent / f'{backend}-client-{index}.txt').write_bytes(bytes(client.transcript))
                if boot_log.exists():
                    output_path.with_suffix('.log').write_bytes(boot_log.read_bytes())
                output_path.write_text(json.dumps(evidence, indent=2))
                stop()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server', type=Path, required=True)
    parser.add_argument('--backend', choices=('flatfile', 'mariadb'), default='flatfile')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    run(args.server.resolve(), args.backend, args.output or ROOT / f'bin/qualification/issue213/onboarding-{args.backend}.json')
