#!/usr/bin/env python3
"""Poll times are the UNIX seconds their INT columns hold.

polls.created_at, polls.expires_at and poll_votes.voted_at are INT columns, but the MariaDB
poll code wrote them with FROM_UNIXTIME() and read them with UNIX_TIMESTAMP(). Under the
runtime's strict sql_mode the insert of a poll or a vote failed ("Out of range value"), a
row written as seconds read back as NULL (and atol(NULL)), and `expires_at >
FROM_UNIXTIME(now)` hid every active poll. The code now writes and compares the seconds.
"""
from pathlib import Path

from _source_contract import strip_comments

SRC = Path(__file__).resolve().parents[2] / "src"
code = strip_comments((SRC / "net/poll.c").read_text())
for conversion in ("FROM_UNIXTIME", "UNIX_TIMESTAMP"):
    assert conversion not in code, f"poll.c converts its INT times with {conversion}"
schema = (Path(__file__).resolve().parents[2] / "migrations/bootstrap_multithread_safe.sql").read_text()
polls = schema[schema.index("CREATE TABLE `polls`"):]
assert "`created_at` int NOT NULL" in polls[:polls.index(";")]
assert "`expires_at` int NOT NULL" in polls[:polls.index(";")]
votes = schema[schema.index("CREATE TABLE `poll_votes`"):]
assert "`voted_at` int NOT NULL" in votes[:votes.index(";")]
print("[PASS] poll times are written and read as the INT seconds the columns hold")
