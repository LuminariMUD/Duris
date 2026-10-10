#!/usr/bin/env python3
"""What only the text of the CHAOS starting grants and the material pouch can show.

The grants' behaviour is checked where it runs: the CHAOS character journey (level 56, the
epic skills, the frigate, 20,000 epic points, 1,000,000 platinum in the bank, the pouch's
scoreboard and generated materials), test_chaos_env_toggle.py (the switches),
test_epic_skill_grant.py and test_guild_chaos_epic_skills.py (which epic skills).

What stays here:

  1. orders the journeys cannot break: the baseline save comes before the kit and the
     ledgers, and the reward intents before the baseline (a crash between them is what the
     order guards); level, skills and tattoo come before the post-entry save;
  2. a bulk level catch-up queues no boon check per level;
  3. code that must not come back;
  4. the pouch where crafting, enhancing, salvaging and encrusting read it, and the
     shipyard's frigate discount: no journey crafts, enhances without materials, salvages
     or encrusts the pouch itself, or buys a hull with the tattoo, so only the text shows
     those branches are still there.
"""

from __future__ import annotations

import re

from _paths import ROOT, source

NANNY = source("nanny.c").read_text(encoding="utf-8", errors="replace")
LIMITS = source("limits.c").read_text(encoding="utf-8", errors="replace")


def function_body(signature: str, start_at: int = 0) -> str:
    start = LIMITS.index(signature, start_at)
    opening = LIMITS.index("{", start)
    depth = 0
    for position in range(opening, len(LIMITS)):
        if LIMITS[position] == "{":
            depth += 1
        elif LIMITS[position] == "}":
            depth -= 1
            if depth == 0:
                return LIMITS[start : position + 1]
    raise AssertionError(signature)


# 1. Orders.
baseline = NANNY.index("if (!writeCharacter(ch, 2, NOWHERE))")
assert baseline < NANNY.index("load_chaos_new_character_kit(ch);") < NANNY.index(
    "schedule_chaos_starting_ledgers(ch);"
)
assert "mark_chaos_starter_reward_intents(ch);\n\tif (!writeCharacter(ch, 2, NOWHERE))" in NANNY
assert (
    NANNY.index("advance_to_level(ch, 56);")
    < NANNY.index("grant_epic_skills_without_specialization(ch);")
    < NANNY.index("grant_chaos_tattoo_achievement(ch);")
    < NANNY.index("if (!writeCharacter(ch, 1, NOWHERE))")
)

# 2. One boon check per ordinary level; none for a bulk catch-up.
advance_impl = function_body(
    "static void advance_level_impl", LIMITS.index("void illithid_advance_level")
)
assert "if (process_boons)\n\t\tcheck_boon_completion(ch, NULL, 0, BOPT_LEVEL);" in advance_impl
assert function_body("void advance_level(P_char ch)\n{").count(
    "advance_level_impl(ch, true, true, 0U);"
) == 1
to_level = function_body("void advance_to_level(P_char ch, int target_level)\n{")
assert to_level.count("advance_level_impl(ch, false, false, 0U);") == 1
assert "advance_level_impl(ch, false, true," not in to_level

# 3. Code that must not come back.
for removed in ("CHAOS_RESOURCE_", "chaos_resource_", "PLR3_CHAOS_STARTER_PENDING",
                "item_creation_grant_submit_to_player_before_entry_with_completion"):
    assert removed not in NANNY, removed
assert "item_creation_grant_submit_to_player_before_entry_with_completion" not in source(
    "item/item_movement_transaction.h").read_text(encoding="utf-8", errors="replace")
MATERIALS_C = (ROOT / "src/combat/chaos_materials.c").read_text(encoding="utf-8", errors="replace")
# Memory is the authority: the pouch records the materials, then consumes them at once.
for removed in ("item_movement_transaction_submit", "chaos_material_pouch_collection_completion",
                "obj_from_char(material)"):
    assert removed not in MATERIALS_C, removed
collect = MATERIALS_C[MATERIALS_C.index("bool collect_into_pouch("):]
collect = collect[: collect.index("\n}\n")]
assert collect.index("chaos_material_pouch_record_collected(pouch, usage.data(), usage_count)") < \
    collect.index("extract_obj(roots[index], FALSE)")
assert "#ifdef TEST_MUD" not in source("chaos.c").read_text(encoding="utf-8", errors="replace")
ACTINF = source("actinf.c").read_text(encoding="utf-8", errors="replace")
assert "chaos_material_pouch_is(tmp_object)" not in ACTINF
SALCHEMIST = source("salchemist.c").read_text(encoding="utf-8", errors="replace")
assert "Virtual Chaos-pouch encrust is temporarily unavailable" not in SALCHEMIST

# 4. The pouch where the trades read it, and the frigate where the shipyard prices it.
SHIP_SHOP = source("ship_shop.c").read_text(encoding="utf-8", errors="replace")
assert "const int tattoo_reward_hull = chaos_frigate_reward ? SH_FRIGATE : SH_SLOOP;" in SHIP_SHOP
assert "const int tattoo_discount = chaos_frigate_reward ? SHIPTYPE_COST(tattoo_reward_hull) :" in SHIP_SHOP
CRAFTING = source("crafting.c").read_text(encoding="utf-8", errors="replace")
assert "!chaos_pouch && (invLowMats < numLowest || invHighMats < numHighest)" in CRAFTING
assert "!chaos_pouch && (numLowest > 0)" in CRAFTING
assert "!chaos_pouch && (invVnum == lowQualityMaterialVnum)" in CRAFTING
assert CRAFTING.count("chaos_material_pouch_report_generated_failure") >= 2
assert "if (!chaos_material_pouch_record_generated" in CRAFTING
ENHANCE = source("enhance.c").read_text(encoding="utf-8", errors="replace")
assert "if (!pouch)" in ENHANCE
assert "chaos_material_pouch_is(source)" in ENHANCE and "chaos_material_pouch_is(material)" in ENHANCE
assert "superior_plan_has_materials(ch, pouch" in ENHANCE
assert "chaos_material_pouch_is(temp)" in source("salvage.c").read_text(
    encoding="utf-8", errors="replace")
assert "chaos_material_pouch_is(item)" in SALCHEMIST and "chaos_material_pouch_is(jewel)" in SALCHEMIST
assert "chaos_material_pouch_record_generated(ch, &generated, 1)" in SALCHEMIST

print("CHAOS starting grants and pouch: text-only contracts passed")
