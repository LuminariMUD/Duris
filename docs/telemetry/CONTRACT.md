# Telemetry contract — version 1 (#260)

Status: implemented; telemetry is off unless `TELEMETRY_ENABLED` is set. This
document, the public headers and the golden fixtures change together. The telemetry
documents name each module by the number of the work item it was built under; the
list below maps the numbers to documents.

`STORAGE_DESIGN.md` preserves the complete published design. Its workload numbers,
SQL examples and table shapes are proposals, not measurements. The precise v1
rules below resolve its open representation choices. Budget proposals require the
separate #272 load/teardown gate before production approval. No production
telemetry, retention, account linkage or automatic balance changes are authorized.

## Ownership and build boundaries

- #260 (this document) owns the shared headers and fixture format. Consumers request
  amendments here rather than fork record types or change enum meanings.
- #261 ([DATABASE.md](DATABASE.md)) owns SQL schema, private connection, idempotent
  apply and immutable migration registration.
- #262 ([TRANSPORT.md](TRANSPORT.md)) owns the preallocated queue, sequential writer,
  retry and stop protocol.
- #263 ([CONFIG_CONTEXT.md](CONFIG_CONTEXT.md)) owns effective config identity and typed
  classifier policy snapshots.
- #264 ([SESSION_STATE.md](SESSION_STATE.md)) owns logical session/connection state and
  cumulative counters.
- #266 ([ACTIVITY.md](ACTIVITY.md)) owns pure activity evidence/classification and
  contextual interval splitting.
- #265 ([SESSION_LIFECYCLE.md](SESSION_LIFECYCLE.md)) alone owns gameplay/lifecycle hooks
  and shared build registration. #267 ([PROGRESSION.md](PROGRESSION.md)) owns the
  additive progression fact extension and the telemetry-only XP/level hooks in
  `world/limits.c`. #268 ([ROLLUPS.md](ROLLUPS.md)) owns external rollups; #269
  ([REPORTS.md](REPORTS.md)) owns report presentation; #270 is
  [REWARD_PROJECTION.md](REWARD_PROJECTION.md); #272 is
  [PERFORMANCE_GATE.md](PERFORMANCE_GATE.md); #273 to #275 are the rested-bonus study
  and the balance shadow policy and application under `studies/` and `balance/`.
- No new header includes game character, SQL, socket, mutex or filesystem types.
  Standalone compilation must work both with and without `__NO_MYSQL__`.
- Flat-file authority explicitly reports disabled/unsupported telemetry. There is
  no file sink, SQL fallback, dependency on telemetry for login/save, or fabricated
  healthy zero. An independent SQL endpoint would require a separate reviewed
  connection-role/configuration change.

## Units, identity and time

### Reporting scope reserved for PostHog (#59)

Preparation reserves `TELEMETRY_ENVIRONMENT_ID=1` for production, `2` for staging,
and `3` for the initial local development world. Match the configured environment
role, not the checkout directory name. Fresh isolated test worlds use distinct
non-production IDs starting at `1000`; never reuse an exported world's identity
for a restored or independently created world. Keep that identity stable across
reconnects, process restarts, and copyover within the same world.
Before export can be enabled, require an explicit nonzero environment ID and
validate its role: production `1`, staging `2`, local `3` or an isolated-world ID
at least `1000`. Missing, malformed or role-mismatched IDs disable export; the
current runtime's independent production-valued default must not reach the new
exporter. This validation remains required implementation work.

`TELEMETRY_SEASON_ID=1` starts the first PostHog reporting season; it does not claim
a historical game-wipe number. Change the season when a wipe/reset starts a new
character population, not on deployment or restart. Tag cloud test runs separately
and exclude their environment IDs from production dashboard queries.

These settings reserve reporting identities only. PostHog encodings and character
reduction are implemented; the exporter is not connected to the runtime yet. Setting either
variable does not enable telemetry. The SQL-specific sections below describe the
existing native path; this section defines its replacement export contract.

### Compact PostHog export schema 1 (#59)

The native record schema remains unchanged. Worker reduction produces six event
families, rather than forwarding native rows. These mappings cover all eight
native kinds:

| Native kind | External meaning |
| --- | --- |
| `interval` | Add deltas to `duris_character_summary`, retaining observed category and historical allocation. |
| `session_lifecycle` | `duris_session` with `transition` equal to `logical_entry`, `logical_exit`, `connection_attached` or `connection_detached`. Only logical entries count as entries. |
| `session_checkpoint` | Latest absolute counters/revision are reconciliation evidence on a later summary/lifecycle event. No periodic checkpoint event and no addition to interval deltas. |
| `coverage_gap` | Mark affected family coverage and coalesce bounded incident evidence into `duris_telemetry_health`. Process-wide unknown scope stays unknown. |
| `configuration` | `duris_configuration` once when first required or changed. Validate the complete fingerprint; do not repeat the full object on activity events. |
| `progression` | XP attempts reduce into character summaries. Observed level advance/loss emits `duris_level_change`. Threshold consumption is separate from awarded XP. |
| `encounter` | Start/join/leave maintain bounded state. Terminal `duris_encounter_summary` rows use `row_type=run` or `participant`. |
| `combat_summary` | Join player/pet contributions into terminal participant rows. Unsupported NPC detail is suppressed with accounting; no raw combat stream. |

