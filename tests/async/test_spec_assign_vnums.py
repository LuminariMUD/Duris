#!/usr/bin/env python3
"""Every special specs.assign.c binds names an object, mob or room the world has.

real_object0(), real_mobile0() and real_room0() return index 0 for a missing vnum, so an
assignment to a vnum that left the world silently lands on object 1, mob 1 or room 0. The
world is what make_all builds: the area files areas/AREA lists, under obj/, mob/ and wld/.
"""

import re

from _paths import ROOT, SRC

AREAS = ROOT / "areas"
LOOKUPS = {"real_object0": "obj", "real_mobile0": "mob", "real_room0": "wld"}


def live_source(text: str) -> str:
    """The source with comments and #if 0 blocks blanked, line numbers kept."""
    text = re.sub(r"/\*.*?\*/", lambda match: re.sub(r"[^\n]", " ", match.group()), text,
                  flags=re.S)
    text = re.sub(r"//[^\n]*", "", text)
    lines, depth = [], 0
    for line in text.split("\n"):
        directive = line.strip()
        if depth:
            if directive.startswith("#if"):
                depth += 1
            elif directive.startswith("#endif"):
                depth -= 1
            lines.append("")
        elif directive == "#if 0":
            depth = 1
            lines.append("")
        else:
            lines.append(line)
    return "\n".join(lines)


def world_vnums() -> dict[str, set[int]]:
    vnums = {kind: set() for kind in LOOKUPS.values()}
    for line in (AREAS / "AREA").read_text(errors="replace").splitlines():
        if not line.strip() or line.startswith("*"):
            continue
        area = line.split()[0]
        for kind in vnums:
            path = AREAS / kind / f"{area}.{kind}"
            if path.is_file():
                vnums[kind].update(int(found) for found in re.findall(
                    r"^#(\d+)", path.read_text(errors="replace"), re.M))
    return vnums


source = live_source((SRC / "specs" / "specs.assign.c").read_text(errors="replace"))
world = world_vnums()
assert all(world.values()), "the area list reads no object, mob or room"

missing = []
assignments = 0
for number, line in enumerate(source.split("\n"), 1):
    for lookup, vnum in re.findall(r"\b(real_object0|real_mobile0|real_room0)\((\d+)\)", line):
        assignments += 1
        if int(vnum) not in world[LOOKUPS[lookup]]:
            missing.append(f"L{number} {lookup}({vnum})")

assert assignments > 1000, f"only {assignments} assignments were read"
assert not missing, (
    f"{len(missing)} assignment(s) in specs.assign.c name a vnum no area in areas/AREA has; "
    "they would land on index 0:\n" + "\n".join(missing))
print(f"spec assignments name existing vnums ({assignments} checked)")
