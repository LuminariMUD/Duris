# Online migrations and activation prerequisites

Read this for pending migrations or a possible activation constraint. Apply
required migrations with the database, MUD and website running under the existing
deployment authorization. The user owns the in-game reboot.

## Finish the preparation that can be done now

Prepare the integrated source, production binary/stamp, generated world/lookups,
content previews, configuration changes and recovery files. Keep incompatible
artifacts outside live promotion paths. Publishing a new boot contract can make
an otherwise healthy running service unable to restart; account for that before
updating the live checkout. Do not weaken an existing startup guard to hide drift.

Use the live baseline and ordered migration IDs/checksums to identify the exact
pending prefix. Inspect its SQL and the candidate's runtime contract. Record the
specific requirement that is unmet; do not infer a maintenance need merely from
the presence of a migration file or an additive schema change.

## Apply migrations online

Do not stop the database service or require all clients to disconnect as a default
migration step. SQL migrations execute against the running database. A runner's
blanket zero-connection guard is a tooling policy, not a property of every ALTER.
Use the current runner and [migration guide](../../../../docs/persistence/IMMUTABLE_MIGRATIONS.md)
for interfaces and ledger semantics; assess downtime from the actual operation.

1. Review each pending step against the deployed writers and candidate readers,
   including DurisWeb. Check column naming/order assumptions, defaults, queries,
   constraints and any backfill's behavior under concurrent writes. An additive
   column with a compatible default can be online; the word "additive" alone is
   insufficient evidence. Account for the old binary's next-boot schema contract.
2. Check the actual server version, engine and affected tables. Select supported
   online DDL: require INSTANT where appropriate, or an explicitly supported
   operation that permits concurrent reads/writes. Bound metadata/row lock waits
   and reject fallback to a blocking table copy. Online DDL can briefly acquire
   metadata locks; waiting connections alone do not prove an outage is necessary.
3. Reuse an existing online runner path when it covers the exact pending steps.
   If support is missing, implement the smallest scoped path in the release
   workspace for the reviewed migration IDs/checksums and engine capabilities.
   Preserve production target confirmation, allow-list, fresh backup, baseline,
   immutable prefix checks, verification and success-last ledger recording. Hold
   the migration advisory lock on one live connection through apply, verification
   and history publication. Retain the default guard for unreviewed operations.
   Validate this change with focused database-free checks; no production test DB,
   full qualification suite or new test infrastructure is required.
4. Take and verify the live backup, coordinate schema-aware backup jobs so none
   overlaps DDL, then execute through the reviewed runner. Verify ordered history,
   migration state and the candidate runtime contract before publication. Restore
   held backup schedules using the new verified contract.

Existing migration-specific options are not general online switches. For example,
`--online-level-cap-sides` is scoped to 0039; a later compatible step needs its own
reviewed support, not a declaration that all clients must stop. Do not fabricate
an available flag, disable checks globally, impersonate a local environment,
execute untracked SQL or edit ledger rows to bypass the runner.

On lock timeout, inspect the holder and retry only when the observed contention
has cleared. On apply/verification failure, inspect live schema and ledger state
before any retry: DDL may already have committed. If an actual writer conflict,
unsupported online operation or required service replacement prevents completion,
retain the preparation and report that exact constraint once. A missing online
flag or generic zero-client refusal by itself is not such a constraint.

The production launcher verifies schema but does not apply pending migrations;
finish the online migration before handing the user their reboot.

## Other activation constraints

An in-game reboot also does not replace the already-running launcher or restart
systemd. Trace configuration and listener changes to the process that must read
them; report an actual new-process requirement instead of promising the reboot
will apply every changed file.

## Preserve the exact recovery and operation details

Use `scripts/backup_pfiles.sh` under the approved backup policy. If the checkout's
contract is newer than the database, use an owner-only copy of the verified
deployed manifest through `RUNTIME_COMPATIBILITY_MANIFEST` when invoking it.

Verify generation metadata, file checksums and `database.sql.gz`. Preserve the
running executable as regular bytes, its stamp/map, configuration/content and
filesystem/journal evidence. Old code can reject an additively upgraded schema;
restoring the old executable alone does not restore bootability. The runner has
no automatic down-migration. No restore drill, disposable database,
Docker, special mount, namespace, or external test host is required here.

For a pending migration, record the exact database host/port/socket/name and
allow-list, IDs/checksums, shared clients, backup location and runner invocation.
The runner reads exported environment, not `.env` automatically. Its production
flags are `--confirm-production-target HOST/DB` and
`--production-backup /absolute/path/database.sql.gz`. The backup must be an
owner-only regular gzip owned by the invoking user, no more than two hours old,
with the configured database/core-table markers. A verified transactional live
backup is appropriate for the reviewed online path; stopped writers are not a
blanket backup prerequisite. Refresh an expired backup before applying migrations.
Successful application must be followed by ordered history/state checks and
`migrations/verify_runtime_compatibility.sh`.

For content, retain reviewed previews and prior rows. For a stopped-server seed,
retain its scoped SQL and audit. For service changes, retain the reviewed unit or
configuration diff, installed state and precise activation requirement. Consult
the owning runbook for details, without executing its stop/start procedure.

## Report once and hand back

State what preparation is complete, where the artifacts and recovery copies are,
and exactly what prevents reboot readiness. Label the result **prepared, but not
ready for reboot**; do not give the reboot command as an actionable final step
until its prerequisites pass.

Do not request a maintenance window, create a watchdog pause, stop clients, or
wait/poll for the user to authorize an expanded task. End with the concrete
prerequisite. Executing maintenance requires a separate explicit user instruction;
it is not a branch that `$deploy-production` enters automatically.
