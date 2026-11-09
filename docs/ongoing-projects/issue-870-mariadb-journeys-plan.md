# Issue #870: finish the MariaDB journey conversion

Status: implementation in progress; baseline reconciled, launch/shop repairs under test.
Date: 2026-11-09.
Issue: [#870 — Follow-ups from the flat-file backend removal](https://github.com/LuminariMUD/Duris/issues/870).
Branch: `branch/issue-870-mariadb-journeys`.
Local worktree: `/home/aiwithapex/projects/duris-worktrees/issue-870-mariadb-journeys`.
Remote: `origin` (`LuminariMUD/Duris` on GitHub); no server worktree is required.

## Outcome

Complete every item in the issue's current **Still open** section: convert the
11 hard-coded scripts/helpers and four item journeys to MariaDB, finish the
14 partially converted scripts, and replace misleading test/build names and
their active references. Preserve the supported gameplay, persistence,
restart, failure and protocol assertions, and prove them against disposable
MariaDB databases. A script that merely boots or compiles is not qualified.

This document is the implementation checklist and evidence record. Update it
as work completes; keep generated reports, transcripts and binaries under
ignored `bin/` paths. Do not create a second tracker or a new test framework.

## Baseline and dependencies

The worktree starts at `81c969a63d82323f3c4e696bdb1cb6af8a07485c`, the inspected
head of [#880](https://github.com/LuminariMUD/Duris/pull/880). It includes
[#873](https://github.com/LuminariMUD/Duris/pull/873) and
[#874](https://github.com/LuminariMUD/Duris/pull/874). All three PRs were open
when this plan was written; their existing changes are dependencies, not new
implementation work for this branch:

- #873 records departure/save intent, with migration 0062 and restored login behavior.
- #874 fixes refused-save departure cooldowns and corpse deletion during boot.
- #880 removes dead code and some obsolete branches and updates current docs.

`origin/master` is `ce0767d30` at implementation start. Merge `4f216b90c`
incorporates it without rewriting the published stack. Documentation conflicts
retain the pending #870 journey descriptions and historical item report while
accepting current MariaDB-only guidance. The baseline reconciliation is a
separate prerequisite [PR #887](https://github.com/LuminariMUD/Duris/pull/887)
so conversion PRs show only their own changes. The historical item evidence JSON
is retained with its report; it does not qualify the current backend.

The [issue's verification comment](https://github.com/LuminariMUD/Duris/issues/870#issuecomment-6737821455)
reports 899 regression passes but an interrupted DB run with a nexus failure,
and no standalone runtime proof for several conversions. These are historical
results, not proof for the final branch. The issue's claim that scripts are
outside the suites is also incomplete: `tests/run_db_tests.sh` already invokes
several of the listed journeys. Inspect actual runner membership.

Two #880 findings were confirmed in its source and must be resolved either
upstream or here, without applying the repair twice:

- [Launch gate](https://github.com/LuminariMUD/Duris/pull/880#discussion_r4511763311):
  its MariaDB branch still indexes `FLATFILE_STATE_DIR` while finding snapshots.
- [Shop bootstrap](https://github.com/LuminariMUD/Duris/pull/880#discussion_r4511763322):
  it still asserts that the removed shopkeeper catalog file exists. Compare
  persisted SQL shopkeeper/item rows across boots instead.

## Non-goals and ablation decisions

- No flat-file backend, fallback, replacement binary inspector, ORM, generic
  fixture framework, new backend selector, or parallel implementation.
- No gameplay rebalance, persistence redesign, production migration, deployment,
  wipe, or live-account testing. No new schema is expected for test conversion.
- Reuse `mariadb_authority()`, `inspect_authority()`, the existing fixture and
  client helpers, and `with_disposable_mariadb.sh`. Extend an existing helper
  only for an actual shared requirement; keep one-off SQL beside its scenario.
- Keep supported behavioral assertions. Remove an obsolete backend-specific
  mechanism only after its useful assertion has a SQL/gameplay replacement,
  or explain why the assertion exclusively concerned the retired backend.
- Retire the old in-game `--flatfile-rejection` pwipe scenario: that backend
  now fails configuration before gameplay exists. Retain the invalid-mode
  checks already in `test_persistence_mode.py` and the valid MariaDB pwipe cases.
- Keep `src/no_mysql` and the harnesses that still require it. Preserve historical
  reports and existing recovery/archive tools; this is not a repository-wide
  purge of every occurrence of the word “flatfile.”
- Preserve the assassin comparison and named-set compatibility purposes until
  their supported requirements are traced. Do not silently remove hard cases
  to make the conversion pass, and do not add historical-backend support.

These choices remove duplicate infrastructure and impossible gameplay paths
while retaining the issue's complete supported behavior and proof obligations.

## Files and implementation order

Unless a full path is shown, Python files below are in `tests/async/`.
Each batch should produce a reviewable commit with its focused runtime proof.

### 1. Establish the disposable test environment and finish partial conversions

- [x] Confirm the working tree, upstream heads and current instructions. Verify
  local compiler, Docker, MariaDB client, Python and Node availability. Use the
  existing disposable wrapper; never source or copy a game `.env` for tests.
  Build this checkout's server and generate any required private world fixture
  under `bin/`; do not borrow mutable runtime state from another checkout.
- [ ] Repair `run_pwipe_launch_gate_journey.py`: remove snapshot discovery,
  preserve admission/denial and unchanged-account/player-state assertions with
  SQL checks, and run launch/copyover paths.
- [ ] Repair `run_shop_bootstrap_journey.py` if #880 has not already done so;
  retain stock identities, contents and revision comparisons across cold boots.
- [ ] Finish `run_news_prompt_journey.py` and
  `run_issue213_onboarding_journey.py`: use SQL for saved news/onboarding state
  and retain the reconnect and command/protocol assertions.
- [ ] Finish `run_death_level_projection_journey.py` and
  `run_corpse_haul_count_cap_journey.py`: retain saved level, account projection,
  item count and wallet checks; remove unreachable inspector fallbacks.
- [ ] Finish `run_cleric_rebalance_journey.py` and
  `run_innate_aura_keywords_journey.py`: keep SQL seeding and saved-affect expiry,
  specialization, command and keyword checks. Remove unused inspector/state args.
- [ ] Finish `run_telemetry_player_journey.py`: remove unused state configuration,
  retaining the local receiver and its gameplay/copyover/performance assertions.
  Use its local test mode; do not send synthetic events to live analytics.
- [ ] Finish `test_corpse_trap_restart_journey.py`: use SQL item/trap state and
  preserve death, nested contents and restart behavior.
- [ ] Finish `test_information_cache_journey.py`: remove file publication and
  select MariaDB by default; retain cache refresh and concurrent reader checks.
- [ ] Finish `test_flight_network_journey.py`: use SQL progress, correct the
  default and build invocation, and retain reconnect/interruption/copyover modes.
- [ ] Finish `test_shop_multi_buy_journey.py`: retain wallet, item identities,
  parentage and cold-restart assertions. Translate any still-relevant delayed
  writer/offline-sale case using the existing MariaDB fault patterns; a file
  lock is not a MariaDB writer stall. Remove only exclusively retired semantics.
- [ ] Finish `test_norent_key_rent_journey.py` and
  `test_artifact_owner_restart_journey.py`: remove inspector fallbacks and retain
  rent/crash/copyover, owner conflict, custody and restart assertions.

Proof: run each changed journey's supported modes. Several already have DB
runner entries; record which modes those entries cover and run the others
explicitly. Retain direct SQL checks of committed state after saves/restarts,
with existing bounded settling patterns where writes are asynchronous.

### 2. Convert the standalone gameplay, protocol and timing runners

- [ ] `run_racial_pulse_journey.py`: replace inspector seeding with the existing
  MariaDB authority and player/skill setup; preserve rebalance and reload cases.
- [ ] `run_cast_timing_probe.py`: replace backend/state setup and preserve its
  trace-derived timing report, pulse budget and requested cast count.
- [ ] `run_divine_refusal_journey.py`: replace the embedded snapshot mutation
  and obsolete fixture compilation with SQL promotion/seeding; test enabled
  and disabled refusal, retry, exempt targets and mixed orders.
- [ ] `run_spellcast_racial_multiplier_journey.py`: seed MariaDB and run every
  configured multiplier; keep ordinary mortal casts and timing comparisons.
- [ ] `run_weapon_actions_journey.py`: seed MariaDB and preserve the existing
  family, enable/disable, completion, cancellation and reaction matrix.
- [ ] `run_copyover_runtime_journey.py`: use one MariaDB setup for ordinary and
  Redis-fault paths. Preserve original sockets, plain/MCCP, TLS/WebSocket paths
  present in the runner, reconnect, failure/success, fresh/full-world and
  non-root cases. Reuse its existing private Redis fault setup.
- [ ] `test_discord_game_journey.py`: seed the synthetic player and staff in
  MariaDB and retain petition/ptell, save and copyover assertions. Use the
  companion bridge's `scripts/testing/duris-game-sink.js` via `--node-driver`;
  verify the actual checkout/path and Node dependencies before running. The
  local sink must remain isolated from the real Discord service.
- [ ] `scripts/validate_colorization_journey.py`: replace inspector setup and
  saved-state dependencies with MariaDB; retain ANSI, paging, rendering,
  permission and persistence checks and its synthetic report.
- [ ] `run_pwipe_runtime_journey.py`: remove the obsolete flat-file rejection
  function, option and dependent argument validation. Preserve supported
  MariaDB/Redis/restore/reward and website modes. Verify affected argument
  combinations and run supported cases touched by the cleanup; provision
  the existing companion website test fixture for its integration mode.

Proof: use the real 250 ms clock for wall-clock/timing comparisons and keep
such runs away from heavy concurrent compilation/tests. Exercise existing
case matrices explicitly; one default invocation is not proof of all flags.

### 3. Convert named-set support and the assassin comparison

- [ ] `named_set_gameplay.py`: replace `NamedSetGame`'s removed snapshot fixture
  compilation, state-directory requirement and inspector reads with the existing
  MariaDB authority. Seed/promote synthetic actors through SQL and read item
  identity, containment, provenance, affects and pets from their owning tables.
  Keep database lifetime across required boots and clean it up after the journey.
- [ ] Update and execute its concrete consumers:
  `run_named_set_edit_clone_journey.py`, `run_named_set_pet_journey.py`,
  `run_named_set_rollback_journey.py`, `run_named_set_shop_journey.py`,
  `run_named_set_transfer_journey.py`, and `run_named_set_wear_journey.py`.
  Also check `run_named_set_mariadb_chest_journey.py` and
  `run_named_set_report_journey.py`, which import the module's gameplay helpers.
  Reuse the chest journey's existing SQL/provenance patterns and generate the
  isolated named-set world through the existing preparation path. Trace the
  rollback runner's compatibility binary before changing its assertions.
- [ ] `run_assassin_balance_journey.py`: replace snapshot seeding/inspection
  with SQL while keeping deterministic RNG and the original/cleansed/revised
  comparison, levels/races, poison/cure and movement scenarios. Inspect the
  pinned `24a2776f13a2f3580c91f945743b09f80144b829` source and cleanse-only patch
  to select their existing MariaDB build/schema path, then prove equivalent
  synthetic actors and gear in all variants. Keep source/binary hashes and
  cache validation truthful; do not relabel current code as a historical build.
- [ ] If either historical comparison cannot be run on its existing MariaDB
  path, record the exact incompatibility and resolve the coverage requirement
  explicitly before claiming completion. A skip or a restored flat-file backend
  does not satisfy this batch.

Proof: exercise all affected consumers and preserve each comparison's purpose.
Update only fixture code/manifests used by these consumers. Remove a superseded
fixture only after checking all callers; do not retain it as a compatibility shim.

### 4. Convert the four live item journeys together

- [ ] `run_item_pilot_journey.py`: make its existing `Server` helper use the
  disposable MariaDB environment. Replace `seed-combat`, `seed-item` and
  `seed-item-operator` inspector operations with SQL or existing gameplay
  fixture operations. Read `artifact_mana` instead of decoding domain files.
  Preserve identity, reserve/version, enabled/disabled, interruption, crash,
  restart and family-specific behavior.
- [ ] `run_item_mana_encounter_journey.py`: retain sustained NPC combat,
  immediate player-encounter refusal, recharge and committed reserve checks.
- [ ] `run_item_config_journey.py`: retain real operator toggles/reload,
  pending-action cancellation, invalid configuration, revision/clamping and
  private metrics checks using SQL-backed state.
- [ ] `run_item_overlap_journey.py`: retain both native dual-weapon overlap
  and ordinary mortal spellcast overlap, reusing the converted pilot/caster setup.

Proof: run the pilot's complete family/case matrix and all three consumers;
SQL queries must observe the same committed identities and mana changes across
the existing crash/reconnect cases. No new mana table or persistence layer.

### 5. Rename supported tests/build helpers and repair active documentation

- [ ] Rename the 14 current `test_flatfile_*.py` files to the corresponding
  `test_mariadb_*.py` names. No destination collisions existed at planning time;
  check again before renaming. Rename `build_flatfile_server` to
  `build_mariadb_server` in both its owner and exposed journey wrapper.
- [ ] Update imports, runner registrations, artifact tests, source-contract
  references, manifests, scripts and active documentation in the same change.
  Include `tests/run_regression_tests.py`, `tests/run_db_tests.sh`,
  `server_build_artifacts.py` and `test_server_build_artifacts.py` where referenced.
  Preserve cache correctness and fast/real-clock behavior. No alias layer is needed
  for repository-owned callers; historical archived sources keep their own API.
- [ ] Replace retired inspector CLI instructions with tested MariaDB commands in
  `docs/testing/ITEM_ABILITY_ROLLOUT.md`, `docs/reference/WEAPON_ACTIONS.md`,
  `docs/guides/COLORIZATION_RELEASE.md` and affected active references in
  `docs/testing/REGRESSIONS.md`, `docs/guides/TESTING.md` and
  `docs/network/DISCORD_BRIDGE.md`. Incorporate the newer master documentation
  instead of undoing it. Leave historical execution records intact.
- [ ] Search the changed scripts and active callers for obsolete backend choices,
  inspector execution, `FLATFILE_STATE_DIR` and old imports. Classify legitimate
  negative-mode tests and historical references rather than requiring zero hits.

Proof: test discovery/imports still work, all moved tests remain registered,
the build-artifact tests pass, and the documented standalone commands execute
from a clean worktree with explicitly provisioned test prerequisites.

### 6. Validate, record evidence and integrate

- [ ] Record for every batch: tested commit, exact command/flags, binary hash
  where available, result and the ignored evidence path. Every supported
  scenario above needs runtime proof; note obsolete scenarios and their reason.
- [ ] Run the final regression suite and DB suite to completion. Check the
  earlier `nexus_journey` failure against current code; if it recurs, diagnose it
  and run the focused reproducer. A focused rerun does not make a failed aggregate
  result disappear. Preserve both results and repair task-blocking failures.
- [ ] Include runtime proof for #880's already edited standalone journeys
  `run_shop_bootstrap_journey.py`, `run_issue37_zone_journey.py` and
  `run_misty_vale_journey.py` if no valid evidence is available for their final code.
- [ ] Review the final diff with ablation: every edit must support a listed
  conversion, its actual consumer, or required proof. Keep unrelated defects
  separate and preserve unrelated worktree changes.
- [ ] Push the implementation and prepare a PR that names this plan, #870 and
  any still-open base PRs, with exact validation results and unresolved limits.
  Reconcile the stack with master without duplicating landed patches. Do not
  claim the issue complete while required scenarios or dependency findings remain
  unresolved. The requested deliverable is tested, pushed PRs ready for review;
  merging this stack and deployment require a separate request.

## Proof commands and environment

Run from this dedicated worktree. These are existing entry points; after the
rename, use the new names and record each runner's actual flags in the evidence
notes. Do not add another orchestration layer just to execute this list.

~~~sh
make -C src
python3 tests/async/test_persistence_mode.py
python3 tests/async/test_server_build_artifacts.py

# Pattern for each standalone DB journey; use its real CLI and all required modes.
tests/async/with_disposable_mariadb.sh python3 tests/async/run_shop_bootstrap_journey.py \
  --server bin/server/dms_new --areas bin/tests/issue-870/world/areas \
  --output bin/tests/issue-870/shop-bootstrap.json

python3 tests/run_regression_tests.py
make test-db
git diff --check
~~~

The shop command requires the isolated generated world from the repository's
existing world-fixture preparation first; the path above is the task's intended
output, not an assertion that it already exists. `make test-db` supplies the
normal DB suite's build/world prerequisites. Preserve earlier evidence outside
`bin/tests/db/`, which that runner replaces. All evidence for this task belongs
under `bin/tests/issue-870/` when configurable, or copied there after a run.

Run `./scripts/format.sh --check` and the required build after any C/C++ fixture
or server edits. Use focused tests while working; rerun broader suites only after
relevant changes or unresolved failures. GitHub CI is not a completion dependency.
No full burn-in, live-server reboot, or repeated cross-version matrix is required
unless a concrete changed contract justifies it.

## Completion criteria

- All 29 issue entries are accounted for, including the shared helper's consumers.
- Supported standalone runners work on disposable MariaDB without the deleted
  inspector, a hidden flat-file default or access to existing game data.
- Gameplay and persistence assertions survive conversion; obsolete backend-only
  checks have an explicit disposition and rejection remains covered.
- Names, test registrations and active runbooks agree with the real implementation.
- Required focused journeys, regression and DB gates pass; no required case is
  silently skipped or described as verified from a partial run.
- The final plan records the implementation commits, commands, results and any
  remaining dependency status, and the reviewable branch is pushed to GitHub.

Planning estimate: approximately 10–16 hours of elapsed agent work, with 12 hours
as a working estimate. Historical comparisons and stale runtime fixtures are
the largest uncertainties; substantial repairs could extend this to 18–24 hours.
This is an estimate, not a time limit or permission to omit required proof.

## Evidence and handoff

### Baseline reconciliation — 2026-11-09

- Base PRs #873, #874 and #880 remain open at their planned heads. Original
  worktrees were untouched. No production operation or game `.env` was used.
- Merge: `4f216b90c`; `make -C src -j4` passed. Build log:
  `bin/tests/issue-870/build.log`. This is the ordinary 250 ms server.
- GCC 16's installed C++ headers triggered a Clang 18 diagnostic in the merge
  hook. Running the hook with `CPLUS_INCLUDE_PATH=/usr/include/c++/13:/usr/include/x86_64-linux-gnu/c++/13:/usr/include/c++/13/backward`
  passed formatting and tidy; no hook was bypassed and no source workaround added.
- Tools verified: Docker 29.9.2, MariaDB client, compiler, Python, Node and gh.
- Private world: `make -C areas/src -j4`; copy `areas/` to
  `bin/tests/issue-870/world/areas`, link its `bin/areas/tools` to this checkout's
  built tools, create `world/lib/misc`, then run `./m_slow` from the private areas.
  The initial generator run needed that missing lookup-output directory; after
  creating it, `./make_lookup` completed. Log: `bin/tests/issue-870/world-build.log`.
- Next: finish launch-gate and shop-bootstrap SQL assertions, run both real
  journeys, publish their focused PR above the baseline PR, then continue the
  remaining partial conversions. Nothing else is qualified yet.
