#!/usr/bin/env python3
"""Real paid epic teacher boundaries, mastery feedback and refresh ordering."""
from pathlib import Path
import re
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
help_text = (ROOT / 'help/duris_help_parsed.hlp').read_text()
cost_help = next(entry for entry in help_text.split('\n#0\n')
                 if entry.strip().splitlines()[:1] == ['Epic skill cost'])
documented = re.findall(
    r'(?m)^([^\n]+)\n  First 10%: (\d+) epics, (\d+) plat\n'
    r'  Total:     (\d+) epics, (\d+) plat', cost_help)
active_source = re.sub(r'/\*.*?\*/|//[^\n]*', '', source, flags=re.S)
names = dict(re.findall(r'SKILL_CREATE\("([^"]+)",\s*(SKILL_\w+)', active_source))
reward_ids = re.findall(r'\{\s*EPIC_REWARD_SKILL,\s*(SKILL_\w+),', active_source)
assert len(documented) == len(reward_ids) == len({row[0].lower() for row in documented})
assert {names[row[0].lower()] for row in documented} == set(reward_ids)
assert [row[0].lower() for row in documented] == sorted(row[0].lower() for row in documented)
cost_checks = '\n'.join(
    f'documented_cost({names[name.lower()]}, "{name.lower()}", {", ".join(values)});'
    for name, *values in documented)
properties = dict(re.findall(r'(?m)^(epic\.[\w.]+)=([\d.]+)',
                             (ROOT / 'lib/duris.properties').read_text()))
property_checks = '\n'.join(
    f'if (std::string(key) == "{key}") return {int(float(properties[key]))};'
    for key in ('epic.progressFactor', 'epic.skillGain',
                'epic.multiclass.EpicSkillCost', 'epic.multiclass.EpicPlatCost'))
harness = (ROOT / 'tests/async/epic_training.cpp').read_text().replace('// PRODUCTION', production)
harness = harness.replace('// DOCUMENTED_COSTS', cost_checks)
harness = harness.replace('// TRAINING_PROPERTIES', property_checks)
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
    for mode in ('boundaries', 'mastery', 'refresh', 'costs'):
        subprocess.run([str(binary), mode], check=True, timeout=30)
