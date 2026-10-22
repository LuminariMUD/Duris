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

**Keep:** each outcome above; eight durable slots; a small validated candidate
catalogue; bounded account activity; prepared reward identity; cargo batches,
cap and settlement receipts; an explicit legacy transition; both backends;
focused tests of actual commands, rewards and recovery. Removing any of these
would leave an explicit acceptance requirement or a traced failure unhandled.

**Simplify:** use the current writer/coordinator, maintenance dispatch, atomic
flat-file after-image transaction, player status saves, bartender cached profile
techniques and native ANSI utilities. Keep policy in one small Divine module
with persistence code following existing repository boundaries. Share only
qualification or arithmetic that has actual reward callers. Consolidate the
unused PvP wrapper rather than preserving two calculations.

**Drop:** a new scheduler, external service, PostHog dependency, generic
reward/quest framework, universal economy rewrite, new gameplay currencies,
legacy point conversion, eight slots per side, rigid category quotas, immediate
refill, catch-up bursts, alternate zone-name colouring, individual player/ship
tracking displays, and broad unrelated cleanup. No feature implementation,
source formatting, database writes or server operation belongs to this planning
commit. Do not expand the task into a full burn-in or require hosted CI waits.

**Files:** implementation is expected to touch `src/economy/boon*`,
`src/economy/currency_transaction*` only for the concrete durable-sale boundary,
`src/world/limits.c`, `src/world/epic*`, `src/world/zone_touch*`,
`src/combat/fight.c` and `combat_outcome*`, `src/ships/ship_shop.c`,
`ship_utils.c`, `ship_base.c`, `ships.h`, the relevant flat-file ship/player
and SQL player snapshot repositories, maintenance dispatch/replay, boot/login/
copyover integration, interpreter/toggle registration, help, and focused tests.
Add `src/economy/divine_boon.{h,c}` and its backend repository/codec files only
where the existing boundaries need them; a command-only source file is optional.
A reviewed common candidate manifest, additive migrations and concise operating
instructions are necessary content/persistence changes, not a new platform.
Touch bartender or activity code only to expose proven reusable facts.

**Proof:** deterministic policy tests plus executable reward, settlement and
restart journeys in disposable MariaDB and flat-file environments. Source-string
assertions and codec tests supplement those journeys; they cannot replace them.

## Implementation sequence

Each numbered unit is a reviewable implementation change with its own focused
tests. Land prerequisites before consumers; stack only where changes actually
depend on each other. The feature remains unavailable until its required
persistence, cutover and reward paths are ready. This is one work item, #245;
the units below are not separate optional deliverables.

### 1. Durable state, award delivery and legacy transition

- Persist a versioned Divine state containing mode, pause state, revision,
  last consumed UTC opportunity, slots with stable IDs/category/rate/timestamps,
  Good/Evil zone or route objectives, and recent expired-zone history.
  Boon identity is distinct from reusable display slot number.
- Use the existing single writer and critical-operation identities for state
  transitions. Commit an opportunity and its selected result, including an
  empty result, together. Publish the cache only after durable acceptance.
  SQL uses unique operation/opportunity keys; flat-file uses its existing
  checksummed, locked after-image transaction. Corruption or unknown schema
  must disable new Divine admissions without guessing targets or deleting data.
- Add only the concrete recipient receipt/checkpoint fields needed for
  recoverable awards. An applied marker and its wallet/epic/player-state effect
  must share a durable transaction/checkpoint. Publication from that checkpoint
  must not overwrite newer live changes; serialize the affected player's reward
  delivery/save sequence and prevent a stale queued save from reversing it.
  Do not replay a delta just because a receipt lacks a message-delivered flag.
- Use explicit durable modes: legacy -> draining -> Divine. Entering draining
  closes new legacy completion, creation/edit/reactivation and shop admissions,
  including SQL reads/callbacks already scheduled to admit a purchase.
  Inventory accepted work, SQL writer requests, critical inbox/outbox entries,
  flat-file pending/login rewards, scheduler requests/results and nested
  cash/epic/stat/level/affect effects. Complete accepted operations with stable
  child identities or preserve their exact unresolved entitlements durably.
- Keep recovery of pre-transition entitlements separate from admission of new
  legacy work. Do not mark an unresolved reward delivered merely because its
  gameplay callback was disabled. Switch only after every accepted operation
  is either settled or explicitly retained for recipient recovery. Boot must
  resume a partially completed drain without reopening admissions.
