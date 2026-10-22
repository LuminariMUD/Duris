# Issue #245: rotating Divine Boons

> **Critical delivery constraint: our resources and tokens are very limited,
> the deadline is already past due, and we must deliver as fast as possible.**
> This governs the entire plan: take
> the shortest path that meets all requirements, reuse existing code and valid
> evidence, and defer optional work. Required correctness and recovery remain
> part of completion.

Status: implementation in progress; rotation, storage, writer/boot, legacy admissions and account activity implemented.
Prepared 2026-10-22 for [Duris #245](https://github.com/LuminariMUD/Duris/issues/245).
Implementation branch: `branch/issue-245-divine-boons`.
Source baseline: [master `e897b5214893`](https://github.com/LuminariMUD/Duris/commit/e897b5214893a66b75db5507be0a9be97b519cfc).
Issue specification inspected at its 2026-10-22 update, including all five comments.
The agreed follow-up decisions take precedence over older exploratory numbers.
The previous issue-59 plan is preserved byte-for-byte in
[plan-issue-59.md](plan-issue-59.md); earlier plans remain in their existing files.

The current request authorizes implementation, focused tests, commits, pushes
and review-ready PRs, stacked as dependencies become ready. It supersedes the
issue's older design-only restriction. Production migrations/imports, deployment,
restart and merge remain separate actions.

## Implementation handoff (2026-10-22)

- Worktree: `/home/aiwithapex/projects/duris-issue245-plan`; branch
  `branch/issue-245-divine-delivery`, stacked on `branch/issue-245-divine-activity`
  -> `branch/issue-245-divine-cutover`
  -> `branch/issue-245-divine-runtime` -> `branch/issue-245-divine-persistence`
  -> `branch/issue-245-divine-boons`.
- Review-ready foundation: [PR #265](https://github.com/LuminariMUD/Duris/pull/265),
  implementation commit `8cbc07fc4`. Further chunks stack on this branch.
- First chunk: `src/economy/divine_boon.{h,c}` implements the eight-slot state,
  category rates/lifetimes, forward legacy/draining/Divine mode transitions,
  fixed UTC hours, skip-on-restart/clock-jump policy, pause/expiry, replacement,
  stable identities, cross-category same-side duplicate rejection and bounded
  expired-zone history. One versioned SHA-256 snapshot format serves both
  future backend adapters. Changes prepare a state; callers must commit it
  before making it visible to gameplay.
- Proof: `python3 tests/async/test_divine_boon.py` passes with ASan/UBSan.
  It exercises the actual state implementation and corruption/truncation of
  snapshots. `make -C src -j12` and changed-file formatting checks pass.
  `./scripts/format.sh --all --check` passes for all 1100 tracked C/C++ files.
  Use `CLANG_TIDY=/home/aiwithapex/.local/bin/clang-tidy` (installed LLVM 22)
  for commits: system LLVM 18 cannot parse the installed GCC 16 headers.
- Second chunk: `divine_boon_repository.{h,c}` provides SQL compare-and-swap
  and flat-file authority after-image commits for the shared snapshot. Exact
  retries are idempotent, stale/rerolled revisions conflict, and corrupt state
  cannot be overwritten. Migration `0048_divine_boon_state` is additive and
  re-runnable, registered with lifecycle and compiled runtime schema contracts.
  Metadata fingerprints were measured on disposable MySQL 8 and MariaDB 10.11;
  both runtime compatibility verifiers pass. No existing databases were changed.
- Review-ready persistence: [PR #266](https://github.com/LuminariMUD/Duris/pull/266),
  implementation commit `99da4373f`, stacked on #265.
- Second-chunk proof: flat-file ASan/UBSan repository harness covers failures
  before commit, after journal commit and after the state after-image, plus
  recovery/retry, stale writes and corruption. The MariaDB repository harness,
  schema apply/replay/verifier, lifecycle/runtime validators, seven boot contract
  tests and 21 immutable migration tests pass. Both MariaDB and flat-file server
  builds pass (`DMS_BINARY=.../bin/server/dms_new_flatfile` isolates flat-file output).
- Third chunk: `divine_boon_runtime.{h,c}` wires boot loading/reconciliation and
  confirmed publication into `comm.c`. One appended writer job kind orders
  state saves with existing player/ship work. New installations retain legacy
  mode; this does not activate Divine gameplay. The game sees a new snapshot
  only after a successful commit; interrupted writes retain the exact pending
  choice and retry, while invalid/conflicting authority disables bonuses.
- Review-ready writer/boot integration: [PR #267](https://github.com/LuminariMUD/Duris/pull/267),
  implementation commit `93f856f06`, stacked on #266.
- Third-chunk proof: `test_divine_boon_runtime.py` passes with ASan/UBSan using
  the real writer, including queue refusal, blocked-writer publication ordering,
  committed journal recovery, exact retry and restart skipping. Existing
  `test_player_save_worker.py` and both server backend builds pass. Earlier
  state/repository proof remains valid and was reused.
- Fourth chunk: legacy command/shop/create/extend/reward and new scan admissions
  close immediately when draining is queued or authority is unavailable. Accepted
  reward/shop completion and login recovery handlers continue unchanged. Restored
  SQL scans check durable mode before parsing old payloads, then recheck with a
  row lock inside the scan transaction; a concurrent retirement must wait for the
  accepted scan or prevent its mutations. Missing/corrupt authority fails closed.
- Fourth-chunk proof: real reward and shop transaction handlers reject new work
  while accepted callbacks still publish once (existing ASan/UBSan epic harness).
  Runtime admission-state, scheduler, producer replay and 13 boon cutover contract
  tests pass. The disposable MariaDB scan fixture exercises live legacy expiry,
  concurrent state-writer locking, restored no-ops and corrupt-state rejection.
  Both server backend builds and changed-file formatting pass.
- Review-ready admission barriers: [PR #268](https://github.com/LuminariMUD/Duris/pull/268),
  implementation commit `315b04fab`, stacked on #267. This is not the completed
  receipt-retirement or activation step.
- Fifth chunk: `divine_boon_activity.{h,c}` observes real playing-input effects
  on room, combat, casting/resources or inventory and keeps bounded 60-minute
  histories by canonical account and side. Repeated no-op input, automatic
  combat and force-like changes to another actor supply no new observation.
  Accounts need gameplay within 15 minutes and a current mortal, non-AFK,
  connected representative. History survives alt changes, including logout;
  PvP qualification needs five distinct observed minutes spanning five minutes,
  and the same account cannot qualify both opposing populations. The four level
  brackets count one representative per account/side. Morphs use their owner;
  staff accounts and unaffiliated characters are excluded. There is no telemetry
  dependency, gameplay I/O or new copyover format.
- Fifth-chunk proof: ASan/UBSan activity harness covers window boundaries, account
  case/alt deduplication, cross-side alts, all bracket edges, stale history,
  real input/automatic/forced/no-op differences, AFK/link-dead/staff exclusions,
  safe extraction and morphed players. Both server backend builds, affected item
  input queue/newbie grant regressions, command latency and telemetry hook checks
  pass. Prior rotation, state persistence and reward evidence remains valid.
- Review-ready activity: [PR #269](https://github.com/LuminariMUD/Duris/pull/269),
  initial implementation `0b6b4926b`, stacked on #268. Cross-side accounts are
  assigned to only one PvP population, balancing available distinct accounts;
  a lone account cannot fabricate an opponent, while a valid different account
  on the other side remains usable.
- Selection integration: call `divine_boon_activity_population()` to obtain
  per-side `brackets`, `active_accounts` and distinct `pvp_accounts`; do not use
  descriptors, hosts or optional telemetry as a substitute for this history.
- Sixth chunk: player status snapshots now checkpoint an unsigned Divine delivery
  sequence with the epic balance. Both repositories reject a status capture below
  the saved watermark, even if its general save revision is newer. Snapshot v10
  upgrades supported older snapshots with a zero watermark; additive migration
  `0049_divine_boon_delivery` preserves balances and defaults existing players to
  zero. This is the recipient checkpoint boundary; prepared-award sequencing,
  publication and login recovery still need integration before any Divine payout.
- Sixth-chunk proof: focused capture, codec, player materialization and load tests
  pass. Flat-file journal interruption/retry preserves the balance and watermark;
  stale, signed and duplicate markers are rejected. Disposable MariaDB save/load
  fixtures prove the same stale rejection and atomic rollback on an injected
  balance/marker update failure. Migration apply/replay and exact verifiers pass
  on disposable MySQL 8 and MariaDB 10.11, with measured runtime fingerprints.
  The runtime validator, seven boot-contract and 21 migration-runner tests pass.
- **Next:** complete legacy receipt retention/delivery reconciliation before activation.
  Then implement the candidate/activity, reward, cargo and command/help paths
  below. The state API does not itself prove targets safe or legacy work settled.
- Concrete next integration findings: `boon_shop()` spends MariaDB stat points
  in a queued writer job and raises/refunds the stat in its completion; closing
  new admissions must not suppress that accepted completion. Legacy flat-file
  `publish_reward()` acknowledges after live publication, and SQL legacy outbox
  delivery currently acknowledges a decoded result without proving a player
  checkpoint. Preserve those exact receipts until delivery is reconciled.
  Likewise, SQL `execute_epic_state()` advances `player_data.epic_revision`
  before saving the new balance, so that existing field alone cannot prove
  durable recipient delivery. Bind prepared Divine awards and their applied
  marker to the player status save; keep activation closed until these paths
  are resolved. No staff command or automatic switch currently enables Divine.
- Recipient-recovery direction: carry an ordered per-recipient delivery sequence
  with the full prepared zone/PvP award, and checkpoint an applied watermark
  atomically with the recipient balance. Recover unpaid sequences before new
  recipient admissions; reject older snapshots that would overwrite a newer
  applied watermark. This stays within the existing prepared payloads and player
  status boundary; do not change general currency semantics or add per-hit XP I/O.
- **Still open:** every full-feature acceptance item. The rotation core is a
  dependency; backend persistence and writer ordering are proven above, while
  live candidate rotation, completed cutover, gameplay payouts and Divine Boons
  remain unproven. No production action performed.
- Ablation: reuse one state/codec for both backends; no scheduler, delivery
  framework, general economy rewrite or extra verification campaign added.
  State revision plus an atomic snapshot supplies retry identity; no additional
  critical-command type, outbox or duplicate receipt catalogue is needed.
- Next delivery step: allocate recipient sequences in the existing writer under
  the recipient row/authority lock, including earlier prepared receipts. Do not
  derive a new sequence from the live applied watermark: multiple accepted
  awards before completion would collide. Publish and recover in sequence,
  saving the amount and applied watermark through the player status boundary.
- Remaining estimate at this checkpoint: 6-8 hours of active implementation and
  focused verification, including review-ready PRs. Cargo recovery and flat-file
  epic payouts remain the largest costs; this is an estimate, not time to fill.

## Outcome

**Delivery priority:** resources and tokens are very limited, and the deadline
is already past due. Deliver the complete required outcome as fast as possible.
Add no optional scope.

Replace the player-facing legacy task/shop boon system with automatic,
persistent world bonuses. Retain `boon`, `boon list` and `CMD_BOON=804`.
Deliver all of #245, including safe legacy retirement, both persistence backends,
real reachable targets, reward integration, cargo anti-abuse and recovery,
staff controls, help and executable acceptance evidence.

Eight slots are global, not eight per side. A slot has one category and lifetime,
with optional Good/Evil objectives. EXP and epic-zone bonuses last eight real
hours; Cargo/Contraband and PvP last four, never longer. At most one Cargo and
one PvP boon coexist. PvE may occupy every remaining slot without a three-per-type
cap. Start empty and add at most one boon per fixed UTC hourly opportunity.
Expire on time; a freed slot may stay empty until a later opportunity.

The rates are 200% total eligible NPC combat EXP, +50% eligible zone epics,
+50% legitimate Good-versus-Evil PvP epics, and +25% qualifying cargo AND
contraband base sale revenue. New Divine benefits add a contribution calculated
from the original eligible base; they do not multiply an already boosted total.
Keep the existing eligibility rules, penalties and final caps.

## Verified code findings and implications

These are facts about the pinned checkout, not claims about production content
or deployed settings. Function names below are navigation points at that commit.
Use these findings to focus the limited time on known required changes. Reopen
investigation only where implementation exposes a concrete unresolved question.

1. **Command replacement is small; legacy retirement is not.**
   [interp.c](../../src/cmd/interp.c), `CMD_BOON` registration at 3454, calls
   `do_boon()`; [interp.h](../../src/cmd/interp.h) defines 804 at 841.
   [boon.c](../../src/economy/boon.c), `do_boon()` at 1573, owns list, shop and
   editing dispatch. `boon_randomize()` at 2924 really is unfinished.
   `check_boon_completion()` at 3027 admits rewards through a transaction;
   changing command dispatch cannot stop its combat/zone/economy callers.

2. **There are independent legacy mutation and delivery paths.**
   [boon_reward_transaction.c](../../src/economy/boon_reward_transaction.c),
   `publish_reward()` at 70 and `player_ready()` at 199, distinguishes live
   publication from flat-file acknowledgement and login delivery. The published
   marker is process memory, not a durable proof of player delivery.
   [boon.c](../../src/economy/boon.c), `boon_shop()` at 1908, uses a flat-file
   transaction but a separate SQL writer/callback path for MariaDB purchases.
   [maintenance_scheduler.c](../../src/persistence/maintenance_scheduler.c),
   initialization at 640, restores unfinished work; the flat-file scan also
   reaches `boon_maintenance()` via completion dispatch.
   A mode flip or suppressed callback alone cannot settle earned rewards.

3. **An operation ID does not currently make wallet payment idempotent.**
   [currency_transaction.c](../../src/economy/currency_transaction.c),
   `currency_transaction_submit_identified()` at 262, explicitly ignores its
   operation ID and updates live money; player saves persist it later.
   [epic_transaction.c](../../src/world/epic_transaction.c), submit at 36,
   likewise changes the live epic balance before queuing ledger evidence.
   [combat_outcome_transaction.c](../../src/combat/combat_outcome_transaction.c),
   `apply_live()` at 62, applies participant deltas in memory.
   Reuse their accounting rules, but do not claim these APIs alone supply
   durable exactly-once delivery. New recoverable rewards need a delivery
   marker committed with the corresponding player state.

4. **EXP has distinct share derivation paths and intermediate truncation.**
   [limits.c](../../src/world/limits.c), `gain_exp()` at 1125, normalizes
   `EXP_KILL_BONUS`, derives tanking recursively from damage before damage
   modifiers, and obtains a healer's hostile NPC through `GET_OPPONENT(victim)`.
   Damage, tanking, healing, melee and kill branches apply their own modifiers.
   Final difficulty scaling precedes integer conversion and the one-third-level
   cap around 1505-1525. Rest, Nexus and epic bonuses occur earlier.
   A late `XP *= 2` compounds existing boosts; an early multiplier also boosts
   the recursively derived tank share again. Neither implements the agreed math.

5. **The active PvP caller differs from the issue's suggested two-route model.**
   [fight.c](../../src/combat/fight.c), `opposite_racewar()` at 522, accepts
   any differing racewars. Death admission around 2510 and
   `submit_pvp_outcome()` at 963 retain the victim and existing frag gates.
   It adds Spill Blood's 500 before calling `epic_calculate_pvp_award()`.
   [epic.c](../../src/world/epic.c) has another implementation in
   `epic_frag()` at 679, but a repository-wide caller search finds only its
   definition and declaration. Do not build a second live payout route merely
   because the issue assumes both are live. Consolidate qualification and math;
   retain generic `gain_epic(EPIC_PVP)` behavior without an unqualified Divine boost.

6. **Flat-file epic support requires more than a candidate codec.**
   [sql.c](../../src/sql/sql.c) at 581-591 supplies empty/failing flat-file
   `sql_zones()`/`get_zone_info()` stubs. The
   [epic task catalogue](../../src/world/epic_task_catalog.c), refresh at 98,
   reports `database_disabled` and otherwise selects `task_zone=1` rows.
   More decisively, [zone_touch_transaction.c](../../src/world/zone_touch_transaction.c),
   submit at 99, explicitly rejects non-MySQL mode.
   Its SQL publication at 60-95 adds player epics with process-local markers;
   recovered stone claims skip repeat side effects. A ledger receipt therefore
   does not by itself prove a player save contains the reward.
   Both real flat-file touch support and durable recipient recovery are in scope.
   [epic.c](../../src/world/epic.c), `epic_stone_payout()` at 780 and touch
   preparation at 1125-1168, already provides group/stone gates and per-recipient
   prepared awards worth extending.

7. **Cargo loses batch identity and settles separate effects.**
   [ship_shop.c](../../src/ships/ship_shop.c), `buy_cargo()` at 2041 and
   `buy_contra()` at 2197, merges quantity and invoice cost by commodity.
   Sales at 936-1230 clear slots, modify markets, credit money, then queue ship
   saves and a separate market write. The market write's own SQL transaction
   does not make that whole sale atomic. Current sales select whole slots;
   partial eligible quantities inside a slot still require exact accounting.
   [ShipSlot](../../src/ships/ships.h) stores counts/costs, not purchase identity.
   Jettison and salvage in [ship_utils.c](../../src/ships/ship_utils.c) at
   2460-2707 discard/reconstruct crates; salvage does keep invoice-free crates
   separate from purchased slots today. Preserve that existing cost-basis rule.
   Customs confiscation and `clear_cargo()` are additional quantity mutations.

8. **Capacity and selection have reusable code, with narrower guarantees.**
   [ships.h](../../src/ships/ships.h) at 685-700 expresses combined cargo and
   contraband load in crates, with two weight units per crate. `SHIP_MAX_CARGO`
   includes a crew modifier; available capacity is also weight-limited.
   [world_quest_policy.c](../../src/world/world_quest_policy.c), the updated
   bartender quest policy, caches zone/mob profiles, excludes `ZONE_TOWN`,
   uses level windows and weighted scores, and bounds target probes.
   [world_quest.c](../../src/world/world_quest.c), assignment at 794, tries
   distinct targets with finite budgets. Its item-reward suitability and map
   heuristics are not proof of Divine side accessibility or epic completion.
   [maintenance_snapshot.c](../../src/persistence/maintenance_snapshot.c)
   at 90-144 counts current descriptors and unique hosts, not active accounts.
   Newer [interp.c](../../src/cmd/interp.c) at 149-188 and
   [telemetry_runtime.h](../../src/telemetry/telemetry_runtime.h) at 345-378
   expose activity evidence, but telemetry is optional and its session counters
   are not the requested rolling, account-deduplicated gameplay population.

9. **Runtime flags and help precedence must remain authoritative.**
   [db.c](../../src/world/db.c) at 1783-1817 initializes hometown to zero and
   loads `ZONE_TOWN` independently; a real town can have index zero.
   The existing `BOON` topic in
   [help_index](../../lib/information/help_index) at 1686-1706 still advertises
   participation toggling and the shop. Parsed help currently has no actual
   Boon topic. [HELP_SYSTEM.md](../content/HELP_SYSTEM.md) documents that a
   matching parsed-help title overrides help_index, including in flat-file mode.
   Update maintained sources consistently; do not create contradictory copies.

## Ablation decisions: non-goals, files and proof

**Resource, token and overdue deadline rule:** these scope limits are essential
to finishing as fast as possible. Every addition must be needed
for a retained requirement or its proof; defer optional improvements and polish.

**Keep:** the issue's gameplay, both backends, safe legacy retirement, prepared
reward identity, cargo batch/cap/payment recovery, hard target exclusions,
activity rules, commands/help and actual-path tests. These are requirements,
not optional hardening. There is no permission to replace exactly-once trade
settlement with a best-effort multiplier or to defer flat-file epic payouts.

**Second-pass changes and retained limits:**

- **No general reward/save redesign.** Extend only the existing stone/combat
  payloads and the player checkpoint fields needed to recover Divine awards.
  Use the existing single writer, save ordering and flat-file after-images.
  Do not add an economy-wide delivery service or retrofit unrelated rewards.
- **No historical reward conversion engine.** Close legacy admissions, let
  existing handlers drain accepted work, and durably retain unresolved exact
  entitlements. Do not rewrite every old cash/level/stat/affect reward into a
  new format. Retention is not acknowledgement or loss; recovery must still
  distinguish already delivered from unpaid work.
- **No new runtime rollback workflow.** Preserve legacy balances/history and
  new receipts; document a controlled backout after reconciling pending work.
  Do not add reverse migrations, a second online mode-switch engine or its
  test matrix. The forward legacy -> draining -> Divine transition remains.
- **No universal trade rewrite.** Atomic purchase/sale receipts cover qualifying
  boon lots and sales that include them, including mixed eligible quantities.
  Ordinary unrelated cargo/payment paths keep their current behavior. The
  receipt's small player/ship/market/cap boundary is still mandatory.
- **No world-wide content audit or mandatory duplicate metadata registry.**
  Cache a bounded safe pool from runtime zones, bartender profiles, real stones
  and existing metadata. Add only missing explicit safety/side-access metadata
  for that pool. Do not invent a second payout source or a generic reachability
  engine. Positive normal access and actual flat-file payout remain required.
- **No activity-history copyover format.** Keep the required 60-minute bounded
  gameplay history in memory and warm it from observed play after process
  replacement. Slots, timestamps, caps and receipts still persist normally.
- **No six-PR delivery requirement or repeated full verification per unit.**
  The steps below describe dependencies, not mandatory PR boundaries. Run a
  focused check when its consumer changes; retain its valid result and run one
  integrated journey per backend at the end. No full burn-in or CI wait.
- **No new broad balance study.** Assess the approved cargo economics with
  representative actual routes/capacities and deterministic fixtures. Keep the
  required 25% and three-hold policy; no live soak or analytics project.

Also exclude new schedulers/services, PostHog dependencies, generic quest/reward
frameworks, point conversion, per-side eight-slot pools, quotas, instant refill,
catch-up bursts, alternate colouring and player/ship location displays.

**Files:** core changes belong in one `divine_boon.{h,c}` module and its minimal
backend persistence boundary, existing boon admission/scan handlers, interpreter/
toggle, `limits.c`, `epic.c`, `zone_touch*`, `fight.c`/`combat_outcome*`,
ship shop/cargo mutation/save code and help. Extend SQL/flat-file player or ship
snapshot capture/load only where the concrete receipt must share a save.
Do not refactor the general currency API merely to give it new semantics;
the cargo operation owns its idempotent payment boundary.

**Proof:** extend existing executable harnesses and disposable database/file
fixtures. Add a small clock/selection test and the missing domain recovery
cases; no new test framework. Helper/codec checks cannot prove a reachable
command, real stone payout or recoverable sale. Gameplay implementation is now
authorized; production actions remain outside this work.

## Implementation sequence

These are dependency steps within the same issue and branch, not six separately
qualified projects. Preserve every acceptance item in the closure map.

**Execution priority:** resources and tokens are very limited; we are already
past the deadline and must deliver fast. Keep reasoning and progress reports brief.
Keep each step to its required changes and focused proof, reuse valid results,
and move directly to the next dependency as soon as the current one is complete.

### 1. State, hourly rotation and forward legacy cutover

**Overdue delivery focus:** reuse the existing writer and recovery machinery to finish
the required state and safe cutover with the smallest necessary changes.

- In the Divine module store eight slots with stable boon IDs, category/rate,
  absolute starts/expiry, per-side objectives, revision, pause flag, last UTC
  opportunity and expired-zone history. Slot number is not award identity.
  Persist via the existing writer and versioned SQL/flat-file records; use
  unique opportunity/operation keys and atomic checksummed after-images.
  Commit a selected or empty result once, then publish its cache. Invalid
  persisted state disables new admissions without deleting historical data.
- Start empty at cutover and use fixed UTC hourly boundaries. At most one
  generation per opportunity; EXP/epic last eight real hours, Cargo/PvP four.
  Enforce eight global slots, one Cargo and one PvP, no other category quota.
  Expiry is checked by display/award queries as well as maintenance.
- Reboot expires overdue slots and consumes/skips missed opportunities; resume
  at the next future hour. No burst, reroll or timestamp extension. Pause
  consumes opportunities and prevents new spawns, while expiry continues.
  Resume waits for the next hour. Forward clock jumps skip elapsed hours;
  backward jumps cannot revisit an already consumed hour.
- Close all new legacy task, create/edit/reactivation, shop and reward
  admissions, including delayed SQL shop callbacks. Durably record draining,
  complete accepted work through existing handlers, and retain exact unresolved
  entitlements with their known delivery state. Cover queued SQL, committed
  unpublished results, flat-file/login rewards and restored maintenance work.
  Never acknowledge a retained reward away or suppress an earned callback
  merely because Divine mode is enabled.
- Activate Divine mode only once admitted work is settled or durably retained
  for recovery. Recovery of old entitlements does not reopen new admissions.
  Disable old scan/restore side effects on both backends afterward. Preserve
  old durable job/command IDs as retired no-ops; append an ID only if needed.
  Preserve all old points/balances/history; no conversion or deletion.
- Add only required guarded, additive, re-runnable schema/codec changes.
  Keep old accepted payloads readable. Backout instructions stop admissions
  and reconcile receipts before changing code; no new rollback engine.

**Focused proof:** deterministic clock/RNG cases for slot/category limits,
hour boundaries, expiry, pause/restart/clock jumps and retry identity. Inject
cutover before admission, after commit and before delivery/acknowledgement;
verify old work is paid once or retained recoverably. Test restored jobs and
offline recipients. Use existing receipt fixtures for actual retained formats.

### 2. Safe candidates and bounded activity

**Overdue delivery focus:** prove a bounded usable candidate pool and reuse existing
observation points. Spend no scarce time on a world-wide audit or new framework.

- Use one cached validated catalogue for SQL and flat-file. Reuse bartender
  boot-profile, level-score and bounded distinct-candidate techniques; do not
  inherit item-reward requirements, minimum quest level, mapless exceptions or
  fallback logic. Runtime stone values own payout/group constraints. Supplement
  only missing candidate eligibility/access metadata; unknown values fail closed.
- Hard-exclude every runtime `ZONE_TOWN` before weighting, fallback,
  activation, persistence/display and award; hometown zero is not an exception.
  Reject removed/unloaded, unfinished, disconnected/inaccessible, staff,
  tutorial/safe-only, guildhall, locker/storage, transit/connector, Surface/
  Underdark map-only, no-NPC and trivially farmable targets. Heaven/Hell variants
  need positive ordinary access evidence for the relevant side. Review the
  actual bounded pool, not every world area. A map marker or file alone proves
  neither reachability nor completion. Revalidate dynamic flags/access.
- EXP needs appropriate normal NPC encounters. Epic selection also needs a real
  enabled payable stone, positive payout, completion/reset/replay eligibility,
  recommended level/group suitability and side reachability. `task_zone` alone
  is insufficient. Include actual eligible positive targets in both backends;
  when no valid candidate exists, choose another eligible category or leave empty.
- At existing gameplay input/movement/combat observation points maintain a
  rolling 60-minute per-account history. Count one current mortal representative
  per canonical account per side, active in the last 15 minutes, excluding
  AFK, link-dead and staff. Hosts, PIDs and telemetry identities are not accounts.
  An account cannot satisfy both opposing PvP populations. PvP needs distinct
  active opposing accounts with five minutes of meaningful play; increase its
  weight with at least two active accounts on each side. Login, keepalive,
  spam, force and idle automatic combat alone cannot qualify.
  Work independently of optional telemetry; cold boot/copyover warms from
  observed play without a new activity handoff format.
- Weight brackets 1-20, 21-35, 36-50, 51+ by actual per-side accounts, under-served
  brackets and realistic distinct-account group capacity; avoid one high-level
  outlier dominating a low-level group. These are selection, not entry rules.
  Category weights 35/30/15/20 are tunable suggestions, not quotas.
- No active same-side duplicate zone across EXP/epic categories. Good/Evil may
  deliberately share a safe contested zone. Prefer 12 hours without repeat
  after expiry; only that soft preference may relax for a thin safe pool.
- Choose real distinct source/destination ports from `ports[]`, commodity and
  market/access data; support both goods and prefer shared contested routes
  where feasible. Do not disclose ships or individual players. Effective
  runtime Good/Evil assignment controls side objectives; unaffiliated Neutral/
  Undead gets no fabricated PvE/PvP benefit but may use global trade boons.

**Focused proof:** all activity windows, account/alt exclusions, group/bracket
boundaries, duplicate/repeat rules and thin pools. Test every excluded area class,
especially town flag with hometown zero/nonzero and changed flags. Prove positive
side access for selected real content, not only rejection of synthetic bad zones.

### 3. Reward integration and flat-file stone payouts

**Overdue delivery focus:** make the required changes at the existing reward and save
boundaries. Avoid unrelated reward work so both backends can finish quickly.

- Derive each legitimate share first. Carry an explicit eligible base and
  calculate the Divine contribution separately from existing increases.
  Preserve non-benefit reductions and existing caps on the whole result.
  Keep percentage precision and round down once on final integer award;
  reject overflow. Make only the local arithmetic changes the affected paths
  need; unrelated reward families retain their current behavior.
- NPC EXP covers spell/melee damage, recursive tanking, healing, melee drip,
  kills and normalized `EXP_KILL_BONUS`. Preserve powerlevel/group/pet,
  safe/guild room, level/global accumulation and final one-third-level caps.
  For healing inspect the healed character's hostile opponent. Derive the
  unboosted tank share before adding the attacker's Divine increase.
  Require recipient and NPC encounter in the side's valid designated zone.
  Exclude PvP, quests/world quests, resurrection, death, old-boon and unrelated
  XP. With no other bonus, 100 becomes 200, never 300; with +20% existing,
  100 becomes 220. Trace rested, Nexus, epic, race/global/difficulty modifiers
  and remove premature truncation only in these eligible calculations.
  Immediate XP uses the normal player save, with no new per-hit I/O or receipt.
- Prepare zone +50% separately for each participant inside the existing stone
  batch before submit. Preserve actual group/stone maximum, alignment, errand,
  witch/Nexus/race/difficulty rules. The +10%/+50% example is 160 from base 100,
  not 165. Store prepared boon ID/time/base/final amount with stable award
  identity; retries never recompute against the current slot.
- Supply the currently missing flat-file zone-touch backend using the existing
  authority transaction. Claim the real stone, record completion/reset/alignment
  and prepared participants, and deliver each award durably once. Remove the
  flat-file refusal only after an actual selected stone can pay. Extend SQL
  recipient delivery at the same existing player-save boundary: a committed
  stone claim or process-local published flag is not proof of saved player credit.
- For new deferred Divine epic/PvP awards, commit the amount and applied marker
  with the recipient's existing status snapshot. Reuse writer ordering and
  checkpoint capture rather than introducing another scheduler/coordinator.
  Handle queued stale saves and offline recovery at that concrete boundary.
  A legitimate pre-expiry prepared award may pay once afterward; admission
  at/after expiry gets no boon. Preserve unrelated epic/artifact side effects.
- Qualify PvP at combat death from effective Good/Evil sides and a legitimate
  positive normal award, retaining arena, level, repeat-victim and fragWorthy
  gates. Carry victim/recipient qualification, boon ID and separated normal/
  Spill Blood components through the existing prepared combat outcome.
  Do not change broad `opposite_racewar()` semantics for unrelated callers.
- Use one PvP preparation calculation. Remove the unused `epic_frag()`
  wrapper/declaration once the caller search confirms it remains dead; do not
  revive a second production route. Unqualified generic `EPIC_PVP` awards get
  no boost. Spill Blood's separate 500 is outside the Divine base:
  100 normal + 500 task becomes 150 + 500 with other modifiers off.
  Same-side, unaffiliated and zero legitimate awards get no Divine increase.
  Version only payloads/records that actually gain prepared identity.

**Focused proof:** actual NPC reward callers, hostile-NPC healing, recursive
tanking, kill bonus, additive/fractional math, reductions, caps and overflow.
Run real stone and PvP preparation/publication with multiple/offline recipients.
Crash before/after commit, callback and player save; retry and reconnect must
neither lose nor duplicate prepared rewards. SQL and flat-file each select
and award a real payable reachable epic target.

### 4. Boon-specific cargo lots and settlement

**Overdue delivery focus:** keep recovery work confined to qualifying lots and affected
sales. This required work is a major time cost; avoid a general trade rewrite.

- Retain ordinary commodity slots; attach exact lots to stable persistent ship
  identity, not its process-local runtime reference. Qualifying purchases store
  lot/operation ID, timestamp, source, invoice/basis, quantity, purchaser account
  and boon ID. Durably establish paid purchase plus provenance together;
  unpaid/failed purchases cannot create eligible goods. Old ships/goods load
  unchanged with no fabricated provenance. This does not rewrite unrelated buys.
- Preserve separate lots inside merged slots: nine old plus one qualifying
  crate boosts one, not ten. Consume quantities/invoice basis deterministically
  on eligible partial sales and every relevant loss/clear/confiscation/jettison/
  sink mutation. Persist lots in affected ship capture/load/save signatures.
  When salvage or ownership/account transfer cannot authenticate lineage,
  invalidate eligibility and retain normal saleability; do not create a cargo
  transfer subsystem. Same-account proven handling cannot multiply quantity.
- Snapshot the first qualifying purchase's ship and full `SHIP_MAX_CARGO`
  capacity, including its then-current crew modifier, once per (account, boon).
  Combined normal cargo/contraband crate units count toward 3 x that fixed hold.
  Available free space, passenger capacity or later ship/crew changes do not
  reset/raise the cap. Keep actual purchase weight and contraband restrictions.
  Persist consumption across alts, sides, ships, relog and restart.
- Require purchase strictly after start at the selected source and sale
  admission before expiry at the distinct destination. Reject source=destination
  at selection and settlement. No bonus on pre-stocked, expired, unverifiable
  or laundered goods; excess-cap quantities still sell normally. Retire sold
  lot identities so sellback/rebuy and salvage cannot reuse purchase proof.
- Preserve base market prices, Nexus, diplomat/Seadog/warship effects, access
  and ordinary trade mechanics. Add +25% of qualifying base sale revenue
  separately from existing benefits, retain mandatory penalties, and round
  down once on final credit. With other modifiers off: cost 100, ordinary
  revenue 120, boon revenue 150, profit 50. Do not alter purchase prices.
- For sales containing boon lots, one receipt holds precise inventory/lot
  consumption, normal+bonus payment, market delta, account allowance and
  player/ship revisions. Commit payment/delivery marker, inventory, market
  and cap together: SQL transaction on the existing writer, flat-file atomic
  player/ship/market/cap after-images using existing authority machinery.
  Memory-only `ADD_MONEY` followed by separate saves is insufficient.
- Reserve only affected participants while that operation settles. Rejection
  before commit leaves all effects unchanged; after commit, publish/recover
  the stored result without reapplying a delta or reselling consumed goods.
  Coordinate normal queued saves so they cannot overwrite that outcome.
  Finish recovery before the affected wallet/cargo can be used again.
  Existing sell-slot/sell-all, achievements and crew behavior remain, with
  success effects emitted once from the same completed operation.
- Assess economy exposure using representative actual routes and hold sizes
  in bounded fixtures, not a new live balance study. Retain the approved rates.

**Focused proof:** both purchase/sale goods and normal pricing; 9+1 merging,
partial eligibility/cap, combined goods, larger second ship, alts and restart;
salvage/jettison/confiscation/transfer/clear, source loops and expiry.
Fault injection at receipt, inventory, player payment, market and cap boundaries
on both backends must prove quantity conservation, one payment and the fixed cap.
No second framework or unrelated ordinary-sale rewrite is required.

### 5. Commands, help and one integrated qualification

**Overdue delivery focus:** finish the required commands/help and reuse focused evidence
for one integrated journey per backend. No optional polish or extra test campaign.

- Keep `CMD_BOON=804`, `boon` and `boon list`. Show the exact requested Gods
  introduction, stored valid targets/rates, real remaining time and next hourly
  opportunity; handle initialization, pause and fewer than eight/zero slots.
  Preserve native `zone_table[].name` ANSI and `ports[].loc_name`, with existing
  ANSI-aware padding/wrapping in 80 visible columns. Good targets Evil, Evil
  targets Good; unaffiliated players see only applicable global trade events.
- Append a staff-only `divineboon` ID without renumbering commands. Implement
  status, pause, resume, replace, force and history via the same state mutation,
  existing authorization/audit conventions and idempotent operation identity.
  Force retries a due unconsumed opportunity; replace expires a slot and uses
  the next normal opportunity. Neither bypasses timing, caps or target safety.
  Old shop/edit admissions are unavailable; `toggle boon` explains automatic
  benefits and no longer affects them. Preserve its stored bit for backout.
- Update existing BOON help_index and consistent Boon/Divine Boons parsed topics,
  staff help and relevant Experience/Epic points/Frag/Ship/helpships references.
  Keep parser title/date format, ANSI policy and parsed-source precedence;
  verify collisions. Explain every rate, duration, shared slot rule, side/
  no-town rule, additive math, cargo provenance and combined account cap.
  Remove obsolete shop/toggle and +30% text. Validate importer dry-run and
  both help-serving backends; no production import.
- Extend the existing harnesses from the earlier steps and reuse their valid
  results. Run one combined legacy-cutover -> rotation -> all four rewards ->
  pause/expiry -> pre-expiry deferred payment -> restart/login journey per
  backend, including actual stone and route. Do not rerun every fault permutation
  again in the integrated journey or require a separate test campaign per PR.
- Build changed C/C++ with `make -C src`; qualify MariaDB and flat-file builds
  with `PERSISTENCE_BACKEND=mariadb` and `PERSISTENCE_BACKEND=flatfile`, isolated
  outputs or a clean backend switch. Keep outputs under `bin/` and uncommitted.
  Run affected tests only, required schema re-run/old payload checks and the
  issue's read-only `./scripts/format.sh --all --check`. Use changed-line
  formatting for touched code; report unrelated formatting failures separately.
- Reapply ablation to the final diff. Publish the eventual feature work with
  local evidence as each chunk becomes ready. Follow review requirements,
  without waiting on hosted CI. Keep cutover/backout operating notes concise.
  No production migration/import, restart, deployment or live balance claim.

## Requirement closure map

#245 remains open until all of these have implementation and executable proof.

**Completion is overdue:** use this map to keep limited resources and tokens
on required work, close each item once its proof is valid, and finish immediately
when the full map is satisfied. Do not add optional acceptance criteria.

The item numbers below refer to the 23 acceptance checkboxes in the issue
snapshot inspected on 2026-10-22; all 23 have a retained implementation path.

- **Slots/time/recovery (9, 13, 14):** step 1 state/receipts and fixed UTC schedule,
  eight global slots, one Cargo/one PvP, four/eight-hour expiry, skipped downtime,
  pause/resume, no rerolls/duplicate targets and soft 12-hour repeats.
- **Targets/population (5, 10, 11, 15, 16):** step 2 hard hometown and unsafe-area
  exclusions,
  per-side access, common SQL/flat-file epic catalogue, actual payable stones,
  60/15-minute activity, five-minute distinct-account PvP and all four brackets.
- **Rewards (6, 7, 17, 18, 19):** step 3 all NPC EXP contributors/kill bonus and
  cap; participant
  zone-epic preparation; qualified Good/Evil PvP; excluded 500 Spill Blood;
  precise additive math, rounding and prepared pre-expiry payment once.
- **Trade (2, 3, 4, 20):** step 4 both goods at +25% revenue, exact 9+1 provenance,
  all quantity mutations, fixed first-ship account cap, normal market constraints,
  no laundering/stockpile bonus, atomic payment/inventory/market/cap recovery.
- **Compatibility/retirement (1, 8, 12):** steps 1 and 5 no new legacy
  awards/purchases,
  preserved historic data and unresolved entitlements, restored-work safety,
  command 804, automatic benefits independent of old toggle and safe rollback.
- **User/staff/docs (21, 22):** step 5 native ANSI, 80-column output, real targets and
  accurate duration, side-correct objectives, safe audited controls, maintained
  help sources/See Also links and importer dry-run on both backends.
- **Delivery (23):** step 5 focused runtime/journey/schema tests, both builds,
  formatting checks, source-grounded content/economy assessment and honest
  separation between local qualification and production actions.

## Planning verification and limits

**Verification with very limited resources and tokens:** reuse valid evidence and
run only checks needed for the actual change. Keep required proof; avoid repeated
checks that add no new evidence and delay an already overdue delivery.

The following existing checks passed against the pinned checkout on 2026-10-22:

- `python3 tests/async/test_world_quest_dynamic_policy.py`
- `python3 tests/async/test_boon_reward_zone_transactional_cutover.py` (13 tests)
- `python3 tests/async/test_flatfile_boon_repository.py`
- `python3 tests/async/test_maintenance_scheduler.py`
- `python3 tests/async/test_ship_cargo_txn.py`
- `python3 tests/async/test_flatfile_cargo_market.py`
- `python3 tests/async/test_currency_transaction_contract.py` (9 tests)
- `python3 tests/async/test_epic_gain_runtime.py`
- `python3 tests/async/test_flatfile_authority_transaction.py` (ablation reuse check)

These characterize existing contracts only. They are not Divine acceptance,
proof of exactly-once recipient delivery, real target reachability, SQL feature
parity or live economy balance. The earlier planning pass performed no server
build, database application, help import, restart or gameplay mutation.
Current implementation evidence is recorded in the handoff above. Before each
publication, check references, preservation of prior plans, the focused diff,
`git diff --check` and remote commit parity. Link each PR to #245 and its stack.

## Estimate for Codex implementation

**Urgent delivery target:** resources and tokens are very limited, and the
deadline is already past due. Deliver fast. The range below is an estimate,
not time to fill.
Finish sooner whenever the required implementation and proof are complete.

**Plan for 6-10 hours of my active implementation and focused verification.**
Use about eight hours for scheduling. This is a source-informed estimate for
Codex working on the complete issue, not human-engineer days, a measured benchmark,
or a promise that work has started in the background.

Most time is in cargo lot/payment recovery and the missing flat-file epic payout
path. Rotation/selection, reward wiring and command/help work use the current
code and test harnesses. The estimate includes both required backend builds,
focused failure/restart cases and the final integrated journeys. It does not
include six PR/test cycles, a full regression burn-in, generalized persistence
repair, a rollback product, CI waiting or production operations.

This assumes the available C++/SQL tools and existing disposable MariaDB/file
fixtures are sufficient, and the bounded candidate pool can be proven from
checked-in content. The tools and fixture wrappers are present; no new environment
installation or production access is planned. If a concrete defect below these
boundaries blocks required proof, report it and revise remaining time from the
actual result. Do not reduce acceptance coverage to meet the estimate.

The earlier 96-144-hour figure was an uncalibrated human-effort guess and is
superseded. The estimate above includes uncertainty rather than deferring an
answer until implementation. The subsequent request now authorizes implementation.
