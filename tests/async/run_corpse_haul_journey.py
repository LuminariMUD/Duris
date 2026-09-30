#!/usr/bin/env python3
"""Three real Telnet players loot NPC and player corpses; coins and items move in memory.

Requires a freshly built MariaDB server and TEST_DB_HOST/USER/PASSWORD pointing
to a disposable loopback database. Creates and drops its own unique schema.
"""
from pathlib import Path
import os
import signal
import subprocess
import sys
import tempfile
import time
import uuid
import test_flatfile_combat_journey as journey

ROOT=Path(__file__).resolve().parents[2]

def drain(client, duration=.5):
    until=time.monotonic()+duration
    while time.monotonic()<until:
        client._receive()
        time.sleep(.02)
    text=client.pending.decode(errors='replace')
    client.pending.clear()
    return text

def reconnect_linkdead(port):
    client=journey.MudClient(port)
    entry,_=client.expect_any(('term type','account name'))
    if entry=='term type': client.send('9'); client.expect('account name')
    client.send(journey.ACCOUNT); client.expect('enter your password')
    client.send(journey.PASSWORD); client.expect('PRESS RETURN'); client.send('')
    client.expect('Please select an option'); client.send('1'); client.expect(journey.CHARACTER)
    client.send('1'); outcome,_=client.expect_any(('Reconnecting...','Play as'))
    if outcome=='Play as': client.send('y'); client.expect('The Regression Arena')
    return client

