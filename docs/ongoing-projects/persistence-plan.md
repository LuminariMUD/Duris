# Persistence reset: memory is the authority again

**Date:** 2026-09-28

This file is the plan: the rules, the design, the three phases of the reset, Phases 4 to 8 for
the open work items, what was cut and [What is left](#what-is-left). Finished work is recorded in
[persistence-done.md](persistence-done.md): when an item of What is left is finished, its record
(what landed, decisions, tests, verification, commits, bugs found) goes there and the item leaves
the list. A decision that changes the framework is written here.

**Status (2026-10-05):** Phases 1 to 8 are done and on master, and
[nothing is left](#what-is-left). Phase 3 landed as
[!5](https://gitlab.com/max757/duris/-/merge_requests/5) in `21f65de2c` after one review
round ([record](persistence-done.md#phase-3-landed-done)). The reset is finished: #7 is closed,
and #3, #5 and #6 record what it resolved
([record](persistence-done.md#the-work-items-closed-out-done)). Phases 4 to 8 took the open work
items, one phase each. Phase 4 landed as
[!6](https://gitlab.com/max757/duris/-/merge_requests/6) in `d6952d701`, its review clean
([record](persistence-done.md#phase-4-landed-done)). Phase 5 landed as
[!7](https://gitlab.com/max757/duris/-/merge_requests/7) in `218d0640b` after one review
round, and #4 is closed ([record](persistence-done.md#phase-5-landed-done)). Phase 6 landed as
[!8](https://gitlab.com/max757/duris/-/merge_requests/8) in `1a4b15f9d` after one review
round ([record](persistence-done.md#phase-6-landed-done)). Phase 7 landed as
[!9](https://gitlab.com/max757/duris/-/merge_requests/9) in `77734a404` after one review
round ([record](persistence-done.md#phase-7-landed-done)). Phase 8 landed as
[!10](https://gitlab.com/max757/duris/-/merge_requests/10) in `791b1b132` after one review
round, and with it the settings that Phases 4, 6 and 7 had left on #6, #3 and #5
([record](persistence-done.md#phase-8-landed-done)); #2, #3, #5 and #6 are closed.

**Work items:** the reset took #7 (player saves and deaths, closed) and the persistence causes
behind #5 (game freezes), #3 (the player-save journal breaking backups) and #6 (persistence alert
storms). Phases 4 to 8 took what was still open in #6, #4, #3, #5 and #2.

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
name and the logins without a password. Decided on 2026-10-04:
[the settings that were left](#the-settings-that-were-left-3-5-6).

Done when: logs rotate with size caps and the latency trace has one destination; a
critical-command failure names its command type and reason, and repeats are counted, not
repeated; `checked_snprintf()` names its call site and reports bytes; the pool test survives an
idle timeout.

How each item is done (decided 2026-10-02):

1. The completion carries its command's type. The alert's detail is `type=N error=N`: the
   detail allows numbers only, which keeps player data out, and both numbers are stable (the
   type is stored with every command, `critical_command.h`).
2. The wizlog limiter keys on domain and action alone. The persistence log still gets every
   alert.
3. `checked_snprintf()` becomes a macro passing `__FILE__` and `__LINE__`, so its call sites
   do not change and the format is still checked; `checked_snprintf_runtime()` the same.
4. At boot `cycle_mud.sh` moves `logs/player-log/*` and `logs/latency_trace.log` into
   `logs/old-logs/<date>/` with `logs/log/*`, then deletes the oldest generations until the
   archive fits its cap. The pwipe's own player-log move goes, since every boot now does it. The
   latency trace goes to its file only, not to stderr as well.
5. One diagnostic switch in the environment, documented with the others in
   `CONFIGURATION.md`, gates the routine locker and shopkeeper-restore trace lines; their
   failure lines stay.
6. A signal exit reads `killed by SIG<NAME>`; 139 stays `crash`.
7. Item 7 found that an idle timeout stopped every write, and was fixed with its tests first.

Done: each item has its record under
[Phase 4 progress](persistence-done.md#phase-4-progress).

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

Done when: each bug has a fix and a focused test, and the schema change is an additive
migration.

How each item is done (decided 2026-10-02):

1. Migration `0036_log_entries_ipv6` widens the column with a guard that issues no `ALTER`
   once it holds 45; its verifier checks the shape. The bootstrap, the runtime head and both
   engines' fingerprints (measured with `run_runtime_compatibility_mysql.sh` on `mysql:8.0`
   and `mariadb:10.11`) move with it, and `sql_log()` keeps 45 bytes. The MariaDB save-claim
   harness writes a 45-character IPv6 address.
2. A harness on the save-claim leg's MariaDB stores a state above 64 KiB through
   `sql_zone_story_quest_state_save()`, `sql_queue()` and `sql_execute()`, and reads it back
   with the boot load.
3. The cause: both loads (`player_load_materialize()`, `restoreCharOnly()`) set `in_room` to
   the saved room without `char_to_room()`. A character freed without entering the game
   (finger, the artifact owner checks, disguise, illusion, the website's character
   deletions, an account-menu back-out, the staff pfile scans) then ran `char_from_room()`
   on a room it was never in, which logged the line and took a mortal off its zone's PvP
   misfire count, which it had never been added to; and `load char` stayed in the game
   listed in its saved room but missing from its people list, because `char_to_room()`
   refuses a character that already has a room. Offline characters rent at inns, hence the
   inn rooms. A loaded character is now in no room: the saved room stays in `was_in_room`,
   where `enter_game()` already looks first. The MariaDB game-loop journey fingers and
   loads an offline character saved in the god's room.

Done: each item has its record under
[Phase 5 progress](persistence-done.md#phase-5-progress).

Not an item: a restored player corpse gets a fresh decay timer on every boot
(`persistence_refresh_restored_corpse()`, `files.c`). That is game behaviour, and it stays
(owner, 2026-10-02).

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
replica and skips the pre-boot backup. Decided on 2026-10-04:
[the settings that were left](#the-settings-that-were-left-3-5-6).

Done when: a status run costs about the same with 1 generation or 40, and a test pins it; a backup
completes while a receipt changes, with a test; failure records name the exception, and an RPO
breach alerts even when every backup fails.

How each item is done (decided 2026-10-03):

1. `generations()` reads each generation's manifest and checks its fields, without hashing a
   file or opening a dump; `verify()` keeps the full check. A generation is verified in full
   when it is published, by `finalize` (which can follow a publish that stopped before its
   check), when it is restored and before it is pruned. The drill verifies every stored
   generation before it restores the newest, so a corrupted older one fails the drill and
   `status --require-drill` alarms. `total_size()` takes sizes from the file system instead of
   hashing every file. Measured locally on the old code with copies of a real 31 MB
   generation, `status` took 1.2 s of CPU with 1 generation and 43 s with 40.
2. When a scheduled backup fails, the schedule still reads the newest generation's age. Past
   the RPO the failure record's code is `rpo_exceeded`, with the backup's own failure under
   `backup`; otherwise the record is the backup's failure with the age added.
3. The receipts are copied after the authority capture instead of before it, and the
   comparison after the dump goes. A receipt is written at once and the wallet reaches the
   database with a later save, so the two never matched at one instant; copied last, a paid,
   failed or delivered receipt is at least as new as the database it is restored with, so a
   restore can lose that identification's charge but not repeat it (as a crash does: money is
   lost rather than paid twice). A prepared receipt is still waiting on its payment, whose
   charge can reach the database first (a bank debit and its save are queued at once), so the
   capture lists the waiting receipts before the authority capture and fails with
   `receipt_payment_in_flight` when the copy holds one that was not waiting, unchanged, then
   (review round 1 of !8). A rename replaces a receipt whole, so the copy is checked on its own
   instead of against the directory, each file held to the budget and the reserve before it is
   copied. The writer's temporary files (`.<pid>.receipt.tmp.<pid>.<n>`), there while a write
   is under way and left behind by a crash, are not copied: one failed the run with
   `journal_filename`, and a crash's leftover failed every run. The check that
   `CRITICAL_COMMAND_JOURNAL_DIR` agrees with the policy moves before the capture, so a
   mismatch still costs no dump.
4. A failure record names the exception's class (`error`) and message (`detail`), except what
   can be private: an OS error keeps its `strerror` without the file names (a flat-file path
   can name an account), and a subprocess error keeps no message (its command line names the
   database user and host). The replica's failure is recorded the same way in `status.json`
   and the run's output, instead of a bare `replication_failed`.

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
4. **The backup job's CPU** competes with the loop; Phase 6 item 1 fixed it: locally a backup
   into a root of 40 generations went from 97.9 s of CPU to 13.7 s, and `status` from 43 s to
   0.04 s ([record](persistence-done.md#each-generation-verified-once-done)).

Left on #5, as server configuration: the MariaDB buffer pool, left at its 128 MB default.
Decided on 2026-10-04: [the settings that were left](#the-settings-that-were-left-3-5-6).

Done when: `rent`, `quit` and the hourly event stay under a set budget under load, and a test pins
it; every slow event names its callback; the production profile builds optimised, with the tick
latency before and after recorded.

How each item is done (decided 2026-10-03):

1. One journey is the measurement and the pin: `test_mysql_game_loop_budget_journey.py`, in
   `make test-db`. It boots the full world on a disposable MariaDB; scripted mortals on their
   own accounts play, camp out with `quit` and rent at an inn while the first hourly event
   runs, and a god rents with 88 items. The budget is one pulse, 250 ms, for the rents, the
   camps and the hourly event alike, and it is read from the loop's own records
   (`COMMAND OP SLOW`, `MUD TICK TOOK TOO LONG`, the event analytics), not timed from
   outside. Every command and every pulse is held to it. `--players` and
   `--hours` scale it into the load a build is measured with; it prints the trace's tick,
   event and command times, the deferred events and the costliest callbacks. What the
   measurement found is fixed in this phase, each with its test:
   - The hourly event still held the loop for 1.4 to 1.6 s, once after every boot. A boot
     leaves every shop dirty, and the hourly save walked the whole character list for each
     shop. It now finds every keeper in one walk.
   - The event debt came from the default limit of 4000 callbacks a pulse, which ended
     pulses at a tenth of the 25 ms time budget. The default is now no count limit: time is
     the limit, as [ARCHITECTURE.md](../reference/ARCHITECTURE.md#event-wheel) already said
     it should be. `DURIS_NEVENT_MAX_CALLBACKS` still sets one.
   - The maintenance scheduler's worker retried a failed write of its state file without a
     pause, and held a core for as long as it failed (every full-world test fixture, or a
     full disk). It waits a second.
   - Found by the review: with the keepers found in one walk, the hourly save queued all
     544 shop saves on the one writer at once, ahead of every player save and relog. It
     fills the writer's queue to 16 jobs and takes the remaining shops on the following
     pulses.
   - Found by the review: the slow commands the journey had put down to the machine were
     log writes on the game thread, the command log before every command and `logit()` for
     every line. The command log is kept in memory and a log thread writes the lines; an
     exit or a crash writes what is held.
   `rent`, `quit` and the camp's save were already inside the budget: the persistence reset
   took their database waits away.
2. The names file lists local and weak functions with the global ones, and keeps a name in
   an anonymous namespace. Both launchers write it with `scripts/event_names.sh`. Registering
   names at `add_event` time was not needed: it would touch every call site and misname a
   callback passed through a wrapper.
3. `-Og` stays the development level and production builds at `-O2`. The warning profile
   holds at both levels: the 84 diagnostics `-O2` newly reported are fixed, not excepted.
   Among them were real defects: a staff command writing ten bytes over five, an event
   whose inverted check used a missing affect, and six more uses of a pointer or value that
   was not there. `make test-all` builds the production profile too
   (`make build-production`), so a later `-O2` report fails the gate. On the same load the
   mean pulse is 6.6 ms at `-Og` and 6.4 ms at `-O2`: the loop follows pointers through
   the world, which the optimiser does not shorten.

Done: each item has its record under
[Phase 7 progress](persistence-done.md#phase-7-progress). The budget holds (no rent, camp or
hourly event past 35 ms under 30 players, against a 250 ms budget); every callback in a
full-world run is named; the production profile builds at `-O2`, with the tick latency
before and after in [the measurement](persistence-done.md#the-measurement-done).

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
4. **A raised corpse's items go to the caster.** Not world recovery: a leftover of the reset,
   found on 2026-10-04. `place_raised_item()` (`necromancy.c`) gives a player caster every item
   in the corpse except the coins, in all six raises (the undead, the golem, the titan, the
   avatar and both dracoliches); `raise_undead()` takes a player's corpse too. `389016091`
   (2026-09-15) made it so because a pet's inventory had no place in the ownership ledger, and
   step 5 of Phase 3 removed the deferred raise (`4401cc6ef`), which left this rule to every
   raise. On the local server, `animate dead` on a guard's corpse put its dagger in the
   caster's inventory. Put the items on the raised creature, as before `389016091`. A pet can
   then carry a hidden (`!show`) item from an NPC's corpse: `wear all` already skips those for
   a player's pet, and `wear` and `wield` by keyword must skip them too.
5. **World recovery is a switch, and it is off unless a server turns it on** (owner,
   2026-10-04). It is a convenience, not a safety net: characters, pets, corpses, lockers,
   banks and shops are saved without it. It only brings the mobs, the loose objects, the
   doors and the zone ages back as they were after a crash or a cold restart, where the boot
   would otherwise reset every zone; a copyover keeps the world by itself. The code already
   leaves it off when `REDIS_WORLD_STATE` is not `TRUE`, but `.env.example` ships `TRUE`, so
   every server set up from the template captures the world. Ship `REDIS_WORLD_STATE=FALSE`
   in `.env.example` and set it in the local `.env`; say beside it, and in
   `CONFIGURATION.md`, what it buys and what it costs; and make sure a server with it off
   does none of the capture's work and raises none of item 3's alerts. Items 1 to 3 are
   still fixed, for the servers that turn it on.
6. **The capture interval is a setting, ten minutes by default** (owner, 2026-10-04).
   `REDIS_WORLD_STATE_INTERVAL` is 10 seconds by default and accepts 5 to 300, and a capture
   of the full world takes close to five minutes, so a server with recovery on captures
   without a pause. Make the default 600 seconds and accept longer intervals. Put the strain
   beside the setting in `.env.example`, measured in this phase: while a capture runs the
   game thread gives it up to 2 ms of every pulse, and each generation is the whole world
   written to Redis (past 64 MiB at full size); a shorter interval costs more of both, and a
   longer one restores an older world. Two limits must follow the interval, or a crash
   restores nothing: at boot `REDIS_WORLD_STATE_MAX_AGE` (300 seconds by default) refuses a
   generation older than itself, and by the time the next capture is due a generation is as
   old as the interval plus the time its capture took.

Done when: a capture of that size publishes, with a test above the old 64 MiB limit; it finishes
within its budget under load; consecutive failures raise an alert with the age of the last good
generation; a raise leaves the corpse's items on the raised creature and a player's pet cannot
wear or wield a hidden item by keyword; a server captures nothing unless
`REDIS_WORLD_STATE=TRUE`, which the template no longer sets; and with recovery on, captures
start ten minutes apart by default, the strain is stated beside the setting, and a generation
taken at that interval is still accepted at boot. Each has its test.

How each item is done (decided 2026-10-04, after the
[baseline](persistence-done.md#the-baseline-measurement-done)):

1. The ceiling goes from 64 MiB to 256 MiB, and the store's chunk limit follows it (256
   chunks of 1 MiB). It stays a fixed number because it is what bounds memory: the game holds
   one generation and Redis two for a moment. A mob costs about 400 bytes and an item 3.3 KiB,
   so 256 MiB holds the 54,000 mobs and 70,000 objects on the ground, against 11,000 today;
   past it a capture fails and item 3 says so. The capture reserves the ceiling's address
   space once, so its buffer never moves: the old one doubled as it grew, and each doubling
   copied the whole capture on the game thread, 18 ms at 32 MiB. Chunking and streaming were
   not needed: the generation already goes to Redis in 1 MiB chunks, and only the ceilings
   stopped it.
2. Time is the capture's only limit, as it is for events since Phase 7. A capture is 0.34 s
   of work, but it took 193 s on an idle server, because each call stopped after 1,024
   steps, and a step is as little as one room looked at (253,000 rooms, two calls a second).
   The step limit goes; the 2 ms a call stays. Each object record also allocated and
   zero-filled room for 512 items (1.7 MB) to write one, three quarters of the capture's
   work: it writes into one scratch array instead. The 300 s budget stays: nothing needs it
   changed once a capture takes a tenth of it.
3. A failed attempt is counted where the capture is driven (`redis_world_runtime.c`): a
   capture that failed or expired, a generation that did not publish, and an attempt that
   could not start because the writer lease or the floor worker was unavailable. A published
   generation resets the count. The third failure in a row raises one
   `domain=world_recovery` alert whose action is the reason (`capture_failed`,
   `capture_expired`, `publish_failed`, `writer_unavailable`, `floor_unavailable`) and whose
   detail is `failures=N last_ack_sequence=N last_ack_age_secs=N` (-1: none since boot). The
   `redis detailed` and runtime health outputs show the same age.
   Found with it: a writer that lost its lease could never publish again without a restart.
   The lease was renewed only by a publish, so a run of failures longer than the lease (the
   three days on staging), a Redis restart or a flush ended it for good. A publish now takes
   the lease when nobody holds it, and still refuses when another writer does.
4. All six raises put the corpse's items on the raised creature again, and
   `place_raised_item()` goes. `wear()`, which every way of equipping goes through, refuses
   a hidden item for a player's pet, so `wear`, `wield` and `hold` by keyword skip it;
   `wear all` keeps its own check, which lets it go on to the next item.
5. `.env.example` and the local `.env` set `REDIS_WORLD_STATE=FALSE`. The code needs no
   change to do nothing when it is off: the capture job is registered disabled, the pulse
   returns at its first test, floor drops are not recorded, and no attempt is counted, so no
   alert. A journey pins it.
6. The interval's default is 600 seconds and it accepts 5 to 3,600. One limit follows it by
   ten minutes (five for a capture's budget, five for the restart):
   `REDIS_WORLD_STATE_MAX_AGE` is at least the interval plus 600 seconds, which is also its
   default; a lower setting is raised to it, since it could only refuse every generation.
   It accepts up to a day.
   The writer lease does not follow the interval. It was ten minutes and only a publish
   renewed it, so at a ten-minute interval it ran out before every publish. It is 60
   seconds and the game loop renews it every 20 (since the MR !10 review, which found that
   a lease as long as the interval kept the boot after a crash or a copyover from capturing
   for that long).
   `.env.example` no longer sets the maximum age, so it follows the interval. A server whose
   `.env` still says `REDIS_WORLD_STATE_INTERVAL=10` keeps capturing without a pause until
   the line is removed: server configuration.

One journey is the measurement and the pin for items 1 and 2, as in Phase 7:
`test_mysql_world_capture_journey.py`, in `make test-db`. It boots the full world on a
disposable MariaDB and Redis with recovery on while mortals play, reads the capture's own
record of its size and time, kills the server and sees the next boot restore the world.
`run_world_recovery_journey.py` is the pin for items 3, 5 and 6, on the mini world.

Done: each item has its record under
[Phase 8 progress](persistence-done.md#phase-8-progress). A generation of 69 MiB is
captured in about 20 s of its 300 s under 30 players, with no pulse past 250 ms, and a
crash restores it in 3 s
([the measurement](persistence-done.md#the-capture-journey-and-the-measurement-done)).

Nothing is left on #2, which is closed (owner, 2026-10-04): how a server sets its recovery
variables is for whoever runs it.

## The settings that were left (#3, #5, #6)

Phases 4, 6 and 7 left settings on their work items as server configuration. The owner
decided each of them on 2026-10-04: the repository carries a default, whoever runs a server
sets what differs, and the items close. They were done on `fix/2-persistence-phase-8`, after
Phase 8, and landed with it ([record](persistence-done.md#the-settings-that-were-left-done)).

1. **Restore drills are off by default** (#3). `drill_seconds` 0 in the backup policy means
   no drills, and the example policy ships it: the drill timer's command does nothing and
   `status --require-drill` asks for no receipt. A stored generation is then checked again
   only when it is restored or pruned.
2. **The off-host replica is off by default** (#3). It already was (`replica_root` null).
3. **The backup before a boot is off by default** (#3). `cycle_mud.sh` takes it only with
   `PREBOOT_BACKUP=1`, and then still refuses a boot whose backup fails.
   `SKIP_PREBOOT_BACKUP` is gone: skipping is the default.
4. **The MariaDB buffer pool is 1 GB by default** (#5). `compose.yaml` starts MariaDB with
   it, and CONFIGURATION.md states it for a server's own MariaDB, whose configuration is
   not the repository's.
5. **The charset warnings** (#6). A MariaDB client unpacked outside the system's prefix
   read another package's charsets and warned twice on every call. The compatibility check
   and the launcher pass the client the charsets directory under its own prefix when there
   is one.
6. **The WebSocket and health listener is off by default** (#6). A server is assumed to have
   no website: the listener, and `GET /health` with it, opens only with
   `DURIS_WEBSOCKET=TRUE`. The Docker deployment and the restore qualifier set it, since
   both wait for `/health`. **A server with a website sets it in its `.env` before it takes
   this change.**
7. **The stale `proxies_priv` grant** (#6) is deleted on the server that had it.
8. **The game's database user** (#6) is named for its environment (`duris_local`,
   `duris_staging`, `duris_prod`), so that a command or credential sent to the wrong server
   fails to log in. The template and CONFIGURATION.md say so; staging, which connected as
   `duris_prod`, connects as `duris_staging`.
9. **The logins without a password** (#6) are left, to see whether they are a real issue.

## What was cut, and why

Each part was removed in turn ([ablation](../../.agents/skills/ablation/SKILL.md)) and stayed only
if a requirement or a concrete risk failed without it. Cut:

- **A per-item revision to order saves across threads:** one writer applies them in capture order.
- **A live uid-to-object index to catch dupes:** the key and the load filter already stop a second
  copy.
- **Deleting the old owner's row when a save claims an item:** loads ignore stale rows, and the old
  owner's next save removes them.
- **Releasing items an owner no longer holds:** the next holder claims them; a release would also
  trip foreign keys and need a "nobody" owner. The cost is on the ground: a dropped item keeps
  its last holder's record. A capture leaves out an item the ledger in memory names a
  character for, and a restore asks the character's save, not the record, whether an item
  is held (the MR !10 review; CONFIGURATION.md says which objects come back).
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
- **Registering callback names at `add_event` time:** listing local and weak symbols names
  every callback without touching a call site.
- **A load tool beside the test:** the budget journey prints what the loop measured and
  takes `--players` and `--hours`.
- **A higher callback limit:** it was raised twice already; time is the limit.
- **Failing the budget journey on any slow pulse:** it judges what it can put on a rent, a
  camp, the hourly event or the event pass. Beside the other database tests two runs in
  five had one unrelated command of 225 to 346 ms; by itself, even with its database
  paused, the journey had none.
- **A flat-file production build in the gate:** production runs MariaDB; the flat-file
  backend built clean at `-O2` once.

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

Nothing. Phases 4 (alerts and logs), 5 (bugs from the logs), 6 (backups), 7 (the game loop)
and 8 (world recovery, with [the settings that were left](#the-settings-that-were-left-3-5-6)
on #3, #5 and #6) are done and on master, and the work items the plan took, #2 to #7, are
closed ([record](persistence-done.md#phase-8-landed-done)).
