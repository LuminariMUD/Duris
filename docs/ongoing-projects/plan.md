# Issue #169: Cleric rebalance implementation plan

Status: implementation in progress, 2026-10-20. Production and balance acceptance remain open.
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

The balance claims remain hypotheses. A correct implementation must be tested as
a combined package; these changes alone do not prove that group sustain or class
choice is balanced.

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

## Verified source findings

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
- [ ] Extend `test_cleric_spell_progression.py` and
  `test_memorized_spell_eligibility.py` with actual grant/spec inputs and
  boundary cases: 25/26, 29/30, 30/31, 35/36, 40/41, 45/46, 50/51, and 56.
  Exercise prepare/cast/list behavior and saved full/pending copies, including
  lawful multiclass access and specialization transitions. Ordinary restored
  grants do not automatically give a character maximum trained proficiency.
- [ ] Execute retained Holy Intercession through group application, damage,
  pool depletion, recast, and expiry. Check both old IDs during the transition.
  Verify the 13 spells' ordinary target, area, save, alignment/undead, and damage
  behavior; verify Negative Energy Barrier's `AFF4_NEG_SHIELD`, Soulshield
  incompatibility, and ward interaction. Do not weaken safeguards to make new
  access work.

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
- [ ] Extend `test_cleric_utilities_runtime.py` beyond its current stubbed
  expiration path: prove no expiry before 2,640 pulses and expiry at the due
  pulse, independent of the global affect-tick phase. Cover all seven effects,
  both refresh orders, repeated recasts, partial dispel, removal/extraction,
  canceled old callbacks, and a scheduling failure without a permanent buff.
  Confirm unrelated effects and individual protection casts retain their behavior.
- [ ] Prove remaining-time display and persistence. Existing
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
- [ ] Exercise the innate command as an ordinary Cleric, Healer, Holyman,
  Zealot, and Paladin; verify group members entering/leaving, provider removal,
  death, and respecialization. Reuse linked-aura cleanup and extend
  `test_paladin_aura_cleanup.py` or the Cleric runtime harness where actual
  entitlement/application coverage is missing.
- [ ] Test Healer/Healer and Healer/Paladin providers in both activation orders.
  One white aura must not multiply itself. Preserve the existing incoming-healing
  exclusions for regeneration, Accelerated Healing, and Regenerate; measure the
  resulting effective healing and ward refill alongside the outgoing 1.20 scalar.
  Different existing aura types may coexist according to the existing rules.

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
- [ ] Add focused executable ward/refill coverage, reusing the existing
  regeneration fixtures rather than creating a balance framework. Exercise
  production capacity/rate, `ward_regen()`, `StartRegen()`,
  `event_ward_regen()`, `heal()`, and `vamp()`; stubbing the rate is insufficient.
  Test levels 30/36/46/51/56 and epic 0/32/33/65/66/98/99/100. In an ordinary room,
  with no healing or other ward bonuses, empty-to-full should be 960 pulses,
  allowing at most one pulse for numeric rounding, independent of capacity.
- [ ] Test no-heal/heal rooms, combat entry/exit, ordinary restart scheduling,
  zero/partial/full ward, changed capacity, and save/reload. Separate time waiting
  for regeneration to restart from its measured 0-to-full recovery; do not hide
  either in a timing claim. For refill, include effective healing 0/1/9/10/19/20,
  overheal, healing reduction, white aura, multiple Healers, and Group Heal sizes
  1/3/6. The sum is per-recipient `floor(effective HP / 10)`, capped at max ward.

### W5 — Tsunami Vitality in both execution paths

- [ ] Apply `min(level + 15, 60)` to Vitality only in the legacy callback and
  native adapter. Preserve native activation-time level capture, delay,
  cancellation, ownership checks, mana cost, and the 300-second tap cooldown.
  Leave thrust/raise, waves, item stats, and pilot defaults unchanged.
- [ ] Handle an existing weaker Vitality explicitly; changing the argument to
  `spell_vitality()` alone does not do so. For an eligible recipient, use the
  existing affect mutation/replacement APIs to retain exactly one Vitality with
  the greater of its current HP modifier and `4 * min(wielder level + 15, 60)`.
  Preserve the current refresh duration of 15 ticks and ordinary fresh-cast
  duration. Never downgrade a stronger existing effect or stack HP modifiers.
  Preserve incompatible deity Vitality restrictions and reflection exclusions.
- [ ] Share only the needed Tsunami application logic between the two real
  callers if otherwise duplicated; do not change ordinary Vitality or Miracle
  globally. Apply the existing self/same-non-null-group test before both new
  application and refresh in both routes. The legacy bystander refresh must not
  become a bystander HP upgrade.
