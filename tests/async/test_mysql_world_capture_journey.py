#!/usr/bin/env python3
"""A capture of the full world publishes, inside its time, and a crash restores it
(persistence plan phase 8).

A real server on a disposable MariaDB and Redis boots the full world with world recovery
on, and with enough objects on the ground to put a generation above the old 64 MiB ceiling,
as staging's world is. Mortals on their own accounts play (they look, list what they carry
and save) while the first capture runs.

That first boot is on an empty database, so it also shows that a boot writes the SQL it
queues before its writer starts (work item #10): see boot_sql_missing(). Neither boot may
log `sql job not queued`.

The capture reports itself in the line that acknowledges its generation:
- the generation, above 64 MiB, was published;
- the capture took under a third of its 300 s (it took two thirds on an idle server);
- no pulse ran past 250 ms while it ran (`MUD TICK TOOK TOO LONG`).
The server is then killed and booted again: the boot restores that generation, with its
mobs, the items their zones load them with, and its objects.

The numbers it prints are the measurement: --players scales the load. Run it through
with_disposable_mariadb.sh (make test-db); --server picks the executable.
"""
from pathlib import Path
import argparse
import os
import re
import shutil
import socket
import subprocess
import tempfile
import time
import uuid

import test_flatfile_combat_journey as journey
import test_mysql_game_loop_budget_journey as budget

ROOT = Path(__file__).resolve().parents[2]
SECRET = 'local-development-only-world-state-hmac-change-before-shared-use'
OLD_CEILING = 64 * 1024 * 1024
CAPTURE_BUDGET_MS = 300000  # WORLD_RECOVERY_CAPTURE_MAX_AGE_MSEC
# Objects for the ground: a reset loads a takeable object again while one is in the room.
EXTRA_OBJECTS = 8000
EXTRA_OBJECT, EXTRA_ROOM = 677, 3
ACKNOWLEDGED = (r'world recovery generation and floor handoff acknowledged sequence=(\d+) '
                r'attempts=\d+ bytes=(\d+) capture_msec=(\d+)')
RESTORED = (r'restored world recovery generation sequence=(\d+) mobs=(\d+) objs=(\d+) '
            r'doors=(\d+) zones=(\d+)')
REHYDRATED = r'rehydrated recovered NPC zone items matched_mobs=(\d+) loaded_items=(\d+)'
CREATED = r'arti_update_sql: Creating entry: vnum: (\d+),'


class Player(budget.Mortal):
    """A mortal that enters the game and plays until the run stops."""

    def run(self):
        try:
            with budget.CREATING:
                self.client = journey.MudClient(self.port)
                journey.create_character(self.client, expected_room=None,
                                         account=self.account, character=self.name,
                                         email=self.account.lower() + '@example.invalid')
            self.play()
        except Exception as error:  # reported by the main thread
            self.error = f'{self.name}: {error}'


def free_port():
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        return listener.getsockname()[1]


def crowded_world(runtime):
    """The world's files, with the extra objects loaded by the first zone's reset."""
    areas = runtime / 'areas'
    areas.mkdir()
    for entry in (ROOT / 'areas').iterdir():
        if entry.name != 'world.zon':
            (areas / entry.name).symlink_to(entry)
    zones = (ROOT / 'areas/world.zon').read_text(encoding='latin-1').split('\n')
    first = zones.index('#0')
    end = zones.index('S', first)
    line = f'O 0 {EXTRA_OBJECT} 9999 {EXTRA_ROOM} 100 0 0 0'
    (areas / 'world.zon').write_text('\n'.join(zones[:end] + [line] * EXTRA_OBJECTS +
                                               zones[end:]), encoding='latin-1')


def boot_sql_missing(sql, log):
    """What the first boot queued before its writer started and did not write.

    The database began empty. Every artifact the zone resets load logs "Creating entry" and
    queues its row and its domain-state row. Each outpost queues its building's hit points
    over the 0 its row began with. The frag list read fills the cache on the first pulse.
    """
    created = sorted(set(map(int, re.findall(CREATED, log('artifact')))))
    missing = [] if created else ['any artifact']
    for table in ('artifacts', 'artifact_domain_state'):
        if sorted(map(int, sql(f'SELECT vnum FROM {table}').split())) != created:
            missing.append(table + ' rows')
    if sql('SELECT MIN(hitpoints) > 0 FROM outposts') != '1':
        missing.append('outpost hit points')
    if 'redis: cached fraglist' not in log('sys'):
        missing.append('the frag list cache')
    return missing


