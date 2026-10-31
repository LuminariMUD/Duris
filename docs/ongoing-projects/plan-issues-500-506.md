# Bartender quest bug fixes: issues #500 and #506

Date: 2026-10-31. Status: #500 implemented; #506 repair and proof in progress.
Fix branch: `branch/issues-500-506-bartender-bugfixes`.
Review: [PR #513](https://github.com/LuminariMUD/Duris/pull/513).
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

The original plan-only checkpoint is `9ef0f4203`; implementation evidence is
recorded below as work proceeds. The two reports share verification, but #506 needs its own
cause established; a #500 classifier fix is not evidence that #506 is resolved.

## Reopened #506 work

The user requires a demonstrated #506 repair on this branch. The earlier passing
29/30 flows are controls, not completion. Trace every post-abandon refusal and
construct the relevant states locally; obtaining the original player's state is
not a prerequisite for this work.

Outcome: reproduce a false refusal after abandonment, fix its owning path and
prove regrant when funds, allowance, history and a suitable target permit it.
Keep legitimate refusals, progressed-KILL history, replacement entitlement and
refunds intact. Non-goals remain changes to quest policy, quotas, fees or reward
selection. Expected owners are the existing bartender handler, history cache,
native fixture and disposable journey; edit only where failing evidence points.

The trace shows reset clears active/completed/origin/replacement fields.
Two missing checks were constructed: Tharnadia purchases across levels
11-56 (including the KILL-only range), and a history read started before a UTC
day change but published afterward. Before this repair SQL returned a boolean "today"
using query time and assigned the cache's day using callback time; the two could
disagree. Proof must first fail against current code, then pass through the real
bartender command path with the repaired implementation.

Constructed failures now established:

- The native fixture compiles the production SQL cache and bartender handler.
  An old zero-progress task is abandoned successfully while a history read is
  outstanding. Advancing the clock across UTC midnight before publishing its
  old-day rows gives a false zero allowance and refuses regrant. The regression
  failed with the original "any more quests" response and an inactive task.
- The same refusal fails against the pre-fix full MariaDB server at the actual
  Tharnadia giver. The disposable SQL writer's session clock makes the history
  SELECT execute with the previous day's date, then is restored before a queued
  completion marker. This faithfully constructs old-query-day/new-callback-day
  results without waiting for midnight or modifying production state. All seeded
  completion timestamps are yesterday; the old cache nevertheless reports zero
  remaining after abandonment. Evidence: `bin/tests/issue506-mariadb-before.log`.
- Additional native controls exposed two connected defects: unavailable history
  was reported as exhausted allowance, and a progressed abandonment as the first
  cache mutation after midnight lost its allowance charge when the next lookup
  cleared the stale day's counters.

The repair reads actual completion timestamps and counts them against the cache
publication day, rolls an existing cache forward before recording progressed
abandonment, and distinguishes unknown history from a known zero allowance in
the existing refusal branch. No quota, fee, history exclusion or route rule is
relaxed. All 72 original native scenarios plus ten production SQL-cache cases
now pass: delayed rollover, real same-day exhaustion, pending read, failed read
with retry, and progressed abandonment across rollover, each at 30 and 56. The
high-level fixture includes a second suitable KILL prototype so target exclusion
does not hide a counting defect. Completed target exclusions remain permanent.

The actual-giver after-fix history journey passes on both backends, including
save/restart: yesterday's records leave the current allowance at eight, paid
zero-progress abandonment keeps eight, regrant succeeds with the normal fee,
and the new task/wallet/eight old history records survive restart. The old
MariaDB binary reported zero and refused that same constructed regrant.
The SQL-only midnight race is now demonstrated through the actual SQL transport;
flatfile is a compatibility control with equivalent past-day records.

Refusal trace completed for the existing command path:

- Completed work goes to its reward/giver path. Active work is described;
  replacement-pending work uses the retained accepted type/level/progress and a
  free replacement, with explicit confirmation to discard it. Reset after a
  successful paid abandonment clears every assignment field before regrant.
- Minimum level, genuinely exhausted allowance, insufficient funds and rejected
  payment remain refusals without publishing a new task or losing a charge.
  Unavailable history now names the history problem and can be retried; it is
  not presented as a known empty allowance.
- Selection failure preserves state and refunds its fee. The expanded Tharnadia
  investigation tried 11,20,29,30,35,40,41,45,49,50,55,56 with fresh history and
  funds. In the captured world, levels 50/55/56 had zero proved-reachable routine
  KILL groups within their eligible bands, although hundreds existed elsewhere;
  routes were below both work/room bounds. Those requests returned the fee and
  left assignment inactive. This is the distinct target/route refusal under the
  current KILL-only/ordinary-travel contract; changing that contract is outside
  this repair. No universal high-level grant expectation was added to tests.

Temporary high-level candidate/flight diagnostics were removed after accounting
for that path. Evidence remains in `bin/tests/issue506-level-diagnostic.log` and
`bin/tests/issue506-candidates-*.json`. The retained regression is the reproduced
false allowance at the real giver, with positive/negative native controls;
it does not manufacture target eligibility or waive a legitimate quota.

The new `history` journey uses only disposable accounts/databases/state. Its
SQL writer's session clock is restored before the completion marker. The first
flatfile test reader incorrectly compared today's count with all past records;
that assertion was corrected to verify yesterday's records via the owning
history API and retain the completed-target exclusion across restart.
Final full-gameplay/recovery and shared abandonment regression checks are running.

The full MariaDB replay reached its final level-30 KILL case but hit the existing
120-second combat limit against brownie 5711 at room 5766 (still fighting,
target HP 211, quota 3). It did not fail a history/regrant assertion. The earlier
cases and recovery checkpoints are retained in `bin/tests/issue506-mariadb-full.log`;
the unchanged integration run is being repeated separately. Combat behavior and
limits are not modified for this quest-history repair.

The final native matrix (including all ten SQL cases), the new real-history
journey on both backends, and the original `reported` abandonment/regrant suite
on both backends pass. In both history runs, wallet values after aged abandonment
and regrant are 9,999,333 and 9,998,733 copper, allowance stays eight and the task
and permanent old-target exclusions survive restart. MariaDB's old binary
instead reports zero remaining and refuses the purchase before charging it.

Commands for the constructed history proof:

```sh
python3 tests/async/test_world_quest_target_retries.py
DURIS_WORLD_QUEST_BACKEND=mariadb DURIS_WORLD_QUEST_JOURNEY=history DURIS_WORLD_QUEST_BINARY="$PWD/bin/server/dms_issue500_mariadb_final" python3 tests/async/run_world_quest_dual_backend.py
DURIS_WORLD_QUEST_BACKEND=mariadb DURIS_WORLD_QUEST_JOURNEY=history DURIS_WORLD_QUEST_BINARY="$PWD/bin/server/dms_issue506_mariadb_final" python3 tests/async/run_world_quest_dual_backend.py
DURIS_WORLD_QUEST_BACKEND=flatfile DURIS_WORLD_QUEST_JOURNEY=history DURIS_WORLD_QUEST_BINARY="$PWD/bin/server/dms_issue506_flatfile_final" python3 tests/async/run_world_quest_dual_backend.py
```

The old MariaDB command fails at regrant as required by the regression. The new
commands pass. Their ignored records are `bin/tests/issue506-mariadb-before.log`,
`issue506-mariadb-history-final.log`, `issue506-flatfile-history-final.log`, and
`issue506-native-final.log`. Qualified binary SHA-256 values:

- MariaDB: `ce6fc80d5967358768a30437ef75e5ea8a241679ee37a9e67ba5b24c5f37d4b9`.
- Flatfile: `5f045a40bf37467040ccfa42934cfd83cf8726cac78d07b70e22509f0c0a13b7`.

The fix stays in `src/sql/sql.c` and the existing allowance refusal in
`src/specs/specs.mobile.c`. The native fixture reuses the production command/
selector with the owning SQL cache bodies and a controlled clock/SQL transport;
the actual MariaDB journey independently verifies the query and publication
behavior. Both use the existing runners and disposable setup. No player repair,
new service, schema field, retry framework or gameplay option was introduced.

Final fixture review ensures progressed work is genuinely incomplete: one kill
with quota above one. The recorded full-world fixtures had quotas four and seven;
the native constructor now grants quota two before advancing its progress. The
same legitimate native states were rerun against SQL bodies from baseline
`787baebbc`: delayed-read refusal and lost first-day abandonment charge fail at
both 30 and 56. The repaired source passes all ten cases. Baseline evidence is
`bin/tests/issue506-baseline-final.log`.

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

The original planning commit changed only this document. Implementation owners are:

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

The staged clang-tidy gate also passes. Its first invocation selected GCC 16's
standard-library headers, which the installed Clang could not parse. Re-running
with `--extra-arg=--gcc-install-dir=/usr/lib/gcc/x86_64-linux-gnu/13` selected the
installed compatible headers. A temporary `CLANG_TIDY` wrapper supplied only that
argument to the normal checker; hooks stayed enabled and no diagnostics were
suppressed. The commit hook checks a snapshot of the staged source, excluding
the unrelated working-tree edits.

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

## Implementation evidence, 2026-10-31

Started from clean branch commit `9ef0f4203`. Added failing route regressions for
the Quietus crew room and Bloodstone wino/watcher at origin, intermediate and
target rooms. The loaded-world audit now includes the three reported givers
explicitly while retaining hometown access checks. Further handler allowances
and Tharnadia transition edits remain conditional on the actual route evidence.

The initial route regression failed before the classifier change and passed
after it. A separate level-30 cosmetic-ASK regression then failed at assignment
creation despite a proved route. The repair shares one explicit list of 31
audited ambient Bloodstone handlers between movement and ASK checks; actual
quest interceptors and unaudited handlers remain excluded. Boundary inspection
identified the previously missed wandering `bs_insane`, plus merchant/holyman
and the other ambient ticks already inspected in #500. With these callbacks
installed, Cerrio proved 99 rooms and granted work; paid age/abandon/regrant also
succeeded. This is no longer the earlier cosmetic-bypass experiment.

Fresh disposable Human command checks at 132560 succeeded at both 29 and 30:
grant, age to 25 hours, pay abandonment, regrant. Wallet changes were purchase
580/600 copper, aged abandonment 60/67 copper, then purchase 580/600 copper;
allowance stayed at eight and no completion history was written. No Tharnadia
state-machine change is justified so far. The maintained runner is being
extended with the named Good/Evil matrix, saved/restarted abandonment/regrant,
progressed confirmation/history, legacy origin and pending free replacement.

The level-29 refusals have a specific geography explanation. Instrumenting the
owning `region()` calculation in a disposable diagnostic probe found Quietus's
interior reaches surface map room 635755 (region 2) and Underdark map room 850045
(a directed Underdark component). Bloodstone similarly reaches surface boundaries
including 602263/598665 (region 2) and Underdark room 813720. Each interior therefore
resolves to zero under the current single-region rule, without exhausting work.
The level-30 route/target fixes do not alter this intentional rejection. Deciding
which region such a mixed-boundary origin should use is deferred mechanics work;
the tests retain the local refusal and exact refund at 29.

The first complete Bloodstone walks exposed two more wandering ambient blockers:
executioner 74011 and homeless NPC 74021 in room 74337. Both backends had already
passed the named command matrix, aged abandonment/regrant restarts, progressed
confirmation/history, origin-zero binding and durable free replacement before
the walk reached those blockers. Audited all 36 current `bs_*` bodies together
to avoid repeated partial allowances: 32 ignore ordinary nonzero commands and
only call speech/emote helpers on ticks. They are explicitly listed; the mistress's
hunting handler and three devour handlers stay excluded and have negative route/
ASK controls. This repairs the same demonstrated wandering-procedure failure
through the whole reported zone, without a wildcard allowance or new registry.
The unbound, undeclared legacy `bs_ettin` is omitted rather than adding a new
binding/declaration; the explicit list covers the 31 current ambient handlers.

The new `reported` journey reuses the existing isolated runner, debugger probe,
snapshot reader, normal navigation/completion helpers and backend setup. Giver
placement, timestamp aging, one progressed-KILL fixture and origin-zero setup are
explicit test preparation; all purchase, paid abandonment, confirmation, refund,
replacement, actual Bloodstone ASK/KILL completion and saving use production
commands. Chaos entry restores its level-56 floor, so after restart the debugger
reapplies only the requested actor level before comparing allowance. It does not
repair or overwrite saved quest fields, wallet or history. The test does not
qualify combat difficulty or identify the original production player's state.

Unrelated concurrent edits to `lib/hardcore.cfg`, `src/cmd/actinf.c` and
`src/world/hardcore*` are preserved and excluded from this change. Production
bartender code remains confined to `src/world/world_quest_policy.c`; neither the
Tharnadia payment/reset path nor schema/configuration has a justified repair.

### Final classification qualification

The focused route regression passes under ASan/UBSan, including all 31 ambient
procedures at origin/intermediate/target rooms and negative hunting/devour cases.
All 72 production selector/creation/payment scenarios pass, including primary,
secondary and shop-delegate ASK checks for each ambient handler and rejection of
actual interceptors. Dynamic-policy and failure-feedback contracts pass.
Both persistence backends build with warnings as errors; the normal `make -C src`
entry point also passes. Formatting, Python compilation and all 14 documentation
checks pass.

The final `reported` journey passes on **both flatfile and disposable MariaDB**:

- Ten real-command cases: Human/Good and Drow/Evil at Quietus and Bloodstone,
  levels 29/30, plus the eligible Human at Tharnadia at 29/30. Level 29 at the
  two mixed-geography origins refuses and refunds exactly; all other cases grant.
- Four separate aged paid-abandon/regrant cases at the named givers, with saved
  abandonment and saved regrant each surviving a graceful restart. Queued
  abandon/quest commands preserve money, allowance and empty history.
- Tharnadia progressed-KILL confirmation records one target/history entry,
  consumes one allowance, survives restart and excludes that target on regrant.
  Origin-zero binding costs nothing. Pending invalidation/map/progress survives
  restart, and the later replacement is free with the retained allowance/map.
- Actual Bloodstone ASK and KILL completion and ordinary return travel: flatfile
  ASK 74118, four steps each way; KILL 74145, 34 each way. MariaDB ASK 74073
  (`bs_boss`, an admitted cosmetic handler), 42 each way; KILL 74004, 11 each way.
  The maintained journey asserts real XP, one reward, one allowance/history entry
  per completion and saved history, using the real command dispatcher.

Final loaded-world audit passes on both backends, with the named givers present.
Bloodstone proves 371-372 rooms in these runs; level-30 purchases succeed on both
sides. The observer's worst response was 271.1 ms flatfile / 270.7 ms MariaDB.
One earlier final flatfile audit failed its existing global assertion because no
Evil level-29 origin returned a candidate in that run. Its original exception
did not retain the origin matrix. A diagnostic rerun with the same assertions
passed (Ixie giver 97540 at 97653 returned target 20936); the runner now includes
the origin matrix in failure output. The earlier availability miss remains an
unexplained intermittent result, not a claimed gameplay repair or reason to
weaken the assertion. The deterministic and reported-giver checks above pass.

Final binary SHA-256 identities:

- Flatfile `bin/server/dms_issue500_flatfile_final`:
  `fb558167f474859911009de38e715c1d717cc9734b96bd334886205887a18978`.
- MariaDB `bin/server/dms_issue500_mariadb_final`:
  `9e8f5e947ea2a67900ed1a595b379718102a598c48e68fea5a378efbd2617d2f`.
- Owning policy source:
  `cd1b2fcbd127cb6368231729fdc2e82b0749c7f9716e434b47a1e895299e429e`.

Exact runtime entry points used, with the workspace path shortened to `$PWD`:

```sh
DURIS_WORLD_QUEST_BACKEND=flatfile DURIS_WORLD_QUEST_JOURNEY=reported DURIS_WORLD_QUEST_BINARY="$PWD/bin/server/dms_issue500_flatfile_final" python3 tests/async/run_world_quest_dual_backend.py
DURIS_WORLD_QUEST_BACKEND=mariadb DURIS_WORLD_QUEST_JOURNEY=reported DURIS_WORLD_QUEST_BINARY="$PWD/bin/server/dms_issue500_mariadb_final" python3 tests/async/run_world_quest_dual_backend.py
DURIS_WORLD_QUEST_BACKEND=flatfile DURIS_WORLD_QUEST_JOURNEY=audit DURIS_WORLD_QUEST_BINARY="$PWD/bin/server/dms_issue500_flatfile_final" python3 tests/async/run_world_quest_dual_backend.py
DURIS_WORLD_QUEST_BACKEND=mariadb DURIS_WORLD_QUEST_JOURNEY=audit DURIS_WORLD_QUEST_BINARY="$PWD/bin/server/dms_issue500_mariadb_final" python3 tests/async/run_world_quest_dual_backend.py
```

Ignored logs are `bin/tests/issue500-*-final*.log`; the earlier diagnostic
evidence is under `bin/tests/bartender-fix/`. #506's original production refusal
has not been reproduced or identified. Keep it open; the qualified transitions
do not establish the unknown original cause. No production operation occurred.

The final binaries also pass the complete existing `both` gameplay/recovery
journey on each backend: ASK and KILL at 11/29, KILL at 30, ordinary outbound and
return travel, real rewards/XP/history, partial-KILL restart, and invalidation,
relogin, restart and free replacement. Each backend completed three server boots.
These results are in `bin/tests/issue500-full-flatfile-final.log` and
`bin/tests/issue500-full-mariadb-final.log`, with the same binary hashes above.

```sh
DURIS_WORLD_QUEST_BACKEND=flatfile DURIS_WORLD_QUEST_JOURNEY=both DURIS_WORLD_QUEST_BINARY="$PWD/bin/server/dms_issue500_flatfile_final" python3 tests/async/run_world_quest_dual_backend.py
DURIS_WORLD_QUEST_BACKEND=mariadb DURIS_WORLD_QUEST_JOURNEY=both DURIS_WORLD_QUEST_BINARY="$PWD/bin/server/dms_issue500_mariadb_final" python3 tests/async/run_world_quest_dual_backend.py
```

Final acceptance review also adds explicit native command controls for an
unaffordable progressed abandonment and exhausted/unknown allowance after
abandonment. The existing flatfile history regression passes, including its
runtime count/history checks. No new history service or payment path was added.
`python3 tests/async/test_world_quest_remaining_unloaded.py` also passes, proving
the existing unknown-count and read-only text/JSON presentation contract.
The progressed-KILL fixture tolerates the selector's existing ASK fallback by
paying a zero-progress abandonment and retrying within the same eight-attempt
setup bound used by the gameplay cases; the recorded successful runs selected
KILL on the first attempt.

Final ablation keeps one private explicit procedure classification shared by
its two real consumers, the crew-room allowance, existing executable fixtures
and the existing dual-backend runner. It drops policy redesign, callback removal,
new registries, new schema/configuration and a speculative Tharnadia state patch.
Broader mechanics choices and the unidentified original #506 refusal remain
open. The PR references both reports without automatic issue closure.

Additional completion commands passed:

```sh
python3 tests/async/test_flatfile_world_quest_history.py
python3 tests/async/test_world_quest_remaining_unloaded.py
python3 -m py_compile tests/async/run_world_quest_dual_backend.py tests/async/test_world_quest_target_retries.py
make -s -C src -j4
make -s -C src PERSISTENCE_BACKEND=flatfile DMS_BINARY="$PWD/bin/server/dms_issue500_flatfile_final" -j4
make -s -C src DMS_BINARY="$PWD/bin/server/dms_issue500_mariadb_final" -j4
./scripts/format.sh --check
python3 tests/async/test_documentation_contract.py
git diff --check
```

Implementation commit: `579f2401a2fd33089748754f06bb96f49f080b29`.
Master advanced to `9ad734e9e60b0938181f85cd20cdb9614a14adc8` during
qualification. The read-only `git merge-tree --write-tree origin/master HEAD`
check is clean, and GitHub reports PR #513 mergeable and non-draft. The PR's
eight changed files are limited to the bartender policy, existing regressions/
runner, reference and this plan. Concurrent unrelated work is excluded.
