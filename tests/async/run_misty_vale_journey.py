#!/usr/bin/env python3
"""Exercise installed Misty Vale in an isolated full-world flat-file server.

Uses synthetic accounts, existing fixture helpers, and the supplied native binary.
Staff supplies recipe ingredients and tranquilizes local NPCs to isolate the
mechanics from combat. All hand-ins and portal/switch uses are mortal.
"""
import argparse
from collections import Counter
import hashlib
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
from test_misty_vale_zone import NAME, records

ROOT = journey.ROOT
PLAYER, ACCOUNT = 'Valewalker', 'Valeacct'
GOD, GOD_ACCOUNT = 'Valewarden', 'Valestaff'


def run(binary, evidence_path):
    evidence = {'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
                'commands': [], 'checks': []}
    (ROOT / 'bin/tests').mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='misty-vale-', dir=ROOT / 'bin/tests') as tmp:
        runtime = Path(tmp)
        _, critical, output_path = setup_run_root(runtime)
        process, clients = None, []
        with authority('flatfile', runtime) as (env, _), output_path.open('w') as output:
            plain, tls, websocket = journey.available_ports()
            env.update(CRITICAL_COMMAND_JOURNAL_DIR=str(critical), DURIS_TLS_PORT=str(tls),
                       DURIS_WEBSOCKET_PORT=str(websocket),
                       MAINTENANCE_STATE_FILE=str(runtime / 'maintenance.state'))

            def boot():
                nonlocal process
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

            def cmd(client, text):
                response = command(client, text)
                evidence['commands'].append({'who': 'staff' if client is god else 'player',
                                             'command': text, 'response': response})
                evidence_path.write_text(json.dumps(evidence, indent=2) + '\n')
                return response

            def login(name, account):
                client = journey.reconnect_character(plain, expected_room=None,
                                                     account=account, character=name)
                clients.append(client)
                client.expect('Welcome to Duris', timeout=60)
                client.expect_any(('Pos: standing >', '<>'), timeout=20)
                command(client, 'toggle paging no')
                return client

            def visit(room):
                # End existing fights and keep local NPCs asleep while testing
                # movement. Quest givers are awakened explicitly for hand-ins.
                cmd(god, f'goto {PLAYER}')
                cmd(god, 'tranquilize')
                assert 'No room exists' not in cmd(god, f'goto {room}')
                assert 'Ok.' in cmd(god, f'transfer {PLAYER}')
                cmd(god, 'tranquilize')
                cmd(god, f'affectpurge {PLAYER} all')
                cmd(player, 'wake')
                cmd(player, 'stand')

            def location():
                response = cmd(god, f'stat char {PLAYER}')
                return int(re.search(r'In room:\s*\[?(\d+)', response)[1])

            def move(text, room):
                response = cmd(player, text)
                assert location() == room, (text, room, response)

            def check(label):
                evidence['checks'].append(label)
                print(label, flush=True)

            def assert_owned_rod_pristine():
                # The rod must be in staff inventory: stat obj by keyword otherwise
                # falls back to scanning the world and might select another copy.
                report = cmd(god, 'stat obj rod')
                # Staff stat inserts colour escapes between the labels and numbers.
                plain = re.sub(r'\x1b\[[0-9;]*m', '', report)
                assert re.search(r'Number:\s*\[300039\]', plain), report
                assert re.search(r'Condition:\s*100\b', plain), report

            def reset():
                cmd(god, 'goto 300000')
                assert 'has been reset.' in cmd(god, 'zreset ok')

            def give_item(vnum):
                keyword = object_records[vnum].split('~')[0].split()[0]
                assert 'created' in cmd(god, f'load obj {vnum}')
                flags = int(object_records[vnum].split('~')[4].split()[6])
                if flags & 4096:  # Supply already-discovered skins/scales for hand-in tests.
                    assert 'SECRET bit removed' in cmd(god, f'secret {keyword}')
                assert 'Ok.' in cmd(god, f'give {keyword} {PLAYER}')
                return keyword

            try:
                evidence_path.parent.mkdir(parents=True, exist_ok=True)
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
                boot()
                god, player = login(GOD, GOD_ACCOUNT), login(PLAYER, ACCOUNT)
                cmd(god, 'vis 0')
                cmd(player, 'drop all')
                cmd(god, f'setbit char {PLAYER} basehit 1000000')
                cmd(god, f'setbit char {PLAYER} mxvit 30000')
                cmd(god, f'restore {PLAYER}')
                object_records = records(ROOT / f'areas/obj/{NAME}.obj')
                for path in (ROOT / 'areas/obj').glob('*.obj'):
                    for vnum, block in records(path).items():
                        if vnum in (35237, 94701):
                            object_records[vnum] = block

                visit(300000)
                cmd(god, 'toggle paging yes')
                report = paged(god, 'zcheck 3000', 'Read-only report')
                evidence['zcheck'] = report
                listing = paged(god, 'qlist', 'Quest givers')
                evidence['qlist'] = listing
                cmd(god, 'toggle paging no')
                assert 'disabled by the loader' not in report, report
                assert '0 high' in report or 'looks clean' in report, report
                assert '<missing' not in listing, listing
                check('native zone diagnostics and quest listing loaded')

                for target, reward, ingredients in (
                    ('shaman', 300013, [300004, 300002, 300012, 300017]),
                    ('gynaeros', 300036, [300001, 300024]),
                ):
                    reset()
                    visit(300024)
                    cmd(player, f'wake {target}')
                    response = cmd(player, f'ask {target} scales')
                    assert 'bring me both a small and large scale' in response, response
                    label = re.sub(r'&[+=].|&[nN]', '', object_records[reward].split('~')[1].strip())
                    for ingredient in ingredients[:-1]:
                        keyword = give_item(ingredient)
                        cmd(player, f'give {keyword} {target}')
                    assert label not in cmd(player, 'inventory'), ('premature reward', reward)
                    keyword = give_item(ingredients[-1])
                    completion = cmd(player, f'give {keyword} {target}')
                    assert label in cmd(player, 'inventory'), (reward, completion)
                    assert 'Gynaeros' not in cmd(player, 'look'), completion
                    check(f'shaman recipe {reward}: ask and hand-ins work via {target}')

                for start, action, end, back in (
                    (300132, 'enter well', 300133, 'up'),
                    (300039, 'enter waterfall', 300144, 'west'),
                    (300068, 'climb ladder', 300151, 'climb ladder'),
                    (300059, 'enter pond', 300152, 'up'),
                    (300166, 'enter archway', 96821, 'enter well'),
                ):
                    visit(start)
                    move(action, end)
                    move(back, start)
                check('five portal pairs, including Dirkn archway/well, work for a mortal')
                for start, action, direction, end in (
                    (300049, 'pull brambles', 'north', 300061),
                    (300061, 'pull brambles', 'south', 300049),
                    (300051, 'wake head', 'down', 300143),
                ):
                    reset()
                    visit(start)
                    move(direction, start)
                    cmd(player, action)
                    move(direction, end)
                visit(300165)
                assert 'rumbling' in cmd(player, 'pull lever')
                visit(300159)
                move('west', 300166)
                visit(300121)
                assert 'rumbling' in cmd(player, 'push head')
                visit(300105)
                move('east', 300106)
                check('all five authored switches open their intended blocked exits')

                # Inspect prototype population counts, subtracting stat's temporary instance.
                reset()
                counts = Counter(int(row.split()[2]) for row in
                                 (ROOT / f'areas/zon/{NAME}.zon').read_text().splitlines()
                                 if row.startswith(('M ', 'F ')))
                for vnum in (300001, 300007, 300008, 300035):
                    response = cmd(god, f'stat mob {vnum}')
                    actual = int(re.search(r'# in game:\s*(\d+)', response)[1]) - 1
                    assert actual == counts[vnum], (vnum, actual, counts[vnum])
                check('multi-room populations and follower groups reach their authored counts')

                # A mortal pays for each recipe; D disappearance remains authored behavior.
                recipes = (
                    (300023, [94701], 120),
                    (300025, [300001, 300001, 300024, 300024], 0),
                    (300034, [35237, 35237, 300024, 300024], 100),
                    (300035, [35237, 35237, 300001, 300001, 300001], 75),
                    (300040, [35237, 94701], 300),
                )
                for reward, ingredients, platinum in recipes:
                    label = re.sub(r'&[+=].|&[nN]', '', object_records[reward].split('~')[1].strip())
                    reset()
                    visit(300151)
                    cmd(player, 'wake dokumaci')
                    cmd(god, f'setbit char {PLAYER} platinum {platinum}')
                    keywords = [give_item(v) for v in ingredients]
                    if platinum:
                        assert 'Ok.' in cmd(player, f'give {platinum} platinum dokumaci')
                    for item in keywords[:-1]:
                        cmd(player, f'give {item} dokumaci')
                    assert label not in cmd(player, 'inventory'), ('premature reward', reward)
                    completion = cmd(player, f'give {keywords[-1]} dokumaci')
                    assert label in cmd(player, 'inventory'), (reward, completion)
                    assert 'Dokumaci' not in cmd(player, 'look'), completion
                    check(f'recipe {reward}: exact ingredients grant reward and the weaver leaves')

                for scale, amount in ((300001, 25), (300024, 50)):
                    reset()
                    # The ordinary warriors roam. Load this quest instance in the
                    # treehouse so it cannot walk away halfway through a hand-in.
                    visit(300151)
                    assert 'created' in cmd(god, 'load mob 300003')
                    cmd(god, f'setbit char {PLAYER} platinum 0')
                    keyword = give_item(scale)
                    cmd(player, f'give {keyword} warrior')
                    wallet = cmd(player, 'score')
                    assert re.search(rf'Coins carried:\s*{amount} platinum', wallet), wallet
                check('warrior independently exchanges either small or large scale')

                visit(300056)
                cmd(player, 'wake fat')
                cmd(god, f'setbit char {PLAYER} platinum 100')
                listing = cmd(player, 'list')
                assert 'canoe' in listing and 'rod' in listing, listing
                for item in ('canoe', 'rod'):
                    response = cmd(player, f'buy {item}')
                    if 'You now have ' not in response:
                        player.expect('You now have ', timeout=30)
                        player.expect_any(('Pos: standing >', '<>'), timeout=30)
                    assert item in cmd(player, 'inventory')
                # Inspect the actual purchased rod, not the pristine prototype
                # nor inventory display (which hides conditions above 90%).
                assert 'Ok.' in cmd(player, f'give rod {GOD}')
                assert_owned_rod_pristine()
                check('tackle shop sells canoe and a 100%-condition teak rod')
                # Fishing requires a learned skill; staff's restore initializes it without
                # changing the mortal recipe/movement fixture's progression.
                cmd(god, 'restore self')
                cmd(god, 'goto 300059')
                fishing = cmd(god, 'fish')
                assert 'cast your pole' in fishing, fishing
                check('the new fishing rod starts native fishing')
                cmd(god, 'goto 300056')
                cmd(god, f'give rod {PLAYER}')
                assert 'rod' in cmd(player, 'inventory'), 'rod not returned after fishing'

                visit(300000)
                player.send('save')
                player.expect(f'Save complete for {PLAYER}.', timeout=60)
                stop()
                boot()
                god, player = login(GOD, GOD_ACCOUNT), login(PLAYER, ACCOUNT)
                inventory = cmd(player, 'inventory')
                assert all(item in inventory for item in ('sleeves', 'shield', 'leggings', 'tunic', 'boots', 'canoe', 'rod')), inventory
                # Confirm the persisted instance, not a newly loaded object template.
                cmd(god, f'goto {PLAYER}')
                assert 'Ok.' in cmd(player, f'give rod {GOD}')
                assert_owned_rod_pristine()
                check('crafting rewards, purchased canoe and 100%-condition rod survive restart')
                evidence['passed'] = True
                stop()
            finally:
                for client in clients:
                    client.close()
                if process is not None and process.poll() is None:
                    process.send_signal(signal.SIGTERM)
                    process.wait(timeout=60)
                evidence['boot_log_tail'] = output_path.read_text(errors='replace')[-6000:]
                evidence_path.write_text(json.dumps(evidence, indent=2) + '\n')
    print('Misty Vale native journey passed.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    args = parser.parse_args()
    run(args.server.resolve(), args.evidence.resolve())
