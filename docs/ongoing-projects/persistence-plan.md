# Persistence reset: memory is the authority again

**Date:** 2026-09-28

This file is the plan: the rules, the design, the three phases, what was cut and
[What is left](#what-is-left). Finished work is recorded in
[persistence-done.md](persistence-done.md): when an item of What is left is finished, its record
(what landed, decisions, tests, verification, commits, bugs found) goes there and the item leaves
the list. A decision that changes the framework is written here.

**Status (2026-10-02):** Phases 1 and 2 are done. Phase 3 steps 1 to 9 are done in this worktree,
on `fix/7-persistence-phase-3`, which is pushed.

**Work items:** #7 (player saves and deaths), and the persistence causes behind #5 (game freezes),
#3 (the player-save journal breaking backups) and #6 (persistence alert storms).

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
8. **It ends.** Phase 1 removes every cause of the problems above. The later phases only simplify.

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

- A save cannot be rejected; its only failure is a lost connection, which the writer retries
  without the game noticing.
- No character is ever held after death, logout or idle rent.
- No corpse raise, resurrection or decay can fail on the database.
- Shutdown and copyover never wait on a failing save.
- The game loop issues no query after boot.
- The database cannot hold one item under two owners, and `logs/log/dupes` accounts for every
  item a save or load gave up.
- No persistence code is left that nothing reaches, and the branch passes the gate.

All but the last hold now.

## What is left

1. **Two fixes the ablation found**, each in its own commit:
   - **Delete the ledger reconcilers that memory authority broke.** A save claim bumps
     `item_revision` and `item_owner_revision` with no ledger row (`item_claim_repository.c`),
     and balances have no ledger that explains them. The runbook already says Phase 3 removes the
     currency, epic and frag reconcilers; `reconcile_item_ownership.sh` has the same flaw (on
     `duris_dev` it reports `owner_revision_mismatch=4`). Delete the four, and take them out of
     `reconcile_phase02_domains.sh`,
     [Domain reconciliation](../operations/RUNBOOK.md#domain-reconciliation), the header of
     `repair_item_nesting.sh` and the contracts that name them
     (`test_currency_transaction_contract.py`, `test_epic_transaction_contract.py`,
     `test_documentation_contract.py`, `test_item_ownership_contract.py`,
     `test_durable_container_put_contract.py`, `test_phase02_raw_queue_retirement.py`). The
     auction, artifact and boon reconcilers stay; all three pass on `duris_dev`.
   - **Bring `docs/reference/DATABASE.md` up to date.** "Critical transactions and current item
     ownership" still calls the table the authority and requires a transfer for every
     reparenting, and "Consistent player load" still checks a durable revision Phase 1 removed.
     Rewrite both to [How it works](#how-it-works), and drop the runbook's "Epic ledger cutover
     and reconciliation" section.
2. **The gate on this worktree's head:** `./scripts/format.sh --all --check`, then
   `make test-all -j16 TEST_JOBS=16` alone, then `make test-db` and `npm test --prefix site` side
   by side. Fix each failure in its own commit, with a regression test where behavior changes,
   rerun what failed, and push the branch.
