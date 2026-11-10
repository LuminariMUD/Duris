#!/usr/bin/env python3
"""Exercise MSP framing, quiet groups and map departures through real Telnet sockets.

Uses a disposable flat-file authority and a small authored map, with GMCP disabled.
No checkout .env or live player data is used.
"""
import argparse
from pathlib import Path
import re
import tempfile

import test_mariadb_combat_journey as journey
from run_divine_refusal_journey import drain
from run_item_pilot_journey import Server

ROOT = journey.ROOT


def configure(root):
    journey.make_fixture(root)
    journey.generate_certificate(root)
    (root / 'logs/log').mkdir(parents=True)
    mini = root / 'areas_mini'
    zone = re.sub(r'^[MGE] .*\n', '', (mini / 'mini.zon').read_text(), flags=re.M)
    zone = zone.replace('$~', '#5000\nMSP Test Map~\nmsp test map~\n500024 0 16 6 11 1\n5 5\nS\n$~')
    (mini / 'mini.zon').write_text(zone)
    rooms = ''
    for number in range(500000, 500025):
        rooms += f'#{number}\nMSP Map {number}~\nA quiet map test field.\n~\n5000 0 2\nS\n'
    path = mini / 'mini.wld'
    path.write_text(path.read_text().replace('$~', rooms + '$~'))
    path = mini / 'mini.obj'
    vest = ('#22850\nmspvest vest~\na plain MSP test vest~\nA plain MSP test vest lies here.~\n~\n'
            '9 13 3 0 11 0 0 9 0 0 0\n0 0 0 0 0 0 0 0\n1 0 100\nA\n13 40\n')
    path.write_text(path.read_text().replace('$~', vest + '$~'))
    (root / 'areas').unlink()  # Only the disposable fixture symlink.
    (root / 'areas').mkdir()
    for suffix in ('wld', 'mob', 'obj', 'zon'):
        (root / f'areas/world.{suffix}').write_text((mini / f'mini.{suffix}').read_text())
    for name in ('world.shp', 'world.qst', 'world.tab', 'world.weather'):
        path = mini / name
        (root / 'areas' / name).write_text(path.read_text() if path.exists() else '$~\n')
    (root / 'areas/world.trg').write_text('#~\n')
    # Other catalog files are immutable fixture inputs.
    for path in (ROOT / 'areas').iterdir():
        target = root / 'areas' / path.name
        if not target.exists():
            target.symlink_to(path, target_is_directory=path.is_dir())


def command(client, text):
    drain(client, .1)
    client.send(text)
    client.send('score')
    output = client.expect('Score information for', timeout=20)
    return output + drain(client, .5)


def run(binary):
    with tempfile.TemporaryDirectory(prefix='msp-journey-', dir=ROOT / 'bin/tests') as tmp:
        root = Path(tmp)
        runtime, state = root / 'runtime', root / 'state'
        runtime.mkdir(); state.mkdir(mode=0o700); (state / 'domains').mkdir(mode=0o700)
        configure(runtime)
        server = Server(binary, runtime, state, 'msp')
        clients = []
        try:
            server.start()
            for name in ('Mspwarden', 'Mspmember'):
                c = journey.MudClient(server.port); clients.append(c)
                journey.create_character(c, account=name, character=name,
                                         email=name.lower() + '@example.invalid')
                c.send('save'); c.expect('Saving ' + name + '.')
                c.send('quit'); c.expect('ACCOUNT MENU')
            for c in clients: c.close()
            clients.clear(); server.stop()
            for name in ('Mspwarden', 'Mspmember'): journey.make_overlord(state, name)
            server.start()
            for name in ('Mspwarden', 'Mspmember'):
                c = journey.reconnect_character(server.port, account=name, character=name)
                clients.append(c)
                command(c, 'toggle page off'); command(c, 'vis 0')
                command(c, 'toggle gmcp off'); command(c, 'toggle map on')
                command(c, 'toggle terminal msp')
                assert '<prompt>' in command(c, 'look')
            observer, member = clients
            command(observer, 'goto 500012'); command(member, 'goto 500013')
            drain(observer, .5)
            command(member, 'goto 22800')
            received = drain(observer, 1)
            assert '<automap>' in received, received
            for observer_room, member_room in ((500010, 500014), (500002, 500022)):
                command(observer, f'goto {observer_room}')
                command(member, f'goto {member_room}')
                drain(observer, .5)
                command(member, 'goto 22800')
                received = drain(observer, 1)
                assert '<automap>' in received, received
            command(observer, 'goto 500012')
            command(member, 'goto 500012')
            command(member, 'consent Mspwarden')
            grouped = command(observer, 'group Mspmember')
            assert 'member of your group' in grouped, grouped
            initial = command(observer, 'group')
            assert '<group>' in initial and 'Mspmember' in initial and 'Mspwarden' in initial, initial
            command(member, 'remove all')
            assert 'created' in command(member, 'load obj 22850')
            worn = command(member, 'wear mspvest')
            worn_hp = int(re.search(r'Hit points: -?\d+\((\d+)\)', worn)[1])
            command(observer, 'group'); drain(observer, .5)
            removed = command(member, 'remove mspvest')
            bare_hp = int(re.search(r'Hit points: -?\d+\((\d+)\)', removed)[1])
            assert worn_hp > bare_hp, (worn, removed)
            updated = drain(observer, 1)
            assert '<group>' in updated and f'/{bare_hp}H' in updated, updated
            command(observer, 'toggle terminal msp quiet')
            command(observer, 'group'); drain(observer, .2)
            command(member, 'setbit char Mspmember hit 10')
            command(member, 'rest')
            text = drain(observer, 2)
            assert '<group>' not in text, text
            manual = command(observer, 'group')
            assert '<group>' in manual and '</group>' in manual and 'Mspmember' in manual, manual
            assert '<prompt>' in manual and '</prompt>' in manual
            assert '<map>' in command(observer, 'look')
            restored = command(observer, 'toggle terminal msp')
            assert 'MSP markup' in restored and 'manual group' not in restored
            command(member, 'setbit char Mspmember hit 1')
            command(member, 'stand')
            automatic = drain(observer, 1)
            assert '<group>' in automatic and '</group>' in automatic, automatic
            print('PASS: Telnet MSP wrapped map departures, derived equipment HP, quiet/manual groups and prompt/map compatibility', flush=True)
        except Exception:
            print(server.output_path.read_text(errors='replace')[-6000:])
            for c in clients: print(bytes(c.transcript[-3000:]).decode(errors='replace'))
            raise
        finally:
            for c in clients: c.close()
            server.stop()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--server', type=Path, default=ROOT / 'bin/server/dms_new')
    run(parser.parse_args().server.resolve())
