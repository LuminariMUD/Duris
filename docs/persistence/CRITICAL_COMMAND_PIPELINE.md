# Critical Command Pipeline

Phase 02 non-idempotent gameplay work uses one bounded command contract. Each command
has a cryptographically random 128-bit operation ID, a schema and payload version, a
categorical source site and deadline, sorted affected entity keys, optional expected
revisions, and owned payload bytes. It contains no live game pointers, SQL, Redis keys,
paths, account names, or character names.

The generic destination stores command identity and result in an InnoDB inbox, applies
a typed test-domain mutation, and creates its notification in the same transaction.
Production gameplay producers remain disabled until their individual Phase 02 domain
sessions. Outside mini mode, startup requires the verified critical-command schema;
failure leaves critical gameplay stopped.

## Acceptance and execution

The coordinator validates and normalizes an envelope before admission. Entity keys
are sorted and duplicates are rejected. It reserves bounded memory, fences the
command's keys, and queues it on the one persistence writer
(`persistence_job_kind::critical`), the same thread that applies every save. A command
therefore lands in capture order with the saves around it: a save captured before the
command is applied before it, one captured after, after it. `submit()` returns
`accepted`; the command is durable once the writer has applied it. New commands are not
journaled: like a save, a command that had not reached the database is lost in a crash
(see the persistence reset plan, "What a crash costs"). Records are never coalesced or
replaced by a newer command.

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

## Journal of an older server

Only a journal an older server left is read, once, at boot, from
`CRITICAL_COMMAND_JOURNAL_DIR`. Every record is validated first: a record this server
cannot execute stops the boot with nothing applied and the journal untouched. The
commands are then queued on the writer in journal order, and each is checkpointed once it
lands (a command held for publication, once its publication is acknowledged). Replay
retains the original operation ID; a command replayed again after a crash finds its
inbox row and returns `already_applied`.

The journal directory must be owned by the server user and mode `0700`; its regular
file is mode `0600` and opened without following symlinks. Records have magic, version,
length, operation ID, canonical command bytes, and CRC32. Exact checkpoint rewrites a
temporary file, syncs it, renames it, and syncs the directory. Truncation, bad framing,
unsupported versions, checksum mismatch, unsafe ownership or permissions, I/O failure,
or quota exhaustion fails closed. Identical repeated frames replay once; conflicting
bytes for one operation ID are corruption.

Default bounds are 1,024 active operations, 64 MiB of command memory, 2,048 pending
completion records, and a 256-operation/8 MiB recent-completion cache. Accepted work is
never dropped because the writer is behind.

## Lifecycle and diagnostics

Copyover and ordinary shutdown quiesce admission and require a three-second drain
before later persistence gates. The drain covers commands on the writer and retained
terminal notifications. Any failed transition resumes admission and leaves the live
server running. The game loop drains typed completions every two pulses. Submission
and pulse perform no file or database I/O on the game thread.

`world persistence` exposes one metadata-only `critical_commands` line: state,
in-flight and publication-pending counts, retained bytes, fences, recent completions,
high-water marks, accepts, attachments, outcomes, retries, ambiguous results, stale
completions, overloads, oldest age, and journal counts/bytes/status. It never prints
command payloads or entity identities.

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
incomplete inbox rows, committed operations missing outbox rows, delivery/retry/error
totals, and high-water records/bytes. `critical_outbox_reconcile()` is the typed
read-only discrepancy interface. `critical_outbox_retry_dead_letter(id)` is the sole
repair action: it can only reset one numeric dead-letter ID and never accepts SQL.

Treat a growing oldest age, `journal=corrupt`, `journal=io_failure`, or
`journal_quota=1` as a stop condition for copyover/shutdown and affected gameplay.
Restore the underlying storage or destination, preserve the journal, and investigate
before restarting. Never delete or edit the journal to clear a fence.

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

## Money lives in memory

Currency is no longer a critical command. `currency_transaction_submit()` and its
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
