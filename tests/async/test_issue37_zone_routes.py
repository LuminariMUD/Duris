#!/usr/bin/env python3
"""Authored/generated contracts for the current surface placements and issue #37 trail."""
import argparse
import re
from pathlib import Path

from test_falling_world_exits import read_rooms

ROOT = Path(__file__).resolve().parents[2]
FILES = ('surface', 'otower', 'underworld3', 'arcium', 'elvish', 'willem', 'turolzoo',
         'mist_chasm', 'underdark', 'asylum')
REVERSE = (2, 3, 0, 1, 5, 4)
SURFACE_ROUTES = ((517246, 3, 85700, 1), (517645, 0, 85700, 2),
                  (548452, 0, 35800, 2), (584845, 0, 7102, 2),
                  (551667, 0, 11300, 2), (616249, 0, 9288, 2))
MARKERS = {517245: 'Arcium', 548052: 'Abandoned Elven Homestead',
           584445: 'Turopolis', 551267: 'Outcast Tower', 615849: 'Temple of Lizizania'}
# Independent acceptance path from the retained surface approach to the cliff trail.
MISTY_TRAIL = ((3, 15000), (3, 15001), (2, 15006), (2, 15007),
               (3, 15008), (3, 15009), (3, 15010), (0, 15011),
               (3, 15012), (0, 15013), (0, 15014), (3, 15015))


def load_rooms(areas, generated=False):
    if generated:
        text = (areas / 'world.wld').read_text(encoding='latin-1')
        check_markers(text)
        return read_rooms(text)
    active = {line.split()[0] for line in (areas / 'AREA').read_text().splitlines()
              if line.strip() and not line.startswith('*')}
    assert set(FILES) <= active, 'required area is not active'
    rooms = {}
    for name in FILES:
        text = (areas / 'wld' / (name + '.wld')).read_text(encoding='latin-1')
        if name == 'surface':
            check_markers(text)
        parsed = read_rooms(text)
        assert not rooms.keys() & parsed.keys(), 'duplicate route vnum'
        rooms.update(parsed)
    return rooms


def check_markers(text):
    for vnum, name in MARKERS.items():
        marker = re.search(rf'(?ms)^#{vnum}\n(.*?)~\n.*?~\n5000 (\d+) (\d+)', text)
        assert marker and marker[1] == name, (vnum, 'map label')
        assert int(marker[2]) & 134250688 == 134250688, (vnum, 'map marker flags')
        assert int(marker[3]) == 0, (vnum, 'map marker sector')
    for vnum in (516443, 546461):
        old = re.search(rf'(?ms)^#{vnum}\n(.*?)~\n.*?~\n5000 (\d+) (\d+)', text)
        assert old and int(old[2]) == 0 and int(old[3]) == 4, (vnum, 'vacated hills')
        assert not any(name in old[1] for name in MARKERS.values()), (vnum, 'stale label')


def check_routes(rooms):
    def pair(start, direction, end, reverse):
        assert start in rooms and end in rooms, (start, end, 'missing endpoint')
        assert rooms[start][2].get(direction) == end, (start, direction, end)
        assert rooms[end][2].get(reverse) == start, (end, reverse, start)

    for route in SURFACE_ROUTES:
        pair(*route)
    pair(11348, 0, 30172, 2)
    pair(7123, 3, 53000, 1)
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
    # Vacated markers become ordinary hills with reciprocal grid travel.
    for footprint in (516443, 546461, 591772):
        assert rooms[footprint][:2] == (4, 0), rooms[footprint]
        for direction, offset in enumerate((-400, 1, 400, -1)):
            pair(footprint, direction, footprint + offset, REVERSE[direction])
    # A map marker names a zone; movement must enter its actual first room.
    assert not [(v, d, target) for v, (_, _, exits) in rooms.items()
                for d, target in exits.items() if target in MARKERS], 'marker is walkable'
    for entrance in {route[2] for route in SURFACE_ROUTES}:
        expected = sorted((v, d) for v, d, target, _ in SURFACE_ROUTES if target == entrance)
        actual = sorted((v, d) for v, (_, _, exits) in rooms.items() for d, target in exits.items()
                        if 500000 <= v < 660000 and target == entrance)
        assert actual == expected, (entrance, 'superseded surface entrance', actual)
    assert 1 not in rooms[35800][2], 'Homestead still exits east to Arcium'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--areas', type=Path, default=ROOT / 'areas')
    parser.add_argument('--generated', action='store_true')
    args = parser.parse_args()
    rooms = load_rooms(args.areas, args.generated)
    check_routes(rooms)
    # Disposable in-memory fixture proves the return edge is an independent gate.
    for room, direction in [(target, reverse) for _, _, target, reverse in SURFACE_ROUTES] + [(834025, 4)]:
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
    print('Zone route contracts passed; all six broken surface returns rejected.')
