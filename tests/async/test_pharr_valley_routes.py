#!/usr/bin/env python3
"""Pharr Valley has a two-way, connected land route from the surface world."""
import argparse
from collections import deque
from pathlib import Path

from test_falling_world_exits import read_rooms

ROOT = Path(__file__).resolve().parents[2]
AREAS = ('surface', 'valley_crushk', 'pharrvly', 'pods')
# (from room, outgoing direction, destination, return direction)
CROSS_ZONE = ((548133, 0, 2060, 2),
              (2006, 1, 40300, 3),
              (40389, 1, 28500, 3))


def one_room(text, vnum):
    """Isolate one huge surface record, avoiding a full surface parse in the fast gate."""
    header = f'#{vnum}\n'
    start = 0 if text.startswith(header) else text.find('\n' + header) + 1
    assert start >= 0 and text[start:].startswith(header), (vnum, 'room missing')
    end = text.find('\n#', start + len(header))
    return text[start:end if end >= 0 else len(text)] + '\n'


def load_rooms(areas, generated=False):
    active = {line.split()[0] for line in (areas / 'AREA').read_text().splitlines()
              if line.strip() and not line.startswith('*')}
    assert set(AREAS) <= active, 'Pharr access areas are not all active'
    if generated:
        return read_rooms((areas / 'world.wld').read_text(encoding='latin-1'))
    surface = (areas / 'wld/surface.wld').read_text(encoding='latin-1')
    rooms = read_rooms(one_room(surface, 548133) + one_room(surface, 547733))
    for name in AREAS[1:]:
        parsed = read_rooms((areas / 'wld' / f'{name}.wld').read_text(encoding='latin-1'))
        assert not rooms.keys() & parsed.keys(), (name, 'duplicate room')
        rooms.update(parsed)
    return rooms


def reachable(rooms, origin, goal):
    """Check authored connectivity, not whether closed scripted doors are open."""
    seen, pending = {origin}, deque([origin])
    while pending:
        for target in rooms[pending.popleft()][2].values():
            if target == goal:
                return True
            if target in rooms and target not in seen:
                seen.add(target)
                pending.append(target)
    return False


def check_routes(rooms):
    for start, direction, end, reverse in CROSS_ZONE:
        assert start in rooms and end in rooms, (start, end, 'missing room')
        assert rooms[start][2].get(direction) == end, (start, direction, end)
        assert rooms[end][2].get(reverse) == start, (end, reverse, start)
    assert rooms[548133][:2] == (1, 0), 'stone highway terrain changed'
    assert rooms[547733][2].get(2) == 548133, 'Pharr Mountains marker south edge changed'
    for target in (40300, 28500):
        assert reachable(rooms, 548133, target), (target, 'not reachable from surface')
        assert reachable(rooms, target, 548133), (target, 'cannot return to surface')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--areas', type=Path, default=ROOT / 'areas')
    parser.add_argument('--generated', action='store_true')
    args = parser.parse_args()
    rooms = load_rooms(args.areas, args.generated)
    check_routes(rooms)
    # A broken return edge must fail the test rather than allowing one-way travel.
    for start, direction, _, _ in CROSS_ZONE:
        sector, fall, exits = rooms[start]
        rooms[start] = (sector, fall, {d: target for d, target in exits.items()
                                       if d != direction})
        try:
            check_routes(rooms)
        except AssertionError:
            pass
        else:
            raise AssertionError(f'broken approach {start}/{direction} was accepted')
        rooms[start] = (sector, fall, exits)
    print('Pharr Valley: reciprocal surface, valley and swamp routes passed.')
