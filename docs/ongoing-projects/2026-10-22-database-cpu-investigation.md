# Database CPU investigation and remediation plan

Date: 2026-10-22. Status: investigation complete; implementation and deployment have
not started. This document is the deliverable for the database CPU investigation.

## Recommended change

Replace the outbox health query's historical aggregates with indexed queries over
pending, dead-letter, and incomplete rows. Keep delivery polling at 250 ms and run
the historical missing-outbox audit on a separate 60-second schedule. Make drain
completion depend on a fresh worker observation, rather than cached health counts.
These changes belong in the first implementation, with no schema migration.

The initial findings identified the dominant workload correctly. The live query
took about 182–199 ms and runs about 2.2 times per second, accounting plausibly for
the observed 44% of one CPU core. The proposed four-counter query took about
0.3–0.5 ms using existing indexes. Its row reads stayed constant when an isolated
fixture gained 100,000 delivered rows.

Two additional findings change the proposed fixes:

- The current missing-outbox counter reports 1,008 legitimate operations as
  integrity failures. All were classified from live receipts and source code.
- Retention is part of replay and reconciliation correctness. Deleting completed
  records after an arbitrary number of days is unsuitable as the first CPU fix.
  Boon checks also generate most of the retained rows, so future growth deserves
  a separate change at the producer.

## Evidence and limits

Production observations were taken on October 22 at approximately 21:13–21:22 UTC.
The checkout's `.env` identifies production, `127.0.0.1:3307`, database
`duris_prod`. Socket inspection mapped that endpoint to MariaDB PID 1630, separate
from the MariaDB instance on port 3306. The server reports MariaDB 11.8.6 and a
1 GiB InnoDB buffer pool. The game process was PID 313739.

Production work consisted of bounded read-only SQL, session-local read-only and
three-second statement-timeout settings, and process observations. No production
data, global settings, indexes, service state, or deployment was changed. The
synthetic tests used disposable MariaDB containers with a separate random port,
a 512 MiB memory limit, and a one-CPU limit; the containers were removed afterward.

The checkout advanced during the investigation through other work. The reviewed
head at the later source check was `565ca0db8d8ffec728439b6949cc88f5bbbfced5`.
The relevant worker SQL matched the SQL observed executing in the live game.
This verifies the relevant runtime behavior without assuming that the running
binary corresponds to every source file at that head.

### Runtime measurements

| Measurement | Observation | Interpretation |
| --- | --- | --- |
| MariaDB process CPU over 30 seconds, starting 21:13:50 UTC | 13.27 CPU seconds; 44.23% of one core | Measured interval usage, rather than `ps`'s lifetime average |
| Physical InnoDB reads / data reads / data writes during that interval | 0 / 0 / 0 | This interval's dominant workload was memory-resident |
| Row-lock waits / row-lock time / log waits | All zero deltas | No evidence that these waits explain the CPU sample |
| SELECT statements | 13.83/s | Includes active gameplay and background work |
| `Select_scan` | 8.9/s | Includes full index scans; does not mean 8.9 distinct slow queries |
| `Handler_read_next` / `Handler_read_rnd_next` / `Handler_read_key` | 570,554 / 287,267 / 287,429 per second | Logical row/index operations, not physical disk reads or distinct rows |
| Processlist sampling, 300 samples over 30.33 seconds | Health query active in 133 samples; another statement in two; no visible active statement in 165 | The health query dominated observed active statements for the application user |
| Health query executions detected in that sampling window | 68; roughly 0.45 seconds between starts | The loop waits 250 ms **in addition to** query and delivery time |

At the later health inspection there were 12 connections, one running thread,
zero InnoDB history-list length, zero buffer-pool waits, and zero recorded
deadlocks. The SQL pool also performs an exclusion-lock ownership probe when
borrowing a connection; this helps explain query counts beyond one health query
and one fetch per cycle. That probe is a correctness guard and should stay.

Performance Schema and the slow-query log are disabled. The application's account
cannot read statement digests or `INNODB_TRX`, and processlist visibility is limited
to that account. Consequently this is not a complete per-statement CPU profile
across every database user. The independent process CPU measurement, live query
observations, query execution plans, and row-read signatures nevertheless strongly
identify this worker as the dominant continuous load.

### Query measurements

