#!/usr/bin/env python3
"""The level cap opens one level at a time, unlocked by frags, on MariaDB or MySQL.

The maintenance job with the shipped lib/frag_cap.cfg, from a wipe: level 30 open to all
and no timer. Frags of victims more than 5 levels below the level open to all unlock
nothing. Neither do kills with unknown ally counts, base shares below the current
threshold, or no frag gain. Eligibility uses the recorded ally count, not the modified
individual gain, and follows configuration changes while a kill is pending. With the
totals level, the first qualifying frag unlocks 31 for every side and starts the
three-day timer. A frag before the timer ends does
nothing. After it, only the side with more total frags unlocks: the other side's and the
undead's frags are passed over, and the leader's next frag unlocks one level for that side
alone. A level that opens a spell circle opens to every side, and 56 ends it. Frags
recorded before the job ran unlock one level, not one per old frag. With no timer, the frag
that unlocks a level cannot unlock another, even when the job runs in its second.
Run through with_disposable_mariadb.sh.
"""
from pathlib import Path
import os
import shlex
import subprocess
import tempfile
import uuid

from _paths import HARNESS_STUBS

ROOT = Path(__file__).resolve().parents[2]
DAY = 86400
WIPE = 1_800_000_000
GOOD, EVIL, UNDEAD, GOOD_TWO = 1, 2, 3, 4  # frag_leaderboard pids, racewar 1, 2, 3, 1


