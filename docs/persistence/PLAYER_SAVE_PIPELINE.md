# Player Save Pipeline

Memory is the authority. The database is a copy that catches up through one writer:

1. The game thread marks the affected component bits and seals an immutable snapshot
   only when dirty work exists.
2. The snapshot goes straight to the one persistence writer, and the character is
   clean again: the writer has it.
3. The writer is a single background thread (`src/player/player_save_worker.c`). It
   applies every queued save in capture order: player saves (with their pets),
   corpse saves, locker saves, saved room items, shopkeeper saves, bank deltas,
   critical commands and the game thread's SQL (see below).
   A newer save of the same owner replaces its queued one only when that is the last
   job queued. Otherwise it is queued behind, because a job queued after the owner's
   save may rely on it being written first (the owner money or an item leaves is
   saved before the one it reaches).
4. The game pulse consumes typed completions. A lost connection never reaches it:
   the writer retries that job at the head of the queue, with a backoff capped at
   five seconds. Any other failure is reported once, the job is dropped, and the
   owner is marked dirty so its next save carries the state again.

The game-thread checkpoint and completion paths perform no MySQL, Redis, or filesystem
operation. Nothing is journaled. A crash loses whatever had not reached the database,
at most one 30-second `dirty-player-checkpoint`.

## Game-thread SQL

Code on the game thread that needs the database does not query it. It queues the SQL on the
writer instead (`src/sql/sql_async.h`):

- `sql_queue()` queues a write. `sql_queue_statements()` queues several, and
  `sql_queue_work()` queues work that reads before it writes.
- `sql_read()` and `sql_read_for()` queue a read, which sees every write queued before it.
  The writer copies the rows, and the game thread gets them on a later pulse.

Each `sql` job runs in one transaction. A lost connection is retried, and a commit whose
outcome is unknown is reported instead of retried. Whatever still queries the game thread's
connection while the loop runs is counted (`game_loop_queries` in `world persistence`) and
logged once per site (`game loop query site ...` in `logs/log/status`).

## What a save writes

