#!/usr/bin/env python3
"""Qualify generated NPCs through file copyover or MariaDB/Redis recovery.

The default mini world uses staff-strung 1255/1256 instances. Pass the generated
areas directory as the third argument for the full-world roaming journey.
"""
from pathlib import Path
import ctypes
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
import test_flatfile_combat_journey as journey

FIXTURE = '\n#include "flatfile/flatfile_player_snapshot_file.h"\n#include "flatfile/flatfile_store.h"\n#include "player/player_snapshot_codec.h"\n#include <cassert>\n#include <openssl/sha.h>\ntemplate<class T> void number(std::vector<uint8_t>& out, T value) {\n    for (size_t i=0; i<sizeof(T); ++i) out.push_back(static_cast<uint64_t>(value) >> (i*8));\n}\nint main(int argc, char **argv) {\n    assert(argc == 2);\n    const std::string root = argv[1];\n    for (uint32_t pid : {1}) {\n        player_snapshot snapshot; std::string error;\n        assert(flatfile_player_snapshot_read(root,pid,&snapshot,&error) == flatfile_player_load_result::ok);\n        for (auto &field : snapshot.status_integers) {\n            if (field.field == player_status_field::level || field.field == player_status_field::highest_level)\n                field.signed_value = field.unsigned_value = 62;\n            if (field.field == player_status_field::base_hit) field.signed_value = field.unsigned_value = 200000;\n            if (field.field == player_status_field::hit_difference) field.signed_value = field.unsigned_value = 0;\n        }\n        std::vector<uint8_t> payload, bytes;\n        snapshot.encoded_size_bound = PLAYER_SNAPSHOT_MAX_BYTES;\n        assert(player_snapshot_encode(snapshot,&payload) == player_snapshot_codec_result::ok);\n        using namespace flatfile_player_snapshot_file;\n        bytes.insert(bytes.end(),player_magic.begin(),player_magic.end());\n        number(bytes,player_file_version); number<uint32_t>(bytes,payload.size());\n        number(bytes,snapshot.pid); number(bytes,snapshot.revision); number(bytes,snapshot.components);\n        unsigned char digest[SHA256_DIGEST_LENGTH]; SHA256(payload.data(),payload.size(),digest);\n        bytes.insert(bytes.end(),digest,digest+sizeof(digest)); bytes.insert(bytes.end(),payload.begin(),payload.end());\n        assert(flatfile_atomic_write(player_directory(root),player_filename(pid),bytes,&error));\n    }\n}\n'

def drain(client,duration=.4):
    end=time.monotonic()+duration
    while time.monotonic()<end: client._receive(); time.sleep(.02)
    text=client.pending.decode(errors='replace'); client.pending.clear(); return text

# Attach only to processes launched here. Permit this harness's GDB child on
# Linux with Yama enabled, without changing the host's ptrace settings.
def permit_probe():
    PR_SET_PTRACER = 0x59616d61
    if ctypes.CDLL(None, use_errno=True).prctl(PR_SET_PTRACER, os.getppid(), 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), 'PR_SET_PTRACER')


