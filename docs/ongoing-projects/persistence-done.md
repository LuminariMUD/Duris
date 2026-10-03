# Persistence reset: completed work

This is the record of completed work for [the persistence reset plan](persistence-plan.md). The
plan holds the framework and [what is left](persistence-plan.md#what-is-left). When a step or an
item there is finished, its record is added here (what landed, the decisions made on the way,
tests, verification, commits and the bugs found) and the item leaves the plan's list.

## Review and branches

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
- Phase 3 was reviewed as [!5](https://gitlab.com/max757/duris/-/merge_requests/5) (source
  `fix/7-persistence-phase-3`, branched from `60f56fb5b`), tagged
  `persistence/phase-3-review-0` and `-1` ([review round 1](#review-round-1-mr-5)). It landed
  on 2026-10-02 in `21f65de2c`, one `--no-ff` merge of the `-1` head, with no rebase or
  squash, so both tags still name what was reviewed. The branch is deleted
  ([record](#phase-3-landed-done)).
- Phase 4 was reviewed as [!6](https://gitlab.com/max757/duris/-/merge_requests/6) (source
  `fix/6-persistence-phase-4`, branched from `fix/7-persistence-closeout`, whose one commit
  beyond master is the plan's Phases 4 to 8), tagged `persistence/phase-4-review-0`. The
  review found nothing. It landed on 2026-10-02 in `d6952d701`, one `--no-ff` merge of that
  head, with no rebase or squash. Both branches are deleted ([record](#phase-4-landed-done)).
- Phase 5 was reviewed as [!7](https://gitlab.com/max757/duris/-/merge_requests/7) (source
  `fix/4-persistence-phase-5`, branched from master `b7105b7d4`), tagged
  `persistence/phase-5-review-0` and `-1` ([review round 1](#review-round-1-mr-7)). It landed
  on 2026-10-03 in `218d0640b`, one `--no-ff` merge of the `-1` head, with no rebase or
  squash, so both tags still name what was reviewed. The branch is deleted
  ([record](#phase-5-landed-done)).
- Phase 6 was reviewed as [!8](https://gitlab.com/max757/duris/-/merge_requests/8) (source
  `fix/3-persistence-phase-6`, branched from master `2d58826c4`), tagged
  `persistence/phase-6-review-0` and `-1` ([review round 1](#review-round-1-mr-8)). It landed
  on 2026-10-03 in `1a4b15f9d`, one `--no-ff` merge of the `-1` head, with no rebase or
  squash, so both tags still name what was reviewed. The branch is deleted
  ([record](#phase-6-landed-done)).
- Each later phase works the same way: a branch from master named for its work item, an MR,
  the head the review reads tagged `persistence/phase-<n>-review-0`, a review round's fixes on
  the branch tagged `-1`, `-2` and so on, then one `--no-ff` merge of the last tag.

## Phase 1 progress

This section is the hand-over log for [Phase 1](persistence-plan.md#phase-1-end-the-problems).
Each step records what landed, the decisions made while implementing it, and anything a later step
must pick up.

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
  (`player_save_journal_retire()`). This is the upgrade path: a stuck character's newest state
  can exist only in that journal. **Step 2 must keep the replay revision-fenced**
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
  it was not run. It was deleted with the restitution feature in Phase 3 step 3.
- Closed on 2026-10-02: `test_flatfile_full_world_boot.py` aborted once in nine runs (SIGABRT at
  the first connection, before character creation). It did not reproduce, and no full run since
  has failed it.

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
  accepted crash model ([What a crash costs](persistence-plan.md#what-a-crash-costs)).
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
  restore cannot create them twice. The flat-file corpse lifecycle capture
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
- A database needs migration `0033_item_owner_audit` before this binary boots; the local boot
  applies it.
- Known and accepted until Phase 2: creation grants and the economy (shops, auctions, collector,
  currency) still move items through their own transactions; the collector's death intake and
  its scheduled collection read the runtime cache; artifacts entering a player's corpse and
  divinely bound reward containers still make one synchronous call each at death; flat-file
  lockers never load items at all (a missing flat-file feature). Phase 3 deletes the dead durable
  paths (item movement transactions, the corpse lifecycle deferrals, terminal fences,
  `player_save_pipeline_terminal_death()`, the flat-file corpse lifecycle code in the critical
  command path). Phase 2 moved the economy; the collector's two cache reads and the
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

## Phase 2 progress

This section is the hand-over log for
[Phase 2](persistence-plan.md#phase-2-money-points-and-the-rest-of-the-loop), in the same form as
Phase 1's.

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
  later command on the same key (see [What was cut](persistence-plan.md#what-was-cut-and-why)).
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
- Order, after the plan's ablation (see [What was cut](persistence-plan.md#what-was-cut-and-why)):
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

This section is the hand-over log for
[Phase 3](persistence-plan.md#phase-3-delete-what-is-left-over), in the same form as Phase 1's; the
step list, its decisions and the gates are in the plan. Steps 1 to 9 are done, through
`ae53636ff`, and each step below records how it was verified.

### Step 1: the journals (done)

- The player-save journal: `player_save_journal.c`, `player_save_pipeline_init()`'s legacy
  replay and its health fields, the revision fence both backends kept for it
  (`PLAYER_SAVE_LEGACY_REPLAY`, `replay_fence()`) and `PLAYER_SAVE_JOURNAL_DIR` are gone.
  `player_save_pipeline_init()` takes no argument.
- The critical-command journal: `critical_command_journal.c`, the coordinator's replay (the
  `replayed` state, checkpoints, the replay observer) and the journal's health line in
  `world persistence` are gone, and so are the coordinator's admission-era health fields
  (`awaiting_durability`, `admission_*`, `append_inflight`), which nothing set.
  `critical_command_coordinator_init()` takes the apply function, its context and the
  extension validator. `CRITICAL_COMMAND_JOURNAL_DIR` remains the directory of the locker
  identification receipts, as decided.
- Backups: the policy's `journal_roots` holds `critical` alone (a policy naming `players` is
  refused, so an existing policy must drop that key), the capture takes only the
  receipts and their empty service lock, and restore qualifies the receipts
  (`qualify_flatfile_restore --receipts`) instead of draining journals. The data lifecycle
  manifest loses the two player-save journal stores, and `file:critical_command_journal`
  describes the receipts. `.env.example`, `compose.yaml` and the Dockerfile lose the player
  journal directory (`.gitignore` keeps ignoring it, since existing checkouts still have one).
- Deleted with them, as tests of the replay alone: `test_player_save_journal.py`,
  `test_critical_command_journal_faults.py`, `test_economic_accounting_replay.py`,
  `test_economic_flatfile_admission_native.py`, `run_player_death_disposition_mysql.sh` and
  the flat-file death disposition cases (deaths only arrived through the journal; the death
  snapshot code itself goes in step 3). The pipeline, coordinator, backup, remediation,
  flat-file repository and restore integration tests lost their replay cases; about 40
  journeys stopped creating a player journal directory.
- Found on the way (fixed in its own commit, `f2534ed63`): `persistence_writer_submit()`
  left its job default-initialized, so the unused snapshot of every corpse, locker, sql and
  critical job carried an indeterminate bool that moving the job read. UBSan caught it in
  the economic admission test once the coordinator's layout changed.
- Verified: both server builds and pfile build, the format check and the census pass,
  `make test-db` passes 36 of 36, and `make test-all` passed but for seven tests that still
  counted the removed manifest entries or called the removed replay argument; each was fixed
  and passes alone. `test_persistence_backup_integration.py` needs a privileged container and
  runs after step 2, which changes the same restore fixture.

### Step 2: what only the replay reached (done)

- The coin transfer command (`coin_transfer_command.c`), both repositories' coin and bank
  (`account_bank` currency command) branches, the item repository's coin leg
  (`item_transfer_repository_execute_coin()`), the flat-file coin apply and coin readers, the
  flat-file domain's bank command (`apply_currency_command()`) and wallet preparation, and the
  currency result codec. A currency command is still the payload of the in-memory charge
  (`currency_transaction_submit_prepared()`, locker identification receipts) and of the corpse
  lifecycle's wallet (step 5).
- Schema 2: the coordinator's extension validator, `critical_command_envelope_valid()`,
  `critical_command_legacy_execution_supported()` (now just `critical_command_valid()`),
  `accounting_intent` and the codec's schema-2 framing. Command types no code submits are
  gone (`wallet`, `locker_transfer`, `coin_transfer`, `guild`, `economic_baseline`); the
  others keep their numbers, which are stored, and `critical_command_valid()` checks the type
  by a switch.
- The coin failure stages (`critical_failure_stage`, `item_transfer_failure_stage`): the
  completion, the apply result and the inbox no longer carry one, and the boot schema probe no
  longer requires `critical_operation_inbox.failure_stage` (34 columns). The column stays
  (default 0).
- The economy accounting foundation (see the decision in
  [Phase 3](persistence-plan.md#phase-3-delete-what-is-left-over)): `src/economy/economic_*`,
  `src/persistence/economic_*`, `src/flatfile/flatfile_accounting_*`, the two mutation writers,
  `flatfile_accounting_dispatch.c`, `economic_command_admission.c`, the flat-file authority
  store `economic_evidence` and its `economic-evidence/` directory (the authority commit is
  `flatfile_authority_transaction_commit_operations()` again), the accounting-only flat-file
  domain helpers (`_load_locked()`, `_recover_locked()`, `_legacy_receipt_locked()`), 44
  tests, `docs/persistence/ECONOMY_ACCOUNTING.md` and `docs/persistence/economy_accounting/`
  with its census (`writers.json`) and `scripts/validate_economy_accounting.py`, which is no
  longer a gate. The data lifecycle manifest loses the nine flat-file accounting stores (239
  entries); the tables wait for step 3's migration.
- The flat-file domain transaction no longer carries banks (its bank count is written as 0 and
  must read 0), and the legacy `.currency-transaction` recovery is gone; the backup and the
  restore verifier no longer name that file, and the restore fixture's interrupted-bank modes
  and their integration test are deleted (the pending authority transaction case covers a
  pending transaction). `run_currency_transaction_schema_mysql.sh` and its harness tested only
  the deleted commands and leave `make test-db`; the player-load harness it also ran still
  runs in the experience-trophy leg. `docs/issue-505-stale-coin-transfer-investigation.md`
  described only the coin transfer and is deleted.
- Two fixtures moved a stored bank with the deleted bank command and now deposit through the
  writer's bank job (`flatfile_bank_delta_apply()`): the new-player bank hydration test and the
  journey inspector's `seed-creation-bank` (`test_flatfile_first_session_currency.py`).
- Verified: both server builds, the format check, `make test-all` (692 of 698; the six
  failures were four source contracts naming removed code and the two fixtures above, each
  fixed and passing alone) and `make test-db` (34 of 34, after the fix below).
- Found on the way (fixed in its own commit, `b9a78afe6`): `save` said `Save complete` once the
  writer had accepted the save, not once it had written it. Phase 1 made the pipeline
  acknowledge a revision at submit ("a character is clean once the writer has its save"), and
  the save command kept comparing against that revision, so its 30-second failure report could
  never fire. Under load three MariaDB journeys read the database right after `Save complete`
  and missed the save (`corpse_haul`, `corpse_haul_count_cap`, `game_loop_queries`, each
  passing alone). The writer's completion now advances the player's written revision
  (`player_revision_record_written()`), and `save` reports against it.
- Found on the way (fixed in its own commit, `61d3eaf01`): the locker identification crash
  test still charged through the repository's bank command, so it proved a ledger
  deduplication that ended when money moved into memory, and the service kept an
  unreachable "unknown payment outcome" retry. `paid()` records paid or failed; the harness
  charges an in-memory purse and saves it after the completion; the test is no longer a
  MariaDB leg; `docs/operations/locker-identification.md` says a prepared receipt is charged
  again on recovery, twice only if the player's save landed between the charge and the paid
  marker before the server stopped.

### Step 3: death custody and restitution (done)

- Gone: the restitution runtime, adapter, locker notice, staff path and `restitution` command
  (its number, 863, is a reserved `_retired_863` slot like the other retired commands), the
  native restitution command and repository and their critical command type (19), the
  restitution sidecars in the item transfer, player save and player load repositories (the
  load query cap is 23 again), `scripts/player_death_restitution*.py` and its codec, the issue
  331 journeys, 31 restitution test files, the spellbook overlay harness and the restitution
  docs.
- The death snapshot went too: `apply_death()` wrote the disposition tables, and only the
  journal (step 1) carried death snapshots, so the snapshot's `death` section, its capture,
  `player_save_pipeline_terminal_death()`, the codec's death wire versions, the flat-file
  `player-deaths/` store and its death quarantine are gone.
- The save pipeline's per-player "target save login fence" existed for restitution's offline
  delivery; with nothing taking it, `player_save_pipeline_save_admitted()` is gone and a load
  waits only while the player's save is queued.
- Kept, renamed: the database exclusion lock the server takes at boot
  (`sql_exclusion_guard.h`). It was named for restitution, but it is also what refuses a second
  server on the same database, which the one writer relies on. It is now
  `duris.runtime.<database>`.
- Migration `0034_retire_death_custody_and_accounting` drops the six death tables and the twelve
  accounting tables, and the accounting reference index 0031 put on `item_ownership_ledger`
  (guarded, re-runnable; the verifier checks nothing of them is left). The fresh bootstrap no
  longer creates them, the runtime contract covers 198 tables (fingerprints measured on clean
  `mysql:8.0` and `mariadb:10.11` with bootstrap and every migration; the same method reproduced
  the previous head's sealed values first), the lifecycle manifest has 220 entries, and the
  unused non-immutable copies `migrations/economy_accounting.sql`, `economic_baseline.sql` and
  their two verifiers are deleted. **An existing database needs
  `python3 scripts/migration_runner.py run` before this binary boots.**
- Verified: both server builds, the format check, `make test-all` (679 of 689; the ten failures
  were a blank line the cut left, two contracts naming removed code, and the journey
  inspector's death report, which broke its build for the seven tests that share it; each was
  fixed and passes alone) and `make test-db` (34 of 34, including the migration replay).

### Step 4: the durable item movement (done)

- Crafts (`e8ff3e55b`): poison, mix, encrust and the PvP orb consume their inputs and hand over
  their outputs in memory at the call site; `item_movement_transaction_submit_craft()` and the
  crafts' completion contexts are gone. Encrusting a Chaos-pouch jewel works again
  (`41c56e030`): it is recorded on the pouch's scoreboard like any other generated item.
- Item commands: `item_command_uses_durable_ownership()` returned false since Phase 1, so every
  get, drop, put, give and empty already moved the object in memory. The durable branches and
  the switch are gone, with their completions, the bulk get/drop/put state machines that waited
  on a commit, the pet and mobile claims and the bulk get busy gate. A bulk get, drop or put
  selects, moves and reports in one pass; `empty` refuses the whole move if any item may not go
  into the destination and stops at the first item that does not fit. `item_command_policy`
  keeps only the two checks get, put and empty share; `item_get_policy` and the put/drop
  destination resolvers are gone.
- The craft path in the repositories (MariaDB and flat-file), the runtime cache, the
  shop-trade materialization and the payload validation; the synthetic transfer adapter;
  `OBJ_RFLAG_CREATION_CANDIDATE`.
- The coordinator's journal-era submit results (`awaiting_durability`, `journal_failure`,
  `journal_uncertain`) and the functions no path reached (`critical_command_coordinator_
  durability()`, `_get_completed()`, `_recover_uncertain()`); its completed cache keeps only the
  command it checks resubmissions against.
- Dropped by the linker on both backends: the locker owner resolvers,
  `item_movement_reject_name()`, `item_ownership_runtime_snapshot_owner()`, the single pre-entry
  grant and `corpse_lifecycle_transaction_note_item_transfer()`.
- Item transfer reasons are stored in ledger and audit rows, so the enum spells out every value;
  `synthetic` (1) and `craft` (29) are retired and their numbers stay unused.
- Kept: `item_movement_transaction_submit()` and `_submit_batch()`. The creation grants use
  them, and the durable corpse lifecycle still calls them until step 5. The grants' stock
  adoption (`operator_repair`) reads the runtime cache, so it goes with step 6.
- Tests: the ones that pinned the durable mechanism are deleted (the bulk drop/put and get-all
  chains, the put partition, the durable empty runtime, the pickup source owner and mixed-owner
  selection, the NPC give boundary, the flat-file craft conservation); the bulk get, corpse
  haul, money count, input queue, collector and coordinator harnesses run the new code;
  `test_empty_command.py` covers `empty`.
- Verified: both server builds, the pfile build, the format check, `make test-all` (679 of 682:
  two contracts still counted the removed no-loot check and the encrust refusal, and
  `test_password_async_runtime.py` missed a timing bound under the parallel load; each passes
  alone after the fixes) and `make test-db` (33 of 34: `game_loop_queries` hit a race in the
  epic bonus display, fixed in its own commit).

### Step 5: the durable corpse lifecycle (done)

- Every `persistence_defer_corpse_*()` returned false since Phase 1 step 6, so its 17 callers
  (and `Decay()`) ran the in-memory code that follows; the calls, the deferrals and everything
  behind them in `handler.c` are gone (about 1,700 lines), with `corpse_lifecycle_command.c`,
  `_repository.c`, `_transaction.c` and the flat-file corpse repository. So is what only they
  reached: the corpse operation and outbox route (critical command type 16 is retired), the
  game-thread completions and pulse, the boot hydration of corpse revisions on both backends
  (the corpse loader no longer reads `corpse_revision`; the corpse save still maintains it),
  the corpse busy checks in `actobj.c`, the ownership runtime's corpse transitions, the
  world-item, artifact, item and collector repositories' corpse lifecycle preparations, the
  resurrection materialization and wallet, and the raise helpers in `necromancy.c` and
  `magic.c` (`corpse_raise_kind` included).
- The corpse raise save fence (`CHAR_RFLAG_CORPSE_RAISE_SAVE_FENCE`,
  `corpse_raise_player_save_fenced()` and `_ready()`) was set only by the durable raise.
- The currency repository (`currency_repository_execute()`, `execute_currency_state()`,
  `write_currency_state()`) was reached only through the corpse lifecycle's wallet; with it go
  the currency outbox record and route, the prepared mutation and rebase helpers and the
  publish functions. Currency commands survive as the payment inside locker-identify receipts,
  applied in memory. Their reasons are stored there, so the enum spells out every value;
  `coin_transfer` (16) and `corpse_lifecycle` (18) are retired.
- The terminal save (`player_save_pipeline_terminal()`, kept for a new flat-file player's
  first save) waited on its own fence table. It now waits for the written revision the
  revision state already records (step 3), and the table is gone; the status line counts
  terminal saves.
- The flat-file restore qualifier no longer builds or runs the corpse repository's validator,
  and the backup integration test no longer corrupts the deleted `corpse_operation_catalog`.
- Tests: the corpse lifecycle command, repository (both backends) and transaction tests, the
  MariaDB schema leg and the fresh-corpse adoption contract are deleted; the build lists of
  the flat-file and schema harnesses drop the deleted sources; the corpse routing,
  corpses-in-memory, restore, runtime and currency contracts keep only what is live.
  `docs/testing/FIRST_FLATFILE_CORPSE.md` described a fix inside the deleted upsert path and
  is gone.
- Verified: both server builds, the pfile build, the restore qualifier build, the format check,
  `make test-all` (677 of 677) and `make test-db` (33 of 33; the corpse lifecycle schema leg is
  gone).

### Step 6: the collector's death intake (done)

- `make_corpse()` begins the death's intake (`collector_death_enrollment_begin()`, with the
  feature's policy as it stands then), and every save of that corpse carries the death until
  one is written. The writer records the death and the corpse's eligible items as collector
  candidates in the corpse save's own transaction: MariaDB in `write_corpse()` through
  `collector_repository_enroll_death()`, flat-file in `flatfile_corpse_snapshot_apply()`
  through `flatfile_collector_prepare_death_enrollment()`, whose catalog image commits with the
  corpse's. A written save completes the intake (`collector_death_enrollment_saved()`), which
  invalidates the collector's catalog cache; a refusal (a full catalog, a death recorded
  differently) leaves the corpse saved without it, comes back as the save's error code and is
  logged. A later save of the same corpse adds only items not yet listed. Listings record
  item revision 1, the floor the collect policy compares against.
- Collection reads the live world: `collector_collection_prepare()` finds the player corpse
  that holds the antiquity and captures its tree from the live objects; anywhere else it was
  claimed. The repositories take the stored item revisions for a corpse or room source (its
  saves move them), as they already did for the owner revisions, and the flat-file world-item
  check of the corpse record's revision is gone for the same reason.
- The intake no longer rides on an item transfer: `item_transfer_payload`'s collector context,
  its codec (the payload keeps a zero-length section so its layout holds), the item command
  path's enrolment on both backends and the movement transaction's attach and note are gone.
- Kept: `item_ownership_runtime.c`. The plan expected it to go once the collector stopped
  reading it, but shops (stock), auctions, the creation grants and the collector's own
  purchases and expiries read it for items the economy holds (shopkeeper, auction, collector
  and system custody), whose revisions only economy commands move. Those reads are live
  fencing, not dead code. Its entries for memory-held owners (players, rooms, corpses) are
  stale since saves claim items; nothing that decides custody for those owners reads them.
- Tests: `test_collector_death_enrollment.py` and its harness, the collection preparation
  harness, both collector repository harnesses and the item-transfer version test follow the
  new shape; `test_flatfile_collector_intake_journey.py` (test-all) and
  `run_mysql_collector_intake_journey.py` (test-db) die with the collector on and wait for it
  to take the banana from the live corpse while the coins stay.
- Verified: both server builds, the format check, `make test-all` (676 of 678: the flat-file
  world-item test still expected the removed revision refusal, and the save pipeline harness
  lacked a stub for the new completion hook; both pass alone after the fix) and
  `make test-db` (33 of 34: the save-claim leg's build list lacked the collector repository the
  corpse writer now calls; it passes alone after the fix). The new MariaDB collector journey
  passed in that run.

### Step 7: the game thread's dead SQL (done)

Each item is its own commit on `fix/7-persistence-phase-3`; the found bugs are fixed in theirs.

- **The legacy event log** (`24c5aeb78`): the item, scalar and large-event queues
  (`persistence_queue.c`), their workers, heartbeat check and flat fallback log
  (`logs/log/events`, `LOG_EVENT`), the raw SQL executor (`sql_persistence_raw.c`), the SQL event
  writers and the persistence connection they borrowed, the pwipe quiescence and fallback
  quarantine, the three queue lines in `world persistence`, and
  `scripts/inspect_legacy_persistence_fallback.sh`. Then the boot-time stress hooks that ran
  the queue's tests in a build without `__NO_TESTS__` (`src/core/test_async.*`, the define and
  the `tests/async` include path; `2f8a6349d`).
- **The non-account login path** (`c382052a3`): `USE_ACCOUNT` is always defined, so
  `select_name()`, `select_pwd()`, `select_main_menu()`, their reconnect, one-hour and multiplay
  checks, `PLAYER_LOAD_MODE_LEGACY` and its completion never ran; nor did `enter_game()`'s
  non-snapshot entry (the bank load, `reset_char()`, the item restores) for a character with a
  level. Gone with them: `sql_load_account_bank()`, `restorePasswdOnly()`,
  `sql_find_racewar_for_ip()` and the flat-file IP lookup.
- **The pfile import and the legacy player writer** (`d62c44713`): `--migrate-all`, and the
  synchronous `sql_save_player()` and `sql_load_player()` with their components, the batched
  item writer, the row readers and the verifier, and the account-menu cache those saves queued
  at commit.
- **The listed game-thread SQL** (`d0d59ce10`): the MariaDB auction expiry and `*_legacy`
  auction commands, the boon progress and shop inserts, the epic zone balance, alignment,
  frequency and modifier updates, the outpost resources, the poll expiry sweep, the guild,
  locker, spellbook and shopkeeper deletes and the shopkeeper restore, `arti_remove_sql()`, the
  account bank functions, `update_nexus_stat_mods()`, `event_write_statistic()`, the other
  `sql.c` functions nothing calls and the unused pfile writers, pet and ship registry functions
  in `files.c`. Then the boon progress notice only the deleted legacy completion sent, whose
  `get_boon_progress_data()` queried MariaDB on the game thread (`c37ec9d0d`).
- **Linker-dead persistence code** (`9920cef74`, `13cdb55a6`, `21017b01a`, `2ad78293e`): the
  flat-file identity mutations (deletion and accounts use the prepared operations); the
  inflight revision API and the state only it and tests read (the revision state keeps the
  current, acknowledged and written revisions, the unacknowledged components, the
  per-component revisions and the overflow flag); the collector catalog codec, the critical
  outbox's reconcile and dead-letter retry (nothing exposed them), the all-component dirty mark
  and the unsliced dirty flush, the pool counters, the session audit result decoder, the
  flat-file artifact release and combined player/locker removal, the flat-file shopkeeper save
  module, three copyover buffer helpers and the random boon routine (it returned at once); and
  `apply_items()`'s half-graph branch, which only the deleted journal records could reach.
- Kept, though nothing in the server calls them: test-only API (the reset, count, health and
  status hooks, the fixture builders such as the `establish` and `list` functions and
  `flatfile_identity_claim()`, the MariaDB harnesses' connection-level `*_repository_apply()`
  and `player_snapshot_repository_write_pets()`, the copyover mob encoder the singleton harness
  pairs with the live decoder), and `restoreItemsOnly()` with its helpers, which the pfile tool
  reads old pfiles with. Dead code outside the persistence reset stays out of scope.
- Found and fixed while doing this:
  - A save that failed with `ENOENT` set `CHAR_RFLAG_NO_DB_BASELINE` on both backends; on
    MariaDB, which has no synchronous first save, that made every later save of the character
    do nothing. The re-arm is flat-file only (`41f93988d`).
  - Nothing has called the poll expiry sweep since the maintenance scheduler, and on flat-file
    it was the only thing that closed an expired poll (`poll vote` still counted votes). The
    flat-file readers now close a poll once it expires, as MariaDB's memory does
    (`ecbfad024`).
  - The scheduler's `auction_due_scan` and `boon_scan` jobs only ever ran against MariaDB: on
    flat-file they asked for a SQL connection and retried forever, and the flat-file auction
    activity (expiry and its recoverable notices, written a day after the scheduler) and the
    flat-file boon expiry never had a caller. On flat-file the worker now completes those two
    jobs at once and the game thread runs the flat-file activity when the result arrives
    (`9b1c519dd`). The other SQL jobs (epic zones, level cap, task catalog, statistics) never
    had a flat-file implementation; they still fail retryably there, as before.
  - Only the non-account login path, which never ran, honored the database creation lock
    (`mud_info` `lock` set to `create`); the account path honored only the in-game toggle and
    WebSocket creation neither. Both creation paths now refuse a new character under either
    lock (`381ff8783`).
- Not part of the reset (decided on 2026-10-02, see
  [What was cut, and why](persistence-plan.md#what-was-cut-and-why)): since the accounting
  foundation went, the opening baselines
  (`currency_wallet_baseline`, `epic_balance_baseline`, `combat_frag_baseline`) are written for
  every player but read only by the boot coverage probes and the account projection repair,
  and nothing writes the event log's tables any more (`sql_pwipe()` still empties them).
  Removing either is a schema change: a migration, the bootstrap, the probes, the lifecycle
  manifest and `scripts/import_legacy_dump.py`.
- Done after step 9, as Phase 3's item 10: dead branches behind live dispatchers, which the
  linker cannot see. Nothing submits a locker deposit or withdrawal any more (step 4), so the flat-file item
  repository's locker transfer branch and `flatfile_locker_prepare_item_transfer()` never run;
  `item_movement_transaction.c` now submits only creation grants (and operator repairs), so its
  corpse batch and trusted-steal paths are unreachable, and both item transfer repositories
  still handle reasons no command sends. Cutting them reshapes live creation-grant and economy
  code, so it was not folded into this step; see
  [After step 9](#after-step-9-the-dead-transfer-branches-not-asked-for).
- Tests: the event log's tests (13 files and `test_persistence.{c,h}`), the legacy writer's
  (`test_sql_player_dirty_bits.py`, `test_player_replacement_state.py`,
  `test_playtime_legacy_sql.py`) and `test_flatfile_shopkeeper_save.py` are deleted; the mixed
  contracts and harnesses keep their other checks or follow the new shape.
- Verified: both server builds, the pfile build, `./scripts/format.sh --all --check`,
  `make test-db` (34 of 34) and `make test-all` (642 of 661). The 19 failures were contracts that
  still named deleted code: three went with it, 16 were updated and pass alone
  (`67962c4da`); the information cache contract's check also found the creation lock bug
  above.

### Step 8: flat-file lockers keep their items (done)

- On flat-file the locker writer never started (`locker_async_init()` wanted a SQL pool, and
  a minimal world did not call it), so every locker save was refused, and entering a locker
  passed no rows: whatever was left in one was gone once it closed, and after a restart.
- The writer now saves a locker's public chest on flat-file too (`write_locker()` in
  `locker_async.c`): `flatfile_locker_snapshot_apply()` claims the chest's items for it and
  writes its locker catalog record in one authority transaction, through the same
  `apply_world_snapshot()` corpses and saved items use, which now names its owner under the
  lock (`flatfile_locker_public_owner()` gives the stored locker's ids or a new locker's, and
  `flatfile_locker_prepare_public_save()` creates a new account or guild locker). A player's
  own named locker is entered only when it exists, so none is ever new.
- Entering a locker reads its record (`flatfile_locker_find()`), keeps the items no other
  owner holds (`flatfile_world_load_item_ownership()`, the corpse restore's filter, now
  public), and materializes them onto the locker character after the access checks; a locker
  that cannot be read or materialized is not opened, so its next save cannot empty it.
- Private chests stay MariaDB's: creating one needs the database.
- `test_flatfile_locker_journey.py` (test-all) promotes the character to a god (lockers are
  otherwise for towns), leaves the banana in the account locker, restarts, takes it back and
  restarts again, and reopens a guild locker once its save has landed (a minimal world loads
  no guilds after a restart). The locker pipeline, leave-during-save, minimal boot, items in
  memory and pool worker gate contracts follow the new routing.
- Commits: `3a3d1c3e6`, and `ae53636ff` for the two contracts the step 8 commit missed.

### Step 9: the die, restart and loot journey (done)

- `test_flatfile_death_restart_journey.py` (test-all, about 70 s) runs the full world on
  flat-file, which restores corpses at boot: a new character takes its own life, the server
  restarts and restores the corpse where it died, the character loots its mace and saves,
  and after another restart the mace is still the character's and no longer in the corpse.
  It found no defect. Commit: `c6e0219da`.

### Steps 8 and 9 verified

At `c6e0219da`: both server builds, the pfile build, `./scripts/format.sh --all --check`,
`make test-all` (658 of 660: the two failures were the contracts fixed in `ae53636ff`, which
then pass alone; both new journeys passed under the parallel load, 151 s and 171 s),
`make test-db` (34 of 34) and the backup-recovery container replay (passed).

### After step 9: the dead transfer branches (not asked for)

After step 9 the dead transfer branches listed under step 7 were cut, without being asked. Since
the 2026-10-02 ablation they are Phase 3's item 10, because they delete what its list says goes
(see [What was cut, and why](persistence-plan.md#what-was-cut-and-why)).

- `4621a6c8a` (committed): `item_movement_transaction.c` keeps only the creation grants
  (the generic and batch movement submits, corpse metadata, mobile claims, trusted-steal
  retention and the opt-in publication callbacks are gone), and the coordinator loses its
  publication phase (`submit_for_publication`, `acknowledge_publication`,
  `publication_pending`). The tests that read or link those files pass;
  `test_publication_retention_runtime.py` is deleted. The full gates were not run on it.
- `01a345b84` (committed): item transfer commands accept only creation, operator
  repair and destruction, at payload version 7 only, without the corpse context; the MariaDB
  repository loses the pet move; the flat-file repositories lose the locker and corpse
  transfer prepares, the artifact transfer prepares become
  `flatfile_artifact_room_transfer_allowed()`, and the materialization loses its pet branch;
  the collector boundary loses the mobile-claim and raise-pet cases. The repository harnesses
  are reworked (the flat-file collector harness now sets up corpses through
  `flatfile_corpse_snapshot_apply()`), `test_item_transfer_version_compatibility.py` becomes
  `test_item_transfer_codec.py` (with `quality.yml` and the collector design doc). Verified:
  both server builds, the pfile build, the 58 tests that name the changed code, and both
  MariaDB harnesses (collector repository, item transfer schema). Not run: the full gates
  and the format check over every file.
- Both are pushed; the full gates are in
  [What is left](persistence-plan.md#what-is-left).

### Local backup policy (done)

This worktree's backup policy still named `players` in `journal_roots`, and its critical journal
directory still held the old, empty `critical-command.journal`, so the backup refused it
(`./scripts/backup_pfiles.sh status` failed with `invalid_journal_roots`) and a scripted local
boot could not pass its backup. On 2026-10-02 `players` was taken out of the policy and the empty
file deleted; `status` now gets past the policy (it reports `rpo_exceeded` until the next backup).

### The ledger reconcilers (done)

What is left's first fix. A save writes balances from memory without a ledger row and claims
the items it holds without a transfer, so the currency, epic, frag and item ownership
reconcilers reported ordinary play as drift (on `duris_dev`, `owner_revision_mismatch=4`;
the three balance reconcilers passed there only because no money had moved since Phase 2).

- `369eb5b33`: the four reconcilers are deleted and taken out of
  `reconcile_phase02_domains.sh` (now artifact and boon), the runbook's Domain reconciliation
  (which now says why nothing reconciles balances or item ownership) and coin-custody steps,
  and the six contracts that named them. The runbook's "Epic ledger cutover and
  reconciliation" section went with `reconcile_epic_balances.sh`. The header of
  `repair_item_nesting.sh` no longer points at the item reconciler or at give/drop capture.
  Verified: the six contracts, `reconcile_phase02_domains.sh` on `duris_dev` (passes).
- Kept: `repair_item_nesting.sh`. On `duris_dev` it reports `nesting_mismatch=13`, all
  Selwyn's (pid 3301, last saved 2026-09-01, before Phase 1): load places items where
  `item_current_owner` says (`player_load_topology.c`), and the next save's claim rewrites
  the nesting from memory, so it is history, not a live defect.

Found along the way, each fixed in its own commit:

- **A new account bank stopped the next boot** (`d09315a79`). Boot refuses an
  `account_banks` row with no `currency_bank_baseline`, and since bank changes became deltas
  the delta that creates a bank row wrote none, so an account's first deposit on a side made
  the next boot fail ("currency bank baseline does not cover every account bank"). The delta
  now writes the bank's opening baseline from the row it has just written, in the same
  transaction (`INSERT IGNORE`, so it leaves an existing one alone and settles an older bank
  on its next delta). `run_player_save_claim_mysql.sh` (test-db) failed on the new check
  before the fix and passes after. The live first-deposit and restart journey now passes too
  ([record](#a-first-bank-deposit-survives-a-restart-done)). Every bank a server without
  this fix created has no baseline, touched since or not, and boot refuses before a
  delta could write one, so migration 0035 backfills them
  ([review round 1](#review-round-1-mr-5)).
- **The combat-baseline repair refused every played database** (`4e9137a14`).
  `repair_missing_combat_baselines.sh` inlined the deleted reconcilers' ledger arithmetic in
  its apply guard and receipt, so the reviewed insert rolled back wherever balances had moved.
  It now checks readiness, wallet, bank and epic baseline coverage and the required foreign
  keys. `run_combat_baseline_repair_mysql.sh` (manual, not in test-db) gives an unrelated
  character ledgerless balances: before, the safe apply rolled back; after, it passes with the
  conflict and history refusals intact. `test_combat_baseline_repair_workflow.py` passes.

### DATABASE.md (done)

What is left's second fix. Besides the two sections the ablation named ("Consistent player
load" and "Critical transactions and current item ownership"), the connection notes, the
execution boundaries table and its journal paragraphs, the item row of "Tables worth
knowing", the epic read model's balance sentence and "Revisioned player checkpoints and
terminal saves" (now "Player checkpoints and terminal saves") still described the database as
the authority, so all of them were rewritten to [How it works](persistence-plan.md#how-it-works).
The documentation and siege removal contracts, which read the file, pass. Commit: `838c0e827`.

### The rest of the docs and a dead branch (done)

Found while bringing DATABASE.md up to date, each in its own commit:

- **The persistence reference docs** (`cb740d18d`). ARCHITECTURE.md, PLAYER_SAVE_PIPELINE.md,
  the runbook and EVENTS.md still described the journal dispatcher, revision-fenced keyed
  save workers, terminal saves that keep the character until the database acknowledges, the
  legacy compatibility queues, operator steps to preserve and replay journals, and alerts the
  server no longer raises (`fallback_saved`, `shutdown_cancelled=1`). They now describe the
  one writer; terminal saves that queue and leave at once; a shutdown that gives the writer
  30 seconds and always goes; a copyover that waits the same 30 seconds and is called off
  when the writer cannot drain (`copyover_save()`); and the save alerts raised now. This also
  corrects DATABASE.md, which had said copyover never waits on a failing save.
- **The remaining docs** (`9b91a4533`): CONVENTIONS.md (it told developers a failed terminal
  save must keep the character), incident response, the starter grants (journal admission
  and the uncertainty gate), CHAOS mode, output preferences, epic stone recovery, the
  telemetry storage design (it cited a `critical_command_journal.c` that no longer exists),
  playtime and the collector design (its purchase no longer debits the wallet). Kept: the
  flat-file authority journal (`flatfile_authority_transaction.c`), backup contents, and the
  dated records (`docs/adr`, `docs/records`, `docs/gates`,
  `docs/testing/CRITICAL_COMPLETION_CAPACITY.md`).
- **The zone touch's dead retry branch** (`7a1613c21`). The coordinator hands a retryable or
  ambiguous result back to the writer, which retries it, so the game thread only receives
  final completions; `zone_touch_transaction_handle_completions()` still had an "awaiting
  recovery" branch that only the stone runtime test's injected completion reached. The
  linker pass cannot see a dead branch inside a live function. Grepping the game-side
  completion handlers for `critical_apply_outcome::retryable_failure` and `ambiguous_commit`
  found no other.

On the way, a flat-file-only wait was checked and kept: a new character's first save waits
up to five seconds for the local write (`writeCharacter()` in `src/core/files.c`), because
its domains are read back right after. It is a file write, not a database query.

### The gate on the branch head (done)

On `0b90e5fc1`, run once each: `./scripts/format.sh --all --check` (1030 files clean),
`make test-all -j16 TEST_JOBS=16` alone (659 of 659, 461 s), then `make test-db` (34 of 34,
197 s) and `npm test --prefix site` (14 tests) side by side. An earlier run of the same gate
on `d737ada3e`, before the docs sweep and the dead branch, also passed (659, 34, 14). No
failure needed a fix.

The live first-deposit and restart journey was verified after this gate
([record](#a-first-bank-deposit-survives-a-restart-done)). The backup-recovery container replay
was not repeated, since nothing here touches what the restore qualifier runs.

### A first bank deposit survives a restart (done)

On 2026-10-02, `run_mysql_bank_restart_journey.py` passed against the MariaDB server built
from `2084cc2ff`. It uses a disposable MariaDB 10.11 container, a fresh schema and a new account
and character, with an ATM and seven platinum in the existing journey fixture. It checks:

- Neither a bank row nor an opening baseline exists before the first deposit.
- The character picks up the coins and runs `deposit 5 platinum` through the real game
  connection. The writer records five platinum in both the bank and its opening baseline,
  with revision zero, and saves the wallet with five fewer platinum.
- A clean shutdown and restart succeed without any intervening migration or repair. A real
  login reports the five-platinum bank balance, and a subsequent save and shutdown preserve
  the bank, wallet and opening baseline.

No server fix was needed. The journey is registered as `bank_restart` in `make test-db`.
The build (`make -C src -j16`) and this focused journey pass:

```sh
tests/async/with_disposable_mariadb.sh \
    python3 tests/async/run_mysql_bank_restart_journey.py bin/server/dms_new
```

Python and shell syntax checks and `git diff --check` pass. The full gate above was not
repeated for this test and documentation change.

### Review round 1 (MR !5)

The review read `949e11dd0`, two commits past `persistence/phase-3-review-0`: a merge of
master with an identical tree, and the bank restart journey. It found five defects. Each is
fixed in its own commit on `fix/7-persistence-phase-3`, with a regression test that fails
without it. The fixed head is tagged `persistence/phase-3-review-1`.

| Finding | Fix | Commit |
|---|---|---|
| 1. High: master leaves `critical-command.journal` (and, after a crash during its rewrite, `critical-command.journal.tmp`) in `CRITICAL_COMMAND_JOURNAL_DIR`, which Phase 3 kept for the locker receipts and in which it refused anything else. On every upgraded host the pre-boot backup failed with `journal_filename`, so `cycle_mud.sh` refused to boot, and every generation taken before the upgrade failed the restore qualifier. | The backup and the restore qualifier carry those two files, unread, beside the receipt store; anything else is still refused. Deleting them at startup would not help, since the pre-boot backup runs before the server. `test_backup_review_remediations.py` and the integration test's receipt cases cover both files and a foreign one. | `a591dec4e` |
| 2. Medium: the restored death intake collected a listed item from whichever player corpse held it. Once another player looted it and died, maintenance took it, and everything under the same root, from that player's corpse. | The preparation requires the listing's own corpse, which its beneficiary and death time name (the death time is the corpse's save id); anywhere else the listing is cancelled as claimed. The payload's owner is that corpse, and only the preparation builds a collect payload, so the repositories (which check the stored owner against it) and the live check need no check of their own: the suggested repository check was left out. The preparation harness covers another player's corpse and the beneficiary's later one. | `7cc9faea4` |
| 3. Medium: an authority intent master left after a crash named its player death (6) and accounting evidence (7) stores. Recovery returned invalid and kept the intent, so every flat-file commit after it was refused. | Recovery skips those stores' operations, applies the rest and clears the intent; a new commit still cannot name them. The authority harness recovers such an intent. | `327f18e70` |
| 4. Medium: every bank a server without `d09315a79` created has no opening baseline, touched since or not, and boot refuses before a delta could write one. The deploy note's "not touched since" was wrong. | Migration 0035 backfills them (`INSERT IGNORE ... SELECT`, re-runnable) and its verifier requires full coverage. It changes no table, so the fingerprints stay and the runtime head moves to 0035. The MariaDB bank journey starts at head 0034 with such a bank and checks its baseline after the migration run. | `1fef621ce` |
| 5. Medium: an item put into a player corpse (`put`, `put all`, `empty`) was saved by neither the corpse nor anything else, so a restart lost it with nothing in the dupe log. | The three command endings save a filled player corpse where they already saved a filled saved item. Unlike coins, items need no putter save first: the ownership key keeps one owner whichever save lands first, and a crash between the two leaves the items in the corpse, so the suggested save-first was left out. The flat-file die, restart and loot journey puts the looted mace back, restarts and loots it again. | `bb497c374` |

Found while fixing finding 3, fixed in its own commit:

- `8a962ac37`: master's flat-file currency command also wrote the player and the account bank
  in one `.player-domain-transaction` intent, and Phase 3 refused an intent that still held a
  bank. After a crash mid-command, every player domain operation failed, and deleting the
  intent would have kept one of the two writes without the other. Recovery decodes and writes
  the banks again, before the players, as master did. The player-domain harness loads a
  player through such an intent. No other intent file changed: master's `.currency-transaction`
  was written only by test builds and recovered at boot.

Left as it is, as game behaviour: a player corpse's capacity is the weight its player carried,
and the corpse shell (object 2, weight 200) counts against it. A put into a player corpse
therefore fits only once more than that weight has been looted, so finding 5 needs a corpse
that has had over 200 looted from it. The journey's world gives the shell no weight.

Verification for this round:

- Each new regression test fails on `949e11dd0` (a throwaway worktree with the new tests):
  the backup capture refuses the retired journal (`journal_filename`) and the old qualifier
  exits 1 on it; the preparation harness collects from another player's corpse; the
  authority and player-domain harnesses leave the older intents unrecovered; the bank
  journey finds no baseline for the older bank after the migration run. With the old
  `actobj.c`, the die, restart and loot journey loses the mace at the restart, and the empty
  command test no longer saves the corpse it filled.
- The gate, on `bb497c374` with this record: `./scripts/format.sh --all --check` (1030 files
  clean); `make test-all -j16 TEST_JOBS=16`, 659 of 659 (459 s); then side by side
  `make test-db`, 35 of 35 (292 s), `npm test --prefix site` (14 tests) and the
  backup-recovery workflow replayed in a privileged `ubuntu:24.04` container (its policy
  tests and all five integration tests, including the receipt matrix's retired-journal and
  foreign-file cases). A first `make test-all` failed two tests, both fixed before the rerun:
  `test_empty_command.py`, whose harness lifts `start_empty()` and lacked the new call, and the
  documentation contract, on this record's anchor before the record existed.

### Phase 3 landed (done)

On 2026-10-02 !5 landed in `21f65de2c`. Master had no commits the branch lacked, so the
merge's tree is the gated review round 1 head's, `18f97f1e1`, and nothing was rerun for it.
The branch is deleted, and this worktree continues on `fix/7-persistence-closeout`, branched
from master after this record.

The local `duris_dev` was upgraded the way the deploy note says, as a first upgrade of a
database a running server wrote. It was at head 0033.

- A `mysqldump` of it went to `~/.local/share/duris-issue-7/`.
- `python3 scripts/migration_runner.py run` applied 0034 and 0035, and
  `./migrations/verify_runtime_compatibility.sh` passes. The retired tables are gone. 0035 had
  nothing to backfill: every bank already had a baseline.
- `./scripts/start_mud.sh --dev` booted the merged build in about a minute, through the
  pre-boot backup with the critical journal directory in place, and `/health` answered
  `healthy`/`ready`.
- The `.env` character logged in without a degraded load, answered `look` and `score`, and
  quit.
- A SIGTERM ended the game normally ("Normal termination of game", `shutdown [0]`). Nothing
  reached `logs/log/dupes` and no persistence alert was raised.

### The work items closed out (done)

On 2026-10-02 every open work item was checked against `master` (`21f65de2c`), and each
description now records what the reset resolved:

- #7 is closed. Each of its Done when items holds; the closing comment names the step and the
  tests behind each. Its first comment linked the plan's old name and the deleted Phase 1
  branch; both links are corrected.
- #3: the journals behind section 2's backup failures are gone. Still open: every run
  re-verifies every generation, failing backups raise no RPO alarm, the catch-all error code,
  the restore drill and replica, and a narrow race left from section 2: a locker
  identification receipt that changes during the dump still fails that run. Retitled.
- #5: `rent`, `quit` and the hourly shop save no longer wait on the database, and the
  2-second death-disposition callback is gone. Still open: the tick stalls under load,
  unnamed callbacks, `-Og` production builds, MariaDB sizing and the backup job's CPU use.
- #6: the corpse `commit_failed` alerts went with the durable corpse lifecycle. The
  critical-command alert lost its failure stage in Phase 3 step 2 and now names nothing; it
  stays open with the rest. The item claimed alerts were not aggregated; a 30-second wizlog
  limiter exists, but it keys on the alert's detail, which is now stated.
- #4 and #2 were checked too. On #4 the zone-story 64 KiB limit (`9fafc10dd`) and the mob
  pickup retries (this reset) are fixed, and a full-length IPv4 address fits `sql_log()` since
  `c8fba0087`; IPv6, the people-list desync and the corpse decay decision stay. Retitled. #2
  is unchanged in code; its capture-expiry section now stands in the item itself.
- At the owner's request, what is still open in #6, #4, #3, #5 and #2 became Phases 4 to 8 of the
  plan, one phase per work item.

## Phase 4 progress

Phase 4 ([plan](persistence-plan.md#phase-4-alerts-and-logs-6)) was done on
`fix/6-persistence-phase-4`, branched on 2026-10-02 from `fix/7-persistence-closeout`
(`6689c5f20`, the plan's Phases 4 to 8).

### Idle connections (done)

Item 7 asked for a test proving that the pool reconnects after MariaDB closes an idle
connection. The test found that an idle timeout stopped every write, for two reasons, and a
third defect behind them. Each is fixed in its own commit:

| Defect | Fix | Commit |
|---|---|---|
| Every pool loan probes the runtime lock on the borrowed connection. On a connection MariaDB had closed for idling, the probe failed and the guard latched the lock as lost: the pool lent nothing again, so no save, load or command reached the database, though the main connection still held the lock. A reconnect that failed also dropped its pool slot for good, so a database restart could leave the pool empty. | A probe that fails says nothing of the lock; only an answer naming another owner loses it. The pool opens a new connection for that loan. A failed reconnect keeps the slot for the next loan. `sql_pool_replace_connection()` gives the slot back whenever it returns NULL, as every caller but `apply_with_pool()` already assumed. | `167f1f88a` |
| The main connection holds the lock, and since Phase 2 step 8 the game thread issues no query on it after boot. MariaDB closes a connection idle past `wait_timeout` (8 hours by default), which released the lock: a server up for more than 8 hours stopped writing. | The main connection sets its session `wait_timeout` to 31536000 seconds before it takes the lock, and boot fails if it cannot. The pool's connections keep the server's timeout and are replaced as above. | `c3db1e6c4` |
| Once the lock is truly lost (the database restarted or ended the session), nothing said so: `/health` answered ready and no log named the cause. | The first loan that finds the lock lost writes one status-log line, and the pool reports itself inactive, so `/health` answers 503. The server does not take the lock back by itself. | `69f168ed3` |

Tests, each failing without its fix:

- `run_sql_pool_interrupt_mysql.sh` (the real pool on a disposable MariaDB) gained an idle
  section: the server closes a pooled connection after 1 second, the next loan gets a working
  one with the lock kept, a refused reconnect keeps the slot, and the loan after it works. Then
  the owner's session is killed: the next loan is refused, the pool reports itself inactive,
  and the status log names the lost lock. On the old pool the section fails at the first loan;
  with only the probe fixed, at the refused reconnect; without the report, at
  `sql_pool_is_active()`.
- `run_mysql_idle_timeout_journey.py`, a new `make test-db` journey: `wait_timeout` is 3
  seconds; the server boots, a character is created and saved, and the server idles past the
  timeout twice. The lock holds, a save lands, the character quits, logs in and saves again,
  and the server shuts down cleanly. Without the fixes the starter kit (a command on the
  writer) never arrives; with `wait_timeout` at 20 seconds, the lock is gone after the idle.

The server does not take the lock back by itself after a database restart: the lock keeps a
second server off the database, and taking it back could overwrite what another server wrote
meanwhile. Restarting the game recovers.

### Critical-command failures name their cause (done)

A refused critical command raised `domain=critical_command action=integrity_failure
detail=operation metadata redacted`. The completion now carries its command's type, and the
alert's detail is `type=N error=N`: the type is the stable number `critical_command.h` assigns
(stored with every command), and the error is the refusal reason, an errno, a database error or
the command's own result code. The reporter allows numbers only in a detail, which keeps player
data out, so the type is not spelt out by name. `3b9886f1e`.

Tests: `test_critical_command_coordinator.py` refuses an auction command and checks that its
completion carries the type and the error; `test_critical_transaction_contract.py` pins the
alert.

### Repeated alerts are grouped (done)

The wizlog limiter keyed on the owner, item, event and full alert text, so alerts whose detail
varied were never grouped. It now keys on domain and action: the first alert of a pair reaches
the wizlog, the rest within 30 seconds are counted and reported with the next one after the
window, as `(suppressed=N age=Ns)`. The persistence log still records every alert. Owner, item
uid and event id fed only that key: `persistence_report()` and `persistence_alert()` keep them
in their signatures and no longer read them. Dropping them from the 122 call sites and the test
stubs was left out as churn that changes nothing. `7bccc5327`.

Tests: `test_persistence_severity.py` sends repeats with other details, owners and events and
gets one wizlog line; another action gets its own; with the window shortened in the extracted
reporter, the next line reports `suppressed=3`. Its severity cases now use one action each,
since they relied on distinct event ids to stay apart.

### `checked_snprintf()` names its call site (done)

`checked_snprintf()` and `checked_snprintf_runtime()` are macros passing `__FILE__` and
`__LINE__` to `checked_snprintf_at()` and `checked_snprintf_runtime_at()`, so none of the
call sites (about 570) changed and the format is still checked. A truncation reads `<file>:<line>:
checked_snprintf: output requires N bytes but destination holds M`, both in bytes with the
NUL; before, both were one short. `1c985b62c`. Found with it, in its own commit:
`checked_substitute_strings()` reported the same off-by-one sizes (`756e1c9f7`).

Tests: `test_safe_format.py` truncates into a 5-byte and an 8-byte buffer and checks both
reports, the first with its own line. Three harnesses with their own stub now define
`checked_snprintf_at()`. The pfile tool and the three `migrations/tools` binaries build.

### Logs rotate with a cap (done)

At boot `cycle_mud.sh` moves `logs/log/*`, `logs/player-log/*` and `logs/latency_trace.log`
into `logs/old-logs/<date>/`, then deletes the oldest generations until `logs/old-logs` fits in
`DURIS_LOG_ARCHIVE_MB` (1024 by default), always keeping the newest. The size cap is on the
archive, as the work item asked (rotate at boot, with a size cap): a running server's files grow
until the next boot. The pwipe's own player-log move went, since every boot does it. The latency trace goes to its file
only, no longer to stderr as well. `cff347888`.

Tests: `test_flatfile_launcher.py` boots with live logs and two old generations under a 1 MB cap:
the logs move into the new generation and only the oldest generation goes (on the old script it
fails at the move); `test_tick_latency_instrumentation.py` pins one dump, to the file.

### Debug noise behind a switch (done)

The `Locker save start`, `LockerToPFile` and `PFileToLocker` routine lines (`storage_lockers.c`)
and the per-shop `sql_restore_shopkeepers` boot line (`sql_player.c`) are written only when
`DURIS_PERSISTENCE_TRACE` is set. It is read once, like the corpse and zone-reset traces, and
documented with them in `CONFIGURATION.md`. The locker failure lines stay on. `77ecc8d27`.

Tests: `test_boot_log_hygiene.py` checks each routine line sits behind the switch and each
failure line does not; the shopkeeper population harness turns it on.

### `cycle_mud.sh` stop reports (done)

An exit above 128 is named by its signal (`killed by SIGKILL [137]`); 139 stays `crash`. The
boot email tested `/logs/old-logs/<date>/exit` and never attached the previous run's exit log;
it tests `logs/old-logs/` in the checkout. `060890586`.

Tests: `test_flatfile_launcher.py` runs the script's own stop-reason block for 0, 139, 137, 143,
134, 200 and 3 (on the old script 137 reads `unknown`), and pins the email's path.

### Found on the live boot (done)

The live check of Phase 4 on the local server (`./scripts/start_mud.sh --dev`) raised
`domain=shopkeeper_save action=dirty_save_failed` at every shutdown: four of the 544 shops
failed every save and stayed dirty, as they had on the merged master build. Each cause is fixed
in its own commit:

| Defect | Fix | Commit |
|---|---|---|
| A failed shopkeeper save logged only `reason=save_failed`. | The capture or codec result is logged with the shop. | `73ccbd06f` |
| Shops 4, 111 and 510: the stock capture refused any keeper whose mob does not run `shop_keeper`, and quest and tradeskill keepers run `world_quest` or `learn_tradeskill`. The save's validator already says identity is the shop's binding. | The capture no longer checks the procedure; its caller checks the binding. | `db503bf50` |
| Shop 521, and any player: a save refused a string over 4096 bytes, and five objects in the world have an extra description up to 8411 bytes (18016, 132677, 132705, 139095, 139149). Every save of whoever held one failed, a player included, with only a capture-failure counter to show for it. | A saved string may be 16384 bytes. Loads, the codec and the `TEXT` columns check the same constant. | `9d14a0d6f` |
| `make test-all` and `make test-db` wrote synthetic claims and dupes into the checkout's `logs/log/item_claims` and `logs/log/dupes`. | The three tests responsible run their harnesses from a temporary directory. | `52d3a84da` |

Tests: the shopkeeper save test checks the cause line; the capture contract fails if the
procedure check comes back; the item codec test round-trips an 8411-byte description and fails
if any string in `areas/obj/*.obj` passes the limit. Live, after the fixes: the `.env`
character saved holding object 139095, whose description failed shop 521's capture with
`limit_exceeded` before (a player holding it was not tried on the old build), and the next
shutdown saved all 544 shops, 4, 111, 510 and 521 included, with no alert.

### The gate on the branch head (done)

On `3b228a90c`, the code head with these records, run once each: `./scripts/format.sh --all
--check` (1030 files clean), `make test-all -j16 TEST_JOBS=16` alone (659 of 659, 464 s), then
`make test-db` (36 of 36, 196 s, with the new `idle_timeout` journey) and `npm test --prefix site`
(14 tests) side by side. Neither suite left `logs/log/dupes` or `logs/log/item_claims` behind. An
earlier run of the same gate on `77ecc8d27`, before the live boot's fixes, also passed (659, 36,
14). The backup-recovery container replay was not run: nothing here touches what the restore
qualifier runs.

The live check on the local server, through `./scripts/start_mud.sh --dev` on `duris_dev`:

- The boot moved the last run's `logs/log/*`, `logs/player-log/*` and `logs/latency_trace.log`
  into `logs/old-logs/<date>/`, and `logs/player-log` kept only its `.gitignore`.
- It wrote no `sql_restore_shopkeepers` or locker trace line (the boot before wrote 544
  shopkeeper lines) and no latency table to the console, while `logs/latency_trace.log` filled.
- `/health` answered `healthy`/`ready`; the `.env` character logged in, looked, saved, saved
  holding object 139095, and quit.
- A SIGKILL was reported as `Mud stopped, reason: killed by SIGKILL [137]`, and the launcher
  rotated the logs again and booted a healthy server.
- A SIGTERM ended it with `shutdown [0]` and "Normal termination of game"; all 544 shops saved
  and no persistence alert was raised.

### Phase 4 landed (done)

On 2026-10-02 !6 landed in `d6952d701`, one `--no-ff` merge of `6bba358b8`, the head the
review read. The review found nothing, so `persistence/phase-4-review-0` is the phase's only
tag and names what landed. Master had no commits the branch lacked, so the merge's tree is that
head's; its last two commits only add records to this file and the plan after the gate on
`3b228a90c`, so nothing was rerun for it. The merge also brought the work item close-out
(`6689c5f20`, the plan's Phases 4 to 8). No migration, so `duris_dev` needed no upgrade.

`fix/6-persistence-phase-4` and `fix/7-persistence-closeout` are deleted, and this worktree
continues on `fix/4-persistence-phase-5`, branched from master after this record. #6 stays open
for its server configuration items; its Status line now records what Phase 4 resolved.

## Phase 5 progress

Phase 5 ([plan](persistence-plan.md#phase-5-bugs-from-the-logs-4)) was done on
`fix/4-persistence-phase-5`, branched on 2026-10-02 from master `b7105b7d4`. Each item below
gets its record when it lands; an item without one is not done.

### Characters missing from their room's people list (done)

The cause was in both loads, `player_load_materialize()` and the legacy `restoreCharOnly()`:
each set `in_room` to the saved room without `char_to_room()`, so the character named a room
whose people list did not hold it. `enter_game()` read the room from `was_in_room` first and
reset `in_room` before `char_to_room()`, so a login was fine; every other use of a loaded
character was not:

- A character freed without entering the game ran `char_from_room()` on that room from
  `free_char()`. That logged `char_from_room: <name> (-1) not in room <r> (...) people list`,
  told the room's procedure the character left, and, for a mortal, took one from its zone's
  (or continent's) PvP misfire count for its side, which it had never been added to. Finger,
  the artifact owner checks, disguise, illusion, the website's character deletions, an
  account-menu back-out and the staff pfile scans all free a loaded character. Offline
  characters rent at inns, which is why 11 of the 19 lines in #4 named inn rooms.
- `load char <name>` put the loaded character in `character_list`, and `char_to_room()`, which
  refuses a character that already has a room, logged `refusing duplicate insertion` and left
  it there: in the game, listed in its saved room, missing from that room's people list.

Reproduced first, on the unfixed build with the `.env` account: `finger Ratgapp` logged
`char_from_room: Ratgapp (-1) not in room 63 (...) people list`, the line the 2026-09-30 log
in this worktree holds, and `load char Ratgapp` said he appeared while `look` did not show him.

Fix (`007b2893d`): a loaded character is in no room. The saved room stays in `was_in_room`
(the locker redirect writes only that), so `enter_game()`'s fallback to `in_room` and its
separate `RENT_CRASH` branch, which did the same as the default one, go, and so does `load
char`'s copy of `in_room` into `was_in_room`. A save of a loaded character that never entered
(the artifact owner's) finds its room through `calculate_save_room()`, which falls back to
`was_in_room`, so it saves the same room as before. Under `_PFILE_` the pfile tool has no
world (`world` is NULL, `real_room()` returns the vnum), so `restoreCharOnly()`'s locker check
is compiled out there instead of reading `world[vnum]`. No legacy pfile exists locally, so
`restoreCharOnly()` was compiled and its tool test run, but not fed a real pfile.

Found with it, in its own commit (`eb52ead25`): `camp()` wrote the home room into the
character `extract_char_after_terminal_save()` had just freed, for "the new nanny"; the menu
loads the character again from its save, so nothing read it.

Tests: the MariaDB game-loop journey (`make test-db`) sets the offline `Vexmora`'s
`last_room` to the god's room once `newchar` has stored it, then runs `finger Vexmora`, `load
char Vexmora` and `look`, and fails if any log holds `people list` or `duplicate insertion`.
On the unfixed binary it stops at `look`, Vexmora missing from the room.
`test_locker_boot_rooms.py` pins the redirect writing `was_in_room` only. Live on the fixed
build: Ratgapp stands in the room after `load char`, and neither line is logged.

Not this cause, and not claimed: #4's three `SanityCheck called from NumAttackers() for
<name> at NOWHERE!` lines, a living character at `NOWHERE` reached from combat code. The
loads do not produce one, and it was not reproduced.

### IPv6 in `log_entries` (done)

Migration `0036_log_entries_ipv6` widens `log_entries.ip_address` from `VARCHAR(15)` to
`VARCHAR(45)`, as `account_ips` has. Its guard reads the column's length and issues no
`ALTER` once it holds 45, and its verifier checks `VARCHAR(45) NOT NULL DEFAULT ''` on both
engines (MariaDB reports the empty default as `''`). `sql_log()` keeps 45 bytes. The fresh
bootstrap holds the new shape; the legacy upgrade path (`run_migration.sh` still creates 15)
reaches it through 0036, and `run_legacy_migration_mysql.sh` compares the two. The runtime
head, the history checksum and both engines' fingerprints move: the fingerprints were measured
by running `run_runtime_compatibility_mysql.sh` on `mysql:8.0` and `mariadb:10.11` with the
old values (each failed, printing the actual one), then written with the measuring script's
own `update_contract()`, and both legs passed. `7ff4462f7`.

A socket address prints at most 39 characters (`inet_ntop()` writes dotted IPv4 only for a
mapped address, which `new_descriptor()` strips to IPv4); 45 also holds the embedded-IPv4
form, as the work item asked.

**An existing database needs `python3 scripts/migration_runner.py run` before this binary
boots (COMPAT-E002 otherwise).** The local `duris_dev` was backed up first
(`~/.local/share/duris-issue-7/duris_dev-before-0036-20261002-213628.sql.gz`), then migrated:
all 159,541 rows kept, a second run and a rerun of the apply file did nothing, and
`verify_runtime_compatibility.sh` passed.

Tests: the save-claim MariaDB harness writes a 45-character IPv6 address through
`log_entry_repository_apply()` and reads it back whole; on master's schema strict mode refuses
the row. The three tests that pin the head (`test_immutable_migration_runner.py`,
`test_runtime_boot_compatibility.py`, `test_collector_catalog_schema.py`) name 0036.

Live, the real path: in a private network namespace (`unshare -rn`, its loopback given
`fd12:3456:789a:bcde:f012:3456:789a:bcde`, the database reached through a socat bridge), the
server listened on `::1` and the `.env` account logged in from that 39-character address and
quit. Its `Entered Game` and `Quit Game` rows hold the whole address; the old code kept 15
characters. The namespace is how a long address was had without opening the server to a
network.

### A zone-story state above 64 KiB (done)

`9fafc10dd` queued the save on the writer, formatted at its real length, so `qry()`'s 64 KiB
buffer no longer applies; nothing stored a state that large. `zone_story_state_mysql_harness.cpp`,
run by `run_player_save_claim_mysql.sh` on the same schema, stores 96 KiB, with quotes,
backslashes and newlines for the escaping to lengthen, through
`sql_zone_story_quest_state_save()`, the real `sql_queue()` and the real `sql_execute()`
(the writer stub runs each job at once on the harness's connection), and reads it back with
`sql_zone_story_quest_state_load()`. `b131126d0`.

The test cannot fail on the save before `9fafc10dd`: that save called `qry()`, which the
harness does not link. It pins the path the fix made.

### The gate on the branch head (done)

On `b131126d0`, the code head, run once each: `./scripts/format.sh --all --check` (1031 files
clean), `make test-all -j16 TEST_JOBS=16` alone (659 of 659, 470 s), then `make test-db` (36
of 36, 187 s, the `game_loop_queries` journey and the `player_save_claim` leg extended, and
`legacy_migration` running 0036's `ALTER` on a legacy-upgraded schema) and `npm test --prefix
site` (14 tests) side by side. Neither suite left `logs/log/dupes` or `logs/log/item_claims`
behind. `run_runtime_compatibility_mysql.sh` passed on `mysql:8.0` and `mariadb:10.11` with
the new fingerprints. The backup-recovery container replay was not run: nothing here touches
what the restore qualifier runs.

The live check on the local server, through `./scripts/start_mud.sh --dev` on `duris_dev` at
head 0036: `/health` answered `healthy`/`ready`; the `.env` character fingered and loaded
Necrotest, whose saved room the 2026-09-30 log named, and Necrotest stood in the room with no
desync or refusal line logged; the character quit, and a SIGTERM ended the server with
`shutdown [0]` and "Normal termination of game", no persistence alert raised.

### Review round 1 (MR !7)

The review read `persistence/phase-5-review-0` (`74b93be72`). It found three defects: two from
this phase and one older one on the same path, a save of a character loaded off the loop.
Each is fixed in its own commit on `fix/4-persistence-phase-5`, with a test that fails without
it. The fixed head is tagged `persistence/phase-5-review-1`.

| Finding | Fix | Commit |
|---|---|---|
| 1. P1: a loaded artifact owner is now in no room, but `poof_artifact()` still made it shout, and `do_shout()` reads `IS_ROOM(ch->in_room, ...)` unchecked: `world[-1]`. An ASan build aborted with a heap-buffer-overflow in `do_shout()` from staff `artifacts poof` and from the artifact-expiry job with nobody logged in. | The owner's two messages and the shout run once, after the switch, and only for an owner in a room. An offline owner has no one to tell; master had it shout "Ouch!" to the game while logged off. `test_artifact_offline_owner_loads.py` pins the guard. | `5f3abdff4` |
| 2. P2: `restoreCharOnly()` stopped setting `in_room`, but `purge pfiles` and `lookup pfile` take the character from `mm_get()`, which zeroes it, so `in_room` was 0, a real room. `purge pfiles` frees every character it restores, and `free_char()` ran `char_from_room()` on room 0 for each: the desync this phase fixes, moved to room 0. Its early failure exits always did. | `restoreCharOnly()` sets `in_room` to `NOWHERE` before its first failure exit. `test_pfile_tool.py` pins it. | `52ecdbd67` |
| 3. P1, older than this phase: an offline load reads no pets, but every save of the character it made wrote all components, so `capture_pets()` sent no pets and `apply_pets()` deleted every stored one without items in custody. `load char` and any save after it, the expiry job's save of an offline owner, and staff artifact poof, swap and files all did it, silently. | The load notes the components it did not read (`unloaded_components`), and `player_save_pipeline_request()` leaves them out of what it marks. A full load reads every component and a new character was loaded from nothing, so their saves are unchanged. The MariaDB game-loop journey stores a pet for the offline Vexmora, loads and saves it, and checks the pet is still there. | `5b451088f` |

Left out: the review also suggested checking `oroom >= 0` before `IS_MAP_ROOM(oroom)` in
`ac_can_see()`. Traced, that alone would not have made the shout safe: `PERS()` reads the
shouter's room through `CAN_NIGHTPEOPLE_SEE()` right after. With finding 1 fixed, nothing
traced hands either a target in no room from a mortal viewer. The character an account loads
to confirm its deletion waits on its descriptor at `NOWHERE`, as a new character in creation
always did, and only staff commands (`users`; `where` checks `in_room` first) look at those.

Verification for this round:

- Each new test fails on `74b93be72`: the two contract tests find two unguarded shouts and no
  `NOWHERE` in `restoreCharOnly()`, and the game-loop journey, on a build with findings 1 and
  2 fixed but not 3, ends with "the loaded character's save left 0 of its 1 pet".
- Live, on an ASan/UBSan build (`scripts/build-san.sh`) against the local `duris_dev`, with the
  `.env` account: Veridian ran `load obj 425`, `load char Ratgapp`, `give avenger ratgapp` and
  `force ratgapp save`, the server restarted, and the artifact's timer was set in the past.
  Before the fixes the expiry job aborted the server in `do_shout()` about 105 s after boot;
  with them it poofed 425 from the offline Ratgapp, saved him and cleared the row, with no
  sanitizer report. `purge pfiles` over a list naming a missing pfile logged `char_from_room:
  (null) (-1) not in room 0 (The Void) people list` before and only `free_char called with no
  name. room: (-1)` after. `load char Zxat` and `force zxat save` deleted both of Zxat's stored
  pets before and kept them after. `duris_dev` was dumped before each session and restored
  from the dump after it.
- The gate, on these fixes with this record: `./scripts/format.sh --all --check` (1031 files
  clean); `make test-all -j16 TEST_JOBS=16` alone (659 of 659, 545 s); then `make test-db` (36
  of 36, 196 s, the `game_loop_queries` journey keeping Vexmora's pet). Neither suite left
  `logs/log/dupes` or `logs/log/item_claims` behind. After the gate a duplicate assertion was
  dropped from `test_pfile_tool.py`, which was run again on its own. Not run:
  `npm test --prefix site` (nothing under `site/` changed), `run_runtime_compatibility_mysql.sh`
  (no schema change: `unloaded_components` lives in memory) and the backup-recovery replay
  (nothing the restore qualifier runs changed).

### Phase 5 landed (done)

On 2026-10-03 !7 landed in `218d0640b`, one `--no-ff` merge of `0d3fcd4ee`, the review round 1
head (`persistence/phase-5-review-1`). Master had no commits the branch lacked, so the merge's
tree is that head's, gated in the round ([record](#review-round-1-mr-7)), and nothing was rerun
for it.

Migration 0036 comes with it: a database must run `python3 scripts/migration_runner.py run`
before the merged binary boots. The local `duris_dev` has been at 0036 since the phase
([record](#ipv6-in-logentries-done)).

`fix/4-persistence-phase-5` is deleted, and this worktree continues on
`fix/3-persistence-phase-6`, branched from master after this record. #4 is closed: sections 1
to 3 are fixed and tested here, section 4 was fixed by the reset, and section 5's decision is
recorded (a restored player corpse keeps refreshing its decay). Its three `SanityCheck called
from NumAttackers() ... at NOWHERE!` lines were not reproduced and are not the loads'
([record](#characters-missing-from-their-rooms-people-list-done)); a new work item takes them
if they recur on this build.

## Phase 6 progress

Phase 6 ([plan](persistence-plan.md#phase-6-backups-3)) was done on `fix/3-persistence-phase-6`,
branched on 2026-10-03 from master `2d58826c4`. Each item below gets its record when it lands;
an item without one is not done.

### Each generation verified once (done)

`generations()` called `verify()` on every stored generation, hashing each file and
decompressing and scanning each dump, and `total_size()` hashed every file to count its bytes.
Every run paid for the whole history: the minute's `status`, each hourly backup (twice: before
the capture and in the rotation) and each replication.

`generations()` now reads each manifest (`read_manifest()`, the first half of the old
`verify()`), and `total_size()` takes sizes from the file system through `walk()`, the
secure walk `inventory()` now shares. A generation is verified in full when it is published,
by `finalize` (which can follow a publish that stopped before its check; the old `finalize`
verified it through `generations()`), when it is restored (the newest was verified only
through `generations()` before) and before it is pruned. The drill verifies every stored
generation before it restores the newest, so a corrupted older one fails the drill, and
`status --require-drill` reports the overdue drill. `9e1bca3d8`.

Measured with copies of a real local generation (the 31 MB `duris_dev` dump) in a scratch
root: `status` took 1.16 s of CPU with 1 generation and 43 s with 40 on the old code, and
0.03 s and 0.04 s on the new one, reporting the same bytes. A real backup of `duris_dev` into
that root of 40 took 97.9 s of CPU on the old code and 13.7 s on the new one, the same as into
the local root of 2 (13.6 s); the dump and the one verification of what it publishes are what
is left. #3's staging dumps are about five times larger, hence its 3 to 4 CPU-minutes a run.

Tests (`test_persistence_backup.py`): `status` with 1 and with 40 generations runs with
`digest()` and `validate_dump()` failing if called; `finalize` refuses a newest generation
corrupted after a publish that stopped before its check, and `status.json` stays on the
previous one; the drill refuses a corrupted older generation and a restore a corrupted newest,
both before any candidate exists, while `status` passes. Each fails on the old code, and with
any one of the new `verify()` calls taken out the test that pins it fails.

### Failure records name their cause (done)

`main()` printed `operation_failed` for every unexpected exception, and `replication_result()`
recorded `replication_failed` for every replica failure, its own `BackupError` code included.
`failure()` now builds a record's cause: a `BackupError` keeps its code; anything else gives
`operation_failed`, the exception's class as `error` (with its module when not a built-in, so
`shutil.Error` or `subprocess.TimeoutExpired`) and its message as `detail`. Two kinds keep less,
so that nothing private reaches the journal: an OS error keeps only its `strerror`, since its
file name can be a flat-file path naming an account; a subprocess error keeps no message,
since `TimeoutExpired` quotes the command line with the database user and host (the password
travels in `MYSQL_PWD`, never in arguments). The replica's failure is recorded the same way as
`replica_error` in `status.json` and in the run's output, which did not carry it at all.
`5ba50200b`.

Tests: `test_persistence_backup.py` runs `main()` with a backup raising a `BackupError`, a
`FileNotFoundError` whose file name names an account, a `TimeoutExpired` whose command line
names a user and host, and a `KeyError`, and compares each whole record, so nothing else can
appear in it; `test_backup_review_remediations.py`'s replication test fails the replica with
`ENOSPC` and checks `replica_error` in the result and in `status.json`. Both fail on the old
code.

### A scheduled backup's pending replication (found, done)

Found while tracing the schedule for item 2. `schedule` required its backup's result to be
`ok` and called anything else `authority_not_initialized`, so a generation published locally
whose replica failed was reported as an uninitialised authority, and the replica's cause was
lost with it. The schedule now prints the `replication_pending` result, with its replica error,
and exits 1 as `backup` does; it leaves its deadline alone, so the next minute's backup sees
the pending receipt and retries only the replication. `879356579`.

Test: `test_backup_review_remediations.py` runs `schedule` with the replica failing (the
pending result and its cause are printed and `schedule.json` is not written), then with it
working (the same generation completes and the deadline is written). On the old code the
first run printed `authority_not_initialized`.

### The RPO alarm while backups fail (done)

While every backup failed, `schedule` never reached `status()`, so `rpo_exceeded` never fired.
The schedule moves into `schedule()`, and when its backup fails, `failed_backup()` reads the
newest generation's manifest (no lock: it only reads, and a broken root has already failed the
backup with the same code). Past the RPO, or with no generation at all, the record's code is
`rpo_exceeded` with `age_seconds` and the backup's own failure under `backup`; within it, the
record is the backup's failure with `age_seconds` added. `main()` now prints every failure
record, raised or returned, the same way. `1265b3ff9`.

Test: `test_persistence_backup.py` fails a scheduled backup with `ENOSPC` an hour after the
last generation, past the RPO, and with no generation, and compares each whole record. All
three fail on the old code.

### Receipts that change during the capture (done)

The capture listed and hashed the receipt directory, copied it, required the copy to match the
listing, ran the authority capture, and then required the directory to match the listing
again, so a receipt written during the dump failed the run (`journal_changed_during_authority_capture`).
Traced further, a receipt write failed it too: `flatfile_atomic_write()` writes to
`.<pid>.receipt.tmp.<pid>.<n>` in the same directory and renames it over the receipt, and the
listing refused that name (`journal_filename`), or lost it to the rename before hashing it
(`FileNotFoundError`, an `operation_failed`). Nothing removes one a crash leaves behind, so a
crash during a receipt write would have failed every backup after it.

The comparison bought no consistency: a receipt is written at once, and the wallet it charges
reaches the database with a later save. What matters on a restore is which way they disagree.
A receipt older than the database can say `prepared` for a charge the database holds, and the
player's next login charges it again; a receipt newer than the database says `paid` for a
charge the database lacks, and the identification is free, the way a crash loses money rather
than paying it twice. So the receipts are now copied after the authority capture (the dump
snapshots at its start, the flat-file copy under its locks), and the copy is checked on its own
instead of against the directory: a rename replaces a receipt whole, so each copied receipt is
one whole version. The writer's temporary files are not copied (`RECEIPT_WRITE`). `copytree()`
keeps symlinks as links, so the copy's own check still refuses one, as the old listing of the
directory did. The check that `CRITICAL_COMMAND_JOURNAL_DIR` matches the policy moves into
`backup()` before the capture, so a mismatch still costs no dump. `8277ddc64`. Review round 1
found that copying last does not cover a payment begun during the capture, whose paid marker
can lag its charge, and its fix refuses one ([record](#review-round-1-mr-8)).

Tests (`test_persistence_backup.py`): in both modes, with a writer's temporary file in the
directory, a receipt rewritten during the authority capture is published as rewritten, and the
temporary file is left out; it pins the writer's name format in `flatfile_store.c`. On the old
code the temporary file failed it with `journal_filename`, and without it the rewrite failed it
with `journal_changed_during_authority_capture`. A policy naming another receipt directory than
`CRITICAL_COMMAND_JOURNAL_DIR` fails before the authority capture is called.
`test_backup_review_remediations.py` adds a symlinked receipt, refused as `symlink_rejected`,
which fails with `copytree()`'s default of following links.

### Live checks on the local database (done)

Run with the `.env` account's `duris_dev` and the local backup policy, on the code head:

- `./scripts/backup_pfiles.sh` published a generation and pruned one by retention (13.6 s of
  CPU), and `status` answered in 0.04 s. `schedule` with no deadline ran a backup and wrote
  `schedule.json`; run again, it answered with the status.
- With a copy of `.env` holding a wrong database password, a scheduled backup within the RPO
  printed `{"age_seconds": 92, "code": "subprocess_failed", ...}`, and with a 60-second RPO
  `{"age_seconds": 81, "backup": {"code": "subprocess_failed"}, "code": "rpo_exceeded", ...}`.
- The game's receipt writer: four loops of `persistence_restore_fixture seed-receipt` (the
  integration test's fixture, writing through `locker_receipt_write()` and
  `flatfile_atomic_write()`) rewrote one receipt about 45,000 times in a scratch receipt
  directory while real backups of `duris_dev` captured it. On master's script 5 of 5 backups
  failed, 3 with `journal_filename` (a temporary file listed) and 2 with
  `journal_changed_during_capture`; on the new one 5 of 5 published, and each retained
  generation's receipt passed `qualify_flatfile_restore --receipts`, the production decoder.

### The gate on the branch head (done)

On `6537ac919`, the head with every record above, run once each: `./scripts/format.sh --all
--check` (1031 files clean); `make test-all -j16 TEST_JOBS=16` alone (659 of 659, 435 s); then
`make test-db` (36 of 36, 183 s) and `npm test --prefix site` (14 tests; `docs/` changed).
Neither suite left `logs/log/dupes` or `logs/log/item_claims` behind.

The backup-recovery job (`.github/workflows/backup-recovery.yml`), which this phase's changes
call for, was replayed in a privileged `ubuntu:24.04` container on a clone of `6537ac9`: both
backends built, the four policy and filesystem tests passed, and the root-only
`test_persistence_backup_integration.py` passed 5 of 5 (57 s), among them the flat-file
generation with a real receipt restored and qualified, and the MariaDB dump restored into a
private database and booted in an isolated namespace. Not run:
`run_runtime_compatibility_mysql.sh` (no schema change) and CodeQL and Trivy (nothing they
check changed).

### Review round 1 (MR !8)

The review read `persistence/phase-6-review-0` (`7b7b247f9`). It found three defects, all
from this phase; each reproduced on that head with a test, and each is fixed in its own
commit on `fix/3-persistence-phase-6`. The fixed head is tagged `persistence/phase-6-review-1`.

| Finding | Fix | Commit |
|---|---|---|
| 1. P1: copying the receipts after the authority does not keep a `prepared` receipt from being published with its charge. A bank payment queues its debit and the player's save at once while the paid marker is written by a worker that can lag or fail, so a payment begun during the capture could be in the snapshot while its receipt still said `prepared`, and the restored player's login charged it again; master's comparison refused that interleaving. | Before the authority capture the backup lists the receipts still waiting on their payment (`waiting_receipts()`: any whose header does not say paid, failed or delivered), and every waiting receipt in the copy must have been waiting, unchanged, then; otherwise the run fails with `receipt_payment_in_flight` and the next run takes it. Settled changes still do not fail it. An unchanged waiting receipt charged during the capture with its paid marker stalled past the copy is not caught, as master did not catch it either: it is the moment in which a crash also charges twice (`locker-identification.md`). In every dangerous case this refuses whatever master refused. | `a6cb01709` |
| 2. P2: the receipt directory was copied before its size checks, so a large file (an older server's `critical-command.journal` has no bound) could consume the free-space reserve or the budget before the capture failed; master refused it before copying. | `copytree()` copies through a function that holds each file to the budget and the reserve before writing a byte of it, which also covers growth after any listing. | `afb181b4b` |
| 3. P2: with `generations()` reading manifests only, a backup that found its last generation's replication pending completed it unchecked; under a policy whose replica was then removed, a generation corrupted since its publication was marked `ok`. | The retry verifies the generation first, as `finalize` does. | `a6741ccf9` |

Also corrected with finding 1: `BACKUPS.md` and the plan's item 3 no longer say that copying
last alone keeps a restore from charging twice, and `locker-identification.md` no longer says
transient files fail the capture (wrong since item 3).

Verification for this round:

- Each new test fails on `7b7b247f9`: a prepared receipt written during the authority capture
  is published in both modes; the 1 MiB legacy journal is copied whole before it is refused,
  and passes outright with 1.5 MiB free against a 1 MiB reserve; the pending retry marks the
  corrupted generation `ok`. The test for finding 1 pins the header layout the backup reads
  (`locker_receipt.c` writes the state at byte 5, `prepared` first) and keeps an unchanged
  waiting receipt publishable.
- A receipt written by the native encoder (`persistence_restore_fixture seed-receipt`) reads
  as settled, and with its state byte set to `prepared` as waiting.
- The live writer check again, on the fixed code: four loops of `seed-receipt` rewrote a paid
  receipt about 33,600 times while 5 of 5 real backups of `duris_dev` published, and each
  retained receipt passed `qualify_flatfile_restore --receipts`.
- The gate on `09e267fff`, the fixed head with this round's record, run once each:
  `./scripts/format.sh --all --check` (1031 files clean); `make test-all -j16 TEST_JOBS=16`
  alone (659 of 659, 615 s); `npm test --prefix site` (14 tests); and the backup-recovery job
  replayed in the privileged container on a clone of `09e267f` (the four policy and filesystem
  tests, and `test_persistence_backup_integration.py` 5 of 5). Not run again: `make test-db`,
  which runs nothing these fixes touch, and passed on the review's code head
  ([record](#the-gate-on-the-branch-head-done-3)).

### Phase 6 landed (done)

On 2026-10-03 !8 landed in `1a4b15f9d`, one `--no-ff` merge of `086cac326`, the review round 1
head (`persistence/phase-6-review-1`). Master had no commits the branch lacked, so the merge's
tree is that head's, gated in the round ([record](#review-round-1-mr-8)), and nothing was rerun
for it. No migration and no change to the backup policy's format, so neither `duris_dev` nor
the local policy needed anything.

`fix/3-persistence-phase-6` is deleted, and this worktree continues on
`fix/5-persistence-phase-7`, branched from master after this record. #3 stays open for its
server configuration (whether a server runs restore drills, keeps an off-host replica and
skips the pre-boot backup); its Status line now records what Phase 6 resolved.

## Phase 7 progress

Phase 7 ([plan](persistence-plan.md#phase-7-game-loop-performance-5)) is being done on
`fix/5-persistence-phase-7`, branched on 2026-10-03 from master `1c5a53de9`. Each item below
gets its record when it lands; an item without one is not done.

### Unnamed callbacks (done)

`lib/misc/event_names` held only global functions (`nm ... | grep " T "`), and its `sed` cut
each name at its first parenthesis, so a callback in an anonymous namespace
(`(anonymous namespace)::community_spellup_event`) lost its whole name. The server has seven
static event callbacks (`sp_hour_event`, `kingdom_gather_tick`, `kingdom_upkeep_tick`,
`kingdom_harvest_tick`, `kingdom_node_reload_event`, `event_deferredTerminalSave`,
`community_spellup_event`); each logged as `unknown function`.

Both launchers (`cycle_mud.sh`, `gdbdms`) now write the file with `scripts/event_names.sh`,
which lists local (`t`) and weak (`W`: inline functions, lambdas in inline variables)
functions with the global ones, drops `(anonymous namespace)::` and every parameter list, and
keeps one token per name, so no line is malformed. A lambda in `do_look()` reads
`do_look::{lambda#1}::_FUN`. The loader takes weak symbols. The file goes from 7,365 names to
26,169. `4df5e1018`.

Tests: `test_event_name_registry.py` builds the names of its own harness with the script and
looks up a global, a static, an anonymous-namespace, an inline and a lambda callback. With
the old pipeline the static one has no name; with the old loader the weak lines are
malformed. The game loop budget journey (below) writes the file as the launchers do and
fails if the event analytics or a slow-event record names an `unknown function` over a
full-world run.

### The game loop budget journey (done)

`test_mysql_game_loop_budget_journey.py` (in `make test-db`, about 3 minutes) is the
measurement and the pin for item 1. It boots the full world on a disposable MariaDB with
the event analytics on and the launcher's names file. Eight mortals on their own accounts
play side by side (`look`, `inventory`, `score`, `equipment`, `who`, `time`, `weather`,
`save`, one line every half second), camp out with `quit`, enter again, are brought to an
inn by a god and `rent`, and enter again; the god rents with 88 items. The run lasts to the
end of the 300-pulse window that holds the first hourly event.

It reads the loop's own records, not a client's clock. The budget is one pulse, 250 ms:

- the hourly event ran, by its `NEVENT ANALYTICS CALLBACK` line, inside the budget;
- no `COMMAND OP SLOW` names a `rent` or a `quit` past it;
- no `MUD TICK TOOK TOO LONG` pulse ran past it in its event pass or in its activity pass,
  where a camp ends;
- no `NEVENT BUDGET` pulse deferred events inside its 25 ms time budget;
- no callback is named `unknown function`;
- every camp and every rent is in `log_entries` after the shutdown.

A slow pulse anywhere else is printed, not judged. The journey first failed on any pulse
past 250 ms; in one of four runs beside the other database tests a single `score` took
346 ms, with nothing else slow in the run, and neither ten MariaDB containers starting and
stopping around a run by itself nor a second suite run repeated it. The loop had lost the
CPU in the middle of a command, which says nothing about a rent, a camp or the hourly
event.

It prints the latency trace's tick, event, command and activity times, the deferred and late
events and the twelve costliest callbacks. `--players N --hours N` scale it; the numbers
below are from `--players 30 --hours 2`. `cb5ceaed9`, `69dbf4886`, `a99782abb`.

Three things the fixture needed: the password worker queues 16 hashes and refuses the rest
(`Password service is busy`), so at most 8 characters are created at once; a camp is refused
in the room north of the start, so the mortals do not move; and the default camp takes nine
short affect updates (about 140 s), so `camp.timer` is 2, as in the full-world boot test.

### The measurement (done)

Thirty mortals and a god, 900 pulses (two hourly events), on this machine (16 cores,
otherwise idle), production profile. "Before" is `1c5a53de9`, the code this phase started
from, at `-Og`; the other two columns are the phase's code at `ca0a6810a`, built at `-Og`
(`EXTRA_CFLAGS=-Og`) and at `-O2`. One run each, times in microseconds:

| | Before, `-Og` | After, `-Og` | After, `-O2` |
|---|---|---|---|
| Slowest pulse | 1,186,017 | 49,866 | 36,625 |
| Mean pulse | 8,070 | 6,560 | 6,356 |
| Slowest event pass (`ne_events`) | 1,183,008 | 25,625 | 26,928 |
| Mean event pass | 6,053 | 4,558 | 4,466 |
| Slowest command sweep (the rents) | 34,647 | 32,218 | 22,702 |
| Mean command sweep | 995 | 989 | 927 |
| Slowest activity pass (the camps) | 4,875 | 8,008 | 3,689 |
| The hourly event, slowest | 1,181,521 | 8,849 | 6,874 |
| `MUD TICK TOOK TOO LONG` | 1 | 0 | 0 |
| Pulses that deferred events | 68 (63 inside the time budget) | 2 (none inside) | 3 (none inside) |
| Events run 1 pulse late | 138,545 | 1,340 | 2,406 |
| Events run 2 to 3 pulses late | 15,908 | 0 | 0 |

What it shows, against #5's figures:

- **`rent` and `quit`** no longer wait: every rent (31, the god's with 88 items) and every
  camp ran inside a command sweep or activity pass of at most 35 ms, against a median of
  1,871 ms and a maximum of 5,002 ms for `rent` in #5. No `COMMAND OP SLOW` (50 ms) was
  logged in any run.
- **The hourly event** still stalled the loop once after every boot, for 1.2 to 1.6 s over
  five runs (#5 measured 1.7 to 2.0 s): see the shop walk below. Later hours took about
  50 µs.
- **The event debt** was not load: it was the callback limit ending pulses early. See the
  callback limit below.
- **What is left in `ne_events`**: `event_mob_mundane` is about 40% of the event time
  (555,000 calls in 900 pulses, 3 µs each), then `event_balance_affects`,
  `event_spellcast`, `event_mob_proc` and the sliced `generic_char_event` (up to 8 ms a
  slice). No other callback reaches 7 ms.
- **`-O2`** takes 3% off the mean pulse and 2% off the mean event pass: the loop spends its
  time following pointers through the world, which the optimiser does not shorten. The
  slowest pulse and command sweep were lower at `-O2` in these single runs.

### The hourly event's shop walk (found, done)

`event_another_hour()` saves the shops marked dirty, and a boot marks every shop dirty (the
world singleton pass and the restore each do). For each dirty shop
`find_shopkeeper_for_dirty_save()` walked the whole character list to find the keeper: 544
shops against about 69,000 characters. Timed inside the loop on a full-world boot, the first
hourly save took 1.65 s, 1.63 s of it in the walks and 0.02 s capturing the stock. The
persistence reset had moved the write to the writer; the walk stayed on the loop.

`sql_save_dirty_shopkeepers()` now collects the shops that are due and finds all their
keepers in one walk, keyed by keeper template (`find_shopkeepers_for_dirty_save()`). The
same save takes about 9 ms. `4f0dfad67`.

Tests: `test_shopkeeper_save_runtime.py` counts the steps along the character list (two
dirty shops and two characters take two steps; the old code took four), and the journey
fails on the old code (`the hourly event took 1229344 us`).

### The maintenance scheduler's retry (found, done)

In every measurement run one server thread used a full core. Stacks taken under `gdb`
showed the maintenance scheduler's worker in `persist_state()`: when the state file cannot
be written it marked the state dirty again and retried at once. The full-world test
fixtures have no `bin/server/` under their run directory, so every such server spun; on a
real server a full disk or a missing directory would do the same. The worker now waits a
second, or for the next job, before it tries again. The journey sets
`MAINTENANCE_STATE_FILE`, so its scheduler works as a real server's does. `7ddcdfae9`.

Test: `test_maintenance_scheduler.py` points the state at a missing directory and requires
under 100 ms of CPU in 300 ms; the old worker used all of it.

### The event callback limit (found, done)

An event pulse ended at 25 ms or at 4,000 callbacks, whichever came first.
`ARCHITECTURE.md` says the time budget is meant to be the binding limit, and the count was
raised twice for that (1000, 2000, 4000), but on a full world a callback costs 1 to 3 µs, so
the count ended pulses at a tenth of the time budget: one pulse deferred 16,732 events after
2.6 ms. In the "before" run 65 of the 72 pulses that deferred events had time left, and
about 167,000 of 1.57 million events ran one to three pulses late. That is #5's standing
event debt (111,846 `NEVENT CATCHUP` and 71,914 `NEVENT BUDGET` lines in five days).

The default count limit is now none (`NEVENT_MAX_CALLBACKS_DEFAULT` 0), so time alone ends a
pulse; `DURIS_NEVENT_MAX_CALLBACKS` still sets a count. Measured on the same load before the
default changed (development build): with the limit, 70 deferring pulses, 150,733 events one
pulse late and 16,495 two to three; without it, 4 deferring pulses, all at the time budget,
and 2,635 events one pulse late, with the slowest and the mean pulse unchanged (42 ms and
6.5 ms against 52 ms and 6.6 ms). `12256b9cd`.

Test: the journey fails if a pulse defers events inside its time budget.

### The production build at `-O2` (done)

`HARDENING_FLAGS` put `-Og` in every profile. The development profile keeps `-Og`, the
production profile compiles at `-O2`, and the hardening flags apply to both. `ca0a6810a`.

The warnings that follow values (`-Wnull-dereference`, `-Wmaybe-uninitialized`,
`-Wformat-truncation`, `-Wstringop-overflow`, `-Warray-bounds`, `-Wstrict-overflow`) see
further at `-O2`, through inlined code: the first `-O2` build reported 84 diagnostics at
about 60 sites that the `-Og` build does not. The warning profile allows no exception, so
each is resolved:

| What `-O2` reported | Resolution | Commit |
|---|---|---|
| `setbit char <name> savthr` copied five shorts over the character's five one-byte saving throws: it ran on into the five conditions after them and stored the bytes of the first values. Two `snprintf()` calls in `setbit` gave a 1024-byte buffer a 65536-byte bound, and the on/off argument was read without a value when not given as a number. | Each throw is set, bounded to a byte, and one not given keeps its value; the bounds and the start value are corrected. | `fd43366b1` |
| `event_embrace_death()` returned whenever the character had the affect and used the missing one when it had none: `9f77d0cda` had inverted the check when it flattened nested ifs. The bonus never followed the wounds and never ended. | It returns when there is no affect, as before that commit. | `8f7012086` |
| Six uses of a pointer or value that is not there: the mob loop's report of an NPC without npc data read that data; `artifact_update_sql()`'s repair of an artifact inside no container left the pointer it then used NULL; a quest action removing a tag the instance lacks went past the list's end; `notch_achievement()` used an unchecked `apply_achievement()`; `do_breathe()` tested `arg \|\| *arg`; `poll_get_by_id()` returned a poll with only its id initialised. | Each path is guarded or initialised. | `f9a09eb0d` |
| Writes that can truncate: the world persistence report's query-site line, the armor list, the guild frag list and default titles, identify's ability list, the kingdom guard class lists, an auction item's ability lists, the forge recipe's flux line, the PROXY header's address and the poll's time remaining. | `checked_snprintf()`, `checked_appendf()` / `APPENDF()` and `strlcpy()`, the helpers the code base has for it; the poll prints ints. | `e4aaebbb0` |
| A null dereference in `check_flags()`. | Nothing calls it; removed. | `50ed401a9` |
| About 30 sites that did not misbehave but did not say why: `GET_PLYR()` and the morph steps (through `MORPH_ORIG()`, whose other arm is NULL), the walks to an outermost container, `do_epic_share()`, the locker grant, the level notice, the password worker, the recovery store, `do_fire()`'s messages, a save file's witness offset, `act()`'s substitution, and four standard-library calls (a vector used as a queue, a path built backwards, a sort and a resize). | Each states what made it safe, or does the same through code the library warnings accept. | `e675d94f5` |

Both backends (`mariadb`, `flatfile`) and the `pfile` tool build clean at `-O2`.

`make test-all` builds the production profile too, so a later `-O2` report fails the gate:
`make build-production` compiles it into `bin/objects/server/mariadb/production` and
`bin/server/production/dms_new` (67 s from clean on 16 cores, then only what changed), and
`bin/server/dms_new` stays the development build the tests run.

Tests: `test_setbit_saving_throws.py` and `test_embrace_death_event.py` run the real
functions and fail on the old code; `test_binary_layout.py` checks each profile's level in
a dry run; `test_root_test_harness.py` pins the production build in `test-all`. The `-O2`
server's own run is the measurement above: the journey passed on it with 31 characters
created, camped and rented.
