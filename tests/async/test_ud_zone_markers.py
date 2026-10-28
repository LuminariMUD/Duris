#!/usr/bin/env python3
"""Underdark marker footprints and entrance routes from the October 26 report."""
import argparse
import re
from pathlib import Path

from test_falling_world_exits import read_rooms

ROOT = Path(__file__).resolve().parents[2]
# Marker, label, travel room, direction into zone, destination, terrain, area.
ENTRANCES = (
    (819888, 'Mushroom Caverns', 820288, 4, 24101, 29, 'mushroom_caverns'),
    (822268, "Pragtog's Domain", 822668, 5, 10649, 13, 'pragtog'),
    (824682, 'Mushroom Caverns', 825082, 4, 24237, 17, 'mushroom_caverns'),
    (746083, 'The Tunnels of Cyric the Destroyer', 746483, 5, 54554, 31, 'cyrictunnel'),
    (709264, 'Caves of Mt. Skelenak', 709664, 4, 4093, 29, 'caves_skelenak'),
    (856819, 'The Stone Tomb of Kelek', 857219, 5, 87950, 29, 'kelek'),
    (844448, 'The Underworld Shafts', 844848, 4, 10021, 29, 'shafts'),
    (766814, 'The Chasm of the Misty Vale', 766815, 3, 300149, 13, 'thechasmofthemistyvale'),
)
REVERSE = (2, 3, 0, 1, 5, 4)
MARKER_FLAGS = 134250688  # Existing no-recall/magic/teleport/gate footprint flags.


def check_markers(areas, generated=False):
    files = {'underdark'} | {entry[-1] for entry in ENTRANCES}
    if generated:
        paths = [areas / 'world.wld']
    else:
        active = {line.split()[0] for line in (areas / 'AREA').read_text().splitlines()
                  if line.strip() and not line.startswith('*')}
        assert files <= active, 'required area is not active'
        paths = [areas / 'wld' / (name + '.wld') for name in sorted(files)]
    rooms, records = {}, {}
    for path in paths:
        text = path.read_text(encoding='latin-1')
        parsed = read_rooms(text)
        assert not rooms.keys() & parsed.keys(), 'duplicate room vnum'
        rooms.update(parsed)
        records.update((int(vnum), body) for vnum, body in re.findall(
            r'(?ms)^#(\d+)\n(.*?)(?=^#|\Z)', text))

    markers = {entry[0] for entry in ENTRANCES}
    for marker, label, entrance, direction, target, sector, _ in ENTRANCES:
        assert marker in records, (marker, 'missing marker')
        assert records[marker].startswith(label + '~\n'), (marker, 'map label')
        assert re.search(rf'^7000 {MARKER_FLAGS} 0(?: 0)?$', records[marker], re.M), (
            marker, 'map marker flags/sector')
        assert rooms[entrance][:2] == (sector, 0), (entrance, 'changed entrance terrain')
        assert rooms[entrance][2].get(direction) == target, (entrance, 'zone entrance')
        assert rooms[target][2].get(REVERSE[direction]) == entrance, (target, 'return route')
        assert marker in (entrance - 400, entrance - 1), (marker, 'adjacent footprint')
    # The vacated marker returns to its original mountain grid footprint.
    assert rooms[834024][:2] == (27, 0)
    assert records[834024].startswith('&+LThe Massive Cavern Walls of the &+mUrusi&n~\n')
    assert not re.search(rf'^7000 {MARKER_FLAGS} 0(?: 0)?$', records[834024], re.M)
    for neighbor, direction in ((833624, 2), (834025, 3), (834424, 0), (834023, 1)):
        assert rooms[neighbor][2].get(direction) == 834024, (neighbor, 'retired marker grid return')
    assert rooms[766814][2].get(1) == 766815
    assert rooms[766814][2].get(0) == 766414
    incoming = [(vnum, direction, target)
                for vnum, (_, _, exits) in rooms.items()
                for direction, target in exits.items() if target in markers]
    assert not incoming, ('marker is walkable', incoming)
    # The shaft remains a falling passage and the pool remains water.
    assert rooms[10021][:2] == (18, 60), 'shaft fall changed'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--areas', type=Path, default=ROOT / 'areas')
    parser.add_argument('--generated', action='store_true')
    args = parser.parse_args()
    check_markers(args.areas, args.generated)
    print('All eight UD markers, reciprocal entrances, terrain and shaft fall passed.')
