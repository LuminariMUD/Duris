#!/usr/bin/env python3
"""Real MariaDB copyover failure/success on the original Telnet/MCCP socket.

Run with a MariaDB server path. Pass --full-world for the generated world.
Pass --redis-failures for private DB/Redis faults.
"""
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import ssl
import subprocess
import sys
import tempfile
import time
import zlib
import test_flatfile_combat_journey as journey
from test_gmcp_control_journey import negotiate, wait_telnet, telnet_packets
from test_flight_network_journey import command
from run_racial_pulse_journey import paged
from test_connection_limit_journey import send_frame, take_frame, upgrade


class Client(journey.MudClient):
    def __init__(self, port, *, source_host=None):
        super().__init__(port, source_host=source_host)
        self.inflater = None
        self.waiting_marker = False
        self.wire = b''
        self.compressed_bytes = 0

    def enable_compression(self):
        self.waiting_marker = True
        self.socket.sendall(bytes([255, 253, 86]))
        self.send('look')
        deadline = time.monotonic() + 15
        while self.inflater is None and time.monotonic() < deadline:
            self._receive()
        assert self.inflater is not None, 'MCCP was not negotiated'
        self.expect('The Regression Arena')

    def _receive(self):
        try: data = self.socket.recv(65536)
        except socket.timeout: return False
        assert data, 'server closed the original gameplay connection'
        plain = b''
        if self.waiting_marker:
            self.wire += data
            marker = bytes([255, 250, 86, 255, 240])
            at = self.wire.find(marker)
            if at < 0: return True
            plain, data = self.wire[:at], self.wire[at + len(marker):]
            self.wire = b''
            self.waiting_marker = False
            self.inflater = zlib.decompressobj()
        if self.inflater:
            self.compressed_bytes += len(data)
            plain += self.inflater.decompress(data)
            if self.inflater.eof:
                plain += self.inflater.unused_data
                self.inflater = None
        else: plain += data
        clean = self._clean(plain)
        self.pending.extend(clean); self.transcript.extend(clean)
        return True


def receive_until(session, marker, initial=b''):
    received = bytearray(initial)
    deadline = time.monotonic() + 10
    while marker not in received:
        remaining = deadline - time.monotonic()
        assert remaining > 0, received
        session.settimeout(remaining)
        data = session.recv(65536)
        assert data, received
        received.extend(data)
    return received


def login_roundtrip(session, received):
    if b'account name' not in received.lower():
        session.sendall(b'9\n')
        receive_until(session, b'account name', received)
    session.sendall(b'Copyotest\n')
    receive_until(session, b'is this correct?')


def redis_socket_inodes(pid, port):
    proc = Path(f'/proc/{pid}')
    remote = f'0100007F:{port:04X}'
    tcp = (proc / 'net/tcp').read_text().splitlines()[1:]
    candidates = {f'socket:[{row[9]}]' for line in tcp if (row := line.split())[2] == remote}
    opened = set()
    for fd in (proc / 'fd').iterdir():
        try:
            opened.add(os.readlink(fd))
        except FileNotFoundError:
            pass  # A short-lived Redis operation may have finished.
    return opened & candidates


def account_menu(port):
    session = journey.MudClient(port)
    entry, _ = session.expect_any(('term type', 'account name'))
    if entry == 'term type':
        session.send('9')
        session.expect('account name')
    # A login to the playing account would evict its existing connection.
    session.send('Menucopytest')
    session.expect('is this correct?')
    session.send('y')
    session.expect('email address')
    session.send('menucopytest@example.test')
    session.expect('is this correct?')
    session.send('y')
    session.expect('enter your password')
    session.send(journey.PASSWORD)
    session.expect('Please re-enter the same password to confirm:  ')
    session.send(journey.PASSWORD)
    session.expect('information correct?')
    session.send('y')
    session.expect('PRESS RETURN')
    session.send('')
    session.expect('Please select an option')
    return session


def player_periodic_events(client):
    events = {'event_autosave', 'event_hatred_check', 'event_smite_evil',
              'event_halfling_check', 'event_righteous_aura_check',
              'event_bleak_foeman_check', 'event_blood_tithe'}
    status = paged(client, f'stat char {journey.CHARACTER}', 'event_autosave')
    return {event for event in events if event in status}