The original SQL was extracted directly from `refresh_counts()` and `fetch_batch()`
in [critical_outbox.c](../../src/persistence/critical_outbox.c). Each query was run
once for session handler counters, once with `ANALYZE FORMAT=JSON`, and three more
times for client elapsed time. These diagnostic executions were outside the
30-second CPU baseline and processlist sampling windows.

| Query | Three repeated client times, ms | Execution evidence |
| --- | --- | --- |
| Original combined health query | 181.90, 182.84, 185.76 | Instrumented server execution: 199.05 ms; three full scans |
| Original outbox `SUM` / conditional `MIN` alone | 28.58, 28.55, 32.71 | Reads all 126,836 outbox entries through the age index |
| Incomplete inbox count, `status<>1` | 0.36, 0.32, 0.31 | Existing status index; zero matching rows |
| Historical missing-outbox audit alone | 164.39, 145.73, 154.76 | Scans 127,845 inbox rows and materializes 126,836 outbox keys |
| Delivery fetch | 0.40, 0.30, 0.32 | Existing claim index; no full scan; no due rows at that instant |
| Proposed four active counters | 0.33, 0.38, 0.35 | Four key reads, zero sequential reads, zero full scans in the empty-queue sample |
| Proposed pending-existence check | 0.21, 0.22, 0.20 | One key read, zero full scans |

The combined query performed 253,672 `Handler_read_next` operations, 127,846
`Handler_read_rnd_next` operations, and 128,045 key reads in one execution.
Its outbox aggregate uses a **full covering index scan**, whereas the audit scans
the inbox's clustered rows. MariaDB materializes outbox operation IDs once and
checks membership for successful inbox operations; this plan is more specific
than the initial description of repeated lookups directly into the outbox.
The `status<>1` inbox subquery already uses an efficient range scan.

The expensive audit occupied about 171 ms of the instrumented combined query's
199 ms. Optimizing only `SUM(status=0)` leaves most of the cost in place.
The approximate duty-cycle calculation `190 / (250 + 190) = 43%` closely matches
the independent CPU sample; it is an explanation of the measurements, not a
post-change CPU guarantee.

### Retained data and its producer

A later aggregate sample contained 127,916 inbox rows and 126,907 outbox rows.
All inbox rows were committed; one represented a rejected auction operation.
The outbox had 126,906 delivered rows and one pending row, with no dead letters.
An earlier sample had no pending rows, illustrating why queue state must be
treated as changing rather than assumed permanently empty. The oldest records
date to October 4.

Table allocation estimates were approximately 354 MiB of inbox data and 245 MiB
of outbox data, excluding indexes. These are engine allocation figures, not a
measurement of reclaimable space or a claim that the tables are fragmented.

| Source | Count / observation |
| --- | --- |
| Boon operations, command type 11 | 114,710; 89.68% of inbox rows |
| Boon outcomes with zero matching entries | 108,453; 94.55% of boon outcomes |
| `BOPT_NONE` checks, option 0 | 101,310; every recorded result had zero entries |
| Boon result size | Exactly 2,080 bytes per inbox result and corresponding outbox payload |
| Combined boon result payload in both tables | About 455 MiB, before row/index overhead |
| Boon operations on October 19 / 20 / 21 | 14,542 / 9,740 / 8,408 |
| October 22 operations by the sample time | 6,307 across all command types; 6,012 boon operations |

[gain_exp()](../../src/world/limits.c) calls `check_boon_completion(..., BOPT_NONE)`
for many experience changes. The
[submission path](../../src/economy/boon_reward_transaction.c) creates a fresh
operation ID; the [repository](../../src/economy/boon_reward_repository.c) writes
an outcome and sets `mutation_applied=true` even when no boon matches. The generic
repository then records both the result and an outbox event. The
[codec](../../src/economy/boon_reward_command.c) zero-fills a fixed 2,080-byte result
even for zero entries. At inspection, the three active boons were all option 3
(`BOPT_MOB`), consistent with the empty option-0 results.

`BOPT_NONE` is an actual zone experience-bonus option, despite its name. Globally
disabling it would break future matching boons. The empty outcomes prove write
and storage amplification; they do not prove that removing replay receipts is safe.

The day's roughly 5% row growth alone does not establish why the original report
observed CPU doubling from 21% to 44%. There is no comparable morning interval
sample or query plan here. Historical scanning explains continuing growth in
cost; the specific earlier increase remains unverified.

## Correctness findings that constrain the change

