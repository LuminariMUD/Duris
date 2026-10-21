# Telemetry performance and degradation gates

## Current PostHog release fixture (#59)

Run `nice -n 10 python3 tests/async/run_telemetry_player_journey.py --backend mariadb --performance`
after the task-specific native build. This uses a disposable socket-only database,
synthetic world and loopback HTTPS; it never sources the host environment. The
release fixture is one client, three alternating off/on pairs, 40 ordinary saves
per run after warmup. Each matched pair must meet the <=5% pulse and save p99
regression limits independently; pooled samples are descriptive only. It is not
200-player capacity certification.

Raw pulse/event/command and process-fsync samples, save/command p99, CPU/RSS,
persistence backlog and sender health are recorded under `bin/issue59/acceptance/`.
Required limits are <=5% pulse and save p99 regression, pulse p99 <=250ms,
event callback p99 <=25ms and critical oldest age <=1,000ms. The maximum whole
event pass bounds every callback inside it; failure of that bound leaves the
callback claim unresolved. Fsync samples include other game-thread and worker
persistence calls and are an upper bound, not isolated journal cost. No production
instrumentation is added. Normal capture/budget loss and sustained backlog must
be absent. Production external I/O stays in the worker.

### Matched-pair qualification — 2026-10-21 UTC

**PASS**, native source `3277e8bd1`, corrected runner/checker in this PR, development
build and one synthetic client. All three pairs independently meet both 5% limits:

| Pair | Pulse p99 off/on, usec | Change | Save p99 off/on, usec | Change |
| --- | --- | --- | --- | --- |
| 0 | 1,704 / 897 | -47.359% | 1,761,459 / 1,761,080 | -0.022% |
| 1 | 695 / 560 | -19.424% | 1,763,700 / 1,765,665 | +0.111% |
| 2 | 788 / 638 | -19.036% | 1,764,019 / 1,761,401 | -0.148% |

There are 1,026 off / 1,032 on pulse samples and 120 saves per condition. Maximum
enabled whole event pass is 905 usec, bounding callback p99 below 25ms. All twelve
sampled critical oldest ages are 0ms. The six retained enabled telemetry snapshots
show zero capture drops, reduction refusals, ambiguity, suppression, expiry and
quota errors. Off/on game-process CPU is 0.248% / 0.344% of one core; maximum RSS
is 35,464 / 43,392 KiB. Pooling is descriptive only and does not decide acceptance.
Maximum enabled pulse is 3,368 usec. Process-wide fsync has 3 off / 84 on samples,
with maxima 3,210 / 6,605 usec; these bound process persistence cost rather than
isolating journal-only latency.

Host snapshot after collection: 16 CPUs, load averages 6.54/7.71/6.90 and 43.7 GiB
available memory. Host load varied; the negative pair differences do not establish
a general speed improvement or concurrent-player capacity.

The command above exited 0. Raw six-run samples, snapshots and summary are under
`bin/issue59/acceptance/mariadb-*performance*`, `mariadb-latency-*` and
`mariadb-persistence-*`; the run log is `/tmp/duris-pr263-matched-performance.log`.
`python3 tests/async/test_telemetry_performance_pairs.py` rejects the historical
false-pass values below and independently rejects pulse or save regression in
each pair. PostHog and production were untouched.

### Historical pooled result — 2026-10-21 UTC

**Not a matched-pair qualification**, native source `18b163a20`, runner at `d558e4bdc`, both native
builds current. The fixture uses the existing development build profile and
minimal synthetic world. It measures one client, not concurrent player capacity.

| Pooled metric | Telemetry off | Telemetry on | Result |
| --- | ---: | ---: | --- |
| Pulse p99 | 630 usec / 1,028 samples | 592 usec / 1,032 samples | -6.03%; descriptive pooled change |
| Save p99 | 1,759,044 usec / 120 saves | 1,758,746 usec / 120 saves | -0.017%; descriptive pooled change |
| Client command p99 | 251,356 usec | 251,420 usec | Recorded; no separate regression gate |
| Game-process CPU | 0.72 seconds / 245.71 seconds | 0.97 seconds / 247.19 seconds | 0.293% / 0.392% of one CPU |
| Maximum RSS | 40,108 KiB | 49,036 KiB | About 8.7 MiB additional |
| Maximum whole event pass | 217 usec | 188 usec | Every callback bounded below 25ms |
| Sampled critical oldest age | 0ms | 0ms | All six snapshots per condition below 1,000ms |
| Process-wide fsync p99/max | 1,959 usec / 3 calls | 2,645 usec / 84 calls | Upper bound including non-journal calls |

