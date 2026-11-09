#!/usr/bin/env python3
"""Both Gith Monks: real Telnet/WebSocket creation, kit, save, restart and relog."""
import argparse
import json
from pathlib import Path
import time
from test_account_recovery_journey import IsolatedServer, OLD_PASSWORD, require
import test_creation_prompt_journey as telnet
from test_character_stat_choice_journey import WebSocketClient

def inspect(server, race, alignment):
    """Assert the saved race, Monk class, faction and alignment; return the kit's identities."""
    row = server.sql("SELECT pid,race,m_class,racewar,alignment FROM player_data WHERE name='Taverek'").split()
    require(row[1:] == [str(race), str(1 << 6), '1' if alignment > 0 else '2', str(alignment)],
            f'saved character is not the expected Monk: {row}')
    kit = server.sql(f"SELECT vnum,obj_uid,equip_slot FROM player_items WHERE pid={row[0]} "
                     "AND vnum BETWEEN 1147 AND 1151 ORDER BY vnum,obj_uid").splitlines()
    fields = [line.split() for line in kit]
    require({vnum for vnum, _, _ in fields} == {str(vnum) for vnum in range(1147, 1152)} and
            all(int(uid) and int(slot) >= 0 for _, uid, slot in fields), f'incomplete Monk kit: {kit}')
    return [f'{vnum}:{uid}' for vnum, uid, _ in fields]


def restart(server):
    server.shutdown()
    telnet.reboot(server)
    deadline = time.monotonic() + 120
    while 'Entering game loop.' not in server.server_output():
        require(server.process.poll() is None and time.monotonic() < deadline,
                'restart failed: ' + server.server_output()[-4000:])
        time.sleep(.1)


def telnet_journey(binary, race, name, alignment):
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
            telnet.reply(client, 'y', telnet.MENU)
            telnet.play_saved_character(client)
            telnet.reply(client, '', 'Your starter kit is ready')
            client.expect('Pos: standing >')
            telnet.reply(client, 'save', 'Saving Taverek.')
            before = inspect(server, race, alignment)
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
            telnet.reply(client, 'save', 'Saving Taverek.')
            require(inspect(server, race, alignment) == before, 'Telnet kit identities changed on reload')
            print(f'PASS Telnet {name} Monk: fixed alignment/faction, equipped kit, save/restart/relog', flush=True)
        finally:
            client.close()


def ws_save(client):
    response = client.command('game', 'save', 'text')
    deadline = time.monotonic() + 15
    while 'Saving Taverek' not in json.dumps(response):
        require(time.monotonic() < deadline, 'save did not commit')
        response = client.receive()


def websocket_journey(binary, race, name, alignment):
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
            client.enter_created_character('Taverek')
            ws_save(client)
            before = inspect(server, race, alignment)
            client.close()
            restart(server)
            client = WebSocketClient(server.websocket_port)
            client.command('login', {'account': 'Githjourney', 'password': OLD_PASSWORD}, 'auth')
            client.command('enter', {'character': 'Taverek'}, 'gmcp')
            ws_save(client)
            require(inspect(server, race, alignment) == before, 'WebSocket kit identities changed on reload')
            print(f'PASS WebSocket {name} Monk: fixed alignment/faction, equipped kit, save/restart/relog', flush=True)
        finally:
            client.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server', type=Path, required=True)
    binary = parser.parse_args().server.resolve()
    for race, name, alignment in ((16, 'Githyanki', -1000), (30, 'Githzerai', 1000)):
        telnet_journey(binary, race, name, alignment)
        websocket_journey(binary, race, name, alignment)


if __name__ == '__main__':
    main()
