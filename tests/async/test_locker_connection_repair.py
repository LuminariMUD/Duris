#!/usr/bin/env python3
"""A locker save's failed connection is rolled back and replaced like every writer job's."""
from _paths import SRC

locker = (SRC / "locker_async.c").read_text(encoding="utf-8", errors="replace")
repository = (SRC / "player_snapshot_repository.c").read_text(encoding="utf-8", errors="replace")


def body(text, signature):
    start = text.index(signature)
    end = text.index("\n}\n", start) + 3
    return text[start:end]


pool = body(repository, "template <typename Apply> player_save_apply_result apply_with_pool(")
owner_write = body(repository,
                   "template <typename Write> player_save_apply_result apply_owner_write(")
write_job = body(locker, "static player_save_apply_result locker_write_job(")
checks = {
    "the locker save runs through the pooled repository apply":
        "apply_with_pool([&](MYSQL *connection) { return apply_locker(connection, locker); })"
        in repository,
    "a lost or ambiguous connection is replaced before it goes back to the pool":
        "sql_pool_replace_connection(connection)" in pool
        and "applied.outcome == player_save_apply_outcome::ambiguous_commit" in pool,
    "a failed write is rolled back": 'execute(connection, "ROLLBACK")' in owner_write,
    "a lost connection goes back to the writer before any result is reported":
        write_job.index("player_save_apply_outcome::retryable_failure")
        < write_job.index("g_results.push_back(res)"),
    "no multi-statement script is built or replayed": "apply_sql_script" not in locker,
}

for name, ok in checks.items():
    print(("PASS" if ok else "FAIL") + ": " + name)

raise SystemExit(0 if all(checks.values()) else 1)
