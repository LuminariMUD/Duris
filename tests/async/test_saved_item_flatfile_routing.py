#!/usr/bin/env python3
"""Source contracts for restored saved-world-item routing."""

from _paths import SRC
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
class SavedItemFlatfileRoutingTests(unittest.TestCase):
    def test_historical_entry_points_do_not_reach_sql_in_flat_primary(self):
        files = (SRC / "files.c").read_text()
        write = files[files.index("void writeSavedItem") :]
        write = write[: write.index("void restoreSavedItems")]
        restore = files[files.index("void restoreSavedItems") :]
        restore = restore[: restore.index("void PurgeSavedItemFile")]
        purge = files[files.index("void PurgeSavedItemFile") :]
        purge = purge[: purge.index("int writeShopKeeper")]
        self.assertLess(restore.index("PERSISTENCE_MODE_FLATFILE_PRIMARY"),
                        restore.index("sql_restore_saved_items"))
        # Saved items live in memory: their saves and deletes are writer jobs (step 6) on
        # both backends, and a job the writer refuses is reported, not run on the loop.
        self.assertEqual(write.count("queue_saved_item_save("), 2)
        self.assertEqual(purge.count("queue_saved_item_save(item, Gbuf2, true)"), 1)
        self.assertNotIn("sql_save_saved_item", write)
        self.assertNotIn("sql_delete_saved_item", write + purge)
        self.assertIn('"queue_failed"', write)
        self.assertIn('"queue_failed"', purge)

    def test_storage_admin_mutations_move_in_memory(self):
        # Memory is the authority: the storage command changes the room at once on
        # both backends, and the room's saved-item write records it.
        actwiz = (SRC / "actwiz.c").read_text()
        storage = actwiz[actwiz.index("void do_storage(") :]
        storage = storage[: storage.index("\n}\n")]
        self.assertNotIn("submit_flat_storage", actwiz)
        self.assertNotIn("PERSISTENCE_MODE_FLATFILE_PRIMARY", storage)
        self.assertLess(storage.index("obj_to_room(s_obj, ch->in_room)"),
                        storage.index("writeSavedItem(s_obj)"))

    def test_room_repository_admits_only_the_bounded_storage_transfers(self):
        repository = (SRC / "flatfile_item_repository.c").read_text()
        room = repository[repository.index("bool room_transfer") :]
        room = room[: room.index("bool generic_transfer_supported")]
        self.assertIn("item_owner_type::system", room)
        self.assertIn("item_owner_type::destruction", room)
        self.assertIn("item_transfer_reason::operator_repair", room)


if __name__ == "__main__":
    unittest.main()
