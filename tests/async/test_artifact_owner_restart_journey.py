#!/usr/bin/env python3
"""Qualified stale ownership -> login -> elite reward feed -> orderly shutdown.

Runs only private servers, synthetic accounts and disposable state; never reads .env.
MariaDB requires the TEST_DB_* credentials for a disposable loopback instance.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import tempfile
import time

import test_flatfile_combat_journey as journey
from test_flight_network_journey import authority, command
from run_world_quest_dual_backend import setup_run_root

ROOT = journey.ROOT
GOD, GOD_ACCOUNT = 'Ownerwarden', 'Ownerstaff'
PLAYER, ACCOUNT = 'Ownerwearer', 'Ownerplayer'
ARTIFACT = 900000


def run(binary, backend, inspector, conflicts_only=False):
    with tempfile.TemporaryDirectory(prefix='artifact-owner-' + backend + '-', dir=ROOT / 'bin/tests') as temporary:
        runtime = Path(temporary)
        _, critical, output_path = setup_run_root(runtime)
        (runtime / 'help').symlink_to(ROOT / 'help', target_is_directory=True)
        # A private artifact has no random reset producer in the full world.
        objects = (ROOT / 'areas/world.obj').read_text(encoding='latin-1')
        original = re.search(r'(?ms)^#900\n.*?(?=^#\d+\n)', objects)
        assert original and not re.search(rf'(?m)^#{ARTIFACT}$', objects)
        position = next(m.start() for m in re.finditer(r'(?m)^#(\d+)\n', objects) if int(m[1]) > ARTIFACT)
        areas = runtime / 'areas'
        areas.unlink(); areas.mkdir()
        for source in (ROOT / 'areas').iterdir():
            if source.name != 'world.obj':
                (areas / source.name).symlink_to(source, target_is_directory=source.is_dir())
        record = original.group().replace('#900\n', f'#{ARTIFACT}\n', 1)
        (areas / 'world.obj').write_text(objects[:position] + record + objects[position:], encoding='latin-1')
        executable = runtime / 'bin/server/dms'
        executable.parent.mkdir(parents=True)
        shutil.copy2(binary, executable)
        with (runtime / 'lib/misc/event_names').open('w') as names:
            subprocess.run([str(ROOT / 'scripts/event_names.sh'), str(executable)], stdout=names, check=True)
        properties = runtime / 'lib/duris.properties'
        text = properties.read_text()
        for key, value in {'camp.timer': 1, 'artifact.feeding.epic.point.seconds': 3600,
                           'artifact.feeding.epic.typeMod.eliteMob': .25,
                           'difficulty.dial.epic.gain': 5, 'difficulty.dial.artifact.feeding': 5,
                           'epic.gain.modifier.good': 1}.items():
            text, count = re.subn(r'^' + re.escape(key) + r'=.*$', key + '=' + str(value), text, flags=re.M)
            if not count:
                text += '\n' + key + '=' + str(value) + '\n'
        properties.write_text(text)
        plain, tls, websocket = journey.available_ports()
        clients, evidence = [], []
        process = None
        with authority(backend, runtime) as (env, sql), output_path.open('w') as output:
            env.update(CRITICAL_COMMAND_JOURNAL_DIR=str(critical), DURIS_TLS_PORT=str(tls),
                       DURIS_WEBSOCKET_PORT=str(websocket), MAINTENANCE_STATE_FILE=str(runtime / 'maintenance.state'))

            def boot():
                nonlocal process
                offset = output_path.stat().st_size
                process = subprocess.Popen([str(executable), '-d', str(runtime), str(plain)],
                                           cwd=runtime, env=env, stdout=output, stderr=subprocess.STDOUT)
                deadline = time.monotonic() + 180
                while b'Entering game loop.' not in output_path.read_bytes()[offset:]:
                    assert process.poll() is None and time.monotonic() < deadline, 'server failed to boot'
                    time.sleep(.1)

            def stop():
                # Keep playing descriptors connected through shutdown: disconnecting
                # first would miss the original extract_char/room-transfer bug.
                process.send_signal(signal.SIGTERM)
                process.wait(timeout=60)
                assert process.returncode == 0
                for client in clients:
                    client.close()
                clients.clear()

            def login(name, account):
                client = journey.reconnect_character(plain, expected_room=None, account=account, character=name)
                clients.append(client)
                client.expect('Welcome to Duris', timeout=60)
                client.expect_any(('Pos: standing >', '<>'), timeout=20)
                command(client, 'toggle paging no')
                return client

            def save(client, name):
                client.send('save'); client.expect('Save complete for ' + name + '.', timeout=60)

            def artifact():
                if sql:
                    fields = sql(f'SELECT COALESCE(canonical_item_uid,0),identity_state,owned,loc_type,location,timer_epoch,bind_owner_pid,bind_timer_epoch FROM artifact_domain_state WHERE vnum={ARTIFACT}')
                    return dict(zip(('uid', 'identity', 'owned', 'type', 'location', 'timer', 'soul', 'bind'), map(int, fields.split('\t'))))
                return json.loads(subprocess.check_output([str(inspector), env['FLATFILE_STATE_DIR'], 'artifact-owner', str(ARTIFACT)], text=True))

            def custody(uid):
                if sql:
                    assert sql(f'SELECT owner_type,owner_id,state FROM item_current_owner WHERE item_uid={uid}') == f'1\t{pid}\t1'
                    assert sql(f'SELECT COUNT(*) FROM player_items WHERE pid={pid} AND obj_uid={uid}') == '1'
                else:
                    state = json.loads(subprocess.check_output([str(inspector), env['FLATFILE_STATE_DIR'], 'inspect', str(pid)], text=True))
                    assert sum(item['uid'] == uid for item in state['player_items']) == 1
                    assert all(item['uid'] != uid for item in state['room_items'])

            def settle(predicate, label, timeout=30):
                deadline = time.monotonic() + timeout
                while not predicate():
                    assert time.monotonic() < deadline, label + ': actual=' + repr(artifact())
                    time.sleep(.1)

            def repair_room(god):
                command(god, 'goto 1')
                command(god, 'setbit room here flag NO_MOB 1')
                command(god, 'purge')
                command(god, 'setbit room here flag SAFE 0')
                command(god, 'transfer ' + PLAYER)

            try:
                boot()
                for name, account in ((GOD, GOD_ACCOUNT), (PLAYER, ACCOUNT)):
                    client = journey.MudClient(plain); clients.append(client)
                    journey.create_character(client, expected_room=None, account=account, character=name,
                                             email=name.lower() + '@example.invalid')
                    save(client, name)
                stop()
                if sql:
                    sql(f"UPDATE player_data SET level=62,highest_level=62 WHERE name='{GOD}'")
                    pid = int(sql(f"SELECT pid FROM player_data WHERE name='{PLAYER}'"))
                else:
                    subprocess.run([str(inspector), env['FLATFILE_STATE_DIR'], 'seed-item-operator'], check=True)
                    subprocess.run([str(inspector), env['FLATFILE_STATE_DIR'], 'seed-combat'], check=True)
                    pid = 2
                boot()
                god, player = login(GOD, GOD_ACCOUNT), login(PLAYER, ACCOUNT)
                repair_room(god)
                command(god, 'setbit char ' + PLAYER + ' level 51')
                command(god, 'setbit char ' + PLAYER + ' basehit 100000')
                command(god, 'restore ' + PLAYER)
                assert 'You have created' in command(god, f'load obj {ARTIFACT}')
                command(god, 'give stone ' + PLAYER)
                command(player, 'wear stone')
                assert 'ioun stone' in command(player, 'equipment')
                command(god, f'artifacts timer set {ARTIFACT} 60')
                save(player, PLAYER)
                settle(lambda: artifact()['type'] == 3 and artifact()['location'] == pid, 'initial owner did not persist')
                initial = artifact()
                assert initial['identity'] == 1 and initial['uid'] > 0
                assert initial['timer'] < time.time() + 4000
                stop()
                assert artifact() == initial, 'shutdown changed artifact owner/timer/soul'
                custody(initial['uid'])

                expected = initial
                for stale_type in (() if conflicts_only else (4, 2, 1, 3)):
                    before = artifact()
                    if sql:
                        owned = int(stale_type != 1)
                        sql(f'UPDATE artifact_domain_state SET owned={owned},loc_type={stale_type},location=88 WHERE vnum={ARTIFACT}')
                        sql(f"UPDATE artifacts SET owned='{'Y' if owned else 'N'}',locType={stale_type},location=88 WHERE vnum={ARTIFACT}")
                    else:
                        subprocess.run([str(inspector), env['FLATFILE_STATE_DIR'], 'artifact-owner', str(ARTIFACT), str(stale_type)], check=True, stdout=subprocess.DEVNULL)
                    boot()
                    god, player = login(GOD, GOD_ACCOUNT), login(PLAYER, ACCOUNT)
                    assert 'ioun stone' in command(player, 'equipment')
                    assert 'small wooden mace' in command(player, 'inventory') + command(player, 'equipment')
                    expected = dict(before, owned=1, type=3, location=pid)
                    settle(lambda: artifact() == expected, f'restored tracking did not reconcile: expected={expected}')
                    repair_room(god)
                    command(god, 'restore ' + PLAYER)
                    # This case measures only the elite award. A luck-based random
                    # epic is a separate legitimate award and would also feed it.
                    command(god, 'setbit char ' + PLAYER + ' luck -1000')
                    assert re.search(r'\bLuk:\s+1\b', command(player, 'attributes'))
                    command(god, 'load mob 11')
                    command(god, 'setbit char raoul level 53')
                    command(god, 'setbit char raoul npcact ELITE 1')
                    command(god, 'setbit char raoul hit 1')
                    player.send('kill raoul')
                    player.expect('You have gained 4 epic points.', timeout=60)
                    player.expect('sense of satisfaction', timeout=30)
                    expected['timer'] += 3600
                    settle(lambda: artifact() == expected, f'first award did not feed exactly once: expected={expected}')
                    save(player, PLAYER)
                    custody(initial['uid'])
                    stop()
                    assert artifact() == expected, 'shutdown drifted restored ownership'
                    evidence.append({'stale_type': stale_type, 'after': expected})
                    print(f'PASS {backend}: stale type {stale_type}, login, exactly one feed, connected shutdown', flush=True)
                boot()
                god, player = login(GOD, GOD_ACCOUNT), login(PLAYER, ACCOUNT)
                assert 'ioun stone' in command(player, 'equipment')
                assert artifact() == expected
                custody(initial['uid'])
                stop()
                assert artifact() == expected
                logs = ''.join(p.read_text(errors='replace') for p in (runtime / 'logs').rglob('*') if p.is_file())
                assert 'owner_mismatch' not in logs
                target = ROOT / 'bin/analysis/artifact-owner'
                target.mkdir(parents=True, exist_ok=True)
                (target / (backend + '.json')).write_text(json.dumps(evidence, indent=2) + '\n')
                print(f'PASS {backend}: fresh restart retained UID, timer, soul and custody; no owner mismatch', flush=True)
                if sql:
                    # Reproduce the production conflict in private accounts: two
                    # qualified saved UIDs, legacy holder tracking, no canonical UID.
                    god_pid = int(sql(f"SELECT pid FROM player_data WHERE name='{GOD}'"))
                    old_uid = initial['uid']
                    duplicate_uid = old_uid + 1000000000
                    columns = [line.split('\t')[0] for line in sql('SHOW COLUMNS FROM player_items').splitlines()]
                    columns.remove('id')
                    replacements = {'pid': str(god_pid), 'obj_uid': str(duplicate_uid),
                                    'container_id': 'NULL', 'equip_slot': '-1'}
                    sql('INSERT INTO player_items (' + ','.join(columns) + ') SELECT ' +
                        ','.join(replacements.get(c, c) for c in columns) +
                        f' FROM player_items WHERE obj_uid={old_uid} AND pid={pid}')
                    sql('INSERT INTO item_current_owner '
                        '(item_uid,root_item_uid,parent_item_uid,owner_type,owner_id,owner_context_id,item_revision,vnum,state) '
                        f'VALUES({duplicate_uid},{duplicate_uid},NULL,1,{god_pid},0,1,{ARTIFACT},1)')
                    sql(f'UPDATE artifact_domain_state SET canonical_item_uid=NULL,identity_state=0,rejected_item_uids=NULL WHERE vnum={ARTIFACT}')
                    boot()
                    player = login(PLAYER, ACCOUNT)
                    assert 'ioun stone' in command(player, 'equipment')
                    settle(lambda: artifact() == expected, 'legacy conflict failed to recover tracked holder')
                    assert sql(f'SELECT rejected_item_uids FROM artifact_domain_state WHERE vnum={ARTIFACT}') == str(duplicate_uid)
                    save(player, PLAYER)
                    stop()
                    # Expire the canonical holder while offline, then restart with
                    # the rejected payload still saved under the other account.
                    sql(f'UPDATE artifact_domain_state SET timer_epoch=1,loc_type=4,location=88 WHERE vnum={ARTIFACT}')
                    sql(f'UPDATE artifacts SET timer=FROM_UNIXTIME(1),locType=4,location=88 WHERE vnum={ARTIFACT}')
                    boot()
                    # The first scheduled expiry runs 35 seconds after boot.
                    settle(lambda: artifact()['identity'] == 2, 'offline recovered identity did not expire', timeout=90)
                    assert artifact()['uid'] == old_uid
                    stop()
                    assert sql(f'SELECT COUNT(*) FROM player_items WHERE obj_uid={duplicate_uid}') == '1'
                    boot()
                    god = login(GOD, GOD_ACCOUNT)
                    assert artifact()['identity'] == 2
                    assert 'staff review' not in bytes(god.transcript).decode(errors='replace')
                    save(god, GOD)
                    assert sql(f'SELECT COUNT(*) FROM player_items WHERE obj_uid={duplicate_uid}') == '0'
                    assert 'You have created' in command(god, f'load obj {ARTIFACT}')
                    settle(lambda: artifact()['identity'] == 1 and artifact()['uid'] not in (old_uid, duplicate_uid),
                           'retired copies blocked a fresh generation')
                    generation = artifact()['uid']
                    save(god, GOD)
                    stop()
                    boot()
                    god = login(GOD, GOD_ACCOUNT)
                    assert artifact()['uid'] == generation
                    assert sql(f'SELECT rejected_item_uids FROM artifact_domain_state WHERE vnum={ARTIFACT}') == ','.join(map(str, sorted((old_uid, duplicate_uid))))
                    stop()
                    logs = ''.join(p.read_text(errors='replace') for p in (runtime / 'logs').rglob('*') if p.is_file())
                    assert 'canonical_identity_unavailable' not in logs
                    print('PASS mariadb: automatic conflict recovery, offline expiry with saved duplicates, automatic duplicate cleanup, fresh generation and repeated restart', flush=True)
            except Exception:
                target = ROOT / 'bin/analysis/artifact-owner' / (backend + '-failure-' + str(time.time_ns()))
                target.mkdir(parents=True)
                shutil.copy2(output_path, target / 'server.out')
                shutil.copytree(runtime / 'logs', target / 'logs')
                for index, client in enumerate(clients):
                    (target / f'client-{index}.txt').write_bytes(bytes(client.transcript))
                print(f'Failure evidence: {target}', flush=True)
                raise
            finally:
                for client in clients:
                    client.close()
                if process and process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=60)
                    except subprocess.TimeoutExpired:
                        process.kill(); process.wait(timeout=10)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--backend', choices=('flatfile', 'mariadb'), default='flatfile')
    parser.add_argument('--server', type=Path)
    parser.add_argument('--conflicts-only', action='store_true', help='run the legacy duplicate recovery journey without repeating stale-owner feeding cases')
    args = parser.parse_args()
    assert not args.conflicts_only or args.backend == 'mariadb'
    (ROOT / 'bin/tests').mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='artifact-owner-build-', dir=ROOT / 'bin/tests') as temporary:
        build = Path(temporary)
        inspector = build / 'inspector'
        if args.backend == 'flatfile':
            subprocess.run(['python3', 'tests/async/test_flatfile_player_repository.py', '--build-inspector', str(inspector)], check=True)
        if args.server:
            binary = args.server.resolve()
        else:
            assert args.backend == 'flatfile', 'pass a MariaDB binary with --server'
            binary = journey.build_flatfile_server(build / 'server')
        run(binary, args.backend, inspector, args.conflicts_only)
