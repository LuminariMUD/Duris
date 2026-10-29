#!/usr/bin/env python3
"""Mortal locker grants, idle saves, legacy coexistence and restart on disposable MariaDB.

Run with tests/async/with_disposable_mariadb.sh. No checkout .env, production
database, running server or existing player is used.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time

import test_flatfile_combat_journey as journey
from test_flight_network_journey import authority, command
from run_world_quest_dual_backend import setup_run_root

ROOT = journey.ROOT
OWNER, VISITOR, OTHER, GOD = 'Vaultowner', 'Guestchar', 'Otherguest', 'Lockwarden'
ACCOUNTS = {OWNER: 'Ownervault', VISITOR: 'Guestacct', OTHER: 'Otheracct', GOD: 'Staffacct'}
ACCOUNT_LOCKER = 'account.ownervault.1.locker'
LEGACY_LOCKER = 'vaultowner.locker'
BANK = 16590
NEUTRAL_COUNTER = 96421  # Ixarkon welcomes both sides, so the locker enforces racewar.
DENIED = "You don't have access to that locker!"


def run(binary):
    (ROOT / 'bin/tests').mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='locker-grants-', dir=ROOT / 'bin/tests') as temporary:
        runtime = Path(temporary)
        _, critical, output_path = setup_run_root(runtime)
        (runtime / 'help').symlink_to(ROOT / 'help', target_is_directory=True)
        executable = runtime / 'bin/server/dms'
        executable.parent.mkdir(parents=True)
        shutil.copy2(binary, executable)
        clients = {}
        process = None
        evidence = {'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(), 'checks': []}
        plain, tls, websocket = journey.available_ports()
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
                    assert process.poll() is None and time.monotonic() < deadline, 'locker world failed to boot'
                    time.sleep(.1)

            def stop():
                nonlocal process
                for client in clients.values():
                    client.close()
                clients.clear()
                process.send_signal(signal.SIGTERM)
                process.wait(timeout=60)
                assert process.returncode == 0, 'unclean locker journey shutdown'
                process = None

            def login(name):
                client = journey.reconnect_character(plain, expected_room=None,
                                                       account=ACCOUNTS[name], character=name)
                clients[name] = client
                client.expect('Welcome to Duris', timeout=60)
                client.expect_any(('Pos: standing >', '<>'), timeout=20)
                command(client, 'toggle paging no')
                return client

            def act(name, text, expected):
                evidence['last_command'] = name + ': ' + text
                client = clients[name]
                start = len(client.transcript)
                client.send(text)
                client.expect(expected, timeout=60)
                if expected != 'ACCOUNT MENU':
                    command(client, 'score')
                return bytes(client.transcript[start:]).decode(errors='replace')

            def check(label):
                evidence['checks'].append(label)
                print('PASS ' + label, flush=True)

            def bank(room=BANK):
                god = clients[GOD]
                command(god, f'goto {room}')
                command(god, 'setbit room here flag SAFE 1')
                command(god, 'load obj 3097')
                for name in (OWNER, VISITOR, OTHER):
                    if name in clients:
                        assert 'Ok.' in command(god, 'transfer ' + name)

            def enter(name, target='', items=1):
                deadline = time.monotonic() + 60
                client = clients[name]
                while True:
                    start = len(client.transcript)
                    client.send(('enter locker ' + target).strip())
                    match, text = client.expect_any(('this cost you', DENIED, 'Please try later',
                                                    'Slow your roll', 'could not be opened'), timeout=30)
                    if match == 'this cost you':
                        assert f'You have {items} items' in text, text
                        command(client, 'score')
                        return bytes(client.transcript[start:]).decode(errors='replace')
                    assert match in ('Please try later', 'Slow your roll'), text
                    assert time.monotonic() < deadline, 'locker save never finished'
                    command(client, 'score')
                    time.sleep(.1)

            def leave(name):
                command(clients[name], 'open door')
                act(name, 'north', 'applying magic locks')

            def denied(name, target=OWNER):
                response = act(name, 'enter locker ' + target, DENIED)
                assert 'currently using' not in response and 'trying to get in' not in response, response
                assert 'Slow your roll' not in response and 'this cost you' not in response, response

            def contents():
                return sql("SELECT l.locker_name,li.obj_uid,li.vnum FROM lockers l "
                           "JOIN locker_items li ON li.locker_id=l.id "
                           f"WHERE l.locker_name IN ('{ACCOUNT_LOCKER}','{LEGACY_LOCKER}') "
                           "ORDER BY l.locker_name,li.obj_uid")

            try:
                boot()
                for name, account in ACCOUNTS.items():
                    client = journey.MudClient(plain)
                    clients[name] = client
                    journey.create_character(client, expected_room=None, account=account,
                                             character=name, email=name.lower() + '@example.invalid')
                    act(name, 'save', 'Save complete for ' + name + '.')
                stop()
                sql(f"UPDATE player_data SET level=62,highest_level=62 WHERE name='{GOD}'")
                sql(f"UPDATE player_data SET level=20,highest_level=20,platinum=50 "
                    f"WHERE name IN ('{OWNER}','{VISITOR}','{OTHER}')")
                # A separate imported personal locker with stable ownership, not a converted account row.
                sql("INSERT INTO lockers(locker_name,owner_pid,racewar,race) "
                    f"SELECT '{LEGACY_LOCKER}',pid,racewar,race FROM player_data WHERE name='{OWNER}'")
                boot()
                for name in ACCOUNTS:
                    login(name)
                bank()
                for name in (OWNER, VISITOR, OTHER):
                    assert sql(f"SELECT level FROM player_data WHERE name='{name}'") == '20'
                check('separate owner/visitor accounts and three level-20 mortal actors at a real bank')
                assert sql(f"SELECT COUNT(*) FROM lockers WHERE locker_name='{ACCOUNT_LOCKER}'") == '0'
                denied(VISITOR)
                denied(OTHER, 'account.Otheracct.2')
                denied(OTHER, 'account.Otheracct.1junk')
                denied(OTHER, OTHER + '.locker')
                assert sql("SELECT COUNT(*) FROM lockers WHERE locker_name LIKE 'account.%'") == '0'
                enter(VISITOR, 'AcCoUnT.Guestacct.1.LoCkEr', items=0)
                leave(VISITOR)
                assert sql("SELECT COUNT(*) FROM lockers WHERE locker_name='account.guestacct.1.locker'") == '1'
                # The live starter-kit catalog may already supply a mace. Keep the
                # two fixture lockers' marker counts independent of that catalog.
                command(clients[OWNER], 'drop all.mace')
                assert 'mace' not in command(clients[OWNER], 'inventory').lower()
                for _ in range(3):
                    command(clients[GOD], 'load obj 677')
                    act(GOD, 'give mace ' + OWNER, 'Ok.')
                enter(OWNER, OWNER, items=0)
                assert sql(f"SELECT COUNT(*) FROM lockers WHERE locker_name='{ACCOUNT_LOCKER}'") == '1'
                check('first named and mixed-case canonical owner entry creates only the authenticated account side')
                act(OWNER, 'drop mace', 'You drop')
                act(OWNER, 'grant add ' + VISITOR, 'given access')
                help_text = act(OWNER, 'help locker', 'account locker takes precedence')
                assert '<character>.locker' in help_text and 'account.<account>.<side>' in help_text
                assert "account's" in act(OWNER, 'help grant', "account's")

                # Authorization is checked before exposing the occupied account locker.
                occupied = act(VISITOR, 'enter locker ' + OWNER, 'currently using that locker')
                assert OWNER in occupied
                denied(OTHER)
                leave(OWNER)
                denied(OTHER)  # Also safe while the owner's terminal locker save may be pending.
                enter(VISITOR, 'VaUlToWnEr')
                leave(VISITOR)
                check('mortal character grant -> leave -> mixed-case named account entry; occupancy privacy')

                enter(OWNER, LEGACY_LOCKER, items=0)
                act(OWNER, 'drop all.mace', 'You drop')
                act(OWNER, 'grant add ' + OTHER, 'given access')
                leave(OWNER)
                enter(OTHER, 'VaUlToWnEr.LoCkEr', items=2)
                leave(OTHER)
                denied(OTHER)
                enter(VISITOR, OWNER)
                leave(VISITOR)
                denied(VISITOR, LEGACY_LOCKER)
                check('account-first precedence, explicit legacy entry, separate contents and grants; no grant fallback')

                enter(OWNER, OWNER)
                act(OWNER, 'grant rem ' + VISITOR, 'lost access')
                leave(OWNER)
                denied(VISITOR)
                enter(OWNER, 'account.Ownervault.1.locker')
                act(OWNER, 'grant add ' + ACCOUNTS[VISITOR], 'given access')
                # Save a valid same-side character grant, then switch that character's side offline below.
                act(OWNER, 'grant add ' + OTHER, 'given access')
                leave(OWNER)
                enter(VISITOR, 'account.Ownervault.1')
                leave(VISITOR)
                enter(VISITOR, 'account.Ownervault.1.locker')
                leave(VISITOR)
                check('named and canonical owner entry, revocation, account visitor grant, optional canonical suffix')

                act(VISITOR, 'save', 'Save complete for ' + VISITOR + '.')
                command(clients[GOD], 'goto 16558')  # The real Woodseer inn handles mortal logout.
                assert 'Ok.' in command(clients[GOD], 'transfer ' + VISITOR)
                act(VISITOR, 'rent', 'ACCOUNT MENU')
                clients.pop(VISITOR).close()
                login(VISITOR)
                command(clients[GOD], f'goto {BANK}')
                assert 'Ok.' in command(clients[GOD], 'transfer ' + VISITOR)
                enter(VISITOR, OWNER)
                leave(VISITOR)
                check('account grant and named entry after visitor reconnect')

                # Reproduce the idle-rent ordering with a real PID-zero holder,
                # a distinct account/character name and one newly deposited UID.
                command(clients[GOD], 'load obj 677')
                act(GOD, 'give mace ' + OWNER, 'Ok.')
                act(OWNER, 'save', 'Save complete for ' + OWNER + '.')
                marker_uid = sql("SELECT pi.obj_uid FROM player_items pi JOIN player_data p "
                                 f"ON p.pid=pi.pid WHERE p.name='{OWNER}' AND pi.vnum=677")
                assert marker_uid.isdecimal(), marker_uid
                previous_contents = contents()
                assert marker_uid not in [row.split('\t')[1] for row in previous_contents.splitlines()]
                enter(OWNER)
                act(OWNER, 'drop mace', 'You drop')
                # The numeric selector preserves the dots in the holder's name.
                for target in ('1.' + ACCOUNT_LOCKER, OWNER):
                    response = command(clients[GOD], f'setbit char {target} timer 15')
                    assert 'No one by that name' not in response, response
                # No owner input after setting the timer: point_update must close
                # the real descriptor, prepare the locker leave and extract the PC.
                deadline = time.monotonic() + 100
                while sql(f"SELECT COUNT(*) FROM log_entries WHERE pid="
                          f"(SELECT pid FROM player_data WHERE name='{OWNER}') "
                          "AND message='Idle Rent'") != '1':
                    assert process.poll() is None and time.monotonic() < deadline, 'owner never idle-rented'
                    time.sleep(.1)
                clients.pop(OWNER).close()
                login(OWNER)
                enter(OWNER, items=2)
                assert command(clients[OWNER], 'look in chest').lower().count('mace') >= 1
                leave(OWNER)
                expected_contents = '\n'.join(sorted(previous_contents.splitlines() +
                                                     [f'{ACCOUNT_LOCKER}\t{marker_uid}\t677']))
                assert '\n'.join(sorted(contents().splitlines())) == expected_contents
                assert sql("SELECT COUNT(*) FROM log_entries WHERE pid=0 AND message='Idle Rent'") == '0'
                object_log_path = runtime / 'logs/log/obj'
                locker_log = object_log_path.read_text() if object_log_path.exists() else ''
                assert f'Locker anti-idle eject: user={OWNER} ' not in locker_log
                file_log = (runtime / 'logs/log/file').read_text()
                assert 'source_missing' not in file_log and 'dirty locker char missing' not in file_log
                assert 'pid=0 intent=5' not in file_log
                check('real idle disconnect preserves both locker UIDs, owner identity and re-entry')

                before_restart = contents()
                assert len(before_restart.splitlines()) == 4, before_restart
                grants = sql("SELECT owner,visitor FROM locker_access ORDER BY owner,visitor")
                evidence['contents_before_restart'] = before_restart
                evidence['grants_before_restart'] = grants
                stop()
                sql(f"UPDATE player_data SET racewar=2 WHERE name='{OTHER}'")
                sql(f"UPDATE account_characters SET racewar=2 WHERE char_name='{OTHER}'")
                sql(f"UPDATE accounts SET last_good_char=NULL WHERE account_name='{ACCOUNTS[OTHER]}'")
                boot()
                for name in ACCOUNTS:
                    login(name)
                bank(NEUTRAL_COUNTER)
                assert contents() == before_restart
                assert sql("SELECT owner,visitor FROM locker_access ORDER BY owner,visitor") == grants
                denied(OTHER)  # A persisted direct grant never overrides racewar.
                enter(OWNER, items=2)
                denied(OTHER)  # No opposite-side occupant disclosure either.
                leave(OWNER)
                enter(VISITOR, OWNER, items=2)
                assert 'mace' in command(clients[VISITOR], 'look in chest')
                leave(VISITOR)
                denied(VISITOR, LEGACY_LOCKER)
                check('cold restart preserves both lockers and grants; opposite-side idle/occupied entry denied')

                enter(OWNER, items=2)
                act(OWNER, 'grant rem ' + ACCOUNTS[VISITOR], 'lost access')
                leave(OWNER)
                denied(VISITOR)
                enter(OWNER, LEGACY_LOCKER, items=2)
                leave(OWNER)
                assert contents() == before_restart
                check('account-grant revocation and legacy owner access; contents and item identities unchanged')

                # Guild creation requires level 25; the actor remains a mortal.
                command(clients[GOD], f'setbit char {OWNER} level 30')
                act(OWNER, 'save', 'Save complete for ' + OWNER + '.')
                assert sql(f"SELECT level FROM player_data WHERE name='{OWNER}'") == '30'
                act(GOD, f'supervise found {OWNER} n Lockerjourney', 'new association is set up')
                deadline = time.monotonic() + 30
                while True:
                    guild_id = sql("SELECT id FROM guilds WHERE TRIM(name)='Lockerjourney'")
                    if guild_id.isdecimal():
                        break
                    assert time.monotonic() < deadline, 'new guild snapshot never landed'
                    time.sleep(.1)
                guild_target = f'guild.{guild_id}'
                act(GOD, f'supervise setbit {guild_id} prestige 500', 'prestige points to 500')
                denied(VISITOR, guild_target + '.locker')
                enter(OWNER, guild_target.upper() + '.LoCkEr', items=0)
                denied(VISITOR, guild_target + '.locker')
                leave(OWNER)
                command(clients[GOD], 'load obj 677')
                act(GOD, 'give mace ' + OWNER, 'Ok.')
                enter(OWNER, 'guild', items=0)
                act(OWNER, 'drop mace', 'You drop')
                leave(OWNER)
                for target in (guild_target, guild_target.upper() + '.LoCkEr', 'guild'):
                    response = enter(OWNER, target, items=1)
                    assert '2 copper' in response, response
                    leave(OWNER)
                act(GOD, f'supervise setbit {guild_id} prestige 0', 'prestige points to 0')
                for target in ('guild', guild_target, guild_target + '.locker'):
                    act(OWNER, 'enter locker ' + target, 'not yet prestigious enough')
                act(GOD, f'supervise setbit {guild_id} prestige 500', 'prestige points to 500')
                denied(OWNER, f'guild.{int(guild_id) + 1}.locker')
                act(GOD, f'supervise govern {guild_id}', 'You are now a god of')
                act(GOD, 'society punish ' + OWNER, 'on parole')
                for target in ('guild', guild_target, guild_target + '.locker'):
                    act(OWNER, 'enter locker ' + target, 'Try becoming part of a guild first')
                assert sql(f"SELECT COUNT(*) FROM lockers WHERE locker_name='{guild_target}.locker'") == '1'
                assert sql(f"SELECT COUNT(*) FROM locker_access WHERE owner='{guild_target}.locker'") == '0'
                assert contents() == before_restart
                check('canonical guild membership, creation, contents and fees match guild; nonmember/prestige/parole gates hold')
                stop()
                target = ROOT / 'bin/analysis/issue-234'
                target.mkdir(parents=True, exist_ok=True)
                (target / 'journey.json').write_text(json.dumps(evidence, indent=2) + '\n')
            except Exception as error:
                target = ROOT / 'bin/analysis/issue-234' / f'failure-{time.time_ns()}'
                target.mkdir(parents=True)
                (target / 'evidence.json').write_text(json.dumps(evidence, indent=2) + '\n')
                shutil.copy2(output_path, target / 'server.out')
                shutil.copytree(runtime / 'logs', target / 'logs')
                traces = '\n'.join(name + ':\n' + bytes(client.transcript[-5000:]).decode(errors='replace')
                                   for name, client in clients.items())
                raise AssertionError(f'{error}\nEvidence: {target}\n{traces}') from error
            finally:
                for client in clients.values():
                    client.close()
                if process and process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=30)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=10)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--server', type=Path, default=ROOT / 'bin/server/dms_new')
    args = parser.parse_args()
    if not os.getenv('TEST_DB_HOST'):
        raise SystemExit('use tests/async/with_disposable_mariadb.sh or supply a disposable TEST_DB_HOST')
    run(args.server.resolve())
