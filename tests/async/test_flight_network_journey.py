#!/usr/bin/env python3
"""Full-world flight discovery, tickets, copyover and restart on disposable authority.

Run under with_disposable_mariadb.sh; --server PATH uses an existing build.
Without --server, build the MariaDB server with its real 250 ms clock.
No checkout .env or running game is used.
"""
import argparse
from contextlib import contextmanager
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

import test_mariadb_combat_journey as journey
from run_world_quest_dual_backend import setup_run_root

ROOT = journey.ROOT
PLAYER, ACCOUNT = 'Flightrider', 'Flightacct'
GOD, GOD_ACCOUNT = 'Flightwarden', 'Flightstaff'
# Acceptance catalog, independent of the production C++ table.
STOPS = [
    (47016, 635756, 'Quietus Quay'), (47017, 588326, 'Storm Port'),
    (47018, 606262, 'Bloodstone Keep'), (47019, 514072, 'Myrabolus'),
    (47020, 582084, 'The City of Torrhan'), (47021, 543701, 'Ugta'),
    (47022, 545407, "Venan'Trut"), (47023, 563522, 'Fort Boyard'),
    (47024, 622276, "Sarmiz'Duul"), (47025, 519043, 'Fort Khoralator'),
    (47026, 543662, 'Kimordril'), (47028, 522247, 'Helgor Outpost'),
    (47029, 631413, 'Clan Shatter Stone'), (47030, 514279, 'Bone Fort Inn'),
    (47031, 533479, 'Winterhaven'), (47032, 584293, 'Shady Grove'),
    (47033, 570024, 'Tharnadia'), (47034, 529229, 'Fenaline'),
    (47035, 546144, 'Canderthal Harbor'), (47036, 575328, 'Nizari'),
    (47037, 641295, 'The Jade Empire'), (47038, 634060, "Dalvik's Dockyard"),
    (47039, 577835, 'Varathorn Keep'), (47040, 616547, "Thur'Gurax"),
    (47041, 557220, 'Moonshae Island'),
]
MASK = sum(1 << (mob - 47015) for mob, _, _ in STOPS)


@contextmanager
def authority(backend, runtime):
    with journey.mariadb_authority() as (env, sql):
        # The maintained importer reads only the copied fixture sources and explicit test DB.
        (runtime / 'scripts').mkdir()
        importer = runtime / 'scripts/import_help_to_prod.sh'
        shutil.copy2(ROOT / 'scripts/import_help_to_prod.sh', importer)
        imported = subprocess.run(['bash', str(importer), '--local'], input='yes\n',
                                  text=True, env=env, capture_output=True, timeout=90)
        assert imported.returncode == 0, imported.stdout[-4000:] + imported.stderr[-4000:]
        yield env, sql


def command(client, text, timeout=20):
    """A subsequent score response fences command completion, even while flying."""
    start = len(client.transcript)
    client.send(text)
    if text != 'score':
        client.send('score')
    client.expect('Score information for', timeout=timeout)
    client.expect('>', timeout=timeout)
    return bytes(client.transcript[start:]).decode(errors='replace')


