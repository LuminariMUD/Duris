#!/usr/bin/env python3
"""Export real session-audit outcomes through a SELECT-only account on the disposable DB."""
from contextlib import redirect_stderr, redirect_stdout
from datetime import date
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import login_stats_export as exporter

# run_session_audit_schema_mysql.sh creates this disposable schema and the typed
# writer harness records the login fixtures (including replay of a v1 command).
assert os.environ.get('ENVIRONMENT') == 'test'
assert os.environ['DB_NAME'] == 'duris_test'
mysql = ['mysql', '--protocol=tcp', '-h', os.environ['DB_HOST'], '-P', os.environ['DB_PORT'],
         '-u', os.environ['DB_USER'], os.environ['DB_NAME']]
def sql(statement):
    subprocess.run(mysql + ['-e', statement], check=True, capture_output=True)

sql("CREATE USER 'stats_reader'@'%' IDENTIFIED BY 'disposable-stats'; "
    "GRANT SELECT ON duris_test.session_audit_outcome TO 'stats_reader'@'%'; "
    "INSERT INTO player_data (pid,name,account_name,level) VALUES "
    "(2147000411,'StatsFixture','alice',56)")
settings = {f'LOGIN_STATS_DB_{key}': value for key, value in {
    'HOST': os.environ['DB_HOST'], 'PORT': os.environ['DB_PORT'], 'DATABASE': 'duris_test',
    'USER': 'stats_reader', 'PASSWORD': 'disposable-stats',
}.items()}
with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, settings):
    directory = Path(temporary) / 'public/stats'
    def export(zone='UTC', today=date(2023, 11, 15)):
        errors = io.StringIO()
        with redirect_stdout(io.StringIO()), redirect_stderr(errors):
            assert exporter.export(directory, zone, 90, today) == 0
        latest = json.loads((directory / 'latest.json').read_text())
        history = json.loads((directory / 'history.json').read_text())
        latest.pop('generated_at'); history.pop('generated_at')
        return latest, history, errors.getvalue()

    before = export()
    assert before[0] == dict(timezone='UTC', date='2023-11-14', unique_accounts=2, logins=3), before
    assert len(before[1]['days']) == 1, before
    assert '1 logins had no identity snapshot' in before[2], before
    # Promotion, account transfer, and erasure each leave historical figures alone.
    for mutation in (
        'UPDATE player_data SET level=57 WHERE pid=2147000411',
        "UPDATE player_data SET account_name='bob' WHERE pid=2147000411",
        'DELETE FROM player_data WHERE pid=2147000411',
    ):
        sql(mutation)
        assert export() == before, mutation
    sydney = export('Australia/Sydney', date(2023, 11, 16))
    assert sydney[0] == dict(timezone='Australia/Sydney', date='2023-11-15', unique_accounts=2, logins=3), sydney
    assert not list(directory.glob('*.tmp'))
print('PASS: typed snapshots, legacy replay, SELECT-only export, alts, staff, today, time zones, promotion, transfer and erasure')
