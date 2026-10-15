#!/usr/bin/env python3
"""Authored/generated route contracts for the approved issue #37 placements."""
import argparse
from pathlib import Path

from test_falling_world_exits import read_rooms

ROOT = Path(__file__).resolve().parents[2]
FILES = ('surface', 'otower', 'underworld3', 'arcium', 'elvish', 'willem', 'turolzoo',
         'mist_chasm', 'underdark')
REVERSE = (2, 3, 0, 1, 5, 4)
# Independent acceptance path from the retained surface approach to the cliff trail.
MISTY_TRAIL = ((3, 15000), (3, 15001), (2, 15006), (2, 15007),
               (3, 15008), (3, 15009), (3, 15010), (0, 15011),
               (3, 15012), (0, 15013), (0, 15014), (3, 15015))


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
    pair(516444, 3, 85700, 1)
    pair(516843, 0, 85700, 2)
    pair(15015, 5, 834025, 4)
    current = 638825
    for direction, target in MISTY_TRAIL:
        pair(current, direction, target, REVERSE[direction])
        assert rooms[target][0] in (2, 3, 4) and rooms[target][1] == 0, target
        current = target
    pair(15015, 2, 15016, 0)
    for start, direction, target, reverse in ((834025, 0, 833625, 2),
                                             (834025, 1, 834026, 3)):
        pair(start, direction, target, reverse)
        assert rooms[target][:2] == (29, 0), target
    # Restore the vacated footprint as hills with all reciprocal grid neighbors.
    assert rooms[615849][:2] == (4, 0), rooms[615849]
    for direction, neighbor, reverse in ((0, 615449, 2), (1, 615850, 3),
                                         (2, 616249, 0), (3, 615848, 1)):
        pair(615849, direction, neighbor, reverse)
    assert not [(v, d) for v, (_, _, exits) in rooms.items()
                for d, target in exits.items() if target == 546461], 'marker is walkable'
    assert [(v, d) for v, (_, _, exits) in rooms.items() for d, target in exits.items()
            if v >= 500000 and target == 11300] == [(546861, 0)], 'superseded entrance'
    assert rooms[591772][:2] == (4, 0), rooms[591772]
    for direction, neighbor, reverse in ((0, 591372, 2), (1, 591773, 3),
                                         (2, 592172, 0), (3, 591771, 1)):
        pair(591772, direction, neighbor, reverse)
    assert not [(v, d) for v, (_, _, exits) in rooms.items()
                for d, target in exits.items() if target == 516443], 'Arcium marker is walkable'
    assert sorted((v, d) for v, (_, _, exits) in rooms.items() for d, target in exits.items()
                  if v >= 500000 and target == 85700) == [(516444, 3), (516843, 0)], 'old Arcium entrance'
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
    for room, direction in ((11300, 2), (85700, 1), (85700, 2), (834025, 4)):
        original = rooms[room]
        sector, fall, exits = original
        rooms[room] = (sector, fall, {d: v for d, v in exits.items() if d != direction})
        try:
            check_routes(rooms)
        except AssertionError:
            pass
        else:
            raise AssertionError(f'missing return edge {room}/{direction} was accepted')
        rooms[room] = original
    print('Issue #37 route contracts passed; broken return edges rejected.')
