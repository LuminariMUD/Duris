#!/usr/bin/env python3
"""Real flatfile copyover failure/success on the original Telnet/MCCP socket.

Run with a flatfile server path. Pass --full-world to boot the generated world
with a disposable arena fixture. All state is disposable.
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
from test_connection_limit_journey import upgrade


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


def run(binary, compressed, nonroot=False, fresh=False, full_world=False):
    with tempfile.TemporaryDirectory(prefix='duris-copyover-journey-') as temporary:
        root = Path(temporary)
        state, runtime = root / 'state', root / 'runtime'
        state.mkdir(mode=0o700); (state / 'domains').mkdir(mode=0o700)
        runtime.mkdir(); (runtime / 'logs/log').mkdir(parents=True)
        journey.make_fixture(runtime); journey.generate_certificate(runtime)
        if full_world:
            add_full_world_arena(runtime)
        (runtime / 'logs/log/.gitignore').write_text('*\n')
        (runtime / 'journals' / 'critical').mkdir(parents=True, mode=0o700)
        (runtime / 'bin/server').mkdir(parents=True)
        shutil.copy2(binary, runtime / 'bin/server/dms')
        shutil.copy2(binary, runtime / 'bin/server/dms_new')
        path = root / 'copyover-state/copyover.dat'
        port, tls, websocket = journey.available_ports()
        env = dict(PATH=os.environ.get('PATH', '/usr/bin:/bin'), ENVIRONMENT='local',
                   PERSISTENCE_MODE='flatfile-primary', FLATFILE_STATE_DIR=str(state),
                   CRITICAL_COMMAND_JOURNAL_DIR=str(runtime / 'journals/critical'),
                   COPYOVER_STATE_FILE=str(path), LISTEN_ADDRESS='127.0.0.1',
                   DURIS_TLS_PORT=str(tls), DURIS_WEBSOCKET_LISTEN_ADDRESS='127.0.0.1',
                   DURIS_WEBSOCKET_PORT=str(websocket), DURIS_WEBSOCKET='TRUE', REDIS='FALSE', CHAOS_MUD='FALSE')
        subprocess.run([str(journey.INSPECTOR), str(state), 'seed-combat'], check=True)
        process = output = client = None
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

        try:
            boot(); client = Client(port); journey.create_character(client)
            client.send('save'); client.expect(f'Save complete for {journey.CHARACTER}.')
            client.send('quit'); client.expect('ACCOUNT MENU', timeout=30)
            stop()
            journey.make_overlord(state, journey.CHARACTER)
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
            if compressed: client.enable_compression()
            process.send_signal(signal.SIGUSR1)
            client.expect('Copyover FAILED', timeout=60)
            assert not path.exists() and process.poll() is None
            client.send('look'); client.expect('The Regression Arena')
            client.send('save'); client.expect(f'Save complete for {journey.CHARACTER}.', timeout=30)
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
                client.send('save'); client.expect(f'Save complete for {journey.CHARACTER}.', timeout=30)
                pending.unlink()  # explicit disposition of this test's synthetic image
            with socket.create_connection(('127.0.0.1', port), timeout=10) as idle:
                idle.settimeout(10)
                idle.recv(65536)
                process.send_signal(signal.SIGUSR1)
                client.expect('Copyover cancelled: a connection cannot survive this handoff', timeout=30)
                assert process.poll() is None and not path.exists()
                client.send('look'); client.expect('The Regression Arena')
                idle.sendall(b'\n')
                assert idle.recv(65536), 'copyover closed a non-preservable connection'
            if fresh:
                # A failed exec must leave the Telnet player and save workers usable,
                # while completing cleanup of the deliberately disconnected login.
                staged = runtime / 'bin/server/dms_new'
                staged.write_text('#!/nonexistent-copyover-interpreter\n')
                staged.chmod(0o700)
                with (
                    socket.create_connection(('127.0.0.1', port), timeout=10) as idle,
                    ssl._create_unverified_context().wrap_socket(
                        socket.create_connection(('127.0.0.1', tls), timeout=10), server_hostname='localhost') as tls_idle,
                    socket.create_connection(('127.0.0.1', websocket), timeout=10) as web_idle,
                ):
                    upgrade(web_idle, '')
                    client.send('copyover')
                    client.expect('Copyover FAILED!', timeout=60)
                    for session in (idle, tls_idle, web_idle):
                        session.settimeout(10)
                        received = b''
                        while True:
                            data = session.recv(65536)
                            if not data: break
                            received += data
                        assert b'about 20 seconds' in received, received
                client.send('look'); client.expect('The Regression Arena')
                client.send('save'); client.expect(f'Save complete for {journey.CHARACTER}.', timeout=30)
                assert process.poll() is None and path.exists()
                path.unlink()  # discard this fixture's known unexecuted handoff
                shutil.copy2(binary, runtime / 'bin/server/dms_new')
                if not full_world:
                    # Fresh handoffs use room vnums even if the replacement adds a room.
                    world = runtime / 'areas_mini/mini.wld'
                    world.write_text(world.read_text().replace('#22800\n',
                        '#22799\nThe Inserted Room~\nA new room changes runtime indices.\n~\n1 0 0\nS\n#22800\n'))
                print('failed player-only exec retained Telnet/save service and cleaned disconnected sessions', flush=True)
            # Mutate live world state, then distinguish fresh copyover from hotboot.
            command(client, 'purge raoul')
            command(client, 'load obj 15')
            command(client, 'drop banana')
            command(client, 'load obj 15')
            before = command(client, 'look').lower()
            assert 'raoul' not in before and 'banana' in before, before
            assert 'banana' in command(client, 'inventory').lower()
            disconnected = []
            if fresh:
                # Real login-screen Telnet, TLS and upgraded WebSocket sessions.
                idle = socket.create_connection(('127.0.0.1', port), timeout=10)
                tls_client = ssl._create_unverified_context().wrap_socket(
                    socket.create_connection(('127.0.0.1', tls), timeout=10), server_hostname='localhost')
                web = socket.create_connection(('127.0.0.1', websocket), timeout=10)
                upgrade(web, '')
                disconnected = [idle, tls_client, web]
                fighting = command(client, 'kill executioner').lower()
                assert 'fighting' in fighting, fighting
            packet_cursor = len(telnet_packets(client))
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
                assert b'copying over' in received and b'about 20 seconds' in received, received
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
            clock = wait_telnet(client, 'Duris.Time', packet_cursor)
            assert clock['process'] == resumed['process']
            print('copyover retained the entry key and changed only the process revision baseline', flush=True)
            client.send('look'); client.expect('The Regression Arena')
            client.send('save'); client.expect(f'Save complete for {journey.CHARACTER}.', timeout=30)
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
        except Exception:
            print((runtime / 'server.out').read_text(errors='replace')[-7000:])
            print(journey.runtime_logs(runtime))
            if client: print(client.transcript.decode(errors='replace')[-6000:])
            raise
        finally: stop()


if __name__ == '__main__':
    for compressed in (False, True):
        run(Path(sys.argv[1]).resolve(), compressed, '--nonroot' in sys.argv,
            '--fresh' in sys.argv, '--full-world' in sys.argv)