def run(server, players):
    database = 'world_capture_' + uuid.uuid4().hex[:12]
    host, port = os.environ['TEST_DB_HOST'], os.environ['TEST_DB_PORT']
    assert host == '127.0.0.1', 'use a disposable loopback database'
    redis_port = free_port()
    environment = {
        'PATH': os.environ.get('PATH', '/usr/bin:/bin'),
        'ENVIRONMENT': 'local', 'DB_HOST': host, 'DB_PORT': port, 'DB_NAME': database,
        'DB_USER': os.environ['TEST_DB_USER'], 'DB_PASSWD': os.environ['TEST_DB_PASSWORD'],
        'DB_ALLOWED_TARGETS': host + '/' + database,
        'MYSQL_PWD': os.environ['TEST_DB_PASSWORD'], 'PERSISTENCE_MODE': 'mariadb-primary',
        'DB_TLS': 'FALSE', 'CHAOS_MUD': 'FALSE',
        'LISTEN_ADDRESS': '127.0.0.1', 'DURIS_WEBSOCKET_LISTEN_ADDRESS': '127.0.0.1',
        'REDIS': 'TRUE', 'REDIS_HOST': '127.0.0.1', 'REDIS_PORT': str(redis_port),
        'REDIS_DB': '0', 'REDIS_NAMESPACE': 'duris:local:capture_' + uuid.uuid4().hex[:8],
        'REDIS_TLS': 'FALSE', 'REDIS_ALLOWED_TARGETS': f'127.0.0.1:{redis_port}/0',
        'REDIS_WORLD_STATE': 'TRUE', 'REDIS_WORLD_STATE_SECRET': SECRET,
        'REDIS_DONATION_SUBSCRIBER': 'FALSE',
    }
    if 'LD_LIBRARY_PATH' in os.environ:
        environment['LD_LIBRARY_PATH'] = os.environ['LD_LIBRARY_PATH']
    mysql = ['mysql', '--protocol=tcp', '-h', host, '-P', port, '-u', environment['DB_USER'],
             '-N', '-B']

    def sql(text, selected=True):
        return subprocess.check_output(mysql + ([database] if selected else []), input=text,
                                       text=True, env=environment).strip()

    sql('CREATE DATABASE ' + database + ' CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci',
        False)
    sql((ROOT / 'migrations/bootstrap_multithread_safe.sql').read_text())
    for args in (('adopt', '--kind', 'fresh_bootstrap'), ('run',)):
        subprocess.run(['python3', 'scripts/migration_runner.py', *args], cwd=ROOT,
                       env=environment, check=True, capture_output=True)
    world = subprocess.run(['make', 'world'], cwd=ROOT, text=True, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, timeout=600)
    assert world.returncode == 0, 'full-world data generation failed:\n' + world.stdout[-8000:]
    (ROOT / 'bin/tests').mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='world-capture-', dir=ROOT / 'bin/tests') as tmp:
        runtime = Path(tmp)
        crowded_world(runtime)
        for directory in ('areas_mini', 'docs'):
            (runtime / directory).symlink_to(ROOT / directory, target_is_directory=True)
        shutil.copytree(ROOT / 'lib', runtime / 'lib')
        journey.generate_certificate(runtime)
        (runtime / 'logs/log').mkdir(parents=True)
        (runtime / 'journals' / 'critical').mkdir(parents=True, mode=0o700)
        (runtime / 'redis').mkdir()
        environment.update(CRITICAL_COMMAND_JOURNAL_DIR=str(runtime / 'journals/critical'),
                           MAINTENANCE_STATE_FILE=str(runtime / 'maintenance-scheduler.state'))
        output_path = runtime / 'server.out'
        redis = subprocess.Popen(
            ['redis-server', '--bind', '127.0.0.1', '--port', str(redis_port), '--save', '',
             '--appendonly', 'no', '--dir', str(runtime / 'redis')],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        def log(name):
            path = runtime / 'logs/log' / name
            return path.read_text(errors='replace') if path.exists() else ''

        def boot():
            plain, tls, websocket = journey.available_ports()
            environment.update(DURIS_TLS_PORT=str(tls), DURIS_WEBSOCKET_PORT=str(websocket))
            started = time.monotonic()
            with output_path.open('w') as output:
                process = subprocess.Popen([str(server), '-d', str(runtime), str(plain)],
                                           cwd=runtime, env=environment, stdout=output,
                                           stderr=subprocess.STDOUT)
            while b'Entering game loop.' not in output_path.read_bytes():
                assert process.poll() is None and time.monotonic() - started < 600, \
                    'boot failed:\n' + output_path.read_text(errors='replace')[-4000:]
                time.sleep(0.1)
            return process, plain, time.monotonic() - started

        process = None
        mortals = []
        try:
            process, plain, boot_seconds = boot()
            assert 'sql job not queued' not in log('file'), log('file')[-2000:]
            written = time.monotonic() + 30
            while boot_sql_missing(sql, log):
                assert time.monotonic() < written, \
                    'the boot did not write: ' + ', '.join(boot_sql_missing(sql, log))
                time.sleep(0.5)
            mortals = [Player(plain, number) for number in range(players)]
            for mortal in mortals:
                mortal.start()

            # The first capture starts 30 seconds after the boot.
            deadline = time.monotonic() + 60 + CAPTURE_BUDGET_MS / 1000
            while not re.search(ACKNOWLEDGED, log('sys')):
                assert process.poll() is None, 'the server exited'
                assert not re.search(r'capture (?:failed|expired)|publish failed', log('sys')), \
                    'the capture failed:\n' + log('sys')[-2000:]
                assert time.monotonic() < deadline, 'no generation was published:\n' + \
                    log('sys')[-2000:]
                for mortal in mortals:
                    assert mortal.error is None, mortal.error
                time.sleep(0.5)
            sequence, size, capture_ms = map(int, re.search(ACKNOWLEDGED, log('sys')).groups())
            for mortal in mortals:
                mortal.stop.set()
            for mortal in mortals:
                mortal.join(timeout=60)
                assert mortal.error is None, mortal.error
                mortal.client.close()
            slow_pulses = re.findall(r'MUD TICK TOOK TOO LONG.*', log('status'))

            # A crash: the next boot restores the generation.
            process.kill()
            process.wait()
            killed = time.monotonic()
            process, _, _ = boot()
            while not (re.search(RESTORED, log('sys')) and
                       'Crash recovery complete' in log('status')):
                assert process.poll() is None, 'the server exited'
                assert time.monotonic() - killed < 300, 'the generation was not restored:\n' + \
                    log('sys')[-2000:] + log('status')[-2000:]
                time.sleep(0.5)
            recovery_seconds = time.monotonic() - killed
            restored, mobs, objects, doors, zones = map(
                int, re.search(RESTORED, log('sys')).groups())
            matched, carried = map(int, re.search(REHYDRATED, log('status')).groups())
        except Exception:
            print(output_path.read_text(errors='replace')[-4000:])
            print(journey.runtime_logs(runtime)[-6000:])
            raise
        finally:
            for mortal in mortals:
                mortal.stop.set()
                if mortal.client:
                    mortal.client.close()
            if process and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=120)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            redis.terminate()
            redis.wait(timeout=10)

        print(f'load: {players} mortals playing; the world booted in {boot_seconds:.0f} s')
        print(f'  generation {sequence}: {size} bytes ({size / 2**20:.1f} MiB), captured in '
              f'{capture_ms / 1000:.1f} s of its {CAPTURE_BUDGET_MS // 1000} s')
        print(f'  pulses past 250 ms while it ran: {len(slow_pulses)}')
        print(f'  restored {recovery_seconds:.0f} s after the kill: {mobs} mobs, {objects} '
              f'objects, {doors} doors, {zones} zones')
        print(f'  {matched} of the mobs were given the {carried} items their zones load them with')
        assert size > OLD_CEILING, f'the generation is {size} bytes, under the old ceiling'
        assert capture_ms < CAPTURE_BUDGET_MS / 3, f'the capture took {capture_ms} ms'
        assert not slow_pulses, 'a pulse ran past its 250 ms:\n' + slow_pulses[0]
        assert restored == sequence, (restored, sequence)
        assert mobs > 50000 and objects > EXTRA_OBJECTS, (mobs, objects)
        assert matched > 50000 and carried > 0, (matched, carried)
        assert 'sql job not queued' not in log('file'), log('file')[-2000:]
    print(f'world capture journey passed: {size / 2**20:.1f} MiB captured in '
          f'{capture_ms / 1000:.1f} s under {players} players, and restored after a crash')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server', type=Path, default=ROOT / 'bin/server/dms_new')
    parser.add_argument('--players', type=int, default=8)
    arguments = parser.parse_args()
    assert 0 <= arguments.players <= 63
    if not os.getenv('TEST_DB_HOST'):
        print('world capture journey skipped: run it through with_disposable_mariadb.sh')
    else:
        run(arguments.server.resolve(strict=True), arguments.players)
