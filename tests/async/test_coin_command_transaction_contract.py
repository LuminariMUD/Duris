#!/usr/bin/env python3
"""Coin commands move coins in memory; the owner the coins leave is saved first."""

from _paths import SRC
import re


ACTOBJ = (SRC / "actobj.c").read_text(encoding="utf-8", errors="replace")


def body(signature: str) -> str:
    """Return one C++ function body selected by its signature."""
    start = ACTOBJ.index(signature)
    opening = ACTOBJ.index("{", start)
    depth = 0
    for position in range(opening, len(ACTOBJ)):
        if ACTOBJ[position] == "{":
            depth += 1
        elif ACTOBJ[position] == "}":
            depth -= 1
            if depth == 0:
                return ACTOBJ[start : position + 1]
    raise AssertionError(f"unterminated function: {signature}")


drop_all = body("void do_dropalldot(")
drop = body("void do_drop(")
put = body("void do_put(")
give = body("void do_give(")
submit = body("bool submit_coin_debit(")
completion = body("void coin_debit_completion(")
publish_drop = body("void publish_coin_drop(")
corpse_put = body("bool publish_pc_corpse_coin_put(")
finish_put = body("void finish_coin_put_publication(")
give_credit = body("bool begin_coin_give_credit(")

for name, command in (
    ("drop all.coins", drop_all),
    ("drop coins", drop),
    ("put coins", put),
    ("give coins", give),
):
    assert "submit_coin_debit(ch, context)" in command, name
    assert "create_money(" not in command, name

# Every actor, player or NPC, takes the coins from the wallet in memory and publishes
# at once.
assert "SUB_MONEY(actor, static_cast<int>(value), 0)" in submit
assert "coin_debit_completion(actor, true," in submit
assert "currency_transaction_submit" not in submit
assert "publish_coin_drop(actor, context)" in completion
assert "publish_coin_put(actor, context)" in completion
assert "begin_coin_give_credit(actor, recipient, context, true)" in completion
assert "create_money(" in publish_drop and "obj_to_room(" in publish_drop

# The owner the coins leave is saved before the one they reach.
assert give_credit.index("currency_transaction_save_first(sender);") < give_credit.index(
    "currency_transaction_submit_wallet_value(")
assert corpse_put.index("currency_transaction_save_first(actor);") < corpse_put.index(
    "writeCorpse(container);")
assert finish_put.index("currency_transaction_save_first(actor);") < finish_put.index(
    "writeSavedItem(container);")

# The durable coin transfer and its custody publication are gone.
for retired in ("submit_coin_give", "submit_coin_put", "submit_coin_get", "coin_get_completion",
                "publish_coin_pile", "prepare_coin_pile", "coin_put_custody_completion",
                "currency_transaction_submit_coin", "currency_transaction_coin_wallet"):
    assert retired not in ACTOBJ, retired

direct_cash_write = re.compile(r"points\.cash\[[^]]+\]\s*(?:[+\-]=|=(?!=))")
assert not direct_cash_write.search(ACTOBJ)

print("coin drop, put and give move coins in memory and save the giver first")
