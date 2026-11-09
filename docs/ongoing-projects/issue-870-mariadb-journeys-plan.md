# Issue #870: finish the MariaDB journey conversion

Status: all 14 partial-conversion runners and telemetry performance passed; standalone racial/cast conversion is under qualification. Aggregate gates remain.
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

The worktree was created at `81c969a63`, the original inspected #880 head.
On 2026-11-09, #873 and #874 merged into master; #880 advanced to
`6f4f1a975`. The baseline branch now merges that updated #880 and master
`f53e564f8` without rewriting published history. Preserve the item valuation,
ship, live-entity index and feedback/migration changes authored upstream.
The final build and suites must qualify this integrated stack.

Review dependencies start with [#880](https://github.com/LuminariMUD/Duris/pull/880)
then [#887](https://github.com/LuminariMUD/Duris/pull/887). #880 adopted
byte-identical launch-gate and shop-bootstrap repairs from #888, verified with
`git diff --exit-code` for both files. Retire that duplicate PR and target #890
at #887; later PRs retain their dependency order.

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

- Ready PR stack: #887 baseline → #888 launch/shop bootstrap → #890 login/news/
  onboarding/death → #891 corpses → #892 cache/flight → #893 Cleric/aura.
  #895 telemetry and #896 rent/artifact above it are ready. #897 shop conversion is draft pending its reproduced server fix.
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
  [draft PR #897](https://github.com/LuminariMUD/Duris/pull/897). Its full run
  failed at the preserved fresh/unsaved staff-bag purchase: zero items delivered,
  no charge, before the delayed-sale leg. The failure and report are preserved
  as `bin/tests/issue-870/shop-unsaved-bag-failure-*`. Do not drop that case.
  The new delayed-sale leg holds `critical_operation_inbox` with a dedicated
  SQL session and requires `ACCOUNT MENU` before unlocking; it is still unrun.
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
- Pwipe matrix: direct, Redis, Redis re-enable and reward-discard modes passed.
  The matched restore and website modes failed; preserve their failed reports and
  logs under `bin/tests/issue-870/`. Restore copied a source-bound locker shutdown
  image into a different private SQL store. Reconcile that image on the original
  source before freezing the portable backup; do not clear or bypass the guard.
  Website donation association needs a verified synthetic email: current signup
  intentionally stores an empty email until verification. Seed that fixture
  precondition while the MUD is offline; keep mail/providers disabled.
- Latest code and plan are committed/pushed on the stacked branches. The worktree
  may be on a parent while its evidence is updated; check `git status` before
  editing, then continue from `branch/issue-870-container-grants-fix` for the server repair.
- Remaining batches 2–6 are still required: standalone gameplay/protocol/timing,
  named sets and historical assassin comparison, four item journeys, naming/docs,
  full regression/DB gates and qualification of #880's other standalone edits.
  No aggregate result or whole-issue completion is claimed yet.
