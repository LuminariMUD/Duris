# Plan: work items #10, #11, #13, #14 and #17

Written 2026-10-05 against `master` at `40a0667c4`. One phase per work item. The owner
locked every recommendation the same day, and the points that were still worded as "check,
then decide" were settled against the code. Nothing is left to decide. This file is a
working note: delete it when the last phase lands.

## Status

Updated 2026-10-07. A new session starts here, then reads the phase it continues.

| Phase | Item | State |
|---|---|---|
| 1 | #10 | Landed on 2026-10-05 in `7fdbb20fe` (!11). |
| 2 | #13 | Landed on 2026-10-06 in `6a4e5511c` (!12). |
| 3 | #11 | Landed on 2026-10-07 in `a55ccef17` (!13). |
| 4 | #14 | Landed on 2026-10-07 in `7ef76523e` (!14). |
| 5 | #17 | Built on 2026-10-07 on `fix/17-telemetry` from `master` at `ab4d91340`; open for review as !15, tag `log-review/phase-5-review-0`. |

## Are the items still valid?

All five are. Every code claim in them was read again at `40a0667c4`. No file under `src/`,
`tests/`, `migrations/` or `scripts/` has changed since `dc8357143`, the commit the log
review ran on, so the observations in #10, #11 and #13 describe today's code. None of the
five is closed, duplicated by another item or covered by an open merge request.

