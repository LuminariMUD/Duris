# Issue #534: bartender KILL bonus items and configurable withholding

Status: **implementation in progress; withholding and batch foundation ready for review**. Updated 2026-11-01.
Issue: [Duris #534](https://github.com/LuminariMUD/Duris/issues/534).

## Current implementation handoff

- Worktree: `/home/aiwithapex/projects/duris-issue-534-kill-rewards`.
  Branch: `branch/issue-534-kill-rewards`, stacked on the withholding commit
  `adbac1a9857f12f77cd2d8c27c4b79e9cf01eaab`. This is the authoritative working
  copy of this plan. The original checkout and all its staged work are preserved.
- Parent worktree: `/home/aiwithapex/projects/duris-issue-534-withholding`,
  branch `branch/issue-534-withholding`, originally based on master
  `0678df92a13991c4b0f7787863b80770ed8f42e0`.
  [PR #535](https://github.com/LuminariMUD/Duris/pull/535) is open for review.
- **Outcome:** deliver the specified bonus formula, personal recoverable batches,
  and 5–25% withholding with the 20% default. **Non-goals:** release/deployment,
  historical backfill, fixed iValue caps, and new configuration infrastructure.
- **Ablation:** reuse the existing property, percentile arithmetic, catalog,
  item snapshots, and completion machinery. Publish the independent withholding
  change first; stack the batch work on it. Fresh master already contains reward
  recovery changes absent from the original checkout's committed HEAD, so no
  uncommitted dependency needs importing. The historical inspection below is
  retained as context and must be checked against this integrated source.
- **Files for chunk 1:** `src/world/world_quest_policy.c`, its existing math
  header, `lib/duris.properties`, the reward policy test, the bartender reference,
  and this plan. **Proof:** reward-policy and dynamic-policy executables,
  documentation checks, full server build, formatting, and isolated catalog boots.
- Implemented: bounded/finite-safe normalization, effective-percent startup
  reporting, unchanged 20% default and tie algorithm, documentation and executable
  cases for every whole percentage, fractional/extreme/nonfinite inputs, and
  20-item pools at 5/20/25%. The general ceiling helper remains unchanged.
- Passed: `python3 tests/async/test_world_quest_reward_policy.py`,
  `python3 tests/async/test_world_quest_dynamic_policy.py`,
  `python3 tests/async/test_documentation_contract.py` (14 tests),
  `make -C src -j6`, `./scripts/format.sh --check`, and `git diff --check`.
  Build log: `bin/qualification/issue534/build.log`.
- Both MariaDB and flatfile builds passed. Five isolated full-world flatfile
  boots verified configured/effective percentages 5/5, 20/20, 25/25, 0/5, and
  100/25. Retained profiles were 7,275 at 5%, 6,105 at 20%, and 5,723 at 25%;
  all boots inspected 353 zones. Evidence and the reusable local probe are in
  `bin/qualification/issue534/catalog.log` and `catalog.py`.
- Further ablation: integrated master already routes both backends through
  `player_save_pipeline_submit_world_quest()`. Its flatfile repository prepares
  history and commits it with the materialized player state through the existing
  authority transaction. Reuse that path; the original flatfile findings below
  describe the older planning checkout and are superseded. Do not add another
  flatfile pending-file protocol or history reconciler. Pending state constants
  also changed: unsecured is 4 and history-pending is 5 on this baseline.
- Remaining: publish the batch foundation, implement saved quantity decisions and multi-root
  delivery/recovery on both backends, extend their focused tests/journeys, and
  publish dependent PRs. The complete goal remains open until those are qualified.

### Batch foundation checkpoint

The completion API now accepts a vector of detached roots, captures their trees
with remapped parent indexes, and admits the graph through one existing
completion transaction. The save pipeline now accepts multiple roots. Publication
checks each root's recorded ancestry, validates/restores all roots before new
attachments, recognizes roots already held by the actor, and cleans up all
detached roots for an offline actor. Restore materializes only the missing tree.
The existing SQL and flatfile repositories already handle multi-root graphs;
no new persistence protocol or migration is needed for this foundation.

Current gameplay still requests its original one-item batch. Bonus quantity
selection, its saved field/migration, and batch player feedback are the next
chunk; this foundation does not claim the requested reward formula is enabled.

Passed on the foundation:

- ASan/UBSan production publication and capture harness for SQL and flatfile,
  including two roots with children, a wrong root identity, failure on the second
  capture without submitting a partial graph, missing-root restoration, an
  already-attached root, repeat publication, offline cleanup, and wrong location.
- Save-pipeline regression with a second root and a save while publication is
  refused; reward-policy, XP feedback, target retries, and flatfile history tests.
- `tests/async/run_player_save_claim_mysql.sh` in its disposable MariaDB: two
  reward roots plus a child, history rollback, exact custody, replay, stale
  wallet rejection, UID collision, load filtering, and retained-state checks.
- MariaDB and flatfile server builds. Logs and SQL evidence are under
  `bin/qualification/issue534/` in this worktree.

The flatfile repository suite initially failed at `prepare PvP receipt`, before
reaching the quest fixture. The fixture never bootstrapped shared frag-cap state.
That independent five-line setup repair passes the unchanged full suite and is
published separately as [PR #538](https://github.com/LuminariMUD/Duris/pull/538),
branch `branch/fix-flatfile-quest-test-bootstrap`, commit `6df741257`.
Its equivalent commit `49b5435c1` is included here to unblock batch qualification.
The expanded multi-root flatfile fixture now passes, including the interrupted
authority commit, reload, single history count, and failed-history fallback
retaining unrelated items. `test_world_quest_remaining_unloaded.py`,
`test_player_item_snapshot_codec.py`, all 14 documentation checks, formatting,
and whitespace checks also pass.

No release tag has been created: these are review branches, not releases.
Master advanced separately through account recovery and racial-spell repairs;
those changes are not imported as uncommitted dependencies.

The requested change is one guaranteed completion item plus an independent 10%
bonus-item roll for each required kill after the first, and a configurable
top-value withholding percentage from **5% through 25%, inclusive**, defaulting
to **20%**. This plan selects those changes; the issue itself remains a record
of historical/current findings. The illustrative fixed iValue range of 25–45
in that discussion is not part of this implementation.

## Original planning baseline and integration dependency

Inspected the working tree on `branch/issues-500-506-bartender-bugfixes`, HEAD
`dc1457f722c4f42d5d11fc39c96fb67859a94de8`, including its existing staged reward,
history, ownership-publication, and save-pipeline changes. Those changes belong
to separate work and are not implemented by this plan. Before implementation,
identify their integrated revision and recheck the boundaries below. Preserve
their recovery fixes rather than implementing against the issue's older source.

- [world_quest.c](../../src/world/world_quest.c): `quest_kill()` calls
  `world_quest_start_reward()` at completion. The latter creates one object;
  `world_quest_deliver_reward()` publishes it and the scalar rewards. Completed
  KILL retries already retain XP/epic/money values in completed-task fields.
  `quest_kill_original` remains the saved total quota.
- [world_quest_policy.c](../../src/world/world_quest_policy.c):
  `load_reward_profiles()` already reads
  `world.quest.reward.top.withheld.percent`, defaults it to 20, and bounds it
  to 0–100. This is an existing configuration setting, not a new setting to
  invent. The catalog is built once; a property reload does not rebuild it.
- [world_quest_policy_math.h](../../src/world/world_quest_policy_math.h):
  `world_quest_reward_value_ceiling()` implements ceiling rounding, boundary
  ties, and the exception that avoids emptying a tied multi-item pool.
- [sql.c](../../src/sql/sql.c),
  [player_save_pipeline.c](../../src/player/player_save_pipeline.c), and
  [player_snapshot_repository.c](../../src/player/player_snapshot_repository.c):
  the staged SQL path commits history, status, and a detached reward graph
  together before publication. It accepts one root, despite storing a vector
  of item snapshots. Capture validation rejects a second root, and restore/
  publication assume a single root. Calling the finish operation once per item
  would incorrectly repeat completion/history and is not a valid extension.
- [player_snapshot.h](../../src/player/player_snapshot.h):
  `player_pending_world_quest` already carries `reward_items`, scalar rewards,
  completion metadata, and failure recovery state. Reuse this structure and
  the existing item ownership machinery.
- The flatfile `sql_world_quest_finish_async()` currently writes history and
  invokes the callback directly. The common pending-completion submission is
  disabled for `__NO_MYSQL__`, and the flatfile snapshot repository rejects
  `pending_world_quest`. SQL transaction behavior must not be attributed to
  this path. Reliable multi-item completion needs explicit flatfile coverage.

## Selected behavior

### Item quantity and timing

For a completed KILL quest with saved required quota `N >= 1`:

```text
items = 1 + sum(N - 1 independent rolls, each succeeding with probability 0.10)
E[items] = 1 + 0.10 * (N - 1)
P(items = 1 + k) = choose(N - 1, k) * 0.1^k * 0.9^(N - 1 - k)
```

- Perform exactly `N - 1` calls equivalent to `number(1, 100) <= 10` when
  finalizing a new completion. Each success adds one item. Use the production
  inclusive RNG contract; do not implement one combined roll or a 10% increase
  to the chance of receiving the base item.
- Deliver the entire batch personally at completion, through the existing
  ownership/persistence path. There are no interim corpse drops. The guarantee
  is an owed item retained for recovery when creation or storage is unavailable,
  not permission to finish with an empty reward.
- One kill gives exactly one item with no bonus RNG calls. Quotas 3, 5, 7,
  and 9 average 1.2, 1.4, 1.6, and 1.8 items. At nine kills, zero items is 0%,
  exactly one is 43.046721%, two or more is 56.953279%, and the maximum is nine.
  These are quantity probabilities assuming eventual successful delivery.
- Use the actual saved quota, including difficulty-scaled quotas above nine.
  Do not use the current progress counter, live mob count, current difficulty,
  or player level to recalculate the number of rolls. Invalid saved quotas must
  retain the task for diagnosis instead of permitting an unbounded loop.
- Each qualifying character rolls independently for their own completed quest.
  Preserve existing sharing and kill-credit rules: sharing currently copies
  progress and quota, so a recipient completes that shared assignment under
  the same quota-based formula. Do not copy a completed reward decision.
- ASK remains one personal completion item. XP, epics, mercenary payments,
  fees, allowances, quota assignment, abandonment, and ordinary mob loot keep
  their current rules. Scalar completion rewards execute once per completion,
  not once per item. Final-kill XP is not paid again during recovery.

### Item selection and withholding

Reuse this existing property in [duris.properties](../../lib/duris.properties):

```properties
world.quest.reward.top.withheld.percent=20.000
```

Support every whole percentage from 5 to 25, not only steps of five. Keep the
missing-key default at 20. Bound finite values to 5–25 before conversion to an
integer; fractional values truncate toward zero, matching the existing integer
policy. Nonfinite values use 20 with a diagnostic. This deliberately changes
old out-of-range settings: 0 becomes 5 and 100 becomes 25. Report the effective
percentage in the existing catalog startup diagnostic.

Read the effective percentage once when building the catalog. Apply it after
source eligibility and authored-quest exclusions, before level-specific pools
and zone scores. Keep the existing `ceil(pool_size * percent / 100)` rule,
boundary-tie inclusion, single-item behavior, and tie exception. The percentage
is a requested share of item prototypes, not a reduction to each item's stats
or iValue; ties and small pools can remove a different actual fraction.

Keep the accepted-level floor `itemvalue > 0 && 2 * itemvalue >= quest_level`.
Select every item independently from the same eligible zone/level pool, with
replacement: duplicate prototypes are allowed but must have distinct UIDs.
Keep the normal random-equipment fallback and reward flag adjustments for each
item. That fallback remains a separate generator, not a promise that all
possible generated rewards fall under the zone's percentile cutoff.

Changing withholding requires a server restart/catalog rebuild. Do not add
hot reload or a second configuration mechanism. Active assignments that have
not materialized rewards use the catalog of the running server; a durably
prepared batch keeps its selected items across restart/configuration changes.
Changing the pool also changes the existing pool-derived zone-selection scores.

## Implementation sequence

### 1. Preserve the reward decision

Add one explicit saved status field, `quest_reward_item_count`, with zero meaning
no new-format quantity decision. Keep the accepted quota in
`quest_kill_original`; do not hide the count in a map flag or overload the scalar
reward fields. Reset the new field when resetting/creating a quest and leave it
zero when sharing unfinished work. Replacement preserves the original quota
and progress, so it does not award or reroll items.

On a newly completed KILL quest, decide the count once while transitioning to
the existing completed/pending state, alongside the frozen scalar rewards.
Checkpoint that decision before publishing rewards or completion history.
If checkpoint admission or writing fails, keep the same decision in memory
and retry saving it; the failure must not call the bonus RNG again. Across
process loss, the durable checkpoint is authoritative. No completion reward
may be exposed from an uncommitted decision.

Carry the field through `pc_only_data`, the status-field registry, capture,
codec, load materialization, SQL load/save mappings, and flatfile snapshots.
Use an additive, guarded SQL migration and the next available snapshot version;
preserve decoding of earlier versions and initialize the field to zero. Cover
legacy import/default initialization too. Update the migration runner/schema
contracts required by the repository rather than selecting a migration number
in advance of integration.

Compatibility rules:

- An unfinished assignment loaded from before the change uses the new formula
  when it finishes, including already-earned progress.
- A legacy completed KILL task in `PLAYER_WORLD_QUEST_KILL_HISTORY_PENDING`
  with zero count retains its original one-item entitlement; do not roll a
  retroactive bonus. New completions enter that state with a positive count.
- Existing `PLAYER_WORLD_QUEST_REWARD_PENDING` and
  `PLAYER_WORLD_QUEST_KILL_REWARD_PENDING` states resume the already-secured
  items/scalar rewards without creating another batch. Completed history is
  never reopened. ASK uses a one-item decision through the shared batch path.

### 2. Prepare and commit one batch

Extend the existing completion API to take multiple detached reward roots.
Create exactly the saved number of items using `quest_item_reward()`. All must
pass the existing UID, ownership, and crumble-loot checks before admission.
If any item cannot be created or admitted, clean up every uncommitted detached
object, retain the completed task/count, and publish no partial batch. A failed
attempt before durable batch admission may retry item generation; it cannot
reroll the saved number of items. After admission, retry the saved item graph,
not the item selector.

Capture roots into the existing `reward_items` vector, remapping parent indexes
for each tree and preserving root markers. Extend capture, encoded-size limits,
UID uniqueness checks, repository claims, materialization, and publication to
accept multiple roots. A container's children are graph members, not additional
quest rewards. Keep object/byte limits; reaching them defers the whole reward
instead of silently shortening it.

For SQL, commit one history record and the complete item graph with the player
after-image. Preserve transaction failure recovery, stale-save protection,
unloaded-component checks, and committed-owner verification. Hydrate ownership
for all roots before attachment; publication retry must recognize roots already
attached and never grant them again. A disconnected player receives committed
items on login. Restore all missing detached roots from the committed snapshots.

Keep the existing single history row per quest. Its legacy `reward_vnum` and
description can describe the base item; document that they are not an exhaustive
inventory of bonus items. Use the item snapshots/UIDs and existing reward logs
to account for the batch. Do not add one history row per bonus item or expand
the history schema into a separate reward ledger.

For flatfile, reuse the integrated completion/save boundary and its existing
authority transaction for prepared history, player state, and item ownership.
Extend only the remaining single-root assumptions. Preserve original completion
metadata and replay matching so a crash cannot consume a second allowance or
lose the batch. Prove the full batch through this real backend; do not add a
second pending-file protocol or assume two independent renames are a transaction.

Only after the batch and completion are secured should the normal completion
callback announce received items, pay scalar rewards once, clear the quest,
and update GMCP. Keep feedback accurate for zero bonus successes, multiple
items, deferred delivery, and already-secured recovery.

### 3. Bound the existing withholding configuration

Change the property normalization in `load_reward_profiles()` to the selected
5–25 range and keep the checked-in/default value at 20. Reuse the existing
ceiling algorithm without changing its tie behavior. Its general mathematical
helper can retain 0/100 test coverage; enforce the narrower operator policy at
the configuration boundary. Add the effective percentage to the current
catalog log, then build all per-level pools and weights from that result.

Update [BARTENDER_QUESTS.md](../reference/BARTENDER_QUESTS.md) and the property
comment with the completion formula, personal batch timing, duplicate-item
possibility, bounds/default, rounding, restart requirement, and pending-task
compatibility. Correct the reference's old single-item and recovery statements
against the integrated code. Update this plan with actual implementation and
validation evidence when that work is performed.

## Verification and acceptance

Use executable production paths with controlled RNG and persistence failures;
source-string assertions or a Monte Carlo average alone cannot prove delivery.

1. **Quantity:** for `N=1`, no bonus RNG call and exactly one root; for `N=9`,
   exactly eight rolls and 1/2/9 roots for zero/one/all successes. Test values
   10 and 11 at the success boundary, quotas 3/5/7 and a valid quota above nine,
   and an invalid quota. Enumerate the eight binary outcomes with their weights
   to verify the nine-kill probabilities. Count RNG calls again on retries:
   they must stay unchanged. ASK always has one root and no bonus roll.
2. **Configuration:** missing/20 defaults agree with the baseline catalog;
   test 5, 25, an interior value such as 17, below/above bounds, fractional and
   nonfinite values. On 20 distinct values, 5/20/25% withhold 1/4/5 prototypes.
   Cover ceiling rounding, boundary ties, all-equal multi-item and single-item
   pools, authored quest exclusions, and level-31/50 floors. Prove every bonus
   item uses the same pool and that a property reload alone leaves it cached.
3. **Decision compatibility:** save/load the count on both backends; load old
   snapshot/SQL defaults; complete an old unfinished quest with the new rule;
   recover old completed states with one item/no retroactive bonus. Exercise
   sharing and free replacement without copying or rerolling a decision.
4. **Whole batch:** fail creation on a later item, snapshot capture, ownership
   validation, queue admission, database commit, and flatfile writes. Retain
   the same quantity decision, no success message, and no partial usable reward.
   Include unloaded inventory, count/byte limits, repeated VNUMs with distinct
   UIDs, and a root containing child items.
5. **Replay/restart:** restart after the quantity checkpoint, after durable
   batch commit but before publication, and at flatfile history reconciliation.
   Also retry partial live publication and disconnect before the callback.
   Verify the exact root UIDs/count, one history entry/allowance consumption,
   one scalar payout, and no repeated final-kill XP. Include another save before
   publication, since a stale snapshot must not erase committed reward items.
6. **Gameplay:** run isolated ASK, one-kill, and nine-kill journeys with zero,
   one, and multiple bonus successes. Include grouped credit, level changes
   after acceptance, and settings 5/20/25 on separate boots. Inspect durable
   inventory and history on both MariaDB and flatfile after relog/restart.

Extend the existing reward policy/publication, save-pipeline, snapshot codec,
flatfile history, SQL claim, and dual-backend journey harnesses. The current
publication harness's two snapshots represent one root plus a child; add actual
multiple-root cases. Replace the reward-policy assertion that every KILL quest
pays exactly one item, preserving the ASK and one-kill controls. Register new
cases in the applicable test runners without duplicating their infrastructure.

Planned focused commands after implementation:

```sh
python3 tests/async/test_world_quest_reward_policy.py
python3 tests/async/test_world_quest_reward_publication.py
python3 tests/async/test_world_quest_xp_feedback.py
python3 tests/async/test_world_quest_target_retries.py
python3 tests/async/test_world_quest_remaining_unloaded.py
python3 tests/async/test_player_save_pipeline.py
python3 tests/async/test_player_item_snapshot_codec.py
python3 tests/async/test_flatfile_player_repository.py
python3 tests/async/test_flatfile_world_quest_history.py
make -C src
./scripts/format.sh --check
python3 tests/async/test_documentation_contract.py
git diff --check
```

Also run the SQL claim harness via `tests/async/run_player_save_claim_mysql.sh`
inside its disposable database fixture, and the expanded
`tests/async/run_world_quest_dual_backend.py` for both backends and the reward
failure/crash cases. Use that runner's current CLI when implementing. Record
exact commands, scenario coverage, migration rerun/backward-load results, and
any unavailable checks; a build or stubbed test is not a runtime qualification.
Compiled artifacts belong under `bin/`. CI is not a substitute for these checks.

## Completion boundary

Implementation is ready for review only when the formula, inclusive 5–25 bounds,
20 default, existing eligibility rules, legacy-task compatibility, and complete
batch recovery are proven by the checks above. Keep the fixed 10% bonus chance
in code; no bonus-chance property, fixed iValue cap, per-kill drops, new difficulty
curve, hot-reload subsystem, or historical reward backfill is required.

The original planning task created only this document. It did not change game behavior,
apply migrations, deploy, commit/push, or close #534. Production migration and
deployment remain separate authorized work. For the eventual rollout, apply the
additive schema change before starting the new binary, retain the default 20%,
and inspect the effective catalog setting. Reverting the percentage to 20 is
independent of reverting code; an older binary must not be started on new-format
pending batches without a tested compatibility/drain procedure.

## Planning validation, 2026-11-01

Re-read issue #534 and the current working-tree paths identified above. The
document specifies both requested changes, delivery timing, property semantics,
integration dependencies, persistence/compatibility work, and executable
acceptance criteria. `python3 tests/async/test_documentation_contract.py` passed
all 14 checks, including maintained Markdown links and anchors. Whitespace
checks passed for the new document and tracked diffs. The pre-existing staged
diff retained SHA-256
`44e6a875fc75ebb0d088bec1dd0d6ad472044219ea0b153f0ea8b18ff039e948`;
there are no tracked unstaged changes from this planning task.

Only this new plan was written. The implementation checks listed above have
not been run for #534, and no build, gameplay, or persistence qualification is
claimed for the proposed behavior.
