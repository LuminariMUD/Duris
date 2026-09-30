#!/usr/bin/env python3
"""Deaths happen at once (step 5 of the persistence reset).

make_corpse() puts a player's items into the corpse in memory, as it does for an
NPC, and the corpse save claims them. die() queues the corpse save, then the
player's save, and extracts the character: there is no recovery hold, retry
event or disputed-death disposition. A player's coins go into the corpse too, and
the player's save, with the wallet empty, is queued before the corpse's.
"""
from _paths import SRC


def body(source: str, signature: str, last: bool = False) -> str:
    start = source.rindex(signature) if last else source.index(signature)
    brace = source.index("{", start)
    depth = 0
    for end in range(brace, len(source)):
        depth += (source[end] == "{") - (source[end] == "}")
        if depth == 0:
            return source[start:end + 1]
    raise AssertionError(signature)


FIGHT = (SRC / "fight.c").read_text()
corpse = body(FIGHT, "P_obj make_corpse(P_char ch, int loss)")
assert "corpse->contains = ch->carrying;" in corpse and "if (IS_NPC(ch))\n\t{\n\t\tcorpse->contains" not in corpse
assert "if (IS_NPC(ch))\n\t\t(void)money_to_inventory(ch);" not in corpse
money = corpse.index("(void)money_to_inventory(ch);")
assert money < corpse.index("currency_transaction_save_first(ch);") < corpse.index(
    "corpse->contains = ch->carrying;") < corpse.index("writeCorpse(corpse);")
assert corpse.index("corpse->contains = ch->carrying;") < corpse.index("writeCorpse(corpse);")
assert "collector_death_enrollment_begin" not in corpse
print("[PASS] a player's items and coins go into the corpse; the empty wallet is saved first")

death = body(FIGHT, "void die(P_char ch, P_char killer)")
assert death.index("make_corpse(ch, loss)") < death.index(
    "persistence_save_character_terminal(ch, RENT_DEATH)") < death.index(
    "extract_char_after_terminal_save(ch)")
for gone in ("submit_next_corpse_item", "event_death_extract_retry", "schedule_death_extract_retry",
             "save_disputed_death_disposition", "DEATH_DISPOSITION_TIMEOUT_MSEC",
             "death_extract_retry_pulse", "corpse_transfer_disputed", "death_wallet_pending"):
    assert gone not in FIGHT, gone
assert "death_extract_retry_pulse" not in (SRC / "comm.c").read_text()
assert "death_retry" not in (SRC / "structs.h").read_text()
# The corpse job reaches the writer before the player's save, and the game thread
# writes no SQL for either (persistence reset phase 1 tests).
assert corpse.index("writeCorpse(corpse);") > corpse.index("corpse->contains = ch->carrying;")
FILES = (SRC / "files.c").read_text()
write = body(FILES, "void writeCorpse(P_obj corpse)")
assert "queue_corpse_save(corpse, !present)" in write and "sql_" not in write
print("[PASS] die() saves the corpse, then the player, and extracts at once")

REPOSITORY = (SRC / "player_snapshot_repository.c").read_text()
save = REPOSITORY[REPOSITORY.index('sql << "INSERT INTO corpses (player_name'):]
assert save.index("mysql_insert_id(connection)") < save.index("claim_graph(connection, corpse.owner")
print("[PASS] the corpse save claims what the corpse holds")
print("deaths happen at once contracts passed")
