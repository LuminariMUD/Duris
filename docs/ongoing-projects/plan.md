# Issue #428: keep missed starter arrows recoverable

Status: **planned; implementation has not started**. Updated 2026-10-28.
Issue: [Duris #428](https://github.com/LuminariMUD/Duris/issues/428).
Owner: `moshehbenavraham`.
Branch: `branch/issue-428-starter-arrow-decay`, based on `master` at
`8e95eb5dddfb6c9dddd7765921ded420696369f6`.

The prior Conjurer plan is preserved byte-for-byte in
[plan-issue-215.md](plan-issue-215.md). The earlier telemetry delivery plan is
[plan-issue-59.md](plan-issue-59.md).

## Selection and availability

Reviewed the complete open issue lists for this project on 2026-10-28:
16 GitHub issues in `LuminariMUD/Duris`, 16 GitLab issues/work items in the
`max757/duris` mirror, and no additional open GitLab tasks. Cross-checked four
open GitHub pull requests and zero open GitLab merge requests. No matching
arrow-fix PR or existing development branch was found for #428 before pickup.
The mirror's open records date from October 3-8 and require comparison with
current GitHub master; an open mirror record alone does not establish unfinished
implementation.

Choose #428 for confirmed player impact, a directly traced cause, no existing
assignee or competing PR, a small production change, and concrete executable
acceptance criteria. It also removes a defect that would otherwise be spread by
starter-kit enhancement #429, without taking on that enhancement.

Other GitHub candidates were considered:

- #439 is a more serious potential locker-state/lifetime failure, already
  assigned and investigated. It needs coordinated extraction, idle, descriptor,
  save/retry and shutdown work. #428 is the more bounded immediately deliverable
  repair; this does not downgrade #439's importance.
- #421 is a confirmed pet/group-output bug, but overlaps active terminal/group
  edits in the original checkout. Do not duplicate that work.
- #419 needs intentional key disposal coordinated with durable custody and
  backend recovery. #418 needs a consistent key/relocking policy. #420 explicitly
  awaits the intended Reflection-versus-summon-capacity rule.
- #438 is a small help-display defect, currently labelled enhancement; losing
  usable starter ammunition has greater direct gameplay impact.
- #429, #436, #437 and #214 are enhancements or gameplay policy/balance work.
  #97 is a broad readiness checklist. #38, #52, #65 and #185 are future-labelled
  or broader efforts; #52 also has its own assigned worktree.

All 16 GitLab records were screened: #8, #9, #12, #15, #16, #19, #20, #21,
#22, #23, #24, #25, #26, #27, #28 and #29. They cover older display/shop fixes,
connection limits, flight/quantity-purchase features, capacity and lifecycle
qualification, security/site maintenance, telemetry, trophies and builder work.
For the bug-labelled alternatives, current source already has the deadlines and
bounded subprocess diagnostics described as missing in #22; the reporting URL
and libcurl baseline have advanced since #21; README repository links have
advanced since #25. Other visible drift includes newer DOMPurify in #9 and
reserved Studio tags in #28. These observations are not a claim that every
acceptance criterion on those records is complete. No mirror item was changed
or closed, and no matching mirror arrow issue was found to link.

## Outcome

A newly granted regular legacy starter missile that misses in an ordinary dry
room must survive scheduled event processing and remain recoverable through its
owner's normal `gather` command. Cover both a same-room miss and a miss landing
in the adjacent room. Preserve arrow identity, condition, quiver count and
encumbrance across fire/gather cycles.

Preserve ordinary ammunition, successful-hit wear/scrapping, returning/cursed
arrows, other transient gear and existing starter-grant publication/ownership.

## Non-goals and explicit compatibility decisions

- Do not implement #429, change class/race kit access, counts, admission masks,
  Chaos kits, damage, accuracy, terrain rules or quiver capacity.
- Keep the starter bow's added transient flag and the quiver's prototype
  transient flag. Deliberately dropping either retains today's dissolution
  behavior; neither must land on the floor for an ordinary missed shot.
- Exempt missiles only from the flag added by this grant path. Do not clear a
  transient flag authored on a prototype or supplied by another legitimate path.
- Previously granted arrows retain their saved flags. This fix applies to new
  materializations, including later grants through the same legacy path; it does
  not repair old instances or resurrect arrows already destroyed. Document that
  limit. Do not infer origin from VNUM or the `newbie` keyword, rewrite saves,
  add load-time normalization, or perform a production inventory migration.
- No global decay exception, firing-time flag rewrite, schema, setting, new
  service, generic policy helper or grant-coordinator refactor is needed.
- This task publishes the plan only. Implementation, PR review/merge and
  production deployment are subsequent work.

## Source evidence and files

Inspected the following on the baseline above; line numbers may move:

- `src/account/nanny.c:1127`: `materialize_legacy_newbie_item()` instantiates a
  detached object. For regular PC grants it sets cost to one and adds
  `ITEM_TRANSIENT` unless the type is exempt. Missiles are missing from that
  list. `load_obj_to_newbies()` supplies the existing bounded grant coordinator.
- `src/account/newbie_kit_plan.c:537` and `:1604`: half-elf and wood-elf Ranger
  rows include quiver 1116, ten missiles 1117 and bow 1118.
- `areas/obj/heavens.obj`: missile 1117 has flags 1032 without the transient bit;
  quiver 1116 has 525320 including it. Bow 1118 has flags 8 before materialization.
  `src/core/defines.h` defines `ITEM_TRANSIENT` as `BIT_20`.
- `src/combat/range.c`: `do_fire()` sends a non-returning miss to `obj_to_room()`
  without hit-related condition loss. `do_gather()` requires the shooter's PID
  mark and gathers from the room in which the player now stands.
- `src/world/handler.c::obj_to_room()` schedules `TAG_OBJ_DECAY` at delay zero
  for transient objects outside lockers; `src/magic/affects.c::event_obj_affect()`
  dispatches that tag to `Decay()`.
- `tests/async/test_fired_missile_encumbrance.py` already runs real fire/gather
  and container-weight functions under ASan/UBSan, but stubs room placement,
  forces same-room misses and aborts on hit-only services. Its existing green
  result cannot prove this defect fixed.
- `tests/async/test_flatfile_newbie_regrant_journey.py` supplies isolated legacy
  prototypes, real grants and a snapshot inspector; it and
  `test_flatfile_combat_journey.py` provide reusable socket/build helpers.

Expected implementation edits: `src/account/nanny.c`, the existing missile
regression, and `docs/reference/LEGACY_STARTER_KITS.md`. Extend the existing
newbie journey for the command/event acceptance where practical; if its regrant
and observer scenario would become tangled, add one focused starter-arrow
journey using those existing helpers. Do not create a new harness framework.
`range.c`, `handler.c`, `affects.c`, kit tables and area prototypes are exercised
inputs, not planned production edits.

## Ablated implementation sequence

1. **Expose the missing boundary in a focused regression.** Extend the existing
   fire/gather harness to materialize production starter missiles and execute
   actual room placement. Exercise the scheduled decay callback for the old
   transient control rather than only counting a requested tag. Use production
   functions with controlled RNG/services, not a copied conditional. The starter
   miss/survival assertion must fail against the unmodified baseline.
2. **Correct the flag at its source.** Add `ITEM_MISSILE` to the existing
   materializer exemption list. Retain costs, prototype flags, keywords,
   spellbooks, NPC behavior and the grant coordinator unchanged. No new helper.
3. **Prove the real route and preserved behavior.** Exercise a real freshly
   granted Ranger kit in a disposable non-Chaos server, wear/load the quiver and
   bow, observe a miss, allow event pulses, and gather. Repeat across an adjacent
   exit after moving to the landing room. Reuse native deterministic cases for
   hit wear, zero-condition scrapping, returning shots and controls. Assert UID,
   condition, counts and weights rather than only the absence of a crumble line.
4. **Document and qualify.** Update the starter-kit reference with the missile
   exemption, preserved bow/quiver behavior and old-instance limitation. Record
   the exact test evidence here, reread the diff, and retain only required work.

Ablation keeps one source condition plus proof of the actual failure path.
It removes a proposed need for general transient-item policy machinery,
retroactive migration and the adjacent #429 enhancement: none is required to
make newly granted arrows recoverable. Executing room placement/event handling
and a command journey stays in scope because the existing stub misses the bug.

## Proof and acceptance

- Fresh half-elf and wood-elf Ranger grants produce the expected missile count,
  normal cost/keywords and no grant-added transient bit. Prototype-authored
  transient flags remain intact, including an explicitly flagged missile control.
- Same-room and adjacent-room misses leave the same arrow UID at full condition
  after event processing. The owner can gather it; a different PID cannot.
  Repeated cycles restore quiver count/weight and carried encumbrance exactly.
- Ordinary missiles behave identically. Returning/cursed missiles stay in the
  quiver. Controlled successful hits still wear and scrap missiles as before.
- Another transient object still schedules and completes decay. Bow/quiver
  dropping still uses the current policy. No general decay code changes.
- The real grant-to-fire-to-event-to-gather journey passes in isolated state;
  native harness coverage and socket coverage are reported separately.

Planned local commands after implementation:

```sh
python3 tests/async/test_fired_missile_encumbrance.py
python3 tests/async/test_newbie_kit_plan.py
python3 tests/async/test_newbie_kit_suitability.py
python3 tests/async/test_newbie_grant_lifecycle.py
# Run the extended newbie journey or its focused starter-arrow entry point.
make -C src
./scripts/format.sh --check
python3 tests/async/test_documentation_contract.py
git diff --check
```

Use the existing flat-file journey build helper for its disposable server.
Confirm development/test configuration before any runtime work. Keep compiled
artifacts under `bin/`; use synthetic accounts and private state, never existing
player files or production. A full burn-in, live-world acceptance and CI waiting
are not completion gates for this focused repair. Report any unavailable check.

## Estimate and planning validation

Estimated **2-3 hours of my active implementation time**, including the focused
regressions, isolated command/event journey, required build, documentation and
reviewable commit. The production edit is small; most time is in proving the
real decay boundary and preserved hit/returning behavior. Allow up to 4 hours if
the existing journey fixtures require additional setup. This excludes external
review, merge scheduling, deployment and any separately requested old-item repair.

Planning validation is recorded below before publication. No implementation or
post-fix runtime result is claimed by this document.

Planning checks on the baseline (2026-10-28):

- `python3 tests/async/test_documentation_contract.py`: all 14 tests passed.
- `python3 tests/async/test_fired_missile_encumbrance.py`: 96 scenarios, 50 cycles
  each passed under ASan/UBSan; room placement is stubbed, so this is a baseline
  compatibility result, not proof of missed-arrow survival.
- `python3 tests/async/test_newbie_kit_suitability.py`: 603 normal
  race/class/alignment cases and all four existing review regressions passed.
- `git diff --check`: passed. The prior plan's SHA-256 is unchanged after the move.
- Only planning documents changed. No production C/C++ change or full server
  build was required for this planning commit; implementation checks remain open.
