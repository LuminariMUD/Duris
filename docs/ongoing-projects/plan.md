# Issue #215: Conjurer specialisation rebalance

> Issue #368 legacy trap implementation and qualification are maintained in
> [plan-issue-368.md](plan-issue-368.md).

Updated 2026-10-25. **Status: implementation in progress; Planar Affinity is the
first independent review chunk.** Work on branch
`branch/issue-215-conjurer-rebalance`, in the existing worktree
`/home/aiwithapex/projects/duris-issue215-conjurer-rebalance`.

Source baseline: `e1efb9bc0779e8b6615353c5672e29f21c6bb7a8`.
The [issue](https://github.com/LuminariMUD/Duris/issues/215) and
[owner's final decision of 2026-10-22](https://github.com/LuminariMUD/Duris/issues/215#issuecomment-6339124853)
define the scope. The final decision supersedes preliminary percentages, cooldowns
and level assumptions in earlier comments. The
[technical review](https://github.com/LuminariMUD/Duris/issues/215#issuecomment-6286381197)
and [pet investigation](https://github.com/LuminariMUD/Duris/issues/215#issuecomment-6318968624)
supply the interaction regression cases.

Owner scope clarification, 2026-10-25: **players will test the balance**.
Our work covers implementation and functional qualification of the agreed
mechanics, limits and compatibility. Comparative balance benchmarks, class
scorecards and judgments about relative spec power are outside this task.

The owner's 2026-10-25 implementation request explicitly authorizes source changes,
focused tests, commits, pushes and focused/stacked PRs. Leave delivered work ready
for review. Merging and deployment are outside this request. The previous contents
of this path are preserved verbatim in [the issue #264 plan](plan-issue-264.md).

## Outcome and boundaries

Deliver the complete approved first pass: Earth sustains physical protection;
Air gains formed self-recovery and shorter travel lag; Water gains a reliable
spring, its own form and controlled shoreline movement; Fire gains its approved
spell pressure, full form and optional mephits. All four Magi and Psycheporter
receive the specified level-51 affinity behavior. Player help and executable
regressions ship with the corresponding behavior.

Keep these boundaries throughout:

- Water Form ocean access has **no additional level-51 gate**. Form availability
  at circle 10 and level-51 Water Affinity are separate mechanics.
- No Cyclone buff, Searing Heat/Scorched combo, Magma Burst adjustment, Solar Flare
  increase beyond **10%**, Water regeneration repair, or extra healing/mitigation.
  The fractional Water regeneration truncation remains a separate investigation.
- No new immunity for player Grapple/Bearhug, new mephit abilities, additional pet
  slots, selectable greater variants, or blanket protection for pets/groupmates.
- No expansion of affinity geography or general scripted-aggro immunity.
- No new balance framework, scheduler, general movement service, database schema,
  or persistent reservation system. Reuse existing gameplay paths and test tools.
  If an inspected consumer requires an additional file, document that dependency
  here before widening the change.
- Follow `AGENTS.md`. Formatting is **check-only** for this issue; make any
  necessary edits deliberately. Do not run autofix or formatting rewrites.
  Production operations require their own authorization.

## Source map and implementation constraints

These paths and behaviors were checked on the baseline above. Recheck the owning
function after any base update; historical issue line numbers are not reliable.

| Area | Owning source and observed constraint |
| --- | --- |
| IDs and registration | [spells.h](../../src/magic/spells.h), [structs.h](../../src/core/structs.h), [skills.c](../../src/classes/skills.c), [prototypes.h](../../src/core/prototypes.h). `LAST_SPELL` is currently `SPELL_BLOOD_TITHE` (683); `LAST_INNATE` is `INNATE_REFLECTION` (179). Append IDs without renumbering saved identifiers; recheck available IDs before implementation. |
| Forms and aura conflicts | [magic.c](../../src/magic/magic.c): `spell_air_form()`, `elemental_aura_failure_message()`, `spell_elemental_aura()`; [psionics.c](../../src/classes/psionics.c): `spell_fire_aura()`; [affects.c](../../src/magic/affects.c). Aura priority clears competing bits, including Ice Aura, without being a safe whole-form rejection mechanism. |
| Casting resources | [sparser.c](../../src/net/sparser.c) checks Elemental Aura eligibility before `use_spell()`. Extend this established preflight path and retain handler-side validity checks for other callers. |
| Healing | [ethermancer.c](../../src/classes/ethermancer.c): `spell_ethereal_recharge()`; [fight.c](../../src/combat/fight.c): `heal()` / `vamp()`. Healing modifiers precede the final HP ceiling, so the existing cap can enforce a 100-HP actual increase without another healing API. |
| Earth and direct spell changes | [magic.c](../../src/magic/magic.c): `spell_stone_skin()`, `has_skin_spell()`, `spell_earthen_maul()`, `spell_fireball()`, `spell_solar_flare()`, `spell_dimension_door()`, `spell_relocate()`. |
| Damage and skin consumption | [fight.c](../../src/combat/fight.c): `decrease_skin_counter()` already consumes the first matching layer; Earth Aura mitigation, fire absorption and all-layer critical shatter already exist. [dam_mods.c](../../src/combat/dam_mods.c) owns elemental vulnerability modifiers. |
| Water spring | [innates.c](../../src/classes/innates.c): `check_innate_time()` consumes a use; `do_conjure_water()` currently calls it before scheduling; `event_conjure_water()` creates VNUM 93300 in the caster's current room. [duris.properties](../../lib/duris.properties) has no Conjure Water timer override. |
| Delayed actions | [new_events.c](../../src/world/new_events.c), [events.c](../../src/world/events.c), [prototypes.h](../../src/core/prototypes.h) provide scheduling results, actor ownership, event lookup, cancellation and owned-payload cleanup. The legacy `add_event()` flag argument is ignored; it cannot supply movement/combat cancellation. |
| Movement and interruption | [actmove.c](../../src/cmd/actmove.c): `can_enter_room()`, `do_simple_move()`, `do_simple_move_skipping_procs()`; [utility.c](../../src/core/utility.c): `move_cost()`; [handler.c](../../src/world/handler.c): `char_from_room()` and extraction; [fight.c](../../src/combat/fight.c): `set_fighting()`. Room entry checks also serve teleports; only a validated directed crossing may get the new exception. |
| Summons | [magic.c](../../src/magic/magic.c): `spell_conjour_elemental()`, `spell_conjour_greater_elemental()`, `conjure_specialized()` (these are the actual spellings). [heavens.mob](../../areas/mob/heavens.mob) contains Fire prototypes 1100 and 1110-1112; these remain reference data, not replacement prototypes. |
| Affinity | [innates.c](../../src/classes/innates.c): registration/`has_innate()`; [utility.c](../../src/core/utility.c): `aggressive_to()`; [mobact.c](../../src/mob/mobact.c): `MobStartFight()` and memory; [map.h](../../src/world/map.h): existing plane ranges. |
| Player help | [help_index](../../lib/information/help_index), [duris_help_parsed.hlp](../../help/duris_help_parsed.hlp), [importer](../../scripts/import_help_to_prod.sh). Parsed topics are imported last. A mention in another topic's See also section is not a dedicated help entry. |

Ablation decision: use the existing final healing cap, individual affect records,
damage flags, summon selection and event lifecycle. Small shared checks are
justified where the same rule has actual callers, such as casting preflight plus
handlers or the two affinity entry points. Do not add parallel representations
of the same state, duplicate elemental prototypes or a general policy layer.

## Delivery sequence

Each implementation step includes its tests and corresponding help edits.
Step 8 reconciles the complete package; it is not a reason to defer help.
The order below is a working sequence, not a requirement for a PR stack.

| Step | Deliverable | Dependency | Status |
| --- | --- | --- | --- |
| 0 | Freeze baseline and capture focused pre-change behavior | Implementation authorization | In progress; relevant baselines pass |
| 1 | New forms, registration, resource checks and cleanup | 0 | Review-ready [PR #378](https://github.com/LuminariMUD/Duris/pull/378), stacked on #376 |
| 2 | Earth Stone Skin layers and shared Earthen Maul | 1 for combined mitigation proof | Review-ready [PR #379](https://github.com/LuminariMUD/Duris/pull/379), stacked on #378 |
| 3 | Air Recharge and travel lag | 1 | Review-ready [PR #380](https://github.com/LuminariMUD/Duris/pull/380), stacked on #379 |
| 4 | Reliable Conjure Water | 0 | Review-ready [PR #381](https://github.com/LuminariMUD/Duris/pull/381), stacked on #380 |
| 5 | Water Form shoreline traversal and ocean cost | 1, event lifecycle established in 4 | Review-ready [PR #382](https://github.com/LuminariMUD/Duris/pull/382), stacked on #381 |
| 6 | Fire damage and optional mephits | 1 for combined Fire mechanics proof | Review-ready [PR #384](https://github.com/LuminariMUD/Duris/pull/384); crash-state follow-up in progress |
| 7 | Five level-51 affinities | 0 | Review-ready [PR #376](https://github.com/LuminariMUD/Duris/pull/376) |
| 8 | Complete help, functional gameplay evidence and review handoff | 1-7 | Pending |

### 0. Establish the implementation baseline

- Confirm the branch, clean/dirty state and current base. Preserve unrelated work.
  Capture the baseline commit and relevant property values for regression checks.
- Run the relevant existing aura, affect, casting, innate and help checks before
  changing their paths. Record any existing failures separately.
- Establish legal test characters at levels **46, 50, 51 and 56**, plus **30 and
  41** for Psycheporter regression. Use actual circle eligibility, memorised
  spells and resources. Use only the fixtures each functional check needs.
- Capture current spell damage, HP changes, Stone Skin charge use, travel waits,
  spring timing and plain summon variants. Use deterministic random inputs for
  component comparisons and actual elapsed pulses for delayed-action journeys.
- Record the deferred regeneration and affinity-boundary findings without
  correcting them in this package.

### 1. Add the three elemental forms and prevent conflicting casts

**Files:** `src/magic/spells.h`, `src/classes/skills.c`,
`src/core/prototypes.h`, `src/magic/magic.c`, `src/net/sparser.c`;
touch `src/magic/affects.c` and competing aura handlers only where required for
conflict/cleanup correctness.

- Append Earth Form, Fire Form and Water Form spell IDs. Register each only for
  the corresponding Conjurer specialisation, at **circle 10**, self-only, with
  an expiration message. Use Air Form's existing casting pattern as the default;
  do not introduce new terrain, combat or resource restrictions.
- Every new form lasts **8 affect-duration units**, with no terrain check or
  random full-form save. Keep Air Form's existing circle, duration and effects.
  Affect units must not be described as seconds or permanent duration.
- Earth Form supplies `AFF2_EARTH_AURA`: the existing **1-in-6** eligible physical
  rejection, including Earth Elemental and `PHSDAM_NOREDUCE` exceptions.
  Add neither Druid stat bonuses nor a second mitigation roll.
- Fire Form supplies the existing full Pyrokinetic effect: **AC -15,
  STR_MAX +15, DEX_MAX -20, AGI_MAX -20, CON_MAX +25**,
  `AFF2_FIRE_AURA` and `AFF2_FIRESHIELD`. Preserve cold vulnerability and
  the existing qualifying fire-absorption HP recovery, including its 110%-max-HP
  ceiling. Add no castable heal or independent damage mechanic.
- Water Form supplies **STR_MAX -20, DEX_MAX +50, AGI_MAX +25, CON_MAX -10**
  and `AFF2_WATER_AURA`. Inherit Capture protection and the selected existing
  mob AI Maul/Bash/Springleap exclusions. Add no universal player grapple immunity,
  water source, regeneration, healing multiplier or separate damage reduction.
- Give all components of each new form its own spell type and equal duration.
  Use normal affect ownership/removal so expiry, dispel and recast clean up the
  entire form while respecting independently supplied effects.
- Reject new forms against existing mutually exclusive elemental auras/forms,
  including Ice Aura and partial aura spell effects. Reject competing aura
  casts while a form is active. Check before mana/prepared-spell consumption and
  again at application; an aura may change during casting. Keep legacy
  Druid/Pyro terrain rules and existing shield interactions.
- Audit ID/table bounds and existing spellbook/affect save/load consumers. Append
  identifiers and use their existing formats; add focused persistence coverage
  for any changed consumer rather than assuming a schema migration.

**Proof:** matching-spec-only acquisition and self-targeting; ordinary rooms,
water, no-ground rooms and unrelated planes; paired conflict orders and mid-cast
conflicts without resource loss; finite expiry/dispel/recast with exact stat/flag
restoration; actual Earth rejection and Fire absorption/cold response; Water
Capture versus player grapple behavior. Keep existing Air/Druid/Pyro behavior
covered. Extend the existing elemental-aura and affect tests, with a command-path
check as well as handler tests.

### 2. Implement personal Earth layers and shared Earthen Maul access

**Files:** `src/magic/magic.c`; `src/combat/fight.c` or affect code only if
the existing layer handling needs a demonstrated adjustment.

- Permit up to **three independent Stone Skin affects on an Earth Magus PC
  recipient**. Gate on the recipient, not merely the caster: an Earth caster
  cannot grant three layers to an ordinary groupmate or pet.
- Preserve each cast's existing charge formula, caster bonuses and **4-unit**
  duration. Do not refresh older layers, combine their charges or change other
  skin-spell exclusions. Refuse a fourth layer without modifying the first three.
- Retain the existing newest-first, single-layer charge decrement on each
  eligible hit and ordinary all-layer critical shatter/dispel. Do not multiply
  per-hit mitigation by the number of remaining layers or alter unrelated skins.
- Remove Earthen Maul's ground/altitude rejection for **every existing eligible
  caster**, including Druids. Use the normal damage tier for newly eligible
  earthless situations. Preserve saves and real terrain-specific bonuses/maluses.
  Keep earthless fallback distinct from the indoor/landslide upgrade so an
  indoor no-ground room does not accidentally gain bonus damage.

**Proof:** zero through three layers and rejected fourth; caster/recipient matrix;
different charges and expiry times; newest-first depletion and last-layer
messages; all-layer critical/dispel removal; no extra reduction with Earth Form.
Exercise Maul on water/ocean, in flight, no-ground and elemental-plane rooms,
alongside existing ordinary/indoor/mountain/lava cases and non-Earth casters.
Use matched rolls to prove normal fallback damage and retained valid modifiers.

### 3. Add the Air self-heal and travel lag reductions

**Files:** `src/classes/ethermancer.c`, `src/magic/magic.c`; use the existing
`heal()`/`vamp()` implementation.

- Add the Air Magus **self-only, active Air Form** eligibility exception to
  Ethereal Recharge. The generic Air Aura bit alone is insufficient.
- Preserve Cure Blind and the existing healing calculation, but pass a final HP
  ceiling equivalent to `min(maximum HP, HP before healing + 100)` for this
  exception. The actual increase must never exceed **100 HP after modifiers**.
  Do not heal first and subtract overflow: XP, achievements and feedback must
  observe the amount actually restored.
- Preserve the existing legitimate other-target route and its **150-base-HP**
  behavior. Do not widen target classes or add an out-of-form self exception.
- Set Air Magus Dimension Door lag to **3 seconds** and Relocate lag to
  **5 seconds**, expressed using existing pulse constants. These are post-cast
  waits, not spell casting-time reductions. Preserve the Shadow Sorcerer
  **1-second** cases, other PC/NPC waits and all target/combat/PvP/teleport checks.

**Proof:** active spell versus loose aura, self versus other target, no form,
low/full/overfull HP; enhanced healing, hardcore and incoming healing modifiers,
plus reduction effects and Cure Blind at the HP cap. Exercise the real
`heal()`/`vamp()` chain, not a stub that omits modifiers. Measure waits for Air,
ordinary PCs, NPCs and Shadow Sorcerers, including rejected travel attempts.

### 4. Make Conjure Water reliable

**Files:** `src/classes/innates.c`, `lib/duris.properties`, and narrow lifecycle
integration in `src/world/handler.c` if needed.

- Set `innate.timer.secs.conjureWater=300`: **5 minutes**. Schedule creation and
  action lag for **one PULSE_VIOLENCE / 4 seconds**, concurrently. Keep spring
  VNUM **93300** and **15-minute** decay.
- Before starting, check innate availability without spending it and reject an
  existing summoned spring or a pending summon for the same room. Rejection
  adds no lag, innate use or cooldown. Prevent a caster queuing several summons.
- Reuse actor-owned scheduled events for pending state, recording the origin
  room. Detect the room's pending summons through existing event/character state;
  cancel on leaving the room. Avoid a second persistent reservation registry.
- On completion, revalidate origin, caster eligibility, innate availability and
  room occupancy. Create/place the object successfully before committing the
  innate use; report success only when a spring exists.
- Handle scheduling refusal, missing prototype, failed object creation,
  cancellation, death/extraction and movement without consuming a use.
  Release pending state on every exit, including scheduler cleanup. If placement
  or final eligibility fails, remove only the object created by this attempt.
- Keep `check_innate_time()` semantics for other innates. Reuse an existing
  read-only availability check if suitable; add only the narrow check this
  delayed charge needs.

**Proof:** two different players racing in one room; repeat command; spring
already present; spring appears during the wait; move away and return; death,
extraction and event scheduling failure; missing prototype/object failure;
cancel then retry; successful expiry and resummon. Verify exactly one spring,
one use committed on success, zero uses on failure, and no stale pending state.
Time spent before an initiated summon is cancelled is not retroactively refunded.

Water to Life remains unchanged: `2*level + max(0, level-50)*20` gives **232 base
HP at level 56** before existing healing modifiers. It still requires external
natural water or a suitable ground container in the caster's room, does not
consume that water, uses prepared spell copies, and has no new dedicated cooldown.
Keep self/water-elemental/water-formed target restrictions.

### 5. Add Water Form shoreline movement

**Files:** `src/cmd/actmove.c`, `src/core/utility.c`, narrow cancellation
hooks in `src/world/handler.c`, `src/combat/fight.c` and form-removal code;
declare only the needed callbacks/checks in existing headers.

- Eligibility is a **Water Magus PC with active Water Form**, with no additional
  level gate. Keep generic Water Aura, other classes and level-51 affinity from
  implicitly granting access.
- Land-to-ocean and ocean-to-land movement through a valid adjacent exit waits
  **5 seconds before crossing**, in both directions. Ocean-to-ocean movement
  does not acquire this shoreline preparation delay.
- Use one actor-owned pending event with origin, direction and destination.
  Prevent duplicate transitions. At initiation check the legal route, movement
  state and absence of combat; at completion revalidate the same route, form,
  position, resources and normal movement restrictions.
- Cancel when combat begins, even if it ends before the callback. Likewise
  invalidate on leaving the origin, death/extraction, loss of form or interruption;
  leaving and returning or losing and recasting the form must not revive the
  pending crossing. Use existing cancellation and ownership cleanup.
- Route completion through the ordinary directed movement pipeline, including
  exit/wall/proc/trap checks and safe handling if a proc extracts the mover.
  Grant only the specific shoreline entry exception for that validated action.
  Do not relax generic `can_enter_room()` behavior for teleport callers, or
  implement the crossing by directly placing the character in the destination.
- Apply a **25% reduction** to the existing computed travel cost for eligible
  steps touching ocean, including ocean-to-ocean travel: truncate to an integer
  with `max(1, cost * 3 / 4)`. Keep stance/injury surcharges in their existing
  positions and use the same payable cost for exhaustion checking and deduction.
  Ordinary land-to-land movement receives no discount; preserve existing
  current/terrain hazards and unrelated cost modifiers.
- Preserve independent checks for mounts, riders, pets, charmies and group
  followers; the caster's exemption does not carry them across. Leave ships,
  cargo, fleeing and teleport destinations without a new bypass.
- When the form expires at sea, restore normal rules without forced relocation.

**Proof:** form at level 46 and gates at 50/51; both shoreline directions and
ocean-to-ocean movement; timed position before/after 5 seconds; combat starting
and ending during preparation; form expiry/dispel/recast; leave-and-return;
closed/blocked/changed exit, death/extraction, repeated commands and schedule
refusal. Check actual vitality deductions at low costs and exhaustion boundaries,
ordinary land movement, currents, followers/mounts/cargo and ocean-target
Dimension Door/Relocate/random teleport. Include a PvP pursuit journey.

### 6. Implement the approved Fire damage and mephit option

**Files:** `src/magic/magic.c`, the existing casting preflight where argument
validation requires it, and affected help/tests.

- For a **Fire Magus at player level 51+**, let Fireball deliver **100% of its
  ordinarily calculated damage through standard Globe**. Narrow the relevant
  `SPLDAM_GLOBE` flag at the spell caller; preserve saves, applicable wards,
  Protection from Fire, Fireshield, absorption and the rest of the damage path.
  Spell/item strength must not substitute for the player's unlock level.
- Increase Solar Flare's **direct base damage exactly 10% for Fire Magus** with
  deterministic integer rounding. Do not apply this multiplier to Star Magus,
  NPC/item callers, blindness, Immolate, or Magma Burst. Preserve random call
  order and existing damage/counterplay behavior.
- Accept the optional `mephit` argument on the existing **circle-5 Conjure
  Elemental** and **circle-11 Conjure Greater Elemental** paths for Fire Magus.
  Thread that choice into `conjure_specialized()` for the greater case.
- Summon exactly the original Fire variant: **1100** or the existing random
  choice among **1110-1112**. Adjust only the summoned instance's Fireshield and
  mephit names/descriptions. Preserve race/elemental identity, other protections,
  base and scaled stats, Infuse Life, costs, control, caps, duration and random
  variant distribution. Verify affect recalculation cannot restore the removed
  prototype shield during the pet's normal lifetime.
- Plain casts retain the normal shielded elemental. Restrict recognition of the
  new option to the eligible Fire path; reject malformed Fire option text
  clearly, and preserve other callers' existing argument behavior.
  Do not globally edit prototypes, create a separate summon spell or add a
  selectable greater variant.

**Proof:** Fireball at 50/51 and non-Fire controls, standard Globe with all normal
mitigation combinations; Solar Flare with matched rolls for Fire/Star/NPC/item
callers and unchanged secondary effects. Compare every plain/mephit variant
under matched RNG and scaling, normal summon limits/failures and invalid args.
Exercise pet combat, affect recalculation and normal lifecycle.

Use a focused multi-mob pull regression to verify that the mephit omits
Fireshield retaliation and its resulting owner-memory/hunter side effects.
Fireshield retaliates against each attacker; it is not a room-wide attack.
Retain normal provocation from other pet actions. Players will assess the
damage/survivability trade-off and the complete Fire kit's balance.

### 7. Implement five level-51 affinities

**Files:** `src/core/structs.h`, `src/classes/innates.c`,
`src/core/utility.c`, `src/core/prototypes.h`, `src/mob/mobact.c`.
Use `src/world/map.h` ranges unchanged.

- Append four passive innate IDs and names with null handlers: Air, Water, Fire
  and Earth Affinity. Register each at **51** for its matching Conjurer spec.
  Move Psycheporter Astral Affinity from **30 to 51**.
- Use one shared PC/native-plane eligibility check and existing `has_innate()`
  level enforcement. Reject invalid rooms/NPCs before reading room state.
- Replace the existing Astral exemption in `aggressive_to()`, removing its
  player-versus-mob-level comparison. Protection requires native-plane affinity
  **and no `CheckFor_remember(mob, player)` result**.
- Apply the same eligibility/memory rule to the existing special cases for
  mobs **19840 and 19870** in `MobStartFight()`. Do not add a global exemption
  to scripted attacks.
- Preserve ordinary retaliation, memory creation/propagation and group/pet
  ownership rules. A remembered player can be attacked again; memoryless mobs
  may resume ignoring the player after combat ends, as the existing model allows.

| Affinity | Covered VNUMs, inclusive |
| --- | --- |
| Air | 24401-24525 |
| Water | 23201-23325 |
| Fire | 25401-25525 |
| Earth | 23801-23925 |
| Astral | 19701-19825 |

**Proof:** all five specialisations at 50/51 against lower/higher-level mobs;
Psycheporter at 30/41; both astral bosses; native versus other plane; first/last
and adjacent out-of-range rooms; invalid room/NPC/no-innate cases. Exercise actual
entry aggro, provoke/flee/re-enter, group memory and pet provocation.
City of Brass, Charcoal Palace, Earth rooms **23926-23929** and Astral side rooms
**19826-19886** remain outside the exemption. Groupmates/pets/charmies do not
inherit it. Retain the acknowledged other scripted-attack gaps.

Add the issue's focused `test_planar_affinity_runtime.py` using production
registration/aggro paths, not only a helper mock. Update the
`test_race_rebalance.py` assertion that Reflection is last while retaining its
Reflection coverage. Check `innates` output for correct names and unlock levels.

### 8. Complete help and qualify the combined package

Update both help sources alongside each step, then reconcile them together:

- **Conjurer**, all four **Magus** pages and their spell lists: roles, correct
  circle-10 forms and level-51 affinities; cross-links and accurate availability.
- Dedicated **Earth Form**, **Fire Form**, **Water Form** pages; update **Air
  Form**. Include 8-unit duration, self-only/terrain rules, exact effects,
  elemental conflicts, expiration and counterplay.
- **Stone Skin**, **Earthen Maul**, **Ethereal Recharge**, **Dimension Door**,
  **Relocate**, **Conjure Water**, **Water to Life**, **Fireball**, **Solar Flare**,
  **Conjure Elemental** and **Conjure Greater Elemental**: all final numbers and
  restrictions described in steps 2-6. Add missing dedicated parsed **Stone
  Skin** and **Water to Life** topics; do not mistake See also mentions for pages.
- **Psycheporter**, **Astral Affinity**, four new elemental affinity pages and
  a **Planar Affinity** overview. Explain own-plane limits, provocation and
  lack of inherited group/pet protection.
- Distinguish 5-second shoreline preparation from Air post-cast lag, Water
  Form travel from Water Affinity, 232 base Water to Life HP from modified
  healing, and Fire absorption recovery from a castable self-heal.

Preserve the established help markup, title/alias conventions and line widths.
Check duplicate titles, cross-links and exact body parity where required by
existing tests. Use the importer's dry-run on an explicitly local/dev target,
then verify real in-game help lookup in the isolated/staging environment;
parsed-source precedence must show the new text.

## Verification and evidence

### Focused executable checks

Extend existing tests before creating replacements. New behavior without a
suitable existing harness needs a small production-code executable test under
`tests/async/`, using existing `_paths`/harness conventions and outputs under
`bin/`. Anticipated gaps are the combined Conjurer spell changes, water spring
lifecycle, shoreline lifecycle, mephit equivalence and Planar Affinity.
Record final test filenames/commands here as each is implemented.

Run the existing checks relevant to the slice being changed:

- Forms/casting: `test_elemental_aura_runtime.py`,
  `test_affect_wear_off_message_contract.py`, `test_spell_affect_regressions.py`,
  `test_memorized_spell_eligibility.py`, `test_spell_schedule_failure_runtime.py`.
- Healing compatibility: `test_healing_spell_precedence_runtime.py` and
  `test_vampiric_overheal_regen.py`, plus actual Recharge cap proof through
  the production healing functions.
- Movement: `test_movement_liveness_runtime.py`,
  `test_combat_movement_feedback.py`, `test_innate_plane_shift.py`,
  plus both new water action lifecycles and ocean teleport controls.
- Affinity: `test_innate_reflection.py`, updated `test_race_rebalance.py`,
  new `test_planar_affinity_runtime.py`, and real plane-entry journeys.
- Help: `test_help_import_live_parser.py`, `test_help_import_atomic.py`,
  `test_class_helpfiles_contract.py`, `test_help_layout.py` and
  `test_flatfile_help_catalog.py`; extend focused topic/parity coverage for
  the new entries.

For each named Python check, run `python3 tests/async/<filename>` directly.
Use ASan/UBSan for the new affect/event lifecycle harnesses where the existing
harness supports them. Verify real command/resource/persistence paths when those
are the acceptance claim; source-string assertions or service stubs alone are
not gameplay proof.

After C/C++ changes run `make -C src`; the server is `bin/server/dms_new`.
Run applicable MariaDB/flat-file spellbook, affect and help checks where changed
IDs or consumers cross those boundaries. Keep generated artifacts under `bin/`.
Run `./scripts/format.sh --check` and `git diff --check`; resolve formatting
manually. Do not wait for hosted CI or substitute it for local proof, and do not
bypass code-review requirements.

### Functional gameplay evidence and player handoff

Run the per-step gameplay journeys needed to prove the agreed mechanics are
reachable and correct: form/resource cleanup, Earth layer consumption, the Air
healing cap, water cancellation/costs, Fire caller restrictions and summon
equivalence, affinity boundaries, and actual help lookup. Test interactions
together where one can break another, without evaluating relative class power.

Retain compact, reproducible evidence with baseline/candidate SHAs, environment,
commands, relevant inputs, expected versus actual results and known gaps. Store
scratch binaries/logs under `bin/`; summarize acceptance in this plan or the
repository's existing QA documentation without committing credentials, logs or
player/account data.

Hand players the implemented mechanics and numbers through the updated help.
Balance playtesting and any later tuning follow player feedback; they are not
completion gates for this implementation. Do not add comparative PvE/PvP
campaigns, burst/sustained/recovery benchmarks or CLASS-POINTS scorecards.

## Completion checklist

- [ ] All approved changes in steps 1-7 are implemented with no extra tuning.
- [ ] Every per-step proof passes, including cancellation after a transient
      combat/form/movement change and unchanged non-targeted callers.
- [ ] Both help sources and actual help lookups agree on the final behavior.
- [ ] Applicable local builds, focused regressions, persistence journeys and
      formatting checks pass; unavailable evidence is explicitly recorded.
- [ ] Functional gameplay evidence and known limitations are recorded; help
      provides the implemented mechanics for players' balance testing.
- [ ] Final diff passes ablation review: every change supplies a requirement or
      a demonstrated dependency, and no unrelated work was discarded.
- [ ] Implementation receives required code review; findings are resolved and
      the plan records exact delivered commits and remaining release work.

## Planning checkpoint

### Implementation checkpoint, 2026-10-25

- Baseline: clean branch at `9d226467f`; gameplay base and fetched `origin/master`
  remain `e1efb9bc0779e8b6615353c5672e29f21c6bb7a8`. The main checkout is on unrelated
  `branch/contain-learning-feedback` and is untouched. The dedicated worktree has
  no `.env`; the main checkout reports `ENVIRONMENT=local`.
- Ablation: deliver affinity first because it is independent of forms/events.
  Append four passive IDs (180-183), move Astral's grant to 51, and use one shared
  PC/native-plane eligibility function at the two real aggression callers. Keep
  existing memory creation, boundaries, scheduler and persistence formats.
- Files: `structs.h`, `innates.c`, `prototypes.h`, `utility.c`, `mobact.c`, both help
  sources, focused affinity test, Reflection contract adjustment and this plan.
  No schema, prototype, balance benchmark or production change is required.
- Pre-change checks passed: `test_innate_reflection.py`, `test_race_rebalance.py`,
  `test_elemental_aura_runtime.py`, `test_class_helpfiles_contract.py`.
- Candidate checks so far: `test_planar_affinity_runtime.py` passes with ASan/UBSan
  through actual registration, innate listing, ordinary aggression and both boss
  paths, levels 30/41/46/50/51/56, lower/higher mob levels, all boundary rooms,
  invalid rooms, NPC/no-spec controls and remembered targets. The final harness
  also executes actual memory lookup, group-memory creation and clearing, and
  memoryless-mob behavior. Full server room-entry and pet-combat journeys remain
  for combined functional qualification in step 8.
- Passed: `python3 tests/async/test_innate_reflection.py`,
  `python3 tests/async/test_race_rebalance.py`,
  `python3 tests/async/test_planar_affinity_runtime.py`,
  `python3 tests/async/test_class_helpfiles_contract.py`,
  `python3 tests/async/test_help_layout.py` (3 tests),
  `python3 tests/async/test_help_import_live_parser.py`, and
  `python3 tests/async/test_flatfile_help_catalog.py` (including production
  `wiki_help()` lookups of all five affinity topics and the overview).
- `bash tests/async/with_disposable_mariadb.sh python3
  tests/async/test_help_import_atomic.py` passed **all 9 tests**, including a new
  full-source dry-run/import into an isolated schema proving one page per affinity
  and parsed-source precedence. No test uses the game database.
- `make -C src -j8` passed with no warnings; `./scripts/format.sh --check` and
  `git diff --check` pass. Build output is under
  `bin/qualification/issue215/` (untracked). No full regression or hosted CI wait
  is needed for this independent slice. No affinity persistence format changed:
  passive grants are derived from existing class/spec/level, not stored timers.
- Delivered: `9c13feaac66e5bcc51e9c3ee8adb91b1395eaf6a`, pushed on
  `branch/issue-215-conjurer-rebalance`; review-ready
  [PR #376](https://github.com/LuminariMUD/Duris/pull/376) targets `master`.
- Next: continue forms/casting on `branch/issue-215-elemental-forms`, stacked on
  #376, and remaining steps. No gameplay test server has been started and no
  production operations performed. Existing Git GC warnings about unreachable
  loose objects predate this work; no logs or unrelated repository state removed.

### Elemental forms checkpoint, 2026-10-25

- Branch `branch/issue-215-elemental-forms` is based on affinity handoff
  `6a8ba49b4`. Append spell IDs 684-686; register Earth/Fire/Water Form for only
  the matching Magus at circle 10, with Air's 4-pulse casting pattern and finite
  8-unit affects. Keep the existing affect list/codec/expiry/dispel paths.
- Add one shared preflight/handler conflict check. It rejects form/partial-aura
  combinations before mana/prepared-spell consumption and at application. Keep
  Druid/Pyro terrain rules, independent shields and existing Air effect intact.
  No new affect flags, scheduler, schema or stat abstraction is required.
- Corresponding help in both sources covers all four forms, spec spell lists
  and Conjurer. Water travel/Air healing text will follow their actual behavior,
  rather than advertising features before their slice lands.
- `test_elemental_forms_runtime.py` passes under ASan/UBSan using production
  registration, handlers, affect list operations, wear-off and binary PC affect
  save/restore. Covers exact attribute records/flags/duration, spec/self/NPC
  controls, all relevant terrains, paired form/aura conflict orders, partial
  effects, recast rejection, independent Fireshield ownership and one wear-off
  message. General stat recalculation and scheduler are fixtures; complete
  parser/resource and combat journeys remain for step 8.
- Extended `test_memorized_spell_eligibility.py` passes for saved new-form copies
  at levels 41/45/46/50/51/56, including wrong-spec denial through production
  circle/knowledge checks. Existing `test_elemental_aura_runtime.py`,
  `test_affect_wear_off_message_contract.py`, `test_spell_affect_regressions.py`,
  `test_spell_schedule_failure_runtime.py`, `test_spellbook_persistence_contract.py`,
  `test_master_spellbook.py`, class-help/layout and flat-file runtime help checks
  pass. These do not claim full server combat coverage.
- `make -C src -j8` passed with no warnings. Format remains check-only; format and
  diff checks pass. Logs and scratch harnesses remain under `bin/`.
- Delivered forms commit: `53a7e1a2cbb95857f6af48f52cc32192ce9e75da`, pushed;
  [PR #378](https://github.com/LuminariMUD/Duris/pull/378) targets
  `branch/issue-215-conjurer-rebalance`. The isolated full-source importer test
  now also proves all four form topics and passed (1 targeted MariaDB test).
- Next: Earth Stone Skin/Earthen Maul on `branch/issue-215-earth-mechanics`,
  stacked on forms; then Air recovery/travel,
  reliable spring, shoreline movement, Fire pressure/mephits, and combined
  gameplay qualification. The original no-extra-tuning boundaries remain.

### Earth checkpoint, 2026-10-25

- Branch `branch/issue-215-earth-mechanics` builds on forms commit `53a7e1a2c`.
  Changes are limited to `magic.c`, existing form/runtime-help tests, both help
  sources and this plan. Stone Skin counts existing layers only for Earth Magus
  PC recipients; it never refreshes or combines them. A small internal
  `has_other_skin_spell()` supplies the unchanged exclusion list to both the
  existing general skin check and the layering exception, avoiding two lists.
- Earthen Maul converts earthless/airborne situations to normal tier 1 **after**
  the existing indoor upgrade. Valid grounded indoor/mountain/lava tiers and
  saves remain. No `fight.c` or affect implementation change is needed.
- Extended `test_elemental_forms_runtime.py` passes with ASan/UBSan: caster versus
  recipient matrix including NPCs/ordinary recipients; 1-3 layers and rejected
  fourth; distinct charges/durations; production single-layer decrement;
  production Earth-aura/skin mitigation branches; Earth Elemental and NOREDUCE
  controls; production critical all-layer shatter; other skin exclusions; and
  actual Maul handlers for Druids/Earth Magi at 46/56, saved/unsaved, indoor versus
  outdoor, grounded/airborne, water/ocean/no-ground/all four plane sectors,
  ordinary/indoor/mountain/lava tiers with matched dice. Reuses the forms/codec
  evidence; full server combat/expiry journeys still belong to step 8.
- `make -C src -j8` passes with no warnings. Class-help/layout and check-only
  formatting/diff checks pass. Added the missing dedicated parsed Stone Skin
  page and aligned both sources' Earth Magus, Stone Skin and Earthen Maul text.
- Delivered Earth commit: `cb4f8206dfc6c6a507469517621976788d604b20`, pushed;
  [PR #379](https://github.com/LuminariMUD/Duris/pull/379) targets forms branch.
- Next: Air healing/travel on `branch/issue-215-air-recovery`, stacked on #379.
  Preserve the verified forms/affinity evidence and avoid full-suite reruns for
  this local spell change. Air uses the existing final healing cap and two
  post-cast wait branches; no new healing API or movement service is needed.

### Air checkpoint, 2026-10-25

- Branch `branch/issue-215-air-recovery` is based on Earth commit `cb4f8206d`.
  `ethermancer.c` adds only the active-Air-Form/self/Air-Magus-PC exception to
  ordinary Ethereal Recharge and passes `min(maxHP, currentHP + 100)` to the
  existing heal chain. Other target routes and Greater Recharge stay unchanged.
  `magic.c` adds only Air-PC 3-second Dimension Door and 5-second Relocate waits,
  preserving their positions before existing travel rejection checks.
- Extended existing `test_cleric_ward_runtime.py` under ASan/UBSan instead of
  creating another healing harness. It executes production `heal()`/`vamp()`,
  Cure Blind, ordinary/Greater Recharge, both whole travel handlers and
  `can_relocate_to()`; general room-entry checks/placement and UI are fixtures.
  Checks low/full/overfull HP, enhanced/hardcore/incoming-aura amplification,
  Plague and Blackmantle reduction, actual achievement/XP credit, Cure Blind at
  the cap, loose aura/wrong spec/other-player controls, normal Phantasmal targets,
  Air/Void pet targets versus Water-pet denial, and unchanged Greater Recharge.
  Travel checks measure pulses for Air/ordinary/Shadow PCs and NPCs on success
  and ocean/no-teleport/hostile-PvP/non-raidable rejection.
- `test_healing_spell_precedence_runtime.py` and `test_vampiric_overheal_regen.py`
  pass. Incremental `make -C src -j8` passes with no warnings after correcting an
  initial patch-location mistake in the adjacent Greater Recharge handler;
  final diff leaves that handler unchanged. Class-help/layout, formatting and
  diff checks pass. Both sources describe the final cap and post-cast waits.
- Delivered Air commit: `d1e42ef56f4eebe78b3cff1dcd9daa38cb00be70`, pushed;
  [PR #380](https://github.com/LuminariMUD/Duris/pull/380) targets Earth branch.
- Next: Conjure Water on `branch/issue-215-reliable-spring`, stacked on #380;
  then Water shoreline and Fire mechanics. Reuse existing healing/build evidence.
  Spring pending state is only its existing actor-owned event with copied origin
  room, checked via room occupants/events and cancelled by actual room departure.
  Reuse `can_use_innate()` for read-only availability and retain other innates'
  `check_innate_time()` semantics. No reservation registry is needed.

### Reliable spring checkpoint, 2026-10-25

- Branch `branch/issue-215-reliable-spring` builds on Air `d1e42ef56`. Changes:
  `innates.c`, its callback declaration, one `char_from_room()` cancellation hook
  after leave-veto checks, the 300-second property, both help sources, focused
  runtime/help checks and this plan. Reuse `can_use_innate()` and actor-owned
  copied event data; no global reservations or new timer semantics.
- Creation and lag are one `PULSE_VIOLENCE` (4 seconds) concurrently. Check
  spring/pending occupancy before scheduling, then check origin/eligibility/use
  and occupancy on completion. Place VNUM 93300 before committing the use. A
  failed placement/final eligibility check extracts only this attempt's object.
  Normal extraction already cancels all actor events; departure now cancels the
  spring specifically. The existing 15-minute decay remains.
- New `python3 tests/async/test_conjure_water_runtime.py` passes ASan/UBSan on the
  **production scheduler**, innate registration/availability/use functions and
  short-affect expiry. Covers exact pre/post-4-second position in the event
  timeline, two-player room race/repeat commands, existing/arriving spring,
  5-minute cooldown and 15-minute decay/resummon, creation/placement/final
  eligibility failure, leave/return cancellation, death, extracted/freed actor,
  eligibility/cooldown changes during wait, real scheduler rejection, retry and
  balanced event/payload cleanup. Object creation/placement/decay and room-leave
  invocation are controlled fixtures; actual hook placement is also asserted.
- Incremental `make -C src -j8` passes with no warnings after adding the missing
  `top_of_world` declaration. Innate plane-shift dispatch/cooldown, movement
  liveness, class-help/layout and flat-file help runtime checks pass; the latter
  verifies Conjure Water and the new dedicated parsed Water to Life formula page.
  Format/diff checks pass. Water to Life implementation is untouched.
- Delivered spring commit: `6c1bdc787ae484dea9fedc100f53ed8b2a1aae49`, pushed;
  [PR #381](https://github.com/LuminariMUD/Duris/pull/381) targets Air branch.
- Next: shoreline traversal on `branch/issue-215-water-shoreline`, stacked on
  #381. Use the running actor event's origin/direction/destination as the narrow
  permission for directed entry; generic `can_enter_room()` stays restrictive.
  Callback returns through `do_move()` and existing movement/proc/trap/cost paths.
  Add only the needed combat/departure/form-removal cancellation hooks. `abort`
  must also cancel this new preparation, requiring a narrow `sparser.c` edit.
  Tests that isolate affect/abort code need a weak callback label in existing
  `harness_stubs.cpp`. No new public movement flags or reservation state.

### Shoreline checkpoint, 2026-10-25

- Branch `branch/issue-215-water-shoreline` builds on spring `6c1bdc787`. One
  actor-owned event records origin/direction/destination. The running event is
  the narrow authorization for that mover's directed ocean entry; the public
  `can_enter_room()` always uses normal restrictions. Completion returns through
  `do_move()`/ordinary procs, traps and movement checks, with route/form/combat
  revalidation after specials and traps. No global bypass, new public movement
  flags or general movement service was added.
- Active Water Form + Water Magus PC is the only new gate, including level 46.
  Shoreline delay is 5 seconds both ways; ocean-to-ocean has no new delay.
  `move_cost()` applies `max(1, cost*3/4)` for steps touching ocean after its
  existing modifiers and before the outer stance/injury surcharges. Entry
  permission excludes mounts/riders/cargo; followers cannot inherit event ownership.
- Departures, either participant entering combat, any Water Form removal and
  explicit `abort` cancel preparation. Existing extraction cancellation owns the
  payload. Guarded the ordinary dispatcher after `special()` against a freed or
  replaced mover, needed when delayed completion invokes scripted movement.
- New `test_water_shoreline_runtime.py` passes under ASan/UBSan with production
  scheduler, command/dispatcher, entry checks, costs and ordinary movement prefix
  through traps/exhaustion/deduction. Tests 46/50/51, timed both-way crossings,
  immediate ocean-to-ocean, rounded minimum-one costs and exact exhaustion,
  stance/flurry/injury placement, currents, transient combat/form/departure,
  changed/closed exits, death/abort, form loss in movement special, trap
  interruption, mount/rider/cargo/loose-aura/wrong-spec controls, real scheduling
  refusal/retry and proc extraction returning false. Final placement, complete
  follower/arrival behavior, and combat/form service calls are fixtures; hook
  placement is asserted and full server/PvP journeys remain for step 8.
- Existing Control Flee and movement-liveness sanitizer regressions pass;
  updated the Control Flee fixture to include the restrictive entry wrapper and
  to supply a neutral shoreline context. Forms/Earth and spring regressions pass.
  Full and final incremental MariaDB builds passed with no warnings. Existing
  `test_item_actions_runtime.py` also passes, including abort/wait isolation.
  Both help sources now explain shoreline timing, discount, cancellation,
  personal-only entry, separate affinity and normal rules after expiry at sea.
- Class-help/layout, flat-file runtime help (including shoreline numbers),
  documentation, check-only formatting and diff checks pass.
- Delivered shoreline commit: `f1c7e4b2e19d75ee485981a0193c246dd133e5d1`, pushed;
  [PR #382](https://github.com/LuminariMUD/Duris/pull/382) targets spring branch.
- Next: Fire damage/mephits on `branch/issue-215-fire-mechanics`, then combined
  gameplay. Source inspection adds two necessary caller files:
  `item/studio_abilities.c` and `item/device_actions.c` currently invoke
  character-targeted spells as `SPELL_TYPE_SPELL` with no source object, so
  Solar Flare needs its existing object argument populated for those item calls
  to remain unbuffed. Keep all other item calls unchanged.
- The legacy staff/wand/scroll paths also label their spell calls as ordinary
  casts. `actoth.c` and staff-area helper `utility.c` therefore pass existing
  STAFF/WAND/SCROLL call types **only for Solar Flare**. The staff-area helper's
  only live player-driven Solar caller is the legacy staff path. No new call
  context API or global policy is needed, and all other spells retain their
  prior call type/object arguments.
- `setup_pet()` appends the owner keyword after summon naming, but currently
  overwrites an owned name without releasing it or marking the replacement as
  owned. The mephit path requires a narrow ownership repair in `necromancy.c`;
  test the real setup/free contract alongside summon equivalence. No new pet
  types, prototypes, flag policy or persistence representation is needed.
  Do not claim complete functional
  qualification until the remaining journeys and Fire implementation pass.

### Fire checkpoint, 2026-10-25

- Branch `branch/issue-215-fire-mechanics` builds on shoreline `f1c7e4b2e`.
  Fireball removes only its Globe flag for Fire Magus PCs at player level 51+.
  Solar Flare multiplies only player Fire spell direct base damage by 110/100
  with integer truncation and unchanged RNG/secondary effects. Existing item
  dispatchers preserve Solar's item origin/type as detailed above; other spells'
  call arguments stay unchanged.
- Optional `mephit` validation is shared by casting preflight and both summon
  handlers. Normal VNUM 1100/random 1110-1112 selection, scaling, control and
  duration paths are reused. Only instance strings and Fireshield change. The
  original race/protections/Infuse Life/caps remain; no new prototype or ability.
  `setup_pet()` now releases an owned old name and owns its appended replacement.
- `test_conjurer_fire_runtime.py` passes ASan/UBSan: production summon handlers,
  terrain/cap helpers and pet setup; matched random state/call counts for every
  greater variant, neutral/good/bad terrain and Infuse Life 0/100; exact stats,
  control affects, durations, original VNUMs, cap failures, malformed args and
  leak-free name ownership. Replays actual affect bit-recalculation, Globe,
  Fire absorption, cold-vulnerability and per-attacker shield/owner-memory
  branches. Checks player 50/51 versus spell power 100, NPC/Star/other spec/item
  controls, exact +10% and unchanged secondary RNG, full Fire Form absorption
  ceiling and cold response, multi-mob pull memory and other pet provocation.
  Prototype reads, general stat/combat services and damage tail are fixtures;
  complete server integration remains for step 8.
- Extended existing forms preflight check proves invalid Fire options reject
  before the resource sentinel while other callers retain ignored arguments.
  Device/Studio regressions include Solar's source/type through actual legacy
  and modern staff/wand/scroll and passive/active Studio dispatchers. Both help
  sources describe the final Fire kit and optional summons. Full flat-file build
  completed in preparation for isolated gameplay; final incremental rebuild
  will include the latest item-call adjustments.
- Final MariaDB `make -C src -j8` passes with warnings treated as errors.
  Existing pet-control/drop, class-help/layout, runtime help, documentation,
  check-only formatting and diff checks pass. No full regression was repeated.
- **Required discovered follow-up:** ordinary Conjurer pet crash snapshots have
  no restore-state payload, so loading VNUM 1100/1110-1112 reconstructs prototype
  Fireshield/names instead of the chosen instance. This predates the feature but
  would erase a mephit's defining choice on recovery. Publish Fire now as its
  focused chunk, then repair this through the existing pet-state codec in a
  separate dependent PR. Preserve both plain/mephit instance stats and finite
  lifetime; add no gameplay pet variant, slot, prototype or schema.
- Delivered Fire commit: `5b53d6617f235c047f15053c5c92c9ecdfd63c8a`, pushed;
  [PR #384](https://github.com/LuminariMUD/Duris/pull/384) targets shoreline branch.
- Crash-state repair on `branch/issue-215-fire-persistence`: append internal
  creation-path labels for plain/mephit Fire summons to the existing portable
  pet-state enum. These are transport labels for the already-approved choice,
  not new gameplay pets, VNUMs, races, powers, slots or a new payload format.
  Use existing intrinsic-state capture/apply and finite charm/death deadlines;
  keep existing Conjurer capacity checks and zero legacy necromancy power cost.
  Reconstruct only the mephit's constant full description on typed restoration;
  the codec already carries its exact keywords, short/room descriptions, stats
  and shield flags. Required owning files: `pet_restore_state.h/.c`,
  `pet_restore_runtime.c`, existing Fire summon paths/tests and this plan.
- Next: implement this narrow crash-state repair, then complete
  isolated gameplay/help/persistence journeys and final ablation/review audit.

### Fire recovery checkpoint, 2026-10-25

- `branch/issue-215-fire-persistence` adds internal state labels 23/24 for the
  existing plain/mephit Fire creation paths, with unchanged original VNUMs.
  Reuse portable state version 1, intrinsic flags and existing full NPC
  materialization. There is no new database schema or gameplay pet/slot.
  Existing elemental-count cap helpers still own capacity; the saved Fire pets
  retain their previous zero necromancy-power cost.
- Both original Fire summon paths mark final intrinsic state before control
  handling. Their existing death schedules route through the maintained
  `schedule_pet_death()` for marked summons so the exact finite deadline is
  captured. Unmarked other-element summons keep their old event submission.
  Restoration reconstructs the mephit's constant full description and retains
  saved exact names/short/room descriptions, scaled stats, shield and deadlines.
- Extended `test_conjurer_fire_runtime.py` passes ASan/UBSan through real
  capture/encode/decode/apply/lifetime restoration for both choices and all
  original variants, while retaining matched-RNG equivalence and string cleanup.
  Extended `test_player_load_items.py` passes actual pet staging/materialization
  for all eight plain/mephit original-VNUM cases and finite restoration.
  `test_player_load_pets.py` contracts pass.
- `test_pet_restore_state.py` passes new kind/prototype/cost boundaries and
  legacy v1 compatibility. Its pre-existing v1 fixture failed unchanged on the
  parent because it trimmed a current v12 checkpoint as if only v5/v7 additions
  existed, retaining wallet/trade bytes. Replaced that brittle surgery with a
  directly authored, fixed v1 wire fixture; no production checkpoint code changed.
- MariaDB and flat-file builds pass with warnings treated as errors. Native
  object/materialization services remain controlled in these component tests;
  actual socket/recovery gameplay is the next combined qualification chunk.
- Older binaries cannot decode labels 23/24 and will retain such pets through
  their existing invalid-state holding path. Review/release must consider that
  normal rollback limitation; no production release or migration is performed.
- Next: publish this repair PR, then run the isolated combined Conjurer journeys,
  reconcile help/import evidence and review the complete stack. Do not rerun
  unrelated full regression suites.

### Review repair checkpoint, 2026-10-25

- Source-validated review finding on #379: snapshot affect hydration prepends
  captured newest-first rows in forward order, reversing Stone Skin layers.
  Legacy binary `restoreAffects()` has the same issue. Reproduced distinct
  charge/duration reversal in the sanitizer harness before repair.
- `branch/issue-215-affect-restore-order` fixes the owning consumers:
  `player_load_materialize.c` replays snapshot rows in reverse; `files.c`
  reverses only its new restored prefix, preserving any pre-existing affects.
  No new saved fields or special Stone Skin representation is needed.
- Extended `test_elemental_forms_runtime.py` exercises two repeated binary and
  snapshot-codec/hydration round trips with charges 19/9/8 and durations 4/2/1,
  then the actual newest-first decrement. Also checks a pre-existing independent
  affect stays behind the restored prefix. General stat services stay fixtures.
- Review findings on #382 still need their own focused repair: input routing
  must admit `abort` during shoreline waits; movement must capture its crossing
  context before specials because cancellation clears callback/actor fields.
  Add outbound cancellation and real input-routing regressions before publishing.
- Affect ordering repair delivered as `c7a6d009b99012dfd9c4273debc52553e58387eb`,
  review-ready [PR #387](https://github.com/LuminariMUD/Duris/pull/387), based on
  #386. Binary/snapshot regressions, Web Spray, player-load contracts, MariaDB
  build and format checks pass.
- `branch/issue-215-shoreline-interruption` now captures the crossing context
  before `special()` and extends the existing restricted input predicate,
  whitelist and interpreter gate to pending shoreline events. It grants abort
  without the separate spell-abort toggle and preserves unrelated type-ahead.
  Reproduced outbound cancellation failure before fixing it. Both-way transient
  interruption tests, actual queue/predicate state-matrix tests, spell-abort
  contracts, selective-queue compatibility, movement liveness and Control Flee
  regressions pass. MariaDB/flat-file builds and check-only formatting pass.
- Existing `test_game_loop_phase_contract.py` has a pre-existing stale direct
  auction-outbox assertion: the recurring phase now calls the already-existing
  `critical_gameplay_publish_outbox()` helper, which calls the auction publisher.
  This branch changes only the input predicate in `comm.c`, not that phase.
  Repair the test separately to follow both real calls; no game-loop change is
  required. Keep this outside the shoreline implementation patch.
- Fire recovery was delivered as `53679b9f04e39f3a13bfba39b13b832268d209e5`,
  review-ready [PR #386](https://github.com/LuminariMUD/Duris/pull/386), based on
  #384. Combined socket/recovery qualification remains pending these repairs.

### Review repair checkpoint, 2026-10-25

- Source-validated review finding on #379: snapshot affect hydration prepends
  captured newest-first rows in forward order, reversing Stone Skin layers.
  Legacy binary `restoreAffects()` has the same issue. Reproduced distinct
  charge/duration reversal in the sanitizer harness before repair.
- `branch/issue-215-affect-restore-order` fixes the owning consumers:
  `player_load_materialize.c` replays snapshot rows in reverse; `files.c`
  reverses only its new restored prefix, preserving any pre-existing affects.
  No new saved fields or special Stone Skin representation is needed.
- Extended `test_elemental_forms_runtime.py` exercises two repeated binary and
  snapshot-codec/hydration round trips with charges 19/9/8 and durations 4/2/1,
  then the actual newest-first decrement. Also checks a pre-existing independent
  affect stays behind the restored prefix. General stat services stay fixtures.
- Review findings on #382 still need their own focused repair: input routing
  must admit `abort` during shoreline waits; movement must capture its crossing
  context before specials because cancellation clears callback/actor fields.
  Add outbound cancellation and real input-routing regressions before publishing.
- Fire recovery was delivered as `53679b9f04e39f3a13bfba39b13b832268d209e5`,
  review-ready [PR #386](https://github.com/LuminariMUD/Duris/pull/386), based on
  #384. Combined socket/recovery qualification remains pending these repairs.

### Historical planning-only evidence

The current change writes this plan and preserves the previous #264 document.
Source inspection supports the proposed paths above. No proposed-feature tests,
full build or gameplay session has been run for this
documentation change. Implementation remains pending.

Planning validation: `python3 tests/async/test_documentation_contract.py` passed
all **14 tests**, including maintained document links and anchors. The preserved
`plan-issue-264.md` matches the original file byte-for-byte; `git diff --check`
passes. Gameplay/build evidence above is future work, not a result of this check.