POPULATION_PROBE = r"""
import gdb
import json

gdb.execute('list spawn_random_mapmob', to_string=True)
def integer(expression):
    return int(gdb.parse_and_eval(expression))

npc_bit = integer('ACT_ISNPC')
sentinel = integer('ACT_SENTINEL')
map_flag = integer('ZONE_MAP')
private_zone = integer('ZONE_PRIVATE')
forbidden_room = integer('ROOM_PRIVATE | ROOM_NO_TELEPORT')
owned_strings = integer('STRUNG_KEYS | STRUNG_DESC1 | STRUNG_DESC2')
forbidden_sectors = [integer(name) for name in ('SECT_OCEAN', 'SECT_MOUNTAIN',
                                               'SECT_WATER_SWIM', 'SECT_WATER_NOSWIM')]

def snapshot():
    ch = gdb.parse_and_eval('character_list')
    prototypes = gdb.parse_and_eval('mob_index')
    objects = gdb.parse_and_eval('obj_index')
    world = gdb.parse_and_eval('world')
    zones = gdb.parse_and_eval('zone_table')
    def item_signature(item):
        rnum = int(item['R_num'])
        return [int(objects[rnum]['virtual_number']), int(item['obj_uid']),
                item['short_description'].string()]

    rows = []
    while int(ch):
        act = int(ch['specials']['act'])
        if act & npc_bit:
            npc = ch['only']['npc']
            prototype = int(prototypes[int(npc['R_num'])]['virtual_number'])
            if prototype == 1255 or bool(npc['training_dummy']):
                room_index = int(ch['in_room'])
                room = world[room_index] if room_index >= 0 else None
                zone_flags = int(zones[int(room['zone'])]['flags']) if room is not None else 0
                slots = ch['equipment']
                lo, hi = slots.type.range()
                equipment = [item_signature(slots[i]) if int(slots[i]) else None for i in range(lo, hi + 1)]
                items = []
                item = ch['carrying']
                while int(item):
                    items.append(item_signature(item))
                    item = item['next_content']
                rows.append(dict(id=int(npc['idnum']), room=int(room['number']) if room is not None else -1,
                                 marked=bool(npc['training_dummy']), fixed=bool(npc['training_dummy_fixed']),
                                 name=ch['player']['name'].string(), description=ch['player']['long_descr'].string(),
                                 prototype=prototype, hit=int(ch['points']['base_hit']),
                                 sentinel=bool(act & sentinel), strings=(int(npc['str_mask']) & owned_strings) == owned_strings,
                                 act=act, race=int(ch['player']['race']), character_class=int(ch['player']['m_class']),
                                 level=int(ch['player']['level']),
                                 eligible=bool(zone_flags & map_flag) and not bool(zone_flags & private_zone)
                                     and not bool(int(room['room_flags']) & forbidden_room)
                                     and int(room['sector_type']) not in forbidden_sectors,
                                 items=sorted(items), equipment=equipment))
        ch = ch['next']
    return rows

def find_roamer(saved_id):
    # Saved NPC IDs can collide with unrelated allocations after recovery.
    ch = gdb.parse_and_eval('character_list')
    prototypes = gdb.parse_and_eval('mob_index')
    matches = []
    while int(ch):
        if int(ch['specials']['act']) & npc_bit:
            npc = ch['only']['npc']
            if (int(npc['idnum']) == saved_id and not bool(npc['training_dummy'])
                    and int(prototypes[int(npc['R_num'])]['virtual_number']) == 1255):
                matches.append(ch)
        ch = ch['next']
    assert len(matches) == 1
    return matches[0]
"""


