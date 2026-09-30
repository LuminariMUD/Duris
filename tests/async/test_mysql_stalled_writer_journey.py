#!/usr/bin/env python3
"""Logging out and shutting down never wait on the database (persistence reset phase 1).

A real server on a disposable MariaDB: with the writer stalled on locked tables
(player_items and log_entries), quit reaches the account menu and the game loop keeps
answering a second connection throughout; the save and the log row land once the tables
are free, and a relog reads the save. Shutdown then exits within its bound and names the
save it could not write twice: while the writer is blocked inside a query on a locked
table (the query is cut off at the deadline), and, on a second server, with the database
stopped. Run through run_mysql_stalled_writer_journey.sh, which sets TEST_DB_* and
TEST_DB_CONTAINER; --server picks the executable.
"""
from pathlib import Path
import argparse
import os
import signal
import subprocess
import tempfile
import threading
import time
import uuid

import test_flatfile_combat_journey as journey

ROOT = Path(__file__).resolve().parents[2]


class LoopProbe(threading.Thread):
    """Pings the game loop from a second connection's login prompt and records the
    slowest reply: a loop blocked on the database stops answering it."""

    def __init__(self, port):
        super().__init__(daemon=True)
        self.client = journey.MudClient(port)
        entry, _ = self.client.expect_any(('term type', 'account name'), timeout=20)
        if entry == 'term type':
            self.client.send('9')
            self.client.expect('account name', timeout=20)
        self.done = threading.Event()
        self.slowest = 0.0
        self.replies = 0
        self.error = None

    def run(self):
        try:
            while not self.done.is_set():
                started = time.monotonic()
                self.client.send('1')  # an illegal account name: re-prompted, nothing else
                self.client.expect('Account Name:', timeout=90)
                self.slowest = max(self.slowest, time.monotonic() - started)
                self.replies += 1
                time.sleep(0.2)
        except Exception as error:  # reported by the main thread
            self.error = error

    def finish(self):
        self.done.set()
        self.join(timeout=100)
        self.client.close()
        assert self.error is None, self.error
        return self.slowest, self.replies


