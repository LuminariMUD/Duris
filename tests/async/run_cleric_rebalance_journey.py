#!/usr/bin/env python3
"""Qualify Cleric commands and saved affects on disposable flatfile/MariaDB authority."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import signal
import subprocess
import tempfile
import time
from pathlib import Path

import test_flatfile_combat_journey as journey
from test_flight_network_journey import authority
from run_paladin_balance_journey import command, configure, hp
from run_item_pilot_journey import Server, object_records, native_template
from run_divine_refusal_journey import drain

ROOT = journey.ROOT
NAMES = ('Clerica', 'Clericb', 'Clericd', 'Clericf')
HEADER = (ROOT / 'src/magic/spells.h').read_text()
DEFINES = (ROOT / 'src/core/defines.h').read_text()
MEM_STORE = 256 | 4 | 2 | 512  # NOAPPLY | NODISPEL | NOSHOW | PERM
MEM_FULL = 16  # AFFTYPE_CUSTOM1
SHORT = 1  # AFFTYPE_SHORT
assert '#define BIT_1 1U' in DEFINES and '#define BIT_9 256U' in DEFINES and '#define BIT_10 512U' in DEFINES


def spell_id(name):
    return int(re.search(r'^#define ' + name + r' (\d+)$', HEADER, re.M)[1])


SPELLS = [spell_id('SPELL_' + name) for name in (
    'MIRACLE', 'TRUE_SEEING', 'DIVINE_WARDING', 'VITAL_INTERCESSION')]
PROTECTIONS = {spell_id('SPELL_PROTECT_FROM_' + element)
               for element in ('FIRE', 'COLD', 'ACID', 'GAS', 'LIGHTNING', 'GOOD', 'EVIL')}


def cast(client, spell, target, expected):
    drain(client, .1)
    start = len(client.transcript)
    client.send(f"cast '{spell}' {target}".strip())
    client.expect(expected, timeout=35)
    drain(client, .2)
    return bytes(client.transcript[start:]).decode(errors='replace')


def saved_affects(sql, inspector, state, pid):
    if sql:
        text = sql(f'SELECT type,duration,flags,modifier,location FROM player_affects WHERE pid={pid} ORDER BY id')
        return [list(map(int, line.split('\t'))) for line in text.splitlines()]
    return json.loads(subprocess.check_output([str(inspector), str(state), 'cleric-inspect', str(pid)], text=True))

def seed_cleric(sql, inspector, state, pid, spec, level):
    if not sql:
        subprocess.run([str(inspector), str(state), 'cleric-seed', str(pid), str(spec), str(level)], check=True)
        return
    sql(f'UPDATE player_data SET level={level},highest_level={level},m_class=32,secondary_class=0,spec={spec},base_hit=2000,hit_diff=500 WHERE pid={pid}')
    sql(f'DELETE FROM player_skills WHERE pid={pid}; DELETE FROM player_affects WHERE pid={pid}')
    for number in SPELLS:
        sql(f'INSERT INTO player_skills(pid,skill_id,learned,taught) VALUES({pid},{number},100,100)')
        for _ in range(2 if number in (spell_id('SPELL_DIVINE_WARDING'),spell_id('SPELL_MIRACLE')) else 1):
            sql(f'INSERT INTO player_affects(pid,type,duration,flags,modifier) VALUES({pid},{spell_id('TAG_MEMORIZE')},-1,{MEM_STORE | MEM_FULL},{number})')
    for number in (spell_id('SKILL_SPELL_KNOWLEDGE_CLERICAL'), spell_id('SKILL_QUICK_CHANT'), spell_id('SKILL_CONCENTRATION')):
        sql(f'INSERT INTO player_skills(pid,skill_id,learned,taught) VALUES({pid},{number},100,100) ON DUPLICATE KEY UPDATE learned=100,taught=100')
    for number in (spell_id('SPELL_VITAL_INTERCESSION'), spell_id('SPELL_MIRACLE')):
        sql(f'INSERT INTO player_affects(pid,type,duration,flags,modifier) VALUES({pid},{spell_id('TAG_MEMORIZE')},-1,{MEM_STORE},{number})')


def run(binary, backend, inspector):
    with tempfile.TemporaryDirectory(prefix='cleric-' + backend + '-', dir=ROOT / 'bin/tests') as temporary:
        root = Path(temporary)
        configure(root, False)
        records = object_records((root/'areas/world.obj').read_text())
        records[2203] = object_records((ROOT/'areas/obj/seacaves.obj').read_text(encoding='latin1')+'\n$~')[2203]
        records[31514] = native_template(31514)
        objects = ''.join(records[v] for v in sorted(records))+'$~\n'
        (root/'areas/world.obj').write_text(objects)
        (root/'areas_mini/mini.obj').write_text(objects)
        (root/'bin/server').mkdir(parents=True)
        for name in ('dms','dms_new'):
            shutil.copy2(binary, root/'bin/server'/name)
        binary = root/'bin/server/dms'
        # Copy the miniature scene and keep all saves/listeners inside this fixture.
        (root / 'help').symlink_to(ROOT / 'help', target_is_directory=True)
        with authority(backend, root) as (env, sql):
            state = Path(env.get('FLATFILE_STATE_DIR', root / 'unused-state'))
            if not sql:
                (state / 'domains').mkdir(mode=0o700)
                subprocess.run([str(inspector), str(state), 'seed-combat'], check=True)
            env['COPYOVER_STATE_FILE'] = str(root/'copyover.state')
            server = Server(binary, root, state, 'cleric', env)
            clients = []
            evidence = {'backend': backend,
                        'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
                        'level': 56, 'race': 'Human', 'gear': 'creation gear; no boons',
                        'properties': {'rechargeTime': 240,
                                       'healer.healing.mod': 1.2, 'white_aura': .2},
                        'pilot': False}

            def login(name, account=None):
                client = journey.reconnect_character(server.port, expected_room=None,
                    account=account or name, character=name)
                clients.append(client)
                command(client, 'toggle page off')
                return client

            def save(client, name):
                client.send('save')
                client.expect('Save complete for ' + name + '.', timeout=60)

            def stop():
                for client in clients:
                    client.close()
                clients.clear()
                server.stop()

            def saved(pid):
                return saved_affects(sql,inspector,state,pid)

            def seed(pid,spec,level):
                seed_cleric(sql,inspector,state,pid,spec,level)

            try:
                server.start()
                staff = journey.MudClient(server.port)
                clients.append(staff)
                journey.create_character(staff)
                save(staff, journey.CHARACTER)
                for i, name in enumerate(NAMES):
                    client = journey.MudClient(server.port, source_host=f'127.0.0.{i+2}')
                    clients.append(client)
                    journey.create_character(client, account=name, character=name,
                        email=name.lower() + '@example.invalid', class_name='c')
                    save(client, name)
                print('Created Cleric party and staff', flush=True)
                stop()
                if sql:
                    sql(f"UPDATE player_data SET level=62,highest_level=62 WHERE name='{journey.CHARACTER}'")
                else:
                    journey.make_overlord(state, journey.CHARACTER)
                for pid in range(2,len(NAMES)+2):
                    seed(pid, 2 if pid < 4 else (3 if pid == 4 else 1), 56)
                server.start()
                staff = login(journey.CHARACTER, journey.ACCOUNT)
                server.client = staff
                command(staff, 'vis 0')
                players = [login(name) for name in NAMES]
                for name, client in zip(NAMES, players):
                    command(client, 'toggle boon')
                    command(client, 'display ward')
                    command(client, f'consent {journey.CHARACTER}')
                    command(staff, 'group ' + name)
                print('Restored all specs and saved full/pending spell fixtures', flush=True)
                healer = players[0]
                # The actual former grant was Holyman-only. Stored full/pending
                # copies must not bypass the new grant table, including after restart.
                holyman = players[2]
                refused = cast(holyman, "vital intercession", "Clericd", "don't know")
                assert "don't know" in refused.lower(), refused
                command(holyman, 'rest')
                prayed = command(holyman, 'pray vital intercession')
                assert 'too powerful' in prayed.lower() or 'beyond your comprehension' in prayed.lower(), prayed
                command(holyman, 'stand')
                evidence['saved_vital_rejected'] = True
                aura = command(healer, 'innate aura_of_improved_healing')
                assert 'radiates from your finger' in aura, aura
                # Every spec is restored through the real innate command.
                for other in (players[2], players[3]):
                    unavailable = command(other, 'innate aura_of_improved_healing')
                    assert 'radiates from your finger' not in unavailable, unavailable
                reset = command(staff, 'resetspec Clerica')
                assert 'They are no longer specialized' in reset, reset
                for client in players:
                    assert 'improved healing' not in command(client, 'score').lower()
                command(staff, 'setbit char Clerica spec 2')
                aura = command(healer, 'innate aura_of_improved_healing')
                assert 'radiates from your finger' in aura, aura
                evidence['staff_unspec_revokes_aura'] = True
                print('Aura entitlement and staff cleanup passed', flush=True)
                command(staff, 'setbit room here flag NO_HEAL 1')
                # Keep the ordinary caster in the staff-led fixture party.
                # Current eligibility takes precedence over stored Miracle slots.
                command(staff, 'setbit char Clerica level 35')
                refused = cast(healer, "miracle", "", "don't know")
                assert "don't know" in refused.lower(), refused
                command(staff, 'setbit char Clerica level 36')
                cast(staff,'vitality',NAMES[3],'You complete your spell')
                stronger_before = hp(staff,NAMES[3])[1]
                before_hp = hp(staff, NAMES[1])[1]
                cast(healer, 'miracle', '', 'You complete your spell')
                miracle_hp = hp(staff, NAMES[1])[1]
                assert miracle_hp - before_hp == 144, (before_hp, miracle_hp)
                command(staff, 'load obj 31514')
                given = command(staff, 'give trident Clerica')
                assert 'do not seem' not in given and 'No such' not in given, given
                command(healer, 'remove all')
                wielded = command(healer, 'wield trident')
                assert 'You wield' in wielded, wielded
                command(staff,'setbit char Clericb hit 10')
                tapped = command(healer, 'tap trident')
                assert 'You tap' in tapped, tapped
                tsunami_hp = hp(staff, NAMES[1])[1]
                expected = 60
                assert tsunami_hp - miracle_hp == expected, (miracle_hp, tsunami_hp, expected)
                current_hp,_ = hp(staff,NAMES[1])
                assert current_hp == 10+expected, current_hp
                position = command(staff,'stat char '+NAMES[1])
                assert 'Standing Normal' in position, position
                assert hp(staff,NAMES[3])[1] == stronger_before
                save(players[1],NAMES[1])
                tapped_vitality = [row for row in saved(3) if row[0] == spell_id('SPELL_VITALITY')]
                assert len(tapped_vitality) == 1 and tapped_vitality[0][1] == 15, tapped_vitality
                cast(healer, 'miracle', '', 'You complete your spell')
                assert hp(staff, NAMES[1])[1] == tsunami_hp
                assert hp(staff,NAMES[3])[1] == stronger_before
                save(players[1], NAMES[1])
                vitality = [row for row in saved(3) if row[0] == spell_id('SPELL_VITALITY')]
                assert len(vitality) == 1 and vitality[0][3] == 204, vitality
                evidence['miracle_tsunami_order'] = {'miracle_bonus':144,'tap_upgrade':expected,'final_affect':vitality,'tap_duration':tapped_vitality[0][1],'stronger_62_level_buff_preserved':True}
                command(staff,'setbit char Clerica level 45')
                refused = cast(healer,"true seeing", "", "don't know")
                assert "don't know" in refused.lower(), refused
                command(staff,'setbit char Clerica level 46')
                cast(healer,'true seeing','', 'You complete your spell')
                evidence['true_seeing_unlock'] = 46
                print('Spell progression, buff order and low-HP upgrade passed', flush=True)
                command(staff, 'setbit char Clerica level 56')
                command(staff, 'setbit room here flag NO_HEAL 1')
                # The real parser rejects targeting another player with self-only Warding.
                rejected = cast(healer, "divine warding", "Clericb", "yourself")
                assert 'yourself' in rejected.lower() or 'self' in rejected.lower(), rejected
                cast(healer, 'divine warding', '', 'protected from')
                save(healer, NAMES[0])
                original = {row[0]: row for row in saved(2) if row[0] in PROTECTIONS}
                assert len(original) == 7, original
                assert all(row[2] & SHORT and 2500 < row[1] <= 2640 for row in original.values()), original
                server.process.send_signal(signal.SIGUSR1)
                healer.expect('Copyover complete!', timeout=180)
                time.sleep(3)
                save(healer, NAMES[0])
                later = {row[0]: row for row in saved(2) if row[0] in PROTECTIONS}
                assert all(later[key][1] < original[key][1] for key in PROTECTIONS), (original,later)
                evidence['saved_protection_remaining_pulses'] = [original, later]
                stop()
                server.start()
                staff = login(journey.CHARACTER, journey.ACCOUNT)
                server.client = staff
                healer = login(NAMES[0])
                save(healer, NAMES[0])
                restored = {row[0]: row for row in saved(2) if row[0] in PROTECTIONS}
                assert set(restored) == PROTECTIONS, restored
                assert all(restored[key][1] <= later[key][1] for key in PROTECTIONS), (later,restored)
                evidence['restart_protection_remaining_pulses'] = restored
                print('Save/copyover/restart retained all seven remaining timers', flush=True)
                command(staff, 'load obj 2203')
                command(staff, 'drop altar')
                command(staff, 'setbit char Clerica epics 10')
                save(healer, NAMES[0])
                aura = command(healer, 'innate aura_of_improved_healing')
                assert 'radiates from your finger' in aura, aura
                healer.send('pray altar')
                healer.expect('Your old habits fall away', timeout=30)
                after = command(healer, 'innate aura_of_improved_healing')
                assert 'radiates from your finger' not in after, after
                assert 'improved healing' not in command(healer, 'score').lower()
                evidence['ordinary_unspec_revokes_aura'] = True
                stop()
                # Shorten only the saved test timers to prove restored expiry
                # without an eleven-minute wall-clock sleep in this journey.
                if sql:
                    sql('UPDATE player_affects SET duration=40 WHERE pid=2 AND (flags & 1) != 0')
                else:
                    subprocess.run([str(inspector),str(state),'cleric-expire','2'],check=True)
                server.start()
                healer = login(NAMES[0])
                server.client = healer
                save(healer, NAMES[0])
                assert len([row for row in saved(2) if row[0] in PROTECTIONS]) == 7
                time.sleep(11)
                save(healer, NAMES[0])
                assert not [row for row in saved(2) if row[0] in PROTECTIONS]
                evidence['restored_short_affects_expire'] = True
                print(json.dumps(evidence), flush=True)
                return evidence
            except Exception:
                print(server.output_path.read_text(errors='replace')[-3000:], flush=True)
                for client in clients:
                    print(bytes(client.transcript).decode(errors='replace').replace(journey.PASSWORD,'[REDACTED]')[-5000:], flush=True)
                raise
            finally:
                stop()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--backend', choices=('flatfile','mariadb'), default='flatfile')
    parser.add_argument('--inspector', type=Path, default=ROOT/'bin/tests/cleric-inspector')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run(args.binary.resolve(), args.backend, args.inspector.resolve())
    args.output.write_text(json.dumps(result, indent=2) + '\n')
