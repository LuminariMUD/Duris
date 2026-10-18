# Immutable Migration Ledger

Duris has two deliberately separate histories:

- `migrations/run_migration.sh` is the legacy additive upgrade path. Its 145 progress
  steps and `mud_schema_migrations` data-copy markers are not complete historical
  execution evidence and are never backfilled as if they were.
- `migrations/migration_manifest.json` is the authoritative immutable history after
  the baseline. Every post-baseline step receives one ordered ID, apply file,
  verifier, compatibility label, and exact SHA-256 hashes.

## Honest baseline adoption

The checked-in baseline identifies the exact 170-table authoritative contract by a
sealed positive table inventory and sorted-name fingerprint. A fresh bootstrap and a
fully completed legacy upgrade must contain that complete inventory. Unrelated tables
from a combined game/website dump may coexist without weakening the canonical check.
Only then may an operator record either
`fresh_bootstrap` or `verified_legacy_adoption` in `mud_schema_baselines`.

The legacy runner creates the ledger and attempts verified adoption only after its last
schema operation. Extra, missing, or renamed tables refuse adoption. This creates one
honest observation at the current boundary; it does not invent timestamps or checksums
for historical steps.

For a fresh isolated database:

```sh
mysql "$DB_NAME" < migrations/bootstrap_multithread_safe.sql
python3 scripts/migration_runner.py inspect
python3 scripts/migration_runner.py adopt --kind fresh_bootstrap
python3 scripts/migration_runner.py run
```

By default, the runner requires `ENVIRONMENT` to be local/development/test, a loopback `DB_HOST`,
a non-production database name, and explicit credentials. An owner-authorized
production `run` additionally requires the exact
`--confirm-production-target HOST/DB` and a fresh owner-only
`--production-backup /absolute/path.sql.gz`. Production baseline adoption remains prohibited, and
the default production path refuses to apply while another connection is using
the configured database. Isolated clone/restore qualification is separate work;
the deployment skill requires verified backups, not a restore-drill receipt.

For the reviewed `0039_level_cap_sides` addition on MariaDB 11.8, an explicit
`run --online-level-cap-sides` path retains the production target, allow-list,
fresh backup, sealed checksums, baseline, ordered history and success-last
verification requirements while allowing live connections. It accepts only the
manifest ending at the exact reviewed 0039 step and only an InnoDB `level_cap`.
It executes the unchanged sealed SQL with session `alter_algorithm=INSTANT` and
one-second metadata/InnoDB lock waits: an unsupported instant operation or lock
timeout fails rather than falling back to a table rebuild. The applying connection
holds the migration advisory lock through verification and history publication.
The equivalent `run --online-combat-outcome-allies` path accepts only the manifest
ending at the sealed `0040_combat_outcome_allies` step and an InnoDB
`combat_outcome` table on MariaDB 11.8. It uses the same INSTANT-only execution,
bounded lock waits and production safeguards. Select only one online option;
neither permits earlier pending steps or arbitrary later migrations.

Before using this path, verify the running writers name their `level_cap` columns
explicitly and remain compatible with the two default-zero additions. Coordinate
schema-aware backup jobs so a backup cannot straddle DDL, preserve the deployed
contract for the pre-change backup, and select the new contract after successful
live verification. Do not edit the immutable SQL or its recorded checksums.

For 0040, check that active `combat_outcome` writers name their columns explicitly
and readers tolerate the new `killer_allies INT UNSIGNED NOT NULL DEFAULT 0` column.
Zero represents an unknown historical ally count; the migration does not rewrite
rewards or infer eligibility for older kills. The default production guard remains
in place for unreviewed operations; other online migrations need their own review
and scoped runner support.

[RUNTIME_COMPATIBILITY.md](RUNTIME_COMPATIBILITY.md) states the current head and the
runtime table count. After the head is applied, the history singleton records the
applied count plus the exact history checksum. If a pre-b029
launcher already created the legacy `server_reboots`
shape, 0004 copies every lifecycle row into the canonical table and atomically
swaps it into place; an interrupted conversion can be retried without making the
legacy table unavailable or duplicating rows. 0006 creates the guild kingdom
realm table with a guarded `CREATE TABLE IF NOT EXISTS` and then converges a
database that already ran the deleted pre-registration
`migrations/kingdom_realms.sql`: that file carried no `COLLATE` clause, so its
table holds the character set's default collation instead of
`utf8mb4_unicode_ci`, and a guarded `CONVERT TO CHARACTER SET utf8mb4 COLLATE
utf8mb4_unicode_ci` brings it to the verified shape. Every column is an integer,
so the conversion changes no stored value, and on an already-correct table the
guard issues no `ALTER` at all, which is what keeps 0006 exactly re-runnable.

