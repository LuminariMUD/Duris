#!/usr/bin/env python3
"""Regression contracts for readable help headings and progression colours."""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from format_help_topics import HEADING, PROGRESSION, SOURCES, format_text


class HelpLayoutTest(unittest.TestCase):
    def test_authored_help_is_normalized(self):
        for path in SOURCES:
            with self.subTest(source=path.name):
                text = path.read_bytes().decode("utf-8", errors="surrogateescape")
                self.assertEqual(format_text(text), text)
                lines = text.split("\n")
                headings = 0
                white_labels = 0
                for index, line in enumerate(lines):
                    self.assertIsNone(PROGRESSION.match(line))
                    if re.match(r"^[ \t]*&\+W\d+(?:st|nd|rd|th) (?:Level|Circle):", line):
                        white_labels += 1
                    if not HEADING.fullmatch(line.strip()):
                        continue
                    headings += 1
                    if index:
                        self.assertEqual(lines[index - 1], "", (path, index))
                    if index + 1 < len(lines):
                        self.assertEqual(lines[index + 1], "", (path, index))
                self.assertGreater(headings, 100)
                self.assertGreater(white_labels, 100)

    def test_formatter_only_changes_heading_spacing_and_label_colour(self):
        original = (
            "Topic\nTopic - Last Edited: 2026-10-25\n"
            "================================================\n"
            "Intro.\n==Description==\nText.\n==Skills==\n"
            "&+b1st Level: &+cparry&n\n"
            "&+bOgre&n retains its racial colour.\n#0\n"
        )
        expected = (
            "Topic\nTopic - Last Edited: 2026-10-25\n"
            "================================================\n"
            "Intro.\n\n==Description==\n\nText.\n\n==Skills==\n\n"
            "&+W1st Level: &+cparry&n\n"
            "&+bOgre&n retains its racial colour.\n#0\n"
        )
        self.assertEqual(format_text(original), expected)
        self.assertEqual(format_text(expected), expected)

    def test_excess_heading_whitespace_is_removed_without_rewriting_prose(self):
        original = "Intro.\n\n\n==See also==\n\n\n* Spell\n\n#0\n"
        expected = "Intro.\n\n==See also==\n\n* Spell\n\n#0\n"
        self.assertEqual(format_text(original), expected)


if __name__ == "__main__":
    unittest.main()
