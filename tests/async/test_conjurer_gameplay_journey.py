#!/usr/bin/env python3
"""Isolated Conjurer command/resource/help/recovery qualification over real TCP.

Uses synthetic accounts and seeded circle-eligible mortal fixtures. No .env,
existing game database, live server or player data is used. Native regressions
cover deterministic damage/cancellation boundaries; this checks reachability
through the real parser, command gate, movement and saved state.
"""
from pathlib import Path
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor

import test_flatfile_combat_journey as journey

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / 'bin/qualification/issue215/gameplay-report.json'

FIXTURE = r'''
#include "flatfile/flatfile_player_snapshot_file.h"
#include "flatfile/flatfile_store.h"
#include "player/player_snapshot_codec.h"
#include "core/structs.h"
#include "core/utils.h"
#include "magic/spells.h"
#include <cassert>
#include <cstring>
#include <ctime>
#include <iostream>
#include <openssl/sha.h>
struct profile { const char *name; int cls,spec,level; };
profile profiles[] = {
    {"Taverek",CLASS_WARRIOR,0,62},
    {"Earthor",CLASS_CONJURER,SPEC_EARTH,56},
    {"Aerilon",CLASS_CONJURER,SPEC_AIR,56},
    {"Nerilon",CLASS_CONJURER,SPEC_WATER,46},
    {"Hydrion",CLASS_CONJURER,SPEC_WATER,50},
    {"Pyrilon",CLASS_CONJURER,SPEC_FIRE,50},
    {"Psylin",CLASS_PSIONICIST,SPEC_PSYCHEPORTER,51},
};
template<class T> void number(std::vector<uint8_t>& out,T value) {
    for(size_t i=0;i<sizeof(T);++i) out.push_back(static_cast<uint64_t>(value)>>(i*8));
}
static bool named(const player_snapshot &s,const char *name) {
    for(const auto &field:s.status_strings) if(field.field==player_status_string_field::name) return field.value==name;
    return false;
}
static void set(player_snapshot &s,player_status_field key,int64_t value) {
    for(auto &field:s.status_integers) if(field.field==key) {
        field.signed_value=value; field.unsigned_value=value; return;
    }
    assert(false);
}
static void write(const std::string &root,player_snapshot &s) {
    std::vector<uint8_t> payload,bytes; std::string error;
    s.encoded_size_bound=PLAYER_SNAPSHOT_MAX_BYTES;
    assert(player_snapshot_encode(s,&payload)==player_snapshot_codec_result::ok);
    using namespace flatfile_player_snapshot_file;
    bytes.insert(bytes.end(),player_magic.begin(),player_magic.end());
    number(bytes,player_file_version); number<uint32_t>(bytes,payload.size());
    number(bytes,s.pid); number(bytes,s.revision); number(bytes,s.components);
    unsigned char digest[SHA256_DIGEST_LENGTH]; SHA256(payload.data(),payload.size(),digest);
    bytes.insert(bytes.end(),digest,digest+sizeof(digest)); bytes.insert(bytes.end(),payload.begin(),payload.end());
    assert(flatfile_atomic_write(player_directory(root),player_filename(s.pid),bytes,&error));
}
int main(int argc,char **argv) {
    assert(argc>=3); const std::string root=argv[1],mode=argv[2];
    int found=0;
    for(int32_t pid=1;pid<=64;++pid) {
        player_snapshot s; std::string error;
        if(flatfile_player_snapshot_read(root,pid,&s,&error)!=flatfile_player_load_result::ok) continue;
        for(const auto &p:profiles) if(named(s,p.name)) {
            ++found;
            if(mode=="seed") {
                set(s,player_status_field::class_primary,p.cls); set(s,player_status_field::class_secondary,0);
                set(s,player_status_field::specialization,p.spec); set(s,player_status_field::level,p.level);
                set(s,player_status_field::highest_level,p.level);
                set(s,player_status_field::played_time,200000);
                set(s,player_status_field::base_hit,10000); set(s,player_status_field::hit_difference,p.spec==SPEC_AIR?500:0);
                set(s,player_status_field::base_mana,1000); set(s,player_status_field::mana,1000);
                set(s,player_status_field::base_vitality,2000); set(s,player_status_field::vitality,2000);
                set(s,player_status_field::screen_length,80); set(s,player_status_field::action_flags_2,PLR2_HEAL);
                s.room_vnum=22800; s.affects.clear(); s.skills.clear();
                std::vector<int> spells;
                if(p.cls==CLASS_CONJURER) {
                    spells={SPELL_DIMENSION_DOOR,SPELL_RELOCATE,SPELL_CONJURE_ELEMENTAL};
                    if(p.spec==SPEC_EARTH) spells.insert(spells.end(),{SPELL_EARTH_FORM,SPELL_STONE_SKIN,SPELL_EARTHEN_MAUL});
                    if(p.spec==SPEC_AIR) spells.insert(spells.end(),{SPELL_AIR_FORM,SPELL_ETHEREAL_RECHARGE});
                    if(p.spec==SPEC_WATER) spells.insert(spells.end(),{SPELL_WATER_FORM,SPELL_WATER_TO_LIFE});
                    if(p.spec==SPEC_FIRE) spells.insert(spells.end(),{SPELL_FIRE_FORM,SPELL_FIREBALL,SPELL_SOLAR_FLARE,SPELL_CONJURE_GREATER_ELEMENTAL});
                    for(int spell:spells) for(int copy=0;copy<6;++copy) {
                        player_affect_snapshot af{}; af.type=TAG_MEMORIZE; af.modifier=spell;
                        af.duration=-1; af.flags=MEMTYPE_FULL; af.level=p.level; s.affects.push_back(af);
                    }
                }
                write(root,s);
            } else if(mode=="inspect") {
                std::cout<<p.name<<" "<<s.room_vnum<<" ";
                for(const auto &af:s.affects)
                    if(af.type==SPELL_STONE_SKIN||af.type==SPELL_EARTH_FORM||af.type==SPELL_AIR_FORM||af.type==SPELL_FIRE_FORM||af.type==SPELL_WATER_FORM)
                        std::cout<<af.type<<":"<<af.modifier<<":"<<af.duration<<",";
                std::cout<<" pets="<<s.pets.size();
                if(p.cls==CLASS_CONJURER && p.spec==SPEC_FIRE) {
                    assert(s.pets.size()==1);
                    const auto &pet=s.pets.front(); pet_restore_state saved;
                    assert(pet_restore_state_decode(pet.restore_state,&saved));
                    assert(pet.mob_vnum==1100 && saved.kind==summoned_pet_kind::conjured_fire_mephit);
                    assert(!(saved.intrinsic_affects[1]&AFF2_FIRESHIELD));
                    assert(saved.charm_expires_at>std::time(nullptr) && saved.death_expires_at>std::time(nullptr));
                    std::cout<<" pet="<<pet.mob_vnum<<":"<<static_cast<int>(saved.kind)<<":"
                             <<saved.intrinsic_affects[1]<<":"<<saved.death_expires_at<<":"<<saved.name;
                }
                std::cout<<"\n";
            }
        }
    }
    assert(found==7);
}
'''