0007 replaces the `pkill_event.stamp` default. The column was created as
`DATETIME NOT NULL DEFAULT '0000-00-00 00:00:00'`, which a server enabling
`NO_ZERO_DATE` and `NO_ZERO_IN_DATE` refuses to load, and which pushed consumers
into relaxing their session SQL mode to write the table at all. Every current
writer supplies `NOW()` explicitly, so the default is only a safety net;
`CURRENT_TIMESTAMP` expresses that portably. Rows written before strict mode was
enabled may still hold the zero value and would fail the `ALTER`, so they are
first normalized to the epoch, which carries the same absence of information in
a form both engines accept. The guard reads the whole contract its verification
step asserts - `DATETIME`, `NOT NULL`, a current-timestamp default, and no
surviving zero-date rows - so a converged database issues no `ALTER` and the step
stays exactly re-runnable, while a partially converged one is still repaired.

0008 adds `idx_statistics_date` to the `statistics` population time series,
which carried only its primary key while every consumer filters an epoch range
on `date` and sorts chronologically. MySQL 8 has no portable
`CREATE INDEX IF NOT EXISTS`, so the guard reads `information_schema` first and
issues no `ALTER` when an index of exactly the verified shape - a single
non-unique entry on `date` - is present; an index of that name with any other
shape is dropped and rebuilt. The index is a structural
correction; its latency benefit has not been measured on a representative clone.

`kingdom_realms` is part of the boot contract's *table list*: both
normalized metadata fingerprints are sealed over an inventory that includes it,
so on the database backend the gate proves the table's engine, collation,
columns and indexes before gameplay publishes. `kingdom_initialize()` still
disables kingdoms for the boot when it cannot read the table, which remains
reachable on the flat-file build, where no boot gate stands in front of it. The
*ledger* is fail-closed too, exactly as it is for every other immutable
migration: `src/core/runtime_compatibility_contract.h` compiles
`RUNTIME_MIGRATION_HEAD_ID` and its sequence, and
`sql_verify_boot_database()` in `src/sql/sql.c` requires the matching
`mud_schema_history` row, its two checksums, and the applied count in
`mud_schema_migration_state`. On the MariaDB/MySQL backend a database left at
an older head therefore refuses to boot, aborting with
`COMPAT-E002`. An operator upgrading an existing database must apply the pending
migrations with
`python3 scripts/migration_runner.py run`, which applies the SQL, runs the
verifier, and only then writes the history row and advances the head, before
starting the server.

The remaining registered steps add the kingdom garrison roster (0009),
committed coin-pile custody payloads (0010), player death disposition and custody
evidence (0011), and atomic epic-stone reward claims (0012). Migration 0012 adds
one InnoDB table keyed by the stone's globally allocated UID, with a foreign
key to the critical-operation inbox. An existing database at head 0011 must
apply that step before deploying the current server.

Migration 0013 preserves generated pet state, and 0014 adds telemetry storage. Migration 0015 adds the independent
physical-item mana authority, keyed by UID and versioned separately from owner
snapshots. An existing database at head 0014 must apply 0015 before the updated
binary boots, even when item actions remain disabled. This additive table has no
owner foreign key or cascade: extraction and old snapshots must not remove its
replay fence. See [artifact mana](../reference/ARTIFACT_MANA.md) for the resource,
crash-window and rollback contracts.

Migration 0034 is the one step that removes data: it drops the death custody and
restitution tables (0011, 0020) and the economy accounting tables (0031, 0032), which
nothing reads since the persistence reset treats every server as new. It is guarded
and re-runnable (`DROP TABLE IF EXISTS`). Back up a database that may still hold that
evidence before running it.

Migration 0035 changes no table. Boot refuses an `account_banks` row without a
`currency_bank_baseline`, and from the persistence reset until the server
wrote the baseline with the bank, the delta that created a bank wrote none. The step
copies each such bank's current row into its baseline (`INSERT IGNORE ... SELECT`, so
it leaves existing baselines alone and re-runs), and its verifier requires every bank
to have one.

Migration 0036 widens `log_entries.ip_address` from `VARCHAR(15)` to `VARCHAR(45)`, as
`account_ips` has: `sql_log()` cut every IPv6 address to fit. The guard reads the column's
length and issues no `ALTER` once it holds 45, so the step re-runs, and its verifier checks
the shape. An existing database must apply it before the updated binary boots.

