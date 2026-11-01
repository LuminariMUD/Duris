# Issue #505: headbutt feedback when no damage is delivered

Updated 2026-11-01. **Implementation plan; runtime behavior has not yet been qualified.**

- Issue: [LuminariMUD/Duris#505](https://github.com/LuminariMUD/Duris/issues/505).
- Owner: `moshehbenavraham`.
- Branch: `branch/issue-505-headbutt-feedback`.
- Local worktree: `/home/aiwithapex/projects/duris-issue-505`.
- Inspected base: `origin/master` at `0a972227636b66c4e0c98900b1120c25ac181353`.
- This replaces the shared plan's completed #498 handoff on this branch only;
  [that handoff remains available at the inspected base](https://github.com/LuminariMUD/Duris/blob/0a972227636b66c4e0c98900b1120c25ac181353/docs/ongoing-projects/plan.md).

## Outcome

A valid headbutt that reaches damage resolution must tell its user what happened
when it causes no damage, including full ward absorption and integer-zero damage.
Give accurate feedback to the attacker, victim and an eligible room observer,
including terse users. Preserve ward protection and consumption, damage formulas,
random calls and their order, combat engagement, waits, cooldown affects,
knockout/stun behavior and the double-headbutt decision.

Separate a demonstrated reproduction from the original production report. The
report lacks target, affects, toggles and an exact transcript. A local reproduction
can establish a matching failure mode, not prove which state that player had.

## What the current source actually establishes

The following anchors refer to the inspected base, not the issue's older SHA.

1. `src/cmd/interp.c:3387` registers `do_headbutt` for a standing, normally
   functioning character. `src/cmd/actoff.c:5326-5690` performs admission checks,
   chooses catastrophic failure, ordinary failure or success, and may attempt a
   second headbutt. The two failure calls reverse damage roles: the selected
   target is the damage source and the headbutting character is the recipient.
2. `src/combat/damage.h:18` defines **`DAM_NONEDEAD` as `0`**.
   `melee_damage()` returning zero after full absorption therefore does **not**
   trigger `do_headbutt()`'s `!= DAM_NONEDEAD` early return. Cooldown, double-hit
   and stun/knockout code can still run. The issue's causal account must be
   corrected rather than turned into a return-value change.
3. `src/combat/fight.c:392-445`, `check_damage_ward()`, already emits ward
   absorption text. Affect wards address attacker, victim and room; the innate
   `GET_WARD` branch addresses attacker and victim. Those calls use
   `ACT_NOTTERSE`. The recipient filter in `src/net/comm.c:5693-5711` suppresses
   that text for PC recipients with `PLR2_TERSE`. A wholly absorbed first hit
   with no double headbutt can consequently have no attacker-facing result text
   in terse mode. Non-terse full absorption already has ward feedback.
4. `src/combat/fight.c:4978-4980` subtracts wards and returns zero when the
   remaining integer damage is nonpositive, before ordinary hit messaging.
   `PHSDAM_NOREDUCE` does not bypass this ward check. Headbutt success truncates
   its computed float before calling melee damage; its second hit truncates
   half damage separately. Zero input can take the same return without a ward
   message. The ordinary backfire also allows physical reductions before this
   return, whereas success and catastrophic backfire use `PHSDAM_NOREDUCE`.
5. The return value reports death outcomes, not whether damage was delivered.
   The existing optional `int *damAccumulator` parameter
   (`src/core/prototypes.h:1100`, `src/combat/fight.c:4835`) supplies a narrower
   solution: early no-damage returns leave a fresh counter at zero; delivery
   forwards it to `raw_damage()`, which increments it after damage calculation
   (`fight.c:5686-5687` for training dummies and `5792-5793` normally).
   The extra Warring Zeal delivery also shares the counter. Treat it as the
   existing damage-delivery signal, not a reason code or a measurement of net
   HP change after healing/counterattacks.
6. Most admission failures already explain themselves in `do_headbutt()` and
   `src/classes/new_skills.c:228-372` (`CanDoFightMove`). Dead actors and special
   training-dummy restrictions are separate admission paths. Do not force a
   generic hit result onto a rejected command or assume every raw-damage early
   return means ward absorption. Double headbutt already has explicit attempt
   messages before its second damage call.

These are source findings. No original-player session or booted reproduction
has been performed for this plan.

## Implementation sequence

### 1. Establish the baseline and preserve the mechanics

- Add a focused executable regression using the existing native-harness pattern
  in `tests/async/_paths.py` and `harness_stubs.cpp`. Execute production
  `do_headbutt`, `melee_damage` and ward resolution; do not stub absorption as
  merely `return 0`. Capture recipient text, per-call damage and ward state.
- Give the attacker, target and observer real descriptor fixtures. Reproduce
  full absorption by an affect ward and by innate ward capacity, first with
  terse off and then on. Keep the victim standing, use nonlethal disposable
  fixtures and control the double-headbutt and stun rolls.
- Record the baseline: ordinary output, exact integer ward consumption, HP,
  damage-call count, engagement, waits/affects, and the random-call sequence.
  Include an unwarded integer-zero successful hit and low ordinary backfire
  damage reduced to integer zero. Use the current formulas and properties;
  do not change stats or configuration in the normal game to create a case.
- Trace any different observed silent return to its actual owner before editing.
  Keep the source-demonstrated terse/zero gaps in scope even if a particular
  ward setup does not reproduce the production report. Record remaining
  report uncertainty explicitly.

### 2. Add feedback at the headbutt command owner

- Pass a freshly zeroed local damage accumulator to each of the four existing
  `melee_damage()` calls: catastrophic backfire, ordinary backfire, first
  success and optional second success. Reset it for each blow so damage from
  the first cannot hide an absorbed second blow.
- Preserve the existing death-result checks before inspecting characters or
  emitting any fallback. After a surviving call with no accumulated damage,
  emit headbutt-specific no-harm text through existing `act()` recipients
  `TO_CHAR`, `TO_VICT`, and `TO_NOTVICTROOM`, with no `ACT_NOTTERSE` flag.
  Resolve messages in the original command's actor/target roles, including
  reversed damage calls on failure.
- Use neutral, accurate wording: the headbutt caused no harm. Do not claim that
  it injured, stunned or killed anyone, or that a ward caused every prevented
  hit. Existing non-terse ward text may still explain absorption; the new
  line supplies the missing command outcome. Retain normal visibility, awake,
  ignore and room eligibility rules from `act()`.
- Leave ordinary positive-damage and death messages on the current path. Keep
  the double-headbutt lead-in; a no-harm outcome for that second blow is distinct
  from its attempt announcement. Share a small command-local piece only if
  needed to keep the four call sites clear; add no general combat framework.
- Do not move damage, ward checks, random calls, waits, affects or control effects.
  In particular, full ward absorption currently does not prevent the later
  headbutt knockout/stun logic. Preserve that behavior in this feedback fix.

### 3. Prove the command and actual output delivery

The focused native regression must cover:

- Full absorption with affect and innate wards, partial absorption, exact ward
  depletion and no ward. Assert current HP/ward changes before and after the
  change, rather than imposing a new interpretation of ward rounding.
- Terse on/off for attacker, victim and observer; correct recipient names and
  roles; room feedback for innate absorption; no extra no-harm outcome on a
  positive-damage hit. Existing non-terse ward text remains intact.
- Humanoid and non-humanoid success messages, ordinary and catastrophic
  backfire, and double headbutt. Cover both zero/zero and positive/zero blows
  and a ward depleted between blows. Confirm unchanged skill rolls, damage
  calls, waits, short affects and knockout/stun decisions.
- Integer-zero input without a ward, and ordinary failure reduced below one
  before ward subtraction. Never fix those cases by raising minimum damage.
- Death/extraction return outcomes without fallback access to dead characters;
  existing refusals such as self-target, unreachable size, immaterial target,
  active cooldown and unsafe combat still follow their established feedback.

Add one short isolated-server journey using the maintained `IsolatedServer`,
character creation/staff promotion and mini-world fixture patterns from
`test_account_recovery_journey.py`, `test_flatfile_combat_journey.py` and
`test_gmcp_control_journey.py`. Use disposable characters/targets and a witness,
private runtime state and loopback ports. Submit the real `headbutt` command
through normal dispatch. Capture attacker/victim/room transcripts and state
snapshots for full absorption in both terse modes; compare ordinary/partial
hits, backfire and a double attempt. Use deterministic native fixtures for
rare random branches rather than changing production RNG or relying on retries
as the sole proof. The booted journey must establish real recipient filtering;
a test double for `act()` cannot prove terse output reaches a player.

Keep sanitized transcripts and state evidence under ignored
`bin/qualification/issue505/`, with source and binary hashes. Preserve baseline
and changed results. No real account, production data or checkout `.env` is
needed by the isolated runner.

### 4. Review, document and hand off

- Run the new focused tests listed below.
  Run repository formatting and build requirements after C/C++ edits.
- Read the final diff and remove task-created scratch code and unnecessary
  machinery. All generated binaries and qualification artifacts stay in `bin/`.
- Update this plan and #505 with the demonstrated conditions, source/binary
  revisions, commands and results. Say that the original reported session is
  still unattributed unless new evidence establishes it. Link the implementation
  review to #505; keep it open until the implementation and proof are complete.

## Files

Expected production edit: `src/cmd/actoff.c` only, at `do_headbutt`.

Focused proof: new `tests/async/test_headbutt_feedback.py` and
`tests/async/test_headbutt_feedback_journey.py`, reusing existing harness and
isolated-server helpers. Keep any native fixture in the focused test's existing
extraction/build pattern instead of adding shared test infrastructure.

Documentation: this `docs/ongoing-projects/plan.md` and the linked issue/review.
`fight.c`, `damage.h`, `comm.c`, core message structures and their public
interfaces are inspected dependencies, not planned production edits. Revisit
that boundary only if the baseline demonstrates a requirement the existing
accumulator cannot satisfy.

## Ablation decisions and non-goals

Keep the per-blow delivery counter, correct three-recipient feedback, baseline
mechanics comparison and real command/output journey: removing any of them
leaves either a reported path or a concrete regression risk unproven.

Reuse the existing accumulator and `act()` instead of adding a combat result
enum, callback, global feedback flag, new message-structure fields or duplicate
ward calculation. Do not infer absorption from HP deltas or call the consuming
ward helper twice. Do not remove terse filtering globally: that changes the
verbosity of every attack. Drop unrelated bash/movement regression suites because
this plan changes no shared combat or output implementation. No ward arithmetic
repair, minimum-damage adjustment,
Monk balance work (#214), protocol expansion, storage/schema migration, new
configuration, persistence campaign, full burn-in, deployment or release tag is
part of this issue. No production operations and no CI wait are required.

## Proof and completion criteria

Planned implementation commands, from this worktree:

```sh
python3 tests/async/test_headbutt_feedback.py
python3 tests/async/test_headbutt_feedback_journey.py
./scripts/format.sh --check
make -C src
```

The new journey should obtain a fresh isolated flatfile binary through the
existing `build_flatfile_server` helper. The regular `make -C src` build remains
required by `AGENTS.md`. Do not broaden to unrelated suites after these pass
unless an actual failure or new evidence requires it.

Done means every admitted no-damage headbutt branch has accurate visible
feedback for eligible recipients, ordinary behavior and all recorded mechanics
are unchanged, focused executable checks and booted output qualification pass,
and the review contains only the necessary implementation, tests and plan update.
A green helper test alone does not close #505 or verify the original production
report. Document any unavailable proof explicitly.

For this planning change, validate source anchors and local links, review the
one-file diff, run `git diff --check`, and verify the pushed commit. Runtime
builds/gameplay tests above are future implementation work, not results claimed
by this plan.

## Estimate for me to implement

**3-5 hours of active agent work** from this plan to an implemented, locally
qualified review: roughly 30-45 minutes for the baseline fixture, 30-45 minutes
for the command change, 60-90 minutes for focused regressions, 45-75 minutes for
builds and the isolated three-viewpoint journey, and 15-30 minutes for final
review and handoff. This excludes deployment, external review waiting and any
newly evidenced root cause outside the traced feedback paths. Revise the
estimate if baseline execution changes that scope.