- Disable future `boon_scan` work on both backends in Divine mode. Preserve
  durable enum IDs; retire the old job as a safe no-op after its old work is
  reconciled. Do not reinterpret an old saved request as a Divine rotation.
  Append a new job ID only if the existing dispatch actually needs one.
- Keep all old points, balances, definitions and history. Rollback stops new
  Divine admissions and reconciles receipts before re-enabling legacy mode;
  it neither deletes Divine receipts nor replays old completions. Document
  that rollback must use code that understands the new receipts.
- Prepare additive, guarded, re-runnable SQL changes and matching flat-file
  versions/read compatibility. Apply only to disposable local fixtures during
  implementation. No production migration or rollback operation is authorized.

**Proof:** inject failure before/after preparation, commit, publication,
player save and acknowledgement; restart and reconnect. Each accepted legacy
reward is delivered once or remains recoverable. Test shop callbacks already
queued at the boundary, offline recipients, restored scans and repeated drains.
Run old receipt/codec fixtures unchanged where backward compatibility requires it.

### 2. Common candidates, account activity and rotation

- Build one validated runtime candidate catalogue for both backends. Use loaded
  runtime zone ownership/flags, mob profiles and actual stone/reset definitions
  as facts. Use a small reviewed common manifest for zone/stone IDs, positive
  ordinary entry evidence per side, recommended level/group and completion
  constraints that boot data does not express reliably. Stone values remain
  authoritative for actual payout/group gates; validate rather than invent
  metadata. Cross-check SQL rows where present; do not let a missing SQL-only
  field become a permissive flat-file default.
- Explicitly reject every `ZONE_TOWN`, including hometown zero, before scoring,
  fallback, activation, display and reward admission. Also reject unloaded,
  removed, disconnected, unfinished, staff-only, safe/tutorial-only,
  guildhall/locker/storage, connector/transit-only, Surface/Underdark map-only
  and unsuitable no-NPC/trivial targets. Heaven/Hell variants require positive
  ordinary access evidence for that side. Neither a map marker nor a numeric
  zone range proves reachability. Review a bounded safe pool rather than
  building a generic world reachability service.
- For EXP, validate suitable naturally available NPCs and relevant-side access.
  For epic zones, also validate a real enabled stone, positive payable amount,
  group-size suitability, normal reachability, completion/replay restrictions
  and current completion/reset state. `task_zone` is not sufficient evidence.
  Include real source-backed positive examples, not just exclusion fixtures.
  Revalidate dynamic completion, flags and access before activation and awards.
- Reuse bartender boot profiles, weighted selection and finite traversal
  techniques where they fit. Do not inherit its item-reward requirements,
  bartender minimum-level restrictions, mapless exceptions or final fallback
  without checking them against Divine rules.
- Keep a bounded rolling 60-minute account history in memory, driven by actual
  gameplay evidence at existing input/movement/combat hooks. Count only mortals
  currently connected, not AFK/link-dead, with gameplay in the last 15 minutes.
  Use canonical actual account identity, not host, character PID or telemetry
  pseudonym. Deduplicate one representative per account per side. An account
  appearing on both sides cannot serve as two opposing accounts for PvP.
  Telemetry disabled/full/unavailable must not change this gameplay accounting.
- For PvP selection require distinct active accounts on opposing sides and at
  least five accumulated minutes of meaningful play in the 60-minute window.
  Weight upward with at least two accounts on each side. Login, keepalive,
  status-command spam, forced commands and idle automatic combat cannot create
  eligibility on their own. Do not invent pre-reboot activity; cold boot
  warms from observed play. Copyover may preserve bounded verified history.
- Select within brackets 1-20, 21-35, 36-50 and 51+, weighted by current per-side
  accounts and under-served brackets. Group suitability uses available distinct
  active accounts, not raw descriptors or an imaginary full group. Cap target
  difficulty to realistic group size and prevent one high-level character from
  dominating a low-level population. These are selection bands, not entry gates.
- EXP 35 / epic 30 / cargo 15 / PvP 20 are initial weights only. Apply category
  availability and the single-Cargo/single-PvP caps first. Reject duplicate
  currently active zones for the same side across EXP and epic categories.
  Allow a safe shared Good/Evil zone for contested play. Prefer 12 hours without
  repeat after expiry; relax only that soft preference if the safe pool is thin.
