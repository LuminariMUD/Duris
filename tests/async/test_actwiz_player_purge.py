#!/usr/bin/env python3
"""Regression contract for the staff purge command's player lifetime.

Extraction frees the player.  Player inventory must be detached before
capturing a terminal snapshot, and no victim access may follow extraction.
"""

from _paths import extract_function

source = extract_function(
    "actwiz.c", "void do_purge(P_char ch, char *argument, int /*cmd*/)"
)
player_branch = source.split("if (IS_NPC(vict))", 1)[1].split(
    "else if ((obj = get_obj_in_list_vis", 1
)[0]

required = (
    "GET_LEVEL(vict) < MINLVLIMMORTAL",
    "update_ingame_racewar(-GET_RACEWAR(vict))",
    "for (int slot = 0; slot < MAX_WEAR; ++slot)",
    "unequip_char(vict, slot)",
    "while (vict->carrying)",
    "obj_from_char(item)",
    "obj_to_room(item, vict->in_room)",
    "IS_SET(item->extra_flags, ITEM_TRANSIENT)",
    "writeCharacter(vict, RENT_QUIT, NOWHERE)",
    "extract_char_after_terminal_save(vict)",
)
for fragment in required:
    assert fragment in player_branch, f"missing player purge contract: {fragment}"

save = player_branch.index("writeCharacter(vict, RENT_QUIT, NOWHERE)")
extract = player_branch.index("extract_char_after_terminal_save(vict)")
assert save < extract
assert player_branch.index("unequip_char(vict, slot)") < save
assert player_branch.index("obj_from_char(item)") < save
assert player_branch[extract:].split("vict = NULL", 1)[0].count("vict->") == 0

for forbidden in (
    "free_char(vict)",
    "close_socket(vict->desc)",
    "vict->desc =",
):
    assert forbidden not in player_branch, f"post-extraction access: {forbidden}"

print("PASS staff purge saves after item cleanup and never reuses freed player")