Each sealed JSON row has `event`, `uuid`, an explicit UTC `timestamp`, and
`properties`. At batch level use only the capture project token (`api_key`) and
`batch`; the project ID is administrative metadata. Set
`$process_person_profile=false` in every row. `duris_event_id` equals `uuid`.
Generate UUID v4 once with OpenSSL randomness when sealing the row. Persist it
in the bounded in-memory serialized output; retry exactly those bytes, without
new IDs, timestamps, properties or reducer input. No payload spool is introduced.
For a duration summary the timestamp is its first known occurrence, so a fragment
ending exactly at midnight retains the day in which its time occurred. Explicit
occurrence bounds and allocation fields remain authoritative for reports.

Common properties are:

| Property | Representation / meaning |
| --- | --- |
| `duris_schema_version` | JSON integer `1`, independent of native schema. |
| `duris_environment_id`, `duris_season_id` | Nonzero unsigned decimal strings. |
| `duris_event_id` | Canonical lowercase UUID matching `uuid`; report deduplication key. |
| `duris_identity_key_version` | JSON integer `1`; rotation requires an explicit version/identity decision. |
| `duris_character_id`, `duris_session_id`, `duris_run_id` | Canonical identities below; null when not applicable or not captured. |
| `distinct_id` | Character pseudonym for character/player rows; pet actor identity for pet rows; scoped system/run identity for health/config/run rows. Never count these latter identities as characters. |
| `duris_config_id` | Captured unsigned decimal string, null only when no identity was captured. Missing metadata keeps the captured ID and adds missing-configuration coverage. |
| `classifier_version`, `policy_version` | Captured JSON integers, null when unavailable. Configuration events also carry build/content/property versions and the validated fingerprint. |
| `class_id`, `race_id`, `faction_id`, `level_band` | Captured JSON integers; null when unknown. Exact before/after levels are available only on progression. |
| `duris_quality_flags` | Native captured quality mask as a JSON integer. |
| `duris_coverage` | Bounded array of export coverage names listed below; empty only when no export coverage fault is known. |
| `occurrence_start_utc_usec`, `occurrence_end_utc_usec` | Signed decimal strings, or null when UTC attribution is unknown. Durations always come from monotonic observations. |
| `timestamp_basis` | `occurrence` or `emitted_at`. The latter uses a known sealing clock solely for transport, retains null occurrence bounds, and is excluded from occurrence-day totals. |
| `duris_test_run` | Null for normal data; bounded synthetic run identifier for cloud fixtures. Production reports require environment `1`, the selected season/schema and null test tag. |

Export coverage names are `native_gap`, `unattributed_time`, `unattributed_xp`,
`missing_configuration`, `counter_overflow`, `incomplete_terminal`,
`output_suppressed`, `unclosed_tail`, `occurrence_utc_unknown`, `late_fragment`,
`historical_dimensions_unavailable` and `unsupported_actor`. Emit each at most
once per row; retain scope-specific detail in bounded health counters. These
flags describe known evidence and do not certify a missing producer as healthy.
After local output suppression, subsequent sealed rows retain `output_suppressed`
as producer-lifetime evidence, using the existing cumulative loss counter. This
is global loss evidence, not a claim that every later character/window lost data.
Already-retained JSON remains immutable; resetting the reducer clears this scope.
`unattributed_combat` marks a retained run whose combined roster/player/pet
identity limit required keeping known contributions without actor attribution.

Identity encodings are implemented in
[`telemetry_posthog.c`](../../src/telemetry/telemetry_posthog.c) and independently
checked against [golden vectors](../../tests/async/fixtures/telemetry/posthog/encodings.json):

- `TELEMETRY_IDENTITY_KEY` is exactly 64 hexadecimal characters encoding 32 random
  bytes. Reject missing, wrong-length, nonhex and all-zero keys. It is independent
  of the project token, never exported/logged, and must be preserved privately
  through restart/restore. Parsing failure clears the output key; no raw-ID fallback.
- Character pseudonym: `dc1_` followed by 64 lowercase hexadecimal digits from
  HMAC-SHA-256. Its message is the ASCII bytes `duris:posthog:character:v1` with
  **no trailing NUL**, then environment, season and native subject ID, each as
  exactly eight unsigned big-endian bytes. The subject is the captured character
  identity, never the account. No decimal-string concatenation or native padding.
- Logical session: `ds1:<environment>:<season>:<boot>:<process>:<session_sequence>`.
  Run: `dr1:<environment>:<season>:<boot>:<process>:<run_sequence>`. Each component
  uses unsigned decimal without leading zeroes and must be nonzero. Retain the
  original session/run producer across copyover; the current exporter producer
  does not replace it. Maximum length is 108 bytes, plus a NUL in native storage.