Individual pulse p99 values (off/on, usec) were 615/725, 504/540 and 631/592.
Pairs 0 and 1 regress by 17.9% and 7.1%, so this collection does not pass the
required <=5% matched-pair gate despite its pooled improvement. The runner now
rejects either pulse or save regression in any pair; a focused regression uses
these archived pair values to prove pooling cannot mask a failure. Maximum enabled
pulse was 1,483 usec, far below the 250ms p99 limit. Enabled health snapshots
showed zero capture drops, reduction refusal, ambiguity, suppression, expiry or
quota errors; queues/output drained. Each enabled run's final workload snapshot
showed three acknowledged events and zero retained output bytes. No event-budget
debt window was observed during collection; the maximum event pass also stays
below the configured 25ms event budget. Telemetry HTTP/fsync remain in the worker.

The real journeys separately retained 38 MariaDB / 36 flat-file events, totaling
72,985 / 68,889 compact JSON event bytes, largest event 4,964 / 4,965 bytes.
These are delivered event-body sizes, excluding failed attempts and HTTP/envelope
overhead; they are not a measured performance-run wire-throughput figure.

Host snapshot during collection: eight CPUs, load average 2.13, 86–91% idle,
6.3 GiB memory available and 46% disk usage. Swap was almost full but swapping
was negligible and observed I/O wait was zero. Production settings were untouched.

Reproduce with the command above. Evidence is in
`bin/issue59/fast-plan/slot-scan-performance.log` (exit 0),
`acceptance/mariadb-performance{,-summary}.json`, all six raw
`mariadb-latency-<pair>-<enabled>.txt` and persistence snapshots, and
`mariadb-event-budget-windows.txt` (no observed debt windows).

The first comparison failed: pulse p99 557 usec off / 654 on (+17.4%); save p99 passed.
It remains preserved under `acceptance/performance-before-slot-scan-fix/`.
Repair `18b163a20` stops scans after existing resident counts are exhausted,
retaining sparse high-index residents and all 256 slots. State/runtime tests,
both native builds and both real gameplay journeys pass after that repair.
The pooled-only acceptance check was insufficient and has been corrected; the
5% requirement and absolute operating bounds are retained. No cloud campaign was repeated.

### Emitted volume and limits

A serial native reducer mix emits 97 rows:
48 periodic + 2 boundary summaries, 10 lifecycle rows (6 entry/exit, 2 reconnect,
2 copyover attachments), 1 level change, 6 encounter rows (run, 4 PCs, 1 pet),
2 configurations and 28 health rows. These measured shapes reconcile the declared
31-day forecast to 396,454 attempts at the selected 30-minute window, including
2% retries and the entire 100-attempt cloud allowance. Workload/retry frequencies
remain assumptions; neither this projection nor the hard quota proves concurrent
player capacity. A 32-date billing span is bounded at 640,000 shared attempts,
below 700,000, provided the documented shared allocation is respected. Keep all
current release criteria; the broader historical capacity profiles below are
optional follow-up, not issue #59 closure conditions.

## Historical offline gate (#272)


This gate is a local, offline evidence package for the telemetry transport and
the pure rollup/report stages. It proves bounded behavior under matched
synthetic workloads and injected repository faults. It is not a production
load qualification, a SQL benchmark, or a claim that telemetry has been
enabled on a live server.

The gate deliberately does not:

- connect to MySQL/MariaDB or read credentials;
- start the game server or generate player/gameplay traffic;
- apply a migration, publish a rollup generation, or change runtime
  activation/balance policy.

## Reproducible workload

The frozen profiles are 50, 200, and 1,000 synthetic telemetry interval facts.
Each profile uses the same value-only record shape, producer identity, monotonic
ordering, and dimensions across all stages. The default runner takes five
repetitions; focused tests use three repetitions to shorten the local test
cycle. The workload is generated in memory and contains no player, account,
credential, or production row.

The queue benchmark uses a 128-record worker batch and flushes between batches,
so the normal profile never relies on an unbounded queue. The capacity fault
case separately uses a 16-record queue with a four-record control reserve to
force both detail and control admission rejection.

## Measured stages

`tests/async/telemetry_capacity_272_harness.cc` runs the C++ stages against an
injected fixed repository and clock:

| Stage | What is measured | What is intentionally absent |
| --- | --- | --- |
| `off` | matched record construction baseline | telemetry validation and queue admission |
| `capture_only` | record validation and value-only capture work | repository and queue writes |
| `capture_write` | actual bounded enqueue plus synchronous in-memory worker batches | SQL/network/disk latency |

