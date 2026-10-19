#!/usr/bin/env python3
"""Validate the curated epic-task roster; emit reviewed SQL without connecting."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

from epic_zone_seed import parse_stones, parse_zones

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "migrations/seeds/epic_task_zones.json"


def roster(root: Path = ROOT, manifest: Path = MANIFEST) -> list[int]:
    data = json.loads(manifest.read_text())
    numbers = data["zone_numbers"]
    if (data["format_version"] != 1 or not numbers or len(numbers) > 1024
            or any(type(n) is not int or not 0 < n <= 2147483647 for n in numbers)
            or numbers != sorted(set(numbers))):
        raise ValueError("task roster must contain sorted, unique positive zone numbers")
    # Eligibility comes only from the reviewed manifest. Active world/stone
    # validation detects stale entries; it never expands the curated roster.
    stones = parse_stones((root / "src/world/epic.h").read_text())
    active = {}
    for line in (root / "areas/AREA").read_text().splitlines():
        if not line.strip() or line.startswith("*"):
            continue
        name = line.split()[0]
        if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
            raise ValueError(f"invalid area-list entry: {name}")
        path = root / "areas/zon" / (name + ".zon")
        zones = parse_zones(path.read_text(encoding="latin-1"), str(path.relative_to(root)), stones)
        if active.keys() & zones.keys():
            raise ValueError("duplicate zone number in active world")
        active.update(zones)
    invalid = [n for n in numbers if n not in active or not active[n]["stones"]]
    if invalid:
        raise ValueError(f"task zones missing from active world or without stone loads: {invalid}")
    return numbers


def audit_sql(numbers: list[int]) -> str:
    seed = " UNION ALL ".join(f"SELECT {n} AS number" for n in numbers)
    return f"""-- Read-only: every curated zone, plus currently enabled zones outside the roster.
WITH seed AS ({seed})
SELECT s.number, COUNT(z.id) AS actual_rows, MIN(z.task_zone) AS task_zone,
       CASE WHEN COUNT(z.id) = 0 THEN 'missing'
            WHEN COUNT(z.id) > 1 THEN 'duplicate-number'
            WHEN MIN(z.task_zone) = 1 THEN 'enabled'
            WHEN MIN(z.task_zone) = 0 THEN 'disabled-review-before-enabling'
            ELSE 'invalid-flag' END AS status
FROM seed s LEFT JOIN zones z ON z.number = s.number GROUP BY s.number
UNION ALL
SELECT z.number, COUNT(*), MIN(z.task_zone), 'outside-roster-preserved'
FROM zones z WHERE z.task_zone = 1 AND z.number NOT IN (SELECT number FROM seed)
GROUP BY z.number ORDER BY number;
"""


def apply_sql(numbers: list[int], database: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_]+", database):
        raise ValueError("database must contain only letters, digits, and underscore")
    values = ",".join(f"({n})" for n in numbers)
    return f"""-- Explicit reviewed roster restoration only. Verify a fresh backup first.
-- Never use mysql --force. No inserts, payouts, history, balances or exclusions change.
CREATE TEMPORARY TABLE _duris_task_seed (number INT PRIMARY KEY) ENGINE=InnoDB;
INSERT INTO _duris_task_seed VALUES {values};
CREATE TEMPORARY TABLE _duris_task_guard (ok INT PRIMARY KEY) ENGINE=InnoDB;
INSERT INTO _duris_task_guard VALUES (1);
SET SESSION innodb_lock_wait_timeout = 5;
SET TRANSACTION ISOLATION LEVEL SERIALIZABLE;
START TRANSACTION;
SELECT id AS locked_zone_id FROM zones ORDER BY number FOR UPDATE;
SET @duris_task_seed_ok = (
  COALESCE(CAST(DATABASE() AS BINARY) = CAST('{database}' AS BINARY), 0)
  AND (SELECT COUNT(*) FROM information_schema.tables
       WHERE table_schema = DATABASE() AND table_name = 'zones' AND engine = 'InnoDB') = 1
  AND NOT EXISTS (SELECT number FROM zones GROUP BY number HAVING COUNT(*) > 1)
  AND (SELECT COUNT(*) FROM zones z JOIN _duris_task_seed s ON s.number = z.number
       WHERE z.task_zone IN (0,1)) = {len(numbers)}
);
-- Duplicate-key failure aborts a batch client before mutation; also guard the DML.
INSERT INTO _duris_task_guard SELECT 1 WHERE NOT @duris_task_seed_ok;
UPDATE zones z JOIN _duris_task_seed s ON s.number = z.number
SET z.task_zone = 1 WHERE @duris_task_seed_ok AND z.task_zone = 0;
SELECT ROW_COUNT() AS enabled_task_zones;
COMMIT;
DROP TEMPORARY TABLE _duris_task_guard;
DROP TEMPORARY TABLE _duris_task_seed;
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["check", "sql-audit", "sql-apply"])
    parser.add_argument("--database", help="exact target database; required for sql-apply")
    args = parser.parse_args()
    if (args.command == "sql-apply") != bool(args.database):
        parser.error("--database is required only for sql-apply")
    try:
        numbers = roster()
        if args.command == "check":
            print(f"{len(numbers)} curated task zones exist with active stone loads")
        else:
            print(audit_sql(numbers) if args.command == "sql-audit"
                  else apply_sql(numbers, args.database), end="")
    except (ValueError, KeyError, TypeError, OSError) as error:
        print(f"epic-task seed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
