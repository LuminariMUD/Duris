#!/usr/bin/env python3
"""Issue #610 surface markers, Temple relocation and preserved Meopham access."""
import argparse
import re
from pathlib import Path

from test_falling_world_exits import read_rooms
from test_lylr_meopham_routes import check as check_lylr_routes, extract

ROOT = Path(__file__).resolve().parents[2]
# Marker, label, surface approach, direction into zone, target, approach terrain.
ENTRANCES = (
    (557270, 'Caves of Mt. Skelenak', 557269, 1, 4125, 4),
    (557276, 'Caves of Mt. Skelenak', 556876, 2, 4131, 11),
    (543261, 'Kimordril', 543661, 0, 95658, 4),
    (541276, 'Lylrstas', 540876, 2, 82200, 2),
    (537888, 'Northern Lakes and Settlements', 537889, 3, 75337, 7),
    (612285, "Gorblaat's Cave", 612685, 0, 97900, 4),
    (547733, 'Valley of Crushk', 548133, 0, 2060, 1),
    (554129, 'The Temple of the Sun', 554128, 1, 82493, 3),
)
REVERSE = (2, 3, 0, 1, 5, 4)
MARKER_FLAGS = 134250688


def load(areas, generated=False):
    if generated:
        paths = [areas / 'world.wld']
    else:
        active = [line.split()[0] for line in (areas / 'AREA').read_text().splitlines()
                  if line.strip() and not line.startswith('*')]
        assert {'surface', 'suntmpl', 'lylr', 'caves_skelenak', 'kimordril', 'nlakes',
                'surfacemini', 'valley_crushk', 'marigot'} <= set(active)
        paths = [areas / 'wld' / f'{name}.wld' for name in active]
    rooms, records = {}, {}
    for path in paths:
        text = path.read_text(encoding='latin-1')
        parsed = read_rooms(text)
        rooms.update(parsed)
        if generated or path.name == 'surface.wld':
            records = {entry[0]: extract(text, entry[0]) for entry in ENTRANCES}
    return rooms, records


def check(rooms, records):
    markers = {entry[0] for entry in ENTRANCES}
    for marker, label, approach, direction, target, terrain in ENTRANCES:
        record = records[marker]
        assert record.startswith(f'#{marker}\n{label}~\n'), (marker, 'map label')
        header = re.search(r'^5000 (\d+) (\d+)(?: 0)?$', record, re.M)
        assert header and int(header[1]) & MARKER_FLAGS == MARKER_FLAGS, (
            marker, 'map marker flags')
        assert int(header[2]) == 0 and rooms[marker][:2] == (0, 0), (
            marker, 'map marker sector/fall')
        assert rooms[approach][:2] == (terrain, 0), (approach, 'approach terrain')
        assert rooms[approach][2].get(direction) == target, (approach, 'zone entrance')
        assert rooms[target][2].get(REVERSE[direction]) == approach, (
            target, 'zone return')
    incoming = [(room, direction, target)
                for room, (_, _, exits) in rooms.items()
                for direction, target in exits.items() if target in markers]
    assert not incoming, ('marker is walkable', incoming)
    # The old Temple approach stays forest, without entering the Lylrstas marker.
    assert rooms[541275][:2] == (3, 0)
    assert rooms[541275][2] == {0: 540875, 2: 541675, 3: 541274}
    temple_entrances = [(room, direction)
                        for room, (_, _, exits) in rooms.items()
                        for direction, target in exits.items()
                        if 500000 <= room < 660000 and target == 82493]
    assert temple_entrances == [(554128, 1)], temple_entrances
    assert rooms[82493][2] == {0: 82457, 3: 554128}, 'Temple interior link changed'
    # The original Temple site remains Fort Marigot's reciprocal entrance.
    assert rooms[519317][2].get(1) == 5315
    assert rooms[5315][2].get(3) == 519317
    # Walking around the Temple footprint still connects its approach to the highway.
    for start, direction, target in ((554128, 0, 553728), (553728, 1, 553729),
                                      (553729, 1, 553730), (553730, 2, 554130),
                                      (554130, 2, 554530), (554530, 3, 554529),
                                      (554529, 3, 554528), (554528, 0, 554128)):
        assert rooms[start][2].get(direction) == target, (start, 'Temple detour')
        assert rooms[target][2].get(REVERSE[direction]) == start, (target, 'detour return')
    # Meopham placement is still undecided: preserve its existing forest path and U/D route.
    assert rooms[538881][:2] == (3, 0)
    check_lylr_routes(rooms)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--areas', type=Path, default=ROOT / 'areas')
    parser.add_argument('--generated', action='store_true')
    args = parser.parse_args()
    rooms, records = load(args.areas, args.generated)
    check(rooms, records)
    for _, _, _, direction, target, _ in ENTRANCES:
        sector, fall, exits = rooms[target]
        rooms[target] = (sector, fall, {d: t for d, t in exits.items()
                                     if d != REVERSE[direction]})
        try:
            check(rooms, records)
        except AssertionError:
            pass
        else:
            raise AssertionError(f'missing return edge not caught: {target}')
        rooms[target] = (sector, fall, exits)
    print('Eight surface markers, reciprocal routes, Temple relocation and Meopham passed.')
