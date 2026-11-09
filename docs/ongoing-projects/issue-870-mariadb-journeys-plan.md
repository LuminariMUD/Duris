# Issue #870: finish the MariaDB journey conversion

Status: batches 1, 2 and 4 are qualified, including every weapon, copyover and live-item mode. Named sets/historical assassin comparison, naming/docs and aggregate gates remain.
Date: 2026-11-09.
Issue: [#870 — Follow-ups from the flat-file backend removal](https://github.com/LuminariMUD/Duris/issues/870).
Review head: `branch/issue-870-named-set-journeys`. See the current-work section before continuing.
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

### Current work / next action

- Ready PR stack: #880 → #887 baseline → #890 login/news/onboarding/death →
  #891 corpses → #892 cache/flight → #893 Cleric/aura → #895 telemetry →
  #896 rent/artifact → #903 container-grant repair → #897 shop → #918 racial/cast.
  #888 is closed because #880 adopted its exact source changes. #897 is ready.
  Every PR has an appropriate documentation, bug or enhancement label. No merge,
  tag/release or deployment was requested or performed.
- Telemetry performance passed all three paired workloads (six legs, 240 saves):
  `python3 tests/async/run_telemetry_player_journey.py --backend mariadb --performance`.
  Pooled native pulse p99 was 645 µs disabled / 541 µs enabled; pooled save p99
  was 1,775,503 / 1,755,792 µs. These local samples passed the existing gate;
  they are not production capacity measurements. Instrumented binary SHA-256:
  `0731f59506dd86d4942eb1490e5708bea81bea40821435b7c1dac14f9a56eb3c`.
  Logs, a hash record and copied pair summaries are under `bin/tests/issue-870/`.
  Session `11319` is terminal with exit 0; do not restart it.
- Shop conversion code: `55927b624`, `branch/issue-870-shop-journey`,
  [PR #897](https://github.com/LuminariMUD/Duris/pull/897), ready after #903.
  Initial failures at the fresh/unsaved staff-bag purchase and retired deferred-sale
  expectation remain under `bin/tests/issue-870/shop-unsaved-bag-failure-*` and
  `shop-retired-sale-expectation-*`. Both are now resolved; the full journey passed
  again after upstream integration (`integrated-shop.json` and run log).
- Server repair is qualified on `branch/issue-870-container-grants-fix`
  before #897. Outcome: newly loaded carried bags can receive a transactional
  child batch without synchronous SQL or a guessed owner/revision. Reuse the
  existing creation queue: capture the actor's inventory, queue an ownership
  read on the same writer, then hydrate its actual row and submit the child
  batch. Offline/failure delivery stays in that queue and existing business
  callback. Already-cached parents keep their existing path. No schema,
  persistence redesign, new service, cache or backend selector is introduced.
- Repair files: `src/item/item_movement_transaction.c`,
  `src/sql/{sql.h,item_owner_rows.h}`, `tests/async/harness_stubs.cpp`, and
  `tests/async/test_item_movement_input_queue.py`. The existing ownership-row
  declaration/macros move to a narrow header used by both real callers; this
  avoids importing MySQL connection headers into the item runtime and changing
  unrelated native-harness compiler flags.
- Repair proof so far: `make -C src -j4` passed; ASan/UBSan item-input queue
  regression passed with new unavailable-checkpoint/read, deferred-parent,
  offline-resume and failure-callback assertions. Creation-batch and
  reconciliation contracts and the existing newbie lifecycle runtime passed.
  Prompt runtime also passed. With the companion #897 conversion, the complete
  real shop journey passed, including a fresh unsaved bag, all 108 ration UIDs/
  parentage/wallet across restart, and sale/logout while SQL saves are locked.
  It then verified exactly-once payment, no returned sold UID and stable buyback
  after restart. The retired deferred-sale receipt was corrected to the current
  immediate-memory sale contract; the lock now holds actual player/shop/log
  tables until the account menu, without querying locked inventory tables.
  Source repair commit: `50112a024`, inserted as a prerequisite of #897.
  It has the same source/native fixture bytes as the originally tested local
  `a504cd578` (verified with `git diff --exit-code`); no published history was
  rewritten. Binary SHA-256:
  `4f13e85355b8940a950d14e3a4b3e061cf294a43369e68c249b17ce3b44d823c`.
  Full runtime evidence: `bin/tests/issue-870/shop-multi-buy*`; earlier failures
  remain under `shop-unsaved-bag-failure-*` and `shop-retired-sale-expectation-*`.
- Container preparation follow-up: failure cleanup now releases the batch before
  notifying its callback, including a target moved during the SQL read. A callback
  may enqueue successor work; the pump stops using its previous map iterators.
  Reads completed while the actor is unloaded leave its cache untouched and resume
  from the subsequent load's current ownership. Query/callback allocation remains
  inside the existing admission guard. Native ASan/UBSan coverage passed for
  rejected/thrown read admission, link loss, unloaded resume, moved target,
  reentrant callback and exactly-once failure delivery. Build and the existing
  grant/reconciliation, newbie and prompt checks passed after upstream integration.
- Racial/cast conversion: `957cab3ac`, `branch/issue-870-racial-casting`,
  [PR #918](https://github.com/LuminariMUD/Duris/pull/918), ready after #897.
  Full racial pulse (21 races, rebalance/help, groundfighting, reflection boundaries,
  adjustment, saved properties/restart and 100-row listing), multiplier .5/1/2,
  default 20-cast probe and 20-cast `--budget-usec 2000` probe passed.
  Commands use `tests/async/with_disposable_mariadb.sh python3 tests/async/<runner>`
  with `--server bin/server/dms_new` for all three runners. Logs: `racial-pulse-run.log`,
  `spellcast-multiplier-run.log`, `cast-timing-default-run.log`, `cast-timing-budget-run.log`.
- Pwipe code: `0de5f6bc9` removes the impossible backend mode; `a8e18cb7b`
  separates mode-specific failure artifacts; `112f0dddb` seeds the website's
  verified synthetic donor email. Direct, Redis, Redis re-enable, reward-discard
  and full website modes passed. CLI help and all six invalid combinations passed
  (`pwipe-cli.json`). Use the real five-minute countdown; no reduced timing.
- Matched restore: `04439c766` fixes tar extraction permissions. A focused
  reproduction proved `filter="data"` creates directories as 0755 under umask022,
  whereas native recovery locks require private0700. Extract under a temporary
  umask077, restoring the caller's umask afterwards. Earlier wrong-store-image
  diagnosis was incorrect: the guard failed before image decoding. Remove the
  extra reboot/crash-freeze workaround; keep the original clean-stop capture and
  native checks. The full `--redis --restore bin/server/dms_new` retry passed
  (ordinary user, real five-minute countdown, fresh private SQL store, original
  bank9/reward3/PID/files and authenticated world, save/reconnect/second boot,
  post-wipe source SQL/files/Redis and immutable backup unchanged). Report revision
  `04439c766`, binary024e32b9dd95… above; `pwipe-restore-run.log` and copied
  `pwipe-runtime-mariadb-redis-restore.json`. First and second failure evidence is
  retained. [PR #922](https://github.com/LuminariMUD/Duris/pull/922) is ready.
- Website qualification uses a detached private DurisWeb worktree at
  `bin/tests/issue-870/website`, pinned to `51549c2`, with no `.env` files.
  Frozen offline pnpm install and backend tsc build passed. Node26.11.1 and
  pnpm12.10.1 must be on PATH. The wrapper uses `TEST_DB_IMAGE=mysql:8.0`;
  `--redis --website <absolute-fixture-path> bin/server/dms_new` passed actual
  HTTP/session/WHO/presence/cache/websocket drain, queued synthetic webhook and
  exactly-once durable donation delivery. Current signup keeps email empty until
  verification; seed that verified donor precondition offline. Mail, Discord,
  analytics and real payment services remain disabled. No website source change.
- Divine refusal: `e7e83d8c3`, `branch/issue-870-divine-refusal-journey`,
  [PR #923](https://github.com/LuminariMUD/Duris/pull/923), ready above #922.
  SQL promotion replaces the embedded C++
  snapshot writer/compiler; preserve the shared drain helper's five consumers.
  `tests/async/with_disposable_mariadb.sh python3 tests/async/run_divine_refusal_journey.py bin/server/dms_new`
  passed both full A/B scenarios: disabled dispatch2/2, enabled dispatch0/2,
  retry lock, exempt commands and mixed non-Cleric orders. Evidence:
  `bin/tests/issue-870/divine-refusal-run.log`; ordinary server SHA-256:
  `024e32b9dd95cf654ed9dbcadb937785d444b20967dbd11ce73d845aed3c875e`.
- Other #880 standalone proof: issue37 zone reset/restart/restart-reset and the
  complete Misty Vale crafting/portals/switches/population/canoe/rod/fishing/reward
  persistence journey passed. Evidence: `issue37-run.log`,
  `misty-vale-run.log` and copied reports under `bin/tests/issue-870/`.
  Their unchanged source was exercised with the recorded 4f13e85355b8… binary.
- Container follow-up `bbb0aca1b` is pushed on #903 and forwarded through the stack.
  Current compiled server SHA-256 is
  `024e32b9dd95cf654ed9dbcadb937785d444b20967dbd11ce73d845aed3c875e`.
  Latest native ASan/UBSan, creation-batch/reconciliation, newbie and prompt checks
  and `make -C src -j4` passed. Final aggregate gates must qualify this integration.
- Colorization: `9939996fb`, `branch/issue-870-colorization-journey`,
  [PR #925](https://github.com/LuminariMUD/Duris/pull/925), ready after #924, removes
  inspector/state setup and uses the shared MariaDB authority. All 65 checks and
  15 frames passed (two accounts, independent recipient GMCP/ANSI colors, saved
  choices/reconnect, paging, coherent animation, motion/static, authored mural,
  previews and shutdown). Evidence: `colorization-run.log`, `colorization.json`;
  binary SHA-256 024e32b9dd95… above. The active release guide now gives the exact
  disposable MariaDB reproduction command. No native gameplay/rendering change.
- Weapon actions: `2b52eaf2e` uses the shared MariaDB authority and removes the
  inspector option. `92d835596` applies the existing ten-minute natural-selection
  deadline to both families: the original 45-second packed window timed out while
  the player dodged every melee hit (failure log retained). All three packed cases
  now passed: legacy damage, 2.002s warning-to-hit, and .250s flee with no damage
  and a fizzle. Avernus off/hold and enabled/hold passed, but its flee case
  timed out before a natural selection within600s. `9f914ede8` raises only the
  synthetic Avernus NPC to the mortal cap56, improving ordinary hit frequency;
  native 1/25 selection and damage/timing/cancellation assertions remain unchanged.
  The complete Avernus matrix passed: disabled damage18.268s, enabled windup2.002s,
  flee.250s with no damage and fizzle. Packed's three cases were already green.
  Prior partial results/failure remain under `pre-fixture-repair-weapon-avernus*`.
  [PR #924](https://github.com/LuminariMUD/Duris/pull/924) is ready; the active weapon
  guide now publishes both exact disposable commands.
- Copyover: `d3df89e40` uses one shared MariaDB setup for ordinary and Redis modes,
  removes the duplicate schema installer, and replaces corrupt-snapshot injection
  with a real rejecting player-save SQL trigger. The first plain case already
  passed all failures and successful socket/session recovery; default MCCP and
  Redis fault and fresh minimal-world modes also passed. Both full-world fresh
  and preserving hotboot modes subsequently passed, plain and MCCP in each.
  UID10001 first failed before boot: Linux protected_regular blocks O_CREAT on
  the ordinary user's shared /tmp port-lock file. `cfea325b8` reopens that same
  existing lock without O_CREAT on PermissionError; confirmed root r+ succeeds.
  Keep shared fcntl reservations. Both UID10001 plain/MCCP retries passed; initial
  failure retained. Full-world first failed before injected file-open failure:
  fresh absent-artifact catalog rows publish asynchronously in batches4. Use the
  existing paged `world persistence` health output to await zero dirty/pending
  artifact/guild work; repeat after replacement boot before the mismatched-account
  rehearsal (`004272af6`, `e74ff78a6`, `de0ae203c`). Native guards stay intact.
  The prior full-world run passed its actual exec and original socket recovery,
  then failed at the second drain before mismatch injection. Both earlier failures
  and the initial pager mistake are retained. All eleven cases now passed:
  default minimal, fresh minimal, preserving full-world, fresh full-world and
  UID10001 (plain/MCCP each), plus Redis checkpoint/failed-replacement faults.
  Plain fresh cases also refused a mismatched authenticated account on the inherited
  socket. Logs: `copyover-{default,redis,fresh,full-world,full-world-preserve,nonroot}-run.log`.
  [PR #926](https://github.com/LuminariMUD/Duris/pull/926) is qualified for review.
- Discord: `a98106d9e` seeds staff in MariaDB. The unchanged bridge sink is at
  `/home/aiwithapex/projects/discord-mud-chat/scripts/testing/duris-game-sink.js`,
  clean checkout `70865ecafb0aeb9b9ac71da37696e416d892ce4c`. Its dependencies load
  using Node26.11.1; the driver uses loopback config and a mocked Discord client,
  without dotenv or real Discord access. Complete runtime qualification passed:
  petition/ptell, concealment/exclusions, one-way ingress, original player/bridge
  sockets across failed exec and successful copyover, save/reload, offline/disabled
  relay, audit deduplication and ordinary shutdown. `8de873801` corrects a stale
  fixture expectation: failed exec removes sealed recovery files. Initial failure
  retained as `discord-game-initial-failed-exec.log`; success `discord-game-run.log`.
  [PR #928](https://github.com/LuminariMUD/Duris/pull/928) is ready after #926.
- Live item conversion: `aa5f4f231`, `branch/issue-870-item-mana-journeys`, uses
  `mariadb_authority()` and the Server helper's existing environment injection.
  Keep Server's current signature: eleven other real journeys still import it;
  no new helper API or duplicate server fixture is needed. `mana_rows(sql)` reads
  all eight authority columns from `artifact_mana`, preserving reserve/version,
  crash/restart, recharge and clamping assertions. No binary file decoder remains.
  Native artifacts are created by real staff `load obj` commands after offline SQL
  promotion, saved and demoted to their original mortal levels; check the resulting
  actual UID instead of fabricating UID1000922. Corpse custody uses existing
  `inspect_authority(sql)`. The existing optional failure-retention mode captures
  the private synthetic SQL dump in place of copying retired domain files.
- The overlap fixture modified mini objects/resets after configure had copied
  them into the generated world. Area-debugger mode2 reads those generated files;
  copy the two modified inputs so dual-weapon/caster cases exercise their intended
  equipment. `6a079045d` replaces obsolete boon-toggle response expectations with
  the current automatic-boon response, preserving the native behavior.
  All four parsers/compiles and diff checks pass. Every runtime case passed:
  Studio complete/abort and crash, Tsunami disabled/complete/abort including real
  corpse loot and unchanged mana, Ioun real incoming spell/paid deflection,
  operator toggles/reload/invalid catalog/private metrics, sustained PvE and low-
  reserve player refusal/recharge, and both dual-weapon/mortal-cast overlaps.
  `4487cc3a6` checkpoints the carried Studio source before the crash-only case;
  otherwise the test killed the process before saving the picked-up item at all.
  Its pending action still never revives and the committed debit remains exact.
  Reused unchanged passing complete/abort evidence and reran the affected crash
  case with `--family studio --case on-crash`; both raw JSONs and their three-case
  aggregate are retained. Initial boon and missing-checkpoint failures remain.
  Evidence: `item-pilot-{studio,studio-crash,tsunami,ioun}*.json/.log`,
  `item-{config,encounter,overlap}*.json/.log`. Native ioun took173.415s to intercept;
  recharge took5.506s from1500 to3000 units; dual sources completed33.534s;
  ordinary mortal casting overlapped its own passive release in4.755s.
  [PR #931](https://github.com/LuminariMUD/Duris/pull/931) is qualified for review.
  The active item rollout runbook now supplies all reproduction commands.
- Named-set discovery: the six runners form a real shared-authority sequence:
  transfer produces gear/containers and a measured baseline consumed by edit/clone,
  pet and shop runners. Rollback copies the authority and changes binaries twice.
  SQL lifetime must span that sequence and the rollback copy must preserve its
  source SQL as well as filesystem evidence. Do not create independent databases
  per consumer or replace generated gear with guessed UIDs. No named-set edit yet;
  inspect the retained compatibility source/catalog before choosing its MariaDB build.
- Current head: `branch/issue-870-named-set-journeys`; no live test sessions remain
  from the preceding batch. #922, #923, #924, #925, #926, #928 and #931 are qualified; the
  earlier stack remains as listed above. All PRs carry enhancement/bug/documentation
  labels as appropriate. Do not merge or deploy without the user's instruction.
- Named-set conversion is now implemented but unqualified. Keep the existing
  six consumer scripts and their assertions. The helper's specific batch entry
  owns one `mariadb_authority()` lifetime, creates the synthetic account through
  the real protocol, and runs transfer → edit/clone → pet → shop → all16 wear
  zones → copied-authority rollback → existing chest/report journeys. Shared
  runtime/server paths are passed only to these concrete consumers; no backend
  selector or generic fixture framework. Each wear result is retained separately.
- SQL readers preserve full inventory parent indices/UID graphs, named provenance,
  permanent HP/Constitution/bit modifiers, saved affects and pet custody/holds.
  SQL intentionally does not restore transient item affects (see
  `src/sql/item_instance_fields.h`); keep the native measured HP/spell assertions
  after reload rather than decoding an obsolete snapshot. The old C++ snapshot
  compiler/fixture is removed after confirming it has no other callers.
- Rollback keeps one copied SQL schema through both binary changes. Dump the
  stopped source, hash SQL/accounts/journals before/after, import directly into another
  disposable schema. The maintained bootstrap has no views and the captured dump
  has no qualified schema identifiers; remove the speculative rebinding machinery. Preserve every
  copied UID/revision/parent/slot and all original gameplay/report assertions.
  The batch retains a private synthetic SQL dump before its authority is removed.
- The compatibility checkpoint is current native code with only its catalog array
  replaced by the115-row array from `bff1043fd`, matching the existing rollback
  rehearsal's purpose and previous plan to keep integrated safety fixes. It is
  **not** represented as a full historical server. Generated source:
  `bin/tests/named-set-rollback-source/named_sets.c`; binary:
  `bin/tests/named-set-rollback-source/dms-115-catalog`; metadata `build.json`.
  The maintained Makefile compiled that one replacement object with normal flags
  and relinked current objects while excluding `item/named_sets.o`; ordinary
  binary remained024e32b9dd95… . Variant source SHA-256:
  `2fb1c22f2e20f125df0bd8bb03509e4ecccbc0394a7d4247bca3b02ea0a2f988`;
  variant binary SHA-256:
  `1576a431f07c49a21f18c79aa85fe0146e98ca83c8b269be4a850d7f3e8b62b8`.
  Build log: `bin/tests/issue-870/named-set-compat-build.log`.
- Current named-set qualification:
  `python3 tests/async/named_set_gameplay.py bin/tests/named-set-rollback-source/dms-115-catalog`,
  running from `cacfbc8be`; log `bin/tests/issue-870/named-set-sequence-run.log`.
  Artifacts: `bin/tests/named-set-mariadb-sequence-ununney2` (private SQL dump is
  retained on exit). Transfer already passed two-level native give, original UID/
  origin/parent/slot persistence through nested/worn reboots and independent
  ordinary Armor non-stacking at -90 Armor Points. Edit/clone also passed renamed
  originals, five distinct recursive clone UIDs, mixed outfit benefits and reboot.
  Pet then stopped on a legitimate NULL pet_uid for an empty saved pet. Mirror the
  native loader's COALESCE(...,0), without inventing a UID. Resume the captured
  SQL fixture in a fresh disposable schema, checking its dump and binary hashes;
  preserve existing generated identities and reuse the two unaffected passes.
  Original failure evidence: `bin/tests/issue-870/named-set-initial-pet-failure/`.
  The entry self-enters the disposable wrapper. The retry adds
  `--resume bin/tests/named-set-mariadb-sequence-ununney2`; its metadata explicitly
  records reused cases. Inspect its terminal result
  and every case before marking batch3 complete; preserve failures and repair
  actual defects without dropping cases. Historical assassin comparison,
  naming/docs and full regression/DB gates still follow. No whole-issue claim.