def run(server):
    database = 'stalled_writer_' + uuid.uuid4().hex[:12]
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
    with tempfile.TemporaryDirectory(prefix='stalled-writer-', dir=ROOT / 'bin/tests') as tmp:
        runtime = Path(tmp)
        journey.make_fixture(runtime)
        journey.generate_certificate(runtime)
        (runtime / 'logs/log').mkdir(parents=True)
        for name in ('players', 'critical'):
            (runtime / 'journals' / name).mkdir(parents=True, mode=0o700)
        plain, tls, websocket = journey.available_ports()
        environment.update(PLAYER_SAVE_JOURNAL_DIR=str(runtime / 'journals/players'),
                           CRITICAL_COMMAND_JOURNAL_DIR=str(runtime / 'journals/critical'),
                           DURIS_TLS_PORT=str(tls), DURIS_WEBSOCKET_PORT=str(websocket))
        servers = []

        def start_server(name):
            output_path = runtime / (name + '.out')
            output = output_path.open('w')
            process = subprocess.Popen(
                [str(server), '--minimal', '-s', '-d', str(runtime), str(plain)], cwd=runtime,
                env=environment, stdout=output, stderr=subprocess.STDOUT)
            servers.append((process, output, output_path))
            deadline = time.monotonic() + 120
            while b'Entering game loop.' not in output_path.read_bytes():
                assert process.poll() is None and time.monotonic() < deadline, 'boot failed'
                time.sleep(0.1)
            return process, output_path

        def stop_server(process, output_path, bound):
            started = time.monotonic()
            process.send_signal(signal.SIGTERM)
            process.wait(timeout=120)
            elapsed = time.monotonic() - started
            assert elapsed < bound, f'shutdown took {elapsed:.1f}s'
            return elapsed, output_path.read_text(errors='replace')

        def lock_tables(tables):
            held = subprocess.Popen(mysql + ['--unbuffered', database], stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE, text=True, env=environment,
                                    bufsize=1)
            held.stdin.write('LOCK TABLES ' + tables + "; SELECT 'held';\n")
            held.stdin.flush()
            assert held.stdout.readline().strip() == 'held'
            return held

        def unlock(held):
            held.stdin.write('UNLOCK TABLES;\n')
            held.stdin.close()
            assert held.wait(timeout=15) == 0

        client = None
        lock = None
        try:
            process, output_path = start_server('server')
            client = journey.MudClient(plain)
            journey.create_character(client)
            client.send('save')
            client.expect('Save complete for ' + journey.CHARACTER + '.', timeout=30)
            pid = int(sql("SELECT pid FROM player_data WHERE name='" + journey.CHARACTER + "'"))
            held = sql(f'SELECT COUNT(*) FROM player_items WHERE pid={pid}')
            # `save` leaves a command lag; let it pass so quit runs when it is sent.
            client.send('look')
            client.expect('Obvious exits', timeout=20)
            client.expect('Pos: standing >', timeout=10)

            # The writer stalls on locked tables; quit still leaves, and the game loop
            # never waits: not for the save, and not for the log row.
            lock = lock_tables('player_items WRITE, log_entries WRITE')
            camped_rows = ("SELECT COUNT(*) FROM log_entries WHERE player_name='" +
                           journey.CHARACTER + "' AND message='Camped'")
            probe = LoopProbe(plain)
            probe.start()
            # Quitting here is camping, which has its own delay. The old terminal save
            # timed out on the stalled writer and cancelled the camp, and the camp's log
            # row blocked the loop on its INSERT; now the character reaches the menu
            # while the tables are still locked.
            started = time.monotonic()
            client.send('quit')
            _, camped = client.expect_any(('ACCOUNT MENU',), timeout=60)
            quit_elapsed = time.monotonic() - started
            slowest, replies = probe.finish()
            assert 'could not be saved' not in camped, camped
            assert replies >= 10 and slowest < 3, \
                f'the game loop stalled: slowest reply {slowest:.1f}s over {replies}'
            client.send('0')
            client.close()
            client = None
            unlock(lock)
            lock = None
            # The queued save and log row land, and a relog reads the save.
            client = journey.reconnect_character(plain)
            client.send('inventory')
            client.expect('Pos: standing >', timeout=15)
            assert sql(f'SELECT COUNT(*) FROM player_items WHERE pid={pid}') == held
            assert sql(camped_rows) == '1', 'the queued log row did not land'
            print(f'camp on a stalled writer: menu after {quit_elapsed:.1f}s with the tables '
                  f'locked, slowest loop reply {slowest:.2f}s; the save and log row landed '
                  'after, and a relog read the save', flush=True)

            # Shutdown while the writer is blocked inside a query on a locked table: the
            # database answers, but not for this table. At the deadline the query is cut
            # off, and the save is named.
            lock = lock_tables('player_items WRITE')
            client.send('drop all')
            client.expect('Pos: standing >', timeout=15)
            client.send('save')
            client.expect('Pos: standing >', timeout=15)
            client.close()
            client = None
            elapsed, output = stop_server(process, output_path, 45)
            logs = journey.runtime_logs(runtime) + output
            assert ('domain=persistence_writer/player action=not_written outcome=alert '
                    f'detail=owner={pid}') in logs, \
                'shutdown did not name the save it could not write'
            unlock(lock)
            lock = None
            print(f'shutdown with the writer blocked in a query: exited in {elapsed:.1f}s and '
                  'named the unwritten save', flush=True)

            # With the database stopped, shutdown still exits within its bound.
            process, output_path = start_server('server-2')
            client = journey.reconnect_character(plain)
            client.send('inventory')
            client.expect('Pos: standing >', timeout=15)
            subprocess.run(['docker', 'stop', '-t', '0', os.environ['TEST_DB_CONTAINER']],
                           check=True, capture_output=True)
            client.send('drop all')
            client.expect('Pos: standing >', timeout=15)
            client.close()
            client = None
            elapsed, output = stop_server(process, output_path, 60)
            logs = journey.runtime_logs(runtime) + output
            assert logs.count('not_written') >= 2, 'shutdown did not name the unwritten save'
            print(f'shutdown with the database down: exited in {elapsed:.1f}s and named the '
                  'unwritten save', flush=True)
        except Exception:
            for _, _, path in servers:
                print(path.read_text(errors='replace')[-6000:])
            print(journey.runtime_logs(runtime)[-6000:])
            raise
        finally:
            if client:
                client.close()
            if lock and lock.poll() is None:
                lock.kill()
            for process, output, _ in servers:
                if process.poll() is None:
                    process.kill()
                    process.wait()
                output.close()
    print('stalled writer journey passed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server', type=Path, default=ROOT / 'bin/server/dms_new')
    arguments = parser.parse_args()
    if not os.getenv('TEST_DB_HOST') or not os.getenv('TEST_DB_CONTAINER'):
        print('stalled writer journey skipped: run it through run_mysql_stalled_writer_journey.sh')
    else:
        run(arguments.server.resolve(strict=True))
