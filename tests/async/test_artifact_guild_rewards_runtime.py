#!/usr/bin/env python3
"""Live artifact/guild awards through the real capture and submission path."""
from pathlib import Path
import subprocess
import tempfile
from _paths import ROOT, HARNESS_STUBS

out = ROOT / 'bin/tests'
out.mkdir(parents=True, exist_ok=True)
# The pre-cutover boot cache is a fixture boundary, not a second implementation.
# This lets check_tests_catch run the same observable assertions on old sources.
legacy = 'bool hydrated = false;' in (ROOT / 'src/guild/artifact_guild_state.c').read_text()
with tempfile.TemporaryDirectory(prefix='artifact-rewards-', dir=out) as directory:
    binary = Path(directory) / 'runtime'
    subprocess.run([
        'g++', '-std=c++20', '-Wall', '-Wextra', '-Werror', '-pthread',
        '-fsanitize=undefined', '-ffunction-sections', '-fdata-sections',
        '-Isrc', '-I/usr/include/mysql', f'-DLEGACY_HYDRATION={int(legacy)}',
        'tests/async/artifact_guild_rewards_runtime.cpp',
        'src/guild/artifact_guild_transaction.c', 'src/guild/artifact_guild_command.c',
        'src/guild/assocs.c', 'src/core/safe_format.c', 'src/persistence/critical_command.c',
        'src/world/zone_touch_transaction.c', 'src/world/zone_touch_command.c',
        'src/world/epic_command.c',
        str(HARNESS_STUBS), '-Wl,--gc-sections', '-lcrypto', '-o', str(binary),
    ], cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True, timeout=30)
