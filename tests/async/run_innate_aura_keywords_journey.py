#!/usr/bin/env python3
"""Qualify "innate aura <keyword>" and the aura help through a disposable real server.

Run once per backend. MariaDB needs TEST_DB_HOST/USER/PASSWORD for a disposable
loopback database; its fixture imports the maintained help sources.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import test_flatfile_combat_journey as journey
from test_flight_network_journey import authority
from run_paladin_balance_journey import command, configure
from run_item_pilot_journey import Server
from run_divine_refusal_journey import drain

ROOT = journey.ROOT
PLAYER = 'Auraknight'
NONE = 'You know no such aura!'


def plain(text):
    return re.sub(r'\x1b\[[0-9;]*m', '', text)


def run(binary, backend):
    with tempfile.TemporaryDirectory(prefix='aura-keywords-' + backend + '-', dir=ROOT / 'bin/tests') as temporary:
        root = Path(temporary)
        configure(root, False)
        (root / 'bin/server').mkdir(parents=True)
        for name in ('dms', 'dms_new'):
            shutil.copy2(binary, root / 'bin/server' / name)
        binary = root / 'bin/server/dms'
        (root / 'help').symlink_to(ROOT / 'help', target_is_directory=True)
        with authority(backend, root) as (env, sql):
            state = Path(env.get('FLATFILE_STATE_DIR', root / 'unused-state'))
            if not sql:
                (state / 'domains').mkdir(mode=0o700)
                subprocess.run([str(journey.INSPECTOR), str(state), 'seed-combat'], check=True)
            server = Server(binary, root, state, 'aura', env)
            clients = []
            try:
                server.start()
                staff = journey.MudClient(server.port)
                clients.append(staff)
                journey.create_character(staff)
                staff.send('save')
                staff.expect('Saving ' + journey.CHARACTER + '.', timeout=60)
                player = journey.MudClient(server.port, source_host='127.0.0.2')
                clients.append(player)
                journey.create_character(player, account=PLAYER, character=PLAYER,
                                         email='aura@example.invalid')
                player.send('save')
                player.expect('Saving ' + PLAYER + '.', timeout=60)
                for client in clients:
                    client.close()
                clients.clear()
                server.stop()
                if sql:
                    sql(f"UPDATE player_data SET level=62,highest_level=62 WHERE name='{journey.CHARACTER}'")
                else:
                    journey.make_overlord(state, journey.CHARACTER)
                server.start()
                staff = server.client = journey.reconnect_character(server.port)
                player = journey.reconnect_character(server.port, account=PLAYER, character=PLAYER,
                                                     source_host='127.0.0.2')
                clients.append(player)
                command(staff, 'vis 0')
                command(player, 'toggle page off')

                def innate(text, expected):
                    # Wait for the reply itself: rank-up notices print their own prompt.
                    drain(player, 0.1)
                    player.send('innate ' + text)
                    player.expect(expected, timeout=20)

                def become(cls, level, spec=None):
                    command(staff, f'setbit char {PLAYER} class {cls}')
                    command(staff, f'setbit char {PLAYER} level {level}')
                    if spec is not None:
                        command(staff, f'setbit char {PLAYER} spec {spec}')

                become('Paladin', 50)
                for text, glow in (('aura prot', 'blue glow'), ('aura p', 'blue glow'),
                                   ('aura pre', 'green glow'), ('aura e', 'yellow glow'),
                                   ('aura heal', 'white glow'), ('aura of improved healing', 'white glow'),
                                   ('aura b', 'blood-red glow'), ('AURA Battle', 'blood-red glow'),
                                   ('aura of protection', 'blue glow'),
                                   ('aura_of_precision', 'green glow'), ('aura', 'blue glow')):
                    innate(text, glow)
                innate('aura vig', NONE)
                innate('aura of', NONE)
                # Ordinary innate abbreviations are unchanged.
                innate('holy', 'This innate is always active.')
                print('PASS Paladin keywords, "of" syntax, full names and ordinary innates', flush=True)

                become('Anti-Paladin', 50)
                innate('aura v', 'purple glow')
                innate('aura of vigor', 'purple glow')
                innate('aura heal', NONE)
                become('Cleric', 50, 2)  # Healer: Spell Protection only
                innate('aura s', 'magenta glow')
                innate('aura p', NONE)
                become('Paladin', 20)
                innate('aura heal', NONE)
                innate('aura end', 'yellow glow')
                print('PASS ownership across classes, specs and unlock levels', flush=True)

                overview = plain(command(player, 'help paladin auras'))
                assert 'innate aura <keyword>' in overview, overview
                assert 'innate aura heal' in overview, overview
                vigor = plain(command(player, 'help aura of vigor'))
                assert 'innate aura vigor (or innate aura_of_vigor)' in vigor, vigor
                print('PASS help shows the shorthand on', backend, flush=True)
            except Exception:
                print(server.output_path.read_text(errors='replace')[-5000:])
                for client in [server.client, *clients]:
                    if client:
                        print(plain(bytes(client.transcript).decode(errors='replace'))
                              .replace(journey.PASSWORD, '[REDACTED]')[-4000:])
                raise
            finally:
                for client in clients:
                    client.close()
                server.stop()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--backend', choices=("mariadb",), required=True)
    args = parser.parse_args()
    run(args.binary.resolve(), args.backend)
