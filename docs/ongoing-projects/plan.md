# Issue #59: fastest useful PostHog delivery

Status: **replanned on 2026-10-21 UTC; implementation incomplete; production disabled.**
Tracking: [Duris #59](https://github.com/LuminariMUD/Duris/issues/59).
Working branch: `issue-59-posthog-http`, based on
`a941a394fa85a917e81c4e8477f206fec9f9dcde`, with the worker HTTPS sender ready for review.
The earlier issue-107 plan remains in [plan-issue-107.md](plan-issue-107.md).
The intervening Assassin plan is preserved byte-for-byte in
[plan-issue-187.md](plan-issue-187.md).

The owner has authorized a smaller first delivery that retains at least 75% of
value and has removed the container/network-isolation requirement completely.
Disposable native tests are the accepted environment. This plan supersedes the
previous implementation sequence and its extra completion gates. Issue #59
closes when this reduced delivery meets the completion criteria below. Deferred
work is outside #59's closure requirements and remains optional follow-up.
Implementation is active. The worker HTTPS component is validated; runtime
integration is next. Production export remains disabled.

## Delivery target and estimate

**Deliver useful, query-verified gameplay analytics in 5–8 further focused agent
hours; use about 6 hours for scheduling.** This includes implementation, local
validation, a bounded cloud smoke test, reports and the operational handoff.
A material lifecycle defect or a failed performance comparison could extend it
to roughly 8–10 hours; that is a contingency, not a guaranteed upper bound.
Production deployment scheduling and reviewer availability are separate.

| Remaining work | Focused time | Concrete exit |
| --- | --- | --- |
| Runtime/transport, copyover, quota and local health integration | 2–3 h | Existing worker sends reduced events in both builds; lifecycle and storage failures preserve gameplay and report loss. |
| Native gameplay journeys and focused cost/volume evidence | 1.5–2.5 h | Both backends exercise the real capture path; measured fixture meets the retained performance and volume gates. |
| Four report views, health query and cloud smoke | 0.75–1.5 h | Synthetic totals reconcile in PostHog, including duplicate IDs and incomplete evidence. |
| Necessary docs, final diff review and handoff | 0.5–1 h | Reproducible queries, exact test commands and enable/disable/recovery steps are recorded. |

The row totals are 4.75–8 hours, rounded to 5–8. The prior 16–24 hour estimate
included SQL boot-schema decoupling and broader qualification. The sender's
known fixture failure and native database uncertainty have now been resolved by
checks recorded below. Reuse those results unless subsequent changes affect them.
There is no Docker setup, additional machine, new database installation, fixed
soak period or CI wait on this delivery path. Required code review still applies.

### What “at least 75%” means here

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
worker and sanitizer regressions passed; integrated PostHog reduction passes 55
scenarios in each backend after carrying the earlier reducer fixes forward.

## Current state and quick checks

The implemented pieces are on the existing stack. Preserve the current worktree;
do not restart these components or reimplement their contracts.

| Piece | Existing evidence / location |
| --- | --- |
| Setup and percentile correction | PRs [252](https://github.com/LuminariMUD/Duris/pull/252), [253](https://github.com/LuminariMUD/Duris/pull/253); integer per-mille p99/p99.9 regressions already implemented. |
| Opaque identities, UTC/UUID/integer encodings and volume fixture | [PR 254](https://github.com/LuminariMUD/Duris/pull/254), `telemetry_posthog.*`, `fixtures/telemetry/posthog/{encodings,volume}.json`. |
| Character, encounter/combat and health reduction | PRs [255](https://github.com/LuminariMUD/Duris/pull/255), [257](https://github.com/LuminariMUD/Duris/pull/257), [258](https://github.com/LuminariMUD/Duris/pull/258). |
| Durable quota and native state tool | [PR 259](https://github.com/LuminariMUD/Duris/pull/259); existing outage-journal regressions include reservation, restart, corruption and publication failure. |
| Worker HTTPS sender | Current branch, ready for review; component suite and both full builds pass. Runtime remains unconnected. |

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
  **434,398 submissions/31 days**, versus **744,021** at 15 minutes. This selects
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

### 1. Connect the existing worker and finish lifecycle behavior

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
`BIN_ROOT` paths above. Add the adapted two-backend gameplay journey, paired
performance comparison and bounded cloud/query assertions. Record their actual
CLIs after adaptation; the current SQL-only runner is not yet a PostHog command.
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

- Sender chunk: worker-only TLS batching, immutable retries, durable pre-send
  quota, cancellation and cached sender health are implemented and reviewed
  locally. Reused the passing component/full-build evidence above; formatting
  and whitespace checks passed again before committing.
- Next chunk: replace the runtime SQL sink with the reducer/sender, preserve
  admission fences and logical copyover identity, then prove runtime failures.
  No production process, schema, credentials or player data was changed.
