#!/usr/bin/env python3
"""Race help keeps every active innate and refuses unresolved assignments."""
import contextlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from _paths import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
import sync_race_innate_help as sync


class RaceInnateHelpTest(unittest.TestCase):
    def test_checked_in_help_matches(self):
        self.assertEqual(sync.sync(True), 0)

    def test_non_prefixed_innates_and_level_match_game(self):
        lists = sync.expected_lists()
        for race, line in (
            ("centaur", "*two-handed sword mastery (obtained at level 31)"),
            ("mountain dwarf", "*magical reduction"),
            ("duergar dwarf", "*magical reduction"),
            ("ogre", "*magic vulnerability"),
            ("firbolg", "*magic vulnerability"),
            ("drider", " web_spray (obtained at level 31)"),
        ):
            with self.subTest(race=race):
                self.assertIn(line, lists[race])
        self.assertNotIn("*dayblind", lists["duergar dwarf"])
        self.assertEqual(lists["storm giant"], ["None."])

    def test_unresolved_or_unsupported_calls_fail_before_writing(self):
        original_read = sync.read
        for call in (
            "ADD_RACIAL_INNATE(MISSING_ABILITY, RACE_CENTAUR, 31);",
            "ADD_RACIAL_INNATE(TWO_HANDED_SWORD_MASTERY, RACE_MISSING, 31);",
            "ADD_RACIAL_INNATE(TWO_HANDED_SWORD_MASTERY, RACE_CENTAUR, 30 + 1);",
        ):
            with self.subTest(call=call), tempfile.TemporaryDirectory() as directory:
                help_path = Path(directory) / "help.hlp"
                before = sync.HELP.read_bytes()
                help_path.write_bytes(before)

                def read_with_call(path):
                    text = original_read(path)
                    return text + "\n" + call if path.name == "innates.c" else text

                with patch.object(sync, "read", read_with_call), patch.object(sync, "HELP", help_path):
                    with self.assertRaisesRegex(SystemExit, "racial innate call"):
                        sync.sync(False)
                self.assertEqual(help_path.read_bytes(), before)

    def test_check_detects_stale_help_and_sync_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            help_path = Path(directory) / "help.hlp"
            before = sync.HELP.read_text()
            help_path.write_text(before.replace("*two-handed sword mastery (obtained at level 31)\n", ""))
            with patch.object(sync, "HELP", help_path), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(sync.sync(True), 1)
                self.assertEqual(sync.sync(False), 0)
                self.assertEqual(help_path.read_text(), before)
                self.assertEqual(sync.sync(False), 0)
                self.assertEqual(sync.sync(True), 0)


if __name__ == "__main__":
    unittest.main()
