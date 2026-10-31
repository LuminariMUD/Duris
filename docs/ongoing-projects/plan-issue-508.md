# Issue #508: a 72-hour Good/Evil frag race with guaranteed progression

Status: **implementation resumed; replacement faction-rules PR #519 is ready for review**.
Updated 2026-10-31. The code and tests in the implementation worktree still contain
parts of the superseded personal-acceleration policy. They are not qualified for
this contract. The owner has authorized implementation of this revised plan. Merge, release and
production deployment remain separate.

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

**This pass's file and proof:** update this plan, inspect owning source and the
existing PR stack, check the policy mathematically and validate document links.
Preserve all pending source/test/help edits. Implementation below is future work;
planning verification is not evidence that the server already follows these rules.

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
new fingerprints. Recheck migration numbering before future implementation.

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

Update `lib/information/help_index`, `docs/reference/CODEBASE.md`,
`docs/reference/CLASSES.md` and `lib/frag_cap.cfg` during implementation. They still
contain superseded wording in the pending patch and are not revised in this pass.
Hardcore help must state that its +2 XP allowance is separate from the normal
one-level faction gap. No news publication or production help sync is implied.

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

## Source alignment review and work remaining

Reviewed against the current checkout on 2026-10-31:

- **Engine/codec/config:** `frag_cap.c/.h` still implements one shared cap,
  per-PID points and acceleration. Replace that policy and its versioned state
  with the rules above; update `frag_cap_config.c/.h`. Preserve useful time bounds,
  atomic preparation, codec validation and the explicit-now test seam.
- **Combat adapters:** both real parent transaction hooks already exist in the
  pending patch. `frag_cap_apply_combat()` currently passes PID/points and discards
  the captured `racewar`; route Good/Evil scores using that existing field. The
  capture owner is [fight.c](../../src/combat/fight.c). No reward producer redesign.
- **Storage/adoption:** transaction borrowing, atomic journal preparation and
  migration 0057 are reusable. `frag_cap_sql_save()` currently zeros both side
  projections; change them as specified. Fix the identified legacy-maximum
  adoption edge before enabling the revised policy.
- **Timer/publication:** the pending flatfile maintenance route, existing scheduler,
  and asynchronous runtime observer are reusable. Change the settlement result,
  status and announcement semantics; remove the acceleration-secured path.
- **Readers/XP:** both `sql_level_cap()` branches currently ignore the side and
  return the same cap. Restore side selection from the new authority. Retain the
  full-XP banking change and test both [XP](../../src/world/limits.c) and
  [epic-stone](../../src/world/epic.c) consumption of the selected faction cap.
- **Player/reference text:** the pending help/config/reference changes still say
  shared access, personal progress and acceleration. Rewrite those at activation;
  keep cached ranking text free of current race/cap data.
- **Tests:** existing policy, storage, publication and journey harnesses use the
  earlier contract. Revise behavior assertions and fixtures, not just output
  strings. In particular, the old cross-PID non-pooling and twenty-winner failure
  assertions must become faction-pooling cases.

Current character-creation/capture code retains historical side enums, but the
accepted live policy has two chosen factions. Use captured chosen side consistently
for neutral/undead races and add representative regressions; do not derive credit
from historical race labels or turn this into an account-policy refactor.

## Focused future qualification

These are implementation acceptance gates, not claims completed by this plan edit:

- [ ] Fresh 31/31; first and later regular results at 72 hours; no early opening or
      minimum frag threshold; positive-score and zero-score ties.
- [ ] All examples above; repeated/alternating winners, trailing winner +2,
      ties preserving the existing lead, every circle override, terminal 56/56.
- [ ] Across all reachable cap states: neither cap decreases, normal gap <=1,
      highest cap advances once per elapsed round, 15/75-day schedules.
- [ ] Positive faction pooling across PIDs/alts; twenty +5 awards =100 points;
      exact ties; less-than-one-frag wins; all scores continue counting; checked
      overflow, negative/zero/non-PvP exclusions and unchanged ordinary rewards.
- [ ] Captured Good/Evil choice for neutral/undead races; historical leaderboard
      leadership and current frag balances cannot change a round result.
- [ ] Stable admission/cutoff, exact-deadline membership, whole-event assignment,
      no carry, late closed-round outcomes, replay and timer/combat contention.
- [ ] SQL rollback/ambiguous commit and flatfile interrupted journal/image recovery;
      reopen/restart, corruption, bounded full-group images and missing-state errors.
- [ ] Downtime: saved scores decide one round, later elapsed empty rounds tie;
      fixed deadlines, no score reuse, no extra transition from duplicate ticks.
- [ ] Legacy caps below 31, divergent caps, customized old floor/maximum,
      earlier/future/expired deadline, existing 56, repeated adoption and any real
      intermediate-format conversion identified during authorized target inventory.
