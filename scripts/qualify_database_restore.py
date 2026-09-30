#!/usr/bin/env python3
"""Complete migration-history and aggregate value-domain restore verification."""
import os
import sys
import migration_runner as migrations


def main():
    if os.environ.get("DB_NAME") != "duris_restore" or not os.environ.get("DB_SOCKET"):
        raise RuntimeError("isolated_restore_connection_required")
    manifest = migrations.load_manifest()
    executor = migrations.MysqlExecutor(manifest)
    executor.command.insert(1, "--no-defaults")
    executor.require_baseline(manifest)
    if migrations.validate_applied_prefix(manifest, executor.applied()):
        raise RuntimeError("restore_migration_history_incomplete")
    queries = [
        "SELECT COUNT(*) FROM artifact_mana WHERE item_uid=0 OR profile_id=0 OR profile_revision=0 "
        "OR version=0 OR capacity=0 OR capacity>1000000000000 OR regeneration>1000000000 "
        "OR reserve>capacity;",
        "SELECT COUNT(*) FROM account_characters c LEFT JOIN accounts a ON a.account_name=c.account_name "
        "LEFT JOIN player_data p ON p.pid=c.pid WHERE c.deleted_at IS NULL AND "
        "(a.account_name IS NULL OR p.pid IS NULL OR (p.account_name IS NOT NULL AND p.account_name<>c.account_name));",
        # Wallets, banks, epic points and frags are memory's and the saves write them
        # (persistence reset Phase 2), so their ledgers are history, not a check on them.

        # This is a conservative generation invariant. It is deliberately
        # separate from persistence_restore.tombstone_preflight(), which
        # validates fresh external evidence and its authority.
        "SELECT COUNT(*) FROM account_erasure_tombstones;",
    ]
    for query in queries:
        if executor.sql(query) != "0":
            raise RuntimeError("restore_reconciliation_failed")
    print('{"history":"ok","reconciliation":"ok"}')


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("database_restore_qualification_failed", file=sys.stderr)
        raise SystemExit(1)

