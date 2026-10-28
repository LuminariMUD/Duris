#!/usr/bin/env python3
"""Authored Misty Vale integration, reset, quest and equipment regressions."""
from collections import Counter, deque
from pathlib import Path
import re

from test_falling_world_exits import read_rooms

ROOT = Path(__file__).resolve().parents[2]
NAME = 'thechasmofthemistyvale'


def records(path):
    return {int(m[1]): m[2] for m in re.finditer(
        r'(?ms)^#(\d+)\n(.*?)(?=^#|\Z)', path.read_text(encoding='latin1'))}


def objects(path):
    return {v: [list(map(int, line.split())) for line in text.split('~')[4].strip().splitlines()[:3]]
            for v, text in records(path).items()}


def check():
    areas = ROOT / 'areas'
    rooms = read_rooms((areas / f'wld/{NAME}.wld').read_text())
    mobs = records(areas / f'mob/{NAME}.mob')
    objs = objects(areas / f'obj/{NAME}.obj')
    assert set(rooms) == set(range(300000, 300167))
    # Reconciled author flags: these rooms must not accept wandering mobiles.
    authored = records(areas / f'wld/{NAME}.wld')
    for vnum in (300011, 300039, 300152):
        flags = re.search(r'(?m)^3000 (\d+) \d+', authored[vnum])
        assert flags and int(flags[1]) & 4, (vnum, 'ROOM_NO_MOB flag lost')
    assert set(mobs) == set(range(300000, 300038))
    assert {'gynaeros', 'shaman'} <= set(mobs[300006].split('~')[0].split()), (
        'Gynaeros must be targetable by her displayed name and role')
    assert set(objs) == set(range(300000, 300042))
    for ext in ('wld', 'zon', 'qst'):
        assert not (areas / ext / f'mist_chasm.{ext}').read_text().strip()
    # Retired prototype IDs must remain loadable for saved inventory/pets.
    assert 15012 in objects(areas / 'obj/mist_chasm.obj')
    assert 15000 in records(areas / 'mob/mist_chasm.mob')
    active = [line.split()[0] for line in (areas / 'AREA').read_text().splitlines()
              if line.strip() and not line.startswith('*')]
    assert active.count(NAME) == active.count('mist_chasm') == 1
    active_ids = {}
    for ext in ('wld', 'mob', 'obj', 'zon'):
        active_ids[ext] = set()
        for name in active:
            path = areas / ext / f'{name}.{ext}'
            if not path.exists():
                path = next(p for p in (areas / ext).iterdir() if p.name.lower() == path.name.lower())
            text = path.read_text(encoding='latin1')
            if name != NAME:
                allocation = r'(?m)^#300[01]\b' if ext == 'zon' else r'(?m)^#300[01]\d\d\b'
                assert not re.search(allocation, text), path
            active_ids[ext].update(map(int, re.findall(r'(?m)^#(\d+)\b', text)))
            if ext == 'wld':
                for vnum, (_, _, exits) in read_rooms(text).items():
                    assert not any(15000 <= target <= 15099 for target in exits.values()), (
                        name, vnum, 'exit into retired Misty Chasm')
    for vnum, (_, _, exits) in rooms.items():
        assert set(exits.values()) <= active_ids['wld'], (vnum, 'dangling exit')

    # Every authored room is reachable when the zone's switches and portals work.
    edges = {v: set(exits.values()) & rooms.keys() for v, (_, _, exits) in rooms.items()}
    resets = [line.split('*')[0].split() for line in
              (areas / f'zon/{NAME}.zon').read_text().splitlines()
              if re.match(r'^[MFOGEPD] ', line)]
    mob_counts = Counter(int(row[2]) for row in resets if row[0] in ('M', 'F'))
    item_counts = Counter(int(row[2]) for row in resets if row[0] in ('O', 'G', 'E', 'P'))
    for row in resets:
        kind, _, a, cap, location = row[:5]
        a, cap, location = map(int, (a, cap, location))
        if kind in ('M', 'F'):
            assert a in mobs and location in rooms
            assert cap >= mob_counts[a], (a, 'global mobile cap suppresses authored spawns')
        elif kind in ('O', 'G', 'E', 'P'):
            assert a in objs or a in (15010, 15012), a
            assert cap >= item_counts[a], (a, 'global item cap suppresses authored drops')
            if kind == 'O':
                assert location in rooms
                if a in objs and objs[a][0][0] == 25:
                    target = objs[a][1][0]
                    if target in rooms:
                        edges[location].add(target)
            if kind == 'E':
                # The supplied necklace had TAKE only despite a neck equip reset.
                assert objs[a][0][7] & {3: 4, 16: 8192, 20: 262144}[location]
        elif kind == 'D':
            assert a in rooms and cap in rooms[a][2], (a, cap, 'reset of missing exit')
    seen, pending = {300000}, deque([300000])
    while pending:
        for target in edges[pending.popleft()] - seen:
            seen.add(target)
            pending.append(target)
    assert seen == rooms.keys(), ('unreachable', rooms.keys() - seen)
    for v, data in objs.items():
        kind = data[0][0]
        if kind == 25:
            assert data[1][0] in rooms or data[1][0] == 96821, v
            assert not data[0][7] & 1, (v, 'fixed landscape portal is portable')
        elif kind == 29:
            assert data[1][1] in rooms and data[1][2] in rooms[data[1][1]][2], v
    assert objs[300028][0][6] & 8192, 'pond entrance must not sink out of sight'
    assert objs[300035][0][7] == 9, 'tunic must fit the torso'
    assert objs[300038][0][0] == 22, 'canoe must provide ordinary boat travel'
    assert objs[300039][2][2] == 100, 'tackle shop fishing rod must be sold undamaged'
    well = objects(areas / 'obj/dirkn.obj')[96824]
    assert well[0][0] == 25 and well[1][:3] == [300166, 7, -1]
    quests = records(areas / f'qst/{NAME}.qst')
    assert quests.keys() <= mobs.keys()
    for vnum, quest in quests.items():
        references = set(map(int, re.findall(r'(?m)^[GR] I (\d+)$', quest)))
        assert references <= active_ids['obj'], (vnum, 'missing quest ingredient/reward')
    warrior = re.split(r'(?m)^QA?\n', quests[300003])[1:]
    assert len(warrior) == 2
    assert [re.findall(r'(?m)^G I (\d+)$', q) for q in warrior] == [['300001'], ['300024']]
    weaver = re.split(r'(?m)^QA?\n', quests[300034])[1:]
    assert len(weaver) == 5
    assert sorted(int(v) for q in weaver for v in re.findall(r'(?m)^R I (\d+)$', q)) == [300023, 300025, 300034, 300035, 300040]
    assert all('\nD\n' in q for q in weaver), 'authored crafting disappearance is preserved'
    hermit = records(areas / 'qst/surfacemini.qst')[97901]
    assert 'G I 15008\n' in hermit and 'G I 300036\n' in hermit
    assert 'G I 15012\n' in (areas / 'qst/wh.qst').read_text()
    print('Misty Vale: unique VNUMs, 167 reachable rooms, reset populations, portals, recipes and equipment passed.')


if __name__ == '__main__':
    check()
