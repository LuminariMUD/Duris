#!/usr/bin/env python3
"""Regression contract for multi-part spell wear-off messages."""

from _paths import SRC
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = (SRC / "affects.c").read_text()

start = SOURCE.index("void wear_off_message(")
end = SOURCE.index("//=================================================================================", start)
body = SOURCE[start:end]

duplicate_guard = body.index("other != af && other->type == af->type")
message = body.index("send_to_char(skills[af->type].wear_off_char[idx], ch)")

assert duplicate_guard < message

# Issue #1021: Monk Regenerate tells its owner when it ends, and observers see a
# blinded creature regain its sight. Both go through wear_off_message() above.
skills = " ".join((SRC / "skills.c").read_text().split())
assert ('SKILL_CREATE_WITH_MESSAGES("regenerate", SKILL_REGENERATE, TAR_PHYS, '
        '"Your body stops healing faster.", NULL);') in skills
assert '"$n blinks as $s sight returns.");' in skills.split('SPELL_CREATE2("blindness", SPELL_BLINDNESS,')[1][:260]
assert "act(skills[af->type].wear_off_room[idx], FALSE, ch, 0, 0, TO_ROOM)" in body

print("multi-part affect wear-off message contract passed")