A player save writes the wallet, epic points, frags and old frags with the rest of the
character; a bank change is its own `bank` job (see
[Money lives in memory](CRITICAL_COMMAND_PIPELINE.md#money-lives-in-memory) and
[Epic points and frags live in memory](CRITICAL_COMMAND_PIPELINE.md#epic-points-and-frags-live-in-memory)).
A save never refuses. In one transaction it writes what its owner holds in memory and
makes `item_current_owner` agree (`claim_items()` in `src/item/item_claim_repository.c`;
the flat-file backend does the same in `flatfile_item_repository_prepare_claim()` and
commits it with the player file):

- an item with no ownership row gets one;
- a row naming this owner is corrected if the item moved;
- a row naming anyone else (a player, corpse, locker, room, pet, auction, shopkeeper
  or the collector) is taken, and an `item_owner_audit` row records the item, its
  vnum, the old owner, the new owner and the time (flat-file: a line in
  `logs/log/item_claims`). An auction listing, a sale and a collection take their
  items out of memory before their command, so a save captured afterwards never
  holds what the economy took;
- a row that says the item was destroyed is left alone: the item and its contents are
  left out of the save and logged to `logs/log/dupes`. Only a save captured before
  the destruction can still hold it;
- a coin pile is claimed like any item. A pile an older server's coin transaction
  spent stays spent, like any destroyed item.

The owner's revision, and the revision of each owner that lost an item, advances once
per save that changes them. There is no revision fence: with one writer, every save is
newer than the last one for that owner. A character with no `player_data` row yet gets
one.

`logs/log/dupes` has one line per item a save left out or a load skipped, naming the
item, its vnum, the owner that lost it and the owner that has it.

## What a load reads

A load takes an item row only if `item_current_owner` has no row for that uid or names
the loading owner, whatever the row's state. A row naming anyone else makes the item a
stale or duplicate copy: it is skipped, logged to `logs/log/dupes` as `load_skipped`,
and the owner's next save no longer writes it. What a skipped container holds moves up
a level (to the top of the inventory, the corpse, the locker chest or the room item), so
one stale row never takes the rest of the graph with it. A root that disagrees with the
graph is corrected, not refused. The same rule applies to player and pet items
(`player_load_repository.c`; flat-file: `flatfile_player_repository.c`), and to corpses,
lockers and saved room items through `sql_persistence_item_owner_matches_identity()`.
The flat-file corpse and room loaders still use their own reconciliation until those
owners are saved through the writer.

A load always succeeds with the rows that pass the filter; there is no degraded
admission, no stale-row refusal threshold and no read-only quarantine. Logins never
block the game loop: the account menu submits the load and the descriptor waits in
`CON_PLAYER_LOAD` until the load worker answers. If the worker refuses the request, the
player is asked to try again. Copyover restore, which runs before the game loop starts,
is the only caller that still waits for a load.

A character is not loaded while it still has a save queued on the writer, or while a
staff target fence holds it (`player_save_pipeline_load_held()`): the load worker moves
it to the back of its queue and loads the others meanwhile, so a quick relog always reads
the latest state. A held load that reaches its deadline is answered `timed_out`. A locker
cannot be reopened while its save slot is dirty or in flight.

## Configuration And Health

The writer needs no configuration. `world persistence` reports the pipeline (marks,
captures, replacements, unchanged checkpoints, write failures, terminal waits, drain
failures) and the writer (queued and in-flight jobs, bytes,
oldest age, high-water marks, connection retries, failures, capture-to-apply and apply
latency). Output contains no player identity or snapshot value.

## Persistence reporting severity

`persistence_report(severity, level, domain, owner, item_uid, event_id, action, format, ...)`
separates event severity from the immortal audience selected by `level`:

| Severity | Structured outcome | Routing |
| --- | --- | --- |
| `persistence_severity::ok` | `outcome=ok` | `LOG_FILE` and `LOG_WIZ` file records |
| `persistence_severity::info` | `outcome=info` | `LOG_FILE` and `LOG_WIZ` file records |
| `persistence_severity::alert` | `outcome=alert` | Both file records and the existing red immortal broadcast |

`persistence_alert(...)` remains an alert-only compatibility entry point. Unknown
severity values also alert. Both entry points use the same category sanitization
and numeric-only detail filtering; owner, item UID and event ID arguments are
omitted from the output at every severity.

Use `ok` after a successful durable operation and `info` for expected progress.
A death is quiet unless its terminal save fails (`terminal_save_failed` alerts); the
character leaves at once either way.

Successful deferred-save flushes, flat fallback writes and complete legacy replays
also use `ok`; failed flushes and partial replays retain alerts. Retired raw-worker
and raw-replay status reports use `info`. Failed I/O, rejected mutations, dropped
or undrained work, unavailable workers and automatic restarts after worker failure
continue to alert even when a recovery path is available.

File delivery runs on a dedicated worker started during boot. Admission uses a fixed
128-record queue and a try-lock: the game loop never opens, writes, closes, or waits
for a reporting file. Each record is bounded to 4095 bytes; the reporter bounds
numeric details to 1023 bytes and the formatted event to 2047 bytes. Formatting may
truncate long numeric details. The worker receives only copied text and enqueue
time; it never accesses characters, descriptors, or the legacy `logit` formatter.

A full or contended queue rejects the new file record and increments `rejected`;
there is no synchronous fallback. Alert broadcasts still run immediately even if
file admission fails. `world persistence` exposes cumulative accepted/completed,
rejected, and independent file/wiz failure counters. The game pulse broadcasts a
reporting-delivery alert when failures increase or pending delivery makes no progress
for 30 seconds, at most once per 30 seconds. These notices do not re-enter the queue.
Counters remain inspectable when no immortal was online for the notice.

The worker creates missing parent directories, opens each sink with append and
close-on-exec, and accepts only regular files. Open, short-write, write, and close
failures are counted per sink; the other sink is still attempted. No ambiguous write
is replayed, so a partial write may leave a truncated record. Rename/create rotation
is supported: a record goes to the file opened for that append and subsequent opens
follow the new path. Use rename/create rotation; concurrent copytruncate cannot
promise lossless records. The two sinks are independent, not an atomic transaction.

Shutdown and copyover wait up to three seconds for queued and in-flight attempts.
A timeout reports possible diagnostic loss to stderr and does not veto authoritative
save/recovery gates. A failed exec leaves the worker available. Worker storage lives
until process exit, avoiding an unbounded destructor join if filesystem I/O hangs.
These diagnostic records are not a durable gameplay journal: no fsync or crash replay
is promised. Failure counts are also printed on ordinary shutdown.

Validate bounded admission, blocked I/O, independent sink failures, rotation, and
drain behavior with `python3 tests/async/test_persistence_log.py`.

Validate routing and privacy with `python3 tests/async/test_persistence_severity.py`.

## Terminal Saves And Process Drain

Destructive player transitions mark and capture a fresh full revision with the
current terminal intent and room behind a fixed-capacity terminal fence. An ACKed
nonterminal retry or an older pending full snapshot cannot authorize a new camp.
A caller may extract the character only after the exact
revision receives a database acknowledgement or, where explicitly allowed, after its
journal record has been synced. Older completions cannot release a newer fence. A
deadline failure keeps the fence and dirty revision retryable; later mutations advance
that same fence instead of becoming untracked.

Copyover and ordinary shutdown quiesce new checkpoint admission and wait to a bounded
deadline until every accepted snapshot is journal-durable. The drain includes a record
currently owned by the journal dispatcher, not only records still visible in its queue.
If the deadline expires, the transition is cancelled and the live server resumes
checkpoint admission.

`world persistence` reports admission, append-in-flight, terminal outcome, timeout,
and drain-failure counters without player identity. New legacy player flat-fallback
writes are retired; existing files remain untouched for compatibility and operator
recovery. Locker fallback behavior remains a separate compatibility boundary.

## Compatibility Boundary

New characters without a durable PID, locker characters, and Phase 02 critical
transactions retain their explicit legacy compatibility route for now. Synchronous
transactional compatibility saves advance `save_revision` in the same transaction,
fencing every older immutable snapshot. They are not treated as an exactly-once
gameplay command; Phase 02 replaces them with operation-keyed domains.

## Deferred and manual saves

`src/cmd/actoth.c::persistence_pulse_character_saves()` services deferred capture
and manual acknowledgement checks from the game-loop persistence path, independent
of world-event debt. It attempts at most 32 due deferred saves per call with a
round-robin cursor and checks the bounded 512-slot manual-status table. Deferred
slots use monotonic due times and character runtime identities so storage reuse
cannot apply work to a different character. Manual completion still requires
acknowledgement within the existing 30-second deadline.

A failed camp retains the live character and permits automatic nonterminal retry;
a later camp must capture its own intent again. Flat-file terminal saves require
authority acknowledgement; SQL-backed callers may explicitly permit a synced
journal handoff. These guarantees do not prevent legitimate storage timeouts or
operating-system starvation. The controlled retry/crash modes are documented in
[Testing](../guides/TESTING.md#full-world-save-diagnostics).

## Player deaths

A death happens at once (persistence reset step 5): `make_corpse()` moves the
player's items into the corpse in memory, the corpse save claims them, the
player's save follows, and the character is extracted. There is no recovery
hold, corpse handoff batch or disputed-death disposition any more. The wallet
becomes a coin pile in the corpse (Phase 2 step 4); the player's save, with the
wallet empty, is queued before the corpse's, so a crash between them can lose
the coins but never leave them in both places. See
[the persistence reset plan](../ongoing-projects/2026-09-28-persistence-memory-authority-plan.md)
and `tests/async/test_deaths_happen_at_once.py`. Death evidence already stored by
older servers (`player_death_disposition`, `player_death_custody`, flat-file
`player-deaths/`) remains protected recovery data in the
[lifecycle manifest](../../migrations/data_lifecycle_manifest.json).
