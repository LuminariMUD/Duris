# Plan: work items #10, #11, #13, #14 and #17

Written 2026-10-05 against `master` at `40a0667c4`. One phase per work item. The owner
locked every recommendation the same day, and the points that were still worded as "check,
then decide" were settled against the code. Nothing is left to decide. This file is a
working note: delete it when the last phase lands.

## Status

Updated 2026-10-05. A new session starts here, then reads the phase it continues.

| Phase | Item | State |
|---|---|---|
| 1 | #10 | Landed on 2026-10-05 in `7fdbb20fe` (!11). |
| 2 | #13 | Not started. It is next, on a new branch from `master`. |
| 3 | #11 | Not started. |
| 4 | #14 | Not started. |
| 5 | #17 | Not started. |

## Are the items still valid?

All five are. Every code claim in them was read again at `40a0667c4`. No file under `src/`,
`tests/`, `migrations/` or `scripts/` has changed since `dc8357143`, the commit the log
review ran on, so the observations in #10, #11 and #13 describe today's code. None of the
five is closed, duplicated by another item or covered by an open merge request.

| Phase | Item | Verdict | What the check added or corrected |
|---|---|---|---|
| 1 | [#10](https://gitlab.com/max757/duris/-/work_items/10) Boot SQL discarded | Valid, accurate | Nothing wrong. `sql_work_repository_apply(MYSQL *, ...)` already exists, which makes the synchronous fix the short one. |
| 2 | [#13](https://gitlab.com/max757/duris/-/work_items/13) Small defects and log noise | Valid, accurate | The wrong `EST` stamp is built at five sites, not one. The quest-count sentinel has four callers, not two. The `lock` lookup has two callers. Three tests and four documents read the event-budget lines. |
| 3 | [#11](https://gitlab.com/max757/duris/-/work_items/11) Ownership rows and the save audit | Valid, accurate | Three `ON DELETE RESTRICT` foreign keys constrain any delete. The flat-file backend keeps the same records. Two journeys wait on the `missing_payload_rows` line. The audit's stated failure no longer exists. |
| 4 | [#14](https://gitlab.com/max757/duris/-/work_items/14) Casts finish late | Valid, not yet measured | The item's first link (`sparser.c` L2193) is in `do_will`, not `do_cast`; `do_cast` starts its cast at L2558. All three scheduling sites go through `schedule_spellcast()`, so one fix covers both. |
| 5 | [#17](https://gitlab.com/max757/duris/-/work_items/17) Telemetry | Valid, accurate | The three community commits were probed against `master`: all source merges cleanly, the conflicts are in documents and the data-lifecycle files. The third commit is needed once the first is in. |

## Decisions

| # | Decision | Where |
|---|---|---|
| 1 | Boot-time SQL runs synchronously on the boot connection until the writer starts. Jobs are not held for later. | Phase 1 |
| 2 | The wrong time stamp is removed at all five sites, from the log line and from the immortal channel. | Phase 2 |
| 3 | A peer that closes its connection writes no read-side line. | Phase 2 |
| 4 | An absent `mud_info` row is not logged. No `lock` row is seeded. | Phase 2 |
| 5 | The shopkeeper save line goes behind `DURIS_PERSISTENCE_TRACE`. | Phase 2 |
| 6 | Event-budget records become one line per 300-pulse window. The per-pulse lines need `DURIS_NEVENT_ANALYTICS=1`. | Phase 2 |
| 7 | Stale ownership records are reaped at boot, in both backends, and never inside a save. | Phase 3 |
| 8 | The `missing_payload_rows` and `unowned_object` lines go behind `DURIS_PERSISTENCE_TRACE`. No in-memory entry is written at pickup, and committed claims are not published back. The item's last done-when clause is amended to match. | Phase 3 |
| 9 | The cast fix lands whatever the measurement shows. `DelayCommune()` is not changed. | Phase 4 |
| 10 | Telemetry parts 1 and 3 are taken from the community tree, with `b3fb28b9f` as well. Part 3 is their bounded gap record, not a replayed spool. | Phase 5 |
| 11 | The phases are done in the order below. | All |

## Order

By cost of leaving it: data that is not written (#10), then the cheap fixes that quiet the
logs every later phase reads (#13), then ownership (#11), then the fix that starts with a
measurement (#14), then the largest change, to a subsystem that is off by default (#17).

Two things to keep in mind across phases:

- **#13 and #14** both touch the event pass. #14's measurement uses the
  `PLAYER EVENT TIMING` trace, which #13 does not change.
- **#10 and #13** both add assertions about a clean boot's logs.
  `tests/async/test_boot_log_hygiene.py` is the place for the source contracts. The logs
  of a real full-world boot are read in `tests/async/test_mysql_world_capture_journey.py`,
  where Phase 1 put its boot checks.

## Every phase

- One branch and one merge request per phase, closing its work item.
- `./scripts/format.sh --check`, `make -C src`, the phase's focused tests, then one run of
  `make test-all` and `make test-db` before it lands.
- A regression test for each behaviour that changes, as the item's done-when asks.
- The head a review reads is tagged `log-review/phase-<n>-review-<round>`, rounds from 0,
  and the tag is pushed with the branch.
- A phase starts from `master`. Phases 1 and 2 both touch `src/net/comm.c` and
  `tests/async/test_boot_log_hygiene.py`, in different places.
- The phase's section is brought up to date in the same branch: what was built, what
  differs from the plan and why, the gate's result, and what is left.

---

## Phase 1: SQL queued during boot is discarded (#10)

**Status: landed in `7fdbb20fe`.** "State of the work" at the end of this phase has the
details.

**Checked.** `submit()` in `src/sql/sql_async.c` logs `sql job not queued` and drops the job
when the writer returns `unavailable`. The writer starts at `comm.c` L990, after `boot_db()`
(L824), `redis_cache_fraglist()` (L838) and `init_outposts()` (L917). Nothing holds or
retries a refused job. `save_outpost_record()` returns before it updates memory.
`artifact_row_store()` updates memory first, so memory and the table disagree after boot.

**Reproduced locally, twice.** The development server booted from this checkout on
2026-10-05 at 13:31 wrote 59 of the lines to `logs/log/file` (49 `artifact_row_store`, 6
`arti_redis_cache`, 1 `redis_cache_fraglist`, 3 `save_outpost_record`). On a long-lived
database the artifact rows exist, so it logged no "Creating entry". The journey of step 3,
on an empty database, failed on the same lines in 22 seconds on the unfixed build.

**Fix: boot-time jobs run synchronously on the boot connection.**

- Until the writer start has been attempted, `sql_queue*()` applies its work on `DB` with
  the existing `sql_work_repository_apply()`, and `sql_read*()` runs its query there and
  hands the rows to the existing `finished` list, so the callback still runs from
  `sql_async_pulse()`.
- The switch is made where the writer starts (`comm.c` L990), not on `game_booted`, which
  is set five lines earlier and before `locker_async_init()`.
- After that point nothing changes: a job the writer refuses is logged and dropped as now.
- The writer start does not move.

Holding the jobs and submitting them later was rejected: it needs a held list, a flush step
and a rule for a writer that fails to start, and the rows reach the database only after the
game loop is running. The synchronous path costs about sixty small statements of boot time
and leaves the rows in place when the loop starts. It keeps to the rule that the game loop
issues no query after boot, because it stops at the writer start.

**As built**

- `src/sql/sql_async.c`: one flag, `booting`, true from process start. While it is set,
  `queue()` and `sql_read_work_at()` call `apply_at_boot()`, which runs the work through
  `sql_work_repository_apply(DB, ...)` (one transaction, as on the writer). A write that
  fails logs `sql job failed at boot: <site> error=<n>` to `logs/log/file` and its call
  returns false, so `save_outpost_record()` leaves memory alone. A read is pushed onto
  `finished` with its outcome and its call returns true.
- `sql_async_boot_done()` clears the flag. `run_the_game()` calls it once, right after the
  `player_save_pipeline_init()` attempt, whether or not the writer started.
- No caller of `sql_queue()` or `sql_read()` changed.
- Review round 1: `arti_cache_init()` is called from `game_loop()`, after the recovery block
  and the transports, and no longer from `setupMortArtiList_sql()`. Read in the middle of
  boot, the six artifact lists were dropped as stale as soon as boot loaded an artifact
  afterwards: an owned one from its row, or all of them when a generation or a copyover is
  restored. So no restart cached them. `arti_redis_cache()` logs each list it caches.
- Nothing inside a transaction on `DB` queues SQL during boot (the pwipe epoch, the lookup
  publication, the account reward and saved-item paths were read), so the transaction the
  job opens never commits another one early.
- Every harness that links `sql_async.c` and expects the writer path now calls
  `sql_async_boot_done()` first: `test_sql_async.py` and
  `zone_story_state_mysql_harness.cpp`. There are no others.

**Steps**

1. Done. Boot mode in `sql_async.c`, switched off at the writer start.
2. Done. `test_boot_log_hygiene.py` pins that `run_the_game()` calls
   `sql_async_boot_done()` once, after `player_save_pipeline_init()`.
   `test_sql_async.py` covers boot mode before it starts the writer: a write is applied at
   once on `DB`, a failed write returns false, a read and a failed read are delivered on
   the first pulse, and nothing after `sql_async_boot_done()` is applied on the game
   thread. Since round 1 `test_boot_log_hygiene.py` also pins that `game_loop()` reads the
   artifact lists after the restores and that nothing in `artifact.c` does.
3. Done, and simpler than planned: no new leg. The first boot of
   `test_mysql_world_capture_journey.py` already is a full-world boot on an empty
   disposable MariaDB with Redis, so the assertions were added there
   (`boot_sql_missing()`) and the gate gains no second full-world boot. It asserts:
   - no `sql job` line in `logs/log/file` (not queued, or failed at boot), after the first
     boot and again after the crash-recovery boot;
   - `artifacts` and `artifact_domain_state` each hold exactly the vnums of the
     "Creating entry" lines in `logs/log/artifact` (42 in the run on the fixed build);
   - every outpost's stored hit points are above the 0 its row is created with. The
     stored value is the building's by construction (`set_current_outpost_hitpoints()`),
     so a nonzero value shows the boot write landed;
   - "cached fraglist" is in `logs/log/sys`;
   - since round 1, six "cached artifact list" lines are in `logs/log/sys` after the first
     boot and six more after the crash-recovery boot.

   Before round 1 the artifact lists were checked by hand only (12, 25 and 5 artifacts in
   the three immortal lists). That was a cold boot on an empty database, the one case that
   cached them.
4. Done. `test_flatfile_boot_preflight.py` already boots with a missing world and requires
   a controlled exit instead of `SIGABRT`. It passes unchanged: the writer start did not
   move, so no new test was needed.

**Documents.** `docs/persistence/PLAYER_SAVE_PIPELINE.md` ("Game-thread SQL") describes the
boot exception. `docs/guides/TESTING.md` says what the world capture journey now also
checks.

**Done when:** the three conditions in the item.

**State of the work**

- Branch `fix/10-boot-sql-discarded`, from `master` at `4f39cdf3e`. `92fce27db` is the
  fix with its tests and documents, and `16a99081b` the first version of this file.
- Review round 1 is `ee927e1a7` (the artifact lists, with their tests) and `ad529fd16` (a
  harness stub that commit needed). This file's commit follows them.
- The branch also carries two documentation commits that are not part of #10:
  `62e475907` and `a9bdc74f6`.
- Merge request !11 closes #10. The tag `log-review/phase-1-review-0` is the head the
  review read, and `log-review/phase-1-review-1` the head with its fix.
- The gate ran once on 2026-10-05 on `a9bdc74f6`, the tree this file was added to:
  - `./scripts/format.sh --check`: clean.
  - `make -C src`: built.
  - `make test-all`: 669 passed, 0 failed, in 8 minutes.
  - `make test-db`: 45 of 45 passed in 267 s. `world_capture`, which carries the boot
    checks, took 92 s.
- A gate run on `ee927e1a7` alone had failed one test: `test_world_recovery_pipeline.py`
  compiles the recovery block of `game_loop()` and did not link without a stub for
  `arti_cache_init()`. `ad529fd16` adds the stub.
- The first gate run, on the tree that became `92fce27db`, was 669 passed and 45 of 45.
  Before that fix, the journey failed on the `sql job not queued` lines.
- Round 1 by hand on the fixed build: a clean restart caches the six lists as a crash
  restore does. A build with the read back in the middle of boot and the new log line kept
  cached none after a crash restore, so the journey's second-boot check fails without the
  fix.
- The lists carry a 15-minute TTL (`artifact_cache_ttl_seconds`), so the boot fill is a
  warm-up: once it expires, a list returns when `artifact list` is run in game.
- Also run by hand, because the journeys boot empty databases: the fixed build booted on a
  copy of the long-lived development database (97 artifact rows, outposts already at
  300,000 hit points). It wrote no `sql job` line of either kind, updated 47 artifact
  rows, left `artifact_domain_state` agreeing with `artifacts` on every row, cached the
  frag list and stopped cleanly.
- Landed on 2026-10-05 in `7fdbb20fe`: one `--no-ff` merge of `log-review/phase-1-review-1`
  (`f2bcd921b`) into `master`, with no squash and no rebase, so both tags still name the
  commits that were reviewed. #10 is closed and the branch is deleted.
- `master` had moved during the review: `6f167e9f9` and `41e11b10f` repair two journeys
  (the world quest dual-backend run, and the playtime journey's copyover bound, which can
  fail in a loaded `make test-db`). So the gate ran once more, on the merge:
  `make test-all` 669 passed, 0 failed, in 8 minutes, and `make test-db` 45 of 45 in 375 s.
- Nothing is open.

---

## Phase 2: small defects and log noise (#13)

**Checked.** All seven findings are in the code as described, at the lines the item links.

**Added by the check**

- The shifted time stamp labelled `EST` is built at five sites: quit (`actoth.c` L309),
  enter game (`nanny.c` L1685), rent (`specs.room.c` L389), void (`limits.c` L1739) and
  lost link (`comm.c` L3361). Three subtract four hours and two subtract five, so they do
  not even agree with each other.
- `sql_world_quest_can_do_another()` has four callers. `world_quest.c` L642 and
  `specs.mobile.c` L10962 test `< 1`, so "not loaded yet" refuses the quest. That is the
  right behaviour and they do not change.
- `get_mud_info("lock")` has two callers: `account.c` L2402 and `ws_handlers.c` L2032. The
  other rows it reads (`news`, `motd`, `wizmotd`) are optional too.
- A playing character's disconnect already writes `Closing link to:` from the close path
  (`comm.c` L3359), so the read-side line repeats it.
- `DURIS_NEVENT_ANALYTICS` already defines a 300-pulse window.
  `test_nevent_budget_contract.py`, `test_nevent_catchup_contract.py` and
  `test_mysql_game_loop_budget_journey.py` read the event-budget lines; `RUNBOOK.md`,
  `EVENTS.md`, `ARCHITECTURE.md` and `CODEBASE.md` describe them.
- `persistence_trace_enabled()` (`DURIS_PERSISTENCE_TRACE`) already gates routine
  persistence lines, and `test_boot_log_hygiene.py` asserts that for the per-shop restore
  line.

**Steps.** Each is its own small commit.

1. **Quest count.** `score` omits the line and the quest JSON omits `remaining` while the
   history is not loaded. A test covers a character whose history has not loaded.
2. **Time stamps.** Remove the stamp at all five sites, from the `logit` lines and from
   the `loginlog()` copies. The log lines keep the logger's UTC prefix; the immortal
   channel is read live and needs none.
3. **Disconnects.** `process_input()` writes nothing when the peer closed: end of file,
   `ECONNRESET`, `GNUTLS_E_PREMATURE_TERMINATION` and `GNUTLS_E_PULL_ERROR`. Any other read
   error keeps its error line.
4. **`mud_info`.** `get_mud_info()` returns empty for an absent row without logging. The
   flat-file version does the same for an absent file and still logs a read error.
5. **Profile dump.** Shutdown skips `PROFILES(SAVE)` and `save_func_call_info()` when
   `do_profile` is off.
6. **Shopkeeper saves.** The `saved %d shopkeepers` line goes behind
   `persistence_trace_enabled()`, and joins the list `test_boot_log_hygiene.py` checks.
7. **Event-budget records.** Last in the phase.
   - Always on: one `NEVENT BUDGET` line per 300-pulse window in which the pass deferred
     work. It carries the pulses over budget, the total deferred, the largest catch-up
     debt, and the worst pulse's lateness, event name, tick and time.
   - The per-pulse `NEVENT BUDGET` and `NEVENT CATCHUP` lines are written only with
     `DURIS_NEVENT_ANALYTICS=1`. `test_mysql_game_loop_budget_journey.py` sets it.
   - The two contract tests and the four documents change in the same commit.

**Done when:** the four conditions in the item. The quit line condition holds for the other
four stamps as well.

---

## Phase 3: ownership records are never retired, and the save audit (#11)

**Checked.** `claim_items()` inserts or re-points rows and never releases one. No statement
in `src/` deletes from `item_current_owner`. The reasons `player_get`, `player_drop`,
`player_give`, `corpse_loot` and `mobile_claim` have no user. The load path counts the row
and logs it on every login. The save's insert is not published to the in-memory table, so
`unowned_object` fires on every save until the next login.

**Added by the check**

- Three foreign keys point at `item_current_owner.item_uid`, all `ON DELETE RESTRICT`: the
  table's own `parent_item_uid`, `auction_item_custody` and `artifact_domain_state`. A
  delete that meets one fails. This is the "would trip foreign keys" in ADR 0002.
- The flat-file backend follows the same claim model and counts the same records
  (`flatfile_player_repository.c` L404), so it collects them the same way.
- World recovery already treats a player's active row with no payload row as not owned
  (`sql_persistence_world_recovery_items_owned()`, `sql.c` L5172). Retiring such a row does
  not change what it restores.
- `test_mysql_combat_journey.py` L163 and `test_flatfile_combat_journey.py` L301 wait for
  the `missing_payload_rows` line as a signal. `test_player_load_topology.py` and
  `test_orphan_item_session_regressions.py` pin the source of both lines.
- The comment above the `unowned_object` line describes a failure that is gone: a load now
  takes a payload row that has no ownership row (`player_load_repository.c` L543), and the
  save inserts the ownership row before it writes the payload. Item grants and shop trades
  already accept an item with no in-memory entry. A grant path that skips the ledger costs
  nothing today, and at save time it is the same state as an ordinary pickup.
- The header of `scripts/item_ownership_audit.sh` still calls a payload row without an
  ownership row "item loss". It is stale in the same way as the `handler.c` comment.

**Retiring records: reaped at boot, never inside a save.**

- At boot no character is in memory, so a player's active record with no payload cannot be
  a held item. The reap deletes exactly those: owner type player, state active, and no row
  in `player_items` or in the character's `player_pet_items`. This is the set the load
  count already defines.
- It skips a row that an auction, an artifact or a child row still references, and repeats
  until a pass deletes nothing, so a stale container goes after its stale contents.
- It runs on the boot connection before the writer starts. A failure is logged and the
  boot continues.
- The flat-file backend gets the same rule on its catalog at boot.
- Only player-owned records are reaped. Lockers, corpses, shops, auctions and the
  collector are not touched.

Releasing in the save's claim was rejected: it runs inside the save transaction, and a
delete that meets one of the three foreign keys would fail the save, which is the failure
ADR 0002 exists to prevent. Accepting the rows was rejected: the table would grow for the
life of the database and every query keyed on an owner would slow with it.

**The two log lines: behind `DURIS_PERSISTENCE_TRACE`.**

- Records still collect during an uptime, so the per-login `missing_payload_rows` line
  goes behind `persistence_trace_enabled()` in both backends.
- The `unowned_object` line goes behind it too, with its comment rewritten. Publishing
  committed inserts to the in-memory table was rejected: it still logs once after every
  pickup. Writing an in-memory entry at pickup was rejected: it adds code to the `get` and
  loot paths to protect a distinction that no longer costs anything.
- The item's last done-when clause becomes: an ordinary pickup followed by several saves
  writes no `unowned_object` line, and with `DURIS_PERSISTENCE_TRACE=1` the line is
  written for any held item that has no ledger entry.

**Steps**

1. Record the decision in ADR 0002 (the "Releasing items an owner no longer holds" row and
   the consequence about dropped items), and amend the done-when on the work item.
2. The boot reap for MariaDB, with a `make test-db` test: a character picks up a zone
   item, saves, drops it, the server restarts, and the row is gone. The same test covers
   an artifact and a nested container that must survive or go in order.
3. The boot reap for the flat-file backend, with the same journey there.
4. Both lines behind the trace switch. The two journeys that wait on
   `missing_payload_rows` set `DURIS_PERSISTENCE_TRACE=1`; the two source-contract tests
   are updated. A test shows several saves after a pickup write no `unowned_object` line
   by default and one with the trace on.
5. Rewrite the `handler.c` L3151 comment, the comment above `unowned_object` and the
   header of `scripts/item_ownership_audit.sh` to say what the reap does.
6. `run_world_restart_journey.py` passes in all its modes.

**Done when:** the three conditions in the item, the last one as amended above.

---

## Phase 4: casts finish late when the event pass runs behind (#14)

**Checked.** `do_will` (L2193) and `do_cast` (L2558) each schedule a first segment of 1 to 4
pulses. `event_spellcast` schedules each further segment at L2759 to L2762 from the current
tick. All three go through `schedule_spellcast()` (L1241). `add_event` sets
`due_tick = ne_event_tick + delay` (`new_events.c` L890). The event pass knows how late the
running event is (L1603), and the continuation does not use it. `DelayCommune()` extends
the memorize event by the nominal segment, which still adds up to the cast time. The defect
follows from the code. Nobody has measured a late cast.

**Steps**

1. **Measure.** A copy of `test_mysql_combat_journey.py` with `DURIS_NEVENT_TRACE_PLAYER=1`
   (it already sets it) and a caster repeating a spell of at least 12 pulses while the
   event pass is loaded. Compare each cast's start-to-finish pulses with its cast time and
   post the numbers on the work item. The fix lands whatever they show.
2. **Fix in `schedule_spellcast()`.** `spellcast_datatype` carries the cast's intended due
   tick. The helper advances it by the segment and schedules for
   `max(1, intended - now)`. A cast then finishes at its cast time plus the lateness of
   its last segment, except where the one-pulse minimum applies. Lateness larger than a
   whole segment carries forward without extra code. `DelayCommune()` and the progress
   display keep using the nominal segment.
3. **Test.** A harness modelled on `test_spell_schedule_failure_runtime.py` drives
   `event_spellcast` with late callbacks and pins the bound. A second case shows a cast
   with no lateness takes exactly its cast time.
4. Run the measurement again and post the second set of numbers.

**Done when:** the three conditions in the item.

---

## Phase 5: telemetry schema check, SQL round trip and restart gaps (#17)

**Checked.** Startup proves only that four tables exist (`telemetry_repository.c` L125).
`test_telemetry_repository.py` prints `SQL runtime: SKIPPED` unless it is given
`--sql-fixture`, and `tests/run_db_tests.sh` has no telemetry leg. The queue and the
in-flight batch are process memory. `TELEMETRY_ENABLED` is in neither `.env` nor
`.env.example`, so the writer is off here and nothing is being lost today.

**Added by the check**

- `src/telemetry` is unchanged since the split (`git diff e1357a30a HEAD -- src/telemetry`
  is empty), as the item says.
- The three community commits were applied to `master` in order with `git merge-tree`
  (nothing was written to the tree). Every file under `src/` and every test harness merges
  without conflict. The conflicts are:

  | Commit | Size | Conflicts |
  |---|---|---|
  | `e0e837102` schema and permission check | 21 files, +1,613 | `docs/telemetry/RECOVERED_FOLLOWUPS.md` and `scripts/telemetry/preflight.py`, neither of which is in our tree. |
  | `03da1882d` bounded outage record | 22 files, +2,055 | `migrations/data_lifecycle_manifest.json`, `scripts/validate_data_lifecycle.py`, `tests/async/test_data_lifecycle_manifest.py`. |
  | `b3fb28b9f` session recovery | 13 files, +493 | `docs/telemetry/IMPLEMENTATION_STATUS.md`. |

- `e0e837102` is built on one column descriptor per record kind
  (`telemetry_columns.inc`), which is the refactor the item calls optional. It also carries
  a 444-line `BALANCE_EXPANSION_PLAN.md` that belongs to their unmerged balance work.
- `b3fb28b9f` keeps a session that begins while the writer is still qualifying the schema
  or is at capacity. The first commit introduces that qualifying window, so the third is
  needed once the first is in. It touches `copyover.c`, `comm.c` and `structs.h`.
- The repository test accepts only ports 3306 and 3307. The disposable MariaDB wrapper
  publishes a random port in `TEST_DB_PORT`.

**Approach.** The gate is built first. Parts 1 and 3 are then taken from the community
tree and each is proved with it. Their three commits are about 3,700 lines without the
balance plan. They are already tested on their side, and taking them keeps `src/telemetry`
close enough to pick from again; a smaller rewrite here would end that. Part 3 is their
bounded gap record. A spool that replays the backlog is not built.

**Steps**

1. **Part 2, the gate.** A `telemetry_repository` leg in `tests/run_db_tests.sh` under
   `with_disposable_mariadb.sh`. The test takes the wrapper's `TEST_DB_*` settings in
   place of its port list. The leg applies the migration chain to the head, runs the SQL
   harness, and fails if the SQL part did not run. It is run against today's code first; a
   record kind that fails there is fixed in its own commit before step 3.
2. The harness covers every record kind: write, read back and compare every field, replay
   and require `duplicate_identical`, change one field and require `duplicate_conflict`.
   A wrong column name fails the leg.
3. **Part 1.** Pick `e0e837102` without `BALANCE_EXPANSION_PLAN.md`,
   `RECOVERED_FOLLOWUPS.md` and `preflight.py`. Tests: a removed or renamed progression
   column and a combat column are each caught at startup; a missing table, column, type
   and grant give distinct messages; the game still starts and telemetry reports itself
   disabled.
4. **Part 3.** Pick `03da1882d` and resolve the three data-lifecycle conflicts by adding
   their entries to our manifest. Tests: a graceful shutdown, a copyover and a kill during
   a simulated SQL outage each leave a queryable gap record.
5. Pick `b3fb28b9f`. `IMPLEMENTATION_STATUS.md` is resolved to describe our tree.
6. Set the "Telemetry" row in `docs/records/COMMUNITY_DURIS_TRACKING.md` to taken, with
   the three commits.

**Done when:** the four conditions in the item.
