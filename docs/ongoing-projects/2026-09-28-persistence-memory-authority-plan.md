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
- **Coin piles.** A save claims a live pile like any item; only a spent (destroyed) pile is left
  alone (`item_claim_leaves_owner_alone(item, recorded_state)`). A login loads a pile only if the
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
    flat-file feature, not part of Phase 1.
  - A floor item is not an owner that saves: an item dropped in memory is gone after a restart on
    both backends (MariaDB never persisted floor drops either). `test_flatfile_full_world_boot.py`
    drops the mace, saves, picks it up and checks it survives the restart with the player.
  - The collector's scheduled collection of antiquities still prepares from the runtime cache
    (`collector_collection_prepare()`): an antiquity moved in memory since load is not collected
    until a reboot refreshes the cache. It is economy code for Phase 2.
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
    Nothing is lost: antiquities simply stay in the corpse. Economy code for Phase 2.
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
  "raising, resurrecting and decaying make no database call" test.
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
  `persistence_writer_pending_owners()`).
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

### Phase 1 tests and journeys (in progress)

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
  branch to be merged.

### Done-when review (in progress)

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
