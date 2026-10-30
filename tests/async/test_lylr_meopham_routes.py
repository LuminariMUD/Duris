#!/usr/bin/env python3
"""Verify reciprocal Lylrstas/Meopham access without damaging wilderness routes."""
import argparse
from pathlib import Path
from test_falling_world_exits import read_rooms

ROOT = Path(__file__).resolve().parents[2]
IDS = (540876, 540476, 540875, 540877, 539281, 538881, 539282, 539681, 539280, 541276)
REVERSE = (2, 3, 0, 1, 5, 4)

def extract(text, number):
    marker = f'#{number}\n'
    at = 0 if text.startswith(marker) else text.find('\n' + marker) + 1
    assert at >= 0 and text[at:].startswith(marker), number
    end = text.find('\n#', at + len(marker))
    return text[at:end if end >= 0 else len(text)] + '\n'

def load(areas, generated=False):
    if generated:
        return read_rooms((areas / 'world.wld').read_text(encoding='latin-1'))
    active = {line.split()[0] for line in (areas / 'AREA').read_text().splitlines()
              if line.strip() and not line.startswith('*')}
    assert {'surface', 'lylr'} <= active
    surface = (areas / 'wld/surface.wld').read_text(encoding='latin-1')
    rooms = read_rooms(''.join(extract(surface, v) for v in IDS))
    zone = read_rooms((areas / 'wld/lylr.wld').read_text(encoding='latin-1'))
    assert not rooms.keys() & zone.keys()
    rooms.update(zone)
    return rooms

def check(rooms):
    for src, direction, target in ((540876, 2, 82200), (539281, 4, 82240)):
        assert rooms[src][2].get(direction) == target, (src, direction)
        assert rooms[target][2].get(REVERSE[direction]) == src, (target, REVERSE[direction])
    assert rooms[82240][2].get(2) == 539281
    for direction, target in enumerate((538881, 539282, 539681, 539280)):
        assert rooms[539281][2].get(direction) == target
        assert rooms[target][2].get(REVERSE[direction]) == 539281
    assert rooms[541276][:2] == (0, 0), 'marker must remain inert'
    for direction, target in ((0, 540476), (1, 540877), (3, 540875)):
        assert rooms[540876][2].get(direction) == target
    for src in IDS:
        if src != 541276:
            assert 541276 not in rooms[src][2].values(), src

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--areas', type=Path, default=ROOT / 'areas')
    parser.add_argument('--generated', action='store_true')
    args = parser.parse_args()
    rooms = load(args.areas, args.generated)
    check(rooms)
    for src, direction in ((540876, 2), (539281, 4)):
        sector, fall, exits = rooms[src]
        rooms[src] = (sector, fall, {d: target for d, target in exits.items() if d != direction})
        try:
            check(rooms)
        except AssertionError:
            pass
        else:
            raise AssertionError(f'missing entrance not caught: {src}/{direction}')
        rooms[src] = (sector, fall, exits)
    print('Lylrstas/Meopham reciprocal access and surface-grid checks passed.')
