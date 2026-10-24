#!/usr/bin/env python3
"""Every tutorial spell-up must bind a real caster of each supported family."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
assignments = (ROOT / 'src/specs/specs.assign.c').read_text()
bound = {int(vnum) for vnum in re.findall(
    r'mob_index\[real_mobile0\((\d+)\)\]\.func\.mob\s*=\s*newbie_spellup_mob;', assignments)}
# The authored mobile header stores a class bitmask: Cleric, Druid, Shaman, Sorcerer.
families = {32, 128, 256, 512}
for name, first in (('newbie', 29200), ('wutvr', 91400)):
    path = ROOT / f'areas/mob/{name}.mob'
    if not path.exists():
        assert name == 'wutvr'  # The evil copy is delivered by its feature stack.
        continue
    records = {int(match[1]): match[0] for match in re.finditer(
        r'(?ms)^#(\d+)\n.*?(?=^#|\Z)', path.read_text())}
    selected = bound.intersection(range(first, first + 200))
    assert len(selected) == 4, (name, selected)
    covered = set()
    for vnum in selected:
        # Four tilde-terminated strings, flags line, then race/spec/class data.
        header = records[vnum].split('~', 4)[4].strip().splitlines()
        class_mask = int(header[1].split()[2])
        supported = {family for family in families if class_mask & family}
        assert supported, f'{name} spell-up {vnum} has no supported caster class'
        covered.update(supported)
    assert covered == families, (name, covered)
print('all tutorial spell-up bindings cover real cleric/druid/shaman/sorcerer casters')
