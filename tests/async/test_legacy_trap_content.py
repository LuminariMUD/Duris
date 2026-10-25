#!/usr/bin/env python3
"""Independently inspect AREA-selected authored objects and optional generated objects."""
from pathlib import Path
import argparse
import re

from _paths import ROOT
from legacy_trap_manifest import TRAPS, CONTAINERS


def selected_inputs():
    directory = ROOT / "areas/obj"
    for line in (ROOT / "areas/AREA").read_text().splitlines():
        if not line.strip() or line.startswith("*"):
            continue
        name = line.split()[0] + ".obj"
        exact = directory / name
        if exact.is_file():
            yield exact
        else:
            matches = [p for p in directory.iterdir() if p.is_file() and p.name.lower() == name.lower()]
            assert len(matches) == 1, (name, matches)
            yield matches[0]


def parse_objects(text):
    """Skip framed strings before interpreting metadata, including extra descriptions."""
    records = {}
    markers = list(re.finditer(r"(?m)^#(\d+)[ \t]*$", text))
    for index, marker in enumerate(markers):
        vnum = int(marker[1])
        if vnum == 9999999:
            continue
        end = markers[index + 1].start() if index + 1 < len(markers) else len(text)
        body = text[marker.end():end].lstrip()
        offset = 0
        for _ in range(4):
            terminator = re.search(r"~[ \t]*$", body[offset:], re.MULTILINE)
            assert terminator, (vnum, "unterminated string")
            offset += terminator.end()
        rows = body[offset:].lstrip().splitlines()
        kind = int(rows[0].split()[0])
        values = tuple(map(int, rows[1].split()))
        cursor, trap = 3, None
        while cursor < len(rows):
            field = rows[cursor].strip()
            cursor += 1
            # The loader tolerates legacy surplus string terminators between records.
            if not field or field == "~":
                continue
            if field == "E":
                for _ in range(2):
                    while not rows[cursor].rstrip().endswith("~"):
                        cursor += 1
                    cursor += 1
            elif field == "A":
                cursor += 1
            elif field == "T":
                assert trap is None, (vnum, "duplicate T")
                trap = tuple(map(int, rows[cursor].split()))
                assert len(trap) == 4, (vnum, trap)
                cursor += 1
            else:
                # Like the template loader, stop at unrecognized trailing metadata.
                break
        assert vnum not in records, (vnum, "duplicate object")
        records[vnum] = (kind, values, trap)
    return records


def check(records):
    for vnum, (_, _, final) in TRAPS.items():
        assert vnum in records, (vnum, "missing object")
        assert records[vnum][2] == final, (vnum, records[vnum][2], final)
    for vnum, (_, final_flags) in CONTAINERS.items():
        kind, values, _ = records[vnum]
        assert kind == 15 and values[1] == final_flags, (vnum, kind, values)
        assert not (values[1] & 8), (vnum, "unexpected lock")
    restored = {vnum for vnum, (_, _, trap) in records.items() if trap and 9 <= trap[1] <= 16}
    assert restored == {vnum for vnum, (_, _, final) in TRAPS.items() if final is not None}
    profiles = {41361: 10, 42290: 10, 32820: 11, 32870: 11, 32835: 11, 32846: 11, 41927: 11}
    assert {vnum: trap[1] for vnum, (_, _, trap) in records.items() if trap and trap[1] in (10, 11)} == profiles
    for vnum, (_, _, trap) in records.items():
        if not trap:
            continue
        effect, kind, _, level = trap
        assert 0 <= kind <= 16, (vnum, "unsupported effect", trap)
        if kind >= 9:
            assert level >= 0, (vnum, "negative level", trap)
            assert not (effect & 504) or effect & 1, (vnum, "orphan direction", trap)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generated", type=Path, help="also verify this generated world.obj")
    arguments = parser.parse_args()
    authored = {}
    for path in selected_inputs():
        records = parse_objects(path.read_text(encoding="latin1"))
        overlap = authored.keys() & records.keys()
        assert not overlap, (path, "duplicate active vnums", overlap)
        authored.update(records)
    check(authored)
    if arguments.generated:
        generated = parse_objects(arguments.generated.read_text(encoding="latin1"))
        check(generated)
        for vnum in TRAPS:
            assert generated[vnum] == authored[vnum], (vnum, "generated/authored mismatch")
    print("legacy trap content: all 61 resolutions, seven profiles and four containers passed")


if __name__ == "__main__":
    main()
