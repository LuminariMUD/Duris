#!/usr/bin/env python3
"""Authored/generated route contracts for the approved issue #37 placements."""
import argparse
from pathlib import Path

from test_falling_world_exits import read_rooms

ROOT = Path(__file__).resolve().parents[2]
FILES = ('surface', 'otower', 'underworld3', 'elvish', 'willem', 'turolzoo')


def load_rooms(areas, generated=False):
    if generated:
        return read_rooms((areas / 'world.wld').read_text(encoding='latin-1'))
    active = {line.split()[0] for line in (areas / 'AREA').read_text().splitlines()
              if line.strip() and not line.startswith('*')}
    assert set(FILES) <= active, 'required area is not active'
    rooms = {}
    for name in FILES:
        parsed = read_rooms((areas / 'wld' / (name + '.wld')).read_text(encoding='latin-1'))
        assert not rooms.keys() & parsed.keys(), 'duplicate route vnum'
        rooms.update(parsed)
    return rooms


def check_routes(rooms):
    def pair(start, direction, end, reverse):
        assert start in rooms and end in rooms, (start, end, 'missing endpoint')
        assert rooms[start][2].get(direction) == end, (start, direction, end)
        assert rooms[end][2].get(reverse) == start, (end, reverse, start)

    pair(546861, 0, 11300, 2)
    pair(11348, 0, 30172, 2)
    # Restore the vacated footprint as hills with all reciprocal grid neighbors.
    assert rooms[615849][:2] == (4, 0), rooms[615849]
    for direction, neighbor, reverse in ((0, 615449, 2), (1, 615850, 3),
                                         (2, 616249, 0), (3, 615848, 1)):
        pair(615849, direction, neighbor, reverse)
    assert not [(v, d) for v, (_, _, exits) in rooms.items()
                for d, target in exits.items() if target == 546461], 'marker is walkable'
    assert [(v, d) for v, (_, _, exits) in rooms.items() for d, target in exits.items()
            if v >= 500000 and target == 11300] == [(546861, 0)], 'superseded entrance'
    # Explicit owner no-change decisions, including both Homestead approaches.
    for start, direction, end, reverse in ((517246, 3, 35800, 1), (517645, 0, 35800, 2),
                                          (548452, 0, 7102, 2), (7123, 3, 53000, 1)):
        pair(start, direction, end, reverse)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--areas', type=Path, default=ROOT / 'areas')
    parser.add_argument('--generated', action='store_true')
    args = parser.parse_args()
    rooms = load_rooms(args.areas, args.generated)
    check_routes(rooms)
    # Disposable in-memory fixture proves the return edge is an independent gate.
    sector, fall, exits = rooms[11300]
    rooms[11300] = (sector, fall, {d: v for d, v in exits.items() if d != 2})
    try:
        check_routes(rooms)
    except AssertionError:
        pass
    else:
        raise AssertionError('missing return edge was accepted')
    print('Issue #37 route contracts passed; broken return edge rejected.')
