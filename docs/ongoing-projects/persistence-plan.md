# Persistence reset: memory is the authority again

**Date:** 2026-09-28

This file is the plan: the framework (the problem, the rules, the design, the three phases and
what was cut) and [What is left](#what-is-left). Completed work is recorded in
[persistence-done.md](persistence-done.md), which links back here.

**Where completed work goes:** all of it goes into [persistence-done.md](persistence-done.md),
not here. When a step or an item of [What is left](#what-is-left) is finished, write its record
there (what landed, the decisions made on the way, tests, verification, commits and the bugs
found) and take the item off the list. This file keeps only the framework and what is left; a
decision that changes the framework is written into the framework here.

**Status (2026-10-01):** Phases 1 and 2 are on `master` (see
[Review and branches](persistence-done.md#review-and-branches)). Phase 3 steps 1 to 9 are done on
`fix/7-persistence-phase-3`, which is pushed; no MR is open yet. See [What is left](#what-is-left).

**Work items:** #7 (player saves and deaths). This plan also removes the persistence causes behind
#5 (game freezes), #3 (the player-save journal breaking backups) and #6 (persistence alert storms).

## What is wrong

Today the database is in charge. An item cannot move, a character cannot die or log out, a corpse
cannot be raised and coins cannot change hands until a database transaction has committed. The game
either waits for that or refuses. On top of that, every player save is checked against the ownership
table `item_current_owner` and thrown away whole if the two disagree in any way. Nothing ever settles
a disagreement, so the refusal repeats forever.

What that did on staging from 2026-09-22 to 2026-09-28:

- One character's save failed 3,416 times in a row, and 36 characters hit custody mismatches.
- 8,815 extracts were refused because a final save had failed. The characters stayed in the game and
  were idle-rented again and again.
- 11 dead characters were held in memory, one of them for about 50 hours.
- About 490 whole-game freezes lasted 2 seconds each, from the death-disposition wait. `rent` blocks the
  game for 1.9 s typically and up to 5 s; `quit` blocks it for 1.3 s typically and up to 3.4 s.
- Corpse raises failed (`raise_commit_failed`, `raise_submission_failed`).
- Shutdowns were cancelled because a save had failed, so restarts ended in SIGKILL.

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

## How it works after the change

### One writer

A single background thread writes everything to the database, in the order it was captured:

- player saves, with their pets;
- corpse saves;
- locker saves;
- saved room items;
- `log_entries` rows from `sql_log()` (since Phase 1 review round 1);
- since Phase 2: critical commands (step 1), bank deltas (step 2), shopkeeper saves (step 6) and
  the game thread's own SQL, as `sql` jobs (step 8).

This writer is the existing player save worker, cut from two threads to one
(`PLAYER_SAVE_WORKER_DEFAULT_THREADS`), with a job kind for each of these.

- **Order:** saves are applied in capture order. A newer save of the same owner replaces its
  queued one only when that is the last job queued; otherwise it is queued behind, so it never
  overtakes a job that relies on the owner's earlier save (see the MR !3 review round 1).
- **Failures:** if the connection is lost, the writer retries the job at the head of the queue. Any
  other failure is logged, the job is dropped, and the owner is marked dirty so its next save carries
  the state again. The game is never told to wait or to refuse.
- **No journal:** the player-save journal goes. A queued save lives only in memory; see
  [What a crash costs](#what-a-crash-costs).

### What a save does

In one transaction:

1. **Claim what it holds.** For every item the owner holds:
   - no row in `item_current_owner`: insert one;
   - the row names this owner: nothing to do;
   - the row names another player, corpse, locker, room or pet, or (since Phase 2 step 7) an
     auction, a shopkeeper or the collector: set it to this owner, and write an `item_owner_audit`
     row with the item, vnum, old owner, new owner and time. The economy takes its items out of
     memory before its command, so a later save never holds what it took.
2. **Leave out what was destroyed.** A row that says the item was destroyed (a sale for
   destruction, a spent coin pile) is final: only a save captured before the destruction can
   still hold the item, so it is left out, with its contents, and logged to `logs/log/dupes`.
   (Until Phase 2 step 7, a row naming an auction, a shopkeeper or the collector was left out the
   same way.)
3. **Write the owner's rows** (`player_items`, `corpse_items`, `locker_items` and the others) from
   memory, as today.

Nothing else is checked. There is no revision fence: with one writer, every save is newer than the
last one for that owner. A character with no `player_data` row yet gets one instead of failing.

### What a load does

A load takes an item row only if `item_current_owner` has no row for that uid or names this owner.
Any other row is a stale or duplicate copy. It is skipped and logged to `logs/log/dupes`, and the
owner's next save removes it for good.

That is the whole dupe protection:

- the key allows one owner per item;
- the last save to claim an item wins;
- nobody loads what they don't own.

A character or locker is not loaded while it still has a save in the queue, so a quick relog always
reads the latest state. The login waits in its loading state while the game loop carries on.

### What a crash costs

A clean shutdown or copyover writes everything first. A crash loses whatever had not reached the
database, at most one 30-second checkpoint (`dirty-player-checkpoint`). That is the classic MUD model.

Nothing is duplicated: an item handed over during a crash ends up with whichever owner was written
last. There is one loss case: a hand-over where the giver's save landed and the receiver's did not.
Both are written in the same checkpoint batch, so that window is milliseconds.

Since Phase 2 money follows the same rule: the owner it leaves is saved first, so a crash between
the two saves loses the money but never pays it twice. On MariaDB a bank delta or an `sql` job
whose commit has an unknown outcome (the connection dropped during `COMMIT`) is reported and not
retried, which can lose it but never apply it twice.

## Phase 1: end the problems

Done. The record of each step is in [Phase 1 progress](persistence-done.md#phase-1-progress).

Each step is its own commit with a focused regression test. The flat-file backend gets the same change
wherever it has the same code, and its CI build and full-world boot test must keep passing.

1. **One writer.**
   - Cut the save worker to one thread.
   - Add job kinds for corpse, locker and saved-room-item snapshots.
   - A newer save of an owner replaces its queued one and moves to the back. (Since MR !3 review
     round 1, only the last job queued is replaced; otherwise the newer save queues behind.)
   - Take the journal out of `player_save_pipeline.c`, and drop the `PLAYER_SAVE_JOURNAL_DIR`
     requirement.
   - Apply the failure policy from [One writer](#one-writer).
2. **Saves never refuse.**
   - In `player_snapshot_repository.c`, replace `verify_player_item_custody()`,
     `verify_player_death_item_payload()` and `verify_pet_custody()` with one `claim_items()` helper
     that every job kind uses.
   - Remove the `save_revision` fence and the missing-row failure.
   - Delete the custody-mismatch recapture and retry handling in `player_save_pipeline.c`.
   - Add a new additive, guarded migration for `item_owner_audit`.
3. **Loads filter on the ownership table.**
   - Apply the filter to player and pet items (`player_load_repository.c`, `player_load_items.c`),
     `sql_load_all_corpses()`, locker items and `sql_restore_saved_items()`.
   - Delete degraded loads (the `CHAR_RFLAG_LOAD_DEGRADED` admission in `player_load_materialize.c`).
     A load always succeeds with the rows that pass the filter.
   - Remove the blocking login fallback in `account.c` (`player_load_pipeline_wait()`), and hold a load
     while its owner has a save queued.
4. **Items move in memory.**
   - `item_command_uses_durable_ownership()` returns false, so get, drop, give and put take their
     in-memory branch.
   - The other callers of `item_movement_transaction_submit*()` move the object directly: `actobj.c`,
     `actwiz.c`, `actmove.c`, `actoth.c`, `salchemist.c`, `rogues.c`, `drannak.c`, `magic.c`,
     `chaos_materials.c`, `forced_weapon_drop.c`, `fight.c` and `handler.c`.
   - Shops, auctions and the collector take what the player holds in memory. Their
     `item_ownership_runtime_lookup()` prechecks use the object's real holder; one example is the
     "That item's ownership is still being synchronized" refusal in `auction_houses.c`.
     `item_transfer_repository.c` claims the item, with an audit row, instead of failing on an owner
     or revision mismatch.
5. **Deaths happen at once.**
   - `make_corpse()` puts a player's carried and worn items into the corpse, the way it already does
     for NPCs, without `submit_next_corpse_item()`.
   - `die()` queues the corpse save, then the player's save, and extracts the character immediately.
   - The NOWHERE hold and its retry chain go: `event_death_extract_retry()`,
     `death_extract_retry_pulse()`, `save_disputed_death_disposition()` and the 2-second
     `DEATH_DISPOSITION_TIMEOUT_MSEC` wait.
   - Coins stay in a dead character's wallet in Phase 1, because `money_to_inventory()` is skipped for
     players. The currency transactions still own the wallet; Phase 2 puts coins back into corpses.
6. **Corpses in memory.**
   - `persistence_defer_corpse_raise()`, `_resurrection()`, `_room_release()`, `_unmaking()`,
     `_wall_of_bones()`, `_compaction()` and `_destruction()` return false. Their 18 callers in
     `necromancy.c`, `magic.c` and four spec files, and `Decay()` in `handler.c`, then run the
     in-memory code that already follows each call.
   - `writeCorpse()` and `writeSavedItem()` queue a job instead of writing SQL on the game thread.
   - A corpse leaving the world queues its delete.
7. **Logging out never waits.**
   - `persistence_save_character_terminal()` and its variants in `actoth.c`, and the terminal call in
     `files.c`, queue the save and return success. The caller extracts at once.
   - There is no extract refusal, no terminal retry and no idle-rent loop.
8. **Shutdown and copyover always go.**
   - Both wait up to 30 s for the writer to drain.
   - Shutdown then exits, naming any owner it could not write.
   - Copyover goes ahead once drained. Otherwise it is called off and the game keeps running.
   - The `shutdown_cancelled` paths in `comm.c` go.
9. **The dupe log.** Add `logs/log/dupes`, with one line per item a save left out or a load skipped:
   uid, vnum, the owner that lost it and the owner that has it.

### Phase 1 tests

New focused tests in `tests/async/`:

- A save whose items the ownership table gives to other owners commits. The table then names the
  saver, and each change has an audit row. This test has a MariaDB leg.
- An item held by an auction is left out and logged, and the rest of the save commits.
- A stale row that the table gives to another owner is not loaded, and is logged.
- A player death puts every item in the corpse and extracts the character in the same pulse. The
  corpse job is queued before the player's, and the game thread makes no SQL call.
- Raising, resurrecting and decaying a corpse make no database call and cannot fail.
- `rent`, `quit` and `camp` extract at once while the writer is stalled.
- Shutdown with the database down exits within the bound.
- The writer applies saves in capture order, and a replaced save moves to the back (since MR !3
  review round 1, only the last job queued is replaced).

Tests that pin the old behaviour (custody contracts, death disposition, corpse batches, terminal
fences) are rewritten to the new rules or deleted.

**Journeys** run first on a local server with the `.env` account, then on staging:

- die and loot your own corpse;
- raise corpses as a necromancer;
- give an item to another player;
- rent, quit, and log straight back in;
- shut down with players online.

**Staging checks** after a day:

- no custody, terminal-save, death-recovery or corpse-raise alerts in the logs;
- `rent` and `quit` gone from `COMMAND OP SLOW`;
- no 2-second `NEVENT SLOW` stalls.

Production follows with the owner's go-ahead.

## Phase 2: money, points and the rest of the loop

Done. The record of each step is in [Phase 2 progress](persistence-done.md#phase-2-progress).

- **Money.** The wallet, coins and bank move to memory.
  - `apply_status()` stops skipping the wallet columns.
  - Bank changes are queued as deltas, because the characters of one account share the bank.
  - Each currency transaction (95 references) becomes the in-memory update that the NPC branches
    already make.
  - Coins drop into corpses again.
  - An action that moves money between two saved owners queues the owner it leaves first, so a
    crash cannot pay twice (see [Phase 2 steps](#phase-2-steps)).
- **Epic points and frags** move the same way: the save writes them, and their transactions become
  in-memory updates.
- **Auctions, shops and the collector** take what they trade out of memory when the command is
  submitted, and MariaDB shopkeepers are saved on the writer after the seller. The economy
  exception in the claim then goes.
- **Game-thread SQL.** The game thread's own queries move off the loop. The plan counted 345
  `qry()` calls; the survey found about 330 functions using the game thread's connection, in
  `sql.c`, `sql_player.c`, `artifact.c`, `auction_houses.c`, `boon.c`, `account_reward.c`,
  `epic.c` and a dozen others:
  - calls that write are queued on the writer;
  - calls that read happen at boot, from memory, or through the async path.

  The game-loop query count must then stay at zero after boot.

### Phase 2 steps

Phase 2 keeps the rules. Each step is its own commit (or a few) with a focused regression test, on
both backends; the MariaDB legs run on a disposable server. Steps 2 to 5 must ship together: the
save writes the wallet only once nothing else writes it.

**One pattern for what is left.** Each transaction API keeps its signature, so its callers stay as
they are; Phase 3 inlines what is left and deletes the rest.

- Balances (wallet, bank, epic points, frags): the submit changes the character at once and calls
  its completion before returning. The save writes the result.
- What must still commit in the database (auctions, the collector, item transfers and grants,
  boons, artifacts, combat outcomes, zone touches, death restitution) runs on the one writer,
  queued at submit on the game thread, so it lands in capture order with the saves around it.

**Two owners.** When money moves between two saved owners, the one it leaves is queued before the
one it reaches: the giver's save before the receiver's, the corpse before the looter, the player
(whose save records a grant as paid) before the bank credit, a bank debit before the wallet it
fills. A crash between them loses the money; it can never pay it twice. One job for both was
considered and cut: ordering on the one writer gives the same guarantee without a new job kind.

1. **Critical commands on the one writer.** `critical_command_coordinator_submit()` queues the
   command as a writer job instead of journaling it for its own workers. The job carries its own
   copy of the command, so one queued at shutdown still lands. A lost connection is retried by the
   writer at the head; any other outcome goes to the existing completion channel, so the operation
   table, its fences, the pulse and every completion handler stay as they are. A journal left by
   an older server is replayed once at boot, onto the writer.
2. **Money in memory.**
   - The save writes the wallet: `apply_status()` stops skipping copper to platinum, and the
     flat-file save writes the wallet into the domain record in its authority transaction.
   - `currency_transaction_submit()` and its variants change the wallet at once, and the bank view
     of every online character of the account and side, then complete before returning. A change
     that would take a balance below zero is refused with `ENOSPC`, as the repository refused it.
   - A bank change is queued on the writer as a delta (`bank` job): MariaDB adds it to the
     `account_banks` row, creating it; flat-file adds it to the bank domain.
   - Coins: get, drop, give and put take the branches NPCs take, and so does
     `money_to_inventory()`. The guards (`currency_transaction_can_submit_nonrebasable()`,
     `_player_busy()`, `_coin_item_busy()`) admit.
3. **The economy stops writing balances.** The auction, collector, coin transfer and combat
   outcome repositories (both backends) stop reading and writing wallet and bank columns and their
   revisions. The money moves in memory: taken at submit and given back on a refusal (a bid, a
   purchase, a fee), or given at commit (a sale's proceeds, a money pickup).
4. **Coins drop into corpses.** `make_corpse()` turns a player's wallet into a pile in the corpse.
5. **Epic points and frags in memory.** The save writes epics, frags and old frags (both
   backends). `epic_transaction_submit*()` and the combat outcome's frag and epic changes update
   the character at once; the repositories stop writing those columns.
6. **Shops in memory.** A trade moves the item and the coins at once, the way the completion
   already publishes it. The shopkeeper's stock is saved through the writer, after the seller's
   save. (As done: the MariaDB stock is saved in order rather than claimed, because it has no
   ownership rows; flat-file shops keep the shop trade command, and a sale takes its item out of
   the seller's inventory at submit. Auction listings and collections take their items out at
   submit the same way.)
7. **The economy exception goes.** With auctions, the collector and shops committing in capture
   order, `item_claim_owner_is_economy()` goes: a save claims whatever its owner holds.
8. **Game-thread SQL off the loop.** Everything below is an `sql` job on the one writer
   (`src/sql/sql_async.h`), in capture order with the saves, and each job runs in one transaction.
   - Writes are queued with the statement built on the game thread (`sql_queue()`,
     `sql_queue_statements()`). A write that needs the database's answer first, such as a lookup
     that decides between an update and an insert, runs its lookup on the writer, just before the
     write it decides (`sql_queue_work()`).
   - Reads that feed a command's output run on the writer, behind the writes queued before them,
     and hand copies of their rows to a game-thread callback on a later pulse (`sql_read()`,
     `sql_read_for()`; `sql_read_work()` for a read that takes more than one query).
   - Reads the game logic depends on come from memory, loaded at boot and kept up to date by the
     writes above. Two variations: data that belongs to one character is read when it enters the
     game (the checks fail closed until it arrives), and data that the website edits rather than
     the game is also read again on a timer (`mud_info`, every minute).
   - Logging in to an account reads the account on the writer while the connection waits with
     its input held and the game loop carries on, the way the Phase 1 player load already
     waits (`CON_PLAYER_LOAD`). Saving an account is queued; the sessions of the same account
     get the saved account copied from memory, not read back.
   - An offline character (finger, disguise, lockers, artifacts, the websocket handlers) is loaded
     through the Phase 1 player load pipeline and materialized, with a callback on a later pulse,
     instead of converting `restoreCharOnly()`'s SQL. A lookup that only needs a pid reads a
     name-to-pid index in memory, kept current when a character is created, renamed or deleted.
   - Only code reachable after boot is converted. Boot and shutdown may still query, and a
     function nothing calls never runs, so it waits for Phase 3 to delete it.
   - While the loop runs, every query on the game thread's connection is counted and each site is
     logged once, and a journey pins that the loop issues no query after boot.

### Phase 2 tests

New focused tests, each failing without its step:

- Critical commands and saves land in capture order (a linked harness with the real writer).
- A deposit, withdrawal, payment and reward change the wallet and bank at once; a spend beyond a
  balance is refused; the save writes the wallet; the bank delta lands (a MariaDB leg).
- Coins given between two players: the giver's save is queued before the receiver's.
- A player's coins go into the corpse at death, and looting them claims the pile.
- An epic purchase and a PvP award change the character at once; the save writes them.
- A shop sale and purchase move the item and the coins at once; the shopkeeper's stock survives a
  restart.
- An auction listing and a bid take the item and the coins at once and give them back when
  refused; a stale save cannot take a listed item back.
- A journey pins that the game loop issues no query after boot (with the rest of step 8).

The Phase 1 journeys (death and corpse loot, necromancer raise, give, rent/quit/relog, shutdown
with players online) run again, and the local `.env`-account session covers money, the bank, a
shop and an auction by hand.

## Phase 3: delete what is left over

Steps 1 to 9 are done; the record of each is in
[Phase 3 progress](persistence-done.md#phase-3-progress). The rest is in
[What is left](#what-is-left).

Remove the code nothing calls any more. Every server is treated as new (decided on 2026-09-30):
none holds an older journal to replay or death records to keep, so the one-time journal replays
and the death custody and restitution feature go too.

- `item_movement_transaction.c`;
- what is left of `item_transfer_command.c` and `item_transfer_repository.c`;
- `item_ownership_runtime.c`, once the collector no longer reads it (see
  [Phase 3 progress](persistence-done.md#phase-3-progress); it stays: step 6 found shops,
  auctions and the creation grants reading it for the items the economy holds);
- `corpse_lifecycle_*.c`;
- the custody and degraded-load code;
- `currency_transaction.c`;
- the item and currency parts of `critical_command_*`;
- the player-save journal: `player_save_journal.c`, the one-time legacy replay in
  `player_save_pipeline_init()` with its revision fence (`PLAYER_SAVE_LEGACY_REPLAY`), and the
  `PLAYER_SAVE_JOURNAL_DIR` setting in the configuration, scripts, backup policy and data
  lifecycle manifest;
- the critical-command journal's one-time replay, and what only it reaches: the currency
  repository, the coin transfer command, the corpse lifecycle wallet, the accounting bank
  commands and the record-only replay of epic, combat and stone commands.
  `CRITICAL_COMMAND_JOURNAL_DIR` stays, because locker identification keeps its receipts there;
- the death custody and restitution feature: the restitution runtime and its boot advisory
  lock, the native restitution command, `scripts/player_death_restitution.py`, the restitution
  locker notice and their docs; flat-file `player-deaths/`; and the tables
  `player_death_disposition`, `player_death_custody` and `player_death_restitution_*`, dropped
  by a new guarded, re-runnable migration (the existing ones are immutable), with their runtime
  compatibility and data lifecycle entries;
- the game-thread SQL functions nothing calls, found by step 8 (see
  [What is left after step 8](persistence-done.md#what-is-left-after-step-8)): the `*_legacy`
  auction functions, `auction_money_pickup_committed()`, `auction_houses_activity()`, the dead
  boon, epic zone, outpost, poll, spellbook, guild, locker and artifact functions listed there,
  `event_write_statistic()`, the account bank functions, and the legacy player load and save
  that only the boot pfile migration still uses;
- the flat-file equivalents of all of the above.

That is roughly 20,000 to 30,000 lines. A deployment that still holds an older journal starts
without it (nothing reads it any more), and the migration drops its death records.

Also decided on 2026-09-30:

- **The economy accounting foundation goes** (decided on 2026-10-01; the owner chose that over
  keeping it as a separate project). Nothing live reached it: the schema-2 command envelope,
  the typed intent and plan, the baseline command and its storage, both bank transactions,
  the flat-file accounting store and the SQL source snapshot, about 29,000 lines of code,
  tests and docs. Its bank transaction committed wallet and bank changes in the database,
  which memory authority no longer does. Its tables are dropped by the same migration as the
  death custody tables (step 3).
- **The collector's death intake is restored in memory** (the owner chose that over deleting
  it). Since Phase 1 step 5 nothing enrols a player's death (`collector_death_enrollment_*()`
  has no caller), so the collector, off by default behind `collector.enabled`, never collects
  from a corpse. Phase 3 enrols the death at `make_corpse()` again and moves the collector's
  scheduled collection (`collector_collection_prepare()`) off the runtime cache onto the live
  objects (done in [step 6](persistence-done.md#step-6-the-collectors-death-intake-done)).

Carried over from Phases 1 and 2, done in Phase 3:

- Flat-file lockers never load their items: the backend's `sql_load_locker()` is a stub and
  nothing reads the locker records it writes, so what a flat-file locker holds does not come
  back after a restart. Phase 3 loads them.
- The journey that dies, restarts with full-world corpse restoration and loots the restored
  corpse (the minimal-world journeys skip corpse restoration).
- The staging sign-off, which never ran: staging still runs a build from 2026-09-23. Once
  Phase 3 is on `master`, deploy it there, run the journeys in [Phase 1 tests](#phase-1-tests)
  and, after a day, the staging checks listed there.

### Phase 3 steps

The list, the "left for Phase 3" notes and the items above went through ablation on
2026-10-01. What decides "nothing reaches it" is the linker, not a name: both server builds
compiled with `-ffunction-sections -fdata-sections` and linked without `-rdynamic` but with
`-Wl,--gc-sections -Wl,--print-gc-sections` name every function no path from `main()` reaches,
and a function is dead only when both backends drop it (see
[Finding dead code](#finding-dead-code)). Code behind a switch that always returns false
(`item_command_uses_durable_ownership()`, `durable_corpse_lifecycle_enabled()`) looks reachable
until the switch goes, so each step removes its switches first and then deletes what the linker
drops.

Changed from the list by the ablation:

- `currency_transaction.c` is not dead: it is the in-memory wallet and bank API with 13 callers
  (Phase 2 step 2). It keeps its live functions and loses the dead ones. Inlining it would copy
  its delta, bank and save-first logic into every caller.
- `item_movement_transaction.c` holds the creation grants, which stay a critical command on the
  writer by design ("What must still commit in the database" in
  [Phase 2](#phase-2-money-points-and-the-rest-of-the-loop)). Its movement transactions are dead
  and go; the grants stay, and so does what they need of `item_transfer_command.c` and
  `item_transfer_repository.c`.
- Dead code outside the persistence reset (unregistered specs, spells, `nq`) is not part of it.

The steps, in order (later ones delete what earlier ones leave unreachable):

1. **The journals** (done, see [Step 1](persistence-done.md#step-1-the-journals-done)): both
   one-time replays and everything about the journals in the server, scripts, backup and restore
   tooling, manifests, docs and test fixtures.
2. **What only the critical-command replay reached** (done, see
   [Step 2](persistence-done.md#step-2-what-only-the-replay-reached-done)): the coin transfer and
   bank commands, schema 2 and the whole economy accounting foundation, on both backends.
3. **The death custody and restitution feature** (done, see
   [Step 3](persistence-done.md#step-3-death-custody-and-restitution-done)), with migration 0034
   dropping its tables and the economy accounting tables.
4. **The durable item movement** (done, see
   [Step 4](persistence-done.md#step-4-the-durable-item-movement-done)): the durable branches in
   `actobj.c` behind `item_command_uses_durable_ownership()` and the switch itself, the craft
   path, the synthetic transfer adapter, `OBJ_RFLAG_CREATION_CANDIDATE`, and the coordinator's
   journal-era submit results and functions.
5. **The durable corpse lifecycle** (done, see
   [Step 5](persistence-done.md#step-5-the-durable-corpse-lifecycle-done)): the paths behind
   `durable_corpse_lifecycle_enabled()`, `corpse_lifecycle_*.c` and their flat-file backend, the
   corpse raise save fence, the corpse wallet and the currency repository it called, and the
   terminal save's fence table.
6. **The collector's death intake** (done, see
   [Step 6](persistence-done.md#step-6-the-collectors-death-intake-done)): the death enrolled
   with the corpse's save again, and collection reading the live corpse.
   `item_ownership_runtime.c` stays: shops, auctions and the creation grants still rely on it
   (see the step).
7. **The game thread's dead SQL** (done, see
   [Step 7](persistence-done.md#step-7-the-game-threads-dead-sql-done)): the functions
   [What is left after step 8](persistence-done.md#what-is-left-after-step-8) names, and
   whatever else of the persistence code the linker drops after steps 1 to 6.
8. **Flat-file lockers load their items** (done, see
   [Step 8](persistence-done.md#step-8-flat-file-lockers-keep-their-items-done)).
9. **The die, restart and loot journey** (done, see
   [Step 9](persistence-done.md#step-9-the-die-restart-and-loot-journey-done)).
10. **Staging** (after Phase 3 is on `master`): the sign-off above.

Each step does its area with its tests, in its own commits, and passes the gates:
`make test-all`, `make test-db`, the flat-file and pfile builds and
`./scripts/format.sh --all --check`.

Build and test commands used throughout:

- `make -C src -j16` for the MariaDB server, and `make -C src pfile` for the pfile build.
- The flat-file build goes into a scratch directory:
  `make -C src PERSISTENCE_BACKEND=flatfile BIN_ROOT=<dir> OBJDIR=<dir>/objects/server SERVER_BIN_DIR=<dir>/server DMS_BINARY=<dir>/server/dms_new -j12`.
- `./scripts/format.sh --all --check` before each commit, because CI formats every tracked file.

### Finding dead code

```sh
# Objects with one section per function, in their own directories (MariaDB, then flat-file).
make -C src -j16 OBJDIR=$PWD/bin/analysis/objects SERVER_BIN_DIR=$PWD/bin/analysis \
    DMS_BINARY=$PWD/bin/analysis/dms_new EXTRA_CFLAGS="-ffunction-sections -fdata-sections"
make -C src -j16 PERSISTENCE_BACKEND=flatfile OBJDIR=$PWD/bin/analysis/flat-objects \
    SERVER_BIN_DIR=$PWD/bin/analysis/flat DMS_BINARY=$PWD/bin/analysis/flat/dms_new \
    EXTRA_CFLAGS="-ffunction-sections -fdata-sections"
```

Then take each build's final link line from the make output, drop `-rdynamic` (it exports every
symbol, which keeps them all), append `-Wl,--gc-sections -Wl,--print-gc-sections` and run it
from `src/`. Each `removing unused section '.text.<symbol>' in file '<object>'` line names a
function nothing reaches in that build. A function is dead when every build that compiles it
removes it; `c++filt` turns the symbols back into names. Compare demangled names with
`st_mysql` read as `MYSQL`: the flat-file build stubs `MYSQL`, so a function taking a
connection has a different mangled name in each build. A function only a test calls counts as
dead and goes with its test, unless it is test API (a reset, count or health hook, a fixture
builder or a harness's seam): those stay. The list is a lead, not proof: read the source
before cutting (a function reached only through a dead branch shows as live, and an inlined
one as dead).

## What was cut, and why

The plan was put through [plan ablation](../../.agents/skills/ablation/SKILL.md): each part was
removed in turn, and it stayed only if a requirement or a concrete correctness risk failed without it.
These parts were cut:

- **A per-item revision or sequence number to order saves across threads.** One writer applies saves
  in capture order for free.
- **A live uid-to-object index to catch dupes in memory.** The key and the load filter already stop a
  second copy from being stored or loaded.
- **Deleting the old owner's row when a save claims an item.** Loads ignore stale rows, and the old
  owner's next save removes them.
- **Releasing items an owner no longer holds.** The next holder claims them. A release would also trip
  the foreign keys from `auction_item_custody` and `artifact_domain_state`, and would need a new owner
  type for "nobody".
- **Saving the receiver the moment an item changes hands.** Dirty players are already checkpointed in
  one batch every 30 s, so both sides of a hand-over land together.
- **Keeping the player-save journal.** After a crash it would replay player saves without the corpse
  and locker saves between them, and could apply half a hand-over. Dropping it also removes one of the
  journals that made backups fail (#3).
- **Moving money in Phase 1.** Deaths were the only reason Phase 1 needed it, and leaving coins in the
  dead character's wallet removes that. This is the one visible, temporary gameplay change in Phase 1.
- **Rewriting the 345 legacy `qry()` calls in Phase 1.** They are small statements. The multi-second
  freezes came from the persistence waits that Phase 1 removes.
- **One job for both saves when money moves between two owners (Phase 2).** Queuing the owner the
  money leaves before the one it reaches, on the one writer, already means a crash can lose the
  money but never pay it twice, with no new job kind.
- **Holding a command's execution while an earlier one on the same key waits for its publication
  (Phase 2).** On the one writer commands already run one at a time in capture order; the fence
  still tells callers the key is busy until the game thread acknowledges the publication.
- **The coordinator's retry cap (Phase 2).** Like a save, a command that loses its connection is
  retried by the writer until it lands or shutdown names it; a cap would only drop a command whose
  outcome is unknown.
- **A barrier job that later saves cannot replace (MR !3 review round 1).** A newer save replaces
  a queued one only when that is the last job queued, which keeps capture order exactly with no
  new job kind.
- **A receipt table for bank deltas (MR !3 review round 1).** A MariaDB delta runs in a
  transaction and a commit with an unknown outcome is not retried; a flat-file retry writes the
  bank record its first attempt prepared. Neither can add a delta twice, and neither needs a
  migration.
- **A second job kind for reads (step 8).** One `sql` job kind carries writes and reads; a read's
  job copies its rows back to the game thread.
- **Converting what never runs after boot (step 8).** A function nothing calls, or one only boot
  calls, cannot make the loop wait. The first waits for Phase 3; the second may keep its query.
- **Converting `restoreCharOnly()`'s SQL (step 8).** The Phase 1 player load pipeline already loads
  and materializes a character off the loop; offline loads reuse it, and pid lookups use a
  name-to-pid index instead of loading a whole character.
- **Reading an account back after saving it (step 8).** Memory holds the account; its other
  sessions get the saved copy from memory. The copy is still needed: a recovery reset saves a
  scratch account, and a session left open must not write the old password back.
- **A public multi-query read (step 8).** Cut first because `sql_read_work()` had no caller
  outside `sql_async.c`, then kept: the account read is a multi-query read for a connection,
  not a character, so it is the first caller.

## Done when

- A save cannot be rejected. Its only failure is a lost connection, and the writer retries that
  without the game noticing.
- No character is ever held after death, logout or idle rent.
- No corpse raise, resurrection or decay can fail on the database.
- Shutdown and copyover never wait on a failing save.
- After Phase 1, saves, logouts, deaths and corpses never wait on the database from the game loop.
  After Phase 2, nothing on the loop does: the game-loop query count stays at zero after boot. (On
  `master` since `60f56fb5b` for the whole game thread; the game-loop queries journey pins it with
  an empty `NOT_CONVERTED` list.)
- The database cannot hold one item under two owners, and `logs/log/dupes` accounts for every item a
  save or load gave up.
- After Phase 3, no code is left that nothing reaches, and staging has run the journeys and a day
  of checks on the result.

## What is left

In order. When an item is finished, its record goes into
[persistence-done.md](persistence-done.md) and the item leaves this list.

1. **The full gates on the branch head.** Steps 1 to 9 passed them; the cleanup after step 9
   (below) has not: `make test-all`, `make test-db`, the flat-file and pfile builds and
   `./scripts/format.sh --all --check` (see [Phase 3 steps](#phase-3-steps)).
2. **The Phase 3 MR**, from `fix/7-persistence-phase-3` to `master`. Tag the head it reads
   `persistence/phase-3-review-0`. Each review round is tagged on the head it read and on the
   head with its fixes (`persistence/phase-3-review-<n>`), so `git diff` between two tags shows
   one round. It lands as one `--no-ff` merge of the reviewed head, with no rebase, so every
   review tag still names the commit that was reviewed.
3. **Step 10, staging**, once Phase 3 is on `master` (staging runs tagged `master`): the staging
   sign-off carried into [Phase 3](#phase-3-delete-what-is-left-over), that is the journeys in
   [Phase 1 tests](#phase-1-tests) and, after a day, the staging checks listed there. Its
   database first needs `python3 scripts/migration_runner.py run` for `0033_item_owner_audit`
   and `0034_retire_death_custody_and_accounting` (COMPAT-E002 otherwise). This is the last
   item of [Done when](#done-when).
4. **Production**, only with the owner's go-ahead, and with the same migrations before the new
   binary boots.

Waiting on the owner's decision; nothing in [Done when](#done-when) needs either:

- **The cleanup after step 9**, which nobody asked for: the dead transfer branches that step 7
  left for a decision were cut in `4621a6c8a` and `01a345b84` (see
  [their record](persistence-done.md#after-step-9-the-dead-transfer-branches-not-asked-for)).
  Whether it stays is the owner's call.
- **The opening baselines and the event log tables.** Since the accounting foundation went, the
  opening baselines (`currency_wallet_baseline`, `epic_balance_baseline`,
  `combat_frag_baseline`) are written for every player but read only by the boot coverage
  probes and the account projection repair, and nothing writes the event log's tables any more
  (`sql_pwipe()` still empties them). Removing either is a schema change: a migration, the
  bootstrap, the probes, the lifecycle manifest and `scripts/import_legacy_dump.py`.

To watch: `test_flatfile_full_world_boot.py` aborted once in nine runs during Phase 1 step 3
(SIGABRT at the first connection, before character creation) and did not reproduce. If it
happens again, run it under gdb.