def probe_population(process, runtime, action=''):
    commands = runtime / 'population.gdb'
    commands.write_text(
        'set pagination off\nset debuginfod enabled off\nset confirm off\n'
        'handle SIGPIPE nostop noprint pass\npython\n' + POPULATION_PROBE + '\nend\n'
        + f'attach {process.pid}\n' + action + '\npython print("POPULATION", json.dumps(snapshot()))\ndetach\n')
    result = subprocess.run(
        ['gdb', '--batch', '-nx', f'/proc/{process.pid}/exe', '-x', str(commands)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=165)
    output = [line.removeprefix('POPULATION ') for line in result.stdout.splitlines()
              if line.startswith('POPULATION ')]
    assert result.returncode == 0 and output, result.stdout
    return json.loads(output[0])


def qualify_roamers(process, runtime, client, recover):
    def partition(action=''):
        rows = probe_population(process(), runtime, action)
        fixed = sorted(row['room'] for row in rows if row['marked'] and row['fixed'])
        custom = [row for row in rows if row['marked'] and not row['fixed']]
        ordinary = [row for row in rows if not row['marked']]
        return fixed, custom, ordinary

    def signature(row):
        # Roamers can walk, so room and placement eligibility are only checked at creation.
        return {key: value for key, value in row.items() if key not in ('room', 'eligible')}

    def roamer_action(row, action):
        return ('break run_activity_phase\ncontinue\n'
                f"python gdb.set_convenience_variable('roamer', find_roamer({row['id']}))\n"
                + action)

    def set_cap(cap, save=False):
        client.send(f'properties set random.mapmob.populationCap {cap}')
        client.send('properties show random.mapmob.populationCap')
        client.expect(f'random.mapmob.populationCap: {cap}.000')
        if save:
            client.send('properties save')
            client.send('properties diff')
        drain(client)
        if save:
            assert f'random.mapmob.populationCap={cap}.000' in (runtime / 'lib/duris.properties').read_text()

    def spawn_dummy():
        client.send('goto 22801')
        drain(client)
        client.send('dummy spawn 50 human warrior mid')
        client.expect('A configurable training dummy appears')

    def tick():
        return partition('break run_activity_phase\ncontinue\ncall (void) spawn_random_mapmob()')

    fixed, custom, ordinary = partition()
    bootstrap = re.findall(r'Training dummy bootstrap created (\d+) fixed PvP target',
                           journey.runtime_logs(runtime) + (runtime / 'server.out').read_text(errors='replace'))
    assert bootstrap and int(bootstrap[-1]) == len(fixed) == len(set(fixed)) and len(fixed) > 45
    assert not custom and not ordinary and 22801 not in fixed

    set_cap(1, save=True)
    # Observe the normal scheduler, allowing generation to fail and retry.
    for _ in range(3):
        rooms, custom, ordinary = partition('break spawn_random_mapmob\ncontinue\nfinish')
        if ordinary:
            break
    assert rooms == fixed and not custom and len(ordinary) == 1, ordinary
    roamer, = ordinary
    assert roamer['eligible'] and roamer['strings'] and 'from ' in roamer['description'], roamer
    assert 0 < roamer['hit'] < 1000000 and not roamer['sentinel'], roamer
    assert any(item is not None for item in roamer['equipment']), roamer
    print(f'Natural spawn with {len(fixed)} fixed rooms: {roamer}', flush=True)

    # Seed a carried item as well as the naturally generated worn gear.
    action = roamer_action(roamer, 'set $item = read_object_for_creation(677, 1)\n'
                          'call (void) obj_to_char($item, $roamer)')
    rooms, custom, ordinary = partition(action)
    assert rooms == fixed and not custom and len(ordinary) == 1
    roamer, = ordinary
    assert any(item[0] == 677 for item in roamer['items'])

    spawn_dummy()
    rooms, custom, ordinary = partition()
    assert rooms == fixed and len(custom) == 1 and custom[0]['prototype'] == 1255
    assert [signature(row) for row in ordinary] == [signature(roamer)]
    client.send('dummy despawn')
    client.expect('The training dummy fades away.')
    rooms, custom, ordinary = tick()
    assert rooms == fixed and not custom and [signature(row) for row in ordinary] == [signature(roamer)]

    for cycle in range(2):
        spawn_dummy()
        rooms, custom, ordinary = partition()
        assert rooms == fixed and len(custom) == 1
        assert [signature(row) for row in ordinary] == [signature(roamer)]
        if cycle == 1:
            set_cap(0, save=True)
        client = recover(cycle)
        rooms, custom, ordinary = tick()
        assert rooms == fixed and not custom
        assert [signature(row) for row in ordinary] == [signature(roamer)], (roamer, ordinary)
        print(f'Recovery {cycle + 1}: roamer identity, stats and items retained; {len(fixed)} fixed rooms', flush=True)

    # Exercise real extraction while the restored cap is zero.
    action = roamer_action(roamer, 'call (void) extract_char($roamer)\ncall (void) spawn_random_mapmob()')
    assert partition(action) == (fixed, [], [])
    set_cap(1)
    for _ in range(3):
        rooms, custom, replacements = tick()
        if replacements:
            break
    assert rooms == fixed and not custom and len(replacements) == 1
    assert replacements[0]['id'] != roamer['id']
    assert replacements[0]['eligible'] and any(item is not None for item in replacements[0]['equipment'])
    print('Zero blocks an empty population; live extraction and cap increase admit one replacement', flush=True)


def run(binary, mode='file', full_world=None):
    assert mode in ('file', 'redis')
    output_root = journey.ROOT / 'bin/tests'
    output_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='generated-npc-journey-', dir=output_root) as temporary:
        root=Path(temporary); state=root/'state'; runtime=root/'runtime'
        state.mkdir(mode=0o700); (state/'domains').mkdir(mode=0o700); runtime.mkdir()
        (runtime/'logs/log').mkdir(parents=True)
        journey.make_fixture(runtime); journey.generate_certificate(runtime)
        # The deployed prototypes use generic placeholder strings. Real string
        # commands below give each instance independently owned identity text.
        path=runtime/'areas_mini/mini.mob'; mobs=path.read_text()
        for vnum,key in [(1255,'maptemplate'),(1256,'themetemplate')]:
            mob=f"#{vnum}\n{key}~\nrandom mob prototype~\nRandom mob prototype stands here.\n~\n~\n10 0 0 0 0 0 0 0 S\nPH 0 0 -1\n35 0 -30 40d1+900 6d5+12\n0.0.0.0 0\n8 8 0\n"
            mobs, replaced = re.subn(rf'(?ms)^#{vnum}\n.*?(?=^#\d+\n|^\$~)', lambda _: mob, mobs)
            assert replaced == 1, (vnum, replaced)
        path.write_text(mobs)
        path=runtime/'areas_mini/mini.zon'
        path.write_text(path.read_text().replace('\nS\n','\nM 0 1255 1 22800 100 0 0 0\nM 0 1256 1 22800 100 0 0 0\nS\n'))
        path=runtime/'areas_mini/mini.wld'
        world=path.read_text().replace('1 0 0\nS\n$~', '1 0 0\nD0\n~\n~\n0 0 22801\nS\n$~')
        assert '0 0 22801' in world
        path.write_text(world.replace('$~', '#22801\nThe Observation Room~\nA quiet room north of the sentinels.\n~\n1 0 0\nD2\n~\n~\n0 0 22800\nS\n$~'))
        if full_world:
            (runtime / 'areas').unlink()
            shutil.copytree(full_world, runtime / 'areas')
            properties = runtime / 'lib/duris.properties'
            properties.write_text(properties.read_text().replace('random.mapmob.populationCap=45.000',
                                                                  'random.mapmob.populationCap=0.000'))
        for name in ('players','critical'): (runtime/'journals'/name).mkdir(parents=True,mode=0o700)
        (runtime/'bin/server').mkdir(parents=True)
        for name in ('dms','dms_new'): shutil.copy2(binary,runtime/'bin/server'/name)
        port,tls,ws=journey.available_ports()
        env=dict(PATH=os.environ.get('PATH','/usr/bin:/bin'),ENVIRONMENT='local',PERSISTENCE_MODE='flatfile-primary',
                 FLATFILE_STATE_DIR=str(state),
                 CRITICAL_COMMAND_JOURNAL_DIR=str(runtime/'journals/critical'),REDIS='FALSE',CHAOS_MUD='FALSE',
                 LISTEN_ADDRESS='127.0.0.1',DURIS_TLS_PORT=str(tls),DURIS_WEBSOCKET_PORT=str(ws),
                 DURIS_WEBSOCKET_LISTEN_ADDRESS='127.0.0.1')
        database = None
        if mode == 'redis':
            database = 'generated_npc_'+uuid.uuid4().hex[:12]
            host = os.environ['TEST_DB_HOST']; assert host in ('127.0.0.1', 'localhost')
            env.update(DB_HOST=host, DB_PORT=os.environ.get('TEST_DB_PORT', '3306'), DB_NAME=database, DB_USER=os.environ['TEST_DB_USER'],
                DB_PASSWD=os.environ['TEST_DB_PASSWORD'], MYSQL_PWD=os.environ['TEST_DB_PASSWORD'],
                DB_ALLOWED_TARGETS=host+'/'+database, DB_TLS='FALSE', PERSISTENCE_MODE='mariadb-primary')
            mysql=['mysql','--protocol=tcp','-h',host,'-P',env['DB_PORT'],'-u',env['DB_USER'],'-N','-B']
            def sql(statement, selected=True):
                return subprocess.check_output(mysql+([database] if selected else []), input=statement,
                    text=True, env=env).strip()
            sql('CREATE DATABASE '+database, False)
            sql((journey.ROOT/'migrations/bootstrap_multithread_safe.sql').read_text())
            for arguments in [('adopt','--kind','fresh_bootstrap'),('run',)]:
                subprocess.run(['python3','scripts/migration_runner.py',*arguments],cwd=journey.ROOT,env=env,check=True)
        else:
            subprocess.run([str(journey.INSPECTOR),str(state),'seed-combat'],check=True)
        cpp=root/'staff.cpp'; cpp.write_text(FIXTURE); fixture=root/'staff'
        subprocess.run(['g++','-std=c++20','-Isrc',str(cpp),'src/player/player_snapshot_codec.c',
            'src/flatfile/flatfile_player_snapshot_file.c','src/flatfile/flatfile_store.c','-lcrypto','-o',str(fixture)],cwd=journey.ROOT,check=True)
        process=output=client=redis=None
        expected_room = None if full_world else 'The Regression Arena'
        def stop():
            nonlocal client,process,output
            if client: client.close(); client=None
            try:
                if process and process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=30)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=10)
                        raise
            finally:
                if output:
                    output.close()
        def boot():
            nonlocal process,output
            output=(runtime/'server.out').open('w')
            flags = [] if full_world else ['--minimal']
            process=subprocess.Popen([str(runtime/'bin/server/dms'), *flags, '-s', str(port)],
                                     cwd=runtime, env=env, stdout=output, stderr=subprocess.STDOUT,
                                     preexec_fn=permit_probe if full_world else None)
            deadline=time.monotonic()+90
            while 'Entering game loop.' not in (runtime/'server.out').read_text(errors='replace'):
                assert process.poll() is None and time.monotonic()<deadline,'boot failed'
                time.sleep(.1)
        try:
            boot(); client=journey.MudClient(port); journey.create_character(client, expected_room=expected_room)
            client.send('save'); client.expect('Save complete for Taverek.')
            client.send('quit'); client.expect('ACCOUNT MENU',timeout=30)
            stop()
            if mode == 'file': subprocess.run([str(fixture),str(state)],check=True)
            else: sql("UPDATE player_data SET level=62,highest_level=62,base_hit=200000 WHERE name='Taverek'")
            if mode == 'redis':
                redis_port = journey.available_ports()[0]
                redis = subprocess.Popen(['redis-server', '--bind', '127.0.0.1', '--port', str(redis_port),
                    '--save', '', '--appendonly', 'no'], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
                env.update(REDIS='TRUE', REDIS_HOST='127.0.0.1', REDIS_PORT=str(redis_port),
                    REDIS_NAMESPACE='duris:local:generated-npc-' + uuid.uuid4().hex[:8],
                    REDIS_WORLD_STATE='TRUE', REDIS_WORLD_STATE_INTERVAL='5',
                    REDIS_WORLD_STATE_SECRET='local-generated-npc-fixture-secret-123456789')
                time.sleep(.3)
            boot(); client=journey.reconnect_character(port, expected_room=expected_room); drain(client)
            if full_world:
                def recover(cycle):
                    nonlocal client
                    client.send('save'); client.expect('Save complete for Taverek.', timeout=30)
                    if mode == 'file':
                        status = runtime / 'logs/log/status'
                        for attempt in range(3):
                            offset = status.stat().st_size
                            client.send('shutdown copyover')
                            outcome, _ = client.expect_any(
                                ('Copyover complete!', 'Copyover FAILED'), timeout=120)
                            if outcome == 'Copyover complete!':
                                break
                            assert 'artifact/guild drain failed' in status.read_bytes()[offset:].decode(errors='replace')
                            assert attempt < 2, 'artifact/guild writer did not drain after copyover'
                            print('Waiting for recovered artifact/guild writes before retrying file copyover', flush=True)
                            time.sleep(15)
                    else:
                        # The full capture can take longer than the interval. A
                        # capture already running may have passed the NPC stage.
                        status = runtime / 'logs/log/sys'
                        offset = status.stat().st_size
                        fresh_capture = re.compile(
                            r'starting bounded world recovery capture.*?'
                            r'generation and floor handoff acknowledged sequence=(\d+)', re.S)
                        deadline = time.monotonic() + 180
                        while True:
                            with status.open('rb') as log:
                                log.seek(offset)
                                acknowledged = fresh_capture.search(log.read().decode(errors='replace'))
                            if acknowledged:
                                break
                            assert time.monotonic() < deadline, 'no fresh acknowledged Redis snapshot'
                            time.sleep(.25)
                        if cycle == 0:
                            process.kill()
                        else:
                            client.send('shutdown reboot')
                        process.wait(timeout=90)
                        stop(); boot()
                        client = journey.reconnect_character(port, expected_room=expected_room)
                        restored = re.findall(r'restored world recovery generation sequence=(\d+)',
                                              journey.runtime_logs(runtime))
                        assert restored and int(restored[-1]) >= int(acknowledged[1])
                        mode_name = 'crash' if cycle == 0 else 'clean restart'
                        assert f'Performing redis {mode_name} recovery' in journey.runtime_logs(runtime)
                    return client

                qualify_roamers(lambda: process, runtime, client, recover)
                return
            for key,name,description in [('maptemplate','mapward','Mapward the wandering sentinel'),
                                         ('themetemplate','themeward','Themeward the cavern sentinel')]:
                for field,value,target in [('name',name,key),('short',description,name),('long',description+' stands watch.',name)]:
                    client.send(f'string char {target} {field} {value}'); client.expect('Ok.')
                client.send(f'setattr {name} str 103'); print('setattr: '+drain(client),flush=True)
            initial={}
            for cycle in range(3):
                drain(client); client.send('look'); text=client.expect('Pos: standing >')
                assert text.count('Mapward the wandering sentinel stands watch.')==1,text
                assert text.count('Themeward the cavern sentinel stands watch.')==1,text
                assert 'random mob prototype' not in text.lower(),text
                for name in ('mapward','themeward'):
                    client.send('stat mob '+name); stat=drain(client,1)
                    assert '103' in stat,stat
                    signature=(re.search(r'Numbers:.*?(\d+)-I', stat).group(1),
                        re.search(r'Level:.*',stat).group(0), re.search(r'Race:.*',stat).group(0),
                        tuple(re.findall(r'(?:Str|Dex|Agi|Con|Kar|Pow|Int|Wis|Cha|Luc):\s*\d+\s*\(\s*(\d+)\)',stat)),
                        tuple(re.findall(r'[PGSC]coins:\s*(\d+)',stat)))
                    if cycle == 0: initial[name]=signature
                    else:
                        expected=initial[name] if mode=='file' else initial[name][:-1]+(tuple('0' for _ in signature[-1]),)
                        assert signature == expected, (name, expected, signature)
                    print(f'{cycle} {name}: '+stat,flush=True)
                    if '[Return to continue' in stat:
                        client.send('q'); drain(client)
                client.send('north'); client.expect('The Observation Room'); drain(client)
                client.send('scan'); scanned=drain(client,1)
                assert 'Mapward the wandering sentinel' in scanned and 'Themeward the cavern sentinel' in scanned,scanned
                assert 'random mob prototype' not in scanned.lower(),scanned
                client.send('south'); client.expect('The Regression Arena'); drain(client)
                if cycle<2:
                    client.send('save'); client.expect('Save complete for Taverek.',timeout=30)
                    if mode == 'file':
                        client.send('shutdown copyover'); client.expect('Copyover complete!',timeout=90)
                        client.send('save'); client.expect('Save complete for Taverek.',timeout=30)
                    else:
                        deadline = time.monotonic() + 60
                        while 'generation and floor handoff acknowledged' not in journey.runtime_logs(runtime):
                            assert time.monotonic() < deadline, 'no acknowledged Redis snapshot'
                            time.sleep(.2)
                        if cycle == 0:
                            process.kill(); process.wait(timeout=30)
                        else:
                            client.send('shutdown reboot'); process.wait(timeout=30)
                        stop(); boot(); client=journey.reconnect_character(port); drain(client)
                        assert 'restored world recovery generation' in journey.runtime_logs(runtime)
            print(f'PASS: real player string/stat/look, {mode} repeated recovery, retained 1255/1256 identities/base strength/counts and save',flush=True)
        except Exception:
            print((runtime/'server.out').read_text(errors='replace')[-6000:])
            print(journey.runtime_logs(runtime)[-12000:])
            if client: print(client.transcript.decode(errors='replace')[-9000:])
            raise
        finally:
            try:
                stop()
            finally:
                try:
                    if redis:
                        redis.terminate()
                        try:
                            redis.wait(timeout=15)
                        except subprocess.TimeoutExpired:
                            redis.kill()
                            redis.wait(timeout=10)
                            raise
                finally:
                    if database:
                        sql('DROP DATABASE '+database, False)

if __name__=='__main__':
    if len(sys.argv) > 1:
        run(Path(sys.argv[1]).resolve(), sys.argv[2] if len(sys.argv) > 2 else 'file',
            Path(sys.argv[3]).resolve() if len(sys.argv) > 3 else None)
    else:
        # make test-all: the flat-file server the other journeys share.
        (journey.ROOT/'bin/tests').mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='generated-npc-build-',dir=journey.ROOT/'bin/tests') as build:
            run(journey.build_flatfile_server(Path(build)))
