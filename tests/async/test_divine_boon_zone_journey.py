#!/usr/bin/env python3
"""One isolated loaded-world Divine campaign per backend.

Exercise cutover/hourly selection, real trade shops, a real payable stone, NPC
combat EXP, legitimate PvP held across expiry, pause and saved restart/login.
Only fixture processes receive the test clock. Stone/EXP/PvP objectives and actor
levels are seeded offline; the saved ship moves between real endpoints offline.
The flat expiry leg requires GDB and an unstripped debug server.
Weighted policy and navigation controls retain their separate focused evidence.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import subprocess
import tempfile
import time
import test_flatfile_combat_journey as journey
from test_flight_network_journey import authority, command
from run_world_quest_dual_backend import setup_run_root
ROOT = journey.ROOT
GOD, GOD_ACCOUNT = ('Boonwarden', 'Boonstaff')
PORTS = [559633,635260,88846,82669,66689,9967,22441,49090,43158,83786]
SEED = json.loads((ROOT / 'migrations/seeds/epic_zone_payouts.json').read_text())['zones']


def build_campaign_helper(output):
    sources=['tests/async/divine_boon_campaign_fixture.cpp','src/economy/divine_boon.c',
             'src/economy/divine_boon_repository.c','src/economy/divine_trade.c',
             'src/economy/divine_trade_repository.c','src/economy/divine_trade_flatfile.c',
             'src/flatfile/flatfile_ship_repository.c','src/flatfile/flatfile_identity_repository.c',
             'src/flatfile/flatfile_player_snapshot_file.c','src/player/player_snapshot_codec.c',
             'src/flatfile/flatfile_player_domain_repository.c', 'src/economy/divine_boon_delivery.c',
             'src/combat/combat_outcome_command.c', 'src/world/zone_touch_command.c',
             'src/flatfile/flatfile_authority_transaction.c','src/flatfile/flatfile_store.c',
             'src/persistence/critical_command.c']
    subprocess.run(['g++','-std=c++20','-g','-Og','-ffunction-sections','-fdata-sections',
                    '-Isrc','-I/usr/include/mysql',*sources,'-Wl,--gc-sections','-lcrypto',
                    '-lmysqlclient','-pthread','-o',str(output)],cwd=ROOT,check=True)


def stone_site(zone):
    current = None
    mob = None
    room = None
    for line in (ROOT / zone['source']).read_text(encoding='latin-1').splitlines():
        if line.startswith('#'):
            current = int(line[1:])
        fields = line.split()
        if current != zone['number'] or len(fields) < 6:
            continue
        if fields[0] == 'M':
            mob, room = int(fields[2]), int(fields[4])
        if fields[0] in ('O', 'G') and fields[2] in ('358', '359', '360'):
            if fields[0] == 'O':
                return int(fields[4]), None
            mobile = (ROOT / 'areas/world.mob').read_text(encoding='latin-1').split('#' + str(mob) + '\n', 1)[1]
            return room, mobile.split('~', 1)[0].split()[0]
    return None


def experience_site(zone):
    current = None
    for line in (ROOT / 'areas/world.zon').read_text(encoding='latin-1').splitlines():
        if line.startswith('#'):
            current = int(line[1:])
        fields = line.split()
        if current == zone and len(fields) >= 6 and fields[0] == 'M' and int(fields[2]) > 0 and int(fields[4]) > 0:
            mob, room = int(fields[2]), int(fields[4])
            mobile = (ROOT / 'areas/world.mob').read_text(encoding='latin-1').split('#' + str(mob) + '\n', 1)[1]
            return room, mob, mobile.split('~', 1)[0].split()[0]
    raise AssertionError('No actual NPC reset in experience zone ' + str(zone))


def run(backend, binary):
    # Exact source-native expectations cover the 200% base and 220/160 additive
    # stacks; the loaded-world delta below must be NPC-only, before PvP can pay.
    subprocess.run(['python3', str(ROOT / 'tests/async/test_world_quest_xp_feedback.py')], cwd=ROOT, check=True)

    if backend == 'flatfile' and not shutil.which('gdb'):
        raise SystemExit('The flat expiry fixture requires GDB and an unstripped debug server')
    if backend == 'mariadb' and (not os.getenv('TEST_DB_HOST')):
        raise SystemExit('MariaDB requires with_disposable_mariadb.sh')
    output_root = ROOT / 'bin/tests'
    output_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='divine-zone-', dir=output_root) as temporary:
        runtime = Path(temporary)
        _, critical, output_path = setup_run_root(runtime)
        (runtime / 'help').symlink_to(ROOT / 'help', target_is_directory=True)
        (runtime / 'bin/server').mkdir(parents=True)
        executable = runtime / 'bin/server/dms'
        shutil.copy2(binary, executable)
        with (runtime / 'lib/misc/event_names').open('w') as names:
            subprocess.run([str(ROOT / 'scripts/event_names.sh'), str(executable)], stdout=names, check=True)
        plain, tls, websocket = journey.available_ports()
        clients = []
        process = None
        game_pid = None
        debug_pid = runtime / "debug-pid"
        prepared_gate = runtime / "pvp-prepared"
        release_gate = runtime / "pvp-hold"
        campaign = runtime / 'campaign-fixture'
        build_campaign_helper(campaign)
        clock = runtime / 'clock.so'
        clock_file = runtime / 'clock-offset'
        epoch = int(time.time()) // 3600 * 3600 + 60
        clock_file.write_text(str(epoch))
        subprocess.run(['gcc', '-shared', '-fPIC', 'tests/async/divine_boon_campaign_clock.c', '-o', str(clock)], cwd=ROOT, check=True)
        with authority(backend, runtime) as (env, sql), output_path.open('w') as output:
            env.update(LD_PRELOAD=str(clock), DURIS_TEST_CLOCK_FILE=str(clock_file), CRITICAL_COMMAND_JOURNAL_DIR=str(critical), DURIS_TLS_PORT=str(tls), DURIS_WEBSOCKET_PORT=str(websocket), MAINTENANCE_STATE_FILE=str(runtime / 'maintenance.state'))

            def fixture(action, *extra):
                return subprocess.check_output([str(campaign), backend, str(runtime / 'state'), action, GOD, *map(str, extra)], env=env, text=True)

            def actor_fixture(action, name, *extra):
                return subprocess.check_output([str(campaign), backend, str(runtime / 'state'), action, name, *map(str, extra)], env=env, text=True)

            def boot(debug=False):
                nonlocal process, game_pid
                offset = output_path.stat().st_size
                arguments = [str(executable), '-d', str(runtime), str(plain)]
                launch_env = env
                if debug:
                    # Stop the game before coordinator admission, after the
                    # immutable combat award has been prepared. A global flat
                    # authority lock would also block unrelated game-thread I/O.
                    script = runtime / 'pvp.gdb'
                    lines = ['set pagination off', 'set confirm off', 'set startup-with-shell off',
                             'handle SIGTERM nostop noprint pass',
                             'set environment LD_PRELOAD = ' + str(clock),
                             'tbreak main', 'commands', 'silent', 'python',
                             f'open({str(debug_pid)!r}, "w").write(str(gdb.selected_inferior().pid))',
                             'end', 'continue', 'end',
                             'break critical_command_coordinator_submit',
                             'condition 2 command.type == critical_command_type::combat_outcome',
                             'commands', 'silent', 'python', 'import os, time',
                             f'open({str(prepared_gate)!r}, "w").write("prepared")',
                             f'while os.path.exists({str(release_gate)!r}): time.sleep(.01)',
                             'end', 'continue', 'end', 'run']
                    script.write_text('\n'.join(lines) + '\n')
                    arguments = ['gdb', '--batch', '--return-child-result', '-x', str(script), '--args', *arguments]
                    launch_env = dict(env)
                    launch_env.pop('LD_PRELOAD', None)
                process = subprocess.Popen(arguments, cwd=runtime, env=launch_env, stdout=output, stderr=subprocess.STDOUT)
                game_pid = process.pid
                deadline = time.monotonic() + 180
                while b'Entering game loop.' not in output_path.read_bytes()[offset:]:
                    assert process.poll() is None and time.monotonic() < deadline, 'world failed to boot'
                    time.sleep(0.1)
                if debug:
                    game_pid = int(debug_pid.read_text())

            def stop():
                for client in clients:
                    client.close()
                clients.clear()
                os.kill(game_pid, signal.SIGTERM)
                process.wait(timeout=60)
                assert process.returncode == 0

            def create(name, account, race_name="h"):
                client = journey.MudClient(plain, source_host=None if name == GOD else '127.0.0.3' if name == 'Boonvictim' else '127.0.0.2')
                clients.append(client)
                journey.create_character(client, expected_room=None, account=account, character=name, email=name.lower() + '@example.invalid', race_name=race_name)
                command(client, 'toggle paging no')
                return client

            def login(name, account):
                client = journey.reconnect_character(plain, expected_room=None, account=account, character=name, source_host=None if name == GOD else '127.0.0.3' if name == 'Boonvictim' else '127.0.0.2')
                clients.append(client)
                client.expect('Welcome to Duris', timeout=60)
                client.expect_any(('Pos: standing >', '<>'), timeout=20)
                command(client, 'toggle paging no')
                return client

            def save(client, name):
                client.send('save')
                client.expect('Save complete for ' + name + '.', timeout=60)
            try:
                boot()
                god = create(GOD, GOD_ACCOUNT)
                shown = command(god, 'boon')
                assert 'The Gods of Duris have given you and your allies' in shown, shown
                for topic in ('boon', 'divine boons'):
                    helped = command(god, 'help ' + topic)
                    assert '200%' in helped and 'three times' in helped, helped

                save(god, GOD)
                stop()
                if sql:
                    sql("UPDATE player_data SET level=62,highest_level=62 WHERE name='" + GOD + "'")
                    sql(';'.join(f"UPDATE zones SET epic_payout={z['epic_payout']},suggested_group_size=100,alignment=0 WHERE number={z['number']}" for z in SEED))
                else:
                    journey.make_overlord(runtime / 'state', GOD)
                boot()
                god = login(GOD, GOD_ACCOUNT)
                clock_file.write_text(str(epoch + 3600))
                # The real hourly selector has no warmed player population here:
                # it must select a valid global cargo route, without a test RNG.
                deadline = time.monotonic() + 15
                while True:
                    rotated = command(god, 'boon')
                    if 'Cargo & contraband' in rotated:
                        break
                    assert time.monotonic() < deadline, rotated
                    time.sleep(.2)
                # Stones initialize on their existing object periodic event (up to
                # PULSE_MOBILE+4 pulses after boot), not at catalogue construction.
                deadline = time.monotonic() + 15
                target = None
                while target is None:
                    status = command(god, 'world persistence')
                    eligible = {int(z): side for side, z in re.findall(r'divine_target side=(good|evil) zone=(\d+)', status)}
                    target = next((z for z in SEED if z['number'] in eligible and stone_site(z) is not None), None)
                    assert target or time.monotonic() < deadline, 'No reachable payable ground stone: ' + status
                    if target is None:
                        time.sleep(.5)
                routes = re.search(r'divine_routes count=(\d+) shared=(\d+) first_source=(-?\d+) first_destination=(-?\d+)', status)
                print('Loaded route catalogue: ' + (routes.group(0) if routes else 'missing'), flush=True)
                zone, payout = target['number'], target['epic_payout']
                room, carrier = stone_site(target)
                side = 1 if eligible[zone] == 'evil' else 0
                exp_zones = [int(z) for faction, z in re.findall(r'divine_exp side=(good|evil) zone=(\d+)', status) if faction == ('evil' if side else 'good') and int(z) != zone]
                assert exp_zones, 'No eligible experience target: ' + status
                exp_zone = exp_zones[0]
                exp_room, exp_mob, exp_keyword = experience_site(exp_zone)
                stop()
                rotated = fixture('inspect')
                route = re.search(r'ROUTE (\d+) (\d+)', rotated)
                assert route, rotated
                source, destination = map(int, route.groups())
                fixture('seed', source)
                helper = runtime / 'zone-fixture'
                flags = shlex.split(subprocess.check_output(['mysql_config', '--cflags'], text=True))
                libraries = shlex.split(subprocess.check_output(['mysql_config', '--libs'], text=True))
                subprocess.run(['g++', '-std=c++20', '-Isrc', *flags, 'tests/async/divine_boon_zone_fixture.cpp',
                    'src/economy/divine_boon.c', 'src/economy/divine_boon_repository.c',
                    'src/flatfile/flatfile_authority_transaction.c', 'src/flatfile/flatfile_store.c',
                    '-lcrypto', '-pthread', *libraries, '-o', str(helper)], cwd=ROOT, check=True)
                subprocess.run([str(helper), backend, str(runtime / 'state'), str(zone), str(side)], env=env, check=True)
                boot()
                god = login(GOD, GOD_ACCOUNT)
                command(god, f'goto {PORTS[source]}')
                deadline = time.monotonic() + 30
                while fixture('ready').strip() != 'READY':
                    assert time.monotonic() < deadline, 'crew normalization did not persist'
                    time.sleep(.1)
                for goods, quantity in (('cargo', 6), ('contraband', 1)):
                    god.send(f'buy {goods} {quantity}')
                    god.expect('Your cargo trade is complete: paid', timeout=60)
                save(god, GOD)
                stop()
                bought = fixture('inspect')
                assert 'BOOK 10 0 2' in bought, bought
                fixture('move', destination)
                boot()
                god = login(GOD, GOD_ACCOUNT)
                command(god, f'goto {PORTS[destination]}')
                for goods in ('cargo', 'contraband'):
                    god.send('sell ' + goods)
                    god.expect('Your cargo trade is complete: received', timeout=60)
                save(god, GOD)
                stop()
                sold = fixture('inspect')
                assert 'BOOK 10 7 0' in sold, sold
                boot()
                god = login(GOD, GOD_ACCOUNT)
                # The fixture relocates the saved ship between real port shops;
                # this tests actual trade/persistence, not navigation controls.
                print(f'{backend}: real route {source}->{destination}, both goods, restart, fixed hold=10 consumed=7', flush=True)
                status = command(god, 'divineboon status')
                assert 'mode=divine' in status and 'paused=yes' in status, status
                command(god, 'divineboon resume')
                deadline = time.monotonic() + 10
                while 'paused=no' not in command(god, 'divineboon status'):
                    assert time.monotonic() < deadline
                command(god, 'divineboon pause')
                deadline = time.monotonic() + 10
                while 'paused=yes' not in command(god, 'divineboon status'):
                    assert time.monotonic() < deadline
                name, account = 'Boonpupil', 'Boonplayer'
                player = create(name, account, "o" if side else "h")
                command(god, f'goto {room}')
                if carrier:
                    given = command(god, f'force {carrier} give rune-covered {GOD}')
                    assert 'gives' in given, given
                command(god, 'purge')
                command(god, 'transfer ' + name)
                if carrier:
                    command(god, 'give rune-covered ' + name)
                    player.expect('gives you', timeout=30)
                player.send('touch rune-covered')
                player.expect('You have gained ', timeout=60)
                tail = player.expect('epic point', timeout=30)
                match = re.search(r'(\d+) epic point', tail)
                assert match, tail
                amount = int(match.group(1))
                print(f'{backend}: real eligible zone {zone} award={amount}, base={payout}', flush=True)
                assert amount == int(payout * 1.5), 'Prepared boon was not applied at the real stone'
                save(player, name)
                victim = create('Boonvictim', 'Boonopponent', 'h' if side else 'o')
                save(victim, 'Boonvictim')
                stop()
                actor_fixture('fighter', name)
                actor_fixture('fighter', 'Boonvictim')
                actor_fixture('objectives', GOD, side, exp_zone)
                properties = dict(line.split('=', 1) for line in (runtime / 'lib/duris.properties').read_text().splitlines() if '=' in line and not line.lstrip().startswith('#'))
                pvp_base = max(float(properties.get('epic.frag.minimum.epics', '100')), min(float(properties.get('epic.frag.maximum.epics', '1500')), float(properties.get('epic.frag.amount', '20')) * (float(properties.get('frag.evil.penalty', '.666')) if side else 1)))
                pvp_base = int(pvp_base)
                pvp_award = pvp_base * 3 // 2
                before_xp = int(re.search(r'XP (\d+)', actor_fixture('player', name)).group(1))
                boot(debug=backend == 'flatfile')
                god = login(GOD, GOD_ACCOUNT)
                player = login(name, account)
                victim = login('Boonvictim', 'Boonopponent')
                # Native combat in a validated, non-town EXP target. Exact stacking
                # and every contributor remain covered by the native math harness.
                command(god, f'goto {exp_room}')
                command(god, 'purge')
                command(god, 'transfer ' + name)
                command(god, f'load mob {exp_mob}')
                command(god, f'setattr {name} str 250')
                command(god, f'setattr {name} dex 250')
                player.send('kill ' + exp_keyword)
                player.expect('punch', timeout=30)
                command(god, f'goto {room}')
                command(god, 'transfer ' + name)
                command(god, f'goto {exp_room}')
                command(god, 'purge')
                command(god, 'transfer ' + name)
                save(player, name)
                npc_xp = int(re.search(r'XP (\d+)', actor_fixture('player', name)).group(1))
                assert npc_xp > before_xp, ('NPC-only XP did not increase', before_xp, npc_xp)
                print(f'{backend}: NPC-only combat XP {before_xp}->{npc_xp}; exact Divine amount oracle passed', flush=True)
                # A distinct, normally created opposing mortal, above the normal
                # level-20 frag threshold, dies through the real combat producer.
                command(god, 'transfer Boonvictim')
                command(god, 'setattr Boonvictim dex 1')
                command(god, 'setattr Boonvictim agi 1')
                wounded = command(victim, 'score')
                hp = re.search(r'Hit points:\s*(\d+)\((\d+)\)', wounded)
                assert hp, wounded
                # setattr's legacy max-hit edit is rebalanced immediately,
                # preserving the missing-HP difference. Prepare one remaining
                # HP without changing the victim's level or reward eligibility.
                command(god, 'setattr Boonvictim hit ' + str(sum(map(int, hp.groups())) - 1))
                wounded = command(victim, 'score')
                assert re.search(r'Hit points:\s*1\(', wounded), wounded
                # Hold only the isolated persistence authority while combat
                # prepares its award. Let the real expiry pass before committing.
                holder = None
                saw_prepared = False
                if backend == 'flatfile':
                    prepared_gate.unlink(missing_ok=True)
                    release_gate.write_text('hold')
                else:
                    holder = subprocess.Popen([str(campaign), backend, str(runtime / 'state'), 'hold', name], env=env, text=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
                try:
                    if holder:
                        assert holder.stdout.readline().strip() == 'LOCKED'
                    deadline = time.monotonic() + 30
                    next_attack = 0
                    while b'Your wounds claim you at last' not in victim.pending:
                        assert time.monotonic() < deadline, 'PvP finishing blows did not complete'
                        if prepared_gate.exists() and release_gate.exists():
                            clock_file.write_text(str(epoch + 5 * 3600))
                            release_gate.unlink()
                            saw_prepared = True
                        if time.monotonic() >= next_attack:
                            player.send('kill ' + ('human' if side else 'orc'))
                            next_attack = time.monotonic() + .8
                        victim._receive()
                        time.sleep(.05)
                    victim.expect('Your wounds claim you at last', timeout=5)
                    if backend == 'flatfile':
                        assert saw_prepared, 'Debugger did not stop the prepared PvP command'
                    else:
                        clock_file.write_text(str(epoch + 5 * 3600))
                finally:
                    release_gate.unlink(missing_ok=True)
                    if holder:
                        holder.communicate('release\n', timeout=20)
                        assert holder.returncode == 0
                player.expect('You just gained', timeout=60)
                deadline = time.monotonic() + 20
                while True:
                    score = command(player, 'score')
                    if f'Epic points(total): {amount + pvp_award}(' in score:
                        break
                    assert time.monotonic() < deadline, score
                amount += pvp_award
                save(player, name)
                stop()
                after_xp = int(re.search(r'XP (\d+)', actor_fixture('player', name)).group(1))
                assert after_xp >= npc_xp, (npc_xp, after_xp)
                print(f'{backend}: actual NPC combat zone {exp_zone}, NPC-only XP {before_xp}->{npc_xp}; legitimate PvP base {pvp_base}->{pvp_award} paid after expiry', flush=True)
                boot()
                player = login(name, account)
                score = command(player, 'score')
                assert f'Epic points(total): {amount}(' in score, score
                god = login(GOD, GOD_ACCOUNT)
                # Four hours passed while the real PvP payment was held above.
                # Expired short events stay absent through restart and pause;
                clock_file.write_text(str(epoch + 5 * 3600))
                deadline = time.monotonic() + 15
                while True:
                    expired = command(god, 'boon')
                    if 'Cargo & contraband' not in expired and 'Opposing racewar PvP' not in expired:
                        break
                    assert time.monotonic() < deadline, expired
                deadline = time.monotonic() + 15
                while True:
                    history = command(god, 'divineboon history')
                    if 'Cargo & contraband' in history and 'PvP' in history:
                        break
                    assert time.monotonic() < deadline, history
                print(f'PASS {backend}: cutover, hourly route, both goods, stone, NPC EXP, PvP, pause/expiry and saved restart/login', flush=True)
            except Exception as error:
                evidence = output_root / ('divine-zone-failure-' + backend + '-' + str(time.time_ns()))
                evidence.mkdir()
                shutil.copy2(output_path, evidence / 'server.out')
                shutil.copytree(runtime / 'logs', evidence / 'logs')
                transcripts = '\n'.join((bytes(c.transcript[-12000:]).decode(errors='replace') for c in clients))
                (evidence / 'clients.txt').write_text(transcripts)
                transcripts = transcripts[-1500:]
                raise AssertionError(f'{error}\nEvidence: {evidence}\n{transcripts}') from error
            finally:
                for client in clients:
                    client.close()
                release_gate.unlink(missing_ok=True)
                if process and process.poll() is None:
                    try:
                        os.kill(game_pid, signal.SIGTERM)
                    except ProcessLookupError:
                        process.terminate()
                    try:
                        process.wait(timeout=30)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=10)
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--backend', choices=['flatfile', 'mariadb'], required=True)
    parser.add_argument('--server', type=Path, required=True)
    args = parser.parse_args()
    run(args.backend, args.server.resolve())
