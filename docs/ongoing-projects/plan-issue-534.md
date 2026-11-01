# Issue #534: bartender completion rewards

Status: **implementation and local qualification complete; delivered through
PRs #535, #538, #539, and #541**.
Updated 2026-11-01.
Issue: [Duris #534](https://github.com/LuminariMUD/Duris/issues/534).

## Outcome

A completed KILL assignment owes one guaranteed personal item plus one independent
10% bonus-item roll for each required kill after the first. A one-kill assignment
therefore pays one item; nine kills pay `1 + Binomial(8, 0.1)`, averaging 1.8 items.
At nine kills, exactly one item has probability 43.046721%, two or more 56.953279%,
and zero 0%, assuming eventual successful delivery. The complete batch arrives
at completion. There are no interim corpse drops.

`world.quest.reward.top.withheld.percent` now accepts whole percentages **5–25**,
inclusive. The checked-in setting is now **5%**, following the owner's follow-up;
the missing-key fallback remains **20%**. Finite values are clamped before conversion;
fractions truncate toward zero. Nonfinite values use 20 with a diagnostic. The
catalog startup log reports the effective percentage. A change takes effect on
restart, when the cached catalog is rebuilt.

The accepted-level iValue floor, source/quest exclusions, percentile ceiling
rounding, boundary ties, and tie exception retain their existing rules. Each
item independently selects from the same accepted zone/level pool, with
replacement; repeated prototypes have distinct UIDs. The existing random-equipment
fallback and reward flag adjustments apply to every item. No fixed iValue cap,
bonus-chance setting, new difficulty curve, or historical reward backfill was added.
ASK still pays one item. Scalar rewards, fees, allowances, sharing eligibility,
kill credit, and quota assignment retain their rules.

## Git and worktrees

Delivery order is [#538](https://github.com/LuminariMUD/Duris/pull/538),
[#535](https://github.com/LuminariMUD/Duris/pull/535),
[#539](https://github.com/LuminariMUD/Duris/pull/539), then
[#541](https://github.com/LuminariMUD/Duris/pull/541). The active Master ruleset
requires linear history, so the PRs use squash merges. Each child was rebased
onto master after its parent landed, with an explicit lease protecting the
published head. Git dropped the duplicate #538 fixture repair from #539.

The complete merge simulation matched reviewed #541 head `b89598dec` exactly.
Both restacks also preserved their reviewed file trees exactly; this final
handoff update changes documentation only. Fresh reward policy, completion/XP
on both backends, sanitizer publication, flatfile repository, snapshot capture,
14 documentation checks, and both backend builds passed on the combined source.

The historical review worktrees were `duris-review-{535,538,539,541}` under
`/home/aiwithapex/projects/`; the original implementation worktrees were
`duris-issue-534-{withholding,kill-rewards,bonus-policy}` and
`duris-flatfile-test-bootstrap`. Their review, qualification and merge-check
logs were copied to the main checkout's ignored
`bin/merge-prs-535-541-20261101/evidence/<worktree-name>/` before cleanup.
Original pre-review heads remain in
`branch/archive-pr{535,538,539,541}-before-review-20261101`.
The clean feature/review worktrees and merged remote branches can be removed
after the final merge.

The original checkout's unrelated staged work and untracked plan are preserved.
Production migration/deployment and release tagging remain separate work.

## Implementation and ablation decisions

The work follows the [ablation skill](../../.agents/skills/ablation/SKILL.md):
reuse the existing property, catalog, completion transaction, item graph, and
ownership publication. Current master already had recoverable flatfile completions;
the older planning checkout did not. A second flatfile protocol, reward ledger,
hot-reload service, and separate asynchronous decision-saving stage were omitted.

The independent adversarial review posted two reproduced findings directly on
#541 and repaired them in separate commits: `f065dae30` updates the stale
version-13 capture test and proves a nonzero frozen count survives production
capture/codec round trip; `d2e245c34` locks the shared `make world` freshness check
and generation after concurrent backend journeys raced on `areas/tworld.*`.
The latter extends the existing parallel-journey regression with two independent
make processes. Neither repair adds a new persistence path or fixture framework.

- [world_quest.c](../../src/world/world_quest.c) rolls once from the saved
  `quest_kill_original`, freezes `quest_reward_item_count`, prepares exactly that
  many detached roots, and announces every received item after publication.
  XP/epic/money completion effects execute once per task, outside the item loop.
  Final-kill XP is not paid again on recovery. The latest master's completion
  banner and explicit "in your inventory" wording are preserved for each item.
- The new count is carried through `pc_only_data`, STATUS capture/load mappings,
  SQL persistence, flatfile snapshots, and supported snapshot-version upgrades.
  Reset/creation clear it; sharing unfinished work leaves an unrolled decision.
  Replacement keeps the original quota/progress. Group members roll independently.
- Failed creation of a later item cleans up the entire uncommitted batch and
  requests a STATUS checkpoint of the completed task/count/scalar values. Retry
  reuses the quantity. Before a durable batch exists, generation may be retried;
  after commit, recovery uses the saved item graph and UIDs.
- [sql.c](../../src/sql/sql.c) accepts multiple roots, captures their trees with
  remapped parent indexes, and submits one existing completion transaction.
  [player_save_pipeline.c](../../src/player/player_save_pipeline.c) admits the
  complete graph with status/history. SQL and flatfile repositories already
  support these graphs. Object/byte limits defer the whole reward rather than
  silently reducing it. Quotas outside 1–4096 are retained for staff diagnosis,
  bounding the loop and every possible quantity by the snapshot object limit.
- Publication verifies each root's recorded ancestry and owner, restores only
  missing trees, recognizes already-attached roots, and validates all roots before
  new attachments. An offline actor's detached bodies are removed; committed
  inventory is restored on login. A container's children are graph members,
  not additional quest rewards.
- [world_quest_policy.c](../../src/world/world_quest_policy.c) normalizes the
  existing percentage once during catalog construction, before per-level pools
  and zone scores. The general percentile helper retains its existing 0/100
  mathematical behavior; the operator setting is bounded to 5–25.

The single history record describes the base item; it is not an exhaustive list
of bonus items. Item snapshots, UIDs, and existing reward logs account for the
batch. There is no history entry per bonus item.

## Migration and compatibility

[0058_world_quest_reward_count.sql](../../migrations/immutable/0058_world_quest_reward_count.sql)
(sequence 59) adds signed `player_data.quest_reward_item_count INT NOT NULL DEFAULT 0`.
Its [verifier](../../migrations/immutable/0058_world_quest_reward_count.sh) checks the
column definition. The guarded migration preserves positive decisions on rerun.
Apply it before starting the new binary. Migration hashes, runtime head/history,
and independently measured MySQL 8/MariaDB 10.11 metadata fingerprints are
synchronized in the manifest and compiled runtime contract.

Snapshot wire version **14** appends the count; supported pre-14 snapshots and
legacy pfile imports initialize it to zero. The legacy 14-value quest payload is
unchanged. Unfinished old assignments use the new formula when they finish.
Already-completed legacy tasks with zero count retain their one-item entitlement.
Unsecured legacy state 4 retains its existing final-XP compatibility behavior;
history-pending state 5 freezes the remaining values. Secured states 2/3 resume
remaining effects without new generation or history.

The schema is additive, but older binaries cannot read version-14 snapshots.
Do not roll back a live binary across that boundary without a tested conversion
or drain procedure. The previously sealed online-migration flags do not authorize
this migration or a 59-step manifest. Production deployment remains separate work.

## Acceptance and evidence

All evidence below comes from local executable tests and isolated disposable
world/database fixtures. No production state was used. Original implementation
logs and independent review logs were preserved under the evidence directory
listed above. The `duris-review-541/review/` evidence includes
both engine compatibility/drift suites and six backend journey results (ordinary
rewards, nine-item maximum, and failed-preparation/committed-crash recovery).
The six-test snapshot suite, production capture/count round trip, both server
builds, repository/claim tests, migration contracts, quest regressions and
two-process world-generation test all passed after the review repairs.

1. **Quantity:** production-body tests enumerate all 256 nine-kill patterns,
   verify the 10/11 roll boundary, eight RNG calls, mean 1.8 and the one-item
   probability, plus one-kill/no-roll, an 18-kill control, and invalid quotas.
   Completion tests produce 1/2/9 items and one scalar callback. A second-item
   creation failure cleans up the batch, retains its count, and awards no repeat XP.
2. **Configuration:** every whole setting 5–25, missing/default 20, fractional,
   extreme and nonfinite inputs pass. Twenty distinct values withhold 1/4/5 at
   5/20/25%. Rounding, ties, all-equal/single-item pools, authored quest exclusions,
   and level-31/50 floors remain covered. Five full-world boots verified 5/20/25
   and out-of-range 0→5 and 100→25 across 353 zones. Retained profiles were
   7,275 / 6,105 / 5,723 at 5 / 20 / 25 in the withholding worktree.
3. **Compatibility:** snapshot-14 round trips preserve a positive count;
   supported older versions default it exactly once and reject a version-14
   field under a version-13 header. SQL old rows default to zero and migration
   replay retains count 4. Both repositories save/load count 2 with multiple roots.
4. **Whole batch:** sanitizer tests execute production capture/publication for
   both backends, including multiple roots with children, wrong ownership/ancestry,
   missing-root restoration, already-attached roots, refusal, offline cleanup,
   and byte/object-limit rejection without partial submission. SQL tests cover
   rollback, replay, stale-wallet refusal and UID collision. The flatfile fixture
   interrupts the authority commit and proves reload, one history count, and
   preservation of unrelated items after failed-history fallback.
5. **Restart/crash:** both backend recovery journeys fail creation on item two,
   checkpoint/restart the frozen count of three, force future rolls to zero, and
   retry the same count. They then kill the isolated server after transaction
   commit but before publication, restore all three exact UIDs, claim remaining
   effects without generation/repeated final XP/history, and restart once more.
   Each journey performs four boots. Chaos login also changes the actor's current
   level; the saved decision remains unchanged.
6. **Gameplay/group credit:** ordinary ASK and one-kill commands pay one item;
   nine kills with zero/one successes pay one/two. Each case saves/restarts and
   checks exact UIDs and one history entry. A fresh maximum case delivers nine
   distinct items for nine kills and preserves them on restart. Both backends
   pass. The production death-hook regression gives two same-room group members
   independent personal quantities of one and nine, sixteen rolls, two scalar
   callbacks, and no repeated killer/victim credit.

Successful journey logs:

- `rewards-flatfile-qualified.log`, `rewards-mariadb-qualified.log`: four cases,
  five boots per backend.
- `max-flatfile-qualified.log`, `max-mariadb-qualified.log`: nine items, two boots
  per backend, using `DURIS_WORLD_QUEST_REWARD_CASES=30:1:9:8`.
- `recovery-flatfile.log`, `recovery-mariadb.log`: generation failure, checkpoint,
  forced crash, claim and final restart, four boots per backend.

The first matrix tried a level-50 nine-kill walking fixture, but could not find
ten eligible fully walkable copies. The maximum-batch journey uses a valid
level-30 assignment in a fresh fixture; accepted-level floor tests still cover
31 and 50. Earlier failed fixture/debugger attempts are not qualification results.

Pre-integration qualified server SHA-256:

- MariaDB: `6c4a0c2d7ab3d9728db610b93af773fe49bf3e6fbf3e791407a0b3e9546f6ff5`.
- Flatfile: `dde85c83be42556b6e681a122bd4be5b2258608ac50b2f6c36d0c7e2aceb2ef9`.

Master integration preserved reward logic and adopted the current inventory
feedback. Both builds and the focused completion/group, policy, publication,
save-pipeline, documentation, format and whitespace checks pass afterward. Fresh
one-kill/restart smoke journeys also passed on both integrated binaries, with two
boots each (`integrated-smoke-flatfile.log`, `integrated-smoke-mariadb.log`).

Final integrated server SHA-256:

- MariaDB: `5f0e11a18d63075ae7f67ff12cda4b32f0334c31393ec1020d2ceedf6c25d693`.
- Flatfile: `ec8b297606a486abef6ba39eecbd0a46ae3526091742e908759c2d6a5f75c611`.

All required implementation and local qualification work is complete. No test
process remains to resume. Issue #534 is complete with this delivery.
Production migration/deployment and any release tagging are separate work.

## Reproduce verification

The following focused checks passed during implementation; final integration
reused valid results and reran the checks affected by its changes. Commit hooks
also passed formatting and clang-tidy. External CI was not used as a completion gate.

```sh
python3 tests/async/test_world_quest_reward_policy.py
python3 tests/async/test_world_quest_dynamic_policy.py
python3 tests/async/test_world_quest_reward_publication.py
python3 tests/async/test_world_quest_xp_feedback.py
python3 tests/async/test_world_quest_target_retries.py
python3 tests/async/test_world_quest_remaining_unloaded.py
python3 tests/async/test_player_save_pipeline.py
python3 tests/async/test_player_load_pipeline.py
python3 tests/async/test_player_item_snapshot_codec.py
python3 tests/async/test_player_snapshot_capture.py
python3 tests/run_regression_tests.py --jobs 4 --match snapshot
python3 tests/async/test_flatfile_journey_build_isolation.py
python3 tests/async/test_flatfile_player_repository.py
python3 tests/async/test_flatfile_world_quest_history.py
python3 tests/async/test_immutable_migration_runner.py
python3 tests/async/test_runtime_boot_compatibility.py
python3 tests/async/test_data_lifecycle_manifest.py
python3 scripts/validate_runtime_compatibility.py
python3 scripts/validate_data_lifecycle.py
tests/async/run_player_save_claim_mysql.sh
RUNTIME_DB_IMAGE=mysql:8.0 tests/async/run_runtime_compatibility_mysql.sh
RUNTIME_DB_IMAGE=mariadb:10.11 tests/async/run_runtime_compatibility_mysql.sh
make -C src -j6
make -C src -j6 PERSISTENCE_BACKEND=flatfile DMS_BINARY="$PWD/bin/server/dms_flat"
./scripts/format.sh --check
python3 tests/async/test_documentation_contract.py
git diff --check
```

Run the ordinary, maximum and recovery journeys using the matching backend binary:

```sh
for quest_backend in flatfile mariadb; do
    quest_binary="$PWD/bin/server/dms_new"
    if [ "$quest_backend" = flatfile ]; then quest_binary="$PWD/bin/server/dms_flat"; fi
    for quest_journey in rewards reward-recovery; do
        DURIS_WORLD_QUEST_BACKEND="$quest_backend" DURIS_WORLD_QUEST_BINARY="$quest_binary" \
        DURIS_WORLD_QUEST_JOURNEY="$quest_journey" \
        python3 tests/async/run_world_quest_dual_backend.py
    done
    DURIS_WORLD_QUEST_BACKEND="$quest_backend" DURIS_WORLD_QUEST_BINARY="$quest_binary" \
    DURIS_WORLD_QUEST_JOURNEY=rewards DURIS_WORLD_QUEST_REWARD_CASES=30:1:9:8 \
    python3 tests/async/run_world_quest_dual_backend.py
done
```

The runners use environment variables, not CLI flags; they create disposable
loopback accounts/state/databases, never read the checkout's `.env`, and remove
their temporary servers and containers. Compiled artifacts and evidence stay
under ignored `bin/` paths. The updated player/operator reference is
[BARTENDER_QUESTS.md](../reference/BARTENDER_QUESTS.md).