### Cached health is also used as a drain barrier

`critical_outbox_drain()` returns success whenever `health.pending` is zero.
Initialization zeroes health before the first worker poll. Counts are refreshed
before fetching a batch, and neither a new inbox/outbox commit nor delivery
immediately updates that cached pending count.

This allows a drain to return success with a committed pending row, or to wait on
an already-delivered row until another refresh. Moving all counts to a 30–60 second
timer would enlarge both errors and conflict with the callers' three-second
budgets. Callers include [copyover](../../src/persistence/copyover.c),
[account deletion](../../src/account/account.c), and
[shutdown](../../src/net/comm.c).

An isolated executable probe reproduced the first case using the actual worker:
insert one pending record, initialize the worker, call `critical_outbox_drain(50)`
before its first poll, and stop the worker. Drain returned true; querying afterward
confirmed that the record was still pending. The existing delivery, retry/restart,
and terminal-failure harness checks then also passed.

`critical_outbox_quiesce()` only changes `health.accepting`; the worker continues
delivering. `critical_outbox_resume()` notifies the condition variable, but its
current wait predicate only accepts `stop_requested`, so notification alone does
not implement an immediate work request. A drain wakeup needs a real predicate.

There is an additional lifecycle interaction to test: auction, collector, combat,
and artifact callbacks can queue publication onto the game thread and return a
retry. Normal pulses publish these events; the coordinator's drain observer handles
command completions but does not run all those outbox publishers. A truthful drain
can therefore expose an existing publication/backoff timeout. Never solve that by
reporting an empty queue. Preserve the caller's bounded failure behavior and test
publication progress explicitly when implementing the drain change.

### Missing an outbox row is not always an integrity failure

The current audit assumes every `status=1 AND result_code=0` inbox operation needs
an outbox. Live classification of its 1,008 results found:

- **1,003 session-audit operations:** every row has a corresponding
  `session_audit_outcome`. The session-audit branch of
  [critical_command_repository.c](../../src/persistence/critical_command_repository.c)
  deliberately commits its inbox result without inserting an outbox.
- **Five combat child epic operations:** all have epic ledger entries with PvP
  reason and combat source. Recomputing the child ID from the parent combat
  operation and participant index matched every row. All also have the empty
  result and identity hashes written by `insert_child_inbox()` in
  [combat_outcome_repository.c](../../src/combat/combat_outcome_repository.c).
  Their parent combat event owns publication.

The rejected auction row has a nonzero result code and is correctly excluded from
the current audit. Other command branches condition outbox creation on
`mutation_applied`, so a general replacement must also account for successful
no-op/recovered operations and operations that legitimately create multiple events.
In particular, a recovered stone claim with `stone_uid` still sets
`mutation_applied=true` and requires its own receipt outbox; recovery alone is not
an exemption.

The [staff health display](../../src/cmd/actinf.c) marks any positive raw count as
degraded, and the [runbook](../operations/RUNBOOK.md) describes it as an integrity
incident. These semantics need correction together. Do not delete rows or create
dummy events to make this diagnostic green, subtract a fixed 1,008, or exempt all
epic operations merely because these five are legitimate children.

### Retention preserves operational guarantees

The [lifecycle manifest](../../migrations/data_lifecycle_manifest.json) marks the
inbox, outbox, and delivery dedupe as protected reconciliation/replay records,
with retain actions and an unresolved retention horizon. There is no ordinary
age-based purge for these tables in the inspected runtime.

The live schema has inbox references from `epic_stone_claim`, `zone_touch_outcome`,
`currency_ledger`, `artifact_guild_outcome` (operation and parent), `auction_ledger`,
`epic_ledger`, `item_ownership_ledger`, `session_audit_outcome`, `boon_reward_outcome`,
`combat_outcome`, and the outbox. These match the migration relationships relevant
to this investigation. The
[outbox schema](../../migrations/critical_command_inbox_outbox.sql) restricts inbox
deletion and cascades outbox deletion into delivery dedupe.

The inbox prevents duplicate application and resolves ambiguous commits. A stone
claim also joins it to recover a canonical prior result. Deleting delivered outbox
rows while retaining successful inbox rows makes the current historical audit
report them all as missing. Removing dedupe or inbox evidence requires a designed
replay horizon and archive lookup policy, not merely a foreign-key-compatible
delete order. Never disable foreign keys to perform this cleanup.

