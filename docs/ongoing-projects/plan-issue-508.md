# Issue #508: shared progression with earned PvP acceleration

Status: **implementation in progress; rules PR open, storage chunk qualified locally**.
Updated 2026-10-31. No gameplay cutover or production operation has occurred.
Delivery target: **270 minutes of implementation/qualification plus 30 minutes contingency**.
The target is a tested, reviewable change; production deployment is separate.

Sources: [issue #508](https://github.com/LuminariMUD/Duris/issues/508),
[history](https://github.com/LuminariMUD/Duris/issues/508#issuecomment-6542566134),
and the [concrete proposal](https://github.com/LuminariMUD/Duris/issues/508#issuecomment-6542754060).
Prepared using the repository's [ablation skill](../../.agents/skills/ablation/SKILL.md).

Research baseline: `b737db20210ff2d3e4eebccb212c9918b9b6f877`.
The dedicated implementation checkout is now `/home/aiwithapex/projects/duris-issue-508`
on `branch/issue-508-frag-progression`, based on freshly fetched master
`9ad734e9e60b0938181f85cd20cdb9614a14adc8`. Implementation is underway here;
the separate bartender task remains in its original checkout.

The newer base includes [#511](https://github.com/LuminariMUD/Duris/pull/511),
which excludes staff from frag rankings and side totals, and
[#512](https://github.com/LuminariMUD/Duris/pull/512), which fixes player leaderboard
scoring. Preserve those changes while removing standings from cap qualification.
The proposed progression contract is unchanged. Recheck master and migration
numbering before implementation.

## Outcome and boundaries

Everyone can reach level 31 through their normal advancement requirements.
Thereafter one shared cap opens one level every 72 real hours, or as early as
48 hours when any character earns 0.20 ordinary PvP frags during the round.
Small positive awards accumulate per character; earned progress survives death,
logout and restart. A quiet server still progresses.

Deliver the complete contract below on MariaDB and flatfile gameplay builds,
with truthful status, durable credit, replay protection and a safe current-season
transition. Keep the existing level-56 maximum, Hardcore's bounded +2 XP allowance,
ordinary level-50 XP ceiling and normal epic-stone requirements.

This work changes cap progression and removes the cap-specific XP penalty.
Keep normal frag eligibility, sharing, victim losses, epic/blood-money/artifact
rewards, achievements and Divine Boons. Do not change quests, gear, combat balance,
account policy, character save formats or the persistence architecture. No new
faction XP boon, additional currency, damage-contribution scoring, new service,
general scheduler, production wipe or unrelated cleanup.

The rules engine and native tests now exist. Storage, gameplay wiring and the
remaining proof below are still required; the engine alone does not change gameplay.

## Fixed gameplay contract

1. **One shared cap:** fresh season 31, maximum 56. All intermediate and circle
   levels open to every side. Standings remain a leaderboard, not a permission
   to level. All mortal racewar sides can contribute normally awarded PvP frags.
2. **One round:** normal earliest deadline = start + 48 hours; automatic deadline
   = start + 72 hours. If the contribution threshold is first durably confirmed
   at `Q`, due time = `min(automatic, max(earliest, Q))`. Without `Q`, use automatic.
   Advance one level at the effective due time and begin the next round there.
3. **Actual earned credit:** add positive ordinary combat `frag_delta` values
   in integer hundredths per PID, capped at the 20-point target. One +0.20,
   two +0.10 or four +0.05 awards to the same character qualify. Different PIDs,
   including alts, never pool. Negative deltas do not subtract earned credit.
   Ignore administrative adjustments, ship frags and arena scores.
4. **Bank only this round:** credit earned before hour 48 is remembered. More
   kills after qualification retain their ordinary rewards but buy no extra
   speed or future credit. Apply an entire combat event to one round, then
   evaluate its newly earned acceleration. No participant or surplus from that
   event may spill into the next round.
5. **Boundaries and recovery:** settle already-due transitions before assigning
   a new event; an admission exactly at a deadline belongs to the new round.
   A late event whose admission belongs to an already-closed round keeps its
   normal rewards but adds no credit to the current round. A replay adds nothing.
   Downtime catches up elapsed deadlines, never fresh waits from reboot time.
   At most 25 advances are possible from 31 to 56.
6. **One reward definition:** remove cap-specific faction-leader,
   shared-cap-minus-five, room-population and base-share checks. Keep the ordinary
   award producer's restrictions. Twenty people each awarded +0.05 from one
   victim do not qualify; four ordinary +0.05 awards to one person do.
7. **XP remains useful:** remove the over-cap 0.70 multiplier. Bank 100% of XP
   otherwise awarded after ordinary modifiers, respecting global/storage limits.
   Do not restore the former twice-next-level storage guard or grant free levels.

Fresh-season cap timing is 50 days to 56 with early qualification every round,
75 days with no PvP, excluding service failures. These are proposed pacing values,
not evidence of an optimal live balance.

## Source findings that determine the implementation

- [Combat capture](../../src/combat/fight.c), `submit_pvp_outcome()`, already computes
  final integer awards. [The coordinator](../../src/persistence/critical_command_coordinator.c)
  captures `critical_command.accepted_at_usec` once and preserves it on retry;
  it is serialized with the command. Use that durable admission timestamp for
  round membership. Do not use the mutable leaderboard or SQL insertion time.
- [MariaDB combat](../../src/combat/combat_outcome_repository.c) runs within the
  [critical repository](../../src/persistence/critical_command_repository.c)'s
  existing inbox/outbox transaction. A repeated operation returns its receipt.
- [Flatfile combat](../../src/flatfile/flatfile_player_domain_repository.c),
  `apply_combat_outcome_command()`, checks its receipt first, holds the existing
  authority lock, and atomically commits its prepared writes with that receipt.
  It can add the cap after-image to the same commit.
- [Cap maintenance](../../src/persistence/maintenance_repository.c) already has a
  [240-pulse job](../../src/persistence/maintenance_scheduler.c). Its flatfile
  dispatcher currently falls through to SQL for this job. Add a direct flatfile
  route before connection acquisition; keep this scheduler.
- [Cap readers](../../src/sql/sql.c) cache SQL state, while the client-free branch
  simply returns the configured floor. That stub is not backend parity.
- [Divine state storage](../../src/economy/divine_boon_repository.c) supplies a nearby
  small versioned-snapshot/flatfile-authority pattern. Reuse the underlying
  [atomic store](../../src/flatfile/flatfile_authority_transaction.h), not the
  boon feature or its legacy/draining state machine.
- [Fraglist](../../src/combat/fraglist.c) has cached and uncached output through
  [report caching](../../src/redis/redis_report_cache.c). Personal round progress
  must be rendered for the requesting player, outside shared cached text.
- [XP banking](../../src/world/limits.c), the existing cap tests and combat
  fixtures already provide most regression boundaries.

## Ablation decisions

**Keep one shared transition engine and one saved snapshot.** Both backends need
the same rules. Two small source/header pairs are justified: proposed
`src/combat/frag_cap.c/.h` for state, transitions, bounded codec and published
read state; `src/combat/frag_cap_repository.c/.h` for the two concrete storage
routes and refresh wiring. Keep configuration in the existing
[frag_cap_config](../../src/combat/frag_cap_config.c) module.

**Attach credit to the parent combat transaction.** This removes the need for a
second reward queue, another operation-ID ledger, callback-only recovery, and a
scan of old SQL/flatfile combat history. Existing receipt deduplication is the
proof that credit is applied once. Credit must not be written only from the
game-thread completion callback: a crash after the parent commit would lose it.

**Reuse the existing timer, admission timestamp, writer and store locks.** No
new background thread, clock framework, critical command type, combat payload
version, global combat resource key or per-player save fields are required by
this design. Backend locks serialize the small cap mutation with timer updates.

**Drop optional layers.** No feature-mode matrix, historical frag backfill,
per-side cap compatibility engine, personalized Redis keys, dashboards, new boon
or generalized repository abstraction. Retain old receipt/history fields and
numeric enum values where replay/telemetry compatibility needs them.

**Keep both backends and the real journey in the first delivery.** The 4–5-hour
target cannot be met by silently substituting a SQL-only patch, a model-only
test, or a reset-setting edit for the accepted proposal.

## Small state and transaction design

### Snapshot

One versioned object contains:

- revision and shared cap;
- persisted credit-admission cutoff for this policy/season;
- current round start, earliest and automatic deadlines;
- this round's target points and qualification timestamp (zero until secured);
- the current round's PID-to-earned-points map.

Store deadlines/target for the active round so a restart or changed boot setting
cannot retime an already published round. New settings apply when a new round
starts. Values are integer points/timestamps, not floating-point frag arithmetic.
Clamp earned points at the target; once secured, the display needs only the
secured state, so the partial-credit map can be cleared. Clear it on every unlock.

Use a bounded, validated codec following the existing domain-file conventions.
Reject corruption or overflow visibly; never truncate another player's credit.
Keep the supported population bound and full-combat after-image byte/operation
budgets explicit in tests. Avoid a player-count tuning option.

For SQL, add **one nullable snapshot column to the existing singleton
`level_cap` row**, through the next additive immutable migration. The snapshot
becomes the sole progression authority once initialized. Keep `level` and
`next_update` as projections for existing readers/tools, updated in the same
transaction; old side/leader fields stop controlling gameplay. Leave old history
intact. For flatfile, save the same encoded snapshot under the selected season's
`domains/frag-cap.state`. No additional table or store is needed.

### Applying an event

After the existing parent-receipt check, under the backend's existing transaction
or authority lock:

1. Read the current authoritative snapshot; settle elapsed deadlines using one
   captured current timestamp. Copy the latest state, not a game-thread cache.
2. Check the command's stable admission against the policy cutoff and current
   round interval. Exclude pre-cutover, already-closed-round and future-invalid
   events from cap credit without changing their legitimate ordinary rewards.
3. Apply all positive participant deltas to that round atomically. Set the
   qualification timestamp once, using the authority decision time captured for
   the successful transaction; it becomes confirmed with that commit. Do not use
   a later callback time or replace the timestamp on a replay.
4. Settle an unlock now due because of that qualification. No remaining
   participants in the same event are applied again to the newly opened round.
5. Persist the cap state together with the normal combat receipt. On SQL this is
   the caller's existing transaction: the helper must not begin/commit another.
   On flatfile append its after-image under the borrowed authority lock; do not
   reacquire the lock or commit a standalone file first.

A rollback loses both receipt and credit. An ambiguous commit resolves through
the existing receipt path. A restart loads the committed state. Recount the
flatfile transaction's current 82-operation bound when adding the extra image,
and adjust only the proven maximum; retain the full-group regression.

### Timer and publication

The existing maintenance job loads/settles/saves the same snapshot under the same
store lock. Repeating a tick against an already-settled timestamp is naturally
idempotent. Use effective deadlines for catch-up, not the worker's late arrival.
Check deadlines before every advance, stop at 56, and never reuse cleared credit.

Boot must validate/adopt the snapshot before ordinary progression is admitted.
A missing flatfile snapshot may be initialized once; corruption or I/O failure
must not masquerade as a new season. Preserve known state through transient reads.

After a confirmed combat write or timer result, request a coalesced asynchronous
refresh on the existing persistence writer. Publish on the game thread only if
the loaded revision is newer. A boot read recovers committed-but-unpublished
changes. Repeated refreshes must not regress a cap or repeat the same live
announcement. This refresh is observation, not a second mutation/reward queue.

Make `get_level_cap_info()`, `sql_level_cap()` and both backend branches read
that common published state. Keep their public signatures where consumers need
them; return the shared cap for every side. Retire the old unlock query and
fixed-floor flatfile behavior. The steady-state game loop must perform no
synchronous SQL or filesystem I/O.

## Current-season adoption and resets

The schema migration adds storage; it does not guess the live cap or clock.
On first activation, after validating the actual legacy inputs and draining
relevant old work, adopt once under the authority lock:

- Let `M` be the highest effective normal cap already open. Use
  `C = min(56, max(31, M))`. SQL supplies its live shared/side values; the legacy
  flatfile build supplies its previously configured effective floor, captured
  before replacing the configuration. Do not infer it from new defaults.
- If `C == 56`, retire the clock.
- If `M < 31`, opening 31 is the transition unlock; start normal deadlines now.
- Otherwise take the earlier of the valid old next-unlock timestamp and
  `now + 72h` as the first automatic deadline. Its earliest opportunity is up to
  24h earlier, never before activation. If the inherited deadline has expired,
  open one shared level immediately, then start a normal round.
- Start credit at activation; do not replay old-season kills or invent missing
  historical rounds. Repeated initialization reads the saved result unchanged.

Preserve character levels, banked XP and frag balances. Persist the actual chosen
cap/deadlines and include them in the eventual deployment handoff.

Wire a new 31/48h/72h state into the existing SQL pwipe reset after its writer
drain, preserving its season/reset-recovery fencing. Flatfile fresh-season
initialization belongs to the selected fresh season root; if a maintained reset
reuses a root, it must replace this snapshot too. Do not build a new wipe command.
Test that a resumed reset cannot reset the clock again or admit an old operation.

The migration must be guarded/re-runnable, with the normal manifest, bootstrap,
runtime-compatibility fingerprints and documentation updates. Allocate its number
from current master during implementation; do not reserve a stale number here.
Production migration/reset/deployment still requires owner authorization.
An application rollback must preserve already opened caps and account for the
new authority; merely booting an old flatfile binary would restore its old floor.

## Work sequence: 4½-hour target

These are elapsed implementation targets, not permission to omit a failing gate.
Start slow builds/test prerequisites early, and batch independent tool work.
No sub-agent delegation is assumed.

### 0–20 minutes: isolate, freeze inputs, establish the thin slice

Create the isolated implementation checkout. Recheck source/migration drift and
the linked proposal. Confirm the single-row SQL adoption inputs and the flatfile
parent-receipt/borrowed-lock insertion point. Prepare disposable fixtures and
start the first build/prerequisite work. Reuse existing build output/cache where
safe; never overwrite the other task's source or mixed-backend objects.

### 20–55 minutes: state/rules and native tests

Implement the shared transitions/codec and updated configuration. Extend the
existing cap test driver, or add one focused native state test if its SQL-only
driver is the wrong home. Inject `now` into the production transition function;
do not add a production clock command or use multi-day sleeps.

Prove the basic threshold, timing, event-boundary and cutover cases before I/O.
This locks down one rules implementation for both adapters.

### 55–125 minutes: atomic credit and persistent clock on both backends

Add the nullable SQL snapshot storage and flatfile state adapters. Connect credit
inside both existing combat transactions and route flatfile cap maintenance
before SQL connection acquisition. Add boot adoption, ordinary reset and receipt
replay tests. Use parent receipts and stable admission time; keep codecs/result
formats compatible.

**Checkpoint at 125 minutes:** partial credit must survive a native store reopen,
and replay must add nothing on both backends. If this is not true, the 4–5-hour
target is at risk. Resolve the demonstrated missing path before adding UI polish;
do not replace it with in-memory or SQL-only behavior.

### 125–160 minutes: readers, feedback, XP and help

Connect committed-state publication and all cap readers. Render the shared
earliest/automatic countdown and viewer progress outside the shared Redis payload;
cover both cached and uncached fraglist paths. Reuse existing combat feedback and
operator alerts for pending/failing recording, with an operation reference for
recovery. Do not add an offline-mail or diagnostics subsystem.

Remove the cap-specific XP modifier from its actual application path and retire
its unused configuration; preserve historical telemetry IDs if compatibility
requires them. Update cap/frag/Hardcore help and the progression reference.
Build both backends in separate existing build roots/output paths.

### 160–240 minutes: executable, storage and gameplay proof

Run the focused suites below. Extend existing native combat/cap fixtures rather
than writing another persistence test framework. Include migration repeat and
compatibility checks and a small full-server PvP/restart journey on both backends.

Use the existing full-world setup/client/authority helpers from
[test_divine_boon_zone_journey.py](../../tests/async/test_divine_boon_zone_journey.py)
and its imports. A small focused `test_frag_cap_journey.py` may reuse these helpers;
it should not rerun unrelated cargo/boon/quest campaigns. Minimal combat fixtures
currently skip the maintenance scheduler, so they alone cannot prove the live
timer. Seed an isolated round close to its real deadline before boot, then let
normal PvP, maintenance, status and XP commands drive the transitions.

### 240–270 minutes: ablate the diff and finish the handoff

Check that the old cap updater has no live caller, both backends use one engine,
and no gameplay path still consults leader/victim/ally predicates. Remove dead
knobs introduced/replaced by this change without deleting historical receipts.

Finish formatting, relevant documentation/link checks and the change review.
Record exact commands/results and any material qualification limit in this plan
and the eventual PR. A ready change includes the adoption/reset instructions.

### 270–300 minutes: contingency

Use only for real build/test/integration findings. At 300 minutes, report actual
remaining work and revise the estimate if necessary; keep required semantics and
proof intact. Do not call incomplete work complete to hit the time target.
Full burn-in, broad unrelated regressions, CI waiting and production deployment
are not substitutes for, or additions to, the focused delivery gate.

## Focused verification and ownership

Extend these existing tests at their relevant seams:

- [Cap SQL lifecycle](../../tests/async/run_level_cap_mysql.py) and its
  [native harness](../../tests/async/level_cap_mysql_harness.cpp): real timer,
  credit, cutover, missing-state/error and transaction races.
- [SQL combat receipts](../../tests/async/run_combat_outcome_schema_mysql.sh) and
  [flatfile domain harness](../../tests/async/flatfile_player_domain_repository_harness.cpp):
  credit in the parent commit, full groups, repeated operation, ambiguous commit,
  interrupted flatfile commit/recovery and reopen.
- [Combat codec/cutover](../../tests/async/test_combat_outcome_transactional_cutover.py)
  and [normal awards](../../tests/async/test_pvp_group_rewards.py): preserve legacy
  receipt/payload behavior and normal reward calculations.
- [XP feedback/banking](../../tests/async/test_world_quest_xp_feedback.py):
  over-cap award becomes 100% of otherwise computed XP; banked XP stays locked
  until the shared cap permits it, with global ceilings/overflow handling intact.
- [Hardcore](../../tests/async/test_hardcore_config_runtime.py),
  [configuration contract](../../tests/async/test_frag_cap_config_contract.py),
  [singleton](../../tests/async/test_level_cap_singleton_contract.py) and
  [cache codec](../../tests/async/test_report_cache_codec.py): update obsolete
  assertions, not merely their expected strings.
- [Migration engines](../../tests/async/run_migration_runner_engines.py),
  [runtime compatibility](../../tests/async/test_runtime_boot_compatibility.py)
  and [immutable runner](../../tests/async/test_immutable_migration_runner.py):
  follow the repository's existing schema-fingerprint workflow; do not invent
  hashes or edit prior migrations.
- The focused full-server journey: a real qualifying mortal PvP death records
  normal frags and round credit; fraglist shows the same progress on both paths;
  normal maintenance opens the shared level; a legitimate positive XP action
  spends banked XP within that cap; restart/re-entry preserves state.

Representative commands from the implementation checkout:

```sh
make -C src -j4
python3 tests/async/test_frag_cap_config_contract.py
python3 tests/async/test_level_cap_singleton_contract.py
python3 tests/async/test_pvp_group_rewards.py
python3 tests/async/test_combat_outcome_transactional_cutover.py
python3 tests/async/test_flatfile_player_domain_repository.py
python3 tests/async/test_world_quest_xp_feedback.py
python3 tests/async/test_hardcore_config_runtime.py
python3 tests/async/test_report_cache_codec.py
bash tests/async/with_disposable_mariadb.sh python3 tests/async/run_level_cap_mysql.py
bash tests/async/with_disposable_mariadb.sh bash tests/async/run_combat_outcome_schema_mysql.sh
python3 tests/async/test_runtime_boot_compatibility.py
python3 tests/async/test_immutable_migration_runner.py
python3 tests/async/run_migration_runner_engines.py
./scripts/format.sh --check
```

Also build/run the flatfile server with the existing
[server build helpers](../../tests/async/server_build_artifacts.py), run the new
native policy and focused journey cases, and repeat the relevant SQL lifecycle
on supported MySQL 8.0. Record their exact entry points once implemented.
All database/character fixtures must be disposable; do not source production
credentials or operate on existing players. Do not rebuild or rerun already-green
unrelated suites without a new reason.

Required scenario checklist:

- [ ] Fresh 31; all sides share caps; 56 ceiling; Hardcore +2; ordinary XP/epic limits.
- [ ] 19/20-point boundary; same-PID accumulation; no cross-PID/alt pooling.
- [ ] Twenty +5 winners do not qualify; four +5 awards to one PID do.
- [ ] Negative deltas never erase progress; zero/non-PvP/arena awards do not add it.
- [ ] Qualification at hour 1/47 opens at 48, hour 60 opens when confirmed,
      no qualification opens at 72; exact boundary belongs to the new round.
- [ ] Whole-event consumption, surplus disposal, delayed closed-round receipt,
      unchanged qualification time on replay and multiple qualifying recipients.
- [ ] Rollback/ambiguous commit, lost publication, reopen/restart, corrupted state,
      timer-versus-combat contention and no silent fallback/reset.
- [ ] Elapsed-time catch-up without reusing credit; 50/75-day schedules.
- [ ] M below 31, divergent old side caps, earlier/future/expired old deadline,
      existing 56, repeated adoption and resumed season reset.
- [ ] Cached/uncached per-viewer status; pending/failure feedback; no repeated
      live announcement or older-revision publication.
- [ ] Real PvP → receipt → maintenance → shared cap → XP advancement → restart
      on both backends.

## Completion record

Planning verification: issue/proposal re-read; owning source and transaction
boundaries inspected. The earlier 18-assertion policy model is useful input but
does not qualify a server implementation.

Passed the maintained Markdown link/anchor check for the new plan:
`python3 tests/async/test_documentation_contract.py DocumentationContractTest.test_maintained_markdown_links_and_anchors_resolve`.

### Chunk 1: shared rules and snapshot

Outcome: one engine implementing the fixed contract for both backends. Files:
`src/combat/frag_cap.c/.h`, `src/Makefile`, and
`tests/async/frag_cap_harness.cpp` / `test_frag_cap.py`. Non-goals for this chunk:
storage adapters, runtime publication, configuration cutover and player feedback.
Those remain mandatory in dependent chunks. Ablation retained only pure state
transitions and the common codec; replay identity stays in the parent receipt,
with no new operation ledger, scheduler, clock abstraction or player fields.

- Passed `python3 tests/async/test_frag_cap.py`: native executable tests for
  19/20 points, same-PID accumulation, negative deltas, twenty +5 recipients,
  two +10/four +5 events, hour 1/47/48/60 qualification, exact 72-hour admission,
  delayed/pre-cutover/future-invalid admissions, whole-event consumption,
  immutable qualification, quiet/active schedules, catch-up, adoption and ceiling.
- Snapshot timestamps use Unix **microseconds**, matching durable admission.
  SHA-256 protects the versioned encoding. Maximum 65,536 active partial-credit
  contributors; exact maximum encoded size **393,318 bytes**. Overflow fails the
  preparation without modifying its input; no balance is evicted or truncated.
- Codec tests cover every single-byte corruption, truncation, unsupported version,
  maximum population, invalid state and revision/time overflow. A future adapter
  must surface these failures and keep rewards/credit in the same transaction.
- Passed `make -C src -j4` and `make -C src -j4 PERSISTENCE_BACKEND=flatfile
  DMS_BINARY=../bin/server/dms_flatfile` with separate backend objects/binaries.
- Passed `./scripts/format.sh --check`, `git diff --cached --check`, and
  `python3 tests/async/test_documentation_contract.py
  DocumentationContractTest.test_maintained_markdown_links_and_anchors_resolve`.
- **Not yet proven:** parent-receipt replay, database/flatfile persistence,
  publication, reset fencing, XP/help/status, and real gameplay journeys.

Rules PR: [#514](https://github.com/LuminariMUD/Duris/pull/514), head
`branch/issue-508-frag-progression` at `422a9e7cc`, base `master`.
No release tag belongs to these preparatory changes; deployment remains separate.

### Chunk 2: durable storage adapters and additive schema

Current checkout remains `/home/aiwithapex/projects/duris-issue-508`, now on
`branch/issue-508-frag-cap-storage`, based on chunk 1. This chunk adds
`src/combat/frag_cap_repository.c/.h`, native storage tests and immutable migration
`0057_shared_frag_cap` (sequence 58). The snapshot is a nullable MEDIUMBLOB on the
existing singleton. Old migrations and baseline bootstrap SQL stay immutable;
fresh bootstraps reach the same shape through the maintained migration runner.
The manifest, compiled compatibility contract and measured MariaDB/MySQL metadata
fingerprints are synchronized. No new table, player field or receipt ledger.

The adapter borrows the caller's SQL transaction or already-recovered flatfile
authority lock. The flatfile preparer only appends an after-image; no nested lock
or separate cap commit. Boot adoption is idempotent and refuses corruption or a
missing/invalid SQL singleton. Timer updates use the same lock and engine.

Proof:

- Passed `python3 tests/async/test_frag_cap_repository.py`, compiled with ASan/UBSan:
  durable partial credit, reopen, parent-receipt replay, interrupted journal/image
  recovery, failure before commit, immutable qualification, timer and corruption.
- Passed `bash tests/async/with_disposable_mariadb.sh python3
  tests/async/test_frag_cap_repository.py --mysql` on disposable MariaDB 10.11.
- Passed the same command with `TEST_DB_IMAGE=mysql:8.0` on disposable MySQL 8.0.
  Both initialize from bootstrap through the real migration runner, repeat the
  runner, repeat the new additive migration, verify preserved legacy values and
  validate the full runtime metadata fingerprint. SQL tests prove parent rollback,
  deduplication, legacy side-cap adoption, corruption and missing-row refusal.
- Passed both server builds with the commands recorded in chunk 1.
- Passed `python3 tests/async/test_runtime_boot_compatibility.py` (7 tests) and
  `python3 tests/async/test_immutable_migration_runner.py` (26 tests).

The parent in these adapter tests is a small native receipt fixture. **Actual
combat transaction integration and gameplay are not yet qualified.** This is a
preparatory storage PR; it must not be reported as feature completion.

Next: open the storage PR stacked on #514, then activate the policy in a dependent
chunk: attach both real combat paths, route both maintenance paths, add boot
adoption/publication, reset fencing, shared readers/status, XP/help and journeys.
The original scenario checklist remains the completion gate. Reuse the focused
two-engine migration/metadata proof above rather than rerunning unrelated Nexus,
artifact and shop campaigns from `run_migration_runner_engines.py` for one column.
