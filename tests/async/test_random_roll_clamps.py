#!/usr/bin/env python3
"""MIN and MAX are macros that roll twice, so a random argument can escape their limit."""
import re
from _paths import ROOT

# A later clamp or the other argument keeps these in range, or fixing them is a balance change.
ALLOWED = {
    ('src/combat/fight.c', 'number(1, learnedvictim)'),
    ('src/combat/fight.c', 'number(1, learnedattacker)'),
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
print('PASS random rolls keep their MIN/MAX limits')
