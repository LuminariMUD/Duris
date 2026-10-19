#!/usr/bin/env python3
"""Pair existing MUD-produced fixture rows with a sibling DurisWeb checkout.

Requires the explicit disposable DB port, capture directory, built frontend,
and Chromium path. Does not read either checkout's .env or start live services.
"""
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
web = Path(os.environ['DURISWEB_ROOT']).resolve()
for name in ('TEST_PVP_DB_PORT', 'PVP_CAPTURE_COMMAND_DIR', 'PVP_WEB_DIST', 'PVP_CHROMIUM'):
    if not os.environ.get(name):
        raise SystemExit(f'{name} is required')
port = int(os.environ['TEST_PVP_DB_PORT'])
if port < 1024 or port in (3306, 3307):
    raise SystemExit('A disposable database port is required')
target = web / 'backend/src/services/__tests__/pvpMudHandoff.test.ts'
# Exclusive creation and finally cleanup preserve unrelated website work.
with target.open('x') as file:
    file.write((ROOT / 'tests/async/pvp_web_handoff.test.ts').read_text())
try:
    subprocess.run(['pnpm', '--dir', str(web / 'backend'), 'test', '--runInBand',
                    'src/services/__tests__/pvpMudHandoff.test.ts'], check=True,
                   env=dict(os.environ, NODE_ENV='test',
                            PVP_BROWSER_SCRIPT=str(ROOT / 'tests/async/pvp_web_handoff_browser.mjs')))
finally:
    target.unlink()