ROSTER = [('Journeyacct', 'Taverek'), ('Earthacct', 'Earthor'),
          ('Airacct', 'Aerilon'), ('Wateracct', 'Nerilon'),
          ('Hydroacct', 'Hydrion'), ('Fireacct', 'Pyrilon'), ('Psycheacct', 'Psylin')]


def drain(client, duration=.4):
    until = time.monotonic() + duration
    while time.monotonic() < until:
        client._receive()
    text = client.pending.decode(errors='replace')
    client.pending.clear()
    return text


def command(client, text, duration=.5):
    drain(client, .05)
    client.send(text)
    output = drain(client, duration)
    for _ in range(20):
        if 'Return to continue' not in output[-500:]:
            break
        client.send('')
        output += drain(client, .3)
    return output


def cast(client, spell, target='', retry=True):
    for _ in range(6):
        drain(client, .05)
        client.send(f"cast '{spell}' {target}".rstrip())
        outcome, output = client.expect_any(('You complete your spell',
                                             'You abort your spell before'), timeout=60)
        output += drain(client, .6)
        if outcome.startswith('You complete') or not retry:
            return output
    raise AssertionError('legitimate concentration failures exhausted fixture retries: ' + spell)


def connect(port, index):
    client = journey.reconnect_character(port, expected_room=None,
                                         account=ROSTER[index][0], character=ROSTER[index][1],
                                         source_host=f'127.0.0.{index+1}')
    client.expect('Pos:', timeout=30)
    drain(client)
    return client


