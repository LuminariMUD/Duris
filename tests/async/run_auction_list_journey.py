#!/usr/bin/env python3
"""Exercise auction list through a real session on disposable TEST_DB_* authority."""
import argparse
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time

import test_flatfile_combat_journey as journey
from test_flight_network_journey import authority, command
from run_world_quest_dual_backend import setup_run_root

ROOT = journey.ROOT
PLAYER = 'Listreader'


def run(binary):
    (ROOT / 'bin/tests').mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='auction-list-', dir=ROOT / 'bin/tests') as directory:
        runtime = Path(directory)
        _, critical, output_path = setup_run_root(runtime)
        (runtime / 'help').symlink_to(ROOT / 'help', target_is_directory=True)
        executable = runtime / 'bin/server/dms'
        executable.parent.mkdir(parents=True)
        shutil.copy2(binary, executable)
        with (runtime / 'lib/misc/event_names').open('w') as names:
            subprocess.run([str(ROOT / 'scripts/event_names.sh'), str(executable)], stdout=names, check=True)
        plain, tls, websocket = journey.available_ports()
        client = None
        with authority('mariadb', runtime) as (env, sql), output_path.open('w') as output:
            env.update(CRITICAL_COMMAND_JOURNAL_DIR=str(critical), DURIS_TLS_PORT=str(tls),
                       DURIS_WEBSOCKET_PORT=str(websocket),
                       MAINTENANCE_STATE_FILE=str(runtime / 'maintenance.state'))
            process = subprocess.Popen([str(executable), '-d', str(runtime), str(plain)],
                                       cwd=runtime, env=env, stdout=output, stderr=subprocess.STDOUT)
            try:
                deadline = time.monotonic() + 180
                while b'Entering game loop.' not in output_path.read_bytes():
                    assert process.poll() is None and time.monotonic() < deadline, 'server failed to boot'
                    time.sleep(.1)
                client = journey.MudClient(plain)
                journey.create_character(client, expected_room=None, account='Listaccount',
                                         character=PLAYER, email='listreader@example.invalid')
                command(client, 'toggle paging no')
                for text in ('auc list plate 1000', 'auc list plate', 'auc list 1',
                             'auction list nonsense', 'auc list sort'):
                    response = command(client, text)
                    assert 'Valid keywords: horns, nose,' in response, response
                    assert ('Auction list syntax:' in response) == (text != 'auc list sort'), response
                    assert process.poll() is None
                    print('PASS:', text, flush=True)

                # Synthetic display rows exercise the real SQL filters and asynchronous
                # rendering without creating live item custody or testing auction writes.
                sql("INSERT INTO auctions (seller_pid,seller_name,obj_short,obj_vnum,obj_blob_str,"
                    "id_keywords,end_time,cur_price) VALUES "
                    "(900001,'Listreader','a display horn',900001,'',' horns, nose,',NOW()+INTERVAL 7 DAY,1000),"
                    "(900002,'Someoneelse','a display helm',900002,'',' head,',NOW()+INTERVAL 7 DAY,2000)")
                for text, present, absent in (
                    ('auc list', ('a display horn', 'a display helm'), ()),
                    ('auction list all', ('a display horn', 'a display helm'), ()),
                    ('auction list player Listreader', ('a display horn',), ('a display helm',)),
                    ('auction list sort horns nose', ('a display horn',), ('a display helm',)),
                    ('auction list sort head', ('a display helm',), ('a display horn',)),
                ):
                    start = len(client.transcript)
                    client.send(text)
                    client.expect(present[-1], timeout=30)
                    response = bytes(client.transcript[start:]).decode(errors='replace')
                    response += command(client, 'score')
                    assert all(name in response for name in present), response
                    assert all(name not in response for name in absent), response
                    print('PASS:', text, flush=True)
                for text, expected in (
                    ('auc list player Missing', 'No auctions found!'),
                    ('auc list player', 'Please enter the name of a player.'),
                    ('auc list sort nonexistent', 'is an invalid keyword!'),
                ):
                    client.send(text)
                    client.expect(expected, timeout=30)
                    command(client, 'score')
                    print('PASS:', text, flush=True)
                assert sql('SELECT COUNT(*) FROM auctions') == '2'
                client.send('save')
                client.expect('Save complete for ' + PLAYER + '.', timeout=60)
                client.close()
                client = None
                process.send_signal(signal.SIGTERM)
                process.wait(timeout=60)
                assert process.returncode == 0
                print('PASS: session remained usable, saved, and shut down cleanly', flush=True)
            except Exception:
                evidence = ROOT / 'bin/analysis/auction-list-failure'
                evidence.mkdir(parents=True, exist_ok=True)
                shutil.copy2(output_path, evidence / 'server.out')
                if client:
                    (evidence / 'client.txt').write_bytes(bytes(client.transcript))
                raise
            finally:
                if client:
                    client.close()
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=60)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=10)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server', type=Path, required=True)
    run(parser.parse_args().server.resolve())
