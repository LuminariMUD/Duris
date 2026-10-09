#!/usr/bin/env python3
"""A server boots with SQL telemetry; its schema check and its outage record are read.

Set TEST_DB_HOST (loopback), TEST_DB_USER and TEST_DB_PASSWORD for a disposable
server; tests/async/with_disposable_mariadb.sh exports them. --server boots
--minimal with telemetry enabled against the whole migration chain and is
stopped, copied over (SIGUSR1) and killed; after each the outage ledger in
TELEMETRY_OUTAGE_LEDGER_DIR, read with scripts/telemetry/outage.py, shows the
producer as clean_drained, as a copied-over producer and a new one, and as a
running watermark that the next producer turns into unknown_tail. It then boots
against the chain with one progression column renamed (the boot gate refuses
the schema with COMPAT-E003 before telemetry runs) and as a writer that may
only SELECT (the game enters its loop with nobody logged in and the one
telemetry_health line names the permission), with no outage ledger directory
and with one readable by others (the line names the storage check). --misnamed-server, a build whose
telemetry_columns.inc names a column the migrations do not create, boots
against the whole chain: the game runs and the line names the missing column,
which is the production incident of work item #17. Only a newly created
synthetic schema is touched.
"""
from pathlib import Path
import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid

import test_flatfile_combat_journey as journey

ROOT = Path(__file__).resolve().parents[2]
# The reviewed catalog of run_telemetry_player_journey.py for the fixture's
# lib/duris.properties and the property registry of this tree.
CATALOG = '6f49b7e9b16055b6c7d48d83f4a9de789d89adeddabbb4bfc1f6d2c86f6b8792 265 265 1\n'
TABLES = ('telemetry_interval', 'telemetry_config', 'telemetry_session', 'telemetry_quarantine')
HEALTH = re.compile(r'telemetry_health event=(\S+) .*?state=(\S+) .*?producer=(\d+:\d+) .*?'
                    r'failure_class=(\S+) error=(\d+) schema_check=(\S+) storage_check=(\S+) ')