- Choose real distinct source/destination ports and commodities from `ports[]`
  and current trade conditions. Validate both cargo and contraband availability,
  access and a usable route; prefer shared contested routes when feasible.
  Show port objectives, never current ships or individual players.
  Unaffiliated Neutral/Undead characters get no invented side targets or PvE/PvP
  benefit; a legitimate runtime Good/Evil assignment follows that effective side.
  Unaffiliated characters may use the global trade event normally.
- Use UTC epoch-hour identities and absolute timestamps. First activation is
  the next scheduled hour after cutover, not eight slots at boot. A live
  opportunity creates at most one slot, starting at its fixed boundary, with
  eight/four-hour expiry. Expiry is checked by every display/bonus query as
  well as maintenance; scheduler delay cannot extend a boon.
- On boot expire overdue slots, consume/skip every missed boundary without
  backfill, and resume at the next scheduled hour. Pause skips spawning but
  preserves natural expiry and consumes opportunities. Resume waits for the
  next hour. Retries reuse the stored choice and timestamps; they cannot reroll.
  Handle UTC rollback by refusing to revisit consumed hours, and forward
  jumps by skipping elapsed opportunities. Persist expiry/repeat history.

**Proof:** fixed clock and fixed RNG tests for all timing, pause, clock-jump,
restart, idempotent-empty-result, slot and side invariants. Test all activity
thresholds and bracket boundaries, alts/cross-side accounts, insufficient groups,
low-population cold start, thin safe pools, cross-category duplicates and soft
repeats. Explicitly test hometown zero/nonzero, flag changes and every excluded
area class; include a genuine eligible target for each implemented category.

### 3. EXP, zone epic and PvP reward consumers

- Establish explicit local `base`, existing-modified amount and Divine
  contribution in each eligible reward family. Preserve structural share,
  level/group/stone rules and non-benefit reductions; Divine cannot undo them.
  Keep precision through percentage arithmetic and round down once at the final
  integer award, then enforce the existing final caps/overflow rules.
  New benefit = eligible base x Divine rate; add it to the existing benefit
  calculation rather than scaling that calculation. Preserve existing behavior
  for rewards outside Divine scope. Do not rewrite all reward math globally.
- EXP: support NPC-derived spell/melee damage, tanking, healing, melee drip,
  kill and normalized kill-bonus awards. Derive the unboosted tank share before
  adding the attacker's Divine contribution. For healing, inspect the healed
  character's hostile opponent. Require the recipient and qualifying NPC
  encounter to be inside that side's designated valid zone. Exclude pets or
  other targets already excluded by normal XP, and all PvP, quest/world-quest,
  resurrection, death, legacy-boon and unrelated XP.
  Retain powerleveling, safe/guild room, level/global accumulation and final
  one-third-level caps. The immediate EXP mutation has no separate replay;
  save its result through the normal player path, without per-hit I/O.
- Define the original eligible base at share derivation before benefit
  multipliers, carrying existing reductions through the whole calculation.
  Trace rested, global/race, Nexus, epic and difficulty modifiers explicitly;
  remove premature integer conversions only where needed for these eligible
  calculations. Verify 100 + 20% existing + 100% Divine = 220 and base 100 with
  no other benefit = 200, never 300. Damage's recursive tank call must not
  inherit the attacker's bonus or apply a second bonus.
- Zone epics: prepare each participant's +50% within the existing stone touch
  batch, before `zone_touch_transaction_submit()`. Keep actual group payout,
  alignment, completion/errand constraints, witch/Nexus/race/difficulty effects,
  stone caps and participant-specific eligibility. Separate eligible base
  from existing benefits so 100 + 10% + 50% = 160, not 165. Persist boon ID,
  prepared time/base/bonus/final amount and stable child award identity.
- Add the missing flat-file stone-touch repository/dispatch path using existing
  locked multi-file authority transactions. Persist claim, zone completion,
  prepared participant awards and recipient delivery status, and integrate
  boot/login recovery. Reconstruct completion/reset/alignment state needed by
  that path. Only remove the existing flat-file refusal after atomic recovery
  is proven; a selected target that can never pay is not acceptance.
- Make SQL stone publication equally recoverable at the player-save boundary.
  Test a claim committed before callback and a callback before player save.
  Recover a legitimate unpaid participant once; do not treat
  `recovered_claim` as proof that every player's balance was saved.
