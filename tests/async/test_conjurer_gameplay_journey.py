#!/usr/bin/env python3
"""Isolated Conjurer command/resource/help/recovery qualification over real TCP.

Uses synthetic accounts and seeded circle-eligible mortal fixtures on disposable
MariaDB. No .env, live server or player data is used. Native regressions
cover deterministic damage/cancellation boundaries; this checks reachability
through the real parser, command gate, movement and saved state.
"""
import argparse
from pathlib import Path
import json
import re
import shutil
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor

import test_mariadb_combat_journey as journey

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / 'bin/qualification/issue215/gameplay-report.json'

PET_DECODER = r'''
#include "player/pet_restore_state.h"
#include "core/structs.h"
#include "core/utils.h"
#include "magic/spells.h"
#include <cassert>
#include <ctime>
#include <iostream>
#include <string>
int main(int argc, char **argv) {
    assert(argc == 2);
    std::string encoded;
    for (const char *hex = argv[1]; *hex; hex += 2)
        encoded.push_back(static_cast<char>(std::stoi(std::string(hex, 2), nullptr, 16)));
    pet_restore_state saved;
    assert(pet_restore_state_decode(encoded, &saved));
    assert(saved.kind == summoned_pet_kind::conjured_fire_mephit);
    assert(!(saved.intrinsic_affects[1] & AFF2_FIRESHIELD));
    assert(saved.charm_expires_at > std::time(nullptr) && saved.death_expires_at > std::time(nullptr));
    std::cout << static_cast<int>(saved.kind) << ":" << saved.intrinsic_affects[1] << ":"
              << saved.death_expires_at << ":" << saved.name;
}
'''

HEADER = (ROOT / 'src/magic/spells.h').read_text()


def spell_id(name):
    return int(re.search(r'^#define ' + name + r' (\d+)', HEADER, re.M)[1])


CONJURER = 1 << 11
AIR, WATER, FIRE, EARTH = 1, 2, 3, 4
PROFILES = (('Taverek', 1, 0, 62), ('Earthor', CONJURER, EARTH, 56), ('Aerilon', CONJURER, AIR, 56),
            ('Nerilon', CONJURER, WATER, 46), ('Hydrion', CONJURER, WATER, 50),
            ('Pyrilon', CONJURER, FIRE, 50), ('Psylin', 1 << 2, 3, 51))
FORM_SPELLS = {EARTH: ('EARTH_FORM', 'STONE_SKIN', 'EARTHEN_MAUL'), AIR: ('AIR_FORM', 'ETHEREAL_RECHARGE'),
               WATER: ('WATER_FORM', 'WATER_TO_LIFE'),
               FIRE: ('FIRE_FORM', 'FIREBALL', 'SOLAR_FLARE', 'CONJURE_GREATER_ELEMENTAL')}


def seed_roster(sql):
    """Circle-eligible levels and memorized spells for the whole roster, in the arena."""
    for name, classes, spec, level in PROFILES:
        pid = sql(f"SELECT pid FROM player_data WHERE name='{name}'")
        statements = [
            f"UPDATE player_data SET m_class={classes},secondary_class=0,spec={spec},level={level},"
            f"highest_level={level},played_time=200000,base_hit=10000,hit_diff={500 if spec == AIR and classes == CONJURER else 0},"
            f"base_mana=1000,mana=1000,base_vitality=2000,vitality=2000,screen_length=80,act2={1 << 20},"
            f"last_room=22800 WHERE pid={pid}",
            f"DELETE FROM player_affects WHERE pid={pid}", f"DELETE FROM player_skills WHERE pid={pid}"]
        if classes == CONJURER:
            memorize = spell_id('TAG_MEMORIZE')
            spells = ('DIMENSION_DOOR', 'RELOCATE', 'CONJURE_ELEMENTAL') + FORM_SPELLS[spec]
            statements += [f"INSERT INTO player_affects(pid,type,duration,flags,modifier,level) "
                           f"VALUES({pid},{memorize},-1,16,{spell_id('SPELL_' + spell)},{level})"
                           for spell in spells for _ in range(6)]
        sql(';'.join(statements))


def saved_conjurers(sql, decoder):
    """One line per roster member: room, form/skin affects in order, and the fire pet."""
    forms = ','.join(str(spell_id('SPELL_' + spell)) for spell in
                     ('STONE_SKIN', 'EARTH_FORM', 'AIR_FORM', 'FIRE_FORM', 'WATER_FORM'))
    lines = []
    for name, classes, spec, _ in PROFILES:
        pid, room = sql(f"SELECT pid,last_room FROM player_data WHERE name='{name}'").split('\t')
        affects = sql(f"SELECT CONCAT(type,':',modifier,':',duration,',') FROM player_affects "
                      f"WHERE pid={pid} AND type IN ({forms}) ORDER BY id").replace('\n', '')
        pets = sql(f"SELECT mob_vnum,HEX(restore_state) FROM player_pets WHERE owner_pid={pid} ORDER BY id")
        pet_rows = [row.split('\t') for row in pets.splitlines()]
        line = f"{name} {room} {affects} pets={len(pet_rows)}"
        if classes == CONJURER and spec == FIRE:
            assert len(pet_rows) == 1, pets
            state = subprocess.check_output([str(decoder), pet_rows[0][1]], text=True)
            line += f" pet={pet_rows[0][0]}:{state}"
        lines.append(line)
    return '\n'.join(lines) + '\n'

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
    with tempfile.TemporaryDirectory(prefix='conjurer-gameplay-', dir=ROOT / 'bin/tests') as temporary, \
            journey.mariadb_authority() as (authority, sql):
        root = Path(temporary); runtime = root / 'runtime'
        runtime.mkdir()
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
        cpp, decoder = root / 'pet_decoder.cpp', root / 'pet_decoder'
        cpp.write_text(PET_DECODER)
        subprocess.run(['g++', '-std=c++20', '-Isrc', str(cpp), 'src/player/pet_restore_state.c',
                        '-o', str(decoder)], cwd=ROOT, check=True)
        port, tls, websocket = journey.available_ports()
        env = dict(authority, CRITICAL_COMMAND_JOURNAL_DIR=str(runtime / 'journals/critical'),
                   DURIS_TLS_PORT=str(tls), DURIS_WEBSOCKET_PORT=str(websocket))
        journey.import_help(runtime, env)
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
                    client.send('save'); client.expect(f'Saving {name}.')
                    client.send('quit'); client.expect('ACCOUNT MENU', timeout=30)
                finally:
                    client.close()
                print('created synthetic fixture ' + name, flush=True)
            with ThreadPoolExecutor(max_workers=len(ROSTER)) as workers:
                list(workers.map(create, range(len(ROSTER))))
            stop(); seed_roster(sql); boot()
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
                    client.send('save'); client.expect(f'Saving {ROSTER[index][1]}.')
                return saved_conjurers(sql, decoder)

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
            staff.send('shutdown hotboot')
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
            REPORT.write_text(json.dumps(dict(backend='mariadb', checks=checks, state=restarted), indent=2))
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server', type=Path, required=True)
    run(parser.parse_args().server.resolve())
