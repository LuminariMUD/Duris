# Issue #245: rotating Divine Boons

> **Delivery contract: six hours TOTAL, never six more hours.**
> Preserve the entire agreed outcome. Do not reset the clock, expand the budget,
> hide a missed deadline behind progress, or call partial implementation done.
> A forecast outside the remaining budget is a delivery failure to disclose
> immediately, not permission to continue spending time.

Status: active implementation; incomplete and inactive in gameplay. The owner explicitly approved continuing the full scope past the old deadline on 2026-10-22.
Revised 2026-10-22 for [Duris #245](https://github.com/LuminariMUD/Duris/issues/245).
Authoritative plan branch: `branch/issue-245-divine-boons`.
Source baseline: [master `e897b5214893`](https://github.com/LuminariMUD/Duris/commit/e897b5214893a66b75db5507be0a9be97b519cfc).
Issue specification inspected at its 2026-10-22 update, including all five comments.
The agreed follow-up decisions take precedence over older exploratory numbers.
The previous issue-59 plan is preserved byte-for-byte in
[plan-issue-59.md](plan-issue-59.md); earlier plans remain in their existing files.

The owner explicitly resumed implementation and approved continuing the full
scope ASAP past the original deadline. This supersedes the previous pause and
the elapsed deadline's stop boundary; it does not reset spent time, invent a new
six-hour allowance, or reduce any acceptance requirement. The original delivery
was missed. Focused code/tests, commits, pushes and stacked review-ready PRs are
authorized. Production migrations/imports, deployment, restart and merge remain
separate actions.

## Fixed budget and failure rules

**Historical contract; missed.** The owner has now explicitly approved full-scope
continuation past this deadline. Retain the original clock and missed checkpoints;
the old stop boundary no longer blocks authorized implementation. No replacement
deadline or extra six-hour budget was granted.

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

### Published trade save support (#287) and live producer WIP

[PR #287](https://github.com/LuminariMUD/Duris/pull/287) is open, ready and
mergeable at `e4a9a120c`, stacked on #283. Both backend builds, focused native
repository/receipt races, currency reservations, pipeline coalescing, sanitized
trade/player codecs, formatting and LLVM 22 clang-tidy pass. No merge or tag.
The original plan branch is synchronized after preserving its externally rebased
history on current master. Source branch is now
`branch/issue-245-divine-shop-integration`, based on #287.

Uncommitted producer code now connects qualifying purchases and single/all cargo
or contraband sales to prepared settlement; boot restores the active boon book,
and completion publishes money, ship/crew, market, book and achievement. Live
player purse publication preserves intervening ordinary money and skips a newly
hydrated session using a process-local flag. Payload v2 shares the existing
fixed affect-row codec, independently of full snapshot schema evolution.
Syntax checks pass; these producer hooks are not yet qualified or published.

Immediate next work: finish affected ship/market reservations and normal-save
coordination, persist loss/invalidation alongside ship snapshots, then prove the
real producer path and publish it. Selector routes, activation/cutover, commands/
help and final integrated gameplay evidence remain unfinished. Keep working on
those concrete paths; do not restart broad analysis or rerun unrelated evidence.
Memory owns all gameplay calculations. SQL/flat-file restore state, validate
revision/identity and persist prepared after-images. Original deadline remains
missed; the owner authorized full-scope continuation without a replacement budget.

### Published producer fixes (#283)

[PR #283](https://github.com/LuminariMUD/Duris/pull/283) is open and ready for
review, implementation `cf50aaf57`, stacked on #282. It is mergeable; both builds,
native focused checks, formatting and LLVM 22 clang-tidy pass. Next source branch
is `branch/issue-245-divine-trade-runtime`, based on #283 plus this handoff.
Outcome: correct ordinary contraband price-cache quotes, persist
zero-revenue cargo/contraband removal, and preserve trade generation through a
staff market reset. Prepared wallet denominations must also respect the existing
`INT_MAX` currency facade limit on both backends. Non-goals: changing approved rates or replacing ordinary
trade. Files: ship cargo/shop code and focused existing native checks. Proof:
execute the actual writer/sale functions for distinct quotes, stale jobs, paid/
zero/empty sales, and reset/reload generation. These native checks pass, including ASan/UBSan,
and prepared-wallet overflow rejection passes. Both final backend builds pass. Reuse the qualified settlement backend
evidence; then continue actual gameplay integration.

### Latest published backend continuation (19:01 UTC / 22:01 Asia/Jerusalem)

- [PR #282](https://github.com/LuminariMUD/Duris/pull/282) is open, ready for
  review and mergeable, stacked on #279. Implementation `5a5d0bf3f` is pushed
  with 0/0 parity; both builds and native evidence match it. No release tag or
  merge. The compound backend slice does not activate gameplay trade rewards.
- Next worktree `/home/aiwithapex/projects/duris-issue245-plan`, branch
  `branch/issue-245-divine-trade-runtime`, based on #282 plus this handoff-only
  commit. This source tree is clean at handoff. The original named plan branch
  continues to carry the foundation and authoritative current plan only.
- Both real repository dispatchers now atomically persist prepared wallet, ship
  slots/crew, market, account book and permanent result. Type 19 and entity 15
  are appended. Memory prepares prices/eligibility/after-images; the writer only
  checks identity/revision/shape and commits them. SQL uses the existing inbox/
  outbox transaction, flat-file uses six after-images in the existing journal.
  Restart/retry returns the stored result and does not apply a financial delta.
- Native SQL purchase/sale proof passes ten rollback boundaries, with cargo and
  contraband cases, exact market/price restoration, conflicting retries, 9+1
  merged stock, spent allowance and repeated receipts. The real SQL maintenance
  executor rejects restored generation-zero work after trade and accepts current
  generation work. The new check caught non-unique legacy market indexes: the
  executor now replaces each logical cell inside the transaction instead of
  appending an ineffective upsert. Crew after-images also handle a missing row.
- Native flat-file purchase/sale proof passes the journal and all six after-image
  interruption boundaries, covering both goods. Retry/reload conserves wallet,
  consumed inventory, market and fixed allowance; old player captures are rejected.
  Native market proof covers v1 -> v2 read compatibility, stale restored maintenance,
  current maintenance, corrupt/symlink files and an unconfigured root. Zero-revenue
  sales also commit consumed goods/cap with unchanged money; no phantom credit.
- Shared market codec is now in `flatfile_cargo_repository`; the existing player
  file envelope encoder is shared in `flatfile_player_snapshot_file`. This keeps
  persistence independent of live ship/gameplay code. The wallet helper owns only
  authority, as all native snapshot writers already do; it does not invert locks
  by acquiring a player lock afterward. Other balances/receipts remain untouched.
- Additive migration 0050 is registered, re-runnable and preserves the generation
  on replay. Both actual engine metadata fingerprints were measured on fresh
  disposable MySQL 8 and MariaDB 10.11 schemas and synchronized with runtime and
  lifecycle manifests. New schema is needed by ordinary market persistence as
  well as the new financial operation; publication must include this migration.
- Passed: `run_divine_trade_mysql.sh`; `test_flatfile_player_repository.py`;
  `test_flatfile_cargo_market.py`; sanitized `test_divine_trade.py`, critical-command
  and player-item-snapshot codecs; existing standalone flat-file item consumer;
  seven runtime-compatibility and twelve lifecycle checks; both backend builds.
  Formatting, LLVM 22 clang-tidy, both final builds and whitespace checks pass. Existing
  loaded-world EXP/PvP/zone evidence is retained, not rerun without a relevant change.
- **Next actual delivery:** wire the existing ship shop paths to memory-cached
  active account books/generation, preserve purchase/access/pricing rules, reserve
  affected participants and publish absolute completion once. Coordinate ordinary
  wallet/ship/market saves and callbacks, add real port-route selection, and attach
  loss/clear/confiscation/salvage/sink/ownership provenance updates to affected ship
  capture/save signatures. Preserve crew and achievement behavior. Qualify actual
  purchase/sale/save/restart journeys on both backends before activation.
- **Subsequently resolved in #283:** ordinary SQL contraband cache quotes,
  zero-revenue slot save marks, staff-reset financial cursor and native wallet
  denomination bounds. The approved 25% and three-hold policy is unchanged.
- Then finish legacy reconciliation/activation, player/staff commands and help,
  and all final integrated acceptance journeys. Full #245 remains incomplete.
- Original start 08:41:02 UTC, original deadline 14:41:02 UTC. At 19:01, elapsed
  is 10h 20m, overrun 4h 20m. Owner-approved full-scope continuation remains active;
  no replacement budget or reliable upper completion ETA is claimed.

### Earlier in-progress checkpoint (17:34 UTC / 20:34 Asia/Jerusalem)

- Current worktree remains `/home/aiwithapex/projects/duris-issue245-plan`, branch
  `branch/issue-245-divine-trade-settlement`, HEAD `6e672a44b` (published #279
  handoff). The settlement source/test diff is **uncommitted and not qualified**.
  Do not mistake the clean published prerequisite head for full trade delivery.
- The real critical-command payload/result and SQL compound executor are written:
  memory supplies absolute wallet, slots/crew, market cells and account-book
  after-images. Existing inbox/outbox handles SQL receipt/retry; type 19 and ship
  entity 15 are appended. Flat-file dispatch now prepares snapshot + domain + ship
  catalogue + market + account book + permanent receipt under one authority journal.
  Player locks precede authority; account validation uses the already locked domain
  record to avoid recursively acquiring authority through identity lookup.
- The market codec was moved intact into `flatfile_cargo_repository` for two actual
  callers: ordinary market persistence and compound trade. This prevents repository
  tests/writers from linking live ship gameplay. Format v2 adds a trade generation,
  reads v1 as zero, and normal writes/maintenance reject obsolete generations.
  Scheduled snapshots append their captured generation; restored old snapshots remain
  accepted at generation zero and cannot overwrite a later committed trade.
- Passed new evidence: sanitized native command/book codec; native flat-file market
  interruption/recovery, old maintenance rejection and v1 load. The SQL server build
  passed **before** the last flat dispatch/codec extraction edits, so rebuild current
  source. The combined native purchase/sale fault harness is being added to the
  existing flat-file player repository suite; first run exposed a fixture ship with
  missing required revision, now corrected. It has not yet passed.
- Files to continue: `divine_trade_command*`, `divine_trade_repository*`,
  `divine_trade_flatfile.c`, existing critical dispatch/outbox and flat-file player/
  ship/market helpers, `ship_cargo_transaction.h`, and focused existing harnesses.
- **Required before publication:** qualify the compound flat-file command at the
  journal and all six after-image boundaries; execute the real SQL command/retry/
  rollback path. Register/verify additive `0050_divine_trade_state.sql` (currently
  present but not in manifests), refresh both measured runtime schema fingerprints,
  update affected native test link lists, and build both backends. Existing market
  code now needs that schema, so do not publish it with migration head 0049.
- **Still not implemented:** game-thread trade admission/publication and mutation
  hooks, real port selection, wallet/ship reservations and normal save ordering,
  precise price/achievement integration, actual cargo journeys; then legacy
  reconciliation/activation, commands/help and final full-scope journeys. No live
  trade rewards are enabled. All requirements remain in scope.
- Clock: original start 08:41:02 UTC, original deadline 14:41:02 UTC. At 17:34,
  elapsed is 8h 53m and overrun is 2h 53m. Full-scope continuation was explicitly
  authorized; no new budget or reliable upper ETA has been invented.

### Earlier verified continuation (16:58 UTC / 19:58 Asia/Jerusalem)

- **Published:** [PR #276](https://github.com/LuminariMUD/Duris/pull/276),
  receipt retention, implementation `b2135ca72`, stacked on #275; and
  [PR #277](https://github.com/LuminariMUD/Duris/pull/277), zone epics,
  implementation `3afb15200`, stacked on #276. Both are open, ready for review.
  No merge or release tag; no ordinary-installation activation or production work.
- [PR #278](https://github.com/LuminariMUD/Duris/pull/278), exact trade lots and
  shared fixed account allowance, is also open and ready for review, stacked on
  #277 at `f436aaac2`. Hosted base/head were read back, mergeable; remote parity
  is 0/0. This is preparation/codec code, not a live trade payout.
- Latest source worktree `/home/aiwithapex/projects/duris-issue245-plan`, branch
  `branch/issue-245-divine-trade-settlement`, based on the published #279
  implementation `3485ea516` plus the handoff-only commit.
  Trade implementation started from a clean tree. Both current server builds
  include the wallet checkpoint below; earlier loaded-world zone journeys remain
  valid evidence for implementation `3afb15200`. No gameplay reward math or
  selector changed in the two trade prerequisites. The named plan branch contains the foundation
  plus this current document, not the whole implementation stack.
- Both final loaded-world journeys pass after the fractional rounding correction:
  real zone 429, normally created Orc, 100 -> 150, save, restart and reconnect.
  Native fixtures validate claim/replay/corruption, ordered zone/PvP delivery,
  old payloads, runtime orchestration, additive math and seed parity. Preserve
  the evidence below; do not repeat green checks without a relevant change.
- **Trade preparation now implemented, not yet wired to gameplay:** exact paid
  operation lots survive merged slots and partial consumption; untracked stock
  goes first, invoice remainders stay with unsold lots. A single account/boon
  record fixes the first full hold and combined three-hold allowance across goods
  and ships. Loss/unproven transfer removes proof without creating a new cap.
  The versioned checked snapshot preserves spent allowance after all lots sell.
  The native ASan/UBSan harness passes 9+1, partial basis conservation, combined
  goods, a larger second ship, different accounts, strict start/expiry, same-port
  sale, loss, invalidation, corrupt/truncated reload and 600 purchase/sale cycles.
  Both incremental server builds pass. No gameplay payment or atomic settlement
  is claimed by these policy/codec checks; no new SQL schema was introduced.
- [PR #279](https://github.com/LuminariMUD/Duris/pull/279), existing wallet revision
  checkpoint, is open and ready for review, stacked on #278 at `3485ea516`.
  Both backend builds match that source; remote parity is 0/0 and the published
  PR base/head have been read back. The source tree is clean at this handoff.
- **Qualified wallet checkpoint prerequisite:** reuse the existing memory
  `wallet_revision` rather than add a trade-specific counter or SQL migration.
  Snapshot wire v11 appends this revision; old versions restore zero. SQL and
  flat-file status saves carry it with money and reject older wallet captures,
  including a later general save revision. Non-wallet status updates preserve
  the wallet revision. Flat-file snapshot/domain balances still share one atomic
  authority commit, including the initial player checkpoint. The real native SQL
  save/load harnesses pass on disposable MariaDB, as do sanitized codec/old-wire,
  actual capture and flat-file repository tests (interrupted commit/reload,
  nonzero starter-wallet revision and stale capture). Both incremental backend
  builds, domain regression and native flat-file save-claim contracts pass.
  Full settlement and gameplay are still missing. SQL proof executed the
  maintained `player_save_claim_mysql_harness.cpp` and
  `player_load_filter_mysql_harness.cpp` on a disposable complete schema; no
  production database or checkout environment credentials were used. The
  temporary local runner has been removed; the maintained complete SQL runner
  remains `tests/async/run_player_save_claim_mysql.sh`.
- **Concrete next implementation:** admit a qualifying buy/sale from memory,
  prepare wallet/ship-slot/market-cell/account-book after-images, persist one
  identified critical command on the existing writer and publish its absolute
  result. Use the existing `wallet_revision` guard above for old player captures;
  reserve the actual ship/market participants and cover their queued save/replay
  ordering. Extend the existing authority helpers instead of adding a second
  transaction framework. Hook loss/clear/ownership mutations to lot consumption
  or invalidation. No live trade bonus may be admitted until this boundary and
  both backend fault/retry journeys pass. No settlement code has been written yet.
- **Next concrete delivery:** connect trade on the branch above. Reuse the existing ship
  capture/writer and cargo-market authority; implement purchase batches and the
  fixed three-first-ship-hold account cap together with atomic sale consumption,
  player payment, market update and recovery. A bonus-only multiplier is not an
  acceptable implementation. Then finish safe legacy reconciliation/activation,
  player/staff boon commands/help and combined final journeys. Full #245 remains
  incomplete; all required outcomes remain in scope.
- **Clock:** original combined start 08:41:02 UTC, original six-hour outer bound
  14:41:02 UTC. At 16:58 UTC, elapsed is 8h 17m and overrun is 2h 17m. The owner
  explicitly approved full-scope work past that deadline. There is no new
  six-hour budget or reliable upper completion ETA.


### Earlier continuation checkpoint (2026-10-22 14:45:07 UTC)

- Owner approval: **Continue full scope ASAP past the old deadline.** The original
  six-hour outer bound was 14:41:02 UTC / 17:41:02 Asia/Jerusalem and is missed.
  No replacement deadline has been invented. Earlier pause text below is history.
- Outcome remains all 23 acceptance items. Non-goals remain optional frameworks,
  repeated green validation, release tags for unmerged work and production changes.
- Receipt retention is committed as `b2135ca72` and published for review in
  [PR #276](https://github.com/LuminariMUD/Duris/pull/276), stacked on #275.
  Both flat-file repository harnesses, sanitized Divine delivery, formatting,
  LLVM 22 clang-tidy and whitespace checks pass. Both previous incremental
  backend builds remain valid for the unchanged reviewed source.
- Current worktree `/home/aiwithapex/projects/duris-issue245-plan` is now on
  `branch/issue-245-divine-zone-epics`, based on #276. Next outcome: a real stone
  prepares each recipient's final zone award and both backends recover it once
  using the existing saved balance/watermark. Reuse the existing claim, writer,
  receipt and delivery machinery; do not add a second reward framework.
- Files: zone command/repository/transaction, existing recipient-delivery and
  flat-file domain code, epic preparation/selection and focused existing tests.
  Proof: old payload compatibility, full-group claim/retry, mixed PvP/zone
  ordering, save/restart and actual stone selection/payment on both backends.
- **Continuation checkpoint 15:12 UTC / 18:12 Asia/Jerusalem:** original outer
  bound missed by 31 minutes; full scope remains authorized past it. No fresh
  completion promise or replacement budget is established. Receipt PR #276 is
  published. The zone-epic slice below is uncommitted and still under focused
  qualification; all-issue acceptance remains OPEN.
- Zone implementation now prepares exact recipient amounts at actual stone
  touch, persists shared PvP/zone delivery ordering and recovers both through
  the existing bounded login query. SQL child inboxes retain the parent receipt;
  no new migration or query budget is needed. Flat-file claim, full receipt,
  issued revisions and alignment/touch state share one authority transaction.
- A common selector validates live payable stones and directed side paths, uses
  actual encounter crowding and matching account brackets for group suitability,
  and rejects towns/unsafe targets before category weighting. Native defaults
  derive from the existing reviewed 110-zone payout seed. Its historical group
  value 100 is a payout divisor, not recommended party guidance. No payout seed
  values were changed; an already-stale epic.h source fingerprint was refreshed.
- Passed this continuation: both backend server builds (later final source edits
  require incremental rebuild); domain, full player save/reload (including claim
  journal recovery, retouch, mixed PvP/zone and checkpoint), sanitized reward math/
  delivery and selector harnesses; ten seed checks; disposable MariaDB full-group
  claim/retry/rollback and actual login recovery/corrupt-zone-receipt rejection.
  Old 88/512-byte compatibility and orchestration checks are being finished.
- **Continuation checkpoint 15:43 UTC / 18:43 Asia/Jerusalem:** original combined
  start 08:41:02 UTC; elapsed 7h 02m, original six-hour bound overrun by 1h 02m.
  The owner-approved continuation remains full scope, with no reliable upper ETA.
  #276 remains the published result. The zone slice is still uncommitted.
- Full-world execution confirms flat-file stones now reach prepared payment and
  save real base payouts (80/275/90/175/600). It also exposed the incumbent selector's
  rejection of Tharnadia's normal inn spawn. `inn()` was traced: it handles RENT
  and returns false for movement. That specific proc is now allowed; unknown
  special-room movement stays excluded, and a focused regression passes.
- The loaded catalogue currently proves an Evil target in zone 429 (six-account
  encounter crowding); the conservative Good pool has no payable epic at the
  sampled untouched world state. Empty objectives remain allowed; no safety
  fallback was relaxed. Metadata becomes available on the normal object event.
- Review of that real mobile-held stone found a completion bug: eligibility
  searched only its NPC/reset-room location. It now follows the existing
  `obj_zone_id()` container/carrier resolver, retaining target proof after corpse
  loot or player acquisition within the same zone. Native regression covers
  acquisition and rejects moving the stone out of its designated zone.
- Existing staff `world persistence` now reports bounded, validated target counts
  and eligible epic zone IDs. This supports the required staff status and lets the
  journey choose a real proved target rather than guess. Stone metadata initializes
  on its existing `PULSE_MOBILE+4` bounded object event; the journey waits for that
  readiness. At this checkpoint, the +50% loaded-world journey is still running.
- Both final backend builds, changed-line LLVM 22 tidy, all 1120 tracked C/C++
  formatting checks, legacy orchestration/88- and 512-byte receipt compatibility,
  quaff/legacy reward publication and dual-backend XP consumer checks pass.
  Reuse these results unless later source changes invalidate the relevant check.
- **Zone-epic qualification complete at 16:07 UTC / 19:07 Asia/Jerusalem.**
  Both actual full-world journeys pass using the current binaries and original
  zone-429 stone: a normally created Orc on the Evil side earns 150 from base
  100, saves, restarts and reconnects with the same balance. The fixture selects
  from actual eligible targets and seeds one paused objective offline; weighted
  population choice/hourly admission remain the separate executable selector
  proof. No production data or shared server was used.
- Exact maintained journey commands:
  `python3 tests/async/test_divine_boon_zone_journey.py --backend flatfile --server bin/server/dms_new_flatfile`;
  `tests/async/with_disposable_mariadb.sh python3 tests/async/test_divine_boon_zone_journey.py --backend mariadb --server bin/server/dms_new`.
  `make world` generated the required ignored world inputs. No generated area
  outputs are staged. Test actor creation reuses the existing journey helper,
  with a race-menu argument and fixed-alignment prompt handling for the Orc.
- The exact final rounding requirement also retains fractional group and
  alignment shares through Divine preparation. A real 100*2/3 base pays 100
  with +50%, rather than 99 after premature rounding. Ordinary legacy integer
  payout behavior remains unchanged. Sanitized production-math tests and both
  final backend builds pass after this correction; both journeys above also
  ran after it. All changed-line formatting/tidy and whitespace checks pass.
- Additional focused proof: native claim/replay/rejection/SQL rollback (including
  15 recipients), old 88/512-byte payloads, actual orchestrator, interrupted flat
  claim/checkpoint and mixed zone/PvP recovery, SQL login/corruption, ten seed
  checks and affected legacy award/XP consumers. Run the SQL claim fixture with
  `tests/async/with_disposable_mariadb.sh python3 tests/async/test_epic_stone_transaction.py`;
  its TEST_DB_* bridge uses only the explicit disposable service.
- **Remaining full feature:** trade batch provenance/account cap/atomic settlement,
  legacy reconciliation and activation, player/staff boon commands/help, and the
  combined cutover/rotation/all-rewards/restart journeys. #245 remains OPEN.
  Publication of the qualified zone slice is the immediate next action.

### Superseded paused checkpoint (history)

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

### Published implementation history (retained evidence)

- Worktree: `/home/aiwithapex/projects/duris-issue245-plan`; branch
  `branch/issue-245-divine-pvp`, stacked on `branch/issue-245-divine-experience`
  -> `branch/issue-245-divine-selection`
  -> `branch/issue-245-divine-delivery`
  -> `branch/issue-245-divine-activity`
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
- Review-ready delivery checkpoint: [PR #270](https://github.com/LuminariMUD/Duris/pull/270),
  implementation `49602d449`, stacked on #269. Both server backend builds,
  changed-line formatting, clang-tidy and whitespace checks pass.
- Seventh chunk: EXP candidate selection caches actual normal NPC reset locations
  from 15 bounded source zones, reusing bartender boot profiles without its item
  reward or quest level gates. It requires at least two eligible NPC prototypes,
  five reset encounters and three reachable encounter rooms. Ordinary directed
  paths start at current `guild_locations[town][0]` spawn rooms for the relevant
  justice side, rejecting restricted rooms, opposite-side towns, locked/secret/
  blocked exits, special room procedures and terrain requiring special access.
  Dynamic paths/flags are rechecked; `ZONE_TOWN` always rejects targets even with
  hometown zero. The selector weights actual account brackets, reduces weight
  for served brackets, prevents same-side duplicates and relaxes only the soft
  repeat preference when the safe pool is thin. Both backends build the same
  boot catalogue. It does not yet drive live rotation or activate rewards.
- Seventh-chunk proof: ASan/UBSan native selector harness passes for directed
  side access, runtime town/safe/map/closed/private flags, restricted rooms,
  inaccessible terrain, changed doors, unknown profiles/content, account
  brackets, side exclusions, active duplicates and repeat relaxation. Existing
  bartender dynamic-policy contracts pass. Actual loaded-world positive target
  journeys, group suitability, epic/trade candidates and category selection
  remain required; synthetic graph proof does not close those acceptance items.
- Review-ready EXP selector: [PR #271](https://github.com/LuminariMUD/Duris/pull/271),
  implementation `3a58b7ede`, stacked on #270. Both backend builds, formatting,
  clang-tidy and whitespace checks pass.
- Eighth chunk: `gain_exp()` now dispatches qualifying NPC combat to precise
  arithmetic with a separate original eligible base. Existing increases do not
  enlarge the Divine contribution; reductions and final/accumulation caps stay
  effective. Damage, tanking, healing, melee, kill and normalized kill-bonus
  awards use the correct NPC encounter and side/zone/window. Healing follows
  the healed character's hostile NPC; recursive tank awards derive independently
  before attacker rest, level-cap reductions or Divine credit. A shared numeric
  body retains ordinary float arithmetic for all non-Divine awards. Group kills
  and blood-streak producers carry their fractional legitimate share alongside
  their original integer calculation; only eligible Divine awards use the
  fraction. Actual caller tests cover a two-player group receiving 161 rather
  than 160 from an 80.8 share, and a 1.99 streak share paying 3 rather than 2.
  Sub-unit bases cannot fabricate an extra minimum bonus. Existing Nexus and
  epic-bonus paths expose their precise values; ordinary integer/float callers
  keep their behavior. Computed epic modifiers retain their original double
  value rather than being normalized as configuration percentages.
  Configured float modifiers use their shortest decimal value for the precise
  path, avoiding final-floor errors such as 179 instead of 180 at 90%.
- The game loop now drives the hourly selector through the existing writer.
  Queue refusal retains the exact unsubmitted choice for the hour; if the hour
  passes it is skipped. Pause, clock jumps and full/empty pools consume the
  opportunity correctly. Just-expired zones enter repeat history before choosing;
  changed targets are cancelled before retry admission without rerolling.
  Default legacy mode and the unfinished activation gate remain closed.
- Eighth-chunk proof: the existing quest/kill XP harness executes real production
  dispatcher, qualification and modifier bodies on both backend builds with
  ASan/UBSan and float-cast checks. It covers all six NPC sources, additive rest/
  global/race/Nexus/epic/difficulty stacking, reductions, precision and caps,
  healer opponent, independent fractional tank shares, unrelated XP families,
  expiry/side/zone/town-zero exclusions and non-finite/overflow rejection.
  The native selector harness covers hourly queue refusal/exact retry, pending
  publication, forward skips, expiry history, pause and target invalidation.
  Real Nexus lifecycle/consumer and flat-file authority harnesses preserve
  integer behavior and prove fractional payouts; difficulty and telemetry
  progression checks pass. Actual full-world reward/save journeys remain open.
- Review-ready NPC EXP and hourly integration:
  [PR #272](https://github.com/LuminariMUD/Duris/pull/272), implementation
  `2b3bb7d4b`, stacked on #271. Both server builds, formatting, clang-tidy and
  whitespace checks pass. Existing passing evidence was reused as applicable.
- Ninth chunk: PvP selection now requires both distinct warmed account populations
  and permits only one active global PvP slot. The actual death producer prepares
  its Good/Evil bonus from the legitimate base, excluding the separate 500 task
  reward and retaining reductions. Generic `EPIC_PVP` gains remain unboosted;
  the unused `epic_frag()` route is removed. Payload v5 stores boon ID, admission
  time, fractional base and task component; ordinary captures still write v4.
  Prepared results use a checksummed flat-file record or SQL inbox result with
  an explicit new envelope; ordinary results retain their 1536-byte layout and
  old captures/results remain readable. No SQL migration was needed.
- Recipient ordering reuses the existing issued `epic_revision`, allocated by the
  locked SQL row or flat authority. A predecessor links only prepared deliveries,
  so ordinary revisions may create harmless gaps. `divine_pvp_award` is a reserved
  compound-ledger reason, not a standalone command. Both repositories retain the
  prepared amount and predecessor before publication. Live submission defers
  these epic deltas until commit; matching callbacks and login recovery share
  one ordered publisher. Already checkpointed sequences are skipped. Publication
  does not issue another ledger revision or re-evaluate an expired boon.
- New player-load readers recover unpaid receipts before admission, and queued
  critical player work holds asynchronous login reads. Captures requested by
  level/achievement hooks are held until all reward effects finish, then the
  normal full player checkpoint saves balance, watermark and affected state.
  A fault test exposed a mixed flat-file read (old watermark/new balance); the
  reader now obtains snapshot, domains and pending receipts under one authority
  lock. Advancing a flat marker requires a complete financial status capture.
- Ninth-chunk proof: ASan/UBSan/float-cast tests execute real PvP preparation,
  submit/completion, ordered publication, nested capture deferral and recovery
  on both build configurations. Real flat repositories cover journal failure,
  replay, multiple awards before checkpoint, login reads and interrupted full
  checkpoints. Disposable MariaDB fixtures cover ordered issuance, rollback/
  retry, exact replay, unpaid login reads, corrupt parents and paid filtering.
  Legacy player-load/save, combat, artifact and frag-cap checks pass. Actual
  loaded-world PvP/save journeys remain part of final qualification.
- Review-ready prepared PvP delivery:
  [PR #275](https://github.com/LuminariMUD/Duris/pull/275), implementation
  `7b3407016`, stacked on #272. Both server builds, affected bank/legacy-boon
  consumers, formatting, clang-tidy and whitespace checks pass.
- **Before activation (uncommitted fix described in the paused checkpoint):**
  remove the fixed lifetime receipt ceiling for new flat
  prepared work. The pre-existing domain operations list caps at 512; complete
  parent results cannot grow in that list forever. Compact checkpointed detail
  while retaining durable retry identity through the existing authority files;
  preserve unrelated legacy receipts. The byte bound now accommodates the
  already-declared operation count instead of failing early at 64 KiB.
- **After explicit resume:** finish and publish flat receipt retention, then implement prepared zone rewards
  and real flat-file stone payouts on the same saved delivery boundary;
  complete legacy receipt retention/delivery reconciliation before activation.
  Then finish epic candidates, cargo and command/help paths below. Activity and
  EXP/PvP selection already have published implementation; do not rebuild them.
  The state API does not itself prove targets safe or legacy work settled.
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
- **Still open:** full-feature acceptance as an integrated system. Published
  state, persistence, writer, activity, EXP selection/reward and prepared PvP
  checks prove the bounded behavior recorded above. They do not prove completed
  cutover, all reward categories, trade, commands or actual loaded-world journeys.
  No production action performed.
- Ablation: reuse one state/codec for both backends; no scheduler, delivery
  framework, general economy rewrite or extra verification campaign added.
  State revision plus an atomic snapshot supplies rotation retry identity.
  The receipt-retention follow-up uses existing authority files because the
  reproduced per-player lifetime limit needs durable replay outside that list;
  do not generalize it into a separate economy framework.
- Next zone delivery step: extend the existing prepared-reason predecessor lookup
  and load readers across both PvP and zone receipts. Reuse issued revisions;
  never derive a new sequence from the applied watermark. Multiple accepted
  awards before callbacks must retain distinct identities and ordered recovery.
- Scheduling: previous time estimates are withdrawn; use the paused checkpoint's
  actual completed, uncommitted and remaining work. Work stays paused until the
  user explicitly resumes it.

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

Runtime authority is the game thread's in-memory state, as the owner reaffirmed
on 2026-10-22. It prepares selection, eligibility, prices, lots and allowances.
The existing single writer persists the exact prepared operation and rejects a
stale revision; SQL does not select targets or recalculate gameplay from rows.
SQL and flat files restore state at boot and identify committed operations during
recovery. A financial success is published only after its prepared atomic record
is durable, so crash recovery cannot duplicate money or restore consumed cargo.

Trade preparation records exact individual purchase lots and one account/boon
allowance, then deterministically prepares partial consumption. Native proof covers
9 old + 1 eligible, invoice conservation, both goods sharing the three-first-hold
cap, another ship/account, loss, expiry and checked reload. PR #282 now commits
the prepared financial after-images on both backends. The next consumer is the
actual game-thread ship shop: admission, prices, reservations, mutation provenance
and completion/recovery publication still require implementation and live proof.

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
