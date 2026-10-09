#!/usr/bin/env python3
"""A service stop is recorded in server_reboots, on MariaDB.

systemd stopped the launcher with its whole control group, so the launcher died with the
server and never wrote the row: one restart in ten was recorded. The unit now sends
SIGTERM to the launcher alone (KillMode=mixed), and the launcher passes it to the server,
waits for it to shut down, records the stop and exits without starting it again. The
issuer and reason go into the row as data: a reason with an apostrophe ended the SQL
string and lost the row without a word.

Here the server is a stand-in that writes logs/shutdown_info.txt and exits when it gets
SIGTERM, as the real one does. A stop, then a start and a second stop (a restart), each
leave one row. Run through with_disposable_mariadb.sh.
"""
from pathlib import Path
import os
import shutil
import signal
import subprocess
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
REASON = "it's a test of the launcher's stop"

STAND_IN = r'''#!/bin/bash
trap 'printf "%s\n" "Zusuk|$REASON" > logs/shutdown_info.txt; echo stopped >> stand-in.stops; exit 0' TERM
echo $$ > stand-in.pid
while :; do sleep 0.1; done
'''


def wait_for(predicate, what, timeout=30):
    deadline = time.monotonic() + timeout
    while not predicate():
        assert time.monotonic() < deadline, what
        time.sleep(.1)


def run():
    host = os.environ['TEST_DB_HOST']
    assert host == '127.0.0.1', 'use a disposable loopback database'
    database = 'launcher_stop_' + uuid.uuid4().hex[:12]
    environment = {
        'PATH': os.environ.get('PATH', '/usr/bin:/bin'),
        'ENVIRONMENT': 'local', 'PERSISTENCE_MODE': 'mariadb-primary',
        'DB_HOST': host, 'DB_PORT': os.environ['TEST_DB_PORT'], 'DB_NAME': database,
        'DB_USER': os.environ['TEST_DB_USER'], 'DB_PASSWD': os.environ['TEST_DB_PASSWORD'],
        'DB_ALLOWED_TARGETS': host + '/' + database, 'DURIS_DEV_PORT': '14999',
        'MYSQL_PWD': os.environ['TEST_DB_PASSWORD'], 'REASON': REASON,
    }
    mysql = ['mysql', '--protocol=tcp', '-h', host, '-P', environment['DB_PORT'],
             '-u', environment['DB_USER'], '-N', '-B']

    def sql(statement, selected=True):
        return subprocess.check_output(mysql + ([database] if selected else []),
                                       input=statement, text=True, env=environment).strip()

    migration = (ROOT / 'migrations/immutable/0004_server_reboots.sql').read_text()
    create = migration[migration.index('CREATE TABLE IF NOT EXISTS server_reboots'):]
    sql('CREATE DATABASE ' + database, False)
    try:
        sql(create[:create.index(';') + 1])
        with tempfile.TemporaryDirectory(prefix='duris-launcher-stop-') as temporary:
            project = Path(temporary)
            (project / 'scripts').mkdir()
            shutil.copy2(ROOT / 'scripts/cycle_mud.sh', project / 'scripts/cycle_mud.sh')
            # The schema checks are other tests' work; the stand-ins pass.
            (project / 'scripts/migration_runner.py').write_text('raise SystemExit(0)\n')
            (project / 'migrations').mkdir()
            verifier = project / 'migrations/verify_runtime_compatibility.sh'
            verifier.write_text('#!/bin/sh\nexit 0\n')
            verifier.chmod(0o755)
            (project / 'areas_mini').mkdir()
            for name in ('mini.mob', 'mini.obj', 'mini.qst', 'mini.wld', 'mini.zon',
                         'world.shp', 'world.tab', 'world.weather'):
                (project / 'areas_mini' / name).write_text('test\n')
            for directory in ('bin/server', 'lib/misc', 'logs'):
                (project / directory).mkdir(parents=True)
            server = project / 'bin/server/dms'
            server.write_text(STAND_IN)
            server.chmod(0o755)

            def stop_once():
                (project / 'stand-in.pid').unlink(missing_ok=True)
                output = (project / 'launcher.out').open('a')
                launcher = subprocess.Popen(
                    ['bash', 'scripts/cycle_mud.sh', '--minimal'], cwd=project,
                    env=environment, stdout=output, stderr=subprocess.STDOUT,
                    start_new_session=True)
                try:
                    wait_for(lambda: (project / 'stand-in.pid').exists(),
                             'the launcher did not start the server')
                    # What KillMode=mixed does: SIGTERM to the launcher alone.
                    started = time.monotonic()
                    launcher.send_signal(signal.SIGTERM)
                    launcher.wait(timeout=30)
                    assert launcher.returncode == 0, launcher.returncode
                    # No relaunch, so none of the 10 s pause between runs either.
                    assert time.monotonic() - started < 8, 'the launcher paused after a stop'
                finally:
                    if launcher.poll() is None:
                        os.killpg(launcher.pid, signal.SIGKILL)
                    output.close()

            stop_once()
            log = (project / 'launcher.out').read_text()
            assert (project / 'stand-in.stops').read_text() == 'stopped\n', log
            assert 'Mud stopped, reason: shutdown [0]' in log and 'Logged reboot' in log, log
            assert sql('SELECT shutdown_type, initiated_by, reason FROM server_reboots') == \
                f'shutdown\tZusuk\t{REASON}', log
            print('[PASS] a stop reaches the server and is recorded with its reason',
                  flush=True)
            stop_once()
            assert (project / 'stand-in.stops').read_text() == 'stopped\nstopped\n'
            assert sql('SELECT COUNT(*) FROM server_reboots') == '2'
            print('[PASS] a restart records its stop too', flush=True)
    finally:
        sql('DROP DATABASE ' + database, False)


if __name__ == '__main__':
    run()