- Health/configuration use scoped system identity `dh1:<environment>:<season>`;
  run-only rows use their run ID. A pet's `dp1_` pseudonym uses HMAC-SHA-256 over
  ASCII `duris:posthog:pet:v1` without NUL followed by environment, season,
  original run boot/process/sequence and native actor ID, all eight-byte unsigned
  big-endian integers. Pet rows also carry the owner's character pseudonym.
  These encodings are implemented; pet vectors are independently checked with
  Python HMAC, including each scope component and unsigned 64-bit maximum.
- UTC format is exactly `YYYY-MM-DDTHH:MM:SS.ffffffZ`, years 0001–9999, independent
  of the process timezone. Zero is the epoch, negative microseconds use floor
  seconds, and `TELEMETRY_UTC_UNKNOWN` is rejected. No clock value may silently
  become a server-assigned timestamp. Invalid encodings clear the output buffer.

All 64-bit IDs, XP values, counters, durations, revisions and UTC microseconds are
decimal JSON **strings**, including small values of these types. Signed values
have an optional minus sign; unsigned values never do; zero is `"0"`. This avoids
cJSON's double precision limit and keeps one type per property. Small enums,
versions, dimensions and masks fit JSON numbers. Unknown/unavailable values are
JSON null, never the string `"null"` or a fabricated zero. Reports must perform
explicit signed/unsigned integer conversion and deduplicate by `duris_event_id`
before summing. Live read-only literal/JSON queries in project `678214` on
2026-10-21 verified `toInt` for signed 64-bit values and
`accurateCastOrNull(value, 'UInt64')` for unsigned values. `toUInt64` is not a
supported HogQL spelling; `toDecimal` cannot hold unsigned 64-bit maximum.
Use `accurateCastOrNull(value, 'Int128')` / `'UInt128'` before sums to avoid
64-bit aggregate overflow. Null/invalid inputs remain null. Count unavailable
inputs separately so an all-missing aggregate cannot appear as a measured zero.
These [supported conversion functions](https://posthog.com/docs/sql/clickhouse-functions)
were checked with the following queries; actual ingested-property/dashboard
round trips remain a separate cloud acceptance gate:

```sql
SELECT
    toString(accurateCastOrNull(
        JSONExtractString('{"v":"18446744073709551615"}', 'v'), 'UInt64'
    )) AS unsigned_max,
    toString(toInt(JSONExtractString('{"v":"-9223372036854775808"}', 'v'))) AS signed_min,
    toInt(JSONExtractString('{"v":null}', 'v')) AS unavailable,
    toInt('invalid') AS invalid
-- 18446744073709551615 | -9223372036854775808 | NULL | NULL

SELECT toString(sum(accurateCastOrNull(v, 'UInt128'))) AS unsigned_sum
FROM (SELECT arrayJoin(['18446744073709551615', '1']) AS v)
-- 18446744073709551616

SELECT toString(sum(accurateCastOrNull(v, 'Int128'))) AS signed_sum
FROM (SELECT arrayJoin(['-9223372036854775808', '-9223372036854775808']) AS v)
-- -18446744073709551616
```

Character summaries retain connected/active/idle/unknown/linkdead and resident
microsecond deltas; `connected = active + idle + unknown` and
`resident = connected + linkdead`. They also retain requested/computed/applied XP,
attempts and zero-applied attempts. Absolute checkpoints/revisions stay in a
separate reconciliation object; missing detail is not attributed to a guessed
dimension or added again to the observed totals. Observed XP is not committed-save
authority. Before/after levels and threshold XP remain separate level-change data.
An unknown level endpoint (`0` in native records) is JSON null, including on
level-advanced/lost rows; known endpoints remain JSON numbers.

Within a summary, retain at most 32 time-allocation buckets keyed by captured
class/race/faction/level-band/zone/group-size/activity context and 32 XP buckets
keyed by captured class/race/faction/level-band/zone/group-size plus
source/reason/modifier mask/observation status. Seal affected data on known
character-dimension, config, classifier/policy
or exact observed-XP-level changes, including a change within one level band.
`xp_observed_level` applies to XP observations only; it never invents an exact
level for time intervals. Unknown context dimensions stay unattributed within the
fragment, without triggering extra periodic rows. If any character dimensions
are unknown, summary-level character dimensions are null with explicit coverage;
known time/XP allocation buckets retain their own captured dimensions. Preserve time and XP arrays
independently; expanding both in one report join would multiply their totals.
Overflow adds known values to explicit unattributed totals and marks lost detail.
Checked-arithmetic overflow makes that metric unavailable with overflow coverage;
never wrap, round or invent a zero.
Known overall totals remain available if only a signed allocation bucket
overflows; that bucket becomes null with overflow/attribution coverage.

Unknown and known exact XP levels also form separate fragments; a later known
level cannot label earlier observations whose level was unavailable. Direct
lifecycle and level-change rows flag missing historical character dimensions,
as do rows carrying the native unknown-dimension quality flag.

A configuration enters the materialized cache only after its JSON row is
retained in output. Event/byte pressure or JSON allocation failure leaves it
unpublished; dependent rows retain missing-configuration coverage and a later
publication of the same fingerprint can retry. Input sequence gaps include a
missing prefix before the first consumed record, since producer sequences start
at one.

The reconciliation object includes the latest checkpoint revision/time/quality,
absolute counters, observed counters through that checkpoint, and a separate
missing-detail difference only when comparison is valid. A logical entry must
have been observed by this producer; a post-copyover/reconnect checkpoint does
not establish a zero baseline. Detail delivered after the checkpoint but before
sealing updates its observed comparison. Stale revisions cannot regress it;
conflicting/nonmonotonic totals are refused with local coverage counters.

There are 256 session slots, at most two retained window fragments per session,
64 complete configuration identities, 128 active encounter runs and a separate
128 pending terminal joins, each retaining at most 64 actors. A terminal run
waits for its participant/combat evidence and a captured native-queue fence, or
closes after 120 seconds with explicit missing coverage. If pending capacity is
full, finalize its oldest known prefix early with incomplete-terminal coverage
before accepting another close; later evidence is explicit late loss. Pending
joins do not consume the active-run allowance. Test both bounds simultaneously.
Unavailable encounter character/session dimensions remain null; do not look up
the current character. Run duration and participation are distinct. Pet and player
contributions remain separate, and unwired control effects remain null.
The encounter reducer consumes native close, roster and combat rows across
separate drains. Expected combat arrivals include unsupported NPCs: count their
terminal revisions before dropping their identities/details. A close and complete
roster alone cannot certify combat completion. `native_terminal_complete` means
the locally observed start, close, roster and all declared combat revisions are
present without a terminal conflict; it makes no claim about cloud delivery.
Run mode merges captured evidence: the native roster can become mixed while
combat retains its initial PvE/PvP classification. A later initial-mode combat
row cannot regress an already observed mixed run.

Run rows contain `run_elapsed_usec`, `expected_reward_credit_count`,
`roster_expected`/`roster_received`, `combat_expected`/`combat_received`,
`native_dropped_actor_attempts`, `unique_player_count`, `unsupported_npc_rows`
and `participant_rows_expected`. Reward membership is separate from participation.
The native dropped-actor count records refusal attempts, not distinct actors.
Count durations/outcomes on run rows, and contributions on participant rows.
`participant_rows_expected` permits detecting output or ingestion loss even if
the run arrived. Every participant retains null character dimensions/session ID
with reason `not_captured_in_native_encounter`; no current-character lookup occurs.

Participant rows have `actor_kind=player|pet`, `duris_actor_id`, optional
`duris_owner_character_id`, nullable `participant_usec`, and nullable `combat`.
`participant_time_basis=terminal|observed_lower_bound` distinguishes a complete
participant summary from known cumulative leave effort retained after terminal
loss. Rejoins/repeated leaves never add absolute cumulative observations twice.
Player IDs use the character pseudonym; pet IDs are run-scoped pseudonyms, with
the captured owner's character pseudonym. Pet totals never enter player totals.
The combat object contains decimal-string damage, healing, casting counts/time
and tanking time, with `control_applications=null` and reason `not_instrumented`.
Captured power bands, opponent count and modifier flags are separate properties.
Native cardinality/saturation flags mark counters as lower bounds; checked reducer
aggregate overflow instead becomes null with `counter_overflow` coverage.

At most 64 combined player/pet identities are retained per run. If the union of
native roster and combat actors exceeds this, run-row
`unattributed_player_combat`, `unattributed_pet_combat`,
`unattributed_player_rows`, `unattributed_pet_rows` and `unattributed_roster_usec`
retain known overflow contributions separately. Add these only to the corresponding
participant totals, once per run; they are not all-actor run totals. Missing
combat/time evidence is null, not a fabricated zero. A terminal orphan preserves
known combat/outcome/duration, with incomplete coverage and no invented roster.
An open run remains open despite silence; forced lifecycle sealing marks its
unclosed tail without inventing an end, duration or outcome.

Terminal assembly waits at most 120 seconds from its first terminal observation.
After the admitted-tail fence, complete runs serialize incrementally across
output drains. A cursor prevents resealing the already immutable prefix; capacity
at the deadline explicitly suppresses remaining rows. Finalized IDs use 128 exact
tombstones and an evicted sequence prefix to prevent late data becoming a second
run. Existing older active runs remain valid. An unseen orphan older than that
prefix is conservatively refused and counted as late loss because bounded state
can no longer distinguish it from a replay. Native runs close before copyover;
new run IDs must belong to the current native producer, while session IDs retain
their original producer across copyover.
If a native lifecycle exit is lost, 3,720 seconds of complete input silence for
that session seals retained data with unknown-tail coverage and releases its
slot. This combines the maximum native cadence and queue allowance; it invents
no logout or logical entry. Later data retains the same logical identity while
checkpoint comparison remains unavailable without a locally observed entry.

Initial export windows are 900 seconds (1800 when the full measured mix requires
it), split at UTC midnight and required lifecycle/config/level boundaries.
Consume native rows once through the admitted-tail fence before timer sealing.
An older row arriving after sealing creates a new uniquely identified partial
fragment, coalesced until the next flush; it cannot mutate an immutable retry.
Every known-window seal advances this boundary, including eviction, forced/aged
flushes and version changes, as well as completed timer windows.
Unknown UTC retains monotonic totals as unallocated evidence. Extra fragments
count toward both loss reporting and the volume budget.
Per-record splitting is bounded to 64 windows. An extreme interval extending
farther retains its remaining duration in `unattributed_time`, with unknown UTC
and explicit coverage rather than looping over unbounded calendar history. This
is a fault bound, not a substitute for splitting ordinary intervals at their boundaries.

Serialized output, including retries, is bounded by 128 events / 512 KiB total,
32 KiB per event, and a 120-second maximum age. Batches contain at most 64 events /
256 KiB and flush within two seconds after sealing. Suppress with coverage when
count/bytes/age/quota cannot retain output; continue draining native capture.
Keep consumed/reduced/suppressed/attempted/HTTP-acknowledged counts separate.
HTTP acceptance does not prove query-visible ingestion.
The character reducer exposes worker-only output views; appending preserves
them, while retirement, expiry and reset invalidate them. The sender must resolve
its immutable retry prefix before these operations. The packed 512 KiB arena
reserves 512 bytes for batch framing and counts terminating NULs; there is no
second retained event buffer. Scratch JSON construction is separately bounded
by bucket counts and the 32 KiB serializer cap. Known native gap counts/durations
are saturating lower bounds; zero known duration never certifies an empty gap.
Hourly/incident health export and runtime HTTP/quota integration are still
pending. Current component tests do not prove ingestion.

### Complete event-volume fixture (#59)

[`volume.json`](../../tests/async/fixtures/telemetry/posthog/volume.json) is a
declared 31-day workload oracle, **not measured player capacity**. It includes
all six families, two percent additional detached residents, lifecycle edges,
extra boundary summaries, encounters, configuration, health, retries and the
entire 100-attempt cloud fixture. Its assumptions are explicit: three logical
entries and one reconnect per average connected character/day, two extra summary
boundaries per character/day, one level change and one encounter per two
character-days, six terminal rows per encounter (run, four players, one pet),
two copyovers, two configuration rows/day, hourly health plus four incidents/day,
and two percent retries on game traffic. Cloud test attempts are already inclusive
of their retries and are not charged twice in this forecast.
Each logical login/logout emits two lifecycle rows (entry and exit). Each
reconnect emits two additional rows (detach and attach); normal entry/exit does
not also emit attach/detach rows. Copyover adds its retained-session attach row.

| Average connected | Window | All submissions / 31 days | ≤450,000 target |
| --- | --- | ---: | --- |
| 50 | 15 minutes | 177,306 | Fits this fixture |
| 100 | 15 minutes | 353,563 | Fits this fixture |
| 200 | 15 minutes | 706,077 | Fails |
| 200 | 30 minutes | 396,454 | Fits this fixture |

The fixture does not establish a production window or daily burst headroom.
Actual emitted counts, late/boundary fragments, retry/fault rates and performance
must qualify the real reducer/gameplay mix. Retain the 20,000/day shared hard
ceiling, 100 reserved health attempts, explicit sender allocations, durable
pre-send reservations, and no payload backlog at exhaustion. Thirty-one days
can touch 32 UTC dates, so the hard bound is 640,000, not necessarily 620,000.
Full implementation, fake-receiver and ≤100-attempt cloud proof remain pending.

### Native record units and identity

All v1 durations and monotonic endpoints are unsigned **microseconds**; UTC
occurrence labels are signed Unix-epoch microseconds. This deliberately chooses
microseconds rather than the storage design's illustrative millisecond columns.
SQL uses corresponding unsigned/signed BIGINT fields. Never infer units from a
column name that omits the suffix. `TELEMETRY_UTC_UNKNOWN` is the sole unknown UTC
sentinel; zero UTC is a real epoch value. Ingestion time is assigned at commit,
never substituted for occurrence time.

A producer is `(boot_id, process_id)`, both nonzero incarnation tokens. `process_id`
is not an OS PID. Provision boot identity once at startup with collision checking;
assign process incarnation independently. Restored backups/test worlds require a
new environment identity. No per-event randomness/hashing is needed.

- Replay key: `(producer.boot_id, producer.process_id, record_seq)`; sequence starts
  at one, increases for each sealed attempted record, and is never reused after
  admission rejection. A retried immutable record retains its key and fields.
- Session key: original producer identity plus `session_seq`. It denotes one
  resident character session, not one accepted socket.
- Connection key: current producer identity plus `connection_seq`. Reconnect makes
  a new connection key, not a new session. All-zero means detached only where the
  payload permits it; partially zero identities are invalid.
- Subject, PID, environment and season are scoped at entry. PID must be positive;
  subject/season/environment identifiers must be nonzero. Subject is a restricted
  opaque character key, not a name, IP or raw account identifier. Environment and
  season distinguish reused player IDs and restored worlds. The contract does
  not claim historical account linkage or distinct-account reports.
- Sequence/revision exhaustion disables further observation for that incarnation;
  never wrap or silently reuse identities. Saturating diagnostic counters expose
  overflow; durations that cannot be represented are invalid, not wrapped facts.

Intervals are half-open `[start,end)` in one producer's monotonic clock. Positive
interval duration equals `end-start`. UTC clock changes never create negative or
extra elapsed time. Seal the current interval at an observed clock jump, mark
clock-discontinuity quality, and start a fresh reporting anchor. UTC endpoints may
move backwards; duration remains monotonic. Clock-ambiguous intervals are excluded
from exact UTC-day attribution, not forced into an invented day.

For a normal UTC midnight, split using the current stable monotonic-to-UTC anchor
and conserve duration exactly. This is deterministic mapping, not proportional
splitting across an unobserved clock jump. Unknown UTC keeps session duration but
cannot contribute to a known daily reporting bucket.

## Resident sessions, connections and classification

Enter occurs on actual gameplay entry. Link loss detaches the connection while
the live character remains resident. A reconnect attaches a new connection to
the same session. Actual quit/rent/camp/idle extraction ends the logical session;
a mere socket loss does not. End reason `disconnect` means eventual resident
unload after connection loss, not the detach event itself.

Successful copyover hands over the original session key, last checkpoint revision,
absolute counters and quality. The new process has a new producer and connection
key, and establishes a new monotonic anchor. No interval subtracts timestamps
from different process incarnations. Do not invent time spent outside observed
gameplay during handoff. Account through the old process cut, then use
`telemetry_runtime_session_handoff_copy` to export a bounded handoff. Its previous
producer is the current exporting process, not necessarily the original session
producer after multiple copyovers. The last allocated checkpoint revision includes
rejected admissions; zero means none has been sealed. Import with
`telemetry_runtime_session_resume`, preserving scope/counters/quality and seeding
the next revision after that value. It emits one `connection_attached`, not a new
`session_entered`; do not also invoke a separate attach. A bare connection transition
cannot restore absent runtime state. Failed/absent handoff leaves an explicitly unclosed old
session; the replacement creates a new one. Shutdown and crash behavior must not
require telemetry durability for gameplay teardown.

The exclusive cumulative accounting identities are:

```
connected = active + idle + unknown
resident = connected + linkdead
```

`unknown` here is connected time with unavailable activity evidence. It is not
unloaded time, missing context, queue backlog or an extra bucket added on top of
active time. Resident-linkdead intervals have no live connection key and contribute
only to linkdead/resident. Connected intervals belong to exactly one active, idle
or unknown category. Checkpoints carry absolute cumulative counters and strictly
increasing per-session revisions. They are never additive on replay.

Classifier v1 proposal: a connected player is active for the configured
`active_window_usec` after a recognized player-origin action or observed combat
participation. Default proposal is 300 seconds, bounded by one hour. Count accepted
movement, meaningful interaction/cast/use, communication and combat participation;
do not count empty/unknown input, protocol keepalives, queued-but-unexecuted input,
autonomous pet/room events or staff force as player evidence. Recognized actions
that fail downstream can still demonstrate input, but are not proof of productive
play. This is an observational heuristic, not a bot detector or reward rule.
The #266 module receives typed evidence from #265 and cannot reparse raw commands.
Evidence unavailable on attach begins unknown; actual observed evidence establishes
the activity window. After its expiry while connected, classify idle. Split exactly
at the activity deadline rather than marking the entire next pulse active.

Context uses a single descriptive category with documented precedence: combat,
travel, crafting, social, administration, other, none; unavailable is unknown.
Capture dimensions at observation time: level band, primary class identifier,
race, faction/racewar, zone, group size, config and classifier/policy versions.
Level bands are fixed five-level bands starting at level one; class/race/faction
IDs use explicit versioned mappings, not enum ordinals inferred at query time.
Secondary class and specialization analyses require a versioned extension rather
than silently overloading `class_id`. Group size zero means unknown, one solo.
Unknown level/class/race/faction is zero; unknown zone is -1, not a guessed room.

Meaningful level-band/class/race/faction/zone/group/config changes seal the current
interval. Same-zone room movement does not force a record. Per-player context
segmentation is capped per fixed monotonic minute from the process anchor. The
candidate default is eight segments, **including one reserved overflow segment**.
When another split would exceed the cap, aggregate the remainder as
`overflow_unknown` context with unknown attribution dimensions. Preserve known
activity/resident counters. Context overflow is not evidence that the player's
activity itself was unknown. Actual accounting can continue in bounded counters
without emitting every transition. Reset the cap on the next monotonic window,
not on each teleport, reconnect or property change.

## Record grains, validation and serialization

Public `telemetry_record` is a tagged trivially-copyable value bounded by 512 bytes;
that is an in-process queue limit, **not a native-layout wire format**. Zero-init
values, set the active union member and reserved fields explicitly. SQL binding
and any canonical fixture encoding serialize named fields, never struct padding,
uninitialized union storage or host endianness. Compare canonical typed content
for replay identity; bytewise `memcmp` of the native record is not the contract.
Unknown enum values/schema versions or nonzero reserved bits are rejected.
`schema_version` is the sole record compatibility version; there is no separate
unserialized record-version constant.

- Interval: immutable one-category elapsed segment, dimensions and quality.
- Lifecycle: logical enter/exit or explicit connection attach/detach, no duration.
- Checkpoint: absolute resident/connection counters plus revision and observation.
- Coverage gap: missing inclusive record-sequence bounds, known duration if any,
  dropped-record count and reason. Bounds zero/zero mean unknown, not empty proof.
- Configuration: immutable bounded effective snapshot admitted before any new
  record references its identity; uses the same finite control reserve.
- Progression: one observed XP storage fact or one level transition with bounded
  source/reason/modifier fields, mutable before/after snapshots, and explicit
  observation status. Level-threshold values are not reward/loss totals.

An all-zero session reference is allowed only for process-wide gap/config records.
Every other payload must identify its subject and scope. Partial identities are
invalid. Generic constexpr validation covers representation invariants; semantic
repository checks also validate scoped session immutability, cumulative monotonicity
and config content. Header validation alone is not full-record validation.
`telemetry_record_is_valid` and `telemetry_config_validate` share the same complete
configuration representation checks, including disabled bounds. The nonzero digest
predicate checks presence/shape only: #263 computes SHA-256 once on publication;
#261 recomputes and compares it on worker-side materialization before durable
acceptance. Queue admission never claims cryptographic verification and must not
hash each gameplay observation. Numeric dimensions are bounded by their field
widths with zone >= -1; mapping existence is a versioned semantic check.

## Configuration identity and publication

Config ID is immutable within the environment namespace. Revision orders local
publication; it is not a replacement for content identity. Store the fixed 32-byte
fingerprint of the versioned canonical typed effective config and build/content/
property/classifier/policy identity. Hash once on effective change, not per event.
Canonical encoding concatenates the following fields in exactly this order, all
unsigned big-endian integers of the specified bit width, with no delimiters:

1. `schema_version` (16).
2. `build_version`, `content_version`, `property_version`, `classifier_version`,
   `policy_version` (32 each, in that order).
3. `season_id`, `environment_id` (64 each).
4. `interval_usec`, `checkpoint_interval_usec`, `active_window_usec` (64 each).
5. `context_segments_per_minute` (32), `pulse_slot_count` (16), `backend` (8),
   `enabled` (8).

Exclude config ID, revision, `effective_utc_usec` (publication metadata), the
fingerprint itself and reserved/native padding. The digest is SHA-256 over these
bytes, stored as 32 raw bytes (fixtures render lowercase hexadecimal). Identical
effective values keep the same digest across publication times. No credentials,
hostnames, raw properties, paths or arbitrary JSON cross the capture boundary.
The property-version registry owned by #263 maps to a reviewed, allowlisted effective
property snapshot; never claim a process-local counter reconstructs historical config.

The game-side config owner copies/publishes state without SQL. It must admit a
configuration control record before attributing new intervals to that config.
Failure to admit degrades coverage; retry the same config identity. Retain bounded
cumulative counters but suppress dependent interval/checkpoint emissions until it
is admitted; retain gap diagnostics for later publication. Do not invent config ID
zero or attribute the missing segment to a stale config. Its historical context
remains unknown even when later checkpoints recover duration. The worker
materializes the config row before dependent facts. A missing config is explicitly
incomplete, never resolved by joining current live properties.

## Transport, thread and failure contract

There is one game-thread producer, one preallocated bounded RAM queue and one
sequential writer. Runtime capture/enqueue/pulse does bounded in-memory work only:
no SQL, file writes, fsync, pool acquisition, blocking locks or unbounded allocation.
The transport's writer pulse, repository apply/config and drain operations are
**worker-only**. A similarly named runtime pulse does not license calling writer
work from the game loop. Health is a synchronized cached value copy; readers never
walk worker-owned connection state.

Candidate limits are 8,192 records total, 128 control-reserved slots, 128 records /
64 KiB per batch and a two-second oldest-record trigger. The reservation is within
total capacity, not extra capacity. Detail stops before consuming it; lifecycle,
checkpoint, configuration and gap records may use it. Control can still be dropped.
Preserve producer FIFO order (and therefore within-class order) and never overwrite
worker-owned records. A first-seen replay key advances that producer's sequence;
retries may revisit the same key unchanged. Repository tests may deliberately
submit a conflicting payload to verify rejection. These are versioned
upper-bound proposals, not outage-duration guarantees.

Admission success means retained in RAM, not durable. Drop new detail/control on
saturation; retain bounded gap counters/ranges for subsequent reporting. Where
noncontiguous losses cannot fit bounded metadata, aggregate a conservative gap
with incomplete coverage rather than claim every sequence in a broad span was lost.
Process death before gap publication leaves an unknown tail. No durable spool.

The writer owns one verified private connection, never the game handle or gameplay
pool. One unresolved transaction at a time. Roll back or reconcile an ambiguous
commit before issuing a later batch. Retrying keeps keys and payloads unchanged.
Configuration materialization is internal to `telemetry_repository_apply`: the
config row and keyed configuration fact commit atomically in that batch. There is
no public keyless `apply_config` entry point. Apply result semantics:

- identical duplicate: no-op; differing content at the same key: conflict.
- older checkpoint: retain the immutable observation but do not regress projection.
- newer checkpoint: require nondecreasing counters and immutable session scope.
- same session revision with different totals: conflict even under another record key.
- retryable/ambiguous batch: retain unchanged, with bounded backoff/catch-up rate.
- invalid/conflicting rows: bounded isolation and diagnostics; do not blanket-ignore
  constraints or permanently block every valid row behind one malformed record.

`request_stop` is nonblocking. #265 owns the thread handle in a process-lifetime
coordinator: initialize the queue, start one worker (repository init and all SQL
run there), request stop, let that worker drain within the approved connector
policy and publish stopped, then join OFF the game thread. Transport init does not
spawn a hidden thread. The coordinator retains state through join and then calls
repository/transport/runtime shutdown. Cached stopped health is not a substitute
for join. No additional join API is needed because the coordinator owns the handle.
Shutdown/destruction is legal only after the worker
has exited and ownership has been joined safely. A SQL timeout does not prove
bounded connector cancellation. #262/#272 must demonstrate teardown or report a
blocker; never detach a thread touching freed state or run an unbounded game-thread
join. Telemetry must not veto valid game shutdown because observations were lost.

## Six-table logical schema and first reports

#261 finalizes physical SQL and indexes within these frozen logical grains:

1. `telemetry_session`: projection keyed by environment/season plus stable session
   key; immutable subject scope, latest revision/counters, lifecycle/completeness.
2. `telemetry_interval`: append-only **tagged fact stream**, not only duration rows.
   Store all admitted record kinds with an increasing ingest ID and unique scoped
   replay key. This resolves dedupe for lifecycle/gap/config/checkpoint records
   without a seventh dedupe table. Non-interval records contribute no interval
   duration. Use typed nullable columns by kind, not arbitrary payload JSON.
3. `telemetry_config`: immutable scoped config identity/fingerprint and typed fields.
4. `telemetry_player_day`: rollup-owned generation/definition/environment/season/
   UTC-day/subject/session contribution, duration buckets and attributable coverage.
5. `telemetry_cohort_day`: rollup-owned generation/definition/environment/season/
   day/level-band/primary-class/race/faction/zone/config/category sums and counts.
6. `telemetry_rollup_state`: definition/generation committed input watermark,
   publication status and coverage/rebuild metadata.

This explicitly refines the storage design's conceptual interval-only table: the
fact stream's record kind is mandatory. No gameplay foreign keys, new gameplay-row
counters, triggers, DB scheduler, partitioning or uncontrolled retention jobs.
The logical version and typed field mapping are shared fixtures, not SQL migrations.

First reports: (a) per-character resident versus connected active/idle/unknown and
linkdead totals, marked incomplete when necessary; (b) observed connected activity
and attribution coverage by the bounded cohort dimensions above. Report session
projection totals separately from sealed-interval coverage. A later checkpoint can
recover total duration after a drop but cannot reconstruct its lost zone history.
Do not sum every checkpoint or combine checkpoint totals with interval totals.

External rollup consumes keyset pages from a stable committed prefix produced by
the sole sequential writer; cursor and aggregate changes commit atomically. After
ambiguous rollup commit, reread the cursor before applying sums again. Versions and
rebuild generations are explicit; publish a new generation atomically, never
truncate tables currently served. No OFFSET scan or raw history query in gameplay.

Reports include input watermark, occurrence coverage, quality flags and provisional
status. No median from sums, average-of-ratios XP/hour, additive multi-day distinct
accounts, or claimed complete crash tail. XP/reward metrics are later extensions
with authoritative ledger reconciliation, not inferred from observational time.
Retention, deletion, archive, backup/restore and subject processing must be listed
by #261's lifecycle owner before operational activation; no purge is authorized.

## Versioning, verification and remaining work

Enums are append-only within a compatible version; changing meaning, units,
identity, grain or fingerprint encoding requires a new schema version and
new golden fixtures. H/K/P extensions get explicit bounded record kinds, not a
raw callback, string map or opaque payload escape hatch. Unknown versions fail
closed for telemetry only and never block ordinary gameplay persistence.

`test_telemetry_contract_headers.py` checks independent headers/layout, validators
and signatures without SQL/game runtime. Golden fixtures and their validator must
cover normal intervals, replay conflict, ambiguous commit, stale/new checkpoints,
dropped detail versus recovered totals, level/zone/config changes, midnight and
clock jumps, link loss/reconnect, copyover and unclosed crash tail. These are a
specification oracle, **not evidence that downstream implementations already pass**.

Run the focused checks from the repository root:

```sh
python3 tests/async/test_telemetry_contract_headers.py
python3 tests/async/test_telemetry_contract_fixtures.py
```

Shared fixtures live in `tests/async/fixtures/telemetry/contract/`. Downstream
implementations must consume the same cases through their actual boundaries; the
reference oracle is not a substitute for queue, repository or classifier tests.
The gameplay journey is `tests/async/run_telemetry_player_journey.py`.