Migration 0037 adds nullable `account_name` and `is_staff` columns to
`session_audit_outcome`. Login commands capture them before queueing; existing
rows and version-1 replay retain NULL rather than inventing historical identity.
The additive migration guards each column separately and re-runs safely.
See [daily login statistics](../operations/LOGIN_STATS.md) for rollout and export.

Migration 0039 adds `level_good` and `level_evil` to `level_cap`, each `INT NOT NULL
DEFAULT 0`: the level a racewar side has unlocked beyond `level`, which stays the level
open to all. A side's cap is the higher of the two, so the 0 every existing row receives
keeps the live cap unchanged until the next unlock. The migration guards each column
separately and re-runs safely, and its verifier checks both shapes and that each side
level lies in 0-56. An existing database must apply it before the updated binary boots.

## Online player updates (0042/0043)

`run --online-player-updates` accepts only the manifest ending at the exact sealed
0042 and 0043 steps, with all earlier migrations already applied. It retains the
production target, allow-list, fresh backup, checksums, persistent advisory lock,
ordered ledger and success-last verification. It requires MariaDB 11.8 and InnoDB
`player_data`; metadata and row-lock waits are bounded to one second.

0042 widens ten signed TINYINT base stats to signed SMALLINT. This needs COPY,
which MariaDB 11.8 supports online. After checking the sealed payload checksum,
the runner strengthens its single generated `ALTER TABLE player_data` to
`ALTER ONLINE TABLE player_data` (LOCK=NONE). It refuses unsupported online shapes,
including outgoing cascading foreign keys, rather than falling back to blocked
writers. The immutable file and ledger checksum remain unchanged. 0043 executes
its sealed SQL unchanged under INSTANT-only DDL, adding the default-empty news
acknowledgement column. Neither path disables foreign-key checks.

Before use, inspect the live table and running writers: stat widening preserves
old values, and named-column inserts/updates tolerate the added column. On the
2026-10-16 deployment, `player_data` had 67 rows, ten nullable signed TINYINT stats
with default 0, no outgoing foreign keys, and no news acknowledgement column.
Its incoming cascading references do not modify the table being copied. Coordinate
schema-aware backup jobs across both migrations and verify the new runtime contract
before installing the server. A lock timeout or unsupported online operation leaves
the game running for diagnosis.

