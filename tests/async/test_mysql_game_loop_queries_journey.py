#!/usr/bin/env python3
"""The game loop never waits on a query after boot (persistence reset phase 2, step 8).

A real server on a disposable MariaDB, in the combat journey's fixture world: a new
account and character are created, the character plays, saves and quits, the account
menu lists its characters, and the character, now a god, enters the game again, runs
the commands the rest of step 8 moved off the loop, and quits. Every
query the game thread issues while the loop runs logs its site once (`game loop query
site <file>:<line> <function> (<kind>)`). No site may appear except the functions
NOT_CONVERTED still lists: the rest of step 8 empties it. Run it through
with_disposable_mariadb.sh (make test-db); --server picks the executable.
"""
from pathlib import Path
import argparse
import os
import re
import signal
import subprocess
import tempfile
import time
import uuid

import test_flatfile_combat_journey as journey

ROOT = Path(__file__).resolve().parents[2]

# What the god runs in the game, and a line of each answer: the answer comes on a later
# pulse when the command reads the database. The next entry summons the divine reward
# granted here and reads back the epic bonus chosen here, and REENTRY_COMMANDS show the
# bonus and revoke the reward.
COMMANDS = (
    ('finger ' + journey.CHARACTER, 'PID:'),
    ('fraglist', 'Lowest Fraggers'),
    ('fraglist warrior', 'Lowest Fraggers'),
    ('load obj 677', 'Pos: standing >'),
    ('epic zones', 'already completed this boot'),
    ('stat zone', 'Zone flags:'),
    ('epic', 'Evils'),
    ('epic trophy', 'Epic Trophy'),
    ('epic bonus exp', 'Your epic bonus has been changed to Experience Bonus'),
    # The poll wizard takes the lines that follow as its answers.
    ('poll create', 'Enter the poll question'),
    ('Which color should the arena be?', 'Allow multiple selections'),
    ('no', 'Poll duration in hours'),
    ('24', 'Enter option 1'),
    ('Red', 'Enter option 2'),
    ('Blue', 'Enter option 3'),
    ('done', 'Create this poll'),
    ('yes', 'Poll created successfully'),
    ('poll vote 1 2', 'Your vote has been recorded'),
    ('poll vote 1 1', 'already voted in this poll'),
    ('poll list', 'Which color should the arena be?'),
    ('poll close 1', 'has been closed by'),
    ('hardcore', 'Hall Of'),
    ('leaderboard', 'Leader Board'),
    ('whitelist add Twins 10.1.*.* Brothers on one network', 'Host pattern added'),
    ('whitelist add Guests 10.2.*.* A shared library', 'Host pattern added'),
    ('whitelist remove 10.1.*.*', 'Host pattern removed'),
    ('whitelist', 'A shared library'),
    ('whois ' + journey.CHARACTER, 'IP Addresses used by'),
    ('whois ip 127.%', 'IP Address:'),
    ('divineclaim mace ' + journey.ACCOUNT + ' days 1', 'Created divine reward #1'),
    ('divineclaim list ' + journey.ACCOUNT, 'Active Divine Account Rewards'),
    ('auction list', 'No auctions to list!'),
    ('auction info 1', 'There is no auction with that id!'),
    ('auction pickup', 'You have no items or money to pickup!'),
    ('nexus', 'Nexus Stones'),
    ('boon add all epic 10 level 50 60', 'Boon successfully created.'),
    ('boon list', 'Displaying 1 result(s).'),
    ('boon list u nobody', 'No results.'),
    ('boon extend 1 30', 'Boon # 1 has been extended for 30 minutes.'),
    ('boon remove 1', 'Successfully removed boon # 1.'),
    ('boon shop', 'Stat points available: 0'),
    ('boon shop stat str', "You don't have any stat points available."),
    ('ctf score', 'No data'),
    # Artifacts are held in memory: the drops write their rows, clear deletes one.
    ('load obj 900', 'Pos: standing >'),
    ('drop stone', 'You drop'),
    ('load obj 901', 'Pos: standing >'),
    ('drop stone', 'You drop'),
    # The lists are read on the writer and answer on a later pulse.
    ('artifacts ioun all', '(#901)'),
    ('artifacts ioun mortal', 'No artifacts found.'),
    ('artifacts player ' + journey.CHARACTER, 'No artifacts found.'),
    ('artifacts clear 901', 'cleared from the Immortal and Mortal lists'),
    ('artifacts reset 900', 'Artifact vnum 900 has a hungry soul.'),
    ('artifacts reset fixit', 'Empty set; no artifacts on PC'),
    ('artifacts reset syncdb', 'Cleared 0, updated 0 artifact ownerships'),
)
REENTRY_COMMANDS = (
    ('epic bonus', 'benefiting from the Experience Bonus'),
    ('divineclaim list', 'Copies'),
    ('divineclaim remove 1', 'Revoked 1 divine account reward'),
    # A staff-made character's first save is queued like a player's; it is the newest
    # character, so it comes last, after every entry that selects the first one.
    ('newchar Vexmora 3 11 56 false', 'character saved.'),
)

