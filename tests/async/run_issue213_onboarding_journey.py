#!/usr/bin/env python3
"""Exercise authored onboarding routes and persisted homes on disposable authority.

Supply the matching --server/--backend. Run the SQL leg through the existing
with_disposable_mariadb.sh wrapper. No checkout .env, shared account or toy
tutorial room is used. Additional acceptance scenarios are recorded in the
issue-213 handoff; this runner reports only cases it actually executes.
"""
import argparse
from collections import deque
from concurrent.futures import ThreadPoolExecutor
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
OVERSIZED = {'Ogreryder', 'Firwalker'}
DIRS = ('north', 'east', 'south', 'west', 'up', 'down', 'northwest', 'southwest', 'northeast', 'southeast')
CASES = (
    {'name': 'Ogreryder', 'account': 'Ogrepupils', 'race': 'r', 'home': 'c', 'entry': 91200,
     'guide': 91204, 'guide_name': 'reaver', 'sword': 91204, 'outpost': 91401, 'portal': 91440,
     'map_name': 'grubruk', 'map': 91401, 'racial_home': 9, 'class_index': 1},
    {'name': 'Firwalker', 'account': 'Firpupils', 'race': 'p', 'home': 'p', 'entry': 22800,
     'guide': 22804, 'guide_name': 'paladin', 'sword': 22804, 'outpost': 29201, 'portal': 29240,
     'map_name': 'burbul', 'map': 29201, 'racial_home': 11, 'class_index': 1},
)
CASES += tuple(dict(CASES[0], **case) for case in (
    {'name': 'Gobspell', 'account': 'Gobpupils', 'race': 'v', 'class': 's', 'class_index': 10, 'racial_home': 20},
    {'name': 'Thrilearn', 'account': 'Thripupils', 'race': 'k', 'alignment': 'e', 'racial_home': 18},
    {'name': 'Minolearn', 'account': 'Minopupils', 'race': 's', 'alignment': 'e', 'racial_home': 14},
    {'name': 'Tieflearn', 'account': 'Tiefpupils', 'race': 'f', 'alignment': 'e', 'racial_home': 3},
))
CASES += (dict(CASES[1], name='Humanlearn', account='Humanpupils', race='h', racial_home=1),)
DIRECT_CASES = (
    {'name': 'Faangling', 'account': 'Faangpupils', 'race': 'r', 'home': 'f', 'entry': 15295},
    {'name': 'Ugtaling', 'account': 'Ugtapupils', 'race': 'p', 'home': 'u', 'entry': 39283},
    {'name': 'Wutvrog', 'account': 'Wutvrpupils', 'race': 'r', 'home': 'w', 'entry': 91401, 'invitation': 91519},
    {'name': 'Ailfir', 'account': 'Ailviopupils', 'race': 'p', 'home': 'o', 'entry': 29201, 'invitation': 29319},
)


def guild_rooms():
    text = (ROOT / 'src/core/constant.c').read_text().split('const int guild_locations[][CLASS_COUNT + 1] =', 1)[1].split('\n};', 1)[0]
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    return [[int(value) for value in match[1].split(',')]
            for match in re.finditer(r'\{([\d,\s-]+)\}', text)]


def wallet_value(client):
    text = command(client, 'score')
    purse = re.search(r'Coins carried:\s*(\d+) platinum\s*(\d+) gold\s*(\d+) silver\s*(\d+) copper', text)
    assert purse, text
    return sum(int(value) * unit for value, unit in zip(purse.groups(), (1000, 100, 10, 1)))