## Assessment of the initial suggestions

| Suggestion | Decision |
| --- | --- |
| Refresh health every 30–60 seconds | Apply to the historical audit. Preserve fast delivery and separate drain correctness from telemetry freshness. |
| Delete completed rows after a few days | Defer. Protection, replay horizons, dependencies, dedupe, and audit semantics must be resolved first. |
| Count only unfinished rows using indexes | Apply. Live and isolated tests demonstrate the existing indexes are sufficient. |
| Check missing outbox rows only in a recent window | Do not silently replace whole-history coverage. It can miss old corruption and late commits; `created_at` is not commit order. |
| Keep counters only in memory | Defer. Startup, reconnects, ambiguous commits, and external repairs require reconciliation; cheap indexed reads avoid that extra state. |
| Add indexes / enlarge the buffer pool / change durability settings | Not supported as the first fix. The relevant indexes exist, reads were cached, and lock/log waits did not explain the sample. |

## Implementation sequence

### 1. Remove historical work from the delivery cadence

Touch the existing worker, health structure, staff health display, and focused
tests. Keep the change within these components; no new service or general scheduler
is needed.

1. Replace the four operational counters with the SQL below. Retain the current
   250 ms delivery interval, batch limit, ordering, backoff, and delivery transaction.
   Count **all** `status=0` rows, including future retries. The due batch alone
   cannot establish an empty queue.
2. Schedule the historical audit once initially and then every 60 seconds using
   `steady_clock`, after delivery work. Set the next deadline after an attempt,
   including failure, so an audit failure does not reintroduce a 250 ms retry loop.
   Avoid catch-up bursts after a stall. Initially preserve its historical coverage
   and raw result while the separate semantic correction is prepared.
3. Remove the `refresh_counts(...) && fetch_batch(...)` dependency. A diagnostic
   SQL failure must not suppress delivery when the connection remains usable.
   A lost connection still follows the pool's replace/reacquire path; do not use
   a known-broken handle. Retain the ownership-lock guard.
4. Track whether operational metrics and the audit have ever succeeded, their
   last successful refresh times, and failure/staleness. Keep the last good values
   on failure, and distinguish stale or unavailable health from a fresh empty
   queue in staff output. Keep this bookkeeping bounded and under the existing mutex.
5. Replace cached-zero drain success with a worker request/acknowledgement
   generation. After upstream admission is quiesced and commands drained, request
   an observation made after that request and after any in-flight batch. A
   successful indexed `EXISTS(status=0)` check with no in-flight delivery establishes
   completion. An uninitialized worker, database error, old observation, or future
   retry must not be interpreted as successful emptiness. Preserve the existing
   backend-specific behavior for builds where this worker is intentionally absent.
6. Add the request to the condition-variable predicate. Keep SQL on the worker;
   the game thread waits only within its existing deadline. Ensure publication
   callbacks that need the game thread can progress during lifecycle drains, or
   return the existing bounded failure if they cannot. Verify the caller's timeout
   and shutdown semantics rather than silently extending them.

Proposed operational query, measured using the live indexes:

```sql
SELECT
  (SELECT COUNT(*) FROM critical_outbox WHERE status=0) AS pending,
  (SELECT COUNT(*) FROM critical_outbox WHERE status=2) AS dead_letter,
  (SELECT COALESCE(
     TIMESTAMPDIFF(MICROSECOND, MIN(created_at), CURRENT_TIMESTAMP(6)) DIV 1000,
     0)
   FROM critical_outbox WHERE status=0) AS oldest_age_msec,
  (SELECT COUNT(*) FROM critical_operation_inbox WHERE status<>1)
    AS incomplete_inbox;
```

The outbox indexes are `(status,next_attempt_at,outbox_id)` and
`(status,created_at)`; the inbox has `(status,created_at)`. The minimum timestamp
can use the age index directly. These counters scale with active/problem rows,
not retained delivered history. A very large pending or dead-letter backlog can
still make exact counts expensive; include that case in verification.

For the fresh drain observation:

```sql
SELECT EXISTS(SELECT 1 FROM critical_outbox WHERE status=0) AS has_pending;
```

At the observed 2.2 audit executions per second, one audit per minute reduces
historical audit executions by roughly 99.3%. That estimate excludes ordinary
gameplay writes and the inexpensive delivery/health polling. Measure the resulting
CPU rather than promising a particular idle percentage.

