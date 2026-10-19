#!/usr/bin/env python3
"""Exercise production SQL/flat-file news reload and stable content identity."""
from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT

build = ROOT / 'bin/tests'
build.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix='news-publication-', dir=build) as temp:
    for backend in ('mysql', 'flatfile'):
        binary = Path(temp) / backend
        flags = (['-D__NO_MYSQL__', '-Isrc/no_mysql'] if backend == 'flatfile'
                 else ['-I/usr/include/mysql'])
        subprocess.run([
            'g++', '-std=c++20', '-Wall', '-Wextra', '-Wpedantic', '-Werror',
            '-ffunction-sections', '-fdata-sections', '-Isrc', *flags,
            'tests/async/news_publication_harness.cpp', 'src/player/news.c',
            'src/flatfile/flatfile_help_catalog.c', 'src/sql/sql.c',
            '-Wl,--gc-sections', '-lcrypto', '-o', str(binary),
        ], cwd=ROOT, check=True)
        subprocess.run([str(binary), str(Path(temp) / (backend + '-root'))],
                       cwd=ROOT, check=True)
