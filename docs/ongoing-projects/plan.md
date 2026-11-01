# Issue #498: small server delivery for Mudlet #26

Updated 2026-11-01. **Active: owner resumed the revised scope.**
The accepted revised plan limits the first delivery to useful, bounded server
interfaces. The rest of [client #26](https://github.com/LuminariMUD/duris-client/issues/26)
and [server #498](https://github.com/LuminariMUD/Duris/issues/498) remains follow-up work;
this delivery does not close either whole issue.

Worktree: `/home/aiwithapex/projects/duris-issue-498`
Item PR branch: `branch/issue-498-owner-items`
Current delivery/evidence branch: `branch/issue-498-delivery-evidence`
Owner-item completion is committed/pushed as `0d5a1ac2d` plus parent integration
`8918c4a65`, ready in [PR #547](https://github.com/LuminariMUD/Duris/pull/547).
Remaining delivery work: short cost check, fixtures and handoff. Parent PRs are
being merged by another agent; leave those branches alone and retarget #547 to
master once the merged source is integrated.
Parent `1f9920ac2` now includes reviewed WebSocket/combat fixes and upstream
bartender reward batches. Revalidate the affected publisher/GUI paths and focused
restoration leg against this integration; retain unrelated proof.

## Deliver

**Outcome:** give Mudlet structured time, combat target/tank, session boundaries,
and visible owner inventory/equipment, with an explicit way to choose supported
streams. Reuse the implementations and passing checks already present.

1. **Time and stream support.** Reuse PR #542. Send the small shared time/phase
   snapshot on entry/re-enable/time changes. Support/interest checks precede new
   optional stream construction.
2. **Session and combat.** Reuse PRs #544, #545 and #546. Send session boundaries
   when they happen. Combat samples the two current prompt subjects in the
   existing flush and constructs changed state only; damage uses the actual hit
   result. No per-hit population scan or second gameplay calculation.
3. **Inventory/equipment.** Finish and publish the existing item branch. An
   interested panel receives coalesced completed owner state; resync is requested.
   Uninterested/unchanged lists build no JSON. Reuse the existing limits: one
   <=16 KiB/128-inspected-entry page per participant per flush, eight global work
   slots, fair rotation. Nested contents are explicitly requested, with bounded
   owner-tree search. Preserve native visibility/access rules, empty states,
   selector lifetime, and completed publication. No new storage calls or deltas.
4. **Client handoff.** Document the packages and provide real serialized fixtures.
   Point client work to existing `Ship.Info`/`Ship.Contacts`, `Char.Status`/
   `Char.Vitals`, `Char.Affects`, `Quest.Map`/`Quest.Status`, and `Comm.Channel`.
   These already support removing redundant contacts/score/time queries, visible
   affect-loss parsing, quest presentation and group-bid parsing where applicable.
   Mudlet must choose one source and retain fallback for unavailable features.

## Finish efficiently

**Files:** current GMCP/item changes and their existing focused tests; affected
parent WebSocket fixes; `docs/network/GMCP.md`, this plan, and client fixture
capture/handoff only. Runtime client UI/automation changes are a separate task.

**Proof:** reuse the recorded native, build, wire and backend results. Review the
final item diff and remaining native presentation/selector assumptions, integrate
parent fixes, and run only checks affected by those changes. Required C/C++ build
and formatting rules still apply. Capture updated client fixtures once.

Run one short matched cost check with the prepared baseline for idle/disabled,
active combat and large subscribed inventory. Measure protocol work, output and
loop cost; include a slow consumer. Confirm bounded work/backlog and no idle list
construction. Report measured results and limits. A material regression gets a
focused fix or the affected optional feature is held back. Do not turn this into
a new benchmark framework or exhaustive population/world workload campaign.

Publish the owner-items PR against `branch/issue-498-combat-events` as soon as its
focused checks pass. Preserve the existing PR stack and reuse valid evidence.
No deployment, release tag, production operation, full burn-in or CI wait.

**Estimate from this checkpoint:** about 4 active hours; allow **3-5 hours** for
server delivery as reviewable PRs plus fixtures/cost evidence/client handoff.
This reuses the substantial implementation already done. It excludes implementing
all of #26, the client UI migration, reviewer turnaround and production rollout.

## Explicit follow-ups

WHO, player/ship scan, dice and identify can be low-cost command-result additions:
emit the decisions/results already produced by the ordinary authorized command,
with bounded output and no second traversal/RNG/identification. They are separate
small PRs after this first delivery, not prerequisites for it.

Action outcomes, cooldown/activity tracking, observer notices, richer score/skills,
affect reasons, epic reports, weather and chargen extensions are deferred. Add a
specific one only for a selected client consumer. No blanket event/cooldown system.
The reported HP widget symptom remains unverified in real Mudlet; server combat
state alone does not establish a client fix.

Ablation: the first delivery is the client investigation's recommended small
server set. Keep useful implemented behavior and its relevant proof. Remove the
requirement to finish every candidate and the large qualification campaign before
shipping that set. Preserve deferred work and evidence; do not discard code.

## Current evidence and resume pointers

- Four open review PRs: [#542](https://github.com/LuminariMUD/Duris/pull/542),
  [#544](https://github.com/LuminariMUD/Duris/pull/544),
  [#545](https://github.com/LuminariMUD/Duris/pull/545),
  [#546](https://github.com/LuminariMUD/Duris/pull/546).
- Live heads checked during this planning pass: #542 `3e0299507` (WebSocket NPC
  accounting fix), #544 `202379077` (rejected-creation chargen reset), #545
  `ad994c6ef`, #546 `5da514bee`. Check ancestry and carry required parent fixes
  forward when implementation resumes; do not overwrite local item work.
- Current local work adds requested nested pages, open/close/access invalidation,
  and focused tests. Native ASan/UBSan passed nested visibility/cancellation,
  3,000-item bounded work, retries, disarm/repair/temporary-save behavior and the
  real reward publisher's failure/retry/replay/logout-to-wire assertions.
- Both server builds passed. Booted Telnet/WebSocket journey passed native
  load/drop/wield/remove/rename, nested put/get-all, wear and give/body switching.
  Focused real reward plus ordinary item restoration passed on MariaDB and
  flatfile (one level-11 ASK quest and restart per backend).
- Container tests passed access/audit/capacity refusal without notification;
  crumbleloot tests passed without announcing a detached reward attachment.
  Player-load tests, documentation checks, formatting and changed-line tidy
  passed. Parser fuzz passed 11,540,402 ASan/UBSan executions.
- Reuse `bin/qualification/issue498/owner-items-nested-wire.json`,
  `owner-items-mariadb-reward-restore.json`, `owner-items-flatfile-reward-restore.json`,
  `owner-items-nested-fuzz.log`, `owner-items-refused-movement.log`,
  `owner-items-crumble.log`, and `owner-items-nested-tidy.log`. Earlier checkpoint
  evidence remains in that directory. `baseline-881/` holds the prepared reference.
- World generation is shared: prepare it once, then run isolated backend legs.
  Concurrent `make world` calls caused a test setup race, corrected before both
  focused backend legs passed. No tracked generated outputs changed.
- The original local plan simplification and pause-handoff deletion predated this
  implementation run and are preserved. Other worktrees remain untouched. No
  owner-items commit/push/PR or production deployment has occurred in this run.

Resume progress: the integrated builds, GMCP sanitizer/WebSocket/publisher tests,
booted item journey and one ASK reward/restoration journey per backend passed.
Evidence: `owner-items-parent-wire.json`, `owner-items-parent-*-restore.json`.
The short cost check uses the existing latency tracer with a `gmcp_protocol`
span ending before storage/completion work; the old `gmcp_flush` span includes it.

PR #547 review follow-up: knockout/recovery now changes the item visibility
filter; reveal-true-name updates notify through the existing setter/publication
path. Both stale-view failures were reproduced in the GMCP sanitizer harness.