### 2. Correct the integrity audit and its operator meaning

Treat the current value as a raw reconciliation candidate count until it is
classified; expose its refresh age. Update the staff display, runbook, and relevant
pipeline documentation together when changing what triggers an integrity alert.

Build fixtures for session audits, proven combat children, successful no-ops,
recovered stone claims, rejected commands, and multi-event item operations. A real
missing expected event must remain visible, including an event missing from an
operation that still has another event. The current `NOT EXISTS` audit cannot
detect that partial loss.

Prefer a domain-aware audit using the existing typed receipts and command/result
contracts. The five live combat exceptions were proven by parent/child identity;
an empty payload or command type alone is not sufficient proof. If existing
receipts cannot unambiguously express an operation's expected event set, introduce
explicit expectation metadata in a separate additive migration. Historical
expectations must remain unknown until classified, not default to zero. Record
expectations atomically with the operation and validate replay compatibility.

Keep full historical coverage at the reduced cadence initially. If it later
exceeds the agreed query-time budget, split the audit into bounded keyset batches
with repeated complete sweeps and report coverage/age. A recent-only time window
or a permanent high-water mark over random operation IDs is insufficient.

### 3. Reduce future boon write and payload amplification

Implement separately after the worker improvement is measured, so its impact is
attributable and gameplay behavior gets its own review.

- Start with the zero-match path identified above. Evaluate filtering impossible
  matches using an authoritative, freshness-aware boon definition view before
  admission. Reuse an existing suitable view if one exists. A cache miss or stale
  snapshot must fall back to authoritative evaluation, and activation, edits,
  expiry, targeting, and racewar changes must invalidate negative decisions.
- Preserve a durable canonical answer for accepted operation IDs. Dropping a
  receipt can make an ambiguous retry re-evaluate against a later boon definition
  and award something the original attempt did not.
- Evaluate a compact versioned result and omission of delivery work for proven
  zero-effect outcomes, with explicit audit expectations. Current decoders require
  exactly 2,080 bytes; trimming stored payloads without versioned reader support
  breaks replay. Test old inbox/outbox records and flat-file readers too.
- Compare submissions, matched outcomes, result bytes, outbox inserts, transaction
  latency, and reward behavior before and after. Gate this work on unchanged reward
  eligibility, progress, completion, and replay behavior.

### 4. Design retention only if it remains necessary

After query and producer changes, measure remaining table growth and backup/restore
cost. If a retention change is justified, first define the replay, delayed
publication, investigation, and restore horizons for each domain and obtain the
corresponding lifecycle decision.

Then design archive or compact-receipt lookups, dependency handling, and audit
coverage. Retain pending, dead-letter, incomplete, referenced, and unresolved
operations. Any eventual deletion must use small indexed batches with resumable
progress and load limits, preserve required dedupe, and have recovery from a tested
backup/archive. A few days of age is not sufficient eligibility by itself.

Production migrations or cleanup require the owner's explicit permission under
[AGENTS.md](../../AGENTS.md). This investigation requests no such action.

## Verification and rollout gates

### Completed during this investigation

- Read the supplied initial findings and traced worker scheduling, SQL plans,
  pool ownership probes, transaction writers, result readers, callers of drain,
  publication callbacks, lifecycle protection, schema relationships, and tests.
- Collected the production measurements and classifications above without
  changing production data or service configuration.
- Compared original and proposed operational counts on disposable MariaDB 11.8.9
  using the repository's outbox schema. Five cases passed: empty tables;
  delivered-only history; mixed due/future pending, dead-letter, incomplete and
  rejected operations; that same mixture plus 100,000 delivered rows; and pending
  rows transitioned to delivered while a dead letter remained.
- With two pending rows, one dead letter, and one incomplete inbox row, both queries
  returned `(2,1,120000,1)` at a fixed session timestamp. The replacement performed
  four sequential index reads both before and after adding 100,000 historical
  deliveries, with zero full scans. The pending-existence check included the future
  retry even though it was ineligible for the delivery batch.
- Reproduced the stale-zero drain bug in a disposable database with the actual
  worker and confirmed the existing delivery, retry/restart, and terminal-failure
  behavior. The investigation probe and result are in the local evidence directory.
- Passed all 14 documentation contract checks and whitespace validation for this
  document.

