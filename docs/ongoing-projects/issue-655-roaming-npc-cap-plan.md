# Issue #655: configurable roaming-NPC cap and training-dummy accounting

Status: implemented and qualified locally. The linked PRs track integration.
Date: 2026-11-04.
Branch: `branch/issue-655-roaming-npc-cap`.
Base: fetched `origin/master`, `af3829b85671480cdae23ae703da6ed1ca50a11a`.

This work will first replace the hardcoded roaming-NPC threshold with a formal
configuration setting whose **code fallback and shipped default are both 45**.
It will then resolve the defects and verification gaps identified in
[issue #655](https://github.com/LuminariMUD/Duris/issues/655), including the
[independent full-world investigation](https://github.com/LuminariMUD/Duris/issues/655#issuecomment-6629410216)
and [test/persistence findings](https://github.com/LuminariMUD/Duris/issues/655#issuecomment-6629412020).
## Evidence and disposition of every finding

1. **Hardcoded limit: implement formal configuration.**
   `src/world/random.mob.c::spawn_random_mapmob()` currently compares its count
   with literal `45`. The existing properties system already supplies file
   loading, staff inspection/editing, reload, revert, and save. Use that system.
   The requested default is 45; no increase or different intermediate default
   is implied by this plan.
2. **Dummies consume the roaming budget: fix the counted population.**
   The spawner counts every NPC with prototype 1255. Dummy creation prefers
   the same prototype and retains its identity. The prior isolated full-world
   boot on this base produced 71 fixed, marked dummies in 71 distinct rooms,
   zero unmarked 1255s, and `count=71` at the first scheduled spawn. A debugger
   bypass of that gate produced an ordinary equipped roamer. The count and
   controlled bypass are historical investigation results, not qualification
   of the future patch or evidence about production deployment.
3. **Stale persistence assertion: repair the regression.**
   `tests/async/test_training_dummy_contract.py` expects the literal
   `copyover_training_dummy_is(ch)`, while the real shared selector calls
   `copyover_training_dummy_is(mob)`. The earlier pytest run had 14 passes and
   this one failure; executable checks still excluded marked dummies.
4. **Silent test invocation: make the checks execute in the normal runner.**
   Rechecked during planning: `tests/run_regression_tests.py` invokes discovered
   `test_*.py` files directly with Python. The dummy contract file defines its
   pytest tests without a script entry point, so that route can report success
   without executing its assertions. Fix this file's invocation contract as
   well as the stale assertion; do not redesign the repository test runner.
5. **Ordinary NPCs sharing the prototype: preserve and test isolation.**
   `training_dummy_is()` uses the instance marker; `read_mobile()` zeroes fresh
   NPC data. Current target, spell-up, capture, and persistence boundaries use
   the marker. Ordinary generated NPCs must retain normal stats, equipment,
   strings, targeting, and recovery. There is no verified prototype-wide
   immunity defect to repair. The related callback collision was addressed in
   [PR #328](https://github.com/LuminariMUD/Duris/pull/328); retain its regression.
6. **Recovery: preserve current exclusions and close the integration gap.**
   Current file-copyover and Redis world-recovery writers exclude marked
   dummies, which bootstrap recreates. Codec tests alone do not prove an actual
   recovery journey. Qualify ordinary-roamer preservation, dummy recreation,
   nonduplication, and the corrected cap through both real recovery paths.
7. **Historical unmarked former dummies: investigate and resolve by evidence.**
   Before `1ba0a3658496c0a4eba9631bb38fc0697b214f85`, dummy payloads could be
   written without preserving their marker. An explicitly supplied payload
   retains million-base-HP and sentinel state after decoding but becomes
   unmarked. Such an instance would still count after the proposed exclusion.
   No affected production instance has been observed. Add bounded regression
   evidence and an operational diagnosis/remediation procedure; do not infer
   identity from name, HP, room, hometown, or prototype, and do not introduce a
   speculative data migration. The counter fix alone cannot recover lost
   provenance.
8. **Scope and observations: document the actual behavior.**
   The cap is global over eligible prototype-1255 NPCs, including off-map and
   owned ones. It controls scheduled generation, not every NPC-creation path.
   Staff `randobj mob` bypasses it; themed prototype 1256 and `M`/`Y` resets are
   separate. The scheduler attempts one spawn per roughly 120 seconds with a
   phase offset, and generation may fail. Woodseer/halfling/shaman is supported
   by the generator's tables, but an individual historical encounter and the
   deployment date remain unverified. These facts do not justify broader
   spawn-policy changes.

## 1. Introduce the setting, with default 45

Add `random.mapmob.populationCap=45.000` to `lib/duris.properties`, with a
nearby comment explaining its population and scheduled-spawn scope. Use 45 as
the missing-key fallback in the production consumer too. Keep one property
name and one meaning across source, tests, configuration, and operator docs.

The setting's contract is:

- It is a nonnegative whole-number population limit. `0` disables scheduled
  roaming spawns; it neither removes existing NPCs nor disables manual staff
  creation. There is no negative/unlimited sentinel.
- It is read from the active properties at each scheduled attempt, so valid
  `properties set`, `properties revert`, and `properties reload` operations
  affect the next attempt without restarting. Do not add an unnecessary cached
  configuration object, environment alias, database setting, new config file,
  or separate administration command.
- Missing key means 45. The shipped key also equals 45. A deployment retaining
  an older properties file still gets the fallback, but staff `show`/`set`
  only operate on loaded keys; document adding the shipped entry to retained
  operator configuration rather than promising automatic insertion.
- Reject negative, fractional, non-finite, overflowing, or malformed values
  for this key before publishing them. Since the properties store uses floats,
  check the representable stored value in widened arithmetic against the
  signed integer range before any integer cast; do not rely on the existing
  integer getter's unchecked cast/truncation. Exercise rounding near the upper
  boundary. Do not silently clamp a rejected value or treat it as unlimited.
- Put the smallest key-specific validation into the existing file-parser and
  staff-set boundaries in `src/world/properties.c`. Reuse one validation rule
  for both paths, including patterns that match this key. Invalid reloads must
  retain the active configuration through the existing transactional loader;
  invalid startup input must follow its existing boot failure path. Invalid
  staff input must leave this setting unchanged and report the reason. Preserve
  unrelated properties' parsing and command behavior; no generic schema
  framework or blanket numeric-policy rewrite is needed.
- Lowering the cap below the current ordinary population only stops future
  attempts until the count drops below it. Raising it enables at most one
  attempt per existing cadence; no immediate refill, cull, or new random draw
  is added by reading/validating the setting.

Operator documentation in `docs/operations/CONFIGURATION.md` and the runtime
section of `docs/operations/RUNBOOK.md` will cover scope, default, validation,
zero, lowered limits, and these existing commands:

```text
properties show random.mapmob.populationCap
properties set random.mapmob.populationCap 45
properties diff
properties save
properties revert
properties reload
```

Explain that `set` changes memory, `save` persists it, `revert` restores the
saved baseline, and `reload` reads disk and replaces unsaved values. Do not
promise saving a missing key through the generic command. Add focused tests
using the real properties loader/commands, following
`tests/async/issue263_property_reload.cpp`, rather than testing only a fake
property getter. Verify missing-key fallback, shipped 45, nondefault 2 and 60,
zero, all invalid classes above, successful and failed reload, save/restart,
and revert. A nondefault cap must alter the actual spawner's boundary.

Land this as the first implementation commit with its tests and documentation.
Retain the current counted membership in that commit so the configuration
change is independently reviewable; do not deploy that intermediate state as
the fix for #655.

## 2. Repair population accounting and regressions

In `src/world/random.mob.c`, include `combat/training_dummy.h` explicitly and
count only:

```cpp
IS_NPC(random_mob) && GET_VNUM(random_mob) == 1255 &&
    !training_dummy_is(random_mob)
```

Compare that count with the effective configured cap from step 1. Keep the
existing character-list scan; adding a maintained population counter would
create unnecessary lifecycle synchronization. Keep the current scheduler,
random selection, equipment, public-map placement, failure handling, and
manual/themed/reset creation paths. Do not change dummy prototypes or infer
markers from descriptions.

Add an executable production-function regression, tentatively
`tests/async/test_random_mapmob_population.py`, with real engine structures
and marker logic. A generator double may measure attempts, but distinguish
attempts from successfully inserted NPCs. Demonstrate failure of the relevant
cases on the original code before applying the fix, then prove:

- Default cap: zero ordinary roamers allows one attempt; 44 allows one; 45
  and above allow none. Repeat the boundary with cap 2 and cap 60 so a literal
  45 cannot pass. With cap 0, even an empty list permits no attempt.
- More than 45 marked dummies, including 69 and 71, do not consume the budget.
  Cover zero, cap-minus-one, cap, and over-cap ordinary populations alongside
  them. Successful insertion of the last available roamer stops the next
  attempt; a failed generator call leaves room for a later retry.
- Fixed, custom, and renamed dummies are excluded. An unmarked ordinary NPC
  with dummy-like text still counts. PCs, unrelated prototypes, themed 1256s,
  and fallback-prototype-7 dummies do not count.
- Unmarked 1255s still count outside map rooms, at `NOWHERE`, and when linked
  as pets; this fix does not add a location or ownership filter.
- Extraction of an ordinary 1255 releases a slot; extraction of a marked dummy
  does not change the corrected count. Exercise real extraction/list teardown
  in an integration fixture or disposable game, not solely a vector deletion.
- Accounting introduces no RNG calls and does not modify prototype data,
  existing NPCs, or the instance marker.

Replace or narrow the stale source-text assertion and add executable coverage
of the actual persistence selectors. Give the existing dummy contract file a
small explicit `main()` that runs its checks under direct Python invocation,
while retaining pytest compatibility. Prove that both invocation routes
execute assertions, including a controlled failing assertion in an isolated
test copy; a successful process exit with no checks is insufficient. Confirm
normal runner discovery and execution of the extended tests.

## 3. Qualify generated-NPC identity and recovery

Extend/reuse `test_generated_npc_state.py`,
`test_training_dummy_dispatch.py`, and the generated-NPC journey instead of
creating another persistence implementation. Verify marked/unmarked NPCs with
the same prototype through the actual target, spell-up, capture, callback, and
serialization selectors. Check fresh allocation, owned strings, normal HP,
act flags, and equipment remain independent of dummy profiling.

On disposable full-world runtimes with isolated state, use the real compiled
patch and shipped creation policy. Recount the eligible bootstrap rooms rather
than treating 71 as a universal constant. Observe marked dummies plus ordinary
roamers, the configured limit, and scheduled replenishment. Prove a genuine
spawn receives generated zone prose and equipment and reaches an eligible map
room; a Woodseer/halfling/shaman deterministic fixture can cover that pool
without requiring a chance encounter in the timed journey. Use a small
nondefault limit to make threshold/replacement journeys practical. Observe at
least one natural scheduler invocation; deterministic invocation can cover
additional boundaries. Do not substitute a debugger-forced count for the
patched-server acceptance evidence.

For file copyover and separately an actual isolated MariaDB/Redis recovery:

- Keep at least one ordinary generated roamer and fixed/custom marked dummies
  present before capture. Assert current writers exclude every marked dummy.
- Exercise repeated recovery; ordinary roamer identity, base state, inventory,
  and normal marker/target behavior must survive. Fixed targets are recreated
  once per eligible room. Custom targets are not promised persistence: under
  the current policy they are omitted and only bootstrap-selected fixed
  targets return. Preserve and document that behavior.
- Verify the post-recovery population decision uses only unmarked 1255s and
  reads the configured cap, including nondefault and zero values. Exercise
  extraction and replacement after recovery and check for duplicate targets
  or ordinary roamers.
- Keep codec and malformed-input checks, but label them separately from real
  file/Redis restart evidence. Use existing disposable-DB helpers and local
  Redis namespaces; no production snapshots or player data are test fixtures.

For the legacy caveat, retain a deliberately supplied old-style dummy payload
control alongside an ordinary-roamer control. Assert that payload decoding
alone cannot reconstruct the missing marker, and that current marked writers
refuse it. Do not "fix" the fixture by relabeling every million-HP or sentinel
1255. Trace any newly demonstrated current writer/admission defect and repair
that specific path with a regression before declaring this work complete.

Add a runbook procedure for a read-only deployed-revision/configuration check
and live 1255 population split by marker, with runtime identity, room, HP/act
state, and available checkpoint provenance as supporting observations. If
legacy contamination is suspected, inspect an isolated copy of the checkpoint
and deployment history. A name/HP match alone is insufficient. Where evidence
identifies an affected instance, document a targeted repair using existing
staff/lifecycle tools and verify that it releases the correct slot without
removing legitimate roamers or fixed targets. Production mutation requires
owner permission and is a separate execution step. If identity cannot be
established, preserve the data and record the unresolved operational question;
do not call it repaired or silently drop it from the handoff.

## Validation and delivery after resumption

Run the smallest applicable checks as each change lands, with ASan/UBSan for
native population, property-validation, and persistence fixtures:

```sh
make -C src
python3 tests/async/test_issue263_property_reload.py
python3 tests/async/test_training_dummy_contract.py
python3 tests/async/test_generated_npc_state.py
python3 tests/async/test_world_recovery_pipeline.py
```

Also run the extended full-world, file-copyover, and Redis journeys described
above using binaries whose revision/backend match the case. Record exact
commands, configuration, outcomes, and any unavailable validation in
`docs/testing/REGRESSIONS.md` and the implementation handoff. All compiled and
runtime artifacts belong under `bin/`; generated areas and temporary
accounts/state belong only to isolated fixtures. No migration is planned.
Do not require CI completion in place of local verification.

Use focused commits: (1) configurable setting/default 45 with property tests
and docs, (2) dummy exclusion plus real population and invocation regressions,
(3) recovery/legacy coverage and operational guidance as needed. Avoid splitting
one coherent regression from its fix merely to match this suggested grouping.

Acceptance requires both shipped and fallback defaults of 45; an effective
nondefault setting through file and staff controls; correct zero/invalid and
lowered-cap behavior; all population/identity/extraction/recovery cases above;
no silent contract-test success; and an explicit disposition of every finding.
Post implementation evidence back to #655, preserving the distinction between
shipped-code qualification and any unverified live legacy population. Do not
claim the historical deployment date or individual Woodseer encounter was
verified. Resolve any newly reproduced defect in these paths before closing
the implementation, and report unresolved production questions explicitly.

## Implementation handoff

Use `/home/aiwithapex/projects/duris-issue655-roaming-npc-cap` for this stack.
The user's original checkout is independent. The first branch remains
`branch/issue-655-roaming-npc-cap`, based on `master`. Each later PR targets its
immediate dependency. Keep this handoff current on the newest branch.

- **Configuration** ([PR #657](https://github.com/LuminariMUD/Duris/pull/657),
  commit `073515e0d`) — the spawner reads the validated property at each
  invocation. Both write boundaries share one parser. A malformed set glob
  matching the loaded cap is rejected before editing any properties. The
  existing transactional loader, setter, saver, and baseline handling do
  the rest. The issue-263 harness now runs the actual spawner with a generator
  double and both property backends, so a separate config harness is redundant.
  Passed: the MariaDB development build, the expanded
  issue-263 test with ASan/UBSan and float-cast checking, and formatting
  and whitespace checks.
- **Population and test invocation** ([PR #658](https://github.com/LuminariMUD/Duris/pull/658),
  commit `541635564`) — branch `branch/issue-655-roaming-npc-population`
  targets the configuration branch. The scan now excludes instances through
  `training_dummy_is()`. Extending the existing ASan/UBSan harness shares the
  real spawner and properties setup. The mixed-population assertion failed
  against the configuration-only spawner and passed after the fix, including
  69/71 marked targets, an owned roamer, `NOWHERE`, themed and fallback NPCs,
  zero, last-slot insertion, and retry after failed generation. MariaDB
  builds passed. The dummy contract passed 15 checks via direct Python and
  pytest, and an isolated failing assertion was detected by both. The normal
  regression runner found and passed the dummy and property checks.

- **Redis roamer items** ([PR #660](https://github.com/LuminariMUD/Duris/pull/660),
  commits `2ce38f5b3` and `c1490d9d5`) — the first fresh Redis capture
  restored the roamer's identity but lost its worn and carried items because
  this NPC had no authored equipment resets. The fix reuses bounded item
  trees, item UIDs, and ownership checks for ordinary 1255s. Later floor
  deltas and durable owners take priority over stale roamer trees. Existing
  generations remain readable. The final follow-up also covers a roamer in
  the Void, a valid room with vnum zero. The MariaDB build and the sanitizer
  pipeline and artifact projection tests passed.
- **Recovery and legacy handoff** — branch
  `branch/issue-655-roaming-npc-recovery` targets the Redis PR. The full
  journeys observed 71 distinct bootstrap rooms on MariaDB using the
  shipped creation rules. Natural scheduling created one normal equipped
  roamer with generated zone prose in an eligible map room. Two live file
  copyovers, a Redis crash restore, and a Redis clean restart preserved the
  respective roamer's identity, stats, worn slots, and carried item UIDs.
  Every recovery recreated fixed targets once per room and omitted custom
  targets. Actual extraction plus a zero cap left the population empty.
  Raising the cap to one allowed one replacement. A file copyover retried
  successfully after the existing artifact writer guard allowed its backlog
  to drain. Full-world Redis evidence was recorded at `2ce38f5b3`, with the
  later Void case qualified using the native pipeline and the MariaDB build.
- **Operator follow-up** — the generated-state harness confirmed that
  explicitly supplied pre-exclusion payloads can retain base HP 1,000,000
  and `ACT_SENTINEL` after losing the marker. The runbook gives a
  provenance-based diagnosis and targeted staff repair. The compiled data
  confirms Woodseer selects halflings and admits shamans. The original
  encounter, production deployment revision, and live legacy population
  remain unverified. No migration or release tag is needed for the stack.

The [regression guide](../testing/REGRESSIONS.md#full-world-roaming-npc-cap-and-recovery)
contains the reproduction commands and outcomes. The [runbook](../operations/RUNBOOK.md#scheduled-roaming-npcs)
contains the runtime controls and legacy diagnosis procedure.

## Merged-master gate follow-up

The implementation stack (#657–#661) landed through `7713fae16`.
The first complete `make test-all` run on that revision recorded 912 passes
and 30 failures across 942 cases. The baseline logs and exact revision are in
`/home/aiwithapex/projects/duris-issue655-roaming-npc-cap/bin/tests/master-gates-7713fae16/`.
The same checkout finished the original full `make test-db` gate with
97 passes and six failures across 103 cases. Its per-case logs are archived
under `db-cases/` in the same baseline log directory.

The focused `test-all` fixes in #663–#676 and #680 landed on master.
PR #656 already covered the command-attribute issue raised in #662. The
first coordinated full `test-all` rerun on `49fabec2c` finished with 930
passes and 11 failures. #685 and #691 addressed all 11. Its log is
`/tmp/duris-test-all-49fabec2c.log`. The next coordinated run uses
`/home/aiwithapex/projects/duris-master-test-all`.

- [#681](https://github.com/LuminariMUD/Duris/pull/681) qualified the playtime
  journey with the current hotboot command.
- [#683](https://github.com/LuminariMUD/Duris/pull/683) qualified epic training
  after synchronously publishing the fixture's effective HP.
- [#686](https://github.com/LuminariMUD/Duris/pull/686) waits for the effective
  luck change before testing artifact and guild rewards. Tracing after that
  fix showed an independent copyover bug. A player read can overlap startup
  writer work, and copyover drops the connection when artifact admission
  requests a fresh read. [#689](https://github.com/LuminariMUD/Duris/pull/689)
  landed as `b1d5d2b97` and refreshes the read within the original player-load
  deadline. All seven MariaDB artifact cases and all eight copyover
  regressions passed. Both native hotboots and canonical artifact swaps
  are covered.
- [#687](https://github.com/LuminariMUD/Duris/pull/687) qualified restart
  from a valid checkpoint after deliberately causing an overlapping capture
  to be rejected.
- [#690](https://github.com/LuminariMUD/Duris/pull/690) repaired the shared
  maintenance linkage for the address-retention and statistics harnesses.
  Both passed in disposable MariaDB after reproducing the original failures.
- [#692](https://github.com/LuminariMUD/Duris/pull/692) isolates the latency
  benchmark after the parallel database cases and preserves its 3-second
  budget. The original parallel run measured 3.25 seconds. The standalone
  run measured 1.00 second across 17 re-entries, with at most 16 queued
  shop saves per pulse.

The full DB rerun used master `01d190929` plus the six DB
PRs at local integration commit `83f39d5e4`. Run
`TEST_DB_JOBS=6 make test-db -j8 CC='ccache g++'` from the issue
worktree to reproduce it. The exact revision, command, log, and eventual
exit status are under `bin/tests/master-gates-verification/` there.
The per-case logs are archived in `db-cases/` beside the gate log.

The integrated run completed 108 passes and four failures across 112 cases.
The serial loop benchmark passed with a slowest re-entry of 1.00 second.
The overlap, epic-training, address-retention, and statistics cases passed.
The following PRs cover the four failures from the integration run.

- [#693](https://github.com/LuminariMUD/Duris/pull/693), stacked on #692,
  moves the full-world capture and artifact matrix before the serial loop
  benchmark. The concurrent NPC hotboot hit the existing player writer
  drain deadline. The capture pulse limit and hotboot guards are retained.
- [#694](https://github.com/LuminariMUD/Duris/pull/694) waits for the locker
  door acknowledgement after an asynchronous save. The entire disposable
  locker journey passed, including the failed guest departure.
- [#695](https://github.com/LuminariMUD/Duris/pull/695) verifies that a failed
  native exec retires its handoff file. The complete MariaDB telemetry
  journey passed with a paced injected outage, failed and successful
  copyover, and reconnect.
- [#696](https://github.com/LuminariMUD/Duris/pull/696) refreshes invalidated
  report batches and retries rejected SQL reads and Redis writes by key.
  The first check counted callbacks, which could pass with missing Redis
  keys. The revised full-world check clears the six keys before restarting,
  then verifies all six values and a recovered artifact in its staff report.
  That local rerun restored a 69.5 MiB generation with no pulses over 250 ms
  during capture.

The second full test-all passed all 941 cases on master `01d190929` with
zero failures or timeouts. Its log is `/tmp/duris-test-all-01d190929.log`.
The serial DB retests use local revision `1dabede8d` and the exact three
serial commands from the proposed runner. They write the revision, logs,
and eventual exit status to `/home/aiwithapex/projects/duris-master-gate-contracts/bin/tests/gate-db-serial/`.

The serial DB retest exited 0. World capture passed in 88 seconds and
restored a 69.5 MiB generation and logged all six report callbacks. This
historical run used the log-only report check. No pulse exceeded 250 ms. All seven artifact scenarios passed in 1,069 seconds,
including the NPC hotboot, and the loop benchmark passed in 177 seconds
with a slowest re-entry of 1.00 second. The separate complete locker and
telemetry retests also passed. All four failures from the full integration
run therefore passed their follow-ups. The 108/112 result belongs to the
full integration run. The later fixes were verified with the focused
journeys and the three commands from the proposed serial runner.
