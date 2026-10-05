#!/usr/bin/env python3
"""rent, quit and the hourly event never cost the game loop a pulse (persistence plan
phase 7).

A real server on a disposable MariaDB boots the full world. Mortals on their own accounts
play side by side (they look, list what they carry and save); each camps out with
`quit`, enters again, is brought to an inn by a god and rents there, and enters again. The
god, carrying a pile of loaded items, rents last. The run lasts past the hourly event,
whose first run after a boot saves every shop.

The loop times itself, and the journey reads its records. The budget is one pulse, 250 ms:
- the hourly event ran, by its line in the event analytics, inside the budget;
- no command, a `rent` and a `quit` among them, ran past it (`COMMAND OP SLOW`);
- no pulse ran past it (`MUD TICK TOOK TOO LONG`);
- no pulse deferred events with time left in its 25 ms event budget;
- every callback the analytics and the slow-event records name has a name.
What the hourly save costs the players is judged too: it queues at most 16 shop saves in a
pulse, and every re-entry, the god's as that save runs, takes under the 3 s a load waits
for its character's queued save.

The numbers it prints (the trace's tick, event and command times, the event debt, the
callbacks that cost the most) are the measurement: --players and --hours scale the load.
Run it through with_disposable_mariadb.sh (make test-db); --server picks the executable.
"""
from pathlib import Path
import argparse
import os
import re
import shutil
import signal
import subprocess
import tempfile
import threading
import time
import uuid

import test_flatfile_combat_journey as journey

ROOT = Path(__file__).resolve().parents[2]

PULSE_US = 250000
EVENT_BUDGET_US = 25000  # NEVENT_BUDGET_USEC_DEFAULT
SHOP_SAVE_QUEUE = 16  # SHOPKEEPER_SAVE_QUEUE
RE_ENTRY_S = 3  # PLAYER_LOAD_TIMEOUT_USEC: a load waits this long for its character's save
INN_ROOM = 81019
INN_NAME = 'The Entryway of the Golden Cat Inn'
GOD_ITEMS = 60
# What a mortal sends, one line every half second. It stays in its room: the next one
# refuses a camp.
PLAY = ('look', 'inventory', 'score', 'equipment', 'who', 'time', 'weather', 'save')
SYLLABLES = ('ka', 'vo', 'ri', 'ne', 'lu', 'ta', 'mo', 'se')
GOD = 'Sesen'
# The password worker queues 16 hashes and refuses the rest.
CREATING = threading.BoundedSemaphore(8)