`scripts/telemetry/benchmark_272.py` measures the existing pure Python
`build_page_contributions` rollup path and the existing administrator report
service over synthetic in-memory rows. These stages exercise the real bounded
semantics and response shaping without opening a database.

Every C++ stage reports p50, p95, p99, and p99.9 sample latency, wall time,
CPU time, admitted/dropped records, repository calls, and checksum. The
capture/write stage also reports worker-batch latency, queue high-water, and
the fixed queue storage footprint plus `producer_allocation_bytes: 0`. The
Python stages report the same latency percentiles, CPU time,
`allocation_bytes`/`memory_bytes` from peak `tracemalloc`, and an explicit
`database_calls: 0` marker.

The source contract checked by the runner verifies that the producer/transport
sources contain no heap allocation, SQL connector, file-open, or blocking
thread primitive. The queue is checked for its atomic SPSC head/tail storage.
The reported queue footprint is the fixed compile-time queue storage, not an
estimate of production RSS.

## Local guard budgets

These are reproducibility guards for this disposable harness, not public
service-level objectives. A slower host should produce a visible gate failure
that is reviewed with the report rather than silently being treated as a
production result.

| Metric | Guard |
| --- | ---: |
| normal `capture_write` p99 | ≤ 1 ms |
| normal `capture_write` p99.9 | ≤ 5 ms |
| normal in-memory worker p99.9 | ≤ 50 ms |
| pure rollup p99.9 | ≤ 5 s |
| pure report p99.9 | ≤ 5 s |
| slow-write producer admission maximum | ≤ 100 ms |
| stop request while a write callback is blocked | ≤ 100 ms |
| normal capture/write drops | 0 |
| normal queue high-water | ≤ 128 records |

The gate is a pass only when the structural checks and these local guards pass
for all three workload sizes. A passing result means “bounded under the
documented synthetic fixture on this host”; it does not authorize production
activation or claim a live-database latency budget.

## Fault and teardown matrix

`tests/async/telemetry_fault_272_harness.cc` uses the same transport seam as
the existing telemetry tests and emits one sanitized JSON object per case.

| Case | Injected condition | Evidence required |
| --- | --- | --- |
| `queue_saturation` | 16-slot queue, four-slot control reserve | explicit detail/control rejection and queue peak exactly 16 |
| `repository_recovery` | first three repository initialization attempts unavailable | retained records catch up after reconnect; no pending tail |
| `ambiguous_commit` | first apply returns lost-COMMIT ambiguity | immutable retry is accepted as three duplicate-identical records |
| `slow_write` | worker callback held while the producer continues | producer admissions and stop request remain bounded; drain completes |
| `copyover_shutdown` | quiesce, reject admission, resume, drain, stop | quiesce rejects exactly the paused record and teardown leaves no tail |
| `churn` | 20 init/drain/shutdown cycles | no retained queue state or cross-cycle identity leakage |

The slow-write case intentionally models the repository callback as a local
blocking fixture. The transport contract says a connector that violates its
worker cancellation contract cannot be preempted by a caller deadline; the
test therefore measures the nonblocking producer/stop requests and releases
the callback before the off-game-thread drain/reap step.

## Commands

From the repository root:

```text
python scripts/telemetry/benchmark_272.py \
  --workloads 50 200 1000 \
  --repetitions 5 \
  --output bin/tests/telemetry_capacity_272.report.json

python tests/async/test_telemetry_capacity_272.py
python tests/async/test_telemetry_fault_272.py
```

The runner uses `CXX` when supplied, then native `g++`, and finally a local
`wsl.exe`/`g++` fallback on Windows. Compiled binaries and JSON reports stay
under `bin/tests/` and are disposable evidence; they are not source or schema
artifacts.

## Review checklist

A reviewer should confirm all of the following from the generated report and
the harness source:

1. The three workload sizes are present and use the same stage definitions.
2. p50/p95/p99/p99.9, CPU, allocation, queue, and repository/DB fields are
   present; `database_calls` remains zero for the pure Python stages.
3. Normal capture/write has no drops and stays within the 128-record batch
   high-water guard.
4. Every fault case has the expected bounded outcome, including explicit loss
   on saturation and duplicate reconciliation after ambiguity.
5. Stop/quiesce/teardown evidence is captured after callbacks are released and
   no test performs a production migration, load, activation, or CI action.

A run's record is the sanitized JSON report with the compiler and Python versions
and the host's limitations. Live database qualification is not part of this gate.
