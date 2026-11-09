#!/usr/bin/env python3
"""Source contracts for restored saved-world-item routing."""

from _paths import SRC
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
class SavedItemFlatfileRoutingTests(unittest.TestCase):
    def test_saved_item_writes_are_writer_jobs(self):
        files = (SRC / "files.c").read_text()
        write = files[files.index("void writeSavedItem") :]
        write = write[: write.index("void restoreSavedItems")]
        purge = files[files.index("void PurgeSavedItemFile") :]
        purge = purge[: purge.index("int writeShopKeeper")]
        # Saved items live in memory: their saves and deletes are writer jobs (step 6),
        # and a job the writer refuses is reported, not run on the loop.
        self.assertEqual(write.count("queue_saved_item_save("), 2)
        self.assertEqual(purge.count("queue_saved_item_save(item, Gbuf2, true)"), 1)
        self.assertNotIn("sql_save_saved_item", write)
        self.assertNotIn("sql_delete_saved_item", write + purge)
        self.assertIn('"queue_failed"', write)
        self.assertIn('"queue_failed"', purge)

    def test_storage_admin_mutations_move_in_memory(self):
        # Memory is the authority: the storage command changes the room at once, and the
        # room's saved-item write records it.
        actwiz = (SRC / "actwiz.c").read_text()
        storage = actwiz[actwiz.index("void do_storage(") :]
        storage = storage[: storage.index("\n}\n")]
        self.assertNotIn("submit_flat_storage", actwiz)
        self.assertNotIn("PERSISTENCE_MODE_FLATFILE_PRIMARY", storage)
        self.assertLess(storage.index("obj_to_room(s_obj, ch->in_room)"),
                        storage.index("writeSavedItem(s_obj)"))

if __name__ == "__main__":
    unittest.main()
