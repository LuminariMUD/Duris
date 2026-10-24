# Issue #264: qualify the full pwipe lifecycle

Status: implementation started 2026-10-24; full wipe readiness remains OPEN.
Prepared 2026-10-23 for [#264](https://github.com/LuminariMUD/Duris/issues/264),
the **Wipe system** readiness item in [#97](https://github.com/LuminariMUD/Duris/issues/97).
Implementation branch: `branch/issue-264-pwipe-qualification`.

**Continuation pointer (2026-10-24):** current implementation/evidence and remaining
gates are in the [stack-tip plan](https://github.com/LuminariMUD/Duris/blob/branch/issue-264-email-fix-integration/docs/ongoing-projects/plan.md),
branch `branch/issue-264-email-fix-integration`, [PR #356](https://github.com/LuminariMUD/Duris/pull/356).
Reuse `/home/aiwithapex/projects/duris-issue264-plan`, on that branch at `82814f58b`
(clean and pushed). Review-ready server stack:
#309 -> #310 -> #311 -> #312 -> #313 -> #317 -> #318 -> #321 -> #322 -> #323 -> #324 -> #325 -> #326 -> #327 -> #329 -> #330 -> #334 -> #336 -> #337 -> #339 -> #340 -> #341 -> #343 -> #344 -> #345 -> #347 -> #348 -> #349 -> #350 -> #351 -> #352 -> #353 -> #354 -> #356,
plus independent production-build repair #316 and email registry repair #355 (included in #356). PR #334 adds the sealed nullable
roster checkpoint. PR #336 resumes the same unfinished SQL epoch without world
startup, acquires the normal runtime exclusion guard, skips a committed roster and
uses the original Redis epoch. Real cold recovery, SIGKILL/rollback, concurrent
exclusion, Redis failure/repair, reward-commit/readiness failure and actual launcher
completion pass on MariaDB 10.11.19 and MySQL 8.0.46 (optimized binary). All three
builds and focused contracts/hooks pass. Earlier Redis-off and full-systemd/Redis-on
reset-to-fresh-gameplay journeys passed on the prior core revision; exact evidence
and scope are in the linked plan.
PR #337 qualifies frozen matched SQL/journal, filesystem and authenticated Redis
recovery with the optimized binary: actual five-minute wipe and fresh gameplay
passed, followed by an independent pre-wipe restore, original account/body/bank/
reward/items/world, save/reconnect/second boot, and unchanged epoch-2 source
SQL/files/Redis plus retained generation hashes. Exact command/revision/hash and
coverage are in the stack-tip plan; no production promotion path was added.
PR #339 closes an unscoped native-handoff gap: guarded filesystem cleanup archives
configured publication/claim/consumption inputs before activation, outside both warm
and cold readers. Bytes remain protected in private Players/Backup archives; normal
copyover format stays unchanged. Ten filesystem tests, 12 ASan/UBSan native-reader
scenarios and the final actual SQL/launcher matrix pass, including partial retry and
fresh-handoff preservation after lost activation ACK. The missing native store is
classified: current lifecycle inventory is 200 tables, 31 other stores, 42 Redis
surfaces. Required incremental build/format/hooks pass; unchanged full-build evidence
is reused. See the stack-tip plan for commands, hashes and remaining gates.
PR #340 independently repairs a lost-floor precondition: stale active player custody
no longer suppresses the physical recovery tree; existing saved-holder/terminal/
economic ownership checks still prevent duplicate replay. Native ASan/UBSan capture/
ownership/codec tests and all three builds pass. Real same-epoch floor recovery passed.
PR #341 then passed the actual five-minute Redis-off wipe and epoch-2 re-enable with
valid authenticated epoch-1 world/floor payloads retained. Old payload hash/keys stayed
unchanged; the old sword stayed absent, fresh presence/combat/save/reconnect and
new-scope recovery/second boot passed. Exact fixture revision `4464aab01`, binary
`e09aacfefb4aec8007d519b029b6af91c78292ceb624d11840571b3572df5cf3`, and reports are
in the stack-tip plan. The Redis on/off/failure/re-enable gate is now qualified;
full external website/donation/client/telemetry cutover remains open.
PR #343 completes the operator gate: strict request validation preserves existing
countdowns, manual timers cancel on issuer departure or lost shared command
permission, replacement has one queued timer, and terminal execution is disarmed.
Native ASan/UBSan clock/event regressions and all three builds pass. The actual
journey at `b20372b9f` proves level-60 grant/revoke, malformed/repeated requests,
menu/link cancellation, and the 301.961-second wipe followed by bank reset, only
level-62 Overlord recreation and fresh combat/loot/save/reconnect/second boot.
Binary/report hashes and commands are recorded in the current stack-tip plan.
PR #344 closes the reward-policy/new-character claim gate. Real staff commands
create exact permanent/day/one-wipe/three-wipe grants. Two complete disposable
journeys prove preserving reset and discard reset, then claims/refusals on a fresh
mortal, exact new item UIDs/values, duplicate refusal, dismiss cooldown, save,
reconnect and second boot. Preserve fixture `528d1e68d`, discard `7819c9916`, same
optimized binary as #343. Reuse native #318/#336 expiry/28-day/ambiguous/delayed
retry proof and unchanged builds. Reports and commands are in the stack-tip plan.
PR #345 completes the documented manual telemetry cutover gate: actual native
worker/CLI/loopback HTTPS proves active-owner refusal, drain/reap, byte-exact old
archive/history, idempotent rollover, stale refusal, new environment season and
distinct same-subject identities with zero fresh same-day HTTP allowance. All 46
cases pass across both UBSan-compiled backend variants at fixture `123d0bb73`;
reuse the passed native quota fault suite for next-day allocation/interruption.
Required incremental build/format/hooks pass; no production source changed.
The runbook records the exact operator/sender-owner procedure and expected states.
Companion DurisWeb [#93](https://github.com/LuminariMUD/DurisWeb/pull/93) and
[#94](https://github.com/LuminariMUD/DurisWeb/pull/94) fence stale events and redact
driver details, with backend checks and native SELECT-only lock proof. The clean
pushed companion worktree is `/home/aiwithapex/projects/durisweb-issue264-presence`,
branch `branch/issue-264-website-runtime-journey` at `c477278`.
Companion [#95](https://github.com/LuminariMUD/DurisWeb/pull/95), stacked on #94,
repairs retired-account characters and reused-name ownership across old caches.
Three regressions fail on the parent and pass after repair; actual service queries
pass on owned disposable MariaDB/MySQL while preserving legacy cached state.
Backend format/lint/types/build/MUD-write verification pass; combined account/
presence unit checks pass (28). The native account case passes explicitly on both
engines; unchanged native presence locking proof is reused. News remains a local
unpublished draft. The full website HTTP/client/cache/donation cutover remains
open. Companion [#96](https://github.com/LuminariMUD/DurisWeb/pull/96) removes
that derived-permission cache and obsolete cleanup, filters active bodies and
recomputes MUD privileges at every authorization. Two regressions fail on #95;
seven tests per owned MariaDB/MySQL fixture pass, including actual JWT/HTTP 200
before level-61 retirement -> 403 for the same token afterward, and 200 for the
recreated Overlord. Explicit website-admin grants remain separate. The fixture
stubs only active-session validity; session-persistence/full-client evidence is
not replaced. Focused unit checks pass (36), all required backend checks pass.
Existing websocket principals still need the stopped-service/reconnect cutover;
Paired server [#347](https://github.com/LuminariMUD/Duris/pull/347) and companion
[#97](https://github.com/LuminariMUD/DurisWeb/pull/97) now qualify the normal backend
through the real reset: old HTTP/session/WHO/rank/cache/MUD-login checks, graceful
WS close/publisher drain, five-minute wipe, new authenticated reconnects, stale-role
cache refusal, fresh feeds and actual game delivery of a queued signed donation.
Repeated webhook leaves one 123-cent credit. Full proof server `9569cc0ae` /
companion `2918696`, same production binary as #343, 302.723 wall seconds; all
private resources clean. Reports/artifact hash/commands are in the stack-tip plan.
A separate supported-Node root/private-mount keeper-unit rehearsal proves legacy
source access after the old unit stops and protected bytes after both stop; mount/
alias controls pass. The website factory now selects supported MySQL 8, with narrow
wrapper/default/boot checks and reused full proof. Joint MariaDB 11.8 and rendered-
browser/production acceptance are not claimed. W5 backend/client-wire integration
is qualified; final manual/readiness and full store/writer reconciliation stay open.
PR #348 proves ordinary retained custody/revision/baseline rows cannot rebuild
wiped player payloads. The actual load repository sees the old payload before,
then no old item/pet graph afterward despite exact metadata retention. Recreated
Overlord has no inherited graph/revision; payload row IDs and a real UID lease stay
monotonic. The committed native matrix passes on MariaDB 10.11.19 and MySQL 8.0.46,
including all 200 lifecycle tables. Descriptions clarify these books are not a
substitute for recovery-input epoch isolation. Existing handoff/service/isolation
proof reconciles the remaining W3 and W6-isolation checkboxes. No production
code/schema/reset action changed. Current origin/master is already an ancestor.
Next required gaps: full retained-store/path/worker consumer inventory, held actual
shared-writer/callback-chain quiescence proof, launcher-kill/child-lock inheritance, then final manual/backup and readiness reconciliation. Visual
browser release testing is not an added #264 acceptance gate.
PR #349 closes the unknown epoch-boundary COMMIT result gap. A targeted native
client wrapper fails once before application and once after real COMMIT; the SQL
caller never resumes writers or marks filesystem-ready, and old rows/files/grants
remain intact. The committed case refuses actual direct startup at the explicit
season fence (raw fatal 1) and launcher cleanup (58). Real SQL-only recovery reuses
the successor epoch, decrements one grant 3 -> 2 once, clears old payload/summons,
and preserves roster/stamp/fresh files on readiness/activation retry. Both full
native matrices pass at fixture `361425efd` on MariaDB 10.11.19 and MySQL 8.0.46;
incremental build/syntax/format/hooks pass. No production source/schema changed.
Remaining required proof: actual held shared-writer/callback chains, launcher
SIGKILL/child-lock inheritance, full retained-store/path consumer inventory and
final manual/backup/readiness reconciliation. No new visual/deployment gate.
Full #264/#97 readiness remains OPEN. Owner policy: reset all account-bank balances;
recreate only exact level-62 Overlords. Next: retained custody/baseline and legacy
fallback consumer proof, final manual/backup readiness reconciliation, W2
remaining writer/replay audit, W4 reset/retained-reader completeness and W7 readiness audit. The
website stop procedure includes its legacy temporary-copy preservation gate.
Nothing is deployed or published; no release tag/readiness sign-off is appropriate.

PR #350 closes the actual shared-writer/SQL callback gap: canonical disposable
MariaDB/MySQL prove held accepted player saves/SQL writes, two dependent real reads
and their final commit drain before admission closes; timeout preserves accepted
work and terminal SQL failure rolls back, with normal persistence resuming afterward.
PR #351 proves actual launcher-parent SIGKILL leaves the orphan wipe child holding
its inherited kernel flock, so a concurrent resume refuses. Orphan completion and
whole-group partial cleanup kill stay fenced; same-epoch resume and duplicate
completion succeed without deleting fresh state. Both full native engine matrices,
focused contracts/format/hooks pass. No production code changed in these two chunks;
reuse the existing builds/full runtime evidence. Remaining store/path/worker consumer
reconciliation and final readiness remain open; see the current stack-tip plan.

PR #352 repairs a reproduced maintenance-checkpoint replay gap: actual native
scheduler init replays an old captured retry even after drain, and the previous
wiper left that unscoped state live. Guarded cleanup now archives default/configured
state and `.tmp` into private Players/Backup/pwipe-maintenance.* before activation,
preserving exact bytes and source path. Actual scheduler default/custom/external/
wipe-target proof, 13 filesystem contracts and both full native SQL/launcher matrices
pass; fresh checkpoints survive duplicate/ambiguous-activation retries. Wiper hash,
logs, command/build evidence reuse and exact remaining inventory targets are in the
current stack-tip plan. All changes committed/pushed/review-ready; full readiness
remains open and no production operation was performed.

PR #353 repairs actual name-keyed MUD mail replay. Normal boot scans Accounts/mail
or Players/mail; the actual native producer/index/reader proves the prior wiper leaves
old multi-block messages reachable by a reused name. Cleanup now privately archives
both paths before activation. Native current/legacy/dual-spool proof, 16 filesystem
cases and both full engine/launcher matrices pass; fresh mail survives duplicate/
ambiguous activation retry. Wiper SHA and logs are in the current stack-tip plan.
PR #354 proves all four retained locker receipt states stay isolated from a new PID
on the same account/side (both modeled purses), copied-PID aliases refuse, old bytes
remain exact and fresh purchase succeeds. It reconciles legacy SQL-only admission
and adds actual registration, admission-policy and client-free namespace inventory:
current 200 SQL tables / 35 other stores / 42 Redis surfaces. Focused executable
pipeline/mode, receipt/crash matrix, filesystem and lifecycle checks pass.
An independent optional email lookup EOF loop/FILE leak found in that audit is fixed
in review-ready PR #355 against master (source worktree duris-account-email-fix,
commit 9b61a23f0). PR #356 integrates it into the qualification stack; native actual-
helper ASan/UBSan enabled/disabled and incremental MariaDB build pass. Default
verification stays disabled. No full timer rerun for this unrelated helper.
All changes are committed/pushed/review-ready. Full retained SQL/worker audit and
final manual/readiness reconciliation remain open; no GitHub merge or production
operation. The plan records exact evidence, dependency order and next targets.

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
- Next chunk: W3 SQL-to-launcher completion/failure contract, including fenced
  post-boundary failures, durable SQL-ready state and guarded filesystem completion.
  W2 writer drain and W4 completeness/carryovers remain required before runtime
  readiness. No production actions, readiness sign-off or release tag.
- The baseline list failures were repaired on master before this continuation;
  removing the remaining duplication prevents the same drift recurring.

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
  policy by affected store.
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
- [ ] Bind reward-policy application to reset identity; failure is an unfinished
  stage. Preserve 28-day protection as a separate business rule unless explicitly
  revised. Separate summon cleanup from grant-decrement eligibility where required.
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

- [ ] Add focused `tests/async/run_pwipe_runtime_journey.py` (planned new file),
  reusing private DB/world/socket fixtures. Drive real command/countdown,
  `cycle_mud.sh` and `wipe_it_all`, then explicitly start the new season. Unit
  tests may control time; at least one acceptance run uses the real five minutes.
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