def add_full_world_arena(runtime):
    # Keep the real world and its required services. Only replace the arena
    # room, mobs and loot marker in copies of the generated inputs.
    source = (runtime / 'areas').resolve()
    (runtime / 'areas').unlink()
    (runtime / 'areas').mkdir()
    for path in source.iterdir():
        (runtime / 'areas' / path.name).symlink_to(path, target_is_directory=path.is_dir())
    for suffix, numbers in (('wld', (22800,)), ('mob', (11, 22800)), ('obj', (15,))):
        path = runtime / f'areas/world.{suffix}'
        data = path.read_bytes()
        fixture = (runtime / f'areas_mini/mini.{suffix}').read_bytes()
        for number in numbers:
            record = rb'(?ms)^#%d\n.*?(?=^#\d+\n|^\$~)' % number
            match = re.search(record, fixture)
            assert match, (suffix, number)
            data, count = re.subn(record, lambda _: match[0], data)
            assert count == 1, (suffix, number, count)
        path.unlink()  # replace only the fixture's link
        path.write_bytes(data)
    path = runtime / 'areas/world.zon'
    zones = path.read_bytes()
    resets = (b'\nM 0 11 1 22800 100 0 0 0\nG 1 15 1 0 100 0 0 0\n'
              b'M 0 22800 1 22800 100 0 0 0\nS\n')
    assert b'\nS\n' in zones
    path.unlink()
    path.write_bytes(zones.replace(b'\nS\n', resets, 1))


def wait_artifact_bootstrap(client):
    # A fresh full catalogue publishes absent artifact identities in
    # bounded batches. Let it settle before injecting copyover faults.
    deadline = time.monotonic() + 180
    while True:
        status = paged(client, 'world persistence', 'artifact_guild')
        if re.search(r'artifact_guild .*dirty_artifacts=0 dirty_guilds=0 .*history_pending=0', status):
            break
        assert time.monotonic() < deadline, status
        time.sleep(.5)
    print('full-world artifact/guild bootstrap is durable before fault injection', flush=True)