def main():
    host = os.environ['TEST_DB_HOST']
    assert host == '127.0.0.1', 'use a disposable loopback database'
    database = 'level_cap_' + uuid.uuid4().hex[:12]
    environment = {
        'PATH': os.environ.get('PATH', '/usr/bin:/bin'),
        'ENVIRONMENT': 'test', 'DB_HOST': host, 'DB_PORT': os.environ['TEST_DB_PORT'],
        'DB_NAME': database, 'DB_USER': os.environ['TEST_DB_USER'],
        'DB_PASSWD': os.environ['TEST_DB_PASSWORD'],
        'MYSQL_PWD': os.environ['TEST_DB_PASSWORD'],
    }
    mysql = ['mysql', '--protocol=tcp', '-h', host, '-P', environment['DB_PORT'],
             '-u', environment['DB_USER'], '-N', '-B']

    def sql(statement, selected=True):
        return subprocess.check_output(
            mysql + ([database] if selected else []),
            input="SET time_zone='+00:00';\n" + statement, text=True,
            env=environment).strip()

    sql('CREATE DATABASE ' + database + ' CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci',
        False)
    try:
        sql((ROOT / 'migrations/bootstrap_multithread_safe.sql').read_text())
        for args in (('adopt', '--kind', 'fresh_bootstrap'), ('run',)):
            result = subprocess.run(['python3', 'scripts/migration_runner.py', *args],
                                    cwd=ROOT, env=environment, capture_output=True, text=True)
            assert result.returncode == 0, result.stdout + result.stderr

        (ROOT / 'bin/tests').mkdir(parents=True, exist_ok=True)
        harness = ROOT / 'bin/tests/level_cap_mysql_harness'
        subprocess.run(
            ['g++', '-std=c++20', '-Wall', '-Wextra', '-Werror', '-Isrc',
             *shlex.split(subprocess.check_output(['mysql_config', '--cflags'], text=True)),
             '-ffunction-sections', '-fdata-sections',
             'tests/async/level_cap_mysql_harness.cpp',
             'src/persistence/maintenance_repository.c',
             'src/economy/divine_boon.c', 'src/economy/divine_boon_repository.c',
             'src/economy/divine_trade.c', 'src/economy/divine_trade_command.c', 'src/economy/divine_trade_repository.c', 'src/economy/currency_command.c', 'src/persistence/critical_command.c',
             'src/persistence/persistence_observability.c', 'src/combat/frag_cap_config.c',
             '-Wl,--gc-sections',
             *shlex.split(subprocess.check_output(['mysql_config', '--libs'], text=True)),
             str(HARNESS_STUBS), '-lcrypto', '-o', str(harness)], cwd=ROOT, check=True)

        runs = iter(range(1, 1000))

        def job(now, config_root=ROOT):
            # From config_root, where boot_frag_cap_config() reads lib/frag_cap.cfg.
            return subprocess.run(
                [str(harness), host, environment['DB_PORT'], environment['DB_USER'],
                 environment['DB_PASSWD'], database, str(now), str(next(runs))],
                cwd=config_root, capture_output=True, text=True, check=True).stdout.strip()

        def cap():
            return sql('SELECT level, level_good, level_evil, UNIX_TIMESTAMP(next_update) '
                       'FROM level_cap')

        def totals(good, evil):
            sql(f'UPDATE frag_leaderboard SET total_frags={good} WHERE pid={GOOD};'
                f'UPDATE frag_leaderboard SET total_frags=0 WHERE pid={GOOD_TWO};'
                f'UPDATE frag_leaderboard SET total_frags={evil} WHERE pid={EVIL};')

        kills = iter(range(1, 1000))

        def kill(at, killer, victim, victim_level, gain=100, allies=5):
            event = next(kills)
            operation = f"UNHEX('{event:032x}')"
            sql(f"""
INSERT INTO critical_operation_inbox (operation_id, command_hash, keys_hash, command_type,
  schema_version, payload_version, status, result_payload)
  VALUES ({operation}, UNHEX(REPEAT('00', 32)), UNHEX(REPEAT('00', 32)), 0, 0, 0, 0, '');
INSERT INTO pkill_info (event_id, pid, level, pk_type, equip)
  VALUES ({event}, {victim}, {victim_level}, 'VICTIM', '');
INSERT INTO combat_outcome (operation_id, pkill_event_id, victim_pid, room_vnum,
  participant_count, killer_allies, created_at) VALUES ({operation}, {event}, {victim}, 0, 2,
  {allies}, FROM_UNIXTIME({at}));
INSERT INTO combat_outcome_participant (operation_id, participant_index, pid, role, flags,
  frag_delta, epic_delta, wallet_delta_copper, frag_after, frag_revision, epic_revision,
  wallet_revision, bank_revision) VALUES
  ({operation}, 0, {killer}, 1, 0, {gain}, 0, 0, {gain},
   1, 0, 0, 0),
  ({operation}, 1, {victim}, 3, 0, {-gain}, 0, 0, {-gain}, 1, 0, 0, 0);
""")
            return operation

        sql(f"""
INSERT INTO frag_leaderboard (pid, account_name, char_name, total_frags, racewar) VALUES
  ({GOOD}, 'a', 'Goodone', 0, 1), ({EVIL}, 'b', 'Evilone', 0, 2),
  ({UNDEAD}, 'c', 'Lichone', 0, 3), ({GOOD_TWO}, 'd', 'Goodtwo', 0, 1);
UPDATE level_cap SET most_frags=0, racewar_leader=0, level=30, level_good=0, level_evil=0,
  next_update=FROM_UNIXTIME({WIPE});
""")

        assert job(WIPE + 60) == 'complete 0', 'unlocked with no frag'
        # 24 is more than 5 levels below the 30 open to all.
        kill(WIPE + 100, GOOD, EVIL, 24)
        assert job(WIPE + 150) == 'complete 0', 'a low-level victim unlocked a level'
        kill(WIPE + 160, GOOD, EVIL, 30, allies=0)
        assert job(WIPE + 170) == 'complete 0', 'a kill without the base share unlocked'
        kill(WIPE + 171, GOOD, EVIL, 30, allies=6)
        assert job(WIPE + 172) == 'complete 0', 'six allies unlocked at the five-ally limit'
        kill(WIPE + 173, GOOD, EVIL, 30, gain=0)
        assert job(WIPE + 175) == 'complete 0', 'a kill that gained nothing unlocked'
        # Twenty winners at 0.05 each: 1.00 frag over 20 is below the 0.20 base share.
        operation = kill(WIPE + 180, GOOD, EVIL, 30, gain=5, allies=20)
        for index in range(2, 21):
            pid = 100 + index
            sql(f"INSERT INTO frag_leaderboard "
                f"(pid, account_name, char_name, total_frags, racewar) "
                f"VALUES ({pid}, 'group{index}', 'Winner{index}', 0, 1);")
            sql(f"INSERT INTO combat_outcome_participant "
                f"(operation_id,participant_index,pid,role,flags,frag_delta,epic_delta,"
                f"wallet_delta_copper,frag_after,frag_revision,epic_revision,"
                f"wallet_revision,bank_revision) VALUES "
                f"({operation},{index},{pid},2,0,5,0,0,5,1,0,0,0);")
        sql(f"UPDATE combat_outcome SET participant_count=21 WHERE operation_id={operation}")
        assert job(WIPE + 190) == 'complete 0', '20 small gains were combined to unlock'
        assert cap() == f'30\t0\t0\t{WIPE}', cap()
        print('[PASS] kills below the base share, even of a full frag, cannot unlock',
              flush=True)
        # The totals are level, so the first qualifying frag by either side unlocks. 0.10 is
        # a 0.20 base share halved for a killer more than 5 levels above the victim.
        kill(WIPE + 200, EVIL, GOOD, 25, gain=10)
        assert job(WIPE + 250) == 'complete 1 2 31 1'
        timer = WIPE + 250 + 3 * DAY
        assert cap() == f'31\t0\t0\t{timer}', cap()
        print('[PASS] the base share and the minimum victim level open 31 to all',
              flush=True)

        kill(WIPE + 300, GOOD, EVIL, 31)
        assert job(timer - 1) == 'complete 0', 'unlocked before the timer ended'
        print('[PASS] nothing unlocks before the 3-day timer ends', flush=True)

        totals(500, 100)
        kill(timer + 1, EVIL, GOOD, 31)
        kill(timer + 2, UNDEAD, GOOD, 31)
        kill(timer + 3, GOOD, EVIL, 25)
        kill(timer + 5, GOOD_TWO, EVIL, 26)
        assert job(timer + 10) == 'complete 1 1 32 0'
        assert cap() == f'31\t32\t0\t{timer + 10 + 3 * DAY}', cap()
        print('[PASS] only the leading side\'s frag unlocks, and 32 for that side alone',
              flush=True)

        timer += 10 + 3 * DAY
        sql('UPDATE level_cap SET level_good=35, level_evil=33')
        kill(timer + 1, GOOD, EVIL, 30)
        assert job(timer + 2) == 'complete 1 1 36 1'
        assert cap() == f'36\t35\t33\t{timer + 2 + 3 * DAY}', cap()
        print('[PASS] a side\'s frag that opens the next spell circle opens it to all',
              flush=True)

        timer += 2 + 3 * DAY
        totals(100, 900)
        sql('UPDATE level_cap SET level=51, level_good=53, level_evil=55')
        kill(timer + 1, EVIL, GOOD, 50)
        assert job(timer + 2) == 'complete 1 2 56 1'
        kill(timer + 3 * DAY + 10, EVIL, GOOD, 56)
        assert job(timer + 3 * DAY + 20) == 'complete 0', 'unlocked past 56'
        assert cap().split('\t')[0] == '56', cap()
        print('[PASS] 56 opens to all and nothing unlocks after it', flush=True)

        # Two qualifying frags 4 days apart, both before the job runs: one unlock, and the
        # timer restarts from it rather than from the first frag.
        backlog = timer + 4 * DAY
        sql('UPDATE level_cap SET level=40, level_good=0, level_evil=0, '
            f'next_update=FROM_UNIXTIME({backlog})')
        kill(backlog + 1, EVIL, GOOD, 40)
        kill(backlog + 4 * DAY, EVIL, GOOD, 40)
        assert job(backlog + 8 * DAY) == 'complete 1 2 41 1'
        assert cap() == f'41\t0\t0\t{backlog + 11 * DAY}', cap()
        assert job(backlog + 8 * DAY + 60) == 'complete 0', 'old frags chained unlocks'
        print('[PASS] frags from before the job ran unlock one level', flush=True)

        config = (ROOT / 'lib/frag_cap.cfg').read_text()
        assert 'timer.unlock.days=3' in config
        with tempfile.TemporaryDirectory() as no_timer:
            (Path(no_timer) / 'lib').mkdir()
            (Path(no_timer) / 'lib/frag_cap.cfg').write_text(
                config.replace('timer.unlock.days=3', 'timer.unlock.days=0'))
            later = backlog + 12 * DAY
            sql('UPDATE level_cap SET level=40, level_good=0, level_evil=0, '
                f'next_update=FROM_UNIXTIME({later})')
            kill(later + 1, EVIL, GOOD, 40)
            # The job runs in the frag's second, the earliest the timer could restart from.
            assert job(later + 1, no_timer) == 'complete 1 2 41 1'
            assert job(later + 2, no_timer) == 'complete 0', 'one frag unlocked twice'
        print('[PASS] with no timer, one frag unlocks one level', flush=True)

        # A pending five-allies kill becomes ineligible when raised from 20 to 25,
        # then eligible again when lowered. The stored fact stays unchanged.
        with tempfile.TemporaryDirectory() as threshold_root:
            cfg = Path(threshold_root) / 'lib/frag_cap.cfg'
            cfg.parent.mkdir()
            later += DAY
            sql('UPDATE level_cap SET level=40, level_good=0, level_evil=0, '
                f'next_update=FROM_UNIXTIME({later})')
            pending = kill(later + 1, EVIL, GOOD, 40, gain=10, allies=5)
            for threshold, expected in ((25, 'complete 0'), (20, 'complete 1 2 41 1')):
                cfg.write_text(config.replace('unlock.minimum.share.points=20',
                                               f'unlock.minimum.share.points={threshold}'))
                assert job(later + 2, threshold_root) == expected
            assert sql(f'SELECT killer_allies FROM combat_outcome WHERE operation_id={pending}') == '5'
            # Integer thresholds compare without rounding: 3*33 <=100, 3*34 >100.
            later += 4 * DAY
            sql('UPDATE level_cap SET level=40, level_good=0, level_evil=0, '
                f'next_update=FROM_UNIXTIME({later})')
            kill(later + 1, EVIL, GOOD, 40, allies=3)
            for threshold, expected in ((34, 'complete 0'), (33, 'complete 1 2 41 1')):
                cfg.write_text(config.replace('unlock.minimum.share.points=20',
                                               f'unlock.minimum.share.points={threshold}'))
                assert job(later + 2, threshold_root) == expected
        print('[PASS] pending kills follow changed thresholds without rounding', flush=True)

        # Reapplying the additive migration preserves the captured facts.
        migration = (ROOT / 'migrations/immutable/0040_combat_outcome_allies.sql').read_text()
        before = sql('SELECT HEX(operation_id),killer_allies FROM combat_outcome ORDER BY operation_id')
        sql(migration)
        sql(migration)
        assert sql('SELECT HEX(operation_id),killer_allies FROM combat_outcome ORDER BY operation_id') == before
        print('[PASS] ally-count migration is rerunnable and preserves history', flush=True)

    finally:
        sql('DROP DATABASE ' + database, False)


if __name__ == '__main__':
    main()
