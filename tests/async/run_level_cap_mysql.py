#!/usr/bin/env python3
"""Real shared cap maintenance, admission, adoption and contention on disposable SQL."""
from pathlib import Path
import os
from concurrent.futures import ThreadPoolExecutor
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
    harness = ROOT / ('bin/tests/level_cap_mysql_harness_' + database)
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
        subprocess.run(
            ['g++', '-std=c++20', '-Wall', '-Wextra', '-Werror', '-Isrc',
             *shlex.split(subprocess.check_output(['mysql_config', '--cflags'], text=True)),
             '-ffunction-sections', '-fdata-sections',
             'tests/async/level_cap_mysql_harness.cpp',
             'src/persistence/maintenance_repository.c', 'src/flatfile/flatfile_authority_transaction.c', 'src/flatfile/flatfile_store.c', 'src/combat/frag_cap.c', 'src/combat/frag_cap_repository.c',
             'src/economy/divine_boon.c', 'src/economy/divine_boon_repository.c',
             'src/economy/divine_trade.c', 'src/economy/divine_trade_command.c', 'src/economy/divine_trade_repository.c', 'src/economy/currency_command.c', 'src/persistence/critical_command.c',
             'src/persistence/persistence_observability.c', 'src/combat/frag_cap_config.c',
             '-Wl,--gc-sections',
             *shlex.split(subprocess.check_output(['mysql_config', '--libs'], text=True)),
             str(HARNESS_STUBS), '-lcrypto', '-o', str(harness)], cwd=ROOT, check=True)

        runs = iter(range(1, 1000))

        def run(now, mode=None, *values, config_root=ROOT, check=True):
            args = [str(harness), host, environment['DB_PORT'], environment['DB_USER'],
                    environment['DB_PASSWD'], database, str(now), str(next(runs))]
            if mode:
                args += [mode, *map(str, values)]
            return subprocess.run(args, cwd=config_root, capture_output=True, text=True, check=check)

        def inspect():
            fields = run(WIPE, 'inspect').stdout.strip().split()
            return dict(zip(('level','revision','start','deadline','good','evil','gcap','ecap'),map(int,fields)))

        def adopt(level=30, good=0, evil=0, deadline=WIPE):
            sql(f"UPDATE level_cap SET snapshot=NULL,level={level},level_good={good},level_evil={evil},"
                f"next_update=FROM_UNIXTIME({deadline})")
            run(WIPE,'adopt')
            return inspect()

        state=adopt()
        assert state['gcap']==state['ecap']==31 and state['deadline']==WIPE+3*DAY
        assert run(WIPE+3*DAY-1).stdout.strip()=='complete 0'
        assert run(WIPE+3*DAY).stdout.strip()=='complete 1'
        assert inspect()['gcap']==inspect()['ecap']==32
        assert run(WIPE+3*DAY).stdout.strip()=='complete 0'

        for hour in (1,47,60):
            adopt(); q=WIPE+hour*3600
            run(q,'credit',1,20,q);run(q,'credit',2,10,q)
            run(q,'credit',1,-100,q)
            state=inspect()
            assert state['level']==31 and state['good']==20 and state['evil']==10
            run(WIPE+3*DAY)
            state=inspect()
            assert (state['gcap'],state['ecap'])==(32,31) and state['good']==state['evil']==0
            run(WIPE+6*DAY) # Quiet tie preserves the previous lead.
            assert (inspect()['gcap'],inspect()['ecap'])==(33,32)
            run(WIPE+6*DAY+1,'credit',2,1,WIPE+6*DAY+1)
            run(WIPE+9*DAY)
            assert (inspect()['gcap'],inspect()['ecap'])==(33,34)

        adopt();boundary=WIPE+3*DAY
        run(boundary-1,'credit',1,19,boundary-1)
        run(boundary,'credit',2,1,boundary)
        state=inspect()
        assert (state['gcap'],state['ecap'])==(32,31) and state['evil']==1
        run(boundary+1,'credit',1,100,boundary-1)
        run(boundary+1,'credit',1,100,WIPE-1)
        assert inspect()==state
        run(WIPE+75*DAY)
        assert inspect()['gcap']==inspect()['ecap']==56 and inspect()['deadline']==0
        assert run(WIPE+90*DAY).stdout.strip()=='complete 0'

        adopt();q=WIPE+60*3600
        with ThreadPoolExecutor(max_workers=3) as pool:
            jobs=[pool.submit(run,q,'credit',1,10,q),pool.submit(run,q,'credit',2,10,q),pool.submit(run,q)]
            for job in jobs:job.result()
        assert inspect()['good']==inspect()['evil']==10
        run(WIPE+3*DAY)
        assert inspect()['gcap']==inspect()['ecap']==32

        state=adopt(36,40,38,WIPE+30*3600)
        assert state['level']==40 and state['deadline']==WIPE+30*3600
        before=inspect();run(WIPE+DAY,'adopt');assert inspect()==before
        assert adopt(40,0,0,WIPE-100*DAY)['level']==41
        assert adopt(56)['deadline']==0
        adopt(35,0,0,WIPE+3*DAY)
        run(WIPE+1,'credit',2,1,WIPE+1);run(WIPE+3*DAY)
        assert inspect()['gcap']==inspect()['ecap']==36

        adopt()
        with tempfile.TemporaryDirectory() as directory:
            config_root=Path(directory);(config_root/'lib').mkdir()
            config=(ROOT/'lib/frag_cap.cfg').read_text().replace('round.hours=72','round.hours=36')
            (config_root/'lib/frag_cap.cfg').write_text(config)
            run(WIPE+3600,'credit',1,10,WIPE+3600,config_root=config_root)
            assert inspect()['deadline']==WIPE+3*DAY
            run(WIPE+3*DAY,config_root=config_root)
            assert inspect()['deadline']==WIPE+108*3600
        sql("UPDATE level_cap SET snapshot=UNHEX('00')")
        assert run(WIPE+3*DAY,check=False).returncode!=0
        assert run(WIPE,'adopt',check=False).returncode!=0
        sql('DELETE FROM level_cap')
        assert run(WIPE,check=False).returncode!=0
        print('PASS faction race SQL lifecycle: pooling, winners, ties, circle equality, admission, contention, catch-up, adoption and fail-closed storage')
    finally:
        if harness.exists():
            harness.unlink()
        sql('DROP DATABASE ' + database, False)


if __name__ == '__main__':
    main()
