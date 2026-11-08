#!/usr/bin/env python3
"""MIN and MAX are macros that roll twice, so a random argument can escape their limit."""
from pathlib import Path
import re
import subprocess
import tempfile
from _paths import ROOT, extract_function

# A later clamp or the other argument keeps these in range.
ALLOWED = {
    ('src/magic/magic.c', 'number(mlvl, mlvl * 3)'),
    ('src/item/random_equipment.c', 'number(0, 20)'),
    ('src/world/events.c', 'number(0, 1)'),
}


def strip_comments(text):
    text = re.sub(r'/\*.*?\*/', ' ', text, flags=re.S)
    return re.sub(r'//[^\n]*', '', text)


found = []
for path in (ROOT / 'src').rglob('*'):
    if path.suffix not in {'.c', '.h', '.cc', '.cpp'}:
        continue
    text = strip_comments(path.read_text(errors='replace'))
    for match in re.finditer(r'\b(?:MIN|MAX)\s*\(', text):
        end, depth = match.end(), 1
        while depth:
            depth += (text[end] == '(') - (text[end] == ')')
            end += 1
        arguments = ' '.join(text[match.end():end - 1].split())
        roll = re.search(r'\b(?:number|dice)\s*\([^()]*(?:\([^()]*\)[^()]*)*\)', arguments)
        if roll and '"' not in arguments:
            found.append((str(path.relative_to(ROOT)), roll.group()))

unexpected = [site for site in found if site not in ALLOWED]
assert not unexpected, f'random roll inside MIN/MAX: {unexpected}'

# Parry rolled once must give every value exactly as often as the old double roll did.
harness = r'''
#include <cassert>
#include <cstdio>
#include <map>
static int scripted, draws;
static int number(int from, int to) {
    assert(from == 1 && to >= scripted && scripted >= 1);
    ++draws;
    return scripted;
}
''' + extract_function('combat/fight.c', 'static int parry_roll(') + r'''
int main() {
    for (int learned = 1; learned <= 500; ++learned) {
        std::map<int, long> before, after;
        for (int first = 1; first <= learned; ++first)
            for (int second = 1; second <= learned; ++second)
                ++before[first < 5 ? 5 : second];
        if (learned < 5) {
            draws = 0;
            after[parry_roll(learned)] = learned * learned;
            assert(!draws);
        } else {
            for (scripted = 1; scripted <= learned * learned; ++scripted) {
                draws = 0;
                ++after[parry_roll(learned)];
                assert(draws == 1);
            }
        }
        assert(before == after);
    }
}
'''
build = ROOT / 'bin/tests'
build.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix='parry-roll-', dir=build) as directory:
    source, binary = Path(directory) / 'test.cpp', Path(directory) / 'test'
    source.write_text(harness)
    subprocess.run(['g++', '-std=c++20', '-O1', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', str(source), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True, timeout=120)
print('PASS random rolls keep their MIN/MAX limits and parry odds are unchanged')