- [ ] Fresh SQL reset and resumed cutoff/clock fencing; fresh flatfile root;
      preserved earned levels/balances and rejection of old-season credit.
- [ ] Correct faction readers for normal XP and epic stones; full XP banking,
      global/storage/overflow bounds, ordinary XP ceiling 50 and Hardcore +2<=56.
- [ ] Cached/uncached current race status, provisional leadership/ties, pending and
      failure feedback, confirmed-state retention, no older-revision regression or
      duplicated announcements.
- [ ] A real loaded-world PvP -> durable faction score -> normal maintenance ->
      distinct faction caps -> legitimate banked-XP advancement -> restart journey
      on MariaDB and flatfile. Include a no-PvP tied-round case; use the existing
      fixture's offline deadline seeding, never a gameplay clock command.

Reuse the existing focused entry points after updating their policy assertions:

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

Implementation checkout: `/home/aiwithapex/projects/duris-issue-508`.
Current working branch: `branch/issue-508-frag-cap-runtime`, based on `a68089af2`.
It contains the intentionally preserved uncommitted activation/help/test work,
including `frag_cap_runtime.c/.h`, `frag_cap_journey_fixture.cpp`,
`frag_cap_runtime_harness.cpp`, `test_frag_cap_journey.py` and
`test_frag_cap_runtime.py`. Do not discard or accidentally commit that work during
this plan-only task. Other worktrees, including bartender work, remain separate.

Existing stack:

- Draft [#514](https://github.com/LuminariMUD/Duris/pull/514), head
  `branch/issue-508-frag-progression` at `422a9e7cc`, base `master`: rules/codec and
  original plan. It still implements the superseded personal policy.
- Draft [#515](https://github.com/LuminariMUD/Duris/pull/515), head
  `branch/issue-508-frag-cap-storage` at `a68089af2`, base #514: storage/migration.
  Its transport is reusable, but tests/adoption/projections need the new contract.

These are not ready to merge as the accepted faction-race implementation. Both
were returned to draft and their descriptions now point to the accepted plan.
The documentation-only review is [#518](https://github.com/LuminariMUD/Duris/pull/518),
head `branch/issue-508-faction-race-plan`, base #515. Policy revision commit
`36b2270c3` changes only this document. The local runtime branch contains the same
plan commit while its implementation remains uncommitted. No release tag belongs
to this step. Future implementation must rescope the parent PRs before this stack
is treated as the new gameplay feature.

After a later request to implement: revise the rules/codec/config and native cases;
then the faction adapters/adoption/projections; then runtime/readers/help and real
journeys. Keep focused commits and reviewable dependent PRs as each chunk passes.
Update PR titles/bodies to the final policy and maintain the stack without force
rewriting existing history. Inspect upstream/migration drift first. Rough remaining
implementation/qualification estimate is 3-5 hours, subject to actual findings;
the earlier minute-by-minute plan for the superseded policy is retired.

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

## This planning review's completion record

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
revision notice. Gameplay implementation remains a later task.

## Resumed implementation — 2026-10-31

Active checkout is now `/home/aiwithapex/projects/duris-issue-508-faction`.
The original `/home/aiwithapex/projects/duris-issue-508` retains the earlier pending
activation work for selective reuse. A clean replacement stack avoids publishing
superseded policy code in the new foundation PRs; #514/#515 stay draft references.
Current master is `aa77a2030`, including #496's credited Divine XP feedback. Preserve
that newer XP source/test change when reusing the old activation patch.

- Rules [#519](https://github.com/LuminariMUD/Duris/pull/519), branch
  `branch/issue-508-faction-rules` at `d6ec78fc9`, base master: new engine and fixed
  97-byte v2 snapshot. Native tests passed all 455 transitions plus pooling,
  boundaries, delayed admission, catch-up, adoption, frozen deadlines, corruption
  and checked overflow. `make -C src -j4`, formatting and staged clang-tidy passed.
- Storage is being prepared on `branch/issue-508-faction-storage`, based on #519.
  It keeps migration 0057 and both existing store mechanisms, routes captured
  Good/Evil awards, publishes the lower shared cap and both faction projections,
  and validates the old configured maximum during SQL adoption. Flatfile native
  parent-receipt/recovery tests passed. Both SQL engine checks passed on disposable MariaDB 10.11 and MySQL 8.0,
  including reset replay, legacy maximum clamping, faction projections, migration
  replay and full runtime metadata. Seven runtime compatibility tests and 26
  immutable runner tests also passed. The MariaDB server build passed.
- The prior gameplay journeys are transport evidence only. Revised runtime,
  faction readers, help/config, source contracts and gameplay journeys still need
  implementation and qualification. Do not claim the feature is complete yet.
