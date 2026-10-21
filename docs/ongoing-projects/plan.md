# Issue #59: fastest useful PostHog delivery

> **DO NOT SCOPE CREEP. WE ARE OUT OF TIME AND TOKENS. DELIVER FAST.**
>
> Owner directive: finish only the agreed reduced delivery. Reuse existing code
> and valid evidence. No optional features, refactors, test matrices, new test
> frameworks, repeated branch syncing, or extra qualification stages. Fix only
> defects that prevent the agreed outcome; run the smallest relevant checks.
> Deferred work must never become a condition for closing issue #59.
> Preserve the agreed correctness and completion requirements; cut extra work.

Status: **resumed by the owner; implementation incomplete; production disabled.**
Tracking: [Duris #59](https://github.com/LuminariMUD/Duris/issues/59).
Working branch: `issue-59-posthog-reports`, based on acceptance PR #262.
Runtime PR #261 is the preceding dependency.
The earlier issue-107 plan remains in [plan-issue-107.md](plan-issue-107.md).
The intervening Assassin plan is preserved byte-for-byte in
[plan-issue-187.md](plan-issue-187.md).

The owner has authorized a smaller first delivery that retains at least 75% of
value and has removed the container/network-isolation requirement completely.
Disposable native tests are the accepted environment. This plan supersedes the
previous implementation sequence and its extra completion gates. Issue #59
closes when this reduced delivery meets the completion criteria below. Deferred
work is outside #59's closure requirements and remains optional follow-up.
Implementation is active within the agreed reduced scope. The worker HTTPS component is in [PR #260](https://github.com/LuminariMUD/Duris/pull/260); runtime
integration is ready for review in [PR #261](https://github.com/LuminariMUD/Duris/pull/261).
Gameplay/report/performance acceptance remains incomplete. Production export remains disabled.

## Delivery target and estimate

**DO NOT SCOPE CREEP. WE ARE OUT OF TIME AND TOKENS. DELIVER FAST.**

**The repeated 3–5 hour remaining estimate is withdrawn. No replacement ETA
has been validated.** Do not reset the estimate after time has elapsed or present
historical passing results as proof for a changed revision. The owner has resumed implementation within the agreed scope.

The remaining delivery is the existing gameplay/failure acceptance, the agreed
performance/volume evidence, four report views plus health, one bounded cloud
test, and the necessary handoff. Reuse passing component evidence. Investigate
only the current failed assertions before rerunning affected checks. Production
deployment scheduling and reviewer availability are separate.

No Docker setup, additional machine, database installation, fixed soak period,
CI wait, or extra qualification stage belongs on this delivery path. Required
code review still applies.

### What “at least 75%” means here

**DO NOT SCOPE CREEP. WE ARE OUT OF TIME AND TOKENS. DELIVER FAST.**

Retain every analytics domain named in the issue and the controls that make its
data useful and affordable. The following is an explicit planning value model,
not a measured user-satisfaction score or a claim that implementation is 85% done.

| Outcome | Value weight | Retained in this delivery |
| --- | ---: | ---: |
| Character activity/returns and correctly allocated time | 35 | 35 |
| Observed XP, attempts, modifiers and level changes | 15 | 15 |
| Encounter outcomes, participant and separate pet contributions | 15 | 15 |
| Bounded delivery, privacy, durable quota, useful health and lifecycle correctness | 20 | 20 |
| Complete removal of legacy SQL boot/schema prerequisites | 10 | 0 — deferred |
| Broad engine/capacity qualification beyond the release fixture | 5 | 0 — deferred |
| **Total** | **100** | **85** |

This retains an estimated **85% of the original plan's value**, with all four
user-facing report domains. The tradeoff is an existing-schema dependency for
SQL gameplay and narrower capacity evidence. Core correctness, privacy and
quota limits are acceptance conditions, not optional points to trade away.

## Scope decisions

**DO NOT SCOPE CREEP. WE ARE OUT OF TIME AND TOKENS. DELIVER FAST.**
The reduced scope below is the delivery boundary. Deferred work stays deferred.

| Keep now | Simplify now | Defer beyond this delivery |
| --- | --- | --- |
| All six exported event families and the existing reducers | Reuse the implemented reducer/sender/journal APIs directly in the existing worker | Removing the nine old telemetry tables from the mandatory SQL boot inventory |
| SQL-backed and flat-file gameplay | One adapted native player journey with backend selection and a fake HTTPS receiver | Regenerating the two engine fingerprints and the absent/drifted legacy-table matrix |
| Four useful report views and one saved health query | Plain saved insights/tables with captured-dimension filters and exact query definitions | Additional dashboards, presentation polish and historical report parity |
| Essential lifecycle, storage, retry and arithmetic regressions | Reuse component evidence; add only integration-specific checks | New cross-products of already-covered faults and repeated whole-repository qualification |
| Measured gameplay/save overhead and a complete event forecast | Paired off/mock-HTTPS runs on one declared representative fixture; one small real-cloud smoke | Full 200-player qualification, all workload ramps and performance runs against real cloud latency |
| Disable the obsolete SQL writer and replaced live rollup scheduling | Remove the writer from active delivery/linking and obsolete active settings | Bulk removal of historical-only writer/report files and their tests |

The retained SQL boot checks and historical tables remain intact. SQL gameplay
still requires its existing schema; PostHog must require no telemetry DB account
or active telemetry SQL connection. Flat-file gameplay has no SQL requirement.
Do not claim full SQL schema decoupling; it is not required to close issue #59.
Do not weaken gameplay schema checks to make a fixture start.

No SDK, service, sink framework, second queue, payload spool, new instrumentation,
backfill, account linkage, paid analytics add-on or balance change is needed.
No production data, migration history or independent reward tooling is removed.

PR #259 review carry-forward: the native `rollover-season` command preserves
history and exhausts the current UTC day without changing the sender allocation.
Failed registration retries reuse one terminal quota archive. The storage guide
documents both wire versions, witness sizes and recovery. Focused journal, CLI,
worker and sanitizer regressions passed; integrated PostHog reduction passes 57
scenarios in each backend after carrying the earlier reducer fixes forward.

Repeated `exhaust-day` and `rollover-season` commands for an already exhausted
current day/season preserve the generation, ledger/witness bytes and archive count.
Retries synchronize the directory to finish a prior successful rename; new-day or
new-season exhaustion still publishes normally. Native, CLI and publication-fault
regressions verify this follow-up review repair.

## Current state and quick checks

**DO NOT SCOPE CREEP. WE ARE OUT OF TIME AND TOKENS. DELIVER FAST.**
Reuse valid evidence; repeat checks only for relevant changes or actual failures.

The implemented pieces are on the existing stack. Preserve the current worktree;
do not restart these components or reimplement their contracts.

| Piece | Existing evidence / location |
| --- | --- |
| Setup and percentile correction | PRs [252](https://github.com/LuminariMUD/Duris/pull/252), [253](https://github.com/LuminariMUD/Duris/pull/253); integer per-mille p99/p99.9 regressions already implemented. |
| Opaque identities, UTC/UUID/integer encodings and volume fixture | [PR 254](https://github.com/LuminariMUD/Duris/pull/254), `telemetry_posthog.*`, `fixtures/telemetry/posthog/{encodings,volume}.json`. |
| Character, encounter/combat and health reduction | PRs [255](https://github.com/LuminariMUD/Duris/pull/255), [257](https://github.com/LuminariMUD/Duris/pull/257), [258](https://github.com/LuminariMUD/Duris/pull/258). |
| Durable quota and native state tool | [PR 259](https://github.com/LuminariMUD/Duris/pull/259); existing outage-journal regressions include reservation, restart, corruption and publication failure. |
| Worker HTTPS sender | PR #260 ready for review; component suite and both full builds pass. Runtime integration is in #261; acceptance work is on this branch. |

Checks completed during this replanning pass on 2026-10-21 UTC:

- Fixed the test-only DNS endpoint to use `stall.invalid`, avoiding libcurl's
  localhost shortcut. The injected resolver writes a marker proving it ran;
  the test retains deadline/cancellation/ambiguous-loss assertions and verifies
  zero received requests. Production endpoint handling is unchanged.
- `nice -n 10 python3 tests/async/test_telemetry_posthog.py` passed in MariaDB
  and flat-file build modes under UBSan: **42 reducer scenarios and 29 HTTPS
  scenarios per mode**, plus encodings and all four volume forecasts. Evidence:
  `bin/issue59/fast-plan/posthog.log`. This includes the previously unreached
  monotonic-clock case and the stalled-DNS cancellation case.
- `env -i PATH="$PATH" LANG=C.UTF-8 ENVIRONMENT=local nice -n 10 python3
  tests/async/test_player_base_stats_mysql.py` passed using native MariaDB
  **11.8.6**, disposable socket-only databases and synthetic data. Fresh and
  upgrade schemas passed migrations, the runtime compatibility verifier and
  native repository save/readback checks. Evidence: `bin/issue59/fast-plan/native-db.log`.
  This did not run the optional interactive login journey and does not prove
  PostHog runtime integration. It establishes that another engine installation
  is not a prerequisite for the retained-schema native fixture.
- Full `nice -n 10 make -C src -j1 PERSISTENCE_BACKEND=<backend>
  BIN_ROOT="$PWD/bin/issue59/<backend>"` builds passed sequentially for
  `mariadb` and `flatfile`. Evidence: `bin/issue59/fast-plan/build-<backend>.log`.
  The earlier failed `build-mariadb-http.log` is superseded by these results.
- `python3 tests/async/test_telemetry_contract_headers.py` passed; evidence:
  `bin/issue59/fast-plan/headers.log`. Formatting and whitespace checks passed.
- Read-only PostHog tools confirmed project **678214**, **Duris SBS PostHog**,
  UTC, admin access, one starter dashboard, `ingested_event=false`, free billing,
  no active subscription and **0 / 1,000,000** analytics events reported for the
  current period. This is a readiness snapshot, not ingestion or write proof.
  Recheck usage before cloud capture. No cloud events or dashboard changes were
  made during replanning.

The native executable is built but not deployed. Do not use these component
results to claim real gameplay delivery, production performance or cloud totals.

## Contracts to reuse

**DO NOT SCOPE CREEP. WE ARE OUT OF TIME AND TOKENS. DELIVER FAST.**
Reuse these contracts; do not redesign or expand them for this delivery.

[CONTRACT.md](../telemetry/CONTRACT.md) is the implementation reference for event
schemas, identity, reducer bounds, delivery and quota. Keep its completed behavior;
update only actual integration changes. The old plan's duplicated design prose
is replaced by that reference and the following integration invariants.

- Existing value-only gameplay capture → bounded queue → existing worker →
  reducer → immutable output → HTTPS. Each admitted native record is consumed
  once or explicitly lost. HTTP retries never feed records into reduction again.
- Keep HMAC character identities scoped by environment/season, logical session
  identity through reconnect/copyover, distinct run/pet IDs, immutable event UUIDs
  and lossless integer encodings. No raw PIDs, names, account identifiers, IPs,
  commands, chat, room locations or secrets leave the game.
- Time charts sum observed interval deltas. Checkpoints reconcile gaps separately.
  Preserve captured dimensions, XP attempt/source/modifier and level boundaries,
  pet/owner separation, and null/unknown coverage. Never invent a zero or fill
  historical dimensions from current game state.
- Keep the existing bounds: 256 sessions, 64 configurations, 128 runs with
  64 combined player/pet identities, 32 time and 32 XP buckets per fragment,
  128 output events / 512 KiB, 32 KiB per event, 64 events / 256 KiB per HTTP
  batch, and 120-second retained output/terminal wait limits.
- Use **30-minute export summaries for the first release**. The reducer already
  accepts 1,800 seconds. The declared 200-average-character mix forecasts
  **396,454 submissions/31 days**, versus **706,077** at 15 minutes. This selects
  the issue's permitted volume fallback before spending time tuning two rollout
  configurations. It does not change native capture cadence or prove capacity.
  Lifecycle/level/configuration/day boundaries still flush as required.
- Keep 1s connect / 2s total HTTP timeouts, nearer lifecycle deadlines, five
  immutable attempts, bounded Retry-After, paced recovery and permanent-error
  circuits. TLS and host checks stay enabled; no redirect or environment proxy
  can carry the token. Keep asynchronous DNS/QUICK_EXIT and owner-safe teardown.
- Keep normal-load submissions **≤450,000/31 days**, combined Duris attempts
  **≤20,000/UTC day**, and projected shared account usage **<700,000/billing
  cycle**. Reserve before every attempt; retries count again. Production gets
  at most 19,900/day including 100 reserved health events; tagged tests get at
  most 100 total submissions. Other environments use mocks. No refund after
  an ambiguous response, no automatic allowance reset and no next-day backlog.
- Missing/corrupt quota state, failed publication, clock rollback and ownership
  conflict stop export while gameplay remains available. Preserve journal
  history and the existing initialization/exhaust-day recovery tool.

## Implementation sequence

**DO NOT SCOPE CREEP. WE ARE OUT OF TIME AND TOKENS. DELIVER FAST.**
On an authorized resume, finish the existing sequence without adding stages.

### 1. Connect the existing worker and finish lifecycle behavior

**DO NOT SCOPE CREEP. WE ARE OUT OF TIME AND TOKENS. DELIVER FAST.**
Preserve implemented behavior; change it only for a demonstrated delivery defect.

Change `telemetry_runtime.*`, `telemetry_transport.*`, their private types,
`telemetry_config.*`, `telemetry_health.*`, `src/Makefile` and the copyover call
site only as required. Reuse the existing queue and lifecycle coordinator.

Replace the production SQL repository binding with direct reducer/sender calls.
Remove the old SQL retry/commit interpretation from this path. Keep native
admission sequence and age; at a timer boundary capture the admitted tail,
consume through that fence, then seal. A later old observation becomes a partial
fragment under the existing reducer rules. Pump the sender while draining so
its output buffer cannot starve behind a terminal burst.

Initialize reducer and sender in the worker after journal ownership. The journal
outlives sender close. Checkpoint dirty coverage on a 60-second cadence,
plus required lifecycle/incident boundaries and durable send reservations;
expose failed checkpoints and pace storage retries. Publish a coherent copied
health snapshot for `world telemetry` and payload-free local logs. Include
native admission/consumption, output occupancy/expiry, attempted/acknowledged/
ambiguous/suppressed events, quota and journal faults; HTTP acknowledgement is
not a claim of query-visible ingestion.

Enable the PostHog path in both persistence builds. Validate token, the fixed US
host, dedicated identity key, scope, property catalog and budget without falling
back to raw IDs or silently generating a new identity key at boot. Retain opt-in
startup and the existing effective-property catalog. Set 1,800 seconds in runtime
configuration; the component's 900-second default is not the release setting.
No new operator tuning API is needed.

Copyover preserves valid logical-session handoff regardless of HTTP outcome.
Keep the 250ms game-thread flush wait; preserve identity/cumulative counters and
mark abandoned queue/accumulator/output tails incomplete. No game-thread HTTP,
fsync or unbounded join. Check successful exec, failed exec, network loss,
detach/reconnect, shutdown and next-process journal ownership/quota continuity.

Remove SQL telemetry credentials and the writer from the active path and active
linking. Inventory replaced rollup/report scheduling in the deployment handoff.
Keep gameplay SQL helpers and historical/reward consumers. Leave `src/sql/sql.c`
boot inventory, runtime compatibility fingerprints and immutable migrations
unchanged for this delivery. Do not add a SQL fallback or permanent dual writing.

### 2. Prove the real path with disposable native fixtures

**DO NOT SCOPE CREEP. WE ARE OUT OF TIME AND TOKENS. DELIVER FAST.**
Use existing fixtures and the agreed checks. Do not add a broader test matrix.

Adapt `tests/async/run_telemetry_player_journey.py` once for both backends and
fake HTTPS, reusing existing combat, flat-file and copyover clients. Use an
allowlisted environment, `ENVIRONMENT=local`, synthetic accounts/characters,
separate runtime/state/journal directories, distinct world IDs >=1000 and
loopback ports. SQL uses a fresh task-owned native MariaDB database; flat-file
uses its own files. Never source the host `.env` or copy live player/DB data.
Docker, namespaces, sudo and another machine are not prerequisites.

One journey per backend covers login, recognized action, idle/linkdead,
combat/XP and a level transition, groups/pets, save/reload, reconnect, successful
and failed copyover, and shutdown. Assert received payloads, conservation and
stable identities. Add one bounded outage/recovery path with a small quota to
prove gameplay still saves, local health reports loss and copyover cannot reset
the budget. Exercise journal failure and unknown crash tail in the existing
native runtime harness rather than duplicating the full storage fault suite in
every game journey.

Use the existing benchmark/measurement seams for repeated matched telemetry-off
and telemetry-on/mock-HTTPS runs with ordinary saves. Start with three paired
runs on the same declared workload and build; record client count, sample count,
pulse/command/save p99, CPU/RSS, backlog, output bytes/events and journal cost.
Require no normal-load capture/budget loss or sustained backlog and **≤5% pulse
and save p99 regression**, with the applicable existing host operating bounds
(pulse p99 ≤250ms, event p99 ≤25ms, critical oldest ≤1,000ms, zero sustained event
debt and zero gameplay-thread external I/O). Measure command p99 without adding
a new independent 5% gate. Do not invent a new save SLA or import the entire
older 200-player soak manifest. If noise makes a 5% claim unsupported, repeat only
that comparison or report the gate unresolved; do not call it passed.

Replay the complete declared event mix through the integrated reducer and count
actual sealed events and attempts, including boundary fragments, lifecycle,
encounters, health, configuration and retries. Reconcile those counts with the
volume fixture and project the chosen workload over 31 days. Capacity numbers in
native record fixtures are not concurrent-player evidence. State the measured
workload; broad 200-player capacity certification is deferred.

### 3. Publish the minimum useful reports and verify cloud ingestion

**DO NOT SCOPE CREEP. WE ARE OUT OF TIME AND TOKENS. DELIVER FAST.**
Deliver the specified saved views; no presentation polish or additional reports.

Use existing project **678214** and create one **Duris gameplay telemetry**
dashboard. Keep the starter dashboard. Deliver four saved views plus the saved
health/coverage query; a clear table or trend is enough. No custom UI or extra
cohort/dashboard project is needed.

| View | Minimum useful result and proof |
| --- | --- |
| Character activity/returns | Distinct opaque characters and logical entries/returning characters; reconnect/copyover does not create a new logical entry. Label character, not account/player, retention. |
| Time allocation | Active/idle/unknown/linkdead deltas by captured dimensions, with unknown allocation and reconciliation-only evidence visible. Expand time buckets independently of XP buckets. |
| XP/levels | Requested/computed/applied XP, attempts/zero-applied count and source/modifier allocation; observed level changes and threshold use separately. Observed XP is not a committed-save ledger. |
| Encounters | Runs/outcomes/duration and supported participant contribution totals; separate run/participant and pet/owner rows, with missing evidence visible. |
| Health/coverage | Freshness, suppression/uncertainty, producer/refusal/output limits, quota and journal state. Local health remains authoritative during complete cloud loss. |

Use event-time properties and exact integer conversions already documented in
the contract. Deduplicate by `duris_event_id` before summing or expanding arrays.
Production views filter environment `1`, season `1`, schema `1` and exclude test
traffic. Unknown timestamps are excluded from occurrence-day totals and shown
as unallocated evidence.

After mock tests pass, recheck project/billing/shared usage and run one tagged
synthetic cloud fixture, **at most 100 submissions including repeats/retries**.
Cover all six event families, two logical sessions for one character, reconnect/
copyover, zero-applied XP and a level boundary, pet/owner separation, an incomplete
encounter and repeated UUIDs. Query and reconcile all four views and health;
HTTP 200 alone is insufficient. Poll for ingestion for at most five minutes,
then report delayed ingestion as unresolved and continue local handoff work.
Use the same synthetic rows for query development and acceptance; no second
cloud load campaign. Record saved query definitions/IDs in `REPORTS.md`.

### 4. Finish the handoff and stop at this milestone

**DO NOT SCOPE CREEP. WE ARE OUT OF TIME AND TOKENS. DELIVER FAST.**
Document what is needed to operate this delivery, publish it, and stop.

Update `.env.example`, `REPORTS.md`, and the affected sections of `CONTRACT.md`,
`TRANSPORT.md`, `OUTAGE_STORAGE.md`, `CONFIG_CONTEXT.md` and
`PERFORMANCE_GATE.md`. Mark superseded SQL guidance as historical with short
links; do not rewrite unrelated telemetry documentation. Record actual fixture
commands, measured workload, limitations, sender allocations and revision IDs.
Correct the example's EU-host suggestion to match the implemented US-only sender.

Document dedicated key creation/private backup, reviewed property catalog,
explicit quota initialization, enable/disable and exhaust-day restore recovery.
Explain that editing `.env` does not update a running process and that copyover
may inherit its old environment. Production enablement remains a separately
authorized operation. Rollback disables export while preserving identity/quota/
loss evidence; it does not refund attempts or resume the obsolete SQL writer.

Keep the existing PR stack. Package remaining implementation and acceptance work
in a small number of reviewable commits; do not create a new serial PR stage for
each test or document. Run required local checks and review the actual diff; do
not wait for hosted CI. Do not drop other required review checks.

## Verification and completion

**DO NOT SCOPE CREEP. WE ARE OUT OF TIME AND TOKENS. DELIVER FAST.**
Prove the five existing conditions below. Add no new completion gates.

The initial quick checks are evidence about components only. For integration,
run directly affected tests after their contracts change:

```sh
python3 tests/async/test_telemetry_config.py
python3 tests/async/test_telemetry_transport.py
python3 tests/async/test_telemetry_runtime_integration.py
python3 tests/async/test_telemetry_runtime_outage.py
python3 tests/async/test_telemetry_runtime_exhaustion.py
python3 tests/async/test_telemetry_copyover_format.py
python3 tests/async/test_telemetry_health.py
python3 tests/async/test_telemetry_posthog.py
python3 tests/async/test_telemetry_contract_headers.py
./scripts/format.sh --check
git diff --check
```

Run the existing gameplay-adapter/progression/encounter/combat/outage regressions
when their code or integration contracts change. Run both full builds after the
final C/C++ changes, sequentially with `nice -n 10`, `-j1` and the task-specific
`BIN_ROOT` paths above. The adapted PostHog gameplay commands are `nice -n 10
python3 tests/async/run_telemetry_player_journey.py --backend <mariadb|flatfile>`;
add `--performance` for the paired release fixture. Bounded cloud/query and
integrated volume assertions remain to be completed.
No blanket rerun of unaffected repository suites is needed.

This delivery is done only when:

1. Both gameplay backends reach the PostHog path with the old writer inactive,
   and native records are consumed once without retry double counting.
2. Real native journeys prove conserved time/XP, captured dimensions, logical
   identity, bounded lifecycle behavior and useful local failure/coverage health.
3. Durable quota survives restart/copyover, and critical network/storage failures
   preserve gameplay. Existing component/fault regressions remain green.
4. All four report totals plus health reconcile to queried synthetic cloud data,
   with test exclusion and duplicate handling demonstrated.
5. The measured release fixture passes the retained performance/volume limits,
   and the operational handoff is executable and explicit about remaining limits.

Meeting these five criteria completes issue #59. Deferred SQL boot-schema
cleanup and broader engine/capacity qualification are optional future work,
not closure conditions. Record the retained schema dependency and measured
workload honestly; deferral does not permit weaker gameplay schema checks,
routine quota loss, incorrect totals or an unbounded exporter. Production
activation is separate and is not a condition for closing this implementation
ticket.

## Implementation handoff — 2026-10-21 UTC

**DO NOT SCOPE CREEP. WE ARE OUT OF TIME AND TOKENS. DELIVER FAST.**
Implementation has resumed. Use the current revision and
existing evidence; do not restart completed work or repeatedly chase moving PR
bases. The older progress notes below are historical, not a fresh completion
claim or a current ETA.

Completed and pushed:

- Sender [PR #260](https://github.com/LuminariMUD/Duris/pull/260), branch
  `issue-59-posthog-http`, revision `d540b778c`, base quota PR #259: bounded
  worker TLS batches, immutable retries, durable quota, cancellation and health.
- Runtime [PR #261](https://github.com/LuminariMUD/Duris/pull/261), branch
  `issue-59-posthog-runtime`, implementation `6ea2ab792`, latest handoff
  `8db892ac9`, stacked on #260. Ready for review. Direct fenced reducer delivery
  replaces the production SQL writer in both persistence builds. Copyover keeps
  identity through failed delivery; cached health reports consumed records and
  sender/quota state. Version-3 outage observations retain consumed sequence/
  counts without claiming durable cloud ingestion; v1/v2 remain readable.
- Native runtime HTTPS cases: `python3 tests/async/test_telemetry_runtime_integration.py
  --posthog` passed nine cases per build under UBSan (18 total): exact time,
  restart quota, cancellation/failed exec, exhaustion, storage publication,
  clock rollback, missing identity/quota and journal ownership. Evidence:
  `bin/issue59/fast-plan/runtime-posthog.log`.
- Focused transport normal/ASan/UBSan/TSan, config, health, contract headers,
  copyover wire, activity/session integration, legacy lifecycle/exhaustion/
  outage, gameplay adapters and journal tests passed. Evidence:
  `bin/issue59/fast-plan/*runtime*.log` and `copyover.log`.
- Both full builds and the state tool passed at the final runtime revision:
  `nice -n 10 make -C src -j1 PERSISTENCE_BACKEND=<backend>
  BIN_ROOT="$PWD/bin/issue59/<backend>" all telemetry-state`.
  Logs: `build-runtime-{mariadb,flatfile}-verified.log` in the same evidence
  directory. Neither executable links `telemetry_repository_init`. Formatting,
  whitespace and commit-hook clang-tidy passed. No production activation.

Current uncommitted chunk: `issue-59-posthog-acceptance`.

- Adapted `tests/async/run_telemetry_player_journey.py` runs disposable native
  games with `--backend flatfile` or `--backend mariadb`. It reuses the existing
  combat/copyover clients and fixture, and the socket-only `private_database`
  helper. Only the two test-seam worker objects are rebuilt before relinking
  already-built game objects under `bin/`; production binaries are unchanged.
- The core journey passed in both backends: save/reload, active/idle/linkdead,
  reconnect, failed/successful exec, one logical session and exact time
  conservation. Each received 13 events. Logs:
  `bin/issue59/fast-plan/gameplay-posthog-{flatfile,mariadb}.log`; synthetic
  payloads: `bin/issue59/acceptance/<backend>-events.json`.
- Native MariaDB cannot write a datadir under this host's `/home`; the same
  disposable helper works under a private `/tmp/duris-telemetry-db-*` directory.
  Only the fixture location changed. No production permissions or DB helper
  were changed. The runner now stops game writers before closing the private
  database, including on failure.
- Expanded domain/failure journey now passes in both backends. It adds a mortal
  companion's combat XP and level transition, groups and separate player/pet
  fights, mock HTTP 503 with continued saves, and durable quota across exec.
  Fixture corrections so far: valid short account name, explicit `look` after
  linkdead reconnect, staff `vis 0` before the companion grants consent, and
  paginated health handling. Logs: `gameplay-posthog-{flatfile,mariadb}-domain.log`.
  Received **36 / 35** events with **46 / 41** attempted/reserved events,
  respectively; no retry duplicates were counted as new reductions. Assertions
  prove one main logical session across exec/reconnect, exact time and XP
  allocation conservation, captured group/level dimensions, positive separate
  pet damage with owner linkage, no private gameplay values in payloads,
  saves during HTTP 503, zero old SQL intervals and persisted quota/producers.
- Expanded journeys reproduced two real adapter defects. Group/pet teardown
  after terminal logout reopened phantom sessions; presence now refuses the
  existing terminal-extraction flag. Pet-first attacks were not attached to an
  owner's run, so their damage had no summary slot; begin now uses the owner
  for the encounter and a separate pet combat actor, and NPC union data is
  excluded from player participants/group keys. Focused adapter regression
  passed under ASan/UBSan (`gameplay-terminal-pet-regression.log`). The full
  game journeys then passed with both fixes. Final focused sanitizer/build
  checks follow a small owner-lookup simplification; earlier successful full
  builds are `build-gameplay-fix-<backend>.log`, final logs are
  `build-acceptance-<backend>.log`.
- Installed clang-format 21 treats `.c` as C while this translation unit builds
  as C++. Its required whole-file check exposed pre-existing formatting drift.
  The mechanically formatted baseline is isolated in commit `e75f017db`, so
  the behavioral repair can be reviewed as a small separate diff. No formatter
  configuration, namespaces, public interfaces or runtime behavior was changed
  by that commit.
- `--performance` runs three matched off/on pairs, alternating order, with one
  client and 120 ordinary saves per run after warmup. A bounded test-link
  wrapper at the existing pulse timer retains raw pulse/event/command samples;
  process fsync samples give a conservative upper bound including journal and
  gameplay persistence. Samples write only on exit. The runner records client
  save/command p99, CPU/RSS and local health. This adds no production telemetry.
  First attempt stopped at the health pager; fixed before collecting a valid
  pair. Current log: `gameplay-posthog-mariadb-performance.log`. No performance
  gate is claimed passed.
- Pause performance collection while gameplay fixture compilation is active;
  the interrupted attempt is diagnostic only. Use the MariaDB build for the
  declared release performance fixture, matching this host's `mariadb-primary`
  setting; both persistence builds still need the full gameplay journey. This
  is the existing one-fixture gate, not a broad backend/capacity matrix.
- Cloud readiness rechecked read-only: shared usage still 0/1,000,000 analytics
  events, no existing Duris insights, one starter dashboard, empty governed
  metric catalog. Standard query/report tools work; taxonomy/template tools
  lack scopes. Use verified SQL inspection and plain saved tables. No cloud
  captures or dashboard writes have occurred.
- Constant-only HogQL checks confirmed that ordinary numeric result rendering
  can round integers above 2^53. Exact report aggregation can use
  `accurateCastOrNull(value, 'Decimal(38, 0)')` and return `toString(...)`;
  unsigned 9223372036854775809 and signed -9223372036854775808 round-trip exactly.
  This is representation proof, not event ingestion/report reconciliation.

Next: paired performance and the complete emitted volume mix;
publish/query the five views with one <=100-attempt
synthetic cloud fixture; update the operational docs and publish this chunk.
The five closure criteria above remain outstanding where not proven. Production
activation is separate. The user's PR 252–255 question was only a question:
**do not undertake their merges or conflict resolution**; none was performed.

- PR #262 is ready for review. Its base #261 moved to `f1aa582e1` during
  acceptance work, including reviewed quota/reducer repairs and unrelated
  upstream gameplay updates. Aligning with that base using a normal merge;
  preserve all upstream files except this chunk's five explicit paths. The
  existing 35/36-event journey results belong to `8d996b1fa`; rerun affected
  proof on the aligned tree. The diagnostic benchmark was stopped before its
  first valid pair. No performance pass is claimed.

- Base-alignment follow-up: #261 advanced again to `458b834ce`; its eight-line
  quota recovery change and matching docs/tests are retained. This alignment
  is prepared in `bin/issue59/base-alignment` to keep the active full builds
  undisturbed. Use normal forward merges/pushes; no force push or history
  rewrite. The current aligned adapter regression under ASan/UBSan passes;
  full builds and requalification are still in progress.

Current continuation (owner resumed): freeze revision `2be333750`; do not chase
moving PR bases. Both aligned full builds and 57 reducer / 29 HTTPS component
cases per backend pass. Latest real-game requalification failed captured group
attribution and pre-exec delivery assertions; the native deadline test also
failed intermittently before witnessing an active request. Investigating these
existing failures only. The fixture now uses the native 60-second interval
instead of an accelerated one-second cadence against its 64-segment/minute cap,
waits for failed-exec sender recovery before successful replacement, and witnesses
the held HTTP request before testing cancellation. Assertions remain intact.
Reports are five SQL drafts under `docs/telemetry/posthog/`; cloud capture and
performance proof remain uncompleted. No production activation.

- Native runtime requalification now passes all 18 HTTPS cases under UBSan:
  `runtime-tight-posthog.log`. The cancellation fixture waits for an independently
  witnessed active request before starting its bounded flush; no assertion was
  removed. Production code is unchanged.
- The slower native capture cadence restores captured group_size=2 in both
  gameplay captures. The original missing-directory fault stopped before telemetry
  flush, so it could not prove failed-exec recovery. The runner now promotes a
  synthetic invalid executable (ENOEXEC), restores its staged binary and removes
  only its disposable handoff image before the subsequent successful exec.
  Full journeys are rerunning; do not claim a pass yet.
- Created dashboard 2240639 and five saved insights 13125342–13125346. All five
  committed SQL definitions execute against project 678214; production views are
  empty as expected. Billing remains free, reported analytics usage 0/1,000,000.
  Cloud ingestion/reconciliation is still pending. Report links and operation
  steps are in REPORTS.md and CONFIG_CONTEXT.md. No extra report/UI scope.

- Deadline fixture repair is committed/pushed to acceptance PR #262 as
  `32b4772f8`; 18/18 native runtime HTTPS cases pass. Full MariaDB gameplay now
  passes with 37 events / 43 charged attempts (`gameplay-tight-mariadb.log`).
  The flat-file fixture reached a real ENOEXEC but interrupted its paced HTTP
  recovery with copyover's lossy deadline. It now waits for the recovered logical
  exit before copyover; requalification is running. No production-code change.
- The five saved report definitions and minimum operation handoff are ready for
  review on the dependent reports branch. They execute successfully; actual
  synthetic cloud reconciliation and the paired performance gate remain pending.
  No repeated base synchronization, new environment, or extra report framework.

- Flat-file real gameplay also passes: 38 events / 44 charged attempts, exact
  time/XP conservation, captured group/level dimensions, positive separate pet
  contributions, 503 save/recovery, stable identity through reconnect and actual
  failed/successful exec. Evidence `gameplay-tight-flatfile.log`.
- Reports are published for review in PR #263, stacked on #262. The bounded
  MariaDB cloud campaign has started after mock journey proof; its persistent
  campaign marker and ledger prevent reruns/resetting the 100-attempt allowance.
- The serial native reducer mix emits exactly 97 rows across all six families;
  actual shape counts reconcile all four volume profiles, including 396,454 at
  the selected 30-minute window. These are workload-frequency projections,
  not 200-player capacity certification. Evidence `release-mix-volume.log`.
- The release benchmark is declared before collection: three alternating off/on
  runs, 120 saves each; the 5% regression comparison pools all three matched raw
  sample sets. Individual runs and host bounds remain recorded. No valid pair
  has been collected yet. Cloud compilation/journeys finish before the benchmark.

- Cloud campaign completed: 41 real attempts / 40 unique event IDs, within 48
  native reservations, environment 1002 / season 1 / `issue59-cloud-smoke`.
  All four report totals and all health fields reconcile exactly to submitted
  native rows. Activity 2 characters / 3 entries / 1 return; connected time
  49,402,710 usec; applied XP 164 / one zero-applied attempt / 9 level changes;
  separate pet damage 13. One intentionally omitted participant makes the cloud
  completeness flag false despite native completeness. All five queries conserve
  results with every SQL input doubled; all five production scopes exclude tests.
  Evidence: `cloud-smoke/{submitted,expected,query-evidence}.json` under acceptance
  artifacts. Saved dashboard readback confirms all five saved tiles/definitions.
- Only retained performance proof and final review/publication remain. Benchmark
  process is live (`gameplay-release-performance.log`), three alternating off/on
  pairs, 120 saves each. Keep compile/load jobs out of this measurement. Do not
  add another campaign, matrix, qualification phase or forecast tuning task.
