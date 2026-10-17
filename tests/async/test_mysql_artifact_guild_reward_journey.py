#!/usr/bin/env python3
"""Artifact/guild rewards from a real Summon Ghasts cast on disposable MariaDB.

Uses the full server/world and synthetic accounts. Never reads the checkout's
.env or operates the shared dev instance. Run with with_disposable_mariadb.sh.
"""
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
PLAYER, ACCOUNT = 'Articaster', 'Artiplayer'
GOD, GOD_ACCOUNT = 'Artiwarden', 'Artistaff'
VICTIM, VICTIM_ACCOUNT = 'Artivictim', 'Artienemy'
ARTIFACT = 900000
SWAP_LIVE, SWAP_OFFLINE, SWAP_CRUMBLE = ARTIFACT + 1, ARTIFACT + 2, ARTIFACT + 3


CASES = ('standard', 'before_artifact', 'after_artifact', 'after_history', 'shutdown', 'pvp')


def run(binary, case):
    with tempfile.TemporaryDirectory(prefix='artifact-rewards-', dir=ROOT / 'bin/tests') as temporary:
        runtime = Path(temporary)
        _, critical, output_path = setup_run_root(runtime)
        # The reward subject is a private prototype with no reset/script
        # producers; natural world population is random and is not fixture state.
        objects = (ROOT / 'areas/world.obj').read_text(encoding='latin-1')
        original = re.search(r'(?ms)^#900\n.*?(?=^#\d+\n)', objects)
        assert original and not re.search(rf'(?m)^#{ARTIFACT}$', objects)
        assert not re.search(rf'(?m)^#({SWAP_LIVE}|{SWAP_OFFLINE}|{SWAP_CRUMBLE})$', objects)
        private_records = []
        for vnum in (ARTIFACT, SWAP_LIVE, SWAP_OFFLINE, SWAP_CRUMBLE):
            record = original.group().replace('#900\n', f'#{vnum}\n', 1)
            if vnum == SWAP_CRUMBLE:
                # The real obj_to_char contract can destroy an artifact with this
                # existing flag before returning to its caller. Keep it private.
                strings = record.split('~', 4)
                numeric = strings[4].splitlines(keepends=True)
                header = next(index for index, line in enumerate(numeric) if line.strip())
                fields = numeric[header].split()
                assert len(fields) == 11
                fields[8] = str(int(fields[8]) | 2048) # ITEM2_CRUMBLELOOT
                numeric[header] = ' '.join(fields) + '\n'
                strings[4] = ''.join(numeric)
                record = '~'.join(strings)
            private_records.append(record)
        inserted = ''.join(private_records)
        position = next(match.start() for match in re.finditer(r'(?m)^#(\d+)\n', objects)
                        if int(match.group(1)) > ARTIFACT)
        areas = runtime / 'areas'
        assert areas.is_symlink()
        areas.unlink(); areas.mkdir()
        for source in (ROOT / 'areas').iterdir():
            if source.name != 'world.obj':
                (areas / source.name).symlink_to(source, target_is_directory=source.is_dir())
        (areas / 'world.obj').write_text(objects[:position] + inserted + objects[position:], encoding='latin-1')
        (runtime / 'help').symlink_to(ROOT / 'help', target_is_directory=True)
        (runtime / 'bin/server').mkdir(parents=True)
        executable = runtime / 'bin/server/dms'
        shutil.copy2(binary, executable)
        executable.chmod(0o700)
        with (runtime / 'lib/misc/event_names').open('w') as names:
            subprocess.run([str(ROOT / 'scripts/event_names.sh'), str(executable)], stdout=names, check=True)
        properties = runtime / 'lib/duris.properties'
        text = properties.read_text()
        for key, value in {
            'camp.timer': 1, 'artifact.feeding.epic.point.seconds': 3600,
            'artifact.feeding.epic.typeMod.boon': .25, 'artifact.feeding.epic.typeMod.pvp': 2,
            'epic.frag.minimum.epics': 100, 'epic.frag.amount': 100,
            'epic.frag.maximum.epics': 100, 'prestige.gain.pvp': 20,
            'difficulty.dial.epic.gain': 5,
            'difficulty.dial.artifact.feeding': 5, 'epic.gain.modifier.good': 1,
            'epic.gain.modifier.evil': 1, 'prestige.guildedInGroupMinimum': 1,
            'prestige.epicsMinimum': 4, 'prestige.gain.default': 10,
            'prestige.constructionPoints.notch': 100,
            'spell.area.minChance.summonGhasts': 100, 'spell.area.chanceStep.summonGhasts': 0,
        }.items():
            text, count = re.subn(r'^' + re.escape(key) + r'=.*$', key + '=' + str(value), text, flags=re.M)
            if not count:
                text += '\n' + key + '=' + str(value) + '\n'
        properties.write_text(text)
        plain, tls, websocket = journey.available_ports()
        clients = []
        process = None
        locker = None
        evidence = {'case': case, 'artifact_vnum': ARTIFACT, 'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest()}
        barrier = runtime / 'history-commit.hold'
        preload = runtime / 'bin/tests/artifact-commit-barrier.so'
        if case == 'after_history':
            preload.parent.mkdir(parents=True)
            subprocess.run(['cc', '-std=c11', '-shared', '-fPIC', '-Wall', '-Wextra', '-Werror',
                            'tests/async/artifact_guild_commit_barrier.c', '-ldl', '-o', str(preload)],
                           cwd=ROOT, check=True)
        with authority('mariadb', runtime) as (env, sql), output_path.open('w') as output:
            env.update(CRITICAL_COMMAND_JOURNAL_DIR=str(critical), DURIS_TLS_PORT=str(tls),
                       DURIS_WEBSOCKET_PORT=str(websocket), MAINTENANCE_STATE_FILE=str(runtime / 'maintenance.state'))

            def boot():
                nonlocal process
                offset = output_path.stat().st_size
                server_env = dict(env)
                if case == 'after_history':
                    server_env.update(LD_PRELOAD=str(preload), DURIS_TEST_ARTIFACT_COMMIT_BARRIER=str(barrier))
                process = subprocess.Popen([str(executable), '-d', str(runtime), str(plain)],
                                           cwd=runtime, env=server_env, stdout=output, stderr=subprocess.STDOUT)
                deadline = time.monotonic() + 180
                while b'Entering game loop.' not in output_path.read_bytes()[offset:]:
                    assert process.poll() is None and time.monotonic() < deadline, 'artifact world failed to boot'
                    time.sleep(.1)
                assert Path(os.readlink(f'/proc/{process.pid}/exe')).resolve() == executable

            def stop(crash=False):
                for client in clients:
                    client.close()
                clients.clear()
                process.send_signal(signal.SIGKILL if crash else signal.SIGTERM)
                process.wait(timeout=60)
                assert process.returncode == (-signal.SIGKILL if crash else 0)

            def login(name, account, *, reconnect=False):
                client = journey.reconnect_character(plain, expected_room=None, account=account, character=name)
                clients.append(client)
                if reconnect:
                    assert 'Reconnecting...' in client.transcript.decode(errors='replace')
                else:
                    client.expect('Welcome to Duris', timeout=60)
                client.expect_any(('Pos: standing >', '<>'), timeout=20)
                command(client, 'toggle paging no')
                return client

            def settle(predicate, label, timeout=30):
                deadline = time.monotonic() + timeout
                while not predicate():
                    assert time.monotonic() < deadline, label
                    time.sleep(.1)

            def summon_ghasts():
                for attempt in range(5):
                    player.send("cast 'summon ghasts'")
                    outcome, _ = player.expect_any(
                        ('Deathly incorporeal ghasts', "You abort your spell before it's done!"),
                        timeout=60)
                    evidence['cast_attempts'] = attempt + 1
                    if outcome == 'Deathly incorporeal ghasts':
                        return
                raise AssertionError('five casts aborted before summon completion')

            def hold_row(table, column, identity):
                nonlocal locker
                locker = subprocess.Popen(
                    ['mysql', '--protocol=tcp', '--unbuffered', '-N', '-B',
                     '-h', env['DB_HOST'], '-P', env['DB_PORT'], '-u', env['DB_USER'], env['DB_NAME']],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, env=env)
                locker.stdin.write(f"START TRANSACTION; SELECT {column} FROM {table} WHERE {column}={identity} FOR UPDATE; SELECT 'locked'; SELECT SLEEP(120);\n")
                locker.stdin.flush()
                assert locker.stdout.readline().strip() == str(identity)
                assert locker.stdout.readline().strip() == 'locked'

            def saved_state():
                return {
                    'artifact': sql(f'SELECT owned,locType,location,UNIX_TIMESTAMP(timer) FROM artifacts WHERE vnum={ARTIFACT}'),
                    'guild': sql("SELECT prestige,construction FROM guilds WHERE TRIM(name)='Rewardguild'"),
                    'history': sql('SELECT COUNT(*) FROM artifact_guild_outcome'),
                }

            try:
                boot()
                identities = ((PLAYER, ACCOUNT), (GOD, GOD_ACCOUNT)) + (((VICTIM, VICTIM_ACCOUNT),) if case == 'pvp' else ())
                for name, account in identities:
                    client = journey.MudClient(plain, source_host='127.0.0.2' if name == VICTIM else None)
                    clients.append(client)
                    journey.create_character(client, expected_room=None, account=account, character=name,
                                             email=name.lower() + '@example.invalid')
                    client.send('save')
                    client.expect('Save complete for ' + name + '.', timeout=60)
                stop()
                sql(f"UPDATE player_data SET level=62,highest_level=62 WHERE name='{GOD}'")
                sql(f"UPDATE player_data SET level=51,highest_level=51,m_class=1024,secondary_class=0 WHERE name='{PLAYER}'")
                if case == 'pvp':
                    sql(f"UPDATE player_data SET level=51,highest_level=51,race=13,racewar=2 WHERE name='{VICTIM}'")
                    # The opposing-side fixture starts without a recent Good login.
                    sql(f"UPDATE accounts SET last_good_char=NULL WHERE account_name='{VICTIM_ACCOUNT}'")
                # An undecodable source graph is data only: ordinary gameplay and
                # repeated character saves must preserve the original rows/metadata.
                source_pid = int(sql(f"SELECT pid FROM player_data WHERE name='{PLAYER}'"))
                sql(f"INSERT INTO player_items(pid,vnum,obj_uid,quantity,weight,extra_flags,short_descr) VALUES({source_pid},900,NULL,7,123,268435456,'held source evidence')")
                retained_root = int(sql(f"SELECT id FROM player_items WHERE pid={source_pid} AND short_descr='held source evidence'"))
                sql(f"INSERT INTO player_items(pid,vnum,obj_uid,container_id,quantity) VALUES({source_pid},901,8888888,{retained_root},1)")
                sql(f"INSERT INTO player_item_extra_descr(item_id,keyword,description) VALUES({retained_root},'retained','original source details')")
                def retained_source_intact():
                    return sql(f"SELECT COUNT(*) FROM player_items p JOIN player_items c ON c.container_id=p.id AND c.obj_uid=8888888 JOIN player_item_extra_descr d ON d.item_id=p.id AND d.keyword='retained' AND d.description='original source details' WHERE p.id={retained_root} AND p.obj_uid IS NULL AND p.quantity=7 AND p.weight=123 AND p.short_descr='held source evidence'") == '1' and sql("SELECT COUNT(*) FROM item_current_owner WHERE item_uid=8888888") == '0'
                # A prepared spell is initial fixture state; casting, delayed events,
                # kills, boon publication and rewards all use the real game path.
                sql(f"INSERT INTO player_skills(pid,skill_id,learned,taught) SELECT pid,571,100,100 FROM player_data WHERE name='{PLAYER}' ON DUPLICATE KEY UPDATE learned=100,taught=100")
                sql(f"INSERT INTO player_affects(pid,type,duration,flags,modifier) SELECT pid,2005,-1,790,571 FROM player_data WHERE name='{PLAYER}'")
                boot()
                god = login(GOD, GOD_ACCOUNT)
                player = login(PLAYER, ACCOUNT)
                command(god, 'goto 1')
                # Roaming world mobs must not join the three controlled boon targets.
                command(god, 'setbit room here flag NO_MOB 1')
                command(god, 'purge')
                command(god, 'setbit room here flag SAFE 0')
                command(god, 'setbit room here flag ROOM_NO_MAGIC 0')
                command(god, 'setbit room here flag ROOM_MAGIC_LIGHT 1')
                command(god, 'transfer ' + PLAYER)
                command(god, f"setbit char {PLAYER} skill 'summon ghasts' 100")
                command(god, f"setbit char {PLAYER} taught 'summon ghasts' 100")
                command(god, 'setbit char ' + PLAYER + ' basehit 100000')
                command(god, 'restore ' + PLAYER)
                assert 'Class: Necromancer' in command(player, 'score')
                assert 'new association is set up' in command(god, 'supervise found ' + PLAYER + ' n Rewardguild')
                settle(lambda: sql("SELECT COUNT(*) FROM guilds WHERE TRIM(name)='Rewardguild'") == '1', 'guild snapshot missing')
                gid = int(sql("SELECT id FROM guilds WHERE TRIM(name)='Rewardguild'"))
                command(god, f'supervise setbit {gid} prestige 85')
                command(god, f'supervise setbit {gid} construction 0')
                command(god, 'setbit char ' + GOD + ' winvis 0')
                command(player, 'consent ' + GOD)
                grouped = command(god, 'group ' + PLAYER)
                assert 'now a member' in grouped, grouped

                created = command(god, f'load obj {ARTIFACT}')
                assert 'You have created' in created, created
                command(god, 'drop stone')
                settle(lambda: sql(f'SELECT owned FROM artifact_domain_state WHERE vnum={ARTIFACT}') == '0', 'unowned ground control missing')
                ground = command(god, f'stat obj {ARTIFACT}')
                assert re.search(r'Number in game\s*:\s*1\b', ground), ground
                duplicate = command(god, f'load obj {ARTIFACT}')
                assert 'creation refused: already present' in duplicate, duplicate
                command(god, 'get stone')
                cloned = command(god, 'clone obj stone 2')
                assert 'Clone refused' in cloned and 'You make a clone' not in cloned, cloned
                command(god, 'give stone ' + PLAYER)
                equipped = command(player, 'wear stone')
                assert 'stone' in equipped, equipped
                assert 'ioun stone' in command(player, 'equipment')
                settle(lambda: sql(f'SELECT COUNT(*) FROM artifacts WHERE vnum={ARTIFACT}') == '1', 'artifact snapshot missing')
                adjusted = command(god, f'artifacts timer set {ARTIFACT} 10')
                assert "timer changed" in adjusted, adjusted
                settle(lambda: int(sql(f'SELECT UNIX_TIMESTAMP(timer) FROM artifacts WHERE vnum={ARTIFACT}')) < time.time() + 1000, 'uncapped timer setup was not saved')
                timer_before = int(sql(f'SELECT UNIX_TIMESTAMP(timer) FROM artifacts WHERE vnum={ARTIFACT}'))
                evidence['timer_before'] = timer_before
                identity_before = sql(f'SELECT COALESCE(canonical_item_uid,0),identity_state FROM artifact_domain_state WHERE vnum={ARTIFACT}')
                assert identity_before.endswith('\t1') and int(identity_before.split('\t')[0]) > 0, identity_before
                evidence['canonical_identity'] = identity_before
                # Exercise actual async list/player reports after boot cached the private template.
                for report in ('artifacts player ' + PLAYER, 'artifacts ioun'):
                    god.send(report)
                    god.expect(f'(#{ARTIFACT})', timeout=30)
                report_population = command(god, f'stat obj {ARTIFACT}')
                assert re.search(r'Number in game\s*:\s*1\b', report_population), report_population
                assert sql(f'SELECT COALESCE(canonical_item_uid,0),identity_state FROM artifact_domain_state WHERE vnum={ARTIFACT}') == identity_before
                evidence['reports_preserved_population'] = True
                if case == 'pvp':
                    # Two synthetic mortal accounts may fight in this private fixture.
                    god.send('whitelist add Fixture 127.0.0.* isolated reward journey')
                    god.expect('Host pattern added', timeout=30)
                    victim = login(VICTIM, VICTIM_ACCOUNT)
                    command(god, 'purge')
                    command(god, 'setbit room here flag ARENA 0')
                    command(god, 'transfer ' + VICTIM)
                    command(god, 'setbit char ' + VICTIM + ' hit 1')
                    command(god, f'artifacts reset {ARTIFACT}')
                    command(god, 'goto 3')
                    player.send('save'); player.expect('Save complete for ' + PLAYER + '.', timeout=60)
                    hold_row('artifacts', 'vnum', ARTIFACT)
                    began = len(player.transcript)
                    print('artifact journey: PvP participants ready; artifact writer held', flush=True)
                    summon_ghasts()
                    player.expect('sense of satisfaction', timeout=60)
                    victim.expect('ACCOUNT MENU', timeout=60)
                    player.expect('You have gained 100 epic points.', timeout=30)
                    held = saved_state()
                    assert int(held['artifact'].split('\t')[-1]) == timer_before and held['guild'] == '85\t0', held
                    status = command(god, 'world persistence')
                    assert 'artifact_guild live_applied=1' in status and 'history_pending=1' in status, status
                    locker.terminate(); locker.wait(timeout=10); locker = None
                    settle(lambda: sql('SELECT COUNT(*) FROM artifact_guild_outcome') == '1', 'PvP child history did not commit')
                    after = saved_state()
                    assert int(after['artifact'].split('\t')[-1]) == timer_before + 720000, after
                    assert after['guild'] == '105\t1', after
                    assert sql('SELECT p.command_type FROM artifact_guild_outcome a JOIN critical_operation_inbox p ON p.operation_id=a.parent_operation_id') == '8'
                    player.send('save'); player.expect('Save complete for ' + PLAYER + '.', timeout=60)
                    evidence['pvp_transcript'] = bytes(player.transcript[began:]).decode(errors='replace')
                    evidence['after_pvp'] = after
                    stop()
                    boot()
                    god = login(GOD, GOD_ACCOUNT); player = login(PLAYER, ACCOUNT)
                    assert 'ioun stone' in command(player, 'equipment')
                    assert saved_state() == after, 'PvP history or rewards changed at restart'
                    assert 'artifact_guild live_applied=0' in command(god, 'world persistence')
                    stop()
                    target = ROOT / 'bin/analysis/artifact-estale'
                    target.mkdir(parents=True, exist_ok=True)
                    (target / 'gameplay-pvp.json').write_text(json.dumps(evidence, indent=2) + '\n')
                    print('PASS actual PvP death -> combat parent -> live feed/guild reward before snapshot commit; restart stable', flush=True)
                    return

                # Keep weapon attacks from killing a target while ghasts defer.
                # This is the ordinary caster combat setting, not a spell override.
                assert 'stop all your attacks' in command(player, 'offensive off')
                assert 'stop all your attacks' in command(god, 'offensive off')
                player.send('save'); player.expect('Save complete for ' + PLAYER + '.', timeout=60)
                for _ in range(3):
                    god.send('boon add all epic 4 mob 1 11 60')
                    god.expect('Boon successfully created.', timeout=30)
                    command(god, 'load mob 11')

                print('artifact journey: caster, worn artifact, guild threshold and three boon targets ready', flush=True)
                # Stop at exact persistence boundaries without changing game code.
                if case == 'after_history':
                    barrier.touch()
                else:
                    locked_table, column, locked_id = ('guilds', 'id', gid) if case == 'after_artifact' else ('artifacts', 'vnum', ARTIFACT)
                    hold_row(locked_table, column, locked_id)
                cast_start = len(player.transcript)
                evidence['cast_wall_usec'] = time.time_ns() // 1000
                summon_ghasts()
                evidence['summoned_wall_usec'] = time.time_ns() // 1000
                player.expect('Your creatures from beyond the grave', timeout=60)
                evidence['attack_wall_usec'] = time.time_ns() // 1000
                for _ in range(3):
                    player.expect('You have gained 4 epic points.', timeout=30)
                evidence['awards_seen_wall_usec'] = time.time_ns() // 1000
                if case == 'after_history':
                    settle(lambda: Path(str(barrier) + '.committed').exists(), 'history did not reach the post-COMMIT barrier')
                expected_increment = 3600 if case in ('after_artifact', 'after_history') else 0
                settle(lambda: int(saved_state()['artifact'].split('\t')[-1]) == timer_before + expected_increment,
                       'writer did not reach the selected snapshot boundary')
                held = saved_state()
                assert held['guild'] == ('95\t0' if case == 'after_history' else '85\t0'), held
                assert held['history'] == ('1' if case == 'after_history' else '0'), held
                status = command(god, 'world persistence')
                assert 'artifact_guild live_applied=3' in status and 'history_pending=3' in status, status
                evidence['while_writer_held'] = next(line for line in status.splitlines() if line.startswith('artifact_guild '))
                evidence['cast_transcript'] = bytes(player.transcript[cast_start:]).decode(errors='replace')
                assert evidence['cast_transcript'].count('Raoul convulses and dies') == 3
                assert evidence['cast_transcript'].count('sense of satisfaction') == 3
                if case != 'standard':
                    evidence['before_crash'] = held
                    stopped_at = time.monotonic()
                    stop(crash=case != 'shutdown')
                    if case == 'shutdown':
                        elapsed = time.monotonic() - stopped_at
                        assert elapsed < 45, ('shutdown exceeded its bounded drains', elapsed)
                        # runtime_logs() is a bounded failure excerpt and can omit
                        # the file containing these shutdown records. Read it whole.
                        reporting = (runtime / 'logs/log/file').read_text(errors='replace') + output_path.read_text(errors='replace')
                        details = '\n'.join(line for line in reporting.splitlines() if any(word in line for word in ('artifact_guild', 'writer', 'shutdown', 'PERSISTENCE')))
                        assert f'reason=unsaved entity=artifact vnum={ARTIFACT}' in reporting, details
                        assert f'reason=unsaved entity=guild guild_id={gid}' in reporting, details
                        unresolved = re.findall(r'domain=artifact_guild/shutdown action=history_unresolved outcome=alert detail=operation=([0-9a-f]{32}) parent=([0-9a-f]{32}) error=\d+ elapsed_ms=\d+', reporting)
                        assert len(set(unresolved)) == 3, details
                        evidence['bounded_shutdown_seconds'] = elapsed
                        evidence['reported_history'] = sorted(set(unresolved))
                        evidence['reported_artifact'] = ARTIFACT
                        evidence['reported_guild'] = gid
                    barrier.unlink(missing_ok=True)
                    if locker:
                        locker.terminate(); locker.wait(timeout=10); locker = None
                    boot()
                    god = login(GOD, GOD_ACCOUNT)
                    player = login(PLAYER, ACCOUNT)
                    assert 'ioun stone' in command(player, 'equipment')
                    assert saved_state() == held, (case, held, saved_state())
                    assert 'artifact_guild live_applied=0' in command(god, 'world persistence')
                    if case == 'after_history':
                        settle(lambda: sql('SELECT COUNT(*) FROM critical_outbox WHERE destination=7 AND delivered_at IS NULL') == '0',
                               'committed history outbox was not delivered after crash')
                        assert saved_state() == held, 'outbox replay granted the reward again'
                    evidence['crash_reload'] = saved_state()
                    stop()
                    target = ROOT / 'bin/analysis/artifact-estale'
                    target.mkdir(parents=True, exist_ok=True)
                    (target / ('gameplay-' + case + '.json')).write_text(json.dumps(evidence, indent=2) + '\n')
                    print('PASS artifact journey stop at ' + case + ': only persisted state reloaded; no history re-award', flush=True)
                    return
                print('artifact journey: three live rewards before snapshots/history can commit', flush=True)
                process.send_signal(signal.SIGUSR1)
                player.expect('Copyover FAILED - server remains live.', timeout=30)
                assert process.poll() is None
                assert 'artifact_guild live_applied=3' in command(god, 'world persistence')
                evidence['blocked_copyover_cancelled'] = True
                locker.terminate(); locker.wait(timeout=10); locker = None
                settle(lambda: sql('SELECT COUNT(*) FROM artifact_guild_outcome') == '3', 'three reward histories did not commit')
                evidence['history_seen_wall_usec'] = time.time_ns() // 1000
                after = saved_state()
                assert int(after['artifact'].split('\t')[-1]) == timer_before + 10800, after
                assert after['guild'] == '115\t1', after
                evidence['timer_before'] = timer_before
                evidence['after_burst'] = after
                evidence['cast_transcript'] = bytes(player.transcript[cast_start:]).decode(errors='replace')
                assert evidence['cast_transcript'].count('sense of satisfaction') == 3, evidence['cast_transcript']
                deadline = time.monotonic() + 30
                while True:
                    status = command(god, 'world persistence')
                    assert 'artifact_guild live_applied=3' in status, status
                    if 'dirty_artifacts=0 dirty_guilds=0 history_committed=3' in status:
                        break
                    assert time.monotonic() < deadline, status
                    time.sleep(.1)
                deltas = sql('SELECT timer_before,timer_after FROM artifact_guild_outcome_delta ORDER BY timer_before')
                assert deltas.splitlines() == [f'{timer_before+i*3600}\t{timer_before+(i+1)*3600}' for i in range(3)], deltas
                assert sql('SELECT guild_prestige_after,guild_construction_after FROM artifact_guild_outcome ORDER BY guild_prestige_after') == '95\t0\n105\t1\n115\t1'
                evidence['outcome_deltas'] = deltas
                print('artifact journey: writer recovered; timers, guild totals and history agree', flush=True)
                # Keep the same canonical artifact on the ground through native copyover.
                command(player, 'drop all') # free the normal starter inventory capacity
                removed = command(player, 'remove stone')
                assert 'You stop using' in removed, removed
                dropped = command(player, 'drop stone')
                assert 'You drop' in dropped, dropped
                settle(lambda: sql(f'SELECT loc_type,location FROM artifact_domain_state WHERE vnum={ARTIFACT}') == '4\t1', 'ground artifact location did not commit')
                ground_state = saved_state()
                assert ground_state['artifact'].split('\t')[-1] == after['artifact'].split('\t')[-1]
                soul_before = sql(f'SELECT bind_owner_pid,bind_timer_epoch FROM artifact_domain_state WHERE vnum={ARTIFACT}')
                evidence['ground_state'] = ground_state
                evidence['ground_custody'] = sql(f'SELECT c.item_uid,c.root_item_uid,c.parent_item_uid,c.owner_type,c.owner_id,c.owner_context_id,c.item_revision,c.state,r.revision FROM item_current_owner c LEFT JOIN item_owner_revision r ON r.owner_type=c.owner_type AND r.owner_id=c.owner_id AND r.owner_context_id=c.owner_context_id WHERE c.vnum={ARTIFACT}')
                process.send_signal(signal.SIGUSR1)
                player.expect('Copyover complete!', timeout=180)
                god.expect('Copyover complete!', timeout=180)
                assert saved_state() == ground_state, 'copyover changed persisted ground artifact/reward state'
                assert sql(f'SELECT bind_owner_pid,bind_timer_epoch FROM artifact_domain_state WHERE vnum={ARTIFACT}') == soul_before
                assert sql(f'SELECT COALESCE(canonical_item_uid,0),identity_state FROM artifact_domain_state WHERE vnum={ARTIFACT}') == identity_before
                recovered_ground = command(god, f'stat obj {ARTIFACT}')
                assert re.search(r'Number in game\s*:\s*1\b', recovered_ground), recovered_ground
                command(player, 'get stone')
                command(player, 'wear stone')
                settle(lambda: saved_state() == after, 'ground pickup changed artifact timer/reward history')
                evidence['ground_copyover_preserved_uid_timer_soul'] = True
                recovered_equipment = command(player, 'equipment')
                assert 'ioun stone' in recovered_equipment, recovered_equipment
                evidence['copyover_after_drain'] = True
                player.send('save'); player.expect('Save complete for ' + PLAYER + '.', timeout=60)
                stop()
                before_restart = saved_state()
                assert sql(f'SELECT COALESCE(canonical_item_uid,0),identity_state FROM artifact_domain_state WHERE vnum={ARTIFACT}') == identity_before
                boot()
                god = login(GOD, GOD_ACCOUNT)
                offline_stat = command(god, f'stat obj {ARTIFACT}')
                assert re.search(r'Number in game\s*:\s*0\b', offline_stat), offline_stat
                offline_denied = command(god, f'load obj {ARTIFACT}')
                assert 'creation refused: already present' in offline_denied, offline_denied
                assert sql(f'SELECT COALESCE(canonical_item_uid,0),identity_state FROM artifact_domain_state WHERE vnum={ARTIFACT}') == identity_before
                # Change mutable source data after boot classified the healthy canonical
                # artifact. The wrong-UID root and child must stay raw, while that real
                # artifact and independent ordinary inventory still enter gameplay.
                sql(f"INSERT INTO player_items(pid,vnum,obj_uid,quantity,extra_flags,short_descr) VALUES({source_pid},{ARTIFACT},8888899,1,268435456,'rejected mutable artifact')")
                rejected_root = int(sql(f"SELECT id FROM player_items WHERE pid={source_pid} AND obj_uid=8888899"))
                sql(f"INSERT INTO player_items(pid,vnum,obj_uid,container_id,quantity) VALUES({source_pid},901,8888898,{rejected_root},1)")
                sql(f"INSERT INTO player_items(pid,vnum,obj_uid,quantity,extra_flags,short_descr) VALUES({source_pid},901,8888897,1,0,'ordinary source control')")
                god.send('load char ' + PLAYER)
                god.expect('greatly humbled by your power', timeout=60)
                loaded_stat = command(god, f'stat obj {ARTIFACT}')
                assert re.search(r'Number in game\s*:\s*1\b', loaded_stat), loaded_stat
                god.send('load char ' + PLAYER)
                god.expect('item load refused.', timeout=60)
                duplicate_stat = command(god, f'stat obj {ARTIFACT}')
                assert re.search(r'Number in game\s*:\s*1\b', duplicate_stat), duplicate_stat
                player = login(PLAYER, ACCOUNT, reconnect=True)
                assert 'Some saved items need staff review' in player.transcript.decode(errors='replace')
                assert 'ioun stone' in command(player, 'equipment')
                assert 'ordinary source control' in command(player, 'inventory')
                evidence['staff_player_load_admission'] = {'canonical_live_count': 1, 'duplicate_refused': True, 'account_reconnected': True}
                admitted_stat = command(god, f'stat obj {ARTIFACT}')
                assert re.search(r'Number in game\s*:\s*1\b', admitted_stat), admitted_stat
                player.send('save'); player.expect('Save complete for ' + PLAYER + '.', timeout=60)
                assert sql(f"SELECT COUNT(*) FROM player_items p JOIN player_items c ON c.container_id=p.id AND c.obj_uid=8888898 WHERE p.id={rejected_root} AND p.obj_uid=8888899 AND p.short_descr='rejected mutable artifact'") == '1'
                assert sql("SELECT COUNT(*) FROM item_current_owner WHERE item_uid IN (8888899,8888898)") == '0'
                assert sql(f"SELECT COUNT(*) FROM item_current_owner WHERE item_uid=8888897 AND owner_type=1 AND owner_id={source_pid} AND state=1") == '1'
                evidence['mutable_player_admission'] = {'wrong_uid_root_retained': True, 'no_held_claim': True, 'canonical_live_count': 1, 'ordinary_inventory_saved': True}
                # Hunt follows the established initial/filename discovery but reads
                # the complete raw SQL source cut without creating a second owner.
                discovery = runtime / 'Players/a'
                discovery.mkdir(parents=True, exist_ok=True)
                (discovery / PLAYER).touch()
                # Compare logical source payloads: an unrelated autosave may replace
                # valid rows' database IDs while this read is in flight.
                audit_query = f"SELECT p.obj_uid,COALESCE(parent.obj_uid,0),p.vnum,p.quantity,p.extra_flags,p.short_descr FROM player_items p LEFT JOIN player_items parent ON parent.id=p.container_id WHERE p.pid={source_pid} ORDER BY p.obj_uid,p.id"
                before_hunt = sql(audit_query)
                god.send('artifacts hunt a')
                god.expect('Artifact source audit for ' + PLAYER, timeout=60)
                god.expect('No repairs applied.', timeout=60)
                hunt_output = god.transcript.decode(errors='replace')
                assert f'vnum={ARTIFACT} uid=8888899' in hunt_output
                assert 'vnum=900 uid=0' in hunt_output and 'quantity=7' in hunt_output
                assert sql(audit_query) == before_hunt
                hunt_stat = command(god, f'stat obj {ARTIFACT}')
                assert re.search(r'Number in game\s*:\s*1\b', hunt_stat), hunt_stat
                assert sql(f'SELECT bind_owner_pid,bind_timer_epoch FROM artifact_domain_state WHERE vnum={ARTIFACT}') == soul_before
                evidence['hunt_read_only_source_inspection'] = True
                # Invalid maintenance input must leave the canonical artifact and
                # raw held source graph untouched, including a vnum that used to wrap.
                for invalid_timer in (f'artifacts timer set {ARTIFACT} not-a-number',
                                      f'artifacts timer set {2**32 + ARTIFACT} 10'):
                    refused = command(god, invalid_timer)
                    assert 'timer changed' not in refused, refused
                command(god, 'artifacts poof 900')
                assert sql(audit_query) == before_hunt
                maintenance_stat = command(god, f'stat obj {ARTIFACT}')
                assert re.search(r'Number in game\s*:\s*1\b', maintenance_stat), maintenance_stat
                assert sql(f'SELECT bind_owner_pid,bind_timer_epoch FROM artifact_domain_state WHERE vnum={ARTIFACT}') == soul_before
                evidence['maintenance_query_preserves_identity_and_source'] = True
                refused_swap = command(god, f'artifacts swap {ARTIFACT} {ARTIFACT}')
                assert 'already present or reserved' in refused_swap, refused_swap
                assert sql(audit_query) == before_hunt
                still_one = command(god, f'stat obj {ARTIFACT}')
                assert re.search(r'Number in game\s*:\s*1\b', still_one), still_one
                assert saved_state() == before_restart, 'restart changed persisted reward state/history'
                assert 'artifact_guild live_applied=0' in command(god, 'world persistence')
                assert 'You stop using' in command(player, 'remove stone')
                failed_swap = command(god, f'artifacts swap {ARTIFACT} {SWAP_CRUMBLE}')
                assert 'replacement placement failed; original retained' in failed_swap, failed_swap
                assert 'ioun stone' in command(player, 'inventory')
                assert re.search(r'Number in game\s*:\s*1\b', command(god, f'stat obj {ARTIFACT}'))
                assert sql(f'SELECT canonical_item_uid,identity_state FROM artifact_domain_state WHERE vnum={ARTIFACT}') == identity_before
                assert sql(f'SELECT COALESCE(canonical_item_uid,0),identity_state FROM artifact_domain_state WHERE vnum={SWAP_CRUMBLE}') == '0\t3'
                assert sql(f'SELECT bind_owner_pid,bind_timer_epoch FROM artifact_domain_state WHERE vnum={ARTIFACT}') == soul_before
                assert saved_state() == before_restart, 'failed placement changed persisted artifact/reward state'
                command(player, 'wear stone')
                assert 'ioun stone' in command(player, 'equipment')
                evidence['destructive_placement_preserves_original'] = True
                # Real worn replacement, then an offline replacement after a clean
                # restart. This proves admission/recovery, not atomic crash windows.
                expected_timer = int(before_restart['artifact'].split('\t')[-1])
                old_uid = int(identity_before.split('\t')[0])
                live_swapped = command(god, f'artifacts swap {ARTIFACT} {SWAP_LIVE}')
                assert 'swapped with artifact' in live_swapped, live_swapped
                settle(lambda: sql(f'SELECT identity_state FROM artifact_domain_state WHERE vnum={ARTIFACT}') == '2',
                       'online swap did not retain its old UID tombstone')
                settle(lambda: sql(f'SELECT timer_epoch FROM artifact_domain_state WHERE vnum={SWAP_LIVE}') == str(expected_timer),
                       'online replacement lost its timer')
                live_uid = int(sql(f'SELECT canonical_item_uid FROM artifact_domain_state WHERE vnum={SWAP_LIVE}'))
                assert live_uid != old_uid
                assert re.search(r'Number in game\s*:\s*1\b', command(god, f'stat obj {SWAP_LIVE}'))
                assert re.search(r'Number in game\s*:\s*0\b', command(god, f'stat obj {ARTIFACT}'))
                player.send('save'); player.expect('Save complete for ' + PLAYER + '.', timeout=60)
                settle(lambda: sql(f'SELECT COUNT(*) FROM player_items WHERE pid={source_pid} AND obj_uid={live_uid}') == '1',
                       'online replacement payload did not save')
                stop()
                boot(); god = login(GOD, GOD_ACCOUNT)
                god.send(f'artifacts swap {SWAP_LIVE} {SWAP_OFFLINE}')
                god.expect('swapped with artifact', timeout=60)
                settle(lambda: sql(f'SELECT identity_state FROM artifact_domain_state WHERE vnum={SWAP_LIVE}') == '2',
                       'offline swap did not retire its requested UID')
                settle(lambda: sql(f'SELECT timer_epoch FROM artifact_domain_state WHERE vnum={SWAP_OFFLINE}') == str(expected_timer),
                       'offline replacement lost its timer')
                final_uid = int(sql(f'SELECT canonical_item_uid FROM artifact_domain_state WHERE vnum={SWAP_OFFLINE}'))
                assert final_uid not in (old_uid, live_uid)
                settle(lambda: sql(f'SELECT COUNT(*) FROM player_items WHERE pid={source_pid} AND vnum={SWAP_OFFLINE} AND obj_uid={final_uid}') == '1',
                       'offline replacement payload did not save')
                assert sql(f'SELECT COUNT(*) FROM player_items WHERE pid={source_pid} AND obj_uid IN ({old_uid},{live_uid})') == '0'
                assert re.search(r'Number in game\s*:\s*0\b', command(god, f'stat obj {SWAP_OFFLINE}'))
                stop()
                boot(); god = login(GOD, GOD_ACCOUNT); player = login(PLAYER, ACCOUNT)
                assert 'ioun stone' in command(player, 'equipment')
                assert re.search(r'Number in game\s*:\s*1\b', command(god, f'stat obj {SWAP_OFFLINE}'))
                assert sql(f'SELECT canonical_item_uid,identity_state,timer_epoch FROM artifact_domain_state WHERE vnum={SWAP_OFFLINE}') == f'{final_uid}\t1\t{expected_timer}'
                assert sql('SELECT COUNT(*) FROM artifact_guild_outcome') == before_restart['history']
                evidence['canonical_online_offline_swap_admission'] = {
                    'source_uid': old_uid, 'online_uid': live_uid, 'offline_uid': final_uid,
                    'timer_preserved': True, 'final_live_count': 1,
                    'atomic_crash_windows_qualified': False,
                }
                stop()
                assert retained_source_intact(), 'load/save/copyover/restart lost or claimed retained source rows'
                evidence['retained_source_survived_without_claim'] = True
                evidence['clean_restart'] = True
                target = ROOT / 'bin/analysis/artifact-estale'
                target.mkdir(parents=True, exist_ok=True)
                (target / 'gameplay-journey.json').write_text(json.dumps(evidence, indent=2) + '\n')
                print('PASS Summon Ghasts -> three feeds/guild threshold -> copyover/restart -> canonical online/offline swaps', flush=True)
            except Exception as error:
                failure = ROOT / 'bin/analysis/artifact-estale' / f'failure-{case}-{time.time_ns()}'
                failure.mkdir(parents=True)
                shutil.copy2(output_path, failure / 'server.out')
                shutil.copytree(runtime / 'logs', failure / 'logs')
                (failure / 'journey-state.json').write_text(json.dumps(evidence, indent=2) + '\n')
                for source in (runtime / 'copyover.dat', runtime / 'copyover.dat.recovering'):
                    if source.is_file():
                        shutil.copy2(source, failure / source.name) # private synthetic handoff evidence
                (failure / 'process.txt').write_text(f'pid={process.pid if process else None} returncode={process.poll() if process else None}\n')
                print(f'artifact journey failure evidence: {failure}', flush=True)
                traces = '\n'.join(bytes(c.transcript[-6000:]).decode(errors='replace') for c in clients)
                raise AssertionError(str(error) + '\n' + traces + '\n' +
                                     output_path.read_text(errors='replace')[-6000:]) from error
            finally:
                barrier.unlink(missing_ok=True)
                if locker and locker.poll() is None:
                    locker.terminate(); locker.wait(timeout=10)
                for client in clients:
                    client.close()
                if process and process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        process.kill(); process.wait(timeout=10)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--server', type=Path, default=ROOT / 'bin/server/dms_new')
    parser.add_argument('--case', choices=('all', *CASES), default='all')
    args = parser.parse_args()
    if not os.getenv('TEST_DB_HOST'):
        print('artifact/guild gameplay journey skipped: TEST_DB_HOST is not set')
    else:
        (ROOT / 'bin/tests').mkdir(parents=True, exist_ok=True)
        for case in CASES if args.case == 'all' else (args.case,):
            run(args.server.resolve(), case)
