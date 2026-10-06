# 0002. Persistence reset: memory is the authority

**Status:** Accepted and implemented
**Date:** 2026-09-28 (decided); on `master` since 2026-10-02

This records why the server saves the way it does and what was deliberately left out. How
it works is described where the code is documented:
[PLAYER_SAVE_PIPELINE.md](../persistence/PLAYER_SAVE_PIPELINE.md) (the one writer, what a
save writes, what a load reads),
[CRITICAL_COMMAND_PIPELINE.md](../persistence/CRITICAL_COMMAND_PIPELINE.md) (money, epic
points and the economy's commands) and [DATABASE.md](../reference/DATABASE.md).

## Context

Before the reset the database was in charge. An item could not move, a character could not
die or log out, a corpse could not be raised and coins could not change hands until a
database transaction had committed, so the game waited or refused. Every player save was
checked against the ownership table `item_current_owner` and thrown away whole on any
disagreement, and nothing ever settled one. On a running server that meant:

- saves that failed forever and characters held in memory after death or logout;
- deaths that froze the whole game for two seconds per retry;
- corpse raises that failed, and shutdowns that cancelled themselves;
- a player-save journal that broke backups, and alert storms from all of the above.

## Decision

1. **Memory is the authority.** Items move, characters die and corpses are raised in
   memory, at once. The database is a copy that catches up.
2. **Saves never refuse.** A save writes what its owner holds in memory, in one
   transaction. Where the ownership table disagrees, the save corrects it and writes an
   audit row. There is no rejection, retry loop, stuck character, blocked shutdown or death
   hold.
3. **One item, one owner.** `item_current_owner` has `PRIMARY KEY (item_uid)`, so the
   database cannot record two owners for one item. A load hands each owner only what that
   table gives it. A save or load that loses an item to another owner writes one line to
   `logs/log/dupes` and carries on.
4. **One writer.** A single background thread writes everything in capture order, so every
   save is newer than the last one for its owner and no revision fence is needed.
5. **The game loop never waits for the database.** It issues no query after boot; writes
   and reads are jobs on the writer.
6. **Corpses just work.** Raising, resurrecting, decaying and looting a corpse happen in
   memory and cannot fail on the database.
7. **Simple.** Each rule fits in a sentence, and nothing was built that no requirement
   needed (see [What was left out](#what-was-left-out-and-why)).

## Consequences

- **A crash loses what had not reached the database**, at most one 30-second checkpoint
  (`dirty-player-checkpoint`): the classic MUD model. A clean shutdown or copyover writes
  everything first. Shutdown gives the writer 30 seconds and always goes; a copyover that
  cannot drain in that time is called off.
- **Nothing is duplicated by a crash.** An item handed over during one stays with
  whichever owner was written last. Money is lost rather than paid twice, because the
  owner it leaves is queued first. On MariaDB a bank delta or `sql` job whose commit
  outcome is unknown is reported, not retried.
- **Every server is treated as new.** No journal is replayed and no death record is kept.
  Migration `0034_retire_death_custody_and_accounting` drops the death custody,
  restitution and economy accounting tables. `CRITICAL_COMMAND_JOURNAL_DIR` remains only
  for the locker identification receipts.
- **A dropped item keeps its last holder's ownership record** until another owner's save
  claims it or the next boot reaps it (see the release entry below). At boot no character
  is in memory, so a player's active record whose item is in no payload row is an item
  the player no longer holds: both backends delete those records then, before the writer
  starts. A record an auction's custody row, an `artifact_domain_state` row or another
  record (its contents) still references is kept for the foreign keys; the pass repeats
  until it deletes nothing, so a container goes after its contents. During an uptime the
  load path tolerates such a record and counts it (`missing_payload_rows`, logged with
  `DURIS_PERSISTENCE_TRACE`).
- **World recovery is a convenience, not a safety net.** Characters, pets, corpses,
  lockers, banks and shops are saved without it. It is off unless a server sets
  `REDIS_WORLD_STATE=TRUE` ([CONFIGURATION.md](../operations/CONFIGURATION.md)).
- The economy still commits in the database where it must (auctions, the collector, item
  grants, repairs and destruction, boons, artifacts, combat outcomes, zone touches), as
  critical commands on the one writer. Auctions, shops and the collector take what they
  trade out of memory at submit and give it back if the command is refused.

## What was left out, and why

Each part of the design was removed in turn and stayed only if a requirement or a concrete
risk failed without it. These did not stay. Do not add one back without the failure that
needs it.

| Left out | Why it is not needed |
| --- | --- |
| A per-item revision to order saves across threads | One writer applies saves in capture order. |
| A live uid-to-object index to catch dupes | The primary key and the load filter already stop a second copy. |
| Deleting the old owner's row when a save claims an item | Loads ignore stale rows, and the old owner's next save removes them. |
| Releasing items an owner no longer holds inside a save | The next holder claims them. A release in the save's transaction would trip the foreign keys and fail the save, and would need a "nobody" owner. The cost is on the ground: a dropped item keeps its last holder's record until the next boot reaps it (work item #11; a record of an item that stopped existing was never claimed again, and the table grew with play). A world capture leaves out an item the in-memory ledger names a character for, and a restore asks the character's save, not the record, whether an item is held. |
| Saving the receiver the moment an item changes hands | The 30-second checkpoint writes both sides together. |
| The player-save journal | A replay would skip the corpse and locker saves between player saves and could apply half a hand-over. |
| One job for both saves when money moves | Queuing the owner it leaves first is enough. |
| Holding a command while an earlier one on its key awaits publication | The writer already runs them one at a time. |
| A retry cap in the command coordinator | It would only drop a command whose outcome is unknown. |
| A barrier job | Replacing only the last queued save keeps capture order. |
| A receipt table for bank deltas | Neither backend can add a delta twice without one. |
| A second job kind for reads | One `sql` job kind carries both. |
| Converting SQL that never runs after boot | It cannot make the loop wait. |
| Reading an account back after saving it | Its other sessions get the saved copy from memory. |
| Dropping the opening-baseline and event-log tables | Nothing needed it, and it is a schema change across a migration, the bootstrap, the boot probes, the lifecycle manifest and the legacy dump import. |

The follow-up work on alerts and logs, backups, the game loop and world recovery made its
own smaller decisions; each is stated beside what it governs
([EVENTS.md](../reference/EVENTS.md), [BUILDING.md](../guides/BUILDING.md),
[BACKUPS.md](../operations/BACKUPS.md),
[WORLD_RECOVERY_PIPELINE.md](../persistence/WORLD_RECOVERY_PIPELINE.md),
[CONFIGURATION.md](../operations/CONFIGURATION.md)).

## Validation

The reset was done when all of these held, and each has a test in `make test-all` or
`make test-db`:

- A save cannot be rejected; its only failure is a lost connection, which the writer
  retries without the game noticing.
- No character is held after death, logout or idle rent.
- No corpse raise, resurrection or decay can fail on the database.
- Shutdown and copyover never wait indefinitely on a failing save.
- The game loop issues no query after boot.
- The database cannot hold one item under two owners, and `logs/log/dupes` accounts for
  every item a save or load gave up.
- No persistence code is left that nothing reaches (see
  [Finding unreachable code](../guides/BUILDING.md#finding-unreachable-code)).
