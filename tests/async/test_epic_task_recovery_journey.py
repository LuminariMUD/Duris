#!/usr/bin/env python3
"""Real stone award, saved pending task and scheduled recovery on disposable MariaDB."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time

import test_flatfile_combat_journey as journey
from test_flight_network_journey import authority, command
from run_world_quest_dual_backend import setup_run_root

ROOT = journey.ROOT
sys.path.insert(0, str(ROOT / "scripts"))
import epic_task_seed

PLAYER, ACCOUNT = 'Taskpupil', 'Taskplayer'
GOD, GOD_ACCOUNT = 'Taskwarden', 'Taskstaff'


def catalogue_offset(plain, tls):
    # Choose ordinary listener ports whose existing scheduler offset is short.
    # The production binary, cadence and clock are unchanged by this test.
    seed = (plain << 32) | tls
    value = 1469598103934665603
    for shift in range(0, 64, 8):
        value = ((value ^ ((seed >> shift) & 255)) * 1099511628211) & ((1 << 64) - 1)
    return ((value ^ 3) * 1099511628211 & ((1 << 64) - 1)) % 14400


class AlternativeRoll(Exception):
    pass


def run(binary):
    (ROOT / 'bin/tests').mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='epic-task-', dir=ROOT / 'bin/tests') as temporary:
        runtime = Path(temporary)
        _, critical, output_path = setup_run_root(runtime)
        (runtime / 'help').symlink_to(ROOT / 'help', target_is_directory=True)
        (runtime / 'bin/server').mkdir(parents=True)
        executable = runtime / 'bin/server/dms'
        shutil.copy2(binary, executable)
        properties = runtime / 'lib/duris.properties'
        text = properties.read_text().replace('camp.timer=9.000', 'camp.timer=1.000')
        text = re.sub(r'^epic.errandStep=.*$', 'epic.errandStep=400.000', text, flags=re.M)
        properties.write_text(text)
        for _ in range(1000):
            plain, tls, websocket = journey.available_ports()
            offset = catalogue_offset(plain, tls)
            if 80 <= offset <= 160:
                break
        else:
            raise AssertionError('could not reserve a short natural catalogue schedule')
        clients = []
        process = None
        evidence = {'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
                    'task_step': 400, 'catalogue_offset_ticks': offset}
        with authority('mariadb', runtime) as (env, sql), output_path.open('w') as output:
            env.update(CRITICAL_COMMAND_JOURNAL_DIR=str(critical), DURIS_TLS_PORT=str(tls),
                       DURIS_WEBSOCKET_PORT=str(websocket),
                       MAINTENANCE_STATE_FILE=str(runtime / 'maintenance.state'))

            def boot():
                nonlocal process
                start = output_path.stat().st_size
                process = subprocess.Popen([str(executable), '-d', str(runtime), str(plain)],
                                           cwd=runtime, env=env, stdout=output, stderr=subprocess.STDOUT)
                deadline = time.monotonic() + 180
                while b'Entering game loop.' not in output_path.read_bytes()[start:]:
                    assert process.poll() is None and time.monotonic() < deadline, 'task world failed to boot'
                    time.sleep(.1)

            def stop():
                for client in clients:
                    client.close()
                clients.clear()
                process.send_signal(signal.SIGTERM)
                process.wait(timeout=60)
                assert process.returncode == 0

            def create(name, account):
                client = journey.MudClient(plain)
                clients.append(client)
                journey.create_character(client, expected_room=None, account=account,
                                         character=name, email=name.lower() + '@example.invalid')
                command(client, 'toggle paging no')
                return client

            def login(name=PLAYER, account=ACCOUNT):
                client = journey.reconnect_character(plain, expected_room=None, account=account, character=name)
                clients.append(client)
                client.expect('Welcome to Duris', timeout=60)
                client.expect_any(('Pos: standing >', '<>'), timeout=20)
                command(client, 'toggle paging no')
                return client

            def save(client, name=PLAYER):
                client.send('save')
                client.expect('Save complete for ' + name + '.', timeout=60)

            def task_rows(name=PLAYER):
                return sql(f"SELECT type,modifier FROM player_affects WHERE pid=(SELECT pid FROM player_data "
                           f"WHERE name='{name}') AND type IN (2022,2128) ORDER BY type")

            def reward_rows():
                return sql(f"SELECT delta,balance_after,reason_type,reason_id FROM epic_ledger WHERE pid="
                           f"(SELECT pid FROM player_data WHERE name='{PLAYER}') ORDER BY epic_revision")

            try:
                boot()
                god = create(GOD, GOD_ACCOUNT)
                save(god, GOD)
                stop()
                sql(f"UPDATE player_data SET level=62,highest_level=62 WHERE name='{GOD}'")
                sql("UPDATE zones SET epic_payout=400,suggested_group_size=100,alignment=0 WHERE number=14")
                boot()
                god = login(GOD, GOD_ACCOUNT)
                player = create(PLAYER, ACCOUNT)
                save(player)
                assert sql('SELECT COUNT(*) FROM zones WHERE task_zone=1') == '0'
                for action in ('goto 1482', 'purge', 'setbit room here flag SAFE 1',
                               'transfer ' + PLAYER):
                    command(god, action)
                player.send('touch stone')
                outcome, reply_text = player.expect_any(('You have gained 400 epic points.',
                                                         'reward service is unavailable'), timeout=60)
                assert outcome.startswith('You have gained'), reply_text + command(god, 'world persistence')
                reply, _ = player.expect_any(('assigned automatically when task data is available',
                                               'spill the', 'convert it!'), timeout=30)
                if not reply.startswith('assigned automatically'):
                    raise AlternativeRoll('valid 5% alternative roll; rerun with a new disposable character')
                save(player)
                assert task_rows() == '2128\t0', task_rows()
                before = reward_rows()
                assert before == '400\t400\t1\t14', before
                status = command(god, 'world persistence')
                assert 'catalog_ready=0 zones=0 last_refresh=empty_task_flags' in status, status
                assert 'pending=1 pending_reads_unavailable=0' in status, status
                print('PASS first-session stone: 400 epics, one pending task, player reads ready', flush=True)

                # Camp is the ordinary saved-rent path and must preserve the obligation.
                # Leave the hostile stone room before restarting its natural NPC resets.
                command(god, 'goto 22800')
                command(god, 'setbit room here sect field')
                command(god, 'transfer ' + PLAYER)
                player.send('camp')
                player.expect('ACCOUNT MENU', timeout=60)
                player.close(); clients.remove(player)
                player = login()
                save(player)
                assert task_rows() == '2128\t0' and reward_rows() == before
                print('PASS saved pending task and reward survive camp/relogin', flush=True)
                stop()
                boot()
                assert task_rows() == '2128\t0'
                sql(epic_task_seed.apply_sql(epic_task_seed.roster(), env['DB_NAME']))
                player = login()
                # The real scheduled worker reads SQL and the normal player pulse retries.
                player.expect('have sent you to seek out', timeout=120)
                save(player)
                rows = task_rows().split('\t')
                assert rows[0] == '2022' and len(rows) == 2, rows
                assigned = int(rows[1])
                assert assigned in epic_task_seed.roster() and assigned != 14
                assert reward_rows() == before
                evidence.update(assigned_zone=assigned, reward=before, pending_survived_rent_restart=True)
                print('PASS scheduled SQL recovery assigns one uncompleted zone without a second reward', flush=True)
                stop()
                boot()
                player = login()
                save(player)
                assert task_rows() == f'2022\t{assigned}' and reward_rows() == before
                assert re.search(r'Epic points(?:\(total\))?:\s*400\b', command(player, 'score'))
                print('PASS active task and original 400 epics survive another clean restart', flush=True)
                fresh = create('Taskfresh', 'Freshacct')
                save(fresh, 'Taskfresh')
                stop()

                # Controlled history fixtures cover the other load/filter boundaries:
                # a pending player with zero completions and one with the entire roster.
                flags = sql(f"SELECT flags FROM player_affects WHERE pid=(SELECT pid FROM player_data "
                            f"WHERE name='{PLAYER}') AND type=2022")
                sql(f"DELETE FROM player_affects WHERE pid=(SELECT pid FROM player_data "
                    f"WHERE name='{PLAYER}') AND type=2022")
                sql(f"INSERT INTO player_affects(pid,type,duration,flags,modifier) "
                    f"SELECT pid,2128,-1,{int(flags)},0 FROM player_data WHERE name IN ('{PLAYER}','Taskfresh')")
                completed = ' UNION ALL '.join(f'SELECT {n} AS number' for n in epic_task_seed.roster())
                sql(f"INSERT INTO epic_gain(pid,time,type,type_id,epics) SELECT p.pid,NOW(),0,z.number,0 "
                    f"FROM player_data p CROSS JOIN ({completed}) z WHERE p.name='{PLAYER}'")
                boot()
                player, fresh = login(), login('Taskfresh', 'Freshacct')
                deadline = time.monotonic() + 120
                while True:
                    full = command(player, 'score')
                    empty = command(fresh, 'score')
                    if 'Current task: spill enemy blood' in full and 'Current task: find runestone' in empty:
                        break
                    assert time.monotonic() < deadline, full + empty
                    time.sleep(1)
                save(player); save(fresh, 'Taskfresh')
                assert task_rows() == '2022\t10000000'
                assert int(task_rows('Taskfresh').split('\t')[1]) in epic_task_seed.roster()
                assert reward_rows() == before
                evidence['connected_zero_and_exhausted_history'] = True
                stop()
                print('PASS connected zero/some/all completion histories select zone/exclude/spill deliberately', flush=True)
                target = ROOT / 'bin/analysis/epic-task-journey'
                target.mkdir(parents=True, exist_ok=True)
                (target / 'journey.json').write_text(json.dumps(evidence, indent=2) + '\n')
            except AlternativeRoll:
                raise
            except Exception as error:
                target = ROOT / 'bin/analysis/epic-task-journey' / f'failure-{time.time_ns()}'
                target.mkdir(parents=True)
                shutil.copy2(output_path, target / 'server.out')
                shutil.copytree(runtime / 'logs', target / 'logs')
                traces = '\n'.join(bytes(c.transcript[-6000:]).decode(errors='replace') for c in clients)
                raise AssertionError(f'{error}\nEvidence: {target}\n{traces}') from error
            finally:
                for client in clients:
                    client.close()
                if process and process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=30)
                    except subprocess.TimeoutExpired:
                        process.kill(); process.wait(timeout=10)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--server', type=Path, default=ROOT / 'bin/server/dms_new')
    args = parser.parse_args()
    if not os.getenv('TEST_DB_HOST'):
        raise SystemExit('Run under tests/async/with_disposable_mariadb.sh; a disposable DB is required')
    for attempt in range(5):
        try:
            run(args.server.resolve())
            break
        except AlternativeRoll as error:
            print(error, flush=True)
    else:
        raise AssertionError('all five independent assignments took the intentional alternative branch')