def run(binary, compressed, nonroot=False, fresh=False, full_world=False, redis_failures=False):
    with journey.mariadb_authority() as (env, sql), \
            tempfile.TemporaryDirectory(prefix='duris-copyover-journey-') as temporary:
        root = Path(temporary)
        runtime = root / 'runtime'
        runtime.mkdir(); (runtime / 'logs/log').mkdir(parents=True)
        journey.make_fixture(runtime); journey.generate_certificate(runtime)
        if full_world:
            add_full_world_arena(runtime)
        (runtime / 'logs/log/.gitignore').write_text('*\n')
        (runtime / 'journals' / 'critical').mkdir(parents=True, mode=0o700)
        (runtime / 'bin/server').mkdir(parents=True)
        active = runtime / 'bin/server/dms'
        staged = runtime / 'bin/server/dms_new'
        shutil.copy2(binary, active)
        shutil.copy2(active, staged)
        event_names = runtime / 'lib/misc/event_names'
        event_names.parent.mkdir(exist_ok=True)
        event_names.unlink(missing_ok=True)  # replace the fixture's link, never the source
        with event_names.open('w') as output:
            subprocess.run([str(journey.ROOT / 'scripts/event_names.sh'), str(active)],
                           check=True, stdout=output)
        path = root / 'copyover-state/copyover.dat'
        port, tls, websocket = journey.available_ports()
        env.update(CRITICAL_COMMAND_JOURNAL_DIR=str(runtime / 'journals/critical'),
                   COPYOVER_STATE_FILE=str(path), DURIS_TLS_PORT=str(tls),
                   DURIS_WEBSOCKET_PORT=str(websocket), DURIS_WEBSOCKET='TRUE')
        process = output = client = redis_server = None
        fixture_user = None

        def stop():
            nonlocal process, output, client
            if client: client.close(); client = None
            if process and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            if output: output.close()

        def boot():
            nonlocal process, output
            output = (runtime / 'server.out').open('w')
            mode = [] if full_world else ['--minimal']
            process = subprocess.Popen([str(runtime / 'bin/server/dms'), *mode, '-s', str(port)],
                                       cwd=runtime, env=env, stdout=output, stderr=subprocess.STDOUT,
                                       user=fixture_user, group=fixture_user)
            deadline = time.monotonic() + 90
            while 'Entering game loop.' not in (runtime / 'server.out').read_text(errors='replace'):
                assert process.poll() is None and time.monotonic() < deadline, 'boot failed'
                time.sleep(0.1)

        def redis(*args):
            return subprocess.check_output(
                ['redis-cli', '-h', '127.0.0.1', '-p', str(redis_port), '--raw', *args],
                text=True, timeout=5, stderr=subprocess.DEVNULL).strip()

        try:
            if redis_failures:
                redis_port = journey.available_ports()[0]
                assert redis_port not in (port, tls, websocket)
                redis_server = subprocess.Popen(
                    ['redis-server', '--bind', '127.0.0.1', '--port', str(redis_port),
                     '--save', '', '--appendonly', 'no', '--dir', str(root)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                env.update(REDIS='TRUE', REDIS_HOST='127.0.0.1', REDIS_PORT=str(redis_port),
                           REDIS_DB='0', REDIS_NAMESPACE='duris:local:copyover-review',
                           REDIS_WORLD_STATE='TRUE',
                           REDIS_WORLD_STATE_SECRET='fixture-only-copyover-redis-secret-001')
                for _ in range(100):
                    try:
                        if redis('PING') == 'PONG':
                            break
                    except subprocess.CalledProcessError:
                        time.sleep(.05)
                else:
                    raise AssertionError('isolated Redis did not start')
            boot(); client = Client(port); journey.create_character(client)
            client.send('save'); client.expect(f'Saving {journey.CHARACTER}.')
            client.send('quit'); client.expect('ACCOUNT MENU', timeout=30)
            stop()
            sql("UPDATE player_data SET level=62,highest_level=62 WHERE name='" +
                journey.CHARACTER + "'")
            if nonroot:
                assert os.geteuid() == 0, '--nonroot fixture must start as root to drop to UID 10001'
                root.chmod(0o755)
                for directory, _, files in os.walk(root, followlinks=False):
                    os.chown(directory, 10001, 10001)
                    for name in files:
                        file = Path(directory) / name
                        if not file.is_symlink(): os.chown(file, 10001, 10001)
                os.chown(runtime, 0, 0); runtime.chmod(0o755)
                fixture_user = 10001
                assert runtime.stat().st_uid == 0 and runtime.stat().st_mode & 0o777 == 0o755
            boot()
            original = journey.MudClient
            journey.MudClient = Client
            try: client = journey.reconnect_character(port)
            finally: journey.MudClient = original
            negotiate(client)
            lifecycle = wait_telnet(client, 'Duris.Session', predicate=lambda state: state['state'] == 'playing')
            assert lifecycle['character']['name'] == journey.CHARACTER and not lifecycle['resumed']
            if redis_failures:
                path.parent.mkdir()
                prefix = env['REDIS_NAMESPACE'] + ':season:1:'
                current = prefix + 'world_state:current'
                assert redis('ACL', 'SETUSER', 'default', '-eval') == 'OK'
                try:
                    client.send('copyover')
                    client.expect('Copyover cancelled: world checkpoint failed.', timeout=60)
                    assert process.poll() is None and not path.exists()
                finally:
                    assert redis('ACL', 'SETUSER', 'default', '+eval') == 'OK'
                client.send('look'); client.expect('The Regression Arena')

                for _ in range(2):
                    before = redis_socket_inodes(process.pid, redis_port)
                    assert before, 'fixture has no live Redis connections'
                    client.send('copyover')
                    client.expect('Copyover complete!', timeout=60)
                    after = redis_socket_inodes(process.pid, redis_port)
                    assert after and before.isdisjoint(after), (before, after)
                    assert not path.exists() and not redis('GET', current)
                    assert 'generation and floor handoff acknowledged' in (
                        runtime / 'logs/log/sys').read_text(errors='replace')
                    # Let the SQL boot finish its bounded artifact retries.
                    client.send('save')
                    client.expect(f'Saving {journey.CHARACTER}.')
                    time.sleep(6)
                print('two real execs replaced every Redis socket', flush=True)
                valid = runtime / 'bin/server/fixture-replacement'
                shutil.copy2(active, valid)
                staged.write_text(f'#!/bin/sh\nmv lib/duris.properties lib/duris.properties.fixture\n'
                                  f'exec {valid} --minimal -C {port}\n')
                staged.chmod(0o700)
                client.send('copyover')
                assert process.wait(timeout=90) != 0
                stderr = (runtime / 'server.out').read_text(errors='replace')
                assert 'Could not load valid server properties' in stderr, stderr[-4000:]
                assert path.with_suffix('.dat.recovering').read_bytes().startswith(b'CPYP')
                sequence = redis('GET', current)
                assert sequence.isdecimal(), sequence
                assert redis('EXISTS', prefix + 'world_state:generation:' + sequence) == '1'
                print('Redis copyover consumes a committed cut, refuses a failed checkpoint, '
                      'and retains the world when replacement boot fails', flush=True)
                return
            if full_world:
                wait_artifact_bootstrap(client)
            if compressed: client.enable_compression()
            process.send_signal(signal.SIGUSR1)
            client.expect('Copyover FAILED', timeout=60)
            assert not path.exists() and process.poll() is None
            client.send('look'); client.expect('The Regression Arena')
            client.send('save'); client.expect(f'Saving {journey.CHARACTER}.', timeout=30)
            if compressed: assert client.inflater is not None and client.compressed_bytes > 0
            boot_log = (runtime / 'logs/log/status').read_text(errors='replace')
            assert 'copyover: cant open' in boot_log, 'copyover never reached the injected file-open failure'
            print(f'{compressed=}: failed open kept transport and save worker usable', flush=True)
            path.parent.mkdir()
            if nonroot: os.chown(path.parent, 10001, 10001)
            claimed = path.with_name(path.name + '.recovering')
            for pending in (path, claimed):
                pending.write_bytes(b'retained fixture evidence')
                if nonroot: os.chown(pending, 10001, 10001)
                process.send_signal(signal.SIGUSR1)
                client.expect('Copyover cancelled: prior recovery state needs review', timeout=30)
                assert pending.read_bytes() == b'retained fixture evidence'
                assert process.poll() is None
                client.send('save'); client.expect(f'Saving {journey.CHARACTER}.', timeout=30)
                pending.unlink()  # explicit disposition of this test's synthetic image
            # A terminal writer failure must preserve the live character and publish nothing.
            command(client, 'load obj 15')
            assert 'banana' in command(client, 'inventory').lower()
            sql("CREATE TRIGGER reject_copyover_save BEFORE UPDATE ON player_data "
                "FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='synthetic copyover save failure'")
            try:
                client.send('copyover' if fresh else 'shutdown hotboot')
                client.expect('Copyover FAILED - server remains live.', timeout=30)
                assert not path.exists() and process.poll() is None
                assert 'banana' in command(client, 'inventory').lower()
                file_log = (runtime / 'logs/log/file').read_text(errors='replace')
                assert 'domain=player_save action=write_failed' in file_log
            finally:
                sql('DROP TRIGGER reject_copyover_save')
            client.send('save'); client.expect(f'Saving {journey.CHARACTER}.')

            active_inode = active.stat().st_ino
            staged.unlink()
            staged.mkdir()
            client.send('copyover' if fresh else 'shutdown hotboot')
            client.expect('Copyover FAILED - server remains live.', timeout=30)
            assert active.stat().st_ino == active_inode and not path.exists() and staged.is_dir()
            staged.rmdir()
            if compressed:
                client.enable_compression()
            staged.write_text('#!/nonexistent-copyover-interpreter\n')
            staged.chmod(0o700)
            if nonroot: os.chown(staged, 10001, 10001)
            with (
                socket.create_connection(('127.0.0.1', port), timeout=10) as idle,
                ssl._create_unverified_context().wrap_socket(
                    socket.create_connection(('127.0.0.1', tls), timeout=10), server_hostname='localhost') as tls_idle,
                socket.create_connection(('127.0.0.1', websocket), timeout=10) as web_idle,
            ):
                frames = upgrade(web_idle, '')
                client.send('copyover' if fresh else 'shutdown hotboot')
                client.expect('Copyover FAILED!', timeout=60)
                for session in (idle, tls_idle):
                    login_roundtrip(session, receive_until(session, b'Copyover FAILED!'))
                buffered = receive_until(web_idle, b'Copyover FAILED!', frames)
                send_frame(web_idle, 9, b'still-connected')
                until = time.monotonic() + 10
                while True:
                    assert time.monotonic() < until, 'WebSocket did not return pong'
                    frame = take_frame(buffered)
                    if frame == (10, b'still-connected'):
                        break
                    if frame is None:
                        data = web_idle.recv(65536)
                        assert data, 'WebSocket closed after failed exec'
                        buffered.extend(data)
            client.send('look'); client.expect('The Regression Arena')
            client.send('save'); client.expect(f'Saving {journey.CHARACTER}.', timeout=30)
            assert process.poll() is None and not path.exists() and not claimed.exists()
            assert active.stat().st_ino == active_inode, 'failed promotion left the broken binary active'
            shutil.copy2(active, staged)
            if nonroot: os.chown(staged, 10001, 10001)
            if compressed:
                client.enable_compression()
            if fresh and not full_world:
                # Static room vnums survive replacement builds that reorder the room table.
                world = runtime / 'areas_mini/mini.wld'
                world.write_text(world.read_text().replace('#22800\n',
                    '#22799\nThe Inserted Room~\nA new room changes runtime indices.\n~\n1 0 0\nS\n#22800\n'))
            print('failed player write and failed exec preserved state, sockets and retryability', flush=True)
            switched_target = 'dummy'
            if not compressed:
                switched_target = 'Sarel'
                other = journey.MudClient(port)
                try:
                    journey.create_character(other, account='Altcopytest', character=switched_target,
                                             email='altcopytest@example.test')
                    command(client, 'load obj 32')
                    command(client, 'give pizza Sarel')
                    assert 'pizza' in command(other, 'inventory').lower()
                    other.send('save')
                    other.expect('Saving Sarel.')
                finally:
                    other.close()
                client.expect('has lost', timeout=15)
            # Mutate live world state, then distinguish fresh copyover from hotboot.
            command(client, 'purge raoul')
            command(client, 'load obj 15')
            command(client, 'drop banana')
            command(client, 'load obj 15')
            before = command(client, 'look').lower()
            assert 'raoul' not in before and 'banana' in before, before
            assert 'banana' in command(client, 'inventory').lower()
            # Account-prompt clients cannot veto either type of restart.
            idle = socket.create_connection(('127.0.0.1', port), timeout=10)
            idle.recv(65536)
            menu = account_menu(port)
            disconnected = [idle, menu.socket]
            expected_events = player_periodic_events(client)
            assert {'event_autosave', 'event_hatred_check'} <= expected_events, expected_events
            if fresh:
                tls_client = ssl._create_unverified_context().wrap_socket(
                    socket.create_connection(('127.0.0.1', tls), timeout=10), server_hostname='localhost')
                web = socket.create_connection(('127.0.0.1', websocket), timeout=10)
                upgrade(web, '')
                disconnected += [tls_client, web]
                fighting = command(client, 'kill executioner').lower()
                assert 'fighting' in fighting, fighting
            # Model a pending reverse-DNS file for a dropped descriptor.
            hosts = runtime / 'lib/etc/hosts'
            hosts.mkdir(exist_ok=True)
            stale_host = hosts / '.65535.127.0.0.1.123.tmp'
            stale_host.write_text('synthetic private hostname\n')
            packet_cursor = len(telnet_packets(client))
            client.send(f'switch {switched_target}')
            client.expect('Ok.', timeout=15)
            if switched_target == 'Sarel':
                # Staff-only commands target the original body when switched.
                # Eat from the controlled PC's saved inventory before the handoff.
                client.send('eat pizza')
                client.expect('You eat')
                assert 'pizza' not in command(client, 'inventory').lower()
            if not fresh and switched_target == 'Sarel':
                process.send_signal(signal.SIGUSR1)
            else:
                client.send('copyover' if fresh else 'shutdown hotboot')
            client.expect('Copyover complete!', timeout=90)
            for session in disconnected:
                received = b''
                session.settimeout(10)
                while True:
                    data = session.recv(65536)
                    if not data: break
                    received += data
                session.close()
                assert b'about 20 seconds' in received, received
            assert not stale_host.exists(), 'dropped descriptor hostname survived exec'
            assert f'Score information for {journey.CHARACTER}' in command(client, 'score')
            recovered_events = player_periodic_events(client)
            assert recovered_events == expected_events, (expected_events, recovered_events)
            if switched_target == 'Sarel':
                other = journey.reconnect_character(port, account='Altcopytest', character='Sarel')
                try:
                    assert 'pizza' not in command(other, 'inventory').lower()
                finally:
                    other.close()
            after = command(client, 'look').lower()
            assert ('raoul' in after) == fresh, after
            assert ('banana' in after) != fresh, after
            assert 'banana' in command(client, 'inventory').lower()
            if fresh:
                assert "aren't fighting anything" in command(client, 'disengage')
            print(f'{fresh=}: real command retained inventory and verified NPC/ground reset policy and disconnect notices', flush=True)
            resumed = wait_telnet(client, 'Duris.Session', packet_cursor, lambda state: state['state'] == 'playing' and state['resumed'])
            assert resumed['context'] == lifecycle['context'] and resumed['generation'] == lifecycle['generation']
            assert resumed['process'] != lifecycle['process']
            wait_telnet(client, 'Duris.Time', packet_cursor,
                        lambda state: state['process'] == resumed['process'])
            print('copyover retained the entry key and changed only the process revision baseline', flush=True)
            client.send('look'); client.expect('The Regression Arena')
            client.send('save'); client.expect(f'Saving {journey.CHARACTER}.', timeout=30)
            assert not path.exists() and not claimed.exists() and process.poll() is None
            assert (runtime / 'server.out').read_text().count('Entering game loop.') == 2
            boot_log = (runtime / 'logs/log/status').read_text(errors='replace')
            assert 'Artifact population evidence: incomplete' in boot_log
            assert 'Item ownership reap skipped: artifact population evidence is incomplete.' in boot_log
            assert 'Artifact population evidence: complete' in boot_log
            assert boot_log.rindex('Artifact population evidence: complete') < boot_log.rindex('Initializing event driver.')
            # The session keeps its account across the exec, so quit returns to its menu.
            client.send('quit'); client.expect('ACCOUNT MENU', timeout=30)
            print(f'{compressed=}, {nonroot=}, {full_world=}: actual exec recovered the original socket, look, acknowledged save and the account menu', flush=True)
            if fresh and not compressed and not nonroot:
                client.close()
                journey.MudClient = Client
                try:
                    client = journey.reconnect_character(port)
                finally:
                    journey.MudClient = original
                # Corrupt only the account binding in the sealed descriptor before boot.
                # The player repository still returns its original authenticated account.
                valid = runtime / 'bin/server/fixture-replacement'
                shutil.copy2(active, valid)
                args = [str(valid), *([] if full_world else ['--minimal']), '-C', str(port)]
                staged.write_text(f"""#!/usr/bin/env python3
import os, pathlib
path = pathlib.Path({str(path)!r})
old = {journey.ACCOUNT.encode()!r}.ljust(64, bytes(1))
new = b"Wrongcopyaccount".ljust(64, bytes(1))
data = path.read_bytes()
assert data.count(old) == 1
path.write_bytes(data.replace(old, new))
os.execv({str(valid)!r}, {args!r})
""")
                staged.chmod(0o700)
                if full_world:
                    wait_artifact_bootstrap(client)
                client.send('copyover')
                client.socket.settimeout(15)
                while client.socket.recv(65536):
                    pass
                deadline = time.monotonic() + 45
                while (runtime / 'server.out').read_text().count('Entering game loop.') != 3:
                    assert process.poll() is None and time.monotonic() < deadline
                    time.sleep(.1)
                boot_log = (runtime / 'logs/log/status').read_text(errors='replace')
                assert f'saved account no longer owns {journey.CHARACTER}' in boot_log
                print('replacement refused a mismatched authenticated account on the inherited socket', flush=True)

        except Exception:
            print((runtime / 'server.out').read_text(errors='replace')[-7000:])
            print(journey.runtime_logs(runtime))
            if client: print(client.transcript.decode(errors='replace')[-6000:])
            raise
        finally:
            stop()
            if redis_server:
                redis_server.terminate()
                redis_server.wait(timeout=10)


if __name__ == '__main__':
    binary = Path(sys.argv[1]).resolve()
    if not os.environ.get('TEST_DB_HOST'):
        wrapper = journey.ROOT / 'tests/async/with_disposable_mariadb.sh'
        os.execv(wrapper, [str(wrapper), sys.executable, str(Path(__file__).resolve()), *sys.argv[1:]])
    if '--redis-failures' in sys.argv:
        run(binary, False, redis_failures=True)
    else:
        for compressed in (False, True):
            run(binary, compressed, '--nonroot' in sys.argv,
                '--fresh' in sys.argv, '--full-world' in sys.argv)
