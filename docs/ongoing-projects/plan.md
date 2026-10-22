# Issue #245: rotating Divine Boons

> **Delivery contract: six hours TOTAL, never six more hours.**
> Preserve the entire agreed outcome. Do not reset the clock, expand the budget,
> hide a missed deadline behind progress, or call partial implementation done.
> A forecast outside the remaining budget is a delivery failure to disclose
> immediately, not permission to continue spending time.

Status: incomplete and inactive; implementation paused by the user's explicit stop.
Revised 2026-10-22 for [Duris #245](https://github.com/LuminariMUD/Duris/issues/245).
Authoritative plan branch: `branch/issue-245-divine-boons`.
Source baseline: [master `e897b5214893`](https://github.com/LuminariMUD/Duris/commit/e897b5214893a66b75db5507be0a9be97b519cfc).
Issue specification inspected at its 2026-10-22 update, including all five comments.
The agreed follow-up decisions take precedence over older exploratory numbers.
The previous issue-59 plan is preserved byte-for-byte in
[plan-issue-59.md](plan-issue-59.md); earlier plans remain in their existing files.

This request repairs the plan. It does not restart the paused implementation or
grant another time budget. Prior implementation authorized focused code/tests
and review-ready commits, pushes and PRs; the subsequent explicit pause is
preserved. Production migrations/imports, deployment, restart and merge remain
separate actions. The owner already reported the deadline overdue: do not label
this delivery on track.

## Fixed budget and failure rules

1. **One clock for the whole outcome.** The budget is 360 elapsed minutes from
   the original agreed start, including discovery, implementation, builds,
   tests, fixes, documentation, Git/PR work and reporting. Active work may be
   tracked separately; it cannot replace elapsed delivery time. New turns,
   resumed goals, branches, PRs, agents, context compaction and revised plans
   reset neither spent time nor the deadline. Waiting and handoffs count. An
   explicit user pause stops work; it does not automatically move the deadline.
2. **Record facts before spending more time.** Keep original start, absolute
   deadline with timezone, elapsed time, remaining budget and next proof in the
   handoff. Read the actual clock at each work boundary and before long commands.
   If the original timestamp is unavailable, label it unknown and use the
   earliest evidenced start as a conservative bound, never a fresh start.
   Tokens and PR counts do not measure remaining delivery time.
3. **Budget is not an estimate.** Forecast ALL unfinished behavior, affected
   tests, required builds and publication using measured durations where
   available. Label unmeasured work uncertain. Required work of unknown cost
   cannot support an on-track claim. Do not quote a new full-project estimate
   as remaining time or turn the six-hour limit into an eight-hour schedule.
4. **Disclose failure early.** Immediately report when required work cannot fit,
   a checkpoint below is missed, or evidence invalidates the forecast. State
   elapsed time, remaining budget, missing acceptance items, concrete cause and
   smallest recovery option without waiting for an ETA question. A report does
   not grant an extension. Record a budget checkpoint at least every 30 elapsed
   minutes; keep routine progress brief and tied to completed behavior/proof.
5. **No unilateral extension or scope reduction.** Remove optional work and
   duplicate verification first. If the complete required outcome still cannot
   fit, stop new implementation, preserve the checkpoint and request only the
   consequential time/scope decision. Only explicit user approval changes that
   contract. Silence, frustration, "go faster" and an ordinary resume do not
   authorize extra hours or omitted requirements. Resume continues the recorded
   balance. Keep the original budget and miss visible after any approved change.
6. **The deadline is a stop boundary.** Do not start commands that cannot finish
   within the allowance; bound long commands by remaining time and safe cleanup
   needs. At the deadline stop this task's work/processes safely, preserve the
   diff/evidence and report complete delivery or an explicit missed delivery
   with blockers. No unattended continuation, new PR cycle or "nearly finished"
   extension. Reserve cleanup/report time inside the budget.
7. **Completion means the whole issue.** All 23 acceptance items need executable
   proof, both backends, commands/help and review-ready published code. A
   foundation PR, passing helper test or inactive subset is partial work. Keep
   #245 open until complete. Report qualification and publication separately
   from merge/production. A deadline never excuses missing safety/recovery proof.

These rules prohibit silent overruns; they cannot guarantee unknown work fits.
If feasibility fails, say so early instead of making another unsupported promise.

### Checkpoints inside the original six hours

These are maximum elapsed thresholds to detect a failed commitment, not fresh
allocations or predicted task durations. Finish earlier when possible. Missed
checkpoints cannot be restarted now; they count as missed.

- **By 00:30:** confirm scope, reuse and fixtures. Trace cargo settlement and
  flat-file stone payout first. Forecast ALL remaining slices and final proof.
  If they cannot fit 360 minutes, disclose failure before building layers.
- **By 01:30:** execute representative purchase -> sale -> save/retry and
  selected stone -> recipient save/reload paths on both backends at production
  boundaries. These are narrow feasibility proofs, not full acceptance. Expose
  missing atomicity/content before optional architecture or foundation-only PRs.
- **By 03:00:** all four reward families have reachable vertical paths; cutover,
  selection and display connect in isolated fixtures. Remaining work is named
  acceptance gaps, not an undiscovered backend or reward subsystem.
- **By 04:00:** required implementation/help exist and focused checks pass.
  Reserve the last two hours for integrated journeys, both builds, required
  review corrections and publication. No new infrastructure or optional work.
- **By 05:00:** integrated journeys and final checks pass on both backends;
  review-ready changes/evidence are prepared. The last hour is contingency for
  concrete failures and delivery, not another feature phase.
- **By 06:00:** publish the complete qualified result and report it, or report
  missed delivery and stop. Never substitute another remaining-time range.

## Implementation handoff (2026-10-22)

- **Clock evidence:** implementation started at 12:30:26 Asia/Jerusalem
  (09:30:26 UTC); the paused checkpoint was recorded at 17:17:38 (14:17:38 UTC):
  4h 47m 12s for that interval alone. Earlier planning began at 11:41:02
  (08:41:02 UTC), the earliest verified start for the combined job. Its six-hour
  outer bound is **17:41:02 Asia/Jerusalem (14:41:02 UTC)**. This is NOT a
  replacement for the owner's already-overdue deadline; the exact earlier
  promise timestamp is unverified. Planning, waiting and this repair count.
  No additional implementation time or reliable on-time forecast is established.
- **Read this branch's current plan before continuing an older stack copy.**
  Preserve the paused work and spent-time record. A resumed goal does not
  restore an old estimate or grant a new six-hour window.
- **Published partial work:** [#265](https://github.com/LuminariMUD/Duris/pull/265)
  state, [#266](https://github.com/LuminariMUD/Duris/pull/266) persistence,
  [#267](https://github.com/LuminariMUD/Duris/pull/267) writer/boot,
  [#268](https://github.com/LuminariMUD/Duris/pull/268) legacy admission barriers,
  [#269](https://github.com/LuminariMUD/Duris/pull/269) activity,
  [#270](https://github.com/LuminariMUD/Duris/pull/270) delivery watermark,
  [#271](https://github.com/LuminariMUD/Duris/pull/271) EXP candidates,
  [#272](https://github.com/LuminariMUD/Duris/pull/272) EXP/hourly integration,
  [#275](https://github.com/LuminariMUD/Duris/pull/275) prepared PvP delivery.
  These prove bounded components, not nine completed feature slices.
- **Latest published implementation:** `branch/issue-245-divine-pvp` at
  `4ecad7a9b578a497eeec31c8e2fe29ac963ac6c9`, implementation `7b3407016`.
  The plan branch contains only the earlier foundation. Do not confuse its
  source tree with the latest implementation or rebuild completed components.
- **Paused dirty worktree:** `/home/aiwithapex/projects/duris-issue245-plan`,
  branch `branch/issue-245-divine-receipts`. Its uncommitted plan records detailed
  evidence and receipt work in `flatfile_player_domain_repository.{c,h}`,
  `flatfile_player_repository.c` and their two existing harnesses. Preserve all
  six modified files. Receipt changes are not published or finally reviewed.
  This plan repair uses a separate worktree and must not overwrite that work.
- **Confirmed remaining work:** `zone_touch_transaction_submit` still refuses
  flat-file mode; `divine_boon_select` selects only EXP/PvP; `CMD_BOON=804` still
  dispatches `do_boon`; cargo credits `ADD_MONEY` separately from ship/market
  saves. Epic candidates/payouts, trade lots/cap/settlement, legacy reconciliation/
  activation, commands/help and final loaded-world journeys remain. This is
  substantial unfinished implementation, not just final verification.
- **Evidence:** reuse results against the relevant unchanged code. The paused
  handoff records both receipt harnesses and both incremental builds passing;
  that is prior evidence, not checks rerun by this plan repair. Existing PRs
  retain their detailed checks. Use installed LLVM 22 for later C++ commits
  (`CLANG_TIDY=/home/aiwithapex/.local/bin/clang-tidy`).
- **Next, only if resumed:** assess ALL remaining cost against the unreset
  budget first. Finish the bounded receipt fix only if that gate permits work;
  then prove cargo and stone gaps before more supporting layers. An older
  "next foundation PR" instruction cannot override a failed checkpoint.
- **Still open:** full-feature acceptance. No merge, production operation or
  live balance claim is supplied by the partial implementation or this repair.

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

## Source findings that bound the remaining work

Original baseline: `e897b5214893`; latest inspected implementation: `4ecad7a9b`
plus the preserved receipt diff. Detailed baseline findings remain in Git history;
do not repeat the completed audit or treat old line numbers as current evidence.

- `zone_touch_transaction.c` still refuses flat-file settlement. Extend the
  existing stone claim/prepared-participant boundary and saved delivery marker;
  a candidate catalogue or committed claim alone does not prove player credit.
- `ship_shop.c`, `ships.h` and `ship_utils.c` merge commodity slots without lot
  identity and save payment, ships and markets separately. `SHIP_MAX_CARGO`
  counts combined crates and includes crew. The affected sale needs atomic
  recovery of all effects; a bonus-only receipt is insufficient.
- Legacy admission barriers now exist in the stack. `boon_reward_transaction.c`,
  `boon.c` and `maintenance_scheduler.c` still need accepted/unpublished/login/
  restored reward reconciliation. Suppressed callbacks lose earned entitlements.
- EXP/PvP integration already exists in `limits.c`, `fight.c` and the stack's
  tests. Reuse it. The old `epic_frag` wrapper had no production callers; do not
  invent a second live route to match the issue's assumption. Remaining award
  entries must share qualified preparation without boosting generic EPIC_PVP.
- Barquest profiles support bounded candidates, not proof of side access or
  epic payout. Runtime `ZONE_TOWN` is authoritative even at hometown zero.
  Reuse existing account activity independently of optional telemetry.
- `interp.c` still routes command 804 to legacy `do_boon`. Existing BOON help
  includes shop/toggle guidance; [HELP_SYSTEM.md](../content/HELP_SYSTEM.md)
  documents parsed-help precedence. Update both maintained sources consistently.

## Ablation decisions: non-goals, files and proof

Every addition must identify its retained acceptance item and concrete failure.
A required addition updates the remaining forecast or triggers the budget failure
rule; discovering it does not create extra hours. Drop optional work.

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

**Files:** reuse the already published `divine_boon*` implementation and minimal
backend persistence boundary, existing boon admission/scan handlers, interpreter/
toggle, `limits.c`, `epic.c`, `zone_touch*`, `fight.c`/`combat_outcome*`,
ship shop/cargo mutation/save code and help. Extend SQL/flat-file player or ship
snapshot capture/load only where the concrete receipt must share a save.
Do not refactor the general currency API merely to give it new semantics;
the cargo operation owns its idempotent payment boundary.

**Proof:** extend existing executable harnesses and disposable database/file
fixtures. Add a small clock/selection test and the missing domain recovery
cases; no new test framework. Helper/codec checks cannot prove a reachable
command, real stone payout or recoverable sale. The paused implementation's
authority and budget limits are recorded above.

## Remaining execution order and technical contracts

The numbered contracts below preserve requirements, not mandatory implementation
or PR boundaries. Reuse the existing stack; do not repeat already proven steps.

On an authorized continuation that passes the budget gate:

1. Finish the existing receipt-retention gap needed by prepared rewards, reusing
   valid tests; no generalized history service or extra foundation PR.
2. Prove actual cargo purchase/sale and stone save/recovery boundaries on both
   backends first. Use a real route and stone, then cover the variations below.
   Do not defer these largest costs or build substitute toy implementations.
3. Complete both vertical paths through selection, eligibility, prepared reward,
   save/reload and player output. Reuse existing EXP/PvP paths.
4. Finish legacy reconciliation, commands/help and combined journeys; run both
   required builds and remaining affected checks, then publish the complete diff.

Use one continuation branch unless a concrete dependency/review requirement needs
another. Keep existing PRs intact. Use focused commits, but do not require a
PR/build/report cycle for each helper. No full burn-in, CI wait, world-wide audit
or optional hardening phase. Apply the same clock and failure rules throughout.

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
  local evidence as each chunk becomes ready. Follow review requirements,
  without waiting on hosted CI. Keep cutover/backout operating notes concise.
  No production migration/import, restart, deployment or live balance claim.

## Requirement closure map

#245 remains open until all of these have implementation and executable proof.

All groups remain OPEN for full-feature delivery. Close an individual item only
with its implementation commit, executable command/result, backend and actual-path
evidence. A group summary cannot close an unproven member. Do not add criteria or
defer existing ones to make the clock fit.

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

## Delivery report and continuation record

The earlier human-days estimate and rolling multi-hour ETAs are withdrawn.
They are history, not additional budget. Never restore them from a child branch.
Current evidence does not support a promise to deliver the remaining feature
immediately or within an invented fresh window.

At each budget checkpoint or final delivery, report these facts briefly and retain
them in the handoff for the next turn:

- Original start/deadline; current time; elapsed, remaining or overrun; any
  explicitly approved change and its exact scope.
- Acceptance items fully proven since the last checkpoint, with commit and
  commands/results; partial and uncommitted work identified separately.
- Exact missing acceptance items and next concrete result; whether ALL remaining
  implementation and proof fit, with unknowns stated explicitly.
- Publication links and state; completion or missed delivery stated plainly.

No tracking service, automation, extra report file or test framework is needed.
The plan and existing evidence are sufficient. Updating this document is not
implementation completion. Finish when the full outcome is proven and published;
otherwise keep the issue open and follow the fixed budget's failure rule.
