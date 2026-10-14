# Log review: merged delivery and release handoff

Tracking: [#56](https://github.com/LuminariMUD/Duris/issues/56) and
[#58](https://github.com/LuminariMUD/Duris/issues/58).
Completed work, acceptance contracts, test evidence and history are in
[log-server-review.md](log-server-review.md). This file records the merged delivery and the remaining conditional/deferred work.

## Integration and review fixes

The authorized repository delivery was merged in **#70 → #73 → #74 → #75**
order on 2026-10-14; #75 includes this final handoff. All four use squash merges to
preserve master's linear history. Master was still `c6a95a470` when landing
began, so no additional conflict resolution was needed.

After each parent landed, the child's complete diff relative to its saved parent
head was applied to the new master. Each resulting tree exactly matched its
qualified branch before the documentation-only handoff below. Published child
branches were updated with explicit old-head leases and retargeted to master.
This preserved the reconciliations in earlier merge commits. Existing repository
rules stayed intact, unrelated worktrees were preserved, and no release tag was
created.

All three review findings are fixed and resolved. The MySQL-client interface
repair `b6a8ecb4c` uses the existing `sql_work` type and is present throughout the
landed stack. The final source, tests and runtime data are unchanged from the
qualified combined tree `8b2681862`; later changes only update documentation.
The retained 736-regression/77-database evidence therefore remains applicable.

| PR | Qualified checkpoint | Landing |
| --- | --- | --- |
| [#70](https://github.com/LuminariMUD/Duris/pull/70) | `b6a8ecb4c` | `455b76a04`: artifact/guild memory authority, all-level awards, task recovery and diagnostics |
| [#73](https://github.com/LuminariMUD/Duris/pull/73) | `bf07716c5` | `ad91bba76`: actual boon results, level-30 training and immediate HP |
| [#74](https://github.com/LuminariMUD/Duris/pull/74) | `5e67ad3dc` | `aaa0aa5aa`: bounded area output and accurate innate help |
| [#75](https://github.com/LuminariMUD/Duris/pull/75) | `8b2681862` (code), `e5dd89d11` (review handoff) | Final delivery: death/healing/distance repairs, connection observer cleanup and this release handoff |

`8b2681862` passed `make -C src -j16`, `make -C src pfile -j16`, maintained
migration targets (also force-rebuilt with `make -B -C migrations/tools all
affects pfile_converter -j16`), `./scripts/format.sh --all --check`, all **736
regressions** in 591.84 seconds, all **77 disposable database legs** in one
707-second run, and all **15 site tests**. Every artifact reward/fault/restart
variant passes. The final documentation contract passes all **14 checks**.
Server/pfile/migration-tool builds also pass with the actual MySQL 8.0.46 client,
using isolated extracted development headers; the installed MariaDB package is
unchanged. `make security-check` passes; no new CodeQL/Trivy scan is claimed.

The corrected connection test from `d4fe27272` now passes within the full
regression run as well as its retained before/after observer probe. The client
interface regression catches the old MySQL mismatch and passes MySQL, MariaDB
and flat-file compile cases; `check_tests_catch.sh 9dd77184e b6a8ecb4c` reports
**1/1 catches**. Final evidence is in `bin/analysis/review-final/`; earlier
qualification remains in `bin/analysis/integrated/` and the integration worktree.
Final handoff commits change documentation only.

The #73 catch script reports 2/4 (native boon and teacher); its two DB journeys
skip without explicit settings and are separately qualified on disposable
MariaDB. #74 reports 2/2, with direct evidence of the original ASan overflow and
old Seadog wording failing the renderer. The original #75 lifecycle 3/3 catches
remain valid for unchanged repairs. All three review findings (#74 area/help,
#75 observer cleanup) are resolved. #56/#58 and the PR descriptions carry the
current evidence; skipped items stay deferred. #58 is closed by #70 with all six
implementation acceptance criteria checked. #56 stays open for its deferred
scope. No production action occurred.

**Outcome:** land all four qualified PRs, reconcile issue status and record the
remaining release handoff. **Non-goals:** production rollout, historical repair, owner-skipped
investigations, and ship-mechanic changes. **Files:** the affected award,
repository/coordinator, boon, area and help paths and their existing tests/docs.
**Proof:** focused executable and disposable gameplay/SQL journeys, defect
before/after checks, then the required final gates below. Ablation keeps existing
writers, diagnostics and test harnesses; no additional service or compatibility
gameplay path is needed.

### 1. Reconcile #70 with current master

- [x] Refresh master and update
  [#70](https://github.com/LuminariMUD/Duris/pull/70), preserving published
  history and unrelated worktrees. Resolve the epic-zone manifest conflict and
  any overlaps introduced by the merged changes below.
- [x] Preserve [#69's all-level epic awards](https://github.com/LuminariMUD/Duris/pull/69):
  `gain_epic()` returns actual synchronous award success. Retain potion failure
  protection, carried/held bottle behavior and all-level score/task display.
  Keep the separate epic skill-training minimum at 30.
- [x] Preserve [#72's pending task recovery](https://github.com/LuminariMUD/Duris/pull/72):
  retain the last valid catalogue, saved pending assignments, recovery without
  another epic milestone, and no repeated roll or outage notice.
- [x] Reconcile [#76's diagnostics](https://github.com/LuminariMUD/Duris/pull/76)
  with #70's memory-authority repair. Preserve readable terminal notices, full
  operation references, bounded entity/context metadata, diagnostic propagation
  through completion/shutdown/copyover, and detailed logging independent of
  notice suppression. Update the repository/coordinator, `comm.c`, pipeline
  documentation and harnesses together; do not restore SQL approval of live
  artifact/guild rewards.
- [x] Regenerate and verify `migrations/seeds/epic_zone_payouts.json` from the
  final combined `src/world/epic.h`, using `scripts/epic_zone_seed.py`. Preserve
  established payouts, group sizes and overrides; a header-hash conflict does
  not authorize changing payouts.
- [x] Recheck the complete #58 contract after integration: every eligible
  uncapped feed and cumulative guild benefit applies once in memory; saves stay
  ordered across transfers, soul changes, spending, expiry/removal and staff
  changes; caps and real eligibility remain enforced; v2 history/replay grants
  no reward; bounded retries, old v1 receipts/outbox handling, reconciliation and
  crash/shutdown/copyover/restart remain correct. Use the
  [retained ES-01–ES-05 acceptance matrix](log-server-review.md#work-sequence).

Integration evidence:
[#69 conflict/policy handoff](https://github.com/LuminariMUD/Duris/pull/70#issuecomment-6165130394)
and [#76 diagnostic handoff](https://github.com/LuminariMUD/Duris/pull/70#issuecomment-6165493647).

### 2. Reconcile #73's boon feedback with all-level awards

- [x] Update [#73](https://github.com/LuminariMUD/Duris/pull/73) after its parent
  #70 is reconciled. Remove/rework the obsolete `BTYPE_EPIC` gain-level branch in
  `src/economy/boon.c`: `epic_level_can_gain()` and `epic_gain_min_level()` were
  deleted by #69. Do not bring back the removed gain gate to make the stack build.
- [x] Make boon feedback follow the actual all-level award result, including
  award failure. Preserve consumed completion semantics, non-epic rewards,
  exactly-once application and artifact/guild publication.
- [x] Retain #73's level-30 skill training, distinct mastery completion, refused
  repeat purchase, and immediate derived-HP/GMCP/save/restart behavior. Keep the
  Human Warrior and Illithid Psionicist purchase coverage.
- [x] Reconcile `test_epic_level_gate.py` with master's all-level award and
  separate skill-gate tests, including `test_epic_gain_runtime.py` and
  `test_epic_skill_level_gate.py`. Resolve plan/manifest/test conflicts, preserve
  #72 task-recovery coverage and update obsolete policy descriptions/help.

Evidence: [policy and conflict handoff](https://github.com/LuminariMUD/Duris/pull/73#issuecomment-6165130734).

### 3. Fix #74's area-response overflow — P1, LR-06

- [x] Reproduce the
  [oversized-name overflow](https://github.com/LuminariMUD/Duris/pull/74#discussion_r4268461592)
  in the actual basic `do_area()` branch in `src/cmd/actoth.c`: a 65,500-byte zone
  name can fill `buf`, then the unbounded average/warning `strcat` writes beyond it.
- [x] Bound the complete response, including name, numeric/sentinel average,
  staff no-argument zone ID and danger warning. Preserve `unknown` / `not applicable`
  meanings and real-level warning boundaries.
- [x] Extend `tests/async/test_zone_average_display.py` with oversized/plain/
  colored names, numeric and sentinel values, warning/no-warning and basic staff
  output. Prove the overflow fails before and passes after under ASan/UBSan.

The 65,500-byte-name probe reproduces an ASan stack-buffer-overflow in the
actual basic branch at `strcat`; evidence is in `bin/analysis/area-before.log`.
The permanent expanded regression and response repair pass at `2a0b335e3`;
the committed before/after check reports 2/2 catches.

The original reported zone/catalog attribution is skipped below; this concrete
review finding is fixed and qualified.

### 4. Correct #74's Seadog help — P2, LR-08

- [x] Resolve the
  [Seadog beneficiary mismatch](https://github.com/LuminariMUD/Duris/pull/74#discussion_r4268461600).
  `order_speed()` / `look_ship()` use the panel actor, while the activity tick
  uses `captain_is_aboard(ship)`, the aboard owner. The current help incorrectly
  promises a stable bonus to any sailor at the helm.
- [x] Make the smallest accurate help correction in `lib/information/help_index`:
  explain who supplies the persistent speed bonus and the panel/tick limitation;
  keep the passive talent, availability and cargo-sale benefit accurate. Changing
  ship mechanics needs a separate explicit behavior decision.
- [x] Check owner/non-owner Seadog behavior against order/display/tick and verify
  the corrected topic through the existing flat-file help renderer and disposable
  MariaDB import/cache/player-help journey. Retain Web Spray and Quickstep coverage.

### 5. Qualify the review stack

- [x] Update #74 and [#75](https://github.com/LuminariMUD/Duris/pull/75) onto their
  reconciled parents. Preserve #75's physical-death continuation, healing posture
  and graph-distance repairs, scheduler guards, resource cleanup and connection
  qualification. Recheck reviews at the resulting heads and resolve real findings.
- [x] Run focused award/potion/task-recovery, artifact/guild reward/history,
  diagnostic/logging, boon/training, area/help and lifecycle checks for the
  changed paths. Use actual gameplay/persistence journeys where the acceptance
  requires them, retaining the full #58 reward/restart matrix.
- [x] Qualify the final coherent behavior batch once on stable source:
  `make -C src`, `./scripts/format.sh --all --check`,
  `make test-all -j16 TEST_JOBS=16`, and `make test-db`. Rebuild pfile/migration
  tools when shared inputs change. Use `scripts/check_tests_catch.sh BASE HEAD`
  for defect regressions and the applicable checks in [TESTING.md](../guides/TESTING.md).
  For documentation, run `python3 tests/async/test_documentation_contract.py`
  and `npm test --prefix site`; reinstall site dependencies only when needed.
  Reuse valid unchanged evidence; diagnose failures and rerun affected cases
  rather than repeatedly running already-green gates. Do not wait for CI as a
  substitute for local proof or bypass review/branch protection.
- [x] Record exact qualified commits, commands, results and limitations in
  [REGRESSIONS.md](../testing/REGRESSIONS.md) and the archive. Update PR bodies
  and #56/#58 status; all six #58 implementation acceptance boxes are checked.
  Do not label the combined release complete from older branch results.

Use isolated worlds/databases and retain evidence in ignored `bin/analysis/`.
Another worktree may be testing the shared dev game. These tasks do not advance
that separate [#52 character-mechanics plan](class-anchor.md) or
[#57 PSP/movement defects](https://github.com/LuminariMUD/Duris/issues/57).

## Next session: release preparation, when requested

No further implementation session is queued for the completed delivery. The
next step is an explicitly requested production release preparation using the
[runbook](../operations/RUNBOOK.md), followed by the owner's in-game reboot and
post-release checks below. Start by checking current master and the actual
production state; this merge does not establish deployment. This session stops
at the repository handoff.

The updated handoff passes `python3 tests/async/test_documentation_contract.py`
(14 checks) and `npm test --prefix site` (15 tests). Landing evidence is retained
in `bin/analysis/landing/`; source qualification remains in
`bin/analysis/review-final/`.

## Conditional release and historical repair

These operations are still unfinished and require their specific owner
authorization; listing them here does not authorize production changes.

- [x] Land **#70 → #73 → #74 → #75** by authorized squash merges, preserving
  each child's tested tree and updating the final handoff with #75. Keep skipped
  items explicitly deferred when reconciling issue closure.

- [ ] For an authorized release, prepare the integrated binary/world/configuration
  and help publication through the [runbook](../operations/RUNBOOK.md). Preserve
  the deployed artifacts and stop/drain the old writer before changing the reward
  behavior. Qualify rollback with retained payload/result/state versions; do not
  assume an old binary can read new pending records or allow concurrent versions
  of the writer. The owner performs the production reboot.
- [ ] Verify the actual loaded build and published help, then observe uncapped
  boon/PvP artifact and guild rewards, settled saves/history, training HP and
  restart behavior. Verify statistics SQL/file agreement through a same-day
  restart and midnight. Local qualification does not establish production rollout.
- [ ] **LR-01 historical file repair, only if specifically requested:** refresh
  the private 76-row proposal, original-file hash, SQL sample identities and UTC
  mapping before replacement. Preserve the original; refuse changed/already-fixed
  input; verify the proposed 1,007 → 1,083 rows and per-counter agreement after
  application. Do not fabricate scheduler IDs. See the
  [retained assessment](log-server-review.md#lr-01--restart-safe-statistics-output-medium-56-2).
  #58's existing assessment proposes no compensation; any later adjustment needs
  attributable loss evidence and separate specific authorization.

## Skipped for now — owner decision

**We are skipping the following work for now.** These are unresolved/deferred,
not fixed, and are excluded from the active queue above. Resume them only when
the owner requests it. The decisions were made on 2026-10-14, except `skeer`
on 2026-10-13. Full requirements and evidence remain in [log-server-review.md](log-server-review.md).

| Item | Work we are skipping for now |
| --- | --- |
| LR-06 — original zone attribution | Identify the reported room/zone and verify its catalog population. The response-overflow repair above is delivered by #74. |
| LR-07 — movement report | Recover the player's race/class, posture, terrain, load, effects, resources, actions and timing; reproduce drain/regen or establish a supported explanation. Keep correlation with #57 distinct. |
| LR-08 — `skeer` | Identify the intended ability/topic before adding help; no meaning has been established. The Seadog correction above is delivered by #74. |
| LR-09/LR-10 — historical attribution | Identify the exact original dead-NPC scheduling and standing/resting producer sequences. The demonstrated #75 producer repairs are delivered. |
| LR-12 — host log rotation | Obtain protected diagnostics, identify the failed rule/hook and verify a successful scheduled/authorized rotation with correct ownership and live writers. |
| LR-13 — off-host replica | Obtain an approved remote destination; provision the supported mount/permissions/retention and prove publication, checksum/readback and failure/recovery. `replica_root` was null. |
| LR-14 — restore qualification | Provision a separate isolated filesystem, enable the drill policy, restore a verified generation including a replica, observe receipt/readiness/cleanup and record recovery time/point. Drills were disabled. |
| LR-15 — failure alerts | Diagnose sendmail exit 100 using protected mail evidence; verify actual OnFailure delivery/recipient receipt and success-only quiet-period stamping. No test alert is authorized by this plan. |
| LR-16 — tunnel impact | Correlate recovered connection IDs/timestamps with contemporaneous external health and client disconnects; establish impact or a supported monitoring-only disposition. |
| LR-17 — exact lookup attribution | Recover the original lookup mode/query and concurrent load for live command/callback correlation. Representative native profiling and the decision not to retain an unproven optimization are archived. |
| LR-18 — original pathfinding reports | Recover caller/source/target rooms for the 22 room-budget and 15 distance-limit exits. The demonstrated #75 maximum-distance repair is delivered. |
| LR-19 — public health monitor | Identify the intended public URL, client/method/headers and network location; verify healthy/unhealthy behavior and resolve urllib 403/1010 versus curl without unsupported rule changes. |
| LR-20 — protected host audit | Review system/kernel/auth/mail/Fail2Ban/Plesk/web-server/host-database logs, including rotations and retention gaps, for 2026-10-12 22:25:09–2026-10-13 05:25:09 UTC. Missing access is not a clean result. |
