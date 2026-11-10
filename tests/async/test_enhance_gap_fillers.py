#!/usr/bin/env python3
"""Keep the Halfway Works available only as single-slot enhancement results."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
source = (ROOT / "areas/obj/wutvr.obj").read_text(encoding="latin1")
starts = list(re.finditer(r"^#(\d+)\n", source, re.M))
vnums = [int(match[1]) for match in starts]
assert vnums == sorted(set(vnums)), "object vnums must be unique and ascending"
assert vnums[-33:] == list(range(91534, 91567))
records = {int(match[1]): source[match.end():starts[i + 1].start() if i + 1 < len(starts) else len(source)]
           for i, match in enumerate(starts)}

# Named wear bits come from the engine so a flag change cannot silently pass.
defines = (ROOT / "src/core/defines.h").read_text()
bits = {name: 1 << (int(bit) - 1) for name, bit in
        re.findall(r"^#define (ITEM_\w+) BIT_(\d+)\b", defines, re.M)}
slots = ("ARMS", "EARRING", "EYES", "EYES", "EYES", "FACE", "FEET",
         "HORN", "HORN", "HORN", "HORSE_BODY", "HORSE_BODY", "HORSE_BODY",
         *("GUILD_INSIGNIA",) * 6, "NOSE", "NOSE", *("QUIVER",) * 4,
         *("SHIELD",) * 3, *("TAIL",) * 5)
assert len(slots) == 33
for vnum, slot in zip(range(91534, 91567), slots):
    keywords, name, room, action, data = records[vnum].split("~", 4)
    assert "_noquest_" in keywords.split(), vnum
    assert name.strip() and room.strip() and not action.strip(), vnum
    lines = data.strip().splitlines()
    flags, values, physical = (list(map(int, line.split())) for line in lines[:3])
    wear = bits["ITEM_" + (slot if slot in ("HORSE_BODY", "GUILD_INSIGNIA") else "WEAR_" + slot)]
    assert len(flags) == 11 and flags[7] == bits["ITEM_TAKE"] | wear, vnum
    assert flags[6] == flags[8] == flags[9] == flags[10] == 0, vnum
    assert len(values) == 8 and values[5:] == [0, 0, 0], vnum
    assert len(physical) == 7 and physical[2:] == [100, 0, 0, 0, 0], vnum
    assert "B5" not in lines, vnum
    allowed_types = (37,) if slot == "SHIELD" else (30,) if slot == "QUIVER" else (9, 11)
    assert flags[0] in allowed_types, vnum
    assert len(re.findall(r"^E\n", data, re.M)) == 1, vnum
    applies = re.findall(r"^A\n(\d+) (-?\d+)$", data, re.M)
    assert 1 <= len(applies) <= 2, vnum
    assert all(int(location) in (1, 2, 3, 4, 5, 6, 13, 17, 20, 21, 22, 23, 24)
               for location, modifier in applies), vnum

print("33 enhancement gap fillers: ordered, single-slot, plain applies, no rewards or affects")
