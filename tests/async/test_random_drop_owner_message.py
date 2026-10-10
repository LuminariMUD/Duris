#!/usr/bin/env python3
"""A player's pet that wins a random drop tells its owner, not itself."""

from _paths import extract_function

die = extract_function("fight.c", "void die(P_char ch, P_char killer)")
start = die.index("// object code - Normal kills.")
drops = die[start : die.index("update_pos(ch);", start)]

assert "P_char credited_killer = IS_PC_PET(killer) ? GET_MASTER(killer) : killer;" in drops
for kind in ("equipment", "material"):
    message = f'"It appears you were able to salvage a piece of {kind} from your enemy.\\n",'
    call = drops[drops.index(message) :]
    assert call.split(")", 1)[0].split(",")[-1].strip() == "credited_killer", kind

# The rolls and the item still use the actual killer's level and luck.
assert "check_random_drop(killer, ch, TRUE)" in drops
assert "create_random_eq_new(killer, ch, -1, -1)" in drops
print("random drop owner message passed")