def run(binary):
    checks = []
    REPORT.unlink(missing_ok=True)
    if not journey.INSPECTOR.exists():
        subprocess.run(['python3', 'tests/async/test_flatfile_player_repository.py',
                        '--build-inspector', str(journey.INSPECTOR)], cwd=ROOT, check=True)
    with tempfile.TemporaryDirectory(prefix='conjurer-gameplay-', dir=ROOT / 'bin/tests') as temporary:
        root = Path(temporary); state = root / 'state'; runtime = root / 'runtime'
        state.mkdir(mode=0o700); (state / 'domains').mkdir(mode=0o700); runtime.mkdir()
        journey.make_fixture(runtime); journey.generate_certificate(runtime)
        (runtime / 'help').symlink_to(ROOT / 'help', target_is_directory=True)
        (runtime / 'logs/log').mkdir(parents=True)
        for name in ('players', 'critical'):
            (runtime / 'journals' / name).mkdir(parents=True, mode=0o700)
        (runtime / 'bin/server').mkdir(parents=True)
        for name in ('dms', 'dms_new'):
            shutil.copy2(binary, runtime / 'bin/server' / name)
        zone = runtime / 'areas_mini/mini.zon'
        zone.write_text(re.sub(r'^[MG] .*\n', '', zone.read_text(), flags=re.M))
        world = runtime / 'areas_mini/mini.wld'
        body = world.read_text()
        arena = 'This quiet stone arena exists to prove the complete combat journey.\n~\n1 0 0\nS\n'
        assert arena in body
        body = body.replace(arena, arena.replace('S\n', 'D0\n~\n~\n0 0 22801\nD1\n~\n~\n0 0 22803\nD4\n~\n~\n0 0 24401\nS\n'))
        for vnum, title, sector, exits in [
                (22801, 'The Regression Ocean', 12, [(2, 22800), (0, 22802)]),
                (22802, 'The Outer Regression Ocean', 12, [(2, 22801)]),
                (22803, 'The Regression Lounge', 2, [(3, 22800)]),
                (24401, 'The Regression Air Plane', 2, [(5, 22800)])]:
            room = f'#{vnum}\n{title}~\nA quiet functional test room.\n~\n1 0 {sector}\n'
            room += ''.join(f'D{direction}\n~\n~\n0 0 {destination}\n' for direction, destination in exits)
            body = body.replace('$~', room + 'S\n$~')
        world.write_text(body)
        mobiles = runtime / 'areas_mini/mini.mob'
        guardian = '''#22810
affinity guardian~
the affinity guardian~
An aggressive guardian watches this native plane.
~
~
2058 1 0 0 0 0 0 0 0 S
PH 0 0 -1
60 0 -100 1000d1+50000 1d1+0
0.0.0.0 0
8 8 0
'''
        mobiles.write_text(mobiles.read_text().replace('$~', guardian + '$~'))
        objects = runtime / 'areas_mini/mini.obj'
        spring = re.search(r'(?ms)^#93300\n.*?(?=^#\d+\n)', (ROOT / 'areas/obj/centaur_zone.obj').read_text())[0]
        assert '#93300\n' not in objects.read_text()
        objects.write_text(objects.read_text().replace('$~', spring + '$~'))
        subprocess.run([str(journey.INSPECTOR), str(state), 'seed-combat'], check=True)
        cpp, fixture = root / 'fixture.cpp', root / 'fixture'
        cpp.write_text(FIXTURE)
        subprocess.run(['g++', '-std=c++20', '-Isrc', str(cpp),
                        'src/player/player_snapshot_codec.c', 'src/flatfile/flatfile_player_snapshot_file.c',
                        'src/flatfile/flatfile_store.c', 'src/player/pet_restore_state.c',
                        '-lcrypto', '-o', str(fixture)], cwd=ROOT, check=True)
        port, tls, websocket = journey.available_ports()
        env = dict(PATH=os.environ.get('PATH', '/usr/bin:/bin'), ENVIRONMENT='local',
                   PERSISTENCE_MODE='flatfile-primary', FLATFILE_STATE_DIR=str(state),
                   CRITICAL_COMMAND_JOURNAL_DIR=str(runtime / 'journals/critical'),
                   LISTEN_ADDRESS='127.0.0.1', DURIS_TLS_PORT=str(tls),
                   DURIS_WEBSOCKET_PORT=str(websocket), DURIS_WEBSOCKET_LISTEN_ADDRESS='127.0.0.1',
                   REDIS='FALSE', CHAOS_MUD='FALSE')
        clients = []; process = output = None

        def stop():
            nonlocal process, output
            for client in clients:
                client.close()
            clients.clear()
            if process and process.poll() is None:
                process.terminate(); process.wait(timeout=30)
            if output:
                output.close()

        def boot():
            nonlocal process, output
            output = (runtime / 'server.out').open('w')
            process = subprocess.Popen([str(runtime / 'bin/server/dms'), '--minimal', '-s', str(port)],
                                       cwd=runtime, env=env, stdout=output, stderr=subprocess.STDOUT)
            until = time.monotonic() + 90
            while 'Entering game loop.' not in (runtime / 'server.out').read_text(errors='replace'):
                assert process.poll() is None and time.monotonic() < until, 'server boot failed'
                time.sleep(.1)

        try:
            boot()
            def create(index):
                account, name = ROSTER[index]
                client = journey.MudClient(port, source_host=f'127.0.0.{index+1}')
                try:
                    journey.create_character(client, account=account, character=name,
                                             email=f'conjurer{index}@example.invalid')
                    client.send('save'); client.expect(f'Save complete for {name}.')
                    client.send('quit'); client.expect('ACCOUNT MENU', timeout=30)
                finally:
                    client.close()
                print('created synthetic fixture ' + name, flush=True)
            with ThreadPoolExecutor(max_workers=len(ROSTER)) as workers:
                list(workers.map(create, range(len(ROSTER))))
            stop(); subprocess.run([str(fixture), str(state), 'seed'], check=True); boot()
            clients.extend(connect(port, index) for index in range(len(ROSTER)))
            staff, earth, air, water, hydro, fire, psyche = clients
            # Keep the observing staff character from becoming the aggro target.
            assert 'visible only' in command(staff, 'vis 61')
            command(staff, 'goto 24401')
            command(staff, 'load char 22810')
            assert 'Regression Air Plane' in command(air, 'up')
            time.sleep(10)
            text = command(staff, 'stat mob guardian')
            assert re.search(r'Fighting:\s*---', text), text
            command(staff, 'transfer Hydrion')
            # Aggression runs on the mundane event and can include a calming delay.
            deadline = time.monotonic() + 30
            while True:
                text = command(staff, 'stat mob guardian')
                if not re.search(r'Fighting:\s*---', text):
                    break
                assert time.monotonic() < deadline, text
                time.sleep(.25)
            assert re.search(r'Fighting:\s*Hydrion', text), text
            command(staff, 'purge guardian')
            assert 'Regression Arena' in command(air, 'down')
            command(staff, 'goto 22800')
            command(staff, 'transfer Hydrion')
            checks.append('real native Air entry ignores level-60 aggressive memory mob; level-50 Water control is attacked')
            print('passed native-plane aggression and non-native control', flush=True)
            for client, form, expected in [(earth, 'earth form', 'living stone'),
                                           (air, 'air form', 'molecules'),
                                           (water, 'water form', 'flowing water'),
                                           (fire, 'fire form', 'living flame')]:
                output_text = cast(client, form)
                assert expected in output_text, (form, output_text)
                checks.append(form + ' reachable through mortal cast/prepared spell')
                print('passed ' + form, flush=True)
            text = cast(air, 'ethereal recharge', 'Aerilon')
            restored = re.search(r'Heal:\s*(\d+)', text)
            assert restored and 0 < int(restored[1]) <= 100, text
            checks.append('Air self-Recharge actual feedback within 100 HP')
            for _ in range(3):
                text = cast(earth, 'stone skin', 'Earthor')
                assert 'Living stone' in text, text
            text = cast(earth, 'stone skin', 'Earthor')
            assert 'already hard' in text, text
            checks.append('three personal Stone Skin casts and rejected fourth')
            print('passed Air recovery and Earth layers', flush=True)
            text = command(water, 'north', 2)
            assert 'gather your flowing body' in text, text
            text += command(water, 'abort', 1)
            assert 'stop preparing' in text, text
            time.sleep(3)
            assert 'Regression Arena' in command(water, 'look'), 'abort crossed the shoreline'
            checks.append('socket abort reaches preparation before crossing')
            text = command(water, 'north', 2)
            assert 'gather your flowing body' in text, text
            time.sleep(4)
            assert 'Regression Ocean' in command(water, 'look'), 'shoreline entry failed'
            text = command(water, 'north', 1)
            assert 'gather your flowing body' not in text and 'Outer Regression Ocean' in text, text
            command(water, 'south', 1)
            text = command(water, 'south', 2)
            assert 'gather your flowing body' in text, text
            time.sleep(4)
            assert 'Regression Arena' in command(water, 'look')
            checks.append('level-46 Water shoreline both ways and ocean-to-ocean real movement')
            text = command(water, 'north')
            assert 'gather your flowing body' in text, text
            for _ in range(3):
                attack = command(psyche, 'murder Nerilon', .4)
                if 'E: Nerilon' in attack:
                    break
            assert 'E: Nerilon' in attack, attack
            time.sleep(5)
            assert 'Regression Arena' in command(water, 'look'), 'PvP failed to cancel shoreline preparation'
            command(staff, 'goto 22803')
            command(staff, 'transfer Psylin')
            command(staff, 'goto 22800')
            checks.append('mortal PvP attack cancels pending shoreline departure')
            print('passed shoreline movement, abort and PvP cancellation', flush=True)
            # The aggression control can be knocked down by ordinary mob AI.
            command(hydro, 'stand')
            text = command(water, 'innate conjure water')
            assert 'incantation summons' in text, text
            text = command(hydro, 'innate conjure water')
            assert 'already being summoned' in text, text
            assert 'Regression Arena' in command(hydro, 'look'), 'rejected spring caller was lagged'
            time.sleep(4)
            text = command(staff, 'look')
            assert text.lower().count('freshwater spring') == 1, text
            assert 'too tired' in command(water, 'innate conjure water')
            text = command(hydro, 'innate conjure water')
            assert 'already summoned' in text and 'too tired' not in text, text
            checks.append('real spring race, one object, only successful caller cooldown')
            text = cast(fire, 'conjure elemental', 'mephit')
            assert 'mephit' in text and 'Your wish is my command' in text, text
            checks.append('optional mephit through mortal prepared summon')
            print('passed spring race and mortal mephit summon', flush=True)
            for topic, needle in [('earth form', '8 affect-duration units'), ('water form', '5 seconds BEFORE'),
                                  ('fireball', '100%'), ('solar flare', 'exactly 10%'),
                                  ('conjure water', '5-minute cooldown'), ('water to life', '232 at'),
                                  ('planar affinity', '19826-19886')]:
                text = command(staff, 'help ' + topic)
                assert needle in text, (topic, text)
            checks.append('real help lookup from both supplied sources')
            def saved_state():
                for index, client in enumerate(clients):
                    client.send('save'); client.expect(f'Save complete for {ROSTER[index][1]}.')
                return subprocess.check_output([str(fixture), str(state), 'inspect'], text=True)

            state_text = saved_state()
            # Time can reduce affect durations; types, charge order and intrinsic pet state must persist.
            def signature(text):
                return re.sub(r'(\d+:-?\d+):\d+,', r'\1,', text)
            assert all(f'{name} 22800 ' in state_text for name in ('Earthor', 'Aerilon', 'Nerilon', 'Pyrilon')), state_text
            lines = {line.split()[0]: line for line in state_text.splitlines()}
            assert lines['Earthor'].count('36:') == 3 and '684:' in lines['Earthor'], state_text
            for name, form in [('Aerilon', 396), ('Nerilon', 686), ('Pyrilon', 685)]:
                assert f'{form}:' in lines[name], state_text
            assert state_text.count('pet=1100:24:') == 1, state_text
            staff.send('shutdown copyover')
            for client in clients:
                client.expect('Copyover complete!', timeout=90)
                drain(client)
            recovered = saved_state()
            assert signature(recovered) == signature(state_text), (state_text, recovered)
            assert 'fire mephit' in command(fire, 'look')
            checks.append('real copyover retains form components, Stone Skin charge order and mephit state/deadline')
            print('passed live copyover with retained form/layer/mephit state', flush=True)
            # A fresh process also exercises ordinary player/pet snapshot materialization.
            stop(); boot()
            clients.extend(connect(port, index) for index in range(len(ROSTER)))
            staff, earth, air, water, hydro, fire, psyche = clients
            restarted = saved_state()
            assert signature(restarted) == signature(recovered), (recovered, restarted)
            assert 'fire mephit' in command(fire, 'look')
            checks.append('cold restart/login retains saved form/layer order and finite mephit state')
            print(restarted, flush=True)
            REPORT.parent.mkdir(parents=True, exist_ok=True)
            REPORT.write_text(json.dumps(dict(backend='flatfile', checks=checks, state=restarted), indent=2))
            print('Conjurer socket journey passed: ' + str(len(checks)) + ' checks', flush=True)
        except Exception:
            if process:
                print('server tail: ' + (runtime / 'server.out').read_text(errors='replace')[-2500:], flush=True)
                print('runtime tail: ' + journey.runtime_logs(runtime)[-5000:], flush=True)
            for index, client in enumerate(clients):
                print(ROSTER[index][1] + ' tail: ' + client.transcript.decode(errors='replace')[-1800:], flush=True)
            raise
        finally:
            stop()


if __name__ == '__main__':
    if len(sys.argv) > 1:
        run(Path(sys.argv[1]).resolve())
    else:
        (ROOT / 'bin/tests').mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='conjurer-gameplay-build-', dir=ROOT / 'bin/tests') as build:
            run(journey.build_flatfile_server(Path(build)))
