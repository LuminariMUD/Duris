#!/usr/bin/env python3
"""Every authored object reset in Ailvio's bank must resolve in the active world."""
import re
from _paths import ROOT

areas = ROOT / "areas"
active = [line.split()[0] for line in (areas / "AREA").read_text().splitlines()
          if line.strip() and not line.startswith("*")]
objects = set()
for name in active:
    path = areas / "obj" / (name + ".obj")
    objects.update(int(value) for value in re.findall(r"(?m)^#(\d+)", path.read_text()))
bank_objects = [int(obj) for obj, room in re.findall(r"(?m)^O\s+\d+\s+(\d+)\s+\d+\s+(\d+)\s", (areas / "zon/newbie.zon").read_text()) if int(room) == 29266]
assert bank_objects, "bank fixture unexpectedly has no object resets"
assert set(bank_objects) <= objects, f"bank references missing objects: {set(bank_objects) - objects}"
assert {29227, 29313, 3097} <= set(bank_objects), "bank sign, locker and working fixture must remain"
print("Ailvio bank reset references resolve in the active authored world")
