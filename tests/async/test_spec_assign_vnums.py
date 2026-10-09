#!/usr/bin/env python3
"""Every special specs.assign.c binds names an object, mob or room the world has.

real_object0(), real_mobile0() and real_room0() return index 0 for a missing vnum, so an
assignment to a vnum that left the world silently lands on object 1, mob 1 or room 0. The
world is what make_all builds: the area files areas/AREA lists, under obj/, mob/ and wld/.
guild_guard acts only in a room its switch names, so each guard a zone loads must stand in one.
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


def listed_areas() -> list[str]:
    return [line.split()[0] for line in (AREAS / "AREA").read_text(errors="replace").splitlines()
            if line.strip() and not line.startswith("*")]


def world_vnums() -> dict[str, set[int]]:
    vnums = {kind: set() for kind in LOOKUPS.values()}
    for area in listed_areas():
        for kind in vnums:
            path = AREAS / kind / f"{area}.{kind}"
            if path.is_file():
                vnums[kind].update(int(found) for found in re.findall(
                    r"^#(\d+)", path.read_text(errors="replace"), re.M))
    return vnums


source = live_source((SRC / "specs" / "specs.assign.c").read_text(errors="replace"))
world = world_vnums()
assert all(world.values()), "the area list reads no object, mob or room"
defines = {name: int(value) for header in SRC.rglob("*.h") for name, value in re.findall(
    r"^\s*#\s*define\s+(\w+)\s+(\d+)\s*$", header.read_text(errors="replace"), re.M)}

missing = []
assignments = 0
for match in re.finditer(r"\b(real_object0|real_mobile0|real_room0)\(\s*(\w+)\s*\)", source):
    lookup, argument = match.groups()
    number = source.count("\n", 0, match.start()) + 1
    if argument in ("i", "x"):  # the claw cavern, Shaboath and squid arena loops
        continue
    assert argument.isdigit() or argument in defines, (
        f"L{number} {lookup}({argument}) is not a vnum")
    vnum = int(argument) if argument.isdigit() else defines[argument]
    assignments += 1
    if vnum not in world[LOOKUPS[lookup]]:
        missing.append(f"L{number} {lookup}({argument})")

assert assignments > 1000, f"only {assignments} assignments were read"
assert not missing, (
    f"{len(missing)} assignment(s) in specs.assign.c name a vnum no area in areas/AREA has; "
    "they would land on index 0:\n" + "\n".join(missing))
print(f"spec assignments name existing vnums ({assignments} checked)")

mobile = (SRC / "specs" / "specs.mobile.c").read_text(errors="replace")
proc = mobile[mobile.index("int guild_guard("):mobile.index("int guardian(")]
guarded_rooms = {int(room) for room in re.findall(r"\bcase (\d+):", proc)}
guards = {int(vnum) for vnum in re.findall(
    r"real_mobile0\(\s*(\d+)\s*\)\]\.func\.mob\s*=\s*guild_guard;", source)}
loads: dict[int, set[int]] = {}
for area in listed_areas():
    path = AREAS / "zon" / f"{area}.zon"
    if path.is_file():
        for mob, room in re.findall(r"^M\s+-?\d+\s+(\d+)\s+-?\d+\s+(\d+)",
                                    path.read_text(errors="replace"), re.M):
            loads.setdefault(int(mob), set()).add(int(room))
loaded = [guard for guard in guards if guard in loads]
assert len(loaded) > 10, f"only {len(loaded)} guild guards are loaded"
idle = [f"mob {guard} loads in {sorted(loads[guard])}" for guard in sorted(loaded)
        if not loads[guard] & guarded_rooms]
assert not idle, ("guild_guard has no case for any room these guards load in, so they "
                  "block nobody:\n" + "\n".join(idle))
print(f"guild guards stand in rooms guild_guard names ({len(loaded)} checked)")
