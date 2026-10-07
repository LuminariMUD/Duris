#!/usr/bin/env python3
"""A server boots with SQL telemetry against a database that is wrong in one way.

Set TEST_DB_HOST (loopback), TEST_DB_USER and TEST_DB_PASSWORD for a disposable
server; tests/async/with_disposable_mariadb.sh exports them. --server boots
--minimal with telemetry enabled against the whole migration chain (healthy),
against the chain with one progression column renamed (the boot gate refuses
the schema with COMPAT-E003 before telemetry runs), and as a writer that may
only SELECT (the game enters its loop with nobody logged in and the one
telemetry_health line names the permission). --misnamed-server, a build whose
telemetry_columns.inc names a column the migrations do not create, boots
against the whole chain: the game runs and the line names the missing column,
which is the production incident of work item #17. Only a newly created
synthetic schema is touched.
"""
from pathlib import Path
import argparse
import os
import re
import subprocess
import tempfile
import time
import uuid

import test_flatfile_combat_journey as journey

ROOT = Path(__file__).resolve().parents[2]
# The reviewed catalog of run_telemetry_player_journey.py for the fixture's
# lib/duris.properties and the property registry of this tree.
CATALOG = '6f49b7e9b16055b6c7d48d83f4a9de789d89adeddabbb4bfc1f6d2c86f6b8792 265 265 1\n'
TABLES = ('telemetry_interval', 'telemetry_config', 'telemetry_session', 'telemetry_quarantine')
HEALTH = re.compile(r'telemetry_health event=(\S+) .*?state=(\S+) .*?failure_class=(\S+) error=(\d+) '
                    r'schema_check=(\S+) ')


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
            catalog = runtime/'reviewed-properties.catalog'
            catalog.touch(mode=0o600)
            catalog.write_text(CATALOG)
            plain, tls, websocket = journey.available_ports()
            environment.update(CRITICAL_COMMAND_JOURNAL_DIR=str(runtime/'journals/critical'),
                               TELEMETRY_PROPERTY_CATALOG_FILE=str(catalog),
                               DURIS_TLS_PORT=str(tls), DURIS_WEBSOCKET_PORT=str(websocket))
            output_path = runtime/'server.out'
            status_path = runtime/'logs/log/status'

            def boot(label, expected, alter=None, revert=None, env_extra=None, binary=server):
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
                    deadline = time.monotonic()+30
                    found = None
                    while found is None:
                        assert process.poll() is None and time.monotonic() < deadline, label+': no telemetry_health line'
                        if status_path.exists():
                            for line in status_path.read_text(errors='replace')[status_offset:].splitlines():
                                found = HEALTH.search(line)
                                if found:
                                    break
                        time.sleep(.1)
                    event, state, failure_class, error, check = found.groups()
                    observed = (state, failure_class, int(error), check)
                    assert observed == expected, f'{label}: {observed} != {expected}\n{found.group(0)}'
                    # The game stays up with telemetry refused.
                    time.sleep(1)
                    assert process.poll() is None, label+': the server exited after the health line'
                    process.send_signal(__import__('signal').SIGTERM)
                    process.wait(timeout=30)
                    assert process.returncode == 0, label+': shutdown returned '+str(process.returncode)
                    print(f'{label}: state={state} failure_class={failure_class} error={error} schema_check={check}', flush=True)
                except Exception as error:
                    raise AssertionError(str(error)+'\n'+output_path.read_text(errors='replace')[offset:][-6000:]+'\n'+journey.runtime_logs(runtime)) from error
                finally:
                    if process and process.poll() is None:
                        process.terminate()
                        try: process.wait(timeout=10)
                        except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=10)
                    if revert:
                        sql(revert)

            boot('whole chain', ('healthy', 'none', 0, 'none'))
            boot('renamed progression column', None,
                 'ALTER TABLE telemetry_interval CHANGE COLUMN progression_requested_xp progression_requested_xp_hidden BIGINT NULL',
                 'ALTER TABLE telemetry_interval CHANGE COLUMN progression_requested_xp_hidden progression_requested_xp BIGINT NULL')
            boot('writer that may only SELECT', ('circuit-open', 'permanent-permission', 1142, 'none'),
                 env_extra={'TELEMETRY_DB_USER': writer, 'TELEMETRY_DB_PASSWD': writer_password})
            if misnamed_server:
                boot('writer naming a column the chain lacks', ('circuit-open', 'permanent-schema', 1054, 'column'),
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
