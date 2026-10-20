# Issue #169: Cleric rebalance implementation plan

Status: implementation complete and published for review, 2026-10-20.
Owner review and separately authorized production acceptance remain open.
Tracking: [issue #169](https://github.com/LuminariMUD/Duris/issues/169).
Implementation branch: `branch/issue-169-cleric-rebalance`.
Source baseline: [master `b81715f3a146`](https://github.com/LuminariMUD/Duris/commit/b81715f3a146388e91fd320e2070baef95a63cc7).

This plan uses the issue body together with the
[2026-10-20 revision](https://github.com/LuminariMUD/Duris/issues/169#issuecomment-6284710833).
That revision supersedes removing Divine Warding and moving Miracle to level 51.
The owner additionally confirmed in the planning conversation that Divine Warding
must last **11 elapsed minutes**, not 11 affect ticks. The issue title and older
acceptance checklist still describe the superseded proposal.

The previous Hatred plan is preserved byte-for-byte in
[plan-issue-166.md](plan-issue-166.md); its outstanding production report belongs
to #166, not this branch.

## Outcome

Implement all six revised Cleric changes and the associated Tsunami proposal:

1. Remove normal player Cleric access to Vital Intercession, retaining Holy
   Intercession and its shared implementation.
2. Keep Divine Warding at level 51/circle 11, restrict it to self, and give its
   seven protections an 11-minute duration with normal independent dispelling.
3. Grant the existing white Improved Healing aura to Healers on specialization.
   Retain Paladin access and exclude Holyman and Zealot from this new grant.
4. Set Miracle to level 36/**circle 8** and True Seeing to level 46/circle 10.
5. Make passive Warding Faith recovery use a 240-second baseline for both base
   and epic capacity; reduce healing-triggered refill to one tenth of effective
   healing.
6. Restore all 13 specified ordinary Cleric offensive spells, ordinary 40% Kick,
   and circle-6 Negative Energy Barrier to Healers.
7. Make Tsunami's Vitality power `min(wielder level + 15, 60)` in both supported
   execution paths, including a useful refresh after a weaker Miracle/Vitality.

The balance claims remain hypotheses. The owner explicitly narrowed this task
to implementation on 2026-10-20: do not spend this task on balance measurements.
Verify changed behavior and publish review-ready PRs; these changes alone do not
prove that group sustain or class choice is balanced.

## Non-goals and ablation decisions

Keep the existing spell IDs, protection effects, aura implementation, scheduler,
spell eligibility rules, and persistence formats. No new balance service,
general spell framework, feature-flag family, ward-break lockout, refill cap,
damage penalty, or schema migration is justified by the inspected code.

Drop the superseded Divine Warding removal and Miracle-at-51 proposal. Do not move
Divine Font, change ordinary Vitality globally, grant Zealot bonuses to Healers,
or implement the latest comment's expressly deferred further ward nerfs.
Keep historical Power Atlas output historical rather than regenerating it as
part of this work.

The necessary exceptions to simple grant-table edits are concrete: elapsed-time
Divine Warding needs event-safe refresh; ward recovery needs fractional rate
handling; Tsunami has two real callers and currently cannot strengthen an existing
Vitality affect. Solve those paths directly, without broad cleanup.

The current implementation request authorizes local development and review-ready PRs. Production deployment,
property reload, help import, restart, and live account changes require separate
operational authorization. Repository-required local checks take precedence over
the issue's older instruction to wait for CI.

## Baseline source findings at b81715f3a146

- **Progression and eligibility:** [skills.c](../../src/classes/skills.c) currently
  gives Miracle circle 7, True Seeing circle 11, Divine Warding circle 11, and
  Holyman Vital/Holy Intercession circles 6/10. In
  [memorize.c](../../src/classes/memorize.c), `get_max_circle()` is
  `(level - 1) / 5 + 1`: level 36 means circle 8, not the revision's parenthetical
  “6th circle.” The explicit level 36 is the planned target. Normal specialization
  requires level 30 in [specializations.c](../../src/classes/specializations.c);
  a circle-6 Holyman assignment is not proof that an ordinary level-26 character
  can already be a Holyman.
- **Saved spells:** `get_spell_circle()` returns `MAX_CIRCLE + 1` for an absent
  grant. `knows_spell()` rejects that or an over-level circle before accepting a
  stored prepared copy. The ordinary cast path in
  [sparser.c](../../src/net/sparser.c) uses this check. Reuse and test it before
  inventing a player-data migration.
- **Intercession:** [magic.c](../../src/magic/magic.c) shares
  `vital_intercession()` and `vital_intercession_heal()` between Vital and Holy.
  [fight.c](../../src/combat/fight.c) checks the two affect IDs independently.
  Triggered Intercession healing uses `vamp()`, not the Healer refill in `heal()`.
- **Divine Warding duration:** its wrapper calls the seven existing protection
  routines. All seven currently use `duration = level` and overwrite that field
  on refresh. [affects.c](../../src/magic/affects.c) decrements ordinary player
  affects once per 300-pulse tick and removes a zero-duration effect on a later
  update; [config.h](../../src/core/config.h) defines four pulses per second.
  Consequently “51 minutes” is not a verified elapsed duration, and substituting
  `11` would not deliver 11 elapsed minutes. `AFFTYPE_SHORT`, `affect_to_char()`,
  `affect_remove()`, and `event_short_affect()` already support pulse-timed expiry.
- **Aura:** [innates.c](../../src/classes/innates.c) grants Improved Healing to
  Paladins at 30; Holyman's existing spec auras demonstrate the level-1
  registration convention for an ability gated by specialization.
  [paladins.c](../../src/classes/paladins.c) supplies the white color, linked group
  effects, duplicate-aura rejection, and cleanup. `vamp()` applies the incoming
  bonus subject to existing regeneration/accelerated-healing exclusions.
- **Ward:** `affect_total()` computes capacity as level times
  `3 + epic_skill / 33`, with the existing NPC multiplier. It currently converts
  capacity to an integer rate using `capacity / rechargeTime * PULSES_IN_TICK`.
  [events.c](../../src/world/events.c) consumes that rate per scheduler pulse.
  [limits.c](../../src/world/limits.c) blocks passive regen during combat and in
  no-heal rooms and adds a heal-room bonus. The property and fallback are both
  120. `heal()` already uses effective HP returned by `vamp()`, then adds
  `hits / 5` to the Healer's ward. Group Heal invokes this per eligible recipient.
- **Healer access:** the table contains exactly 13 offensive circle-zero Healer
  overrides, one for Negative Energy Barrier, and the zero Kick override.
  A repository-wide `SPEC_HEALER` scan found healing bonuses and other existing
  behavior, not an additional explicit Healer-only damage-spell exclusion.
  This scan is source evidence, not command-level proof of every restored spell.
- **Tsunami:** VNUM 31514 is assigned `SeaKingdom_Tsunami()` in
  [specs.assign.c](../../src/specs/specs.assign.c). Both the legacy callback in
  [specs.underworld.c](../../src/specs/specs.underworld.c) and the optional adapter
  in [tsunami_actions.c](../../src/item/tsunami_actions.c) use wielder level for
  new Vitality. Existing affects only have duration refreshed to 15. Even
  `spell_vitality()` itself does not upgrade an existing HP modifier.
  The native path captures level at activation and filters refresh to self/group;
  the legacy refresh branch currently reaches unrelated room occupants.
  Shipped [properties](../../lib/duris.properties) disable the native pilot, so
  changing that adapter alone would miss the default route.

### Planning-time proof and limits

At the pinned baseline, these existing checks passed:

```sh
python3 tests/async/test_cleric_spell_progression.py
python3 tests/async/test_cleric_utilities_runtime.py
python3 tests/async/test_memorized_spell_eligibility.py
python3 tests/async/test_native_artifact_runtime.py
python3 tests/async/test_tick_work_spread.py
python3 tests/async/test_documentation_contract.py
```

An isolated compiled probe reused the current `StartRegen()` and
`event_ward_regen()` bodies and the exact rate expression, with a test scheduler
and stubbed `ward_regen()`. At level 56 and epic skill 0/100, capacities were
168/336. Property 120 filled in 121 pulses (30.25 nominal seconds); property 240
filled in 241 pulses (60.25 seconds). Adding the missing seconds conversion while
retaining integer truncation produced 242.50 seconds at capacity 168 and 240.00
seconds at capacity 336. This proves both the units error and the remaining
quantization problem at those inputs; it is not a running-server measurement.
The temporary probe was removed after execution.

The existing progression/utility tests intentionally assert the old behavior;
their green baseline does not validate the proposed behavior. The prepared-spell
test currently exercises Freedom of Movement, not removed Vital Intercession.
The native artifact harness records spell calls; it does not prove real
Vitality HP recalculation. The tick test stubs the regen rate. Extend these
specific gaps rather than counting their existing passes as acceptance.

No production revision, runtime override, controlled group-balance measurement,
full build, or full regression run was obtained for this planning publication.
The [historical Atlas](../../site/power-atlas/content.html) excludes groups and
other material combat behavior; it cannot supply the missing balance evidence.

## Implementation work items

### W1 — Spell access, progression, and retained Intercession

- [x] In `src/classes/skills.c`, remove only Vital Intercession's Holyman grant;
  retain its ID, handler, shared helpers, and Holy's circle-10 grant. Retain
  existing Vital affects until their ordinary expiry; prohibit preparing or
  casting new copies through normal Cleric access, including saved prepared ones.
  Preserve internal/item/NPC uses unless a traced path bypasses this requirement.
- [x] Set Cleric Miracle to circle 8 and True Seeing to circle 10, leaving
  underlying buffs and other classes' access unchanged.
- [x] Remove the 13 Healer offensive exclusions: Cause Light (circle 1); Cause
  Serious (2); Cause Critical, Earthquake, Dispel Evil, Dispel Good (3); Destroy
  Undead (5); Harm and Flame Strike (6); Holy Word and Unholy Word (9); Full Harm
  and Taint (10). Restore Negative Energy Barrier at circle 6 and Kick's ordinary
  level-1/40% entitlement by removing their Healer overrides. Preserve Zealot's
  90% Kick cap and unique damage bonuses.
- [x] Extend `test_cleric_spell_progression.py` and
  `test_memorized_spell_eligibility.py` with actual grant/spec inputs and
  boundary cases: 25/26, 29/30, 30/31, 35/36, 40/41, 45/46, 50/51, and 56.
  Exercise prepare/cast/list behavior and saved full/pending copies, including
  lawful multiclass access and specialization transitions. Ordinary restored
  grants do not automatically give a character maximum trained proficiency.
- [x] Preserve existing Holy Intercession and offensive spell implementations.
  No new damage or target mechanics were added. Source-derived eligibility
  regressions cover all 13 grants, barrier and ordinary/Zealot Kick caps; existing
  Holy Sacrifice/vamp and healing-precedence tests pass. The owner excluded a
  new combat/measurement campaign from this implementation task.

### W2 — Self-only Divine Warding for 660 seconds

- [x] Keep circle 11 and use the existing `TAR_SELF_ONLY` target convention.
  Enforce self-only behavior inside `spell_divine_warding()` as well, because
  direct/item calls do not all traverse the player parser. Reject an explicit
  non-self target without applying any of the seven effects; retain living-caster
  and valid-room checks.
- [x] Reuse the seven protection effects and the existing short-affect lifecycle.
  Set their bundle duration to `11 * 60 * WAIT_SEC` (2,640 pulses). Preserve
  bitvectors, strength, visibility, and independent dispelling; do not add one
  undispellable umbrella buff or simply change the routines' level argument to 11.
- [x] Make refresh replace/cancel the old timed instance safely. A bundle recast
  resets each protection to 660 seconds, including a protection originally cast
  individually. A later individual cast restores its ordinary level-based
  duration and cancels the bundle expiry for that instance. These protections
  are the same IDs, so a raw `af->duration = level` on a short affect is unsafe.
  A small local protection-application helper is justified only to share this
  logic among the seven real routines; no generic effect-system rewrite.
- [x] Extend `test_cleric_utilities_runtime.py` beyond its current stubbed
  expiration path: prove no expiry before 2,640 pulses and expiry at the due
  pulse, independent of the global affect-tick phase. Cover all seven effects,
  both refresh orders, repeated recasts, partial dispel, removal/extraction,
  canceled old callbacks, and a scheduling failure without a permanent buff.
  Confirm unrelated effects and individual protection casts retain their behavior.
- [x] Prove remaining-time display and persistence. Existing
  `src/core/files.c:updateShortAffects()` obtains event time before saving;
  snapshot capture copies affect duration and materialization uses the existing
  affect APIs. Trace the real callers and test flatfile and MariaDB
  save/relogin, copyover, and restart, so saving cannot renew a full 11 minutes.
  Preserve the ordinary offline-time policy. Old tick-based protections may
  expire naturally; do not guess their original source or rewrite player data.
  Repair a missing handoff only if these journeys demonstrate it.

### W3 — Healer's existing white aura

- [x] Add `ADD_CLASS_INNATE(INNATE_AURA_HEALING, CLASS_CLERIC, 1, SPEC_HEALER)`
  alongside the existing class/spec grants. The real unlock is specialization
  at level 30. Leave the Paladin level-30 grant and aura coefficient unchanged.
- [x] Verify the new Healer command and lost-entitlement cleanup through ordinary
  and staff unspecialization in the disposable journey. Source-derived innate
  tests cover ordinary Cleric, Healer, Holyman, Zealot and retained Paladin access.
- [x] Reuse the existing linked-aura application and duplicate-provider policy.
  Keep the existing incoming regeneration/Accelerated Healing/Regenerate
  exclusions; focused executable refill tests check all three and normal white
  aura. Broader unchanged provider combinations are outside this narrow task.

Aura lifecycle closeout for the access PR: ordinary and staff unspecialization
now purge outgoing Cleric specialization auras and refresh the target's skills.
Paladin and Anti-Paladin base auras remain available. The executable regression
covers successful/failed transactions, the correct staff target, both retained
base classes, and linked aura cleanup. This fix is included with the new Healer
grant in #222 so it is independently safe to review. The later #226 repair is
superseded by this integration.

### W4 — Ward seconds and effective-healing refill

- [x] Set `innate.wardingFaith.rechargeTime` and its fallback to 240 seconds.
  Preserve the existing capacity calculation, epic integer steps, NPC capacity
  multiplier, and other ward modifiers.
- [x] Keep fractional Warding Faith rate until event accumulation. The required
  contribution, in points per 300-pulse tick, is
  `base_ward * PULSES_IN_TICK / (240.0 * WAIT_SEC)`.
  A narrow implementation is to move that contribution from integer
  `TmpAffs.ward_reg` into the existing `ward_regen()` calculation, return a
  floating rate, and keep it floating in `event_ward_regen()` and `StartRegen()`.
  Update the declaration and directly affected fixture stubs. Compute the innate
  contribution in one place; retain the existing event accumulator and integer
  ward balance. No persisted character layout or other resource's rate needs to
  change. Evaluate the combined rate before full/negative-rate early exits.
- [x] Change only the Healer refill in `heal()` from `hits / 5` to `hits / 10`,
  retaining the effective-HP source and ward cap. Use it both in and out of combat,
  as the existing path does. Preserve healing modifiers and Group Heal's
  per-recipient rounding. Do not refill from attempted healing or Intercession's
  direct `vamp()` path.
- [x] Add focused executable ward/refill coverage, reusing the existing
  regeneration fixtures rather than creating a balance framework. Exercise
  production capacity/rate, `ward_regen()`, `StartRegen()`,
  `event_ward_regen()`, `heal()`, and `vamp()`; stubbing the rate is insufficient.
  Test levels 30/36/46/51/56 and epic 0/32/33/65/66/98/99/100. In an ordinary room,
  with no healing or other ward bonuses, empty-to-full should be 960 pulses,
  allowing at most one pulse for numeric rounding, independent of capacity.
- [x] Test no-heal/heal rooms, combat entry/exit, ordinary restart scheduling,
  zero/partial/full ward and changed capacity. Ward is runtime state; saved
  affect restoration is covered by the separate journey. Separate time waiting
  for regeneration to restart from its measured 0-to-full recovery; do not hide
  either in a timing claim. For refill, include effective healing 0/1/9/10/19/20,
  overheal, healing reduction, white aura, multiple Healers, and Group Heal sizes
  1/3/6. The sum is per-recipient `floor(effective HP / 10)`, capped at max ward.

### W5 — Tsunami Vitality in both execution paths

- [x] Apply `min(level + 15, 60)` to Vitality only in the legacy callback and
  native adapter. Preserve native activation-time level capture, delay,
  cancellation, ownership checks, mana cost, and the 300-second tap cooldown.
  Leave thrust/raise, waves, item stats, and pilot defaults unchanged.
- [x] Handle an existing weaker Vitality explicitly; changing the argument to
  `spell_vitality()` alone does not do so. For an eligible recipient, use the
  existing affect mutation/replacement APIs to retain exactly one Vitality with
  the greater of its current HP modifier and `4 * min(wielder level + 15, 60)`.
  Preserve the current refresh duration of 15 ticks and ordinary fresh-cast
  duration. Never downgrade a stronger existing effect or stack HP modifiers.
  Preserve incompatible deity Vitality restrictions and reflection exclusions.
- [x] Share only the needed Tsunami application logic between the two real
  callers if otherwise duplicated; do not change ordinary Vitality or Miracle
  globally. Apply the existing self/same-non-null-group test before both new
  application and refresh in both routes. The legacy bystander refresh must not
  become a bystander HP upgrade.
- [x] Extend `test_native_artifact_runtime.py` to assert power at wielder levels
  30/36/44/45/46/56 (effective levels 45/51/59/60/60/60), with the native pilot
  disabled and enabled. Add real Vitality/affect recalculation coverage for fresh,
  weaker, equal, and stronger effects; test Miracle before/after tap, ungrouped
  self, group members, bystanders, absent members, and interruption.
  Extend the existing `run_item_pilot_journey.py --family tsunami` journey to
  observe actual max HP and duration, not just the cast message.

### W6 — Help and saved-character compatibility

- [x] Update both maintained help import sources,
  `help/duris_help_parsed.hlp` and `lib/information/help_index`: Cleric skills,
  Healer, Holyman, Improved Healing aura, Divine Warding, Miracle/True Seeing,
  Warding Faith/Epic Warding Faith, and affected spell descriptions. Describe
  training, real specialization unlock, circle 8, elapsed minutes/seconds, and
  10% effective-healing refill accurately.
- [x] Update the current Tsunami contract in
  `docs/reference/NATIVE_ARTIFACT_PILOTS.md` and Healer capability text in
  `docs/reference/CLASS-POINTS.md`. Leave historical rankings and source snapshots
  unchanged. Keep published player news/help import for the authorized release.
- [x] Help/progression contracts pass. Disposable existing-character fixtures
  prove saved full/pending Vital/Miracle eligibility, restored Cleric specs,
  buff order and timed protection save/copyover/restart/expiry on both backends.
  Existing eligibility/runtime fixtures cover Kick, old ordinary protections and
  both timer-unit transitions. Preserve IDs and source attribution; no bulk
  player-data cleanup or migration was needed.

### W7 — Implementation verification and release follow-up

Owner scope correction, 2026-10-20: **implementation only; no balance measurements**.
The earlier matched PvP/PvE matrix, individual-change attribution, TTK, kill-rate,
and wall-clock recovery campaign are removed from this task. Do not restart them
in a continuation session without a new request. Existing focused ward timing
regressions remain necessary correctness proof of the requested 240-second rate.

- [x] Complete the narrow saved-spell/aura/buff/timer journey on disposable
  flatfile and MariaDB backends. Record source and binary identity and actual
  results; this verifies implementation and persistence, not balance.
- [x] Publish final qualification and the current handoff, verify PR head/base,
  remote parity and a clean task worktree. Leave the implementation ready for
  review without merging or deploying it.
- [ ] After separately authorized deployment, record the deployed revision and
  effective properties and verify player-facing behavior. Keep #169 active until
  owner release acceptance; implementation PRs do not establish deployment.

## Files and delivery sequence

Primary implementation files: `src/classes/skills.c`, `src/classes/innates.c`,
`src/magic/magic.c`, `src/magic/affects.c`, `src/combat/fight.c`,
`src/world/limits.c`, `src/world/events.c`, `src/core/prototypes.h`,
`src/specs/specs.underworld.c`, `src/item/tsunami_actions.c`, and
`lib/duris.properties`. A narrow shared Tsunami declaration may belong in the
existing `src/item/native_artifact_actions.h`.

Use the test/help/doc files named with each work item. Inspect rather than
preemptively edit `src/classes/memorize.c`, `src/net/sparser.c`,
`src/classes/paladins.c`, `src/core/files.c`, `src/player/player_snapshot_capture.c`,
`src/player/player_load_materialize.c`, and `src/persistence/copyover.c`;
change them only if required command/lifecycle proof fails.

Deliver small commits on this branch: access/aura with matching help and tests;
Divine Warding timing with lifecycle proof; ward recovery/refill; Tsunami; then
combined journey evidence and final documentation. Keep each behavior's help
and tests beside its implementation rather than a trailing cleanup phase.
Recheck the issue discussion and refreshed master before implementation and
before publication; preserve this explicit requirement list through conflicts.
No extra tracking issues or PR stack is necessary just to begin the job.

## Proof required after implementation

Run the focused checks below after extending their relevant cases. Add a dedicated
Cleric ward/refill test and disposable Cleric journey only for the gaps described
above; use the current harness, scene, client, and backend helpers. Register new
tests with the existing runner as needed. The final focused results are recorded in the handoff below.

```sh
python3 tests/async/test_cleric_spell_progression.py
python3 tests/async/test_cleric_utilities_runtime.py
python3 tests/async/test_memorized_spell_eligibility.py
python3 tests/async/test_paladin_aura_cleanup.py
python3 tests/async/test_tick_work_spread.py
python3 tests/async/test_psp_move_regen.py
python3 tests/async/test_cleric_ward_runtime.py
python3 tests/async/test_gui_gmcp_contract.py
python3 tests/async/test_gmcp_prompt_regressions.py
python3 tests/async/test_nevent_scheduler_runtime.py
python3 tests/async/test_nevent_cancellation_runtime.py
python3 tests/async/test_native_artifact_runtime.py
python3 tests/async/test_holy_sacrifice_and_vamp_cap.py
python3 tests/async/test_healing_spell_precedence_runtime.py
python3 tests/async/test_class_helpfiles_contract.py
python3 tests/async/test_player_snapshot_capture.py
python3 tests/async/test_documentation_contract.py
make -C src -j12
make -C src -j12 PERSISTENCE_BACKEND=flatfile DMS_BINARY=../bin/server/dms_cleric_flatfile
./scripts/format.sh --check --rev origin/branch/issue-169-tsunami-vitality
git diff --check
```

Run the new Cleric gameplay/persistence journey and existing extended Tsunami
journey against both appropriate binaries and disposable databases, following
each script's actual arguments. Keep compiled artifacts and diagnostic evidence
under ignored `bin/`. Use ASan/UBSan for affect, aura, Intercession, and artifact
lifetime regressions. Do not require hosted CI to finish; report local failures
and any unrun checks precisely, while preserving normal review requirements.

Planning closeout: validate documentation links and whitespace, confirm the
preserved #166 file matches the baseline, create the linked issue-development
branch from refreshed master, commit only these two plan files, push, and read
back the remote commit and issue linkage. Do not mark the implementation work
items above complete during this planning publication.

## Implementation handoff — 2026-10-20

### Current delivery and continuation

All gameplay implementation is committed and pushed. Review the stack in order:

1. [#222](https://github.com/LuminariMUD/Duris/pull/222), access/progression and
   Healer aura lifecycle and correct help command: `c09f4fa60`, base `master`.
2. [#223](https://github.com/LuminariMUD/Duris/pull/223), timed self-only Warding
   and remaining-time snapshots, including GMCP countdowns: `1b01d5fe5`, base #222 branch.
3. [#224](https://github.com/LuminariMUD/Duris/pull/224), passive recovery and
   effective-healing refill: `ff94ba4f9`, base #223 branch.
4. [#225](https://github.com/LuminariMUD/Duris/pull/225), both Tsunami paths:
   `58a410f2b`, base #224 branch.
5. [#229](https://github.com/LuminariMUD/Duris/pull/229), narrow implementation
   regression and final handoff, base #225 branch.

The superseded aura-only [#226](https://github.com/LuminariMUD/Duris/pull/226) is
closed; its corrected implementation is folded into #222. The countdown repair
and tests from [#227](https://github.com/LuminariMUD/Duris/pull/227) are folded into
#223, and #227 is closed as superseded. All five active PRs remain open/non-draft.
They were rebased sequentially onto master `2315cb687` with explicit leases,
removing integration merges without duplicating repairs. That master includes
the already-merged retention documentation PR #228. No gameplay merge, release
tag, production operation or issue closure has occurred. Release tags belong to
an accepted release. Merge in the listed order and rebase/retarget each successor
onto master after its predecessor is squash-merged, excluding the old parent
branch's commits so the predecessor is not replayed.

This review pass uses the isolated worktree
`/home/aiwithapex/projects/duris-pr-review`; its detached HEAD publishes to
`branch/issue-169-qualification-proof`. Existing checkouts and local branches
are preserved; they may still refer to the pre-rebase history. Use this explicit
worktree for the recorded binaries and evidence.

Qualification changes extend the existing flatfile inspector, add one narrow disposable
server journey, and check incoming white-aura exclusions. They reuse the current
scene, clients and authority helper. The measurement matrix and separate offense
journey were removed after the owner narrowed scope. Offense changes only grant
existing spells; source-derived eligibility tests cover all 13 restored grants.

### Review repairs and focused proof

The substantive access/Tsunami review findings were reproduced and fixed:

- Successful ordinary and staff unspecialization purge lost Cleric auras. Failed
  epic transactions retain them. Staff updates the target's skills after clearing
  its spec. Base Paladin/Anti-Paladin auras remain valid and are preserved.
- Tsunami strengthens an existing Vitality affect in place. Real HP recalculation
  runs before position is observed: 10 HP with a 144-point buff becomes 70 HP
  after upgrading to 204. The Aramus crown object link remains intact, and real
  link removal still removes that affect. Both pilot modes pass ASan/UBSan.
- The GMCP finding is addressed directly in #223 using the repair from #227. The old serializer
  reported 158,400 seconds for 2,640 pulses. It now reports 660 then 430 seconds
  from the expiry event and preserves ordinary duration display. Divine Warding
  publishes its final state after all seven timers exist.

Focused checks passed on the rebased stack: progression,
saved-spell eligibility, Cleric utility timing, Cleric ward runtime, aura cleanup,
GUI GMCP serialization, player snapshot capture, tick work spread, PSP/movement
regeneration, scheduler and cancellation, native artifacts, Holy Sacrifice/vamp
cap, healing precedence, GMCP prompt, class help and documentation (14 cases).
Commands are listed above. Final fixture formatting and whitespace pass.
The aura regression now executes the real purge function and checks outgoing
links and event cancellation. The Python 3.11 review finding in #229 was
reproduced with Python 3.11.14; changing the two SQL f-strings' outer quotes
preserves the queries and allows compilation and `--help` on that interpreter.
The later #222 help finding was also reproduced: both Healer entries used an
unregistered aura command. They now use `aura_of_improved_healing`; the existing
class-help contract derives that name from `do_aura_healing`'s registration and
failed before the help edit, then passed. This help/test-only follow-up was
carried through each successor with no change under `src/`, preserving the
native build and both running-server journey results below.

Evidence boundaries:

- Eligibility uses source-derived registrations and real eligibility/innate
  functions: level boundaries, all 13 attacks, barrier, Kick caps, saved
  full/pending copies and multiclass.
- Utility proof runs the production scheduler/expiry callback at tick phases
  0/1/299, exact 2,640-pulse expiry, recasts, both timer-unit transitions,
  partial removal and scheduler admission failure. Affect storage is isolated.
  Snapshot capture saves 800 remaining pulses from a raw 2,640-pulse TTL without
  mutating live state.
- Ward proof runs actual capacity, rate, `StartRegen`, ward event, `heal`, `vamp`
  and Group Heal with an isolated deterministic event queue. All 40 level/epic
  cases fill in 960 +/- 1 pulses. It covers room/combat gates, restart, capacity,
  effective-healing boundaries, cap, Plague and incoming aura exclusions.
  Component Group Heal sizes 1/3/6 restore 14/46/94 ward. These are component
  measurements, not competitive balance acceptance.
- Native artifact proof covers both paths at levels 30/36/44/45/46/56, captured
  activation power, single weaker/equal/stronger buffs, exclusions, bystanders,
  low-HP recalculation, crown links and cancellation/lifetime.

### Builds and running-server qualification

Both native builds passed on the rebased #225 source `8ce856948`; #229 changes
only tests and documentation. The native source and binary hashes match the
previously qualified assembled implementation. SHA-256:

- MariaDB `bin/server/dms_new`:
  `795e8b0d1f229b562d2b687b53c75c24d4c53ed0389a8fbf9610101b8bc1b6dd`.
- Flatfile `bin/server/dms_cleric_flatfile`:
  `1928dde1dd373977da01a34e30d2b75a4d4c93e7e00e48cd69a624d22718ed47`.
Build logs are ignored `bin/cleric-review-{mariadb,flatfile}-build.log`.
Runtime JSON/transcripts also stay under ignored `bin/`; no credentials, player
data or generated outputs belong in commits.

The earlier extended `run_item_pilot_journey.py --family tsunami` passed pilot
off/on completion and native abort on the earlier implementation binary
`12c5b4c3fb66bef182293ca9d04c6452d600ac0a6cabe06fb77cdf3229e8320c`.
Actual level-1 max HP increased 32 to 96 on completion and zero on abort; native
completion included durable debit, restart, death and corpse recovery. That
historical run does not validate the later low-HP repair. Final component proof
and the new combined journey cover the repair separately.

Current command-level qualification:

```sh
python3 tests/async/test_flatfile_player_repository.py --build-inspector bin/tests/cleric-inspector
uv run --no-project --python 3.11 python -m py_compile tests/async/run_cleric_rebalance_journey.py
uv run --no-project --python 3.11 python tests/async/run_cleric_rebalance_journey.py --help
uv run --no-project --python 3.11 python tests/async/run_cleric_rebalance_journey.py --binary bin/server/dms_cleric_flatfile --output bin/cleric-review-flatfile.json
tests/async/with_disposable_mariadb.sh uv run --no-project --python 3.11 python tests/async/run_cleric_rebalance_journey.py --binary bin/server/dms_new --backend mariadb --output bin/cleric-review-mariadb.json
```

Both flatfile and MariaDB journeys passed on the final gameplay binaries: saved Vital denial;
Healer-only activation; staff and ordinary aura removal; Miracle 35 denial/36
success; True Seeing 45 denial/46 success; Miracle/Tsunami upgrade 144 to 204;
10 HP becomes 70 HP while standing; stronger level-62 Vitality is preserved;
self-only Warding; all seven timers save/copyover/restart at 2,620 -> 2,601 ->
2,590 remaining pulses; restored shortened test timers expire. Component proof
separately checks the real 2,640-pulse duration. Both backends produced identical
remaining-time sequences and passed ordinary unspecialization and restored expiry.
Results are `bin/cleric-review-{flatfile,mariadb}.json`; transcripts use
the corresponding `.log` paths. Both runs exited zero and cleaned their servers
and disposable database authorities.

Fixture saved preparations use canonical permanent flags and duration -1.
The final restored-expiry leg shortens only disposable saved timers to 40 pulses;
it verifies materialization/expiry while the scheduler regression proves the
2,640-pulse contract. No gameplay safeguard was weakened.

### Remaining acceptance

Implementation, local builds, focused regressions, both persistence journeys and
publication are complete. All five active PR bases/heads and remote parity were read
back; the task worktree is clean after publication. No CI wait is required by
repository instructions. Normal owner review remains required. No full burn-in
or production deployment was run.

The owner explicitly excluded balance measurements from this task. Do not claim
that implementation checks establish competitive balance, and do not expand this
work into a measurement campaign. The broader unchanged aura/spell mechanics are
covered by existing focused tests rather than a new scenario matrix.

Production acceptance needs separately authorized deployment, property reload,
help import and runtime verification at the actual deployed revision. Keep #169
and this plan active until owner production acceptance is recorded.