def run(server, misnamed_server):
    database = 'telemetry_schema_boot_' + uuid.uuid4().hex[:12]
    host = os.environ['TEST_DB_HOST']
    assert host in ('127.0.0.1', 'localhost'), 'use a disposable loopback database'
    writer = 'telemetry_boot_' + uuid.uuid4().hex[:8]
    writer_password = 'select-only-' + uuid.uuid4().hex[:8]
    environment = {
        'PATH': os.environ.get('PATH', '/usr/bin:/bin'),
        'ENVIRONMENT': 'local', 'DB_HOST': host, 'DB_PORT': os.environ.get('TEST_DB_PORT', '3306'),
        'DB_NAME': database, 'DB_USER': os.environ['TEST_DB_USER'],
        'DB_PASSWD': os.environ['TEST_DB_PASSWORD'],
        'DB_ALLOWED_TARGETS': host+'/'+database,
        'MYSQL_PWD': os.environ['TEST_DB_PASSWORD'],
        'PERSISTENCE_MODE': 'mariadb-primary', 'DB_TLS': 'FALSE',
        'REDIS': 'FALSE', 'CHAOS_MUD': 'FALSE',
        'LISTEN_ADDRESS': '127.0.0.1', 'DURIS_WEBSOCKET_LISTEN_ADDRESS': '127.0.0.1',
        'TELEMETRY_ENABLED': 'true', 'TELEMETRY_BACKEND': 'sql',
        'TELEMETRY_DB_USER': os.environ['TEST_DB_USER'],
        'TELEMETRY_DB_PASSWD': os.environ['TEST_DB_PASSWORD'],
        'TELEMETRY_INTERVAL_USEC': '1000000', 'TELEMETRY_CHECKPOINT_INTERVAL_USEC': '1000000',
        'TELEMETRY_ACTIVE_WINDOW_USEC': '3000000', 'TELEMETRY_CONTEXT_SEGMENTS_PER_MINUTE': '64',
    }
    if 'LD_LIBRARY_PATH' in os.environ:
        environment['LD_LIBRARY_PATH'] = os.environ['LD_LIBRARY_PATH']
    mysql = ['mysql', '--protocol=tcp', '-h', host, '-P', environment['DB_PORT'], '-u',
             environment['DB_USER'], '-N', '-B']

    def sql(text, selected=True):
        return subprocess.check_output(mysql+([database] if selected else []), input=text,
                                       text=True, env=environment).strip()

    sql('CREATE DATABASE '+database+' CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci', False)
    try:
        sql((ROOT/'migrations/bootstrap_multithread_safe.sql').read_text())
        subprocess.run(['python3', 'scripts/migration_runner.py', 'adopt', '--kind', 'fresh_bootstrap'],
                       cwd=ROOT, env=environment, check=True)
        subprocess.run(['python3', 'scripts/migration_runner.py', 'run'], cwd=ROOT, env=environment, check=True)
        sql(f"CREATE USER '{writer}'@'%' IDENTIFIED BY '{writer_password}'", False)
        for table in TABLES:
            sql(f"GRANT SELECT ON {database}.{table} TO '{writer}'@'%'", False)
        with tempfile.TemporaryDirectory(prefix='telemetry-schema-boot-', dir=ROOT/'bin/tests') as temporary:
            runtime = Path(temporary)
            journey.make_fixture(runtime)
            journey.generate_certificate(runtime)
            (runtime/'logs/log').mkdir(parents=True)
            (runtime/'journals'/'critical').mkdir(parents=True, mode=0o700)
            ledger = runtime/'telemetry-outages'
            ledger.mkdir(mode=0o700)
            # A copyover execs bin/server/dms below the directory the server runs in.
            (runtime/'bin/server').mkdir(parents=True)
            shutil.copy2(server, runtime/'bin/server/dms')
            (runtime/'copyover-state').mkdir()
            catalog = runtime/'reviewed-properties.catalog'
            catalog.touch(mode=0o600)
            catalog.write_text(CATALOG)
            plain, tls, websocket = journey.available_ports()
            environment.update(CRITICAL_COMMAND_JOURNAL_DIR=str(runtime/'journals/critical'),
                               TELEMETRY_PROPERTY_CATALOG_FILE=str(catalog),
                               TELEMETRY_OUTAGE_LEDGER_DIR=str(ledger),
                               COPYOVER_STATE_FILE=str(runtime/'copyover-state/copyover.dat'),
                               DURIS_TLS_PORT=str(tls), DURIS_WEBSOCKET_PORT=str(websocket))
            output_path = runtime/'server.out'
            status_path = runtime/'logs/log/status'

            def evidence(pending_allowed=False):
                read = subprocess.run([sys.executable, 'scripts/telemetry/outage.py', str(ledger)],
                                      cwd=ROOT, text=True, stdout=subprocess.PIPE)
                packet = json.loads(read.stdout)
                # A kill during a publication leaves outages.pending, which the reader leaves
                # to the next producer's recovery.
                if pending_allowed and packet.get('reason') == 'pending_publication':
                    return None
                assert read.returncode == 0, packet
                return [(row['phase'], row['unknown_after_last_sample']) for row in packet['observations']]

            def health_line(label, status_offset, process, deadline=30):
                deadline = time.monotonic()+deadline
                while True:
                    assert process.poll() is None and time.monotonic() < deadline, label+': no telemetry_health line'
                    if status_path.exists():
                        for line in status_path.read_text(errors='replace')[status_offset:].splitlines():
                            # The first observation can precede the worker's qualification.
                            if (found := HEALTH.search(line)) and found.group(2) != 'starting':
                                return found
                    time.sleep(.1)

            def committed(label, status_offset, process):
                # The newest health line's records wait up to 2 s in a batch, and a stop
                # flushes what is left within its own 2 s: a host stall then leaves the
                # ledger "abandoned". Stop once they are in SQL, with nothing left to flush.
                text = status_path.read_text(errors='replace')[status_offset:]
                newest = [line for line in HEALTH.finditer(text) if line.group(2) != 'starting'][-1]
                boot_id, process_id = newest.group(3).split(':')
                admitted = int(re.search(r'last_admitted_seq=(\d+)', newest.group(0)).group(1))
                deadline = time.monotonic()+30
                while int(sql(f'SELECT COALESCE(MAX(record_seq), 0) FROM telemetry_interval '
                              f'WHERE boot_id={boot_id} AND process_id={process_id}')) < admitted:
                    assert process.poll() is None and time.monotonic() < deadline, label+': the admitted records never reached SQL'
                    time.sleep(.2)

            def boot(label, expected, alter=None, revert=None, env_extra=None, binary=server, stop='term'):
                if alter:
                    sql(alter)
                process = None
                offset = output_path.stat().st_size if output_path.exists() else 0
                status_offset = status_path.stat().st_size if status_path.exists() else 0
                env = dict(environment, **(env_extra or {}))
                try:
                    with output_path.open('a') as output:
                        process = subprocess.Popen([str(binary), '--minimal', '-s', '-d', str(runtime), str(plain)],
                                                   cwd=runtime, env=env, stdout=output, stderr=subprocess.STDOUT)
                    deadline = time.monotonic()+120
                    while b'Entering game loop.' not in output_path.read_bytes()[offset:]:
                        if expected is None and process.poll() is not None:
                            # The boot gate refused the schema before telemetry ran; it
                            # says so in the status log, which the launcher's exit may precede.
                            settle = time.monotonic()+10
                            def refused():
                                return status_path.exists() and 'COMPAT-E003' in status_path.read_text(errors='replace')[status_offset:]
                            while not refused() and time.monotonic() < settle:
                                time.sleep(.1)
                            assert process.returncode != 0 and refused(), f'{label}: expected the boot gate to refuse the schema, exit {process.returncode}'
                            print(f'{label}: the boot gate refused the schema (COMPAT-E003), the server did not start', flush=True)
                            return
                        assert process.poll() is None and time.monotonic() < deadline, label+': the server did not enter its loop'
                        time.sleep(.1)
                    assert expected is not None, label+': the server booted on a schema the boot gate should refuse'
                    found = health_line(label, status_offset, process)
                    event, state, producer, failure_class, error, check, storage = found.groups()
                    observed = (state, failure_class, int(error), check, storage)
                    assert observed == expected, f'{label}: {observed} != {expected}\n{found.group(0)}'
                    # The game stays up, with telemetry refused or running.
                    time.sleep(1.5)
                    assert process.poll() is None, label+': the server exited after the health line'
                    if stop == 'copyover':
                        copied_at = status_path.stat().st_size
                        process.send_signal(signal.SIGUSR1)
                        # The old image can log a health line (a stall alert) until it execs.
                        marker = 'copyover: executing new binary'
                        deadline = time.monotonic()+90
                        while marker not in status_path.read_text(errors='replace')[copied_at:]:
                            assert process.poll() is None and time.monotonic() < deadline, label+': the copyover did not exec'
                            time.sleep(.1)
                        again = health_line(label, status_path.read_text(errors='replace').index(marker, copied_at), process, 90)
                        assert again.group(3) != producer, label+': the copied-over image kept the producer'
                        time.sleep(1.5)
                        stop = 'term'
                    if stop == 'kill':
                        process.kill()
                        process.wait(timeout=30)
                    else:
                        if state == 'healthy':
                            committed(label, status_offset, process)
                        process.send_signal(signal.SIGTERM)
                        process.wait(timeout=30)
                        assert process.returncode == 0, label+': shutdown returned '+str(process.returncode)
                    print(f'{label}: state={state} failure_class={failure_class} error={error} schema_check={check} storage_check={storage}, {stop}', flush=True)
                except Exception as error:
                    raise AssertionError(str(error)+'\n'+output_path.read_text(errors='replace')[offset:][-6000:]+'\n'+journey.runtime_logs(runtime)) from error
                finally:
                    if process and process.poll() is None:
                        process.terminate()
                        try: process.wait(timeout=10)
                        except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=10)
                    if revert:
                        sql(revert)

            boot('whole chain', ('healthy', 'none', 0, 'none', 'none'))
            assert evidence() == [('clean_drained', False)], evidence()
            boot('whole chain, copied over', ('healthy', 'none', 0, 'none', 'none'), stop='copyover')
            # The copyover flushes durably but writes no terminal sample before the exec,
            # so the copied-over producer is an unknown tail; the new image drains cleanly.
            assert evidence() == [('clean_drained', False), ('unknown_tail', True), ('clean_drained', False)], evidence()
            boot('whole chain, killed', ('healthy', 'none', 0, 'none', 'none'), stop='kill')
            killed = evidence(pending_allowed=True)
            assert killed is None or killed[3] == ('running', True), killed
            print(f'outage ledger after stop, copyover and kill: {killed or "publication pending"}', flush=True)
            boot('renamed progression column', None,
                 'ALTER TABLE telemetry_interval CHANGE COLUMN progression_requested_xp progression_requested_xp_hidden BIGINT NULL',
                 'ALTER TABLE telemetry_interval CHANGE COLUMN progression_requested_xp_hidden progression_requested_xp BIGINT NULL')
            boot('writer that may only SELECT', ('circuit-open', 'permanent-permission', 1142, 'none', 'none'),
                 env_extra={'TELEMETRY_DB_USER': writer, 'TELEMETRY_DB_PASSWD': writer_password})
            # The next producer's registration turned the killed one's watermark into a gap.
            assert evidence()[3] == ('unknown_tail', True), evidence()
            # A ledger the worker cannot use is refused before SQL, and the line says what.
            boot('no outage ledger directory', ('circuit-open', 'permanent-repository', 22, 'none', 'directory'),
                 env_extra={'TELEMETRY_OUTAGE_LEDGER_DIR': ''})
            ledger.chmod(0o755)
            try:
                boot('outage ledger directory readable by others',
                     ('circuit-open', 'permanent-repository', 1, 'none', 'protection'))
            finally:
                ledger.chmod(0o700)
            # Neither refused boot registered a producer; the SELECT-only writer did.
            assert len(evidence()) == 5, evidence()
            if misnamed_server:
                boot('writer naming a column the chain lacks', ('circuit-open', 'permanent-schema', 1054, 'column', 'none'),
                     binary=misnamed_server)
            assert sql('SELECT COUNT(*) FROM telemetry_interval WHERE record_kind<>5') == '0', 'a refused writer admitted records'
            print('telemetry schema boot: each refusal named its cause with nobody logged in, and the game ran whenever the boot gate let it', flush=True)
    finally:
        sql(f"DROP USER IF EXISTS '{writer}'@'%'", False)
        sql('DROP DATABASE '+database, False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--server', type=Path, required=True)
    parser.add_argument('--misnamed-server', type=Path,
                        help='a build whose telemetry_columns.inc names a column the migrations do not create')
    args = parser.parse_args()
    run(args.server.resolve(), args.misnamed_server.resolve() if args.misnamed_server else None)