- PvP: qualify at combat death with effective Good/Evil victim/recipient sides,
  positive legitimate normal award, arena/level/recent-frag/fragWorthy gates.
  Keep general `opposite_racewar()` unchanged for its unrelated combat callers.
  Carry qualifying sides, boon ID, prepared time and separated normal/Spill
  Blood values in the existing combat outcome.
- Use one PvP preparation calculation for existing modifiers plus the Divine
  contribution. Remove the unreferenced `epic_frag()` declaration/wrapper
  after verifying the final caller graph; do not resurrect it as another
  award route. Generic `gain_epic(EPIC_PVP)` without qualified combat context
  gets no Divine benefit. Thus both historical calculation paths are resolved
  through consolidation rather than left with inconsistent mathematics.
  Spill Blood's separate 500 is excluded from the Divine base:
  normal 100 plus task 500 yields 150 + 500 with other modifiers off.
  Same-side, unaffiliated or zero-legitimate-award cases get no bonus.
- Version affected command/result payloads compatibly and persist prepared
  amounts. A legitimate operation prepared before expiry may complete once
  afterward; an operation admitted at/after expiry gets no boost. Replay never
  consults the then-current slot. Add only required delivery/save coordination
  for these rewards, retaining existing unrelated epic/artifact side effects.

**Proof:** run actual reward callers, not just a percentage helper. Cover every
XP type, hostile-NPC healer context, shared tank derivation, reductions, stacked
bonuses, fractional rounding, overflow and caps. Exercise real stone touch and
combat outcome paths in both backends, multiple/offline recipients, duplicate
callback, ambiguous commit, reconnect and restart before/after player save.
SQL and flat-file must select a real payable epic target and actually award it.

### 4. Cargo provenance, account cap and atomic settlement

- Keep ordinary commodity slots and normal market/access rules; add exact
  purchase lots associated with stable ship identity and commodity/slot.
  Record operation/lot ID, source, purchase timestamp, invoice/cost basis,
  quantity, canonical purchaser account and matching boon ID. Purchases must
  durably debit their payer and establish provenance together; a failed or
  unpaid purchase cannot mint eligible cargo. Older ships load with existing
  cargo intact and no fabricated Divine provenance.
- Persist multiple lots per merged slot. Nine old crates plus one qualifying
  crate grants only one crate's bonus. Track partial eligible sales, jettison,
  loss/confiscation, slot clearing, ship ownership/transfer, sinking, salvage,
  ship save/load and copyover. Consume lots deterministically without duplicating
  quantity or losing invoice allocation. Include provenance in save signatures,
  SQL capture/load and versioned flat-file capture/materialization.
- Use the issue's permitted simpler salvage/transfer rule: invalidate Divine
  eligibility when normal crate/ownership transfer cannot preserve authenticated
  purchase/account lineage. Goods remain saleable normally. Never relabel
  salvage or another account's goods as a new qualifying purchase; direct
  same-account operations that retain proof must not multiply quantity.
  Destructive quantity mutations must atomically retire matching provenance.
- For each (canonical account, boon ID), persist the first qualifying purchase's
  ship and fixed full hold capacity. Use `SHIP_MAX_CARGO`'s combined crate
  units (including the snapshotted crew capacity), not remaining free hold,
  `get_capacity()` passenger count, per-character or current-ship capacity.
  Both cargo and contraband use this same three-times-capacity allowance;
  weight availability and contraband restrictions still limit each purchase.
  Snapshot once, even before any sale, and never increase it after ship/crew,
  character, side, account session or restart changes.
- A qualifying lot was purchased strictly after that boon starts at the
  selected source, with paid and verifiable basis, and admitted for sale before
  expiry at its distinct destination. Reject source=destination in selection
  and settlement. Unproven/prestocked/out-of-period goods get ordinary revenue.
  Apply a reduced eligible quantity when only part of the shared cap remains.
  Retire settled lot identities permanently so sellback, rebuy, salvage and
  transfer cannot recycle a single purchase into several capped claims.
- Preserve `cargo_buy_price()`/`contra_buy_price()` and existing Nexus,
  diplomat, Seadog, warship, contraband access and market effects. Compute a
  separate +25% of eligible market sale revenue before those optional reward
  modifiers, with mandatory penalties/constraints retained. Do not add the
  Divine component to purchase prices or multiply the Nexus-adjusted total.
  Record all components and round the final integer credit down once.
  Required no-other-modifier example: cost 100, normal revenue 120,
  Divine revenue 150, profit 50.
