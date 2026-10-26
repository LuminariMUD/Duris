#!/usr/bin/env python3
"""Full-world Nexus placement, mortal capture and cold-restart persistence on a disposable DB."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import signal
import struct
import subprocess
import tempfile
import time

import test_flatfile_combat_journey as journey
from test_flight_network_journey import authority, command
from test_mysql_epic_training_journey import stats
from run_world_quest_dual_backend import setup_run_root

ROOT = journey.ROOT
GOD, GOOD, EVIL = 'Stonewarden', 'Stonegood', 'Stoneevil'
ACCOUNTS = {GOD: 'Stoneadmin', GOOD: 'Stonegooda', EVIL: 'Stoneevila'}


def run(binary):
    (ROOT / 'bin/tests').mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='nexus-journey-', dir=ROOT / 'bin/tests') as temporary:
        runtime = Path(temporary)
        _, critical, output_path = setup_run_root(runtime)
        (runtime / 'help').symlink_to(ROOT / 'help', target_is_directory=True)
        (runtime / 'bin/server').mkdir(parents=True)
        executable = runtime / 'bin/server/dms'
        shutil.copy2(binary, executable)
        executable.chmod(0o700)
        properties = runtime / 'lib/duris.properties'
        properties.write_text(properties.read_text().replace(
            'nexusStones.touchTimerSecs=300.000', 'nexusStones.touchTimerSecs=5.000').replace(
            'nexusStones.turnTimerSecs=3600.000', 'nexusStones.turnTimerSecs=6.000'))
        plain, tls, websocket = journey.available_ports()
        clients = []
        process = None
        guardian_diagnostic = ''
        evidence = {'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
                    'fixture_touch_seconds': 5, 'fixture_turn_seconds': 6,
                    'guardian_combat_fixture': {'level': 1, 'hit': 1, 'armor': 1000, 'agility': 1},
                    'attacker_fixture_hitroll': 100, 'attacker_fixture_damroll': 100,
                    'attacker_fixture_unarmed_skill': 100, 'captures': [], 'cargo_sales': []}
        with authority('mariadb', runtime) as (env, sql), output_path.open('w') as output:
            env.update(CRITICAL_COMMAND_JOURNAL_DIR=str(critical), DURIS_TLS_PORT=str(tls),
                       DURIS_WEBSOCKET_PORT=str(websocket),
                       MAINTENANCE_STATE_FILE=str(runtime / 'maintenance.state'))

            def boot():
                nonlocal process
                offset = output_path.stat().st_size
                log_offsets = {path: path.stat().st_size for path in (runtime / 'logs/log').glob('*')
                               if path.is_file()}
                process = subprocess.Popen([str(executable), '-d', str(runtime), str(plain)],
                                           cwd=runtime, env=env, stdout=output, stderr=subprocess.STDOUT)
                deadline = time.monotonic() + 180
                while b'Entering game loop.' not in output_path.read_bytes()[offset:]:
                    assert process.poll() is None and time.monotonic() < deadline, 'Nexus world failed to boot'
                    time.sleep(.1)
                logs = '\n'.join(path.read_bytes()[log_offsets.get(path, 0):].decode(errors='replace')
                                 for path in (runtime / 'logs/log').glob('*') if path.is_file())
                ship_rooms = re.findall(r'Nexus Stone \(3\) loaded in \[(\d+)\]', logs)
                assert ship_rooms, 'Enlil did not load on this boot'
                assert 'Nexus Stone (1) loaded in [130199]' in logs
                return int(ship_rooms[-1])

            def stop():
                nonlocal process
                for client in clients:
                    client.close()
                clients.clear()
                process.send_signal(signal.SIGTERM)
                process.wait(timeout=60)
                assert process.returncode == 0
                process = None

            def login(name):
                client = journey.reconnect_character(plain, expected_room=None,
                                                       account=ACCOUNTS[name], character=name)
                clients.append(client)
                client.expect('Welcome to Duris', timeout=60)
                client.expect_any(('Pos: standing >', '<>'), timeout=20)
                command(client, 'toggle paging no')
                return client

            def state():
                return sql('SELECT id,align,last_touched_at FROM nexus_stones ORDER BY id')

            def wait_align(stone_id, align):
                deadline = time.monotonic() + 60
                while sql(f'SELECT align FROM nexus_stones WHERE id={stone_id}') != str(align):
                    assert time.monotonic() < deadline, 'Nexus alignment did not persist'
                    time.sleep(.1)

            try:
                first_ship_room = boot()
                for name in (GOD, GOOD, EVIL):
                    client = journey.MudClient(plain)
                    clients.append(client)
                    journey.create_character(client, expected_room=None, account=ACCOUNTS[name],
                                             character=name, email=name.lower() + '@example.invalid')
                    client.send('save')
                    client.expect('Save complete for ' + name + '.', timeout=60)
                stop()
                sql(f"UPDATE player_data SET level=62,highest_level=62 WHERE name='{GOD}'")
                for name in (GOOD, EVIL):
                    sql(f"UPDATE player_data SET level=51,highest_level=51,epics=1000 "
                        f"WHERE name='{name}'")
                    sql("INSERT INTO player_skills(pid,skill_id,learned,taught) "
                        f"SELECT pid,1033,100,100 FROM player_data WHERE name='{name}' "
                        "ON DUPLICATE KEY UPDATE learned=100,taught=100")
                # Creation uses good-side humans. Arrange the synthetic evil account
                # before gameplay so both initial login and restart use normal admission.
                sql(f"UPDATE player_data SET racewar=2 WHERE name='{EVIL}'")
                sql(f"UPDATE accounts SET last_good_char=NULL WHERE account_name='{ACCOUNTS[EVIL]}'")
                base_stats_query = ("SELECT name,base_str,base_dex,base_agi,base_con,base_pow,"
                                    "base_int,base_wis,base_cha,base_kar,base_luk FROM player_data "
                                    f"WHERE name IN ('{GOOD}','{EVIL}') ORDER BY name")
                base_stats = sql(base_stats_query)
                boon_ids = {}
                for stone_id, side in ((1, 1), (3, 2)):
                    boon_ids[stone_id] = int(sql(
                        "INSERT INTO boons(time,duration,racewar,type,opt,criteria,bonus,author,active) "
                        f"VALUES(UNIX_TIMESTAMP(),-1,{side},10,9,{stone_id},7,'nexus-fixture',1); SELECT LAST_INSERT_ID()"))
                    name = GOOD if side == 1 else EVIL
                    sql("INSERT INTO boons_progress(boonid,pid,counter) "
                        f"SELECT {boon_ids[stone_id]},pid,0.5 FROM player_data WHERE name='{name}'")
                    sql("INSERT INTO boons_shop(pid,points,stats) "
                        f"SELECT pid,7,3 FROM player_data WHERE name='{name}' "
                        "ON DUPLICATE KEY UPDATE points=7,stats=3")
                ship_room = boot()
                god, good, evil = login(GOD), login(GOOD), login(EVIL)
                command(good, 'remove all')
                command(evil, 'remove all')
                command(god, 'goto 559633')
                for name, client in ((GOOD, good), (EVIL, evil)):
                    command(god, 'transfer ' + name)
                    command(god, f'setbit char {name} platinum 30000')
                    command(god, f'setbit char {name} align -1000')
                    enabled = command(client, 'toggle boon yes')
                    assert 'Divine Boons apply automatically.' in enabled, enabled
                    bought = command(client, f'buy hull 3 {name} Trader')
                    assert 'committed hull purchase' in bought, bought
                    command(god, f'setbit ship {name} frags 1000')
                listed = command(god, 'nexus')
                assert 'Marduk' in listed and 'Enlil' in listed
                assert 'Antu' not in listed and 'Ningishzida' not in listed
                assert sql('SELECT GROUP_CONCAT(id ORDER BY id) FROM nexus_stones') == '1,3'
                command(god, 'goto 130399')
                assert 'The nexus stone of Enlil stands here.' not in command(god, 'look')

                for stone_id, stone_name, room, player_name, player, side in (
                    (1, 'Marduk', 130199, GOOD, good, 1),
                    (3, 'Enlil', ship_room, EVIL, evil, -1),
                ):
                    command(god, f'goto {room}')
                    look = command(god, 'look')
                    assert look.count(f'The nexus stone of {stone_name} stands here.') == 1, look
                    command(god, f'setbit char {player_name} basehit 100000')
                    command(god, 'restore ' + player_name)
                    # Exercise real combat/death without requiring a raid to kill
                    # the production-strength boss; later spawns retain its template.
                    command(god, 'setbit char guardian aggro AGGR_ALL 0')
                    command(god, 'setbit char guardian level 1')
                    command(god, 'setbit char guardian ac 1000')
                    command(god, 'setbit char guardian agi 1')
                    command(god, 'setbit char guardian hit 1')
                    command(god, f'setbit char {player_name} hitrol 100')
                    command(god, f'setbit char {player_name} damrol 100')
                    guardian_diagnostic = command(god, 'stat mob guardian')
                    command(god, 'transfer ' + player_name)
                    blocked = command(player, 'touch stone')
                    assert 'strange field of energy prevents' in blocked, blocked
                    player.send('kill guardian')
                    player.expect('You receive your share of experience.', timeout=60)
                    assert 'dim mass of energy swirls' not in command(god, 'look')
                    command(god, f"affectpurge {player_name} 'blindness'")
                    command(god, 'restore ' + player_name)
                    before = stats(command(player, 'score'))['epics']
                    for touch in (1, 2, 3):
                        touch_start = len(player.transcript)
                        player.send('touch stone')
                        player.expect('very soul being siphoned', timeout=20)
                        command(god, 'restore ' + player_name)
                        wait_align(stone_id, side * touch)
                        if touch == 1:
                            blocked = command(player, 'touch stone')
                            assert 'touch is repulsed' in blocked, blocked
                        # Cooldowns advance in game-loop pulses, not wall time.
                        # A command fence may already have consumed the notification.
                        if b'starts to hum wildly!' not in player.transcript[touch_start:]:
                            player.expect('starts to hum wildly!', timeout=60)
                    after = stats(command(player, 'score'))['epics']
                    assert after > before, 'capture did not award epics'
                    # Cutover retains legacy balances/progress and closes new awards.
                    assert sql("SELECT counter=0.5 FROM boons_progress WHERE boonid="
                               f"{boon_ids[stone_id]} AND pid=(SELECT pid FROM player_data "
                               f"WHERE name='{player_name}')") == '1'
                    assert sql("SELECT points,stats FROM boons_shop WHERE pid=(SELECT pid "
                               f"FROM player_data WHERE name='{player_name}')") == '7\t3'
                    command(god, 'purge guardian')
                    same_side = command(player, 'touch stone')
                    assert 'The stone is indifferent to your touch.' in same_side, same_side
                    player.send('save')
                    player.expect('Save complete for ' + player_name + '.', timeout=60)
                    evidence['captures'].append({'stone': stone_id, 'align': side * 3,
                                                 'epic_delta': after - before})
                    print(f'PASS {stone_name}: mortal guardian defeat, touch cooldown, full capture and epic award', flush=True)

                # Real shipwright purchases and settlements on both racewar sides.
                # Each sale reports its pre-Nexus price, so changing market prices
                # do not make this a comparison against a stale quote.
                command(god, 'goto 559633')
                rate = struct.unpack('f', struct.pack('f', .110))[0]
                for name, client, owned in ((GOOD, good, False), (EVIL, evil, True)):
                    command(god, 'transfer ' + name)
                    for commodity in ('cargo', 'contraband'):
                        deadline = time.monotonic() + 240
                        while True:
                            bought = command(client, f'buy {commodity} 1')
                            if 'You buy 1 crates' in bought:
                                break
                            assert 'currently being worked on' in bought and time.monotonic() < deadline, bought
                            time.sleep(1)
                        before = stats(command(client, 'score'))['coins']
                        sold = command(client, 'sell ' + commodity)
                        quoted = re.search(r'You sell .*? for (.*?), making', sold, re.S)
                        assert quoted, sold
                        denominations = {'platinum': 1000, 'gold': 100, 'silver': 10, 'copper': 1}
                        base = sum(int(number.replace(',', '')) * denominations[coin]
                                   for number, coin in re.findall(r'([\d,]+)\s+(platinum|gold|silver|copper)', quoted[1]))
                        assert base > 0, quoted[1]
                        paid = stats(sold)['coins'] - before
                        bonus = max(10, int(base * rate)) if owned else 0
                        assert paid == base + bonus, (base, bonus, paid, sold)
                        assert ('Enlil grants you an additional' in sold) == owned, sold
                        evidence['cargo_sales'].append({'player': name, 'commodity': commodity,
                                                       'base': base, 'bonus': bonus, 'paid': paid})
                    client.send('save')
                    client.expect('Save complete for ' + name + '.', timeout=60)
                print('PASS actual cargo/contraband sales: owning-side bonus and opposing-side exclusion', flush=True)
                assert sql(base_stats_query) == base_stats, 'Nexus journey changed base stats'
                evidence['base_stats_unchanged'] = True

                before_restart = state()
                player_scores = {name: stats(command(client, 'score'))
                                 for name, client in ((GOOD, good), (EVIL, evil))}
                player_state_query = ("SELECT name,epics,platinum,gold,silver,copper FROM player_data "
                                      f"WHERE name IN ('{GOOD}','{EVIL}') ORDER BY name")
                player_state = sql(player_state_query)
                stop()
                ship_room = boot()
                assert state() == before_restart, 'cold restart changed Nexus ownership or touch timestamps'
                assert sql(player_state_query) == player_state, 'cold restart changed saved reward balances'
                god, good, evil = login(GOD), login(GOOD), login(EVIL)
                for name, client in ((GOOD, good), (EVIL, evil)):
                    restored = stats(command(client, 'score'))
                    for field in ('epics', 'coins'):
                        assert restored[field] == player_scores[name][field], \
                            (name, field, player_scores[name], restored)
                    ownership = command(client, 'nexus')
                    assert 'Marduk (good)' in ownership and 'Enlil (evil)' in ownership, ownership
                for stone_name, room, guardian in (('Marduk', 130199, 65), ('Enlil', ship_room, 66)):
                    command(god, f'goto {room}')
                    assert command(god, 'look').count(f'The nexus stone of {stone_name} stands here.') == 1
                    guardian_diagnostic = command(god, 'stat mob guardian')
                    assert re.search(rf'Numbers: {guardian}-V .*# in game: 1\b', guardian_diagnostic), \
                        guardian_diagnostic
                evidence['restart_state'] = state()
                evidence['restored_player_balances'] = {
                    name: {field: score[field] for field in ('epics', 'coins')}
                    for name, score in player_scores.items()}
                evidence['ship_rooms'] = [first_ship_room, ship_room]
                print('PASS cold restart: reconnected scores, live ownership, aligned guardians and placements retained', flush=True)
                stop()
                sql("UPDATE nexus_stones SET last_touched_at='2000-01-01 00:00:00' WHERE id=1")
                boot()
                wait_align(1, 0)
                assert sql('SELECT last_touched_at IS NULL FROM nexus_stones WHERE id=1') == '1'
                assert sql('SELECT align FROM nexus_stones WHERE id=3') == '-3'
                god = login(GOD)
                command(god, 'goto 130199')
                guardian_diagnostic = command(god, 'stat mob guardian')
                assert re.search(r'Numbers: 74-V .*# in game: 1\b', guardian_diagnostic), guardian_diagnostic
                for _ in range(2):
                    command(god, 'nexus reload 1')
                    look = command(god, 'look')
                    assert look.count('The nexus stone of Marduk stands here.') == 1, look
                    # Combat changes the room description; count the actual
                    # prototype population instead of its idle display text.
                    guardian_diagnostic = command(god, 'stat mob guardian')
                    assert re.search(r'Numbers: 74-V .*# in game: 1\b', guardian_diagnostic), guardian_diagnostic
                print('PASS expiration and repeated neutral reload: state reset, peer retained, one guardian', flush=True)
                stop()
                print(json.dumps(evidence, sort_keys=True), flush=True)
            except Exception:
                print(guardian_diagnostic[-5000:], flush=True)
                excerpt = output_path.read_text(errors='replace')[-3500:]
                print(excerpt.replace(env['DB_PASSWD'], '[REDACTED]'), flush=True)
                raise
            finally:
                for client in clients:
                    client.close()
                if process is not None and process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=30)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--server', type=Path, required=True)
    run(parser.parse_args().server.resolve())
