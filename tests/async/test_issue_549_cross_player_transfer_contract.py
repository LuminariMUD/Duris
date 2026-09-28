#!/usr/bin/env python3
"""Contracts for issue 549's cross-player Soulbind and Slip handoffs.

Memory is the authority: both commands move the item from one player to the other
at once, and the next save of each records where it went.
"""

import unittest

from _paths import source
from _source_contract import function_body


class CrossPlayerTransferContractTests(unittest.TestCase):
    def test_soulbind_to_another_player_moves_in_memory(self):
        magic = source("magic/magic.c").read_text()
        soulbind = function_body(magic, r"void do_soulbind\(")
        cross_player = soulbind[soulbind.index("if (ch != victim)\n\t\t{") :]
        cross_player = cross_player[: cross_player.index("\n\t\t}\n")]

        self.assertNotIn("item_movement_transaction_submit", magic)
        self.assertLess(cross_player.index("total_carried_weight(victim)"),
                        cross_player.index("give_soulbind_item(ch, victim, obj)"))
        self.assertLess(cross_player.index("remove_soulbind(victim)"),
                        cross_player.index("give_soulbind_item(ch, victim, obj)"))
        self.assertLess(cross_player.index("give_soulbind_item(ch, victim, obj)"),
                        cross_player.index("apply_soulbind_metadata(victim, obj)"))
        give = function_body(magic, r"static bool give_soulbind_item\(")
        self.assertLess(give.index("obj_from_char(object)"), give.index("obj_to_char(object, victim)"))

    def test_slip_moves_in_memory(self):
        rogues = source("classes/rogues.c").read_text()
        slip = function_body(rogues, r"void do_slip\(")
        success = slip[slip.index("if (success)") :]

        self.assertNotIn("item_movement_transaction_submit", rogues)
        self.assertNotIn("item_ownership_runtime", rogues)
        self.assertLess(success.index("obj_from_char(obj)"), success.index("obj_to_char(obj, vict)"))
        self.assertLess(success.index("notch_skill(ch, SKILL_SLIP"), success.index("obj_to_char(obj, vict)"))


if __name__ == "__main__":
    unittest.main()