- Introduce one concrete sale receipt per operation containing exact lot
  consumption, normal and Divine credit, account allowance before/after,
  ship and player revisions and market delta. For SQL, commit authoritative
  inventory/provenance, market mutation, cap and player payment/delivery marker
  under one transaction/serialized operation. For flat-file, commit the
  equivalent player/ship/market/cap/receipt after-images together using
  `flatfile_authority_transaction`. Existing memory-only `ADD_MONEY` and
  three separate save calls cannot be the settlement guarantee.
- Reserve only the affected ship/account/recipient while a prepared sale is
  outstanding. Prevent stale writer/player/ship snapshots from overwriting the
  settlement. Before durable commit, rejection leaves cargo, money, market
  and cap unchanged; after commit, recovery publishes the exact outcome and
  never resells the old inventory or credits a second delta. Offline recovery
  completes before those goods or wallet funds can be used again.
- Keep normal sell-all and sell-slot commands and their achievement/crew
  behavior. Publish success and resulting side effects after settlement.
  Make secondary achievement/crew effects idempotent with that receipt.
  Measure approved-rate returns on actual reviewed routes and ship capacities;
  report economy exposure without silently changing 25% or three holds.

**Proof:** executable purchases and both sale commands; old/new merged lots,
partial eligible quantities and remaining cap, mixed cargo/contraband, larger
second ship, alts/accounts, relog/restart, confiscation/jettison/salvage/transfer,
source sellback and expired/untraceable goods. Inject failure at receipt,
inventory, wallet/player checkpoint, market and cap boundaries on both backends;
verify conservation, no duplicate credit and exactly the approved cap.
Test normal pricing/Nexus/penalties and non-qualifying sales unchanged.

### 5. Player/staff commands, help and operating notes

- Keep command 804 and replace its dispatch with Divine display after cutover;
  no mortal legacy shop/edit path remains. `boon` and `boon list` show:
  "The Gods of Duris have given you and your allies the following boons:"
  then actual stored eligible targets, rates, remaining real time and the next
  UTC opportunity. Handle initializing, paused, empty and partial lists cleanly.
- Render native `zone_table[].name` colour sequences unchanged and use
  `ports[].loc_name` for routes. Reuse `pad_ansi()` and existing ANSI-aware
  wrapping utilities; wrap long objectives without splitting colour escapes.
  Verify visible widths in an 80-column terminal and actual Good/Evil PvP
  objective wording. Show unaffiliated players only applicable global events.
- Append one safely allocated staff-only `divineboon` command ID without
  renumbering existing IDs. Provide `status|pause|resume|replace <slot>|force|history`
  with existing staff authorization/audit conventions and durable operation IDs.
  `force` retries a currently due, unconsumed opportunity; it does not add an
  extra hourly roll. `replace` expires the selected slot and requests a future
  normal opportunity, preserving caps and timestamps. Repeated admin requests
  must be idempotent, and no staff control may activate an invalid town target.
- Remove the participation effect of `toggle boon` for Divine mode and explain
  automatic benefits. Preserve the old stored preference for rollback.
  Remove obsolete shop/toggle wording from the toggle summary and help.
- Update existing `BOON` help_index plus consistent two-line/title/date
  `Boon` and `Divine Boons` parsed topics, and staff-only administration help.
  Check case-insensitive collisions and parsed-source precedence. Update the
  relevant Experience, Epic points, Frag, Ship and `helpships` references.
  Document all rates, durations, eight shared slots, hourly empty slots,
  additive examples, no-town rule, effective sides, provenance and combined
  three-hold account cap. No +30% cargo text or legacy shop instructions remain.
- Follow HELP_STYLE_GUIDE.md. Validate importer dry-run and both serving
  backends; do not run a production import. Add concise cutover/status/recovery
  and rollback instructions with production application kept separate.

**Proof:** actual interpreter dispatch, legacy command denial and staff privilege
tests; ANSI-visible-width and native-colour fixtures for real/multicolour/long
names, both sides and unaffiliated viewers; repeated admin operations; help
parsing, collision, search and SQL/flat-file serving parity.

### 6. Integrated acceptance and delivery

- Extend the existing harnesses and executable journeys before adding new
  focused files. Add a small Divine model/clock test and durable-sale/recipient
  failure cases only where current tests cannot prove these new requirements.
  Do not start a general test framework or repeat green unrelated suites.
