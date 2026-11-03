# PostHog free-plan strategy and implementation plan

- Issue: [#446](https://github.com/LuminariMUD/Duris/issues/446)
- Prepared: 2026-11-03
- Status: implementation active; report scope and cached diagnostics are the first
  review chunks. Production changes have not started.
- Branch: `branch/issue-446-posthog-free-plan`
- Local worktree: `/home/aiwithapex/projects/duris-issue-446-posthog-free-plan`
- Source baseline: `96ef0ed6b` (`origin/master` when this worktree was created).

## Decision

Keep all six existing event families, complete character/session/XP data, and
the existing 30-minute summaries. First establish the current sender and billing
facts and make the current season visible in reports. Do not raise limits or
sample players merely because the launch incident counted many native records.

At the reported current peak of roughly 20 players, the existing summary design
could fit very comfortably. However, peak players are not average resident
characters, and encounter frequency, participant/pet fan-out, summary boundaries,
retries, and other applications can dominate the bill. The low-volume fixture is
a useful comparison, not evidence that production fits.

If measurement proves reduction necessary, fix accidental duplication or excessive
fragmentation first. If valid routine PvE encounter detail remains the driver,
sample complete routine runs at the exporter, preserving rare outcomes and PvP.
Keep time, XP, logical sessions, levels, configuration, and coverage unsampled.
Choose the minimum reduction that meets the budget. Spending the full free
allowance is not a success metric; useful, representative coverage is.

**Outcome:** a $0 collection policy that answers population/return, playtime,
progression, encounter, and data-quality questions throughout the day, with a
measured margin for launch-sized traffic.

**Non-goals:** deployment or quota repair; new raw
combat/action streams; account linkage; gameplay or balance changes; a telemetry
service, SDK replacement, second writer, payload spool, or paid add-on. Preserve
the existing worker, reducer, queue, journal, and gameplay independence.

**Files:** this plan and `plan.md`; the five existing report SQL files,
`REPORTS.md` and their local SQL runner for the confirmed season mismatch;
`src/cmd/actinf.c` and its focused command regression for cached family diagnostics.
Other implementation owners below remain conditional on measured demand.

**Proof:** source tracing, read-only production configuration/log inspection,
official pricing checks, executable local reducer/sender tests, reproducible
budget arithmetic, and Git checks. Current cloud ingestion and Duris organization
billing remain unverified; they are explicit first-step implementation inputs.

## What the evidence establishes

### Implementation checkpoint — 2026-11-03

- The user confirms Duris is on the FREE tier and supplies production season 2.
  No capture or identity key is recorded in this plan or any committed artifact.
- Current read-only access checks again returned 404 for project 678214; the
  connected organization lists four other projects and no Duris project.
  A capture (`phc_`) key does not grant private reporting/billing API access.
  Requested the correct account connection while continuing independent work.
- Read-only production SSH still finds checkout `3c08535b3` and only the
  15:33:18 startup health line. It does not establish current sender counters,
  actual billing usage, ingestion or effective running scope.
- Ablation: retain all six families, 30-minute summaries and existing limits.
  Do not build a sampler, pacing controller or new storage while the excess is
  unmeasured. Expose the already-cached per-family/per-kind counters through the
  existing staff command, because the current command has only combined totals
  and cloud health is unavailable. This is a diagnostic gap, not evidence that
  any particular family dominates.
- Delivery order: publish the plan/handoff, stack the season-2 SQL/fixture fix,
  then stack the cached diagnostics with executable command coverage and builds.
  Each chunk will be committed, pushed and left in a focused review PR.
  Plan/handoff: [PR #629](https://github.com/LuminariMUD/Duris/pull/629),
  branch `branch/issue-446-posthog-free-plan`, head `04dd635c5`.
- Remaining acceptance: correct-account billing/query access; saved-query
  comparison/refresh under #578; comparable busy-interval and UTC-rollover live
  snapshots; measured family demand and organization headroom. Neither #446 nor
  #578 can close on the local scope fix alone. Production deployment, journal
  mutation, quota reset and new cloud capture campaigns remain outside this work.

### Report scope chunk

Branch `branch/issue-446-posthog-season2` is stacked on the plan PR. All five
committed SQL files now select season 2; environment/schema/test exclusions and
UUID deduplication are preserved. `REPORTS.md` records the current scope, explicit
historical querying, and the still-pending saved-cloud refresh under #578.
The existing embedded ClickHouse runner now uses season-2 native fixtures and
mixes independently identified season-1, other-environment, other-schema and
synthetic records into every report. This regression failed against the old SQL
(`AssertionError: activity`) before the scope change. No extra cloud campaign
or new report framework is needed. Validation passed:

```sh
PYTHONPATH=bin/tests/posthog-report-deps python3 tests/async/run_telemetry_posthog_reports.py
git diff --check
```

All five reports passed scope isolation/deduplication plus the existing rollback,
quota/capacity, recovered incidents, pet overflow, context/XP dimensions and late
checkpoint assertions. The installed dependency is local under ignored `bin/`.

1. **The issue describes an October 28 incident.** It reports 46,700 native
   admissions in about three hours, `EDQUOT`, and zero historical SQL
   applied/committed counters. These do not establish 46,700 outgoing events or
   zero HTTP delivery. Current source separates native consumption, reduced
   output, reservations, HTTP acknowledgements, and query-visible ingestion.
   Do not extrapolate the issue's admission rate into a PostHog invoice.
2. **Aggregation already exists.** `telemetry_runtime.c` selects 1,800-second
   windows. `telemetry_posthog.c` reduces eight native kinds to six cloud families;
   checkpoints and XP attempts do not each become an event. Runs emit one run row
   plus retained player/pet rows. Native encounters span their observed run
   lifecycle; a combat hit or NPC kill is not automatically a new exported run.
3. **`EDQUOT` identifies a local allocation refusal.** In
   `telemetry_outage_quota_reserve`, it means the requested batch cannot fit the
   normal, health, or combined allowance. Missing initialization returns
   `ENODATA`, a binding mismatch `EINVAL`, and clock rollback `ERANGE`.
   A season rollover or `exhaust-day` intentionally consumes that day's allowance;
   boot does not replenish it. A refused batch is retired with suppression or
   ambiguity evidence, not held until tomorrow. A batch can be refused while a
   smaller remainder still exists.
4. **Production has moved since the incident.** Read-only SSH inspection on
   November 3 at approximately 18:19 UTC found the production checkout at
   `3c08535b3`, telemetry enabled, project `678214`, environment `1`, season `2`,
   and limits `19,900 / 19,800 / 100`. This is checkout/configuration evidence,
   not proof of the running binary's revision or effective configuration.
   The current status file contained a healthy startup snapshot with zero counts
   at `15:33:18`; it did not provide a later sender/usage snapshot. Neither that
   startup line nor absence of later alerts proves current ingestion.
5. **The committed reports select the wrong season for that configuration.**
   All five files in `docs/telemetry/posthog/` select season `1`.
   [#578](https://github.com/LuminariMUD/Duris/issues/578) already owns comparison
   and reconciliation of saved reports. Coordinate the season-2 scope there,
   including activity; do not change the server's season to fit an old report.
   Saved cloud definitions were not accessible for comparison in this task.
6. **The current MCP connection cannot reach Duris.** Organization/project
   discovery did not list `678214`; selecting it returned HTTP 404. Its visible
   billing overview therefore cannot establish Duris usage, plan type, billing
   dates, or the $0 limit. No available cross-account connection tool was found.
   Do not use the unrelated organization's low usage as Duris headroom.
7. **Health traffic is already bounded and paced.** Commit `244b13a1e` (#281),
   also present in the inspected production checkout, spreads the 100 daily health
   attempts across the UTC day; ordinary unknown attribution does not create an
   incident. Reimplementing this or simply silencing warnings is not the fix.

Source owners: [contract](../telemetry/CONTRACT.md),
[outage and quota operations](../telemetry/OUTAGE_STORAGE.md),
[reports](../telemetry/REPORTS.md),
[runtime](../../src/telemetry/telemetry_runtime.c),
[reducer/sender](../../src/telemetry/telemetry_posthog.c),
[quota implementation](../../src/telemetry/telemetry_outage.c), and
[`world telemetry`](../../src/cmd/actinf.c).

## Information worth protecting

| Priority and question | Retain | Interpretation and decision supported |
| --- | --- | --- |
| Core: are characters playing and returning? | Every logical session entry/exit and connection transition | Character entries/returns and reconnect trouble. Reconnect/copyover is not a fresh logical entry. Characters are not unique people/accounts. |
| Core: are they actively playing, and where does time go? | Every 30-minute character summary; active/idle/unknown/linkdead time and existing captured allocation buckets | Active character-days, activity share, broad level/class/faction/zone/group patterns. Long sessions spanning midnight must count on each observed day, even without a fresh login. |
| Core: where does progression stall? | Requested/computed/applied XP, attempts, zero-applied counts, source/modifier buckets, all level changes | XP per observed active hour, progression pace and zero-reward patterns. Sum XP and time before dividing; observed XP is not proof of a committed save. |
| Core: can these conclusions be trusted? | Effective configuration changes, hourly/coalesced health, loss/freshness and quota evidence | Distinguish inactivity from missing coverage, changes in policy/build, and delivery outages. Local diagnostics remain authoritative when cloud health cannot arrive. |
| High value: what makes encounters succeed or fail? | Current run outcomes/durations and separate participant/pet contributions | Preserve PvP/mixed, death/failure and other rare/problem outcomes if routine PvE ever needs sampling. Separate run time, participant time, player damage and pet damage. |

Use the existing dashboard rather than creating a second analytics surface.
Add only report calculations the decision above actually needs: observed active
character-days and eligible day-1/day-7 return cohorts can use existing time/session
data. Label them **character retention** and **first observed this season**, not
new-account signup or player churn. Show cohort counts, observation coverage, and
right-censoring; exclude cohorts whose return window has not elapsed. Missing
telemetry days are unknown, not non-return days. No extra heartbeat is needed.

With a small population, prefer 7/28-day totals and broad cohorts over many daily
class/race/level combinations. Show numerator and denominator; label cohorts
under five observed characters as too small for a balance conclusion. This is
a presentation policy, not a reason to discard their data. Do not declare a
causal balance effect from observational XP/time or a few encounters.

All-counted data still has bounded loss. Preserve unknowns, coverage flags,
checkpoint reconciliation, lossless integers, UUID deduplication and historical
dimensions. Expand time and XP buckets independently. Keep HMAC identities scoped
to environment/season and `$process_person_profile=false`; no names, account IDs,
IPs, chat, command text, or precise room locations. A new season intentionally
starts a new character identity scope; do not promise cross-season retention.

## Free allowance and operating budget

Official sources checked November 3: Product Analytics includes **1,000,000 events
per month**. The allowance is organization-wide across projects, unused allowance
does not roll over, and billing periods need not start on the first of a calendar
month. A free account stops ingestion at its limit; a paid billing setup should
have a verified **$0 Product Analytics billing limit** for this objective. Data
over the limit is lost, not deferred. Reconfirm the actual Duris plan/period in
Billing before activation changes. [Pricing](https://posthog.com/pricing),
[analytics pricing](https://posthog.com/docs/product-analytics/pricing),
[billing limits](https://posthog.com/docs/billing/limits-alerts).

Replay, flags, logs, surveys and other products have separate meters. They cannot
be repurposed as extra gameplay-event allowance. No such product is required here.
Inventory enabled products for the $0 objective; do not enable them just because
they advertise free usage. Free event retention is currently one year; multi-season
archives are a separate requirement, not a new export service in this plan.

Preserve the existing Duris controls:

- **Hard production ceiling:** 19,800 normal plus 100 health submissions per UTC
  day, 19,900 combined. Every event in every retry reserves allowance before HTTP;
  batching reduces requests, not event count. Count ambiguous attempts without a
  refund. Runtime validation caps production at these values, and the journal
  binds the limits: increasing an environment value alone is not a valid change.
- **Tests:** at most 100 total cloud-test submissions across the declared campaign
  allocation, including retries; all other development/staging traffic uses local
  mocks. Do not treat this as 100 per restart or new worktree. Reuse the existing
  completed cloud campaign rather than run another one for report changes.
- **Normal target:** retain the existing ceiling of 450,000 combined Duris
  submissions per 31 days and projected organization analytics **below 700,000**
  per actual billing cycle. Count all other applications, website autocapture,
  duplicate client/server capture, test traffic and every sender in that org.
- **Initial operational warning:** projected normal submissions above 14,000/day,
  sustained retry amplification above the fixture's 2%, any unexplained loss, or
  organization projection at/above 600,000 calls for investigation. These are
  proposed review thresholds, not new automatic drops. At 14,000 normal/day plus
  the full health reserve and 100 test attempts, 31 days total **437,200**.
- **Daily early warning:** warn before 80% of the normal allowance (15,840) is
  reserved, and whenever the observed rate predicts exhaustion before UTC midnight.
  PostHog's own 80%/100% allowance alerts are a backstop, not early enough to protect
  the day's remaining gameplay coverage. Reuse existing health/reporting paths.

A 31-day billing interval can touch **32 UTC dates**. The conservative existing
combined allocation gives `20,000 * 32 = 640,000` submissions; production alone
gives `19,900 * 32 = 636,800`. The 640,000 bound does **not** guarantee the shared
700,000 target unless other org usage is below 60,000. Conversely, the normal
450,000 target leaves roughly 250,000 for other usage before that target is hit.
State which bound a forecast uses. The local journal cannot police another app.

Use the actual remaining billing allowance when commissioning mid-cycle:

```text
remaining_organization_target = 700,000 - billed_usage_to_date
remaining_Duris_budget = max(0, remaining_organization_target
                               - forecast_other_usage_to_period_end
                               - planned_remaining_test_attempts
                               - 25,000 uncertainty_reserve)
```

The 25,000 is a proposed extra forecast cushion, not a vendor limit. Subtract
already reserved/ambiguous Duris attempts that billing has not yet reflected so
ingestion lag is not mistaken for headroom. Use this result, the normal 31-day
target, and the daily cap together; the tightest constraint wins. If unknown
other usage prevents establishing headroom, keep the existing limits and resolve
the account evidence before authorizing more collection. No monthly budget
service is needed: the existing daily cap, billing limit and reviewed forecast
are sufficient unless real usage disproves that approach.

## Capacity model: population is only one input

Model **emitted rows and attempted submissions**, not native queue admissions:

```text
forecast_unique_output = periodic_summaries + required_boundary_fragments
                       + lifecycle_rows + level_change_rows
                       + sum_over_runs(1 + retained_player_rows + retained_pet_rows)
                       + configuration_rows + health_rows
forecast_submissions = forecast_unique_output + additional_event_attempts_from_retries
organization_usage = Duris billable ingestion + every other producer in the org
```

This forecasts delivering the whole chosen mix. For actual usage, use sender
submitted-event counts, durable reservations and billing separately: rows refused
before HTTP are not submissions; reservations may exceed submissions. Lost
acknowledgements do not prove non-ingestion, and every retry attempt still counts
against the local allocation.

For periodic summaries, use observed resident character-hours (including linkdead
residents) divided by the 0.5-hour window, with short sessions, partial windows and
boundary fragments counted separately. Average concurrency is resident-hours/24;
peak concurrency alone cannot supply it. Measure group participation and pets per
run, not per connected player. For already-failed delivery, reconcile created and
suppressed rows by stage: suppression before creation adds unmet demand, while
expiry/suppression of an already-created row must not be counted twice. Received
cloud rows alone underestimate demand.

The existing [volume fixture](../../tests/async/fixtures/telemetry/posthog/volume.json)
assumes 2% detached residents (rounded up), three logical entries and one reconnect
per average connected character/day, two extra boundary summaries/day, one level
change and one run per two character-days, six rows/run, two copyovers/31 days,
two configuration rows/day, 28 health rows/day, 2% retries, and 100 test attempts.
Applying those unchanged assumptions with 30-minute windows gives:

| Average connected characters, all day | Estimated total submissions / 31 days |
| ---: | ---: |
| 5 | 12,300 |
| 10 | 22,034 |
| 20 | 41,500 |
| 40 | 80,434 |

These are **synthetic scenarios**, not measured consumption. Twenty as an average
is deliberately more demanding than twenty as a brief peak, but is not an upper
bound when linkdead residency, churn or encounter mix differs. Halving population
does not halve fixed health/configuration traffic or outage retries.

Sensitivity illustrates why run counts matter. Hold 20 average connected, 21
residents, two boundary rows/character/day, eight lifecycle rows/character/day,
ten levels/day, two configurations/day, 28 health rows/day and 2% retries. Replace
only the run assumption, with six rows/run:

| Runs/day across the whole server | Approximate submissions/day | Approximate submissions/31 days, plus 100 tests |
| ---: | ---: | ---: |
| 100 | 1,885 | 58,534 |
| 500 | 4,333 | 134,422 |
| 1,500 | 10,453 | 324,142 |
| 3,000 | 19,633 | 608,722 |

Sensitivity uses `(1,248 + 6 * runs) * 1.02` per day and omits the two monthly
copyover attachment bursts; add those when forecasting a real period. At 40
average connected and 3,000 runs/day the same assumptions reach about 20,826/day,
above the hard cap. Larger groups/pet rosters reach it with fewer runs. These
examples demonstrate the variables, not an assertion about actual run frequency.

Changing 30-minute summaries to 60 minutes would save only about 504 periodic
rows/day for 21 residents, before retries, and none of the encounter rows. Keep
30 minutes unless measurements identify periodic summaries as the actual driver.
Do not change native capture/checkpoint/context cadence to save cloud events
without proving the reducer benefit and preserved attribution.

## Implementation sequence in this worktree

### 1. Establish current scope and a trustworthy baseline

This step can resolve the original incident without a sampling change.

- Obtain access to US project `678214` and its owning organization's Billing.
  Record plan type, actual billing-period boundaries, $0 analytics limit, total
  usage/projection, per-project usage and other producers. Use billing usage tools
  for billable totals and bounded event queries for family mix; do not use
  deduplicated report counts as a billing meter. Exclude separately billed product
  events when attributing Product Analytics usage. Keep raw account data private.
- Compare October 28–29 launch, October 30–November 2 settled days, and November 3
  partial day separately, with UTC windows and scope recorded. Extend to one full
  weekday/weekend cycle when available. Respect source retention and gaps; do not
  reconstruct missing records as zeros or wait a week to fix a demonstrated fault.
- Read effective `world telemetry` counters while the server runs: native consumed,
  reducer created/suppressed/expired/ambiguous/acknowledged, sender state and error,
  attempts/retries, durable quota day, normal/health reserved counts, and limits.
  Take comparable snapshots across a busy interval and a UTC rollover. Associate
  cumulative counters with producer identity and resets; never sum snapshots.
- Inspect per-family `output_by_family` and `native_reduction_by_kind` in health
  payloads. If cloud loss prevents access, expose these **existing counters** in
  `world telemetry` using the current cached snapshot. This is the only proposed
  diagnostic code addition; no payload logging or new collector. Add boundary-reason
  counters only if unexplained summary amplification cannot otherwise be located.
- Record resident/connected/active hours, logical session starts and reconnects,
  run rows and actor-row fan-out, level/config/required-boundary rates, restart
  frequency, retries, HTTP status and byte/capacity pressure. Where a dimension is
  unavailable, mark it unknown and use a bounded local fixture to test sensitivity.
- If `EDQUOT` persists, distinguish normal, health and total exhaustion from an
  intentional recovery/season rollover. Check prior reservations before assuming
  a startup failure. Verify first successful next-day reservation and subsequent
  queried events. Do not clear the journal or grant replacement allowance.
  If no current failure exists, document the historical incident and current
  evidence; do not manufacture a quota repair.

`scripts/telemetry/outage.py` and `telemetry-state` require the telemetry worker
to be stopped. Do not run them against the live owned ledger just to obtain a
baseline. Use cached live diagnostics first. Any necessary production repair or
stop remains a separately authorized operational step; preserve ledger/witness
and archives and follow `OUTAGE_STORAGE.md`. No production change is authorized
by this planning commit.

### 2. Make the existing data usable

Coordinate with #578: compare the five saved definitions on dashboard `2240639`
against the reviewed repository SQL, select the verified current season (`2` at
this inspection), and retain explicit historical-season querying. Update the
repository SQL and `REPORTS.md` together with any actual saved-view change.
Do not blindly overwrite saved queries or filter away evidence of missing data.

Keep environment `1`, the appropriate schema, test exclusion and UUID deduplication.
Add the limited activity/return calculations described above only after confirming
their observation and cohort semantics. Use already ingested rows or local report
fixtures. No capture campaign is needed. A report filter reduces neither sends
nor billing; it only changes what is shown.

### 3. Reduce only a measured excess

If complete settled-day demand, launch-sized stress and shared-org projection fit
the budget with no unexplained loss, **stop here with full-fidelity collection**.
An unused feature flag, sampler or new quota system is not required deliverable.

Otherwise act on the measured cause:

1. Fix a proven duplicate reduction/send, redundant seal, retry storm or faulty
   run lifecycle at its owning path. Preserve legitimate level/config/day/lifecycle
   boundaries, immutable retry IDs and necessary coverage. Keep supported retries
   and durable reservations; do not claim savings by refunding uncertain delivery.
2. If periodic summaries dominate, compare the existing 30-minute design with
   a validated coarser window. The reducer currently supports its declared window
   choices; a 60-minute option is a real code/contract change, not an assumed env
   toggle. Accept it only if useful savings justify reduced time resolution and
   retained-state/byte pressure still fits. Do not introduce adaptive windowing.
3. If valid routine PvE encounter detail dominates, apply **one deterministic
   whole-run selection policy** in the existing worker before output serialization.
   Select by scoped run identity, not player, row, time of day or outcome alone.
   Keep all rows of a selected run together under the selection decision; existing
   transport loss may still make delivery incomplete and must remain visible.

For that conditional sampler, retain all PvP/mixed runs and observed
death/failure/flee/abandonment/timeout/unknown/incomplete outcomes. Only complete
routine PvE success/withdrawal runs are initially eligible. Preserve all existing
session, time, XP, level, configuration and health events. Do not equate a run's
terminal outcome with a comprehensive death ledger for every participant; add
no unsupported claim about individual deaths. Validate mode/outcome classification
against actual native hooks before defining the eligible set.

Compute the eligible-run selection fraction from measured demand:

```text
p <= (normal_submission_target / measured_attempt_multiplier
      - mandatory_normal_rows_per_day) / eligible_routine_run_rows_per_day
```

Clamp to `[0,1]`, use a conservative high-activity estimate, and select the largest
simple fraction that fits both daily and billing-period constraints. Use one
fixed versioned policy for a measurement period, not an automatically changing
controller. If mandatory traffic alone exceeds the target, sampling routine runs
cannot solve it; re-evaluate scope and report that explicitly before rollout.
Allow margin for selection variance and large rosters; `p * rows` is an expectation,
not a hard burst bound. If no positive fraction fits, routine-run estimates cannot
be supported; do not publish `1/p` weights or pretend a zero sample preserves them.

Export selection probability and policy version on retained run/participant rows;
coalesce eligible/selected/omitted counts by the policy's bounded strata in existing
health evidence. Intentional selection is not a transport fault and must not
generate an incident for every omitted run. Distinguish selected-but-lost rows
from intentionally omitted runs. Update the encounter SQL and contract in the same
change. Never silently redefine existing exact counts: sampled estimates need
explicit probability-aware definitions and an export schema version if field or
grain semantics change.

Keep raw selected counts and weighted estimates separate. Weight a selected
routine run by `1/p`; protected strata have weight 1. Do not apply ordinary
unweighted success rates across those strata, inflate unique players with `1/p`,
or present rare-cohort/percentile estimates as exact. Sampling whole runs preserves
within-run relationships; it does not recover omitted detail or cloud loss.

Preserve the hard daily quota and health reserve as the final stop. If a measured
burst can still burn the day's allowance early, add only the smallest necessary
budget-aware admission rule to protect mandatory normal traffic from eligible
routine detail, using existing durable counts and explicit coverage. Do not design
a new scheduler before such a burst is demonstrated. Never increase limits to
mask an unmeasured producer or hide routine omissions behind midnight-only data.

### 4. Qualify, then commission through the normal deployment workflow

Candidate implementation files are conditional, not a checklist to edit all of
them:

- Diagnostics: `src/cmd/actinf.c`, existing cached health types only if necessary.
- A demonstrated reducer/sender change: `src/telemetry/telemetry_posthog.c` and
  `.h`; `telemetry_runtime.c` only for a necessary supported setting/integration.
  Leave quota format/state and capture hooks alone unless a traced defect owns
  the failure there.
- Queries/semantics: `docs/telemetry/posthog/*.sql`, `REPORTS.md`, and `CONTRACT.md`
  only where their current contract changes. Reconcile #578 rather than duplicate it.
- Extend `tests/async/test_telemetry_posthog.py`, its native reducer harness and
  `fixtures/telemetry/posthog/volume.json`. Reuse runtime/journal and report fixtures
  for affected boundaries. No separate forecasting service or test framework.

Required implementation proof:

- Verify the full emitted mix for measured current usage and a sustained
  40-character stress case, separately declaring average population, detached
  residents, session churn, boundary rate, run fan-out and retries. Include an
  encounter-heavy peak and outage/recovery burst; the old serial fixture is not a
  concurrent capacity test. Normal use must not rely on quota suppression to fit.
- Prove exact time/XP conservation, identity through reconnect/copyover, level and
  midnight boundaries, config publication, unknown coverage, separate pet totals,
  immutable retry UUIDs and no accidental duplicate reduction. If sampling is
  introduced, prove stable whole-run selection, protected strata, omission counts,
  probability-aware queries and byte/actor-bound overflow behavior.
- Prove daily reservations/retries, independent health reserve, UTC rollover,
  season rollover/exhaust-day, mismatch/corruption/clock refusal and unchanged
  bounded output/teardown. Extend focused tests only for changed behavior.
- Run `python3 tests/async/test_telemetry_posthog.py`; use
  `python3 tests/async/test_telemetry_runtime_integration.py --posthog` for runtime
  changes and `python3 tests/async/test_telemetry_outage.py` for journal changes.
  Report query changes use the existing local ClickHouse runner documented in
  `REPORTS.md`. C/C++ edits require `./scripts/format.sh --check` and `make -C src`,
  plus the affected flat-file path. Repeat applicable gameplay/performance journeys
  if capture/worker lifecycle changes; retain the existing <=5% pulse/save p99
  regression criterion. No blanket burn-in or CI wait.
- During separately authorized commissioning, observe a busy interval, one UTC
  rollover, and a representative multi-day/weekend sample. Confirm query-visible
  current-season events, family coverage and matching local counters. Allow for
  ingestion lag; HTTP 2xx is insufficient. Keep local and billing forecasts within
  the proposed targets and verify the $0 billing limit. Record limits of the
  observation rather than calling a brief test a month-long guarantee.

Rollback: restore the previous reviewed exporter policy/binary and matching
report interpretation through the normal deployment procedure. Preserve quota
day/counts, journal witness, season and identity key. Do not restore old quota
allowance with a binary rollback. If reliable collection cannot fit or delivery
is unhealthy, leave explicit coverage loss and use the authorized telemetry-off
path if needed; gameplay must continue. Retain old report definitions for old
schema/policy data rather than interpreting mixed versions as one population.

## Completion and ablation decisions

#446 can close after the current quota failure is explained/resolved (or shown
to be historical), useful current-season data is query-visible, daily/billing
headroom is evidenced for the chosen policy, and any intentional reduction is
visible and correctly interpreted. A mandatory reporting dependency must either
land via #578 or have its exact remaining gap stated; successful sending alone
does not prove a useful dashboard. This planning commit does not close either issue.

Kept: existing six-family analytics, source-level diagnosis, privacy, durable quota,
shared-org arithmetic, report scope repair, representative workload proof, and
conditional whole-run reduction. Each protects a stated analytical or cost outcome.

Simplified: reuse existing counters, dashboard, tests and quota journal; use a
fixed measured policy if needed. Do not build multiple reduction strategies at
once. No new abstraction is needed to produce the baseline or fix report scope.

Dropped from initial implementation: blanket player/row sampling, global event
disabling, quota increases, extra cloud campaigns, automatic adaptive budgeting,
unlimited catch-up/backfill, self-hosted PostHog, dual SQL export and new services.
They either lose critical small-population data, do not address the demonstrated
uncertainty, or add maintenance before a measured need exists.

## Planning validation record

- Read issue #446 and related #578/#59; traced current runtime/reducer/quota/report
  owners on the baseline above. Read-only production inspection did not alter
  files, services, quotas or gameplay. No saved PostHog entity or billing setting
  was changed, and no cloud capture campaign was run.
- `python3 tests/async/test_telemetry_posthog.py`: PASS on both MariaDB and
  flat-file compile variants with UBSan; 64 reducer semantic/capacity/fault cases
  and 33 loopback HTTPS/quota/cancellation cases per variant. The actual serial
  release mix emitted 97 rows, and all existing volume forecasts passed.
  This verifies the current baseline locally, not production ingestion.
- Scenario arithmetic was recomputed with Python using the committed fixture's
  rounding and retry rules; the sensitivity formula and 32-UTC-date bounds above
  were checked independently. No runtime implementation or full server build is
  part of this documentation-only change.
- Relative links and the scenario calculations passed the local documentation
  check. Final publication checks are `git diff --cached --check`, the single-file
  staged diff, and matching local/remote commit IDs after pushing this branch.
  Preserve all existing worktrees and their changes.