def run(binary, backend, interruptions_only=False, reconnect_only=False, skip_interruptions=False):
    with tempfile.TemporaryDirectory(prefix='flight-' + backend + '-', dir=ROOT / 'bin/tests') as temporary:
        runtime = Path(temporary)
        _, critical, output_path = setup_run_root(runtime)
        (runtime / 'help').symlink_to(ROOT / 'help', target_is_directory=True)
        (runtime / 'bin/server').mkdir(parents=True)
        executable = runtime / 'bin/server/dms'
        shutil.copy2(binary, executable)
        executable.chmod(0o700)
        with (runtime / 'lib/misc/event_names').open('w') as names:
            subprocess.run([str(ROOT / 'scripts/event_names.sh'), str(executable)], stdout=names, check=True)
        properties = runtime / 'lib/duris.properties'
        properties.write_text(properties.read_text().replace('camp.timer=9.000', 'camp.timer=1.000'))
        plain, tls, websocket = journey.available_ports()
        process = None
        clients = []
        evidence = {'backend': backend, 'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest()}
        with authority(backend, runtime) as (env, sql), output_path.open('w') as output:
            env.update(CRITICAL_COMMAND_JOURNAL_DIR=str(critical), DURIS_TLS_PORT=str(tls),
                       DURIS_WEBSOCKET_PORT=str(websocket),
                       MAINTENANCE_STATE_FILE=str(runtime / 'maintenance.state'))

            def boot():
                nonlocal process
                offset = output_path.stat().st_size
                proc = subprocess.Popen([str(executable), '-d', str(runtime), str(plain)],
                                        cwd=runtime, env=env, stdout=output, stderr=subprocess.STDOUT)
                process = proc
                deadline = time.monotonic() + 180
                while b'Entering game loop.' not in output_path.read_bytes()[offset:]:
                    assert proc.poll() is None and time.monotonic() < deadline, 'flight world failed to boot'
                    time.sleep(.1)
                assert Path(os.readlink(f'/proc/{proc.pid}/exe')).resolve() == executable
                return proc

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
                # reconnect_character consumes the reconnect banner itself.
                if b'Reconnecting...' not in client.transcript:
                    client.expect('Welcome to Duris', timeout=60)
                client.expect_any(('Pos: standing >', '<>'), timeout=20)
                command(client, 'toggle paging no')
                command(client, 'look')
                return client

            def save(client, name=PLAYER):
                client.send('save')
                client.expect('Saving ' + name + '.', timeout=60)

            def progress():
                row = sql("SELECT learned_flight_stops,exp,level,copper,silver,gold,platinum FROM player_data WHERE name='" + PLAYER + "'")
                fields = [int(x) for x in row.split('\t')]
                return {'learned_flight_stops': fields[0], 'experience': fields[1],
                        'level': fields[2], 'wallet': fields[3:]}

            def visit(room):
                moved = command(god, 'goto ' + str(room))
                assert 'No room exists' not in moved, moved
                command(god, 'setbit room here flag ROOM_MAGIC_LIGHT 1')
                if room in (619771, 576577):
                    command(god, 'setbit room here flag SAFE 1')
                transferred = command(god, 'transfer ' + PLAYER)
                assert 'Ok.' in transferred, transferred

            def qualify_socket_reconnect():
                nonlocal player
                visit(582084)
                command(god, 'setbit char ' + PLAYER + ' platinum 1000')
                assert 'Here is your ticket' in command(player, 'buy 1')
                player.send('give ticket griffin')
                player.expect('launches', timeout=20)
                player.close()
                clients.remove(player)
                disconnected = command(god, 'stat char ' + PLAYER)
                assert 'Linkdead' in disconnected and 'RIDING' in disconnected, disconnected
                player = login(PLAYER, ACCOUNT)
                assert 'learned flight stops' in command(player, 'flights')
                player.expect('lands.', timeout=120)
                command(god, 'goto 582084')
                deadline = time.monotonic() + 120
                while 'Flight Service' not in command(god, 'list'):
                    assert time.monotonic() < deadline, 'carrier lost after socket reconnect'
                    time.sleep(.5)
                evidence['live_passenger_reconnected'] = True
                print(backend + ': socket loss retained a live passenger and reconnect completed the trip',
                      flush=True)

            def qualify_interruptions():
                nonlocal player
                # Use the real NPC kill/hit command path while the first movement
                # callback is still in its normal departure delay.
                for attacker_altitude in (0, 10):
                    visit(582084)
                    command(god, 'setbit char ' + PLAYER + ' platinum 1000')
                    assert 'Here is your ticket' in command(player, 'buy 1')
                    loaded = command(god, 'load mob 3220')
                    assert 'created' in loaded, loaded
                    command(god, 'setbit char rabbit npcact SENTINEL 1')
                    command(god, 'setbit char rabbit basehit 1000000')
                    command(god, 'restore rabbit')
                    command(god, 'setbit char rabbit zcord ' + str(attacker_altitude))
                    player.send('give ticket griffin')
                    player.expect('launches', timeout=20)
                    command(god, 'force rabbit kill ' + PLAYER)
                    state = command(god, 'stat char ' + PLAYER)
                    assert 'RIDING' in state, state
                    if attacker_altitude == 0:
                        assert re.search(r'Fighting:\s*---', state), state
                    else:
                        assert re.search(r'Fighting:\s*rabbit', state), state
                    command(god, 'peace')
                    command(god, 'purge rabbit')
                    player.expect('lands.', timeout=120)
                    command(god, 'goto 582084')
                    deadline = time.monotonic() + 120
                    while 'Flight Service' not in command(god, 'list'):
                        assert time.monotonic() < deadline, 'carrier lost after attack qualification'
                        time.sleep(.5)
                    print(backend + ': actual NPC attack at altitude ' + str(attacker_altitude) +
                          ' retained the paid ride', flush=True)
                evidence['npc_attack_altitudes'] = [0, 10]
                # Exercise complete command/extraction paths on Torrhan's reported service.
                # Staff privilege is temporary test setup to permit explicit interruption;
                # discovery, purchase and initial boarding still use the mortal path.
                original_level = progress()['level']
                for interruption in ('unlink', 'extract'):
                    visit(582084)
                    assert 'Flight Service' in command(player, 'list')
                    command(god, 'setbit char ' + PLAYER + ' platinum 1000')
                    assert 'Here is your ticket' in command(player, 'buy 1')
                    player.send('give ticket griffin')
                    player.expect('launches', timeout=20)
                    player.expect('flies ', timeout=20)
                    # A mortal can look/list known stops, but cannot leave the ride.
                    locked = command(player, 'dismount')
                    assert 'holding on for dear life' in locked, locked
                    assert 'learned flight stops' in command(player, 'flights')
                    command(god, 'setbit char ' + PLAYER + ' level 62')
                    if interruption == 'unlink':
                        unlinked = command(player, 'dismount')
                        assert 'You dismount' in unlinked, unlinked
                        # A new location must survive return of the now-empty carrier.
                        command(god, 'setbit char ' + PLAYER + ' zcord 0')
                        command(god, 'goto 543701')
                        assert 'Ok.' in command(god, 'transfer ' + PLAYER)
                    else:
                        player.send('quit')
                        player.expect('ACCOUNT MENU', timeout=30)
                        player.send('0')
                        player.close()
                        clients.remove(player)
                    command(god, 'goto 582084')
                    deadline = time.monotonic() + 90
                    while 'Flight Service' not in command(god, 'list'):
                        assert time.monotonic() < deadline, 'Torrhan carrier stranded after ' + interruption
                        time.sleep(.5)
                    carrier = command(god, 'stat mob griffin')
                    assert 'event_flying_transport_move' not in carrier, carrier
                    assert 'event_flying_transport_return' not in carrier, carrier
                    if interruption == 'extract':
                        player = login(PLAYER, ACCOUNT)
                    command(god, 'setbit char ' + PLAYER + ' level ' + str(original_level))
                    visit(582084)
                    assert 'Flight Service' in command(player, 'list')
                    assert 'Here is your ticket' in command(player, 'buy 1')
                    player.send('give ticket griffin')
                    player.expect('launches', timeout=20)
                    player.expect('lands.', timeout=120)
                    command(god, 'goto 582084')
                    deadline = time.monotonic() + 120
                    while 'Flight Service' not in command(god, 'list'):
                        assert time.monotonic() < deadline, 'Torrhan service did not return after reuse'
                        time.sleep(.5)
                    print(backend + ': Torrhan recovered and completed a new trip after ' + interruption,
                          flush=True)
                evidence['torrhan_outbound_interruptions'] = ['unlink_and_separate', 'passenger_extraction']
                qualify_socket_reconnect()

            try:
                process = boot()
                for name, account in ((PLAYER, ACCOUNT), (GOD, GOD_ACCOUNT)):
                    client = journey.MudClient(plain)
                    clients.append(client)
                    journey.create_character(client, expected_room=None, account=account,
                                             character=name, email=name.lower() + '@example.invalid')
                    save(client, name)
                assert progress()['learned_flight_stops'] == 0
                stop()
                if sql:
                    sql("UPDATE player_data SET level=62,highest_level=62 WHERE name='" + GOD + "'")
                process = boot()
                god = login(GOD, GOD_ACCOUNT)
                player = login(PLAYER, ACCOUNT)
                command(god, 'setbit char ' + PLAYER + ' platinum 25')
                command(god, 'setbit char ' + PLAYER + ' basehit 1000000')
                command(god, 'restore ' + PLAYER)
                if interruptions_only or reconnect_only:
                    for room in (582084, 575328):
                        visit(room)
                        assert 'Flight Service' in command(player, 'list')
                    if reconnect_only:
                        qualify_socket_reconnect()
                    else:
                        qualify_interruptions()
                    print(json.dumps(evidence, sort_keys=True), flush=True)
                    return
                help_text = command(player, 'help flights')
                assert 'Explore 25 ordinary flight stops' in help_text, help_text
                assert 'good side of the racewar' in help_text, help_text
                assert 'None yet' in command(player, 'flights')
                # All ordinary service mobs and corrected pads must be usable in the real world.
                for mob, room, name in STOPS:
                    visit(room)
                    listing = command(player, 'list')
                    assert 'You discover a flight stop: ' + name in listing, (mob, room, listing)
                    assert 'You discover' not in command(player, 'list'), 'repeat discovery awarded again'
                save(player)
                saved = progress()
                assert saved['learned_flight_stops'] == MASK, saved
                evidence['discovered_stops'] = len(STOPS)
                print(backend + ': all 25 ordinary stops discovered and checkpointed', flush=True)
                learned = command(player, 'flights')
                assert all(name in learned for _, _, name in STOPS), learned
                assert 'The Isle of Undeath' not in learned and 'Chief Blood-Eye' not in learned
                # A short real route exposes half-platinum pricing; record the wallet debit.
                visit(543701)
                command(god, 'setbit char ' + PLAYER + ' platinum 25')
                listing = command(player, 'list')
                route = re.search(r'^(\d+)\) Kimordril\s*- (\d+) rooms - ([^\r\n]+)', listing, re.M)
                assert route, listing
                choice, steps = int(route[1]), int(route[2])
                assert steps == 39 and '19 platinum' in route[3] and '5 gold' in route[3], route[0]
                save(player)
                before = progress()
                assert 'Here is your ticket' in command(player, f'buy {choice}')
                save(player)
                after = progress()
                money = lambda state: sum(value * factor for value, factor in zip(state['wallet'], (1, 10, 100, 1000)))
                assert money(before) - money(after) == steps * 500, (before, after)
                evidence['ordinary_wallet_before'] = before['wallet']
                evidence['ordinary_wallet_after'] = after['wallet']
                # A learned stop and an existing paid ticket cannot bypass the
                # Kimordril faction gate. Numeric alignment remains good here.
                command(god, 'setbit char ' + PLAYER + ' racewar 2')
                assert 'Kimordril' not in command(player, 'list')
                refused = command(player, 'give ticket griffin')
                assert 'not valid for a flight you can take' in refused, refused
                assert 'ticket' in command(player, 'inventory').lower()
                save(player)
                assert progress()['wallet'] == after['wallet']
                command(god, 'setbit char ' + PLAYER + ' racewar 1')
                assert 'Kimordril' in command(player, 'list')
                evidence['kimordril_evil_refused'] = True
                # The real dispatcher skips an immobile carrier's special procedure.
                # Ordinary give must still retain the paid ticket, without another debit.
                command(god, 'setbit char griffin aff2 MINOR_PARA 1')
                carrier = command(god, 'stat mob griffin')
                assert 'MINOR_PARA' in carrier, carrier
                refused = command(player, 'give ticket griffin')
                assert 'not ready to depart' in refused, refused
                assert 'ticket' in command(player, 'inventory').lower()
                carrier = command(god, 'stat mob griffin')
                assert 'a flight ticket' not in carrier.lower(), carrier
                save(player)
                assert progress()['wallet'] == after['wallet']
                command(god, 'setbit char griffin aff2 MINOR_PARA 0')
                evidence['immobile_ticket_retained'] = True
                player.send('give ticket griffin')
                player.expect('launches', timeout=20)
                player.expect('flies ', timeout=20)
                assert 'Kimordril' in command(player, 'flights')
                # Occupied flight recovery keeps the socket, discovery status, rider and path.
                process.send_signal(signal.SIGUSR1)
                player.expect('Copyover complete!', timeout=180)
                assert 'Kimordril' in command(player, 'flights')
                player.expect('lands.', timeout=90)
                assert 'A Rocky Mountain Clearing' in command(player, 'look')
                # An empty returning carrier is recovered as well.
                process.send_signal(signal.SIGUSR1)
                player.expect('Copyover complete!', timeout=180)
                visit(543701)
                deadline = time.monotonic() + 90
                while 'Kimordril' not in command(player, 'list'):
                    assert time.monotonic() < deadline, 'returning carrier did not resume its service'
                    time.sleep(.5)
                save(player)
                copied = progress()
                assert copied['wallet'] == after['wallet'], ('wallet changed through copyover', after, copied)
                evidence['ordinary_route_steps'] = steps
                evidence['copyovers'] = 2
                print(backend + ': occupied flight and empty return survived copyover', flush=True)
                # Land and extract the passenger before the empty return completes.
                # No copyover/reconciliation may rescue this carrier.
                command(god, 'goto 543662')
                command(god, 'setbit room here flag SAFE 1')
                command(god, 'goto 543701')
                command(god, 'setbit char ' + PLAYER + ' platinum 25')
                assert 'Here is your ticket' in command(player, f'buy {choice}')
                player.send('give ticket griffin')
                player.expect('launches', timeout=20)
                player.expect('lands.', timeout=90)
                player.send('quit')
                player.expect('ACCOUNT MENU', timeout=30)
                player.send('0')
                player.close()
                clients.remove(player)
                deadline = time.monotonic() + 30
                while 'Flight Service' not in command(god, 'list'):
                    assert time.monotonic() < deadline, 'logout canceled the empty carrier return'
                    time.sleep(.5)
                player = login(PLAYER, ACCOUNT)
                visit(543701)
                assert 'Kimordril' in command(player, 'list')
                evidence['return_after_logout'] = True
                print(backend + ': immobile ticket retained and empty return survived logout', flush=True)
                if not skip_interruptions:
                    qualify_interruptions()
                # Dedicated services do not discover anything and keep their level gates.
                for room, keyword, destination, fare in (
                    (619771, 'krrlytstalarryn', 'Cavern', 50),
                    (576577, 'corrosyvile', 'Desolate Island', 200),
                ):
                    command(god, 'setbit char ' + PLAYER + ' level 1')
                    visit(room)
                    assert 'No destinations available' in command(player, 'list')
                    assert 'Invalid choice' in command(player, 'buy 1')
                    command(god, 'setbit char ' + PLAYER + ' level 51')
                    command(god, 'setbit char ' + PLAYER + ' platinum ' + str(fare))
                    # The existing caster dragon can turn invisible between boots.
                    command(god, 'setbit char ' + PLAYER + ' aff DET_INV 1')
                    listing = command(player, 'list')
                    assert destination in listing and f'{fare} platinum' in listing and 'one-way' in listing
                    assert 'You discover' not in listing
                    assert 'Here is your ticket' in command(player, 'buy 1')
                    player.send('give ticket ' + keyword)
                    player.expect('launches', timeout=20)
                    player.expect('lands.', timeout=120)
                    assert 'Flight Service' not in command(player, 'list'), 'epic entrance has a return service'
                    save(player)
                    assert progress()['learned_flight_stops'] == MASK
                    print(backend + ': restricted ' + destination + ' trip completed', flush=True)
                # Durable discovery and EXP survive a crash; relogging and revisiting cannot award again.
                visit(543662)
                save(player)
                saved = progress()
                stop(crash=True)
                process = boot()
                god = login(GOD, GOD_ACCOUNT)
                player = login(PLAYER, ACCOUNT)
                known = command(player, 'flights')
                assert all(name in known for _, _, name in STOPS)
                visit(543662)
                assert 'You discover' not in command(player, 'list')
                save(player)
                loaded = progress()
                assert loaded['learned_flight_stops'] == saved['learned_flight_stops']
                assert loaded['experience'] == saved['experience'] and loaded['level'] == saved['level'], (saved, loaded)
                # A normal logout/login, without a server restart, also retains progress.
                command(god, 'setbit room here flag SAFE 1')
                player.send('quit')
                player.expect('ACCOUNT MENU', timeout=90)
                player.send('0')
                player.close()
                clients.remove(player)
                player = login(PLAYER, ACCOUNT)
                visit(543662)
                assert 'You discover' not in command(player, 'list')
                save(player)
                relogged = progress()
                assert relogged['learned_flight_stops'] == saved['learned_flight_stops']
                assert relogged['experience'] == saved['experience']
                print(backend + ': crash recovery and normal relog retain discovery and EXP', flush=True)
                # Named service dragons keep the ordinary death/corpse path for builder quests.
                command(god, 'remove all')
                for room, keyword in ((576577, 'corrosyvile'), (563522, 'azerathrax'),
                                      (619771, 'krrlytstalarryn'), (514279, 'cryoss'),
                                      (575328, 'aurumax'), (641295, 'verdax'), (557220, 'glimmyris')):
                    command(god, 'goto ' + str(room))
                    killed = command(god, 'kill ' + keyword)
                    assert 'still beating heart' in killed, killed
                    corpse = command(god, 'stat object corpse')
                    assert 'Type: CORPSE' in corpse and keyword in corpse.lower(), corpse
                evidence['named_dragon_corpses'] = 7
                stop()
                # Address retention can rotate the earlier boots' records during
                # this journey. Include that history when measuring every boot.
                status_logs = [runtime / 'logs/log/status',
                               *sorted((runtime / 'logs/old-logs').glob('*/status'))]
                status = '\n'.join(path.read_text(errors='replace') for path in status_logs)
                times = re.findall(r'Flight network: 27 services, 603 routes, 603 available; paths prepared in (\d+) ms', status)
                assert len(times) >= 4, re.findall(r'Flight network:[^\n]*', status)
                evidence['path_prepare_ms'] = [int(value) for value in times]
                print(json.dumps(evidence, sort_keys=True), flush=True)
            except BaseException:
                for client in clients:
                    print(bytes(client.transcript[-7000:]).decode(errors='replace'), flush=True)
                print(output_path.read_text(errors='replace')[-9000:], flush=True)
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
                        process.wait(timeout=10)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend', choices=('mariadb',), default='mariadb')
    parser.add_argument('--server', type=Path)
    focus = parser.add_mutually_exclusive_group()
    focus.add_argument('--interruptions-only', action='store_true',
                       help='qualify transport interruptions using two discovered stops')
    focus.add_argument('--reconnect-only', action='store_true',
                       help='qualify socket reconnect with a live paid-flight passenger')
    args = parser.parse_args()
    if args.interruptions_only:
        # Exit through run()'s cleanup when the route journey stops this child.
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
    subprocess.run(['make', 'world'], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    (ROOT / 'bin/tests').mkdir(parents=True, exist_ok=True)
    interruptions = None
    if not (args.interruptions_only or args.reconnect_only):
        # The interruptions need only two discovered stops and take half of the route's
        # real-time flying: qualify them beside it, in a world of their own. Two migration
        # runs cannot share one MariaDB server, so a MariaDB leg gets its own container.
        child = [sys.executable, __file__, '--interruptions-only', '--backend', args.backend,
                 *(['--server', str(args.server)] if args.server else [])]
        child.insert(0, str(ROOT / 'tests/async/with_disposable_mariadb.sh'))
        # The MariaDB wrapper's bash defers SIGTERM until its command ends, so that leg
        # gets its own process group and the signal reaches the Python child directly.
        interruptions = subprocess.Popen(child, cwd=ROOT,
                                         process_group=0)
    try:
        with tempfile.TemporaryDirectory(prefix='flight-build-', dir=ROOT / 'bin/tests') as temporary:
            build = Path(temporary)
            if args.server:
                binary = args.server.resolve()
            else:
                binary = journey.build_mariadb_server(build / 'server', real_clock=True)
            run(binary, args.backend, args.interruptions_only, args.reconnect_only,
                skip_interruptions=interruptions is not None)
    except BaseException:
        if interruptions:
            # SIGTERM, so that the child and a MariaDB leg's wrapper still clean up.
            os.killpg(interruptions.pid, signal.SIGTERM)
            interruptions.wait()
        raise
    if interruptions:
        assert interruptions.wait() == 0, 'flight interruption qualification failed'


if __name__ == '__main__':
    main()
