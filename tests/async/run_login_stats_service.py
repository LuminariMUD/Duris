#!/usr/bin/env python3
"""Exercise the user unit with temporary paths and a fake mysql client; no live DB."""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
name = 'duris-stats-test-' + uuid.uuid4().hex[:10]
service, database = name + '.service', name + '-db.service'

def systemctl(*arguments, check=True):
    return subprocess.run(['systemctl', '--user', *arguments], check=check,
                          capture_output=True, text=True)

with tempfile.TemporaryDirectory(prefix=name) as temporary:
    root = Path(temporary)
    (root / 'duris').symlink_to(ROOT, target_is_directory=True)
    config = root / '.config/duris'
    config.mkdir(parents=True)
    (config / 'login-stats.env').write_text(
        'LOGIN_STATS_DB_DATABASE=fixture\nLOGIN_STATS_DB_USER=fixture\nLOGIN_STATS_DB_PASSWORD=fixture\n')
    commands = root / 'commands'; commands.mkdir()
    yesterday = datetime.now(timezone.utc).replace(hour=12, minute=0, second=0, microsecond=0) - timedelta(days=1)
    stamp = int(yesterday.timestamp())
    client = commands / 'mysql'
    client.write_text(f'''#!/usr/bin/python3
from pathlib import Path
import sys
root = Path({str(root)!r})
assert (root / 'database-ready').exists(), 'export started before database'
assert '--host=127.0.0.1' in sys.argv and '--port=3307' in sys.argv
first = root / 'first-attempt'
if not first.exists():
    first.touch()
    sys.exit(1)
print({str(stamp)!r} if 'MIN(' in sys.argv[-1] else {f'{stamp}\talice\t0'!r})
''')
    client.chmod(0o755)
    unit = (ROOT / 'deploy/systemd/duris-login-stats.service').read_text()
    unit = unit.replace('%h', str(root)).replace('duris-mariadb.service', database)
    # Accelerate the checked-in retry interval without changing the retry policy.
    unit = unit.replace('RestartSec=5min', 'RestartSec=2s')
    unit += f'\nEnvironment="PATH={commands}:/usr/bin:/bin"\n'
    (root / service).write_text(unit)
    (root / database).write_text(
        f'[Service]\nType=oneshot\nExecStart=/usr/bin/touch {root}/database-ready\nRemainAfterExit=yes\n')
    try:
        systemctl('link', '--runtime', str(root / service), str(root / database))
        systemctl('daemon-reload')
        systemctl('start', '--no-block', service)
        output = root / 'durisweb/backend/public/stats/latest.json'
        deadline = time.monotonic() + 30
        while not output.exists() and time.monotonic() < deadline:
            time.sleep(.2)
        assert output.exists(), systemctl('status', service, check=False).stdout
        result = json.loads(output.read_text())
        assert result['unique_accounts'] == result['logins'] == 1, result
        assert result['date'] == yesterday.date().isoformat(), result
        assert (root / 'first-attempt').exists() # First query failed; only the unit retries it.
        print('PASS: user unit, configured paths, DB ordering, first-run directory creation and retry after failure')
    finally:
        systemctl('stop', service, database, check=False)
        systemctl('disable', '--runtime', service, database, check=False)
        systemctl('reset-failed', service, database, check=False)
        systemctl('daemon-reload')
