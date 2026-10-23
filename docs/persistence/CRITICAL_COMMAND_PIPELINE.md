# Critical Command Pipeline

Persisted domain commands use one bounded command contract. Each command has a
cryptographically random 128-bit operation ID, a schema and payload version, a
categorical source site and deadline, sorted affected entity keys, optional expected
revisions, and owned payload bytes. It contains no live game pointers, SQL, Redis keys,
paths, account names, or character names.

In SQL-backed builds, the destination stores command identity and result in an
InnoDB inbox, applies the typed domain mutation or history record, and writes its
outbox record in the same transaction. Outside mini mode, SQL startup requires
the verified critical-command schema. Flat-file builds select
`flatfile_critical_command_repository_apply_selected` and do not start the SQL
outbox worker; each domain still has its own capability and persistence rules.
Coordinator initialization failure leaves critical gameplay stopped. Critical
envelopes carry typed payloads; ordinary SQL-backed snapshots can still queue
owned SQL statements through `sql_async`.

## Domains

| Command | What its transaction commits | Entity keys |
|---|---|---|
| Item grant, operator repair and destruction | Current owner (`item_current_owner`) and transfer history (`item_ownership_ledger`) | item + owners |
| Auction | auction, custody and ledger rows | auction + item + players/accounts |
| Collector | the listing, its item custody and ledger rows | listing + player/account + items |
| Shop trade (flat-file backend only) | the trade and its item custody | player + shopkeeper + items |
| Boon shop (flat-file backend only) | the purchase | player |
| PvP/combat outcome | `pkill_event`, `pkill_info`, `combat_outcome`, frag and epic ledgers, frag leaderboard | all participant players |
| Artifact/guild | captured reward history only; artifact/guild snapshots save state ([branch status below](#artifact-and-guild-rewards-live-in-memory)) | actor + artifacts + guild |
| Boon reward | progress and bounded outcomes | player |
| Zone touch | zone, history, alignment, participants | zone + participants |
| Epic | `epic_ledger` history only; the balance is the save's ([below](#epic-points-and-frags-live-in-memory)) | player |
| Session audit | `session_audit_outcome` | player |

Wallets and banks are not commands ([Money lives in memory](#money-lives-in-memory)).
Fan-out is bounded at 15 participants or artifacts and 32 boon results per command.

## Acceptance and execution

The coordinator validates and normalizes an envelope before admission. Entity keys
are sorted and duplicates are rejected. It reserves bounded memory, fences the
command's keys, and queues it on the one persistence writer
(`persistence_job_kind::critical`), the same thread that applies every save. A command
therefore lands in capture order with the saves around it: a save captured before the
command is applied before it, one captured after, after it. `submit()` returns
`accepted`; the command is durable once the writer has applied it. Commands are not
journaled: like a save, a command that had not reached the database is lost in a crash
(see [ADR 0002](../adr/0002-persistence-reset-memory-is-the-authority.md#consequences)).
Records are never coalesced or replaced by a newer command.

The writer job carries its own copy of the command and of the apply function, so a
command queued before shutdown still lands after the coordinator has stopped; its
completion is then not delivered. The writer retries a lost connection, a lock wait or an
ambiguous commit at the head of its queue, before anything queued after the command,
exactly as it retries a save. Any other outcome is handed to the coordinator's
completion channel.

The state and transition table is deliberately split between the coordinator's
command lifecycle and a domain's live-publication lifecycle. The
`critical_completion_delivery` boundary owns bounded completion retention and
queue operations; the coordinator owns fencing and terminal transitions.
There is no second generic lifecycle framework hidden behind the domain adapters.

| State | Owner | Durable evidence and allowed transition |
| --- | --- | --- |
| Queued on the writer | Coordinator plus the persistence writer | The operation is reserved in bounded memory and fenced on every key; the writer applies it in capture order through the typed domain adapter. A domain transaction/flat-file authority and its inbox/result are the durable evidence; the coordinator receives an exact revisioned completion. |
| Retried by the writer | Persistence writer | A lost connection, lock wait or ambiguous commit is applied again with the same operation ID before anything queued after it, until it lands. The fence remains. A command whose outcome never becomes known is named at shutdown with what the writer could not write. |
| Final notification retained | `critical_completion_delivery` plus coordinator pulse | The exact operation ID, outcome, and durable revision remain queued until the simulation-thread consumer supplies capacity. Consumer backpressure cannot cause a final result to be discarded; publication then releases or preserves the appropriate fence. |
| Snapshot pending and outbox pending | Snapshot and outbox subsystems | Snapshot capture/replay and outbox delivery have their own owners, records, and recovery rules. They do not coalesce critical commands. |

The writer applies commands one at a time in acceptance order, so conflicting commands
never overlap. The fence exists from acceptance until the game thread takes the
completion, or, for a command held for publication, until it acknowledges the
publication. `critical_command_coordinator_is_fenced()` reports it, so callers do not
build a command from a view another command is changing. A completion with the wrong
operation ID or attempt is stale and cannot release anything.

An identical duplicate submission attaches to the active operation or the bounded
recent-completion cache. Reusing an ID with different bytes fails closed. Accepted
commands cannot be cancelled. A terminal destination failure is reported once.

Default bounds are 1,024 active operations, 64 MiB of command memory, 2,048 pending
completion records, and a 256-operation/8 MiB recent-completion cache. Accepted work is
never dropped because the writer is behind.

## Lifecycle and diagnostics

Copyover and shutdown quiesce admission and give commands, then the outbox, a
three-second drain each. The drain covers commands on the writer and retained terminal
notifications. A copyover whose drain fails resumes admission and leaves the live server
running; a shutdown reports the failure and goes on. The game loop drains typed
completions every two pulses. Submission and pulse perform no file or database I/O on
the game thread.

`world persistence` exposes one metadata-only `critical_commands` line: state,
in-flight and publication-pending counts, retained bytes, fences, recent completions,
high-water marks, accepts, attachments, outcomes, retries, ambiguous results, stale
completions, overloads and oldest age. It never prints
command payloads or entity identities.

Terminal command failures also go to `logs/log/file` and `logs/player-log/wizcmds`,
relative to the server's runtime directory, whether or not a staff member is online.
The staff notice names the operation (for example, `artifact/guild reward`), explains
recognized errors, and gives the full 32-digit operation reference and log path.
It is limited to one notice per command type/error every 30 seconds; this limit
does not suppress the detailed log records. Copyover/shutdown drains use the same
reporter. A full log queue or failed file append is tracked by the existing
persistence log health counters; a refused submission is identified in the notice.

To investigate, copy the reference from the notice and search on the server:

```sh
rg -n -F 'operation=PASTE_THE_32_DIGIT_REFERENCE' logs/log/file* logs/player-log/wizcmds*
```

Each record includes the operation ID, named command, numeric error, source category,
and affected entity types/IDs. Large key lists explicitly count omitted keys. For
artifact/guild history failures, it also includes the parent operation ID, source
filename/line, payload version, and a named reason: `malformed_payload`,
`identity_conflict`, `missing_parent`, `legacy_uncommitted`, or `storage_failure`.
Decoded payloads include actor PID, guild ID and artifact count; malformed data
is marked `decoded=0`. Artifact IDs are retained in the bounded command keys.

Payload-v2 history does not compare live timers, souls or guild revisions with SQL.
Current mirror disagreement is a
snapshot/reconciliation problem, not grounds to reject an earned reward.

These values are captured at rejection, before rollback, so a missing
`critical_operation_inbox` row does not remove the evidence. Search the parent
operation ID to connect the reward to its originating operation. No raw SQL,
credentials, character names, or arbitrary command payloads enter this report.

The database inbox stores the canonical command/key hashes and authoritative result.
An identical duplicate returns that result; different bytes under the same operation ID
fail closed. Connection loss after `COMMIT` is reconciled by rereading the inbox before
the original immutable command can retry. Test-state rows are locked in normalized key
order. Deadlocks and lock waits are retryable with the same operation ID.

Each transaction also writes a bounded typed outbox record. The dispatcher reads at
most 64 records/4 MiB at a time, passes the stable outbox ID to a typed consumer, and
records consumer dedupe plus delivered state together. Retryable delivery uses bounded
backoff; the eighth failure or a terminal result retains a dead-letter row. Copyover and
shutdown drain commands first and outbox records second.

`world persistence` adds cached `critical_outbox` counts for pending age, dead letters,
incomplete inbox rows, event-expectation mismatches, unknown historical expectations,
reconciliation candidates, delivery/retry/error totals, and high-water records/bytes.

Operational counts use the existing status indexes on the 250 ms delivery cadence;
the full historical missing-outbox audit runs after delivery, initially and then
60 seconds after each attempt, including failures. Diagnostic errors preserve the
last successful values and do not gate delivery on a usable connection. The
`critical_outbox_health` line labels each sample `unavailable`, `stale`, or `fresh`
and reports its age. A stale or unavailable sample makes the aggregate state
`unknown`, never proof of an empty queue.

An outbox drain requests a new worker observation after any in-flight batch and
checks for all pending rows, including future retries. While waiting within the
existing deadline, the game thread runs the same auction, collector, combat, and
artifact publishers as normal pulses. Auction events remain unacknowledged until
their asynchronous read's
game-thread callback has actually published; drains pump completed SQL callbacks
as well as the publishers. Publication does not bypass durable retry
backoff; a future retry may truthfully make a bounded drain fail. A SQL build
without an initialized worker fails closed; the flat-file backend intentionally
has no SQL outbox and retains its successful absent-worker drain behavior.

An accepted auction read returns `publication_pending`: its row remains due,
without consuming retry attempts or moving `next_attempt_at`. Its completed
game-thread callback wakes the worker for acknowledgement immediately. A failed
read/admission is observed as a real failure by the worker and retains the normal
durable backoff before another read can be submitted.

The additive `immutable/0050_critical_outbox_expectations.sql` migration must precede the new
writer/audit consumer. New committed inbox results record the exact expected
contiguous event indexes `0..expected_outbox_events-1` in their own transaction.
NULL preserves unknown historical intent and replay never rewrites it. The audit
counts all outbox statuses and compares both cardinality and indexes, so a
partially lost multi-event operation remains visible even if one event survives.
An unexpected event for a known zero is also a mismatch.

Historical expectations are classified only with the domain contract and positive
typed evidence. Session audits need a corresponding outcome receipt. Combat epic
children need their canonical empty/hash identity plus the exact parent,
participant index, ledger revision/delta, reason/source, and derived child ID;
the parent owns their publication. Empty epic payloads or command type alone are
insufficient. Typed mutation receipts can prove a single event. Remaining old
ambiguity, including historical item/collector multi-event counts, stays unknown.
All committed history is covered on every audit attempt; no timestamp window or
permanent high-water mark skips old rows.

`outbox_mismatches` is a proven integrity failure. `unknown_expectations` is a
coverage count; `reconciliation_candidates` counts its operations with no outbox
row. These unknowns produce `state=reconciliation`, while dead letters,
incomplete inbox rows, or proven mismatches produce `degraded`. Diagnostic failure
or staleness still produces `unknown`, preserving last-good values. Neither a
candidate count nor an unknown historical set proves loss or permits claiming a
clean audit. The legacy health member `committed_without_outbox` now carries the
reconciliation-candidate count and is no longer an integrity verdict. Never infer
historical intent from the rows still present or fabricate zero expectations.

Treat a growing oldest age as a stop condition for copyover/shutdown and affected
gameplay: restore the underlying database or destination and investigate before
restarting.

## Failure behavior

This is the required result at each boundary;
`python3 tests/async/test_phase02_capacity_and_crash_gate.py` pins the table.

| Boundary | Failure | Required result |
|---|---|---|
| Admission | queue full, coordinator unavailable, key fenced | state-changing commands reject before gameplay success and return what they took from memory; history-only submission failure does not undo a live reward |
| DB acquire/begin | outage, timeout, pool close | the writer retries at the head of its queue; fences stay |
| DB apply | deadlock or lock timeout | rollback and retry with the same operation ID |
| DB commit | connection loss, ambiguous result | reread the inbox by operation ID; never resubmit under a new ID |
| Completion | stale, malformed, offline player, consumer full | exact ID match; the result is retained until it can be published |
| Outbox | destination outage, duplicate delivery, restart | retry the same outbox ID; the consumer dedupes; the eighth failure keeps a dead letter |
| Duplicate | the same operation ID submitted again | attaches to the active operation, or returns the stored result as `already_applied`; no repeated mutation |
| Crash | process dies with commands queued | they are lost like a save that was not written; nothing is replayed |
| Copyover | drain timeout | called off; admission resumes and the game keeps running |
| Shutdown | writer stall or database outage | bounded drain, then the process goes; the log names what was not written |

One operation per client at 25, 50, 100 and 200 clients stays below the 1,024-operation
cap, and all payloads below the 64 MiB cap. An outage must show bounded overload and retry
counters, not unbounded memory, threads, connections or log payloads.

## Reconciliation

On a local, development or test database:

```bash
migrations/reconcile_phase02_domains.sh
```

Any nonzero mismatch blocks a release. Do not repair with direct SQL: keep the inbox,
ledger and current-row evidence, find the owning domain, and issue only a guarded
idempotent command or a reviewed additive repair migration.

`reconcile_artifact_guild_outcomes.sh` requires explicit
`DB_HOST`, `DB_USER`, `DB_PASSWD`, `DB_NAME` and optional `DB_PORT`; it does not load
the checkout's `.env`. Use disposable/local credentials. Its read-only snapshot
checks artifact mirror agreement (including missing rows), item-owner references,
outcome/ledger agreement, committed parent receipts, and parent/actor uniqueness.
It does not equate reward-ledger totals with current timers or guild balances:
transfers, timer adjustments and spending can legitimately change current state.
It cannot observe unsaved memory or prove that the writer drained.

Focused validation is `python3 tests/async/test_critical_command_admission.py`,
`python3 tests/async/test_critical_command_coordinator.py`,
`python3 tests/async/test_critical_completion_capacity.py`,
`python3 tests/async/test_critical_transaction_contract.py`, and, on a disposable
database, `tests/async/run_critical_command_schema_mysql.sh`.

## Epic points and frags live in memory

`epic_transaction_submit()` changes the balance at once and calls its completion before
returning: committed, or refused with `ENOSPC` when a purchase needs more than the
balance (`ERANGE` on overflow). The player's save writes epics, frags and old frags, on
both backends. The command still goes to the one writer as type `epic`, where it only
records history: MariaDB adds an `epic_ledger` row whose balance and revision continue
from the player's last row (or the saved balance when there is none) and advances
`player_data.epic_revision`, which the rows are keyed on; it never writes the balance.
Zone trophies, the epic bonus window and the completed-zone reads at login read that
ledger. Flat-file records the operation only.

A PvP outcome changes the participants' frags, epics and blood money when it is submitted.
Its command records the kill (`pkill_event`, `pkill_info`, `combat_outcome`), continues the
frag and epic ledgers the same way, and updates the frag leaderboard; it is no longer fenced
on the participants' revisions. An epic stone's awards are added in memory when the touch
commits, once per participant (a participant who left gets theirs on return), and the
repository records them in the epic ledger with the stone claim.

`world persistence` reports `epic_transactions` submitted, committed, rejected and ledger
rows the coordinator would not queue. Focused validation is
`python3 tests/async/test_epic_transaction_contract.py`,
`python3 tests/async/test_epic_stone_runtime.py` and, on a guarded development database,
`tests/async/run_epic_transaction_schema_mysql.sh` and
`tests/async/run_combat_outcome_schema_mysql.sh`.

## Artifact and guild rewards live in memory

For a new source award, the game thread captures eligible artifact feeds and guild
prestige/construction from current memory, checks the combined bounds, applies
them immediately, and publishes feedback. It queues artifact rows/souls and guild
snapshots on the existing writer before submitting type-9 reward history. Later
transfers, soul changes, removal, spending and settings capture their current
state independently; history completion never changes that state or repeats feedback.

Capture excludes all contributions from a repeated worn artifact vnum, and
requires each other artifact to have a physical UID, match the live wearer and
match the current memory record's tracked player. Exclusion preserves unrelated
artifact and guild contributions and emits a rate-limited persistence alert with
vnum/reason/source reference. Until canonical admission and reward validation are integrated,
this is conservative conflict isolation: it does not establish the identity of
a single copy whose legacy vnum record already names its wearer.

Artifact and soul snapshots for a known artifact capture its complete current
UID/state, timer and soul in one transaction, including all-souls resets. A failed
UID change cannot be followed by a partial soul write that changes the old UID.
Legacy mirrors preserve identity. Boot stages all artifact, soul and identity reads
before publishing memory; malformed or failed input cannot publish a prefix.
Administrative refresh preserves current identity on conflict and retries current
snapshots. Clear requires a proven-absent identity; retirement evidence and known
absence remain in memory even after legacy tracking is removed. These storage
boundaries do not perform complete population classification or universal
duplicate admission; that work remains in the issue #67 plan.

Flat-file mode hydrates the same artifact/soul maps from the catalog before world
population. Gameplay getters and mutations use those maps; complete immutable
captures reach `artifact_catalog` through the existing persistence writer.
An all-souls reset is one atomic catalog capture. The repository assigns record
revisions, preserves untouched records, rejects conflicting UIDs across the
resulting catalog, and makes exact capture replay a no-op. Storage failure leaves
current gameplay state readable and dirty for retry. Refused admission, including
a full writer, never performs a synchronous fallback. Flat reports still read
persisted catalog state and may lag live state.

Positive feeding feedback is `You feel a sense of satisfaction from above.`
The live artifact/guild award publishes it once even when several artifacts feed;
guild-only, ineligible, rejected and no-effect awards do not publish it. A valid
capped feed retains its positive feedback. The monolith's direct feeding path
uses the same wording per accepted artifact and checks its existing tracked-owner
restriction before publishing feedback; its negative feedback is unchanged.
Direct feeding keeps signed timer arithmetic separate from its diagnostic
magnitude: a negative feed reduces the timer, an above-cap timer clamps to the
current cap, and depletion leaves an expired timer instead of restarting it.

New history uses payload v2 with parent/actor identity and calculated before/after
facts. The repository records outcome/delta ledgers with history revisions, not
gameplay approval revisions. It never compares current SQL timer/soul/guild totals
to authorize a reward and never writes those gameplay fields. Committed v1 commands
still decode for receipt replay; an uncommitted v1 command is refused with the named
`legacy_uncommitted` reason. The existing v1 result/outbox format remains readable,
and delivery invalidates caches without applying a reward.

The pending history bound is 256 entries. Retries retain the original command
identity and bytes and attempt at most eight unqueued entries per second. Admission
or retention failure is reported separately from live success; it never reverses
the reward. Missing history is not regenerated by granting again. Source publication
guards own once-only live application; the coordinator's finite completion cache
is not a permanent deduplication store. The producer fixture crosses the actual
cache capacity and verifies that old completions cannot republish a benefit.

Artifact and guild snapshots retain per-entity dirty metadata and a preallocated
`sql_write_receipt`. Only acknowledgement of the current capture clears its dirty
state. Admission, allocation or terminal write failure leaves it dirty; later
bounded pulses capture the entity's latest state rather than the old reward values.
Artifact removal retains a tombstone through deletion acknowledgement. Cache
generations change on mutation and successful resubmission after failed admission,
so an earlier read cannot become current after those changes.

A guild with a pending kingdom payment captures its current realm in the same
transaction as every guild snapshot, including a member-deletion snapshot.
`payment_pending` lasts until the matching guild receipt confirms commit. Failed
captures or transactions retry current values without another debit; an older
receipt cannot settle a newer capture or a recreated realm. Later realm changes
remain dirty after an earlier pair succeeds, so copyover flushes them after the
payment drain and before the writer drain. Flat-file payments retain their shared
recovery-journal transaction.

Domain drains run before coordinator quiescence and again after final copyover
saves. Failure aborts copyover through the existing resume guard; shutdown reports
unresolved histories and dirty entities.
`world persistence` displays domain live applications, capture failures, dirty
snapshots, history results/loss/pending counts, admission failures and oldest
pending-history age separately. Its age is not wizlog suppression age.

The counts describe observations on the game thread, not fresh SQL queries. In
particular, a history can have committed before its completion reaches that thread.
Diagnostic stage/reason labels use the reporter's category fields and numeric
substitutions retain the full opaque IDs; the string-redaction policy is unchanged.

The staff `artifacts reset syncdb` repair keeps current memory if its asynchronous
result overlaps a later artifact update or an unresolved snapshot failure. Existing
dirty retries then capture fresh state. The result is processed after staff logout;
only notification requires the same live staff character.
Flat-file `syncdb` refuses live reconciliation pending a complete population
audit: a player-only scan cannot select canonical physical identities across all
storage domains. The audited repair workflow remains open in issue #67.

History success and snapshot durability are distinct: either may fail independently.
A crash may lose unsaved state, and restart loads persisted snapshots without
re-awarding committed history. This change adds no schema migration, gameplay
journal or new flat-file reward support; the MySQL capability check remains explicit.

## Money lives in memory

Currency is not a critical command. `currency_transaction_submit()` and its
variants change the character's wallet, and the bank view of every online character
of its account and side, at once, then call their completion before returning:
committed, or refused with `ENOSPC` when a balance would go below zero. The player's
save writes the wallet. A bank change is queued on the one writer as a `bank` job
holding the delta: MariaDB adds it to the `account_banks` row (creating it), flat-file
to the account's bank domain. The bank job is queued after the player's save when the
bank gains and before it when the bank loses, so a crash can lose money but never pay
it twice. A retried bank job never adds its delta twice either: MariaDB writes it in a
transaction and reports a commit whose outcome is unknown instead of retrying it, and
flat-file writes again the bank record it prepared the first time. Shutdown names bank deltas the writer could not write
(`persistence_writer/bank ... deltas=N`).

The economy's commands still run on the writer, but they no longer read or write a
balance. An auction listing fee or bid and a collector purchase price leave the wallet
at submit, with the player's save queued before the command. The completion gives back
what the command did not charge: all of it when refused, and the rest of a bid that was
capped at the buy-now price or only raised the bidder's own bid. A money claim brings
its money at completion. A refund for a collector buyer who has left is given when they
return. A flat-file shop purchase pays its price the same way, and a sale is paid when
it commits.

Items the economy takes leave memory the same way: a listing's items, a flat-file sale's
item and a collected antiquity are taken out at submit, before the owner's save. A
committed command extracts them (a sale hands its item to the shopkeeper); a refused
one puts them back. So a save captured afterwards never holds them, and saves claim
whatever their owner holds, the economy's records included.

Coins are ordinary items. Get, drop, give and put move the pile and the wallet in
memory, the way they always did for NPCs, and `money_to_inventory()` does the same.
When money moves between two saved owners, the owner it leaves is saved first
(`currency_transaction_save_first()`): the giver before the receiver, the container a
put fills after the player it leaves.

`world persistence` reports `currency_transactions` submitted, committed, rejected and
queued bank delta counts. `test_currency_in_memory.py` links the real transaction and
checks the order of what it queues; `test_take_coins.py` the coin pickup;
`test_coin_command_transaction_contract.py` the command sources; and
`test_transaction_input_queue.py` the input that still waits behind a collector
transaction.
