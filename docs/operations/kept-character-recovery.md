# Recovering a historical kept character

`keptchar` is an OVERLORD command for a broken, unentered character. Normal kept
characters resume through their account; they do not need this command.

Inspect an exact PID and expected spelling first:

```text
keptchar inspect 42 Taverek
```

The report includes owner, mapping owner, active/tombstone state, level, saved
revision, usable snapshot and monetary-domain availability, identity conflicts,
and live/pending work. `-` means no saved owner. Inspection does not attach or
delete anything. Native readers may finish an already committed authority journal.

Verify ownership from the incident record, an authenticated account and independent
ownership evidence. A matching name, IP, creation time or level alone is insufficient.
Record the evidence outside the game and supply its reference:

```text
keptchar attach 42 Taverek Verifiedacct issue-612-case-42
```

Attachment preserves the PID, chosen stats, items, balances and approval flags.
It accepts an empty or matching owner and repairs only this PID's membership.
MariaDB reuses the existing guarded baseline/projection repair inside the same
transaction. The native backend requires the original usable snapshot and matching
existing monetary domains; it commits a guarded identity after-image. Missing or
corrupt financial authority is not replaced with guessed balances. Re-login to
refresh an already open account menu.

If the snapshot is genuinely absent, the command cannot restore its lost stats.
Restore only from verified existing recovery evidence, or explicitly release the
broken attempt after confirming that this is the intended disposition:

```text
keptchar release 42 Taverek Verifiedacct issue-612-case-42-release
keptchar release 43 Veralis - issue-612-case-43-release
```

The owner argument must match the inspection (`-` for an ownerless row). Release
uses the normal character deletion, custody cleanup and tombstone machinery.
It forgets the live name index only after durable success. A later claimant uses
a new PID; the retired PID remains fenced by its tombstone. MariaDB retains that
tombstone under an internal retired spelling when the original name is reused.
No new character receives the old snapshot or ownership.

Mutations refuse established characters, accepted names, completed approval
metadata, conflicting owners/names, corruption or I/O uncertainty, live bodies,
queued saves, critical operations and unresolved starter grants. A complete usable
owned character cannot be released through this repair command. A missing native
identity or missing financial authority may require a verified backup rather than
release. Repeating an attachment converges on the same ownership; repeating a
release either confirms/refuses the tombstone without touching a replacement.

Wait for the committed result. On refusal or failure, inspect again before retrying.
A rollback retains the original character. An uncertain MariaDB commit reconciles
on the writer; a disconnected staff session does not cancel admitted work. The audit
log records staff identity, action, PID, account, evidence reference and result.

After attachment, check fresh account selection, the same PID and all ten stats,
required approval, and first entry. After release, check storage tombstones and name
availability, then verify that an old save cannot resurrect the retired PID. Also
check after a cold restart.

Keep `CRITICAL_COMMAND_JOURNAL_DIR/starter-kits/` with database/native backups. Its
checksummed records bind first grants to exact operation IDs and item UIDs. Never
delete pending, rejected or damaged records to force another kit. Investigate the
existing item-transfer receipt and repair storage evidence before retrying. Completed
records remain necessary after items have been consumed. Backup captures these
records before the authority snapshot; the restore qualifier validates them.

This command does not authorize production repairs. Production inspection or
mutation still requires the owner's permission. Examples above are synthetic.
