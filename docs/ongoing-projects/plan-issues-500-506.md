# Bartender quest bug fixes: issues #500 and #506

Date: 2026-10-31. Status: planned; implementation has not started.
Fix branch: `branch/issues-500-506-bartender-bugfixes`.
Source baseline: `b737db20210ff2d3e4eebccb212c9918b9b6f877` (`master` and
freshly fetched `origin/master`).

Reports: [#500, Quietus/Bloodstone refusals](https://github.com/LuminariMUD/Duris/issues/500)
and [#506, Tharnadia regrant after abandonment](https://github.com/LuminariMUD/Duris/issues/506).
Read alongside the current [bartender reference](../reference/BARTENDER_QUESTS.md).

## Outcome

Repair demonstrated false refusals in the existing bartender purchase and
abandon/regrant paths. An eligible character with a suitable ordinarily reachable
target can obtain work at the reported giver. A legitimate refusal retains the
correct quest/history state, gives consistent feedback, and returns any purchase
fee when selection fails. Preserve existing paid work and replacement entitlement.

This checkpoint delivers this plan on a dedicated fix branch. The implementation
below is future work. The two reports share verification, but #506 needs its own
cause established; a #500 classifier fix is not evidence that #506 is resolved.

## Non-goals

Keep current mechanics as regression boundaries for this repair, leaving their
long-term design open. Do not change ASK/KILL target-level bands, zone averages,
reward pools/weights, target history, allowances, fees, quotas, sharing, or the
level-29 local / level-30 broader-geography boundary. Level 30 still requires
ordinary outward and return travel; it does not authorize ferries, portals,
teleports, or unknown scripts. The 24-hour setting decays the abandonment fee;
it does not expire a quest.

The [historical follow-up on #500](https://github.com/LuminariMUD/Duris/issues/500#issuecomment-6523930773)
raises real design/compatibility questions about ASK levels and former destinations.
Those decisions are deferred. A changed historical selection rule, or failure to
randomly receive a particular zone, does not establish a bug in this scope.
Do not reset player history, force a different target after zero-progress
abandonment, remove content callbacks, relax genuine route gates, add a general
procedure registry, or redesign persistence. No production operations, player-data
repair, release, or issue closure are part of this planning commit.

## Evidence and remaining uncertainty

- **Quietus:** giver **1709** resets at **1734**; reported room 1754 is nearby,
  not the giver. `inspect_room()` in
  [world_quest_policy.c](../../src/world/world_quest_policy.c) rejects
  `crew_shop_proc`. Its gate in [ship_shop.c](../../src/ships/ship_shop.c)
  handles only LIST/HIRE. #500 records a level-30 real-command grant and paid
  abandon/regrant when that callback alone was disabled in a disposable process.
  Keep the crew feature and correct its classification. The separate level-29
  failure remains unexplained by that experiment.
- **Bloodstone:** Cerrio **74060** resets at **74339**. The existing shop delegate
  in [shop.c](../../src/economy/shop.c) preserves `world_quest`; this is not a
  missing giver binding. `ordinary_mobile_proc()` rejects `bs_wino` and
  `bs_watcher`, whose bodies in [specs.mobile.c](../../src/specs/specs.mobile.c)
  ignore ordinary nonzero commands and perform cosmetic ticks. #500 reports
  that allowing one, or even ten inspected cosmetic handlers, still did not
  produce a grant. Identify the remaining route and target constraints before
  claiming this location repaired. `ask_handler()` is a separate eligibility
  gate: movement safety does not imply that a handler lets ASK reach its target.
- **Tharnadia:** giver **132555** resets at **132560**. Its binding remains in
  [specs.assign.c](../../src/specs/specs.assign.c), and the reset is in
  [tharnadia.zon](../../areas/zon/tharnadia.zon). The original level, target,
  exact refusal, wallet, history, and quest state are unknown. `world_quest()`
  refreshes validity before handling abandonment; payment completion records
  progressed-KILL history and calls `resetQuest()`. In
  [world_quest.c](../../src/world/world_quest.c), reset clears origin/replacement
  fields and marks STATUS dirty. These paths need a reproduction, not a guessed
  reset or timeout patch.
- **Coverage:** the loaded-world `quest_world_audit()` in
  [world_quest_journey_probe.cpp](../../tests/async/world_quest_journey_probe.cpp)
  skips `hometown < 1`, omitting both #500 givers. The existing
  [dual-backend runner](../../tests/async/run_world_quest_dual_backend.py) uses
  room 16633 for its command journeys. It already supports queued abandon/quest
  commands, disposable persistence, recovery, normal travel, and restart.

Current source inspection confirms these owners. Compared with #500's
`2b2b6fb2d578b88e54b2a653506c4dd429346479` baseline, the inspected route,
quest-state, giver-binding, crew, shop, reset and journey files are unchanged;
the only `specs.mobile.c` changes concern unrelated money-changer/smelter paths.
The full-world results above are evidence recorded in #500, not new runtime
reproductions performed while writing this plan.

## Implementation sequence

### 1. Establish failures at the actual givers

Extend the existing loaded-world probe/runner with explicit cases for the three
giver/room pairs. Retain the existing hometown audit and add the named cases
without weakening hometown access checks or expanding into an all-world audit.
Use disposable eligible characters, empty history and known funds. Record race,
level, equipment/affects, exact refusal, origin, route status/work, target checks,
wallet, allowance, and assignment/replacement fields. Keep observations in ignored
`bin/` output. Do not inspect existing player records or use trusted privileges
to bypass the mechanics being tested.

Start #500 at levels 29 and 30 with Good/Human and Evil/Drow fixtures, preserving
the issue's distinction between requesting work there and being sent there.
For each refusal, trace from the actual origin through the first blocked boundary
and onward to candidate targets: callbacks, directed return access, region/map
resolution, level/reward eligibility, live/reset provenance, ASK/KILL suitability,
and history. Follow later blockers after the first is removed. A small positive
room count alone is insufficient. For Quietus at 29, distinguish unresolved or
conflicting region, missing reachable map boundary, and an actual traversal defect.

At Tharnadia compare a fresh purchase with the same eligible fixture after a real
grant, aging its timestamp beyond 24 hours, paid zero-progress abandonment, and
another purchase. Setup may age only the disposable fixture; ASK/payment/reset
transitions must execute production commands. Include a legacy assignment with
origin zero and an existing replacement entitlement. Establish a failing native
regression for each confirmed defect before changing its owner. If #506 cannot be
reproduced, retain the tested cases and exact evidence gap; do not call it fixed.

### 2. Correct only demonstrated false decisions

In `world_quest_policy.c`, admit `crew_shop_proc` at the existing room-procedure
check and the individually audited Bloodstone callbacks at the existing mobile
check. Audit any additional handler only when it blocks one of the reported
routes or targets. Inspect movement, door and arrival/departure behavior as well
as tick side effects; never allow every `bs_*` handler by name or clear callbacks
in the final fix. Preserve unknown/gating handlers and all request work limits.

Where an otherwise suitable reported ASK target is rejected solely by a known
ASK-ignoring handler, fix the existing ASK check separately. Preserve rejection
of actual ASK interceptors, including quest handlers and relevant shop delegates.
The positive case must reach `quest_ask()` through the real command dispatcher.

Resolve Bloodstone and low-level geography with the evidence from step 1. Correct
a boundary calculation only if it contradicts the existing local/ordinary-travel
contract. If no target qualifies under that contract, record the specific
remaining restriction and faithful refusal/refund; do not manufacture eligibility
or present that result as a restored grant. A change to the contract belongs in
the later mechanics discussion, with unresolved report elements left open.

For #506, change `world_quest()`, its payment completion, `resetQuest()` or recovery
only if the reproduction identifies a defect there. Preserve the existing
currency-publication boundary and command fencing. Update a misleading refusal
at its existing branch if demonstrated; no new diagnostic subsystem or exhaustive
player-facing rejection taxonomy is needed.

### 3. Prove the command and saved-state behavior

Extend the existing route/live-target harnesses, then run the named full-world
cases with real callbacks installed. Use normal commands for outbound travel,
target interaction/completion and return on representative repaired routes;
debugger placement and callback bypasses are setup/diagnostics, not journey proof.
Exercise ASK and KILL where eligible, including Cerrio's shop-dispatch path.

Required assertions:

- Known harmless room/NPC procedures no longer empty a valid route. Cosmetic
  NPC wandering through origin/intermediate/target rooms does not cause false
  refusal. Genuine interceptors, unknown procedures, locked/unsafe edges, absent
  directed returns and exhausted work bounds remain conservative. Below 30 stays
  local; broader geography at 30 retains ordinary-travel proof.
- A successful new purchase captures the real giver/origin and charges once.
  Paid zero-progress abandonment clears the task only after successful payment,
  adds no completion history and consumes no allowance; a subsequent eligible
  purchase succeeds, even if selection legitimately chooses the same target.
  Age changes the abandonment fee, not task validity or regrant eligibility.
- Progressed KILL requires confirmation. Successful paid confirmation records
  the target and consumes the existing allowance once. Regrant succeeds when
  allowance/targets remain, and correctly refuses when the last allowance or
  target pool has been used. Preserve completed-target exclusions across types
  and levels; distinguish unreadable/unready history from known exhaustion.
- Insufficient funds, rejected/submission-busy payment, stale completion state,
  and no route/target do not publish a new assignment or lose money. Failed paid
  selection refunds once. Test immediate queued `abandon` then `quest`, and the
  earlier coin-credit/abandon/quest ordering using the existing command fencing.
- Genuinely invalidated work retains free replacement, progress and bought-map
  state while no replacement exists; later replacement is free and uses the
  accepted type/level/remaining work. Temporary blocked/unproven work is not
  destructively reset. Preserve origin-zero binding and free cancellation's
  confirmation behavior.
- On both flatfile and disposable MariaDB, assert live state and durable state
  after save/relog and a graceful restart at abandonment, regrant and pending
  replacement checkpoints. Compare wallet, quest fields, allowance and target
  history, including failed selection/refund. A serializer test or build alone
  does not qualify restart/payment ordering.

Reuse existing controls for rewards, sharing and unrelated policy; add no tests
that merely restate unchanged implementation. Update the bartender reference
only where the repaired behavior or a necessary clarification changes it.

## Files

This commit changes only this document. Expected implementation files are:

- `src/world/world_quest_policy.c`: demonstrated route/ASK classification fixes;
  any geography change requires the separate evidence described above.
- `tests/async/world_quest_routes_harness.cpp`,
  `tests/async/world_quest_live_targets_harness.cpp` and their existing
  `test_world_quest_routes.py` / `test_world_quest_target_retries.py` runners:
  missing executable failure and preservation cases.
- `tests/async/world_quest_journey_probe.cpp` and
  `tests/async/run_world_quest_dual_backend.py`: the named origins and real
  abandonment/regrant/persistence journeys, reusing existing setup and clients.
- Conditional: `src/specs/specs.mobile.c` / `src/world/world_quest.c` for a proven
  #506 transition/feedback defect, and `docs/reference/BARTENDER_QUESTS.md` for
  relevant corrections. No area, schema, configuration or generic payment-layer
  change is justified by the evidence so far.

## Proof and completion

After implementation, run these existing entry points from the repository root.
The full-world commands qualify the new named cases only after the runner/probe
extension above; the current runner does not yet cover them.

```sh
python3 tests/async/test_world_quest_routes.py
python3 tests/async/test_world_quest_target_retries.py
python3 tests/async/test_world_quest_dynamic_policy.py
python3 tests/async/test_world_quest_failure_feedback.py
make -C src
DURIS_WORLD_QUEST_BACKEND=both DURIS_WORLD_QUEST_JOURNEY=audit python3 tests/async/run_world_quest_dual_backend.py
DURIS_WORLD_QUEST_BACKEND=both DURIS_WORLD_QUEST_JOURNEY=both python3 tests/async/run_world_quest_dual_backend.py
./scripts/format.sh --check
python3 tests/async/test_documentation_contract.py
git diff --check
```

Run additional existing history/reward tests only if the actual diff touches
their behavior. The journey runner builds both backends in isolated `bin/` roots
and uses a disposable MariaDB container; do not point it at production. Record
commands, source/binary identities, failing-before/passing-after assertions and
any unavailable runtime coverage here. Do not wait for CI or substitute CI for
the required local proof.

Completion requires every confirmed defect fixed and demonstrated through its
real path, and each remaining refusal tied to evidence. An unexplained Bloodstone
restriction or unreproduced Tharnadia report remains explicitly unresolved;
passing synthetic tests cannot close either gap. Keep issue references as
references until their applicable acceptance work is actually complete.

## Ablation decisions and planning validation

Keep classification repairs, the bounded Bloodstone/geography investigation and
the separate Tharnadia reproduction: removing any leaves a reported failure
unaddressed. Simplify verification by extending the existing harnesses and
dual-backend journey. Drop historical-policy restoration, a generalized callback
framework, new knobs, broad content cleanup and persistence redesign: none is
needed to prove or repair the currently identified false decisions.

Planning checks on 2026-10-31:

- `python3 tests/async/test_world_quest_routes.py`: passed, including directed
  routes, barriers, capabilities, scripts, traps and bounds.
- `python3 tests/async/test_world_quest_target_retries.py`: all 71 production
  live-target/creation/payment scenarios passed under ASan/UBSan.
- `python3 tests/async/test_documentation_contract.py`: all 14 checks passed.
- `git diff --cached --check`: passed for the plan-only staged change.

These are baseline controls, not reproduction or qualification of the three
reported giver flows. No gameplay implementation, full server build, full-world
journey, database mutation or production validation was performed for this plan.
