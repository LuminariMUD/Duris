#!/usr/bin/env python3
"""Source contract for the early database compatibility boot gate."""

from _paths import SRC
from pathlib import Path
import os
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[2]
CYCLE = (ROOT / "scripts" / "cycle_mud.sh").read_text()
SQL_PLAYER = (SRC / "sql_player.c").read_text()

migration = 'python3 scripts/migration_runner.py run'
verification = './migrations/verify_runtime_compatibility.sh'
launch = '"$RUNTIME_BINARY" "${SERVER_ARGS[@]}" "${MUD_PORT}"'

assert 'export DB_NAME="$EFFECTIVE_DB_NAME"' in CYCLE
assert '[[ "$ENVIRONMENT" == "local" ]]' in CYCLE
assert migration in CYCLE
assert verification in CYCLE
assert CYCLE.index(migration) < CYCLE.index(launch)
assert CYCLE.index(verification) < CYCLE.index(launch)
assert "Database schema is incompatible with this server; refusing to boot" in CYCLE

restore = SQL_PLAYER[SQL_PLAYER.index("void sql_restore_saved_items(void)") :]
assert "root restore query failed; saved ground items were not loaded" in restore
assert restore.index("if (!result)") < restore.index("root restore query failed")

# A client unpacked outside the system's prefix is given its own charsets directory; one
# with no such directory beside it is called as before.
VERIFY = ROOT / "migrations" / "verify_runtime_compatibility.sh"
for relocated in (True, False):
    with tempfile.TemporaryDirectory(prefix="duris-boot-gate-") as temporary:
        prefix = Path(temporary) / "opt"
        (prefix / "bin").mkdir(parents=True)
        if relocated:
            (prefix / "share/mysql/charsets").mkdir(parents=True)
        client = prefix / "bin/mysql"
        client.write_text('#!/bin/sh\nprintf "%s\\n" "$@" >> "$CALLS"\n')
        client.chmod(0o755)
        calls = Path(temporary) / "calls"
        subprocess.run(
            ["bash", str(VERIFY)], cwd=ROOT, capture_output=True, text=True,
            env={"PATH": f"{prefix / 'bin'}:/usr/bin:/bin", "CALLS": str(calls),
                 "DB_HOST": "127.0.0.1", "DB_USER": "fixture", "DB_PASSWD": "fixture",
                 "DB_NAME": "fixture"})
        option = f"--character-sets-dir={prefix / 'share/mysql/charsets'}"
        assert (option in calls.read_text().splitlines()) == relocated, calls.read_text()
assert 'MYSQL_CONNECTION_ARGS+=(--character-sets-dir="$MYSQL_CHARSETS")' in CYCLE

print("database boot gate contract passed")
