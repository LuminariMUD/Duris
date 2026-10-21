# Issue #59: PostHog gameplay telemetry implementation plan

Status: **implementation in progress; production remains disabled.**
Source evidence checked on 2026-10-21 UTC against retained
[master `9090518ba091`](https://github.com/LuminariMUD/Duris/commit/9090518ba091abc15b8fb2df4675b9ee3d83bd08).
Tracking: [Duris #59](https://github.com/LuminariMUD/Duris/issues/59).
The previous plan is preserved in [plan-issue-107.md](plan-issue-107.md).
The intervening Assassin plan from master is preserved byte-for-byte in
[plan-issue-187.md](plan-issue-187.md), including its dated review status.

## Implementation handoff (updated 2026-10-21 UTC)

- Preparation is ready for review in [PR #252](https://github.com/LuminariMUD/Duris/pull/252),
  branch `issue-59-posthog-telemetry`. Subsequent chunks stack on this branch.
- The first implementation chunk, [PR #253](https://github.com/LuminariMUD/Duris/pull/253),
  branch `issue-59-posthog-percentiles`, repairs
  both performance-gate percentile helpers. Both now use integer per-mille ranks
  (`990` = p99, `999` = p99.9), with deterministic Python and native regressions
  that distinguish p99.9 from the maximum at 2,000 observations.
- `nice -n 10 python3 tests/async/test_telemetry_capacity_272.py` passed for
  50/200/1,000 synthetic records, three repetitions, including fault fixtures.
  Report: `bin/tests/telemetry_capacity_272.report.json`. This proves the
  existing offline gate, not PostHog delivery or player capacity.
- `./scripts/format.sh --check` and `git diff --check` passed. The full SQL build
  passed with `nice -n 10 make -C src -j2 PERSISTENCE_BACKEND=mariadb
  BIN_ROOT="$PWD/bin/issue59/mariadb"`; log: `bin/issue59/build-mariadb.log`.
- The second chunk, [PR #254](https://github.com/LuminariMUD/Duris/pull/254),
  branch `issue-59-posthog-encodings`, implements worker-side
  character HMAC pseudonyms, canonical session/run IDs, one-time UUID v4 creation
  and timezone-independent microsecond UTC formatting in `telemetry_posthog.*`.
  It links into both builds but is not connected to capture/delivery yet.
- The compact mapping, concrete encodings, integer/null representation, reducer
  bounds and complete declared volume fixture are in `docs/telemetry/CONTRACT.md`.
  `tests/async/fixtures/telemetry/posthog/{encodings,volume}.json` and
  `test_telemetry_posthog.py` check native encodings against independent Python
  HMAC vectors, integer limits, invalid inputs and the six-family volume forecast.
  Both MariaDB and flat-file component variants passed under UBSan.
  The forecast is 353,563 submissions at 100 average connected characters with
  15-minute windows, 706,077 at 200, and 396,454 at 200 with 30-minute windows.
  These are explicit fixture assumptions, not production or reducer measurements.
  Logical login/logout contributes two lifecycle rows, reconnect two additional
  rows, and copyover one attach; the oracle follows the native session producer.
- Second-chunk verification passed: `python3 tests/async/test_telemetry_posthog.py`,
  `python3 tests/async/test_telemetry_contract_headers.py` and
  `python3 tests/async/test_telemetry_contract_fixtures.py`. Native encoding
  children use an allowlisted local environment and synthetic keys; the
  pre-existing contract checks covered ten fixtures / 40 records and standalone
  headers in both build modes. Full low-priority `make -C src -j2` builds passed
  with `PERSISTENCE_BACKEND=mariadb` and `flatfile`, respectively, using
  `BIN_ROOT="$PWD/bin/issue59/<backend>"`. Logs:
  `bin/issue59/build-{mariadb,flatfile}-encodings.log`. No executable was deployed.
- Authenticated read-only PostHog literal/JSON queries verified lossless signed
  and unsigned 64-bit conversion, null handling and 128-bit aggregate sums.
  `toUInt64` is unsupported in HogQL, and `toDecimal` returns null for unsigned
  maximum. Use `toInt` / `accurateCastOrNull(..., 'UInt64')` for values and
  `accurateCastOrNull(..., 'Int128'/'UInt128')` before sums. Exact successful
  queries/results are recorded in the contract; no cloud events were submitted.
  The account recheck confirmed project `678214`, free billing, no active
  subscription, `ingested_event=false` and zero analytics usage.
- The third chunk, [PR #255](https://github.com/LuminariMUD/Duris/pull/255),
  branch `issue-59-posthog-reducer`, implements character
  reduction and bounded immutable JSON output in the same module: 256 sessions,
  two fragments/session, 32 time and 32 XP buckets, 64 validated configurations,
  and 128 events / 512 KiB retained output. It consumes intervals, XP/levels,
  lifecycle, checkpoints, configuration and gaps. It explicitly refuses encounter
  and combat records until the next slice; the runtime is still unconnected.
- Reducer evidence: `python3 tests/async/test_telemetry_posthog.py` passes 36
  executable scenarios in both build modes under UBSan. They cover conservation,
  checkpoint baselines/conflicts/late detail, level/config/dimension changes,
  late windows, midnight, clock failure, signed/unsigned arithmetic and bucket
  overflow, 256/257 sessions, 64/65 configurations, row/byte/age limits, immutable
  retained output, JSON allocation failure and scope/replay refusal. A lost native
  exit cannot pin a slot forever: after 3,720 seconds without any input for that
  session (maximum native cadence plus queue allowance), seal with unknown-tail
  coverage and free it without inventing a logout/entry. A later observation
  keeps its original logical identity and has no invented checkpoint baseline.
  The JSON allocation-failure case also passes ASan/UBSan with leak detection,
  covering zero and partially constructed documents at four allocation budgets.
  Contract
  header and configuration tests also pass. Both full low-priority builds pass;
  logs: `bin/issue59/build-{mariadb,flatfile}-reducer.log`.
- Review repair validates all six findings: configurations are cached only after
  output retention; every known-window seal tracks subsequent late fragments;
  the split-limit remainder is explicitly unattributed; missing initial sequence
  prefixes are counted; unknown XP levels cannot inherit later known levels;
  and direct character events flag incomplete dimensions. Twelve added scenarios
  reproduce event/byte/allocation pressure, all sealing paths and the remaining
  accounting cases using the existing harness. Both backend variants pass UBSan.
  All 36 scenarios also pass ASan/UBSan with leak detection. Review build logs:
  `bin/issue59/build-pr255-{mariadb,flatfile}.log`; both server builds pass.
- Ablation: reuse the existing canonical configuration fingerprint; retain only
  typed accumulators, checked metrics and one packed output arena. HTTP can read
  an immutable prefix without making a second retained JSON copy. Context
  overflow stays inside summaries, avoiding per-minute exports. Explicit unknown
  dimensions remain in allocations rather than being filled from later data.
- Next: implement bounded encounter/combat joining and health output, then the
  HTTPS sender and durable quota before connecting runtime/transport. Native
  queue admission age and the timer fence belong to that integration; occurrence
  age is not admission age. Resolve the sender's retained retry prefix before
  retiring/expiring borrowed output views. Pet identity, HTTP/quota/lifecycle,
  SQL removal, gameplay/cloud/report proofs remain open. The isolation gate
  below still applies; no production operation or cloud capture has occurred.
- No live game operation or cloud event has been performed. Production enablement
  is separately authorized; this work prepares reviewable implementation PRs.

This plan implements the issue's PostHog decision and acceptance requirements.
The SQL recommendations in the older [telemetry review](telemetry-review.md)
are superseded where they describe the delivery/reporting path being replaced.
Its capture, capacity, coverage and performance findings still matter.
Numbers below described as implementation limits are decisions to implement and
test, not measurements of enabled telemetry or claims about player capacity.

## Outcome and boundaries

Deliver one opt-in C++ telemetry path: existing gameplay observations → bounded
queue → existing worker → bounded summaries → PostHog HTTPS batch capture.
Provide one PostHog dashboard covering character activity/returns, time
allocation, observed XP/levels, and encounter outcomes/contributions, with a
saved health/coverage query. Both SQL-backed and flat-file gameplay must work.
Analytics failure must not compromise commands, saves, login, copyover or shutdown.

Keep the existing hooks, classifier, captured configuration, logical sessions,
queue, worker ownership and protected outage-storage machinery. Remove the
replaced SQL writer and active rollup/report dependencies. Preserve historical
data, immutable migrations, committed reward authorities and independent reward,
study and non-writing balance tools.

No new service, Node/Python sidecar, generic sink framework, payload spool,
historical backfill, website instrumentation, LLM integration, MCP-tool analytics,
Workflows, Session Replay, warehouse connection, paid Group Analytics, account
linkage, automatic balancing or new gameplay metric is required. PostHog MCP is
an administrative tool for this work; the game never depends on it.

Production deployment/enablement is a separate, explicitly authorized operation.
Work through the character-reducer chunk performed no game login, server restart, migration, database
mutation, event capture or PostHog dashboard mutation.

## Verified starting facts

| Area | Current evidence and implication |
| --- | --- |
| Host | `/home/staging/duris` is production: both `.env` and the running process identify it as production. The live executable is `bin/server/dms`; directory naming does not make it staging. |
| Live environment | The inspected process had no `TELEMETRY_ENABLED`, PostHog host/project settings, or property-catalog setting. Current bootstrap defaults disabled. The newly edited `.env` is not the running process environment. No fresh health line was found in the bounded recent-log sample; no enabled runtime/performance claim follows from this inspection. |
| Local setup | `.env` is ignored and mode `0600`; the project token is populated, host is `https://us.i.posthog.com`, project is `678214`, environment is `1`, season is `1`. No token value belongs in this plan or Git. |
| Journal directory | `/home/staging/duris/runtime/telemetry-outages` exists, is owned by the current user and has mode `0700`. Existence is not proof of initialized quota state or permission to change live evidence. |
| PostHog | Authenticated MCP read at 10:59 UTC returned project **Duris SBS PostHog**, ID `678214`, UTC timezone and admin access. Its capture token matched `.env`. Dashboard reads and `SELECT 1 AS setup_access_check` succeeded. Write scopes were authorized; writes were not exercised during planning. |
| Billing | The live billing overview returned `billing_plan=free`, no active subscription, a 1,000,000-event free allocation/usage limit and zero reported analytics usage. Current billing period: 2026-10-21 09:14:54.264 UTC through 2026-11-20 09:14:54.264 UTC. Usage is a snapshot and must be checked again before cloud tests and enablement. |
| Existing reports | Only the [starter dashboard](https://us.posthog.com/project/678214/dashboard/2238933) was returned. `ingested_event=false`; no Duris event schema or report ingestion has been proven. Session recording is off. |
| Build dependencies | `src/Makefile` already links libcurl, cJSON and OpenSSL. Installed libcurl is `8.18.0`, cJSON `1.7.19`; compiler, make, clang-format, Python and native MariaDB tools are available. No analytics SDK is needed. |
| Host resources | Read-only snapshot: 8 logical CPUs, approximately 15.6 GiB RAM, 6.7 GiB available, and 257.5 GiB free filesystem space. These are not reservations or an enabled-telemetry budget. |
| Isolation access | Docker daemon access is denied; noninteractive sudo is unavailable; `unshare -Urn true` is denied. The existing `with_disposable_mariadb.sh` uses Docker and cannot currently run under this login. Native MariaDB is `11.8.6`; it is not evidence for the repository's MySQL 8/MariaDB 10.11 compatibility fingerprints. |
| Scheduled jobs | No telemetry entry was found in the current user's crontab or readable `/etc/cron.d`, `/etc/systemd/system` and user-systemd files. This does not establish the contents of other users' private crontabs or external schedulers. Recheck the actual deployment inventory at cutover. |

The local Codex MCP connection is OAuth-authenticated at `https://mcp.posthog.com/mcp`.
This session verified it through the local Codex app-server's MCP calls; installing
local configuration does not imply tools appear automatically in every hosted chat.
Capture uses the project token. Query/dashboard administration uses OAuth, not the
capture token; no personal API key is currently needed.

## Source facts that determine the change

1. [Runtime](../../src/telemetry/telemetry_runtime.c) enables only the SQL backend,
   explicitly disables `__NO_MYSQL__` builds, and qualifies a reviewed property
   catalog before enabled capture. Its worker opens the outage journal, then
   calls transport pulse/drain. `all_admitted_records_durable()` relies on SQL
   applied/duplicate/checkpoint accounting. These are real coupling points.
2. [Transport](../../src/telemetry/telemetry_transport.c) owns bounded queue and
   in-flight records, but its production binding calls the SQL repository.
   SQL record-by-record commit reconciliation cannot be reused as an HTTP
   acknowledgement contract. Reduction must consume each native record once;
   an HTTP retry must never feed the same XP/time into the reducer again.
3. [Native records](../../src/telemetry/telemetry_types.h) have eight kinds.
   Activity is fragmented by time/category/context; progression emits individual
   XP attempts. Changing the native interval from one minute to 15 minutes alone
   does not bound external volume.
4. The queue has 8,192 slots with 128 reserved for control. Session/activity each
   retain 256 resident sessions; configuration identity has a 64-entry lifetime
   registry and four pending publications. Encounters retain 128 runs, 64
   participants and 256 events per run; combat retains 128 runs × 64 actors.
   Detached sessions and departed actors still consume applicable capacity.
   These are capture limits, not supported concurrent-player claims.
5. Native `subject_id` is currently the character's numeric PID. Exporting it
   directly would not provide opaque identity. `game_dimensions()` captures
   class, race, faction, zone and a five-level **band**, not exact level.
   Progression separately carries before/after levels. Encounter/combat records
   do not contain all character dimensions or a logical-session reference.
6. [Copyover](../../src/persistence/copyover.c) writes a valid telemetry handoff
   only when a 250 ms flush reports durability. Keeping that condition would
   discard logical-session continuity during a PostHog outage. Session identity
   preservation must be separated from delivery success.
7. [Outage storage](../telemetry/OUTAGE_STORAGE.md) is evidence, not payload
   recovery. The current worker attempts a full-history sample roughly every
   second and ignores later checkpoint failures. The new quota must durably
   reserve before HTTP, and publication failures must become visible.
8. [SQL boot checks](../../src/sql/sql.c), the
   [compiled compatibility contract](../../src/core/runtime_compatibility_contract.h)
   and [manifest](../../migrations/runtime_compatibility_manifest.json) include
   telemetry tables in the 198-table inventory and metadata fingerprint.
   Removing the worker's SQL connection alone does not remove this boot dependency.
   [The validator](../../scripts/validate_runtime_compatibility.py) currently
   equates the complete lifecycle inventory with the required runtime inventory.
9. The [player journey](../../tests/async/run_telemetry_player_journey.py) is
   SQL-specific, asserts SQL telemetry rows and uses an older DB-name prefix.
   Reuse its clients, fixtures and copyover journey, replacing its analytics
   assertions and supplying an isolated journal. Do not run it unchanged here.
10. Both percentile helpers in
    [benchmark_272.py](../../scripts/telemetry/benchmark_272.py) and
    [its native harness](../../tests/async/telemetry_capacity_272_harness.cc)
    originally divided by 100 when passed `999`, reporting the maximum as
    p99.9. The first implementation chunk fixes both to use per-mille ranks.
    Existing 50/200/1,000 profiles count records, not players.

## Locked event and identity contract

Use exported schema version `1`, distinct from the native schema discriminator.
Preserve native immutable record identities internally. Every exported row gets
an immutable valid event UUID and matching `duris_event_id`; retries retain the
UUID, occurrence timestamp, distinct ID and serialized event properties.

| Native kind | Export decision |
| --- | --- |
| `interval` | Reducer input for `duris_character_summary`: additive connected/active/idle/unknown/linkdead microseconds and bounded historical allocation buckets. |
| `session_lifecycle` | `duris_session`, with explicit logical-entry/exit or connection-attach/detach transition. Connection changes do not become new logical sessions. |
| `session_checkpoint` | Keep latest absolute counters/revision as reconciliation evidence attached to the next summary/lifecycle boundary; never emit every checkpoint or add them to interval deltas. |
| `coverage_gap` | Mark affected summaries and aggregate bounded incident evidence into `duris_telemetry_health`; retain local evidence even when cloud delivery is unavailable. |
| `configuration` | `duris_configuration` when a configuration is first required or changes; bounded full-fingerprint validation/cache. No full config object on every activity row. |
| `progression` | XP observations coalesce into summaries. Level-advanced/lost records become `duris_level_change`; threshold consumption remains separate from XP awarded/lost. |
| `encounter` | Start/join/leave update bounded run state only. Terminal run and participant summaries become `duris_encounter_summary` with `row_type=run` or `participant`. |
| `combat_summary` | Join retained player/pet contributions into terminal `row_type=participant` rows, distinguished by `actor_kind`. Pet rows carry an opaque owner reference and are never added into the owner's player row. Drop unsupported NPC detail before export, with explicit accounting. |

Identity and permitted fields:

- Use a dedicated random 32-byte `TELEMETRY_IDENTITY_KEY`, generated during
  implementation/setup, stored only in protected `.env` and backed up privately.
  It is not the PostHog token. HMAC-SHA-256 over a versioned, unambiguous encoding
  of `(environment, season, character PID)` produces `duris_character_id` and the
  character-event `distinct_id`. The same character retains identity across
  connections/restarts; different worlds/seasons cannot collide. Never log the
  key or raw PID. Record a nonsecret key-version identifier; no silent rotation.
- Missing/invalid identity key disables export rather than falling back to raw
  IDs or generating a new key at every boot. Test keys are synthetic. Key setup
  is work the implementation can do, not missing information from the owner.
- Keep `duris_session_id` and run IDs as canonical string encodings of their
  original producer/sequence identity. Health/configuration/run-only rows use
  separate scoped system/run distinct IDs and cannot enter character counts.
  Pet rows identify the pseudonymous owner and a run-scoped opaque actor ID;
  owner and pet contributions are separate.
- Use `$process_person_profile=false`; send no identify/alias/person updates,
  `$groups`, browser `$session_id`, names, emails, account IDs, IP properties,
  raw commands/chat, credentials, room IDs, hostnames or arbitrary config text.
  Use event-time fields, never current PostHog person properties.
- Retain captured environment/season/configuration versions, quality flags and
  occurrence bounds. Export class/race/faction/level-band only where captured.
  Exact before/after level comes from progression. For existing encounter rows,
  unavailable character dimensions remain null with a reason; no lookups of
  current characters and no invented historical session IDs. Encounter views
  use the captured run/actor dimensions they actually have.
- UTC `[start,end)` bounds and integer microseconds remain the accounting units.
  Export IDs and potentially large integer counters losslessly as decimal
  strings where needed; cJSON's double-valued number API must not round 64-bit
  IDs or XP. Define and fixture-test the corresponding HogQL conversions.
  Use checked arithmetic; counter overflow marks an explicit lower bound or
  unavailable total rather than wrapping or silently rounding.
- If occurrence UTC is unavailable, preserve null occurrence bounds and mark
  `timestamp_basis=emitted_at` using the sealing UTC solely for transport.
  Such rows are excluded from occurrence-day totals and shown as unallocated
  evidence. If sealing UTC is also untrustworthy, hold only within the bounded
  age limit and report clock failure locally; do not let PostHog invent the date.

Production environment `1`, staging `2`, initial local world `3`, and initial
PostHog season `1` remain reserved in [CONTRACT.md](../telemetry/CONTRACT.md).
Fresh isolated worlds receive distinct IDs starting at `1000`; a test-run tag
is additional filtering, not a replacement for namespace isolation. A restored
independent world receives a new identity. A restart/deployment is not a season
change. Season `1` is not a claim about the historical wipe number.
Enabled export must require an explicit nonzero `TELEMETRY_ENVIRONMENT_ID` and
validate it against `ENVIRONMENT`: production `1`, staging `2`, local `3` or a
dedicated isolated-world ID at least `1000`. Missing, malformed or role-mismatched
scope disables export without affecting gameplay. The current runtime defaults
to `1` independently of the role; replacing that fallback is required before
connecting the exporter, with regression cases for every role and missing scope.

## Reducer: bounded work without changing observed meaning

Implement the reducer and HTTP sender together in `telemetry_posthog.{c,h}`,
called only by the current worker. Reuse the existing queue and test seams;
replace their SQL-specific delivery contract rather than wrapping the SQL
repository with another sink layer.

Initial limits, to be enforced by constants and fixtures:

| Resource | Limit / behavior |
| --- | --- |
| Summary window | 900 seconds; configurable to 1,800 if measured volume requires it. This is separate from native capture/checkpoint/classifier timing. |
| Character accumulators | 256 session slots, each with at most two window fragments to tolerate a boundary crossed by a deferred native interval. Flush affected data on identity/configuration/level boundaries and lifecycle exit. A sealed row must be queued or explicitly suppressed before its slot is reused. |
| Historical allocation | Up to 32 `(class,race,faction,level-band,zone,group-size,activity-context)` buckets per character window. Overflow preserves category totals in an explicit unattributed bucket. |
| XP allocation | Up to 32 `(class,race,faction,level-band,zone,group-size,source,reason,modifier-flags,observation-status)` buckets per character window, with requested/computed/applied totals, attempt count and zero-applied count; overflow preserves overall totals/counts and marks attribution unavailable. |
| Encounter reduction | Separate bounds of 128 active runs and 128 pending terminal joins, each with at most 64 retained actors. Producer close frees its active slot immediately; reducer pending state cannot consume the active-run allowance. A close waits at most 120 seconds. If pending capacity is full, finalize its oldest join early with incomplete-terminal coverage and known-prefix totals before accepting another close; later evidence is explicit late loss. |
| Configuration cache | 64 full identities, matching the capture registry; collision/missing/full states are reported, never silently aliased or evicted into false completeness. |
| Sealed output | At most 128 events and 512 KiB serialized storage, including the immutable retry batch. At most 32 KiB per event and 120 seconds retained age for all output. Limits include nested buckets and framing, not `sizeof(native_record)`. |
| HTTP batch | At most 64 events and 256 KiB, flush within 2 seconds after rows are sealed. Flush timing does not generate extra periodic character rows. |

Important ordering and accounting rules:

1. Release native queue entries only after reduction has consumed them once or
   recorded explicit loss. Keep native-consumed, summaries-created, output-dropped,
   attempted and HTTP-acknowledged counts separate. A drained native queue can
   still have accumulator state, sealed events, or an ambiguous retry batch.
2. Key summary dimensions/configuration at observation time. Never smear an XP
   reward across a later level/configuration or put earlier time in the last zone.
   Preserve time and XP attribution separately: two independently expanded
   bucket arrays must not create a Cartesian product in report queries.
3. Seal at UTC-day and export-window boundaries as well as required lifecycle
   and version boundaries. Split time intervals using captured endpoints; count
   an XP observation once in its occurrence window. Monotonic duration remains
   authoritative across wall-clock changes; untrustworthy UTC allocation is
   unknown coverage rather than a guessed historical day.
4. At a timer boundary snapshot the native queue's admitted tail, then consume
   through that fence before sealing eligible windows. The fence orders consumed
   records; it does not prove that a delayed producer can never emit older time.
   A row arriving after its window was sealed goes into a new uniquely identified
   partial fragment, never into the old sealed row. Coalesce that fragment until
   the next normal flush/boundary, rather than sending once per late record.
   If both window fragments are occupied, seal the oldest before accepting a
   third; inability to retain it is explicit suppression. Late/extra fragments
   count in the volume fixture and cannot disappear from completeness reporting.
5. Compare latest absolute checkpoints with accumulated observed deltas. Missing
   detail can be shown as reconciliation-only totals, never attributed to a
   guessed zone/class or added to the same chart twice. Keep
   `connected = active + idle + unknown` and `resident = connected + linkdead`.
6. Finalize run/participant/combat joins after expected terminal evidence has
   arrived and the captured queue fence is consumed, or at the 120-second close
   deadline or pending-capacity pressure with missing pieces marked unavailable.
   Pressure finalization is explicitly incomplete even if its fence has not yet
   been consumed. Test 128 pending closes plus 128 new active runs, then pending
   overflow, preserving known contributions and counting missing/late evidence.
   A native close row alone
   does not prove all combat rows followed. Finalize output incrementally within
   the bounded output capacity. Late terminal data after finalization is explicit
   late loss, not a second counted run. Missing run state, actor/roster overflow
   and incomplete terminals affect coverage; retain known contribution totals.
7. Reaching output capacity, age limits or a quota is explicit suppression, not
   permission to grow a queue, mutate a sealed retry or randomly sample XP/time.
   Native capture is still drained and its loss/coverage counters remain useful.

## HTTP delivery and failure states

Construct `/batch/` from validated `POSTHOG_HOST`, allowing only
`https://us.i.posthog.com` or `https://eu.i.posthog.com`; the configured project's
region determines the endpoint. Reject missing/invalid hosts rather than falling
back to another region. Use the existing libcurl/cJSON dependencies, with the
project token at batch level and event name, distinct ID,
timestamp, UUID and properties per event. Validate required fields locally.
The [capture API](https://posthog.com/docs/api/capture) documents batching and
anonymous capture, and explicitly warns that HTTP 200 can accompany discarded
invalid events. Thus HTTP acceptance is not query-verified ingestion.

Use one reusable worker-owned curl handle. Verify TLS and the host; do not follow
redirects carrying the token. Keep response bodies capped at 16 KiB and logs
payload/token-free. Initial connect/total timeouts: 1/2 seconds, always reduced
by a nearer lifecycle deadline. Check the deployed curl resolver/cancellation
behavior rather than assuming a timeout alone guarantees bounded teardown.

- Retry network errors, 408, 429 and 5xx with the same sealed events; count the
  initial send and every retry against quota. Initial policy: at most five
  attempts per batch, 1/2/4/8-second backoff, capped retry age 120 seconds.
  Respect a valid `Retry-After`; if it exceeds retention/deadline, suppress with
  visible loss rather than hammering the service.
- Retry exhaustion discards only the bounded unresolved payload with uncertainty
  recorded. Use a paced 60-second recovery probe before resuming ordinary sends;
  do not permanently disable analytics for a temporary outage or retry in a loop.
- Permanent authentication/configuration/TLS failures open a telemetry-only
  circuit until corrected and reinitialized. Malformed local rows are rejected
  before sending. Unexpected permanent batch rejection/413 is an exporter
  failure; do not build an unbounded split/replay mechanism to hide it.
- Acknowledged batches can be released from RAM. Record that their ingestion
  remains unverified until independently queried. No administrative/query token
  is required in the game server and it performs no per-batch query polling.
- Retain a stable `duris_event_id` in addition to UUID. Validate actual duplicate
  handling with the bounded cloud fixture; saved totals must deduplicate by this
  identity before summing or expanding arrays. Do not assume eventual ingestion
  deduplication alone is sufficient for every dashboard query.

PostHog documents a valid optional deduplication UUID in its
[capture SDK contract](https://posthog.com/docs/libraries/ruby). Its exact
behavior for our direct batches remains a cloud acceptance test, not a planning
claim. [SQL array expressions](https://posthog.com/docs/sql/expressions) provide
the basis for bucket reports; validate the exact queries against synthetic rows.

## Free-tier enforcement and durable evidence

Keep issue #59's targets: **≤450,000 submissions per 31 days under normal load**,
**≤20,000 per UTC day across all Duris senders**, including every retry and test,
and **<700,000 projected combined project/account usage per billing cycle**.
Of the daily allowance, reserve 100 for hourly/change-driven health. Ordinary
configuration/lifecycle/encounter events do not consume the health reserve.
No unused credits carry over. Batch HTTP requests do not reduce event count.

Operationally allocate at most 19,900/day to the production sender, including
its health reserve, and at most 100 total cloud-smoke submissions on a test day.
Other environments default to mocks. Additional real senders require a documented
allocation whose sum stays within 20,000; independent state directories do not
create additional free allowances. Recheck unrelated website/other producer use
before enabling and lower allocations when the shared projection requires it.

Extend the existing protected outage journal format and ownership mechanism:

- Store project/sender/scope binding, UTC quota-day high-water mark, cumulative
  normal/health reservations and versioned coverage state in the same publication
  transaction. Preserve checksums, exclusive ownership, `O_CLOEXEC`, owner-only
  files, atomic rename/fsync, pending-frame validation and historical decoding.
- Durably reserve the exact event count **before each HTTP attempt**. Charge
  against the attempt-start UTC day, not the event's occurrence date. A crash
  after reservation or an ambiguous response never refunds credits.
- Initialize quota explicitly once before first enablement, under the existing
  lock and without sending. Provide a small one-shot native state-tool command
  that calls the same journal implementation; no second writer/serializer or
  automatic initialize-on-boot flag. Normal startup never treats a missing ledger
  as a fresh allowance. Corrupt/missing initialized state, detectable rollback,
  conflicting ownership or failed durable publication stops export locally.
  A complete rollback of every local file is not magically detectable from those
  same files: the restore procedure must conservatively exhaust the affected
  UTC day's allowance before export resumes. Test that recovery command and
  preserve the original evidence; never present an old backup as a fresh budget.
- Preserve current quota through producer restart, copyover and the journal's
  256-lifetime archive rollover. It is sender/day state, not a counter belonging
  only to the newest producer. Test clock rollback: no new allowance while UTC
  is behind the recorded high-water day; roll forward only on a valid new day.
- Publish quota with sends, lifecycle/incident changes and a bounded dirty-state
  checkpoint cadence (initially 60 seconds), rather than rewriting an unchanged
  full producer history every second. Pace storage-failure retries; include
  unsampled crash-tail uncertainty explicitly. This changes the evidence window
  and must be reflected in the journal contract and tests.
- At quota exhaustion suppress that class of events until the next eligible UTC
  day, with bounded local counters and no next-day payload backlog. Local health
  remains available even when the health reserve or network is exhausted.

One 15-minute character summary gives 148,800 submissions at 50 average connected
characters over 31 days, or 297,600 at 100. These exclude other event families,
detached residents, boundary splits and retries. At 200 the summary-only figure is
595,200: the initial window already misses the normal-load target. Test the full
mix; switch to 30-minute summaries and reduce encounter detail only while retaining
required totals and explicit coverage, then remeasure. A 31-day billing window
can touch 32 UTC dates; the 20,000 ceiling therefore bounds submissions to 640,000
before unrelated project producers, not necessarily 620,000.

## Lifecycle, health and SQL removal

**Copyover:** retain every valid logical-session handoff regardless of HTTP
delivery. Carry cumulative counters and quality flags using the existing value
handoff; identify any abandoned accumulator/queue/in-flight tail as incomplete.
Keep the 250 ms game-thread wait bounded. If the worker cannot finish, retain
identity and record uncertainty rather than zeroing the handoff or blocking
copyover. No HTTP/journal operation moves onto the game thread. New process
startup must acquire journal ownership and preserve the same day's reservations.
Test real exec, failed exec, failed flush, detach/reconnect and shutdown.

**Health:** extend the existing snapshot, `world telemetry` and payload-free
health logging. Expose producer occupied/max slots and refusals by reason,
configuration availability, attempted/admitted native counts by kind, reduced
rows, output occupancy/age, submissions/retries, HTTP acknowledgements, known
suppression and ambiguous loss, quota remaining, last successful journal time,
publication error and clock state. Do not relabel `applied_records` as durable
PostHog data. Refusal attempts are not distinct lost characters; actor-add
failures are not distinct omitted players. Include coverage flags by family and
known scope, with global unknown scope where finer attribution was never captured.

**SQL removal:** replace runtime enablement/backend/durability guards and the
production repository binding; flat-file builds use the same HTTPS exporter.
Remove the old native SQL writer from active linking and retire its writer-only
code/tests once replacement coverage exists. Keep any socket-close-on-exec helper
still used by gameplay SQL. Search real callers before deletion.

Separate full historical/lifecycle schema inventory from mandatory gameplay boot
inventory. Exclude the nine replaced ingest/rollup/report tables from the latter:
`telemetry_config`, `telemetry_quarantine`, `telemetry_session`, `telemetry_interval`,
`telemetry_player_day`, `telemetry_cohort_day`, `telemetry_cohort_member`,
`telemetry_rollup_state`, `telemetry_rollup_session`. Preserve reward projection
tables and their independent consumers. Keep full migration/lifecycle inventories,
sealed migration checksums and historical tables intact. Update the compiled
runtime list/count, manifest, validator and normalized metadata calculation
together; account for foreign keys involving excluded tables without weakening
checks on gameplay-owned constraints. Recompute both supported engine fingerprints
from fresh disposable schemas; never invent hashes or loosen the whole boot gate.

Prove boot succeeds with those nine tables absent or drifted in **synthetic**
databases, while missing/drifted gameplay authority still fails before writes.
Historical readers may remain explicitly offline where they serve retained data;
stop scheduling the replaced live SQL rollup/report path. Preserve independently
used reward tooling and its non-writing evaluator boundary. There is no production
DROP, data deletion, backfill or migration-history rewrite in this task.

## Dashboard acceptance

Create **Duris gameplay telemetry** in the verified project, leaving the starter
dashboard alone. Store event/property descriptions and the exact saved query
definitions/IDs in [REPORTS.md](../telemetry/REPORTS.md) and the contract.
Use native insights where semantics fit; use saved HogQL for explicit event-ID
deduplication, nested allocation and cross-family reductions. All production
queries require environment `1`, the chosen season, schema `1` and non-test data.

| View | Required meaning and proof |
| --- | --- |
| Character activity/returns | Unique pseudonymous characters and logical entries/returns across sessions. Reconnect/copyover does not increment logical-entry counts. Label as returning characters, not player/account retention. |
| Time allocation | Add interval-derived active/idle/unknown/linkdead deltas by captured dimensions. Show reconciliation-only evidence separately, missing attribution and incomplete coverage. Prove conservation and no checkpoint double counting. |
| XP and levels | Requested/computed/applied XP, attempts/zero-applied counts and source/modifier allocation; observed level transitions and threshold use separately. Do not call observed XP a committed-save reward. |
| Encounters | Run outcomes/duration, participation and supported player/pet contributions, separated by row type. Avoid counting a run once per actor or merging pet totals into owner totals. No unwired control-effect metric rendered as zero. |
| Saved health/coverage query | Freshness, last HTTP acknowledgement versus queried data, suppression/unknown attribution, producer limits, journal faults and quota. Show incomplete periods even if normal events disappear. No cloud dashboard can report a currently disconnected server's unsent health; local health is authoritative then. |

The cloud fixture must prove these definitions with known totals, repeated UUIDs,
two logical sessions for one character, a reconnect/copyover within one session,
XP zero-application and a level boundary, pet/owner separation, and an incomplete
encounter. Validate exact integer decoding and array expansion; unavailable
fields are null, not zero. Query results, not HTTP status or onboarding checkmarks,
establish ingestion. No event is sent during this planning task.

## Implementation sequence and files

1. **Freeze fixtures and encodings.** Extend
   [CONTRACT.md](../telemetry/CONTRACT.md) with all eight mappings, event-ID and
   pseudonym encoding, bucket bounds, UTC/late-record rules, terminal ordering,
   64-bit encoding, loss classifications and a complete event-volume fixture.
   Implement a focused `tests/async/test_telemetry_posthog.py` alongside existing
   native harnesses. Its tests must verify behavior rather than source strings.
2. **Replace worker delivery.** Add `src/telemetry/telemetry_posthog.{c,h}` and
   adjust `telemetry_runtime.*`, `telemetry_transport.*`, relevant private
   bindings/types and `src/Makefile`. Preserve gameplay-thread value-only capture.
   Implement reducer, bounded serialized retry ownership and fake HTTP tests
   before allowing cloud delivery. Update config/backend validation for both builds.
3. **Finish quota, failure and lifecycle semantics.** Extend `telemetry_outage.*`,
   `telemetry_health.*`, relevant types, `src/persistence/copyover.c` and existing
   operator/log formatting. Update `scripts/telemetry/outage.py` for versioned
   evidence and add the one-shot native quota initialization/recovery command
   under `bin/tools/`. Make publication/producer failures visible and enforce quota before
   send. This is part of the exporter, not a later hardening phase.
4. **Remove SQL prerequisites together.** Update `src/sql/sql.c`,
   `src/core/runtime_compatibility_contract.h`,
   `migrations/runtime_compatibility_manifest.json`,
   `scripts/validate_runtime_compatibility.py` and compatibility tests. Keep
   lifecycle inventory/history intact; adjust its validator only where it must
   recognize optional historical stores. Remove obsolete live writer/settings
   and inventory any actually scheduled legacy jobs.
5. **Qualify real gameplay and reports.** Adapt
   `tests/async/run_telemetry_player_journey.py` for both persistence backends and
   fake capture, reusing flat-file/combat/copyover fixtures. Update the schema
   boot journey for the new optional telemetry-table boundary. Correct and adapt
   the capacity/performance gate. Run the bounded cloud fixture and create the
   dashboard only once access/budget checks pass.
6. **Write the operational handoff.** Update `.env.example`, `CONTRACT.md`,
   `TRANSPORT.md`, `OUTAGE_STORAGE.md`, `CONFIG_CONTEXT.md`, `REPORTS.md`,
   `PERFORMANCE_GATE.md`, the canonical operator
   [configuration table](../operations/CONFIGURATION.md),
   [runbook](../operations/RUNBOOK.md) and
   [regression descriptions](../testing/REGRESSIONS.md). Replace active
   SQL-writer/backend instructions when retiring that path; label retained
   historical SQL tools explicitly offline. Mark superseded SQL guidance in the
   readiness review. Record exact evidence, remaining limitations, enable/disable/recovery,
   active sender allocations and deployed version identities. Keep production
   disabled until separately authorized.

Settings remain focused: existing opt-in/scope/version/property-catalog controls,
`POSTHOG_API_KEY`, `POSTHOG_HOST`, a dedicated identity key, export-window seconds,
downward-adjustable daily submission limit and protected state directory.
`POSTHOG_PROJECT_ID` is administrative metadata, not authentication. HTTP sizes,
retry limits and bucket capacities are constants, not a new operator tuning API.
Use an injected fake receiver in tests; never accept arbitrary production HTTP
hosts or disable TLS as a convenience.

## Verification and execution environment

### Isolation prerequisites

Build and execute only disposable fixtures, never the running production binary
or state. Build under a task-specific `bin/` subtree or a separate checkout;
copyover fixtures contain their own `bin/server/dms` and state path. Start from
an allowlisted child environment, with `ENVIRONMENT=local`, synthetic credentials,
distinct world IDs, test journals, locked loopback ports, disabled Redis/external
integrations and fake PostHog tokens. Never source the host `.env` or copy live
accounts, player files, authoritative journals or database rows.

The existing native disposable-MariaDB pattern in
[test_player_base_stats_mysql.py](../../tests/async/test_player_base_stats_mysql.py)
can support component tests with `--no-defaults`, task-owned datadir/socket/PID/log
and a small buffer pool. Real SQL journeys additionally need a dedicated loopback
listener and fresh database. This can be adapted without root or a permanent
service, but its current installed 11.8 engine does not qualify the two supported
fingerprints. Provision pinned supported engine binaries locally or use the
established compatible test environment; do not test against the production DB.

**Full network-isolated gameplay qualification is currently an environment gate.**
Issue #59 explicitly calls for the existing isolated/container approach. Docker
and new namespaces are unavailable to this login; host loopback/credential
separation is useful local progress but is not evidence of network isolation.
Before that gate, obtain an owner-provided disposable container/test environment
with the required isolation, or an explicit decision to revise that requirement.
Do not silently mark it passed or seek broader production privileges to bypass it.
All reducer/serializer/fault tests, documentation and local builds can proceed
independently. Planning itself does not require that environment to be created.

Run builds with low priority and bounded parallelism (initially `nice -n 10`,
`-j2`); serialize game/load fixtures. Host resource snapshots do not authorize
unbounded load alongside players. Full stress/fault testing belongs in the
isolated environment; only the separate cloud fixture receives the real project
token, after mock tests pass, with a hard total of 100 submissions including retries.

### Proof matrix

| Gate | Required executable evidence |
| --- | --- |
| Semantics | All eight native kinds; zero/applied/negative XP and threshold consumption; config/level/window/day boundaries; reconnect; checkpoints versus deltas; captured dimensions; identity stability/isolation; integer limits; late records; array overflow; no forbidden payload fields. |
| Native/output capacity | 256/257 resident sessions, 64/65 configs, full pending config FIFO, 128 pending closes plus 128 active runs, pending overflow/late terminals, run/actor/256-roster-event exhaustion and terminal bursts, queue/control reserve, bucket and JSON byte limits. Failures visible even when HTTP is healthy and queue empty. |
| HTTP | US/EU configured-host selection and invalid-host refusal; missing/invalid/role-mismatched environment refusal; valid batch, malformed row, permanent auth/config error, 413, 429 with Retry-After, 5xx, slow connect/response, cancellation, retry exhaustion/recovery and receiver-accepted/lost-response ambiguity. Frozen retry identity and bounded memory/work. |
| Quota/storage | Tiny allowance with reserved health, every attempted event counted, midnight crossing and clock rollback, restart/copyover, missing/corrupt/pending state, stale restore, writer contention, disk-full/fsync/rename failure, archive rollover and non-resetting reservations. Gameplay remains available. |
| Real gameplay | SQL and flat-file login, recognized action, idle/linkdead, combat and XP, level transition, groups/pets, save/reload, disconnect/reconnect, successful and failed copyover, shutdown and unknown crash tail. Assert captured payloads and conserved totals, not just helper return values. |
| SQL decoupling | Fresh supported schemas with the nine legacy tables intact, absent and drifted; unchanged gameplay drift rejection and immutable migration validation; SQL telemetry credentials absent/invalid cannot affect PostHog or gameplay. Flat-file binary has no telemetry SQL requirement. |
| Cloud/reports | At most 100 total tagged submissions, including retry cases. Query observed events, UUID/custom-ID duplicate behavior and all four report totals plus health. Exclude test identities from production views; wait only bounded time and report delayed ingestion honestly. |
| Performance | Repeated matched off/capture/mock-HTTP/real-HTTP fixture runs with ordinary saves; valid percentile math, CPU/RSS, native/reduced/event-attempt rates, serialized bytes, backlog, retries, journal bytes/publication/fsync time and complete monthly projection. No normal-load loss or sustained backlog. |

Performance acceptance retains the issue's ≤5% regression in pulse and save p99;
also measure command p99 and treat a >5% regression as a blocker. Use the existing
[operating gate](../../tests/async/session14_gate_manifest.json) bounds of pulse
p99 ≤250 ms, event p99 ≤25 ms, critical oldest ≤1,000 ms, zero sustained event
debt and zero gameplay-thread external I/O. The critical-oldest bound is not a
measured save-p99 SLA. Establish and record the explicit save/acknowledgement
absolute acceptance limit at **1,000 ms p99** for the representative fixture.
This is this plan's initial engineering gate, not a claim about an existing
production SLA; if the disabled baseline already fails it, investigate the
fixture/host and resolve the gate before rollout rather than quietly weakening it.
Preserve the proposed <0.5 ms
aggregate telemetry capture p99/pulse at 200 resident characters as a separate
capture-cost target, not proof that the 15-minute export fits that population.
Use enough samples/repetitions to distinguish a 5% change from shared-host noise;
insufficient evidence fails qualification. There is no arbitrary fixed soak time.

Commands to execute **during implementation**, not evidence already obtained:

```sh
./scripts/format.sh --check
nice -n 10 make -C src -j2 PERSISTENCE_BACKEND=mariadb BIN_ROOT="$PWD/bin/issue59/mariadb"
nice -n 10 make -C src -j2 PERSISTENCE_BACKEND=flatfile BIN_ROOT="$PWD/bin/issue59/flatfile"
python3 tests/async/test_telemetry_posthog.py
python3 tests/async/test_telemetry_config.py
python3 tests/async/test_telemetry_transport.py
python3 tests/async/test_telemetry_runtime_integration.py
python3 tests/async/test_telemetry_gameplay_adapters.py
python3 tests/async/test_telemetry_progression.py
python3 tests/async/test_telemetry_encounters.py
python3 tests/async/test_telemetry_combat_summary.py
python3 tests/async/test_telemetry_health.py
python3 tests/async/test_telemetry_outage.py
python3 tests/async/test_telemetry_runtime_outage.py
python3 tests/async/test_telemetry_runtime_exhaustion.py
python3 tests/async/test_telemetry_copyover_format.py
python3 tests/async/test_runtime_boot_compatibility.py
python3 scripts/validate_runtime_compatibility.py
python3 tests/async/test_data_lifecycle_manifest.py
python3 tests/async/test_telemetry_reward_projection.py
python3 tests/async/test_telemetry_balance_apply_contract.py
python3 scripts/telemetry/benchmark_272.py --workloads 50 200 1000 --repetitions 5 --output bin/tests/issue59-performance.json
```

Add affected connection/cloexec, session/activity, transport-fault and gameplay
hook regressions as their contracts change. The adapted SQL/flat-file journeys,
both supported-engine compatibility runs, representative performance comparison
and bounded cloud/dashboard assertions are additional required runs, not replaced
by the command list. Record their final actual CLI and environment selectors
once the harness is adapted; do not advertise the current SQL-only runner as a
working PostHog command. All compiled and generated artifacts stay under `bin/`.
Hosted CI is not a substitute for this local evidence or a merge prerequisite.

## Readiness, cutover and rollback

Before enabling, all gates above must pass; recheck billing usage/other senders,
prepare the identity key and explicitly initialized quota state, and load a
reviewed effective-property catalog for the deployed build. Current production
has no catalog configured. The five on-disk allowlisted property values match
the existing fixture (`0`, `10`, `1`, `0.20`, `0.15`), but that is not a live
in-memory measurement or a substitute for the full registry digest. Preserve the
catalog's stable mapping/collision rules; unknown properties refuse attribution.
Assign build/content/classifier/policy versions deliberately rather than leaving
every future deployment labeled `1`.

The implementation can generate the key, validate the catalog, initialize test
state, assemble the runbook and create the PostHog reports. The current missing
external capability is the required fully isolated supported-engine/gameplay
test environment. The save/ack budget and all other performance/volume limits
are acceptance decisions still requiring measurement, not verified host behavior.

After a separately authorized production deployment, set the reviewed opt-in
configuration through the established deployment procedure. Editing `.env`
alone does not update the running process, and copyover inherits its existing
environment unless the actual deployment path deliberately replaces it. Verify
the running process settings, local health, first queried synthetic/approved
events and production dashboard filters; do not assume a copyover applied them.

Rollback disables the exporter through that same controlled lifecycle and
preserves quota state, pseudonym key and outage evidence. It does not switch back
to the obsolete SQL writer or refund reservations. Stop on capture loss under
normal load, incorrect totals, privacy-contract violation, excessive host cost,
unbounded backlog, stale/corrupt budget state or billing risk. Historical data
remains available; there is no automatic replay of lost RAM payloads.

## Ablation and completion conditions

Keep the reducer, opaque identity, durable reservation, producer/journal health,
copyover identity repair, SQL boot decoupling and real report/gameplay proofs:
each addresses an explicit requirement or a traced failure. Reuse the queue,
worker, libcurl/cJSON/OpenSSL, existing protected publication and gameplay fixtures.
Drop SDK installation, a new service/sink abstraction, raw-event forwarding,
per-action cloud calls, SQL rollup repair, automatic balancing and a payload spool.
None is needed for the requested outcome.

Implementation is complete only when the compact contract and all five reporting
deliverables reconcile to executable synthetic evidence, both gameplay backends
pass their lifecycle/fault journeys, quota survives failure/restart, active SQL
telemetry dependencies are removed without weakening authority checks, the
measured complete event mix fits the free-tier targets, and gameplay/save
performance meets the stated gates. Passing serializer tests or an HTTP 200 is
insufficient. Production activation remains a separate owner decision.
