#!/usr/bin/env python3
"""Real account/character combat and death on an isolated MariaDB schema.

A death happens at once: the corpse takes the items and the character leaves.

Set TEST_DB_HOST (loopback), TEST_DB_USER and TEST_DB_PASSWORD for a disposable
server; TEST_DB_PORT defaults to 3306. No checkout .env or existing schema is
used. --server selects a freshly built MariaDB executable; by default this
script builds bin/server/dms_new.
"""
from pathlib import Path
import argparse
import os
import signal
import subprocess
import sys
import tempfile
import time
import uuid

import test_flatfile_combat_journey as journey

ROOT = Path(__file__).resolve().parents[2]


def run(server, reset_coins=False, boons=False):
    database = 'corpse_journey_test_' + uuid.uuid4().hex[:12]
    host = os.environ['TEST_DB_HOST']
    port = os.environ.get('TEST_DB_PORT', '3306')
    assert host in ('127.0.0.1', 'localhost'), 'use a disposable loopback database'
    environment = {
        'PATH': os.environ.get('PATH', '/usr/bin:/bin'),
        'ENVIRONMENT': 'local', 'DB_HOST': host, 'DB_PORT': port,
        'DB_NAME': database, 'DB_USER': os.environ['TEST_DB_USER'],
        'DB_PASSWD': os.environ['TEST_DB_PASSWORD'],
        'DB_ALLOWED_TARGETS': host+'/'+database,
        'MYSQL_PWD': os.environ['TEST_DB_PASSWORD'],
        'PERSISTENCE_MODE': 'mariadb-primary', 'DB_TLS': 'FALSE',
        'REDIS': 'FALSE', 'CHAOS_MUD': 'FALSE', 'DURIS_NEVENT_TRACE_PLAYER': '1',
        # The ghost record's missing_payload_rows line is a trace (#11).
        'DURIS_PERSISTENCE_TRACE': '1',
        'LISTEN_ADDRESS': '127.0.0.1', 'DURIS_WEBSOCKET_LISTEN_ADDRESS': '127.0.0.1',
    }
    if 'LD_LIBRARY_PATH' in os.environ:
        environment['LD_LIBRARY_PATH'] = os.environ['LD_LIBRARY_PATH']
    mysql = ['mysql', '--protocol=tcp', '-h', host, '-P', port,
             '-u', environment['DB_USER'], '-N', '-B']

    def sql(text, selected=True):
        return subprocess.check_output(mysql+([database] if selected else []), input=text,
                                       text=True, env=environment).strip()

    def number(text):
        return int(sql(text))

    sql('CREATE DATABASE '+database+' CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci', False)
    try:
        sql((ROOT/'migrations/bootstrap_multithread_safe.sql').read_text())
        subprocess.run(['python3', 'scripts/migration_runner.py', 'adopt', '--kind', 'fresh_bootstrap'],
                       cwd=ROOT, env=environment, check=True)
        subprocess.run(['python3', 'scripts/migration_runner.py', 'run'], cwd=ROOT, env=environment, check=True)
        with tempfile.TemporaryDirectory(prefix='mysql-combat-', dir=ROOT/'bin/tests') as temporary:
            runtime = Path(temporary)
            journey.make_fixture(runtime, reset_coins)
            journey.generate_certificate(runtime)
            (runtime/'logs/log').mkdir(parents=True)
            (runtime/'journals'/'critical').mkdir(parents=True, mode=0o700)
            plain, tls, websocket = journey.available_ports()
            environment.update(CRITICAL_COMMAND_JOURNAL_DIR=str(runtime/'journals/critical'),
                               DURIS_TLS_PORT=str(tls), DURIS_WEBSOCKET_PORT=str(websocket))
            output_path = runtime/'server.out'
            process = None
            client = None
            with output_path.open('w') as output:
                def boot():
                    offset = output_path.stat().st_size
                    proc = subprocess.Popen([str(server), '--minimal', '-s', '-d', str(runtime), str(plain)],
                                            cwd=runtime, env=environment, stdout=output, stderr=subprocess.STDOUT)
                    deadline = time.monotonic()+120
                    while b'Entering game loop.' not in output_path.read_bytes()[offset:]:
                        if proc.poll() is not None or time.monotonic()>deadline:
                            proc.terminate() if proc.poll() is None else None
                            proc.wait(timeout=10)
                            raise AssertionError('MariaDB combat fixture failed to boot')
                        time.sleep(.1)
                    return proc

                def stop():
                    process.send_signal(signal.SIGTERM)
                    process.wait(timeout=30)
                    assert process.returncode == 0

                def settle(check, what, timeout=20):
                    # The writer applies the death's corpse and player saves after the
                    # character has left; give it time to catch up.
                    deadline = time.monotonic()+timeout
                    while not check():
                        assert time.monotonic()<deadline, what() if callable(what) else what
                        time.sleep(.1)

                def stable_state(pid):
                    return (
                        sql(f'SELECT copper,silver,gold,platinum,wallet_revision,numb_deaths,exp,level FROM player_data WHERE pid={pid}'),
                        sql(f'SELECT item_uid,owner_type,owner_id,state FROM item_current_owner WHERE owner_type=1 AND owner_id={pid} ORDER BY item_uid'),
                    )

                try:
                    process = boot()
                    client = journey.MudClient(plain)
                    journey.create_character(client)
                    if not boons:
                        client.send('toggle boon'); client.expect('You will no longer be affected by boons.')
                    journey.complete_npc_combat_journey(client, reset_coins)
                    client.close(); client = journey.reconnect_character(plain)
                    # Recover the starter-kit roots dropped by the NPC fixture,
                    # so the real player's death exercises a multi-root batch.
                    client.send('get all'); client.expect('You get', timeout=20)
                    client.send('save'); client.expect('Save complete for '+journey.CHARACTER+'.', timeout=30)
                    pid = number("SELECT pid FROM player_data WHERE name='"+journey.CHARACTER+"'")
                    # What the save wrote is what the player holds; the ownership table
                    # also still names the player for items it dropped in memory.
                    captured = sql(f'SELECT obj_uid FROM player_items WHERE pid={pid} ORDER BY obj_uid').splitlines()
                    assert len(captured)>2, 'fixture did not retain a multi-root inventory'
                    before_deaths=number(f'SELECT numb_deaths FROM player_data WHERE pid={pid}')
                    began=time.monotonic(); journey.attack_until_death(client)
                    client.expect('ACCOUNT MENU',timeout=45)
                    elapsed=time.monotonic()-began
                    client.send('0'); client.close(); client=None
                    uids=','.join(captured)
                    settle(lambda: number(f'SELECT COUNT(*) FROM item_current_owner WHERE item_uid IN ({uids}) AND owner_type=4 AND state=1')==len(captured),
                           lambda: 'the corpse did not claim the items: '+sql(f'SELECT item_uid,owner_type,owner_id,state FROM item_current_owner WHERE item_uid IN ({uids})'))
                    settle(lambda: number(f'SELECT numb_deaths FROM player_data WHERE pid={pid}')==before_deaths+1, 'the death was not saved')
                    # The coins went into the corpse; the death saved the empty wallet.
                    assert sql(f'SELECT copper,silver,gold,platinum FROM player_data WHERE pid={pid}')=='0\t0\t0\t0'
                    assert number("SELECT COUNT(*) FROM corpse_items ci JOIN corpses c ON c.id=ci.corpse_id WHERE c.player_name='"+journey.CHARACTER+"'")>=len(captured)
                    print(f'MariaDB actual character: {len(captured)} items in the corpse, attack-to-menu {elapsed:.3f}s',flush=True)
                    # Minimal boot deliberately skips SQL corpse restoration.
                    # Verify persisted rows and in-game loot before restarting;
                    # the restart below tests death disposition/player authority.
                    # MariaDB's existing loader also uses the normal login text.
                    client=journey.reconnect_character(plain)
                    client.send('look'); client.expect('The corpse of a Human is lying here.')
                    client.send('look in '+journey.CHARACTER); client.expect('a banana')
                    client.send('get coins '+journey.CHARACTER)
                    client.expect('There were: 3 silver coins.' if reset_coins else 'There were: 1 copper coin.',timeout=15)
                    client.send('get banana '+journey.CHARACTER); client.expect('get a banana',timeout=15)
                    client.send('save'); client.expect('Save complete for '+journey.CHARACTER+'.')
                    client.send('quit'); client.expect('ACCOUNT MENU',timeout=30)
                    client.send('0'); client.close(); client=None
                    journey.verify_recovered_loot(plain)
                    expected='0\t3\t0\t0' if reset_coins else '1\t0\t0\t0'
                    assert sql(f'SELECT copper,silver,gold,platinum FROM player_data WHERE pid={pid}')==expected
                    client=journey.reconnect_character(plain)
                    client.send('save'); client.expect('Save complete for '+journey.CHARACTER+'.')
                    banana=number(f'SELECT item_uid FROM item_current_owner WHERE owner_type=1 AND owner_id={pid} AND state=1 AND vnum=15 LIMIT 1')
                    client.send('quit'); client.expect('ACCOUNT MENU',timeout=30)
                    client.send('0'); client.close(); client=None
                    # A durable child absent from the live object graph is only
                    # reported at load; the character loads what it holds.
                    ghost=9000000000000000000+pid
                    sql(f'INSERT INTO item_current_owner(item_uid,root_item_uid,parent_item_uid,owner_type,owner_id,item_revision,vnum,state) VALUES({ghost},{banana},{banana},1,{pid},1,15,1)')
                    client=journey.reconnect_character(plain)
                    client.send('inventory'); client.expect('a banana',timeout=15)
                    deadline=time.monotonic()+15
                    while 'outcome=missing_payload_rows' not in journey.runtime_logs(runtime):
                        assert time.monotonic()<deadline, 'payload gap was not reported at load'
                        time.sleep(.01)
                    before_deaths=number(f'SELECT numb_deaths FROM player_data WHERE pid={pid}')
                    # The death happens at once: the corpse takes the banana and the
                    # character goes straight to the menu.
                    journey.attack_until_death(client)
                    client.expect('ACCOUNT MENU',timeout=45)
                    client.send('0'); client.close(); client=None
                    settle(lambda: number(f'SELECT COUNT(*) FROM item_current_owner WHERE item_uid={banana} AND owner_type=4 AND state=1')==1, 'the corpse did not claim the banana')
                    settle(lambda: number(f'SELECT COUNT(*) FROM player_items WHERE pid={pid}')==0, 'the dead player still holds items')
                    settle(lambda: number(f'SELECT numb_deaths FROM player_data WHERE pid={pid}')==before_deaths+1, 'the second death was not saved')
                    assert sql(f'SELECT copper,silver,gold,platinum FROM player_data WHERE pid={pid}')=='0\t0\t0\t0'
                    before=stable_state(pid)
                    # The boot reaps every player row no payload row carries (#11): the ghost,
                    # and the starter kit that dissolved when the character dropped it. The
                    # rest of the state stays, and the login after it counts nothing.
                    held=set(sql(f'SELECT obj_uid FROM player_items WHERE pid={pid}').split())
                    wallet,rows=before
                    kept='\n'.join(row for row in rows.split('\n') if row.split('\t')[0] in held)
                    assert any(row.startswith(f'{ghost}\t') for row in rows.split('\n')), 'the ghost row was not in place before the restart'
                    gaps=journey.runtime_logs(runtime).count('outcome=missing_payload_rows')
                    # With the switch on, each save of the looted banana named it (#11).
                    assert f'outcome=unowned_object uid={banana} vnum=15' in journey.runtime_logs(runtime), 'the looted banana was not traced on its saves'
                    stop(); process=boot()
                    assert number(f'SELECT COUNT(*) FROM item_current_owner WHERE item_uid={ghost}')==0, 'the boot did not reap the ghost row'
                    client=journey.reconnect_character(plain)
                    client.send('save'); client.expect('Save complete for '+journey.CHARACTER+'.')
                    client.send('quit'); client.expect('ACCOUNT MENU',timeout=30)
                    client.send('0'); client.close(); client=None
                    assert stable_state(pid)==(wallet,kept), 'restart duplicated death consequences'
                    assert journey.runtime_logs(runtime).count('outcome=missing_payload_rows')==gaps, 'the login after the reap still counted the ghost'
                    stop()
                    print(f'MariaDB second death: corpse took the items at once; restart stable; reset_coins={reset_coins}, boons={boons}',flush=True)
                except Exception as error:
                    raise AssertionError(str(error)+'\n'+output_path.read_text(errors='replace')[-10000:]+'\n'+journey.runtime_logs(runtime)) from error
                finally:
                    if client: client.close()
                    if process and process.poll() is None:
                        process.terminate()
                        try: process.wait(timeout=10)
                        except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=10)
    finally:
        sql('DROP DATABASE '+database,False)


VARIANTS={'default':{},'reset-coins':{'reset_coins':True},'boons':{'boons':True}}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--server',type=Path)
    parser.add_argument('--one',action='store_true',help='run only the default-coin variant')
    parser.add_argument('--variant',choices=VARIANTS,help=argparse.SUPPRESS)
    args=parser.parse_args()
    if not os.getenv('TEST_DB_HOST'):
        print('MariaDB live combat skipped: TEST_DB_HOST is not set')
    else:
        (ROOT/'bin/tests').mkdir(parents=True,exist_ok=True)
        if not args.server:
            subprocess.run(['make','-C','src','-j2','PERSISTENCE_BACKEND=mariadb'],cwd=ROOT,check=True)
        server=(args.server or ROOT/'bin/server/dms_new').resolve()
        if args.one or args.variant:
            run(server,**VARIANTS[args.variant or 'default'])
        else:
            # Each variant has its own schema, fixture and ports: run them at once.
            variants=[subprocess.Popen([sys.executable,__file__,'--server',str(server),'--variant',name],
                                       cwd=ROOT) for name in VARIANTS]
            assert not any([variant.wait() for variant in variants]),'a combat variant failed'
