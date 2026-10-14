#!/usr/bin/env python3
"""Real paid epic teacher boundaries, mastery feedback and refresh ordering."""
from pathlib import Path
import subprocess
import tempfile
from _paths import ROOT, HARNESS_STUBS, extract_function

source = (ROOT / 'src/classes/epic_skills.c').read_text()
context = source[source.index('struct epic_skill_purchase_context'):source.index('void epic_skill_purchase_committed(')]
tables = source[source.index('epic_reward epic_rewards[]'):source.index('\nnamespace', source.index('epic_reward epic_rewards[]'))]
production = '\n'.join((
    extract_function('utility.c', 'int BOUNDED(int a, int b, int c)'),
    extract_function('interp.c', 'bool is_abbrev('),
    extract_function('epic.c', 'int epic_skills_min_level()'),
    context,
    extract_function('epic_skills.c', 'void epic_skill_purchase_committed('),
    tables,
    extract_function('epic_skills.c', 'int epic_teacher('),
))
harness = (ROOT / 'tests/async/epic_training.cpp').read_text().replace('// PRODUCTION', production)
out = ROOT / 'bin/tests'; out.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix='epic-training-native-', dir=out) as directory:
    cpp, binary = Path(directory) / 'fixture.cpp', Path(directory) / 'fixture'
    cpp.write_text(harness)
    subprocess.run(['g++', '-std=c++20', '-Wall', '-Wextra', '-Werror',
                    '-ffunction-sections', '-fdata-sections', '-fsanitize=address,undefined',
                    '-g', '-Isrc', '-I/usr/include/mysql', str(cpp),
                    'src/world/epic_transaction.c', 'src/world/epic_command.c',
                    'src/persistence/critical_command.c', str(HARNESS_STUBS),
                    '-Wl,--gc-sections', '-lcrypto', '-o', str(binary)], cwd=ROOT, check=True)
    for mode in ('boundaries', 'mastery', 'refresh'):
        subprocess.run([str(binary), mode], check=True, timeout=30)
