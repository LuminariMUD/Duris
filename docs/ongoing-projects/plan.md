# Issue #166: Mountain Dwarf Hatred implementation plan

Tracking: [issue #166](https://github.com/LuminariMUD/Duris/issues/166).
Implementation branch: `branch/issue-166-hatred`.
Status: implementation in progress; runtime acceptance remains open.
Reviewed on 2026-10-18 against `origin/master` at
`9017ce1ca940cbe74a6162fca3d4d8c113eeb8b6`.
The issue body and its empty comment thread were read on that date.

The previous issue #67 plan is preserved byte-for-byte in
[issue-67-artifact-identity-plan.md](issue-67-artifact-identity-plan.md).
Its incoming migration-document link now points there. That unrelated work remains
unchanged and is not a dependency of #166.

## Outcome, scope, and evidence boundary

An eligible mountain dwarf has exactly one `-1` combat-pulse modifier and one
`-1` spell-pulse modifier while a visible Orc, Duergar, or Drow occupies the same
room. Each inactive-to-active transition announces activation once; each reverse
transition announces subsidence once. Repeated checks and repairs of partial or
duplicate state are silent. Preserve the level-21 unlock, existing sight rules,
actual-race matching, player as well as NPC targets, and existing message text.

This remains a periodic innate: assess the room on the next scheduled check.
Movement or a visibility change need not synchronously trigger an extra check;
entering and leaving between checks may produce no transition. Record the effective
interval in acceptance results. No movement hooks or zone/plane-specific rules are
needed.

The reported live "any NPC" behavior is **not yet reproduced or explained**.
Source inspection establishes defects and a configuration discrepancy; it does not
identify the deployed binary, actual offending NPC races, or live event history.
A code repair can be ready while root-cause and live acceptance criteria stay open.

Non-goals: racial rebalance, area-wide race rewrites, a new affect/event framework,
new telemetry service, schema migrations, production changes, deployment, or a restart.
The original publication contained documentation only.

## Active implementation handoff (2026-10-19)

- Delivery remains on `branch/issue-166-hatred`. Master `a32d6a4f3` was merged
  at `366095875`, preserving this plan byte-for-byte during conflict resolution.
  Master's previous active document is preserved byte-for-byte as
  [plan-issue-57.md](plan-issue-57.md). Issue #166 is still open with no comments.
- Outcome: bounded same-room race matching, exactly one transient combat/spell
  pulse pair, one message per transition, and one recoverable watcher per resident.
  Non-goals remain those above; no production mutations or deployment are included.
- Ablation: retain the existing race table, eligibility/visibility rules, effect
  APIs and scheduler. No second allowlist, persistent active flag, movement hook,
  timer service, or general event/affect abstraction is required. Keep lifecycle
  handling with the watcher and existing entry/recovery paths.
- Expected files: `innates.c`, `nanny.c`, `prototypes.h`, `duris.properties`,
  copyover recovery only if its entry trace proves a missing start, and focused
  Hatred harness/journey files. Proof uses the production callback, table,
  eligibility, visibility, affect removal/messaging and scheduler with ASan/UBSan,
  followed by both server builds and disposable gameplay/persistence journeys.
- Chunk 1 repairs bounded table matching, canonical pair repair and safe removal.
  It preserves the existing finite duration/refresh until the watcher lifetime
  change is qualified in a dependent PR. The callback clears stale state after
  temporary eligibility loss and continues checking its living owner.
- Baseline `366095875` independently fails three production-code harness cases:
  UBSan reports column 5 outside `int[5]`; ASan reports a freed affect read during
  cleanup; an existing single combat modifier stays incomplete. Logs and the
  baseline runner are private under ignored `bin/analysis/issue166/`.
- Chunk 1 proof passed: `python3 tests/async/test_innate_hatred.py` (seven modes,
  ASan/UBSan, real eligibility/visibility, effect removal/messaging and scheduler),
  `test_affect_wear_off_message_contract.py`, `test_innate_reflection.py`,
  `test_race_innate_help_sync.py` and `make -C src -j4`.
  The harness replaces world services and stat recalculation; pulse contributions
  use the real `affect_modify`. Running-server journeys remain required.
- Published chunk 1: [PR #209](https://github.com/LuminariMUD/Duris/pull/209),
  `b3ef7c89e`, base `master`. Review remains open.
- Chunk 2 is on `branch/issue-166-hatred-lifecycle`, based on #209. It makes
  both modifiers unlimited and event-owned, reserves one successor before retaining
  effects, clears them on scheduling refusal, clamps nonpositive timer values,
  and fixes the checked-in key without changing the one-second effective default.
  Normal PC entry starts one watcher even before unlock or during ineligibility;
  this avoids separate level/race-change hooks and permits recovery in place.
  Copyover recovery lacked normal entry scheduling and now starts Hatred explicitly.
- Chunk 2 focused proof passed: all ten Hatred harness modes, including real
  scheduler refusal/self-cancellation, repeated entry, short/default/long/missing/
  nonpositive timers, level unlock, temporary eligibility recovery, cancellation
  before releasing an owner, five affect ticks with a three-tick watcher interval,
  and legacy `writeAffects` omission. `test_player_snapshot_capture.py` now executes
  a real capture containing both Hatred tags and an unrelated saved affect.
  Scheduler/cancellation, Reflection, wear-off and race-help controls pass.
- Both required builds passed: `make -C src -j4` and `make -C src -j4
  PERSISTENCE_BACKEND=flatfile DMS_BINARY=../bin/server/dms_hatred_flatfile`.
  Build logs are under ignored `bin/analysis/issue166/`.
- Next: publish chunk 2 as a dependent PR, then add/run the disposable running-server
  journey on both persistence backends, including movement, visibility, sustained
  state, rent/relogin, reconnect and copyover. Record exact runtime evidence here.
- The production build, effective overrides and offending NPC trace are still
  unavailable. Keep the live root-cause gate open unless direct evidence resolves it.

## What the current code actually does

References below describe the reviewed commit, not a promise that moving master
or production still has the same contents.

1. **The intended race set is already explicit.**
   [constant.c](../../src/core/constant.c#L2109-L2113) contains
   `{ RACE_MOUNTAIN, RACE_ORC, RACE_DUERGAR, RACE_DROW, -1 }` followed by
   an all-`-1` row. [defines.h](../../src/core/defines.h#L1002-L1005) declares
   `MAX_HATRED=5`. [innates.c](../../src/classes/innates.c#L375-L485)
   grants Hatred at level 21; `has_innate()` also accounts for existing
   disguise/corpseform eligibility rules. Do not replace that check with race alone.

2. **Room and visibility restrictions already exist.**
   [event_hatred_check](../../src/classes/innates.c#L4368-L4446) skips self,
   uses `CAN_SEE`, and compares `GET_RACE(tch)`; it does not test "any NPC"
   or alignment. [utils.h](../../src/core/utils.h#L706-L708) enumerates only
   `world[ch->in_room].people`. `GET_RACE` is `player.race`, not a display
   name or disguised appearance. [ac_can_see](../../src/core/utility.c#L1673)
   owns sleeping, invisibility/detection, blindness, and other sight rules.
   There is no Hatred zone/plane filter to remove.

3. **The table traversal is defective.**
   The target loop permits column 5 although valid columns are 0 through 4;
   it also compares the in-row `-1` terminator instead of stopping there.
   The outer loop continues only while the current row already matches the actor
   (or is the sentinel, or a match was found), so it is not a correct search over
   multiple rules. Today there is only one playable row. Fix these bounds and
   selection errors without inventing additional rules. The adjacent sentinel
   does not make the out-of-bounds read valid, and it does not prove every NPC matches.

4. **Removal invalidates the callback's traversal.**
   [affect_from_char](../../src/magic/affects.c#L2121-L2134) removes every
   affect of the requested type. Calling it while walking the same list
   invalidates both the current Hatred node and possibly the saved next node.
   `affect_remove()` returns nodes to a memory pool; sanitizer silence alone
   would not establish safe lifetime. The callback also attempts to issue its
   wear-off message through an already-released node.

5. **One existing tag is incorrectly treated as a complete pair.**
   The callback refreshes any Hatred nodes, then adds both modifiers only if
   `get_spell_from_char()` finds none. It cannot repair one missing modifier,
   duplicates, or wrong modifier values. A normal repeated check is already
   silent; the repair must preserve that behavior.

6. **The current wear-off contract matters.**
   [wear_off_message](../../src/magic/affects.c#L2246-L2281) suppresses a
   message while another affect of the same type remains. Calling it once
   before bulk-removing a normal pair would therefore emit nothing.
   [skills.c](../../src/classes/skills.c#L5248-L5249) already owns the desired
   subsidence text. Reuse it and leave the shared message policy intact.

7. **Timer units and configuration disagree.**
   Both [login scheduling](../../src/account/nanny.c#L1293-L1296) and the
   callback read `innate.timer.hatred` directly as event pulses with fallback
   `WAIT_SEC`. [duris.properties](../../lib/duris.properties#L2032)
   instead defines `innate.timer.secs.hatred=4.000`.
   [properties.c](../../src/world/properties.c#L68-L101) performs an exact-key
   lookup; there is no alias. [config.h](../../src/core/config.h#L101-L103)
   defines four pulses per second and 300 pulses per affect tick.
   Thus the checked-in configuration gives a one-second Hatred check through
   fallback, not a configured four-second check. Live overrides remain unknown.

8. **Normal timing does not by itself explain repeated activation.**
   Both modifiers have `duration=1`. [affect_update](../../src/magic/affects.c#L3841-L3900)
   decrements 1 to 0 on one tick and removes it on a later tick unless refreshed;
   ordinary PC ticks are 75 seconds apart. A functioning one-second watcher
   should refresh them. Long overrides, interrupted scheduling, and eligibility
   loss require tests rather than an assumed timer root cause. The current
   early return on loss of the innate leaves existing affects to expire.

9. **Reuse existing lifecycle and persistence mechanisms.**
   [schedule_pc_events](../../src/account/nanny.c#L1275-L1310) starts the watcher
   at world entry; the callback rearms itself. [new_events.c](../../src/world/new_events.c#L767-L976)
   provides targeted cancellation and a scheduling result; ordinary `add_event`
   does not deduplicate callbacks. [extract_char](../../src/world/handler.c#L3796-L3802)
   removes affects and disarms character events.
   [writeAffects](../../src/core/files.c#L363-L391) and
   [capture_affects](../../src/player/player_snapshot_capture.c#L296-L306)
   omit `AFFTYPE_NOSAVE`. These support an event-owned transient pair, but
   reconnect, temporary ineligibility, and recovery still need executable proof.

10. **NPC appearance is not evidence of its loaded race.**
    The [mob loader](../../src/world/db.c#L2160-L2195) maps race codes through
    `race_names_table`, with `RACE_NONE` as the unmatched default; the legacy
    loader also performs a code lookup. Verify the loaded instance and its VNUM.
    These paths do not establish that an apparently ordinary NPC is unrelated,
    nor that all production mobs use the same definitions as this checkout.

## Implementation sequence

### 1. Establish a reproducible baseline and collect the missing runtime evidence

- Refresh master and issue comments before coding; recheck the paths above and
  record the new base if it moved. Keep this as one focused implementation branch.
- Build a disposable local/staging scene with a mortal level-21 mountain dwarf,
  an empty room, a verified ordinary NPC, and one NPC of each intended enemy race.
  Include a second room and another zone/plane. Use actual loaded race numbers
  and VNUMs, not names. Include a below-level-21 dwarf as a control.
- On the unchanged source, capture each callback's actor race/innate eligibility,
  room VNUM, candidate VNUM/actual race, visibility, selected row/column/value,
  Hatred count/locations/modifiers/durations, and activation/subsidence counts.
  Instrument only a disposable test build or the focused harness; retain raw
  evidence privately under ignored `bin/analysis/issue166/`.
- Reproduce the table boundary and unsafe cleanup in separate executable cases;
  one sanitizer abort must not hide the other. Also reproduce the missing-pair
  failure. Distinguish reproduced defects from cases that merely pass a baseline.
- Obtain owner-supplied or separately authorized read-only evidence identifying
  the running production executable/build and both effective timer-key values,
  plus a minimal trace for one offending NPC. Compare it with the local baseline.
  The issue explicitly does not authorize production instrumentation, code changes,
  player modification, or restarts.
- Test rapid movement versus waiting for a callback, sustained occupancy across
  affect ticks, rent/logout/relogin, and another zone. Classify any false positive
  as an actual race match, an invalid comparison/state, lifecycle behavior, or a
  deployed-code mismatch only when evidence supports that classification.
  If it cannot be reproduced or production evidence is unavailable, record that
  precise gap and keep the root-cause criterion open while repairing proven bugs.

### 2. Repair room matching and canonicalize the two affects

Primary implementation: [src/classes/innates.c](../../src/classes/innates.c).

- Separate the read-only room query from effect mutation with a small file-local
  function, returning the matching occupant if needed by the existing `act()` call.
  Select the actor's `GET_RACE` row by walking to the row sentinel; inspect enemy
  columns from 1 while `z < MAX_HATRED` and the value is not `-1`.
  The table's three constants are the single source of allowed enemies.
  Do not duplicate them in a second allowlist or use alignment/NPC status.
- Retain `has_innate()`, self exclusion, and `CAN_SEE`. Guard a missing/dead actor
  or `NOWHERE` before indexing the room. Preserve the existing distinction
  between innate eligibility and actual-race table selection; add disguise and
  corpseform cases so this repair does not silently grant a different race rule.
- Inspect all Hatred nodes before modifying them. A valid active state is exactly
  one `APPLY_COMBAT_PULSE=-1` and one `APPLY_SPELL_PULSE=-1`, with the intended
  transient/non-dispellable flags and lifecycle duration. Leave a valid pair in
  place on repeated checks.
- With a visible enemy and no Hatred state, add the pair and announce once.
  With a visible enemy and a partial, duplicate, or malformed Hatred state,
  silently replace only those tags with the canonical pair. Treat any existing
  Hatred tag as an already-active state for message purposes.
- With no valid condition, remove every Hatred node in a safe single-node walk:
  save its next pointer, call `wear_off_message()` while that node is still valid,
  then `affect_remove()` for that node only. The existing last-of-type guard
  emits exactly one subsidence message. Do not bulk-remove from inside that walk.
  Silent normalization may use `affect_from_char()` outside a list traversal.
- Keep both changes within one game-thread callback before returning to gameplay.
  Use the existing affect APIs so pulse recalculation and displays stay correct.
  Verify actual pulse contributions, not just list length. No generic transaction
  API or separate persistent "Hatred active" flag is needed.

### 3. Make the watcher own the pair's lifetime and scheduling

Expected touchpoints: [innates.c](../../src/classes/innates.c),
[nanny.c](../../src/account/nanny.c), and
[duris.properties](../../lib/duris.properties).

- Use the existing unlimited `duration=-1` convention for both Hatred modifiers,
  retaining `AFFTYPE_NOSAVE | AFFTYPE_NODISPEL`; the watcher removes the pair when
  the predicate becomes false. This removes independent affect-tick expiry
  instead of tuning a fragile duration against the interval.
- Complete the lifecycle protections in the same change: clear stale tags on
  loss of eligibility or a valid room; keep an established watcher able to recover
  after temporary ineligibility while its character remains alive. Do not let an
  early return strand permanent bonuses or permanently stop a resident's watcher.
  Trace level unlock, race/disguise restoration, linkdead reconnect, rent, death,
  extraction, and copyover entry; add a Hatred-specific start only where an actual
  entry/recovery path lacks one. Never reschedule an extracted/dead owner.
- Make starting the Hatred watcher idempotent using existing character-event
  inspection/cancellation, scoped to `event_hatred_check`. A callback schedules
  one successor. Prove repeated entry/reconnect cannot multiply it, without
  altering autosave or other innates' schedules. If sharing start/rearm code is
  needed by both callers, keep one small Hatred-specific function.
- Inspect the existing scheduling result. A failure must not leave an unlimited
  pair without a future owner callback. Use the existing failure/logging path and
  clear the pair safely; do not add a retry service or scheduler redesign.
- Preserve the current effective default cadence and supported runtime key:
  keep `innate.timer.hatred` in **pulses**, default `WAIT_SEC`, and replace the
  unused checked-in `innate.timer.secs.hatred=4.000` entry with
  `innate.timer.hatred=4.000` plus a units comment. Apply the same positive-delay
  policy at both scheduling sites; use the default for nonpositive values.
  Test missing, default, short, long, zero, and negative settings.
  Record any live override before rollout and retain that effective value.
  Changing the default to four seconds is a separate balance decision.
- Prove generic expiration leaves the pair intact over multiple ticks, including
  an interval longer than a tick. Prove entry/persistence reconstructs transient
  state from current room conditions and never restores saved Hatred tags.

### 4. Add focused executable regressions and complete gameplay acceptance

Use [tests/async/_paths.py](../../tests/async/_paths.py) and the native-harness
pattern in [test_innate_reflection.py](../../tests/async/test_innate_reflection.py).
Add `tests/async/test_innate_hatred.py`, discovered by the existing runner.
Compile the production callback/query, real table, eligibility, and relevant
affect/messaging code; do not test a separately reimplemented algorithm.

The harness must execute the production removal and wear-off logic. Use a
freeing/poisoning pool adapter or equivalent checked lifetime tracking so released
nodes cannot remain harmlessly readable. Use the real scheduler for event-count,
rearm, and cancellation cases, following
[test_nevent_scheduler_runtime.py](../../tests/async/test_nevent_scheduler_runtime.py)
and [test_nevent_cancellation_runtime.py](../../tests/async/test_nevent_cancellation_runtime.py).
Stub unrelated world services only. Build with ASan/UBSan (including bounds
checking) and put generated files under `bin/tests/`.

Required cases:

- Empty and self-only room; ordinary non-hated NPCs; every configured enemy race;
  multiple enemies; an enemy in another room; NPC and player enemy targets;
  `RACE_NONE`, sentinel `-1`, and out-of-range target values rejected.
- Non-mountain actor and level 20/21 boundary; existing transformed-actor eligibility
  semantics; hidden/invisible enemy with and without detection; blind/asleep actor.
  Exercise real visibility in the integration cases, not only a boolean stub.
- Inactive -> active -> repeated checks -> inactive -> repeated checks, then
  re-entry: exact message counts and one pair, regardless of occupant order.
  A visible-to-hidden change must deactivate on the next check.
- Missing either modifier, duplicate pairs, wrong locations/values, and unrelated
  interleaved affects: silently normalize when active, clear once when inactive,
  preserve all unrelated effects, and verify the aggregate pulse deltas.
- Affect tick before/after the watcher, multiple ticks of sustained presence,
  changed timer settings, and transient eligibility loss/recovery.
- Idempotent scheduling, one successor per callback, scheduling refusal, extraction
  cancellation, and no lingering callback against a released character.
- Flat-file and snapshot serialization omit Hatred; rent/logout/relogin restores
  exactly one watcher and recomputes the pair. Cover linkdead reconnect and
  copyover as lifecycle checks for the new unlimited duration.

For the actual server journey, extend/reuse the disposable scene/client support in
[test_flatfile_combat_journey.py](../../tests/async/test_flatfile_combat_journey.py)
and the isolated database setup pattern in
[test_mysql_playtime_journey.py](../../tests/async/test_mysql_playtime_journey.py).
Add only the Hatred scenarios required here, with synthetic characters and known
NPC definitions. Exercise normal movement, visibility, timing, and relogin in the
running server. Check both supported persistence paths for transient-effect
round-trips; do not run unrelated database migrations against a configured server.

Implementation verification, from the worktree root:

```sh
python3 tests/async/test_innate_hatred.py
python3 tests/async/test_affect_wear_off_message_contract.py
python3 tests/async/test_innate_reflection.py
python3 tests/async/test_race_innate_help_sync.py
python3 tests/async/test_nevent_scheduler_runtime.py
python3 tests/async/test_nevent_cancellation_runtime.py
./scripts/format.sh --check
git diff --check
make -C src
make -C src PERSISTENCE_BACKEND=flatfile DMS_BINARY=../bin/server/dms_hatred_flatfile
```

Record the final journey invocation, backend, source SHA, binary identity, timer,
NPC races/VNUMs, message counts, and resulting affects in this plan. Extend an
existing persistence test only if its actual path needs new coverage. Follow
[TESTING.md](../guides/TESTING.md) and the installed commit hooks; run additional
checks only for changed dependencies or observed failures. Hosted CI is reported
separately and is not a required wait.

Complete an authorized staging/in-game acceptance session using the repaired
binary: all three enemy races, ordinary NPCs, empty rooms, visibility changes,
rapid/waited movement, another zone/plane, sustained presence, and relogin.
Do not call the reported live problem resolved without its root-cause evidence
and this acceptance record. Production rollout remains separately authorized.

## Completion gates and handoff

Keep these unchecked until the named evidence exists:

- [ ] The reported any-NPC activation has an evidence-supported explanation using
      the actual loaded build/races/trigger trace; source defects alone do not count.
- [ ] Eligible mountain dwarves match only visible Orc/Duergar/Drow occupants in
      their current room; negative race/level/visibility cases pass.
- [ ] Transition messages occur exactly once and unchanged state/normalization is silent.
- [ ] Both intended pulse modifiers remain together, without duplicates or partial
      state, and both disappear when the condition ceases at the next check.
- [ ] Bounds, released-node access, event uniqueness, and lifecycle regressions
      pass executable sanitizer checks, including other innates' controls.
- [ ] Formatting, required server builds, transient persistence journeys, and
      authorized staging/in-game acceptance pass on the recorded implementation.
- [ ] The plan records remaining live evidence or rollout work explicitly; close
      #166 only when its acceptance requirements are met.

Publish incremental implementation commits on this branch and open one focused
PR against refreshed master when the code and focused proof are ready. Reference
#166 without auto-closing it while root-cause or live acceptance remains open.
Refresh refs and validate the final affected source after integration; preserve
linear history and unrelated work. This planning request does not merge or deploy.

## Estimate

Allow **12-20 engineering hours, approximately 2-3 working days**, for one engineer
familiar with this repository, assuming a usable local/staging environment:

- Reproduction, runtime evidence comparison, and lifecycle trace: 2-4 hours.
- Matching, effect lifecycle, timer, and scheduling repair: 3-5 hours.
- Executable regressions, sanitizer qualification, and builds: 4-6 hours.
- Persistence/gameplay journeys, review repairs, and final evidence: 3-5 hours.

This is an estimate for implementation and local/staging qualification, not a
promise of live closure. Waiting for production build/trace evidence or an
authorized rollout is additional elapsed time. If the verified live false positive
persists after the proven defects are repaired, investigate that result and
re-estimate from its evidence rather than declaring the issue fixed.

## Planning validation

This plan is based on current source, caller, configuration, serialization, and
test-harness inspection. No gameplay or sanitizer reproduction is claimed during
planning; the verification commands above are implementation work still to run.
Before publication, verify linked repository paths, the preserved #67 document,
the narrow documentation diff, and local/remote branch parity. No C/C++ change,
server build, production access, deployment, or operational diagnostic is part
of this planning commit.
