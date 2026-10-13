# Log review: implementation and follow-up plan

Tracking issue: [#56 — Production follow-ups from the 2026-10-13 log review](https://github.com/LuminariMUD/Duris/issues/56).

Status: resumed at the owner's request on 2026-10-13 from `c8655bfbd`, on
`fix/58-56-estale-log-review` (started from `7a2a63447`). #58 qualification continues
from the saved checkpoint below before the remaining LR work.
The unchecked items below remain open until their required evidence is recorded.
Production operations are not part of this local-worktree execution.

LR-01 is implemented and locally qualified: 727 regression checks, 75 disposable
database checks, and 15 site tests passed on its source; the historical recovery
proposal is prepared and unapplied. [PR #66](https://github.com/LuminariMUD/Duris/pull/66)
was last verified open, ready for review, and unmerged on `fix/56-statistics-restart`
at `66dbfc016`. Other LR items remain open. `skeer` is explicitly skipped by owner
decision under LR-08.

Current continuation: #58 now has a passing full-server Summon Ghasts burst,
blocked-writer/copyover cancellation, writer recovery, successful copyover and
clean restart journey. Shared allocation-admission fixes `dfecafbda` and
`532fe0653` are committed/pushed and each has a passing before/after regression.
Remaining #58 cases and the source-audit findings are in
[the continuation evidence](plan-estale.md#continuation-evidence-2026-10-13).
These advances do not close another LR item or make #58 review-ready yet.

## Pause handoff

This records the earlier checkpoint; work is active again as described above.

- The work branch has uncommitted artifact/guild implementation and tests above
  `0ccec836e`. [plan-estale.md](plan-estale.md#pause-handoff) records the current
  code, passing focused checks, known gaps, temporary evidence, and exact next
  actions. The v2 history/memory/snapshot changes exist but are not fully qualified;
  no #58 acceptance item is complete. Keep this work off PR #66's review branch.
- After resumption, finish the #58 matrix and separate review, then continue
  LR-02–LR-20. LR-03's level-30 rule was selected in merged PR #55; its remaining
  work is teacher-command verification. The prior issue #56 update records LR-01,
  PR #66, and the `skeer` disposition; no additional LR completion is claimed.
- LR-01 validation and failure-before evidence remain under ignored
  `bin/analysis/lr01-validation/`; private recovery inputs and the unapplied
  proposal are in `bin/analysis/lr01-recovery/`. Preserve them before any cleanup
  of `bin/`. The LR-01 section below records commands, counts, commits,
  limitations, and recovery preconditions.
- No task test/build/disposable-database process is pending. The shared local/dev
  game and database remain running and may be used by another worktree. Use
  isolated tests and recheck runtime ownership before operational actions.
  No production repair, rollout, restore, backup change, or alert test occurred.
  Host-owner work remains open with its specific access/authorization requirements;
  the statistics assessment used read-only production access.

Prepared on 2026-10-13 against `master` at
`690ff313f3e3f115ef14b58612b0e302de2ce28d`, the current issue body and its scope-transfer
comment. The original production evidence covers **2026-10-12 22:25:09 through
2026-10-13 05:25:09 UTC**, from checkout
`1a529fa05c1af258b226258b6c9b48021e0908f8`. Counts and operational states quoted here
belong to that review; source inspection is not a fresh production health check.
The issue retains the private-log locations and timestamps; do not copy player
identities, addresses, conversations, credentials, or raw logs into this plan.

## Outcome, boundaries, and proof

Resolve every remaining #56 item with either a verified fix, an explicit gameplay
decision, or evidence that the investigated behavior is expected. Start with
statistics loss. Keep an unresolved report or missing host access open with its
specific next action; inability to reproduce once is not evidence of correctness.

Implementation uses the existing source owners, test harnesses, content import,
and backup tools identified below. It does not need a new persistence framework,
monitoring service, or test runner. Production repairs, imports, restarts,
configuration changes, and test alerts require their specific authorization.

Scope relationships:

- The 158 artifact transaction failures and artifact/guild reward consistency
  moved to [#58](https://github.com/LuminariMUD/Duris/issues/58). That transfer is
  not a fix. Keep its stale-capture, diagnostics, and exactly-once work there.
- [#57](https://github.com/LuminariMUD/Duris/issues/57) owns the reproduced PSP
  regeneration and movement over-cap defects. LR-07 must correlate the original
  movement report with that work, without assuming it proves the player's cause.
- The character-mechanics plan in [plan.md](plan.md), tracked by
  [#52](https://github.com/LuminariMUD/Duris/issues/52), is separate. These focused
  fixes do not depend on completing that project.

### Preserve memory authority

Follow [ADR 0002](../adr/0002-persistence-reset-memory-is-the-authority.md): live
character state is authoritative, saves follow capture order on the existing
writer, and the game loop does not wait for SQL. The ADR retains some durable
economy commands, including boons; the #58 branch narrows the artifact/guild
exception for epic-derived rewards. None of these commands authorizes adding
database approval to ordinary character changes.

The relevant failures have different causes:

- **Statistics:** `prepare_statistics()` captures live descriptors in memory.
  SQL and the daily file are outputs of that sample. The observed loss is in
  output identity/deduplication, not a reason to read gameplay state back from SQL.
- **Epic skills:** [epic_transaction.c](../../src/world/epic_transaction.c)
  changes the epic balance in memory and invokes the completion synchronously;
  its queued command records the ledger. A callback named `committed` does not
  mean training waits for a database commit. LR-04/LR-05 must preserve this path.
- **Artifact/guild rewards:** #58 documents pending captures sharing old state
  and SQL rejecting later rewards before completion publication catches memory
  up. That authority/ordering problem needs its own fix; do not fold it into
  statistics or add new revision fences here.

Proof must cover the real changed path: executable scheduler/repository checks
for statistics, command/callback and reconnect checks for gameplay, and observed
service or delivery results for host work. Source matches and configuration
values alone do not prove these outcomes.

## Work order and ownership

| Order | Work | Responsible role and dependencies |
| --- | --- | --- |
| 1 | LR-01 statistics | Server maintainer; isolate the failure before any historical recovery. |
| 2 | LR-02–LR-08 gameplay/help | Server/content maintainer; LR-03's level-30 policy needs command verification; LR-05 and LR-07 need reproduction. Other items can proceed independently. |
| 3 | LR-09–LR-11 lifecycle/connections | Server maintainer; preserve the existing guards, admission limits, and proxy trust rules. |
| Independent host track | LR-12–LR-15 and LR-20 | Host owner/backup custodian; access and specific production actions must be authorized. Prioritize restoring alert delivery before deliberately exercising backup failures. |
| Measured follow-ups | LR-16–LR-19 | Server maintainer plus tunnel/monitoring owner; change behavior only when measurement supports it. |

Record the assigned person when execution starts. These role assignments are not
claims that host work has already been requested or performed.

## Statistics

### LR-01 — Restart-safe statistics output (medium; #56 §2)

- [x] Write each logical sample exactly once to SQL and its daily file across
  retries/restarts; separately assess recovery of the 76 missing file samples.

**Execution, 2026-10-13.** The scheduler now allocates random 64-bit identities
outside the legacy low-byte namespace; its existing v4 state records them before
effects. No layout change, second queue, or database schema is needed. Retries
retain the entire capture; only cursor continuation prepares new values. Queue
delay and durable-state sync no longer consume the repository execution deadline.
The file append repairs only a matching partial row, checks the complete row on
replay, and retries syncs. State rename and daily-file creation both sync their
containing directory.
See the [runtime/recovery contract](../operations/CONFIGURATION.md) and
[regression evidence](../testing/REGRESSIONS.md#statistics-across-restarts-and-interrupted-output).

Passed focused commands: `python3 tests/async/test_maintenance_scheduler.py` and
`tests/async/with_disposable_mariadb.sh bash tests/async/run_statistics_mysql.sh`.
The latter is registered in `tests/run_db_tests.sh`; it checks SQL/file agreement,
all injected fault/restart cases, and actual legacy IDs in v2/v3/v4 state.
The scheduler test fails before the fix on changed captured values.
The server build and full-tree format check passed. The first broad regression
run passed 725/727: its wrapper-permission failure is repaired, and its flight
journey had completed gameplay before failing to count archived boot logs.
`81b8350e1` separately fixes that evidence collector. The final
`make test-all -j16 TEST_JOBS=16` passed all 727 checks in 700.33 seconds, including
flight evidence collection. `scripts/check_tests_catch.sh 81b8350e1 1e735655e`
confirms the scheduler regression passes after and fails before the repair.
The slow-state-sync regression also failed before the deadline adjustment and
passes after it. Output conflicts are refused with `EILSEQ`; first retry and
terminal failures log the opaque work ID and error. All 15 site tests pass.
`make test-db` passed all 75 isolated database checks in 459 seconds, including
the statistics matrix and MariaDB flight journey. LR-01 implementation is
`1e735655e`; `81b8350e1` is the separate flight-test correction. Validation logs
are retained under the ignored, owner-only `bin/analysis/lr01-validation/`
directory. No production rollout or historical replacement has been performed.
Review: [PR #66](https://github.com/LuminariMUD/Duris/pull/66), left unmerged.

**Historical assessment, 2026-10-13 16:47 UTC.** A bounded read-only production
transaction and a private copy of the original daily file confirm 1,007 existing
rows, all before hour 22, and all 76 reported SQL samples still present (28 in
hour 22 and 48 in hour 23). Both source timezone and proposed output mapping are
UTC. The private dry run under `bin/analysis/lr01-recovery/` retains `original`,
`proposed`, `samples.json` (SQL primary keys, timestamps and all counters), and
`assessment.json` (collection time and hashes), with owner-only permissions.
The proposal preserves the original bytes and adds 76 legacy-format rows,
bringing the total to 1,083. It invents no scheduler IDs: SQL primary keys identify
the source samples, and the existing file consumer accepts rows without a work
ID. An exact original-file hash is the application precondition; a changed or
already-repaired file must be refused rather than appended again. Scheduler IDs
cannot be reconstructed from SQL. This assesses only the reported interval,
not other possible historical gaps. No production file or table was changed;
replacement requires separate specific authorization and the retained original.

**Evidence and files.** The review found 76 SQL samples from 22:25:20–23:59:11
missing from the October 12 file, with all extrapolated work IDs already in that
file's last 8 KiB. Before the fix,
[maintenance_scheduler.c](../../src/persistence/maintenance_scheduler.c)
derived IDs as `(scheduled_tick << 8) | (job_id + 1)`.
The instance seed in [comm.c](../../src/net/comm.c) comes from listener ports,
so it does not supply a boot identity. The file check in
[maintenance_repository.c](../../src/persistence/maintenance_repository.c)
used only the work ID; SQL uses the latest high/low timer marker. Capture lives
in [maintenance_snapshot.c](../../src/persistence/maintenance_snapshot.c).

**Original implementation sequence (completed; evidence above).**

1. Reproduce two same-day boots with the same ports/tick schedule and distinct
   sample payloads, including the old IDs in the file tail. Exercise the actual
   scheduler, SQL marker, and file append path in disposable storage.
2. Replace tick-only identity with a restart-safe identity allocated once per
   new work item and persisted before effects. Reuse the scheduler's durable
   request/state path. Select and document the smallest allocation scheme that
   distinguishes new work from replay and cannot reuse legacy IDs under the
   supported restart/state-recovery contract. Increasing the tail scan or
   inventing a fresh ID on retry does not solve that contract.
3. Keep the captured timestamp and all 11 counters unchanged for the lifetime
   of a sample. Before the fix, `apply_completion_locked()` cleared the durable
   request, while `submit_due_locked()` invoked preparation again. A file failure
   after SQL commit must not retry the same ID with newly
   captured counters or a new date. This is an additional source-derived risk
   to reproduce, not a claimed observation from the production window.
4. Preserve acknowledged/pending completion recovery, cursor continuation,
   bounded worker execution, and the other maintenance jobs' marker semantics.
   If the durable layout changes, support the existing v2/v3/v4 state files and
   test the upgrade with pending requests/completions. Define handling of missing
   or invalid state explicitly. Keep SQL/file work off the game loop and preserve
   the daily file's consumer-facing columns and local-time date/hour convention.
5. After the fix is proven, compare a private copy of the affected daily file
   with the bounded SQL interval. Produce a dry-run recovery proposal with the
   missing rows, timestamp/timezone mapping, deduplication rule, and before/after
   totals. The current SQL insertion stores counters/date, not each work ID:
   establish recoverable identity instead of fabricating historical IDs. Retain
   the original file and require specific authorization before production
   replacement. Record a justified unrecoverable/ambiguous disposition if exact
   reconstruction is impossible.

**Verification.** Extend
[test_maintenance_scheduler.py](../../tests/async/test_maintenance_scheduler.py)
and add a focused statistics repository test using the existing disposable
MariaDB wrapper, registered in [tests/run_db_tests.sh](../../tests/run_db_tests.sh).
Cover fresh same-day boots; two distinct samples with identical counts; failure
before SQL commit; SQL commit followed by failed/partial file output; failure
after file append but before acknowledgement; repeated retry; restart with a
pending request/completion; and retry across local midnight. Compare per-sample
values and multiplicity, not just total counts. Test legacy file/state inputs
and ensure no new sample is lost and no replay produces an extra SQL/file row.
The existing scheduler harness alone does not prove cross-store agreement.

## Gameplay and help

### LR-02 — Epic boon eligibility feedback (medium; #56 §3)

- [ ] Show accurate completion/reward feedback below and at the epic gain gate.

[boon.c](../../src/economy/boon.c), `boon_publish_transaction_result()`, announces
completion before `gain_epic()` can decline a below-level award.
[epic.c](../../src/world/epic.c) already provides `epic_level_can_gain()` and
`epic_gain_min_level()`; the checked-in minimum is 50. Reuse those rules to explain
why a completed epic boon awarded no epics. Preserve boon completion semantics,
non-epic rewards, and the existing successful-award feedback; do not lower the
gate, reopen a consumed boon, or claim a persistence failure.

Extend [test_epic_level_gate.py](../../tests/async/test_epic_level_gate.py) with
the actual publication/award path, supplementing its helper/source checks.
At levels 49/50 and an overridden configured boundary, assert message, epic
balance, and completion state together. Cover a declined award without a false
success message and ensure the change adds no second reward application.

### LR-03 — Epic training minimum (medium; policy decision; #56 §3)

- [ ] Record the game owner's intended minimum, then align configuration, help,
  and teacher boundary behavior.

[PR #55](https://github.com/LuminariMUD/Duris/pull/55) selects
`epic.skills.minLevel=30.000` in [duris.properties](../../lib/duris.properties),
read by `epic_skills_min_level()` and enforced by `epic_teacher()` in
[epic_skills.c](../../src/classes/epic_skills.c). Refusal below 30 follows that
rule. The property, compiled default, [Ship Damage Control reference](../reference/SHIP_GAMEPLAY.md#ship-damage-control),
and [CODEBASE.md](../reference/CODEBASE.md#epic-point-and-epic-skill-levels) now
agree. Epic point gain remains separately gated at level 50. The teacher-command
journey below remains the focused follow-up for this plan.

Prove teacher behavior at minimum minus one, minimum, and minimum plus one with
otherwise eligible characters and sufficient funds. Refusal must spend nothing;
successful training must retain its class/prerequisite/cost checks. Extend the
level-gate test and run an actual teacher-command journey. Keep epic gain and
epic training thresholds independently configurable.

### LR-04 — Mastery completion feedback (low; #56 §3)

- [ ] Distinguish an intermediate improvement, the purchase reaching full
  mastery, and an attempt after mastery.

Change `epic_skill_purchase_committed()` in
[epic_skills.c](../../src/classes/epic_skills.c) using its resulting learned value.
It currently uses the same improvement message at every value, including 100.
Do not change the increment, cost, teacher cap, or purchase eligibility.

Extend or add a focused native teacher/purchase-callback harness: intermediate
gain, final gain capped at 100, already-mastered attempt, teacher-specific cap,
and refused purchase. Assert learned/taught values, one charge, and the correct
message; a repeat at mastery must change neither balance nor skill. Existing
[test_epic_skill_grant.py](../../tests/async/test_epic_skill_grant.py) checks
Chaos grants, so it is not proof of the ordinary paid-training path.

### LR-05 — Toughness HP refresh (medium; needs reproduction; #56 §3)

- [ ] Establish when training updates derived HP and correct the successful
  purchase path if the reported delay is reproduced.

The same purchase callback changes learned/taught values and saves without an
explicit HP refresh. In [affects.c](../../src/magic/affects.c),
`calculate_hitpoints2()` uses toughness, `balance_affects()` schedules a refresh,
and `affect_total()` rebuilds stats while preserving missing HP. Trace this
existing path before choosing the smallest correction. Do not call the HP
formula on top of already-derived values or make training wait for SQL.

Capture skill, epic/cash balances, max/current HP, pending refresh, prompt/GMCP,
and persisted state before purchase, at callback return, after the next event
pulse, and after reconnect. Cover full and injured characters, repeated
purchases/refreshes, declined purchases, and the Illithid HP branch where
applicable. Require correct derived HP on the next visible result, existing
missing-HP semantics, no cumulative bonus, and reconnect agreement. Use a native
callback test plus a save/load journey; document the observed timing if the
reported delay cannot yet be reproduced.

### LR-06 — Zone average sentinels (low; #56 §3)

- [ ] Identify the reported zone, validate catalog population, and render
  unknown/not-applicable averages without displaying a negative mob level.

[db.c](../../src/world/db.c) initializes `avg_mob_level` to -2;
[world_quest_policy.c](../../src/world/world_quest_policy.c) populates averages
and uses -1 for some zones without a usable population;
[actoth.c](../../src/cmd/actoth.c) prints the value directly. Reproduce the
zone-info command for the affected zone and distinguish a missing catalog
update from an intentionally absent average. Correct the population path only
if defective; render each sentinel appropriately without changing stored
sentinels or treating an unknown zone as level zero.

Use fixtures for a populated zone, a normal zone without qualifying mobs, an
uninitialized/special zone, and catalog refresh. Assert command text and that
the hazardous-level warning only compares real averages. Catalog-file validity
alone is not a test of this display.

### LR-07 — Movement drain/regeneration report (low; #56 §3)

- [ ] Reproduce the player's conditions or record a supported explanation;
  correlate any matching defect with #57.

Capture race/class/level, posture/status, terrain, carried load, movement mode,
effects, recovery properties, current/max vitality, actions, and elapsed pulses
and wall time. Compare `move_cost()` in [utility.c](../../src/core/utility.c),
`move_regen()` in [limits.c](../../src/world/limits.c), and actual callbacks in
[events.c](../../src/world/events.c), including entering/leaving combat.
The checked-in recovery dial is already neutral (`player.recovery=5.000`);
#57 records the prior dial's effect and the separate reproduced over-cap bug.
Do not undo event optimizations or change balance based only on the chat report.

Reuse [test_move_cost_runtime.py](../../tests/async/test_move_cost_runtime.py)
for cost cases, and add only the missing callback/timed journey coverage for
the reproduced condition. Record predicted versus measured drain and recovery.
If #57 explains the case, link its eventual fix and the matching reproduction;
otherwise retain this report's separate disposition and any needed owner decision.

### LR-08 — Missing help topics/aliases (low; #56 §3)

- [ ] Resolve `web-spray`, `quickstep`, and `seadog` searches.

Owner decision, 2026-10-13: skip `skeer` for now because its meaning is unknown.
Source/help searches found no matching ability or topic. Do not invent an alias;
this term is excluded from the current implementation, while the three named
topics above remain in scope.

Inspect the real abilities and current titles in
[help_index](../../lib/information/help_index) and
[duris_help_parsed.hlp](../../help/duris_help_parsed.hlp). The latter already
documents `innate web_spray` under Drider and mentions seadog; mentions inside a
page do not make a title searchable. Add the smallest accurate topic or redirect
using [HELP_SYSTEM.md](../content/HELP_SYSTEM.md) and
[HELP_STYLE_GUIDE.md](../content/HELP_STYLE_GUIDE.md). Check importer precedence
so a later source does not overwrite the entry.

Dry-run [import_help_to_prod.sh](../../scripts/import_help_to_prod.sh), then
exercise the selected topics through `wiki_help()` after an isolated import and
cache refresh. Check the flat-file help catalog too when changing shared source
content. Reuse the help parser/import/cache harnesses. Production publication is
a separately authorized import, verified by actual `help` queries.

## Runtime lifecycle and connections

### LR-09 — Scheduling an affect for a dead NPC (low; #56 §4)

- [ ] Identify and correct the caller scheduling after extraction; retain the
  scheduler's dead-owner guard.

The observed `event_short_affect` schedule was rejected, not a proven crash.
Trace `affect_to_char()`/`set_short_affected_by()` in
[affects.c](../../src/magic/affects.c) through the relevant combat/spell caller
and extraction. The rejecting guard is in
[new_events.c](../../src/world/new_events.c). Reproduce death/extraction during
the effect sequence and stop the invalid continuation at its owner, including
any affect/payload cleanup needed there. Add bounded caller diagnostics only if
the existing evidence cannot identify that continuation.

Extend [test_nevent_scheduler_runtime.py](../../tests/async/test_nevent_scheduler_runtime.py)
and [test_nevent_cancellation_runtime.py](../../tests/async/test_nevent_cancellation_runtime.py)
with the real producer sequence: live scheduling works, extraction cancels
owned events, the caller schedules no new work after death, and no callback or
payload survives owner reuse. A test that merely confirms `dead_owner` rejection
does not demonstrate the caller fix.

### LR-10 — Standing/resting inconsistency (low; #56 §4)

- [ ] Find the producing transition and keep posture/status consistent while
  preserving `stand` recovery of an already-invalid state.

[actmove.c](../../src/cmd/actmove.c) already normalizes wake posture and recovers
`POS_STANDING+STAT_RESTING`. The log shows the recovery worked; it does not name
the remaining producer. Trace commands, combat/effects, and restore transitions
that write position/status. Reproduce the complete transition before changing
it; preserve intentionally valid standing/sleeping states.

Extend [test_posture_state_regression.py](../../tests/async/test_posture_state_regression.py)
with that actual producer and subsequent rest/wake/stand behavior. Assert both
fields, movement/regen behavior, and recovery feedback. Keep the recovery test;
silencing its diagnostic is not a repair.

### LR-11 — Unauthenticated connection burst (medium; #56 §5)

- [ ] Demonstrate bounded connection resources and repeated-error logging while
  legitimate clients can connect and reconnect.

The review counted 2,001 pre-character disconnects from one address, with 27
concurrent-limit refusals, TLS failures, and write errors. Inspect admission,
timeouts, cleanup, and logging in [comm.c](../../src/net/comm.c),
[ssl.c](../../src/net/ssl.c), and [websocket.c](../../src/net/websocket.c).
The existing eight-connection limit is concurrent, not a rate limit. Establish
whether repeated sequential attempts still produce excessive CPU, descriptors,
worker state, or logs. Apply the smallest measured admission/logging correction;
any per-address state must itself be bounded and expire.

Extend [test_connection_limit_journey.py](../../tests/async/test_connection_limit_journey.py)
with sustained sequential churn and incomplete TLS/WebSocket handshakes. Record
attempt count/rate/duration, peak descriptors/memory, loop latency, and log
lines/bytes; assert finite limits tied to the chosen controls and state cleanup
after the burst. Verify another client remains usable and reconnect works after
the limit window. Retain shared-address/NAT, trusted-proxy, IPv6-prefix, and
authenticated website-service behavior. Coordinate host-log correlation with
LR-20; the original evidence does not establish compromise.

## Host operations and backups

Use the current [RUNBOOK.md](../operations/RUNBOOK.md) and
[BACKUPS.md](../operations/BACKUPS.md). Recheck deployed units/policy before
acting: historical deployment notes may predate the issue's observations.
Record redacted results on #56, keeping installed credentials and host-specific
configuration out of Git. Repository examples cannot prove a deployed service
works, and this planning task performs no production operations.

### LR-12 — Failed host log rotation (medium; #56 §6)

- [ ] Have the host owner identify the failed rule/hook and verify a subsequent
  successful `logrotate.service` execution.

The October 13 run failed with exit 1 at 00:57:16–00:57:20 UTC and has a Plesk
drop-in. The owner should inspect the protected journal beginning
`2026-10-13 00:57:00 UTC`, review the effective unit/rules and hook, validate the
correction, then observe the next authorized/scheduled rotation. Record the
specific cause, unit result, and evidence that the intended logs rotated with
correct ownership and services still writing. Resetting the failed flag alone
is insufficient. Do not conflate this host job with Duris's restart-time log
rotation in [cycle_mud.sh](../../scripts/cycle_mud.sh).

### LR-13 — Off-host backup replica (medium; #56 §7)

- [ ] Configure an actual remote replica and prove completed generations can be
  read and verified there.

The reviewed policy had `replica_root=null`. The custodian provisions the
supported SSHFS mount, remote account, host-key verification, permissions,
capacity/retention, and private policy. Reuse
[persistence_backup.py](../../scripts/persistence_backup.py) and
[backup_policy.example.json](../../scripts/backup_policy.example.json).
Verify generation publication and remote checksum/readback, then exercise an
authorized mount failure/recovery: failure remains visible, a local generation
survives, and replication resumes without duplication. Never substitute an
ordinary local folder for a disconnected mount. Record the remote failure
domain, generation ID, and verification result; couple an independent remote
restore to LR-14. Readback alone does not prove recovery after host loss.

### LR-14 — Isolated restore qualification (medium; #56 §7)

- [ ] Provision the restore filesystem, enable the selected drill interval, and
  complete a qualified restore with an observed drill receipt.

The reviewed policy had `drill_seconds=0`. Follow BACKUPS.md using a dedicated
mounted filesystem on a different device from live authority and backup storage,
within the policy's size/free-space limits. Use matching server/schema/verifier
artifacts and independently current erasure evidence; do not manufacture an
empty tombstone ledger or bypass a restore refusal. Run the existing isolated
restore/drill path with private authority and namespace isolation, including a
generation retrieved from the replica once LR-13 is available.

Verify checksum validation, database/flat-file reconciliation as applicable,
isolated readiness and clean shutdown, cleanup, and the recorded generation and
drill time. Observe the enabled timer and `status --require-drill`; that command
alone proves no drill requirement when the interval is still zero. Record
elapsed restore time and recovery-point age. Successful archive CRC/hash checks
from the original review are not restore evidence. No candidate is promoted.

### LR-15 — Backup failure alert delivery (medium; #56 §7)

- [ ] Diagnose exit 100 and prove an end-to-end failure notification reaches
  the responsible recipient, retaining delivery-aware rate limiting.

`OnFailure=` was connected in the review, but alert instances had failed before
the evidence window, on October 12 at 18:54:05. Inspect the deployed
`duris-backup-alert@...` unit, script, sender/recipient configuration, sendmail
exit, and protected mail journal with the owner. The installed alert script is
not one of this checkout's backup service templates; find the real command
before proposing a repository edit. Repair the diagnosed mail/configuration
problem instead of introducing a second alert system.

With explicit permission for the test, trigger a harmless controlled failure
through the real `OnFailure=` route and obtain recipient receipt. Verify failed
submission leaves no quiet-period stamp, a later attempt remains eligible, and
successful submission applies the intended quiet period. Submission success
alone does not establish receipt. Record which backup/health/drill units route
to it, and verify repeated failures do not create an alert storm.

## Monitoring and bounded investigations

### LR-16 — Tunnel interruptions (low; #56 observations)

- [ ] Correlate recovered edge interruptions with external health and client
  disconnect evidence; record impact or a supported monitoring-only disposition.

The review's ten interruptions recovered; it established no complete tunnel
outage. Compare connection IDs/timestamps with actual public probes and game
disconnects, plus later recurrence. Distinguish one edge reconnect from loss of
all usable connections. Reuse existing monitoring; adjust connection handling
or alerts only for demonstrated impact. Prove any change with the same measured
signals and an agreed observation window, and retain recovery timing in the
disposition even when no code change is justified.

### LR-17 — Lookup latency and event deferrals (low; #56 observations)

- [ ] Profile the 73.738 ms staff `lookup` and characterize the event deferrals;
  record a measured improvement or why no change is justified.

Use a representative lookup mode/query/data size against `do_lookup()` in
[actwiz.c](../../src/cmd/actwiz.c), with existing
[command_latency.c](../../src/net/command_latency.c) and event diagnostics.
Measure repeated warm/cold requests and loop/callback times under a stated load.
The original four event-budget reports deferred at most one tick and do not
demonstrate sustained stalls. If profiling identifies a reproducible blocking
operation, correct that path while preserving staff permissions/results and
bounded loop work. Reuse the command-latency/event runtime harnesses and compare
before/after distributions; a single faster run is insufficient evidence.

### LR-18 — Pathfinding limits and diagnostics (low; #56 observations)

- [ ] Explain the 22 room-budget and 15 distance-limit exits, correcting a
  reproducible false failure or excessive logging if found.

Trace the actual caller and source/target rooms into `how_close()` in
[graph.c](../../src/world/graph.c). Confirm edge/room eligibility and intended
distance semantics using small native fixtures at, below, and above the limit,
plus a room-budget exhaustion case. Keep both bounds and queue cleanup; do not
increase/remove them just to hide a diagnostic. Verify caller-visible results
and bounded work, and measure any log-volume change. The spelling clarification
in the review does not establish a relocation/pathfinding bug.

### LR-19 — Public health clients (low; #56 observations)

- [ ] Confirm the intended monitoring clients work through Cloudflare and
  document the urllib 403/1010 versus successful curl result.

Inventory the configured clients and reproduce their real method, headers,
URL, response status/body, and timeout from the expected network location.
Compare local readiness with the public path using the
[health contract](../reference/api/health.md) and
[healthcheck.sh](../../scripts/healthcheck.sh). Prefer correcting the intended
probe configuration. Change a narrowly scoped health rule only if required and
authorized; retain protection of other paths. Verify healthy/unhealthy handling,
no cached false health result, and useful failure reporting from the actual
monitor. A curl success alone does not qualify a monitor using another client.

### LR-20 — Protected host-log coverage (host-owner audit; #56 coverage)

- [ ] Complete the same fixed-window review of system/kernel/auth/mail/Fail2Ban,
  Plesk, web-server, and host database logs.

The original service account could not read these logs. The host owner must
inspect **2026-10-12 22:25:09–2026-10-13 05:25:09 UTC**, including rotations and
the logs' timezone conversion. Record each source's coverage and any retention
gap, actionable finding, or verified clean result. Correlate connection bursts,
rotation, and mail failures with LR-11/LR-12/LR-15. Keep sensitive entries private
and publish only the necessary redacted conclusions. A still-inaccessible or
expired log is an explicit coverage gap, not a clean result.

## Verification, rollout, and closure

For each LR item, record the implementing commit or operational change, actual
commands/fixtures, result, and remaining limitation here or on #56. Mark its
checkbox complete only when its stated proof exists. Synchronize the matching
#56 checkbox and link the evidence. A policy decision must name the selected
rule; an expected-behavior disposition must explain it from reproduction or
measurement. Keep unresolved owner actions and unavailable evidence open.

For implementation changes:

1. Run the smallest relevant executable tests while iterating. Add missing
   behavior coverage to existing harnesses first, and register any new database
   leg with `tests/run_db_tests.sh`. Use disposable authority for database and
   gameplay journeys. Record failing-before/passing-after evidence for fixes.
2. Apply [TESTING.md](../guides/TESTING.md) and [AGENTS.md](../../AGENTS.md):
   `make -C src` after C/C++ changes, changed-line formatting during work, and
   the required completion gates for behavior changes:
   `./scripts/format.sh --all --check`, `make test-all -j16 TEST_JOBS=16`, and
   `make test-db`. Use
   `scripts/check_tests_catch.sh BASE HEAD` for changed defect regressions and
   explain any inability to establish that they catch the old behavior.
3. If backup/restore code changes, run its focused tests and the documented
   privileged integration test in a disposable environment. Apply the security
   checks specified in TESTING.md for network/authentication changes. Use
   `npm ci --prefix site && npm test --prefix site` for documentation changes.
   Do not wait for CI as a substitute for local proof.
4. Update [REGRESSIONS.md](../testing/REGRESSIONS.md) for fixed defects and the
   relevant existing reference/operations docs when behavior changes. Keep raw
   production data and generated test/build artifacts out of commits.
5. For a later authorized rollout, use the existing runbook, preserve the
   deployed binary/configuration and any file requiring repair, verify the
   actual loaded build, then observe the affected path. In particular, compare
   new SQL/file statistics through a same-day restart and midnight boundary.
   Do not run deliberate failure experiments on production by default. If
   scheduler state changes, document binary/state rollback compatibility before
   release; reverting a binary alone may not safely read the new state.

Do not add fixes for observations already explained by the review: successful
backup/archive verification, historical login-export omissions, TLS renewal not
being due, or healthy service/outbox/Redis samples. They remain historical
context, not guarantees about the current host.

The plan-delivery check is separate from executing it: review coverage of all
20 remaining #56 checkboxes, validate this document's links and site build,
publish it on `master`, and verify the issue links back to this file. Keep #56
open until its execution evidence satisfies the items above. #57 and #58 retain
their own acceptance criteria and closure decisions.
