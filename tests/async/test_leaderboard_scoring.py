#!/usr/bin/env python3
"""Run the real leaderboard command and live score functions; optional disposable SQL.

Use with_disposable_mariadb.sh for SQL ranking and formatting coverage as well.
"""
import os
from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT

build = ROOT / 'bin/tests'
build.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix='leaderboard-', dir=build) as directory:
    binary = Path(directory) / 'leaderboard-scoring'
    subprocess.run([
        'g++', '-std=c++20', '-Wall', '-Wextra', '-Werror', '-ffunction-sections',
        '-fdata-sections', '-fsanitize=undefined', '-fno-sanitize-recover=all',
        '-Isrc', '-I/usr/include/mysql',
        'tests/async/leaderboard_scoring_harness.cpp', 'src/world/hardcore.c',
        'src/world/hardcore_config.c', 'src/classes/drannak.c', 'src/ships/ship_utils.c',
        'src/core/safe_format.c', '-Wl,--gc-sections', '-lmysqlclient', '-lbsd',
        '-o', str(binary),
    ], cwd=ROOT, check=True)
    subprocess.run([str(binary)], cwd=ROOT, check=True, timeout=30)
if not os.getenv('TEST_DB_HOST'):
    print('SQL checks skipped: run through tests/async/with_disposable_mariadb.sh')
