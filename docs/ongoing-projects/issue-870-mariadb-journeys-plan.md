# Issue #870: finish the MariaDB journey conversion

Status: standalone conversions and the full907-file regression/native/build gate passed. First DB run153/154; its sole pet-reader failure is repaired and qualified. Full154-leg DB retry is running; final readiness remains pending.
Date: 2026-11-09.
Issue: [#870 — Follow-ups from the flat-file backend removal](https://github.com/LuminariMUD/Duris/issues/870).
Review head: `branch/issue-870-world-recovery-alert`. See the latest qualification notes before continuing.
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

The worktree was created at `81c969a63`, the original inspected #880 head.
On 2026-11-09, #873 and #874 merged into master; #880 advanced to
`6f4f1a975`. The baseline branch now merges that updated #880 and master
`f53e564f8` without rewriting published history. Preserve the item valuation,
ship, live-entity index and feedback/migration changes authored upstream.
The final build and suites must qualify this integrated stack.

Review dependencies start with [#880](https://github.com/LuminariMUD/Duris/pull/880)
then [#887](https://github.com/LuminariMUD/Duris/pull/887). #880 adopted
byte-identical launch-gate and shop-bootstrap repairs from #888, verified with
`git diff --exit-code` for both files. Duplicate #888 is closed; #890 now
targets #887. Later PRs retain their dependency order.

Historical qualification notes and binary hashes remain evidence for their
tested revisions. Historical item delivery evidence is retained explicitly as
history; active weapon/colorization runbooks point to #870 until their SQL
commands are qualified. No other worktree or production environment changed.

The [issue's verification comment](https://github.com/LuminariMUD/Duris/issues/870#issuecomment-6737821455)
reports 899 regression passes but an interrupted DB run with a nexus failure,
and no standalone runtime proof for several conversions. These are historical
results, not proof for the final branch. The issue's claim that scripts are
outside the suites is also incomplete: `tests/run_db_tests.sh` already invokes
several of the listed journeys. Inspect actual runner membership.

Two #880 findings were resolved by those adopted SQL checks:

- [Launch gate](https://github.com/LuminariMUD/Duris/pull/880#discussion_r4511763311):
  removed the `FLATFILE_STATE_DIR` snapshot lookup from the MariaDB path.
- [Shop bootstrap](https://github.com/LuminariMUD/Duris/pull/880#discussion_r4511763322):
  replaced the removed catalog-file assertion with persisted SQL
  shopkeeper/item comparisons across boots.

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
- [x] Repair `run_pwipe_launch_gate_journey.py`: remove snapshot discovery,
  preserve admission/denial and unchanged-account/player-state assertions with
  SQL checks, and run launch/copyover paths.
- [x] Repair `run_shop_bootstrap_journey.py` if #880 has not already done so;
  retain stock identities, contents and revision comparisons across cold boots.
- [x] Finish `run_news_prompt_journey.py` and
  `run_issue213_onboarding_journey.py`: use SQL for saved news/onboarding state
  and retain the reconnect and command/protocol assertions.
- [x] Finish `run_death_level_projection_journey.py` and
  `run_corpse_haul_count_cap_journey.py`: retain saved level, account projection,
  item count and wallet checks; remove unreachable inspector fallbacks.
- [x] Finish `run_cleric_rebalance_journey.py` and
  `run_innate_aura_keywords_journey.py`: keep SQL seeding and saved-affect expiry,
  specialization, command and keyword checks. Remove unused inspector/state args.
- [x] Finish `run_telemetry_player_journey.py`: remove unused state configuration,
  retaining the local receiver and its gameplay/copyover/performance assertions.
  Use its local test mode; do not send synthetic events to live analytics.
- [x] Finish `test_corpse_trap_restart_journey.py`: use SQL item/trap state and
  preserve death, nested contents and restart behavior.
- [x] Finish `test_information_cache_journey.py`: remove file publication and
  select MariaDB by default; retain cache refresh and concurrent reader checks.
- [x] Finish `test_flight_network_journey.py`: use SQL progress, correct the
  default and build invocation, and retain reconnect/interruption/copyover modes.
- [x] Finish `test_shop_multi_buy_journey.py`: retain wallet, item identities,
  parentage and cold-restart assertions. Translate any still-relevant delayed
  writer/offline-sale case using the existing MariaDB fault patterns; a file
  lock is not a MariaDB writer stall. Remove only exclusively retired semantics.
- [x] Finish `test_norent_key_rent_journey.py` and
  `test_artifact_owner_restart_journey.py`: remove inspector fallbacks and retain
  rent/crash/copyover, owner conflict, custody and restart assertions.

Proof: run each changed journey's supported modes. Several already have DB
runner entries; record which modes those entries cover and run the others
explicitly. Retain direct SQL checks of committed state after saves/restarts,
with existing bounded settling patterns where writes are asynchronous.

### 2. Convert the standalone gameplay, protocol and timing runners

- [x] `run_racial_pulse_journey.py`: replace inspector seeding with the existing
  MariaDB authority and player/skill setup; preserve rebalance and reload cases.
- [x] `run_cast_timing_probe.py`: replace backend/state setup and preserve its
  trace-derived timing report, pulse budget and requested cast count.
- [x] `run_divine_refusal_journey.py`: replace the embedded snapshot mutation
  and obsolete fixture compilation with SQL promotion/seeding; test enabled
  and disabled refusal, retry, exempt targets and mixed orders.
- [x] `run_spellcast_racial_multiplier_journey.py`: seed MariaDB and run every
  configured multiplier; keep ordinary mortal casts and timing comparisons.
- [x] `run_weapon_actions_journey.py`: seed MariaDB and preserve the existing
  family, enable/disable, completion, cancellation and reaction matrix.
- [x] `run_copyover_runtime_journey.py`: use one MariaDB setup for ordinary and
  Redis-fault paths. Preserve original sockets, plain/MCCP, TLS/WebSocket paths
  present in the runner, reconnect, failure/success, fresh/full-world and
  non-root cases. Reuse its existing private Redis fault setup.
- [x] `test_discord_game_journey.py`: seed the synthetic player and staff in
  MariaDB and retain petition/ptell, save and copyover assertions. Use the
  companion bridge's `scripts/testing/duris-game-sink.js` via `--node-driver`;
  verify the actual checkout/path and Node dependencies before running. The
  local sink must remain isolated from the real Discord service.
- [x] `scripts/validate_colorization_journey.py`: replace inspector setup and
  saved-state dependencies with MariaDB; retain ANSI, paging, rendering,
  permission and persistence checks and its synthetic report.
- [x] `run_pwipe_runtime_journey.py`: remove the obsolete flat-file rejection
  function, option and dependent argument validation. Preserve supported
  MariaDB/Redis/restore/reward and website modes. Verify affected argument
  combinations and run supported cases touched by the cleanup; provision
  the existing companion website test fixture for its integration mode.

Proof: use the real 250 ms clock for wall-clock/timing comparisons and keep
such runs away from heavy concurrent compilation/tests. Exercise existing
case matrices explicitly; one default invocation is not proof of all flags.

### 3. Convert named-set support and the assassin comparison

- [x] `named_set_gameplay.py`: replace `NamedSetGame`'s removed snapshot fixture
  compilation, state-directory requirement and inspector reads with the existing
  MariaDB authority. Seed/promote synthetic actors through SQL and read item
  identity, containment, provenance, affects and pets from their owning tables.
  Keep database lifetime across required boots and clean it up after the journey.
- [x] Update and execute its concrete consumers:
  `run_named_set_edit_clone_journey.py`, `run_named_set_pet_journey.py`,
  `run_named_set_rollback_journey.py`, `run_named_set_shop_journey.py`,
  `run_named_set_transfer_journey.py`, and `run_named_set_wear_journey.py`.
  Also check `run_named_set_mariadb_chest_journey.py` and
  `run_named_set_report_journey.py`, which import the module's gameplay helpers.
  Reuse the chest journey's existing SQL/provenance patterns and generate the
  isolated named-set world through the existing preparation path. Trace the
  rollback runner's compatibility binary before changing its assertions.
- [x] `run_assassin_balance_journey.py`: replace snapshot seeding/inspection
  with SQL while keeping deterministic RNG and the original/cleansed/revised
  comparison, levels/races, poison/cure and movement scenarios. Inspect the
  pinned `24a2776f13a2f3580c91f945743b09f80144b829` source and cleanse-only patch
  to select their existing MariaDB build/schema path, then prove equivalent
  synthetic actors and gear in all variants. Keep source/binary hashes and
  cache validation truthful; do not relabel current code as a historical build.
- [x] If either historical comparison cannot be run on its existing MariaDB
  path, record the exact incompatibility and resolve the coverage requirement
  explicitly before claiming completion. A skip or a restored flat-file backend
  does not satisfy this batch.

Proof: exercise all affected consumers and preserve each comparison's purpose.
Update only fixture code/manifests used by these consumers. Remove a superseded
fixture only after checking all callers; do not retain it as a compatibility shim.

### 4. Convert the four live item journeys together

- [x] `run_item_pilot_journey.py`: make its existing `Server` helper use the
  disposable MariaDB environment. Replace `seed-combat`, `seed-item` and
  `seed-item-operator` inspector operations with SQL or existing gameplay
  fixture operations. Read `artifact_mana` instead of decoding domain files.
  Preserve identity, reserve/version, enabled/disabled, interruption, crash,
  restart and family-specific behavior.
- [x] `run_item_mana_encounter_journey.py`: retain sustained NPC combat,
  immediate player-encounter refusal, recharge and committed reserve checks.
- [x] `run_item_config_journey.py`: retain real operator toggles/reload,
  pending-action cancellation, invalid configuration, revision/clamping and
  private metrics checks using SQL-backed state.
- [x] `run_item_overlap_journey.py`: retain both native dual-weapon overlap
  and ordinary mortal spellcast overlap, reusing the converted pilot/caster setup.

Proof: run the pilot's complete family/case matrix and all three consumers;
SQL queries must observe the same committed identities and mana changes across
the existing crash/reconnect cases. No new mana table or persistence layer.

### 5. Rename supported tests/build helpers and repair active documentation

- [x] Rename the 14 current `test_flatfile_*.py` files to the corresponding
  `test_mariadb_*.py` names. No destination collisions existed at planning time;
  check again before renaming. Rename `build_flatfile_server` to
  `build_mariadb_server` in both its owner and exposed journey wrapper.
- [x] Update imports, runner registrations, artifact tests, source-contract
  references, manifests, scripts and active documentation in the same change.
  Include `tests/run_regression_tests.py`, `tests/run_db_tests.sh`,
  `server_build_artifacts.py` and `test_server_build_artifacts.py` where referenced.
  Preserve cache correctness and fast/real-clock behavior. No alias layer is needed
  for repository-owned callers; historical archived sources keep their own API.
- [x] Replace retired inspector CLI instructions with tested MariaDB commands in
  `docs/testing/ITEM_ABILITY_ROLLOUT.md`, `docs/reference/WEAPON_ACTIONS.md`,
  `docs/guides/COLORIZATION_RELEASE.md` and affected active references in
  `docs/testing/REGRESSIONS.md`, `docs/guides/TESTING.md` and
  `docs/network/DISCORD_BRIDGE.md`. Incorporate the newer master documentation
  instead of undoing it. Leave historical execution records intact.
- [x] Search the changed scripts and active callers for obsolete backend choices,
  inspector execution, `FLATFILE_STATE_DIR` and old imports. Classify legitimate
  negative-mode tests and historical references rather than requiring zero hits.

Proof: test discovery/imports still work, all moved tests remain registered,
the build-artifact tests pass, and the documented standalone commands execute
from a clean worktree with explicitly provisioned test prerequisites.

### 6. Validate, record evidence and integrate

- [x] Record for every batch: tested commit, exact command/flags, binary hash
  where available, result and the ignored evidence path. Every supported
  scenario above needs runtime proof; note obsolete scenarios and their reason.
- [ ] Run the final regression suite and DB suite to completion. Check the
  earlier `nexus_journey` failure against current code; if it recurs, diagnose it
  and run the focused reproducer. A focused rerun does not make a failed aggregate
  result disappear. Preserve both results and repair task-blocking failures.
- [x] Include runtime proof for #880's already edited standalone journeys
  `run_shop_bootstrap_journey.py`, `run_issue37_zone_journey.py` and
  `run_misty_vale_journey.py` if no valid evidence is available for their final code.
- [x] Review the final diff with ablation: every edit must support a listed
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

The earlier results below retain their tested revisions and hashes. Current PR
status, source integration and outstanding work are in the final checkpoint.

### Baseline reconciliation — 2026-11-09

- Initial base PRs #873, #874 and #880 have since merged. The current integration
  checkpoint below supersedes their historical review status. Original worktrees
  were untouched. No production operation or game `.env` was used.
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
- `make world` also passed in this dedicated checkout for runners whose existing
  fixture helpers use `ROOT/areas`; its generated outputs remain ignored. Log:
  `bin/tests/issue-870/world-checkout-build.log`.

### Launch gate and shop bootstrap

- Implementation: `014f99194` and `bd20661cf`; no server code changed. Baseline-only document
  follow-up `8fce01495` is included by merge `cc7af38e9`.
- Binary SHA-256: `fe10882bac125606e69a8acaba57b32071bfdccdc3e4100a4b4b7742fc7c096c`.
- Passed: `tests/async/with_disposable_mariadb.sh python3 tests/async/run_pwipe_launch_gate_journey.py --server bin/server/dms_new --backend mariadb`.
  Evidence: `bin/tests/issue-870/launch-gate-run.log`, `mariadb.json`, transport
  captures and runtime logs in that same directory. The report records code
  commit `014f99194`. Real copyover/restart, Telnet/TLS/WS denial and approval,
  unchanged denied account/player/item state, and real UTC opening all passed.
- Passed: `tests/async/with_disposable_mariadb.sh python3 tests/async/run_shop_bootstrap_journey.py --server bin/server/dms_new --areas bin/tests/issue-870/world/areas --output bin/tests/issue-870/shop-bootstrap.json`.
  Evidence: that JSON plus `.log` and `shop-bootstrap-run.log`. Both full-world
  boots passed: 552 original shops and 294 retained items in the final run
  (earlier random resets produced 553/295), unchanged payloads/custody and
  non-regressing owner revisions. A later replay exposed a random world reset
  creating an additional keeper; the comparison now follows all original shop
  IDs and permits newly spawned shops, recording both retained and total counts.
  Final runtime qualification passed after `bd20661cf`; the report records
  `8d74a4afb`, whose shop code is identical to that commit. Failure evidence is retained as
  `bin/tests/issue-870/new-keeper-failure-shop-bootstrap*`.
  SQL rewrites replace row IDs and advance
  revisions legitimately; NPCs may cast buffs during a game pulse, so their
  live character affects are not treated as immutable stock. Item affects and
  extra descriptions remain compared in full.
- Also passed directly: `python3 tests/async/test_persistence_mode.py` and
  `python3 tests/async/test_server_build_artifacts.py`; their logs are in the
  evidence directory. Python syntax and `git diff --check` passed.
- Ablation: reused the existing MariaDB authority and kept SQL checks local to
  each journey; removed snapshot discovery and backend-only fallbacks. No new
  inspector, schema, framework or server option was added.

### News, onboarding and death projection

- Code: `c2fdd28eb`, `branch/issue-870-login-journeys`,
  [PR #890](https://github.com/LuminariMUD/Duris/pull/890), ready for review after full qualification. Base: #888. News now publishes its first synthetic
  edition to SQL instead of an ignored file; inspector fallbacks are gone.
- Passed: `tests/async/with_disposable_mariadb.sh python3 tests/async/run_news_prompt_journey.py --backend mariadb --server bin/server/dms_new`.
  Includes acknowledgement isolation, invalid/valid/periodic reload, reconnect,
  copyover, restart and distinct saved domain balances. Evidence:
  `bin/tests/issue-870/news-prompt-run.log` and `news-journey-mariadb.{json,log}`.
- Passed all 11 cases: `tests/async/with_disposable_mariadb.sh python3 tests/async/run_death_level_projection_journey.py --backend mariadb --binary bin/server/dms_new --output bin/tests/issue-870/death-projection`.
  Telnet/WS protected and actual-delevel deaths, menu projection, cold restart
  and long-session side cooldown all passed. Evidence: `death-projection/`
  and `death-projection-run.log` below the task evidence directory.
- Full onboarding passed without `--case` narrowing: all seven routes and
  28 recorded cases. Its `onboarding.json` has `completed: true`.
- These tests ran the edits later committed unchanged as `c2fdd28eb`;
  the death report's Git revision is the parent `014f99194` plus those edits.
  Binary hash is the shared `fe10882b...` recorded above.

### Corpse haul and lethal trap restart

- Code: `1f6adddb0`, `branch/issue-870-corpse-journeys`,
  [PR #891](https://github.com/LuminariMUD/Duris/pull/891), ready for review,
  based on #890. Reused `mariadb_authority()` instead of duplicated database
  setup and removed 145 net lines. SQL wallet, custody, trap and restart
  assertions remain. The retired backend is rejected; the trap runner's
  no-argument build now selects MariaDB.
- Both passed against code commit `1f6adddb0` and the same ordinary 250 ms
  binary (no C/C++ edits):
  `tests/async/with_disposable_mariadb.sh python3 tests/async/run_corpse_haul_count_cap_journey.py bin/server/dms_new mariadb`;
  `tests/async/with_disposable_mariadb.sh python3 tests/async/test_corpse_trap_restart_journey.py bin/server/dms_new mariadb`.
- Evidence: `bin/tests/issue-870/corpse-haul-run.log` and
  `corpse-trap-run.log`. NPC/player cap notices, partial haul, coin/wallet
  state, saved custody and reconnect passed. The lethal trap also passed
  cancellation, bystander effect, server survival, nested contents/custody
  and spent state across cold restart. Syntax, diff check and hooks passed.

### Cleric and aura journeys

- Code: `6723fd439` plus stale-fixture repair `8dd6a13a7`,
  `branch/issue-870-cleric-journeys`, based on the cache/flight
  [PR #892](https://github.com/LuminariMUD/Duris/pull/892).
- Passed: `tests/async/with_disposable_mariadb.sh python3 tests/async/run_innate_aura_keywords_journey.py --binary bin/server/dms_new --backend mariadb`.
  All keyword/alias, class/spec/unlock and imported-help assertions passed.
- Passed after the repair: `tests/async/with_disposable_mariadb.sh python3 tests/async/run_cleric_rebalance_journey.py --binary bin/server/dms_new --output bin/tests/issue-870/cleric.json`.
  Preserved saved full/pending spell rejection, current aura entitlement and
  staff/ordinary unspec cleanup, Miracle/Tsunami order and low-HP upgrade,
  True Seeing unlock, seven protection timers across copyover/cold restart
  and restored timer expiry. Same ordinary binary hash as above.
- The first run failed on the removed Cleric healing-aura grant. Current
  `src/classes/innates.c` grants that aura to Paladins, Protection to Holyman/
  Zealot, and Spell Protection to Healer/Holyman. The fixture now tests these
  supported grants and explicitly rejects the old healing grant on Clerics.
  This is a fixture correction; no gameplay rule changed.
- Evidence: `bin/tests/issue-870/{cleric-run.log,cleric.json,aura-run.log}`;
  original failure retained as `cleric-retired-aura-failure.log`. Inspector
  options, seeding and unused state setup were removed. Existing `Server`'s
  unused state parameter is passed `None` until its item-batch API cleanup.

### Telemetry and item custody

- Telemetry code `f2ddec22d`, `branch/issue-870-telemetry-journey`,
  [PR #895](https://github.com/LuminariMUD/Duris/pull/895), ready for review after both modes passed. The full normal local-receiver journey passed:
  `python3 tests/async/run_telemetry_player_journey.py --backend mariadb`.
  It received 42 events over 44 attempts/reservations and verified disabled
  save/reload, mortal/group/pet gameplay, outage saves, reload/reconnect,
  failed/successful copyover, privacy, quota and time-allocation conservation.
  Log: `bin/tests/issue-870/telemetry-run.log`; detailed artifacts:
  `bin/issue59/acceptance/`. This uses its own instrumented binary, not the
  ordinary binary hash recorded for the other journeys. The normal temporary
  binary was cleaned by the runner; its hash was not retained.
- Rent/artifact code `04da5426e`, `branch/issue-870-item-custody-journeys`,
  [PR #896](https://github.com/LuminariMUD/Duris/pull/896), ready for review.
  Both full journeys passed using the ordinary binary hash above and the new
  default backend:
  `tests/async/with_disposable_mariadb.sh python3 tests/async/test_norent_key_rent_journey.py --server bin/server/dms_new`;
  `tests/async/with_disposable_mariadb.sh python3 tests/async/test_artifact_owner_restart_journey.py --server bin/server/dms_new`.
  Six rent/no-rent carried/equipped/nested cases, cold restart, crash and
  copyover passed. Artifact tests passed all four stale owner types, exactly-one
  feeding, handoffs/repeated login, UID/timer/soul/custody preservation,
  duplicate conflict recovery, offline expiry, duplicate cleanup and fresh
  generations across repeated restarts. Logs: `norent-key-run.log` and
  `artifact-owner-run.log`; the rent report is copied to `norent-key.json`.
- The explicit `--reconnect-only` flight mode also passed; log:
  `bin/tests/issue-870/flight-reconnect-run.log`. The full default/interruptions
  matrix was already green in [PR #892](https://github.com/LuminariMUD/Duris/pull/892).

### Completed standalone qualifications

All paths below are relative to this worktree. Logs are under ignored
`bin/tests/issue-870/`; previous binary hashes describe the revisions actually run.
These are preserved per-chunk results, not claims that a later binary ran them.

- **Telemetry performance, #895:** `python3 tests/async/run_telemetry_player_journey.py
  --backend mariadb --performance` passed all three pairs/six legs/240 saves.
  Pulse p99 off/on645/541us; save p99 off/on1,775,503/1,755,792us. These are local
  samples, not production capacity measurements. Instrumented SHA-256:
  `0731f59506dd86d4942eb1490e5708bea81bea40821435b7c1dac14f9a56eb3c`.
- **Shop, #897 and repair #903:** the full SQL journey passed quantities, funds,
  capacity/refusals, a fresh unsaved bag,108 exact ration UIDs/parentage/wallet
  across restart, SQL-stalled sale/logout, exactly-once payment and stable UID
  buyback. Logs `shop-multi-buy*`, `integrated-shop*`; initial failures remain in
  `shop-unsaved-bag-failure-*` and `shop-retired-sale-expectation-*`.
  The merged repair reuses the creation queue and same-writer ownership read;
  existing owner declarations use `src/sql/item_owner_rows.h`. Its independent
  review added version8 atomic paid-creation receipts, exact wallet debit and
  retention of purchased bag subtrees through pre-publication saves. Those
  reviewed changes are included from master002ad622e, without a schema change,
  synchronous game-thread SQL or second persistence path. Native ASan/UBSan
  input, grant/reconciliation, newbie/prompt and ownership consumers passed.
- **Racial/cast, #918, code957cab3ac:** ordinary 250ms binary
  `4f13e85355b8940a950d14e3a4b3e061cf294a43369e68c249b17ce3b44d823c`
  passed21 races, rebalance/help/groundfighting/Reflection boundaries, adjustment,
  saved properties/restart and listing. Multiplier0.5/1/2 and20-cast default and
  `--budget-usec 2000` probes passed. Use the disposable wrapper and each runner's
  `--server bin/server/dms_new`. Logs `racial-pulse-run.log`,
  `spellcast-multiplier-run.log`, `cast-timing-{default,budget}-run.log`.
- **Pwipe, #922:** all six supported modes passed with the real five-minute
  countdown: direct; Redis; Redis re-enable; reward discard; matched restore;
  website. Help and six invalid CLI combinations passed (`pwipe-cli.json`).
  Codes0de5f6bc9/a8e18cb7b/112f0dddb remove the impossible retired mode, separate
  failure artifacts and seed the synthetic donor's verified email. Restore
  code04439c766 extracts under temporary umask077 because native recovery locks
  require0700; the earlier extra-reboot workaround was removed. Restore preserved
  bank9/reward3/PID/files/authenticated world, reconnect/second boot, source
  SQL/files/Redis and immutable backup. Logs `pwipe-*-run.log`, copied reports
  including `pwipe-runtime-mariadb-redis-restore.json`; ordinary hash024e32b9dd95….
  Website fixture `bin/tests/issue-870/website` is detached DurisWeb51549c2,
  with no `.env`. Frozen offline install/tsc passed using Node26.11.1/pnpm12.10.1.
  `TEST_DB_IMAGE=mysql:8.0` and `--redis --website <absolute-fixture-path>
  bin/server/dms_new` passed real local HTTP/session/WHO/cache/websocket drain
  and exactly-once synthetic webhook donation delivery; real providers disabled.
- **Divine refusal, #923, e7e83d8c3:** the disposable wrapper with
  `python3 tests/async/run_divine_refusal_journey.py bin/server/dms_new` passed
  disabled dispatch2/2, enabled0/2, retry lock, exempt commands and mixed orders.
  Log `divine-refusal-run.log`; binary
  `024e32b9dd95cf654ed9dbcadb937785d444b20967dbd11ce73d845aed3c875e`.
- **#880 standalone consumers:** `shop-bootstrap-run.log` confirms full-world
  initialization and cold restoration. `issue37-run.log` confirms ordinary route
  reset/restart/reset; `misty-vale-run.log` confirms full crafting/portals/switches/
  population/canoe/rod/fishing/reward persistence. The latter unchanged sources
  used the recorded4f13e85355b8… image. Copied reports are retained.
- **Weapons, #924:** packed and Avernus each passed all three cases: disabled
  ordinary damage, enabled windup/hit and flee with no damage/fizzle. Both enabled
  windups2.002s; flee0.250s. Native Avernus1/25 selection remains unchanged;
  synthetic NPC level56 and the existing600s natural-selection bound avoid
  expecting a proc from a window of missed melee attacks. Prior failures remain
  under `pre-fixture-repair-weapon-avernus*`. Active weapon guide has both commands.
- **Colorization, #925, 9939996fb:** all65 checks/15 frames passed: independent
  accounts/GMCP/ANSI recipients, saved choices/reconnect, paging, animation,
  motion/static, authored mural and previews. `colorization-run.log`/`.json`,
  binary024e32b9dd95…; active release guide gives the disposable SQL command.
- **Copyover, #926:** all11 cases passed: default/fresh minimal, preserving/fresh
  full-world and UID10001, plain/MCCP each, plus Redis faults. Retain sockets,
  TLS/WebSocket survivors, failure/success, session change, mismatched-account
  refusal and failed-replacement generation assertions. SQL save rejection
  replaces snapshot corruption. The shared port lock retries an existing file
  without O_CREAT on PermissionError, preserving fcntl reservations. Full-world
  cases await paged zero artifact/guild dirty/pending before faults and after
  replacement. Logs `copyover-{default,redis,fresh,full-world,
  full-world-preserve,nonroot}-run.log`; initial failures are retained.
- **Discord, #928, a98106d9e/8de873801:** full petition/ptell/exclusions/ingress,
  original player/bridge sockets through failed/successful exec, saves, reconnect,
  offline/disabled relay, deduplicated audit and shutdown passed. Use clean
  companion70865ecafb0aeb9b9ac71da37696e416d892ce4c at
  `/home/aiwithapex/projects/discord-mud-chat/scripts/testing/duris-game-sink.js`
  and Node26.11.1. It uses loopback/mock Discord with no dotenv. Logs
  `discord-game-run.log` and the retained initial failed-exec expectation failure.
- **Four item journeys, #931, aa5f4f231/6a079045d/4487cc3a6:** all seven pilot
  cases passed: Studio complete/abort/crash; Tsunami disabled/complete/abort with
  corpse loot; Ioun paid incoming-spell interception. Config/reload/invalid
  catalog/metrics, sustained PvE/player refusal/recharge and both dual-weapon and
  mortal-cast overlaps passed. SQL reads all eight artifact_mana fields. Real
  staff-created UIDs survive demotion to original mortal levels; Server's existing
  signature remains for11 other consumers. Modified mini objects/resets are
  copied to their generated world inputs. Crash proof checkpoints the carried
  source before SIGKILL and preserves exact debit/no revival. Unchanged Studio
  complete/abort evidence is reused with the separately rerun affected crash.
  Logs/reports `item-pilot-{studio,studio-crash,tsunami,ioun}*` and
  `item-{config,encounter,overlap}*`. Ioun173.415s; recharge1500→3000 in5.506s;
  dual sources33.534s; mortal casting/passive overlap4.755s. Active rollout
  runbook publishes the complete reproduction matrix.

### Named-set implementation and proof

- Code starts at cacfbc8be, PR #938. `NamedSetGame` owns one SQL authority through
  transfer → edit/clone → pet → shop →16 wear zones → copied rollback → existing
  chest/report. Existing consumers receive only their concrete runtime/server
  paths. The removed C++ snapshot writer has no remaining caller.
- SQL readers keep exact UID/parent/slot/provenance, permanent HP/Constitution/bit
  modifiers, saved affects and pet custody. SQL does not restore transient item
  affects; native HP/spell assertions prove those benefits after reload. Nullable
  empty pet_uid mirrors the native loader's COALESCE0. The controlled named coat
  is seeded weight1 offline in its actual owning payload table, retaining all
  identity/affect fields, so native pet give/return meets the heavy-item guard.
  Shop equips originals natively and promotes both donor and recipient before
  transfer; no production gameplay rule is changed.
- Transfer, edit/clone, pet and shop passed: original nested/worn UID/origin/slots,
  independent ordinary Armor, five distinct recursive clone UIDs, mixed outfit
  benefits, two pet reboots/return/final wear, paid sale/rebuy and Armor/+5HP.
  Wear1325,740,827,13,44,204,808,811,814,990,300,1350,87,370,676 passed their full
  native threshold, persistence and removal assertions. Wear824 also passed its full potion/removal leg; all16 wear cases are complete.
- Preserve ordinary potion timers. Wear13 waits up to600s for native Armor-potion
  expiry. Wear824 likewise recognizes both actual potion cooldown messages from
  actoth.c4767–4777, then requires `Nothing new seems to happen.` and intact
  Vitality set benefits. Previous cooldown failures remain under
  `named-set-vitality-cooldown-failure/` and `named-set-last-tick-cooldown-failure/`.
- The captured fixture is `bin/tests/named-set-mariadb-sequence-ununney2`.
  `authority.sql` is private synthetic state; `sequence.json` records SQL/binary
  checksums, completed labels and reused proof hashes. Normal `--resume` rejects
  changed binaries without changing recovery evidence; negative proof is
  `named-set-resume-rejection.log`. `--allow-binary-change` explicitly records
  repair replays; SQL dump SHA remains mandatory. Earlier frozen sequence
  metadata in failure folders preserves each previous proof epoch.
- Rollback hashes stopped source SQL/accounts/journals, imports into another
  disposable schema, keeps that copy across both binary changes and requires the
  source unchanged. No view/schema-rebinding framework is needed. Compatibility
  uses current code with only bff1043fd's115-row catalog substituted, not a full
  historical server. Source SHA-256:
  `2fb1c22f2e20f125df0bd8bb03509e4ecccbc0394a7d4247bca3b02ea0a2f988`.
  Build source/binary/command are in `bin/tests/named-set-rollback-source/`.
  Its Make recipe uses `.SECONDEXPANSION` for DMS_OBJS and excludes the normal
  named_sets.o; relinks must actually change the binary hash after native edits.

### Assassin implementation and versioned proof

- PR #948 pins BASE24a2776f13a2f3580c91f945743b09f80144b829 and the exact existing
  cleanse-only patch. Fresh archives are byte-verified. Each uses its own existing
  MariaDB bootstrap/migrations through `mariadb_authority(source_root=...)`.
  The current verified builder builds each source with seed187 and ordinary
  250000us pulses; no retired backend or current fast-clock comparison.
- SQL seed_actors creates the same attacker/Cleric defender, gear and four
  remove-poison/two slow-poison memorization slots. Class/skill/memorization
  constants match headers. Historical account creation uses its byte-checked
  archive helper because Keep entered the MOTD directly; current transport/SQL
  remain shared. Old saves await `Save complete`, never queued admission.
- FIRST_POISON1536..LAST_POISON1542 comes from the verified header chain, retaining
  all seven poison types without a general macro parser. Poison/coating/cure
  inspection remains SQL. The obsolete C++ actor writer is removed; the existing
  manifest-input regression tracks the actual Python seeder/auditor.
- Full original12/cleanse12/revised36 openings passed. Immutable original/cleanse
  evidence is `assassin-qualified-initial-{binaries,results-matrix}.json`.
  Original binary5a2c9dbacf2eb71ab0ff360e2724f5cb9e3d6078286ff15c67953b673f470521;
  cleanse dd66f5d524c2b5babdd52673b3da6ec22da103c537b3803bbe4a5f48b4cb680e.
- Revised36 was requalified after each native save repair. Matching manifests/
  reports are `assassin-qualified-deep-{binaries,results-revised-matrix}.json`
  and `assassin-qualified-ordering-{binaries,results-revised-matrix}.json`.
  The latter matrix exited0. Following scenario invocations correctly refused
  changed source/runtime inputs; never relabel those older matrices as current
  integrated executions. Selected variants write separate result files.
- Preparation verifies source, fixture, seed, patch, creator, schema, runtime and
  binary hashes. Original/cleanse cache reuse remains valid. The final integrated
  preparation and revised scenarios exited0. Seeded binary SHA-256:
  `44815784471b7846eedab8d74048280891d132783e38c8283c1103dd95816213`;
  source6fba71dbf. `assassin-qualified-integrated-{binaries,results-scenarios}.json`
  preserves that exact epoch. PR #948 is ready. No PvP win-rate inference is claimed.

### Mechanical naming

- PR #949 physically renames all14 test_flatfile_ Python files to test_mariadb_,
  and both public build helpers to build_mariadb_server. Update every active
  import, runner, source contract, script, Makefile/workflow and runbook; no alias.
  Historical reports and immutable archive helpers retain their actual old names.
- Moved/changed Python files compile. Initial naming discovery listed905 tests.
  Artifact reuse/corruption/isolation/publication, root harness, manifest inputs,
  launcher, real MariaDB boot preflight, help reader and shopkeeper-capture checks
  passed: `naming-*.log`. Boot preflight uses the disposable wrapper and --server.
  The integrated checkout compiles150 changed Python modules. Final regression
  discovery/count comes from the pending full gate; do not reuse905 as its result.
- Remaining retired strings are historical/negative-mode/file-journal references
  or unreachable __NO_MYSQL__ probe branches, not an active supported backend.

### Native defects found and separately repaired

- **#954, c5f47b514, bug:** the named-set sequence reproduced DELETE failure1296/
  InnoDB193 on a15-level/1361-row graph because item metadata adds a cascade level.
  `named-set-sql-delete-repro.log` proves the owning SQL operation. Detach parent
  links only on rows selected for replacement inside the existing transaction,
  excluding validated retained components, then delete/reinsert. No depth/schema/
  UID reduction. The existing player-save claim DB harness passed a20-level tree,
  affects/descriptions, injected-delete rollback restoring exact links/revision,
  successful payload replacement and empty replacement. Ordinary build and native
  wear1350 save/reboot/removal passed. Integrated claim harness passed again,
  including current master's retained paid-receipt logic.
- **#957, 5e5c76d9e, bug:** executable worker/pipeline regressions reproduced a
  status-only tail replacing a queued inventory payload and a later partial
  success falsely acknowledging an earlier failed full save. Repro logs are
  `test_player_save_{worker,pipeline}-partial-repro.log`. Only coalesce a covering
  component mask. One internal failed-component mask holds written acknowledgement
  until successful ordered completions repair it; stale captures cannot clear it.
  Existing worker, pipeline, revision-state and actual manual-feedback harnesses
  passed, including stale completion and repair. Formatting/tidy and native build
  passed; post-integration pipeline passed (`partial-save-post-integration-pipeline.log`).
- **#955, afc746847, enhancement:** explicit captured-fixture repair replay,
  accurate poison-ID lookup and separate selected-variant evidence. Final integrated named-set and Assassin scenarios passed; ready for review.
  No new fixture framework.

### Current continuation checkpoint

- Integrated base `branch/issue-870-completion-qualification`, source integration6fba71dbf
  and paid-crash import fixea9fd03ca, draft
  [#958](https://github.com/LuminariMUD/Duris/pull/958), enhancement/documentation,
  after ready bug #957. Master002ad622e is forward-merged; no history rewritten.
  Merge conflict retained reviewed shop paid-crash coverage and current names.
  Prerequisites #880/#887/#890–#893/#895–#897/#903 are merged by independent review;
  #918 now targets master. Pending dependent PRs continue #918 → #922 → #923 →
  #924 → #925 → #926 → #928 → #931 → #938 → #948 → #949 → #954 → #955 → #957 → #958
  → #961 → #962 → #963.
- Integrated native build and deep claim DB matrix exited0. Ordinary SHA-256:
  `6dfb502003ca659f83dff27acd9cf51c5ac1b263d2b4a408e8339ecd0c1494f0`;
  compatibility SHA-256:
  `e0c5e6c1c3c466fe00f8882aeaad714fe2939ff9e09755ac35266cd217a34627`.
  Logs `integrated-native-build.log`, `integrated-deep-save-claim.log`,
  `integrated-compat-build.log`. Changed-line formatting/tidy and own diff check
  against origin/master passed. Existing upstream help-index trailing spaces are
  preserved. Other worktrees, production data and game .env files are untouched.
- Named controller49919 exited0: all23 sequence labels passed (transfer,
  edit/clone, pet, shop,16 wear zones, copied rollback, chest, report). Per-version
  reused proof remains explicit. Frozen final metadata is
  `named-set-qualified-integrated-sequence.json`; full log and terminal result:
  `named-set-sequence-integrated-run.log`/`.exit`.
  Reproduction: `python3 tests/async/named_set_gameplay.py
  bin/tests/named-set-rollback-source/dms-115-catalog`; to continue the captured
  fixture add `--resume bin/tests/named-set-mariadb-sequence-ununney2` and only
  after an actual native rebuild add `--allow-binary-change`.
- Copied rollback preserved every UID/origin/parent/slot and HP through298→115→298
  rows, removed/restored the new spell and left source SQL/accounts/journals
  unchanged. Chest passed real purchase/deposit/retrieval/world-storage/mortal
  sale/paid-repurchase and reboots with the exact graph and set. Report passed all
  298 rows, one-day warm TTL, staff local/Redis invalidation, stale-report reboot,
  Redis loss and Redis-disabled pagination/order/conditional notes.
- Assassin controller73465 exited0 on the integrated source: equal/mismatched gear,
  Control Flee, preemptive and post-first-tick Heart cure, Slowness cure, Healer
  poison, mixed/duplicate dual poisons, solo PvE survival and traded vial use.
  Solo reference NPC completed60.77s with314 HP lost. Logs
  `assassin-prepare-integrated-run.log`, `assassin-scenarios-integrated-run.log`
  and `.exit`; exact integrated seeded binary hash is recorded above.
- Paid fresh-bag crash controller74416 exited0. The new reviewed mode initially
  exposed a missing `os` import at SIGSTOP; `integrated-paid-fresh-crash-missing-import.*`
  retains that failure. Commit ea9fd03ca adds only that import. The same real
  crash/restart path passed: wallet100000→99989, item UID1072350 under parent
  UID1072324, identical after SIGKILL/cold restart. Evidence
  `integrated-paid-fresh-crash.{json,log,exit}`. No schema or receipt change.
- **First aggregate controller55425 is terminal:** production prebuild exited0.
  `make test-all -j4 TEST_JOBS=8` completed907 files,903 passed/4 failed,
  0 timeouts/signals in457.42s (make exit2). Preserved
  `final-test-all-first-run.log`/`.exit`. It correctly did not start test-db.
  The four concrete repairs and focused results follow below; no full-suite
  success is claimed yet.
- #938/#948/#955 descriptions now record their qualified runtime results and
  linked follow-ups; all three are ready. #958 remains draft. The four findings
  are now repaired in ready #961/#962/#963. Repeat full test-all and test-db to terminal success,
  then finish scope/names/evidence/diff review and mark the final review work ready.
  Preserve failed results before retries. No CI wait/full burn-in.
- The mission remains all #870 work with autonomous issue repair and tested,
  labeled, pushed PRs ready for review. Final-suite findings are the remaining
  uncertainty. No GitHub merge, release, deployment or production action was
  performed by this task.


### First aggregate result and focused repairs

- `make test-all -j4 TEST_JOBS=8` completed all907 files:903 passed,4 failed,
  0 timeouts/signals,457.42s; terminal make exit2. Production build passed.
  Preserved complete result: `final-test-all-first-run.log`/`.exit`. Aggregate
  controller55425 is terminal; it correctly did not start test-db after failure.
- Two fixtures introduced by the reviewed-master merge still called the old
  two-argument written-ack API. `test_item_movement_prompt_runtime.py` now passes
  its actual queued component mask; `test_newbie_grant_lifecycle.py` passes the
  STATUS component its baseline marked/queued. Keep all executable grant/prompt
  assertions. Both focused executable tests exited0 after that repair (including
  ASan/UBSan prompts), and `make -C src` passed. Evidence
  `test_{item_movement_prompt_runtime,newbie_grant_lifecycle}-ack-mask-fixed.log`/`.exit`.
  This is a focused test-only follow-up after #958.
- Artifact inventory's old assignment-site parser loses all80 callbacks after
  master #902 moved the same native499 bindings into their shared catalog.
  An unfixed candidate confirms171 templates but0 callbacks, versus the tracked
  80 bindings/69 callbacks. Do not regenerate that loss into documentation.
  The existing consumer now reads the compiler-selected object/room catalogs in
  stage order, preserving later overrides and rejecting missing/unreadable tables.
  `test_artifact_source_inventory.py` passed the byte-identical tracked171-row
  inventory with80 bindings/69 callbacks and explicit override checks; the native
  499-entry catalog ASan/UBSan test passed too. No JSON loss was regenerated.
  Evidence `test_{artifact_source_inventory,object_binding_catalog}-inventory-catalog-fixed.log`/`.exit`.
- Telemetry passed reducer and first HTTPS matrix, then its second-build pin
  case measured448292us against the existing250000us pulse limit under the
  compilation pool. Its isolated run exited0 for both build variants, all64
  reducer and33 HTTPS cases each, with the same pulse limit. This is consistent
  with compilation contention; the runner currently has one shared pool. Keep
  that hard latency test outside the pool, then require a green full aggregate.
  Isolated log `telemetry-posthog-isolated.log`/`.exit`; no threshold relaxation.
- #938, #948 and #955 are now ready with the exact integrated runtime results
  and explicit linked follow-ups. #958 remains draft until both aggregate gates
  and the final audit pass. Current repair branch:
  #961 and #962 are ready for the save-fixture callers and inventory consumer
  after #958. Current branch `branch/issue-870-telemetry-test-scheduling` adds
  only the separately qualified hard-latency test scheduling fix after #962.

- Telemetry scheduling outcome: preserve the250ms pulse budget and every selected
  test while keeping this concrete hard-clock check after the compilation pool.
  Files: existing runner/root-harness regression, testing guide and this tracker.
  No native transport change, new target, option, resource framework or tolerance.
  An executable three-test scheduling regression put telemetry first and failed
  on the old runner (missing completed-pool markers). With the fix, the two pool
  jobs overlap and telemetry follows both; all3 pass, and existing worker-limit,
  timeout/signal/process cleanup contracts also pass. Logs
  `runner-telemetry-isolation-{repro,fixed}.log`, fixed `.exit`0.
- All four first-aggregate findings now have focused passing proof. Full aggregate
  success still requires rerunning test-all and test-db; earlier903/907 remains
  the recorded failed aggregate and the DB gate has not yet run.

- **Active retry controller88225** on pushed scheduling code bf2bbc41c:
  `make test-all -j4 TEST_JOBS=8`, then `make test-db` only if regression succeeds.
  Logs `final-test-all-retry1.log`/`.exit`, then `final-test-db.log`/`.exit`.
  It copies the first DB run to `final-db-first-run/` at terminal completion.
  Previous controller55425 and every named/Assassin/paid-crash controller are
  terminal. Check88225 before starting any duplicate full run. All four focused
  repairs are committed, pushed and labeled bug (#961/#962/#963).
- Current ETA update:1–2 more hours for remaining full gates and actual findings;
  this is an estimate, not permission to omit required validation or final review.


### Full regression passed; database qualification continues

- Controller88225's `make test-all -j4 TEST_JOBS=8` retry exited0:907/907 passed,
  0 timeouts/signals,261.13s, including the isolated unchanged-budget PostHog check
  and native signal gate. Production and development builds passed. Proof
  `final-test-all-retry1.log`/`.exit`. The first903/907 result remains preserved.
- Current ordinary binary remains6dfb502003ca659f83dff27acd9cf51c5ac1b263d2b4a408e8339ecd0c1494f0;
  production profile1a41cd1c43ed76b83347d3d092e4e6eca605d7eac55e8bf3d000a2c0346ed175.
  Scope/name audit found only the five intended native save files beyond frozen
  master002ad622e, no protected-file diffs, no current test_flatfile_ files, and
  no active old build-helper reference. Remaining retired strings are the
  documented historical/negative-mode/no-MySQL-probe cases. Required wall-clock
  runners require explicit binaries; the Assassin builder explicitly uses real_clock.
- First `make test-db` is still collecting all legs under88225. It found
  `pet_restart` failing an offline-expiry sibling-UID assertion; do not stop or
  duplicate that live aggregate. Logs remain `bin/tests/db/` and `final-test-db.log`;
  the controller archives them to `final-db-first-run/` after terminal completion.
- Pet-reader outcome: metadata and gear IDs must come from the same committed
  SQL view during maintenance checkpoints. Files: existing pet journey and this
  tracker. Native `apply_pets` retains UID-bearing pet IDs but replaces legacy
  held rows without pet_uid. The old reader fetched pet IDs, then issued separate
  item queries; a committed row replacement between them loses the apparent UID.
  Read each pet's metadata/ordered UID list in one SQL statement. Keep empty/null
  UID semantics and every identity, expiry, stat, cooldown and rollback assertion;
  improve the actual failure diagnostic rather than weakening its check.
- The isolated old reader happened to pass (`pet-restart-diagnostic.log`/`.exit`),
  so that pass alone is not the repair proof. A controlled real-MariaDB interleaving
  executes the actual old/new reader bodies and replaces a legacy row after the
  first SQL result: old returns no UID while committed777/NULL remain; new returns
  both777/NULL consistently. Proof `pet-reader-transaction-probe.log`/`.exit`0.
  The complete real-server journey with the coherent reader exited0 in
  `pet-restart-coherent-read.log`/`.exit`, including offline artifact expiry,
  finite/permanent pets, both cooldown reboots, rollback-held release and later
  held-equipment quit/restart/save. No native code or schema change was needed.
- Publish this focused follow-up after #963, then require terminal full DB output,
  diagnose any other findings, and rerun the complete DB gate after repairs.
  The successful907-file gate remains valid: only its excluded DB pet journey
  changed, with common helpers and native source unchanged. No whole-issue claim.

- GitHub audit verified appropriate labels on all19 pending/recent PRs; all are
  ready or merged except #958, deliberately draft until the final gates finish.
  #918 is now merged by independent review; its three runtime scripts are byte-
  identical to our qualified copies (review delta e5294b9c→a88af2b07 is empty).
  #922 now targets master because its prerequisite is merged.
- Fresh master524eb47b8 adds independent MXP/output-link, auction, smith and
  proc-library work. Its #918 changes are already present byte-for-byte here.
  Keep the qualified002ad622e integration baseline for this issue, with explicit
  native/source hashes, rather than expanding validation into those later features.
  No original #870 requirement or reviewed #918 repair is omitted by this freeze.

- Historical `nexus_journey` concern is resolved on the qualified image: the
  complete current DB leg passed in290s, including mortal guardian captures,
  cooldown/full turn/epic rewards, actual cargo/contraband bonus/exclusion,
  cold restoration and expiry/neutral reload. Its log records the same6dfb5020…
  binary. First DB run has reached its final serial recovery/latency checks with
  151 passing legs and only the already-repaired pet-reader failure so far.

### Database first run preserved; full retry active

- First database controller88225 is terminal:153/154 passed, only pet_restart
  failed,2913s, make exit2. All final serial checks passed, including all artifact/
  guild crash/recovery cases and the8-mortal/god game-loop budget. Complete
  stdout/status are in `final-test-db-first-run.log`/`.exit`; all154 logs are in
  `final-db-first-run/`. Archive completeness was checked before bin/tests/db reuse.
- Ready/labeled bug [#965](https://github.com/LuminariMUD/Duris/pull/965) contains
  the old/new reader transactional reproduction and full pet journey proof.
  Source commit0ed24f840; later commits update the tracker.
- **Active full DB retry56758** runs unchanged `make test-db` with all154 legs
  after the pet fix. Output/status: `final-test-db-retry1.log`/`.exit`; completed
  logs will be archived as `final-db-retry1/`. Prior88225, both focused pet runs
  and the transaction probe are terminal. Poll56758; do not duplicate this run.
- Final diff/ablation audit against baseline002ad622e:180 changed paths,
  128 strictly mechanical test/helper renames and52 scoped conversion, consumer,
  fixture, documentation or reproduced-defect changes. Two obsolete C++ snapshot
  writers are deleted; only the five documented native save files differ. Every
  retained addition has a traced caller or concrete failing proof. No extra
  backend, generic fixture/resource framework or protected-file diff remains.
  Only the full DB retry and final PR/evidence publication remain.

### World-recovery outage alert fixture

- Retry56758 is still collecting all154 legs. Its pet leg passed in150s under
  parallel load, but world_recovery failed because the fixture demanded only
  `publish_failed`; the actual third failed attempt reported `floor_unavailable`.
  Preserve that result as `world-recovery-outage-phase-failure.log`. Do not call
  this aggregate green from the later focused results.
- Native redis_world_runtime.c1010–1042 reports floor_unavailable when a floor
  barrier is still waiting, cannot be requested, or fails preflight. Lines1065–1074
  report publish_failed only after reaching the publisher. Redis loss can cause
  either stage to stop first. The floor worker retries pending mutations while
  Redis is down, so a still-waiting barrier is a legitimate outage result.
- Outcome/files: correct that stage assumption in the existing
  run_world_recovery_journey.py and record its proof here. Accept only those two
  traced reasons; keep exact third-attempt count, last sequence/age, one-alert
  suppression, automatic lease recovery, crash restoration, floor UID and default
  interval/max-age assertions. No native, schema, tolerance, CLI or framework change.
- Normal focused journey exited0: `world-recovery-alert-phase-fixed.log`/`.exit`.
  It exercised publish_failed, exactly3 failures, one alert, recovery without
  restart, crash restoration65s after kill, the physical floor UID and defaults.
- An isolated validation variant keeps the existing player connected, then gets/
  drops the floor bag after stopping Redis to force queued floor work. It requires
  floor_unavailable explicitly and passed the same complete recovery/crash/UID/
  defaults assertions: `world-recovery-floor-outage-probe.log`/`.exit`0. Both
  actual native outage paths are proven; no underlying assertion was discarded.
- Publish this focused follow-up after #965. Let56758 reach its terminal result,
  preserve its complete logs, then rerun the entire DB gate after this correction.
  The907-file gate remains valid: its inputs/native code are unchanged and this
  DB-only run_ journey is not discovered there. Final readiness is still pending.
- This correction is pushed at caa1a4ba7 in ready/labeled bug
  [#970](https://github.com/LuminariMUD/Duris/pull/970). No focused run remains
  active. Aggregate56758 is now terminal:153/154 passed in2868s, make exit2;
  only the corrected world_recovery stage assertion failed. Pet, all artifact/
  guild recovery cases and the game-loop budget passed. All154 logs are preserved
  in `final-db-retry1/`; stdout/status in `final-test-db-retry1.log`/`.exit`.

### Current final-gate continuation

- **Active full DB controller34613** runs unchanged `make test-db` after both
  committed DB-fixture corrections. Output/status: `final-test-db-retry2.log`/
  `.exit`; completed logs will be copied to `final-db-retry2/`. Archive completeness
  of the prior154-log run was verified before this new run cleared bin/tests/db.
  Both earlier aggregate controllers88225/56758 and every focused probe are terminal.
- The907-file regression/native/build pass remains valid. Direct dependency
  inspection found no included test importing/reading either modified DB-only
  journey; pet appears only in the exclusion/deadline name sets and their tests.
  Common helpers and all native sources/binaries remain unchanged.
- No required work is omitted: await34613's terminal full154-leg result, repair
  any actual further finding, then publish final evidence, mark #958 ready and
  verify clean/pushed Git and all PR labels/readiness. Do not start a duplicate
  run or call a focused pass a green aggregate. No merge/deployment is requested.
