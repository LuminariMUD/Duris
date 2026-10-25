# October 24: lag after today's deployment

## Implementation handoff, October 25

Issue: [#365](https://github.com/LuminariMUD/Duris/issues/365). Work continues on
`investigate/365-server-lag` in `/home/aiwithapex/projects/duris-issue365`.
The branch was fast-forwarded to `master` baseline `f31283e56` before editing;
the original October 24 observations below remain historical evidence, not
measurements of the new implementation. General lag attribution is still open.

### Chunk 1: publish ready critical results every pulse

The coordinator poll and existing game-thread completion handlers now run each
250 ms pulse, still after `ne_events()` and before player-save capture. Even-pulse
GMCP/ship/locker work still precedes them; outbox publication, saves, load/recovery,
Divine selection and caches keep their 500 ms cadence. The routing function's
bounded locker-identify completion polling also runs each pulse. No new worker,
configuration, database query, event budget or socket flush was added.

Keeping the existing output phase means completion receipts still wait until
the next pulse to drain. The change deliberately removes the extra alternating
publication pulse without moving effects across the event scheduling boundary
or changing the one-playing-command-per-pulse admission policy.

`test_critical_publication_cadence.py` executes the extracted production recurring
phase with the real coordinator and shared writer, using an immediate synthetic
backend and a virtual pulse clock. It checks both submission parities,
success/replay/terminal failure, fence release, exactly-once routing, and the
other recurring owners' cadence/order. For a result ready just after pulse zero,
baseline `f31283e56` publishes at 499 ms and drains simulated output at 749 ms;
the new phase publishes at 249 ms and drains at 499 ms. Just after an odd pulse,
both versions publish at 249 ms and drain at 499 ms. These are controlled
phase waits, **not live cargo socket or database timings**. The new regression
fails against the old phase's missing odd-pulse routing.

Passed: `make -C src -j4` (MariaDB development),
`make -C src -j4 PERSISTENCE_BACKEND=flatfile DMS_BINARY=.../bin/server/dms_flatfile`,
`python3 tests/async/test_critical_publication_cadence.py`,
`test_critical_command_coordinator.py`, `test_critical_completion_capacity.py`,
`test_divine_trade_runtime.py`, `test_divine_trade_outbox_versions.py`,
`test_game_loop_phase_contract.py`, `test_command_latency_runtime.py`,
`test_locker_identify.py`, `test_item_movement_prompt_runtime.py`,
`bash tests/async/run_divine_trade_mysql.sh`, and `./scripts/format.sh --check`.
Python test paths here are under `tests/async/`. The database test uses its own
disposable MariaDB, checks receipts, ten rollback boundaries and atomic ordinary
loss/deletion saves, and rechecks the migration without resetting trade state.
The trade runtime test covers held payment/save reservations, rejection, retry,
relog and ordinary losses. The phase source test had a stale direct-auction
call expectation; it now checks the existing outbox routing wrapper.

### Remaining work and resumption boundaries

- Finish chunk 1 validation and publish its focused review PR; record the PR,
  commit/tag and final test evidence here. The change is not deployed.
- General reported slowdown: obtain a representative slow action and UTC time
  or trace a recurrence. Staff and mortal reports are equally useful on shared
  paths. Do not declare the reports resolved from this cadence improvement.
- Historical 47.759 ms callback: its identity remains unrecoverable. Capture a
  new slow callback with concrete vnum/procedure and CPU/off-CPU/syscall timing.
- First-command polling/type-ahead: evaluate separately; preserve simulation
  cadence and intentional action-rate gates. No input-throughput change yet.
- Cargo: measure representative purchase/sale submit, commit, publication,
  receipt, blocked-command and save timing. The writer/phase driver isolates
  publication only; prompt output still has its separate next-pulse wait.
- Eligible-mortal activity: measure representative inventory/list position
  before changing identity lookup. Current `master` changed Divine eligibility
  and selection since the original fixture; inspect the owning source again.
- Divine selection: evaluate repeated object traversal within current selection
  and status passes, separating hourly work from recurring eligibility checks.
- Outbox: correlate audit duration with delivery of newly arriving work.
- Network/GMCP: extend to the reported client/gameplay path (movement, combat,
  ships and state updates); read-only negotiation comparisons are insufficient.
- Telemetry: extend hook comparisons only if a matching incident identifies an
  unmeasured hook. Existing healthy queues do not prove hook execution cost.

The local primary checkout is `ENVIRONMENT=local`; its separate worktree has no
`.env`. A read-only remote check found `/home/staging/duris` marked production
and a different live game PID, **2235802**, started October 25 at 10:01:53 in the
remote host's timezone. The old PID/ELF offsets below must not be reused. No
production operation, tracing configuration, migration or restart was performed.
The old ignored evidence was not found under that remote checkout; locate its
actual owning checkout before relying on retained drivers. Keep new test/build
artifacts ignored under this worktree's `bin/tests/`.

## October 24 observation record

Scope of the observations below: **October 24, 2026 only**, from the production reboot at 10:37 UTC.
Initial live observations were collected around 12:43–12:56 UTC; follow-up
observations were collected from 18:06 UTC and resumed at 18:21 UTC. A sudo
follow-up ran from 20:38 UTC. All times below are UTC.

**Status after the privileged follow-up: access-blocked tests completed;
general lag attribution remains unproven.** Production remains running with its
original PID and executable. The follow-ups from 20:38 through 20:54 successfully sampled CPU,
read live queue/gate metadata and traced command waits and concrete object
procedures. It confirmed type-ahead serialization, but did not reproduce the
earlier slow callback or identify the cause of the general complaints. Staff
reports are fully valid for investigating shared input, scheduling, execution,
output and network paths. Mortal eligibility matters only to the specific
Divine activity observer comparison.

**Measured waits include 250 ms input serialization, hundreds of milliseconds
waiting for completion publication, and intermittent event deferral.** Controlled
comparisons now quantify Divine activity, selection and telemetry costs. They
do not establish a cause for the general player complaints or a provider fault.
The reported slowdown is not declared resolved.

## Actual delays recorded today

The current boot's `logs/log/status` records these scheduler observations:

| Log time | Deferring pulses in that window | Deferred work count | Worst recorded lateness | Callback named for worst lateness |
| --- | ---: | ---: | ---: | --- |
| 10:39:11 | 15 | 72,386 | 2 pulses, approximately 500 ms | `event_mob_mundane` |
| 10:40:26 | 2 | 1,554 | 1 pulse, approximately 250 ms | `event_balance_affects` |
| 11:09:13 | 1 | 270 | 1 pulse, approximately 250 ms | `event_memorize` |
| 17:59:42 | 1 | 455 | 1 pulse, approximately 250 ms | `event_object_proc` |

These are window aggregates, timestamped when the window was logged. Deferred
work counts can include repeated deferrals of the same event; they are not
counts of distinct players or distinct delayed actions. The largest window
occurred immediately after today's reboot. The `event_memorize` observation
also shows that lateness was not confined to startup.

At **17:59:09**, the scheduler recorded a **55.808 ms** event pass, including
**47.759 ms** in one `event_object_proc` callback. Its scheduled-event count was
67,858. The following window recorded the 455 deferrals shown above.

The scheduler normally has a **25 ms event-pass budget**. A callback that exceeds
that budget cannot be interrupted midway; remaining work can be deferred to a
later 250 ms pulse. Consequently, a tick can finish comfortably under 250 ms
while some events still run a pulse late. That distinction matters for this
investigation.

The slow-object log identifies the wrapper callback, but not its object vnum or
the specific object procedure it invoked. The duration is wall time, so it does
not distinguish expensive computation, a blocking operation, or descheduling.
It is insufficient to attribute the callback to a particular new system.

Sources: [event scheduler](../../src/world/new_events.c),
`ne_events()` and `nevent_budget_window_record()`;
[object callback](../../src/world/db.c), `event_object_proc()`.

## Today's running deployment and workload

Production PID **4044784** booted at **10:37:55** and remained running during the
follow-up. The build stamp is `mariadb/production`; the executable matches
`bin/server/dms`, SHA-256:

```text
ad1b2626169b2c544113ca569ba6a5dc349bd1ea9c3b8f4e26c711c6c994bcf0
```

Source inspected: `4b4fec518`. Runtime measurements identify the running process;
the source revision identifies the checkout reviewed.

| System | Today's observed state | What this establishes |
| --- | --- | --- |
| Divine Boons | At 18:09: active, unpaused, revision 13; one cargo objective running from 15:00 to 19:00. | The system is active. EXP/epic target load was not exercised by that snapshot. |
| Prepared cargo settlement | Two cargo commands in the preceding hour; one nonempty account book plus the global-generation row. | There is some real trade traffic, but little evidence for capacity under heavy trading. |
| Critical delivery | Preceding hour: 53 outbox records, mean creation-to-delivery 144.56 ms, maximum 244.48 ms; none pending or dead-lettered, zero attempts/retries. | No delayed critical delivery was captured in that hour's aggregate. |
| Telemetry | At about 18:08: PostHog enabled, queue/output empty, 530 HTTP-acknowledged events; zero capture drops, retries, reduction refusals or storage failures. | No telemetry backlog was observed. This does not isolate its game-thread overhead. |

## Current host and persistence observations

Five fresh observations over **18:08:19–18:10:19**, 30 seconds apart, measured:

| Measurement | Result |
| --- | --- |
| Game CPU | Mean 3.63% of one core; intervals 3.23–4.70% |
| Database CPU | Mean 3.06% of one core; intervals 0.70–5.43% |
| Host CPU | 92.35% idle, 0.014% I/O wait, zero recorded steal |
| Pending / dead-letter / incomplete critical work | Zero at all five observations |
| New InnoDB physical buffer-pool reads | Zero |
| New row-lock waits, lock-wait time, or slow queries | Zero |

The authenticated staff readback at approximately 18:08 showed:

- Save writer empty: all 5,181 submitted jobs applied, no write failures or
  timeouts, maximum capture-to-apply about 110 ms; dirty/deferred queues empty.
- Critical command queue empty, with no blocked/fenced work, overloads or
  terminal failures. Instrumented game-loop SQL count was zero.
- Event wheel/counter/pool all agreed at 67,494, with zero integrity errors.
  All ten enabled periodic jobs were armed; no missed runs or failures.
- The outbox health snapshot was labelled **stale** at that instant: counts
  age 1.222 seconds and audit age 61.298 seconds, with zero database failures.
  Independent read-only observations found no pending work. The stale label
  must not be presented as fresh health evidence.

Today's completed trace windows through **18:07:13** contain **107,700 ticks**:
mean recorded tick work **7.240 ms**, maximum **56.189 ms**. No >=250 ms whole-tick
overrun was found in today's status log at inspection. These summaries do not
erase the separately recorded event lateness above, measure command queue wait,
or fully account for sleep/wakeup delays between ticks.

The measurements do not show sustained CPU, database or save-queue saturation
during collection. They do not explain every reported delay.

## Today's network and response measurements

Fresh 60-packet probes from the server:

| Destination | Packet loss | RTT min / mean / max |
| --- | ---: | ---: |
| `1.1.1.1` | 0% | 1.105 / 1.192 / 1.427 ms |
| `8.8.8.8` | 0% | 12.627 / 12.715 / 13.243 ms |

A subsequent 61-sample observation of the three established remote game TCP
connections found:

| Anonymized connection | RTT min / mean / max | New retransmissions during observation | Maximum sampled send queue |
| --- | ---: | ---: | ---: |
| A | 106.52 / 109.33 / 112.13 ms | 0 | 25 bytes |
| B | 75.76 / 85.85 / 98.07 ms | 0 | 324 bytes |
| C | 214.96 / 225.13 / 261.61 ms | 0 | 172 bytes |

Connection C has appreciable latency and variation. Without an earlier baseline
or client-side timing, this does not identify a new provider fault. Outbound
probes to two destinations also cannot exclude an intermittent or route-specific
problem on the players' paths.

Twenty-four sequential authenticated `time` commands from the server took
**49.465–249.546 ms**, median **199.606 ms**, to identifying response text.
The existing loop polls input once per 250 ms pulse, and its final sleep is not
woken by incoming socket data. This accounts for ordinary input wait even with
little CPU work. It does not establish a newly introduced regression. The test
character is staff, so this test does not exercise mortal-only activity tracking
or every gameplay command gate.

Source: [game loop](../../src/net/comm.c), `run_connection_phase()`,
`run_session_input_phase()` and pulse-reset sleep.

## New-system costs and specific next steps

### Measured input backlog, 18:24:02–18:24:24

An authenticated test-account session sent batches of `time` commands in one
socket write. This is a direct response measurement against today's running
process, not an inference from idle CPU or a healthy persistence queue.

| Commands in one write | First identifying response | Last identifying response |
| --- | ---: | ---: |
| 2 | 100.052 ms | 350.374 ms |
| 4 | 200.045 ms | 951.128 ms |
| 8 | 200.168 ms | 1,951.652 ms |
| 8, repeated | 200.183 ms | 1,951.896 ms |

Within each burst the server returned one response approximately every 250 ms.
Forty separate commands in the same session took 9.678–200.059 ms, median
99.954 ms. The delay before the first command varies with arrival phase; each
additional queued command adds a pulse. The source agrees: the session sweep
dequeues one command per descriptor per pulse, and the final `select(0, ...)`
sleep cannot wake for socket input. Thus a burst can feel seconds behind while
individual command execution and persistence are fast. **This explains the
measured burst delay; it does not establish that today's deployment introduced
this rate limit or that players' complaints were caused by type-ahead.** Staff
commands do not exercise mortal-specific gates.

The same live readback counted 57,607 living mobiles, 38,937 existing objects,
253,261 real rooms and 67,577 pending events. These are measured workload sizes
for the subsequent isolated comparisons, not evidence of responsiveness.

### Divine input observation: controlled cost

At 18:24:50–18:24:59 and 18:32:27–18:32:43, an isolated optimized (`-O2`) harness
linked the current `divine_boon_activity.c`, the actual
`find_character_by_runtime_id()` implementation and the actual interpreter item
dependency policy. A synthetic eligible mortal executed begin/end observation
1,000 times per case. The command body was omitted to isolate the new observer;
an observation-disabled empty body provided the timing baseline. The character
list used a fixed randomized order and tested a player at its head and tail.
No player, account or inventory data was copied or changed.

| Fixture | Observation enabled, mean | Interpretation |
| --- | ---: | --- |
| 57,608 characters, player at head, `look`, no items | 0.144 µs | Early identity match is cheap. |
| Same, `get`, 1,000 inventory objects | 28.344 µs | Two inventory fingerprints add measurable but small work. |
| Same population, player at tail, `look`, no items | 2.659 ms | Identity lookup walks the character list even for inventory-independent commands. |
| Same tail, `get`, 1,000 objects | 2.761 ms | Character lookup dominates this fixture. |

For the last case p95 was 5.058 ms and maximum 9.731 ms. Across all enabled
57,608-character cases, the largest wall-time observation was 30.487 ms;
per-case mean thread CPU and wall time were close. An earlier 40,000-character
tail fixture averaged 1.224–1.341 ms. These are synthetic layout measurements,
not live per-player timings or an upper bound on every inventory or cache state.
They demonstrate a new per-command cost with world-size dependence, but do not
reproduce a persistent one-second stall. The live staff probe bypasses this
observer's eligible-mortal path, so it cannot dismiss that cost.

Source: [Divine activity](../../src/economy/divine_boon_activity.c),
`divine_boon_activity_end()`;
[identity lookup](../../src/account/character_identity.c),
`find_character_by_runtime_id()`.

### Telemetry: matched disabled/enabled comparison

At 18:30:10–18:30:12, an isolated harness compared the current PostHog runtime
disabled/enabled/enabled/disabled, with 4 and 64 synthetic sessions. It used the
production optimized telemetry objects; runtime/sender objects were rebuilt at
`-O2` with the existing test-only HTTPS endpoint hook. The native reducer,
transport worker, synthetic quota journal and a local TLS receiver remained
active. Only synthetic credentials were supplied, in a fresh environment;
requests reached the local receiver, never the production analytics project.
The configuration used the default 60-second intervals, 300-second checkpoints
and activity window, and one pulse slot.

Each trial measured 10,000 calls to the real `telemetry_runtime_game_evidence()`
hook and 1,200 pulse calls advancing virtual time by 500 ms. Small sleeps outside
the measurements allowed the worker to run. Initialization and shutdown were
excluded. Timing includes the same measurement overhead in both variants.

| Sessions | Mean enabled-minus-disabled evidence-hook time | Mean enabled-minus-disabled pulse time | Worst enabled pulse |
| --- | ---: | ---: | ---: |
| 4 | 0.327 µs | 1.519 µs | 58.469 µs |
| 64 | 0.459 µs | 3.765 µs | 258.193 µs |

Every trial completed successfully; enabled captures had zero rejected or
dropped records. All enabled workers reported healthy, with queue high-water
16 for four sessions and at most 432 for 64 sessions. This **directly measures
small producer overhead for these workloads**; queue health is supplementary
evidence. The fixture does not measure every progression/encounter hook, remote
HTTP failure mode or a historical stall. It does not support blaming ordinary
telemetry evidence capture for the measured hundreds of milliseconds of input
wait.

### Diagnostic observer effect

The investigation itself issued `world persistence` at 18:08:39 and 18:24:06.
Today's command diagnostics recorded those `world` operations taking 89.417 ms
and 89.648 ms respectively. The command invokes
`divine_boon_selection_status()`, which refreshes world paths and evaluates the
whole candidate catalogue. Those two invocations were not separately profiled; the 20:51 follow-up
below isolates the selector in later live calls. These diagnostic operations must not be represented as
spontaneous player stalls. They show that diagnostic readback can itself occupy
the game thread for a material fraction of a pulse.

### Full-world Divine comparison, 18:45:36–18:45:42

An isolated executable linked today's optimized server objects and read today's
generated world files: 253,261 rooms, 351 zones and 17,680 mobile prototypes.
It initialized gameplay properties from a private copy of `lib/duris.properties`,
loaded the native quest profiles, assigned room/object procedures and built the
real Divine catalogue and paths. Its 85 catalogue entries produced the same
two good-side and eight evil-side experience targets as the live readback.
The executable did not enter the server loop or initialize a database connection;
an unexpected direct socket connection was configured to abort the fixture.
Runtime authority and zone metadata were supplied by isolated in-memory fixtures.

Twenty calls per case measured the selector with no live objects, then with a
randomized list of 38,937 synthetic non-stone objects, matching today's observed
object count. Status output was collected in memory. This isolates traversal
cost without copying player data or claiming to reproduce live object placement,
door changes or every metadata field. Cargo-route eligibility did not match the
live route count; this comparison establishes EXP/epic traversal cost, not a
complete production rotation benchmark.

| Operation | No objects, mean | 38,937 objects, mean | Maximum in populated case |
| --- | ---: | ---: | ---: |
| Recurring check with only cargo active | 0.067 µs | 0.081 µs | 0.851 µs |
| Refresh one active EXP slot, good zone 148 / evil zone 190 | 114.137 µs | 127.991 µs | 212.147 µs |
| Hourly selection, four active accounts per side | 10.575 ms | 46.175 ms | 72.017 ms |
| Staff eligibility status | 21.349 ms | 42.614 ms | 60.901 ms |

The populated-list comparison demonstrates a concrete cost of the new selector:
`epic_target()` scans `object_list` separately for candidate zones. The selector
can spend tens of milliseconds in this workload; ordinary cargo-only pulses do
not repeat that traversal. The EXP refresh case forced a revision change on
every call so that every sample performed validation. Hourly selection is not
run on every pulse. These results therefore do not explain continuous lag while
only cargo is active.

Earlier fixture attempts omitted gameplay configuration and produced an empty
or almost empty catalogue. Their cheap timings were rejected. They are not used
as evidence that production selection is cheap. The final fixture's eligibility
counts were checked before accepting its results.

At 18:45:46–18:45:51, two live `divineboon status` readbacks completed in 117.439
and 118.461 ms from send to identifying text, interleaved with `time` controls.
These include pulse-arrival wait and do not isolate execution time. Neither
crossed the command logger's 50 ms execution threshold. This does not support
attributing all of `world persistence`'s approximately 90 ms to Divine status.

Source: [selection](../../src/economy/divine_boon_selection.c),
`epic_target()`, `divine_boon_select()`, `divine_boon_selection_pulse()` and
`divine_boon_selection_status()`.

### Durable completion waits: database work versus publication

A read-only query at **18:44:38** found these two prepared cargo operations in
today's boot. Both committed successfully, without outbox retries.

| Inbox creation | Inbox committed | Creation-to-committed span | Outbox creation-to-delivery |
| --- | --- | ---: | ---: |
| 17:43:36.728574 | 17:43:36.734337 | 5.763 ms | 203.506 ms |
| 17:49:33.391685 | 17:49:33.396305 | 4.620 ms | 75.494 ms |

The inbox interval is a recorded portion of the database transaction, **not**
submit-to-commit latency: it excludes waiting before the inbox row was inserted,
and `committed_at` is assigned before final transaction acknowledgement. Outbox
delivery is also not the player's receipt timestamp. No pending or dead-letter
outbox rows were found. Today's 29 item-transfer inbox intervals averaged
37.157 ms and reached 52.156 ms; those are transaction spans, not measured player
input waits.

The game only polls coordinator completions every two 250 ms pulses, **after**
the output phase. The cargo completion handler clears its pending state and
queues the receipt at that poll; ordinary output reaches the socket next pulse.
This can add hundreds of milliseconds after fast durable work.

At **18:43:58–18:44:03**, an executable linked the real coordinator and shared
writer with an immediate synthetic backend. It measured worker and completion
timestamps while a small driver reproduced the game's 250 ms phase cadence and
output-before-completion order. A matched comparison changed only completion
polling from 500 ms to 250 ms; production was not changed.

| Submission phase within the driver's second | Worker finished after submit, current-cadence case | Current 500 ms polling: publication / simulated visible output | 250 ms polling control: simulated visible output |
| --- | ---: | ---: | ---: |
| 1 ms, just after an even pulse | 0.067 ms | 499.032 / 749.020 ms | 498.973 ms |
| 251 ms, just after an odd pulse | 0.096 ms | 248.994 / 499.017 ms | 499.022 ms |

All eight phase/comparison cases passed. Backend application took 1–2 µs, and
writer queue time was 34–449 µs. The result demonstrates waiting for publication
despite an idle writer. **The output times are from a phase-order driver, not a
live cargo socket measurement.** They explain the mechanism and its contribution
under the controlled workload; the two actual trades do not establish that
cargo settlement caused general player complaints.

A possible fix is to publish ready completions at a more responsive point in
the existing loop and flush their output promptly. It requires gameplay ordering
and persistence validation: the current phase order is an explicit compatibility
boundary, so simply moving the call is not an established safe fix.

Sources: [game loop](../../src/net/comm.c), `run_output_phase()` and
`run_recurring_persistence_phase()`;
[cargo completion](../../src/economy/divine_trade_runtime.c),
`divine_trade_runtime_completions()`;
[coordinator](../../src/persistence/critical_command_coordinator.c),
`execute()` and `critical_command_coordinator_pulse()`.

### Actual 19:00 rotation

Read-only observations at **19:01:26** and **19:02:32** found revision **14**,
Divine mode active and unpaused, with the 19:00 opportunity consumed. The old
cargo objective had been replaced by cargo objective **3**, starting at 19:00
and expiring at 23:00. The database's table metadata reported an update time of
**19:00:00**. This supplies a new live rotation observation in addition to the
isolated selector comparisons above.

The completed trace window covering **18:58:31.660486–19:00:35.792439** recorded
496 ticks and 248 recurring-persistence passes. Its maximum `gmcp_flush`
duration was **11.909 ms**, maximum command sweep **3.766 ms**, and maximum tick
work **20.031 ms**. The `gmcp_flush` timer surrounds the recurring phase including
Divine publication and selection. Thus the whole recorded phase containing the
reported rotation was bounded by 11.909 ms; that number must not be described as
an isolated selection duration.

The following window, **19:00:35.792439–19:01:50.879412**, recorded 300 ticks:
maximum recurring phase **1.302 ms**, command sweep **1.178 ms**, and tick work
**21.860 ms**. Neither window reported dropped or invalid clock samples. No new
event-deferral, slow-event or whole-tick-overrun entry appeared in the status
log during this check.

This live rotation did not reproduce a long game-thread processing stall.
These bounds still exclude input arrival wait, command gates, completion
publication cadence, sleep/wakeup timing and the player's network path; they
do not establish that players were responsive or attribute the general
complaints.

### Live profiling access

At approximately 18:23, `perf record -e cpu-clock -F 49 -p 4044784` failed before
recording: this host sets `perf_event_paranoid=4` and the investigation user has
no applicable capability. Noninteractive `sudo` is denied. No kernel setting
was changed and no debugger was attached to production. Existing logs identify
the slow object callback only as `event_object_proc`; recovering its concrete
object/procedure identity from that past log entry is not possible. Isolated
executable comparisons remain available, so this restriction alone is not a
reason to stop the investigation.

At **18:59:48**, a fresh sampling attempt was again denied with
`perf_event_paranoid=4`. A separate read-only open of `/proc/4044784/mem` also
returned **EACCES**, and was not followed by a memory read or debugger attach.
The process remained running. This rules out the available unprivileged direct
memory-inspection alternative for observing live input-queue and gate metadata.

### Focused object-callback reproduction

At **18:55:44–18:55:49**, a second isolated executable used the same native world
loader, gameplay properties, initialized skill and character-link tables, native
zone resets and the event scheduler. It populated **53,929 NPCs and 32,227
objects**, then advanced **120 event pulses**. A private copy of
`event_object_proc()` measured the concrete object procedure; only the private
executable contained this instrumentation.

The run completed successfully and measured **2,040 object callbacks**. Its
maximum was **1.144 ms**, `artifact_stone()` on object vnum 23808. No callback
reached the probe's 5 ms reporting threshold. This did **not** reproduce today's
47.759 ms production callback, and does not identify that past callback as
`artifact_stone()`. The fixture had no connected players, player inventories or
production guild/account state and did not reconstruct eight hours of runtime
changes. Its negative result is limited to that workload. An earlier attempt
omitted character-link initialization and emitted warnings; the accepted run
initialized those tables and completed without those warnings.

### Privileged live tracing, 20:38–20:43

The owner supplied sudo access for this follow-up. The previous access barrier
is resolved: CPU sampling, read-only `/proc/4044784/mem` reads and eBPF uprobes
all succeeded without restarting or stopping production. `perf_event_paranoid`
remained **4** and `ptrace_scope` remained **1**; no permission setting was
relaxed. The running ELF has debug information and matches the SHA-256 above.
Field offsets were obtained from that ELF with an offline debugger; no debugger
attached to the live process and no game function was called through a debugger.

Twenty-three temporary probes ran from approximately **20:39:50.547 to
20:42:52.116**. They recorded input queue entry/removal, interpreter duration,
gate metadata, Divine observer eligibility, object vnum/procedure identity and
object callback wall time. Selected-node instruction probes cover the casting
and transaction-filtered dequeue paths as well as ordinary FIFO removal; those
filtered paths were not exercised in the accepted workload. Off-CPU and syscall
hooks were available to distinguish blocking/descheduling if a slow object
callback recurred. No callback reached the 5 ms detailed-reporting threshold.
The observed object syscall records were solely syscall 335 (`uretprobe`),
generated by the tracing mechanism, not evidence of application blocking I/O.
The trace reported no lost events or runtime errors. These are instrumented
wall times and include probe overhead.

#### Live send, enqueue, dequeue and response correlation

An authenticated test-account session issued **16 single `time` commands**, then
bursts of **2, 4, 8 and 8** commands. All **38** responses were matched to live
enqueue/dequeue/interpreter events using the client's and kernel's monotonic
clocks. A further traced command was the session's `quit`.

| Measurement | Privileged live result |
| --- | --- |
| Single-command send-to-response | 49.850–150.247 ms; median 100.087 ms |
| All 38 commands: send-to-enqueue | 49.251–199.643 ms; includes input-poll wait |
| All 38 commands: interpreter execution | 0.123–0.212 ms; median 0.148 ms |
| All 38 commands: dequeue-to-client-response | 0.484–0.701 ms |
| Maximum measured enqueue-to-dequeue wait | 1,752.268 ms, last command of an eight-command burst |

| Commands in one write | First identifying response | Last identifying response | Last command's measured queue wait |
| --- | ---: | ---: | ---: |
| 2 | 200.188 ms | 450.457 ms | 250.304 ms |
| 4 | 200.024 ms | 950.924 ms | 750.906 ms |
| 8 | 200.242 ms | 1,952.372 ms | 1,752.228 ms |
| 8, repeated | 200.238 ms | 1,952.504 ms | 1,752.268 ms |

All 39 queued-command gate samples had no wait flag, casting flag, charm flag
or pending writer ID. No creation-grant or pending item/currency transaction
gate was recorded. The input queue still drained one command per 250 ms pulse.
This directly attributes the controlled burst delay to serialization, with a
separate first-command input-poll wait; it is no longer inferred only from
socket timing or source. It does not establish that the behavior began today.

The test character was level 62. All 39 Divine end-observer calls were
ineligible; **zero eligible-mortal observer calls occurred**. A separate
**60-second, 241-sample** read-only memory observation at 20:41:13–20:42:14
successfully inspected three sessions, all level 61 or 62, with empty sampled
queues and zero read errors. Those samples were not atomic and were collected
after the controlled bursts. They do not prove that no queue existed between
samples, nor do they replace the direct burst trace. Staff timing is valid evidence for input handling, scheduling, execution,
output and network behavior. The absence of mortal observer calls limits only
claims about that observer; it does not weaken staff reports of lag. This
workload supplies no live trade submit-to-receipt measurement. The existing
eligible-mortal and completion-cadence harness results retain their stated
scope; no production account or trade was manufactured to extend it.

#### Concrete production object procedures

The trace measured **16,710 live object callbacks** in **437 vnum/procedure
groups**. Mean wrapper duration was **16.590 µs**, including instrumentation.

| Concrete procedure / object vnum | Calls in this group | Mean wrapper time | Maximum wrapper time |
| --- | ---: | ---: | ---: |
| `nexus_stone()`, 394 | 47 | 1.177 ms | 1.671 ms |
| `artifact_stone()`, 23808 | 23 | 0.599 ms | 0.735 ms |

Every other observed vnum/procedure group had a maximum at or below 0.105 ms.
The procedure addresses resolved to symbols in the live executable. These are
concrete identities from production, resolving the earlier inability to
observe them. **No callback reproduced 17:59's 47.759 ms observation.** Neither
of the procedures above can be assigned to that historical incident: its log
omitted the object/procedure identity, and later tracing cannot recover it.
No new slow-event, event-deferral or whole-tick-overrun entry appeared in the
follow-up status-log interval.

#### CPU profile and cleanup

A **120-second**, 99 Hz `cpu-clock` profile completed with **420 samples and
zero lost samples**. Leading leaf samples included `strcmp` (8.10%),
`get_spell_from_char()` (6.43%), `affected_by_spell()` (5.00%) and the main
`event_mob_mundane()` body (4.52%). This describes CPU activity in a quiet
observed window, not a causal profile of a lag incident. Probe activity also
contributes overhead. An initial 45-second profile produced 61 leaf samples;
its frame-pointer call chains were unreliable for this optimized executable
and were excluded. The accepted 120-second profile did not collect call chains.

The authenticated session quit, both `perf` recordings finished, the memory
sampler exited and the tracing process exited successfully. The kernel's
`uprobe_events` file was empty afterward. Final verification confirmed the
original production PID, start-time identity and executable hash. No restart,
executable replacement, schema change or persistent tracing configuration was
performed. Evidence is saved under the ignored `sudo-2038/` directory below,
owned by the staging account. No command text, player names, player addresses,
account credentials or raw process-memory dumps were captured by the new
queue/memory probes.

### Staff commands and GMCP follow-up, 20:51–20:54

Staff reports are valid evidence of lag. The earlier mention of absent mortal
activity was too broad: staff sessions exercise the common command, scheduling,
output and network paths. Their eligibility excludes only the new Divine
activity observer. This follow-up therefore used the available authenticated
staff account to extend shared-path coverage.

At **20:51:00–20:51:10**, three repetitions of seven read-only commands were
matched to enqueue, dequeue, interpreter entry/return and nested function
probes. All **21** commands completed. These are live instrumented durations;
the response measurement includes input-poll wait, output and local socket
delivery. It is not a client-side measurement from a reporting staff member.

| Command | Interpreter execution, three trials | Send-to-identifying-response, three trials |
| --- | ---: | ---: |
| `time` | 0.128–0.162 ms | 31.247–250.115 ms |
| `inventory` | 0.493–0.556 ms | 50.550–50.736 ms |
| `score` | 0.400–0.425 ms | 49.520–49.670 ms |
| `look` | 0.142–0.189 ms | 49.599–49.686 ms |
| `world stats` | 0.474–0.590 ms | 50.310–50.548 ms |
| `world persistence` | 19.192–27.542 ms | 68.844–77.223 ms |
| `divineboon status` | 17.998–19.636 ms | 41.693–49.557 ms |

The three `world persistence` calls spent **17.129–25.318 ms** in
`divine_boon_selection_status()`, about **89–92%** of interpreter time. The
remaining instrumented health-copy calls each took at most **0.044 ms**;
`persistence_query_snapshot_copy()` reached **0.075 ms**. This isolates the
dominant cost of these diagnostic commands. Their earlier approximately 90 ms
durations were not reproduced, and their historical breakdown cannot be
assigned from these later calls. Separate `divineboon status` commands spent
**17.796–19.481 ms** in the same selector.

Concurrent phase probes recorded **360** intervals between connection-phase
starts: mean **250.349 ms**, maximum **250.459 ms**. The longest measured work
interval from connection-phase start to pulse-reset entry was **38.260 ms**,
coincident with the slowest controlled `world persistence` command. This bounds
the sampled loop cadence and that work interval; it does not cover client-side
rendering, remote network latency or an incident outside the observation window.

A field-only read at **20:51:55** found both connected staff sessions using
plain Telnet with **GMCP enabled**. Their sampled transport buffers and input
queues were empty. A single non-atomic snapshot cannot exclude intermittent
backpressure, but it establishes that GMCP is relevant to the available staff
client configuration.

At **20:53:17–20:53:40**, a second staff session compared GMCP
**off / on / on / off**. Each phase ran two repetitions of `time`, `look`,
`inventory` and `score`, then an eight-command `time` burst. A Telnet parser
excluded GMCP subnegotiation payloads from text-response matching. All **64**
commands were matched to server enqueue, dequeue and interpreter timing.

| GMCP setting, two phases each | Single-command interpreter mean | Single-command interpreter maximum |
| --- | ---: | ---: |
| Disabled | 0.291 ms | 0.481 ms |
| Enabled | 0.298 ms | 0.570 ms |

The first enabled phase received **10 GMCP frames** after opt-in. Neither
disabled phase received GMCP frames. The repeated enabled phase generated no
new state frames because the read-only workload did not change gameplay state.
The comparison therefore covers negotiation, the initial snapshot and ordinary
read-only commands with GMCP enabled, not moving maps, combat, ships or every
structured update. Differences in send-to-response timing also reflect arrival
phase within the 250 ms input cycle; they cannot be assigned to GMCP itself.

Across the four bursts, the last response arrived at **1,950.581–1,950.955 ms**,
including **1,752.075–1,752.241 ms** measured in the server input queue. No active
command wait, casting, charm, writer, creation or transaction gate was recorded
in this controlled comparison. The same one-command-per-pulse serialization
persists with either GMCP setting. This reproduces a seconds-long staff-visible
type-ahead delay and identifies its shared input-queue cause. It does not prove
that a particular staff complaint involved type-ahead or that the behavior was
introduced by today's deployment.

Both temporary tracing processes finished and all probes were removed. The
controlled sessions quit. The original production PID/start identity and
executable hash were verified again, with no persistent configuration or source
change. No new slow-event, event-deferral or whole-tick-overrun entry appeared
in the follow-up status-log interval. The general reported regression still
needs correlation with a specific slow action/time, from staff or mortal play.

### Attribution after the completed tests

**Attribution blocked at 20:59:29 after the completed access-limited tests.**
The same missing correlation remained through the privileged follow-up, the
expanded staff/GMCP tests and a fresh final recheck. No new slow-command or
scheduler incident was recorded since the 20:57 check; sampled input, writer and
transport queues were empty. No measurement process remains running, so there
is no live tracing job to wait on. These quiet observations do not disprove
staff or mortal lag reports. Progress on the remaining causal claim needs a
specific slow action/sequence with its approximate UTC time, or a recurrence
that can be traced. No additional privilege or mortal account is required for
shared-path investigation. See `attribution-blocked-audit-2059.json` below.

The earlier three-turn access block ended when sudo access became available.
All tests previously prevented by privilege restrictions have now run. The
controlled input delay is attributed, and live callback identities are available
for this observation window. The remaining uncertainty is evidentiary: the
general complaints and historical slow callback were not reproduced while
tracing. The measured staff workload is valid for investigating shared paths.
Attribution needs a matching slow action or incident, regardless of whether the
reporting player is staff or mortal. Only the Divine eligible-mortal observer
comparison specifically needs an eligible mortal; trade timing specifically
needs a trade.

The next useful investigation would trace a recurrence or a representative
reported action, including staff gameplay, and correlate it with the reported
time. A mortal or trade workload is needed only for those particular paths.
The retained trace can capture a new callback's identity and wait metadata;
its offsets must be revalidated against the running ELF before reuse. Tracing
is currently detached. There is no outstanding access request and the reported
slowdown is not declared resolved.

| Suspect path | Evidence today | Next diagnostic or possible fix |
| --- | --- | --- |
| Object procedures and event deferral | A 47.759 ms callback and resulting scheduler lateness are recorded at 17:59. The privileged trace identified 16,710 later callbacks, all at or below 1.671 ms. | Capture a recurrence with its object vnum and procedure identity; the historical identity is unrecoverable. Profile that procedure; slice an expensive traversal or move blocking I/O through an existing worker if that is the measured cause. Preserve player timer priority. |
| Divine activity observation | The isolated 57,608-character fixture demonstrates about 2.5–2.8 ms mean observation cost for a player at the list tail; 1,000 inventory objects alone add about 28 µs at the head. | If live profiling establishes that lookup matters, reuse an existing identity index or otherwise avoid the repeated full list walk. The privileged workload contained no eligible-mortal observer calls; live mortal timings remain unmeasured. |
| Divine selection/eligibility | The full-world comparison measured about 46 ms mean hourly selection with 38,937 objects; one EXP slot refreshed in about 128 µs. | Avoid repeated object-list traversal within a selection pass if optimizing rotation. This does not account for sustained cargo-only lag. |
| Cargo/save coordination | Actual trade inbox spans were 4.6–5.8 ms. The real coordinator/worker reproduction demonstrated approximately 500–750 ms to simulated output at normal command submission phases. | Measure live submit-to-receipt and blocked-command timing. Faster completion publication is a measured opportunity, subject to phase-order validation. |
| Outbox audit | One staff snapshot was stale around the minute audit boundary. | Correlate audit duration with delivery latency for newly arriving work. The current aggregate does not demonstrate delayed delivery. |
| Telemetry capture | Matched current-source off/on comparison measured sub-microsecond mean evidence-hook increments and 1.5–3.8 µs mean pulse increments at 4/64 sessions. | These workloads do not reproduce a telemetry stall. Investigate additional hooks only when a specific measured path justifies it. |
| Input polling and network path | Privileged tracing measured 1.752 seconds of queue wait for the last command in an eight-command burst, with no active gate in that controlled session; remote RTTs reached approximately 262 ms in the earlier sample. | Queue timing now attributes the controlled type-ahead delay. Capture wait reasons during a representative lag complaint. A network-readiness change could reduce first-command wait; changing type-ahead throughput requires preserving intentional action rate limits. |

Do not raise the event budget or change simulation frequency merely to hide the
deferrals. First identify the expensive callback and distinguish event lateness,
input queue wait, command gates and network delay. Temporary probes were removed.
No persistent runtime setting, schema, application source or executable was
changed by this investigation.

**Remaining attribution:** today's event deferrals are established. Their
connection to the new systems and the cause of any persistent player lag remain
unproven. Callback identity and command wait timing were captured in the
privileged window, but no corresponding lag incident was observed. Staff
reports are equally valid; a matching staff or mortal incident can resolve
that uncertainty.

## Evidence

Today's source logs are `logs/log/status` and `logs/latency_trace.log` from the
10:37 boot. Fresh sanitized observations are in
`bin/investigations/performance-20261024/current-1807/`:

- `today-latency-windows.json`
- `live-observations.json`
- `game-diagnostics.json`
- `divine-state-and-traffic.json`
- `remote-tcp-samples.json`
- `ping-cloudflare.txt` and `ping-google.txt`

These local measurement files are ignored by Git. Database collection used
read-only sessions with statement deadlines; diagnostic sessions quit after
readback. This report contains no player addresses or credentials.

The 18:21 continuation adds local evidence in
`bin/investigations/performance-20261024/current-1828/`: `input-wait.json`,
`activity-benchmark.csv`, `activity-worldsize.csv`, `telemetry-benchmark.json`,
`full-world-results.txt`, `full-world-run.json`, `trade-timing.json`,
`completion-cadence.csv`, `completion-cadence-run.json` and
`divine-live-comparison.json`, plus `object-reproduction-results.txt`,
`object-reproduction-runtime.log`, `object-reproduction-run.json` and
`final-server-check.json`, their source/driver files and build argument lists.
The next continuation adds `observability-recheck-1859.json` and
`rotation-1900.json`, with `check-1900-rotation.py` retaining the read-only query
and trace-window extraction. `blocked-audit.json` records the final process and
access checks and the classification of the preceding turn as progress.

The privileged continuation adds
`bin/investigations/performance-20261024/sudo-2038/`:

- `live.bt`, `live-trace.txt`, `live-trace.stderr` and `object-summary.json`:
  version-specific probes, raw sanitized timing events and object aggregates.
- `client.py`, `client.json`, `analyze.py` and `analysis.json`: the successful
  authenticated workload and 38 matched send/enqueue/dequeue/response timings.
  The initial loopback connection was refused because the game binds its public
  interface; the accepted run used that interface. No loopback timing was used.
- `memory-sample.py` and `memory-samples.json`: read-only field samples and
  their limitations. No raw memory dump was retained.
- `baseline-perf.data`, `baseline-profile.txt`, `live-perf.data` and
  `live-profile.txt`: the initial sampling attempt and accepted leaf profile.
  The baseline call chains are excluded from the conclusions.
- `offsets.txt`, `more-offsets.txt`, `before.json`, `followup-log-check.json`
  and `final-check.json`: layout checks, process identity, log interval and
  cleanup verification. `completion-audit.json` records the test coverage and
  remaining causal limitations.

The staff follow-up adds `bin/investigations/performance-20261024/staff-2052/`:
`live.bt`, `live-trace.txt`, `live-trace.stderr`, `client.py`, `client.json`,
`function-symbols.json`, `analyze.py`, `analysis.json`, `transport-offsets.txt`,
`transport-snapshot.json`, `before.json` and `final-check.json`. The GMCP
comparison is in the adjacent `staff-gmcp-2053/` directory: `live.bt`,
`live-trace.txt`, `live-trace.stderr`, `client.py`, `client.json`, `analyze.py`
and `analysis.json`. These files contain controlled command labels and timing
metadata, with no captured player command text or GMCP payloads.

`sudo-2038/attribution-blocked-audit-2059.json` retains the final fresh checks,
the three-turn blocker audit and the information needed to resume attribution.
