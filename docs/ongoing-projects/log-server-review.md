# Log review and ESTALE: notes and history

The current unfinished work is in [plan-log_review.md](plan-log_review.md).
This file preserves the completed work, acceptance contracts, evidence, decisions,
and earlier plans. The recorded snapshot below is historical: its completion
claims and execution instructions do not define the current work queue.

The snapshot predates reconciliation with merged PRs
[#69](https://github.com/LuminariMUD/Duris/pull/69),
[#72](https://github.com/LuminariMUD/Duris/pull/72) and
[#76](https://github.com/LuminariMUD/Duris/pull/76), and does not resolve the two
[#74 review findings](https://github.com/LuminariMUD/Duris/pull/74#pullrequestreview-5515105547).
Its successful checks qualify the recorded branch revisions, not the combined
release on current master. Follow the current plan for those unfinished tasks
and the owner's skipped items.

## Current-master integration — qualified 2026-10-14

The requested repository delivery is ready for review in the unmerged stack
#70 → #73 → #74 → #75. Parent checkpoints are `2ec958e83`, `5e75d025a` and
`2a0b335e3`; combined merge `42b7afb17` includes master `67ca142ff`. Observer
cleanup `d4fe27272` changes only the test and documentation; runtime/world/schema
sources match the qualified merge. Later handoff commits are documentation only.
The [current handoff](plan-log_review.md) retains conditional and skipped work.

Final combined proof: server and pfile builds; maintained migration tools
(including a forced rebuild); all 1052 tracked C/C++ files formatted; **736/736
regressions** in 567.56 seconds; **77/77 disposable database legs** in one
710-second run; **14 documentation checks** and **15 site tests**. All six actual
artifact/guild variants pass: Summon Ghasts/boons with copyover/restart, three
crash boundaries, blocked shutdown and PvP/restart. The native and SQL matrix
retains caps, eligibility, multiple guild participants, state ordering/reload,
retries, identity/replay, v1 receipts/outbox and named failures. Current v2 history
has no SQL gameplay veto. Payout data and override policy remain unchanged.

All-level boon failure/success, Human Warrior/Illithid Psionicist training,
HP/GMCP/save/restart, bounded area responses and flat-file/MariaDB player help
pass. Seadog mechanics are unchanged; the native owner/non-owner probe and source
trace establish the help's actual beneficiary and panel limitation.
The original zone attribution and other owner-skipped items remain deferred.

Before/after: `scripts/check_tests_catch.sh 2ec958e83 5e75d025a` reports 2/4;
the native award/teacher tests catch defects while its two database journeys skip
without settings and need the separate real disposable evidence.
`scripts/check_tests_catch.sh b89150407 2a0b335e3` reports 2/2. Direct ASan and
help-render checks establish the intended failures rather than incidental last
log lines. The unchanged lifecycle repairs retain their original 3/3 proof.
The observer-cleanup probe reproduces local socket closure before observation;
the corrected actual-server journey passes 2,001 attempts with both genuine
handshake expiries, reconnect, bounded resources/logs and no pulse overrun.

Exact commands, fixture limits and the test-only qualification exception are in
[REGRESSIONS.md](../testing/REGRESSIONS.md). Evidence is retained under
`bin/analysis/integrated/` and the isolated integration worktree's
`bin/analysis/integration/`. All review findings are resolved, PRs and #56/#58
are synchronized, and no production rollout or historical repair was performed.

Former document title: **Log review: implementation and follow-up plan**.

Issues: [#56](https://github.com/LuminariMUD/Duris/issues/56) and
[#58](https://github.com/LuminariMUD/Duris/issues/58).

## Execution plan — deadline correction, 2026-10-14

**Agreed delivery scope is complete.** The final repository bundle is
[PR #75](https://github.com/LuminariMUD/Duris/pull/75), stacked on #74. All 736
regressions pass in 869.90 seconds and all 77 isolated database checks pass in
one 775-second run, including every artifact/reward scenario. Build, full-tree
formatting, 12 documentation checks and 15 site checks pass. Three defect
regressions fail before and pass after. The owner skipped unmatched historical
investigations and host work for this delivery; those are recorded as deferred,
not fixed. No production action or shared-dev test occurred.

Integration order is #70 → #73 → #74 → #75. The reviews remain unmerged; rollout
and historical file replacement require their existing separate authorization.
LR-01's implementation is already merged in #66. Evidence for this final bundle
is retained under `bin/analysis/lifecycle/`, including the full database logs.

**LR-02–LR-05 are locally qualified in [PR #73](https://github.com/LuminariMUD/Duris/pull/73).**
The LR-06 display fix and LR-08 help coverage are now locally qualified in
[PR #74](https://github.com/LuminariMUD/Duris/pull/74), ready and stacked on #73.
All 734 regressions pass in 593.65 seconds; all 77 database checks pass in one
743-second run. The before/after script reports 2/2 catches. A separate native
lookup using the base help data fails specifically at the missing Web Spray
entry and passes with the new data, removing ambiguity from the script's final
runtime-warning line. Original zone attribution remains open.

**Final delivery:** the remaining confirmed repository repairs were bundled,
using focused proof and valid completed results, then one final set of required
gates. This follows the owner's 2026-10-14 deadline correction. No per-item
full-suite loop or additional hardening pass was added. Accepted scope changes
and all evidence/access gaps are explicit.

**Owner scope correction, 2026-10-14:** skip the requested privileged host
diagnostics, replica destination and restore filesystem work. LR-12–LR-15 and
LR-20 are deferred by that decision and leave the active delivery scope. Their
requirements and read-only findings remain below; none is represented as fixed
or verified. Do not request those inputs again or perform production operations.

The owner also answered “Skip them for now” to the unmatched historical reports:
LR-06 original zone/catalog attribution, LR-07 movement conditions, original
LR-09/LR-10 combat/posture sequences, LR-16 tunnel impact, LR-17 exact query/load,
LR-18 original pathfinding caller and LR-19 public-monitor details. Their missing
evidence stays explicit in the retained requirements. Confirmed producer/range
repairs and the measured connection/lookup dispositions below remain delivered;
no historical-attribution claim is implied by their passing tests.

The qualified bundle is on `fix/56-runtime-review`, above #74. `d1c30d284`
stops physical-damage continuation after either participant dies. Focused native
proof also reproduces and repairs healing into standing/resting, and accepting
a target one room beyond `how_close()`'s maximum distance. The connection journey
now measures 2,001 sequential plain/TLS/WebSocket attempts, actual incomplete
handshake expiry, authenticated responses and reconnect. Its focused run passes
with no 250 ms pulse overrun. The final broad gates also pass, with source and
tests unchanged from `7ab77e895`; the final documentation records qualification.


**Execution checkpoint, 2026-10-14.** The gameplay implementation is `4a202c2fb`
above LR-02's `55248b7ad`; `9551e64bb` repairs a confirmed fixture failure.
All 733 regressions pass in 703.11 seconds. The full database run passes 76/77
and its five non-PvP artifact variants; PvP failed before summon completion due
to lost concentration. Bounded retries now handle only confirmed aborted casts,
and the affected PvP reward/restart rerun passes. Thus all 77 distinct database
checks pass in aggregate; the original `make test-db` invocation exited nonzero.
The helper's controlled-response probe covers immediate success, two aborts
then success, and exhaustion at five attempts. It is fixture-boundary proof;
the real PvP journey supplies gameplay/persistence proof. Server source is
unchanged from the passing regression gate. No full green gate was repeated.

The next batch was prepared separately on `fix/56-zone-help` at `baf93f70a`, in
`bin/analysis/zone-help-worktree/`, while the #73 checkout was frozen. It is now
`884f1ceba` on `fix/56-zone-help-review`, above #73's `c404fc159`, in the main
worktree. Focused evidence has been copied to `bin/analysis/zone-help/`. Native
area display fails before and passes after; flat-file help and actual player
help queries after disposable MariaDB import/cache refresh pass. It retains the
existing Quick Step title and uses ordinary searchable topics; no importer or
redirect framework is added. The main server build, full-tree formatting and final broad gates pass; #74
is ready for review. Original zone attribution remains open.

Evidence: `bin/analysis/epic-training/` (including the preserved full database
logs and PvP rerun), and the next worktree's `bin/analysis/zone-help/`.

This section controls execution. The detailed requirements and evidence below
remain in this file for lookup. Earlier work orders, pause/resume checklists and
imperative wording inside completed items are historical, not a second queue.
This revision changes the plan only; existing implementation edits are preserved.

**Outcome:** reviewable fixes and an evidence-backed disposition for every LR/ES
item. **Non-goals:** new frameworks, general cleanup, speculative hardening,
rebalancing unproven reports, or reopening satisfied acceptance cases.
**Files:** the remaining repairs use `src/combat/fight.c`, `src/world/graph.c`,
the existing posture/connection journeys and focused native checks in
`tests/async/`. **Proof:** the focused results and final required batch gates
are recorded below; none remains to run for this delivery.

### 1. Delivered gameplay batch

The sequence below is retained as the delivery record for #73. Its local
qualification is complete; continue with stage 2 rather than replaying it.

1. Preserve PR #70 at `466414226` and LR-01's merged PR #66. Their work is already
   qualified. Do not replay their implementation plans or separately rerun their
   fault matrices without a relevant change or new failing evidence.
2. On `fix/56-log-review-followups`, commit the existing teacher fix, fixtures,
   database registration and accompanying documentation. LR-02 is already committed
   at `55248b7ad`. LR-03's level 30 was selected in PR #55. Native teacher tests,
   the full Human/Illithid purchase/restart journey, build and formatting already
   pass. No additional teacher feature or test framework is needed.
3. Run `scripts/check_tests_catch.sh 55248b7ad HEAD` for the teacher commit range.
   Reuse LR-02's completed before/after check. The database journey skips without
   explicit disposable DB settings; report that limitation and use its retained
   real before/after journey evidence, not a skipped run, as proof.
4. Run the remaining final gates once on the frozen batch. Fix actual failures,
   rerun the affected checks, then publish the ready PR immediately. Do not add
   LR-06–LR-20 while this batch is being qualified.
5. While #70 is unmerged, base the follow-up PR on `fix/58-artifact-guild-memory`
   so its diff contains only the follow-ups. After #70 lands, reconcile the base
   with master. Keep published history and other worktrees intact. Leave the PRs
   unmerged; reference the completed LR items without closing all of #56.

PR #69 still proposes removing the epic gain gate. Recheck it once before this
batch is finalized. Follow the current selected policy; if it lands, reconcile
LR-02 and its tests in the same batch. Do not wait indefinitely for that proposal
or implement both policies.

### 2. Delivered zone/help batch

The display/content implementation and its qualification are delivered in #74.
Preserve those results; original zone attribution is the only open LR-06 leg.

### 3. Resolve investigations from concrete evidence

The bounded triage and confirmed repairs below are complete. The owner skipped
unmatched historical evidence for this delivery; the following method is kept
for a later requested investigation, not an active queue.

Start with LR-09–LR-11, then LR-07 and LR-16–LR-19. For each report, make one
bounded first pass through the original evidence, its actual caller/path and the
closest existing executable check. Budget 15 minutes for that initial triage,
then choose the next action from evidence: fix a demonstrated defect, record a
supported expected-behavior result, or name the precise missing evidence/access
and continue an independent item. The timebox is a scheduling checkpoint, not
permission to call an unverified report fixed or abandon a confirmed defect.

A reproduced defect gets the smallest repair and the proof its acceptance needs.
Batch related repairs before final gates. A missing player condition or host
log stays open with its next action; it does not hold already-qualified PRs.
Do not build a new stress rig, monitoring service or general test framework when
an existing harness, bounded measurement or actual command journey can answer it.

### 4. Host work deferred by the owner

The owner answered “skip this” to the request for privileged diagnostics,
approved replica destination and isolated restore filesystem. LR-12–LR-15 and
LR-20 are now deferred, with no new access request or operational action due in
this delivery. Read-only inspection found rotation still failed, both alert
instances failed with exit 100, `replica_root=null` and `drill_seconds=0`. The
installed alert script already stamps its quiet period only after sendmail
succeeds; the protected mail logs needed for diagnosis are unavailable. Preserve
these gaps and requirements for a separately requested follow-up. Historical
recovery and rollout still require their existing specific authorization.

All LR-01–LR-20 and ES-01–ES-05 requirements remain in the detailed sections
below. LR-01's assessed 76-row recovery proposal stays private and unapplied;
#58's historical assessment proposes no compensation. `skeer` remains excluded
by the owner's decision. Unavailable report attribution, access or evidence
stays explicitly open and does not delay an independently qualified PR.

### Verification and delivery rules

- During implementation, run the smallest relevant existing check. Extend a
  fixture only for an unmet behavior/acceptance case; completed coverage needs no
  second fixture. Reuse valid results for unchanged code and dependencies.
- At the end of each ready behavior batch, follow `TESTING.md`: build after C++
  changes, then `./scripts/format.sh --all --check`,
  `make test-all -j16 TEST_JOBS=16`, and `make test-db`. Run them once, in order,
  on stable source. These required gates are retained; there is no additional
  burn-in, per-item full-suite loop, or requirement to wait for CI.
- A failing gate warrants diagnosis and affected reruns. Broaden/repeat only
  when the repair, dependency change or unresolved failure requires it. Record
  aggregate versus single-run results honestly, as in #58's qualification.
- For documentation/content changes, run applicable link/parser/import/site
  checks. Use the already-installed matching site dependencies; repeat `npm ci`
  when they change or are absent. Do not rebuild the server for this plan edit.
- Network/authentication and backup/restore changes retain their conditional
  security and isolated integration checks from `TESTING.md`. Do not run those
  unrelated jobs for the epic feedback batch. Rebuild pfile/migration tools only
  when their shared inputs change.
- Record commit, proof and any real limitation once in the relevant entry;
  summarize it in the PR and synchronize issue status. Preserve ignored evidence
  in `bin/analysis/`; missing temporary logs alone do not require repeating an
  already-observed successful test. Use isolated worlds/databases; another
  worktree may be testing the shared dev game.
- A ready PR is a delivery milestone. Overall completion still requires every
  retained acceptance criterion or explicitly supported disposition. Keep
  unavailable evidence and owner actions open; do not silently drop them.

**Ablation applied:** removed completed LR-01/#58 work from the execution queue,
replaced overlapping resume checklists with this single order, removed repeated
proof and speculative infrastructure, and stopped unrelated investigations/host
work from delaying a qualified batch. Existing safety, gameplay, persistence and
acceptance requirements remain. No gameplay implementation was changed by this edit.

## Detailed requirements and evidence

Use these sections for the exact contracts, source paths, commands and retained
results. Completed implementation recipes and historical checkpoints explain the
work already done. The execution plan above determines what to do next.

## Statistics

### LR-01 — Restart-safe statistics output (medium; #56 §2)

- [x] Write each logical sample exactly once to SQL and its daily file across
  retries/restarts; separately assess recovery of the 76 missing file samples.

**Execution, 2026-10-13.** The scheduler now allocates random 64-bit identities
outside the legacy low-byte namespace; its existing v4 state records them before
effects. No layout change, second queue, or database schema is needed. Retries
retain the entire capture; only cursor continuation prepares new values. Queue
delay and durable-state sync no longer consume the repository execution deadline.
The file append repairs only a matching partial row, checks the complete row on
replay, and retries syncs. State rename and daily-file creation both sync their
containing directory.
See the [runtime/recovery contract](../operations/CONFIGURATION.md) and
[regression evidence](../testing/REGRESSIONS.md#statistics-across-restarts-and-interrupted-output).

Passed focused commands: `python3 tests/async/test_maintenance_scheduler.py` and
`tests/async/with_disposable_mariadb.sh bash tests/async/run_statistics_mysql.sh`.
The latter is registered in `tests/run_db_tests.sh`; it checks SQL/file agreement,
all injected fault/restart cases, and actual legacy IDs in v2/v3/v4 state.
The scheduler test fails before the fix on changed captured values.
The server build and full-tree format check passed. The first broad regression
run passed 725/727: its wrapper-permission failure is repaired, and its flight
journey had completed gameplay before failing to count archived boot logs.
`81b8350e1` separately fixes that evidence collector. The final
`make test-all -j16 TEST_JOBS=16` passed all 727 checks in 700.33 seconds, including
flight evidence collection. `scripts/check_tests_catch.sh 81b8350e1 1e735655e`
confirms the scheduler regression passes after and fails before the repair.
The slow-state-sync regression also failed before the deadline adjustment and
passes after it. Output conflicts are refused with `EILSEQ`; first retry and
terminal failures log the opaque work ID and error. All 15 site tests pass.
`make test-db` passed all 75 isolated database checks in 459 seconds, including
the statistics matrix and MariaDB flight journey. LR-01 implementation is
`1e735655e`; `81b8350e1` is the separate flight-test correction. Validation logs
are retained under the ignored, owner-only `bin/analysis/lr01-validation/`
directory. No production rollout or historical replacement has been performed.
Source integration: [PR #66](https://github.com/LuminariMUD/Duris/pull/66),
squash-merged as `8c3f7384a` after the original qualification.

**Historical assessment, 2026-10-13 16:47 UTC.** A bounded read-only production
transaction and a private copy of the original daily file confirm 1,007 existing
rows, all before hour 22, and all 76 reported SQL samples still present (28 in
hour 22 and 48 in hour 23). Both source timezone and proposed output mapping are
UTC. The private dry run under `bin/analysis/lr01-recovery/` retains `original`,
`proposed`, `samples.json` (SQL primary keys, timestamps and all counters), and
`assessment.json` (collection time and hashes), with owner-only permissions.
The proposal preserves the original bytes and adds 76 legacy-format rows,
bringing the total to 1,083. It invents no scheduler IDs: SQL primary keys identify
the source samples, and the existing file consumer accepts rows without a work
ID. An exact original-file hash is the application precondition; a changed or
already-repaired file must be refused rather than appended again. Scheduler IDs
cannot be reconstructed from SQL. This assesses only the reported interval,
not other possible historical gaps. No production file or table was changed;
replacement requires separate specific authorization and the retained original.

**Evidence and files.** The review found 76 SQL samples from 22:25:20–23:59:11
missing from the October 12 file, with all extrapolated work IDs already in that
file's last 8 KiB. Before the fix,
[maintenance_scheduler.c](../../src/persistence/maintenance_scheduler.c)
derived IDs as `(scheduled_tick << 8) | (job_id + 1)`.
The instance seed in [comm.c](../../src/net/comm.c) comes from listener ports,
so it does not supply a boot identity. The file check in
[maintenance_repository.c](../../src/persistence/maintenance_repository.c)
used only the work ID; SQL uses the latest high/low timer marker. Capture lives
in [maintenance_snapshot.c](../../src/persistence/maintenance_snapshot.c).

**Original implementation sequence (completed; evidence above).**

1. Reproduce two same-day boots with the same ports/tick schedule and distinct
   sample payloads, including the old IDs in the file tail. Exercise the actual
   scheduler, SQL marker, and file append path in disposable storage.
2. Replace tick-only identity with a restart-safe identity allocated once per
   new work item and persisted before effects. Reuse the scheduler's durable
   request/state path. Select and document the smallest allocation scheme that
   distinguishes new work from replay and cannot reuse legacy IDs under the
   supported restart/state-recovery contract. Increasing the tail scan or
   inventing a fresh ID on retry does not solve that contract.
3. Keep the captured timestamp and all 11 counters unchanged for the lifetime
   of a sample. Before the fix, `apply_completion_locked()` cleared the durable
   request, while `submit_due_locked()` invoked preparation again. A file failure
   after SQL commit must not retry the same ID with newly
   captured counters or a new date. This is an additional source-derived risk
   to reproduce, not a claimed observation from the production window.
4. Preserve acknowledged/pending completion recovery, cursor continuation,
   bounded worker execution, and the other maintenance jobs' marker semantics.
   If the durable layout changes, support the existing v2/v3/v4 state files and
   test the upgrade with pending requests/completions. Define handling of missing
   or invalid state explicitly. Keep SQL/file work off the game loop and preserve
   the daily file's consumer-facing columns and local-time date/hour convention.
5. After the fix is proven, compare a private copy of the affected daily file
   with the bounded SQL interval. Produce a dry-run recovery proposal with the
   missing rows, timestamp/timezone mapping, deduplication rule, and before/after
   totals. The current SQL insertion stores counters/date, not each work ID:
   establish recoverable identity instead of fabricating historical IDs. Retain
   the original file and require specific authorization before production
   replacement. Record a justified unrecoverable/ambiguous disposition if exact
   reconstruction is impossible.

**Verification.** Extend
[test_maintenance_scheduler.py](../../tests/async/test_maintenance_scheduler.py)
and add a focused statistics repository test using the existing disposable
MariaDB wrapper, registered in [tests/run_db_tests.sh](../../tests/run_db_tests.sh).
Cover fresh same-day boots; two distinct samples with identical counts; failure
before SQL commit; SQL commit followed by failed/partial file output; failure
after file append but before acknowledgement; repeated retry; restart with a
pending request/completion; and retry across local midnight. Compare per-sample
values and multiplicity, not just total counts. Test legacy file/state inputs
and ensure no new sample is lost and no replay produces an extra SQL/file row.
The existing scheduler harness alone does not prove cross-store agreement.

## Gameplay and help

### LR-02 — Epic boon eligibility feedback (medium; #56 §3)

- [x] Show accurate completion/reward feedback below and at the epic gain gate.

**Implementation, 2026-10-14.** The publisher now explains that no epic points
were awarded below the configured gain level, using the existing eligibility
helper and minimum. Completion stays consumed; eligible rewards retain their
existing feedback and non-epic rewards bypass this explanation.

The extended `test_epic_level_gate.py` executes the real boon completion handler,
publisher, epic preparation/publication and balance transaction at 49/50/51 and
an overridden 54/55/56 boundary. It checks feedback, balance/revision, consumed
completion, one artifact publication and non-epic EXP; replay after becoming
eligible grants nothing again. It fails before at the missing explanation and
passes after under ASan/UBSan. SQL outcomes and unrelated bonus/reward services
are fixture boundaries. The server build and final follow-up batch gates pass as recorded above. Commit: `55248b7ad`. `scripts/check_tests_catch.sh 466414226 55248b7ad`
reported 1/1 passing after and failing before. The original `/tmp/duris-lr02-*`
logs were temporary and are no longer available; new evidence is retained under
ignored `bin/analysis/`.

[PR #69](https://github.com/LuminariMUD/Duris/pull/69) separately proposes removing
the epic gain gate. It is open and unmerged; this fix follows the currently
shipped level-50 rule and the approved plan. If that policy change lands, reconcile
this feedback and its gate tests with it instead of retaining calls to removed helpers.

[boon.c](../../src/economy/boon.c), `boon_publish_transaction_result()`, announces
completion before `gain_epic()` can decline a below-level award.
[epic.c](../../src/world/epic.c) already provides `epic_level_can_gain()` and
`epic_gain_min_level()`; the checked-in minimum is 50. Reuse those rules to explain
why a completed epic boon awarded no epics. Preserve boon completion semantics,
non-epic rewards, and the existing successful-award feedback; do not lower the
gate, reopen a consumed boon, or claim a persistence failure.

Extend [test_epic_level_gate.py](https://github.com/LuminariMUD/Duris/blob/55248b7ad/tests/async/test_epic_level_gate.py) with
the actual publication/award path, supplementing its helper/source checks.
At levels 49/50 and an overridden configured boundary, assert message, epic
balance, and completion state together. Cover a declined award without a false
success message and ensure the change adds no second reward application.

Batch review and final gate evidence: [PR #73](https://github.com/LuminariMUD/Duris/pull/73)
and the execution checkpoint at the top. Local qualification is not production rollout.

### LR-03 — Epic training minimum (medium; policy decision; #56 §3)

- [x] Record the game owner's intended minimum, then align configuration, help,
  and teacher boundary behavior.

**Focused qualification passed, 2026-10-14.**
`python3 tests/async/test_epic_training.py` runs the actual teacher, purchase
callback and epic transaction under ASan/UBSan. The 29/30/31 and configured
39/40/41 boundaries pass, with unchanged class/prerequisite/cost/cap refusals.
The full-server MariaDB journey uses teacher 80862 and synthetic accounts in a
private world and disposable database; it does not use the shared dev instance.
At 29 training refuses without changing balances or skill; at 30 and 31 the
actual command charges once and saves the learned/taught values. The imported
`Epic skills` help already states level 30, matching the property and default.

[PR #55](https://github.com/LuminariMUD/Duris/pull/55) selects
`epic.skills.minLevel=30.000` in [duris.properties](../../lib/duris.properties),
read by `epic_skills_min_level()` and enforced by `epic_teacher()` in
[epic_skills.c](../../src/classes/epic_skills.c). Refusal below 30 follows that
rule. The property, compiled default, [Ship Damage Control reference](../reference/SHIP_GAMEPLAY.md#ship-damage-control),
and [CODEBASE.md](../reference/CODEBASE.md#epic-point-and-epic-skill-levels) now
agree. Epic point gain remains separately gated at level 50. The teacher-command
journey below remains the focused follow-up for this plan.

Prove teacher behavior at minimum minus one, minimum, and minimum plus one with
otherwise eligible characters and sufficient funds. Refusal must spend nothing;
successful training must retain its class/prerequisite/cost checks. Extend the
level-gate test and run an actual teacher-command journey. Keep epic gain and
epic training thresholds independently configurable.

### LR-04 — Mastery completion feedback (low; #56 §3)

- [x] Distinguish an intermediate improvement, the purchase reaching full
  mastery, and an attempt after mastery.

**Implementation, 2026-10-14.** The existing purchase callback selects feedback
from the resulting learned value. Native checks prove 80→90 improvement,
95→100 mastery, and a no-charge repeat at 100. The unchanged source compiled
and failed at the missing mastery message; the fix passes. Prices, increments,
eligibility and teacher caps are unchanged.

The change is in `epic_skill_purchase_committed()` in
[epic_skills.c](../../src/classes/epic_skills.c) using its resulting learned value.
It previously used the same improvement message at every value, including 100.
Do not change the increment, cost, teacher cap, or purchase eligibility.

Extend or add a focused native teacher/purchase-callback harness: intermediate
gain, final gain capped at 100, already-mastered attempt, teacher-specific cap,
and refused purchase. Assert learned/taught values, one charge, and the correct
message; a repeat at mastery must change neither balance nor skill. Existing
[test_epic_skill_grant.py](../../tests/async/test_epic_skill_grant.py) checks
Chaos grants, so it is not proof of the ordinary paid-training path.

### LR-05 — Toughness HP refresh (medium; needs reproduction; #56 §3)

- [x] Establish when training updates derived HP and correct the successful
  purchase path if the reported delay is reproduced.

**Reproduced, fixed and focused qualification passed, 2026-10-14.**
The actual level-30 teacher charged 150 epics and 1,000,000 copper and saved
Toughness 10, but HP remained 233/263 instead of 243/273. Evidence is retained in
`bin/analysis/epic-training/failure-1791937911284822201/evidence.json`.
The purchase callback now uses `affect_total()` after learning and publishes
GMCP vitals before saving. This reuses the existing rebuild and missing-HP
semantics, including the separate Illithid formula; no new refresh mechanism or
direct HP arithmetic is introduced. The native test proves refresh before save
and vitals publication, and the server build passes. Cash, save, refresh and
client output are adapters in that native fixture; the full-server journey
checks their real behavior. Logs are retained under `bin/analysis/epic-training/`.

`tests/async/with_disposable_mariadb.sh python3
tests/async/test_mysql_epic_training_journey.py` passes and is registered in
`tests/run_db_tests.sh`. It proves full/injured Human Warrior (+10 HP per ten
Toughness) and Illithid Psionicist (+5) purchases, immediate score/prompt and GMCP
agreement, unchanged missing HP, later-pulse stability, two repeated scheduled
refreshes per purchase, refusal below the level and at mastery, and both clean
restart round trips. The 95→100 final purchase adds only its remaining five HP
for the Warrior. `journey.json` retains the binary hash and before/after values.
The initial post-fix journey passed the Human cases, then exposed a fixture
setup error: Limbo's safe flag was restored at restart and removed the loaded
teacher. Reapplying the test room setup fixed the fixture; the complete rerun
passes. No additional gameplay rule was changed.

The original callback changed learned/taught values and saved without an
explicit HP refresh. In [affects.c](../../src/magic/affects.c),
`calculate_hitpoints2()` uses toughness, `balance_affects()` schedules a refresh,
and `affect_total()` rebuilds stats while preserving missing HP. Trace this
existing path before choosing the smallest correction. Do not call the HP
formula on top of already-derived values or make training wait for SQL.

Capture skill, epic/cash balances, max/current HP, pending refresh, prompt/GMCP,
and persisted state before purchase, at callback return, after the next event
pulse, and after reconnect. Cover full and injured characters, repeated
purchases/refreshes, declined purchases, and the Illithid HP branch where
applicable. Require correct derived HP on the next visible result, existing
missing-HP semantics, no cumulative bonus, and reconnect agreement. Use a native
callback test plus a save/load journey; document the observed timing if the
reported delay cannot yet be reproduced.

### LR-06 — Zone average sentinels (low; #56 §3)

- [ ] Identify the reported zone, validate catalog population, and render
  unknown/not-applicable averages without displaying a negative mob level.

**Display fix and focused proof, 2026-10-14.** `884f1ceba` renders -2 as
`unknown` and -1 as `not applicable`, preserves numeric averages, and compares
only real values for the hazard warning. `test_zone_average_display.py` executes
the production basic `do_area()` branch under ASan/UBSan: populated/empty/unknown,
zero, the exact +15/+16 warning boundary, a changed catalog value, and staff
no-argument display pass. The unchanged source compiled and failed on the
negative sentinel. Name padding and the unrelated morph check are adapters;
staff search subcommands are outside this fixture. Catalog loading is unchanged.
The original reported room/zone remains unidentified; its population check
is owner-skipped for this delivery; this display repair alone does not close that attribution.


[db.c](../../src/world/db.c) initializes `avg_mob_level` to -2;
[world_quest_policy.c](../../src/world/world_quest_policy.c) populates averages
and uses -1 for some zones without a usable population;
[actoth.c](../../src/cmd/actoth.c) prints the value directly. Reproduce the
zone-info command for the affected zone and distinguish a missing catalog
update from an intentionally absent average. Correct the population path only
if defective; render each sentinel appropriately without changing stored
sentinels or treating an unknown zone as level zero.

Use fixtures for a populated zone, a normal zone without qualifying mobs, an
uninitialized/special zone, and catalog refresh. Assert command text and that
the hazardous-level warning only compares real averages. Catalog-file validity
alone is not a test of this display.

### LR-07 — Movement drain/regeneration report (low; #56 §3)

- [ ] Reproduce the player's conditions or record a supported explanation;
  correlate any matching defect with #57.

**Bounded triage, 2026-10-14.** The retained chat identifies no race/class,
terrain, effects, resource maxima or timed action sequence. #57 remains open
and explicitly separates its reproduced PSP/over-cap defects from this report;
its neutral-dial movement baseline is 229/tick, with 2,289 gained over 3,000
pulses. That does not identify this player's conditions. No balance change is
justified. The missing input is a repeatable movement/regen sequence with the
conditions listed below; the owner skipped this unmatched report for the current delivery.

Capture race/class/level, posture/status, terrain, carried load, movement mode,
effects, recovery properties, current/max vitality, actions, and elapsed pulses
and wall time. Compare `move_cost()` in [utility.c](../../src/core/utility.c),
`move_regen()` in [limits.c](../../src/world/limits.c), and actual callbacks in
[events.c](../../src/world/events.c), including entering/leaving combat.
The checked-in recovery dial is already neutral (`player.recovery=5.000`);
#57 records the prior dial's effect and the separate reproduced over-cap bug.
Do not undo event optimizations or change balance based only on the chat report.

Reuse [test_move_cost_runtime.py](../../tests/async/test_move_cost_runtime.py)
for cost cases, and add only the missing callback/timed journey coverage for
the reproduced condition. Record predicted versus measured drain and recovery.
If #57 explains the case, link its eventual fix and the matching reproduction;
otherwise retain this report's separate disposition and any needed owner decision.

### LR-08 — Missing help topics/aliases (low; #56 §3)

- [x] Resolve `web-spray`, `quickstep`, and `seadog` searches.

**Content fix and focused proof, 2026-10-14.** `884f1ceba` adds Web Spray with
its hyphen/underscore search forms, a short Quickstep topic pointing to the
unchanged Quick Step page, and passive Seadog help. Actual innate/skill/ship
sources supply their behavior. The importer and parser retain their existing
precedence and metadata; the first new entry gets an explicit separator after
what was the final undelimited entry.

The existing flat-file catalog/runtime test now proves all three searches.
The information-cache journey dry-runs and imports the copied source through the
maintained importer into a disposable schema, then exercises all three through
actual player `help` commands and cached serving. Both focused checks pass. Its
SQL run used #73's server: help behavior is unchanged code, with the new content
in the isolated runtime. The zone code has separate native proof; the rebuilt
server and final gates now pass. [PR #74](https://github.com/LuminariMUD/Duris/pull/74)
is ready for review. Direct base-data lookup proves the missing topic before;
updated data renders all three searches after. Evidence is under
`bin/analysis/zone-help/`. No shared or production import occurred.


Owner decision, 2026-10-13: skip `skeer` for now because its meaning is unknown.
Source/help searches found no matching ability or topic. Do not invent an alias;
this term is excluded from the current implementation, while the three named
topics above remain in scope.

Inspect the real abilities and current titles in
[help_index](../../lib/information/help_index) and
[duris_help_parsed.hlp](../../help/duris_help_parsed.hlp). The latter already
documents `innate web_spray` under Drider and mentions seadog; mentions inside a
page do not make a title searchable. Add the smallest accurate topic or redirect
using [HELP_SYSTEM.md](../content/HELP_SYSTEM.md) and
[HELP_STYLE_GUIDE.md](../content/HELP_STYLE_GUIDE.md). Check importer precedence
so a later source does not overwrite the entry.

Dry-run [import_help_to_prod.sh](../../scripts/import_help_to_prod.sh), then
exercise the selected topics through `wiki_help()` after an isolated import and
cache refresh. Check the flat-file help catalog too when changing shared source
content. Reuse the help parser/import/cache harnesses. Production publication is
a separately authorized import, verified by actual `help` queries.

## Runtime lifecycle and connections

### LR-09 — Scheduling an affect for a dead NPC (low; #56 §4)

- [x] Identify and correct the caller scheduling after extraction; retain the
  scheduler's dead-owner guard.

**Confirmed producer repair, 2026-10-14.** `d1c30d284` makes the legacy physical
`damage()` wrapper stop its caller after any nonzero death outcome, as its spell
branch already does. Previously `DAM_BOTHDEAD` fell through, allowing fighting
setup/counterattack and `cleave()`'s subsequent short-affect request on a dead
NPC. The actual damage/cleave bodies reproduce that request before and stop it
after under ASan/UBSan. Death outcomes and unrelated skill eligibility are
controlled adapters, not a full `raw_damage()` gameplay simulation. The existing
real scheduler/cancellation tests also pass, preserving dead-owner rejection,
extraction cleanup and owner-reuse protection. Formal before/after verification
passes. The original timestamp does not identify the combat caller, so that
specific guard report remains unattributed; this repairs a demonstrated producer
without claiming it was the only possible producer.

The observed `event_short_affect` schedule was rejected, not a proven crash.
Trace `affect_to_char()`/`set_short_affected_by()` in
[affects.c](../../src/magic/affects.c) through the relevant combat/spell caller
and extraction. The rejecting guard is in
[new_events.c](../../src/world/new_events.c). Reproduce death/extraction during
the effect sequence and stop the invalid continuation at its owner, including
any affect/payload cleanup needed there. Add bounded caller diagnostics only if
the existing evidence cannot identify that continuation.

Extend [test_nevent_scheduler_runtime.py](../../tests/async/test_nevent_scheduler_runtime.py)
and [test_nevent_cancellation_runtime.py](../../tests/async/test_nevent_cancellation_runtime.py)
with the real producer sequence: live scheduling works, extraction cancels
owned events, the caller schedules no new work after death, and no callback or
payload survives owner reuse. A test that merely confirms `dead_owner` rejection
does not demonstrate the caller fix.

### LR-10 — Standing/resting inconsistency (low; #56 §4)

- [x] Find the producing transition and keep posture/status consistent while
  preserving `stand` recovery of an already-invalid state.

**Confirmed producer repair, 2026-10-14.** `fe999645f` normalizes standing to
sitting when `update_pos()` calculates resting status. The actual transition is
a humanoid remaining upright at -3 HP/incapacitated, then healing to -2 HP:
before, `calculate_ch_state()` returns resting while the standing posture
survives. The extended existing native posture test fails before and passes
after under ASan/UBSan. A separate native before/after probe also executes
actual `spell_cure_serious()` → a controlled heal adapter → `update_pos()` →
stand/rest, using the legal minimum three-point heal; it fails before and passes
after. It retains prone/kneeling/sitting recovery, normal
standing and intentionally standing sleepers; subsequent stand/rest transitions
and their regen-start/feedback observations pass, including recovery of an
already-invalid state. Random falling is controlled; combat/wake and unrelated
services are adapters. The original player's producing action is still absent
from the retained log, so this does not claim exact historical attribution or
a live timed movement/regen journey.

[actmove.c](../../src/cmd/actmove.c) already normalizes wake posture and recovers
`POS_STANDING+STAT_RESTING`. The log shows the recovery worked; it does not name
the remaining producer. Trace commands, combat/effects, and restore transitions
that write position/status. Reproduce the complete transition before changing
it; preserve intentionally valid standing/sleeping states.

Extend [test_posture_state_regression.py](../../tests/async/test_posture_state_regression.py)
with that actual producer and subsequent rest/wake/stand behavior. Assert both
fields, movement/regen behavior, and recovery feedback. Keep the recovery test;
silencing its diagnostic is not a repair.

### LR-11 — Unauthenticated connection burst (medium; #56 §5)

- [x] Demonstrate bounded connection resources and repeated-error logging while
  legitimate clients can connect and reconnect.

**Measured focused qualification, 2026-10-14.** The extended existing journey
passes 2,001 sequential attempts across plain/TLS/WebSocket listeners over
80.835 seconds (24.75/s). Descriptors start/end at 10, peak at 26; RSS peaks
1,012 KiB above baseline. It uses 9.02 process CPU seconds, emits 2,563 lines /
261,011 bytes and records no pulse above 250 ms. An authenticated account menu
responds throughout (maximum 216.93 ms), then the burst address logs in after
cleanup. Separate held incomplete WebSocket/TLS handshakes expire in 27.16 /
37.54 seconds. The first extended run completed resource measurements but hit
a fixture-only context-manager error before reconnect; it is repaired and the
focused rerun passes. Existing shared-address, proxy, IPv6, website and timeout
cases remain in the same journey for the final gate.

This bounded local stream shows no retained descriptors or observed memory/log
growth needing an admission change. DNS already limits
workers to eight; no new address-rate table is introduced. The fixture caps
peak descriptors, memory and lines/bytes per attempt and checks cleanup; it
does not establish an unlimited-load or hostile-network guarantee. Host audit
correlation is owner-deferred under LR-20. The final regression/database gates
pass, including this full journey and every artifact/reward variant.

The review counted 2,001 pre-character disconnects from one address, with 27
concurrent-limit refusals, TLS failures, and write errors. Inspect admission,
timeouts, cleanup, and logging in [comm.c](../../src/net/comm.c),
[ssl.c](../../src/net/ssl.c), and [websocket.c](../../src/net/websocket.c).
The existing eight-connection limit is concurrent, not a rate limit. Establish
whether repeated sequential attempts still produce excessive CPU, descriptors,
worker state, or logs. Apply the smallest measured admission/logging correction;
any per-address state must itself be bounded and expire.

Extend [test_connection_limit_journey.py](../../tests/async/test_connection_limit_journey.py)
with sustained sequential churn and incomplete TLS/WebSocket handshakes. Record
attempt count/rate/duration, peak descriptors/memory, loop latency, and log
lines/bytes; assert finite limits tied to the chosen controls and state cleanup
after the burst. Verify another client remains usable and reconnect works after
the limit window. Retain shared-address/NAT, trusted-proxy, IPv6-prefix, and
authenticated website-service behavior. Coordinate host-log correlation with
LR-20; the original evidence does not establish compromise.

## Host operations and backups

Use the current [RUNBOOK.md](../operations/RUNBOOK.md) and
[BACKUPS.md](../operations/BACKUPS.md). Recheck deployed units/policy before
acting: historical deployment notes may predate the issue's observations.
Record redacted results on #56, keeping installed credentials and host-specific
configuration out of Git. Repository examples cannot prove a deployed service
works, and this planning task performs no production operations.

**Owner-deferred, 2026-10-14:** LR-12–LR-15 and LR-20 are skipped for this
delivery by the owner's answer to the host access/destination/filesystem request.
Their unchecked boxes indicate absent operational proof, not active work waiting
for another permission request. Rotation still exits 1, alert instances still
exit 100, and the installed policy still has no replica and disables drills.
Protected system/mail diagnostics remain unavailable; no root cause is guessed.

### LR-12 — Failed host log rotation (medium; #56 §6)

- [ ] Have the host owner identify the failed rule/hook and verify a subsequent
  successful `logrotate.service` execution.

The October 13 run failed with exit 1 at 00:57:16–00:57:20 UTC and has a Plesk
drop-in. The owner should inspect the protected journal beginning
`2026-10-13 00:57:00 UTC`, review the effective unit/rules and hook, validate the
correction, then observe the next authorized/scheduled rotation. Record the
specific cause, unit result, and evidence that the intended logs rotated with
correct ownership and services still writing. Resetting the failed flag alone
is insufficient. Do not conflate this host job with Duris's restart-time log
rotation in [cycle_mud.sh](../../scripts/cycle_mud.sh).

### LR-13 — Off-host backup replica (medium; #56 §7)

- [ ] Configure an actual remote replica and prove completed generations can be
  read and verified there.

The reviewed policy had `replica_root=null`. The custodian provisions the
supported SSHFS mount, remote account, host-key verification, permissions,
capacity/retention, and private policy. Reuse
[persistence_backup.py](../../scripts/persistence_backup.py) and
[backup_policy.example.json](../../scripts/backup_policy.example.json).
Verify generation publication and remote checksum/readback, then exercise an
authorized mount failure/recovery: failure remains visible, a local generation
survives, and replication resumes without duplication. Never substitute an
ordinary local folder for a disconnected mount. Record the remote failure
domain, generation ID, and verification result; couple an independent remote
restore to LR-14. Readback alone does not prove recovery after host loss.

### LR-14 — Isolated restore qualification (medium; #56 §7)

- [ ] Provision the restore filesystem, enable the selected drill interval, and
  complete a qualified restore with an observed drill receipt.

The reviewed policy had `drill_seconds=0`. Follow BACKUPS.md using a dedicated
mounted filesystem on a different device from live authority and backup storage,
within the policy's size/free-space limits. Use matching server/schema/verifier
artifacts and independently current erasure evidence; do not manufacture an
empty tombstone ledger or bypass a restore refusal. Run the existing isolated
restore/drill path with private authority and namespace isolation, including a
generation retrieved from the replica once LR-13 is available.

Verify checksum validation, database/flat-file reconciliation as applicable,
isolated readiness and clean shutdown, cleanup, and the recorded generation and
drill time. Observe the enabled timer and `status --require-drill`; that command
alone proves no drill requirement when the interval is still zero. Record
elapsed restore time and recovery-point age. Successful archive CRC/hash checks
from the original review are not restore evidence. No candidate is promoted.

### LR-15 — Backup failure alert delivery (medium; #56 §7)

- [ ] Diagnose exit 100 and prove an end-to-end failure notification reaches
  the responsible recipient, retaining delivery-aware rate limiting.

`OnFailure=` was connected in the review, but alert instances had failed before
the evidence window, on October 12 at 18:54:05. Inspect the deployed
`duris-backup-alert@...` unit, script, sender/recipient configuration, sendmail
exit, and protected mail journal with the owner. The installed alert script is
not one of this checkout's backup service templates; find the real command
before proposing a repository edit. Repair the diagnosed mail/configuration
problem instead of introducing a second alert system.

With explicit permission for the test, trigger a harmless controlled failure
through the real `OnFailure=` route and obtain recipient receipt. Verify failed
submission leaves no quiet-period stamp, a later attempt remains eligible, and
successful submission applies the intended quiet period. Submission success
alone does not establish receipt. Record which backup/health/drill units route
to it, and verify repeated failures do not create an alert storm.

## Monitoring and bounded investigations

### LR-16 — Tunnel interruptions (low; #56 observations)

- [ ] Correlate recovered edge interruptions with external health and client
  disconnect evidence; record impact or a supported monitoring-only disposition.

**Bounded disposition, 2026-10-14.** The original retained review reports ten
individual recoveries in roughly 1–16 seconds, one about 19 seconds; no service
restart or loss of all four tunnel connections was established. The missing
evidence is a contemporaneous public-probe/client-disconnect timeline matched
to those connection IDs, rather than a later successful readiness probe. No
connection or alert change is supported; the owner skipped historical-impact
correlation for this delivery.

The review's ten interruptions recovered; it established no complete tunnel
outage. Compare connection IDs/timestamps with actual public probes and game
disconnects, plus later recurrence. Distinguish one edge reconnect from loss of
all usable connections. Reuse existing monitoring; adjust connection handling
or alerts only for demonstrated impact. Prove any change with the same measured
signals and an agreed observation window, and retain recovery timing in the
disposition even when no code change is justified.

### LR-17 — Lookup latency and event deferrals (low; #56 observations)

- [x] Profile the 73.738 ms staff `lookup` and characterize the event deferrals;
  record a measured improvement or why no change is justified.

**Native measurement, 2026-10-14.** The actual ordinary file-search branch,
`strip_ansi()` and `strToLower()` were compiled at `-O2` with output adapters.
Thirty warm and thirty advised-cold requests per dataset measure the generated
files: mob 17,681 lines (guard), object 19,148 lines (sword), room 253,262 lines /
about 14 MiB (no match), and zone 351 lines (no match). Warm p50/p95 milliseconds
are respectively 14.069/23.235, 7.506/14.397, 51.171/65.601 and 0.053/0.098;
room advised-cold p50/p95 is 100.823/146.935, maximum 159.152. Cold advice applies
only to a copied fixture file and is not a guarantee of physical disk reads.
Raw distributions and fixture/source are under `bin/analysis/lifecycle/lookup/`.

This explains an isolated 73.738 ms lookup as plausible full-file work, with
all measured requests below the 250 ms pulse deadline. Original review windows
cover 100,800 ticks, mean 7.25 ms, maximum 80.744 ms, with four event reports
deferring at most one tick; the command-latency and scheduler/budget harnesses
pass. A small scan shortcut did not show a consistent improvement and was
removed. There is no evidence justifying a new cache/worker subsystem. The
original mode/query and concurrent player load are unavailable, so exact
historical attribution and loaded command/callback correlation remain open;
native timings do not qualify a live staff command under production load.

Use a representative lookup mode/query/data size against `do_lookup()` in
[actwiz.c](../../src/cmd/actwiz.c), with existing
[command_latency.c](../../src/net/command_latency.c) and event diagnostics.
Measure repeated warm/cold requests and loop/callback times under a stated load.
The original four event-budget reports deferred at most one tick and do not
demonstrate sustained stalls. If profiling identifies a reproducible blocking
operation, correct that path while preserving staff permissions/results and
bounded loop work. Reuse the command-latency/event runtime harnesses and compare
before/after distributions; a single faster run is insufficient evidence.

### LR-18 — Pathfinding limits and diagnostics (low; #56 observations)

- [x] Explain the 22 room-budget and 15 distance-limit exits, correcting a
  reproducible false failure or excessive logging if found.

**Boundary repair, 2026-10-14.** `f8e302270` checks maximum distance before
accepting a target. Previously a target at distance four returned success with
maximum three (and an adjacent target succeeded with maximum zero). Actual
`how_close()`, queue/mark functions, structs and edge macros fail before and pass
after under ASan/UBSan. Cases retain exact/below/above, zero/negative distance,
invalid rooms, door eligibility, ocean/NOWHERE exclusions, room-budget exit,
queue cleanup and later reuse. Pool allocation/logging are adapters. The room
budget is unchanged; each tested budget/distance exit emits one diagnostic,
including 37 repeated distance failures without a diagnostic loop. Teleport and
listen callers use the returned sign/distance, so this enforces their declared
range. The original 22/15 diagnostics lack a captured caller/query; expected
bounded exits are demonstrated, but no exact historical false failure or log
amplification is claimed.

Trace the actual caller and source/target rooms into `how_close()` in
[graph.c](../../src/world/graph.c). Confirm edge/room eligibility and intended
distance semantics using small native fixtures at, below, and above the limit,
plus a room-budget exhaustion case. Keep both bounds and queue cleanup; do not
increase/remove them just to hide a diagnostic. Verify caller-visible results
and bounded work, and measure any log-volume change. The spelling clarification
in the review does not establish a relocation/pathfinding bug.

### LR-19 — Public health clients (low; #56 observations)

- [ ] Confirm the intended monitoring clients work through Cloudflare and
  document the urllib 403/1010 versus successful curl result.

**Bounded inspection, 2026-10-14.** The maintained `healthcheck.sh` uses curl
with a three-second timeout and exact JSON verification; its local default is
the listener's health endpoint. The original review's urllib request is not
identified as a configured monitor. An intended public URL/client configuration
and expected network location are still missing and owner-skipped for this
delivery; a later curl success would
not supply them. No health rule or Cloudflare configuration change is justified.

Inventory the configured clients and reproduce their real method, headers,
URL, response status/body, and timeout from the expected network location.
Compare local readiness with the public path using the
[health contract](../reference/api/health.md) and
[healthcheck.sh](../../scripts/healthcheck.sh). Prefer correcting the intended
probe configuration. Change a narrowly scoped health rule only if required and
authorized; retain protection of other paths. Verify healthy/unhealthy handling,
no cached false health result, and useful failure reporting from the actual
monitor. A curl success alone does not qualify a monitor using another client.

### LR-20 — Protected host-log coverage (host-owner audit; #56 coverage)

- [ ] Complete the same fixed-window review of system/kernel/auth/mail/Fail2Ban,
  Plesk, web-server, and host database logs.

The original service account could not read these logs. The host owner must
inspect **2026-10-12 22:25:09–2026-10-13 05:25:09 UTC**, including rotations and
the logs' timezone conversion. Record each source's coverage and any retention
gap, actionable finding, or verified clean result. Correlate connection bursts,
rotation, and mail failures with LR-11/LR-12/LR-15. Keep sensitive entries private
and publish only the necessary redacted conclusions. A still-inaccessible or
expired log is an explicit coverage gap, not a clean result.

## Verification, rollout, and closure

For each LR item, record the implementing commit or operational change, actual
commands/fixtures, result, and remaining limitation here or on #56. Mark its
checkbox complete only when its stated proof exists. Synchronize the matching
#56 checkbox and link the evidence. A policy decision must name the selected
rule; an expected-behavior disposition must explain it from reproduction or
measurement. Keep unresolved owner actions and unavailable evidence open.

For implementation changes:

1. Run the smallest relevant executable tests while iterating. Add missing
   behavior coverage to existing harnesses first, and register any new database
   leg with `tests/run_db_tests.sh`. Use disposable authority for database and
   gameplay journeys. Record failing-before/passing-after evidence for fixes.
2. Apply [TESTING.md](../guides/TESTING.md) and [AGENTS.md](../../AGENTS.md):
   `make -C src` after C/C++ changes, changed-line formatting during work, and
   the required completion gates for behavior changes:
   `./scripts/format.sh --all --check`, `make test-all -j16 TEST_JOBS=16`, and
   `make test-db`. Use
   `scripts/check_tests_catch.sh BASE HEAD` for changed defect regressions and
   explain any inability to establish that they catch the old behavior.
3. If backup/restore code changes, run its focused tests and the documented
   privileged integration test in a disposable environment. Apply the security
   checks specified in TESTING.md for network/authentication changes. Use
   `npm ci --prefix site && npm test --prefix site` for documentation changes.
   Do not wait for CI as a substitute for local proof.
4. Update [REGRESSIONS.md](../testing/REGRESSIONS.md) for fixed defects and the
   relevant existing reference/operations docs when behavior changes. Keep raw
   production data and generated test/build artifacts out of commits.
5. For a later authorized rollout, use the existing runbook, preserve the
   deployed binary/configuration and any file requiring repair, verify the
   actual loaded build, then observe the affected path. In particular, compare
   new SQL/file statistics through a same-day restart and midnight boundary.
   Do not run deliberate failure experiments on production by default. If
   scheduler state changes, document binary/state rollback compatibility before
   release; reverting a binary alone may not safely read the new state.

Do not add fixes for observations already explained by the review: successful
backup/archive verification, historical login-export omissions, TLS renewal not
being due, or healthy service/outbox/Redis samples. They remain historical
context, not guarantees about the current host.

**Historical plan-publication instruction (superseded by the PR delivery above):**

The plan-delivery check is separate from executing it: review coverage of all
20 remaining #56 checkboxes, validate this document's links and site build,
publish it on `master`, and verify the issue links back to this file. Keep #56
open until its execution evidence satisfies the items above. #57 and #58 retain
their own acceptance criteria and closure decisions.

## Artifact and guild rewards: memory authority and ESTALE repair

Tracking issue: [#58 — Batched epic awards fail with ESTALE](https://github.com/LuminariMUD/Duris/issues/58).

Status: implementation and local qualification complete on 2026-10-14; ready for
review in [PR #70](https://github.com/LuminariMUD/Duris/pull/70) on
`fix/58-artifact-guild-memory`, based on `origin/master` at `0e27ef1e8`.
No #58 merge, production rollout or compensation has occurred. LR-01 statistics
was already squash-merged through [PR #66](https://github.com/LuminariMUD/Duris/pull/66)
as `8c3f7384a`; LR-02–LR-20 remain in [gameplay and later follow-ups](#gameplay-and-help).

### Qualification update (2026-10-14)

Live eligible feeds and guild prestige/construction apply once on the game thread.
The existing ordered writer saves current entity snapshots; type-9 v2 commands
record immutable history and never apply rewards on completion/replay. Failed
snapshot admission or terminal writes retain dirty state and retry fresh captures.
History retention is bounded at 256 entries with at most eight unqueued retries
per second. Old committed v1 receipts/outbox remain readable; an uncommitted v1
command is refused explicitly. No schema migration is required for this cutover.

The payment repair keeps `payment_pending` until the matching guild receipt
confirms COMMIT. Later guild saves and member-deletion transactions carry the
current pending realm in the same transaction. Failed writes retry without
another debit. The realm owns retry state; the duplicate pending-ID list is gone.
Flat-file payments retain their existing shared recovery journal.

| #58 acceptance criterion | Local evidence |
| --- | --- |
| Actual clustered gameplay awards | The full-server journey casts Summon Ghasts, records cast/feedback/history timing, kills three boon targets, and observes three live rewards while the writer is held. The original repository probe isolates expected-timer/guild-revision vetoes; the native real-capture test fails before immediate publication. The exact historical cast remains unproven. |
| Every eligible feed and guild increment; state ordering | Native real reward capture covers same-character and same/different-guild bursts, cumulative construction and mixed rewards. Real artifact stores, timer command, wars callback and corpse/removal APIs run through held snapshots, then actual MariaDB transactions and the boot-row decoder verify final state and mirror agreement. |
| Capped feed and genuine eligibility | Native capture and SQL history cover below/at/above cap, same-second awards, zero-effect capped success, unworn/missing artifacts, trusted actors, group eligibility and wrong/right/free PvP souls. No blanket ESTALE retry was added. |
| Stable identity and no repeated benefit | Parent/actor-derived IDs, immutable history replay, actual boon/combat/stone producers, offline return/reconnect, and eviction beyond the real 256-entry completion cache all pass. Full-server crash/restart and PvP cases pass. |
| Useful bounded diagnostics | Actual reporters retain full opaque IDs plus stage/reason, entity and error metadata. Reconciliation detects mirror/missing-row/identity/history defects without equating history totals to current gameplay state. New history has no old SQL gameplay veto to report. Suppression age remains distinct from operation age. |
| Regressions, gameplay and historical assessment | The gates and fault cases below pass after documented fixture corrections. The bounded historical disposition below establishes no compensable amount from the reported capped bursts. |

The deterministic native direct-award control covers capped and uncapped bursts;
the full-server legs exercise actual spell/boon and PvP publication. The state-ordering
SQL leg controls writer scheduling and receipts, then runs real SQL and reloads
through the production row decoder. It covers feeds around transfer, soul changes,
staff extension, war burn, corpse moves, expiry/removal and recreation. It does
not simulate the full physical inventory/room engine. Those boundaries retain
existing gameplay checks and have the separate full-server reward/restart legs.

| Full-server boundary | Persisted artifact increment | Guild prestige / construction | Reward histories |
| --- | ---: | --- | ---: |
| Crash before the first artifact save | 0 | 85 / 0 | 0 |
| Crash after the first artifact save, before guild save | 3,600 seconds | 85 / 0 | 0 |
| Crash after first history COMMIT, before notification | 3,600 seconds | 95 / 0 | 1 |
| Boon burst drained, copied over, then restarted | 10,800 seconds | 115 / 1 | 3 |
| Blocked bounded shutdown, then restart | 0 | 85 / 0 | 0 |
| PvP reward drained and restarted | 720,000 seconds | 105 / 1 | 1 |

All six variants passed together on the final production source in the database
gate. A test-only interposer holds the real history COMMIT before notification.
Blocked shutdown names unsaved artifact/guild state and every unresolved history
pair; copyover cancels while the writer is blocked and succeeds after recovery.
`bin/analysis/artifact-estale/gameplay*.json` retains the private fixture evidence.

Validation and corrections:

- `make test-all -j16 TEST_JOBS=16`: **731/731 passed**, 695.94 seconds.
  An earlier run had five stale source/documentation/fixture checks; all were
  corrected before this passing run. The epic seed manifest changed only the
  `epic.h` source hash, not payout data.
- `make test-db`: **76 distinct legs**. Its full run passed 68 and exposed eight
  linker failures for the new metadata-log callback. A shared weak fixture adapter
  fixes those; all eight reran successfully under disposable MariaDB, plus the
  expanded artifact/guild SQL leg. The aggregate is 76/76; the original make
  invocation exited nonzero, and the entire already-passing set was not repeated.
- Server/development/production builds, `make -C src pfile`, maintained migration
  tools (`all affects pfile_converter`), and full-tree formatting pass.
- `npm ci --prefix site && npm test --prefix site`: **15/15 passed**.
- Writer/coordinator allocation regressions, guild-member capture restoration and
  copyover lifetime regression each pass after and fail before their repair.
  `scripts/check_tests_catch.sh` reports 1/1 for each corresponding isolated range.

Qualification also repaired three concrete persistence/lifetime defects: stale
staff artifact-sync publication, temporary guild-member removal surviving a
capture exception, and copyover running room-entry effects on restored characters.
The last was observed as an intermittent full-server crash and reproduced as an
ASan heap-use-after-free in the actual buffer restorer. Recovery now uses the
existing placement mode that skips movement hazards/procs. Old acknowledgements
cannot settle a newer snapshot or a recreated realm. No extra persistence queue
or generic retry framework was introduced.

The published working checkpoint is preserved on `fix/58-56-estale-log-review`.
The review branch replays only the #58 code/qualification commits onto current
master; it does not replay the squash-merged statistics commits. Its complete
`src/` tree equals the tested checkpoint (`5959df9992b3a0e8f6ca6af2f5d9dbcc191f5597`).
Only upstream migration/docs/help/news changes accompany the new base. Integration
checks pass: 18 migration-runner tests, 12 documentation tests, the pipeline contract,
full-tree formatting and all 15 site tests. No published branch was
rewritten. The earlier continuation/pause records below are historical and are
superseded by this section.

Historical compensation assessment: the reported three capped bursts contain
seven committed parent epic awards, three successful artifact-only children and
four rejected children. Successful feeds added 8, 123 and 55 seconds, each reaching
the ten-day cap; this evidence establishes no additional compensable timer value
or missing guild amount. Rejected transactions leave no child inbox/payload, so
alert counts and parent awards cannot reconstruct each rejected benefit. Below-cap
and guild-only loss is reproduced synthetically but is not an attributable recovery
amount for these historical failures. No compensation is proposed or applied.
Any later adjustment requires recoverable parent/actor/state/cap evidence and
specific owner authorization.

Local logs: `/tmp/duris-es-final-test-all.log`, `/tmp/duris-es-final-test-db.log`,
`/tmp/duris-es-db-fixed-*.log`, `/tmp/duris-es-copyover-placement-catches.log`,
`/tmp/duris-es-guild-capture-catches.log`, and `/tmp/duris-es-state-ordering*.log`.
All gameplay/database tests used isolated worlds and disposable schemas. The
shared dev game and production were not used for this implementation/qualification.

### Continuation evidence (2026-10-13)

The reward cutover builds with `make -C src -j16`, and the updated disposable
MariaDB artifact/guild fixture passes, including the corrected outbox stub.
`world persistence` now shows live applications, capture failures, dirty
artifact/soul and guild snapshots, committed/rejected/lost/pending history,
admission failures, malformed completions, and oldest pending-history age.
`test_persistence_status_contract.py` verifies that metadata boundary.

The writer allocation regression now injects failure at every admission allocation.
It proves that a refused submission leaves neither a queued job nor an owner-index
entry, and that replacing the tail needs no allocation. It passes on the worktree;
`0ccec836e` compiles but fails because a refused job remains queued. Evidence:
`bin/analysis/artifact-estale/writer-allocation-before.log`. This exposes a concrete
shared-writer defect required by snapshot admission recovery, not only an errno change.
It is committed in `dfecafbda`; `scripts/check_tests_catch.sh c8655bfbd dfecafbda`
confirms 1/1 changed tests pass after and fail before.

The snapshot fixture additionally passes bulk soul-reset receipt ownership,
later binding changes, and reset admission/allocation failure recovery. The reward
fixture adds a positive different-guild control and links the real stone publisher
to the actual artifact reward path: online publication, offline return, derived
parent identity, duplicate completion/reconnect after child completion, and a
recovered claim all pass. Its coordinator has no completed-ID cache, so the stone
source guards supply deduplication. Full real-coordinator cache-eviction and PvP
producer evidence remain open.

Allocation probing then reproduced a reservation leak between coordinator
reservation and writer submission: constructing the owned callback could throw,
leaving a fenced operation with no writer job. `532fe0653` releases that reservation
on dispatch failure, distinguishes admission errors, and counts acceptance only
once the writer accepts. The native fault test warms the hash buckets before
walking allocations (otherwise a failed rehash can shift a later failure point).
It fails before the fix with retained inflight/fence state and passes after it.
Local evidence is `/tmp/duris-es-coordinator-allocation-before.log` and
`/tmp/duris-es-coordinator-allocation.log`.
`scripts/check_tests_catch.sh dfecafbda 532fe0653` confirms 1/1 tests catch the
pre-fix behavior. The server was rebuilt successfully after this fix.

No new completed-result API is needed after that cleanup: admitted history remains
queued, retries submit only unadmitted commands, and source guards own new live
publication. Actual coordinator-cache eviction and the PvP producer still need
end-to-end proof; do not replace them with the finite cache as a deduplication store.

`test_mysql_artifact_guild_reward_journey.py` now passes against a disposable full
server/world and is registered in `tests/run_db_tests.sh`. The actual mortal
necromancer casts Summon Ghasts, its delayed event kills three targets, and the
real boon publisher grants three 4-epic awards. An SQL row lock holds the writer:
`world persistence` reports three live applications, one dirty artifact and guild,
and three pending histories while SQL still holds the old timer and 85/0 totals.
Copyover fails boundedly and leaves the server live. After release, the timer gains
exactly 10,800 seconds and guild totals become 115/1; the three history rows retain
successive timer values and 95/0, 105/1, 115/1 guild outcomes. Copyover then succeeds,
and a clean restart preserves state without granting history again.

Evidence is `bin/analysis/artifact-estale/gameplay-journey.json` (binary hash,
cast/event/award/history timestamps, held-writer health, SQL values and synthetic
transcript) and `/tmp/duris-es-gameplay.log`. This run used the server before the
later coordinator allocation fix; the complete final-source database gate still
must rerun it. The current journey does not yet cover crash stages, PvP, all
transfers/removals/spending, or real coordinator-cache eviction.

`make -C src -j16 pfile` and `make -C migrations/tools -j16 all affects pfile_converter`
pass. The migration build exposed one obsolete `Guild::add_points_from_epics` stub,
now removed. Full-tree formatting passed for tracked C/C++ before the subsequent
coordinator fix; the two untracked C++ fixtures have also been formatted.

Additional source-audit findings to reproduce and fix before final qualification:
`arti_syncdb_sql()` clears and hydrates artifact memory in an asynchronous callback,
which can overwrite changes made after the staff command was queued. The kingdom
payment pair still reports queue admission as durability and lacks terminal-failure
receipt tracking. Preserve paired guild/realm semantics while investigating it;
keep any independent pre-existing repair separate from the reward cutover.

### Pause handoff

This checkpoint was saved before resumption. The implementation and qualification
are active again; subsequent evidence is recorded below as it completes.

The worktree is `/home/aiwithapex/projects/duris-estale-log-review`; its common
Git directory is `/home/aiwithapex/projects/duris/.git`. Preserve the source,
reconciliation script, and maintained-test changes shown by `git status`, including
the four new runtime/snapshot fixture files. They are local work in progress,
not part of PR #66. This handoff updates documentation only.

The last pending snapshot/shutdown/severity test sequence completed successfully.
No task build, test, or disposable database process remains running. The shared
local/dev game and database remain running and may be used by another worktree.
Keep future journeys isolated; check current runtime ownership before operating
any shared instance. No #58 production operation, deployment, or compensation
has occurred.

#### Implementation present in the worktree

- `artifact_guild_command.*`, `artifact_guild_state.*`, and
  `artifact_guild_transaction.*` implement v2 captured before/after facts,
  immediate game-thread rewards and feedback, immutable bounded pending history,
  and completion handling that does not apply rewards. Guild thresholds accumulate
  from current memory. The MySQL capability gate remains explicit; unused duplicate
  feeding formulas and the SQL approval/hydration cache are removed.
- `artifact_guild_repository.*` writes history only. It preserves committed v1
  receipt and outbox replay, refuses uncommitted v1 commands, and reports named
  malformed/identity/missing-parent failures. History revisions come from ledger
  metadata. No schema migration was added.
- `sql_async.*` adds preallocated commit receipts; `artifact.c`, `assocs.*`, and
  `sql_player.c` retain dirty current state after snapshot failure, acknowledge only
  the corresponding capture, and retry fresh snapshots in bounded batches. Guild
  upserts include both reward totals. Artifact removal retains a deletion tombstone
  until its write completes. The player writer preserves admission atomicity on
  allocation failure; coordinator admission distinguishes capacity, allocation,
  and quiescence errors.
- `comm.c` and `copyover.c` add domain pulse/drain accounting and unresolved-write
  reporting. The most recent copyover change adds a final domain drain after final
  saves; it still needs executable lifecycle qualification.
- `reconcile_artifact_guild_outcomes.sh` now takes explicit database credentials,
  checks persisted mirrors/references and internal history consistency in a read-only
  snapshot, and permits legitimate divergence between reward history and current
  gameplay totals. Cache generation invalidation also covers a successful retry
  after earlier snapshot admission failed.

#### Verified evidence and limits

| Check | Result at pause |
| --- | --- |
| `test_artifact_guild_rewards_runtime.py` | Passes real capture/application tests for bursts, cumulative guild thresholds, caps, eligibility, invalid arithmetic, pending duplicates, delayed completions, and history refusal/retry/capacity. Against `0ccec836e`, fails at the first pre-completion timer assertion. |
| `test_artifact_guild_snapshots.py` | Passes real artifact row/soul and guild capture, exact-capture acknowledgement, terminal/admission/allocation failure, current-state retry, removal/recreation, bounded round-robin retries, and cache generation cases. The cache read after failed admission case failed before retry invalidation was added and now passes. SQL completion is controlled by the fixture; this is not a full database/restart journey. |
| `run_artifact_guild_schema_mysql.sh` under `with_disposable_mariadb.sh` | Passed captured history/replay, newer snapshot preservation, reconciliation mismatch/missing-row detection, cap no-op, malformed/identity/missing-parent failures, committed v1 receipt/outbox, and history after removal. A subsequent fixture-only return-type/header correction still needs a rerun. |
| Codec and existing focused tests | Passed `test_artifact_guild_transactional_cutover.py`, `test_combat_artifact_persistence.py`, `test_artifact_cache_codec.py`, `test_sql_async.py`, `test_player_save_worker.py`, `test_critical_command_coordinator.py`, `test_epic_in_memory.py`, `test_epic_stone_runtime.py`, `test_kingdom_contract.py`, `test_flatfile_artifact_repository.py`, and `test_flatfile_association_repository.py`. The stone fixture's artifact stub does not prove the full producer. |
| Latest completed sequence | Snapshot tests, `test_shutdown_writer_bound.py`, and `test_persistence_severity.py` pass. The shutdown test is a source contract, not the required live shutdown/copyover journey. |
| Server build | `make -C src -j16` passed during implementation, before the latest cache/copyover/diagnostic edits. A build of the final source is still required. |
| Complete qualification | Not run for #58. LR-01's 727 regression / 75 database / 15 site successes apply to its earlier source only. |

Before-fix evidence is retained under the ignored
`bin/analysis/artifact-estale/`: `probe.py`, `result.txt`, `runtime_before.cpp`,
and `runtime-regression-before.log`. The original SQL probe reproduced burst/cap
rejection, mirror disagreement, and successful receipt replay. The old native
fixture captured three identical +3,600-second feeds while memory advanced zero,
and three same-guild awards left memory at 85 prestige / 0 construction instead
of 115 / 1. Run old-source fixtures only in a detached checkout of `0ccec836e`,
with separate build outputs; their old APIs do not describe the new worktree.
The maintained runtime fixture's before-fix failure was a behavior assertion,
not a compile error.

Additional local logs are temporary files: `/tmp/duris-es-runtime.log`,
`/tmp/duris-es-sql-async.log`, `/tmp/duris-es-codec.log`,
`/tmp/duris-es-mysql.log`, `/tmp/duris-es-snapshots.log`,
`/tmp/duris-es-snapshot-retry-before.log`, and `/tmp/duris-es-build.log`.
Preserve needed evidence before cleanup; `make clean-all` removes ignored `bin/`
evidence, and `/tmp` is not durable storage.

#### Resume checklist

Historical checkpoint, superseded by the execution plan at the top.

1. Review the existing diff and the continuation evidence above. Diagnostics and
   shared admission repairs are implemented; preserve their separation of live
   application, unsaved state, and history success/loss.
2. Prove real boon/PvP/stone publication guards, including reconnect and completion
   cache eviction. The dispatch-allocation reservation leak is now fixed; retain that
   fault regression while checking source publication guards. Do not
   use that finite cache as permanent live-award deduplication.
3. Audit every artifact tombstone/removal loop, bulk soul-reset acknowledgement,
   and the kingdom-payment/member-removal shared SQL builders. Prove kingdom
   payment interleaving beyond source contracts. Writer enqueue allocation, bulk
   soul reset and the different-guild positive control now have executable coverage.
4. Extend the registered `test_mysql_artifact_guild_reward_journey.py` from its
   passing Summon Ghasts / blocked writer / copyover / clean restart cases to the
   remaining crash stages and gameplay interleavings. Qualify shutdown reporting
   and the final copyover drain after late saves. The full matrix below remains required.
5. Rerun the changed MariaDB fixture, build the final server and maintained tools
   affected by shared headers, format, run all local gates below, and retain genuine
   before/after evidence. References and regression notes now describe the branch
   implementation with its qualification limits; reconcile them with the final code.
6. Commit/push coherent qualified changes and open a separate #58 PR, leaving it
   unmerged. Then continue LR-02–LR-20 in [gameplay and later follow-ups](#gameplay-and-help).
   `skeer` stays skipped by owner decision.

Prepared on 2026-10-13 against `master` at `79541e206`, the current issue and its
two reproduction/trigger comments. Production observations below are the issue's
reported evidence, not a new inspection of the production database or logs.

Related work: [#56](https://github.com/LuminariMUD/Duris/issues/56) and
[memory-authority requirements](#preserve-memory-authority). That plan
correctly separates statistics output identity and epic-skill refresh from this
artifact/guild reward defect. #58 owns this work and its closure evidence.

### Decision, outcome, and boundaries

**Make artifact feeding and guild prestige/construction authoritative in memory.**
Apply each eligible reward on the game thread before processing the next award.
Persist the resulting state through the existing artifact and guild snapshot
writes on the single writer. Retain the derived type-9 command as idempotent
reward history; it must neither decide the reward nor mutate its live state on
completion. This follows the existing epic-point design and gives the live award
one authority.

The required outcome is that a burst of eligible awards produces all its timer,
prestige, and construction effects immediately, in gameplay order, with the
existing eligibility, feeding cap, and soul rules. Transfers, spending, expiry,
and removal must see those updated values. Ordered saves must preserve that
sequence; retries, completion delivery, and history replay must add no rewards.

[ADR 0002](../adr/0002-persistence-reset-memory-is-the-authority.md) and the
pipeline reference now record the branch's narrowed economy exception for
epic-derived artifact/guild rewards, now locally qualified for review. Other
economy transactions retain their current authority and durability contracts.

**Crash contract:** this is asynchronous persistence, not a new durable gameplay
journal. A crash may lose state not yet saved, as the ADR permits. Committed
history is not an instruction to award again at boot. Exactly-once means one
live application per new source award, idempotent state snapshots, and one
history outcome per parent/actor through repository retries and replay. It does
not promise recovery of every unsaved reward or atomic durability of the epic
balance, all artifact snapshots, guild snapshot, and history as one transaction.
Do not claim the player's 30-second checkpoint covers artifact/guild state:
those currently have their own immediate queued writes, without that checkpoint.

**Non-goals:** spell balance, changing reward amounts or level gates, completing
the other #56 findings, a general persistence rewrite, new writer/journal/lock
infrastructure, new flat-file reward support, or automatic historical compensation.
Production repair, migration, restart, deployment, and historical compensation
require their specific authorization; none has been performed for this repair.

**Files and proof:** the source owners and existing tests are listed below.
Implementation needs executable tests of the actual capture/application path,
disposable database tests of snapshots/history, and a gameplay/restart journey.
The original planning document was published before implementation began.
Implementation delivery is through reviewed PRs, with documentation and
qualification evidence updated alongside the code.

### Original evidence and implementation consequences

The table records the pre-cutover behavior at `0ccec836e`; the pause handoff above
describes what is now implemented. The work sequence below remains the acceptance
contract, not a claim that every listed change or test is still unstarted.

| Original path | Finding and consequence |
| --- | --- |
| [epic_transaction.c](../../src/world/epic_transaction.c), `epic_transaction_submit_identified()` | Changes the balance and calls completion before returning. The writer records history; player saves persist the balance. Preserve this model. |
| [epic.c](../../src/world/epic.c), `gain_epic()`; [boon.c](../../src/economy/boon.c), `boon_publish_transaction_result()` | Each completed epic boon can submit a child before any preceding child's completion is handled. Ordinary awards are a real burst producer. |
| [artifact_guild_state.c](../../src/guild/artifact_guild_state.c) | Captures artifact timer/soul and cached guild revision; computes construction from current guild prestige. Reward-driven updates arrive only in `artifact_guild_state_publish()`. Successive captures can therefore reuse both a timer and a threshold calculation. |
| [artifact_guild_repository.c](../../src/guild/artifact_guild_repository.c) | Rejects mirror disagreement, expected timer/soul disagreement, or an old guild revision with `ESTALE`. An artifact revision change alone is already allowed. It currently mutates state as well as history. |
| [artifact_guild_transaction.c](../../src/guild/artifact_guild_transaction.c) | Publishes state/messages only after success and erases rejected pending work. `pending.emplace()` and coordinator attachment are not, by themselves, a guarantee of one live application after changing this design. |
| [artifact.c](../../src/guild/artifact.c) | `artifact_row_store()` and the soul stores already change memory and enqueue snapshots, including the domain mirror. `artifact_feed_published()` compensates for an intervening move storing the old timer by queueing another row. Remove the need for that delayed repair. |
| [assocs.h](../../src/guild/assocs.h), [assocs.c](../../src/guild/assocs.c), [sql_player.c](../../src/sql/sql_player.c) | Guild totals live on `Guild`, but `sql_save_guild_statements()` deliberately uses `prestige=prestige, construction=construction` on update. Memory authority requires saving both captured totals. Apply both before one save; do not reuse `add_points_from_epics()` unchanged, which saves prestige before adding construction. |
| [fight.c](../../src/combat/fight.c), `submit_pvp_outcome()`; [zone_touch_transaction.c](../../src/world/zone_touch_transaction.c), `publish()` | These are the other child producers. PvP derives children from a combat parent plus actor; stones use each participant's derived epic award ID and publish an offline participant on return. Preserve those identities and source timing. |
| [critical_command_coordinator.c](../../src/persistence/critical_command_coordinator.c), [player_save_worker.c](../../src/player/player_save_worker.c) | Commands and SQL jobs share one writer. Retried commands remain ahead of later jobs; completions return separately. Serial execution does not repair an already-stale captured command. The coordinator's 256-entry completion cache is not a permanent deduplication store. |
| [artifact_guild_outcome.sql](../../migrations/artifact_guild_outcome.sql) | Existing inbox/outcome keys, parent foreign key, and unique parent/actor pair protect history identity. Keep them. A failed parent-history insertion can also prevent child history; it must not undo or gate live benefits. |

The issue reproduces three captures yielding one applied child and two `ESTALE`
failures, separately for artifacts and guilds. It also reproduces rejection when
the first feed already reached the same capped target. The actual production
bursts' successful feeds reached ten days, so those alerts do not establish lost
additional time or guild benefits for that incident. Below-cap and guild-only
losses are demonstrated by the repository probe.

Summon Ghasts is the player's tentative corrected trigger. Its delayed area
attack can reach ordinary kill/boon awards; it is not a persistent-pet operation.
The exact production cast and rejected comparison remain unverified.

### Work sequence

Completed #58 acceptance record; the qualification section above supplies the
proof. These recipes do not require a new implementation or qualification pass.

#### ES-01 — Establish executable evidence through gameplay capture

- [x] Add failing-before tests for the real reward path and identify each old rejection.

Extend [test_artifact_guild_transactional_cutover.py](../../tests/async/test_artifact_guild_transactional_cutover.py)
with a native runtime fixture, or a focused `test_artifact_guild_rewards_runtime.py`
if separation improves clarity. Link the real capture/submit/application code;
stub unrelated engine services and control writer/completion delivery, not reward
arithmetic. Hold completions while issuing three awards from the same character
and awards from multiple characters in one eligible guild. Include a prestige
threshold crossed only by the accumulated awards, mixed artifact/guild rewards,
and a timer already at the cap. Assert intermediate and final values, not only
an absence of `ESTALE`.

Extend the existing [MariaDB harness](../../tests/async/artifact_guild_mysql_harness.cpp)
with the issue's repository probe cases. Label that probe as repository evidence,
separate from the new real-capture fixture. During characterization, distinguish
`mirror`, `expected_timer`, `expected_soul`, `expected_bind_timer`, and
`guild_revision`; one numeric error cannot identify them. Preserve an executable
before-fix case even when the final implementation removes these checks.

#### ES-02 — Apply rewards once in memory and save the actual state

- [x] Make live application synchronous and remove completion-driven state changes.

1. Keep one calculation path in `artifact_guild_state.c`, using the existing
   artifact memory and `Guild` objects. Preserve epic-source modifiers, difficulty
   scaling, recent-frag bonus, worn-artifact selection, trusted-character rules,
   group eligibility, nexus prestige bonus, and PvP soul eligibility. Capture
   time once per award and preserve the current cap calculation. Check arithmetic
   and result bounds before changing any part of a combined reward.
2. Calculate each timer from the current memory timer. Calculate construction as
   `(prestige_after / notch) - (prestige_before / notch)` using the newly updated
   prestige from preceding awards. Apply both guild totals before capturing one
   guild save. When the timer already equals this award's cap, the eligible feed
   has zero added time and is a successful no-op. Preserve the existing clamp
   behavior for a timer above the cap; do not introduce a new balance rule.
3. Reuse `artifact_row_store()` for timer persistence and its domain mirror;
   introduce only the small timer-update entry point needed across these files.
   A feed changes no location, ownership, or soul. Reuse `Guild::save()` and
   change its SQL upsert to write captured prestige/construction totals. Preserve
   other guild fields and the shared statements used by kingdom payment writes.
4. Queue snapshots at the point of live mutation. They capture owned values,
   never game pointers for the writer to read later. Later transfers, soul
   changes, timer extensions/wars, expiry/removal, guild spending, and staff
   settings must capture the resulting newer state. Do not append an old reward
   snapshot again when a completion arrives or a history retry is requested.
5. Publish reward feedback once with live application. Completion processing
   updates persistence health only. Remove `artifact_feed_published()`'s delayed
   repair and the guild revision cache/hydration dependency once their callers
   are replaced. Keep boot loading of actual artifact/guild state.
6. Integrate ordinary awards, PvP, and stone publication. Keep the stone's durable
   claim boundary and offline-recipient behavior. Inspect each source's existing
   publication guard; no callback, reconnect, or duplicate completion may invoke
   the live reward a second time. A history replay is a separate operation from
   a new gameplay award and must never enter live application.

Do not revive the unused `epic_feed_artifacts()`/`Guild::add_points_from_epics()`
formula copies as a second path. Keep backend capability checks explicit:
The old `artifact_guild_state_hydrate()` returned false without MySQL, and the
flat-file critical dispatcher has no type-9 implementation. Removing hydration
must not accidentally enable an unsupported backend or change its reward rules.

#### ES-03 — Make type-9 history idempotent and independent of live state

- [x] Convert the existing command/repository to record captured reward facts only.

Use [artifact_guild_command.h](../../src/guild/artifact_guild_command.h) and
[artifact_guild_command.c](../../src/guild/artifact_guild_command.c) for a versioned
payload containing the parent/actor identity, calculated deltas, actual timer
before/after values, and guild totals before/after live application. Keep the
15-artifact bound. Before-values describe history; they are not SQL approval
conditions. The existing result shape can remain if it still represents these
captured values unambiguously.

In `artifact_guild_repository.c`, remove gameplay timer/soul/guild comparisons
and writes to those gameplay fields. Record outcome and delta rows with the
captured facts in the existing inbox/outbox transaction. Allocate database ledger
revisions on the writer from durable ledger metadata; they order history only
and are not hydrated into a gameplay approval cache. Keep identity/hash checks,
parent linkage, unique parent/actor identity, bounds checks, and the existing
transactional replay result. History must never recompute a reward from current
SQL totals or overwrite memory or persisted snapshots.

Submit state snapshots before their history command on the game thread. A
terminal snapshot failure can still be followed by a successful history write;
the receipt alone therefore does not certify saved state. Keep those statuses
distinct and verify the actual state after recovery/drain.

Handle the following explicitly in `artifact_guild_transaction.c` and its three
producers:

- Derive the child from the same parent, domain constant, and actor. Distinguish
  a new source award from attaching/retrying its existing history before any live
  mutation. Do not treat `accepted` and `attached` as two new grants or recapture
  changed state under an existing identity. Reuse the original immutable command.
- Writer retry, duplicate completion, and repository replay perform history work
  only. Parent publication guards own live once-only application; prove them at
  the real producers. Do not rely on the coordinator's short completion cache,
  add an unbounded set of every award ever seen, or allow a replay API to call
  `gain_epic()` with a newly minted parent.
- Preserve a prepared history command when its local submission is retryable,
  within the existing pending-work bounds. A later history retry cannot reorder
  gameplay snapshots because it writes no gameplay fields. Queue refusal,
  unavailable history, malformed data, or a missing parent receipt must be
  reported separately from live reward success; none reverses an earned reward.
- Check snapshot admission errors too: the old `artifact_row_store()` ignored
  the SQL queue result. Surface the failure and retain a dirty indication on the
  affected current artifact/guild state for a bounded later save attempt. Retry
  a freshly captured current snapshot, not the old reward's values. Keep this
  domain-local: one dirty indication per existing entity, serviced from the game
  thread, without a second queue of historical snapshots. Use the same writer,
  include unsaved dirty entities in shutdown drain accounting,
  and acknowledge it only for the captured state that actually succeeded. No
  false durable-success report or endless invisible dirty state is acceptable.
- Distinguish queue capacity from memory allocation failure and shutdown
  quiescence. Keep the live state authoritative and report anything that could
  not be retained/saved. Do not invent crash recovery for work never persisted.
  Test the exhaustion policy and pending-state bounds explicitly.

Retain decoding of committed old commands/results needed for receipt replay and
pending outbox delivery. Produce only the new payload for new awards. Old-format
replay must resolve an existing receipt without applying gameplay; unsupported
uncommitted old payloads must receive an identifiable disposition, not a new
identity. Drain before upgrading and qualify an old pending outbox fixture.
Do not add a second long-lived gameplay implementation for compatibility.

The existing tables already contain the required history and uniqueness fields;
no schema migration is planned. If the executable design reveals an actual
missing field, use an additive, guarded migration and update bootstrap/verifiers
and compatibility contracts together. Preserve existing history and baselines.

#### ES-04 — Keep diagnostics and reconciliation truthful

- [x] Separate live application, saved state, history results, and genuine integrity failures.

Use bounded fields in existing persistence diagnostics: stage, reason, opaque
operation/parent IDs, entity kind, counts, relevant non-sensitive values, and
capture/queue/completion timing. Exclude player names, credentials, and raw
payloads. Give each retained rejection a named reason, including identity
conflict, malformed payload, missing parent, missing state, and storage failure.
The old expected-timer/soul/guild-revision vetoes are removed from the new history
path, not renamed into a retry loop. Mirror disagreement remains diagnosable as
a persistence problem. Preserve full logging before wizlog suppression and
document that suppression age is not operation age. Preserve artifact cache
generation invalidation at mutation and durable outbox invalidation, and test
that an earlier in-flight Redis read cannot become current after the change.

Update [reconcile_artifact_guild_outcomes.sh](../../migrations/reconcile_artifact_guild_outcomes.sh):
its baseline-plus-feed-ledger and latest-guild-ledger-equals-current-state checks
cannot prove current state after timer wars, staff adjustments, or guild spending.
Check artifact mirror agreement including missing rows, outcome/ledger internal
agreement, identity uniqueness, and referential integrity separately. Do not
silence a real mismatch by rewriting baselines or replaying rewards. Prove state
equality after an observed writer drain in disposable tests; distinguish pending
writes from settled divergence. The old script read `.env`; the branch version
requires explicit credentials. Keep its tests on disposable storage rather than
the configured game database.

Keep `artifact_domain_state` and its item ownership reference; removing that
table or the one-item/one-owner protections is unnecessary. Document the new
meaning of reward ledgers in
[CRITICAL_COMMAND_PIPELINE.md](../persistence/CRITICAL_COMMAND_PIPELINE.md), the
ADR, and the existing database reference where affected.

#### ES-05 — Prove gameplay, persistence, replay, and restart

- [x] Pass the matrix below, a real Summon Ghasts journey, and the required local gates.

| Case | Required evidence |
| --- | --- |
| Same character: three uncapped feeds with writer/completions held | Three increments visible before completion; persisted timer agrees after drain; one history outcome per award. |
| Guild-only and mixed rewards from several same-guild participants | Every prestige increment survives; construction crosses each threshold correctly; artifact/guild eligibility remains independent. Include different guilds as a control. |
| At/below/above cap boundary and successive awards in one clock second | Existing cap formula is preserved; repeated capped awards succeed with zero added time; no duplicate messages on completion. |
| Missing/unworn artifact, trusted actor, insufficient group, PvP wrong/right/free soul | Current eligibility rules hold; no newly eligible reward due to removing SQL checks; malformed combined payloads cannot partly change memory. |
| Feed before and after transfer, soul change, extension/wars, death/corpse move, expiry, removal/recreation | Memory follows game-thread order immediately; drained and reloaded state retains the final owner/soul/timer; delayed history or completion resurrects nothing. |
| Guild reward interleaved with spending, construction changes, staff settings, and kingdom payment save | Captured saves preserve both totals in order; an old completion/history replay cannot undo a spend or overwrite a later setting. |
| Retry, duplicate completion, receipt replay, reconnect, and completed-cache eviction | One live source publication and one outcome per parent/actor; unchanged command identity/bytes; no reapplication after receipt replay or after boot hydration. Exercise PvP and stone producers, not only `gain_epic()`. |
| SQL outage, rollback, lost commit acknowledgement, local queue refusal, and missing parent receipt | Gameplay remains usable; snapshots recover or report their actual unresolved state; history retries add no reward; dirty/pending state is bounded; no false claim of atomic state/history durability. |
| Hard crash before saves, between entity saves/history, and after history commit but before completion | Restart loads only persisted state, with any permitted unsaved loss documented; history/outbox replay never re-awards. No timer/guild increment is applied twice. |
| Clean restart and copyover with outstanding writes | Correct state after successful drain; unresolved writes named on bounded shutdown; copyover follows the existing drain-failure policy. |
| Mirror missing/mismatched row, bad payload, identity conflict, old result/outbox | Named diagnostic and correct recovery/refusal disposition; no blind state overwrite; old notification delivery remains compatible. |

Extend the existing artifact/guild MariaDB wrapper and register a new gameplay
journey, `test_mysql_artifact_guild_reward_journey.py`, in
[tests/run_db_tests.sh](../../tests/run_db_tests.sh). Use the maintained disposable
MariaDB setup. Run the full game with isolated staff/players, controlled worn
artifacts and guild membership, and several eligible epic boons/targets. Cast
Summon Ghasts and record cast, delayed attack, kills, boon publications, live
reward values, snapshot writes, and history completion. Allow for its random
one-round deferral or control randomness in the test fixture; do not substitute
a direct SQL payload for the gameplay leg. Include a deterministic direct-award
burst as the control and test both capped and uncapped conditions.

Reuse these focused checks, extending behavioral coverage where needed:

- `python3 tests/async/test_artifact_guild_transactional_cutover.py`
- `python3 tests/async/test_combat_artifact_persistence.py`
- `python3 tests/async/test_artifact_cache_codec.py`
- `python3 tests/async/test_epic_in_memory.py`
- `python3 tests/async/test_epic_stone_runtime.py` (its current artifact stub is
  not proof of actual feeding; the new runtime/journey coverage must supply it)
- `python3 tests/async/test_critical_command_coordinator.py`
- `python3 tests/async/test_persistence_severity.py`
- `python3 tests/async/test_kingdom_contract.py`
- `tests/async/with_disposable_mariadb.sh tests/async/run_artifact_guild_schema_mysql.sh`

Replace source assertions that require delayed publication, hydrated approval
revisions, or protected guild totals with assertions for the new contract; keep
codec bounds, identity, mirror, and transaction coverage. Run the existing
flat-file artifact/association tests to prove unchanged backend behavior.

For implementation, follow [TESTING.md](../guides/TESTING.md) and
[AGENTS.md](../../AGENTS.md): `make -C src`, changed-line formatting while working,
then `./scripts/format.sh --all --check`, `make test-all -j16 TEST_JOBS=16`, and
`make test-db`. Run `scripts/check_tests_catch.sh BASE HEAD` for changed defect
regressions and inspect that failures demonstrate behavior rather than a missing
renamed symbol. Add before/after evidence to
[REGRESSIONS.md](../testing/REGRESSIONS.md). Run
`npm ci --prefix site && npm test --prefix site` for documentation. Do not wait
for CI in place of local verification.

### Rollout, historical impact, and closure

- [x] Record code/test evidence for all six #58 acceptance criteria before closure.

The first criterion maps to ES-01 and the Summon Ghasts journey; reward/cap/state
ordering maps to ES-02 and the matrix; identity/retry/restart maps to ES-03 and
the fault/restart legs; diagnostic specificity maps to ES-04; regression and
historical-impact evidence maps to ES-05 and this section. None is complete
merely because this plan is published.

For a later authorized release, use the existing runbook and stop/drain the old
writer before booting the new behavior. Verify the actual loaded binary and
observe an uncapped award burst plus settled artifact/guild saves. Qualify
rollback against retained payload/result versions; an older binary must not be
assumed to understand new pending records. No live two-version writer operation.

Historical recovery requires attributable parent/actor/reward evidence and the
state/cap applicable at that time. Failed type-9 transactions leave no inbox row;
successful parent epics and a count of alerts do not establish compensable loss.
Produce a bounded, redacted assessment on #58, including unresolvable cases.
Obtain specific authorization for any production adjustment. Never grant all
rejected capped feeds as additional time or compensate under a fresh identity
without establishing what was actually lost.

### Ablation decisions

Keep the existing memory stores, writer, command identity, inbox/outbox, and
history tables. Remove the SQL gameplay vetoes, delayed memory publication,
guild approval-revision cache, and compensating feed write. A per-artifact or
per-guild completion queue, SQL-side rebasing, or a generic retry framework would
retain competing state owners and leave transfers/spending dependent on delayed
publication. They are not needed once calculations use current memory.

Simply deleting `ESTALE` is insufficient: captured artifact targets would still
collapse several increments, and guild construction would still use old totals.
Simply advancing memory early is also insufficient: the old repository would
apply deltas again, ordinary guild saves would omit the totals, and completion
could overwrite newer state. The changes above form one coherent cutover.

## Earlier overview and execution guidance (2026-10-14)

Retained in full for continuity. Its former ordering (including “start with
statistics”) is superseded by the execution plan at the top. Facts and proof
remain relevant to their recorded commits; this is not an additional work queue.

Tracking issue: [#56 — Production follow-ups from the 2026-10-13 log review](https://github.com/LuminariMUD/Duris/issues/56).

This is the combined work record for #56 and
[#58 — Batched epic awards fail with ESTALE](https://github.com/LuminariMUD/Duris/issues/58).
It includes the complete artifact/guild plan, its historical checkpoints and
qualification evidence. Each issue retains its own acceptance and closure criteria.

Jump to [statistics](#statistics), [gameplay and help](#gameplay-and-help),
[runtime and connections](#runtime-lifecycle-and-connections),
[host operations](#host-operations-and-backups),
[monitoring](#monitoring-and-bounded-investigations),
[LR verification and rollout](#verification-rollout-and-closure), or the
[artifact/guild plan](#artifact-and-guild-rewards-memory-authority-and-estale-repair)
and its [latest qualification](#qualification-update-2026-10-14).

Status: active. LR-01 statistics was squash-merged in
[PR #66](https://github.com/LuminariMUD/Duris/pull/66) as `8c3f7384a` on 2026-10-13.
Its historical recovery proposal remains private and unapplied; a source merge
is not production rollout or historical restoration. LR-02–LR-20 remain open.
The owner explicitly skipped the unidentified `skeer` term under LR-08.

#58 implementation and local qualification are complete on
`fix/58-artifact-guild-memory`, published for review in
[PR #70](https://github.com/LuminariMUD/Duris/pull/70), open and unmerged. The actual Summon
Ghasts/PvP, crash, shutdown, copyover/restart, payment rollback and artifact-ordering
cases pass. The 731-regression gate passes; 76 database legs pass across the full
run plus eight reruns after one shared fixture-link correction. All 15 site tests
pass. Detailed evidence and fixture boundaries are in
[artifact/guild qualification](#qualification-update-2026-10-14).
No additional LR item is completed by that work. Follow-ups now run on
`fix/56-log-review-followups`. LR-02's source fix and focused executable proof
pass; the branch's final gates remain due. LR-03's level-30 policy was already chosen
in #55. LR-03–LR-05's native teacher checks and isolated full-server journey pass;
the follow-up branch's final broad gates remain due.

## Integration handoff — 2026-10-14

The statistics PR's tested code tip was `66dbfc016`; its later handoff-only
changes were included in squash commit `8c3f7384a`. The published
`fix/58-56-estale-log-review` checkpoint is retained. The new #58 review branch
starts at freshly fetched `origin/master` (`0e27ef1e8`) and replays only the #58
implementation/qualification commits, excluding the four already-squashed
statistics commits. Documentation conflicts retain the newer #58 evidence and
this integration record. No published history is rewritten. The complete server
source tree equals the qualified checkpoint. The upstream migration and documentation
integration checks, full-tree formatting and all 15 site tests pass.

Preserve ignored `bin/analysis/lr01-validation/` and `bin/analysis/lr01-recovery/`
before cleaning build output. Production repairs, rollout, backup/host changes,
and historical replacement require their specific authorization. The independent
character-mechanics project in [class-anchor.md](class-anchor.md) belongs to #52 and is not advanced
by this work. The shared dev game may be used by another worktree; qualification
here uses isolated worlds and databases.

The earlier pause checkpoint is superseded by the integration and qualification
records above. Work is active; #70 remains separate from this follow-up branch.
No production repair, rollout, restore, backup change, or alert test occurred.
Host-owner work remains open with its specific access/authorization requirements.

Prepared on 2026-10-13 against `master` at
`690ff313f3e3f115ef14b58612b0e302de2ce28d`, the current issue body and its scope-transfer
comment. The original production evidence covers **2026-10-12 22:25:09 through
2026-10-13 05:25:09 UTC**, from checkout
`1a529fa05c1af258b226258b6c9b48021e0908f8`. Counts and operational states quoted here
belong to that review; source inspection is not a fresh production health check.
The issue retains the private-log locations and timestamps; do not copy player
identities, addresses, conversations, credentials, or raw logs into this plan.

## Outcome, boundaries, and proof

Resolve every remaining #56 item with either a verified fix, an explicit gameplay
decision, or evidence that the investigated behavior is expected. Start with
statistics loss. Keep an unresolved report or missing host access open with its
specific next action; inability to reproduce once is not evidence of correctness.

Implementation uses the existing source owners, test harnesses, content import,
and backup tools identified below. It does not need a new persistence framework,
monitoring service, or test runner. Production repairs, imports, restarts,
configuration changes, and test alerts require their specific authorization.

Scope relationships:

- The 158 artifact transaction failures and artifact/guild reward consistency
  moved to [#58](https://github.com/LuminariMUD/Duris/issues/58). That transfer is
  not a fix. Keep its stale-capture, diagnostics, and exactly-once work there.
- [#57](https://github.com/LuminariMUD/Duris/issues/57) owns the reproduced PSP
  regeneration and movement over-cap defects. LR-07 must correlate the original
  movement report with that work, without assuming it proves the player's cause.
- The character-mechanics plan in [class-anchor.md](class-anchor.md), tracked by
  [#52](https://github.com/LuminariMUD/Duris/issues/52), is separate. These focused
  fixes do not depend on completing that project.

### Preserve memory authority

Follow [ADR 0002](../adr/0002-persistence-reset-memory-is-the-authority.md): live
character state is authoritative, saves follow capture order on the existing
writer, and the game loop does not wait for SQL. The ADR retains some durable
economy commands, including boons; the #58 branch narrows the artifact/guild
exception for epic-derived rewards. None of these commands authorizes adding
database approval to ordinary character changes.

The relevant failures have different causes:

- **Statistics:** `prepare_statistics()` captures live descriptors in memory.
  SQL and the daily file are outputs of that sample. The observed loss is in
  output identity/deduplication, not a reason to read gameplay state back from SQL.
- **Epic skills:** [epic_transaction.c](../../src/world/epic_transaction.c)
  changes the epic balance in memory and invokes the completion synchronously;
  its queued command records the ledger. A callback named `committed` does not
  mean training waits for a database commit. LR-04/LR-05 must preserve this path.
- **Artifact/guild rewards:** #58 documents pending captures sharing old state
  and SQL rejecting later rewards before completion publication catches memory
  up. That authority/ordering problem needs its own fix; do not fold it into
  statistics or add new revision fences here.

Proof must cover the real changed path: executable scheduler/repository checks
for statistics, command/callback and reconnect checks for gameplay, and observed
service or delivery results for host work. Source matches and configuration
values alone do not prove these outcomes.

## Work order and ownership

| Order | Work | Responsible role and dependencies |
| --- | --- | --- |
| 1 | LR-01 statistics | Server maintainer; isolate the failure before any historical recovery. |
| 2 | LR-02–LR-08 gameplay/help | Server/content maintainer; LR-03's level-30 policy needs command verification; LR-05 and LR-07 need reproduction. Other items can proceed independently. |
| 3 | LR-09–LR-11 lifecycle/connections | Server maintainer; preserve the existing guards, admission limits, and proxy trust rules. |
| Independent host track | LR-12–LR-15 and LR-20 | Host owner/backup custodian; access and specific production actions must be authorized. Prioritize restoring alert delivery before deliberately exercising backup failures. |
| Measured follow-ups | LR-16–LR-19 | Server maintainer plus tunnel/monitoring owner; change behavior only when measurement supports it. |

Record the assigned person when execution starts. These role assignments are not
claims that host work has already been requested or performed.
