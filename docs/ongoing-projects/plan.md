# Issue #187: Assassin mechanics and poison rebalance

Status: implementation plan; no gameplay changes or combat qualification performed.
Prepared 2026-10-21 for [issue #187](https://github.com/LuminariMUD/Duris/issues/187).
Implementation branch: `branch/issue-187-assassin-rebalance`.
Source baseline: [master `24a2776f13a2`](https://github.com/LuminariMUD/Duris/commit/24a2776f13a2f3580c91f945743b09f80144b829).

The issue now contains twelve workstreams: A-E and poison recommendations 1-7.
This plan covers all twelve, distinguishing corrections and requested changes
from investigations whose result may be **retain current behavior**. The issue's
earlier investigation-only wording does not prevent this requested plan and
branch publication; implementation, merge and production operation are separate
steps. The [owner's discussion](https://github.com/LuminariMUD/Duris/issues/187#issuecomment-6248301143)
also asks for precise final changes rather than treating every suggestion as settled.

The previous issue #107 plan is preserved byte-for-byte in
[plan-issue-107.md](plan-issue-107.md), including its historical status text.

## Outcome

- Apply general backstab Awareness mitigation consistently across attacker
  races; repair trained Awareness arithmetic and give its active affect a
  tested anti-backstab function without resurrecting historical hit penalties.
- Keep Assassin poison access at level 30, stage stronger recipes as requested,
  add one consistent weapon-delivery resistance policy, make poison Slowness
  curable, and reduce early Weakness while retaining its high-level potential.
- Notify the victim exactly once when a coated weapon establishes a new poison.
  Repair directional Control Flee to 95% at skill 100 while preserving its
  separate chance to escape combat and the movement engine's restrictions.
- Measure Critical Stab, recurring control/damage, mixed poisons, dual coatings,
  traded supplies and crafting costs. Resolve each conditional recommendation
  with evidence and an explicit retain/change decision; implement additional
  substantive balance restrictions only after the required owner decision.
- Prove affected commands, combat callers, cures, event lifetime and item
  compatibility with focused executable regressions and isolated gameplay.

## Verified source findings

These observations were checked against the baseline above. They establish
code behavior and test gaps, not live-server outcomes or deployed settings.

1. **Awareness is two mechanisms.**
   [new_skills.c](../../src/classes/new_skills.c), `do_awareness()` at 421,
   multiplies by integer `skl_lvl / 75`; valid sub-75 skills get a zero modifier.
   [skills.c](../../src/classes/skills.c), Awareness registration at 4903,
   includes 70, 80 and 100 skill caps. The skill grants `AFF_SKILL_AWARE`, not
   `AFF_AWARE`. Active consumers include hamstring, guarding, movement detection
   and mob behavior; the skill is not globally inert. In
   [actoff.c](../../src/cmd/actoff.c), the old backstab hit-chance consumers are
   inside a comment at 6372. Arithmetic repair alone cannot restore stab defense.

2. **The racial exception and critical bypass are active damage rules.**
   `single_stab()` checks `AFF_AWARE`, `!crit`, no knockout, and attacker race
   other than Mountain Dwarf/Duergar. A subsequent INT-versus-opportunity roll
   can multiply damage by 0.6; Awareness is not guaranteed 40% reduction.
   Separate recent-backstab protection multiplies by 0.25 and survives a critical.
   `backstab()` supports Assassin offhand stabs and may call ordinary `hit()`
   when a stab roll fails. Keep stab-roll failure distinct from a melee miss.

3. **Checked-in properties differ materially from function defaults.**
   [duris.properties](../../lib/duris.properties) sets
   `backstab.CriticalStab=0.115`, `backstab.CriticalStab.Multiplier=0.300` and
   `poison.maxDuration.min=4.000`; code fallbacks are 0.200, 1.000 and 15.
   `backstab.AwareModifier=0.750` belongs to the commented hit-chance block.
   Tests must load the real properties and record any tested overrides.
   [config.h](../../src/core/config.h) defines four pulses per second,
   `PULSE_VIOLENCE=16` and `PULSES_IN_TICK=300`: affect duration units must not
   be read as exact real-time minutes.

4. **Weapon delivery has no additional poison save.**
   Normal `hit()` in [fight.c](../../src/combat/fight.c) at 7538 and
   `single_stab()` at 6220 dispatch the stored poison and clear `value[4]`.
   Both preserve a legacy non-ID coating fallback to Lifeleak. These calls
   pass nominal level 10; Heart Toxin instead obtains the attacker's level.
   [handler.c](../../src/world/handler.c), `poison_common()` at 752, rejects
   an active same ID but supplies no generic save/immunity gate. Different
   poison IDs coexist. There is no uniform immediate weapon-delivery notice.
   Some poison routines can remove their newly created affect immediately,
   so calling a void spell function is not proof of successful poisoning.

5. **Slowness loses its cleansing marker.**
   `poison_slowness()` at 950 overwrites `AFF2_POISONED` with `AFF2_SLOW`, while
   `poison_common_remove()` at 721 removes poison-marked affects.
   [affects.c](../../src/magic/affects.c), `affect_to_char()` at 1845, publishes
   initial bits and schedules recalculation; verify the settled character bits
   as well as the stored affect. A flag-text assertion alone is insufficient.

6. **Recurrence needs an actual timeline.**
   Neurotoxin applies 2-4 seconds of wait on later events, first scheduled about
   20 seconds after delivery, not immediately; its initial duration is one tick.
   Slow Poison increases this interval to 60 seconds, and Aid can cure on an
   event. Heart Toxin first schedules after six seconds, or twelve under Slow
   Poison, then requests `3 * level + number(0,40)` through `raw_damage()`.
   A surviving damage call can schedule a repeat with probability 1/4.
   Wards, victim state, attacker departure and event expiry affect realized
   outcomes. `event_poison()` finds an affect by poison type; cure followed by
   same-type reapplication needs a stale-event regression. Do not infer an
   unbounded control chain from the function comments.

7. **Crafting access is not use access.**
   [salchemist.c](../../src/classes/salchemist.c), `poison_data[]` at 246 and
   `do_mixpoison()` at 681, is the authoritative recipe and eligibility path.
   No-argument mixing makes the first eligible recipe with complete inputs;
   any argument already lists eligible recipes. Ingredients are collected
   before consumption, and no extra random crafting-failure roll exists.
   [actobj.c](../../src/cmd/actobj.c), `do_apply_poison()` at 7509, checks skill,
   container and weapon/dart eligibility, then consumes a dose and stores only
   the poison ID. It does not consult recipe gates or preserve maker potency.
   Traded vials and coated weapons therefore bypass crafting-only progression.

8. **Control Flee mixes training with directional success.**
   `do_flee()` parses an argument but calls `dir_from_keyword()` only after
   `notch_skill(...) || skl > number(1,130)`. In
   [guild.c](../../src/guild/guild.c), `notch_skill()` at 168 returns false when
   learned skill reaches its taught cap. At learned/taught 100 the base chance
   is therefore exactly 99/130; while training, notch successes can add to it.
   The existing 95 cap is unused. Random exits use `CAN_GO`, `bad_flee_dir()`
   and `can_enter_room()`; a chosen direction skips that selection filter.
   [utility.c](../../src/core/utility.c), `dir_from_keyword()` at 4235, already
   supports abbreviations and diagonals. [actmove.c](../../src/cmd/actmove.c),
   `do_simple_move()` at 2168 and its callee, owns additional secret/blocked,
   mount, current, special-proc and terrain restrictions. The separate escape
   comparison uses `number(0,100)` against configured 78-86 thresholds; preserve
   its current inclusive-roll behavior rather than silently correcting it too.

The [Power Atlas](../../site/power-atlas/content.html) is explicitly a historical
2026-09-16 model of `f3b66b07f`. Its duel excludes backstab openers and fleeing;
it provides no verified poison model. It cannot choose today's save rate,
critical mitigation or stacking limit. Production properties, ingredient
availability and the reported win/escape outcomes remain unverified.

## Ablation: non-goals, files and proof

- **Keep:** the twelve outcomes, existing command compatibility, a shared
  weapon-delivery function, effect-lifetime checks and real combat journeys.
  Two production weapon callers justify sharing delivery/save/feedback; a
  helper-only test cannot prove either caller actually uses it.
- **Simplify:** reuse `poison_data[]`, `NewSaves`, existing affect `level`,
  `dir_from_keyword`, exit checks and native harness/journey utilities.
  Keep poison spell signatures and existing event/affect machinery. Use
  sequential focused commits on this branch; no stack or new work items needed.
- **Drop:** blanket base/offhand stab reductions, an 80% offhand multiplier,
  removal of dual-poison openings, universal one-poison caps, automatic critical
  nerfs, recipe-selection UI, random crafting failure, inventory invalidation,
  new persistence schemas, balance services, feature flags, a new scheduler,
  generic combat/resistance frameworks and broad movement cleanup. The optional
  recipe selector already has a listing alternative and no proven need.
- **Investigate before expanding:** the exact Awareness combat contract,
  resistance calibration, traded-item use policy and recurring-event identity.
  Each investigation below has a concrete test and a recorded decision.
  Extra numeric nerfs require the issue's evidence and owner approval.

Expected implementation files are `src/cmd/actoff.c`,
`src/classes/new_skills.c`, `src/classes/salchemist.c`,
`src/world/handler.c`, `src/combat/fight.c`, `src/core/prototypes.h`,
focused `tests/async/` coverage and `lib/information/help_index`.
Touch `src/cmd/actobj.c` only for an accepted use gate;
`src/magic/affects.c` only if a lifecycle regression requires it.
Read `skills.c`, `config.h`, `utility.c`, `actmove.c`, `guild.c`, `sparser.c`
and `duris.properties` as dependencies; they do not need automatic edits.
This planning commit changes only this document and the preserved #107 plan.

## Implementation sequence and acceptance

### 1. Capture a working baseline and settle Awareness (A, B, poison 7)

- Add focused executable Assassin/poison cases using the existing
  [native harness utilities](../../tests/async/_paths.py) and
  [affect/proc harness pattern](../../tests/async/test_freedom_of_movement_procs.py).
  Drive complete touched production functions with controlled RNG and real
  affect operations; do not copy combat formulas into a separate simulator.
- First reproduce racial mitigation, zero sub-75 modifiers, absent trained
  stab defense, uncured Slowness and both weapon delivery paths. Retain the
  unchanged baseline plus a working-cleanse baseline for later comparisons.
- Remove only Mountain Dwarf/Duergar's exception in the ordinary aware-damage
  branch. Preserve knockout, recent-stab protection, wards, hit chance, critical
  chance/bonus and both weapon slots.
- Compute the trained modifier with multiplication before division, e.g.
  `(base * skl_lvl) / 75`, preserving the current base and random range.
  Test actual formula outputs at skill 1, 45, 60, 70, 74, 75, 80 and 100;
  legitimate rounding at very small inputs need not be forced above zero.
  Preserve duration policy and test low INT's existing short/zero duration,
  refresh, expiry, and coexistence with the passive/flee-created affect.
- Proposed minimal anti-stab contract: let active `AFF_SKILL_AWARE` qualify for
  the same existing damage-mitigation branch as `AFF_AWARE`, once, with no
  stacking or restored hit-chance penalty. Keep its scaled modifier for the
  existing consumers that actually read it. Compare trained/passive/both/neither
  before accepting this contract; record the owner decision if those tests show
  a materially different strength policy is needed. Do not globally alias the
  flags or set `AFF_AWARE` on every trained affect, which would change unrelated
  attacks. Arithmetic is a correction; the new anti-stab contract is an explicit
  proposed behavior change, not a fact established by the issue.
- Accept when non-critical matched stabs have race-consistent mitigation,
  trained defense is demonstrably reachable, all recent-stab/critical/ward rules
  remain scoped, and hamstring/guard/detection consumers retain their behavior
  apart from the intended corrected modifier. Update the Awareness help entry.

### 2. Repair cleansing, delivery, feedback and resistance (D, poison 2, 3, 7)

- Add `AFF2_SLOW` without losing `AFF2_POISONED`. Prove Remove Poison,
  Purification and the existing healing/staff/class cure callers remove poison
  Slowness, including when it is the only poison. Independently cast Slow must
  survive a poison-only cure. Confirm immediate/settled flags and attack impact.
- Introduce one small weapon-poison delivery function in `handler.c`, declared
  in `prototypes.h`, called by ordinary hits and `single_stab()` at their current
  delivery points. Normalize the existing legacy Lifeleak coating case; retain
  current ordering relative to weapon procs and attack survival checks.
- On a valid landed delivery attempt consume one coating regardless of save,
  immunity or duplicate rejection. Preserve coating on a true miss; a failed
  stab that lands its fallback melee hit may legitimately consume it. Perform
  at most one application save for that weapon attempt. Validate the ID and
  callback before indexing; preserve legitimate NPC and legacy coatings.
- Reuse `NewSaves(victim, SAVING_PARA, modifier)` as the first calibration
  candidate: [sparser.c](../../src/net/sparser.c) already handles class/race
  saves, gear, NPC difficulty and Quick Thinking; negative modifiers favor the
  defender. Measure actual equal-level chances before choosing the modifier
  and bounded level adjustment. Do not add a second arbitrary proc roll.
  Establish relevant poison immunity rules from existing poison sources such
  as Pythonsting, including NPC/racial cases; paralysis immunity and magical
  resistance are not automatically poison immunity. Record which rules apply.
- Calibrate meaningful PvP resistance against the baselines in step 5. Preserve
  PvE/non-weapon source behavior by default; do not put the new save or generic
  feedback into `poison_common()`, where food, spells and scripted NPC uses
  would also receive it. Document any proposed PvE application-save change
  separately with its compatibility evidence before accepting it.
- Record absence of the exact poison ID before dispatch and presence after
  dispatch; emit success feedback only for a new retained affect. An initial
  self-removal, duplicate, immune or resisted attempt is not a success.
  Keep existing symptom messages; do not use a total poisoned-bit check, which
  cannot distinguish mixed effects. No poison recipe name goes into the new
  generic message. Keep non-weapon sources out of that notice.
- Victim-only bladed-weapon text, followed by the normal line ending:

  > &+RYou feel a sharp burning sensation as &+gpoison&+R from your attacker's blade enters your bloodstream!&n

  Use `weapon` for an eligible non-bladed weapon/dart. A dual opening can produce
  one notice for each distinct newly established poison; two coatings of the
  same already-active poison cannot produce a second success notice.
- Exercise cure -> reapply before the old timer fires, natural expiry, Aid,
  disconnect/reconnect, attacker extraction and victim death. If the type-only
  event lookup targets a replacement affect, make the smallest poison-specific
  cancellation/ownership repair using existing event APIs. No stale event may
  accelerate a replacement poison, recreate a cured effect or access dead data.

### 3. Stage recipes and scale Weakness (poison 1, 5, 6, 7)

- Change the recipe matrix to Lifeleak **30/1**, Weakness **30/1**, Moveleak
  **36/50**, Slowness **41/70**, Neurotoxin **46/80**, Heart Toxin **46/80**,
  Madness **51/100** (level / mix skill). Keep both Assassin poison skills at
  level 30. Test each level and skill threshold immediately below, at and above
  the boundary; verify listing and no-argument recipe ordering use the same data.
- Reproduce high-recipe transfer to a low-level user through a vial and an
  already-coated weapon. Proposed initial scope is crafting gates only, as the
  issue requests first. Record whether the early-PvP objective requires an
  additional PC use-level gate; this is a required decision, not a claim that
  crafting gates prevent low-level use. If accepted, reuse recipe lookup at
  coating and delivery so trading a coated weapon cannot evade it. Decide the
  treatment of existing stocks explicitly; do not delete, migrate or silently
  invalidate player items. Do not invent a mix-skill requirement for ordinary
  delivery or alter NPC/quest uses without that policy decision.
- Test the issue's Weakness candidate: **5-10 at source level 30-40, 5-15 at
  41-50, current 5-20 at 51+**; include lower-level NPC/spell sources separately.
  For weapon poison, propose capturing the delivering attacker's level on
  initial application into the existing affect `level`, then reuse it on every
  refresh. Do not use the caller's hardcoded 10, the victim's changing level,
  or an attacker pointer that can disappear. This is delivery-level potency,
  not maker-level provenance, which the current vial does not contain.
  For other sources use their supplied source level and preserve their current
  effect until an intentional compatibility decision is made. Verify existing
  affect save/copyover support before relying on the stored value; define the
  fallback for legacy zero-level affects without a schema migration.
- Keep Slow Poison's existing upper bound of 8, capped by the chosen Weakness
  ceiling. Measure physical and caster impact before accepting the test curve;
  keep high-level potential unchanged. Recheck refresh, cures and source logout.
- Keep deterministic crafting and existing eligible-recipe listing. Check
  multiple eligible recipes, missing ingredients/vials, creation failure,
  exact input/dose/weight consumption, last-dose transient vials, re-coating,
  item transfer and existing serialized coatings. Record realistic preparation
  cost before proposing any anti-stockpile restriction. Update Apply Poison
  and Mixpoison help, including the actual two-object apply syntax.

### 4. Repair directional Control Flee (E, poison 7)

- For Rogue PCs with the skill and an argument, parse the extracted token with
  `dir_from_keyword()` before rolling. Reject malformed/extra tokens and
  unavailable/prohibited requested exits explicitly. Reuse the current eligible
  exit conditions and the movement engine; do not run movement specials twice
  as a speculative preflight or duplicate all terrain/mount logic.
- Replace the 1-130 directional roll with one explicit skill-scaled check using
  `MAX_CHANCE_TO_CONTROL_FLEE`: proposed
  `chance = skill * MAX_CHANCE_TO_CONTROL_FLEE / 100` and an
  inclusive 1-100 roll. Retain the skill-training call as a training side
  effect, with no automatic directional-success shortcut; use the pre-training
  skill for that attempt. At skill 100 this gives exactly 95 successful rolls
  per 100, with neither notch outcome changing that attempt's chance.
- On directional failure send `You panic and lose control of your escape
  direction!` and use existing random eligible-exit selection. On a bad requested
  exit remain in place with useful feedback; do not silently randomize it.
  Handle zero eligible exits before selecting a random exit.
- Preserve no-argument, non-Rogue and no-skill random flee, escape-roll comparison,
  action lag, vitality cost, Sneak restoration, grapple/woods/expeditious retreat,
  mount and movement-special behavior. A direction roll never guarantees escape.
  Confirm destination and displayed direction agree; an interfering special
  must not produce a false claim that the requested move succeeded.
- Test exact/abbreviated/diagonal directions, zero/one/many exits, closed,
  blocked, secret, unsafe/drop destinations, mounts, water/current and room
  specials. At skills 45, 60, 80, 90 and 100 enumerate deterministic roll
  boundaries with notch success/failure. Also run 10,000 fixed-seed valid-exit
  attempts: require effective skill-100 control within 94-96%, counting control
  separately from random fallback coincidences and final escape successes.
  Update Control Flee help with both failure modes.

### 5. Resolve conditional balance work (C, poison 4, 6, 7)

- Use an isolated real-server combat fixture, reusing
  [flat-file combat journey](../../tests/async/test_flatfile_combat_journey.py)
  boot/client/build utilities. Do not build a new general benchmark service.
  Record source, properties, seed, actors, gear and defense setup. Compare
  unchanged baseline, working-cleanse baseline and each proposed change before
  testing the combined patch. Store concise reproducible results in this plan.
- Cover levels **30, 36, 41, 46, 51 and 56**, Mountain Dwarf/Duergar/one other
  Assassin race, physical and caster defenders, equal gear plus representative
  gear/level mismatches, ordinary hits, one/two weapon openings and solo PvE.
  Use valid learned/unlocked skills: do not assume Critical Stab or Control Flee
  is available at every sampled level. Include matched Thief comparisons where
  they help quantify preservation of Assassin's role.
- Measure landed/missed stabs, normal/critical delivered damage, recent-stab
  mitigation, defense uptime, poison attempts/saves/new affects, notification
  count/routing, control seconds and usable command/cure windows, Heart Toxin
  post-ward damage/repeats/kill attribution, time to kill, flee/survival and
  ingredient/dose cost. Advance real event/tick boundaries, including different
  delivery phases; aggregate proc counts without calling them live win rates.
- **Critical Stab:** compare aware/unaware, trained/passive and both weapon
  slots with actual properties. Retain current critical mechanics unless
  controlled outcomes justify a specific mitigation change. Any proposal must
  retain a distinct critical bonus and preserve the recent-stab rule.
- **Neurotoxin and Heart Toxin:** measure cures, Slow Poison, Aid, repeat
  applications, wounded victims, attacker departure and wards first. If needed,
  propose one smallest PvP control/repeat adjustment with before/after results;
  do not stack cooldowns, diminishing returns and caps as speculative defenses.
- **Layering and supplies:** test same-ID rejection and the mixed
  Neurotoxin/Slowness/Moveleak/Weakness combination, same/different dual coatings,
  rapid recoating and preparation/trading cost. Retain mixed stacking and dual
  stab unless those results justify a targeted restriction. Madness remains
  51/100; measure its existing caster/hitter Berserk tradeoff rather than
  treating it as paralysis. Optional recipe selection is considered and
  omitted unless the audit demonstrates a material unresolved usability need.
- Finish each conditional item with **retain + evidence**, or **proposed
  change + evidence + owner decision + targeted regression**. Pending policy or
  additional nerf approval stays visible and prevents claiming the entire issue
  resolved. No fixed soak period or production test is required for local proof.

## Verification and completion

Proposed new focused entry points are `test_assassin_mechanics_runtime.py`,
`test_weapon_poison_runtime.py`, `test_control_flee_runtime.py` and
`test_assassin_combat_journey.py` under `tests/async/`; combine with existing
fixtures where simpler. These names describe planned tests, not files already
present. Include actual callers and event execution, not just source-string
contracts. Keep compiled outputs under ignored `bin/`; keep disposable worlds
and account/item fixtures isolated from real data.

During implementation run those tests directly, plus the existing adjacent
checks that cover touched behavior:

```sh
python3 tests/async/test_combat_movement_feedback.py
python3 tests/async/test_spell_affect_regressions.py
python3 tests/async/test_freedom_of_movement_procs.py
python3 tests/async/test_cleric_utilities_runtime.py
python3 tests/async/test_issue_551_crafting_conservation.py
./scripts/format.sh --check
make -C src
git diff --check
```

Use focused ASan/UBSan execution for changed poison/affect/event ownership.
Run the new gameplay journey with a verified isolated `__NO_MYSQL__` build;
reuse the combat journey's build isolation instead of pointing it at a running
server or selecting a binary by filename alone. Test item save/reload and affect
restore/copyover where the potency implementation depends on them. Use `make
world` only if a chosen full-world journey requires absent generated files;
do not commit generated world outputs. No CI wait is a completion requirement.

Before calling the issue complete: all twelve workstreams have their specified
implementation/proof or evidence-backed retained-behavior decision; gameplay and
compatibility checks pass; conditional owner decisions are resolved; help and
this document describe the final behavior. Report unavailable checks explicitly.
Production deployment, migrations, player-data changes and live balance
acceptance are separate owner-authorized operations.

Planning validation performed here: current issue and both comments read;
baseline fetched; affected functions, callers, flags, properties, event/cure
paths and existing test infrastructure inspected. No C/C++ changes, native
build, regression execution or controlled PvP/PvE result is claimed by this plan.
Documentation checks pass: all 19 local links resolve, all twelve workstreams
are mapped, the previous plan is byte-identical, and `git diff --check` is clean.

## Estimate

**16-24 active engineering hours, approximately 2-3 focused working days** for
the proposed corrections, delivery/save/feedback policy, recipe/Weakness changes,
Control Flee, focused regressions and first controlled combat comparison:

- 3-4 hours: baseline fixtures, Awareness/racial repair and cleansing.
- 4-6 hours: shared delivery, feedback, resistance, progression and Weakness.
- 2-3 hours: directional flee and probability/movement coverage.
- 5-8 hours: integrated PvP/PvE, event/item compatibility and conditional decisions.
- 2-3 hours: help, final validation, review fixes and delivery documentation.

The range includes the required audits even when their correct outcome is to
retain current behavior. Evidence-backed extra critical/control/stacking tuning
or an approved traded-item restriction may add **2-6 active hours**. Time awaiting
owner policy decisions, review or separately requested deployment is elapsed
time outside this estimate. Re-estimate only if the first executable baseline
reveals a material lifecycle/persistence issue or expands the agreed scope.