- [ ] Extend `test_native_artifact_runtime.py` to assert power at wielder levels
  30/36/44/45/46/56 (effective levels 45/51/59/60/60/60), with the native pilot
  disabled and enabled. Add real Vitality/affect recalculation coverage for fresh,
  weaker, equal, and stronger effects; test Miracle before/after tap, ungrouped
  self, group members, bystanders, absent members, and interruption.
  Extend the existing `run_item_pilot_journey.py --family tsunami` journey to
  observe actual max HP and duration, not just the cast message.

### W6 — Help and saved-character compatibility

- [ ] Update both maintained help import sources,
  `help/duris_help_parsed.hlp` and `lib/information/help_index`: Cleric skills,
  Healer, Holyman, Improved Healing aura, Divine Warding, Miracle/True Seeing,
  Warding Faith/Epic Warding Faith, and affected spell descriptions. Describe
  training, real specialization unlock, circle 8, elapsed minutes/seconds, and
  10% effective-healing refill accurately.
- [ ] Update the current Tsunami contract in
  `docs/reference/NATIVE_ARTIFACT_PILOTS.md` and Healer capability text in
  `docs/reference/CLASS-POINTS.md`. Leave historical rankings and source snapshots
  unchanged. Keep published player news/help import for the authorized release.
- [ ] Run help/progression contracts. Use disposable existing-character fixtures
  for full/pending Vital and Miracle preparations, old ordinary protection
  affects, new timed protections, trained Kick, and all Cleric specs across both
  persistence backends. Preserve IDs and existing source attribution; add no
  bulk SQL/pfile cleanup unless a demonstrated compatibility failure requires it.

### W7 — Combined qualification and issue acceptance

- [ ] Record exact source/binary revisions, backend, effective properties, pilot
  mode, level, epic skill, race, gear, and group composition. Compare the unchanged
  baseline, relevant individual changes for attribution, and the assembled
  package on matched PvE/PvP scenarios.
- [ ] Include Healer, Holyman, and Zealot; base/epic ward; solo and 3/6-character
  groups; one/multiple Healers; Paladin white/other-aura combinations; Negative
  Energy Barrier versus Soulshield; and Miracle/Tsunami buff order. Measure
  effective healing, ward restored/absorbed, spell expenditure, fight duration,
  time to kill, and solo damage/PvE kill rate.
- [ ] Verify restored offense does not inherit Zealot bonuses, reduced passive
  recovery is actually four minutes, the new aura does not double-stack, and
  Group Heal's total refill is reported rather than assumed small. Publish
  before/after measurements for owner balance review; no numeric TTK target is
  established by the issue. Additional nerfs require a separate measured proposal.
- [ ] Complete local implementation proof before requesting deployment. After
  separately authorized deployment, record the actual deployed revision and
  effective properties and confirm the player-facing behavior. Keep #169 open
  while required balance/production acceptance is outstanding; a plan commit
  or passing component test is not issue completion.

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
tests with the existing runner as needed. These future tests are not claimed to
exist or pass yet.

