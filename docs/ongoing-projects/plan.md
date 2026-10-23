# Issue #264: qualify the full pwipe lifecycle

Status: implementation started 2026-10-24; full wipe readiness remains OPEN.
Prepared 2026-10-23 for [#264](https://github.com/LuminariMUD/Duris/issues/264),
the **Wipe system** readiness item in [#97](https://github.com/LuminariMUD/Duris/issues/97).
Implementation branch: `branch/issue-264-pwipe-qualification`.
Source baseline: [master `e2a2166f34fc`](https://github.com/LuminariMUD/Duris/commit/e2a2166f34fc56b814d553feed0a43d952b4a4d2).
Issue #264 had no comments when inspected. This plan covers its seven review areas,
four verification requirements, and four completion criteria. The latest master #245
plan is preserved in [plan-issue-245.md](plan-issue-245.md).

## Outcome, non-goals, files, and proof

**Outcome:** one supported, recoverable pwipe workflow that resets precisely the
agreed seasonal state, preserves approved carryovers, remains fenced after an
incomplete reset, and reaches a playable new season without old state returning.
Readiness requires command -> launcher -> filesystem -> startup -> fresh character
-> save/rent -> reconnect -> second reboot evidence, plus failure/retry evidence.
A SQL success message or passing source checks is insufficient.

**Non-goals:** production wipe/deployment, general persistence redesign, a new
wipe service/framework, privacy-retention policy changes, deleting audit history
merely because it is old, unrelated cleanup, and adding a new flat-file pwipe
feature. Existing flat-file builds reject this command; qualify that rejection
and document the support boundary. The issue requires supported modes and coverage
gaps to be recorded, not an invented promise of backend parity. A later request for
flat-file wipe support requires an explicit scope extension and revised estimate.

**Files:** start with `src/cmd/actwiz.c`, `src/sql/sql.c`, `src/net/comm.c`,
`scripts/cycle_mud.sh`, `Players/wipers/wipe_it_all`, and
`deploy/systemd/duris-mud-production.service.in`. Follow the writer/replay/retention
consumers below; change them only where a reproduced failure or reset requirement
needs it. Use existing lifecycle/migration manifests, additive migrations if needed,
`docs/operations/RUNBOOK.md`, `docs/operations/CONFIGURATION.md`,
`docs/testing/REGRESSIONS.md`, and focused `tests/async/` tests. Keep this plan current.

**Proof:** disposable MariaDB/Redis, private runtime directories, synthetic accounts;
real server/launcher execution; targeted writer/failure tests; SQL/filesystem/Redis
postconditions; new-season gameplay; required builds/formatting. No production
operation is authorized by this plan. No C/C++ build or destructive runtime test
was run during planning.

## Current continuation — artifact retirement

Branch `branch/issue-264-artifact-reset`, based on collector PR #323 at `025a6da7c`.
Review-ready PR #324 (https://github.com/LuminariMUD/Duris/pull/324), implementation
`527a3cafb`; committed and pushed after this handoff update.
Outcome: clear current artifact ownership, timers and souls while retaining retired
canonical UIDs, rejected UIDs, delivery markers and immutable history. Reuse the
existing retired/absent identity states so both runtime and SQL delivery recovery
recognize old bodies as retired and new bodies may spawn. Keep ledger revisions and
baseline history unchanged: current repository revisions derive from the greatest
ledger/baseline revision; historical outcomes do not replay gameplay snapshots.
Non-goals: deleting audit/baselines, new schema, or a second artifact lifecycle.
Files: SQL reset/manifest, existing native SQL and artifact boot tests, runbook/plan,
and the existing reconciliation check (domain-only retired rows are valid history).
Proof: seeded owned/retired/unresolved records, actual reset and boot/population/new
creation, old pending-delivery and receipt replay, retained history/revision, and
failed-update fencing. The full native SQL/launcher matrix passed, including the
actual boot/population/creation/save/reload executable and old pending delivery/
receipt replay. All existing artifact snapshot cases passed under UBSan. The
reconciliation tool now accepts cleared domain-only identity history and returned
zero for all checks against the reset DB; baseline and ledger rows were unchanged.
MariaDB and flat-file development builds, optimized MariaDB production build,
12 season-manifest and 14 lifecycle checks and reset-fence contracts passed.
Commit hooks passed; PR #324 is ready for review. Full readiness stays open.
Next concrete consumer: prepared cargo commands in `divine_trade_repository.c`
validate market generation/book state, player wallet/account and ship owner/preimage.
Ships and players have monotonic IDs, so prove stale prepared commands reject after
reset before adding epoch/cutoff machinery. Ordinary critical outbox receipts do not
replay wallets; `comm.c` documents that the old journal directory now holds only
locker identification receipts. Trace actual consumers, not historical names.

## Current continuation — collector retirement and recovery view

Branch `branch/issue-264-collector-reset`, based on PR #322 at `297045583`.
Review-ready PR #323 (https://github.com/LuminariMUD/Duris/pull/323), implementation
`b0b7206c0`; all changes are committed and pushed after this handoff update.
Outcome: use existing `collector::reason::season_reset` cancellations through the
normal audited critical repository. Candidates close; held stock moves to destroyed
custody; record blobs, payloads, receipts and listing-ID allocation survive. Derive
operation identity from reset epoch/listing. Preflight validates pending records and
held payload/custody after writer drain, before advancing the epoch. Reset then
commits each normal command; retry skips already-terminal rows. Normal bootstrap
must omit terminal history whose beneficiary is retired, so protected old receipts
do not consume the new season's bounded catalog. The reset scan needs pending rows
across all owners, including deleted beneficiaries. Reuse the existing bootstrap,
codec and command executor; no new store, binary offsets or un-audited status patch.
Files: SQL orchestration, collector bootstrap query/header, existing native DB tests,
manifest and runbook/plan. Proof: real candidate/held/paused records, destruction
ledger, restart view, receipt/payload/ID retention, stale purchase refusal and failure/
retry fencing. Positive native cases and the existing full SQL collector suite
passed; the final matrix now includes real pre-reset purchase rejection, new-owner
bootstrap, corrupt payload, delegated schema loss and partial cancellation/retry.
Preflight reuses the existing runtime metadata fingerprint rather than duplicating
all delegated writer column lists. The complete native matrix and existing SQL collector
suite passed, together with the real writer/quiescence harness, reset-fence/reward
contracts, 12 season-manifest and 14 lifecycle checks. MariaDB and flat-file development
builds and the optimized MariaDB production build passed. Final review confirmed the
authoritative cache accepts an equal-revision refresh when retired history disappears;
no extra revision mechanism is needed. The final native matrix and incremental
MariaDB build passed after review; formatting/tidy hooks passed. Full readiness
remains open. Next: artifact current ownership and compatible reconciliation baselines;
`src/guild/artifact.c` loads `artifact_domain_state` unscoped after the old legacy
rows have been wiped. Inspect its history/recovery consumers before choosing reset
semantics; retain immutable history and monotonic identity/revision allocation.

## Current continuation — retire active Divine Boons

Branch `branch/issue-264-divine-reset`, stacked on kingdom PR #321 at `2640ae94d`
(https://github.com/LuminariMUD/Duris/pull/321), review-ready.
Published as PR #322 (https://github.com/LuminariMUD/Duris/pull/322), implementation
`af12278b2`; current worktree is clean and pushed after this handoff update.
Outcome: retire old active objectives and selection-repeat preferences in one
versioned state transition, while preserving monotonic boon IDs, staff recent history,
mode/pause configuration and protected cargo-book identities. Reuse the existing
model serializer/repository CAS; no new schema or blanket ledger deletion. Validate
the existing snapshot before crossing the reset boundary. Files: existing boon model/
repository, SQL/manifest, native model/DB tests and docs. Proof: seeded active EXP and
cargo slots, empty post-reset slots/history, retained IDs/audit/config, idempotent
repeat, corrupt-state preflight and failed durable update fencing. The ASan/UBSan model
test and actual SQL/native matrix passed, including a database-triggered failed
update followed by one repaired retirement. Both development backends and the
optimized MariaDB production build passed, as did all 12 season-manifest checks,
14 lifecycle tests, reward/SQL contracts and diff checks. Commit hooks passed
and PR #322 is ready for review; earlier five-minute evidence is reused for unchanged
reset paths. No readiness sign-off, merge, release tag or deployment is claimed.

Next retained-state consumers to trace after collector PR #323: artifact current ownership/baselines in
`src/guild/artifact.c` and prepared cargo replay in
`src/economy/divine_trade_repository.c`. Old financial commands must not restore
wiped cargo/market/player after-images. Preserve audit/receipt evidence and prove
actual startup/recovery behavior before closing those W1/W2/W4 items. SQL-stage
resume/restore, Redis-on/external cutover, flat-file rejection and full system-service
qualification also remain. Do not sign off readiness from the completed chunks.

## Kingdom reset delivery

Branch `branch/issue-264-kingdom-reset`, stacked on reward retry PR #318 at
`b35af6d08` (https://github.com/LuminariMUD/Duris/pull/318), review-ready.
Outcome: remove realm resources/territory, purchased garrisons and legacy land before
removing their association owners. Those association IDs are reused; current SQL
loads are unscoped by season. Add the three real stores to preflight, postflight and
the existing lifecycle classifications. Non-goals: new schema, realm mechanics,
protected historical ledgers or another reset manifest. Files: SQL, manifest,
existing native SQL journey, runbook/plan. Proof: seed real positive world rows,
execute the actual reset, reuse an association ID and prove no holdings/guards;
missing-store preflight must preserve the old epoch. The actual SQL journey passed
positive territory/resource/guard deletion, association-ID reuse and missing-store
preflight; both builds passed. It exposed another stale source-test schema list,
now replaced with the same sealed migration inventory already used by the lifecycle
validator. All 12 reset-manifest and 14 lifecycle checks, both builds, and hooks
passed before publishing PR #321.

## Reward retry delivery

Branch `branch/issue-264-reward-retries`, based on PR #317 at `7fc360575`.
Outcome: bind reward-policy eligibility and its committed stamp to the fixed SQL
reset start and validate the current resetting epoch. Preserve the 28-day business
protection between distinct resets, while making same-reset retries safe even
months later. Clear old summon/body links regardless of that protection window.
Files: existing account reward hook/config, native DB harness, regression docs/plan.
Proof: real hook on the private migrated DB, both preserve modes, expiry/finite and
permanent grants, same/distinct reset timing, rollback and lost-ACK retries; focused
builds/contracts. Non-goals: new schema, ledger or migration framework, and changing
approved grant rates/lifetimes. Existing singleton + policy timestamp suffice.
The real hook/private-DB matrix passed, including invalid boundaries, delayed
retries, fixed-boundary 28-day protection, both configurations, rollback and lost
ACK. Both backend builds and the exact reward source contract passed; format/hooks
and publication passed. Published as PR #318 at `b35af6d08`. Full readiness remains open.

## Implementation handoff — 2026-10-24

- Reused `/home/aiwithapex/projects/duris-issue264-plan`, clean at `1ec58eee5`;
  merged current master `7d3bd3b95` as `3031b0fef` without rewriting history.
  Merge hooks passed changed-line format and tidy. Preserved current master’s
  Divine Boons plan in `plan-issue-245.md`; this document remains the #264 plan.
- First focused dependency: remove the validator/test's duplicate hand-maintained
  schema lists. Reuse the migration runner's sealed, ordered manifest plus the
  two supported bootstrap sources. This covers 200 SQL tables on this revision,
  including recent Divine trade state; no reset behavior or retention policy changes.
  Found and repaired phantom foreign-key dependencies from tables dropped by later
  supported migrations; the complete sequence exposed this validator crash.
  Proof: `python3 tests/async/test_data_lifecycle_manifest.py` (14 passed),
  `python3 scripts/validate_data_lifecycle.py` (200 SQL tables, 30 other stores,
  42 Redis surfaces). No C/C++ change: no server rebuild needed.
- The wider migration-runner check exposed an existing test tied to “last migration”
  instead of its reviewed manifest prefix. Corrected that test separately, matching
  the other reviewed-online-migration fixtures; all 23 runner tests passed.
- PR #309: https://github.com/LuminariMUD/Duris/pull/309, review-ready at `470c9c92a`.
- Current chunk: W3 SQL-to-launcher completion/failure contract, including fenced
  post-boundary failures, durable SQL-ready state and guarded filesystem completion.
  W2 writer drain and W4 completeness/carryovers remain required before runtime
  readiness. No production actions, readiness sign-off or release tag.
- The baseline list failures were repaired on master before this continuation;
  removing the remaining duplication prevents the same drift recurring.

### SQL/filesystem handoff chunk (stacked after PR #309)

Outcome: keep boot fenced through filesystem deletion and distinguish failed stops
from deletion permission. Files: existing SQL/comm/launcher/wiper/service paths,
runbook, regression index and focused handoff tests. Non-goals for this chunk:
writer-drain/completeness/carryover policy repairs, full gameplay and deployment.
Those remain required for the overall issue. Ablation removed a proposed migration:
existing status + completion timestamp already encode the SQL-ready handoff.

- `resetting`/NULL completion: SQL incomplete, no file cleanup permitted.
  `resetting`/timestamp: SQL/Redis/rewards ready, filesystem still fenced.
  `active`/timestamp: full handoff complete. Launcher final activation is guarded
  by epoch; duplicate completion never deletes newly created files.
- Exit 55 requires acknowledged SQL readiness; 58 stops incomplete resets.
  Launcher additionally checks the boot epoch's successor before cleanup and
  preserves both statuses. Production unit prevents automatic restart for both.
- Filesystem preflight validates every fixed legacy target before deletion and
  is invoked before SQL's irreversible boundary; cleanup revalidates. SQL reward
  failure now prevents SQL-ready publication. SQL-stage resume is still unimplemented;
  matched restore is the documented safe recovery route for that stage.
- Proven: 4 executable filesystem/launcher-contract tests; SQL completion, durable
  fence, existing quiescence/source-manifest and both Redis source contracts passed.
  `run_pwipe_handoff_mysql.py` applied the sealed sequence on a private MariaDB 10.11,
  matched all 200 actual tables, executed native begin/ready/boot-fence functions,
  and passed real launcher resume/failure/retry/lost-ACK cases. This is a handoff
  journey, not the full command-to-fresh-gameplay acceptance journey.
- Both builds passed: `make -C src -j4 PERSISTENCE_BACKEND=mariadb` and
  `make -C src -j4 PERSISTENCE_BACKEND=flatfile BIN_ROOT=$PWD/bin/qualification-flatfile`.
  `format.sh --check`, shell syntax,
  runtime compatibility validation and `git diff --check` passed.
- Executed the exact production restart properties in isolated user-systemd transient
  services: after 12 seconds, exits 55 and 58 had one invocation each; reboot exit 52
  had two. All fixture units stopped/reset afterward. This proves restart policy,
  not the full installed system-service sandbox.
- Remaining W3 proof: actual server exit/handoff in W6, interruption at the process
  boundary, full installed service sandbox and SQL-stage recovery. W2, W4, W5 and
  the fresh-gameplay journey remain open. Do not sign off #264 or #97.

- Follow-up on PR #311: the normal `sql_clear_zone_trophy()` queues on the writer.
  Pwipe must perform its own zone reset through the main SQL connection after the
  gate closes. Replaced that call and extended the private DB harness to compile
  and execute the actual full `sql_pwipe()` and its schema pre/postflight. That
  executable passed with the real MariaDB schema and zone reset assertions; both
  backend incremental rebuilds passed. This remains a controlled-peripheral SQL
  journey, not the real game command journey.

### Writer-quiescence chunk (stacked after PR #310)

PR #310: https://github.com/LuminariMUD/Duris/pull/310 at `3224c38d1`, ready for review.
Current outcome: drain accepted coordinator/outbox/maintenance/player/locker/artifact
work before SQL's boundary, then close the actual shared writer's admission gate.
Reuse existing drains; add only reversible quiesce/resume at the one writer because
player-pipeline quiescence alone does not cover SQL, banks and world-save jobs.
Pre-boundary failure resumes existing workers; an ambiguous boundary never resumes.
Suppress post-reset kingdom writeback and the remaining old-world pulse, and join
the drained writer on pwipe exit. Full W2 is still open for external/direct writers
and startup recovery isolation; W4/W5/W6 are still required.

- Found a concrete outbox defect: quiesce only changed health, while its background
  loop continued polling. Quiesced workers now poll only to satisfy an explicit
  drain; game-thread preparation closes admission again after publication callbacks.
- Proof: real shared-writer held/callback/late-refusal/abort-resume and accepted-write
  failure tests pass; existing worker and coordinator suites pass, as do copyover
  guards and durable-boundary checks. Both final backend incremental builds passed.
  `bash tests/async/run_critical_command_schema_mysql.sh` passed on private MySQL 8,
  including actual pause/drain/resume and the existing 60-second audit cadence case.
  Source modified time precedes the executed outbox binary; no repeated full suite
  is needed for unchanged outbox code. Required format/tidy hooks run at commit.
- Owner decision, 2026-10-24: **reset all account-bank balances; recreate only
  level-62 staff (Overlords)**. All other characters are wiped, including staff below
  62. Preserve the associated accounts; recreation must not restore seasonal items,
  money, progression or ownership. Implemented in #312/#313 and exercised through
  real login/gameplay in #317; historical notes below describe that delivery.
- No production operations.

### Seasonal bank reset chunk (stacked after PR #311)

PR #311: https://github.com/LuminariMUD/Duris/pull/311 at `2f123996e`, review-ready.
Owner explicitly confirmed all bank balances reset and only level-62 Overlords are
recreated. This chunk deletes every `account_banks` row, adds it to reset preflight
and postflight, and corrects its existing lifecycle classification. Accounts,
credentials/donations, historical currency baselines/ledger and monotonic bank IDs
survive. A recreated bank gets a new ID and zero initial balances, so old baseline
identity is never reused. No schema migration, account deletion, history purge or
new reconciliation framework is needed. Exact Overlord recreation and persistent
old-operation replay isolation remain next work; this is not full W4 completion.
Proof: `python3 tests/async/run_pwipe_handoff_mysql.py` passed the actual full
SQL reset with nonzero banks on Good/Evil/neutral, unchanged account credentials
and donation history, retained old baseline, fresh bank ID and zero defaults.
All 14 lifecycle and 12 season-manifest checks passed, as did the standalone
validator (200/30/42), both backend incremental builds and `git diff --check`.
No production operations.

### Exact level-62 Overlord recreation (stacked after PR #312)

PR #312: https://github.com/LuminariMUD/Duris/pull/312 at `d8919da5f`, review-ready.
Outcome: recreate only current exact level-62 staff under the same accounts/names,
with new monotonic PIDs and clean progression/assets. In one transaction snapshot
only their identity/physical template, retire all old rows under reserved `~pwipe-PID`
names, insert clean staff and opening baselines, and restore only those account links.
Retired SQL history stays inactive; names become available without reusing ledger IDs.
Clear old summon-to-body links independently of the 28-day grant-decrement guard.
No durable table/framework or old inventory/preferences copy is needed. Files: SQL,
existing native DB journey/source contract and runbook. Proof: extend the actual SQL
journey with levels 56/61/62/63, new identity/baseline/zero assets/name reuse; full login
proof and replay isolation still belong to W6/W4. The native SQL journey passed
exact-level selection, clean fresh identities/baselines, account mapping and mortal
name reuse; an injected mid-recreation SQL failure rolled back the entire roster
and left the SQL fence in place. Both backend builds and focused source/lifecycle
checks passed (14 lifecycle tests, 12 manifest checks plus SQL/fence/writer tests).
The final test extension removed a required recreation column and proved a
pre-boundary refusal with unchanged epoch; it and commit hooks passed before #313
was published.

### Runtime qualification continuation

PR #313: https://github.com/LuminariMUD/Duris/pull/313 at `427860b58`, review-ready.
Current branch: `branch/issue-264-runtime-qualification`, based on that stack.
Published as PR #317: https://github.com/LuminariMUD/Duris/pull/317 at `e8b43d01c`.
PRs #309, #310, #311, #312, #313, #316 and #317 are review-ready and unmerged.
`tests/async/run_pwipe_runtime_journey.py` was published and passed using a private
MariaDB via the existing wrapper, supported adopt/run migrations, copied real launcher
and binary, synthetic world/account, real five-minute pwipe, explicit next boot,
recreated staff login and fresh mortal combat/save/reconnect/reboot. It uses no
checkout `.env`; mail/Discord/telemetry are absent/disabled. Extends the existing
creation fixture only to log into the preserved account before creating a mortal.
First real execution passed mortal denial, malformed/cancelled requests and actual
countdown -> exit 55 -> filesystem cleanup -> active epoch 2. The test then failed
its timing assertion because it started measurement after buffered notice output;
start time now precedes command send. A second run again completed activation but
showed the same ~293-second monotonic measurement; collect wall-clock duration
against the actual calendar-based shutdown deadline in the next run. Do not call
the discrepancy solved or weaken the real configured five-minute countdown.
A 10-second host probe measured 10.884 seconds of wall time versus 10.000 seconds
of monotonic time; the clocks drift here. The game uses a calendar deadline, so
record both durations and assert the wall-clock interval. GDB read-only inspection
of the disposable server confirmed its stored deadline (no timer acceleration).
Source review found the game SIGCHLD handler can reap the preflight child first;
reuse `take_reaped_child_status()` on ECHILD. The native handoff test now forces
that real reaper ordering. The successful scoped result is recorded below. Outputs remain
uncommitted under `bin/analysis`.

Consumer review during countdown: `zone_story_quest_runtime.c` already derives
`current_season_id()` from the SQL epoch and passes it to rendering, assignments,
transactions and character registration. Existing `test_zone_story_quest_feature.py`
passed; preserve the season-keyed history. Kingdom ownership has no such epoch gate:
`kingdom_realms` is loaded by association ID (which can be reused), with garrison/land
side state; it must reset. Divine Boons' `next_id` must remain monotonic if active
slots are expired at cutover, to avoid reusing retained cargo-book boon identities.
Do not blanket-delete protected ledgers; trace live consumers and reset current views.

Independent production-build finding: `ship_shop_proc` maintained `owned` separately
from `ship`, causing an optimized `-Werror=null-dereference` failure. Isolated minimal
repair is review-ready as PR #316 at `ee152d2ba`, in
`/home/aiwithapex/projects/duris-issue264-ship-build` on
`branch/fix-ship-shop-production-ownership`. Full MariaDB production build and the
native ship-panel/staff-cargo guards passed there. Incorporate that commit into the
qualification stack before executing the full production-unit fixture. No production
service or user worktree was changed. Production repair was merged into the qualification branch as `f6694e7fe` and
the combined production build passed. Runtime changes are published in #317.

Next focused implementation candidates after runtime publication:

- Reward retry accounting: current guard compares `last_processed_at` to retry-time
  `NOW()`, so an old unfinished reset retried after 28 days can consume again.
  Evaluate the existing durable `reset_started_at`/epoch instead: base eligibility
  on that fixed boundary and stamp it atomically with grant policy. This may meet
  exact retry accounting without a new migration/ledger. Prove same reset after
  >28 days, distinct resets inside/outside the business guard, both preserve modes,
  grant expiry, summon clearing and lost COMMIT acknowledgment before choosing it.
- W5 companion source rechecked at DurisWeb `7147e6b1`: active-season presence/cache
  reads already query the SQL fence, but failed 60-second subscriber refresh retains
  its previous channel. The manual workflow must stop external seasonal writers
  before reset and restart them only after activation; exercise it and fix stale
  event handling independently if needed. No DurisWeb edits or operations yet.

Runtime result: **PASS**, MariaDB-primary with Redis disabled, using the real
five-minute command (300.581 wall seconds; 292.483 monotonic on this drifting host).
Mortal denial, malformed confirmation, cancellation, old-season observations,
actual exit 55, full SQL/launcher/filesystem cleanup, epoch 2 activation, existing
account + recreated level-62 login, fresh mortal combat/loot/save, reconnect and
another boot all passed. Old PID 1 stayed inactive; fresh staff PID 2 and mortal
PID 3 persisted. Old pfile/ship sentinels disappeared and backup sentinel survived.
Evidence: `bin/analysis/pwipe-runtime-mariadb.json` (uncommitted), binary SHA-256
`69adaed05e55b82e5b2a0f44ae47fb4570e89757fa5a451eca95bdc981b4830b`, source
`427860b58` plus the reaper repair. Later ship ownership repair was independently
qualified and merged as `f6694e7fe`; no repeated five-minute campaign for that
unchanged reset path. Required `format.sh --all --check` passed all 1,147 C/C++ files;
MariaDB development, isolated flat-file and the full combined MariaDB production
builds passed. Forced actual reaper/SQL/launcher failure tests and affected source
contracts passed. This proves the mini-world, Redis-off path, not full wipe readiness.

Remaining blocking work is still W1's complete consumer inventory, W2 direct/external
writers/replay, W4 active retained stores and epoch-bound reward retries, W5 website/
Redis/telemetry cutover, and W6 failure/recovery/full installed service evidence.
The finished PRs do not sign off the wipe. Continue autonomous local qualification.

## What the code currently does

These are baseline observations, not claims that every failure has been reproduced.

1. **Permission and confirmation exist.** `do_shutdown()` in `src/cmd/actwiz.c`
   accepts `shutdown pwipe confirm yes` only at `OVERLORD` and schedules five
   minutes. A later shutdown command cancels the pending request. Help says leaving
   the game cancels a schedule, but `timedShutdown()` has that cancellation block
   commented out. Test command-table access, malformed input, cancellation,
   notices and issuer disconnect; resolve the help/behavior mismatch deliberately.
2. **A durable SQL fence exists.** `sql_begin_pwipe_epoch()` locks the singleton,
   increments its epoch, and records `resetting` before reset SQL. Ambiguous COMMIT
   sets `pwipe_crossed_boundary`. Startup's `sql_load_active_season_state()` refuses
   a non-active season. Reuse this fence.
3. **Completion is premature across processes.** `sql_pwipe()` calls
   `sql_complete_pwipe_epoch()` and emits `WIPE COMPLETED!` before server exit and
   filesystem cleanup. A filesystem failure therefore has no remaining SQL fence.
   Post-boundary SQL failure also leaves `_pwipe` set; `src/net/comm.c` returns 55
   for it just as for SQL success. The launcher treats either 55 as permission to
   wipe files and can print `Wiped!` after incomplete SQL reset. This is a concrete
   control-flow defect, not merely a missing test.
4. **Launcher stopping is not service stopping.** The loop treats 55 as terminal,
   requires executable `wipe_it_all`, and exits nonzero on filesystem error. The
   production unit nevertheless has `Restart=always` and no pwipe-specific restart
   prevention. The runbook's 55/no-restart statement does not describe the entire
   installed service. Qualify both direct-launch and service modes.
5. **Skipping shutdown saves is not writer quiescence.** `_pwipe` suppresses
   terminal saves/extraction, dirty marks and several world saves. Reset SQL runs
   inside `timedShutdown()` before game-loop shutdown quiesces the coordinator/
   outbox. `critical_command_coordinator.c` explicitly notes that an already queued
   job still lands after coordinator shutdown. `player_save_pipeline.h` already
   provides quiesce/resume/drain/finish operations. `kingdom_shutdown()` retries
   upkeep and flushes dirty realms when enabled, and runs after the game loop
   during pwipe too. Inventory all writers and demonstrate races with held jobs;
   a flag alone is not proof of safety.
6. **Inventory classifications need consumer review.** The lifecycle manifest
   classifies 199 SQL tables and 24 other stores. It retains recovery evidence and
   active stores such as `item_current_owner`, `collector_listings`, `kingdom_realms`,
   `kingdom_garrison`, `zone_story_quest_state` and `divine_boon_state`. Kingdom loads,
   collector repositories, player-load ownership joins and quest/boon loads consume
   them. Retaining bytes and letting them influence a new season are separate
   decisions. Trace consumers before deleting, deactivating, reinitializing or
   retaining with isolation.
7. **Filesystem cleanup is a legacy allowlist.** `wipe_it_all` clears letter
   buckets/named stores under `Players/`, `Ships/` and optional root `Corpses/`,
   preserving `Players/Backup`. It does not cover every manifest store. Modern
   flat-file authority uses `FLATFILE_STATE_DIR`; `sql_pwipe()` under
   `__NO_MYSQL__` returns false. The script is not a complete flat-file backend wipe.
8. **Rewards have policy but lack reset identity.**
   `account_bound_rewards_on_successful_pwipe()` uses a transaction and global
   `last_processed_at` with a documented 28-day guard (`lib/account_rewards.cfg`).
   `pwipe.preserve=true` keeps permanent/unexpired grants, decrements finite grants,
   expires exhausted grants, and clears summons on a processed wipe; false removes
   grants. Failure is logged but SQL still declares completion. A timestamp window
   does not identify a reset. Preserve the documented 28-day business protection
   unless explicitly changed; separate it from retry accounting.
9. **Redis is already season scoped.** `redis.c` captures SQL epoch once at boot.
   Cleanup cancels donation/presence/cache/legacy-ship work, quiesces world recovery,
   and deletes/verifies old-epoch keys through `redis_maintenance.c`. Disabled Redis
   skips cleanup; later activation must still ignore old epochs. Reuse isolated
   Redis tests. Check legacy unscoped cleanup against shared installations; do not
   introduce `FLUSHALL` or another namespace scheme.
10. **Telemetry season is independent configuration.** `telemetry_runtime.c` loads
    `TELEMETRY_SEASON_ID` (default 1), independently of SQL epoch. PostHog identities
    include environment/season; the outage ledger preserves quota reservations and
    sender ownership. Specify cutover without deleting history, resetting same-day
    project quota or relabeling old events.
11. **Website epoch consumers exist.** Read-only inspection of local DurisWeb
    revision `7147e6b1bece2e650dbe3cb312c904edfa43bf9d` found active-season queries in
    `backend/src/services/onlinePlayersService.ts`, `playerEventSubscriber.ts` and
    `donationOutboxService.ts`. The subscriber refreshes every 60 seconds; failed
    refresh can leave its prior subscription in place. Test stale events, response
    caches, websockets, donations and leaderboards. This is source evidence, not
    deployed validation. Recheck its revision and link companion fixes to #264.

## Implementation work items

### W1 — Reset/preservation contract and fixture (4–6 hours)

- [ ] Inventory tables from the supported migration runner's applied manifest and
  a fully migrated disposable DB, not a glob of historical SQL. Compare lifecycle
  classification and runtime pre/postflight, foreign keys, retained parents,
  identities/sequences and inactive account-character semantics. Include newly
  landed systems at the final qualification revision.
- [ ] Inventory paths from readers/writers, Redis registry keys/channels, workers,
  maintenance jobs, website writes, telemetry and backup/restore tools. Record each
  store's authority, readers/writers, reset/retain action, recovery behavior and
  assertion in the existing manifest/runbook. Archives must not become live input.
- [ ] Specify accounts/passwords, staff access/recreation, bans/whitelists,
  donations, account banks, rewards, configuration, catalogs, UID allocation,
  audit/erasure evidence, backups and archives. Account-character soft-delete
  includes staff links: prove a staff access path after wipe. Do not infer every
  bank balance or staff character is an approved carryover; list unresolved owner
  policy by affected store. Owner has resolved banks/staff: reset all account-bank
  balances; recreate only exact level-62 Overlords, without old seasonal assets.
- [ ] Cover characters/progression/discoveries; item ownership/equipment;
  inventories, lockers/account lockers/chests/corpses/pets; ships/cargo;
  guilds/alliances/kingdoms/world ownership; auctions/currency; rankings/statistics/
  reports; quests; collectors; Divine Boons and epic-stone claims.
- [x] Remove duplicate schema inventories via the sealed migration manifest;
  lifecycle scanner and runner tests pass. Actual fully migrated DB inventory
  comparison remains in the first W1 item.
- [ ] Seed synthetic old-season data/carryovers, connected/linkdead characters,
  pending saves/outbox records, recovery receipts, Redis and external-client state.
  Reuse `run_copyover_runtime_journey.py`, `test_flatfile_combat_journey.py` and
  `scripts/persistence_restore.py` fixture/private-database patterns.

Exit: every store has a disposition and assertion. Unresolved destructive policy
choices remain explicit readiness blockers, not inferred defaults.

### W2 — Quiesce writers before the irreversible boundary (6–10 hours)

- [ ] Exercise nonstaff/underlevel staff, malformed requests, exact confirmation,
  cancellation/countdown boundaries, repeated requests and issuer disconnect.
  Align help/runbook behavior; ordinary reboot/copyover must never enter reset.
- [ ] Order preparation: validate dependencies/recovery prerequisites, stop new
  seasonal work, settle or safely cancel accepted work, confirm no writer can
  commit, then establish the boundary. Reuse coordinator, outbox, player-save,
  locker, maintenance and Redis controls. Inspect load completions and account/
  donation writers. Preserve accepted benefits while blocking stale character
  writes; pause only writers that can mutate the reset contract.
- [ ] On pre-boundary preflight/quiescence failure, resume service and prove the
  old season remains intact. Do not discard accepted saves and call cancellation
  harmless. Once boundary COMMIT may have succeeded, never resume the old world.
- [ ] Suppress post-reset writebacks, including kingdom flushes and completion
  callbacks. Preserve diagnostics/telemetry according to contract. Prove queued
  shared-writer jobs are covered; coordinator teardown alone is insufficient.
- [ ] Trace retained outbox/journal/checkpoint/authority startup replay. Fence or
  retire old effects at existing consumers when draining cannot prevent replay.
  Add epoch fields only where necessary, with compatibility for historical records;
  do not stamp every table by default.

Exit: hold old saves/operations during preparation, release at former race points,
and prove they cannot recreate reset data. A pre-boundary abort preserves accepted
old-season work and normal saves continue.

### W3 — Durable completion through filesystem cleanup (6–10 hours)

- [ ] Extend the singleton only with phase/receipt information needed to distinguish
  incomplete SQL, SQL-ready filesystem cleanup and completed reset. Resume uses
  the same reset identity/epoch. Use additive guarded migrations; do not change
  previously applied immutable migrations.
- [ ] Keep startup fenced until SQL, reward processing, required Redis cleanup,
  filesystem cleanup and all postconditions succeed. Use truthful stage messages;
  final activation must be guarded by expected reset identity.
- [ ] Distinguish a fenced failed stop from permission to clean files. Exit 55
  alone cannot authorize deletion after post-boundary SQL failure. The launcher
  must verify durable state or a handoff bound to it, preserving failure status
  through logging/notification commands.
- [ ] Preflight artifact, target layout and access before destructive SQL. Revalidate
  canonical targets during cleanup; reject unexpected symlink/path escape, denied
  access and partial deletion. Preserve accounts/config/backups. Repeating cleanup
  for the same unfinished reset must be safe.
- [ ] Make direct launcher and production service honor intentional pwipe stop
  and incomplete-reset fencing, using the existing exit contract with explicit
  non-restart status where needed. Preserve ordinary reboot/crash recovery. Direct
  server starts must also honor the fence.
- [ ] Document/exercise resume at each irreversible stage and restore of a matched
  pre-wipe DB/filesystem/Redis generation. Resume cannot increment epoch again or
  repeat rewards. Never bypass recovery by simply setting state active.

Exit: interruptions after SQL, within file deletion and before final activation
keep startup fenced. Verified completion permits explicit fresh start; duplicate
completion is safe and overall success appears only after all required stages.

### W4 — Reset completeness and exactly-once carryovers (4–8 hours)

- [ ] Reconcile W1 with SQL in child-before-parent order; extend required preflight/
  postflight tables, columns and actions. Test actual values/defaults, not just
  empty counts. Separate active ownership/catalog/baseline state from history.
- [ ] Correct retained active state that crosses seasons, including world ownership
  and snapshots. Preserve history while blocking old payload startup/replay.
  Prove banks, IDs, quests and economic/item baselines match the contract rather
  than blindly following `retain` labels.
- [x] Bind reward-policy application to the resetting epoch and fixed boundary;
  failure prevents SQL-ready publication. The native real-hook matrix proves
  28-day business protection, delayed retries, rollback/lost ACK and unconditional
  old-body summon cleanup. See the reward-retry chunk above.
- [ ] Test permanent, time-expiring, finite-one/finite-many grants, both preserve
  settings, summons, ambiguous commit, immediate/delayed retries, distinct resets
  inside/outside 28 days and failure before activation. Prove new-character claims
  against surviving accounts behave correctly.
- [ ] Reconcile files with actual MariaDB fallback/startup reads. Isolate retained
  recovery evidence instead of loading it as new gameplay. Prevent stale copyover
  files from reattaching old characters/descriptors.

Exit: reset data is absent/inactive with correct defaults; carryover sentinels
survive except documented transitions; retries neither double-consume rewards
nor suppress an independent reset's required cleanup.

### W5 — Website, Redis and telemetry cutover (3–6 hours)

- [ ] Exercise Redis enabled, disabled, unavailable before reset, failing after
  boundary, and re-enabled in the new epoch. Old data/events stay invisible and
  unrelated namespaces survive. Extend `test_redis_maintenance_live.py` and
  season-scope tests rather than building another subsystem.
- [ ] Exercise website presence, cached lists/leaderboards, account characters,
  websocket/reconnecting clients and queued donations against the disposable
  reset. Verify website writers cannot race it, including stale subscriptions
  during `resetting` and refresh. Link necessary DurisWeb fixes to #264 with their
  revisions/tests; required untested integrations remain open.
- [ ] Specify telemetry season-ID change and sender stop/drain/rebind/start order,
  historical events, identity separation and same-day quota conservation. Reuse
  protected outage-ledger tools and local HTTP receiver. Never delete/reinitialize
  quota evidence or send fixtures to production PostHog.
- [ ] Document remaining manual steps, owner, expected state and verification,
  including backup generation validation and external writer pause/resume. Rehearse
  them; the issue permits documented manual cutover.

Exit: observations belong to the correct season, clients cannot revive old state,
and donations and retained telemetry/quota evidence remain correct.

### W6 — Full journeys and failure/recovery cases (6–10 hours)

- [x] Add `tests/async/run_pwipe_runtime_journey.py`, reusing private DB/world/socket
  fixtures. PR #317 executes the real five-minute command, launcher/wiper, explicit
  new season, recreated Overlord login, fresh mortal gameplay and another boot.
  Qualified scope: MariaDB-primary, Redis off, mini world. Wider cases remain below.
- [ ] Use independent database, Redis process/namespace, ports and runtime tree.
  Never source the checkout's `.env` or read real player/account data. Disable
  production mail/Discord/PostHog in fixtures; artifacts belong under `bin/`.
- [ ] Assert SQL/filesystem/Redis/recovery results, log into an existing account,
  recover staff access by the documented route, create/play a mortal, claim
  benefits, gain progression/items, save/rent, reconnect and reboot again. Prove
  fresh state persists and old characters/items/world ownership never return.
- [ ] Before boundary: unavailable DB/Redis, missing schema, absent/nonexecutable
  wipe artifact, denied file access and quiescence timeout leave the old season
  intact. Invalid/cancelled requests cannot change epoch or invoke cleanup.
- [ ] After boundary: fail SQL, ambiguous COMMIT, Redis invalidation, rewards, file
  cleanup and final activation. Interrupt server and launcher separately at
  SQL/filesystem/completion boundaries. Attempt direct start, repeated launcher
  invocation and service restart against incomplete state.
- [ ] Exercise resume and disposable restore, including interruption after reward
  commit but before completion. Preserve backup/audit sentinels and unrelated
  Redis keys through repeated cleanup attempts.
- [ ] Execute production unit restart behavior in an isolated service-capable
  environment. Mocks/unit text checks cannot prove systemd behavior; keep the
  readiness gate open if that execution is unavailable.
- [ ] Fully qualify MariaDB-primary with Redis on/off. Build flat-file mode and
  execute unsupported-pwipe rejection, proving no data loss and normal continuation.
  Record build profiles, enabled optional systems and gaps; do not label rejection
  successful flat-file wipe qualification.

Exit: record revisions, sanitized configuration, commands, before/after assertions,
exit statuses, durable phases and recovery outcomes. Fix every blocker and rerun
its failing path, not just the happy path.

### W7 — Review, handoff and readiness (3–6 hours)

- [ ] Reapply ablation: each file has a traced consumer/requirement. Remove
  speculative layers, duplicate state, obsolete paths and task-created scratch;
  preserve unrelated work.
- [ ] Run required formatting/builds, focused checks and final journeys. Update
  runbook, configuration/reward help, regression index and plan to match code.
  Complete applicable reviews; do not wait for CI instead of local qualification.
- [ ] Give findings a disposition: fixed with proof, disproven with proof, explicit
  policy decision, or blocker. Keep #264 and #97's Wipe system item open until
  contract/runbook, gameplay journey, failure/recovery proof and blocking repairs
  are complete. Separate qualification from deployment/production authorization.

## Ablation decisions

- **Keep** launcher/service journeys, durable completion, writer fencing,
  reset-specific carryover accounting and failure tests: omitting these leaves
  demonstrated cross-process/replay risks unproved.
- **Simplify** with the existing singleton, Redis maintenance, worker APIs,
  migration runner, manifest and fixtures. No new coordinator service, generic
  wipe framework or parallel manifest is needed.
- **Drop** blanket ledger deletion/epoch columns, new flat-file reset support,
  repository-wide burn-in and unrelated cleanup. Add isolation/tests for actual
  consumers; do not trade away acceptance requirements.
- **Investigate** bank/staff carryovers, protected recovery records and reward
  policy before destructive choices. Preserve policy/evidence by default; those
  stores remain in completion criteria.

## Validation recorded during planning

These commands passed on the baseline in an isolated source worktree without
executing a wipe or contacting production:

```text
python3 tests/async/test_pwipe_quiescence.py
python3 tests/async/test_sql_pwipe_completion.py
python3 tests/async/test_cycle_pwipe_status.py
python3 tests/async/test_redis_pwipe_invalidation.py
python3 tests/async/test_season_reset_fence.py
python3 tests/async/test_season_reset_manifest.py
python3 tests/async/test_redis_season_scope.py
python3 scripts/validate_data_lifecycle.py
bash -n scripts/cycle_mud.sh Players/wipers/wipe_it_all
```

`python3 tests/async/test_data_lifecycle_manifest.py` ran 12 tests with five
failures. Its overridden schema list omits `0048_divine_boon_state.sql`; validation
reports unknown `divine_boon_state`, masking four expected-error assertions. The
standalone validator includes it and passes (199 tables, 24 stores, 42 Redis
surfaces). W1 repairs the divergence; neither result proves live-schema coverage.
The seven passing pwipe/season tests are source contracts, not runtime wipe,
race, filesystem, systemd or gameplay qualification.

Implementation completion must include, as applicable:

```text
./scripts/format.sh --check
make -C src PERSISTENCE_BACKEND=mariadb
make -C src PERSISTENCE_BACKEND=flatfile BIN_ROOT=<absolute-path-under-bin>
python3 tests/async/test_data_lifecycle_manifest.py
python3 tests/async/test_redis_maintenance_live.py
```

Also rerun the seven source contracts, affected subsystem executable tests,
existing account reward schema tests, and the planned journey/failure cases.
Choose the new runner's interface during W6; never record future commands as
executed. Use separate backend output directories to avoid stale builds.

## Estimate and uncertainty

**32–56 active engineering hours (about 4–7 eight-hour working days)** for one
implementer, including W1–W7, tests, builds, review fixes and evidence. Work-item
ranges sum to this total; they are not parallel-agent estimates. Planning and
publication in this change are separate from implementation. This is a forecast,
not a fixed budget or promised date, and does not establish October 28 readiness.

Largest uncertainties: retained authority/recovery replay, cross-process recovery
changes, and companion website/quota cutover. Disposable systemd/DB/Redis access
and owner policy decisions can add calendar delay. Re-estimate after W1 and the
first real reset journey, and immediately when findings invalidate the range.
Do not silently drop acceptance items to preserve the estimate.
