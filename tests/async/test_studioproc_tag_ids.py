#!/usr/bin/env python3
"""The studio-proc tag ids keep the top of the skills[] index space to themselves.

studioproc.h's static_assert keeps them above TAG_INFO_COOLDOWN and inside skills[], but
the compiler cannot see a new #define that takes one of their numbers; this does. A tag
that reached 2198 would share its affects with the engine's per-instance state.
"""
import re

from _paths import SRC

STUDIO = {"TAG_STUDIOPROC_TRIG": 2198, "TAG_STUDIOPROC_COOLDOWN": 2199,
          "TAG_STUDIOPROC_COUNTER": 2200}

spells = (SRC / "magic" / "spells.h").read_text()
values = dict(re.findall(r"^#define\s+(\w+)\s+(\d+)\b", spells, re.M))
assert {name: int(values.get(name, -1)) for name in STUDIO} == STUDIO, values

taken = {name: value for name, value in values.items()
         if int(value) >= min(STUDIO.values()) and name not in STUDIO}
assert not taken, f"spells.h defines take the studio-proc tag ids: {taken}"

header = (SRC / "mob" / "studioproc.h").read_text()
for alias, name in (("SP_TAG_TRIG", "TAG_STUDIOPROC_TRIG"),
                    ("SP_TAG_COOLDOWN", "TAG_STUDIOPROC_COOLDOWN"),
                    ("SP_TAG_COUNTER", "TAG_STUDIOPROC_COUNTER")):
    assert re.search(rf"^#define {alias} {name}\b", header, re.M), alias
assert "static_assert(TAG_INFO_COOLDOWN < SP_TAG_TRIG && SP_TAG_COUNTER <= MAX_AFFECT_TYPES" in header

print("studio-proc tag ids are the only defines at 2198 and above in spells.h")
