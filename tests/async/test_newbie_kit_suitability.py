#!/usr/bin/env python3
"""Focused pre-wipe starter-kit admission and equipment-data regressions.

Full runtime admission is owned by can_char_use_item() and has_eq_slot().
This test pins the integration boundaries and corrected shared prototypes,
while test_newbie_kit_plan.py executes the pure C++ selection matrix.
"""
from pathlib import Path
import re
from _paths import ROOT

nanny = (ROOT / "src/account/nanny.c").read_text()
plan = (ROOT / "src/account/newbie_kit_plan.c").read_text()
objects = (ROOT / "areas/obj/heavens.obj").read_text()
defines = (ROOT / "src/core/defines.h").read_text()

capture = nanny.split("static newbie_item_facts capture_newbie_item_facts(", 1)[1]
capture = capture.split("/** Capture the finite legacy selection", 1)[0]
assert "if (!item.regular)" in capture
assert "can_char_use_item(ch, &view)" in capture
assert "prototype->anti_flags" in capture and "prototype->anti2_flags" in capture
assert "prototype->wear_flags & position[0]" in capture
assert "has_eq_slot(ch, position[2])" in capture
assert "facts.available = !has_wear_position || has_usable_position;" in capture
assert "required_weapon_skill(&view)" in capture  # weapon checks still apply

grant = nanny.split("static std::vector<prepared_newbie_item> prepare_legacy_newbie_plan(", 1)[1]
grant = grant.split("/** Materialize one detached legacy root", 1)[0]
assert grant.index("prepare_newbie_kit_items(selection, facts, first_circle)") < grant.index("if (!has_container)")
assert "prototype->type == ITEM_CONTAINER" in grant
assert "prepared.push_back({ { 390, true }, {} })" in grant
assert "if (!has_container)" in grant  # no duplicate bag
assert "item_creation_grant_defer(" in nanny  # existing durable batched grants stay in use

# Existing small leather bag must be a container. No new prototype needed.
def prototype(vnum):
    match = re.search(r"(?m)^#" + str(vnum) + r"\s*\n(.*?)(?=^#\d+\s*$|\Z)", objects, re.S | re.M)
    assert match, vnum
    line = next(line for line in match[1].splitlines()
                if re.fullmatch(r"-?\d+(?:\s+-?\d+){10}", line.strip()))
    return [int(value) for value in line.split()]

assert prototype(390)[0] == 15
pal = re.search(r"^#define CLASS_PALADIN BIT_(\d+)\b", defines, re.M)
anti = re.search(r"^#define CLASS_ANTIPALADIN BIT_(\d+)\b", defines, re.M)
assert pal and anti
required = (1 << (int(pal[1]) - 1)) | (1 << (int(anti[1]) - 1))
for vnum in (1104, 1105):
    flags = prototype(vnum)
    assert flags[6] & 1024  # ITEM_ALLOWED_CLASSES
    assert flags[9] & required == required, (vnum, flags[9])
assert "CLASS_BERSERKER" in plan and "CLASS_PSIONICIST" in plan
print("starter-kit suitability: bag, race/class admission, anatomical slots and class fallback contracts passed")
