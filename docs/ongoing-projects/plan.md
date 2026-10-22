# Issue #245: rotating Divine Boons

Status: implementation plan only; no feature implementation or production action.
Prepared 2026-10-22 for [Duris #245](https://github.com/LuminariMUD/Duris/issues/245).
Implementation branch: `branch/issue-245-divine-boons`.
Source baseline: [master `e897b5214893`](https://github.com/LuminariMUD/Duris/commit/e897b5214893a66b75db5507be0a9be97b519cfc).
Issue specification inspected at its 2026-10-22 update, including all five comments.
The agreed follow-up decisions take precedence over older exploratory numbers.
The previous issue-59 plan is preserved byte-for-byte in
[plan-issue-59.md](plan-issue-59.md); earlier plans remain in their existing files.

This request authorizes this plan, its branch, commit, push and issue linkage.
The issue's design-only restriction does not prevent those requested actions.
Gameplay implementation, a feature PR, production migrations/imports, deployment,
restart and merge are separate actions. This document proposes their sequence;
it does not perform them.

## Outcome

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
command, real stone payout or recoverable sale. No gameplay implementation or
production action is part of this planning change.

## Implementation sequence

These are dependency steps within the same issue and branch, not six separately
qualified projects. Preserve every acceptance item in the closure map.

### 1. State, hourly rotation and forward legacy cutover

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
  local evidence once implementation is authorized. Follow review requirements,
  without waiting on hosted CI. Keep cutover/backout operating notes concise.
  No production migration/import, restart, deployment or live balance claim.

## Requirement closure map

#245 remains open until all of these have implementation and executable proof.

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
parity or live economy balance. This planning change performs no server build,
database application, help import, server restart or gameplay mutation.
Before publication, check document/source references, preservation of the prior
plan, a documentation-only diff, `git diff --check`, remote commit parity and
native GitHub issue-to-branch linkage.

## Estimate for Codex implementation

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
answer until implementation. Implementation remains a separate requested action.