| Phase | Item | Verdict | What the check added or corrected |
|---|---|---|---|
| 1 | [#10](https://gitlab.com/max757/duris/-/work_items/10) Boot SQL discarded | Valid, accurate | Nothing wrong. `sql_work_repository_apply(MYSQL *, ...)` already exists, which makes the synchronous fix the short one. |
| 2 | [#13](https://gitlab.com/max757/duris/-/work_items/13) Small defects and log noise | Valid, accurate | The wrong `EST` stamp is built at five sites, not one. The quest-count sentinel has five callers, not two. The `lock` lookup has two callers. Three tests and four documents read the event-budget lines. |
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

**Status: landed in `6a4e5511c`.** "State of the work" at the end of this phase has the
details.

**Checked.** All seven findings are in the code as described, at the lines the item links.

**Added by the check.** The line numbers are `master`'s at `9725a354d`, before this phase.

- The shifted time stamp labelled `EST` is built at five sites: quit (`actoth.c` L309),
  enter game (`nanny.c` L1685), rent (`specs.room.c` L389), void (`limits.c` L1739) and
  lost link (`comm.c` L3361). Three subtract four hours and two subtract five, so they do
  not even agree with each other.
- `sql_world_quest_can_do_another()` has five callers. `world_quest.c` L642 and
  `specs.mobile.c` L10962 and L11161 test `< 1`, so "not loaded yet" refuses the quest.
  That is the right behaviour and they do not change.
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

**As built.** Each step is its own commit.

1. **Quest count** (`8e25ee1f5`). `score` leaves the line out, and
   `json_build_quest_status()` leaves `remaining` out, while
   `sql_world_quest_can_do_another()` answers below zero: the MariaDB history has not
   loaded, or the flat-file read failed. `test_world_quest_remaining_unloaded.py` runs
   score's own lines and the production JSON builder against a history that has not
   loaded, then against one that has.
   Review round 1 (`87cca01d2`): `enter_game()` queues the history read and sends
   `Quest.Status` in the same call, so a first entry after a boot could never carry the
   count, and nothing sent it later. The read's callback now sends the status again to a
   character that is in the game. `sql_world_quest_can_do_another()` no longer logs
   `history not loaded yet`: every first entry asks once before the read can answer.
2. **Time stamps** (`26531fc28`). The stamp is gone from the five `loginlog()` lines and
   from the quit `logit()` line, with the locals that only built it.
   `test_boot_log_hygiene.py` pins the five format strings.
   Review round 1 (`d2fbf849d`): four of the five lines (enter game, rent, void and lost
   link) are written by `loginlog()` alone, which reaches no log file, so the stamp that
   was removed was the only time they carried. `loginlog()` now starts every line of the
   staff channel with the server's time and the zone it is in.
3. **Disconnects** (`9f027d69d`). `process_input()` returns without a line for end of
   file, `ECONNRESET`, `GNUTLS_E_PREMATURE_TERMINATION` and `GNUTLS_E_PULL_ERROR`. Any
   other read error keeps its line. `close_socket()` logs every descriptor it closes,
   playing or not, so a disconnect still writes one line. The WebSocket read path never
   logged these.
4. **`mud_info`** (`53b51de63`). The MariaDB lookup returns empty for an absent row and
   logs nothing. The flat-file lookup logs only a source it cannot read; a page that has
   no source there, as `lock` has none, and a missing file are quiet.
   `flatfile_mud_info_runtime_harness.cpp` covers the three cases.
5. **Profile dump** (`0ce7f0586`). Shutdown runs `PROFILES(SAVE)` and
   `save_func_call_info()` only while `do_profile` is on. `debug profile save` still
   writes them on request.
   Review round 1 (`e07673051`): a run that was switched off before the stop was lost, so
   the guard is now `event_loop_profile.calls > 0`. That timer counts only while
   profiling is on and `debug profile reset` zeroes it, so a server that never profiled
   still writes nothing.
6. **Shopkeeper saves** (`aa7d10392`). The `saved %d shopkeepers` line is behind
   `persistence_trace_enabled()` and in the list `test_boot_log_hygiene.py` checks.
   `CONFIGURATION.md` names it under `DURIS_PERSISTENCE_TRACE`.
7. **Event-budget records** (`3b6d3ae90`).
   - Always on: `NEVENT BUDGET WINDOW`, one line when a revolution of the wheel (300
     pulses) ends, if the pass deferred work or ran work late in it. It carries
     `deferring_pulses`, `deferred`, `peak_catchup_debt`, and the worst pulse as
     `max_late_ticks`, `max_late_name`, `max_late_tick` and `max_late_total_us`.
   - The per-pulse `NEVENT BUDGET:` and `NEVENT CATCHUP:` lines are written only with
     `DURIS_NEVENT_ANALYTICS=1`. `test_mysql_game_loop_budget_journey.py` already set it.
   - `test_nevent_scheduler_runtime.py` runs the production pass through two revolutions,
     with analytics off and on: one window line with the worst pulse, none for a quiet
     revolution, and per-pulse lines only with analytics. The two contract tests pin the
     gates. `EVENTS.md`, `CONFIGURATION.md`, `RUNBOOK.md`, `ARCHITECTURE.md` and
     `CODEBASE.md` describe the line and the switch.

The lines a real server writes are checked in `test_mysql_world_capture_journey.py`
(`world_capture` in `make test-db`), where Phase 1 put its boot checks. Its mortals each
name a new character and close their sockets, and its last server is stopped cleanly. The
journey waits until `close_socket()` has logged every disconnect, requires
`Normal termination of game.`, and fails on `EOF encountered` or `process_input()` in
`logs/log/comm`, `get_mud_info` in `logs/log/debug` and `Profile info` in `logs/log/file`
(`9cd0ef332`). Since review round 1 its mortals turn GMCP on, and each must be sent a
`Quest.Status` with its count.

**Differs from the plan**

- Step 6: `test_mysql_game_loop_budget_journey.py` waits for the shopkeeper save line and
  measures the batch from it, which the check had missed. The journey now sets
  `DURIS_PERSISTENCE_TRACE=1`, and `test_shopkeeper_save_runtime.py` stubs the switch.
- Step 7: the summary has its own prefix, `NEVENT BUDGET WINDOW`, so nothing that reads
  `NEVENT BUDGET:` meets a line of another shape. The window is one revolution of the
  wheel and ends on its last bucket, so it needs no counter of its own.
- Step 7: a revolution that only ran work late is reported too. The pulse that defers and
  the pulse that runs that work late can fall on either side of the boundary, and the
  worst case would be lost otherwise. The revolution a stop interrupts is not reported.
- Step 7: five documents changed, not four. `CONFIGURATION.md` lists the switch as well.
- Step 4: in the flat-file backend `lock` has no source at all, so "no source" is quiet as
  well as "no file". A read error is recognised by the reader's own
  `invalid information source` text.
- Step 2: the stamp the logger puts in front of every line is the server's clock
  (`localtime`), not UTC as such. It is UTC on a server set to UTC. The logger did not
  change.
- No test of its own for the real log lines: they are checked in the world capture
  journey, which already boots, plays and stops a full server.
- Step 2, review round 1: decision 2 removed the wrong stamp from the immortal channel as
  well as from the log line. For four of the five lines the channel is the only record, so
  that left them with no time at all. The channel now carries the server's own time on
  every line. `d2fbf849d` stands alone: it can be dropped if the channel should carry none.
- Step 5, review round 1: the review offered `do_profile || event_loop_profile.calls > 0`.
  The second half alone is used. With profiling on at the stop the timer has counted,
  unless the stop came within two pulses of switching it on or resetting it, and then
  there is nothing but zeros to write.

**Found on the way**

- `time` showed players a second line: the server's time minus five hours, labelled
  `(EST)`. It is the same stamp. The line is removed, and the one that is left names the
  zone the server's clock is in, `(UTC)` on a server set to UTC (`c93b4588c`). A correct
  Eastern line would need the time zone database at run time; it was not built.
  Review round 1 (`f0a8c4e3a`): the zone was formatted into 16 bytes with an unchecked
  `strftime()`, so a zone abbreviation of 16 characters or more printed stack bytes. Only
  the server's own `TZ` can do that. The line now prints `tm_zone`, with no buffer. The
  test is `test_server_time_zone.py`, which also runs the production `loginlog()`.
- A new character's "enters game" line on the staff channel gave the time since 1970 as
  its absence (`MIA: 20731 days`): a character that has never been saved has a save time
  of zero. The line now carries an absence only for a character that has been saved
  (`ad5c0af68`). Seen in the round 1 probe.
- Two defects of the journeys themselves each failed a `make test-db` run. Neither is
  part of #13, so each went to `master` after its own gate, and this branch was rebased
  onto it.
  - `19c71cc22`: the first run failed `world_restart_crash` and
    `world_restart_slowread` on one port collision. Four journeys chose their Redis port
    by binding port 0 and started Redis on it 20 seconds or more later. Such a port comes
    from the kernel's ephemeral range, 4,096 ports wide here, and was handed out again in
    between: the crash leg's port went to the slow-read leg's proxy. The journeys now
    take the port from below that range and bind it at once. Its gate: `make test-all`
    669 passed and 0 failed, `make test-db` 45 of 45.
  - `105dc9092`: the second run failed `chaos_raise`. One greater dracolich in ten
    turns on its creator, and the journey starts over when that happens, but it waited
    for a standing prompt first, which a caster killed in the first round never gets. It
    now looks for the hostile line first. Against a server built with the roll forced,
    the old journey fails with the same timeout and the new one starts over five times
    out of five. Its gate: `make test-db` 45 of 45, the only gate that runs that file.

**As built**

1. **The gate (steps 1 and 2).** `test_telemetry_repository.py --sql-fixture` takes the
   wrapper's `TEST_DB_*`, creates `duris_telemetry_test`, applies the chain with
   `migration_runner.py` (36 steps through `0036_log_entries_ipv6`) and checks the
   history head, then runs the harness with the `DB_*` settings; a missing setting is an
   error. The harness is #591's: every record kind 1 to 8 is written, replayed for
   `duplicate_identical` and changed for `duplicate_conflict`. The leg is
   `telemetry_repository` in `run_db_tests.sh`, 19 s. On today's code (`ab4d91340`) it
   passes on MariaDB 10.11.19: no record kind needed a fix before step 3. Probed: with
   `session_boot_id` misspelt in `session_fields()` (a column the Python mapping contract
   does not cover) the harness fails on the first INSERT and the leg exits 1.
   `DATABASE.md` names the leg and the command.

2. **Part 1** (`f7368e60e`, the pick of `e0e837102` with the four documents and the
   script dropped, author kept). It merged cleanly and compiled on the step-1 harness.
   Reviewing it found a defect it did not fix: the transport opened the circuit on a
   refused repository start with `permanent_repository` and error 0, never reading the
   repository's health, so the operator line said that for a schema or a grant refusal
   alike; and the check's own mismatches (type, index, engine) borrowed SQL error 1054,
   the missing-column code. `ce09d17bc` fixes both: `telemetry_schema_check` (table,
   column, column-type, index, engine) in the health snapshot, set by the repository
   and carried by the transport through an optional `health` callback on the repository
   binding (defaulted, so the harness bindings compile unchanged), printed as
   `schema_check=` on the `telemetry_health` line and by `world telemetry`, and part of
   the monitor's failure signature. The repository harness pins the kind and the code
   per case and gains a renamed progression column; the transport harness pins the
   carried cause. `run_telemetry_schema_boot_journey.py` boots a real server with
   telemetry on: whole chain (healthy), one progression column renamed (the boot gate
   refuses the schema with COMPAT-E003 before telemetry runs, so on this tree a drifted
   telemetry table never reaches the writer), a writer that may only SELECT
   (`permanent-permission error=1142 schema_check=none`, game running, nothing admitted)
   and, with `--misnamed-server`, a build whose `telemetry_columns.inc` names a column
   the chain lacks (`permanent-schema error=1054 schema_check=column`, game running):
   the production incident of the item, reproduced on a running server. It is the
   `telemetry_schema_boot` leg of `make test-db`, 20 s. On the binary of `f7368e60e`
   the SELECT-only writer logged `permanent-repository error=0`. `RUNBOOK.md` lists the
   causes; `DATABASE.md` names the journey.

3. **Part 3** (`476376592`, the pick of `03da1882d`; author kept). The data-lifecycle
   conflicts were resolved by adding only the ledger's entry (23 non-database stores),
   the validator's one check and the test's one case; their two status documents stay
   out, `OUTAGE_STORAGE.md` is reworded without their follow-up numbers and indexed in
   `README_docs.md`. Their two tests (`test_telemetry_outage.py`: lifecycle, protected
   paths, corruption, a real SIGKILL, a real exec and restart, the producer quota, the
   offline export; `test_telemetry_runtime_outage.py`: registration before SQL init,
   clean drain and restart, transient SQL recovery, a shutdown with an unresolved
   commit, disk-full) pass here, as do the harnesses the transport change touches.
   `TELEMETRY_OUTAGE_LEDGER_DIR` is required once telemetry is on: without it the
   server logged `permanent-repository error=22` and ran on, as designed. On the real
   server (the schema boot journey, `bc763f090`): a SIGTERM leaves the producer `clean_drained`; a copyover leaves the
   copied-over producer `unknown_tail` and the new image `clean_drained`; a SIGKILL
   leaves `running` until the next producer registers, then `unknown_tail`. The
   copyover result is an observation, not a defect of the item: the flush before the
   exec is durable, but no terminal sample is written, so the record says only that
   coverage after the last sample is unknown, which is the conservative reading the
   document gives `unknown_tail`. Writing that sample before the exec would be a
   change to the copyover path, left out of this phase.

4. **Step 5** (`95cf073c7`, the pick of `b3fb28b9f`; author kept). The two status
   documents stay out and the `SESSION_LIFECYCLE.md` paragraph ends without the pointer to
   them. `structs.h` now includes `telemetry_types.h`, so everything recompiled (36 s
   here). Its adapter, hook and copyover-format tests pass, and the schema boot journey's
   copyover case still shows the copied-over producer as an unknown tail: that commit is
   about sessions, not the ledger.
5. **Step 6.** The ledger's telemetry row is `Adopted` with the three commits and the two
   on top; PR #591's row is `Adapted` with `38c59e6fe`. `REGRESSIONS.md` has the section
   "Telemetry writer: schema check, round trip and the gap record" and `TESTING.md`'s
   samples table a telemetry row (`04ccf6a2c`).

**Differs from the plan**

- Steps 1 and 2 are PR #591's harness and test on our wrapper, not a new harness (see
  "Added by the check"). The read-back is the repository's own replay comparison.
- Part 1 needed a fix of our own on top of the pick (`ce09d17bc`): the transport reported
  every refused start as `permanent_repository` with error 0, so the item's "told apart in
  one operator message" was not met by the pick alone, and its synthetic mismatches
  borrowed SQL error 1054. The `telemetry_schema_check` field, the binding's `health`
  callback and the `schema_check=` output are ours.
- The schema cases of the item's first condition are detected by the persistence boot
  gate (`COMPAT-E003`) before telemetry on a real server, because the telemetry tables are
  in the runtime fingerprint. The telemetry check matters for grants and for a writer
  whose column list disagrees with the migrations, the production incident; the journey
  proves both on a running server, the second with a variant build
  (`bin/analysis/misnamed`, two lines added to `telemetry_columns.inc`, built with its own
  `OBJDIR`; the recipe is in "State of the work").
- The plan's step 4 tests (shutdown, copyover, kill "during a simulated SQL outage") are
  their harnesses (simulated faults, real SIGKILL and exec at the journal level) plus the
  journey's real-server stop, copyover and kill without an outage. A real-server outage
  with queued records is not simulated (see the regression notes' "Not covered").
- `IMPLEMENTATION_STATUS.md` is deleted at each pick rather than "resolved to describe our
  tree" (see "Added by the check").
- Three documents of ours changed that the plan did not list: `RUNBOOK.md` (the causes
  on the health line), `README_docs.md` (the outage document) and `.env.example` (the
  ledger directory, from the pick).

**Done when:** the four conditions in the item. The quit line condition holds for the other
four stamps as well.

**State of the work**

- Branch `fix/13-small-defects-log-noise`, from `master` at `105dc9092`: the nine
  commits named above, then this file's.
- Review round 1 is five commits: `87cca01d2`, `e07673051`, `f0a8c4e3a` and `d2fbf849d`
  for the review's findings 1 to 4, and `ad5c0af68` for what was found on the way. This
  file's second commit follows them.
- Merge request !12 closes #13. The tag `log-review/phase-2-review-0` is the head the
  review read, and `log-review/phase-2-review-1` the head with its fixes.
- The gate, on 2026-10-05, on `c93b4588c`, the head before this file's commit:
  - `./scripts/format.sh --check`: clean.
  - `make -C src`: built.
  - `make test-db`: 45 of 45 passed in 272 s. `world_capture`, which reads the logs, took
    95 s, and `game_loop_budget` 202 s.
  - `make test-all`: 671 passed, 0 failed, in 462 s. It ran before the last rebase, which
    added only `105dc9092`: a change to a journey that `make test-all` does not run.
- Two earlier `make test-db` runs were 43 of 45 and 44 of 45. Each failed on one of the
  two journey defects under "Found on the way", and `make test-all` was 671 passed and 0
  failed beside the first as well.
- Shown to fail without the fixes:
  - A server built from `master` (`9725a354d`) fails the world capture journey with all
    four lines: `EOF encountered` and `process_input()` in `logs/log/comm`, `get_mud_info`
    in `logs/log/debug` and `Profile info` in `logs/log/file`. The branch's server passes.
  - `test_world_quest_remaining_unloaded.py` and the flat-file `mud_info` harness fail on
    the old code.
- By hand, on the development server with its long-lived database and the branch build:
  - `score` shows "Bartender Quests Remaining: 2". `time` shows one line, with the zone.
  - A staff quit writes `has quit in [1200].`. A dropped link writes `Closing link to:`
    and nothing else. A close at the account menu writes `Losing descriptor without char`
    and nothing else.
  - A clean stop writes no `Profile info` line. The old build, stopped a few minutes
    before, wrote 39.
  - The first revolution after the boot wrote one `NEVENT BUDGET WINDOW` line (41 pulses
    deferred 234,593 events, the worst ran 3 pulses late) and no per-pulse line.
- In the game loop budget journey, with analytics on, 9 `NEVENT BUDGET:` and 14
  `NEVENT CATCHUP:` lines over 600 pulses came with 1 window line. A default server
  writes only that one.
- The rent and void lines were not triggered by hand before the review.
  `test_boot_log_hygiene.py` pins their format strings. Round 1 triggered both.
- The review ran its own gate on `dfc8e2c99`: `make test-all` 671 passed and 0 failed in
  472 s, and `make test-db` 45 of 45 in 266 s.
- The round 1 gate, on 2026-10-06 on `ad5c0af68`, the head before this file's second
  commit:
  - `./scripts/format.sh --all --check` and `--check`: clean.
  - `make -C src`: built.
  - `make test-db`: 45 of 45 passed in 279 s. `world_capture`, which now requires the
    quest count, took 99 s, and `game_loop_budget` 201 s.
  - `make test-all`: 671 passed, 0 failed, in 450 s. That was its second run. The first,
    with the round's two probe servers running beside it, was 670 passed and 1 failed:
    `test_password_async_runtime.py` holds each step of its game thread to 50 ms and
    missed that once. The test passed alone 3 times of 3, and 32 times of 32 as 16 copies
    side by side.
- Round 1 by hand, with the review's probe on a real server (disposable MariaDB, the full
  world, three boots), a level 62 character watching a mortal:
  - A new character over telnet with GMCP is sent `Quest.Status` without the count, then
    with it (`"remaining":8`) inside 3 seconds. An existing character gets the same pair
    on its first entry after a restart, over telnet and over the WebSocket. A later entry
    in the same boot gets the count twice. `logs/log/debug` has no `world_quest` line.
  - The staff channel shows `*** LOGMSG: 01:01:46 IDT Morwenna [127.0.0.1] has rented out
    in [81019].`, and the same stamp on the enter game, lost link, reconnect and camp
    lines. A mortal left idle was voided after 21 minutes: `*** LOGMSG: 01:48:20 IDT
    Morwenna has voided in [22800].`
  - `debug profile on`, 10 seconds, `debug profile off`, then a stop: 59 `Profile info`
    lines. Stopped with profiling still on: 59. Never profiled: none.
  - A new character's entry line carries no absence: `*** LOGMSG: 01:27:06 IDT Morwenna
    [127.0.0.1] enters game. [22800]`.
- Shown to fail without the round 1 fixes, on the build of `dfc8e2c99`:
  - The world capture journey with its new check stops with `Kakan was never sent its
    remaining quests`.
  - The same probe gets one `Quest.Status`, without the count, on each first entry. Its
    channel lines carry no time, and the new character's reads `(MIA: 20731 days, 22
    hours, 5 minutes)`. On, off and a stop writes no `Profile info` line, and
    `logs/log/debug` has four `history not loaded yet` lines.
  - `time`'s own lines, run alone under `TZ='<ABCDEFGHIJKLMNOP>5'`, print `(0)` and
    valgrind reports an uninitialised value. The new lines print the zone whole and
    valgrind is clean.
- Not checked: the `NEVENT BUDGET WINDOW` line over a long run with players on. The
  development server, with no one connected, wrote 101 of them in 153 revolutions (3 hours
  11 minutes) and no per-pulse line. The worst pulse was 2 late, apart from five
  revolutions while the round's gate and probes loaded the machine, where it was up to 6.
- Landed on 2026-10-06 in `6a4e5511c`: one `--no-ff` merge of `log-review/phase-2-review-1`
  (`630e34830`) into `master`, with no squash and no rebase, so both tags still name the
  commits that were reviewed. `master` had not moved since the branch was made, so the
  merge's tree is the branch's and the round 1 gate stands for it. #13 is closed and the
  branch is deleted.
- Nothing is open.

---

## Phase 3: ownership records are never retired, and the save audit (#11)

**Status: landed in `a55ccef17`.** "State of the work" at the end of this phase has the
details.

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
  (`sql_persistence_world_recovery_items_owned()`, `sql.c` L5170). Retiring such a row does
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

**Ablated before the work started (2026-10-06).** Read again at `1e3a464ca`, against the
code and the tests. What the plan asked for is kept; how it is proved got smaller.

- No new journey and no new `make test-db` leg. The `taken` mode of
  `run_world_restart_journey.py` already does the done-when's sequence: get a zone-loaded
  mace, save, drop it, save, crash, boot, log in. Its docstring even states the stale
  record. It gains three assertions: the mace's player record is gone after the boot, the
  login after it writes no `missing_payload_rows` line, and the saves before it wrote no
  `unowned_object` line (it does not set the trace switch).
- Both combat journeys already insert a ghost ownership record under the banana and
  restart the server. Their comparisons of the player's records across the restart
  (`stable_state()` in `test_mysql_combat_journey.py`, `player_items` in
  `test_flatfile_combat_journey.py`) fail once the reap exists, so they change anyway:
  after the restart the ghost is gone and the rest is unchanged, and the login after it
  adds no `missing_payload_rows` line although the journey now has the trace on.
- The rules are proved where `claim_items()` already is: a fixture in
  `player_save_claim_mysql_harness.cpp` (the `player_save_claim` leg) and in
  `flatfile_player_save_claim_harness.cpp` (`test_player_save_claim.py`). A record with a
  payload row stays, one a legacy pet's payload carries stays, a stale container goes
  after its stale contents, a row an auction's custody row or an `artifact_domain_state`
  row references stays (the foreign keys), another owner's record and a quarantined one
  are not touched. A full-world boot to prove a foreign key would add a minute to the
  gate for what twenty fixture rows show.
- The reap does not advance `item_owner_revision`. A player owner's revision is not a
  fence (`item_transfer_repository.c`: "saves move their revisions, so a transfer does not
  fence on them"), and the in-memory copy is hydrated in `main()` before `run_the_game()`,
  so a bump there would only make the two disagree.
- The flat-file reap skips only a record another record names as its parent. The auction
  and artifact exclusions exist because the MariaDB delete fails on those foreign keys;
  the catalog has none. `artifact_domain_state.item_uid` is written by nothing in `src/`
  (the mirror leaves it NULL), so the exclusion is a schema guard and is tested with a
  fixture row.
- `missing_payload_rows` is logged in `player_load_materialize.c` for both backends, so
  the gate is one site. `unowned_object` needs a `persistence_trace_enabled()` stub in
  every harness that compiles `player_snapshot_capture.c`, as the shopkeeper line needed
  one in Phase 2.
- `test_player_snapshot_capture.py` runs the production capture: it is where "several
  saves after a pickup write no `unowned_object` line by default and one each with the
  trace on" is shown with the switch toggled; the `taken` journey shows the default on a
  real server.

**Files.** `src/item/item_claim_repository.{c,h}` (the MariaDB reap),
`src/flatfile/flatfile_item_repository.{c,h}` (the flat-file reap), `src/net/comm.c` (the
call, after the owner revisions are hydrated and before `run_the_game()`),
`src/player/player_load_materialize.c` and `src/player/player_snapshot_capture.c` (the
two lines), `src/world/handler.c` and `scripts/item_ownership_audit.sh` (the comments),
ADR 0002, `PLAYER_SAVE_PIPELINE.md`, `DATABASE.md` and `CONFIGURATION.md`; the tests named
above, `test_boot_log_hygiene.py` (the gates and the call's place in the boot) and
`test_player_load_topology.py` and `test_orphan_item_session_regressions.py` (the two
source contracts).

**Non-goals.** Rows of other owner types, destroyed rows, the `item_ownership_ledger`,
and the `item_owner_audit` table are not reaped. No in-memory entry is written at pickup
and committed claims are not published back (decision 8). No transfer reason is wired.

**Steps**

1. Record the decision in ADR 0002 (the "Releasing items an owner no longer holds" row and
   the consequence about dropped items), and amend the done-when on the work item.
2. The boot reap for MariaDB, with its fixture in the claim harness and the assertions
   in the `taken` mode and the MariaDB combat journey.
3. The boot reap for the flat-file backend, with its fixture in the flat-file claim
   harness and the assertions in the flat-file combat journey.
4. Both lines behind the trace switch. The two journeys that wait on
   `missing_payload_rows` set `DURIS_PERSISTENCE_TRACE=1`; the two source-contract tests
   are updated; `test_player_snapshot_capture.py` toggles the switch.
5. Rewrite the `handler.c` L3151 comment, the comment above `unowned_object` and the
   header of `scripts/item_ownership_audit.sh` to say what the reap does.
6. `run_world_restart_journey.py` passes in all its modes (they run in `make test-db`).

**As built**

1. ADR 0002 (`f3f21475a`): the "dropped item" consequence names the boot reap, and the
   "Releasing items" row says why a save never releases one. The item's third done-when
   clause was amended on GitLab as decision 8 says, with the reason.
2. and 3. The reap (`61fa52894`). `reap_unheld_player_items()` in
   `item_claim_repository.c` is one multi-table `DELETE` with the self-join for the
   child rows (a subquery on the deleted table is refused by MySQL), `LEFT JOIN`s on
   `player_items`, `auction_item_custody` and `artifact_domain_state`, and a
   `NOT EXISTS` on the player's `player_pet_items`; it repeats until a pass deletes
   nothing. `flatfile_item_repository_reap_unheld_player_items()` reads each player's
   file once under the authority lock, keeps the records of a file it cannot read,
   un-stales a container while a record that stays names it, and writes the catalog as
   `establish_owner()` does. `reap_unheld_player_items_at_boot()` in `comm.c` runs
   whichever backend is configured, right after the owner revisions are hydrated in
   `main()` and before `run_the_game()`; a failure is one `logs/log/status` line, and a
   count above zero is another (`Item ownership reap: records of items no player holds
   deleted=N`).
4. The two lines (`61fa52894`): `missing_payload_rows` in `player_load_materialize.c`
   and `unowned_object` in `player_snapshot_capture.c` are behind
   `persistence_trace_enabled()`, with the comment above the second rewritten. The two
   combat journeys set `DURIS_PERSISTENCE_TRACE=1`; `test_player_load_topology.py` and
   `test_orphan_item_session_regressions.py` pin the gated lines; seven harnesses that
   compile `player_snapshot_capture.c` stub the switch (`61fa52894` had five; the first
   `make test-all` found `test_locker_save_room.py` and
   `test_item_movement_input_queue.py`, which name the file through a path helper,
   `119dda91e`), and
   `test_player_snapshot_capture.py` records `logit()` and toggles it: three saves with
   it off write no line, two with it on write one each.
5. The `handler.c` comment, the audit script's header (and its `--help` range) say what
   the reap does (`61fa52894`). `PLAYER_SAVE_PIPELINE.md`, `DATABASE.md` and
   `CONFIGURATION.md` describe it; `TESTING.md` and `REGRESSIONS.md` describe its tests
   (`f77ff5022`).
6. `run_world_restart_journey.py taken` carries the real-path assertions; the other five
   modes run in `make test-db`.

**Differs from the plan**

- The journeys' characters `drop all` their starter kit after creation, and most of its
  items are `ITEM_TRANSIENT` ("dissolves when dropped"), so every journey's character
  has 26 creation-grant rows for items that no longer exist: the item's case at scale.
  The reap deletes them with the ghost or the mace, so the journeys assert "every player
  row left has a payload row" and "the rows whose items the save holds are the ones that
  stay", not "one row fewer". `taken` reads the status line's count as above one.
- The `taken` pickup never wrote `unowned_object`, even on the old build: the mini
  world's floor mace has an in-memory ledger entry from world recovery. The looted
  banana in the combat journeys has none, so with the switch on they require the line
  for it (`f44e37fde`), and `taken` keeps the default's "no line" check.
- The flat-file rule "a record that stays keeps its container" is in the code but its
  fixture is only in the MariaDB harness: `establish_owner()` refuses an owner that has
  saved, and a save re-points what it holds, so no API writes that catalog state. The
  rule exists for the foreign key, which is MariaDB's.

**Review round 1**

The review read `e0928db80` and, in a second pass, `028eb062e` (the same code), and left two
High findings, each a thread on the diff of !13.

1. **A crash after an item changed hands duplicated it** (finding 1, `0ca22fdcc`). A load
   skips a copy whose record names another owner, so a record naming a player who no
   longer holds the item is what keeps an older copy elsewhere out of play: after a crash
   that follows a hand-over, the giver's save still holds the item. The reap asked only
   whether the record's own player held it, deleted the record, and the older copy loaded
   beside the restored floor copy. It now deletes a player's active record only when no
   stored payload of anyone carries the uid: on MariaDB a `NOT EXISTS` each on
   `player_items`, `player_pet_items`, `locker_items`, `corpse_items` and `saved_items`;
   on flat-file every player file (the `players` directory) and the locker, corpse and
   room stores. Such a record stays while the copy can still load against it: the
   holder's next save drops the copy and the boot after it reaps the record. A flat-file
   player file or store the reap cannot read now stops the reap with nothing deleted (it
   used to keep only that player's records), since any record may be what keeps a copy in
   that file out.
2. **A crash after a flat-file purchase or grant lost the item** (finding 2,
   `0ca22fdcc`). The flat-file login delivers what a committed transfer left in the
   materialization store, and only while the record names the player; the reap read only
   the file. For each player that owns a record no payload carries, it now runs the
   load's own `flatfile_shop_trade_materialization_reconcile()` on the player's file and
   counts what it would deliver.

**Found on the way**

- Flat-file world recovery counted every ownership record as an owner, so a floor copy
  whose record names a character who does not hold it was left out of the restore, and
  the older copy that record keeps out was skipped at its load: finding 1's sequence lost
  the item on flat-file, on `master` too (the review called it a separate bug, read not
  run). `9f157be7a` counts a player's record only when the player's next load holds the
  item (its file, its pets, a delivery still pending), as MariaDB asks `player_items`.
- The two claim harnesses built a check's message before the reap it checks ran (the
  order of a call's arguments is unspecified), so a failure showed a stale count. Each
  reap now runs before its check (`0ca22fdcc`).

**Tests added in the round**

- `run_world_restart_journey.py handover`, a new `make test-db` leg (`world_restart_handover`):
  finding 1's crash on a real server. Taverek takes the banana after the first capture and
  the journey waits until the next player checkpoint has saved him with it; he gives it to
  Brannoc, who saves, drops it and saves, and the server is killed. After the boot the
  record still names Brannoc, Taverek loads without the banana (`load_skipped` in
  `logs/log/dupes`), the floor copy is back, and after Brannoc takes it and both save only
  Brannoc's `player_items` holds it.
- `player_save_claim_mysql_harness.cpp`: rows whose item another player's `player_items`,
  another player's pet, a locker, a corpse and a saved room item carry stay, and go once
  the copies are gone.
- `flatfile_player_save_claim_harness.cpp`: the same with a newcomer's file, a corpse, a
  room and a guild locker; the newcomer's load skips its handed-over copy; a creation
  grant committed after the player's last save keeps its record, the load delivers it,
  and once a save has carried it and the ring is used up the next reap takes the record;
  an unreadable player file stops the reap; world recovery counts what a load holds as
  owned and not a record that only keeps an older copy out.

**Shown to fail without the fix,** on the reviewed head `028eb062e` (built in a scratch
worktree): the MariaDB harness reaps 8 rows instead of 3 (the five that older copies
need), the flat-file harness reaps 12 records instead of 8 (the four that keep older
copies out and the pending grant's) and reaps on an unreadable file, and `handover` stops
with `the boot reaped the record that keeps Taverek's copy out`. A copy of `handover`
without that check, on the same server, ends with the banana in the `player_items` of
both characters.

**Differs from the review's proposals**

- Only the players that own a record no payload carries are reconciled, not every player
  the reap reads: the reconcile adds only items whose record names that player.
- The scenario waits for a checkpoint instead of racing one: the review's probe killed the
  server in the five seconds between a capture and the next checkpoint.
- No shop fixture for finding 2: the harness commits a creation grant, which writes the
  same materialization event a purchase does and goes through the same reconcile.

**Cost.** On `duris_dev` (69,576 rows) the SELECT with the DELETE's joins and conditions
finds the same 94 first-pass candidates as before, in 0.13 s. `EXPLAIN DELETE` shows each
payload check materialized once, so the unindexed `saved_items.obj_uid` is read once.

**Done when:** the three conditions in the item, the last one as amended above.

**State of the work**

- Branch `fix/11-ownership-reap`, from `master` at `1e3a464ca`: `6500b2f9e` (this
  file's ablation), `f3f21475a` (ADR), `61fa52894` (the reap, the two lines, their
  tests and documents), `f77ff5022` (test documents), `f44e37fde` (the traced pickup),
  `76d21809b` (this file, as built), `119dda91e` (two more harness stubs), `923135184`
  (this file's note of them), then this file's commit with the gate's result.
- Merge request !13 closes #11. The tag `log-review/phase-3-review-0` is the head the
  review reads.
- Shown to fail without the fix, on a server built from `master` under
  `bin/analysis`: `taken` stops with `the boot did not reap the dropped mace's record`,
  and the MariaDB combat journey with `the boot did not reap the ghost row` (all three
  variants).
- Run on the branch: `run_player_save_claim_mysql.sh`, `test_player_save_claim.py`,
  `test_player_snapshot_capture.py`, `test_boot_log_hygiene.py`,
  `test_orphan_item_session_regressions.py`, `test_player_load_topology.py`, the four
  other stubbed harnesses, `taken`, and both combat journeys (twice, the second with
  the traced-pickup assertion): all pass.
- The gate, on 2026-10-06:
  - `./scripts/format.sh --check`: clean.
  - `make -C src`: built.
  - `make test-db`: 45 of 45 passed in 339 s, on `76d21809b`. `world_restart_taken` took
    87 s, `mysql_combat` 164 s, `player_save_claim` 63 s, `world_capture` 104 s.
  - `make test-all`: 671 passed, 0 failed, in 457 s, on `923135184`. Its first run, on
    `76d21809b`, was 669 passed and 2 failed: `test_locker_save_room.py` and
    `test_item_movement_input_queue.py` did not link without the switch's stub
    (`119dda91e`). `make test-db` does not run either, and the server did not change
    between the two heads, so it was not run again.
- By hand, the fixed build on a copy of the long-lived development database (dumped,
  imported into a disposable MariaDB, the full world, one boot and a clean stop):
  69,576 rows before, 37,446 of them a player's active rows, 101 with no payload row (94
  reap candidates on the first pass and 7 containers whose contents were among them).
  The boot logged `Item ownership reap: records of items no player holds deleted=101`
  and stopped with `Normal termination`. After it: 69,475 rows, 37,345 player rows, each
  with a payload row, and the 31 room, 114 corpse, 31,972 locker and 13 destroyed rows
  as before; `item_owner_audit` and `item_owner_revision` unchanged; none of the 101 is
  left. 24 of the 101 named "player" 4,000,000,001, which is no pid: rows
  `item_transfer_mysql_harness.cpp` left on 2026-09-01 when it was run against that
  database.
- Review round 1 (2026-10-07): `0ca22fdcc` (findings 1 and 2), `9f157be7a` (flat-file
  world recovery, found on the way), then this file's commit with the round and its gate.
  The tag `log-review/phase-3-review-1` names that head.
- The round's gate, on 2026-10-07, on `9f157be7a`:
  - `./scripts/format.sh --check`: clean.
  - `make -C src`: built.
  - `make test-all`: 671 passed, 0 failed, in 465 s.
  - `make test-db`: 45 of 46 passed in 380 s. `world_restart_handover` took 87 s,
    `world_restart_taken` 85 s, `mysql_combat` 172 s, `player_save_claim` 44 s. The one
    failure, `sql_pool_interrupt` ("the pool lent a connection without the lock"), was a
    race in that leg: it kills the lock owner's session and asks the pool at once, but
    `KILL` returns before the server ends the session, and the lock goes only with it.
    This branch does not touch the pool.
- Fixed on `master`, each in its own commit, pushed as a fast-forward to `a7e43bd0a`:
  `2bc212690` (the leg waits until the server shows the lock free; two of four runs side
  by side still saw the killed session's lock on the first check), and `a7e43bd0a`
  (`make test-db` generates the world before its legs: run alone on a fresh worktree,
  `saved_item_allocator` booted before another leg had written `world.mob`). On `master`
  with both: `make test-db` 45 of 45 in 276 s from a worktree without a generated world,
  and the 51 tests that read `TESTING.md` or the `Makefile` pass.
- On a merge of that `master` with `9f157be7a` (scratch, not pushed): `make test-db` 46 of
  46 in 269 s, `world_restart_handover` among them.
- Landed on 2026-10-07 in `a55ccef17`: one `--no-ff` merge of the branch head
  (`43264d32d`) into `master` at `a7e43bd0a`, with no squash and no rebase, so both
  review tags still name the commits that were reviewed. The head is
  `log-review/phase-3-review-1` (`4694c74ea`) plus three documentation commits: the two
  working notes the owner added (`build-issues.md` and `fall-while-walking.md` in this
  folder) and the plan's landing line. `master` had moved (`2bc212690`, `a7e43bd0a`), so
  the gate ran again on the merge:
  - `./scripts/format.sh --check`: clean.
  - `make -C src`: built.
  - `make test-all`: 671 passed, 0 failed, in 464 s.
  - `make test-db`: 46 of 46 passed in 274 s.
  #11 is closed and the branch is deleted.
- Nothing is open.

---

## Phase 4: casts finish late when the event pass runs behind (#14)

**Status: landed in `7ef76523e`.** "State of the work" at the end of this phase has the
details.

**Checked.** `do_will` (L2193) and `do_cast` (L2558) each schedule a first segment of 1 to 4
pulses. `event_spellcast` schedules each further segment at L2759 to L2762 from the current
tick. All three go through `schedule_spellcast()` (L1241). `add_event` sets
`due_tick = ne_event_tick + delay` (`new_events.c` L904). The event pass knows how late the
running event is (L1651), and the continuation does not use it. `DelayCommune()` extends
the memorize event by the nominal segment, which still adds up to the cast time. The defect
follows from the code. Nobody has measured a late cast.

**Added by the check (2026-10-07).** Read again at `647e785d7`.

- There are four scheduling sites, not three. `MobCastSpell()` (`mobact.c` L821) schedules
  a mob's first segment with its own `add_event(event_spellcast, 4, ...)`; only its
  continuations go through `schedule_spellcast()`. A mob of level 60 or more, or with a
  cast of four pulses or less, calls `event_spellcast()` at once with no event, as
  `do_cast` does for `CMD_INSTACAST` and a weaved spell.
- `event_spellcast` has player priority only for a PC (`nevent_is_player_timed()`); a
  mob's cast is NORMAL priority and is deferred first. The `PLAYER EVENT TIMING` line is
  written for a PC's callbacks only, so the measurement sees players' casts.
- `spellcast_datatype` is copied into the event as a raw payload, zeroed by `memset` or
  `bzero` at its three construction sites, and persisted nowhere.
- `ne_event_tick` has no header; `comm.c`, `events.c` and `nevent_periodic.c` each
  declare it `extern`.
- `test_spell_schedule_failure_runtime.py` and `test_death_field_runtime.py` compile
  `schedule_spellcast()` (the second `event_spellcast()` and `MobCastSpell()` too)
  without `new_events.c`, so each must define the tick once the helper reads it.
  `test_elemental_aura_runtime.py` reads `event_spellcast` as text only.
- The event budget is checked every 64 scanned events, so the `--minimal` world never
  defers; load needs the full world. The full-world flat-file layout of
  `test_flatfile_full_world_boot.py` boots with no database, and with `CHAOS_MUD=TRUE` a
  new MindFlayer is level 56 and casts `adrenaline control` (18 pulses, five segments)
  through `do_will` with mana alone, as `run_spellcast_racial_multiplier_journey.py` does.
- `RUNBOOK.md` ("For casting complaints") states the defect. `EVENTS.md` and
  `CONFIGURATION.md` do not describe the segments.

**Ablated before the work started (2026-10-07).**

- Outcome: the item's three done-when conditions. Non-goals: `DelayCommune()` and the
  progress stars keep the nominal segment (decision 9); the scheduler's ordering, budgets
  and trace line do not change; a mob whose first `add_event()` is refused stays
  `AFF2_CASTING`, which is older than this item and not fixed here.
- The measurement is not a copy of `test_mysql_combat_journey.py`: its character is a
  warrior and it needs a MariaDB leg, and the measurement needs a caster and load.
  `tests/async/run_cast_timing_probe.py` boots the full world on the flat-file backend,
  creates the level-56 MindFlayer, casts `adrenaline control` a number of times and reads
  the trace: per cast, the start tick (the first segment's due tick less its length), the
  finish tick (the last callback's actual tick) and each callback's lateness. Load is the
  existing `DURIS_NEVENT_BUDGET_USEC` knob on the full world, not scripted mobs: a cut
  budget defers the pass's work every pulse, which is the condition the item describes.
  The script is committed so that step 4 and the review re-run it; `make test-all` does
  not run it.
- The fix is in `schedule_spellcast()` as planned, plus one line in `MobCastSpell()` so a
  mob's first segment carries its due tick; without it a mob's cast keeps its first
  callback's lateness. The field is `due_tick`, the tick the scheduled segment is due at.
  Zero means the cast has not been scheduled yet; a scheduled segment is always due at
  tick 1 or later, so zero cannot be a real value. The delay is the intended tick less
  the current one, at least 1, and the intended tick is kept when the minimum applies so
  that lateness larger than a segment carries forward.
- One harness, `test_cast_lateness_runtime.py`, modelled on the two above: the production
  `schedule_spellcast()`, `event_spellcast()` and `MobCastSpell()` with `add_event()`
  stubbed to record the delay, each callback run at its due tick plus an injected
  lateness. It pins exact finish ticks, not a model of the code.
- `RUNBOOK.md`'s sentence becomes the new rule; `REGRESSIONS.md` and `TESTING.md` get the
  test's entry as the earlier phases did.

**Files.** `src/core/structs.h`, `src/net/sparser.c`, `src/mob/mobact.c`;
`tests/async/test_cast_lateness_runtime.py` and `tests/async/run_cast_timing_probe.py`
(new), `tests/async/test_spell_schedule_failure_runtime.py` and
`tests/async/test_death_field_runtime.py` (the tick); `docs/operations/RUNBOOK.md`,
`docs/testing/REGRESSIONS.md`, `docs/guides/TESTING.md`; this file.

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

**As built**

1. **The measurement** (`0df20ac4a`, posted on the item at 15:39 on 2026-10-07). On a
   server built from `master` at `647e785d7`: with the default 25 ms budget on a quiet
   machine all 20 casts took exactly their 9 pulses and no callback was late (the only
   budget window was the boot's, 3 deferring pulses). With the budget cut to 2 ms (210
   deferring pulses, 1,981,482 deferred events, worst callback 19 pulses late) 12 of 20
   casts finished late, by 5.6 pulses on average and 22 at most (a 9-pulse cast took
   31), and every late cast's extra was exactly the sum of its callbacks' lateness. The
   last callback's lateness, which the fix leaves, was 1.85 on average and 9 at most.
2. **The fix.** `spellcast_datatype.due_tick` is the tick the scheduled segment is due
   at. `schedule_spellcast()` takes the segment's length: it advances `due_tick` from
   its old value, or from the current tick for a cast that has not been scheduled yet,
   and schedules for `due_tick - now`, at least 1. `MobCastSpell()` sets `due_tick` for
   the first segment it schedules itself. Both files declare `ne_event_tick` as
   `comm.c` does. `DelayCommune()`, the progress stars and the three construction sites
   of the payload (`memset`/`bzero`) did not change.
3. **The test.** `test_cast_lateness_runtime.py` compiles the production
   `schedule_spellcast()`, `event_spellcast()` and `MobCastSpell()` with a scheduler
   double that records each segment's delay and runs the callback at its due tick plus
   an injected lateness. Pinned, as exact ticks: casts of 1 to 20 pulses with no
   lateness take their cast time in segments of four and extend the memorize event by
   the nominal segments; the item's 12-pulse cast with three callbacks two late finishes
   in 14; only the last callback late gives cast time plus that; lateness before the
   last segment is made up in full; after a stall each remaining segment is one pulse;
   five segments all two late give 18 + 2 + 1; a mob's cast makes up its lateness as a
   player's does, so the `MobCastSpell()` line is covered. On `master`'s sources (the
   harness minus its one `due_tick` assertion, in a scratch worktree) the no-lateness
   loop passes and the item's example fails: 18, not 14.
   `test_spell_schedule_failure_runtime.py` and `test_death_field_runtime.py` define
   the tick they now link; the first also zeroes `due_tick` on the payload it reuses
   for its "fresh cast" retry, since a rejected payload dies with its cast in production
   and a new cast's payload is zeroed.
4. **The measurement again**, on the server built from `f461a9b91`. Default budget: all
   20 casts took exactly 9 pulses, none late. Budget cut to 2 ms (213 deferring pulses,
   2,250,592 deferred events, worst callback 21 late): 12 of 20 casts late, 5.0 extra
   pulses on average and 21 at most, with the callbacks' lateness summing to 6.3 on
   average and 24 at most. Every row is what the harness pins: `[5, 6, 7]` finished in
   24 pulses (27 before), `[3, 4, 4]` in 17 (20), `[1, 2, 0]` in 11 (12). The mean moved
   little because under that budget a callback runs 5 to 20 pulses late, more than the
   4- and 1-pulse segments after it, so the cast sits on the one-pulse minimum: the
   gain is bounded by the slack of the remaining segments, 3 pulses for this 9-pulse
   cast, which is the exception the item's bound allows for. A run at an 8 ms budget,
   where callbacks are late by a few pulses, is in "State of the work".
- **Documents.** `RUNBOOK.md`'s casting paragraph states the rule and names the probe.
  `REGRESSIONS.md` has the section "Casts that run behind the event pass", and
  `TESTING.md`'s samples table names the harness and the probe.

**Differs from the plan**

- Four scheduling sites, not three: `MobCastSpell()` gets one line (see "Added by the
  check").
- The measurement is `run_cast_timing_probe.py` on a flat-file full world, not a copy
  of the MariaDB combat journey (see "Ablated"). The cast time is not a constant: it
  depends on the character's `spell_pulse` and affects (the level-56 MindFlayer casts
  the 18-beat spell in 9 pulses, three segments of 4, 4 and 1), so the probe takes it
  from the run as the shortest cast, which is exact whenever a cast ran with no late
  callback.
- `schedule_spellcast()` keeps the intended tick when the one-pulse minimum applies,
  so lateness larger than a segment carries into the following segments; the plan said
  so and the harness pins it (`{10, 0, 0}` on a 12-pulse cast gives 16: the stall, then
  one pulse per remaining segment).

**Done when:** the three conditions in the item. The second condition's bound, cast time
plus the lateness of the last segment, is not attainable by any design once a callback is
later than the segments left after it, since those cannot run before it; the rule as
built, and as the closing note on #14 states it, is that bound except after such a stall,
where each remaining segment costs one pulse plus its own lateness.

**State of the work**

- Branch `fix/14-cast-lateness`, from `master` at `647e785d7`: `6dad532f7` (this file's
  ablation), `0df20ac4a` (the probe), `f461a9b91` (the fix, its tests and documents),
  then this file's commit with the gate's result.
- The probe ran six times on 2026-10-07, 20 casts each, on the server of `647e785d7`
  (before) and of `f461a9b91` (after), from the regression artifact cache:
  - default budget: before, 20 of 20 casts exactly 9 pulses; after, the same.
  - 2 ms budget: before, 12 late, extra mean 5.60 max 22, every extra the sum of the
    callbacks' lateness; after, 12 late, extra mean 5.00 max 21 against a summed
    lateness of mean 6.30 max 24.
  - 8 ms budget: before, 11 late, extra mean 8.00 max 46 (124 deferring pulses, worst
    callback 15 late); after, 9 late, extra mean 4.70 max 37 against a summed lateness
    of mean 5.75 max 40 (212 deferring pulses, worst callback 28 late: the load of a run
    is not repeatable, so the rows, not the means, are the comparison).
  - On the fixed build every row follows the rule: `[5, 1, 0]` took 12 pulses (15 on
    the old code), `[5, 2, 1]` 14 (17), `[1, 4, 7]` 20 (21), `[2, 2, 0]` 11 (13),
    `[0, 1, 1]` 11 (11: the lateness fell on the last segments).
  - Under these budgets a callback is late by 1 to 28 pulses, mostly more than the 4
    and 1 pulses of the segments after it, so the one-pulse minimum rules: on this
    9-pulse cast the fix can take back at most 3 pulses. A longer cast has more slack
    (an 18-pulse one, 10), and lateness of a pulse or two per callback is made up in
    full, as the harness shows; the real server with its default budget showed none.
- Run on the branch: `test_cast_lateness_runtime.py`,
  `test_spell_schedule_failure_runtime.py`, `test_death_field_runtime.py`: pass. The
  first, minus its `due_tick` assertion, fails on `master`'s sources at the item's
  example (18, not 14).
- Both measurements are posted on the item (15:39 and 15:51 on 2026-10-07).
- Merge request !14 closes #14. The tag `log-review/phase-4-review-0` is the head the
  review reads: `f461a9b91` plus this file's commit.
- The gate, on 2026-10-07, on `f461a9b91` with this file's edits in the tree:
  - `./scripts/format.sh --check`: clean.
  - `make -C src`: built (9 minutes: `structs.h` changed, so everything recompiled).
  - `make test-all`: 672 passed, 0 failed, in 576 s. `test_cast_lateness_runtime.py`
    is the 672nd.
  - `make test-db`: 46 of 46 passed in 275 s. `mysql_combat` took 160 s,
    `world_capture` 94 s, `game_loop_budget` 194 s, `chaos_raise` 86 s.
- The review (2026-10-07, on !14, of `b89a2d7a0`) left no finding. It checked the rule
  against the scheduler's contract, the anchor of the first segment at all four sites,
  the payload's zeroing and copying, and `MobCastSpell()`'s ignored refusal (unreachable
  for a live mob); it re-ran the three harnesses, the format check and the probe on the
  gate's own binary at a 2 ms budget (10 of 20 casts late, extra mean 4.55 and max 19,
  every row following the rule, none under 9 pulses). Its two observations are not
  defects: the item's literal bound is unattainable after a stall (noted under "Done
  when"), and paying one pulse per remaining segment after a stall is the per-segment
  design decision 9 keeps.
- Landed on 2026-10-07 in `7ef76523e`: one `--no-ff` merge of `log-review/phase-4-review-0`
  (`b89a2d7a0`) into `master`, with no squash and no rebase, so the tag still names the
  commit that was reviewed. `master` had not moved since the branch was made, so the
  merge's tree is the branch's and the gate above stands for it. #14 is closed and the
  branch is deleted.
- Nothing is open.

---

## Phase 5: telemetry schema check, SQL round trip and restart gaps (#17)

**Status: built, open for review as !15.** "State of the work" at the end of this phase
has the details.

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

**Added by the check (2026-10-07).** Read again at `ab4d91340`, on the branch.

- Their harness and its Python test were reshaped before the three commits, by their PR
  #591 (`34b6593b3`, 2026-10-01; the ledger's row for it says `N/A`, a hosted job). In
  that shape the harness takes host, port, user, password and database from the
  environment and no longer parses migration files; the Python test creates the database,
  applies the whole chain with `scripts/migration_runner.py` (`adopt --kind
  fresh_bootstrap`, then `run`) and checks the history's count and head against
  `migration_manifest.json`; and `every_record_kind_round_trip_tests()` writes each of
  the eight kinds, replays it for `duplicate_identical`, changes one field and requires
  `duplicate_conflict`. The `startup_contract_tests()` that `e0e837102` adds reads
  `fixture_database`, `fixture_user` and `fixture_password` from that shape, so the
  commit merges onto our harness without conflict and does not compile there. Steps 1
  and 2 are therefore #591's harness and test changes on our wrapper. Not taken from
  #591: `run_telemetry_repository_sql.sh` (its own container and a loopback proxy), the
  hosted workflow, its Makefile lines and its `migration_runner.py` message change.
- The repository's replay check is the read-back the item asks for: `apply_record()`
  selects every mapped column of the stored row by the replay key and `equal_row()`
  compares each with the record's serialized value, so `duplicate_identical` is only
  returned when every field matched. `typed_extension_mapping_tests()` names the
  progression, encounter and combat columns in SQL, and the golden tests read the
  interval and checkpoint columns, so a mapping to an existing column of the wrong name
  is caught there. A column name the table lacks fails the INSERT with 1054.
- `IMPLEMENTATION_STATUS.md` is new in `e0e837102` and is their delivery record for the
  balance expansion: pending rows, their hosts, their follow-up PRs. Documents here hold
  no open-work lists, so it is not taken from any of the three commits, and step 5's
  resolution is a deletion. `BALANCE_EXPANSION_PLAN.md`, `RECOVERED_FOLLOWUPS.md` and
  `scripts/telemetry/preflight.py` are not taken either.
- `03da1882d` adds `TELEMETRY_OUTAGE_LEDGER_DIR` to `.env.example` (required when
  telemetry is on; capture is refused without it), `telemetry_outage.o` to
  `src/Makefile`, `scripts/telemetry/outage.py` (a read-only export of the evidence)
  and `docs/telemetry/OUTAGE_STORAGE.md`.
- `b3fb28b9f`'s parent is `9b5c23fec`, three commits after `03da1882d`. None of the
  three touches `src/`; `9b5c23fec` touches three rollup and report tests only.
- `test_telemetry_connection.py` keeps its own `TELEMETRY_REPOSITORY_DISPOSABLE` guard;
  it is a different test, skipped by `make test-all`, and is not changed.

**Ablated before the work started (2026-10-07).**

- Outcome: the item's four done-when conditions. Non-goals: a replayed spool
  (decision 10); a MySQL leg (the gate runs on the wrapper's MariaDB, like every other
  leg); their hosted workflow; any descriptor refactor beyond what `e0e837102` carries.
- The Python test reads the wrapper's `TEST_DB_HOST`, `TEST_DB_PORT`, `TEST_DB_USER`
  and `TEST_DB_PASSWORD`, as `run_mysql_deletion_journey.py` does, builds the same
  `DB_*` environment the migration runner needs, and hands it to the harness. Not
  taken from #591: the `TELEMETRY_REPOSITORY_*` names, the disposable acknowledgement
  and the port list (the wrapper's container is disposable by construction, as for
  every other leg), the engine name, the harness's own history count (the Python test
  checks the head) and `fixture_safety_contract()`.
- `--sql-fixture` stays the flag. With it, a missing `TEST_DB_*` setting is an error,
  which is how the leg cannot report the SQL part as skipped. Without it, as in
  `make test-all`, the test compiles the harness and prints `SKIPPED`, as today.
- The database is `duris_telemetry_test` on the wrapper's server and dies with the
  container; the test does not drop it.
- The leg is one line in `tests/run_db_tests.sh`.

**Files.** `tests/async/test_telemetry_repository.py`,
`tests/async/telemetry_repository_harness.cc`, `tests/run_db_tests.sh`,
`docs/telemetry/DATABASE.md`, `docs/guides/TESTING.md`, `docs/testing/REGRESSIONS.md`;
then the files of the three picks less the four documents and the script above,
`docs/README_docs.md` (the outage document), `.env.example`,
`docs/records/COMMUNITY_DURIS_TRACKING.md`; this file.

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

**As built**

1. **The gate (steps 1 and 2).** `test_telemetry_repository.py --sql-fixture` takes the
   wrapper's `TEST_DB_*`, creates `duris_telemetry_test`, applies the chain with
   `migration_runner.py` (36 steps through `0036_log_entries_ipv6`) and checks the
   history head, then runs the harness with the `DB_*` settings; a missing setting is an
   error. The harness is #591's: every record kind 1 to 8 is written, replayed for
   `duplicate_identical` and changed for `duplicate_conflict`. The leg is
   `telemetry_repository` in `run_db_tests.sh`, 19 s. On today's code (`ab4d91340`) it
   passes on MariaDB 10.11.19: no record kind needed a fix before step 3. Probed: with
   `session_boot_id` misspelt in `session_fields()` (a column the Python mapping contract
   does not cover) the harness fails on the first INSERT and the leg exits 1.
   `DATABASE.md` names the leg and the command.

2. **Part 1** (`f7368e60e`, the pick of `e0e837102` with the four documents and the
   script dropped, author kept). It merged cleanly and compiled on the step-1 harness.
   Reviewing it found a defect it did not fix: the transport opened the circuit on a
   refused repository start with `permanent_repository` and error 0, never reading the
   repository's health, so the operator line said that for a schema or a grant refusal
   alike; and the check's own mismatches (type, index, engine) borrowed SQL error 1054,
   the missing-column code. `ce09d17bc` fixes both: `telemetry_schema_check` (table,
   column, column-type, index, engine) in the health snapshot, set by the repository
   and carried by the transport through an optional `health` callback on the repository
   binding (defaulted, so the harness bindings compile unchanged), printed as
   `schema_check=` on the `telemetry_health` line and by `world telemetry`, and part of
   the monitor's failure signature. The repository harness pins the kind and the code
   per case and gains a renamed progression column; the transport harness pins the
   carried cause. `run_telemetry_schema_boot_journey.py` boots a real server with
   telemetry on: whole chain (healthy), one progression column renamed (the boot gate
   refuses the schema with COMPAT-E003 before telemetry runs, so on this tree a drifted
   telemetry table never reaches the writer), a writer that may only SELECT
   (`permanent-permission error=1142 schema_check=none`, game running, nothing admitted)
   and, with `--misnamed-server`, a build whose `telemetry_columns.inc` names a column
   the chain lacks (`permanent-schema error=1054 schema_check=column`, game running):
   the production incident of the item, reproduced on a running server. It is the
   `telemetry_schema_boot` leg of `make test-db`, 20 s. On the binary of `f7368e60e`
   the SELECT-only writer logged `permanent-repository error=0`. `RUNBOOK.md` lists the
   causes; `DATABASE.md` names the journey.

3. **Part 3** (`476376592`, the pick of `03da1882d`; author kept). The data-lifecycle
   conflicts were resolved by adding only the ledger's entry (23 non-database stores),
   the validator's one check and the test's one case; their two status documents stay
   out, `OUTAGE_STORAGE.md` is reworded without their follow-up numbers and indexed in
   `README_docs.md`. Their two tests (`test_telemetry_outage.py`: lifecycle, protected
   paths, corruption, a real SIGKILL, a real exec and restart, the producer quota, the
   offline export; `test_telemetry_runtime_outage.py`: registration before SQL init,
   clean drain and restart, transient SQL recovery, a shutdown with an unresolved
   commit, disk-full) pass here, as do the harnesses the transport change touches.
   `TELEMETRY_OUTAGE_LEDGER_DIR` is required once telemetry is on: without it the
   server logged `permanent-repository error=22` and ran on, as designed. On the real
   server (the schema boot journey, `bc763f090`): a SIGTERM leaves the producer `clean_drained`; a copyover leaves the
   copied-over producer `unknown_tail` and the new image `clean_drained`; a SIGKILL
   leaves `running` until the next producer registers, then `unknown_tail`. The
   copyover result is an observation, not a defect of the item: the flush before the
   exec is durable, but no terminal sample is written, so the record says only that
   coverage after the last sample is unknown, which is the conservative reading the
   document gives `unknown_tail`. Writing that sample before the exec would be a
   change to the copyover path, left out of this phase.

4. **Step 5** (`95cf073c7`, the pick of `b3fb28b9f`; author kept). The two status
   documents stay out and the `SESSION_LIFECYCLE.md` paragraph ends without the pointer to
   them. `structs.h` now includes `telemetry_types.h`, so everything recompiled (36 s
   here). Its adapter, hook and copyover-format tests pass, and the schema boot journey's
   copyover case still shows the copied-over producer as an unknown tail: that commit is
   about sessions, not the ledger.
5. **Step 6.** The ledger's telemetry row is `Adopted` with the three commits and the two
   on top; PR #591's row is `Adapted` with `38c59e6fe`. `REGRESSIONS.md` has the section
   "Telemetry writer: schema check, round trip and the gap record" and `TESTING.md`'s
   samples table a telemetry row (`04ccf6a2c`).

**Differs from the plan**

- Steps 1 and 2 are PR #591's harness and test on our wrapper, not a new harness (see
  "Added by the check"). The read-back is the repository's own replay comparison.
- Part 1 needed a fix of our own on top of the pick (`ce09d17bc`): the transport reported
  every refused start as `permanent_repository` with error 0, so the item's "told apart in
  one operator message" was not met by the pick alone, and its synthetic mismatches
  borrowed SQL error 1054. The `telemetry_schema_check` field, the binding's `health`
  callback and the `schema_check=` output are ours.
- The schema cases of the item's first condition are detected by the persistence boot
  gate (`COMPAT-E003`) before telemetry on a real server, because the telemetry tables are
  in the runtime fingerprint. The telemetry check matters for grants and for a writer
  whose column list disagrees with the migrations, the production incident; the journey
  proves both on a running server, the second with a variant build
  (`bin/analysis/misnamed`, two lines added to `telemetry_columns.inc`, built with its own
  `OBJDIR`; the recipe is in "State of the work").
- The plan's step 4 tests (shutdown, copyover, kill "during a simulated SQL outage") are
  their harnesses (simulated faults, real SIGKILL and exec at the journal level) plus the
  journey's real-server stop, copyover and kill without an outage. A real-server outage
  with queued records is not simulated (see the regression notes' "Not covered").
- `IMPLEMENTATION_STATUS.md` is deleted at each pick rather than "resolved to describe our
  tree" (see "Added by the check").
- Three documents of ours changed that the plan did not list: `RUNBOOK.md` (the causes
  on the health line), `README_docs.md` (the outage document) and `.env.example` (the
  ledger directory, from the pick).

**Done when:** the four conditions in the item. On this tree the first condition's
schema cases are met twice over: the persistence boot gate refuses a drifted telemetry
table before the game starts, and the writer's own check refuses, with the cause named,
what that gate cannot see (a grant, or a writer whose columns the chain lacks). The
fourth condition is met by the gap record (`unknown_tail`, or `abandoned` with the
unattempted count), never by a replay; decision 10.

**State of the work**

- Branch `fix/17-telemetry`, from `master` at `ab4d91340`: `e2ca538f4` (this file's
  ablation), `38c59e6fe` (the gate: the round-trip leg), `f7368e60e` (pick of
  `e0e837102`), `ce09d17bc` (the cause on the operator line, the schema boot journey and
  its leg), `2ec01dc7c` (plan), `476376592` (pick of `03da1882d`), `bc763f090` (the ledger
  read on a real server), `683daafeb` (plan), `95cf073c7` (pick of `b3fb28b9f`),
  `04ccf6a2c` (regression notes, testing sample, ledger rows), `360838fc4` (plan),
  `426bb5557` (three lifecycle tests pin 221 entries), then this file's commit with the
  gate's result.
- The two new `make test-db` legs: `telemetry_repository` (the SQL harness, about 70 s)
  and `telemetry_schema_boot` (the journey, about 20 s). The journey's optional
  `--misnamed-server` case is not in the leg; the build it needs is two lines in
  `src/telemetry/telemetry_columns.inc` (`TELEMETRY_COLUMN(combat_damage_dealtx, bigint,
  true, 0U)` after `combat_damage_dealt`, and the matching
  `TELEMETRY_TABLE_COLUMN(telemetry_interval, combat_damage_dealtx, true, false,
  null_value)`), built with `make -C src OBJDIR=$PWD/bin/analysis/misnamed/objects
  DMS_BINARY=$PWD/bin/analysis/misnamed/dms_misnamed`, then `git checkout` and `touch`
  the file. Run on 2026-10-07 after every pick, last on `04ccf6a2c`'s tree: the game
  ran and the line said `permanent-schema error=1054 schema_check=column`.
- Before `ce09d17bc` (the tree of `f7368e60e`, built in a scratch worktree), the same
  journey's SELECT-only writer logged `permanent-repository error=0` and its healthy
  boot had no `schema_check=` field.
- `make test-all` on `360838fc4` found the three count pins (671 of 674); fixed in
  `426bb5557`.
- The gate, on 2026-10-07, on `426bb5557`'s tree:
  - `./scripts/format.sh --check`: clean (checked at every commit).
  - `make -C src`: built.
  - `make test-all`: 674 passed, 0 failed, in 466 s (8 min 15 s with the build).
  - `make test-db`: 48 of 48 passed in 469 s. `telemetry_repository` took 43 s,
    `telemetry_schema_boot` 44 s, `game_loop_budget` 215 s, `mysql_combat` 194 s.
- Merge request !15 closes #17. The tag `log-review/phase-5-review-0` is the head
  the review reads: `426bb5557` plus this file's commit. The measurements of the
  journey, before and after `ce09d17bc`, are posted on #17.
- Left for the review: nothing known. Two observations are recorded under "Differs from
  the plan" and in the regression notes' "Not covered": the persistence boot gate refuses
  a drifted telemetry table before the writer sees it, and a copyover leaves the
  copied-over producer an unknown tail.
