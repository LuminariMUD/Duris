#!/usr/bin/env python3
"""Both Gith Monks: real Telnet/WebSocket creation, kit, save, restart and relog."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile
import time
from test_account_recovery_journey import IsolatedServer, OLD_PASSWORD, ROOT, require, build_flatfile_server
import test_creation_prompt_journey as telnet
from test_character_stat_choice_journey import WebSocketClient

INSPECTOR = r'''
#include "flatfile/flatfile_player_snapshot_file.h"
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <set>
int main(int argc, char **argv) {
    assert(argc == 5);
    player_snapshot snapshot; std::string error;
    assert(flatfile_player_snapshot_read(argv[1], atoi(argv[2]), &snapshot, &error) == flatfile_player_load_result::ok);
    bool race=false, cls=false, side=false, alignment=false;
    int expected_race=atoi(argv[3]), expected_alignment=atoi(argv[4]);
    for (const auto &entry : snapshot.status_integers) {
        if (entry.field==player_status_field::race) race=entry.unsigned_value==static_cast<unsigned>(expected_race);
        if (entry.field==player_status_field::class_primary) cls=entry.unsigned_value==(1u<<6);
        if (entry.field==player_status_field::racewar) side=entry.unsigned_value==(expected_alignment>0?1u:2u);
        if (entry.field==player_status_field::alignment) alignment=entry.signed_value==expected_alignment;
    }
    assert(race && cls && side && alignment);
    std::set<int> kit;
    for (const auto &item : snapshot.items)
        if (item.vnum>=1147 && item.vnum<=1151) {
            kit.insert(item.vnum);
            assert(item.object_uid && item.equipment_slot>=0);
            printf("%d:%llu\n",item.vnum,static_cast<unsigned long long>(item.object_uid));
        }
    assert(kit.size()==5);
}
'''


def inspect(server, inspector, race, alignment):
    snapshots = list((server.state_root / 'players').glob('*.snapshot'))
    require(len(snapshots) == 1, 'expected one synthetic character')
    return subprocess.check_output([str(inspector), str(server.state_root), snapshots[0].stem,
                                    str(race), str(alignment)], text=True)


def restart(server):
    server.shutdown()
    telnet.reboot(server)
    deadline = time.monotonic() + 120
    while 'Entering game loop.' not in server.server_output():
        require(server.process.poll() is None and time.monotonic() < deadline,
                'restart failed: ' + server.server_output()[-4000:])
        time.sleep(.1)


def telnet_journey(binary, inspector, race, name, alignment):
    with IsolatedServer(binary, {}) as server:
        client = telnet.MudClient(server.plain_port)
        try:
            telnet.reach_race(client)
            telnet.reply(client, 'j' if alignment < 0 else 'n', 'Male or Female')
            telnet.reply(client, 'm', 'H (for Hardcore), N (for Normal)')
            menu = telnet.reply(client, 'n', telnet.RACE_MENU)
            require('Monk' in menu, f'{name} lacks Monk in ordinary class menu')
            client.send('k')
            prompt, _ = client.expect_any(('Your stat rolling system [D]:', telnet.RACE_MENU))
            if prompt == telnet.RACE_MENU:
                telnet.reply(client, 'c' if alignment < 0 else 'p', 'Your stat rolling system [D]:')
            telnet.reply(client, 'd', 'first bonus')
            for stat, next_prompt in zip('sdal', ('second bonus', 'third bonus', 'fourth bonus', 'swap stats (Y/N):')):
                telnet.reply(client, stat, next_prompt)
            telnet.reply(client, 'n', telnet.KEEP)
            telnet.reply(client, 'y', 'PRESS RETURN')
            telnet.reply(client, '', 'Your starter kit is ready')
            client.expect('Pos: standing >')
            telnet.reply(client, 'save', 'Save complete for Taverek.')
            before = inspect(server, inspector, race, alignment)
            client.close()
            restart(server)
            client = telnet.MudClient(server.plain_port)
            telnet.enter_account_name(client)
            client.expect('Please enter your password:')
            telnet.reply(client, OLD_PASSWORD, 'PRESS RETURN')
            telnet.reply(client, '', telnet.MENU)
            telnet.reply(client, '1', 'Taverek')
            telnet.reply(client, '1', '(Y/N)')
            telnet.reply(client, 'y', 'Pos: standing >')
            telnet.reply(client, 'save', 'Save complete for Taverek.')
            require(inspect(server, inspector, race, alignment) == before, 'Telnet kit identities changed on reload')
            print(f'PASS Telnet {name} Monk: fixed alignment/faction, equipped kit, save/restart/relog', flush=True)
        finally:
            client.close()


def ws_save(client):
    response = client.command('game', 'save', 'text')
    deadline = time.monotonic() + 15
    while 'Save complete for Taverek' not in json.dumps(response):
        require(time.monotonic() < deadline, 'save did not commit')
        response = client.receive()


def websocket_journey(binary, inspector, race, name, alignment):
    with IsolatedServer(binary, {'DURIS_WEBSOCKET': 'TRUE'}) as server:
        client = WebSocketClient(server.websocket_port)
        try:
            client.command('register', {'account': 'Githjourney', 'password': OLD_PASSWORD,
                                       'email': 'gith@example.invalid'}, 'auth')
            options = client.command('chargen_options')
            row = next(row for row in options['races'] if row['id'] == race)
            monk = next(cls for cls in row['classes'] if cls['name'].lower() == 'monk')
            homes = client.command('get_hometowns', {'race': race}, 'hometowns')
            client.command('roll_stats', {'race': race, 'method': 'default'})
            for stat in ('str', 'dex', 'agi', 'luk'):
                client.command('add_bonus', {'stat': stat}, 'bonus_added')
            created = client.command('create_character', {'name': 'Taverek', 'race': race,
                'class': monk['id'], 'sex': 1, 'alignment': 'good' if alignment > 0 else 'evil',
                'hometown': homes['options'][0]['id'], 'newbie': True})
            require(created['status'] == 'created', f'WebSocket creation failed: {created}')
            ws_save(client)
            before = inspect(server, inspector, race, alignment)
            client.close()
            restart(server)
            client = WebSocketClient(server.websocket_port)
            client.command('login', {'account': 'Githjourney', 'password': OLD_PASSWORD}, 'auth')
            client.command('enter', {'character': 'Taverek'}, 'gmcp')
            ws_save(client)
            require(inspect(server, inspector, race, alignment) == before, 'WebSocket kit identities changed on reload')
            print(f'PASS WebSocket {name} Monk: fixed alignment/faction, equipped kit, save/restart/relog', flush=True)
        finally:
            client.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, help='Fresh flat-file server build')
    args = parser.parse_args()
    build = ROOT / 'bin/tests'
    build.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='gith-monk-journey-', dir=build) as directory:
        binary = args.binary.resolve() if args.binary else build_flatfile_server(Path(directory) / 'server')
        cpp, inspector = Path(directory) / 'inspect.cpp', Path(directory) / 'inspect'
        cpp.write_text(INSPECTOR)
        subprocess.run(['g++', '-std=c++20', '-Isrc', str(cpp),
            'src/player/player_snapshot_codec.c', 'src/flatfile/flatfile_player_snapshot_file.c',
            'src/flatfile/flatfile_store.c', '-lcrypto', '-o', str(inspector)], cwd=ROOT, check=True)
        for race, name, alignment in ((16, 'Githyanki', -1000), (30, 'Githzerai', 1000)):
            telnet_journey(binary, inspector, race, name, alignment)
            websocket_journey(binary, inspector, race, name, alignment)


if __name__ == '__main__':
    main()