def character_name(number):
    """A name per player; the last of the 64 is the god's."""
    return (SYLLABLES[number % 8] + SYLLABLES[number // 8] + 'n').capitalize()


def enter_game(client, character):
    """From the account menu into the game; returns the seconds it took from the request.
    A load that gave up waiting for the character's queued save is asked again, and its
    wait counts."""
    client.send('1')
    client.expect(character, timeout=30)
    asked = None
    for _ in range(5):
        client.send('1')
        client.expect('Play as', timeout=30)
        client.send('y')
        asked = asked or time.monotonic()
        entered, _ = client.expect_any(('Pos: standing >', 'temporarily unavailable'),
                                       timeout=60)
        if entered == 'Pos: standing >':
            return time.monotonic() - asked
    raise AssertionError(character + ' was refused five times')


class Mortal(threading.Thread):
    def __init__(self, port, number):
        super().__init__(daemon=True)
        self.port = port
        self.name = character_name(number)
        self.account = 'Budget' + self.name.lower()
        self.client = None
        self.camped = threading.Event()
        self.rented = threading.Event()
        self.stop = threading.Event()
        self.entries = []
        self.error = None

    def play(self, seconds=None):
        """Send the play commands for that long; with no time given, until the run stops
        or the god brings this character to the inn (which returns True)."""
        inn = INN_NAME.encode()
        started = time.monotonic()
        step = 0
        while not self.stop.is_set():
            if seconds and time.monotonic() - started >= seconds:
                break
            self.client.send(PLAY[step % len(PLAY)])
            step += 1
            until = time.monotonic() + 0.5
            while time.monotonic() < until:
                self.client._receive()
            if not seconds and not self.rented.is_set() and inn in self.client.pending:
                return True
            # Keep what could be the start of the inn's name.
            del self.client.pending[:-len(inn)]
        return False

    def run(self):
        try:
            with CREATING:
                self.client = journey.MudClient(self.port)
                journey.create_character(self.client, expected_room=None,
                                         account=self.account, character=self.name,
                                         email=self.account.lower() + '@example.invalid')
            self.play(10)
            # `save` leaves a command lag; let it pass so quit runs when it is sent.
            self.client.send('look')
            self.client.expect('Pos: standing >', timeout=30)
            self.client.send('quit')
            self.client.expect('Please select an option', timeout=90)
            self.entries.append(enter_game(self.client, self.name))
            self.camped.set()
            if self.play():
                self.client.send('rent')
                self.client.expect('Please select an option', timeout=60)
                self.entries.append(enter_game(self.client, self.name))
                self.rented.set()
                self.play()
        except Exception as error:  # reported by the main thread
            self.error = f'{self.name}: {error}'


def run(server, players, hours):
    database = 'loop_budget_' + uuid.uuid4().hex[:12]
    host, port = os.environ['TEST_DB_HOST'], os.environ['TEST_DB_PORT']
    assert host == '127.0.0.1', 'use a disposable loopback database'
    environment = {
        'PATH': os.environ.get('PATH', '/usr/bin:/bin'),
        'ENVIRONMENT': 'local', 'DB_HOST': host, 'DB_PORT': port, 'DB_NAME': database,
        'DB_USER': os.environ['TEST_DB_USER'], 'DB_PASSWD': os.environ['TEST_DB_PASSWORD'],
        'DB_ALLOWED_TARGETS': host + '/' + database,
        'MYSQL_PWD': os.environ['TEST_DB_PASSWORD'], 'PERSISTENCE_MODE': 'mariadb-primary',
        'DB_TLS': 'FALSE', 'REDIS': 'FALSE', 'CHAOS_MUD': 'FALSE',
        'LISTEN_ADDRESS': '127.0.0.1', 'DURIS_WEBSOCKET_LISTEN_ADDRESS': '127.0.0.1',
        'DURIS_NEVENT_ANALYTICS': '1', 'DURIS_PERSISTENCE_TRACE': '1',
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
    with tempfile.TemporaryDirectory(prefix='loop-budget-', dir=ROOT / 'bin/tests') as tmp:
        runtime = Path(tmp)
        for directory in ('areas', 'areas_mini', 'docs'):
            (runtime / directory).symlink_to(ROOT / directory, target_is_directory=True)
        shutil.copytree(ROOT / 'lib', runtime / 'lib')
        # A camp ends at the first short affect update (every 17.5 s), not the ninth.
        properties = runtime / 'lib/duris.properties'
        assert 'camp.timer=9.000' in properties.read_text(), 'the camp timer changed'
        properties.write_text(properties.read_text().replace('camp.timer=9.000',
                                                             'camp.timer=2.000'))
        # The launcher's step: the callback names of this executable.
        with (runtime / 'lib/misc/event_names').open('w') as names:
            subprocess.run([str(ROOT / 'scripts/event_names.sh'), str(server)], check=True,
                           stdout=names)
        journey.generate_certificate(runtime)
        (runtime / 'logs/log').mkdir(parents=True)
        (runtime / 'journals' / 'critical').mkdir(parents=True, mode=0o700)
        plain, tls, websocket = journey.available_ports()
        environment.update(CRITICAL_COMMAND_JOURNAL_DIR=str(runtime / 'journals/critical'),
                           MAINTENANCE_STATE_FILE=str(runtime / 'maintenance-scheduler.state'),
                           DURIS_TLS_PORT=str(tls), DURIS_WEBSOCKET_PORT=str(websocket))
        output_path = runtime / 'server.out'
        output = output_path.open('w')
        process = subprocess.Popen([str(server), '-d', str(runtime), str(plain)], cwd=runtime,
                                   env=environment, stdout=output, stderr=subprocess.STDOUT)
        mortals = [Mortal(plain, number) for number in range(players)]
        god = None
        try:
            deadline = time.monotonic() + 600
            while b'Entering game loop.' not in output_path.read_bytes():
                assert process.poll() is None and time.monotonic() < deadline, 'boot failed'
                time.sleep(0.1)
            booted = time.monotonic()
            for mortal in mortals:
                mortal.start()

            # The god: created, camped, promoted once the camp's save has landed (its log
            # row is queued after it), and at the inn with a pile of items.
            with CREATING:
                god = journey.MudClient(plain)
                journey.create_character(god, expected_room=None, account='Budgetgod',
                                         character=GOD, email='god@example.invalid')
            god.send('quit')
            god.expect('Please select an option', timeout=90)
            deadline = time.monotonic() + 60
            while sql(f"SELECT COUNT(*) FROM log_entries WHERE player_name='{GOD}' "
                      "AND message='Camped'") != '1':
                assert time.monotonic() < deadline, "the god's camp was not written"
                time.sleep(0.2)
            sql(f"UPDATE player_data SET level=62 WHERE name='{GOD}'")
            enter_game(god, GOD)
            god.send(f'goto {INN_ROOM}')
            god.expect(INN_NAME, timeout=30)
            for _ in range(GOD_ITEMS):
                god.send('load obj 677')
                god.expect('You have created', timeout=30)

            # Each mortal rents at the inn once it has camped, while the others play.
            for mortal in mortals:
                while not mortal.camped.wait(1):
                    assert mortal.error is None, mortal.error
                    assert time.monotonic() - booted < 600, mortal.name + ' never camped'
                god.send('trans ' + mortal.name)
                while not mortal.rented.wait(1):
                    assert mortal.error is None, mortal.error
                    assert time.monotonic() - booted < 900, mortal.name + ' never rented'
            # The god rents as the first hourly save queues its shops, and enters again
            # at once: its load waits for its own save, behind what the writer holds.
            debug_log = runtime / 'logs/log/debug'
            while 'sql_save_dirty_shopkeepers: saved' not in debug_log.read_text(
                    errors='replace'):
                assert time.monotonic() - booted < 300, 'the hourly save never ran'
                time.sleep(0.02)
            god.send('rent')
            god.expect('Please select an option', timeout=60)
            entries = [enter_game(god, GOD)]

            # Play on past the last hourly event, to the end of its 300-pulse window:
            # the event analytics and the latency trace are written a window at a time.
            def hourly_lines():
                status = (runtime / 'logs/log/status').read_text(errors='replace')
                return re.findall(r'NEVENT ANALYTICS CALLBACK: .*name=event_another_hour '
                                  r'calls=(\d+) total_us=\d+ avg_us=\S+ max_us=(\d+)', status)

            # The first hourly event comes 500 pulses after the boot, the rest every 300.
            trace_path = runtime / 'logs/latency_trace.log'
            windows = hours + 1
            deadline = booted + windows * 75 + 60
            while (sum(int(calls) for calls, _ in hourly_lines()) < hours or
                   trace_path.read_text().count('END LATENCY TRACE') < windows):
                assert time.monotonic() < deadline, 'the hourly event was never reported'
                for mortal in mortals:
                    assert mortal.error is None, mortal.error
                time.sleep(1)
            for mortal in mortals:
                mortal.stop.set()
            for mortal in mortals:
                mortal.join(timeout=120)
                assert mortal.error is None, mortal.error
                entries += mortal.entries
            elapsed = time.monotonic() - booted
        except Exception:
            print(output_path.read_text(errors='replace')[-6000:])
            print(journey.runtime_logs(runtime)[-6000:])
            raise
        finally:
            for client in [god] + [mortal.client for mortal in mortals]:
                if client:
                    client.close()
            process.send_signal(signal.SIGTERM)
            try:
                process.wait(timeout=120)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            output.close()

        # Shutdown drained the writer: every camp and every rent is in the log.
        logged = dict(line.split('\t') for line in sql(
            "SELECT message, COUNT(*) FROM log_entries WHERE message IN "
            "('Camped', 'Rented Out') GROUP BY message").splitlines())
        assert logged == {'Camped': str(players + 1), 'Rented Out': str(players + 1)}, logged

        status = (runtime / 'logs/log/status').read_text(errors='replace')
        report(status, trace_path.read_text(), players, elapsed)
        shop_saves = [int(saved) for saved in re.findall(
            r'sql_save_dirty_shopkeepers: saved (\d+) shopkeepers', debug_log.read_text())]
        print(f'  slowest re-entry {max(entries):.2f} s of {len(entries)}; {sum(shop_saves)} '
              f'shop saves queued over {len(shop_saves)} pulses, at most {max(shop_saves)} '
              'in one')
        slowest_hour = max(int(slowest) for _, slowest in hourly_lines())
        assert slowest_hour < PULSE_US, f'the hourly event took {slowest_hour} us'
        assert max(shop_saves) <= SHOP_SAVE_QUEUE, \
            f'{max(shop_saves)} shop saves were queued in one pulse, ahead of the players\''
        assert max(entries) < RE_ENTRY_S, \
            f'a re-entry took {max(entries):.2f} s: its load waited for saves queued ahead'
        for operation, spent in re.findall(
                r'COMMAND OP SLOW: .*operation=(\S+) duration_us=(\d+)', status):
            assert int(spent) < PULSE_US, f'a {operation} took {spent} us'
        slow_pulses = re.findall(r'MUD TICK TOOK TOO LONG.*', status)
        assert not slow_pulses, 'a pulse ran past its 250 ms:\n' + slow_pulses[0]
        early = [line for line in re.findall(r'NEVENT BUDGET: .*', status)
                 if int(re.search(r'total_us=(\d+)', line).group(1)) < EVENT_BUDGET_US]
        assert not early, 'events were deferred inside the time budget:\n' + early[0]
        unnamed = re.findall(r'.*(?:name|slowest|max_late_name)=unknown function.*', status)
        assert not unnamed, 'an event callback has no name:\n' + '\n'.join(unnamed[:5])
    print(f'game loop budget journey passed: {players} mortals and a god camped and rented, '
          f'and the hourly event took at most {slowest_hour} us')


def report(status, trace, players, elapsed):
    """Print what the loop measured over the run."""
    print(f'load: {players} mortals and a god, {elapsed:.0f} s in the game loop')
    sections = {}
    for name, low, high, mean, samples in re.findall(
            r'^(\w+) +(\d+) +(\d+) +(\d+) +(\d+)$', trace, re.MULTILINE):
        total = sections.setdefault(name, [0, 0, 0])
        total[0] = max(total[0], int(high))
        total[1] += int(mean) * int(samples)
        total[2] += int(samples)
    for name in ('total_tick', 'ne_events', 'commands', 'activities', 'affect_and_points'):
        if name in sections:
            worst, weighted, samples = sections[name]
            print(f'  {name:18} max {worst:8} us   mean {weighted // samples:6} us   '
                  f'{samples} pulses')
    for label in ('MUD TICK TOOK TOO LONG', 'NEVENT SLOW', 'NEVENT BUDGET', 'NEVENT CATCHUP',
                  'COMMAND OP SLOW'):
        print(f'  {label}: {status.count(label)}')
    for line in re.findall(r'COMMAND OP SLOW: .*', status)[:8]:
        print('   ', re.sub(r'boot=\S+ ', '', line))
    deferring = [int(spent) for spent in re.findall(r'NEVENT BUDGET: .* total_us=(\d+)', status)]
    print(f'  pulses that deferred events: {len(deferring)}, '
          f'{sum(spent < EVENT_BUDGET_US for spent in deferring)} of them inside the 25 ms '
          'time budget')
    late = [sum(int(count) for count in re.findall(key + r'=(\d+)', status))
            for key in ('lateness_on_time', 'lateness_1', 'lateness_2_3', 'lateness_4_15',
                        'lateness_16_plus')]
    print('  events run on time, 1, 2-3, 4-15 and 16+ pulses late:', *late)
    callbacks = {}
    for name, calls, total, worst in re.findall(
            r'NEVENT ANALYTICS CALLBACK: .*name=(.+?) calls=(\d+) total_us=(\d+) avg_us=\S+ '
            r'max_us=(\d+)', status):
        entry = callbacks.setdefault(name, [0, 0, 0])
        entry[0] += int(calls)
        entry[1] += int(total)
        entry[2] = max(entry[2], int(worst))
    print('  callbacks by total time (calls, total us, max us):')
    for name, (calls, total, worst) in sorted(callbacks.items(),
                                              key=lambda item: -item[1][1])[:12]:
        print(f'    {name:32} {calls:9} {total:11} {worst:9}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server', type=Path, default=ROOT / 'bin/server/dms_new')
    parser.add_argument('--players', type=int, default=8)
    parser.add_argument('--hours', type=int, default=1)
    arguments = parser.parse_args()
    assert 1 <= arguments.players <= 63 and arguments.hours >= 1
    if not os.getenv('TEST_DB_HOST'):
        print('game loop budget journey skipped: run it through with_disposable_mariadb.sh')
    else:
        run(arguments.server.resolve(strict=True), arguments.players, arguments.hours)