The disposable engine's patch release (11.8.9) differs from production (11.8.6).
Live query plans validate the production optimizer; fixture results validate mixed
state semantics. The executable probe validates the existing drain defect; none of
these tests validate the proposed scheduling or drain implementation before it is
written.

Local, ignored evidence is under `bin/analysis/db-cpu-investigation/`: CPU baseline,
query plans and timings, processlist summaries, aggregate table summaries, audit
classification, and synthetic SQL fixture results. This document preserves the
decision-relevant results without player identifiers, credentials, or payloads.

### Required for the implementation

Extend [critical_outbox_mysql_harness.cpp](../../tests/async/critical_outbox_mysql_harness.cpp)
with executable checks rather than relying on source-string assertions. The
existing harness covers delivery, retry/restart, and terminal failure; it does not
cover cadence, health freshness, or drain races.

| Area | Acceptance evidence |
| --- | --- |
| Query semantics and scaling | Empty, mixed, future retry, large active backlog, 100k+ delivered history; exact counts; indexed plans; retained history does not drive operational row reads |
| Scheduling | Delivery continues at its short cadence; audit attempts obey their independent deadline, including failure and resume; no catch-up burst |
| Diagnostic failures | Counter/audit failure does not stop usable-connection delivery; connection loss recovers correctly; stale values are labelled; failures cannot masquerade as zero |
| Drain | Startup-before-first-poll; commit-after-last-zero; delivery in flight; stale positive after delivery; future retry; DB failure; timeout; stop/resume; intentionally absent backend |
| Publication and lifecycle | Auction/collector/combat/artifact publication progresses on the game thread; copyover and account deletion never pass with unresolved pending work; shutdown preserves its bounded reporting policy |
| Existing delivery contract | At-least-once behavior, recorded delivery, duplicate callback, ambiguous commit, backoff and dead letters remain correct across restart |
| Integrity audit | Legitimate omissions classified; a truly missing or partially missing expected event detected; old mismatches remain discoverable |

For the first C/C++ implementation, run the focused harness, the applicable
copyover/publication journeys, formatting, and the build. Relevant existing entry
points include:

```sh
./scripts/format.sh --check
make -C src
CRITICAL_DB_IMAGE=mariadb:11.8 tests/async/run_critical_command_schema_mysql.sh
python3 tests/async/test_critical_transaction_contract.py
python3 tests/async/test_copyover_failure_runtime.py
python3 tests/async/test_txn_publication_copyover_drain.py
```

The last source-contract test supplements runtime evidence; it cannot prove the
new concurrency behavior. Add the missing executable drain/publication coverage
and verify the flat-file/no-MySQL path before shipping. No C/C++ source was changed
in this planning task, so a full server build is not a claim of this investigation.

Stage and then deploy the first worker change alone through the normal authorized
deployment process. At comparable traffic, collect 30–60 second intervals of
process CPU, handler deltas, statement mix, delivery latency, pending age, database
failures, and audit freshness; also watch a longer gameplay period.

Acceptance requires that delivered history disappear from frequent operational
scans, historical audit frequency fall to approximately once per minute, idle
health-related row work fall by at least 95%, and pending delivery/recovery remain
correct. A comparable quiet overall CPU sample should fall substantially from
44%; any residual load must be attributed before claiming the incident resolved.
Compare activity levels, not CPU alone. Audit false-positive correction and boon
optimizations have their own acceptance gates above.

If delivery, lifecycle drains, or recovery regress, stop the rollout and restore
the prior binary through the normal deployment process. The first change needs no
schema or data rollback. Expected consequences of reverting are restoration of
the original CPU load and diagnostic behavior; never purge rows as a rollback.

## Measurement references

MariaDB's [ANALYZE FORMAT=JSON documentation](https://mariadb.com/docs/server/reference/sql-statements/administrative-sql-statements/analyze-and-explain-statements/analyze-format-json)
describes execution-time, loop, row, and engine statistics. This investigation used
`ANALYZE FORMAT=JSON SELECT ...`, which executes the SELECT, rather than
`ANALYZE TABLE`, which changes optimizer statistics. See also MariaDB's
[row-counter interpretation](https://mariadb.com/docs/server/reference/sql-statements/administrative-sql-statements/analyze-and-explain-statements/analyze-interpreting-rows-and-filtered-members).
Client elapsed times include round-trip and result handling; server execution
times and process CPU are reported separately above.
