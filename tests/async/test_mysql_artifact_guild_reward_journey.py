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
        inserted = original.group().replace('#900\n', f'#{ARTIFACT}\n', 1)
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

            def login(name, account):
                client = journey.reconnect_character(plain, expected_room=None, account=account, character=name)
                clients.append(client)
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
                process.send_signal(signal.SIGUSR1)
                player.expect('Copyover complete!', timeout=180)
                god.expect('Copyover complete!', timeout=180)
                assert saved_state() == after, 'copyover changed persisted reward state/history'
                assert sql(f'SELECT COALESCE(canonical_item_uid,0),identity_state FROM artifact_domain_state WHERE vnum={ARTIFACT}') == identity_before
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
                player = login(PLAYER, ACCOUNT)
                assert 'ioun stone' in command(player, 'equipment')
                assert saved_state() == before_restart, 'restart changed persisted reward state/history'
                assert 'artifact_guild live_applied=0' in command(god, 'world persistence')
                stop()
                evidence['clean_restart'] = True
                target = ROOT / 'bin/analysis/artifact-estale'
                target.mkdir(parents=True, exist_ok=True)
                (target / 'gameplay-journey.json').write_text(json.dumps(evidence, indent=2) + '\n')
                print('PASS Summon Ghasts -> actual kills/boons -> three feeds and cumulative guild threshold; clean restart', flush=True)
            except Exception as error:
                failure = ROOT / 'bin/analysis/artifact-estale' / f'failure-{case}-{time.time_ns()}'
                failure.mkdir(parents=True)
                shutil.copy2(output_path, failure / 'server.out')
                shutil.copytree(runtime / 'logs', failure / 'logs')
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
