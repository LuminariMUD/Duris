#!/usr/bin/env python3
"""Authored area data must name races and quest rewards that exist (issue #1021).

A mobile whose race code is not in race_names_table loads with no race, and a
quest whose reward object is gone took the player's item for nothing.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AREAS = ROOT / "areas"
# Creatures deliberately authored with the unlisted code "O": they have no race.
RACELESS = {20305, 26100, 51800, 52200}

zones = [line.split()[0] for line in (AREAS / "AREA").read_text().splitlines()
         if line.strip() and not line.startswith("*")]
codes = {code.upper() for code in re.findall(
    r'\{ "[^"]*", "[^"]*", "[^"]*", "(\w+)" \}', (ROOT / "src/core/common.c").read_text())} - {"NO"}
assert len(codes) > 90, codes

unknown = []
for zone in zones:
    path = AREAS / "mob" / (zone + ".mob")
    if not path.exists():
        continue
    lines = path.read_text(encoding="latin-1").split("\n")
    vnum = None
    for number, line in enumerate(lines):
        header = re.fullmatch(r"#(\d+)\s*", line)
        if header:
            vnum = int(header[1])
        elif re.fullmatch(r"-?\d+( -?\d+){8} S\s*", line):
            code = lines[number + 1].split()[0]
            if code.upper() not in codes and vnum not in RACELESS:
                unknown.append(f"{path.name} #{vnum}: race code {code!r}")
assert not unknown, "mobiles with a race code the server does not know:\n" + "\n".join(unknown)

# Lancer's snake-necklace quest pays the glowing white rod.
objects = set()
for path in (AREAS / "obj").glob("*.obj"):
    objects.update(int(vnum) for vnum in re.findall(r"^#(\d+)\s*$", path.read_text(encoding="latin-1"), re.M))
lancer = (AREAS / "qst/wh.qst").read_text(encoding="latin-1").split("#55151\n")[1].split("\nS\n")[0]
assert "R I 33719\nG I 15012\n" in lancer
assert {33719, 15012} <= objects

print("area race codes and Lancer's quest reward resolve")
