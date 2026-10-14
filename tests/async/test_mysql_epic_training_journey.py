#!/usr/bin/env python3
"""Actual epic teacher boundaries, mastery and derived HP on disposable MariaDB."""
import argparse
import hashlib
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
PLAYER, ACCOUNT = 'Trainpupil', 'Trainplayer'
GOD, GOD_ACCOUNT = 'Trainwarden', 'Trainstaff'
TOUGHNESS = 1230


def stats(text):
    hp = re.search(r'Hit points:\s*(\d+)\((\d+)\)', text)
    epics = re.search(r'Epic points(?:\(total\))?:\s*(\d+)', text)
    coins = re.search(r'Coins carried:\s*(\d+) platinum\s+(\d+) gold\s+(\d+) silver\s+(\d+) copper', text)
    assert hp and epics and coins, text
    return {'hp': int(hp[1]), 'max_hp': int(hp[2]), 'epics': int(epics[1]),
            'coins': sum(int(value) * scale for value, scale in zip(coins.groups(), (1000, 100, 10, 1)))}


def run(binary):
    (ROOT / 'bin/tests').mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='epic-training-', dir=ROOT / 'bin/tests') as temporary:
        runtime = Path(temporary)
        _, critical, output_path = setup_run_root(runtime)
        (runtime / 'help').symlink_to(ROOT / 'help', target_is_directory=True)
        (runtime / 'bin/server').mkdir(parents=True)
        executable = runtime / 'bin/server/dms'
        shutil.copy2(binary, executable)
        executable.chmod(0o700)
        plain, tls, websocket = journey.available_ports()
        clients = []
        process = None
        evidence = {'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(), 'purchases': []}
        with authority('mariadb', runtime) as (env, sql), output_path.open('w') as output:
            env.update(CRITICAL_COMMAND_JOURNAL_DIR=str(critical), DURIS_TLS_PORT=str(tls),
                       DURIS_WEBSOCKET_PORT=str(websocket),
                       MAINTENANCE_STATE_FILE=str(runtime / 'maintenance.state'))

            def boot():
                nonlocal process
                offset = output_path.stat().st_size
                process = subprocess.Popen([str(executable), '-d', str(runtime), str(plain)],
                                           cwd=runtime, env=env, stdout=output, stderr=subprocess.STDOUT)
                deadline = time.monotonic() + 180
                while b'Entering game loop.' not in output_path.read_bytes()[offset:]:
                    assert process.poll() is None and time.monotonic() < deadline, 'training world failed to boot'
                    time.sleep(.1)

            def stop():
                for client in clients:
                    client.close()
                clients.clear()
                process.send_signal(signal.SIGTERM)
                process.wait(timeout=60)
                assert process.returncode == 0

            def login(name, account):
                client = journey.reconnect_character(plain, expected_room=None, account=account, character=name)
                clients.append(client)
                client.expect('Welcome to Duris', timeout=60)
                client.expect_any(('Pos: standing >', '<>'), timeout=20)
                command(client, 'toggle paging no')
                return client

            def saved_skill():
                value = sql(f"SELECT learned,taught FROM player_skills WHERE pid=(SELECT pid FROM player_data WHERE name='{PLAYER}') AND skill_id={TOUGHNESS}")
                return tuple(map(int, value.split('\t'))) if value else (0, 0)

            def saved_player():
                return sql(f"SELECT level,epics,platinum,gold,silver,copper,hit_diff FROM player_data WHERE name='{PLAYER}'")

            def save():
                player.send('save')
                player.expect('Save complete for ' + PLAYER + '.', timeout=60)

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
                sql(f"UPDATE player_data SET level=62,highest_level=62 WHERE name='{GOD}'")
                sql(f"UPDATE player_data SET level=29,highest_level=31,epics=10000,platinum=12000,gold=0,silver=0,copper=0 WHERE name='{PLAYER}'")
                sql(f"DELETE FROM player_skills WHERE pid=(SELECT pid FROM player_data WHERE name='{PLAYER}') AND skill_id={TOUGHNESS}")
                boot()
                god, player = login(GOD, GOD_ACCOUNT), login(PLAYER, ACCOUNT)
                command(god, 'goto 1')
                command(god, 'setbit room here flag SAFE 0')
                command(god, 'setbit room here flag NO_HEAL 1')
                command(god, 'transfer ' + PLAYER)
                command(god, 'load mob 80862')
                assert 'butcher' in command(player, 'look'), 'the actual toughness teacher is absent'
                player.socket.sendall(bytes([255, 253, 201]))  # negotiate GMCP
                before = stats(command(player, 'score'))
                refused = command(player, 'practice toughness')
                assert 'must reach level 30' in refused, refused
                assert stats(refused) == before
                save()
                assert saved_skill() == (0, 0)
                evidence['below_minimum'] = before
                print('PASS actual teacher at 29: refusal preserves skill and both balances', flush=True)

                for level, learned, missing in ((30, 10, 0), (31, 20, 30)):
                    command(god, f'setbit char {PLAYER} level {level}')
                    initial = stats(command(player, 'score'))
                    command(god, f'setbit char {PLAYER} hit {initial["max_hp"] - missing}')
                    before = stats(command(player, 'score'))
                    assert before['max_hp'] - before['hp'] == missing, before
                    packet_start = len(player.transcript)
                    purchased = command(player, 'practice toughness')
                    after = stats(purchased)
                    assert 'improve your mastery of' in purchased, purchased
                    assert after['epics'] == before['epics'] - 150
                    assert after['coins'] == before['coins'] - 1000000
                    save()
                    assert saved_skill() == (learned, learned), saved_skill()
                    evidence['purchases'].append({'level': level, 'before': before, 'after': after, 'learned': learned})
                    assert after['max_hp'] == before['max_hp'] + 10, evidence['purchases'][-1]
                    assert after['max_hp'] - after['hp'] == missing, evidence['purchases'][-1]
                    packets = re.findall(rb'\xff\xfa\xc9Char\.Vitals (.*?)\xff\xf0',
                                         bytes(player.transcript[packet_start:]), re.S)
                    assert packets, 'training did not publish GMCP vitals'
                    vitals = json.loads(packets[-1])
                    assert vitals['maxHp'] == after['max_hp'] and vitals['hp'] == after['hp'], vitals
                    time.sleep(1)
                    assert stats(command(player, 'score')) == after, 'HP changed on a later pulse'
                    # setbit schedules the existing affect refresh even for an unchanged hit value.
                    for _ in range(2):
                        command(god, f'setbit char {PLAYER} hit {after["hp"]}')
                        assert stats(command(player, 'score')) == after, 'refresh stacked the toughness bonus'
                    print(f'PASS actual teacher at {level}: one charge, learned {learned}, prompt/GMCP HP +10, missing HP {missing}, stable refreshes', flush=True)

                command(god, f"setbit char {PLAYER} skill 'toughness' 95")
                command(god, f"setbit char {PLAYER} taught 'toughness' 95")
                before = stats(command(player, 'score'))
                mastered = command(player, 'practice toughness')
                after = stats(mastered)
                assert 'You have mastered' in mastered, mastered
                assert after['epics'] == before['epics'] - 600
                assert after['coins'] == before['coins'] - 4000000
                assert after['max_hp'] == before['max_hp'] + 5
                save()
                assert saved_skill() == (100, 100)
                repeated = command(player, 'practice toughness')
                assert 'already mastered this skill' in repeated, repeated
                assert stats(repeated) == after
                save()
                before_restart = saved_player()
                evidence['mastery'] = after
                stop()
                boot()
                player = login(PLAYER, ACCOUNT)
                restored = stats(command(player, 'score'))
                assert restored['max_hp'] == after['max_hp'], (restored, after)
                assert restored['max_hp'] - restored['hp'] == 30, restored
                assert restored['epics'] == after['epics'] and restored['coins'] == after['coins']
                assert saved_skill() == (100, 100)
                assert saved_player() == before_restart
                print('PASS mastery/at-cap refusal and clean restart preserve skill, balances and derived HP', flush=True)

                # The Illithid HP formula has a separate base-plus-skill branch.
                god = login(GOD, GOD_ACCOUNT)
                command(god, 'goto 1')
                command(god, 'setbit room here flag SAFE 0')
                command(god, 'setbit room here flag NO_HEAL 1')
                command(god, 'transfer ' + PLAYER)
                command(god, 'load mob 80862')
                command(god, f'setbit char {PLAYER} class psionicist')
                command(god, f'setbit char {PLAYER} race illithid')
                command(god, f"setbit char {PLAYER} skill 'toughness' 0")
                command(god, f"setbit char {PLAYER} taught 'toughness' 0")
                player.socket.sendall(bytes([255, 253, 201]))
                for learned, missing in ((10, 0), (20, 30)):
                    initial = stats(command(player, 'score'))
                    command(god, f'setbit char {PLAYER} hit {initial["max_hp"] - missing}')
                    before = stats(command(player, 'score'))
                    packet_start = len(player.transcript)
                    purchased = command(player, 'practice toughness')
                    assert 'improve your mastery of' in purchased, purchased
                    after = stats(purchased)
                    assert after['max_hp'] == before['max_hp'] + 5, (before, after)
                    assert after['max_hp'] - after['hp'] == missing, (before, after)
                    assert after['epics'] == before['epics'] - 150
                    assert after['coins'] == before['coins'] - 1000000
                    packets = re.findall(rb'\xff\xfa\xc9Char\.Vitals (.*?)\xff\xf0',
                                         bytes(player.transcript[packet_start:]), re.S)
                    assert packets, 'Illithid training did not publish GMCP vitals'
                    vitals = json.loads(packets[-1])
                    assert vitals['maxHp'] == after['max_hp'] and vitals['hp'] == after['hp'], vitals
                    for _ in range(2):
                        command(god, f'setbit char {PLAYER} hit {after["hp"]}')
                        assert stats(command(player, 'score')) == after
                    save()
                    assert saved_skill() == (learned, learned)
                    evidence['purchases'].append({'race': 'illithid', 'before': before, 'after': after, 'learned': learned})
                before_restart = saved_player()
                stop()
                boot()
                player = login(PLAYER, ACCOUNT)
                assert stats(command(player, 'score')) == after
                assert saved_skill() == (20, 20)
                assert saved_player() == before_restart
                stop()
                target = ROOT / 'bin/analysis/epic-training'
                target.mkdir(parents=True, exist_ok=True)
                (target / 'journey.json').write_text(json.dumps(evidence, indent=2) + '\n')
                print('PASS Illithid full/injured HP, repeated refreshes, GMCP and clean restart', flush=True)
            except Exception as error:
                target = ROOT / 'bin/analysis/epic-training' / f'failure-{time.time_ns()}'
                target.mkdir(parents=True)
                (target / 'evidence.json').write_text(json.dumps(evidence, indent=2) + '\n')
                shutil.copy2(output_path, target / 'server.out')
                shutil.copytree(runtime / 'logs', target / 'logs')
                traces = '\n'.join(bytes(client.transcript[-5000:]).decode(errors='replace') for client in clients)
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
        print('epic training journey skipped: TEST_DB_HOST is not set')
    else:
        run(args.server.resolve())
