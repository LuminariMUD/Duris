#!/usr/bin/env python3
"""Regression tests for the nightly account login statistics export."""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from datetime import date, datetime, timezone
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import login_stats_export as export_module  # noqa: E402

UTC = ZoneInfo("UTC")


def at(text: str) -> int:
    return int(datetime.fromisoformat(text).replace(tzinfo=timezone.utc).timestamp())


class DailyCountsTest(unittest.TestCase):
    def test_counts_accounts_not_characters(self):
        logins = [
            (at("2026-10-11T01:00"), "alice", 0),
            (at("2026-10-11T05:00"), "alice", 0),  # an alt on the same account
            (at("2026-10-11T09:00"), "bob", 0),
        ]
        rows, unmapped = export_module.daily_counts(logins, [date(2026, 10, 11)], UTC)
        self.assertEqual(rows, [{"date": "2026-10-11", "unique_accounts": 2, "logins": 3}])
        self.assertEqual(unmapped, 0)

    def test_leaves_out_immortals_and_logins_without_account(self):
        logins = [
            (at("2026-10-11T01:00"), "alice", 0),
            (at("2026-10-11T02:00"), "staff", 1),
            (at("2026-10-11T03:00"), None, None),
        ]
        rows, unmapped = export_module.daily_counts(logins, [date(2026, 10, 11)], UTC)
        self.assertEqual(rows, [{"date": "2026-10-11", "unique_accounts": 1, "logins": 1}])
        self.assertEqual(unmapped, 1)

    def test_day_follows_the_export_time_zone(self):
        # 13:30 UTC on the 11th is 00:30 on the 12th in Sydney (UTC+11 from October 4).
        logins = [(at("2026-10-11T13:30"), "alice", 0)]
        day = [date(2026, 10, 11)]
        sydney, _ = export_module.daily_counts(logins, day, ZoneInfo("Australia/Sydney"))
        utc, _ = export_module.daily_counts(logins, day, UTC)
        self.assertEqual(sydney[0]["unique_accounts"], 0)
        self.assertEqual(utc[0]["unique_accounts"], 1)


class ExportTest(unittest.TestCase):
    def run_export(self, query_rows, days=90):
        queries = []

        def fake_query(sql):
            queries.append(sql)
            return query_rows["first"] if "MIN(" in sql else query_rows["logins"]

        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        directory = Path(temporary.name) / "new" / "stats"
        with patch.object(export_module, "run_query", fake_query), \
                redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            status = export_module.export(directory, "UTC", days, date(2026, 10, 12))
        self.assertEqual(status, 0)
        return directory, queries

    def test_publishes_complete_days_only_from_first_recorded_login(self):
        directory, queries = self.run_export({
            "first": [[str(at("2026-10-09T18:00"))]],
            "logins": [
                [str(at("2026-10-10T08:00")), "alice", "0"],
                [str(at("2026-10-11T08:00")), "alice", "0"],
                [str(at("2026-10-11T09:00")), "bob", "0"],
                [str(at("2026-10-11T10:00")), "NULL", "NULL"],
            ],
        })
        history = json.loads((directory / "history.json").read_text())
        latest = json.loads((directory / "latest.json").read_text())
        self.assertEqual([day["date"] for day in history["days"]],
                         ["2026-10-09", "2026-10-10", "2026-10-11"])
        self.assertEqual(history["days"][0], {"date": "2026-10-09", "unique_accounts": 0, "logins": 0})
        self.assertEqual((latest["date"], latest["unique_accounts"], latest["logins"]), ("2026-10-11", 2, 2))
        # The fetch window starts at the first recorded day and stops before today.
        self.assertIn(f"FROM_UNIXTIME({at('2026-10-09T00:00')})", queries[1])
        self.assertIn(f"< FROM_UNIXTIME({at('2026-10-12T00:00')})", queries[1])
        self.assertFalse(list(directory.glob("*.tmp")))

    def test_window_is_limited_to_requested_days(self):
        directory, _ = self.run_export({"first": [[str(at("2020-01-01T00:00"))]], "logins": []}, days=7)
        history = json.loads((directory / "history.json").read_text())
        self.assertEqual(len(history["days"]), 7)
        self.assertEqual(history["days"][-1]["date"], "2026-10-11")

    def test_writes_nothing_before_any_login_is_recorded(self):
        directory, queries = self.run_export({"first": [["NULL"]], "logins": []})
        self.assertFalse(directory.exists())
        self.assertEqual(len(queries), 1)


if __name__ == "__main__":
    unittest.main()
