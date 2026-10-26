#!/usr/bin/env python3
"""Retired SQL telemetry stays disabled; its retained schema still gates boot.

Use only the disposable TEST_DB_* authority. Ordinary gameplay remains available
with the old SQL backend setting, without SQL telemetry writes or an outage
producer. The runtime schema contract still rejects drift. The active PostHog
backend has its own gameplay, copyover and restart journey.
"""
from pathlib import Path
import argparse
import re
import shutil
import subprocess
import tempfile
import time

import test_flatfile_combat_journey as journey
from test_flight_network_journey import authority

ROOT = journey.ROOT


def run(server):
    with tempfile.TemporaryDirectory(prefix='telemetry-schema-boot-', dir=ROOT / 'bin/tests') as temporary:
        runtime = Path(temporary)
        journey.make_fixture(runtime)
        journey.generate_certificate(runtime)
        for name in ('logs/log', 'journals/critical', 'bin/server', 'copyover-state', 'telemetry-outages'):
            (runtime / name).mkdir(parents=True, mode=0o700)
        shutil.copy2(server, runtime / 'bin/server/dms')
        output_path = runtime / 'server.out'
        status_path = runtime / 'logs/log/status'
        with authority('mariadb', runtime) as (env, sql):
            env.update(TELEMETRY_ENABLED='true', TELEMETRY_BACKEND='sql',
                       TELEMETRY_DB_USER=env['DB_USER'], TELEMETRY_DB_PASSWD=env['DB_PASSWD'],
                       TELEMETRY_OUTAGE_LEDGER_DIR=str(runtime / 'telemetry-outages'),
                       CRITICAL_COMMAND_JOURNAL_DIR=str(runtime / 'journals/critical'),
                       COPYOVER_STATE_FILE=str(runtime / 'copyover-state/copyover.dat'))
            plain, tls, websocket = journey.available_ports()
            env.update(DURIS_TLS_PORT=str(tls), DURIS_WEBSOCKET_PORT=str(websocket))

            def boot(label, refused=False):
                output_offset = output_path.stat().st_size if output_path.exists() else 0
                status_offset = status_path.stat().st_size if status_path.exists() else 0
                with output_path.open('a') as output:
                    process = subprocess.Popen(
                        [str(runtime / 'bin/server/dms'), '--minimal', '-s', '-d', str(runtime), str(plain)],
                        cwd=runtime, env=env, stdout=output, stderr=subprocess.STDOUT)
                try:
                    deadline = time.monotonic() + 120
                    while b'Entering game loop.' not in output_path.read_bytes()[output_offset:]:
                        if refused and process.poll() is not None:
                            assert process.returncode != 0
                            assert 'COMPAT-E003' in status_path.read_text()[status_offset:]
                            print(label + ': runtime schema drift refused boot', flush=True)
                            return
                        assert process.poll() is None and time.monotonic() < deadline, label + ': boot failed'
                        time.sleep(.1)
                    assert not refused, label + ': invalid schema booted'

                    def disabled(offset):
                        deadline = time.monotonic() + 30
                        while time.monotonic() < deadline:
                            text = status_path.read_text(errors='replace')[offset:]
                            found = re.search(r'telemetry_health event=state .*?state=(\S+) .*?producer=(\d+:\d+)', text)
                            if found:
                                assert found[1] == 'disabled', text
                                return
                            assert process.poll() is None, label + ': server exited'
                            time.sleep(.1)
                        raise AssertionError(label + ': no telemetry health record')

                    disabled(status_offset)
                    process.terminate()
                    assert process.wait(timeout=30) == 0
                    assert sql('SELECT COUNT(*) FROM telemetry_interval') == '0'
                    assert not list((runtime / 'telemetry-outages').iterdir())
                    print(label + ': retired SQL setting disabled; gameplay boot and retained schema intact', flush=True)
                except Exception as error:
                    raise AssertionError(str(error) + '\n' + journey.runtime_logs(runtime)) from error
                finally:
                    if process.poll() is None:
                        process.terminate()
                        try:
                            process.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            process.kill(); process.wait(timeout=10)

            boot('whole chain')
            sql('ALTER TABLE telemetry_interval CHANGE progression_requested_xp progression_requested_xp_drift BIGINT NULL')
            boot('renamed progression column', refused=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server', type=Path, default=ROOT / 'bin/server/dms_new')
    args = parser.parse_args()
    (ROOT / 'bin/tests').mkdir(parents=True, exist_ok=True)
    run(args.server.resolve())