- In disposable fixtures on both backends, take the real path through legacy
  admission drain, Divine activation, hourly selection, all four reward types,
  pause/expiry, pre-expiry prepared payment after expiry, restart and login.
  Include an actual world epic stone and cargo route, not fabricated catalogue
  entries or codec-only round trips.
- Build changed C/C++ with `make -C src`; qualify both
  `PERSISTENCE_BACKEND=mariadb` and `PERSISTENCE_BACKEND=flatfile` with isolated
  build outputs/appropriate clean rebuild between backend macro changes.
  The maintained executable is `bin/server/dms_new`; generated outputs stay
  under `bin/` and are never committed. The issue also requests the read-only
  `./scripts/format.sh --all --check`. Use changed-line formatting for touched
  implementation code and report unrelated formatting failures separately.
- Run the affected boon/zone, EXP/epic/PvP, ship/market, scheduler, help and
  persistence/restart tests. Additive schema changes must be re-runnable and
  tested for upgrade, replay and old payload reads in isolated databases/files.
  A production data audit or live balance result remains unverified until a
  separately authorized environment exercise.
- Review every retained change with the ablation test again. Publish focused
  implementation PRs linked to #245 once implementation is authorized, with
  exact local evidence and any limitations. Review requirements still apply;
  hosted CI completion is not a merge gate under AGENTS.md. Production
  application/import, restart and activation remain separate owner actions.

## Requirement closure map

#245 remains open until all of these have implementation and executable proof:

- **Slots/time/recovery:** unit 1 state and receipts; unit 2 fixed UTC schedule,
  eight global slots, one Cargo/one PvP, four/eight-hour expiry, skipped downtime,
  pause/resume, no rerolls/duplicate targets and soft 12-hour repeats.
- **Targets/population:** unit 2 hard hometown and unsafe-area exclusions,
  per-side access, common SQL/flat-file epic catalogue, actual payable stones,
  60/15-minute activity, five-minute distinct-account PvP and all four brackets.
- **Rewards:** unit 3 all NPC EXP contributors/kill bonus and cap; participant
  zone-epic preparation; qualified Good/Evil PvP; excluded 500 Spill Blood;
  precise additive math, rounding and prepared pre-expiry payment once.
- **Trade:** unit 4 both goods at +25% revenue, exact 9+1 provenance,
  all quantity mutations, fixed first-ship account cap, normal market constraints,
  no laundering/stockpile bonus, atomic payment/inventory/market/cap recovery.
- **Compatibility/retirement:** units 1 and 5 no new legacy awards/purchases,
  preserved historic data and unresolved entitlements, restored-work safety,
  command 804, automatic benefits independent of old toggle and safe rollback.
- **User/staff/docs:** unit 5 native ANSI, 80-column output, real targets and
  accurate duration, side-correct objectives, safe audited controls, maintained
  help sources/See Also links and importer dry-run on both backends.
- **Delivery:** unit 6 focused runtime/journey/schema tests, both builds,
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

These characterize existing contracts only. They are not Divine acceptance,
proof of exactly-once recipient delivery, real target reachability, SQL feature
parity or live economy balance. This planning change performs no server build,
database application, help import, server restart or gameplay mutation.
Before publication, check document/source references, preservation of the prior
plan, a documentation-only diff, `git diff --check`, remote commit parity and
native GitHub issue-to-branch linkage.

## Implementation estimate

**The initial 96-144-hour human-effort estimate is withdrawn as a delivery ETA.**
The per-unit ranges were judgment calls, not timings measured in this checkout.
They do not establish how long Codex implementation would take, and there is no
evidence from this planning pass that the user must wait 96 hours.

The useful forecast is the dependency order and where uncertainty sits:
cargo provenance/atomic payment and recipient-save recovery dominate the work;
flat-file stone-touch support is another necessary dependency. Command display,
the eight-slot policy and help are comparatively small. Existing writer and
after-image primitives should be reused, with focused tests rather than broad
qualification added to each unit.

A numerical Codex wall-clock estimate is not yet calibrated. Implementation is
expected to span multiple focused work sessions, but this read-only source review
cannot substantiate a reliable hour range. Record actual elapsed implementation
and verification time for the first prerequisite unit, then forecast remaining
work from that evidence. Do not run implementation merely to calibrate this
planning task, silently reduce the issue's requirements, or substitute another
unsupported precise ETA. Review turnaround and separately authorized production
actions are outside implementation time.