```sh
python3 tests/async/test_cleric_spell_progression.py
python3 tests/async/test_cleric_utilities_runtime.py
python3 tests/async/test_memorized_spell_eligibility.py
python3 tests/async/test_paladin_aura_cleanup.py
python3 tests/async/test_tick_work_spread.py
python3 tests/async/test_psp_move_regen.py
python3 tests/async/test_nevent_scheduler_runtime.py
python3 tests/async/test_nevent_cancellation_runtime.py
python3 tests/async/test_native_artifact_runtime.py
python3 tests/async/test_holy_sacrifice_and_vamp_cap.py
python3 tests/async/test_healing_spell_precedence_runtime.py
python3 tests/async/test_class_helpfiles_contract.py
python3 tests/async/test_player_snapshot_capture.py
python3 tests/async/test_documentation_contract.py
make -C src -j4
make -C src -j4 PERSISTENCE_BACKEND=flatfile DMS_BINARY=../bin/server/dms_cleric_flatfile
./scripts/format.sh --check
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

The worktree started clean at `808d45117`; refreshed `origin/master` remains
`b81715f3a`. The revised issue discussion was rechecked. No existing PR uses this
branch. First delivery: W1 grant changes and W3 Healer aura entitlement, with
matching help and executable eligibility proof. Outcome: preserve existing spell
and aura mechanics while changing only access/progression. Non-goals: production
operations and global spell/aura changes. Files: class grant tables, maintained
help, capability reference and existing focused tests. Proof: source-derived
grants through actual eligibility functions, aura cleanup, help contracts and
required native build. Further runtime journeys remain explicit open gates below.

Ablation: no migration, new balance framework or spell implementation is needed
for grant-table changes. Existing saved-spell eligibility already checks current
circles before honoring a full prepared slot; extend that proof for #169.

First chunk validation passed: `make -C src -j4` (MariaDB development binary),
`test_memorized_spell_eligibility.py` (ASan/UBSan, source-derived grants and real
eligibility/innate functions), `test_cleric_spell_progression.py`,
`test_paladin_aura_cleanup.py`, `test_class_helpfiles_contract.py`,
`test_documentation_contract.py` (14 cases), `./scripts/format.sh --check`, and
`git diff --check`. Exact build output: ignored `bin/cleric-build.log`.
No release tag is appropriate for an unmerged gameplay change.
W1 command/combat and W3 group/lifetime journeys remain open; the tests above do
not claim that coverage. Next implementation chunk is W2.

W2 in progress on `branch/issue-169-divine-warding`, stacked on PR #222
(`988dd1e6d`, remote verified). Shared timer replacement is local to the seven
protections: ordinary casts restore tick-based duration, bundle casts use 2,640
pulses, and removal cancels the previous timer. Timed scheduling failure removes
the affected protection instead of leaving it permanent. Inspecting persistence
found the snapshot capture path copies raw short-affect duration without first
refreshing remaining time; the legacy saver calls `updateShortAffects`, but the
current save pipeline bypasses that call. Reproduce and repair this W2 blocker.

W2 focused proof passed with ASan/UBSan: the extended Cleric utility harness runs
the production scheduler and expiry callback at tick phases 0/1/299, checks the
exact 2,640-pulse deadline, recasts, both timer-unit transitions, partial dispel,
removal and real scheduler sequence-exhaustion admission failure. Effect-list
storage is isolated in that harness; full-server extraction remains a journey
gate. `test_player_snapshot_capture.py` reproduces original TTL 2,640 versus
remaining 800 and proves capture saves 800 without mutating the live value.
The fix applies to shared snapshot capture used by both backends. Snapshot
codec/backends/relogin/copyover journeys must still prove the whole handoff.

W2 publication checks passed: MariaDB native build, Cleric progression/eligibility,
snapshot capture, all scheduler timing/priority/catch-up modes and cancellation
under ASan/UBSan, class help and documentation contracts, format and whitespace.
Scheduler logs are ignored `bin/cleric-scheduler.log` and
`bin/cleric-cancellation.log`. This chunk is ready for focused review; W2 complete
persistence journeys and the assembled-package gates remain open.

W4 in progress on `branch/issue-169-ward-recovery`, stacked on PR #223
(`c11bfab61`, remote verified). Move only innate recovery out of integer
`TmpAffs.ward_reg`; keep the existing event accumulator and character layout.
Rate policy now expresses points per 300 pulses and converts seconds using
`WAIT_SEC`. The combined rate is evaluated before the full-ward early return.
Healer refill remains based on `vamp()` effective HP, now divided by ten.

W4 component proof: new `test_cleric_ward_runtime.py` passed under ASan/UBSan.
It extracts the actual innate capacity block (without other affect modifiers),
executes real `ward_regen`, `StartRegen`, `event_ward_regen`, `heal`, `vamp`, and
Group Heal with an isolated deterministic event queue. All 40 level/epic cases
fill at 960 +/- 1 pulses. It checks full-rate sign, heal/no-heal rooms, combat,
NPC multiplier, duplicate scheduling, effective healing 0/1/9/10/19/20/200,
overheal, cap and aura-enhanced group refill. Group sizes 1/3/6 restore 14/46/94
ward in the fixed 120-point Group Heal fixture; the healer's outgoing scalar is
1.20 and the level-56 white aura on other recipients adds 11.2%. This is component
measurement, not matched PvE/PvP balance proof. Native MariaDB build,
`test_tick_work_spread.py` and `test_psp_move_regen.py` passed.

Additional W4 checks passed: combat interrupts/restarts the chain; Plague reduces
120 attempted healing to 84 effective HP and 8 ward; direct `vamp()` restores no
ward. Existing scheduler, Holy Sacrifice/vamp-cap, healing-precedence, help and
documentation tests pass after the rate declaration change. The new test is
automatically discovered by `tests/run_regression_tests.py`; no registry needed.
Full persistence/restart and matched combat balance gates remain open.
