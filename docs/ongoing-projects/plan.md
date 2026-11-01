# Issue #505: headbutt feedback when no damage is delivered

Updated 2026-11-01. **Implemented and locally qualified; ready for review.**

- Issue: [#505](https://github.com/LuminariMUD/Duris/issues/505).
- Review: [PR #557](https://github.com/LuminariMUD/Duris/pull/557).
- Branch: `branch/issue-505-headbutt-feedback`.
- Worktree: `/home/aiwithapex/projects/duris-issue-505`.
- Inspected baseline: `0a972227636b66c4e0c98900b1120c25ac181353`.
- [The original implementation plan](https://github.com/LuminariMUD/Duris/blob/5e3ab6d560a313a275a730c80a52c4f41ecde3fe/docs/ongoing-projects/plan.md)
  and [the previous completed #498 handoff](https://github.com/LuminariMUD/Duris/blob/0a972227636b66c4e0c98900b1120c25ac181353/docs/ongoing-projects/plan.md)
  remain in Git history. The completed backup qualification from merged
  [PR #556](https://github.com/LuminariMUD/Duris/pull/556) is preserved separately
  in [plan-issue-537.md](plan-issue-537.md); its production and restore evidence
  is retained. [plan-issue-498.md](plan-issue-498.md) retains the protocol handoff.

## Outcome and source findings

An admitted headbutt now gives accurate zero-damage feedback to its user, target
and eligible room observers, including terse users. This covers fully absorbed
wards, integer-zero input and backfires. Each blow of a double headbutt gets its
own outcome. Ordinary damage and death messaging stay on their existing paths.

Source review corrected the issue's causal account:

- `src/combat/damage.h` defines `DAM_NONEDEAD` as zero. A ward stopping damage
  therefore does not trigger headbutt's `!= DAM_NONEDEAD` early return.
- `src/combat/fight.c::check_damage_ward()` already emits absorption messages.
  Those messages use `ACT_NOTTERSE`, which `src/net/comm.c::act()` suppresses
  for terse PC recipients. Affect wards address three views; innate ward text
  addresses attacker and victim. The ward path precedes ordinary hit messaging
  even with `PHSDAM_NOREDUCE`.
- Integer-zero damage can reach that same early return without a ward message.
  The two backfire branches reverse damage-source/recipient roles.
- The existing damage accumulator distinguishes an uninjured damage resolution
  from an ordinary surviving hit without changing the damage API. It measures
  delivered damage, not net HP after healing or a particular prevention reason.

The isolated baseline server reproduced the reported *kind* of empty response:
full ward absorption with terse enabled produced only the attacker's prompt,
no result text for the victim or observer, unchanged target HP, and consumed
ward capacity. The changed server emitted the new outcome to all three views.
This establishes a matching failure mode. The original production report still
has no target, affects, toggles or exact transcript, so its precise cause remains
unattributed.

## Implementation and ablation

**Production file:** `src/cmd/actoff.c`, inside `do_headbutt()` only.

One command-local lambda wraps its four existing damage calls. Every call gets a
fresh accumulator; zero delivered damage with `DAM_NONEDEAD` emits three `act()`
messages without terse suppression. Backfire text uses the original command's
actor/target roles. A terminal return skips feedback and preserves the caller's
existing immediate return. Double-hit attempt announcements remain distinct from
the outcome of each blow.

Examples:

- Attacker: `Your headbutt does no damage to Wardtarget.`
- Victim: `Headbutter's headbutt does no damage to you.`
- Observer: `Headbutter's headbutt does no damage to Wardtarget.`
- Backfire: `Your headbutt backfires, but does no damage to you.`

The neutral wording does not invent a ward reason or imply that stun/knockout
was prevented. Full absorption can still lead to those existing control effects.
Visibility, awake, ignore, room and elevation filtering remain owned by `act()`.

Reused the accumulator, native harness helpers, isolated-server lifecycle,
WebSocket client and offline snapshot writer. Kept the native mechanics comparison
and real dispatch/output journey because each proves a different requirement.
No combat result enum, global verbosity change, new flags, message-structure fields,
duplicate ward calculation or shared test framework was needed. No changes to
ward arithmetic, damage floors, properties, random rolls, control effects,
Monk balance (#214), protocol or persistence behavior. Unrelated bash/movement
suites and a full burn-in were excluded because no shared implementation changed.

## Proof

Focused tests added:

- `tests/async/test_headbutt_feedback.py`: production headbutt, melee reductions
  and consuming affect/innate wards under ASan/UBSan, with deterministic raw-HP
  and world-service fixtures. All **214 scenarios pass**: all eight combinations
  of recipient terse settings; full/partial/exact/depleted wards; ordinary and
  non-humanoid hits; ordinary/catastrophic backfires; integer zero and reduced
  backfire damage; zero/zero and positive/zero doubles; knockout/stun branches;
  raw prevention; admission refusals; observer filtering; and all three terminal
  results on the first and second blows. Terminal fixtures poison character
  memory to detect feedback or continued command work after a terminal result.
- The identical harness compiled with the baseline command fails only the
  expected missing-feedback assertion. Its **214 mechanics records exactly match**
  the changed command: HP, ward balances, engagement, skill-notch count, random
  bounds/results/order, waits and short-affect/control-effect calls.
- `tests/async/test_headbutt_feedback_journey.py`: an isolated flatfile server,
  three disposable accounts, copied mini-world and offline synthetic snapshots.
  Actual WebSocket `game` input dispatches `headbutt`; actual raw damage and
  `act()` produce captured attacker/victim/observer output. Staff `stat char`
  observes HP and ward state before and after each attempt. Both baseline and
  changed binaries pass six qualifying scenarios: full absorption with terse
  off/on, partial absorption, ordinary hit, warded backfire and a warded double.
  Native fixtures cover rare branches deterministically; live retries select
  actual outcomes without replacing RNG. Legal Mercenary fixtures account for
  login skill floors and the level-56 double-headbutt grant.

Commands completed successfully from this worktree:

```sh
python3 tests/async/test_headbutt_feedback.py
python3 tests/async/test_headbutt_feedback_journey.py
python3 tests/async/test_headbutt_feedback_journey.py \
  --server bin/qualification/issue505/baseline-build/server/dms_new --baseline
./scripts/format.sh --check
make -C src -j8
make -C src
git diff --check
python3 -m py_compile tests/async/test_headbutt_feedback.py \
  tests/async/test_headbutt_feedback_journey.py
```

The ordinary MariaDB-enabled server build and fresh flatfile qualification builds
passed with the repository's warning-as-error flags. The standard commit hooks
also check staged formatting and changed-line tidy before publication. No CI wait
is required by `AGENTS.md`.

Ignored local evidence is in `bin/qualification/issue505/`:
`baseline-native.log`, `native.log`, `native-comparison.txt`,
`baseline-journey.log`, `baseline-journey.json`, `journey.log`, `journey.json`,
`build.log` and `build-final.log`. Journey JSON includes sanitized gameplay
transcripts, observed before/after state, source hashes and binary hashes.
Both recorded binaries remain under `bin/`; their hashes and the changed source
hashes were verified against the actual files. Booted runs use normal randomness,
so their HP/ward totals are observations rather than matched-seed comparisons;
the native records provide the deterministic mechanics comparison.

## Completion and limits

All implementation and local qualification work in the plan is complete. PR #557
contains the command change, the two focused tests and this updated handoff.
Merging PR #557 completes #505. No production reproduction, deployment,
migration, real-account operation or release tag was performed. The unrelated
main checkout and other worktrees were preserved.
