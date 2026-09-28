# Persistence reset: memory is the authority again

**Date:** 2026-09-28

**Status:** Phase 1 in progress on branch `fix/7-persistence-phase-1`. See
[Phase 1 progress](#phase-1-progress) at the end for what is done, how it was done, and what is
left.

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
- saved room items.

This writer is the existing player save worker, cut from two threads to one
(`PLAYER_SAVE_WORKER_DEFAULT_THREADS`), with three new job kinds.

- **Order:** a newer save of the same owner replaces its queued one and goes to the back of the
  queue. Saves are therefore always applied in capture order.
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
   - the row names another player, corpse, locker, room or pet: set it to this owner, and write an
     `item_owner_audit` row with the item, vnum, old owner, new owner and time.
2. **Leave out what the economy holds.** If the row names an auction, a shopkeeper or the collector,
   the item is left out of this save and logged to `logs/log/dupes`. Those three still move items
   through their own transactions until Phase 2, so the database is right about them.
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

## Phase 1: end the problems

Each step is its own commit with a focused regression test. The flat-file backend gets the same change
wherever it has the same code, and its CI build and full-world boot test must keep passing.

1. **One writer.**
   - Cut the save worker to one thread.
   - Add job kinds for corpse, locker and saved-room-item snapshots.
   - A newer save of an owner replaces its queued one and moves to the back.
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
- The writer applies saves in capture order, and a replaced save moves to the back.

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
  - An action that moves money between two saved owners queues both saves as one job, so a crash
    cannot pay twice.
- **Epic points and frags** move the same way: the save writes them, and their transactions become
  in-memory updates.
- **Auctions, shops and the collector** save their holdings through the writer with the same claim.
  The economy exception in the claim then goes.
- **Game-thread SQL.** The remaining 345 `qry()` calls, most of them in `sql.c`, `artifact.c`,
  `auction_houses.c`, `boon.c`, `account_reward.c` and `epic.c`, move off the loop:
  - calls that write are queued on the writer;
  - calls that read happen at boot, from a cache, or through the async path.

  The latency trace must then show no database wait on the loop.

## Phase 3: delete what is left over

Remove the code nothing calls any more:

- `item_movement_transaction.c`;
- what is left of `item_transfer_command.c` and `item_transfer_repository.c`;
- `item_ownership_runtime.c`;
- `corpse_lifecycle_*.c`;
- the death restitution runtime;
- `player_save_journal.c`;
- the custody and degraded-load code;
- `currency_transaction.c`;
- the item and currency parts of `critical_command_*`;
- the flat-file equivalents of all of the above.

That is roughly 20,000 to 30,000 lines. The death-custody tables stay until staff have resolved the
records in them; dropping them is a separate owner decision.

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

## Done when

- A save cannot be rejected. Its only failure is a lost connection, and the writer retries that
  without the game noticing.
- No character is ever held after death, logout or idle rent.
- No corpse raise, resurrection or decay can fail on the database.
- Shutdown and copyover never wait on a failing save.
- After Phase 1, saves, logouts, deaths and corpses never wait on the database from the game loop.
  After Phase 2, nothing on the loop does.
- The database cannot hold one item under two owners, and `logs/log/dupes` accounts for every item a
  save or load gave up.

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
  matrix caught it). A pile with no row gets one.
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