def authored_graph():
    graph = {}
    for name in ('newbie2', 'newbie', 'chaos_intro', 'wutvr'):
        for room, record in records((ROOT / f'areas/wld/{name}.wld').read_text()).items():
            graph[room] = {DIRS[direction]: fields[2]
                           for direction, _, fields in room_exit_fields(record.splitlines(keepends=True))}
    # The secret shop has no directional exit: the authored orb and mirror
    # form its touch/enter route. Their remapped values are checked by parity.
    for offset in (0, 62200):
        graph[29232 + offset]['touch orb'] = 29305 + offset
        graph[29305 + offset]['enter mirror'] = 29232 + offset
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
        'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
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
        player_ids = {}
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
                assert 'Paging mode off' in command(client, 'toggle paging no')
                return client

            def save(client, name):
                client.send('save')
                client.expect('Save complete for ' + name + '.', timeout=45)

            def stat(name):
                text = command(god, 'stat char ' + name)
                room = re.search(r'In room:\s*\[(\d+)\]', text)
                pid = re.search(r'ID numb:\s*(\d+)', text)
                assert room and pid, text
                player_ids[name] = int(pid[1])
                return int(room[1]), int(pid[1])

            def state(name, resident=True):
                room, pid = stat(name) if resident else (None, player_ids[name])
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
                    arrived = stat(case['name'])[0]
                    if arrived != expected and direction in DIRS:
                        command(client, 'open ' + direction)
                        text += command(client, direction)
                        arrived = stat(case['name'])[0]
                    assert arrived == expected, (case['name'], direction, expected, text)

            def die_and_return(client, case, expected_room):
                save(client, case['name'])
                before = state(case['name'])
                command(god, 'goto ' + case['name'])
                command(god, 'kill ' + case['name'])
                client.expect('ACCOUNT MENU', timeout=45)
                after = state(case['name'], resident=False)
                assert after['level'] == before['level'] and after['experience'] == before['experience'], (before, after)
                client.close()
                client = login(case['name'], case['account'])
                assert stat(case['name'])[0] == expected_room
                if before['level'] in (1, 29):
                    command(god, 'setbit char ' + GOD + ' class Cleric')
                    command(god, "cast 'resurrect' corpse", timeout=45)
                    save(client, case['name'])
                    resurrected = state(case['name'])
                    assert resurrected['level'] == before['level'] and resurrected['experience'] == before['experience'], (before, resurrected)
                    # Restore only resources after the verified resurrection's
                    # normal exhaustion; tutorial encounter balance is unchanged.
                    command(god, 'restore ' + case['name'])
                command(client, 'get all corpse')
                evidence['cases'].append({'case': case['name'] + ' protected death and respawn', 'state': after})
                return client

            def services(player, case):
                offset = case['outpost'] - 29201
                name = case['name']
                searcher = 'zyrrak' if offset else 'chyron'
                walk(player, case, 29247 + offset)
                assert 'search' in command(player, 'ask ' + searcher + ' search').lower()
                inventory = command(player, 'inventory').lower()
                for _ in range(30):
                    if 'a salt box' in inventory and 'basilisk tears' in inventory:
                        break
                    command(player, 'search')
                    if 'a salt box' not in inventory:
                        command(player, 'get salt')
                    if 'basilisk tears' not in inventory:
                        command(player, 'get vial')
                    inventory = command(player, 'inventory').lower()
                else:
                    raise AssertionError('authored search ingredients were not obtainable: ' + inventory)
                command(player, 'give salt ' + searcher)
                reward = command(player, 'give vial ' + searcher)
                assert 'first batch' in reward, reward
                command(player, 'get marbled')
                save(player, name)
                assert count_item(state(name), 29222 + offset) == 1
                command(player, 'quaff marbled')
                assert "from 'detect magic'" in command(god, 'stat char ' + name)
                print('[PASS]', backend, name, 'search and potion reward', flush=True)

                walk(player, case, 29289 + offset)
                save(player, name)
                before = state(name)['experience']
                text = command(player, 'bandage ' + ('orc' if offset else 'human'))
                assert 'attempt to bandage' in text, text
                if 'THANK YOU!!!' not in text:
                    player.expect('THANK YOU!!!', timeout=60)
                save(player, name)
                assert state(name)['experience'] > before
                print('[PASS]', backend, name, 'bandage reward', flush=True)

                # Exercise the complete item goal and item/coin/XP payout through
                # real GIVE dispatch. Prerequisite body parts are allocated by
                # staff here; encounter parity is covered by the loaded profiles.
                walk(player, case, 29217 + offset)
                command(god, 'goto ' + name)
                for vnum, keyword in ((29262, 'ear'), (29263, 'scalp'), (29264, 'toe')):
                    command(god, 'load obj ' + str(vnum + offset))
                    command(god, 'drop ' + keyword)
                # These authored body parts start SECRET. Staff reveals the
                # allocated prerequisites through normal search dispatch.
                command(god, 'search')
                for keyword in ('ear', 'scalp', 'toe'):
                    received = command(player, 'get ' + keyword)
                    assert 'You get' in received, received
                save(player, name)
                before = state(name)['experience']
                reward = ''
                for keyword in ('ear', 'scalp', 'toe'):
                    reward += command(player, 'give ' + keyword + ' ' + ('krag' if offset else 'kord'))
                assert 'experience' in reward and re.search(r'gives .*?\d.*?(?:copper|silver|gold|platinum).*? to you', reward, re.I), reward
                save(player, name)
                snapshot = state(name)
                assert count_item(snapshot, 29237 + offset) == 1 and snapshot['experience'] > before, snapshot
                print('[PASS]', backend, name, 'multi-item quest and item/coin/XP rewards', flush=True)

                command(god, 'setbit char ' + name + ' platinum 100')
                save(player, name)
                walk(player, case, case['outpost'])
                listing = command(player, 'list')
                assert 'bandage' in listing.lower(), listing
                save(player, name)
                bandages = count_item(state(name), 393)
                purse = wallet_value(player)
                bought = command(player, 'buy bandage')
                if 'You now have' not in bought:
                    assert 'Your purchase is being processed' in bought, bought
                    outcome, bought = player.expect_any(('You now have', 'could not', 'failed'), timeout=45)
                    assert outcome == 'You now have', bought
                save(player, name)
                assert count_item(state(name), 393) == bandages + 1
                assert wallet_value(player) == purse - 1, 'small bandage was not charged its listed one copper'
                # Legacy prices/visibility can leave a source shop with nothing
                # for sale. Check every binding without inventing sale stock.
                for room in (29269, 29276, 29260, 29271, 29257, 29268, 29305):
                    walk(player, case, room + offset)
                    listing = command(player, 'list')
                    assert 'You can buy:' in listing, listing
                    assert 'Nothing!' in listing or re.search(r'(?m)^\s*\d+\) .+ for ', listing), listing
                print('[PASS]', backend, name, 'eight shop bindings and one-copper purchase', flush=True)
                for room in (29280, 29282):
                    walk(player, case, room + offset)
                    listing = command(player, 'list')
                    assert 'Available hirelings' in listing and ' for ' in listing, listing
                    pet_name = 'a black mountain pony' if room == 29280 else 'a small squirrel'
                    offered = re.search(r'(?m)^\[(\d+)\]\s*' + re.escape(pet_name) + r'\s+for ', listing)
                    assert offered, listing
                    buy = 'buy ' + offered[1]
                    if room == 29280:
                        denied = command(player, buy)
                        assert 'not experienced enough' in denied, denied
                        command(god, 'advance ' + name + ' 10')
                        assert 'May you enjoy your pet' in command(player, buy)
                    else:
                        assert 'May you enjoy your pet' in command(player, buy)

                for room, effect in ((29206, 'spirit armor'), (29227, 'armor'),
                                     (29233, 'detect magic'), (29228, 'barkskin')):
                    walk(player, case, room + offset)
                    # Start each spell family without a mutually exclusive skin
                    # or sign buff; keep normal service timing and spell power.
                    command(god, 'affectpurge ' + name + ' all')
                    deadline = time.monotonic() + 90
                    while "from '" + effect + "'" not in command(god, 'stat char ' + name):
                        assert time.monotonic() < deadline, 'no authored spell-up: ' + effect
                        time.sleep(.5)
                    print('[PASS]', backend, name, 'periodic spell-up', effect, flush=True)
                walk(player, case, 29202 + offset)
                save(player, name)
                player.send('rent')
                player.expect('ACCOUNT MENU', timeout=45)
                player.close()
                player = login(name, case['account'])
                assert stat(name)[0] == 29202 + offset
                command(god, 'goto ' + name)
                assert 'has been reset' in command(god, 'zreset ok')
                walk(player, case, case['outpost'])
                assert 'hands you' in command(player, 'ask ' + case['map_name'] + ' map')
                evidence['cases'].append({'case': name + ' search/bandage/quest/shop/pet/spell-up/inn/reset services', 'state': state(name)})
                print('[PASS]', backend, name, 'authored services, rent and reset', flush=True)
                return player

            try:
                boot()
                def create(index_case):
                    index, case = index_case
                    client = journey.MudClient(port, source_host='127.0.0.' + str(20 + index))
                    clients.append(client)
                    history.append(client)
                    journey.create_character(client, expected_room=None, account=case['account'], character=case['name'],
                        email=case['name'].lower() + '@example.invalid', race_name=case['race'], hometown=case['home'],
                        class_name=case.get('class', 'w'), alignment=case.get('alignment', 'g'))
                    save(client, case['name'])
                creations = ({'name': GOD, 'account': GOD_ACCOUNT, 'race': 'h', 'home': 't'}, *CASES, *DIRECT_CASES)
                with ThreadPoolExecutor(max_workers=8) as workers:
                    list(workers.map(create, enumerate(creations)))
                stop()
                if sql:
                    sql(f"UPDATE player_data SET level=62,highest_level=62 WHERE name='{GOD}'")
                else:
                    journey.make_overlord(Path(environment['FLATFILE_STATE_DIR']), GOD)
                boot()
                god = login(GOD, GOD_ACCOUNT)
                pupils = {case['name']: login(case['name'], case['account']) for case in CASES}
                for case in DIRECT_CASES:
                    player = login(case['name'], case['account'])
                    snapshot = state(case['name'])
                    assert snapshot['current_room'] == case['entry'], snapshot
                    assert snapshot['birthplace'] == case['entry'], snapshot
                    if 'invitation' in case:
                        assert count_item(snapshot, case['invitation']) == 1, snapshot
                    evidence['cases'].append({'case': case['name'] + ' direct creation and cold reload', 'state': snapshot})
                for case in CASES:
                    player = pupils[case['name']]
                    assert stat(case['name'])[0] == case['entry']
                    if case['name'] in OVERSIZED:
                        assert 'all races and sides are protected' in command(player, 'help death')
                        player = pupils[case['name']] = die_and_return(player, case, case['entry'])
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
                    if case['name'] in OVERSIZED:
                        # Keep worn armor and discard unused carried kit so
                        # swapping weapons obeys normal inventory/hand limits.
                        command(player, 'drop all')
                        for keyword in ('mace', 'sword', 'shield'):
                            command(player, 'remove ' + keyword)
                        command(player, 'get blessed')
                        wielded = command(player, 'wield blessed')
                        assert 'You wield' in wielded, wielded
                        command(player, 'wear all')
                        for _ in range(4):
                            command(player, 'get bandage')
                    command(player, 'ask ' + case['guide_name'] + ' racewars')
                    save(player, case['name'])
                    assert count_item(state(case['name']), case['sword']) == 1
                    evidence['cases'].append({'case': case['name'] + ' guide gate and single reward', 'state': snapshot})
                    print('[PASS]', backend, case['name'], 'gate and one-time guide reward', flush=True)
                stop()
                boot()
                god = login(GOD, GOD_ACCOUNT)
                threshold_states = {}
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
                    if case['name'] in OVERSIZED:
                        player = services(player, case)
                    walk(player, case, case['portal'])
                    command(player, 'enter archway')
                    save(player, case['name'])
                    snapshot = state(case['name'])
                    expected = guilds[case['racial_home']][case['class_index']]
                    if expected == -1:
                        expected = guilds[case['racial_home']][0]
                    assert [snapshot[key] for key in ('hometown', 'birthplace', 'original_birthplace')] == [expected] * 3, snapshot
                    if case['name'] in OVERSIZED:
                        player = die_and_return(player, case, expected)
                    evidence['cases'].append({'case': case['name'] + ' full authored route and racial home', 'state': snapshot})
                    print('[PASS]', backend, case['name'], 'authored route and three racial home fields', flush=True)
                stop()
                boot()
                god = login(GOD, GOD_ACCOUNT)
                for case in CASES:
                    player = login(case['name'], case['account'])
                    expected = guilds[case['racial_home']][case['class_index']]
                    if expected == -1:
                        expected = guilds[case['racial_home']][0]
                    snapshot = state(case['name'])
                    assert [snapshot[key] for key in ('hometown', 'birthplace', 'original_birthplace')] == [expected] * 3, snapshot
                    if case['name'] in OVERSIZED:
                        command(god, 'setbit char ' + case['name'] + ' level 29')
                        command(god, 'setbit char ' + case['name'] + ' exp 12345')
                        player = die_and_return(player, case, expected)
                        raw_start = len(player.raw_transcript)
                        command(god, 'advance ' + case['name'] + ' 30')
                        warning = command(player, 'score')
                        assert warning.count('WARNING: YOU HAVE REACHED LEVEL 30.') == 1, warning
                        bold = re.search(rb'\x1b\[([0-9;]*)mWARNING: YOU HAVE REACHED LEVEL 30\.', bytes(player.raw_transcript[raw_start:]))
                        assert bold and b'1' in bold[1].split(b';'), 'terminal warning did not enable ANSI bold'
                        command(god, 'setbit char ' + case['name'] + ' exp 12345')
                        save(player, case['name'])
                        before = state(case['name'])
                        command(god, 'goto ' + case['name'])
                        command(god, 'kill ' + case['name'])
                        player.expect('ACCOUNT MENU', timeout=45)
                        player.close()
                        player = login(case['name'], case['account'])
                        save(player, case['name'])
                        after = state(case['name'])
                        assert after['level'] < before['level'] or after['experience'] < before['experience'], (before, after)
                        assert [after[key] for key in ('hometown', 'birthplace', 'original_birthplace')] == [expected] * 3
                        threshold_states[case['name']] = after
                        evidence['cases'].append({'case': case['name'] + ' threshold warning and unprotected death', 'before': before, 'after': after})
                        print('[PASS]', backend, case['name'], 'level 29 protection, bold crossing and level 30 loss', flush=True)
                stop()
                boot()
                god = login(GOD, GOD_ACCOUNT)
                for case in CASES:
                    if case['name'] not in threshold_states:
                        continue
                    player = login(case['name'], case['account'])
                    final = state(case['name'])
                    for field in ('level', 'experience', 'hometown', 'birthplace', 'original_birthplace'):
                        assert final[field] == threshold_states[case['name']][field], (field, final, threshold_states[case['name']])
                evidence['routes'] = [case['name'] for case in CASES]
                evidence['completed'] = True
            finally:
                for index, client in enumerate(history):
                    (output_path.parent / f'{output_path.stem}-client-{index}.txt').write_bytes(bytes(client.transcript))
                    (output_path.parent / f'{output_path.stem}-client-{index}.ansi').write_bytes(bytes(client.raw_transcript))
                if boot_log.exists():
                    output_path.with_suffix('.log').write_bytes(boot_log.read_bytes())
                output_path.write_text(json.dumps(evidence, indent=2))
                stop()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server', type=Path, required=True)
    parser.add_argument('--backend', choices=('flatfile', 'mariadb'), default='flatfile')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--case', action='append', choices=[case['name'] for case in CASES],
                        help='run only the named route(s) while developing a focused acceptance leg')
    args = parser.parse_args()
    if args.case:
        CASES = tuple(case for case in CASES if case['name'] in args.case)
        DIRECT_CASES = ()
    run(args.server.resolve(), args.backend, args.output or ROOT / f'bin/qualification/issue213/onboarding-{args.backend}.json')
