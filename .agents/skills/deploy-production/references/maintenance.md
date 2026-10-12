# Migration and activation prerequisites

Read this when assessing a pending migration, stopped-server seed, incompatible
recovery change, or new launcher/service requirement. Complete supported online
work under the deployment authorization. Report only constraints that remain
after that assessment; this reference does not authorize stopping services.
The user owns the in-game reboot.

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

The production immutable runner normally requires zero other database connections.
Before treating that as a blocker, check its supported online paths. The reviewed
`run --online-level-cap-sides` path applies only the sealed `0039_level_cap_sides`
addition on MariaDB 11.8/InnoDB. Follow its running-writer compatibility, fresh
backup, advisory-lock and instant-DDL requirements in
[IMMUTABLE_MIGRATIONS.md](../../../../docs/persistence/IMMUTABLE_MIGRATIONS.md).
When those requirements hold, deployment authorization covers completing this
online prerequisite with services running. Verify the new contract and finish
publication before handing the user the reboot command.
The option requires the manifest to end at that exact reviewed step; it is not a
general online-migration switch for later releases. Inspect the current runner
and live history rather than assuming 0039 is still pending.

An arbitrary additive ALTER does not waive the default guard. Do not run individual
SQL files, edit migration history, adopt a baseline, or stop clients to get past it.
The production launcher verifies the schema but does not apply pending migrations,
so the user's ordinary reboot cannot finish them automatically.

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
allow-list, IDs/checksums, shared clients, backup location and runner invocation
for the operator's later work. The runner reads exported environment, not `.env`
automatically. Its production flags are `--confirm-production-target HOST/DB` and
`--production-backup /absolute/path/database.sql.gz`. The backup must be an
owner-only regular gzip owned by the invoking user, no more than two hours old,
with the configured database/core-table markers. A later operation may need a
fresh backup after writers are quiescent; do not present a live snapshot as that
final stopped-writer backup. Successful application must be followed by ordered
history/state checks and `migrations/verify_runtime_compatibility.sh`.

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
