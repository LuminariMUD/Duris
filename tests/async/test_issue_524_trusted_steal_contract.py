#!/usr/bin/env python3
"""Source contracts for issue 524's trusted-steal custody boundary.

The live game journey needs two player sessions and a running ownership
backend, so these checks pin the parts that must remain true in every build:
admission happens before detachment, the exact UID is published after commit,
and a refused publication cannot destroy an already-authoritative graph.
"""

import unittest

from _paths import source
from _source_contract import function_body


class TrustedStealCustodyContractTests(unittest.TestCase):
    def test_a_player_victim_is_robbed_in_memory(self):
        actoth = source("cmd/actoth.c").read_text()
        steal_item = function_body(actoth, r"static bool steal_player_item\(")
        self.assertIn("trusted_steal_binding_allows_tree(thief, object)", steal_item)
        self.assertIn("object->type == ITEM_MONEY", steal_item)
        self.assertIn("steal_from_player(thief, victim, object, context);", steal_item)
        self.assertNotIn("item_movement_transaction_submit", actoth)
        self.assertNotIn("item_ownership_runtime_lookup", actoth)

        steal = function_body(actoth, r"void do_steal\(")
        equipped = steal[steal.index("if (!failed && (trusted ||"):]
        self.assertIn("steal_player_item(ch, victim, obj, TRUE", equipped)
        inventory = steal[steal.index("case 2:"):steal.index("case 3:")]
        self.assertIn("steal_player_item(ch, victim, obj, FALSE", inventory)
        self.assertIn("return;", equipped[equipped.index("steal_player_item"):])
        self.assertIn("return;", inventory[inventory.index("steal_player_item"):])

    def test_the_item_is_detached_before_the_thief_gets_it(self):
        actoth = source("cmd/actoth.c").read_text()
        move = function_body(actoth, r"static void steal_from_player\(")
        self.assertLess(move.index("unequip_char(victim, slot)"), move.index("obj_to_char(object, thief)"))
        self.assertLess(move.index("obj_from_char(object)"), move.index("obj_to_char(object, thief)"))
        # obj_to_char may crumble the item; it is found again by uid before any use.
        after = move[move.index("obj_to_char(object, thief)"):]
        self.assertLess(after.index("find_trusted_steal_item(context.item_uid)"),
                        after.index('send_to_char("Got it!'))
        self.assertIn("OBJ_CARRIED_BY(object, thief)", after)

    def test_trusted_steal_bypasses_legacy_random_and_cooldown_gates(self):
        steal = function_body(source("cmd/actoth.c").read_text(), r"void do_steal\(")
        self.assertIn("const bool trusted = IS_TRUSTED(ch);", steal)
        self.assertIn("if (!trusted && affected_by_spell(ch, TAG_PVPDELAY))", steal)
        self.assertIn("if (!trusted && IS_FIGHTING(victim))", steal)
        self.assertIn("if (trusted)\n\t\tpercent = 100;", steal)
        self.assertIn("roll = trusted ? 1 : number(0, 100);", steal)
        self.assertIn("if (!trusted && roll > MIN(percent, 99))", steal)
        self.assertIn("if (!trusted)\n\t\tCharWait(ch, PULSE_VIOLENCE * 2);", steal)
        self.assertIn("if (trusted)\n\t\treturn;", steal)

    def test_trusted_steal_preserves_account_and_soul_binding(self):
        command = source("cmd/actoth.c").read_text()
        recipient = function_body(
            command, r"static bool trusted_steal_binding_allows_recipient\("
        )
        self.assertIn("!account_bound_reward_owner(thief, object)", recipient)
        self.assertIn("ITEM2_SOULBIND", recipient)
        self.assertLess(
            recipient.index("!account_bound_reward_owner"),
            recipient.index("ITEM2_SOULBIND"),
        )
        self.assertIn("return false;", recipient)
        self.assertIn("trusted_steal_binding_allows_tree", command)

    def test_binding_walk_rejects_cycles_and_oversized_trees(self):
        command = source("cmd/actoth.c").read_text()
        binding = function_body(
            command, r"static bool trusted_steal_binding_allows_tree\("
        )
        self.assertIn("std::vector<P_obj> pending", binding)
        self.assertIn("std::vector<P_obj> visited", binding)
        self.assertIn("ITEM_TRANSFER_MAX_ITEMS", binding)
        self.assertIn("std::find(visited.begin(), visited.end(), child)", binding)
        self.assertIn("std::find(pending.begin(), pending.end(), child)", binding)
        self.assertIn("catch (const std::bad_alloc &)", binding)

    def test_trusted_steal_has_no_random_caught_result_or_delay(self):
        command = source("cmd/actoth.c").read_text()
        caught = function_body(command, r"static bool trusted_steal_was_caught\(")
        delay = function_body(command, r"static void trusted_steal_attempt_delay\(")
        self.assertIn("return false;", caught)
        self.assertIn("if (IS_TRUSTED(thief))\n\t\treturn;", delay)

    def test_trusted_player_gate_remains_in_place(self):
        steal = function_body(source("cmd/actoth.c").read_text(), r"void do_steal\(")
        self.assertIn('if (!IS_TRUSTED(ch))', steal)
        self.assertIn("Steal is temporarily disabled", steal)


if __name__ == "__main__":
    unittest.main()
