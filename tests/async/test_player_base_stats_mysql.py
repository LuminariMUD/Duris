#!/usr/bin/env python3
"""Exercise stat migration and real saves in a disposable socket-only MariaDB.

Requires native mariadbd, mariadb-install-db, mysql, mysql_config and g++.
Use --mysql-basedir for an unpacked MySQL 8 distribution instead of MariaDB.
Never reads .env or connects to an existing database.
"""
from pathlib import Path
import os
import shlex
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / 'migrations/immutable/0042_player_base_stats.sql'
STATS = ('str', 'dex', 'agi', 'con', 'pow', 'int', 'wis', 'cha', 'kar', 'luk')


def login_journey(socket, work, server):
    """Use the real account menu, command parser, writer and materialization path."""
    import signal
    import test_flatfile_combat_journey as journey
    database = 'stats_login'
    environment = {
        'PATH': os.environ.get('PATH', '/usr/bin:/bin'), 'ENVIRONMENT': 'local',
        'DB_HOST': 'localhost', 'DB_SOCKET': socket, 'DB_NAME': database,
        'DB_USER': 'root', 'DB_PASSWD': 'stats-test', 'MYSQL_PWD': 'stats-test',
        'DB_ALLOWED_TARGETS': 'localhost/' + database,
        'PERSISTENCE_MODE': 'mariadb-primary', 'DB_TLS': 'FALSE', 'REDIS': 'FALSE',
        'CHAOS_MUD': 'FALSE', 'LISTEN_ADDRESS': '127.0.0.1',
        'DURIS_WEBSOCKET_LISTEN_ADDRESS': '127.0.0.1',
    }
    mysql = ['mysql', '--no-defaults', '--protocol=socket', f'--socket={socket}', '-uroot', '-N', '-B']

    def sql(statement, selected=True):
        return subprocess.check_output(mysql + ([database] if selected else []),
                                       input=statement, text=True, env=environment).strip()

    sql('CREATE DATABASE ' + database, False)
    sql((ROOT / 'migrations/bootstrap_multithread_safe.sql').read_text())
    for arguments in (('adopt', '--kind', 'fresh_bootstrap'), ('run',)):
        result = subprocess.run(['python3', 'scripts/migration_runner.py', *arguments],
                                cwd=ROOT, env=environment, capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
    runtime = work / 'runtime'
    runtime.mkdir()
    journey.make_fixture(runtime)
    journey.generate_certificate(runtime)
    (runtime / 'logs/log').mkdir(parents=True)
    (runtime / 'journals/critical').mkdir(parents=True)
    plain, tls, websocket = journey.available_ports()
    environment.update(CRITICAL_COMMAND_JOURNAL_DIR=str(runtime / 'journals/critical'),
                       DURIS_TLS_PORT=str(tls), DURIS_WEBSOCKET_PORT=str(websocket))
    output_path = runtime / 'server.out'
    process = client = None
    with output_path.open('w') as output:
        try:
            process = subprocess.Popen([str(server), '--minimal', '-s', '-d', str(runtime), str(plain)],
                                       cwd=runtime, env=environment, stdout=output, stderr=subprocess.STDOUT)
            deadline = time.monotonic() + 120
            while b'Entering game loop.' not in output_path.read_bytes():
                assert process.poll() is None and time.monotonic() < deadline, output_path.read_text(errors='replace')[-6000:]
                time.sleep(0.1)
            client = journey.MudClient(plain)
            journey.create_character(client)

            def save():
                client.send('save')
                client.expect('Save complete for ' + journey.CHARACTER + '.', timeout=30)

            def quit_player():
                client.send('quit')
                client.expect('ACCOUNT MENU', timeout=60)
                client.send('0')
                client.close()

            save()
            quit_player()
            # Only this synthetic offline character is promoted to exercise staff commands.
            sql(f"UPDATE player_data SET level=62,highest_level=62 WHERE name='{journey.CHARACTER}'")
            client = journey.reconnect_character(plain)
            client.expect_any(('Pos: standing >', '<>'), timeout=20)
            for stat, value in (('str', 128), ('agi', 129), ('int', 255)):
                client.send(f'setbit char {journey.CHARACTER} {stat} {value}')
                client.expect_any(('Pos: standing >', '<>'), timeout=20)
            save()
            assert sql(f"SELECT base_str,base_agi,base_int FROM player_data WHERE name='{journey.CHARACTER}'") == '128\t129\t255'
            quit_player()
            client = journey.reconnect_character(plain)
            client.expect_any(('Pos: standing >', '<>'), timeout=20)
            save()
            assert sql(f"SELECT base_str,base_agi,base_int FROM player_data WHERE name='{journey.CHARACTER}'") == '128\t129\t255'
            print('Real setbit/save/logout/relog preserves widened stats: PASS', flush=True)

            # Any terminal SQL failure must restore access to the last committed save.
            # A trigger gives a deterministic non-stat failure without changing production.
            sql("CREATE TRIGGER fail_checkpoint BEFORE UPDATE ON player_data FOR EACH ROW "
                "SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='synthetic checkpoint failure'")
            durable = sql(f"SELECT save_revision FROM player_data WHERE name='{journey.CHARACTER}'")
            quit_player()
            client = None
            deadline = time.monotonic() + 30
            while True:
                logs = '\n'.join(p.read_text(errors='replace') for p in (runtime / 'logs').rglob('*') if p.is_file())
                if 'ended=1' in logs and 'rollback_confirmed=1' in logs:
                    break
                assert time.monotonic() < deadline, logs[-5000:]
                time.sleep(0.1)
            assert sql(f"SELECT save_revision FROM player_data WHERE name='{journey.CHARACTER}'") == durable
            sql('DROP TRIGGER fail_checkpoint')
            client = journey.reconnect_character(plain)
            client.expect_any(('Pos: standing >', '<>'), timeout=20)
            save()
            assert int(sql(f"SELECT save_revision FROM player_data WHERE name='{journey.CHARACTER}'")) > int(durable)
            assert sql(f"SELECT base_str,base_agi,base_int FROM player_data WHERE name='{journey.CHARACTER}'") == '128\t129\t255'
            assert process.poll() is None
            print('Terminal rollback logged; committed revision reloaded and saved without restart: PASS', flush=True)
        finally:
            if client:
                client.close()
            if process and process.poll() is None:
                process.send_signal(signal.SIGTERM)
                process.wait(timeout=45)
            evidence = ROOT / 'bin/tests/player-stat-login-evidence'
            evidence.mkdir(parents=True, exist_ok=True)
            import shutil
            shutil.copy2(output_path, evidence / 'server.out')
            shutil.copytree(runtime / 'logs', evidence / 'logs', dirs_exist_ok=True)


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server', type=Path, help='also run real save/logout/login acceptance')
    parser.add_argument('--mysql-basedir', type=Path, help='use native MySQL 8 from this directory')
    arguments = parser.parse_args()
    server_binary = arguments.server
    if server_binary:
        server_binary = server_binary.resolve()
    binary = ROOT / 'bin/tests/player_base_stats_mysql_harness'
    binary.parent.mkdir(parents=True, exist_ok=True)
    sources = ['tests/async/player_base_stats_mysql_harness.cpp',
               'tests/async/harness_stubs.cpp',
               'src/player/player_snapshot_repository.c', 'src/player/player_snapshot_codec.c',
               'src/item/item_claim_repository.c', 'src/item/item_claim.c',
               'src/persistence/dupe_log.c', 'src/sql/item_extra_descr_codec.c',
               'src/persistence/persistence_observability.c']
    subprocess.run(['g++', '-std=c++20', '-Wall', '-Wextra', '-Werror', '-pthread',
                    '-ffunction-sections', '-fdata-sections', '-Isrc',
                    *shlex.split(subprocess.check_output(['mysql_config', '--cflags'], text=True)),
                    *sources, '-Wl,--gc-sections',
                    *shlex.split(subprocess.check_output(['mysql_config', '--libs'], text=True)),
                    '-lcrypto', '-o', str(binary)], cwd=ROOT, check=True)
    with tempfile.TemporaryDirectory(prefix='duris-base-stats-') as td:
        work = Path(td)
        socket = str(work / 'mysql.sock')
        if arguments.mysql_basedir:
            daemon = str(arguments.mysql_basedir.resolve() / 'bin/mysqld')
            initialize = [daemon, '--no-defaults', '--initialize-insecure', f'--datadir={work}/data']
            extra = ['--mysqlx=OFF', '--default-authentication-plugin=mysql_native_password']
        else:
            daemon = 'mariadbd'
            initialize = ['mariadb-install-db', '--no-defaults', f'--datadir={work}/data',
                          '--auth-root-authentication-method=normal', '--skip-test-db']
            extra = []
        with (work / 'setup.log').open('w') as log:
            subprocess.run(initialize, check=True, stdout=log, stderr=subprocess.STDOUT)
        server = subprocess.Popen([daemon, '--no-defaults', f'--datadir={work}/data',
                                   f'--socket={socket}', '--skip-networking',
                                   f'--pid-file={work}/pid', f'--log-error={work}/server.log',
                                   '--innodb-buffer-pool-size=64M', *extra],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        mysql = ['mysql', '--no-defaults', '--protocol=socket', f'--socket={socket}',
                 '-uroot', '-N', '-B']
        try:
            for _ in range(100):
                assert server.poll() is None, (work / 'server.log').read_text()
                if subprocess.run(mysql + ['-e', 'SELECT 1'], capture_output=True).returncode == 0:
                    break
                time.sleep(0.1)
            else:
                raise RuntimeError('isolated database did not start')

            def sql(statement, database=None):
                return subprocess.check_output(mysql + ([database] if database else []),
                                               input=statement, text=True).strip()

            sql("ALTER USER 'root'@'localhost' IDENTIFIED BY 'stats-test'")
            mysql.append('--password=stats-test')
            bootstrap = (ROOT / 'migrations/bootstrap_multithread_safe.sql').read_text()
            for database, legacy in (('stats_fresh', False), ('stats_upgrade', True)):
                sql(f'CREATE DATABASE {database}')
                schema = bootstrap
                if legacy:
                    for stat in STATS:
                        schema = schema.replace(f'`base_{stat}` smallint', f'`base_{stat}` tinyint')
                sql(schema, database)
                sql("INSERT INTO player_data(pid,name,base_str,base_dex) VALUES(1,'Retained',-128,127)", database)
                environment = dict(os.environ, ENVIRONMENT='test', DB_HOST='localhost',
                                   DB_SOCKET=socket, DB_USER='root', DB_PASSWD='stats-test', DB_NAME=database)
                for arguments in (('adopt', '--kind', 'fresh_bootstrap'), ('run',)):
                    result = subprocess.run(['python3', 'scripts/migration_runner.py', *arguments],
                                            cwd=ROOT, env=environment, capture_output=True, text=True)
                    assert result.returncode == 0, result.stdout + result.stderr
                sql(MIGRATION.read_text(), database)
                assert sql('SELECT base_str,base_dex FROM player_data WHERE pid=1', database) == '-128\t127'
                subprocess.run([str(ROOT / 'migrations/verify_runtime_compatibility.sh')],
                               cwd=ROOT, env=environment, check=True)
                subprocess.run([str(MIGRATION.with_suffix('.sh'))], env=environment, check=True)
                subprocess.run([str(binary), socket, database], cwd=work, check=True)
                print(f'{database}: migration replay, verifier, retained data and real saves PASS', flush=True)

            # Mixed partial upgrades retain defaults/nullability; wider columns are never narrowed.
            sql('DELETE FROM player_data', 'stats_upgrade')
            sql('ALTER TABLE player_data MODIFY base_str TINYINT NOT NULL DEFAULT 7, '
                'MODIFY base_dex INT DEFAULT 0', 'stats_upgrade')
            sql(MIGRATION.read_text(), 'stats_upgrade')
            assert sql("SELECT data_type,is_nullable,column_default FROM information_schema.columns "
                       "WHERE table_schema='stats_upgrade' AND table_name='player_data' "
                       "AND column_name='base_str'") == 'smallint\tNO\t7'
            assert sql("SELECT data_type FROM information_schema.columns WHERE table_schema='stats_upgrade' "
                       "AND table_name='player_data' AND column_name='base_dex'") == 'int'
            print('Partial upgrade preserves definitions and never narrows wider columns: PASS')
            if server_binary:
                login_journey(socket, work, server_binary)
        finally:
            server.terminate()
            server.wait(timeout=30)


if __name__ == '__main__':
    main()