def run(binary):
    database='haul_journey_'+uuid.uuid4().hex[:12]
    host=os.environ['TEST_DB_HOST']
    assert host in ('localhost','127.0.0.1')
    port=os.environ.get('TEST_DB_PORT','3306')
    env=dict(PATH=os.environ.get('PATH','/usr/bin:/bin'), ENVIRONMENT='local',
             DB_HOST=host,DB_PORT=port,DB_NAME=database,DB_USER=os.environ['TEST_DB_USER'],
             DB_PASSWD=os.environ['TEST_DB_PASSWORD'],MYSQL_PWD=os.environ['TEST_DB_PASSWORD'],
             DB_ALLOWED_TARGETS=host+'/'+database,PERSISTENCE_MODE='mariadb-primary',DB_TLS='FALSE',
             REDIS='FALSE',CHAOS_MUD='FALSE',LISTEN_ADDRESS='127.0.0.1',
             DURIS_WEBSOCKET_LISTEN_ADDRESS='127.0.0.1')
    mysql=['mysql','--protocol=tcp','-h',host,'-P',port,'-u',env['DB_USER'],'-N','-B','--unbuffered']
    def sql(statement, selected=True):
        return subprocess.check_output(mysql+([database] if selected else []),input=statement,
                                       text=True,env=env).strip()
    sql('CREATE DATABASE '+database,False)
    try:
        sql((ROOT/'migrations/bootstrap_multithread_safe.sql').read_text())
        for args in [('adopt','--kind','fresh_bootstrap'),('run',)]:
            subprocess.run(['python3','scripts/migration_runner.py',*args],cwd=ROOT,env=env,check=True)
        with tempfile.TemporaryDirectory(prefix='corpse-haul-',dir=ROOT/'bin/tests') as temporary:
            runtime=Path(temporary)
            journey.make_fixture(runtime,True); journey.generate_certificate(runtime)
            wld=runtime/'areas_mini/mini.wld'; world=wld.read_text()
            world=world.replace('This quiet stone arena exists to prove the complete combat journey.\n~\n1 0 0\nS',
                'This quiet stone arena exists to prove the complete combat journey.\n~\n1 0 0\nD0\n~\n~\n0 -1 22801\nS')
            world=world.replace('$~','#22801\nThe Observer Landing~\nAn adjacent room for the observer.\n~\n1 0 0\nD2\n~\n~\n0 -1 22800\nS\n$~')
            assert '0 -1 22801' in world
            wld.write_text(world)
            (runtime/'logs/log').mkdir(parents=True)
            for name in ('players','critical'): (runtime/'journals'/name).mkdir(parents=True,mode=0o700)
            port,tls,ws=journey.available_ports()
            env.update(CRITICAL_COMMAND_JOURNAL_DIR=str(runtime/'journals/critical'),
                       DURIS_TLS_PORT=str(tls),DURIS_WEBSOCKET_PORT=str(ws))
            clients=[]; process=None
            output=(runtime/'server.out').open('w')
            try:
                process=subprocess.Popen([str(binary),'--minimal','-s','-d',str(runtime),str(port)],
                                         cwd=runtime,env=env,stdout=output,stderr=subprocess.STDOUT)
                deadline=time.monotonic()+120
                while 'Entering game loop.' not in (runtime/'server.out').read_text(errors='replace'):
                    assert process.poll() is None and time.monotonic()<deadline,'boot failed'
                    time.sleep(.1)
                actor=journey.MudClient(port); clients.append(actor); journey.create_character(actor)
                source=journey.MudClient(port); clients.append(source)
                journey.create_character(source,account='Sourceacct',character='Sourcemortal',email='source@example.invalid')
                dest=journey.MudClient(port); clients.append(dest)
                journey.create_character(dest,account='Destacct',character='Destmortal',email='dest@example.invalid')
                dest.send('north'); dest.expect('The Observer Landing')
                actor.send('toggle boon'); actor.expect('You will no longer be affected by boons.')
                actor.send('wield mace'); actor.expect('You wield')
                actor.send('drop all'); actor.expect('You drop a steel long sword.',timeout=20)
                actor.send('kill raoul')
                deadline=time.monotonic()+45
                while True:
                    outcome,_=actor.expect_any(('is dead! R.I.P.','You stumble, but recover in time!',
                       'You stumble in your attack, and jab at','You stumble in your attack, and hit yourself!'),
                       timeout=max(1,deadline-time.monotonic()))
                    if outcome=='is dead! R.I.P.': break
                    assert time.monotonic()<deadline
                    actor.send('kill raoul')
                actor.send('look in corpse'); actor.expect('banana')
                actor.send('save'); actor.expect('Save complete for Taverek.',timeout=30)
                pid=int(sql("SELECT pid FROM player_data WHERE name='Taverek'"))

                def plain_haul(target='corpse', name='the corpse of Raoul'):
                    for c in clients: drain(c)
                    actor.send('get all '+target)
                    actor.expect('You finish sorting your haul from '+name,timeout=30)
                    final=drain(actor,1)
                    assert 'Haul:' in final,final
                    return final

                # Coins and items move in memory, so the haul completes at once. The
                # room sees it start; the next room sees nothing.
                first=plain_haul()
                assert '3s' in first and 'a banana' in first,first
                assert 'Some contents were not acquired.' not in first,first
                observed=drain(source); elsewhere=drain(dest)
                assert 'begins pulling things from' in observed,observed
                assert 'gets ' not in elsewhere and 'pulling things' not in elsewhere,elsewhere
                print('npc corpse haul: '+first,flush=True)
                actor.send('inventory'); actor.expect('a banana')
                actor.send('save'); actor.expect('Save complete for Taverek.',timeout=30)
                assert sql(f'SELECT COUNT(*) FROM item_current_owner WHERE owner_type=1 AND owner_id={pid} AND vnum=15 AND state=1')=='1'
                assert sql(f'SELECT copper,silver,gold,platinum FROM player_data WHERE pid={pid}')=='0\t3\t0\t0'
                actor.close(); clients.remove(actor)
                # Reconnect to the same live player, verify inventory and save.
                actor=reconnect_linkdead(port); clients.append(actor)
                actor.send('inventory'); actor.expect('a banana')
                actor.send('save'); actor.expect('Save complete for Taverek.',timeout=30)
                assert 'finish sorting' not in drain(actor), 'completion replayed on reconnect'
                # The player's own corpse gives the banana back, and the wallet ends
                # where it was whether the coins went into the corpse or stayed.
                journey.attack_until_death(actor); actor.expect('ACCOUNT MENU',timeout=45)
                actor.close(); clients.remove(actor)
                actor=journey.reconnect_character(port); clients.append(actor)
                actor.send('look'); actor.expect('The corpse of a Human is lying here.')
                pc_items=plain_haul('Taverek','the corpse of Taverek')
                assert 'a banana' in pc_items and 'Some contents were not acquired.' not in pc_items,pc_items
                print('player corpse haul: '+pc_items,flush=True)
                actor.send('save'); actor.expect('Save complete for Taverek.',timeout=30)
                assert sql(f'SELECT copper,silver,gold,platinum FROM player_data WHERE pid={pid}')=='0\t3\t0\t0'
                print('PASS: three-player NPC/player corpse hauls: coins and items in memory, observers, saved custody, wallet and reconnect',flush=True)
            except Exception:
                print((runtime/'server.out').read_text(errors='replace')[-5000:])
                print(journey.runtime_logs(runtime)[-12000:])
                for c in clients: print(c.transcript.decode(errors='replace')[-7000:])
                raise
            finally:
                for c in clients: c.close()
                if process and process.poll() is None:
                    process.send_signal(signal.SIGTERM); process.wait(timeout=30)
                output.close()
    finally: sql('DROP DATABASE '+database,False)

if __name__=='__main__': run(Path(sys.argv[1]).resolve())
