# Persistence reset: memory is the authority again

**Date:** 2026-09-28

This file is the plan: the rules, the design, the three phases of the reset, Phases 4 to 8 for
the open work items, what was cut and [What is left](#what-is-left). Finished work is recorded in
[persistence-done.md](persistence-done.md): when an item of What is left is finished, its record
(what landed, decisions, tests, verification, commits, bugs found) goes there and the item leaves
the list. A decision that changes the framework is written here.

**Status (2026-10-02):** Phases 1, 2 and 3 are done and on master. Phase 3 landed as
[!5](https://gitlab.com/max757/duris/-/merge_requests/5) in `21f65de2c` after one review
round ([record](persistence-done.md#phase-3-landed-done)). The reset is finished: #7 is closed,
and #3, #5 and #6 record what it resolved
([record](persistence-done.md#the-work-items-closed-out-done)). Phases 4 to 8 take the open work
items, one phase each; none is started.

**Work items:** the reset took #7 (player saves and deaths, closed) and the persistence causes
behind #5 (game freezes), #3 (the player-save journal breaking backups) and #6 (persistence alert
storms). Phases 4 to 8 take what is still open in #6, #4, #3, #5 and #2.

## What was wrong

The database was in charge. An item could not move, a character could not die or log out, a
corpse could not be raised and coins could not change hands until a database transaction had
committed, so the game waited or refused. Every player save was checked against the ownership
table `item_current_owner` and thrown away whole on any disagreement, and nothing ever settled
one. Saves failed forever, extracts were refused, dead characters were held in memory, deaths
froze the whole game for 2 seconds, corpse raises failed and shutdowns were cancelled.

## The rules

1. **Simple.** Each rule below fits in a sentence. No new frameworks.
2. **No over-engineering.** Anything no requirement needs was cut; see
   [What was cut, and why](#what-was-cut-and-why).
3. **Memory is the authority.** Items move, characters die and corpses are raised in memory, at once.
   The database is a copy that catches up.
4. **Saves never refuse.** A save writes what its owner holds in memory, in one transaction. Where the
   ownership table disagrees, the save corrects it and writes an audit row. There is no rejection, no
   retry loop, no stuck character, no blocked shutdown and no death hold.
5. **One item, one owner.** `item_current_owner` already has `PRIMARY KEY (item_uid)`, so the database
   cannot record two owners for one item. Loads hand each owner only what that table gives it. A save
   or load that loses an item to another owner writes one line to `logs/log/dupes` and carries on.
6. **The game loop never waits for the database.**
7. **Corpses just work.** Raising, resurrecting, decaying and looting a corpse happen in memory and
   cannot fail on the database.
8. **It ends.** Phase 1 removes every cause of the problems above. Phases 2 and 3 only simplify.

## How it works

### One writer

One background thread, the player save worker cut to one thread, writes everything to the
database in capture order: player saves with their pets, corpse, locker and saved-room-item saves,
`sql_log()` rows, critical commands, bank deltas, shopkeeper saves and the game thread's own SQL
(`sql` jobs).

- **Order:** a newer save of an owner replaces its queued one only when that is the last job
  queued; otherwise it queues behind, so it never overtakes a job that relies on the earlier save.
- **Failures:** a lost connection is retried at the head of the queue. Any other failure is
  logged, the job is dropped and the owner is marked dirty, so its next save carries the state
  again. The game never waits or refuses.
- **No journal:** a queued job lives only in memory; see [What a crash costs](#what-a-crash-costs).

### What a save does

In one transaction:

1. **Claim what it holds.** For each item: no `item_current_owner` row, insert one; a row naming
   this owner, nothing to do; a row naming any other owner, set it to this owner and write an
   `item_owner_audit` row. The economy takes its items out of memory before its command, so a
   later save never holds what it took.
2. **Leave out what was destroyed.** A row that says the item was destroyed is final: the item and
   its contents are left out and logged to `logs/log/dupes`.
3. **Write the owner's rows** (`player_items`, `corpse_items`, `locker_items` and the others) from
   memory.

Nothing else is checked: with one writer every save is newer than the last, so there is no
revision fence, and a character with no `player_data` row gets one.

### What a load does

A load takes an item row only if `item_current_owner` has no row for it or names this owner. Any
other row is a stale or duplicate copy: it is skipped, logged to `logs/log/dupes` and removed by
the owner's next save. With the key allowing one owner per item and the last claim winning, that
is the whole dupe protection. A character or locker is not loaded while it has a save queued, so
a quick relog reads the latest state; the login waits while the game loop carries on.

### Money and the economy

Balances (the wallet, the bank, epic points and frags) change in memory at once, and the save
writes them; a bank change, shared by the account's characters, is also queued as a delta. What
must still commit in the database (auctions, the collector, item grants, repairs and destruction,
boons, artifacts, combat outcomes, zone touches) is a critical command on the one writer, queued
at submit so it lands in capture order with the saves. Auctions, shops and the collector take what
they trade out of memory at submit and give it back if the command is refused. When money moves
between two saved owners, the one it leaves is queued first.

### The game thread and the database

The game loop issues no query after boot, and a journey pins it. Writes are `sql` jobs on the
writer (`src/sql/sql_async.h`), built on the game thread. Reads that feed a command's output run on
the writer and hand copies of their rows to a game-thread callback on a later pulse. Reads the game
logic depends on come from memory: loaded at boot, or when a character enters the game, and kept
current by the writes (`mud_info`, which the website edits, is read again every minute). Account
logins read on the writer while the connection waits, offline characters load through the player
load pipeline, and pid lookups use the in-memory name index. Boot and shutdown may still query.

### What a crash costs

A clean shutdown or copyover writes everything first. A crash loses what had not reached the
database, at most one 30-second checkpoint (`dirty-player-checkpoint`), the classic MUD model.
Nothing is duplicated: an item handed over during a crash stays with whichever owner was written
last, and money is lost rather than paid twice, because the owner it leaves is saved first. On
MariaDB a bank delta or `sql` job whose commit outcome is unknown is reported, not retried.

## Phase 1: end the problems

Done ([record](persistence-done.md#phase-1-progress)): one writer; saves never
refuse; loads filter on the ownership table; items move in memory; deaths happen at once; corpses
in memory; logging out never waits; shutdown and copyover always go; the dupe log.

## Phase 2: money, points and the rest of the loop

Done ([record](persistence-done.md#phase-2-progress)): critical commands on the
one writer; money, epic points and frags in memory; the economy stops writing balances; coins drop
into corpses; shops in memory; no economy exception in the claim; the game thread's SQL off the
loop.

## Phase 3: delete what is left over

Remove the persistence code nothing reaches any more
([record](persistence-done.md#phase-3-progress)). Decisions:

- **Every server is treated as new:** no journal is replayed and no death record kept, so both
  one-time replays and the death custody and restitution feature go, and migration 0034 drops
  their tables. `CRITICAL_COMMAND_JOURNAL_DIR` stays for the locker identification receipts.
- **The economy accounting foundation goes;** migration 0034 drops its tables too.
- **The collector's death intake is restored in memory.**
- **The linker decides what is dead:** a function is dead when both server builds drop it (see
  [Finding dead code](#finding-dead-code)), and code behind an always-false switch goes with the
  switch. Test API and dead code outside the reset stay.
- **Kept:** `currency_transaction.c` (the in-memory wallet and bank API), the creation grants with
  what they need of the item transfer command and repositories, and `item_ownership_runtime.c`
  (the economy's fence for the items it holds).

Done, each with its tests in its own commits, through the gate:

1. [The journals](persistence-done.md#step-1-the-journals-done).
2. [What only the critical-command replay reached](persistence-done.md#step-2-what-only-the-replay-reached-done),
   with the economy accounting foundation.
3. [The death custody and restitution feature](persistence-done.md#step-3-death-custody-and-restitution-done)
   and migration 0034.
4. [The durable item movement](persistence-done.md#step-4-the-durable-item-movement-done).
5. [The durable corpse lifecycle](persistence-done.md#step-5-the-durable-corpse-lifecycle-done).
6. [The collector's death intake](persistence-done.md#step-6-the-collectors-death-intake-done).
7. [The game thread's dead SQL](persistence-done.md#step-7-the-game-threads-dead-sql-done), and
   whatever else the linker dropped.
8. [Flat-file lockers load their items](persistence-done.md#step-8-flat-file-lockers-keep-their-items-done).
9. [The die, restart and loot journey](persistence-done.md#step-9-the-die-restart-and-loot-journey-done).
10. [The movement transactions and the transfer branches only they used](persistence-done.md#after-step-9-the-dead-transfer-branches-not-asked-for)
    (`4621a6c8a`, `01a345b84`).
11. [The ledger reconcilers](persistence-done.md#the-ledger-reconcilers-done) and
    [DATABASE.md](persistence-done.md#databasemd-done), with two defects found on the way, and
    [the rest of the docs and a dead branch](persistence-done.md#the-rest-of-the-docs-and-a-dead-branch-done).

### Finding dead code

Build both servers with one section per function, in their own object directories:

```sh
make -C src -j16 OBJDIR=$PWD/bin/analysis/objects SERVER_BIN_DIR=$PWD/bin/analysis \
    DMS_BINARY=$PWD/bin/analysis/dms_new EXTRA_CFLAGS="-ffunction-sections -fdata-sections"
make -C src -j16 PERSISTENCE_BACKEND=flatfile OBJDIR=$PWD/bin/analysis/flat-objects \
    SERVER_BIN_DIR=$PWD/bin/analysis/flat DMS_BINARY=$PWD/bin/analysis/flat/dms_new \
    EXTRA_CFLAGS="-ffunction-sections -fdata-sections"
```

Rerun each build's final link line from `src/` without `-rdynamic` and with
`-Wl,--gc-sections -Wl,--print-gc-sections`. Each `removing unused section '.text.<symbol>'` line
names a function that build never reaches; demangle with `c++filt` and read `st_mysql` as `MYSQL`
(the flat-file build stubs it). A function is dead when every build that compiles it drops it. The
list is a lead, not proof: read the source first (a function reached only through a dead branch
shows as live, an inlined one as dead).

On 2026-10-02 the pass on `93d315d07` found nothing newly unreachable since the step 7 head
(`c551f5d05`). Run it again only if a later change removes a caller.

The linker cannot see a dead branch inside a live function. Completions are an example: the
writer retries a retryable or ambiguous result itself, so a game-side branch for one is dead
(the zone touch had the last, removed in `7a1613c21`).

## Phase 4: alerts and logs (#6)

1. **Critical-command failures name nothing.** The `integrity_failure` alert in
   `run_recurring_persistence_phase()` (`comm.c`) passes `none` and redacts its detail. Log the
   command type and the refusal reason, without player data.
2. **Repeated alerts are not grouped.** The wizlog limiter (`persistence_alert_wizlog_decision()`,
   `utility.c`) keys on the full alert text, so alerts whose detail varies never group. Count
   repeats per domain and action per interval.
3. **`checked_snprintf()` names no caller** and reports both sizes one short (`safe_format.c`).
   Take a call-site argument, and report bytes including the NUL.
4. **Logs that never rotate.** `cycle_mud.sh` rotates only `logs/log/*` at boot. Rotate
   `logs/player-log/*` and `logs/latency_trace.log` too, with a size cap, and send the latency
   trace to one destination instead of the file and stdout.
5. **Debug noise.** The `PFileToLocker`, `LockerToPFile` and `Locker save start` trace lines
   (`storage_lockers.c`) and `sql_restore_shopkeepers: shop N` on every boot (`sql_player.c`) go
   behind a debug flag.
6. **`cycle_mud.sh` stop reports.** Decode a signal exit (128+N) into a reason instead of
   `unknown [137]`. The boot email tests `/logs/old-logs/...`, with a leading slash, so it never
   attaches the previous exit log.
7. **Idle connections.** The logs show 57 connections MariaDB closed for `wait_timeout`. Prove
   with a test that the SQL pool reconnects after one.

Left on #6, as server configuration rather than code: the `mysql` client's charset warnings, the
WebSocket warning on a MUD-only server, the stale `proxies_priv` grant, the game's database user
name and the logins without a password.

Done when: logs rotate with size caps and the latency trace has one destination; a
critical-command failure names its command type and reason, and repeats are counted, not
repeated; `checked_snprintf()` names its call site and reports bytes; the pool test survives an
idle timeout.

## Phase 5: bugs from the logs (#4)

1. **IPv6 in `log_entries`.** `ip_address` is `varchar(15)`, and `sql_log()` cuts the address to
   fit (`sql.c`). Add a guarded, re-runnable migration to `VARCHAR(45)`, as `account_ips` has,
   raise the field limit with it, update what pins the schema head, and test an IPv6 address.
2. **A zone-story state above 64 KiB.** The save was fixed in `9fafc10dd`; add the regression test
   that stores one.
3. **Characters missing from their room's people list.** `char_from_room()` (`handler.c`) logs and
   returns when `in_room` and `world[].people` disagree: 19 times in the logs, 11 in inn rooms.
   Reproduce it, find the path that sets `in_room` without `char_to_room()` (rent, camp and
   reconnect restores are the leads), and fix it with a test.
4. **Owner decision: restored corpse decay.** `persistence_refresh_restored_corpse()` (`files.c`)
   gives a restored player corpse a fresh decay timer on every boot, so a server restarted more
   often than that never lets one decay. Keep refreshing, or keep the remaining time with a
   minimum?

Done when: each bug has a fix and a focused test, the schema change is an additive migration,
and item 4's decision is recorded here.

## Phase 6: backups (#3)

1. **Every run re-verifies every generation.** `generations()` in
   `scripts/persistence_backup.py` calls `verify()` on each stored generation, which hashes every
   file and decompresses and scans each dump; at 40 generations a run takes 3 to 4 CPU-minutes.
   Verify a generation fully once, when it is published; `status` reads the manifests and the
   receipt; full re-verification moves to the drill's slow cadence.
2. **Failing backups raise no RPO alarm.** While `backup()` keeps failing, `schedule` never
   reaches `status()`. Report the RPO age from the schedule path too.
3. **A receipt that changes during the dump fails the run.** The capture compares the critical
   directory after the dump. Copy the locker identification receipts at the dump's snapshot point,
   or retry the receipt step without redoing the dump.
4. **Failures lose their cause.** `operation_failed` is a catch-all. Log the exception class and
   message, without secrets.

Left on #3, as server configuration: whether a server runs restore drills, keeps an off-host
replica and skips the pre-boot backup.

Done when: a status run costs about the same with 1 generation or 40, and a test pins it; a backup
completes while a receipt changes, with a test; failure records name the exception, and an RPO
breach alerts even when every backup fails.

## Phase 7: game-loop performance (#5)

1. **Measure again.** The tick stalls, the event debt and the `rent`, `quit` and hourly timings in
   #5 predate the reset, which took their database waits away. Measure them on a local full-world
   boot under scripted load, find what is left in `ne_events`, and add an in-process test that
   fails if `rent` blocks the loop past a budget.
2. **Unnamed callbacks.** `cycle_mud.sh` builds `lib/misc/event_names` from global `T` symbols
   only, so static functions and lambdas show as `unknown function`. Register names at
   `add_event` time, or include local symbols.
3. **Production builds at `-Og`.** `HARDENING_FLAGS` in `src/Makefile` puts `-Og` in every profile.
   Build `BUILD_PROFILE=production` at `-O2`, and record the tick latency before and after on the
   same load.
4. **The backup job's CPU** competes with the loop; Phase 6 item 1 fixes it.

Left on #5, as server configuration: the MariaDB buffer pool, left at its 128 MB default.

Done when: `rent`, `quit` and the hourly event stay under a set budget under load, and a test pins
it; every slow event names its callback; the production profile builds optimised, with the tick
latency before and after recorded.

## Phase 8: world recovery (#2)

1. **Captures above 64 MiB fail.** `append_record()` (`world_recovery_pipeline.c`) refuses any
   record past `WORLD_RECOVERY_MAX_BYTES`, and a world of about 55,000 mobs and 11,000 objects
   passes it, so no generation publishes and a crash falls back to a full zone boot. Size the cap
   from the world, or chunk and stream the generation.
2. **Captures expire under load.** A capture takes 285 to 295 s of its 300 s budget. Measure it on
   the Phase 7 build before changing the budget.
3. **Nothing escalates.** Each failure is one `LOG_SYS` line. After a run of failed or expired
   captures, raise one persistence alert with the reason and the last acknowledged sequence and
   age, and report that age in runtime health.

Done when: a capture of that size publishes, with a test above the old 64 MiB limit; it finishes
within its budget under load; consecutive failures raise an alert with the age of the last good
generation.

## What was cut, and why

Each part was removed in turn ([ablation](../../.agents/skills/ablation/SKILL.md)) and stayed only
if a requirement or a concrete risk failed without it. Cut:

- **A per-item revision to order saves across threads:** one writer applies them in capture order.
- **A live uid-to-object index to catch dupes:** the key and the load filter already stop a second
  copy.
- **Deleting the old owner's row when a save claims an item:** loads ignore stale rows, and the old
  owner's next save removes them.
- **Releasing items an owner no longer holds:** the next holder claims them; a release would also
  trip foreign keys and need a "nobody" owner.
- **Saving the receiver the moment an item changes hands:** the 30-second checkpoint writes both
  sides together.
- **Keeping the player-save journal:** a replay would skip the corpse and locker saves between
  player saves and could apply half a hand-over.
- **Moving money in Phase 1:** coins stayed in a dead character's wallet until Phase 2.
- **Rewriting the legacy `qry()` calls in Phase 1:** the freezes came from the persistence waits.
- **One job for both saves when money moves:** queuing the owner it leaves first is enough.
- **Holding a command while an earlier one on its key awaits publication:** the writer already
  runs them one at a time.
- **The coordinator's retry cap:** it would only drop a command whose outcome is unknown.
- **A barrier job:** replacing only the last queued save keeps capture order.
- **A receipt table for bank deltas:** neither backend can add a delta twice without one.
- **A second job kind for reads:** one `sql` job kind carries both.
- **Converting what never runs after boot:** it cannot make the loop wait.
- **Converting `restoreCharOnly()`'s SQL:** offline loads reuse the player load pipeline.
- **Reading an account back after saving it:** its other sessions get the saved copy from memory.
- **Flat-file and pfile builds as separate gates:** `make test-all` builds both, and the restore
  qualifier.
- **A second backup-recovery container run:** it passed at `c6e0219da`, and nothing since touches
  what the restore qualifier runs.
- **Waiting on the owner for item 10 of Phase 3:** it deletes what Phase 3 said goes, and the gate
  covers it.
- **Dropping the opening baselines and the event log tables:** nothing in
  [Done when](#done-when) needs it, and it is a schema change across a migration, the bootstrap,
  the boot probes, the lifecycle manifest and the legacy dump import.
- **Watching `test_flatfile_full_world_boot.py`:** one abort in nine runs during Phase 1, none
  since.

## Done when

The reset (Phases 1 to 3) is done when:

- A save cannot be rejected; its only failure is a lost connection, which the writer retries
  without the game noticing.
- No character is ever held after death, logout or idle rent.
- No corpse raise, resurrection or decay can fail on the database.
- Shutdown and copyover never wait indefinitely on a failing save: after 30 seconds shutdown
  goes and copyover is called off.
- The game loop issues no query after boot.
- The database cannot hold one item under two owners, and `logs/log/dupes` accounts for every
  item a save or load gave up.
- No persistence code is left that nothing reaches, and the branch passes the gate.

All hold: the gate passed on `0b90e5fc1`
([record](persistence-done.md#the-gate-on-the-branch-head-done)) and again on review round
1's head ([record](persistence-done.md#review-round-1-mr-5)).

## What is left

In this order: alerts that name their cause first, so the later phases can be diagnosed; the
backup job's cost before Phase 7 measures the loop; the world capture last, on the optimised
build.

1. [Phase 4: alerts and logs (#6)](#phase-4-alerts-and-logs-6).
2. [Phase 5: bugs from the logs (#4)](#phase-5-bugs-from-the-logs-4).
3. [Phase 6: backups (#3)](#phase-6-backups-3).
4. [Phase 7: game-loop performance (#5)](#phase-7-game-loop-performance-5).
5. [Phase 8: world recovery (#2)](#phase-8-world-recovery-2).