# The functions this session still reaches with a query on the game loop.
NOT_CONVERTED = set()


def enter(client):
    client.send('1')
    client.expect(journey.CHARACTER, timeout=15)
    client.send('1')
    client.expect('Play as', timeout=15)
    client.send('y')
    client.expect('The Regression Arena', timeout=30)


def run_commands(client, commands):
    for command, answer in commands:
        client.send(command)
        client.expect(answer, timeout=30)


def run(server):
    database = 'loop_queries_' + uuid.uuid4().hex[:12]
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
    def sql(text):
        subprocess.run(mysql + [database], input=text, text=True, env=environment, check=True)

    subprocess.run(mysql, input='CREATE DATABASE ' + database +
                   ' CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci', text=True,
                   env=environment, check=True)
    subprocess.run(mysql + [database],
                   input=(ROOT / 'migrations/bootstrap_multithread_safe.sql').read_text(),
                   text=True, env=environment, check=True)
    for args in (('adopt', '--kind', 'fresh_bootstrap'), ('run',)):
        subprocess.run(['python3', 'scripts/migration_runner.py', *args], cwd=ROOT,
                       env=environment, check=True, capture_output=True)
    with tempfile.TemporaryDirectory(prefix='loop-queries-', dir=ROOT / 'bin/tests') as tmp:
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
        output_path = runtime / 'server.out'
        output = output_path.open('w')
        process = subprocess.Popen(
            [str(server), '--minimal', '-s', '-d', str(runtime), str(plain)], cwd=runtime,
            env=environment, stdout=output, stderr=subprocess.STDOUT)
        client = None
        try:
            deadline = time.monotonic() + 120
            while b'Entering game loop.' not in output_path.read_bytes():
                assert process.poll() is None and time.monotonic() < deadline, 'boot failed'
                time.sleep(0.1)

            client = journey.MudClient(plain)
            journey.create_character(client)
            client.send('save')
            client.expect('Save complete for ' + journey.CHARACTER + '.', timeout=30)
            # `save` leaves a command lag; let it pass so quit runs when it is sent.
            client.send('look')
            client.expect('Obvious exits', timeout=20)
            client.expect('Pos: standing >', timeout=10)
            client.send('quit')
            client.expect('Please select an option', timeout=60)
            # The staff commands below need a god. The camp's log row is queued after
            # the quit's save, so once it lands the save cannot undo the promotion.
            deadline = time.monotonic() + 30
            while subprocess.run(
                    mysql + [database], text=True, env=environment, check=True,
                    capture_output=True,
                    input="SELECT COUNT(*) FROM log_entries WHERE player_name='" +
                    journey.CHARACTER + "' AND message='Camped'").stdout.strip() != '1':
                assert time.monotonic() < deadline, 'the quit was not written'
                time.sleep(0.2)
            sql(f"UPDATE player_data SET level=62 WHERE name='{journey.CHARACTER}'")
            # The account menu's lists come from the account in memory.
            client.send('8')
            client.expect('RESTED BONUS STATUS', timeout=15)
            client.expect('Please select an option', timeout=15)
            client.send('3')
            client.expect('Which character do you want to', timeout=15)
            client.send('0')
            client.expect('Please select an option', timeout=15)
            enter(client)
            run_commands(client, COMMANDS)
            client.send('quit')
            client.expect('Please select an option', timeout=60)
            enter(client)
            client.expect('A divine account reward begins to materialize', timeout=30)
            run_commands(client, REENTRY_COMMANDS)
            client.send('quit')
            client.expect('Please select an option', timeout=60)
            client.send('0')
            client.close()
            client = None
        except Exception:
            print(output_path.read_text(errors='replace')[-6000:])
            print(journey.runtime_logs(runtime)[-6000:])
            if client:
                print(client.transcript.decode(errors='replace')[-6000:])
            raise
        finally:
            if client:
                client.close()
            process.send_signal(signal.SIGTERM)
            try:
                process.wait(timeout=90)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            output.close()

        # The new character's first save went through the writer: its row and the
        # opening baselines the accounting ledgers start from.
        for table in ('player_data', 'currency_wallet_baseline', 'epic_balance_baseline',
                      'combat_frag_baseline'):
            count = subprocess.run(
                mysql + [database], text=True, env=environment, check=True,
                capture_output=True,
                input=f"SELECT COUNT(*) FROM {table} t JOIN player_data pd ON pd.pid=t.pid "
                      f"WHERE pd.name='{journey.CHARACTER}'").stdout.strip()
            assert count == '1', f'{table} holds {count} rows for the new character'
        made = subprocess.run(
            mysql + [database], text=True, env=environment, check=True, capture_output=True,
            input="SELECT (SELECT COUNT(*) FROM player_data WHERE name='Vexmora'), "
                  "(SELECT COUNT(*) FROM account_characters WHERE char_name='Vexmora')"
            ).stdout.split()
        assert made == ['1', '1'], f'newchar stored {made}'
        # Shutdown drained the writer: the revoked grant and its summon are gone, the
        # closed poll, its two options and the one vote are stored, and so is the one
        # whitelist entry left.
        def scalar(query):
            return subprocess.run(mysql + [database], input=query, text=True,
                                  env=environment, check=True,
                                  capture_output=True).stdout.strip()
        for table in ('account_bound_rewards', 'account_bound_reward_summons'):
            left = scalar('SELECT COUNT(*) FROM ' + table)
            assert left == '0', f'{table} still holds {left} rows'
        # The dropped stone's row landed through the writer (on the ground, or on Raoul if he
        # picked it up). The cleared one's ground row is gone; Raoul picking it up later
        # tracks it again, on him.
        rows = subprocess.run(mysql + [database], text=True, env=environment, check=True,
                              capture_output=True,
                              input='SELECT vnum, owned, locType FROM artifacts ORDER BY vnum'
                              ).stdout.split()
        artifacts, cleared = rows[:3], rows[3:]
        assert artifacts in (['900', 'N', '4'], ['900', 'N', '2']), rows
        assert cleared in ([], ['901', 'N', '2']), rows
        # artifact_domain_state repeats the row and its soul, which the guild feed checks.
        domain = subprocess.run(mysql + [database], text=True, env=environment, check=True,
                                capture_output=True,
                                input='SELECT s.vnum, s.owned, s.loc_type, s.location, s.timer_epoch, '
                                      's.bind_owner_pid, s.bind_timer_epoch FROM artifact_domain_state s '
                                      'WHERE s.vnum=900').stdout.split()
        assert domain[:3] == ['900', '0', artifacts[2]], domain
        poll = scalar('SELECT is_active, created_at > 0, expires_at - created_at, '
                      '(SELECT COUNT(*) FROM poll_options WHERE poll_id=1), '
                      '(SELECT COUNT(*) FROM poll_votes WHERE poll_id=1 AND option_id=2) '
                      'FROM polls WHERE id=1')
        assert poll.split() == ['0', '1', '86400', '2', '1'], poll
        whitelist = scalar('SELECT pattern, player, admin, created_on IS NOT NULL '
                           'FROM multiplay_whitelist')
        assert whitelist.split('\t') == ['10.2.*.*', 'guests', journey.CHARACTER, '1'], whitelist

        logs = output_path.read_text(errors='replace') + '\n'.join(
            path.read_text(errors='replace') for path in (runtime / 'logs/log').glob('*')
            if path.is_file())
        sites = sorted(set(re.findall(r'game loop query site (\S+) (\S+) \((\w+)\)', logs)))
        unexpected = [site for site in sites if site[1] not in NOT_CONVERTED]
        for site in sites:
            print('game loop query site', *site)
        assert not unexpected, f'the game loop still queries: {unexpected}'
    print(f'game loop queries journey passed ({len(sites)} sites still listed as not converted)')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server', type=Path, default=ROOT / 'bin/server/dms_new')
    arguments = parser.parse_args()
    if not os.getenv('TEST_DB_HOST'):
        print('game loop queries journey skipped: run it through with_disposable_mariadb.sh')
    else:
        run(arguments.server.resolve(strict=True))
