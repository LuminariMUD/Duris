#!/usr/bin/env python3
"""Curated task eligibility is independent of payouts and never inferred."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import epic_task_seed as seed


class EpicTaskSeedTest(unittest.TestCase):
    def cli(self, *args):
        return subprocess.run([sys.executable, str(ROOT / "scripts/epic_task_seed.py"), *args],
                              text=True, capture_output=True)

    def test_historical_roster_and_current_world(self):
        numbers = seed.roster()
        self.assertEqual(len(numbers), 107)
        self.assertEqual(numbers, sorted(set(numbers)))
        self.assertTrue({590, 1312, 1389}.isdisjoint(numbers))
        self.assertEqual(self.cli("check").returncode, 0)

    def test_invalid_roster_refused(self):
        data = json.loads(seed.MANIFEST.read_text())
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "roster.json"
            for numbers in ([], [14, 14], [24, 14], [0], [True], [999999], [13]):
                data["zone_numbers"] = numbers
                path.write_text(json.dumps(data))
                with self.subTest(numbers=numbers), self.assertRaises(ValueError):
                    seed.roster(manifest=path)

    def test_explicit_target_and_read_only_audit(self):
        for args in (("sql-apply",), ("sql-apply", "--database", "bad'; DROP TABLE zones;--"),
                     ("check", "--database", "unexpected")):
            self.assertNotEqual(self.cli(*args).returncode, 0)
        self.assertEqual(self.cli("sql-apply", "--database", "task_qa").returncode, 0)
        audit = self.cli("sql-audit")
        self.assertEqual(audit.returncode, 0, audit.stderr)
        for verb in ("UPDATE ", "INSERT ", "DELETE ", "CREATE ", "DROP "):
            self.assertNotIn(verb, audit.stdout)


if __name__ == "__main__":
    unittest.main()
