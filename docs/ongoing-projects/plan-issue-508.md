# Issue #508: a 72-hour Good/Evil frag race with guaranteed progression

Status: **implemented and locally qualified; replacement PR stack being finalized**.
Updated 2026-10-31. Active checkout is `/home/aiwithapex/projects/duris-issue-508-faction`,
branch `branch/issue-508-faction-runtime`. The owner authorized implementation of
this revised contract. Merge, release, migration and production deployment remain
separate. Earlier personal-policy work is preserved in the original checkout.

The controlling decisions are the owner's latest clarification in this chat:
positive PvP frags pool by chosen Good/Evil faction during each three-day round;
the leading faction receives the next cap; a tie, including zero frags, advances
both existing caps; circle levels equalize the caps. The owner accepted the
follow-up interpretation that there is **no minimum 1.00-frag threshold**.

[Issue #508](https://github.com/LuminariMUD/Duris/issues/508) remains the tracking
issue. Its [earlier proposal](https://github.com/LuminariMUD/Duris/issues/508#issuecomment-6542754060)
is historical context and is superseded where it conflicts with this document.
The reported original +1.00-frag incident still lacks an identified event; this
policy change does not retrospectively explain that incident.

Prepared with the repository's [ablation skill](../../.agents/skills/ablation/SKILL.md).

## Outcome, boundaries and current scope

**Outcome:** everyone can reach level 31 through normal advancement. Each regular
72-hour round advances the highest normal faction cap by one. Good and Evil are
never more than one normal-cap level apart; shared circle levels remove the gap.
A quiet server progresses through zero-score ties. Fresh-season pacing is 15 days
from 31 to shared 36 and 75 days to shared 56, excluding service/publication delays.

**Retained behavior:** ordinary PvP eligibility, sharing, victim losses, epic and
blood-money rewards, artifacts, achievements, Divine Boons, account policy,
character levels/balances, and normal XP/epic-stone requirements. Keep full banking
of otherwise awarded XP within existing global/storage limits, the ordinary
level-50 XP ceiling, and Hardcore's +2 XP allowance bounded by 56. The one-level
invariant applies to normal faction caps, not actual character levels or the
additional Hardcore allowance.

**Non-goals:** quest/gear/combat-balance changes, a third faction, faction XP boons,
new currency, new services/schedulers, personal contribution targets, damage-based
scoring, production wipes, or a second persistence/reward queue.

**Implementation and proof:** the owners and accepted rules below are implemented
in the replacement stack. The completion record distinguishes native policy,
transaction/storage, and loaded-world evidence. Original pending work was reused
selectively through a three-way merge; current master's #496 XP feedback was
preserved. The original checkout remains a superseded recovery copy.

## Fixed gameplay contract

1. **Fresh season and cadence.** Both normal caps begin at 31. The first regular
   result occurs 72 real hours after the round starts, then every 72 hours.
   Reaching any score never opens a level early. Maximum normal cap is 56.
2. **Two faction scores.** Sum positive ordinary combat `frag_delta` awards, in
   integer hundredths, into Good or Evil according to each recipient's chosen
   faction captured with the combat outcome. Neutral and undead races participate
   on their chosen Good/Evil side; race identity and alignment are not extra
   scoreboards. Different characters, including alts, pool into their faction.
3. **Earned points, not balances.** All qualifying positive awards during the
   round count toward its final result. Negative victim deltas never subtract
   earned race points. Historical leaderboard balances, administrative changes,
   ship frags and arena scores do not decide this race. Ordinary reward eligibility
   remains the sole award definition; no new victim-level, ally-count or minimum
   individual-share gate is added.
4. **No target to reach.** Compare the two complete round scores at its deadline.
   A 0.01 lead wins. A score of 0.20 beats 0.10. There is no 0.20 personal target,
   1.00 faction minimum, or score ceiling at which counting stops. A provisional
   leader can be overtaken until the round closes.
5. **Decisive result.** Let `N = max(Good cap, Evil cap) + 1`. The winning faction
   receives normal cap `N`; the other receives `N - 1`. A trailing winner can jump
   two cap levels while the former leader holds its cap. Repeated wins raise the
   other faction too, so the gap cannot grow beyond one.
6. **Tied result.** Increase each faction's own existing normal cap by one. This
   includes both positive-score ties and 0-0. A tie preserves an existing one-level
   lead; it does not normally equalize the factions.
7. **Circle override and terminal state.** Whenever `N` is 36, 41, 46, 51 or 56,
   both caps become `N`, regardless of winner or tie. Fresh 31 is already shared.
   At 56 both are equal and the progression clock stops; ordinary PvP rewards
   continue. Apply this override before the normal winner/tie assignment.
8. **One event, one round.** Reset both race scores after every result. No score,
   participant remainder or surplus carries forward. Score the whole combat
   outcome atomically with its parent receipt; a replay adds nothing.
9. **Durable boundaries.** Use the command's stable `accepted_at_usec` and a
   persisted policy/season cutoff. Settle already-due rounds under the store lock
   before assigning a newly applied event. An admission exactly at the deadline
   belongs to the new round. A delayed event admitted to an already-ended round
   keeps its normal rewards but cannot alter a closed winner or score a later
   round. Pre-cutover and future-invalid admissions add no race points. This
   retains the earlier plan's late-receipt rule; pending recording is not a
   confirmed race contribution.
10. **Fixed-time recovery.** The next round starts at the previous effective
    deadline, not when a late worker or reboot happens. Downtime settles the saved
    round once using its committed scores, then any later elapsed empty rounds as
    zero-score ties. Never reuse an earlier score or invent historical PvP. There
    are at most 25 advances from a fresh 31 to 56.
11. **Permission to advance.** Cap changes grant no character levels or currency.
    An appropriate positive XP action can spend banked XP up to that character's
    faction allowance; ordinary XP and epic-stone requirements still apply.

### Required examples

All pairs below are **Evil / Good normal caps**. Each arrow is one round ending.

- Repeated Evil wins: `31/31 -> 32/31 -> 33/32 -> 34/33 -> 35/34 -> 36/36`.
- Good wins from `32/31`: `32/33`; Evil remains at 32 while Good catches up and leads.
- Evil wins from `32/31`: `33/32`; Good advances without winning that round.
- Either a positive tie or 0-0 from `32/31`: `33/32`, preserving the existing lead.
- A tie from equal caps `31/31`: `32/32`; repeated quiet rounds reach `36/36` in 15 days.
- Any result from `35/34` or `34/35`: `36/36`; any result from `55/54`: `56/56`.
- Twenty eligible winners each awarded +0.05 contribute **1.00 to their faction**.
  Four +0.05 awards to one character contribute 0.20 to that same faction; neither
  pattern has a separate qualification gate.

A faction can hold its cap for one round when it loses the lead. The guarantee is
one global progression step per round with a maximum one-level normal-cap gap,
not that every faction advances on every decisive result.

## Ablation and the smallest implementation

Keep the existing three concrete owners: [the rules engine](../../src/combat/frag_cap.c),
[storage adapters](../../src/combat/frag_cap_repository.c), and the locally added
`src/combat/frag_cap_runtime.c/.h` for boot/writer observation/game-thread publication.
Keep the existing maintenance job, critical admission timestamp, parent receipts,
SQL transaction and flatfile authority lock. Keep the XP-banking change and the
existing full-world test helpers. No new combat command or payload version is
needed: `combat_outcome_participant.racewar` already captures `GET_RACEWAR(ch)`.

Replace the old policy rather than add a selectable second mode. Drop the PID
credit map, 65,536-contributor limit, personal target, qualification timestamp,
earliest/automatic dual deadlines, 48-hour acceleration, and per-player progress
UI. Two exact faction counters replace the population-sized map. Retain ordinary
combat/history fields and numeric telemetry IDs needed for replay compatibility.

Use one 72-hour round duration in the existing configuration/policy module. Remove
obsolete threshold and acceleration settings. Persist the active start/deadline;
reboot or a configuration edit must not retime a published round. No additional
scoring or tie-break options are needed for the accepted contract.

### One bounded snapshot and one transition engine

The new snapshot needs:

- a version/policy identity and monotonic revision;
- the highest normal cap `top`, and which faction has the one-level advantage
  (`Good`, `Evil`, or `none`);
- policy/season credit cutoff, current round start and one closing deadline;
- two nonnegative integer earned-point totals, Good and Evil.

Derive caps: the leading faction has `top`, the other `top - 1`; with no advantage
both have `top`. At 31 and every shared circle, the advantage is `none`. Do not
maintain independent cap counters that can drift apart.

On each elapsed deadline:

```text
if top == 56: stop
next = top + 1
if next is a shared circle: advantage = none
else if Good points > Evil points: advantage = Good
else if Evil points > Good points: advantage = Evil
else: retain the existing advantage

top = next
clear both scores
round_start = the deadline just settled
next_deadline = round_start + 72 hours, or inactive at 56
```

Retaining the advantage on a tie is exactly equivalent to adding one to each old
cap. Keeping one `top` and one advantage also enforces the one-level invariant.
Do not cap scores at 100 points: that would turn unequal high scores into false
ties. Use checked integer accumulation and a small checksummed codec; corruption
or overflow must fail visibly without partially committing rewards/points.

Change the snapshot format/version deliberately. Existing personal-acceleration
snapshots cannot be reinterpreted as faction scores: they did not retain each
contributor's faction at capture. No production use of that intermediate format
is evidenced by this task. Before activation, inventory actual target snapshots.
If a real intermediate-policy authority exists, provide a guarded one-time
conversion that preserves opened access and adopts the first deadline under the
cutover rules below, with new race scores zeroed. Unknown/corrupt formats must not
be treated as missing state. Do not retain two live policy engines or reconstruct
faction credit from today's player records.

### Atomic combat scoring and timer settlement

After the existing parent-receipt replay check, while holding the existing SQL
transaction or recovered flatfile authority lock:

1. Load the latest authoritative snapshot, capture one decision time, and settle
   every elapsed deadline, comparing the saved round only once.
2. Validate admission against the cutoff and current half-open round interval
   `[round_start, deadline)`. Exclude late/pre-cutover/future-invalid credit while
   preserving legitimate ordinary rewards.
3. Sum every positive participant award into its captured Good/Evil bucket. Do
   not infer a side from race, current leaderboard rank or a later login. Historical
   side enum values do not create a third counter or get silently remapped.
4. Save the new snapshot with the parent combat receipt. There is no immediate
   threshold-triggered unlock after the event. SQL helpers borrow the caller's
   transaction; flatfile adds its after-image to the same prepared operations.

Rollback loses both receipt and race points. Ambiguous commits resolve through
existing receipt recovery. The normal maintenance job takes the same state lock
and applies the same deadline transition. Duplicate ticks are naturally idempotent.
Timer/combat contention must have executable boundary tests, including delayed
receipts, rather than relying only on a model of the rules.

The current pending flatfile patch allows 83 operations: the previous 82 plus one
cap image. Keep the full 40-participant regression and explicit after-image byte
budget; recompute the snapshot bound for the new small state. No new ledger,
global combat key, player field or persistence thread is justified.

### SQL projections and common readers

Reuse immutable [0057_shared_frag_cap](../../migrations/immutable/0057_shared_frag_cap.sql),
sequence 58, which adds one nullable MEDIUMBLOB to the existing singleton. The
column is suitable for the revised snapshot; no new SQL schema is required merely
because the serialized policy changes. Do not edit sealed migrations or fabricate
new fingerprints. The final upstream check still has migration 0056 as its head; 0057 is the
next additive migration. Recheck this again when merging/deploying.

The snapshot is the sole authority. In the same transaction publish projections:
`level = min(Good cap, Evil cap)`, `level_good = Good cap`, `level_evil = Evil cap`,
and `next_update = the round deadline` (inactive terminal representation at 56).
Using the highest cap for `level` would incorrectly grant it to both sides through
legacy max(shared, side) readers. Retired lifetime-frag/leader fields do not select
the round result. Keep historical rows intact.

`sql_level_cap(side)` must select the confirmed Good/Evil cap. `get_level_cap_info()`
returns the common lower cap plus both effective faction caps and the deadline.
Both MariaDB and client-free paths use the same published state. XP and epic-stone
callers already pass `GET_RACEWAR(ch)`; retain their ordinary advancement checks.
The steady-state game loop performs no synchronous SQL/filesystem cap reads.

### Publication, status and help

Retain the coalesced observation on the existing writer and publish only newer
revisions on the game thread. A committed result survives lost publication/restart;
transient reads retain confirmed state. Boot validates/adopts before gameplay.
Announce newly confirmed faction caps once, with both caps named. If several
missed rounds are caught up, a combined final-state announcement is sufficient;
boot recovery is quiet. Do not infer a winning score/result from counters already
cleared for the next round, and do not announce a provisional leader as secured.

FRAGLIST must show both normal faction caps, the two **current-round earned**
scores, the remaining 72-hour deadline and the current provisional leader or tie.
Explain that ties advance each existing cap and circle levels equalize them.
Keep the lifetime/current-balance leaderboard clearly distinct from this round's
race. Render current cap/race status outside the shared cached rankings; the
existing raw leaderboard cache and its old-format rejection can remain. Personal
pending/failure feedback still carries the combat operation reference for recovery;
there is no personal progress target. At 56, stop showing an unlock race/requirement.

Updated `lib/information/help_index`, its overriding `help/duris_help_parsed.hlp`
entries, `docs/reference/CODEBASE.md`, `docs/reference/CLASSES.md` and
`lib/frag_cap.cfg`. Hardcore help explicitly separates its +2 XP allowance from
the normal one-level faction gap. No news publication or production help sync
has occurred.

## Current-season adoption, fresh resets and rollback

Retain the earlier plan's preserve-access cutover promise. This is a one-time
transition exception; all regular new-policy rounds last 72 hours.

- Before replacing configuration, capture the actual old effective normal caps,
  floor **and maximum**, the old next-unlock timestamp and relevant pending work.
  SQL inputs must reflect the legacy clamping rules, not just the largest raw row
  value. Flatfile needs its previously effective floor. Validate these inputs;
  never infer a customized old maximum from the new fixed-56 default.
- Let `M` be the highest validated effective normal cap already open, excluding
  Hardcore's allowance. Set both new normal caps to `C = min(56, max(31, M))`,
  with no advantage and zero race scores. This preserves previously opened access
  and provides equal starting caps for the new contest. It is not a normal tie
  result. Preserve character levels, banked XP and ordinary frag balances.
- If `C == 56`, retire the clock. If `M < 31`, opening 31 is the transition unlock;
  start the first full 72-hour round at activation.
- Otherwise retain the earlier of the valid old deadline and `activation + 72h`
  for the first result. There is no earlier acceleration deadline. If the old
  deadline has already expired, process exactly one zero-score tied result at
  activation, then start a full new round. Do not invent a chain of old rounds.
- Set credit cutoff to activation. Do not count pre-policy outcomes, transfer the
  old personal-credit map or backfill historical faction scores. Repeated adoption
  returns the saved state and never resets a deadline. Record actual chosen caps,
  cutoff and deadline in the deployment handoff when deployment is authorized.

SQL pwipe keeps its existing writer drain and epoch/recovery fence. Initialize
31/31, no advantage and zero scores using the persisted `reset_started_at` as the
new cutoff/start, with deadline +72h. Retrying/resuming that same reset must not
move the clock or admit an old-season operation. Keep the native reset-handoff
regression and the focused repository reset tests.

Flatfile `shutdown pwipe` remains unsupported by the existing runbook. Use a
selected fresh authority root for a new season and initialize 31/31 there. The
existing missing-state adoption input must explicitly reflect fresh-season 31
(e.g. `cap.floor.level=31` for that root), rather than reuse an old season's higher
legacy floor. Do not erase/reuse an old root to manufacture a fresh season, and
do not add a new wipe system to this work.

Migration, production reset and deployment require owner authorization. Before
activation, an application rollback may leave the additive nullable column. After
activation, preserve the new snapshot/read path in any qualified rollback build
or use a forward fix. An old flatfile binary ignores this state and restores its
old floor; old SQL maintenance only updates projections. Neither is a safe way to
run an activated race. Never restore a lower cap or clear scores as a shortcut.

## Final source alignment review

- `frag_cap.c/.h` now implements the compressed top/advantage state, two exact
  faction counters, fixed deadlines and the 97-byte v2 codec. No personal map,
  target, qualification timestamp or early-opening path remains.
- Both real combat repositories call `frag_cap_apply_combat()` inside the parent
  transaction after receipt replay checks. The helper uses captured faction,
  never PID or race identity, to select the bucket.
- SQL saves the lower common cap and both effective side caps. Adoption validates
  the old floor/maximum and custom clamping; flatfile prepares the same snapshot
  under the existing authority lock. The full-group bound is 83 operations, with
  an explicit conservative byte bound below the existing 256 MiB journal limit.
- The existing maintenance job and store locks settle every deadline once.
  Flatfile routes before SQL acquisition; SQL retains its time-budget rollback.
- The runtime observes on the existing writer, preserves confirmed state during
  read errors/backpressure, and publishes only newer revisions. Boot logs both
  actual caps, revision, cutoff and deadline. Announcements show confirmed caps;
  score changes remain provisional until the deadline.
- Both `sql_level_cap()` branches select the chosen faction. XP and epic-stone
  callers retain their normal checks. XP banks fully within existing ceilings,
  and current master's credited Divine feedback remains intact.
- Status/help/reference text consistently describes the new race. Current race
  scores/caps stay outside cached historical rankings. The obsolete countdown
  codec and acceleration settings are removed; history/telemetry IDs remain.
- Native tests, real receipt tests and loaded-world fixtures now assert faction
  pooling, ties and circles. Mechanical native compiler-list changes supply real
  dependencies; they do not claim every unrelated campaign was rerun.

Neutral/undead race identity does not select another score bucket. The capture
continues to record `GET_RACEWAR(ch)`; direct routing tests pool distinct PIDs on
Good/Evil and do not create a counter from historical third-side enum values.
Account and character-creation policy itself is unchanged.

## Implementation acceptance record

The local implementation gates below passed. Production inventory/activation is
a separate authorized operation; no production policy or player state was inspected.

- [x] Fresh 31/31; first and later regular results at 72 hours; no early opening or
      minimum frag threshold; positive-score and zero-score ties.
- [x] All examples above; repeated/alternating winners, trailing winner +2,
      ties preserving the existing lead, every circle override, terminal 56/56.
- [x] Across all reachable cap states: neither cap decreases, normal gap <=1,
      highest cap advances once per elapsed round, 15/75-day schedules.
- [x] Positive faction pooling across PIDs/alts; twenty +5 awards =100 points;
      exact ties; less-than-one-frag wins; all scores continue counting; checked
      overflow, negative/zero/non-PvP exclusions and unchanged ordinary rewards.
- [x] Captured Good/Evil choice for neutral/undead races; historical leaderboard
      leadership and current frag balances cannot change a round result.
- [x] Stable admission/cutoff, exact-deadline membership, whole-event assignment,
      no carry, late closed-round outcomes, replay and timer/combat contention.
- [x] SQL rollback/ambiguous commit and flatfile interrupted journal/image recovery;
      reopen/restart, corruption, bounded full-group images and missing-state errors.
- [x] Downtime: saved scores decide one round, later elapsed empty rounds tie;
      fixed deadlines, no score reuse, no extra transition from duplicate ticks.
- [x] Legacy caps below 31, divergent caps, customized old floor/maximum,
      earlier/future/expired deadline, existing 56 and repeated adoption. Unsupported/corrupt versions fail visibly;
      no real intermediate-policy authority was found in this local work. Any
      target conversion remains conditional on authorized deployment inventory.
- [x] Fresh SQL reset and resumed cutoff/clock fencing; fresh flatfile root;
      preserved earned levels/balances and rejection of old-season credit.
- [x] Correct faction readers for normal XP and epic stones; full XP banking,
      global/storage/overflow bounds, ordinary XP ceiling 50 and Hardcore +2<=56.
- [x] Cached/uncached current race status, provisional leadership/ties, pending and
      failure feedback, confirmed-state retention, no older-revision regression or
      duplicated announcements.
- [x] A real loaded-world PvP -> durable faction score -> normal maintenance ->
      distinct faction caps -> legitimate banked-XP advancement -> restart journey
      on MariaDB and flatfile. Include a no-PvP tied-round case; use the existing
      fixture's offline deadline seeding, never a gameplay clock command.

Focused entry points used for qualification:

```sh
python3 tests/async/test_frag_cap.py
python3 tests/async/test_frag_cap_config_contract.py
python3 tests/async/test_frag_cap_repository.py
python3 tests/async/test_frag_cap_runtime.py
python3 tests/async/test_flatfile_player_domain_repository.py
python3 tests/async/test_world_quest_xp_feedback.py
python3 tests/async/test_report_cache_codec.py
python3 tests/async/test_maintenance_scheduler.py
bash tests/async/with_disposable_mariadb.sh python3 tests/async/run_level_cap_mysql.py
TEST_DB_IMAGE=mysql:8.0 bash tests/async/with_disposable_mariadb.sh python3 tests/async/run_level_cap_mysql.py
bash tests/async/with_disposable_mariadb.sh python3 tests/async/test_frag_cap_repository.py --mysql
bash tests/async/with_disposable_mariadb.sh bash tests/async/run_combat_outcome_schema_mysql.sh
make -C src -j4
make -C src -j4 PERSISTENCE_BACKEND=flatfile DMS_BINARY=../bin/server/dms_flatfile
python3 tests/async/test_frag_cap_journey.py --backend flatfile --server bin/server/dms_flatfile
bash tests/async/with_disposable_mariadb.sh python3 tests/async/test_frag_cap_journey.py --backend mariadb --server bin/server/dms_new
./scripts/format.sh --check
```

Use the existing award/codec, Hardcore, singleton, migration/runtime-contract and
reset-handoff tests when their owners change. Reuse valid unchanged schema and
ordinary-reward evidence below. No full burn-in, CI waiting or unrelated campaign
rerun is required for this policy revision. Build separate backend objects/binaries;
all fixtures remain disposable and must not source production credentials.

## Git and continuation handoff

Active implementation: `/home/aiwithapex/projects/duris-issue-508-faction`, branch
`branch/issue-508-faction-runtime`. Current master base is `aa77a2030`, including
#496. The original `/home/aiwithapex/projects/duris-issue-508` remains a superseded
recovery checkout; its pending files were preserved. Other worktrees were untouched.

Replacement review stack:

- [#519](https://github.com/LuminariMUD/Duris/pull/519), branch
  `branch/issue-508-faction-rules`, commit `d6ec78fc9`, base master: engine/codec
  and exhaustive native rules.
- [#521](https://github.com/LuminariMUD/Duris/pull/521), branch
  `branch/issue-508-faction-storage`, commit `9cd4a14ab`, base #519: both adapters,
  immutable migration 0057, compatibility contract and storage/reset tests.
- Activation: `branch/issue-508-faction-runtime`, base #521. The final PR/commit
  will be recorded here after publication. It contains real combat/maintenance,
  boot/publication/readers, full XP banking, status/help and runtime regressions.

The earlier #514/#515 drafts and plan review #518 are superseded by this stack;
their branches/work remain preserved. Review the replacement stack, not those
old personal-policy implementation diffs. No force rewrite, merge, release tag or
production operation has occurred. Keep future checks proportional and reuse the
qualified unchanged migration/receipt evidence rather than rerunning unrelated
Nexus, shop, cargo or quest campaigns.

Before deployment, apply 0057 through the maintained runner, retain the actual old
configuration for validated adoption, and inventory any existing snapshot format.
Boot refuses corrupt/unsupported snapshots. Never delete authority to force a new
season, downgrade to the old flatfile floor or run old SQL projection-only
maintenance after activation. The adoption/reset/rollback section remains the
operator handoff; record actual production caps/cutoff/deadline only when that
operation is explicitly authorized.

## Evidence retained from the earlier implementation

The following checks passed for the earlier shared-cap policy. They provide
reusable storage/transport and unchanged-behavior evidence, **not faction-race
qualification**. Results and failure/retry history are in local
`bin/tests/issue-508-*.log`; build artifacts/world outputs are ignored and uncommitted.

- Rules/codec and both backend builds passed in #514; native ASan/UBSan storage,
  adoption, rollback/reopen/replay and corruption passed in #515 on flatfile,
  MariaDB 10.11 and MySQL 8.0. Both SQL legs used the real bootstrap/migration
  runner, repeated migration 0057 and verified measured runtime fingerprints.
- Pending real combat hooks passed `test_flatfile_player_domain_repository.py`
  and `run_combat_outcome_schema_mysql.sh`, including full groups, receipt replay,
  rollback after prepared rewards, and interrupted flatfile recovery.
- Pending `run_level_cap_mysql.py` passed on MariaDB and MySQL 8.0. The updated
  reset adapter tests passed both engines. The native `run_pwipe_handoff_mysql.py`
  run exited successfully, covering fencing, retry/lost acknowledgements and the
  new reset clock. Its optional full-server cold-recovery leg was not requested.
- Both earlier loaded-world `test_frag_cap_journey.py` legs passed ordinary PvP,
  maintenance, cap permission, banked XP and saved restart; the SQL leg also used
  a private Redis instance for cached/uncached views. Their personal-score/shared
  cap expectations must be replaced before they prove the accepted policy.
- Publication under ASan/UBSan, full XP feedback/banking on both variants, ordinary
  PvP rewards/codec, Hardcore config, singleton, cache framing, maintenance,
  lifecycle inventory and maintained documentation links passed. Preserve evidence
  for unchanged paths and rerun only affected checks or required completion gates.
- `make -j4 world` generated the missing local world files for the isolated
  journeys. No tracked area files, production data or credentials were changed.

## Historical plan review before implementation resumed

The accepted requirements, implementation owners, migration/reset/rollback rules,
examples, and future acceptance cases have been reconciled above. Existing source
and open-PR metadata were inspected; their remaining policy mismatches are explicit.
An independent planning model checked **455 scored transitions across 66 reachable
states**, including sub-frag wins, positive/zero ties, alternating/repeated leaders,
monotonic caps, gap <=1, circle overrides, terminal 56 and 15/75-day schedules.
It compared the compressed top/advantage representation with the literal two-cap
rules. This is a policy consistency check, not a production C++ test.

Passed `python3 tests/async/test_documentation_contract.py
DocumentationContractTest.test_maintained_markdown_links_and_anchors_resolve` and
`git diff --check -- docs/ongoing-projects/plan-issue-508.md`. Every relative link
in this plan resolves in the committed base, so the plan review does not depend
on unpublished implementation files. The final policy sections were checked
against the accepted examples, scoring, timing, circle and advancement rules.
All 73 pre-existing non-plan paths were verified byte-for-byte unchanged.

The reviewed plan is committed and pushed in [#518](https://github.com/LuminariMUD/Duris/pull/518).
The superseded implementation PRs #514/#515 are drafts with an explicit policy
revision notice. At that checkpoint gameplay implementation remained a later
task; the implementation completion record below supersedes that status.

## Revised implementation completion record — 2026-10-31

- Both server builds passed using separate backend objects/binaries. Formatting,
  whitespace and staged clang-tidy passed. Upstream and migration numbering were
  rechecked against current master.
- Native policy passed all 455 transitions across 66 reachable states plus exact
  admission, pooling, no early unlock, catch-up, adoption, deadline freezing,
  codec corruption and arithmetic failure cases.
- Native store tests passed under ASan/UBSan on flatfile, MariaDB 10.11 and
  MySQL 8.0. Real combat tests passed flatfile interruption/recovery and SQL
  rollback/replay. An injected lost COMMIT acknowledgement returned ambiguous;
  retry recovered the actual committed receipt without adding points again.
- `run_level_cap_mysql.py` passed on MariaDB and MySQL 8.0, including concurrent
  score/timer writers, zero/positive ties, lead flips, circle equality, delayed
  admission, catch-up and corrupted/missing authority. Each test run now owns a
  unique harness output, allowing independent disposable engine runs safely.
- `test_frag_cap_runtime.py` passed ASan/UBSan checks for coalesced observation,
  distinct viewer caps, failed reads and writer refusal, stale revisions, quiet
  boot recovery and exactly-once cap announcements.
- Full XP feedback/banking passed both backend variants with the new #496 cases
  preserved. Ordinary PvP rewards/codec, Hardcore config, singleton, cache framing,
  maintenance contracts, lifecycle inventory, native epic paths and help catalog/
  live-parser checks passed. The optional standalone SQL epic leg was skipped;
  native epic checks and the real SQL combat/receipt suite passed.
- The existing native `run_pwipe_handoff_mysql.py` suite passed with faction
  projections and the stable reset clock, including fencing, retries, lost
  acknowledgements and preserved fresh state. Its optional full-server cold-reset
  recovery leg was not requested; no production wipe occurred.
- Loaded-world `test_frag_cap_journey.py` passed on **both backends**: legitimate
  mortal PvP changes the provisional leader, ordinary maintenance opens distinct
  caps, banked XP advances only on a legitimate action, and restart preserves the
  result. A later 0-0 round preserves the 33/32 lead; another quiet circle opens
  36/36. None of those cap results grants a free character level. The SQL leg
  verified real private Redis cached/uncached views; flatfile verified its native
  uncached path and the shared native cache framing test covers the cache codec.
- Cosmetic logging and restored budget/backpressure handling were checked with
  focused native tests/builds; valid normal-path journey evidence was reused.
  Final local logs are under `bin/tests/` (`journey-*.log`, `sql-combat.log`,
  `sql-lifecycle.log`, `lifecycle-mysql.log`, `reset.log`, `runtime-tidy.log`).

No production migration, live gameplay deployment, news publication or release
tag is part of this delivery. Actual live caps and target snapshot inventory are
unverified until deployment is authorized.
