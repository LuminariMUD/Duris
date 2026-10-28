#!/usr/bin/env python3
"""Contract checks for the five durable local drug-dealer shop identities."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HEAVENS = ROOT / "areas/shp/heavens.shp"
END = ROOT / "areas/shp/end.shp"
AREA = ROOT / "areas/AREA"
DB = (ROOT / "src/world/db.c").read_text()
SINGLETONS = (ROOT / "src/world/world_singletons.c").read_text()
SHOP_SOURCE = (ROOT / "src/economy/shop.c").read_text()


def parse_records(path: Path) -> list[list[str]]:
    lines = path.read_text().splitlines()
    records = []
    index = 0
    while index < len(lines):
        if not lines[index].startswith("#"):
            index += 1
            continue
        end = index + 1
        while end < len(lines) and lines[end] != "X":
            end += 1
        assert end < len(lines), f"unterminated shop record in {path}"
        records.append(lines[index : end + 1])
        index = end + 1
    return records


# Shop identity is positional and durable. Migration 0053 explicitly reindexes
# shops after the Misty Vale insertion; the catalog before end.shp is now 0..540.
# test_misty_vale_shop_migration.py checks the complete migration mapping.
stable_records = []
for line in AREA.read_text().splitlines():
    stripped = line.strip()
    if not stripped or stripped.startswith("*"):
        continue
    area = stripped.split()[0]
    if area == "end":
        break
    path = ROOT / f"areas/shp/{area}.shp"
    if path.exists():
        stable_records.extend(parse_records(path))

assert len(stable_records) == 541, "existing durable shop IDs were renumbered"
assert len(parse_records(HEAVENS)) == 1
# Later shops may follow these four durable identities without renumbering them.
appended_records = parse_records(END)[:4]
assert len(appended_records) == 4

# The runtime fallback uses a lexical glob rather than AREA order. It must also
# keep the sentinel file last so these additions cannot shift an old identity.
fallback_records = []
for path in sorted((ROOT / "areas/shp").glob("*.shp")):
    if path != END:
        fallback_records.extend(parse_records(path))
# The legacy glob includes orphaned source files that AREA intentionally omits,
# so its catalog is larger; with Misty Vale its 0..720 IDs stay ahead of the
# four appended records just as canonical 0..540 do.
assert len(fallback_records) == 721
assert list(range(len(fallback_records), len(fallback_records) + 4)) == [721, 722, 723, 724]
assert [record[0] for record in appended_records] == [
    "#101-room-36329~",
    "#101-room-37718~",
    "#101-room-97685~",
    "#101-room-132767~",
]

records = [parse_records(HEAVENS)[0], *appended_records]
local_shop_ids = [0, *range(len(stable_records), len(stable_records) + 4)]
assert local_shop_ids == [0, 541, 542, 543, 544]

assert len(records) == 5, f"expected five local dealer records, found {len(records)}"
rooms = ["23", "36329", "37718", "97685", "132767"]
products = [str(vnum) for vnum in range(829, 839)]
for index, (record, room) in enumerate(zip(records, rooms)):
    assert record[1] == "N"
    assert record[2:12] == products, record[:12]
    assert record[29] == "101", record[29:37]
    assert record[31] == room, record[29:37]
    # Preserve durable shop 0's historical roaming contract so an old snapshot
    # from any valid room remains loadable; the appended identities are fixed.
    assert record[36] == ("Y" if index == 0 else "N"), record[29:39]
    assert record[37] == "Y" and record[38] == "N"

template = records[0][1:].copy()
template[35] = "N"
for record in records[1:]:
    normalized = record[1:].copy()
    normalized[30] = "23"
    normalized[35] = "N"
    assert normalized == template, "local dealer records must differ only by identity and room"

assert "static int configured_shopkeeper_for_room" in DB
assert "configured_shopkeeper_for_room(ZCMD.arg1, ZCMD.arg3)" in DB
assert "static bool live_shopkeeper_for_identity" in DB
assert "!live_shopkeepers(shop).empty()" in DB
assert "live_shopkeeper_for_identity(configured_shop)" in DB
assert "bind_shopkeeper(mob, configured_shop)" in DB
assert "is_replicated_shop(configured_shop)" in DB
assert "bool is_replicated_shop(int shop)" in SINGLETONS
assert "SET_BIT(keeper->specials.act, ACT_SENTINEL)" in SINGLETONS
assert "read_mobile(shop_index[shop].keeper, REAL)" in SINGLETONS
assert "place_replicated_shop_at_home(keeper, shop)" in SINGLETONS
assert "char_to_room(keeper, home, -2)" in SINGLETONS
assert "char_in_list(keeper)" in SINGLETONS
assert "saved.insert(shop)" in SINGLETONS
assert 'FILE *end = fopen("areas/shp/end.shp", "r")' in SHOP_SOURCE

print("Issue 552 local shop identity contract passed")
