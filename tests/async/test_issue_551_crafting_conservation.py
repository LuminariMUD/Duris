"""Crafts consume their inputs and hand over their outputs in memory, at once (#551)."""

from _paths import ROOT
from contract_text import contains


def section(text: str, start: str, end: str) -> str:
    begin = text.index(start)
    return text[begin:text.index(end, begin)]


salchemist_c = (ROOT / "src/classes/salchemist.c").read_text()
drannak_c = (ROOT / "src/classes/drannak.c").read_text()
poison = section(salchemist_c, "void do_mixpoison", "void do_mix(")
mix = section(salchemist_c, "void do_mix(", "bool is_neg_good")
encrust = section(salchemist_c, "void do_encrust", "int encrusted_eq_proc")
pvp = section(drannak_c, "int pvp_store", "// Proc for weapon")

for writer in (poison, mix, encrust, pvp):
    assert "item_movement_transaction" not in writer

assert contains(poison, "for (P_obj input : inputs) extract_obj(input); obj_to_char(poison_vial, ch);")
assert contains(mix, "for (P_obj input : inputs) extract_obj(input); for (P_obj output : outputs) obj_to_char(output, ch);")
# A mix that produced nothing still consumed what it says it did.
assert "struct alchemy_bottle_candidate" in mix
assert "available_bottles.push_front" in mix
assert "if (ingredients_consumed)" in mix
# A failed encrust breaks the item and the jewel and makes nothing.
failure = section(encrust, "if (!succeeded)", "P_obj new_item")
assert contains(failure, "extract_obj(item); extract_obj(jewel);")
assert "obj_to_char" not in failure
assert contains(encrust, "extract_obj(item); extract_obj(jewel); obj_to_char(new_item, ch);")
assert contains(pvp, "for (P_obj shard : shards) extract_obj(shard); obj_to_char(orb, pl);")
# A Chaos-pouch jewel is recorded on the pouch's scoreboard and encrusts like any other.
assert contains(encrust, "chaos_material_pouch_record_generated(ch, &generated, 1)")
assert "temporarily unavailable" not in encrust

print("Issue 551 crafting conservation contract passed")
