#!/usr/bin/env python3
"""Authored area data must name races and quest items that exist (issue #1021).

A mobile whose race code is not in race_names_table loads with no race. A quest
that pays an object which is gone took the player's item for nothing, and
object numbers left stale by a renumbering make a quest take the wrong things.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AREAS = ROOT / "areas"
# Creatures deliberately authored with the unlisted code "O": they have no race.
RACELESS = {20305, 26100, 51800, 52200}
# Quest references to objects that have never existed in this repository, as
# (quest mobile, G for given or R for reward, object). The quest giver refuses
# these hand-ins. Shrink this list; never add a reference a change has broken.
NEVER_EXISTED = {
    (17, "R", 0), (17, "G", 0), (4224, "R", 35708), (13030, "G", 0), (24021, "G", 1515),
    (27082, "R", 25000), (66017, "G", 4372), (74250, "G", 0),
}

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

names = {}
for path in (AREAS / "obj").glob("*.obj"):
    lines = path.read_text(encoding="latin-1").split("\n")
    for number, line in enumerate(lines[:-2]):
        header = re.fullmatch(r"#(\d+)\s*", line)
        if header:
            names[int(header[1])] = re.sub(r"&[+\-=]?[a-zA-Z]", "", lines[number + 2]).rstrip("~")

quests = {}  # quest mobile -> completions, each a list of (G or R, object)
dangling = set()
for zone in zones:
    path = AREAS / "qst" / (zone + ".qst")
    if not path.exists():
        continue
    mobile = None
    for line in path.read_text(encoding="latin-1").split("\n"):
        header = re.fullmatch(r"#(\d+)\s*", line)
        item = re.fullmatch(r"([RG]) I (\d+)\s*", line)
        if header:
            mobile = int(header[1])
        elif line == "Q":
            quests.setdefault(mobile, []).append([])
        elif item and quests.get(mobile):
            quests[mobile][-1].append((item[1], int(item[2])))
            if int(item[2]) not in names:
                dangling.add((mobile, item[1], int(item[2])))
assert dangling == NEVER_EXISTED, ("quest references to missing objects changed:\n"
                                   f"new: {sorted(dangling - NEVER_EXISTED)}\n"
                                   f"fixed: {sorted(NEVER_EXISTED - dangling)}")


def step(mobile, reward):
    """The names a completion takes, for the one completion of mobile paying reward."""
    (found,) = [rule for rule in quests[mobile]
                if reward in [names.get(vnum) for kind, vnum in rule if kind == "R"]]
    return sorted(names[vnum] for kind, vnum in found if kind == "G")


# Lancer's snake necklace and the Divhome bounty hunter pay objects a zone cleanup deleted.
assert step(55151, "a glowing white rod") == ["a live snake necklace"]
assert step(40706, "some angelic wings") == ["the dark heart of Relazier"]
# Ashrumite's object file closed a two-number gap; its quests and shops kept the old numbers.
assert step(66021, "a silver ring set with a small gem") == ["a lustrous diamond", "a silver ring"]
assert step(66021, "a lustrous diamond") == ["a raw gem"]
assert step(66040, "a necklace of fine silver") == ["a bar of pure silver"] * 5
shops = (AREAS / "shp/ashrumite.shp").read_text(encoding="latin-1")
bartender = shops.split("#66041~\n")[1].split("\n0\n")[0].split("\n")[1:]
assert [names[int(vnum)] for vnum in bartender] == [
    "a bottle of gnome spirits", "a barrel of gnomish beer", "a bottle of ale"], bartender
# Masha's cookbook wants the renumbered Tharnadia book and Ashrumite jerky.
assert {"a large blank book", "a large strip of beef jerky"} <= set(step(97006, "a map of Icecrag Castle"))

print("area race codes and quest item references resolve")
