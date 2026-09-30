# Persistence reset: memory is the authority again

**Date:** 2026-09-28

**Status (2026-09-30):**

- **Phase 1** ([!2](https://gitlab.com/max757/duris/-/merge_requests/2)) and **Phase 2 steps 1 to
  7 and the foundation of step 8** ([!3](https://gitlab.com/max757/duris/-/merge_requests/3)) are
  on `master`, merged together in `7887bf1d6` after two and one review rounds (see
  [Review and branches](#review-and-branches)).
- **The rest of Phase 2 step 8** (the game thread's remaining SQL,
  [!4](https://gitlab.com/max757/duris/-/merge_requests/4)) is on `master` since `60f56fb5b`,
  after one review round. **Phase 2 is done.** See
  [Step 8](#step-8-game-thread-sql-off-the-loop-done).
- **Phase 3** has not started. It continues on `fix/7-persistence-phase-3`; see
  [Phase 3 progress](#phase-3-progress) for where it starts.

See [Phase 1 progress](#phase-1-progress) and [Phase 2 progress](#phase-2-progress) for what each
step did and how.

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

Remove the code nothing calls any more. Every server is treated as new (decided on 2026-09-30):
none holds an older journal to replay or death records to keep, so the one-time journal replays
and the death custody and restitution feature go too.

- `item_movement_transaction.c`;
- what is left of `item_transfer_command.c` and `item_transfer_repository.c`;
- `item_ownership_runtime.c`, once the collector no longer reads it (see
  [Phase 3 progress](#phase-3-progress));
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
  [What is left after step 8](#what-is-left-after-step-8)): the `*_legacy` auction functions,
  `auction_money_pickup_committed()`, `auction_houses_activity()`, the dead boon, epic zone,
  outpost, poll, spellbook, guild, locker and artifact functions listed there,
  `event_write_statistic()`, the account bank functions, and the legacy player load and save
  that only the boot pfile migration still uses;
- the flat-file equivalents of all of the above.

That is roughly 20,000 to 30,000 lines. A deployment that still holds an older journal starts
without it (nothing reads it any more), and the migration drops its death records.

## What was cut, and why

The plan was put through [plan ablation](../../.agents/skills/plan-ablation/SKILL.md): each part was
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

## Phase 1 progress

This section is the hand-over log. Each step records what landed, the decisions made while
implementing it, and anything a later step must pick up.

Build and test commands used throughout:

- `make -C src -j16` for the MariaDB server.
- The flat-file build goes into a scratch directory:
  `make -C src PERSISTENCE_BACKEND=flatfile BIN_ROOT=<dir> OBJDIR=<dir>/objects/server SERVER_BIN_DIR=<dir>/server DMS_BINARY=<dir>/server/dms_new -j12`.
- `./scripts/format.sh --all --check` before each commit, because CI formats every tracked file.

### Step 1: one writer (done)

- `src/player/player_save_worker.c` is now the one writer: a single `std::thread`, one FIFO
  (`std::list`) plus an index of the queued job per owner, and the job being written held apart
  in `inflight`. Job kinds are `player`, `corpse`, `locker` and `saved_item`
  (`persistence_job_kind`). Player jobs carry a `player_snapshot` and use the apply callback;
  the other kinds carry a `persistence_job_write_fn` closure that runs on the writer thread.
- A newer job for the same owner removes the queued one and goes to the back. A job for an owner
  whose save is being written simply queues behind it.
- Failure policy: `retryable_failure` and `ambiguous_commit` (a lost connection) are retried at
  the head with a backoff from 100 ms to 5 s, so no later save overtakes them. Anything else is
  returned as a completion and dropped. Shutdown interrupts a retry; the job stays listed in
  `persistence_writer_pending_owners()` so the caller can name it.
- Revision bookkeeping moved out of the writer. `player_save_pipeline.c` calls
  `player_revision_queue()`, captures, submits, and then `player_revision_acknowledge_durable()`
  straight away: a character is clean once the writer has its save. A failed write re-marks the
  captured components with `player_save_pipeline_mark()` (only while the character is live).
- The dispatcher thread, `pending_append`/`durable_ready` and journal appends are gone.
  `player_save_pipeline_init()` takes the old `PLAYER_SAVE_JOURNAL_DIR` only to replay a leftover
  journal once, synchronously on the main thread before the writer starts, and then renames it
  `player-save.journal.retired-<ms>` if anything could not be applied
  (`player_save_journal_retire()`). This is the upgrade path: on staging the stuck characters'
  newest state exists only in that journal. **Step 2 must keep the replay revision-fenced**
  (skip records whose revision is not newer than `player_data.save_revision`) even though
  ordinary saves lose the fence, or a replay could roll a character back.
- Locker saves: `locker_async.c` keeps its per-locker slots and game-thread completion handling,
  but its sealed SQL script now runs as a `locker` job on the writer (keyed by `locker_id`), and
  its own pthread is gone. A lost connection inside the script is returned as retryable so the
  writer retries it; any other failure still pushes a failed result, which runs the old
  synchronous fallback (`sql_save_locker()` on the game thread). Revisit in step 2 when lockers
  claim their items.
- Terminal saves still wait (`player_save_pipeline_terminal()` pumps the pulse until the
  completion for its revision arrives; the journal hand-off result is gone). Step 7 removes the
  wait.
- `world persistence` prints a `player_pipeline` line and a `writer` line; the `player_journal`
  line is gone.
- Tests: `test_player_save_worker.py` (capture order, replacement, head retry, failures, shutdown
  naming), `test_player_save_pipeline.py` (now a linked harness: legacy replay and retire,
  handoff, replacement, re-mark on failure, drain bound), plus contract updates in
  `test_phase01_recovery_gate.py`, `test_player_save_journal.py`, `test_sql_worker_thread_init.py`,
  `test_locker_ownership_cutover.py`, `test_terminal_save_safety.py`,
  `test_character_persistence_gap.py`, `test_death_item_custody_contract.py` and
  `test_player_item_custody_write_guard.py`.
- `PLAYER_SAVE_ERROR_CUSTODY_PAYLOAD_MISMATCH` now lives only in
  `player_snapshot_repository.c`; step 2 deletes it with the custody checks.

### Step 2: saves never refuse (done)

- One claim rule for every item graph, in two places:
  - MariaDB: `claim_items()` in `src/item/item_claim_repository.c`, called by
    `player_snapshot_repository.c` for the player's items and each pet's items, inside the
    save transaction.
  - Flat-file: `flatfile_item_repository_prepare_claim()` builds one catalog after-image,
    committed in the same authority transaction as the player file
    (`flatfile_player_snapshot_apply()`).
  - Shared rules live in `src/item/item_claim.{h,c}` (`item_claim_owner_is_economy()`,
    `item_claim_written_items()`, `item_claim_log_dupes()`). Corpse, locker and saved-item jobs
    (steps 1 and 6) must use the same helpers.
- The claim, per item, parents before children: no row → insert; same owner → fix placement
  (root, parent, vnum, state) silently; another owner → take it, bump `item_revision`, and write
  an `item_owner_audit` row (flat-file: a `claimed` line in `logs/log/item_claims`); an auction,
  shopkeeper or collector row → the item and its contents are left out of the save and logged to
  `logs/log/dupes`.
- **Coins:** a money object (`ITEM_MONEY`) with an existing row is never claimed or revived; the
  currency transactions own coin custody until Phase 2. Without this, a save captured just before
  a coin pickup committed revived a destroyed pile (`test_flatfile_player_repository.py`'s coin
  matrix caught it). A pile with no row gets one. Step 4 narrowed this to spent piles only: a live
  pile moves in memory now, so a save claims it like any item.
- Owner revisions: each owner whose holdings changed (the claimer, and every owner that lost an
  item) gets its revision bumped once per save; the claimer's row is created if missing.
- No revision fence and no missing-row failure: `apply_snapshot()` inserts a minimal
  `player_data (pid,name)` row when there is none. Only the one-time legacy journal replay keeps the
  fence: the pipeline passes `PLAYER_SAVE_LEGACY_REPLAY` as the apply context, and both backends
  skip a record whose revision is not newer than the stored one.
- Removed: `verify_player_item_custody()`, `verify_player_death_item_payload()`,
  `verify_pet_custody()`, `read_durable_revision()`, the flat-file `establish_item_baseline()`, and
  the refusal paths in `sync_restitution_runtime_state()` (it now just updates the sidecar for
  delivered items the player still holds). A pet row is found by `pet_uid` alone and follows
  whoever holds the pet.
- The flat-file save now takes the authority lock. It is not reentrant, and a new player's domain
  baseline takes it itself, so the save releases it around that call.
- Migration `0033_item_owner_audit` (additive, no foreign keys). Everything that pins the
  schema head was updated: `migration_manifest.json`, `runtime_compatibility_manifest.json`
  (216 tables, fingerprints measured on clean `mariadb:10.11` and `mysql:8.0` containers:
  bootstrap + all immutable migrations, then `verify_runtime_compatibility.sh` prints the actual
  value; the same method reproduced HEAD's sealed values first), `runtime_compatibility_contract.h`,
  `data_lifecycle_manifest.json` (250 stores), `bootstrap_multithread_safe.sql`, the two
  validators, and the tests that pin counts or the head. **Any existing database needs
  `python3 scripts/migration_runner.py run` before this binary boots (COMPAT-E002 otherwise).**
- Tests: `test_player_save_claim.py` (flat-file leg plus contracts), the MariaDB leg
  `tests/async/run_player_save_claim_mysql.sh` (in `make test-db`; also passes on
  `PLAYER_SAVE_CLAIM_DB_IMAGE=mysql:8.0`), and rewrites of the tests that pinned custody refusal
  or the fence (`test_player_item_custody_write_guard.py` deleted; the flat-file player
  repository, playtime, death-disposition, output-preference and trophy harnesses updated).
- Found while doing this: `run_output_preferences_mysql.sh` and `run_experience_trophy_mysql.sh`
  had not linked for a while (missing codec and restitution sources, `sql_escape_string`,
  `-lcrypto`), so they are not in `make test-db`. Their link is fixed; the trophy script's second
  harness, `player_load_repository_mysql_harness`, still expects `component_failure` for a bad
  trophy row where the loader now degrades. Step 3 rewrites load outcomes, so fix that
  expectation there and then add both legs to `make test-db`.

### Step 3: loads filter on the ownership table (done)

- The filter: a load takes an item row when `item_current_owner` has no row for its uid or the
  row names the loading owner, in any state. Otherwise the row is skipped, counted in
  `stale_item_rows`, and logged to `logs/log/dupes` as `load_skipped uid= vnum= lost_by= held_by=`
  (`dupe_log_item()`). An unreadable row is skipped and counted too. Nothing about item rows
  refuses a load any more.
  - Player and pet items (MariaDB): `parse_item_payload()` in `player_load_repository.c` returns
    `accepted`, `foreign` or `invalid`. An unrecorded item (no ownership row) is placed from its
    payload row once every row is read; a recorded one keeps the ownership row's placement. A root
    that disagrees with the graph is corrected in `player_load_reconcile_item_topology()` and
    counted in `repaired_item_rows`. An ownership row with no payload row is only counted
    (`missing_payload_rows`): its next holder claims it.
  - Player and pet items (flat-file): `build_item_identities()` in `flatfile_player_repository.c`
    reads each payload uid's record with the new `flatfile_item_repository_load_uids_locked()` and
    applies the same rule; contents of a skipped container move to the top level. A legacy pet
    without a uid carries items its owner holds, so they count in `authoritative_item_count`
    as they do on MariaDB.
  - Corpses, lockers, private chests and saved room items (MariaDB) go through
    `sql_persistence_item_owner_matches_identity()` in `sql.c`: no row or a matching row loads,
    another owner's row is skipped and logged, and a failed lookup keeps the item (losing it would
    be worse than a copy the next claim settles). Only an active row is hydrated into
    `item_ownership_runtime`, which the item commands still use until step 4. What a skipped
    container holds moves up a level: to the corpse's top level (both passes in
    `sql_load_all_corpses()`; before this an item whose container was skipped or malformed was never
    placed and leaked), to the locker level (`append_loaded_objects()`), into the private chest, or
    up the saved room item, which no longer fails its source-graph check over one stale child.
- **Deferred to step 6:** the flat-file corpse and room loaders still use their strict
  `flatfile_world_reconcile_item_ownership()`; they get the filter when corpses and room items are
  saved through the writer with claims.
- Degraded loads are gone: `player_load_outcome::degraded`, `PLAYER_LOAD_DEGRADED_*`,
  `degraded_components`, `CHAR_RFLAG_LOAD_DEGRADED`, `CHAR_RFLAG_LOAD_ITEM_PAYLOAD_GAP`,
  `pc_only_data::load_degraded_components`, `PLAYER_LOAD_ITEM_SKIP_MAX`, the degraded save guards
  in `files.c`, `sql.c`, `sql_player.c` and `player_save_pipeline.c`, and the payload-gap death
  route in `fight.c`. A load step fails only on a database error or a limit; the load then fails as
  a whole and the login is asked to try again. The materializer refuses (instead of admitting
  degraded) when something it must set up fails.
- Logins never block: `load_char_into_game()` in `account.c` submits the load and parks the
  descriptor in `CON_PLAYER_LOAD`; the sync fallback, `execute_account_load_sync()` and the retry
  of `timed_out`/`retryable_failure` results are gone. Account character deletion loads the same
  way (`PLAYER_LOAD_MODE_ACCOUNT_DELETE`; `account_delete_char_loaded()` asks for the final
  confirmation once the load arrives). The legacy non-account login in `nanny.c` (unreachable:
  its states are dispatched only without `USE_ACCOUNT`, which is always defined) lost its sync
  fallback too. Copyover restore is the only
  caller of `player_load_pipeline_wait()`/`_execute_sync()`; it runs before the game loop.
  `player_load_pipeline_login_admit()` was an unused shim and is gone.
- Hold: `player_load_pipeline_set_hold(player_save_pipeline_load_held)` (set in `comm.c`). The
  load worker rotates a held request to the back of its queue and loads the others; when every
  queued request is held it sleeps 10 ms. A held request that reaches its deadline is answered
  `timed_out`. `player_save_pipeline_load_held(pid)` is true while the writer has a job for the
  pid (`player_save_worker_pid_pending()`) or a staff target fence holds it. Lock order: the load
  worker calls the hold with its own mutex held; nothing holding the writer or save-pipeline mutex
  takes the load mutex. Lockers were already held: `lockerName_is_inuse()` counts a locker whose
  async save slot is dirty or in flight.
- Found while doing this, fixed in its own commit (`916f99520`): the coin failure matrix in
  `run_currency_transaction_schema_mysql.sh` inserted a second `player_items` row for a pile the
  coin put had already projected, so every later coin merge failed with `EILSEQ`. It had been
  failing since `b839cadbd`.
- `make test-db` now also runs the four legs that link the player loader:
  `run_player_load_repository_mysql.sh`, `run_currency_transaction_schema_mysql.sh`,
  `run_experience_trophy_mysql.sh` and `run_output_preferences_mysql.sh`.
- Tests: `tests/async/player_load_filter_mysql_harness.cpp` (in `run_player_save_claim_mysql.sh`:
  the giver's stale sword row is skipped and logged after the taker's save claims it, a quarantined
  own row and an unrecorded row still load, and the giver's next save clears the stale row), the
  flat-file leg in `flatfile_player_save_claim_harness.cpp`, the hold in
  `test_player_load_pipeline.py`'s linked harness, the contracts in `test_player_save_claim.py`,
  and rewrites of `player_load_repository_mysql_harness.cpp`, `test_player_load_items.py`,
  `test_player_load_topology.py`, `test_death_item_custody_contract.py`,
  `test_character_persistence_gap.py` and `test_locker_receipt_recovery.py`.
- Journey rewrite: `test_flatfile_combat_journey.py`'s payload-gap death (a ghost ownership record
  under a held item, then a death that had to take the disposition route) became
  `ghost_ownership_record()`: the character loads, the record is only counted, and it saves and
  camps out normally. The restart check now expects the inventory to survive re-entry. (Its printed
  ~13 s is the camp timer: `quit` camps mortals, `RENT_CAMPED`.) `test_account_character_delete_runtime.py`
  drives the asynchronous delete load.
- **Interim race until steps 5 and 6 land:** a player save queued before a death can land after the
  old durable corpse batch and claim the items back from the corpse, so a corpse loot is then
  refused with "ownership records disagree". It made `test_flatfile_combat_journey.py` fail once at
  `recover_player_corpse` (passed on rerun). Steps 2 to 6 must ship together.
- Environment limitation: `run_player_load_repository_spellbook_mysql.sh` needs the
  `duris-issue-213-tools` Docker image, which is not available here; its link line was updated but
  it was not run.
- Open: `test_flatfile_full_world_boot.py` aborted once in nine runs (SIGABRT at the first
  connection, before character creation). It did not reproduce; if it recurs, run it under gdb.

### Step 4: items move in memory (done)

Kept to the step 4 list after a plan-ablation pass: anything that did not stop a real failure was
taken back out (see "Removed in the ablation" below).

- `obj_to_char()` lost its ownership gate. It refused to publish any item the runtime ownership
  catalog did not give the player, and routed a fresh object through a creation grant. The object is
  placed, and the next save records it (the claim inserts a missing row).
  `OBJ_RFLAG_CREATION_CANDIDATE` is still set by `db.c` but nothing reads it; Phase 3 deletes it.
- `item_command_uses_durable_ownership()` returns false, so get, drop, give, put, empty and their
  bulk forms take the in-memory branches that already existed next to the durable ones. Those
  branches carry the game rules (NOLOOT, NODROP, weight, cursed). The durable branches in
  `actobj.c` stay as dead code until Phase 3 deletes them with `item_movement_transaction.c`.
  `get` from a uid-less container no longer refuses ("lacks authoritative ownership").
- The other callers move the object directly; their durable submissions and publication callbacks
  are deleted: slip (`rogues.c`), steal from a player (`steal_player_item()`/`steal_from_player()` in
  `actoth.c`), soulbind to another player (`give_soulbind_item()` in `magic.c`, which also clears a
  replaced soulbind), key break (`actmove.c`), wizard `load` and the `storage` command (`actwiz.c`;
  the flat-file branches are gone, both backends now use the in-memory path), the Chaos pouch
  (`collect_into_pouch()`), and the forced weapon drop (`forced_weapon_drop_result` is now only
  `rejected` or `dropped`).
- Crafts: `item_movement_transaction_submit_craft()` retires the inputs and gives the outputs in
  memory, then calls the completion with `committed=true` before returning. The five callers in
  `salchemist.c` and `drannak.c` are unchanged. Phase 3 can inline it.
- `item_get_source_owner()` (coin gets) resolves the source from the live placement: a room, a
  player, a PC corpse, or a locker chest (`locker_owner_for_room()`/`_for_container()`).
- **Decision: creation grants stay durable in Phase 1.** They are asynchronous (the loop never waits
  on them), they only create new uids, and they are not in the step 4 list.
- The economy still moves items through its own transactions until Phase 2, so what memory says a
  player, room, corpse, locker or pet holds is what those transactions take
  (`item_claim_owner_is_memory_held()`, inline in `item_claim.h`):
  - The item transfer repository (`item_transfer_repository_execute_at_offset()`: coins, grants,
    pet and shop transfers), the auction listing (`transition_items()`, whose custody rows then take
    the claimed revisions) and the flat-file `apply_transfer()` and `prepare_auction_transfer()`
    stop fencing on a memory-held owner's revision and claim the items first:
    `claim_transfer_item()` in `item_claim_repository.c` (MariaDB) and `claim_catalog_item()` in
    `flatfile_item_repository.c` insert a missing record, take another owner's (with an
    `item_owner_audit` row, or a `logs/log/item_claims` line) and correct a stale placement. A
    destroyed record is never revived and an item the economy holds is never taken; those fail with
    `ESTALE`. A grant into a container the player holds claims the container too, and the
    `player_items` projection writes the item loose when the container has no row yet.
  - The collector (MariaDB, flat-file and the runtime cache's collector publication) only stops
    fencing on a memory-held owner's revision.
  - Game-thread prechecks take the real holder: the auction listing (no more "ownership is still
    being synchronized") and the shop trade payload (`shop_trade_runtime.c`: a sale no longer asks
    the cache, and a purchase into a bag needs the bag carried).
  - The runtime ownership cache learns a committed transfer out of a memory-held owner instead of
    refusing to publish it (`item_ownership_runtime_apply()`); it counts exactly when it was in step
    and takes the result's revision when a claim moved it.
- **Coin piles.** A save claims a live pile like any item; a spent (destroyed) pile is left out
  (`item_claim_leaves_out()`, which since the MR !2 review applies to every destroyed item). A
  login loads a pile only if the
  character's own saved rows hold it: the MariaDB coin query requires a `player_items` row of this
  pid, and the flat-file reconcile only mentions piles the player file lists. Before this, a pile
  dropped or given away in memory came back at the next login from its custody row, which still
  named the player. The cost: a pile committed after the last save is lost on a crash, which is the
  accepted crash model ([What a crash costs](#what-a-crash-costs)).
- **Flat-file transfer events.** Every flat-file transfer to a player leaves a materialization event
  (`buy_existing`), and a login added back any event item the catalog still gave the player but the
  file lacked. With drops in memory the catalog keeps naming the player, so a dropped kit came back
  and the newbie regrant never fired. A flat-file player save that carries equipment, inventory and
  pets now retires that player's events in the same authority transaction
  (`flatfile_shop_trade_materialization_prepare_player_remove()`, already used by character
  delete), the way a MariaDB save replaces the `player_items` rows a transfer wrote.
- Lockers claim: `sql_save_private_chest_items()` and `sql_save_locker()` run `claim_items()` for
  owner `locker(locker_id, chest_id)` in their transaction, and the async public-chest job captures
  the chest's items (`player_item_snapshot_list_capture()`), opens the transaction itself, claims,
  then runs its script (which no longer starts its own transaction).
  `player_item_snapshot_contents_capture()` captures a container's contents.
- Found while doing this: `run_item_transfer_schema_mysql.sh` ran against the `.env` database, so it
  was never run; it now uses a disposable MariaDB server and is in `make test-db`. Its restitution
  craft payload had not built since the #551 craft validation (it needed `multi_root` and no target
  root).
- **Removed in the ablation** (each had no failing requirement behind it): detaching a record's
  stale child when its container moves (both backends), limiting the `player_items` projection to
  the target pid's own rows, collector claims (the revision relax is enough), the flat-file shop
  trade recording an unrecorded shopper, the shop trade publication's per-item revisions, and the
  deletion of `OBJ_RFLAG_CREATION_CANDIDATE`.
- **Known gaps, to close before Phase 1 ships:**
  - Flat-file storage containers were persisted only through the durable transfers; step 6 gives
    saved room items a flat-file writer job. Flat-file lockers are not a gap of this step: the
    backend never loads a locker's items at all (`sql_load_locker()` is a stub there and nothing
    reads the locker records), so a save job would have nothing to feed. That is a missing
    flat-file feature, not part of Phase 1; it is carried into
    [Phase 3 progress](#phase-3-progress).
  - A floor item is not an owner that saves: an item dropped in memory is gone after a restart on
    both backends (MariaDB never persisted floor drops either). `test_flatfile_full_world_boot.py`
    drops the mace, saves, picks it up and checks it survives the restart with the player.
  - The collector's scheduled collection of antiquities still prepares from the runtime cache
    (`collector_collection_prepare()`): an antiquity moved in memory since load is not collected
    until a reboot refreshes the cache. It is economy code for Phase 2, which left it; it is
    carried into [Phase 3 progress](#phase-3-progress).
  - World recovery (`world_recovery_pipeline.c`) still skips a room item whose cached owner is not
    the room. That is the safe side: it cannot restore a floor copy of an item its dropper's save
    still holds.
  - Until steps 5 and 6, a durable corpse batch could race a queued player save that claimed the
    same items back, which made the combat journey flaky. Resolved: step 5 removed the batch and
    step 6 puts the corpse save on the one writer, behind the player's older saves.
  - Until step 5, a player who dies carrying an item that moved in memory keeps it: the durable
    corpse batch still runs at death, the runtime cache never learned the in-memory move, so the
    batch submits the item as a creation and the repository refuses it (`EEXIST`,
    `corpse rejected_preserved`). Nothing is lost or duplicated, but the corpse is empty. The
    player-corpse part of `run_corpse_haul_journey.py` checks this; it passes since step 5.
- Found while doing this, not fixed (outside Phase 1): on the flat-file backend a character that
  becomes trusted (level 61) is written with identity racewar `ACCT_IMMORTAL` (0, from
  `account.c`) while its player domain keeps the racewar it was created with. The domain load then
  reports `conflict`, which the login turns into a component failure, and the test inspector's
  `inspect` fails. Flat-file banks are keyed by account and racewar, so the fix is a decision about
  which bank an immortal uses. `run_npc_container_claim_journey.py` hit it through the inspector.
  (Resolved as the owner chose in `6e4934ab0`; see [Review round 1 (MR !2)](#review-round-1-mr-2).)
- Tests: `test_items_move_in_memory.py` (contracts for all of the above), the rewritten
  `item_transfer_mysql_harness.cpp` (stale revisions no longer fence; a stale owner's record is
  taken with an audit row; an auction-held item and a destroyed item are refused; a grant claims its
  container), `flatfile_item_repository_harness.cpp` (a pile missing from the player file is not
  loaded; one it lists takes its amount from custody), and rewrites of the tests that pinned the
  durable paths: `test_issue_524_trusted_steal_contract.py`,
  `test_issue_549_cross_player_transfer_contract.py` (its runtime harness, which drove the deleted
  publication callbacks, is deleted), `test_key_break_custody_contract.py`,
  `test_forced_weapon_drop.py`, `test_get_item_source_owner.py`, `test_saved_item_flatfile_routing.py`,
  `test_orphan_item_session_regressions.py`, `test_newbie_grant_lifecycle.py` (the scenarios that
  routed `obj_to_char` into grants are gone), `test_item_movement_input_queue.py`,
  `test_item_ownership_runtime.py`, `test_flatfile_item_repository.py`, `test_shop_trade_runtime.py`,
  `test_auction_transactional_cutover.py`, `test_chaos_infinite_starting_grants.py`,
  `test_bulk_drop_put_durable_chain.py`, `test_item_command_pipeline_contract.py`,
  `test_live_item_movement_contract.py`, and the journeys `test_flatfile_full_world_boot.py` and
  `test_flatfile_newbie_regrant_journey.py` (which read what the player's saved file holds). Every
  harness that links the transfer, auction or collector repository also links
  `item_claim_repository.c`, `item_claim.c`, `dupe_log.c` and `persistence_observability.c`.
- Journeys rewritten for in-memory moves: `run_npc_container_claim_journey.py` no longer inspects
  the ownership catalog after the drop (it checks the NPC takes the nested item, the container
  empties and the server lives). `run_corpse_haul_journey.py` holds only the coin pickup now (the
  committed coins are credited, nothing is taken from a room the actor left), then takes the banana
  with a plain haul, and it honours `TEST_DB_PORT` so it can run on a disposable MariaDB.
- Found while doing this, fixed in its own commit (`b1b31399b`): `run_critical_command_schema_mysql.sh`
  stopped at the linker (restitution sources, and the outbox harness's codecs).
- Verified: `make -C src`, the flat-file build, `./scripts/format.sh --all --check`, the tests
  above, `run_item_transfer_schema_mysql.sh`, `run_currency_transaction_schema_mysql.sh` and
  `run_critical_command_schema_mysql.sh` on disposable MariaDB, `test_playtime_mysql_repository.py`
  on a disposable MariaDB, and the journeys `test_flatfile_newbie_regrant_journey.py`,
  `test_flatfile_full_world_boot.py`, `test_flatfile_combat_journey.py`,
  `test_account_recovery_journey.py`, `test_flatfile_auction_coin_put_journey.py`,
  `test_pet_restart_journey.py`, `run_npc_container_claim_journey.py`,
  `run_saved_item_recovery_journey.py` (disposable MariaDB) and the NPC-corpse part of
  `run_corpse_haul_journey.py` (disposable MariaDB; the player-corpse part waits for step 5).

### Step 5: deaths happen at once (done)

- `make_corpse()` moves a player's carried and worn items into the corpse the way it does for an NPC
  (`corpse->contains = ch->carrying`), then queues the corpse save (`writeCorpse()`) and marks the
  player dirty. `money_to_inventory()` runs only for NPCs, so a player's coins stay in the wallet.
  Moving the items first also brings back two things the durable batch had silently skipped for
  players: owned artifacts are unflagged as they enter the corpse, and divinely bound reward
  containers dissolve inside it (`account_bound_reward_prepare_player_corpse()` walks the corpse).
- `die()` calls the terminal save and extracts at once, whatever the save returns; a failed save is
  logged (`terminal_save_failed`) and the character still leaves. The terminal save still waits
  up to 2 s until step 7.
- Deleted: `submit_next_corpse_item()`, `corpse_item_completion()`, the dispute helpers,
  `death_wallet_pending()`, the whole recovery chain (`event_death_extract_retry()`,
  `schedule_`/`wake_`/`hold_for_death_extract_retry()`, `death_extract_retry_pulse()` and its call in
  `comm.c`, `save_disputed_death_disposition()`, `release_after_terminal_death()`, the
  custody-wait clock and `DEATH_*` constants), the `pc_only_data` fields they used, and the
  spawn-raise skip that waited for the handoff.
- The MariaDB corpse save claims what the corpse holds: `sql_save_corpse()` runs `claim_items()` for
  owner `corpse(item_corpse_owner_id(pid, save_id))` inside its transaction, before it writes the
  `corpse_items` rows, the same way the locker saves do. Without it the ownership rows keep naming
  the player and the corpse load filter drops the items after a reboot.
- **Known gaps:**
  - The collector's death intake rode on the durable `corpse_create` transfer
    (`collector_death_enrollment_attach()`), so the collector no longer enrols player deaths.
    Nothing is lost: antiquities simply stay in the corpse. Economy code for Phase 2, which left
    it; Phase 3 restores it in memory (see [Phase 3 progress](#phase-3-progress)).
  - A flat-file corpse's items were persisted only by those durable transfers (the flat-file
    lifecycle upsert carries the corpse and its money, not its items), so on the flat-file backend
    a corpse's items did not survive a restart until step 6 added the flat-file corpse job.
  - `player_save_pipeline_terminal_death()` and the death-disposition plumbing behind it have no
    caller left; Phase 3 deletes them.
- Tests: `test_deaths_happen_at_once.py`; the death sections of `test_character_persistence_gap.py`,
  `test_terminal_extract_item_retention.py`, `test_persistence_severity.py` and
  `test_live_item_movement_contract.py` now pin the new contract. Deleted with the code they tested:
  `test_collector_death_recovery.py`, `test_corpse_creation_batch.py`,
  `test_corpse_handoff_inflight_contract.py`, `test_death_item_custody_contract.py` (and its
  `run_death_item_custody.sh` wrapper), `test_death_recovery_alert_level.py` and
  `test_death_wallet_retry.py`; also `test_account_reward_container_contract.py` (the reward hook
  now runs with the items already in the corpse) and `test_flatfile_corpse_live_routing.py`.
- Journeys: `test_flatfile_combat_journey.py` checks the player's corpse holds no coins (the wallet
  keeps them). `test_mysql_combat_journey.py` takes the player's saved `player_items` rows as what
  must reach the corpse (the ownership table still names the player for items it dropped in
  memory), and its second half, which drove the deleted disputed-death disposition, now checks a
  second death is immediate and a restart changes nothing.
- Docs: the death sections of `docs/persistence/PLAYER_SAVE_PIPELINE.md` describe the new path;
  `docs/operations/corpse-creation-batches.md` and `docs/testing/DEATH_WALLET_FAILURE_PROOF.md`
  described only the deleted code and are gone. `docs/persistence/economy_accounting/writers.json`
  drops `death.wallet_disposition`, re-anchors the writers whose functions steps 4 and 5 deleted
  (`staff.load`, `staff.storage_repair`, `item.trusted_steal`, `death.corpse_creation`), and has a
  fresh census, so `scripts/validate_economy_accounting.py` passes again (it had drifted on
  master; nothing runs it automatically). Regenerate the census whenever `src/` changes before a
  commit: rerun the scan in that script and keep the file's layout.
- Verified: `make -C src`, `./scripts/format.sh --all --check`, the 162 tests that read
  `fight.c`, `sql_player.c`, `comm.c` or `structs.h`, the validator, and the journeys
  `test_flatfile_combat_journey.py` (three variants), `test_mysql_combat_journey.py` (three
  variants, disposable MariaDB) and `run_corpse_haul_journey.py` (disposable MariaDB; the
  player-corpse part passes now).

### Step 6: corpses in memory (done)

- `durable_corpse_lifecycle_enabled()` returns false, so every `persistence_defer_corpse_*()`
  (raise, resurrection, room release, unmaking, wall of bones, compaction, destruction) returns
  false and its 18 callers, and `Decay()`, run the in-memory code that already follows the call.
  The durable paths behind it stay as dead code for Phase 3.
- `writeCorpse()`, `PurgeCorpseFile()` (a corpse leaving the world), `writeSavedItem()` and
  `PurgeSavedItemFile()` queue a job on the one writer (`queue_corpse_save()` and
  `queue_saved_item_save()` in `files.c`), keyed by the corpse owner id or the item uid, so a newer
  write replaces a queued one and an older save of the player can no longer claim the items back
  after the corpse or room write. The game thread captures the corpse or item graph
  (`player_item_snapshot_contents_capture()`, `player_item_snapshot_tree_capture()`); nothing is
  written on the game thread any more. If the writer refuses a job, MariaDB falls back to the old
  synchronous `sql_save_corpse()`/`sql_save_saved_item()` (which the corpse save claims in, since
  step 5); flat-file alerts `queue_failed`.
- MariaDB: `corpse_snapshot_repository_apply()` and `saved_item_snapshot_repository_apply()` in
  `player_snapshot_repository.c` run in one transaction: replace the corpse row (catalog and
  corpse revisions as before) or the saved item's rows, claim the graph for
  `corpse(item_corpse_owner_id(pid, save_id))` or `room(vnum)` with `claim_graph()`, and write the
  rows with the player save's `insert_item_rows()`, now parameterized by an `item_tables`
  descriptor (player, pet, corpse, saved item). Economy-held items are left out as in a player
  save.
- Flat-file: `flatfile_corpse_snapshot_apply()` and `flatfile_saved_item_snapshot_apply()` in
  `flatfile_player_repository.c` take the authority lock, claim the graph in the ownership catalog,
  and write the world item catalog (`flatfile_world_item_prepare_corpse_snapshot()` /
  `_saved_item_snapshot()`) in one authority transaction. The catalog requires every uid to be
  unique across corpse, saved-item and room records, so a write strips its items from any other
  record that still lists them (the last save to claim an item wins; a saved item left empty is
  dropped). A corpse's coin piles are items in the record and its scalar `money` stays zero, so a
  restore cannot create them twice. The flat-file corpse lifecycle staging
  (`stage_corpse_lifecycle()`, `capture_corpse_lifecycle()`, `capture_corpse_money()`) is gone.
- Tests: `test_corpses_in_memory.py`; `player_save_claim_mysql_harness.cpp` and
  `flatfile_player_save_claim_harness.cpp` now also save, replace and remove a corpse and a saved
  item, check the claims (with audit) and the flat-file strip rule; `test_flatfile_corpse_live_routing.py`
  and `test_saved_item_flatfile_routing.py` pin the job routing.
- `docs/persistence/economy_accounting/writers.json` census regenerated for the new lines.
- Verified: `make -C src`, `make -C src pfile` (`files.c` is also built with `-D_PFILE_`; the purge
  call is guarded), `./scripts/format.sh --all --check`, the validator, the 38 tests that read
  the corpse, saved-item, repository or flat-file world-item code, `test_player_save_claim.py`,
  the MariaDB legs `run_player_save_claim_mysql.sh`, `run_pet_repository_mysql.sh`,
  `run_player_death_disposition_mysql.sh`, `run_output_preferences_mysql.sh`,
  `run_experience_trophy_mysql.sh` and `test_playtime_mysql_repository.py` (disposable MariaDB),
  and the journeys `test_flatfile_combat_journey.py`, `test_mysql_combat_journey.py`,
  `run_corpse_haul_journey.py`, `test_flatfile_full_world_boot.py` and
  `run_saved_item_recovery_journey.py`.
- Left for the Phase 1 tests: a journey that dies, restarts with full-world corpse restoration
  and loots the restored corpse (the minimal-world journeys skip corpse restoration), and the
  "raising, resurrecting and decaying make no database call" test. The second is
  `test_corpses_in_memory.py`; the first is carried into [Phase 3 progress](#phase-3-progress).
- **Correction (made with step 8):** a flat-file boot restores corpse records and per-room records
  (`flatfile_room_item_record`), never the `saved_items` records, so the flat-file saved-item job
  now writes the item's graph into its room's record
  (`flatfile_world_item_prepare_room_item_snapshot()`; a removal only strips it). The step 3
  item deferred here is done too: `flatfile_world_filter_item_ownership()` in
  `flatfile_corpse_ownership.c` replaces the strict `flatfile_world_reconcile_item_ownership()`
  for corpse and room loads. A record's item is taken if the catalog has no record for it or
  names the corpse or room; one naming anyone else is skipped and logged (`load_skipped`), and
  what it held moves to the top level. The strict check would have failed a boot over a stale
  corpse record, or over a room whose custody also holds claimed saved items.
  `flatfile_item_repository_load_uids()` is the unlocked lookup it uses.

### Step 7: logging out never waits (done)

- `persistence_save_character_terminal()` (`actoth.c`) marks every component, captures and
  queues the save with `player_save_pipeline_request()`, clears the player's deferred-save slot,
  and returns true. A save that cannot be queued is alerted (`player_save terminal
  queue_failed`); the character still leaves. The timeout policy (`_with_policy`, 2 s / 5 s) and
  the `terminal-save-retry` crash-save retry are gone.
  `persistence_save_character_terminal_database_acknowledged()` (copyover) queues the same way;
  copyover and shutdown already drain the writer afterwards (`player_save_pipeline_drain()`).
  `persistence_save_all_characters_terminal()` queues a save for everyone and returns true.
- Every caller dropped its refusal branch and extracts at once: quit (`actoth.c`, both paths),
  camp (`affects.c`), rent at an inn and the undead coffin inn, heaven release
  (`specs.room.c`), death (`fight.c`), idle rent (`limits.c`), link loss (`comm.c`, no more
  `link-loss-retry`) and ghost extraction (`actwiz.c`).
- The flat-file build's terminal branch in `writeCharacter()` (`#ifdef __NO_MYSQL__`) queues too,
  except a new player's first save (`CHAR_RFLAG_NO_DB_BASELINE`): that one still waits for the
  write, because the domains it established are read back straight after.
- `player_save_pipeline_terminal()` stays for that baseline case; its terminal fences are
  otherwise unused and go in Phase 3.
- Tests: `test_terminal_save_safety.py` and `test_deferred_save_retry.py` pin the new contract
  (callers queue and extract, no refusal, no retry, copyover queues then drains);
  `test_persistence_severity.py` checks the `queue_failed` alert. The behavioural test "rent, quit
  and camp extract at once while the writer is stalled" is in the Phase 1 tests list.
- Verified: `make -C src`, the flat-file build, `./scripts/format.sh --all --check`, the
  accounting validator (census regenerated), the 97 tests that mention terminal saves, rent,
  copyover or quit, and the journeys `test_flatfile_newbie_regrant_journey.py`,
  `test_flatfile_combat_journey.py`, `test_mysql_combat_journey.py` (disposable MariaDB) and
  `test_account_recovery_journey.py`.

### Step 8: shutdown and copyover always go (done)

- Shutdown (`game_loop()` in `comm.c`) no longer cancels: a pending starter kit, a failed critical
  command or outbox drain, a failed world recovery drain or a failed shopkeeper save is alerted
  (`shutdown_cancelled=0`) and the shutdown goes on. Every player's save is queued, and the
  writer gets 30 s (`player_save_pipeline_drain(30000)`); whatever it could not write is named,
  one alert per owner (`persistence_writer not_written owner=<id>`, from
  `persistence_writer_pending_owners()`). Review round 1 moved the report to the end of
  `run_the_game()`, after the last locker drain, and made the 30 s a hard bound; see
  [Review round 1](#review-round-1-mr-2).
- Copyover drains the writer for up to 30 s; if it cannot, copyover is called off and the game
  keeps running (the existing path, now alerted as `copyover_failed copyover_cancelled=1`).
- Tests: `test_terminal_save_safety.py`, `test_copyover_save_guards.py`,
  `test_save_logging_sweep.py`, `test_locker_ownership_cutover.py`, `test_pwipe_quiescence.py` and
  `test_chaos_preentry_grant.py` pin the new contract. `run_copyover_runtime_journey.py` (flat-file)
  passes both the failed-copyover and the real exec cases. The behavioural test "shutdown with the
  database down exits within the bound" is in the Phase 1 tests list.

### Step 9: the dupe log (done, built in steps 2 and 3)

- `src/persistence/dupe_log.c` writes `logs/log/dupes`, one line per item: `save_left_out` when a
  save leaves out what the economy holds, `load_skipped` when a load skips a stale copy, with the
  uid, vnum, `lost_by=<owner>` and `held_by=<owner>`. Claims taken from another owner go to
  `logs/log/item_claims` on flat-file (`claimed ... from ... to ...`) and to `item_owner_audit`
  on MariaDB.
- Every path writes it: player and pet saves and loads on both backends, lockers
  (`locker_async.c`), the corpse and saved-item jobs, the MariaDB corpse, locker and saved-item
  loads (`sql_persistence_item_owner_matches_identity()`), and the flat-file corpse and room loads
  (`flatfile_world_filter_item_ownership()`). The harnesses check the exact lines.
- Verified (steps 8 and the step 6 correction): `make -C src`, the flat-file build,
  `./scripts/format.sh --all --check`, the validator, the 97 terminal/copyover/shutdown tests,
  the flat-file world-item, corpse, restore, ownership and repository tests, and the journeys
  `run_copyover_runtime_journey.py`, `test_flatfile_combat_journey.py`,
  `test_flatfile_full_world_boot.py`, `test_flatfile_newbie_regrant_journey.py`,
  `test_flatfile_auction_coin_put_journey.py`, `test_pet_restart_journey.py` and
  `run_npc_container_claim_journey.py`.

### Phase 1 tests and journeys (done)

- Covered by the step tests: claims with audit and a MariaDB leg, the auction left out and logged,
  stale rows skipped and logged (steps 2 and 3); deaths (`test_deaths_happen_at_once.py`, which
  also pins that `writeCorpse()` queues the corpse job before any SQL path and that the corpse
  gets the items before it is saved); raise, resurrection and decay take the in-memory paths
  (`test_corpses_in_memory.py`); capture order and replacement (`test_player_save_worker.py`).
- `tests/async/test_mysql_stalled_writer_journey.py`, run by `run_mysql_stalled_writer_journey.sh`
  on a disposable MariaDB: with `player_items` locked (the writer stalls), `quit` (camping in the
  fixture room, which has its own ~11 s delay) still reaches the account menu while the table is
  locked, where the old terminal save timed out and cancelled the camp; after unlock the save
  lands and a relog reads it. With the database container stopped, shutdown exits in about 30 s
  and names the unwritten save. (`save` leaves a command lag; the journey waits it out before
  quitting.)
- Raising a corpse as a necromancer: `run_chaos_raise_transient_journey.py`'s default path now
  checks the in-memory raise (the caster takes the items, the corpse row is deleted through the
  queued delete, the caster's save records the items once; a hostile raise retries a fresh
  fixture). Its option modes pinned the durable raise and its receipts; they refuse to run.
- Found by that journey and fixed with it: the in-memory raise called `create_saved_corpse()`,
  which cloned the corpse and its contents (new uids) into the corpse storage room, where nothing
  ever restored it. With corpses saved through the writer that clone would have been a second,
  persisted set of the items. It is deleted with `check_saved_corpse()` and its event.
- Local server with the `.env` account (2026-09-29, `duris_dev` migrated by the boot, script in
  the session scratchpad): Veridian loads clean (no `missing_payload_rows`, no dupe or claim log
  lines; before Phase 1 he loaded degraded and blocked a graceful stop); drop and get move in
  memory; `quit` and a relog give back the same inventory and equipment; SIGTERM with Veridian
  online ends in a normal termination after 6 s, and after a restart and relog his inventory and
  equipment are unchanged.
- Not run live: dying and looting your own corpse, and giving an item to another player, need a
  second character online, and the `.env` account allows one session at a time. Both run on a
  real server in `test_flatfile_combat_journey.py` / `test_mysql_combat_journey.py` and the corpse
  haul journey (death and loot) and in the item transfer legs (give).
- Staging runs tagged `master`, so the staging journeys and the day of staging checks wait for this
  branch to be merged. They are carried into [Phase 3 progress](#phase-3-progress).

### Done-when review (done)

- Private locker chests: `sql_save_private_chest_items()` (run when a player leaves the locker
  room, from `LockerToPFile()`) wrote on the game thread. Outside a transaction it now queues a
  `locker` job keyed `(chest_id << 32) | locker_id`, so it never replaces its locker's public-chest
  job (keyed by `locker_id`); `locker_chest_snapshot_repository_apply()` deletes the chest's rows,
  claims the graph for `locker(locker_id, chest_id)` and writes `locker_items` with the shared item
  writer. Inside a caller's transaction, or if the writer refuses the job, the old synchronous
  write runs. The corpse, saved-item and chest applies share one transaction wrapper
  (`apply_owner_write()`). `player_save_claim_mysql_harness.cpp` covers the chest.
- Still on the game thread at a death, both economy-adjacent and both only when the corpse holds
  such an item: `remove_owned_artifact_sql()` for an owned artifact entering a player's corpse,
  and the `account_bound_reward_summons` reset when a divinely bound reward container dissolves.
  These belong with Phase 2 (artifacts and rewards move with the economy).
- Found while doing this, fixed in its own commit: `test_locker_receipt_recovery.py`'s MariaDB leg
  did not link (the extra-description codec, its escape stub and the restitution sources).
- Full suite (`make test-all`, 2026-09-29): 688 passed, 4 failed, all fixed after. `extractlink`
  still counted and described a "retained after save failure" case step 7 removed; the counter,
  its help line and its summary text are gone and `test_extractlink_feedback_runtime.py` checks a
  failing save stub still extracts. `test_new_player_bank_hydration.py` picked the first
  `if (establishing_baseline)` block in `files.c`, which step 7 made the wait; it now selects the
  domain read-back block. `test_mysql_stalled_writer_journey.py` skips without its runner's
  environment, like the other MariaDB journeys. `test_information_cache_journey.py` failed only
  because a source edit landed during its build ("inputs changed during compilation") and passes
  alone.
- Found while doing this, fixed in its own commit (`a970f6bec`):
  `run_collector_catalog_schema_mysql.sh` kept its own copy of the runtime metadata query, missing
  the economic baseline sections the verifier gained, so `make test-db` stopped there on master too.
- `make test-db` passes in full on this branch (2026-09-29).

### Phase 1 status (2026-09-29)

- Steps 1 to 9 are done on `fix/7-persistence-phase-1`, with the Phase 1 tests above. Verified by
  `make test-all` (688 of 692 at the time; the 4 failures were fixed in `599f70c5d` and pass),
  `make test-db`, the flat-file build and full-world boot, the journeys listed under each step,
  and the local `.env`-account session.
- Left for Phase 1 sign-off, in this order:
  1. merge the branch (staging runs tagged `master`) and run the staging journeys (die and loot
     your own corpse, raise corpses as a necromancer, give an item to another player, rent, quit
     and relog, shut down with players online);
  2. after a day on staging, check the logs: no custody, terminal-save, death-recovery or
     corpse-raise alerts; `rent` and `quit` gone from `COMMAND OP SLOW`; no 2-second
     `NEVENT SLOW` stalls;
  3. production only with the owner's go-ahead. `duris_dev` and any other database need
     `python3 scripts/migration_runner.py run` for `0033_item_owner_audit` before this binary
     boots (the local boot applies it).

  Staging still runs a build from 2026-09-23, so items 1 and 2 are carried into
  [Phase 3 progress](#phase-3-progress); item 3 stands for every production deployment.
- Known and accepted until Phase 2: creation grants and the economy (shops, auctions, collector,
  currency) still move items through their own transactions; the collector's death intake and
  its scheduled collection read the runtime cache; artifacts entering a player's corpse and
  divinely bound reward containers still make one synchronous call each at death; flat-file
  lockers never load items at all (a missing flat-file feature). Phase 3 deletes the dead durable
  paths (item movement transactions, the corpse lifecycle deferrals, terminal fences,
  `player_save_pipeline_terminal_death()`, the flat-file corpse lifecycle staging code in the
  critical command path). Phase 2 moved the economy; the collector's two cache reads and the
  flat-file lockers are carried into [Phase 3 progress](#phase-3-progress).

### Review round 1 (MR !2)

The review of `2881c9f20` (tag `persistence/phase-1-review-0`) found five defects. Each is fixed
in its own commit on `fix/7-persistence-phase-1`, with a regression test that fails without it.
The fixed head is tagged `persistence/phase-1-review-1`.

| Finding | Fix | Commit |
|---|---|---|
| 1. High: a stale save revived an item the economy had destroyed (sold for destruction), so relog restored it while the player kept the proceeds. | A destroyed record is final for every item type on both backends: the save leaves the item and its contents out and names them in `logs/log/dupes` (`item_claim_leaves_out()`). | `0ee61068b` |
| 2. High: shutdown named what the writer had not written, then ran locker drains that queued more; with a stalled writer those were lost without an alert. | The game loop queues dirty lockers before its timed drain; `player_save_pipeline_finish()` reports once, in `run_the_game()`, after the last locker drain. | `3aca05650`, `a3b7e6934` |
| 3. Medium: a locker snapshot looked up and created locker ids with SQL on the game loop, and a failed job fell back to synchronous `sql_save_locker()`. | The public locker job is a snapshot applied wholly on the writer (`locker_snapshot_repository_apply()` finds or creates the locker and chest); a failed terminal save retries through the writer after 30 s. The one-in-flight cap and the 128-slot table, which made a stalled writer object-lock users or fall back to `writeCharacter()`, are gone. | `35bdc71d3` |
| 4. Medium: every logout ran `sql_log()`'s synchronous `INSERT` on the game loop (9.8 s freeze measured with `log_entries` locked). | `sql_log()` queues a `log` job on the writer, escaped there, with the time it was logged. | `c8fba0087` |
| 5. Medium: after the drain timed out, the writer was joined without a bound, so a query blocked on the database held shutdown. | At the deadline `sql_pool_interrupt_borrowed()` shuts the borrowed connection's socket down; the query returns as a lost connection and the job is named unwritten. | `3aca05650` |

Found while verifying, fixed in their own commits:

- `00ec69f56`: the snapshot capture wrote one row per spellbook marker; the game reads only the
  first, so a second marker's spells were saved but unusable. The capture keeps one marker with
  every spell, as the legacy writers and the old locker SQL did.
- `9ddb74003`: the economy writer census re-anchored after line shifts (no site added or removed).
- `6ae847fe3`: boot flagged locker rooms by room index, not vnum, so since 2026-07-04 100
  unrelated rooms (#107747-#107846) were treated as lockers and the real ones were not; a
  character saved inside a locker came back stranded in an empty room. The proc is left unset at
  boot, because a free locker room is found by not having it.
- `d45e751ea`: queued saves (checkpoints, terminal saves) recorded the locker room a character
  stood in; the capture now records the room outside the locker's door.
- `3e5be7f57`: queued saves never ran the locker's post-save hook, so a locker was saved only when
  its occupant walked out; what was dropped in it was lost on shutdown, idle rent, link loss or a
  crash. Checkpoints and terminal saves now save it, and the locker slot keeps no character
  pointers across pulses.
- `77b0ff0c2`: `persistence_log_submit()` dropped an alert when it raced the log worker's
  dequeue (`try_to_lock`); one of shutdown's unwritten-save alerts was lost that way.
- `924b8b900`: `migrations/tools` had not built since 2026-09-13 (a C++20 header in a C++14
  build); it builds as C++20 and `test_migration_tools_build.py` builds it in the suite.
- `a810bed5a`: a character deletion failed ("could not be confirmed") whenever the zone-story
  catalog had not booted, as in every minimal journey world; it now succeeds when no zone-story
  state was ever stored and still fails closed otherwise.
- Tests left stale by earlier Phase 1 commits: `f16fd3e48` (the terminal-extract contract looked
  for `extractlink_attempt()`'s old signature), `28116f7f8` (the flat-file concurrent-writer check
  assumed a revision fence; it now checks the file is whole), `d22ea9cc7` (the MariaDB combat and
  corpse-haul count-cap journeys read the database before the writer had caught up), and
  `850d21253` (four MariaDB journeys pinned port 3306).

Verification for this round, on the final head:

- `make -C src`, the flat-file build, `make -C src pfile`, the `migrations/tools` builds and
  `./scripts/format.sh --all --check`; `scripts/validate_economy_accounting.py`.
- `make test-all`: 699 passed on the final head (an earlier run caught the two stale tests
  fixed above); `make test-db`: all 24 legs, with the new `run_sql_pool_interrupt_mysql.sh`.
- MariaDB journeys on a disposable server: combat (all three variants), corpse haul and its count
  cap (also flat-file), chaos raise, saved-item recovery and allocator, world writer retry,
  deletion, playtime, information cache and the locker receipt leg; on flat-file,
  `run_generated_npc_journey.py`.
- `run_generated_npc_journey.py` (flat-file) promotes its character to level 62 and failed the
  copyover reload with `component=domain_identity`, on `master` too: the owner decision in !2.
  Resolved as the owner chose (an immortal keeps their own side's bank, as on MariaDB) in
  `6e4934ab0`: the flat-file identity keeps the character's own racewar, the account menu works
  its admission racewar out from that and the level, and an identity written before holds 0 and
  loads with the snapshot's racewar. The journey now passes.
- `run_mysql_stalled_writer_journey.sh`: camp with `player_items` and `log_entries` locked reaches
  the menu while a second connection's slowest reply is 0.25 s (9.8 s before finding 4's fix),
  and the save and log row land after; shutdown with the writer blocked in a query on a locked
  table exits in about 30 s and names the save; shutdown with the database stopped does the same
  on a second server.
- Local server with the `.env` account: a locker save lands through the writer (row, claim and
  public chest); a bread dropped in the locker reaches `locker_items` within one checkpoint with
  the character inside, and one dropped just before a SIGTERM is saved; after the restart the
  character loads outside the locker (before the boot fix it was stranded in room 65202);
  shutdown with the writer stalled and the character in the locker names the player save and the
  locker by name (about 35 s); `quit` writes its `log_entries` row through the writer.

### Review round 2 (MR !2)

The follow-up review of `507c9881b` (tag `persistence/phase-1-review-1`) confirmed the round 1
fixes and found four more defects. Each is fixed in its own commit on `fix/7-persistence-phase-1`,
with a regression test that fails without it. The fixed head is tagged
`persistence/phase-1-review-2`.

| Finding | Fix | Commit |
|---|---|---|
| 1. High: leaving a locker while an in-stay save was being written extracted the locker character when that older save landed, so what went in after it started was never written. | A completion with a newer generation waiting leaves the locker character alone; it goes once the save that holds its contents lands. `test_locker_leave_during_save.py` links `locker_async.c` and plays the sequence. | `8e049c849` |
| 2. Medium: after a lost connection the writer opens a replacement, which the interrupt cannot cut short, so the writer join and then the pool teardown could run past the 30 s bound. | After the interrupt the writer gets one second (`PLAYER_SAVE_WORKER_STOP_GRACE_MSEC`). One still busy is left to finish on its own and its job is named unwritten; an interrupted pool's shutdown no longer waits for that borrower. | `5e5fcc2bb` |
| 3. Medium: a job that failed after shutdown's last pulse was neither reported as `write_failed` nor named as not written. | `player_save_pipeline_finish()` takes the completions again once the writer has stopped. A failed corpse, locker, saved-item or log job names its owner too. | `5fe1a7574` |
| 4. Medium: on flat-file, a level 62 character saved in mortal mode came back exempt from the racewar cooldown, because the admission was worked out from the level alone. | The identity stores whether the account menu admits the character as an immortal (format version 3). A record written before is read as before until the account's next save. | `7d129958c` |

Found while verifying, fixed in their own commits:

- `4e1b1bd20` re-anchors the economy writer census, which `3e5be7f57` (round 1) had left behind in
  `actoth.c` and `files.c`.
- `4f1096267`: four journeys (saved-item allocator and recovery, copyover runtime, divine refusal)
  left their server running when it did not stop within the wait after SIGTERM. Two left by the
  allocator journey on `master` had spun at full CPU for eight hours after their disposable
  database was dropped. The cleanup now kills the server.

Verification for this round, on the final head:

- `make -C src`, the flat-file build and `./scripts/format.sh --all --check`;
  `scripts/validate_economy_accounting.py`.
- Each new regression test fails without its fix (run against the previous code):
  `test_locker_leave_during_save.py` extracts the locker character when the older save lands,
  `test_player_save_worker.py` hangs in the join, `run_sql_pool_interrupt_mysql.sh` waits for
  the borrower, `test_player_save_pipeline.py` raises no alert, and
  `test_flatfile_account_membership.py` reloads the character as an immortal.
- `make test-all`: 700 of 700. `make test-db`: all 24 legs.
- Journeys: on a disposable MariaDB, `run_mysql_stalled_writer_journey.sh` (camp reaches the
  menu with the tables locked, slowest loop reply 0.25 s; shutdown exits in 30.5 s with the writer
  blocked in a query and in 30.3 s with the database down, naming the save), and the saved-item
  allocator and recovery journeys with their new cleanup; on flat-file,
  `run_generated_npc_journey.py` (the level 62 character through a copyover reload),
  `run_copyover_runtime_journey.py` and `run_divine_refusal_journey.py`.

### Review and branches

- Phase 1 was reviewed as [!2](https://gitlab.com/max757/duris/-/merge_requests/2) (source
  `fix/7-persistence-phase-1`), Phase 2 as [!3](https://gitlab.com/max757/duris/-/merge_requests/3)
  (source `fix/7-persistence-phase-2`, stacked on !2 so its diff was Phase 2 alone). Each review
  round is tagged on the head it read and the head with its fixes: `persistence/phase-1-review-0`
  to `-2`, `persistence/phase-2-review-0` and `-1`. `git diff` between two tags shows one round.
- Both landed together on 2026-09-30 in `7887bf1d6`, one `--no-ff` merge of the phase 2 head,
  which held phase 1 and had `master` merged in. No rebase, so every review tag still names the
  commit that was reviewed. The two branches are deleted.
- The rest of Phase 2 step 8 was reviewed as [!4](https://gitlab.com/max757/duris/-/merge_requests/4)
  (source `fix/7-persistence-phase-2-step-8`, branched from that merge), tagged
  `persistence/phase-2-step-8-review-0` and `-1`. It landed on 2026-09-30 in `60f56fb5b`, one
  `--no-ff` merge of the `-1` head, with no rebase. The branch is deleted.
- Phase 3 continues on `fix/7-persistence-phase-3`, branched from `60f56fb5b`. Its MR targets
  `master` and is opened once it holds work; its review rounds are tagged
  `persistence/phase-3-review-<n>`.

## Phase 2 progress

This section is the hand-over log for Phase 2, in the same form as Phase 1's.

### Step 1: critical commands on the one writer (done)

- `critical_command_coordinator_submit()` reserves the operation, fences its keys and queues it
  on the one writer as a `critical` job (`persistence_job_kind::critical`), so a command lands in
  capture order with the saves around it. The job carries its own copy of the command and of the
  apply function: a command queued before shutdown still lands, and its completion is dropped
  (a generation counter tells a stale job from a new coordinator's).
- The writer retries a lost connection, a lock wait and an ambiguous commit at the head of its
  queue, as it retries a save; the coordinator counts them in its `retries` and `ambiguous`
  health. Any other outcome goes to the existing completion channel, so the pulse, the fences,
  the recent-completion cache, the publication hold and every domain's completion handler are
  unchanged.
- Removed from the coordinator: the admission worker and its journal appends, the two execution
  workers, the per-key execution slots (`keys_available()`), uncertain-admission recovery and the
  coordinator's own retry cap. `critical_command_coordinator_init()` lost its worker count. A
  command held for publication keeps its fences until acknowledged, but no longer holds back a
  later command on the same key (see [What was cut](#what-was-cut-and-why)).
- The journal: `CRITICAL_COMMAND_JOURNAL_DIR` is read only for a journal an older server left.
  Every record is validated first (one this server cannot execute stops the boot with nothing
  applied and the journal untouched), then its commands go to the writer in journal order and
  each is checkpointed once it lands. The directory stays required outside mini mode: locker
  identification keeps its receipts there.
- Shutdown names unwritten commands by count (`persistence_writer/critical ... commands=N`).
- Tests: `test_critical_command_coordinator.py` links the real writer: saves and commands land in
  capture order, fences, attach and conflict, a writer retry of an ambiguous commit, the
  publication hold, a job queued before a coordinator shutdown, an older journal's one-time
  replay, the bounds, and a never-resolved command named at writer shutdown.
  `test_critical_command_admission.py` now pins that a submit to a stalled writer returns in
  microseconds with no file I/O on the game thread. `test_critical_completion_capacity.py` keeps
  the once-only delivery through a full pulse buffer. The economic accounting admission and
  replay, baseline, native flat-file admission and publication retention harnesses start the
  writer and replay an older journal where they used to restart a journaled one;
  `test_critical_command_journal_uncertain.py` tested only the uncertain append and is deleted
  (its adapter check moved into the admission test). The native death restitution crash harness
  journals the command the way an older server did before its crash.
- Found while doing this, fixed in its own commit (`9c627799c`): the restitution repository
  unit's stub no longer matched `critical_command_repository_finish_inbox()`, so
  `build_player_death_restitution_native.sh` stopped at the link.
- Docs: `docs/persistence/CRITICAL_COMMAND_PIPELINE.md` describes execution on the writer and the
  one-time journal replay; `docs/operations/CONFIGURATION.md` the journal directory.
- Verified: `make -C src`, the flat-file build, `./scripts/format.sh --all --check`, the tests
  above and every other test that links the coordinator, `build_player_death_restitution_native.sh`,
  and the journeys `test_area_coin_pickup.py`, `test_flatfile_combat_journey.py` and
  `run_corpse_haul_journey.py` (disposable MariaDB), whose coin, death and haul commands now run
  on the writer.

### Step 2: money in memory (done)

- The save writes the wallet. MariaDB `apply_status()` no longer skips copper to platinum;
  `flatfile_player_snapshot_apply()` writes the wallet into the player's domain record in the
  save's authority transaction whenever the snapshot carries all four fields (a partial status
  save carries none and leaves it).
- `currency_transaction_submit()` and its variants apply at once: the wallet, its revision, and
  the bank view of every online character of the account and side
  (`publish_account_bank_balances_revision()`), then the completion runs before the submit
  returns. A change that would take a balance below zero (or above `INT_MAX`) is refused with
  `ENOSPC` and changes nothing. The pending table, publication states, `player_ready()`, the
  completion handler and `currency_publication.h` are gone; so are
  `currency_transaction_can_submit_nonrebasable()`, `_player_busy()`, `_coin_item_busy()`,
  `_coin_wallet()` and `_submit_coin()`. Input no longer waits behind money, and an item move is
  no longer refused while a coin is pending.
- A bank change is a `bank` job on the one writer (`persistence_job_kind::bank`, its own owner
  per delta): MariaDB `bank_delta_repository_apply()` upserts the delta into `account_banks`
  (`bank_revision` + 1; the unsigned columns make a debit the row cannot cover fail), flat-file
  `flatfile_bank_delta_apply()` adds it to the bank domain
  (`flatfile_player_domain_prepare_bank_delta()` refuses such a debit). A debit is queued before
  the player's save, a credit after it. Shutdown names unwritten deltas
  (`persistence_writer/bank ... deltas=N`).
- Coins: get, drop, give and put take the in-memory branches NPCs took, for everyone
  (`take_coins()` in `actobj.c`; the durable coin commands, their contexts and completions are
  gone), and so does `money_to_inventory()`. Money that leaves one saved owner for another
  queues the one it leaves first (`currency_transaction_save_first()`): the giver before a player
  recipient, the player before a storage container or player corpse it put coins into.
- The currency repository and the coin transfer command stay only for an older journal's replay
  (Phase 3 deletes them). `world persistence` prints `currency_transactions state=ready
  submitted= committed= rejected= bank_deltas=`.
- Found while doing this, fixed in its own commit: both backends loaded a legacy coin pile's
  amount from its custody row (`coin_payload`) instead of what the save wrote. With coins in
  memory that value goes stale, so taking part of such a pile and logging in again gave the old
  amount back. A pile now loads like any item; one an older server's coin transaction spent
  stays spent. The MariaDB load lost its coin query (`PLAYER_LOAD_BASE_QUERY_MAX` 24 to 23).
- Tests: `test_currency_in_memory.py` (links the real transaction: at once, refusals, the order
  of saves and bank deltas, the shared bank view), `test_take_coins.py` (was
  `test_coin_get_completion.py`), `test_transaction_input_queue.py` (was
  `test_currency_input_queue.py`: only the collector still holds input), and a rewritten
  `test_coin_command_transaction_contract.py`. The save-claim MariaDB leg and
  `test_flatfile_player_repository.py` check that the save writes the wallet and that bank
  deltas create, add and refuse; the player-load harness and `test_flatfile_item_repository.py`
  load a legacy pile with a stale custody amount. `test_currency_completion_retention.py` and
  `test_coin_custody_lifecycle.py` tested the removed publication and are deleted. The item
  movement input-queue and prompt harnesses fence with the collector where they used a pending
  coin; the coin-pickup, combat and auction coin-put journeys save before reading the wallet
  from disk and expect the in-memory coin messages.
- `docs/persistence/economy_accounting/writers.json` census re-anchored (the three coin writers
  point at `begin_coin_give_credit`, `publish_coin_put` and `take_coins`).
- `test_flatfile_auction_coin_put_journey.py` still fails its listing-fee check: the auction
  repository writes the wallet until step 3.
- Verified: `make -C src`, the flat-file build, `./scripts/format.sh --all --check`, the
  validator, `make test-all` (every other test passed), `run_currency_transaction_schema_mysql.sh`
  and `run_player_save_claim_mysql.sh` (disposable MariaDB), and the journeys
  `test_area_coin_pickup.py` and `test_flatfile_combat_journey.py`.

### Step 3: the economy stops writing balances (done)

- Auction: `auction_transaction` takes a listing's fee or a bid from the wallet in memory at
  submit, queues the player's save, then queues the command; a coordinator refusal gives it
  straight back. The completion gives back what the command did not charge (the escrow plus
  `wallet_value_delta`): everything when refused, the rest of a bid capped at the buy-now
  price or raising the bidder's own bid, and a money claim's money. The four list and bid
  commands check the wallet first and say so. `auction_repository.c` and
  `flatfile_auction_repository.c` no longer read or write the wallet, the bank, their
  revisions, the currency ledger or the baselines; they report `wallet_value_delta`. A
  completion for a player who has left still waits for `auction_transaction_player_ready()`.
  Changed behavior: raising your own bid needs the full new bid on hand while it settles,
  though only the difference is charged.
- Collector: a purchase takes the price of the listing it was prepared from (the in-memory
  catalog, at the payload's listing revision) at submit, saves first, and is refunded when
  refused; a refund for a buyer who has left waits in `refunds` for
  `collector_transaction_player_ready()`. Both repositories hand the policy the price as
  what the buyer carries and no longer write the wallet or the ledger.
- Left as they are, because only an older journal's one-time replay reaches them, at boot and
  before anyone loads: the currency repository, the coin transfer command, the corpse
  lifecycle wallet (dead since Phase 1 step 6) and the accounting bank commands. Phase 3
  deletes them. The combat outcome's blood money moves with step 5, in the same repository
  code as frags and epics; shops are step 6.
- Tests: `test_auction_escrow.py` (new: the production submit and completion with a recorded
  wallet, save and coordinator), the collector transaction harness (the price at submit, the
  refund, a refund held for a buyer who left), the MariaDB and flat-file auction and
  collector repository harnesses (the wallet is left alone; the stale-wallet and
  insufficient-funds refusals the repositories no longer make are gone) and the source
  contracts. `test_flatfile_auction_coin_put_journey.py` passes again.
- Found while doing this, fixed in their own commits: `run_auction_transaction_schema_mysql.sh`
  no longer linked (the restitution command sources were missing); it runs against the
  `.env` development database, not a disposable one, so it is not part of `make test-db`.
  And removing an auction with a winning bid gave the item back to the seller but kept the
  bid: both repositories now stage it as the bidder's money pickup, and both publishers
  tell the bidder.
- Verified: `make -C src`, the flat-file build, `./scripts/format.sh --all --check`, the
  validator, the tests above and every other test that links the auction or collector code,
  `run_collector_repository_schema_mysql.sh` (disposable MariaDB),
  `run_auction_transaction_schema_mysql.sh` (local development database) and the auction
  coin-put journey.

### Step 4: coins drop into corpses (done)

- `make_corpse()` turns every wallet into a pile, players' too (`money_to_inventory()`), and
  the pile goes into the corpse with the items. For a player, the save with the wallet empty
  (`currency_transaction_save_first()`) is queued before the corpse's, so a crash between
  them can lose the coins but never leave them in both the wallet and the corpse. Looting
  them is an ordinary coin get from the corpse, which queues the corpse's save before the
  looter's.
- Tests: `test_deaths_happen_at_once.py` pins the order (the pile, the player's save, the
  items, the corpse save). The flat-file and MariaDB combat journeys check that the death
  saved an empty wallet and loot the coins back from the player's corpse.
- Verified: `make -C src`, the flat-file build, `./scripts/format.sh --all --check`, the
  validator, the death and corpse tests, and both combat journeys (all variants; MariaDB on a
  disposable server).

### Step 5: epic points and frags in memory (done)

- The save writes epics, frags and old frags: MariaDB `apply_status()` no longer skips any
  status field, the legacy `sql_save_player_status()` writes memory's wallet, epics and frags
  instead of keeping the stored ones, and the flat-file save writes them into the domain
  record with the wallet (`flatfile_player_domain_prepare_saved_balances()`).
- `epic_transaction_submit*()` changes the balance at once and calls its completion before
  returning; a purchase beyond the balance is refused with `ENOSPC`, an overflow with
  `ERANGE`. The pending table, `player_ready()`, the completion handler and
  `epic_transaction_publish_balance()` are gone. The command is still queued afterwards, and
  now only records history: MariaDB `execute_epic_state()` continues the `epic_ledger` from
  the player's last row (or the saved balance when there is none), advances only
  `player_data.epic_revision` (the ledger's unique key), and no longer checks funds or
  revisions; flat-file records the operation. Zone trophies, the epic bonus window and the
  completed-zone reads at login still read that ledger.
- Why the command cannot keep writing the balance as well: a grant with a receipt (the CHAOS
  starter epics clear their flag in the completion) needs its save queued before the command,
  and a command that also added the delta after that save would count it twice.
- PvP outcomes: `combat_outcome_transaction_submit()` applies the frags, epics and blood money
  to the online participants when the command is accepted. Both repositories stop writing
  those balances and stop fencing on the participants' revisions (in-memory currency and epic
  changes had made every outcome after step 2 fail with `ESTALE`); MariaDB records the kill,
  continues the frag and epic ledgers from their last rows, updates the leaderboard, and
  writes no currency ledger; flat-file records the operation. A refused outcome now only
  loses its history rows, so its effects and messages still happen.
- Epic stones: a committed touch adds each participant's award in memory, once (a participant
  who left gets it on return); the repository records it in the ledger with the stone claim
  and no longer writes the balance.
- An older journal's in-flight epic, combat or stone command replays as a record only: the
  balance change it would have made is lost, the same class of loss as a crash.
- Found while doing this, fixed in their own commits: `run_epic_transaction_schema_mysql.sh`
  and `run_combat_outcome_schema_mysql.sh` no longer linked (the restitution sources);
  `test_critical_command_coordinator.py` still required the currency publication row step 2
  removed from the pipeline doc; and `test_player_load_items.py` and
  `test_txn_publication_copyover_drain.py` still pinned source the load fix and step 3
  changed. Restore qualification (`qualify_database_restore.py`) and the
  runbook's balance reconciliations assumed the ledgers explain every balance; that commit
  follows this step.
- Tests: `test_epic_in_memory.py` (new: at once, refusals, completion before the ledger row),
  the save-claim MariaDB leg and `test_flatfile_player_repository.py` (the save writes epics
  and frags), the epic and combat outcome MariaDB legs (the ledgers continue across a save
  and leave the balances alone; a second outcome is not fenced), `test_epic_stone_runtime.py`
  (a returning participant's award is added once), `test_flatfile_player_domain_repository.py`
  and `test_flatfile_accounting_bank.py` (record-only epic and combat commands), and the
  source contracts.
- Verified: `make -C src`, the flat-file build, `./scripts/format.sh --all --check`, the
  validator, the tests above, `run_player_save_claim_mysql.sh` (disposable MariaDB),
  `run_epic_transaction_schema_mysql.sh` and `run_combat_outcome_schema_mysql.sh` (local
  development database), and `make test-all`.

### Step 6: shops in memory (done)

- MariaDB shops already trade in memory: the item and the coins move at once and the
  shopkeeper is saved afterwards. What changed is the save. `sql_save_shopkeeper()` used to
  capture and write the stock on the game thread with dozens of queries; it now captures the
  record the flat-file backend writes (`flatfile_shopkeeper_capture()`), strips the produced
  stock, and queues one `shopkeeper` job on the writer, which replaces the keeper's rows,
  affects and stock in one transaction (`shopkeeper_snapshot_repository_apply()`). A sale
  queues the seller's save before the keeper's, so a crash between them loses the item and
  never leaves it with both. Copyover and shutdown queue the dirty shopkeepers before they
  drain the writer.
- Flat-file shops keep the shop trade command, which records the trade in the shop's
  authority. A purchase's price leaves the wallet at submit, with the buyer's save queued
  first, and comes back on a refusal. The repository no longer writes the wallet: since
  step 2 its balance publication was skipped, so a buyer kept both the item and the money. A
  sale takes its item out of the inventory at submit, saves the seller first, and is paid
  when it commits. The completion hands the item to the shopkeeper or destroys it, and a
  refusal gives it back before the callback.
- Changed from the plan: the MariaDB keeper's stock is saved in order, not claimed. It has no
  ownership rows, and a restore gives it fresh uids, so there is nothing to claim.
- The auction listing and the collector's collection, which step 7 needed, moved the same
  way. A listing's items and a collected antiquity leave memory at submit, before the
  owner's save. A committed command extracts them, and a refused one puts them back: in
  the seller's inventory, or where the antiquity was (in the room, if its container is gone).
- Found while doing this, fixed in its own commit: a held item was kept as a raw pointer
  until its completion. A god revoking a reward grant, or a soulbind removing a character's
  other soulbound items, walks the object list and can extract such an item. The completion
  then gave back or extracted freed memory. The completions now look each held item up
  again (`find_live_object()`, made public) and leave one that is gone.
- Tests: the shop trade transaction harness (the price at submit, the item held from submit,
  given back on refusal, left alone once extracted), `test_shop_trade_live_route.py` (the
  order in the submit), `test_shopkeeper_save_runtime.py` (capture and queue), the save-claim
  MariaDB leg (a shopkeeper save replaces its rows), `test_auction_escrow.py` and the
  collector transaction harness (held items, the extracted case), and the source contracts.

### Step 7: the economy exception goes (done)

- `item_claim_owner_is_economy()` is gone. Saves and memory-held transfers now claim any item
  their owner holds, even when its record names an auction, a shopkeeper or the collector.
  Only a destroyed record is still left out (`item_claim_leaves_out(state)`).
- This is safe because nothing the economy is taking stays in memory once its save has been
  captured. Listings, flat-file sales and collections take their items out before the
  command, and a MariaDB sale saves the seller before the keeper.
- Tests: the save-claim harnesses on both backends and the MariaDB transfer harness: an item
  whose record names an auction is claimed and audited. Plus the source contracts.
- Verified: `make -C src`, the flat-file build, `./scripts/format.sh --all --check`, the
  validator, the tests above and every other test that links the shop, auction, collector
  or claim code. The MariaDB legs `run_player_save_claim_mysql.sh`,
  `run_item_transfer_schema_mysql.sh` and `run_collector_repository_schema_mysql.sh` ran on
  disposable servers.

### Step 8: game-thread SQL off the loop (done)

- The way off the loop (`src/sql/sql_async.{h,c}`):
  - `sql_queue()`, `sql_queue_statements()` and `sql_queue_work()` build SQL on the game
    thread and queue it on the one writer as an `sql` job, in capture order with the saves.
    Work that must read before it writes, such as a lookup followed by an update or an
    insert, runs there too, with `sql_select()` and `sql_execute()`.
  - Each job runs in one transaction, so a retry after a lost connection never applies it
    twice. A commit whose outcome is unknown is reported instead of retried.
  - `sql_read()` and `sql_read_work()` queue a read the same way, so it sees every write
    queued before it. The writer copies its rows, and the game thread gets them on a later
    pulse (`sql_async_pulse()`). `sql_read_for()` calls back only while the character is
    still in the game.
- What still waits is named. While the loop runs, every query on the game thread's connection
  is counted (`game_loop_queries` in `world persistence`), and each site is logged once
  (`game loop query site <file>:<line> <function> (<kind>)`).
- `sql.c` is done:
  - Queued on the writer: the core save, the account-character projection (its lookup
    runs on the writer, just before the write it decides), the frag leaderboard, progress
    rows, IP activity, world quest, shop and quest trophies, manual logs, offline message
    enqueues and the level cap updates.
  - Read at boot and kept current by the game's own writes:
    - the level cap row, read again when the maintenance job raises it;
    - `ip_info`;
    - the recent shop sales and quest rewards;
    - `mud_info`, also read every minute so a creation lock set in the database still
      takes hold.
  - Read when a character enters the game: its world quest history. The quest checks fail
    closed until it arrives.
  - Answered on a later pulse: offline messages, the wiki search, the frag trophy, total
    donations, the `mud_info` reload and the `sql` command. Offline delivery claims each
    receipt on the writer before the game shows it.
- Changed from the plan: the plan counted 345 `qry()` calls. The survey found about 330
  functions on the game thread's connection, and about 250 of them remain. So on 2026-09-30
  the step was split: the foundation above and `sql.c` went to `master` with !3 (in
  `7887bf1d6`), and the rest follows in its own MR from `fix/7-persistence-phase-2-step-8`,
  subsystem by subsystem, each its own commit with its test.
- What was left when the rest of step 8 began. A session as the `.env` account (log in, the
  account menu, character entry, then
  `finger`, `trophy`, `fraglist`, `epic`, `boon`, `nexus`, `arti`, `auction`, `poll`, `outpost`,
  `kingdom`, `hardcore`, `leaderboard`, `prestige`, `ledger`, `save` and `quit`) still logged
  33 sites:
  - logging in: `sql_account_exists()`, `sql_load_account()` with its characters and IPs,
    and the account save (`sql_save_account()`, its character mapping lookup and its
    transaction);
  - a whole offline character load (`restoreCharOnly()`: `sql_get_player_pid()`,
    `sql_load_player_status()`, skills and affects) during character entry, still to be traced
    to its caller; finger, lockers, artifacts and the websocket handlers load offline
    characters the same way;
  - at login: `query_grants()` (account rewards), `check_frag_position()` and
    `player_death_restitution_locker_notice()`;
  - periodic events: `event_artifact_check_poof_sql()` and `event_artifact_wars_sql()`;
  - command output: `auction_list()`, `boon_display()`, `nexus_stone_god_list()`,
    `poll_get_all()`, `do_prestige()`, `get_epic_players()`, `displayHardCore()`,
    `displayLeader()` and `load_outpost_records()`.

  The rest of the static inventory (lockers and private chests, ships, guilds and
  associations, kingdoms, the remaining artifact, boon, auction and nexus paths, epic zones
  and `get_zone_info()`, artifact bind data) is converted with its subsystem, whether the
  session reached it or not.
- Order, after the plan's ablation (see [What was cut](#what-was-cut-and-why)):
  1. Account login and saves (every player goes through them): one writer read for the account,
     its repair, IPs and characters; a queued save; same-account sessions copied from memory.
     **Done**, see [Account login and saves](#account-login-and-saves-done).
  2. The name-to-pid index, and offline character loads through the player load pipeline.
     **Done** (the index, the account screens, `finger`, `lore`, `disguise`, `mask`,
     `load char`); the offline loads left belong to lockers, artifacts and deletion.
  3. The login-time reads (**done**: rewards, the frag position, the restitution notice),
     a new character's first save (**done**), then the periodic events and the command
     output, subsystem by subsystem, skipping what nothing calls and what only boot runs.
  4. The journey that pins no query after boot: `test_mysql_game_loop_queries_journey.py`,
     in `make test-db` since the account screens. **Done**: its `NOT_CONVERTED` list is empty.
- How the rest was split (2026-09-30, the user allowed up to five subagents): four agents
  work in their own worktrees under `/home/aiwithapex/projects/duris-issue-7-wt/`, each on a
  branch from `96714d824`: `step8/artifacts` (`artifact.c`, `artifact_guild_state.c`, the
  artifact bind data in `sql.c`, `load_dummy_char()`), `step8/economy` (`auction_houses.c`,
  `boon.c`, `nexus_stones.c`, `ctf.c`, the crafting recipe reads), `step8/guilds`
  (`storage_lockers.c` and the locker and chest functions in `sql_player.c`, ships,
  guilds, guildhalls, alliances, kingdoms, `ship_cargo.c`) and `step8/world` (`epic.c`,
  `outposts.c`, `poll.c`, `hardcore.c` and the hardcore `killed_by` write in `die()`,
  `timers.c`, `epic_bonus.c`, `db.c`, `epic_task_catalog.c`, the zone story state, the zone
  functions in `sql.c`, spellbook mobs, the multiplay whitelist, `whois`, `test`,
  `newchar`). They do not edit this document or the census; the coordinator merges each
  branch into `fix/7-persistence-phase-2-step-8`, regenerates the census, records each
  subsystem here and runs the gates. The coordinator keeps character and account deletion
  (both websocket deletions too), renames and the leftovers in `sql.c` and `sql_player.c`.
  All four branches are merged (their sections are below) and their worktrees and branches
  removed; the coordinator's parts are done too.
- Found on the way (the rest of step 8): copyover restored each preserved session's account
  under the character's name, so unless the two names matched the session lost its account
  and `quit` closed the connection instead of returning to the menu. The restore now uses the
  account name the player load returns (`9a4c3bcfd`); `run_copyover_runtime_journey.py`
  quits after the real exec and expects the account menu.
- Found on the way (the rest of step 8): the MariaDB account read parsed its DATETIME columns
  (`last_good_char`, `last_evil_char`, `last_login`, and the characters' `last_login` and
  `last_save`) with `atol()`, which gives the year. So any account save after a login wrote
  back 1970 for the racewar side timestamps, and the side-switch cooldown did not survive a
  relog (`duris_dev` held `1970-01-01 02:32:50`). The read now selects `UNIX_TIMESTAMP()`;
  the stalled-writer journey logs in to the menu, disconnects, and checks the timestamp
  once that save has landed (the previous binary lost it).
- Found on the way (the `sql.c` part):
  - `sql_find_racewar_for_ip()` assigned `RACEWAR_NONE` to its pointer instead of the side,
    and leaked the result after an hour offline.
  - The frag leaderboard upsert passed an `int` to `%ld` and a `long` to `%d`.
  - The in-memory versions do neither. The dead `get_level_cap()`,
    `sql_check_level_cap_periodic()`, `sql_modify_frags()` and `sql_save_pkill()` are
    deleted.
- Tests: `test_sql_async.py` (new) links the real writer. It checks the order, the later
  pulse, a retried read, work that reads before it writes, and a character who left. The
  save-claim MariaDB leg checks the transaction and the copied rows. The source contracts
  for the converted functions follow them. A local session as the `.env` account confirmed
  that the converted commands answer, and that their sites no longer log as loop queries.

#### Account login and saves (done)

- `account_read()` (`account.c`) replaces `read_account()` and `account_exists()`. On MariaDB
  it queues one `sql_read_work()` job (`sql_load_account()` in `sql_player.c`): the account's
  character projection repair (`sql_repair_account_character_projection()`, now on the
  writer's connection), then the account, its IPs and its characters, in one transaction and
  behind every save queued before it. The rows come back on a later pulse and become a live
  account (`account_from_rows()`). The descriptor records the read (`writer_wait_id`), and
  its input is held while that is set (`session_input_authentication_pending()` in `comm.c`,
  the websocket command gate in `ws_handle_command()`); the result goes to the descriptor with
  that id, so a closed connection just drops it. On flat-file the read happens at once, as
  before. No new connection state was needed.
- Callers continue in the read's callback: the telnet login (`select_accountname()`), the
  websocket login and registration (registration checks the name once, on the writer, just
  before its save, where it used to check before and after hashing), the websocket reset
  request, both reset completions (`account_recovery_complete()` now takes the account the
  caller has just read, and `account_apply_recovered_password()` checks and writes that one),
  the websocket admin delete (its tail is `admin_delete_character_loaded()`, still with the
  offline load and deletion SQL that later steps convert), and copyover restore.
- `write_account()` queues the save on MariaDB (`sql_save_account()` builds the account and
  IP statements on the game thread; each character's mapping lookup runs on the writer) and
  then copies the saved account into the account's other sessions (`copy_account()`), instead
  of reading it back into every one of them. The character deletion no longer reads the
  account back either: it already removes the character from the account in memory.
- Removed with them: `sql_account_exists()`, `sql_load_account_ips()`,
  `sql_save_account_ips()`, `sql_delete_account_ips()`, `sql_find_account_character_mapping()`,
  the flat-file reload repair, and the dead file helpers `write_unique_ip()`,
  `read_unique_ip()`, `write_character_list()` and `read_character_list()`.
- Tests: `test_mysql_stalled_writer_journey.py` locks `accounts` and checks that a login gets
  no password prompt while the loop keeps answering a second connection, and gets it once the
  table is free; on the previous binary the loop stalled for 10 s. The account projection
  harness runs the writer-side repair on a disposable MariaDB. The recovery, projection,
  persistence-path, boot-log, copyover-custody and character-delete tests follow the new
  code.
- Verified: `make -C src`, the flat-file build, `make test-db` (35 of 35), the flat-file
  combat, copyover and account recovery journeys, and a local session as the `.env` account
  (log in, `finger`, `save`, `quit`): no account site logs as a loop query any more.

#### Account screens without character loads (done)

- The "whole offline character load during character entry" was `GetMIA()`: the login log's
  MIA text loaded the entering character again to read its last save time. `GetMIA()` now
  takes that time, which the character already holds (finger passes its target's), and the
  unused `GetMIA2()` is gone.
- The account menu's rested-bonus and delete lists and the websocket character list, account
  information and rested bonus loaded every character on the account (four queries each) to
  show what the account already holds. They read the account's characters now. The account
  carries two more fields for them, `spec` and `played` (read with the account, kept current
  by `sync_account_character_projection()` at each save), and the websocket class text comes
  from `class_string()`, `get_class_string()` split from its character. The websocket
  `lastRoom` shows the last room, as the telnet list does (it indexed `world[]` with the
  hometown vnum). Gone: `load_char_display_data()`, `struct char_display_info`,
  `get_race_name_from_info()`, `ws_load_char_info()`, `struct ws_char_info` and
  `cleanup_temp_char()`. The flat-file account has no `spec` or `played` yet, so there the
  websocket shows no specialization and no playtime; before, it listed no characters at
  all, because the flat-file backend has no pfiles for `restoreCharOnly()` to read.
- `tests/async/test_mysql_game_loop_queries_journey.py` (in `make test-db`) creates an
  account and a character on a disposable MariaDB, plays, saves, quits, opens the rested
  and delete lists, enters again and quits, and fails on any game-loop query site outside
  its `NOT_CONVERTED` list, which the rest of step 8 empties. On the previous binary it
  fails with the character loads (`sql_get_player_pid()`, `sql_load_player_status()`, skills
  and affects).

#### The name-to-pid index (done)

- On MariaDB, `sql_player_exists()`, `sql_get_player_pid()` and the new
  `sql_get_player_name()` answer from memory: every `player_data` row's pid, name and active
  flag, read at boot in `initialize_mysql()` (`sql_player_names_load()`; the boot stops if it
  cannot be read) and kept current where the game changes them: entry
  (`sql_save_player_core()`, which also covers a rename, since the renamed character is
  saved again; it deactivates any other character of that name, as the SQL does) and
  deletion (`delete_character_result()`, once its transaction commits). Flat-file already
  answered these from its identity store and keeps doing so.
- `get_player_pid_from_name()` loaded the whole character to read its pid; it is now
  `sql_get_player_pid()`. `get_player_name_from_pid()` reads the index (an active
  character's name only, as its query did). `get_player_from_name()` had no caller and is
  gone.
- Left for character creation: `sql_try_get_player_pid()` in the first save of a new
  character, which inserts the row and must not insert it twice.
- Tests: `test_player_names_index.py` links the index and checks its rules; the game-loop
  queries journey no longer lists `sql_player_exists`.

#### Offline character loads (done)

- `player_load_offline()` (`src/player/player_load_offline.{h,c}`) loads a character that is
  not in the game through the player load pipeline, by its pid from the name index (so the
  load waits for the character's queued saves, since the MR !4 review) or else by name,
  without its pets and, unless
  asked, its items, and hands it to a callback on a later pulse (`comm.c` gives it every
  load no descriptor claims). `player_load_offline_for()` is the command form: the callback
  runs only while the requester is still in the game, and a load that cannot be queued
  tells them. Both backends load through it, so these commands also work on flat-file now,
  where `restoreCharOnly()` read pfiles the backend no longer writes.
- Converted: `finger`, `lore` (a character; an object in the inventory is still lored at
  once), `disguise`, the illusionist's `mask` (masking back as yourself loads nothing), and
  staff `load char`, which now brings the character in with its items: on MariaDB
  `restoreItemsOnly()` skipped them, so a loaded character held nothing, and its next save
  would have written that.
- The last `restoreCharOnly()` loads went with their subsystems: the locker access check
  (lockers), the artifact owner loads (`load_dummy_char()`, artifacts) and the websocket
  character deletions (character deletion). Then `restoreCharOnly()` lost its SQL branch
  (`435c3db2a`) and stays the pfile reader that `lookup pfile`, `purge pfiles`, the boot pfile
  migration and the `pfile` tool use. The pfile test pins that it reads no database.
- The game-loop queries journey promotes its character to a god between sessions (after
  the camp's log row lands, so the queued quit save cannot undo it) and runs `finger`.

#### Account-bound rewards (done)

- Every login ran the divine reward queries (`query_grants()`, the expiry purge, the login
  summon's choice, the cooldown), and `divineclaim` ran them and its writes in transactions
  on the game loop. Only the game writes these tables (the pwipe policy runs at shutdown),
  so memory holds them now: `account_rewards_load()` reads every grant and summon at boot
  (`initialize_mysql()`), and every change is made in memory at once and queued on the
  writer. New grants take their id from memory (`record_grant()`). A revocation, whether
  expiry, staff removal or a dismissed or duplicate copy, queues one writer job that retires
  the saved copies' custody and rows (`clear_saved_grant()` now returns that work,
  `revoke_grants()` queues it), then removes the live copies at once. The staff account
  lookup (`with_account()`) reads the account's stored name on the writer and continues in
  its callback, since accounts are not in memory.
- The "records are temporarily unavailable" and "status unavailable" branches went with the
  queries they reported on.
- Tests: the game-loop queries journey's god grants the starter mace to the account, lists
  it, enters again so the login summons it, lists and revokes it, and after shutdown finds
  both tables empty; the six reward source contracts follow the memory version.

#### The frag leaderboard (done)

- `frag_leaderboard` is the web-facing projection the game writes on the writer
  (`sql_update_frag_leaderboard()`, the combat outcome), so the game reads it there too,
  behind the writes queued before each read. At entry `check_frag_position()` reads the
  overall top and bottom and sets the Frag Lord flags in the callback. `fraglist` with a
  filter reads the totals by side and the top and lowest fraggers in one job
  (`show_fraglist()`); the rows come tagged `total`, `top` and `low`, and
  `fraglist_leaders()` (`redis_report_cache.c`) reads the last two for both callers.
- The cached default view is rebuilt the same way: `redis_cache_fraglist(ch)` reads on the
  writer, caches the list, and shows it to `ch` on a cache miss. Without the cache (Redis
  off) `fraglist` shows the list it reads. The boot's own rebuild now lands on the first
  pulses.
- The game-loop queries journey runs `fraglist` and `fraglist warrior` (Redis off there).

#### The restitution locker notice (done)

- The login notice that a restitution bag waits in an account locker
  (`player_death_restitution_locker_notice()`) reads the lockers on the writer and prints
  on a later pulse while the character is still in the game. A background read for a
  character stays silent when it fails (`sql_read()` with the character's runtime id), where
  a command's read (`sql_read_for()`) tells the player.
- With it, the game-loop queries journey lists no login-time read any more.

#### A new character's first save (done)

- On MariaDB a new character's first save ran the whole legacy synchronous save on the loop
  (`sql_save_player()`: the name lookup, the status INSERT, skills, affects, items, pets and
  shapechanges, each in the loop's transaction), because it was the only path that could
  insert the `player_data` row, and the row took its pid from AUTO_INCREMENT. The writer's
  save has inserted a missing row since Phase 1 (`ensure_player_row()`), so the first save
  is now queued like any other. The writer also gives a row it creates its opening
  baselines (`insert_opening_baselines()`: wallet, epics and frags, from the row it has just
  written), which the legacy save did.
- The pid comes from memory: `getNewPCidNumb()` takes the name index's highest pid plus one
  (`sql_highest_player_pid()`, seeded at boot past `player_data`'s AUTO_INCREMENT since the
  MR !4 review, so a deleted character's pid is not given out again) and `init_char()`
  records the new name and pid in the index
  at once. The old `Players/pc_idnumb` counter had fallen far behind the rows (22 against
  3306 in `duris_dev`) because the legacy insert ignored it; in a fresh runtime it could not
  be written at all, so the pid was -1 until that insert. Flat-file keeps its identity
  allocator and its synchronous first save (its domains are read back after it).
- The game-loop queries journey checks the new character's row and its three baselines
  after shutdown; its session no longer reaches any query outside the artifact events.

#### Economy: auctions, nexus stones, boons, CTF and recipes (done)

Converted on `step8/economy` by an agent and rebased onto this branch (`7fcb189db` to
`1ddc99a31`).

- Auctions read on the writer: `auction list`, `auction info`, `auction pickup` (its money,
  else its oldest auction's items, in one `sql_read_work_for()`; the claim is submitted in the
  callback) and `auction resort` (its keyword updates queued back). The committed event's row
  is read with `sql_read()` and published on a later pulse; an event whose auction cannot be
  read is logged instead of held. `insert_money_pickup()` is queued, so auction refunds, ship
  insurance and the epic and boon fallbacks carry on at once.
- Nexus stones are in memory: only the game writes `nexus_stones` (the pwipe aside, at
  shutdown), so `load_nexus_stones()` keeps every row (`nexus_rows`) and the bonus check on
  every gain, the expiry tick, the sage, the lists and the random enemy stone answer from it.
  A touch or an expiry changes the row and queues the update; a reset or reload loads from
  memory. The old bonus check returned 0 when its store failed, which zeroed the gain. In
  mini mode `init_nexus_stones()` does not run, so there are no stones there.
- Boons are read on the writer: the maintenance scheduler and the reward commands also write
  these tables. `boon list` and the shop are shown on a later pulse; a stat point is spent on
  the writer (`stats > 0`, one affected row), the stat rises in the callback and a point spent
  at 100 is given back. `create_boon()` (now told the requester) counts, inserts and reads its
  id in one writer job; extend reads and extends in one; remove reads there and queues
  `remove_boon()`. Each is announced from the row it read (`boon_notify_snapshot()` also
  takes `BN_EXTEND` and `BN_REACTIVATE`). `is_boon_valid()`, `count_boons()`,
  `get_boon_data()`, `get_boon_shop_data()` and `extend_boon()` are flat-file only now.
- CTF: `add_ctf_entry()` is queued and `ctf score` reads on the writer.
- Recipes are in memory: only the game writes `player_recipes`, so
  `sql_player_recipes_load()` reads them at boot (the boot stops if it fails) and learning
  or forgetting changes memory and queues the write.
- Left for Phase 3: `auction_houses_activity()` (the maintenance scheduler scans), the
  auction backfill tick, `auction_money_pickup_committed()`, the `*_legacy` auction
  functions, `boon_maintenance()`, `boon_random_maintenance()`, `boon_get_random_zone()`,
  `get_boon_progress_data()`, `create_boon_progress()` and `create_boon_shop_entry()`, all
  reached from nothing or from dead code. `ctf_populate_boons()` runs only at boot.
- Found on the way: `boon list u <name>` is open to every player and put the name into the
  boons query unescaped, so a quote rewrote the SQL (`c0defb8b2`, escaped with `escape_str()`).
- Tests: the game-loop queries journey runs auction list, info and pickup, `nexus`, boon add,
  list, filter, extend, remove and shop, and `ctf score`. `test_ctf_writer_contract.py` is
  new; the auction cutover, copyover drain, boon cutover, flat-file nexus and recipe
  contracts pin the writer reads, memory answers and queued writes. The MariaDB combat journey
  (all three variants) passes. Recipe learning happens through an object proc the minimal
  world cannot reach, so only its contract covers it.

#### Artifacts (done)

Converted on `step8/artifacts` by an agent and applied to this branch (`d3dbaf0aa` to
`f1890fc7a`).

- Every artifact move, a zone reset's owned check, feeding and a death into a corpse read
  and wrote `artifacts` and `artifact_bind` on the game loop, and the expiry, wars and soul
  events paged both tables every few seconds. On MariaDB `artifacts_load()` now reads both
  tables at boot (`initialize_mysql()`; the boot stops if it cannot), and the game reads and
  changes them in memory, queuing each change on the writer as an upsert
  (`artifact_row_store()`, `artifact_bind_store()`, `artifact_binds_reset()`). The bind
  functions moved from `sql.c` to `artifact.c`.
- The corpse lifecycle writes the same rows the game writes when it moves the items. The
  artifact guild feed publishes its committed timers and souls into memory
  (`artifact_feed_published()`). Account deletion releases its characters' rows in memory on
  success (`artifacts_forget_deleted_account_character()`).
- The lists (`artifacts major|unique|ioun`, `artifacts player`) read on the writer and answer
  on a later pulse. The list query joins `player_data` for each owner's side, so it loads no
  character. A list read that an invalidation overtook is shown but not cached.
  `reset syncdb` runs its statements in one writer job and reloads memory from its result.
- Offline owners (expiry, poof, swap, hunt, files) load through `player_load_offline()`;
  `load_dummy_char()` is gone, and `artifact.c` no longer calls `restoreCharOnly()`.
- For character deletion `remove_all_artifacts_sql(pid)` returns its statement, and
  `artifacts_forget_deleted_character(pid)` follows the commit.
- Left: boot-only `setupMortArtiList_sql()`, `addOnGroundArtis_sql()`,
  `addOnMobArtis_sql()` (the latter two also in the loop's recovery fallback, before
  counting starts) and `artifact_guild_state_hydrate()`; `arti_remove_sql()` has no body or
  caller (Phase 3).
- Found on the way: the expiry event extracted an offline owner without removing its items,
  so they fell to its room while its save kept them (`d3dbaf0aa`); `reset fixit` extracted
  each display copy before naming it and then again, a use-after-free and double free
  (`00efb191f`); `swap` on an offline owner read a null container for a worn artifact and an
  uninitialized flag and never showed its messages, and `poof` never showed its own (fixed
  with the offline loads).
- A small window where memory and the tables disagree until that artifact's next write: a
  game change made while a `syncdb` job is in flight. (A game write queued between a guild
  feed's capture and its publish was a second one, closed in the MR !4 review.)
- Found on the way (fixed in `ae6ac52e0`): every epic gain submits one transaction for the
  guild's prestige and the feeding of the worn artifacts. It took each artifact's expected
  timer, soul and revision from a copy of `artifact_domain_state` read at boot, and nothing
  the game did kept that table current (it is empty unless a development baseline script
  filled it: `duris_dev` held 0 rows for 97 artifacts). So a mortal wearing an artifact lost
  the whole transaction, prestige included. Now every artifact row and soul change the game
  queues is repeated in `artifact_domain_state` in the same job (`artifact_domain_mirror()`;
  also at boot and after `syncdb`), the capture reads the timer and soul from the artifact
  memory (`artifact_feed_state()`), and the repository locks the revision it reads instead of
  one the game cannot know (the corpse, restitution and deletion transactions advance it
  too). The guild MariaDB harness (`run_artifact_guild_schema_mysql.sh`, which had stopped
  linking: `8087e080b`) applies a feed after another transaction advanced the revision, and
  the game-loop queries journey checks the dropped artifact's domain row.
- Tests: the game-loop queries journey drops two artifacts, lists them, clears one, resets a
  soul and runs `fixit` and `syncdb`, then checks the rows after shutdown; its
  `NOT_CONVERTED` list is empty from here. `test_artifact_offline_owner_loads.py` is new; the
  event, bind, cache and deletion contracts follow the memory version.

#### World: zones, outposts, polls and the rest (done)

Converted on `step8/world` by an agent and applied to this branch (16 commits, from the
zone reset key fix to `3ce8e7cf9`).

- Kept in memory, read at boot and kept current by the game's own writes (each queued on
  the writer; memory changes once the write is queued):
  - the `zones` rows (`sql_load_zones()`, again after `update_zone_db()`). A no-reset zone's
    reset chance changes there (`sql_set_zone_reset_perc()`). Alignment, last touch and
    rarity change on other connections, so `sql_zones_refresh()` reads them again on the
    writer after a stone touch and after the `epic_zone_balance` and `epic_zone_modifiers`
    jobs. Epic stones, `epic zones`, the boon and CTF lists and `stat zone` read memory.
  - the outposts (both backends now load, change and save a record; `clear_outposts()`
    serves `test clearoutposts`), the polls with their options and votes (a new poll takes
    its ids from memory; a poll closes when it expires, as the maintenance job records),
    the spellbooks and the multiplay whitelist. `polls_load()`, `sql_spellbooks_load()` and
    `whitelist_load()` stop the boot if they fail.
- Read on the writer, printed on a later pulse: `epic`, `epic trophy`, `hardcore`,
  `leaderboard` and `whois`. The epic bonus is read in the background when a character
  enters and at copyover restore.
- Queued: `set_timer()`, the epic bonus selection, the hardcore `killed_by` (now escaped),
  the zone-story state and `newchar`'s account link. Whether zone-story state is stored is
  read once at every boot (`note_stored_state()` in `boot_db()`).
- Found on the way:
  - `no_reset_zone_reset()` keyed zones by the zone index, another zone's row; it now uses
    the zone number, as the stone touch does.
  - The poll columns are INT seconds, but the code wrote `FROM_UNIXTIME()` and read
    `UNIX_TIMESTAMP()`: under strict mode every poll and vote insert failed, and the active
    list was always empty.
  - Nothing hydrated the epic bonus since the player load pipeline replaced
    `sql_load_player()`, so every relog or copyover lost the chosen bonus.
  - `newchar` passed an int pid to `%ld`; the whitelist and `killed_by` were unescaped.
  - `newchar` reset the pid `init_char()` had allocated to 0, which sent its first save down
    the legacy path that no longer inserts, so it always failed on MariaDB; it keeps the pid
    now, its save is queued, and its account menu entry carries the level, race and class
    the menu shows (`7c8fc92e7`). The journey runs it in its last session.
- Dead, for Phase 3: `epic_zone_balance()`, `update_epic_zone_alignment()`,
  `update_epic_zone_mods()`, `update_epic_zone_frequency()`,
  `get_epic_zone_frequency_mod()`, `update_zone_epic_level()`, `get_guild_resources()`,
  `outpost_update_resources()`, `poll_check_expirations()`, `event_write_statistic()`
  (its body is under `#if 0`) and `sql_delete_spellbook_mobs()`.
- Tests: the game-loop queries journey runs `epic zones`, `stat zone`, `epic`,
  `epic trophy`, `epic bonus`, a poll created, voted, listed and closed, `hardcore`,
  `leaderboard`, the whitelist and `whois`, and checks the poll, option, vote and whitelist
  rows after shutdown, plus an epic bonus that survives re-entry. New source contracts:
  `test_zones_in_memory.py`, `test_no_reset_zone_key.py`, `test_epic_command_reads.py`,
  `test_outposts_in_memory.py`, `test_poll_int_times.py`, `test_polls_in_memory.py`,
  `test_hardcore_boards_off_loop.py`, `test_timers_queued.py`,
  `test_zone_story_state_queued.py`, `test_spellbooks_in_memory.py`,
  `test_whitelist_in_memory.py`, `test_whois_reads.py` and
  `test_newchar_account_link_queued.py`.

#### Guilds, guildhalls, alliances, kingdoms and ships (done)

Converted on `step8/guilds` by an agent and applied to this branch (`5c321bf41` to
`197280c92`, with the lockers below).

- Guildhall saves and deletes are queued. New hall and room ids come from memory:
  `load_guildhalls()` reads the highest at boot. `Guildhall::reload()` rebuilds its rooms
  from memory on both backends; `load_guildhall()` is gone.
- `save_alliances()` and `write_cargo()` are one writer job each. The staff `cargo reload`
  reads on the writer.
- `sql_save_guild()` queues `sql_save_guild_statements()`; inside a caller's transaction
  (character deletion, until it moves to the writer) it still joins it.
- A kingdom realm's row and roster are one writer step (`realm_work()`); a missing
  `kingdom_garrison` still only skips the roster. `kingdom_persist_payment()` queues the
  guild's statements and the realm as one job (`kingdom_db_save_payment_pair()`).
  `kingdom_db_save_roster()` had no other caller and is gone.
- `found_asc()` and the ledger lines are queued. `Guild::ledger()` reads on the writer.
  `do_prestige()` sorts the guilds in memory on both backends.
- A new ship takes its id from memory (the highest is read at boot), and each save is one
  job of upserts by id, so `db_id_unconfirmed` and `sql_ship_row_exists()` are gone. The
  boot keeps the rows of ships it could not place and places them later from memory
  (`sql_place_ship()`, `sql_ship_stored()`, `sql_ship_from_rows()`). `shutdown_ships()`
  queues like every other save. `sql_delete_ship()` queues its delete (its statement is
  `sql_delete_ship_statement()`).
- Found on the way: the MariaDB prestige list read `associations.prestige`, which nothing
  writes.
- Left: boot-only `sql_load_all_guilds()`, `sql_load_guild()`, `load_guildhalls()`,
  `load_guildhall_rooms()`, `load_alliances()`, `kingdom_db_load_all()`,
  `kingdom_db_load_rosters()`, `read_cargo()` (boot), `sql_load_all_ships()`,
  `sql_read_ship_rows()` and `sql_update_assoc_table()`; dead (Phase 3)
  `sql_delete_guild()` and `sql_delete_locker_by_name()`.
- Tests: the game-loop queries journey founds a guild, lists prestige and reads the ledger,
  then checks the rows after shutdown; `test_guildhall_writer_saves.py` and
  `test_ship_save_ids_in_memory.py` are new (the latter replaces
  `test_ship_save_failure_keeps_db_id.py` and `test_ship_nested_transaction.py`);
  `docs/reference/SHIPS.md` follows.

#### Lockers (done)

- Entering a locker is one writer read. It also creates a missing account or guild locker
  and its public chest, and answers the grant check; the items are built from its rows by
  `sql_locker_items_from_rows()`. A locker with a read in flight counts as in use, so no
  second copy is loaded and its rows never predate a save.
- The grant commands (`list`, `add`, `remove`, `transfer`) are writer jobs. A grant reads the
  named character's side by pid instead of calling `restoreCharOnly()`.
- Private chests and their password hashes live in memory while the locker is open; every
  change is queued, and a new chest's row is made on the writer (the chest now shows at
  once). The activity log is read on the writer and its lines are queued.
- Gone: `sql_load_locker*()`, `sql_locker_exists*()`, `sql_locker_owner_can_access()`, the
  private-chest SQL helpers and the `locker_access_*` query helpers. The item ownership
  check is split into `sql_persistence_item_owner_fields_match()` and shared column macros.
- Found on the way: top-level private-chest items loaded without bitvectors and material
  (fixed by the shared row builder), and minimal-world MariaDB runs never started the async
  locker writer, so their lockers saved on the game loop (`comm.c`, covered by
  `test_minimal_boot.py`).
- The journey no longer boots with `-s`, so the locker counter's proc runs.
- Tests: the game-loop queries journey adds locker rooms and a counter and does a full
  round trip (enter, chest, items, leave, re-enter), checking the rows after shutdown.

#### Account deletion (done)

- On MariaDB `verify_delete_account()` drained every persistence queue on the game loop and
  then ran `sql_delete_account()` there: the fence lock, the item custody destruction, each
  character's rows and the credential, in one transaction on the game thread's connection.
  It is one writer job now (`sql_read_work()`, with `sql_select()` and `sql_execute()` on
  the writer's connection): still one transaction, still refusing an account that is not
  fenced for deletion or has an unsettled auction. It runs behind the account's queued
  saves, the fence among them, so the drain is gone. The account's characters leave the
  game first (`remove_deleted_account_characters()`), so no save of theirs can follow it;
  memory lets go of them only on success (`forget_deleted_account_characters()`, since the
  MR !4 review).
- The session waits for the reply with its input held, as the account read does:
  `wait_for_writer()` and `writer_replied()` in `account.c`; the descriptor field is now
  `writer_wait_id` (was `account_read_id`). `finish_account_deletion()` tells the session
  either way. On success the characters' names leave the index, their artifacts are released
  in memory, the account's grants leave the reward memory (`account_rewards_forget_account()`),
  its poll votes leave the poll memory (`polls_forget_account()`) and its recovery state
  goes. A refusal rolls back and keeps all of that and the fence, and the session can retry.
- Flat-file keeps its synchronous deletion with the drain. The flat-file
  `sql_delete_account()` stub had no caller and is gone.
- Found on the way: account deletion never told the name index, so a deleted account's
  character names stayed taken until the next boot.
- Tests: `run_mysql_deletion_journey.py` (in `make test-db`) now also deletes an account
  with a character. A trigger refuses the first try (the fence and the rows stay), the
  retry deletes it, a new account takes the same account and character names, and no
  account site logs as a game-loop query. The deletion contracts pin the writer job, the
  order and the forgets on success.

#### Corpse and saved-item fallbacks (done)

- A corpse or saved-item job the writer would not take fell back to the legacy synchronous
  SQL on the game thread's connection, out of order with the jobs already queued. For a
  corpse removal it could only fail or do nothing: the queue refuses a corpse without an
  owner pid, and `sql_delete_corpse()` refused the same row for the same reason. Both
  backends now report a refused job (`queue_failed`), as flat-file already did, and
  `sql_save_corpse()`, `sql_delete_corpse()`, `sql_save_saved_item()` and
  `sql_delete_saved_item()` are deleted with their helpers (`8fdd54c6f`). MariaDB's
  `PurgeCorpseFile()` still ignores `skip_corpse_save`, as before.
- Left for Phase 3 in `sql_player.c`: `sql_load_account_bank()` (only the non-account menu,
  compiled out by `USE_ACCOUNT`, reaches it) and the account bank deposit and withdraw
  functions, which nothing calls since the bank moved to critical commands.

#### Terminal saves and the synchronous save paths (done)

- On MariaDB `writeCharacter()` queued only non-terminal saves; a terminal type (the offline
  artifact poof and swap save their loaded owner that way) ran the legacy synchronous player
  save on the game loop. It is queued like any other now, as
  `persistence_save_character_terminal()` does, and the caller disposes of the character.
- The locker code saved synchronously whenever the async locker writer refused a job: a
  first-time personal locker, a refused save and the deferred leave event went through
  `writeCharacter()` to `sql_save_locker()`, and a private chest fell back to its own
  transaction. A refused save is now the failure the callers already report, the deferred
  leave event asks the async writer again every second (the locker character keeps its items
  meanwhile), and a new locker is stored once it holds something or its user leaves.
- Gone with them: the synchronous tail of `writeCharacter()`, `sql_save_locker()`, the locker
  item writers, the chest id lookups, `sql_update_money/playtime/epics()`,
  `writeShapechangeData()`, the flat pfile fallback and
  `persistence_should_extract_terminal_inventory()` (`35bc25443`).
- Tests: the save pipeline, terminal-save, locker and item contracts pin the queued paths; the
  game-loop queries (locker round trip), MariaDB combat and deletion journeys pass.

#### Character deletion (done)

- Every character deletion (the account menu, both websocket deletions, hardcore death,
  `terminate`, a forger's delete, `newchar`'s cleanup) ran one transaction on the game
  thread's connection. `delete_character()` (`files.c`) now builds its statements on the game
  thread, from the builders the artifact, locker, guild and ship conversions left
  (`remove_all_artifacts_sql()`, `remove_all_locker_access_statement()`,
  `Guild::statements_without_member()`, `sql_delete_locker_statement()`,
  `sql_delete_ship_statement()`), and runs them as one writer job, so one transaction behind
  every save queued before it (`a67ceb11a`).
- What memory must forget is captured when the deletion starts and let go only once it
  commits (`forget_deleted_character()`): a refused deletion leaves the character playable,
  and a character extracted meanwhile is still forgotten. The account menu waits for the
  reply with its input held (`wait_for_writer()` / `writer_replied()`, now shared in
  `account.h`); the websocket deletions load the character through the player load pipeline
  and delete it the same way. A deleted character's name leaves every live session's account
  list (names are unique), and its artifacts are released in `artifact_domain_state` too.
- Gone: `delete_character_result()`, `deleteCharacter()`, `sql_soft_delete_character()`,
  `sql_delete_player()`, `sql_delete_player_by_name()`, `sql_delete_locker()`,
  `remove_all_locker_access()`, `Guild::save_without_member()`, the transaction-joining
  branches of `sql_save_guild()` and `sql_delete_ship()`, the pfile tool's stubs for them and
  `test_soft_delete_statement_runtime.py`. `docs/persistence/CHARACTER_DELETION.md` describes
  the new flow.
- Tests: `test_account_character_delete_runtime.py` holds the queued job, refuses it at every
  statement, retries, and closes a session before the reply, on both backends. The MariaDB
  deletion journey's refusals, retry and restart pass, and it now fails on any game-loop query
  site.

#### Renames (done)

- A rename ran one transaction on the game thread's connection and, when its COMMIT failed,
  read the player row back. It is one writer job now (`sql_rename_character_statements()`):
  the player row, what the name keys and the ship, whose statements are built under its new
  owner while memory keeps the old one (`9ea831ded`).
- Memory follows only once the job is stored, on a later pulse: the ship's owner, the guild
  roster, the name index, the character if still in the game, and every live session's
  account list. A failed job changes nothing. That matters: a name the account mapping still
  holds would otherwise split the login mapping from the character, as the rename lockout of
  2026-09-27 did. The requester is told either way, and the paid rename charges only a stored
  rename. The ship is left for its own next save instead of being marked saved, since the
  reply comes after the job.
- Gone: `sql_player_rename()`, `sql_player_row_named()`, `sql_commit_outcome` and the
  transaction-joining branch of `sql_save_ship()`.
- Tests: `test_character_rename_ship_ownership.py` holds the job until a pulse, fails each
  statement, refuses the job, and lets the target or the requester leave before the reply; the
  references harness runs the statements on MariaDB; the game-loop queries journey renames its
  god and checks the stored rows.

#### What is left after step 8

A scan of every remaining query on the game thread's connection (`qry()`, `db_query()`,
`sql_run_query()`, `sql_trace_exec()`, `sql_run_multi_query()`, the transaction calls and
`mysql_query(DB, ...)`) finds only:

- **Boot only:** the loaders (`sql_player_names_load()`, `account_rewards_load()`,
  `sql_player_recipes_load()`, `artifacts_load()` and the artifact lists, `polls_load()`,
  `sql_spellbooks_load()`, `whitelist_load()`, `sql_load_zones()` and `update_zone_db()`,
  `load_nexus_stones()`, `load_outpost_records()`, guilds, guildhalls, alliances, kingdoms,
  cargo, ships, corpses, saved items and shopkeepers, `get_timer()`, the epic task catalog, the
  zone-story state, `artifact_guild_state_hydrate()`, `ctf_populate_boons()`), the boot checks
  in `sql.c`, the item owner reconciliation of world recovery (before counting starts) and the
  boot pfile migration (`sql_migrate_all_players()`, with the legacy `sql_save_player()` and
  `sql_load_player()` it uses).
- **Shutdown only:** `sql_pwipe()` and `account_bound_rewards_on_successful_pwipe()`.
- **Dead, for Phase 3** (nothing reaches them, or only other dead code): the `*_legacy`
  auction functions, `auction_money_pickup_committed()`, `auction_houses_activity()`,
  `check_boon_completion_legacy()`, `boon_maintenance()`, `boon_random_maintenance()`,
  `get_boon_progress_data()`, `create_boon_progress()`, `create_boon_shop_entry()`,
  `epic_zone_balance()`, `update_epic_zone_alignment()`, `update_epic_zone_mods()`,
  `update_epic_zone_frequency()`, `get_epic_zone_frequency_mod()`, `update_zone_epic_level()`,
  `get_guild_resources()`, `outpost_update_resources()`, `poll_check_expirations()`,
  `sql_delete_guild()`, `sql_delete_locker_by_name()`, `sql_delete_spellbook_mobs()`,
  `arti_remove_sql()`, `restoreItemsOnly()` (only the non-snapshot entry reaches it, which
  accounts never use) with `readShapechangeData()`, `sql_load_account_bank()` (only the
  non-account menu, compiled out) and the account bank deposit and withdraw functions,
  `sql_delete_shopkeeper()` and `sql_restore_shopkeeper()` (their wrappers have no caller),
  `update_nexus_stat_mods()` (returns before its query) and `event_write_statistic()` (its
  body is under `#if 0`).
- The game-loop queries journey (a god in the minimal world, 150-odd commands across three
  sessions, including character creation, `newchar`, a rename, lockers, guilds, artifacts,
  polls, the economy and the account screens) and the MariaDB deletion journey (character
  and account deletion with refusals) run with no game-loop query site at all.

### Review round 1 (MR !3)

The review of `c3ffc4b8a` (tag `persistence/phase-2-review-0`) found five defects. Each is fixed
in its own commit on `fix/7-persistence-phase-2`, with a regression test that fails without it.
The fixed head is tagged `persistence/phase-2-review-1`.

| Finding | Fix | Commit |
|---|---|---|
| 1. P1: a newer save of an owner removed its queued save and went to the back, past a job that relied on it. A deposit's [wallet debit, bank credit] became [bank credit, newer wallet save], so a crash between them kept the old wallet and the credited bank. | A newer save replaces the queued one only when that one is the last job queued; otherwise it is queued behind, so saves apply in capture order exactly. `test_player_save_worker.py` and `test_player_save_pipeline.py` queue a save behind another owner's job. | `d887fc6d3` |
| 2. P1: a retried bank delta could be added twice: flat-file recovered a journaled commit and then added the delta again; MariaDB retried a relative autocommit update after a lost acknowledgement. | Flat-file prepares the bank record once and writes that same record on a retry. MariaDB writes the delta in a transaction: a connection lost before the commit leaves nothing written, and a commit whose outcome is unknown is reported instead of retried. | `f4d512451` |
| 3. P1: a player's `get coins` emptied the pile and then added it up in an `int`; a pile worth more than `INT_MAX` copper overflowed and the coins were lost. | `credit_coins()` adds the 64-bit total to the purse first and says whether it took them; the pile gives up its coins only then, on both pickup paths. `test_take_coins.py` keeps a pile the purse cannot hold. | `363b75a97` |
| 4. P2: the writer refuses owner 0, so every save of shop 0 was refused and its stock restored stale after a restart. | The shopkeeper job is keyed by the shop number plus one. The shopkeeper save test's writer stub now refuses owner 0 like the writer. | `bdd152f35` |
| 5. P2: the quest history and trophy caches counted local days while every connection counts UTC days, so a UTC+3 server reset the daily world quest allowance three hours early. | The caches count UTC days. | `44a678df4` |

`a5492e45c` re-anchors the economy writer census after these fixes.

Verification for this round, on the final head:

- `make -C src`, the flat-file build and `./scripts/format.sh --all --check`;
  `scripts/validate_economy_accounting.py`.
- Each new regression test fails on `persistence/phase-2-review-0` (a throwaway worktree with the
  new tests): the worker and pipeline tests see the newer save replace the queued one, the
  flat-file repository test adds a retried delta twice, `test_take_coins.py` and the save-claim,
  shopkeeper and world quest contracts fail on the old code.
- The save-claim MariaDB leg (disposable server) and the coin journeys
  (`test_area_coin_pickup.py`, `test_flatfile_auction_coin_put_journey.py`).
- `make test-all`: 702 of 702 (653 s). `make test-db`: 35 of 35 (191 s).

### Review round 1 (MR !4)

The review of `4611514ce` (tag `persistence/phase-2-step-8-review-0`) found seven defects. Each
is fixed in its own commit on `fix/7-persistence-phase-2-step-8`, with a regression test that
fails without it. The fixed head is tagged `persistence/phase-2-step-8-review-1`.

| Finding | Fix | Commit |
|---|---|---|
| 1. High: the pid allocator started past the highest pid among the `player_data` rows left, so after a restart a new character could take a deleted character's pid and inherit its pid-keyed rows (opening baselines, currency ledger, item ownership). Reward grant ids had the same flaw. | Both allocators also start past their table's AUTO_INCREMENT (`sql_next_auto_increment()`), which InnoDB keeps past deleted rows. The MariaDB deletion journey creates a character after deleting one and restarting. | `7d895f6e0` |
| 2. High: none of the three character deletions (account menu, web client, web admin) checked that the character had left the game, so a linkdead character could be deleted and play on unsaved, its artifacts released and its name free. | Each refuses a character in the game (linkdead too) or being loaded to enter it, before anything is queued. The deletion runtime harness and the MariaDB deletion journey (a linkdead character) check it. | `c23ab95a5` |
| 3. Medium: offline loads named the character only by name, so the load worker never held them behind its queued saves, and the artifact expiry, `arti swap`, `arti poof` and `arti` files give saved a copy older than the terminal save. | An offline load carries the pid from the name index, so it waits like a login; a pid load from a session still names its account, an offline one none. The callbacks that save the copy back also give up while another load of the character is pending. | `6c9d610c4` |
| 4. Medium: a refused account deletion had already forgotten its characters' guild memberships, ships, revision and item ownership state, so the next guild save dropped them. | `remove_deleted_account_characters()` takes them out of the game before the job; `forget_deleted_account_characters()` runs only once it committed. | `1e12e2108` |
| 5. Medium-low: a guild save queued while a deletion or rename ran rewrote `guild_members` from memory that still held the old member, and landed after the job. | The guild is saved again once memory lets go of the member or renames it, so that save lands last. | `8322d0453` |
| 6. Medium-low: an artifact move queued during a guild feed stored the old timer behind the feed, so later feeds were refused as stale until another store. | The publication takes the fed timer only if memory still holds the one the feed captured, and queues the row again either way; it no longer writes the captured soul back over memory. | `7d836cd45` |
| 7. Low: two creations that passed the name prompt, or a creation during a queued rename to that name, stored two characters with one name, and the later one took over the other's account mapping. | The end of creation checks the name again; a rename holds its new name in the index from the moment it is queued and releases it if refused. With both, the mapping write's fallback only ever meets a deleted character's tombstone, so the suggested defensive change to it was left out. | `25194f948` |

Found while fixing finding 3, fixed in their own commits:

- `94c408502`: the artifact expiry event loaded an owner holding two expired artifacts twice.
  When both copies were read before either saved, the later save put back the artifact the
  earlier one had poofed, after its row was cleared. The event starts no load for an owner
  that has one pending, which replaces its per-artifact set of loads in flight.
- `4fec76b30`: when the expiry event could not load an owner, it cleared the artifact's row
  while the artifact stayed on the character, so a zone reset could load a second copy. The
  row now stays for the next pass. Offline loads that wait for queued saves made this more
  likely under a writer running behind.

`868408da4` re-anchors the economy writer census after these fixes.

Verification for this round, on the final head:

- `make -C src`, the flat-file build and `make -C src pfile`; `./scripts/format.sh --all
  --check`; `scripts/validate_economy_accounting.py`.
- Each new regression test fails on the code before its fix: the deletion journey gave the
  new character the deleted one's pid (both 1); the deletion runtime harness deleted a
  character in the game; the flat-file repository harness refused a load by pid alone; the
  feed publication harness, the name index test (a creation whose name was taken) and the
  rename harness (the held name), and the web deletion, account deletion, load pipeline and
  artifact offline-owner contracts fail on the previous code.
- `make test-all`: 718 of 718 (663 s, with another project's CI loading the machine).
  `make test-db`: 36 of 36 (359 s).
- Journeys: the MariaDB deletion journey (a linkdead character refused, a new pid after the
  restart, the account deletion refused and retried) and the game-loop queries journey
  (`finger` through an offline load by pid with no account).

## Phase 3 progress

Not started. The branch is `fix/7-persistence-phase-3` (see [Review and branches](#review-and-branches)).

Decided on 2026-09-30, so nothing in Phase 3 waits on anyone:

- **Every server is treated as new.** None holds an older player-save or critical-command
  journal to replay or death-custody records to keep. The replays, what only they reach and the
  death custody and restitution feature with its tables all go (see
  [Phase 3](#phase-3-delete-what-is-left-over)).
- **The collector's death intake is restored in memory** (the owner chose that over deleting
  it). Since Phase 1 step 5 nothing enrols a player's death (`collector_death_enrollment_*()`
  has no caller), so the collector, off by default behind `collector.enabled`, never collects
  from a corpse. Phase 3 enrols the death at `make_corpse()` again, and moves the collector's
  scheduled collection (`collector_collection_prepare()`) and its maintenance reads off the
  runtime cache onto the live objects, before `item_ownership_runtime.c` goes.

Carried over from Phases 1 and 2, done in Phase 3:

- Flat-file lockers never load their items: the backend's `sql_load_locker()` is a stub and
  nothing reads the locker records it writes, so what a flat-file locker holds does not come
  back after a restart. Phase 3 loads them.
- The journey that dies, restarts with full-world corpse restoration and loots the restored
  corpse (the minimal-world journeys skip corpse restoration).
- The staging sign-off, which never ran: staging still runs a build from 2026-09-23. Once
  Phase 3 is on `master`, deploy it there, run the journeys in [Phase 1 tests](#phase-1-tests)
  and, after a day, the staging checks listed there.

The first step: put the [Phase 3](#phase-3-delete-what-is-left-over) list, the "left for Phase 3"
notes in the Phase 1 and 2 steps and the items above through ablation (`.agents/skills/ablation`),
confirming each deletion has no caller left, and split them into steps. Each step does one
area with its tests, in its own commits, and passes the gates: `make test-all`, `make test-db`,
the flat-file and pfile builds and `./scripts/format.sh --all --check`.