Reference: [MariaDB online schema change](https://mariadb.com/docs/server/reference/sql-statements/data-definition/alter/alter-table/online-schema-change).

## Post-baseline migration contract

`run --online-artifact-pvp` accepts only the sealed manifest ending at 0045,
with all steps through 0043 already applied. It retains production target,
allow-list, backup, checksum, advisory-lock, ordered-history and success-last
verification safeguards. On MariaDB 11.8 InnoDB it strengthens the exact 0044
and 0045 ALTER statements to `ALTER ONLINE TABLE` (`LOCK=NONE`), with one-second
metadata and row-lock waits. 0044 uses NOCOPY for its appended columns and unique
index; 0045 uses INSTANT. Unsupported operations fail without a table-copy or
offline fallback. The sealed files and ledger checksums do not change.

The October 18 production review found 90 artifact rows and 11 PvP rows, both
InnoDB, with the additions absent. Existing artifact and combat writers name
their columns explicitly; NULL/0 defaults preserve unresolved identity and
unknown consent until the new runtime writes them. The artifact custody FK is
retained. Coordinate schema-aware backup jobs across the migration and verify
the new runtime contract before installing the server. See MariaDB's
[NOCOPY online DDL documentation](https://mariadb.com/docs/server/server-usage/storage-engines/innodb/innodb-online-ddl/innodb-online-ddl-operations-with-the-nocopy-alter-algorithm).

Migration 0045 appends `pkill_info.webinfo_at_capture TINYINT NULL DEFAULT NULL`
at position 11. The verifier requires its exact signed, nullable/default-NULL
shape and position. Replays preserve existing values and snapshots; old rows
and old-writer inserts retain unknown consent. No current player flag is used
to backfill permission. The v4 combat writer records NULL/0/1 with each owned
snapshot in the existing transaction. See the
[PvP implementation and rollout plan](../records/2026-10-18-pvp-mud-implementation-plan.md).

Migration 0044 adds canonical artifact UID/state fields to the existing
`artifact_domain_state` store. It retains `item_uid` and its custody FK: the
canonical physical UID must also represent unclaimed NPC/ground items without
inventing custody. Old rows receive NULL/0 (unresolved), with no automatic
canonical selection or data cleanup. A unique key prevents one non-null canonical
UID from naming two vnums, and retired UIDs remain representable. Column/index
guards replay partial DDL; the verifier checks their full shape, preserves the
custody FK, and refuses inconsistent state/UID pairs. Apply it before starting
the updated database-backed server. See the [artifact plan](../ongoing-projects/plan-issue-67.md)
for the separate runtime/admission/reconciliation acceptance work.

Migration 0046 restores only Nexus IDs 1 (Marduk) and 3 (Enlil), with explicit
zero stat fields and the existing epic/cargo bonus assignments. Its SQL checks
both existing IDs and reserved names before inserting either missing row. A
configuration conflict raises a field/ID-specific error; matching rows retain
alignment and last-touch state. The verifier accepts legitimate played state and
unrelated rows. Reapplying the payload completes a partial insert without resetting
the first row; replaying recorded history remains a no-op. Runtime activation needs
a controlled restart because SQL Nexus records are cached at boot.

Files live under `migrations/immutable/` and are listed explicitly in the manifest.
Before opening a database, the runner reads every file with no-follow and fixed-size
limits and rejects duplicate JSON keys, invalid paths, missing/duplicate/reordered IDs,
unknown fields, and checksum changes.

At runtime it acquires one database lock, verifies the adopted baseline, validates the
entire applied prefix, and checks the singleton history count/head checksum. For each
pending migration it runs apply, then verifier, and only then atomically inserts the
history row and advances the history head. A verifier failure leaves the step
unrecorded. The migration itself must therefore be additive and re-runnable so an exact
retry can finish partial MySQL DDL safely.

Every runner mode holds that advisory lock on a persistent, non-reconnecting client
through the complete operation. A one-shot `mysql -e GET_LOCK` would release it before
the first apply. All runner SQL, including apply and history publication, executes on
the lock-owning session, so killing that session also interrupts its SQL and prevents
later statements in the batch from writing after a competing runner acquires the lock.
The runner also checks ownership before and after SQL and the external read-only
verifiers, including server-side loss where the client process has not exited.
Ordinary production quiescence excludes its own session; any other connection to the
target database still refuses the operation. Any interrupted apply must be recovered
by its guarded retry, not assumed rolled back.

Editing or reordering an applied row fails against the manifest. Deleting even the
trailing row fails against the retained history count/head rather than silently
reclassifying it as pending. Exact replay with a complete prefix performs no work.

## Supported engines

MySQL 8.0, MariaDB 10.11 and MariaDB 11.8. The verifiers of `0031_economy_accounting` and
`0032_economic_baseline` hash their tables' metadata against one fingerprint per engine,
and they know only MariaDB 10.11 and MySQL 8.0; on any other version they refuse. A
sealed verifier cannot change, since every database's history holds its checksum, so
the manifest's `engine_verifiers` list names a verifier of its own for MariaDB 11.8
(`immutable/0031_economy_accounting_mariadb_11_8.sh` and
`immutable/0032_economic_baseline_mariadb_11_8.sh`),
with its own checksum. The runner asks the server's `VERSION()` and runs that verifier
in place of the sealed one on 11.8 only; the history row keeps the sealed verifier's
checksum, so a history is the same on every engine. Their 11.8 fingerprints are
10.11's. Another engine needs the same: a verifier per migration that refuses it, and
an entry in `ENGINE_VERSIONS` in `scripts/migration_runner.py`.

## Verification

```sh
python3 tests/async/test_immutable_migration_runner.py
tests/async/run_legacy_migration_mysql.sh
tests/async/run_immutable_migration_ledger_mysql.sh
tests/async/run_runtime_compatibility_mysql.sh
RUNTIME_DB_IMAGE=mariadb:10.11 tests/async/run_runtime_compatibility_mysql.sh
RUNTIME_DB_IMAGE=mariadb:11.8 tests/async/run_runtime_compatibility_mysql.sh
python3 tests/async/run_migration_runner_engines.py
```

The isolated MySQL tests verify the full legacy upgrade, exact fresh-bootstrap
equivalence, replay, schema compatibility, ordered uniqueness, honest baseline kind
uniqueness, preservation of legacy data-copy markers, and record-preserving
convergence of the pre-b029 `server_reboots` table on the supported engines.
`run_migration_runner_engines.py` builds a database through the runner on each of the
three, checks that all reach the same history checksum, and that an edited history row
stops the runner.
