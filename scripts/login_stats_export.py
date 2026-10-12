#!/usr/bin/env python3
"""Export daily unique-account login counts as JSON for a website.

Run once a night, shortly after midnight in --timezone. Each run recomputes the
last --days complete days from session_audit_outcome and rewrites two files in
--output-dir:

  latest.json   yesterday's figures
  history.json  one entry per day, oldest first

Today is never included, so published numbers trail by one full day. A login
belongs to the day it happened in --timezone. Account identity and staff status
come from the immutable login snapshot, so later transfers, promotions and
deletions cannot rewrite history. Alts on one account count once. Days before
the first login with a snapshot are omitted; legacy rows cannot be backfilled
accurately and are excluded, with missing snapshots reported on stderr.

Connection settings come only from the environment:

  LOGIN_STATS_DB_HOST      (default localhost, which uses the local socket)
  LOGIN_STATS_DB_PORT      (default 3306)
  LOGIN_STATS_DB_DATABASE
  LOGIN_STATS_DB_USER
  LOGIN_STATS_DB_PASSWORD

For the checked-in service's loopback TCP connection, create a dedicated user
with the same password as LOGIN_STATS_DB_PASSWORD and grant only:

  CREATE USER 'duris_stats'@'127.0.0.1' IDENTIFIED BY '<password>';
  GRANT SELECT ON <db>.session_audit_outcome TO 'duris_stats'@'127.0.0.1';

Use 'localhost' instead only for a Unix-socket connection (the script default).

Example:

  python3 scripts/login_stats_export.py --output-dir ~/durisweb/backend/public/stats \\
      --timezone America/New_York
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

LOGIN_EVENT = 1  # session_audit_event::login in src/account/session_audit_command.h
ENV = "LOGIN_STATS_DB_"


def run_query(sql: str) -> list[list[str]]:
    """Run one SELECT through the mysql client and return its rows as strings.

    SQL NULL comes back as the text NULL. Account names are lowercased in the
    query, so a real account can never read back as that uppercase text.
    """
    missing = [ENV + name for name in ("DATABASE", "USER", "PASSWORD") if not os.environ.get(ENV + name)]
    if missing:
        raise SystemExit("missing environment: " + ", ".join(missing))
    command = [
        "mysql", "--no-defaults", "--batch", "--skip-column-names",
        "--host=" + os.environ.get(ENV + "HOST", "localhost"),
        "--port=" + os.environ.get(ENV + "PORT", "3306"),
        "--user=" + os.environ[ENV + "USER"],
        os.environ[ENV + "DATABASE"],
        "-e", "SET time_zone='+00:00'; " + sql,
    ]
    result = subprocess.run(command, env=dict(os.environ, MYSQL_PWD=os.environ[ENV + "PASSWORD"]),
                            capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise SystemExit("query failed: " + result.stderr.strip())
    return [line.split("\t") for line in result.stdout.splitlines()]


def first_login_time() -> int | None:
    rows = run_query("SELECT UNIX_TIMESTAMP(MIN(occurred_at)) FROM session_audit_outcome "
                     f"WHERE event_type = {LOGIN_EVENT} "
                     "AND NULLIF(account_name, '') IS NOT NULL AND is_staff IS NOT NULL")
    return None if rows[0][0] == "NULL" else int(rows[0][0])


def fetch_logins(start: datetime, end: datetime) -> list[tuple[int, str | None, int | None]]:
    """Return (unix time, lowercased account or None, event-time staff flag or None)."""
    rows = run_query(
        "SELECT UNIX_TIMESTAMP(s.occurred_at), LOWER(NULLIF(s.account_name, '')), s.is_staff "
        "FROM session_audit_outcome s "
        f"WHERE s.event_type = {LOGIN_EVENT} "
        f"AND s.occurred_at >= FROM_UNIXTIME({int(start.timestamp())}) "
        f"AND s.occurred_at < FROM_UNIXTIME({int(end.timestamp())})")
    return [(int(when), None if account == "NULL" else account, None if staff == "NULL" else int(staff))
            for when, account, staff in rows]


def daily_counts(logins, days: list[date], zone: ZoneInfo) -> tuple[list[dict], int]:
    """Count unique accounts and logins per local day; also return logins with no account."""
    accounts: dict[date, set[str]] = {day: set() for day in days}
    logins_per_day = dict.fromkeys(days, 0)
    unmapped = 0
    for when, account, is_staff in logins:
        day = datetime.fromtimestamp(when, zone).date()
        if day not in accounts:
            continue
        if account is None or is_staff is None:
            unmapped += 1
        elif not is_staff:
            accounts[day].add(account)
            logins_per_day[day] += 1
    rows = [{"date": day.isoformat(), "unique_accounts": len(accounts[day]), "logins": logins_per_day[day]}
            for day in days]
    return rows, unmapped


def write_json(path: Path, value: dict) -> None:
    """Replace the file in one step so the web server never serves half of it."""
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def export(output_dir: Path, zone_name: str, days: int, today: date) -> int:
    zone = ZoneInfo(zone_name)
    last = today - timedelta(days=1)
    first = last - timedelta(days=days - 1)
    earliest = first_login_time()
    if earliest is not None:
        first = max(first, datetime.fromtimestamp(earliest, zone).date())
    if earliest is None or first > last:
        print("no complete day of login data yet; nothing written", file=sys.stderr)
        return 0

    window = [first + timedelta(days=offset) for offset in range((last - first).days + 1)]
    logins = fetch_logins(datetime.combine(first, time(), zone),
                          datetime.combine(last + timedelta(days=1), time(), zone))
    rows, unmapped = daily_counts(logins, window, zone)
    if unmapped:
        print(f"{unmapped} logins had no identity snapshot and were left out", file=sys.stderr)

    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "history.json", {"timezone": zone_name, "generated_at": generated_at, "days": rows})
    write_json(output_dir / "latest.json", {"timezone": zone_name, "generated_at": generated_at, **rows[-1]})
    print(f"{rows[-1]['date']}: {rows[-1]['unique_accounts']} accounts, {rows[-1]['logins']} logins")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output-dir", type=Path, required=True, help="directory the website serves")
    parser.add_argument("--timezone", default="UTC", help="IANA zone that defines a day (default UTC)")
    parser.add_argument("--days", type=int, default=90, help="complete days to include (default 90)")
    args = parser.parse_args(argv)
    if args.days < 1:
        parser.error("--days must be at least 1")
    try:
        today = datetime.now(ZoneInfo(args.timezone)).date()
    except (ZoneInfoNotFoundError, ValueError):
        parser.error(f"unknown time zone: {args.timezone}")
    return export(args.output_dir, args.timezone, args.days, today)


if __name__ == "__main__":
    sys.exit(main())
